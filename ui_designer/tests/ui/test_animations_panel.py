"""Qt UI tests for AnimationsPanel."""

import pytest

from ui_designer.tests.qt_test_utils import HAS_PYQT5, skip_if_no_qt

if HAS_PYQT5:
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QCheckBox, QComboBox, QFormLayout, QLineEdit, QSpinBox

_skip_no_qt = skip_if_no_qt


def _make_widget(name="title"):
    from ui_designer.model.widget_model import WidgetModel

    return WidgetModel("label", name=name, x=12, y=16, width=100, height=24)


def _detail_row_widgets(panel, label_text):
    for row in range(panel._detail_form.rowCount()):
        label_item = panel._detail_form.itemAt(row, QFormLayout.LabelRole)
        field_item = panel._detail_form.itemAt(row, QFormLayout.FieldRole)
        label_widget = label_item.widget() if label_item is not None else None
        field_widget = field_item.widget() if field_item is not None else None
        if label_widget is not None and label_widget.text() == label_text:
            return label_widget, field_widget
    raise AssertionError(f"detail row {label_text!r} not found")


@_skip_no_qt
class TestAnimationsPanel:
    def test_panel_shows_selected_widget_animations(self, qapp):
        from ui_designer.model.widget_animations import create_default_animation
        from ui_designer.ui.animations_panel import AnimationsPanel

        widget = _make_widget()
        widget.animations = [create_default_animation("alpha")]

        panel = AnimationsPanel()
        panel.set_selection([widget], primary=widget)
        header_layout = panel._header_frame.layout()
        header_margins = header_layout.contentsMargins()
        title_row = header_layout.itemAt(1).layout()

        assert panel._summary_label.text() == "Animations: 1 animation on label title"
        assert panel.accessibleName() == "Animations: 1 animation on label title"
        assert panel.toolTip() == panel.accessibleName()
        assert panel.layout().spacing() == 2
        assert (header_margins.left(), header_margins.top(), header_margins.right(), header_margins.bottom()) == (2, 2, 2, 2)
        assert header_layout.spacing() == 2
        assert title_row.spacing() == 2
        assert panel._actions_strip.layout().spacing() == 2
        assert panel._header_eyebrow.accessibleName() == "Motion timeline workspace surface."
        assert panel._header_eyebrow.isHidden() is True
        assert panel._header_frame.accessibleName() == (
            "Animations header. Animations: 1 animation on label title"
        )
        assert panel._selection_chip.text() == "1 animation"
        assert panel._selection_chip.isHidden() is True
        assert panel._selection_chip.accessibleName() == "Animation selection status: 1 animation."
        assert panel._hint_label.text() == "Showing 1 animation on label title. Select a row to inspect details."
        assert panel._hint_label.isHidden() is True
        assert panel._summary_label.toolTip() == panel._summary_label.text()
        assert panel._summary_label.statusTip() == panel._summary_label.toolTip()
        assert panel._summary_label.accessibleName() == panel._summary_label.text()
        assert panel._table.toolTip() == panel._summary_label.text()
        assert panel._table.statusTip() == panel._table.toolTip()
        assert panel._table.accessibleName() == "Animations table: Animations: 1 animation on label title"
        assert panel._table.horizontalHeader().height() == 20
        assert panel._table.verticalHeader().defaultSectionSize() == 26
        assert panel._actions_strip.accessibleName() == "Animation actions: add, duplicate, or remove the selected animation."
        assert panel._add_button.toolTip() == "Add an animation to label title."
        assert panel._add_button.statusTip() == panel._add_button.toolTip()
        assert panel._add_button.accessibleName() == "Add animation to label title"
        assert panel._add_button.minimumHeight() == 22
        assert panel._add_button.maximumHeight() == 22
        assert panel._duplicate_button.toolTip() == "Duplicate the selected animation: alpha."
        assert panel._duplicate_button.statusTip() == panel._duplicate_button.toolTip()
        assert panel._duplicate_button.accessibleName() == "Duplicate animation: alpha"
        assert panel._duplicate_button.minimumHeight() == 22
        assert panel._duplicate_button.maximumHeight() == 22
        assert panel._remove_button.toolTip() == "Remove the selected animation: alpha."
        assert panel._remove_button.statusTip() == panel._remove_button.toolTip()
        assert panel._remove_button.accessibleName() == "Remove animation: alpha"
        assert panel._remove_button.minimumHeight() == 22
        assert panel._remove_button.maximumHeight() == 22
        assert panel._detail_group.title() == ""
        assert panel._detail_group.isFlat() is True
        assert panel._detail_group.toolTip() == "Selected animation details: alpha. Duration 500 ms. Interpolator linear."
        assert panel._detail_group.accessibleName() == panel._detail_group.toolTip()
        assert panel._table.rowCount() == 1
        assert panel._table.rowHeight(0) == 26
        assert panel._table.item(0, 0).text() == "alpha"
        assert panel._table.item(0, 2).text() == "linear"
        assert panel._table.item(0, 0).toolTip() == "Animation Type: alpha."
        assert panel._table.item(0, 0).statusTip() == panel._table.item(0, 0).toolTip()
        assert panel._table.item(0, 0).data(Qt.AccessibleTextRole) == panel._table.item(0, 0).toolTip()
        assert panel._table.item(0, 3).toolTip() == "Animation Auto Start: Yes."
        assert panel._table.item(0, 3).statusTip() == panel._table.item(0, 3).toolTip()
        assert panel._table.item(0, 3).data(Qt.AccessibleTextRole) == panel._table.item(0, 3).toolTip()
        type_label, type_combo = _detail_row_widgets(panel, "Type:")
        assert isinstance(type_combo, QComboBox)
        assert type_label.toolTip() == "Animation field label: Type."
        assert type_label.statusTip() == type_label.toolTip()
        assert type_label.accessibleName() == type_label.toolTip()
        assert type_combo.minimumHeight() == 22
        assert type_combo.maximumHeight() == 22
        assert type_combo.toolTip() == "Type for animation alpha on label title. Current value: alpha."
        assert type_combo.statusTip() == type_combo.toolTip()
        assert type_combo.accessibleName() == "Animation Type: alpha."
        duration_label, duration_spin = _detail_row_widgets(panel, "Duration (ms):")
        assert isinstance(duration_spin, QSpinBox)
        assert duration_label.accessibleName() == "Animation field label: Duration (ms)."
        assert duration_spin.minimumHeight() == 22
        assert duration_spin.maximumHeight() == 22
        assert duration_spin.toolTip() == "Duration (ms) for animation alpha on label title. Current value: 500."
        assert duration_spin.accessibleName() == "Animation Duration (ms): 500."
        interpolator_label, interpolator_combo = _detail_row_widgets(panel, "Interpolator:")
        assert isinstance(interpolator_combo, QComboBox)
        assert interpolator_label.accessibleName() == "Animation field label: Interpolator."
        assert interpolator_combo.minimumHeight() == 22
        assert interpolator_combo.maximumHeight() == 22
        assert interpolator_combo.toolTip() == (
            "Interpolator for animation alpha on label title. Current value: linear."
        )
        assert interpolator_combo.accessibleName() == "Animation Interpolator: linear."
        repeat_count_label, repeat_count_spin = _detail_row_widgets(panel, "Repeat Count:")
        assert isinstance(repeat_count_spin, QSpinBox)
        assert repeat_count_label.accessibleName() == "Animation field label: Repeat Count."
        assert repeat_count_spin.minimumHeight() == 22
        assert repeat_count_spin.maximumHeight() == 22
        assert repeat_count_spin.toolTip() == (
            "Repeat Count for animation alpha on label title. Current value: 0."
        )
        assert repeat_count_spin.accessibleName() == "Animation Repeat Count: 0."
        repeat_mode_label, repeat_mode_combo = _detail_row_widgets(panel, "Repeat Mode:")
        assert isinstance(repeat_mode_combo, QComboBox)
        assert repeat_mode_label.accessibleName() == "Animation field label: Repeat Mode."
        assert repeat_mode_combo.minimumHeight() == 22
        assert repeat_mode_combo.maximumHeight() == 22
        assert repeat_mode_combo.toolTip() == (
            "Repeat Mode for animation alpha on label title. Current value: restart."
        )
        assert repeat_mode_combo.accessibleName() == "Animation Repeat Mode: restart."
        auto_start_check = next(
            check for check in panel.findChildren(QCheckBox) if check.text() == "Start automatically"
        )
        assert auto_start_check.minimumHeight() == 22
        assert auto_start_check.maximumHeight() == 22
        assert auto_start_check.toolTip() == (
            "Auto Start for animation alpha on label title. Current value: enabled."
        )
        assert auto_start_check.statusTip() == auto_start_check.toolTip()
        assert auto_start_check.accessibleName() == "Animation Auto Start: enabled."

    def test_panel_add_duplicate_remove_animation_emits_changes(self, qapp):
        from ui_designer.ui.animations_panel import AnimationsPanel

        widget = _make_widget()
        panel = AnimationsPanel()
        panel.set_selection([widget], primary=widget)
        captured = []
        panel.animations_changed.connect(lambda animations: captured.append(animations))

        panel._on_add_animation()
        qapp.processEvents()
        assert panel._table.rowCount() == 1
        assert panel._duplicate_button.toolTip() == "Duplicate the selected animation: alpha."
        assert panel._duplicate_button.accessibleName() == "Duplicate animation: alpha"
        assert panel._remove_button.toolTip() == "Remove the selected animation: alpha."
        assert panel._remove_button.accessibleName() == "Remove animation: alpha"
        assert captured[-1][0].anim_type == "alpha"

        panel._on_duplicate_animation()
        qapp.processEvents()
        assert panel._table.rowCount() == 2
        assert captured[-1][1].anim_type == "alpha"

        panel._table.selectRow(1)
        panel._on_remove_animation()
        qapp.processEvents()
        assert panel._table.rowCount() == 1
        assert len(captured[-1]) == 1

    def test_header_frame_hint_skips_no_op_rewrites(self, qapp, monkeypatch):
        from ui_designer.ui.animations_panel import AnimationsPanel

        widget = _make_widget()
        panel = AnimationsPanel()
        panel._header_frame.setProperty("_animations_panel_hint_snapshot", None)

        hint_calls = 0
        original_set_tooltip = panel._header_frame.setToolTip

        def counted_set_tooltip(text):
            nonlocal hint_calls
            hint_calls += 1
            return original_set_tooltip(text)

        monkeypatch.setattr(panel._header_frame, "setToolTip", counted_set_tooltip)

        panel._update_summary()
        assert hint_calls == 1

        panel._update_summary()
        assert hint_calls == 1

        panel.set_selection([widget], primary=widget)
        assert hint_calls == 2
        panel.deleteLater()

    def test_header_frame_accessible_name_skips_no_op_rewrites(self, qapp, monkeypatch):
        from ui_designer.ui.animations_panel import AnimationsPanel

        widget = _make_widget()
        panel = AnimationsPanel()
        panel._header_frame.setProperty("_animations_panel_accessible_snapshot", None)

        accessible_calls = 0
        original_set_accessible_name = panel._header_frame.setAccessibleName

        def counted_set_accessible_name(text):
            nonlocal accessible_calls
            accessible_calls += 1
            return original_set_accessible_name(text)

        monkeypatch.setattr(panel._header_frame, "setAccessibleName", counted_set_accessible_name)

        panel._update_summary()
        assert accessible_calls == 1

        panel._update_summary()
        assert accessible_calls == 1

        panel.set_selection([widget], primary=widget)
        assert accessible_calls == 2
        panel.deleteLater()

    def test_detail_form_spacing_follows_runtime_tokens(self, qapp, monkeypatch):
        import ui_designer.ui.animations_panel as animations_panel_module
        from ui_designer.ui.animations_panel import AnimationsPanel

        spacing_tokens = dict(animations_panel_module.app_theme_tokens())
        spacing_tokens["space_sm"] = 7
        spacing_tokens["space_xs"] = 3
        monkeypatch.setattr(animations_panel_module, "app_theme_tokens", lambda *args, **kwargs: spacing_tokens)

        panel = AnimationsPanel()

        assert panel._detail_form.horizontalSpacing() == 7
        assert panel._detail_form.verticalSpacing() == 3
        panel.deleteLater()

    def test_panel_type_change_rebuilds_detail_params(self, qapp):
        from ui_designer.ui.animations_panel import AnimationsPanel

        widget = _make_widget()
        panel = AnimationsPanel()
        panel.set_selection([widget], primary=widget)
        panel._on_add_animation()
        qapp.processEvents()

        type_combo = panel._detail_form.itemAt(0, QFormLayout.FieldRole).widget()
        assert isinstance(type_combo, QComboBox)

        type_combo.setCurrentText("translate")
        qapp.processEvents()

        assert panel._table.item(0, 0).text() == "translate"
        labels = []
        for row in range(panel._detail_form.rowCount()):
            item = panel._detail_form.itemAt(row, QFormLayout.LabelRole)
            if item and item.widget():
                labels.append(item.widget().text())
        assert "From X:" in labels
        assert "To Y:" in labels

    def test_panel_param_edit_updates_animation_model(self, qapp):
        from ui_designer.model.widget_animations import create_default_animation
        from ui_designer.ui.animations_panel import AnimationsPanel

        widget = _make_widget()
        widget.animations = [create_default_animation("translate")]
        panel = AnimationsPanel()
        panel.set_selection([widget], primary=widget)
        captured = []
        panel.animations_changed.connect(lambda animations: captured.append(animations))

        target_editor = None
        for row in range(panel._detail_form.rowCount()):
            label_item = panel._detail_form.itemAt(row, QFormLayout.LabelRole)
            field_item = panel._detail_form.itemAt(row, QFormLayout.FieldRole)
            if label_item and label_item.widget() and label_item.widget().text() == "To Y:":
                target_editor = field_item.widget()
                break

        assert isinstance(target_editor, QLineEdit)
        assert target_editor.toolTip() == "To Y for animation translate on label title. Current value: 32."
        assert target_editor.accessibleName() == "Animation To Y: 32."
        target_editor.setText("64")
        target_editor.editingFinished.emit()
        qapp.processEvents()

        assert captured[-1][0].params["to_y"] == "64"
        assert target_editor.toolTip() == "To Y for animation translate on label title. Current value: 64."
        assert target_editor.accessibleName() == "Animation To Y: 64."

    def test_panel_marks_detail_group_when_selected_widget_has_no_animations(self, qapp):
        from ui_designer.ui.animations_panel import AnimationsPanel

        widget = _make_widget()
        panel = AnimationsPanel()
        panel.set_selection([widget], primary=widget)

        assert panel._detail_group.title() == ""
        assert panel._detail_group.isFlat() is True
        assert panel._detail_group.toolTip() == (
            "Selected animation details unavailable. No animations on the selected widget."
        )
        assert panel._detail_group.accessibleName() == panel._detail_group.toolTip()

    def test_panel_disables_multi_selection_editing(self, qapp):
        from ui_designer.ui.animations_panel import AnimationsPanel

        primary = _make_widget("primary")
        secondary = _make_widget("secondary")
        panel = AnimationsPanel()
        panel.set_selection([primary, secondary], primary=primary)

        assert "select a single widget" in panel._summary_label.text().lower()
        assert panel.accessibleName() == "Animations: select a single widget (2 selected)"
        assert panel.toolTip() == panel.accessibleName()
        assert panel._selection_chip.text() == "2 Selected"
        assert panel._selection_chip.isHidden() is True
        assert panel._selection_chip.accessibleName() == "Animation selection status: 2 Selected."
        assert panel._hint_label.text() == "Animation editing is available for a single selected widget only."
        assert panel._table.toolTip() == "Animations: select a single widget (2 selected)"
        assert panel._table.accessibleName() == (
            "Animations table: Animations: select a single widget (2 selected)"
        )
        assert panel._add_button.isEnabled() is False
        assert panel._add_button.toolTip() == "Select a single widget to add an animation."
        assert panel._add_button.accessibleName() == "Add animation unavailable"
        assert panel._duplicate_button.toolTip() == "Select a single widget to duplicate an animation."
        assert panel._duplicate_button.accessibleName() == "Duplicate animation unavailable"
        assert panel._remove_button.toolTip() == "Select a single widget to remove an animation."
        assert panel._remove_button.accessibleName() == "Remove animation unavailable"
        assert panel._detail_group.accessibleName() == (
            "Selected animation details unavailable. "
            "Animation editing is available for a single selected widget only."
        )
        assert panel._actions_strip.accessibleName() == (
            "Animation actions unavailable. Select a single widget to edit animations."
        )
