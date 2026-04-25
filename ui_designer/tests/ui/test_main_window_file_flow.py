"""Qt UI tests for MainWindow project file flows."""

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from ui_designer.tests.project_builders import (
    build_saved_test_project_and_page_with_widgets as _create_project_and_page_with_widgets,
    build_saved_test_project_and_root_with_widgets as _create_project_and_root_with_widgets,
    build_saved_test_project as _create_project,
    build_saved_test_project_only_with_page_widgets as _create_project_only_with_page_widgets,
    build_saved_test_project_only_with_widgets as _create_project_only_with_widgets,
    build_saved_test_project_with_widgets as _create_project_with_widgets,
    build_saved_test_project_with_page_widgets as _create_project_with_page_widgets,
    load_saved_test_project as _load_project,
)
from ui_designer.tests.codegen_fixtures import (
    build_fake_prepare_project_codegen_outputs as _fake_prepare_project_codegen_outputs,
    build_fake_save_project_and_materialize_codegen as _fake_save_project_and_materialize_codegen,
)
from ui_designer.tests.process_fixtures import build_completed_process_result
from ui_designer.tests.page_builders import (
    build_test_page_only_with_widget as _build_test_page_only_with_widget,
    build_test_page_root_with_widgets as _build_test_page_root_with_widgets,
)
from ui_designer.tests.qt_test_utils import HAS_PYQT5, skip_if_no_qt
from ui_designer.tests.sdk_builders import build_test_sdk_root as _create_sdk_root
from ui_designer.tests.ui.window_test_helpers import (
    close_test_window as _close_window,
    disable_main_window_compile as _disable_window_compile,
    open_loaded_test_project as _open_project_window,
)
from ui_designer.utils.scaffold import (
    add_widget_children as _add_widget_children,
    project_file_path,
    project_config_mockup_path,
    project_config_mockup_relpath,
    RESOURCE_DIR_RELPATH,
    require_project_page_root,
    save_project_model,
)
from ui_designer.model.workspace import sdk_output_path

if HAS_PYQT5:
    from PyQt5.QtCore import QByteArray, Qt, QPoint
    from PyQt5.QtWidgets import QApplication, QAbstractItemView, QLabel, QSizePolicy
    from PyQt5.QtWidgets import QMessageBox
    from PyQt5.QtTest import QTest

_skip_no_qt = skip_if_no_qt


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
    try:
        app.sendPostedEvents()
    except Exception:
        pass
    app.processEvents()
    for widget in list(QApplication.topLevelWidgets()):
        try:
            if widget.isVisible():
                undo_manager = getattr(widget, "_undo_manager", None)
                if undo_manager is not None:
                    undo_manager.mark_all_saved()
                clear_project_dirty = getattr(widget, "_clear_project_dirty", None)
                if callable(clear_project_dirty):
                    clear_project_dirty()
                widget.close()
            widget.deleteLater()
        except Exception:
            pass
    try:
        app.sendPostedEvents()
    except Exception:
        pass
    app.processEvents()


@pytest.fixture(autouse=True)
def bind_designer_runtime(monkeypatch, tmp_path):
    designer_root = tmp_path / "designer_runtime"
    designer_root.mkdir()

    import ui_designer.ui.app_selector as app_selector_module
    import ui_designer.ui.main_window as main_window_module
    import ui_designer.ui.new_project_dialog as new_project_dialog_module
    monkeypatch.setattr(app_selector_module, "list_designer_example_entries", lambda repo_root=None: [])
    monkeypatch.setattr(main_window_module, "designer_runtime_root", lambda repo_root=None: str(designer_root))
    monkeypatch.setattr(new_project_dialog_module, "designer_runtime_root", lambda repo_root=None: str(designer_root))
    yield designer_root
def _left_panel_tab_index(window, panel_key):
    return window._left_panel_tab_index_by_key[panel_key]


def _left_panel_tab_tooltip(window, panel_key):
    return window._left_panel_stack.tabToolTip(_left_panel_tab_index(window, panel_key))


def _left_panel_tab_whats_this(window, panel_key):
    return window._left_panel_stack.tabWhatsThis(_left_panel_tab_index(window, panel_key))


def _menu_target_labels(menu):
    ignored_labels = {"Move Into Last Target", "Clear Move Target History"}
    return [
        action.text()
        for action in menu.actions()
        if action.text()
        and action.text() not in ignored_labels
        and action.isEnabled()
        and not action.isSeparator()
        and action.menu() is None
    ]


def _context_submenu(menu, label):
    for action in menu.actions():
        if action.text() == label:
            return action.menu()
    raise AssertionError(f"{label} submenu not found")


def _actions_by_text(*actions):
    return {action.text(): action for action in actions if action is not None}


def test_resource_path_helpers_delegate_to_project_paths(qapp, isolated_config):
    from ui_designer.ui.main_window import MainWindow

    class _FakeProject:
        def get_project_file_path(self):
            return "D:/delegate/HelperDemo.egui"

        def get_build_mk_path(self):
            return "D:/delegate/build.mk"

        def get_app_config_path(self):
            return "D:/delegate/app_egui_config.h"

        def get_designer_dir(self):
            return "D:/delegate/.designer"

        def get_resource_dir(self):
            return "D:/demo/resource"

        def get_resource_src_dir(self):
            return "D:/demo/resource/src"

        def get_user_resource_config_path(self):
            return "D:/demo/resource/src/app_resource_config.json"

        def get_designer_resource_dir(self):
            return "D:/demo/resource/src/.designer"

        def get_eguiproject_layout_dir(self):
            return "D:/demo/.eguiproject/layout"

        def get_eguiproject_mockup_dir(self):
            return "D:/demo/.eguiproject/mockup"

        def get_eguiproject_resource_dir(self):
            return "D:/demo/.eguiproject/resources"

        def get_eguiproject_images_dir(self):
            return "D:/demo/.eguiproject/resources/images"

    window = MainWindow("")
    window.project = _FakeProject()
    window._project_dir = "D:/fallback"
    window.app_name = "FallbackDemo"

    assert window._get_project_file_path() == "D:/delegate/HelperDemo.egui"
    assert window._get_build_mk_path() == "D:/delegate/build.mk"
    assert window._get_app_config_path() == "D:/delegate/app_egui_config.h"
    assert window._get_designer_dir() == "D:/delegate/.designer"
    assert window._get_resource_dir() == "D:/demo/resource"
    assert window._get_resource_src_dir() == "D:/demo/resource/src"
    assert window._get_user_resource_config_path() == "D:/demo/resource/src/app_resource_config.json"
    assert window._get_designer_resource_dir() == "D:/demo/resource/src/.designer"
    assert window._get_eguiproject_layout_dir() == "D:/demo/.eguiproject/layout"
    assert window._get_eguiproject_mockup_dir() == "D:/demo/.eguiproject/mockup"
    assert window._get_eguiproject_resource_dir() == "D:/demo/.eguiproject/resources"
    assert window._get_eguiproject_images_dir() == "D:/demo/.eguiproject/resources/images"
    _close_window(window)


def test_persist_current_project_to_config_uses_project_file_helper(qapp, isolated_config, tmp_path):
    from ui_designer.ui.main_window import MainWindow

    delegated_project_file = tmp_path / "delegated" / "HelperDemo.egui"
    delegated_project_file.parent.mkdir(parents=True)
    delegated_project_file.write_text("<Project />\n", encoding="utf-8")

    class _FakeProject:
        def get_project_file_path(self):
            return str(delegated_project_file)

    window = MainWindow("")
    window.project = _FakeProject()
    window._project_dir = str(tmp_path / "fallback")
    window.app_name = "HelperDemo"

    window._persist_current_project_to_config()

    assert isolated_config.last_project_path == os.path.normpath(os.path.abspath(delegated_project_file))
    assert isolated_config.recent_projects[0]["project_path"] == os.path.normpath(os.path.abspath(delegated_project_file))
    _close_window(window)


def test_build_project_watch_snapshot_uses_project_level_path_helpers(
    qapp, isolated_config, tmp_path, monkeypatch
):
    from ui_designer.ui.main_window import MainWindow

    project_file = tmp_path / "delegated" / "WatchDemo.egui"
    build_mk = tmp_path / "delegated" / "build.mk"
    app_config = tmp_path / "delegated" / "app_egui_config.h"
    designer_dir = tmp_path / "delegated" / ".designer"
    fallback_project_dir = tmp_path / "fallback"
    legacy_designer_resource_config = fallback_project_dir / "resource" / "src" / "app_resource_config_designer.json"
    legacy_merged_resource_config = fallback_project_dir / "resource" / "src" / ".app_resource_config_merged.json"
    user_resource_config = tmp_path / "delegated" / "resource" / "src" / "app_resource_config.json"
    designer_resource_dir = tmp_path / "delegated" / "resource" / "src" / ".designer"
    layout_dir = tmp_path / "delegated" / ".eguiproject" / "layout"
    resource_dir = tmp_path / "delegated" / ".eguiproject" / "resources"
    mockup_dir = tmp_path / "delegated" / ".eguiproject" / "mockup"

    for path, content in (
        (project_file, "<Project />\n"),
        (build_mk, "include .designer/build_designer.mk\n"),
        (app_config, '#include ".designer/app_egui_config_designer.h"\n'),
        (legacy_designer_resource_config, "{}\n"),
        (legacy_merged_resource_config, "{}\n"),
        (user_resource_config, "{}\n"),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    for directory in (designer_dir, designer_resource_dir, layout_dir, resource_dir, mockup_dir):
        directory.mkdir(parents=True, exist_ok=True)

    class _FakeProject:
        def get_project_file_path(self):
            return str(project_file)

        def get_build_mk_path(self):
            return str(build_mk)

        def get_app_config_path(self):
            return str(app_config)

        def get_designer_dir(self):
            return str(designer_dir)

        def get_user_resource_config_path(self):
            return str(user_resource_config)

        def get_designer_resource_dir(self):
            return str(designer_resource_dir)

        def get_eguiproject_layout_dir(self):
            return str(layout_dir)

        def get_eguiproject_resource_dir(self):
            return str(resource_dir)

        def get_eguiproject_mockup_dir(self):
            return str(mockup_dir)

    window = MainWindow("")
    window.project = _FakeProject()
    window._project_dir = str(fallback_project_dir)
    window.app_name = "FallbackDemo"
    monkeypatch.setattr("ui_designer.utils.header_parser.discover_widget_headers", lambda project_dir: [])

    snapshot = window._build_project_watch_snapshot()

    assert os.path.normpath(os.path.abspath(project_file)) in snapshot
    assert os.path.normpath(os.path.abspath(build_mk)) in snapshot
    assert os.path.normpath(os.path.abspath(app_config)) in snapshot
    assert os.path.normpath(os.path.abspath(designer_dir)) in snapshot
    assert os.path.normpath(os.path.abspath(legacy_designer_resource_config)) in snapshot
    assert os.path.normpath(os.path.abspath(legacy_merged_resource_config)) in snapshot
    assert os.path.normpath(os.path.abspath(user_resource_config)) in snapshot
    assert os.path.normpath(os.path.abspath(designer_resource_dir)) in snapshot
    assert os.path.normpath(os.path.abspath(layout_dir)) in snapshot
    assert os.path.normpath(os.path.abspath(resource_dir)) in snapshot
    assert os.path.normpath(os.path.abspath(mockup_dir)) in snapshot
    _close_window(window)


def test_changed_paths_touch_resource_config_recognizes_legacy_merged_config():
    from ui_designer.ui.main_window import MainWindow

    assert MainWindow._changed_paths_touch_resource_config(
        ["D:/demo/resource/src/.app_resource_config_merged.json"]
    ) is True


class _DisabledCompiler:
    def can_build(self):
        return False

    def is_preview_running(self):
        return False

    def stop_exe(self):
        return None

    def cleanup(self):
        return None

    def get_build_error(self):
        return "preview disabled for test"

    def set_screen_size(self, width, height):
        return None

    def is_exe_ready(self):
        return False


class _DummySignal:
    def connect(self, _handler):
        return None


class _IdleWorker:
    def __init__(self):
        self.log = _DummySignal()

    def isRunning(self):
        return False


class _AutoRetryCompiler:
    app_root_arg = "example"

    def __init__(self, app_dir, *, exe_ready=True):
        self.app_dir = str(app_dir)
        self._exe_ready = bool(exe_ready)
        self.precompile_calls = 0
        self.stop_calls = 0
        self.precompile_callback = None

    def can_build(self):
        return True

    def get_build_error(self):
        return ""

    def set_screen_size(self, width, height):
        return None

    def is_preview_running(self):
        return False

    def is_exe_ready(self):
        return self._exe_ready

    def stop_exe(self):
        self.stop_calls += 1

    def cleanup(self):
        return None

    def precompile_async(self, callback):
        self.precompile_calls += 1
        self.precompile_callback = callback
        return _IdleWorker()

    def compile_and_run_async(self, *args, **kwargs):
        return _IdleWorker()


@_skip_no_qt
class TestMainWindowFileFlow:
    def test_open_project_path_accepts_directory(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.project import Project
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "OpenDemo"
        _create_project(project_dir, "OpenDemo", sdk_root)

        window = MainWindow(str(sdk_root))
        captured = {}
        loaded_paths = []

        monkeypatch.setattr(
            "ui_designer.ui.main_window.load_saved_project_model",
            lambda path: loaded_paths.append(os.path.normpath(os.path.abspath(path))) or _load_project(path),
        )

        def fake_open_loaded_project(project, project_root, preferred_sdk_root="", silent=False):
            captured["app_name"] = project.app_name
            captured["project_dir"] = project_root
            captured["preferred_sdk_root"] = preferred_sdk_root
            captured["silent"] = silent

        monkeypatch.setattr(window, "_open_loaded_project", fake_open_loaded_project)

        window._open_project_path(str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)

        assert captured == {
            "app_name": "OpenDemo",
            "project_dir": os.path.normpath(os.path.abspath(project_dir)),
            "preferred_sdk_root": os.path.normpath(os.path.abspath(sdk_root)),
            "silent": True,
        }
        assert loaded_paths == [os.path.normpath(os.path.abspath(project_dir))]
        _close_window(window)

    def test_open_project_path_registers_app_local_widgets_before_loading_pages(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_registry import WidgetRegistry
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "CustomWidgetDemo"
        _create_project(project_dir, "CustomWidgetDemo", sdk_root)

        widget_dir = project_dir / "widgets"
        widget_dir.mkdir()
        (widget_dir / "egui_view_fancy_label.h").write_text(
            (
                "#ifndef _EGUI_VIEW_FANCY_LABEL_H_\n"
                "#define _EGUI_VIEW_FANCY_LABEL_H_\n"
                '#include "egui_view.h"\n'
                "typedef struct egui_view_fancy_label egui_view_fancy_label_t;\n"
                "void egui_view_fancy_label_init(egui_view_t *self);\n"
                "void egui_view_fancy_label_set_text(egui_view_t *self, const char *text);\n"
                "#endif\n"
            ),
            encoding="utf-8",
        )
        (project_dir / ".eguiproject" / "layout" / "main_page.xml").write_text(
            (
                '<?xml version="1.0" encoding="utf-8"?>\n'
                "<Page>\n"
                '    <Group id="root_group" x="0" y="0" width="240" height="320">\n'
                '        <FancyLabel id="fancy_1" x="10" y="20" width="120" height="24" text="Hello" />\n'
                "    </Group>\n"
                "</Page>\n"
            ),
            encoding="utf-8",
        )

        window = MainWindow(str(sdk_root))
        captured = {}

        def fake_open_loaded_project(project, project_root, preferred_sdk_root="", silent=False):
            _page, root = require_project_page_root(project)
            child = root.children[0]
            captured["widget_type"] = child.widget_type
            captured["text"] = child.properties["text"]
            captured["project_dir"] = project_root

        monkeypatch.setattr(window, "_open_loaded_project", fake_open_loaded_project)

        window._open_project_path(str(project_dir / "CustomWidgetDemo.egui"), preferred_sdk_root=str(sdk_root), silent=True)

        assert WidgetRegistry.instance().has("fancy_label")
        assert WidgetRegistry.instance().get("fancy_label")["header_include"] == "widgets/egui_view_fancy_label.h"
        assert captured["widget_type"] == "fancy_label"
        assert captured["text"] == "Hello"
        assert captured["project_dir"] == os.path.normpath(os.path.abspath(project_dir))
        WidgetRegistry.instance().clear_app_local_widgets()
        _close_window(window)

    def test_open_loaded_project_prompts_and_resets_on_sdk_version_mismatch(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.project import Project
        from ui_designer.model.sdk_fingerprint import SdkFingerprint
        from ui_designer.ui import main_window as main_window_module
        from ui_designer.ui.main_window import MainWindow

        class _FakeCompiler(_DisabledCompiler):
            def __init__(self, project_root, app_dir, app_name="HelloDesigner"):
                self.project_root = project_root
                self.app_dir = app_dir
                self.app_name = app_name
                self.app_root_arg = "example"

            def can_build(self):
                return True

            def get_build_error(self):
                return ""

        def _setup_project(project):
            project.sdk_fingerprint = SdkFingerprint(
                source_kind="submodule",
                revision="sdk-old-123",
                commit="old1234567890",
                commit_short="old1234",
            )

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "MismatchDemo"
        project = _create_project(
            project_dir,
            "MismatchDemo",
            sdk_root,
            project_customizer=_setup_project,
        )

        (project_dir / "build.mk").write_text("# legacy build\n", encoding="utf-8")
        (project_dir / "app_egui_config.h").write_text("#define LEGACY_CONFIG 1\n", encoding="utf-8")
        (project_dir / "build_designer.mk").write_text("EGUI_CODE_SRC += $(EGUI_APP_PATH)\n", encoding="utf-8")
        (project_dir / "app_egui_config_designer.h").write_text("#define EGUI_CONFIG_SCEEN_WIDTH 240\n", encoding="utf-8")
        (project_dir / "resource" / "src" / "app_resource_config.json").write_text(
            json.dumps(
                {
                    "img": [
                        {
                            "file": "legacy_extra.png",
                            "format": "alpha",
                            "alpha": "4",
                        }
                    ],
                    "font": [],
                },
                ensure_ascii=False,
            ) + "\n",
            encoding="utf-8",
        )

        monkeypatch.setattr(main_window_module, "CompilerEngine", _FakeCompiler)
        monkeypatch.setattr(
            main_window_module,
            "collect_sdk_fingerprint",
            lambda sdk_root, designer_repo_root=None: SdkFingerprint(
                source_kind="submodule",
                revision="sdk-new-456",
                commit="new4567890abcd",
                commit_short="new4567",
            ),
        )

        prompts = []
        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_start_precompile", lambda: None)
        monkeypatch.setattr(
            main_window_module.QMessageBox,
            "question",
            lambda *args, **kwargs: prompts.append({"title": args[1], "text": args[2]}) or QMessageBox.Yes,
        )

        compile_calls = []
        monkeypatch.setattr(window, "_trigger_compile", lambda *args, **kwargs: compile_calls.append("compile"))

        loaded = _load_project(project_dir)
        _open_project_window(window, loaded, project_dir, sdk_root, silent=False)

        reloaded = _load_project(project_dir)
        assert prompts
        assert prompts[0]["title"] == "SDK Version Mismatch"
        assert "sdk-old-123" in prompts[0]["text"]
        assert "sdk-new-456" in prompts[0]["text"]
        assert reloaded.sdk_fingerprint.revision == "sdk-new-456"
        assert ".designer/build_designer.mk" in (project_dir / "build.mk").read_text(encoding="utf-8")
        assert "# legacy build" in (project_dir / "build.mk").read_text(encoding="utf-8")
        assert '#include ".designer/app_egui_config_designer.h"' in (project_dir / "app_egui_config.h").read_text(encoding="utf-8")
        assert "#define LEGACY_CONFIG 1" in (project_dir / "app_egui_config.h").read_text(encoding="utf-8")
        assert not (project_dir / "build_designer.mk").exists()
        assert not (project_dir / "app_egui_config_designer.h").exists()
        assert (project_dir / ".designer" / "build_designer.mk").is_file()
        assert (project_dir / ".designer" / "app_egui_config_designer.h").is_file()
        assert json.loads((project_dir / "resource" / "src" / "app_resource_config.json").read_text(encoding="utf-8")) == {
            "img": [
                {
                    "file": "legacy_extra.png",
                    "format": "alpha",
                    "alpha": "4",
                }
            ],
            "font": [],
        }
        assert json.loads((project_dir / "resource" / "src" / ".designer" / "app_resource_config_designer.json").read_text(encoding="utf-8")) == {
            "img": [],
            "font": [],
            "mp4": [],
        }
        assert compile_calls
        assert "Project scaffold reset" in window.statusBar().currentMessage()
        _close_window(window)

    def test_open_project_uses_recovered_cached_sdk_example_as_default_dir(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        cached_sdk = tmp_path / "config" / "sdk" / "EmbeddedGUI"
        _create_sdk_root(cached_sdk)
        isolated_config.sdk_root = str(tmp_path / "missing_sdk")
        isolated_config.sdk_root = str(tmp_path / "missing_sdk")
        captured = {}

        def fake_get_open_file_name(parent, title, directory, filters):
            captured["title"] = title
            captured["directory"] = directory
            captured["filters"] = filters
            return "", ""

        window = MainWindow("")
        monkeypatch.setattr("ui_designer.ui.main_window.default_sdk_install_dir", lambda: str(cached_sdk))
        monkeypatch.setattr("ui_designer.ui.main_window.QFileDialog.getOpenFileName", fake_get_open_file_name)

        window._open_project()

        assert captured["title"] == "Open Project"
        assert captured["directory"] == window._default_open_project_dir()
        assert "EmbeddedGUI Projects" in captured["filters"]
        _close_window(window)

    def test_open_project_uses_nearest_existing_parent_for_missing_last_project(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        recent_parent = tmp_path / "workspace" / "RecentApp"
        recent_parent.mkdir(parents=True)
        isolated_config.last_project_path = str(recent_parent / "Missing.egui")
        captured = {}

        def fake_get_open_file_name(parent, title, directory, filters):
            captured["directory"] = directory
            return "", ""

        window = MainWindow("")
        monkeypatch.setattr("ui_designer.ui.main_window.QFileDialog.getOpenFileName", fake_get_open_file_name)

        window._open_project()

        assert captured["directory"] == os.path.normpath(os.path.abspath(recent_parent))
        _close_window(window)

    def test_save_project_writes_project_and_generated_files(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "SaveDemo"
        project = _create_project(project_dir, "SaveDemo", sdk_root)

        window = MainWindow(str(sdk_root))
        window.project = project
        window.project_root = str(sdk_root)
        window._project_dir = str(project_dir)
        window.app_name = "SaveDemo"
        window._undo_manager.get_stack("main_page").push("<Page />")

        monkeypatch.setattr(window, "_recreate_compiler", lambda: None)
        monkeypatch.setattr(
            "ui_designer.ui.main_window.save_project_and_materialize_codegen",
            _fake_save_project_and_materialize_codegen("generated.c", "// generated\n"),
        )

        window._save_project()

        assert (project_dir / "SaveDemo.egui").is_file()
        assert (project_dir / "generated.c").read_text(encoding="utf-8") == "// generated\n"
        assert (project_dir / "build.mk").is_file()
        assert (project_dir / ".designer" / "build_designer.mk").is_file()
        assert (project_dir / "app_egui_config.h").is_file()
        assert (project_dir / ".designer" / "app_egui_config_designer.h").is_file()
        assert (project_dir / "resource" / "src" / "app_resource_config.json").is_file()
        assert (project_dir / "resource" / "src" / ".designer" / "app_resource_config_designer.json").is_file()
        assert isolated_config.last_project_path == project_file_path(str(project_dir), "SaveDemo")
        assert isolated_config.recent_projects[0]["project_path"] == project_file_path(str(project_dir), "SaveDemo")
        assert window._undo_manager.is_any_dirty() is False
        assert "Saved:" in window.statusBar().currentMessage()
        _close_window(window)

    def test_save_project_clears_environmental_auto_retry_block_when_preview_recovers(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.ui.main_window import MainWindow

        class _ProbeFailCompiler:
            app_root_arg = "example"

            def __init__(self, app_dir):
                self.app_dir = str(app_dir)

            def can_build(self):
                return True

            def get_build_error(self):
                return ""

            def get_preview_build_error(self):
                return "make: *** No rule to make target 'main.exe'.  Stop."

            def ensure_preview_build_available(self, force=False):
                return False

            def set_screen_size(self, width, height):
                return None

            def is_preview_running(self):
                return False

            def is_exe_ready(self):
                return False

            def stop_exe(self):
                return None

            def cleanup(self):
                return None

            def precompile_async(self, callback):
                raise AssertionError("precompile_async should not be called when preview target probe fails")

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "SaveRetryRecoveryDemo"
        project = _create_project(project_dir, "SaveRetryRecoveryDemo", sdk_root)
        good_compiler = _AutoRetryCompiler(project_dir, exe_ready=True)
        recreate_calls = {"count": 0}

        window = MainWindow(str(sdk_root))

        def _recreate_compiler():
            recreate_calls["count"] += 1
            if recreate_calls["count"] == 1:
                window.compiler = _ProbeFailCompiler(project_dir)
            else:
                window.compiler = good_compiler

        monkeypatch.setattr(window, "_recreate_compiler", _recreate_compiler)
        monkeypatch.setattr(
            "ui_designer.ui.main_window.save_project_and_materialize_codegen",
            _fake_save_project_and_materialize_codegen("generated.c", "// generated\n"),
        )

        _open_project_window(window, project, project_dir, sdk_root)

        assert "main.exe" in window._auto_compile_retry_block_reason

        assert window._save_project() is True

        assert window._auto_compile_retry_block_reason == ""
        assert "Editing-only mode" not in window.statusBar().currentMessage()
        _close_window(window)

    def test_save_project_switches_to_python_preview_when_preview_becomes_unavailable(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.ui.main_window import MainWindow

        class _PreviewIncompatibleCompiler:
            app_root_arg = "example"

            def __init__(self, app_dir):
                self.app_dir = str(app_dir)

            def can_build(self):
                return True

            def get_build_error(self):
                return ""

            def get_preview_build_error(self):
                return "make: *** No rule to make target 'main.exe'.  Stop."

            def set_screen_size(self, width, height):
                return None

            def is_preview_running(self):
                return False

            def is_exe_ready(self):
                return False

            def stop_exe(self):
                return None

            def cleanup(self):
                return None

            def precompile_async(self, callback):
                return _IdleWorker()

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "SaveEditingOnlyPreviewDemo"
        project = _create_project(project_dir, "SaveEditingOnlyPreviewDemo", sdk_root)

        window = MainWindow(str(sdk_root))
        preview_reasons = []
        monkeypatch.setattr(window, "_switch_to_python_preview", lambda reason="": preview_reasons.append(reason))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _PreviewIncompatibleCompiler(project_dir)))
        monkeypatch.setattr(
            "ui_designer.ui.main_window.save_project_and_materialize_codegen",
            _fake_save_project_and_materialize_codegen("generated.c", "// generated\n"),
        )

        _open_project_window(window, project, project_dir, sdk_root)

        assert window._save_project() is True

        assert preview_reasons[-1] == "make: *** No rule to make target 'main.exe'.  Stop."
        assert "Editing-only mode: make: *** No rule to make target 'main.exe'.  Stop." in window.statusBar().currentMessage()
        _close_window(window)

    def test_save_project_reprobes_environmental_preview_block_after_compiler_recreation(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.ui.main_window import MainWindow

        class _ReprobeCompiler:
            app_root_arg = "example"

            def __init__(self, app_dir):
                self.app_dir = str(app_dir)
                self.preview_error = ""
                self.ensure_calls = []

            def can_build(self):
                return True

            def get_build_error(self):
                return ""

            def get_preview_build_error(self):
                return self.preview_error

            def ensure_preview_build_available(self, force=False):
                self.ensure_calls.append(force)
                self.preview_error = "make: *** No rule to make target 'main.exe'.  Stop."
                return False

            def set_screen_size(self, width, height):
                return None

            def is_preview_running(self):
                return False

            def is_exe_ready(self):
                return False

            def stop_exe(self):
                return None

            def cleanup(self):
                return None

            def precompile_async(self, callback):
                return _IdleWorker()

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "SaveReprobePreviewDemo"
        project = _create_project(project_dir, "SaveReprobePreviewDemo", sdk_root)
        compiler = _ReprobeCompiler(project_dir)

        window = MainWindow(str(sdk_root))
        window.project = project
        window.project_root = str(sdk_root)
        window._project_dir = str(project_dir)
        window.app_name = "SaveReprobePreviewDemo"
        window._block_auto_compile_retry("make: *** No rule to make target 'main.exe'.  Stop.")

        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", compiler))
        monkeypatch.setattr(
            "ui_designer.ui.main_window.save_project_and_materialize_codegen",
            _fake_save_project_and_materialize_codegen("generated.c", "// generated\n"),
        )

        assert window._save_project() is True

        assert compiler.ensure_calls == [True]
        assert "main.exe" in window._auto_compile_retry_block_reason
        assert "Editing-only mode: make: *** No rule to make target 'main.exe'.  Stop." in window.statusBar().currentMessage()
        _close_window(window)

    def test_save_project_files_writes_split_page_outputs_on_disk(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "SaveSplitDemo"
        project = _create_project(project_dir, "SaveSplitDemo", sdk_root)

        window = MainWindow(str(sdk_root))
        window.project = project
        window.project_root = str(sdk_root)
        window._project_dir = str(project_dir)
        monkeypatch.setattr(window, "_load_project_app_local_widgets", lambda *args, **kwargs: None)

        files = window._save_project_files(str(project_dir))

        assert ".designer/main_page.h" in files
        assert ".designer/main_page_layout.c" in files
        assert "main_page.c" in files
        assert "main_page_ext.h" in files
        assert (project_dir / ".designer" / "main_page.h").is_file()
        assert (project_dir / ".designer" / "main_page_layout.c").is_file()
        assert (project_dir / "main_page.c").is_file()
        assert (project_dir / "main_page_ext.h").is_file()
        assert '#include "main_page_ext.h"' in (project_dir / ".designer" / "main_page.h").read_text(encoding="utf-8")
        assert "void egui_main_page_user_init(egui_main_page_t *page)" in (project_dir / "main_page.c").read_text(encoding="utf-8")
        assert "#define EGUI_MAIN_PAGE_EXT_FIELDS" in (project_dir / "main_page_ext.h").read_text(encoding="utf-8")
        _close_window(window)

    def test_save_project_files_removes_legacy_root_designer_outputs(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "SaveLegacyDesignerOutputsDemo"
        project = _create_project(project_dir, "SaveLegacyDesignerOutputsDemo", sdk_root)

        (project_dir / "main_page.h").write_text("// legacy root header\n", encoding="utf-8")
        (project_dir / "main_page_layout.c").write_text("// legacy root layout\n", encoding="utf-8")
        (project_dir / "uicode.h").write_text("// legacy root uicode header\n", encoding="utf-8")
        (project_dir / "uicode.c").write_text("// legacy root uicode source\n", encoding="utf-8")

        window = MainWindow(str(sdk_root))
        window.project = project
        window.project_root = str(sdk_root)
        window._project_dir = str(project_dir)
        monkeypatch.setattr(window, "_load_project_app_local_widgets", lambda *args, **kwargs: None)

        window._save_project_files(str(project_dir))

        assert not (project_dir / "main_page.h").exists()
        assert not (project_dir / "main_page_layout.c").exists()
        assert not (project_dir / "uicode.h").exists()
        assert not (project_dir / "uicode.c").exists()
        assert (project_dir / ".designer" / "main_page.h").is_file()
        assert (project_dir / ".designer" / "main_page_layout.c").is_file()
        assert (project_dir / ".designer" / "uicode.h").is_file()
        assert (project_dir / ".designer" / "uicode.c").is_file()
        backup_root = project_dir / ".eguiproject" / "backup"
        assert any(path.name == "main_page.h" for path in backup_root.rglob("main_page.h"))
        assert any(path.name == "uicode.c" for path in backup_root.rglob("uicode.c"))
        _close_window(window)

    def test_save_project_files_rejects_legacy_page_files(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "SaveMigrationDemo"
        button = WidgetModel("button", name="confirm_button", x=10, y=10, width=80, height=32)
        button.on_click = "on_confirm"
        project = _create_project_only_with_widgets(
            project_dir,
            "SaveMigrationDemo",
            sdk_root,
            widgets=[button],
        )

        (project_dir / "main_page.h").write_text(
            (
                "#ifndef _MAIN_PAGE_H_\n"
                "#define _MAIN_PAGE_H_\n"
                "// USER CODE BEGIN includes\n"
                '#include "legacy_logic.h"\n'
                "// USER CODE END includes\n"
                "// USER CODE BEGIN declarations\n"
                "#define EGUI_MAIN_PAGE_HOOK_ON_OPEN(_page) main_page_after_open(_page)\n"
                "void main_page_after_open(egui_main_page_t *page);\n"
                "// USER CODE END declarations\n"
                "#endif\n"
            ),
            encoding="utf-8",
        )
        (project_dir / "main_page.c").write_text(
            (
                "// main_page.c - User implementation for main_page\n"
                "// Layout/widget init is in main_page_layout.c (auto-generated).\n"
                '#include "egui.h"\n'
                '#include "uicode.h"\n'
                '#include "main_page.h"\n'
                "\n"
                "// USER CODE BEGIN callbacks\n"
                "void on_confirm(egui_view_t *self)\n"
                "{\n"
                "    EGUI_UNUSED(self);\n"
                "    custom_confirm();\n"
                "}\n"
                "// USER CODE END callbacks\n"
                "\n"
                "// USER CODE BEGIN on_open\n"
                "    main_page_after_open(local);\n"
                "// USER CODE END on_open\n"
            ),
            encoding="utf-8",
        )

        window = MainWindow(str(sdk_root))
        window.project = project
        window.project_root = str(sdk_root)
        window._project_dir = str(project_dir)
        monkeypatch.setattr(window, "_load_project_app_local_widgets", lambda *args, **kwargs: None)

        with pytest.raises(ValueError, match="Unsupported legacy page source detected: main_page.c"):
            window._save_project_files(str(project_dir))

        assert not (project_dir / "main_page_ext.h").exists()
        assert '#include "legacy_logic.h"' in (project_dir / "main_page.h").read_text(encoding="utf-8")
        assert "custom_confirm();" in (project_dir / "main_page.c").read_text(encoding="utf-8")
        _close_window(window)

    def test_save_project_files_renames_existing_page_codegen_files(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.project import Project
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "RenameSaveDemo"
        project = _create_project(project_dir, "RenameSaveDemo", sdk_root)

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window, "_load_project_app_local_widgets", lambda *args, **kwargs: None)

        _open_project_window(window, project, project_dir, sdk_root)
        window._save_project_files(str(project_dir))
        (project_dir / "main_page.c").write_text("/* rename me */\n", encoding="utf-8")
        (project_dir / "main_page_ext.h").write_text("#define KEEP_MAIN_PAGE_EXT 1\n", encoding="utf-8")

        window._on_page_renamed("main_page", "dashboard_page")
        files = window._save_project_files(str(project_dir))

        assert ".designer/dashboard_page.h" in files
        assert ".designer/dashboard_page_layout.c" in files
        assert window._current_page is not None
        assert window._current_page.name == "dashboard_page"
        assert window.project.startup_page == "dashboard_page"
        assert not (project_dir / "main_page.h").exists()
        assert not (project_dir / "main_page_layout.c").exists()
        assert not (project_dir / ".designer" / "main_page.h").exists()
        assert not (project_dir / ".designer" / "main_page_layout.c").exists()
        assert not (project_dir / "main_page.c").exists()
        assert not (project_dir / "main_page_ext.h").exists()
        assert (project_dir / ".designer" / "dashboard_page.h").is_file()
        assert (project_dir / ".designer" / "dashboard_page_layout.c").is_file()
        assert (project_dir / "dashboard_page.c").is_file()
        assert (project_dir / "dashboard_page_ext.h").is_file()
        assert (project_dir / "dashboard_page.c").read_text(encoding="utf-8") == "/* rename me */\n"
        assert (project_dir / "dashboard_page_ext.h").read_text(encoding="utf-8") == "#define KEEP_MAIN_PAGE_EXT 1\n"
        reloaded = _load_project(project_dir)
        assert reloaded.startup_page == "dashboard_page"
        assert reloaded.get_page_by_name("dashboard_page") is not None
        assert reloaded.get_page_by_name("main_page") is None
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_save_project_files_rename_archives_old_user_files_when_target_exists(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "RenameConflictDemo"
        project = _create_project(project_dir, "RenameConflictDemo", sdk_root)

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window, "_load_project_app_local_widgets", lambda *args, **kwargs: None)

        _open_project_window(window, project, project_dir, sdk_root)
        window._save_project_files(str(project_dir))
        (project_dir / "main_page.c").write_text("/* old renamed source */\n", encoding="utf-8")
        (project_dir / "main_page_ext.h").write_text("#define OLD_MAIN_PAGE_EXT 1\n", encoding="utf-8")
        (project_dir / "dashboard_page.c").write_text("/* keep new source */\n", encoding="utf-8")
        (project_dir / "dashboard_page_ext.h").write_text("#define KEEP_DASHBOARD_EXT 1\n", encoding="utf-8")

        window._on_page_renamed("main_page", "dashboard_page")
        window._save_project_files(str(project_dir))

        archive_dir = project_dir / ".eguiproject" / "orphaned_user_code" / "main_page"
        assert not (project_dir / "main_page.c").exists()
        assert not (project_dir / "main_page_ext.h").exists()
        assert (project_dir / "dashboard_page.c").read_text(encoding="utf-8") == "/* keep new source */\n"
        assert (project_dir / "dashboard_page_ext.h").read_text(encoding="utf-8") == "#define KEEP_DASHBOARD_EXT 1\n"
        assert (archive_dir / "main_page.c").read_text(encoding="utf-8") == "/* old renamed source */\n"
        assert (archive_dir / "main_page_ext.h").read_text(encoding="utf-8") == "#define OLD_MAIN_PAGE_EXT 1\n"
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_new_project_can_be_created_without_sdk_root(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        parent_dir = tmp_path / "workspace"
        parent_dir.mkdir()

        class FakeDialog:
            Accepted = 1

            def __init__(self, *args, **kwargs):
                self.sdk_root = ""
                self.parent_dir = str(parent_dir)
                self.app_name = "NoSdkDemo"
                self.screen_width = 240
                self.screen_height = 320

            def exec_(self):
                return self.Accepted

        opened = {}
        window = MainWindow("")

        def fake_open_loaded_project(project, project_dir, preferred_sdk_root="", silent=False):
            opened["project"] = project
            opened["project_dir"] = project_dir
            opened["preferred_sdk_root"] = preferred_sdk_root
            opened["silent"] = silent

        monkeypatch.setattr("ui_designer.ui.main_window.NewProjectDialog", FakeDialog)
        monkeypatch.setattr(window, "_open_loaded_project", fake_open_loaded_project)

        window._new_project()

        project_dir = parent_dir / "NoSdkDemo"
        assert project_dir.is_dir()
        assert (project_dir / "NoSdkDemo.egui").is_file()
        assert (project_dir / "build.mk").is_file()
        assert opened["project"].sdk_root == ""
        assert opened["project_dir"] == os.path.normpath(os.path.abspath(project_dir))
        assert opened["preferred_sdk_root"] == ""
        assert "Created project: NoSdkDemo" in window.statusBar().currentMessage()
        _close_window(window)

    def test_new_project_preserves_editing_only_reason_in_created_status(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.ui.main_window import MainWindow

        class _PreviewIncompatibleCompiler:
            app_root_arg = "example"

            def __init__(self, app_dir):
                self.app_dir = str(app_dir)

            def can_build(self):
                return True

            def get_build_error(self):
                return ""

            def ensure_preview_build_available(self, force=False):
                return False

            def get_preview_build_error(self):
                return "make: *** No rule to make target 'main.exe'.  Stop."

            def set_screen_size(self, width, height):
                return None

            def is_preview_running(self):
                return False

            def is_exe_ready(self):
                return False

            def stop_exe(self):
                return None

            def cleanup(self):
                return None

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        parent_dir = tmp_path / "workspace"
        parent_dir.mkdir()

        class FakeDialog:
            Accepted = 1

            def __init__(self, *args, **kwargs):
                self.sdk_root = str(sdk_root)
                self.parent_dir = str(parent_dir)
                self.app_name = "CreatedEditingOnlyDemo"
                self.screen_width = 240
                self.screen_height = 320

            def exec_(self):
                return self.Accepted

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr("ui_designer.ui.main_window.NewProjectDialog", FakeDialog)
        monkeypatch.setattr(window, "_load_project_app_local_widgets", lambda *args, **kwargs: None)
        monkeypatch.setattr(
            window,
            "_recreate_compiler",
            lambda: setattr(
                window,
                "compiler",
                _PreviewIncompatibleCompiler(parent_dir / "CreatedEditingOnlyDemo"),
            ),
        )

        window._new_project()

        message = window.statusBar().currentMessage()
        assert "Created project: CreatedEditingOnlyDemo" in message
        assert "Editing-only mode: make: *** No rule to make target 'main.exe'.  Stop." in message
        assert "main.exe" in window._auto_compile_retry_block_reason
        _close_window(window)

    def test_new_project_uses_current_project_parent_as_default_parent_dir(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        workspace_dir = tmp_path / "workspace"
        project_dir = workspace_dir / "CurrentApp"
        project_dir.mkdir(parents=True)
        captured = {}

        class FakeDialog:
            Accepted = 1

            def __init__(self, parent=None, sdk_root="", default_parent_dir=""):
                captured["default_parent_dir"] = default_parent_dir

            def exec_(self):
                return 0

        window = MainWindow("")
        window._project_dir = str(project_dir)
        monkeypatch.setattr("ui_designer.ui.main_window.NewProjectDialog", FakeDialog)

        window._new_project()

        assert captured["default_parent_dir"] == os.path.normpath(os.path.abspath(workspace_dir))
        _close_window(window)

    def test_new_project_warns_when_target_directory_already_exists_even_if_empty(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        parent_dir = tmp_path / "workspace"
        target_dir = parent_dir / "ExistingDemo"
        target_dir.mkdir(parents=True)

        class FakeDialog:
            Accepted = 1

            def __init__(self, *args, **kwargs):
                self.sdk_root = str(sdk_root)
                self.parent_dir = str(parent_dir)
                self.app_name = "ExistingDemo"
                self.screen_width = 240
                self.screen_height = 320

            def exec_(self):
                return self.Accepted

        warnings = []
        window = MainWindow(str(sdk_root))
        monkeypatch.setattr("ui_designer.ui.main_window.NewProjectDialog", FakeDialog)
        monkeypatch.setattr("ui_designer.ui.main_window.QMessageBox.warning", lambda *args: warnings.append(args[1:]))
        monkeypatch.setattr(window, "_open_loaded_project", lambda *args, **kwargs: pytest.fail("_open_loaded_project should not be called"))

        window._new_project()

        assert warnings
        assert warnings[0][0] == "Directory Conflict"
        assert "already exists" in warnings[0][1]
        _close_window(window)

    def test_selection_feedback_status_mentions_locked_hidden_and_layout_managed_widget(self, qapp, isolated_config):
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")
        child = _build_test_page_only_with_widget(
            "main_page",
            "switch",
            root_widget_type="linearlayout",
            root_name="root",
            name="child",
        )
        child.designer_locked = True
        child.designer_hidden = True

        window._set_selection([child], primary=child, sync_tree=False, sync_preview=False)

        message = window.statusBar().currentMessage()
        assert "Selection note:" in message
        assert "child is locked" in message
        assert "hidden" in message
        assert "layout-managed by linearlayout" in message
        _close_window(window)

    def test_selection_feedback_status_summarizes_multi_selection_constraints(self, qapp, isolated_config):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")
        first = WidgetModel("switch", name="first")
        second = WidgetModel("switch", name="second")
        first.designer_locked = True
        second.designer_hidden = True
        _root = _build_test_page_root_with_widgets(
            "main_page",
            root_widget_type="linearlayout",
            root_name="root",
            widgets=[first, second],
        )

        window._set_selection([first, second], primary=second, sync_tree=False, sync_preview=False)

        message = window.statusBar().currentMessage()
        assert "Selection note: current selection includes" in message
        assert "1 locked widget" in message
        assert "1 hidden widget" in message
        assert "2 layout-managed widgets" in message
        _close_window(window)

    def test_selection_feedback_status_reports_isolated_structure_limit(self, qapp, isolated_config):
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")
        child = _build_test_page_only_with_widget(
            "main_page",
            "switch",
            root_name="root",
            name="child",
        )

        window._set_selection([child], primary=child, sync_tree=False, sync_preview=False)

        assert window.statusBar().currentMessage() == (
            "Selection note: select another sibling or target container to move this widget."
        )
        _close_window(window)

    @pytest.mark.skip(reason="removed quick-move history feature")
    def test_selection_feedback_status_mentions_repeat_move_target(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "SelectionRepeatMoveTargetDemo"
        target = WidgetModel("group", name="target")
        first = WidgetModel("switch", name="first")
        second = WidgetModel("button", name="second")
        project = _create_project_only_with_widgets(
            project_dir,
            "SelectionRepeatMoveTargetDemo",
            sdk_root,
            widgets=[target, first, second],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)

        _open_project_window(window, project, project_dir, sdk_root)
        window.widget_tree.remember_move_target_label("root_group / target (group)")
        window._set_selection([second], primary=second, sync_tree=True, sync_preview=False)

        assert window.statusBar().currentMessage() == "Selection note: Ctrl+Alt+I repeats move into target."
        _close_window(window)

    def test_delete_selection_blocks_locked_widgets(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "DeleteLockedDemo"
        locked = WidgetModel("switch", name="locked_widget")
        locked.designer_locked = True
        project, root = _create_project_and_root_with_widgets(
            project_dir,
            "DeleteLockedDemo",
            sdk_root,
            widgets=[locked],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)

        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([locked], primary=locked, sync_tree=False, sync_preview=False)

        deleted_count, skipped_locked = window._delete_selection()

        assert deleted_count == 0
        assert skipped_locked == 1
        assert locked in root.children
        assert window.statusBar().currentMessage() == "Cannot delete selection: 1 locked widget."
        _close_window(window)

    def test_delete_selection_skips_locked_widgets(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "DeleteMixedDemo"
        removable = WidgetModel("switch", name="removable")
        locked = WidgetModel("switch", name="locked_widget")
        locked.designer_locked = True
        project, root = _create_project_and_root_with_widgets(
            project_dir,
            "DeleteMixedDemo",
            sdk_root,
            widgets=[removable, locked],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)

        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([removable, locked], primary=removable, sync_tree=False, sync_preview=False)

        deleted_count, skipped_locked = window._delete_selection()

        assert deleted_count == 1
        assert skipped_locked == 1
        assert removable not in root.children
        assert locked in root.children
        assert window.statusBar().currentMessage() == "Deleted 1 widget(s); skipped 1 locked widget"
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_cut_selection_skips_locked_widgets(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "CutMixedDemo"
        removable = WidgetModel("switch", name="removable")
        locked = WidgetModel("switch", name="locked_widget")
        locked.designer_locked = True
        project, root = _create_project_and_root_with_widgets(
            project_dir,
            "CutMixedDemo",
            sdk_root,
            widgets=[removable, locked],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([removable, locked], primary=removable, sync_tree=False, sync_preview=False)

        window._cut_selection()

        assert removable not in root.children
        assert locked in root.children
        assert len(window._clipboard_payload["widgets"]) == 1
        assert window._clipboard_payload["widgets"][0]["name"] == "removable"
        assert window.statusBar().currentMessage() == "Cut 1 widget(s); skipped 1 locked widget"
        window._undo_manager.mark_all_saved()
        _close_window(window)

    @pytest.mark.skip(reason="removed quick-move history feature")
    def test_delete_selection_clears_removed_recent_move_targets(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "DeleteRecentMoveTargetDemo"
        target = WidgetModel("group", name="target")
        sibling = WidgetModel("label", name="sibling")
        project, root = _create_project_and_root_with_widgets(
            project_dir,
            "DeleteRecentMoveTargetDemo",
            sdk_root,
            widgets=[target, sibling],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)

        _open_project_window(window, project, project_dir, sdk_root)
        window.widget_tree.remember_move_target(target, "root_group / target (group)")
        window._set_selection([target], primary=target, sync_tree=True, sync_preview=False)

        deleted_count, skipped_locked, removed_targets = window._delete_selection()

        assert deleted_count == 1
        assert skipped_locked == 0
        assert removed_targets == 1
        assert target not in root.children
        assert window.widget_tree.recent_move_target_labels() == []
        assert window.statusBar().currentMessage() == "Deleted 1 widget(s); cleared 1 recent move target"
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_widget_tree_delete_skips_locked_widgets_and_updates_status(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "TreeDeleteMixedDemo"
        removable = WidgetModel("switch", name="removable")
        locked = WidgetModel("switch", name="locked_widget")
        locked.designer_locked = True
        project, root = _create_project_and_root_with_widgets(
            project_dir,
            "TreeDeleteMixedDemo",
            sdk_root,
            widgets=[removable, locked],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([removable, locked], primary=removable, sync_tree=True, sync_preview=False)

        window.widget_tree._on_delete_clicked()

        assert removable not in root.children
        assert locked in root.children
        assert window.statusBar().currentMessage() == "Deleted 1 widget(s); skipped 1 locked widget"
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_selection_sync_reveals_widget_tree_path(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "TreeRevealDemo"
        container = WidgetModel("group", name="container")
        nested = WidgetModel("group", name="nested")
        target = WidgetModel("switch", name="target")
        _add_widget_children(nested, [target])
        _add_widget_children(container, [nested])
        project = _create_project_only_with_widgets(
            project_dir,
            "TreeRevealDemo",
            sdk_root,
            widgets=[container],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        container_item = window.widget_tree._item_map[id(container)]
        nested_item = window.widget_tree._item_map[id(nested)]
        container_item.setExpanded(False)
        nested_item.setExpanded(False)

        window._set_selection([target], primary=target, sync_tree=True, sync_preview=False)

        assert container_item.isExpanded() is True
        assert nested_item.isExpanded() is True
        assert window.widget_tree._get_selected_widget() is target
        _close_window(window)

    def test_widget_tree_rebuild_preserves_manual_collapse_state(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "TreeCollapseStateDemo"
        container = WidgetModel("group", name="container")
        nested = WidgetModel("group", name="nested")
        target = WidgetModel("switch", name="target")
        _add_widget_children(nested, [target])
        _add_widget_children(container, [nested])
        project = _create_project_only_with_widgets(
            project_dir,
            "TreeCollapseStateDemo",
            sdk_root,
            widgets=[container],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._clear_selection(sync_tree=True, sync_preview=False)
        container_item = window.widget_tree._item_map[id(container)]
        nested_item = window.widget_tree._item_map[id(nested)]
        container_item.setExpanded(False)
        nested_item.setExpanded(False)

        window._on_property_changed()

        assert window.widget_tree._item_map[id(container)].isExpanded() is False
        assert window.widget_tree._item_map[id(nested)].isExpanded() is False
        _close_window(window)

    def test_widget_tree_filter_updates_status_bar(self):
        repo_root = Path(__file__).resolve().parents[4]
        script = textwrap.dedent(
            f"""
            import os
            import shutil
            import sys
            from pathlib import Path

            os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

            repo_root = Path({repr(str(repo_root))})
            sys.path.insert(0, str(repo_root / "scripts"))

            from PyQt5.QtWidgets import QApplication

            from ui_designer.model.widget_model import WidgetModel
            from ui_designer.tests.project_builders import build_saved_test_project_only_with_widgets
            from ui_designer.tests.ui.window_test_helpers import (
                disable_main_window_compile as _disable_window_compile,
                open_loaded_test_project as _open_project_window,
            )
            from ui_designer.ui.main_window import MainWindow
            from ui_designer.utils.runtime_temp import create_repo_temp_workspace


            def create_sdk_root(root: Path):
                (root / "src").mkdir(parents=True)
                (root / "porting" / "designer").mkdir(parents=True)
                (root / "Makefile").write_text("all:\\n", encoding="utf-8")


            class DisabledCompiler:
                def can_build(self):
                    return False

                def is_preview_running(self):
                    return False

                def stop_exe(self):
                    return None

                def cleanup(self):
                    return None

                def get_build_error(self):
                    return "preview disabled for test"

                def set_screen_size(self, width, height):
                    return None

                def is_exe_ready(self):
                    return False


            temp_root = create_repo_temp_workspace(repo_root, "ui_designer_filter_status_")
            app = QApplication.instance() or QApplication([])
            try:
                sdk_root = temp_root / "sdk"
                project_dir = temp_root / "TreeFilterStatusDemo"
                create_sdk_root(sdk_root)

                project = build_saved_test_project_only_with_widgets(
                    project_dir,
                    "TreeFilterStatusDemo",
                    sdk_root,
                    widgets=[
                        WidgetModel("label", name="field_label"),
                        WidgetModel("button", name="field_button"),
                    ],
                )

                window = MainWindow(str(sdk_root))
                _disable_window_compile(window, DisabledCompiler)

                _open_project_window(window, project, project_dir, sdk_root)

                window.widget_tree.filter_edit.setText("field")
                assert window.statusBar().currentMessage() == "Widget filter 'field': 2 matches."

                window.widget_tree._select_next_filter_match()
                assert window.statusBar().currentMessage() == "Widget filter 'field': 2 matches (1/2)."

                window.widget_tree._select_all_filter_matches()
                assert window.statusBar().currentMessage() == "Widget filter 'field': selected 2 matches."
                assert [widget.name for widget in window._selected_widgets()] == ["field_label", "field_button"]
                assert [widget.name for widget in window.preview_panel.selected_widgets()] == ["field_label", "field_button"]

                window.widget_tree.filter_edit.setText("")
                assert window.statusBar().currentMessage() == "Widget filter cleared."

                window._undo_manager.mark_all_saved()
                window.close()
                window.deleteLater()
                app.sendPostedEvents()
                app.processEvents()
            finally:
                shutil.rmtree(temp_root, ignore_errors=True)
            """
        )

        env = os.environ.copy()
        env.setdefault("QT_QPA_PLATFORM", "offscreen")
        result = subprocess.run(
            [sys.executable, "-c", script],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            timeout=60,
        )

        assert result.returncode == 0, f"stdout:\n{result.stdout}\n\nstderr:\n{result.stderr}"

    def test_widget_tree_select_actions_sync_main_window_selection(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "TreeSelectActionDemo"
        other = WidgetModel("label", name="other")
        container = WidgetModel("group", name="container")
        child_a = WidgetModel("switch", name="child_a")
        child_b = WidgetModel("button", name="child_b")
        _add_widget_children(container, [child_a, child_b])
        project = _create_project_only_with_widgets(
            project_dir,
            "TreeSelectActionDemo",
            sdk_root,
            widgets=[other, container],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)

        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([other], primary=other, sync_tree=True, sync_preview=True)

        menu = window.widget_tree._build_context_menu(container)
        select_menu = next(action.menu() for action in menu.actions() if action.text() == "Select")
        select_children_action = next(action for action in select_menu.actions() if action.text() == "Children")

        select_children_action.trigger()

        assert window._selection_state.primary is child_a
        assert window._selection_state.widgets == [child_a, child_b]
        assert window.widget_tree.selected_widgets() == [child_a, child_b]
        assert window.preview_panel.selected_widgets() == [child_a, child_b]
        assert window.statusBar().currentMessage() == "Selected 2 child widgets of container."

        menu.deleteLater()
        _close_window(window)

    def test_widget_tree_batch_rename_updates_status_and_selection(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "TreeBatchRenameDemo"
        existing = WidgetModel("label", name="field_1")
        first = WidgetModel("label", name="title")
        second = WidgetModel("switch", name="cta")
        project = _create_project_only_with_widgets(
            project_dir,
            "TreeBatchRenameDemo",
            sdk_root,
            widgets=[existing, first, second],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(
            "ui_designer.ui.widget_tree.QInputDialog.getText",
            lambda *args, **kwargs: ("field", True),
        )

        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([first, second], primary=first, sync_tree=True, sync_preview=False)

        window.widget_tree._on_rename_clicked()

        assert first.name == "field_2"
        assert second.name == "field_3"
        assert window.widget_tree.selected_widgets() == [first, second]
        assert window.widget_tree._get_selected_widget() is first
        assert window.statusBar().currentMessage() == "Renamed 2 widget(s) with prefix 'field'."
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_align_selection_reports_locked_constraint(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "AlignLockedDemo"
        first = WidgetModel("switch", name="first", x=10, y=10, width=40, height=20)
        second = WidgetModel("switch", name="second", x=60, y=20, width=40, height=20)
        second.designer_locked = True
        project = _create_project_only_with_widgets(
            project_dir,
            "AlignLockedDemo",
            sdk_root,
            widgets=[first, second],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([first, second], primary=first, sync_tree=False, sync_preview=False)

        window._align_selection("left")

        assert window.statusBar().currentMessage() == "Cannot align selection: locked widgets leave fewer than 2 editable widgets."
        _close_window(window)

    def test_align_selection_reports_layout_managed_constraint(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "AlignLayoutManagedDemo"
        layout_parent = WidgetModel("linearlayout", name="layout_parent", x=0, y=0, width=200, height=80)
        first = WidgetModel("switch", name="first", width=40, height=20)
        second = WidgetModel("switch", name="second", width=40, height=20)
        _add_widget_children(layout_parent, [first, second])
        project = _create_project_only_with_widgets(
            project_dir,
            "AlignLayoutManagedDemo",
            sdk_root,
            widgets=[layout_parent],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([first, second], primary=first, sync_tree=False, sync_preview=False)

        window._align_selection("left")

        assert window.statusBar().currentMessage() == (
            "Cannot align selection: selected widgets are layout-managed by the same "
            "linearlayout parent; reorder them instead."
        )
        _close_window(window)

    def test_group_selection_groups_widgets_and_updates_status(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "GroupSelectionDemo"
        first = WidgetModel("label", name="first", x=10, y=20, width=30, height=10)
        second = WidgetModel("button", name="second", x=60, y=40, width=20, height=20)
        project, root = _create_project_and_root_with_widgets(
            project_dir,
            "GroupSelectionDemo",
            sdk_root,
            widgets=[first, second],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([first, second], primary=first, sync_tree=False, sync_preview=False)

        window._group_selection()

        group = root.children[0]
        assert group.widget_type == "group"
        assert group.children == [first, second]
        assert window.widget_tree.selected_widgets() == [group]
        assert window.widget_tree._get_selected_widget() is group
        assert window._undo_manager.get_stack("main_page").current_label() == "group selection"
        assert window.statusBar().currentMessage() == "Grouped 2 widget(s) into group."
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_move_selection_into_container_uses_dialog_choice(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "MoveIntoDemo"
        target = WidgetModel("group", name="target_group", x=90, y=20, width=100, height=80)
        child = WidgetModel("switch", name="child", x=10, y=15, width=20, height=10)
        project = _create_project_only_with_widgets(
            project_dir,
            "MoveIntoDemo",
            sdk_root,
            widgets=[target, child],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(
            "ui_designer.ui.main_window.QInputDialog.getItem",
            lambda *args, **kwargs: ("root_group / target_group (group)", True),
        )

        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([child], primary=child, sync_tree=False, sync_preview=False)

        window._move_selection_into_container()

        assert child.parent is target
        assert (child.display_x, child.display_y) == (10, 15)
        assert window.widget_tree.selected_widgets() == [child]
        assert window.widget_tree._get_selected_widget() is child
        assert window._undo_manager.get_stack("main_page").current_label() == "move into container"
        assert window.statusBar().currentMessage() == "Moved 1 widget(s) into target_group."
        window._undo_manager.mark_all_saved()
        _close_window(window)

    @pytest.mark.skip(reason="removed quick-move history feature")
    def test_move_selection_into_container_dialog_prefers_remembered_target(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "RememberMoveIntoDemo"
        target_a = WidgetModel("group", name="target_a")
        target_b = WidgetModel("group", name="target_b")
        first = WidgetModel("label", name="first")
        second = WidgetModel("button", name="second")
        project = _create_project_only_with_widgets(
            project_dir,
            "RememberMoveIntoDemo",
            sdk_root,
            widgets=[target_a, target_b, first, second],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)

        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([first], primary=first, sync_tree=False, sync_preview=False)
        window._move_selection_into_target(
            target_b,
            target_label="root_group / target_b (group)",
        )

        window._set_selection([second], primary=second, sync_tree=False, sync_preview=False)
        captured = {}

        def _fake_get_item(*args, **kwargs):
            captured["prompt"] = args[2]
            captured["labels"] = list(args[3])
            captured["current_index"] = args[4]
            return "root_group / target_b (group)", True

        monkeypatch.setattr("ui_designer.ui.main_window.QInputDialog.getItem", _fake_get_item)

        window._move_selection_into_container()

        assert captured["labels"] == [
            "root_group / target_b (group)",
            "root_group / target_a (group)",
        ]
        assert captured["prompt"] == "Target container (recent targets first):"
        assert captured["current_index"] == 0
        assert second.parent is target_b
        window._undo_manager.mark_all_saved()
        _close_window(window)

    @pytest.mark.skip(reason="removed quick-move history feature")
    def test_move_selection_into_container_dialog_prioritizes_recent_target_history(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "DialogRecentMoveIntoDemo"
        target_a = WidgetModel("group", name="target_a")
        target_b = WidgetModel("group", name="target_b")
        target_c = WidgetModel("group", name="target_c")
        first = WidgetModel("label", name="first")
        second = WidgetModel("button", name="second")
        third = WidgetModel("switch", name="third")
        project = _create_project_only_with_widgets(
            project_dir,
            "DialogRecentMoveIntoDemo",
            sdk_root,
            widgets=[target_a, target_b, target_c, first, second, third],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)

        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([first], primary=first, sync_tree=False, sync_preview=False)
        window._move_selection_into_target(
            target_c,
            target_label="root_group / target_c (group)",
        )
        window._set_selection([second], primary=second, sync_tree=False, sync_preview=False)
        window._move_selection_into_target(
            target_b,
            target_label="root_group / target_b (group)",
        )

        window._set_selection([third], primary=third, sync_tree=False, sync_preview=False)
        captured = {}

        def _fake_get_item(*args, **kwargs):
            captured["labels"] = list(args[3])
            captured["current_index"] = args[4]
            return "root_group / target_b (group)", True

        monkeypatch.setattr("ui_designer.ui.main_window.QInputDialog.getItem", _fake_get_item)

        window._move_selection_into_container()

        assert captured["labels"] == [
            "root_group / target_b (group)",
            "root_group / target_c (group)",
            "root_group / target_a (group)",
        ]
        assert captured["current_index"] == 0
        window._undo_manager.mark_all_saved()
        _close_window(window)

    @pytest.mark.skip(reason="removed quick-move history feature")
    def test_structure_actions_follow_precise_selection_constraints(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "StructureActionStateDemo"
        first = WidgetModel("label", name="first")
        second = WidgetModel("button", name="second")
        target = WidgetModel("group", name="target_group")
        nested = WidgetModel("switch", name="nested")
        _add_widget_children(target, [nested])
        project = _create_project_only_with_widgets(
            project_dir,
            "StructureActionStateDemo",
            sdk_root,
            widgets=[first, second, target],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)

        _open_project_window(window, project, project_dir, sdk_root)

        window._set_selection([first, second], primary=first, sync_tree=False, sync_preview=False)

        assert window._group_selection_action.isEnabled() is True
        assert window._ungroup_selection_action.isEnabled() is False
        assert window._move_into_container_action.isEnabled() is True
        assert window._move_into_last_target_action.isEnabled() is False
        assert window._quick_move_into_menu.menuAction().isEnabled() is True
        assert window._lift_to_parent_action.isEnabled() is False
        assert window._move_up_action.isEnabled() is False
        assert window._move_down_action.isEnabled() is True
        assert window._move_top_action.isEnabled() is False
        assert window._move_bottom_action.isEnabled() is True
        assert "selection must only include groups" in window._ungroup_selection_action.toolTip()
        assert "move something into a container first" in window._move_into_last_target_action.toolTip()
        assert "selected widgets already belong to the top container" in window._lift_to_parent_action.statusTip()
        assert "selected widgets are already at the top" in window._move_up_action.toolTip()
        assert "selected widgets are already at the top" in window._move_top_action.statusTip()

        window._set_selection([second], primary=second, sync_tree=False, sync_preview=False)

        assert window._move_up_action.isEnabled() is True
        assert window._move_down_action.isEnabled() is True
        assert window._move_top_action.isEnabled() is True
        assert window._move_bottom_action.isEnabled() is True

        window._set_selection([nested], primary=nested, sync_tree=False, sync_preview=False)

        assert window._group_selection_action.isEnabled() is False
        assert window._ungroup_selection_action.isEnabled() is False
        assert window._move_into_container_action.isEnabled() is True
        assert window._lift_to_parent_action.isEnabled() is True
        assert window._move_up_action.isEnabled() is False
        assert window._move_down_action.isEnabled() is False
        assert window._move_top_action.isEnabled() is False
        assert window._move_bottom_action.isEnabled() is False

        _close_window(window)

    @pytest.mark.skip(reason="removed quick-move history feature")
    def test_structure_actions_disable_root_ungroup_and_noop_move_into(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "StructureActionDisabledDemo"
        first = WidgetModel("label", name="first")
        project, root = _create_project_and_root_with_widgets(
            project_dir,
            "StructureActionDisabledDemo",
            sdk_root,
            widgets=[first],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)

        window._selection_state.set_widgets([root], primary=root)
        window._selected_widget = root
        window._update_edit_actions()

        assert window._group_selection_action.isEnabled() is False
        assert window._ungroup_selection_action.isEnabled() is False
        assert window._move_into_container_action.isEnabled() is False
        assert window._move_into_last_target_action.isEnabled() is False
        assert window._quick_move_into_menu.menuAction().isEnabled() is False
        assert window._lift_to_parent_action.isEnabled() is False
        assert window._move_top_action.isEnabled() is False
        assert window._move_bottom_action.isEnabled() is False
        assert "root widgets cannot be regrouped or reordered" in window._group_selection_action.toolTip()
        assert "root widgets cannot be regrouped or reordered" in window._group_selection_action.statusTip()

        window._selection_state.set_widgets([first], primary=first)
        window._selected_widget = first
        window._update_edit_actions()

        assert window._group_selection_action.isEnabled() is False
        assert window._ungroup_selection_action.isEnabled() is False
        assert window._move_into_container_action.isEnabled() is False
        assert window._move_into_last_target_action.isEnabled() is False
        assert window._quick_move_into_menu.menuAction().isEnabled() is False
        assert window._lift_to_parent_action.isEnabled() is False
        assert window._move_up_action.isEnabled() is False
        assert window._move_down_action.isEnabled() is False
        assert window._move_top_action.isEnabled() is False
        assert window._move_bottom_action.isEnabled() is False
        assert "select at least 2 widgets" in window._group_selection_action.toolTip()
        assert "selection must only include groups" in window._ungroup_selection_action.statusTip()
        assert "no eligible target containers are available" in window._move_into_container_action.toolTip()
        assert "no eligible target containers are available" in window._move_into_container_action.statusTip()
        assert "selected widgets already belong to the top container" in window._lift_to_parent_action.toolTip()

        _close_window(window)

    @pytest.mark.skip(reason="removed quick-move history feature")
    def test_quick_move_into_menu_moves_selection_into_target(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "QuickMoveIntoDemo"
        target = WidgetModel("group", name="target_group", x=90, y=20, width=100, height=80)
        child = WidgetModel("switch", name="child", x=10, y=15, width=20, height=10)
        project = _create_project_only_with_widgets(
            project_dir,
            "QuickMoveIntoDemo",
            sdk_root,
            widgets=[target, child],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)

        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([child], primary=child, sync_tree=True, sync_preview=False)
        window._refresh_quick_move_into_menu()

        quick_action = next(action for action in window._quick_move_into_menu.actions() if action.text() == "root_group / target_group (group)")
        quick_action.trigger()

        assert child.parent is target
        assert (child.display_x, child.display_y) == (10, 15)
        assert window.widget_tree.selected_widgets() == [child]
        assert window.widget_tree._get_selected_widget() is child
        assert window._undo_manager.get_stack("main_page").current_label() == "move into container"
        assert window.statusBar().currentMessage() == "Moved 1 widget(s) into target_group."
        window._undo_manager.mark_all_saved()
        _close_window(window)

    @pytest.mark.skip(reason="removed quick-move history feature")
    def test_move_into_last_target_action_reuses_remembered_target(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "RepeatMoveIntoDemo"
        target_a = WidgetModel("group", name="target_a")
        target_b = WidgetModel("group", name="target_b")
        first = WidgetModel("label", name="first")
        second = WidgetModel("button", name="second")
        project = _create_project_only_with_widgets(
            project_dir,
            "RepeatMoveIntoDemo",
            sdk_root,
            widgets=[target_a, target_b, first, second],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)

        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([first], primary=first, sync_tree=True, sync_preview=False)
        window._move_selection_into_target(
            target_b,
            target_label="root_group / target_b (group)",
        )

        window._set_selection([second], primary=second, sync_tree=True, sync_preview=False)

        assert window._move_into_last_target_action.isEnabled() is True
        assert "root_group / target_b (group)" in window._move_into_last_target_action.toolTip()

        window._move_into_last_target_action.trigger()

        assert second.parent is target_b
        assert window.widget_tree.selected_widgets() == [second]
        assert window.widget_tree._get_selected_widget() is second
        assert window._undo_manager.get_stack("main_page").current_label() == "move into container"
        assert window.statusBar().currentMessage() == "Moved 1 widget(s) into target_b."
        window._undo_manager.mark_all_saved()
        _close_window(window)

    @pytest.mark.skip(reason="removed quick-move history feature")
    def test_clear_move_target_history_action_clears_recent_targets(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "ClearMoveTargetHistoryDemo"
        target = WidgetModel("group", name="target")
        first = WidgetModel("label", name="first")
        second = WidgetModel("button", name="second")
        project = _create_project_only_with_widgets(
            project_dir,
            "ClearMoveTargetHistoryDemo",
            sdk_root,
            widgets=[target, first, second],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)

        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([first], primary=first, sync_tree=True, sync_preview=False)
        window._move_selection_into_target(
            target,
            target_label="root_group / target (group)",
        )

        window._set_selection([second], primary=second, sync_tree=True, sync_preview=False)

        assert window._clear_move_target_history_action.isEnabled() is True
        assert "Forget 1 recent move-into target" in window._clear_move_target_history_action.toolTip()

        window._clear_move_target_history_action.trigger()

        assert window.widget_tree.recent_move_target_labels() == []
        assert window._clear_move_target_history_action.isEnabled() is False
        assert window._move_into_last_target_action.isEnabled() is False
        assert window.statusBar().currentMessage() == "Cleared 1 recent move target."
        assert "no recent move targets are saved" in window._clear_move_target_history_action.toolTip()

        window._undo_manager.mark_all_saved()
        _close_window(window)

    @pytest.mark.skip(reason="removed quick-move history feature")
    def test_clear_move_target_history_reports_plural_count(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "ClearMoveHistoryCountDemo"
        target_a = WidgetModel("group", name="target_a")
        target_b = WidgetModel("group", name="target_b")
        first = WidgetModel("label", name="first")
        second = WidgetModel("button", name="second")
        third = WidgetModel("switch", name="third")
        project = _create_project_only_with_widgets(
            project_dir,
            "ClearMoveHistoryCountDemo",
            sdk_root,
            widgets=[target_a, target_b, first, second, third],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)

        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([first], primary=first, sync_tree=True, sync_preview=False)
        window._move_selection_into_target(
            target_a,
            target_label="root_group / target_a (group)",
        )
        window._set_selection([second], primary=second, sync_tree=True, sync_preview=False)
        window._move_selection_into_target(
            target_b,
            target_label="root_group / target_b (group)",
        )
        window._set_selection([third], primary=third, sync_tree=True, sync_preview=False)

        window._clear_move_target_history_action.trigger()

        assert window.widget_tree.recent_move_target_labels() == []
        assert window.statusBar().currentMessage() == "Cleared 2 recent move targets."
        window._undo_manager.mark_all_saved()
        _close_window(window)

    @pytest.mark.skip(reason="removed quick-move history feature")
    def test_move_into_last_target_is_scoped_per_page(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PerPageMoveIntoDemo"
        main_target = WidgetModel("group", name="main_target")
        main_first = WidgetModel("label", name="main_first")
        main_second = WidgetModel("button", name="main_second")
        detail_target = WidgetModel("group", name="detail_target")
        detail_first = WidgetModel("label", name="detail_first")
        detail_second = WidgetModel("button", name="detail_second")
        project = _create_project_only_with_page_widgets(
            project_dir,
            "PerPageMoveIntoDemo",
            sdk_root,
            page_widgets={
                "main_page": [main_target, main_first, main_second],
                "detail_page": [detail_target, detail_first, detail_second],
            },
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)

        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([main_first], primary=main_first, sync_tree=True, sync_preview=False)
        window._move_selection_into_target(
            main_target,
            target_label="root_group / main_target (group)",
        )

        window._switch_page("detail_page")
        window._set_selection([detail_first], primary=detail_first, sync_tree=True, sync_preview=False)
        window._move_selection_into_target(
            detail_target,
            target_label="root_group / detail_target (group)",
        )

        window._switch_page("main_page")
        window._set_selection([main_second], primary=main_second, sync_tree=True, sync_preview=False)

        assert window.widget_tree.remembered_move_target_label() == "root_group / main_target (group)"
        assert "root_group / main_target (group)" in window._move_into_last_target_action.toolTip()
        assert "detail_target" not in window._move_into_last_target_action.toolTip()

        window._move_into_last_target_action.trigger()
        assert main_second.parent is main_target

        window._switch_page("detail_page")
        window._set_selection([detail_second], primary=detail_second, sync_tree=True, sync_preview=False)

        assert window.widget_tree.remembered_move_target_label() == "root_group / detail_target (group)"
        assert "root_group / detail_target (group)" in window._move_into_last_target_action.toolTip()

        window._move_into_last_target_action.trigger()
        assert detail_second.parent is detail_target

        window._undo_manager.mark_all_saved()
        _close_window(window)

    @pytest.mark.skip(reason="removed quick-move history feature")
    def test_repeat_move_target_hint_follows_target_rename(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "RepeatMoveTargetRenameDemo"
        target = WidgetModel("group", name="target")
        first = WidgetModel("label", name="first")
        second = WidgetModel("button", name="second")
        project = _create_project_only_with_widgets(
            project_dir,
            "RepeatMoveTargetRenameDemo",
            sdk_root,
            widgets=[target, first, second],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)

        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([first], primary=first, sync_tree=True, sync_preview=False)
        window._move_selection_into_target(
            target,
            target_label="root_group / target (group)",
        )

        target.name = "renamed_target"
        window.widget_tree.rebuild_tree()
        window._set_selection([second], primary=second, sync_tree=True, sync_preview=False)

        assert window.widget_tree.remembered_move_target_label() == "root_group / renamed_target (group)"
        assert "root_group / renamed_target (group)" in window._move_into_last_target_action.toolTip()
        assert window.statusBar().currentMessage() == "Selection note: Ctrl+Alt+I repeats move into renamed_target."

        window._undo_manager.mark_all_saved()
        _close_window(window)

    @pytest.mark.skip(reason="removed quick-move history feature")
    def test_quick_move_into_menu_prioritizes_remembered_target(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "RememberQuickMoveIntoDemo"
        target_a = WidgetModel("group", name="target_a")
        target_b = WidgetModel("group", name="target_b")
        first = WidgetModel("label", name="first")
        second = WidgetModel("button", name="second")
        project = _create_project_only_with_widgets(
            project_dir,
            "RememberQuickMoveIntoDemo",
            sdk_root,
            widgets=[target_a, target_b, first, second],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)

        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([first], primary=first, sync_tree=True, sync_preview=False)
        window._move_selection_into_target(
            target_b,
            target_label="root_group / target_b (group)",
        )

        window._set_selection([second], primary=second, sync_tree=True, sync_preview=False)
        window._refresh_quick_move_into_menu()

        labels = _menu_target_labels(window._quick_move_into_menu)
        assert labels[:2] == [
            "root_group / target_b (group)",
            "root_group / target_a (group)",
        ]
        assert "Recent Targets" in [action.text() for action in window._quick_move_into_menu.actions()]
        assert "Other Targets" in [action.text() for action in window._quick_move_into_menu.actions()]

        window._undo_manager.mark_all_saved()
        _close_window(window)

    @pytest.mark.skip(reason="removed quick-move history feature")
    def test_quick_move_into_menu_follows_recent_target_history(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "RecentQuickMoveIntoDemo"
        target_a = WidgetModel("group", name="target_a")
        target_b = WidgetModel("group", name="target_b")
        target_c = WidgetModel("group", name="target_c")
        first = WidgetModel("label", name="first")
        second = WidgetModel("button", name="second")
        third = WidgetModel("switch", name="third")
        project = _create_project_only_with_widgets(
            project_dir,
            "RecentQuickMoveIntoDemo",
            sdk_root,
            widgets=[target_a, target_b, target_c, first, second, third],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)

        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([first], primary=first, sync_tree=True, sync_preview=False)
        window._move_selection_into_target(
            target_c,
            target_label="root_group / target_c (group)",
        )

        window._set_selection([second], primary=second, sync_tree=True, sync_preview=False)
        window._move_selection_into_target(
            target_b,
            target_label="root_group / target_b (group)",
        )

        window._set_selection([third], primary=third, sync_tree=True, sync_preview=False)
        window._refresh_quick_move_into_menu()

        labels = _menu_target_labels(window._quick_move_into_menu)
        assert labels[:3] == [
            "root_group / target_b (group)",
            "root_group / target_c (group)",
            "root_group / target_a (group)",
        ]

        window._undo_manager.mark_all_saved()
        _close_window(window)

    @pytest.mark.skip(reason="removed quick-move history feature")
    def test_quick_move_into_menu_shows_recent_placeholder_without_history(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "QuickMovePlaceholderDemo"
        target = WidgetModel("group", name="target")
        child = WidgetModel("label", name="child")
        project = _create_project_only_with_widgets(
            project_dir,
            "QuickMovePlaceholderDemo",
            sdk_root,
            widgets=[target, child],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)

        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([child], primary=child, sync_tree=False, sync_preview=False)
        window._refresh_quick_move_into_menu()

        action_texts = [action.text() for action in window._quick_move_into_menu.actions()]
        assert "Recent Targets" in action_texts
        assert "Other Targets" in action_texts
        assert "History" in action_texts
        recent_placeholder = next(action for action in window._quick_move_into_menu.actions() if action.text() == "(No recent targets yet)")
        repeat_action = next(action for action in window._quick_move_into_menu.actions() if action.text() == "Move Into Last Target")
        clear_action = next(action for action in window._quick_move_into_menu.actions() if action.text() == "Clear Move Target History")
        assert recent_placeholder.isEnabled() is False
        assert repeat_action.isEnabled() is False
        assert clear_action.isEnabled() is False
        assert _menu_target_labels(window._quick_move_into_menu) == ["root_group / target (group)"]

        window._undo_manager.mark_all_saved()
        _close_window(window)

    @pytest.mark.skip(reason="removed quick-move history feature")
    def test_quick_move_into_menu_reuses_last_target_and_clears_history(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "QuickMoveHistoryMenuDemo"
        target = WidgetModel("group", name="target")
        first = WidgetModel("label", name="first")
        second = WidgetModel("button", name="second")
        project = _create_project_only_with_widgets(
            project_dir,
            "QuickMoveHistoryMenuDemo",
            sdk_root,
            widgets=[target, first, second],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)

        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([first], primary=first, sync_tree=True, sync_preview=False)
        window._move_selection_into_target(
            target,
            target_label="root_group / target (group)",
        )

        window._set_selection([second], primary=second, sync_tree=True, sync_preview=False)
        window._refresh_quick_move_into_menu()

        action_texts = [action.text() for action in window._quick_move_into_menu.actions()]
        assert "History" in action_texts
        repeat_action = next(action for action in window._quick_move_into_menu.actions() if action.text() == "Move Into Last Target")
        clear_action = next(action for action in window._quick_move_into_menu.actions() if action.text() == "Clear Move Target History")
        assert repeat_action.isEnabled() is True
        assert clear_action.isEnabled() is True
        assert "root_group / target (group)" in repeat_action.toolTip()

        repeat_action.trigger()

        assert second.parent is target
        assert window.widget_tree.selected_widgets() == [second]
        assert window.widget_tree._get_selected_widget() is second

        window._refresh_quick_move_into_menu()
        clear_action = next(action for action in window._quick_move_into_menu.actions() if action.text() == "Clear Move Target History")
        clear_action.trigger()

        assert window.widget_tree.recent_move_target_labels() == []
        assert window.statusBar().currentMessage() == "Cleared 1 recent move target."
        window._undo_manager.mark_all_saved()
        _close_window(window)

    @pytest.mark.skip(reason="removed quick-move history feature")
    def test_quick_move_into_menu_stays_available_for_history_only(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "QuickMoveHistoryOnlyDemo"
        target = WidgetModel("group", name="target")
        child = WidgetModel("label", name="child")
        project = _create_project_only_with_widgets(
            project_dir,
            "QuickMoveHistoryOnlyDemo",
            sdk_root,
            widgets=[target, child],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)

        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([child], primary=child, sync_tree=True, sync_preview=False)
        window._move_selection_into_target(
            target,
            target_label="root_group / target (group)",
        )

        window._set_selection([target], primary=target, sync_tree=True, sync_preview=False)
        window._refresh_quick_move_into_menu()

        assert window._move_into_container_action.isEnabled() is False
        assert window._move_into_last_target_action.isEnabled() is False
        assert window._clear_move_target_history_action.isEnabled() is True
        assert window._quick_move_into_menu.menuAction().isEnabled() is True

        action_texts = [action.text() for action in window._quick_move_into_menu.actions()]
        assert "(No eligible target containers)" in action_texts
        assert "History" in action_texts
        repeat_action = next(action for action in window._quick_move_into_menu.actions() if action.text() == "Move Into Last Target")
        clear_action = next(action for action in window._quick_move_into_menu.actions() if action.text() == "Clear Move Target History")
        assert repeat_action.isEnabled() is False
        assert clear_action.isEnabled() is True

        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_widget_tree_group_selection_updates_main_window_selection(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "TreeGroupSelectionDemo"
        first = WidgetModel("label", name="first", x=10, y=20, width=30, height=10)
        second = WidgetModel("button", name="second", x=60, y=40, width=20, height=20)
        project, root = _create_project_and_root_with_widgets(
            project_dir,
            "TreeGroupSelectionDemo",
            sdk_root,
            widgets=[first, second],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([first, second], primary=first, sync_tree=True, sync_preview=False)

        window.widget_tree._group_selected_widgets()

        group = root.children[0]
        assert window._primary_selected_widget() is group
        assert window.preview_panel.selected_widgets() == [group]
        assert window._undo_manager.get_stack("main_page").current_label() == "group selection"
        assert window.statusBar().currentMessage() == "Grouped 2 widget(s) into group."
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_widget_tree_drop_move_updates_main_window_selection_and_history(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "TreeDropMoveDemo"
        first = WidgetModel("label", name="first")
        second = WidgetModel("label", name="second")
        third = WidgetModel("label", name="third")
        project, root = _create_project_and_root_with_widgets(
            project_dir,
            "TreeDropMoveDemo",
            sdk_root,
            widgets=[first, second, third],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)

        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([first], primary=first, sync_tree=True, sync_preview=False)

        moved = window.widget_tree._move_selected_widgets_by_tree_drop(third, QAbstractItemView.BelowItem)

        assert moved is True
        assert [widget.name for widget in root.children] == ["second", "third", "first"]
        assert window._primary_selected_widget() is first
        assert window.preview_panel.selected_widgets() == [first]
        assert window._undo_manager.get_stack("main_page").current_label() == "tree move"
        assert window.statusBar().currentMessage() == "Moved 1 widget(s) in the widget tree."
        window._undo_manager.mark_all_saved()
        _close_window(window)

    @pytest.mark.skip(reason="removed quick-move history feature")
    def test_structure_actions_expose_keyboard_shortcuts(self, qapp):
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")

        assert window._group_selection_action.shortcut().toString() == "Ctrl+G"
        assert window._ungroup_selection_action.shortcut().toString() == "Ctrl+Shift+G"
        assert window._move_into_container_action.shortcut().toString() == "Ctrl+Shift+I"
        assert window._move_into_last_target_action.shortcut().toString() == "Ctrl+Alt+I"
        assert window._lift_to_parent_action.shortcut().toString() == "Ctrl+Shift+L"
        assert window._move_up_action.shortcut().toString() == "Alt+Up"
        assert window._move_down_action.shortcut().toString() == "Alt+Down"
        assert window._move_top_action.shortcut().toString() == "Alt+Shift+Up"
        assert window._move_bottom_action.shortcut().toString() == "Alt+Shift+Down"

        _close_window(window)

    def test_move_selection_to_edge_updates_status_and_history(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "MoveToEdgeDemo"
        first = WidgetModel("label", name="first")
        second = WidgetModel("label", name="second")
        third = WidgetModel("label", name="third")
        project, root = _create_project_and_root_with_widgets(
            project_dir,
            "MoveToEdgeDemo",
            sdk_root,
            widgets=[first, second, third],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)

        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([second], primary=second, sync_tree=True, sync_preview=False)

        window._move_selection_to_bottom()

        assert [widget.name for widget in root.children] == ["first", "third", "second"]
        assert window._primary_selected_widget() is second
        assert window._undo_manager.get_stack("main_page").current_label() == "move to bottom"
        assert window.statusBar().currentMessage() == "Moved 1 widget(s) to the bottom."

        window._move_selection_to_top()

        assert [widget.name for widget in root.children] == ["second", "first", "third"]
        assert window._primary_selected_widget() is second
        assert window._undo_manager.get_stack("main_page").current_label() == "move to top"
        assert window.statusBar().currentMessage() == "Moved 1 widget(s) to the top."
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_widget_tree_invalid_drop_updates_status_bar(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "TreeInvalidDropDemo"
        first = WidgetModel("label", name="first")
        project = _create_project_only_with_widgets(
            project_dir,
            "TreeInvalidDropDemo",
            sdk_root,
            widgets=[first],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)

        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([first], primary=first, sync_tree=True, sync_preview=False)

        moved = window.widget_tree._move_selected_widgets_by_tree_drop(first, QAbstractItemView.AboveItem)

        assert moved is False
        assert window.statusBar().currentMessage() == "Cannot move selection in tree: widgets are already in that position."
        _close_window(window)

    def test_distribute_selection_reports_mixed_parent_constraint(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "DistributeParentDemo"
        group_a = WidgetModel("group", name="group_a", x=0, y=0, width=120, height=120)
        group_b = WidgetModel("group", name="group_b", x=130, y=0, width=120, height=120)
        first = WidgetModel("switch", name="first", x=10, y=10, width=20, height=20)
        second = WidgetModel("switch", name="second", x=40, y=10, width=20, height=20)
        third = WidgetModel("switch", name="third", x=10, y=10, width=20, height=20)
        _add_widget_children(group_a, [first, second])
        _add_widget_children(group_b, [third])
        project = _create_project_only_with_widgets(
            project_dir,
            "DistributeParentDemo",
            sdk_root,
            widgets=[group_a, group_b],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([first, second, third], primary=first, sync_tree=False, sync_preview=False)

        window._distribute_selection("horizontal")

        assert window.statusBar().currentMessage() == "Cannot distribute selection: selected widgets do not share the same free-position parent."
        _close_window(window)

    def test_distribute_selection_reports_layout_managed_constraint(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "DistributeLayoutManagedDemo"
        layout_parent = WidgetModel("linearlayout", name="layout_parent", x=0, y=0, width=200, height=120)
        first = WidgetModel("switch", name="first", width=20, height=20)
        second = WidgetModel("switch", name="second", width=20, height=20)
        third = WidgetModel("switch", name="third", width=20, height=20)
        _add_widget_children(layout_parent, [first, second, third])
        project = _create_project_only_with_widgets(
            project_dir,
            "DistributeLayoutManagedDemo",
            sdk_root,
            widgets=[layout_parent],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([first, second, third], primary=first, sync_tree=False, sync_preview=False)

        window._distribute_selection("horizontal")

        assert window.statusBar().currentMessage() == (
            "Cannot distribute selection: selected widgets are layout-managed by the same "
            "linearlayout parent; reorder them instead."
        )
        _close_window(window)

    def test_move_selection_to_front_reports_all_locked(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "FrontLockedDemo"
        locked = WidgetModel("switch", name="locked_widget")
        locked.designer_locked = True
        project = _create_project_only_with_widgets(
            project_dir,
            "FrontLockedDemo",
            sdk_root,
            widgets=[locked],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([locked], primary=locked, sync_tree=False, sync_preview=False)

        window._move_selection_to_front()

        assert window.statusBar().currentMessage() == "Cannot bring to front: all selected widgets are locked."
        _close_window(window)

    def test_move_selection_to_back_reports_all_locked(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "BackLockedDemo"
        locked = WidgetModel("switch", name="locked_widget")
        locked.designer_locked = True
        project = _create_project_only_with_widgets(
            project_dir,
            "BackLockedDemo",
            sdk_root,
            widgets=[locked],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([locked], primary=locked, sync_tree=False, sync_preview=False)

        window._move_selection_to_back()

        assert window.statusBar().currentMessage() == "Cannot send to back: all selected widgets are locked."
        _close_window(window)

    def test_property_edit_status_mentions_dirty_source(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PropertyStatusDemo"
        widget = WidgetModel("switch", name="toggle")
        project = _create_project_only_with_widgets(
            project_dir,
            "PropertyStatusDemo",
            sdk_root,
            widgets=[widget],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([widget], primary=widget, sync_tree=False, sync_preview=False)
        widget.properties["is_checked"] = True

        window._on_property_changed()

        assert window.statusBar().currentMessage() == "Changed main_page: property edit."
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_canvas_move_status_mentions_dirty_source(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "CanvasMoveStatusDemo"
        widget = WidgetModel("switch", name="toggle", x=10, y=10, width=50, height=24)
        project = _create_project_only_with_widgets(
            project_dir,
            "CanvasMoveStatusDemo",
            sdk_root,
            widgets=[widget],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([widget], primary=widget, sync_tree=False, sync_preview=False)
        widget.x = 20
        widget.display_x = 20

        window._on_widget_moved(widget, 20, 10)

        assert window.statusBar().currentMessage() == "Changed main_page: canvas move."
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_canvas_move_defers_full_refresh_until_drag_finishes(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "CanvasMovePerfDemo"
        widget = WidgetModel("switch", name="toggle", x=10, y=10, width=50, height=24)
        project = _create_project_only_with_widgets(
            project_dir,
            "CanvasMovePerfDemo",
            sdk_root,
            widgets=[widget],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        calls = {
            "property_panel_refresh_live_geometry": 0,
            "update_preview_overlay": 0,
            "sync_xml_to_editors": 0,
            "update_resource_usage_panel": 0,
            "trigger_compile": 0,
        }

        monkeypatch.setattr(
            window.property_panel,
            "refresh_live_geometry",
            lambda *args, **kwargs: calls.__setitem__(
                "property_panel_refresh_live_geometry",
                calls["property_panel_refresh_live_geometry"] + 1,
            ) or True,
        )
        monkeypatch.setattr(
            window,
            "_update_preview_overlay",
            lambda: calls.__setitem__("update_preview_overlay", calls["update_preview_overlay"] + 1),
        )
        monkeypatch.setattr(
            window,
            "_sync_xml_to_editors",
            lambda: calls.__setitem__("sync_xml_to_editors", calls["sync_xml_to_editors"] + 1),
        )
        monkeypatch.setattr(
            window,
            "_update_resource_usage_panel",
            lambda: calls.__setitem__(
                "update_resource_usage_panel",
                calls["update_resource_usage_panel"] + 1,
            ),
        )
        monkeypatch.setattr(
            window,
            "_trigger_compile",
            lambda *args, **kwargs: calls.__setitem__("trigger_compile", calls["trigger_compile"] + 1),
        )

        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([widget], primary=widget, sync_tree=False, sync_preview=False)
        for key in calls:
            calls[key] = 0
        window._on_drag_started()
        widget.x = 20
        widget.display_x = 20

        window._on_widget_moved(widget, 20, 10)

        assert calls == {
            "property_panel_refresh_live_geometry": 1,
            "update_preview_overlay": 0,
            "sync_xml_to_editors": 0,
            "update_resource_usage_panel": 0,
            "trigger_compile": 0,
        }

        window._on_drag_finished()

        assert calls == {
            "property_panel_refresh_live_geometry": 2,
            "update_preview_overlay": 1,
            "sync_xml_to_editors": 1,
            "update_resource_usage_panel": 1,
            "trigger_compile": 1,
        }
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_canvas_move_throttles_live_geometry_refresh_during_drag(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui import main_window as main_window_module
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "CanvasMoveThrottleDemo"
        widget = WidgetModel("switch", name="toggle", x=10, y=10, width=50, height=24)
        project = _create_project_only_with_widgets(
            project_dir,
            "CanvasMoveThrottleDemo",
            sdk_root,
            widgets=[widget],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        calls = {"property_panel_refresh_live_geometry": 0}
        monkeypatch.setattr(
            window.property_panel,
            "refresh_live_geometry",
            lambda *args, **kwargs: calls.__setitem__(
                "property_panel_refresh_live_geometry",
                calls["property_panel_refresh_live_geometry"] + 1,
            ) or True,
        )
        tick_values = iter([0.0, 0.01, 0.02, 0.06])
        monkeypatch.setattr(main_window_module.time, "monotonic", lambda: next(tick_values))

        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([widget], primary=widget, sync_tree=False, sync_preview=False)
        calls["property_panel_refresh_live_geometry"] = 0
        window._on_drag_started()

        window._on_widget_moved(widget, 11, 10)
        window._on_widget_moved(widget, 12, 10)
        window._on_widget_moved(widget, 13, 10)

        assert calls["property_panel_refresh_live_geometry"] == 2
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_new_project_prefers_recovered_cached_sdk_for_defaults(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        cached_sdk = tmp_path / "config" / "sdk" / "EmbeddedGUI"
        _create_sdk_root(cached_sdk)
        isolated_config.sdk_root = str(tmp_path / "missing_sdk")
        isolated_config.sdk_root = str(tmp_path / "missing_sdk")
        captured = {}

        class FakeDialog:
            Accepted = 1

            def __init__(self, parent=None, sdk_root="", default_parent_dir=""):
                captured["sdk_root"] = sdk_root
                captured["default_parent_dir"] = default_parent_dir

            def exec_(self):
                return 0

        window = MainWindow("")
        monkeypatch.setattr("ui_designer.ui.main_window.default_sdk_install_dir", lambda: str(cached_sdk))
        monkeypatch.setattr("ui_designer.ui.main_window.NewProjectDialog", FakeDialog)

        window._new_project()

        assert captured["sdk_root"] == os.path.normpath(os.path.abspath(cached_sdk))
        assert captured["default_parent_dir"] == window._default_new_project_parent_dir(captured["sdk_root"])
        _close_window(window)

    def test_save_project_as_copies_sidecar_files_and_updates_project_dir(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        src_dir = tmp_path / "SrcDemo"
        dst_dir = tmp_path / "DstDemo"
        project = _create_project(src_dir, "SaveAsDemo", sdk_root)

        feature_dir = src_dir / "feature"
        feature_dir.mkdir(parents=True, exist_ok=True)
        (src_dir / "build.mk").write_text(
            "# custom build\nEGUI_CODE_SRC += feature\nEGUI_CODE_INCLUDE += feature\n",
            encoding="utf-8",
        )
        (src_dir / "app_egui_config.h").write_text("#define CUSTOM_CFG 1\n", encoding="utf-8")
        images_dir = src_dir / ".eguiproject" / "resources" / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        (images_dir / "legacy.png").write_bytes(b"PNG")
        (images_dir / "_generated_text_preview.png").write_bytes(b"BAD")
        resource_root = src_dir / ".eguiproject" / "resources"
        (resource_root / "_generated_text_demo_16_4.txt").write_text("designer\n", encoding="utf-8")
        resource_src_dir = src_dir / "resource" / "src"
        resource_src_dir.mkdir(parents=True, exist_ok=True)
        (resource_src_dir / "app_resource_config.json").write_text(
            json.dumps({"img": [{"file": "legacy.png"}], "font": []}, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        extra_resource_dir = resource_src_dir / "custom_assets"
        extra_resource_dir.mkdir(parents=True, exist_ok=True)
        (extra_resource_dir / "hero.png").write_bytes(b"HERO")
        mockup_dir = src_dir / ".eguiproject" / "mockup"
        mockup_dir.mkdir(parents=True, exist_ok=True)
        (mockup_dir / "legacy.txt").write_text("mock", encoding="utf-8")
        reference_frames_dir = src_dir / ".eguiproject" / "reference_frames"
        reference_frames_dir.mkdir(parents=True, exist_ok=True)
        (reference_frames_dir / "frame_000.png").write_bytes(b"REF")
        orphaned_dir = src_dir / ".eguiproject" / "orphaned_user_code" / "main_page"
        orphaned_dir.mkdir(parents=True, exist_ok=True)
        (orphaned_dir / "main_page.c").write_text("// orphan\n", encoding="utf-8")
        (src_dir / ".eguiproject" / "release.json").write_text('{"profiles":["pc"]}\n', encoding="utf-8")
        (src_dir / ".eguiproject" / "regression_report.html").write_text("<html>generated</html>\n", encoding="utf-8")
        (src_dir / ".eguiproject" / "regression_results.json").write_text('{"passed":1}\n', encoding="utf-8")
        (src_dir / "main_page.c").write_text("/* keep page source */\n", encoding="utf-8")
        (src_dir / "main_page_ext.h").write_text("#define KEEP_MAIN_EXT 1\n", encoding="utf-8")
        (src_dir / "legacy_logic.h").write_text("#define KEEP_LOGIC 1\n", encoding="utf-8")
        (feature_dir / "helper.c").write_text("int helper(void) { return 1; }\n", encoding="utf-8")
        (feature_dir / "helper.h").write_text("#define FEATURE_HELPER 1\n", encoding="utf-8")
        (src_dir / ".designer").mkdir(parents=True, exist_ok=True)
        (src_dir / ".designer" / "main_page.h").write_text("// designer page header\n", encoding="utf-8")
        (src_dir / "main_page.h").write_text("// stale legacy page header\n", encoding="utf-8")
        widgets_dir = src_dir / "widgets"
        widgets_dir.mkdir(parents=True, exist_ok=True)
        (widgets_dir / "demo_widget.py").write_text("WIDGET = 1\n", encoding="utf-8")
        custom_widgets_dir = src_dir / "custom_widgets"
        custom_widgets_dir.mkdir(parents=True, exist_ok=True)
        (custom_widgets_dir / "__pycache__").mkdir(parents=True, exist_ok=True)
        (custom_widgets_dir / "demo_widget.json").write_text('{"name":"demo"}\n', encoding="utf-8")
        (custom_widgets_dir / "demo_widget.pyc").write_bytes(b"PYC")
        (custom_widgets_dir / "__pycache__" / "demo_widget.cpython-314.pyc").write_bytes(b"CACHE")

        window = MainWindow(str(sdk_root))
        window.project = project
        window.project_root = str(sdk_root)
        window._project_dir = str(src_dir)
        window.app_name = "SaveAsDemo"

        monkeypatch.setattr("ui_designer.ui.main_window.QFileDialog.getExistingDirectory", lambda *args, **kwargs: str(dst_dir))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: None)
        monkeypatch.setattr(
            "ui_designer.ui.main_window.save_project_and_materialize_codegen",
            _fake_save_project_and_materialize_codegen("generated.c", "// save as\n"),
        )

        window._save_project_as()

        assert window._project_dir == os.path.normpath(os.path.abspath(dst_dir))
        assert window.project.project_dir == os.path.normpath(os.path.abspath(dst_dir))
        assert (dst_dir / "generated.c").read_text(encoding="utf-8") == "// save as\n"
        assert ".designer/build_designer.mk" in (dst_dir / "build.mk").read_text(encoding="utf-8")
        assert "# custom build" in (dst_dir / "build.mk").read_text(encoding="utf-8")
        assert '#include ".designer/app_egui_config_designer.h"' in (dst_dir / "app_egui_config.h").read_text(encoding="utf-8")
        assert "#define CUSTOM_CFG 1" in (dst_dir / "app_egui_config.h").read_text(encoding="utf-8")
        assert (dst_dir / ".designer" / "build_designer.mk").is_file()
        assert (dst_dir / ".designer" / "app_egui_config_designer.h").is_file()
        assert (dst_dir / ".eguiproject" / "resources" / "images" / "legacy.png").is_file()
        assert not (dst_dir / ".eguiproject" / "resources" / "images" / "_generated_text_preview.png").exists()
        assert not (dst_dir / ".eguiproject" / "resources" / "_generated_text_demo_16_4.txt").exists()
        assert (dst_dir / ".eguiproject" / "mockup" / "legacy.txt").is_file()
        assert (dst_dir / ".eguiproject" / "reference_frames" / "frame_000.png").read_bytes() == b"REF"
        assert not (dst_dir / ".eguiproject" / "regression_report.html").exists()
        assert not (dst_dir / ".eguiproject" / "regression_results.json").exists()
        assert json.loads((dst_dir / "resource" / "src" / "app_resource_config.json").read_text(encoding="utf-8")) == {
            "img": [{"file": "legacy.png"}],
            "font": [],
        }
        assert (dst_dir / "resource" / "src" / "legacy.png").is_file()
        assert (dst_dir / "resource" / "src" / "custom_assets" / "hero.png").read_bytes() == b"HERO"
        assert not (dst_dir / "resource" / "src" / "_generated_text_preview.png").exists()
        assert not (dst_dir / "resource" / "src" / "_generated_text_demo_16_4.txt").exists()
        assert (dst_dir / "main_page.c").read_text(encoding="utf-8") == "/* keep page source */\n"
        assert (dst_dir / "main_page_ext.h").read_text(encoding="utf-8") == "#define KEEP_MAIN_EXT 1\n"
        assert (dst_dir / "legacy_logic.h").read_text(encoding="utf-8") == "#define KEEP_LOGIC 1\n"
        assert (dst_dir / "feature" / "helper.c").read_text(encoding="utf-8") == "int helper(void) { return 1; }\n"
        assert (dst_dir / "feature" / "helper.h").read_text(encoding="utf-8") == "#define FEATURE_HELPER 1\n"
        assert not (dst_dir / "main_page.h").exists()
        assert (dst_dir / ".eguiproject" / "orphaned_user_code" / "main_page" / "main_page.c").read_text(
            encoding="utf-8"
        ) == "// orphan\n"
        assert (dst_dir / ".eguiproject" / "release.json").read_text(encoding="utf-8") == '{"profiles":["pc"]}\n'
        assert (dst_dir / "widgets" / "demo_widget.py").read_text(encoding="utf-8") == "WIDGET = 1\n"
        assert (dst_dir / "custom_widgets" / "demo_widget.json").read_text(encoding="utf-8") == '{"name":"demo"}\n'
        assert not (dst_dir / "custom_widgets" / "demo_widget.pyc").exists()
        assert not (dst_dir / "custom_widgets" / "__pycache__").exists()
        _close_window(window)

    def test_save_project_as_reports_editing_only_mode_when_preview_unavailable(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.ui.main_window import MainWindow

        class _PreviewIncompatibleCompiler:
            app_root_arg = "example"

            def __init__(self, app_dir):
                self.app_dir = str(app_dir)

            def can_build(self):
                return True

            def get_build_error(self):
                return ""

            def get_preview_build_error(self):
                return "make: *** No rule to make target 'main.exe'.  Stop."

            def set_screen_size(self, width, height):
                return None

            def is_preview_running(self):
                return False

            def is_exe_ready(self):
                return False

            def stop_exe(self):
                return None

            def cleanup(self):
                return None

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        src_dir = tmp_path / "SaveAsEditingOnlySrcDemo"
        dst_dir = tmp_path / "SaveAsEditingOnlyDstDemo"
        project = _create_project(src_dir, "SaveAsEditingOnlyDemo", sdk_root)

        window = MainWindow(str(sdk_root))
        window.project = project
        window.project_root = str(sdk_root)
        window._project_dir = str(src_dir)
        window.app_name = "SaveAsEditingOnlyDemo"

        monkeypatch.setattr("ui_designer.ui.main_window.QFileDialog.getExistingDirectory", lambda *args, **kwargs: str(dst_dir))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _PreviewIncompatibleCompiler(dst_dir)))
        monkeypatch.setattr(
            "ui_designer.ui.main_window.save_project_and_materialize_codegen",
            _fake_save_project_and_materialize_codegen("generated.c", "// save as\n"),
        )

        assert window._save_project_as() is True

        assert "Editing-only mode: make: *** No rule to make target 'main.exe'.  Stop." in window.statusBar().currentMessage()
        assert "main.exe" in window._auto_compile_retry_block_reason
        assert "main.exe" in window._compile_action.toolTip()
        _close_window(window)

    def test_save_project_as_switches_to_python_preview_when_preview_unavailable(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.ui.main_window import MainWindow

        class _PreviewIncompatibleCompiler:
            app_root_arg = "example"

            def __init__(self, app_dir):
                self.app_dir = str(app_dir)

            def can_build(self):
                return True

            def get_build_error(self):
                return ""

            def get_preview_build_error(self):
                return "make: *** No rule to make target 'main.exe'.  Stop."

            def set_screen_size(self, width, height):
                return None

            def is_preview_running(self):
                return False

            def is_exe_ready(self):
                return False

            def stop_exe(self):
                return None

            def cleanup(self):
                return None

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        src_dir = tmp_path / "SaveAsEditingOnlyPreviewSrcDemo"
        dst_dir = tmp_path / "SaveAsEditingOnlyPreviewDstDemo"
        project = _create_project(src_dir, "SaveAsEditingOnlyPreviewDemo", sdk_root)

        window = MainWindow(str(sdk_root))
        window.project = project
        window.project_root = str(sdk_root)
        window._project_dir = str(src_dir)
        window.app_name = "SaveAsEditingOnlyPreviewDemo"
        preview_reasons = []

        monkeypatch.setattr(window, "_switch_to_python_preview", lambda reason="": preview_reasons.append(reason))
        monkeypatch.setattr("ui_designer.ui.main_window.QFileDialog.getExistingDirectory", lambda *args, **kwargs: str(dst_dir))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _PreviewIncompatibleCompiler(dst_dir)))
        monkeypatch.setattr(
            "ui_designer.ui.main_window.save_project_and_materialize_codegen",
            _fake_save_project_and_materialize_codegen("generated.c", "// save as\n"),
        )

        assert window._save_project_as() is True

        assert preview_reasons[-1] == "make: *** No rule to make target 'main.exe'.  Stop."
        assert "Editing-only mode: make: *** No rule to make target 'main.exe'.  Stop." in window.statusBar().currentMessage()
        _close_window(window)

    def test_save_project_as_writes_split_page_outputs_with_real_generator(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        src_dir = tmp_path / "SrcRealDemo"
        dst_dir = tmp_path / "DstRealDemo"
        project = _create_project(src_dir, "SaveAsRealDemo", sdk_root)

        window = MainWindow(str(sdk_root))
        window.project = project
        window.project_root = str(sdk_root)
        window._project_dir = str(src_dir)
        window.app_name = "SaveAsRealDemo"

        monkeypatch.setattr("ui_designer.ui.main_window.QFileDialog.getExistingDirectory", lambda *args, **kwargs: str(dst_dir))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: None)
        monkeypatch.setattr(window, "_load_project_app_local_widgets", lambda *args, **kwargs: None)

        window._save_project_as()

        assert window._project_dir == os.path.normpath(os.path.abspath(dst_dir))
        assert (dst_dir / ".designer" / "main_page.h").is_file()
        assert (dst_dir / ".designer" / "main_page_layout.c").is_file()
        assert (dst_dir / "main_page.c").is_file()
        assert (dst_dir / "main_page_ext.h").is_file()
        assert '#include "main_page_ext.h"' in (dst_dir / ".designer" / "main_page.h").read_text(encoding="utf-8")
        assert "void egui_main_page_user_init(egui_main_page_t *page)" in (dst_dir / "main_page.c").read_text(encoding="utf-8")
        assert "#define EGUI_MAIN_PAGE_EXT_FIELDS" in (dst_dir / "main_page_ext.h").read_text(encoding="utf-8")
        _close_window(window)

    def test_save_project_as_multi_page_real_generator_writes_all_page_files(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        src_dir = tmp_path / "SrcMultiDemo"
        dst_dir = tmp_path / "DstMultiDemo"
        project = _create_project(
            src_dir,
            "SaveAsMultiDemo",
            sdk_root,
            pages=["main_page", "detail_page"],
        )

        window = MainWindow(str(sdk_root))
        window.project = project
        window.project_root = str(sdk_root)
        window._project_dir = str(src_dir)
        window.app_name = "SaveAsMultiDemo"

        monkeypatch.setattr("ui_designer.ui.main_window.QFileDialog.getExistingDirectory", lambda *args, **kwargs: str(dst_dir))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: None)
        monkeypatch.setattr(window, "_load_project_app_local_widgets", lambda *args, **kwargs: None)

        window._save_project_as()

        for page_name in ("main_page", "detail_page"):
            assert (dst_dir / ".designer" / f"{page_name}.h").is_file()
            assert (dst_dir / ".designer" / f"{page_name}_layout.c").is_file()
            assert (dst_dir / f"{page_name}.c").is_file()
            assert (dst_dir / f"{page_name}_ext.h").is_file()
        _close_window(window)

    def test_save_project_as_warns_on_non_empty_directory(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        src_dir = tmp_path / "SrcDemo"
        dst_dir = tmp_path / "BusyDir"
        dst_dir.mkdir()
        (dst_dir / "existing.txt").write_text("busy", encoding="utf-8")
        project = _create_project(src_dir, "SaveAsDemo", sdk_root)

        window = MainWindow(str(sdk_root))
        window.project = project
        window.project_root = str(sdk_root)
        window._project_dir = str(src_dir)
        window.app_name = "SaveAsDemo"

        warnings = []
        monkeypatch.setattr("ui_designer.ui.main_window.QFileDialog.getExistingDirectory", lambda *args, **kwargs: str(dst_dir))
        monkeypatch.setattr("ui_designer.ui.main_window.QMessageBox.warning", lambda *args: warnings.append(args[1:]))
        monkeypatch.setattr(window, "_save_project_files", lambda *args, **kwargs: pytest.fail("_save_project_files should not be called"))

        window._save_project_as()

        assert warnings
        assert warnings[0][0] == "Directory Conflict"
        _close_window(window)

    def test_save_project_as_warns_on_existing_empty_directory(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        src_dir = tmp_path / "SrcDemo"
        dst_dir = tmp_path / "ExistingDir"
        dst_dir.mkdir()
        project = _create_project(src_dir, "SaveAsDemo", sdk_root)

        window = MainWindow(str(sdk_root))
        window.project = project
        window.project_root = str(sdk_root)
        window._project_dir = str(src_dir)
        window.app_name = "SaveAsDemo"

        warnings = []
        monkeypatch.setattr("ui_designer.ui.main_window.QFileDialog.getExistingDirectory", lambda *args, **kwargs: str(dst_dir))
        monkeypatch.setattr("ui_designer.ui.main_window.QMessageBox.warning", lambda *args: warnings.append(args[1:]))
        monkeypatch.setattr(window, "_save_project_files", lambda *args, **kwargs: pytest.fail("_save_project_files should not be called"))

        window._save_project_as()

        assert warnings
        assert warnings[0][0] == "Directory Conflict"
        assert "already exists" in warnings[0][1]
        _close_window(window)

    def test_save_project_as_uses_current_project_parent_as_initial_directory(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        workspace_dir = tmp_path / "workspace"
        src_dir = workspace_dir / "SrcDemo"
        project = _create_project(src_dir, "SaveAsDemo", sdk_root)
        captured = {}

        window = MainWindow(str(sdk_root))
        window.project = project
        window.project_root = str(sdk_root)
        window._project_dir = str(src_dir)

        def fake_get_existing_directory(parent, title, directory):
            captured["title"] = title
            captured["directory"] = directory
            return ""

        monkeypatch.setattr("ui_designer.ui.main_window.QFileDialog.getExistingDirectory", fake_get_existing_directory)

        window._save_project_as()

        assert captured["title"] == "Save Project To Directory"
        assert captured["directory"] == os.path.normpath(os.path.abspath(workspace_dir))
        _close_window(window)

    def test_export_code_uses_current_project_dir_as_initial_directory(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "ExportDemo"
        project = _create_project(project_dir, "ExportDemo", sdk_root)
        captured = {}

        window = MainWindow(str(sdk_root))
        window.project = project
        window._project_dir = str(project_dir)

        def fake_get_existing_directory(parent, title, directory):
            captured["title"] = title
            captured["directory"] = directory
            return ""

        monkeypatch.setattr("ui_designer.ui.main_window.QFileDialog.getExistingDirectory", fake_get_existing_directory)

        window._export_code()

        assert captured["title"] == "Export C Code To Directory"
        assert captured["directory"] == os.path.normpath(os.path.abspath(project_dir))
        _close_window(window)

    def test_export_code_is_blocked_by_diagnostics_errors(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "ExportBlockedDemo"
        export_dir = tmp_path / "export_out"
        export_dir.mkdir()
        project = _create_project_only_with_widgets(
            project_dir,
            "ExportBlockedDemo",
            sdk_root,
            widgets=[WidgetModel("label", name="bad-name", x=8, y=8, width=60, height=20)],
        )

        warnings = []
        window = MainWindow(str(sdk_root))
        monkeypatch.setattr("ui_designer.ui.main_window.QFileDialog.getExistingDirectory", lambda *args, **kwargs: str(export_dir))
        monkeypatch.setattr("ui_designer.ui.main_window.QMessageBox.warning", lambda *args: warnings.append(args[1:]))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._export_code()

        assert warnings
        assert warnings[0][0] == "Export Blocked"
        assert "blocked by diagnostics" in warnings[0][1]
        assert not (export_dir / "main_page.c").exists()
        assert window.statusBar().currentMessage() == "Export blocked: 1 error(s) in diagnostics."
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_export_code_rejects_legacy_page_files_with_warning(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "ExportLegacyDemo"
        export_dir = tmp_path / "export_out"
        export_dir.mkdir()
        button = WidgetModel("button", name="confirm_button", x=10, y=10, width=80, height=32)
        button.on_click = "on_confirm"
        project = _create_project_only_with_widgets(
            project_dir,
            "ExportLegacyDemo",
            sdk_root,
            widgets=[button],
        )

        (export_dir / "main_page.h").write_text(
            (
                "#ifndef _MAIN_PAGE_H_\n"
                "#define _MAIN_PAGE_H_\n"
                "// USER CODE BEGIN includes\n"
                '#include "legacy_logic.h"\n'
                "// USER CODE END includes\n"
                "// USER CODE BEGIN declarations\n"
                "#define EGUI_MAIN_PAGE_HOOK_ON_OPEN(_page) main_page_after_open(_page)\n"
                "void main_page_after_open(egui_main_page_t *page);\n"
                "// USER CODE END declarations\n"
                "#endif\n"
            ),
            encoding="utf-8",
        )
        (export_dir / "main_page.c").write_text(
            (
                "// main_page.c - User implementation for main_page\n"
                "// Layout/widget init is in main_page_layout.c (auto-generated).\n"
                '#include "egui.h"\n'
                '#include "uicode.h"\n'
                '#include "main_page.h"\n'
                "\n"
                "// USER CODE BEGIN callbacks\n"
                "void on_confirm(egui_view_t *self)\n"
                "{\n"
                "    EGUI_UNUSED(self);\n"
                "    custom_confirm();\n"
                "}\n"
                "// USER CODE END callbacks\n"
                "\n"
                "// USER CODE BEGIN on_open\n"
                "    main_page_after_open(local);\n"
                "// USER CODE END on_open\n"
            ),
            encoding="utf-8",
        )

        window = MainWindow(str(sdk_root))
        warnings = []
        monkeypatch.setattr("ui_designer.ui.main_window.QFileDialog.getExistingDirectory", lambda *args, **kwargs: str(export_dir))
        monkeypatch.setattr(window, "_ensure_codegen_preflight", lambda *args, **kwargs: True)
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr("ui_designer.ui.main_window.QMessageBox.warning", lambda *args: warnings.append(args[1:]))

        _open_project_window(window, project, project_dir, sdk_root)
        window._export_code()

        assert not (export_dir / "main_page_ext.h").exists()
        assert '#include "legacy_logic.h"' in (export_dir / "main_page.h").read_text(encoding="utf-8")
        assert "custom_confirm();" in (export_dir / "main_page.c").read_text(encoding="utf-8")
        assert warnings
        assert warnings[0][0] == "Export Failed"
        assert "Unsupported legacy page source detected: main_page.c" in warnings[0][1]
        assert "Export failed:" in window.statusBar().currentMessage()
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_export_code_keeps_existing_user_owned_page_files(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "ExportKeepUserDemo"
        export_dir = tmp_path / "export_keep_out"
        export_dir.mkdir()
        project = _create_project(project_dir, "ExportKeepUserDemo", sdk_root)

        (export_dir / "main_page.c").write_text("/* keep user source */\n", encoding="utf-8")
        (export_dir / "main_page_ext.h").write_text("#define KEEP_USER_EXT 1\n", encoding="utf-8")

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr("ui_designer.ui.main_window.QFileDialog.getExistingDirectory", lambda *args, **kwargs: str(export_dir))
        monkeypatch.setattr(window, "_ensure_codegen_preflight", lambda *args, **kwargs: True)
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._export_code()

        assert (export_dir / "main_page.c").read_text(encoding="utf-8") == "/* keep user source */\n"
        assert (export_dir / "main_page_ext.h").read_text(encoding="utf-8") == "#define KEEP_USER_EXT 1\n"
        assert (export_dir / ".designer" / "main_page.h").is_file()
        assert (export_dir / ".designer" / "main_page_layout.c").is_file()
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_export_code_copies_project_user_owned_page_files_into_empty_directory(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "ExportCopyProjectUserDemo"
        export_dir = tmp_path / "export_copy_project_user_out"
        export_dir.mkdir()
        project = _create_project(project_dir, "ExportCopyProjectUserDemo", sdk_root)

        feature_dir = project_dir / "feature"
        feature_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "build.mk").write_text(
            '# custom build\ninclude $(EGUI_APP_PATH)/.designer/build_designer.mk\nEGUI_CODE_SRC += feature\nEGUI_CODE_INCLUDE += feature\n',
            encoding="utf-8",
        )
        (project_dir / "main_page.c").write_text("/* keep project user source */\n", encoding="utf-8")
        (project_dir / "main_page_ext.h").write_text("#define KEEP_PROJECT_USER_EXT 1\n", encoding="utf-8")
        (project_dir / "legacy_logic.h").write_text("#define KEEP_PROJECT_LOGIC 1\n", encoding="utf-8")
        (feature_dir / "helper.c").write_text("int helper(void) { return 1; }\n", encoding="utf-8")
        (feature_dir / "helper.h").write_text("#define FEATURE_HELPER 1\n", encoding="utf-8")
        (project_dir / ".designer").mkdir(parents=True, exist_ok=True)
        (project_dir / ".designer" / "main_page.h").write_text("// designer page header\n", encoding="utf-8")
        (project_dir / "main_page.h").write_text("// stale legacy page header\n", encoding="utf-8")

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr("ui_designer.ui.main_window.QFileDialog.getExistingDirectory", lambda *args, **kwargs: str(export_dir))
        monkeypatch.setattr(window, "_ensure_codegen_preflight", lambda *args, **kwargs: True)
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._export_code()

        assert (export_dir / "main_page.c").read_text(encoding="utf-8") == "/* keep project user source */\n"
        assert (export_dir / "main_page_ext.h").read_text(encoding="utf-8") == "#define KEEP_PROJECT_USER_EXT 1\n"
        assert (export_dir / "legacy_logic.h").read_text(encoding="utf-8") == "#define KEEP_PROJECT_LOGIC 1\n"
        assert (export_dir / "feature" / "helper.c").read_text(encoding="utf-8") == "int helper(void) { return 1; }\n"
        assert (export_dir / "feature" / "helper.h").read_text(encoding="utf-8") == "#define FEATURE_HELPER 1\n"
        assert not (export_dir / "main_page.h").exists()
        assert (export_dir / ".designer" / "main_page.h").is_file()
        assert (export_dir / ".designer" / "main_page_layout.c").is_file()
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_export_code_multi_page_mixed_directory_preserves_existing_and_generates_missing(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "ExportMultiMixedDemo"
        export_dir = tmp_path / "export_multi_mixed_out"
        export_dir.mkdir()
        project = _create_project(
            project_dir,
            "ExportMultiMixedDemo",
            sdk_root,
            pages=["main_page", "detail_page"],
        )

        (export_dir / "main_page.c").write_text("/* keep main page user */\n", encoding="utf-8")
        (export_dir / "detail_page_ext.h").write_text("#define KEEP_DETAIL_EXT 1\n", encoding="utf-8")

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr("ui_designer.ui.main_window.QFileDialog.getExistingDirectory", lambda *args, **kwargs: str(export_dir))
        monkeypatch.setattr(window, "_ensure_codegen_preflight", lambda *args, **kwargs: True)
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._export_code()

        assert (export_dir / "main_page.c").read_text(encoding="utf-8") == "/* keep main page user */\n"
        assert (export_dir / "detail_page_ext.h").read_text(encoding="utf-8") == "#define KEEP_DETAIL_EXT 1\n"
        assert (export_dir / "main_page_ext.h").is_file()
        assert (export_dir / "detail_page.c").is_file()
        assert (export_dir / ".designer" / "detail_page.h").is_file()
        assert (export_dir / ".designer" / "detail_page_layout.c").is_file()
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_export_code_after_page_rename_replaces_previous_page_file_set(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "ExportRenameDemo"
        export_dir = tmp_path / "export_rename_out"
        export_dir.mkdir()
        project = _create_project(project_dir, "ExportRenameDemo", sdk_root)

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr("ui_designer.ui.main_window.QFileDialog.getExistingDirectory", lambda *args, **kwargs: str(export_dir))
        monkeypatch.setattr(window, "_ensure_codegen_preflight", lambda *args, **kwargs: True)
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._export_code()
        (export_dir / "main_page.c").write_text("/* exported rename me */\n", encoding="utf-8")
        (export_dir / "main_page_ext.h").write_text("#define EXPORT_KEEP_MAIN_EXT 1\n", encoding="utf-8")

        window._on_page_renamed("main_page", "dashboard_page")
        window._export_code()

        assert not (export_dir / "main_page.h").exists()
        assert not (export_dir / "main_page_layout.c").exists()
        assert not (export_dir / ".designer" / "main_page.h").exists()
        assert not (export_dir / ".designer" / "main_page_layout.c").exists()
        assert not (export_dir / "main_page.c").exists()
        assert not (export_dir / "main_page_ext.h").exists()
        assert (export_dir / ".designer" / "dashboard_page.h").is_file()
        assert (export_dir / ".designer" / "dashboard_page_layout.c").is_file()
        assert (export_dir / "dashboard_page.c").read_text(encoding="utf-8") == "/* exported rename me */\n"
        assert (export_dir / "dashboard_page_ext.h").read_text(encoding="utf-8") == "#define EXPORT_KEEP_MAIN_EXT 1\n"
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_set_sdk_root_updates_current_project_and_rebuilds_compiler(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.project import Project
        from ui_designer.ui.main_window import MainWindow

        old_sdk = tmp_path / "old_sdk"
        new_sdk = tmp_path / "new_sdk"
        _create_sdk_root(old_sdk)
        _create_sdk_root(new_sdk)

        window = MainWindow(str(old_sdk))
        window.project = Project(app_name="DemoApp")
        window.auto_compile = True

        class FakeCompiler:
            def can_build(self):
                return True

            def is_preview_running(self):
                return False

            def stop_exe(self):
                return None

            def cleanup(self):
                return None

        calls = {"recreate": 0, "compile": 0}

        def fake_recreate():
            calls["recreate"] += 1
            window.compiler = FakeCompiler()

        monkeypatch.setattr("ui_designer.ui.main_window.QFileDialog.getExistingDirectory", lambda *args, **kwargs: str(new_sdk))
        monkeypatch.setattr(window, "_recreate_compiler", fake_recreate)
        monkeypatch.setattr(
            window,
            "_trigger_compile",
            lambda *args, **kwargs: calls.__setitem__("compile", calls["compile"] + 1),
        )

        window._set_sdk_root()

        assert window.project_root == os.path.normpath(os.path.abspath(new_sdk))
        assert window.project.sdk_root == os.path.normpath(os.path.abspath(new_sdk))
        assert isolated_config.sdk_root == os.path.normpath(os.path.abspath(new_sdk))
        assert calls == {"recreate": 1, "compile": 1}
        assert "SDK root set to:" in window.statusBar().currentMessage()
        assert "selected SDK root" in window.statusBar().currentMessage()
        _close_window(window)

    def test_set_sdk_root_auto_resolves_parent_directory(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_parent = tmp_path / "tools"
        sdk_root = sdk_parent / "sdk" / "EmbeddedGUI-main"
        _create_sdk_root(sdk_root)

        window = MainWindow("")
        monkeypatch.setattr("ui_designer.ui.main_window.QFileDialog.getExistingDirectory", lambda *args, **kwargs: str(sdk_parent))

        window._set_sdk_root()

        assert window.project_root == os.path.normpath(os.path.abspath(sdk_root))
        assert isolated_config.sdk_root == os.path.normpath(os.path.abspath(sdk_root))
        assert "SDK root set to:" in window.statusBar().currentMessage()
        assert "selected SDK root" in window.statusBar().currentMessage()
        _close_window(window)

    def test_set_sdk_root_uses_recovered_cached_sdk_as_initial_directory(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        cached_sdk = tmp_path / "config" / "sdk" / "EmbeddedGUI"
        _create_sdk_root(cached_sdk)
        isolated_config.sdk_root = str(tmp_path / "missing_sdk")
        isolated_config.sdk_root = str(tmp_path / "missing_sdk")
        captured = {}

        def fake_get_existing_directory(parent, title, directory):
            captured["title"] = title
            captured["directory"] = directory
            return ""

        window = MainWindow("")
        monkeypatch.setattr("ui_designer.ui.main_window.default_sdk_install_dir", lambda: str(cached_sdk))
        monkeypatch.setattr("ui_designer.ui.main_window.QFileDialog.getExistingDirectory", fake_get_existing_directory)

        window._set_sdk_root()

        assert captured["title"] == "Select EmbeddedGUI SDK Root"
        assert captured["directory"] == os.path.normpath(os.path.abspath(cached_sdk))
        _close_window(window)

    def test_open_app_dialog_uses_recovered_cached_sdk_root(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        cached_sdk = tmp_path / "config" / "sdk" / "EmbeddedGUI"
        _create_sdk_root(cached_sdk)
        isolated_config.sdk_root = str(tmp_path / "missing_sdk")
        isolated_config.sdk_root = str(tmp_path / "missing_sdk")
        captured = {}

        class FakeDialog:
            Accepted = 1

            def __init__(self, parent=None, sdk_root=None, on_download_sdk=None):
                captured["sdk_root"] = sdk_root
                self._selected_entry = None
                self._sdk_root = sdk_root

            def exec_(self):
                return 0

            @property
            def selected_entry(self):
                return self._selected_entry

            @property
            def sdk_root(self):
                return self._sdk_root

        window = MainWindow("")
        monkeypatch.setattr("ui_designer.ui.main_window.default_sdk_install_dir", lambda: str(cached_sdk))
        monkeypatch.setattr("ui_designer.ui.main_window.AppSelectorDialog", FakeDialog)

        window._open_app_dialog()

        assert captured["sdk_root"] == os.path.normpath(os.path.abspath(cached_sdk))
        _close_window(window)

    def test_open_app_dialog_opens_bundled_example_without_rebinding_sdk(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        isolated_config.sdk_root = str(sdk_root)
        isolated_config.sdk_root = str(sdk_root)
        project_dir = tmp_path / "examples" / "DesignerSandbox"
        project_dir.mkdir(parents=True)
        project_path = project_dir / "DesignerSandbox.egui"
        project_path.write_text("<Project />", encoding="utf-8")
        captured = {}

        class FakeDialog:
            Accepted = 1

            def __init__(self, parent=None, sdk_root=None, on_download_sdk=None):
                self._selected_entry = {
                    "app_name": "DesignerSandbox",
                    "project_path": str(project_path),
                    "has_project": True,
                    "is_unmanaged": False,
                    "source": "designer",
                }
                self._sdk_root = sdk_root or ""

            def exec_(self):
                return self.Accepted

            @property
            def selected_entry(self):
                return self._selected_entry

            @property
            def sdk_root(self):
                return self._sdk_root

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr("ui_designer.ui.main_window.AppSelectorDialog", FakeDialog)
        monkeypatch.setattr(
            window,
            "_open_project_path",
            lambda path, preferred_sdk_root="", silent=False: captured.update(
                {
                    "path": path,
                    "preferred_sdk_root": preferred_sdk_root,
                    "silent": silent,
                }
            ),
        )

        window._open_app_dialog()

        assert captured == {
            "path": os.path.normpath(os.path.abspath(project_path)),
            "preferred_sdk_root": "",
            "silent": False,
        }
        assert isolated_config.sdk_root == os.path.normpath(os.path.abspath(sdk_root))
        assert isolated_config.sdk_root == os.path.normpath(os.path.abspath(sdk_root))
        _close_window(window)

    def test_open_loaded_project_discovers_default_sdk_cache_when_config_is_empty(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.project import Project
        from ui_designer.ui.main_window import MainWindow

        project_dir = tmp_path / "CacheDemo"
        project = _create_project(project_dir, "CacheDemo", "")
        sdk_root = tmp_path / "config" / "sdk" / "EmbeddedGUI"
        _create_sdk_root(sdk_root)

        window = MainWindow("")
        monkeypatch.setattr("ui_designer.ui.main_window.default_sdk_install_dir", lambda: str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, _load_project(project_dir), project_dir)

        assert window.project_root == os.path.normpath(os.path.abspath(sdk_root))
        assert window.project.sdk_root == os.path.normpath(os.path.abspath(sdk_root))
        assert isolated_config.sdk_root == os.path.normpath(os.path.abspath(sdk_root))
        _close_window(window)

    @pytest.mark.skip(reason="removed SDK download workflow from Designer")
    def test_download_sdk_updates_config_and_project_root(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "downloaded_sdk"

        def fake_ensure_sdk_downloaded(target_dir, progress_callback=None):
            _create_sdk_root(sdk_root)
            if progress_callback is not None:
                progress_callback("EmbeddedGUI SDK is ready.", 100)
            return str(sdk_root)

        window = MainWindow("")
        monkeypatch.setattr("ui_designer.ui.main_window.default_sdk_install_dir", lambda: str(tmp_path / "sdk_cache"))
        monkeypatch.setattr("ui_designer.ui.main_window.ensure_sdk_downloaded", fake_ensure_sdk_downloaded)

        result = window._download_sdk()

        assert result == os.path.normpath(os.path.abspath(sdk_root))
        assert window.project_root == os.path.normpath(os.path.abspath(sdk_root))
        assert isolated_config.sdk_root == os.path.normpath(os.path.abspath(sdk_root))
        assert isolated_config.sdk_setup_prompted is True
        assert "SDK downloaded to:" in window.statusBar().currentMessage()
        _close_window(window)

    def test_compile_preview_is_blocked_by_diagnostics_errors(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "CompileBlockedDemo"
        project = _create_project_only_with_widgets(
            project_dir,
            "CompileBlockedDemo",
            sdk_root,
            widgets=[WidgetModel("label", name="bad-name", x=8, y=8, width=60, height=20)],
        )

        class CompileFailIfCalled:
            app_root_arg = "app"

            def can_build(self):
                return True

            def get_build_error(self):
                return ""

            def compile_and_run_async(self, *args, **kwargs):
                raise AssertionError("compile_and_run_async should not be called when diagnostics block compile")

            def set_screen_size(self, width, height):
                return None

            def is_preview_running(self):
                return False

            def stop_exe(self):
                return None

            def cleanup(self):
                return None

        window = MainWindow(str(sdk_root))
        preview_reasons = []
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window, "_ensure_resources_generated", lambda: (_ for _ in ()).throw(AssertionError("resource generation should not run")))
        monkeypatch.setattr(window, "_switch_to_python_preview", lambda reason="": preview_reasons.append(reason))

        _open_project_window(window, project, project_dir, sdk_root)
        window.compiler = CompileFailIfCalled()
        preview_reasons.clear()
        window._do_compile_and_run()

        assert preview_reasons == ["Compile blocked by diagnostics"]
        assert window.statusBar().currentMessage() == "Compile preview blocked: 1 error(s) in diagnostics."
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_rebuild_egui_project_uses_clean_rebuild_cycle(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        class _DummySignal:
            def connect(self, _handler):
                return None

        class _DummyWorker:
            def __init__(self):
                self.log = _DummySignal()

            def isRunning(self):
                return False

        class _RebuildCaptureCompiler:
            app_root_arg = "example"

            def __init__(self):
                self.stop_calls = 0
                self.force_rebuild = None

            def can_build(self):
                return True

            def get_build_error(self):
                return ""

            def set_screen_size(self, width, height):
                return None

            def is_preview_running(self):
                return False

            def is_exe_ready(self):
                return True

            def stop_exe(self):
                self.stop_calls += 1

            def cleanup(self):
                return None

            def compile_and_run_async(self, *args, **kwargs):
                self.force_rebuild = kwargs.get("force_rebuild")
                return _DummyWorker()

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "RebuildDemo"
        project = _create_project(project_dir, "RebuildDemo", sdk_root)
        compiler = _RebuildCaptureCompiler()
        compiler.app_dir = str(project_dir)
        preview_stop_calls = []
        generated = {}
        rename_hook_calls = []

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", compiler))
        monkeypatch.setattr(window, "_ensure_resources_generated", lambda: None)
        monkeypatch.setattr(window, "_ensure_codegen_preflight", lambda *args, **kwargs: True)
        monkeypatch.setattr(window, "_update_diagnostics_panel", lambda: None)
        monkeypatch.setattr(window.preview_panel, "stop_rendering", lambda: preview_stop_calls.append("stop"))
        rename_hook = lambda output_dir: rename_hook_calls.append(output_dir)
        monkeypatch.setattr(window, "_apply_pending_page_rename_outputs", rename_hook)
        monkeypatch.setattr(
            "ui_designer.ui.main_window.prepare_project_codegen_outputs",
            _fake_prepare_project_codegen_outputs(
                {".designer/uicode.c": "// rebuild test\n"},
                capture=generated,
            ),
        )

        _open_project_window(window, project, project_dir, sdk_root)
        compiler.force_rebuild = None
        compiler.stop_calls = 0
        preview_stop_calls.clear()

        window._do_rebuild_egui_project()

        assert compiler.force_rebuild is True
        assert compiler.stop_calls == 1
        assert preview_stop_calls == ["stop"]
        assert generated["project"] is project
        assert generated["output_dir"] == os.path.normpath(os.path.abspath(project_dir))
        assert generated["backup"] is False
        assert generated["before_prepare"] == rename_hook
        assert generated["cleanup_legacy"] is True
        assert rename_hook_calls == [os.path.normpath(os.path.abspath(project_dir))]
        assert window.preview_panel.status_label.text() == "Rebuilding..."
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_compile_failure_shows_debug_rebuild_button_and_click_runs_rebuild(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        class _DummySignal:
            def connect(self, _handler):
                return None

        class _DummyWorker:
            def __init__(self):
                self.log = _DummySignal()

            def isRunning(self):
                return False

        class _RebuildCaptureCompiler:
            app_root_arg = "example"

            def __init__(self):
                self.force_rebuild = None
                self.stop_calls = 0

            def can_build(self):
                return True

            def get_build_error(self):
                return ""

            def set_screen_size(self, width, height):
                return None

            def is_preview_running(self):
                return False

            def is_exe_ready(self):
                return True

            def stop_exe(self):
                self.stop_calls += 1

            def cleanup(self):
                return None

            def compile_and_run_async(self, *args, **kwargs):
                self.force_rebuild = kwargs.get("force_rebuild")
                return _DummyWorker()

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "RebuildButtonDemo"
        project = _create_project(project_dir, "RebuildButtonDemo", sdk_root)
        compiler = _RebuildCaptureCompiler()
        compiler.app_dir = str(project_dir)
        preview_reasons = []

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", compiler))
        monkeypatch.setattr(window, "_ensure_resources_generated", lambda: None)
        monkeypatch.setattr(window, "_ensure_codegen_preflight", lambda *args, **kwargs: True)
        monkeypatch.setattr(window, "_update_diagnostics_panel", lambda: None)
        monkeypatch.setattr(window.preview_panel, "stop_rendering", lambda: None)
        monkeypatch.setattr(window, "_switch_to_python_preview", lambda reason="": preview_reasons.append(reason))
        monkeypatch.setattr(
            "ui_designer.ui.main_window.prepare_project_codegen_outputs",
            _fake_prepare_project_codegen_outputs(
                {".designer/uicode.c": "// rebuild button test\n"},
            ),
        )

        _open_project_window(window, project, project_dir, sdk_root)
        compiler.force_rebuild = None
        preview_reasons.clear()

        window._on_compile_finished(None, window._async_generation, False, False, "Compilation failed:\nboom")

        assert preview_reasons == ["boom"]
        assert window.debug_panel._rebuild_btn.isHidden() is False
        assert window.debug_panel._rebuild_btn.isEnabled() is True

        window.debug_panel._rebuild_btn.click()

        assert compiler.force_rebuild is True
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_compile_failure_missing_main_target_reports_makefile_issue(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "MissingMainTargetDemo"
        project = _create_project(project_dir, "MissingMainTargetDemo", sdk_root)
        compiler = _AutoRetryCompiler(project_dir, exe_ready=True)
        preview_reasons = []

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", compiler))
        monkeypatch.setattr(window, "_switch_to_python_preview", lambda reason="": preview_reasons.append(reason))
        window.preview_panel.is_python_preview_active = lambda: True

        _open_project_window(window, project, project_dir, sdk_root)
        build_action = next(action for action in window.menuBar().actions() if action.text() == "Build")
        preview_reasons.clear()

        window._on_compile_finished(
            None,
            window._async_generation,
            False,
            False,
            "Compilation failed:\nmake: *** No rule to make target 'main.exe'.  Stop.",
        )

        assert preview_reasons == ["make: *** No rule to make target 'main.exe'.  Stop."]
        assert "main.exe" in window.statusBar().currentMessage()
        assert "Clean All" not in window.statusBar().currentMessage()
        assert "cannot recover missing build targets" in window.debug_panel._output.toPlainText()
        assert window._compile_action.isEnabled() is False
        assert window._rebuild_action.isEnabled() is False
        assert "main.exe" in window._compile_action.toolTip()
        assert "Preview: Editing Only" in window._workspace_status_label.text()
        assert window.debug_panel._rebuild_btn.isHidden() is True
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_clean_rebuild_failure_missing_clean_target_keeps_compile_available(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "MissingCleanTargetDemo"
        project = _create_project(project_dir, "MissingCleanTargetDemo", sdk_root)
        compiler = _AutoRetryCompiler(project_dir, exe_ready=True)
        preview_reasons = []

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", compiler))
        monkeypatch.setattr(window, "_switch_to_python_preview", lambda reason="": preview_reasons.append(reason))
        window.preview_panel.is_python_preview_active = lambda: True

        _open_project_window(window, project, project_dir, sdk_root)
        build_action = next(action for action in window.menuBar().actions() if action.text() == "Build")

        window._on_compile_finished(
            None,
            window._async_generation,
            True,
            False,
            "Rebuild failed:\nmake: *** No rule to make target 'clean'.  Stop.",
        )

        assert preview_reasons[-1] == "make: *** No rule to make target 'clean'.  Stop."
        assert "clean" in window.statusBar().currentMessage()
        assert "Regular Compile remains available" in window.debug_panel._output.toPlainText()
        assert window._effective_preview_unavailable_reason() == ""
        assert window._auto_compile_retry_block_reason == ""
        assert window._compile_action.isEnabled() is True
        assert window._rebuild_action.isEnabled() is False
        assert "clean" in window._rebuild_action.toolTip()
        assert window._clean_all_action.toolTip() == (
            "Destructive recovery: delete project-side generated/code files outside the preserved "
            "Designer source set and reconstruct the project (Ctrl+Shift+F5). "
            "Project: open. Saved project: saved. SDK: valid. Preview: python preview. "
            "Preview rerun will be skipped: make: *** No rule to make target 'clean'.  Stop."
        )
        assert build_action.toolTip() == (
            "Compile previews, generate resources, or reconstruct a project from Designer sources. "
            "Project: open. SDK: valid. Compile: available. Rebuild: unavailable. Reconstruct: available (preview rerun skipped). Auto compile: on. "
            f"Preview: python preview. Source resources: available. Resource directory: {window._get_eguiproject_resource_dir()}."
        )
        assert window.debug_panel._rebuild_btn.isHidden() is True
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_compile_failure_after_missing_clean_target_avoids_rebuild_recovery_guidance(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "MissingCleanTargetGuidanceDemo"
        project = _create_project(project_dir, "MissingCleanTargetGuidanceDemo", sdk_root)
        compiler = _AutoRetryCompiler(project_dir, exe_ready=True)

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", compiler))
        monkeypatch.setattr(window, "_switch_to_python_preview", lambda reason="": None)

        _open_project_window(window, project, project_dir, sdk_root)

        window._on_compile_finished(
            None,
            window._async_generation,
            True,
            False,
            "Rebuild failed:\nmake: *** No rule to make target 'clean'.  Stop.",
        )

        window.debug_panel._output.clear()
        window._on_compile_finished(
            None,
            window._async_generation,
            False,
            False,
            "Compilation failed:\nboom",
        )

        assert "Rebuild-based recovery is unavailable" in window.statusBar().currentMessage()
        debug_output = window.debug_panel._output.toPlainText()
        assert "required by Rebuild EGUI Project" in debug_output
        assert "Clean All && Reconstruct can still rebuild project files" in debug_output
        assert "Use Build > Rebuild EGUI Project first" not in debug_output
        assert window._compile_action.isEnabled() is True
        assert window._rebuild_action.isEnabled() is False
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_debug_rebuild_button_hides_after_environmental_preview_block(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "DebugRebuildButtonHideDemo"
        project = _create_project(project_dir, "DebugRebuildButtonHideDemo", sdk_root)
        compiler = _AutoRetryCompiler(project_dir, exe_ready=True)

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", compiler))

        _open_project_window(window, project, project_dir, sdk_root)

        window._update_debug_rebuild_action(show=True)
        assert window.debug_panel._rebuild_btn.isHidden() is False

        window._block_auto_compile_retry("make: *** No rule to make target 'main.exe'.  Stop.")
        window._update_compile_availability()

        assert window._compile_action.isEnabled() is False
        assert window._rebuild_action.isEnabled() is False
        assert window.debug_panel._rebuild_btn.isHidden() is True
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_compile_failure_feedback_handles_generic_preview_target_unavailable(self):
        from ui_designer.ui.main_window import MainWindow

        status, guidance = MainWindow._compile_failure_feedback(
            "Preview build target unavailable: make defines neither 'main.exe' nor 'main'."
        )

        assert "Preview build target is unavailable" in status
        assert "cannot recover missing build targets" in guidance

    def test_compile_failure_feedback_handles_generic_preview_build_unavailable(self):
        from ui_designer.ui.main_window import MainWindow

        status, guidance = MainWindow._compile_failure_feedback("Preview build unavailable")

        assert status == "Preview build is unavailable, switched to Python fallback."
        assert "cannot recover missing preview build availability" in guidance

    def test_compile_failure_feedback_handles_missing_clean_target(self):
        from ui_designer.ui.main_window import MainWindow

        status, guidance = MainWindow._compile_failure_feedback(
            "Rebuild failed:\nmake: *** No rule to make target 'clean'.  Stop.",
            force_rebuild=True,
        )

        assert status == "Clean rebuild target 'clean' is unavailable, switched to Python fallback."
        assert "Regular Compile remains available" in guidance
        assert "Clean All && Reconstruct will rebuild project files without rerunning the preview" in guidance

    def test_compile_failure_feedback_handles_generic_compile_failure_when_clean_target_is_unavailable(self):
        from ui_designer.ui.main_window import MainWindow

        status, guidance = MainWindow._compile_failure_feedback(
            "Compilation failed:\nboom",
            rebuild_unavailable_reason="make: *** No rule to make target 'clean'.  Stop.",
        )

        assert "Rebuild-based recovery is unavailable" in status
        assert "required by Rebuild EGUI Project" in guidance
        assert "Clean All && Reconstruct can still rebuild project files" in guidance

    def test_compile_failure_feedback_handles_preview_probe_timeout(self):
        from ui_designer.ui.main_window import MainWindow

        status, guidance = MainWindow._compile_failure_feedback("Preview build target probe timed out")

        assert status == "Preview build target probe timed out, switched to Python fallback."
        assert "cannot recover probe timeouts caused by the environment" in guidance

    def test_open_project_skips_precompile_when_preview_target_probe_fails(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.ui.main_window import MainWindow

        class _ProbeFailCompiler:
            app_root_arg = "example"

            def __init__(self, app_dir):
                self.app_dir = str(app_dir)
                self.reset_calls = 0

            def can_build(self):
                return True

            def get_build_error(self):
                return ""

            def get_preview_build_error(self):
                return "make: *** No rule to make target 'main.exe'.  Stop."

            def ensure_preview_build_available(self, force=False):
                return False

            def reset_preview_build_probe(self):
                self.reset_calls += 1

            def set_screen_size(self, width, height):
                return None

            def is_preview_running(self):
                return False

            def is_exe_ready(self):
                return False

            def stop_exe(self):
                return None

            def cleanup(self):
                return None

            def precompile_async(self, callback):
                raise AssertionError("precompile_async should not be called when preview target probe fails")

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewTargetProbeDemo"
        project = _create_project(project_dir, "PreviewTargetProbeDemo", sdk_root)
        compiler = _ProbeFailCompiler(project_dir)

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", compiler))

        _open_project_window(window, project, project_dir, sdk_root)

        assert "main.exe" in window._auto_compile_retry_block_reason
        assert window._compile_action.isEnabled() is False
        assert window._rebuild_action.isEnabled() is False
        assert "main.exe" in window._compile_action.toolTip()
        message = window.statusBar().currentMessage()
        assert f"Opened: {os.path.normpath(os.path.abspath(project_dir))}" in message
        assert "Editing-only mode: make: *** No rule to make target 'main.exe'.  Stop." in message
        assert "Preview: Editing Only" in window._workspace_status_label.text()
        assert "cannot recover missing build targets" in window.debug_panel._output.toPlainText()
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_open_project_uses_effective_preview_block_reason_when_probe_error_is_not_exposed(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.ui.main_window import MainWindow

        class _SilentProbeFailCompiler:
            app_root_arg = "example"

            def __init__(self, app_dir):
                self.app_dir = str(app_dir)

            def can_build(self):
                return True

            def get_build_error(self):
                return ""

            def get_preview_build_error(self):
                return ""

            def ensure_preview_build_available(self, force=False):
                return False

            def set_screen_size(self, width, height):
                return None

            def is_preview_running(self):
                return False

            def is_exe_ready(self):
                return False

            def stop_exe(self):
                return None

            def cleanup(self):
                return None

            def precompile_async(self, callback):
                raise AssertionError("precompile_async should not be called when preview target probe fails")

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewSilentProbeFailDemo"
        project = _create_project(project_dir, "PreviewSilentProbeFailDemo", sdk_root)
        compiler = _SilentProbeFailCompiler(project_dir)

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", compiler))

        _open_project_window(window, project, project_dir, sdk_root)

        message = window.statusBar().currentMessage()
        assert f"Opened: {os.path.normpath(os.path.abspath(project_dir))}" in message
        assert "Editing-only mode: Preview build unavailable" in message
        assert window._compile_action.isEnabled() is False
        assert window._rebuild_action.isEnabled() is False
        assert "Preview build unavailable" in window._compile_action.toolTip()
        assert "Preview: Editing Only" in window._workspace_status_label.text()
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_trigger_compile_skips_timer_when_only_effective_preview_block_reason_exists(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.ui.main_window import MainWindow

        class _SilentProbeFailCompiler:
            app_root_arg = "example"

            def __init__(self, app_dir):
                self.app_dir = str(app_dir)

            def can_build(self):
                return True

            def get_build_error(self):
                return ""

            def get_preview_build_error(self):
                return ""

            def ensure_preview_build_available(self, force=False):
                return False

            def set_screen_size(self, width, height):
                return None

            def is_preview_running(self):
                return False

            def is_exe_ready(self):
                return False

            def stop_exe(self):
                return None

            def cleanup(self):
                return None

            def precompile_async(self, callback):
                raise AssertionError("precompile_async should not be called when preview target probe fails")

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewSilentAutoCompileBlockDemo"
        project = _create_project(project_dir, "PreviewSilentAutoCompileBlockDemo", sdk_root)

        window = MainWindow(str(sdk_root))
        compile_cycle_calls = []
        preview_reasons = []
        window.auto_compile = False
        window._compile_timer.stop()
        window._compile_timer.setInterval(0)
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _SilentProbeFailCompiler(project_dir)))
        monkeypatch.setattr(
            window,
            "_start_compile_cycle",
            lambda *args, **kwargs: compile_cycle_calls.append(kwargs.get("force_rebuild", False)),
        )
        monkeypatch.setattr(window, "_switch_to_python_preview", lambda reason="": preview_reasons.append(reason))

        _open_project_window(window, project, project_dir, sdk_root)

        window.auto_compile = True
        window._trigger_compile()
        qapp.processEvents()
        window._run_auto_compile_cycle()

        debug_output = window.debug_panel._output.toPlainText()
        assert compile_cycle_calls == []
        assert preview_reasons[-1] == "Preview build unavailable"
        assert "Auto compile trigger blocked: unspecified change (retry blocked: Preview build unavailable)" in debug_output
        assert window._compile_timer.isActive() is False
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_toggle_auto_compile_off_cancels_pending_timer_and_cycle(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "AutoCompileToggleCancelDemo"
        project = _create_project(project_dir, "AutoCompileToggleCancelDemo", sdk_root)
        compiler = _AutoRetryCompiler(project_dir, exe_ready=True)
        compile_cycle_calls = []

        window = MainWindow(str(sdk_root))
        window.auto_compile = False
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", compiler))
        monkeypatch.setattr(
            window,
            "_start_compile_cycle",
            lambda *args, **kwargs: compile_cycle_calls.append(kwargs.get("force_rebuild", False)),
        )

        _open_project_window(window, project, project_dir, sdk_root)

        window.auto_compile = True
        window._compile_timer.stop()
        window._compile_timer.setInterval(10)
        window._compile_timer.start()
        window._pending_compile = True

        window._toggle_auto_compile(False)
        QTest.qWait(30)
        qapp.processEvents()
        window._run_auto_compile_cycle()

        assert compile_cycle_calls == []
        assert window.auto_compile is False
        assert window._compile_timer.isActive() is False
        assert window._pending_compile is False
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_compile_reason_logs_show_queue_merge_and_start(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.ui.main_window import MainWindow

        class _CaptureCompiler:
            app_root_arg = "example"

            def __init__(self, app_dir):
                self.app_dir = str(app_dir)
                self.compile_calls = 0

            def can_build(self):
                return True

            def get_build_error(self):
                return ""

            def set_screen_size(self, width, height):
                return None

            def is_preview_running(self):
                return False

            def is_exe_ready(self):
                return True

            def stop_exe(self):
                return None

            def cleanup(self):
                return None

            def compile_and_run_async(self, *args, **kwargs):
                self.compile_calls += 1
                return _IdleWorker()

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "CompileReasonLogDemo"
        project = _create_project(project_dir, "CompileReasonLogDemo", sdk_root)
        compiler = _CaptureCompiler(project_dir)

        window = MainWindow(str(sdk_root))
        window.auto_compile = False
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", compiler))
        monkeypatch.setattr(window, "_ensure_resources_generated", lambda: None)
        monkeypatch.setattr(window, "_ensure_codegen_preflight", lambda *args, **kwargs: True)
        monkeypatch.setattr(window, "_update_diagnostics_panel", lambda: None)
        monkeypatch.setattr(
            "ui_designer.ui.main_window.prepare_project_codegen_outputs",
            _fake_prepare_project_codegen_outputs(
                {".designer/uicode.c": "// compile reason log test\n"},
            ),
        )

        _open_project_window(window, project, project_dir, sdk_root)
        window.debug_panel._output.clear()

        window.auto_compile = True
        window._compile_timer.stop()
        window._compile_timer.setInterval(60000)
        window._trigger_compile(reason="property edit")
        window._trigger_compile(reason="page fields edit")
        window._compile_timer.stop()
        window._start_compile_cycle(force_rebuild=False, reason_fallback="auto compile")

        debug_output = window.debug_panel._output.toPlainText()
        assert "Auto compile trigger queued: property edit" in debug_output
        assert "Auto compile trigger merged: page fields edit" in debug_output
        assert "Compile request received: property edit; page fields edit" in debug_output
        assert "Compile trigger: property edit; page fields edit" in debug_output
        assert window._queued_compile_reasons == []
        assert compiler.compile_calls == 1
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_widget_selection_change_does_not_queue_compile_reason(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "SelectionNoCompileDemo"
        project = _create_project(project_dir, "SelectionNoCompileDemo", sdk_root)
        compiler = _AutoRetryCompiler(project_dir, exe_ready=True)

        window = MainWindow(str(sdk_root))
        window.auto_compile = False
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", compiler))

        _open_project_window(window, project, project_dir, sdk_root)
        window.debug_panel._output.clear()
        window.auto_compile = True
        window._compile_timer.stop()
        window._clear_selection(sync_tree=False, sync_preview=False)
        window._on_widget_selected(window._current_page.root_widget)

        debug_output = window.debug_panel._output.toPlainText()
        assert "Selection event (tree):" in debug_output
        assert "Property panel rebuild: mode=single" in debug_output
        assert "Selection pipeline:" in debug_output
        assert "Selection applied (tree):" in debug_output
        assert "No compile queued." in debug_output
        assert "Auto compile trigger" not in debug_output
        assert "Compile trigger:" not in debug_output
        assert window._compile_timer.isActive() is False
        assert window._queued_compile_reasons == []
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_apply_sdk_root_reports_editing_only_mode_without_status_prefix(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.ui.main_window import MainWindow

        class _PreviewIncompatibleCompiler:
            app_root_arg = "example"

            def __init__(self, app_dir):
                self.app_dir = str(app_dir)

            def can_build(self):
                return True

            def get_build_error(self):
                return ""

            def get_preview_build_error(self):
                return "make: *** No rule to make target 'main.exe'.  Stop."

            def is_preview_running(self):
                return False

            def is_exe_ready(self):
                return False

            def set_screen_size(self, width, height):
                return None

            def stop_exe(self):
                return None

            def cleanup(self):
                return None

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "ApplySdkRootEditingOnlyDemo"
        project = _create_project(project_dir, "ApplySdkRootEditingOnlyDemo", sdk_root)

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        _open_project_window(window, project, project_dir, sdk_root)

        monkeypatch.setattr(
            window,
            "_recreate_compiler",
            lambda: setattr(window, "compiler", _PreviewIncompatibleCompiler(project_dir)),
        )

        window._apply_sdk_root(str(sdk_root))

        assert window.statusBar().currentMessage() == (
            "Editing-only mode: make: *** No rule to make target 'main.exe'.  Stop."
        )
        assert "Preview: Editing Only" in window._workspace_status_label.text()
        assert "main.exe" in window._compile_action.toolTip()
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_apply_sdk_root_clears_auto_retry_block_when_preview_recovers(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.ui.main_window import MainWindow

        class _ProbeFailCompiler:
            app_root_arg = "example"

            def __init__(self, app_dir):
                self.app_dir = str(app_dir)

            def can_build(self):
                return True

            def get_build_error(self):
                return ""

            def get_preview_build_error(self):
                return "make: *** No rule to make target 'main.exe'.  Stop."

            def ensure_preview_build_available(self, force=False):
                return False

            def set_screen_size(self, width, height):
                return None

            def is_preview_running(self):
                return False

            def is_exe_ready(self):
                return False

            def stop_exe(self):
                return None

            def cleanup(self):
                return None

            def precompile_async(self, callback):
                raise AssertionError("precompile_async should not be called when preview target probe fails")

        bad_sdk_root = tmp_path / "sdk_bad"
        good_sdk_root = tmp_path / "sdk_good"
        _create_sdk_root(bad_sdk_root)
        _create_sdk_root(good_sdk_root)
        project_dir = tmp_path / "ApplySdkRootRetryRecoveryDemo"
        project = _create_project(project_dir, "ApplySdkRootRetryRecoveryDemo", bad_sdk_root)
        good_compiler = _AutoRetryCompiler(project_dir, exe_ready=True)

        window = MainWindow(str(bad_sdk_root))
        compile_cycle_calls = []
        window._compile_timer.stop()
        window._compile_timer.setInterval(0)
        monkeypatch.setattr(
            window,
            "_start_compile_cycle",
            lambda *args, **kwargs: compile_cycle_calls.append(kwargs.get("force_rebuild", False)),
        )

        def _recreate_compiler():
            if window.project_root == os.path.normpath(os.path.abspath(good_sdk_root)):
                window.compiler = good_compiler
            else:
                window.compiler = _ProbeFailCompiler(project_dir)

        monkeypatch.setattr(window, "_recreate_compiler", _recreate_compiler)

        _open_project_window(window, project, project_dir, bad_sdk_root)

        assert "main.exe" in window._auto_compile_retry_block_reason

        window._apply_sdk_root(str(good_sdk_root))
        qapp.processEvents()

        assert compile_cycle_calls == [False]
        assert window._auto_compile_retry_block_reason == ""
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_apply_sdk_root_probes_preview_availability_before_clearing_state(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.ui.main_window import MainWindow

        class _DelayedProbeCompiler:
            app_root_arg = "example"

            def __init__(self, app_dir):
                self.app_dir = str(app_dir)
                self.preview_error = ""
                self.ensure_calls = []

            def can_build(self):
                return True

            def get_build_error(self):
                return ""

            def get_preview_build_error(self):
                return self.preview_error

            def ensure_preview_build_available(self, force=False):
                self.ensure_calls.append(force)
                self.preview_error = "make: *** No rule to make target 'main.exe'.  Stop."
                return False

            def is_preview_running(self):
                return False

            def is_exe_ready(self):
                return False

            def set_screen_size(self, width, height):
                return None

            def stop_exe(self):
                return None

            def cleanup(self):
                return None

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "ApplySdkRootDelayedProbeDemo"
        project = _create_project(project_dir, "ApplySdkRootDelayedProbeDemo", sdk_root)
        compiler = _DelayedProbeCompiler(project_dir)

        window = MainWindow(str(sdk_root))
        window.auto_compile = False
        _disable_window_compile(window, _DisabledCompiler)
        _open_project_window(window, project, project_dir, sdk_root)

        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", compiler))

        window._apply_sdk_root(str(sdk_root))

        assert compiler.ensure_calls == [True]
        assert "main.exe" in window._auto_compile_retry_block_reason
        assert window._compile_action.isEnabled() is False
        assert "Editing-only mode: make: *** No rule to make target 'main.exe'.  Stop." in window.statusBar().currentMessage()
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_precompile_failure_blocks_auto_precompile_after_external_reload(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PrecompileRetryBlockDemo"
        project = _create_project(project_dir, "PrecompileRetryBlockDemo", sdk_root)
        compiler = _AutoRetryCompiler(project_dir, exe_ready=False)

        window = MainWindow(str(sdk_root))
        window.auto_compile = False
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", compiler))

        _open_project_window(window, project, project_dir, sdk_root)

        assert compiler.precompile_calls == 1

        worker = window._precompile_worker
        window._on_precompile_done(worker, window._async_generation, False, "Compilation failed:\nboom")

        assert "EXE build failed, switched to Python fallback" in window.statusBar().currentMessage()
        assert window._compile_action.isEnabled() is True
        assert window.preview_panel.is_python_preview_active() is True

        layout_file = project_dir / ".eguiproject" / "layout" / "main_page.xml"
        layout_file.write_text(layout_file.read_text(encoding="utf-8") + "\n<!-- blocked precompile retry -->\n", encoding="utf-8")

        assert window._poll_project_files() is None
        assert compiler.precompile_calls == 1
        assert window._auto_compile_retry_block_reason == "boom"
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_precompile_failure_with_missing_preview_target_updates_editing_only_state(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PrecompilePreviewTargetMissingDemo"
        project = _create_project(project_dir, "PrecompilePreviewTargetMissingDemo", sdk_root)
        compiler = _AutoRetryCompiler(project_dir, exe_ready=False)

        window = MainWindow(str(sdk_root))
        window.auto_compile = False
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", compiler))

        _open_project_window(window, project, project_dir, sdk_root)

        worker = window._precompile_worker
        window._on_precompile_done(
            worker,
            window._async_generation,
            False,
            "Compilation failed:\nmake: *** No rule to make target 'main.exe'.  Stop.",
        )

        assert "main.exe" in window._auto_compile_retry_block_reason
        assert window._compile_action.isEnabled() is False
        assert window._rebuild_action.isEnabled() is False
        assert "Preview build target 'main.exe' is unavailable" in window.statusBar().currentMessage()
        assert window.preview_panel.is_python_preview_active() is True
        assert window._clean_all_action.toolTip() == (
            "Destructive recovery: delete project-side generated/code files outside the preserved "
            "Designer source set and reconstruct the project (Ctrl+Shift+F5). "
            "Project: open. Saved project: saved. SDK: valid. Preview: editing only. "
            "Unavailable: missing preview build targets cannot be recovered by reconstruction: "
            "make: *** No rule to make target 'main.exe'.  Stop."
        )
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_precompile_success_resumes_queued_compile_request(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "QueuedCompileAfterPrecompileDemo"
        project = _create_project(project_dir, "QueuedCompileAfterPrecompileDemo", sdk_root)
        compiler = _AutoRetryCompiler(project_dir, exe_ready=False)
        compile_cycle_calls = []

        window = MainWindow(str(sdk_root))
        window.auto_compile = False
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", compiler))
        monkeypatch.setattr(
            window,
            "_start_compile_cycle",
            lambda *args, **kwargs: compile_cycle_calls.append(kwargs.get("force_rebuild", False)),
        )

        _open_project_window(window, project, project_dir, sdk_root)

        worker = window._precompile_worker
        window._pending_compile = True
        window._pending_rebuild = False
        window._on_precompile_done(worker, window._async_generation, True, "ok")

        assert compile_cycle_calls == [False]
        assert window._pending_compile is False
        assert window._pending_rebuild is False
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_precompile_success_resumes_queued_rebuild_request(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "QueuedRebuildAfterPrecompileDemo"
        project = _create_project(project_dir, "QueuedRebuildAfterPrecompileDemo", sdk_root)
        compiler = _AutoRetryCompiler(project_dir, exe_ready=False)
        compile_cycle_calls = []

        window = MainWindow(str(sdk_root))
        window.auto_compile = False
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", compiler))
        monkeypatch.setattr(
            window,
            "_start_compile_cycle",
            lambda *args, **kwargs: compile_cycle_calls.append(kwargs.get("force_rebuild", False)),
        )

        _open_project_window(window, project, project_dir, sdk_root)

        worker = window._precompile_worker
        window._pending_compile = True
        window._pending_rebuild = True
        window._on_precompile_done(worker, window._async_generation, True, "ok")

        assert compile_cycle_calls == [True]
        assert window._pending_compile is False
        assert window._pending_rebuild is False
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_precompile_success_prioritizes_pending_external_reload_over_queued_rebuild(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "QueuedReloadBeforeRebuildDemo"
        project = _create_project(project_dir, "QueuedReloadBeforeRebuildDemo", sdk_root)
        compiler = _AutoRetryCompiler(project_dir, exe_ready=False)
        compile_cycle_calls = []
        reload_calls = []

        window = MainWindow(str(sdk_root))
        window.auto_compile = False
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", compiler))
        monkeypatch.setattr(
            window,
            "_start_compile_cycle",
            lambda *args, **kwargs: compile_cycle_calls.append(kwargs.get("force_rebuild", False)),
        )

        def _capture_reload(*args, **kwargs):
            reload_calls.append(kwargs)
            window._bump_async_generation()
            window._clear_external_reload_pending()
            return True

        monkeypatch.setattr(window, "_reload_project_from_disk", _capture_reload)

        _open_project_window(window, project, project_dir, sdk_root)

        worker = window._precompile_worker
        layout_file = project_dir / ".eguiproject" / "layout" / "main_page.xml"
        window._set_external_reload_pending([os.path.normpath(os.path.abspath(layout_file))])
        monkeypatch.setattr(
            window,
            "_pending_external_reload_changed_paths",
            lambda: [os.path.normpath(os.path.abspath(layout_file))],
        )
        window._pending_compile = True
        window._pending_rebuild = True
        current_generation = window._async_generation
        window._on_precompile_done(worker, current_generation, True, "ok")

        assert reload_calls == [
            {
                "auto": True,
                "changed_paths": [os.path.normpath(os.path.abspath(layout_file))],
            }
        ]
        assert compile_cycle_calls == []
        assert window._pending_compile is False
        assert window._pending_rebuild is False
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_precompile_failure_drops_queued_compile_and_rebuild_requests(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "QueuedRetryDropAfterPrecompileDemo"
        project = _create_project(project_dir, "QueuedRetryDropAfterPrecompileDemo", sdk_root)
        compiler = _AutoRetryCompiler(project_dir, exe_ready=False)
        compile_cycle_calls = []

        window = MainWindow(str(sdk_root))
        window.auto_compile = False
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", compiler))
        monkeypatch.setattr(
            window,
            "_start_compile_cycle",
            lambda *args, **kwargs: compile_cycle_calls.append(kwargs.get("force_rebuild", False)),
        )

        _open_project_window(window, project, project_dir, sdk_root)

        worker = window._precompile_worker
        window._pending_compile = True
        window._pending_rebuild = True
        window._on_precompile_done(worker, window._async_generation, False, "Compilation failed:\nboom")

        assert compile_cycle_calls == []
        assert window._pending_compile is False
        assert window._pending_rebuild is False
        assert window._auto_compile_retry_block_reason == "boom"
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_precompile_failure_resumes_pending_external_reload_without_waiting_for_watch_tick(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PrecompileFailureReloadResumeDemo"
        project = _create_project(project_dir, "PrecompileFailureReloadResumeDemo", sdk_root)
        compiler = _AutoRetryCompiler(project_dir, exe_ready=False)
        reload_calls = []

        window = MainWindow(str(sdk_root))
        window.auto_compile = False
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", compiler))

        def _capture_reload(*args, **kwargs):
            reload_calls.append(kwargs)
            window._bump_async_generation()
            window._clear_external_reload_pending()
            return True

        monkeypatch.setattr(window, "_reload_project_from_disk", _capture_reload)

        _open_project_window(window, project, project_dir, sdk_root)

        worker = window._precompile_worker
        layout_file = project_dir / ".eguiproject" / "layout" / "main_page.xml"
        window._set_external_reload_pending([os.path.normpath(os.path.abspath(layout_file))])
        monkeypatch.setattr(
            window,
            "_pending_external_reload_changed_paths",
            lambda: [os.path.normpath(os.path.abspath(layout_file))],
        )
        current_generation = window._async_generation
        window._on_precompile_done(worker, current_generation, False, "Compilation failed:\nboom")

        assert reload_calls == [
            {
                "auto": True,
                "changed_paths": [os.path.normpath(os.path.abspath(layout_file))],
            }
        ]
        assert window._auto_compile_retry_block_reason == "boom"
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_compile_failure_blocks_auto_retry_after_external_reload(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "CompileRetryBlockDemo"
        project = _create_project(project_dir, "CompileRetryBlockDemo", sdk_root)
        compiler = _AutoRetryCompiler(project_dir, exe_ready=True)
        compile_cycle_calls = []

        window = MainWindow(str(sdk_root))
        window.auto_compile = False
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", compiler))
        monkeypatch.setattr(
            window,
            "_start_compile_cycle",
            lambda *args, **kwargs: compile_cycle_calls.append(kwargs.get("force_rebuild", False)),
        )

        _open_project_window(window, project, project_dir, sdk_root)

        window.auto_compile = True
        window._compile_timer.stop()
        window._compile_timer.setInterval(0)

        window._on_compile_finished(None, window._async_generation, False, False, "Compilation failed:\nboom")

        layout_file = project_dir / ".eguiproject" / "layout" / "main_page.xml"
        layout_file.write_text(layout_file.read_text(encoding="utf-8") + "\n<!-- blocked compile retry -->\n", encoding="utf-8")

        assert window._poll_project_files() is None
        qapp.processEvents()
        assert compile_cycle_calls == []
        assert window._auto_compile_retry_block_reason == "boom"
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_compile_failure_resumes_pending_external_reload_without_waiting_for_watch_tick(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "CompileFailureReloadResumeDemo"
        project = _create_project(project_dir, "CompileFailureReloadResumeDemo", sdk_root)
        compiler = _AutoRetryCompiler(project_dir, exe_ready=True)
        reload_calls = []

        window = MainWindow(str(sdk_root))
        window.auto_compile = False
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", compiler))

        def _capture_reload(*args, **kwargs):
            reload_calls.append(kwargs)
            window._bump_async_generation()
            window._clear_external_reload_pending()
            return True

        monkeypatch.setattr(window, "_reload_project_from_disk", _capture_reload)

        _open_project_window(window, project, project_dir, sdk_root)

        layout_file = project_dir / ".eguiproject" / "layout" / "main_page.xml"
        window._set_external_reload_pending([os.path.normpath(os.path.abspath(layout_file))])
        monkeypatch.setattr(
            window,
            "_pending_external_reload_changed_paths",
            lambda: [os.path.normpath(os.path.abspath(layout_file))],
        )
        current_generation = window._async_generation
        window._on_compile_finished(None, current_generation, False, False, "Compilation failed:\nboom")

        assert reload_calls == [
            {
                "auto": True,
                "changed_paths": [os.path.normpath(os.path.abspath(layout_file))],
            }
        ]
        assert window._auto_compile_retry_block_reason == "boom"
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_compile_failure_drops_queued_compile_retry(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "QueuedCompileRetryDropDemo"
        project = _create_project(project_dir, "QueuedCompileRetryDropDemo", sdk_root)
        compiler = _AutoRetryCompiler(project_dir, exe_ready=True)
        trigger_calls = []

        window = MainWindow(str(sdk_root))
        window.auto_compile = False
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", compiler))

        _open_project_window(window, project, project_dir, sdk_root)

        window.auto_compile = True
        monkeypatch.setattr(window, "_trigger_compile", lambda *args, **kwargs: trigger_calls.append("compile"))
        window._pending_compile = True
        window._pending_rebuild = False
        window._on_compile_finished(None, window._async_generation, False, False, "Compilation failed:\nboom")

        assert trigger_calls == []
        assert window._pending_compile is False
        assert window._pending_rebuild is False
        assert window._auto_compile_retry_block_reason == "boom"
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_compile_failure_drops_queued_rebuild_retry(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "QueuedRebuildRetryDropDemo"
        project = _create_project(project_dir, "QueuedRebuildRetryDropDemo", sdk_root)
        compiler = _AutoRetryCompiler(project_dir, exe_ready=True)
        compile_cycle_calls = []

        window = MainWindow(str(sdk_root))
        window.auto_compile = False
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", compiler))
        monkeypatch.setattr(
            window,
            "_start_compile_cycle",
            lambda *args, **kwargs: compile_cycle_calls.append(kwargs.get("force_rebuild", False)),
        )

        _open_project_window(window, project, project_dir, sdk_root)

        window._pending_compile = False
        window._pending_rebuild = True
        window._on_compile_finished(None, window._async_generation, False, False, "Compilation failed:\nboom")

        assert compile_cycle_calls == []
        assert window._pending_compile is False
        assert window._pending_rebuild is False
        assert window._auto_compile_retry_block_reason == "boom"
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_compile_success_prioritizes_pending_external_reload_over_queued_rebuild(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "QueuedReloadBeforeQueuedRebuildDemo"
        project = _create_project(project_dir, "QueuedReloadBeforeQueuedRebuildDemo", sdk_root)
        compiler = _AutoRetryCompiler(project_dir, exe_ready=True)
        compile_cycle_calls = []
        reload_calls = []

        window = MainWindow(str(sdk_root))
        window.auto_compile = False
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", compiler))
        monkeypatch.setattr(
            window,
            "_start_compile_cycle",
            lambda *args, **kwargs: compile_cycle_calls.append(kwargs.get("force_rebuild", False)),
        )
        monkeypatch.setattr(window.preview_panel, "start_rendering", lambda _compiler: None)

        def _capture_reload(*args, **kwargs):
            reload_calls.append(kwargs)
            window._bump_async_generation()
            window._clear_external_reload_pending()
            return True

        monkeypatch.setattr(window, "_reload_project_from_disk", _capture_reload)

        _open_project_window(window, project, project_dir, sdk_root)

        layout_file = project_dir / ".eguiproject" / "layout" / "main_page.xml"
        window._set_external_reload_pending([os.path.normpath(os.path.abspath(layout_file))])
        monkeypatch.setattr(
            window,
            "_pending_external_reload_changed_paths",
            lambda: [os.path.normpath(os.path.abspath(layout_file))],
        )
        window._pending_compile = True
        window._pending_rebuild = True
        current_generation = window._async_generation
        window._on_compile_finished(None, current_generation, False, True, "ok")

        assert reload_calls == [
            {
                "auto": True,
                "changed_paths": [os.path.normpath(os.path.abspath(layout_file))],
            }
        ]
        assert compile_cycle_calls == []
        assert window._pending_compile is False
        assert window._pending_rebuild is False
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_compile_success_resumes_pending_external_reload_without_waiting_for_watch_tick(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "CompileSuccessReloadResumeDemo"
        project = _create_project(project_dir, "CompileSuccessReloadResumeDemo", sdk_root)
        compiler = _AutoRetryCompiler(project_dir, exe_ready=True)
        reload_calls = []

        window = MainWindow(str(sdk_root))
        window.auto_compile = False
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", compiler))
        monkeypatch.setattr(window.preview_panel, "start_rendering", lambda _compiler: None)

        def _capture_reload(*args, **kwargs):
            reload_calls.append(kwargs)
            window._bump_async_generation()
            window._clear_external_reload_pending()
            return True

        monkeypatch.setattr(window, "_reload_project_from_disk", _capture_reload)

        _open_project_window(window, project, project_dir, sdk_root)

        layout_file = project_dir / ".eguiproject" / "layout" / "main_page.xml"
        window._set_external_reload_pending([os.path.normpath(os.path.abspath(layout_file))])
        monkeypatch.setattr(
            window,
            "_pending_external_reload_changed_paths",
            lambda: [os.path.normpath(os.path.abspath(layout_file))],
        )
        current_generation = window._async_generation
        window._on_compile_finished(None, current_generation, False, True, "ok")

        assert reload_calls == [
            {
                "auto": True,
                "changed_paths": [os.path.normpath(os.path.abspath(layout_file))],
            }
        ]
        assert window._pending_compile is False
        assert window._pending_rebuild is False
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_manual_rebuild_clears_auto_retry_block(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "ManualRetryResumeDemo"
        project = _create_project(project_dir, "ManualRetryResumeDemo", sdk_root)
        compiler = _AutoRetryCompiler(project_dir, exe_ready=True)
        captured = {}

        window = MainWindow(str(sdk_root))
        window.auto_compile = False
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", compiler))
        monkeypatch.setattr(
            window,
            "_start_compile_cycle",
            lambda *args, **kwargs: captured.update(
                force_rebuild=kwargs.get("force_rebuild", False),
                blocked=window._is_auto_compile_retry_blocked(),
            ),
        )

        _open_project_window(window, project, project_dir, sdk_root)

        window._on_compile_finished(None, window._async_generation, False, False, "Compilation failed:\nboom")

        assert window._is_auto_compile_retry_blocked() is True

        window._do_rebuild_egui_project()

        assert captured == {"force_rebuild": True, "blocked": False}
        assert window._auto_compile_retry_block_reason == ""
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_clean_rebuild_failure_blocks_auto_precompile_after_external_reload(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "CleanRebuildRetryBlockDemo"
        project = _create_project(project_dir, "CleanRebuildRetryBlockDemo", sdk_root)
        compiler = _AutoRetryCompiler(project_dir, exe_ready=False)

        window = MainWindow(str(sdk_root))
        window.auto_compile = False
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", compiler))

        _open_project_window(window, project, project_dir, sdk_root)

        compiler.precompile_calls = 0
        window._precompile_worker = None

        window._on_compile_finished(None, window._async_generation, True, False, "Rebuild failed:\nboom")

        layout_file = project_dir / ".eguiproject" / "layout" / "main_page.xml"
        layout_file.write_text(
            layout_file.read_text(encoding="utf-8") + "\n<!-- blocked clean rebuild retry -->\n",
            encoding="utf-8",
        )

        assert window._poll_project_files() is None
        assert compiler.precompile_calls == 0
        assert window._auto_compile_retry_block_reason == "boom"
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_rebuild_egui_project_rejects_legacy_page_source_before_compile(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.ui.main_window import MainWindow

        class _DummySignal:
            def connect(self, _handler):
                return None

        class _DummyWorker:
            def __init__(self):
                self.log = _DummySignal()

            def isRunning(self):
                return False

        class _CaptureCompiler:
            app_root_arg = "example"

            def __init__(self, app_dir):
                self.app_dir = str(app_dir)
                self.files_dict = None
                self.force_rebuild = None

            def can_build(self):
                return True

            def get_build_error(self):
                return ""

            def set_screen_size(self, width, height):
                return None

            def is_preview_running(self):
                return False

            def is_exe_ready(self):
                return True

            def stop_exe(self):
                return None

            def cleanup(self):
                return None

            def compile_and_run_async(self, *args, **kwargs):
                self.files_dict = kwargs.get("files_dict")
                self.force_rebuild = kwargs.get("force_rebuild")
                return _DummyWorker()

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewMigrationDemo"
        project = _create_project(project_dir, "PreviewMigrationDemo", sdk_root)
        legacy_source = (
            Path(__file__).resolve().parents[1] / "test_data" / "user_code_sample.c"
        ).read_text(encoding="utf-8")
        (project_dir / "main_page.c").write_text(legacy_source, encoding="utf-8")

        compiler = _CaptureCompiler(project_dir)

        window = MainWindow(str(sdk_root))
        python_preview_reasons = []
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", compiler))
        monkeypatch.setattr(window, "_ensure_resources_generated", lambda: None)
        monkeypatch.setattr(window, "_ensure_codegen_preflight", lambda *args, **kwargs: True)
        monkeypatch.setattr(window, "_update_diagnostics_panel", lambda: None)
        monkeypatch.setattr(window, "_switch_to_python_preview", lambda reason="": python_preview_reasons.append(reason))

        _open_project_window(window, project, project_dir, sdk_root)
        window._do_rebuild_egui_project()

        assert compiler.force_rebuild is None
        assert compiler.files_dict is None
        assert python_preview_reasons
        assert "Unsupported legacy page source detected: main_page.c" in python_preview_reasons[0]
        assert window.preview_panel.status_label.text() == python_preview_reasons[0]
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_rebuild_egui_project_removes_stale_designer_string_outputs_before_compile(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.ui.main_window import MainWindow

        class _DummySignal:
            def connect(self, _handler):
                return None

        class _DummyWorker:
            def __init__(self):
                self.log = _DummySignal()

            def isRunning(self):
                return False

        class _CaptureCompiler:
            app_root_arg = "example"

            def __init__(self, app_dir):
                self.app_dir = str(app_dir)
                self.files_dict = None

            def can_build(self):
                return True

            def get_build_error(self):
                return ""

            def set_screen_size(self, width, height):
                return None

            def is_preview_running(self):
                return False

            def is_exe_ready(self):
                return True

            def stop_exe(self):
                return None

            def cleanup(self):
                return None

            def compile_and_run_async(self, *args, **kwargs):
                self.files_dict = kwargs.get("files_dict")
                return _DummyWorker()

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewStringCleanupDemo"
        project = _create_project(project_dir, "PreviewStringCleanupDemo", sdk_root)
        designer_dir = project_dir / ".designer"
        designer_dir.mkdir(exist_ok=True)
        (designer_dir / "egui_strings.h").write_text("// stale string header\n", encoding="utf-8")
        (designer_dir / "egui_strings.c").write_text("// stale string source\n", encoding="utf-8")

        compiler = _CaptureCompiler(project_dir)

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", compiler))
        monkeypatch.setattr(window, "_ensure_resources_generated", lambda: None)
        monkeypatch.setattr(window, "_ensure_codegen_preflight", lambda *args, **kwargs: True)
        monkeypatch.setattr(window, "_update_diagnostics_panel", lambda: None)

        _open_project_window(window, project, project_dir, sdk_root)
        window._do_rebuild_egui_project()

        assert compiler.files_dict is not None
        assert ".designer/egui_strings.h" not in compiler.files_dict
        assert ".designer/egui_strings.c" not in compiler.files_dict
        assert not (designer_dir / "egui_strings.h").exists()
        assert not (designer_dir / "egui_strings.c").exists()
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_clean_all_and_reconstruct_runs_destructive_recovery_flow(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.utils.scaffold import ORPHANED_USER_CODE_DIR_RELPATH, REFERENCE_FRAMES_DIR_RELPATH
        from ui_designer.model.project_cleaner import ProjectCleanReport
        from ui_designer.ui.main_window import MainWindow

        class _BuildReadyCompiler:
            def can_build(self):
                return True

            def is_preview_running(self):
                return False

            def stop_exe(self):
                return None

            def cleanup(self):
                return None

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "CleanAllFlowDemo"
        project = _create_project(project_dir, "CleanAllFlowDemo", sdk_root)

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _AutoRetryCompiler(project_dir, exe_ready=True)))
        _open_project_window(window, project, project_dir, sdk_root)

        compiler = _BuildReadyCompiler()
        captured = {"resources": 0}

        def fake_confirm(*args):
            captured["title"] = args[1]
            captured["text"] = args[2]
            return QMessageBox.Yes

        def fake_clean(project_path):
            captured["clean_path"] = project_path
            return ProjectCleanReport(removed_files=5, removed_dirs=2)

        def fake_save_project_files(project_path, *, reset_scaffold=False):
            captured["save_project_files"] = (project_path, reset_scaffold)
            return {".designer/uicode.c": "// reconstructed\n"}

        monkeypatch.setattr("ui_designer.ui.main_window.QMessageBox.warning", fake_confirm)
        monkeypatch.setattr("ui_designer.ui.main_window.clean_project_for_reconstruct", fake_clean)
        monkeypatch.setattr(window, "_persist_designer_state_only", lambda project_path: captured.setdefault("persist_path", project_path))
        monkeypatch.setattr(window, "_shutdown_async_activity", lambda wait_ms=500: captured.setdefault("shutdown_wait", wait_ms))
        monkeypatch.setattr(window, "_cleanup_compiler", lambda stop_exe=False: captured.setdefault("cleanup_stop_exe", stop_exe))
        monkeypatch.setattr(window, "_save_project_files", fake_save_project_files)
        monkeypatch.setattr(window, "_ensure_resources_generated", lambda: captured.__setitem__("resources", captured["resources"] + 1))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", compiler))
        monkeypatch.setattr(window, "_refresh_project_watch_snapshot", lambda: captured.setdefault("snapshot_refreshed", True))
        monkeypatch.setattr(window, "_update_window_title", lambda: captured.setdefault("title_updated", True))
        monkeypatch.setattr(window, "_update_compile_availability", lambda: captured.setdefault("availability_updated", True))
        monkeypatch.setattr(
            window,
            "_start_compile_cycle",
            lambda *args, **kwargs: captured.setdefault("compile_force_rebuild", kwargs.get("force_rebuild", False)),
        )

        window._do_clean_all_and_reconstruct()

        assert captured["title"] == "Clean All and Reconstruct"
        assert "Preserved:" in captured["text"]
        assert "Deleted and reconstructed:" in captured["text"]
        assert "widgets/** app-local widget sources" in captured["text"]
        assert f"{REFERENCE_FRAMES_DIR_RELPATH}/** regression baseline captures" in captured["text"]
        assert f"{ORPHANED_USER_CODE_DIR_RELPATH}/** archived user page code" in captured["text"]
        assert "runtime cache files inside app-local widget source dirs (__pycache__, *.pyc, *.pyo)" in captured["text"]
        assert "designer-reserved generated resource files (for example _generated_text_*)" in captured["text"]
        assert captured["clean_path"] == os.path.normpath(os.path.abspath(project_dir))
        assert captured["persist_path"] == os.path.normpath(os.path.abspath(project_dir))
        assert captured["shutdown_wait"] == 500
        assert captured["cleanup_stop_exe"] is True
        assert captured["save_project_files"] == (os.path.normpath(os.path.abspath(project_dir)), True)
        assert captured["resources"] == 1
        assert captured["compile_force_rebuild"] is True
        assert "Cleaned 5 file(s) and 2 directories" in window.statusBar().currentMessage()
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_clean_all_and_reconstruct_reports_editing_only_mode_when_preview_is_unavailable(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.model.project_cleaner import ProjectCleanReport
        from ui_designer.ui.main_window import MainWindow

        class _BuildUnavailableCompiler(_DisabledCompiler):
            def get_build_error(self):
                return "SDK unavailable, compile preview disabled"

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "CleanAllEditingOnlyDemo"
        project = _create_project(project_dir, "CleanAllEditingOnlyDemo", sdk_root)

        window = MainWindow(str(sdk_root))
        preview_reasons = []
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _BuildUnavailableCompiler()))
        monkeypatch.setattr(window, "_switch_to_python_preview", lambda reason="": preview_reasons.append(reason))
        _open_project_window(window, project, project_dir, sdk_root)
        preview_reasons.clear()

        compiler = _BuildUnavailableCompiler()
        captured = {"resources": 0}

        monkeypatch.setattr("ui_designer.ui.main_window.QMessageBox.warning", lambda *args: QMessageBox.Yes)
        monkeypatch.setattr(
            "ui_designer.ui.main_window.clean_project_for_reconstruct",
            lambda project_path: ProjectCleanReport(removed_files=1, removed_dirs=0),
        )
        monkeypatch.setattr(window, "_persist_designer_state_only", lambda project_path: None)
        monkeypatch.setattr(window, "_shutdown_async_activity", lambda wait_ms=500: None)
        monkeypatch.setattr(window, "_cleanup_compiler", lambda stop_exe=False: None)
        monkeypatch.setattr(window, "_save_project_files", lambda project_path, reset_scaffold=False: {".designer/uicode.c": "// reconstructed\n"})
        monkeypatch.setattr(window, "_ensure_resources_generated", lambda: captured.__setitem__("resources", captured["resources"] + 1))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", compiler))
        monkeypatch.setattr(window, "_refresh_project_watch_snapshot", lambda: None)
        monkeypatch.setattr(window, "_update_window_title", lambda: None)
        monkeypatch.setattr(window, "_update_compile_availability", lambda: None)
        monkeypatch.setattr(window, "_start_compile_cycle", lambda *args, **kwargs: pytest.fail("_start_compile_cycle should not run"))
        window._do_clean_all_and_reconstruct()

        assert preview_reasons == ["SDK unavailable, compile preview disabled"]
        assert captured["resources"] == 1
        assert "Editing-only mode: SDK unavailable, compile preview disabled" in window.statusBar().currentMessage()
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_clean_all_and_reconstruct_is_unavailable_when_preview_target_is_still_missing(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.ui.main_window import MainWindow

        class _PreviewIncompatibleCompiler:
            app_root_arg = "example"

            def can_build(self):
                return True

            def get_build_error(self):
                return ""

            def get_preview_build_error(self):
                return "Preview build target unavailable: make defines neither 'main.exe' nor 'main'."

            def ensure_preview_build_available(self, force=False):
                return False

            def set_screen_size(self, width, height):
                return None

            def is_preview_running(self):
                return False

            def is_exe_ready(self):
                return False

            def stop_exe(self):
                return None

            def cleanup(self):
                return None

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "CleanAllPreviewTargetMissingDemo"
        project = _create_project(project_dir, "CleanAllPreviewTargetMissingDemo", sdk_root)

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _PreviewIncompatibleCompiler()))
        _open_project_window(window, project, project_dir, sdk_root)

        monkeypatch.setattr(
            "ui_designer.ui.main_window.clean_project_for_reconstruct",
            lambda *args, **kwargs: pytest.fail("clean_project_for_reconstruct should not run"),
        )
        monkeypatch.setattr(
            window,
            "_save_project_files",
            lambda *args, **kwargs: pytest.fail("_save_project_files should not run"),
        )
        monkeypatch.setattr(window, "_start_compile_cycle", lambda *args, **kwargs: pytest.fail("_start_compile_cycle should not run"))

        assert window._clean_all_action.isEnabled() is False
        window._do_clean_all_and_reconstruct()

        assert "Clean All skipped: missing preview build targets cannot be recovered by reconstruction" in (
            window.statusBar().currentMessage()
        )
        assert window._clean_all_action.toolTip() == (
            "Destructive recovery: delete project-side generated/code files outside the preserved "
            "Designer source set and reconstruct the project (Ctrl+Shift+F5). "
            "Project: open. Saved project: saved. SDK: valid. Preview: editing only. "
            "Unavailable: missing preview build targets cannot be recovered by reconstruction: "
            "Preview build target unavailable: make defines neither 'main.exe' nor 'main'."
        )
        build_action = next(action for action in window.menuBar().actions() if action.text() == "Build")
        assert build_action.toolTip() == (
            "Compile previews, generate resources, or reconstruct a project from Designer sources. "
            "Project: open. SDK: valid. Compile: unavailable. Rebuild: unavailable. Reconstruct: unavailable. Auto compile: on. "
            f"Preview: editing only. Source resources: available. Resource directory: {window._get_eguiproject_resource_dir()}."
        )
        assert "cannot recover missing build targets" in window.debug_panel._output.toPlainText()
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_clean_all_and_reconstruct_skips_force_rebuild_when_clean_target_is_unavailable(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.model.project_cleaner import ProjectCleanReport
        from ui_designer.ui.main_window import MainWindow

        class _BuildReadyCompiler:
            app_root_arg = "example"

            def can_build(self):
                return True

            def get_build_error(self):
                return ""

            def get_preview_build_error(self):
                return ""

            def is_preview_running(self):
                return False

            def stop_exe(self):
                return None

            def cleanup(self):
                return None

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "CleanAllMissingCleanTargetDemo"
        project = _create_project(project_dir, "CleanAllMissingCleanTargetDemo", sdk_root)

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _AutoRetryCompiler(project_dir, exe_ready=True)))
        _open_project_window(window, project, project_dir, sdk_root)
        window._block_auto_compile_retry("boom")
        window._block_rebuild_retry("make: *** No rule to make target 'clean'.  Stop.")
        compile_cycle_calls = []

        monkeypatch.setattr("ui_designer.ui.main_window.QMessageBox.warning", lambda *args: QMessageBox.Yes)
        monkeypatch.setattr(
            "ui_designer.ui.main_window.clean_project_for_reconstruct",
            lambda project_path: ProjectCleanReport(removed_files=1, removed_dirs=0),
        )
        monkeypatch.setattr(window, "_persist_designer_state_only", lambda project_path: None)
        monkeypatch.setattr(window, "_shutdown_async_activity", lambda wait_ms=500: None)
        monkeypatch.setattr(window, "_cleanup_compiler", lambda stop_exe=False: None)
        monkeypatch.setattr(
            window,
            "_save_project_files",
            lambda project_path, reset_scaffold=False: {".designer/uicode.c": "// reconstructed\n"},
        )
        monkeypatch.setattr(window, "_ensure_resources_generated", lambda: None)
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _BuildReadyCompiler()))
        monkeypatch.setattr(window, "_refresh_project_watch_snapshot", lambda: None)
        monkeypatch.setattr(window, "_update_window_title", lambda: None)
        monkeypatch.setattr(window, "_switch_to_python_preview", lambda reason="": None)
        monkeypatch.setattr(window, "_start_compile_cycle", lambda *args, **kwargs: pytest.fail("_start_compile_cycle should not run"))

        window._do_clean_all_and_reconstruct()
        window.auto_compile = True
        monkeypatch.setattr(
            window,
            "_start_compile_cycle",
            lambda *args, **kwargs: compile_cycle_calls.append(kwargs.get("force_rebuild", False)),
        )
        window._run_auto_compile_cycle()

        assert "Preview rerun skipped: make: *** No rule to make target 'clean'.  Stop." in window.statusBar().currentMessage()
        assert "Preview rerun skipped after reconstruction: make: *** No rule to make target 'clean'.  Stop." in (
            window.debug_panel._output.toPlainText()
        )
        assert compile_cycle_calls == [False]
        assert window._auto_compile_retry_block_reason == ""
        assert window._compile_action.isEnabled() is True
        assert window._rebuild_action.isEnabled() is False
        assert window._rebuild_retry_block_reason == "make: *** No rule to make target 'clean'.  Stop."
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_clean_all_confirmation_mentions_preview_rerun_limitation_when_clean_target_is_unavailable(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "CleanAllConfirmMissingCleanTargetDemo"
        project = _create_project(project_dir, "CleanAllConfirmMissingCleanTargetDemo", sdk_root)
        compiler = _AutoRetryCompiler(project_dir, exe_ready=True)

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", compiler))

        _open_project_window(window, project, project_dir, sdk_root)
        window._block_rebuild_retry("make: *** No rule to make target 'clean'.  Stop.")

        text = window._clean_all_confirmation_text()

        assert "Current preview rerun limitation:" in text
        assert "make: *** No rule to make target 'clean'.  Stop." in text
        assert "preview rerun will be skipped until this is resolved" in text
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_clean_all_and_reconstruct_stops_when_user_declines(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "CleanAllCancelDemo"
        project = _create_project(project_dir, "CleanAllCancelDemo", sdk_root)

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _AutoRetryCompiler(project_dir, exe_ready=True)))
        _open_project_window(window, project, project_dir, sdk_root)

        monkeypatch.setattr("ui_designer.ui.main_window.QMessageBox.warning", lambda *args: QMessageBox.No)
        monkeypatch.setattr("ui_designer.ui.main_window.clean_project_for_reconstruct", lambda *args, **kwargs: pytest.fail("cleanup should not run"))
        monkeypatch.setattr(window, "_save_project_files", lambda *args, **kwargs: pytest.fail("_save_project_files should not run"))
        monkeypatch.setattr(window, "_start_compile_cycle", lambda *args, **kwargs: pytest.fail("_start_compile_cycle should not run"))

        window._do_clean_all_and_reconstruct()

        assert "Opened" in window.statusBar().currentMessage()
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_startup_notice_mentions_clean_all_once(self, qapp, isolated_config):
        from ui_designer.ui.main_window import MainWindow

        first = MainWindow("")
        first.show()
        qapp.processEvents()

        assert "Build > Clean All && Reconstruct" in first.statusBar().currentMessage()
        assert first._config.show_clean_all_startup_notice is False

        _close_window(first)

        second = MainWindow("")
        second.show()
        qapp.processEvents()

        assert "Build > Clean All && Reconstruct" not in second.statusBar().currentMessage()
        _close_window(second)

    def test_startup_notice_skips_clean_all_tip_when_reconstruction_cannot_recover_preview_target(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.ui.main_window import MainWindow

        class _PreviewIncompatibleCompiler:
            app_root_arg = "example"

            def can_build(self):
                return True

            def get_build_error(self):
                return ""

            def get_preview_build_error(self):
                return "Preview build target unavailable: make defines neither 'main.exe' nor 'main'."

            def ensure_preview_build_available(self, force=False):
                return False

            def set_screen_size(self, width, height):
                return None

            def is_preview_running(self):
                return False

            def is_exe_ready(self):
                return False

            def stop_exe(self):
                return None

            def cleanup(self):
                return None

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "StartupNoticePreviewTargetMissingDemo"
        project = _create_project(project_dir, "StartupNoticePreviewTargetMissingDemo", sdk_root)

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _PreviewIncompatibleCompiler()))

        _open_project_window(window, project, project_dir, sdk_root)
        window.show()
        qapp.processEvents()

        assert window._clean_all_action.isEnabled() is False
        assert "Build > Clean All && Reconstruct" not in window.statusBar().currentMessage()
        assert window._config.show_clean_all_startup_notice is True
        window._undo_manager.mark_all_saved()
        _close_window(window)

    @pytest.mark.skip(reason="removed SDK download workflow from Designer")
    def test_download_sdk_failure_mentions_target_dir(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        target_dir = tmp_path / "sdk_cache"
        warnings = []

        window = MainWindow("")
        monkeypatch.setattr("ui_designer.ui.main_window.default_sdk_install_dir", lambda: str(target_dir))
        monkeypatch.setattr(
            "ui_designer.ui.main_window.ensure_sdk_downloaded",
            lambda target, progress_callback=None: (_ for _ in ()).throw(RuntimeError("network blocked")),
        )
        monkeypatch.setattr("ui_designer.ui.main_window.QMessageBox.warning", lambda *args: warnings.append(args[1:]))

        result = window._download_sdk()

        assert result == ""
        assert warnings
        assert warnings[0][0] == "Download SDK Failed"
        assert str(target_dir) in warnings[0][1]
        assert "GitHub archive" in warnings[0][1]
        assert "install git for clone fallback" in warnings[0][1]
        _close_window(window)

    @pytest.mark.skip(reason="removed SDK download workflow from Designer")
    def test_initial_sdk_prompt_shows_target_dir_and_dispatches_download(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        target_dir = tmp_path / "sdk_cache"
        captured = {}

        class FakeMessageBox:
            Information = QMessageBox.Information
            AcceptRole = QMessageBox.AcceptRole
            ActionRole = QMessageBox.ActionRole
            RejectRole = QMessageBox.RejectRole

            def __init__(self, parent=None):
                self.parent = parent
                self._buttons = []
                self._clicked = None

            def setWindowTitle(self, title):
                captured["title"] = title

            def setIcon(self, icon):
                captured["icon"] = icon

            def setText(self, text):
                captured["text"] = text

            def setInformativeText(self, text):
                captured["info"] = text

            def addButton(self, text, role):
                button = object()
                self._buttons.append((text, role, button))
                if text == "Download SDK Automatically":
                    self._clicked = button
                return button

            def exec_(self):
                return 0

            def clickedButton(self):
                return self._clicked

        download_calls = []

        window = MainWindow("")
        monkeypatch.setattr("ui_designer.ui.main_window.default_sdk_install_dir", lambda: str(target_dir))
        monkeypatch.setattr("ui_designer.ui.main_window.QMessageBox", FakeMessageBox)
        monkeypatch.setattr(window, "_download_sdk", lambda: download_calls.append("download"))

        window.maybe_prompt_initial_sdk_setup()

        assert captured["title"] == "Prepare EmbeddedGUI SDK"
        assert "No EmbeddedGUI SDK was detected." in captured["text"]
        assert str(target_dir) in captured["info"]
        assert "Automatic setup order:" in captured["info"]
        assert "GitHub archive" in captured["info"]
        assert isolated_config.sdk_setup_prompted is True
        assert download_calls == ["download"]
        _close_window(window)

    def test_initialize_unmanaged_sdk_example_generates_project_and_uses_existing_dimensions(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.project import Project
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        app_dir = sdk_root / "example" / "LegacyApp"
        app_dir.mkdir(parents=True)
        (app_dir / "build.mk").write_text("# legacy\n", encoding="utf-8")
        (app_dir / "app_egui_config.h").write_text(
            "#define EGUI_CONFIG_SCEEN_WIDTH  480\n#define EGUI_CONFIG_SCEEN_HEIGHT 272\n",
            encoding="utf-8",
        )

        window = MainWindow(str(sdk_root))
        opened = {}

        def fake_open_project_path(path, preferred_sdk_root="", silent=False):
            opened["path"] = path
            opened["preferred_sdk_root"] = preferred_sdk_root
            opened["silent"] = silent

        monkeypatch.setattr(window, "_open_project_path", fake_open_project_path)
        monkeypatch.setattr("ui_designer.ui.main_window.QMessageBox.question", lambda *args, **kwargs: QMessageBox.Yes)

        window._initialize_unmanaged_sdk_example(
            {
                "app_name": "LegacyApp",
                "app_dir": str(app_dir),
            },
            str(sdk_root),
        )

        project_path = app_dir / "LegacyApp.egui"
        saved = _load_project(project_path)
        assert project_path.is_file()
        assert saved.screen_width == 480
        assert saved.screen_height == 272
        assert (app_dir / "resource" / "src" / "app_resource_config.json").is_file()
        assert (app_dir / "resource" / "src" / ".designer" / "app_resource_config_designer.json").is_file()
        assert opened == {
            "path": os.path.normpath(os.path.abspath(project_path)),
            "preferred_sdk_root": os.path.normpath(os.path.abspath(sdk_root)),
            "silent": False,
        }
        _close_window(window)

    def test_initialize_unmanaged_sdk_example_without_split_designer_wrapper_uses_defaults(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.project import Project
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        app_dir = sdk_root / "example" / "LegacyWrappedApp"
        app_dir.mkdir(parents=True)
        (app_dir / "build.mk").write_text("# legacy\n", encoding="utf-8")
        (app_dir / "app_egui_config.h").write_text(
            '#include "app_egui_config_designer.h"\n',
            encoding="utf-8",
        )
        (app_dir / "app_egui_config_designer.h").write_text(
            "#define EGUI_CONFIG_SCEEN_WIDTH  320\n#define EGUI_CONFIG_SCEEN_HEIGHT 320\n",
            encoding="utf-8",
        )

        window = MainWindow(str(sdk_root))
        opened = {}

        def fake_open_project_path(path, preferred_sdk_root="", silent=False):
            opened["path"] = path
            opened["preferred_sdk_root"] = preferred_sdk_root
            opened["silent"] = silent

        monkeypatch.setattr(window, "_open_project_path", fake_open_project_path)
        monkeypatch.setattr("ui_designer.ui.main_window.QMessageBox.question", lambda *args, **kwargs: QMessageBox.Yes)

        window._initialize_unmanaged_sdk_example(
            {
                "app_name": "LegacyWrappedApp",
                "app_dir": str(app_dir),
            },
            str(sdk_root),
        )

        project_path = app_dir / "LegacyWrappedApp.egui"
        saved = _load_project(project_path)
        assert saved.screen_width == 240
        assert saved.screen_height == 320
        assert opened["path"] == os.path.normpath(os.path.abspath(project_path))
        _close_window(window)

    def test_initialize_unmanaged_sdk_example_cancels_when_user_declines_initialization(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        app_dir = sdk_root / "example" / "LegacyDeclined"
        app_dir.mkdir(parents=True)
        (app_dir / "build.mk").write_text("# legacy\n", encoding="utf-8")

        window = MainWindow(str(sdk_root))

        monkeypatch.setattr("ui_designer.ui.main_window.QMessageBox.question", lambda *args, **kwargs: QMessageBox.No)
        monkeypatch.setattr(window, "_open_project_path", lambda *args, **kwargs: pytest.fail("_open_project_path should not be called"))

        window._initialize_unmanaged_sdk_example(
            {
                "app_name": "LegacyDeclined",
                "app_dir": str(app_dir),
            },
            str(sdk_root),
        )

        assert not (app_dir / "LegacyDeclined.egui").exists()
        assert not (app_dir / ".designer").exists()
        _close_window(window)

    def test_initialize_unmanaged_sdk_example_warns_on_eguiproject_conflict(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        app_dir = sdk_root / "example" / "LegacyConflict"
        (app_dir / ".eguiproject").mkdir(parents=True)
        (app_dir / "build.mk").write_text("# legacy\n", encoding="utf-8")

        window = MainWindow(str(sdk_root))
        warnings = []

        monkeypatch.setattr("ui_designer.ui.main_window.QMessageBox.warning", lambda *args: warnings.append(args[1:]))
        monkeypatch.setattr(window, "_open_project_path", lambda *args, **kwargs: pytest.fail("_open_project_path should not be called"))

        window._initialize_unmanaged_sdk_example(
            {
                "app_name": "LegacyConflict",
                "app_dir": str(app_dir),
            },
            str(sdk_root),
        )

        assert warnings
        assert warnings[0][0] == "Designer Project Conflict"
        assert not (app_dir / "LegacyConflict.egui").exists()
        _close_window(window)

    def test_open_recent_project_can_remove_missing_entry(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        missing_project = tmp_path / "MissingApp" / "MissingApp.egui"
        window = MainWindow("")
        isolated_config.last_project_path = str(missing_project)
        isolated_config.recent_projects = [
            {
                "project_path": str(missing_project),
                "sdk_root": "",
                "display_name": "MissingApp",
            }
        ]
        window._update_recent_menu()

        monkeypatch.setattr("ui_designer.ui.main_window.QMessageBox.question", lambda *args, **kwargs: QMessageBox.Yes)

        window._open_recent_project(str(missing_project))

        assert isolated_config.recent_projects == []
        assert isolated_config.last_project_path == ""
        assert window._recent_menu.actions()[0].text() == "(No recent projects)"
        assert window._recent_menu.actions()[0].toolTip() == "No recent projects are available."
        assert window._recent_menu.actions()[0].statusTip() == window._recent_menu.actions()[0].toolTip()
        recent_widget = window._welcome_page._recent_list.itemAt(0).widget()
        assert recent_widget is not None
        assert "No recent projects" in (recent_widget.accessibleName() or "")
        assert any("No recent projects" in (lb.text() or "") for lb in recent_widget.findChildren(QLabel))
        assert "Removed missing project" in window.statusBar().currentMessage()
        _close_window(window)

    def test_recent_menu_action_uses_recovered_cached_sdk_root(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        cached_sdk = tmp_path / "config" / "sdk" / "EmbeddedGUI"
        _create_sdk_root(cached_sdk)
        project_path = tmp_path / "DemoApp" / "DemoApp.egui"
        project_path.parent.mkdir(parents=True)
        project_path.write_text("<egui />\n", encoding="utf-8")
        isolated_config.recent_projects = [
            {
                "project_path": str(project_path),
                "sdk_root": str(tmp_path / "missing_sdk"),
                "display_name": "DemoApp",
            }
        ]
        captured = {}

        window = MainWindow("")
        monkeypatch.setattr("ui_designer.ui.main_window.default_sdk_install_dir", lambda: str(cached_sdk))
        monkeypatch.setattr(window, "_open_recent_project", lambda path, sdk_root="": captured.update({"path": path, "sdk_root": sdk_root}))

        window._update_recent_menu()
        window._recent_menu.actions()[0].trigger()

        assert captured["path"] == str(project_path)
        assert captured["sdk_root"] == os.path.normpath(os.path.abspath(cached_sdk))
        assert window._recent_menu.actions()[0].toolTip() == (
            f"Project: {project_path}\nSDK root: {os.path.normpath(os.path.abspath(cached_sdk))}."
        )
        assert window._recent_menu.actions()[0].statusTip() == window._recent_menu.actions()[0].toolTip()
        _close_window(window)

    def test_recent_menu_marks_missing_project_entries(self, qapp, isolated_config, tmp_path):
        from ui_designer.ui.main_window import MainWindow

        missing_project = tmp_path / "MissingApp" / "MissingApp.egui"
        isolated_config.recent_projects = [
            {
                "project_path": str(missing_project),
                "sdk_root": "",
                "display_name": "MissingApp",
            }
        ]

        window = MainWindow("")
        window._update_recent_menu()

        action = window._recent_menu.actions()[0]
        assert action.text() == "[Missing] MissingApp"
        assert "Project path is missing" in action.toolTip()
        assert action.statusTip() == action.toolTip()
        _close_window(window)

    def test_recent_menu_skips_no_op_rebuilds(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        project_path = tmp_path / "DemoApp" / "DemoApp.egui"
        project_path.parent.mkdir(parents=True)
        project_path.write_text("<egui />\n", encoding="utf-8")
        isolated_config.recent_projects = [
            {
                "project_path": str(project_path),
                "sdk_root": "",
                "display_name": "DemoApp",
            }
        ]

        window = MainWindow("")
        monkeypatch.setattr(window, "_resolve_ui_sdk_root", lambda *args: "")
        if hasattr(window._recent_menu, "_recent_menu_snapshot"):
            delattr(window._recent_menu, "_recent_menu_snapshot")

        clear_calls = 0
        original_clear = window._recent_menu.clear

        def counted_clear():
            nonlocal clear_calls
            clear_calls += 1
            return original_clear()

        monkeypatch.setattr(window._recent_menu, "clear", counted_clear)

        window._update_recent_menu()
        assert clear_calls == 1

        clear_calls = 0
        window._update_recent_menu()
        assert clear_calls == 0

        isolated_config.recent_projects = []
        window._update_recent_menu()
        assert clear_calls == 1
        assert window._recent_menu.actions()[0].text() == "(No recent projects)"
        _close_window(window)

    def test_recent_and_view_submenu_categories_expose_status_hints(self, qapp, isolated_config, tmp_path, monkeypatch):
        from PyQt5.QtGui import QPixmap
        from ui_designer.ui import main_window as main_window_module
        from ui_designer.ui.main_window import MainWindow

        monkeypatch.setattr(main_window_module, "apply_theme", lambda app, theme, density="standard": None)

        window = MainWindow("")
        file_menu = next(action.menu() for action in window.menuBar().actions() if action.text() == "File")
        view_menu = next(action.menu() for action in window.menuBar().actions() if action.text() == "View")
        background_menu = next(action.menu() for action in view_menu.actions() if action.text() == "Background Mockup")

        assert window._recent_menu.menuAction().toolTip() == "Open a recently used project. No recent projects are available."
        assert window._recent_menu.menuAction().statusTip() == window._recent_menu.menuAction().toolTip()

        project_path = tmp_path / "DemoApp" / "DemoApp.egui"
        project_path.parent.mkdir(parents=True)
        project_path.write_text("<egui />\n", encoding="utf-8")
        isolated_config.recent_projects = [
            {
                "project_path": str(project_path),
                "sdk_root": "",
                "display_name": "DemoApp",
            }
        ]
        monkeypatch.setattr(window, "_resolve_ui_sdk_root", lambda *args: "")
        window._update_recent_menu()
        assert window._recent_menu.menuAction().toolTip() == "Open a recently used project. 1 recent project available."
        assert window._recent_menu.menuAction().statusTip() == window._recent_menu.menuAction().toolTip()
        assert window._recent_menu.actions()[0].toolTip() == f"Project: {project_path}\nSDK root: not recorded."
        assert window._recent_menu.actions()[0].statusTip() == window._recent_menu.actions()[0].toolTip()

        file_actions = {action.text(): action for action in file_menu.actions() if action.text()}
        view_actions = {action.text(): action for action in view_menu.actions() if action.text()}
        background_actions = {action.text(): action for action in background_menu.actions() if action.text()}

        assert file_actions["Recent"].toolTip() == window._recent_menu.menuAction().toolTip()
        assert file_actions["Recent"].statusTip() == file_actions["Recent"].toolTip()
        assert view_actions["Theme"].toolTip() == "Choose the Designer theme. Current theme: Dark."
        assert view_actions["Theme"].statusTip() == view_actions["Theme"].toolTip()
        assert view_actions["UI Density"].toolTip() == "Choose standard or roomy UI density."
        assert view_actions["UI Density"].statusTip() == view_actions["UI Density"].toolTip()
        assert view_actions["Workspace"].toolTip() == "Choose a workspace panel to show. Current panel: Project."
        assert view_actions["Workspace"].statusTip() == view_actions["Workspace"].toolTip()
        assert view_actions["Inspector"].toolTip() == "Choose an inspector section to show. Current section: Properties."
        assert view_actions["Inspector"].statusTip() == view_actions["Inspector"].toolTip()
        assert view_actions["Tools"].toolTip() == "Choose a bottom tools panel to show. Current section: Diagnostics. Panel hidden."
        assert view_actions["Tools"].statusTip() == view_actions["Tools"].toolTip()
        assert view_actions["Grid Size"].toolTip() == "Choose the grid snap size. Current snap: 8px. Grid visible."
        assert view_actions["Grid Size"].statusTip() == view_actions["Grid Size"].toolTip()
        assert view_actions["Background Mockup"].toolTip() == (
            "Manage the preview background mockup image. Current mockup: none loaded. Opacity: 30%."
        )
        assert view_actions["Background Mockup"].statusTip() == view_actions["Background Mockup"].toolTip()
        assert background_actions["Opacity"].toolTip() == "Choose the mockup image opacity. Current mockup: none loaded. Opacity: 30%."
        assert background_actions["Opacity"].statusTip() == background_actions["Opacity"].toolTip()

        window._set_theme("light")
        window._set_show_grid(False)
        window._set_grid_size(12)
        window.preview_panel.set_background_image(QPixmap(8, 8))
        window.preview_panel.set_background_image_visible(False)
        window._set_background_opacity(0.7)

        assert view_actions["Theme"].toolTip() == "Choose the Designer theme. Current theme: Light."
        assert view_actions["UI Density"].toolTip() == "Choose standard or roomy UI density."
        assert view_actions["Grid Size"].toolTip() == "Choose the grid snap size. Current snap: 12px. Grid hidden."
        assert view_actions["Background Mockup"].toolTip() == (
            "Manage the preview background mockup image. Current mockup: hidden. Opacity: 70%."
        )
        assert background_actions["Opacity"].toolTip() == "Choose the mockup image opacity. Current mockup: hidden. Opacity: 70%."
        _close_window(window)

    def test_generate_resources_action_exposes_status_hint(self, qapp, isolated_config):
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")
        action = window._generate_resources_action

        assert action.toolTip() == (
            "Run resource generation (app_resource_generate.py) to produce\n"
            f"C source files from {RESOURCE_DIR_RELPATH}/ assets and widget config. "
            "Project: none. SDK: invalid. Source resources: missing. Resource directory: none."
        )
        assert action.statusTip() == action.toolTip()
        _close_window(window)

    def test_build_menu_actions_expose_status_hints(self, qapp, isolated_config, tmp_path):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "BuildHintsDemo"
        project = _create_project(project_dir, "BuildHintsDemo", sdk_root)

        window = MainWindow("")
        actions = _actions_by_text(
            window._compile_action,
            window._rebuild_action,
            window._clean_all_action,
            window.auto_compile_action,
            window._stop_action,
            window._generate_resources_action,
        )
        build_action = next(action for action in window.menuBar().actions() if action.text() == "Build")

        assert actions["Build EXE && Run"].toolTip() == (
            "Compile the current project and run the preview (F5). "
            "Project: none. SDK: invalid. Preview: stopped. Unavailable: open a project first."
        )
        assert actions["Rebuild EGUI Project"].toolTip() == (
            "Clean and rebuild the whole EGUI project, then rerun the preview (Ctrl+F5). "
            "Project: none. SDK: invalid. Preview: stopped. Unavailable: open a project first."
        )
        assert actions["Clean All && Reconstruct"].toolTip() == (
            "Destructive recovery: delete project-side generated/code files outside the preserved "
            "Designer source set, reconstruct the project, and rerun the preview (Ctrl+Shift+F5). "
            "Project: none. Saved project: unsaved. SDK: invalid. Preview: stopped. Unavailable: open a project first."
        )
        assert actions["Auto Compile"].toolTip() == (
            "Automatically compile and rerun the preview after changes. "
            "Project: none. SDK: invalid. Preview: stopped. Unavailable: open a project first."
        )
        assert actions["Stop Exe"].toolTip() == (
            "Stop the running preview executable. Project: none. Preview: stopped. "
            "Unavailable: preview is not running."
        )
        assert actions["Generate Resources"].toolTip() == (
            "Run resource generation (app_resource_generate.py) to produce\n"
            f"C source files from {RESOURCE_DIR_RELPATH}/ assets and widget config. "
            "Project: none. SDK: invalid. Source resources: missing. Resource directory: none."
        )
        assert build_action.toolTip() == (
            "Compile previews, generate resources, or reconstruct a project from Designer sources. "
            "Project: none. SDK: invalid. Compile: unavailable. Rebuild: unavailable. Reconstruct: unavailable. Auto compile: on. "
            "Preview: stopped. Source resources: missing. Resource directory: none."
        )
        for action in actions.values():
            assert action.statusTip() == action.toolTip()

        window.project = project
        window.project_root = str(sdk_root)
        window.compiler = _DisabledCompiler()
        window._update_compile_availability()
        project_resources_dir = project.get_eguiproject_resource_dir()

        assert actions["Build EXE && Run"].toolTip() == (
            "Compile the current project and run the preview (F5). "
            "Project: open. SDK: valid. Preview: editing only. Unavailable: preview disabled for test."
        )
        assert actions["Rebuild EGUI Project"].toolTip() == (
            "Clean and rebuild the whole EGUI project, then rerun the preview (Ctrl+F5). "
            "Project: open. SDK: valid. Preview: editing only. Unavailable: preview disabled for test."
        )
        assert actions["Clean All && Reconstruct"].toolTip() == (
            "Destructive recovery: delete project-side generated/code files outside the preserved "
            "Designer source set, reconstruct the project, and rerun the preview (Ctrl+Shift+F5). "
            "Project: open. Saved project: unsaved. SDK: valid. Preview: editing only. Unavailable: save the project first."
        )
        assert actions["Auto Compile"].toolTip() == (
            "Automatically compile and rerun the preview after changes. "
            "Project: open. SDK: valid. Preview: editing only. Unavailable: preview disabled for test."
        )
        assert build_action.toolTip() == (
            "Compile previews, generate resources, or reconstruct a project from Designer sources. "
            "Project: open. SDK: valid. Compile: unavailable. Rebuild: unavailable. Reconstruct: unavailable. Auto compile: on. "
            f"Preview: editing only. Source resources: available. Resource directory: {project_resources_dir}."
        )

        class _BuildReadyCompiler:
            def can_build(self):
                return True

            def is_preview_running(self):
                return False

            def stop_exe(self):
                return None

            def cleanup(self):
                return None

        window._project_dir = str(project_dir)
        window.compiler = _BuildReadyCompiler()
        window._update_compile_availability()
        resources_dir = window._get_eguiproject_resource_dir()

        assert actions["Build EXE && Run"].isEnabled() is True
        assert actions["Build EXE && Run"].toolTip() == (
            "Compile the current project and run the preview (F5). Project: open. SDK: valid. Preview: stopped."
        )
        assert actions["Rebuild EGUI Project"].toolTip() == (
            "Clean and rebuild the whole EGUI project, then rerun the preview (Ctrl+F5). "
            "Project: open. SDK: valid. Preview: stopped."
        )
        assert actions["Clean All && Reconstruct"].isEnabled() is True
        assert actions["Clean All && Reconstruct"].toolTip() == (
            "Destructive recovery: delete project-side generated/code files outside the preserved "
            "Designer source set, reconstruct the project, and rerun the preview (Ctrl+Shift+F5). "
            "Project: open. Saved project: saved. SDK: valid. Preview: stopped."
        )
        assert actions["Auto Compile"].toolTip() == (
            "Automatically compile and rerun the preview after changes. Project: open. SDK: valid. Preview: stopped."
        )
        assert actions["Stop Exe"].toolTip() == (
            "Stop the running preview executable. Project: open. Preview: stopped. "
            "Unavailable: preview is not running."
        )
        assert actions["Generate Resources"].toolTip() == (
            "Run resource generation (app_resource_generate.py) to produce\n"
            f"C source files from {RESOURCE_DIR_RELPATH}/ assets and widget config. "
            f"Project: open. SDK: valid. Source resources: available. Resource directory: {resources_dir}."
        )
        assert build_action.toolTip() == (
            "Compile previews, generate resources, or reconstruct a project from Designer sources. "
            "Project: open. SDK: valid. Compile: available. Rebuild: available. Reconstruct: available. Auto compile: on. "
            f"Preview: stopped. Source resources: available. Resource directory: {resources_dir}."
        )

        window.preview_panel.is_python_preview_active = lambda: True
        window._update_compile_availability()

        assert actions["Build EXE && Run"].toolTip() == (
            "Compile the current project and run the preview (F5). Project: open. SDK: valid. Preview: python preview."
        )
        assert actions["Rebuild EGUI Project"].toolTip() == (
            "Clean and rebuild the whole EGUI project, then rerun the preview (Ctrl+F5). "
            "Project: open. SDK: valid. Preview: python preview."
        )
        assert build_action.toolTip() == (
            "Compile previews, generate resources, or reconstruct a project from Designer sources. "
            "Project: open. SDK: valid. Compile: available. Rebuild: available. Reconstruct: available. Auto compile: on. "
            f"Preview: python preview. Source resources: available. Resource directory: {resources_dir}."
        )

        window.preview_panel.is_python_preview_active = lambda: False
        window._update_compile_availability()

        window.auto_compile_action.setChecked(False)

        assert build_action.toolTip() == (
            "Compile previews, generate resources, or reconstruct a project from Designer sources. "
            "Project: open. SDK: valid. Compile: available. Rebuild: available. Reconstruct: available. Auto compile: off. "
            f"Preview: stopped. Source resources: available. Resource directory: {resources_dir}."
        )
        for action in actions.values():
            assert action.statusTip() == action.toolTip()
        _close_window(window)

    def test_view_panel_navigation_actions_expose_status_hints(self, qapp, isolated_config):
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")
        actions = _actions_by_text(
            *window._workspace_view_actions.values(),
            *window._inspector_view_actions.values(),
            *window._tools_view_actions.values(),
        )

        assert actions["Project"].toolTip() == (
            "Currently showing the Project workspace panel. "
            "View: List view. Active page: none. Startup page: none."
        )
        assert actions["Project"].statusTip() == actions["Project"].toolTip()
        assert actions["Structure"].toolTip() == "Show the Structure workspace panel. Current page: none. Selection: none."
        assert actions["Structure"].statusTip() == actions["Structure"].toolTip()
        assert actions["Components"].toolTip() == "Show the Components workspace panel. Current page: none. Insert target: unavailable."
        assert actions["Components"].statusTip() == actions["Components"].toolTip()
        assert actions["Assets"].toolTip() == "Show the Assets workspace panel. Current page: none."
        assert actions["Assets"].statusTip() == actions["Assets"].toolTip()
        assert actions["Properties"].toolTip() == (
            "Currently showing the Properties inspector section. Current page: none. Selection: none."
        )
        assert actions["Properties"].statusTip() == actions["Properties"].toolTip()
        assert actions["Animations"].toolTip() == (
            "Show the Animations inspector section. Current page: none. Selection: none."
        )
        assert actions["Animations"].statusTip() == actions["Animations"].toolTip()
        assert actions["Page"].toolTip() == "Show the Page inspector section. Current page: none. Selection: none."
        assert actions["Page"].statusTip() == actions["Page"].toolTip()
        assert actions["Diagnostics"].toolTip() == "Show the Diagnostics tools panel. Current page: none. Panel hidden."
        assert actions["Diagnostics"].statusTip() == actions["Diagnostics"].toolTip()
        assert actions["History"].toolTip() == "Show the History tools panel. Current page: none. Panel hidden."
        assert actions["History"].statusTip() == actions["History"].toolTip()
        assert actions["Debug Output"].toolTip() == "Show the Debug Output tools panel. Current page: none. Panel hidden."
        assert actions["Debug Output"].statusTip() == actions["Debug Output"].toolTip()

        window._select_left_panel("widgets")
        window._show_inspector_tab("page")
        window._show_bottom_panel("History")

        assert actions["Project"].toolTip() == (
            "Show the Project workspace panel. View: List view. Active page: none. Startup page: none."
        )
        assert actions["Components"].toolTip() == (
            "Currently showing the Components workspace panel. "
            "Current page: none. Insert target: unavailable."
        )
        assert actions["Properties"].toolTip() == (
            "Show the Properties inspector section. Current page: none. Selection: none."
        )
        assert actions["Page"].toolTip() == (
            "Currently showing the Page inspector section. Current page: none. Selection: none."
        )
        assert actions["Diagnostics"].toolTip() == "Show the Diagnostics tools panel. Current page: none. Panel visible."
        assert actions["History"].toolTip() == "Currently showing the History tools panel. Current page: none. Panel visible."
        _close_window(window)

    def test_view_panel_navigation_actions_include_primary_display_scope_for_multi_display_projects(
        self, qapp, isolated_config, tmp_path
    ):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "MultiDisplayViewHintDemo"
        project = _create_project(
            project_dir,
            "MultiDisplayViewHintDemo",
            sdk_root,
            pages=["main_page", "detail_page"],
        )
        project.displays = [
            {"width": 320, "height": 240},
            {"width": 128, "height": 64},
        ]

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        _open_project_window(window, project, project_dir, sdk_root)

        view_menu = next(action.menu() for action in window.menuBar().actions() if action.text() == "View")
        view_actions = {action.text(): action for action in view_menu.actions() if action.text()}
        background_menu = next(action.menu() for action in view_menu.actions() if action.text() == "Background Mockup")
        background_actions = {action.text(): action for action in background_menu.actions() if action.text()}
        opacity_menu = next(action.menu() for action in background_menu.actions() if action.text() == "Opacity")
        opacity_actions = {action.text(): action for action in opacity_menu.actions() if action.text()}
        actions = _actions_by_text(
            *window._workspace_view_actions.values(),
            *window._inspector_view_actions.values(),
            *window._tools_view_actions.values(),
        )
        current_zoom = window.preview_panel._zoom_label.text()

        assert view_menu.menuAction().toolTip() == (
            "Change workspace layout, themes, preview modes, and mockup options. "
            "Theme: Dark. Density: Standard. Font size: app default. Layout: Horizontal, overlay first. "
            "Grid: visible. Snap: 8px. Mockup: none loaded. Display target: Display 0 (primary only)."
        )
        assert view_actions["Workspace"].toolTip() == (
            "Choose a workspace panel to show. Current panel: Project. Display target: Display 0 (primary only)."
        )
        assert view_actions["Inspector"].toolTip() == (
            "Choose an inspector section to show. Current section: Properties. Display target: Display 0 (primary only)."
        )
        assert view_actions["Tools"].toolTip() == (
            "Choose a bottom tools panel to show. Current section: Diagnostics. Panel hidden. "
            "Display target: Display 0 (primary only)."
        )
        assert actions["Project"].toolTip() == (
            "Currently showing the Project workspace panel. "
            "View: List view. Active page: main_page. Startup page: main_page. Display target: Display 0 (primary only)."
        )
        assert actions["Structure"].toolTip() == (
            "Show the Structure workspace panel. Current page: main_page. Selection: none. "
            "Display target: Display 0 (primary only)."
        )
        assert actions["Components"].toolTip() == (
            "Show the Components workspace panel. Current page: main_page. Insert target: root_group. "
            "Display target: Display 0 (primary only)."
        )
        assert actions["Assets"].toolTip() == (
            "Show the Assets workspace panel. Current page: main_page. Display target: Display 0 (primary only)."
        )
        assert actions["Properties"].toolTip() == (
            "Currently showing the Properties inspector section. Current page: main_page. Selection: none. "
            "Display target: Display 0 (primary only)."
        )
        assert actions["Animations"].toolTip() == (
            "Show the Animations inspector section. Current page: main_page. Selection: none. "
            "Display target: Display 0 (primary only)."
        )
        assert actions["Page"].toolTip() == (
            "Show the Page inspector section. Current page: main_page. Selection: none. "
            "Display target: Display 0 (primary only)."
        )
        assert actions["Diagnostics"].toolTip() == (
            "Show the Diagnostics tools panel. Current page: main_page. Panel hidden. "
            "Display target: Display 0 (primary only)."
        )
        assert actions["History"].toolTip() == (
            "Show the History tools panel. Current page: main_page. Panel hidden. "
            "Display target: Display 0 (primary only)."
        )
        assert actions["Debug Output"].toolTip() == (
            "Show the Debug Output tools panel. Current page: main_page. Panel hidden. "
            "Display target: Display 0 (primary only)."
        )
        assert view_actions["Vertical"].toolTip() == (
            f"Show preview and overlay stacked vertically (Ctrl+1). Current layout: Horizontal, overlay first. "
            f"Zoom: {current_zoom}. Display target: Display 0 (primary only)."
        )
        assert view_actions["Horizontal"].toolTip() == (
            f"Currently showing preview and overlay side by side (Ctrl+2). Current layout: Horizontal, overlay first. "
            f"Zoom: {current_zoom}. Display target: Display 0 (primary only)."
        )
        assert view_actions["Zoom In"].toolTip() == (
            f"Zoom in on the preview overlay (Ctrl+=). Current zoom: {current_zoom}. "
            "Display target: Display 0 (primary only)."
        )
        assert view_actions["Zoom Reset (100%)"].toolTip() == (
            f"Reset the preview overlay zoom to 100% (Ctrl+0). Current zoom: {current_zoom}. "
            "Unavailable: already at 100% zoom. Display target: Display 0 (primary only)."
        )
        assert view_actions["Show Grid"].toolTip() == (
            "Currently showing the preview grid overlay. Current snap: 8px. Display target: Display 0 (primary only)."
        )
        assert view_actions["Grid Size"].toolTip() == (
            "Choose the grid snap size. Current snap: 8px. Grid visible. Display target: Display 0 (primary only)."
        )
        assert view_actions["Background Mockup"].toolTip() == (
            "Manage the preview background mockup image. Current mockup: none loaded. Opacity: 30%. "
            "Display target: Display 0 (primary only)."
        )
        assert background_actions["Load Mockup Image..."].toolTip() == (
            "Load a mockup image behind the preview. Current mockup: none loaded. Opacity: 30%. "
            "Display target: Display 0 (primary only)."
        )
        assert background_actions["Show Mockup"].toolTip() == (
            "Toggle the background mockup image (Ctrl+M). Current mockup: none loaded. Opacity: 30%. "
            "Display target: Display 0 (primary only)."
        )
        assert background_actions["Clear Mockup Image"].toolTip() == (
            "Remove the current background mockup image. Unavailable: no mockup image loaded. "
            "Current mockup: none loaded. Opacity: 30%. Display target: Display 0 (primary only)."
        )
        assert background_actions["Opacity"].toolTip() == (
            "Choose the mockup image opacity. Current mockup: none loaded. Opacity: 30%. "
            "Display target: Display 0 (primary only)."
        )
        assert opacity_actions["30%"].toolTip() == (
            "Currently showing mockup opacity at 30%. Current mockup: none loaded. Opacity: 30%. "
            "Display target: Display 0 (primary only)."
        )
        for action in [view_menu.menuAction()] + list(view_actions.values()) + list(actions.values()) + list(background_actions.values()) + list(opacity_actions.values()):
            assert action.statusTip() == action.toolTip()
        _close_window(window)

    def test_apply_action_hint_skips_no_op_rewrites(self, qapp, isolated_config, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")
        action_type = type(window._save_action)
        action = action_type("Temp Action", window)

        tooltip_calls = 0
        original_set_tooltip = action.setToolTip

        def counted_set_tooltip(text):
            nonlocal tooltip_calls
            tooltip_calls += 1
            return original_set_tooltip(text)

        monkeypatch.setattr(action, "setToolTip", counted_set_tooltip)

        window._apply_action_hint(action, "Hint A")
        assert tooltip_calls == 1
        assert action.toolTip() == "Hint A"
        assert action.statusTip() == "Hint A"

        window._apply_action_hint(action, "Hint A")
        assert tooltip_calls == 1

        window._apply_action_hint(action, "Hint B")
        assert tooltip_calls == 2
        assert action.toolTip() == "Hint B"
        assert action.statusTip() == "Hint B"
        _close_window(window)

    def test_structure_action_hints_skip_no_op_rewrites(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "StructureHintDemo"
        first = WidgetModel("label", name="first")
        second = WidgetModel("button", name="second")
        project = _create_project_only_with_widgets(
            project_dir,
            "StructureHintDemo",
            sdk_root,
            widgets=[first, second],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        _open_project_window(window, project, project_dir, sdk_root)

        window._group_selection_action.setProperty("_action_hint_snapshot", None)

        tooltip_calls = 0
        original_set_tooltip = window._group_selection_action.setToolTip

        def counted_set_tooltip(text):
            nonlocal tooltip_calls
            tooltip_calls += 1
            return original_set_tooltip(text)

        monkeypatch.setattr(window._group_selection_action, "setToolTip", counted_set_tooltip)

        window._set_selection([first], primary=first, sync_tree=True, sync_preview=True)
        assert tooltip_calls == 1

        tooltip_calls = 0
        window._set_selection([first], primary=first, sync_tree=True, sync_preview=True)
        assert tooltip_calls == 0

        window._set_selection([first, second], primary=first, sync_tree=True, sync_preview=True)
        assert tooltip_calls == 1
        assert window._group_selection_action.toolTip() == "Group the current selection (Ctrl+G)"
        assert window._group_selection_action.statusTip() == window._group_selection_action.toolTip()
        _close_window(window)

    def test_generate_resources_action_metadata_skips_no_op_rewrites(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "GenerateResourcesHintDemo"
        project = _create_project(project_dir, "GenerateResourcesHintDemo", sdk_root)

        window = MainWindow("")
        window._generate_resources_action.setProperty("_action_hint_snapshot", None)

        tooltip_calls = 0
        original_set_tooltip = window._generate_resources_action.setToolTip

        def counted_set_tooltip(text):
            nonlocal tooltip_calls
            tooltip_calls += 1
            return original_set_tooltip(text)

        monkeypatch.setattr(window._generate_resources_action, "setToolTip", counted_set_tooltip)

        window._update_generate_resources_action_metadata()
        assert tooltip_calls == 1

        tooltip_calls = 0
        window._update_generate_resources_action_metadata()
        assert tooltip_calls == 0

        window.project = project
        window._project_dir = str(project_dir)
        window.project_root = str(sdk_root)
        window._update_generate_resources_action_metadata()
        assert tooltip_calls == 1
        assert window._generate_resources_action.toolTip() == (
            "Run resource generation (app_resource_generate.py) to produce\n"
            f"C source files from {RESOURCE_DIR_RELPATH}/ assets and widget config. "
            f"Project: open. SDK: valid. Source resources: available. Resource directory: {window._get_eguiproject_resource_dir()}."
        )
        assert window._generate_resources_action.statusTip() == window._generate_resources_action.toolTip()
        _close_window(window)

    def test_view_appearance_actions_expose_status_hints(self, qapp, isolated_config, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui import main_window as main_window_module
        from ui_designer.ui.main_window import MainWindow
        from ui_designer.ui.preview_panel import MODE_HIDDEN, MODE_VERTICAL

        monkeypatch.setattr(main_window_module, "apply_theme", lambda app, theme, density="standard": None)

        window = MainWindow("")
        actions = _actions_by_text(
            window.theme_dark_action,
            window.theme_light_action,
            window._font_size_action,
            *window._overlay_mode_actions.values(),
            window._swap_overlay_action,
            window._zoom_in_action,
            window._zoom_out_action,
            window._zoom_reset_action,
        )

        assert actions["Dark"].toolTip() == "Currently using the dark Designer theme."
        assert actions["Dark"].statusTip() == actions["Dark"].toolTip()
        assert actions["Light"].toolTip() == "Switch the Designer theme to light."
        assert actions["Light"].statusTip() == actions["Light"].toolTip()
        assert actions["Font Size..."].toolTip() == "Adjust the Designer font size. Current size: app default."
        assert actions["Font Size..."].statusTip() == actions["Font Size..."].toolTip()
        current_zoom = window.preview_panel._zoom_label.text()
        assert actions["Vertical"].toolTip() == (
            f"Show preview and overlay stacked vertically (Ctrl+1). Current layout: Horizontal, overlay first. Zoom: {current_zoom}."
        )
        assert actions["Vertical"].statusTip() == actions["Vertical"].toolTip()
        assert actions["Horizontal"].toolTip() == (
            f"Currently showing preview and overlay side by side (Ctrl+2). Current layout: Horizontal, overlay first. Zoom: {current_zoom}."
        )
        assert actions["Horizontal"].statusTip() == actions["Horizontal"].toolTip()
        assert actions["Overlay Only"].toolTip() == (
            f"Show only the overlay workspace (Ctrl+3). Current layout: Horizontal, overlay first. Zoom: {current_zoom}."
        )
        assert actions["Overlay Only"].statusTip() == actions["Overlay Only"].toolTip()
        assert actions["Swap Preview/Overlay"].toolTip() == (
            f"Swap the preview and overlay positions (Ctrl+4). Current layout: Horizontal, overlay first. Zoom: {current_zoom}."
        )
        assert actions["Swap Preview/Overlay"].statusTip() == actions["Swap Preview/Overlay"].toolTip()
        assert actions["Zoom In"].toolTip() == f"Zoom in on the preview overlay (Ctrl+=). Current zoom: {current_zoom}."
        assert actions["Zoom In"].statusTip() == actions["Zoom In"].toolTip()
        assert actions["Zoom Out"].toolTip() == f"Zoom out on the preview overlay (Ctrl+-). Current zoom: {current_zoom}."
        assert actions["Zoom Out"].statusTip() == actions["Zoom Out"].toolTip()
        assert actions["Zoom Reset (100%)"].toolTip() == (
            f"Reset the preview overlay zoom to 100% (Ctrl+0). Current zoom: {current_zoom}. Unavailable: already at 100% zoom."
        )
        assert actions["Zoom Reset (100%)"].statusTip() == actions["Zoom Reset (100%)"].toolTip()

        window._set_overlay_mode(MODE_VERTICAL)

        current_zoom = window.preview_panel._zoom_label.text()
        assert actions["Vertical"].toolTip() == (
            f"Currently showing preview and overlay stacked vertically (Ctrl+1). Current layout: Vertical, overlay first. Zoom: {current_zoom}."
        )
        assert actions["Horizontal"].toolTip() == (
            f"Show preview and overlay side by side (Ctrl+2). Current layout: Vertical, overlay first. Zoom: {current_zoom}."
        )
        assert actions["Swap Preview/Overlay"].toolTip() == (
            f"Swap the preview and overlay positions (Ctrl+4). Current layout: Vertical, overlay first. Zoom: {current_zoom}."
        )

        window._flip_overlay_layout()

        current_zoom = window.preview_panel._zoom_label.text()
        assert actions["Swap Preview/Overlay"].toolTip() == (
            f"Swap the preview and overlay positions (Ctrl+4). Current layout: Vertical, preview first. Zoom: {current_zoom}."
        )

        window.preview_panel.overlay.zoom_in()

        current_zoom = window.preview_panel._zoom_label.text()
        assert actions["Zoom In"].toolTip() == f"Zoom in on the preview overlay (Ctrl+=). Current zoom: {current_zoom}."
        assert actions["Zoom Out"].toolTip() == f"Zoom out on the preview overlay (Ctrl+-). Current zoom: {current_zoom}."
        assert actions["Zoom Reset (100%)"].toolTip() == (
            f"Reset the preview overlay zoom to 100% (Ctrl+0). Current zoom: {current_zoom}."
        )

        window._set_overlay_mode(MODE_HIDDEN)

        current_zoom = window.preview_panel._zoom_label.text()
        assert actions["Overlay Only"].toolTip() == (
            f"Currently showing only the overlay workspace (Ctrl+3). Current layout: Overlay Only. Zoom: {current_zoom}."
        )
        assert actions["Swap Preview/Overlay"].toolTip() == (
            f"Swap preview and overlay unavailable in Overlay Only layout (Ctrl+4). Current layout: Overlay Only. Zoom: {current_zoom}."
        )

        window._set_theme("light")

        assert actions["Dark"].toolTip() == "Switch the Designer theme to dark."
        assert actions["Light"].toolTip() == "Currently using the light Designer theme."

        label = WidgetModel("label", name="title")
        label.properties["font_builtin"] = "&egui_res_font_montserrat_8_4"
        window.property_panel.set_widget(label)
        font_selector = window.property_panel._editors["prop_font_builtin"]
        initial_preview_style = font_selector._preview.styleSheet()

        monkeypatch.setattr(main_window_module.QInputDialog, "getInt", lambda *args, **kwargs: (11, True))
        window._set_font_sizes()

        assert actions["Font Size..."].toolTip() == "Adjust the Designer font size. Current size: 11pt."
        assert window.debug_panel.get_output_font().pointSize() == 11
        assert window.editor_tabs.code_editor.font().pointSize() == 11
        assert window.editor_tabs.split_editor.font().pointSize() == 11
        assert font_selector._preview.styleSheet() != initial_preview_style
        assert f"font-size: {font_selector._preview_font_floor_px()}px;" in font_selector._preview.styleSheet()
        _close_window(window)

    def test_view_appearance_refreshes_tree_typography_helpers(self, qapp, isolated_config, monkeypatch):
        from ui_designer.ui import main_window as main_window_module
        from ui_designer.ui.main_window import MainWindow

        monkeypatch.setattr(main_window_module, "apply_theme", lambda app, theme, density="standard": None)

        window = MainWindow("")
        calls = {"project": 0, "tree": 0}
        original_project_refresh = window.project_dock.refresh_tree_typography
        original_tree_refresh = window.widget_tree.refresh_tree_typography

        def count_project_refresh():
            calls["project"] += 1
            return original_project_refresh()

        def count_tree_refresh():
            calls["tree"] += 1
            return original_tree_refresh()

        monkeypatch.setattr(window.project_dock, "refresh_tree_typography", count_project_refresh)
        monkeypatch.setattr(window.widget_tree, "refresh_tree_typography", count_tree_refresh)

        window._set_theme("light")
        window._set_ui_density("roomy")
        monkeypatch.setattr(main_window_module.QInputDialog, "getInt", lambda *args, **kwargs: (11, True))
        window._set_font_sizes()

        assert calls["project"] == 3
        assert calls["tree"] == 3
        _close_window(window)

    def test_view_grid_and_mockup_actions_expose_status_hints(self, qapp, isolated_config):
        from PyQt5.QtGui import QPixmap
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")
        actions = _actions_by_text(
            window._show_grid_action,
            *window._grid_size_actions.values(),
            window._load_bg_action,
            window._toggle_bg_action,
            window._clear_bg_action,
            *window._opacity_actions.values(),
        )

        assert actions["Show Grid"].toolTip() == "Currently showing the preview grid overlay. Current snap: 8px."
        assert actions["Show Grid"].statusTip() == actions["Show Grid"].toolTip()
        assert actions["No Snap"].toolTip() == "Disable grid snapping. Current snap: 8px. Grid visible."
        assert actions["No Snap"].statusTip() == actions["No Snap"].toolTip()
        assert actions["4px"].toolTip() == "Snap the overlay grid to 4px. Current snap: 8px. Grid visible."
        assert actions["4px"].statusTip() == actions["4px"].toolTip()
        assert actions["8px"].toolTip() == "Currently snapping the overlay grid to 8px. Grid visible."
        assert actions["8px"].statusTip() == actions["8px"].toolTip()
        assert actions["12px"].toolTip() == "Snap the overlay grid to 12px. Current snap: 8px. Grid visible."
        assert actions["12px"].statusTip() == actions["12px"].toolTip()
        assert actions["16px"].toolTip() == "Snap the overlay grid to 16px. Current snap: 8px. Grid visible."
        assert actions["16px"].statusTip() == actions["16px"].toolTip()
        assert actions["24px"].toolTip() == "Snap the overlay grid to 24px. Current snap: 8px. Grid visible."
        assert actions["24px"].statusTip() == actions["24px"].toolTip()
        assert actions["Load Mockup Image..."].toolTip() == (
            "Load a mockup image behind the preview. Current mockup: none loaded. Opacity: 30%."
        )
        assert actions["Load Mockup Image..."].statusTip() == actions["Load Mockup Image..."].toolTip()
        assert actions["Show Mockup"].toolTip() == (
            "Toggle the background mockup image (Ctrl+M). Current mockup: none loaded. Opacity: 30%."
        )
        assert actions["Show Mockup"].statusTip() == actions["Show Mockup"].toolTip()
        assert actions["Clear Mockup Image"].toolTip() == (
            "Remove the current background mockup image. Unavailable: no mockup image loaded. "
            "Current mockup: none loaded. Opacity: 30%."
        )
        assert actions["Clear Mockup Image"].statusTip() == actions["Clear Mockup Image"].toolTip()
        assert actions["10%"].toolTip() == "Set the mockup image opacity to 10%. Current mockup: none loaded. Opacity: 30%."
        assert actions["10%"].statusTip() == actions["10%"].toolTip()
        assert actions["20%"].toolTip() == "Set the mockup image opacity to 20%. Current mockup: none loaded. Opacity: 30%."
        assert actions["20%"].statusTip() == actions["20%"].toolTip()
        assert actions["30%"].toolTip() == "Currently showing mockup opacity at 30%. Current mockup: none loaded. Opacity: 30%."
        assert actions["30%"].statusTip() == actions["30%"].toolTip()
        assert actions["50%"].toolTip() == "Set the mockup image opacity to 50%. Current mockup: none loaded. Opacity: 30%."
        assert actions["50%"].statusTip() == actions["50%"].toolTip()
        assert actions["70%"].toolTip() == "Set the mockup image opacity to 70%. Current mockup: none loaded. Opacity: 30%."
        assert actions["70%"].statusTip() == actions["70%"].toolTip()
        assert actions["100%"].toolTip() == "Set the mockup image opacity to 100%. Current mockup: none loaded. Opacity: 30%."
        assert actions["100%"].statusTip() == actions["100%"].toolTip()

        window._set_show_grid(False)
        assert actions["Show Grid"].toolTip() == "Show the preview grid overlay. Current snap: 8px."
        assert actions["8px"].toolTip() == "Currently snapping the overlay grid to 8px. Grid hidden."

        window._set_grid_size(12)
        assert actions["Show Grid"].toolTip() == "Show the preview grid overlay. Current snap: 12px."
        assert actions["No Snap"].toolTip() == "Disable grid snapping. Current snap: 12px. Grid hidden."
        assert actions["12px"].toolTip() == "Currently snapping the overlay grid to 12px. Grid hidden."

        window.preview_panel.set_background_image(QPixmap(8, 8))
        window.preview_panel.set_background_image_visible(True)
        window._update_preview_grid_and_mockup_action_metadata()
        assert actions["Show Mockup"].toolTip() == (
            "Currently showing the background mockup image (Ctrl+M). Current mockup: visible. Opacity: 30%."
        )
        assert actions["Clear Mockup Image"].toolTip() == (
            "Remove the current background mockup image. Current mockup: visible. Opacity: 30%."
        )

        window._toggle_background_image(False)
        assert actions["Show Mockup"].toolTip() == (
            "Show the background mockup image (Ctrl+M). Current mockup: hidden. Opacity: 30%."
        )

        window._set_background_opacity(0.7)
        assert actions["70%"].toolTip() == "Currently showing mockup opacity at 70%. Current mockup: hidden. Opacity: 70%."

        window._clear_background_image()
        assert actions["Clear Mockup Image"].toolTip() == (
            "Remove the current background mockup image. Unavailable: no mockup image loaded. "
            "Current mockup: none loaded. Opacity: 70%."
        )
        _close_window(window)

    def test_edit_menu_secondary_actions_expose_status_hints(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "EditHintsDemo"
        widget = WidgetModel("label", name="title", x=12, y=16, width=100, height=24)
        project = _create_project_only_with_widgets(
            project_dir,
            "EditHintsDemo",
            sdk_root,
            widgets=[widget],
        )

        window = MainWindow("")
        actions = _actions_by_text(
            window._select_all_action,
            window._cut_action,
            window._duplicate_action,
            window._delete_action,
        )

        assert actions["Select All"].toolTip() == (
            "Select all visible widgets on the current page or all text in the focused editor (Ctrl+A). "
            "Unavailable: focus a text field or open a page with selectable widgets."
        )
        assert actions["Select All"].statusTip() == actions["Select All"].toolTip()
        assert actions["Cut"].toolTip() == "Cut the current selection (Ctrl+X). Unavailable: select at least 1 widget."
        assert actions["Cut"].statusTip() == actions["Cut"].toolTip()
        assert actions["Duplicate"].toolTip() == (
            "Duplicate the current selection (Ctrl+D). Unavailable: select at least 1 widget."
        )
        assert actions["Duplicate"].statusTip() == actions["Duplicate"].toolTip()
        assert actions["Delete"].toolTip() == "Delete the current selection (Del). Unavailable: select at least 1 widget."
        assert actions["Delete"].statusTip() == actions["Delete"].toolTip()

        _disable_window_compile(window, _DisabledCompiler)
        _open_project_window(window, project, project_dir, sdk_root)
        loaded_widget = window._current_page.root_widget.children[0]
        window._set_selection([loaded_widget], primary=loaded_widget, sync_tree=True, sync_preview=True)
        window._update_edit_actions()

        refreshed_actions = _actions_by_text(
            window._select_all_action,
            window._cut_action,
            window._duplicate_action,
            window._delete_action,
        )
        assert refreshed_actions["Select All"].toolTip() == (
            "Select all visible widgets on the current page or all text in the focused editor (Ctrl+A)."
        )
        assert refreshed_actions["Select All"].statusTip() == refreshed_actions["Select All"].toolTip()
        assert refreshed_actions["Cut"].toolTip() == "Cut the current selection (Ctrl+X)."
        assert refreshed_actions["Cut"].statusTip() == refreshed_actions["Cut"].toolTip()
        assert refreshed_actions["Duplicate"].toolTip() == "Duplicate the current selection (Ctrl+D)."
        assert refreshed_actions["Duplicate"].statusTip() == refreshed_actions["Duplicate"].toolTip()
        assert refreshed_actions["Delete"].toolTip() == "Delete the current selection (Del)."
        assert refreshed_actions["Delete"].statusTip() == refreshed_actions["Delete"].toolTip()
        _close_window(window)

    def test_edit_actions_include_primary_display_scope_for_multi_display_projects(self, qapp, isolated_config, tmp_path):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "MultiDisplayEditHintsDemo"
        widget = WidgetModel("label", name="title", x=12, y=16, width=100, height=24)
        project = _create_project_only_with_widgets(
            project_dir,
            "MultiDisplayEditHintsDemo",
            sdk_root,
            widgets=[widget],
        )
        project.displays = [
            {"width": 320, "height": 240},
            {"width": 128, "height": 64},
        ]

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        _open_project_window(window, project, project_dir, sdk_root)

        edit_action = next(action for action in window.menuBar().actions() if action.text() == "Edit")
        assert edit_action.toolTip() == (
            "Undo changes and work with the current selection. "
            "Page: main_page. Undo: unavailable. Redo: unavailable. Selection: none. "
            "Display target: Display 0 (primary only)."
        )
        assert window._undo_action.toolTip() == (
            "Undo the last change on the current page (Ctrl+Z). "
            "Unavailable: no earlier changes are available on this page. Display target: Display 0 (primary only)."
        )
        assert window._redo_action.toolTip() == (
            "Redo the next change on the current page (Ctrl+Shift+Z). "
            "Unavailable: no later changes are available on this page. Display target: Display 0 (primary only)."
        )
        assert window._copy_action.toolTip() == (
            "Copy the current selection (Ctrl+C). Unavailable: select at least 1 widget. "
            "Display target: Display 0 (primary only)."
        )
        assert window._paste_action.toolTip() == (
            "Paste clipboard widgets into the current page (Ctrl+V). Unavailable: copy or cut widgets first. "
            "Display target: Display 0 (primary only)."
        )
        assert window._select_all_action.toolTip() == (
            "Select all visible widgets on the current page or all text in the focused editor (Ctrl+A). "
            "Display target: Display 0 (primary only)."
        )
        assert window._cut_action.toolTip() == (
            "Cut the current selection (Ctrl+X). Unavailable: select at least 1 widget. "
            "Display target: Display 0 (primary only)."
        )
        assert window._duplicate_action.toolTip() == (
            "Duplicate the current selection (Ctrl+D). Unavailable: select at least 1 widget. "
            "Display target: Display 0 (primary only)."
        )
        assert window._delete_action.toolTip() == (
            "Delete the current selection (Del). Unavailable: select at least 1 widget. "
            "Display target: Display 0 (primary only)."
        )

        loaded_widget = window._current_page.root_widget.children[0]
        window._set_selection([loaded_widget], primary=loaded_widget, sync_tree=True, sync_preview=True)
        stack = window._undo_manager.get_stack(window._current_page.name)
        stack.push("state 1", label="initial")
        window._update_undo_actions()

        assert edit_action.toolTip() == (
            "Undo changes and work with the current selection. "
            "Page: main_page. Undo: available. Redo: unavailable. Selection: title (label). "
            "Display target: Display 0 (primary only)."
        )
        assert window._undo_action.toolTip() == (
            "Undo the last change on the current page (Ctrl+Z). Display target: Display 0 (primary only)."
        )
        assert window._copy_action.toolTip() == (
            "Copy the current selection (Ctrl+C). Display target: Display 0 (primary only)."
        )
        assert window._cut_action.toolTip() == (
            "Cut the current selection (Ctrl+X). Display target: Display 0 (primary only)."
        )
        assert window._duplicate_action.toolTip() == (
            "Duplicate the current selection (Ctrl+D). Display target: Display 0 (primary only)."
        )
        assert window._delete_action.toolTip() == (
            "Delete the current selection (Del). Display target: Display 0 (primary only)."
        )

        window._copy_selection()
        assert window._paste_action.toolTip() == (
            "Paste clipboard widgets into the current page (Ctrl+V). Display target: Display 0 (primary only)."
        )

        for action in (
            edit_action,
            window._undo_action,
            window._redo_action,
            window._copy_action,
            window._paste_action,
            window._select_all_action,
            window._cut_action,
            window._duplicate_action,
            window._delete_action,
        ):
            assert action.statusTip() == action.toolTip()
        _close_window(window)

    def test_arrange_actions_expose_dynamic_status_hints(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "ArrangeHintsDemo"
        first = WidgetModel("label", name="first", x=8, y=8, width=60, height=20)
        second = WidgetModel("button", name="second", x=72, y=8, width=60, height=20)
        third = WidgetModel("switch", name="third", x=136, y=8, width=60, height=20)
        project = _create_project_only_with_widgets(
            project_dir,
            "ArrangeHintsDemo",
            sdk_root,
            widgets=[first, second, third],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        _open_project_window(window, project, project_dir, sdk_root)

        assert window._align_left_action.toolTip() == (
            "Align the current selection to the left edge of the primary widget. Unavailable: select at least 2 widgets."
        )
        assert window._align_left_action.statusTip() == window._align_left_action.toolTip()
        assert window._distribute_h_action.toolTip() == (
            "Distribute the current selection evenly across the horizontal axis. "
            "Unavailable: select at least 3 widgets."
        )
        assert window._distribute_h_action.statusTip() == window._distribute_h_action.toolTip()

        loaded_first, loaded_second, loaded_third = window._current_page.root_widget.children[:3]
        window._set_selection([loaded_first, loaded_second], primary=loaded_first, sync_tree=True, sync_preview=True)
        assert window._align_left_action.toolTip() == "Align the current selection to the left edge of the primary widget."
        assert window._align_left_action.statusTip() == window._align_left_action.toolTip()
        assert window._distribute_h_action.toolTip() == (
            "Distribute the current selection evenly across the horizontal axis. "
            "Unavailable: select at least 3 widgets."
        )
        assert window._distribute_h_action.statusTip() == window._distribute_h_action.toolTip()

        loaded_second.designer_locked = True
        window._update_edit_actions()
        assert window._align_left_action.toolTip() == (
            "Align the current selection to the left edge of the primary widget. "
            "Unavailable: locked widgets leave fewer than 2 editable widgets."
        )
        assert window._align_left_action.statusTip() == window._align_left_action.toolTip()
        loaded_second.designer_locked = False

        window._set_selection([loaded_first, loaded_second, loaded_third], primary=loaded_first, sync_tree=True, sync_preview=True)
        assert window._distribute_h_action.toolTip() == "Distribute the current selection evenly across the horizontal axis."
        assert window._distribute_h_action.statusTip() == window._distribute_h_action.toolTip()
        _close_window(window)

    def test_arrange_reorder_and_toggle_actions_expose_status_hints(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "ArrangeToggleHintsDemo"
        first = WidgetModel("label", name="first", x=8, y=8, width=60, height=20)
        second = WidgetModel("button", name="second", x=72, y=8, width=60, height=20)
        second.designer_locked = True
        project = _create_project_only_with_widgets(
            project_dir,
            "ArrangeToggleHintsDemo",
            sdk_root,
            widgets=[first, second],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        _open_project_window(window, project, project_dir, sdk_root)

        assert window._bring_front_action.toolTip() == (
            "Bring the current selection to the front of its parent stack. Unavailable: select at least 1 widget."
        )
        assert window._bring_front_action.statusTip() == window._bring_front_action.toolTip()
        assert window._send_back_action.toolTip() == (
            "Send the current selection to the back of its parent stack. Unavailable: select at least 1 widget."
        )
        assert window._send_back_action.statusTip() == window._send_back_action.toolTip()
        assert window._toggle_lock_action.toolTip() == (
            "Toggle the designer lock state for the current selection. Unavailable: select at least 1 widget."
        )
        assert window._toggle_lock_action.statusTip() == window._toggle_lock_action.toolTip()
        assert window._toggle_hide_action.toolTip() == (
            "Toggle the designer visibility state for the current selection. Unavailable: select at least 1 widget."
        )
        assert window._toggle_hide_action.statusTip() == window._toggle_hide_action.toolTip()

        loaded_first, loaded_second = window._current_page.root_widget.children[:2]
        window._set_selection([loaded_second], primary=loaded_second, sync_tree=True, sync_preview=True)
        assert window._bring_front_action.toolTip() == (
            "Bring the current selection to the front of its parent stack. "
            "Unavailable: all selected widgets are locked."
        )
        assert window._bring_front_action.statusTip() == window._bring_front_action.toolTip()
        assert window._send_back_action.toolTip() == (
            "Send the current selection to the back of its parent stack. "
            "Unavailable: all selected widgets are locked."
        )
        assert window._send_back_action.statusTip() == window._send_back_action.toolTip()
        assert window._toggle_lock_action.toolTip() == "Toggle the designer lock state for the current selection."
        assert window._toggle_lock_action.statusTip() == window._toggle_lock_action.toolTip()
        assert window._toggle_hide_action.toolTip() == "Toggle the designer visibility state for the current selection."
        assert window._toggle_hide_action.statusTip() == window._toggle_hide_action.toolTip()

        window._set_selection([loaded_first, loaded_second], primary=loaded_first, sync_tree=True, sync_preview=True)
        assert window._bring_front_action.toolTip() == (
            "Bring the current selection to the front of its parent stack. Locked widgets remain in place."
        )
        assert window._bring_front_action.statusTip() == window._bring_front_action.toolTip()
        assert window._send_back_action.toolTip() == (
            "Send the current selection to the back of its parent stack. Locked widgets remain in place."
        )
        assert window._send_back_action.statusTip() == window._send_back_action.toolTip()
        _close_window(window)

    def test_menu_bar_categories_expose_status_hints(self, qapp, isolated_config, monkeypatch):
        from ui_designer.ui import main_window as main_window_module
        from ui_designer.ui.main_window import MainWindow

        monkeypatch.setattr(main_window_module, "apply_theme", lambda app, theme, density="standard": None)

        window = MainWindow("")
        actions = {action.text(): action for action in window.menuBar().actions() if action.text()}

        assert actions["File"].toolTip() == (
            "Create, open, save, export, and close projects. "
            "Project: none. SDK: invalid. Unsaved changes: none. Reload: unavailable. Recent projects: none."
        )
        assert actions["File"].statusTip() == actions["File"].toolTip()
        assert actions["Edit"].toolTip() == (
            "Undo changes and work with the current selection. "
            "Page: none. Undo: unavailable. Redo: unavailable. Selection: none."
        )
        assert actions["Edit"].statusTip() == actions["Edit"].toolTip()
        assert actions["Arrange"].toolTip() == (
            "Align, distribute, reorder, lock, and hide selected widgets. "
            "Selection: none. Align: unavailable. Distribute: unavailable. Reorder: unavailable. Lock/Hide: unavailable."
        )
        assert actions["Arrange"].statusTip() == actions["Arrange"].toolTip()
        assert actions["Structure"].toolTip() == (
            "Group, move, and reorder widgets in the page hierarchy. "
            "Selection: none. Group/Ungroup: unavailable. Move Into: unavailable. Reorder/Lift: unavailable."
        )
        assert actions["Structure"].statusTip() == actions["Structure"].toolTip()
        assert actions["Build"].toolTip() == (
            "Compile previews, generate resources, or reconstruct a project from Designer sources. "
            "Project: none. SDK: invalid. Compile: unavailable. Rebuild: unavailable. Reconstruct: unavailable. Auto compile: on. "
            "Preview: stopped. Source resources: missing. Resource directory: none."
        )
        assert actions["Build"].statusTip() == actions["Build"].toolTip()
        assert actions["View"].toolTip() == (
            "Change workspace layout, themes, preview modes, and mockup options. "
            "Theme: Dark. Density: Standard. Font size: app default. Layout: Horizontal, overlay first. Grid: visible. Snap: 8px. Mockup: none loaded."
        )
        assert actions["View"].statusTip() == actions["View"].toolTip()

        window._set_theme("light")
        window._set_show_grid(False)
        window._set_overlay_mode("hidden")
        isolated_config.font_size_px = 11
        window._update_view_and_theme_action_metadata()

        assert actions["View"].toolTip() == (
            "Change workspace layout, themes, preview modes, and mockup options. "
            "Theme: Light. Density: Standard. Font size: 11pt. Layout: Overlay Only. Grid: hidden. Snap: 8px. Mockup: none loaded."
        )
        _close_window(window)

    def test_edit_menu_category_exposes_page_selection_and_undo_state(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "EditCategoryHintsDemo"
        widget = WidgetModel("label", name="title", x=12, y=16, width=100, height=24)
        project = _create_project_only_with_widgets(
            project_dir,
            "EditCategoryHintsDemo",
            sdk_root,
            widgets=[widget],
        )

        window = MainWindow("")
        _disable_window_compile(window, _DisabledCompiler)

        edit_action = next(action for action in window.menuBar().actions() if action.text() == "Edit")
        assert edit_action.toolTip() == (
            "Undo changes and work with the current selection. "
            "Page: none. Undo: unavailable. Redo: unavailable. Selection: none."
        )

        _open_project_window(window, project, project_dir, sdk_root)

        assert edit_action.toolTip() == (
            "Undo changes and work with the current selection. "
            "Page: main_page. Undo: unavailable. Redo: unavailable. Selection: none."
        )
        assert edit_action.statusTip() == edit_action.toolTip()

        loaded_widget = window._current_page.root_widget.children[0]
        window._set_selection([loaded_widget], primary=loaded_widget, sync_tree=True, sync_preview=True)

        stack = window._undo_manager.get_stack(window._current_page.name)
        stack.push("state 1", label="initial")
        stack.push("state 2", label="changed")
        stack.push("state 3", label="changed again")
        stack.undo()
        window._update_undo_actions()

        assert edit_action.toolTip() == (
            "Undo changes and work with the current selection. "
            "Page: main_page. Undo: available. Redo: available. Selection: title (label)."
        )
        assert edit_action.statusTip() == edit_action.toolTip()
        _close_window(window)

    def test_file_menu_category_exposes_project_dirty_and_recent_state(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "FileCategoryHintsDemo"
        project = _create_project(project_dir, "FileCategoryHintsDemo", sdk_root)

        window = MainWindow("")
        _disable_window_compile(window, _DisabledCompiler)

        file_action = next(action for action in window.menuBar().actions() if action.text() == "File")
        assert file_action.toolTip() == (
            "Create, open, save, export, and close projects. "
            "Project: none. SDK: invalid. Unsaved changes: none. Reload: unavailable. Recent projects: none."
        )
        assert file_action.statusTip() == file_action.toolTip()

        _open_project_window(window, project, project_dir, sdk_root)

        assert file_action.toolTip() == (
            "Create, open, save, export, and close projects. "
            "Project: open. SDK: valid. Unsaved changes: none. Reload: available. Recent projects: 1 project."
        )
        assert file_action.statusTip() == file_action.toolTip()

        stack = window._undo_manager.get_stack(window._current_page.name)
        stack.push("state 1", label="initial")
        stack.mark_saved()
        stack.push("state 2", label="changed")
        window._update_window_title()

        assert file_action.toolTip() == (
            "Create, open, save, export, and close projects. "
            "Project: open. SDK: valid. Unsaved changes: 1 page. Reload: available. Recent projects: 1 project."
        )
        assert file_action.statusTip() == file_action.toolTip()
        _close_window(window)

    def test_file_menu_reports_project_level_unsaved_changes_without_dirty_pages(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "FileCategoryProjectDirtyDemo"
        project = _create_project(
            project_dir,
            "FileCategoryProjectDirtyDemo",
            sdk_root,
            pages=["main_page", "detail_page"],
        )

        window = MainWindow("")
        _disable_window_compile(window, _DisabledCompiler)

        file_action = next(action for action in window.menuBar().actions() if action.text() == "File")

        _open_project_window(window, project, project_dir, sdk_root)
        window._on_startup_changed("detail_page")

        assert window._undo_manager.is_any_dirty() is False
        assert window._has_unsaved_changes() is True
        assert file_action.toolTip() == (
            "Create, open, save, export, and close projects. "
            "Project: open. SDK: valid. Unsaved changes: project changes (startup page). Reload: available. "
            "Recent projects: 1 project."
        )
        assert file_action.statusTip() == file_action.toolTip()
        _close_window(window)

    def test_file_menu_reports_page_and_project_dirty_reasons_together(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "FileCategoryMixedDirtyDemo"
        project = _create_project(
            project_dir,
            "FileCategoryMixedDirtyDemo",
            sdk_root,
            pages=["main_page", "detail_page"],
        )

        window = MainWindow("")
        _disable_window_compile(window, _DisabledCompiler)

        file_action = next(action for action in window.menuBar().actions() if action.text() == "File")

        _open_project_window(window, project, project_dir, sdk_root)
        window._switch_page("detail_page")
        stack = window._undo_manager.get_stack("detail_page")
        stack.push("state 1", label="initial")
        stack.mark_saved()
        stack.push("state 2", label="changed")
        window._update_window_title()
        window._on_startup_changed("detail_page")

        assert file_action.toolTip() == (
            "Create, open, save, export, and close projects. "
            "Project: open. SDK: valid. Unsaved changes: 1 page + project changes (startup page). "
            "Reload: available. Recent projects: 1 project."
        )
        assert file_action.statusTip() == file_action.toolTip()
        _close_window(window)

    def test_file_menu_reports_pending_external_change_summary(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "FileCategoryPendingReloadDemo"
        project = _create_project(project_dir, "FileCategoryPendingReloadDemo", sdk_root)

        window = MainWindow("")
        _disable_window_compile(window, _DisabledCompiler)

        file_action = next(action for action in window.menuBar().actions() if action.text() == "File")

        _open_project_window(window, project, project_dir, sdk_root)
        layout_file = project_dir / ".eguiproject" / "layout" / "main_page.xml"
        window._set_external_reload_pending([os.path.normpath(os.path.abspath(layout_file))])

        assert file_action.toolTip() == (
            "Create, open, save, export, and close projects. "
            "Project: open. SDK: valid. Unsaved changes: none. "
            "Reload: pending external changes (main_page.xml). Recent projects: 1 project."
        )
        assert file_action.statusTip() == file_action.toolTip()
        _close_window(window)

    def test_arrange_menu_category_exposes_selection_state(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "ArrangeCategoryHintsDemo"
        first = WidgetModel("label", name="title", x=12, y=16, width=100, height=24)
        second = WidgetModel("button", name="action", x=132, y=16, width=100, height=24)
        project = _create_project_only_with_widgets(
            project_dir,
            "ArrangeCategoryHintsDemo",
            sdk_root,
            widgets=[first, second],
        )

        window = MainWindow("")
        _disable_window_compile(window, _DisabledCompiler)

        arrange_action = next(action for action in window.menuBar().actions() if action.text() == "Arrange")
        assert arrange_action.toolTip() == (
            "Align, distribute, reorder, lock, and hide selected widgets. "
            "Selection: none. Align: unavailable. Distribute: unavailable. Reorder: unavailable. Lock/Hide: unavailable."
        )
        assert arrange_action.statusTip() == arrange_action.toolTip()

        _open_project_window(window, project, project_dir, sdk_root)
        loaded_first, loaded_second = window._current_page.root_widget.children[:2]

        window._set_selection([loaded_first], primary=loaded_first, sync_tree=True, sync_preview=True)
        assert arrange_action.toolTip() == (
            "Align, distribute, reorder, lock, and hide selected widgets. "
            "Selection: title (label). Align: unavailable. Distribute: unavailable. Reorder: available. Lock/Hide: available."
        )
        assert arrange_action.statusTip() == arrange_action.toolTip()

        window._set_selection([loaded_first, loaded_second], primary=loaded_first, sync_tree=True, sync_preview=True)
        assert arrange_action.toolTip() == (
            "Align, distribute, reorder, lock, and hide selected widgets. "
            "Selection: 2 widgets. Align: available. Distribute: unavailable. Reorder: available. Lock/Hide: available."
        )
        assert arrange_action.statusTip() == arrange_action.toolTip()
        _close_window(window)

    def test_structure_menu_category_exposes_selection_state(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "StructureCategoryHintsDemo"
        first = WidgetModel("label", name="title", x=12, y=16, width=100, height=24)
        second = WidgetModel("button", name="action", x=132, y=16, width=100, height=24)
        target = WidgetModel("group", name="target_group", x=24, y=72, width=200, height=120)
        project = _create_project_only_with_widgets(
            project_dir,
            "StructureCategoryHintsDemo",
            sdk_root,
            widgets=[first, second, target],
        )

        window = MainWindow("")
        _disable_window_compile(window, _DisabledCompiler)

        structure_action = next(action for action in window.menuBar().actions() if action.text() == "Structure")
        assert structure_action.toolTip() == (
            "Group, move, and reorder widgets in the page hierarchy. "
            "Selection: none. Group/Ungroup: unavailable. Move Into: unavailable. Reorder/Lift: unavailable."
        )
        assert structure_action.statusTip() == structure_action.toolTip()

        _open_project_window(window, project, project_dir, sdk_root)
        loaded_first, loaded_second = window._current_page.root_widget.children[:2]

        window._set_selection([loaded_first, loaded_second], primary=loaded_first, sync_tree=True, sync_preview=True)
        assert structure_action.toolTip() == (
            "Group, move, and reorder widgets in the page hierarchy. "
            "Selection: 2 widgets. Group/Ungroup: available. Move Into: available. Reorder/Lift: available."
        )
        assert structure_action.statusTip() == structure_action.toolTip()
        _close_window(window)

    def test_arrange_and_structure_actions_include_primary_display_scope_for_multi_display_projects(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "MultiDisplayArrangeStructureHintsDemo"
        first = WidgetModel("label", name="title", x=12, y=16, width=100, height=24)
        second = WidgetModel("button", name="action", x=132, y=16, width=100, height=24)
        target = WidgetModel("group", name="target_group", x=24, y=72, width=200, height=120)
        project = _create_project_only_with_widgets(
            project_dir,
            "MultiDisplayArrangeStructureHintsDemo",
            sdk_root,
            widgets=[first, second, target],
        )
        project.displays = [
            {"width": 320, "height": 240},
            {"width": 128, "height": 64},
        ]

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        _open_project_window(window, project, project_dir, sdk_root)

        arrange_action = next(action for action in window.menuBar().actions() if action.text() == "Arrange")
        structure_action = next(action for action in window.menuBar().actions() if action.text() == "Structure")
        assert arrange_action.toolTip() == (
            "Align, distribute, reorder, lock, and hide selected widgets. "
            "Selection: none. Align: unavailable. Distribute: unavailable. Reorder: unavailable. "
            "Lock/Hide: unavailable. Display target: Display 0 (primary only)."
        )
        assert structure_action.toolTip() == (
            "Group, move, and reorder widgets in the page hierarchy. "
            "Selection: none. Group/Ungroup: unavailable. Move Into: unavailable. "
            "Reorder/Lift: unavailable. Display target: Display 0 (primary only)."
        )
        assert window._align_left_action.toolTip() == (
            "Align the current selection to the left edge of the primary widget. "
            "Unavailable: select at least 2 widgets. Display target: Display 0 (primary only)."
        )
        assert window._bring_front_action.toolTip() == (
            "Bring the current selection to the front of its parent stack. "
            "Unavailable: select at least 1 widget. Display target: Display 0 (primary only)."
        )

        loaded_first, loaded_second = window._current_page.root_widget.children[:2]
        window._set_selection([loaded_first, loaded_second], primary=loaded_first, sync_tree=True, sync_preview=True)

        assert arrange_action.toolTip() == (
            "Align, distribute, reorder, lock, and hide selected widgets. "
            "Selection: 2 widgets. Align: available. Distribute: unavailable. Reorder: available. "
            "Lock/Hide: available. Display target: Display 0 (primary only)."
        )
        assert structure_action.toolTip() == (
            "Group, move, and reorder widgets in the page hierarchy. "
            "Selection: 2 widgets. Group/Ungroup: available. Move Into: available. "
            "Reorder/Lift: available. Display target: Display 0 (primary only)."
        )
        assert window._align_left_action.toolTip() == (
            "Align the current selection to the left edge of the primary widget. "
            "Display target: Display 0 (primary only)."
        )
        assert window._bring_front_action.toolTip() == (
            "Bring the current selection to the front of its parent stack. "
            "Display target: Display 0 (primary only)."
        )
        assert window._group_selection_action.toolTip() == (
            "Group the current selection (Ctrl+G) Display target: Display 0 (primary only)."
        )
        assert window._move_into_container_action.toolTip() == (
            "Move the current selection into another container (Ctrl+Shift+I) Display target: Display 0 (primary only)."
        )

        for action in (
            arrange_action,
            structure_action,
            window._align_left_action,
            window._bring_front_action,
            window._group_selection_action,
            window._move_into_container_action,
        ):
            assert action.statusTip() == action.toolTip()
        _close_window(window)

    @pytest.mark.skip(reason="removed quick-move history feature")
    def test_quick_move_submenu_exposes_available_and_history_state(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "QuickMoveHintsDemo"
        target = WidgetModel("group", name="target")
        first = WidgetModel("label", name="first")
        second = WidgetModel("button", name="second")
        project = _create_project_only_with_widgets(
            project_dir,
            "QuickMoveHintsDemo",
            sdk_root,
            widgets=[target, first, second],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        _open_project_window(window, project, project_dir, sdk_root)

        window._set_selection([first], primary=first, sync_tree=True, sync_preview=True)
        assert window._quick_move_into_menu.menuAction().toolTip() == (
            "Move directly into an available container target, or manage move-target history. "
            "Targets: 1 available. Remembered target: none. Recent history: none."
        )
        assert window._quick_move_into_menu.menuAction().statusTip() == window._quick_move_into_menu.menuAction().toolTip()

        window._move_selection_into_target(target, target_label="root_group / target (group)")
        window._set_selection([second], primary=second, sync_tree=True, sync_preview=True)

        assert window._quick_move_into_menu.menuAction().toolTip() == (
            "Move directly into an available container target, or manage move-target history. "
            "Targets: 1 available. Remembered target: target. Recent history: 1 target."
        )
        assert window._quick_move_into_menu.menuAction().statusTip() == window._quick_move_into_menu.menuAction().toolTip()
        _close_window(window)

    def test_file_menu_primary_actions_expose_status_hints(self, qapp, isolated_config):
        from ui_designer.ui import main_window as main_window_module
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")
        actions = _actions_by_text(
            window._new_project_action,
            window._open_app_action,
            window._open_project_action,
            window._set_sdk_root_action,
        )

        assert actions["New Project"].toolTip() == (
            "Create a new EmbeddedGUI Designer project. "
            f"Current binding: SDK: missing. Default parent: {window._default_new_project_parent_dir()}."
        )
        assert actions["New Project"].statusTip() == actions["New Project"].toolTip()
        assert actions["Open Example..."].toolTip() == (
            "Open a bundled example, SDK example project, or initialize a Designer project "
            "for an unmanaged SDK example. "
            f"Current binding: SDK: missing. Default SDK root: {window._active_sdk_root() or 'none'}."
        )
        assert actions["Open Example..."].statusTip() == actions["Open Example..."].toolTip()
        assert actions["Open Project..."].toolTip() == (
            "Open an existing .egui project file. "
            f"Recent projects: none. Default directory: {window._default_open_project_dir()}."
        )
        assert actions["Open Project..."].statusTip() == actions["Open Project..."].toolTip()
        assert actions["Set SDK..."].toolTip() == (
            "Choose the EmbeddedGUI SDK root used for compile preview. "
            f"Current binding: SDK: missing. Default selection: {window._active_sdk_root() or 'none'}."
        )
        assert actions["Set SDK..."].statusTip() == actions["Set SDK..."].toolTip()
        _close_window(window)

    def test_set_sdk_root_action_tracks_current_binding_label(self, qapp, isolated_config, monkeypatch):
        from ui_designer.ui import main_window as main_window_module
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")
        monkeypatch.setattr(main_window_module, "format_sdk_binding_label", lambda sdk_root, designer_repo_root=None: "SDK: test-binding")

        window.project_root = "C:/sdk"
        window._update_sdk_status_label()

        action = window._set_sdk_root_action
        assert action.toolTip() == (
            "Choose the EmbeddedGUI SDK root used for compile preview. "
            f"Current binding: SDK: test-binding. Default selection: {window._active_sdk_root() or 'none'}."
        )
        assert action.statusTip() == action.toolTip()
        _close_window(window)

    def test_file_open_actions_track_binding_and_recent_projects(self, qapp, isolated_config, monkeypatch):
        from ui_designer.ui import main_window as main_window_module
        from ui_designer.ui.main_window import MainWindow

        isolated_config.recent_projects = [
            {"project_path": "C:/work/Demo.egui", "sdk_root": "", "display_name": "Demo"},
        ]
        window = MainWindow("")
        monkeypatch.setattr(main_window_module, "format_sdk_binding_label", lambda sdk_root, designer_repo_root=None: "SDK: cached")

        window.project_root = "C:/sdk"
        window._update_sdk_status_label()
        window._update_recent_menu()

        actions = _actions_by_text(
            window._open_app_action,
            window._open_project_action,
        )
        assert actions["Open Example..."].toolTip() == (
            "Open a bundled example, SDK example project, or initialize a Designer project "
            "for an unmanaged SDK example. "
            f"Current binding: SDK: cached. Default SDK root: {window._active_sdk_root() or 'none'}."
        )
        assert actions["Open Example..."].statusTip() == actions["Open Example..."].toolTip()
        assert actions["Open Project..."].toolTip() == (
            "Open an existing .egui project file. "
            f"Recent projects: 1 project. Default directory: {window._default_open_project_dir()}."
        )
        assert actions["Open Project..."].statusTip() == actions["Open Project..."].toolTip()
        _close_window(window)

    def test_open_sdk_example_action_tracks_default_sdk_root(self, qapp, isolated_config, monkeypatch):
        from ui_designer.ui import main_window as main_window_module
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")
        monkeypatch.setattr(main_window_module, "format_sdk_binding_label", lambda sdk_root, designer_repo_root=None: "SDK: sdk-example")
        window.project_root = "C:/sdk"
        window._update_sdk_status_label()

        action = window._open_app_action
        assert action.toolTip() == (
            "Open a bundled example, SDK example project, or initialize a Designer project "
            "for an unmanaged SDK example. "
            f"Current binding: SDK: sdk-example. Default SDK root: {window._active_sdk_root() or 'none'}."
        )
        assert action.statusTip() == action.toolTip()
        _close_window(window)

    def test_open_project_action_tracks_default_directory(self, qapp, isolated_config, tmp_path):
        from ui_designer.ui.main_window import MainWindow

        workspace_dir = tmp_path / "workspace"
        project_dir = workspace_dir / "CurrentApp"
        project_dir.mkdir(parents=True)

        window = MainWindow("")
        window._project_dir = str(project_dir)
        window._update_window_title()

        action = window._open_project_action
        assert action.toolTip() == (
            "Open an existing .egui project file. "
            f"Recent projects: none. Default directory: {os.path.normpath(os.path.abspath(project_dir))}."
        )
        assert action.statusTip() == action.toolTip()
        _close_window(window)

    @pytest.mark.skip(reason="removed SDK download workflow from Designer")
    def test_download_sdk_action_tracks_current_binding_label(self, qapp, isolated_config, monkeypatch):
        from ui_designer.ui import main_window as main_window_module
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")
        monkeypatch.setattr(main_window_module, "format_sdk_binding_label", lambda sdk_root, designer_repo_root=None: "SDK: download-test")
        monkeypatch.setattr(main_window_module, "default_sdk_install_dir", lambda: "C:/sdk-target")

        window.project_root = "C:/sdk"
        window._update_sdk_status_label()

        action = next(
            action for action in window.findChildren(type(window._save_action))
            if action.text() == "Download SDK..."
        )
        assert "Current binding: SDK: download-test." in action.toolTip()
        assert f"Install target: {os.path.normpath('C:/sdk-target')}." in action.toolTip()
        assert action.statusTip() == action.toolTip()
        _close_window(window)

    def test_new_project_action_tracks_current_binding_label(self, qapp, isolated_config, monkeypatch):
        from ui_designer.ui import main_window as main_window_module
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")
        monkeypatch.setattr(main_window_module, "format_sdk_binding_label", lambda sdk_root, designer_repo_root=None: "SDK: new-project")

        window.project_root = "C:/sdk"
        window._update_sdk_status_label()

        action = window._new_project_action
        assert action.toolTip() == (
            "Create a new EmbeddedGUI Designer project. "
            f"Current binding: SDK: new-project. Default parent: {window._default_new_project_parent_dir()}."
        )
        assert action.statusTip() == action.toolTip()
        _close_window(window)

    def test_new_project_action_tracks_default_parent_dir(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui import main_window as main_window_module
        from ui_designer.ui.main_window import MainWindow

        workspace_dir = tmp_path / "workspace"
        project_dir = workspace_dir / "CurrentApp"
        project_dir.mkdir(parents=True)

        window = MainWindow("")
        monkeypatch.setattr(main_window_module, "format_sdk_binding_label", lambda sdk_root, designer_repo_root=None: "SDK: parent-dir")
        window._project_dir = str(project_dir)
        window._update_window_title()

        action = window._new_project_action
        assert action.toolTip() == (
            "Create a new EmbeddedGUI Designer project. "
            f"Current binding: SDK: parent-dir. Default parent: {os.path.normpath(os.path.abspath(workspace_dir))}."
        )
        assert action.statusTip() == action.toolTip()
        _close_window(window)

    def test_file_menu_secondary_actions_expose_status_hints(self, qapp, isolated_config, tmp_path):
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")
        actions = _actions_by_text(
            window._save_as_action,
            window._reload_project_action,
            window._close_project_action,
            window._export_action,
            window._quit_action,
        )

        assert actions["Save As..."].toolTip() == (
            "Save the current project to a new file (Ctrl+Shift+S). Unavailable: open a project first."
        )
        assert actions["Save As..."].statusTip() == actions["Save As..."].toolTip()
        assert actions["Save As..."].isEnabled() is False
        assert actions["Reload Project From Disk"].toolTip() == (
            "Reload the current project from disk (Ctrl+Shift+R). Unavailable: open a project first."
        )
        assert actions["Reload Project From Disk"].statusTip() == actions["Reload Project From Disk"].toolTip()
        assert actions["Close Project"].toolTip() == "Close the current project (Ctrl+W). Unavailable: open a project first."
        assert actions["Close Project"].statusTip() == actions["Close Project"].toolTip()
        assert actions["Close Project"].isEnabled() is False
        assert actions["Export C Code..."].toolTip() == (
            "Export generated C code for the current project (Ctrl+E). Unavailable: open a project first."
        )
        assert actions["Export C Code..."].statusTip() == actions["Export C Code..."].toolTip()
        assert actions["Export C Code..."].isEnabled() is False
        assert actions["Quit"].toolTip() == "Quit EmbeddedGUI Designer (Ctrl+Q). Project: none. Unsaved pages: none."
        assert actions["Quit"].statusTip() == actions["Quit"].toolTip()

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "ReloadDemo"
        project = _create_project(project_dir, "ReloadDemo", sdk_root)
        _open_project_window(window, project, project_dir, sdk_root)
        window._update_compile_availability()

        reloaded_actions = _actions_by_text(
            window._save_as_action,
            window._reload_project_action,
            window._close_project_action,
            window._export_action,
            window._quit_action,
        )
        assert reloaded_actions["Save As..."].toolTip() == (
            "Save the current project to a new file (Ctrl+Shift+S). "
            f"Default parent: {window._default_save_project_as_dir()}."
        )
        assert reloaded_actions["Save As..."].statusTip() == reloaded_actions["Save As..."].toolTip()
        assert reloaded_actions["Save As..."].isEnabled() is True
        assert reloaded_actions["Reload Project From Disk"].toolTip() == (
            "Reload the current project from disk (Ctrl+Shift+R). "
            f"Current project directory: {window._project_dir}."
        )
        assert reloaded_actions["Reload Project From Disk"].statusTip() == reloaded_actions["Reload Project From Disk"].toolTip()
        assert reloaded_actions["Close Project"].toolTip() == "Close the current project (Ctrl+W). Unsaved pages: none."
        assert reloaded_actions["Close Project"].statusTip() == reloaded_actions["Close Project"].toolTip()
        assert reloaded_actions["Close Project"].isEnabled() is True
        assert reloaded_actions["Export C Code..."].toolTip() == (
            "Export generated C code for the current project (Ctrl+E). "
            f"Default export directory: {window._default_export_code_dir()}."
        )
        assert reloaded_actions["Export C Code..."].statusTip() == reloaded_actions["Export C Code..."].toolTip()
        assert reloaded_actions["Export C Code..."].isEnabled() is True
        assert reloaded_actions["Quit"].toolTip() == "Quit EmbeddedGUI Designer (Ctrl+Q). Project: open. Unsaved pages: none."
        assert reloaded_actions["Quit"].statusTip() == reloaded_actions["Quit"].toolTip()
        _close_window(window)

    def test_reload_project_action_exposes_unsaved_and_pending_external_change_context(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "ReloadActionContextDemo"
        project = _create_project(
            project_dir,
            "ReloadActionContextDemo",
            sdk_root,
            pages=["main_page", "detail_page"],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._on_startup_changed("detail_page")

        reload_calls = []
        monkeypatch.setattr(
            window,
            "_reload_project_from_disk",
            lambda *args, **kwargs: reload_calls.append(kwargs) or True,
        )

        layout_file = project_dir / ".eguiproject" / "layout" / "main_page.xml"
        layout_file.write_text(layout_file.read_text(encoding="utf-8") + "\n<!-- reload action context external -->\n", encoding="utf-8")

        window._poll_project_files()

        assert reload_calls == []
        assert window._reload_project_action.toolTip() == (
            "Reload the current project from disk (Ctrl+Shift+R). "
            f"Current project directory: {window._project_dir}. "
            "Current unsaved changes: project changes (startup page). "
            "Pending external changes: main_page.xml."
        )
        assert window._reload_project_action.statusTip() == window._reload_project_action.toolTip()
        _close_window(window)

    def test_reload_project_action_and_file_menu_clear_pending_external_change_context(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "ReloadActionPendingClearDemo"
        project = _create_project(project_dir, "ReloadActionPendingClearDemo", sdk_root)

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        file_action = next(action for action in window.menuBar().actions() if action.text() == "File")

        _open_project_window(window, project, project_dir, sdk_root)
        layout_file = project_dir / ".eguiproject" / "layout" / "main_page.xml"
        window._set_external_reload_pending([os.path.normpath(os.path.abspath(layout_file))])

        window._clear_external_reload_pending()

        assert window._reload_project_action.toolTip() == (
            "Reload the current project from disk (Ctrl+Shift+R). "
            f"Current project directory: {window._project_dir}."
        )
        assert file_action.toolTip() == (
            "Create, open, save, export, and close projects. "
            "Project: open. SDK: valid. Unsaved changes: none. Reload: available. Recent projects: 1 project."
        )
        _close_window(window)

    def test_close_project_action_exposes_dirty_page_count(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "CloseHintDemo"
        project = _create_project(project_dir, "CloseHintDemo", sdk_root)

        window = MainWindow("")
        _disable_window_compile(window, _DisabledCompiler)
        _open_project_window(window, project, project_dir, sdk_root)

        stack = window._undo_manager.get_stack(window._current_page.name)
        stack.push("state 1", label="initial")
        stack.mark_saved()
        stack.push("state 2", label="changed")
        window._update_window_title()

        assert window._close_project_action.toolTip() == "Close the current project (Ctrl+W). Unsaved pages: 1 page."
        assert window._close_project_action.statusTip() == window._close_project_action.toolTip()
        assert window._close_project_action.isEnabled() is True
        _close_window(window)

    def test_close_project_action_exposes_project_change_state(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "CloseProjectChangeHintDemo"
        project = _create_project(
            project_dir,
            "CloseProjectChangeHintDemo",
            sdk_root,
            pages=["main_page", "detail_page"],
        )

        window = MainWindow("")
        _disable_window_compile(window, _DisabledCompiler)
        _open_project_window(window, project, project_dir, sdk_root)

        window._on_startup_changed("detail_page")

        assert window._undo_manager.is_any_dirty() is False
        assert window._close_project_action.toolTip() == (
            "Close the current project (Ctrl+W). Unsaved changes: project changes (startup page)."
        )
        assert window._close_project_action.statusTip() == window._close_project_action.toolTip()
        assert window._quit_action.toolTip() == (
            "Quit EmbeddedGUI Designer (Ctrl+Q). Project: open. Unsaved changes: project changes (startup page)."
        )
        _close_window(window)

    def test_duplicate_page_copies_existing_page_content(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        label = WidgetModel("label", name="title", x=12, y=16, width=100, height=24)
        label.properties["text"] = "Original Title"

        def _setup_source_page(page, _root):
            page.user_fields.append({"name": "counter", "type": "int", "default": 7})
            page.timers.append(
                {
                    "name": "refresh_timer",
                    "callback": "tick_refresh",
                    "delay_ms": "500",
                    "period_ms": "1000",
                    "auto_start": True,
                }
            )
            page.mockup_image_path = "mockup/main.png"
            page.mockup_image_opacity = 0.6

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "DuplicateDemo"
        project, source_page, source_root = _create_project_with_widgets(
            project_dir,
            "DuplicateDemo",
            sdk_root,
            widgets=[label],
            page_customizer=_setup_source_page,
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window.project_dock._duplicate_page("main_page")

        duplicated, duplicated_root = require_project_page_root(window.project, "main_page_copy")
        assert window._current_page is duplicated
        assert duplicated_root is not source_root
        assert len(duplicated_root.children) == 1
        assert duplicated_root.children[0].properties["text"] == "Original Title"
        assert duplicated.user_fields == [{"name": "counter", "type": "int", "default": "7"}]
        assert duplicated.timers == [
            {
                "name": "refresh_timer",
                "callback": "tick_refresh",
                "delay_ms": "500",
                "period_ms": "1000",
                "auto_start": True,
            }
        ]
        assert duplicated.mockup_image_path == "mockup/main.png"
        assert duplicated.mockup_image_opacity == 0.6
        assert window._undo_manager.is_any_dirty() is True
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_delete_page_via_project_dock_archives_user_owned_files(self, qapp, isolated_config, tmp_path, monkeypatch):
        from PyQt5.QtWidgets import QMessageBox
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "DeletePageArchiveDemo"
        project = _create_project(
            project_dir,
            "DeletePageArchiveDemo",
            sdk_root,
            pages=["main_page", "detail_page"],
        )

        (project_dir / ".designer").mkdir()
        (project_dir / ".designer" / "detail_page.h").write_text("", encoding="utf-8")
        (project_dir / ".designer" / "detail_page_layout.c").write_text("", encoding="utf-8")
        (project_dir / "detail_page.c").write_text("/* detail user */\n", encoding="utf-8")
        (project_dir / "detail_page_ext.h").write_text("#define DETAIL_EXT 1\n", encoding="utf-8")

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr("ui_designer.ui.project_dock.QMessageBox.question", lambda *args, **kwargs: QMessageBox.Yes)

        _open_project_window(window, project, project_dir, sdk_root)
        window.project_dock._delete_page("detail_page")
        qapp.processEvents()

        assert window.project.get_page_by_name("detail_page") is None
        assert not (project_dir / ".designer" / "detail_page.h").exists()
        assert not (project_dir / ".designer" / "detail_page_layout.c").exists()
        assert not (project_dir / "detail_page.c").exists()
        assert not (project_dir / "detail_page_ext.h").exists()
        assert (project_dir / ".eguiproject" / "orphaned_user_code" / "detail_page" / "detail_page.c").is_file()
        assert (project_dir / ".eguiproject" / "orphaned_user_code" / "detail_page" / "detail_page_ext.h").is_file()
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_delete_current_page_via_project_dock_switches_to_remaining_page(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "DeleteCurrentPageDemo"
        project = _create_project(
            project_dir,
            "DeleteCurrentPageDemo",
            sdk_root,
            pages=["main_page", "detail_page"],
        )

        (project_dir / "detail_page.c").write_text("/* detail user */\n", encoding="utf-8")
        (project_dir / "detail_page_ext.h").write_text("#define DETAIL_EXT 1\n", encoding="utf-8")

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window, "_remove_page_tab", lambda *args, **kwargs: None)

        _open_project_window(window, project, project_dir, sdk_root)
        window._switch_page("detail_page")
        window._on_page_removed("detail_page")
        qapp.processEvents()

        assert window._current_page is not None
        assert window._current_page.name == "main_page"
        assert window.page_navigator._current_page == "main_page"
        assert window.project.get_page_by_name("detail_page") is None
        assert (project_dir / ".eguiproject" / "orphaned_user_code" / "detail_page" / "detail_page.c").is_file()
        assert (project_dir / ".eguiproject" / "orphaned_user_code" / "detail_page" / "detail_page_ext.h").is_file()
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_delete_renamed_page_cleans_pre_rename_codegen_files(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "DeleteRenamedPageDemo"
        project = _create_project(
            project_dir,
            "DeleteRenamedPageDemo",
            sdk_root,
            pages=["main_page", "detail_page"],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window, "_load_project_app_local_widgets", lambda *args, **kwargs: None)
        monkeypatch.setattr(window, "_remove_page_tab", lambda *args, **kwargs: None)

        _open_project_window(window, project, project_dir, sdk_root)
        window._save_project_files(str(project_dir))
        (project_dir / "detail_page.c").write_text("/* detail renamed user */\n", encoding="utf-8")
        (project_dir / "detail_page_ext.h").write_text("#define DETAIL_RENAMED_EXT 1\n", encoding="utf-8")

        window._on_page_renamed("detail_page", "dashboard_page")
        window._on_page_removed("dashboard_page")

        assert window.project.get_page_by_name("dashboard_page") is None
        assert not (project_dir / "detail_page.h").exists()
        assert not (project_dir / "detail_page_layout.c").exists()
        assert not (project_dir / ".designer" / "detail_page.h").exists()
        assert not (project_dir / ".designer" / "detail_page_layout.c").exists()
        assert not (project_dir / "detail_page.c").exists()
        assert not (project_dir / "detail_page_ext.h").exists()
        assert (project_dir / ".eguiproject" / "orphaned_user_code" / "detail_page" / "detail_page.c").read_text(
            encoding="utf-8"
        ) == "/* detail renamed user */\n"
        assert (
            project_dir / ".eguiproject" / "orphaned_user_code" / "detail_page" / "detail_page_ext.h"
        ).read_text(encoding="utf-8") == "#define DETAIL_RENAMED_EXT 1\n"
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_page_fields_panel_edit_updates_page_dirty_state_and_xml(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PageFieldsDemo"
        project = _create_project(project_dir, "PageFieldsDemo", sdk_root)

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        assert window.page_fields_dock.objectName() == "page_fields_dock"

        window.page_fields_panel._on_add_field()
        qapp.processEvents()

        table = window.page_fields_panel._table
        table.item(0, 0).setText("counter")
        table.item(0, 1).setText("uint32_t")
        table.item(0, 2).setText("7")
        qapp.processEvents()

        assert window._current_page.user_fields == [{"name": "counter", "type": "uint32_t", "default": "7"}]
        assert window._undo_manager.is_any_dirty() is True
        assert window.statusBar().currentMessage() == "Changed main_page: page fields edit."

        xml = window._current_page.to_xml_string()
        assert "<UserFields>" in xml
        assert 'name="counter"' in xml
        assert 'type="uint32_t"' in xml
        assert 'default="7"' in xml

        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_page_fields_panel_tracks_current_page_when_switching_pages(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        def _setup_main_page(page, _root):
            page.user_fields = [{"name": "counter", "type": "int", "default": "0"}]

        def _setup_detail_page(page, _root):
            page.user_fields = [{"name": "state", "type": "bool", "default": "false"}]

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PageFieldsSwitchDemo"
        project = _create_project_only_with_page_widgets(
            project_dir,
            "PageFieldsSwitchDemo",
            sdk_root,
            page_customizers={
                "main_page": _setup_main_page,
                "detail_page": _setup_detail_page,
            },
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)

        assert window.page_fields_panel._summary_label.text() == "Page Fields: 1 field on main_page"
        assert window.page_fields_panel._table.item(0, 0).text() == "counter"

        window._switch_page("detail_page")

        assert window.page_fields_panel._summary_label.text() == "Page Fields: 1 field on detail_page"
        assert window.page_fields_panel._table.item(0, 0).text() == "state"
        assert window.page_fields_panel._table.item(0, 2).text() == "false"

        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_page_fields_panel_open_init_creates_page_source_and_updates_status(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PageFieldsCodeDemo"
        project = _create_project(project_dir, "PageFieldsCodeDemo", sdk_root)

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        opened = []
        monkeypatch.setattr(window, "_open_path_in_default_app", lambda path: opened.append(path) or True)

        _open_project_window(window, project, project_dir, sdk_root)
        window._on_page_user_code_section_requested("init")

        source_path = project_dir / "main_page.c"
        assert opened == [str(source_path)]
        assert source_path.exists() is True
        content = source_path.read_text(encoding="utf-8")
        assert "void egui_main_page_user_init(egui_main_page_t *page)" in content
        assert "// USER CODE BEGIN" not in content
        assert window.statusBar().currentMessage() == "Opened user code: main_page.c (init)."
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_page_timers_panel_edit_updates_page_dirty_state_and_xml(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PageTimersDemo"
        project = _create_project(project_dir, "PageTimersDemo", sdk_root)

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        assert window.page_timers_dock.objectName() == "page_timers_dock"

        window.page_timers_panel._on_add_timer()
        qapp.processEvents()

        table = window.page_timers_panel._table
        table.item(0, 0).setText("refresh_timer")
        table.item(0, 1).setText("tick_refresh")
        table.item(0, 2).setText("500")
        table.item(0, 3).setText("1000")
        table.item(0, 4).setText("true")
        qapp.processEvents()

        assert window._current_page.timers == [
            {
                "name": "refresh_timer",
                "callback": "tick_refresh",
                "delay_ms": "500",
                "period_ms": "1000",
                "auto_start": True,
            }
        ]
        assert window._undo_manager.is_any_dirty() is True
        assert window.statusBar().currentMessage() == "Changed main_page: page timers edit."

        xml = window._current_page.to_xml_string()
        assert "<Timers>" in xml
        assert 'name="refresh_timer"' in xml
        assert 'callback="tick_refresh"' in xml
        assert 'auto_start="true"' in xml

        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_page_timers_panel_tracks_current_page_when_switching_pages(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        def _setup_main_page(page, _root):
            page.timers = [{"name": "refresh_timer", "callback": "tick_refresh", "delay_ms": "500", "period_ms": "1000", "auto_start": True}]

        def _setup_detail_page(page, _root):
            page.timers = [{"name": "poll_timer", "callback": "tick_poll", "delay_ms": "250", "period_ms": "250", "auto_start": False}]

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PageTimersSwitchDemo"
        project = _create_project_only_with_page_widgets(
            project_dir,
            "PageTimersSwitchDemo",
            sdk_root,
            page_customizers={
                "main_page": _setup_main_page,
                "detail_page": _setup_detail_page,
            },
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)

        assert window.page_timers_panel._summary_label.text() == "Page Timers: 1 timer on main_page"
        assert window.page_timers_panel._table.item(0, 0).text() == "refresh_timer"

        window._switch_page("detail_page")

        assert window.page_timers_panel._summary_label.text() == "Page Timers: 1 timer on detail_page"
        assert window.page_timers_panel._table.item(0, 0).text() == "poll_timer"
        assert window.page_timers_panel._table.item(0, 4).text() == "false"

        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_animations_panel_edit_updates_widget_dirty_state_and_xml(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "AnimationsDemo"
        card = WidgetModel("group", name="card", x=12, y=16, width=100, height=60)
        project = _create_project_only_with_widgets(
            project_dir,
            "AnimationsDemo",
            sdk_root,
            widgets=[card],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([card], primary=card, sync_tree=True, sync_preview=False)

        assert window.animations_dock.objectName() == "animations_dock"
        window.animations_panel._on_add_animation()
        window.animations_panel._on_type_changed(0, "translate")
        window.animations_panel._on_interpolator_changed(0, "bounce")
        window.animations_panel._on_duration_changed(0, 900)
        window.animations_panel._on_repeat_mode_changed(0, "reverse")
        window.animations_panel._on_param_changed(0, "to_y", "64")
        qapp.processEvents()

        assert len(card.animations) == 1
        assert card.animations[0].anim_type == "translate"
        assert card.animations[0].interpolator == "bounce"
        assert card.animations[0].duration == 900
        assert card.animations[0].repeat_mode == "reverse"
        assert card.animations[0].params["to_y"] == "64"
        assert window._undo_manager.is_any_dirty() is True
        assert window.statusBar().currentMessage() == "Changed main_page: widget animations edit."

        xml = window._current_page.to_xml_string()
        assert '<Animation type="translate"' in xml
        assert 'duration="900"' in xml
        assert 'interpolator="bounce"' in xml
        assert 'repeat_mode="reverse"' in xml
        assert 'to_y="64"' in xml

        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_animations_panel_tracks_primary_selection(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_animations import create_default_animation
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "AnimationsSelectionDemo"
        card = WidgetModel("group", name="card", x=12, y=16, width=100, height=60)
        badge = WidgetModel("group", name="badge", x=12, y=88, width=80, height=40)
        card.animations = [create_default_animation("alpha")]
        badge.animations = [create_default_animation("color")]
        project = _create_project_only_with_widgets(
            project_dir,
            "AnimationsSelectionDemo",
            sdk_root,
            widgets=[card, badge],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)

        window._set_selection([card], primary=card, sync_tree=True, sync_preview=False)
        assert window.animations_panel._summary_label.text() == "Animations: 1 animation on group card"
        assert window.animations_panel._table.item(0, 0).text() == "alpha"

        window._set_selection([badge], primary=badge, sync_tree=True, sync_preview=False)
        assert window.animations_panel._summary_label.text() == "Animations: 1 animation on group badge"
        assert window.animations_panel._table.item(0, 0).text() == "color"

        window._set_selection([card, badge], primary=card, sync_tree=True, sync_preview=False)
        assert "select a single widget" in window.animations_panel._summary_label.text().lower()

        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_property_panel_resource_imported_signal_triggers_resource_refresh_flow(self, qapp, isolated_config, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")
        monkeypatch.setattr(window, "_refresh_project_watch_snapshot", lambda: None)

        window.property_panel.resource_imported.emit()

        assert window._resources_need_regen is True
        assert window._regen_timer.isActive() is True
        assert "Resources changed, will regenerate..." in window.statusBar().currentMessage()
        window._regen_timer.stop()
        _close_window(window)

    def test_ensure_resources_generated_reruns_when_output_bin_is_missing(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        output_bin = Path(sdk_output_path(str(sdk_root), "app_egui_resource_merge.bin"))
        output_bin.parent.mkdir(parents=True, exist_ok=True)

        window = MainWindow(str(sdk_root))
        calls = []

        def _fake_run_resource_generation(*, silent=False):
            calls.append(silent)
            output_bin.write_bytes(b"")
            return True

        monkeypatch.setattr(window, "_run_resource_generation", _fake_run_resource_generation)

        window._resources_need_regen = False
        if output_bin.exists():
            output_bin.unlink()

        window._ensure_resources_generated()

        assert calls == [True]
        assert output_bin.exists() is True
        _close_window(window)

    def test_run_resource_generation_recreates_missing_user_overlay_config(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        gen_script = sdk_root / "scripts" / "tools" / "app_resource_generate.py"
        gen_script.parent.mkdir(parents=True, exist_ok=True)
        gen_script.write_text("print('ok')\n", encoding="utf-8")

        project_dir = tmp_path / "ResourceOverlayRecoveryDemo"
        project = _create_project(project_dir, "ResourceOverlayRecoveryDemo", sdk_root)
        user_config_path = project_dir / "resource" / "src" / "app_resource_config.json"
        if user_config_path.exists():
            user_config_path.unlink()

        window = MainWindow(str(sdk_root))
        window.project = project
        window.project_root = str(sdk_root)
        window._project_dir = str(project_dir)
        window.app_name = "ResourceOverlayRecoveryDemo"

        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *args, **kwargs: build_completed_process_result(),
        )

        assert window._run_resource_generation(silent=True) is True
        assert user_config_path.read_text(encoding="utf-8") == '{\n    "img": [],\n    "font": [],\n    "mp4": []\n}\n'
        _close_window(window)

    def test_run_resource_generation_syncs_watch_snapshot_before_missing_generator_return(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "ResourceWatchSyncDemo"
        project = _create_project(project_dir, "ResourceWatchSyncDemo", sdk_root)
        designer_config = project_dir / "resource" / "src" / ".designer" / "app_resource_config_designer.json"

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)

        def _fake_sync(*args, **kwargs):
            designer_config.write_text('{"img":["updated"]}\n', encoding="utf-8")

        reload_calls = []
        monkeypatch.setattr(
            "ui_designer.ui.main_window.sync_project_resources_and_generate_designer_resource_config",
            _fake_sync,
        )
        monkeypatch.setattr(
            window,
            "_reload_project_from_disk",
            lambda *args, **kwargs: reload_calls.append(kwargs) or True,
        )

        assert window._run_resource_generation(silent=True) is False

        window._poll_project_files()

        assert reload_calls == []
        assert window._external_reload_pending is False
        assert window._external_reload_changed_paths == []
        _close_window(window)

    def test_property_panel_callback_edit_updates_widget_and_dirty_state(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "EventCallbackDemo"
        slider = WidgetModel("slider", name="volume_slider", x=16, y=16, width=160, height=24)
        project = _create_project_only_with_widgets(
            project_dir,
            "EventCallbackDemo",
            sdk_root,
            widgets=[slider],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([slider], primary=slider, sync_tree=True, sync_preview=False)

        editor = window.property_panel._editors["callback_onValueChanged"]
        editor.setText("on_volume_changed")
        editor.editingFinished.emit()

        assert slider.events["onValueChanged"] == "on_volume_changed"
        assert window._undo_manager.is_any_dirty() is True
        assert window.statusBar().currentMessage() == "Changed main_page: property edit."
        assert 'onValueChanged="on_volume_changed"' in window._current_page.to_xml_string()
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_user_code_request_creates_page_source_and_opens_callback_stub(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "UserCodeCreateDemo"
        slider = WidgetModel("slider", name="volume_slider", x=16, y=16, width=160, height=24)
        slider.events["onValueChanged"] = "on_volume_changed"
        project = _create_project_only_with_widgets(
            project_dir,
            "UserCodeCreateDemo",
            sdk_root,
            widgets=[slider],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        opened = []
        monkeypatch.setattr(window, "_open_path_in_default_app", lambda path: opened.append(path) or True)

        _open_project_window(window, project, project_dir, sdk_root)
        window._on_user_code_requested("on_volume_changed", "void {func_name}(egui_view_t *self, uint8_t value)")

        source_path = project_dir / "main_page.c"
        assert opened == [str(source_path)]
        assert source_path.exists() is True
        content = source_path.read_text(encoding="utf-8")
        assert "void on_volume_changed(egui_view_t *self, uint8_t value)" in content
        assert window.statusBar().currentMessage() == "Opened user code: main_page.c (on_volume_changed)."
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_user_code_request_updates_existing_page_source_with_missing_callback_stub(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.generator.code_generator import generate_page_user_source
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "UserCodeUpdateDemo"
        project, page = _create_project_and_page_with_widgets(
            project_dir,
            "UserCodeUpdateDemo",
            sdk_root,
        )
        source_path = project_dir / "main_page.c"
        source_path.write_text(generate_page_user_source(page, project), encoding="utf-8")

        timer = {"name": "refresh_timer", "callback": "tick_refresh", "delay_ms": "500", "period_ms": "1000", "auto_start": True}
        page.timers = [timer]
        save_project_model(project, str(project_dir))

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        refresh_calls = []
        monkeypatch.setattr(window, "_refresh_project_watch_snapshot", lambda: refresh_calls.append("refreshed"))
        monkeypatch.setattr(window, "_open_path_in_default_app", lambda path: True)

        _open_project_window(window, project, project_dir, sdk_root)
        refresh_calls.clear()
        window._on_user_code_requested("tick_refresh", "void {func_name}(egui_timer_t *timer)")

        content = source_path.read_text(encoding="utf-8")
        assert "void tick_refresh(egui_timer_t *timer)" in content
        assert "EGUI_UNUSED(local);" in content
        assert refresh_calls
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_user_code_request_does_not_duplicate_existing_callback_stub(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.generator.code_generator import generate_page_user_source
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "UserCodeDuplicateDemo"
        slider = WidgetModel("slider", name="volume_slider", x=16, y=16, width=160, height=24)
        slider.events["onValueChanged"] = "on_volume_changed"
        project, page = _create_project_and_page_with_widgets(
            project_dir,
            "UserCodeDuplicateDemo",
            sdk_root,
            widgets=[slider],
        )

        source_path = project_dir / "main_page.c"
        source_path.write_text(generate_page_user_source(page, project), encoding="utf-8")

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        refresh_calls = []
        monkeypatch.setattr(window, "_refresh_project_watch_snapshot", lambda: refresh_calls.append("refreshed"))
        monkeypatch.setattr(window, "_open_path_in_default_app", lambda path: True)

        _open_project_window(window, project, project_dir, sdk_root)
        refresh_calls.clear()
        window._on_user_code_requested("on_volume_changed", "void {func_name}(egui_view_t *self, uint8_t value)")

        content = source_path.read_text(encoding="utf-8")
        assert content.count("void on_volume_changed(egui_view_t *self, uint8_t value)") == 1
        assert not refresh_calls
        assert window.statusBar().currentMessage() == "Opened user code: main_page.c (on_volume_changed)."
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_property_panel_multi_selection_callback_edit_updates_widgets_and_dirty_state(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "BatchEventCallbackDemo"
        first = WidgetModel("slider", name="volume_slider_a", x=16, y=16, width=160, height=24)
        second = WidgetModel("slider", name="volume_slider_b", x=16, y=48, width=160, height=24)
        project = _create_project_only_with_widgets(
            project_dir,
            "BatchEventCallbackDemo",
            sdk_root,
            widgets=[first, second],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([first, second], primary=second, sync_tree=True, sync_preview=False)

        editor = window.property_panel._editors["callback_onValueChanged"]
        editor.setText("on_shared_volume_changed")
        editor.editingFinished.emit()

        assert first.events["onValueChanged"] == "on_shared_volume_changed"
        assert second.events["onValueChanged"] == "on_shared_volume_changed"
        assert window._undo_manager.is_any_dirty() is True
        assert window.statusBar().currentMessage() == "Changed main_page: property edit."
        assert window._current_page.to_xml_string().count('onValueChanged="on_shared_volume_changed"') == 2
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_resource_panel_feedback_signal_updates_status_bar(self, qapp, isolated_config):
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")

        window.res_panel.feedback_message.emit("Restored image resources: 2 restored.")

        assert window.statusBar().currentMessage() == "Restored image resources: 2 restored."
        _close_window(window)

    def test_focus_missing_resource_updates_main_window_status(self, qapp, isolated_config, tmp_path):
        from ui_designer.model.resource_catalog import ResourceCatalog
        from ui_designer.ui.main_window import MainWindow

        resource_dir = tmp_path / "project" / ".eguiproject" / "resources"
        images_dir = resource_dir / "images"
        images_dir.mkdir(parents=True)
        (images_dir / "present.png").write_bytes(b"PNG")

        catalog = ResourceCatalog()
        catalog.add_image("missing.png")
        catalog.add_image("present.png")

        window = MainWindow("")
        window.res_panel.set_resource_dir(str(resource_dir))
        window.res_panel.set_resource_catalog(catalog)

        focused = window.res_panel._focus_missing_resource("image")

        assert focused == "missing.png"
        assert window.statusBar().currentMessage() == "Focused missing image resource 1/1: missing.png."
        _close_window(window)

    def test_load_background_image_uses_existing_mockup_dir_as_initial_directory(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        def _setup_mockup_page(page, _root):
            page.mockup_image_path = "mockup/existing.png"

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "MockupDemo"
        project, page = _create_project_and_page_with_widgets(
            project_dir,
            "MockupDemo",
            sdk_root,
            page_customizer=_setup_mockup_page,
        )
        mockup_dir = project_dir / ".eguiproject" / "mockup"
        mockup_dir.mkdir(parents=True, exist_ok=True)
        (mockup_dir / "existing.png").write_bytes(b"PNG")
        captured = {}

        window = MainWindow(str(sdk_root))
        window.project = project
        window._project_dir = str(project_dir)
        window._current_page = page

        def fake_get_open_file_name(parent, title, directory, filters):
            captured["title"] = title
            captured["directory"] = directory
            captured["filters"] = filters
            return "", ""

        monkeypatch.setattr("ui_designer.ui.main_window.QFileDialog.getOpenFileName", fake_get_open_file_name)

        window._load_background_image()

        assert captured["title"] == "Load Mockup Image"
        assert captured["directory"] == os.path.normpath(os.path.abspath(mockup_dir))
        assert "Images" in captured["filters"]
        _close_window(window)

    def test_load_background_image_falls_back_to_project_dir_when_mockup_dir_missing(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "MockupDemo"
        project, page = _create_project_and_page_with_widgets(
            project_dir,
            "MockupDemo",
            sdk_root,
        )
        captured = {}

        window = MainWindow(str(sdk_root))
        window.project = project
        window._project_dir = str(project_dir)
        window._current_page = page

        def fake_get_open_file_name(parent, title, directory, filters):
            captured["directory"] = directory
            return "", ""

        monkeypatch.setattr("ui_designer.ui.main_window.QFileDialog.getOpenFileName", fake_get_open_file_name)

        window._load_background_image()

        assert captured["directory"] == os.path.normpath(os.path.abspath(project_dir))
        _close_window(window)

    def test_load_background_image_copies_file_into_shared_mockup_path(self, qapp, isolated_config, tmp_path, monkeypatch):
        from PyQt5.QtCore import Qt
        from PyQt5.QtGui import QPixmap
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "MockupCopyDemo"
        project, page = _create_project_and_page_with_widgets(
            project_dir,
            "MockupCopyDemo",
            sdk_root,
            screen_width=8,
            screen_height=8,
        )

        source_path = tmp_path / "design.png"
        pixmap = QPixmap(8, 8)
        pixmap.fill(Qt.white)
        assert pixmap.save(str(source_path))

        window = MainWindow(str(sdk_root))
        window.project = project
        window._project_dir = str(project_dir)
        window._current_page = page

        monkeypatch.setattr(
            "ui_designer.ui.main_window.QFileDialog.getOpenFileName",
            lambda *args, **kwargs: (str(source_path), "Images (*.png)"),
        )

        window._load_background_image()

        assert window._current_page.mockup_image_path == project_config_mockup_relpath("design.png")
        assert Path(project_config_mockup_path(str(project_dir), "design.png")).is_file()
        _close_window(window)

    def test_xml_edit_updates_page_mockup_metadata(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        def _setup_mockup_page(page, _root):
            page.mockup_image_path = "mockup/design.png"
            page.mockup_image_visible = False
            page.mockup_image_opacity = 0.45

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "XmlMockupDemo"
        project, xml_page = _create_project_and_page_with_widgets(
            project_dir,
            "XmlMockupDemo",
            sdk_root,
            page_customizer=_setup_mockup_page,
        )
        xml_text = xml_page.to_xml_string()
        xml_page.mockup_image_path = ""
        xml_page.mockup_image_visible = True
        xml_page.mockup_image_opacity = 0.3
        save_project_model(project, str(project_dir))

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._on_xml_changed(xml_text)

        assert window._current_page.mockup_image_path == "mockup/design.png"
        assert window._current_page.mockup_image_visible is False
        assert window._current_page.mockup_image_opacity == 0.45
        assert window._undo_manager.is_any_dirty() is True
        assert window.history_panel._source_value.text() == "Source: xml edit"
        history_items = [window.history_panel._history_list.item(i).text() for i in range(window.history_panel._history_list.count())]
        assert any("xml edit" in item and "Current" in item for item in history_items)
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_toggle_background_image_marks_dirty_and_supports_undo(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        def _setup_mockup_page(page, _root):
            page.mockup_image_path = "mockup/design.png"
            page.mockup_image_visible = True

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "MockupUndoDemo"
        project = _create_project_only_with_widgets(
            project_dir,
            "MockupUndoDemo",
            sdk_root,
            page_customizer=_setup_mockup_page,
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        assert window._undo_manager.is_any_dirty() is False

        window._toggle_background_image(False)

        assert window._current_page.mockup_image_visible is False
        assert window._undo_manager.is_any_dirty() is True
        assert window.history_panel._dirty_value.text() == "Dirty: Yes"
        assert window.history_panel._source_value.text() == "Source: mockup visibility"

        window._undo()

        assert window._current_page.mockup_image_visible is True
        assert window._undo_manager.is_any_dirty() is False
        assert window.history_panel._dirty_value.text() == "Dirty: No"
        assert window.history_panel._source_value.text() == "Source: Saved state"
        _close_window(window)

    def test_resource_rename_updates_widget_references_across_pages(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "RenameResourceDemo"
        image_a = WidgetModel("image", name="image_a")
        image_a.properties["image_file"] = "star.png"
        image_b = WidgetModel("image", name="image_b")
        image_b.properties["image_file"] = "star.png"
        project = _create_project_only_with_page_widgets(
            project_dir,
            "RenameResourceDemo",
            sdk_root,
            page_widgets={
                "main_page": [image_a],
                "detail_page": [image_b],
            },
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._selected_widget = image_a
        window.property_panel.set_widget(image_a)

        window._on_resource_renamed("image", "star.png", "star_new.png")

        assert image_a.properties["image_file"] == "star_new.png"
        assert image_b.properties["image_file"] == "star_new.png"
        assert window._undo_manager.get_stack("main_page").is_dirty() is True
        assert window._undo_manager.get_stack("detail_page").is_dirty() is True
        assert window.statusBar().currentMessage() == "Updated resources in 2 pages: image resource rename."
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_replace_missing_resource_updates_widget_references_across_pages(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        def _setup_project(project):
            project.resource_catalog.add_image("star.png")

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "ReplaceMissingResourceDemo"
        image_a = WidgetModel("image", name="image_a")
        image_a.properties["image_file"] = "star.png"
        image_b = WidgetModel("image", name="image_b")
        image_b.properties["image_file"] = "star.png"
        project = _create_project_only_with_page_widgets(
            project_dir,
            "ReplaceMissingResourceDemo",
            sdk_root,
            page_widgets={
                "main_page": [image_a],
                "detail_page": [image_b],
            },
            project_customizer=_setup_project,
        )

        replacement_dir = tmp_path / "external_images"
        replacement_dir.mkdir()
        replacement_path = replacement_dir / "star_new.png"
        replacement_path.write_bytes(b"PNG")

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._selected_widget = image_a
        window.property_panel.set_widget(image_a)

        restored, renamed, failures = window.res_panel._replace_missing_resources_from_mapping(
            "image",
            {"star.png": str(replacement_path)},
        )

        assert restored == []
        assert renamed == [("star.png", "star_new.png")]
        assert failures == []
        assert image_a.properties["image_file"] == "star_new.png"
        assert image_b.properties["image_file"] == "star_new.png"
        assert window.project.resource_catalog.has_image("star_new.png") is True
        assert window.project.resource_catalog.has_image("star.png") is False
        assert window._undo_manager.get_stack("main_page").is_dirty() is True
        assert window._undo_manager.get_stack("detail_page").is_dirty() is True
        assert window.statusBar().currentMessage() == "Replaced image resources: 1 renamed."
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_replace_missing_resources_batch_preview_confirmation_updates_widget_references_across_pages(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        def _setup_project(project):
            project.resource_catalog.add_image("star.png")

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "ReplaceMissingBatchPreviewDemo"
        image_a = WidgetModel("image", name="image_a")
        image_a.properties["image_file"] = "star.png"
        image_b = WidgetModel("image", name="image_b")
        image_b.properties["image_file"] = "star.png"
        project = _create_project_only_with_page_widgets(
            project_dir,
            "ReplaceMissingBatchPreviewDemo",
            sdk_root,
            page_widgets={
                "main_page": [image_a],
                "detail_page": [image_b],
            },
            project_customizer=_setup_project,
        )

        replacement_dir = tmp_path / "external_images"
        replacement_dir.mkdir()
        replacement_path = replacement_dir / "star_new.png"
        replacement_path.write_bytes(b"PNG")

        preview_calls = []

        class FakeDialog:
            def __init__(self, missing_names, source_paths, parent=None):
                assert missing_names == ["star.png"]
                assert source_paths == [str(replacement_path)]

            def exec_(self):
                return 1

            def selected_mapping(self):
                return {"star.png": str(replacement_path)}

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(
            "ui_designer.ui.resource_panel.QFileDialog.getOpenFileNames",
            lambda *args, **kwargs: ([str(replacement_path)], "Images (*.png *.bmp *.jpg *.jpeg)"),
        )
        monkeypatch.setattr("ui_designer.ui.resource_panel._MissingResourceReplaceDialog", FakeDialog)
        monkeypatch.setattr(
            window.res_panel,
            "_confirm_batch_replace_impact",
            lambda resource_type, impacts, total_rename_count: preview_calls.append((resource_type, impacts, total_rename_count)) or True,
        )

        _open_project_window(window, project, project_dir, sdk_root)
        assert window.res_panel._missing_resource_names("image") == ["star.png"]
        window._selected_widget = image_a
        window.property_panel.set_widget(image_a)

        window.res_panel._replace_missing_resources("image")

        assert len(preview_calls) == 1
        assert preview_calls[0][0] == "image"
        assert preview_calls[0][2] == 1
        assert preview_calls[0][1][0]["old_name"] == "star.png"
        assert preview_calls[0][1][0]["new_name"] == "star_new.png"
        assert image_a.properties["image_file"] == "star_new.png"
        assert image_b.properties["image_file"] == "star_new.png"
        assert window.project.resource_catalog.has_image("star_new.png") is True
        assert window.project.resource_catalog.has_image("star.png") is False
        assert window._undo_manager.get_stack("main_page").is_dirty() is True
        assert window._undo_manager.get_stack("detail_page").is_dirty() is True
        assert window.statusBar().currentMessage() == "Replaced image resources: 1 renamed."
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_resource_panel_rename_preserves_specific_status_message(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        def _setup_project(project):
            project.resource_catalog.add_image("star.png")

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "RenameResourceSignalDemo"
        images_dir = project_dir / ".eguiproject" / "resources" / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        (images_dir / "star.png").write_bytes(b"PNG")

        image_a = WidgetModel("image", name="image_a")
        image_a.properties["image_file"] = "star.png"
        image_b = WidgetModel("image", name="image_b")
        image_b.properties["image_file"] = "star.png"
        project = _create_project_only_with_page_widgets(
            project_dir,
            "RenameResourceSignalDemo",
            sdk_root,
            page_widgets={
                "main_page": [image_a],
                "detail_page": [image_b],
            },
            project_customizer=_setup_project,
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(
            "ui_designer.ui.resource_panel.QInputDialog.getText",
            lambda *args, **kwargs: ("star_new.png", True),
        )
        monkeypatch.setattr(window.res_panel, "_confirm_reference_impact", lambda *args: True)

        _open_project_window(window, project, project_dir, sdk_root)
        window._selected_widget = image_a
        window.property_panel.set_widget(image_a)

        window.res_panel._rename_resource("star.png", "image")

        assert image_a.properties["image_file"] == "star_new.png"
        assert image_b.properties["image_file"] == "star_new.png"
        assert window.statusBar().currentMessage() == "Updated resources in 2 pages: image resource rename."
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_resource_delete_clears_widget_references(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "DeleteResourceDemo"
        label = WidgetModel("label", name="title")
        label.properties["font_file"] = "demo.ttf"
        project = _create_project_only_with_widgets(
            project_dir,
            "DeleteResourceDemo",
            sdk_root,
            widgets=[label],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)

        _open_project_window(window, project, project_dir, sdk_root)
        window._selected_widget = label
        window.property_panel.set_widget(label)

        window._on_resource_deleted("font", "demo.ttf")

        assert label.properties["font_file"] == ""
        assert window._undo_manager.get_stack("main_page").is_dirty() is True
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_resource_selected_assigns_text_file_to_selected_widget(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "AssignTextResourceDemo"
        label = WidgetModel("label", name="title")
        label.properties["font_file"] = "demo.ttf"
        project = _create_project_only_with_widgets(
            project_dir,
            "AssignTextResourceDemo",
            sdk_root,
            widgets=[label],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._selected_widget = label
        window.property_panel.set_widget(label)

        window._on_resource_selected("text", "chars.txt")

        assert label.properties["font_text_file"] == "chars.txt"
        assert window._undo_manager.get_stack("main_page").is_dirty() is True
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_generate_charset_from_resource_panel_binds_text_file_to_selected_widget(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "GenerateCharsetDemo"
        label = WidgetModel("label", name="title")
        label.properties["font_file"] = "demo.ttf"
        project = _create_project_only_with_widgets(
            project_dir,
            "GenerateCharsetDemo",
            sdk_root,
            widgets=[label],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._selected_widget = label
        window.property_panel.set_widget(label)

        expected_resource_dir = os.path.join(str(project_dir), ".eguiproject", "resources")

        class FakeDialog:
            _source_label = "demo_font.ttf"

            def __init__(self, resource_dir_arg, initial_filename="", source_label="", initial_preset_ids=(), initial_custom_text="", parent=None):
                assert os.path.normpath(resource_dir_arg) == os.path.normpath(expected_resource_dir)
                assert initial_filename == ""
                assert source_label == ""
                assert initial_preset_ids == ()
                assert initial_custom_text == ""

            def exec_(self):
                return 1

            def filename(self):
                return "charset_combo.txt"

            def generated_text(self):
                return "A\nB\n&#x4E2D;\n"

            def generated_chars(self):
                return ("A", "B", "\u4E2D")

            def overwrite_diff(self):
                return type(
                    "_Diff",
                    (),
                    {
                        "existing_count": 0,
                        "new_count": 3,
                        "added_count": 3,
                        "removed_count": 0,
                    },
                )()

            def save_and_assign(self):
                return True

        monkeypatch.setattr("ui_designer.ui.resource_panel._GenerateCharsetDialog", FakeDialog)

        window.res_panel._on_generate_charset()

        generated_path = project_dir / ".eguiproject" / "resources" / "charset_combo.txt"
        assert generated_path.read_text(encoding="utf-8") == "A\nB\n&#x4E2D;\n"
        assert label.properties["font_text_file"] == "charset_combo.txt"
        assert window.project.resource_catalog.has_text_file("charset_combo.txt")
        assert window.res_panel._tabs.currentIndex() == 2
        assert window.res_panel._text_list.currentItem().data(Qt.UserRole + 1) == "charset_combo.txt"
        assert window._undo_manager.get_stack("main_page").is_dirty() is True
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_property_panel_generate_charset_signal_switches_to_assets_and_opens_generator(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PropertyCharsetDemo"
        label = WidgetModel("label", name="title")
        label.properties["font_file"] = "demo_font.ttf"
        label.properties["font_text_file"] = "chars.txt"
        project = _create_project_only_with_widgets(
            project_dir,
            "PropertyCharsetDemo",
            sdk_root,
            widgets=[label],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._selected_widget = label
        window.property_panel.set_widget(label)
        captured = []
        monkeypatch.setattr(
            window.res_panel,
            "open_generate_charset_dialog_for_resource",
            lambda resource_type, source_name, initial_filename="": captured.append((resource_type, source_name, initial_filename)),
        )

        window.property_panel.generate_charset_requested.emit("font", "demo_font.ttf", "chars.txt")

        assert window._left_panel_stack.currentWidget() is window.res_panel
        assert captured == [("font", "demo_font.ttf", "chars.txt")]
        _close_window(window)

    def test_property_panel_generate_charset_keeps_existing_text_resource_hint_for_res_panel(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PropertyCharsetPresetDemo"
        label = WidgetModel("label", name="title")
        label.properties["font_file"] = "simhei.ttf"
        label.properties["font_text_file"] = "charset_ascii_printable.txt"
        project = _create_project_only_with_widgets(
            project_dir,
            "PropertyCharsetPresetDemo",
            sdk_root,
            widgets=[label],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._selected_widget = label
        window.property_panel.set_widget(label)
        captured = []
        monkeypatch.setattr(
            window.res_panel,
            "open_generate_charset_dialog_for_resource",
            lambda resource_type, source_name, initial_filename="": captured.append((resource_type, source_name, initial_filename)),
        )

        window.property_panel.generate_charset_requested.emit("font", "simhei.ttf", "charset_ascii_printable.txt")

        assert window._left_panel_stack.currentWidget() is window.res_panel
        assert captured == [("font", "simhei.ttf", "charset_ascii_printable.txt")]
        _close_window(window)

    def test_resource_rename_updates_text_references_across_pages(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "RenameTextResourceDemo"
        label_a = WidgetModel("label", name="label_a")
        label_a.properties["font_file"] = "demo.ttf"
        label_a.properties["font_text_file"] = "chars.txt"
        label_b = WidgetModel("label", name="label_b")
        label_b.properties["font_file"] = "demo.ttf"
        label_b.properties["font_text_file"] = "chars.txt"
        project = _create_project_only_with_page_widgets(
            project_dir,
            "RenameTextResourceDemo",
            sdk_root,
            page_widgets={
                "main_page": [label_a],
                "detail_page": [label_b],
            },
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._selected_widget = label_a
        window.property_panel.set_widget(label_a)

        window._on_resource_renamed("text", "chars.txt", "chars_new.txt")

        assert label_a.properties["font_text_file"] == "chars_new.txt"
        assert label_b.properties["font_text_file"] == "chars_new.txt"
        assert window._undo_manager.get_stack("main_page").is_dirty() is True
        assert window._undo_manager.get_stack("detail_page").is_dirty() is True
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_resource_delete_clears_text_references(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "DeleteTextResourceDemo"
        label = WidgetModel("label", name="title")
        label.properties["font_file"] = "demo.ttf"
        label.properties["font_text_file"] = "chars.txt"
        project = _create_project_only_with_widgets(
            project_dir,
            "DeleteTextResourceDemo",
            sdk_root,
            widgets=[label],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._selected_widget = label
        window.property_panel.set_widget(label)

        window._on_resource_deleted("text", "chars.txt")

        assert label.properties["font_text_file"] == ""
        assert window._undo_manager.get_stack("main_page").is_dirty() is True
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_string_key_delete_rewrites_widget_text_refs_to_default_literal(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.string_resource import DEFAULT_LOCALE
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        def _setup_project(project):
            project.string_catalog.set("greeting", "Hello", DEFAULT_LOCALE)
            project.string_catalog.set("greeting", "Ni Hao", "zh")

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "DeleteStringKeyDemo"
        title = WidgetModel("label", name="title")
        title.properties["text"] = "@string/greeting"
        subtitle = WidgetModel("label", name="subtitle")
        subtitle.properties["text"] = "@string/greeting"
        project = _create_project_only_with_page_widgets(
            project_dir,
            "DeleteStringKeyDemo",
            sdk_root,
            page_widgets={
                "main_page": [title],
                "detail_page": [subtitle],
            },
            project_customizer=_setup_project,
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.res_panel, "_confirm_reference_impact", lambda *args: True)

        _open_project_window(window, project, project_dir, sdk_root)
        window.res_panel._select_resource_item("string", "greeting")

        window.res_panel._on_remove_string_key()

        assert title.properties["text"] == "Hello"
        assert subtitle.properties["text"] == "Hello"
        assert "greeting" not in window.project.string_catalog.all_keys
        assert window._undo_manager.get_stack("main_page").is_dirty() is True
        assert window._undo_manager.get_stack("detail_page").is_dirty() is True
        assert window.statusBar().currentMessage() == "Updated resources in 2 pages: string key delete."
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_string_key_rename_updates_widget_text_refs_across_pages(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.string_resource import DEFAULT_LOCALE
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        def _setup_project(project):
            project.string_catalog.set("greeting", "Hello", DEFAULT_LOCALE)
            project.string_catalog.set("greeting", "Ni Hao", "zh")

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "RenameStringKeyDemo"
        title = WidgetModel("label", name="title")
        title.properties["text"] = "@string/greeting"
        subtitle = WidgetModel("label", name="subtitle")
        subtitle.properties["text"] = "@string/greeting"
        project = _create_project_only_with_page_widgets(
            project_dir,
            "RenameStringKeyDemo",
            sdk_root,
            page_widgets={
                "main_page": [title],
                "detail_page": [subtitle],
            },
            project_customizer=_setup_project,
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(
            "ui_designer.ui.resource_panel.QInputDialog.getText",
            lambda *args, **kwargs: ("salutation", True),
        )
        monkeypatch.setattr(window.res_panel, "_confirm_reference_impact", lambda *args: True)

        _open_project_window(window, project, project_dir, sdk_root)
        window.res_panel._select_resource_item("string", "greeting")

        window.res_panel._on_rename_string_key()

        assert title.properties["text"] == "@string/salutation"
        assert subtitle.properties["text"] == "@string/salutation"
        assert window.project.string_catalog.get("salutation", DEFAULT_LOCALE) == "Hello"
        assert "greeting" not in window.project.string_catalog.all_keys
        assert window._undo_manager.get_stack("main_page").is_dirty() is True
        assert window._undo_manager.get_stack("detail_page").is_dirty() is True
        assert window.statusBar().currentMessage() == "Updated resources in 2 pages: string key rename."
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_string_key_delete_can_focus_usage_without_deleting(self, tmp_path):
        repo_root = Path(__file__).resolve().parents[4]
        script = textwrap.dedent(
            f"""
            import os
            import shutil
            import sys
            from pathlib import Path

            os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

            repo_root = Path({repr(str(repo_root))})
            sys.path.insert(0, str(repo_root / "scripts"))

            from PyQt5.QtWidgets import QApplication

            from ui_designer.model.string_resource import DEFAULT_LOCALE
            from ui_designer.model.widget_model import WidgetModel
            from ui_designer.tests.project_builders import build_saved_test_project_only_with_page_widgets
            from ui_designer.tests.ui.window_test_helpers import (
                disable_main_window_compile as _disable_window_compile,
                open_loaded_test_project as _open_project_window,
            )
            from ui_designer.ui.main_window import MainWindow
            from ui_designer.utils.runtime_temp import create_repo_temp_workspace


            def create_sdk_root(root: Path):
                (root / "src").mkdir(parents=True)
                (root / "porting" / "designer").mkdir(parents=True)
                (root / "Makefile").write_text("all:\\n", encoding="utf-8")
            class DisabledCompiler:
                def can_build(self):
                    return False

                def is_preview_running(self):
                    return False

                def stop_exe(self):
                    return None

                def cleanup(self):
                    return None

                def get_build_error(self):
                    return "preview disabled for test"

                def set_screen_size(self, width, height):
                    return None

                def is_exe_ready(self):
                    return False


            temp_root = create_repo_temp_workspace(repo_root, "ui_designer_string_delete_inspect_")
            app = QApplication.instance() or QApplication([])
            try:
                sdk_root = temp_root / "sdk"
                create_sdk_root(sdk_root)
                project_dir = temp_root / "DeleteStringKeyInspectDemo"
                subtitle = WidgetModel("label", name="subtitle")
                subtitle.properties["text"] = "@string/greeting"
                project = build_saved_test_project_only_with_page_widgets(
                    project_dir,
                    "DeleteStringKeyInspectDemo",
                    sdk_root,
                    page_widgets={{"detail_page": [subtitle]}},
                    pages=["main_page", "detail_page"],
                    project_customizer=lambda project: project.string_catalog.set("greeting", "Hello", DEFAULT_LOCALE),
                )

                window = MainWindow(str(sdk_root))
                _disable_window_compile(window, DisabledCompiler)

                def inspect_usage(*args):
                    window.res_panel.usage_activated.emit("detail_page", "subtitle")
                    return False

                window.res_panel._confirm_reference_impact = inspect_usage

                _open_project_window(window, project, project_dir, sdk_root)
                assert window._current_page.name == "main_page"
                window.res_panel._select_resource_item("string", "greeting")

                window.res_panel._on_remove_string_key()

                assert window._current_page.name == "detail_page"
                assert window._selection_state.primary is subtitle
                assert window.project.string_catalog.get("greeting", DEFAULT_LOCALE) == "Hello"
                assert subtitle.properties["text"] == "@string/greeting"
                assert window.statusBar().currentMessage() == "Focused resource usage: detail_page/subtitle."
                assert window._undo_manager.is_any_dirty() is False

                window._undo_manager.mark_all_saved()
                window.close()
                window.deleteLater()
                app.sendPostedEvents()
                app.processEvents()
            finally:
                shutil.rmtree(temp_root, ignore_errors=True)
            """
        )

        env = os.environ.copy()
        env.setdefault("QT_QPA_PLATFORM", "offscreen")
        result = subprocess.run(
            [sys.executable, "-c", script],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            timeout=60,
        )

        assert result.returncode == 0, f"stdout:\\n{result.stdout}\\n\\nstderr:\\n{result.stderr}"

    def test_string_key_usage_activation_switches_page_and_selects_widget(self, tmp_path):
        repo_root = Path(__file__).resolve().parents[4]
        script = textwrap.dedent(
            f"""
            import os
            import shutil
            import sys
            from pathlib import Path

            os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

            repo_root = Path({repr(str(repo_root))})
            sys.path.insert(0, str(repo_root / "scripts"))

            from PyQt5.QtWidgets import QApplication

            from ui_designer.model.string_resource import DEFAULT_LOCALE
            from ui_designer.model.widget_model import WidgetModel
            from ui_designer.tests.project_builders import build_saved_test_project_only_with_page_widgets
            from ui_designer.tests.ui.window_test_helpers import (
                disable_main_window_compile as _disable_window_compile,
                open_loaded_test_project as _open_project_window,
            )
            from ui_designer.ui.main_window import MainWindow
            from ui_designer.utils.runtime_temp import create_repo_temp_workspace


            def create_sdk_root(root: Path):
                (root / "src").mkdir(parents=True)
                (root / "porting" / "designer").mkdir(parents=True)
                (root / "Makefile").write_text("all:\\n", encoding="utf-8")
            class DisabledCompiler:
                def can_build(self):
                    return False

                def is_preview_running(self):
                    return False

                def stop_exe(self):
                    return None

                def cleanup(self):
                    return None

                def get_build_error(self):
                    return "preview disabled for test"

                def set_screen_size(self, width, height):
                    return None

                def is_exe_ready(self):
                    return False


            temp_root = create_repo_temp_workspace(repo_root, "ui_designer_string_usage_")
            app = QApplication.instance() or QApplication([])
            try:
                sdk_root = temp_root / "sdk"
                create_sdk_root(sdk_root)
                project_dir = temp_root / "StringUsageNavigationDemo"
                subtitle = WidgetModel("label", name="subtitle")
                subtitle.properties["text"] = "@string/greeting"
                project = build_saved_test_project_only_with_page_widgets(
                    project_dir,
                    "StringUsageNavigationDemo",
                    sdk_root,
                    page_widgets={{"detail_page": [subtitle]}},
                    pages=["main_page", "detail_page"],
                    project_customizer=lambda project: project.string_catalog.set("greeting", "Hello", DEFAULT_LOCALE),
                )

                window = MainWindow(str(sdk_root))
                _disable_window_compile(window, DisabledCompiler)

                _open_project_window(window, project, project_dir, sdk_root)
                assert window._current_page.name == "main_page"

                window.res_panel._select_resource_item("string", "greeting")
                window.res_panel._on_usage_item_activated(window.res_panel._usage_table.item(0, 0))

                assert window._current_page.name == "detail_page"
                assert window._selection_state.primary is subtitle
                assert window.statusBar().currentMessage() == "Focused resource usage: detail_page/subtitle."

                window._undo_manager.mark_all_saved()
                window.close()
                window.deleteLater()
                app.sendPostedEvents()
                app.processEvents()
            finally:
                shutil.rmtree(temp_root, ignore_errors=True)
            """
        )

        env = os.environ.copy()
        env.setdefault("QT_QPA_PLATFORM", "offscreen")
        result = subprocess.run(
            [sys.executable, "-c", script],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            timeout=60,
        )

        assert result.returncode == 0, f"stdout:\\n{result.stdout}\\n\\nstderr:\\n{result.stderr}"

    def test_resource_usage_activation_switches_page_and_selects_widget(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        def _setup_project(project):
            project.resource_catalog.add_image("star.png")

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "ResourceUsageNavigationDemo"
        hero = WidgetModel("image", name="hero")
        hero.properties["image_file"] = "star.png"
        project = _create_project_only_with_page_widgets(
            project_dir,
            "ResourceUsageNavigationDemo",
            sdk_root,
            page_widgets={"detail_page": [hero]},
            pages=["main_page", "detail_page"],
            project_customizer=_setup_project,
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)

        assert window._current_page.name == "main_page"

        window._show_inspector_tab("animations")
        assert window._inspector_tabs.currentIndex() == 1

        window.res_panel._select_resource_item("image", "star.png")
        window.res_panel._on_usage_item_activated(window.res_panel._usage_table.item(0, 0))

        assert window._current_page.name == "detail_page"
        assert window._selection_state.primary is hero
        assert window._selection_state.widgets == [hero]
        assert window._inspector_tabs.currentIndex() == 0
        assert window.statusBar().currentMessage() == "Focused resource usage: detail_page/hero."
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_resource_usage_filter_tracks_current_page(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        def _setup_project(project):
            project.resource_catalog.add_image("star.png")

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "ResourceUsageFilterDemo"
        hero_main = WidgetModel("image", name="hero_main")
        hero_main.properties["image_file"] = "star.png"
        hero_detail = WidgetModel("image", name="hero_detail")
        hero_detail.properties["image_file"] = "star.png"
        project = _create_project_only_with_page_widgets(
            project_dir,
            "ResourceUsageFilterDemo",
            sdk_root,
            page_widgets={
                "main_page": [hero_main],
                "detail_page": [hero_detail],
            },
            project_customizer=_setup_project,
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window.res_panel._usage_current_page_only.setChecked(True)
        window.res_panel._select_resource_item("image", "star.png")

        assert window._current_page.name == "main_page"
        assert window.res_panel._usage_table.rowCount() == 1
        assert window.res_panel._usage_table.item(0, 0).text() == "main_page"

        window._switch_page("detail_page")

        assert window.res_panel._usage_table.rowCount() == 1
        assert window.res_panel._usage_table.item(0, 0).text() == "detail_page"
        assert window.res_panel._usage_summary.text() == "1 widget on this page | 2 total across 2 pages | star.png"
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_poll_project_files_auto_reloads_clean_project(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "WatchDemo"
        project = _create_project(project_dir, "WatchDemo", sdk_root)

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)

        reload_calls = []
        monkeypatch.setattr(
            window,
            "_reload_project_from_disk",
            lambda *args, **kwargs: reload_calls.append(kwargs) or True,
        )

        layout_file = project_dir / ".eguiproject" / "layout" / "main_page.xml"
        layout_file.write_text(layout_file.read_text(encoding="utf-8") + "\n<!-- external -->\n", encoding="utf-8")

        window._poll_project_files()

        assert len(reload_calls) == 1
        assert reload_calls[0]["auto"] is True
        assert os.path.normpath(os.path.abspath(layout_file)) in reload_calls[0]["changed_paths"]
        _close_window(window)

    def test_poll_project_files_marks_pending_when_project_is_dirty(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "DirtyWatchDemo"
        project = _create_project(project_dir, "DirtyWatchDemo", sdk_root)

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._undo_manager.get_stack("main_page").push("<Page dirty='1' />")

        reload_calls = []
        monkeypatch.setattr(
            window,
            "_reload_project_from_disk",
            lambda *args, **kwargs: reload_calls.append(kwargs) or True,
        )

        layout_file = project_dir / ".eguiproject" / "layout" / "main_page.xml"
        layout_file.write_text(layout_file.read_text(encoding="utf-8") + "\n<!-- dirty external -->\n", encoding="utf-8")

        window._poll_project_files()

        assert reload_calls == []
        assert window._external_reload_pending is True
        assert window._external_reload_changed_paths == [os.path.normpath(os.path.abspath(layout_file))]
        assert window.statusBar().currentMessage() == (
            "External project changes detected: main_page.xml. Local unsaved changes remain: 1 page. "
            "Save or reload from disk to sync."
        )
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_poll_project_files_marks_pending_when_only_project_state_is_dirty(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "ProjectStateDirtyWatchDemo"
        project = _create_project(
            project_dir,
            "ProjectStateDirtyWatchDemo",
            sdk_root,
            pages=["main_page", "detail_page"],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._on_startup_changed("detail_page")

        reload_calls = []
        monkeypatch.setattr(
            window,
            "_reload_project_from_disk",
            lambda *args, **kwargs: reload_calls.append(kwargs) or True,
        )

        layout_file = project_dir / ".eguiproject" / "layout" / "main_page.xml"
        layout_file.write_text(layout_file.read_text(encoding="utf-8") + "\n<!-- project state dirty external -->\n", encoding="utf-8")

        window._poll_project_files()

        assert window._undo_manager.is_any_dirty() is False
        assert reload_calls == []
        assert window._external_reload_pending is True
        assert window._external_reload_changed_paths == [os.path.normpath(os.path.abspath(layout_file))]
        assert window.statusBar().currentMessage() == (
            "External project changes detected: main_page.xml. Local unsaved changes remain: project changes (startup page). "
            "Save or reload from disk to sync."
        )
        _close_window(window)

    def test_poll_project_files_marks_pending_with_page_and_project_dirty_reason_summary(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "MixedDirtyWatchDemo"
        project = _create_project(
            project_dir,
            "MixedDirtyWatchDemo",
            sdk_root,
            pages=["main_page", "detail_page"],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._switch_page("detail_page")
        stack = window._undo_manager.get_stack("detail_page")
        stack.push("state 1", label="initial")
        stack.mark_saved()
        stack.push("state 2", label="changed")
        window._update_window_title()
        window._on_startup_changed("detail_page")

        reload_calls = []
        monkeypatch.setattr(
            window,
            "_reload_project_from_disk",
            lambda *args, **kwargs: reload_calls.append(kwargs) or True,
        )

        layout_file = project_dir / ".eguiproject" / "layout" / "main_page.xml"
        layout_file.write_text(layout_file.read_text(encoding="utf-8") + "\n<!-- mixed dirty external -->\n", encoding="utf-8")

        window._poll_project_files()

        assert reload_calls == []
        assert window._external_reload_pending is True
        assert window._external_reload_changed_paths == [os.path.normpath(os.path.abspath(layout_file))]
        assert window.statusBar().currentMessage() == (
            "External project changes detected: main_page.xml. Local unsaved changes remain: "
            "1 page + project changes (startup page). Save or reload from disk to sync."
        )
        _close_window(window)

    def test_poll_project_files_reports_compile_wait_with_changed_file_summary(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        class _BusyWorker:
            def isRunning(self):
                return True

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "CompileWaitWatchDemo"
        project = _create_project(project_dir, "CompileWaitWatchDemo", sdk_root)

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._compile_worker = _BusyWorker()

        reload_calls = []
        monkeypatch.setattr(
            window,
            "_reload_project_from_disk",
            lambda *args, **kwargs: reload_calls.append(kwargs) or True,
        )

        layout_file = project_dir / ".eguiproject" / "layout" / "main_page.xml"
        layout_file.write_text(layout_file.read_text(encoding="utf-8") + "\n<!-- compile wait external -->\n", encoding="utf-8")

        window._poll_project_files()

        assert reload_calls == []
        assert window._external_reload_pending is True
        assert window._external_reload_changed_paths == [os.path.normpath(os.path.abspath(layout_file))]
        assert window.statusBar().currentMessage() == (
            "External project changes detected: main_page.xml. Reload will resume after background compile."
        )
        window._compile_worker = None
        _close_window(window)

    def test_poll_project_files_reports_precompile_wait_with_changed_file_summary(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        class _BusyWorker:
            def isRunning(self):
                return True

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PrecompileWaitWatchDemo"
        project = _create_project(project_dir, "PrecompileWaitWatchDemo", sdk_root)

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._precompile_worker = _BusyWorker()

        reload_calls = []
        monkeypatch.setattr(
            window,
            "_reload_project_from_disk",
            lambda *args, **kwargs: reload_calls.append(kwargs) or True,
        )

        layout_file = project_dir / ".eguiproject" / "layout" / "main_page.xml"
        layout_file.write_text(layout_file.read_text(encoding="utf-8") + "\n<!-- precompile wait external -->\n", encoding="utf-8")

        window._poll_project_files()

        assert reload_calls == []
        assert window._external_reload_pending is True
        assert window._external_reload_changed_paths == [os.path.normpath(os.path.abspath(layout_file))]
        assert window.statusBar().currentMessage() == (
            "External project changes detected: main_page.xml. Reload will resume after background compile."
        )
        window._precompile_worker = None
        _close_window(window)

    def test_pending_external_reload_preserves_changed_paths_until_dirty_clears(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PendingDirtyReloadResumeDemo"
        project = _create_project(project_dir, "PendingDirtyReloadResumeDemo", sdk_root)

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._undo_manager.get_stack("main_page").push("<Page dirty='1' />")

        reload_calls = []

        def _capture_reload(*args, **kwargs):
            reload_calls.append(kwargs)
            window._clear_external_reload_pending()
            return True

        monkeypatch.setattr(window, "_reload_project_from_disk", _capture_reload)

        layout_file = project_dir / ".eguiproject" / "layout" / "main_page.xml"
        layout_file.write_text(layout_file.read_text(encoding="utf-8") + "\n<!-- resume dirty external -->\n", encoding="utf-8")

        window._poll_project_files()
        assert reload_calls == []
        assert window._external_reload_changed_paths == [os.path.normpath(os.path.abspath(layout_file))]

        window._undo_manager.mark_all_saved()
        window._poll_project_files()

        assert len(reload_calls) == 1
        assert reload_calls[0]["auto"] is True
        assert reload_calls[0]["changed_paths"] == [os.path.normpath(os.path.abspath(layout_file))]
        assert window._external_reload_pending is False
        assert window._external_reload_changed_paths == []
        _close_window(window)

    def test_pending_external_reload_preserves_changed_paths_until_compile_finishes(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        class _BusyWorker:
            def isRunning(self):
                return True

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PendingCompileReloadResumeDemo"
        project = _create_project(project_dir, "PendingCompileReloadResumeDemo", sdk_root)

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._compile_worker = _BusyWorker()

        reload_calls = []

        def _capture_reload(*args, **kwargs):
            reload_calls.append(kwargs)
            window._clear_external_reload_pending()
            return True

        monkeypatch.setattr(window, "_reload_project_from_disk", _capture_reload)

        layout_file = project_dir / ".eguiproject" / "layout" / "main_page.xml"
        layout_file.write_text(layout_file.read_text(encoding="utf-8") + "\n<!-- resume compile external -->\n", encoding="utf-8")

        window._poll_project_files()
        assert reload_calls == []
        assert window._external_reload_changed_paths == [os.path.normpath(os.path.abspath(layout_file))]

        window._compile_worker = None
        window._poll_project_files()

        assert len(reload_calls) == 1
        assert reload_calls[0]["auto"] is True
        assert reload_calls[0]["changed_paths"] == [os.path.normpath(os.path.abspath(layout_file))]
        assert window._external_reload_pending is False
        assert window._external_reload_changed_paths == []
        _close_window(window)

    def test_pending_external_reload_preserves_changed_paths_until_precompile_finishes(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        class _BusyWorker:
            def isRunning(self):
                return True

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PendingPrecompileReloadResumeDemo"
        project = _create_project(project_dir, "PendingPrecompileReloadResumeDemo", sdk_root)

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._precompile_worker = _BusyWorker()

        reload_calls = []

        def _capture_reload(*args, **kwargs):
            reload_calls.append(kwargs)
            window._clear_external_reload_pending()
            return True

        monkeypatch.setattr(window, "_reload_project_from_disk", _capture_reload)

        layout_file = project_dir / ".eguiproject" / "layout" / "main_page.xml"
        layout_file.write_text(layout_file.read_text(encoding="utf-8") + "\n<!-- resume precompile external -->\n", encoding="utf-8")

        window._poll_project_files()
        assert reload_calls == []
        assert window._external_reload_changed_paths == [os.path.normpath(os.path.abspath(layout_file))]

        window._precompile_worker = None
        window._poll_project_files()

        assert len(reload_calls) == 1
        assert reload_calls[0]["auto"] is True
        assert reload_calls[0]["changed_paths"] == [os.path.normpath(os.path.abspath(layout_file))]
        assert window._external_reload_pending is False
        assert window._external_reload_changed_paths == []
        _close_window(window)

    def test_save_project_clears_pending_external_reload_state(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "SaveClearsPendingReloadDemo"
        project = _create_project(project_dir, "SaveClearsPendingReloadDemo", sdk_root)

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window, "_load_project_app_local_widgets", lambda *args, **kwargs: None)

        _open_project_window(window, project, project_dir, sdk_root)
        window._undo_manager.get_stack("main_page").push("<Page dirty='1' />")

        layout_file = project_dir / ".eguiproject" / "layout" / "main_page.xml"
        layout_file.write_text(layout_file.read_text(encoding="utf-8") + "\n<!-- save clears pending external -->\n", encoding="utf-8")

        window._poll_project_files()

        assert window._external_reload_pending is True
        assert window._external_reload_changed_paths == [os.path.normpath(os.path.abspath(layout_file))]

        assert window._save_project() is True
        assert window._external_reload_pending is False
        assert window._external_reload_changed_paths == []
        _close_window(window)

    def test_pending_external_reload_retries_with_same_changed_paths_after_reload_failure(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.model.project import Project
        from ui_designer.ui.main_window import MainWindow

        class _BusyWorker:
            def isRunning(self):
                return True

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PendingReloadFailureRetryDemo"
        project = _create_project(project_dir, "PendingReloadFailureRetryDemo", sdk_root)

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._compile_worker = _BusyWorker()

        layout_file = project_dir / ".eguiproject" / "layout" / "main_page.xml"
        layout_file.write_text(layout_file.read_text(encoding="utf-8") + "\n<!-- reload failure retry external -->\n", encoding="utf-8")

        window._poll_project_files()
        assert window._external_reload_pending is True
        assert window._external_reload_changed_paths == [os.path.normpath(os.path.abspath(layout_file))]

        window._compile_worker = None
        monkeypatch.setattr(
            "ui_designer.ui.main_window.load_saved_project_model",
            lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
        )

        assert window._poll_project_files() is None
        assert window._external_reload_pending is True
        assert window._external_reload_changed_paths == [os.path.normpath(os.path.abspath(layout_file))]
        assert window.statusBar().currentMessage() == "Project reload failed: boom"

        monkeypatch.setattr("ui_designer.ui.main_window.load_saved_project_model", lambda path: _load_project(path))

        assert window._poll_project_files() is None
        assert window._external_reload_pending is False
        assert window._external_reload_changed_paths == []
        assert window.statusBar().currentMessage() == (
            "Reloaded external changes: main_page.xml | Editing-only mode: preview disabled for test"
        )
        _close_window(window)

    def test_pending_external_reload_preserves_editing_only_reason_after_successful_reload(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.ui.main_window import MainWindow

        class _BusyWorker:
            def isRunning(self):
                return True

        class _PreviewIncompatibleCompiler:
            app_root_arg = "example"

            def __init__(self, app_dir):
                self.app_dir = str(app_dir)

            def can_build(self):
                return True

            def get_build_error(self):
                return ""

            def get_preview_build_error(self):
                return "make: *** No rule to make target 'main.exe'.  Stop."

            def ensure_preview_build_available(self, force=False):
                return False

            def set_screen_size(self, width, height):
                return None

            def is_preview_running(self):
                return False

            def is_exe_ready(self):
                return False

            def stop_exe(self):
                return None

            def cleanup(self):
                return None

            def precompile_async(self, callback):
                raise AssertionError("precompile_async should not be called when preview target probe fails")

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PendingReloadEditingOnlyDemo"
        project = _create_project(project_dir, "PendingReloadEditingOnlyDemo", sdk_root)

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        _open_project_window(window, project, project_dir, sdk_root)

        window._compile_worker = _BusyWorker()
        layout_file = project_dir / ".eguiproject" / "layout" / "main_page.xml"
        layout_file.write_text(layout_file.read_text(encoding="utf-8") + "\n<!-- reload editing only -->\n", encoding="utf-8")

        window._poll_project_files()
        assert window._external_reload_pending is True
        assert window._external_reload_changed_paths == [os.path.normpath(os.path.abspath(layout_file))]

        window._compile_worker = None
        monkeypatch.setattr(
            window,
            "_recreate_compiler",
            lambda: setattr(window, "compiler", _PreviewIncompatibleCompiler(project_dir)),
        )

        assert window._poll_project_files() is None
        assert window._external_reload_pending is False
        assert window._external_reload_changed_paths == []
        message = window.statusBar().currentMessage()
        assert "Reloaded external changes: main_page.xml" in message
        assert "Editing-only mode: make: *** No rule to make target 'main.exe'.  Stop." in message
        _close_window(window)

    def test_pending_external_reload_recomputes_changed_paths_before_retry(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        class _BusyWorker:
            def isRunning(self):
                return True

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PendingReloadRecomputeDemo"
        project = _create_project(
            project_dir,
            "PendingReloadRecomputeDemo",
            sdk_root,
            pages=["main_page", "detail_page"],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._compile_worker = _BusyWorker()

        reload_calls = []

        def _capture_reload(*args, **kwargs):
            reload_calls.append(kwargs)
            window._clear_external_reload_pending()
            return True

        monkeypatch.setattr(window, "_reload_project_from_disk", _capture_reload)

        main_layout = project_dir / ".eguiproject" / "layout" / "main_page.xml"
        detail_layout = project_dir / ".eguiproject" / "layout" / "detail_page.xml"
        main_layout.write_text(main_layout.read_text(encoding="utf-8") + "\n<!-- recompute main -->\n", encoding="utf-8")

        window._poll_project_files()
        assert window._external_reload_changed_paths == [os.path.normpath(os.path.abspath(main_layout))]

        detail_layout.write_text(detail_layout.read_text(encoding="utf-8") + "\n<!-- recompute detail -->\n", encoding="utf-8")
        window._compile_worker = None
        window._poll_project_files()

        assert len(reload_calls) == 1
        assert reload_calls[0]["auto"] is True
        assert reload_calls[0]["changed_paths"] == [
            os.path.normpath(os.path.abspath(detail_layout)),
            os.path.normpath(os.path.abspath(main_layout)),
        ]
        _close_window(window)

    def test_pending_external_reload_clears_when_files_return_to_original_state(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        class _BusyWorker:
            def isRunning(self):
                return True

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PendingReloadResolvedDemo"
        project = _create_project(project_dir, "PendingReloadResolvedDemo", sdk_root)

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._compile_worker = _BusyWorker()

        reload_calls = []
        monkeypatch.setattr(
            window,
            "_reload_project_from_disk",
            lambda *args, **kwargs: reload_calls.append(kwargs) or True,
        )

        layout_file = project_dir / ".eguiproject" / "layout" / "main_page.xml"
        layout_file.write_text(layout_file.read_text(encoding="utf-8") + "\n<!-- transient external -->\n", encoding="utf-8")

        window._poll_project_files()
        assert window._external_reload_pending is True
        assert window._external_reload_changed_paths == [os.path.normpath(os.path.abspath(layout_file))]

        monkeypatch.setattr(window, "_build_project_watch_snapshot", lambda: dict(window._project_watch_snapshot))
        window._compile_worker = None
        window._poll_project_files()

        assert reload_calls == []
        assert window._external_reload_pending is False
        assert window._external_reload_changed_paths == []
        assert window.statusBar().currentMessage() == "External project changes resolved. Reload no longer needed."
        _close_window(window)

    def test_close_project_prompts_when_only_project_state_is_dirty(self, qapp, isolated_config, tmp_path, monkeypatch):
        from PyQt5.QtWidgets import QMessageBox
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "CloseProjectDirtyStateDemo"
        project = _create_project(
            project_dir,
            "CloseProjectDirtyStateDemo",
            sdk_root,
            pages=["main_page", "detail_page"],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._on_startup_changed("detail_page")

        prompts = []
        monkeypatch.setattr(
            "ui_designer.ui.main_window.QMessageBox.question",
            lambda *args, **kwargs: prompts.append(args[1:3]) or QMessageBox.Cancel,
        )

        window._close_project()

        assert window._undo_manager.is_any_dirty() is False
        assert prompts == [
            ("Close Project", "There are unsaved changes: project changes (startup page). Do you want to save before closing?")
        ]
        assert window.project is not None
        _close_window(window)

    def test_reload_project_prompt_describes_project_level_unsaved_reason(self, qapp, isolated_config, tmp_path, monkeypatch):
        from PyQt5.QtWidgets import QMessageBox
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "ReloadProjectDirtyStateDemo"
        project = _create_project(
            project_dir,
            "ReloadProjectDirtyStateDemo",
            sdk_root,
            pages=["main_page", "detail_page"],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._on_startup_changed("detail_page")

        prompts = []
        monkeypatch.setattr(
            "ui_designer.ui.main_window.QMessageBox.question",
            lambda *args, **kwargs: prompts.append(args[1:3]) or QMessageBox.No,
        )

        assert window._reload_project_from_disk() is False
        assert prompts == [
            ("Reload Project", "Reload project files from disk and discard unsaved changes: project changes (startup page)?")
        ]
        _close_window(window)

    def test_close_event_prompt_describes_project_level_unsaved_reason(self, qapp, isolated_config, tmp_path, monkeypatch):
        from PyQt5.QtGui import QCloseEvent
        from PyQt5.QtWidgets import QMessageBox
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "CloseEventDirtyStateDemo"
        project = _create_project(
            project_dir,
            "CloseEventDirtyStateDemo",
            sdk_root,
            pages=["main_page", "detail_page"],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._on_startup_changed("detail_page")

        prompts = []
        monkeypatch.setattr(
            "ui_designer.ui.main_window.QMessageBox.question",
            lambda *args, **kwargs: prompts.append(args[1:3]) or QMessageBox.Cancel,
        )

        event = QCloseEvent()
        window.closeEvent(event)

        assert prompts == [
            ("Unsaved Changes", "There are unsaved changes: project changes (startup page). Do you want to save before closing?")
        ]
        assert event.isAccepted() is False
        assert window._is_closing is False
        _close_window(window)

    def test_save_project_clears_project_change_flag(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.project import Project
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "SaveProjectDirtyStateDemo"
        project = _create_project(
            project_dir,
            "SaveProjectDirtyStateDemo",
            sdk_root,
            pages=["main_page", "detail_page"],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window, "_load_project_app_local_widgets", lambda *args, **kwargs: None)

        _open_project_window(window, project, project_dir, sdk_root)
        window._on_startup_changed("detail_page")

        assert window._undo_manager.is_any_dirty() is False
        assert window._has_unsaved_changes() is True
        assert window._save_project() is True
        assert window._has_unsaved_changes() is False
        assert window.windowTitle().endswith("*") is False

        reloaded = _load_project(project_dir)
        assert reloaded.startup_page == "detail_page"
        _close_window(window)

    def test_project_level_changes_update_page_tab_and_workspace_summaries(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "ProjectDirtySummaryDemo"
        project = _create_project(
            project_dir,
            "ProjectDirtySummaryDemo",
            sdk_root,
            pages=["main_page", "detail_page"],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._switch_page("detail_page")
        window._on_startup_changed("detail_page")

        assert window._undo_manager.is_any_dirty() is False
        assert window.page_tab_bar.accessibleName() == (
            "Page tabs: 2 open pages. Current page: detail_page. Startup page: detail_page. "
            "Project changes pending (startup page)."
        )
        assert window.page_tab_bar.toolTip() == window.page_tab_bar.accessibleName()
        assert window._project_workspace._dirty_chip.text() == "Project"
        assert window._project_workspace._summary_label.text() == (
            "2 pages. Active: detail_page. Project changes pending (startup page)."
        )
        assert window._project_workspace.accessibleName() == (
            "Project workspace: List view. Pages: 2 pages. Active page: detail_page. Startup page: detail_page. "
            "Dirty state: Project changes pending (startup page)."
        )
        _close_window(window)

    def test_project_dirty_reasons_accumulate_in_hints_and_workspace(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "ProjectDirtyReasonsDemo"
        project = _create_project(
            project_dir,
            "ProjectDirtyReasonsDemo",
            sdk_root,
            pages=["main_page", "detail_page"],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._switch_page("detail_page")
        window._on_startup_changed("detail_page")
        window._on_page_mode_changed("activity")
        window._mark_project_dirty("resources")

        assert window._undo_manager.is_any_dirty() is False
        assert window._project_dirty_reason_text() == "startup page, page mode (+1)"
        assert window._save_action.toolTip() == (
            "Save the current project (Ctrl+S). "
            f"Unsaved changes: project changes (startup page, page mode (+1)). Target: {window._project_dir}."
        )
        assert window.page_tab_bar.accessibleName() == (
            "Page tabs: 2 open pages. Current page: detail_page. Startup page: detail_page. "
            "Project changes pending (startup page, page mode (+1))."
        )
        assert window._project_workspace._dirty_chip.text() == "Project"
        assert window._project_workspace._summary_label.text() == (
            "2 pages. Active: detail_page. Project changes pending (startup page, page mode (+1))."
        )
        _close_window(window)

    def test_dirty_page_and_project_reason_are_combined_in_unsaved_change_hints(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "DirtyPageAndProjectReasonDemo"
        project = _create_project(
            project_dir,
            "DirtyPageAndProjectReasonDemo",
            sdk_root,
            pages=["main_page", "detail_page"],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._switch_page("detail_page")
        stack = window._undo_manager.get_stack("detail_page")
        stack.push("state 1", label="initial")
        stack.mark_saved()
        stack.push("state 2", label="changed")
        window._update_window_title()

        window._on_startup_changed("detail_page")

        assert window._save_action.toolTip() == (
            "Save the current project (Ctrl+S). "
            f"Unsaved changes: 1 page + project changes (startup page). Target: {window._project_dir}."
        )
        assert window.page_tab_bar.accessibleName() == (
            "Page tabs: 2 open pages. Current page: detail_page. Startup page: detail_page. "
            "1 dirty page + project changes (startup page)."
        )
        assert window._project_workspace._dirty_chip.text() == "1 dirty + proj"
        assert window._project_workspace._summary_label.text() == (
            "2 pages. Active: detail_page. 1 dirty page + project changes (startup page)."
        )
        _close_window(window)

    def test_save_project_clears_project_dirty_reasons_from_hints_and_workspace(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "ProjectDirtyReasonSaveDemo"
        project = _create_project(
            project_dir,
            "ProjectDirtyReasonSaveDemo",
            sdk_root,
            pages=["main_page", "detail_page"],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window, "_load_project_app_local_widgets", lambda *args, **kwargs: None)

        _open_project_window(window, project, project_dir, sdk_root)
        window._switch_page("detail_page")
        window._on_startup_changed("detail_page")
        window._on_page_mode_changed("activity")

        assert window._project_dirty_reason_text() == "startup page, page mode"
        assert window._has_unsaved_changes() is True

        assert window._save_project() is True
        assert window._has_unsaved_changes() is False
        assert window._project_dirty_reason_text() == ""
        assert window._save_action.toolTip() == (
            "Save the current project (Ctrl+S). "
            f"Unsaved pages: none. Target: {window._project_dir}."
        )
        assert window.page_tab_bar.accessibleName() == (
            "Page tabs: 2 open pages. Current page: detail_page. Startup page: detail_page. No dirty pages."
        )
        assert window._project_workspace._dirty_chip.text() == "Clean"
        assert window._project_workspace._summary_label.text() == "2 pages. Active: detail_page. Clean."
        _close_window(window)

    def test_reload_project_from_disk_preserves_current_page(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.project import Project
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "ReloadDemo"

        project = _create_project(
            project_dir,
            "ReloadDemo",
            sdk_root,
            pages=["main_page", "detail_page"],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._switch_page("detail_page")

        reloaded = _load_project(project_dir)
        reloaded.startup_page = "main_page"
        reloaded.create_new_page("summary_page")
        reloaded.save(str(project_dir))

        assert window._reload_project_from_disk() is True
        assert window._current_page is not None
        assert window._current_page.name == "detail_page"
        assert window.project.get_page_by_name("summary_page") is not None
        _close_window(window)

    def test_reload_project_from_disk_clears_auto_retry_block_when_preview_recovers(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.ui.main_window import MainWindow

        class _ProbeFailCompiler:
            app_root_arg = "example"

            def __init__(self, app_dir):
                self.app_dir = str(app_dir)

            def can_build(self):
                return True

            def get_build_error(self):
                return ""

            def get_preview_build_error(self):
                return "make: *** No rule to make target 'main.exe'.  Stop."

            def ensure_preview_build_available(self, force=False):
                return False

            def set_screen_size(self, width, height):
                return None

            def is_preview_running(self):
                return False

            def is_exe_ready(self):
                return False

            def stop_exe(self):
                return None

            def cleanup(self):
                return None

            def precompile_async(self, callback):
                raise AssertionError("precompile_async should not be called when preview target probe fails")

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "ReloadRetryRecoveryDemo"
        project = _create_project(project_dir, "ReloadRetryRecoveryDemo", sdk_root)
        good_compiler = _AutoRetryCompiler(project_dir, exe_ready=True)

        window = MainWindow(str(sdk_root))
        compile_cycle_calls = []
        recreate_calls = {"count": 0}
        window._compile_timer.stop()
        window._compile_timer.setInterval(0)
        monkeypatch.setattr(
            window,
            "_start_compile_cycle",
            lambda *args, **kwargs: compile_cycle_calls.append(kwargs.get("force_rebuild", False)),
        )

        def _recreate_compiler():
            recreate_calls["count"] += 1
            if recreate_calls["count"] == 1:
                window.compiler = _ProbeFailCompiler(project_dir)
            else:
                window.compiler = good_compiler

        monkeypatch.setattr(window, "_recreate_compiler", _recreate_compiler)

        _open_project_window(window, project, project_dir, sdk_root)

        assert "main.exe" in window._auto_compile_retry_block_reason

        assert window._reload_project_from_disk() is True
        qapp.processEvents()

        assert compile_cycle_calls == [False]
        assert window._auto_compile_retry_block_reason == ""
        _close_window(window)

    def test_page_navigator_is_populated_and_tracks_current_page(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "NavigatorDemo"
        project = _create_project(
            project_dir,
            "NavigatorDemo",
            sdk_root,
            pages=["main_page", "detail_page"],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)

        assert set(window.page_navigator._pages.keys()) == {"main_page", "detail_page"}
        assert window.page_navigator._current_page == "main_page"
        assert window.page_navigator._startup_page == "main_page"
        assert "Startup page: main_page." in window.page_navigator.accessibleName()
        assert "Startup page" in window.page_navigator._thumbnails["main_page"].accessibleName()
        assert "Startup page: main_page." in window.page_tab_bar.accessibleName()
        assert "Startup page: main_page." in window._project_workspace.accessibleName()
        assert window._page_tools_scroll.accessibleName() == (
            "Page inspector: Fields and Timers sections. Scroll focus: Fields. Current page: main_page."
        )
        assert _left_panel_tab_tooltip(window, "project") == (
            "Currently showing Project panel. View: List view. Active page: main_page. Startup page: main_page."
        )
        assert _left_panel_tab_tooltip(window, "assets") == "Open Assets panel. Current page: main_page."
        assert window._workspace_context_label.text() == "NavigatorDemo / main_page"
        assert window._workspace_context_label.toolTip() == (
            "Current workspace context: NavigatorDemo. Current page: main_page. Project contains 2 pages."
        )
        editor_layout = window._editor_container.layout()
        editor_margins = editor_layout.contentsMargins()
        toolbar_host_margins = window._toolbar_host_layout.contentsMargins()
        left_shell_layout = window._left_shell.layout()
        bottom_header_layout = window._bottom_header.layout()
        bottom_header_margins = bottom_header_layout.contentsMargins()
        assert (editor_margins.left(), editor_margins.top(), editor_margins.right(), editor_margins.bottom()) == (2, 2, 2, 2)
        assert editor_layout.spacing() == 2
        assert (toolbar_host_margins.left(), toolbar_host_margins.top(), toolbar_host_margins.right(), toolbar_host_margins.bottom()) == (1, 1, 1, 1)
        assert window._toolbar_command_row_layout.spacing() == 1
        assert window.project_dock.minimumWidth() == 256
        assert window._left_panel_stack.minimumWidth() == 256
        assert window._left_shell.minimumWidth() == 256
        assert left_shell_layout.spacing() == 2
        assert (left_shell_layout.contentsMargins().left(), left_shell_layout.contentsMargins().top(), left_shell_layout.contentsMargins().right(), left_shell_layout.contentsMargins().bottom()) == (0, 0, 0, 0)
        assert window._left_panel_stack.count() == 4
        assert window._left_panel_stack.tabText(_left_panel_tab_index(window, "project")) == "Pages"
        assert window._left_panel_stack.tabText(_left_panel_tab_index(window, "structure")) == "Tree"
        assert window._left_panel_stack.tabText(_left_panel_tab_index(window, "widgets")) == "Add"
        assert window._left_panel_stack.tabText(_left_panel_tab_index(window, "assets")) == "Assets"
        assert window._center_shell.layout().spacing() == 2
        assert window._page_inspector_body.layout().spacing() == 2
        assert (bottom_header_margins.left(), bottom_header_margins.top(), bottom_header_margins.right(), bottom_header_margins.bottom()) == (0, 0, 0, 0)
        assert bottom_header_layout.spacing() == 1
        assert window._bottom_shell.layout().spacing() == 2
        assert window._workspace_nav_frame.accessibleName() == "Workspace panel tabs. Current panel: Project."
        assert window._left_panel_stack.accessibleName() == (
            "Workspace panels: Project visible. View: List view. Active page: main_page. Startup page: main_page."
        )
        assert window._left_shell.accessibleName() == (
            "Workspace left shell: Project panel visible. View: List view. Active page: main_page. Startup page: main_page."
        )
        assert window._editor_container.accessibleName() == (
            "Editor workspace. Left panel: Project. Current page: main_page. Mode: Design. Bottom tools hidden."
        )
        assert window._center_shell.accessibleName() == "Workspace center shell. Current page: main_page. Mode: Design."
        assert window._top_splitter.accessibleName() == (
            "Workspace columns. Left panel: Project. Editor mode: Design. Inspector section: Properties. Current page: main_page."
        )
        assert window._workspace_splitter.accessibleName() == (
            "Workspace rows. Editor area visible. Bottom tools hidden. Current section: Diagnostics. Current page: main_page."
        )
        assert window._bottom_header.accessibleName() == "Bottom tools header. Current section: Diagnostics. Panel hidden."
        assert window._bottom_shell.accessibleName() == (
            "Workspace bottom shell. Current section: Diagnostics. Panel hidden. Current page: main_page."
        )

        window._switch_page("detail_page")

        assert window.page_navigator._current_page == "detail_page"
        assert window.page_navigator._startup_page == "main_page"
        assert window._page_tools_scroll.accessibleName() == (
            "Page inspector: Fields and Timers sections. Scroll focus: Fields. Current page: detail_page."
        )
        assert _left_panel_tab_tooltip(window, "project") == (
            "Currently showing Project panel. View: List view. Active page: detail_page. Startup page: main_page."
        )
        assert _left_panel_tab_tooltip(window, "assets") == "Open Assets panel. Current page: detail_page."
        assert window._workspace_context_label.text() == "NavigatorDemo / detail_page"
        assert window._workspace_context_label.toolTip() == (
            "Current workspace context: NavigatorDemo. Current page: detail_page. Project contains 2 pages."
        )
        assert window._left_panel_stack.toolTip() == (
            "Workspace panels: Project visible. View: List view. Active page: detail_page. Startup page: main_page."
        )
        assert window._left_shell.toolTip() == (
            "Workspace left shell: Project panel visible. View: List view. Active page: detail_page. Startup page: main_page."
        )
        assert window._editor_container.toolTip() == (
            "Editor workspace. Left panel: Project. Current page: detail_page. Mode: Design. Bottom tools hidden."
        )
        assert window._center_shell.toolTip() == "Workspace center shell. Current page: detail_page. Mode: Design."
        assert window._top_splitter.toolTip() == (
            "Workspace columns. Left panel: Project. Editor mode: Design. Inspector section: Properties. Current page: detail_page."
        )
        assert window._workspace_splitter.toolTip() == (
            "Workspace rows. Editor area visible. Bottom tools hidden. Current section: Diagnostics. Current page: detail_page."
        )
        assert window._bottom_shell.toolTip() == (
            "Workspace bottom shell. Current section: Diagnostics. Panel hidden. Current page: detail_page."
        )

        window._on_startup_changed("detail_page")

        assert window.project.startup_page == "detail_page"
        assert window.page_navigator._startup_page == "detail_page"
        assert "Startup page: detail_page." in window.page_navigator.accessibleName()
        assert "Startup page" in window.page_navigator._thumbnails["detail_page"].accessibleName()
        assert "Startup page" not in window.page_navigator._thumbnails["main_page"].accessibleName()
        assert "Startup page: detail_page." in window.page_tab_bar.accessibleName()
        assert "Startup page: detail_page." in window._project_workspace.accessibleName()
        assert _left_panel_tab_tooltip(window, "project") == (
            "Currently showing Project panel. View: List view. Active page: detail_page. Startup page: detail_page."
        )
        assert window._workspace_context_label.text() == "NavigatorDemo / detail_page"
        assert window._left_panel_stack.accessibleName() == (
            "Workspace panels: Project visible. View: List view. Active page: detail_page. Startup page: detail_page."
        )
        assert window._left_shell.accessibleName() == (
            "Workspace left shell: Project panel visible. View: List view. Active page: detail_page. Startup page: detail_page."
        )
        assert window._editor_container.accessibleName() == (
            "Editor workspace. Left panel: Project. Current page: detail_page. Mode: Design. Bottom tools hidden."
        )
        assert window._center_shell.accessibleName() == "Workspace center shell. Current page: detail_page. Mode: Design."
        _close_window(window)

    def test_workspace_status_reports_multi_display_primary_scope(self, qapp, isolated_config, tmp_path):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "MultiDisplayWorkspaceDemo"
        project = _create_project(
            project_dir,
            "MultiDisplayWorkspaceDemo",
            sdk_root,
            pages=["main_page", "detail_page"],
        )
        project.displays = [
            {"width": 320, "height": 240},
            {"width": 128, "height": 64},
        ]

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        build_action = next(action for action in window.menuBar().actions() if action.text() == "Build")
        project_resources_dir = window._get_eguiproject_resource_dir()

        assert window._workspace_context_label.toolTip() == (
            "Current workspace context: MultiDisplayWorkspaceDemo. Current page: main_page. Project contains 2 pages. "
            "Multi-display project: editing and preview target the primary display."
        )
        assert window._workspace_context_card.accessibleName() == (
            "Workspace context card: MultiDisplayWorkspaceDemo / main_page. Display target: Display 0 (primary only)."
        )
        assert window._workspace_nav_frame.accessibleName() == (
            "Workspace panel tabs. Current panel: Project. Display target: Display 0 (primary only)."
        )
        assert window._insert_widget_button.toolTip() == (
            "Open the Components panel and insert a component into root_group. Display target: Display 0 (primary only)."
        )
        assert window._insert_widget_button.accessibleName() == (
            "Insert component target: root_group. Display target: Display 0 (primary only)."
        )
        assert window._compile_action.toolTip() == (
            "Compile the current project and run the preview (F5). "
            "Project: open. SDK: valid. Preview: editing only. Display target: Display 0 (primary only). "
            "Unavailable: preview disabled for test."
        )
        assert window._rebuild_action.toolTip() == (
            "Clean and rebuild the whole EGUI project, then rerun the preview (Ctrl+F5). "
            "Project: open. SDK: valid. Preview: editing only. Display target: Display 0 (primary only). "
            "Unavailable: preview disabled for test."
        )
        assert window._clean_all_action.toolTip() == (
            "Destructive recovery: delete project-side generated/code files outside the preserved "
            "Designer source set and reconstruct the project (Ctrl+Shift+F5). "
            "Project: open. Saved project: saved. SDK: valid. Preview: editing only. Display target: Display 0 (primary only). "
            "Preview rerun will be skipped: preview disabled for test."
        )
        assert window.auto_compile_action.toolTip() == (
            "Automatically compile and rerun the preview after changes. "
            "Project: open. SDK: valid. Preview: editing only. Display target: Display 0 (primary only). "
            "Unavailable: preview disabled for test."
        )
        assert window._stop_action.toolTip() == (
            "Stop the running preview executable. Project: open. Preview: stopped. Display target: Display 0 (primary only). "
            "Unavailable: preview is not running."
        )
        assert build_action.toolTip() == (
            "Compile previews, generate resources, or reconstruct a project from Designer sources. "
            "Project: open. SDK: valid. Compile: unavailable. Rebuild: unavailable. Reconstruct: available (preview rerun skipped). "
            "Auto compile: on. Preview: editing only. Display target: Display 0 (primary only). "
            f"Source resources: available. Resource directory: {project_resources_dir}."
        )
        assert _left_panel_tab_tooltip(window, "project") == (
            "Currently showing Project panel. View: List view. Active page: main_page. Startup page: main_page. "
            "Display target: Display 0 (primary only)."
        )
        assert window.page_tab_bar.accessibleName() == (
            "Page tabs: 1 open page. Current page: main_page. Startup page: main_page. No dirty pages. "
            "Display target: Display 0 (primary only)."
        )
        assert window.page_tab_bar.toolTip() == window.page_tab_bar.accessibleName()
        assert window.page_navigator.accessibleName() == (
            "Page navigator: 2 pages. Current page: main_page. Startup page: main_page. No dirty pages. "
            "Display target: Display 0 (primary only)."
        )
        assert window.page_navigator._header_meta_label.accessibleName() == (
            "Current page: main_page. Startup page: main_page. Display target: Display 0 (primary only). "
            "Use the rail to scan visual state and jump between pages."
        )
        assert window._toolbar_meta_label.text() == (
            "Design mode. Project panel. Current page: main_page. "
            "Display target: Display 0 (primary only). Use commands to insert, save, build, and check runtime."
        )
        assert window._toolbar_meta_label.accessibleName() == window._toolbar_meta_label.text()
        assert window._workspace_status_label.text() == (
            "Page: main_page | Preview: Editing Only | Displays: 2 total, primary only | Selection: none "
            "| Warnings: 0 | Ready"
        )
        assert window._left_panel_stack.accessibleName() == (
            "Workspace panels: Project visible. View: List view. Active page: main_page. Startup page: main_page. "
            "Display target: Display 0 (primary only)."
        )
        assert window._left_shell.accessibleName() == (
            "Workspace left shell: Project panel visible. View: List view. Active page: main_page. Startup page: main_page. "
            "Display target: Display 0 (primary only)."
        )
        assert window._inspector_tabs.accessibleName() == (
            "Inspector tabs: Properties selected. 3 tabs. Current page: main_page. Selection: none. "
            "Display target: Display 0 (primary only)."
        )
        assert window._page_tools_scroll.accessibleName() == (
            "Page inspector: Fields and Timers sections. Scroll focus: Fields. Current page: main_page. "
            "Display target: Display 0 (primary only)."
        )
        assert window._editor_container.accessibleName() == (
            "Editor workspace. Left panel: Project. Current page: main_page. Mode: Design. Bottom tools hidden. "
            "Display target: Display 0 (primary only)."
        )
        assert window._center_shell.accessibleName() == (
            "Workspace center shell. Current page: main_page. Mode: Design. "
            "Display target: Display 0 (primary only)."
        )
        assert window._top_splitter.accessibleName() == (
            "Workspace columns. Left panel: Project. Editor mode: Design. Inspector section: Properties. Current page: main_page. "
            "Display target: Display 0 (primary only)."
        )
        assert window._workspace_splitter.accessibleName() == (
            "Workspace rows. Editor area visible. Bottom tools hidden. Current section: Diagnostics. Current page: main_page. "
            "Display target: Display 0 (primary only)."
        )
        assert window._bottom_tabs.accessibleName() == (
            "Bottom tools tabs: Diagnostics selected. 3 tabs. Current page: main_page. Panel hidden. "
            "Display target: Display 0 (primary only)."
        )
        assert window._bottom_header.accessibleName() == (
            "Bottom tools header. Current section: Diagnostics. Panel hidden. Display target: Display 0 (primary only)."
        )
        assert window._bottom_toggle_button.toolTip() == (
            "Show the bottom tools panel. Display target: Display 0 (primary only)."
        )
        assert window._bottom_toggle_button.accessibleName() == (
            "Bottom tools toggle: hidden. Activate to show. Display target: Display 0 (primary only)."
        )
        assert window._bottom_shell.accessibleName() == (
            "Workspace bottom shell. Current section: Diagnostics. Panel hidden. Current page: main_page. "
            "Display target: Display 0 (primary only)."
        )
        assert window._project_workspace._metrics_frame.isHidden() is False
        assert window._project_workspace._view_chip.text() == "List"
        assert window._project_workspace._view_chip.accessibleName() == (
            "Workspace view: List view. Multi-display project: editing and preview use the primary display."
        )
        assert window._project_workspace._page_count_chip.isHidden() is False
        assert window._project_workspace._page_count_chip.text() == "2 pages"
        assert window._project_workspace._dirty_chip.isHidden() is False
        assert window._project_workspace._dirty_chip.text() == "Clean"
        assert window._project_workspace._display_target_chip.isHidden() is False
        assert window._project_workspace._display_target_chip.text() == "Primary"
        assert window._project_workspace._display_target_chip.accessibleName() == (
            "Display target: Display 0. Editing and preview use the primary display."
        )
        assert window._project_workspace._meta_label.text() == (
            "Startup: main_page | 2 displays | Editing/preview: primary display only"
        )
        assert window._project_workspace.accessibleName() == (
            "Project workspace: List view. Pages: 2 pages. Active page: main_page. Startup page: main_page. "
            "Dirty state: No dirty pages. Display scope: 2 displays; editing and preview target the primary display."
        )
        _close_window(window)

    def test_page_navigator_copy_and_template_add_keep_pages_in_sync(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "NavigatorActionsDemo"
        project = _create_project(project_dir, "NavigatorActionsDemo", sdk_root)

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)

        window._duplicate_page_from_navigator("main_page")
        assert window.project.get_page_by_name("main_page_copy") is not None
        assert "main_page_copy" in window.page_navigator._pages
        assert window._current_page.name == "main_page_copy"

        window._on_page_add_from_template("detail", "main_page")
        _template_page, template_root = require_project_page_root(window.project, "detail_page")
        assert "detail_page" in window.page_navigator._pages
        assert window._current_page.name == "detail_page"
        assert [child.name for child in template_root.children] == ["title", "hero_image", "description"]
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_dirty_page_indicators_sync_across_tabs_navigator_and_project_tree(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow
        from ui_designer.ui.theme import app_theme_tokens

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "DirtyPagesDemo"
        project = _create_project(
            project_dir,
            "DirtyPagesDemo",
            sdk_root,
            pages=["main_page", "detail_page"],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        tokens = app_theme_tokens()

        assert window.page_tab_bar.accessibleName() == (
            "Page tabs: 1 open page. Current page: main_page. Startup page: main_page. No dirty pages."
        )
        assert window.page_tab_bar.height() == int(tokens["h_tab_min"]) + int(tokens["space_md"])
        assert window.page_tab_bar.tabMaximumWidth() == 188
        assert window.page_tab_bar.tabRect(0).height() <= window.page_tab_bar.height()
        assert window.page_tab_bar.toolTip() == window.page_tab_bar.accessibleName()

        window._undo_manager.get_stack("main_page").push("<Page dirty='main' />")
        window._undo_manager.get_stack("detail_page").push("<Page dirty='detail' />")
        window._update_window_title()

        assert window.page_tab_bar.tabText(0) == "main_page*"
        assert window.page_navigator._thumbnails["main_page"]._name_label.text() == "main_page*"
        assert window.page_navigator._thumbnails["detail_page"]._name_label.text() == "detail_page*"

        texts_by_page = {}
        for i in range(window.project_dock._page_tree.topLevelItemCount()):
            item = window.project_dock._page_tree.topLevelItem(i)
            texts_by_page[item.data(0, Qt.UserRole)] = item.text(0)
        assert texts_by_page["main_page"] == "main_page (startup)*"
        assert texts_by_page["detail_page"].endswith("detail_page*")
        assert window.page_tab_bar.accessibleName() == (
            "Page tabs: 1 open page. Current page: main_page. Startup page: main_page. 2 dirty pages."
        )

        window._switch_page("detail_page")
        assert window._current_page.name == "detail_page"
        assert any(window.page_tab_bar.tabText(i) == "detail_page*" for i in range(window.page_tab_bar.count()))
        assert window.page_tab_bar.accessibleName() == (
            "Page tabs: 2 open pages. Current page: detail_page. Startup page: main_page. 2 dirty pages."
        )

        window._undo_manager.mark_all_saved()
        window._update_window_title()

        assert all(not window.page_tab_bar.tabText(i).endswith("*") for i in range(window.page_tab_bar.count()))
        assert window.page_navigator._thumbnails["main_page"]._name_label.text() == "main_page"
        assert window.page_navigator._thumbnails["detail_page"]._name_label.text() == "detail_page"
        assert window.page_tab_bar.accessibleName() == (
            "Page tabs: 2 open pages. Current page: detail_page. Startup page: main_page. No dirty pages."
        )
        _close_window(window)

    def test_page_tab_bar_metadata_skips_no_op_refreshes(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PageTabMetadataNoOpDemo"
        project = _create_project(project_dir, "PageTabMetadataNoOpDemo", sdk_root)

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        if hasattr(window, "_page_tab_bar_metadata_snapshot"):
            delattr(window, "_page_tab_bar_metadata_snapshot")

        tooltip_calls = 0
        original_set_tooltip = window.page_tab_bar.setToolTip

        def counted_set_tooltip(text):
            nonlocal tooltip_calls
            tooltip_calls += 1
            return original_set_tooltip(text)

        monkeypatch.setattr(window.page_tab_bar, "setToolTip", counted_set_tooltip)

        window._update_page_tab_bar_metadata()
        assert tooltip_calls == 1

        tooltip_calls = 0
        window._update_page_tab_bar_metadata()
        assert tooltip_calls == 0

        window._undo_manager.get_stack("main_page").push("<Page dirty='main' />")
        window._update_window_title()
        assert tooltip_calls == 1
        _close_window(window)

    def test_page_tab_context_menu_actions_expose_status_hints(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PageTabContextMenuDemo"
        project = _create_project(
            project_dir,
            "PageTabContextMenuDemo",
            sdk_root,
            pages=["main_page", "detail_page"],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        _open_project_window(window, project, project_dir, sdk_root)

        menu, actions = window._build_page_tab_context_menu(0)
        assert actions["close_tab"].toolTip() == (
            "Close page tab. Page: main_page. Current page. Startup page. No unsaved changes."
        )
        assert actions["close_tab"].statusTip() == actions["close_tab"].toolTip()
        assert actions["close_others"].isEnabled() is False
        assert actions["close_others"].toolTip() == (
            "Close all other open page tabs and keep main_page. "
            "Page: main_page. Current page. Startup page. No unsaved changes. "
            "Unavailable: only 1 page tab is open."
        )
        assert actions["close_others"].statusTip() == actions["close_others"].toolTip()
        assert actions["close_all"].toolTip() == (
            "Close all open page tabs from main_page. Page: main_page. Current page. Startup page. No unsaved changes."
        )
        assert actions["close_all"].statusTip() == actions["close_all"].toolTip()
        menu.deleteLater()

        window._switch_page("detail_page")
        window._undo_manager.get_stack("main_page").push("<Page dirty='main' />")
        window._update_window_title()
        menu, actions = window._build_page_tab_context_menu(0)
        assert actions["close_tab"].toolTip() == (
            "Close page tab. Page: main_page. Startup page. Unsaved changes."
        )
        assert actions["close_tab"].statusTip() == actions["close_tab"].toolTip()
        assert actions["close_others"].isEnabled() is True
        assert actions["close_others"].toolTip() == (
            "Close all other open page tabs and keep main_page. "
            "Page: main_page. Startup page. Unsaved changes."
        )
        assert actions["close_others"].statusTip() == actions["close_others"].toolTip()
        assert actions["close_all"].toolTip() == (
            "Close all open page tabs from main_page. Page: main_page. Startup page. Unsaved changes."
        )
        assert actions["close_all"].statusTip() == actions["close_all"].toolTip()
        menu.deleteLater()
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_context_menus_include_primary_display_scope_for_multi_display_projects(self, qapp, isolated_config, tmp_path):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "MultiDisplayContextMenusDemo"
        widget = WidgetModel("label", name="title", x=12, y=16, width=100, height=24)
        project = _create_project_only_with_widgets(
            project_dir,
            "MultiDisplayContextMenusDemo",
            sdk_root,
            widgets=[widget],
        )
        project.displays = [
            {"width": 320, "height": 240},
            {"width": 128, "height": 64},
        ]

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        _open_project_window(window, project, project_dir, sdk_root)

        menu, actions = window._build_page_tab_context_menu(0)
        assert actions["close_tab"].toolTip() == (
            "Close page tab. Page: main_page. Current page. Startup page. No unsaved changes. "
            "Display target: Display 0 (primary only)."
        )
        assert actions["close_others"].toolTip() == (
            "Close all other open page tabs and keep main_page. "
            "Page: main_page. Current page. Startup page. No unsaved changes. "
            "Display target: Display 0 (primary only). Unavailable: only 1 page tab is open."
        )
        assert actions["close_all"].toolTip() == (
            "Close all open page tabs from main_page. Page: main_page. Current page. Startup page. No unsaved changes. "
            "Display target: Display 0 (primary only)."
        )
        for action in actions.values():
            assert action.statusTip() == action.toolTip()
        menu.deleteLater()

        window._selection_state.set_widgets([], primary=None)
        window._selected_widget = None
        window._update_edit_actions()
        menu = window._build_preview_context_menu(None)
        actions = {action.text(): action for action in menu.actions() if action.text()}
        assert actions["Arrange"].toolTip() == (
            "Arrange unavailable: select at least 1 widget. Display target: Display 0 (primary only)."
        )
        assert actions["Arrange"].statusTip() == actions["Arrange"].toolTip()
        assert actions["Structure"].toolTip() == (
            "Structure unavailable: select at least 1 widget. Display target: Display 0 (primary only)."
        )
        assert actions["Structure"].statusTip() == actions["Structure"].toolTip()
        menu.deleteLater()

        _close_window(window)

    def test_copy_and_paste_selection_creates_unique_widget_names(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "ClipboardDemo"
        label = WidgetModel("label", name="title", x=10, y=10, width=80, height=20)
        project, root = _create_project_and_root_with_widgets(
            project_dir,
            "ClipboardDemo",
            sdk_root,
            widgets=[label],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)

        def fake_set_selection(widgets=None, primary=None, sync_tree=True, sync_preview=True):
            window._selection_state.set_widgets(widgets or [], primary=primary)
            window._selected_widget = window._selection_state.primary

        monkeypatch.setattr(window, "_set_selection", fake_set_selection)
        window._selected_widget = label

        window._copy_selection()
        window._paste_selection()

        label_names = [child.name for child in root.children if child.widget_type == "label"]
        assert label_names == ["title", "title_2"]
        assert window._selection_state.primary.name == "title_2"
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_diagnostics_panel_lists_page_issues_and_selection_notes(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "DiagnosticsDemo"
        invalid = WidgetModel("label", name="bad-name", x=8, y=8, width=60, height=20)
        duplicate_a = WidgetModel("label", name="dup_name", x=20, y=40, width=60, height=20)
        duplicate_b = WidgetModel("label", name="dup_name", x=230, y=40, width=30, height=20)
        layout_parent = WidgetModel("linearlayout", name="layout_parent", x=0, y=120, width=240, height=80)
        managed = WidgetModel("label", name="managed_widget", x=12, y=8, width=80, height=20)
        managed.designer_locked = True
        managed.designer_hidden = True
        _add_widget_children(layout_parent, [managed])
        missing = WidgetModel("image", name="missing_image", x=16, y=220, width=48, height=48)
        missing.properties["image_file"] = "missing.png"
        project = _create_project_only_with_widgets(
            project_dir,
            "DiagnosticsDemo",
            sdk_root,
            widgets=[invalid, duplicate_a, duplicate_b, layout_parent, missing],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._selection_state.set_widgets([managed], primary=managed)
        window._selected_widget = managed
        window._update_diagnostics_panel()

        summary = window.diagnostics_panel._summary_label.text()
        items = [window.diagnostics_panel._list.item(i).text() for i in range(window.diagnostics_panel._list.count())]

        assert window.diagnostics_dock.objectName() == "diagnostics_dock"
        assert summary == "Diagnostics: 3 error(s), 2 warning(s), 3 info item(s)"
        assert any("bad-name" in item and "valid C identifier" in item for item in items)
        assert sum("dup_name" in item and "duplicated" in item for item in items) == 2
        assert any("dup_name" in item and "geometry issues" in item for item in items)
        assert any("missing_image" in item and "missing from the resource catalog" in item for item in items)
        assert any("canvas drag and resize are disabled" in item for item in items)
        assert any("canvas hit testing" in item for item in items)
        assert any("layout-managed by linearlayout" in item for item in items)

        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_diagnostics_panel_lists_project_callback_duplicates(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "ProjectCallbackDiagnosticsDemo"
        main_button = WidgetModel("button", name="confirm_button", x=8, y=8, width=80, height=28)
        detail_button = WidgetModel("button", name="confirm_button_2", x=8, y=8, width=80, height=28)
        main_button.on_click = "on_confirm"
        detail_button.on_click = "on_confirm"
        project = _create_project_only_with_page_widgets(
            project_dir,
            "ProjectCallbackDiagnosticsDemo",
            sdk_root,
            page_widgets={
                "main_page": [main_button],
                "detail_page": [detail_button],
            },
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._update_diagnostics_panel()

        summary = window.diagnostics_panel._summary_label.text()
        items = [window.diagnostics_panel._list.item(i).text() for i in range(window.diagnostics_panel._list.count())]

        assert summary == "Diagnostics: 1 error(s), 0 warning(s), 0 info item(s)"
        assert any("project/on_confirm" in item and "duplicate global symbols" in item for item in items)

        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_project_callback_diagnostic_activation_switches_to_target_widget(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "ProjectCallbackDiagnosticFocusDemo"
        main_button = WidgetModel("button", name="confirm_button", x=8, y=8, width=80, height=28)
        detail_button = WidgetModel("button", name="confirm_button_2", x=8, y=8, width=80, height=28)
        main_button.on_click = "on_confirm"
        detail_button.on_click = "on_confirm"
        project = _create_project_only_with_page_widgets(
            project_dir,
            "ProjectCallbackDiagnosticFocusDemo",
            sdk_root,
            page_widgets={
                "main_page": [main_button],
                "detail_page": [detail_button],
            },
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        def fake_set_selection(widgets=None, primary=None, sync_tree=True, sync_preview=True):
            window._selection_state.set_widgets(widgets or [], primary=primary)
            window._selected_widget = window._selection_state.primary

        monkeypatch.setattr(window, "_set_selection", fake_set_selection)

        _open_project_window(window, project, project_dir, sdk_root)
        window._update_diagnostics_panel()

        assert window._current_page.name == "main_page"

        item = window.diagnostics_panel._list.item(0)
        window.diagnostics_panel._on_item_activated(item)

        assert window._current_page.name == "detail_page"
        assert window._selection_state.primary is detail_button
        assert window._selection_state.widgets == [detail_button]
        assert window.statusBar().currentMessage() == "Opened diagnostic target: detail_page/confirm_button_2."

        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_diagnostics_panel_filters_visible_entries_by_severity(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "DiagnosticsFilterDemo"
        invalid = WidgetModel("label", name="bad-name", x=8, y=8, width=60, height=20)
        duplicate_a = WidgetModel("label", name="dup_name", x=20, y=40, width=60, height=20)
        duplicate_b = WidgetModel("label", name="dup_name", x=230, y=40, width=30, height=20)
        layout_parent = WidgetModel("linearlayout", name="layout_parent", x=0, y=120, width=240, height=80)
        managed = WidgetModel("label", name="managed_widget", x=12, y=8, width=80, height=20)
        managed.designer_locked = True
        managed.designer_hidden = True
        _add_widget_children(layout_parent, [managed])
        missing = WidgetModel("image", name="missing_image", x=16, y=220, width=48, height=48)
        missing.properties["image_file"] = "missing.png"
        project = _create_project_only_with_widgets(
            project_dir,
            "DiagnosticsFilterDemo",
            sdk_root,
            widgets=[invalid, duplicate_a, duplicate_b, layout_parent, missing],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._selection_state.set_widgets([managed], primary=managed)
        window._selected_widget = managed
        window._update_diagnostics_panel()

        filter_combo = window.diagnostics_panel._severity_filter_combo
        filter_combo.setCurrentIndex(filter_combo.findData("warning"))
        warning_items = [window.diagnostics_panel._list.item(i).text() for i in range(window.diagnostics_panel._list.count())]

        assert window.diagnostics_panel._summary_label.text() == "Diagnostics: 3 error(s), 2 warning(s), 3 info item(s)"
        assert len(warning_items) == 2
        assert all(item.startswith("[Warning]") for item in warning_items)
        assert window.diagnostics_panel._copy_button.isEnabled() is True
        assert window.diagnostics_panel._copy_json_button.isEnabled() is True

        filter_combo.setCurrentIndex(filter_combo.findData("info"))
        info_items = [window.diagnostics_panel._list.item(i).text() for i in range(window.diagnostics_panel._list.count())]

        assert len(info_items) == 3
        assert all(item.startswith("[Info]") for item in info_items)

        filter_combo.setCurrentIndex(filter_combo.findData("warning"))
        layout_warning_items = [window.diagnostics_panel._list.item(i).text() for i in range(window.diagnostics_panel._list.count())]
        assert any("geometry issues" in item for item in layout_warning_items)
        assert any("missing from the resource catalog" in item for item in layout_warning_items)

        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_diagnostics_panel_reset_view_clears_severity_filter(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "DiagnosticsResetViewDemo"
        invalid = WidgetModel("label", name="bad-name", x=8, y=8, width=60, height=20)
        duplicate_a = WidgetModel("label", name="dup_name", x=20, y=40, width=60, height=20)
        duplicate_b = WidgetModel("label", name="dup_name", x=230, y=40, width=30, height=20)
        layout_parent = WidgetModel("linearlayout", name="layout_parent", x=0, y=120, width=240, height=80)
        managed = WidgetModel("label", name="managed_widget", x=12, y=8, width=80, height=20)
        managed.designer_locked = True
        managed.designer_hidden = True
        _add_widget_children(layout_parent, [managed])
        missing = WidgetModel("image", name="missing_image", x=16, y=220, width=48, height=48)
        missing.properties["image_file"] = "missing.png"
        project = _create_project_only_with_widgets(
            project_dir,
            "DiagnosticsResetViewDemo",
            sdk_root,
            widgets=[invalid, duplicate_a, duplicate_b, layout_parent, missing],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._selection_state.set_widgets([managed], primary=managed)
        window._selected_widget = managed
        window._update_diagnostics_panel()

        filter_combo = window.diagnostics_panel._severity_filter_combo
        reset_button = window.diagnostics_panel._reset_view_button

        assert reset_button.isEnabled() is False

        filter_combo.setCurrentIndex(filter_combo.findData("warning"))

        assert reset_button.isEnabled() is True
        assert window.diagnostics_panel._list.count() == 2

        reset_button.click()

        assert filter_combo.currentData() == ""
        assert reset_button.isEnabled() is False
        assert window.diagnostics_panel._list.count() == 8

        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_diagnostics_panel_restores_saved_severity_filter(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "DiagnosticsRestoreFilterDemo"
        invalid = WidgetModel("label", name="bad-name", x=8, y=8, width=60, height=20)
        missing = WidgetModel("image", name="missing_image", x=16, y=48, width=48, height=48)
        missing.properties["image_file"] = "missing.png"
        project = _create_project_only_with_widgets(
            project_dir,
            "DiagnosticsRestoreFilterDemo",
            sdk_root,
            widgets=[invalid, missing],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._update_diagnostics_panel()
        filter_combo = window.diagnostics_panel._severity_filter_combo
        filter_combo.setCurrentIndex(filter_combo.findData("warning"))

        _close_window(window)

        assert isolated_config.diagnostics_view == {"severity_filter": "warning"}

        restored = MainWindow(str(sdk_root))
        _disable_window_compile(restored, _DisabledCompiler)

        _open_project_window(restored, project, project_dir, sdk_root)
        restored._update_diagnostics_panel()

        assert restored.diagnostics_panel._severity_filter_combo.currentData() == "warning"
        assert restored.diagnostics_panel._list.count() == 1
        assert "missing_image" in restored.diagnostics_panel._list.item(0).text()

        restored._undo_manager.mark_all_saved()
        _close_window(restored)

    def test_diagnostics_panel_open_first_error_activates_first_error(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "DiagnosticsOpenFirstErrorDemo"
        invalid = WidgetModel("label", name="bad-name", x=8, y=8, width=60, height=20)
        missing = WidgetModel("image", name="missing_image", x=16, y=48, width=48, height=48)
        missing.properties["image_file"] = "missing.png"
        project = _create_project_only_with_widgets(
            project_dir,
            "DiagnosticsOpenFirstErrorDemo",
            sdk_root,
            widgets=[invalid, missing],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        def fake_set_selection(widgets=None, primary=None, sync_tree=True, sync_preview=True):
            window._selection_state.set_widgets(widgets or [], primary=primary)
            window._selected_widget = window._selection_state.primary

        monkeypatch.setattr(window, "_set_selection", fake_set_selection)

        _open_project_window(window, project, project_dir, sdk_root)
        window._update_diagnostics_panel()
        filter_combo = window.diagnostics_panel._severity_filter_combo
        filter_combo.setCurrentIndex(filter_combo.findData("warning"))

        assert window.diagnostics_panel._open_first_error_button.isEnabled() is True
        assert window.diagnostics_panel._list.count() == 1

        window.diagnostics_panel._open_first_error_button.click()

        assert filter_combo.currentData() == "error"
        assert window.diagnostics_panel._list.count() == 1
        assert window._selection_state.primary is invalid
        assert window._selection_state.widgets == [invalid]

        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_diagnostics_panel_open_first_error_is_disabled_without_errors(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "DiagnosticsNoErrorOpenDemo"
        missing = WidgetModel("image", name="missing_image", x=16, y=48, width=48, height=48)
        missing.properties["image_file"] = "missing.png"
        project = _create_project_only_with_widgets(
            project_dir,
            "DiagnosticsNoErrorOpenDemo",
            sdk_root,
            widgets=[missing],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._update_diagnostics_panel()

        assert window.diagnostics_panel._open_first_error_button.isEnabled() is False

        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_diagnostics_panel_open_first_warning_activates_first_warning(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "DiagnosticsOpenFirstWarningDemo"
        invalid = WidgetModel("label", name="bad-name", x=8, y=8, width=60, height=20)
        missing = WidgetModel("image", name="missing_image", x=16, y=48, width=48, height=48)
        missing.properties["image_file"] = "missing.png"
        project = _create_project_only_with_widgets(
            project_dir,
            "DiagnosticsOpenFirstWarningDemo",
            sdk_root,
            widgets=[invalid, missing],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        def fake_set_selection(widgets=None, primary=None, sync_tree=True, sync_preview=True):
            window._selection_state.set_widgets(widgets or [], primary=primary)
            window._selected_widget = window._selection_state.primary

        monkeypatch.setattr(window, "_set_selection", fake_set_selection)

        _open_project_window(window, project, project_dir, sdk_root)
        window._update_diagnostics_panel()
        filter_combo = window.diagnostics_panel._severity_filter_combo
        filter_combo.setCurrentIndex(filter_combo.findData("error"))

        assert window.diagnostics_panel._open_first_warning_button.isEnabled() is True
        assert window.diagnostics_panel._list.count() == 1

        window.diagnostics_panel._open_first_warning_button.click()

        assert filter_combo.currentData() == "warning"
        assert window.diagnostics_panel._list.count() == 1
        assert window._selection_state.primary is missing
        assert window._selection_state.widgets == [missing]
        assert window.statusBar().currentMessage() == "Opened diagnostic resource check: image/missing.png."

        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_diagnostics_panel_open_first_warning_is_disabled_without_warnings(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "DiagnosticsNoWarningOpenDemo"
        invalid = WidgetModel("label", name="bad-name", x=8, y=8, width=60, height=20)
        project = _create_project_only_with_widgets(
            project_dir,
            "DiagnosticsNoWarningOpenDemo",
            sdk_root,
            widgets=[invalid],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._update_diagnostics_panel()

        assert window.diagnostics_panel._open_first_warning_button.isEnabled() is False

        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_diagnostics_panel_open_selected_activates_current_item(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "DiagnosticsOpenSelectedDemo"
        invalid = WidgetModel("label", name="bad-name", x=8, y=8, width=60, height=20)
        missing = WidgetModel("image", name="missing_image", x=16, y=48, width=48, height=48)
        missing.properties["image_file"] = "missing.png"
        project = _create_project_only_with_widgets(
            project_dir,
            "DiagnosticsOpenSelectedDemo",
            sdk_root,
            widgets=[invalid, missing],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        def fake_set_selection(widgets=None, primary=None, sync_tree=True, sync_preview=True):
            window._selection_state.set_widgets(widgets or [], primary=primary)
            window._selected_widget = window._selection_state.primary

        monkeypatch.setattr(window, "_set_selection", fake_set_selection)

        _open_project_window(window, project, project_dir, sdk_root)
        window._update_diagnostics_panel()

        assert window.diagnostics_panel._open_selected_button.isEnabled() is False

        target_item = window.diagnostics_panel._list.item(1)
        window.diagnostics_panel._list.setCurrentItem(target_item)

        assert window.diagnostics_panel._open_selected_button.isEnabled() is True

        window.diagnostics_panel._open_selected_button.click()

        assert window._selection_state.primary is missing
        assert window._selection_state.widgets == [missing]
        assert window.statusBar().currentMessage() == "Opened diagnostic resource check: image/missing.png."

        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_diagnostics_panel_preserves_selected_item_across_severity_filter_changes(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "DiagnosticsSelectionFilterDemo"
        invalid = WidgetModel("label", name="bad-name", x=8, y=8, width=60, height=20)
        missing = WidgetModel("image", name="missing_image", x=16, y=48, width=48, height=48)
        missing.properties["image_file"] = "missing.png"
        project = _create_project_only_with_widgets(
            project_dir,
            "DiagnosticsSelectionFilterDemo",
            sdk_root,
            widgets=[invalid, missing],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        def fake_set_selection(widgets=None, primary=None, sync_tree=True, sync_preview=True):
            window._selection_state.set_widgets(widgets or [], primary=primary)
            window._selected_widget = window._selection_state.primary

        monkeypatch.setattr(window, "_set_selection", fake_set_selection)

        _open_project_window(window, project, project_dir, sdk_root)
        window._update_diagnostics_panel()

        target_item = None
        for row in range(window.diagnostics_panel._list.count()):
            item = window.diagnostics_panel._list.item(row)
            if "missing_image" in item.text():
                target_item = item
                break

        assert target_item is not None

        window.diagnostics_panel._list.setCurrentItem(target_item)
        filter_combo = window.diagnostics_panel._severity_filter_combo

        filter_combo.setCurrentIndex(filter_combo.findData("warning"))

        assert window.diagnostics_panel._list.count() == 1
        assert window.diagnostics_panel._list.currentItem() is not None
        assert "missing_image" in window.diagnostics_panel._list.currentItem().text()
        assert window.diagnostics_panel._open_selected_button.isEnabled() is True

        filter_combo.setCurrentIndex(filter_combo.findData(""))

        assert window.diagnostics_panel._list.count() == 2
        assert window.diagnostics_panel._list.currentItem() is not None
        assert "missing_image" in window.diagnostics_panel._list.currentItem().text()

        window.diagnostics_panel._open_selected_button.click()

        assert window._selection_state.primary is missing
        assert window._selection_state.widgets == [missing]
        assert window.statusBar().currentMessage() == "Opened diagnostic resource check: image/missing.png."

        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_diagnostics_panel_preserves_selected_item_across_refresh(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "DiagnosticsSelectionRefreshDemo"
        invalid = WidgetModel("label", name="bad-name", x=8, y=8, width=60, height=20)
        missing = WidgetModel("image", name="missing_image", x=16, y=48, width=48, height=48)
        missing.properties["image_file"] = "missing.png"
        project = _create_project_only_with_widgets(
            project_dir,
            "DiagnosticsSelectionRefreshDemo",
            sdk_root,
            widgets=[invalid, missing],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        def fake_set_selection(widgets=None, primary=None, sync_tree=True, sync_preview=True):
            window._selection_state.set_widgets(widgets or [], primary=primary)
            window._selected_widget = window._selection_state.primary

        monkeypatch.setattr(window, "_set_selection", fake_set_selection)

        _open_project_window(window, project, project_dir, sdk_root)
        window._update_diagnostics_panel()

        target_item = None
        for row in range(window.diagnostics_panel._list.count()):
            item = window.diagnostics_panel._list.item(row)
            if "missing_image" in item.text():
                target_item = item
                break

        assert target_item is not None

        window.diagnostics_panel._list.setCurrentItem(target_item)
        window._update_diagnostics_panel()

        assert window.diagnostics_panel._list.count() == 2
        assert window.diagnostics_panel._list.currentItem() is not None
        assert "missing_image" in window.diagnostics_panel._list.currentItem().text()
        assert window.diagnostics_panel._open_selected_button.isEnabled() is True

        window.diagnostics_panel._open_selected_button.click()

        assert window._selection_state.primary is missing
        assert window._selection_state.widgets == [missing]
        assert window.statusBar().currentMessage() == "Opened diagnostic resource check: image/missing.png."

        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_diagnostics_panel_open_selected_is_disabled_for_non_navigable_items(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "DiagnosticsNonNavigableDemo"
        layout_parent = WidgetModel("linearlayout", name="layout_parent", x=0, y=0, width=240, height=80)
        managed = WidgetModel("label", name="managed_widget", x=12, y=8, width=80, height=20)
        managed.designer_locked = True
        managed.designer_hidden = True
        _add_widget_children(layout_parent, [managed])
        project = _create_project_only_with_widgets(
            project_dir,
            "DiagnosticsNonNavigableDemo",
            sdk_root,
            widgets=[layout_parent],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._selection_state.set_widgets([managed], primary=managed)
        window._selected_widget = managed
        window._update_diagnostics_panel()

        assert window.diagnostics_panel._list.count() == 3

        activations = []
        window.diagnostics_panel.diagnostic_activated.connect(lambda page_name, widget_name: activations.append((page_name, widget_name)))

        item = window.diagnostics_panel._list.item(0)
        window.diagnostics_panel._list.setCurrentItem(item)

        assert item.text().startswith("[Info]")
        assert window.diagnostics_panel._open_selected_button.isEnabled() is False

        window.diagnostics_panel._on_item_activated(item)

        assert activations == []

        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_copy_diagnostics_summary_copies_panel_entries(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "DiagnosticsCopyDemo"
        invalid = WidgetModel("label", name="bad-name", x=8, y=8, width=60, height=20)
        missing = WidgetModel("image", name="missing_image", x=16, y=48, width=48, height=48)
        missing.properties["image_file"] = "missing.png"
        project = _create_project_only_with_widgets(
            project_dir,
            "DiagnosticsCopyDemo",
            sdk_root,
            widgets=[invalid, missing],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._update_diagnostics_panel()

        QApplication.clipboard().clear()
        assert window.diagnostics_panel._copy_button.isEnabled() is True

        window.diagnostics_panel._copy_button.click()

        copied = QApplication.clipboard().text()
        assert copied.startswith("Diagnostics: ")
        assert "bad-name" in copied
        assert "missing_image" in copied
        assert window.statusBar().currentMessage() == "Copied diagnostics summary."

        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_copy_diagnostics_summary_respects_severity_filter(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "DiagnosticsCopyFilteredDemo"
        invalid = WidgetModel("label", name="bad-name", x=8, y=8, width=60, height=20)
        missing = WidgetModel("image", name="missing_image", x=16, y=48, width=48, height=48)
        missing.properties["image_file"] = "missing.png"
        project = _create_project_only_with_widgets(
            project_dir,
            "DiagnosticsCopyFilteredDemo",
            sdk_root,
            widgets=[invalid, missing],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._update_diagnostics_panel()
        filter_combo = window.diagnostics_panel._severity_filter_combo
        filter_combo.setCurrentIndex(filter_combo.findData("warning"))

        QApplication.clipboard().clear()
        window.diagnostics_panel._copy_button.click()

        copied = QApplication.clipboard().text()
        assert copied.startswith("Diagnostics: ")
        assert "Filter: warning (1 item(s))" in copied
        assert "missing_image" in copied
        assert "bad-name" not in copied
        assert window.statusBar().currentMessage() == "Copied diagnostics summary."

        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_copy_diagnostics_summary_without_entries_reports_empty_state(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "DiagnosticsCopyEmptyDemo"
        project = _create_project(project_dir, "DiagnosticsCopyEmptyDemo", sdk_root)

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._update_diagnostics_panel()

        QApplication.clipboard().setText("sentinel")
        assert window.diagnostics_panel._copy_button.isEnabled() is False

        window._copy_diagnostics_summary()

        assert QApplication.clipboard().text() == "sentinel"
        assert window.statusBar().currentMessage() == "No diagnostics to copy."

        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_copy_diagnostics_json_copies_structured_payload(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "DiagnosticsCopyJsonDemo"
        invalid = WidgetModel("label", name="bad-name", x=8, y=8, width=60, height=20)
        missing = WidgetModel("image", name="missing_image", x=16, y=48, width=48, height=48)
        missing.properties["image_file"] = "missing.png"
        project = _create_project_only_with_widgets(
            project_dir,
            "DiagnosticsCopyJsonDemo",
            sdk_root,
            widgets=[invalid, missing],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._update_diagnostics_panel()

        QApplication.clipboard().clear()
        assert window.diagnostics_panel._copy_json_button.isEnabled() is True

        window.diagnostics_panel._copy_json_button.click()

        copied = json.loads(QApplication.clipboard().text())
        assert copied["project"]["app_name"] == "DiagnosticsCopyJsonDemo"
        assert Path(copied["project"]["project_dir"]) == project_dir
        assert copied["summary"]["errors"] == 1
        assert copied["summary"]["warnings"] == 1
        assert copied["summary"]["info"] == 0
        assert copied["summary"]["total"] == 2
        assert copied["view"] == {
            "severity_filter": "",
            "visible_total": 2,
            "selected_code": "",
            "selected_target_kind": "",
            "selected_target_page_name": "",
            "selected_target_widget_name": "",
        }
        assert any(
            entry["code"] == "invalid_name"
            and entry["widget_name"] == "bad-name"
            and entry["target_kind"] == "widget"
            and entry["target_page_name"] == "main_page"
            and entry["target_widget_name"] == "bad-name"
            for entry in copied["entries"]
        )
        assert any(
            entry["code"] == "missing_resource"
            and entry["resource_name"] == "missing.png"
            and entry["target_kind"] == "resource"
            and entry["target_page_name"] == "main_page"
            and entry["target_widget_name"] == "missing_image"
            for entry in copied["entries"]
        )
        assert window.statusBar().currentMessage() == "Copied diagnostics JSON."

        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_copy_diagnostics_json_respects_severity_filter(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "DiagnosticsCopyJsonFilteredDemo"
        invalid = WidgetModel("label", name="bad-name", x=8, y=8, width=60, height=20)
        missing = WidgetModel("image", name="missing_image", x=16, y=48, width=48, height=48)
        missing.properties["image_file"] = "missing.png"
        project = _create_project_only_with_widgets(
            project_dir,
            "DiagnosticsCopyJsonFilteredDemo",
            sdk_root,
            widgets=[invalid, missing],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._update_diagnostics_panel()
        filter_combo = window.diagnostics_panel._severity_filter_combo
        filter_combo.setCurrentIndex(filter_combo.findData("warning"))

        QApplication.clipboard().clear()
        window.diagnostics_panel._copy_json_button.click()

        copied = json.loads(QApplication.clipboard().text())
        assert copied["summary"] == {"errors": 0, "warnings": 1, "info": 0, "total": 1}
        assert copied["view"] == {
            "severity_filter": "warning",
            "visible_total": 1,
            "selected_code": "",
            "selected_target_kind": "",
            "selected_target_page_name": "",
            "selected_target_widget_name": "",
        }
        assert len(copied["entries"]) == 1
        assert copied["entries"][0]["code"] == "missing_resource"
        assert copied["entries"][0]["widget_name"] == "missing_image"
        assert copied["entries"][0]["target_kind"] == "resource"
        assert copied["entries"][0]["target_page_name"] == "main_page"
        assert copied["entries"][0]["target_widget_name"] == "missing_image"

        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_copy_diagnostics_json_includes_selected_entry_context(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "DiagnosticsCopyJsonSelectedDemo"
        invalid = WidgetModel("label", name="bad-name", x=8, y=8, width=60, height=20)
        missing = WidgetModel("image", name="missing_image", x=16, y=48, width=48, height=48)
        missing.properties["image_file"] = "missing.png"
        project = _create_project_only_with_widgets(
            project_dir,
            "DiagnosticsCopyJsonSelectedDemo",
            sdk_root,
            widgets=[invalid, missing],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._update_diagnostics_panel()

        target_item = None
        for row in range(window.diagnostics_panel._list.count()):
            item = window.diagnostics_panel._list.item(row)
            if "missing_image" in item.text():
                target_item = item
                break

        assert target_item is not None

        window.diagnostics_panel._list.setCurrentItem(target_item)

        QApplication.clipboard().clear()
        window.diagnostics_panel._copy_json_button.click()

        copied = json.loads(QApplication.clipboard().text())
        assert copied["view"]["selected_code"] == "missing_resource"
        assert copied["view"]["selected_target_kind"] == "resource"
        assert copied["view"]["selected_target_page_name"] == "main_page"
        assert copied["view"]["selected_target_widget_name"] == "missing_image"

        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_copy_diagnostics_json_classifies_page_metadata_targets(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        def _setup_page_metadata(page, _root):
            page.user_fields = [{"name": "bad-name", "type": "int", "default": "0"}]
            page.timers = [{"name": "refresh_timer", "callback": "", "delay_ms": "1000", "period_ms": "1000", "auto_start": False}]

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "DiagnosticsCopyJsonMetadataDemo"
        project = _create_project_only_with_widgets(
            project_dir,
            "DiagnosticsCopyJsonMetadataDemo",
            sdk_root,
            page_customizer=_setup_page_metadata,
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._update_diagnostics_panel()

        QApplication.clipboard().clear()
        window.diagnostics_panel._copy_json_button.click()

        copied = json.loads(QApplication.clipboard().text())
        assert any(
            entry["code"] == "page_field_invalid_name"
            and entry["widget_name"] == "bad-name"
            and entry["target_kind"] == "page_field"
            and entry["target_page_name"] == "main_page"
            and entry["target_widget_name"] == ""
            for entry in copied["entries"]
        )
        assert any(
            entry["code"] == "page_timer_missing_callback"
            and entry["widget_name"] == "refresh_timer"
            and entry["target_kind"] == "page_timer"
            and entry["target_page_name"] == "main_page"
            and entry["target_widget_name"] == ""
            for entry in copied["entries"]
        )

        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_copy_diagnostics_json_classifies_project_callback_targets(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "DiagnosticsCopyJsonProjectTargetsDemo"
        main_button = WidgetModel("button", name="confirm_button", x=8, y=8, width=80, height=28)
        detail_button = WidgetModel("button", name="confirm_button_2", x=8, y=8, width=80, height=28)
        main_button.on_click = "on_confirm"
        detail_button.on_click = "on_confirm"
        project = _create_project_only_with_page_widgets(
            project_dir,
            "DiagnosticsCopyJsonProjectTargetsDemo",
            sdk_root,
            page_widgets={
                "main_page": [main_button],
                "detail_page": [detail_button],
            },
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._update_diagnostics_panel()

        QApplication.clipboard().clear()
        window.diagnostics_panel._copy_json_button.click()

        copied = json.loads(QApplication.clipboard().text())
        assert any(
            entry["code"] == "project_callback_duplicate"
            and entry["widget_name"] == "on_confirm"
            and entry["target_kind"] == "widget"
            and entry["target_page_name"] == "detail_page"
            and entry["target_widget_name"] == "confirm_button_2"
            for entry in copied["entries"]
        )

        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_copy_diagnostics_json_without_entries_reports_empty_state(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "DiagnosticsCopyJsonEmptyDemo"
        project = _create_project(project_dir, "DiagnosticsCopyJsonEmptyDemo", sdk_root)

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._update_diagnostics_panel()

        QApplication.clipboard().setText("sentinel")
        assert window.diagnostics_panel._copy_json_button.isEnabled() is False

        window._copy_diagnostics_json()

        assert QApplication.clipboard().text() == "sentinel"
        assert window.statusBar().currentMessage() == "No diagnostics JSON to copy."

        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_export_diagnostics_summary_writes_panel_entries(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "DiagnosticsExportDemo"
        invalid = WidgetModel("label", name="bad-name", x=8, y=8, width=60, height=20)
        missing = WidgetModel("image", name="missing_image", x=16, y=48, width=48, height=48)
        missing.properties["image_file"] = "missing.png"
        project = _create_project_only_with_widgets(
            project_dir,
            "DiagnosticsExportDemo",
            sdk_root,
            widgets=[invalid, missing],
        )

        export_path = tmp_path / "exports" / "diagnostics-summary"

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(
            "ui_designer.ui.main_window.QFileDialog.getSaveFileName",
            lambda *args, **kwargs: (str(export_path), "Text Files (*.txt)"),
        )

        _open_project_window(window, project, project_dir, sdk_root)
        window._update_diagnostics_panel()

        assert window.diagnostics_panel._export_button.isEnabled() is True

        window.diagnostics_panel._export_button.click()

        resolved_export_path = export_path.with_suffix(".txt")
        exported = resolved_export_path.read_text(encoding="utf-8")
        assert exported.startswith("Diagnostics: ")
        assert "bad-name" in exported
        assert "missing_image" in exported
        assert exported.endswith("\n")
        assert window.statusBar().currentMessage() == f"Exported diagnostics summary to {resolved_export_path}"

        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_export_diagnostics_summary_without_entries_reports_empty_state(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "DiagnosticsExportEmptyDemo"
        project = _create_project(project_dir, "DiagnosticsExportEmptyDemo", sdk_root)

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        def unexpected_get_save_file_name(*args, **kwargs):
            raise AssertionError("getSaveFileName should not be called without diagnostics")

        monkeypatch.setattr("ui_designer.ui.main_window.QFileDialog.getSaveFileName", unexpected_get_save_file_name)

        _open_project_window(window, project, project_dir, sdk_root)
        window._update_diagnostics_panel()

        assert window.diagnostics_panel._export_button.isEnabled() is False

        window._export_diagnostics_summary()

        assert window.statusBar().currentMessage() == "No diagnostics to export."

        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_export_diagnostics_json_writes_structured_payload(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "DiagnosticsJsonDemo"
        invalid = WidgetModel("label", name="bad-name", x=8, y=8, width=60, height=20)
        missing = WidgetModel("image", name="missing_image", x=16, y=48, width=48, height=48)
        missing.properties["image_file"] = "missing.png"
        project = _create_project_only_with_widgets(
            project_dir,
            "DiagnosticsJsonDemo",
            sdk_root,
            widgets=[invalid, missing],
        )

        export_path = tmp_path / "exports" / "diagnostics"

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(
            "ui_designer.ui.main_window.QFileDialog.getSaveFileName",
            lambda *args, **kwargs: (str(export_path), "JSON Files (*.json)"),
        )

        _open_project_window(window, project, project_dir, sdk_root)
        window._update_diagnostics_panel()

        assert window.diagnostics_panel._export_json_button.isEnabled() is True

        window.diagnostics_panel._export_json_button.click()

        resolved_export_path = export_path.with_suffix(".json")
        exported = json.loads(resolved_export_path.read_text(encoding="utf-8"))
        assert exported["project"]["app_name"] == "DiagnosticsJsonDemo"
        assert Path(exported["project"]["project_dir"]) == project_dir
        assert exported["project"]["current_page"] == "main_page"
        assert exported["summary"]["errors"] == 1
        assert exported["summary"]["warnings"] == 1
        assert exported["summary"]["info"] == 0
        assert exported["summary"]["total"] == 2
        assert any(
            entry["code"] == "invalid_name"
            and entry["widget_name"] == "bad-name"
            and entry["target_kind"] == "widget"
            and entry["target_page_name"] == "main_page"
            and entry["target_widget_name"] == "bad-name"
            for entry in exported["entries"]
        )
        assert any(
            entry["code"] == "missing_resource"
            and entry["resource_name"] == "missing.png"
            and entry["target_kind"] == "resource"
            and entry["target_page_name"] == "main_page"
            and entry["target_widget_name"] == "missing_image"
            for entry in exported["entries"]
        )
        assert window.statusBar().currentMessage() == f"Exported diagnostics JSON to {resolved_export_path}"

        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_export_diagnostics_json_without_entries_reports_empty_state(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "DiagnosticsJsonEmptyDemo"
        project = _create_project(project_dir, "DiagnosticsJsonEmptyDemo", sdk_root)

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        def unexpected_get_save_file_name(*args, **kwargs):
            raise AssertionError("getSaveFileName should not be called without diagnostics")

        monkeypatch.setattr("ui_designer.ui.main_window.QFileDialog.getSaveFileName", unexpected_get_save_file_name)

        _open_project_window(window, project, project_dir, sdk_root)
        window._update_diagnostics_panel()

        assert window.diagnostics_panel._export_json_button.isEnabled() is False

        window._export_diagnostics_json()

        assert window.statusBar().currentMessage() == "No diagnostics JSON to export."

        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_diagnostic_request_switches_page_and_selects_widget(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "DiagnosticFocusDemo"
        target = WidgetModel("label", name="target", x=16, y=16, width=80, height=20)
        project = _create_project_only_with_page_widgets(
            project_dir,
            "DiagnosticFocusDemo",
            sdk_root,
            page_widgets={"detail_page": [target]},
            pages=["main_page", "detail_page"],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)

        def fake_set_selection(widgets=None, primary=None, sync_tree=True, sync_preview=True):
            window._selection_state.set_widgets(widgets or [], primary=primary)
            window._selected_widget = window._selection_state.primary

        monkeypatch.setattr(window, "_set_selection", fake_set_selection)

        assert window._current_page.name == "main_page"

        window._show_inspector_tab("animations")
        window._on_diagnostic_requested("detail_page", "target")

        assert window._current_page.name == "detail_page"
        assert window._inspector_tabs.currentIndex() == 0
        assert window._selection_state.primary is target
        assert window._selection_state.widgets == [target]
        assert window.statusBar().currentMessage() == "Opened diagnostic target: detail_page/target."

        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_page_field_diagnostic_activation_selects_field_row(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        def _setup_page_fields(page, _root):
            page.user_fields = [{"name": "bad-name", "type": "int", "default": "0"}]

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "FieldDiagnosticFocusDemo"
        project = _create_project_only_with_widgets(
            project_dir,
            "FieldDiagnosticFocusDemo",
            sdk_root,
            page_customizer=_setup_page_fields,
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._update_diagnostics_panel()

        item = window.diagnostics_panel._list.item(0)
        window.diagnostics_panel._on_item_activated(item)

        selected_rows = window.page_fields_panel._table.selectionModel().selectedRows()
        assert len(selected_rows) == 1
        assert selected_rows[0].row() == 0
        assert window.page_fields_panel._table.item(0, 0).text() == "bad-name"
        assert window.statusBar().currentMessage() == "Opened diagnostic field: main_page/bad-name."

        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_page_timer_diagnostic_activation_selects_timer_row(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        def _setup_page_timers(page, _root):
            page.timers = [{"name": "refresh_timer", "callback": "", "delay_ms": "1000", "period_ms": "1000", "auto_start": False}]

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "TimerDiagnosticFocusDemo"
        project = _create_project_only_with_widgets(
            project_dir,
            "TimerDiagnosticFocusDemo",
            sdk_root,
            page_customizer=_setup_page_timers,
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        window._update_diagnostics_panel()

        item = window.diagnostics_panel._list.item(0)
        window.diagnostics_panel._on_item_activated(item)

        selected_rows = window.page_timers_panel._table.selectionModel().selectedRows()
        assert len(selected_rows) == 1
        assert selected_rows[0].row() == 0
        assert window.page_timers_panel._table.item(0, 0).text() == "refresh_timer"
        assert window.statusBar().currentMessage() == "Opened diagnostic timer: main_page/refresh_timer."

        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_missing_resource_diagnostic_activation_opens_resource_panel_usage(self, tmp_path):
        repo_root = Path(__file__).resolve().parents[4]
        script = textwrap.dedent(
            f"""
            import os
            import shutil
            import sys
            from pathlib import Path

            os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

            repo_root = Path({repr(str(repo_root))})
            sys.path.insert(0, str(repo_root / "scripts"))

            from PyQt5.QtWidgets import QApplication

            from ui_designer.model.widget_model import WidgetModel
            from ui_designer.tests.project_builders import build_saved_test_project_only_with_widgets
            from ui_designer.tests.ui.window_test_helpers import (
                disable_main_window_compile as _disable_window_compile,
                open_loaded_test_project as _open_project_window,
            )
            from ui_designer.ui.main_window import MainWindow
            from ui_designer.utils.runtime_temp import create_repo_temp_workspace


            def create_sdk_root(root: Path):
                (root / "src").mkdir(parents=True)
                (root / "porting" / "designer").mkdir(parents=True)
                (root / "Makefile").write_text("all:\\n", encoding="utf-8")
            class DisabledCompiler:
                def can_build(self):
                    return False

                def is_preview_running(self):
                    return False

                def stop_exe(self):
                    return None

                def cleanup(self):
                    return None

                def get_build_error(self):
                    return "preview disabled for test"

                def set_screen_size(self, width, height):
                    return None

                def is_exe_ready(self):
                    return False


            temp_root = create_repo_temp_workspace(repo_root, "ui_designer_diag_resource_")
            app = QApplication.instance() or QApplication([])
            try:
                sdk_root = temp_root / "sdk"
                create_sdk_root(sdk_root)
                project_dir = temp_root / "DiagnosticMissingResourceDemo"
                missing = WidgetModel("image", name="missing_image", x=16, y=16, width=48, height=48)
                missing.properties["image_file"] = "ghost.png"
                project = build_saved_test_project_only_with_widgets(
                    project_dir,
                    "DiagnosticMissingResourceDemo",
                    sdk_root,
                    widgets=[missing],
                )

                window = MainWindow(str(sdk_root))
                _disable_window_compile(window, DisabledCompiler)

                _open_project_window(window, project, project_dir, sdk_root)

                item = window.diagnostics_panel._list.item(0)
                window.diagnostics_panel._on_item_activated(item)

                assert window._selection_state.primary is missing
                assert window.res_panel._current_resource_type == "image"
                assert window.res_panel._current_resource_name == "ghost.png"
                assert window.res_panel._tabs.currentIndex() == 0
                assert window.res_panel._usage_summary.text() == "1 widget across 1 page | ghost.png"
                assert window.statusBar().currentMessage() == "Opened diagnostic resource check: image/ghost.png."

                window._undo_manager.mark_all_saved()
                window.close()
                window.deleteLater()
                app.sendPostedEvents()
                app.processEvents()
            finally:
                shutil.rmtree(temp_root, ignore_errors=True)
            """
        )

        env = os.environ.copy()
        env.setdefault("QT_QPA_PLATFORM", "offscreen")
        result = subprocess.run(
            [sys.executable, "-c", script],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            timeout=60,
        )

        assert result.returncode == 0, f"stdout:\\n{result.stdout}\\n\\nstderr:\\n{result.stderr}"

    def test_missing_string_diagnostic_activation_opens_string_usage(self, tmp_path):
        repo_root = Path(__file__).resolve().parents[4]
        script = textwrap.dedent(
            f"""
            import os
            import shutil
            import sys
            from pathlib import Path

            os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

            repo_root = Path({repr(str(repo_root))})
            sys.path.insert(0, str(repo_root / "scripts"))

            from PyQt5.QtWidgets import QApplication

            from ui_designer.model.widget_model import WidgetModel
            from ui_designer.tests.project_builders import build_saved_test_project_only_with_widgets
            from ui_designer.tests.ui.window_test_helpers import (
                disable_main_window_compile as _disable_window_compile,
                open_loaded_test_project as _open_project_window,
            )
            from ui_designer.ui.main_window import MainWindow
            from ui_designer.utils.runtime_temp import create_repo_temp_workspace


            def create_sdk_root(root: Path):
                (root / "src").mkdir(parents=True)
                (root / "porting" / "designer").mkdir(parents=True)
                (root / "Makefile").write_text("all:\\n", encoding="utf-8")
            class DisabledCompiler:
                def can_build(self):
                    return False

                def is_preview_running(self):
                    return False

                def stop_exe(self):
                    return None

                def cleanup(self):
                    return None

                def get_build_error(self):
                    return "preview disabled for test"

                def set_screen_size(self, width, height):
                    return None

                def is_exe_ready(self):
                    return False


            temp_root = create_repo_temp_workspace(repo_root, "ui_designer_diag_string_")
            app = QApplication.instance() or QApplication([])
            try:
                sdk_root = temp_root / "sdk"
                create_sdk_root(sdk_root)
                project_dir = temp_root / "DiagnosticMissingStringDemo"
                title = WidgetModel("label", name="title", x=16, y=16, width=80, height=20)
                title.properties["text"] = "@string/missing_key"
                project = build_saved_test_project_only_with_widgets(
                    project_dir,
                    "DiagnosticMissingStringDemo",
                    sdk_root,
                    widgets=[title],
                )

                window = MainWindow(str(sdk_root))
                _disable_window_compile(window, DisabledCompiler)

                _open_project_window(window, project, project_dir, sdk_root)

                item = window.diagnostics_panel._list.item(0)
                window.diagnostics_panel._on_item_activated(item)

                assert window._selection_state.primary is title
                assert window.res_panel._current_resource_type == "string"
                assert window.res_panel._current_resource_name == "missing_key"
                assert window.res_panel._tabs.currentIndex() == 3
                assert window.res_panel._usage_summary.text() == "1 widget across 1 page | missing_key"
                assert window.statusBar().currentMessage() == "Opened diagnostic resource check: string/missing_key."

                window._undo_manager.mark_all_saved()
                window.close()
                window.deleteLater()
                app.sendPostedEvents()
                app.processEvents()
            finally:
                shutil.rmtree(temp_root, ignore_errors=True)
            """
        )

        env = os.environ.copy()
        env.setdefault("QT_QPA_PLATFORM", "offscreen")
        result = subprocess.run(
            [sys.executable, "-c", script],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            timeout=60,
        )

        assert result.returncode == 0, f"stdout:\\n{result.stdout}\\n\\nstderr:\\n{result.stderr}"

    def test_window_state_helpers_roundtrip_with_config_storage(self, qapp, isolated_config, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")

        saved_geometry = QByteArray(b"geometry-bytes")
        saved_state = QByteArray(b"state-bytes")
        monkeypatch.setattr(window, "saveGeometry", lambda: saved_geometry)
        monkeypatch.setattr(window, "saveState", lambda: saved_state)

        window._save_window_state_to_config()

        assert isolated_config.window_geometry == bytes(saved_geometry.toBase64()).decode("ascii")
        assert isolated_config.window_state == bytes(saved_state.toBase64()).decode("ascii")
        assert isolated_config.workspace_state.get("focus_canvas_enabled") is False

        restore_calls = {}
        monkeypatch.setattr(window, "restoreGeometry", lambda data: restore_calls.setdefault("geometry", bytes(data)) or True)
        monkeypatch.setattr(window, "restoreState", lambda data: restore_calls.setdefault("state", bytes(data)) or True)

        window._apply_saved_window_state()

        assert restore_calls["geometry"] == b"geometry-bytes"
        assert restore_calls["state"] == b"state-bytes"
        assert window.project_dock.objectName() == "project_explorer_dock"
        assert window.tree_dock.objectName() == "widget_tree_dock"
        assert window.props_dock.objectName() == "properties_dock"
        assert window.animations_dock.objectName() == "animations_dock"
        assert window.res_dock.objectName() == "resources_dock"
        assert window.history_dock.objectName() == "history_dock"
        assert window.diagnostics_dock.objectName() == "diagnostics_dock"
        assert window.debug_dock.objectName() == "debug_output_dock"
        assert window._toolbar.objectName() == "main_toolbar"
        assert isolated_config.workspace_state.get("inspector_group_expanded") == {}
        _close_window(window)

    def test_inspector_group_expanded_persist_and_restore(self, qapp, isolated_config, monkeypatch):
        from PyQt5.QtCore import QByteArray

        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")
        window.property_panel.set_inspector_group_expanded_state(
            {"label\tBasic": False, "__multi__\tCallbacks": False}
        )
        monkeypatch.setattr(window, "saveGeometry", lambda: QByteArray())
        monkeypatch.setattr(window, "saveState", lambda: QByteArray())
        window._save_window_state_to_config()
        assert isolated_config.workspace_state.get("inspector_group_expanded") == {
            "label\tBasic": False,
            "__multi__\tCallbacks": False,
        }
        _close_window(window)

        isolated_config.workspace_layout_version = 3
        isolated_config.workspace_state = {
            "inspector_group_expanded": {"button\tStyle": False},
        }
        window2 = MainWindow("")
        assert window2.property_panel.inspector_group_expanded_snapshot() == {"button\tStyle": False}
        _close_window(window2)

    def test_property_grid_name_column_width_persists_and_restores(self, qapp, isolated_config, monkeypatch):
        from PyQt5.QtCore import QByteArray

        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")
        window.property_panel.set_property_grid_name_column_width(222)
        monkeypatch.setattr(window, "saveGeometry", lambda: QByteArray())
        monkeypatch.setattr(window, "saveState", lambda: QByteArray())
        window._save_window_state_to_config()
        assert isolated_config.workspace_state.get("property_grid_name_column_width") == 222
        _close_window(window)

        isolated_config.workspace_layout_version = 3
        isolated_config.workspace_state = {
            "property_grid_name_column_width": 244,
        }
        window2 = MainWindow("")
        assert window2.property_panel.property_grid_name_column_width() == 244
        _close_window(window2)

    def test_main_window_clamps_to_available_screen(self, qapp, monkeypatch):
        from PyQt5.QtCore import QRect

        class _FakeScreen:
            def availableGeometry(self):
                return QRect(0, 0, 1000, 700)

        monkeypatch.setattr(
            "ui_designer.ui.main_window.QGuiApplication.primaryScreen",
            staticmethod(lambda: _FakeScreen()),
        )
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")
        margin = 12
        assert window.width() <= 1000 - 2 * margin
        assert window.height() <= 700 - 2 * margin
        assert window.minimumWidth() == 960
        assert window.props_dock.minimumWidth() == 264
        _close_window(window)

    def test_workspace_preferences_restore_focus_canvas_mode(self, qapp, isolated_config):
        from ui_designer.ui.main_window import MainWindow

        isolated_config.workspace_state = {"focus_canvas_enabled": True}
        isolated_config.workspace_layout_version = 3

        window = MainWindow("")

        assert window._focus_canvas_enabled is True
        assert window._focus_canvas_action.isChecked() is True
        assert window._left_shell.isHidden() is True
        assert window._inspector_tabs.isHidden() is True
        _close_window(window)

    def test_workspace_layout_version_bump_ignores_old_splitter_state_and_keeps_center_primary(self, qapp, isolated_config):
        from ui_designer.ui.main_window import (
            MainWindow,
            LEFT_PANEL_DEFAULT_WIDTH,
            INSPECTOR_PANEL_DEFAULT_WIDTH,
        )

        seed = MainWindow("")
        seed._top_splitter.setSizes([520, 400, 500])
        saved_top_splitter = bytes(seed._top_splitter.saveState().toBase64()).decode("ascii")
        _close_window(seed)

        isolated_config.window_state = ""
        isolated_config.workspace_state = {"top_splitter": saved_top_splitter}
        isolated_config.workspace_layout_version = 2

        window = MainWindow("")
        window._central_stack.setCurrentWidget(window._editor_container)
        window.resize(1400, 900)
        window.show()
        qapp.processEvents()

        sizes = window._top_splitter.sizes()

        assert sizes[1] > sizes[0]
        assert sizes[1] > sizes[2]
        assert abs(sizes[0] - LEFT_PANEL_DEFAULT_WIDTH) <= 2
        assert abs(sizes[2] - INSPECTOR_PANEL_DEFAULT_WIDTH) <= 2
        _close_window(window)

    def test_bottom_panel_toggle_preserves_user_splitter_sizes(self, qapp, isolated_config):
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")

        window._set_bottom_panel_visible(True)
        window._workspace_splitter.setSizes([777, 333])
        expected_visible_sizes = window._workspace_splitter.sizes()

        window._set_bottom_panel_visible(False)
        assert window._bottom_panel_visible is False
        assert window._bottom_panel_last_visible_sizes == expected_visible_sizes[:2]

        window._set_bottom_panel_visible(True)
        assert window._bottom_panel_visible is True
        restored = window._workspace_splitter.sizes()
        assert restored[1] > 0
        assert abs(restored[0] - expected_visible_sizes[0]) <= 2
        assert abs(restored[1] - expected_visible_sizes[1]) <= 2

        _close_window(window)

    def test_show_bottom_panel_does_not_reset_splitter_when_already_visible(self, qapp, isolated_config):
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")

        window._set_bottom_panel_visible(True)
        window._workspace_splitter.setSizes([643, 289])
        before = window._workspace_splitter.sizes()

        window._show_bottom_panel("History")

        after = window._workspace_splitter.sizes()
        assert window._bottom_panel_visible is True
        assert after[1] > 0
        assert abs(after[0] - before[0]) <= 2
        assert abs(after[1] - before[1]) <= 2

        _close_window(window)

    def test_focus_canvas_restore_reuses_last_bottom_splitter_sizes(self, qapp, isolated_config):
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")

        window._set_bottom_panel_visible(True)
        window._workspace_splitter.setSizes([702, 198])
        expected_visible_sizes = window._workspace_splitter.sizes()

        window._set_focus_canvas_enabled(True)
        assert window._bottom_panel_visible is False

        window._set_focus_canvas_enabled(False)

        restored = window._workspace_splitter.sizes()
        assert window._bottom_panel_visible is True
        assert restored[1] > 0
        assert abs(restored[0] - expected_visible_sizes[0]) <= 2
        assert abs(restored[1] - expected_visible_sizes[1]) <= 2

        _close_window(window)

    def test_top_splitter_sizes_survive_left_panel_switches(self, qapp, isolated_config):
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")

        window._top_splitter.setSizes([281, 654, 299])
        before = window._top_splitter.sizes()

        window._select_left_panel("widgets")
        window._select_left_panel("assets")
        window._select_left_panel("project")

        after = window._top_splitter.sizes()
        assert abs(after[0] - before[0]) <= 2
        assert abs(after[1] - before[1]) <= 2
        assert abs(after[2] - before[2]) <= 2

        _close_window(window)

    def test_top_splitter_sizes_survive_inspector_tab_switches(self, qapp, isolated_config):
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")

        window._top_splitter.setSizes([305, 620, 321])
        before = window._top_splitter.sizes()

        window._show_inspector_tab("animations")
        window._show_inspector_tab("page", "timers")
        window._show_inspector_tab("properties")

        after = window._top_splitter.sizes()
        assert abs(after[0] - before[0]) <= 2
        assert abs(after[1] - before[1]) <= 2
        assert abs(after[2] - before[2]) <= 2

        _close_window(window)

    def test_focus_canvas_roundtrip_restores_top_splitter_sizes(self, qapp, isolated_config):
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")

        window._top_splitter.setSizes([263, 701, 287])
        expected = window._top_splitter.sizes()

        window._set_focus_canvas_enabled(True)
        assert window._focus_canvas_enabled is True

        window._set_focus_canvas_enabled(False)
        restored = window._top_splitter.sizes()

        assert window._focus_canvas_enabled is False
        assert abs(restored[0] - expected[0]) <= 2
        assert abs(restored[1] - expected[1]) <= 2
        assert abs(restored[2] - expected[2]) <= 2

        _close_window(window)

    def test_status_panel_top_splitter_handle_drag_with_qtest(self, qapp, isolated_config, monkeypatch):
        from PyQt5.QtCore import QRect

        if os.environ.get("QT_QPA_PLATFORM", "").strip().lower() == "offscreen":
            pytest.skip("QTest splitter drag requires a non-offscreen platform plugin")

        class _FakeScreen:
            def availableGeometry(self):
                return QRect(0, 0, 1800, 1200)

        monkeypatch.setattr(
            "ui_designer.ui.main_window.QGuiApplication.primaryScreen",
            staticmethod(lambda: _FakeScreen()),
        )
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")
        window.resize(1800, 1000)
        window.showNormal()
        window.show()
        qapp.processEvents()
        QTest.qWait(80)

        window._select_left_panel("status")
        split = window._top_splitter
        split.setSizes([360, 920, 360])
        qapp.processEvents()
        QTest.qWait(30)

        before = split.sizes()
        handle = split.handle(1)
        handle.show()
        qapp.processEvents()
        start = handle.rect().center()

        # Drag right on the first splitter handle: left pane should grow.
        QTest.mousePress(handle, Qt.LeftButton, Qt.NoModifier, start)
        for step in range(1, 7):
            QTest.mouseMove(handle, QPoint(start.x() + step * 14, start.y()))
            QTest.qWait(5)
        QTest.mouseRelease(handle, Qt.LeftButton, Qt.NoModifier, QPoint(start.x() + 84, start.y()))
        qapp.processEvents()
        after_right = split.sizes()

        # Drag left from the same handle: left pane should shrink.
        start2 = handle.rect().center()
        QTest.mousePress(handle, Qt.LeftButton, Qt.NoModifier, start2)
        for step in range(1, 7):
            QTest.mouseMove(handle, QPoint(start2.x() - step * 16, start2.y()))
            QTest.qWait(5)
        QTest.mouseRelease(handle, Qt.LeftButton, Qt.NoModifier, QPoint(start2.x() - 96, start2.y()))
        qapp.processEvents()
        after_left = split.sizes()

        assert after_right[0] > before[0]
        assert after_right[1] < before[1]
        assert after_left[0] < after_right[0]
        assert after_left[1] > after_right[1]

        _close_window(window)

    def test_workspace_left_tabs_switch_panels_via_click(self, qapp, isolated_config):
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")
        window.show()
        qapp.processEvents()

        tab_bar = window._workspace_nav_frame
        assets_rect = tab_bar.tabRect(_left_panel_tab_index(window, "assets"))
        QTest.mouseClick(tab_bar, Qt.LeftButton, Qt.NoModifier, assets_rect.center())
        qapp.processEvents()

        assert window._current_left_panel == "assets"
        assert window._left_panel_stack.currentWidget() is window.res_panel

        structure_rect = tab_bar.tabRect(_left_panel_tab_index(window, "structure"))
        QTest.mouseClick(tab_bar, Qt.LeftButton, Qt.NoModifier, structure_rect.center())
        qapp.processEvents()

        assert window._current_left_panel == "structure"
        assert window._left_panel_stack.currentWidget() is window.widget_tree

        _close_window(window)

    def test_workspace_inspector_tabs_switch_via_tabbar_click(self, qapp, isolated_config):
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")
        window.show()
        qapp.processEvents()

        tab_bar = window._inspector_tabs.tabBar()
        page_rect = tab_bar.tabRect(2)
        QTest.mouseClick(tab_bar, Qt.LeftButton, Qt.NoModifier, page_rect.center())
        qapp.processEvents()

        assert window._inspector_tabs.currentIndex() == 2

        animations_rect = tab_bar.tabRect(1)
        QTest.mouseClick(tab_bar, Qt.LeftButton, Qt.NoModifier, animations_rect.center())
        qapp.processEvents()

        assert window._inspector_tabs.currentIndex() == 1

        _close_window(window)

    def test_bottom_toggle_button_click_hides_and_shows_bottom_panel(self, qapp, isolated_config):
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")
        window.show()
        qapp.processEvents()

        window._set_bottom_panel_visible(True)
        assert window._bottom_panel_visible is True

        QTest.mouseClick(window._bottom_toggle_button, Qt.LeftButton)
        qapp.processEvents()
        assert window._bottom_panel_visible is False

        QTest.mouseClick(window._bottom_toggle_button, Qt.LeftButton)
        qapp.processEvents()
        assert window._bottom_panel_visible is True

        _close_window(window)

    def test_workspace_panel_preferences_restore_from_config(self, qapp, isolated_config):
        from ui_designer.ui.main_window import MainWindow
        from ui_designer.ui.project_workspace import ProjectWorkspacePanel

        isolated_config.workspace_left_panel = "widgets"
        isolated_config.workspace_state = {"project_workspace_view": ProjectWorkspacePanel.VIEW_THUMBNAILS}
        isolated_config.workspace_layout_version = 1

        window = MainWindow("")

        assert window._current_left_panel == "widgets"
        assert window._left_panel_stack.currentWidget() is window.widget_browser
        assert window._project_workspace.current_view() == ProjectWorkspacePanel.VIEW_THUMBNAILS
        assert window._project_workspace._view_chip.text() == "Thumbs"
        assert window._project_workspace._view_chip.isHidden() is False
        assert window._project_workspace._summary_label.text() == "0 pages. Active: none. Clean."
        assert window._project_workspace._meta_label.text() == "Startup: none"
        assert _left_panel_tab_tooltip(window, "widgets") == (
            "Currently showing Components panel. Current page: none. Insert target: unavailable."
        )
        assert _left_panel_tab_tooltip(window, "project") == (
            "Open Project panel. View: Thumbnails. Active page: none. Startup page: none."
        )
        assert window._workspace_nav_frame.toolTip() == "Workspace panel tabs. Current panel: Components."
        assert window._workspace_nav_frame.statusTip() == window._workspace_nav_frame.toolTip()
        assert window._workspace_nav_frame.accessibleName() == "Workspace panel tabs. Current panel: Components."
        assert window._left_panel_stack.toolTip() == (
            "Workspace panels: Components visible. Current page: none. Insert target: unavailable."
        )
        assert window._left_panel_stack.statusTip() == window._left_panel_stack.toolTip()
        assert window._left_panel_stack.accessibleName() == (
            "Workspace panels: Components visible. Current page: none. Insert target: unavailable."
        )
        assert window._left_shell.toolTip() == (
            "Workspace left shell: Components panel visible. Current page: none. Insert target: unavailable."
        )
        assert window._left_shell.statusTip() == window._left_shell.toolTip()
        assert window._left_shell.accessibleName() == (
            "Workspace left shell: Components panel visible. Current page: none. Insert target: unavailable."
        )
        _close_window(window)

    @pytest.mark.skip(reason="removed workspace indicator chips")
    def test_workspace_chips_use_sentence_case_and_humanized_counts(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow
        from ui_designer.ui.theme import app_theme_tokens

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "WorkspaceChipDemo"
        label = WidgetModel("label", name="title", x=8, y=8, width=80, height=20)
        project = _create_project_only_with_widgets(
            project_dir,
            "WorkspaceChipDemo",
            sdk_root,
            widgets=[label],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        monkeypatch.setattr(window.preview_panel, "is_python_preview_active", lambda: False)
        window._update_workspace_chips()
        window._clear_selection(sync_tree=False, sync_preview=False)
        tokens = app_theme_tokens()
        expected_control_height = max(int(tokens["h_tab_min"]) - int(tokens["space_xxs"]), 1)
        expected_command_width = int(tokens["h_tab_min"]) * 2

        assert window._workspace_context_label.text() == "WorkspaceChipDemo / main_page"
        assert window._workspace_context_label.toolTip() == (
            "Current workspace context: WorkspaceChipDemo. Current page: main_page. Project contains 1 page."
        )
        assert window._workspace_health_chip.text() == "Workspace Stable"
        assert window._workspace_health_chip.height() == 26
        assert window._workspace_health_chip.accessibleName() == "Workspace health indicator: Workspace Stable."
        assert window._workspace_health_chip.toolTip() == "Pages, inspector, and diagnostics are clear."
        assert window._workspace_health_chip.statusTip() == window._workspace_health_chip.toolTip()
        assert window._runtime_chip.text() == "Build Unavailable"
        assert window._runtime_chip.height() == 26
        assert window._runtime_chip.accessibleName() == "Preview runtime indicator: Build Unavailable."
        assert window._runtime_chip.toolTip() == "Open Debug Output. preview disabled for test."
        assert window._runtime_chip.statusTip() == window._runtime_chip.toolTip()
        assert window._central_stack.accessibleName() == "Main view stack: Editor workspace visible."
        assert window._sdk_status_label.accessibleName().startswith("SDK binding: SDK: ")
        assert window._sdk_status_label.toolTip() == str(sdk_root)
        assert window._sdk_status_label.statusTip() == window._sdk_status_label.toolTip()
        assert window._insert_widget_button.toolTip() == (
            "Open the Components panel and insert a component into root_group."
        )
        assert window._insert_widget_button.statusTip() == window._insert_widget_button.toolTip()
        assert window._insert_widget_button.accessibleName() == "Insert component target: root_group."
        assert window._insert_widget_button.objectName() == "workspace_insert_button"
        assert window._insert_widget_button.text() == "Add"
        assert window._insert_widget_button.width() == expected_command_width
        assert window._insert_widget_button.height() == expected_control_height
        assert window._insert_widget_button.icon().isNull() is True
        assert window._toolbar_more_button.icon().isNull() is True
        assert all(window._left_panel_stack.tabIcon(i).isNull() for i in range(window._left_panel_stack.count()))
        assert window._project_workspace._view_chip.isHidden() is False
        assert window._project_workspace._summary_label.text() == "1 page. Active: main_page. Clean."
        assert window._project_workspace._meta_label.text() == "Startup: main_page"
        assert window._workspace_nav_buttons["structure"].toolTip() == (
            "Open Structure panel. Current page: main_page. Selection: none."
        )
        assert window._workspace_nav_buttons["widgets"].toolTip() == (
            "Open Components panel. Current page: main_page. Insert target: root_group."
        )
        assert window._workspace_nav_buttons["assets"].toolTip() == "Open Assets panel. Current page: main_page."
        assert window._inspector_tabs.objectName() == "workspace_inspector_tabs"
        assert window._bottom_tabs.objectName() == "workspace_bottom_tabs"
        assert window._inspector_tabs.accessibleName() == (
            "Inspector tabs: Properties selected. 3 tabs. Current page: main_page. Selection: none."
        )
        assert window._bottom_tabs.accessibleName() == (
            "Bottom tools tabs: Diagnostics selected. 3 tabs. Current page: main_page. Panel hidden."
        )

        window._set_selection([label], primary=label, sync_tree=False, sync_preview=False)
        assert window._workspace_health_chip.text() == "1 Selected"
        assert window._workspace_health_chip.accessibleName() == "Workspace health indicator: 1 Selected."
        assert window._workspace_health_chip.toolTip() == "Open Structure to inspect the current selection."
        assert window._workspace_nav_buttons["structure"].toolTip() == (
            "Open Structure panel. Current page: main_page. Selection: title (label)."
        )
        assert window._workspace_nav_buttons["widgets"].toolTip() == (
            "Open Components panel. Current page: main_page. Insert target: root_group."
        )
        assert window._inspector_tabs.accessibleName() == (
            "Inspector tabs: Properties selected. 3 tabs. Current page: main_page. Selection: title (label)."
        )

        window._undo_manager.get_stack("main_page").push("<Page dirty='main' />")
        window._update_window_title()

        assert window._workspace_health_chip.text() == "Dirty 1"
        assert window._workspace_health_chip.accessibleName() == "Workspace health indicator: Dirty 1."
        assert window._workspace_health_chip.toolTip() == "Open History to review unsaved changes."
        assert window._project_workspace._summary_label.text() == "1 page. Active: main_page. 1 dirty page."

        monkeypatch.setattr(window.diagnostics_panel, "severity_counts", lambda: {"error": 1, "warning": 0, "info": 0})
        window._update_workspace_chips()

        assert window._workspace_health_chip.text() == "1 Error"
        assert window._workspace_health_chip.accessibleName() == "Workspace health indicator: 1 Error."
        assert window._workspace_health_chip.toolTip() == "Open Diagnostics. Current issues: 1 errors and 0 warnings."
        _close_window(window)

    @pytest.mark.skip(reason="removed workspace indicator chips")
    def test_workspace_chips_skip_no_op_toolbar_refreshes(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "WorkspaceChipNoOpDemo"
        label = WidgetModel("label", name="title", x=8, y=8, width=80, height=20)
        project = _create_project_only_with_widgets(
            project_dir,
            "WorkspaceChipNoOpDemo",
            sdk_root,
            widgets=[label],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)
        monkeypatch.setattr(window.preview_panel, "is_python_preview_active", lambda: False)
        monkeypatch.setattr(window.diagnostics_panel, "severity_counts", lambda: {"error": 0, "warning": 0, "info": 0})
        window._clear_selection(sync_tree=False, sync_preview=False)

        for chip in (window._workspace_health_chip, window._runtime_chip):
            if hasattr(chip, "_workspace_indicator_snapshot"):
                delattr(chip, "_workspace_indicator_snapshot")
        health_tooltip_calls = 0
        runtime_tooltip_calls = 0
        original_health_set_tooltip = window._workspace_health_chip.setToolTip
        original_runtime_set_tooltip = window._runtime_chip.setToolTip

        def counted_health_set_tooltip(text):
            nonlocal health_tooltip_calls
            health_tooltip_calls += 1
            return original_health_set_tooltip(text)

        def counted_runtime_set_tooltip(text):
            nonlocal runtime_tooltip_calls
            runtime_tooltip_calls += 1
            return original_runtime_set_tooltip(text)

        monkeypatch.setattr(window._workspace_health_chip, "setToolTip", counted_health_set_tooltip)
        monkeypatch.setattr(window._runtime_chip, "setToolTip", counted_runtime_set_tooltip)

        window._update_workspace_chips()
        assert health_tooltip_calls == 1
        assert runtime_tooltip_calls == 1

        health_tooltip_calls = 0
        runtime_tooltip_calls = 0
        window._update_workspace_chips()
        assert health_tooltip_calls == 0
        assert runtime_tooltip_calls == 0

        window._set_selection([label], primary=label, sync_tree=False, sync_preview=False)
        assert health_tooltip_calls == 1
        assert runtime_tooltip_calls == 0

        health_tooltip_calls = 0
        runtime_tooltip_calls = 0
        window._update_workspace_chips()
        assert health_tooltip_calls == 0
        assert runtime_tooltip_calls == 0
        _close_window(window)

    def test_welcome_view_and_sdk_status_label_expose_accessible_metadata(self, qapp, isolated_config):
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")

        assert window._central_stack.accessibleName() == "Main view stack: Welcome page visible."
        assert window._central_stack.toolTip() == window._central_stack.accessibleName()
        assert window._sdk_status_label.text() == "SDK: missing"
        assert window._sdk_status_label.toolTip() == "No SDK root configured"
        assert window._sdk_status_label.statusTip() == window._sdk_status_label.toolTip()
        assert window._sdk_status_label.accessibleName() == "SDK binding: SDK: missing."
        assert window._workspace_context_label.text() == "No project open"
        assert window._workspace_context_label.toolTip() == "Open or create a project to start editing."
        assert window._insert_widget_button.toolTip() == "Open or create a project to insert a component."
        assert window._insert_widget_button.statusTip() == window._insert_widget_button.toolTip()
        assert window._insert_widget_button.accessibleName() == "Insert component unavailable."
        _close_window(window)

    def test_welcome_page_resource_button_opens_resource_generator(self, qapp, isolated_config, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        triggered = []
        monkeypatch.setattr(
            MainWindow,
            "_open_resource_generator_window",
            lambda self: triggered.append("resource"),
        )

        window = MainWindow("")

        window._welcome_page._resource_generator_btn.click()

        assert triggered == ["resource"]
        _close_window(window)

    def test_sdk_status_label_skips_no_op_refreshes(self, qapp, isolated_config, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")
        if hasattr(window._sdk_status_label, "_sdk_status_label_snapshot"):
            delattr(window._sdk_status_label, "_sdk_status_label_snapshot")
        if hasattr(window._sdk_status_label, "_metadata_summary_snapshot"):
            delattr(window._sdk_status_label, "_metadata_summary_snapshot")

        tooltip_calls = 0
        original_set_tooltip = window._sdk_status_label.setToolTip

        def counted_set_tooltip(text):
            nonlocal tooltip_calls
            tooltip_calls += 1
            return original_set_tooltip(text)

        monkeypatch.setattr(window._sdk_status_label, "setToolTip", counted_set_tooltip)

        window._update_sdk_status_label()
        assert tooltip_calls == 1
        assert window._sdk_status_label.toolTip() == "No SDK root configured"

        tooltip_calls = 0
        window._update_sdk_status_label()
        assert tooltip_calls == 0

        monkeypatch.setattr(window, "_active_sdk_root", lambda: "C:\\sdk")
        window._update_sdk_status_label()
        assert tooltip_calls == 1
        assert window._sdk_status_label.toolTip() == "C:\\sdk"
        _close_window(window)

    def test_main_view_metadata_skips_no_op_refreshes(self, qapp, isolated_config, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")
        if hasattr(window._central_stack, "_metadata_summary_snapshot"):
            delattr(window._central_stack, "_metadata_summary_snapshot")

        tooltip_calls = 0
        original_set_tooltip = window._central_stack.setToolTip

        def counted_set_tooltip(text):
            nonlocal tooltip_calls
            tooltip_calls += 1
            return original_set_tooltip(text)

        monkeypatch.setattr(window._central_stack, "setToolTip", counted_set_tooltip)

        window._update_main_view_metadata()
        assert tooltip_calls == 1

        tooltip_calls = 0
        window._update_main_view_metadata()
        assert tooltip_calls == 0

        window._central_stack.setCurrentIndex(1)
        window._update_main_view_metadata()
        assert tooltip_calls == 1
        _close_window(window)

    def test_insert_widget_button_metadata_skips_no_op_refreshes(self, qapp, isolated_config, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        class _FakeWidget:
            def __init__(self, name, widget_type="group", parent=None):
                self.name = name
                self.widget_type = widget_type
                self.parent = parent

        window = MainWindow("")
        if hasattr(window._insert_widget_button, "_metadata_summary_snapshot"):
            delattr(window._insert_widget_button, "_metadata_summary_snapshot")

        tooltip_calls = 0
        original_set_tooltip = window._insert_widget_button.setToolTip

        def counted_set_tooltip(text):
            nonlocal tooltip_calls
            tooltip_calls += 1
            return original_set_tooltip(text)

        monkeypatch.setattr(window._insert_widget_button, "setToolTip", counted_set_tooltip)

        window._update_insert_widget_button_metadata()
        assert tooltip_calls == 1
        assert window._insert_widget_button.toolTip() == "Open or create a project to insert a component."

        tooltip_calls = 0
        window._update_insert_widget_button_metadata()
        assert tooltip_calls == 0

        window._current_page = object()
        root_group = _FakeWidget("root_group")
        window._update_insert_widget_button_metadata(root_group)
        assert tooltip_calls == 1
        assert window._insert_widget_button.toolTip() == "Open the Components panel and insert a component into root_group."
        assert window._insert_widget_button.accessibleName() == "Insert component target: root_group."
        _close_window(window)

    def test_arrange_and_structure_menu_icons_use_extra_small_scale(self, qapp, isolated_config, monkeypatch):
        from PyQt5.QtGui import QIcon
        import ui_designer.ui.main_window as main_window_module
        from ui_designer.ui.main_window import MainWindow

        captured = []

        def _capture_make_icon(icon_key, size=None, mode=None):
            captured.append((icon_key, size, mode))
            return QIcon()

        menu_tokens = dict(main_window_module.app_theme_tokens())
        menu_tokens["icon_xs"] = 11
        monkeypatch.setattr(main_window_module, "make_icon", _capture_make_icon)
        monkeypatch.setattr(main_window_module, "app_theme_tokens", lambda *args, **kwargs: menu_tokens)

        window = MainWindow("")
        expected_size = main_window_module._menu_action_icon_size()
        expected_keys = {
            "layout.align.left",
            "layout.align.right",
            "layout.align.top",
            "layout.align.bottom",
            "layout.align.center",
            "layout.align.middle",
            "layout.distribute.h",
            "layout.distribute.v",
            "canvas.layer.top",
            "canvas.layer.bottom",
            "edit.lock",
            "edit.hidden",
            "nav.page_group",
            "nav.component_library",
            "canvas.layer.up",
            "canvas.layer.down",
        }

        assert expected_keys.issubset({icon_key for icon_key, _, _ in captured})
        for icon_key in expected_keys:
            assert (icon_key, expected_size, None) in captured

        _close_window(window)

    def test_toolbar_and_top_level_actions_expose_dynamic_hints(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        import ui_designer.ui.main_window as main_window_module
        from ui_designer.ui.main_window import MainWindow
        from ui_designer.ui.theme import app_theme_tokens

        window = MainWindow("")
        mode_host = window._mode_buttons["design"].parentWidget()
        separator = window._toolbar_host.findChild(type(window._toolbar_header), "toolbar_host_separator")
        tokens = app_theme_tokens()
        expected_control_height = max(int(tokens["h_tab_min"]) - int(tokens["space_xxs"]), 1)
        expected_command_width = int(tokens["h_tab_min"]) * 2
        expected_toolbar_height = expected_control_height + (int(tokens["space_toolbar_separator"]) * 2)

        assert window._toolbar.accessibleName() == "Main toolbar: insert, save, edit, and preview commands."
        assert window._toolbar.toolTip() == window._toolbar.accessibleName()
        assert window._toolbar_host.accessibleName() == "Workspace command bar with insert, save, build, mode, context, and runtime indicators."
        assert window._toolbar_host.statusTip() == window._toolbar_host.toolTip()
        assert window._toolbar_command_row_layout.spacing() == 1
        assert mode_host.layout().spacing() == 1
        assert window._toolbar.height() == expected_toolbar_height
        assert window._toolbar.widgetForAction(window._save_action).height() == expected_control_height
        assert window._mode_buttons["design"].width() == expected_command_width
        assert window._mode_buttons["design"].height() == expected_control_height
        assert separator.minimumHeight() == expected_control_height
        assert separator.maximumHeight() == expected_control_height
        assert window._workspace_context_label.text() == "No project open"
        assert all(
            action.icon().isNull()
            for action in (
                window._save_action,
                window._undo_action,
                window._redo_action,
                window._copy_action,
                window._paste_action,
                window._compile_action,
                window._stop_action,
            )
        )
        assert window._show_grid_action.icon().isNull() is True
        assert window._grid_menu.icon().isNull() is True
        assert window._insert_widget_button.icon().isNull() is True
        assert window._toolbar_more_button.icon().isNull() is True
        assert all(window._left_panel_stack.tabIcon(i).isNull() for i in range(window._left_panel_stack.count()))
        assert all(button.icon().isNull() for button in window._mode_buttons.values())
        assert window._save_action.toolTip() == "Save the current project (Ctrl+S). Unavailable: open a project first."
        assert window._save_action.statusTip() == window._save_action.toolTip()
        assert window._save_action.isEnabled() is False
        assert window._undo_action.toolTip() == "Undo the last change on the current page (Ctrl+Z). Unavailable: open a page first."
        assert window._redo_action.toolTip() == "Redo the next change on the current page (Ctrl+Shift+Z). Unavailable: open a page first."
        assert window._copy_action.toolTip() == "Copy the current selection (Ctrl+C). Unavailable: select at least 1 widget."
        assert window._paste_action.toolTip() == "Paste clipboard widgets into the current page (Ctrl+V). Unavailable: open a page first."
        assert window._compile_action.toolTip() == (
            "Compile the current project and run the preview (F5). "
            "Project: none. SDK: invalid. Preview: stopped. Unavailable: open a project first."
        )
        assert window._stop_action.toolTip() == (
            "Stop the running preview executable. Project: none. Preview: stopped. Unavailable: preview is not running."
        )
        monkeypatch.setattr(main_window_module, "apply_theme", lambda *args, **kwargs: None)
        window._set_theme("light")
        window._set_ui_density("roomy")
        assert all(
            action.icon().isNull()
            for action in (
                window._save_action,
                window._undo_action,
                window._redo_action,
                window._copy_action,
                window._paste_action,
                window._compile_action,
                window._stop_action,
                window._show_grid_action,
            )
        )
        assert window._grid_menu.icon().isNull() is True
        assert window._insert_widget_button.icon().isNull() is True
        assert window._toolbar_more_button.icon().isNull() is True
        assert all(window._left_panel_stack.tabIcon(i).isNull() for i in range(window._left_panel_stack.count()))
        assert all(button.icon().isNull() for button in window._mode_buttons.values())

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "ToolbarHintDemo"
        label = WidgetModel("label", name="title", x=8, y=8, width=80, height=20)
        project = _create_project_only_with_widgets(
            project_dir,
            "ToolbarHintDemo",
            sdk_root,
            widgets=[label],
        )

        _disable_window_compile(window, _DisabledCompiler)

        _open_project_window(window, project, project_dir, sdk_root)

        assert window._workspace_context_label.text() == "ToolbarHintDemo / main_page"
        assert window._workspace_context_label.toolTip() == (
            "Current workspace context: ToolbarHintDemo. Current page: main_page. Project contains 1 page."
        )
        assert window._save_action.toolTip() == (
            "Save the current project (Ctrl+S). "
            f"Unsaved pages: none. Target: {window._project_dir}."
        )
        assert window._save_action.statusTip() == window._save_action.toolTip()
        assert window._save_action.isEnabled() is True
        assert window._compile_action.toolTip() == (
            "Compile the current project and run the preview (F5). "
            "Project: open. SDK: valid. Preview: editing only. Unavailable: preview disabled for test."
        )
        assert window._compile_action.statusTip() == window._compile_action.toolTip()
        assert window._stop_action.toolTip() == (
            "Stop the running preview executable. Project: open. Preview: stopped. Unavailable: preview is not running."
        )
        assert window._stop_action.statusTip() == window._stop_action.toolTip()
        assert window._undo_action.toolTip() == (
            "Undo the last change on the current page (Ctrl+Z). Unavailable: no earlier changes are available on this page."
        )
        assert window._redo_action.toolTip() == (
            "Redo the next change on the current page (Ctrl+Shift+Z). Unavailable: no later changes are available on this page."
        )
        assert window._copy_action.toolTip() == "Copy the current selection (Ctrl+C). Unavailable: select at least 1 widget."
        assert window._paste_action.toolTip() == "Paste clipboard widgets into the current page (Ctrl+V). Unavailable: copy or cut widgets first."

        window._set_selection([label], primary=label, sync_tree=False, sync_preview=False)

        assert window._copy_action.toolTip() == "Copy the current selection (Ctrl+C)."
        assert window._copy_action.statusTip() == window._copy_action.toolTip()

        window._copy_selection()

        assert window._paste_action.toolTip() == "Paste clipboard widgets into the current page (Ctrl+V)."
        assert window._paste_action.statusTip() == window._paste_action.toolTip()

        class _RunningCompiler:
            def can_build(self):
                return True

            def is_preview_running(self):
                return True

            def stop_exe(self):
                return None

            def cleanup(self):
                return None

        window.compiler = _RunningCompiler()
        window._update_compile_availability()

        assert window._compile_action.toolTip() == (
            "Compile the current project and run the preview (F5). Project: open. SDK: valid. Preview: running."
        )
        assert window._compile_action.statusTip() == window._compile_action.toolTip()
        assert window._stop_action.toolTip() == (
            "Stop the running preview executable. Project: open. Preview: running."
        )
        assert window._stop_action.statusTip() == window._stop_action.toolTip()
        _close_window(window)

    def test_toolbar_summaries_skip_no_op_refreshes(self, qapp, isolated_config, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")
        for widget in (window._toolbar, window._toolbar_host):
            if hasattr(widget, "_metadata_summary_snapshot"):
                delattr(widget, "_metadata_summary_snapshot")

        tooltip_calls = 0
        original_set_tooltip = window._toolbar.setToolTip

        def counted_set_tooltip(text):
            nonlocal tooltip_calls
            tooltip_calls += 1
            return original_set_tooltip(text)

        monkeypatch.setattr(window._toolbar, "setToolTip", counted_set_tooltip)

        window._update_toolbar_action_metadata()
        assert tooltip_calls == 1

        tooltip_calls = 0
        window._update_toolbar_action_metadata()
        assert tooltip_calls == 0
        _close_window(window)

    def test_save_action_exposes_dirty_page_count(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "SaveHintDemo"
        project = _create_project(project_dir, "SaveHintDemo", sdk_root)

        window = MainWindow("")
        _disable_window_compile(window, _DisabledCompiler)
        _open_project_window(window, project, project_dir, sdk_root)

        stack = window._undo_manager.get_stack(window._current_page.name)
        stack.push("state 1", label="initial")
        stack.mark_saved()
        stack.push("state 2", label="changed")
        window._update_toolbar_action_metadata()

        assert window._save_action.toolTip() == (
            "Save the current project (Ctrl+S). "
            f"Unsaved pages: 1 page. Target: {window._project_dir}."
        )
        assert window._save_action.statusTip() == window._save_action.toolTip()
        assert window._save_action.isEnabled() is True
        assert window._quit_action.toolTip() == "Quit EmbeddedGUI Designer (Ctrl+Q). Project: open. Unsaved pages: 1 page."
        assert window._quit_action.statusTip() == window._quit_action.toolTip()
        _close_window(window)

    def test_save_action_exposes_project_change_state(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "SaveProjectChangeHintDemo"
        project = _create_project(
            project_dir,
            "SaveProjectChangeHintDemo",
            sdk_root,
            pages=["main_page", "detail_page"],
        )

        window = MainWindow("")
        _disable_window_compile(window, _DisabledCompiler)
        _open_project_window(window, project, project_dir, sdk_root)

        window._on_startup_changed("detail_page")

        assert window._undo_manager.is_any_dirty() is False
        assert window._save_action.toolTip() == (
            "Save the current project (Ctrl+S). "
            f"Unsaved changes: project changes (startup page). Target: {window._project_dir}."
        )
        assert window._save_action.statusTip() == window._save_action.toolTip()
        _close_window(window)

    def test_editor_mode_buttons_track_current_workspace_mode(self, qapp, isolated_config):
        from ui_designer.ui.editor_tabs import MODE_CODE, MODE_DESIGN, MODE_SPLIT
        from ui_designer.ui.main_window import MainWindow
        from ui_designer.ui.theme import app_theme_tokens

        window = MainWindow("")
        tokens = app_theme_tokens()
        expected_control_height = max(int(tokens["h_tab_min"]) - int(tokens["space_xxs"]), 1)
        expected_command_width = int(tokens["h_tab_min"]) * 2

        assert window._mode_buttons[MODE_DESIGN].toolTip() == "Currently showing Design mode."
        assert window._mode_buttons[MODE_DESIGN].width() == expected_command_width
        assert window._mode_buttons[MODE_DESIGN].height() == expected_control_height
        assert window._mode_buttons[MODE_DESIGN].accessibleName() == "Editor mode button: Design. Current mode."
        assert window._mode_buttons[MODE_CODE].toolTip() == "Switch the workspace editor to Code mode."
        assert window._mode_buttons[MODE_CODE].statusTip() == window._mode_buttons[MODE_CODE].toolTip()
        assert window._mode_buttons[MODE_SPLIT].accessibleName() == "Editor mode button: Split."
        assert window.editor_tabs._summary_label.isHidden() is True
        assert window._editor_container.accessibleName() == (
            "Editor workspace. Left panel: Project. Current page: none. Mode: Design. Bottom tools hidden."
        )
        assert window._center_shell.accessibleName() == "Workspace center shell. Current page: none. Mode: Design."
        assert window._top_splitter.accessibleName() == (
            "Workspace columns. Left panel: Project. Editor mode: Design. Inspector section: Properties. Current page: none."
        )
        assert window._workspace_splitter.accessibleName() == (
            "Workspace rows. Editor area visible. Bottom tools hidden. Current section: Diagnostics. Current page: none."
        )
        assert window._bottom_header.accessibleName() == "Bottom tools header. Current section: Diagnostics. Panel hidden."
        assert window._bottom_shell.accessibleName() == (
            "Workspace bottom shell. Current section: Diagnostics. Panel hidden. Current page: none."
        )

        window.editor_tabs.set_mode(MODE_CODE)

        assert window._mode_buttons[MODE_CODE].toolTip() == "Currently showing Code mode."
        assert window._mode_buttons[MODE_CODE].accessibleName() == "Editor mode button: Code. Current mode."
        assert window._mode_buttons[MODE_DESIGN].toolTip() == "Switch the workspace editor to Design mode."
        assert window._editor_container.toolTip() == (
            "Editor workspace. Left panel: Project. Current page: none. Mode: Code. Bottom tools hidden."
        )
        assert window._center_shell.toolTip() == "Workspace center shell. Current page: none. Mode: Code."
        assert window._top_splitter.toolTip() == (
            "Workspace columns. Left panel: Project. Editor mode: Code. Inspector section: Properties. Current page: none."
        )

        window.editor_tabs.set_mode(MODE_SPLIT)

        assert window._mode_buttons[MODE_SPLIT].toolTip() == "Currently showing Split mode."
        assert window._mode_buttons[MODE_SPLIT].accessibleName() == "Editor mode button: Split. Current mode."
        assert window._mode_buttons[MODE_CODE].toolTip() == "Switch the workspace editor to Code mode."
        assert window._editor_container.accessibleName() == (
            "Editor workspace. Left panel: Project. Current page: none. Mode: Split. Bottom tools hidden."
        )
        assert window._center_shell.accessibleName() == "Workspace center shell. Current page: none. Mode: Split."
        assert window._top_splitter.accessibleName() == (
            "Workspace columns. Left panel: Project. Editor mode: Split. Inspector section: Properties. Current page: none."
        )
        _close_window(window)

    def test_workspace_command_surface_metadata_tracks_context_and_mode(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.editor_tabs import MODE_CODE
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "CommandSurfaceDemo"
        project = _create_project(project_dir, "CommandSurfaceDemo", sdk_root)

        window = MainWindow("")

        default_summary = "Open a project to enable insert, save, preview, and mode controls."
        assert window._toolbar_header.accessibleName() == (
            "Workspace command header. Engineering summary, current context, and command posture."
        )
        assert window._toolbar_eyebrow_label.accessibleName() == "Engineering workspace command surface."
        assert window._toolbar_title_label.accessibleName() == (
            "Design command center for insert, save, preview, and mode controls."
        )
        assert window._toolbar_meta_label.text() == default_summary
        assert window._toolbar_meta_label.toolTip() == default_summary
        assert window._toolbar_meta_label.accessibleName() == default_summary
        assert window._workspace_context_eyebrow.accessibleName() == "Current workspace context card."
        assert window._workspace_context_card.toolTip() == "Open or create a project to start editing."
        assert window._workspace_context_card.accessibleName() == "Workspace context card: No project open."

        _disable_window_compile(window, _DisabledCompiler)
        _open_project_window(window, project, project_dir, sdk_root)

        design_summary = (
            "Design mode. Project panel. Current page: main_page. "
            "Use commands to insert, save, build, and check runtime."
        )
        assert window._toolbar_meta_label.text() == design_summary
        assert window._toolbar_meta_label.statusTip() == design_summary
        assert window._workspace_context_card.toolTip() == (
            "Current workspace context: CommandSurfaceDemo. Current page: main_page. Project contains 1 page."
        )
        assert window._workspace_context_card.accessibleName() == "Workspace context card: CommandSurfaceDemo / main_page."

        window._select_left_panel("widgets")
        window.editor_tabs.set_mode(MODE_CODE)

        code_summary = (
            "Code mode. Components panel. Current page: main_page. "
            "Use commands to insert, save, build, and check runtime."
        )
        assert window._toolbar_meta_label.text() == code_summary
        assert window._toolbar_meta_label.toolTip() == code_summary
        assert window._toolbar_meta_label.accessibleName() == code_summary
        assert window._workspace_context_card.accessibleName() == "Workspace context card: CommandSurfaceDemo / main_page."
        _close_window(window)

    def test_workspace_layout_metadata_skips_no_op_refreshes(self, qapp, isolated_config, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")
        for widget in (
            window._editor_container,
            window._center_shell,
            window._top_splitter,
            window._workspace_splitter,
            window._bottom_header,
            window._bottom_shell,
        ):
            if hasattr(widget, "_metadata_summary_snapshot"):
                delattr(widget, "_metadata_summary_snapshot")

        tooltip_calls = 0
        original_set_tooltip = window._editor_container.setToolTip

        def counted_set_tooltip(text):
            nonlocal tooltip_calls
            tooltip_calls += 1
            return original_set_tooltip(text)

        monkeypatch.setattr(window._editor_container, "setToolTip", counted_set_tooltip)

        window._update_workspace_layout_metadata()
        assert tooltip_calls == 1

        tooltip_calls = 0
        window._update_workspace_layout_metadata()
        assert tooltip_calls == 0

        window._bottom_panel_visible = True
        window._update_workspace_layout_metadata()
        assert tooltip_calls == 1
        _close_window(window)

    def test_editor_mode_metadata_skips_no_op_refreshes(self, qapp, isolated_config, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")
        for button in window._mode_buttons.values():
            if hasattr(button, "_metadata_summary_snapshot"):
                delattr(button, "_metadata_summary_snapshot")

        tooltip_calls = 0
        original_set_tooltip = window._mode_buttons["design"].setToolTip

        def counted_set_tooltip(text):
            nonlocal tooltip_calls
            tooltip_calls += 1
            return original_set_tooltip(text)

        monkeypatch.setattr(window._mode_buttons["design"], "setToolTip", counted_set_tooltip)

        window._update_editor_mode_button_metadata("design")
        assert tooltip_calls == 1

        tooltip_calls = 0
        window._update_editor_mode_button_metadata("design")
        assert tooltip_calls == 0

        window._update_editor_mode_button_metadata("code")
        assert tooltip_calls == 1
        _close_window(window)

    def test_workspace_left_tabs_and_bottom_toggle_buttons_expose_current_state(self, qapp, isolated_config):
        from ui_designer.ui.main_window import MainWindow
        from ui_designer.ui.theme import app_theme_tokens

        window = MainWindow("")
        tokens = app_theme_tokens()
        expected_control_height = max(int(tokens["h_tab_min"]) - int(tokens["space_xxs"]), 1)

        assert window._left_panel_stack.tabText(_left_panel_tab_index(window, "project")) == "Pages"
        assert window._left_panel_stack.tabText(_left_panel_tab_index(window, "structure")) == "Tree"
        assert window._left_panel_stack.tabText(_left_panel_tab_index(window, "widgets")) == "Add"
        assert window._left_panel_stack.tabText(_left_panel_tab_index(window, "assets")) == "Assets"
        assert window._workspace_nav_frame.height() >= 24
        assert window._bottom_toggle_button.height() == expected_control_height
        assert window.project_dock.minimumWidth() == 256
        assert window._left_panel_stack.minimumWidth() == 256
        assert window._left_shell.minimumWidth() == 256
        assert window._workspace_nav_frame.parentWidget() is window._left_panel_stack

        assert _left_panel_tab_tooltip(window, "project") == (
            "Currently showing Project panel. View: List view. Active page: none. Startup page: none."
        )
        assert _left_panel_tab_whats_this(window, "project") == (
            "Workspace panel tab: Project. Current panel. View: List view. Active page: none. Startup page: none."
        )
        assert _left_panel_tab_tooltip(window, "structure") == (
            "Open Structure panel. Current page: none. Selection: none."
        )
        assert _left_panel_tab_tooltip(window, "widgets") == (
            "Open Components panel. Current page: none. Insert target: unavailable."
        )
        assert _left_panel_tab_tooltip(window, "assets") == "Open Assets panel. Current page: none."
        assert _left_panel_tab_whats_this(window, "widgets") == (
            "Workspace panel tab: Components. Current page: none. Insert target: unavailable."
        )
        assert window._workspace_nav_frame.toolTip() == "Workspace panel tabs. Current panel: Project."
        assert window._workspace_nav_frame.statusTip() == window._workspace_nav_frame.toolTip()
        assert window._workspace_nav_frame.accessibleName() == "Workspace panel tabs. Current panel: Project."
        assert window._left_panel_stack.toolTip() == (
            "Workspace panels: Project visible. View: List view. Active page: none. Startup page: none."
        )
        assert window._left_panel_stack.statusTip() == window._left_panel_stack.toolTip()
        assert window._left_panel_stack.accessibleName() == (
            "Workspace panels: Project visible. View: List view. Active page: none. Startup page: none."
        )
        assert window._left_shell.toolTip() == (
            "Workspace left shell: Project panel visible. View: List view. Active page: none. Startup page: none."
        )
        assert window._left_shell.statusTip() == window._left_shell.toolTip()
        assert window._left_shell.accessibleName() == (
            "Workspace left shell: Project panel visible. View: List view. Active page: none. Startup page: none."
        )
        assert window._editor_container.toolTip() == (
            "Editor workspace. Left panel: Project. Current page: none. Mode: Design. Bottom tools hidden."
        )
        assert window._center_shell.toolTip() == "Workspace center shell. Current page: none. Mode: Design."
        assert window._top_splitter.toolTip() == (
            "Workspace columns. Left panel: Project. Editor mode: Design. Inspector section: Properties. Current page: none."
        )
        assert window._workspace_splitter.toolTip() == (
            "Workspace rows. Editor area visible. Bottom tools hidden. Current section: Diagnostics. Current page: none."
        )
        assert window._bottom_header.toolTip() == "Bottom tools header. Current section: Diagnostics. Panel hidden."
        assert window._bottom_shell.toolTip() == (
            "Workspace bottom shell. Current section: Diagnostics. Panel hidden. Current page: none."
        )
        assert window._bottom_toggle_button.objectName() == "workspace_bottom_toggle_button"
        assert window._bottom_toggle_button.text() == "Show"
        assert window._bottom_toggle_button.toolTip() == "Show the bottom tools panel."
        assert window._bottom_toggle_button.accessibleName() == "Bottom tools toggle: hidden. Activate to show."

        window._select_left_panel("widgets")

        assert _left_panel_tab_tooltip(window, "widgets") == (
            "Currently showing Components panel. Current page: none. Insert target: unavailable."
        )
        assert _left_panel_tab_whats_this(window, "widgets") == (
            "Workspace panel tab: Components. Current panel. Current page: none. Insert target: unavailable."
        )
        assert _left_panel_tab_tooltip(window, "project") == (
            "Open Project panel. View: List view. Active page: none. Startup page: none."
        )
        assert window._workspace_nav_frame.accessibleName() == "Workspace panel tabs. Current panel: Components."
        assert window._left_panel_stack.accessibleName() == (
            "Workspace panels: Components visible. Current page: none. Insert target: unavailable."
        )
        assert window._left_shell.accessibleName() == (
            "Workspace left shell: Components panel visible. Current page: none. Insert target: unavailable."
        )
        assert window._editor_container.accessibleName() == (
            "Editor workspace. Left panel: Components. Current page: none. Mode: Design. Bottom tools hidden."
        )
        assert window._center_shell.accessibleName() == "Workspace center shell. Current page: none. Mode: Design."
        assert window._top_splitter.accessibleName() == (
            "Workspace columns. Left panel: Components. Editor mode: Design. Inspector section: Properties. Current page: none."
        )

        window._set_bottom_panel_visible(True)

        assert window._bottom_toggle_button.text() == "Hide"
        assert window._bottom_toggle_button.toolTip() == "Hide the bottom tools panel."
        assert window._bottom_toggle_button.statusTip() == window._bottom_toggle_button.toolTip()
        assert window._bottom_toggle_button.accessibleName() == "Bottom tools toggle: shown. Activate to hide."
        assert window._editor_container.accessibleName() == (
            "Editor workspace. Left panel: Components. Current page: none. Mode: Design. Bottom tools visible."
        )
        assert window._workspace_splitter.accessibleName() == (
            "Workspace rows. Editor area visible. Bottom tools visible. Current section: Diagnostics. Current page: none."
        )
        assert window._bottom_header.accessibleName() == "Bottom tools header. Current section: Diagnostics. Panel visible."
        assert window._bottom_shell.accessibleName() == (
            "Workspace bottom shell. Current section: Diagnostics. Panel visible. Current page: none."
        )
        _close_window(window)

    def test_workspace_command_metrics_follow_runtime_tokens(self, qapp, isolated_config, monkeypatch):
        import ui_designer.ui.main_window as main_window_module
        from ui_designer.ui.main_window import MainWindow

        metric_tokens = dict(main_window_module.app_theme_tokens())
        metric_tokens["h_tab_min"] = 26
        metric_tokens["space_xxs"] = 3
        metric_tokens["space_md"] = 11
        metric_tokens["space_toolbar_separator"] = 2
        monkeypatch.setattr(main_window_module, "app_theme_tokens", lambda *args, **kwargs: metric_tokens)

        window = MainWindow("")
        separator = window._toolbar_host.findChild(type(window._toolbar_header), "toolbar_host_separator")

        assert window._insert_widget_button.width() == 52
        assert window._insert_widget_button.height() == 23
        assert window.page_tab_bar.height() == 37
        assert window._toolbar.height() == 27
        assert window._toolbar.widgetForAction(window._save_action).height() == 23
        assert window._mode_buttons["design"].width() == 52
        assert window._mode_buttons["design"].height() == 23
        assert window._bottom_toggle_button.width() == 52
        assert window._bottom_toggle_button.height() == 23
        assert separator.minimumHeight() == 23
        assert separator.maximumHeight() == 23

        _close_window(window)

    def test_bottom_toggle_metadata_skips_no_op_refreshes(self, qapp, isolated_config, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")
        if hasattr(window._bottom_toggle_button, "_metadata_summary_snapshot"):
            delattr(window._bottom_toggle_button, "_metadata_summary_snapshot")

        tooltip_calls = 0
        original_set_tooltip = window._bottom_toggle_button.setToolTip

        def counted_set_tooltip(text):
            nonlocal tooltip_calls
            tooltip_calls += 1
            return original_set_tooltip(text)

        monkeypatch.setattr(window._bottom_toggle_button, "setToolTip", counted_set_tooltip)

        window._update_bottom_toggle_button_metadata()
        assert tooltip_calls == 1
        assert window._bottom_toggle_button.toolTip() == "Show the bottom tools panel."

        tooltip_calls = 0
        window._update_bottom_toggle_button_metadata()
        assert tooltip_calls == 0

        window._bottom_panel_visible = True
        window._update_bottom_toggle_button_metadata()
        assert tooltip_calls == 1
        assert window._bottom_toggle_button.toolTip() == "Hide the bottom tools panel."
        assert window._bottom_toggle_button.accessibleName() == "Bottom tools toggle: shown. Activate to hide."
        _close_window(window)

    def test_workspace_left_tab_metadata_skips_no_op_refreshes(self, qapp, isolated_config, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")
        for widget in (
            window._workspace_nav_frame,
            window._left_panel_stack,
            window._left_shell,
        ):
            if hasattr(widget, "_metadata_summary_snapshot"):
                delattr(widget, "_metadata_summary_snapshot")

        project_tooltip_calls = 0
        stack_tooltip_calls = 0
        project_index = _left_panel_tab_index(window, "project")
        window._left_panel_stack.setTabToolTip(project_index, "")
        original_set_tab_tooltip = window._left_panel_stack.setTabToolTip
        original_stack_set_tooltip = window._left_panel_stack.setToolTip

        def counted_set_tab_tooltip(index, text):
            nonlocal project_tooltip_calls
            if index == project_index:
                project_tooltip_calls += 1
            return original_set_tab_tooltip(index, text)

        def counted_stack_set_tooltip(text):
            nonlocal stack_tooltip_calls
            stack_tooltip_calls += 1
            return original_stack_set_tooltip(text)

        monkeypatch.setattr(window._left_panel_stack, "setTabToolTip", counted_set_tab_tooltip)
        monkeypatch.setattr(window._left_panel_stack, "setToolTip", counted_stack_set_tooltip)

        window._update_workspace_nav_button_metadata("project")
        assert project_tooltip_calls == 1
        assert stack_tooltip_calls == 1

        project_tooltip_calls = 0
        stack_tooltip_calls = 0
        window._update_workspace_nav_button_metadata("project")
        assert project_tooltip_calls == 0
        assert stack_tooltip_calls == 0

        window._update_workspace_nav_button_metadata("widgets")
        assert project_tooltip_calls == 1
        assert stack_tooltip_calls == 1
        _close_window(window)

    def test_workspace_tab_widgets_expose_current_section_metadata(self, qapp, isolated_config):
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")

        assert window._inspector_tabs.accessibleName() == (
            "Inspector tabs: Properties selected. 3 tabs. Current page: none. Selection: none."
        )
        assert window._inspector_tabs.minimumWidth() == 264
        assert window._inspector_tabs.documentMode() is True
        assert all(window._inspector_tabs.tabBar().tabIcon(i).isNull() for i in range(window._inspector_tabs.count()))
        assert window._inspector_tabs.tabBar().drawBase() is False
        assert window._inspector_tabs.toolTip() == (
            "Inspector tabs. Current section: Properties. Current page: none. Selection: none."
        )
        assert window._page_tools_scroll.accessibleName() == (
            "Page inspector: Fields and Timers sections. Scroll focus: Fields. Current page: none."
        )
        assert window._page_tools_scroll.toolTip() == (
            "Page inspector (Fields and Timers). Scroll focus: Fields. Current page: none."
        )
        assert window._bottom_tabs.accessibleName() == (
            "Bottom tools tabs: Diagnostics selected. 3 tabs. Current page: none. Panel hidden."
        )
        assert window._bottom_tabs.documentMode() is True
        assert all(window._bottom_tabs.tabBar().tabIcon(i).isNull() for i in range(window._bottom_tabs.count()))
        assert window._bottom_tabs.tabBar().drawBase() is False
        assert window._bottom_tabs.toolTip() == (
            "Bottom tools tabs. Current section: Diagnostics. Current page: none. Panel hidden."
        )

        window._show_inspector_tab("page", inner_section="timers")
        window._show_bottom_panel("History")

        assert window._inspector_tabs.accessibleName() == (
            "Inspector tabs: Page selected. 3 tabs. Current page: none. Selection: none."
        )
        assert window._page_tools_scroll.accessibleName() == (
            "Page inspector: Fields and Timers sections. Scroll focus: Timers. Current page: none."
        )
        assert window._bottom_tabs.accessibleName() == (
            "Bottom tools tabs: History selected. 3 tabs. Current page: none. Panel visible."
        )
        assert window._bottom_tabs.statusTip() == window._bottom_tabs.toolTip()
        _close_window(window)

    def test_workspace_tab_metadata_skips_no_op_refreshes(self, qapp, isolated_config, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")
        for widget in (
            window._inspector_tabs,
            window._page_tools_scroll,
            window._bottom_tabs,
        ):
            if hasattr(widget, "_metadata_summary_snapshot"):
                delattr(widget, "_metadata_summary_snapshot")

        tooltip_calls = 0
        original_set_tooltip = window._bottom_tabs.setToolTip

        def counted_set_tooltip(text):
            nonlocal tooltip_calls
            tooltip_calls += 1
            return original_set_tooltip(text)

        monkeypatch.setattr(window._bottom_tabs, "setToolTip", counted_set_tooltip)

        window._update_workspace_tab_metadata()
        assert tooltip_calls == 1

        tooltip_calls = 0
        window._update_workspace_tab_metadata()
        assert tooltip_calls == 0

        window._bottom_panel_visible = True
        window._update_workspace_tab_metadata()
        assert tooltip_calls == 1
        _close_window(window)

    def test_focus_canvas_toggle_hides_side_panels_and_restores_on_open_actions(self, qapp, isolated_config):
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")
        assert window._focus_canvas_enabled is False
        assert window._left_shell.isHidden() is False
        assert window._inspector_tabs.isHidden() is False

        window._focus_canvas_action.trigger()
        assert window._focus_canvas_enabled is True
        assert window._focus_canvas_action.isChecked() is True
        assert window._left_shell.isHidden() is True
        assert window._inspector_tabs.isHidden() is True
        assert window._bottom_panel_visible is False

        window._show_inspector_tab("properties")
        assert window._focus_canvas_enabled is False
        assert window._left_shell.isHidden() is False
        assert window._inspector_tabs.isHidden() is False
        _close_window(window)

    def test_widget_browser_insert_updates_selection_and_recent_history(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "WidgetBrowserInsertDemo"
        container = WidgetModel("group", name="container", x=0, y=0, width=200, height=200)
        project = _create_project_only_with_widgets(
            project_dir,
            "WidgetBrowserInsertDemo",
            sdk_root,
            widgets=[container],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([container], primary=container, sync_tree=True, sync_preview=True)

        window._show_widget_browser_for_parent(container)
        window._show_inspector_tab("animations")
        window._insert_widget_from_browser("button")

        assert window._current_left_panel == "widgets"
        assert window._inspector_tabs.currentIndex() == 0
        assert len(container.children) == 1
        inserted = container.children[0]
        assert inserted.widget_type == "button"
        assert window._selection_state.primary is inserted
        assert isolated_config.widget_browser_recent[0] == "button"
        _close_window(window)

    def test_widget_browser_reveal_selects_first_matching_widget_in_structure(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "WidgetBrowserRevealDemo"
        label = WidgetModel("label", name="title", x=4, y=4, width=60, height=20)
        button = WidgetModel("button", name="cta", x=10, y=30, width=80, height=24)
        project = _create_project_only_with_widgets(
            project_dir,
            "WidgetBrowserRevealDemo",
            sdk_root,
            widgets=[label, button],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        _open_project_window(window, project, project_dir, sdk_root)

        window._show_inspector_tab("animations")
        window._reveal_widget_type_in_structure("button")

        assert window._current_left_panel == "structure"
        assert window._inspector_tabs.currentIndex() == 0
        assert window._selection_state.primary is button
        assert window.widget_tree._get_selected_widget() is button
        assert "Revealed Button in structure." == window.statusBar().currentMessage()
        _close_window(window)

    def test_widget_browser_highlights_selected_widget_type(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "WidgetBrowserSelectionDemo"
        label = WidgetModel("label", name="title", x=4, y=4, width=60, height=20)
        project = _create_project_only_with_widgets(
            project_dir,
            "WidgetBrowserSelectionDemo",
            sdk_root,
            widgets=[label],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        _open_project_window(window, project, project_dir, sdk_root)

        window._set_selection([label], primary=label, sync_tree=True, sync_preview=True)

        assert window.widget_browser._selected_type == "label"
        _close_window(window)

    def test_widget_type_drop_clamps_to_project_screen_bounds(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        def _setup_project(project):
            project.screen_width = 240
            project.screen_height = 320

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "WidgetDropClampDemo"
        project = _create_project(
            project_dir,
            "WidgetDropClampDemo",
            sdk_root,
            project_customizer=_setup_project,
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        _open_project_window(window, project, project_dir, sdk_root)

        before_count = len(window._current_page.root_widget.children)
        window._on_widget_type_dropped("button", 9999, 9999, None)

        assert len(window._current_page.root_widget.children) == before_count + 1
        inserted = window._current_page.root_widget.children[-1]
        assert inserted.widget_type == "button"
        assert inserted.x == max(project.screen_width - inserted.width, 0)
        assert inserted.y == max(project.screen_height - inserted.height, 0)
        _close_window(window)

    @pytest.mark.parametrize(
        "handler_name",
        [
            "_on_tree_selection_changed",
            "_on_preview_selection_changed",
            "_on_widget_selected",
            "_on_preview_widget_selected",
        ],
    )
    def test_widget_selection_handlers_focus_properties_inspector(self, qapp, isolated_config, monkeypatch, handler_name):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")
        label = WidgetModel("label", name="title", x=4, y=4, width=60, height=20)

        def fake_set_selection(widgets=None, primary=None, sync_tree=True, sync_preview=True):
            window._selection_state.set_widgets(widgets or [], primary=primary)
            window._selected_widget = window._selection_state.primary

        monkeypatch.setattr(window, "_set_selection", fake_set_selection)
        window._show_inspector_tab("animations")

        if handler_name in {"_on_tree_selection_changed", "_on_preview_selection_changed"}:
            getattr(window, handler_name)([label], label)
        else:
            getattr(window, handler_name)(label)

        assert window._inspector_tabs.currentIndex() == 0
        _close_window(window)

    @pytest.mark.parametrize("handler_name", ["_on_tree_selection_changed", "_on_preview_selection_changed"])
    def test_selection_sync_handlers_keep_current_inspector_tab_when_selection_clears(
        self, qapp, isolated_config, monkeypatch, handler_name
    ):
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")

        def fake_set_selection(widgets=None, primary=None, sync_tree=True, sync_preview=True):
            window._selection_state.set_widgets(widgets or [], primary=primary)
            window._selected_widget = window._selection_state.primary

        monkeypatch.setattr(window, "_set_selection", fake_set_selection)
        window._show_inspector_tab("animations")

        getattr(window, handler_name)([], None)

        assert window._inspector_tabs.currentIndex() == 1
        _close_window(window)

    @pytest.mark.parametrize(
        ("first_handler", "second_handler"),
        [
            ("_on_widget_selected", "_on_tree_selection_changed"),
            ("_on_preview_widget_selected", "_on_preview_selection_changed"),
        ],
    )
    def test_redundant_selection_signals_skip_expensive_rebuilds(
        self, qapp, isolated_config, monkeypatch, first_handler, second_handler
    ):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")
        label = WidgetModel("textinput", name="title", x=4, y=4, width=120, height=28)
        counts = {
            "property": 0,
            "animations": 0,
            "focus": 0,
        }

        def _bump(key):
            counts[key] += 1

        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: _bump("property"))
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: _bump("animations"))
        monkeypatch.setattr(window.widget_tree, "set_selected_widgets", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.preview_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window, "_update_edit_actions", lambda: None)
        monkeypatch.setattr(window, "_update_diagnostics_panel", lambda: None)
        monkeypatch.setattr(window, "_show_selection_feedback", lambda: None)
        monkeypatch.setattr(window, "_update_widget_browser_target", lambda: None)
        monkeypatch.setattr(window, "_update_workspace_chips", lambda: None)
        monkeypatch.setattr(window.widget_browser, "select_widget_type", lambda *args, **kwargs: None)
        monkeypatch.setattr(window, "_focus_properties_for_selection", lambda: _bump("focus"))

        getattr(window, first_handler)([label], label) if first_handler.endswith("selection_changed") else getattr(window, first_handler)(label)
        getattr(window, second_handler)([label], label) if second_handler.endswith("selection_changed") else getattr(window, second_handler)(label)

        assert counts == {
            "property": 1,
            "animations": 1,
            "focus": 1,
        }
        _close_window(window)

    @pytest.mark.skip(reason="removed status center panel")
    def test_status_center_workspace_actions_switch_left_panel(self, qapp, isolated_config):
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")

        window._on_status_center_action_requested("open_components_panel")
        assert window._current_left_panel == "widgets"
        window._on_status_center_action_requested("open_project_panel")
        assert window._current_left_panel == "project"
        window._on_status_center_action_requested("open_structure_panel")
        assert window._current_left_panel == "structure"
        window._on_status_center_action_requested("open_assets_panel")
        assert window._current_left_panel == "assets"
        _close_window(window)

    @pytest.mark.skip(reason="removed status center panel")
    def test_status_center_inspector_actions_switch_inspector_tabs(self, qapp, isolated_config):
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")

        window._on_status_center_action_requested("open_animations_inspector")
        assert window._inspector_tabs.currentIndex() == 1
        window._on_status_center_action_requested("open_properties_inspector")
        assert window._inspector_tabs.currentIndex() == 0
        window._on_status_center_action_requested("open_page_timers")
        assert window._inspector_tabs.currentIndex() == 2
        assert window._page_tools_section_focus == "timers"
        window._on_status_center_action_requested("open_page_fields")
        assert window._inspector_tabs.currentIndex() == 2
        assert window._page_tools_section_focus == "fields"
        _close_window(window)

    @pytest.mark.skip(reason="removed status center panel")
    def test_status_center_tool_actions_switch_bottom_tabs(self, qapp, isolated_config):
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")

        window._on_status_center_action_requested("open_history")
        assert window._bottom_panel_visible is True
        assert window._bottom_tabs.currentIndex() == 1
        window._on_status_center_action_requested("open_debug")
        assert window._bottom_tabs.currentIndex() == 2
        window._on_status_center_action_requested("open_diagnostics")
        assert window._bottom_tabs.currentIndex() == 0
        _close_window(window)

    @pytest.mark.skip(reason="removed status center panel")
    def test_status_center_diagnostic_mix_actions_apply_severity_filter(self, qapp, isolated_config):
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")

        window._on_status_center_action_requested("open_error_diagnostics")
        assert window._bottom_panel_visible is True
        assert window._bottom_tabs.currentIndex() == 0
        assert window.diagnostics_panel._severity_filter_combo.currentData() == "error"
        window._on_status_center_action_requested("open_warning_diagnostics")
        assert window.diagnostics_panel._severity_filter_combo.currentData() == "warning"
        window._on_status_center_action_requested("open_info_diagnostics")
        assert window.diagnostics_panel._severity_filter_combo.currentData() == "info"
        _close_window(window)

    @pytest.mark.skip(reason="removed status center panel")
    def test_status_center_first_error_action_opens_diagnostics_entry(self, qapp, isolated_config, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")
        opened = []
        monkeypatch.setattr(window.diagnostics_panel, "open_first_error", lambda: opened.append("error"))

        window._on_status_center_action_requested("open_first_error")

        assert window._bottom_panel_visible is True
        assert window._bottom_tabs.currentIndex() == 0
        assert opened == ["error"]
        _close_window(window)

    @pytest.mark.skip(reason="removed status center panel")
    def test_status_center_first_warning_action_opens_diagnostics_entry(self, qapp, isolated_config, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")
        opened = []
        monkeypatch.setattr(window.diagnostics_panel, "open_first_warning", lambda: opened.append("warning"))

        window._on_status_center_action_requested("open_first_warning")

        assert window._bottom_panel_visible is True
        assert window._bottom_tabs.currentIndex() == 0
        assert opened == ["warning"]
        _close_window(window)

    @pytest.mark.skip(reason="removed status center panel")
    def test_status_center_suggested_action_button_routes_contextually(self, qapp, isolated_config, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")
        opened = []
        monkeypatch.setattr(window.diagnostics_panel, "open_first_error", lambda: opened.append("error"))

        assert window.status_center_panel._suggested_action_button.text() == "Configure SDK"
        window.status_center_panel._suggested_action_button.click()
        assert window._current_left_panel == "project"

        window.status_center_panel.set_status(sdk_ready=True, can_compile=True, dirty_pages=2)
        assert window.status_center_panel._suggested_action_button.text() == "Review History (2)"
        window.status_center_panel._suggested_action_button.click()
        assert window._bottom_panel_visible is True
        assert window._bottom_tabs.currentIndex() == 1

        window.status_center_panel.set_status(sdk_ready=True, can_compile=True, selection_count=1)
        assert window.status_center_panel._suggested_action_button.text() == "Inspect Selection (1)"
        window.status_center_panel._suggested_action_button.click()
        assert window._current_left_panel == "structure"

        window.status_center_panel.set_status(sdk_ready=True, can_compile=True, diagnostics_errors=1)
        assert window.status_center_panel._suggested_action_button.text() == "Fix First Error (1)"
        window.status_center_panel._suggested_action_button.click()
        assert window._bottom_tabs.currentIndex() == 0
        assert opened == ["error"]
        _close_window(window)

    @pytest.mark.skip(reason="removed status center panel")
    def test_status_center_workspace_chip_routes_contextually(self, qapp, isolated_config, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")
        opened = []
        monkeypatch.setattr(window.diagnostics_panel, "open_first_error", lambda: opened.append("error"))

        assert window.status_center_panel._workspace_chip.text() == "Check Workspace (Setup)"
        window.status_center_panel._workspace_chip.click()
        assert window._current_left_panel == "project"

        window.status_center_panel.set_status(sdk_ready=True, can_compile=True, diagnostics_errors=1)
        assert window.status_center_panel._workspace_chip.text() == "Action Needed (Diagnostics)"
        window.status_center_panel._workspace_chip.click()
        assert window._bottom_tabs.currentIndex() == 0
        assert opened == ["error"]
        _close_window(window)

    @pytest.mark.skip(reason="removed status center panel")
    def test_status_center_suggested_action_routes_runtime_and_info_context(self, qapp, isolated_config):
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")

        window.status_center_panel.set_status(sdk_ready=True, can_compile=True, runtime_error="Bridge lost")
        assert window.status_center_panel._suggested_action_button.text() == "Inspect Debug Output"
        window.status_center_panel._suggested_action_button.click()
        assert window._bottom_panel_visible is True
        assert window._bottom_tabs.currentIndex() == 2

        window.status_center_panel.set_status(sdk_ready=True, can_compile=True, diagnostics_infos=2)
        assert window.status_center_panel._suggested_action_button.text() == "Inspect Info (2)"
        window.status_center_panel._suggested_action_button.click()
        assert window._bottom_tabs.currentIndex() == 0
        assert window.diagnostics_panel._severity_filter_combo.currentData() == "info"
        _close_window(window)

    @pytest.mark.skip(reason="removed status center panel")
    def test_status_center_repeat_action_replays_restored_action(self, qapp, isolated_config):
        from ui_designer.ui.main_window import MainWindow

        isolated_config.workspace_status_panel_state = {"last_action": "open_assets_panel"}

        window = MainWindow("")

        assert window.status_center_panel._repeat_action_button.isEnabled() is True
        assert window.status_center_panel._repeat_action_button.text() == "Repeat Assets"

        window.status_center_panel._repeat_action_button.click()

        assert window._current_left_panel == "assets"
        assert window._left_panel_stack.currentWidget() is window.res_panel
        _close_window(window)

    @pytest.mark.skip(reason="removed status center panel")
    def test_status_center_recent_action_menu_replays_restored_action(self, qapp, isolated_config):
        from ui_designer.ui.main_window import MainWindow

        isolated_config.workspace_status_panel_state = {
            "last_action": "open_assets_panel",
            "recent_actions": ["open_assets_panel", "open_project_panel", "open_debug"],
        }

        window = MainWindow("")

        assert [action.text() for action in window.status_center_panel._repeat_action_menu.actions() if not action.isSeparator()] == [
            "Assets",
            "Project",
            "Debug Output",
            "Clear Recent Actions (3)",
        ]

        window.status_center_panel._repeat_action_menu.actions()[1].trigger()

        assert window._current_left_panel == "project"
        assert window._left_panel_stack.currentWidget() is window._project_workspace
        assert window.status_center_panel._last_action_label.text() == "Last action: Project"
        assert window.status_center_panel._repeat_action_button.text() == "Repeat Project"
        _close_window(window)

    @pytest.mark.skip(reason="removed status center panel")
    def test_status_center_recent_action_menu_can_clear_restored_history(self, qapp, isolated_config):
        from ui_designer.ui.main_window import MainWindow

        isolated_config.workspace_status_panel_state = {
            "last_action": "open_assets_panel",
            "recent_actions": ["open_assets_panel", "open_project_panel", "open_debug"],
        }

        window = MainWindow("")

        clear_action = next(
            action
            for action in window.status_center_panel._repeat_action_menu.actions()
            if action.text().startswith("Clear Recent Actions")
        )
        clear_action.trigger()

        assert window.status_center_panel._last_action_label.text() == "Last action: None"
        assert window.status_center_panel._repeat_action_button.isEnabled() is False
        assert window.status_center_panel.view_state() == {"last_action": "", "recent_actions": []}

        _close_window(window)
        assert isolated_config.workspace_status_panel_state == {"last_action": "", "recent_actions": []}


@_skip_no_qt
class TestMainWindowCanvasActions:
    def test_select_all_selects_visible_non_root_widgets(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "SelectAllDemo"
        first = WidgetModel("label", name="first", x=8, y=8, width=60, height=20)
        second = WidgetModel("button", name="second", x=16, y=40, width=80, height=24)
        hidden = WidgetModel("switch", name="hidden", x=24, y=72, width=60, height=20)
        hidden.designer_hidden = True
        project, root = _create_project_and_root_with_widgets(
            project_dir,
            "SelectAllDemo",
            sdk_root,
            widgets=[first, second, hidden],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        _open_project_window(window, project, project_dir, sdk_root)

        window._select_all_action.trigger()

        assert window._select_all_action.shortcut().toString() == "Ctrl+A"
        assert window._selection_state.widgets == [first, second]
        assert root not in window._selection_state.widgets
        _close_window(window)

    def test_select_all_prefers_focused_text_input(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "SelectAllFilterDemo"
        first = WidgetModel("label", name="first", x=8, y=8, width=60, height=20)
        project = _create_project_only_with_widgets(
            project_dir,
            "SelectAllFilterDemo",
            sdk_root,
            widgets=[first],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([first], primary=first, sync_tree=True, sync_preview=True)
        window.widget_tree.filter_edit.setText("first")
        monkeypatch.setattr("ui_designer.ui.main_window.QApplication.focusWidget", lambda: window.widget_tree.filter_edit)

        window._select_all_action.trigger()

        assert window.widget_tree.filter_edit.selectedText() == "first"
        assert window._selection_state.widgets == [first]
        _close_window(window)

    def test_build_preview_context_menu_includes_expected_actions(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewContextMenuDemo"
        first = WidgetModel("label", name="first", x=8, y=8, width=60, height=20)
        project = _create_project_only_with_widgets(
            project_dir,
            "PreviewContextMenuDemo",
            sdk_root,
            widgets=[first],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        _open_project_window(window, project, project_dir, sdk_root)
        menu = window._build_preview_context_menu(first)
        labels = [action.text() for action in menu.actions() if action.text()]
        select_menu = next(action.menu() for action in menu.actions() if action.text() == "Select")
        select_labels = [action.text() for action in select_menu.actions() if action.text()]

        assert labels == [
            "Select All",
            "Select",
            "Copy",
            "Cut",
            "Paste",
            "Duplicate",
            "Delete",
            "Arrange",
            "Structure",
        ]
        assert "Select All" in labels
        assert "Select" in labels
        assert "Copy" in labels
        assert "Delete" in labels
        assert "Arrange" in labels
        assert "Structure" in labels
        assert "Parent" in select_labels
        assert "Previous Sibling" in select_labels
        assert "Next Sibling" in select_labels
        assert "Previous Siblings" in select_labels
        assert "Next Siblings" in select_labels
        assert "Previous In Tree" in select_labels
        assert "Next In Tree" in select_labels
        assert "First Child" in select_labels
        assert "Last Child" in select_labels
        assert "Root" in select_labels
        assert "Path" in select_labels
        assert "Top-Level" in select_labels
        assert "Ancestors" in select_labels
        assert "Children" in select_labels
        assert "Descendants" in select_labels
        assert "Subtree" in select_labels
        assert "Leaves" in select_labels
        assert "Containers" in select_labels
        assert "Layout Containers" in select_labels
        assert "Visible" in select_labels
        assert "Hidden" in select_labels
        assert "Unlocked" in select_labels
        assert "Locked" in select_labels
        assert "Managed" in select_labels
        assert "Free Position" in select_labels
        assert "Siblings" in select_labels
        assert "Same Parent Type" in select_labels
        assert "Subtree Type" in select_labels
        assert "Same Type" in select_labels
        assert "Same Depth" in select_labels
        _close_window(window)

    def test_build_preview_context_menu_select_actions_appear_in_expected_order(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewSelectMenuOrderDemo"
        first = WidgetModel("label", name="first", x=8, y=8, width=60, height=20)
        project = _create_project_only_with_widgets(
            project_dir,
            "PreviewSelectMenuOrderDemo",
            sdk_root,
            widgets=[first],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        _open_project_window(window, project, project_dir, sdk_root)

        menu = window._build_preview_context_menu(first)
        select_labels = [action.text() for action in _context_submenu(menu, "Select").actions() if action.text()]

        assert select_labels == [
            "Parent",
            "Previous Sibling",
            "Next Sibling",
            "Previous Siblings",
            "Next Siblings",
            "Previous In Tree",
            "Next In Tree",
            "Ancestors",
            "Root",
            "Path",
            "Top-Level",
            "First Child",
            "Last Child",
            "Children",
            "Descendants",
            "Subtree",
            "Leaves",
            "Containers",
            "Layout Containers",
            "Visible",
            "Hidden",
            "Unlocked",
            "Locked",
            "Managed",
            "Free Position",
            "Siblings",
            "Same Parent Type",
            "Subtree Type",
            "Same Type",
            "Same Depth",
        ]

        menu.deleteLater()
        _close_window(window)

    def test_build_preview_context_menu_exposes_expected_shortcuts(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewContextMenuShortcutDemo"
        first = WidgetModel("label", name="first", x=8, y=8, width=60, height=20)
        second = WidgetModel("button", name="second", x=72, y=8, width=60, height=20)
        target = WidgetModel("group", name="target", x=10, y=40, width=120, height=80)
        project = _create_project_only_with_widgets(
            project_dir,
            "PreviewContextMenuShortcutDemo",
            sdk_root,
            widgets=[first, second, target],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([first, second], primary=first, sync_tree=True, sync_preview=True)

        menu = window._build_preview_context_menu(first)
        actions = {action.text(): action for action in menu.actions() if action.text()}
        structure_actions = {
            action.text(): action for action in _context_submenu(menu, "Structure").actions() if action.text()
        }

        assert actions["Select All"].shortcut().toString() == "Ctrl+A"
        assert actions["Copy"].shortcut().toString() == "Ctrl+C"
        assert actions["Cut"].shortcut().toString() == "Ctrl+X"
        assert actions["Paste"].shortcut().toString() == "Ctrl+V"
        assert actions["Duplicate"].shortcut().toString() == "Ctrl+D"
        assert actions["Delete"].shortcut().toString() == "Del"

        assert structure_actions["Group Selection"].shortcut().toString() == "Ctrl+G"
        assert structure_actions["Ungroup"].shortcut().toString() == "Ctrl+Shift+G"
        assert structure_actions["Move Into..."].shortcut().toString() == "Ctrl+Shift+I"
        assert structure_actions["Lift To Parent"].shortcut().toString() == "Ctrl+Shift+L"
        assert structure_actions["Move Up"].shortcut().toString() == "Alt+Up"
        assert structure_actions["Move Down"].shortcut().toString() == "Alt+Down"
        assert structure_actions["Move To Top"].shortcut().toString() == "Alt+Shift+Up"
        assert structure_actions["Move To Bottom"].shortcut().toString() == "Alt+Shift+Down"

        menu.deleteLater()
        _close_window(window)

    @pytest.mark.skip(reason="removed quick-move history feature")
    def test_build_preview_context_menu_structure_actions_appear_in_expected_order(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewStructureMenuOrderDemo"
        first = WidgetModel("label", name="first", x=8, y=8, width=60, height=20)
        second = WidgetModel("button", name="second", x=72, y=8, width=60, height=20)
        target = WidgetModel("group", name="target", x=10, y=40, width=120, height=80)
        project = _create_project_only_with_widgets(
            project_dir,
            "PreviewStructureMenuOrderDemo",
            sdk_root,
            widgets=[first, second, target],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([first, second], primary=first, sync_tree=True, sync_preview=True)

        menu = window._build_preview_context_menu(first)
        structure_menu = next(action.menu() for action in menu.actions() if action.text() == "Structure")
        structure_labels = [action.text() for action in structure_menu.actions() if action.text()]

        assert structure_labels == [
            "Group Selection",
            "Ungroup",
            "Move Into...",
            "Move Into Last Target",
            "Clear Move Target History",
            "Quick Move Into",
            "Lift To Parent",
            "Move Up",
            "Move Down",
            "Move To Top",
            "Move To Bottom",
        ]
        _close_window(window)

    @pytest.mark.skip(reason="removed quick-move history feature")
    def test_build_preview_context_menu_structure_actions_reflect_selection_state(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewStructureMenuStateDemo"
        first = WidgetModel("label", name="first", x=8, y=8, width=60, height=20)
        second = WidgetModel("button", name="second", x=72, y=8, width=60, height=20)
        target = WidgetModel("group", name="target_group", x=10, y=40, width=120, height=80)
        nested = WidgetModel("switch", name="nested", x=4, y=4, width=32, height=16)
        _add_widget_children(target, [nested])
        project = _create_project_only_with_widgets(
            project_dir,
            "PreviewStructureMenuStateDemo",
            sdk_root,
            widgets=[first, second, target],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        _open_project_window(window, project, project_dir, sdk_root)

        def _structure_actions(widget):
            menu = window._build_preview_context_menu(widget)
            structure_menu = _context_submenu(menu, "Structure")
            actions = {action.text(): action for action in structure_menu.actions() if action.text()}
            return menu, actions

        window._set_selection([first, second], primary=first, sync_tree=True, sync_preview=True)
        menu, actions = _structure_actions(first)
        structure_action = next(action for action in menu.actions() if action.text() == "Structure")
        assert structure_action.isEnabled() is True
        assert structure_action.toolTip() == "Group, move, and reorder widgets relative to the current selection."
        assert structure_action.statusTip() == structure_action.toolTip()
        assert actions["Group Selection"].isEnabled() is True
        assert actions["Ungroup"].isEnabled() is False
        assert actions["Move Into..."].isEnabled() is True
        assert actions["Move Into Last Target"].isEnabled() is False
        assert actions["Quick Move Into"].menu() is not None
        assert actions["Quick Move Into"].isEnabled() is window._quick_move_into_menu.menuAction().isEnabled()
        assert actions["Quick Move Into"].toolTip() == window._quick_move_into_menu.menuAction().toolTip()
        assert actions["Lift To Parent"].isEnabled() is False
        assert actions["Move Up"].isEnabled() is False
        assert actions["Move Down"].isEnabled() is True
        assert actions["Move To Top"].isEnabled() is False
        assert actions["Move To Bottom"].isEnabled() is True
        assert "selection must only include groups" in actions["Ungroup"].toolTip()
        assert "move something into a container first" in actions["Move Into Last Target"].toolTip()
        assert "selected widgets already belong to the top container" in actions["Lift To Parent"].toolTip()
        assert actions["Group Selection"].shortcut().toString() == "Ctrl+G"
        assert actions["Move Into Last Target"].shortcut().toString() == "Ctrl+Alt+I"
        assert actions["Lift To Parent"].shortcut().toString() == "Ctrl+Shift+L"
        menu.deleteLater()

        window._set_selection([nested], primary=nested, sync_tree=True, sync_preview=True)
        menu, actions = _structure_actions(nested)
        assert actions["Group Selection"].isEnabled() is False
        assert actions["Ungroup"].isEnabled() is False
        assert actions["Move Into..."].isEnabled() is True
        assert actions["Lift To Parent"].isEnabled() is True
        assert actions["Move Up"].isEnabled() is False
        assert actions["Move Down"].isEnabled() is False
        assert actions["Move To Top"].isEnabled() is False
        assert actions["Move To Bottom"].isEnabled() is False
        menu.deleteLater()

        window._set_selection([first], primary=first, sync_tree=True, sync_preview=True)
        window._move_selection_into_target(target, target_label="root_group / target_group (group)")
        window._set_selection([second], primary=second, sync_tree=True, sync_preview=True)
        menu, actions = _structure_actions(second)
        assert actions["Move Into Last Target"].isEnabled() is True
        assert actions["Clear Move Target History"].isEnabled() is True
        assert "root_group / target_group (group)" in actions["Move Into Last Target"].toolTip()
        menu.deleteLater()

        _close_window(window)

    @pytest.mark.skip(reason="removed quick-move history feature")
    def test_build_preview_context_menu_structure_actions_disable_root_and_noop_move_into(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewStructureActionDisabledDemo"
        child = WidgetModel("label", name="child", x=8, y=8, width=60, height=20)
        project, root = _create_project_and_root_with_widgets(
            project_dir,
            "PreviewStructureActionDisabledDemo",
            sdk_root,
            widgets=[child],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        _open_project_window(window, project, project_dir, sdk_root)

        def _structure_actions(widget):
            menu = window._build_preview_context_menu(widget)
            structure_menu = _context_submenu(menu, "Structure")
            actions = {action.text(): action for action in structure_menu.actions() if action.text()}
            return menu, structure_menu, actions

        window._set_selection([root], primary=root, sync_tree=True, sync_preview=True)
        menu, structure_menu, actions = _structure_actions(root)
        structure_action = next(action for action in menu.actions() if action.text() == "Structure")
        assert actions["Group Selection"].isEnabled() is False
        assert actions["Ungroup"].isEnabled() is False
        assert actions["Move Into..."].isEnabled() is False
        assert actions["Move Into Last Target"].isEnabled() is False
        assert actions["Quick Move Into"].isEnabled() is window._quick_move_into_menu.menuAction().isEnabled()
        assert actions["Quick Move Into"].toolTip() == window._quick_move_into_menu.menuAction().toolTip()
        assert actions["Lift To Parent"].isEnabled() is False
        assert actions["Move Up"].isEnabled() is False
        assert actions["Move Down"].isEnabled() is False
        assert actions["Move To Top"].isEnabled() is False
        assert actions["Move To Bottom"].isEnabled() is False
        assert "root widgets cannot be regrouped or reordered" in actions["Group Selection"].toolTip()
        assert structure_action.isEnabled() is False
        assert structure_action.toolTip() == "Structure unavailable: root widgets cannot be regrouped or reordered."
        assert structure_action.statusTip() == structure_action.toolTip()
        assert "(No eligible target containers)" in [
            action.text() for action in next(action.menu() for action in structure_menu.actions() if action.text() == "Quick Move Into").actions()
        ]
        menu.deleteLater()

        window._set_selection([child], primary=child, sync_tree=True, sync_preview=True)
        menu, structure_menu, actions = _structure_actions(child)
        structure_action = next(action for action in menu.actions() if action.text() == "Structure")
        assert actions["Group Selection"].isEnabled() is False
        assert actions["Ungroup"].isEnabled() is False
        assert actions["Move Into..."].isEnabled() is False
        assert actions["Move Into Last Target"].isEnabled() is False
        assert actions["Quick Move Into"].isEnabled() is window._quick_move_into_menu.menuAction().isEnabled()
        assert actions["Quick Move Into"].toolTip() == window._quick_move_into_menu.menuAction().toolTip()
        assert actions["Lift To Parent"].isEnabled() is False
        assert actions["Move Up"].isEnabled() is False
        assert actions["Move Down"].isEnabled() is False
        assert actions["Move To Top"].isEnabled() is False
        assert actions["Move To Bottom"].isEnabled() is False
        assert "no eligible target containers are available" in actions["Move Into..."].toolTip()
        assert structure_action.isEnabled() is False
        assert (
            structure_action.toolTip()
            == "Structure unavailable: select another sibling or target container to move this widget."
        )
        assert structure_action.statusTip() == structure_action.toolTip()
        assert "(No eligible target containers)" in [
            action.text() for action in next(action.menu() for action in structure_menu.actions() if action.text() == "Quick Move Into").actions()
        ]
        menu.deleteLater()

        _close_window(window)

    def test_build_preview_context_menu_arrange_actions_appear_in_expected_order(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewArrangeMenuOrderDemo"
        first = WidgetModel("label", name="first", x=8, y=8, width=60, height=20)
        second = WidgetModel("button", name="second", x=72, y=8, width=60, height=20)
        project = _create_project_only_with_widgets(
            project_dir,
            "PreviewArrangeMenuOrderDemo",
            sdk_root,
            widgets=[first, second],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([first, second], primary=first, sync_tree=True, sync_preview=True)

        menu = window._build_preview_context_menu(first)
        arrange_menu = next(action.menu() for action in menu.actions() if action.text() == "Arrange")
        arrange_labels = [action.text() for action in arrange_menu.actions() if action.text()]

        assert arrange_labels == [
            "Align Left",
            "Align Right",
            "Align Top",
            "Align Bottom",
            "Align Horizontal Center",
            "Align Vertical Center",
            "Distribute Horizontally",
            "Distribute Vertically",
            "Bring to Front",
            "Send to Back",
            "Toggle Lock",
            "Toggle Hide",
        ]
        _close_window(window)

    def test_build_preview_context_menu_arrange_actions_reflect_selection_state(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewArrangeMenuStateDemo"
        first = WidgetModel("label", name="first", x=8, y=8, width=60, height=20)
        second = WidgetModel("button", name="second", x=72, y=8, width=60, height=20)
        third = WidgetModel("switch", name="third", x=136, y=8, width=60, height=20)
        project = _create_project_only_with_widgets(
            project_dir,
            "PreviewArrangeMenuStateDemo",
            sdk_root,
            widgets=[first, second, third],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        _open_project_window(window, project, project_dir, sdk_root)

        def _arrange_actions():
            menu = window._build_preview_context_menu(first)
            arrange_menu = _context_submenu(menu, "Arrange")
            actions = {action.text(): action for action in arrange_menu.actions() if action.text()}
            return menu, actions

        window._set_selection([first], primary=first, sync_tree=True, sync_preview=True)
        menu, actions = _arrange_actions()
        arrange_action = next(action for action in menu.actions() if action.text() == "Arrange")
        assert arrange_action.isEnabled() is True
        assert arrange_action.toolTip() == "Arrange selected widgets by alignment, order, lock, and visibility."
        assert arrange_action.statusTip() == arrange_action.toolTip()
        assert actions["Align Left"].isEnabled() is False
        assert actions["Align Vertical Center"].isEnabled() is False
        assert actions["Distribute Horizontally"].isEnabled() is False
        assert actions["Distribute Vertically"].isEnabled() is False
        assert actions["Bring to Front"].isEnabled() is True
        assert actions["Send to Back"].isEnabled() is True
        assert actions["Toggle Lock"].isEnabled() is True
        assert actions["Toggle Hide"].isEnabled() is True
        menu.deleteLater()

        window._set_selection([first, second], primary=first, sync_tree=True, sync_preview=True)
        menu, actions = _arrange_actions()
        assert actions["Align Left"].isEnabled() is True
        assert actions["Align Vertical Center"].isEnabled() is True
        assert actions["Distribute Horizontally"].isEnabled() is False
        assert actions["Distribute Vertically"].isEnabled() is False
        assert actions["Bring to Front"].isEnabled() is True
        assert actions["Send to Back"].isEnabled() is True
        menu.deleteLater()

        window._set_selection([first, second, third], primary=first, sync_tree=True, sync_preview=True)
        menu, actions = _arrange_actions()
        assert actions["Align Left"].isEnabled() is True
        assert actions["Align Vertical Center"].isEnabled() is True
        assert actions["Distribute Horizontally"].isEnabled() is True
        assert actions["Distribute Vertically"].isEnabled() is True
        assert actions["Toggle Lock"].isEnabled() is True
        assert actions["Toggle Hide"].isEnabled() is True
        menu.deleteLater()

        _close_window(window)

    def test_build_preview_context_menu_edit_actions_reflect_selection_state(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewEditMenuStateDemo"
        first = WidgetModel("label", name="first", x=8, y=8, width=60, height=20)
        locked = WidgetModel("button", name="locked", x=72, y=8, width=60, height=20)
        locked.designer_locked = True
        project = _create_project_only_with_widgets(
            project_dir,
            "PreviewEditMenuStateDemo",
            sdk_root,
            widgets=[first, locked],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        _open_project_window(window, project, project_dir, sdk_root)

        def _menu_actions(widget):
            menu = window._build_preview_context_menu(widget)
            actions = {action.text(): action for action in menu.actions() if action.text()}
            return menu, actions

        window._set_selection([first], primary=first, sync_tree=True, sync_preview=True)
        menu, actions = _menu_actions(first)
        assert actions["Select All"].isEnabled() is True
        assert actions["Copy"].isEnabled() is True
        assert actions["Cut"].isEnabled() is True
        assert actions["Paste"].isEnabled() is False
        assert actions["Duplicate"].isEnabled() is True
        assert actions["Delete"].isEnabled() is True
        menu.deleteLater()

        window._set_selection([locked], primary=locked, sync_tree=True, sync_preview=True)
        menu, actions = _menu_actions(locked)
        assert actions["Select All"].isEnabled() is True
        assert actions["Copy"].isEnabled() is True
        assert actions["Cut"].isEnabled() is False
        assert actions["Paste"].isEnabled() is False
        assert actions["Duplicate"].isEnabled() is True
        assert actions["Delete"].isEnabled() is False
        menu.deleteLater()

        window._clipboard_payload = {"widgets": []}
        window._set_selection([first], primary=first, sync_tree=True, sync_preview=True)
        menu, actions = _menu_actions(first)
        assert actions["Paste"].isEnabled() is True
        menu.deleteLater()

        _close_window(window)

    def test_build_preview_context_menu_select_actions_reflect_widget_relationships(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewSelectMenuRelationshipsDemo"
        first = WidgetModel("label", name="first", x=8, y=8, width=40, height=16)
        container = WidgetModel("group", name="container", x=10, y=24, width=120, height=80)
        child_a = WidgetModel("switch", name="child_a", x=4, y=4, width=32, height=16)
        child_b = WidgetModel("button", name="child_b", x=4, y=28, width=48, height=20)
        solo = WidgetModel("label", name="solo", x=140, y=24, width=40, height=16)
        _add_widget_children(container, [child_a, child_b])
        project, root = _create_project_and_root_with_widgets(
            project_dir,
            "PreviewSelectMenuRelationshipsDemo",
            sdk_root,
            widgets=[first, container, solo],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        _open_project_window(window, project, project_dir, sdk_root)

        def _select_actions(widget):
            menu = window._build_preview_context_menu(widget)
            select_menu = next(action.menu() for action in menu.actions() if action.text() == "Select")
            actions = {action.text(): action for action in select_menu.actions() if action.text()}
            return menu, actions

        root_menu, root_actions = _select_actions(root)
        assert root_actions["Parent"].isEnabled() is False
        assert root_actions["Previous Sibling"].isEnabled() is False
        assert root_actions["Next Sibling"].isEnabled() is False
        assert root_actions["Previous Siblings"].isEnabled() is False
        assert root_actions["Next Siblings"].isEnabled() is False
        assert root_actions["Previous In Tree"].isEnabled() is False
        assert root_actions["Ancestors"].isEnabled() is False
        assert root_actions["Root"].isEnabled() is False
        assert root_actions["Same Depth"].isEnabled() is False
        assert root_actions["Children"].isEnabled() is True
        assert root_actions["Descendants"].isEnabled() is True
        assert root_actions["Subtree"].isEnabled() is True
        assert root_actions["Leaves"].isEnabled() is True
        assert root_actions["Containers"].isEnabled() is True
        assert root_actions["Layout Containers"].isEnabled() is False
        assert root_actions["Visible"].isEnabled() is True
        assert root_actions["Hidden"].isEnabled() is False
        assert root_actions["Unlocked"].isEnabled() is True
        assert root_actions["Locked"].isEnabled() is False
        assert root_actions["Siblings"].isEnabled() is False
        assert root_actions["Managed"].isEnabled() is False
        assert root_actions["Free Position"].isEnabled() is True
        assert "Unavailable: root widgets do not have a parent." in root_actions["Parent"].toolTip()
        assert "Unavailable: root widgets do not have siblings." in root_actions["Previous Sibling"].toolTip()
        assert "Unavailable: root widgets do not have siblings." in root_actions["Next Sibling"].toolTip()
        assert "Unavailable: root widgets do not have siblings." in root_actions["Previous Siblings"].toolTip()
        assert "Unavailable: root widgets do not have siblings." in root_actions["Next Siblings"].toolTip()
        assert "Unavailable: widget is already the first widget in tree order on this page." in root_actions["Previous In Tree"].toolTip()
        assert "Unavailable: root widgets do not have ancestors." in root_actions["Ancestors"].toolTip()
        assert "Unavailable: widget is already the page root." in root_actions["Root"].toolTip()
        assert "Unavailable: no other widgets exist at depth 0 on this page." in root_actions["Same Depth"].toolTip()
        assert "Unavailable: no layout container widgets exist in this subtree." in root_actions["Layout Containers"].toolTip()
        assert "Unavailable: no hidden widgets exist in this subtree." in root_actions["Hidden"].toolTip()
        assert "Unavailable: no locked widgets exist in this subtree." in root_actions["Locked"].toolTip()
        assert "Unavailable: root widgets do not have siblings." in root_actions["Siblings"].toolTip()
        assert "Unavailable: no layout-managed widgets exist in this subtree." in root_actions["Managed"].toolTip()
        assert root_actions["Parent"].statusTip() == root_actions["Parent"].toolTip()
        assert root_actions["Managed"].statusTip() == root_actions["Managed"].toolTip()
        root_menu.deleteLater()

        container_menu, container_actions = _select_actions(container)
        assert container_actions["Parent"].isEnabled() is True
        assert container_actions["Previous Sibling"].isEnabled() is True
        assert container_actions["Next Sibling"].isEnabled() is True
        assert container_actions["Previous Siblings"].isEnabled() is True
        assert container_actions["Next Siblings"].isEnabled() is True
        assert container_actions["Previous In Tree"].isEnabled() is True
        assert container_actions["Next In Tree"].isEnabled() is True
        assert container_actions["Ancestors"].isEnabled() is True
        assert container_actions["Root"].isEnabled() is True
        assert container_actions["Path"].isEnabled() is True
        assert container_actions["Top-Level"].isEnabled() is True
        assert container_actions["First Child"].isEnabled() is True
        assert container_actions["Last Child"].isEnabled() is True
        assert container_actions["Children"].isEnabled() is True
        assert container_actions["Descendants"].isEnabled() is True
        assert container_actions["Subtree"].isEnabled() is True
        assert container_actions["Leaves"].isEnabled() is True
        assert container_actions["Containers"].isEnabled() is False
        assert container_actions["Layout Containers"].isEnabled() is False
        assert container_actions["Visible"].isEnabled() is True
        assert container_actions["Unlocked"].isEnabled() is True
        assert container_actions["Managed"].isEnabled() is False
        assert container_actions["Free Position"].isEnabled() is True
        assert container_actions["Siblings"].isEnabled() is True
        assert container_actions["Same Parent Type"].isEnabled() is False
        assert container_actions["Subtree Type"].isEnabled() is False
        assert container_actions["Same Depth"].isEnabled() is True
        assert container_actions["Children"].statusTip() == container_actions["Children"].toolTip()
        container_menu.deleteLater()

        child_menu, child_actions = _select_actions(child_a)
        assert child_actions["Parent"].isEnabled() is True
        assert child_actions["Previous Sibling"].isEnabled() is False
        assert child_actions["Next Sibling"].isEnabled() is True
        assert child_actions["Previous Siblings"].isEnabled() is False
        assert child_actions["Next Siblings"].isEnabled() is True
        assert child_actions["Previous In Tree"].isEnabled() is True
        assert child_actions["Next In Tree"].isEnabled() is True
        assert child_actions["Ancestors"].isEnabled() is True
        assert child_actions["Root"].isEnabled() is True
        assert child_actions["Path"].isEnabled() is True
        assert child_actions["Top-Level"].isEnabled() is True
        assert child_actions["First Child"].isEnabled() is False
        assert child_actions["Last Child"].isEnabled() is False
        assert child_actions["Children"].isEnabled() is False
        assert child_actions["Descendants"].isEnabled() is False
        assert child_actions["Subtree"].isEnabled() is False
        assert child_actions["Leaves"].isEnabled() is False
        assert child_actions["Containers"].isEnabled() is False
        assert child_actions["Layout Containers"].isEnabled() is False
        assert child_actions["Visible"].isEnabled() is True
        assert child_actions["Hidden"].isEnabled() is False
        assert child_actions["Unlocked"].isEnabled() is True
        assert child_actions["Locked"].isEnabled() is False
        assert child_actions["Managed"].isEnabled() is False
        assert child_actions["Free Position"].isEnabled() is True
        assert child_actions["Siblings"].isEnabled() is True
        assert child_actions["Same Parent Type"].isEnabled() is False
        assert child_actions["Subtree Type"].isEnabled() is False
        assert child_actions["Same Type"].isEnabled() is False
        assert child_actions["Same Depth"].isEnabled() is True
        assert "Unavailable: widget has no child widgets." in child_actions["First Child"].toolTip()
        assert "Unavailable: widget has no child widgets." in child_actions["Last Child"].toolTip()
        assert "Unavailable: widget has no child widgets." in child_actions["Children"].toolTip()
        assert "Unavailable: widget has no descendant widgets." in child_actions["Descendants"].toolTip()
        assert "Unavailable: widget has no descendant widgets." in child_actions["Subtree"].toolTip()
        assert "Unavailable: widget has no leaf descendants." in child_actions["Leaves"].toolTip()
        assert "Unavailable: no other container widgets exist in this subtree." in child_actions["Containers"].toolTip()
        assert "Unavailable: no layout container widgets exist in this subtree." in child_actions["Layout Containers"].toolTip()
        assert "Unavailable: no hidden widgets exist in this subtree." in child_actions["Hidden"].toolTip()
        assert "Unavailable: no locked widgets exist in this subtree." in child_actions["Locked"].toolTip()
        assert "Unavailable: no layout-managed widgets exist in this subtree." in child_actions["Managed"].toolTip()
        assert "Unavailable: widget does not have a previous sibling under the same parent." in child_actions["Previous Sibling"].toolTip()
        assert "Unavailable: widget does not have any previous siblings under the same parent." in child_actions["Previous Siblings"].toolTip()
        assert "Unavailable: no other switch widgets exist under the same parent." in child_actions["Same Parent Type"].toolTip()
        assert "Unavailable: no other switch widgets exist in this subtree." in child_actions["Subtree Type"].toolTip()
        assert "Unavailable: no other switch widgets exist on this page." in child_actions["Same Type"].toolTip()
        assert child_actions["Children"].statusTip() == child_actions["Children"].toolTip()
        assert child_actions["Same Type"].statusTip() == child_actions["Same Type"].toolTip()
        child_menu.deleteLater()

        solo_menu, solo_actions = _select_actions(solo)
        assert solo_actions["Previous Siblings"].isEnabled() is True
        assert solo_actions["Next Siblings"].isEnabled() is False
        assert solo_actions["Previous In Tree"].isEnabled() is True
        assert solo_actions["Next In Tree"].isEnabled() is False
        assert "Unavailable: widget does not have any next siblings under the same parent." in solo_actions["Next Siblings"].toolTip()
        assert "Unavailable: widget is already the last widget in tree order on this page." in solo_actions["Next In Tree"].toolTip()
        solo_menu.deleteLater()

        _close_window(window)

    def test_build_preview_context_menu_without_widget_omits_select_submenu(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewNoWidgetContextMenuDemo"
        project = _create_project_only_with_widgets(
            project_dir,
            "PreviewNoWidgetContextMenuDemo",
            sdk_root,
            widgets=[WidgetModel("label", name="first")],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        _open_project_window(window, project, project_dir, sdk_root)
        menu = window._build_preview_context_menu(None)
        labels = [action.text() for action in menu.actions() if action.text()]

        assert labels == [
            "Select All",
            "Copy",
            "Cut",
            "Paste",
            "Duplicate",
            "Delete",
            "Arrange",
            "Structure",
        ]
        assert "Select" not in labels
        assert "Structure" in labels
        _close_window(window)

    def test_build_preview_context_menu_without_widget_reflects_empty_selection_state(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewNoWidgetContextMenuStateDemo"
        project = _create_project_only_with_widgets(
            project_dir,
            "PreviewNoWidgetContextMenuStateDemo",
            sdk_root,
            widgets=[WidgetModel("label", name="first")],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        _open_project_window(window, project, project_dir, sdk_root)

        window._selection_state.set_widgets([], primary=None)
        window._selected_widget = None
        window._update_edit_actions()

        menu = window._build_preview_context_menu(None)
        actions = {action.text(): action for action in menu.actions() if action.text()}
        arrange_actions = {
            action.text(): action for action in _context_submenu(menu, "Arrange").actions() if action.text()
        }
        structure_menu = _context_submenu(menu, "Structure")
        structure_actions = {action.text(): action for action in structure_menu.actions() if action.text()}

        assert "Select" not in actions
        assert actions["Select All"].isEnabled() is True
        assert actions["Copy"].isEnabled() is False
        assert actions["Cut"].isEnabled() is False
        assert actions["Paste"].isEnabled() is False
        assert actions["Duplicate"].isEnabled() is False
        assert actions["Delete"].isEnabled() is False
        assert actions["Arrange"].isEnabled() is False
        assert actions["Arrange"].toolTip() == "Arrange unavailable: select at least 1 widget."
        assert actions["Arrange"].statusTip() == actions["Arrange"].toolTip()
        assert actions["Structure"].isEnabled() is False
        assert actions["Structure"].toolTip() == "Structure unavailable: select at least 1 widget."
        assert actions["Structure"].statusTip() == actions["Structure"].toolTip()

        assert arrange_actions["Align Left"].isEnabled() is False
        assert arrange_actions["Distribute Horizontally"].isEnabled() is False
        assert arrange_actions["Bring to Front"].isEnabled() is False
        assert arrange_actions["Toggle Lock"].isEnabled() is False

        assert structure_actions["Group Selection"].isEnabled() is False
        assert structure_actions["Ungroup"].isEnabled() is False
        assert structure_actions["Move Into..."].isEnabled() is False
        assert structure_actions["Lift To Parent"].isEnabled() is False
        assert structure_actions["Move Up"].isEnabled() is False
        assert structure_actions["Move Down"].isEnabled() is False
        assert structure_actions["Move To Top"].isEnabled() is False
        assert structure_actions["Move To Bottom"].isEnabled() is False
        menu.deleteLater()

        window._clipboard_payload = {"widgets": []}
        window._update_edit_actions()
        menu = window._build_preview_context_menu(None)
        actions = {action.text(): action for action in menu.actions() if action.text()}
        assert actions["Paste"].isEnabled() is True
        menu.deleteLater()

        _close_window(window)

    @pytest.mark.skip(reason="removed quick-move history feature")
    def test_build_preview_context_menu_quick_move_into_shows_recent_placeholder_without_history(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewQuickMovePlaceholderDemo"
        target = WidgetModel("group", name="target")
        child = WidgetModel("label", name="child")
        project = _create_project_only_with_widgets(
            project_dir,
            "PreviewQuickMovePlaceholderDemo",
            sdk_root,
            widgets=[target, child],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([child], primary=child, sync_tree=True, sync_preview=False)

        menu = window._build_preview_context_menu(child)
        structure_menu = _context_submenu(menu, "Structure")
        quick_move_menu = next(action.menu() for action in structure_menu.actions() if action.text() == "Quick Move Into")
        action_texts = [action.text() for action in quick_move_menu.actions()]
        recent_placeholder = next(action for action in quick_move_menu.actions() if action.text() == "(No recent targets yet)")
        repeat_action = next(action for action in quick_move_menu.actions() if action.text() == "Move Into Last Target")
        clear_action = next(action for action in quick_move_menu.actions() if action.text() == "Clear Move Target History")

        assert "Recent Targets" in action_texts
        assert "Other Targets" in action_texts
        assert "History" in action_texts
        assert recent_placeholder.isEnabled() is False
        assert repeat_action.isEnabled() is False
        assert clear_action.isEnabled() is False
        assert _menu_target_labels(quick_move_menu) == ["root_group / target (group)"]

        menu.deleteLater()
        _close_window(window)

    @pytest.mark.skip(reason="removed quick-move history feature")
    def test_build_preview_context_menu_quick_move_into_shows_history_without_targets(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewQuickMoveHistoryOnlyContextMenuDemo"
        target = WidgetModel("group", name="target")
        child = WidgetModel("label", name="child")
        project = _create_project_only_with_widgets(
            project_dir,
            "PreviewQuickMoveHistoryOnlyContextMenuDemo",
            sdk_root,
            widgets=[target, child],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        _open_project_window(window, project, project_dir, sdk_root)

        window._set_selection([child], primary=child, sync_tree=True, sync_preview=True)
        window._move_selection_into_target(
            target,
            target_label="root_group / target (group)",
        )

        window._set_selection([target], primary=target, sync_tree=True, sync_preview=True)
        menu = window._build_preview_context_menu(target)
        structure_menu = _context_submenu(menu, "Structure")
        structure_action = next(action for action in menu.actions() if action.text() == "Structure")
        structure_actions = {action.text(): action for action in structure_menu.actions() if action.text()}
        quick_move_menu = next(action.menu() for action in structure_menu.actions() if action.text() == "Quick Move Into")
        quick_action_texts = [action.text() for action in quick_move_menu.actions()]
        repeat_action = next(action for action in quick_move_menu.actions() if action.text() == "Move Into Last Target")
        clear_action = next(action for action in quick_move_menu.actions() if action.text() == "Clear Move Target History")

        assert structure_action.isEnabled() is True
        assert structure_actions["Quick Move Into"].menu() is not None
        assert structure_actions["Quick Move Into"].isEnabled() is window._quick_move_into_menu.menuAction().isEnabled()
        assert structure_actions["Quick Move Into"].toolTip() == window._quick_move_into_menu.menuAction().toolTip()
        assert "(No eligible target containers)" in quick_action_texts
        assert "History" in quick_action_texts
        assert repeat_action.isEnabled() is False
        assert clear_action.isEnabled() is True
        assert _menu_target_labels(quick_move_menu) == []

        menu.deleteLater()
        _close_window(window)

    @pytest.mark.skip(reason="removed quick-move history feature")
    def test_build_preview_context_menu_quick_move_into_follows_recent_target_history(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewQuickMoveHistoryOrderingDemo"
        target_a = WidgetModel("group", name="target_a")
        target_b = WidgetModel("group", name="target_b")
        target_c = WidgetModel("group", name="target_c")
        first = WidgetModel("label", name="first")
        second = WidgetModel("button", name="second")
        third = WidgetModel("switch", name="third")
        project = _create_project_only_with_widgets(
            project_dir,
            "PreviewQuickMoveHistoryOrderingDemo",
            sdk_root,
            widgets=[target_a, target_b, target_c, first, second, third],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        _open_project_window(window, project, project_dir, sdk_root)

        window._set_selection([first], primary=first, sync_tree=True, sync_preview=True)
        window._move_selection_into_target(
            target_c,
            target_label="root_group / target_c (group)",
        )
        window._set_selection([second], primary=second, sync_tree=True, sync_preview=True)
        window._move_selection_into_target(
            target_b,
            target_label="root_group / target_b (group)",
        )

        window._set_selection([third], primary=third, sync_tree=True, sync_preview=True)
        menu = window._build_preview_context_menu(third)
        structure_menu = _context_submenu(menu, "Structure")
        quick_move_menu = next(action.menu() for action in structure_menu.actions() if action.text() == "Quick Move Into")

        assert _menu_target_labels(quick_move_menu)[:3] == [
            "root_group / target_b (group)",
            "root_group / target_c (group)",
            "root_group / target_a (group)",
        ]
        assert "Recent Targets" in [action.text() for action in quick_move_menu.actions()]
        assert "Other Targets" in [action.text() for action in quick_move_menu.actions()]

        menu.deleteLater()
        _close_window(window)

    @pytest.mark.skip(reason="removed quick-move history feature")
    def test_build_preview_context_menu_quick_move_labels_follow_target_rename(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewQuickMoveRenameDemo"
        target = WidgetModel("group", name="target")
        first = WidgetModel("label", name="first")
        second = WidgetModel("button", name="second")
        project = _create_project_only_with_widgets(
            project_dir,
            "PreviewQuickMoveRenameDemo",
            sdk_root,
            widgets=[target, first, second],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        _open_project_window(window, project, project_dir, sdk_root)

        window._set_selection([first], primary=first, sync_tree=True, sync_preview=True)
        window._move_selection_into_target(
            target,
            target_label="root_group / target (group)",
        )

        target.name = "renamed_target"
        window.widget_tree.rebuild_tree()
        window._set_selection([second], primary=second, sync_tree=True, sync_preview=True)

        menu = window._build_preview_context_menu(second)
        structure_menu = _context_submenu(menu, "Structure")
        structure_actions = {action.text(): action for action in structure_menu.actions() if action.text()}
        quick_move_menu = next(action.menu() for action in structure_menu.actions() if action.text() == "Quick Move Into")

        assert window.widget_tree.remembered_move_target_label() == "root_group / renamed_target (group)"
        assert "root_group / renamed_target (group)" in structure_actions["Move Into Last Target"].toolTip()
        assert _menu_target_labels(quick_move_menu)[0] == "root_group / renamed_target (group)"

        menu.deleteLater()
        _close_window(window)

    @pytest.mark.skip(reason="removed quick-move history feature")
    def test_preview_context_menu_move_into_last_target_is_scoped_per_page(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewPerPageMoveIntoDemo"
        main_target = WidgetModel("group", name="main_target")
        main_first = WidgetModel("label", name="main_first")
        main_second = WidgetModel("button", name="main_second")
        detail_target = WidgetModel("group", name="detail_target")
        detail_first = WidgetModel("label", name="detail_first")
        detail_second = WidgetModel("button", name="detail_second")
        project = _create_project_only_with_page_widgets(
            project_dir,
            "PreviewPerPageMoveIntoDemo",
            sdk_root,
            page_widgets={
                "main_page": [main_target, main_first, main_second],
                "detail_page": [detail_target, detail_first, detail_second],
            },
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        _open_project_window(window, project, project_dir, sdk_root)

        window._set_selection([main_first], primary=main_first, sync_tree=True, sync_preview=True)
        window._move_selection_into_target(
            main_target,
            target_label="root_group / main_target (group)",
        )

        window._switch_page("detail_page")
        window._set_selection([detail_first], primary=detail_first, sync_tree=True, sync_preview=True)
        window._move_selection_into_target(
            detail_target,
            target_label="root_group / detail_target (group)",
        )

        window._switch_page("main_page")
        window._set_selection([main_second], primary=main_second, sync_tree=True, sync_preview=True)
        menu = window._build_preview_context_menu(main_second)
        structure_menu = _context_submenu(menu, "Structure")
        structure_actions = {action.text(): action for action in structure_menu.actions() if action.text()}
        assert window.widget_tree.remembered_move_target_label() == "root_group / main_target (group)"
        assert "root_group / main_target (group)" in structure_actions["Move Into Last Target"].toolTip()
        assert "detail_target" not in structure_actions["Move Into Last Target"].toolTip()
        structure_actions["Move Into Last Target"].trigger()
        assert main_second.parent is main_target
        menu.deleteLater()

        window._switch_page("detail_page")
        window._set_selection([detail_second], primary=detail_second, sync_tree=True, sync_preview=True)
        menu = window._build_preview_context_menu(detail_second)
        structure_menu = _context_submenu(menu, "Structure")
        structure_actions = {action.text(): action for action in structure_menu.actions() if action.text()}
        assert window.widget_tree.remembered_move_target_label() == "root_group / detail_target (group)"
        assert "root_group / detail_target (group)" in structure_actions["Move Into Last Target"].toolTip()
        assert "main_target" not in structure_actions["Move Into Last Target"].toolTip()
        structure_actions["Move Into Last Target"].trigger()
        assert detail_second.parent is detail_target
        assert window.statusBar().currentMessage() == "Moved 1 widget(s) into detail_target."
        menu.deleteLater()

        window._undo_manager.mark_all_saved()
        _close_window(window)

    @pytest.mark.skip(reason="removed quick-move history feature")
    def test_preview_context_menu_quick_move_actions_update_selection_and_history(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewQuickMoveActionsDemo"
        target = WidgetModel("group", name="target")
        first = WidgetModel("label", name="first")
        second = WidgetModel("button", name="second")
        third = WidgetModel("switch", name="third")
        project = _create_project_only_with_widgets(
            project_dir,
            "PreviewQuickMoveActionsDemo",
            sdk_root,
            widgets=[target, first, second, third],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        _open_project_window(window, project, project_dir, sdk_root)

        window._set_selection([first], primary=first, sync_tree=True, sync_preview=True)
        window._move_selection_into_target(
            target,
            target_label="root_group / target (group)",
        )

        window._set_selection([second], primary=second, sync_tree=True, sync_preview=True)
        menu = window._build_preview_context_menu(second)
        structure_menu = _context_submenu(menu, "Structure")
        quick_move_menu = next(action.menu() for action in structure_menu.actions() if action.text() == "Quick Move Into")
        quick_action = next(action for action in quick_move_menu.actions() if action.text() == "root_group / target (group)")
        quick_action.trigger()

        assert second.parent is target
        assert window._selection_state.widgets == [second]
        assert window.widget_tree.selected_widgets() == [second]
        assert window.preview_panel.selected_widgets() == [second]
        assert window.widget_tree.recent_move_target_labels() == ["root_group / target (group)"]
        assert window._undo_manager.get_stack("main_page").current_label() == "move into container"
        assert window.statusBar().currentMessage() == "Moved 1 widget(s) into target."
        menu.deleteLater()

        window._set_selection([third], primary=third, sync_tree=True, sync_preview=True)
        menu = window._build_preview_context_menu(third)
        structure_menu = _context_submenu(menu, "Structure")
        structure_actions = {action.text(): action for action in structure_menu.actions() if action.text()}
        assert structure_actions["Move Into Last Target"].isEnabled() is True
        assert structure_actions["Clear Move Target History"].isEnabled() is True
        assert "root_group / target (group)" in structure_actions["Move Into Last Target"].toolTip()
        structure_actions["Move Into Last Target"].trigger()

        assert third.parent is target
        assert window._selection_state.widgets == [third]
        assert window.widget_tree.selected_widgets() == [third]
        assert window.preview_panel.selected_widgets() == [third]
        assert window._undo_manager.get_stack("main_page").current_label() == "move into container"
        assert window.statusBar().currentMessage() == "Moved 1 widget(s) into target."
        menu.deleteLater()

        menu = window._build_preview_context_menu(third)
        structure_menu = _context_submenu(menu, "Structure")
        structure_actions = {action.text(): action for action in structure_menu.actions() if action.text()}
        assert structure_actions["Clear Move Target History"].isEnabled() is True
        assert "Forget 1 recent move-into target" in structure_actions["Clear Move Target History"].toolTip()
        structure_actions["Clear Move Target History"].trigger()

        assert window.widget_tree.recent_move_target_labels() == []
        assert window.statusBar().currentMessage() == "Cleared 1 recent move target."
        menu.deleteLater()

        menu = window._build_preview_context_menu(third)
        structure_menu = _context_submenu(menu, "Structure")
        structure_actions = {action.text(): action for action in structure_menu.actions() if action.text()}
        assert structure_actions["Move Into Last Target"].isEnabled() is False
        assert structure_actions["Clear Move Target History"].isEnabled() is False
        menu.deleteLater()

        window._undo_manager.mark_all_saved()
        _close_window(window)

    @pytest.mark.skip(reason="removed quick-move history feature")
    def test_preview_context_menu_quick_move_submenu_history_actions_update_selection_and_history(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewQuickMoveHistorySubmenuDemo"
        target = WidgetModel("group", name="target")
        first = WidgetModel("label", name="first")
        second = WidgetModel("button", name="second")
        project = _create_project_only_with_widgets(
            project_dir,
            "PreviewQuickMoveHistorySubmenuDemo",
            sdk_root,
            widgets=[target, first, second],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        _open_project_window(window, project, project_dir, sdk_root)

        window._set_selection([first], primary=first, sync_tree=True, sync_preview=True)
        window._move_selection_into_target(
            target,
            target_label="root_group / target (group)",
        )

        window._set_selection([second], primary=second, sync_tree=True, sync_preview=True)
        menu = window._build_preview_context_menu(second)
        structure_menu = _context_submenu(menu, "Structure")
        quick_move_menu = next(action.menu() for action in structure_menu.actions() if action.text() == "Quick Move Into")
        repeat_action = next(action for action in quick_move_menu.actions() if action.text() == "Move Into Last Target")
        clear_action = next(action for action in quick_move_menu.actions() if action.text() == "Clear Move Target History")
        assert repeat_action.isEnabled() is True
        assert clear_action.isEnabled() is True
        assert "root_group / target (group)" in repeat_action.toolTip()
        repeat_action.trigger()

        assert second.parent is target
        assert window._selection_state.widgets == [second]
        assert window.widget_tree.selected_widgets() == [second]
        assert window.preview_panel.selected_widgets() == [second]
        assert window.statusBar().currentMessage() == "Moved 1 widget(s) into target."
        menu.deleteLater()

        menu = window._build_preview_context_menu(second)
        structure_menu = _context_submenu(menu, "Structure")
        quick_move_menu = next(action.menu() for action in structure_menu.actions() if action.text() == "Quick Move Into")
        clear_action = next(action for action in quick_move_menu.actions() if action.text() == "Clear Move Target History")
        assert clear_action.isEnabled() is True
        assert "Forget 1 recent move-into target" in clear_action.toolTip()
        clear_action.trigger()

        assert window.widget_tree.recent_move_target_labels() == []
        assert window.statusBar().currentMessage() == "Cleared 1 recent move target."
        menu.deleteLater()

        menu = window._build_preview_context_menu(second)
        structure_menu = _context_submenu(menu, "Structure")
        quick_move_menu = next(action.menu() for action in structure_menu.actions() if action.text() == "Quick Move Into")
        repeat_action = next(action for action in quick_move_menu.actions() if action.text() == "Move Into Last Target")
        clear_action = next(action for action in quick_move_menu.actions() if action.text() == "Clear Move Target History")
        assert repeat_action.isEnabled() is False
        assert clear_action.isEnabled() is False
        menu.deleteLater()

        window._undo_manager.mark_all_saved()
        _close_window(window)

    @pytest.mark.skip(reason="removed quick-move history feature")
    def test_preview_context_menu_clear_move_target_history_reports_plural_count(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewClearMoveHistoryCountDemo"
        target_a = WidgetModel("group", name="target_a")
        target_b = WidgetModel("group", name="target_b")
        first = WidgetModel("label", name="first")
        second = WidgetModel("button", name="second")
        third = WidgetModel("switch", name="third")
        project = _create_project_only_with_widgets(
            project_dir,
            "PreviewClearMoveHistoryCountDemo",
            sdk_root,
            widgets=[target_a, target_b, first, second, third],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        _open_project_window(window, project, project_dir, sdk_root)

        window._set_selection([first], primary=first, sync_tree=True, sync_preview=True)
        window._move_selection_into_target(
            target_a,
            target_label="root_group / target_a (group)",
        )
        window._set_selection([second], primary=second, sync_tree=True, sync_preview=True)
        window._move_selection_into_target(
            target_b,
            target_label="root_group / target_b (group)",
        )

        window._set_selection([third], primary=third, sync_tree=True, sync_preview=True)
        menu = window._build_preview_context_menu(third)
        structure_menu = _context_submenu(menu, "Structure")
        structure_actions = {action.text(): action for action in structure_menu.actions() if action.text()}

        assert structure_actions["Clear Move Target History"].isEnabled() is True
        assert "Forget 2 recent move-into targets" in structure_actions["Clear Move Target History"].toolTip()
        structure_actions["Clear Move Target History"].trigger()

        assert window.widget_tree.recent_move_target_labels() == []
        assert window.statusBar().currentMessage() == "Cleared 2 recent move targets."
        menu.deleteLater()

        menu = window._build_preview_context_menu(third)
        structure_menu = _context_submenu(menu, "Structure")
        structure_actions = {action.text(): action for action in structure_menu.actions() if action.text()}
        assert structure_actions["Clear Move Target History"].isEnabled() is False
        menu.deleteLater()

        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_preview_context_menu_select_actions_sync_selection(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewSelectContextMenuDemo"
        other = WidgetModel("label", name="other", x=8, y=8, width=40, height=16)
        container = WidgetModel("group", name="container", x=10, y=24, width=120, height=80)
        child_a = WidgetModel("switch", name="child_a", x=4, y=4, width=32, height=16)
        child_b = WidgetModel("button", name="child_b", x=4, y=28, width=48, height=20)
        _add_widget_children(container, [child_a, child_b])
        project = _create_project_only_with_widgets(
            project_dir,
            "PreviewSelectContextMenuDemo",
            sdk_root,
            widgets=[other, container],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([other], primary=other, sync_tree=True, sync_preview=True)

        menu = window._build_preview_context_menu(container)
        select_menu = next(action.menu() for action in menu.actions() if action.text() == "Select")
        select_children_action = next(action for action in select_menu.actions() if action.text() == "Children")
        select_children_action.trigger()

        assert window._selection_state.primary is child_a
        assert window._selection_state.widgets == [child_a, child_b]
        assert window.widget_tree.selected_widgets() == [child_a, child_b]
        assert window.preview_panel.selected_widgets() == [child_a, child_b]
        assert window.statusBar().currentMessage() == "Selected 2 child widgets of container."
        _close_window(window)

    def test_preview_context_menu_parent_and_siblings_actions_sync_selection(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewParentAndSiblingsContextMenuDemo"
        other = WidgetModel("label", name="other", x=8, y=8, width=40, height=16)
        container = WidgetModel("group", name="container", x=10, y=24, width=120, height=80)
        child_a = WidgetModel("switch", name="child_a", x=4, y=4, width=32, height=16)
        child_b = WidgetModel("button", name="child_b", x=4, y=28, width=48, height=20)
        child_c = WidgetModel("label", name="child_c", x=4, y=52, width=48, height=16)
        _add_widget_children(container, [child_a, child_b, child_c])
        project = _create_project_only_with_widgets(
            project_dir,
            "PreviewParentAndSiblingsContextMenuDemo",
            sdk_root,
            widgets=[other, container],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([other], primary=other, sync_tree=True, sync_preview=True)

        parent_menu = window._build_preview_context_menu(child_a)
        parent_select_menu = next(action.menu() for action in parent_menu.actions() if action.text() == "Select")
        select_parent_action = next(action for action in parent_select_menu.actions() if action.text() == "Parent")
        select_parent_action.trigger()
        assert window._selection_state.primary is container
        assert window._selection_state.widgets == [container]
        assert window.widget_tree.selected_widgets() == [container]
        assert window.preview_panel.selected_widgets() == [container]
        assert window.statusBar().currentMessage() == "Selected parent widget: container."

        siblings_menu = window._build_preview_context_menu(child_b)
        siblings_select_menu = next(action.menu() for action in siblings_menu.actions() if action.text() == "Select")
        select_siblings_action = next(action for action in siblings_select_menu.actions() if action.text() == "Siblings")
        select_siblings_action.trigger()
        assert window._selection_state.primary is child_b
        assert window._selection_state.widgets == [child_a, child_b, child_c]
        assert window.widget_tree.selected_widgets() == [child_a, child_b, child_c]
        assert window.preview_panel.selected_widgets() == [child_a, child_b, child_c]
        assert window.statusBar().currentMessage() == "Selected 3 widgets under container."
        _close_window(window)

    def test_preview_context_menu_adjacent_sibling_actions_sync_selection(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewSiblingTraversalContextMenuDemo"
        container = WidgetModel("group", name="container", x=10, y=24, width=120, height=80)
        child_a = WidgetModel("switch", name="child_a", x=4, y=4, width=32, height=16)
        child_b = WidgetModel("button", name="child_b", x=4, y=28, width=48, height=20)
        child_c = WidgetModel("label", name="child_c", x=4, y=52, width=48, height=16)
        _add_widget_children(container, [child_a, child_b, child_c])
        project = _create_project_only_with_widgets(
            project_dir,
            "PreviewSiblingTraversalContextMenuDemo",
            sdk_root,
            widgets=[container],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([container], primary=container, sync_tree=True, sync_preview=True)

        previous_menu = window._build_preview_context_menu(child_b)
        previous_select_menu = next(action.menu() for action in previous_menu.actions() if action.text() == "Select")
        select_previous_action = next(action for action in previous_select_menu.actions() if action.text() == "Previous Sibling")
        select_previous_action.trigger()
        assert window._selection_state.primary is child_a
        assert window._selection_state.widgets == [child_a]
        assert window.widget_tree.selected_widgets() == [child_a]
        assert window.preview_panel.selected_widgets() == [child_a]
        assert window.statusBar().currentMessage() == "Selected previous sibling: child_a."

        next_menu = window._build_preview_context_menu(child_b)
        next_select_menu = next(action.menu() for action in next_menu.actions() if action.text() == "Select")
        select_next_action = next(action for action in next_select_menu.actions() if action.text() == "Next Sibling")
        select_next_action.trigger()
        assert window._selection_state.primary is child_c
        assert window._selection_state.widgets == [child_c]
        assert window.widget_tree.selected_widgets() == [child_c]
        assert window.preview_panel.selected_widgets() == [child_c]
        assert window.statusBar().currentMessage() == "Selected next sibling: child_c."
        _close_window(window)

    def test_preview_context_menu_sibling_range_actions_sync_selection(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewSiblingRangeContextMenuDemo"
        container = WidgetModel("group", name="container", x=10, y=24, width=120, height=80)
        child_a = WidgetModel("switch", name="child_a", x=4, y=4, width=32, height=16)
        child_b = WidgetModel("button", name="child_b", x=4, y=28, width=48, height=20)
        child_c = WidgetModel("label", name="child_c", x=4, y=52, width=48, height=16)
        _add_widget_children(container, [child_a, child_b, child_c])
        project = _create_project_only_with_widgets(
            project_dir,
            "PreviewSiblingRangeContextMenuDemo",
            sdk_root,
            widgets=[container],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([container], primary=container, sync_tree=True, sync_preview=True)

        previous_siblings_menu = window._build_preview_context_menu(child_c)
        previous_siblings_select_menu = next(action.menu() for action in previous_siblings_menu.actions() if action.text() == "Select")
        select_previous_siblings_action = next(
            action for action in previous_siblings_select_menu.actions() if action.text() == "Previous Siblings"
        )
        select_previous_siblings_action.trigger()
        assert window._selection_state.primary is child_b
        assert window._selection_state.widgets == [child_a, child_b]
        assert window.widget_tree.selected_widgets() == [child_a, child_b]
        assert window.preview_panel.selected_widgets() == [child_a, child_b]
        assert window.statusBar().currentMessage() == "Selected 2 previous sibling widgets before child_c."

        next_siblings_menu = window._build_preview_context_menu(child_a)
        next_siblings_select_menu = next(action.menu() for action in next_siblings_menu.actions() if action.text() == "Select")
        select_next_siblings_action = next(
            action for action in next_siblings_select_menu.actions() if action.text() == "Next Siblings"
        )
        select_next_siblings_action.trigger()
        assert window._selection_state.primary is child_b
        assert window._selection_state.widgets == [child_b, child_c]
        assert window.widget_tree.selected_widgets() == [child_b, child_c]
        assert window.preview_panel.selected_widgets() == [child_b, child_c]
        assert window.statusBar().currentMessage() == "Selected 2 next sibling widgets after child_a."
        _close_window(window)

    def test_preview_context_menu_child_navigation_actions_sync_selection(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewChildTraversalContextMenuDemo"
        container = WidgetModel("group", name="container", x=10, y=24, width=120, height=80)
        child_a = WidgetModel("switch", name="child_a", x=4, y=4, width=32, height=16)
        child_b = WidgetModel("button", name="child_b", x=4, y=28, width=48, height=20)
        child_c = WidgetModel("label", name="child_c", x=4, y=52, width=48, height=16)
        _add_widget_children(container, [child_a, child_b, child_c])
        project, root = _create_project_and_root_with_widgets(
            project_dir,
            "PreviewChildTraversalContextMenuDemo",
            sdk_root,
            widgets=[container],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([root], primary=root, sync_tree=True, sync_preview=True)

        first_child_menu = window._build_preview_context_menu(container)
        first_child_select_menu = next(action.menu() for action in first_child_menu.actions() if action.text() == "Select")
        select_first_child_action = next(action for action in first_child_select_menu.actions() if action.text() == "First Child")
        select_first_child_action.trigger()
        assert window._selection_state.primary is child_a
        assert window._selection_state.widgets == [child_a]
        assert window.widget_tree.selected_widgets() == [child_a]
        assert window.preview_panel.selected_widgets() == [child_a]
        assert window.statusBar().currentMessage() == "Selected first child: child_a."

        last_child_menu = window._build_preview_context_menu(container)
        last_child_select_menu = next(action.menu() for action in last_child_menu.actions() if action.text() == "Select")
        select_last_child_action = next(action for action in last_child_select_menu.actions() if action.text() == "Last Child")
        select_last_child_action.trigger()
        assert window._selection_state.primary is child_c
        assert window._selection_state.widgets == [child_c]
        assert window.widget_tree.selected_widgets() == [child_c]
        assert window.preview_panel.selected_widgets() == [child_c]
        assert window.statusBar().currentMessage() == "Selected last child: child_c."
        _close_window(window)

    def test_preview_context_menu_tree_navigation_actions_sync_selection(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewTreeTraversalContextMenuDemo"
        other = WidgetModel("label", name="other", x=8, y=8, width=40, height=16)
        container = WidgetModel("group", name="container", x=10, y=24, width=120, height=80)
        child_a = WidgetModel("switch", name="child_a", x=4, y=4, width=32, height=16)
        child_b = WidgetModel("button", name="child_b", x=4, y=28, width=48, height=20)
        _add_widget_children(container, [child_a, child_b])
        project = _create_project_only_with_widgets(
            project_dir,
            "PreviewTreeTraversalContextMenuDemo",
            sdk_root,
            widgets=[other, container],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([container], primary=container, sync_tree=True, sync_preview=True)

        previous_in_tree_menu = window._build_preview_context_menu(container)
        previous_in_tree_select_menu = next(action.menu() for action in previous_in_tree_menu.actions() if action.text() == "Select")
        select_previous_in_tree_action = next(
            action for action in previous_in_tree_select_menu.actions() if action.text() == "Previous In Tree"
        )
        select_previous_in_tree_action.trigger()
        assert window._selection_state.primary is other
        assert window._selection_state.widgets == [other]
        assert window.widget_tree.selected_widgets() == [other]
        assert window.preview_panel.selected_widgets() == [other]
        assert window.statusBar().currentMessage() == "Selected previous widget in tree order: other."

        next_in_tree_menu = window._build_preview_context_menu(container)
        next_in_tree_select_menu = next(action.menu() for action in next_in_tree_menu.actions() if action.text() == "Select")
        select_next_in_tree_action = next(
            action for action in next_in_tree_select_menu.actions() if action.text() == "Next In Tree"
        )
        select_next_in_tree_action.trigger()
        assert window._selection_state.primary is child_a
        assert window._selection_state.widgets == [child_a]
        assert window.widget_tree.selected_widgets() == [child_a]
        assert window.preview_panel.selected_widgets() == [child_a]
        assert window.statusBar().currentMessage() == "Selected next widget in tree order: child_a."
        _close_window(window)

    def test_preview_context_menu_descendants_action_syncs_selection(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewDescendantsContextMenuDemo"
        other = WidgetModel("label", name="other", x=8, y=8, width=40, height=16)
        container = WidgetModel("group", name="container", x=10, y=24, width=120, height=80)
        child_a = WidgetModel("switch", name="child_a", x=4, y=4, width=32, height=16)
        nested_group = WidgetModel("group", name="nested_group", x=4, y=28, width=60, height=40)
        nested_leaf = WidgetModel("label", name="nested_leaf", x=2, y=2, width=32, height=16)
        _add_widget_children(nested_group, [nested_leaf])
        _add_widget_children(container, [child_a, nested_group])
        project = _create_project_only_with_widgets(
            project_dir,
            "PreviewDescendantsContextMenuDemo",
            sdk_root,
            widgets=[other, container],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([other], primary=other, sync_tree=True, sync_preview=True)

        menu = window._build_preview_context_menu(container)
        select_menu = next(action.menu() for action in menu.actions() if action.text() == "Select")
        select_descendants_action = next(action for action in select_menu.actions() if action.text() == "Descendants")
        select_descendants_action.trigger()

        assert window._selection_state.primary is child_a
        assert window._selection_state.widgets == [child_a, nested_group, nested_leaf]
        assert window.widget_tree.selected_widgets() == [child_a, nested_group, nested_leaf]
        assert window.preview_panel.selected_widgets() == [child_a, nested_group, nested_leaf]
        assert window.statusBar().currentMessage() == "Selected 3 descendant widgets of container."
        _close_window(window)

    def test_preview_context_menu_ancestors_action_syncs_selection(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewAncestorsContextMenuDemo"
        other = WidgetModel("label", name="other", x=8, y=8, width=40, height=16)
        container = WidgetModel("group", name="container", x=10, y=24, width=120, height=80)
        nested_group = WidgetModel("group", name="nested_group", x=4, y=28, width=60, height=40)
        nested_leaf = WidgetModel("label", name="nested_leaf", x=2, y=2, width=32, height=16)
        _add_widget_children(nested_group, [nested_leaf])
        _add_widget_children(container, [nested_group])
        project, root = _create_project_and_root_with_widgets(
            project_dir,
            "PreviewAncestorsContextMenuDemo",
            sdk_root,
            widgets=[other, container],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([other], primary=other, sync_tree=True, sync_preview=True)

        menu = window._build_preview_context_menu(nested_leaf)
        select_menu = next(action.menu() for action in menu.actions() if action.text() == "Select")
        select_ancestors_action = next(action for action in select_menu.actions() if action.text() == "Ancestors")
        select_ancestors_action.trigger()

        assert window._selection_state.primary is nested_group
        assert window._selection_state.widgets == [root, container, nested_group]
        assert window.widget_tree.selected_widgets() == [root, container, nested_group]
        assert window.preview_panel.selected_widgets() == [root, container, nested_group]
        assert window.statusBar().currentMessage() == "Selected 3 ancestor widgets of nested_leaf."
        _close_window(window)

    def test_preview_context_menu_root_action_syncs_selection(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewRootContextMenuDemo"
        other = WidgetModel("label", name="other", x=8, y=8, width=40, height=16)
        container = WidgetModel("group", name="container", x=10, y=24, width=120, height=80)
        nested_group = WidgetModel("group", name="nested_group", x=4, y=28, width=60, height=40)
        nested_leaf = WidgetModel("label", name="nested_leaf", x=2, y=2, width=32, height=16)
        _add_widget_children(nested_group, [nested_leaf])
        _add_widget_children(container, [nested_group])
        project, root = _create_project_and_root_with_widgets(
            project_dir,
            "PreviewRootContextMenuDemo",
            sdk_root,
            widgets=[other, container],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([other], primary=other, sync_tree=True, sync_preview=True)

        menu = window._build_preview_context_menu(nested_leaf)
        select_menu = next(action.menu() for action in menu.actions() if action.text() == "Select")
        select_root_action = next(action for action in select_menu.actions() if action.text() == "Root")
        select_root_action.trigger()

        assert window._selection_state.primary is root
        assert window._selection_state.widgets == [root]
        assert window.widget_tree.selected_widgets() == [root]
        assert window.preview_panel.selected_widgets() == [root]
        assert window.statusBar().currentMessage() == "Selected page root: root_group."
        _close_window(window)

    def test_preview_context_menu_path_action_syncs_selection(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewPathContextMenuDemo"
        other = WidgetModel("label", name="other", x=8, y=8, width=40, height=16)
        container = WidgetModel("group", name="container", x=10, y=24, width=120, height=80)
        nested_group = WidgetModel("group", name="nested_group", x=4, y=28, width=60, height=40)
        nested_leaf = WidgetModel("label", name="nested_leaf", x=2, y=2, width=32, height=16)
        _add_widget_children(nested_group, [nested_leaf])
        _add_widget_children(container, [nested_group])
        project, root = _create_project_and_root_with_widgets(
            project_dir,
            "PreviewPathContextMenuDemo",
            sdk_root,
            widgets=[other, container],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([other], primary=other, sync_tree=True, sync_preview=True)

        menu = window._build_preview_context_menu(nested_leaf)
        select_menu = next(action.menu() for action in menu.actions() if action.text() == "Select")
        select_path_action = next(action for action in select_menu.actions() if action.text() == "Path")
        select_path_action.trigger()

        assert window._selection_state.primary is nested_leaf
        assert window._selection_state.widgets == [root, container, nested_group, nested_leaf]
        assert window.widget_tree.selected_widgets() == [root, container, nested_group, nested_leaf]
        assert window.preview_panel.selected_widgets() == [root, container, nested_group, nested_leaf]
        assert window.statusBar().currentMessage() == "Selected 4 widgets in path to nested_leaf."
        _close_window(window)

    def test_preview_context_menu_top_level_action_syncs_selection(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewTopLevelContextMenuDemo"
        other = WidgetModel("label", name="other", x=8, y=8, width=40, height=16)
        container = WidgetModel("group", name="container", x=10, y=24, width=120, height=80)
        nested_group = WidgetModel("group", name="nested_group", x=4, y=28, width=60, height=40)
        nested_leaf = WidgetModel("label", name="nested_leaf", x=2, y=2, width=32, height=16)
        same_type = WidgetModel("button", name="same_type", x=8, y=120, width=48, height=20)
        _add_widget_children(nested_group, [nested_leaf])
        _add_widget_children(container, [nested_group])
        project = _create_project_only_with_widgets(
            project_dir,
            "PreviewTopLevelContextMenuDemo",
            sdk_root,
            widgets=[other, container, same_type],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([other], primary=other, sync_tree=True, sync_preview=True)

        menu = window._build_preview_context_menu(nested_leaf)
        select_menu = next(action.menu() for action in menu.actions() if action.text() == "Select")
        select_top_level_action = next(action for action in select_menu.actions() if action.text() == "Top-Level")
        select_top_level_action.trigger()

        assert window._selection_state.primary is container
        assert window._selection_state.widgets == [other, container, same_type]
        assert window.widget_tree.selected_widgets() == [other, container, same_type]
        assert window.preview_panel.selected_widgets() == [other, container, same_type]
        assert window.statusBar().currentMessage() == "Selected 3 top-level widgets on this page."
        _close_window(window)

    def test_preview_context_menu_subtree_action_syncs_selection(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewSubtreeContextMenuDemo"
        other = WidgetModel("label", name="other", x=8, y=8, width=40, height=16)
        container = WidgetModel("group", name="container", x=10, y=24, width=120, height=80)
        child_a = WidgetModel("switch", name="child_a", x=4, y=4, width=32, height=16)
        nested_group = WidgetModel("group", name="nested_group", x=4, y=28, width=60, height=40)
        nested_leaf = WidgetModel("label", name="nested_leaf", x=2, y=2, width=32, height=16)
        _add_widget_children(nested_group, [nested_leaf])
        _add_widget_children(container, [child_a, nested_group])
        project = _create_project_only_with_widgets(
            project_dir,
            "PreviewSubtreeContextMenuDemo",
            sdk_root,
            widgets=[other, container],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([other], primary=other, sync_tree=True, sync_preview=True)

        menu = window._build_preview_context_menu(container)
        select_menu = next(action.menu() for action in menu.actions() if action.text() == "Select")
        select_subtree_action = next(action for action in select_menu.actions() if action.text() == "Subtree")
        select_subtree_action.trigger()

        assert window._selection_state.primary is container
        assert window._selection_state.widgets == [container, child_a, nested_group, nested_leaf]
        assert window.widget_tree.selected_widgets() == [container, child_a, nested_group, nested_leaf]
        assert window.preview_panel.selected_widgets() == [container, child_a, nested_group, nested_leaf]
        assert window.statusBar().currentMessage() == "Selected 4 widgets in subtree of container."
        _close_window(window)

    def test_preview_context_menu_leaves_action_syncs_selection(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewLeavesContextMenuDemo"
        other = WidgetModel("label", name="other", x=8, y=8, width=40, height=16)
        container = WidgetModel("group", name="container", x=10, y=24, width=120, height=80)
        child_a = WidgetModel("switch", name="child_a", x=4, y=4, width=32, height=16)
        child_b = WidgetModel("button", name="child_b", x=4, y=28, width=48, height=20)
        nested_group = WidgetModel("group", name="nested_group", x=4, y=52, width=60, height=40)
        nested_leaf = WidgetModel("label", name="nested_leaf", x=2, y=2, width=32, height=16)
        _add_widget_children(nested_group, [nested_leaf])
        _add_widget_children(container, [child_a, child_b, nested_group])
        project = _create_project_only_with_widgets(
            project_dir,
            "PreviewLeavesContextMenuDemo",
            sdk_root,
            widgets=[other, container],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([other], primary=other, sync_tree=True, sync_preview=True)

        menu = window._build_preview_context_menu(container)
        select_menu = next(action.menu() for action in menu.actions() if action.text() == "Select")
        select_leaves_action = next(action for action in select_menu.actions() if action.text() == "Leaves")
        select_leaves_action.trigger()

        assert window._selection_state.primary is child_a
        assert window._selection_state.widgets == [child_a, child_b, nested_leaf]
        assert window.widget_tree.selected_widgets() == [child_a, child_b, nested_leaf]
        assert window.preview_panel.selected_widgets() == [child_a, child_b, nested_leaf]
        assert window.statusBar().currentMessage() == "Selected 3 leaf widgets in subtree of container."
        _close_window(window)

    def test_preview_context_menu_containers_action_syncs_selection(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewContainersContextMenuDemo"
        other = WidgetModel("label", name="other", x=8, y=8, width=40, height=16)
        container = WidgetModel("group", name="container", x=10, y=24, width=120, height=80)
        child_a = WidgetModel("switch", name="child_a", x=4, y=4, width=32, height=16)
        nested_group = WidgetModel("group", name="nested_group", x=4, y=28, width=60, height=40)
        nested_leaf = WidgetModel("label", name="nested_leaf", x=2, y=2, width=32, height=16)
        _add_widget_children(nested_group, [nested_leaf])
        _add_widget_children(container, [child_a, nested_group])
        project = _create_project_only_with_widgets(
            project_dir,
            "PreviewContainersContextMenuDemo",
            sdk_root,
            widgets=[other, container],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([other], primary=other, sync_tree=True, sync_preview=True)

        menu = window._build_preview_context_menu(container)
        select_menu = next(action.menu() for action in menu.actions() if action.text() == "Select")
        select_containers_action = next(action for action in select_menu.actions() if action.text() == "Containers")
        select_containers_action.trigger()

        assert window._selection_state.primary is container
        assert window._selection_state.widgets == [container, nested_group]
        assert window.widget_tree.selected_widgets() == [container, nested_group]
        assert window.preview_panel.selected_widgets() == [container, nested_group]
        assert window.statusBar().currentMessage() == "Selected 2 container widgets in subtree of container."
        _close_window(window)

    def test_preview_context_menu_hidden_and_locked_actions_sync_selection(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewStateContextMenuDemo"
        other = WidgetModel("label", name="other", x=8, y=8, width=40, height=16)
        container = WidgetModel("group", name="container", x=10, y=24, width=120, height=80)
        hidden_self = WidgetModel("button", name="hidden_self", x=4, y=4, width=48, height=20)
        hidden_self.designer_hidden = True
        hidden_leaf = WidgetModel("label", name="hidden_leaf", x=4, y=28, width=40, height=16)
        hidden_leaf.designer_hidden = True
        locked_group = WidgetModel("group", name="locked_group", x=4, y=52, width=60, height=40)
        locked_group.designer_locked = True
        locked_leaf = WidgetModel("switch", name="locked_leaf", x=2, y=2, width=32, height=16)
        locked_leaf.designer_locked = True
        _add_widget_children(locked_group, [locked_leaf])
        _add_widget_children(container, [hidden_self, hidden_leaf, locked_group])
        project = _create_project_only_with_widgets(
            project_dir,
            "PreviewStateContextMenuDemo",
            sdk_root,
            widgets=[other, container],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([other], primary=other, sync_tree=True, sync_preview=True)

        visible_menu = window._build_preview_context_menu(container)
        visible_select_menu = next(action.menu() for action in visible_menu.actions() if action.text() == "Select")
        select_visible_action = next(action for action in visible_select_menu.actions() if action.text() == "Visible")
        select_visible_action.trigger()
        assert window._selection_state.primary is container
        assert window._selection_state.widgets == [container, locked_group, locked_leaf]
        assert window.widget_tree.selected_widgets() == [container, locked_group, locked_leaf]
        assert window.preview_panel.selected_widgets() == [container, locked_group, locked_leaf]
        assert window.statusBar().currentMessage() == "Selected 3 visible widgets in subtree of container."

        hidden_menu = window._build_preview_context_menu(container)
        hidden_select_menu = next(action.menu() for action in hidden_menu.actions() if action.text() == "Select")
        select_hidden_action = next(action for action in hidden_select_menu.actions() if action.text() == "Hidden")
        select_hidden_action.trigger()
        assert window._selection_state.primary is hidden_self
        assert window._selection_state.widgets == [hidden_self, hidden_leaf]
        assert window.widget_tree.selected_widgets() == [hidden_self, hidden_leaf]
        assert window.preview_panel.selected_widgets() == [hidden_self, hidden_leaf]
        assert window.statusBar().currentMessage() == "Selected 2 hidden widgets in subtree of container."

        unlocked_menu = window._build_preview_context_menu(container)
        unlocked_select_menu = next(action.menu() for action in unlocked_menu.actions() if action.text() == "Select")
        select_unlocked_action = next(action for action in unlocked_select_menu.actions() if action.text() == "Unlocked")
        select_unlocked_action.trigger()
        assert window._selection_state.primary is container
        assert window._selection_state.widgets == [container, hidden_self, hidden_leaf]
        assert window.widget_tree.selected_widgets() == [container, hidden_self, hidden_leaf]
        assert window.preview_panel.selected_widgets() == [container, hidden_self, hidden_leaf]
        assert window.statusBar().currentMessage() == "Selected 3 unlocked widgets in subtree of container."

        locked_menu = window._build_preview_context_menu(container)
        locked_select_menu = next(action.menu() for action in locked_menu.actions() if action.text() == "Select")
        select_locked_action = next(action for action in locked_select_menu.actions() if action.text() == "Locked")
        select_locked_action.trigger()
        assert window._selection_state.primary is locked_group
        assert window._selection_state.widgets == [locked_group, locked_leaf]
        assert window.widget_tree.selected_widgets() == [locked_group, locked_leaf]
        assert window.preview_panel.selected_widgets() == [locked_group, locked_leaf]
        assert window.statusBar().currentMessage() == "Selected 2 locked widgets in subtree of container."
        _close_window(window)

    def test_preview_context_menu_layout_containers_action_syncs_selection(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewLayoutContainersContextMenuDemo"
        other = WidgetModel("label", name="other", x=8, y=8, width=40, height=16)
        container = WidgetModel("group", name="container", x=10, y=24, width=140, height=100)
        layout_parent = WidgetModel("linearlayout", name="layout_parent", x=4, y=4, width=100, height=60)
        managed_group = WidgetModel("group", name="managed_group", x=2, y=2, width=48, height=24)
        managed_leaf = WidgetModel("label", name="managed_leaf", x=1, y=1, width=24, height=12)
        unmanaged_leaf = WidgetModel("label", name="unmanaged_leaf", x=4, y=72, width=40, height=16)
        _add_widget_children(managed_group, [managed_leaf])
        _add_widget_children(layout_parent, [managed_group])
        _add_widget_children(container, [layout_parent, unmanaged_leaf])
        project = _create_project_only_with_widgets(
            project_dir,
            "PreviewLayoutContainersContextMenuDemo",
            sdk_root,
            widgets=[other, container],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([other], primary=other, sync_tree=True, sync_preview=True)

        menu = window._build_preview_context_menu(container)
        select_menu = next(action.menu() for action in menu.actions() if action.text() == "Select")
        select_layout_action = next(action for action in select_menu.actions() if action.text() == "Layout Containers")
        select_layout_action.trigger()

        assert window._selection_state.primary is layout_parent
        assert window._selection_state.widgets == [layout_parent]
        assert window.widget_tree.selected_widgets() == [layout_parent]
        assert window.preview_panel.selected_widgets() == [layout_parent]
        assert window.statusBar().currentMessage() == "Selected 1 layout container widget in subtree of container."

        menu = window._build_preview_context_menu(layout_parent)
        select_menu = next(action.menu() for action in menu.actions() if action.text() == "Select")
        select_layout_action = next(action for action in select_menu.actions() if action.text() == "Layout Containers")
        select_layout_action.trigger()

        assert window._selection_state.primary is layout_parent
        assert window._selection_state.widgets == [layout_parent]
        assert window.widget_tree.selected_widgets() == [layout_parent]
        assert window.preview_panel.selected_widgets() == [layout_parent]
        assert window.statusBar().currentMessage() == "Selected 1 layout container widget in subtree of layout_parent."
        _close_window(window)

    def test_preview_context_menu_managed_action_syncs_selection(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewManagedContextMenuDemo"
        other = WidgetModel("label", name="other", x=8, y=8, width=40, height=16)
        container = WidgetModel("group", name="container", x=10, y=24, width=140, height=100)
        layout_parent = WidgetModel("linearlayout", name="layout_parent", x=4, y=4, width=100, height=60)
        managed_group = WidgetModel("group", name="managed_group", x=2, y=2, width=48, height=24)
        managed_leaf = WidgetModel("label", name="managed_leaf", x=1, y=1, width=24, height=12)
        managed_button = WidgetModel("button", name="managed_button", x=2, y=30, width=48, height=20)
        unmanaged_leaf = WidgetModel("label", name="unmanaged_leaf", x=4, y=72, width=40, height=16)
        _add_widget_children(managed_group, [managed_leaf])
        _add_widget_children(layout_parent, [managed_group, managed_button])
        _add_widget_children(container, [layout_parent, unmanaged_leaf])
        project = _create_project_only_with_widgets(
            project_dir,
            "PreviewManagedContextMenuDemo",
            sdk_root,
            widgets=[other, container],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([other], primary=other, sync_tree=True, sync_preview=True)

        menu = window._build_preview_context_menu(container)
        select_menu = next(action.menu() for action in menu.actions() if action.text() == "Select")
        select_managed_action = next(action for action in select_menu.actions() if action.text() == "Managed")
        select_managed_action.trigger()

        assert window._selection_state.primary is managed_group
        assert window._selection_state.widgets == [managed_group, managed_button]
        assert window.widget_tree.selected_widgets() == [managed_group, managed_button]
        assert window.preview_panel.selected_widgets() == [managed_group, managed_button]
        assert window.statusBar().currentMessage() == "Selected 2 layout-managed widgets in subtree of container."

        menu = window._build_preview_context_menu(managed_button)
        select_menu = next(action.menu() for action in menu.actions() if action.text() == "Select")
        select_managed_action = next(action for action in select_menu.actions() if action.text() == "Managed")
        select_managed_action.trigger()

        assert window._selection_state.primary is managed_button
        assert window._selection_state.widgets == [managed_button]
        assert window.widget_tree.selected_widgets() == [managed_button]
        assert window.preview_panel.selected_widgets() == [managed_button]
        assert window.statusBar().currentMessage() == "Selected 1 layout-managed widget in subtree of managed_button."
        _close_window(window)

    def test_preview_context_menu_free_position_action_syncs_selection(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewFreePositionContextMenuDemo"
        other = WidgetModel("label", name="other", x=8, y=8, width=40, height=16)
        container = WidgetModel("group", name="container", x=10, y=24, width=140, height=100)
        layout_parent = WidgetModel("linearlayout", name="layout_parent", x=4, y=4, width=100, height=60)
        managed_group = WidgetModel("group", name="managed_group", x=2, y=2, width=48, height=24)
        managed_leaf = WidgetModel("label", name="managed_leaf", x=1, y=1, width=24, height=12)
        managed_button = WidgetModel("button", name="managed_button", x=2, y=30, width=48, height=20)
        unmanaged_leaf = WidgetModel("label", name="unmanaged_leaf", x=4, y=72, width=40, height=16)
        _add_widget_children(managed_group, [managed_leaf])
        _add_widget_children(layout_parent, [managed_group, managed_button])
        _add_widget_children(container, [layout_parent, unmanaged_leaf])
        project = _create_project_only_with_widgets(
            project_dir,
            "PreviewFreePositionContextMenuDemo",
            sdk_root,
            widgets=[other, container],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([other], primary=other, sync_tree=True, sync_preview=True)

        menu = window._build_preview_context_menu(container)
        select_menu = next(action.menu() for action in menu.actions() if action.text() == "Select")
        select_free_position_action = next(action for action in select_menu.actions() if action.text() == "Free Position")
        select_free_position_action.trigger()

        assert window._selection_state.primary is container
        assert window._selection_state.widgets == [container, layout_parent, managed_leaf, unmanaged_leaf]
        assert window.widget_tree.selected_widgets() == [container, layout_parent, managed_leaf, unmanaged_leaf]
        assert window.preview_panel.selected_widgets() == [container, layout_parent, managed_leaf, unmanaged_leaf]
        assert window.statusBar().currentMessage() == "Selected 4 free-position widgets in subtree of container."

        menu = window._build_preview_context_menu(managed_leaf)
        select_menu = next(action.menu() for action in menu.actions() if action.text() == "Select")
        select_free_position_action = next(action for action in select_menu.actions() if action.text() == "Free Position")
        select_free_position_action.trigger()

        assert window._selection_state.primary is managed_leaf
        assert window._selection_state.widgets == [managed_leaf]
        assert window.widget_tree.selected_widgets() == [managed_leaf]
        assert window.preview_panel.selected_widgets() == [managed_leaf]
        assert window.statusBar().currentMessage() == "Selected 1 free-position widget in subtree of managed_leaf."
        _close_window(window)

    def test_preview_context_menu_same_type_action_syncs_selection(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewSameTypeContextMenuDemo"
        other = WidgetModel("label", name="other", x=8, y=8, width=40, height=16)
        first = WidgetModel("button", name="first", x=8, y=28, width=56, height=20)
        second = WidgetModel("button", name="second", x=8, y=56, width=56, height=20)
        project = _create_project_only_with_widgets(
            project_dir,
            "PreviewSameTypeContextMenuDemo",
            sdk_root,
            widgets=[other, first, second],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([other], primary=other, sync_tree=True, sync_preview=True)

        menu = window._build_preview_context_menu(second)
        select_menu = next(action.menu() for action in menu.actions() if action.text() == "Select")
        select_same_type_action = next(action for action in select_menu.actions() if action.text() == "Same Type")
        select_same_type_action.trigger()

        assert window._selection_state.primary is second
        assert window._selection_state.widgets == [first, second]
        assert window.widget_tree.selected_widgets() == [first, second]
        assert window.preview_panel.selected_widgets() == [first, second]
        assert window.statusBar().currentMessage() == "Selected 2 button widgets."
        _close_window(window)

    def test_preview_context_menu_same_parent_type_action_syncs_selection(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewSameParentTypeContextMenuDemo"
        first = WidgetModel("label", name="first", x=8, y=8, width=40, height=16)
        second = WidgetModel("label", name="second", x=8, y=28, width=40, height=16)
        other = WidgetModel("button", name="other", x=8, y=56, width=56, height=20)
        project = _create_project_only_with_widgets(
            project_dir,
            "PreviewSameParentTypeContextMenuDemo",
            sdk_root,
            widgets=[first, second, other],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([other], primary=other, sync_tree=True, sync_preview=True)

        menu = window._build_preview_context_menu(first)
        select_menu = next(action.menu() for action in menu.actions() if action.text() == "Select")
        select_same_parent_type_action = next(action for action in select_menu.actions() if action.text() == "Same Parent Type")
        select_same_parent_type_action.trigger()

        assert window._selection_state.primary is first
        assert window._selection_state.widgets == [first, second]
        assert window.widget_tree.selected_widgets() == [first, second]
        assert window.preview_panel.selected_widgets() == [first, second]
        assert window.statusBar().currentMessage() == "Selected 2 sibling label widgets under root_group."
        _close_window(window)

    def test_preview_context_menu_subtree_type_action_syncs_selection(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewSubtreeTypeContextMenuDemo"
        other = WidgetModel("label", name="other", x=8, y=8, width=40, height=16)
        container = WidgetModel("group", name="container", x=10, y=24, width=120, height=80)
        nested_group = WidgetModel("group", name="nested_group", x=4, y=28, width=60, height=40)
        nested_leaf = WidgetModel("label", name="nested_leaf", x=2, y=2, width=32, height=16)
        _add_widget_children(nested_group, [nested_leaf])
        _add_widget_children(container, [nested_group])
        project, root = _create_project_and_root_with_widgets(
            project_dir,
            "PreviewSubtreeTypeContextMenuDemo",
            sdk_root,
            widgets=[other, container],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([other], primary=other, sync_tree=True, sync_preview=True)

        menu = window._build_preview_context_menu(root)
        select_menu = next(action.menu() for action in menu.actions() if action.text() == "Select")
        select_subtree_type_action = next(action for action in select_menu.actions() if action.text() == "Subtree Type")
        select_subtree_type_action.trigger()

        assert window._selection_state.primary is root
        assert window._selection_state.widgets == [root, container, nested_group]
        assert window.widget_tree.selected_widgets() == [root, container, nested_group]
        assert window.preview_panel.selected_widgets() == [root, container, nested_group]
        assert window.statusBar().currentMessage() == "Selected 3 group widgets in subtree of root_group."
        _close_window(window)

    def test_preview_context_menu_same_depth_action_syncs_selection(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewSameDepthContextMenuDemo"
        branch_a = WidgetModel("group", name="branch_a", x=8, y=8, width=80, height=80)
        branch_b = WidgetModel("group", name="branch_b", x=100, y=8, width=80, height=80)
        leaf_a = WidgetModel("label", name="leaf_a", x=4, y=4, width=40, height=16)
        leaf_b = WidgetModel("button", name="leaf_b", x=4, y=4, width=48, height=20)
        nested_group = WidgetModel("group", name="nested_group", x=4, y=28, width=50, height=30)
        _add_widget_children(branch_a, [leaf_a, nested_group])
        _add_widget_children(branch_b, [leaf_b])
        project = _create_project_only_with_widgets(
            project_dir,
            "PreviewSameDepthContextMenuDemo",
            sdk_root,
            widgets=[branch_a, branch_b],
        )

        window = MainWindow(str(sdk_root))
        _disable_window_compile(window, _DisabledCompiler)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        _open_project_window(window, project, project_dir, sdk_root)
        window._set_selection([branch_a], primary=branch_a, sync_tree=True, sync_preview=True)

        menu = window._build_preview_context_menu(leaf_a)
        select_menu = next(action.menu() for action in menu.actions() if action.text() == "Select")
        select_same_depth_action = next(action for action in select_menu.actions() if action.text() == "Same Depth")
        select_same_depth_action.trigger()

        assert window._selection_state.primary is leaf_a
        assert window._selection_state.widgets == [leaf_a, nested_group, leaf_b]
        assert window.widget_tree.selected_widgets() == [leaf_a, nested_group, leaf_b]
        assert window.preview_panel.selected_widgets() == [leaf_a, nested_group, leaf_b]
        assert window.statusBar().currentMessage() == "Selected 3 widgets at depth 2."
        _close_window(window)

    def test_preview_failure_switches_back_to_v1_renderer(self, qapp, isolated_config, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        class CompilerWithStopCount(_DisabledCompiler):
            def __init__(self):
                self.stop_calls = 0

            def stop_exe(self):
                self.stop_calls += 1

        window = MainWindow("")
        compiler = CompilerWithStopCount()
        window.compiler = compiler

        switch_calls = []
        monkeypatch.setattr(window._renderer_manager, "switch", lambda engine, fallback="v1": switch_calls.append((engine, fallback)) or "v1")
        monkeypatch.setattr(window, "_show_bottom_panel", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(window, "_update_compile_availability", lambda: None)

        window._handle_preview_failure("forced failure")

        assert compiler.stop_calls == 1
        assert switch_calls == [("v1", "v1")]
        assert window._last_runtime_error_text == "forced failure"

        _close_window(window)

    def test_preview_failure_resumes_pending_external_reload_without_waiting_for_watch_tick(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.ui.main_window import MainWindow

        class CompilerWithStopCount(_DisabledCompiler):
            def __init__(self):
                self.stop_calls = 0

            def stop_exe(self):
                self.stop_calls += 1

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewFailureReloadResumeDemo"
        project = _create_project(project_dir, "PreviewFailureReloadResumeDemo", sdk_root)
        reload_calls = []
        compiler = CompilerWithStopCount()

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", compiler))

        def _capture_reload(*args, **kwargs):
            reload_calls.append(kwargs)
            window._bump_async_generation()
            window._clear_external_reload_pending()
            return True

        monkeypatch.setattr(window, "_reload_project_from_disk", _capture_reload)
        monkeypatch.setattr(window, "_show_bottom_panel", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(window._renderer_manager, "switch", lambda engine, fallback="v1": "v1")

        _open_project_window(window, project, project_dir, sdk_root)

        layout_file = project_dir / ".eguiproject" / "layout" / "main_page.xml"
        window._set_external_reload_pending([os.path.normpath(os.path.abspath(layout_file))])
        monkeypatch.setattr(
            window,
            "_pending_external_reload_changed_paths",
            lambda: [os.path.normpath(os.path.abspath(layout_file))],
        )

        window._handle_preview_failure("forced failure")

        assert reload_calls == [
            {
                "auto": True,
                "changed_paths": [os.path.normpath(os.path.abspath(layout_file))],
            }
        ]
        assert compiler.stop_calls == 1
        assert window._last_runtime_error_text == "forced failure"
        _close_window(window)

    @pytest.mark.skip(reason="removed preview-engine selection feature")
    def test_preview_engine_invalid_name_is_ignored(self, qapp, isolated_config, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")
        window._preview_engine_actions["v1"].setChecked(True)
        window._config.preview_engine = "v1"
        window._state_store.set_preview_engine("v1")

        switch_calls = []
        monkeypatch.setattr(window._renderer_manager, "switch", lambda *args, **kwargs: switch_calls.append(args) or "v2")

        window._set_preview_engine("unknown")

        assert switch_calls == []
        assert window._config.preview_engine == "v1"
        assert window._state_store.state.preview_engine == "v1"
        assert window._preview_engine_actions["v1"].isChecked() is True

        _close_window(window)

