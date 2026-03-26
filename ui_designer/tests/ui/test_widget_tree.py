"""Qt UI tests for WidgetTreePanel name handling."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtCore import QEvent, Qt
    from PyQt5.QtGui import QKeyEvent
    from PyQt5.QtWidgets import QApplication, QAbstractItemView, QToolButton

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
    app.processEvents()


def _build_project_with_root():
    from ui_designer.model.project import Project

    project = Project(screen_width=240, screen_height=320, app_name="WidgetTreeDemo")
    project.create_new_page("main_page")
    return project, project.get_startup_page().root_widget


def _structure_menu_actions(menu):
    structure_menu = None
    for action in menu.actions():
        if action.text() == "Structure":
            structure_menu = action.menu()
            break
    assert structure_menu is not None
    return {action.text(): action for action in structure_menu.actions() if action.text()}


def _structure_submenu(menu, label):
    for action in menu.actions():
        if action.text() == "Structure":
            structure_menu = action.menu()
            break
    else:
        raise AssertionError("Structure menu not found")

    for action in structure_menu.actions():
        if action.text() == label:
            return action.menu()
    raise AssertionError(f"{label} submenu not found")


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


@_skip_no_qt
class TestWidgetTreePanel:
    def test_rename_widget_resolves_duplicate_name(self, qapp, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
        first = WidgetModel("label", name="title")
        second = WidgetModel("label", name="subtitle")
        root.add_child(first)
        root.add_child(second)

        panel = WidgetTreePanel()
        panel.set_project(project)

        monkeypatch.setattr(
            "ui_designer.ui.widget_tree.QInputDialog.getText",
            lambda *args, **kwargs: ("title", True),
        )

        panel._rename_widget(second)

        assert first.name == "title"
        assert second.name == "title_2"
        panel.deleteLater()

    def test_add_child_resolves_duplicate_auto_name(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
        root.add_child(WidgetModel("button", name="button_1"))
        WidgetModel.reset_counter()

        panel = WidgetTreePanel()
        panel.set_project(project)
        panel._add_child_to(root, "button")

        names = [child.name for child in root.children if child.widget_type == "button"]
        assert names == ["button_1", "button_2"]
        panel.deleteLater()

    def test_rename_widget_rejects_invalid_identifier(self, qapp, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
        widget = WidgetModel("label", name="title")
        root.add_child(widget)

        panel = WidgetTreePanel()
        panel.set_project(project)
        warnings = []

        monkeypatch.setattr(
            "ui_designer.ui.widget_tree.QInputDialog.getText",
            lambda *args, **kwargs: ("123 bad-name", True),
        )
        monkeypatch.setattr("ui_designer.ui.widget_tree.QMessageBox.warning", lambda *args: warnings.append(args[1:]))

        panel._rename_widget(widget)

        assert widget.name == "title"
        assert warnings
        assert warnings[0][0] == "Invalid Widget Name"
        panel.deleteLater()

    def test_rename_widget_emits_feedback_when_duplicate_name_is_resolved(self, qapp, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
        first = WidgetModel("label", name="title")
        second = WidgetModel("label", name="subtitle")
        root.add_child(first)
        root.add_child(second)

        panel = WidgetTreePanel()
        panel.set_project(project)
        feedback = []
        panel.feedback_message.connect(lambda message: feedback.append(message))

        monkeypatch.setattr(
            "ui_designer.ui.widget_tree.QInputDialog.getText",
            lambda *args, **kwargs: ("title", True),
        )

        panel._rename_widget(second)

        assert second.name == "title_2"
        assert feedback == ["Widget name 'title' already exists. Renamed to 'title_2'."]
        panel.deleteLater()

    def test_rename_selected_widgets_applies_prefix_and_emits_feedback(self, qapp, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
        existing = WidgetModel("label", name="field_1")
        first = WidgetModel("label", name="title")
        second = WidgetModel("button", name="cta")
        root.add_child(existing)
        root.add_child(first)
        root.add_child(second)

        panel = WidgetTreePanel()
        panel.set_project(project)
        feedback = []
        panel.feedback_message.connect(lambda message: feedback.append(message))
        panel.set_selected_widgets([first, second], primary=first)

        monkeypatch.setattr(
            "ui_designer.ui.widget_tree.QInputDialog.getText",
            lambda *args, **kwargs: ("field", True),
        )

        panel._rename_selected_widgets()

        assert first.name == "field_2"
        assert second.name == "field_3"
        assert panel.selected_widgets() == [first, second]
        assert panel._get_selected_widget() is first
        assert feedback == ["Renamed 2 widget(s) with prefix 'field'."]
        panel.deleteLater()

    def test_rename_selected_widgets_rejects_invalid_prefix(self, qapp, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
        first = WidgetModel("label", name="title")
        second = WidgetModel("button", name="cta")
        root.add_child(first)
        root.add_child(second)

        panel = WidgetTreePanel()
        panel.set_project(project)
        warnings = []
        panel.set_selected_widgets([first, second], primary=first)

        monkeypatch.setattr(
            "ui_designer.ui.widget_tree.QInputDialog.getText",
            lambda *args, **kwargs: ("123 bad", True),
        )
        monkeypatch.setattr("ui_designer.ui.widget_tree.QMessageBox.warning", lambda *args: warnings.append(args[1:]))

        panel._rename_selected_widgets()

        assert first.name == "title"
        assert second.name == "cta"
        assert warnings
        assert warnings[0][0] == "Invalid Widget Prefix"
        panel.deleteLater()

    def test_delete_selected_parent_and_child_removes_only_top_level_once(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
        container = WidgetModel("group", name="container")
        child = WidgetModel("label", name="title")
        container.add_child(child)
        root.add_child(container)

        panel = WidgetTreePanel()
        panel.set_project(project)
        panel.set_selected_widgets([container, child], primary=container)

        panel._on_delete_clicked()

        assert root.children == []
        panel.deleteLater()

    def test_delete_selected_skips_locked_widgets_and_emits_feedback(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
        removable = WidgetModel("label", name="removable")
        locked = WidgetModel("label", name="locked_widget")
        locked.designer_locked = True
        root.add_child(removable)
        root.add_child(locked)

        panel = WidgetTreePanel()
        panel.set_project(project)
        feedback = []
        panel.feedback_message.connect(lambda message: feedback.append(message))
        panel.set_selected_widgets([removable, locked], primary=removable)

        panel._on_delete_clicked()

        assert removable not in root.children
        assert locked in root.children
        assert feedback == ["Deleted 1 widget(s); skipped 1 locked widget"]
        panel.deleteLater()

    def test_delete_widget_blocks_locked_widget_and_emits_feedback(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
        locked = WidgetModel("label", name="locked_widget")
        locked.designer_locked = True
        root.add_child(locked)

        panel = WidgetTreePanel()
        panel.set_project(project)
        feedback = []
        panel.feedback_message.connect(lambda message: feedback.append(message))

        panel._delete_widget(locked)

        assert locked in root.children
        assert feedback == ["Cannot delete widget: locked_widget is locked."]
        panel.deleteLater()

    def test_delete_selection_clears_removed_recent_move_targets(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
        target = WidgetModel("group", name="target")
        removable = WidgetModel("label", name="removable")
        sibling = WidgetModel("button", name="sibling")
        root.add_child(target)
        root.add_child(removable)
        root.add_child(sibling)

        panel = WidgetTreePanel()
        panel.set_project(project)
        feedback = []
        panel.feedback_message.connect(lambda message: feedback.append(message))
        panel.remember_move_target(target, "root_group / target (group)")
        panel.set_selected_widgets([target], primary=target)

        panel._on_delete_clicked()

        assert target not in root.children
        assert panel.recent_move_target_labels() == []
        assert feedback == ["Deleted 1 widget(s); cleared 1 recent move target"]
        panel.deleteLater()

    def test_group_selected_widgets_emits_tree_change_and_selects_group(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
        first = WidgetModel("label", name="first", x=10, y=20, width=30, height=10)
        second = WidgetModel("button", name="second", x=60, y=40, width=20, height=20)
        root.add_child(first)
        root.add_child(second)

        panel = WidgetTreePanel()
        panel.set_project(project)
        sources = []
        feedback = []
        panel.tree_changed.connect(lambda source: sources.append(source))
        panel.feedback_message.connect(lambda message: feedback.append(message))
        panel.set_selected_widgets([first, second], primary=first)

        panel._group_selected_widgets()

        group = root.children[0]
        assert group.widget_type == "group"
        assert panel.selected_widgets() == [group]
        assert panel._get_selected_widget() is group
        assert sources == ["group selection"]
        assert feedback == ["Grouped 2 widget(s) into group."]
        panel.deleteLater()

    def test_move_selected_widgets_into_uses_dialog_target(self, qapp, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
        target = WidgetModel("group", name="target", x=80, y=10, width=100, height=100)
        child = WidgetModel("label", name="child", x=10, y=15, width=20, height=10)
        root.add_child(target)
        root.add_child(child)

        panel = WidgetTreePanel()
        panel.set_project(project)
        sources = []
        feedback = []
        panel.tree_changed.connect(lambda source: sources.append(source))
        panel.feedback_message.connect(lambda message: feedback.append(message))
        panel.set_selected_widgets([child], primary=child)

        monkeypatch.setattr(
            "ui_designer.ui.widget_tree.QInputDialog.getItem",
            lambda *args, **kwargs: ("root_group / target (group)", True),
        )

        panel._move_selected_widgets_into()

        assert child.parent is target
        assert panel.selected_widgets() == [child]
        assert panel._get_selected_widget() is child
        assert sources == ["move into container"]
        assert feedback == ["Moved 1 widget(s) into target."]
        panel.deleteLater()

    def test_move_selected_widgets_into_dialog_prefers_remembered_target(self, qapp, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
        target_a = WidgetModel("group", name="target_a")
        target_b = WidgetModel("group", name="target_b")
        first = WidgetModel("label", name="first")
        second = WidgetModel("button", name="second")
        root.add_child(target_a)
        root.add_child(target_b)
        root.add_child(first)
        root.add_child(second)

        panel = WidgetTreePanel()
        panel.set_project(project)
        panel.set_selected_widgets([first], primary=first)
        panel._move_selected_widgets_into(
            target_widget=target_b,
            target_label="root_group / target_b (group)",
        )

        panel.set_selected_widgets([second], primary=second)
        captured = {}

        def _fake_get_item(*args, **kwargs):
            captured["prompt"] = args[2]
            captured["labels"] = list(args[3])
            captured["current_index"] = args[4]
            return "root_group / target_b (group)", True

        monkeypatch.setattr("ui_designer.ui.widget_tree.QInputDialog.getItem", _fake_get_item)

        panel._move_selected_widgets_into()

        assert captured["labels"] == [
            "root_group / target_b (group)",
            "root_group / target_a (group)",
        ]
        assert captured["prompt"] == "Target container (recent targets first):"
        assert captured["current_index"] == 0
        assert second.parent is target_b
        panel.deleteLater()

    def test_move_selected_widgets_into_dialog_prioritizes_recent_target_history(self, qapp, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
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

        panel = WidgetTreePanel()
        panel.set_project(project)
        panel.set_selected_widgets([first], primary=first)
        panel._move_selected_widgets_into(
            target_widget=target_c,
            target_label="root_group / target_c (group)",
        )
        panel.set_selected_widgets([second], primary=second)
        panel._move_selected_widgets_into(
            target_widget=target_b,
            target_label="root_group / target_b (group)",
        )

        panel.set_selected_widgets([third], primary=third)
        captured = {}

        def _fake_get_item(*args, **kwargs):
            captured["labels"] = list(args[3])
            captured["current_index"] = args[4]
            return "root_group / target_b (group)", True

        monkeypatch.setattr("ui_designer.ui.widget_tree.QInputDialog.getItem", _fake_get_item)

        panel._move_selected_widgets_into()

        assert captured["labels"] == [
            "root_group / target_b (group)",
            "root_group / target_c (group)",
            "root_group / target_a (group)",
        ]
        assert captured["current_index"] == 0
        panel.deleteLater()

    def test_into_button_quick_menu_moves_selection_into_target(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
        target = WidgetModel("group", name="target", x=80, y=10, width=100, height=100)
        child = WidgetModel("label", name="child", x=10, y=15, width=20, height=10)
        root.add_child(target)
        root.add_child(child)

        panel = WidgetTreePanel()
        panel.set_project(project)
        sources = []
        feedback = []
        panel.tree_changed.connect(lambda source: sources.append(source))
        panel.feedback_message.connect(lambda message: feedback.append(message))
        panel.set_selected_widgets([child], primary=child)

        target_action = next(action for action in panel.into_btn.menu().actions() if action.text() == "root_group / target (group)")
        target_action.trigger()

        assert child.parent is target
        assert panel.selected_widgets() == [child]
        assert panel._get_selected_widget() is child
        assert sources == ["move into container"]
        assert feedback == ["Moved 1 widget(s) into target."]
        panel.deleteLater()

    def test_quick_move_into_menus_prioritize_remembered_target(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
        target_a = WidgetModel("group", name="target_a")
        target_b = WidgetModel("group", name="target_b")
        first = WidgetModel("label", name="first")
        second = WidgetModel("button", name="second")
        root.add_child(target_a)
        root.add_child(target_b)
        root.add_child(first)
        root.add_child(second)

        panel = WidgetTreePanel()
        panel.set_project(project)
        panel.set_selected_widgets([first], primary=first)
        panel._move_selected_widgets_into(
            target_widget=target_b,
            target_label="root_group / target_b (group)",
        )

        panel.set_selected_widgets([second], primary=second)
        panel._refresh_into_button_menu()

        button_labels = _menu_target_labels(panel.into_btn.menu())
        assert button_labels[:2] == [
            "root_group / target_b (group)",
            "root_group / target_a (group)",
        ]
        assert "Recent Targets" in [action.text() for action in panel.into_btn.menu().actions()]
        assert "Other Targets" in [action.text() for action in panel.into_btn.menu().actions()]

        menu = panel._build_context_menu(second)
        quick_menu = _structure_submenu(menu, "Quick Move Into")
        context_labels = _menu_target_labels(quick_menu)
        assert context_labels[:2] == [
            "root_group / target_b (group)",
            "root_group / target_a (group)",
        ]

        menu.deleteLater()
        panel.deleteLater()

    def test_quick_move_into_menus_follow_recent_target_history(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
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

        panel = WidgetTreePanel()
        panel.set_project(project)
        panel.set_selected_widgets([first], primary=first)
        panel._move_selected_widgets_into(
            target_widget=target_c,
            target_label="root_group / target_c (group)",
        )

        panel.set_selected_widgets([second], primary=second)
        panel._move_selected_widgets_into(
            target_widget=target_b,
            target_label="root_group / target_b (group)",
        )

        panel.set_selected_widgets([third], primary=third)
        panel._refresh_into_button_menu()

        button_labels = _menu_target_labels(panel.into_btn.menu())
        assert button_labels[:3] == [
            "root_group / target_b (group)",
            "root_group / target_c (group)",
            "root_group / target_a (group)",
        ]

        menu = panel._build_context_menu(third)
        quick_menu = _structure_submenu(menu, "Quick Move Into")
        context_labels = _menu_target_labels(quick_menu)
        assert context_labels[:3] == [
            "root_group / target_b (group)",
            "root_group / target_c (group)",
            "root_group / target_a (group)",
        ]

        menu.deleteLater()
        panel.deleteLater()

    def test_quick_move_into_menus_show_recent_placeholder_without_history(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
        target = WidgetModel("group", name="target")
        child = WidgetModel("label", name="child")
        root.add_child(target)
        root.add_child(child)

        panel = WidgetTreePanel()
        panel.set_project(project)
        panel.set_selected_widgets([child], primary=child)
        panel._refresh_into_button_menu()

        button_actions = panel.into_btn.menu().actions()
        assert "Recent Targets" in [action.text() for action in button_actions]
        assert "Other Targets" in [action.text() for action in button_actions]
        assert "History" in [action.text() for action in button_actions]
        recent_placeholder = next(action for action in button_actions if action.text() == "(No recent targets yet)")
        repeat_action = next(action for action in button_actions if action.text() == "Move Into Last Target")
        clear_action = next(action for action in button_actions if action.text() == "Clear Move Target History")
        assert recent_placeholder.isEnabled() is False
        assert repeat_action.isEnabled() is False
        assert clear_action.isEnabled() is False
        assert _menu_target_labels(panel.into_btn.menu()) == ["root_group / target (group)"]

        menu = panel._build_context_menu(child)
        quick_menu = _structure_submenu(menu, "Quick Move Into")
        context_actions = quick_menu.actions()
        assert "Recent Targets" in [action.text() for action in context_actions]
        assert "Other Targets" in [action.text() for action in context_actions]
        recent_placeholder = next(action for action in context_actions if action.text() == "(No recent targets yet)")
        assert recent_placeholder.isEnabled() is False
        assert _menu_target_labels(quick_menu) == ["root_group / target (group)"]

        menu.deleteLater()
        panel.deleteLater()

    def test_into_button_menu_reuses_last_target_and_clears_history(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
        target = WidgetModel("group", name="target")
        first = WidgetModel("label", name="first")
        second = WidgetModel("button", name="second")
        root.add_child(target)
        root.add_child(first)
        root.add_child(second)

        panel = WidgetTreePanel()
        panel.set_project(project)
        feedback = []
        panel.feedback_message.connect(lambda message: feedback.append(message))

        panel.set_selected_widgets([first], primary=first)
        panel._move_selected_widgets_into(
            target_widget=target,
            target_label="root_group / target (group)",
        )

        panel.set_selected_widgets([second], primary=second)
        panel._refresh_into_button_menu()

        assert "History" in [action.text() for action in panel.into_btn.menu().actions()]
        repeat_action = next(action for action in panel.into_btn.menu().actions() if action.text() == "Move Into Last Target")
        clear_action = next(action for action in panel.into_btn.menu().actions() if action.text() == "Clear Move Target History")
        assert repeat_action.isEnabled() is True
        assert clear_action.isEnabled() is True
        assert "root_group / target (group)" in repeat_action.toolTip()

        repeat_action.trigger()

        assert second.parent is target
        assert panel.selected_widgets() == [second]

        panel._refresh_into_button_menu()
        clear_action = next(action for action in panel.into_btn.menu().actions() if action.text() == "Clear Move Target History")
        clear_action.trigger()

        assert panel.recent_move_target_labels() == []
        assert feedback[-1] == "Cleared 1 recent move target."
        panel.deleteLater()

    def test_into_button_stays_available_for_history_only(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
        target = WidgetModel("group", name="target")
        child = WidgetModel("label", name="child")
        root.add_child(target)
        root.add_child(child)

        panel = WidgetTreePanel()
        panel.set_project(project)
        panel.set_selected_widgets([child], primary=child)
        panel._move_selected_widgets_into(
            target_widget=target,
            target_label="root_group / target (group)",
        )

        panel.set_selected_widgets([target], primary=target)

        assert panel.into_btn.isEnabled() is True
        assert panel.into_btn.popupMode() == QToolButton.InstantPopup
        assert panel.into_btn.toolTip() == "Open the Into menu to reuse move-target history."

        button_actions = panel.into_btn.menu().actions()
        assert "(No eligible target containers)" in [action.text() for action in button_actions]
        assert "History" in [action.text() for action in button_actions]
        repeat_action = next(action for action in button_actions if action.text() == "Move Into Last Target")
        clear_action = next(action for action in button_actions if action.text() == "Clear Move Target History")
        assert repeat_action.isEnabled() is False
        assert clear_action.isEnabled() is True

        panel.deleteLater()

    def test_structure_hint_mentions_history_without_selection(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
        target = WidgetModel("group", name="target")
        child = WidgetModel("label", name="child")
        root.add_child(target)
        root.add_child(child)

        panel = WidgetTreePanel()
        panel.set_project(project)
        panel.set_selected_widgets([child], primary=child)
        panel._move_selected_widgets_into(
            target_widget=target,
            target_label="root_group / target (group)",
        )

        panel.set_selected_widgets([], primary=None)

        assert panel.structure_hint_label.text() == (
            "Structure: select widgets to group, move, or reorder. Into menu can clear move history."
        )
        panel.deleteLater()

    def test_context_menu_quick_move_into_target_moves_selection(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
        target = WidgetModel("group", name="target", x=80, y=10, width=100, height=100)
        child = WidgetModel("label", name="child", x=10, y=15, width=20, height=10)
        root.add_child(target)
        root.add_child(child)

        panel = WidgetTreePanel()
        panel.set_project(project)
        sources = []
        feedback = []
        panel.tree_changed.connect(lambda source: sources.append(source))
        panel.feedback_message.connect(lambda message: feedback.append(message))
        panel.set_selected_widgets([child], primary=child)

        menu = panel._build_context_menu(child)
        quick_menu = _structure_submenu(menu, "Quick Move Into")
        target_action = next(action for action in quick_menu.actions() if action.text() == "root_group / target (group)")

        target_action.trigger()

        assert child.parent is target
        assert panel.selected_widgets() == [child]
        assert panel._get_selected_widget() is child
        assert sources == ["move into container"]
        assert feedback == ["Moved 1 widget(s) into target."]

        menu.deleteLater()
        panel.deleteLater()

    def test_context_menu_quick_move_into_shows_history_without_targets(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
        target = WidgetModel("group", name="target")
        child = WidgetModel("label", name="child")
        root.add_child(target)
        root.add_child(child)

        panel = WidgetTreePanel()
        panel.set_project(project)
        panel.set_selected_widgets([child], primary=child)
        panel._move_selected_widgets_into(
            target_widget=target,
            target_label="root_group / target (group)",
        )

        panel.set_selected_widgets([target], primary=target)
        menu = panel._build_context_menu(target)
        actions = _structure_menu_actions(menu)
        quick_menu = _structure_submenu(menu, "Quick Move Into")

        assert actions["Quick Move Into"].menu() is not None
        quick_action_texts = [action.text() for action in quick_menu.actions()]
        assert "(No eligible target containers)" in quick_action_texts
        assert "History" in quick_action_texts

        repeat_action = next(action for action in quick_menu.actions() if action.text() == "Move Into Last Target")
        clear_action = next(action for action in quick_menu.actions() if action.text() == "Clear Move Target History")
        assert repeat_action.isEnabled() is False
        assert clear_action.isEnabled() is True
        assert _menu_target_labels(quick_menu) == []

        menu.deleteLater()
        panel.deleteLater()

    def test_context_menu_structure_actions_reflect_selection_state(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
        first = WidgetModel("label", name="first")
        second = WidgetModel("button", name="second")
        target = WidgetModel("group", name="target")
        nested = WidgetModel("switch", name="nested")
        target.add_child(nested)
        root.add_child(first)
        root.add_child(second)
        root.add_child(target)

        panel = WidgetTreePanel()
        panel.set_project(project)
        panel.set_selected_widgets([first, second], primary=first)

        menu = panel._build_context_menu(first)
        actions = _structure_menu_actions(menu)

        assert actions["Group Selection"].isEnabled() is True
        assert actions["Ungroup"].isEnabled() is False
        assert actions["Move Into..."].isEnabled() is True
        assert actions["Move Into Last Target"].isEnabled() is False
        assert actions["Quick Move Into"].menu() is not None
        assert actions["Quick Move Into"].toolTip() == "Move directly into an available container target, or reuse move-target history."
        assert actions["Lift To Parent"].isEnabled() is False
        assert actions["Move Up"].isEnabled() is False
        assert actions["Move Down"].isEnabled() is True
        assert actions["Move To Top"].isEnabled() is False
        assert actions["Move To Bottom"].isEnabled() is True
        assert "Unavailable: selection must only include groups." in actions["Ungroup"].toolTip()
        assert "Unavailable: move something into a container first." in actions["Move Into Last Target"].toolTip()
        assert "Unavailable: selected widgets already belong to the top container." in actions["Lift To Parent"].toolTip()
        assert "Unavailable: selected widgets are already at the top." in actions["Move Up"].toolTip()
        assert "Unavailable: selected widgets are already at the top." in actions["Move To Top"].toolTip()
        assert actions["Group Selection"].shortcut().toString() == "Ctrl+G"
        assert actions["Ungroup"].shortcut().toString() == "Ctrl+Shift+G"
        assert actions["Move Into..."].shortcut().toString() == "Ctrl+Shift+I"
        assert actions["Move Into Last Target"].shortcut().toString() == "Ctrl+Alt+I"
        assert actions["Lift To Parent"].shortcut().toString() == "Ctrl+Shift+L"
        assert actions["Move Up"].shortcut().toString() == "Alt+Up"
        assert actions["Move Down"].shortcut().toString() == "Alt+Down"
        assert actions["Move To Top"].shortcut().toString() == "Alt+Shift+Up"
        assert actions["Move To Bottom"].shortcut().toString() == "Alt+Shift+Down"

        menu.deleteLater()

        panel.set_selected_widgets([nested], primary=nested)
        nested_menu = panel._build_context_menu(nested)
        nested_actions = _structure_menu_actions(nested_menu)

        assert nested_actions["Group Selection"].isEnabled() is False
        assert nested_actions["Ungroup"].isEnabled() is False
        assert nested_actions["Move Into..."].isEnabled() is True
        assert nested_actions["Lift To Parent"].isEnabled() is True
        assert nested_actions["Move Up"].isEnabled() is False
        assert nested_actions["Move Down"].isEnabled() is False
        assert nested_actions["Move To Top"].isEnabled() is False
        assert nested_actions["Move To Bottom"].isEnabled() is False

        nested_menu.deleteLater()

        panel.set_selected_widgets([target], primary=target)
        target_menu = panel._build_context_menu(target)
        target_actions = _structure_menu_actions(target_menu)

        assert target_actions["Move To Top"].isEnabled() is True
        assert target_actions["Move To Bottom"].isEnabled() is False

        target_menu.deleteLater()
        panel.deleteLater()

    def test_move_into_last_target_context_action_reuses_remembered_target(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
        target_a = WidgetModel("group", name="target_a")
        target_b = WidgetModel("group", name="target_b")
        first = WidgetModel("label", name="first")
        second = WidgetModel("button", name="second")
        root.add_child(target_a)
        root.add_child(target_b)
        root.add_child(first)
        root.add_child(second)

        panel = WidgetTreePanel()
        panel.set_project(project)
        panel.set_selected_widgets([first], primary=first)
        panel._move_selected_widgets_into(
            target_widget=target_b,
            target_label="root_group / target_b (group)",
        )

        panel.set_selected_widgets([second], primary=second)
        menu = panel._build_context_menu(second)
        actions = _structure_menu_actions(menu)

        assert actions["Move Into Last Target"].isEnabled() is True
        assert "root_group / target_b (group)" in actions["Move Into Last Target"].toolTip()

        actions["Move Into Last Target"].trigger()

        assert second.parent is target_b
        assert panel.selected_widgets() == [second]

        menu.deleteLater()
        panel.deleteLater()

    def test_clear_move_target_history_context_action_clears_recent_targets(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
        target = WidgetModel("group", name="target")
        first = WidgetModel("label", name="first")
        second = WidgetModel("button", name="second")
        root.add_child(target)
        root.add_child(first)
        root.add_child(second)

        panel = WidgetTreePanel()
        panel.set_project(project)
        feedback = []
        panel.feedback_message.connect(lambda message: feedback.append(message))

        panel.set_selected_widgets([first], primary=first)
        panel._move_selected_widgets_into(
            target_widget=target,
            target_label="root_group / target (group)",
        )

        panel.set_selected_widgets([second], primary=second)
        menu = panel._build_context_menu(second)
        actions = _structure_menu_actions(menu)

        assert actions["Clear Move Target History"].isEnabled() is True
        assert "Forget 1 recent move-into target" in actions["Clear Move Target History"].toolTip()

        actions["Clear Move Target History"].trigger()

        assert panel.recent_move_target_labels() == []
        assert feedback[-1] == "Cleared 1 recent move target."

        menu.deleteLater()
        menu = panel._build_context_menu(second)
        actions = _structure_menu_actions(menu)
        assert actions["Clear Move Target History"].isEnabled() is False
        assert "Unavailable: no recent move targets are saved." in actions["Clear Move Target History"].toolTip()

        menu.deleteLater()
        panel.deleteLater()

    def test_clear_move_target_history_reports_plural_count(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
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

        panel = WidgetTreePanel()
        panel.set_project(project)
        feedback = []
        panel.feedback_message.connect(lambda message: feedback.append(message))

        panel.set_selected_widgets([first], primary=first)
        panel._move_selected_widgets_into(
            target_widget=target_a,
            target_label="root_group / target_a (group)",
        )
        panel.set_selected_widgets([second], primary=second)
        panel._move_selected_widgets_into(
            target_widget=target_b,
            target_label="root_group / target_b (group)",
        )
        panel.set_selected_widgets([third], primary=third)

        panel._clear_move_target_history()

        assert panel.recent_move_target_labels() == []
        assert feedback[-1] == "Cleared 2 recent move targets."
        panel.deleteLater()

    def test_remembered_move_target_is_scoped_per_project(self, qapp):
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project_a, _root_a = _build_project_with_root()
        project_b, _root_b = _build_project_with_root()

        panel = WidgetTreePanel()
        panel.set_project(project_a)
        panel.set_remembered_move_target_label("target-a")

        panel.set_project(project_b)
        assert panel.remembered_move_target_label() == ""

        panel.set_remembered_move_target_label("target-b")
        assert panel.remembered_move_target_label() == "target-b"

        panel.set_project(project_a)
        assert panel.remembered_move_target_label() == "target-a"

        panel.set_project(project_b)
        assert panel.remembered_move_target_label() == "target-b"
        panel.deleteLater()

    def test_recent_move_target_label_follows_target_rename(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
        target = WidgetModel("group", name="target")
        first = WidgetModel("label", name="first")
        second = WidgetModel("button", name="second")
        root.add_child(target)
        root.add_child(first)
        root.add_child(second)

        panel = WidgetTreePanel()
        panel.set_project(project)
        panel.set_selected_widgets([first], primary=first)
        panel._move_selected_widgets_into(
            target_widget=target,
            target_label="root_group / target (group)",
        )

        target.name = "renamed_target"
        panel.rebuild_tree()
        panel.set_selected_widgets([second], primary=second)

        assert panel.remembered_move_target_label() == "root_group / renamed_target (group)"
        assert "Ctrl+Alt+I repeat into renamed_target" in panel.structure_hint_label.text()

        panel.deleteLater()

    def test_context_menu_structure_actions_disable_root_and_noop_move_into(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
        child = WidgetModel("label", name="child")
        root.add_child(child)

        panel = WidgetTreePanel()
        panel.set_project(project)
        panel.set_selected_widgets([root], primary=root)

        root_menu = panel._build_context_menu(root)
        root_actions = _structure_menu_actions(root_menu)
        root_structure_action = next(action for action in root_menu.actions() if action.text() == "Structure")

        assert root_actions["Group Selection"].isEnabled() is False
        assert root_actions["Ungroup"].isEnabled() is False
        assert root_actions["Move Into..."].isEnabled() is False
        assert root_actions["Lift To Parent"].isEnabled() is False
        assert root_actions["Move Up"].isEnabled() is False
        assert root_actions["Move Down"].isEnabled() is False
        assert root_actions["Move To Top"].isEnabled() is False
        assert root_actions["Move To Bottom"].isEnabled() is False
        assert "root widgets cannot be regrouped or reordered" in root_actions["Group Selection"].toolTip()
        assert "Structure unavailable: root widgets cannot be regrouped or reordered." == root_structure_action.toolTip()

        root_menu.deleteLater()

        panel.set_selected_widgets([child], primary=child)
        child_menu = panel._build_context_menu(child)
        child_actions = _structure_menu_actions(child_menu)
        child_structure_action = next(action for action in child_menu.actions() if action.text() == "Structure")

        assert child_actions["Group Selection"].isEnabled() is False
        assert child_actions["Ungroup"].isEnabled() is False
        assert child_actions["Move Into..."].isEnabled() is False
        assert child_actions["Lift To Parent"].isEnabled() is False
        assert child_actions["Move Up"].isEnabled() is False
        assert child_actions["Move Down"].isEnabled() is False
        assert child_actions["Move To Top"].isEnabled() is False
        assert child_actions["Move To Bottom"].isEnabled() is False
        assert "no eligible target containers are available" in child_actions["Move Into..."].toolTip()
        assert (
            "Structure unavailable: select another sibling or target container to move this widget."
            == child_structure_action.toolTip()
        )

        child_menu.deleteLater()
        panel.deleteLater()

    def test_structure_buttons_reflect_selection_state(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
        first = WidgetModel("label", name="first")
        second = WidgetModel("button", name="second")
        target = WidgetModel("group", name="target")
        nested = WidgetModel("switch", name="nested")
        target.add_child(nested)
        root.add_child(first)
        root.add_child(second)
        root.add_child(target)

        panel = WidgetTreePanel()
        panel.set_project(project)

        assert panel.group_btn.isEnabled() is False
        assert panel.ungroup_btn.isEnabled() is False
        assert panel.into_btn.isEnabled() is False
        assert panel.lift_btn.isEnabled() is False
        assert panel.up_btn.isEnabled() is False
        assert panel.down_btn.isEnabled() is False
        assert panel.top_btn.isEnabled() is False
        assert panel.bottom_btn.isEnabled() is False
        assert panel.structure_hint_label.text() == "Structure: select widgets to group, move, or reorder."
        assert "#666666" in panel.drag_target_label.styleSheet()

        panel.set_selected_widgets([first, second], primary=first)

        assert panel.group_btn.isEnabled() is True
        assert panel.ungroup_btn.isEnabled() is False
        assert panel.into_btn.isEnabled() is True
        assert panel.lift_btn.isEnabled() is False
        assert panel.up_btn.isEnabled() is False
        assert panel.down_btn.isEnabled() is True
        assert panel.top_btn.isEnabled() is False
        assert panel.bottom_btn.isEnabled() is True
        assert "Unavailable: selection must only include groups." in panel.ungroup_btn.toolTip()
        assert "Unavailable: selected widgets already belong to the top container." in panel.lift_btn.toolTip()
        assert "Unavailable: selected widgets are already at the top." in panel.up_btn.toolTip()
        assert "Unavailable: selected widgets are already at the top." in panel.top_btn.toolTip()
        assert "Ctrl+G group siblings" in panel.structure_hint_label.text()
        assert "Ctrl+Shift+I move into container" in panel.structure_hint_label.text()
        assert "Alt+Down reorder" in panel.structure_hint_label.text()
        assert "Alt+Shift+Down move to bottom" in panel.structure_hint_label.text()

        panel.remember_move_target_label("root_group / target (group)")
        panel.set_selected_widgets([second], primary=second)
        assert "Ctrl+Alt+I repeat into target" in panel.structure_hint_label.text()

        panel.set_selected_widgets([second], primary=second)

        assert panel.group_btn.isEnabled() is False
        assert panel.ungroup_btn.isEnabled() is False
        assert panel.into_btn.isEnabled() is True
        assert panel.lift_btn.isEnabled() is False
        assert panel.up_btn.isEnabled() is True
        assert panel.down_btn.isEnabled() is True
        assert panel.top_btn.isEnabled() is True
        assert panel.bottom_btn.isEnabled() is True
        assert "Unavailable: select at least 2 widgets." in panel.group_btn.toolTip()
        assert "Alt+Up/Down reorder" in panel.structure_hint_label.text()
        assert "Alt+Shift+Up/Down move to edge" in panel.structure_hint_label.text()

        panel.set_selected_widgets([nested], primary=nested)

        assert panel.group_btn.isEnabled() is False
        assert panel.ungroup_btn.isEnabled() is False
        assert panel.into_btn.isEnabled() is True
        assert panel.lift_btn.isEnabled() is True
        assert panel.up_btn.isEnabled() is False
        assert panel.down_btn.isEnabled() is False
        assert panel.top_btn.isEnabled() is False
        assert panel.bottom_btn.isEnabled() is False
        assert "Ctrl+Shift+I move into container" in panel.structure_hint_label.text()
        assert "Ctrl+Shift+L lift to parent" in panel.structure_hint_label.text()

        panel.set_selected_widgets([root], primary=root)

        assert panel.group_btn.isEnabled() is False
        assert panel.ungroup_btn.isEnabled() is False
        assert panel.into_btn.isEnabled() is True
        assert panel.into_btn.popupMode() == QToolButton.InstantPopup
        assert panel.lift_btn.isEnabled() is False
        assert panel.up_btn.isEnabled() is False
        assert panel.down_btn.isEnabled() is False
        assert panel.top_btn.isEnabled() is False
        assert panel.bottom_btn.isEnabled() is False
        assert panel.structure_hint_label.text() == (
            "Structure: root widgets cannot be regrouped or reordered. Into menu can clear move history."
        )
        assert "Unavailable: root widgets cannot be regrouped or reordered." in panel.group_btn.toolTip()
        assert panel.into_btn.toolTip() == "Open the Into menu to reuse move-target history."

        panel.deleteLater()

    def test_structure_hint_reports_locked_and_invalid_selection(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
        locked = WidgetModel("label", name="locked")
        locked.designer_locked = True
        root.add_child(locked)

        panel = WidgetTreePanel()
        panel.set_project(project)
        panel.set_selected_widgets([locked], primary=locked)

        assert panel.structure_hint_label.text() == "Structure: locked widgets cannot be moved or regrouped."

        panel.deleteLater()

    def test_structure_hint_reports_isolated_widget_without_move_targets(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
        child = WidgetModel("label", name="child")
        root.add_child(child)

        panel = WidgetTreePanel()
        panel.set_project(project)
        panel.set_selected_widgets([child], primary=child)

        assert panel.structure_hint_label.text() == (
            "Structure: select another sibling or target container to move this widget."
        )
        assert "Unavailable: select at least 2 widgets." in panel.group_btn.toolTip()
        assert "Unavailable: selection must only include groups." in panel.ungroup_btn.toolTip()
        assert "Unavailable: no eligible target containers are available." in panel.into_btn.toolTip()
        assert "Unavailable: selected widgets already belong to the top container." in panel.lift_btn.toolTip()

        panel.deleteLater()

    def test_tree_drop_reorders_selected_widgets_and_emits_feedback(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
        first = WidgetModel("label", name="first")
        second = WidgetModel("label", name="second")
        third = WidgetModel("label", name="third")
        fourth = WidgetModel("label", name="fourth")
        root.add_child(first)
        root.add_child(second)
        root.add_child(third)
        root.add_child(fourth)

        panel = WidgetTreePanel()
        panel.set_project(project)
        panel.set_selected_widgets([second, third], primary=second)
        sources = []
        feedback = []
        panel.tree_changed.connect(lambda source: sources.append(source))
        panel.feedback_message.connect(lambda message: feedback.append(message))

        moved = panel._move_selected_widgets_by_tree_drop(fourth, QAbstractItemView.BelowItem)

        assert moved is True
        assert [widget.name for widget in root.children] == ["first", "fourth", "second", "third"]
        assert panel.selected_widgets() == [second, third]
        assert panel._get_selected_widget() is third
        assert sources == ["tree move"]
        assert feedback == ["Moved 2 widget(s) in the widget tree."]
        panel.deleteLater()

    def test_tree_drop_into_container_moves_selection(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
        target = WidgetModel("group", name="target", x=80, y=20, width=100, height=100)
        child = WidgetModel("label", name="child", x=10, y=15, width=20, height=10)
        root.add_child(target)
        root.add_child(child)

        panel = WidgetTreePanel()
        panel.set_project(project)
        panel.set_selected_widgets([child], primary=child)

        moved = panel._move_selected_widgets_by_tree_drop(target, QAbstractItemView.OnItem)

        assert moved is True
        assert child.parent is target
        assert panel.selected_widgets() == [child]
        assert panel._get_selected_widget() is child
        panel.deleteLater()

    def test_tree_drop_viewport_moves_selection_to_root_end(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
        container = WidgetModel("group", name="container")
        child = WidgetModel("label", name="child")
        tail = WidgetModel("label", name="tail")
        container.add_child(child)
        root.add_child(container)
        root.add_child(tail)

        panel = WidgetTreePanel()
        panel.set_project(project)
        panel.set_selected_widgets([child], primary=child)

        moved = panel._move_selected_widgets_by_tree_drop(None, QAbstractItemView.OnViewport)

        assert moved is True
        assert root.children[-1] is child
        assert child.parent is root
        panel.deleteLater()

    def test_tree_drop_capability_blocks_root_locked_and_noop_targets(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
        first = WidgetModel("label", name="first")
        locked = WidgetModel("label", name="locked")
        locked.designer_locked = True
        root.add_child(first)
        root.add_child(locked)

        panel = WidgetTreePanel()
        panel.set_project(project)

        panel.set_selected_widgets([root], primary=root)
        assert panel._can_drop_selected_widgets(None, QAbstractItemView.OnViewport) is False

        panel.set_selected_widgets([locked], primary=locked)
        assert panel._can_drop_selected_widgets(first, QAbstractItemView.BelowItem) is False

        panel.set_selected_widgets([first], primary=first)
        assert panel._can_drop_selected_widgets(first, QAbstractItemView.AboveItem) is False
        assert panel._can_drop_selected_widgets(None, QAbstractItemView.OnViewport) is True

        panel.deleteLater()

    def test_tree_drop_invalid_target_emits_feedback(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
        first = WidgetModel("label", name="first")
        root.add_child(first)

        panel = WidgetTreePanel()
        panel.set_project(project)
        panel.set_selected_widgets([first], primary=first)
        feedback = []
        panel.feedback_message.connect(lambda message: feedback.append(message))

        moved = panel._move_selected_widgets_by_tree_drop(first, QAbstractItemView.AboveItem)

        assert moved is False
        assert feedback == ["Cannot move selection in tree: widgets are already in that position."]
        panel.deleteLater()

    def test_tree_drag_hover_updates_drop_target_preview(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
        source = WidgetModel("label", name="source")
        target = WidgetModel("group", name="target")
        sibling = WidgetModel("label", name="sibling")
        root.add_child(source)
        root.add_child(target)
        root.add_child(sibling)

        panel = WidgetTreePanel()
        panel.set_project(project)
        panel.set_selected_widgets([source], primary=source)
        target_item = panel._item_map[id(target)]
        sibling_item = panel._item_map[id(sibling)]

        panel._on_tree_drag_hover(target_item, QAbstractItemView.OnItem)

        assert panel.drag_target_label.text() == "Drop target: move into target."
        assert panel._drag_target_item is target_item
        assert "#0b5cab" in panel.drag_target_label.styleSheet()

        panel._on_tree_drag_hover(sibling_item, QAbstractItemView.AboveItem)

        assert panel.drag_target_label.text() == "Drop target: insert before sibling."
        assert panel._drag_target_item is sibling_item

        panel._clear_tree_drag_hover()

        assert panel.drag_target_label.text() == "Drop target: drag over the tree to preview where the selection will land."
        assert panel._drag_target_item is None
        assert "#666666" in panel.drag_target_label.styleSheet()
        panel.deleteLater()

    def test_tree_drag_hover_reports_invalid_target_preview(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
        first = WidgetModel("label", name="first")
        root.add_child(first)

        panel = WidgetTreePanel()
        panel.set_project(project)
        panel.set_selected_widgets([first], primary=first)
        first_item = panel._item_map[id(first)]

        panel._on_tree_drag_hover(first_item, QAbstractItemView.AboveItem)

        assert panel.drag_target_label.text() == (
            "Drop target unavailable: Cannot move selection in tree: widgets are already in that position."
        )
        assert panel._drag_target_item is None
        assert "#a1260d" in panel.drag_target_label.styleSheet()
        panel.deleteLater()

    def test_tree_drag_preview_clears_on_selection_change_and_rebuild(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
        first = WidgetModel("label", name="first")
        second = WidgetModel("group", name="second")
        third = WidgetModel("label", name="third")
        root.add_child(first)
        root.add_child(second)
        root.add_child(third)

        panel = WidgetTreePanel()
        panel.set_project(project)
        panel.set_selected_widgets([first], primary=first)
        second_item = panel._item_map[id(second)]

        panel._on_tree_drag_hover(second_item, QAbstractItemView.OnItem)
        assert panel._drag_target_item is second_item

        panel.set_selected_widgets([third], primary=third)
        assert panel._drag_target_item is None
        assert panel.drag_target_label.text() == "Drop target: drag over the tree to preview where the selection will land."
        assert "#666666" in panel.drag_target_label.styleSheet()

        panel._on_tree_drag_hover(second_item, QAbstractItemView.OnItem)
        assert panel._drag_target_item is second_item

        panel.rebuild_tree()
        assert panel._drag_target_item is None
        assert panel.drag_target_label.text() == "Drop target: drag over the tree to preview where the selection will land."
        assert "#666666" in panel.drag_target_label.styleSheet()
        panel.deleteLater()

    def test_tree_drag_hover_expands_valid_collapsed_container(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
        source = WidgetModel("label", name="source")
        container = WidgetModel("group", name="container")
        nested = WidgetModel("group", name="nested")
        deep_child = WidgetModel("label", name="deep_child")
        nested.add_child(deep_child)
        container.add_child(nested)
        root.add_child(source)
        root.add_child(container)

        panel = WidgetTreePanel()
        panel.set_project(project)
        panel.set_selected_widgets([source], primary=source)
        container_item = panel._item_map[id(container)]
        container_item.setExpanded(False)

        panel._on_tree_drag_hover(container_item, QAbstractItemView.OnItem)
        panel._expand_drag_hover_item()

        assert container_item.isExpanded() is True
        assert id(container) in panel._expanded_widgets
        panel.deleteLater()

    def test_tree_drag_hover_ignores_invalid_targets(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
        source = WidgetModel("label", name="source")
        sibling = WidgetModel("label", name="sibling")
        container = WidgetModel("group", name="container")
        child = WidgetModel("label", name="child")
        container.add_child(child)
        root.add_child(source)
        root.add_child(sibling)
        root.add_child(container)

        panel = WidgetTreePanel()
        panel.set_project(project)
        panel.set_selected_widgets([source], primary=source)
        container_item = panel._item_map[id(container)]
        container_item.setExpanded(False)
        sibling_item = panel._item_map[id(sibling)]

        panel._on_tree_drag_hover(sibling_item, QAbstractItemView.OnItem)
        panel._expand_drag_hover_item()
        assert container_item.isExpanded() is False

        panel._on_tree_drag_hover(container_item, QAbstractItemView.BelowItem)
        panel._expand_drag_hover_item()
        assert container_item.isExpanded() is False

        panel.set_selected_widgets([container], primary=container)
        panel._on_tree_drag_hover(container_item, QAbstractItemView.OnItem)
        panel._expand_drag_hover_item()
        assert container_item.isExpanded() is False

        panel.deleteLater()

    def test_tree_keyboard_shortcuts_dispatch_actions(self, qapp, monkeypatch):
        from ui_designer.ui.widget_tree import WidgetTreePanel

        panel = WidgetTreePanel()
        calls = []

        monkeypatch.setattr(panel, "_on_delete_clicked", lambda: calls.append("delete"))
        monkeypatch.setattr(panel, "_on_rename_clicked", lambda: calls.append("rename"))
        monkeypatch.setattr(panel, "_group_selected_widgets", lambda *args, **kwargs: calls.append("group"))
        monkeypatch.setattr(panel, "_ungroup_selected_widgets", lambda *args, **kwargs: calls.append("ungroup"))
        monkeypatch.setattr(panel, "_move_selected_widgets_into", lambda *args, **kwargs: calls.append("into"))
        monkeypatch.setattr(panel, "_lift_selected_widgets", lambda *args, **kwargs: calls.append("lift"))
        monkeypatch.setattr(panel, "_move_selected_widgets_up", lambda *args, **kwargs: calls.append("up"))
        monkeypatch.setattr(panel, "_move_selected_widgets_down", lambda *args, **kwargs: calls.append("down"))
        monkeypatch.setattr(panel, "_move_selected_widgets_to_top", lambda *args, **kwargs: calls.append("top"))
        monkeypatch.setattr(panel, "_move_selected_widgets_to_bottom", lambda *args, **kwargs: calls.append("bottom"))

        for key, modifiers in (
            (Qt.Key_Delete, Qt.NoModifier),
            (Qt.Key_F2, Qt.NoModifier),
            (Qt.Key_G, Qt.ControlModifier),
            (Qt.Key_G, Qt.ControlModifier | Qt.ShiftModifier),
            (Qt.Key_I, Qt.ControlModifier | Qt.ShiftModifier),
            (Qt.Key_L, Qt.ControlModifier | Qt.ShiftModifier),
            (Qt.Key_Up, Qt.AltModifier),
            (Qt.Key_Down, Qt.AltModifier),
            (Qt.Key_Up, Qt.AltModifier | Qt.ShiftModifier),
            (Qt.Key_Down, Qt.AltModifier | Qt.ShiftModifier),
        ):
            QApplication.sendEvent(panel.tree, QKeyEvent(QEvent.KeyPress, key, modifiers))

        assert calls == ["delete", "rename", "group", "ungroup", "into", "lift", "up", "down", "top", "bottom"]
        panel.deleteLater()

    def test_tree_buttons_and_context_menu_expose_shortcut_hints(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
        first = WidgetModel("label", name="first")
        second = WidgetModel("button", name="second")
        root.add_child(first)
        root.add_child(second)

        panel = WidgetTreePanel()
        panel.set_project(project)
        panel.set_selected_widgets([first, second], primary=first)

        assert "F2" in panel.rename_btn.toolTip()
        assert "Del" in panel.del_btn.toolTip()
        assert "Ctrl+G" in panel.group_btn.toolTip()
        assert "Ctrl+Shift+G" in panel.ungroup_btn.toolTip()
        assert "Ctrl+Shift+I" in panel.into_btn.toolTip()
        assert "Ctrl+Shift+L" in panel.lift_btn.toolTip()
        assert "Alt+Up" in panel.up_btn.toolTip()
        assert "Alt+Down" in panel.down_btn.toolTip()
        assert "Alt+Shift+Up" in panel.top_btn.toolTip()
        assert "Alt+Shift+Down" in panel.bottom_btn.toolTip()

        menu = panel._build_context_menu(first)
        rename_action = next(action for action in menu.actions() if action.text() == "Rename Selected")
        delete_action = next(action for action in menu.actions() if action.text() == "Delete")

        assert rename_action.shortcut().toString() == "F2"
        assert delete_action.shortcut().toString() == "Del"

        menu.deleteLater()
        panel.deleteLater()

    def test_set_selected_widgets_reveals_primary_item_path(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
        container = WidgetModel("group", name="container")
        nested = WidgetModel("group", name="nested")
        target = WidgetModel("label", name="target")
        nested.add_child(target)
        container.add_child(nested)
        root.add_child(container)

        panel = WidgetTreePanel()
        panel.set_project(project)
        container_item = panel._item_map[id(container)]
        nested_item = panel._item_map[id(nested)]
        container_item.setExpanded(False)
        nested_item.setExpanded(False)

        panel.set_selected_widgets([target], primary=target)

        assert container_item.isExpanded() is True
        assert nested_item.isExpanded() is True
        assert panel.selected_widgets() == [target]
        assert panel._get_selected_widget() is target
        panel.deleteLater()

    def test_filter_widgets_keeps_matching_paths_visible_across_rebuilds(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
        container = WidgetModel("group", name="container")
        target = WidgetModel("label", name="target_label")
        other = WidgetModel("button", name="other_button")
        container.add_child(target)
        root.add_child(container)
        root.add_child(other)

        panel = WidgetTreePanel()
        panel.set_project(project)

        panel.filter_edit.setText("target")

        assert panel._item_map[id(root)].isHidden() is False
        assert panel._item_map[id(container)].isHidden() is False
        assert panel._item_map[id(target)].isHidden() is False
        assert panel._item_map[id(container)].isExpanded() is True
        assert panel._item_map[id(container)].font(0).bold() is False
        assert panel._item_map[id(target)].font(0).bold() is True
        assert panel._item_map[id(other)].isHidden() is True
        assert panel.filter_position_label.text() == "0/1"
        assert panel.filter_status_label.text() == "1 match"

        panel.rebuild_tree()

        assert panel._item_map[id(root)].isHidden() is False
        assert panel._item_map[id(container)].isHidden() is False
        assert panel._item_map[id(target)].isHidden() is False
        assert panel._item_map[id(other)].isHidden() is True
        assert panel._item_map[id(target)].font(0).bold() is True
        assert panel.filter_position_label.text() == "0/1"
        assert panel.filter_status_label.text() == "1 match"

        panel.filter_edit.setText("")

        assert panel._item_map[id(other)].isHidden() is False
        assert panel._item_map[id(target)].font(0).bold() is False
        assert panel.filter_position_label.text() == ""
        assert panel.filter_status_label.text() == "All widgets"
        panel.deleteLater()

    def test_filter_widgets_matches_widget_type(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
        label = WidgetModel("label", name="headline")
        button = WidgetModel("button", name="cta")
        root.add_child(label)
        root.add_child(button)

        panel = WidgetTreePanel()
        panel.set_project(project)

        panel.filter_edit.setText("button")

        assert panel._item_map[id(label)].isHidden() is True
        assert panel._item_map[id(button)].isHidden() is False
        assert panel._item_map[id(button)].font(0).bold() is True
        assert panel.filter_position_label.text() == "0/1"
        assert panel.filter_status_label.text() == "1 match"
        panel.deleteLater()

    def test_filter_widgets_reports_no_matches(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
        label = WidgetModel("label", name="headline")
        button = WidgetModel("button", name="cta")
        root.add_child(label)
        root.add_child(button)

        panel = WidgetTreePanel()
        panel.set_project(project)

        panel.filter_edit.setText("missing")

        assert panel._item_map[id(root)].isHidden() is True
        assert panel._item_map[id(label)].isHidden() is True
        assert panel._item_map[id(button)].isHidden() is True
        assert panel.filter_position_label.text() == ""
        assert panel.filter_status_label.text() == "No matches"
        assert panel.filter_prev_btn.isEnabled() is False
        assert panel.filter_next_btn.isEnabled() is False
        panel.deleteLater()

    def test_filter_text_change_emits_feedback_message(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
        root.add_child(WidgetModel("label", name="field_label"))
        root.add_child(WidgetModel("button", name="field_button"))

        panel = WidgetTreePanel()
        panel.set_project(project)
        feedback = []
        panel.feedback_message.connect(lambda message: feedback.append(message))

        panel.filter_edit.setText("field")
        panel.filter_edit.setText("missing")
        panel.filter_edit.setText("")

        assert feedback == [
            "Widget filter 'field': 2 matches.",
            "Widget filter 'missing': no matches.",
            "Widget filter cleared.",
        ]
        panel.deleteLater()

    def test_filter_match_navigation_cycles_through_matches(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
        first = WidgetModel("label", name="field_label")
        second = WidgetModel("button", name="field_button")
        third = WidgetModel("switch", name="status")
        root.add_child(first)
        root.add_child(second)
        root.add_child(third)

        panel = WidgetTreePanel()
        panel.set_project(project)
        panel.filter_edit.setText("field")

        assert panel.filter_position_label.text() == "0/2"
        assert panel.filter_status_label.text() == "2 matches"
        assert panel.filter_prev_btn.isEnabled() is True
        assert panel.filter_next_btn.isEnabled() is True

        panel._select_next_filter_match()
        assert panel._get_selected_widget() is first
        assert panel.filter_position_label.text() == "1/2"

        panel._select_next_filter_match()
        assert panel._get_selected_widget() is second
        assert panel.filter_position_label.text() == "2/2"

        panel._select_next_filter_match()
        assert panel._get_selected_widget() is first
        assert panel.filter_position_label.text() == "1/2"

        panel._select_previous_filter_match()
        assert panel._get_selected_widget() is second
        assert panel.filter_position_label.text() == "2/2"
        panel.deleteLater()

    def test_filter_match_navigation_emits_position_feedback(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
        first = WidgetModel("label", name="field_label")
        second = WidgetModel("button", name="field_button")
        root.add_child(first)
        root.add_child(second)

        panel = WidgetTreePanel()
        panel.set_project(project)
        feedback = []
        panel.feedback_message.connect(lambda message: feedback.append(message))
        panel.filter_edit.setText("field")
        feedback.clear()

        panel._select_next_filter_match()
        panel._select_next_filter_match()

        assert feedback == [
            "Widget filter 'field': 2 matches (1/2).",
            "Widget filter 'field': 2 matches (2/2).",
        ]
        panel.deleteLater()

    def test_filter_edit_keyboard_shortcuts_navigate_matches(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
        first = WidgetModel("label", name="field_label")
        second = WidgetModel("button", name="field_button")
        root.add_child(first)
        root.add_child(second)

        panel = WidgetTreePanel()
        panel.set_project(project)
        panel.filter_edit.setText("field")

        qapp.sendEvent(panel.filter_edit, QKeyEvent(QEvent.KeyPress, Qt.Key_Return, Qt.NoModifier))
        assert panel._get_selected_widget() is first
        assert panel.filter_position_label.text() == "1/2"

        qapp.sendEvent(panel.filter_edit, QKeyEvent(QEvent.KeyPress, Qt.Key_Return, Qt.NoModifier))
        assert panel._get_selected_widget() is second
        assert panel.filter_position_label.text() == "2/2"

        qapp.sendEvent(panel.filter_edit, QKeyEvent(QEvent.KeyPress, Qt.Key_Return, Qt.ShiftModifier))
        assert panel._get_selected_widget() is first
        assert panel.filter_position_label.text() == "1/2"
        panel.deleteLater()

    def test_filter_edit_escape_clears_active_filter(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
        label = WidgetModel("label", name="headline")
        button = WidgetModel("button", name="cta")
        root.add_child(label)
        root.add_child(button)

        panel = WidgetTreePanel()
        panel.set_project(project)
        panel.filter_edit.setText("head")

        qapp.sendEvent(panel.filter_edit, QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier))

        assert panel.filter_edit.text() == ""
        assert panel.filter_position_label.text() == ""
        assert panel.filter_status_label.text() == "All widgets"
        assert panel._item_map[id(root)].isHidden() is False
        assert panel._item_map[id(label)].isHidden() is False
        assert panel._item_map[id(button)].isHidden() is False
        panel.deleteLater()

    def test_filter_position_label_updates_for_manual_match_selection(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
        first = WidgetModel("label", name="field_label")
        second = WidgetModel("button", name="field_button")
        root.add_child(first)
        root.add_child(second)

        panel = WidgetTreePanel()
        panel.set_project(project)
        panel.filter_edit.setText("field")

        panel.set_selected_widgets([second], primary=second)

        assert panel.filter_position_label.text() == "2/2"
        panel.deleteLater()

    def test_rebuild_tree_preserves_manual_collapse_state(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
        container = WidgetModel("group", name="container")
        nested = WidgetModel("group", name="nested")
        nested.add_child(WidgetModel("label", name="target"))
        container.add_child(nested)
        root.add_child(container)

        panel = WidgetTreePanel()
        panel.set_project(project)
        container_item = panel._item_map[id(container)]
        nested_item = panel._item_map[id(nested)]
        container_item.setExpanded(False)
        nested_item.setExpanded(False)

        panel.rebuild_tree()

        assert panel._item_map[id(container)].isExpanded() is False
        assert panel._item_map[id(nested)].isExpanded() is False
        panel.deleteLater()

    def test_clearing_filter_restores_previous_collapse_state(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
        container = WidgetModel("group", name="container")
        nested = WidgetModel("group", name="nested")
        target = WidgetModel("label", name="target")
        nested.add_child(target)
        container.add_child(nested)
        root.add_child(container)

        panel = WidgetTreePanel()
        panel.set_project(project)
        container_item = panel._item_map[id(container)]
        nested_item = panel._item_map[id(nested)]
        container_item.setExpanded(False)
        nested_item.setExpanded(False)

        panel.filter_edit.setText("target")

        assert panel._item_map[id(container)].isExpanded() is True
        assert panel._item_map[id(nested)].isExpanded() is True

        panel.filter_edit.setText("")

        assert panel._item_map[id(container)].isExpanded() is False
        assert panel._item_map[id(nested)].isExpanded() is False
        panel.deleteLater()

    def test_expand_all_updates_tree_and_saved_expansion_state(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
        container = WidgetModel("group", name="container")
        nested = WidgetModel("group", name="nested")
        nested.add_child(WidgetModel("label", name="target"))
        container.add_child(nested)
        root.add_child(container)

        panel = WidgetTreePanel()
        panel.set_project(project)
        panel._collapse_all_items()

        panel._expand_all_items()
        panel.rebuild_tree()

        assert panel._item_map[id(root)].isExpanded() is True
        assert panel._item_map[id(container)].isExpanded() is True
        assert panel._item_map[id(nested)].isExpanded() is True
        panel.deleteLater()

    def test_collapse_all_updates_tree_and_saved_expansion_state(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
        container = WidgetModel("group", name="container")
        nested = WidgetModel("group", name="nested")
        nested.add_child(WidgetModel("label", name="target"))
        container.add_child(nested)
        root.add_child(container)

        panel = WidgetTreePanel()
        panel.set_project(project)

        panel._collapse_all_items()
        panel.rebuild_tree()

        assert panel._item_map[id(root)].isExpanded() is False
        assert panel._item_map[id(container)].isExpanded() is False
        assert panel._item_map[id(nested)].isExpanded() is False
        panel.deleteLater()
