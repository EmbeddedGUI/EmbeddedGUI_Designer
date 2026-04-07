"""Widget tree panel for EmbeddedGUI Designer."""

import re

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem, QFrame,
    QPushButton, QToolButton, QHBoxLayout, QMenu, QAction, QInputDialog, QAbstractItemView, QMessageBox, QLineEdit, QLabel,
)
from PyQt5.QtCore import pyqtSignal, Qt, QItemSelectionModel, QEvent, QTimer
from PyQt5.QtGui import QColor, QBrush, QFont

from ..model.config import get_config
from ..model.widget_name import (
    is_valid_widget_name,
    make_unique_widget_name,
    resolve_widget_name,
    sanitize_widget_name,
)
from ..model.structure_ops import (
    available_move_targets,
    can_move_widgets_to_parent_index,
    describe_structure_actions,
    group_selection,
    lift_to_parent,
    move_into_container,
    move_selection_by_step,
    move_selection_to_edge,
    move_widgets_to_parent_index,
    ungroup_selection,
    validate_move_widgets_to_parent_index,
)
from ..model.widget_model import WidgetModel
from ..model.widget_registry import WidgetRegistry
from .iconography import make_icon, widget_icon_key


def _set_widget_metadata(widget, *, tooltip=None, accessible_name=None):
    if tooltip is not None:
        hint = str(tooltip or "")
        if str(widget.property("_widget_tree_hint_snapshot") or "") != hint:
            widget.setToolTip(hint)
            widget.setStatusTip(hint)
            widget.setProperty("_widget_tree_hint_snapshot", hint)
    if accessible_name is not None:
        name = str(accessible_name or "")
        if str(widget.property("_widget_tree_accessible_snapshot") or "") != name:
            widget.setAccessibleName(name)
            widget.setProperty("_widget_tree_accessible_snapshot", name)


def _set_action_metadata(action, *, tooltip=None, whats_this=None):
    if tooltip is not None:
        action.setToolTip(tooltip)
        action.setStatusTip(tooltip)
    if whats_this is not None:
        action.setWhatsThis(whats_this)


def _count_label(count, singular, plural=None):
    value = max(int(count or 0), 0)
    noun = singular if value == 1 else (plural or f"{singular}s")
    return f"{value} {noun}"


def _get_addable_types():
    """Get addable widget types from the registry."""
    return WidgetRegistry.instance().addable_types()


def _get_container_types():
    """Get container widget types from the registry."""
    return WidgetRegistry.instance().container_types()


class _StructureTreeWidget(QTreeWidget):
    def __init__(
        self,
        drop_handler=None,
        can_drop_handler=None,
        key_handler=None,
        drag_hover_handler=None,
        clear_drag_hover_handler=None,
        parent=None,
    ):
        super().__init__(parent)
        self._drop_handler = drop_handler
        self._can_drop_handler = can_drop_handler
        self._key_handler = key_handler
        self._drag_hover_handler = drag_hover_handler
        self._clear_drag_hover_handler = clear_drag_hover_handler
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setDragDropMode(QAbstractItemView.DragDrop)

    def set_drop_handler(self, drop_handler):
        self._drop_handler = drop_handler

    def set_can_drop_handler(self, can_drop_handler):
        self._can_drop_handler = can_drop_handler

    def set_key_handler(self, key_handler):
        self._key_handler = key_handler

    def set_drag_hover_handler(self, drag_hover_handler):
        self._drag_hover_handler = drag_hover_handler

    def set_clear_drag_hover_handler(self, clear_drag_hover_handler):
        self._clear_drag_hover_handler = clear_drag_hover_handler

    def dragEnterEvent(self, event):
        if event.source() is self and self.selectedItems():
            event.acceptProposedAction()
            return
        event.ignore()

    def dragMoveEvent(self, event):
        if event.source() is self and self.selectedItems():
            target_item = self.itemAt(event.pos())
            if self._drag_hover_handler is not None:
                self._drag_hover_handler(target_item, int(self.dropIndicatorPosition()))
            if self._can_drop_handler is not None and not self._can_drop_handler(
                target_item, int(self.dropIndicatorPosition())
            ):
                event.ignore()
                return
            event.acceptProposedAction()
            return
        event.ignore()

    def dropEvent(self, event):
        if event.source() is not self or self._drop_handler is None:
            event.ignore()
            return
        target_item = self.itemAt(event.pos())
        if self._clear_drag_hover_handler is not None:
            self._clear_drag_hover_handler()
        handled = bool(self._drop_handler(target_item, int(self.dropIndicatorPosition())))
        if handled:
            event.acceptProposedAction()
            return
        event.ignore()

    def dragLeaveEvent(self, event):
        if self._clear_drag_hover_handler is not None:
            self._clear_drag_hover_handler()
        super().dragLeaveEvent(event)

    def keyPressEvent(self, event):
        if self._key_handler is not None and self._key_handler(event):
            event.accept()
            return
        super().keyPressEvent(event)


