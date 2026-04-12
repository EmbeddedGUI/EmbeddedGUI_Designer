"""Tests for shared MainWindow UI test helpers."""

from __future__ import annotations

from ui_designer.tests.ui.window_test_helpers import (
    close_test_window,
    disable_main_window_compile,
    open_loaded_test_project,
)


class TestWindowTestHelpers:
    def test_open_loaded_test_project_forwards_window_open_arguments(self):
        calls = []

        class _FakeWindow:
            def _open_loaded_project(self, project, project_dir, preferred_sdk_root="", silent=False):
                calls.append(
                    {
                        "project": project,
                        "project_dir": project_dir,
                        "preferred_sdk_root": preferred_sdk_root,
                        "silent": silent,
                    }
                )

        window = _FakeWindow()
        project = object()

        returned = open_loaded_test_project(
            window,
            project,
            "D:/workspace/DemoApp",
            "D:/sdk",
        )

        assert returned is window
        assert calls == [
            {
                "project": project,
                "project_dir": "D:/workspace/DemoApp",
                "preferred_sdk_root": "D:/sdk",
                "silent": True,
            }
        ]

    def test_close_test_window_delegates_to_qt_helper(self, monkeypatch):
        calls = []

        monkeypatch.setattr(
            "ui_designer.tests.ui.window_test_helpers.close_widget_safely",
            lambda window, stop_rendering=False: calls.append(
                {
                    "window": window,
                    "stop_rendering": stop_rendering,
                }
            ),
        )

        window = object()
        close_test_window(window, stop_rendering=True)

        assert calls == [
            {
                "window": window,
                "stop_rendering": True,
            }
        ]

    def test_disable_main_window_compile_installs_disabled_compiler_factory(self):
        class _Compiler:
            pass

        class _FakeWindow:
            compiler = None

        window = _FakeWindow()

        returned = disable_main_window_compile(window, _Compiler)

        assert returned is window
        window._recreate_compiler()
        assert isinstance(window.compiler, _Compiler)
        assert window._trigger_compile() is None

    def test_disable_main_window_compile_replaces_existing_compiler_immediately(self):
        calls = []

        class _ExistingCompiler:
            def cleanup(self):
                calls.append("cleanup")

        class _Compiler:
            pass

        class _FakeWindow:
            def __init__(self):
                self.compiler = _ExistingCompiler()

        window = _FakeWindow()

        disable_main_window_compile(window, _Compiler)

        assert calls == ["cleanup"]
        assert isinstance(window.compiler, _Compiler)
