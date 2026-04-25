"""Qt UI tests for PageFieldsPanel."""

import pytest

from ui_designer.tests.page_builders import build_test_page_with_title
from ui_designer.tests.qt_test_utils import HAS_PYQT5, skip_if_no_qt

if HAS_PYQT5:
    from PyQt5.QtCore import Qt

_skip_no_qt = skip_if_no_qt


@_skip_no_qt
class TestPageFieldsPanel:
    def test_panel_displays_current_page_fields(self, qapp):
        from ui_designer.ui.page_fields_panel import PageFieldsPanel
        from ui_designer.ui.theme import app_theme_tokens

        page, _title = build_test_page_with_title()
        page.user_fields = [
            {"name": "counter", "type": "int", "default": "0"},
            {"name": "buffer", "type": "uint8_t[16]"},
        ]

        panel = PageFieldsPanel()
        panel.set_page(page)
        tokens = app_theme_tokens()
        expected_row_height = int(tokens["h_tab_min"])
        expected_control_height = max(int(tokens["h_tab_min"]) - int(tokens["space_xxs"]), 1)

        header_margins = panel._header_frame.layout().contentsMargins()
        chip_margins = panel._header_chip_row.contentsMargins()
        code_buttons = panel._code_frame.layout().itemAt(2).layout()
        action_buttons = panel._actions_frame.layout().itemAt(1).layout()
        table_layout = panel._table_frame.layout()

        assert panel.layout().spacing() == 2
        assert (header_margins.left(), header_margins.top(), header_margins.right(), header_margins.bottom()) == (1, 1, 1, 1)
        assert panel._header_frame.layout().spacing() == 2
        assert (chip_margins.left(), chip_margins.top(), chip_margins.right(), chip_margins.bottom()) == (0, 0, 0, 0)
        assert panel._header_chip_row.spacing() == 2
        assert panel._code_frame.layout().spacing() == 2
        assert table_layout.spacing() == 2
        assert panel._actions_frame.layout().spacing() == 2
        assert code_buttons.spacing() == 2
        assert action_buttons.spacing() == 2
        assert panel._summary_label.text() == "Page Fields: 2 fields on main_page"
        assert panel.accessibleName() == "Page Fields: 2 fields on main_page. Selected field: none."
        assert panel.toolTip() == panel.accessibleName()
        assert panel._summary_label.toolTip() == panel._summary_label.text()
        assert panel._summary_label.statusTip() == panel._summary_label.toolTip()
        assert panel._summary_label.accessibleName() == panel._summary_label.text()
        assert panel._eyebrow_label.text() == "Fields"
        assert panel._eyebrow_label.accessibleName() == "Page fields engineering surface."
        assert panel._eyebrow_label.isHidden() is True
        assert panel._header_frame.accessibleName() == (
            "Page fields header. Page Fields: 2 fields on main_page. Selected field: none."
        )
        assert panel._header_meta_label.accessibleName() == panel._header_meta_label.text()
        assert panel._header_meta_label.isHidden() is True
        assert panel._count_chip.text() == "2 fields"
        assert panel._count_chip.accessibleName() == "Field count: 2 fields."
        assert panel._selection_chip.text() == "No selection"
        assert panel._selection_chip.accessibleName() == "Field selection: No field selected."
        assert panel._metrics_frame.isHidden() is True
        assert panel._metrics_frame.accessibleName() == "Page fields metrics: 2 fields. No field selected."
        assert panel._hint_label.toolTip() == panel._hint_label.text()
        assert panel._hint_label.statusTip() == panel._hint_label.toolTip()
        assert panel._hint_label.accessibleName() == panel._hint_label.text()
        assert panel._hint_label.isHidden() is True
        assert panel._code_hint_label.toolTip() == panel._code_hint_label.text()
        assert panel._code_hint_label.statusTip() == panel._code_hint_label.toolTip()
        assert panel._code_hint_label.accessibleName() == panel._code_hint_label.text()
        assert panel._code_hint_label.isHidden() is True
        assert panel._code_label.isHidden() is True
        assert panel._table_label.isHidden() is True
        assert panel._actions_label.isHidden() is True
        assert panel._table.toolTip() == panel.accessibleName()
        assert panel._table.statusTip() == panel._table.toolTip()
        assert panel._table.accessibleName() == "Page fields table: Page Fields: 2 fields on main_page. Selected field: none."
        assert panel._table.horizontalHeader().height() == expected_control_height
        assert panel._table.verticalHeader().defaultSectionSize() == expected_row_height
        assert panel._open_on_open_button.toolTip() == "Open the on_open section in main_page user code."
        assert panel._open_on_open_button.statusTip() == panel._open_on_open_button.toolTip()
        assert panel._open_on_open_button.accessibleName() == "Open on_open user code for main_page"
        assert panel._open_on_open_button.minimumHeight() == expected_control_height
        assert panel._open_on_open_button.maximumHeight() == expected_control_height
        assert panel._open_on_close_button.accessibleName() == "Open on_close user code for main_page"
        assert panel._open_on_close_button.minimumHeight() == expected_control_height
        assert panel._open_on_close_button.maximumHeight() == expected_control_height
        assert panel._open_init_button.accessibleName() == "Open init user code for main_page"
        assert panel._open_init_button.minimumHeight() == expected_control_height
        assert panel._open_init_button.maximumHeight() == expected_control_height
        assert panel._add_button.toolTip() == "Add a page field."
        assert panel._add_button.accessibleName() == "Add page field to main_page"
        assert panel._add_button.statusTip() == panel._add_button.toolTip()
        assert panel._add_button.minimumHeight() == expected_control_height
        assert panel._add_button.maximumHeight() == expected_control_height
        assert panel._remove_button.toolTip() == "Select a field to remove it."
        assert panel._remove_button.accessibleName() == "Remove page field unavailable"
        assert panel._remove_button.minimumHeight() == expected_control_height
        assert panel._remove_button.maximumHeight() == expected_control_height
        assert panel._table.rowCount() == 2
        assert panel._table.rowHeight(0) == expected_row_height
        assert panel._table.item(0, 0).text() == "counter"
        assert panel._table.item(0, 1).text() == "int"
        assert panel._table.item(0, 2).text() == "0"
        assert panel._table.item(1, 0).text() == "buffer"
        assert panel._table.item(0, 0).toolTip() == "Page field Name: counter."
        assert panel._table.item(0, 0).statusTip() == panel._table.item(0, 0).toolTip()
        assert panel._table.item(0, 0).data(Qt.AccessibleTextRole) == panel._table.item(0, 0).toolTip()
        assert panel._table.item(1, 2).toolTip() == "Page field Default: none."
        assert panel._table.item(1, 2).statusTip() == panel._table.item(1, 2).toolTip()
        assert panel._table.item(1, 2).data(Qt.AccessibleTextRole) == panel._table.item(1, 2).toolTip()

    def test_panel_row_height_follows_runtime_tokens(self, qapp, monkeypatch):
        import ui_designer.ui.page_fields_panel as page_fields_panel_module
        from ui_designer.ui.page_fields_panel import PageFieldsPanel

        row_tokens = dict(page_fields_panel_module.app_theme_tokens())
        row_tokens["h_tab_min"] = 26
        row_tokens["space_xxs"] = 3
        monkeypatch.setattr(page_fields_panel_module, "app_theme_tokens", lambda *args, **kwargs: row_tokens)

        panel = PageFieldsPanel()

        assert panel._table.verticalHeader().defaultSectionSize() == 26
        assert panel._table.verticalHeader().minimumSectionSize() == 26
        assert panel._table.horizontalHeader().height() == 23
        assert panel._add_button.minimumHeight() == 23
        assert panel._add_button.maximumHeight() == 23
        assert panel._open_on_open_button.minimumHeight() == 23
        assert panel._open_on_open_button.maximumHeight() == 23
        panel.deleteLater()

    def test_panel_marks_actions_unavailable_without_active_page(self, qapp):
        from ui_designer.ui.page_fields_panel import PageFieldsPanel

        panel = PageFieldsPanel()

        assert panel.accessibleName() == "Page Fields: no active page"
        assert panel.toolTip() == panel.accessibleName()
        assert panel._header_frame.accessibleName() == "Page fields header. Page Fields: no active page"
        assert panel._header_meta_label.accessibleName() == panel._header_meta_label.text()
        assert panel._header_meta_label.isHidden() is True
        assert panel._table.toolTip() == "Page Fields: no active page"
        assert panel._table.accessibleName() == "Page fields table: Page Fields: no active page"
        assert panel._code_label.isHidden() is True
        assert panel._table_label.isHidden() is True
        assert panel._actions_label.isHidden() is True
        assert panel._add_button.toolTip() == "Open a page to manage fields."
        assert panel._add_button.accessibleName() == "Add page field unavailable"
        assert panel._remove_button.toolTip() == "Open a page to manage fields."
        assert panel._remove_button.accessibleName() == "Remove page field unavailable"
        assert panel._open_on_open_button.toolTip() == "Open a page to edit the on_open section."
        assert panel._open_on_open_button.accessibleName() == "Open on_open user code unavailable"
        assert panel._open_on_close_button.toolTip() == "Open a page to edit the on_close section."
        assert panel._open_on_close_button.accessibleName() == "Open on_close user code unavailable"
        assert panel._open_init_button.toolTip() == "Open a page to edit the init section."
        assert panel._open_init_button.accessibleName() == "Open init user code unavailable"
        assert panel._count_chip.text() == "0 fields"
        assert panel._selection_chip.text() == "No selection"
        assert panel._metrics_frame.accessibleName() == "Page fields metrics: 0 fields. No field selected."

    def test_header_frame_hint_skips_no_op_rewrites(self, qapp, monkeypatch):
        from ui_designer.ui.page_fields_panel import PageFieldsPanel

        page, _title = build_test_page_with_title()
        page.user_fields = [{"name": "counter", "type": "int", "default": "0"}]

        panel = PageFieldsPanel()
        panel.set_page(page)
        panel._header_frame.setProperty("_page_fields_hint_snapshot", None)

        hint_calls = 0
        original_set_tooltip = panel._header_frame.setToolTip

        def counted_set_tooltip(text):
            nonlocal hint_calls
            hint_calls += 1
            return original_set_tooltip(text)

        monkeypatch.setattr(panel._header_frame, "setToolTip", counted_set_tooltip)

        panel._update_summary()
        assert hint_calls == 1

        panel._update_actions()
        assert hint_calls == 1

        panel._table.selectRow(0)
        qapp.processEvents()
        assert hint_calls == 2

    def test_header_frame_accessible_name_skips_no_op_rewrites(self, qapp, monkeypatch):
        from ui_designer.ui.page_fields_panel import PageFieldsPanel

        page, _title = build_test_page_with_title()
        page.user_fields = [{"name": "counter", "type": "int", "default": "0"}]

        panel = PageFieldsPanel()
        panel.set_page(page)
        panel._header_frame.setProperty("_page_fields_accessible_snapshot", None)

        accessible_calls = 0
        original_set_accessible_name = panel._header_frame.setAccessibleName

        def counted_set_accessible_name(text):
            nonlocal accessible_calls
            accessible_calls += 1
            return original_set_accessible_name(text)

        monkeypatch.setattr(panel._header_frame, "setAccessibleName", counted_set_accessible_name)

        panel._update_summary()
        assert accessible_calls == 1

        panel._update_actions()
        assert accessible_calls == 1

        panel._table.selectRow(0)
        qapp.processEvents()
        assert accessible_calls == 2

    def test_panel_add_and_remove_field_emits_changes(self, qapp):
        from ui_designer.ui.page_fields_panel import PageFieldsPanel

        page, _title = build_test_page_with_title()
        panel = PageFieldsPanel()
        panel.set_page(page)
        captured = []
        panel.fields_changed.connect(lambda fields: captured.append(fields))

        assert panel._remove_button.toolTip() == "Select a field to remove it."
        panel._on_add_field()
        qapp.processEvents()

        assert panel._table.rowCount() == 1
        assert panel.accessibleName() == "Page Fields: 1 field on main_page. Selected field: field."
        assert panel._header_frame.accessibleName() == (
            "Page fields header. Page Fields: 1 field on main_page. Selected field: field."
        )
        assert panel._table.accessibleName() == "Page fields table: Page Fields: 1 field on main_page. Selected field: field."
        assert panel._remove_button.toolTip() == "Remove the selected page field: field."
        assert panel._remove_button.accessibleName() == "Remove page field: field"
        assert panel._count_chip.text() == "1 field"
        assert panel._selection_chip.text() == "field"
        assert panel._selection_chip.accessibleName() == "Field selection: Selected field: field."
        assert panel._metrics_frame.accessibleName() == "Page fields metrics: 1 field. Selected field: field."
        assert captured[-1] == [{"name": "field", "type": "int", "default": "0"}]

        panel._table.selectRow(0)
        assert panel._remove_button.toolTip() == "Remove the selected page field: field."
        panel._on_remove_field()
        qapp.processEvents()

        assert panel._table.rowCount() == 0
        assert panel.accessibleName() == "Page Fields: 0 fields on main_page. Selected field: none."
        assert panel._header_frame.accessibleName() == (
            "Page fields header. Page Fields: 0 fields on main_page. Selected field: none."
        )
        assert captured[-1] == []

    def test_panel_rejects_conflicting_field_name(self, qapp):
        from ui_designer.ui.page_fields_panel import PageFieldsPanel

        page, _title = build_test_page_with_title()
        panel = PageFieldsPanel()
        panel.set_page(page)
        messages = []
        panel.validation_message.connect(messages.append)

        panel._on_add_field()
        qapp.processEvents()
        panel._table.item(0, 0).setText("title")
        qapp.processEvents()

        assert messages[-1] == "Page field 'title' conflicts with an auto-generated page member."
        assert panel._table.item(0, 0).text() == "field"

    def test_panel_open_lifecycle_section_emits_request(self, qapp):
        from ui_designer.ui.page_fields_panel import PageFieldsPanel

        page, _title = build_test_page_with_title()
        panel = PageFieldsPanel()
        captured = []
        panel.user_code_section_requested.connect(captured.append)
        panel.set_page(page)

        panel._request_section("init")

        assert captured == ["init"]

    def test_panel_rejects_duplicate_field_name(self, qapp):
        from ui_designer.ui.page_fields_panel import PageFieldsPanel

        page, _title = build_test_page_with_title()
        page.user_fields = [
            {"name": "counter", "type": "int", "default": "0"},
            {"name": "buffer", "type": "uint8_t[16]"},
        ]
        panel = PageFieldsPanel()
        panel.set_page(page)
        messages = []
        panel.validation_message.connect(messages.append)

        panel._table.item(1, 0).setText("counter")
        qapp.processEvents()

        assert messages[-1] == "Page field 'counter' already exists in this page."
        assert panel._table.item(1, 0).text() == "buffer"
