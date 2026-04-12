"""Shared helpers for repo-local temporary workspaces."""

from __future__ import annotations

import tempfile
from pathlib import Path


def repo_temp_dir(repo_root: str | Path, name: str = "") -> Path:
    """Return a repo-scoped temp directory, optionally under a named subdir."""
    root = Path(repo_root).expanduser().resolve() / "temp"
    normalized_name = str(name or "").strip().replace("\\", "/").strip("/")
    if not normalized_name:
        return root
    return root / Path(normalized_name)


def create_temp_workspace(parent_root: str | Path, prefix: str) -> Path:
    """Create a temporary directory under a caller-provided parent root."""
    parent = Path(parent_root).expanduser().resolve()
    parent.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=prefix, dir=str(parent)))


def create_repo_temp_workspace(
    repo_root: str | Path,
    prefix: str,
    name: str = "",
) -> Path:
    """Create a temporary directory under the repo-scoped temp root."""
    return create_temp_workspace(repo_temp_dir(repo_root, name), prefix)
