"""SDK path helpers for packaged UI Designer flows."""

from __future__ import annotations

import os
from pathlib import Path
import sys

from .config import _get_config_dir
from .workspace import normalize_path, resolve_sdk_root_candidate


BUNDLED_SDK_METADATA_NAME = ".designer_sdk_bundle.json"


def runtime_sdk_container_dir() -> str:
    """Return the packaged-runtime sdk container directory when frozen."""
    if not getattr(sys, "frozen", False):
        return ""
    runtime_dir = normalize_path(os.path.dirname(sys.executable))
    if not runtime_dir:
        return ""
    return normalize_path(os.path.join(runtime_dir, "sdk"))


def default_sdk_install_dir() -> str:
    """Return the preferred SDK root path for the current runtime."""
    runtime_sdk_dir = runtime_sdk_container_dir()
    if runtime_sdk_dir:
        bundled_root = resolve_sdk_root_candidate(runtime_sdk_dir)
        if bundled_root:
            return bundled_root

        runtime_dir = normalize_path(os.path.dirname(runtime_sdk_dir))
        if os.path.isdir(runtime_sdk_dir) or os.access(runtime_dir, os.W_OK):
            return normalize_path(os.path.join(runtime_sdk_dir, "EmbeddedGUI"))

    return default_cached_sdk_install_dir()


def default_cached_sdk_install_dir() -> str:
    """Return the per-user SDK cache directory used outside bundled runtimes."""
    return normalize_path(os.path.join(_get_config_dir(), "sdk", "EmbeddedGUI"))


def is_runtime_local_sdk_root(path: str | None) -> bool:
    """Return True when *path* lives beside the packaged Designer runtime."""
    sdk_root = resolve_sdk_root_candidate(path)
    runtime_sdk_dir = runtime_sdk_container_dir()
    if not sdk_root or not runtime_sdk_dir:
        return False
    try:
        return os.path.commonpath([sdk_root, runtime_sdk_dir]) == runtime_sdk_dir
    except ValueError:
        return False


def bundled_sdk_metadata_path(path: str | None) -> str:
    """Return the bundle metadata file path for a packaged SDK root."""
    sdk_root = resolve_sdk_root_candidate(path)
    if not sdk_root or not is_runtime_local_sdk_root(sdk_root):
        return ""
    return normalize_path(os.path.join(sdk_root, BUNDLED_SDK_METADATA_NAME))


def is_bundled_sdk_root(path: str | None) -> bool:
    """Return True when *path* is a packaged SDK bundle with bundle metadata."""
    metadata_path = bundled_sdk_metadata_path(path)
    return bool(metadata_path and os.path.isfile(metadata_path))


def load_bundled_sdk_metadata(path: str | None) -> dict[str, object]:
    """Load packaged SDK metadata when available."""
    metadata_path = bundled_sdk_metadata_path(path)
    if not metadata_path or not os.path.isfile(metadata_path):
        return {}

    try:
        with open(metadata_path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return {}

    try:
        import json

        data = json.loads(content)
    except (TypeError, ValueError):
        return {}

    if not isinstance(data, dict):
        return {}
    return data


def bundled_sdk_revision(metadata: dict[str, object]) -> str:
    """Return the most useful bundled SDK revision label."""
    for key in ("git_describe", "git_commit_short", "git_commit"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def is_cached_sdk_root(path: str | None) -> bool:
    """Return True when *path* points at the default per-user SDK cache."""
    sdk_root = resolve_sdk_root_candidate(path)
    cached_root = default_cached_sdk_install_dir()
    if not sdk_root or not cached_root:
        return False
    return sdk_root == cached_root


def sdk_root_source_kind(path: str | None) -> str:
    """Classify the active SDK root for UI status text."""
    sdk_root = resolve_sdk_root_candidate(path) or normalize_path(path)
    if not sdk_root:
        return "missing"
    if is_bundled_sdk_root(sdk_root):
        return "bundled"
    if is_runtime_local_sdk_root(sdk_root):
        return "runtime_local"
    if is_cached_sdk_root(sdk_root):
        return "cached"
    return "custom"


def describe_sdk_source(path: str | None) -> str:
    """Return a short label describing where the active SDK came from."""
    source_kind = sdk_root_source_kind(path)
    if source_kind == "bundled":
        return "bundled SDK copy"
    if source_kind == "runtime_local":
        return "SDK stored beside the application"
    if source_kind == "cached":
        return "default SDK cache"
    if source_kind == "custom":
        return "selected SDK root"
    return "missing SDK root"


def describe_sdk_source_hint(path: str | None) -> str:
    """Return a longer explanation for the detected SDK source."""
    source_kind = sdk_root_source_kind(path)
    if source_kind == "bundled":
        metadata = load_bundled_sdk_metadata(path)
        source_root = normalize_path(metadata.get("source_root")) if isinstance(metadata.get("source_root"), str) else ""
        revision = bundled_sdk_revision(metadata)
        lines = []
        if source_root:
            lines.append(f"Packaged with Designer from: {source_root}")
        else:
            lines.append("Packaged with Designer.")
        if revision:
            lines.append(f"Bundled SDK revision: {revision}")
        lines.append("You can switch to another SDK root at any time.")
        return "\n".join(lines)
    if source_kind == "runtime_local":
        return "Stored beside the application directory for the packaged Designer runtime."
    if source_kind == "cached":
        return f"Stored in the default SDK cache: {default_cached_sdk_install_dir()}"
    if source_kind == "custom":
        return "Using the SDK root selected for the current workspace."
    return "No SDK root is available yet."
