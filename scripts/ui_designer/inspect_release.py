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
        help="Path to a release root, release-manifest.json, packaged app dir, or bundled SDK dir",
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


def summarize_manifest(manifest_path: str | Path) -> dict[str, object]:
    resolved_path = Path(manifest_path).resolve()
    manifest = _load_json_dict(resolved_path)
    if not manifest:
        raise ValueError(f"invalid release manifest: {resolved_path}")

    sdk = manifest.get("sdk") if isinstance(manifest.get("sdk"), dict) else {}
    workspace = manifest.get("workspace") if isinstance(manifest.get("workspace"), dict) else {}
    artifacts = manifest.get("artifacts") if isinstance(manifest.get("artifacts"), list) else []

    return {
        "kind": "release_manifest",
        "source_path": str(resolved_path),
        "build_id": _string(manifest.get("build_id")),
        "status": _string(manifest.get("status")),
        "app_name": _string(manifest.get("app_name")),
        "profile_id": _string(manifest.get("profile_id")),
        "designer_revision": _string(manifest.get("designer_revision")),
        "sdk_source_kind": _string(sdk.get("source_kind")),
        "sdk_revision": _string(sdk.get("revision") or sdk.get("commit_short") or sdk.get("commit")),
        "sdk_commit": _string(sdk.get("commit")),
        "sdk_remote": _string(sdk.get("remote")),
        "sdk_dirty": bool(sdk.get("dirty", False)),
        "workspace_commit": _string(workspace.get("git_commit")),
        "workspace_dirty": bool(workspace.get("dirty", False)),
        "artifact_count": len(artifacts),
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
        if (resolved_path / DESIGNER_BUILD_METADATA_NAME).is_file():
            return summarize_packaged_app(resolved_path)
        if (resolved_path / BUNDLED_SDK_METADATA_NAME).is_file():
            return summarize_sdk_bundle(resolved_path)
    elif resolved_path.is_file():
        if resolved_path.name == "release-manifest.json":
            return summarize_manifest(resolved_path)
        if resolved_path.name == DESIGNER_BUILD_METADATA_NAME:
            return summarize_packaged_app(resolved_path.parent)
        if resolved_path.name == BUNDLED_SDK_METADATA_NAME:
            return summarize_sdk_bundle(resolved_path.parent)

    raise ValueError(
        "path must point to a release root, release-manifest.json, packaged app directory, or bundled SDK directory"
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
