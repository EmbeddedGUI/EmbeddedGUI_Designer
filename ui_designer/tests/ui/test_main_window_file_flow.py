"""Qt UI tests for MainWindow project file flows."""

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtCore import QByteArray, Qt
    from PyQt5.QtWidgets import QApplication, QAbstractItemView
    from PyQt5.QtWidgets import QMessageBox

    _has_pyqt5 = True
except ImportError:
    _has_pyqt5 = False

_skip_no_qt = pytest.mark.skipif(not _has_pyqt5, reason="PyQt5 not available")


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
                widget.close()
            widget.deleteLater()
        except Exception:
            pass
    try:
        app.sendPostedEvents()
    except Exception:
        pass
    app.processEvents()


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    from ui_designer.model.config import DesignerConfig

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_path = config_dir / "config.json"
    legacy_config_dir = tmp_path / "legacy_config"
    legacy_config_path = legacy_config_dir / "config.json"
    monkeypatch.setattr("ui_designer.model.config._get_config_dir", lambda: str(config_dir))
    monkeypatch.setattr("ui_designer.model.config._get_config_path", lambda: str(config_path))
    monkeypatch.setattr("ui_designer.model.config._get_legacy_config_dir", lambda: str(legacy_config_dir))
    monkeypatch.setattr("ui_designer.model.config._get_legacy_config_path", lambda: str(legacy_config_path))
    monkeypatch.setattr("ui_designer.model.config._get_load_config_paths", lambda: [str(config_path), str(legacy_config_path)])
    DesignerConfig._instance = None
    config = DesignerConfig.instance()
    yield config
    DesignerConfig._instance = None


def _create_sdk_root(root):
    (root / "src").mkdir(parents=True)
    (root / "porting" / "designer").mkdir(parents=True)
    (root / "Makefile").write_text("all:\n", encoding="utf-8")


def _create_project(project_dir, app_name, sdk_root=""):
    from ui_designer.model.project import Project

    project = Project(screen_width=240, screen_height=320, app_name=app_name)
    project.sdk_root = str(sdk_root)
    project.project_dir = str(project_dir)
    project.create_new_page("main_page")
    project.save(str(project_dir))
    return project


def _close_window(window):
    undo_manager = getattr(window, "_undo_manager", None)
    if undo_manager is not None:
        try:
            # Avoid headless test teardown entering the unsaved-changes dialog path.
            undo_manager.mark_all_saved()
        except Exception:
            pass
    window.close()
    window.deleteLater()
    app = QApplication.instance()
    if app is not None:
        try:
            app.sendPostedEvents()
        except Exception:
            pass
        app.processEvents()


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


