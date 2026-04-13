"""Shared helpers for MainWindow-oriented UI tests."""

from __future__ import annotations

from ui_designer.tests.qt_test_utils import close_widget_safely


def close_test_window(window, *, stop_rendering=False):
    close_widget_safely(window, stop_rendering=stop_rendering)


def disable_main_window_compile(window, compiler_factory):
    existing_compiler = getattr(window, "compiler", None)
    if existing_compiler is not None and hasattr(existing_compiler, "cleanup"):
        existing_compiler.cleanup()
    window.compiler = compiler_factory()
    window._recreate_compiler = lambda _window=window: setattr(_window, "compiler", compiler_factory())
    window._trigger_compile = lambda *args, **kwargs: None
    return window


def open_loaded_test_project(window, project, project_dir, sdk_root="", *, silent=True):
    window._open_loaded_project(
        project,
        str(project_dir),
        preferred_sdk_root=str(sdk_root or ""),
        silent=silent,
    )
    return window
