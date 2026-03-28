"""Editor panel for widget animations."""

from __future__ import annotations

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..model.widget_animations import (
    ANIMATION_REPEAT_MODES,
    animation_interpolator_names,
    animation_param_choices,
    animation_param_defaults,
    animation_type_names,
    clone_animation,
    create_default_animation,
    normalize_widget_animations,
)
from .iconography import make_icon


def _set_widget_metadata(widget, *, tooltip=None, accessible_name=None):
    if tooltip is not None:
        widget.setToolTip(tooltip)
        widget.setStatusTip(tooltip)
    if accessible_name is not None:
        widget.setAccessibleName(accessible_name)


def _set_item_metadata(item, tooltip):
    item.setToolTip(tooltip)
    item.setStatusTip(tooltip)
    item.setData(Qt.AccessibleTextRole, tooltip)


class AnimationsPanel(QWidget):
    """Editable list of animations for the currently selected widget."""

    animations_changed = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._selection = []
        self._primary_widget = None
        self._animations = []
        self._updating = False
        self._init_ui()
        self.clear()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self._summary_label = QLabel("")
        self._summary_label.setObjectName("workspace_section_title")
        self._hint_label = QLabel(
            "Animations are stored on the selected widget and compiled into the generated layout source."
        )
        self._hint_label.setObjectName("workspace_section_subtitle")
        self._hint_label.setWordWrap(True)
        _set_widget_metadata(
            self._hint_label,
            tooltip=self._hint_label.text(),
            accessible_name=self._hint_label.text(),
        )

        self._table = QTableWidget(0, 4, self)
        self._table.setHorizontalHeaderLabels(["Type", "Duration", "Interpolator", "Auto Start"])
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._table.itemSelectionChanged.connect(self._on_row_selected)
        self._table.setAccessibleName("Animations table")

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(6)
        self._add_button = QPushButton("Add Animation")
        self._add_button.setIcon(make_icon("animation"))
        self._duplicate_button = QPushButton("Duplicate")
        self._duplicate_button.setIcon(make_icon("page"))
        self._remove_button = QPushButton("Remove")
        self._remove_button.setIcon(make_icon("stop"))
        self._add_button.clicked.connect(self._on_add_animation)
        self._duplicate_button.clicked.connect(self._on_duplicate_animation)
        self._remove_button.clicked.connect(self._on_remove_animation)
        buttons.addWidget(self._add_button)
        buttons.addWidget(self._duplicate_button)
        buttons.addWidget(self._remove_button)
        buttons.addStretch(1)

        self._detail_group = QGroupBox("Selected Animation")
        self._detail_form = QFormLayout()
        self._detail_group.setLayout(self._detail_form)

        layout.addWidget(self._summary_label)
        layout.addWidget(self._hint_label)
        layout.addWidget(self._table, 1)
        layout.addLayout(buttons)
        layout.addWidget(self._detail_group)
        self._update_actions()
        self._update_detail_group_metadata("Selected animation details unavailable. Select a widget to edit animations.")

    def _update_accessibility_summary(self, summary_text):
        _set_widget_metadata(self, tooltip=summary_text, accessible_name=summary_text)
        _set_widget_metadata(self._summary_label, tooltip=summary_text, accessible_name=summary_text)
        _set_widget_metadata(
            self._table,
            tooltip=summary_text,
            accessible_name=f"Animations table: {summary_text}",
        )

    def _update_action_button_metadata(self, button, label, tooltip, enabled):
        accessible_name = label if enabled else f"{label} unavailable"
        _set_widget_metadata(button, tooltip=tooltip, accessible_name=accessible_name)

    def _update_detail_group_metadata(self, summary_text):
        _set_widget_metadata(
            self._detail_group,
            tooltip=summary_text,
            accessible_name=summary_text,
        )

    def _selected_animation_label(self):
        row = self._selected_row()
        if row < 0 or row >= len(self._animations):
            return ""
        return str(self._animations[row].anim_type or "").strip()

    def clear(self):
        self.set_selection([], primary=None)

    def set_selection(self, widgets, primary=None):
        widgets = [widget for widget in (widgets or []) if widget is not None]
        self._selection = list(widgets)
        if primary is None or all(widget is not primary for widget in widgets):
            primary = widgets[-1] if widgets else None
        self._primary_widget = primary if len(widgets) == 1 else None
        selected_row = self._selected_row()
        self._animations = normalize_widget_animations(getattr(self._primary_widget, "animations", []))
        self._rebuild_table(selected_row=selected_row)

    def refresh(self):
        self.set_selection(self._selection, primary=self._primary_widget)

    def _selected_row(self):
        selection_model = self._table.selectionModel()
        if selection_model is None:
            return -1
        rows = selection_model.selectedRows()
        if not rows:
            return -1
        return rows[0].row()

    def _clear_form_layout(self):
        while self._detail_form.rowCount():
            self._detail_form.removeRow(0)

    def _rebuild_table(self, selected_row=-1):
        self._updating = True
        self._table.setRowCount(len(self._animations))
        for row, animation in enumerate(self._animations):
            values = [
                animation.anim_type,
                str(animation.duration),
                animation.interpolator,
                "Yes" if animation.auto_start else "No",
            ]
            hints = [
                f"Animation Type: {animation.anim_type or 'none'}.",
                f"Animation Duration: {animation.duration} ms.",
                f"Animation Interpolator: {animation.interpolator or 'none'}.",
                f"Animation Auto Start: {'Yes' if animation.auto_start else 'No'}.",
            ]
            for column, (value, hint) in enumerate(zip(values, hints)):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                _set_item_metadata(item, hint)
                self._table.setItem(row, column, item)
        self._updating = False

        if self._primary_widget is not None and self._animations:
            row = selected_row if 0 <= selected_row < len(self._animations) else 0
            self._table.selectRow(row)
        self._update_summary()
        self._update_actions()
        self._rebuild_detail_form()

    def _update_summary(self):
        if not self._selection:
            summary_text = "Animations: no widget selected"
            self._summary_label.setText(summary_text)
            self._update_accessibility_summary(summary_text)
            return
        if len(self._selection) > 1 or self._primary_widget is None:
            summary_text = f"Animations: select a single widget ({len(self._selection)} selected)"
            self._summary_label.setText(summary_text)
            self._update_accessibility_summary(summary_text)
            return

        count = len(self._animations)
        noun = "animation" if count == 1 else "animations"
        summary_text = f"Animations: {count} {noun} on {self._primary_widget.widget_type} {self._primary_widget.name}"
        self._summary_label.setText(summary_text)
        self._update_accessibility_summary(summary_text)

    def _update_actions(self):
        has_widget = self._primary_widget is not None
        selected_animation = self._selected_animation_label()
        has_selection = bool(selected_animation)
        self._table.setEnabled(has_widget)
        self._detail_group.setEnabled(has_widget and has_selection)
        self._add_button.setEnabled(has_widget)
        self._duplicate_button.setEnabled(has_widget and has_selection)
        self._remove_button.setEnabled(has_widget and has_selection)
        if has_widget:
            widget_label = f"{self._primary_widget.widget_type} {self._primary_widget.name}"
            add_hint = f"Add an animation to {widget_label}."
        else:
            add_hint = "Select a single widget to add an animation."
            widget_label = ""
        if has_widget and has_selection:
            duplicate_hint = f"Duplicate the selected animation: {selected_animation}."
            remove_hint = f"Remove the selected animation: {selected_animation}."
        elif has_widget:
            duplicate_hint = "Select an animation to duplicate it."
            remove_hint = "Select an animation to remove it."
        else:
            duplicate_hint = "Select a single widget to duplicate an animation."
            remove_hint = "Select a single widget to remove an animation."
        self._update_action_button_metadata(
            self._add_button,
            f"Add animation to {widget_label}" if has_widget else "Add animation",
            add_hint,
            has_widget,
        )
        self._update_action_button_metadata(
            self._duplicate_button,
            f"Duplicate animation: {selected_animation}" if has_widget and has_selection else "Duplicate animation",
            duplicate_hint,
            has_widget and has_selection,
        )
        self._update_action_button_metadata(
            self._remove_button,
            f"Remove animation: {selected_animation}" if has_widget and has_selection else "Remove animation",
            remove_hint,
            has_widget and has_selection,
        )

    def _rebuild_detail_form(self):
        self._clear_form_layout()

        if not self._selection:
            message = "Select a widget to edit animations."
            self._detail_form.addRow(QLabel(message))
            self._update_detail_group_metadata(f"Selected animation details unavailable. {message}")
            return

        if len(self._selection) > 1 or self._primary_widget is None:
            message = "Animation editing is available for a single selected widget only."
            self._detail_form.addRow(QLabel(message))
            self._update_detail_group_metadata(f"Selected animation details unavailable. {message}")
            return

        row = self._selected_row()
        if row < 0 or row >= len(self._animations):
            if self._animations:
                message = "Select an animation from the table above."
            else:
                message = "No animations on the selected widget."
            self._detail_form.addRow(QLabel(message))
            self._update_detail_group_metadata(f"Selected animation details unavailable. {message}")
            return

        animation = self._animations[row]
        self._update_detail_group_metadata(
            f"Selected animation details: {animation.anim_type}. "
            f"Duration {animation.duration} ms. Interpolator {animation.interpolator}."
        )

        type_combo = QComboBox()
        type_combo.addItems(animation_type_names())
        type_combo.setCurrentText(animation.anim_type)
        type_combo.currentTextChanged.connect(lambda value, index=row: self._on_type_changed(index, value))
        self._detail_form.addRow("Type:", type_combo)

        duration_spin = QSpinBox()
        duration_spin.setRange(0, 600000)
        duration_spin.setValue(animation.duration)
        duration_spin.valueChanged.connect(lambda value, index=row: self._on_duration_changed(index, value))
        self._detail_form.addRow("Duration (ms):", duration_spin)

        interpolator_combo = QComboBox()
        interpolator_combo.addItems(animation_interpolator_names())
        interpolator_combo.setCurrentText(animation.interpolator)
        interpolator_combo.currentTextChanged.connect(lambda value, index=row: self._on_interpolator_changed(index, value))
        self._detail_form.addRow("Interpolator:", interpolator_combo)

        repeat_count_spin = QSpinBox()
        repeat_count_spin.setRange(0, 9999)
        repeat_count_spin.setValue(animation.repeat_count)
        repeat_count_spin.valueChanged.connect(lambda value, index=row: self._on_repeat_count_changed(index, value))
        self._detail_form.addRow("Repeat Count:", repeat_count_spin)

        repeat_mode_combo = QComboBox()
        repeat_mode_combo.addItems(ANIMATION_REPEAT_MODES)
        repeat_mode_combo.setCurrentText(animation.repeat_mode)
        repeat_mode_combo.currentTextChanged.connect(lambda value, index=row: self._on_repeat_mode_changed(index, value))
        self._detail_form.addRow("Repeat Mode:", repeat_mode_combo)

        auto_start_check = QCheckBox("Start automatically")
        auto_start_check.setChecked(animation.auto_start)
        auto_start_check.toggled.connect(lambda value, index=row: self._on_auto_start_changed(index, value))
        self._detail_form.addRow(auto_start_check)

        for param_name, default_value in animation_param_defaults(animation.anim_type).items():
            editor = self._create_param_editor(row, param_name, animation.params.get(param_name, default_value))
            self._detail_form.addRow(self._label_for_param(param_name), editor)

    def _label_for_param(self, param_name):
        name = str(param_name or "")
        if name.startswith("from_"):
            return "From " + name[len("from_"):].replace("_", " ").title() + ":"
        if name.startswith("to_"):
            return "To " + name[len("to_"):].replace("_", " ").title() + ":"
        return name.replace("_", " ").title() + ":"

    def _create_param_editor(self, row, param_name, value):
        choices = animation_param_choices(param_name)
        if choices:
            editor = QComboBox()
            editor.setEditable(param_name != "mode")
            editor.addItems(choices)
            if editor.findText(str(value)) < 0:
                editor.addItem(str(value))
            editor.setCurrentText(str(value))
            editor.currentTextChanged.connect(lambda text, index=row, key=param_name: self._on_param_changed(index, key, text))
            return editor

        editor = QLineEdit()
        editor.setText(str(value))
        editor.editingFinished.connect(lambda index=row, key=param_name, line_edit=editor: self._on_param_changed(index, key, line_edit.text()))
        return editor

    def _emit_changed(self):
        if self._primary_widget is None:
            return
        self.animations_changed.emit([clone_animation(animation) for animation in self._animations])

    def _schedule_rebuild_table(self, selected_row):
        QTimer.singleShot(0, lambda row=selected_row: self._rebuild_table(selected_row=row))

    def _on_row_selected(self):
        if self._updating:
            return
        self._update_actions()
        self._rebuild_detail_form()

    def _on_add_animation(self):
        if self._primary_widget is None:
            return
        self._animations.append(create_default_animation())
        self._rebuild_table(selected_row=len(self._animations) - 1)
        self._emit_changed()

    def _on_duplicate_animation(self):
        row = self._selected_row()
        if self._primary_widget is None or row < 0 or row >= len(self._animations):
            return
        self._animations.insert(row + 1, clone_animation(self._animations[row]))
        self._rebuild_table(selected_row=row + 1)
        self._emit_changed()

    def _on_remove_animation(self):
        row = self._selected_row()
        if self._primary_widget is None or row < 0 or row >= len(self._animations):
            return
        del self._animations[row]
        next_row = min(row, len(self._animations) - 1)
        self._rebuild_table(selected_row=next_row)
        self._emit_changed()

    def _on_type_changed(self, row, anim_type):
        if self._updating or row < 0 or row >= len(self._animations):
            return
        current = self._animations[row]
        replacement = create_default_animation(anim_type)
        replacement.duration = current.duration
        replacement.interpolator = current.interpolator
        replacement.repeat_count = current.repeat_count
        replacement.repeat_mode = current.repeat_mode
        replacement.auto_start = current.auto_start
        self._animations[row] = replacement
        self._schedule_rebuild_table(row)
        self._emit_changed()

    def _on_duration_changed(self, row, value):
        if row < 0 or row >= len(self._animations):
            return
        self._animations[row].duration = int(value)
        self._schedule_rebuild_table(row)
        self._emit_changed()

    def _on_interpolator_changed(self, row, value):
        if row < 0 or row >= len(self._animations):
            return
        self._animations[row].interpolator = str(value)
        self._schedule_rebuild_table(row)
        self._emit_changed()

    def _on_repeat_count_changed(self, row, value):
        if row < 0 or row >= len(self._animations):
            return
        self._animations[row].repeat_count = int(value)
        self._emit_changed()

    def _on_repeat_mode_changed(self, row, value):
        if row < 0 or row >= len(self._animations):
            return
        self._animations[row].repeat_mode = str(value)
        self._emit_changed()

    def _on_auto_start_changed(self, row, value):
        if row < 0 or row >= len(self._animations):
            return
        self._animations[row].auto_start = bool(value)
        self._schedule_rebuild_table(row)
        self._emit_changed()

    def _on_param_changed(self, row, param_name, value):
        if row < 0 or row >= len(self._animations):
            return
        default_value = animation_param_defaults(self._animations[row].anim_type).get(param_name, "0")
        text = str(value).strip() or str(default_value)
        self._animations[row].params[param_name] = text
        self._emit_changed()
