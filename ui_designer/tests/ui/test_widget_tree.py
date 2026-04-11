"""Qt UI tests for WidgetTreePanel name handling."""

import pytest

from ui_designer.tests.project_builders import (
    build_test_project_with_root as _build_project_with_root,
    build_test_project_with_widgets as _build_project_with_widgets,
)
from ui_designer.tests.qt_test_utils import HAS_PYQT5, skip_if_no_qt
from ui_designer.utils.scaffold import add_widget_children as _add_widget_children

if HAS_PYQT5:
    from PyQt5.QtCore import QEvent, Qt
    from PyQt5.QtGui import QFont, QKeyEvent
    from PyQt5.QtWidgets import QApplication, QAbstractItemView, QToolButton

_skip_no_qt = skip_if_no_qt


def _structure_menu_actions(menu):
    structure_menu = None
    for action in menu.actions():
        if action.text() == "Structure":
            structure_menu = action.menu()
            break
    assert structure_menu is not None
    return {action.text(): action for action in structure_menu.actions() if action.text()}


def _structure_menu_labels(menu):
    structure_menu = _context_submenu(menu, "Structure")
    return [action.text() for action in structure_menu.actions() if action.text()]


def _context_submenu(menu, label):
    for action in menu.actions():
        if action.text() == label:
            return action.menu()
    raise AssertionError(f"{label} submenu not found")


def _select_menu_actions(menu):
    select_menu = _context_submenu(menu, "Select")
    return {action.text(): action for action in select_menu.actions() if action.text()}


def _select_menu_labels(menu):
    select_menu = _context_submenu(menu, "Select")
    return [action.text() for action in select_menu.actions() if action.text()]


