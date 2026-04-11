"""Shared test-only project construction helpers."""

from __future__ import annotations

from pathlib import Path

from ui_designer.utils.scaffold import build_empty_project_model


def build_test_project(
    app_name="TestApp",
    screen_width=240,
    screen_height=320,
    *,
    sdk_root="",
    project_dir="",
    pages=None,
):
    """Build a minimal test project using the shared empty-project scaffold."""
    return build_empty_project_model(
        app_name,
        screen_width,
        screen_height,
        sdk_root=str(sdk_root or ""),
        project_dir=str(project_dir or ""),
        pages=pages,
    )


def build_saved_test_project(
    project_dir,
    app_name,
    sdk_root="",
    *,
    screen_width=240,
    screen_height=320,
    pages=None,
):
    """Build and save a minimal test project to disk."""
    project_root = Path(project_dir)
    project_root.mkdir(parents=True, exist_ok=True)
    project = build_test_project(
        app_name,
        screen_width,
        screen_height,
        sdk_root=sdk_root,
        project_dir=str(project_root),
        pages=pages,
    )
    project.save(str(project_root))
    return project
