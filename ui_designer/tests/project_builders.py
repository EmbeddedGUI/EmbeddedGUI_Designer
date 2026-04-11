"""Shared test-only project construction helpers."""

from __future__ import annotations

import os
from pathlib import Path

from ui_designer.tests.page_builders import add_test_widget, build_test_page_from_root
from ui_designer.model.project import Project
from ui_designer.utils.scaffold import (
    build_empty_project_model,
    build_empty_project_model_with_root,
    require_project_page_root,
    save_project_with_designer_scaffold,
)


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


def build_test_project_with_root(
    app_name="TestApp",
    *,
    page_name="main_page",
    screen_width=240,
    screen_height=320,
    sdk_root="",
    project_dir="",
):
    """Build a minimal test project and return it with the startup page root widget."""
    project, _page, root = build_empty_project_model_with_root(
        app_name,
        screen_width,
        screen_height,
        sdk_root=sdk_root,
        project_dir=project_dir,
        page_name=page_name,
    )
    return project, root


def build_test_project_with_page_root(
    app_name="TestApp",
    *,
    page_name="main_page",
    screen_width=240,
    screen_height=320,
    sdk_root="",
    project_dir="",
):
    """Build a minimal test project and return it with the selected page and root widget."""
    return build_empty_project_model_with_root(
        app_name,
        screen_width,
        screen_height,
        sdk_root=sdk_root,
        project_dir=project_dir,
        page_name=page_name,
    )


def build_test_project_with_page_roots(
    app_name="TestApp",
    screen_width=240,
    screen_height=320,
    *,
    sdk_root="",
    project_dir="",
    pages=None,
):
    """Build a minimal test project and return a map of page names to root widgets."""
    project = build_test_project(
        app_name,
        screen_width,
        screen_height,
        sdk_root=sdk_root,
        project_dir=project_dir,
        pages=pages,
    )
    roots = {}
    for page in project.pages:
        _page, root = require_project_page_root(project, page.name)
        roots[page.name] = root
    return project, roots


def build_test_project_with_widgets(
    app_name="TestApp",
    *,
    page_name="main_page",
    screen_width=240,
    screen_height=320,
    sdk_root="",
    project_dir="",
    widgets=None,
):
    """Build a minimal test project and attach caller-supplied widgets to one page root."""
    project, page, root = build_test_project_with_page_root(
        app_name,
        page_name=page_name,
        screen_width=screen_width,
        screen_height=screen_height,
        sdk_root=sdk_root,
        project_dir=project_dir,
    )
    for widget in widgets or []:
        root.add_child(widget)
    return project, page, root


def build_test_project_with_widget(
    app_name="TestApp",
    widget_type="label",
    *,
    page_name="main_page",
    screen_width=240,
    screen_height=320,
    sdk_root="",
    project_dir="",
    **widget_kwargs,
):
    """Build a minimal test project and attach one basic widget to the selected page."""
    project, page, _root = build_test_project_with_page_root(
        app_name,
        page_name=page_name,
        screen_width=screen_width,
        screen_height=screen_height,
        sdk_root=sdk_root,
        project_dir=project_dir,
    )
    widget = add_test_widget(page, widget_type, **widget_kwargs)
    return project, page, widget


def build_test_project_from_pages(
    pages=None,
    app_name="TestApp",
    screen_width=240,
    screen_height=320,
    *,
    sdk_root="",
    project_dir="",
    page_mode="easy_page",
    startup=None,
    startup_page=None,
):
    """Build a minimal test project from preconstructed Page models."""
    project = Project(screen_width=screen_width, screen_height=screen_height, app_name=app_name)
    project.sdk_root = str(sdk_root or "")
    project.project_dir = os.path.normpath(str(project_dir)) if project_dir else ""
    project.page_mode = page_mode
    for page in pages or []:
        project.add_page(page)
    if startup_page is not None:
        project.startup_page = startup_page
    elif startup is not None:
        project.startup_page = startup
    elif project.pages:
        project.startup_page = project.pages[0].name
    return project


def build_test_project_from_root(
    root,
    *,
    page_name="main_page",
    app_name="TestApp",
    screen_width=None,
    screen_height=None,
    sdk_root="",
    project_dir="",
    page_mode="easy_page",
    startup=None,
    startup_page=None,
):
    """Build a minimal test project from a caller-supplied page root widget."""
    resolved_screen_width = screen_width
    if resolved_screen_width is None:
        resolved_screen_width = getattr(root, "width", None)
    if resolved_screen_width is None:
        resolved_screen_width = 240

    resolved_screen_height = screen_height
    if resolved_screen_height is None:
        resolved_screen_height = getattr(root, "height", None)
    if resolved_screen_height is None:
        resolved_screen_height = 320

    page = build_test_page_from_root(
        page_name,
        root=root,
        screen_width=resolved_screen_width,
        screen_height=resolved_screen_height,
    )
    project = build_test_project_from_pages(
        [page],
        app_name=app_name,
        screen_width=resolved_screen_width,
        screen_height=resolved_screen_height,
        sdk_root=sdk_root,
        project_dir=project_dir,
        page_mode=page_mode,
        startup=startup,
        startup_page=startup_page,
    )
    return project, page


def build_saved_test_project(
    project_dir,
    app_name,
    sdk_root="",
    *,
    screen_width=240,
    screen_height=320,
    pages=None,
    with_designer_scaffold=False,
    overwrite_scaffold=False,
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
    if with_designer_scaffold:
        save_project_with_designer_scaffold(
            project,
            str(project_root),
            overwrite=overwrite_scaffold,
            remove_legacy_designer_files=True,
        )
    else:
        project.save(str(project_root))
    return project