@_skip_no_qt
class TestWidgetTreePanel:
    def test_structure_tree_uses_dense_item_font_by_default(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.theme import app_theme_tokens
        from ui_designer.ui.widget_tree import WidgetTreePanel

        leaf = WidgetModel("label", name="field_label")
        project, _page, root = _build_project_with_widgets(widgets=[leaf])

        panel = WidgetTreePanel()
        panel.set_project(project)

        tokens = app_theme_tokens()
        expected_px = int(tokens["fs_body_sm"])
        leaf_item = panel._item_map[id(leaf)]

        assert panel.tree.font().pixelSize() == expected_px
        assert leaf_item.font(0).pixelSize() == expected_px
        panel.deleteLater()

    def test_refresh_tree_typography_reuses_current_tree_font(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        label = WidgetModel("label", name="field_label")
        button = WidgetModel("button", name="field_button")
        project, _page, root = _build_project_with_widgets(widgets=[label, button])

        panel = WidgetTreePanel()
        panel.set_project(project)
        panel.filter_edit.setText("field_button")

        font = QFont(panel.tree.font())
        font.setPointSize(15)
        panel.tree.setFont(font)
        panel.refresh_tree_typography()

        label_item = panel._item_map[id(label)]
        button_item = panel._item_map[id(button)]
        assert label_item.font(0).pointSize() == 15
        assert button_item.font(0).pointSize() == 15
        assert label_item.font(0).bold() is False
        assert button_item.font(0).bold() is True
        panel.deleteLater()

    def test_change_event_refreshes_tree_typography(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        label = WidgetModel("label", name="field_label")
        button = WidgetModel("button", name="field_button")
        project, _page, root = _build_project_with_widgets(widgets=[label, button])

        panel = WidgetTreePanel()
        panel.set_project(project)
        panel.filter_edit.setText("field_button")

        font = QFont(panel.tree.font())
        font.setPointSize(15)
        panel.tree.setFont(font)
        panel.changeEvent(QEvent(QEvent.FontChange))

        label_item = panel._item_map[id(label)]
        button_item = panel._item_map[id(button)]
        assert label_item.font(0).pointSize() == 15
        assert button_item.font(0).pointSize() == 15
        assert label_item.font(0).bold() is False
        assert button_item.font(0).bold() is True
        panel.deleteLater()

    def test_parent_nodes_use_semibold_tree_typography(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        branch = WidgetModel("group", name="branch")
        nested = WidgetModel("group", name="nested")
        leaf = WidgetModel("label", name="leaf")
        nested_leaf = WidgetModel("button", name="nested_leaf")
        _add_widget_children(branch, [leaf, nested])
        _add_widget_children(nested, [nested_leaf])
        project, _page, root = _build_project_with_widgets(widgets=[branch])

        panel = WidgetTreePanel()
        panel.set_project(project)

        root_item = panel._item_map[id(root)]
        branch_item = panel._item_map[id(branch)]
        nested_item = panel._item_map[id(nested)]
        leaf_item = panel._item_map[id(leaf)]
        nested_leaf_item = panel._item_map[id(nested_leaf)]

        assert root_item.font(0).weight() == QFont.DemiBold
        assert branch_item.font(0).weight() == QFont.DemiBold
        assert nested_item.font(0).weight() == QFont.DemiBold
        assert leaf_item.font(0).weight() == QFont.Normal
        assert nested_leaf_item.font(0).weight() == QFont.Normal
        panel.deleteLater()

    def test_header_metadata_tracks_selection_and_filter_context(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        leaf = WidgetModel("label", name="leaf")
        project, _page, root = _build_project_with_widgets(widgets=[leaf])

        panel = WidgetTreePanel()
        panel.set_project(project)
        header_layout = panel._header_frame.layout()
        title_row = header_layout.itemAt(1).layout()
        metrics_layout = panel._metrics_frame.layout()
        drag_hint_layout = panel._drag_hint_frame.layout()
        drag_margins = drag_hint_layout.contentsMargins()
        header_margins = header_layout.contentsMargins()

        assert panel._header_eyebrow.accessibleName() == "Structure navigation workspace surface."
        assert panel._header_eyebrow.isHidden() is True
        assert panel.layout().spacing() == 2
        assert (header_margins.left(), header_margins.top(), header_margins.right(), header_margins.bottom()) == (2, 2, 2, 2)
        assert header_layout.spacing() == 2
        assert title_row.spacing() == 2
        assert metrics_layout.spacing() == 2
        assert (drag_margins.left(), drag_margins.top(), drag_margins.right(), drag_margins.bottom()) == (2, 2, 2, 2)
        assert panel._header_frame.accessibleName() == (
            "Widget tree header. Widget tree: 2 widgets. 0 selected widgets. Current widget: none. "
            "Filter: none. Status: All widgets. Position: none. "
            f"{panel.structure_hint_label.text()}"
        )
        assert panel.tree.header().isHidden() is True
        assert panel._title_label.accessibleName() == "Widget tree title: Structure."
        assert panel._header_meta_label.accessibleName() == panel._header_meta_label.text()
        assert panel._header_meta_label.isHidden() is True
        assert panel._filter_hint_label.accessibleName() == panel._filter_hint_label.text()
        assert panel._filter_hint_label.isHidden() is True
        assert panel._tree_count_chip.text() == "2 widgets"
        assert panel._tree_count_chip.accessibleName() == "Widget count: 2 widgets."
        assert panel._selection_summary_chip.text() == "No selection"
        assert panel._selection_summary_chip.isHidden() is True
        assert panel._selection_summary_chip.accessibleName() == "Selection summary: no selection."
        assert panel._filter_summary_chip.text() == "All widgets"
        assert panel._filter_summary_chip.accessibleName() == "Filter summary: All widgets."
        assert panel._metrics_frame.isHidden() is True
        assert panel._metrics_frame.accessibleName() == "Structure metrics: 2 widgets. Filter status: All widgets."

        panel.set_selected_widgets([leaf], primary=leaf)
        panel.filter_edit.setText("leaf")
        qapp.processEvents()

        assert panel._header_frame.accessibleName() == (
            "Widget tree header. Widget tree: 2 widgets. 1 selected widget. Current widget: leaf. "
            "Filter: leaf. Status: 1 match. Position: 1/1. "
            f"{panel.structure_hint_label.text()}"
        )
        assert panel._header_meta_label.accessibleName() == panel._header_meta_label.text()
        assert panel._selection_summary_chip.text() == "1 selected - leaf"
        assert panel._selection_summary_chip.isHidden() is True
        assert panel._selection_summary_chip.accessibleName() == "Selection summary: 1 selected - leaf."
        assert panel._filter_summary_chip.text() == "1 match"
        assert panel._filter_summary_chip.accessibleName() == "Filter summary: 1 match."
        assert panel._metrics_frame.isHidden() is True
        assert panel._metrics_frame.accessibleName() == (
            "Structure metrics: 2 widgets. Filter status: 1 match. Match position: 1/1."
        )
        panel.deleteLater()

    def test_header_frame_hint_skips_no_op_rewrites(self, qapp, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        leaf = WidgetModel("label", name="leaf")
        project, _page, root = _build_project_with_widgets(widgets=[leaf])

        panel = WidgetTreePanel()
        panel.set_project(project)
        panel.set_selected_widgets([leaf], primary=leaf)
        panel._header_frame.setProperty("_widget_tree_hint_snapshot", None)

        hint_calls = 0
        original_set_tooltip = panel._header_frame.setToolTip

        def counted_set_tooltip(text):
            nonlocal hint_calls
            hint_calls += 1
            return original_set_tooltip(text)

        monkeypatch.setattr(panel._header_frame, "setToolTip", counted_set_tooltip)

        panel._update_accessibility_summary()
        assert hint_calls == 1

        panel._update_accessibility_summary()
        assert hint_calls == 1

        panel.filter_edit.setText("leaf")
        qapp.processEvents()
        assert hint_calls == 2
        panel.deleteLater()

    def test_header_frame_accessible_name_skips_no_op_rewrites(self, qapp, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        leaf = WidgetModel("label", name="leaf")
        project, _page, root = _build_project_with_widgets(widgets=[leaf])

        panel = WidgetTreePanel()
        panel.set_project(project)
        panel.set_selected_widgets([leaf], primary=leaf)
        panel._header_frame.setProperty("_widget_tree_accessible_snapshot", None)

        accessible_calls = 0
        original_set_accessible_name = panel._header_frame.setAccessibleName

        def counted_set_accessible_name(text):
            nonlocal accessible_calls
            accessible_calls += 1
            return original_set_accessible_name(text)

        monkeypatch.setattr(panel._header_frame, "setAccessibleName", counted_set_accessible_name)

        panel._update_accessibility_summary()
        assert accessible_calls == 1

        panel._update_accessibility_summary()
        assert accessible_calls == 1

        panel.filter_edit.setText("leaf")
        qapp.processEvents()
        assert accessible_calls == 2
        panel.deleteLater()

    def test_context_menu_top_level_actions_appear_in_expected_order(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        leaf = WidgetModel("label", name="leaf")
        project, _page, root = _build_project_with_widgets(widgets=[leaf])

        panel = WidgetTreePanel()
        panel.set_project(project)

        root_menu = panel._build_context_menu(root)
        root_labels = [action.text() for action in root_menu.actions() if action.text()]
        assert root_labels[:2] == ["Rename", "Insert Component..."]
        assert root_labels[-3:] == ["Select", "Structure", "Delete"]
        if len(root_labels) == 6:
            assert root_labels[2] == "Recent Widgets"
        else:
            assert root_labels == [
                "Rename",
                "Insert Component...",
                "Select",
                "Structure",
                "Delete",
            ]
        root_menu.deleteLater()

        leaf_menu = panel._build_context_menu(leaf)
        leaf_labels = [action.text() for action in leaf_menu.actions() if action.text()]
        assert leaf_labels[:2] == ["Rename", "Insert Component..."]
        assert leaf_labels[-3:] == ["Select", "Structure", "Delete"]
        if len(leaf_labels) == 6:
            assert leaf_labels[2] == "Recent Widgets"
        else:
            assert leaf_labels == [
                "Rename",
                "Insert Component...",
                "Select",
                "Structure",
                "Delete",
            ]
        leaf_menu.deleteLater()
        panel.deleteLater()

    def test_context_menu_structure_actions_appear_in_expected_order(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        first = WidgetModel("label", name="first")
        second = WidgetModel("button", name="second")
        target = WidgetModel("group", name="target")
        project, _page, root = _build_project_with_widgets(widgets=[first, second, target])

        panel = WidgetTreePanel()
        panel.set_project(project)
        panel.set_selected_widgets([first, second], primary=first)

        menu = panel._build_context_menu(first)
        assert _structure_menu_labels(menu) == [
            "Group Selection",
            "Ungroup",
            "Move Into...",
            "Lift To Parent",
            "Move Up",
            "Move Down",
            "Move To Top",
            "Move To Bottom",
        ]

        menu.deleteLater()
        panel.deleteLater()

    def test_context_menu_select_actions_appear_in_expected_order(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, _page, root = _build_project_with_widgets(
            widgets=[WidgetModel("label", name="first")]
        )

        panel = WidgetTreePanel()
        panel.set_project(project)

        menu = panel._build_context_menu(root)
        assert _select_menu_labels(menu) == [
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
        panel.deleteLater()

    def test_insert_button_emits_browser_request_with_expected_parent(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        leaf = WidgetModel("label", name="leaf")
        project, _page, root = _build_project_with_widgets(widgets=[leaf])

        panel = WidgetTreePanel()
        panel.set_project(project)
        panel.set_selected_widgets([leaf], primary=leaf)

        requests = []
        panel.browse_widgets_requested.connect(requests.append)

        panel._on_add_clicked()

        assert requests == [root]
        panel.deleteLater()

    def test_context_menu_recent_widgets_follow_browser_history(self, qapp):
        from ui_designer.model.config import DesignerConfig
        from ui_designer.model.widget_registry import WidgetRegistry
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()
        panel = WidgetTreePanel()
        panel.set_project(project)
        DesignerConfig.instance().widget_browser_recent = ["label", "button", "missing_widget"]

        menu = panel._build_context_menu(root)
        recent_menu = _context_submenu(menu, "Recent Widgets")
        recent_actions = [action for action in recent_menu.actions() if action.text()]

        assert [action.text() for action in recent_actions] == [
            WidgetRegistry.instance().display_name("label"),
            WidgetRegistry.instance().display_name("button"),
        ]
        assert recent_menu.menuAction().toolTip() == "Insert a recently used widget into root_group (group)."
        assert recent_menu.menuAction().statusTip() == recent_menu.menuAction().toolTip()
        assert recent_actions[0].toolTip() == f"Insert {recent_actions[0].text()} into root_group (group)."
        assert recent_actions[0].statusTip() == recent_actions[0].toolTip()
        assert recent_actions[1].toolTip() == f"Insert {recent_actions[1].text()} into root_group (group)."
        assert recent_actions[1].statusTip() == recent_actions[1].toolTip()

        DesignerConfig.instance().widget_browser_recent = []
        menu.deleteLater()
        panel.deleteLater()

    def test_rename_widget_resolves_duplicate_name(self, qapp, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        first = WidgetModel("label", name="title")
        second = WidgetModel("label", name="subtitle")
        project, _page, root = _build_project_with_widgets(widgets=[first, second])

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

        project, _page, root = _build_project_with_widgets(
            widgets=[WidgetModel("button", name="button_1")]
        )
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

        widget = WidgetModel("label", name="title")
        project, _page, root = _build_project_with_widgets(widgets=[widget])

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

        first = WidgetModel("label", name="title")
        second = WidgetModel("label", name="subtitle")
        project, _page, root = _build_project_with_widgets(widgets=[first, second])

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

        existing = WidgetModel("label", name="field_1")
        first = WidgetModel("label", name="title")
        second = WidgetModel("button", name="cta")
        project, _page, root = _build_project_with_widgets(widgets=[existing, first, second])

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

        first = WidgetModel("label", name="title")
        second = WidgetModel("button", name="cta")
        project, _page, root = _build_project_with_widgets(widgets=[first, second])

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

        container = WidgetModel("group", name="container")
        child = WidgetModel("label", name="title")
        _add_widget_children(container, [child])
        project, _page, root = _build_project_with_widgets(widgets=[container])

        panel = WidgetTreePanel()
        panel.set_project(project)
        panel.set_selected_widgets([container, child], primary=container)

        panel._on_delete_clicked()

        assert root.children == []
        panel.deleteLater()

    def test_delete_selected_skips_locked_widgets_and_emits_feedback(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        removable = WidgetModel("label", name="removable")
        locked = WidgetModel("label", name="locked_widget")
        locked.designer_locked = True
        project, _page, root = _build_project_with_widgets(widgets=[removable, locked])

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

        locked = WidgetModel("label", name="locked_widget")
        locked.designer_locked = True
        project, _page, root = _build_project_with_widgets(widgets=[locked])

        panel = WidgetTreePanel()
        panel.set_project(project)
        feedback = []
        panel.feedback_message.connect(lambda message: feedback.append(message))

        panel._delete_widget(locked)

        assert locked in root.children
        assert feedback == ["Cannot delete widget: locked_widget is locked."]
        panel.deleteLater()

    def test_delete_selection_removes_selected_widget(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        target = WidgetModel("group", name="target")
        removable = WidgetModel("label", name="removable")
        sibling = WidgetModel("button", name="sibling")
        project, _page, root = _build_project_with_widgets(widgets=[target, removable, sibling])

        panel = WidgetTreePanel()
        panel.set_project(project)
        feedback = []
        panel.feedback_message.connect(lambda message: feedback.append(message))
        panel.set_selected_widgets([target], primary=target)

        panel._on_delete_clicked()

        assert target not in root.children
        assert feedback == []
        panel.deleteLater()

    def test_group_selected_widgets_emits_tree_change_and_selects_group(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        first = WidgetModel("label", name="first", x=10, y=20, width=30, height=10)
        second = WidgetModel("button", name="second", x=60, y=40, width=20, height=20)
        project, _page, root = _build_project_with_widgets(widgets=[first, second])

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

        target = WidgetModel("group", name="target", x=80, y=10, width=100, height=100)
        child = WidgetModel("label", name="child", x=10, y=15, width=20, height=10)
        project, _page, root = _build_project_with_widgets(widgets=[target, child])

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

    def test_context_menu_structure_actions_reflect_selection_state(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        first = WidgetModel("label", name="first")
        second = WidgetModel("button", name="second")
        target = WidgetModel("group", name="target")
        nested = WidgetModel("switch", name="nested")
        target.add_child(nested)
        project, _page, root = _build_project_with_widgets(widgets=[first, second, target])

        panel = WidgetTreePanel()
        panel.set_project(project)
        panel.set_selected_widgets([first, second], primary=first)

        menu = panel._build_context_menu(first)
        actions = _structure_menu_actions(menu)

        assert actions["Group Selection"].isEnabled() is True
        assert actions["Ungroup"].isEnabled() is False
        assert actions["Move Into..."].isEnabled() is True
        assert actions["Lift To Parent"].isEnabled() is False
        assert actions["Move Up"].isEnabled() is False
        assert actions["Move Down"].isEnabled() is True
        assert actions["Move To Top"].isEnabled() is False
        assert actions["Move To Bottom"].isEnabled() is True
        assert "Unavailable: selection must only include groups." in actions["Ungroup"].toolTip()
        assert actions["Group Selection"].statusTip() == actions["Group Selection"].toolTip()
        assert actions["Ungroup"].statusTip() == actions["Ungroup"].toolTip()
        assert actions["Move Into..."].statusTip() == actions["Move Into..."].toolTip()
        assert actions["Lift To Parent"].statusTip() == actions["Lift To Parent"].toolTip()
        assert actions["Move Up"].statusTip() == actions["Move Up"].toolTip()
        assert actions["Move Down"].statusTip() == actions["Move Down"].toolTip()
        assert actions["Move To Top"].statusTip() == actions["Move To Top"].toolTip()
        assert actions["Move To Bottom"].statusTip() == actions["Move To Bottom"].toolTip()
        assert "Unavailable: selected widgets already belong to the top container." in actions["Lift To Parent"].toolTip()
        assert "Unavailable: selected widgets are already at the top." in actions["Move Up"].toolTip()
        assert "Unavailable: selected widgets are already at the top." in actions["Move To Top"].toolTip()
        assert actions["Group Selection"].shortcut().toString() == "Ctrl+G"
        assert actions["Ungroup"].shortcut().toString() == "Ctrl+Shift+G"
        assert actions["Move Into..."].shortcut().toString() == "Ctrl+Shift+I"
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

    def test_context_menu_select_actions_reflect_widget_relationships(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        first = WidgetModel("label", name="first")
        container = WidgetModel("group", name="container")
        child_a = WidgetModel("switch", name="child_a")
        child_b = WidgetModel("button", name="child_b")
        solo = WidgetModel("label", name="solo")
        _add_widget_children(container, [child_a, child_b])
        project, _page, root = _build_project_with_widgets(widgets=[first, container, solo])

        panel = WidgetTreePanel()
        panel.set_project(project)

        root_menu = panel._build_context_menu(root)
        root_actions = _select_menu_actions(root_menu)
        root_select_action = next(action for action in root_menu.actions() if action.text() == "Select")
        assert root_actions["Parent"].isEnabled() is False
        assert root_actions["Previous Sibling"].isEnabled() is False
        assert root_actions["Next Sibling"].isEnabled() is False
        assert root_actions["Previous Siblings"].isEnabled() is False
        assert root_actions["Next Siblings"].isEnabled() is False
        assert root_actions["Previous In Tree"].isEnabled() is False
        assert root_actions["Next In Tree"].isEnabled() is True
        assert root_actions["Ancestors"].isEnabled() is False
        assert root_actions["Root"].isEnabled() is False
        assert root_actions["Path"].isEnabled() is True
        assert root_actions["Top-Level"].isEnabled() is True
        assert root_actions["First Child"].isEnabled() is True
        assert root_actions["Last Child"].isEnabled() is True
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
        assert root_actions["Managed"].isEnabled() is False
        assert root_actions["Free Position"].isEnabled() is True
        assert root_actions["Siblings"].isEnabled() is False
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
        assert "Unavailable: no layout-managed widgets exist in this subtree." in root_actions["Managed"].toolTip()
        assert "Unavailable: root widgets do not have siblings." in root_actions["Siblings"].toolTip()
        assert root_actions["Parent"].statusTip() == root_actions["Parent"].toolTip()
        assert root_actions["Managed"].statusTip() == root_actions["Managed"].toolTip()
        assert root_select_action.toolTip() == (
            "Select related widgets from this widget's parent, subtree, siblings, and page hierarchy."
        )
        assert root_select_action.statusTip() == root_select_action.toolTip()
        root_menu.deleteLater()

        first_menu = panel._build_context_menu(first)
        first_actions = _select_menu_actions(first_menu)
        assert first_actions["Same Parent Type"].isEnabled() is True
        assert first_actions["Subtree Type"].isEnabled() is False
        assert first_actions["Same Type"].isEnabled() is True
        assert first_actions["Same Depth"].isEnabled() is True
        first_menu.deleteLater()

        container_menu = panel._build_context_menu(container)
        container_actions = _select_menu_actions(container_menu)
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

        child_menu = panel._build_context_menu(child_a)
        child_actions = _select_menu_actions(child_menu)
        child_structure_action = next(action for action in child_menu.actions() if action.text() == "Structure")
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
        assert "Unavailable: widget has no child widgets." in child_actions["Children"].toolTip()
        assert "Unavailable: widget has no descendant widgets." in child_actions["Descendants"].toolTip()
        assert "Unavailable: widget has no descendant widgets." in child_actions["Subtree"].toolTip()
        assert "Unavailable: widget has no leaf descendants." in child_actions["Leaves"].toolTip()
        assert "Unavailable: no other container widgets exist in this subtree." in child_actions["Containers"].toolTip()
        assert "Unavailable: no layout container widgets exist in this subtree." in child_actions["Layout Containers"].toolTip()
        assert "Unavailable: widget has no child widgets." in child_actions["First Child"].toolTip()
        assert "Unavailable: widget has no child widgets." in child_actions["Last Child"].toolTip()
        assert "Unavailable: no hidden widgets exist in this subtree." in child_actions["Hidden"].toolTip()
        assert "Unavailable: no locked widgets exist in this subtree." in child_actions["Locked"].toolTip()
        assert "Unavailable: no layout-managed widgets exist in this subtree." in child_actions["Managed"].toolTip()
        assert "Unavailable: no other switch widgets exist under the same parent." in child_actions["Same Parent Type"].toolTip()
        assert "Unavailable: no other switch widgets exist in this subtree." in child_actions["Subtree Type"].toolTip()
        assert "Unavailable: no other switch widgets exist on this page." in child_actions["Same Type"].toolTip()
        assert "Unavailable: widget does not have a previous sibling under the same parent." in child_actions["Previous Sibling"].toolTip()
        assert "Unavailable: widget does not have any previous siblings under the same parent." in child_actions["Previous Siblings"].toolTip()
        assert child_actions["Children"].statusTip() == child_actions["Children"].toolTip()
        assert child_actions["Same Type"].statusTip() == child_actions["Same Type"].toolTip()
        assert child_structure_action.toolTip() == "Group, move, and reorder widgets relative to the current selection."
        assert child_structure_action.statusTip() == child_structure_action.toolTip()
        child_menu.deleteLater()

        solo_menu = panel._build_context_menu(solo)
        solo_actions = _select_menu_actions(solo_menu)
        assert solo_actions["Previous Siblings"].isEnabled() is True
        assert solo_actions["Next Siblings"].isEnabled() is False
        assert solo_actions["Previous In Tree"].isEnabled() is True
        assert solo_actions["Next In Tree"].isEnabled() is False
        assert "Unavailable: widget does not have any next siblings under the same parent." in solo_actions["Next Siblings"].toolTip()
        assert "Unavailable: widget is already the last widget in tree order on this page." in solo_actions["Next In Tree"].toolTip()
        solo_menu.deleteLater()
        panel.deleteLater()

    def test_context_menu_select_actions_update_selection_and_feedback(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        other = WidgetModel("label", name="other")
        container = WidgetModel("group", name="container")
        child_a = WidgetModel("switch", name="child_a")
        child_b = WidgetModel("button", name="child_b")
        nested_group = WidgetModel("group", name="nested_group")
        nested_leaf = WidgetModel("label", name="nested_leaf")
        same_type = WidgetModel("button", name="same_type")
        _add_widget_children(nested_group, [nested_leaf])
        _add_widget_children(container, [child_a, child_b, nested_group])
        project, _page, root = _build_project_with_widgets(widgets=[other, container, same_type])

        panel = WidgetTreePanel()
        panel.set_project(project)
        selection_events = []
        feedback = []
        panel.selection_changed.connect(
            lambda widgets, primary: selection_events.append(
                ([widget.name for widget in widgets], primary.name if primary is not None else "")
            )
        )
        panel.feedback_message.connect(lambda message: feedback.append(message))

        panel.set_selected_widgets([other], primary=other)

        parent_menu = panel._build_context_menu(child_a)
        parent_actions = _select_menu_actions(parent_menu)
        parent_actions["Parent"].trigger()
        assert panel.selected_widgets() == [container]
        assert panel._get_selected_widget() is container
        assert selection_events[-1] == (["container"], "container")
        assert feedback[-1] == "Selected parent widget: container."
        parent_menu.deleteLater()

        previous_in_tree_menu = panel._build_context_menu(container)
        previous_in_tree_actions = _select_menu_actions(previous_in_tree_menu)
        previous_in_tree_actions["Previous In Tree"].trigger()
        assert panel.selected_widgets() == [other]
        assert panel._get_selected_widget() is other
        assert selection_events[-1] == (["other"], "other")
        assert feedback[-1] == "Selected previous widget in tree order: other."
        previous_in_tree_menu.deleteLater()

        next_in_tree_menu = panel._build_context_menu(container)
        next_in_tree_actions = _select_menu_actions(next_in_tree_menu)
        next_in_tree_actions["Next In Tree"].trigger()
        assert panel.selected_widgets() == [child_a]
        assert panel._get_selected_widget() is child_a
        assert selection_events[-1] == (["child_a"], "child_a")
        assert feedback[-1] == "Selected next widget in tree order: child_a."
        next_in_tree_menu.deleteLater()

        previous_siblings_menu = panel._build_context_menu(nested_group)
        previous_siblings_actions = _select_menu_actions(previous_siblings_menu)
        previous_siblings_actions["Previous Siblings"].trigger()
        assert panel.selected_widgets() == [child_a, child_b]
        assert panel._get_selected_widget() is child_b
        assert selection_events[-1] == (["child_a", "child_b"], "child_b")
        assert feedback[-1] == "Selected 2 previous sibling widgets before nested_group."
        previous_siblings_menu.deleteLater()

        next_siblings_menu = panel._build_context_menu(child_a)
        next_siblings_actions = _select_menu_actions(next_siblings_menu)
        next_siblings_actions["Next Siblings"].trigger()
        assert panel.selected_widgets() == [child_b, nested_group]
        assert panel._get_selected_widget() is child_b
        assert selection_events[-1] == (["child_b", "nested_group"], "child_b")
        assert feedback[-1] == "Selected 2 next sibling widgets after child_a."
        next_siblings_menu.deleteLater()

        first_child_menu = panel._build_context_menu(container)
        first_child_actions = _select_menu_actions(first_child_menu)
        first_child_actions["First Child"].trigger()
        assert panel.selected_widgets() == [child_a]
        assert panel._get_selected_widget() is child_a
        assert selection_events[-1] == (["child_a"], "child_a")
        assert feedback[-1] == "Selected first child: child_a."
        first_child_menu.deleteLater()

        last_child_menu = panel._build_context_menu(container)
        last_child_actions = _select_menu_actions(last_child_menu)
        last_child_actions["Last Child"].trigger()
        assert panel.selected_widgets() == [nested_group]
        assert panel._get_selected_widget() is nested_group
        assert selection_events[-1] == (["nested_group"], "nested_group")
        assert feedback[-1] == "Selected last child: nested_group."
        last_child_menu.deleteLater()

        previous_menu = panel._build_context_menu(child_b)
        previous_actions = _select_menu_actions(previous_menu)
        previous_actions["Previous Sibling"].trigger()
        assert panel.selected_widgets() == [child_a]
        assert panel._get_selected_widget() is child_a
        assert selection_events[-1] == (["child_a"], "child_a")
        assert feedback[-1] == "Selected previous sibling: child_a."
        previous_menu.deleteLater()

        next_menu = panel._build_context_menu(child_b)
        next_actions = _select_menu_actions(next_menu)
        next_actions["Next Sibling"].trigger()
        assert panel.selected_widgets() == [nested_group]
        assert panel._get_selected_widget() is nested_group
        assert selection_events[-1] == (["nested_group"], "nested_group")
        assert feedback[-1] == "Selected next sibling: nested_group."
        next_menu.deleteLater()

        ancestors_menu = panel._build_context_menu(nested_leaf)
        ancestors_actions = _select_menu_actions(ancestors_menu)
        ancestors_actions["Ancestors"].trigger()
        assert panel.selected_widgets() == [root, container, nested_group]
        assert panel._get_selected_widget() is nested_group
        assert selection_events[-1] == (["root_group", "container", "nested_group"], "nested_group")
        assert feedback[-1] == "Selected 3 ancestor widgets of nested_leaf."
        ancestors_menu.deleteLater()

        root_menu = panel._build_context_menu(nested_leaf)
        root_actions = _select_menu_actions(root_menu)
        root_actions["Root"].trigger()
        assert panel.selected_widgets() == [root]
        assert panel._get_selected_widget() is root
        assert selection_events[-1] == (["root_group"], "root_group")
        assert feedback[-1] == "Selected page root: root_group."
        root_menu.deleteLater()

        path_menu = panel._build_context_menu(nested_leaf)
        path_actions = _select_menu_actions(path_menu)
        path_actions["Path"].trigger()
        assert panel.selected_widgets() == [root, container, nested_group, nested_leaf]
        assert panel._get_selected_widget() is nested_leaf
        assert selection_events[-1] == (["root_group", "container", "nested_group", "nested_leaf"], "nested_leaf")
        assert feedback[-1] == "Selected 4 widgets in path to nested_leaf."
        path_menu.deleteLater()

        top_level_menu = panel._build_context_menu(nested_leaf)
        top_level_actions = _select_menu_actions(top_level_menu)
        top_level_actions["Top-Level"].trigger()
        assert panel.selected_widgets() == [other, container, same_type]
        assert panel._get_selected_widget() is container
        assert selection_events[-1] == (["other", "container", "same_type"], "container")
        assert feedback[-1] == "Selected 3 top-level widgets on this page."
        top_level_menu.deleteLater()

        subtree_type_menu = panel._build_context_menu(root)
        subtree_type_actions = _select_menu_actions(subtree_type_menu)
        subtree_type_actions["Subtree Type"].trigger()
        assert panel.selected_widgets() == [root, container, nested_group]
        assert panel._get_selected_widget() is root
        assert selection_events[-1] == (["root_group", "container", "nested_group"], "root_group")
        assert feedback[-1] == "Selected 3 group widgets in subtree of root_group."
        subtree_type_menu.deleteLater()

        children_menu = panel._build_context_menu(container)
        children_actions = _select_menu_actions(children_menu)
        children_actions["Children"].trigger()
        assert panel.selected_widgets() == [child_a, child_b, nested_group]
        assert panel._get_selected_widget() is child_a
        assert selection_events[-1] == (["child_a", "child_b", "nested_group"], "child_a")
        assert feedback[-1] == "Selected 3 child widgets of container."
        children_menu.deleteLater()

        descendants_menu = panel._build_context_menu(container)
        descendants_actions = _select_menu_actions(descendants_menu)
        descendants_actions["Descendants"].trigger()
        assert panel.selected_widgets() == [child_a, child_b, nested_group, nested_leaf]
        assert panel._get_selected_widget() is child_a
        assert selection_events[-1] == (["child_a", "child_b", "nested_group", "nested_leaf"], "child_a")
        assert feedback[-1] == "Selected 4 descendant widgets of container."
        descendants_menu.deleteLater()

        subtree_menu = panel._build_context_menu(container)
        subtree_actions = _select_menu_actions(subtree_menu)
        subtree_actions["Subtree"].trigger()
        assert panel.selected_widgets() == [container, child_a, child_b, nested_group, nested_leaf]
        assert panel._get_selected_widget() is container
        assert selection_events[-1] == (["container", "child_a", "child_b", "nested_group", "nested_leaf"], "container")
        assert feedback[-1] == "Selected 5 widgets in subtree of container."
        subtree_menu.deleteLater()

        leaves_menu = panel._build_context_menu(container)
        leaves_actions = _select_menu_actions(leaves_menu)
        leaves_actions["Leaves"].trigger()
        assert panel.selected_widgets() == [child_a, child_b, nested_leaf]
        assert panel._get_selected_widget() is child_a
        assert selection_events[-1] == (["child_a", "child_b", "nested_leaf"], "child_a")
        assert feedback[-1] == "Selected 3 leaf widgets in subtree of container."
        leaves_menu.deleteLater()

        containers_menu = panel._build_context_menu(container)
        containers_actions = _select_menu_actions(containers_menu)
        containers_actions["Containers"].trigger()
        assert panel.selected_widgets() == [container, nested_group]
        assert panel._get_selected_widget() is container
        assert selection_events[-1] == (["container", "nested_group"], "container")
        assert feedback[-1] == "Selected 2 container widgets in subtree of container."
        containers_menu.deleteLater()

        siblings_menu = panel._build_context_menu(child_b)
        siblings_actions = _select_menu_actions(siblings_menu)
        siblings_actions["Siblings"].trigger()
        assert panel.selected_widgets() == [child_a, child_b, nested_group]
        assert panel._get_selected_widget() is child_b
        assert selection_events[-1] == (["child_a", "child_b", "nested_group"], "child_b")
        assert feedback[-1] == "Selected 3 widgets under container."
        siblings_menu.deleteLater()

        same_type_menu = panel._build_context_menu(child_b)
        same_type_actions = _select_menu_actions(same_type_menu)
        same_type_actions["Same Type"].trigger()
        assert panel.selected_widgets() == [child_b, same_type]
        assert panel._get_selected_widget() is child_b
        assert selection_events[-1] == (["child_b", "same_type"], "child_b")
        assert feedback[-1] == "Selected 2 button widgets."
        same_type_menu.deleteLater()
        panel.deleteLater()

    def test_context_menu_same_parent_type_action_updates_selection_and_feedback(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        first = WidgetModel("label", name="first")
        second = WidgetModel("label", name="second")
        other = WidgetModel("button", name="other")
        project, _page, root = _build_project_with_widgets(widgets=[first, second, other])

        panel = WidgetTreePanel()
        panel.set_project(project)
        selection_events = []
        feedback = []
        panel.selection_changed.connect(
            lambda widgets, primary: selection_events.append(
                ([widget.name for widget in widgets], primary.name if primary is not None else "")
            )
        )
        panel.feedback_message.connect(lambda message: feedback.append(message))

        menu = panel._build_context_menu(first)
        actions = _select_menu_actions(menu)
        actions["Same Parent Type"].trigger()
        assert panel.selected_widgets() == [first, second]
        assert panel._get_selected_widget() is first
        assert selection_events[-1] == (["first", "second"], "first")
        assert feedback[-1] == "Selected 2 sibling label widgets under root_group."
        menu.deleteLater()
        panel.deleteLater()

    def test_context_menu_same_depth_action_updates_selection_and_feedback(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        branch_a = WidgetModel("group", name="branch_a")
        branch_b = WidgetModel("group", name="branch_b")
        leaf_a = WidgetModel("label", name="leaf_a")
        leaf_b = WidgetModel("button", name="leaf_b")
        nested_group = WidgetModel("group", name="nested_group")
        branch_a.add_child(leaf_a)
        branch_a.add_child(nested_group)
        branch_b.add_child(leaf_b)
        project, _page, root = _build_project_with_widgets(widgets=[branch_a, branch_b])

        panel = WidgetTreePanel()
        panel.set_project(project)
        selection_events = []
        feedback = []
        panel.selection_changed.connect(
            lambda widgets, primary: selection_events.append(
                ([widget.name for widget in widgets], primary.name if primary is not None else "")
            )
        )
        panel.feedback_message.connect(lambda message: feedback.append(message))

        menu = panel._build_context_menu(leaf_a)
        actions = _select_menu_actions(menu)
        actions["Same Depth"].trigger()
        assert panel.selected_widgets() == [leaf_a, nested_group, leaf_b]
        assert panel._get_selected_widget() is leaf_a
        assert selection_events[-1] == (["leaf_a", "nested_group", "leaf_b"], "leaf_a")
        assert feedback[-1] == "Selected 3 widgets at depth 2."
        menu.deleteLater()
        panel.deleteLater()

    def test_context_menu_state_select_actions_update_selection_and_feedback(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        container = WidgetModel("group", name="container")
        hidden_self = WidgetModel("button", name="hidden_self")
        hidden_self.designer_hidden = True
        hidden_leaf = WidgetModel("label", name="hidden_leaf")
        hidden_leaf.designer_hidden = True
        locked_self = WidgetModel("group", name="locked_self")
        locked_self.designer_locked = True
        locked_leaf = WidgetModel("switch", name="locked_leaf")
        locked_leaf.designer_locked = True
        visible_leaf = WidgetModel("label", name="visible_leaf")
        _add_widget_children(locked_self, [locked_leaf])
        _add_widget_children(container, [hidden_self, hidden_leaf, locked_self, visible_leaf])
        project, _page, root = _build_project_with_widgets(widgets=[container])

        panel = WidgetTreePanel()
        panel.set_project(project)
        selection_events = []
        feedback = []
        panel.selection_changed.connect(
            lambda widgets, primary: selection_events.append(
                ([widget.name for widget in widgets], primary.name if primary is not None else "")
            )
        )
        panel.feedback_message.connect(lambda message: feedback.append(message))

        visible_menu = panel._build_context_menu(container)
        visible_actions = _select_menu_actions(visible_menu)
        visible_actions["Visible"].trigger()
        assert panel.selected_widgets() == [container, locked_self, locked_leaf, visible_leaf]
        assert panel._get_selected_widget() is container
        assert selection_events[-1] == (["container", "locked_self", "locked_leaf", "visible_leaf"], "container")
        assert feedback[-1] == "Selected 4 visible widgets in subtree of container."
        visible_menu.deleteLater()

        hidden_menu = panel._build_context_menu(container)
        hidden_actions = _select_menu_actions(hidden_menu)
        hidden_actions["Hidden"].trigger()
        assert panel.selected_widgets() == [hidden_self, hidden_leaf]
        assert panel._get_selected_widget() is hidden_self
        assert selection_events[-1] == (["hidden_self", "hidden_leaf"], "hidden_self")
        assert feedback[-1] == "Selected 2 hidden widgets in subtree of container."
        hidden_menu.deleteLater()

        unlocked_menu = panel._build_context_menu(container)
        unlocked_actions = _select_menu_actions(unlocked_menu)
        unlocked_actions["Unlocked"].trigger()
        assert panel.selected_widgets() == [container, hidden_self, hidden_leaf, visible_leaf]
        assert panel._get_selected_widget() is container
        assert selection_events[-1] == (["container", "hidden_self", "hidden_leaf", "visible_leaf"], "container")
        assert feedback[-1] == "Selected 4 unlocked widgets in subtree of container."
        unlocked_menu.deleteLater()

        locked_menu = panel._build_context_menu(container)
        locked_actions = _select_menu_actions(locked_menu)
        locked_actions["Locked"].trigger()
        assert panel.selected_widgets() == [locked_self, locked_leaf]
        assert panel._get_selected_widget() is locked_self
        assert selection_events[-1] == (["locked_self", "locked_leaf"], "locked_self")
        assert feedback[-1] == "Selected 2 locked widgets in subtree of container."
        locked_menu.deleteLater()
        panel.deleteLater()

    def test_context_menu_managed_select_action_updates_selection_and_feedback(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        container = WidgetModel("group", name="container")
        layout_parent = WidgetModel("linearlayout", name="layout_parent")
        managed_group = WidgetModel("group", name="managed_group")
        managed_leaf = WidgetModel("label", name="managed_leaf")
        managed_button = WidgetModel("button", name="managed_button")
        unmanaged_leaf = WidgetModel("label", name="unmanaged_leaf")
        _add_widget_children(managed_group, [managed_leaf])
        _add_widget_children(layout_parent, [managed_group, managed_button])
        _add_widget_children(container, [layout_parent, unmanaged_leaf])
        project, _page, root = _build_project_with_widgets(widgets=[container])

        panel = WidgetTreePanel()
        panel.set_project(project)
        selection_events = []
        feedback = []
        panel.selection_changed.connect(
            lambda widgets, primary: selection_events.append(
                ([widget.name for widget in widgets], primary.name if primary is not None else "")
            )
        )
        panel.feedback_message.connect(lambda message: feedback.append(message))

        layout_menu = panel._build_context_menu(container)
        layout_actions = _select_menu_actions(layout_menu)
        layout_actions["Layout Containers"].trigger()
        assert panel.selected_widgets() == [layout_parent]
        assert panel._get_selected_widget() is layout_parent
        assert selection_events[-1] == (["layout_parent"], "layout_parent")
        assert feedback[-1] == "Selected 1 layout container widget in subtree of container."
        layout_menu.deleteLater()

        layout_parent_menu = panel._build_context_menu(layout_parent)
        layout_parent_actions = _select_menu_actions(layout_parent_menu)
        layout_parent_actions["Layout Containers"].trigger()
        assert panel.selected_widgets() == [layout_parent]
        assert panel._get_selected_widget() is layout_parent
        assert selection_events[-1] == (["layout_parent"], "layout_parent")
        assert feedback[-1] == "Selected 1 layout container widget in subtree of layout_parent."
        layout_parent_menu.deleteLater()

        container_menu = panel._build_context_menu(container)
        container_actions = _select_menu_actions(container_menu)
        container_actions["Managed"].trigger()
        assert panel.selected_widgets() == [managed_group, managed_button]
        assert panel._get_selected_widget() is managed_group
        assert selection_events[-1] == (["managed_group", "managed_button"], "managed_group")
        assert feedback[-1] == "Selected 2 layout-managed widgets in subtree of container."
        container_menu.deleteLater()

        managed_menu = panel._build_context_menu(managed_button)
        managed_actions = _select_menu_actions(managed_menu)
        managed_actions["Managed"].trigger()
        assert panel.selected_widgets() == [managed_button]
        assert panel._get_selected_widget() is managed_button
        assert selection_events[-1] == (["managed_button"], "managed_button")
        assert feedback[-1] == "Selected 1 layout-managed widget in subtree of managed_button."
        managed_menu.deleteLater()

        free_menu = panel._build_context_menu(container)
        free_actions = _select_menu_actions(free_menu)
        free_actions["Free Position"].trigger()
        assert panel.selected_widgets() == [container, layout_parent, managed_leaf, unmanaged_leaf]
        assert panel._get_selected_widget() is container
        assert selection_events[-1] == (["container", "layout_parent", "managed_leaf", "unmanaged_leaf"], "container")
        assert feedback[-1] == "Selected 4 free-position widgets in subtree of container."
        free_menu.deleteLater()

        free_leaf_menu = panel._build_context_menu(managed_leaf)
        free_leaf_actions = _select_menu_actions(free_leaf_menu)
        free_leaf_actions["Free Position"].trigger()
        assert panel.selected_widgets() == [managed_leaf]
        assert panel._get_selected_widget() is managed_leaf
        assert selection_events[-1] == (["managed_leaf"], "managed_leaf")
        assert feedback[-1] == "Selected 1 free-position widget in subtree of managed_leaf."
        free_leaf_menu.deleteLater()
        panel.deleteLater()

    def test_context_menu_structure_actions_disable_root_and_noop_move_into(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        child = WidgetModel("label", name="child")
        project, _page, root = _build_project_with_widgets(widgets=[child])

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
        assert root_structure_action.statusTip() == root_structure_action.toolTip()

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
        assert child_structure_action.statusTip() == child_structure_action.toolTip()

        child_menu.deleteLater()
        panel.deleteLater()

    def test_structure_buttons_reflect_selection_state(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        first = WidgetModel("label", name="first")
        second = WidgetModel("button", name="second")
        target = WidgetModel("group", name="target")
        nested = WidgetModel("switch", name="nested")
        target.add_child(nested)
        project, _page, root = _build_project_with_widgets(widgets=[first, second, target])

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
        assert panel.into_btn.popupMode() == QToolButton.DelayedPopup
        assert panel.lift_btn.isEnabled() is False
        assert panel.up_btn.isEnabled() is False
        assert panel.down_btn.isEnabled() is False
        assert panel.top_btn.isEnabled() is False
        assert panel.bottom_btn.isEnabled() is False
        assert panel.structure_hint_label.text() == "Structure: root widgets cannot be regrouped or reordered."
        assert "Unavailable: root widgets cannot be regrouped or reordered." in panel.group_btn.toolTip()

        panel.deleteLater()

    def test_structure_hint_reports_locked_and_invalid_selection(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        locked = WidgetModel("label", name="locked")
        locked.designer_locked = True
        project, _page, root = _build_project_with_widgets(widgets=[locked])

        panel = WidgetTreePanel()
        panel.set_project(project)
        panel.set_selected_widgets([locked], primary=locked)

        assert panel.structure_hint_label.text() == "Structure: locked widgets cannot be moved or regrouped."

        panel.deleteLater()

    def test_structure_hint_reports_isolated_widget_without_move_targets(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        child = WidgetModel("label", name="child")
        project, _page, root = _build_project_with_widgets(widgets=[child])

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

        first = WidgetModel("label", name="first")
        second = WidgetModel("label", name="second")
        third = WidgetModel("label", name="third")
        fourth = WidgetModel("label", name="fourth")
        project, _page, root = _build_project_with_widgets(widgets=[first, second, third, fourth])

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

        target = WidgetModel("group", name="target", x=80, y=20, width=100, height=100)
        child = WidgetModel("label", name="child", x=10, y=15, width=20, height=10)
        project, _page, root = _build_project_with_widgets(widgets=[target, child])

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

        container = WidgetModel("group", name="container")
        child = WidgetModel("label", name="child")
        tail = WidgetModel("label", name="tail")
        _add_widget_children(container, [child])
        project, _page, root = _build_project_with_widgets(widgets=[container, tail])

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

        first = WidgetModel("label", name="first")
        locked = WidgetModel("label", name="locked")
        locked.designer_locked = True
        project, _page, root = _build_project_with_widgets(widgets=[first, locked])

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

        first = WidgetModel("label", name="first")
        project, _page, root = _build_project_with_widgets(widgets=[first])

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

        source = WidgetModel("label", name="source")
        target = WidgetModel("group", name="target")
        sibling = WidgetModel("label", name="sibling")
        project, _page, root = _build_project_with_widgets(widgets=[source, target, sibling])

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

        first = WidgetModel("label", name="first")
        project, _page, root = _build_project_with_widgets(widgets=[first])

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

        first = WidgetModel("label", name="first")
        second = WidgetModel("group", name="second")
        third = WidgetModel("label", name="third")
        project, _page, root = _build_project_with_widgets(widgets=[first, second, third])

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

        source = WidgetModel("label", name="source")
        container = WidgetModel("group", name="container")
        nested = WidgetModel("group", name="nested")
        deep_child = WidgetModel("label", name="deep_child")
        _add_widget_children(nested, [deep_child])
        _add_widget_children(container, [nested])
        project, _page, root = _build_project_with_widgets(widgets=[source, container])

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

        source = WidgetModel("label", name="source")
        sibling = WidgetModel("label", name="sibling")
        container = WidgetModel("group", name="container")
        child = WidgetModel("label", name="child")
        _add_widget_children(container, [child])
        project, _page, root = _build_project_with_widgets(widgets=[source, sibling, container])

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

        first = WidgetModel("label", name="first")
        second = WidgetModel("button", name="second")
        project, _page, root = _build_project_with_widgets(widgets=[first, second])

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
        insert_action = next(action for action in menu.actions() if action.text() == "Insert Component...")
        delete_action = next(action for action in menu.actions() if action.text() == "Delete")

        assert rename_action.shortcut().toString() == "F2"
        assert rename_action.toolTip() == "Batch rename 2 selected widgets (F2)."
        assert rename_action.statusTip() == rename_action.toolTip()
        assert insert_action.toolTip() == "Open the Components panel to insert a component into root_group (group)."
        assert insert_action.statusTip() == insert_action.toolTip()
        assert delete_action.shortcut().toString() == "Del"
        assert delete_action.toolTip() == "Delete first (Del)."
        assert delete_action.statusTip() == delete_action.toolTip()

        menu.deleteLater()
        panel.deleteLater()

    def test_tree_panel_exposes_initial_accessibility_metadata(self, qapp):
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, root = _build_project_with_root()

        panel = WidgetTreePanel()
        panel.set_project(project)
        header_layout = panel._header_frame.layout()
        title_row = header_layout.itemAt(1).layout()
        metrics_layout = panel._metrics_frame.layout()
        drag_hint_layout = panel._drag_hint_frame.layout()
        drag_margins = drag_hint_layout.contentsMargins()
        header_margins = header_layout.contentsMargins()

        assert panel.accessibleName() == (
            "Widget tree: 1 widget. 0 selected widgets. Current widget: none. "
            "Filter: none. Status: All widgets. Position: none. "
            "Structure: select widgets to group, move, or reorder."
        )
        assert panel.layout().spacing() == 2
        assert (header_margins.left(), header_margins.top(), header_margins.right(), header_margins.bottom()) == (2, 2, 2, 2)
        assert header_layout.spacing() == 2
        assert title_row.spacing() == 2
        assert metrics_layout.spacing() == 2
        assert (drag_margins.left(), drag_margins.top(), drag_margins.right(), drag_margins.bottom()) == (2, 2, 2, 2)
        assert panel.add_btn.toolTip() == "Open the Components panel to insert a component into root_group (group)."
        assert panel.add_btn.statusTip() == panel.add_btn.toolTip()
        assert panel.add_btn.accessibleName() == "Insert component target: root_group (group)"
        assert panel.add_btn.icon().isNull()
        assert panel.rename_btn.toolTip() == "Rename the current selection (F2)\nUnavailable: select at least 1 widget."
        assert panel.rename_btn.statusTip() == panel.rename_btn.toolTip()
        assert panel.rename_btn.accessibleName() == "Rename selected widget unavailable"
        assert panel.rename_btn.icon().isNull()
        assert panel.del_btn.toolTip() == "Delete the current selection (Del)\nUnavailable: select at least 1 widget."
        assert panel.del_btn.statusTip() == panel.del_btn.toolTip()
        assert panel.del_btn.accessibleName() == "Delete selected widget unavailable"
        assert panel.del_btn.icon().isNull()
        assert panel.expand_btn.toolTip() == "Expand all widgets in the tree."
        assert panel.expand_btn.statusTip() == panel.expand_btn.toolTip()
        assert panel.expand_btn.accessibleName() == "Expand all widget tree items"
        assert panel.expand_btn.icon().isNull()
        assert panel.collapse_btn.toolTip() == "Collapse all widgets in the tree."
        assert panel.collapse_btn.statusTip() == panel.collapse_btn.toolTip()
        assert panel.collapse_btn.accessibleName() == "Collapse all widget tree items"
        assert panel.collapse_btn.icon().isNull()
        assert panel.structure_actions_btn.toolTip() == (
            "Open structure actions for grouping, moving, and tree visibility."
        )
        assert panel.structure_actions_btn.statusTip() == panel.structure_actions_btn.toolTip()
        assert panel.structure_actions_btn.accessibleName() == "Open structure actions"
        assert panel.structure_actions_btn.icon().isNull()
        assert panel.add_btn.text() == "Add"
        assert panel.structure_actions_btn.text() == "More"
        assert panel.structure_hint_label.isHidden() is True
        assert panel._primary_actions_label.isHidden() is True
        assert panel._selection_toolbar_label.isHidden() is True
        assert panel._drag_hint_label.isHidden() is True
        assert panel._filter_label.isHidden() is True
        assert panel.tree.columnCount() == 1
        assert panel.tree.headerItem().text(0) == "Structure"
        assert panel.tree.indentation() == 24
        assert [action.text() for action in panel.structure_actions_btn.menu().actions() if action.text()] == [
            "Group Selection",
            "Ungroup",
            "Move Into...",
            "Lift To Parent",
            "Move Up",
            "Move Down",
            "Move To Top",
            "Move To Bottom",
            "Expand All",
            "Collapse All",
        ]
        assert panel.filter_edit.placeholderText() == "Filter"
        assert panel.filter_edit.toolTip() == "Filter widgets by name or type. Current filter: none."
        assert panel._filter_hint_label.isHidden() is True
        assert panel._filter_hint_label.accessibleName() == panel._filter_hint_label.text()
        assert panel.filter_prev_btn.toolTip() == "Type a widget filter to navigate previous matches."
        assert panel.filter_next_btn.toolTip() == "Type a widget filter to navigate next matches."
        assert panel.filter_select_btn.toolTip() == "Type a widget filter to select matching widgets."
        assert panel.filter_select_btn.text() == "All"
        assert panel.filter_prev_btn.accessibleName() == "Previous widget filter match unavailable"
        assert panel.filter_next_btn.accessibleName() == "Next widget filter match unavailable"
        assert panel.filter_select_btn.accessibleName() == "Select widget filter matches unavailable"
        assert panel.tree.accessibleName() == "Widget tree: 1 widget. 0 selected widgets. Current widget: none."
        assert panel.tree.topLevelItem(0).toolTip(0) == f"Widget {root.name}. Type: {root.widget_type}. State: default."
        assert panel.tree.topLevelItem(0).data(0, Qt.AccessibleTextRole) == panel.tree.topLevelItem(0).toolTip(0)
        panel.deleteLater()

    def test_tree_panel_filter_accessibility_updates_with_matches_and_selection(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        first = WidgetModel("label", name="field_label")
        second = WidgetModel("button", name="field_button")
        project, _page, root = _build_project_with_widgets(widgets=[first, second])

        panel = WidgetTreePanel()
        panel.set_project(project)
        panel.filter_edit.setText("field")

        assert panel.filter_edit.accessibleName() == "Widget filter: field"
        assert panel.filter_prev_btn.toolTip() == "Select the previous widget filter match (Shift+Enter)."
        assert panel.filter_next_btn.toolTip() == "Select the next widget filter match (Enter)."
        assert panel.filter_select_btn.toolTip() == "Select all current filter matches (Ctrl+Enter)."
        assert panel.filter_prev_btn.accessibleName() == "Previous widget filter match: 2 matches. Current position 0/2."
        assert panel.filter_next_btn.accessibleName() == "Next widget filter match: 2 matches. Current position 0/2."
        assert panel.filter_select_btn.accessibleName() == "Select 2 widget filter matches"
        assert panel.filter_status_label.accessibleName() == "Widget filter status: 2 matches"
        assert "Filter: field. Status: 2 matches. Position: 0/2." in panel.accessibleName()

        panel.set_selected_widgets([second], primary=second)

        assert panel.add_btn.accessibleName() == "Insert component target: root_group (group)"
        assert panel.rename_btn.toolTip() == "Rename field_button (F2)."
        assert panel.rename_btn.accessibleName() == "Rename selected widget: field_button"
        assert panel.del_btn.toolTip() == "Delete field_button (Del)."
        assert panel.del_btn.accessibleName() == "Delete selected widget: field_button"
        assert panel.group_btn.icon().isNull()
        assert panel.ungroup_btn.icon().isNull()
        assert panel.into_btn.icon().isNull()
        assert panel.lift_btn.icon().isNull()
        assert panel.up_btn.icon().isNull()
        assert panel.down_btn.icon().isNull()
        assert panel.top_btn.icon().isNull()
        assert panel.bottom_btn.icon().isNull()
        assert panel.filter_position_label.accessibleName() == "Widget filter position: 2/2"
        assert panel.filter_prev_btn.accessibleName() == "Previous widget filter match: 2 matches. Current position 2/2."
        assert panel.filter_next_btn.accessibleName() == "Next widget filter match: 2 matches. Current position 2/2."
        assert panel.tree.accessibleName() == "Widget tree: 3 widgets. 1 selected widget. Current widget: field_button."
        assert "Current widget: field_button." in panel.accessibleName()
        panel.deleteLater()

    def test_tree_panel_drag_target_metadata_updates_with_structure_state(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        first = WidgetModel("label", name="first")
        second = WidgetModel("button", name="second")
        target = WidgetModel("group", name="target")
        project, _page, root = _build_project_with_widgets(widgets=[first, second, target])

        panel = WidgetTreePanel()
        panel.set_project(project)
        panel.set_selected_widgets([first, second], primary=first)

        assert panel.structure_hint_label.accessibleName() == panel.structure_hint_label.text()

        panel._set_drag_target_label("Drop target: move into target.", tone="valid")

        assert panel.drag_target_label.accessibleName() == "Drop target: move into target."
        assert "Drop target: move into target." in panel.accessibleName()
        panel.deleteLater()

    def test_set_selected_widgets_reveals_primary_item_path(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        container = WidgetModel("group", name="container")
        nested = WidgetModel("group", name="nested")
        target = WidgetModel("label", name="target")
        _add_widget_children(nested, [target])
        _add_widget_children(container, [nested])
        project, _page, root = _build_project_with_widgets(widgets=[container])

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

        container = WidgetModel("group", name="container")
        target = WidgetModel("label", name="target_label")
        other = WidgetModel("button", name="other_button")
        _add_widget_children(container, [target])
        project, _page, root = _build_project_with_widgets(widgets=[container, other])

        panel = WidgetTreePanel()
        panel.set_project(project)

        panel.filter_edit.setText("target")

        assert panel._item_map[id(root)].isHidden() is False
        assert panel._item_map[id(container)].isHidden() is False
        assert panel._item_map[id(target)].isHidden() is False
        assert panel._item_map[id(container)].isExpanded() is True
        assert panel._item_map[id(container)].font(0).weight() == QFont.DemiBold
        assert panel._item_map[id(target)].font(0).weight() == QFont.Bold
        assert panel._item_map[id(other)].isHidden() is True
        assert panel.filter_position_label.text() == "0/1"
        assert panel.filter_status_label.text() == "1 match"

        panel.rebuild_tree()

        assert panel._item_map[id(root)].isHidden() is False
        assert panel._item_map[id(container)].isHidden() is False
        assert panel._item_map[id(target)].isHidden() is False
        assert panel._item_map[id(other)].isHidden() is True
        assert panel._item_map[id(container)].font(0).weight() == QFont.DemiBold
        assert panel._item_map[id(target)].font(0).weight() == QFont.Bold
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

        label = WidgetModel("label", name="headline")
        button = WidgetModel("button", name="cta")
        project, _page, root = _build_project_with_widgets(widgets=[label, button])

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

        label = WidgetModel("label", name="headline")
        button = WidgetModel("button", name="cta")
        project, _page, root = _build_project_with_widgets(widgets=[label, button])

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
        assert panel.filter_select_btn.isEnabled() is False
        panel.deleteLater()

    def test_filter_text_change_emits_feedback_message(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        project, _page, root = _build_project_with_widgets(
            widgets=[
                WidgetModel("label", name="field_label"),
                WidgetModel("button", name="field_button"),
            ]
        )

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

        first = WidgetModel("label", name="field_label")
        second = WidgetModel("button", name="field_button")
        third = WidgetModel("switch", name="status")
        project, _page, root = _build_project_with_widgets(widgets=[first, second, third])

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

        first = WidgetModel("label", name="field_label")
        second = WidgetModel("button", name="field_button")
        project, _page, root = _build_project_with_widgets(widgets=[first, second])

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

    def test_filter_select_button_selects_all_matches_and_emits_feedback(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        first = WidgetModel("label", name="field_label")
        second = WidgetModel("button", name="field_button")
        third = WidgetModel("switch", name="status")
        project, _page, root = _build_project_with_widgets(widgets=[first, second, third])

        panel = WidgetTreePanel()
        panel.set_project(project)
        selection_events = []
        feedback = []
        panel.selection_changed.connect(
            lambda widgets, primary: selection_events.append(
                ([widget.name for widget in widgets], primary.name if primary is not None else "")
            )
        )
        panel.feedback_message.connect(lambda message: feedback.append(message))

        panel.filter_edit.setText("field")
        panel.set_selected_widgets([second], primary=second)
        selection_events.clear()
        feedback.clear()

        panel.filter_select_btn.click()

        assert panel.filter_select_btn.isEnabled() is True
        assert panel.selected_widgets() == [first, second]
        assert panel._get_selected_widget() is second
        assert panel.filter_position_label.text() == "2/2"
        assert selection_events == [(["field_label", "field_button"], "field_button")]
        assert feedback == ["Widget filter 'field': selected 2 matches."]
        panel.deleteLater()

    def test_filter_edit_keyboard_shortcuts_navigate_matches(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        first = WidgetModel("label", name="field_label")
        second = WidgetModel("button", name="field_button")
        project, _page, root = _build_project_with_widgets(widgets=[first, second])

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

    def test_filter_edit_ctrl_enter_selects_all_matches(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        first = WidgetModel("label", name="field_label")
        second = WidgetModel("button", name="field_button")
        third = WidgetModel("switch", name="status")
        project, _page, root = _build_project_with_widgets(widgets=[first, second, third])

        panel = WidgetTreePanel()
        panel.set_project(project)
        panel.filter_edit.setText("field")

        qapp.sendEvent(panel.filter_edit, QKeyEvent(QEvent.KeyPress, Qt.Key_Return, Qt.ControlModifier))

        assert panel.selected_widgets() == [first, second]
        assert panel._get_selected_widget() is first
        assert panel.filter_position_label.text() == "1/2"
        panel.deleteLater()

    def test_filter_edit_escape_clears_active_filter(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        label = WidgetModel("label", name="headline")
        button = WidgetModel("button", name="cta")
        project, _page, root = _build_project_with_widgets(widgets=[label, button])

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

        first = WidgetModel("label", name="field_label")
        second = WidgetModel("button", name="field_button")
        project, _page, root = _build_project_with_widgets(widgets=[first, second])

        panel = WidgetTreePanel()
        panel.set_project(project)
        panel.filter_edit.setText("field")

        panel.set_selected_widgets([second], primary=second)

        assert panel.filter_position_label.text() == "2/2"
        panel.deleteLater()

    def test_rebuild_tree_preserves_manual_collapse_state(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.widget_tree import WidgetTreePanel

        container = WidgetModel("group", name="container")
        nested = WidgetModel("group", name="nested")
        _add_widget_children(nested, [WidgetModel("label", name="target")])
        _add_widget_children(container, [nested])
        project, _page, root = _build_project_with_widgets(widgets=[container])

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

        container = WidgetModel("group", name="container")
        nested = WidgetModel("group", name="nested")
        target = WidgetModel("label", name="target")
        _add_widget_children(nested, [target])
        _add_widget_children(container, [nested])
        project, _page, root = _build_project_with_widgets(widgets=[container])

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

        container = WidgetModel("group", name="container")
        nested = WidgetModel("group", name="nested")
        _add_widget_children(nested, [WidgetModel("label", name="target")])
        _add_widget_children(container, [nested])
        project, _page, root = _build_project_with_widgets(widgets=[container])

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

        container = WidgetModel("group", name="container")
        nested = WidgetModel("group", name="nested")
        _add_widget_children(nested, [WidgetModel("label", name="target")])
        _add_widget_children(container, [nested])
        project, _page, root = _build_project_with_widgets(widgets=[container])

        panel = WidgetTreePanel()
        panel.set_project(project)

        panel._collapse_all_items()
        panel.rebuild_tree()

        assert panel._item_map[id(root)].isExpanded() is False
        assert panel._item_map[id(container)].isExpanded() is False
        assert panel._item_map[id(nested)].isExpanded() is False
        panel.deleteLater()
