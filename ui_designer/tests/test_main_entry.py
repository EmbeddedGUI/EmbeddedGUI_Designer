"""Tests for UI Designer main entry flow."""

from __future__ import annotations

import argparse
import os

import pytest


class _FakeConfig:
    def __init__(self):
        self.sdk_root = ""
        self.last_app = "HelloDesigner"
        self.last_project_path = ""
        self.recent_projects = []
        self.theme = "dark"
        self.ui_density = "standard"
        self.font_size_px = 0
        self.save_calls = 0

    def save(self):
        self.save_calls += 1

    def remove_recent_project(self, project_path):
        original_len = len(self.recent_projects)
        self.recent_projects = [item for item in self.recent_projects if item.get("project_path") != project_path]
        removed = len(self.recent_projects) != original_len
        if removed:
            if self.last_project_path == project_path:
                self.last_project_path = ""
            self.save()
        return removed


class _FakeApp:
    last_instance = None

    def __init__(self, argv):
        self.argv = argv
        self.application_name = ""
        self._style_sheet = "base-style"
        self._properties = {}
        self.exec_calls = 0
        type(self).last_instance = self

    def setApplicationName(self, name):
        self.application_name = name

    def styleSheet(self):
        return self._style_sheet

    def setStyleSheet(self, style):
        self._style_sheet = style

    def setProperty(self, key, value):
        self._properties[key] = value

    def property(self, key):
        return self._properties.get(key)

    def exec_(self):
        self.exec_calls += 1
        return 0


class _FakeWindow:
    last_instance = None

    def __init__(self, sdk_root, app_name="HelloDesigner"):
        self.sdk_root = sdk_root
        self.app_name = app_name
        self.open_calls = []
        self.show_called = False
        self.raise_on_open = None
        self.prompt_calls = 0
        type(self).last_instance = self

    def _open_project_path(self, path, preferred_sdk_root="", silent=False):
        self.open_calls.append(
            {
                "path": path,
                "preferred_sdk_root": preferred_sdk_root,
                "silent": silent,
            }
        )
        if self.raise_on_open is not None:
            raise self.raise_on_open

    def show(self):
        self.show_called = True

    def maybe_prompt_initial_sdk_setup(self):
        self.prompt_calls += 1


@pytest.fixture
def main_module():
    import ui_designer.main as designer_main

    return designer_main


def _patch_main_dependencies(monkeypatch, config, sdk_root, main_module, open_error=None, find_sdk_root_calls=None):
    import PyQt5.QtWidgets as qtwidgets
    import PyQt5.QtCore as qtcore
    import ui_designer.model.config as config_module
    import ui_designer.model.widget_registry as registry_module
    import ui_designer.model.workspace as workspace_module
    import ui_designer.ui.main_window as main_window_module
    import ui_designer.ui.theme as theme_module

    theme_calls = []
    registry_calls = []
    exit_codes = []
    window_state = {"instance": None}

    class WindowFactory(_FakeWindow):
        def __init__(self, sdk_root_arg, app_name="HelloDesigner"):
            super().__init__(sdk_root_arg, app_name=app_name)
            self.raise_on_open = open_error
            window_state["instance"] = self

    monkeypatch.setattr(config_module, "get_config", lambda: config)
    def _fake_find_sdk_root(**kwargs):
        if find_sdk_root_calls is not None:
            find_sdk_root_calls.append(kwargs)
        return sdk_root

    monkeypatch.setattr(workspace_module, "find_sdk_root", _fake_find_sdk_root)
    monkeypatch.setattr(
        registry_module.WidgetRegistry,
        "instance",
        classmethod(lambda cls: registry_calls.append("instance") or object()),
    )
    monkeypatch.setattr(
        theme_module,
        "apply_theme",
        lambda app, theme, density="standard": theme_calls.append((theme, density)),
    )
    monkeypatch.setattr(main_window_module, "MainWindow", WindowFactory)
    monkeypatch.setattr(qtcore.QTimer, "singleShot", staticmethod(lambda _msec, callback: callback()))
    monkeypatch.setattr(qtwidgets, "QApplication", _FakeApp)
    monkeypatch.setattr(main_module.sys, "exit", lambda code=0: exit_codes.append(code))

    return theme_calls, registry_calls, exit_codes, window_state


