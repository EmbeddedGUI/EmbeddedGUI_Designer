
"""Release build pipeline for UI Designer projects."""

from __future__ import annotations

import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import time

from ..generator.code_generator import generate_all_files_preserved
from ..generator.resource_config_generator import ResourceConfigGenerator
from ..model.build_metadata import (
    DEFAULT_SDK_REMOTE_URL,
    collect_git_metadata,
    collect_sdk_fingerprint,
    current_designer_metadata,
    current_designer_revision,
    describe_git_revision,
    is_git_worktree_dirty,
)
from ..model.diagnostics import (
    analyze_page,
    analyze_project_callback_conflicts,
    diagnostic_entry_payload,
    sort_diagnostic_entries,
)
from ..model.release import ReleaseArtifact, ReleaseRequest, ReleaseResult
from ..model.workspace import compute_make_app_root_arg, is_valid_sdk_root, normalize_path
from ..utils.scaffold import make_app_build_mk_content, make_app_config_h_content, make_empty_resource_config_content


MAX_RELEASE_HISTORY = 100


def build_release_id() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def collect_release_diagnostics(project) -> dict[str, list[object]]:
    if project is None:
        return {"errors": [], "warnings": [], "entries": []}

    resource_dir = project.get_eguiproject_resource_dir() if hasattr(project, "get_eguiproject_resource_dir") else ""
    catalog = getattr(project, "resource_catalog", None)
    string_catalog = getattr(project, "string_catalog", None)
    entries = []
    for page in getattr(project, "pages", []) or []:
        entries.extend(
            analyze_page(
                page,
                resource_catalog=catalog,
                string_catalog=string_catalog,
                source_resource_dir=resource_dir,
            )
        )
    entries.extend(analyze_project_callback_conflicts(project))
    entries = sort_diagnostic_entries(entries)
    errors = [entry for entry in entries if getattr(entry, "severity", "") == "error"]
    warnings = [entry for entry in entries if getattr(entry, "severity", "") == "warning"]
    return {
        "entries": entries,
        "errors": errors,
        "warnings": warnings,
    }


def summarize_diagnostic_entries(entries: list[object]) -> list[str]:
    messages = []
    for entry in entries:
        page_name = getattr(entry, "page_name", "") or "<project>"
        widget_name = getattr(entry, "widget_name", "")
        scope = page_name
        if widget_name:
            scope = f"{scope}/{widget_name}"
        messages.append(f"{scope}: {getattr(entry, 'message', '')}")
    return messages


def _first_release_diagnostic_text(diagnostic_entries: list[dict[str, object]]) -> str:
    if not diagnostic_entries:
        return ""
    first_entry = diagnostic_entries[0] if isinstance(diagnostic_entries[0], dict) else {}
    severity = str(first_entry.get("severity") or "").strip() or "issue"
    page_name = str(first_entry.get("target_page_name") or first_entry.get("page_name") or "").strip()
    widget_name = str(first_entry.get("target_widget_name") or first_entry.get("widget_name") or "").strip()
    scope = page_name or "<project>"
    if widget_name:
        scope = f"{scope}/{widget_name}"
    message = str(first_entry.get("message") or "").strip()
    return f"{severity} {scope}: {message}" if message else f"{severity} {scope}"


def release_history_path(project_dir: str, output_dir: str = "") -> str:
    project_dir = normalize_path(project_dir)
    output_dir = normalize_path(output_dir)
    base_dir = output_dir or os.path.join(project_dir, "output", "ui_designer_release")
    return os.path.join(base_dir, "history.json")


def load_release_history(project_dir: str, output_dir: str = "") -> list[dict[str, object]]:
    path = release_history_path(project_dir, output_dir=output_dir)
    if not os.path.isfile(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError, TypeError):
        return []
    return data if isinstance(data, list) else []


def latest_release_entry(project_dir: str, output_dir: str = "") -> dict[str, object]:
    history = load_release_history(project_dir, output_dir=output_dir)
    return history[0] if history else {}


