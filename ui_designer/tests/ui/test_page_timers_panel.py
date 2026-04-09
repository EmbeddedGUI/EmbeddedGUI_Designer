"""Qt UI tests for PageTimersPanel."""

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
class TestPageTimersPanel:
    def test_panel_displays_current_page_timers(self, qapp):
        from ui_designer.ui.page_timers_panel import PageTimersPanel

        page = _make_page()
        page.timers = [
            {"name": "refresh_timer", "callback": "tick_refresh", "delay_ms": "500", "period_ms": "1000", "auto_start": True},
        ]

        panel = PageTimersPanel()
        panel.set_page(page)

        header_margins = panel._header_frame.layout().contentsMargins()
        chip_margins = panel._header_chip_row.contentsMargins()
        action_buttons = panel._actions_frame.layout().itemAt(1).layout()
        table_layout = panel._table_frame.layout()

        assert panel.layout().spacing() == 2
        assert (header_margins.left(), header_margins.top(), header_margins.right(), header_margins.bottom()) == (2, 2, 2, 2)
        assert panel._header_frame.layout().spacing() == 2
        assert (chip_margins.left(), chip_margins.top(), chip_margins.right(), chip_margins.bottom()) == (0, 0, 0, 0)
        assert panel._header_chip_row.spacing() == 2
        assert table_layout.spacing() == 2
        assert panel._actions_frame.layout().spacing() == 2
        assert action_buttons.spacing() == 2
        assert panel._summary_label.text() == "Page Timers: 1 timer on main_page"
        assert panel.accessibleName() == "Page Timers: 1 timer on main_page. Selected timer: none."
        assert panel.toolTip() == panel.accessibleName()
        assert panel._summary_label.toolTip() == panel._summary_label.text()
        assert panel._summary_label.statusTip() == panel._summary_label.toolTip()
        assert panel._summary_label.accessibleName() == panel._summary_label.text()
        assert panel._eyebrow_label.text() == "Timers"
        assert panel._eyebrow_label.accessibleName() == "Page timers engineering surface."
        assert panel._eyebrow_label.isHidden() is True
        assert panel._header_frame.accessibleName() == (
            "Page timers header. Page Timers: 1 timer on main_page. Selected timer: none."
        )
        assert panel._header_meta_label.accessibleName() == panel._header_meta_label.text()
        assert panel._header_meta_label.isHidden() is True
        assert panel._count_chip.text() == "1 timer"
        assert panel._count_chip.accessibleName() == "Timer count: 1 timer."
        assert panel._selection_chip.text() == "No selection"
        assert panel._selection_chip.accessibleName() == "Timer selection: No timer selected."
        assert panel._metrics_frame.isHidden() is True
        assert panel._metrics_frame.accessibleName() == "Page timers metrics: 1 timer. No timer selected."
        assert panel._hint_label.toolTip() == panel._hint_label.text()
        assert panel._hint_label.statusTip() == panel._hint_label.toolTip()
        assert panel._hint_label.accessibleName() == panel._hint_label.text()
        assert panel._hint_label.isHidden() is True
        assert panel._table_label.isHidden() is True
        assert panel._actions_label.isHidden() is True
        assert panel._table.toolTip() == panel.accessibleName()
        assert panel._table.statusTip() == panel._table.toolTip()
        assert panel._table.accessibleName() == "Page timers table: Page Timers: 1 timer on main_page. Selected timer: none."
        assert panel._add_button.toolTip() == "Add a page timer."
        assert panel._add_button.accessibleName() == "Add page timer to main_page"
        assert panel._add_button.statusTip() == panel._add_button.toolTip()
        assert panel._add_button.minimumHeight() == 22
        assert panel._add_button.maximumHeight() == 22
        assert panel._remove_button.toolTip() == "Select a timer to remove it."
        assert panel._remove_button.accessibleName() == "Remove page timer unavailable"
        assert panel._remove_button.minimumHeight() == 22
        assert panel._remove_button.maximumHeight() == 22
        assert panel._open_code_button.toolTip() == "Select a timer to open its user code."
        assert panel._open_code_button.accessibleName() == "Open timer user code unavailable"
        assert panel._open_code_button.minimumHeight() == 22
        assert panel._open_code_button.maximumHeight() == 22
        assert panel._table.rowCount() == 1
        assert panel._table.item(0, 0).text() == "refresh_timer"
        assert panel._table.item(0, 1).text() == "tick_refresh"
        assert panel._table.item(0, 4).text() == "true"
        assert panel._table.item(0, 0).toolTip() == "Page timer Name: refresh_timer."
        assert panel._table.item(0, 0).statusTip() == panel._table.item(0, 0).toolTip()
        assert panel._table.item(0, 0).data(Qt.AccessibleTextRole) == panel._table.item(0, 0).toolTip()
        assert panel._table.item(0, 4).toolTip() == "Page timer Auto Start: true."
        assert panel._table.item(0, 4).statusTip() == panel._table.item(0, 4).toolTip()
        assert panel._table.item(0, 4).data(Qt.AccessibleTextRole) == panel._table.item(0, 4).toolTip()

    def test_panel_marks_actions_unavailable_without_active_page(self, qapp):
        from ui_designer.ui.page_timers_panel import PageTimersPanel

        panel = PageTimersPanel()

        assert panel.accessibleName() == "Page Timers: no active page"
        assert panel.toolTip() == panel.accessibleName()
        assert panel._header_frame.accessibleName() == "Page timers header. Page Timers: no active page"
        assert panel._header_meta_label.accessibleName() == panel._header_meta_label.text()
        assert panel._header_meta_label.isHidden() is True
        assert panel._table.toolTip() == "Page Timers: no active page"
        assert panel._table.accessibleName() == "Page timers table: Page Timers: no active page"
        assert panel._table_label.isHidden() is True
        assert panel._actions_label.isHidden() is True
        assert panel._add_button.toolTip() == "Open a page to manage timers."
        assert panel._add_button.accessibleName() == "Add page timer unavailable"
        assert panel._remove_button.toolTip() == "Open a page to manage timers."
        assert panel._remove_button.accessibleName() == "Remove page timer unavailable"
        assert panel._open_code_button.toolTip() == "Open a page to access timer user code."
        assert panel._open_code_button.accessibleName() == "Open timer user code unavailable"
        assert panel._count_chip.text() == "0 timers"
        assert panel._selection_chip.text() == "No selection"
        assert panel._metrics_frame.accessibleName() == "Page timers metrics: 0 timers. No timer selected."

    def test_header_frame_hint_skips_no_op_rewrites(self, qapp, monkeypatch):
        from ui_designer.ui.page_timers_panel import PageTimersPanel

        page = _make_page()
        page.timers = [
            {"name": "refresh_timer", "callback": "tick_refresh", "delay_ms": "500", "period_ms": "1000", "auto_start": True},
        ]

        panel = PageTimersPanel()
        panel.set_page(page)
        panel._header_frame.setProperty("_page_timers_hint_snapshot", None)

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
        from ui_designer.ui.page_timers_panel import PageTimersPanel

        page = _make_page()
        page.timers = [
            {"name": "refresh_timer", "callback": "tick_refresh", "delay_ms": "500", "period_ms": "1000", "auto_start": True},
        ]

        panel = PageTimersPanel()
        panel.set_page(page)
        panel._header_frame.setProperty("_page_timers_accessible_snapshot", None)

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

    def test_panel_add_and_remove_timer_emit_changes(self, qapp):
        from ui_designer.ui.page_timers_panel import PageTimersPanel

        page = _make_page()
        panel = PageTimersPanel()
        panel.set_page(page)
        captured = []
        panel.timers_changed.connect(lambda timers: captured.append(timers))

        assert panel._remove_button.toolTip() == "Select a timer to remove it."
        assert panel._open_code_button.toolTip() == "Select a timer to open its user code."
        panel._on_add_timer()
        qapp.processEvents()

        assert panel._table.rowCount() == 1
        assert panel.accessibleName() == "Page Timers: 1 timer on main_page. Selected timer: timer."
        assert panel._header_frame.accessibleName() == (
            "Page timers header. Page Timers: 1 timer on main_page. Selected timer: timer."
        )
        assert panel._table.accessibleName() == "Page timers table: Page Timers: 1 timer on main_page. Selected timer: timer."
        assert panel._remove_button.toolTip() == "Remove the selected page timer: timer."
        assert panel._remove_button.accessibleName() == "Remove page timer: timer"
        assert panel._open_code_button.toolTip() == "Open user code for timer callback: egui_main_page_timer_callback."
        assert panel._open_code_button.accessibleName() == "Open timer user code: egui_main_page_timer_callback"
        assert panel._count_chip.text() == "1 timer"
        assert panel._selection_chip.text() == "timer"
        assert panel._selection_chip.accessibleName() == "Timer selection: Selected timer: timer."
        assert panel._metrics_frame.accessibleName() == "Page timers metrics: 1 timer. Selected timer: timer."
        assert captured[-1][0]["name"] == "timer"
        assert captured[-1][0]["callback"] == "egui_main_page_timer_callback"

        panel._table.selectRow(0)
        assert panel._remove_button.toolTip() == "Remove the selected page timer: timer."
        assert panel._open_code_button.toolTip() == "Open user code for timer callback: egui_main_page_timer_callback."
        panel._on_remove_timer()
        qapp.processEvents()

        assert panel._table.rowCount() == 0
        assert panel.accessibleName() == "Page Timers: 0 timers on main_page. Selected timer: none."
        assert panel._header_frame.accessibleName() == (
            "Page timers header. Page Timers: 0 timers on main_page. Selected timer: none."
        )
        assert captured[-1] == []

    def test_panel_open_user_code_emits_selected_timer_callback(self, qapp):
        from ui_designer.ui.page_timers_panel import PageTimersPanel

        page = _make_page()
        page.timers = [
            {"name": "refresh_timer", "callback": "tick_refresh", "delay_ms": "500", "period_ms": "1000", "auto_start": True},
        ]

        panel = PageTimersPanel()
        captured = []
        panel.user_code_requested.connect(lambda name, signature: captured.append((name, signature)))
        panel.set_page(page)

        panel._table.selectRow(0)
        panel._on_open_user_code()

        assert captured == [("tick_refresh", "void {func_name}(egui_timer_t *timer)")]

    def test_panel_rejects_conflicting_timer_name(self, qapp):
        from ui_designer.ui.page_timers_panel import PageTimersPanel

        page = _make_page()
        panel = PageTimersPanel()
        panel.set_page(page)
        messages = []
        panel.validation_message.connect(messages.append)

        panel._on_add_timer()
        qapp.processEvents()
        panel._table.item(0, 0).setText("title")
        qapp.processEvents()

        assert messages[-1] == "Page timer 'title' conflicts with an auto-generated page member."
        assert panel._table.item(0, 0).text() == "timer"