def test_main_opens_cli_project_with_resolved_sdk_root(monkeypatch, tmp_path, main_module):
    project_path = tmp_path / "DemoApp.egui"
    project_path.write_text("demo", encoding="utf-8")
    sdk_root = os.path.normpath(os.path.abspath(tmp_path / "sdk"))
    config = _FakeConfig()

    monkeypatch.setattr(
        main_module,
        "_parse_args",
        lambda: argparse.Namespace(project=str(project_path), app="DemoApp", sdk_root=str(tmp_path / "sdk")),
    )
    theme_calls, registry_calls, exit_codes, window_state = _patch_main_dependencies(monkeypatch, config, sdk_root, main_module)

    main_module.main()

    window = window_state["instance"]
    app = _FakeApp.last_instance
    assert config.sdk_root == sdk_root
    assert config.save_calls == 1
    assert theme_calls == [("dark", "standard")]
    assert registry_calls == ["instance"]
    assert window.sdk_root == sdk_root
    assert window.app_name == "DemoApp"
    assert window.open_calls == [
        {
            "path": os.path.normpath(os.path.abspath(project_path)),
            "preferred_sdk_root": sdk_root,
            "silent": False,
        }
    ]
    assert window.show_called is True
    assert app.application_name == "EmbeddedGUI Designer"
    assert app.styleSheet() == "base-style"
    assert app.property("designer_font_size_pt") == 0
    assert window.prompt_calls == 0
    assert exit_codes == [0]


def test_main_reopens_recent_project_directory_silently(monkeypatch, tmp_path, main_module):
    project_dir = tmp_path / "RecentProject"
    project_dir.mkdir()
    sdk_root = os.path.normpath(os.path.abspath(tmp_path / "sdk"))
    config = _FakeConfig()
    config.sdk_root = sdk_root
    config.last_app = "RecentApp"
    config.last_project_path = str(project_dir)

    monkeypatch.setattr(
        main_module,
        "_parse_args",
        lambda: argparse.Namespace(project=None, app=None, sdk_root=None),
    )
    _, _, _, window_state = _patch_main_dependencies(monkeypatch, config, sdk_root, main_module)

    main_module.main()

    window = window_state["instance"]
    assert window.app_name == "RecentApp"
    assert window.open_calls == [
        {
            "path": os.path.normpath(os.path.abspath(project_dir)),
            "preferred_sdk_root": sdk_root,
            "silent": True,
        }
    ]
    assert window.prompt_calls == 0
    assert window.show_called is True


def test_main_prints_warning_when_project_open_fails(monkeypatch, tmp_path, capsys, main_module):
    project_path = tmp_path / "Broken.egui"
    project_path.write_text("broken", encoding="utf-8")
    sdk_root = os.path.normpath(os.path.abspath(tmp_path / "sdk"))
    config = _FakeConfig()

    monkeypatch.setattr(
        main_module,
        "_parse_args",
        lambda: argparse.Namespace(project=str(project_path), app=None, sdk_root=None),
    )
    _, _, _, window_state = _patch_main_dependencies(monkeypatch, config, sdk_root, main_module, open_error=RuntimeError("boom"))

    main_module.main()

    window = window_state["instance"]
    out = capsys.readouterr().out
    assert "Warning: Failed to load project: boom" in out
    assert window.show_called is True
    assert window.prompt_calls == 0


def test_main_starts_without_sdk_root_and_keeps_window_usable(monkeypatch, main_module):
    config = _FakeConfig()

    monkeypatch.setattr(
        main_module,
        "_parse_args",
        lambda: argparse.Namespace(project=None, app=None, sdk_root=None),
    )
    theme_calls, registry_calls, exit_codes, window_state = _patch_main_dependencies(monkeypatch, config, "", main_module)

    main_module.main()

    window = window_state["instance"]
    app = _FakeApp.last_instance
    assert config.sdk_root == ""
    assert config.save_calls == 0
    assert theme_calls == [("dark", "standard")]
    assert registry_calls == ["instance"]
    assert window.sdk_root == ""
    assert window.open_calls == []
    assert window.show_called is True
    assert app.application_name == "EmbeddedGUI Designer"
    assert window.prompt_calls == 0
    assert exit_codes == [0]


