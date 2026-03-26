"""Widget tree panel for EmbeddedGUI Designer."""

import re

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QHBoxLayout, QMenu, QAction, QInputDialog, QAbstractItemView, QMessageBox, QLineEdit, QLabel,
)
from PyQt5.QtCore import pyqtSignal, Qt, QItemSelectionModel, QEvent, QTimer
from PyQt5.QtGui import QColor, QBrush

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
    move_widgets_to_parent_index,
    ungroup_selection,
    validate_move_widgets_to_parent_index,
)
from ..model.widget_model import WidgetModel
from ..model.widget_registry import WidgetRegistry


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

    def __init__(self, parent=None):
        super().__init__(parent)
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
        self._drag_hover_expand_timer = QTimer(self)
        self._drag_hover_expand_timer.setSingleShot(True)
        self._drag_hover_expand_timer.setInterval(350)
        self._drag_hover_expand_timer.timeout.connect(self._expand_drag_hover_item)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # Button bar
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("Add")
        self.add_btn.clicked.connect(self._on_add_clicked)
        self.rename_btn = QPushButton("Rename")
        self.rename_btn.setToolTip("Rename the current selection (F2)")
        self.rename_btn.clicked.connect(self._on_rename_clicked)
        self.del_btn = QPushButton("Delete")
        self.del_btn.setToolTip("Delete the current selection (Del)")
        self.del_btn.clicked.connect(self._on_delete_clicked)
        self.expand_btn = QPushButton("Expand")
        self.expand_btn.clicked.connect(self._expand_all_items)
        self.collapse_btn = QPushButton("Collapse")
        self.collapse_btn.clicked.connect(self._collapse_all_items)
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.rename_btn)
        btn_layout.addWidget(self.del_btn)
        btn_layout.addWidget(self.expand_btn)
        btn_layout.addWidget(self.collapse_btn)
        layout.addLayout(btn_layout)

        structure_layout = QHBoxLayout()
        self.group_btn = QPushButton("Group")
        self.group_btn.setToolTip("Group the current selection (Ctrl+G)")
        self.group_btn.clicked.connect(self._group_selected_widgets)
        self.ungroup_btn = QPushButton("Ungroup")
        self.ungroup_btn.setToolTip("Ungroup the selected group widgets (Ctrl+Shift+G)")
        self.ungroup_btn.clicked.connect(self._ungroup_selected_widgets)
        self.into_btn = QPushButton("Into")
        self.into_btn.setToolTip("Move the current selection into another container (Ctrl+Shift+I)")
        self.into_btn.clicked.connect(self._move_selected_widgets_into)
        self.lift_btn = QPushButton("Lift")
        self.lift_btn.setToolTip("Lift the current selection to the parent container (Ctrl+Shift+L)")
        self.lift_btn.clicked.connect(self._lift_selected_widgets)
        self.up_btn = QPushButton("Up")
        self.up_btn.setToolTip("Move the current selection up among its siblings (Alt+Up)")
        self.up_btn.clicked.connect(self._move_selected_widgets_up)
        self.down_btn = QPushButton("Down")
        self.down_btn.setToolTip("Move the current selection down among its siblings (Alt+Down)")
        self.down_btn.clicked.connect(self._move_selected_widgets_down)
        for button in (
            self.group_btn,
            self.ungroup_btn,
            self.into_btn,
            self.lift_btn,
            self.up_btn,
            self.down_btn,
        ):
            structure_layout.addWidget(button)
        layout.addLayout(structure_layout)
        self.structure_hint_label = QLabel("Structure: select widgets to group, move, or reorder.")
        self.structure_hint_label.setWordWrap(True)
        layout.addWidget(self.structure_hint_label)
        self.drag_target_label = QLabel(self._default_drag_target_text())
        self.drag_target_label.setWordWrap(True)
        layout.addWidget(self.drag_target_label)

        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Filter widgets by name or type")
        self.filter_edit.setClearButtonEnabled(True)
        self.filter_edit.textChanged.connect(self._on_filter_text_changed)
        self.filter_edit.installEventFilter(self)
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(self.filter_edit, 1)
        self.filter_prev_btn = QPushButton("Prev")
        self.filter_prev_btn.clicked.connect(self._select_previous_filter_match)
        self.filter_next_btn = QPushButton("Next")
        self.filter_next_btn.clicked.connect(self._select_next_filter_match)
        self.filter_prev_btn.setEnabled(False)
        self.filter_next_btn.setEnabled(False)
        filter_layout.addWidget(self.filter_prev_btn)
        filter_layout.addWidget(self.filter_next_btn)
        self.filter_position_label = QLabel("")
        filter_layout.addWidget(self.filter_position_label)
        self.filter_status_label = QLabel("All widgets")
        filter_layout.addWidget(self.filter_status_label)
        layout.addLayout(filter_layout)

        # Tree
        self.tree = _StructureTreeWidget(
            drop_handler=self._handle_tree_drop,
            can_drop_handler=self._can_handle_tree_drop,
            key_handler=self._handle_tree_key_press,
            drag_hover_handler=self._on_tree_drag_hover,
            clear_drag_hover_handler=self._clear_tree_drag_hover,
            parent=self,
        )
        self.tree.setHeaderLabels(["Widget", "Type"])
        self.tree.setColumnWidth(0, 140)
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_context_menu)
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)
        self.tree.itemExpanded.connect(self._on_item_expanded)
        self.tree.itemCollapsed.connect(self._on_item_collapsed)
        layout.addWidget(self.tree)
        self._update_structure_controls()

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
        item.setText(1, widget.widget_type)
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
        prefix = []
        if getattr(widget, "designer_locked", False):
            prefix.append("[L]")
        if getattr(widget, "designer_hidden", False):
            prefix.append("[H]")
        if prefix:
            return f"{' '.join(prefix)} {widget.name}"
        return widget.name

    def eventFilter(self, watched, event):
        if watched is self.filter_edit and event.type() == QEvent.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                if event.modifiers() & Qt.ShiftModifier:
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

    def _update_structure_controls(self):
        if not hasattr(self, "group_btn"):
            return
        state = self._structure_action_state()
        self.group_btn.setEnabled(state.can_group)
        self.ungroup_btn.setEnabled(state.can_ungroup)
        self.into_btn.setEnabled(state.can_move_into)
        self.lift_btn.setEnabled(state.can_lift)
        self.up_btn.setEnabled(state.can_move_up)
        self.down_btn.setEnabled(state.can_move_down)
        self.structure_hint_label.setText(self._structure_hint_text(state))

    def _default_drag_target_text(self):
        return "Drop target: drag over the tree to preview where the selection will land."

    def _structure_hint_text(self, state=None):
        state = state or self._structure_action_state()
        widgets = state.widgets
        if not widgets:
            return "Structure: select widgets to group, move, or reorder."
        if any(getattr(widget, "designer_locked", False) for widget in widgets):
            return "Structure: locked widgets cannot be moved or regrouped."

        hints = []
        if state.can_group:
            hints.append("Ctrl+G group siblings")
        if state.can_ungroup:
            hints.append("Ctrl+Shift+G ungroup")
        if state.can_move_into:
            hints.append("Ctrl+Shift+I move into container")
        if state.can_lift:
            hints.append("Ctrl+Shift+L lift to parent")
        if state.can_move_up and state.can_move_down:
            hints.append("Alt+Up/Down reorder")
        elif state.can_move_up:
            hints.append("Alt+Up reorder")
        elif state.can_move_down:
            hints.append("Alt+Down reorder")
        if hints:
            return "Structure: " + "; ".join(hints) + "."
        return "Structure: no valid structure actions for the current selection."

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

    def _choose_move_target(self, widgets):
        choices = available_move_targets(self.project, widgets)
        if not choices:
            self.feedback_message.emit("Cannot move into container: no eligible target containers are available.")
            return None

        labels = [choice.label for choice in choices]
        selected_label, ok = QInputDialog.getItem(
            self,
            "Move Into Container",
            "Target container:",
            labels,
            0,
            False,
        )
        if not ok or not selected_label:
            return None

        for choice in choices:
            if choice.label == selected_label:
                return choice.widget
        return None

    def _on_add_clicked(self):
        menu = QMenu(self)
        for display_name, type_name in _get_addable_types():
            action = QAction(display_name, self)
            action.setData(type_name)
            action.triggered.connect(lambda checked, t=type_name: self._add_widget(t))
            menu.addAction(action)
        menu.exec_(self.add_btn.mapToGlobal(self.add_btn.rect().bottomLeft()))

    def _on_rename_clicked(self):
        widgets = self.selected_widgets()
        if len(widgets) > 1:
            self._rename_selected_widgets(widgets)
            return
        if widgets:
            self._rename_widget(widgets[0])

    def _add_widget(self, widget_type):
        if not self.project:
            return

        widget = WidgetModel(widget_type)
        widget.name = self._make_unique_widget_name(widget.name)

        # Find selected container to add to
        selected = self._get_selected_widget()
        if selected and selected.is_container:
            selected.add_child(widget)
        elif selected and selected.parent and selected.parent.is_container:
            selected.parent.add_child(widget)
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

        deleted_count = 0
        for widget in self._top_level_selected_widgets(deletable):
            if widget.parent:
                widget.parent.remove_child(widget)
            elif widget in self.project.root_widgets:
                self.project.root_widgets.remove(widget)
            deleted_count += 1

        self.rebuild_tree()
        self.set_selected_widgets([], primary=None)
        self._emit_tree_changed("widget delete")
        if locked_count:
            self.feedback_message.emit(f"Deleted {deleted_count} widget(s); skipped {self._locked_widget_summary(locked_count)}")

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
        if rename_selected:
            rename_action.triggered.connect(lambda: self._rename_selected_widgets(context_widgets))
        else:
            rename_action.triggered.connect(lambda: self._rename_widget(widget))
        menu.addAction(rename_action)

        # Add child (if container)
        if widget.is_container:
            add_menu = menu.addMenu("Add Child")
            for display_name, type_name in _get_addable_types():
                action = QAction(display_name, self)
                action.triggered.connect(
                    lambda checked, w=widget, t=type_name: self._add_child_to(w, t)
                )
                add_menu.addAction(action)

        structure_menu = menu.addMenu("Structure")
        group_action = QAction("Group Selection", self)
        group_action.setShortcut("Ctrl+G")
        group_action.setEnabled(structure_state.can_group)
        group_action.triggered.connect(lambda: self._group_selected_widgets(context_widgets))
        structure_menu.addAction(group_action)

        ungroup_action = QAction("Ungroup", self)
        ungroup_action.setShortcut("Ctrl+Shift+G")
        ungroup_action.setEnabled(structure_state.can_ungroup)
        ungroup_action.triggered.connect(lambda: self._ungroup_selected_widgets(context_widgets))
        structure_menu.addAction(ungroup_action)

        move_into_action = QAction("Move Into...", self)
        move_into_action.setShortcut("Ctrl+Shift+I")
        move_into_action.setEnabled(structure_state.can_move_into)
        move_into_action.triggered.connect(lambda: self._move_selected_widgets_into(widgets=context_widgets))
        structure_menu.addAction(move_into_action)

        lift_action = QAction("Lift To Parent", self)
        lift_action.setShortcut("Ctrl+Shift+L")
        lift_action.setEnabled(structure_state.can_lift)
        lift_action.triggered.connect(lambda: self._lift_selected_widgets(context_widgets))
        structure_menu.addAction(lift_action)

        structure_menu.addSeparator()

        move_up_action = QAction("Move Up", self)
        move_up_action.setShortcut("Alt+Up")
        move_up_action.setEnabled(structure_state.can_move_up)
        move_up_action.triggered.connect(lambda: self._move_selected_widgets_up(context_widgets))
        structure_menu.addAction(move_up_action)

        move_down_action = QAction("Move Down", self)
        move_down_action.setShortcut("Alt+Down")
        move_down_action.setEnabled(structure_state.can_move_down)
        move_down_action.triggered.connect(lambda: self._move_selected_widgets_down(context_widgets))
        structure_menu.addAction(move_down_action)
        structure_menu.setEnabled(any([
            structure_state.can_group,
            structure_state.can_ungroup,
            structure_state.can_move_into,
            structure_state.can_lift,
            structure_state.can_move_up,
            structure_state.can_move_down,
        ]))

        # Delete
        del_action = QAction("Delete", self)
        del_action.setShortcut("Del")
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
        if widget.parent:
            widget.parent.remove_child(widget)
        elif widget in self.project.root_widgets:
            self.project.root_widgets.remove(widget)
        self.rebuild_tree()
        self.set_selected_widgets([], primary=None)
        self._emit_tree_changed("widget delete")

    def _group_selected_widgets(self, widgets=None):
        self._apply_structure_result(group_selection(self.project, widgets or self.selected_widgets()))

    def _ungroup_selected_widgets(self, widgets=None):
        self._apply_structure_result(ungroup_selection(self.project, widgets or self.selected_widgets()))

    def _move_selected_widgets_into(self, target_widget=None, widgets=None):
        widgets = widgets or self.selected_widgets()
        target_widget = target_widget or self._choose_move_target(widgets)
        if target_widget is None:
            return
        self._apply_structure_result(move_into_container(self.project, widgets, target_widget))

    def _lift_selected_widgets(self, widgets=None):
        self._apply_structure_result(lift_to_parent(self.project, widgets or self.selected_widgets()))

    def _move_selected_widgets_up(self, widgets=None):
        self._apply_structure_result(move_selection_by_step(self.project, widgets or self.selected_widgets(), -1))

    def _move_selected_widgets_down(self, widgets=None):
        self._apply_structure_result(move_selection_by_step(self.project, widgets or self.selected_widgets(), 1))

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
        self.drag_target_label.setText(self._default_drag_target_text())

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
            self.drag_target_label.setText(
                self._format_drag_target_text(target_widget, target_parent, drop_position)
            )
            return
        self._set_drag_target_item(None)
        if message:
            self.drag_target_label.setText(f"Drop target unavailable: {message}")
            return
        self.drag_target_label.setText(self._default_drag_target_text())

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
        if key == Qt.Key_L and modifiers == (Qt.ControlModifier | Qt.ShiftModifier):
            self._lift_selected_widgets()
            return True
        if key == Qt.Key_Up and modifiers == Qt.AltModifier:
            self._move_selected_widgets_up()
            return True
        if key == Qt.Key_Down and modifiers == Qt.AltModifier:
            self._move_selected_widgets_down()
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

    def _set_item_match_state(self, item, matched):
        for column in range(self.tree.columnCount()):
            font = item.font(column)
            font.setBold(bool(matched))
            item.setFont(column, font)

    def _update_filter_status(self, query, match_count):
        has_matches = bool(query and self._filter_matches)
        self.filter_prev_btn.setEnabled(has_matches)
        self.filter_next_btn.setEnabled(has_matches)
        if not query:
            self.filter_status_label.setText("All widgets")
            self.filter_position_label.setText("")
            return
        if match_count == 0:
            self.filter_status_label.setText("No matches")
            self.filter_position_label.setText("")
            return
        noun = "match" if match_count == 1 else "matches"
        self.filter_status_label.setText(f"{match_count} {noun}")
        self._update_filter_position_label()

    def _update_filter_position_label(self):
        query = self.filter_edit.text().strip()
        matches = [widget for widget in self._filter_matches if id(widget) in self._item_map]
        if not query or not matches:
            self.filter_position_label.setText("")
            return

        current = self._get_selected_widget()
        if current in matches:
            position = matches.index(current) + 1
        else:
            position = 0
        self.filter_position_label.setText(f"{position}/{len(matches)}")

    def _filter_feedback_text(self):
        query = self.filter_edit.text().strip()
        matches = [widget for widget in self._filter_matches if id(widget) in self._item_map]
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
        matches = [widget for widget in self._filter_matches if id(widget) in self._item_map]
        if not matches:
            return

        current = self._get_selected_widget()
        if current in matches:
            current_index = matches.index(current)
            next_index = (current_index + step) % len(matches)
        else:
            next_index = 0 if step > 0 else len(matches) - 1

        target = matches[next_index]
        self.set_selected_widgets([target], primary=target)
        self.widget_selected.emit(target)
        self.selection_changed.emit([target], target)
        self._announce_filter_feedback()

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