class WidgetTreePanel(QWidget):
    """Tree view showing the widget hierarchy."""

    widget_selected = pyqtSignal(object)  # emits WidgetModel or None
    selection_changed = pyqtSignal(list, object)  # widgets, primary
    tree_changed = pyqtSignal(str)  # emits change source when tree structure changes
    feedback_message = pyqtSignal(str)  # emits user-facing status messages
    browse_widgets_requested = pyqtSignal(object)  # preferred parent widget or None

    _DRAG_TARGET_LABEL_STYLES = {
        "default": "color: #666666;",
        "valid": "color: #0b5cab; font-weight: 600;",
        "invalid": "color: #a1260d; font-weight: 600;",
    }
    _MAX_RECENT_MOVE_TARGETS = 5

    def __init__(self, parent=None):
        super().__init__(parent)
        self._config = get_config()
        self.project = None
        self._widget_map = {}  # QTreeWidgetItem -> WidgetModel
        self._item_map = {}  # widget id -> QTreeWidgetItem
        self._building = False
        self._syncing_selection = False
        self._expanded_widgets = set()
        self._suppress_expansion_tracking = False
        self._default_expand_next_rebuild = True
        self._filter_matches = []
        self._drag_hover_item = None
        self._drag_hover_position = None
        self._drag_target_item = None
        self._remembered_move_target_labels = {}
        self._drag_hover_expand_timer = QTimer(self)
        self._drag_hover_expand_timer.setSingleShot(True)
        self._drag_hover_expand_timer.setInterval(350)
        self._drag_hover_expand_timer.timeout.connect(self._expand_drag_hover_item)
        self._init_ui()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.StyleChange, QEvent.FontChange, QEvent.PaletteChange):
            self.refresh_tree_typography()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self._header_frame = QFrame()
        self._header_frame.setObjectName("workspace_panel_header")
        self._header_frame.setProperty("panelTone", "structure")
        header_layout = QVBoxLayout(self._header_frame)
        header_layout.setContentsMargins(2, 2, 2, 2)
        header_layout.setSpacing(2)

        self._header_eyebrow = QLabel("Widget Map")
        self._header_eyebrow.setObjectName("structure_header_eyebrow")
        header_layout.addWidget(self._header_eyebrow)
        self._header_eyebrow.hide()

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(2)
        self._title_label = QLabel("Structure")
        self._title_label.setObjectName("workspace_section_title")
        title_row.addWidget(self._title_label)
        title_row.addStretch()
        self._selection_summary_chip = QLabel("No selection")
        self._selection_summary_chip.setObjectName("workspace_status_chip")
        self._selection_summary_chip.setProperty("chipTone", "accent")
        title_row.addWidget(self._selection_summary_chip)
        self._selection_summary_chip.hide()
        header_layout.addLayout(title_row)

        self._header_meta_label = QLabel(
            "Plan hierarchy, inspect selection state, and execute grouping or reorder operations without leaving the tree."
        )
        self._header_meta_label.setObjectName("structure_header_meta")
        self._header_meta_label.setWordWrap(True)
        header_layout.addWidget(self._header_meta_label)
        self._header_meta_label.hide()

        self._metrics_frame = QFrame()
        self._metrics_frame.setObjectName("structure_metrics_strip")
        metrics_layout = QHBoxLayout(self._metrics_frame)
        metrics_layout.setContentsMargins(0, 0, 0, 0)
        metrics_layout.setSpacing(2)
        self._tree_count_chip = self._make_status_chip("0 widgets", "accent")
        self._filter_summary_chip = self._make_status_chip("All widgets")
        metrics_layout.addWidget(self._tree_count_chip)
        metrics_layout.addWidget(self._filter_summary_chip)
        metrics_layout.addStretch()
        header_layout.addWidget(self._metrics_frame)
        self._metrics_frame.hide()

        self.add_btn = QPushButton("Add")
        self.add_btn.setToolTip("Open the widget browser for the current insert target.")
        self.add_btn.clicked.connect(self._on_add_clicked)
        self.rename_btn = QPushButton("Rename")
        self.rename_btn.setToolTip("Rename the current selection (F2)")
        self.rename_btn.clicked.connect(self._on_rename_clicked)
        self.del_btn = QPushButton("Delete")
        self.del_btn.setToolTip("Delete the current selection (Del)")
        self.del_btn.clicked.connect(self._on_delete_clicked)
        self.structure_actions_btn = QToolButton()
        self.structure_actions_btn.setText("More")
        self.structure_actions_btn.setPopupMode(QToolButton.InstantPopup)
        self._structure_actions_menu = QMenu(self)
        self._structure_actions_menu.setToolTipsVisible(True)
        self.structure_actions_btn.setMenu(self._structure_actions_menu)
        self.expand_btn = QPushButton("Expand")
        self.expand_btn.clicked.connect(self._expand_all_items)
        self.collapse_btn = QPushButton("Collapse")
        self.collapse_btn.clicked.connect(self._collapse_all_items)

        self._structure_base_hint_text = "Select widgets to inspect hierarchy, batch-edit grouping, and reorder layout."
        self.structure_hint_label = QLabel(self._structure_base_hint_text)
        self.structure_hint_label.setWordWrap(True)
        self.structure_hint_label.setObjectName("workspace_section_subtitle")
        self.structure_hint_label.hide()

        self._primary_actions_frame = QFrame()
        self._primary_actions_frame.setObjectName("structure_primary_strip")
        primary_actions_layout = QVBoxLayout(self._primary_actions_frame)
        primary_actions_layout.setContentsMargins(0, 0, 0, 0)
        primary_actions_layout.setSpacing(2)
        self._primary_actions_label = QLabel("Selection and Structure")
        self._primary_actions_label.setObjectName("structure_panel_label")
        primary_actions_layout.addWidget(self._primary_actions_label)
        self._primary_actions_label.hide()
        primary_actions_layout.addWidget(self.structure_hint_label)

        primary_row = QHBoxLayout()
        primary_row.setContentsMargins(0, 0, 0, 0)
        primary_row.setSpacing(2)
        primary_row.addWidget(self.add_btn)
        primary_row.addWidget(self.structure_actions_btn)
        primary_row.addStretch()
        primary_actions_layout.addLayout(primary_row)
        header_layout.addWidget(self._primary_actions_frame)

        self.group_btn = QPushButton("Group")
        self.group_btn.setToolTip("Group the current selection (Ctrl+G)")
        self.group_btn.clicked.connect(self._group_selected_widgets)
        self.ungroup_btn = QPushButton("Ungroup")
        self.ungroup_btn.setToolTip("Ungroup the selected group widgets (Ctrl+Shift+G)")
        self.ungroup_btn.clicked.connect(self._ungroup_selected_widgets)
        self.into_btn = QToolButton()
        self.into_btn.setText("Into")
        self.into_btn.setToolTip("Move the current selection into another container (Ctrl+Shift+I)")
        self.into_btn.clicked.connect(self._move_selected_widgets_into)
        self._into_quick_menu = QMenu(self)
        self._into_quick_menu.setToolTipsVisible(True)
        self.into_btn.setPopupMode(QToolButton.MenuButtonPopup)
        self.into_btn.setMenu(self._into_quick_menu)
        self.lift_btn = QPushButton("Lift")
        self.lift_btn.setToolTip("Lift the current selection to the parent container (Ctrl+Shift+L)")
        self.lift_btn.clicked.connect(self._lift_selected_widgets)
        self.up_btn = QPushButton("Up")
        self.up_btn.setToolTip("Move the current selection up among its siblings (Alt+Up)")
        self.up_btn.clicked.connect(self._move_selected_widgets_up)
        self.down_btn = QPushButton("Down")
        self.down_btn.setToolTip("Move the current selection down among its siblings (Alt+Down)")
        self.down_btn.clicked.connect(self._move_selected_widgets_down)
        self.top_btn = QPushButton("Top")
        self.top_btn.setToolTip("Move the current selection to the top of its sibling list (Alt+Shift+Up)")
        self.top_btn.clicked.connect(self._move_selected_widgets_to_top)
        self.bottom_btn = QPushButton("Bottom")
        self.bottom_btn.setToolTip("Move the current selection to the bottom of its sibling list (Alt+Shift+Down)")
        self.bottom_btn.clicked.connect(self._move_selected_widgets_to_bottom)
        self._structure_button_tooltips = {
            self.group_btn: ("Group the current selection (Ctrl+G)", "group_reason"),
            self.ungroup_btn: ("Ungroup the selected group widgets (Ctrl+Shift+G)", "ungroup_reason"),
            self.into_btn: ("Move the current selection into another container (Ctrl+Shift+I)", "move_into_reason"),
            self.lift_btn: ("Lift the current selection to the parent container (Ctrl+Shift+L)", "lift_reason"),
            self.up_btn: ("Move the current selection up among its siblings (Alt+Up)", "move_up_reason"),
            self.down_btn: ("Move the current selection down among its siblings (Alt+Down)", "move_down_reason"),
            self.top_btn: ("Move the current selection to the top of its sibling list (Alt+Shift+Up)", "move_top_reason"),
            self.bottom_btn: ("Move the current selection to the bottom of its sibling list (Alt+Shift+Down)", "move_bottom_reason"),
        }
        for button in (
            self.group_btn,
            self.ungroup_btn,
            self.into_btn,
            self.lift_btn,
            self.up_btn,
            self.down_btn,
            self.top_btn,
            self.bottom_btn,
        ):
            button.hide()
        self.expand_btn.hide()
        self.collapse_btn.hide()

        self._selection_toolbar = QFrame()
        self._selection_toolbar.setObjectName("structure_selection_strip")
        selection_layout = QVBoxLayout(self._selection_toolbar)
        selection_layout.setContentsMargins(0, 0, 0, 0)
        selection_layout.setSpacing(2)
        self._selection_toolbar_label = QLabel("Quick Edit")
        self._selection_toolbar_label.setObjectName("structure_panel_label")
        selection_layout.addWidget(self._selection_toolbar_label)
        self._selection_toolbar_label.hide()
        selection_row = QHBoxLayout()
        selection_row.setContentsMargins(0, 0, 0, 0)
        selection_row.setSpacing(2)
        for button in (
            self.rename_btn,
            self.del_btn,
            self.group_btn,
            self.ungroup_btn,
            self.into_btn,
            self.lift_btn,
            self.up_btn,
            self.down_btn,
        ):
            selection_row.addWidget(button)
        selection_row.addStretch()
        selection_layout.addLayout(selection_row)
        self._selection_toolbar.hide()
        header_layout.addWidget(self._selection_toolbar)

        self.drag_target_label = QLabel(self._default_drag_target_text())
        self.drag_target_label.setWordWrap(True)
        self._set_drag_target_label(self._default_drag_target_text(), tone="default")
        self.drag_target_label.hide()

        self._drag_hint_frame = QFrame()
        self._drag_hint_frame.setObjectName("structure_drag_hint_strip")
        drag_hint_layout = QVBoxLayout(self._drag_hint_frame)
        drag_hint_layout.setContentsMargins(2, 2, 2, 2)
        drag_hint_layout.setSpacing(2)
        self._drag_hint_label = QLabel("Drag Preview")
        self._drag_hint_label.setObjectName("structure_panel_label")
        drag_hint_layout.addWidget(self._drag_hint_label)
        self._drag_hint_label.hide()
        drag_hint_layout.addWidget(self.drag_target_label)
        self._drag_hint_frame.hide()
        header_layout.addWidget(self._drag_hint_frame)

        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Filter")
        self.filter_edit.setClearButtonEnabled(True)
        self.filter_edit.textChanged.connect(self._on_filter_text_changed)
        self.filter_edit.installEventFilter(self)

        self._filter_frame = QFrame()
        self._filter_frame.setObjectName("structure_filter_bar")
        filter_frame_layout = QVBoxLayout(self._filter_frame)
        filter_frame_layout.setContentsMargins(0, 0, 0, 0)
        filter_frame_layout.setSpacing(2)
        self._filter_label = QLabel("Find Widgets")
        self._filter_label.setObjectName("structure_panel_label")
        filter_frame_layout.addWidget(self._filter_label)
        self._filter_label.hide()
        self._filter_hint_label = QLabel("Filter by widget name or type, then jump between matches or select them in one pass.")
        self._filter_hint_label.setObjectName("structure_panel_hint")
        self._filter_hint_label.setWordWrap(True)
        filter_frame_layout.addWidget(self._filter_hint_label)
        _set_widget_metadata(
            self._filter_hint_label,
            tooltip=self._filter_hint_label.text(),
            accessible_name=self._filter_hint_label.text(),
        )
        self._filter_hint_label.hide()

        filter_layout = QHBoxLayout()
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.setSpacing(2)
        filter_layout.addWidget(self.filter_edit, 1)
        self.filter_prev_btn = QPushButton("Prev")
        self.filter_prev_btn.clicked.connect(self._select_previous_filter_match)
        self.filter_next_btn = QPushButton("Next")
        self.filter_next_btn.clicked.connect(self._select_next_filter_match)
        self.filter_select_btn = QPushButton("All")
        self.filter_select_btn.setToolTip("Select all current filter matches (Ctrl+Enter)")
        self.filter_select_btn.clicked.connect(self._select_all_filter_matches)
        self.filter_prev_btn.setEnabled(False)
        self.filter_next_btn.setEnabled(False)
        self.filter_select_btn.setEnabled(False)
        filter_layout.addWidget(self.filter_prev_btn)
        filter_layout.addWidget(self.filter_next_btn)
        filter_layout.addWidget(self.filter_select_btn)
        self.filter_position_label = self._make_status_chip("", "accent")
        self.filter_position_label.hide()
        filter_layout.addWidget(self.filter_position_label)
        self.filter_status_label = self._make_status_chip("All widgets")
        filter_layout.addWidget(self.filter_status_label)
        filter_frame_layout.addLayout(filter_layout)
        header_layout.addWidget(self._filter_frame)
        layout.addWidget(self._header_frame)

        # Tree
        self.tree = _StructureTreeWidget(
            drop_handler=self._handle_tree_drop,
            can_drop_handler=self._can_handle_tree_drop,
            key_handler=self._handle_tree_key_press,
            drag_hover_handler=self._on_tree_drag_hover,
            clear_drag_hover_handler=self._clear_tree_drag_hover,
            parent=self,
        )
        self.tree.setObjectName("widget_tree_panel_tree")
        self.tree.setColumnCount(1)
        self.tree.setHeaderLabels(["Structure"])
        self.tree.header().setStretchLastSection(True)
        self.tree.header().hide()
        self.tree.setIndentation(24)
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_context_menu)
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)
        self.tree.itemExpanded.connect(self._on_item_expanded)
        self.tree.itemCollapsed.connect(self._on_item_collapsed)
        layout.addWidget(self.tree)
        self.add_btn.setAccessibleName("Insert component")
        self.rename_btn.setAccessibleName("Rename selected widget")
        self.del_btn.setAccessibleName("Delete selected widget")
        self.structure_actions_btn.setAccessibleName("Open structure actions")
        self.expand_btn.setAccessibleName("Expand widget tree")
        self.collapse_btn.setAccessibleName("Collapse widget tree")
        self.group_btn.setAccessibleName("Group selected widgets")
        self.ungroup_btn.setAccessibleName("Ungroup selected widgets")
        self.into_btn.setAccessibleName("Move selected widgets into container")
        self.lift_btn.setAccessibleName("Lift selected widgets to parent")
        self.up_btn.setAccessibleName("Move selected widgets up")
        self.down_btn.setAccessibleName("Move selected widgets down")
        self.top_btn.setAccessibleName("Move selected widgets to top")
        self.bottom_btn.setAccessibleName("Move selected widgets to bottom")
        self.filter_edit.setAccessibleName("Widget filter")
        self.filter_prev_btn.setAccessibleName("Previous widget filter match")
        self.filter_next_btn.setAccessibleName("Next widget filter match")
        self.filter_select_btn.setAccessibleName("Select widget filter matches")
        self.tree.setAccessibleName("Widget tree")
        _set_widget_metadata(
            self.expand_btn,
            tooltip="Expand all widgets in the tree.",
            accessible_name="Expand all widget tree items",
        )
        _set_widget_metadata(
            self.collapse_btn,
            tooltip="Collapse all widgets in the tree.",
            accessible_name="Collapse all widget tree items",
        )
        _set_widget_metadata(
            self.structure_actions_btn,
            tooltip="Open structure actions for grouping, moving, and reordering widgets.",
            accessible_name="Open structure actions",
        )
        self._update_structure_controls()
        self._update_filter_accessibility()
        self._update_accessibility_summary()

    def set_project(self, project):
        self.project = project
        self._clear_tree_drag_hover()
        self._expanded_widgets = set()
        self._default_expand_next_rebuild = True
        self.rebuild_tree()

    def rebuild_tree(self):
        self._clear_tree_drag_hover()
        self._expanded_widgets = self._collect_expanded_widget_ids()
        default_expand = self._default_expand_next_rebuild
        self._default_expand_next_rebuild = False
        self._building = True
        self.tree.clear()
        self._widget_map = {}
        self._item_map = {}
        if self.project:
            for root_widget in self.project.root_widgets:
                self._add_widget_to_tree(root_widget, None)
        self._building = False
        self._apply_tree_filter(default_expand=default_expand)
        self._update_structure_controls()

    def shutdown(self):
        self._filter_matches = []
        self._clear_tree_drag_hover()
        self._suppress_expansion_tracking = True
        try:
            self.filter_edit.removeEventFilter(self)
        except Exception:
            pass
        for signal, handler in (
            (self.filter_edit.textChanged, self._on_filter_text_changed),
            (self.tree.itemSelectionChanged, self._on_selection_changed),
            (self.tree.itemExpanded, self._on_item_expanded),
            (self.tree.itemCollapsed, self._on_item_collapsed),
        ):
            try:
                signal.disconnect(handler)
            except Exception:
                pass
        self.filter_edit.blockSignals(True)
        self.tree.blockSignals(True)
        self.blockSignals(True)

    def _add_widget_to_tree(self, widget, parent_item):
        item = QTreeWidgetItem()
        item.setText(0, self._display_name(widget))
        item.setIcon(0, make_icon(widget_icon_key(widget.widget_type), size=18))
        item_tooltip = self._tree_item_tooltip(widget)
        item.setToolTip(0, item_tooltip)
        item.setStatusTip(0, item_tooltip)
        item.setData(0, Qt.AccessibleTextRole, item_tooltip)
        self._widget_map[id(item)] = widget
        self._item_map[id(widget)] = item

        if parent_item is None:
            self.tree.addTopLevelItem(item)
        else:
            parent_item.addChild(item)

        for child in widget.children:
            self._add_widget_to_tree(child, item)

        return item

    def _display_name(self, widget):
        base = f"{widget.name} · {widget.widget_type}"
        states = self._widget_state_tags(widget)
        if states:
            return f"{base} [{', '.join(states)}]"
        return base

    def _widget_state_summary(self, widget):
        parts = [widget.widget_type]
        if getattr(widget, "designer_locked", False):
            parts.append("locked")
        if getattr(widget, "designer_hidden", False):
            parts.append("hidden")
        if widget.parent is not None and self._parent_has_layout(widget):
            parts.append("managed")
        return " | ".join(parts)

    def _widget_state_tags(self, widget):
        tags = []
        if getattr(widget, "designer_locked", False):
            tags.append("locked")
        if getattr(widget, "designer_hidden", False):
            tags.append("hidden")
        if widget.parent is not None and self._parent_has_layout(widget):
            tags.append("managed")
        return tags

    def _tree_item_tooltip(self, widget):
        state_tags = self._widget_state_tags(widget)
        state_text = f"State: {', '.join(state_tags)}." if state_tags else "State: default."
        return f"Widget {self._widget_label(widget)}. Type: {widget.widget_type}. {state_text}"

    def _parent_has_layout(self, widget):
        parent = getattr(widget, "parent", None)
        if parent is None:
            return False
        type_info = WidgetRegistry.instance().get(parent.widget_type)
        return type_info.get("layout_func") is not None

    def eventFilter(self, watched, event):
        if watched is self.filter_edit and event.type() == QEvent.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                if event.modifiers() & Qt.ControlModifier:
                    self._select_all_filter_matches()
                elif event.modifiers() & Qt.ShiftModifier:
                    self._select_previous_filter_match()
                else:
                    self._select_next_filter_match()
                return True
            if event.key() == Qt.Key_Escape and self.filter_edit.text():
                self.filter_edit.clear()
                return True
        return super().eventFilter(watched, event)

    def _on_filter_text_changed(self, _text):
        self._apply_tree_filter(announce=True)

    def _on_selection_changed(self):
        if self._building or self._syncing_selection:
            return
        self._clear_tree_drag_hover()
        widgets = self.selected_widgets()
        primary = self._widget_map.get(id(self.tree.currentItem())) if self.tree.currentItem() else None
        if primary is None and widgets:
            primary = widgets[-1]
        self._update_filter_position_label()
        self._update_structure_controls()
        self.widget_selected.emit(primary)
        self.selection_changed.emit(widgets, primary)

    def _get_selected_widget(self):
        item = self.tree.currentItem()
        if item is None:
            return None
        return self._widget_map.get(id(item))

    def selected_widgets(self):
        widgets = []
        for item in self.tree.selectedItems():
            widget = self._widget_map.get(id(item))
            if widget is not None:
                widgets.append(widget)
        return widgets

    def _widget_label(self, widget):
        if widget is None:
            return ""
        return getattr(widget, "name", "") or getattr(widget, "widget_type", "widget")

    def _make_status_chip(self, text, tone=None):
        chip = QLabel(text)
        chip.setObjectName("workspace_status_chip")
        if tone:
            chip.setProperty("chipTone", tone)
        return chip

    def _set_status_chip_state(self, chip, text, tone=None):
        if chip is None:
            return
        chip.setText(text)
        chip.setProperty("chipTone", tone)
        chip.style().unpolish(chip)
        chip.style().polish(chip)
        chip.update()

    def _update_header_context(self):
        if not hasattr(self, "_tree_count_chip"):
            return

        widget_total = len(self._item_map)
        selected_total = len(self.selected_widgets()) if hasattr(self, "tree") else 0
        filter_query = self.filter_edit.text().strip() if hasattr(self, "filter_edit") else ""
        filter_status = self.filter_status_label.text().strip() if hasattr(self, "filter_status_label") else "All widgets"
        filter_position = self.filter_position_label.text().strip() if hasattr(self, "filter_position_label") else ""

        self._set_status_chip_state(
            self._tree_count_chip,
            _count_label(widget_total, "widget"),
            "accent" if widget_total else "warning",
        )

        if not filter_query:
            filter_summary = "All widgets"
            filter_tone = None
        elif filter_status == "No matches":
            filter_summary = "No matches"
            filter_tone = "warning"
        else:
            filter_summary = filter_status
            filter_tone = "success"
        self._set_status_chip_state(self._filter_summary_chip, filter_summary, filter_tone)
        self._set_status_chip_state(self.filter_status_label, filter_status or "All widgets", filter_tone)

        selection_chip_text = self._selection_summary_chip.text().strip() if hasattr(self, "_selection_summary_chip") else "No selection"
        selection_summary = (
            "Selection summary: no selection."
            if selection_chip_text == "No selection"
            else f"Selection summary: {selection_chip_text}."
        )
        metrics_summary = f"Structure metrics: {_count_label(widget_total, 'widget')}. Filter status: {filter_summary}."
        if filter_position:
            metrics_summary = f"{metrics_summary} Match position: {filter_position}."

        _set_widget_metadata(
            self._header_eyebrow,
            tooltip="Structure navigation workspace surface.",
            accessible_name="Structure navigation workspace surface.",
        )
        _set_widget_metadata(
            self._selection_summary_chip,
            tooltip=selection_summary,
            accessible_name=selection_summary,
        )
        _set_widget_metadata(
            self._tree_count_chip,
            tooltip=f"Widget count: {_count_label(widget_total, 'widget')}.",
            accessible_name=f"Widget count: {_count_label(widget_total, 'widget')}.",
        )
        _set_widget_metadata(
            self._filter_summary_chip,
            tooltip=f"Filter summary: {filter_summary}.",
            accessible_name=f"Filter summary: {filter_summary}.",
        )
        _set_widget_metadata(
            self._metrics_frame,
            tooltip=metrics_summary,
            accessible_name=metrics_summary,
        )

        if filter_position:
            self._set_status_chip_state(self.filter_position_label, filter_position, "accent")
            self.filter_position_label.show()
        else:
            self.filter_position_label.hide()

        if hasattr(self, "_header_meta_label"):
            if self.project is None:
                meta = "Open a page to inspect hierarchy, selection state, and structure actions."
            elif selected_total > 1:
                meta = (
                    f"Working with {_count_label(widget_total, 'widget')} and "
                    f"{_count_label(selected_total, 'selected widget')} in the current tree."
                )
            elif selected_total == 1:
                current_widget = self._widget_label(self._get_selected_widget()) or "widget"
                meta = (
                    f"Working with {_count_label(widget_total, 'widget')}. "
                    f"Focused widget: {current_widget}."
                )
            else:
                meta = f"Working with {_count_label(widget_total, 'widget')} in the current tree."
            self._header_meta_label.setText(meta)

    def _apply_programmatic_selection(self, widgets, primary=None, feedback_message=""):
        widgets = [widget for widget in (widgets or []) if widget is not None]
        if primary not in widgets:
            primary = widgets[0] if widgets else None
        self.set_selected_widgets(widgets, primary=primary)
        self.widget_selected.emit(primary)
        self.selection_changed.emit(widgets, primary)
        if feedback_message:
            self.feedback_message.emit(feedback_message)

    def _select_parent_widget(self, widget):
        parent = widget.parent if widget is not None else None
        if parent is None:
            if widget is not None:
                self.feedback_message.emit("Cannot select parent: root widgets do not have a parent.")
            return
        self._apply_programmatic_selection(
            [parent],
            primary=parent,
            feedback_message=f"Selected parent widget: {self._widget_label(parent)}.",
        )

    def _previous_sibling_widget(self, widget):
        siblings = self._sibling_widgets(widget)
        if widget not in siblings:
            return None
        index = siblings.index(widget)
        if index <= 0:
            return None
        return siblings[index - 1]

    def _next_sibling_widget(self, widget):
        siblings = self._sibling_widgets(widget)
        if widget not in siblings:
            return None
        index = siblings.index(widget)
        if index < 0 or index >= len(siblings) - 1:
            return None
        return siblings[index + 1]

    def _previous_sibling_widgets(self, widget):
        siblings = self._sibling_widgets(widget)
        if widget not in siblings:
            return []
        index = siblings.index(widget)
        if index <= 0:
            return []
        return siblings[:index]

    def _next_sibling_widgets(self, widget):
        siblings = self._sibling_widgets(widget)
        if widget not in siblings:
            return []
        index = siblings.index(widget)
        if index < 0 or index >= len(siblings) - 1:
            return []
        return siblings[index + 1:]

    def _first_child_widget(self, widget):
        children = [child for child in getattr(widget, "children", []) if child is not None]
        if not children:
            return None
        return children[0]

    def _last_child_widget(self, widget):
        children = [child for child in getattr(widget, "children", []) if child is not None]
        if not children:
            return None
        return children[-1]

    def _previous_tree_widget(self, widget):
        root = self._root_widget(widget)
        if root is None:
            return None
        tree_widgets = [current for current in root.get_all_widgets_flat() if current is not None]
        if widget not in tree_widgets:
            return None
        index = tree_widgets.index(widget)
        if index <= 0:
            return None
        return tree_widgets[index - 1]

    def _next_tree_widget(self, widget):
        root = self._root_widget(widget)
        if root is None:
            return None
        tree_widgets = [current for current in root.get_all_widgets_flat() if current is not None]
        if widget not in tree_widgets:
            return None
        index = tree_widgets.index(widget)
        if index < 0 or index >= len(tree_widgets) - 1:
            return None
        return tree_widgets[index + 1]

    def _select_previous_sibling_widget(self, widget):
        sibling = self._previous_sibling_widget(widget)
        if sibling is None:
            if widget is not None:
                if widget.parent is None:
                    self.feedback_message.emit("Cannot select previous sibling: root widgets do not have siblings.")
                else:
                    self.feedback_message.emit(
                        "Cannot select previous sibling: widget does not have a previous sibling under the same parent."
                    )
            return
        self._apply_programmatic_selection(
            [sibling],
            primary=sibling,
            feedback_message=f"Selected previous sibling: {self._widget_label(sibling)}.",
        )

    def _select_next_sibling_widget(self, widget):
        sibling = self._next_sibling_widget(widget)
        if sibling is None:
            if widget is not None:
                if widget.parent is None:
                    self.feedback_message.emit("Cannot select next sibling: root widgets do not have siblings.")
                else:
                    self.feedback_message.emit(
                        "Cannot select next sibling: widget does not have a next sibling under the same parent."
                    )
            return
        self._apply_programmatic_selection(
            [sibling],
            primary=sibling,
            feedback_message=f"Selected next sibling: {self._widget_label(sibling)}.",
        )

    def _select_previous_sibling_widgets(self, widget):
        siblings = self._previous_sibling_widgets(widget)
        if not siblings:
            if widget is not None:
                if widget.parent is None:
                    self.feedback_message.emit("Cannot select previous siblings: root widgets do not have siblings.")
                else:
                    self.feedback_message.emit(
                        "Cannot select previous siblings: widget does not have any previous siblings under the same parent."
                    )
            return
        noun = "widget" if len(siblings) == 1 else "widgets"
        self._apply_programmatic_selection(
            siblings,
            primary=siblings[-1],
            feedback_message=f"Selected {len(siblings)} previous sibling {noun} before {self._widget_label(widget)}.",
        )

    def _select_next_sibling_widgets(self, widget):
        siblings = self._next_sibling_widgets(widget)
        if not siblings:
            if widget is not None:
                if widget.parent is None:
                    self.feedback_message.emit("Cannot select next siblings: root widgets do not have siblings.")
                else:
                    self.feedback_message.emit(
                        "Cannot select next siblings: widget does not have any next siblings under the same parent."
                    )
            return
        noun = "widget" if len(siblings) == 1 else "widgets"
        self._apply_programmatic_selection(
            siblings,
            primary=siblings[0],
            feedback_message=f"Selected {len(siblings)} next sibling {noun} after {self._widget_label(widget)}.",
        )

    def _select_first_child_widget(self, widget):
        child = self._first_child_widget(widget)
        if child is None:
            if widget is not None:
                self.feedback_message.emit("Cannot select first child: widget has no child widgets.")
            return
        self._apply_programmatic_selection(
            [child],
            primary=child,
            feedback_message=f"Selected first child: {self._widget_label(child)}.",
        )

    def _select_last_child_widget(self, widget):
        child = self._last_child_widget(widget)
        if child is None:
            if widget is not None:
                self.feedback_message.emit("Cannot select last child: widget has no child widgets.")
            return
        self._apply_programmatic_selection(
            [child],
            primary=child,
            feedback_message=f"Selected last child: {self._widget_label(child)}.",
        )

    def _select_previous_tree_widget(self, widget):
        previous_widget = self._previous_tree_widget(widget)
        if previous_widget is None:
            if widget is not None:
                self.feedback_message.emit(
                    "Cannot select previous in tree: widget is already the first widget in tree order on this page."
                )
            return
        self._apply_programmatic_selection(
            [previous_widget],
            primary=previous_widget,
            feedback_message=f"Selected previous widget in tree order: {self._widget_label(previous_widget)}.",
        )

    def _select_next_tree_widget(self, widget):
        next_widget = self._next_tree_widget(widget)
        if next_widget is None:
            if widget is not None:
                self.feedback_message.emit(
                    "Cannot select next in tree: widget is already the last widget in tree order on this page."
                )
            return
        self._apply_programmatic_selection(
            [next_widget],
            primary=next_widget,
            feedback_message=f"Selected next widget in tree order: {self._widget_label(next_widget)}.",
        )

    def _ancestor_widgets(self, widget):
        if widget is None:
            return []
        ancestors = []
        current = widget.parent
        while current is not None:
            ancestors.append(current)
            current = current.parent
        return list(reversed(ancestors))

    def _root_widget(self, widget):
        if widget is None:
            return None
        current = widget
        while current.parent is not None:
            current = current.parent
        return current

    def _widget_path(self, widget):
        if widget is None:
            return []
        return self._ancestor_widgets(widget) + [widget]

    def _top_level_widgets(self, widget):
        root = self._root_widget(widget)
        if root is None:
            return []
        return [child for child in getattr(root, "children", []) if child is not None]

    def _top_level_ancestor(self, widget):
        path_widgets = self._widget_path(widget)
        if len(path_widgets) >= 2:
            return path_widgets[1]
        if len(path_widgets) == 1:
            return path_widgets[0]
        return None

    def _select_ancestor_widgets(self, widget):
        ancestors = self._ancestor_widgets(widget)
        if not ancestors:
            if widget is not None:
                self.feedback_message.emit("Cannot select ancestors: root widgets do not have ancestors.")
            return
        noun = "widget" if len(ancestors) == 1 else "widgets"
        self._apply_programmatic_selection(
            ancestors,
            primary=widget.parent if widget is not None else None,
            feedback_message=f"Selected {len(ancestors)} ancestor {noun} of {self._widget_label(widget)}.",
        )

    def _select_root_widget(self, widget):
        root = self._root_widget(widget)
        if root is None or root is widget:
            if widget is not None:
                self.feedback_message.emit("Cannot select root: widget is already the page root.")
            return
        self._apply_programmatic_selection(
            [root],
            primary=root,
            feedback_message=f"Selected page root: {self._widget_label(root)}.",
        )

    def _select_widget_path(self, widget):
        path_widgets = self._widget_path(widget)
        if not path_widgets:
            return
        noun = "widget" if len(path_widgets) == 1 else "widgets"
        self._apply_programmatic_selection(
            path_widgets,
            primary=widget,
            feedback_message=f"Selected {len(path_widgets)} {noun} in path to {self._widget_label(widget)}.",
        )

    def _select_top_level_widgets(self, widget):
        top_level_widgets = self._top_level_widgets(widget)
        if not top_level_widgets:
            if widget is not None:
                self.feedback_message.emit("Cannot select top-level widgets: page root has no child widgets.")
            return
        noun = "widget" if len(top_level_widgets) == 1 else "widgets"
        primary = self._top_level_ancestor(widget)
        if primary not in top_level_widgets:
            primary = top_level_widgets[0]
        self._apply_programmatic_selection(
            top_level_widgets,
            primary=primary,
            feedback_message=f"Selected {len(top_level_widgets)} top-level {noun} on this page.",
        )

    def _select_child_widgets(self, widget):
        children = [child for child in getattr(widget, "children", []) if child is not None]
        if not children:
            if widget is not None:
                self.feedback_message.emit("Cannot select children: widget has no child widgets.")
            return
        noun = "widget" if len(children) == 1 else "widgets"
        self._apply_programmatic_selection(
            children,
            primary=children[0],
            feedback_message=f"Selected {len(children)} child {noun} of {self._widget_label(widget)}.",
        )

    def _descendant_widgets(self, widget):
        if widget is None:
            return []
        return [child for child in widget.get_all_widgets_flat()[1:] if child is not None]

    def _select_descendant_widgets(self, widget):
        descendants = self._descendant_widgets(widget)
        if not descendants:
            if widget is not None:
                self.feedback_message.emit("Cannot select descendants: widget has no descendant widgets.")
            return
        noun = "widget" if len(descendants) == 1 else "widgets"
        self._apply_programmatic_selection(
            descendants,
            primary=descendants[0],
            feedback_message=f"Selected {len(descendants)} descendant {noun} of {self._widget_label(widget)}.",
        )

    def _subtree_widgets(self, widget):
        if widget is None:
            return []
        descendants = self._descendant_widgets(widget)
        if not descendants:
            return []
        return [widget] + descendants

    def _select_subtree_widgets(self, widget):
        subtree = self._subtree_widgets(widget)
        if not subtree:
            if widget is not None:
                self.feedback_message.emit("Cannot select subtree: widget has no descendant widgets.")
            return
        noun = "widget" if len(subtree) == 1 else "widgets"
        self._apply_programmatic_selection(
            subtree,
            primary=widget,
            feedback_message=f"Selected {len(subtree)} {noun} in subtree of {self._widget_label(widget)}.",
        )

    def _leaf_descendant_widgets(self, widget):
        return [
            current
            for current in self._descendant_widgets(widget)
            if not getattr(current, "children", [])
        ]

    def _select_leaf_descendant_widgets(self, widget):
        leaves = self._leaf_descendant_widgets(widget)
        if not leaves:
            if widget is not None:
                self.feedback_message.emit("Cannot select leaves: widget has no leaf descendants.")
            return
        noun = "widget" if len(leaves) == 1 else "widgets"
        self._apply_programmatic_selection(
            leaves,
            primary=leaves[0],
            feedback_message=f"Selected {len(leaves)} leaf {noun} in subtree of {self._widget_label(widget)}.",
        )

    def _container_subtree_widgets(self, widget):
        if widget is None:
            return []
        subtree = [widget] + self._descendant_widgets(widget)
        return [
            current
            for current in subtree
            if current is not None and getattr(current, "is_container", False)
        ]

    def _select_container_subtree_widgets(self, widget):
        containers = self._container_subtree_widgets(widget)
        if len(containers) <= 1:
            if widget is not None:
                self.feedback_message.emit("Cannot select containers: no other container widgets exist in this subtree.")
            return
        noun = "widget" if len(containers) == 1 else "widgets"
        primary = widget if widget in containers else containers[0]
        self._apply_programmatic_selection(
            containers,
            primary=primary,
            feedback_message=f"Selected {len(containers)} container {noun} in subtree of {self._widget_label(widget)}.",
        )

    def _widgets_including_self(self, widget):
        if widget is None:
            return []
        return [widget] + self._descendant_widgets(widget)

    def _widget_parent_uses_layout(self, widget):
        parent = widget.parent if widget is not None else None
        if parent is None:
            return False
        return WidgetModel._get_type_info(parent.widget_type).get("layout_func") is not None

    def _widget_uses_layout(self, widget):
        if widget is None:
            return False
        return WidgetModel._get_type_info(widget.widget_type).get("layout_func") is not None

    def _hidden_subtree_widgets(self, widget):
        return [
            current
            for current in self._widgets_including_self(widget)
            if getattr(current, "designer_hidden", False)
        ]

    def _layout_container_subtree_widgets(self, widget):
        return [
            current
            for current in self._widgets_including_self(widget)
            if self._widget_uses_layout(current)
        ]

    def _visible_subtree_widgets(self, widget):
        return [
            current
            for current in self._widgets_including_self(widget)
            if not getattr(current, "designer_hidden", False)
        ]

    def _managed_subtree_widgets(self, widget):
        return [
            current
            for current in self._widgets_including_self(widget)
            if self._widget_parent_uses_layout(current)
        ]

    def _unlocked_subtree_widgets(self, widget):
        return [
            current
            for current in self._widgets_including_self(widget)
            if not getattr(current, "designer_locked", False)
        ]

    def _free_position_subtree_widgets(self, widget):
        return [
            current
            for current in self._widgets_including_self(widget)
            if current.parent is not None and not self._widget_parent_uses_layout(current)
        ]

    def _select_hidden_subtree_widgets(self, widget):
        hidden_widgets = self._hidden_subtree_widgets(widget)
        if not hidden_widgets:
            if widget is not None:
                self.feedback_message.emit("Cannot select hidden widgets: no hidden widgets exist in this subtree.")
            return
        noun = "widget" if len(hidden_widgets) == 1 else "widgets"
        primary = widget if widget in hidden_widgets else hidden_widgets[0]
        self._apply_programmatic_selection(
            hidden_widgets,
            primary=primary,
            feedback_message=f"Selected {len(hidden_widgets)} hidden {noun} in subtree of {self._widget_label(widget)}.",
        )

    def _select_visible_subtree_widgets(self, widget):
        visible_widgets = self._visible_subtree_widgets(widget)
        if not visible_widgets:
            if widget is not None:
                self.feedback_message.emit("Cannot select visible widgets: no visible widgets exist in this subtree.")
            return
        noun = "widget" if len(visible_widgets) == 1 else "widgets"
        primary = widget if widget in visible_widgets else visible_widgets[0]
        self._apply_programmatic_selection(
            visible_widgets,
            primary=primary,
            feedback_message=f"Selected {len(visible_widgets)} visible {noun} in subtree of {self._widget_label(widget)}.",
        )

    def _locked_subtree_widgets(self, widget):
        return [
            current
            for current in self._widgets_including_self(widget)
            if getattr(current, "designer_locked", False)
        ]

    def _select_locked_subtree_widgets(self, widget):
        locked_widgets = self._locked_subtree_widgets(widget)
        if not locked_widgets:
            if widget is not None:
                self.feedback_message.emit("Cannot select locked widgets: no locked widgets exist in this subtree.")
            return
        noun = "widget" if len(locked_widgets) == 1 else "widgets"
        primary = widget if widget in locked_widgets else locked_widgets[0]
        self._apply_programmatic_selection(
            locked_widgets,
            primary=primary,
            feedback_message=f"Selected {len(locked_widgets)} locked {noun} in subtree of {self._widget_label(widget)}.",
        )

    def _select_unlocked_subtree_widgets(self, widget):
        unlocked_widgets = self._unlocked_subtree_widgets(widget)
        if not unlocked_widgets:
            if widget is not None:
                self.feedback_message.emit("Cannot select unlocked widgets: no unlocked widgets exist in this subtree.")
            return
        noun = "widget" if len(unlocked_widgets) == 1 else "widgets"
        primary = widget if widget in unlocked_widgets else unlocked_widgets[0]
        self._apply_programmatic_selection(
            unlocked_widgets,
            primary=primary,
            feedback_message=f"Selected {len(unlocked_widgets)} unlocked {noun} in subtree of {self._widget_label(widget)}.",
        )

    def _select_layout_container_subtree_widgets(self, widget):
        layout_containers = self._layout_container_subtree_widgets(widget)
        if not layout_containers:
            if widget is not None:
                self.feedback_message.emit(
                    "Cannot select layout containers: no layout container widgets exist in this subtree."
                )
            return
        noun = "widget" if len(layout_containers) == 1 else "widgets"
        primary = widget if widget in layout_containers else layout_containers[0]
        self._apply_programmatic_selection(
            layout_containers,
            primary=primary,
            feedback_message=(
                f"Selected {len(layout_containers)} layout container {noun} "
                f"in subtree of {self._widget_label(widget)}."
            ),
        )

    def _select_managed_subtree_widgets(self, widget):
        managed_widgets = self._managed_subtree_widgets(widget)
        if not managed_widgets:
            if widget is not None:
                self.feedback_message.emit(
                    "Cannot select layout-managed widgets: no layout-managed widgets exist in this subtree."
                )
            return
        noun = "widget" if len(managed_widgets) == 1 else "widgets"
        primary = widget if widget in managed_widgets else managed_widgets[0]
        self._apply_programmatic_selection(
            managed_widgets,
            primary=primary,
            feedback_message=(
                f"Selected {len(managed_widgets)} layout-managed {noun} "
                f"in subtree of {self._widget_label(widget)}."
            ),
        )

    def _select_free_position_subtree_widgets(self, widget):
        free_widgets = self._free_position_subtree_widgets(widget)
        if not free_widgets:
            if widget is not None:
                self.feedback_message.emit(
                    "Cannot select free-position widgets: no free-position widgets exist in this subtree."
                )
            return
        noun = "widget" if len(free_widgets) == 1 else "widgets"
        primary = widget if widget in free_widgets else free_widgets[0]
        self._apply_programmatic_selection(
            free_widgets,
            primary=primary,
            feedback_message=(
                f"Selected {len(free_widgets)} free-position {noun} "
                f"in subtree of {self._widget_label(widget)}."
            ),
        )

    def _sibling_widgets(self, widget):
        parent = widget.parent if widget is not None else None
        if parent is None:
            return []
        return [child for child in getattr(parent, "children", []) if child is not None]

    def _select_sibling_widgets(self, widget):
        siblings = self._sibling_widgets(widget)
        if len(siblings) <= 1:
            if widget is not None:
                if widget.parent is None:
                    self.feedback_message.emit("Cannot select siblings: root widgets do not have siblings.")
                else:
                    self.feedback_message.emit("Cannot select siblings: widget has no siblings under the same parent.")
            return
        parent = widget.parent
        noun = "widget" if len(siblings) == 1 else "widgets"
        primary = widget if widget in siblings else siblings[0]
        self._apply_programmatic_selection(
            siblings,
            primary=primary,
            feedback_message=f"Selected {len(siblings)} {noun} under {self._widget_label(parent)}.",
        )

    def _same_parent_type_widgets(self, widget):
        siblings = self._sibling_widgets(widget)
        if not siblings or widget is None:
            return []
        widget_type = getattr(widget, "widget_type", "")
        return [
            current
            for current in siblings
            if current is not None and getattr(current, "widget_type", "") == widget_type
        ]

    def _select_same_parent_type_widgets(self, widget):
        matches = self._same_parent_type_widgets(widget)
        if len(matches) <= 1:
            if widget is not None:
                widget_type = getattr(widget, "widget_type", "widget")
                if widget.parent is None:
                    self.feedback_message.emit("Cannot select same parent type: root widgets do not have siblings.")
                else:
                    self.feedback_message.emit(
                        f"Cannot select same parent type: no other {widget_type} widgets exist under the same parent."
                    )
            return
        widget_type = getattr(widget, "widget_type", "widget")
        noun = "widget" if len(matches) == 1 else "widgets"
        parent = widget.parent
        self._apply_programmatic_selection(
            matches,
            primary=widget if widget in matches else matches[0],
            feedback_message=f"Selected {len(matches)} sibling {widget_type} {noun} under {self._widget_label(parent)}.",
        )

    def _same_subtree_type_widgets(self, widget):
        if widget is None:
            return []
        widget_type = getattr(widget, "widget_type", "")
        return [
            current
            for current in self._widgets_including_self(widget)
            if current is not None and getattr(current, "widget_type", "") == widget_type
        ]

    def _select_same_subtree_type_widgets(self, widget):
        matches = self._same_subtree_type_widgets(widget)
        if len(matches) <= 1:
            if widget is not None:
                widget_type = getattr(widget, "widget_type", "widget")
                self.feedback_message.emit(
                    f"Cannot select subtree type: no other {widget_type} widgets exist in this subtree."
                )
            return
        widget_type = getattr(widget, "widget_type", "widget")
        noun = "widget" if len(matches) == 1 else "widgets"
        self._apply_programmatic_selection(
            matches,
            primary=widget if widget in matches else matches[0],
            feedback_message=f"Selected {len(matches)} {widget_type} {noun} in subtree of {self._widget_label(widget)}.",
        )

    def _same_type_widgets(self, widget):
        if widget is None:
            return []
        widget_type = getattr(widget, "widget_type", "")
        return [
            current
            for current in self._iter_widgets() or []
            if current is not None and getattr(current, "widget_type", "") == widget_type
        ]

    def _widget_depth(self, widget):
        depth = 0
        current = widget
        while current is not None and current.parent is not None:
            depth += 1
            current = current.parent
        return depth

    def _same_depth_widgets(self, widget):
        if widget is None:
            return []
        depth = self._widget_depth(widget)
        return [
            current
            for current in self._iter_widgets() or []
            if current is not None and self._widget_depth(current) == depth
        ]

    def _select_same_type_widgets(self, widget):
        matches = self._same_type_widgets(widget)
        if len(matches) <= 1:
            if widget is not None:
                widget_type = getattr(widget, "widget_type", "widget")
                self.feedback_message.emit(
                    f"Cannot select same type: no other {widget_type} widgets exist on this page."
                )
            return
        widget_type = getattr(widget, "widget_type", "widget")
        noun = "widget" if len(matches) == 1 else "widgets"
        self._apply_programmatic_selection(
            matches,
            primary=widget if widget in matches else matches[0],
            feedback_message=f"Selected {len(matches)} {widget_type} {noun}.",
        )

    def _select_same_depth_widgets(self, widget):
        matches = self._same_depth_widgets(widget)
        if len(matches) <= 1:
            if widget is not None:
                depth = self._widget_depth(widget)
                self.feedback_message.emit(
                    f"Cannot select same depth: no other widgets exist at depth {depth} on this page."
                )
            return
        depth = self._widget_depth(widget)
        noun = "widget" if len(matches) == 1 else "widgets"
        self._apply_programmatic_selection(
            matches,
            primary=widget if widget in matches else matches[0],
            feedback_message=f"Selected {len(matches)} {noun} at depth {depth}.",
        )

    def _populate_select_menu(self, select_menu, widget):
        if select_menu is None or widget is None:
            return

        select_menu.setToolTipsVisible(True)
        child_widgets = [child for child in getattr(widget, "children", []) if child is not None]
        descendant_widgets = self._descendant_widgets(widget)
        subtree_widgets = self._subtree_widgets(widget)
        leaf_descendant_widgets = self._leaf_descendant_widgets(widget)
        container_subtree_widgets = self._container_subtree_widgets(widget)
        visible_subtree_widgets = self._visible_subtree_widgets(widget)
        hidden_subtree_widgets = self._hidden_subtree_widgets(widget)
        unlocked_subtree_widgets = self._unlocked_subtree_widgets(widget)
        locked_subtree_widgets = self._locked_subtree_widgets(widget)
        layout_container_subtree_widgets = self._layout_container_subtree_widgets(widget)
        managed_subtree_widgets = self._managed_subtree_widgets(widget)
        free_position_subtree_widgets = self._free_position_subtree_widgets(widget)
        sibling_widgets = self._sibling_widgets(widget)
        same_parent_type_widgets = self._same_parent_type_widgets(widget)
        same_subtree_type_widgets = self._same_subtree_type_widgets(widget)
        same_type_widgets = self._same_type_widgets(widget)
        same_depth_widgets = self._same_depth_widgets(widget)
        can_select_parent = widget.parent is not None
        can_select_previous_sibling = self._previous_sibling_widget(widget) is not None
        can_select_next_sibling = self._next_sibling_widget(widget) is not None
        can_select_previous_siblings = bool(self._previous_sibling_widgets(widget))
        can_select_next_siblings = bool(self._next_sibling_widgets(widget))
        can_select_previous_in_tree = self._previous_tree_widget(widget) is not None
        can_select_next_in_tree = self._next_tree_widget(widget) is not None
        can_select_first_child = self._first_child_widget(widget) is not None
        can_select_last_child = self._last_child_widget(widget) is not None
        can_select_ancestors = bool(self._ancestor_widgets(widget))
        can_select_root = self._root_widget(widget) is not None and self._root_widget(widget) is not widget
        can_select_path = bool(self._widget_path(widget))
        can_select_top_level = bool(self._top_level_widgets(widget))
        can_select_children = bool(child_widgets)
        can_select_descendants = bool(descendant_widgets)
        can_select_subtree = bool(subtree_widgets)
        can_select_leaves = bool(leaf_descendant_widgets)
        can_select_containers = len(container_subtree_widgets) > 1
        can_select_visible = bool(visible_subtree_widgets)
        can_select_hidden = bool(hidden_subtree_widgets)
        can_select_unlocked = bool(unlocked_subtree_widgets)
        can_select_locked = bool(locked_subtree_widgets)
        can_select_layout_containers = bool(layout_container_subtree_widgets)
        can_select_managed = bool(managed_subtree_widgets)
        can_select_free_position = bool(free_position_subtree_widgets)
        can_select_siblings = len(sibling_widgets) > 1
        can_select_same_parent_type = len(same_parent_type_widgets) > 1
        can_select_same_subtree_type = len(same_subtree_type_widgets) > 1
        can_select_same_type = len(same_type_widgets) > 1
        can_select_same_depth = len(same_depth_widgets) > 1

        select_parent_action = QAction("Parent", self)
        select_parent_action.setEnabled(can_select_parent)
        select_parent_action.setToolTip(
            self._structure_tooltip(
                "Select the direct parent of this widget.",
                can_select_parent,
                "root widgets do not have a parent.",
            )
        )
        select_parent_action.triggered.connect(lambda: self._select_parent_widget(widget))
        select_menu.addAction(select_parent_action)

        select_previous_sibling_action = QAction("Previous Sibling", self)
        select_previous_sibling_action.setEnabled(can_select_previous_sibling)
        select_previous_sibling_action.setToolTip(
            self._structure_tooltip(
                "Select the previous sibling under the same parent.",
                can_select_previous_sibling,
                "root widgets do not have siblings."
                if widget.parent is None else
                "widget does not have a previous sibling under the same parent.",
            )
        )
        select_previous_sibling_action.triggered.connect(lambda: self._select_previous_sibling_widget(widget))
        select_menu.addAction(select_previous_sibling_action)

        select_next_sibling_action = QAction("Next Sibling", self)
        select_next_sibling_action.setEnabled(can_select_next_sibling)
        select_next_sibling_action.setToolTip(
            self._structure_tooltip(
                "Select the next sibling under the same parent.",
                can_select_next_sibling,
                "root widgets do not have siblings."
                if widget.parent is None else
                "widget does not have a next sibling under the same parent.",
            )
        )
        select_next_sibling_action.triggered.connect(lambda: self._select_next_sibling_widget(widget))
        select_menu.addAction(select_next_sibling_action)

        select_previous_siblings_action = QAction("Previous Siblings", self)
        select_previous_siblings_action.setEnabled(can_select_previous_siblings)
        select_previous_siblings_action.setToolTip(
            self._structure_tooltip(
                "Select all previous siblings under the same parent.",
                can_select_previous_siblings,
                "root widgets do not have siblings."
                if widget.parent is None else
                "widget does not have any previous siblings under the same parent.",
            )
        )
        select_previous_siblings_action.triggered.connect(lambda: self._select_previous_sibling_widgets(widget))
        select_menu.addAction(select_previous_siblings_action)

        select_next_siblings_action = QAction("Next Siblings", self)
        select_next_siblings_action.setEnabled(can_select_next_siblings)
        select_next_siblings_action.setToolTip(
            self._structure_tooltip(
                "Select all next siblings under the same parent.",
                can_select_next_siblings,
                "root widgets do not have siblings."
                if widget.parent is None else
                "widget does not have any next siblings under the same parent.",
            )
        )
        select_next_siblings_action.triggered.connect(lambda: self._select_next_sibling_widgets(widget))
        select_menu.addAction(select_next_siblings_action)

        select_previous_tree_action = QAction("Previous In Tree", self)
        select_previous_tree_action.setEnabled(can_select_previous_in_tree)
        select_previous_tree_action.setToolTip(
            self._structure_tooltip(
                "Select the previous widget in page tree order.",
                can_select_previous_in_tree,
                "widget is already the first widget in tree order on this page.",
            )
        )
        select_previous_tree_action.triggered.connect(lambda: self._select_previous_tree_widget(widget))
        select_menu.addAction(select_previous_tree_action)

        select_next_tree_action = QAction("Next In Tree", self)
        select_next_tree_action.setEnabled(can_select_next_in_tree)
        select_next_tree_action.setToolTip(
            self._structure_tooltip(
                "Select the next widget in page tree order.",
                can_select_next_in_tree,
                "widget is already the last widget in tree order on this page.",
            )
        )
        select_next_tree_action.triggered.connect(lambda: self._select_next_tree_widget(widget))
        select_menu.addAction(select_next_tree_action)

        select_ancestors_action = QAction("Ancestors", self)
        select_ancestors_action.setEnabled(can_select_ancestors)
        select_ancestors_action.setToolTip(
            self._structure_tooltip(
                "Select all ancestor widgets up to the page root.",
                can_select_ancestors,
                "root widgets do not have ancestors.",
            )
        )
        select_ancestors_action.triggered.connect(lambda: self._select_ancestor_widgets(widget))
        select_menu.addAction(select_ancestors_action)

        select_root_action = QAction("Root", self)
        select_root_action.setEnabled(can_select_root)
        select_root_action.setToolTip(
            self._structure_tooltip(
                "Select the page root widget for this subtree.",
                can_select_root,
                "widget is already the page root.",
            )
        )
        select_root_action.triggered.connect(lambda: self._select_root_widget(widget))
        select_menu.addAction(select_root_action)

        select_path_action = QAction("Path", self)
        select_path_action.setEnabled(can_select_path)
        select_path_action.setToolTip(
            self._structure_tooltip(
                "Select the full widget path from the page root to this widget.",
                can_select_path,
                "widget path is unavailable.",
            )
        )
        select_path_action.triggered.connect(lambda: self._select_widget_path(widget))
        select_menu.addAction(select_path_action)

        select_top_level_action = QAction("Top-Level", self)
        select_top_level_action.setEnabled(can_select_top_level)
        select_top_level_action.setToolTip(
            self._structure_tooltip(
                "Select widgets directly under the page root.",
                can_select_top_level,
                "page root has no child widgets.",
            )
        )
        select_top_level_action.triggered.connect(lambda: self._select_top_level_widgets(widget))
        select_menu.addAction(select_top_level_action)

        select_first_child_action = QAction("First Child", self)
        select_first_child_action.setEnabled(can_select_first_child)
        select_first_child_action.setToolTip(
            self._structure_tooltip(
                "Select the first direct child of this widget.",
                can_select_first_child,
                "widget has no child widgets.",
            )
        )
        select_first_child_action.triggered.connect(lambda: self._select_first_child_widget(widget))
        select_menu.addAction(select_first_child_action)

        select_last_child_action = QAction("Last Child", self)
        select_last_child_action.setEnabled(can_select_last_child)
        select_last_child_action.setToolTip(
            self._structure_tooltip(
                "Select the last direct child of this widget.",
                can_select_last_child,
                "widget has no child widgets.",
            )
        )
        select_last_child_action.triggered.connect(lambda: self._select_last_child_widget(widget))
        select_menu.addAction(select_last_child_action)

        select_children_action = QAction("Children", self)
        select_children_action.setEnabled(can_select_children)
        select_children_action.setToolTip(
            self._structure_tooltip(
                "Select the direct child widgets of this container.",
                can_select_children,
                "widget has no child widgets.",
            )
        )
        select_children_action.triggered.connect(lambda: self._select_child_widgets(widget))
        select_menu.addAction(select_children_action)

        select_descendants_action = QAction("Descendants", self)
        select_descendants_action.setEnabled(can_select_descendants)
        select_descendants_action.setToolTip(
            self._structure_tooltip(
                "Select all descendant widgets in this subtree.",
                can_select_descendants,
                "widget has no descendant widgets.",
            )
        )
        select_descendants_action.triggered.connect(lambda: self._select_descendant_widgets(widget))
        select_menu.addAction(select_descendants_action)

        select_subtree_action = QAction("Subtree", self)
        select_subtree_action.setEnabled(can_select_subtree)
        select_subtree_action.setToolTip(
            self._structure_tooltip(
                "Select this widget and all descendant widgets in its subtree.",
                can_select_subtree,
                "widget has no descendant widgets.",
            )
        )
        select_subtree_action.triggered.connect(lambda: self._select_subtree_widgets(widget))
        select_menu.addAction(select_subtree_action)

        select_leaves_action = QAction("Leaves", self)
        select_leaves_action.setEnabled(can_select_leaves)
        select_leaves_action.setToolTip(
            self._structure_tooltip(
                "Select only the leaf widgets in this subtree.",
                can_select_leaves,
                "widget has no leaf descendants.",
            )
        )
        select_leaves_action.triggered.connect(lambda: self._select_leaf_descendant_widgets(widget))
        select_menu.addAction(select_leaves_action)

        select_containers_action = QAction("Containers", self)
        select_containers_action.setEnabled(can_select_containers)
        select_containers_action.setToolTip(
            self._structure_tooltip(
                "Select container widgets in this subtree.",
                can_select_containers,
                "no other container widgets exist in this subtree.",
            )
        )
        select_containers_action.triggered.connect(lambda: self._select_container_subtree_widgets(widget))
        select_menu.addAction(select_containers_action)

        select_layout_containers_action = QAction("Layout Containers", self)
        select_layout_containers_action.setEnabled(can_select_layout_containers)
        select_layout_containers_action.setToolTip(
            self._structure_tooltip(
                "Select layout container widgets in this subtree.",
                can_select_layout_containers,
                "no layout container widgets exist in this subtree.",
            )
        )
        select_layout_containers_action.triggered.connect(
            lambda: self._select_layout_container_subtree_widgets(widget)
        )
        select_menu.addAction(select_layout_containers_action)

        select_visible_action = QAction("Visible", self)
        select_visible_action.setEnabled(can_select_visible)
        select_visible_action.setToolTip(
            self._structure_tooltip(
                "Select visible widgets in this subtree.",
                can_select_visible,
                "no visible widgets exist in this subtree.",
            )
        )
        select_visible_action.triggered.connect(lambda: self._select_visible_subtree_widgets(widget))
        select_menu.addAction(select_visible_action)

        select_hidden_action = QAction("Hidden", self)
        select_hidden_action.setEnabled(can_select_hidden)
        select_hidden_action.setToolTip(
            self._structure_tooltip(
                "Select hidden widgets in this subtree.",
                can_select_hidden,
                "no hidden widgets exist in this subtree.",
            )
        )
        select_hidden_action.triggered.connect(lambda: self._select_hidden_subtree_widgets(widget))
        select_menu.addAction(select_hidden_action)

        select_unlocked_action = QAction("Unlocked", self)
        select_unlocked_action.setEnabled(can_select_unlocked)
        select_unlocked_action.setToolTip(
            self._structure_tooltip(
                "Select unlocked widgets in this subtree.",
                can_select_unlocked,
                "no unlocked widgets exist in this subtree.",
            )
        )
        select_unlocked_action.triggered.connect(lambda: self._select_unlocked_subtree_widgets(widget))
        select_menu.addAction(select_unlocked_action)

        select_locked_action = QAction("Locked", self)
        select_locked_action.setEnabled(can_select_locked)
        select_locked_action.setToolTip(
            self._structure_tooltip(
                "Select locked widgets in this subtree.",
                can_select_locked,
                "no locked widgets exist in this subtree.",
            )
        )
        select_locked_action.triggered.connect(lambda: self._select_locked_subtree_widgets(widget))
        select_menu.addAction(select_locked_action)

        select_managed_action = QAction("Managed", self)
        select_managed_action.setEnabled(can_select_managed)
        select_managed_action.setToolTip(
            self._structure_tooltip(
                "Select layout-managed widgets in this subtree.",
                can_select_managed,
                "no layout-managed widgets exist in this subtree.",
            )
        )
        select_managed_action.triggered.connect(lambda: self._select_managed_subtree_widgets(widget))
        select_menu.addAction(select_managed_action)

        select_free_position_action = QAction("Free Position", self)
        select_free_position_action.setEnabled(can_select_free_position)
        select_free_position_action.setToolTip(
            self._structure_tooltip(
                "Select free-position widgets in this subtree.",
                can_select_free_position,
                "no free-position widgets exist in this subtree.",
            )
        )
        select_free_position_action.triggered.connect(lambda: self._select_free_position_subtree_widgets(widget))
        select_menu.addAction(select_free_position_action)

        select_siblings_action = QAction("Siblings", self)
        select_siblings_action.setEnabled(can_select_siblings)
        select_siblings_action.setToolTip(
            self._structure_tooltip(
                "Select this widget and its siblings under the same parent.",
                can_select_siblings,
                "root widgets do not have siblings."
                if widget.parent is None else
                "widget has no siblings under the same parent.",
            )
        )
        select_siblings_action.triggered.connect(lambda: self._select_sibling_widgets(widget))
        select_menu.addAction(select_siblings_action)

        select_same_parent_type_action = QAction("Same Parent Type", self)
        select_same_parent_type_action.setEnabled(can_select_same_parent_type)
        select_same_parent_type_action.setToolTip(
            self._structure_tooltip(
                f"Select sibling {getattr(widget, 'widget_type', 'widget')} widgets under the same parent.",
                can_select_same_parent_type,
                "root widgets do not have siblings."
                if widget.parent is None else
                f"no other {getattr(widget, 'widget_type', 'widget')} widgets exist under the same parent.",
            )
        )
        select_same_parent_type_action.triggered.connect(lambda: self._select_same_parent_type_widgets(widget))
        select_menu.addAction(select_same_parent_type_action)

        select_same_subtree_type_action = QAction("Subtree Type", self)
        select_same_subtree_type_action.setEnabled(can_select_same_subtree_type)
        select_same_subtree_type_action.setToolTip(
            self._structure_tooltip(
                f"Select {getattr(widget, 'widget_type', 'widget')} widgets in this subtree.",
                can_select_same_subtree_type,
                f"no other {getattr(widget, 'widget_type', 'widget')} widgets exist in this subtree.",
            )
        )
        select_same_subtree_type_action.triggered.connect(lambda: self._select_same_subtree_type_widgets(widget))
        select_menu.addAction(select_same_subtree_type_action)

        select_same_type_action = QAction("Same Type", self)
        select_same_type_action.setEnabled(can_select_same_type)
        select_same_type_action.setToolTip(
            self._structure_tooltip(
                f"Select all {getattr(widget, 'widget_type', 'widget')} widgets on this page.",
                can_select_same_type,
                f"no other {getattr(widget, 'widget_type', 'widget')} widgets exist on this page.",
            )
        )
        select_same_type_action.triggered.connect(lambda: self._select_same_type_widgets(widget))
        select_menu.addAction(select_same_type_action)

        select_same_depth_action = QAction("Same Depth", self)
        select_same_depth_action.setEnabled(can_select_same_depth)
        select_same_depth_action.setToolTip(
            self._structure_tooltip(
                f"Select all widgets at depth {self._widget_depth(widget)} on this page.",
                can_select_same_depth,
                f"no other widgets exist at depth {self._widget_depth(widget)} on this page.",
            )
        )
        select_same_depth_action.triggered.connect(lambda: self._select_same_depth_widgets(widget))
        select_menu.addAction(select_same_depth_action)
        select_enabled = any([
            can_select_parent,
            can_select_previous_sibling,
            can_select_next_sibling,
            can_select_previous_siblings,
            can_select_next_siblings,
            can_select_previous_in_tree,
            can_select_next_in_tree,
            can_select_first_child,
            can_select_last_child,
            can_select_ancestors,
            can_select_root,
            can_select_path,
            can_select_top_level,
            can_select_children,
            can_select_descendants,
            can_select_subtree,
            can_select_leaves,
            can_select_containers,
            can_select_layout_containers,
            can_select_visible,
            can_select_hidden,
            can_select_unlocked,
            can_select_locked,
            can_select_managed,
            can_select_free_position,
            can_select_siblings,
            can_select_same_parent_type,
            can_select_same_subtree_type,
            can_select_same_type,
            can_select_same_depth,
        ])
        for action in select_menu.actions():
            action.setStatusTip(action.toolTip())
        select_menu.menuAction().setEnabled(select_enabled)
        _set_action_metadata(
            select_menu.menuAction(),
            tooltip=(
                "Select related widgets from this widget's parent, subtree, siblings, and page hierarchy."
                if select_enabled
                else "Selection navigation unavailable for this widget."
            ),
        )

    def _move_target_memory_key(self):
        if self.project is None:
            return None

        page = getattr(self.project, "_page", None)
        if page is not None:
            return ("page", id(page))

        project_dir = (getattr(self.project, "project_dir", "") or "").strip()
        get_startup_page = getattr(self.project, "get_startup_page", None)
        if callable(get_startup_page):
            page = get_startup_page()
            page_name = getattr(page, "name", "") if page is not None else ""
            return ("project", project_dir or id(self.project), page_name)

        root_ids = tuple(id(widget) for widget in (getattr(self.project, "root_widgets", []) or []) if widget is not None)
        if root_ids:
            return ("roots", root_ids)
        return ("project", id(self.project))

    def remembered_move_target_label(self):
        labels = self.recent_move_target_labels()
        return labels[0] if labels else ""

    def _current_move_target_label(self, widget=None, fallback_label=""):
        if widget is not None:
            current_item = widget
            names = []
            while current_item is not None:
                names.append(current_item.name or current_item.widget_type)
                current_item = current_item.parent
            if names:
                return f"{' / '.join(reversed(names))} ({widget.widget_type})"
        return (fallback_label or "").strip()

    def _move_target_history_entries(self):
        key = self._move_target_memory_key()
        if key is None:
            return []
        entries = self._remembered_move_target_labels.get(key, [])
        normalized = []
        seen = set()
        valid_widget_ids = {id(widget) for widget in self._iter_widgets() or []}
        for entry in entries:
            if isinstance(entry, str):
                widget = None
                fallback_label = entry
                tracked = False
            else:
                widget = entry.get("widget")
                fallback_label = entry.get("label", "")
                tracked = bool(entry.get("tracked", widget is not None))
            if widget is not None and id(widget) not in valid_widget_ids:
                if tracked:
                    continue
                widget = None
            label = self._current_move_target_label(widget, fallback_label)
            if not label or label in seen:
                continue
            seen.add(label)
            normalized.append({"widget": widget, "label": label, "tracked": tracked})
        self._remembered_move_target_labels[key] = normalized[: self._MAX_RECENT_MOVE_TARGETS]
        return list(self._remembered_move_target_labels[key])

    def recent_move_target_labels(self):
        return [entry["label"] for entry in self._move_target_history_entries()]

    def has_recent_move_targets(self):
        return bool(self.recent_move_target_labels())

    def set_remembered_move_target_label(self, label):
        key = self._move_target_memory_key()
        if key is None:
            return
        normalized = (label or "").strip()
        if normalized:
            self._remembered_move_target_labels[key] = [{"widget": None, "label": normalized, "tracked": False}]
        else:
            self._remembered_move_target_labels.pop(key, None)

    def remember_move_target_label(self, label):
        self.remember_move_target(None, label)

    def remember_move_target(self, widget=None, label=""):
        key = self._move_target_memory_key()
        if key is None:
            return
        normalized = self._current_move_target_label(widget, label)
        if not normalized:
            return
        history = [{"widget": widget, "label": normalized, "tracked": widget is not None}]
        for entry in self._move_target_history_entries():
            same_widget = widget is not None and entry.get("widget") is widget
            same_label = entry.get("label") == normalized
            if same_widget or same_label:
                continue
            history.append(entry)
        self._remembered_move_target_labels[key] = history[: self._MAX_RECENT_MOVE_TARGETS]

    def forget_move_targets_for_widgets(self, widgets):
        key = self._move_target_memory_key()
        if key is None:
            return 0
        removed_ids = set()
        for widget in widgets or []:
            if widget is None:
                continue
            removed_ids.update(id(current) for current in widget.get_all_widgets_flat())
        if not removed_ids:
            return 0
        kept = []
        removed_count = 0
        for entry in self._move_target_history_entries():
            widget = entry.get("widget")
            if widget is not None and id(widget) in removed_ids:
                removed_count += 1
                continue
            kept.append(entry)
        self._remembered_move_target_labels[key] = kept
        return removed_count

    def clear_remembered_move_target_labels(self):
        key = self._move_target_memory_key()
        if key is None:
            return
        self._remembered_move_target_labels.pop(key, None)

    def set_selected_widgets(self, widgets, primary=None):
        self._clear_tree_drag_hover()
        self._syncing_selection = True
        try:
            self.tree.clearSelection()
            widgets = [widget for widget in (widgets or []) if widget is not None]
            current_item = None
            for widget in widgets:
                item = self._item_map.get(id(widget))
                if item is not None:
                    item.setSelected(True)
            if primary is not None:
                item = self._item_map.get(id(primary))
                if item is not None:
                    self.tree.setCurrentItem(item, 0, QItemSelectionModel.NoUpdate)
                    current_item = item
            elif widgets:
                item = self._item_map.get(id(widgets[-1]))
                if item is not None:
                    self.tree.setCurrentItem(item, 0, QItemSelectionModel.NoUpdate)
                    current_item = item
            else:
                self.tree.setCurrentItem(None)
            if current_item is not None:
                self._reveal_item(current_item)
        finally:
            self._syncing_selection = False
        self._update_filter_position_label()
        self._update_structure_controls()

    def _iter_widgets(self):
        if not self.project:
            return
        for root_widget in self.project.root_widgets:
            yield root_widget
            yield from root_widget.get_all_widgets_flat()[1:]

    def _existing_widget_names(self, exclude_widget=None, exclude_widgets=None):
        excluded_ids = set()
        if exclude_widget is not None:
            excluded_ids.add(id(exclude_widget))
        for widget in exclude_widgets or []:
            if widget is not None:
                excluded_ids.add(id(widget))
        names = set()
        for widget in self._iter_widgets() or []:
            if id(widget) in excluded_ids:
                continue
            if widget.name:
                names.add(widget.name)
        return names

    def _make_unique_widget_name(self, base_name, exclude_widget=None):
        candidate = (base_name or "").strip().replace(" ", "_")
        if not candidate:
            return ""
        existing = self._existing_widget_names(exclude_widget=exclude_widget)
        if candidate not in existing:
            return candidate

        match = re.match(r"^(.*?)(?:_(\d+))?$", candidate)
        stem = candidate
        suffix = 2
        if match:
            stem = match.group(1) or candidate
            if match.group(2):
                suffix = int(match.group(2)) + 1

        while f"{stem}_{suffix}" in existing:
            suffix += 1
        return f"{stem}_{suffix}"

    def _context_widgets(self, anchor_widget=None):
        selected_widgets = self.selected_widgets()
        if anchor_widget is not None and anchor_widget not in selected_widgets:
            return [anchor_widget]
        return selected_widgets or ([anchor_widget] if anchor_widget is not None else [])

    def _drop_root_widget(self):
        root_widgets = list(getattr(self.project, "root_widgets", []) or [])
        return root_widgets[0] if root_widgets else None

    def _structure_action_state(self, widgets=None):
        selection = self.selected_widgets() if widgets is None else widgets
        return describe_structure_actions(self.project, selection)

    def _structure_tooltip(self, base_text, enabled, blocked_reason=""):
        if enabled or not blocked_reason:
            return base_text
        reason = blocked_reason.rstrip(".")
        return f"{base_text}\nUnavailable: {reason}."

    def _update_primary_action_metadata(self):
        if not hasattr(self, "add_btn"):
            return

        insert_parent = self._default_insert_parent()
        insert_target = self._current_move_target_label(insert_parent, "page root") or "page root"
        can_insert = self.project is not None
        if can_insert:
            add_tooltip = f"Open the Components panel to insert a component into {insert_target}."
            add_accessible_name = f"Insert component target: {insert_target}"
        else:
            add_tooltip = "Open or create a project page to insert a component."
            add_accessible_name = "Insert component unavailable"
        self.add_btn.setEnabled(can_insert)
        _set_widget_metadata(self.add_btn, tooltip=add_tooltip, accessible_name=add_accessible_name)

        selected_widgets = self.selected_widgets()
        selected_count = len(selected_widgets)
        if selected_count == 0:
            rename_enabled = False
            rename_tooltip = self._structure_tooltip(
                "Rename the current selection (F2)",
                False,
                "select at least 1 widget.",
            )
            rename_accessible_name = "Rename selected widget unavailable"
        elif selected_count == 1:
            rename_enabled = True
            selected_label = self._widget_label(selected_widgets[0])
            rename_tooltip = f"Rename {selected_label} (F2)."
            rename_accessible_name = f"Rename selected widget: {selected_label}"
        else:
            rename_enabled = True
            selection_label = _count_label(selected_count, "selected widget", "selected widgets")
            rename_tooltip = f"Batch rename {selection_label} (F2)."
            rename_accessible_name = f"Rename {selection_label}"
        self.rename_btn.setEnabled(rename_enabled)
        _set_widget_metadata(self.rename_btn, tooltip=rename_tooltip, accessible_name=rename_accessible_name)

        deletable_widgets = [widget for widget in selected_widgets if not getattr(widget, "designer_locked", False)]
        locked_count = selected_count - len(deletable_widgets)
        if selected_count == 0:
            delete_enabled = False
            delete_tooltip = self._structure_tooltip(
                "Delete the current selection (Del)",
                False,
                "select at least 1 widget.",
            )
            delete_accessible_name = "Delete selected widget unavailable"
        elif not deletable_widgets:
            delete_enabled = False
            delete_tooltip = self._structure_tooltip(
                "Delete the current selection (Del)",
                False,
                f"{self._locked_widget_summary(locked_count)}.",
            )
            delete_accessible_name = "Delete selected widget unavailable"
        elif len(deletable_widgets) == 1 and selected_count == 1:
            delete_enabled = True
            selected_label = self._widget_label(deletable_widgets[0])
            delete_tooltip = f"Delete {selected_label} (Del)."
            delete_accessible_name = f"Delete selected widget: {selected_label}"
        else:
            delete_enabled = True
            selection_label = _count_label(len(deletable_widgets), "selected widget", "selected widgets")
            delete_tooltip = f"Delete {selection_label} (Del)."
            delete_accessible_name = f"Delete {selection_label}"
            if locked_count:
                locked_summary = self._locked_widget_summary(locked_count)
                delete_tooltip += f" Skips {locked_summary}."
                delete_accessible_name += f". {locked_summary} skipped."
        self.del_btn.setEnabled(delete_enabled)
        _set_widget_metadata(self.del_btn, tooltip=delete_tooltip, accessible_name=delete_accessible_name)

    def _context_rename_tooltip(self, widget, context_widgets):
        if len(context_widgets) > 1 and widget in context_widgets:
            selection_label = _count_label(len(context_widgets), "selected widget", "selected widgets")
            return f"Batch rename {selection_label} (F2)."
        selected_label = self._widget_label(widget) or "widget"
        return f"Rename {selected_label} (F2)."

    def _context_insert_tooltip(self, preferred_parent):
        insert_target = self._context_insert_target_label(preferred_parent)
        return f"Open the Components panel to insert a component into {insert_target}."

    def _context_insert_target_label(self, preferred_parent):
        insert_target = self._current_move_target_label(preferred_parent, "page root") or "page root"
        return insert_target

    def _context_recent_widget_tooltip(self, display_name, preferred_parent):
        return f"Insert {display_name} into {self._context_insert_target_label(preferred_parent)}."

    def _context_recent_widgets_menu_tooltip(self, preferred_parent):
        return f"Insert a recently used widget into {self._context_insert_target_label(preferred_parent)}."

    def _context_delete_tooltip(self, widget):
        selected_label = self._widget_label(widget) or "widget"
        return f"Delete {selected_label} (Del)."

    def _structure_action_reason(self, state, reason_attr=""):
        if reason_attr:
            reason = getattr(state, reason_attr, "")
            if reason:
                return reason
        return state.blocked_reason

    def _move_target_choices(self, widgets):
        return available_move_targets(self.project, widgets)

    def _quick_move_target_choices(self, widgets):
        choices = self._move_target_choices(widgets)
        recent_labels = self.recent_move_target_labels()
        if not recent_labels:
            return choices

        choice_by_label = {choice.label: choice for choice in choices}
        prioritized = [choice_by_label[label] for label in recent_labels if label in choice_by_label]
        if not prioritized:
            return choices
        prioritized_labels = {choice.label for choice in prioritized}
        return prioritized + [choice for choice in choices if choice.label not in prioritized_labels]

    def _recent_move_target_choices(self, widgets):
        choices = self._move_target_choices(widgets)
        if not choices:
            return []
        choice_by_label = {choice.label: choice for choice in choices}
        return [choice_by_label[label] for label in self.recent_move_target_labels() if label in choice_by_label]

    def _remaining_move_target_choices(self, widgets):
        choices = self._move_target_choices(widgets)
        recent_labels = {choice.label for choice in self._recent_move_target_choices(widgets)}
        return [choice for choice in choices if choice.label not in recent_labels]

    def _move_target_default_index(self, choices):
        remembered_label = self.remembered_move_target_label()
        if not remembered_label:
            return 0
        for index, choice in enumerate(choices):
            if choice.label == remembered_label:
                return index
        return 0

    def _resolve_move_target_label(self, widgets, target_widget):
        for choice in self._move_target_choices(widgets):
            if choice.widget is target_widget:
                return choice.label
        return ""

    def _remembered_move_target_choice(self, widgets):
        remembered_label = self.remembered_move_target_label()
        if not remembered_label:
            return None
        for choice in self._move_target_choices(widgets):
            if choice.label == remembered_label:
                return choice
        return None

    def _move_into_last_target_reason(self, widgets):
        if not self.remembered_move_target_label():
            return "move something into a container first."
        if self._remembered_move_target_choice(widgets) is None:
            return "the last target is not available for the current selection."
        return ""

    def _move_into_last_target_hint(self, widgets, shortcut_text="Ctrl+Alt+I"):
        choice = self._remembered_move_target_choice(widgets)
        label = choice.label if choice is not None else self.remembered_move_target_label()
        action_suffix = f" ({shortcut_text})" if shortcut_text else ""
        if label:
            return f"Move the current selection into {label} again{action_suffix}"
        return f"Move the current selection into the last remembered container target{action_suffix}"

    def _repeat_move_target_summary(self, widgets):
        choice = self._remembered_move_target_choice(widgets)
        if choice is None:
            return ""
        return getattr(choice.widget, "name", "") or choice.label

    def _clear_move_target_history_hint(self):
        count = len(self.recent_move_target_labels())
        if count:
            noun = "target" if count == 1 else "targets"
            return f"Forget {count} recent move-into {noun} for the current page"
        return "Forget recent move-into targets for the current page"

    def _quick_move_menu_hint(self):
        return "Move directly into an available container target, or manage move-target history."

    def _into_button_history_hint(self):
        return "Open the Into menu to manage move-target history."

    def _structure_history_hint_suffix(self):
        if not self.has_recent_move_targets():
            return ""
        return " Into menu can manage move history."

    def _cleared_move_target_history_text(self, count):
        noun = "target" if count == 1 else "targets"
        return f"cleared {count} recent move {noun}"

    def _cleared_move_target_history_message(self, count):
        noun = "target" if count == 1 else "targets"
        return f"Cleared {count} recent move {noun}."

    def _update_structure_controls(self):
        if not hasattr(self, "group_btn"):
            return
        state = self._structure_action_state()
        selected_count = len(state.widgets)
        has_quick_move_history = self._remembered_move_target_choice(state.widgets) is not None or self.has_recent_move_targets()
        self.group_btn.setEnabled(state.can_group)
        self.ungroup_btn.setEnabled(state.can_ungroup)
        self.into_btn.setEnabled(state.can_move_into or has_quick_move_history)
        self.into_btn.setPopupMode(QToolButton.MenuButtonPopup if state.can_move_into else QToolButton.InstantPopup)
        self.lift_btn.setEnabled(state.can_lift)
        self.up_btn.setEnabled(state.can_move_up)
        self.down_btn.setEnabled(state.can_move_down)
        self.top_btn.setEnabled(state.can_move_top)
        self.bottom_btn.setEnabled(state.can_move_bottom)
        for button, (base_text, reason_attr) in self._structure_button_tooltips.items():
            button.setToolTip(self._structure_tooltip(base_text, button.isEnabled(), self._structure_action_reason(state, reason_attr)))
            button.setStatusTip(button.toolTip())
        if not state.can_move_into and has_quick_move_history:
            self.into_btn.setToolTip(self._into_button_history_hint())
            self.into_btn.setStatusTip(self.into_btn.toolTip())
        if hasattr(self, "_selection_toolbar"):
            self._selection_toolbar.setVisible(selected_count > 0)
        if hasattr(self, "_selection_summary_chip"):
            if selected_count <= 0:
                chip_text = "No selection"
                chip_tone = "warning"
            elif selected_count == 1:
                widget = state.widgets[0]
                chip_text = f"1 selected - {self._widget_label(widget)}"
                chip_tone = "accent"
            else:
                chip_text = f"{selected_count} selected"
                chip_tone = "accent"
            self._set_status_chip_state(self._selection_summary_chip, chip_text, chip_tone)
        self._refresh_into_button_menu(state)
        self._structure_base_hint_text = self._structure_hint_text(state)
        self._apply_structure_status_summary()
        self._refresh_structure_actions_menu(state)
        self._update_structure_actions_button_metadata(state)
        self._update_primary_action_metadata()
        self._update_header_context()
        self._update_accessibility_summary()

    def _apply_structure_status_summary(self):
        base_text = (self._structure_base_hint_text or "").strip() or "Structure hint unavailable."
        drag_text = self.drag_target_label.text().strip() or self._default_drag_target_text()
        default_drag_text = self._default_drag_target_text()
        if drag_text and drag_text != default_drag_text:
            summary = f"{base_text} {drag_text}"
            tone = self._drag_target_tone if hasattr(self, "_drag_target_tone") else "default"
            self.structure_hint_label.setStyleSheet(self._DRAG_TARGET_LABEL_STYLES.get(tone, self._DRAG_TARGET_LABEL_STYLES["default"]))
        else:
            summary = base_text
            self.structure_hint_label.setStyleSheet("")
        self.structure_hint_label.setText(summary)

    def _add_structure_menu_action(self, menu, text, *, tooltip="", enabled=True, handler=None, shortcut=""):
        action = QAction(text, self)
        if shortcut:
            action.setShortcut(shortcut)
        action.setEnabled(bool(enabled))
        if tooltip:
            _set_action_metadata(action, tooltip=tooltip)
        if handler is not None:
            action.triggered.connect(handler)
        menu.addAction(action)
        return action

    def _refresh_structure_actions_menu(self, state=None):
        if not hasattr(self, "_structure_actions_menu"):
            return

        state = state or self._structure_action_state()
        widgets = list(state.widgets)
        menu = self._structure_actions_menu
        menu.clear()

        self._add_structure_menu_action(
            menu,
            "Group Selection",
            tooltip=self._structure_tooltip("Group the current selection (Ctrl+G)", state.can_group, self._structure_action_reason(state, "group_reason")),
            enabled=state.can_group,
            handler=lambda checked=False: self._group_selected_widgets(widgets),
            shortcut="Ctrl+G",
        )
        self._add_structure_menu_action(
            menu,
            "Ungroup",
            tooltip=self._structure_tooltip("Ungroup the selected group widgets (Ctrl+Shift+G)", state.can_ungroup, self._structure_action_reason(state, "ungroup_reason")),
            enabled=state.can_ungroup,
            handler=lambda checked=False: self._ungroup_selected_widgets(widgets),
            shortcut="Ctrl+Shift+G",
        )
        self._add_structure_menu_action(
            menu,
            "Move Into...",
            tooltip=self._structure_tooltip("Move the current selection into another container (Ctrl+Shift+I)", state.can_move_into, self._structure_action_reason(state, "move_into_reason")),
            enabled=state.can_move_into,
            handler=lambda checked=False: self._move_selected_widgets_into(widgets=widgets),
            shortcut="Ctrl+Shift+I",
        )
        quick_move_menu = menu.addMenu("Quick Move Into")
        quick_move_menu.setToolTipsVisible(True)
        _set_action_metadata(quick_move_menu.menuAction(), tooltip=self._quick_move_menu_hint())
        self._populate_quick_move_menu(quick_move_menu, widgets, max_targets=5, include_management_actions=True)
        self._add_structure_menu_action(
            menu,
            "Lift To Parent",
            tooltip=self._structure_tooltip("Lift the current selection to the parent container (Ctrl+Shift+L)", state.can_lift, self._structure_action_reason(state, "lift_reason")),
            enabled=state.can_lift,
            handler=lambda checked=False: self._lift_selected_widgets(widgets),
            shortcut="Ctrl+Shift+L",
        )

        menu.addSeparator()

        self._add_structure_menu_action(
            menu,
            "Move Up",
            tooltip=self._structure_tooltip("Move the current selection up among its siblings (Alt+Up)", state.can_move_up, self._structure_action_reason(state, "move_up_reason")),
            enabled=state.can_move_up,
            handler=lambda checked=False: self._move_selected_widgets_up(widgets),
            shortcut="Alt+Up",
        )
        self._add_structure_menu_action(
            menu,
            "Move Down",
            tooltip=self._structure_tooltip("Move the current selection down among its siblings (Alt+Down)", state.can_move_down, self._structure_action_reason(state, "move_down_reason")),
            enabled=state.can_move_down,
            handler=lambda checked=False: self._move_selected_widgets_down(widgets),
            shortcut="Alt+Down",
        )
        self._add_structure_menu_action(
            menu,
            "Move To Top",
            tooltip=self._structure_tooltip("Move the current selection to the top of its sibling list (Alt+Shift+Up)", state.can_move_top, self._structure_action_reason(state, "move_top_reason")),
            enabled=state.can_move_top,
            handler=lambda checked=False: self._move_selected_widgets_to_top(widgets),
            shortcut="Alt+Shift+Up",
        )
        self._add_structure_menu_action(
            menu,
            "Move To Bottom",
            tooltip=self._structure_tooltip("Move the current selection to the bottom of its sibling list (Alt+Shift+Down)", state.can_move_bottom, self._structure_action_reason(state, "move_bottom_reason")),
            enabled=state.can_move_bottom,
            handler=lambda checked=False: self._move_selected_widgets_to_bottom(widgets),
            shortcut="Alt+Shift+Down",
        )

        menu.addSeparator()

        has_items = bool(self._item_map)
        self._add_structure_menu_action(
            menu,
            "Expand All",
            tooltip="Expand all widgets in the tree.",
            enabled=has_items,
            handler=self._expand_all_items,
        )
        self._add_structure_menu_action(
            menu,
            "Collapse All",
            tooltip="Collapse all widgets in the tree.",
            enabled=has_items,
            handler=self._collapse_all_items,
        )

    def _update_structure_actions_button_metadata(self, state):
        if not hasattr(self, "structure_actions_btn"):
            return
        has_project = self.project is not None
        enabled = bool(
            has_project
            or self.has_recent_move_targets()
            or state.can_group
            or state.can_ungroup
            or state.can_move_into
            or state.can_lift
            or state.can_move_up
            or state.can_move_down
            or state.can_move_top
            or state.can_move_bottom
            or self._item_map
        )
        self.structure_actions_btn.setEnabled(enabled)
        if enabled:
            tooltip = "Open structure actions for grouping, moving, history, and tree visibility."
            accessible_name = "Open structure actions"
        else:
            tooltip = "Open a project page to manage structure actions."
            accessible_name = "Structure actions unavailable"
        _set_widget_metadata(self.structure_actions_btn, tooltip=tooltip, accessible_name=accessible_name)

    def _refresh_into_button_menu(self, state=None):
        if not hasattr(self, "_into_quick_menu"):
            return

        state = state or self._structure_action_state()
        self._populate_quick_move_menu(self._into_quick_menu, state.widgets, include_management_actions=True)

    def _add_move_target_menu_action(self, menu, choice, widgets):
        action = QAction(choice.label, self)
        _set_action_metadata(action, tooltip=f"Move the current selection into {choice.label}.")
        action.triggered.connect(
            lambda checked=False, target=choice.widget, target_label=choice.label, selected_widgets=list(widgets): self._move_selected_widgets_into(
                target_widget=target,
                widgets=selected_widgets,
                target_label=target_label,
            )
        )
        menu.addAction(action)

    def _add_menu_section_label(self, menu, title):
        section_action = QAction(title, menu)
        section_action.setEnabled(False)
        menu.addAction(section_action)

    def _add_disabled_menu_note(self, menu, text, tooltip=""):
        note_action = QAction(text, menu)
        note_action.setEnabled(False)
        if tooltip:
            _set_action_metadata(note_action, tooltip=tooltip)
        menu.addAction(note_action)

    def _add_into_button_management_actions(self, menu, widgets):
        move_into_last_target_action = QAction("Move Into Last Target", self)
        move_into_last_target_choice = self._remembered_move_target_choice(widgets)
        move_into_last_target_action.setEnabled(move_into_last_target_choice is not None)
        _set_action_metadata(
            move_into_last_target_action,
            tooltip=self._structure_tooltip(
                self._move_into_last_target_hint(widgets),
                move_into_last_target_choice is not None,
                self._move_into_last_target_reason(widgets),
            ),
        )
        move_into_last_target_action.triggered.connect(lambda checked=False, selected_widgets=list(widgets): self._move_selected_widgets_into_last_target(selected_widgets))
        menu.addAction(move_into_last_target_action)

        clear_move_target_history_action = QAction("Clear Move Target History", self)
        clear_move_target_history_action.setEnabled(self.has_recent_move_targets())
        _set_action_metadata(
            clear_move_target_history_action,
            tooltip=self._structure_tooltip(
                self._clear_move_target_history_hint(),
                self.has_recent_move_targets(),
                "no recent move targets are saved.",
            ),
        )
        clear_move_target_history_action.triggered.connect(self._clear_move_target_history)
        menu.addAction(clear_move_target_history_action)

    def _populate_quick_move_menu(self, menu, widgets, max_targets=None, include_management_actions=False):
        menu.clear()
        recent_choices = self._recent_move_target_choices(widgets)
        remaining_choices = self._remaining_move_target_choices(widgets)

        recent_limit = len(recent_choices) if max_targets is None else max(0, min(len(recent_choices), max_targets))
        recent_display = recent_choices[:recent_limit]
        remaining_limit = None if max_targets is None else max(0, max_targets - len(recent_display))
        remaining_display = remaining_choices if remaining_limit is None else remaining_choices[:remaining_limit]

        if recent_display:
            self._add_menu_section_label(menu, "Recent Targets")
            for choice in recent_display:
                self._add_move_target_menu_action(menu, choice, widgets)
            if remaining_display:
                menu.addSeparator()
                self._add_menu_section_label(menu, "Other Targets")
        elif remaining_display:
            self._add_menu_section_label(menu, "Recent Targets")
            self._add_disabled_menu_note(
                menu,
                "(No recent targets yet)",
                "Move something into a container first to build recent targets for this page.",
            )
            menu.addSeparator()
            self._add_menu_section_label(menu, "Other Targets")
        for choice in remaining_display:
            self._add_move_target_menu_action(menu, choice, widgets)
        if not recent_display and not remaining_display:
            self._add_disabled_menu_note(menu, "(No eligible target containers)")
        if include_management_actions:
            if menu.actions():
                menu.addSeparator()
            self._add_menu_section_label(menu, "History")
            self._add_into_button_management_actions(menu, widgets)

    def _default_drag_target_text(self):
        return "Drop target: drag over the tree to preview where the selection will land."

    def _set_drag_target_label(self, text, tone="default"):
        self._drag_target_tone = tone
        self.drag_target_label.setText(text)
        self.drag_target_label.setStyleSheet(self._DRAG_TARGET_LABEL_STYLES.get(tone, self._DRAG_TARGET_LABEL_STYLES["default"]))
        if hasattr(self, "_drag_hint_frame"):
            default_text = self._default_drag_target_text()
            self._drag_hint_frame.setVisible(bool(text.strip()) and text.strip() != default_text)
        self._apply_structure_status_summary()
        self._update_accessibility_summary()

    def _update_filter_accessibility(self):
        if not hasattr(self, "filter_edit"):
            return
        query = self.filter_edit.text().strip()
        status_text = self.filter_status_label.text().strip() or "All widgets"
        position_text = self.filter_position_label.text().strip() or "none"
        matches = self._current_filter_matches()
        if not query:
            prev_hint = "Type a widget filter to navigate previous matches."
            next_hint = "Type a widget filter to navigate next matches."
            select_hint = "Type a widget filter to select matching widgets."
        elif not matches:
            prev_hint = "No previous widget filter match is available."
            next_hint = "No next widget filter match is available."
            select_hint = "No widget filter matches are available to select."
        else:
            prev_hint = "Select the previous widget filter match (Shift+Enter)."
            next_hint = "Select the next widget filter match (Enter)."
            select_hint = "Select all current filter matches (Ctrl+Enter)."
        if matches:
            match_count_text = _count_label(len(matches), "match", "matches")
            position_summary = f" Current position {position_text}." if position_text != "none" else ""
            prev_accessible_name = f"Previous widget filter match: {match_count_text}.{position_summary}".rstrip()
            next_accessible_name = f"Next widget filter match: {match_count_text}.{position_summary}".rstrip()
            select_accessible_name = f"Select {len(matches)} widget filter {'match' if len(matches) == 1 else 'matches'}"
        else:
            prev_accessible_name = "Previous widget filter match unavailable"
            next_accessible_name = "Next widget filter match unavailable"
            select_accessible_name = "Select widget filter matches unavailable"
        _set_widget_metadata(
            self.filter_edit,
            tooltip=f"Filter widgets by name or type. Current filter: {query or 'none'}.",
            accessible_name=f"Widget filter: {query or 'none'}",
        )
        _set_widget_metadata(
            self.filter_prev_btn,
            tooltip=prev_hint,
            accessible_name=prev_accessible_name,
        )
        _set_widget_metadata(
            self.filter_next_btn,
            tooltip=next_hint,
            accessible_name=next_accessible_name,
        )
        _set_widget_metadata(
            self.filter_select_btn,
            tooltip=select_hint,
            accessible_name=select_accessible_name,
        )
        _set_widget_metadata(
            self.filter_status_label,
            tooltip=f"Widget filter status: {status_text}",
            accessible_name=f"Widget filter status: {status_text}",
        )
        _set_widget_metadata(
            self.filter_position_label,
            tooltip=f"Widget filter position: {position_text}",
            accessible_name=f"Widget filter position: {position_text}",
        )

    def _update_accessibility_summary(self):
        if not all(
            hasattr(self, attr)
            for attr in (
                "tree",
                "filter_edit",
                "filter_status_label",
                "filter_position_label",
                "structure_hint_label",
            )
        ):
            return
        widget_count = _count_label(len(self._item_map), "widget")
        selected_widgets = self.selected_widgets()
        selected_count = _count_label(len(selected_widgets), "selected widget", "selected widgets")
        current_widget = self._widget_label(self._get_selected_widget()) or "none"
        filter_query = self.filter_edit.text().strip() or "none"
        filter_status = self.filter_status_label.text().strip() or "All widgets"
        filter_position = self.filter_position_label.text().strip() or "none"
        structure_hint = self.structure_hint_label.text().strip() or "Structure hint unavailable."
        drag_target_text = getattr(self, "drag_target_label", None)
        drag_target_text = drag_target_text.text().strip() if drag_target_text is not None else self._default_drag_target_text()
        summary = (
            f"Widget tree: {widget_count}. {selected_count}. Current widget: {current_widget}. "
            f"Filter: {filter_query}. Status: {filter_status}. Position: {filter_position}. "
            f"{structure_hint}"
        )
        tree_summary = f"Widget tree: {widget_count}. {selected_count}. Current widget: {current_widget}."
        _set_widget_metadata(self, tooltip=summary, accessible_name=summary)
        _set_widget_metadata(
            self._header_frame,
            tooltip=f"Widget tree header. {summary}",
            accessible_name=f"Widget tree header. {summary}",
        )
        _set_widget_metadata(
            self._title_label,
            tooltip="Widget tree title: Structure.",
            accessible_name="Widget tree title: Structure.",
        )
        if hasattr(self, "_header_meta_label"):
            _set_widget_metadata(
                self._header_meta_label,
                tooltip=self._header_meta_label.text(),
                accessible_name=self._header_meta_label.text(),
            )
        _set_widget_metadata(
            self.structure_hint_label,
            tooltip=structure_hint,
            accessible_name=structure_hint,
        )
        if hasattr(self, "drag_target_label"):
            _set_widget_metadata(
                self.drag_target_label,
                tooltip=drag_target_text,
                accessible_name=drag_target_text,
            )
        _set_widget_metadata(
            self.tree,
            tooltip=tree_summary,
            accessible_name=tree_summary,
        )

    def _structure_hint_text(self, state=None):
        state = state or self._structure_action_state()
        widgets = state.widgets
        if not widgets and not state.blocked_reason:
            return "Structure: select widgets to group, move, or reorder." + self._structure_history_hint_suffix()

        hints = []
        if state.can_group:
            hints.append("Ctrl+G group siblings")
        if state.can_ungroup:
            hints.append("Ctrl+Shift+G ungroup")
        if state.can_move_into:
            hints.append("Ctrl+Shift+I move into container")
            repeat_target = self._repeat_move_target_summary(widgets)
            if repeat_target:
                hints.append(f"Ctrl+Alt+I repeat into {repeat_target}")
        if state.can_lift:
            hints.append("Ctrl+Shift+L lift to parent")
        if state.can_move_up and state.can_move_down:
            hints.append("Alt+Up/Down reorder")
        elif state.can_move_up:
            hints.append("Alt+Up reorder")
        elif state.can_move_down:
            hints.append("Alt+Down reorder")
        if state.can_move_top and state.can_move_bottom:
            hints.append("Alt+Shift+Up/Down move to edge")
        elif state.can_move_top:
            hints.append("Alt+Shift+Up move to top")
        elif state.can_move_bottom:
            hints.append("Alt+Shift+Down move to bottom")
        if hints:
            return "Structure: " + "; ".join(hints) + "."
        if state.blocked_reason:
            return f"Structure: {state.blocked_reason}" + self._structure_history_hint_suffix()
        return "Structure: no valid structure actions for the current selection." + self._structure_history_hint_suffix()

    def _emit_tree_changed(self, source):
        self.tree_changed.emit(source or "widget tree change")

    def _apply_structure_result(self, result):
        if not result.changed:
            if result.message:
                self.feedback_message.emit(result.message)
            return False

        self.rebuild_tree()
        self.set_selected_widgets(result.widgets, primary=result.primary)
        self._emit_tree_changed(result.source)
        if result.message:
            self.feedback_message.emit(result.message)
        return True

    def _choose_move_target_choice(self, widgets):
        choices = self._quick_move_target_choices(widgets)
        if not choices:
            self.feedback_message.emit("Cannot move into container: no eligible target containers are available.")
            return None

        labels = [choice.label for choice in choices]
        selected_label, ok = QInputDialog.getItem(
            self,
            "Move Into Container",
            "Target container (recent targets first):",
            labels,
            self._move_target_default_index(choices),
            False,
        )
        if not ok or not selected_label:
            return None

        for choice in choices:
            if choice.label == selected_label:
                return choice
        return None

    def _on_add_clicked(self):
        self.browse_widgets_requested.emit(self._default_insert_parent())

    def _default_insert_parent(self):
        selected = self._get_selected_widget()
        if selected is not None and getattr(selected, "is_container", False):
            return selected
        if selected is not None and getattr(selected, "parent", None) is not None and getattr(selected.parent, "is_container", False):
            return selected.parent
        if self.project and self.project.root_widgets:
            root = self.project.root_widgets[0]
            if getattr(root, "is_container", False):
                return root
        return None

    def _recent_widget_types(self):
        valid = {type_name for _display, type_name in _get_addable_types()}
        return [widget_type for widget_type in self._config.widget_browser_recent if widget_type in valid]

    def _on_rename_clicked(self):
        widgets = self.selected_widgets()
        if len(widgets) > 1:
            self._rename_selected_widgets(widgets)
            return
        if widgets:
            self._rename_widget(widgets[0])

    def insert_widget(self, widget_type, parent=None):
        if not self.project:
            return None

        widget = WidgetModel(widget_type)
        widget.name = self._make_unique_widget_name(widget.name)

        target_parent = parent or self._default_insert_parent()
        if target_parent is not None and getattr(target_parent, "is_container", False):
            target_parent.add_child(widget)
        elif self.project.root_widgets:
            # Add to first root if it's a container
            root = self.project.root_widgets[0]
            if root.is_container:
                root.add_child(widget)
            else:
                self.project.root_widgets.append(widget)
        else:
            self.project.root_widgets.append(widget)

        self.rebuild_tree()
        self.set_selected_widgets([widget], primary=widget)
        self._emit_tree_changed("widget add")
        self._config.record_widget_browser_recent(widget_type)
        return widget

    def _add_widget(self, widget_type):
        self.insert_widget(widget_type)

    def _on_delete_clicked(self):
        widgets = self.selected_widgets()
        if not widgets:
            return

        deletable = [widget for widget in widgets if not getattr(widget, "designer_locked", False)]
        locked_count = len(widgets) - len(deletable)
        if not deletable:
            if locked_count:
                self.feedback_message.emit(f"Cannot delete selection: {self._locked_widget_summary(locked_count)}.")
            return

        deleted_widgets = self._top_level_selected_widgets(deletable)
        removed_targets = self.forget_move_targets_for_widgets(deleted_widgets)
        deleted_count = 0
        for widget in deleted_widgets:
            if widget.parent:
                widget.parent.remove_child(widget)
            elif widget in self.project.root_widgets:
                self.project.root_widgets.remove(widget)
            deleted_count += 1

        self.rebuild_tree()
        self.set_selected_widgets([], primary=None)
        self._emit_tree_changed("widget delete")
        extras = []
        if removed_targets:
            extras.append(self._cleared_move_target_history_text(removed_targets))
        if locked_count:
            extras.append(f"skipped {self._locked_widget_summary(locked_count)}")
        if extras:
            self.feedback_message.emit(f"Deleted {deleted_count} widget(s); " + "; ".join(extras))

    def _on_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if item is None:
            return

        widget = self._widget_map.get(id(item))
        if widget is None:
            return

        menu = self._build_context_menu(widget)
        if menu is None:
            return
        menu.exec_(self.tree.viewport().mapToGlobal(pos))

    def _build_context_menu(self, widget):
        if widget is None:
            return None

        menu = QMenu(self)
        context_widgets = self._context_widgets(widget)
        rename_selected = len(context_widgets) > 1 and widget in context_widgets
        structure_state = self._structure_action_state(context_widgets)

        # Rename
        rename_action = QAction("Rename Selected" if rename_selected else "Rename", self)
        rename_action.setShortcut("F2")
        _set_action_metadata(rename_action, tooltip=self._context_rename_tooltip(widget, context_widgets))
        if rename_selected:
            rename_action.triggered.connect(lambda: self._rename_selected_widgets(context_widgets))
        else:
            rename_action.triggered.connect(lambda: self._rename_widget(widget))
        menu.addAction(rename_action)

        preferred_parent = widget if widget.is_container else getattr(widget, "parent", None)
        insert_action = QAction("Insert Component...", self)
        insert_action.setIcon(make_icon("widgets"))
        _set_action_metadata(insert_action, tooltip=self._context_insert_tooltip(preferred_parent))
        insert_action.triggered.connect(lambda: self.browse_widgets_requested.emit(preferred_parent))
        menu.addAction(insert_action)

        recent_types = self._recent_widget_types()
        if recent_types:
            recent_menu = menu.addMenu("Recent Widgets")
            recent_menu.setToolTipsVisible(True)
            _set_action_metadata(recent_menu.menuAction(), tooltip=self._context_recent_widgets_menu_tooltip(preferred_parent))
            display_names = {type_name: display_name for display_name, type_name in _get_addable_types()}
            for type_name in recent_types[:8]:
                display_name = display_names.get(type_name, WidgetRegistry.instance().display_name(type_name))
                action = QAction(display_name, self)
                action.setIcon(make_icon(widget_icon_key(type_name)))
                _set_action_metadata(action, tooltip=self._context_recent_widget_tooltip(display_name, preferred_parent))
                action.triggered.connect(lambda checked=False, t=type_name, p=preferred_parent: self.insert_widget(t, parent=p))
                recent_menu.addAction(action)

        self._populate_select_menu(menu.addMenu("Select"), widget)

        structure_menu = menu.addMenu("Structure")
        structure_menu.setToolTipsVisible(True)
        group_action = QAction("Group Selection", self)
        group_action.setShortcut("Ctrl+G")
        group_action.setEnabled(structure_state.can_group)
        _set_action_metadata(
            group_action,
            tooltip=self._structure_tooltip("Group the current selection (Ctrl+G)", structure_state.can_group, self._structure_action_reason(structure_state, "group_reason")),
        )
        group_action.triggered.connect(lambda: self._group_selected_widgets(context_widgets))
        structure_menu.addAction(group_action)

        ungroup_action = QAction("Ungroup", self)
        ungroup_action.setShortcut("Ctrl+Shift+G")
        ungroup_action.setEnabled(structure_state.can_ungroup)
        _set_action_metadata(
            ungroup_action,
            tooltip=self._structure_tooltip("Ungroup the selected group widgets (Ctrl+Shift+G)", structure_state.can_ungroup, self._structure_action_reason(structure_state, "ungroup_reason")),
        )
        ungroup_action.triggered.connect(lambda: self._ungroup_selected_widgets(context_widgets))
        structure_menu.addAction(ungroup_action)

        move_into_action = QAction("Move Into...", self)
        move_into_action.setShortcut("Ctrl+Shift+I")
        move_into_action.setEnabled(structure_state.can_move_into)
        _set_action_metadata(
            move_into_action,
            tooltip=self._structure_tooltip("Move the current selection into another container (Ctrl+Shift+I)", structure_state.can_move_into, self._structure_action_reason(structure_state, "move_into_reason")),
        )
        move_into_action.triggered.connect(lambda: self._move_selected_widgets_into(widgets=context_widgets))
        structure_menu.addAction(move_into_action)
        move_into_last_target_action = QAction("Move Into Last Target", self)
        move_into_last_target_action.setShortcut("Ctrl+Alt+I")
        move_into_last_target_choice = self._remembered_move_target_choice(context_widgets)
        move_into_last_target_action.setEnabled(move_into_last_target_choice is not None)
        _set_action_metadata(
            move_into_last_target_action,
            tooltip=self._structure_tooltip(
                self._move_into_last_target_hint(context_widgets),
                move_into_last_target_choice is not None,
                self._move_into_last_target_reason(context_widgets),
            ),
        )
        move_into_last_target_action.triggered.connect(lambda: self._move_selected_widgets_into_last_target(context_widgets))
        structure_menu.addAction(move_into_last_target_action)
        clear_move_target_history_action = QAction("Clear Move Target History", self)
        clear_move_target_history_action.setEnabled(self.has_recent_move_targets())
        _set_action_metadata(
            clear_move_target_history_action,
            tooltip=self._structure_tooltip(
                self._clear_move_target_history_hint(),
                self.has_recent_move_targets(),
                "no recent move targets are saved.",
            ),
        )
        clear_move_target_history_action.triggered.connect(self._clear_move_target_history)
        structure_menu.addAction(clear_move_target_history_action)
        quick_targets = self._quick_move_target_choices(context_widgets)
        if quick_targets or self.remembered_move_target_label() or self.has_recent_move_targets():
            quick_move_menu = structure_menu.addMenu("Quick Move Into")
            quick_move_menu.setToolTipsVisible(True)
            _set_action_metadata(quick_move_menu.menuAction(), tooltip=self._quick_move_menu_hint())
            self._populate_quick_move_menu(quick_move_menu, context_widgets, max_targets=5, include_management_actions=True)

        lift_action = QAction("Lift To Parent", self)
        lift_action.setShortcut("Ctrl+Shift+L")
        lift_action.setEnabled(structure_state.can_lift)
        _set_action_metadata(
            lift_action,
            tooltip=self._structure_tooltip("Lift the current selection to the parent container (Ctrl+Shift+L)", structure_state.can_lift, self._structure_action_reason(structure_state, "lift_reason")),
        )
        lift_action.triggered.connect(lambda: self._lift_selected_widgets(context_widgets))
        structure_menu.addAction(lift_action)

        structure_menu.addSeparator()

        move_up_action = QAction("Move Up", self)
        move_up_action.setShortcut("Alt+Up")
        move_up_action.setEnabled(structure_state.can_move_up)
        _set_action_metadata(
            move_up_action,
            tooltip=self._structure_tooltip("Move the current selection up among its siblings (Alt+Up)", structure_state.can_move_up, self._structure_action_reason(structure_state, "move_up_reason")),
        )
        move_up_action.triggered.connect(lambda: self._move_selected_widgets_up(context_widgets))
        structure_menu.addAction(move_up_action)

        move_down_action = QAction("Move Down", self)
        move_down_action.setShortcut("Alt+Down")
        move_down_action.setEnabled(structure_state.can_move_down)
        _set_action_metadata(
            move_down_action,
            tooltip=self._structure_tooltip("Move the current selection down among its siblings (Alt+Down)", structure_state.can_move_down, self._structure_action_reason(structure_state, "move_down_reason")),
        )
        move_down_action.triggered.connect(lambda: self._move_selected_widgets_down(context_widgets))
        structure_menu.addAction(move_down_action)

        move_top_action = QAction("Move To Top", self)
        move_top_action.setShortcut("Alt+Shift+Up")
        move_top_action.setEnabled(structure_state.can_move_top)
        _set_action_metadata(
            move_top_action,
            tooltip=self._structure_tooltip("Move the current selection to the top of its sibling list (Alt+Shift+Up)", structure_state.can_move_top, self._structure_action_reason(structure_state, "move_top_reason")),
        )
        move_top_action.triggered.connect(lambda: self._move_selected_widgets_to_top(context_widgets))
        structure_menu.addAction(move_top_action)

        move_bottom_action = QAction("Move To Bottom", self)
        move_bottom_action.setShortcut("Alt+Shift+Down")
        move_bottom_action.setEnabled(structure_state.can_move_bottom)
        _set_action_metadata(
            move_bottom_action,
            tooltip=self._structure_tooltip("Move the current selection to the bottom of its sibling list (Alt+Shift+Down)", structure_state.can_move_bottom, self._structure_action_reason(structure_state, "move_bottom_reason")),
        )
        move_bottom_action.triggered.connect(lambda: self._move_selected_widgets_to_bottom(context_widgets))
        structure_menu.addAction(move_bottom_action)
        structure_enabled = any([
            structure_state.can_group,
            structure_state.can_ungroup,
            structure_state.can_move_into,
            structure_state.can_lift,
            structure_state.can_move_up,
            structure_state.can_move_down,
            structure_state.can_move_top,
            structure_state.can_move_bottom,
            self.has_recent_move_targets(),
        ])
        structure_menu.setEnabled(structure_enabled)
        if not structure_enabled and structure_state.blocked_reason:
            _set_action_metadata(structure_menu.menuAction(), tooltip=f"Structure unavailable: {structure_state.blocked_reason}")
        else:
            _set_action_metadata(
                structure_menu.menuAction(),
                tooltip="Group, move, and reorder widgets relative to the current selection.",
            )

        # Delete
        del_action = QAction("Delete", self)
        del_action.setShortcut("Del")
        _set_action_metadata(del_action, tooltip=self._context_delete_tooltip(widget))
        del_action.triggered.connect(lambda: self._delete_widget(widget))
        menu.addAction(del_action)

        return menu

    def _rename_widget(self, widget):
        new_name, ok = QInputDialog.getText(
            self, "Rename Widget", "New name:", text=widget.name
        )
        if ok and new_name:
            valid, resolved_name, message = resolve_widget_name(widget, new_name)
            if not valid:
                QMessageBox.warning(self, "Invalid Widget Name", message)
                return
            widget.name = resolved_name
            self.rebuild_tree()
            self.set_selected_widgets([widget], primary=widget)
            self._emit_tree_changed("widget rename")
            feedback = message or f"Renamed widget to {resolved_name}."
            self.feedback_message.emit(feedback)

    def _rename_selected_widgets(self, widgets=None):
        widgets = [widget for widget in (widgets or self.selected_widgets()) if widget is not None]
        if not widgets:
            return
        if len(widgets) == 1:
            self._rename_widget(widgets[0])
            return

        default_prefix = self._batch_rename_default_prefix(widgets)
        prefix, ok = QInputDialog.getText(
            self, "Batch Rename Widgets", "Prefix:", text=default_prefix
        )
        if not ok:
            return

        normalized = sanitize_widget_name(prefix)
        if not normalized or not is_valid_widget_name(normalized):
            QMessageBox.warning(
                self,
                "Invalid Widget Prefix",
                "Batch rename prefix must be a valid C identifier using letters, numbers, and underscores, and it cannot start with a digit.",
            )
            return

        existing_names = self._existing_widget_names(exclude_widgets=widgets)
        for index, widget in enumerate(widgets, start=1):
            candidate = f"{normalized}_{index}"
            resolved_name = make_unique_widget_name(candidate, existing_names)
            existing_names.add(resolved_name)
            widget.name = resolved_name

        primary = widgets[0]
        self.rebuild_tree()
        self.set_selected_widgets(widgets, primary=primary)
        self._emit_tree_changed("widget rename")
        self.feedback_message.emit(f"Renamed {len(widgets)} widget(s) with prefix '{normalized}'.")

    def _add_child_to(self, parent, widget_type):
        child = WidgetModel(widget_type)
        child.name = self._make_unique_widget_name(child.name)
        parent.add_child(child)
        self.rebuild_tree()
        self.set_selected_widgets([child], primary=child)
        self._emit_tree_changed("widget add")

    def _delete_widget(self, widget):
        if getattr(widget, "designer_locked", False):
            self.feedback_message.emit(f"Cannot delete widget: {widget.name} is locked.")
            return
        removed_targets = self.forget_move_targets_for_widgets([widget])
        if widget.parent:
            widget.parent.remove_child(widget)
        elif widget in self.project.root_widgets:
            self.project.root_widgets.remove(widget)
        self.rebuild_tree()
        self.set_selected_widgets([], primary=None)
        self._emit_tree_changed("widget delete")
        if removed_targets:
            self.feedback_message.emit(f"Deleted widget; {self._cleared_move_target_history_text(removed_targets)}.")

    def _group_selected_widgets(self, widgets=None):
        self._apply_structure_result(group_selection(self.project, widgets or self.selected_widgets()))

    def _ungroup_selected_widgets(self, widgets=None):
        self._apply_structure_result(ungroup_selection(self.project, widgets or self.selected_widgets()))

    def _move_selected_widgets_into(self, target_widget=None, widgets=None, target_label=""):
        widgets = widgets or self.selected_widgets()
        if target_widget is None:
            target_choice = self._choose_move_target_choice(widgets)
            if target_choice is None:
                return
            target_widget = target_choice.widget
            target_label = target_choice.label
        elif not target_label:
            target_label = self._resolve_move_target_label(widgets, target_widget)
        if target_widget is None:
            return
        if self._apply_structure_result(move_into_container(self.project, widgets, target_widget)) and target_label:
            self.remember_move_target(target_widget, target_label)

    def _move_selected_widgets_into_last_target(self, widgets=None):
        widgets = widgets or self.selected_widgets()
        target_choice = self._remembered_move_target_choice(widgets)
        if target_choice is None:
            reason = self._move_into_last_target_reason(widgets).rstrip(".")
            if reason:
                self.feedback_message.emit(f"Cannot move into last target: {reason}.")
            return
        self._move_selected_widgets_into(
            target_widget=target_choice.widget,
            widgets=widgets,
            target_label=target_choice.label,
        )

    def _clear_move_target_history(self):
        if not self.has_recent_move_targets():
            self.feedback_message.emit("Cannot clear move target history: no recent move targets are saved.")
            return
        cleared_count = len(self.recent_move_target_labels())
        self.clear_remembered_move_target_labels()
        self._update_structure_controls()
        self.feedback_message.emit(self._cleared_move_target_history_message(cleared_count))

    def _lift_selected_widgets(self, widgets=None):
        self._apply_structure_result(lift_to_parent(self.project, widgets or self.selected_widgets()))

    def _move_selected_widgets_up(self, widgets=None):
        self._apply_structure_result(move_selection_by_step(self.project, widgets or self.selected_widgets(), -1))

    def _move_selected_widgets_down(self, widgets=None):
        self._apply_structure_result(move_selection_by_step(self.project, widgets or self.selected_widgets(), 1))

    def _move_selected_widgets_to_top(self, widgets=None):
        self._apply_structure_result(move_selection_to_edge(self.project, widgets or self.selected_widgets(), "top"))

    def _move_selected_widgets_to_bottom(self, widgets=None):
        self._apply_structure_result(move_selection_to_edge(self.project, widgets or self.selected_widgets(), "bottom"))

    def _resolve_tree_drop_destination(self, target_widget, drop_position):
        root = self._drop_root_widget()
        if root is None:
            return None, None

        if drop_position == QAbstractItemView.OnViewport:
            return root, len(root.children)

        if target_widget is None:
            return None, None

        if drop_position == QAbstractItemView.AboveItem:
            if target_widget.parent is None:
                return target_widget, 0
            parent = target_widget.parent
            return parent, parent.children.index(target_widget)

        if drop_position == QAbstractItemView.BelowItem:
            if target_widget.parent is None:
                return target_widget, len(target_widget.children)
            parent = target_widget.parent
            return parent, parent.children.index(target_widget) + 1

        if drop_position == QAbstractItemView.OnItem:
            if target_widget.is_container:
                return target_widget, len(target_widget.children)
            if target_widget.parent is not None:
                parent = target_widget.parent
                return parent, parent.children.index(target_widget) + 1
        return None, None

    def _move_selected_widgets_by_tree_drop(self, target_widget, drop_position):
        widgets = self.selected_widgets()
        target_parent, target_index = self._resolve_tree_drop_destination(target_widget, drop_position)
        valid, message = validate_move_widgets_to_parent_index(self.project, widgets, target_parent, target_index)
        if not valid:
            if message:
                self.feedback_message.emit(message)
            return False
        return self._apply_structure_result(
            move_widgets_to_parent_index(self.project, widgets, target_parent, target_index)
        )

    def _handle_tree_drop(self, target_item, drop_position):
        target_widget = self._widget_map.get(id(target_item)) if target_item is not None else None
        return self._move_selected_widgets_by_tree_drop(target_widget, drop_position)

    def _can_drop_selected_widgets(self, target_widget, drop_position):
        widgets = self.selected_widgets()
        target_parent, target_index = self._resolve_tree_drop_destination(target_widget, drop_position)
        if target_parent is None:
            return False
        return can_move_widgets_to_parent_index(self.project, widgets, target_parent, target_index)

    def _can_handle_tree_drop(self, target_item, drop_position):
        target_widget = self._widget_map.get(id(target_item)) if target_item is not None else None
        return self._can_drop_selected_widgets(target_widget, drop_position)

    def _on_tree_drag_hover(self, target_item, drop_position):
        target_widget = self._widget_map.get(id(target_item)) if target_item is not None else None
        target_parent, target_index = self._resolve_tree_drop_destination(target_widget, drop_position)
        valid, message = validate_move_widgets_to_parent_index(self.project, self.selected_widgets(), target_parent, target_index)
        self._update_drag_target_preview(
            target_item=target_item,
            target_widget=target_widget,
            target_parent=target_parent,
            drop_position=drop_position,
            valid=valid,
            message=message,
        )
        if (
            target_item is None
            or target_widget is None
            or not target_widget.is_container
            or drop_position != QAbstractItemView.OnItem
            or target_item.isExpanded()
            or not valid
        ):
            self._drag_hover_expand_timer.stop()
            self._drag_hover_item = None
            self._drag_hover_position = None
            return
        if (
            self._drag_hover_item is target_item
            and self._drag_hover_position == drop_position
            and self._drag_hover_expand_timer.isActive()
        ):
            return
        self._drag_hover_item = target_item
        self._drag_hover_position = drop_position
        self._drag_hover_expand_timer.start()

    def _clear_tree_drag_hover(self):
        self._drag_hover_expand_timer.stop()
        self._drag_hover_item = None
        self._drag_hover_position = None
        self._set_drag_target_item(None)
        self._set_drag_target_label(self._default_drag_target_text(), tone="default")

    def _expand_drag_hover_item(self):
        item = self._drag_hover_item
        self._drag_hover_item = None
        self._drag_hover_position = None
        if item is None or item.isExpanded():
            return
        widget = self._widget_map.get(id(item))
        if widget is None or not widget.is_container:
            return
        item.setExpanded(True)

    def _set_drag_target_item(self, item):
        if self._drag_target_item is item:
            return
        if self._drag_target_item is not None:
            for column in range(self.tree.columnCount()):
                self._drag_target_item.setBackground(column, QBrush())
        self._drag_target_item = item
        if self._drag_target_item is not None:
            brush = QBrush(QColor("#d8ecff"))
            for column in range(self.tree.columnCount()):
                self._drag_target_item.setBackground(column, brush)

    def _format_drag_target_text(self, target_widget, target_parent, drop_position):
        if drop_position == QAbstractItemView.OnViewport and target_parent is not None:
            return f"Drop target: append to {target_parent.name}."
        if target_widget is None:
            return self._default_drag_target_text()
        if drop_position == QAbstractItemView.OnItem:
            if target_widget.is_container:
                return f"Drop target: move into {target_widget.name}."
            return f"Drop target: insert after {target_widget.name}."
        if drop_position == QAbstractItemView.AboveItem:
            return f"Drop target: insert before {target_widget.name}."
        if drop_position == QAbstractItemView.BelowItem:
            if target_widget.parent is None and target_parent is target_widget:
                return f"Drop target: append inside {target_widget.name}."
            return f"Drop target: insert after {target_widget.name}."
        return self._default_drag_target_text()

    def _update_drag_target_preview(self, target_item, target_widget, target_parent, drop_position, valid, message):
        if valid:
            self._set_drag_target_item(target_item)
            self._set_drag_target_label(
                self._format_drag_target_text(target_widget, target_parent, drop_position),
                tone="valid",
            )
            return
        self._set_drag_target_item(None)
        if message:
            self._set_drag_target_label(f"Drop target unavailable: {message}", tone="invalid")
            return
        self._set_drag_target_label(self._default_drag_target_text(), tone="default")

    def _handle_tree_key_press(self, event):
        key = event.key()
        modifiers = event.modifiers()

        if key == Qt.Key_Delete and modifiers == Qt.NoModifier:
            self._on_delete_clicked()
            return True
        if key == Qt.Key_F2 and modifiers == Qt.NoModifier:
            self._on_rename_clicked()
            return True
        if key == Qt.Key_G and modifiers == Qt.ControlModifier:
            self._group_selected_widgets()
            return True
        if key == Qt.Key_G and modifiers == (Qt.ControlModifier | Qt.ShiftModifier):
            self._ungroup_selected_widgets()
            return True
        if key == Qt.Key_I and modifiers == (Qt.ControlModifier | Qt.ShiftModifier):
            self._move_selected_widgets_into()
            return True
        if key == Qt.Key_I and modifiers == (Qt.ControlModifier | Qt.AltModifier):
            self._move_selected_widgets_into_last_target()
            return True
        if key == Qt.Key_L and modifiers == (Qt.ControlModifier | Qt.ShiftModifier):
            self._lift_selected_widgets()
            return True
        if key == Qt.Key_Up and modifiers == Qt.AltModifier:
            self._move_selected_widgets_up()
            return True
        if key == Qt.Key_Down and modifiers == Qt.AltModifier:
            self._move_selected_widgets_down()
            return True
        if key == Qt.Key_Up and modifiers == (Qt.AltModifier | Qt.ShiftModifier):
            self._move_selected_widgets_to_top()
            return True
        if key == Qt.Key_Down and modifiers == (Qt.AltModifier | Qt.ShiftModifier):
            self._move_selected_widgets_to_bottom()
            return True
        return False

    def _top_level_selected_widgets(self, widgets):
        selected_ids = {id(widget) for widget in widgets}
        result = []
        for widget in widgets:
            parent = widget.parent
            skip = False
            while parent is not None:
                if id(parent) in selected_ids:
                    skip = True
                    break
                parent = parent.parent
            if not skip:
                result.append(widget)
        return result

    def _expand_all_items(self):
        self._suppress_expansion_tracking = True
        try:
            self.tree.expandAll()
        finally:
            self._suppress_expansion_tracking = False
        self._expanded_widgets = self._collect_expanded_widget_ids()

    def _collapse_all_items(self):
        self._suppress_expansion_tracking = True
        try:
            self.tree.collapseAll()
        finally:
            self._suppress_expansion_tracking = False
        self._expanded_widgets = set()

    def _batch_rename_default_prefix(self, widgets):
        widget_types = {widget.widget_type for widget in widgets if widget is not None}
        if len(widget_types) == 1:
            return next(iter(widget_types))
        return "widget"

    def _apply_tree_filter(self, _text="", default_expand=False, announce=False):
        query = self.filter_edit.text().strip().lower()
        self._filter_matches = []
        match_count = 0
        self._suppress_expansion_tracking = True
        try:
            for index in range(self.tree.topLevelItemCount()):
                item = self.tree.topLevelItem(index)
                if query:
                    _, item_matches = self._apply_filter_to_item(item, query)
                    match_count += item_matches
                else:
                    self._clear_item_filter(item)
            if not query:
                if default_expand:
                    self.tree.expandAll()
                    self._expanded_widgets = self._collect_expanded_widget_ids()
                else:
                    for index in range(self.tree.topLevelItemCount()):
                        self._restore_item_expansion(self.tree.topLevelItem(index))
        finally:
            self._suppress_expansion_tracking = False
        self._update_filter_status(query, match_count)
        if announce:
            self._announce_filter_feedback()

    def _apply_filter_to_item(self, item, query):
        widget = self._widget_map.get(id(item))
        name = (widget.name if widget is not None else item.text(0)).lower()
        type_name = (widget.widget_type if widget is not None else item.text(1)).lower()
        own_match = query in name or query in type_name
        if own_match and widget is not None:
            self._filter_matches.append(widget)
        child_match = False
        match_count = 1 if own_match else 0
        for index in range(item.childCount()):
            child = item.child(index)
            child_visible, child_matches = self._apply_filter_to_item(child, query)
            match_count += child_matches
            if child_visible:
                child_match = True
        visible = own_match or child_match
        item.setHidden(not visible)
        self._set_item_match_state(item, own_match)
        if visible and item.childCount():
            item.setExpanded(child_match)
        return visible, match_count

    def _clear_item_filter(self, item):
        item.setHidden(False)
        self._set_item_match_state(item, False)
        for index in range(item.childCount()):
            self._clear_item_filter(item.child(index))

    def _tree_item_font(self, item, matched=False):
        font = self.tree.font()
        if matched:
            font.setWeight(QFont.Bold)
            font.setBold(True)
            return font

        if item is not None and item.childCount() > 0:
            font.setWeight(QFont.DemiBold)
        else:
            font.setWeight(QFont.Normal)
        return font

    def _set_item_match_state(self, item, matched):
        for column in range(self.tree.columnCount()):
            item.setFont(column, self._tree_item_font(item, matched))

    def refresh_tree_typography(self):
        """Re-apply match emphasis using the current tree font."""
        query = self.filter_edit.text().strip().lower()
        for item in self._item_map.values():
            widget = self._widget_map.get(id(item))
            matched = False
            if query and widget is not None:
                name = (widget.name or "").lower()
                type_name = (widget.widget_type or "").lower()
                matched = query in name or query in type_name
            self._set_item_match_state(item, matched)

    def _update_filter_status(self, query, match_count):
        has_matches = bool(query and self._filter_matches)
        self.filter_prev_btn.setEnabled(has_matches)
        self.filter_next_btn.setEnabled(has_matches)
        self.filter_select_btn.setEnabled(has_matches)
        if not query:
            self.filter_status_label.setText("All widgets")
            self.filter_position_label.setText("")
            self._update_header_context()
            self._update_filter_accessibility()
            self._update_accessibility_summary()
            return
        if match_count == 0:
            self.filter_status_label.setText("No matches")
            self.filter_position_label.setText("")
            self._update_header_context()
            self._update_filter_accessibility()
            self._update_accessibility_summary()
            return
        noun = "match" if match_count == 1 else "matches"
        self.filter_status_label.setText(f"{match_count} {noun}")
        self._update_filter_position_label()
        self._update_header_context()
        self._update_filter_accessibility()
        self._update_accessibility_summary()

    def _current_filter_matches(self):
        return [widget for widget in self._filter_matches if id(widget) in self._item_map]

    def _update_filter_position_label(self):
        query = self.filter_edit.text().strip()
        matches = self._current_filter_matches()
        if not query or not matches:
            self.filter_position_label.setText("")
            self._update_header_context()
            self._update_filter_accessibility()
            self._update_accessibility_summary()
            return

        current = self._get_selected_widget()
        if current in matches:
            position = matches.index(current) + 1
        else:
            position = 0
        self.filter_position_label.setText(f"{position}/{len(matches)}")
        self._update_header_context()
        self._update_filter_accessibility()
        self._update_accessibility_summary()

    def _filter_feedback_text(self):
        query = self.filter_edit.text().strip()
        matches = self._current_filter_matches()
        if not query:
            return "Widget filter cleared."
        if not matches:
            return f"Widget filter '{query}': no matches."

        noun = "match" if len(matches) == 1 else "matches"
        current = self._get_selected_widget()
        if current in matches:
            position = matches.index(current) + 1
            return f"Widget filter '{query}': {len(matches)} {noun} ({position}/{len(matches)})."
        return f"Widget filter '{query}': {len(matches)} {noun}."

    def _announce_filter_feedback(self):
        message = self._filter_feedback_text()
        if message:
            self.feedback_message.emit(message)

    def _select_previous_filter_match(self):
        self._select_filter_match(step=-1)

    def _select_next_filter_match(self):
        self._select_filter_match(step=1)

    def _select_filter_match(self, step):
        matches = self._current_filter_matches()
        if not matches:
            return

        current = self._get_selected_widget()
        if current in matches:
            current_index = matches.index(current)
            next_index = (current_index + step) % len(matches)
        else:
            next_index = 0 if step > 0 else len(matches) - 1

        target = matches[next_index]
        self._apply_programmatic_selection([target], primary=target)
        self._announce_filter_feedback()

    def _select_all_filter_matches(self):
        matches = self._current_filter_matches()
        if not matches:
            return

        current = self._get_selected_widget()
        primary = current if current in matches else matches[0]
        self._apply_programmatic_selection(matches, primary=primary)
        noun = "match" if len(matches) == 1 else "matches"
        query = self.filter_edit.text().strip()
        self.feedback_message.emit(f"Widget filter '{query}': selected {len(matches)} {noun}.")

    def _restore_item_expansion(self, item):
        widget = self._widget_map.get(id(item))
        item.setExpanded(widget is not None and id(widget) in self._expanded_widgets)
        for index in range(item.childCount()):
            self._restore_item_expansion(item.child(index))

    def _collect_expanded_widget_ids(self):
        expanded = set()
        for index in range(self.tree.topLevelItemCount()):
            self._collect_expanded_widget_ids_from_item(self.tree.topLevelItem(index), expanded)
        return expanded

    def _collect_expanded_widget_ids_from_item(self, item, expanded):
        widget = self._widget_map.get(id(item))
        if widget is not None and item.isExpanded():
            expanded.add(id(widget))
        for index in range(item.childCount()):
            self._collect_expanded_widget_ids_from_item(item.child(index), expanded)

    def _on_item_expanded(self, item):
        if self._building or self._suppress_expansion_tracking or self.filter_edit.text().strip():
            return
        widget = self._widget_map.get(id(item))
        if widget is not None:
            self._expanded_widgets.add(id(widget))

    def _on_item_collapsed(self, item):
        if self._building or self._suppress_expansion_tracking or self.filter_edit.text().strip():
            return
        widget = self._widget_map.get(id(item))
        if widget is not None:
            self._expanded_widgets.discard(id(widget))

    def _reveal_item(self, item):
        parent = item.parent()
        while parent is not None:
            parent.setExpanded(True)
            parent = parent.parent()
        self.tree.scrollToItem(item, QAbstractItemView.PositionAtCenter)

    def _locked_widget_summary(self, count):
        noun = "widget" if count == 1 else "widgets"
        return f"{count} locked {noun}"