def test_main_clears_stale_last_project_path_before_showing_window(monkeypatch, tmp_path, main_module):
    config = _FakeConfig()
    missing_project = os.path.normpath(os.path.abspath(tmp_path / "Missing" / "Missing.egui"))
    config.last_project_path = missing_project
    config.recent_projects = [
        {
            "project_path": missing_project,
            "sdk_root": "",
            "display_name": "Missing",
        }
    ]

    monkeypatch.setattr(
        main_module,
        "_parse_args",
        lambda: argparse.Namespace(project=None, app=None, sdk_root=None),
    )
    _, _, exit_codes, window_state = _patch_main_dependencies(monkeypatch, config, "", main_module)

    main_module.main()

    window = window_state["instance"]
    assert config.last_project_path == ""
    assert config.recent_projects == []
    assert config.save_calls == 1
    assert window.open_calls == []
    assert window.show_called is True
    assert window.prompt_calls == 0
    assert exit_codes == [0]


def test_main_passes_default_sdk_cache_candidate_to_sdk_discovery(monkeypatch, tmp_path, main_module):
    config = _FakeConfig()
    find_sdk_root_calls = []
    default_cache = os.path.normpath(os.path.abspath(tmp_path / "config" / "sdk" / "EmbeddedGUI"))

    monkeypatch.setattr(
        main_module,
        "_parse_args",
        lambda: argparse.Namespace(project=None, app=None, sdk_root=None),
    )
    monkeypatch.setattr(
        "ui_designer.model.sdk_bootstrap.default_sdk_install_dir",
        lambda: default_cache,
    )
    _, _, _, _ = _patch_main_dependencies(
        monkeypatch,
        config,
        "",
        main_module,
        find_sdk_root_calls=find_sdk_root_calls,
    )

    main_module.main()

    assert len(find_sdk_root_calls) == 1
    assert "extra_candidates" not in find_sdk_root_calls[0]


def test_suppress_noisy_qt_platform_logs_sets_defaults_when_rules_missing(monkeypatch, main_module):
    monkeypatch.delenv("QT_LOGGING_RULES", raising=False)

    main_module._suppress_noisy_qt_platform_logs()

    assert os.environ["QT_LOGGING_RULES"] == "qt.qpa.windows.debug=false;qt.qpa.events.debug=false"


def test_suppress_noisy_qt_platform_logs_appends_missing_qpa_rules(monkeypatch, main_module):
    monkeypatch.setenv("QT_LOGGING_RULES", "qt.network.ssl.warning=true")

    main_module._suppress_noisy_qt_platform_logs()

    assert os.environ["QT_LOGGING_RULES"] == (
        "qt.network.ssl.warning=true;"
        "qt.qpa.windows.debug=false;"
        "qt.qpa.events.debug=false"
    )


def test_suppress_noisy_qt_platform_logs_preserves_explicit_qpa_rules(monkeypatch, main_module):
    monkeypatch.setenv("QT_LOGGING_RULES", "qt.qpa.windows.debug=true;qt.network.ssl.warning=true")

    main_module._suppress_noisy_qt_platform_logs()

    assert os.environ["QT_LOGGING_RULES"] == (
        "qt.qpa.windows.debug=true;"
        "qt.network.ssl.warning=true;"
        "qt.qpa.events.debug=false"
    )


def test_should_suppress_qt_message_matches_wm_destroy_noise(main_module):
    assert main_module._should_suppress_qt_message("External WM_DESTROY received for QWidgetWindow(...)") is True
    assert main_module._should_suppress_qt_message("qt.qpa.windows: QWindowsWindow::destroyWindow") is False


def test_install_qt_message_filter_suppresses_only_matching_messages(monkeypatch, main_module):
    installed = {}
    forwarded = []

    def previous_handler(msg_type, context, message):
        forwarded.append((msg_type, context, message))

    def fake_install(handler):
        installed["handler"] = handler
        return previous_handler

    monkeypatch.setattr("PyQt5.QtCore.qInstallMessageHandler", fake_install)
    main_module._PREVIOUS_QT_MESSAGE_HANDLER = None
    main_module._QT_MESSAGE_FILTER_INSTALLED = False

    main_module._install_qt_message_filter()

    assert "handler" in installed
    installed["handler"](0, object(), "External WM_DESTROY received for QWidgetWindow(...)")
    installed["handler"](0, object(), "Some other Qt warning")

    assert len(forwarded) == 1
    assert forwarded[0][0] == 0
    assert forwarded[0][2] == "Some other Qt warning"
