"""Tests for shared MainWindow UI test helpers."""

from __future__ import annotations

from ui_designer.tests.ui.window_test_helpers import close_test_window, open_loaded_test_project


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
