"""Shared test-only project construction helpers."""

from __future__ import annotations

from pathlib import Path

from ui_designer.utils.scaffold import (
    build_project_model_and_page_with_widget,
    build_project_model_and_page_with_widgets,
    build_project_model_and_root_with_widgets,
    build_project_model_with_widget,
    build_project_model_with_page_widgets,
    build_project_model_only_with_page_widgets,
    build_project_model_only_with_widget,
    build_project_model_only_with_widgets,
    build_project_model_with_widgets,
    build_project_model_from_pages,
    build_project_model_from_root,
    build_project_model_only_from_root_with_widgets,
    build_project_model_from_root_with_widgets,
    build_empty_project_model,
    build_empty_project_model_and_root,
    build_empty_project_model_with_root,
    build_empty_project_model_with_page_roots,
    build_saved_project_model,
    build_saved_project_model_and_page_with_widgets,
    build_saved_project_model_and_root_with_widgets,
    build_saved_project_model_only_with_page_widgets,
    build_saved_project_model_only_with_widgets,
    build_saved_project_model_with_page_widgets,
    build_saved_project_model_with_widgets,
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
    return build_empty_project_model_and_root(
        app_name,
        screen_width,
        screen_height,
        sdk_root=sdk_root,
        project_dir=project_dir,
        page_name=page_name,
    )


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
    return build_empty_project_model_with_page_roots(
        app_name,
        screen_width,
        screen_height,
        sdk_root=sdk_root,
        project_dir=project_dir,
        pages=pages,
    )


def build_test_project_with_page_widgets(
    app_name="TestApp",
    screen_width=240,
    screen_height=320,
    *,
    sdk_root="",
    project_dir="",
    page_widgets=None,
    page_customizers=None,
    pages=None,
    project_customizer=None,
):
    """Build a minimal multi-page project, attach widgets, and optionally customize pages and project."""
    return build_project_model_with_page_widgets(
        app_name,
        screen_width,
        screen_height,
        sdk_root=sdk_root,
        project_dir=project_dir,
        page_widgets=page_widgets,
        page_customizers=page_customizers,
        pages=pages,
        project_customizer=project_customizer,
    )


def build_test_project_only_with_page_widgets(
    app_name="TestApp",
    screen_width=240,
    screen_height=320,
    *,
    sdk_root="",
    project_dir="",
    page_widgets=None,
    page_customizers=None,
    pages=None,
    project_customizer=None,
):
    """Build a minimal multi-page project and return only the populated project."""
    return build_project_model_only_with_page_widgets(
        app_name,
        screen_width,
        screen_height,
        sdk_root=sdk_root,
        project_dir=project_dir,
        page_widgets=page_widgets,
        page_customizers=page_customizers,
        pages=pages,
        project_customizer=project_customizer,
    )


def build_test_project_with_widgets(
    app_name="TestApp",
    *,
    page_name="main_page",
    screen_width=240,
    screen_height=320,
    sdk_root="",
    project_dir="",
    widgets=None,
    page_customizer=None,
    project_customizer=None,
):
    """Build a minimal test project, attach widgets, and optionally customize the page and project."""
    return build_project_model_with_widgets(
        app_name,
        screen_width,
        screen_height,
        sdk_root=sdk_root,
        project_dir=project_dir,
        page_name=page_name,
        widgets=widgets,
        page_customizer=page_customizer,
        project_customizer=project_customizer,
    )


def build_test_project_and_page_with_widgets(
    app_name="TestApp",
    *,
    page_name="main_page",
    screen_width=240,
    screen_height=320,
    sdk_root="",
    project_dir="",
    widgets=None,
    page_customizer=None,
    project_customizer=None,
):
    """Build a minimal test project and return it with the populated page."""
    return build_project_model_and_page_with_widgets(
        app_name,
        screen_width,
        screen_height,
        sdk_root=sdk_root,
        project_dir=project_dir,
        page_name=page_name,
        widgets=widgets,
        page_customizer=page_customizer,
        project_customizer=project_customizer,
    )


def build_test_project_and_root_with_widgets(
    app_name="TestApp",
    *,
    page_name="main_page",
    screen_width=240,
    screen_height=320,
    sdk_root="",
    project_dir="",
    widgets=None,
    page_customizer=None,
    project_customizer=None,
):
    """Build a minimal test project and return it with the populated root widget."""
    return build_project_model_and_root_with_widgets(
        app_name,
        screen_width,
        screen_height,
        sdk_root=sdk_root,
        project_dir=project_dir,
        page_name=page_name,
        widgets=widgets,
        page_customizer=page_customizer,
        project_customizer=project_customizer,
    )


def build_test_project_only_with_widgets(
    app_name="TestApp",
    *,
    page_name="main_page",
    screen_width=240,
    screen_height=320,
    sdk_root="",
    project_dir="",
    widgets=None,
    page_customizer=None,
    project_customizer=None,
):
    """Build a minimal test project and return only the populated project."""
    return build_project_model_only_with_widgets(
        app_name,
        screen_width,
        screen_height,
        sdk_root=sdk_root,
        project_dir=project_dir,
        page_name=page_name,
        widgets=widgets,
        page_customizer=page_customizer,
        project_customizer=project_customizer,
    )


def build_test_project_with_widget(
    app_name="TestApp",
    widget_type="label",
    *,
    page_name="main_page",
    screen_width=240,
    screen_height=320,
    sdk_root="",
    project_dir="",
    page_customizer=None,
    project_customizer=None,
    **widget_kwargs,
):
    """Build a minimal test project, attach one widget, and optionally customize the page and project."""
    return build_project_model_with_widget(
        app_name,
        widget_type,
        page_name=page_name,
        screen_width=screen_width,
        screen_height=screen_height,
        sdk_root=sdk_root,
        project_dir=project_dir,
        page_customizer=page_customizer,
        project_customizer=project_customizer,
        **widget_kwargs,
    )


def build_test_project_and_page_with_widget(
    app_name="TestApp",
    widget_type="label",
    *,
    page_name="main_page",
    screen_width=240,
    screen_height=320,
    sdk_root="",
    project_dir="",
    page_customizer=None,
    project_customizer=None,
    **widget_kwargs,
):
    """Build a minimal test project with one widget and return it with the populated page."""
    return build_project_model_and_page_with_widget(
        app_name,
        widget_type,
        page_name=page_name,
        screen_width=screen_width,
        screen_height=screen_height,
        sdk_root=sdk_root,
        project_dir=project_dir,
        page_customizer=page_customizer,
        project_customizer=project_customizer,
        **widget_kwargs,
    )


def build_test_project_only_with_widget(
    app_name="TestApp",
    widget_type="label",
    *,
    page_name="main_page",
    screen_width=240,
    screen_height=320,
    sdk_root="",
    project_dir="",
    page_customizer=None,
    project_customizer=None,
    **widget_kwargs,
):
    """Build a minimal test project with one widget and return only the project."""
    return build_project_model_only_with_widget(
        app_name,
        widget_type,
        page_name=page_name,
        screen_width=screen_width,
        screen_height=screen_height,
        sdk_root=sdk_root,
        project_dir=project_dir,
        page_customizer=page_customizer,
        project_customizer=project_customizer,
        **widget_kwargs,
    )


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
    return build_project_model_from_pages(
        pages,
        app_name=app_name,
        screen_width=screen_width,
        screen_height=screen_height,
        sdk_root=sdk_root,
        project_dir=project_dir,
        page_mode=page_mode,
        startup=startup,
        startup_page=startup_page,
    )


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
    return build_project_model_from_root(
        root,
        page_name=page_name,
        app_name=app_name,
        screen_width=screen_width,
        screen_height=screen_height,
        sdk_root=sdk_root,
        project_dir=project_dir,
        page_mode=page_mode,
        startup=startup,
        startup_page=startup_page,
    )


def build_test_project_from_root_with_widgets(
    root,
    *,
    widgets=None,
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
    """Build a minimal test project from a caller-supplied root widget and attach children."""
    return build_project_model_from_root_with_widgets(
        root,
        widgets=widgets,
        page_name=page_name,
        app_name=app_name,
        screen_width=screen_width,
        screen_height=screen_height,
        sdk_root=sdk_root,
        project_dir=project_dir,
        page_mode=page_mode,
        startup=startup,
        startup_page=startup_page,
    )


def build_test_project_only_from_root_with_widgets(
    root,
    *,
    widgets=None,
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
    """Build a minimal test project from a caller-supplied root widget and return only the populated project."""
    return build_project_model_only_from_root_with_widgets(
        root,
        widgets=widgets,
        page_name=page_name,
        app_name=app_name,
        screen_width=screen_width,
        screen_height=screen_height,
        sdk_root=sdk_root,
        project_dir=project_dir,
        page_mode=page_mode,
        startup=startup,
        startup_page=startup_page,
    )


def build_saved_test_project(
    project_dir,
    app_name,
    sdk_root="",
    *,
    screen_width=240,
    screen_height=320,
    pages=None,
    project_customizer=None,
    with_designer_scaffold=False,
    overwrite_scaffold=False,
):
    """Build, optionally customize, and save a minimal test project to disk."""
    project_root = Path(project_dir)
    return build_saved_project_model(
        app_name,
        str(project_root),
        screen_width,
        screen_height,
        sdk_root=sdk_root,
        pages=pages,
        project_customizer=project_customizer,
        with_designer_scaffold=with_designer_scaffold,
        overwrite_scaffold=overwrite_scaffold,
        remove_legacy_designer_files=True,
    )


def build_saved_test_project_with_widgets(
    project_dir,
    app_name,
    sdk_root="",
    *,
    page_name="main_page",
    screen_width=240,
    screen_height=320,
    widgets=None,
    page_customizer=None,
    project_customizer=None,
    with_designer_scaffold=False,
    overwrite_scaffold=False,
):
    """Build, populate, optionally customize, and save a single-page test project to disk."""
    return build_saved_project_model_with_widgets(
        app_name,
        page_name=page_name,
        screen_width=screen_width,
        screen_height=screen_height,
        sdk_root=sdk_root,
        project_dir=str(project_dir),
        widgets=widgets,
        page_customizer=page_customizer,
        project_customizer=project_customizer,
        with_designer_scaffold=with_designer_scaffold,
        overwrite_scaffold=overwrite_scaffold,
        remove_legacy_designer_files=True,
    )


def build_saved_test_project_and_page_with_widgets(
    project_dir,
    app_name,
    sdk_root="",
    *,
    page_name="main_page",
    screen_width=240,
    screen_height=320,
    widgets=None,
    page_customizer=None,
    project_customizer=None,
    with_designer_scaffold=False,
    overwrite_scaffold=False,
):
    """Build, populate, optionally customize, save, and return the project with its page."""
    return build_saved_project_model_and_page_with_widgets(
        app_name,
        page_name=page_name,
        screen_width=screen_width,
        screen_height=screen_height,
        sdk_root=sdk_root,
        project_dir=str(project_dir),
        widgets=widgets,
        page_customizer=page_customizer,
        project_customizer=project_customizer,
        with_designer_scaffold=with_designer_scaffold,
        overwrite_scaffold=overwrite_scaffold,
        remove_legacy_designer_files=True,
    )


def build_saved_test_project_and_root_with_widgets(
    project_dir,
    app_name,
    sdk_root="",
    *,
    page_name="main_page",
    screen_width=240,
    screen_height=320,
    widgets=None,
    page_customizer=None,
    project_customizer=None,
    with_designer_scaffold=False,
    overwrite_scaffold=False,
):
    """Build, populate, optionally customize, save, and return the project with its root widget."""
    return build_saved_project_model_and_root_with_widgets(
        app_name,
        page_name=page_name,
        screen_width=screen_width,
        screen_height=screen_height,
        sdk_root=sdk_root,
        project_dir=str(project_dir),
        widgets=widgets,
        page_customizer=page_customizer,
        project_customizer=project_customizer,
        with_designer_scaffold=with_designer_scaffold,
        overwrite_scaffold=overwrite_scaffold,
        remove_legacy_designer_files=True,
    )


def build_saved_test_project_only_with_widgets(
    project_dir,
    app_name,
    sdk_root="",
    *,
    page_name="main_page",
    screen_width=240,
    screen_height=320,
    widgets=None,
    page_customizer=None,
    project_customizer=None,
    with_designer_scaffold=False,
    overwrite_scaffold=False,
):
    """Build, populate, optionally customize, save, and return only the project."""
    return build_saved_project_model_only_with_widgets(
        app_name,
        page_name=page_name,
        screen_width=screen_width,
        screen_height=screen_height,
        sdk_root=sdk_root,
        project_dir=str(project_dir),
        widgets=widgets,
        page_customizer=page_customizer,
        project_customizer=project_customizer,
        with_designer_scaffold=with_designer_scaffold,
        overwrite_scaffold=overwrite_scaffold,
        remove_legacy_designer_files=True,
    )


def build_saved_test_project_with_page_widgets(
    project_dir,
    app_name,
    sdk_root="",
    *,
    screen_width=240,
    screen_height=320,
    page_widgets=None,
    page_customizers=None,
    pages=None,
    project_customizer=None,
    with_designer_scaffold=False,
    overwrite_scaffold=False,
):
    """Build, populate, optionally customize, and save a multi-page test project to disk."""
    return build_saved_project_model_with_page_widgets(
        app_name,
        screen_width,
        screen_height,
        sdk_root=sdk_root,
        project_dir=str(project_dir),
        page_widgets=page_widgets,
        page_customizers=page_customizers,
        pages=pages,
        project_customizer=project_customizer,
        with_designer_scaffold=with_designer_scaffold,
        overwrite_scaffold=overwrite_scaffold,
        remove_legacy_designer_files=True,
    )


def build_saved_test_project_only_with_page_widgets(
    project_dir,
    app_name,
    sdk_root="",
    *,
    screen_width=240,
    screen_height=320,
    page_widgets=None,
    page_customizers=None,
    pages=None,
    project_customizer=None,
    with_designer_scaffold=False,
    overwrite_scaffold=False,
):
    """Build, populate, optionally customize, save, and return only the project."""
    return build_saved_project_model_only_with_page_widgets(
        app_name,
        screen_width,
        screen_height,
        sdk_root=sdk_root,
        project_dir=str(project_dir),
        page_widgets=page_widgets,
        page_customizers=page_customizers,
        pages=pages,
        project_customizer=project_customizer,
        with_designer_scaffold=with_designer_scaffold,
        overwrite_scaffold=overwrite_scaffold,
        remove_legacy_designer_files=True,
    )
