"""Build metadata helpers shared by packaging, runtime, and release flows."""

from __future__ import annotations

import json
import os
import shutil
from subprocess import run as _subprocess_run
import sys
import time
from pathlib import Path

from .release import SdkFingerprint
from .sdk_bootstrap import (
    BUNDLED_SDK_METADATA_NAME,
    is_bundled_sdk_root,
    load_bundled_sdk_metadata,
)
from .workspace import default_designer_sdk_root, normalize_path, resolve_sdk_root_candidate


DESIGNER_BUILD_METADATA_NAME = ".designer_build_info.json"
DEFAULT_SDK_REMOTE_URL = "https://github.com/EmbeddedGUI/EmbeddedGUI.git"


def _run_git_text(repo_root: str | Path, *args: str) -> str:
    resolved_repo_root = Path(repo_root).resolve()
    git_exe = shutil.which("git")
    if not git_exe or not resolved_repo_root.is_dir():
        return ""

    result = _subprocess_run(
        [git_exe, "-c", f"safe.directory={resolved_repo_root}", "-C", str(resolved_repo_root), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def collect_git_metadata(source_root: str | Path) -> dict[str, object]:
    resolved_source_root = Path(source_root).resolve()
    commit = _run_git_text(resolved_source_root, "rev-parse", "HEAD")
    if not commit:
        return {}

    metadata: dict[str, object] = {
        "git_commit": commit,
    }
    commit_short = _run_git_text(resolved_source_root, "rev-parse", "--short", "HEAD")
    if commit_short:
        metadata["git_commit_short"] = commit_short

    describe = _run_git_text(resolved_source_root, "describe", "--tags", "--always", "--dirty")
    if describe:
        metadata["git_describe"] = describe

    branch = _run_git_text(resolved_source_root, "rev-parse", "--abbrev-ref", "HEAD")
    if branch:
        metadata["git_branch"] = branch

    remote_url = _run_git_text(resolved_source_root, "config", "--get", "remote.origin.url")
    if remote_url:
        metadata["git_remote_url"] = remote_url

    return metadata


def is_git_worktree_dirty(source_root: str | Path) -> bool:
    status = _run_git_text(source_root, "status", "--porcelain")
    return bool(status.strip())


def describe_git_revision(metadata: dict[str, object]) -> str:
    for key in ("git_describe", "git_commit_short", "git_commit"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def designer_build_metadata_path(root_dir: str | Path) -> str:
    resolved_root = normalize_path(root_dir)
    if not resolved_root:
        return ""
    return normalize_path(os.path.join(resolved_root, DESIGNER_BUILD_METADATA_NAME))


def load_designer_build_metadata(root_dir: str | Path) -> dict[str, object]:
    metadata_path = designer_build_metadata_path(root_dir)
    if not metadata_path or not os.path.isfile(metadata_path):
        return {}

    try:
        with open(metadata_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError, TypeError):
        return {}

    return data if isinstance(data, dict) else {}


def runtime_designer_metadata_path() -> str:
    if not getattr(sys, "frozen", False):
        return ""
    runtime_dir = normalize_path(os.path.dirname(sys.executable))
    if not runtime_dir:
        return ""
    return designer_build_metadata_path(runtime_dir)


def load_runtime_designer_metadata() -> dict[str, object]:
    metadata_path = runtime_designer_metadata_path()
    if not metadata_path:
        return {}
    return load_designer_build_metadata(os.path.dirname(metadata_path))


def write_designer_build_metadata(target_dir: str | Path, source_root: str | Path) -> str:
    resolved_target_dir = Path(target_dir).resolve()
    resolved_target_dir.mkdir(parents=True, exist_ok=True)
    resolved_source_root = Path(source_root).resolve()
    metadata = {
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source_root": str(resolved_source_root),
    }
    metadata.update(collect_git_metadata(resolved_source_root))
    metadata["git_dirty"] = bool(is_git_worktree_dirty(resolved_source_root))

    metadata_path = resolved_target_dir / DESIGNER_BUILD_METADATA_NAME
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(metadata_path)


def current_designer_metadata(repo_root: str | None = None) -> dict[str, object]:
    runtime_metadata = load_runtime_designer_metadata()
    if runtime_metadata:
        return runtime_metadata

    resolved_repo_root = normalize_path(repo_root)
    if not resolved_repo_root:
        return {}

    metadata = {
        "source_root": resolved_repo_root,
    }
    metadata.update(collect_git_metadata(resolved_repo_root))
    metadata["git_dirty"] = bool(is_git_worktree_dirty(resolved_repo_root))
    return metadata


def current_designer_revision(repo_root: str | None = None) -> str:
    return describe_git_revision(current_designer_metadata(repo_root))


def collect_sdk_fingerprint(sdk_root: str | None, designer_repo_root: str | None = None) -> SdkFingerprint:
    resolved_sdk_root = resolve_sdk_root_candidate(sdk_root) or normalize_path(sdk_root)
    if not resolved_sdk_root:
        return SdkFingerprint(source_kind="missing")

    if is_bundled_sdk_root(resolved_sdk_root):
        metadata = load_bundled_sdk_metadata(resolved_sdk_root)
        return SdkFingerprint(
            source_kind="bundled",
            source_root=normalize_path(metadata.get("source_root")) or resolved_sdk_root,
            remote=str(metadata.get("git_remote_url") or ""),
            commit=str(metadata.get("git_commit") or ""),
            commit_short=str(metadata.get("git_commit_short") or ""),
            revision=describe_git_revision(metadata),
            dirty=bool(metadata.get("git_dirty", False)),
            metadata_path=normalize_path(os.path.join(resolved_sdk_root, BUNDLED_SDK_METADATA_NAME)),
        )

    metadata = collect_git_metadata(resolved_sdk_root)
    dirty = bool(is_git_worktree_dirty(resolved_sdk_root)) if metadata else False
    source_kind = "filesystem"
    submodule_root = default_designer_sdk_root(designer_repo_root)
    if submodule_root and normalize_path(submodule_root) == resolved_sdk_root:
        source_kind = "submodule"
    elif metadata:
        source_kind = "external"

    remote = str(metadata.get("git_remote_url") or "")
    if source_kind == "submodule" and not remote:
        remote = DEFAULT_SDK_REMOTE_URL

    return SdkFingerprint(
        source_kind=source_kind,
        source_root=resolved_sdk_root,
        remote=remote,
        commit=str(metadata.get("git_commit") or ""),
        commit_short=str(metadata.get("git_commit_short") or ""),
        revision=describe_git_revision(metadata),
        dirty=dirty,
    )


def format_sdk_binding_label(sdk_root: str | None, designer_repo_root: str | None = None) -> str:
    fingerprint = collect_sdk_fingerprint(sdk_root, designer_repo_root=designer_repo_root)
    if fingerprint.source_kind == "missing":
        return "SDK: missing"

    label = f"SDK: {fingerprint.source_kind}"
    revision = fingerprint.revision or fingerprint.commit_short
    if revision:
        label += f" @ {revision}"
    if fingerprint.dirty:
        label += " (dirty)"
    return label



