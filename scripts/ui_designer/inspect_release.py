#!/usr/bin/env python
"""Inspect UI Designer release manifests and packaged build metadata."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ui_designer.model.build_metadata import (  # noqa: E402
    DESIGNER_BUILD_METADATA_NAME,
    describe_git_revision,
    load_designer_build_metadata,
)
from ui_designer.model.sdk_bootstrap import (  # noqa: E402
    BUNDLED_SDK_METADATA_NAME,
    bundled_sdk_revision,
)


EXIT_OK = 0
EXIT_INPUT_ERROR = 2


def _parse_args():
    parser = argparse.ArgumentParser(description="Inspect UI Designer release or package metadata")
    parser.add_argument(
        "path",
        help="Path to a release root, release-manifest.json, VERSION.txt, packaged app dir, or bundled SDK dir",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    return parser.parse_args()


def _string(value) -> str:
    if isinstance(value, str):
        return value.strip()
    if value is None:
        return ""
    return str(value)


def _load_json_dict(path: Path) -> dict[str, object]:
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    return content if isinstance(content, dict) else {}


def _load_version_text(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}

    payload: dict[str, str] = {}
    for line in lines:
        key, sep, value = line.partition("=")
        if not sep:
            continue
        normalized_key = _string(key)
        if not normalized_key:
            continue
        payload[normalized_key] = _string(value)
    return payload


def _first_diagnostic_text(manifest: dict[str, object]) -> str:
    diagnostics = manifest.get("diagnostics") if isinstance(manifest.get("diagnostics"), dict) else {}
    entries = diagnostics.get("entries") if isinstance(diagnostics.get("entries"), list) else []
    if entries:
        first_entry = entries[0] if isinstance(entries[0], dict) else {}
        severity = _string(first_entry.get("severity")) or "issue"
        page_name = _string(first_entry.get("target_page_name") or first_entry.get("page_name"))
        widget_name = _string(first_entry.get("target_widget_name") or first_entry.get("widget_name"))
        scope = page_name or "<project>"
        if widget_name:
            scope = f"{scope}/{widget_name}"
        message = _string(first_entry.get("message"))
        return f"{severity} {scope}: {message}" if message else f"{severity} {scope}"
    error_entries = manifest.get("errors") if isinstance(manifest.get("errors"), list) else []
    if error_entries:
        return f"error: {_string(error_entries[0])}"
    warning_entries = manifest.get("warnings") if isinstance(manifest.get("warnings"), list) else []
    if warning_entries:
        return f"warning: {_string(warning_entries[0])}"
    return ""


def _find_release_manifest_in_children(root_dir: Path) -> Path | None:
    candidates = []
    for child in root_dir.iterdir():
        if not child.is_dir():
            continue
        manifest_path = child / "release-manifest.json"
        if manifest_path.is_file():
            candidates.append(manifest_path)
    if not candidates:
        return None
    return sorted(candidates, key=lambda path: path.parent.name)[-1]


def summarize_manifest(manifest_path: str | Path) -> dict[str, object]:
    resolved_path = Path(manifest_path).resolve()
    manifest = _load_json_dict(resolved_path)
    if not manifest:
        raise ValueError(f"invalid release manifest: {resolved_path}")

    sdk = manifest.get("sdk") if isinstance(manifest.get("sdk"), dict) else {}
    workspace = manifest.get("workspace") if isinstance(manifest.get("workspace"), dict) else {}
    artifacts = manifest.get("artifacts") if isinstance(manifest.get("artifacts"), list) else []
    diagnostics = manifest.get("diagnostics") if isinstance(manifest.get("diagnostics"), dict) else {}
    diagnostics_summary = diagnostics.get("summary") if isinstance(diagnostics.get("summary"), dict) else {}
    warning_entries = manifest.get("warnings") if isinstance(manifest.get("warnings"), list) else []
    error_entries = manifest.get("errors") if isinstance(manifest.get("errors"), list) else []
    diagnostics_warning_count = int(diagnostics_summary.get("warnings", len(warning_entries)) or 0)
    diagnostics_error_count = int(diagnostics_summary.get("errors", len(error_entries)) or 0)
    diagnostics_total = int(diagnostics_summary.get("total", diagnostics_warning_count + diagnostics_error_count) or 0)
    first_diagnostic = _first_diagnostic_text(manifest)

    return {
        "kind": "release_manifest",
        "source_path": str(resolved_path),
        "build_id": _string(manifest.get("build_id")),
        "status": _string(manifest.get("status")),
        "app_name": _string(manifest.get("app_name")),
        "profile_id": _string(manifest.get("profile_id")),
        "designer_revision": _string(manifest.get("designer_revision")),
        "sdk_source_kind": _string(sdk.get("source_kind")),
        "sdk_source_root": _string(sdk.get("source_root")),
        "sdk_revision": _string(sdk.get("revision") or sdk.get("commit_short") or sdk.get("commit")),
        "sdk_commit": _string(sdk.get("commit")),
        "sdk_remote": _string(sdk.get("remote")),
        "sdk_dirty": bool(sdk.get("dirty", False)),
        "workspace_commit": _string(workspace.get("git_commit")),
        "workspace_dirty": bool(workspace.get("dirty", False)),
        "artifact_count": len(artifacts),
        "diagnostics_warning_count": diagnostics_warning_count,
        "diagnostics_error_count": diagnostics_error_count,
        "diagnostics_total": diagnostics_total,
        "first_diagnostic": first_diagnostic,
    }


def summarize_version_file(version_path: str | Path) -> dict[str, object]:
    resolved_path = Path(version_path).resolve()
    version_data = _load_version_text(resolved_path)
    if not version_data:
        raise ValueError(f"invalid version file: {resolved_path}")

    return {
        "kind": "release_version",
        "source_path": str(resolved_path),
        "build_id": _string(version_data.get("build_id")),
        "app_name": _string(version_data.get("app")),
        "profile_id": _string(version_data.get("profile")),
        "designer_revision": _string(version_data.get("designer_revision")),
        "sdk_source_kind": _string(version_data.get("sdk_source_kind")),
        "sdk_revision": _string(version_data.get("sdk_revision")),
        "sdk_commit": _string(version_data.get("sdk_commit")),
        "sdk_remote": _string(version_data.get("sdk_remote")),
    }


def summarize_sdk_bundle(sdk_root: str | Path) -> dict[str, object]:
    resolved_sdk_root = Path(sdk_root).resolve()
    metadata_path = resolved_sdk_root / BUNDLED_SDK_METADATA_NAME
    metadata = _load_json_dict(metadata_path)
    if not metadata:
        raise ValueError(f"bundled SDK metadata not found: {metadata_path}")

    return {
        "kind": "bundled_sdk",
        "source_path": str(resolved_sdk_root),
        "sdk_source_kind": "bundled",
        "sdk_revision": bundled_sdk_revision(metadata),
        "sdk_commit": _string(metadata.get("git_commit")),
        "sdk_remote": _string(metadata.get("git_remote_url")),
        "sdk_dirty": bool(metadata.get("git_dirty", False)),
        "sdk_source_root": _string(metadata.get("source_root")),
        "file_count": int(metadata.get("file_count", 0) or 0),
        "total_size_bytes": int(metadata.get("total_size_bytes", 0) or 0),
    }


def summarize_packaged_app(app_dir: str | Path) -> dict[str, object]:
    resolved_app_dir = Path(app_dir).resolve()
    designer_metadata = load_designer_build_metadata(str(resolved_app_dir))
    if not designer_metadata:
        raise ValueError(f"designer build metadata not found: {resolved_app_dir / DESIGNER_BUILD_METADATA_NAME}")

    payload = {
        "kind": "packaged_app",
        "source_path": str(resolved_app_dir),
        "designer_revision": describe_git_revision(designer_metadata),
        "designer_commit": _string(designer_metadata.get("git_commit")),
        "designer_dirty": bool(designer_metadata.get("git_dirty", False)),
    }

    bundled_sdk_root = resolved_app_dir / "sdk" / "EmbeddedGUI"
    if (bundled_sdk_root / BUNDLED_SDK_METADATA_NAME).is_file():
        payload.update(summarize_sdk_bundle(bundled_sdk_root))
        payload["kind"] = "packaged_app"
        payload["source_path"] = str(resolved_app_dir)
    else:
        payload.update(
            {
                "sdk_source_kind": "",
                "sdk_revision": "",
                "sdk_commit": "",
                "sdk_remote": "",
                "sdk_dirty": False,
                "sdk_source_root": "",
                "file_count": 0,
                "total_size_bytes": 0,
            }
        )
    return payload


def inspect_path(path: str | Path) -> dict[str, object]:
    resolved_path = Path(path).resolve()
    if resolved_path.is_dir():
        manifest_path = resolved_path / "release-manifest.json"
        if manifest_path.is_file():
            return summarize_manifest(manifest_path)
        nested_manifest_path = _find_release_manifest_in_children(resolved_path)
        if nested_manifest_path is not None:
            return summarize_manifest(nested_manifest_path)
        if (resolved_path / DESIGNER_BUILD_METADATA_NAME).is_file():
            return summarize_packaged_app(resolved_path)
        if (resolved_path / BUNDLED_SDK_METADATA_NAME).is_file():
            return summarize_sdk_bundle(resolved_path)
    elif resolved_path.is_file():
        if resolved_path.name == "release-manifest.json":
            return summarize_manifest(resolved_path)
        if resolved_path.name.lower() == "version.txt":
            return summarize_version_file(resolved_path)
        if resolved_path.name == DESIGNER_BUILD_METADATA_NAME:
            return summarize_packaged_app(resolved_path.parent)
        if resolved_path.name == BUNDLED_SDK_METADATA_NAME:
            return summarize_sdk_bundle(resolved_path.parent)

    raise ValueError(
        "path must point to a release root, release-manifest.json, VERSION.txt, packaged app directory, or bundled SDK directory"
    )


def _print_field(label: str, value) -> None:
    if value in ("", None):
        return
    if isinstance(value, bool):
        value = "true" if value else "false"
    print(f"{label}: {value}")


def _print_human(payload: dict[str, object]) -> None:
    print(f"[{payload.get('kind', 'unknown')}] {payload.get('source_path', '')}")
    ordered_fields = [
        ("build_id", "build_id"),
        ("status", "status"),
        ("app_name", "app"),
        ("profile_id", "profile"),
        ("designer_revision", "designer_revision"),
        ("designer_commit", "designer_commit"),
        ("designer_dirty", "designer_dirty"),
        ("sdk_source_kind", "sdk_source"),
        ("sdk_revision", "sdk_revision"),
        ("sdk_commit", "sdk_commit"),
        ("sdk_remote", "sdk_remote"),
        ("sdk_dirty", "sdk_dirty"),
        ("sdk_source_root", "sdk_source_root"),
        ("workspace_commit", "workspace_commit"),
        ("workspace_dirty", "workspace_dirty"),
        ("artifact_count", "artifact_count"),
        ("diagnostics_warning_count", "diagnostics_warning_count"),
        ("diagnostics_error_count", "diagnostics_error_count"),
        ("diagnostics_total", "diagnostics_total"),
        ("first_diagnostic", "first_diagnostic"),
        ("file_count", "file_count"),
        ("total_size_bytes", "total_size_bytes"),
    ]
    for key, label in ordered_fields:
        _print_field(label, payload.get(key))


def main() -> int:
    args = _parse_args()
    try:
        payload = inspect_path(args.path)
    except Exception as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return EXIT_INPUT_ERROR

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        _print_human(payload)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