@_skip_no_qt
class TestMainWindowFileFlow:
    def test_open_project_path_accepts_directory(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "OpenDemo"
        _create_project(project_dir, "OpenDemo", sdk_root)

        window = MainWindow(str(sdk_root))
        captured = {}

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
        _close_window(window)

    def test_open_project_uses_recovered_cached_sdk_example_as_default_dir(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        cached_sdk = tmp_path / "config" / "sdk" / "EmbeddedGUI"
        _create_sdk_root(cached_sdk)
        isolated_config.sdk_root = str(tmp_path / "missing_sdk")
        isolated_config.egui_root = str(tmp_path / "missing_sdk")
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
        assert captured["directory"] == os.path.join(os.path.normpath(os.path.abspath(cached_sdk)), "example")
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
        monkeypatch.setattr("ui_designer.ui.main_window.generate_all_files_preserved", lambda *args, **kwargs: {"generated.c": "// generated\n"})

        window._save_project()

        assert (project_dir / "SaveDemo.egui").is_file()
        assert (project_dir / "generated.c").read_text(encoding="utf-8") == "// generated\n"
        assert (project_dir / "build.mk").is_file()
        assert (project_dir / "app_egui_config.h").is_file()
        assert (project_dir / "resource" / "src" / "app_resource_config.json").is_file()
        assert isolated_config.last_project_path == os.path.join(str(project_dir), "SaveDemo.egui")
        assert isolated_config.recent_projects[0]["project_path"] == os.path.join(str(project_dir), "SaveDemo.egui")
        assert window._undo_manager.is_any_dirty() is False
        assert "Saved:" in window.statusBar().currentMessage()
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
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")
        root = WidgetModel("linearlayout", name="root")
        child = WidgetModel("switch", name="child")
        child.designer_locked = True
        child.designer_hidden = True
        root.add_child(child)

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
        root = WidgetModel("linearlayout", name="root")
        first = WidgetModel("switch", name="first")
        second = WidgetModel("switch", name="second")
        first.designer_locked = True
        second.designer_hidden = True
        root.add_child(first)
        root.add_child(second)

        window._set_selection([first, second], primary=second, sync_tree=False, sync_preview=False)

        message = window.statusBar().currentMessage()
        assert "Selection note: current selection includes" in message
        assert "1 locked widget" in message
        assert "1 hidden widget" in message
        assert "2 layout-managed widgets" in message
        _close_window(window)

    def test_selection_feedback_status_reports_isolated_structure_limit(self, qapp, isolated_config):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")
        root = WidgetModel("group", name="root")
        child = WidgetModel("switch", name="child")
        root.add_child(child)

        window._set_selection([child], primary=child, sync_tree=False, sync_preview=False)

        assert window.statusBar().currentMessage() == (
            "Selection note: select another sibling or target container to move this widget."
        )
        _close_window(window)

    def test_selection_feedback_status_mentions_repeat_move_target(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "SelectionRepeatMoveTargetDemo"
        project = _create_project(project_dir, "SelectionRepeatMoveTargetDemo", sdk_root)
        root = project.get_startup_page().root_widget
        target = WidgetModel("group", name="target")
        first = WidgetModel("switch", name="first")
        second = WidgetModel("button", name="second")
        root.add_child(target)
        root.add_child(first)
        root.add_child(second)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "DeleteLockedDemo", sdk_root)
        locked = WidgetModel("switch", name="locked_widget")
        locked.designer_locked = True
        project.get_startup_page().root_widget.add_child(locked)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
        window._set_selection([locked], primary=locked, sync_tree=False, sync_preview=False)

        deleted_count, skipped_locked, removed_targets = window._delete_selection()

        assert deleted_count == 0
        assert skipped_locked == 1
        assert removed_targets == 0
        assert locked in project.get_startup_page().root_widget.children
        assert window.statusBar().currentMessage() == "Cannot delete selection: 1 locked widget."
        _close_window(window)

    def test_delete_selection_skips_locked_widgets(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "DeleteMixedDemo"
        project = _create_project(project_dir, "DeleteMixedDemo", sdk_root)
        removable = WidgetModel("switch", name="removable")
        locked = WidgetModel("switch", name="locked_widget")
        locked.designer_locked = True
        root = project.get_startup_page().root_widget
        root.add_child(removable)
        root.add_child(locked)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
        window._set_selection([removable, locked], primary=removable, sync_tree=False, sync_preview=False)

        deleted_count, skipped_locked, removed_targets = window._delete_selection()

        assert deleted_count == 1
        assert skipped_locked == 1
        assert removed_targets == 0
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
        project = _create_project(project_dir, "CutMixedDemo", sdk_root)
        removable = WidgetModel("switch", name="removable")
        locked = WidgetModel("switch", name="locked_widget")
        locked.designer_locked = True
        root = project.get_startup_page().root_widget
        root.add_child(removable)
        root.add_child(locked)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
        window._set_selection([removable, locked], primary=removable, sync_tree=False, sync_preview=False)

        window._cut_selection()

        assert removable not in root.children
        assert locked in root.children
        assert len(window._clipboard_payload["widgets"]) == 1
        assert window._clipboard_payload["widgets"][0]["name"] == "removable"
        assert window.statusBar().currentMessage() == "Cut 1 widget(s); skipped 1 locked widget"
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_delete_selection_clears_removed_recent_move_targets(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "DeleteRecentMoveTargetDemo"
        project = _create_project(project_dir, "DeleteRecentMoveTargetDemo", sdk_root)
        root = project.get_startup_page().root_widget
        target = WidgetModel("group", name="target")
        sibling = WidgetModel("label", name="sibling")
        root.add_child(target)
        root.add_child(sibling)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "TreeDeleteMixedDemo", sdk_root)
        removable = WidgetModel("switch", name="removable")
        locked = WidgetModel("switch", name="locked_widget")
        locked.designer_locked = True
        root = project.get_startup_page().root_widget
        root.add_child(removable)
        root.add_child(locked)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "TreeRevealDemo", sdk_root)
        root = project.get_startup_page().root_widget
        container = WidgetModel("group", name="container")
        nested = WidgetModel("group", name="nested")
        target = WidgetModel("switch", name="target")
        nested.add_child(target)
        container.add_child(nested)
        root.add_child(container)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "TreeCollapseStateDemo", sdk_root)
        root = project.get_startup_page().root_widget
        container = WidgetModel("group", name="container")
        nested = WidgetModel("group", name="nested")
        target = WidgetModel("switch", name="target")
        nested.add_child(target)
        container.add_child(nested)
        root.add_child(container)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
            import tempfile
            from pathlib import Path

            os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

            repo_root = Path({repr(str(repo_root))})
            sys.path.insert(0, str(repo_root / "scripts"))

            from PyQt5.QtWidgets import QApplication

            from ui_designer.model.project import Project
            from ui_designer.model.widget_model import WidgetModel
            from ui_designer.ui.main_window import MainWindow


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


            temp_root = Path(tempfile.mkdtemp(prefix="ui_designer_filter_status_", dir=str(repo_root)))
            app = QApplication.instance() or QApplication([])
            try:
                sdk_root = temp_root / "sdk"
                project_dir = temp_root / "TreeFilterStatusDemo"
                create_sdk_root(sdk_root)

                project = Project(screen_width=240, screen_height=320, app_name="TreeFilterStatusDemo")
                project.sdk_root = str(sdk_root)
                project.project_dir = str(project_dir)
                page = project.create_new_page("main_page")
                page.root_widget.add_child(WidgetModel("label", name="field_label"))
                page.root_widget.add_child(WidgetModel("button", name="field_button"))
                project.save(str(project_dir))

                window = MainWindow(str(sdk_root))
                window._recreate_compiler = lambda _window=window: setattr(_window, "compiler", DisabledCompiler())
                window._trigger_compile = lambda: None

                window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)

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
        project = _create_project(project_dir, "TreeSelectActionDemo", sdk_root)
        root = project.get_startup_page().root_widget
        other = WidgetModel("label", name="other")
        container = WidgetModel("group", name="container")
        child_a = WidgetModel("switch", name="child_a")
        child_b = WidgetModel("button", name="child_b")
        container.add_child(child_a)
        container.add_child(child_b)
        root.add_child(other)
        root.add_child(container)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "TreeBatchRenameDemo", sdk_root)
        root = project.get_startup_page().root_widget
        existing = WidgetModel("label", name="field_1")
        first = WidgetModel("label", name="title")
        second = WidgetModel("switch", name="cta")
        root.add_child(existing)
        root.add_child(first)
        root.add_child(second)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(
            "ui_designer.ui.widget_tree.QInputDialog.getText",
            lambda *args, **kwargs: ("field", True),
        )

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "AlignLockedDemo", sdk_root)
        first = WidgetModel("switch", name="first", x=10, y=10, width=40, height=20)
        second = WidgetModel("switch", name="second", x=60, y=20, width=40, height=20)
        second.designer_locked = True
        root = project.get_startup_page().root_widget
        root.add_child(first)
        root.add_child(second)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "AlignLayoutManagedDemo", sdk_root)
        root = project.get_startup_page().root_widget
        layout_parent = WidgetModel("linearlayout", name="layout_parent", x=0, y=0, width=200, height=80)
        first = WidgetModel("switch", name="first", width=40, height=20)
        second = WidgetModel("switch", name="second", width=40, height=20)
        layout_parent.add_child(first)
        layout_parent.add_child(second)
        root.add_child(layout_parent)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "GroupSelectionDemo", sdk_root)
        root = project.get_startup_page().root_widget
        first = WidgetModel("label", name="first", x=10, y=20, width=30, height=10)
        second = WidgetModel("button", name="second", x=60, y=40, width=20, height=20)
        root.add_child(first)
        root.add_child(second)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "MoveIntoDemo", sdk_root)
        root = project.get_startup_page().root_widget
        target = WidgetModel("group", name="target_group", x=90, y=20, width=100, height=80)
        child = WidgetModel("switch", name="child", x=10, y=15, width=20, height=10)
        root.add_child(target)
        root.add_child(child)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(
            "ui_designer.ui.main_window.QInputDialog.getItem",
            lambda *args, **kwargs: ("root_group / target_group (group)", True),
        )

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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

    def test_move_selection_into_container_dialog_prefers_remembered_target(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "RememberMoveIntoDemo"
        project = _create_project(project_dir, "RememberMoveIntoDemo", sdk_root)
        root = project.get_startup_page().root_widget
        target_a = WidgetModel("group", name="target_a")
        target_b = WidgetModel("group", name="target_b")
        first = WidgetModel("label", name="first")
        second = WidgetModel("button", name="second")
        root.add_child(target_a)
        root.add_child(target_b)
        root.add_child(first)
        root.add_child(second)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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

    def test_move_selection_into_container_dialog_prioritizes_recent_target_history(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "DialogRecentMoveIntoDemo"
        project = _create_project(project_dir, "DialogRecentMoveIntoDemo", sdk_root)
        root = project.get_startup_page().root_widget
        target_a = WidgetModel("group", name="target_a")
        target_b = WidgetModel("group", name="target_b")
        target_c = WidgetModel("group", name="target_c")
        first = WidgetModel("label", name="first")
        second = WidgetModel("button", name="second")
        third = WidgetModel("switch", name="third")
        root.add_child(target_a)
        root.add_child(target_b)
        root.add_child(target_c)
        root.add_child(first)
        root.add_child(second)
        root.add_child(third)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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

    def test_structure_actions_follow_precise_selection_constraints(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "StructureActionStateDemo"
        project = _create_project(project_dir, "StructureActionStateDemo", sdk_root)
        root = project.get_startup_page().root_widget
        first = WidgetModel("label", name="first")
        second = WidgetModel("button", name="second")
        target = WidgetModel("group", name="target_group")
        nested = WidgetModel("switch", name="nested")
        target.add_child(nested)
        root.add_child(first)
        root.add_child(second)
        root.add_child(target)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)

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

    def test_structure_actions_disable_root_ungroup_and_noop_move_into(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "StructureActionDisabledDemo"
        project = _create_project(project_dir, "StructureActionDisabledDemo", sdk_root)
        root = project.get_startup_page().root_widget
        first = WidgetModel("label", name="first")
        root.add_child(first)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)

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

    def test_quick_move_into_menu_moves_selection_into_target(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "QuickMoveIntoDemo"
        project = _create_project(project_dir, "QuickMoveIntoDemo", sdk_root)
        root = project.get_startup_page().root_widget
        target = WidgetModel("group", name="target_group", x=90, y=20, width=100, height=80)
        child = WidgetModel("switch", name="child", x=10, y=15, width=20, height=10)
        root.add_child(target)
        root.add_child(child)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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

    def test_move_into_last_target_action_reuses_remembered_target(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "RepeatMoveIntoDemo"
        project = _create_project(project_dir, "RepeatMoveIntoDemo", sdk_root)
        root = project.get_startup_page().root_widget
        target_a = WidgetModel("group", name="target_a")
        target_b = WidgetModel("group", name="target_b")
        first = WidgetModel("label", name="first")
        second = WidgetModel("button", name="second")
        root.add_child(target_a)
        root.add_child(target_b)
        root.add_child(first)
        root.add_child(second)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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

    def test_clear_move_target_history_action_clears_recent_targets(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "ClearMoveTargetHistoryDemo"
        project = _create_project(project_dir, "ClearMoveTargetHistoryDemo", sdk_root)
        root = project.get_startup_page().root_widget
        target = WidgetModel("group", name="target")
        first = WidgetModel("label", name="first")
        second = WidgetModel("button", name="second")
        root.add_child(target)
        root.add_child(first)
        root.add_child(second)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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

    def test_clear_move_target_history_reports_plural_count(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "ClearMoveHistoryCountDemo"
        project = _create_project(project_dir, "ClearMoveHistoryCountDemo", sdk_root)
        root = project.get_startup_page().root_widget
        target_a = WidgetModel("group", name="target_a")
        target_b = WidgetModel("group", name="target_b")
        first = WidgetModel("label", name="first")
        second = WidgetModel("button", name="second")
        third = WidgetModel("switch", name="third")
        root.add_child(target_a)
        root.add_child(target_b)
        root.add_child(first)
        root.add_child(second)
        root.add_child(third)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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

    def test_move_into_last_target_is_scoped_per_page(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PerPageMoveIntoDemo"
        project = _create_project(project_dir, "PerPageMoveIntoDemo", sdk_root)

        main_page = project.get_page_by_name("main_page")
        main_root = main_page.root_widget
        main_target = WidgetModel("group", name="main_target")
        main_first = WidgetModel("label", name="main_first")
        main_second = WidgetModel("button", name="main_second")
        main_root.add_child(main_target)
        main_root.add_child(main_first)
        main_root.add_child(main_second)

        detail_page = project.create_new_page("detail_page")
        detail_root = detail_page.root_widget
        detail_target = WidgetModel("group", name="detail_target")
        detail_first = WidgetModel("label", name="detail_first")
        detail_second = WidgetModel("button", name="detail_second")
        detail_root.add_child(detail_target)
        detail_root.add_child(detail_first)
        detail_root.add_child(detail_second)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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

    def test_repeat_move_target_hint_follows_target_rename(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "RepeatMoveTargetRenameDemo"
        project = _create_project(project_dir, "RepeatMoveTargetRenameDemo", sdk_root)
        root = project.get_startup_page().root_widget
        target = WidgetModel("group", name="target")
        first = WidgetModel("label", name="first")
        second = WidgetModel("button", name="second")
        root.add_child(target)
        root.add_child(first)
        root.add_child(second)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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

    def test_quick_move_into_menu_prioritizes_remembered_target(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "RememberQuickMoveIntoDemo"
        project = _create_project(project_dir, "RememberQuickMoveIntoDemo", sdk_root)
        root = project.get_startup_page().root_widget
        target_a = WidgetModel("group", name="target_a")
        target_b = WidgetModel("group", name="target_b")
        first = WidgetModel("label", name="first")
        second = WidgetModel("button", name="second")
        root.add_child(target_a)
        root.add_child(target_b)
        root.add_child(first)
        root.add_child(second)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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

    def test_quick_move_into_menu_follows_recent_target_history(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "RecentQuickMoveIntoDemo"
        project = _create_project(project_dir, "RecentQuickMoveIntoDemo", sdk_root)
        root = project.get_startup_page().root_widget
        target_a = WidgetModel("group", name="target_a")
        target_b = WidgetModel("group", name="target_b")
        target_c = WidgetModel("group", name="target_c")
        first = WidgetModel("label", name="first")
        second = WidgetModel("button", name="second")
        third = WidgetModel("switch", name="third")
        root.add_child(target_a)
        root.add_child(target_b)
        root.add_child(target_c)
        root.add_child(first)
        root.add_child(second)
        root.add_child(third)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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

    def test_quick_move_into_menu_shows_recent_placeholder_without_history(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "QuickMovePlaceholderDemo"
        project = _create_project(project_dir, "QuickMovePlaceholderDemo", sdk_root)
        root = project.get_startup_page().root_widget
        target = WidgetModel("group", name="target")
        child = WidgetModel("label", name="child")
        root.add_child(target)
        root.add_child(child)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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

    def test_quick_move_into_menu_reuses_last_target_and_clears_history(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "QuickMoveHistoryMenuDemo"
        project = _create_project(project_dir, "QuickMoveHistoryMenuDemo", sdk_root)
        root = project.get_startup_page().root_widget
        target = WidgetModel("group", name="target")
        first = WidgetModel("label", name="first")
        second = WidgetModel("button", name="second")
        root.add_child(target)
        root.add_child(first)
        root.add_child(second)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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

    def test_quick_move_into_menu_stays_available_for_history_only(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "QuickMoveHistoryOnlyDemo"
        project = _create_project(project_dir, "QuickMoveHistoryOnlyDemo", sdk_root)
        root = project.get_startup_page().root_widget
        target = WidgetModel("group", name="target")
        child = WidgetModel("label", name="child")
        root.add_child(target)
        root.add_child(child)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "TreeGroupSelectionDemo", sdk_root)
        root = project.get_startup_page().root_widget
        first = WidgetModel("label", name="first", x=10, y=20, width=30, height=10)
        second = WidgetModel("button", name="second", x=60, y=40, width=20, height=20)
        root.add_child(first)
        root.add_child(second)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "TreeDropMoveDemo", sdk_root)
        root = project.get_startup_page().root_widget
        first = WidgetModel("label", name="first")
        second = WidgetModel("label", name="second")
        third = WidgetModel("label", name="third")
        root.add_child(first)
        root.add_child(second)
        root.add_child(third)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "MoveToEdgeDemo", sdk_root)
        root = project.get_startup_page().root_widget
        first = WidgetModel("label", name="first")
        second = WidgetModel("label", name="second")
        third = WidgetModel("label", name="third")
        root.add_child(first)
        root.add_child(second)
        root.add_child(third)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "TreeInvalidDropDemo", sdk_root)
        root = project.get_startup_page().root_widget
        first = WidgetModel("label", name="first")
        root.add_child(first)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "DistributeParentDemo", sdk_root)
        root = project.get_startup_page().root_widget
        group_a = WidgetModel("group", name="group_a", x=0, y=0, width=120, height=120)
        group_b = WidgetModel("group", name="group_b", x=130, y=0, width=120, height=120)
        first = WidgetModel("switch", name="first", x=10, y=10, width=20, height=20)
        second = WidgetModel("switch", name="second", x=40, y=10, width=20, height=20)
        third = WidgetModel("switch", name="third", x=10, y=10, width=20, height=20)
        group_a.add_child(first)
        group_a.add_child(second)
        group_b.add_child(third)
        root.add_child(group_a)
        root.add_child(group_b)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "DistributeLayoutManagedDemo", sdk_root)
        root = project.get_startup_page().root_widget
        layout_parent = WidgetModel("linearlayout", name="layout_parent", x=0, y=0, width=200, height=120)
        first = WidgetModel("switch", name="first", width=20, height=20)
        second = WidgetModel("switch", name="second", width=20, height=20)
        third = WidgetModel("switch", name="third", width=20, height=20)
        layout_parent.add_child(first)
        layout_parent.add_child(second)
        layout_parent.add_child(third)
        root.add_child(layout_parent)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "FrontLockedDemo", sdk_root)
        locked = WidgetModel("switch", name="locked_widget")
        locked.designer_locked = True
        project.get_startup_page().root_widget.add_child(locked)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "BackLockedDemo", sdk_root)
        locked = WidgetModel("switch", name="locked_widget")
        locked.designer_locked = True
        project.get_startup_page().root_widget.add_child(locked)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "PropertyStatusDemo", sdk_root)
        widget = WidgetModel("switch", name="toggle")
        project.get_startup_page().root_widget.add_child(widget)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "CanvasMoveStatusDemo", sdk_root)
        widget = WidgetModel("switch", name="toggle", x=10, y=10, width=50, height=24)
        project.get_startup_page().root_widget.add_child(widget)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
        window._set_selection([widget], primary=widget, sync_tree=False, sync_preview=False)
        widget.x = 20
        widget.display_x = 20

        window._on_widget_moved(widget, 20, 10)

        assert window.statusBar().currentMessage() == "Changed main_page: canvas move."
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_new_project_prefers_recovered_cached_sdk_for_defaults(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        cached_sdk = tmp_path / "config" / "sdk" / "EmbeddedGUI"
        _create_sdk_root(cached_sdk)
        isolated_config.sdk_root = str(tmp_path / "missing_sdk")
        isolated_config.egui_root = str(tmp_path / "missing_sdk")
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
        assert captured["default_parent_dir"] == os.path.join(os.path.normpath(os.path.abspath(cached_sdk)), "example")
        _close_window(window)

    def test_save_project_as_copies_sidecar_files_and_updates_project_dir(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        src_dir = tmp_path / "SrcDemo"
        dst_dir = tmp_path / "DstDemo"
        project = _create_project(src_dir, "SaveAsDemo", sdk_root)

        (src_dir / "build.mk").write_text("# custom build\n", encoding="utf-8")
        (src_dir / "app_egui_config.h").write_text("#define CUSTOM_CFG 1\n", encoding="utf-8")
        images_dir = src_dir / ".eguiproject" / "resources" / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        (images_dir / "legacy.png").write_bytes(b"PNG")
        mockup_dir = src_dir / ".eguiproject" / "mockup"
        mockup_dir.mkdir(parents=True, exist_ok=True)
        (mockup_dir / "legacy.txt").write_text("mock", encoding="utf-8")

        window = MainWindow(str(sdk_root))
        window.project = project
        window.project_root = str(sdk_root)
        window._project_dir = str(src_dir)
        window.app_name = "SaveAsDemo"

        monkeypatch.setattr("ui_designer.ui.main_window.QFileDialog.getExistingDirectory", lambda *args, **kwargs: str(dst_dir))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: None)
        monkeypatch.setattr("ui_designer.ui.main_window.generate_all_files_preserved", lambda *args, **kwargs: {"generated.c": "// save as\n"})

        window._save_project_as()

        assert window._project_dir == os.path.normpath(os.path.abspath(dst_dir))
        assert window.project.project_dir == os.path.normpath(os.path.abspath(dst_dir))
        assert (dst_dir / "generated.c").read_text(encoding="utf-8") == "// save as\n"
        assert (dst_dir / "build.mk").read_text(encoding="utf-8") == "# custom build\n"
        assert (dst_dir / "app_egui_config.h").read_text(encoding="utf-8") == "#define CUSTOM_CFG 1\n"
        assert (dst_dir / ".eguiproject" / "resources" / "images" / "legacy.png").is_file()
        assert (dst_dir / ".eguiproject" / "mockup" / "legacy.txt").is_file()
        assert (dst_dir / "resource" / "src" / "legacy.png").is_file()
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
        project = _create_project(project_dir, "ExportBlockedDemo", sdk_root)
        project.get_startup_page().root_widget.add_child(WidgetModel("label", name="bad-name", x=8, y=8, width=60, height=20))
        project.save(str(project_dir))

        warnings = []
        window = MainWindow(str(sdk_root))
        monkeypatch.setattr("ui_designer.ui.main_window.QFileDialog.getExistingDirectory", lambda *args, **kwargs: str(export_dir))
        monkeypatch.setattr("ui_designer.ui.main_window.QMessageBox.warning", lambda *args: warnings.append(args[1:]))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
        window._export_code()

        assert warnings
        assert warnings[0][0] == "Export Blocked"
        assert "blocked by diagnostics" in warnings[0][1]
        assert not (export_dir / "main_page.c").exists()
        assert window.statusBar().currentMessage() == "Export blocked: 1 error(s) in diagnostics."
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
        monkeypatch.setattr(window, "_trigger_compile", lambda: calls.__setitem__("compile", calls["compile"] + 1))

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
        isolated_config.egui_root = str(tmp_path / "missing_sdk")
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
        isolated_config.egui_root = str(tmp_path / "missing_sdk")
        captured = {}

        class FakeDialog:
            Accepted = 1

            def __init__(self, parent=None, egui_root=None, on_download_sdk=None):
                captured["egui_root"] = egui_root
                captured["has_download_handler"] = callable(on_download_sdk)
                self._selected_entry = None
                self._egui_root = egui_root

            def exec_(self):
                return 0

            @property
            def selected_entry(self):
                return self._selected_entry

            @property
            def egui_root(self):
                return self._egui_root

        window = MainWindow("")
        monkeypatch.setattr("ui_designer.ui.main_window.default_sdk_install_dir", lambda: str(cached_sdk))
        monkeypatch.setattr("ui_designer.ui.main_window.AppSelectorDialog", FakeDialog)

        window._open_app_dialog()

        assert captured["egui_root"] == os.path.normpath(os.path.abspath(cached_sdk))
        assert captured["has_download_handler"] is True
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
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(Project.load(str(project_dir)), str(project_dir), preferred_sdk_root="", silent=True)

        assert window.project_root == os.path.normpath(os.path.abspath(sdk_root))
        assert window.project.sdk_root == os.path.normpath(os.path.abspath(sdk_root))
        assert isolated_config.sdk_root == os.path.normpath(os.path.abspath(sdk_root))
        _close_window(window)

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
        project = _create_project(project_dir, "CompileBlockedDemo", sdk_root)
        project.get_startup_page().root_widget.add_child(WidgetModel("label", name="bad-name", x=8, y=8, width=60, height=20))
        project.save(str(project_dir))

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
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_ensure_resources_generated", lambda: (_ for _ in ()).throw(AssertionError("resource generation should not run")))
        monkeypatch.setattr(window, "_switch_to_python_preview", lambda reason="": preview_reasons.append(reason))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
        window.compiler = CompileFailIfCalled()
        preview_reasons.clear()
        window._do_compile_and_run()

        assert preview_reasons == ["Compile blocked by diagnostics"]
        assert window.statusBar().currentMessage() == "Compile preview blocked: 1 error(s) in diagnostics."
        window._undo_manager.mark_all_saved()
        _close_window(window)

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

    def test_import_legacy_example_generates_project_and_uses_existing_dimensions(self, qapp, isolated_config, tmp_path, monkeypatch):
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

        window._import_legacy_example(
            {
                "app_name": "LegacyApp",
                "app_dir": str(app_dir),
            },
            str(sdk_root),
        )

        project_path = app_dir / "LegacyApp.egui"
        saved = Project.load(str(project_path))
        assert project_path.is_file()
        assert saved.screen_width == 480
        assert saved.screen_height == 272
        assert (app_dir / "resource" / "src" / "app_resource_config.json").is_file()
        assert opened == {
            "path": os.path.normpath(os.path.abspath(project_path)),
            "preferred_sdk_root": os.path.normpath(os.path.abspath(sdk_root)),
            "silent": False,
        }
        _close_window(window)

    def test_import_legacy_example_warns_on_eguiproject_conflict(self, qapp, isolated_config, tmp_path, monkeypatch):
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

        window._import_legacy_example(
            {
                "app_name": "LegacyConflict",
                "app_dir": str(app_dir),
            },
            str(sdk_root),
        )

        assert warnings
        assert warnings[0][0] == "Legacy Example Conflict"
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
        assert "No recent projects" in recent_widget.text()
        assert "Removed missing project" in window.statusBar().currentMessage()
        _close_window(window)

    def test_recent_menu_action_uses_recovered_cached_sdk_root(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        cached_sdk = tmp_path / "config" / "sdk" / "EmbeddedGUI"
        _create_sdk_root(cached_sdk)
        project_path = tmp_path / "DemoApp" / "DemoApp.egui"
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

    def test_recent_and_view_submenu_categories_expose_status_hints(self, qapp, isolated_config, tmp_path):
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")
        file_menu = next(action.menu() for action in window.menuBar().actions() if action.text() == "File")
        view_menu = next(action.menu() for action in window.menuBar().actions() if action.text() == "View")
        background_menu = next(action.menu() for action in view_menu.actions() if action.text() == "Background Mockup")

        assert window._recent_menu.menuAction().toolTip() == "Open a recently used project. No recent projects are available."
        assert window._recent_menu.menuAction().statusTip() == window._recent_menu.menuAction().toolTip()

        project_path = tmp_path / "DemoApp" / "DemoApp.egui"
        isolated_config.recent_projects = [
            {
                "project_path": str(project_path),
                "sdk_root": "",
                "display_name": "DemoApp",
            }
        ]
        window._update_recent_menu()
        assert window._recent_menu.menuAction().toolTip() == "Open a recently used project. 1 recent project available."
        assert window._recent_menu.menuAction().statusTip() == window._recent_menu.menuAction().toolTip()

        file_actions = {action.text(): action for action in file_menu.actions() if action.text()}
        view_actions = {action.text(): action for action in view_menu.actions() if action.text()}
        background_actions = {action.text(): action for action in background_menu.actions() if action.text()}

        assert file_actions["Recent Projects"].toolTip() == window._recent_menu.menuAction().toolTip()
        assert file_actions["Recent Projects"].statusTip() == file_actions["Recent Projects"].toolTip()
        assert view_actions["Theme"].toolTip() == "Choose the Designer theme."
        assert view_actions["Theme"].statusTip() == view_actions["Theme"].toolTip()
        assert view_actions["Workspace"].toolTip() == "Choose a workspace panel to show."
        assert view_actions["Workspace"].statusTip() == view_actions["Workspace"].toolTip()
        assert view_actions["Inspector"].toolTip() == "Choose an inspector section to show."
        assert view_actions["Inspector"].statusTip() == view_actions["Inspector"].toolTip()
        assert view_actions["Tools"].toolTip() == "Choose a bottom tools panel to show."
        assert view_actions["Tools"].statusTip() == view_actions["Tools"].toolTip()
        assert view_actions["Grid Size"].toolTip() == "Choose the grid snap size."
        assert view_actions["Grid Size"].statusTip() == view_actions["Grid Size"].toolTip()
        assert view_actions["Background Mockup"].toolTip() == "Manage the preview background mockup image."
        assert view_actions["Background Mockup"].statusTip() == view_actions["Background Mockup"].toolTip()
        assert background_actions["Opacity"].toolTip() == "Choose the mockup image opacity."
        assert background_actions["Opacity"].statusTip() == background_actions["Opacity"].toolTip()
        _close_window(window)

    def test_generate_resources_action_exposes_status_hint(self, qapp, isolated_config):
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")
        action = next(action for action in window.findChildren(type(window._save_action)) if action.text() == "Generate Resources")

        assert action.toolTip() == (
            "Run resource generation (app_resource_generate.py) to produce\n"
            "C source files from .eguiproject/resources/ assets and widget config."
        )
        assert action.statusTip() == action.toolTip()
        _close_window(window)

    def test_build_menu_actions_expose_status_hints(self, qapp, isolated_config, tmp_path):
        from ui_designer.ui.main_window import MainWindow

        class _BuildReadyCompiler:
            def can_build(self):
                return True

            def is_preview_running(self):
                return False

            def cleanup(self):
                return None

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "BuildHintsDemo"
        project = _create_project(project_dir, "BuildHintsDemo", sdk_root)

        window = MainWindow("")
        actions = {
            action.text(): action
            for action in window.findChildren(type(window._save_action))
            if action.text() in {
                "Auto Compile",
                "Release Build...",
                "Release Profiles...",
                "Release History...",
                "Repository Health...",
            }
        }

        assert actions["Auto Compile"].toolTip() == (
            "Automatically compile and rerun the preview after changes. Unavailable: open a project first."
        )
        assert actions["Auto Compile"].statusTip() == actions["Auto Compile"].toolTip()
        assert actions["Release Build..."].toolTip() == (
            "Build a release package for the current project. Unavailable: open a project first."
        )
        assert actions["Release Build..."].statusTip() == actions["Release Build..."].toolTip()
        assert actions["Release Profiles..."].toolTip() == (
            "Edit release profiles for the current project. Unavailable: open a project first."
        )
        assert actions["Release Profiles..."].statusTip() == actions["Release Profiles..."].toolTip()
        assert actions["Release History..."].toolTip() == (
            "Browse recorded release builds for the current project. Unavailable: open a project first."
        )
        assert actions["Release History..."].statusTip() == actions["Release History..."].toolTip()
        assert actions["Repository Health..."].toolTip() == "Inspect the Designer repository health summary."
        assert actions["Repository Health..."].statusTip() == actions["Repository Health..."].toolTip()

        window.project = project
        window._project_dir = str(project_dir)
        window.project_root = str(sdk_root)
        window.compiler = _BuildReadyCompiler()
        window._update_compile_availability()

        refreshed_actions = {
            action.text(): action
            for action in window.findChildren(type(window._save_action))
            if action.text() in actions
        }
        assert refreshed_actions["Auto Compile"].toolTip() == "Automatically compile and rerun the preview after changes."
        assert refreshed_actions["Auto Compile"].statusTip() == refreshed_actions["Auto Compile"].toolTip()
        assert refreshed_actions["Release Build..."].toolTip() == "Build a release package for the current project."
        assert refreshed_actions["Release Build..."].statusTip() == refreshed_actions["Release Build..."].toolTip()
        assert refreshed_actions["Release Profiles..."].toolTip() == "Edit release profiles for the current project."
        assert refreshed_actions["Release Profiles..."].statusTip() == refreshed_actions["Release Profiles..."].toolTip()
        assert refreshed_actions["Release History..."].toolTip() == "Browse recorded release builds for the current project."
        assert refreshed_actions["Release History..."].statusTip() == refreshed_actions["Release History..."].toolTip()
        assert refreshed_actions["Repository Health..."].toolTip() == "Inspect the Designer repository health summary."
        assert refreshed_actions["Repository Health..."].statusTip() == refreshed_actions["Repository Health..."].toolTip()
        _close_window(window)

    def test_view_panel_navigation_actions_expose_status_hints(self, qapp, isolated_config):
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")
        actions = {
            action.text(): action
            for action in window.findChildren(type(window._save_action))
            if action.text() in {
                "Project",
                "Structure",
                "Components",
                "Assets",
                "Status",
                "Properties",
                "Animations",
                "Page",
                "Diagnostics",
                "History",
                "Debug Output",
            }
        }

        assert actions["Project"].toolTip() == "Show the Project workspace panel."
        assert actions["Project"].statusTip() == actions["Project"].toolTip()
        assert actions["Structure"].toolTip() == "Show the Structure workspace panel."
        assert actions["Structure"].statusTip() == actions["Structure"].toolTip()
        assert actions["Components"].toolTip() == "Show the Components workspace panel."
        assert actions["Components"].statusTip() == actions["Components"].toolTip()
        assert actions["Assets"].toolTip() == "Show the Assets workspace panel."
        assert actions["Assets"].statusTip() == actions["Assets"].toolTip()
        assert actions["Status"].toolTip() == "Show the Status workspace panel."
        assert actions["Status"].statusTip() == actions["Status"].toolTip()
        assert actions["Properties"].toolTip() == "Show the Properties inspector section."
        assert actions["Properties"].statusTip() == actions["Properties"].toolTip()
        assert actions["Animations"].toolTip() == "Show the Animations inspector section."
        assert actions["Animations"].statusTip() == actions["Animations"].toolTip()
        assert actions["Page"].toolTip() == "Show the Page inspector section."
        assert actions["Page"].statusTip() == actions["Page"].toolTip()
        assert actions["Diagnostics"].toolTip() == "Show the Diagnostics tools panel."
        assert actions["Diagnostics"].statusTip() == actions["Diagnostics"].toolTip()
        assert actions["History"].toolTip() == "Show the History tools panel."
        assert actions["History"].statusTip() == actions["History"].toolTip()
        assert actions["Debug Output"].toolTip() == "Show the Debug Output tools panel."
        assert actions["Debug Output"].statusTip() == actions["Debug Output"].toolTip()
        _close_window(window)

    def test_view_appearance_actions_expose_status_hints(self, qapp, isolated_config):
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")
        actions = {
            action.text(): action
            for action in window.findChildren(type(window._save_action))
            if action.text() in {
                "Dark",
                "Light",
                "Font Size...",
                "Vertical",
                "Horizontal",
                "Overlay Only",
                "Swap Preview/Overlay",
                "Zoom In",
                "Zoom Out",
                "Zoom Reset (100%)",
            }
        }

        assert actions["Dark"].toolTip() == "Switch the Designer theme to dark."
        assert actions["Dark"].statusTip() == actions["Dark"].toolTip()
        assert actions["Light"].toolTip() == "Switch the Designer theme to light."
        assert actions["Light"].statusTip() == actions["Light"].toolTip()
        assert actions["Font Size..."].toolTip() == "Adjust the Designer font size."
        assert actions["Font Size..."].statusTip() == actions["Font Size..."].toolTip()
        assert actions["Vertical"].toolTip() == "Show preview and overlay stacked vertically (Ctrl+1)."
        assert actions["Vertical"].statusTip() == actions["Vertical"].toolTip()
        assert actions["Horizontal"].toolTip() == "Show preview and overlay side by side (Ctrl+2)."
        assert actions["Horizontal"].statusTip() == actions["Horizontal"].toolTip()
        assert actions["Overlay Only"].toolTip() == "Show only the overlay workspace (Ctrl+3)."
        assert actions["Overlay Only"].statusTip() == actions["Overlay Only"].toolTip()
        assert actions["Swap Preview/Overlay"].toolTip() == "Swap the preview and overlay positions (Ctrl+4)."
        assert actions["Swap Preview/Overlay"].statusTip() == actions["Swap Preview/Overlay"].toolTip()
        assert actions["Zoom In"].toolTip() == "Zoom in on the preview overlay (Ctrl+=)."
        assert actions["Zoom In"].statusTip() == actions["Zoom In"].toolTip()
        assert actions["Zoom Out"].toolTip() == "Zoom out on the preview overlay (Ctrl+-)."
        assert actions["Zoom Out"].statusTip() == actions["Zoom Out"].toolTip()
        assert actions["Zoom Reset (100%)"].toolTip() == "Reset the preview overlay zoom to 100% (Ctrl+0)."
        assert actions["Zoom Reset (100%)"].statusTip() == actions["Zoom Reset (100%)"].toolTip()
        _close_window(window)

    def test_view_grid_and_mockup_actions_expose_status_hints(self, qapp, isolated_config):
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")
        actions = {
            action.text(): action
            for action in window.findChildren(type(window._save_action))
            if action.text() in {
                "Show Grid",
                "No Snap",
                "4px",
                "8px",
                "12px",
                "16px",
                "24px",
                "Load Mockup Image...",
                "Show Mockup",
                "Clear Mockup Image",
                "10%",
                "20%",
                "30%",
                "50%",
                "70%",
                "100%",
            }
        }

        assert actions["Show Grid"].toolTip() == "Toggle the preview grid overlay."
        assert actions["Show Grid"].statusTip() == actions["Show Grid"].toolTip()
        assert actions["No Snap"].toolTip() == "Disable grid snapping."
        assert actions["No Snap"].statusTip() == actions["No Snap"].toolTip()
        assert actions["4px"].toolTip() == "Snap the overlay grid to 4px."
        assert actions["4px"].statusTip() == actions["4px"].toolTip()
        assert actions["8px"].toolTip() == "Snap the overlay grid to 8px."
        assert actions["8px"].statusTip() == actions["8px"].toolTip()
        assert actions["12px"].toolTip() == "Snap the overlay grid to 12px."
        assert actions["12px"].statusTip() == actions["12px"].toolTip()
        assert actions["16px"].toolTip() == "Snap the overlay grid to 16px."
        assert actions["16px"].statusTip() == actions["16px"].toolTip()
        assert actions["24px"].toolTip() == "Snap the overlay grid to 24px."
        assert actions["24px"].statusTip() == actions["24px"].toolTip()
        assert actions["Load Mockup Image..."].toolTip() == "Load a mockup image behind the preview."
        assert actions["Load Mockup Image..."].statusTip() == actions["Load Mockup Image..."].toolTip()
        assert actions["Show Mockup"].toolTip() == "Toggle the background mockup image (Ctrl+M)."
        assert actions["Show Mockup"].statusTip() == actions["Show Mockup"].toolTip()
        assert actions["Clear Mockup Image"].toolTip() == "Remove the current background mockup image."
        assert actions["Clear Mockup Image"].statusTip() == actions["Clear Mockup Image"].toolTip()
        assert actions["10%"].toolTip() == "Set the mockup image opacity to 10%."
        assert actions["10%"].statusTip() == actions["10%"].toolTip()
        assert actions["20%"].toolTip() == "Set the mockup image opacity to 20%."
        assert actions["20%"].statusTip() == actions["20%"].toolTip()
        assert actions["30%"].toolTip() == "Set the mockup image opacity to 30%."
        assert actions["30%"].statusTip() == actions["30%"].toolTip()
        assert actions["50%"].toolTip() == "Set the mockup image opacity to 50%."
        assert actions["50%"].statusTip() == actions["50%"].toolTip()
        assert actions["70%"].toolTip() == "Set the mockup image opacity to 70%."
        assert actions["70%"].statusTip() == actions["70%"].toolTip()
        assert actions["100%"].toolTip() == "Set the mockup image opacity to 100%."
        assert actions["100%"].statusTip() == actions["100%"].toolTip()
        _close_window(window)

    def test_edit_menu_secondary_actions_expose_status_hints(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "EditHintsDemo"
        project = _create_project(project_dir, "EditHintsDemo", sdk_root)
        widget = WidgetModel("label", name="title", x=12, y=16, width=100, height=24)
        project.get_startup_page().root_widget.add_child(widget)
        project.save(str(project_dir))

        window = MainWindow("")
        actions = {
            action.text(): action
            for action in window.findChildren(type(window._save_action))
            if action.text() in {
                "Select All",
                "Cut",
                "Duplicate",
                "Delete",
            }
        }

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

        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
        loaded_widget = window._current_page.root_widget.children[0]
        window._set_selection([loaded_widget], primary=loaded_widget, sync_tree=True, sync_preview=True)
        window._update_edit_actions()

        refreshed_actions = {
            action.text(): action
            for action in window.findChildren(type(window._save_action))
            if action.text() in actions
        }
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

    def test_arrange_actions_expose_dynamic_status_hints(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "ArrangeHintsDemo"
        project = _create_project(project_dir, "ArrangeHintsDemo", sdk_root)
        root = project.get_startup_page().root_widget
        first = WidgetModel("label", name="first", x=8, y=8, width=60, height=20)
        second = WidgetModel("button", name="second", x=72, y=8, width=60, height=20)
        third = WidgetModel("switch", name="third", x=136, y=8, width=60, height=20)
        root.add_child(first)
        root.add_child(second)
        root.add_child(third)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)

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
        project = _create_project(project_dir, "ArrangeToggleHintsDemo", sdk_root)
        root = project.get_startup_page().root_widget
        first = WidgetModel("label", name="first", x=8, y=8, width=60, height=20)
        second = WidgetModel("button", name="second", x=72, y=8, width=60, height=20)
        second.designer_locked = True
        root.add_child(first)
        root.add_child(second)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)

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

    def test_menu_bar_categories_expose_status_hints(self, qapp, isolated_config):
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")
        actions = {action.text(): action for action in window.menuBar().actions() if action.text()}

        assert actions["File"].toolTip() == "Create, open, save, export, and close projects."
        assert actions["File"].statusTip() == actions["File"].toolTip()
        assert actions["Edit"].toolTip() == "Undo changes and work with the current selection."
        assert actions["Edit"].statusTip() == actions["Edit"].toolTip()
        assert actions["Arrange"].toolTip() == "Align, distribute, reorder, lock, and hide selected widgets."
        assert actions["Arrange"].statusTip() == actions["Arrange"].toolTip()
        assert actions["Structure"].toolTip() == "Group, move, and reorder widgets in the page hierarchy."
        assert actions["Structure"].statusTip() == actions["Structure"].toolTip()
        assert actions["Build"].toolTip() == "Compile previews, generate resources, and manage release builds."
        assert actions["Build"].statusTip() == actions["Build"].toolTip()
        assert actions["View"].toolTip() == "Change workspace layout, themes, preview modes, and mockup options."
        assert actions["View"].statusTip() == actions["View"].toolTip()
        _close_window(window)

    def test_file_menu_primary_actions_expose_status_hints(self, qapp, isolated_config):
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")
        actions = {
            action.text(): action
            for action in window.findChildren(type(window._save_action))
            if action.text() in {
                "New Project",
                "Open SDK Example...",
                "Open Project File...",
                "Download SDK Copy...",
                "Set SDK Root...",
            }
        }

        assert actions["New Project"].toolTip() == "Create a new EmbeddedGUI Designer project."
        assert actions["New Project"].statusTip() == actions["New Project"].toolTip()
        assert actions["Open SDK Example..."].toolTip() == "Open an SDK example project or legacy example."
        assert actions["Open SDK Example..."].statusTip() == actions["Open SDK Example..."].toolTip()
        assert actions["Open Project File..."].toolTip() == "Open an existing .egui project file."
        assert actions["Open Project File..."].statusTip() == actions["Open Project File..."].toolTip()
        assert "GitHub archive" in actions["Download SDK Copy..."].toolTip()
        assert actions["Download SDK Copy..."].statusTip() == actions["Download SDK Copy..."].toolTip()
        assert actions["Set SDK Root..."].toolTip() == "Choose the EmbeddedGUI SDK root used for compile preview."
        assert actions["Set SDK Root..."].statusTip() == actions["Set SDK Root..."].toolTip()
        _close_window(window)

    def test_file_menu_secondary_actions_expose_status_hints(self, qapp, isolated_config, tmp_path):
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")
        actions = {
            action.text(): action
            for action in window.findChildren(type(window._save_action))
            if action.text() in {
                "Save As...",
                "Reload Project From Disk",
                "Close Project",
                "Export C Code...",
                "Quit",
            }
        }

        assert actions["Save As..."].toolTip() == "Save the current project to a new file (Ctrl+Shift+S)."
        assert actions["Save As..."].statusTip() == actions["Save As..."].toolTip()
        assert actions["Reload Project From Disk"].toolTip() == (
            "Reload the current project from disk (Ctrl+Shift+R). Unavailable: open a project first."
        )
        assert actions["Reload Project From Disk"].statusTip() == actions["Reload Project From Disk"].toolTip()
        assert actions["Close Project"].toolTip() == "Close the current project (Ctrl+W)."
        assert actions["Close Project"].statusTip() == actions["Close Project"].toolTip()
        assert actions["Export C Code..."].toolTip() == "Export generated C code for the current project (Ctrl+E)."
        assert actions["Export C Code..."].statusTip() == actions["Export C Code..."].toolTip()
        assert actions["Quit"].toolTip() == "Quit EmbeddedGUI Designer (Ctrl+Q)."
        assert actions["Quit"].statusTip() == actions["Quit"].toolTip()

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "ReloadDemo"
        project = _create_project(project_dir, "ReloadDemo", sdk_root)
        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
        window._update_compile_availability()

        reloaded_actions = {
            action.text(): action
            for action in window.findChildren(type(window._save_action))
            if action.text() == "Reload Project From Disk"
        }
        assert reloaded_actions["Reload Project From Disk"].toolTip() == "Reload the current project from disk (Ctrl+Shift+R)."
        assert reloaded_actions["Reload Project From Disk"].statusTip() == reloaded_actions["Reload Project From Disk"].toolTip()
        _close_window(window)

    def test_duplicate_page_copies_existing_page_content(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "DuplicateDemo"
        project = _create_project(project_dir, "DuplicateDemo", sdk_root)
        source_page = project.get_page_by_name("main_page")
        label = WidgetModel("label", name="title", x=12, y=16, width=100, height=24)
        label.properties["text"] = "Original Title"
        source_page.root_widget.add_child(label)
        source_page.user_fields.append({"name": "counter", "type": "int", "default": 7})
        source_page.timers.append(
            {
                "name": "refresh_timer",
                "callback": "tick_refresh",
                "delay_ms": "500",
                "period_ms": "1000",
                "auto_start": True,
            }
        )
        source_page.mockup_image_path = "mockup/main.png"
        source_page.mockup_image_opacity = 0.6
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
        window.project_dock._duplicate_page("main_page")

        duplicated = window.project.get_page_by_name("main_page_copy")
        assert duplicated is not None
        assert window._current_page is duplicated
        assert duplicated.root_widget is not source_page.root_widget
        assert len(duplicated.root_widget.children) == 1
        assert duplicated.root_widget.children[0].properties["text"] == "Original Title"
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

    def test_page_fields_panel_edit_updates_page_dirty_state_and_xml(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PageFieldsDemo"
        project = _create_project(project_dir, "PageFieldsDemo", sdk_root)

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PageFieldsSwitchDemo"
        project = _create_project(project_dir, "PageFieldsSwitchDemo", sdk_root)
        project.get_startup_page().user_fields = [{"name": "counter", "type": "int", "default": "0"}]
        detail_page = project.create_new_page("detail_page")
        detail_page.user_fields = [{"name": "state", "type": "bool", "default": "false"}]
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)

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
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        opened = []
        monkeypatch.setattr(window, "_open_path_in_default_app", lambda path: opened.append(path) or True)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
        window._on_page_user_code_section_requested("init")

        source_path = project_dir / "main_page.c"
        assert opened == [str(source_path)]
        assert source_path.exists() is True
        content = source_path.read_text(encoding="utf-8")
        assert "void egui_main_page_init(egui_page_base_t *self)" in content
        assert "// USER CODE BEGIN init" in content
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
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PageTimersSwitchDemo"
        project = _create_project(project_dir, "PageTimersSwitchDemo", sdk_root)
        project.get_startup_page().timers = [
            {"name": "refresh_timer", "callback": "tick_refresh", "delay_ms": "500", "period_ms": "1000", "auto_start": True}
        ]
        detail_page = project.create_new_page("detail_page")
        detail_page.timers = [
            {"name": "poll_timer", "callback": "tick_poll", "delay_ms": "250", "period_ms": "250", "auto_start": False}
        ]
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)

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
        project = _create_project(project_dir, "AnimationsDemo", sdk_root)
        card = WidgetModel("group", name="card", x=12, y=16, width=100, height=60)
        project.get_startup_page().root_widget.add_child(card)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "AnimationsSelectionDemo", sdk_root)
        page = project.get_startup_page()
        card = WidgetModel("group", name="card", x=12, y=16, width=100, height=60)
        badge = WidgetModel("group", name="badge", x=12, y=88, width=80, height=40)
        card.animations = [create_default_animation("alpha")]
        badge.animations = [create_default_animation("color")]
        page.root_widget.add_child(card)
        page.root_widget.add_child(badge)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)

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

    def test_property_panel_callback_edit_updates_widget_and_dirty_state(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "EventCallbackDemo"
        project = _create_project(project_dir, "EventCallbackDemo", sdk_root)
        slider = WidgetModel("slider", name="volume_slider", x=16, y=16, width=160, height=24)
        project.get_startup_page().root_widget.add_child(slider)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "UserCodeCreateDemo", sdk_root)
        slider = WidgetModel("slider", name="volume_slider", x=16, y=16, width=160, height=24)
        slider.events["onValueChanged"] = "on_volume_changed"
        project.get_startup_page().root_widget.add_child(slider)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        opened = []
        monkeypatch.setattr(window, "_open_path_in_default_app", lambda path: opened.append(path) or True)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "UserCodeUpdateDemo", sdk_root)
        page = project.get_startup_page()
        source_path = project_dir / "main_page.c"
        source_path.write_text(generate_page_user_source(page, project), encoding="utf-8")

        timer = {"name": "refresh_timer", "callback": "tick_refresh", "delay_ms": "500", "period_ms": "1000", "auto_start": True}
        page.timers = [timer]
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        refresh_calls = []
        monkeypatch.setattr(window, "_refresh_project_watch_snapshot", lambda: refresh_calls.append("refreshed"))
        monkeypatch.setattr(window, "_open_path_in_default_app", lambda path: True)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
        refresh_calls.clear()
        window._on_user_code_requested("tick_refresh", "void {func_name}(egui_timer_t *timer)")

        content = source_path.read_text(encoding="utf-8")
        assert "void tick_refresh(egui_timer_t *timer)" in content
        assert "EGUI_UNUSED(local);" in content
        assert refresh_calls
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
        project = _create_project(project_dir, "BatchEventCallbackDemo", sdk_root)
        first = WidgetModel("slider", name="volume_slider_a", x=16, y=16, width=160, height=24)
        second = WidgetModel("slider", name="volume_slider_b", x=16, y=48, width=160, height=24)
        project.get_startup_page().root_widget.add_child(first)
        project.get_startup_page().root_widget.add_child(second)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "MockupDemo"
        project = _create_project(project_dir, "MockupDemo", sdk_root)
        mockup_dir = project_dir / ".eguiproject" / "mockup"
        mockup_dir.mkdir(parents=True, exist_ok=True)
        (mockup_dir / "existing.png").write_bytes(b"PNG")
        project.get_startup_page().mockup_image_path = "mockup/existing.png"
        captured = {}

        window = MainWindow(str(sdk_root))
        window.project = project
        window._project_dir = str(project_dir)
        window._current_page = project.get_startup_page()

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
        project = _create_project(project_dir, "MockupDemo", sdk_root)
        captured = {}

        window = MainWindow(str(sdk_root))
        window.project = project
        window._project_dir = str(project_dir)
        window._current_page = project.get_startup_page()

        def fake_get_open_file_name(parent, title, directory, filters):
            captured["directory"] = directory
            return "", ""

        monkeypatch.setattr("ui_designer.ui.main_window.QFileDialog.getOpenFileName", fake_get_open_file_name)

        window._load_background_image()

        assert captured["directory"] == os.path.normpath(os.path.abspath(project_dir))
        _close_window(window)

    def test_xml_edit_updates_page_mockup_metadata(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "XmlMockupDemo"
        project = _create_project(project_dir, "XmlMockupDemo", sdk_root)
        xml_page = project.get_startup_page()
        xml_page.mockup_image_path = "mockup/design.png"
        xml_page.mockup_image_visible = False
        xml_page.mockup_image_opacity = 0.45
        xml_text = xml_page.to_xml_string()
        xml_page.mockup_image_path = ""
        xml_page.mockup_image_visible = True
        xml_page.mockup_image_opacity = 0.3
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "MockupUndoDemo"
        project = _create_project(project_dir, "MockupUndoDemo", sdk_root)
        page = project.get_startup_page()
        page.mockup_image_path = "mockup/design.png"
        page.mockup_image_visible = True
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "RenameResourceDemo", sdk_root)
        detail_page = project.create_new_page("detail_page")

        image_a = WidgetModel("image", name="image_a")
        image_a.properties["image_file"] = "star.png"
        project.get_page_by_name("main_page").root_widget.add_child(image_a)

        image_b = WidgetModel("image", name="image_b")
        image_b.properties["image_file"] = "star.png"
        detail_page.root_widget.add_child(image_b)

        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "ReplaceMissingResourceDemo"
        project = _create_project(project_dir, "ReplaceMissingResourceDemo", sdk_root)
        detail_page = project.create_new_page("detail_page")
        project.resource_catalog.add_image("star.png")

        image_a = WidgetModel("image", name="image_a")
        image_a.properties["image_file"] = "star.png"
        project.get_page_by_name("main_page").root_widget.add_child(image_a)

        image_b = WidgetModel("image", name="image_b")
        image_b.properties["image_file"] = "star.png"
        detail_page.root_widget.add_child(image_b)

        project.save(str(project_dir))

        replacement_dir = tmp_path / "external_images"
        replacement_dir.mkdir()
        replacement_path = replacement_dir / "star_new.png"
        replacement_path.write_bytes(b"PNG")

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "ReplaceMissingBatchPreviewDemo"
        project = _create_project(project_dir, "ReplaceMissingBatchPreviewDemo", sdk_root)
        detail_page = project.create_new_page("detail_page")
        project.resource_catalog.add_image("star.png")

        image_a = WidgetModel("image", name="image_a")
        image_a.properties["image_file"] = "star.png"
        project.get_page_by_name("main_page").root_widget.add_child(image_a)

        image_b = WidgetModel("image", name="image_b")
        image_b.properties["image_file"] = "star.png"
        detail_page.root_widget.add_child(image_b)

        project.save(str(project_dir))

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
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
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

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "RenameResourceSignalDemo"
        project = _create_project(project_dir, "RenameResourceSignalDemo", sdk_root)
        detail_page = project.create_new_page("detail_page")
        project.resource_catalog.add_image("star.png")

        images_dir = project_dir / ".eguiproject" / "resources" / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        (images_dir / "star.png").write_bytes(b"PNG")

        image_a = WidgetModel("image", name="image_a")
        image_a.properties["image_file"] = "star.png"
        project.get_page_by_name("main_page").root_widget.add_child(image_a)

        image_b = WidgetModel("image", name="image_b")
        image_b.properties["image_file"] = "star.png"
        detail_page.root_widget.add_child(image_b)

        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(
            "ui_designer.ui.resource_panel.QInputDialog.getText",
            lambda *args, **kwargs: ("star_new.png", True),
        )
        monkeypatch.setattr(window.res_panel, "_confirm_reference_impact", lambda *args: True)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "DeleteResourceDemo", sdk_root)
        label = WidgetModel("label", name="title")
        label.properties["font_file"] = "demo.ttf"
        project.get_page_by_name("main_page").root_widget.add_child(label)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "AssignTextResourceDemo", sdk_root)
        label = WidgetModel("label", name="title")
        label.properties["font_file"] = "demo.ttf"
        project.get_page_by_name("main_page").root_widget.add_child(label)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
        window._selected_widget = label
        window.property_panel.set_widget(label)

        window._on_resource_selected("text", "chars.txt")

        assert label.properties["font_text_file"] == "chars.txt"
        assert window._undo_manager.get_stack("main_page").is_dirty() is True
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_resource_rename_updates_text_references_across_pages(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "RenameTextResourceDemo"
        project = _create_project(project_dir, "RenameTextResourceDemo", sdk_root)
        detail_page = project.create_new_page("detail_page")

        label_a = WidgetModel("label", name="label_a")
        label_a.properties["font_file"] = "demo.ttf"
        label_a.properties["font_text_file"] = "chars.txt"
        project.get_page_by_name("main_page").root_widget.add_child(label_a)

        label_b = WidgetModel("label", name="label_b")
        label_b.properties["font_file"] = "demo.ttf"
        label_b.properties["font_text_file"] = "chars.txt"
        detail_page.root_widget.add_child(label_b)

        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "DeleteTextResourceDemo", sdk_root)
        label = WidgetModel("label", name="title")
        label.properties["font_file"] = "demo.ttf"
        label.properties["font_text_file"] = "chars.txt"
        project.get_page_by_name("main_page").root_widget.add_child(label)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "DeleteStringKeyDemo"
        project = _create_project(project_dir, "DeleteStringKeyDemo", sdk_root)
        detail_page = project.create_new_page("detail_page")
        project.string_catalog.set("greeting", "Hello", DEFAULT_LOCALE)
        project.string_catalog.set("greeting", "Ni Hao", "zh")

        title = WidgetModel("label", name="title")
        title.properties["text"] = "@string/greeting"
        project.get_page_by_name("main_page").root_widget.add_child(title)

        subtitle = WidgetModel("label", name="subtitle")
        subtitle.properties["text"] = "@string/greeting"
        detail_page.root_widget.add_child(subtitle)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.res_panel, "_confirm_reference_impact", lambda *args: True)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "RenameStringKeyDemo"
        project = _create_project(project_dir, "RenameStringKeyDemo", sdk_root)
        detail_page = project.create_new_page("detail_page")
        project.string_catalog.set("greeting", "Hello", DEFAULT_LOCALE)
        project.string_catalog.set("greeting", "Ni Hao", "zh")

        title = WidgetModel("label", name="title")
        title.properties["text"] = "@string/greeting"
        project.get_page_by_name("main_page").root_widget.add_child(title)

        subtitle = WidgetModel("label", name="subtitle")
        subtitle.properties["text"] = "@string/greeting"
        detail_page.root_widget.add_child(subtitle)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(
            "ui_designer.ui.resource_panel.QInputDialog.getText",
            lambda *args, **kwargs: ("salutation", True),
        )
        monkeypatch.setattr(window.res_panel, "_confirm_reference_impact", lambda *args: True)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
            import tempfile
            from pathlib import Path

            os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

            repo_root = Path({repr(str(repo_root))})
            sys.path.insert(0, str(repo_root / "scripts"))

            from PyQt5.QtWidgets import QApplication

            from ui_designer.model.project import Project
            from ui_designer.model.string_resource import DEFAULT_LOCALE
            from ui_designer.model.widget_model import WidgetModel
            from ui_designer.ui.main_window import MainWindow


            def create_sdk_root(root: Path):
                (root / "src").mkdir(parents=True)
                (root / "porting" / "designer").mkdir(parents=True)
                (root / "Makefile").write_text("all:\\n", encoding="utf-8")


            def create_project(project_dir: Path, app_name: str, sdk_root: Path):
                project = Project(screen_width=240, screen_height=320, app_name=app_name)
                project.sdk_root = str(sdk_root)
                project.project_dir = str(project_dir)
                project.create_new_page("main_page")
                project.save(str(project_dir))
                return project


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


            temp_root = Path(tempfile.mkdtemp(prefix="ui_designer_string_delete_inspect_", dir=str(repo_root)))
            app = QApplication.instance() or QApplication([])
            try:
                sdk_root = temp_root / "sdk"
                create_sdk_root(sdk_root)
                project_dir = temp_root / "DeleteStringKeyInspectDemo"
                project = create_project(project_dir, "DeleteStringKeyInspectDemo", sdk_root)
                detail_page = project.create_new_page("detail_page")
                project.string_catalog.set("greeting", "Hello", DEFAULT_LOCALE)

                subtitle = WidgetModel("label", name="subtitle")
                subtitle.properties["text"] = "@string/greeting"
                detail_page.root_widget.add_child(subtitle)
                project.save(str(project_dir))

                window = MainWindow(str(sdk_root))
                window._recreate_compiler = lambda _window=window: setattr(_window, "compiler", DisabledCompiler())
                window._trigger_compile = lambda: None

                def inspect_usage(*args):
                    window.res_panel.usage_activated.emit("detail_page", "subtitle")
                    return False

                window.res_panel._confirm_reference_impact = inspect_usage

                window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
            import tempfile
            from pathlib import Path

            os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

            repo_root = Path({repr(str(repo_root))})
            sys.path.insert(0, str(repo_root / "scripts"))

            from PyQt5.QtWidgets import QApplication

            from ui_designer.model.project import Project
            from ui_designer.model.string_resource import DEFAULT_LOCALE
            from ui_designer.model.widget_model import WidgetModel
            from ui_designer.ui.main_window import MainWindow


            def create_sdk_root(root: Path):
                (root / "src").mkdir(parents=True)
                (root / "porting" / "designer").mkdir(parents=True)
                (root / "Makefile").write_text("all:\\n", encoding="utf-8")


            def create_project(project_dir: Path, app_name: str, sdk_root: Path):
                project = Project(screen_width=240, screen_height=320, app_name=app_name)
                project.sdk_root = str(sdk_root)
                project.project_dir = str(project_dir)
                project.create_new_page("main_page")
                project.save(str(project_dir))
                return project


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


            temp_root = Path(tempfile.mkdtemp(prefix="ui_designer_string_usage_", dir=str(repo_root)))
            app = QApplication.instance() or QApplication([])
            try:
                sdk_root = temp_root / "sdk"
                create_sdk_root(sdk_root)
                project_dir = temp_root / "StringUsageNavigationDemo"
                project = create_project(project_dir, "StringUsageNavigationDemo", sdk_root)
                detail_page = project.create_new_page("detail_page")
                project.string_catalog.set("greeting", "Hello", DEFAULT_LOCALE)

                subtitle = WidgetModel("label", name="subtitle")
                subtitle.properties["text"] = "@string/greeting"
                detail_page.root_widget.add_child(subtitle)
                project.save(str(project_dir))

                window = MainWindow(str(sdk_root))
                window._recreate_compiler = lambda _window=window: setattr(_window, "compiler", DisabledCompiler())
                window._trigger_compile = lambda: None

                window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "ResourceUsageNavigationDemo"
        project = _create_project(project_dir, "ResourceUsageNavigationDemo", sdk_root)
        detail_page = project.create_new_page("detail_page")
        project.resource_catalog.add_image("star.png")

        hero = WidgetModel("image", name="hero")
        hero.properties["image_file"] = "star.png"
        detail_page.root_widget.add_child(hero)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)

        assert window._current_page.name == "main_page"

        window.res_panel._select_resource_item("image", "star.png")
        window.res_panel._on_usage_item_activated(window.res_panel._usage_table.item(0, 0))

        assert window._current_page.name == "detail_page"
        assert window._selection_state.primary is hero
        assert window._selection_state.widgets == [hero]
        assert window.statusBar().currentMessage() == "Focused resource usage: detail_page/hero."
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_resource_usage_filter_tracks_current_page(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "ResourceUsageFilterDemo"
        project = _create_project(project_dir, "ResourceUsageFilterDemo", sdk_root)
        detail_page = project.create_new_page("detail_page")
        project.resource_catalog.add_image("star.png")

        hero_main = WidgetModel("image", name="hero_main")
        hero_main.properties["image_file"] = "star.png"
        project.get_page_by_name("main_page").root_widget.add_child(hero_main)

        hero_detail = WidgetModel("image", name="hero_detail")
        hero_detail.properties["image_file"] = "star.png"
        detail_page.root_widget.add_child(hero_detail)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
        window.res_panel._usage_current_page_only.setChecked(True)
        window.res_panel._select_resource_item("image", "star.png")

        assert window._current_page.name == "main_page"
        assert window.res_panel._usage_table.rowCount() == 1
        assert window.res_panel._usage_table.item(0, 0).text() == "main_page"

        window._switch_page("detail_page")

        assert window.res_panel._usage_table.rowCount() == 1
        assert window.res_panel._usage_table.item(0, 0).text() == "detail_page"
        assert window.res_panel._usage_summary.text() == "'star.png' is used by 1 widget on the current page (2 total across 2 pages)."
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_poll_project_files_auto_reloads_clean_project(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "WatchDemo"
        project = _create_project(project_dir, "WatchDemo", sdk_root)

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)

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
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        assert "External project changes detected" in window.statusBar().currentMessage()
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_reload_project_from_disk_preserves_current_page(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.project import Project
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "ReloadDemo"

        project = Project(screen_width=240, screen_height=320, app_name="ReloadDemo")
        project.sdk_root = str(sdk_root)
        project.project_dir = str(project_dir)
        project.create_new_page("main_page")
        project.create_new_page("detail_page")
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
        window._switch_page("detail_page")

        reloaded = Project.load(str(project_dir))
        reloaded.startup_page = "main_page"
        reloaded.create_new_page("summary_page")
        reloaded.save(str(project_dir))

        assert window._reload_project_from_disk() is True
        assert window._current_page is not None
        assert window._current_page.name == "detail_page"
        assert window.project.get_page_by_name("summary_page") is not None
        _close_window(window)

    def test_page_navigator_is_populated_and_tracks_current_page(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "NavigatorDemo"
        project = _create_project(project_dir, "NavigatorDemo", sdk_root)
        project.create_new_page("detail_page")
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)

        assert set(window.page_navigator._pages.keys()) == {"main_page", "detail_page"}
        assert window.page_navigator._current_page == "main_page"
        assert window.page_navigator._startup_page == "main_page"
        assert "Startup page: main_page." in window.page_navigator.accessibleName()
        assert "Startup page" in window.page_navigator._thumbnails["main_page"].accessibleName()
        assert "Startup page: main_page." in window.page_tab_bar.accessibleName()

        window._switch_page("detail_page")

        assert window.page_navigator._current_page == "detail_page"
        assert window.page_navigator._startup_page == "main_page"

        window._on_startup_changed("detail_page")

        assert window.project.startup_page == "detail_page"
        assert window.page_navigator._startup_page == "detail_page"
        assert "Startup page: detail_page." in window.page_navigator.accessibleName()
        assert "Startup page" in window.page_navigator._thumbnails["detail_page"].accessibleName()
        assert "Startup page" not in window.page_navigator._thumbnails["main_page"].accessibleName()
        assert "Startup page: detail_page." in window.page_tab_bar.accessibleName()
        _close_window(window)

    def test_page_navigator_copy_and_template_add_keep_pages_in_sync(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "NavigatorActionsDemo"
        project = _create_project(project_dir, "NavigatorActionsDemo", sdk_root)

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)

        window._duplicate_page_from_navigator("main_page")
        assert window.project.get_page_by_name("main_page_copy") is not None
        assert "main_page_copy" in window.page_navigator._pages
        assert window._current_page.name == "main_page_copy"

        window._on_page_add_from_template("detail", "main_page")
        template_page = window.project.get_page_by_name("detail_page")
        assert template_page is not None
        assert "detail_page" in window.page_navigator._pages
        assert window._current_page.name == "detail_page"
        assert [child.name for child in template_page.root_widget.children] == ["title", "hero_image", "description"]
        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_dirty_page_indicators_sync_across_tabs_navigator_and_project_tree(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "DirtyPagesDemo"
        project = _create_project(project_dir, "DirtyPagesDemo", sdk_root)
        project.create_new_page("detail_page")
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)

        assert window.page_tab_bar.accessibleName() == (
            "Page tabs: 1 open page. Current page: main_page. Startup page: main_page. No dirty pages."
        )
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
        assert texts_by_page["main_page"].endswith("main_page*")
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

    def test_page_tab_context_menu_actions_expose_status_hints(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PageTabContextMenuDemo"
        project = _create_project(project_dir, "PageTabContextMenuDemo", sdk_root)
        project.create_new_page("detail_page")
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)

        menu, actions = window._build_page_tab_context_menu(0)
        assert actions["close_tab"].toolTip() == "Close this open page tab."
        assert actions["close_tab"].statusTip() == actions["close_tab"].toolTip()
        assert actions["close_others"].isEnabled() is False
        assert actions["close_others"].toolTip() == (
            "Close all other open page tabs. Unavailable: only 1 page tab is open."
        )
        assert actions["close_others"].statusTip() == actions["close_others"].toolTip()
        assert actions["close_all"].toolTip() == "Close all open page tabs."
        assert actions["close_all"].statusTip() == actions["close_all"].toolTip()
        menu.deleteLater()

        window._switch_page("detail_page")
        menu, actions = window._build_page_tab_context_menu(0)
        assert actions["close_tab"].toolTip() == "Close this open page tab."
        assert actions["close_tab"].statusTip() == actions["close_tab"].toolTip()
        assert actions["close_others"].isEnabled() is True
        assert actions["close_others"].toolTip() == "Close all other open page tabs."
        assert actions["close_others"].statusTip() == actions["close_others"].toolTip()
        assert actions["close_all"].toolTip() == "Close all open page tabs."
        assert actions["close_all"].statusTip() == actions["close_all"].toolTip()
        menu.deleteLater()
        _close_window(window)

    def test_copy_and_paste_selection_creates_unique_widget_names(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "ClipboardDemo"
        project = _create_project(project_dir, "ClipboardDemo", sdk_root)
        page = project.get_startup_page()
        label = WidgetModel("label", name="title", x=10, y=10, width=80, height=20)
        page.root_widget.add_child(label)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)

        def fake_set_selection(widgets=None, primary=None, sync_tree=True, sync_preview=True):
            window._selection_state.set_widgets(widgets or [], primary=primary)
            window._selected_widget = window._selection_state.primary

        monkeypatch.setattr(window, "_set_selection", fake_set_selection)
        window._selected_widget = label

        window._copy_selection()
        window._paste_selection()

        label_names = [child.name for child in page.root_widget.children if child.widget_type == "label"]
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
        project = _create_project(project_dir, "DiagnosticsDemo", sdk_root)
        page = project.get_startup_page()

        invalid = WidgetModel("label", name="bad-name", x=8, y=8, width=60, height=20)
        duplicate_a = WidgetModel("label", name="dup_name", x=20, y=40, width=60, height=20)
        duplicate_b = WidgetModel("label", name="dup_name", x=230, y=40, width=30, height=20)
        layout_parent = WidgetModel("linearlayout", name="layout_parent", x=0, y=120, width=240, height=80)
        managed = WidgetModel("label", name="managed_widget", x=12, y=8, width=80, height=20)
        managed.designer_locked = True
        managed.designer_hidden = True
        layout_parent.add_child(managed)
        missing = WidgetModel("image", name="missing_image", x=16, y=220, width=48, height=48)
        missing.properties["image_file"] = "missing.png"

        page.root_widget.add_child(invalid)
        page.root_widget.add_child(duplicate_a)
        page.root_widget.add_child(duplicate_b)
        page.root_widget.add_child(layout_parent)
        page.root_widget.add_child(missing)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "ProjectCallbackDiagnosticsDemo", sdk_root)
        detail_page = project.create_new_page("detail_page")
        main_button = WidgetModel("button", name="confirm_button", x=8, y=8, width=80, height=28)
        detail_button = WidgetModel("button", name="confirm_button_2", x=8, y=8, width=80, height=28)
        main_button.on_click = "on_confirm"
        detail_button.on_click = "on_confirm"
        project.get_startup_page().root_widget.add_child(main_button)
        detail_page.root_widget.add_child(detail_button)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "ProjectCallbackDiagnosticFocusDemo", sdk_root)
        detail_page = project.create_new_page("detail_page")
        main_button = WidgetModel("button", name="confirm_button", x=8, y=8, width=80, height=28)
        detail_button = WidgetModel("button", name="confirm_button_2", x=8, y=8, width=80, height=28)
        main_button.on_click = "on_confirm"
        detail_button.on_click = "on_confirm"
        project.get_startup_page().root_widget.add_child(main_button)
        detail_page.root_widget.add_child(detail_button)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        def fake_set_selection(widgets=None, primary=None, sync_tree=True, sync_preview=True):
            window._selection_state.set_widgets(widgets or [], primary=primary)
            window._selected_widget = window._selection_state.primary

        monkeypatch.setattr(window, "_set_selection", fake_set_selection)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "DiagnosticsFilterDemo", sdk_root)
        page = project.get_startup_page()

        invalid = WidgetModel("label", name="bad-name", x=8, y=8, width=60, height=20)
        duplicate_a = WidgetModel("label", name="dup_name", x=20, y=40, width=60, height=20)
        duplicate_b = WidgetModel("label", name="dup_name", x=230, y=40, width=30, height=20)
        layout_parent = WidgetModel("linearlayout", name="layout_parent", x=0, y=120, width=240, height=80)
        managed = WidgetModel("label", name="managed_widget", x=12, y=8, width=80, height=20)
        managed.designer_locked = True
        managed.designer_hidden = True
        layout_parent.add_child(managed)
        missing = WidgetModel("image", name="missing_image", x=16, y=220, width=48, height=48)
        missing.properties["image_file"] = "missing.png"

        page.root_widget.add_child(invalid)
        page.root_widget.add_child(duplicate_a)
        page.root_widget.add_child(duplicate_b)
        page.root_widget.add_child(layout_parent)
        page.root_widget.add_child(missing)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "DiagnosticsResetViewDemo", sdk_root)
        page = project.get_startup_page()

        invalid = WidgetModel("label", name="bad-name", x=8, y=8, width=60, height=20)
        duplicate_a = WidgetModel("label", name="dup_name", x=20, y=40, width=60, height=20)
        duplicate_b = WidgetModel("label", name="dup_name", x=230, y=40, width=30, height=20)
        layout_parent = WidgetModel("linearlayout", name="layout_parent", x=0, y=120, width=240, height=80)
        managed = WidgetModel("label", name="managed_widget", x=12, y=8, width=80, height=20)
        managed.designer_locked = True
        managed.designer_hidden = True
        layout_parent.add_child(managed)
        missing = WidgetModel("image", name="missing_image", x=16, y=220, width=48, height=48)
        missing.properties["image_file"] = "missing.png"

        page.root_widget.add_child(invalid)
        page.root_widget.add_child(duplicate_a)
        page.root_widget.add_child(duplicate_b)
        page.root_widget.add_child(layout_parent)
        page.root_widget.add_child(missing)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "DiagnosticsRestoreFilterDemo", sdk_root)
        page = project.get_startup_page()

        invalid = WidgetModel("label", name="bad-name", x=8, y=8, width=60, height=20)
        missing = WidgetModel("image", name="missing_image", x=16, y=48, width=48, height=48)
        missing.properties["image_file"] = "missing.png"
        page.root_widget.add_child(invalid)
        page.root_widget.add_child(missing)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
        window._update_diagnostics_panel()
        filter_combo = window.diagnostics_panel._severity_filter_combo
        filter_combo.setCurrentIndex(filter_combo.findData("warning"))

        _close_window(window)

        assert isolated_config.diagnostics_view == {"severity_filter": "warning"}

        restored = MainWindow(str(sdk_root))
        monkeypatch.setattr(restored, "_recreate_compiler", lambda: setattr(restored, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(restored, "_trigger_compile", lambda: None)

        restored._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "DiagnosticsOpenFirstErrorDemo", sdk_root)
        page = project.get_startup_page()

        invalid = WidgetModel("label", name="bad-name", x=8, y=8, width=60, height=20)
        missing = WidgetModel("image", name="missing_image", x=16, y=48, width=48, height=48)
        missing.properties["image_file"] = "missing.png"
        page.root_widget.add_child(invalid)
        page.root_widget.add_child(missing)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        def fake_set_selection(widgets=None, primary=None, sync_tree=True, sync_preview=True):
            window._selection_state.set_widgets(widgets or [], primary=primary)
            window._selected_widget = window._selection_state.primary

        monkeypatch.setattr(window, "_set_selection", fake_set_selection)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "DiagnosticsNoErrorOpenDemo", sdk_root)
        page = project.get_startup_page()

        missing = WidgetModel("image", name="missing_image", x=16, y=48, width=48, height=48)
        missing.properties["image_file"] = "missing.png"
        page.root_widget.add_child(missing)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "DiagnosticsOpenFirstWarningDemo", sdk_root)
        page = project.get_startup_page()

        invalid = WidgetModel("label", name="bad-name", x=8, y=8, width=60, height=20)
        missing = WidgetModel("image", name="missing_image", x=16, y=48, width=48, height=48)
        missing.properties["image_file"] = "missing.png"
        page.root_widget.add_child(invalid)
        page.root_widget.add_child(missing)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        def fake_set_selection(widgets=None, primary=None, sync_tree=True, sync_preview=True):
            window._selection_state.set_widgets(widgets or [], primary=primary)
            window._selected_widget = window._selection_state.primary

        monkeypatch.setattr(window, "_set_selection", fake_set_selection)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "DiagnosticsNoWarningOpenDemo", sdk_root)
        page = project.get_startup_page()

        invalid = WidgetModel("label", name="bad-name", x=8, y=8, width=60, height=20)
        page.root_widget.add_child(invalid)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "DiagnosticsOpenSelectedDemo", sdk_root)
        page = project.get_startup_page()

        invalid = WidgetModel("label", name="bad-name", x=8, y=8, width=60, height=20)
        missing = WidgetModel("image", name="missing_image", x=16, y=48, width=48, height=48)
        missing.properties["image_file"] = "missing.png"
        page.root_widget.add_child(invalid)
        page.root_widget.add_child(missing)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        def fake_set_selection(widgets=None, primary=None, sync_tree=True, sync_preview=True):
            window._selection_state.set_widgets(widgets or [], primary=primary)
            window._selected_widget = window._selection_state.primary

        monkeypatch.setattr(window, "_set_selection", fake_set_selection)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "DiagnosticsSelectionFilterDemo", sdk_root)
        page = project.get_startup_page()

        invalid = WidgetModel("label", name="bad-name", x=8, y=8, width=60, height=20)
        missing = WidgetModel("image", name="missing_image", x=16, y=48, width=48, height=48)
        missing.properties["image_file"] = "missing.png"
        page.root_widget.add_child(invalid)
        page.root_widget.add_child(missing)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        def fake_set_selection(widgets=None, primary=None, sync_tree=True, sync_preview=True):
            window._selection_state.set_widgets(widgets or [], primary=primary)
            window._selected_widget = window._selection_state.primary

        monkeypatch.setattr(window, "_set_selection", fake_set_selection)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "DiagnosticsSelectionRefreshDemo", sdk_root)
        page = project.get_startup_page()

        invalid = WidgetModel("label", name="bad-name", x=8, y=8, width=60, height=20)
        missing = WidgetModel("image", name="missing_image", x=16, y=48, width=48, height=48)
        missing.properties["image_file"] = "missing.png"
        page.root_widget.add_child(invalid)
        page.root_widget.add_child(missing)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        def fake_set_selection(widgets=None, primary=None, sync_tree=True, sync_preview=True):
            window._selection_state.set_widgets(widgets or [], primary=primary)
            window._selected_widget = window._selection_state.primary

        monkeypatch.setattr(window, "_set_selection", fake_set_selection)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "DiagnosticsNonNavigableDemo", sdk_root)
        page = project.get_startup_page()

        layout_parent = WidgetModel("linearlayout", name="layout_parent", x=0, y=0, width=240, height=80)
        managed = WidgetModel("label", name="managed_widget", x=12, y=8, width=80, height=20)
        managed.designer_locked = True
        managed.designer_hidden = True
        layout_parent.add_child(managed)
        page.root_widget.add_child(layout_parent)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "DiagnosticsCopyDemo", sdk_root)
        page = project.get_startup_page()

        invalid = WidgetModel("label", name="bad-name", x=8, y=8, width=60, height=20)
        missing = WidgetModel("image", name="missing_image", x=16, y=48, width=48, height=48)
        missing.properties["image_file"] = "missing.png"
        page.root_widget.add_child(invalid)
        page.root_widget.add_child(missing)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "DiagnosticsCopyFilteredDemo", sdk_root)
        page = project.get_startup_page()

        invalid = WidgetModel("label", name="bad-name", x=8, y=8, width=60, height=20)
        missing = WidgetModel("image", name="missing_image", x=16, y=48, width=48, height=48)
        missing.properties["image_file"] = "missing.png"
        page.root_widget.add_child(invalid)
        page.root_widget.add_child(missing)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
        window._update_diagnostics_panel()
        filter_combo = window.diagnostics_panel._severity_filter_combo
        filter_combo.setCurrentIndex(filter_combo.findData("warning"))

        QApplication.clipboard().clear()
        window.diagnostics_panel._copy_button.click()

        copied = QApplication.clipboard().text()
        assert copied.startswith("Diagnostics: ")
        assert "Filter: warnings (1 item(s))" in copied
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
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "DiagnosticsCopyJsonDemo", sdk_root)
        page = project.get_startup_page()

        invalid = WidgetModel("label", name="bad-name", x=8, y=8, width=60, height=20)
        missing = WidgetModel("image", name="missing_image", x=16, y=48, width=48, height=48)
        missing.properties["image_file"] = "missing.png"
        page.root_widget.add_child(invalid)
        page.root_widget.add_child(missing)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "DiagnosticsCopyJsonFilteredDemo", sdk_root)
        page = project.get_startup_page()

        invalid = WidgetModel("label", name="bad-name", x=8, y=8, width=60, height=20)
        missing = WidgetModel("image", name="missing_image", x=16, y=48, width=48, height=48)
        missing.properties["image_file"] = "missing.png"
        page.root_widget.add_child(invalid)
        page.root_widget.add_child(missing)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "DiagnosticsCopyJsonSelectedDemo", sdk_root)
        page = project.get_startup_page()

        invalid = WidgetModel("label", name="bad-name", x=8, y=8, width=60, height=20)
        missing = WidgetModel("image", name="missing_image", x=16, y=48, width=48, height=48)
        missing.properties["image_file"] = "missing.png"
        page.root_widget.add_child(invalid)
        page.root_widget.add_child(missing)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "DiagnosticsCopyJsonMetadataDemo"
        project = _create_project(project_dir, "DiagnosticsCopyJsonMetadataDemo", sdk_root)
        page = project.get_startup_page()
        page.user_fields = [{"name": "bad-name", "type": "int", "default": "0"}]
        page.timers = [{"name": "refresh_timer", "callback": "", "delay_ms": "1000", "period_ms": "1000", "auto_start": False}]
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "DiagnosticsCopyJsonProjectTargetsDemo", sdk_root)
        detail_page = project.create_new_page("detail_page")
        main_button = WidgetModel("button", name="confirm_button", x=8, y=8, width=80, height=28)
        detail_button = WidgetModel("button", name="confirm_button_2", x=8, y=8, width=80, height=28)
        main_button.on_click = "on_confirm"
        detail_button.on_click = "on_confirm"
        project.get_startup_page().root_widget.add_child(main_button)
        detail_page.root_widget.add_child(detail_button)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "DiagnosticsExportDemo", sdk_root)
        page = project.get_startup_page()

        invalid = WidgetModel("label", name="bad-name", x=8, y=8, width=60, height=20)
        missing = WidgetModel("image", name="missing_image", x=16, y=48, width=48, height=48)
        missing.properties["image_file"] = "missing.png"
        page.root_widget.add_child(invalid)
        page.root_widget.add_child(missing)
        project.save(str(project_dir))

        export_path = tmp_path / "exports" / "diagnostics-summary"

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(
            "ui_designer.ui.main_window.QFileDialog.getSaveFileName",
            lambda *args, **kwargs: (str(export_path), "Text Files (*.txt)"),
        )

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        def unexpected_get_save_file_name(*args, **kwargs):
            raise AssertionError("getSaveFileName should not be called without diagnostics")

        monkeypatch.setattr("ui_designer.ui.main_window.QFileDialog.getSaveFileName", unexpected_get_save_file_name)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "DiagnosticsJsonDemo", sdk_root)
        page = project.get_startup_page()

        invalid = WidgetModel("label", name="bad-name", x=8, y=8, width=60, height=20)
        missing = WidgetModel("image", name="missing_image", x=16, y=48, width=48, height=48)
        missing.properties["image_file"] = "missing.png"
        page.root_widget.add_child(invalid)
        page.root_widget.add_child(missing)
        project.save(str(project_dir))

        export_path = tmp_path / "exports" / "diagnostics"

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(
            "ui_designer.ui.main_window.QFileDialog.getSaveFileName",
            lambda *args, **kwargs: (str(export_path), "JSON Files (*.json)"),
        )

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        def unexpected_get_save_file_name(*args, **kwargs):
            raise AssertionError("getSaveFileName should not be called without diagnostics")

        monkeypatch.setattr("ui_designer.ui.main_window.QFileDialog.getSaveFileName", unexpected_get_save_file_name)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "DiagnosticFocusDemo", sdk_root)
        detail_page = project.create_new_page("detail_page")
        target = WidgetModel("label", name="target", x=16, y=16, width=80, height=20)
        detail_page.root_widget.add_child(target)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)

        def fake_set_selection(widgets=None, primary=None, sync_tree=True, sync_preview=True):
            window._selection_state.set_widgets(widgets or [], primary=primary)
            window._selected_widget = window._selection_state.primary

        monkeypatch.setattr(window, "_set_selection", fake_set_selection)

        assert window._current_page.name == "main_page"

        window._on_diagnostic_requested("detail_page", "target")

        assert window._current_page.name == "detail_page"
        assert window._selection_state.primary is target
        assert window._selection_state.widgets == [target]
        assert window.statusBar().currentMessage() == "Opened diagnostic target: detail_page/target."

        window._undo_manager.mark_all_saved()
        _close_window(window)

    def test_page_field_diagnostic_activation_selects_field_row(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "FieldDiagnosticFocusDemo"
        project = _create_project(project_dir, "FieldDiagnosticFocusDemo", sdk_root)
        page = project.get_startup_page()
        page.user_fields = [{"name": "bad-name", "type": "int", "default": "0"}]
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "TimerDiagnosticFocusDemo"
        project = _create_project(project_dir, "TimerDiagnosticFocusDemo", sdk_root)
        page = project.get_startup_page()
        page.timers = [{"name": "refresh_timer", "callback": "", "delay_ms": "1000", "period_ms": "1000", "auto_start": False}]
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
            import tempfile
            from pathlib import Path

            os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

            repo_root = Path({repr(str(repo_root))})
            sys.path.insert(0, str(repo_root / "scripts"))

            from PyQt5.QtWidgets import QApplication

            from ui_designer.model.project import Project
            from ui_designer.model.widget_model import WidgetModel
            from ui_designer.ui.main_window import MainWindow


            def create_sdk_root(root: Path):
                (root / "src").mkdir(parents=True)
                (root / "porting" / "designer").mkdir(parents=True)
                (root / "Makefile").write_text("all:\\n", encoding="utf-8")


            def create_project(project_dir: Path, app_name: str, sdk_root: Path):
                project = Project(screen_width=240, screen_height=320, app_name=app_name)
                project.sdk_root = str(sdk_root)
                project.project_dir = str(project_dir)
                project.create_new_page("main_page")
                project.save(str(project_dir))
                return project


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


            temp_root = Path(tempfile.mkdtemp(prefix="ui_designer_diag_resource_", dir=str(repo_root)))
            app = QApplication.instance() or QApplication([])
            try:
                sdk_root = temp_root / "sdk"
                create_sdk_root(sdk_root)
                project_dir = temp_root / "DiagnosticMissingResourceDemo"
                project = create_project(project_dir, "DiagnosticMissingResourceDemo", sdk_root)
                missing = WidgetModel("image", name="missing_image", x=16, y=16, width=48, height=48)
                missing.properties["image_file"] = "ghost.png"
                project.get_page_by_name("main_page").root_widget.add_child(missing)
                project.save(str(project_dir))

                window = MainWindow(str(sdk_root))
                window._recreate_compiler = lambda _window=window: setattr(_window, "compiler", DisabledCompiler())
                window._trigger_compile = lambda: None

                window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)

                item = window.diagnostics_panel._list.item(0)
                window.diagnostics_panel._on_item_activated(item)

                assert window._selection_state.primary is missing
                assert window.res_panel._current_resource_type == "image"
                assert window.res_panel._current_resource_name == "ghost.png"
                assert window.res_panel._tabs.currentIndex() == 0
                assert window.res_panel._usage_summary.text() == "'ghost.png' is used by 1 widget across 1 page."
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
            import tempfile
            from pathlib import Path

            os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

            repo_root = Path({repr(str(repo_root))})
            sys.path.insert(0, str(repo_root / "scripts"))

            from PyQt5.QtWidgets import QApplication

            from ui_designer.model.project import Project
            from ui_designer.model.widget_model import WidgetModel
            from ui_designer.ui.main_window import MainWindow


            def create_sdk_root(root: Path):
                (root / "src").mkdir(parents=True)
                (root / "porting" / "designer").mkdir(parents=True)
                (root / "Makefile").write_text("all:\\n", encoding="utf-8")


            def create_project(project_dir: Path, app_name: str, sdk_root: Path):
                project = Project(screen_width=240, screen_height=320, app_name=app_name)
                project.sdk_root = str(sdk_root)
                project.project_dir = str(project_dir)
                project.create_new_page("main_page")
                project.save(str(project_dir))
                return project


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


            temp_root = Path(tempfile.mkdtemp(prefix="ui_designer_diag_string_", dir=str(repo_root)))
            app = QApplication.instance() or QApplication([])
            try:
                sdk_root = temp_root / "sdk"
                create_sdk_root(sdk_root)
                project_dir = temp_root / "DiagnosticMissingStringDemo"
                project = create_project(project_dir, "DiagnosticMissingStringDemo", sdk_root)
                title = WidgetModel("label", name="title", x=16, y=16, width=80, height=20)
                title.properties["text"] = "@string/missing_key"
                project.get_page_by_name("main_page").root_widget.add_child(title)
                project.save(str(project_dir))

                window = MainWindow(str(sdk_root))
                window._recreate_compiler = lambda _window=window: setattr(_window, "compiler", DisabledCompiler())
                window._trigger_compile = lambda: None

                window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)

                item = window.diagnostics_panel._list.item(0)
                window.diagnostics_panel._on_item_activated(item)

                assert window._selection_state.primary is title
                assert window.res_panel._current_resource_type == "string"
                assert window.res_panel._current_resource_name == "missing_key"
                assert window.res_panel._tabs.currentIndex() == 3
                assert window.res_panel._usage_summary.text() == "'missing_key' is used by 1 widget across 1 page."
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
        _close_window(window)

    def test_workspace_panel_preferences_restore_from_config(self, qapp, isolated_config):
        from ui_designer.ui.main_window import MainWindow
        from ui_designer.ui.project_workspace import ProjectWorkspacePanel

        isolated_config.workspace_left_panel = "widgets"
        isolated_config.workspace_state = {"project_workspace_view": ProjectWorkspacePanel.VIEW_THUMBNAILS}
        isolated_config.workspace_status_panel_state = {"last_action": "open_page_fields"}
        isolated_config.workspace_layout_version = 1

        window = MainWindow("")

        assert window._current_left_panel == "widgets"
        assert window._left_panel_stack.currentWidget() is window.widget_browser
        assert window._project_workspace.current_view() == ProjectWorkspacePanel.VIEW_THUMBNAILS
        assert window.status_center_panel._last_action_label.text() == "Last action: Fields"
        _close_window(window)

    def test_workspace_chips_use_sentence_case_and_humanized_counts(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "WorkspaceChipDemo"
        project = _create_project(project_dir, "WorkspaceChipDemo", sdk_root)
        page = project.get_startup_page()
        label = WidgetModel("label", name="title", x=8, y=8, width=80, height=20)
        page.root_widget.add_child(label)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
        monkeypatch.setattr(window.preview_panel, "is_python_preview_active", lambda: False)
        window._update_workspace_chips()
        window._clear_selection(sync_tree=False, sync_preview=False)

        assert window._sdk_chip.text() == "SDK ready"
        assert window._sdk_chip.accessibleName() == "Workspace status: SDK ready."
        assert window._sdk_chip.toolTip() == "Open Status Center to review SDK readiness."
        assert window._sdk_chip.statusTip() == window._sdk_chip.toolTip()
        assert window._central_stack.accessibleName() == "Main view stack: Editor workspace visible."
        assert window._sdk_status_label.accessibleName().startswith("SDK binding: SDK: ")
        assert window._sdk_status_label.toolTip() == str(sdk_root)
        assert window._sdk_status_label.statusTip() == window._sdk_status_label.toolTip()
        assert window._insert_widget_button.toolTip() == "Open Components and insert a widget into root_group."
        assert window._insert_widget_button.statusTip() == window._insert_widget_button.toolTip()
        assert window._insert_widget_button.accessibleName() == "Insert widget target: root_group."
        assert window._selection_chip.text() == "No selection"
        assert window._selection_chip.accessibleName() == "Workspace status: no selection."
        assert window._selection_chip.toolTip() == "Open Structure to review the current selection."
        assert window._selection_chip.statusTip() == window._selection_chip.toolTip()
        assert window._preview_chip.text() == "Preview idle"
        assert window._preview_chip.accessibleName() == "Workspace status: Preview idle."
        assert window._preview_chip.toolTip() == "Open Debug Output to inspect preview runtime details."
        assert window._preview_chip.statusTip() == window._preview_chip.toolTip()
        assert window._diagnostics_chip.accessibleName() == "Workspace diagnostics: 0 errors and 0 warnings."
        assert window._diagnostics_chip.toolTip() == "Open Diagnostics to review issues and warnings."
        assert window._diagnostics_chip.statusTip() == window._diagnostics_chip.toolTip()
        assert window._project_workspace._page_count_chip.text() == "1 page"
        assert window._project_workspace._active_page_chip.text() == "Active: main_page"
        assert window._project_workspace._dirty_pages_chip.text() == "No dirty pages"

        window._set_selection([label], primary=label, sync_tree=False, sync_preview=False)
        assert window._selection_chip.text() == "1 selected"
        assert window._selection_chip.accessibleName() == "Workspace status: 1 selected."

        window._undo_manager.get_stack("main_page").push("<Page dirty='main' />")
        window._update_window_title()

        assert window._dirty_chip.text() == "Dirty 1"
        assert window._dirty_chip.accessibleName() == "Workspace status: 1 dirty page."
        assert window._dirty_chip.toolTip() == "Open History to review unsaved changes."
        assert window._dirty_chip.statusTip() == window._dirty_chip.toolTip()
        assert window._project_workspace._dirty_pages_chip.text() == "1 dirty page"
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
        assert window._insert_widget_button.toolTip() == "Open or create a project to insert a widget."
        assert window._insert_widget_button.statusTip() == window._insert_widget_button.toolTip()
        assert window._insert_widget_button.accessibleName() == "Insert widget unavailable."
        _close_window(window)

    def test_toolbar_and_top_level_actions_expose_dynamic_hints(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")

        assert window._toolbar.accessibleName() == "Main toolbar: insert, save, edit, and preview commands."
        assert window._toolbar.toolTip() == window._toolbar.accessibleName()
        assert window._toolbar_host.accessibleName() == "Workspace command bar with insert, edit, preview, mode, and status controls."
        assert window._toolbar_host.statusTip() == window._toolbar_host.toolTip()
        assert window._save_action.toolTip() == "Save the current project (Ctrl+S)."
        assert window._save_action.statusTip() == window._save_action.toolTip()
        assert window._undo_action.toolTip() == "Undo the last change on the current page (Ctrl+Z). Unavailable: open a page first."
        assert window._redo_action.toolTip() == "Redo the next change on the current page (Ctrl+Shift+Z). Unavailable: open a page first."
        assert window._copy_action.toolTip() == "Copy the current selection (Ctrl+C). Unavailable: select at least 1 widget."
        assert window._paste_action.toolTip() == "Paste clipboard widgets into the current page (Ctrl+V). Unavailable: open a page first."
        assert window._compile_action.toolTip() == "Compile the current project and run the preview (F5). Unavailable: open a project first."
        assert window._stop_action.toolTip() == "Stop the running preview executable. Unavailable: preview is not running."

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "ToolbarHintDemo"
        project = _create_project(project_dir, "ToolbarHintDemo", sdk_root)
        page = project.get_startup_page()
        label = WidgetModel("label", name="title", x=8, y=8, width=80, height=20)
        page.root_widget.add_child(label)
        project.save(str(project_dir))

        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)

        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)

        assert window._compile_action.toolTip() == (
            "Compile the current project and run the preview (F5). Unavailable: preview disabled for test."
        )
        assert window._compile_action.statusTip() == window._compile_action.toolTip()
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
        _close_window(window)

    def test_editor_mode_buttons_track_current_workspace_mode(self, qapp, isolated_config):
        from ui_designer.ui.editor_tabs import MODE_CODE, MODE_DESIGN, MODE_SPLIT
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")

        assert window._mode_buttons[MODE_DESIGN].toolTip() == "Currently showing Design mode."
        assert window._mode_buttons[MODE_DESIGN].accessibleName() == "Editor mode button: Design. Current mode."
        assert window._mode_buttons[MODE_CODE].toolTip() == "Switch the workspace editor to Code mode."
        assert window._mode_buttons[MODE_CODE].statusTip() == window._mode_buttons[MODE_CODE].toolTip()
        assert window._mode_buttons[MODE_SPLIT].accessibleName() == "Editor mode button: Split."

        window.editor_tabs.set_mode(MODE_CODE)

        assert window._mode_buttons[MODE_CODE].toolTip() == "Currently showing Code mode."
        assert window._mode_buttons[MODE_CODE].accessibleName() == "Editor mode button: Code. Current mode."
        assert window._mode_buttons[MODE_DESIGN].toolTip() == "Switch the workspace editor to Design mode."

        window.editor_tabs.set_mode(MODE_SPLIT)

        assert window._mode_buttons[MODE_SPLIT].toolTip() == "Currently showing Split mode."
        assert window._mode_buttons[MODE_SPLIT].accessibleName() == "Editor mode button: Split. Current mode."
        assert window._mode_buttons[MODE_CODE].toolTip() == "Switch the workspace editor to Code mode."
        _close_window(window)

    def test_workspace_nav_and_bottom_toggle_buttons_expose_current_state(self, qapp, isolated_config):
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")

        assert window._workspace_nav_buttons["project"].toolTip() == "Currently showing Project panel."
        assert window._workspace_nav_buttons["project"].accessibleName() == (
            "Workspace panel button: Project. Current panel."
        )
        assert window._workspace_nav_buttons["status"].toolTip() == "Open Status panel."
        assert window._workspace_nav_buttons["status"].statusTip() == window._workspace_nav_buttons["status"].toolTip()
        assert window._workspace_nav_buttons["status"].accessibleName() == "Workspace panel button: Status."
        assert window._bottom_toggle_button.text() == "Show"
        assert window._bottom_toggle_button.toolTip() == "Show the bottom tools panel."
        assert window._bottom_toggle_button.accessibleName() == "Bottom tools toggle: hidden. Activate to show."

        window._select_left_panel("status")

        assert window._workspace_nav_buttons["status"].toolTip() == "Currently showing Status panel."
        assert window._workspace_nav_buttons["status"].accessibleName() == (
            "Workspace panel button: Status. Current panel."
        )
        assert window._workspace_nav_buttons["project"].toolTip() == "Open Project panel."

        window._set_bottom_panel_visible(True)

        assert window._bottom_toggle_button.text() == "Hide"
        assert window._bottom_toggle_button.toolTip() == "Hide the bottom tools panel."
        assert window._bottom_toggle_button.statusTip() == window._bottom_toggle_button.toolTip()
        assert window._bottom_toggle_button.accessibleName() == "Bottom tools toggle: shown. Activate to hide."
        _close_window(window)

    def test_workspace_tab_widgets_expose_current_section_metadata(self, qapp, isolated_config):
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")

        assert window._inspector_tabs.accessibleName() == "Inspector tabs: Properties selected. 3 tabs."
        assert window._inspector_tabs.toolTip() == "Inspector tabs. Current section: Properties."
        assert window._page_tools_tabs.accessibleName() == "Page tools tabs: Fields selected. 2 tabs."
        assert window._page_tools_tabs.toolTip() == "Page tools tabs. Current section: Fields."
        assert window._bottom_tabs.accessibleName() == "Bottom tools tabs: Diagnostics selected. 3 tabs. Panel hidden."
        assert window._bottom_tabs.toolTip() == "Bottom tools tabs. Current section: Diagnostics. Panel hidden."

        window._show_inspector_tab("page", inner_section="timers")
        window._show_bottom_panel("History")

        assert window._inspector_tabs.accessibleName() == "Inspector tabs: Page selected. 3 tabs."
        assert window._page_tools_tabs.accessibleName() == "Page tools tabs: Timers selected. 2 tabs."
        assert window._bottom_tabs.accessibleName() == "Bottom tools tabs: History selected. 3 tabs. Panel visible."
        assert window._bottom_tabs.statusTip() == window._bottom_tabs.toolTip()
        _close_window(window)

    def test_widget_browser_insert_updates_selection_and_recent_history(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "WidgetBrowserInsertDemo"
        project = _create_project(project_dir, "WidgetBrowserInsertDemo", sdk_root)
        root = project.get_startup_page().root_widget
        container = WidgetModel("group", name="container", x=0, y=0, width=200, height=200)
        root.add_child(container)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
        window._set_selection([container], primary=container, sync_tree=True, sync_preview=True)

        window._show_widget_browser_for_parent(container)
        window._insert_widget_from_browser("button")

        assert window._current_left_panel == "widgets"
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
        project = _create_project(project_dir, "WidgetBrowserRevealDemo", sdk_root)
        root = project.get_startup_page().root_widget
        label = WidgetModel("label", name="title", x=4, y=4, width=60, height=20)
        button = WidgetModel("button", name="cta", x=10, y=30, width=80, height=24)
        root.add_child(label)
        root.add_child(button)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)

        window._reveal_widget_type_in_structure("button")

        assert window._current_left_panel == "structure"
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
        project = _create_project(project_dir, "WidgetBrowserSelectionDemo", sdk_root)
        root = project.get_startup_page().root_widget
        label = WidgetModel("label", name="title", x=4, y=4, width=60, height=20)
        root.add_child(label)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)

        window._set_selection([label], primary=label, sync_tree=True, sync_preview=True)

        assert window.widget_browser._selected_type == "label"
        _close_window(window)

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

    def test_status_center_inspector_actions_switch_inspector_tabs(self, qapp, isolated_config):
        from ui_designer.ui.main_window import MainWindow

        window = MainWindow("")

        window._on_status_center_action_requested("open_animations_inspector")
        assert window._inspector_tabs.currentIndex() == 1
        window._on_status_center_action_requested("open_properties_inspector")
        assert window._inspector_tabs.currentIndex() == 0
        window._on_status_center_action_requested("open_page_timers")
        assert window._inspector_tabs.currentIndex() == 2
        assert window._page_tools_tabs.currentIndex() == 1
        window._on_status_center_action_requested("open_page_fields")
        assert window._inspector_tabs.currentIndex() == 2
        assert window._page_tools_tabs.currentIndex() == 0
        _close_window(window)

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
        project = _create_project(project_dir, "SelectAllDemo", sdk_root)
        root = project.get_startup_page().root_widget
        first = WidgetModel("label", name="first", x=8, y=8, width=60, height=20)
        second = WidgetModel("button", name="second", x=16, y=40, width=80, height=24)
        hidden = WidgetModel("switch", name="hidden", x=24, y=72, width=60, height=20)
        hidden.designer_hidden = True
        root.add_child(first)
        root.add_child(second)
        root.add_child(hidden)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)

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
        project = _create_project(project_dir, "SelectAllFilterDemo", sdk_root)
        first = WidgetModel("label", name="first", x=8, y=8, width=60, height=20)
        project.get_startup_page().root_widget.add_child(first)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "PreviewContextMenuDemo", sdk_root)
        first = WidgetModel("label", name="first", x=8, y=8, width=60, height=20)
        project.get_startup_page().root_widget.add_child(first)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "PreviewSelectMenuOrderDemo", sdk_root)
        first = WidgetModel("label", name="first", x=8, y=8, width=60, height=20)
        project.get_startup_page().root_widget.add_child(first)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)

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
        project = _create_project(project_dir, "PreviewContextMenuShortcutDemo", sdk_root)
        root = project.get_startup_page().root_widget
        first = WidgetModel("label", name="first", x=8, y=8, width=60, height=20)
        second = WidgetModel("button", name="second", x=72, y=8, width=60, height=20)
        target = WidgetModel("group", name="target", x=10, y=40, width=120, height=80)
        root.add_child(first)
        root.add_child(second)
        root.add_child(target)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        assert structure_actions["Move Into Last Target"].shortcut().toString() == "Ctrl+Alt+I"
        assert structure_actions["Lift To Parent"].shortcut().toString() == "Ctrl+Shift+L"
        assert structure_actions["Move Up"].shortcut().toString() == "Alt+Up"
        assert structure_actions["Move Down"].shortcut().toString() == "Alt+Down"
        assert structure_actions["Move To Top"].shortcut().toString() == "Alt+Shift+Up"
        assert structure_actions["Move To Bottom"].shortcut().toString() == "Alt+Shift+Down"

        menu.deleteLater()
        _close_window(window)

    def test_build_preview_context_menu_structure_actions_appear_in_expected_order(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewStructureMenuOrderDemo"
        project = _create_project(project_dir, "PreviewStructureMenuOrderDemo", sdk_root)
        first = WidgetModel("label", name="first", x=8, y=8, width=60, height=20)
        second = WidgetModel("button", name="second", x=72, y=8, width=60, height=20)
        target = WidgetModel("group", name="target", x=10, y=40, width=120, height=80)
        project.get_startup_page().root_widget.add_child(first)
        project.get_startup_page().root_widget.add_child(second)
        project.get_startup_page().root_widget.add_child(target)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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

    def test_build_preview_context_menu_structure_actions_reflect_selection_state(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewStructureMenuStateDemo"
        project = _create_project(project_dir, "PreviewStructureMenuStateDemo", sdk_root)
        root = project.get_startup_page().root_widget
        first = WidgetModel("label", name="first", x=8, y=8, width=60, height=20)
        second = WidgetModel("button", name="second", x=72, y=8, width=60, height=20)
        target = WidgetModel("group", name="target_group", x=10, y=40, width=120, height=80)
        nested = WidgetModel("switch", name="nested", x=4, y=4, width=32, height=16)
        target.add_child(nested)
        root.add_child(first)
        root.add_child(second)
        root.add_child(target)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)

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

    def test_build_preview_context_menu_structure_actions_disable_root_and_noop_move_into(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewStructureActionDisabledDemo"
        project = _create_project(project_dir, "PreviewStructureActionDisabledDemo", sdk_root)
        root = project.get_startup_page().root_widget
        child = WidgetModel("label", name="child", x=8, y=8, width=60, height=20)
        root.add_child(child)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)

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
        project = _create_project(project_dir, "PreviewArrangeMenuOrderDemo", sdk_root)
        first = WidgetModel("label", name="first", x=8, y=8, width=60, height=20)
        second = WidgetModel("button", name="second", x=72, y=8, width=60, height=20)
        project.get_startup_page().root_widget.add_child(first)
        project.get_startup_page().root_widget.add_child(second)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "PreviewArrangeMenuStateDemo", sdk_root)
        root = project.get_startup_page().root_widget
        first = WidgetModel("label", name="first", x=8, y=8, width=60, height=20)
        second = WidgetModel("button", name="second", x=72, y=8, width=60, height=20)
        third = WidgetModel("switch", name="third", x=136, y=8, width=60, height=20)
        root.add_child(first)
        root.add_child(second)
        root.add_child(third)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)

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
        project = _create_project(project_dir, "PreviewEditMenuStateDemo", sdk_root)
        root = project.get_startup_page().root_widget
        first = WidgetModel("label", name="first", x=8, y=8, width=60, height=20)
        locked = WidgetModel("button", name="locked", x=72, y=8, width=60, height=20)
        locked.designer_locked = True
        root.add_child(first)
        root.add_child(locked)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)

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
        project = _create_project(project_dir, "PreviewSelectMenuRelationshipsDemo", sdk_root)
        root = project.get_startup_page().root_widget
        first = WidgetModel("label", name="first", x=8, y=8, width=40, height=16)
        container = WidgetModel("group", name="container", x=10, y=24, width=120, height=80)
        child_a = WidgetModel("switch", name="child_a", x=4, y=4, width=32, height=16)
        child_b = WidgetModel("button", name="child_b", x=4, y=28, width=48, height=20)
        solo = WidgetModel("label", name="solo", x=140, y=24, width=40, height=16)
        container.add_child(child_a)
        container.add_child(child_b)
        root.add_child(first)
        root.add_child(container)
        root.add_child(solo)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)

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
        project = _create_project(project_dir, "PreviewNoWidgetContextMenuDemo", sdk_root)
        project.get_startup_page().root_widget.add_child(WidgetModel("label", name="first"))
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "PreviewNoWidgetContextMenuStateDemo", sdk_root)
        project.get_startup_page().root_widget.add_child(WidgetModel("label", name="first"))
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)

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

        assert arrange_actions["Align Left"].isEnabled() is False
        assert arrange_actions["Distribute Horizontally"].isEnabled() is False
        assert arrange_actions["Bring to Front"].isEnabled() is False
        assert arrange_actions["Toggle Lock"].isEnabled() is False

        assert structure_actions["Group Selection"].isEnabled() is False
        assert structure_actions["Ungroup"].isEnabled() is False
        assert structure_actions["Move Into..."].isEnabled() is False
        assert structure_actions["Move Into Last Target"].isEnabled() is False
        assert structure_actions["Clear Move Target History"].isEnabled() is False
        assert structure_actions["Lift To Parent"].isEnabled() is False
        assert structure_actions["Move Up"].isEnabled() is False
        assert structure_actions["Move Down"].isEnabled() is False
        assert structure_actions["Move To Top"].isEnabled() is False
        assert structure_actions["Move To Bottom"].isEnabled() is False
        quick_move_menu = next(action.menu() for action in structure_menu.actions() if action.text() == "Quick Move Into")
        quick_move_texts = [action.text() for action in quick_move_menu.actions() if action.text()]
        quick_move_action = next(action for action in structure_menu.actions() if action.text() == "Quick Move Into")
        assert quick_move_action.isEnabled() is window._quick_move_into_menu.menuAction().isEnabled()
        assert quick_move_action.toolTip() == window._quick_move_into_menu.menuAction().toolTip()
        assert "(No eligible target containers)" in quick_move_texts
        assert "History" in quick_move_texts
        menu.deleteLater()

        window._clipboard_payload = {"widgets": []}
        window._update_edit_actions()
        menu = window._build_preview_context_menu(None)
        actions = {action.text(): action for action in menu.actions() if action.text()}
        assert actions["Paste"].isEnabled() is True
        menu.deleteLater()

        _close_window(window)

    def test_build_preview_context_menu_quick_move_into_shows_recent_placeholder_without_history(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewQuickMovePlaceholderDemo"
        project = _create_project(project_dir, "PreviewQuickMovePlaceholderDemo", sdk_root)
        root = project.get_startup_page().root_widget
        target = WidgetModel("group", name="target")
        child = WidgetModel("label", name="child")
        root.add_child(target)
        root.add_child(child)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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

    def test_build_preview_context_menu_quick_move_into_shows_history_without_targets(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewQuickMoveHistoryOnlyContextMenuDemo"
        project = _create_project(project_dir, "PreviewQuickMoveHistoryOnlyContextMenuDemo", sdk_root)
        root = project.get_startup_page().root_widget
        target = WidgetModel("group", name="target")
        child = WidgetModel("label", name="child")
        root.add_child(target)
        root.add_child(child)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)

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

    def test_build_preview_context_menu_quick_move_into_follows_recent_target_history(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewQuickMoveHistoryOrderingDemo"
        project = _create_project(project_dir, "PreviewQuickMoveHistoryOrderingDemo", sdk_root)
        root = project.get_startup_page().root_widget
        target_a = WidgetModel("group", name="target_a")
        target_b = WidgetModel("group", name="target_b")
        target_c = WidgetModel("group", name="target_c")
        first = WidgetModel("label", name="first")
        second = WidgetModel("button", name="second")
        third = WidgetModel("switch", name="third")
        root.add_child(target_a)
        root.add_child(target_b)
        root.add_child(target_c)
        root.add_child(first)
        root.add_child(second)
        root.add_child(third)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)

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

    def test_build_preview_context_menu_quick_move_labels_follow_target_rename(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewQuickMoveRenameDemo"
        project = _create_project(project_dir, "PreviewQuickMoveRenameDemo", sdk_root)
        root = project.get_startup_page().root_widget
        target = WidgetModel("group", name="target")
        first = WidgetModel("label", name="first")
        second = WidgetModel("button", name="second")
        root.add_child(target)
        root.add_child(first)
        root.add_child(second)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)

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

    def test_preview_context_menu_move_into_last_target_is_scoped_per_page(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewPerPageMoveIntoDemo"
        project = _create_project(project_dir, "PreviewPerPageMoveIntoDemo", sdk_root)

        main_page = project.get_page_by_name("main_page")
        main_root = main_page.root_widget
        main_target = WidgetModel("group", name="main_target")
        main_first = WidgetModel("label", name="main_first")
        main_second = WidgetModel("button", name="main_second")
        main_root.add_child(main_target)
        main_root.add_child(main_first)
        main_root.add_child(main_second)

        detail_page = project.create_new_page("detail_page")
        detail_root = detail_page.root_widget
        detail_target = WidgetModel("group", name="detail_target")
        detail_first = WidgetModel("label", name="detail_first")
        detail_second = WidgetModel("button", name="detail_second")
        detail_root.add_child(detail_target)
        detail_root.add_child(detail_first)
        detail_root.add_child(detail_second)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)

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

    def test_preview_context_menu_quick_move_actions_update_selection_and_history(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewQuickMoveActionsDemo"
        project = _create_project(project_dir, "PreviewQuickMoveActionsDemo", sdk_root)
        root = project.get_startup_page().root_widget
        target = WidgetModel("group", name="target")
        first = WidgetModel("label", name="first")
        second = WidgetModel("button", name="second")
        third = WidgetModel("switch", name="third")
        root.add_child(target)
        root.add_child(first)
        root.add_child(second)
        root.add_child(third)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)

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

    def test_preview_context_menu_quick_move_submenu_history_actions_update_selection_and_history(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewQuickMoveHistorySubmenuDemo"
        project = _create_project(project_dir, "PreviewQuickMoveHistorySubmenuDemo", sdk_root)
        root = project.get_startup_page().root_widget
        target = WidgetModel("group", name="target")
        first = WidgetModel("label", name="first")
        second = WidgetModel("button", name="second")
        root.add_child(target)
        root.add_child(first)
        root.add_child(second)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)

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

    def test_preview_context_menu_clear_move_target_history_reports_plural_count(
        self, qapp, isolated_config, tmp_path, monkeypatch
    ):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.main_window import MainWindow

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_dir = tmp_path / "PreviewClearMoveHistoryCountDemo"
        project = _create_project(project_dir, "PreviewClearMoveHistoryCountDemo", sdk_root)
        root = project.get_startup_page().root_widget
        target_a = WidgetModel("group", name="target_a")
        target_b = WidgetModel("group", name="target_b")
        first = WidgetModel("label", name="first")
        second = WidgetModel("button", name="second")
        third = WidgetModel("switch", name="third")
        root.add_child(target_a)
        root.add_child(target_b)
        root.add_child(first)
        root.add_child(second)
        root.add_child(third)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)

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
        project = _create_project(project_dir, "PreviewSelectContextMenuDemo", sdk_root)
        root = project.get_startup_page().root_widget
        other = WidgetModel("label", name="other", x=8, y=8, width=40, height=16)
        container = WidgetModel("group", name="container", x=10, y=24, width=120, height=80)
        child_a = WidgetModel("switch", name="child_a", x=4, y=4, width=32, height=16)
        child_b = WidgetModel("button", name="child_b", x=4, y=28, width=48, height=20)
        container.add_child(child_a)
        container.add_child(child_b)
        root.add_child(other)
        root.add_child(container)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "PreviewParentAndSiblingsContextMenuDemo", sdk_root)
        root = project.get_startup_page().root_widget
        other = WidgetModel("label", name="other", x=8, y=8, width=40, height=16)
        container = WidgetModel("group", name="container", x=10, y=24, width=120, height=80)
        child_a = WidgetModel("switch", name="child_a", x=4, y=4, width=32, height=16)
        child_b = WidgetModel("button", name="child_b", x=4, y=28, width=48, height=20)
        child_c = WidgetModel("label", name="child_c", x=4, y=52, width=48, height=16)
        container.add_child(child_a)
        container.add_child(child_b)
        container.add_child(child_c)
        root.add_child(other)
        root.add_child(container)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "PreviewSiblingTraversalContextMenuDemo", sdk_root)
        root = project.get_startup_page().root_widget
        container = WidgetModel("group", name="container", x=10, y=24, width=120, height=80)
        child_a = WidgetModel("switch", name="child_a", x=4, y=4, width=32, height=16)
        child_b = WidgetModel("button", name="child_b", x=4, y=28, width=48, height=20)
        child_c = WidgetModel("label", name="child_c", x=4, y=52, width=48, height=16)
        container.add_child(child_a)
        container.add_child(child_b)
        container.add_child(child_c)
        root.add_child(container)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "PreviewSiblingRangeContextMenuDemo", sdk_root)
        root = project.get_startup_page().root_widget
        container = WidgetModel("group", name="container", x=10, y=24, width=120, height=80)
        child_a = WidgetModel("switch", name="child_a", x=4, y=4, width=32, height=16)
        child_b = WidgetModel("button", name="child_b", x=4, y=28, width=48, height=20)
        child_c = WidgetModel("label", name="child_c", x=4, y=52, width=48, height=16)
        container.add_child(child_a)
        container.add_child(child_b)
        container.add_child(child_c)
        root.add_child(container)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "PreviewChildTraversalContextMenuDemo", sdk_root)
        root = project.get_startup_page().root_widget
        container = WidgetModel("group", name="container", x=10, y=24, width=120, height=80)
        child_a = WidgetModel("switch", name="child_a", x=4, y=4, width=32, height=16)
        child_b = WidgetModel("button", name="child_b", x=4, y=28, width=48, height=20)
        child_c = WidgetModel("label", name="child_c", x=4, y=52, width=48, height=16)
        container.add_child(child_a)
        container.add_child(child_b)
        container.add_child(child_c)
        root.add_child(container)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "PreviewTreeTraversalContextMenuDemo", sdk_root)
        root = project.get_startup_page().root_widget
        other = WidgetModel("label", name="other", x=8, y=8, width=40, height=16)
        container = WidgetModel("group", name="container", x=10, y=24, width=120, height=80)
        child_a = WidgetModel("switch", name="child_a", x=4, y=4, width=32, height=16)
        child_b = WidgetModel("button", name="child_b", x=4, y=28, width=48, height=20)
        container.add_child(child_a)
        container.add_child(child_b)
        root.add_child(other)
        root.add_child(container)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "PreviewDescendantsContextMenuDemo", sdk_root)
        root = project.get_startup_page().root_widget
        other = WidgetModel("label", name="other", x=8, y=8, width=40, height=16)
        container = WidgetModel("group", name="container", x=10, y=24, width=120, height=80)
        child_a = WidgetModel("switch", name="child_a", x=4, y=4, width=32, height=16)
        nested_group = WidgetModel("group", name="nested_group", x=4, y=28, width=60, height=40)
        nested_leaf = WidgetModel("label", name="nested_leaf", x=2, y=2, width=32, height=16)
        nested_group.add_child(nested_leaf)
        container.add_child(child_a)
        container.add_child(nested_group)
        root.add_child(other)
        root.add_child(container)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "PreviewAncestorsContextMenuDemo", sdk_root)
        root = project.get_startup_page().root_widget
        other = WidgetModel("label", name="other", x=8, y=8, width=40, height=16)
        container = WidgetModel("group", name="container", x=10, y=24, width=120, height=80)
        nested_group = WidgetModel("group", name="nested_group", x=4, y=28, width=60, height=40)
        nested_leaf = WidgetModel("label", name="nested_leaf", x=2, y=2, width=32, height=16)
        nested_group.add_child(nested_leaf)
        container.add_child(nested_group)
        root.add_child(other)
        root.add_child(container)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "PreviewRootContextMenuDemo", sdk_root)
        root = project.get_startup_page().root_widget
        other = WidgetModel("label", name="other", x=8, y=8, width=40, height=16)
        container = WidgetModel("group", name="container", x=10, y=24, width=120, height=80)
        nested_group = WidgetModel("group", name="nested_group", x=4, y=28, width=60, height=40)
        nested_leaf = WidgetModel("label", name="nested_leaf", x=2, y=2, width=32, height=16)
        nested_group.add_child(nested_leaf)
        container.add_child(nested_group)
        root.add_child(other)
        root.add_child(container)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "PreviewPathContextMenuDemo", sdk_root)
        root = project.get_startup_page().root_widget
        other = WidgetModel("label", name="other", x=8, y=8, width=40, height=16)
        container = WidgetModel("group", name="container", x=10, y=24, width=120, height=80)
        nested_group = WidgetModel("group", name="nested_group", x=4, y=28, width=60, height=40)
        nested_leaf = WidgetModel("label", name="nested_leaf", x=2, y=2, width=32, height=16)
        nested_group.add_child(nested_leaf)
        container.add_child(nested_group)
        root.add_child(other)
        root.add_child(container)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "PreviewTopLevelContextMenuDemo", sdk_root)
        root = project.get_startup_page().root_widget
        other = WidgetModel("label", name="other", x=8, y=8, width=40, height=16)
        container = WidgetModel("group", name="container", x=10, y=24, width=120, height=80)
        nested_group = WidgetModel("group", name="nested_group", x=4, y=28, width=60, height=40)
        nested_leaf = WidgetModel("label", name="nested_leaf", x=2, y=2, width=32, height=16)
        same_type = WidgetModel("button", name="same_type", x=8, y=120, width=48, height=20)
        nested_group.add_child(nested_leaf)
        container.add_child(nested_group)
        root.add_child(other)
        root.add_child(container)
        root.add_child(same_type)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "PreviewSubtreeContextMenuDemo", sdk_root)
        root = project.get_startup_page().root_widget
        other = WidgetModel("label", name="other", x=8, y=8, width=40, height=16)
        container = WidgetModel("group", name="container", x=10, y=24, width=120, height=80)
        child_a = WidgetModel("switch", name="child_a", x=4, y=4, width=32, height=16)
        nested_group = WidgetModel("group", name="nested_group", x=4, y=28, width=60, height=40)
        nested_leaf = WidgetModel("label", name="nested_leaf", x=2, y=2, width=32, height=16)
        nested_group.add_child(nested_leaf)
        container.add_child(child_a)
        container.add_child(nested_group)
        root.add_child(other)
        root.add_child(container)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "PreviewLeavesContextMenuDemo", sdk_root)
        root = project.get_startup_page().root_widget
        other = WidgetModel("label", name="other", x=8, y=8, width=40, height=16)
        container = WidgetModel("group", name="container", x=10, y=24, width=120, height=80)
        child_a = WidgetModel("switch", name="child_a", x=4, y=4, width=32, height=16)
        child_b = WidgetModel("button", name="child_b", x=4, y=28, width=48, height=20)
        nested_group = WidgetModel("group", name="nested_group", x=4, y=52, width=60, height=40)
        nested_leaf = WidgetModel("label", name="nested_leaf", x=2, y=2, width=32, height=16)
        nested_group.add_child(nested_leaf)
        container.add_child(child_a)
        container.add_child(child_b)
        container.add_child(nested_group)
        root.add_child(other)
        root.add_child(container)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "PreviewContainersContextMenuDemo", sdk_root)
        root = project.get_startup_page().root_widget
        other = WidgetModel("label", name="other", x=8, y=8, width=40, height=16)
        container = WidgetModel("group", name="container", x=10, y=24, width=120, height=80)
        child_a = WidgetModel("switch", name="child_a", x=4, y=4, width=32, height=16)
        nested_group = WidgetModel("group", name="nested_group", x=4, y=28, width=60, height=40)
        nested_leaf = WidgetModel("label", name="nested_leaf", x=2, y=2, width=32, height=16)
        nested_group.add_child(nested_leaf)
        container.add_child(child_a)
        container.add_child(nested_group)
        root.add_child(other)
        root.add_child(container)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "PreviewStateContextMenuDemo", sdk_root)
        root = project.get_startup_page().root_widget
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
        locked_group.add_child(locked_leaf)
        container.add_child(hidden_self)
        container.add_child(hidden_leaf)
        container.add_child(locked_group)
        root.add_child(other)
        root.add_child(container)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "PreviewLayoutContainersContextMenuDemo", sdk_root)
        root = project.get_startup_page().root_widget
        other = WidgetModel("label", name="other", x=8, y=8, width=40, height=16)
        container = WidgetModel("group", name="container", x=10, y=24, width=140, height=100)
        layout_parent = WidgetModel("linearlayout", name="layout_parent", x=4, y=4, width=100, height=60)
        managed_group = WidgetModel("group", name="managed_group", x=2, y=2, width=48, height=24)
        managed_leaf = WidgetModel("label", name="managed_leaf", x=1, y=1, width=24, height=12)
        unmanaged_leaf = WidgetModel("label", name="unmanaged_leaf", x=4, y=72, width=40, height=16)
        managed_group.add_child(managed_leaf)
        layout_parent.add_child(managed_group)
        container.add_child(layout_parent)
        container.add_child(unmanaged_leaf)
        root.add_child(other)
        root.add_child(container)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "PreviewManagedContextMenuDemo", sdk_root)
        root = project.get_startup_page().root_widget
        other = WidgetModel("label", name="other", x=8, y=8, width=40, height=16)
        container = WidgetModel("group", name="container", x=10, y=24, width=140, height=100)
        layout_parent = WidgetModel("linearlayout", name="layout_parent", x=4, y=4, width=100, height=60)
        managed_group = WidgetModel("group", name="managed_group", x=2, y=2, width=48, height=24)
        managed_leaf = WidgetModel("label", name="managed_leaf", x=1, y=1, width=24, height=12)
        managed_button = WidgetModel("button", name="managed_button", x=2, y=30, width=48, height=20)
        unmanaged_leaf = WidgetModel("label", name="unmanaged_leaf", x=4, y=72, width=40, height=16)
        managed_group.add_child(managed_leaf)
        layout_parent.add_child(managed_group)
        layout_parent.add_child(managed_button)
        container.add_child(layout_parent)
        container.add_child(unmanaged_leaf)
        root.add_child(other)
        root.add_child(container)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "PreviewFreePositionContextMenuDemo", sdk_root)
        root = project.get_startup_page().root_widget
        other = WidgetModel("label", name="other", x=8, y=8, width=40, height=16)
        container = WidgetModel("group", name="container", x=10, y=24, width=140, height=100)
        layout_parent = WidgetModel("linearlayout", name="layout_parent", x=4, y=4, width=100, height=60)
        managed_group = WidgetModel("group", name="managed_group", x=2, y=2, width=48, height=24)
        managed_leaf = WidgetModel("label", name="managed_leaf", x=1, y=1, width=24, height=12)
        managed_button = WidgetModel("button", name="managed_button", x=2, y=30, width=48, height=20)
        unmanaged_leaf = WidgetModel("label", name="unmanaged_leaf", x=4, y=72, width=40, height=16)
        managed_group.add_child(managed_leaf)
        layout_parent.add_child(managed_group)
        layout_parent.add_child(managed_button)
        container.add_child(layout_parent)
        container.add_child(unmanaged_leaf)
        root.add_child(other)
        root.add_child(container)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "PreviewSameTypeContextMenuDemo", sdk_root)
        root = project.get_startup_page().root_widget
        other = WidgetModel("label", name="other", x=8, y=8, width=40, height=16)
        first = WidgetModel("button", name="first", x=8, y=28, width=56, height=20)
        second = WidgetModel("button", name="second", x=8, y=56, width=56, height=20)
        root.add_child(other)
        root.add_child(first)
        root.add_child(second)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "PreviewSameParentTypeContextMenuDemo", sdk_root)
        root = project.get_startup_page().root_widget
        first = WidgetModel("label", name="first", x=8, y=8, width=40, height=16)
        second = WidgetModel("label", name="second", x=8, y=28, width=40, height=16)
        other = WidgetModel("button", name="other", x=8, y=56, width=56, height=20)
        root.add_child(first)
        root.add_child(second)
        root.add_child(other)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "PreviewSubtreeTypeContextMenuDemo", sdk_root)
        root = project.get_startup_page().root_widget
        other = WidgetModel("label", name="other", x=8, y=8, width=40, height=16)
        container = WidgetModel("group", name="container", x=10, y=24, width=120, height=80)
        nested_group = WidgetModel("group", name="nested_group", x=4, y=28, width=60, height=40)
        nested_leaf = WidgetModel("label", name="nested_leaf", x=2, y=2, width=32, height=16)
        nested_group.add_child(nested_leaf)
        container.add_child(nested_group)
        root.add_child(other)
        root.add_child(container)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
        project = _create_project(project_dir, "PreviewSameDepthContextMenuDemo", sdk_root)
        root = project.get_startup_page().root_widget
        branch_a = WidgetModel("group", name="branch_a", x=8, y=8, width=80, height=80)
        branch_b = WidgetModel("group", name="branch_b", x=100, y=8, width=80, height=80)
        leaf_a = WidgetModel("label", name="leaf_a", x=4, y=4, width=40, height=16)
        leaf_b = WidgetModel("button", name="leaf_b", x=4, y=4, width=48, height=20)
        nested_group = WidgetModel("group", name="nested_group", x=4, y=28, width=50, height=30)
        branch_a.add_child(leaf_a)
        branch_a.add_child(nested_group)
        branch_b.add_child(leaf_b)
        root.add_child(branch_a)
        root.add_child(branch_b)
        project.save(str(project_dir))

        window = MainWindow(str(sdk_root))
        monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
        monkeypatch.setattr(window, "_trigger_compile", lambda: None)
        monkeypatch.setattr(window.property_panel, "set_selection", lambda *args, **kwargs: None)
        monkeypatch.setattr(window.animations_panel, "set_selection", lambda *args, **kwargs: None)
        window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)
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
