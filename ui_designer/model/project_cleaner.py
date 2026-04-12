"""Project cleanup helpers for destructive designer-state reconstruction."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field

from ..utils.resource_config_overlay import DESIGNER_RESOURCE_DIRNAME
from ..utils.scaffold import (
    APP_CONFIG_RELPATH,
    BUILD_MK_RELPATH,
    DESIGNER_PROJECT_DIRNAME,
    EGUIPROJECT_DIRNAME,
    LAYOUT_DIR_RELPATH,
    MOCKUP_DIR_RELPATH,
    RELEASE_CONFIG_RELPATH,
    RESOURCE_CONFIG_RELPATH,
    RESOURCE_DIR_RELPATH,
    RESOURCE_FONT_DIR_RELPATH,
    RESOURCE_IMG_DIR_RELPATH,
    RESOURCE_SRC_DIR_RELPATH,
)
from .workspace import normalize_path


DESIGNER_SOURCE_PRESERVE_SUMMARY = (
    "*.egui project metadata",
    f"{BUILD_MK_RELPATH} and {APP_CONFIG_RELPATH} user override wrappers",
    f"{RESOURCE_CONFIG_RELPATH} user overlay config",
    f"{LAYOUT_DIR_RELPATH}/*.xml page layouts",
    f"{RESOURCE_DIR_RELPATH}/** source assets and resource metadata",
    f"{MOCKUP_DIR_RELPATH}/** preview mockups",
    f"{RELEASE_CONFIG_RELPATH} release packaging profiles",
    "widgets/** app-local widget sources",
    "custom_widgets/** app-local widget descriptors",
)

DESIGNER_RECONSTRUCT_DELETE_SUMMARY = (
    "user-owned page files in the project root (*.c, *_ext.h)",
    f"{RESOURCE_IMG_DIR_RELPATH}, {RESOURCE_FONT_DIR_RELPATH}, and other synced/generated resource outputs",
    f"{RESOURCE_SRC_DIR_RELPATH}/{DESIGNER_RESOURCE_DIRNAME}/** designer-generated resource metadata",
    f"{DESIGNER_PROJECT_DIRNAME}/** generated code and scaffold files (legacy root designer files also removed)",
    ".eguiproject/backup, orphaned_user_code, and other generated caches",
)

_PRESERVED_TOP_LEVEL_DIRS = {"widgets", "custom_widgets"}
_PRESERVED_EGUIPROJECT_DIRS = {
    os.path.basename(LAYOUT_DIR_RELPATH),
    os.path.basename(RESOURCE_DIR_RELPATH),
    os.path.basename(MOCKUP_DIR_RELPATH),
}
_PRESERVED_EGUIPROJECT_FILES = {os.path.basename(RELEASE_CONFIG_RELPATH)}
_PRESERVED_TOP_LEVEL_FILES = {
    os.path.basename(BUILD_MK_RELPATH),
    os.path.basename(APP_CONFIG_RELPATH),
}
_PRESERVED_RESOURCE_SRC_FILES = {os.path.basename(RESOURCE_CONFIG_RELPATH)}
_RESOURCE_DIRNAME = os.path.basename(os.path.dirname(RESOURCE_SRC_DIR_RELPATH))
_RESOURCE_SRC_DIRNAME = os.path.basename(RESOURCE_SRC_DIR_RELPATH)


@dataclass(frozen=True)
class ProjectCleanReport:
    """Summary of a clean-all operation."""

    removed_files: int = 0
    removed_dirs: int = 0
    removed_paths: tuple[str, ...] = field(default_factory=tuple)
    preserved_paths: tuple[str, ...] = field(default_factory=tuple)


def _is_within_project(project_dir: str, path: str) -> bool:
    project_real = os.path.realpath(project_dir)
    path_real = os.path.realpath(path)
    return path_real == project_real or path_real.startswith(project_real + os.sep)


def _is_project_entry_path(project_dir: str, path: str) -> bool:
    """Return True when the path entry itself lives under the project root."""
    project_abs = os.path.abspath(project_dir)
    path_abs = os.path.abspath(path)
    return path_abs == project_abs or path_abs.startswith(project_abs + os.sep)


def _remove_path(project_dir: str, path: str, removed_paths: list[str]) -> tuple[int, int]:
    if not _is_project_entry_path(project_dir, path):
        raise ValueError(f"Refusing to remove path outside project: {path}")

    rel_path = os.path.relpath(path, project_dir).replace("\\", "/")

    if os.path.islink(path):
        os.unlink(path)
        removed_paths.append(rel_path)
        return 1, 0

    if not _is_within_project(project_dir, path):
        raise ValueError(f"Refusing to remove path outside project: {path}")

    if os.path.isdir(path):
        shutil.rmtree(path)
        removed_paths.append(rel_path)
        return 0, 1

    if os.path.exists(path):
        os.remove(path)
        removed_paths.append(rel_path)
        return 1, 0

    return 0, 0


def _clean_eguiproject_dir(project_dir: str, eguiproject_dir: str, removed_paths: list[str], preserved_paths: list[str]) -> tuple[int, int]:
    removed_files = 0
    removed_dirs = 0
    for name in os.listdir(eguiproject_dir):
        child_path = os.path.join(eguiproject_dir, name)
        rel_path = os.path.relpath(child_path, project_dir).replace("\\", "/")
        if os.path.isdir(child_path) and name in _PRESERVED_EGUIPROJECT_DIRS:
            preserved_paths.append(rel_path)
            continue
        if os.path.isfile(child_path) and name in _PRESERVED_EGUIPROJECT_FILES:
            preserved_paths.append(rel_path)
            continue
        files, dirs = _remove_path(project_dir, child_path, removed_paths)
        removed_files += files
        removed_dirs += dirs
    return removed_files, removed_dirs


def _clean_resource_src_dir(project_dir: str, src_dir: str, removed_paths: list[str], preserved_paths: list[str]) -> tuple[int, int]:
    removed_files = 0
    removed_dirs = 0
    for name in os.listdir(src_dir):
        child_path = os.path.join(src_dir, name)
        rel_path = os.path.relpath(child_path, project_dir).replace("\\", "/")
        if os.path.isfile(child_path) and name in _PRESERVED_RESOURCE_SRC_FILES:
            preserved_paths.append(rel_path)
            continue
        files, dirs = _remove_path(project_dir, child_path, removed_paths)
        removed_files += files
        removed_dirs += dirs
    return removed_files, removed_dirs


def _clean_resource_dir(project_dir: str, resource_dir: str, removed_paths: list[str], preserved_paths: list[str]) -> tuple[int, int]:
    removed_files = 0
    removed_dirs = 0
    for name in os.listdir(resource_dir):
        child_path = os.path.join(resource_dir, name)
        rel_path = os.path.relpath(child_path, project_dir).replace("\\", "/")
        if os.path.isdir(child_path) and name == _RESOURCE_SRC_DIRNAME:
            preserved_paths.append(rel_path)
            files, dirs = _clean_resource_src_dir(project_dir, child_path, removed_paths, preserved_paths)
            removed_files += files
            removed_dirs += dirs
            continue
        files, dirs = _remove_path(project_dir, child_path, removed_paths)
        removed_files += files
        removed_dirs += dirs
    return removed_files, removed_dirs


def clean_project_for_reconstruct(project_dir: str) -> ProjectCleanReport:
    """Delete reconstructible project outputs while keeping designer-owned source state."""

    project_dir = normalize_path(project_dir)
    if not project_dir:
        raise ValueError("project_dir is required")
    if not os.path.isdir(project_dir):
        raise FileNotFoundError(project_dir)

    removed_paths: list[str] = []
    preserved_paths: list[str] = []
    removed_files = 0
    removed_dirs = 0

    for name in os.listdir(project_dir):
        child_path = os.path.join(project_dir, name)
        rel_path = os.path.relpath(child_path, project_dir).replace("\\", "/")

        if os.path.isfile(child_path) and name.lower().endswith(".egui"):
            preserved_paths.append(rel_path)
            continue

        if os.path.isfile(child_path) and name in _PRESERVED_TOP_LEVEL_FILES:
            preserved_paths.append(rel_path)
            continue

        if os.path.isdir(child_path) and name == EGUIPROJECT_DIRNAME:
            preserved_paths.append(rel_path)
            files, dirs = _clean_eguiproject_dir(project_dir, child_path, removed_paths, preserved_paths)
            removed_files += files
            removed_dirs += dirs
            continue

        if os.path.isdir(child_path) and name == _RESOURCE_DIRNAME:
            preserved_paths.append(rel_path)
            files, dirs = _clean_resource_dir(project_dir, child_path, removed_paths, preserved_paths)
            removed_files += files
            removed_dirs += dirs
            continue

        if os.path.isdir(child_path) and name in _PRESERVED_TOP_LEVEL_DIRS:
            preserved_paths.append(rel_path)
            continue

        files, dirs = _remove_path(project_dir, child_path, removed_paths)
        removed_files += files
        removed_dirs += dirs

    return ProjectCleanReport(
        removed_files=removed_files,
        removed_dirs=removed_dirs,
        removed_paths=tuple(sorted(removed_paths)),
        preserved_paths=tuple(sorted(set(preserved_paths))),
    )
