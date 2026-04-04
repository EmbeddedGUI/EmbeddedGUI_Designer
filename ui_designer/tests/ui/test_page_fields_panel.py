"""Qt UI tests for PageFieldsPanel."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QApplication

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


def _make_page():
    from ui_designer.model.page import Page
    from ui_designer.model.widget_model import WidgetModel

    page = Page.create_default("main_page", screen_width=240, screen_height=320)
    title = WidgetModel("label", name="title", x=12, y=16, width=100, height=24)
    page.root_widget.add_child(title)
    return page


@_skip_no_qt
class TestPageFieldsPanel:
    def test_panel_displays_current_page_fields(self, qapp):
        from ui_designer.ui.page_fields_panel import PageFieldsPanel

        page = _make_page()
        page.user_fields = [
            {"name": "counter", "type": "int", "default": "0"},
            {"name": "buffer", "type": "uint8_t[16]"},
        ]

        panel = PageFieldsPanel()
        panel.set_page(page)

        assert panel._summary_label.text() == "Page Fields: 2 fields on main_page"
        assert panel.accessibleName() == "Page Fields: 2 fields on main_page. Selected field: none."
        assert panel.toolTip() == panel.accessibleName()
        assert panel._summary_label.toolTip() == panel._summary_label.text()
        assert panel._summary_label.statusTip() == panel._summary_label.toolTip()
        assert panel._summary_label.accessibleName() == panel._summary_label.text()
        assert panel._eyebrow_label.text() == "Generated Members"
        assert panel._eyebrow_label.accessibleName() == "Page fields engineering surface."
        assert panel._count_chip.text() == "2 fields"
        assert panel._count_chip.accessibleName() == "Field count: 2 fields."
        assert panel._selection_chip.text() == "No selection"
        assert panel._selection_chip.accessibleName() == "Field selection: No field selected."
        assert panel._metrics_frame.accessibleName() == "Page fields metrics: 2 fields. No field selected."
        assert panel._hint_label.toolTip() == panel._hint_label.text()
        assert panel._hint_label.statusTip() == panel._hint_label.toolTip()
        assert panel._hint_label.accessibleName() == panel._hint_label.text()
        assert panel._code_hint_label.toolTip() == panel._code_hint_label.text()
        assert panel._code_hint_label.statusTip() == panel._code_hint_label.toolTip()
        assert panel._code_hint_label.accessibleName() == panel._code_hint_label.text()
        assert panel._table.toolTip() == panel.accessibleName()
        assert panel._table.statusTip() == panel._table.toolTip()
        assert panel._table.accessibleName() == "Page fields table: Page Fields: 2 fields on main_page. Selected field: none."
        assert panel._open_on_open_button.toolTip() == "Open the on_open section in main_page user code."
        assert panel._open_on_open_button.statusTip() == panel._open_on_open_button.toolTip()
        assert panel._open_on_open_button.accessibleName() == "Open on_open user code for main_page"
        assert panel._open_on_close_button.accessibleName() == "Open on_close user code for main_page"
        assert panel._open_init_button.accessibleName() == "Open init user code for main_page"
        assert panel._add_button.toolTip() == "Add a page field."
        assert panel._add_button.accessibleName() == "Add page field to main_page"
        assert panel._add_button.statusTip() == panel._add_button.toolTip()
        assert panel._remove_button.toolTip() == "Select a field to remove it."
        assert panel._remove_button.accessibleName() == "Remove page field unavailable"
        assert panel._table.rowCount() == 2
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

    def test_panel_marks_actions_unavailable_without_active_page(self, qapp):
        from ui_designer.ui.page_fields_panel import PageFieldsPanel

        panel = PageFieldsPanel()

        assert panel.accessibleName() == "Page Fields: no active page"
        assert panel.toolTip() == panel.accessibleName()
        assert panel._table.toolTip() == "Page Fields: no active page"
        assert panel._table.accessibleName() == "Page fields table: Page Fields: no active page"
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

    def test_panel_add_and_remove_field_emits_changes(self, qapp):
        from ui_designer.ui.page_fields_panel import PageFieldsPanel

        page = _make_page()
        panel = PageFieldsPanel()
        panel.set_page(page)
        captured = []
        panel.fields_changed.connect(lambda fields: captured.append(fields))

        assert panel._remove_button.toolTip() == "Select a field to remove it."
        panel._on_add_field()
        qapp.processEvents()

        assert panel._table.rowCount() == 1
        assert panel.accessibleName() == "Page Fields: 1 field on main_page. Selected field: field."
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
        assert captured[-1] == []

    def test_panel_rejects_conflicting_field_name(self, qapp):
        from ui_designer.ui.page_fields_panel import PageFieldsPanel

        page = _make_page()
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

        page = _make_page()
        panel = PageFieldsPanel()
        captured = []
        panel.user_code_section_requested.connect(captured.append)
        panel.set_page(page)

        panel._request_section("init")

        assert captured == ["init"]

    def test_panel_rejects_duplicate_field_name(self, qapp):
        from ui_designer.ui.page_fields_panel import PageFieldsPanel

        page = _make_page()
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
