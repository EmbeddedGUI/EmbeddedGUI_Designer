"""Qt UI tests for the diagnostics panel."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QApplication

    _has_pyqt5 = True
except ImportError:
    _has_pyqt5 = False

from ui_designer.model.diagnostics import DiagnosticEntry

_skip_no_qt = pytest.mark.skipif(not _has_pyqt5, reason="PyQt5 not available")


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
    app.processEvents()


def _sample_entries():
    return [
        DiagnosticEntry(
            "error",
            "duplicate_name",
            "Widget name 'title' is duplicated in page 'main_page'.",
            page_name="main_page",
            widget_name="title",
            target_page_name="main_page",
            target_widget_name="title",
        ),
        DiagnosticEntry(
            "warning",
            "bounds",
            "Widget 'hero' has geometry issues: exceeds parent 'root' bounds.",
            page_name="main_page",
            widget_name="hero",
            target_page_name="main_page",
            target_widget_name="hero",
        ),
        DiagnosticEntry(
            "info",
            "selection_locked",
            "1 selected widget is locked; canvas drag and resize are disabled.",
        ),
    ]


@_skip_no_qt
class TestDiagnosticsPanel:
    def test_clear_state_exposes_summary_and_action_metadata(self, qapp):
        from ui_designer.ui.diagnostics_panel import DiagnosticsPanel

        panel = DiagnosticsPanel()

        assert panel.accessibleName() == "Diagnostics: no active issues. Severity filter: Any. 0 visible items."
        assert panel.toolTip() == panel.accessibleName()
        assert panel.statusTip() == panel.toolTip()
        assert panel._header_eyebrow.accessibleName() == "Workspace diagnostics surface."
        assert panel._header_eyebrow.isHidden() is True
        assert panel._header_frame.accessibleName() == (
            "Diagnostics header. Diagnostics: no active issues. Severity filter: Any. 0 visible items."
        )
        assert panel._summary_label.toolTip() == "Diagnostics: no active issues"
        assert panel._visible_count_chip.text() == "0 visible"
        assert panel._visible_count_chip.isHidden() is True
        assert panel._visible_count_chip.accessibleName() == "Visible diagnostics: 0 visible items."
        assert panel._filter_chip.text() == "Any Severity"
        assert panel._filter_chip.isHidden() is True
        assert panel._filter_chip.accessibleName() == "Severity scope: Any Severity."
        assert panel._hint_label.accessibleName() == (
            "Diagnostics hint: Double-click a diagnostic to switch page or focus the widget."
        )
        assert panel._hint_label.isHidden() is True
        assert panel._severity_filter_combo.accessibleName() == "Diagnostics severity filter: Any"
        assert panel._controls_primary_strip.accessibleName() == "Diagnostics primary actions. Current filter: Any."
        assert panel._controls_secondary_strip.accessibleName() == "Diagnostics export actions. 0 visible items."
        assert panel._reset_view_button.toolTip() == "Diagnostics already show every severity."
        assert panel._reset_view_button.accessibleName() == "Reset diagnostics view unavailable"
        assert panel._open_selected_button.toolTip() == "Select a diagnostic to open its target."
        assert panel._open_selected_button.accessibleName() == "Open selected diagnostic unavailable"
        assert panel._open_first_error_button.accessibleName() == "Open first error diagnostic unavailable"
        assert panel._open_first_warning_button.accessibleName() == "Open first warning diagnostic unavailable"
        assert panel._copy_button.toolTip() == "No diagnostics available to copy."
        assert panel._copy_button.accessibleName() == "Copy diagnostics summary unavailable"
        assert panel._copy_json_button.accessibleName() == "Copy diagnostics JSON unavailable"
        assert panel._export_button.accessibleName() == "Export diagnostics summary unavailable"
        assert panel._export_json_button.accessibleName() == "Export diagnostics JSON unavailable"
        assert panel._list.toolTip() == "Diagnostics list: 0 visible items. Severity filter: Any."
        panel.deleteLater()

    def test_entries_refresh_item_list_and_action_metadata(self, qapp):
        from ui_designer.ui.diagnostics_panel import DiagnosticsPanel

        panel = DiagnosticsPanel()
        panel.set_entries(_sample_entries())
        qapp.processEvents()

        assert panel.accessibleName() == "Diagnostics: 1 error(s), 1 warning(s), 1 info item(s). Severity filter: Any. 3 visible items."
        assert panel.toolTip() == panel.accessibleName()
        assert panel._header_frame.accessibleName() == (
            "Diagnostics header. Diagnostics: 1 error(s), 1 warning(s), 1 info item(s). Severity filter: Any. 3 visible items."
        )
        assert panel._visible_count_chip.text() == "3 visible"
        assert panel._visible_count_chip.isHidden() is True
        assert panel._filter_chip.text() == "Any Severity"
        assert panel._filter_chip.isHidden() is True
        assert panel._open_first_error_button.toolTip() == "Open the first navigable error diagnostic."
        assert panel._open_first_warning_button.toolTip() == "Open the first navigable warning diagnostic."
        assert panel._open_first_error_button.accessibleName() == "Open first error diagnostic: main_page/title"
        assert panel._open_first_warning_button.accessibleName() == "Open first warning diagnostic: main_page/hero"
        assert panel._copy_json_button.toolTip() == "Copy the visible diagnostics as JSON."
        assert panel._copy_button.accessibleName() == "Copy diagnostics summary: 3 visible items"
        assert panel._copy_json_button.accessibleName() == "Copy diagnostics JSON: 3 visible items"
        assert panel._export_button.toolTip() == "Export the visible diagnostics summary to a text file."
        assert panel._export_button.accessibleName() == "Export diagnostics summary: 3 visible items"
        assert panel._export_json_button.accessibleName() == "Export diagnostics JSON: 3 visible items"
        assert panel._list.accessibleName() == (
            "Diagnostics list: 3 visible items. Severity filter: Any. Double-click a diagnostic to open its target when available."
        )
        assert panel._list.item(0).toolTip() == (
            "Error diagnostic: main_page/title. Widget name 'title' is duplicated in page 'main_page'. Double-click to open."
        )
        assert panel._list.item(0).statusTip() == panel._list.item(0).toolTip()
        assert panel._list.item(0).data(Qt.AccessibleTextRole) == panel._list.item(0).toolTip()
        assert panel._list.item(2).toolTip() == (
            "Info diagnostic: selection. 1 selected widget is locked; canvas drag and resize are disabled. Navigation unavailable."
        )
        assert panel._list.item(2).statusTip() == panel._list.item(2).toolTip()
        assert panel._list.item(2).data(Qt.AccessibleTextRole) == panel._list.item(2).toolTip()

        panel._list.setCurrentRow(0)
        qapp.processEvents()
        assert panel._open_selected_button.isEnabled() is True
        assert panel._open_selected_button.toolTip() == "Open the selected diagnostic target."
        assert panel._open_selected_button.accessibleName() == "Open selected diagnostic: main_page/title"

        panel._list.setCurrentRow(2)
        qapp.processEvents()
        assert panel._open_selected_button.isEnabled() is False
        assert panel._open_selected_button.toolTip() == "The selected diagnostic has no page or widget target to open."
        assert panel._open_selected_button.accessibleName() == "Open selected diagnostic unavailable"
        panel.deleteLater()

    def test_filter_empty_state_updates_hints_and_copy_metadata(self, qapp):
        from ui_designer.ui.diagnostics_panel import DiagnosticsPanel

        panel = DiagnosticsPanel()
        panel.set_entries(_sample_entries()[:2])
        panel.set_severity_filter("info")
        qapp.processEvents()

        assert panel.toolTip() == panel.accessibleName()
        assert panel._hint_label.text() == "No diagnostics match the current severity filter."
        assert panel._hint_label.toolTip() == "No diagnostics match the current severity filter."
        assert panel._hint_label.isHidden() is True
        assert panel._visible_count_chip.text() == "0 visible"
        assert panel._visible_count_chip.isHidden() is True
        assert panel._filter_chip.text() == "Info Only"
        assert panel._filter_chip.isHidden() is True
        assert panel._severity_filter_combo.accessibleName() == "Diagnostics severity filter: Info"
        assert panel._reset_view_button.isEnabled() is True
        assert panel._reset_view_button.toolTip() == "Reset the diagnostics filter and show every severity."
        assert panel._reset_view_button.accessibleName() == "Reset diagnostics view: Info"
        assert panel._copy_button.toolTip() == "No diagnostics match the current filter to copy."
        assert panel._copy_json_button.toolTip() == "No diagnostics match the current filter to copy as JSON."
        assert panel._export_button.toolTip() == "No diagnostics match the current filter to export."
        assert panel._copy_button.accessibleName() == "Copy diagnostics summary unavailable"
        assert panel._copy_json_button.accessibleName() == "Copy diagnostics JSON unavailable"
        assert panel._export_button.accessibleName() == "Export diagnostics summary unavailable"
        assert panel._export_json_button.accessibleName() == "Export diagnostics JSON unavailable"
        assert panel._list.toolTip() == "Diagnostics list: 0 visible items. Severity filter: Info."
        panel.deleteLater()

    def test_header_frame_hint_skips_no_op_rewrites(self, qapp, monkeypatch):
        from ui_designer.ui.diagnostics_panel import DiagnosticsPanel

        panel = DiagnosticsPanel()
        panel._header_frame.setProperty("_diagnostics_hint_snapshot", None)

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

        panel.set_entries(_sample_entries())
        assert hint_calls == 2
        panel.deleteLater()

    def test_header_frame_accessible_name_skips_no_op_rewrites(self, qapp, monkeypatch):
        from ui_designer.ui.diagnostics_panel import DiagnosticsPanel

        panel = DiagnosticsPanel()
        panel._header_frame.setProperty("_diagnostics_accessible_snapshot", None)

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

        panel.set_entries(_sample_entries())
        assert accessible_calls == 2
        panel.deleteLater()