def _write_release_history_entry(project_dir: str, output_dir: str, entry: dict[str, object]) -> str:
    path = release_history_path(project_dir, output_dir=output_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    history = load_release_history(project_dir, output_dir=output_dir)
    history = [entry] + [item for item in history if item.get("build_id") != entry.get("build_id")]
    history = history[:MAX_RELEASE_HISTORY]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return path


def _iter_files(root_dir: str) -> list[str]:
    resolved_root = normalize_path(root_dir)
    if not resolved_root or not os.path.isdir(resolved_root):
        return []
    result = []
    for current_root, _, filenames in os.walk(resolved_root):
        for filename in sorted(filenames):
            result.append(normalize_path(os.path.join(current_root, filename)))
    return result


def _hash_files(paths: list[str], base_root: str = "") -> str:
    digest = hashlib.sha256()
    base_root = normalize_path(base_root)
    normalized_paths = []
    for path in paths:
        resolved = normalize_path(path)
        if resolved and os.path.isfile(resolved):
            normalized_paths.append(resolved)

    for path in sorted(set(normalized_paths)):
        rel_path = path
        if base_root:
            try:
                rel_path = os.path.relpath(path, base_root)
            except ValueError:
                rel_path = path
        digest.update(rel_path.replace("\\", "/").encode("utf-8"))
        with open(path, "rb") as f:
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
    return digest.hexdigest()


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _ensure_project_scaffold(project_dir: str, app_name: str, screen_width: int, screen_height: int) -> None:
    os.makedirs(project_dir, exist_ok=True)
    resource_src_dir = os.path.join(project_dir, "resource", "src")
    os.makedirs(resource_src_dir, exist_ok=True)

    build_mk = os.path.join(project_dir, "build.mk")
    if not os.path.exists(build_mk):
        with open(build_mk, "w", encoding="utf-8") as f:
            f.write(make_app_build_mk_content(app_name))

    config_h = os.path.join(project_dir, "app_egui_config.h")
    if not os.path.exists(config_h):
        with open(config_h, "w", encoding="utf-8") as f:
            f.write(make_app_config_h_content(app_name, screen_width, screen_height))

    resource_cfg = os.path.join(resource_src_dir, "app_resource_config.json")
    if not os.path.exists(resource_cfg):
        with open(resource_cfg, "w", encoding="utf-8") as f:
            f.write(make_empty_resource_config_content())


def _write_generated_files(project_dir: str, files: dict[str, str]) -> list[str]:
    written_paths = []
    for filename, content in files.items():
        path = os.path.join(project_dir, filename)
        os.makedirs(os.path.dirname(path) or project_dir, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        written_paths.append(path)
    return written_paths


def _create_dir_alias(alias_dir: str, target_dir: str) -> None:
    if sys.platform == "win32":
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", alias_dir, target_dir],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return
        try:
            os.symlink(target_dir, alias_dir, target_is_directory=True)
            return
        except OSError as exc:
            detail = (result.stderr or result.stdout or "").strip()
            if detail:
                raise RuntimeError(f"Failed to create external app alias: {detail}") from exc
            raise RuntimeError("Failed to create external app alias") from exc

    os.symlink(target_dir, alias_dir, target_is_directory=True)


def _remove_dir_alias(alias_dir: str) -> None:
    if not alias_dir or not os.path.lexists(alias_dir):
        return
    try:
        if os.path.islink(alias_dir):
            os.unlink(alias_dir)
        else:
            os.rmdir(alias_dir)
    except OSError:
        shutil.rmtree(alias_dir, ignore_errors=True)

def _resolve_make_app_root_arg(sdk_root: str, app_dir: str, app_name: str) -> tuple[str, str]:
    raw_app_root_arg = compute_make_app_root_arg(sdk_root, app_dir, app_name)
    if not raw_app_root_arg.startswith(".."):
        return raw_app_root_arg, ""

    parent_dir = normalize_path(os.path.dirname(app_dir))
    alias_root = os.path.join(sdk_root, "build", "ui_designer_external_release")
    digest = hashlib.sha1(parent_dir.encode("utf-8")).hexdigest()[:12]
    alias_dir = os.path.join(alias_root, digest)
    os.makedirs(alias_root, exist_ok=True)

    if os.path.lexists(alias_dir):
        try:
            if os.path.samefile(alias_dir, parent_dir):
                return os.path.relpath(alias_dir, sdk_root).replace("\\", "/"), alias_dir
        except OSError:
            pass
        _remove_dir_alias(alias_dir)

    _create_dir_alias(alias_dir, parent_dir)
    return os.path.relpath(alias_dir, sdk_root).replace("\\", "/"), alias_dir


def _collect_ui_input_paths(project_dir: str, app_name: str) -> list[str]:
    paths = []
    project_file = os.path.join(project_dir, f"{app_name}.egui")
    if os.path.isfile(project_file):
        paths.append(project_file)
    eguiproject_dir = os.path.join(project_dir, ".eguiproject")
    for rel_dir in ("layout", "resources"):
        paths.extend(_iter_files(os.path.join(eguiproject_dir, rel_dir)))
    release_json = os.path.join(eguiproject_dir, "release.json")
    if os.path.isfile(release_json):
        paths.append(release_json)
    return paths


def _run_resource_generation(project, project_dir: str, sdk_root: str) -> tuple[list[str], str]:
    project.sync_resources_to_src(project_dir)
    resource_dir = project.get_resource_dir()
    source_resource_dir = project.get_eguiproject_resource_dir()
    source_dir = os.path.join(resource_dir, "src") if resource_dir else ""
    if not resource_dir or not source_resource_dir or not os.path.isdir(source_resource_dir):
        return [], "Resource generation skipped: no .eguiproject/resources directory found.\n"

    ResourceConfigGenerator().generate_and_save(project, source_dir)

    generator_script = os.path.join(sdk_root, "scripts", "tools", "app_resource_generate.py")
    if not os.path.isfile(generator_script):
        raise FileNotFoundError(f"Cannot find resource generator: {generator_script}")

    output_dir = os.path.join(sdk_root, "output")
    os.makedirs(output_dir, exist_ok=True)
    cmd = [
        sys.executable,
        generator_script,
        "-r",
        resource_dir,
        "-o",
        output_dir,
        "-f",
        "true",
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=180,
        cwd=sdk_root,
        check=False,
    )
    output_text = result.stdout + result.stderr
    if result.returncode != 0:
        raise RuntimeError(f"Resource generation failed (rc={result.returncode})\n{output_text.strip()}")

    output_paths = []
    if os.path.isdir(output_dir):
        for name in os.listdir(output_dir):
            if name.startswith("app_egui_resource"):
                candidate = os.path.join(output_dir, name)
                if os.path.isfile(candidate):
                    output_paths.append(candidate)
    return output_paths, output_text


def _find_make_artifact(sdk_root: str, port: str) -> str:
    output_dir = os.path.join(sdk_root, "output")
    candidates = []
    if port in {"pc", "designer"}:
        candidates.extend(
            [
                os.path.join(output_dir, "main.exe"),
                os.path.join(output_dir, "main"),
            ]
        )
    else:
        candidates.extend(
            [
                os.path.join(output_dir, "main.exe"),
                os.path.join(output_dir, "main"),
                os.path.join(output_dir, "main.elf"),
                os.path.join(output_dir, "main.bin"),
            ]
        )

    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate

    if os.path.isdir(output_dir):
        for name in sorted(os.listdir(output_dir)):
            candidate = os.path.join(output_dir, name)
            if os.path.isfile(candidate) and name.startswith("main"):
                return candidate
    raise FileNotFoundError(f"No build artifact found under {output_dir}")


def _copy_release_artifacts(
    built_artifact: str,
    dist_dir: str,
    app_name: str,
    copy_resource_dir: bool,
    project_dir: str,
) -> list[str]:
    os.makedirs(dist_dir, exist_ok=True)

    ext = os.path.splitext(built_artifact)[1]
    target_artifact = os.path.join(dist_dir, f"{app_name}{ext}")
    shutil.copy2(built_artifact, target_artifact)
    copied_paths = [target_artifact]

    if copy_resource_dir:
        source_resource_dir = os.path.join(project_dir, "resource")
        target_resource_dir = os.path.join(dist_dir, "resource")
        if os.path.isdir(source_resource_dir):
            shutil.copytree(source_resource_dir, target_resource_dir, dirs_exist_ok=True)
            copied_paths.extend(_iter_files(target_resource_dir))

    return copied_paths


def _format_version_text(app_name: str, profile, designer_revision: str, sdk_fingerprint, build_id: str) -> str:
    revision = designer_revision or "unknown"
    sdk_revision = sdk_fingerprint.revision or sdk_fingerprint.commit_short or sdk_fingerprint.commit or "unknown"
    sdk_commit = sdk_fingerprint.commit or sdk_fingerprint.commit_short or "unknown"
    sdk_source_kind = sdk_fingerprint.source_kind or "unknown"
    return (
        f"app={app_name}\n"
        f"profile={profile.id}\n"
        f"designer_revision={revision}\n"
        f"sdk_source_kind={sdk_source_kind}\n"
        f"sdk_revision={sdk_revision}\n"
        f"sdk_commit={sdk_commit}\n"
        f"build_id={build_id}\n"
    )


def _write_text(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _write_manifest_files(release_root: str, dist_dir: str, manifest: dict[str, object], include_package_artifacts: bool) -> str:
    manifest_path = os.path.join(release_root, "release-manifest.json")
    dist_manifest_path = os.path.join(dist_dir, "release-manifest.json")

    root_manifest = manifest
    dist_manifest = manifest
    if include_package_artifacts and manifest.get("artifacts"):
        dist_manifest = dict(manifest)
        dist_manifest["artifacts"] = [
            artifact
            for artifact in manifest["artifacts"]
            if not str(artifact.get("path", "")).endswith(".zip")
        ]

    payload = json.dumps(root_manifest, indent=2, ensure_ascii=False) + "\n"
    _write_text(manifest_path, payload)
    _write_text(dist_manifest_path, json.dumps(dist_manifest, indent=2, ensure_ascii=False) + "\n")
    return manifest_path

def release_project(request: ReleaseRequest) -> ReleaseResult:
    project = request.project
    project_dir = normalize_path(request.project_dir)
    sdk_root = normalize_path(request.sdk_root)
    designer_root = normalize_path(request.designer_root)
    output_base = normalize_path(request.output_dir) or os.path.join(project_dir, "output", "ui_designer_release")
    profile = request.profile

    build_id = build_release_id()
    release_root = os.path.join(output_base, profile.id, build_id)
    dist_dir = os.path.join(release_root, "dist")
    log_path = os.path.join(release_root, "logs", "build.log")
    history_path = release_history_path(project_dir, output_dir=output_base)
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    os.makedirs(dist_dir, exist_ok=True)

    warnings: list[str] = []
    errors: list[str] = []
    diagnostic_entries: list[dict[str, object]] = []
    log_chunks: list[str] = []
    artifacts: list[ReleaseArtifact] = []
    zip_path = ""
    alias_dir = ""
    ui_input_digest = ""
    generated_digest = ""
    command: list[str] = []
    workspace_metadata = collect_git_metadata(project_dir)
    workspace_dirty = bool(is_git_worktree_dirty(project_dir)) if workspace_metadata else False
    sdk_fingerprint = collect_sdk_fingerprint(sdk_root, designer_repo_root=designer_root)
    designer_metadata = current_designer_metadata(designer_root)
    designer_revision = current_designer_revision(designer_root)

    def _finalize(success: bool, message: str) -> ReleaseResult:
        diagnostic_error_count = sum(1 for entry in diagnostic_entries if str(entry.get("severity") or "") == "error")
        diagnostic_warning_count = sum(1 for entry in diagnostic_entries if str(entry.get("severity") or "") == "warning")
        diagnostics_summary = {
            "errors": diagnostic_error_count,
            "warnings": diagnostic_warning_count,
            "total": len(diagnostic_entries),
        }
        sdk_payload = sdk_fingerprint.to_dict()
        manifest = {
            "schema_version": 1,
            "build_id": build_id,
            "status": "success" if success else "failed",
            "app_name": getattr(project, "app_name", ""),
            "profile_id": profile.id,
            "designer_revision": designer_revision or describe_git_revision(designer_metadata),
            "sdk": sdk_payload,
            "workspace": {
                "git_commit": str(workspace_metadata.get("git_commit") or ""),
                "dirty": workspace_dirty,
                "ui_input_digest": ui_input_digest,
                "generated_digest": generated_digest,
            },
            "artifacts": [artifact.to_dict() for artifact in artifacts],
            "warnings": warnings,
            "errors": errors,
            "diagnostics": {
                "summary": diagnostics_summary,
                "entries": list(diagnostic_entries),
            },
            "command": command,
            "message": message,
        }

        version_text = _format_version_text(
            getattr(project, "app_name", ""),
            profile,
            manifest["designer_revision"],
            sdk_fingerprint,
            build_id,
        )
        _write_text(os.path.join(release_root, "VERSION.txt"), version_text)
        _write_text(os.path.join(dist_dir, "VERSION.txt"), version_text)
        manifest_path_local = _write_manifest_files(
            release_root,
            dist_dir,
            manifest,
            include_package_artifacts=bool(zip_path),
        )
        _write_text(log_path, "".join(log_chunks))

        history_entry = {
            "build_id": build_id,
            "status": manifest["status"],
            "success": success,
            "app_name": getattr(project, "app_name", ""),
            "profile_id": profile.id,
            "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "designer_revision": manifest["designer_revision"],
            "sdk": dict(sdk_payload),
            "warning_count": len(warnings),
            "error_count": len(errors),
            "diagnostics_total": len(diagnostic_entries),
            "first_diagnostic": _first_release_diagnostic_text(diagnostic_entries),
            "release_root": release_root,
            "dist_dir": dist_dir,
            "manifest_path": manifest_path_local,
            "log_path": log_path,
            "zip_path": zip_path,
            "message": message,
        }
        history_path_local = _write_release_history_entry(project_dir, output_base, history_entry)
        return ReleaseResult(
            success=success,
            message=message,
            build_id=build_id,
            profile_id=profile.id,
            release_root=release_root,
            dist_dir=dist_dir,
            manifest_path=manifest_path_local,
            log_path=log_path,
            history_path=history_path_local,
            designer_revision=manifest["designer_revision"],
            sdk=dict(sdk_payload),
            zip_path=zip_path,
            warnings=warnings,
            errors=errors,
            artifacts=artifacts,
            diagnostics_summary=diagnostics_summary,
            diagnostics_entries=list(diagnostic_entries),
        )

    try:
        if project is None:
            raise ValueError("project is required")
        if not project_dir:
            raise ValueError("project_dir is required")
        if not sdk_root or not is_valid_sdk_root(sdk_root):
            raise ValueError("A valid EmbeddedGUI SDK root is required for release builds")

        project.project_dir = project_dir
        project.sdk_root = sdk_root
        _ensure_project_scaffold(project_dir, project.app_name, project.screen_width, project.screen_height)
        project.save(project_dir)
        ui_input_digest = _hash_files(_collect_ui_input_paths(project_dir, project.app_name), base_root=project_dir)

        diagnostics = collect_release_diagnostics(project)
        diagnostic_entries = [diagnostic_entry_payload(entry) for entry in diagnostics["entries"]]
        warnings = summarize_diagnostic_entries(diagnostics["warnings"])
        errors = summarize_diagnostic_entries(diagnostics["errors"])
        if errors:
            raise RuntimeError(f"Release blocked by diagnostics ({len(errors)} error(s))")
        if request.warnings_as_errors and warnings:
            errors = list(warnings)
            raise RuntimeError(f"Release blocked by diagnostics ({len(warnings)} warning(s) treated as errors)")

        generated_files = generate_all_files_preserved(project, project_dir, backup=True)
        generated_paths = _write_generated_files(project_dir, generated_files)
        resource_paths, resource_log = _run_resource_generation(project, project_dir, sdk_root)
        log_chunks.append("=== Resource Generation ===\n")
        if resource_log:
            log_chunks.append(resource_log.rstrip() + "\n")
        generated_digest = _hash_files(generated_paths + resource_paths, base_root=project_dir)

        app_root_arg, alias_dir = _resolve_make_app_root_arg(sdk_root, project_dir, project.app_name)
        command = [
            "make",
            "-j",
            profile.make_target,
            f"APP={project.app_name}",
            f"PORT={profile.port}",
            f"EGUI_APP_ROOT_PATH={app_root_arg}",
        ]
        command.extend(profile.extra_make_args)
        log_chunks.append("=== Build Command ===\n")
        log_chunks.append(" ".join(shlex.quote(part) for part in command) + "\n")

        build_result = subprocess.run(
            command,
            cwd=sdk_root,
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
        build_output = build_result.stdout + build_result.stderr
        log_chunks.append("=== Build Output ===\n")
        log_chunks.append(build_output)
        if build_result.returncode != 0:
            raise RuntimeError(f"Build failed (rc={build_result.returncode})")

        built_artifact = _find_make_artifact(sdk_root, profile.port)
        copied_paths = _copy_release_artifacts(
            built_artifact,
            dist_dir,
            project.app_name,
            profile.copy_resource_dir,
            project_dir,
        )
        for path in copied_paths:
            rel_path = os.path.relpath(path, release_root).replace("\\", "/")
            artifacts.append(ReleaseArtifact(path=rel_path, sha256=_sha256_file(path)))

        if request.package_release and profile.package_format == "dir+zip":
            archive_base = os.path.join(release_root, f"{project.app_name}-{profile.id}-sdk{sdk_fingerprint.commit_short or 'unknown'}-{build_id}")
            zip_path = shutil.make_archive(archive_base, "zip", root_dir=dist_dir, base_dir=".")
            artifacts.append(
                ReleaseArtifact(
                    path=os.path.relpath(zip_path, release_root).replace("\\", "/"),
                    sha256=_sha256_file(zip_path),
                )
            )

        if sdk_fingerprint.source_kind == "submodule" and not sdk_fingerprint.remote:
            sdk_fingerprint.remote = DEFAULT_SDK_REMOTE_URL

        return _finalize(True, f"Release created: {release_root}")
    except Exception as exc:
        if not errors:
            errors = [str(exc)]
        return _finalize(False, str(exc))
    finally:
        _remove_dir_alias(alias_dir)
