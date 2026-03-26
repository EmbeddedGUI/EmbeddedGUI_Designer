#!/usr/bin/env python
"""CLI entry point for releasing a UI Designer project."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ui_designer.engine.release_engine import release_project
from ui_designer.model.project import Project
from ui_designer.model.release import ReleaseRequest
from ui_designer.model.sdk_bootstrap import default_sdk_install_dir
from ui_designer.model.workspace import find_sdk_root, normalize_path


EXIT_OK = 0
EXIT_DIAGNOSTICS_FAILED = 2
EXIT_BUILD_FAILED = 3
EXIT_PACKAGE_FAILED = 4
EXIT_CONFIG_ERROR = 5


def _parse_args():
    parser = argparse.ArgumentParser(description="Release a UI Designer project")
    parser.add_argument("--project", required=True, help="Path to a .egui file or a project directory")
    parser.add_argument("--profile", default="", help="Release profile id (default: project's default profile)")
    parser.add_argument("--sdk-root", default="", help="EmbeddedGUI SDK root directory")
    parser.add_argument("--output-dir", default="", help="Optional release output root")
    parser.add_argument("--warnings-as-errors", action="store_true", help="Treat diagnostics warnings as fatal")
    parser.add_argument("--no-package", action="store_true", help="Skip zip packaging")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON result")
    return parser.parse_args()


def _string(value) -> str:
    if isinstance(value, str):
        return value.strip()
    if value is None:
        return ""
    return str(value).strip()


def _diagnostics_payload(result):
    warnings = list(getattr(result, "warnings", []) or [])
    errors = list(getattr(result, "errors", []) or [])
    summary = dict(getattr(result, "diagnostics_summary", {}) or {})
    summary.setdefault("errors", len(errors))
    summary.setdefault("warnings", len(warnings))
    summary.setdefault("total", int(summary.get("errors", 0) or 0) + int(summary.get("warnings", 0) or 0))
    return {
        "summary": summary,
        "entries": list(getattr(result, "diagnostics_entries", []) or []),
    }


def _sdk_payload(result):
    sdk = getattr(result, "sdk", {})
    return dict(sdk) if isinstance(sdk, dict) else {}


def _sdk_revision_text(result) -> str:
    sdk = _sdk_payload(result)
    return _string(sdk.get("revision") or sdk.get("commit_short") or sdk.get("commit"))


def _first_diagnostic_text(result):
    diagnostics = _diagnostics_payload(result)
    entries = diagnostics["entries"]
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

    errors = list(getattr(result, "errors", []) or [])
    if errors:
        return f"error: {errors[0]}"

    warnings = list(getattr(result, "warnings", []) or [])
    if warnings:
        return f"warning: {warnings[0]}"

    return ""


def _result_payload(result):
    diagnostics = _diagnostics_payload(result)
    first_diagnostic = _first_diagnostic_text(result)
    sdk = _sdk_payload(result)
    return {
        "success": result.success,
        "message": result.message,
        "build_id": result.build_id,
        "profile_id": result.profile_id,
        "release_root": result.release_root,
        "dist_dir": result.dist_dir,
        "manifest_path": result.manifest_path,
        "log_path": result.log_path,
        "history_path": result.history_path,
        "zip_path": result.zip_path,
        "designer_revision": _string(getattr(result, "designer_revision", "")),
        "sdk_source_kind": _string(sdk.get("source_kind")),
        "sdk_source_root": _string(sdk.get("source_root")),
        "sdk_revision": _sdk_revision_text(result),
        "sdk_commit": _string(sdk.get("commit")),
        "sdk_remote": _string(sdk.get("remote")),
        "sdk_dirty": bool(sdk.get("dirty", False)),
        "sdk": sdk,
        "warnings": list(result.warnings),
        "errors": list(result.errors),
        "artifacts": [artifact.to_dict() for artifact in result.artifacts],
        "diagnostics_warning_count": int(diagnostics["summary"].get("warnings", 0) or 0),
        "diagnostics_error_count": int(diagnostics["summary"].get("errors", 0) or 0),
        "diagnostics_total": int(diagnostics["summary"].get("total", 0) or 0),
        "first_diagnostic": first_diagnostic,
        "diagnostics": diagnostics,
    }


def _resolve_exit_code(result):
    message = (result.message or "").lower()
    if result.success:
        return EXIT_OK
    if "diagnostic" in message:
        return EXIT_DIAGNOSTICS_FAILED
    if "build failed" in message:
        return EXIT_BUILD_FAILED
    if "zip" in message or "package" in message:
        return EXIT_PACKAGE_FAILED
    return EXIT_CONFIG_ERROR


def main():
    args = _parse_args()
    project_path = normalize_path(args.project)
    if not project_path:
        print("Project path is required", file=sys.stderr)
        return EXIT_CONFIG_ERROR

    project = Project.load(project_path)
    project_dir = project_path if os.path.isdir(project_path) else os.path.dirname(project_path)
    profile = project.release_config.get_profile(args.profile)

    sdk_root = find_sdk_root(
        cli_sdk_root=args.sdk_root or project.sdk_root,
        configured_sdk_root=project.sdk_root,
        project_path=project_dir,
        extra_candidates=[default_sdk_install_dir()],
    )

    request = ReleaseRequest(
        project=project,
        project_dir=project_dir,
        sdk_root=sdk_root,
        profile=profile,
        designer_root=str(REPO_ROOT),
        output_dir=args.output_dir,
        warnings_as_errors=args.warnings_as_errors,
        package_release=not args.no_package,
    )
    result = release_project(request)
    payload = _result_payload(result)

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        diagnostics = _diagnostics_payload(result)
        print(f"[{'OK' if result.success else 'FAIL'}] {result.message}")
        if result.build_id:
            print(f"[INFO] build_id: {result.build_id}")
        if result.profile_id:
            print(f"[INFO] profile: {result.profile_id}")
        print(f"[INFO] manifest: {result.manifest_path}")
        if result.history_path:
            print(f"[INFO] history: {result.history_path}")
        if result.zip_path:
            print(f"[INFO] package: {result.zip_path}")
        designer_revision = _string(getattr(result, "designer_revision", ""))
        if designer_revision:
            print(f"[INFO] designer_revision: {designer_revision}")
        sdk_payload = _sdk_payload(result)
        sdk_source_kind = _string(sdk_payload.get("source_kind"))
        if sdk_source_kind:
            print(f"[INFO] sdk_source: {sdk_source_kind}")
        sdk_revision = _sdk_revision_text(result)
        if sdk_revision:
            print(f"[INFO] sdk_revision: {sdk_revision}")
        sdk_remote = _string(sdk_payload.get("remote"))
        if sdk_remote:
            print(f"[INFO] sdk_remote: {sdk_remote}")
        print(
            "[INFO] diagnostics: "
            f"warnings={diagnostics['summary']['warnings']}, "
            f"errors={diagnostics['summary']['errors']}, "
            f"total={diagnostics['summary']['total']}"
        )
        first_diagnostic = _first_diagnostic_text(result)
        if first_diagnostic:
            print(f"[INFO] first_diagnostic: {first_diagnostic}")

    return _resolve_exit_code(result)


if __name__ == "__main__":
    sys.exit(main())
