"""Qt UI tests for the status center panel."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtCore import Qt
    from PyQt5.QtTest import QTest
    from PyQt5.QtWidgets import QApplication, QToolButton

    _has_pyqt5 = True
except ImportError:
    _has_pyqt5 = False

_skip_no_qt = pytest.mark.skipif(not _has_pyqt5, reason="PyQt5 not available")


def _menu_labels(menu):
    return [action.text() for action in menu.actions() if not action.isSeparator()]


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
    app.processEvents()


@_skip_no_qt
class TestStatusCenterPanel:
    def test_health_chip_and_bars_track_diagnostic_mix(self, qapp):
        from ui_designer.ui.status_center_panel import StatusCenterPanel

        panel = StatusCenterPanel()
        panel.set_status(diagnostics_errors=2, diagnostics_warnings=1, diagnostics_infos=1)

        assert panel._health_chip.isHidden() is False
        assert panel._health_chip.text() == "Critical (2)"
        assert panel._health_chip.property("chipTone") == "danger"
        assert panel._workspace_chip.isHidden() is False
        assert panel._workspace_chip.text() == "Action Needed (Diagnostics)"
        assert panel._workspace_chip.property("chipTone") == "danger"
        assert panel._health_title.text() == "Diagnostic Mix (4 total)"
        assert panel._health_title.toolTip() == "Diagnostic mix with 4 total diagnostics."
        assert panel._health_title.accessibleName() == "Diagnostic mix title: 4 total diagnostics."
        assert panel._runtime_title.text() == "Runtime"
        assert panel._runtime_title.toolTip() == "Runtime status: clear."
        assert panel._runtime_title.accessibleName() == "Runtime title: Clear. No runtime errors."
        assert panel._error_row.isHidden() is False
        assert panel._warning_row.isHidden() is False
        assert panel._info_row.isHidden() is False
        assert panel._runtime_chip.isHidden() is True
        assert panel._diag_value.toolTip() == "Diagnostics: 2 errors, 1 warning, 1 info item"
        assert panel._diag_value.accessibleName() == "Diagnostics value: 2 errors, 1 warning, 1 info item"
        assert panel._diag_card.accessibleName() == (
            "Diagnostics metric: 2 errors, 1 warning, 1 info item. "
            "Open Diagnostics. 2 errors, 1 warning, 1 info item."
        )
        assert panel._error_bar.value() == 50
        assert panel._warning_bar.value() == 25
        assert panel._info_bar.value() == 25
        assert panel._error_value.text() == "2 errors (50%)"
        assert panel._warning_value.text() == "1 warning (25%)"
        assert panel._info_value.text() == "1 info item (25%)"
        assert panel._error_value.toolTip() == "Errors: 2 errors (50%)"
        assert panel._warning_value.toolTip() == "Warnings: 1 warning (25%)"
        assert panel._info_value.toolTip() == "Info: 1 info item (25%)"
        assert panel._error_value.statusTip() == panel._error_value.toolTip()
        assert panel._warning_value.statusTip() == panel._warning_value.toolTip()
        assert panel._info_value.statusTip() == panel._info_value.toolTip()
        assert panel._error_bar.toolTip() == "Errors share: 2 errors (50%)"
        assert panel._warning_bar.toolTip() == "Warnings share: 1 warning (25%)"
        assert panel._info_bar.toolTip() == "Info share: 1 info item (25%)"
        assert panel._error_bar.accessibleName() == "Errors share: 2 errors (50%)"
        assert panel._warning_bar.accessibleName() == "Warnings share: 1 warning (25%)"
        assert panel._info_bar.accessibleName() == "Info share: 1 info item (25%)"
        assert panel._diagnostic_jump_host.isHidden() is False
        assert panel._first_error_btn.isHidden() is False
        assert panel._first_warning_btn.isHidden() is False
        assert panel._first_error_btn.isEnabled() is True
        assert panel._first_warning_btn.isEnabled() is True
        assert panel._first_error_btn.text() == "Open First Error (2)"
        assert panel._first_warning_btn.text() == "Open First Warning (1)"
        assert panel._health_chip_action == "open_error_diagnostics"
        assert panel._workspace_chip.property("iconKey") == "diagnostics"
        assert panel._workspace_chip.accessibleName() == (
            "Workspace status: Action Needed (Diagnostics). Suggested: Fix First Error (2). "
            "Start with the first error in Diagnostics. 2 errors active."
        )
        assert panel._health_chip.toolTip() == "Open Errors. 2 errors active."
        assert panel._health_chip.property("iconKey") == "diagnostics"
        assert panel._health_chip.accessibleName() == (
            "Diagnostic status: Critical (2). Open Errors. 2 errors active."
        )
        assert panel._workspace_chip.toolTip() == (
            "Action Needed (Diagnostics). Start with the first error in Diagnostics. 2 errors active."
        )
        assert panel._health_summary_label.isHidden() is False
        assert panel._health_summary_label.text() == "Summary: 2 errors, 1 warning, 1 info item need attention. Errors lead at 50%."
        assert panel._health_summary_label.toolTip() == panel._health_summary_label.text()
        assert panel._health_summary_label.accessibleName() == (
            "Diagnostic summary: Summary: 2 errors, 1 warning, 1 info item need attention. Errors lead at 50%."
        )
        assert panel._runtime_label.isHidden() is True
        assert panel._runtime_label.toolTip() == "No runtime errors."
        assert panel._runtime_label.accessibleName() == "Runtime details: No runtime errors."
        assert panel._error_row.toolTip() == "Open Errors. 2 errors active."
        assert panel._warning_row.toolTip() == "Open Warnings. 1 warning active."
        assert panel._info_row.toolTip() == "Open Info. 1 info item active."
        assert panel._error_row.accessibleName() == "Errors diagnostics: 2 errors (50%)"
        assert panel._warning_row.accessibleName() == "Warnings diagnostics: 1 warning (25%)"
        assert panel._info_row.accessibleName() == "Info diagnostics: 1 info item (25%)"
        assert panel._first_error_btn.toolTip() == "Jump to the first error in Diagnostics. 2 errors active."
        assert panel._first_warning_btn.toolTip() == "Jump to the first warning in Diagnostics. 1 warning active."
        assert panel._first_error_btn.accessibleName() == (
            "First Error action: Open First Error (2). Jump to the first error in Diagnostics. 2 errors active."
        )
        assert panel._first_warning_btn.accessibleName() == (
            "First Warning action: Open First Warning (1). "
            "Jump to the first warning in Diagnostics. 1 warning active."
        )
        panel.deleteLater()

    def test_health_chip_runtime_and_buttons_update_across_status_changes(self, qapp):
        from ui_designer.ui.status_center_panel import StatusCenterPanel

        panel = StatusCenterPanel()
        panel.set_status(diagnostics_errors=0, diagnostics_warnings=3, diagnostics_infos=1, runtime_error="Runtime failed")

        assert panel._health_chip.isHidden() is False
        assert panel._health_chip.text() == "Attention (3)"
        assert panel._health_chip.property("chipTone") == "warning"
        assert panel._workspace_chip.text() == "Check Workspace (Diagnostics)"
        assert panel._workspace_chip.property("chipTone") == "danger"
        assert panel._workspace_chip.property("iconKey") == "diagnostics"
        assert panel._workspace_chip.toolTip() == (
            "Check Workspace (Diagnostics). Review the first warning in Diagnostics. 3 warnings active."
        )
        assert panel._workspace_chip.accessibleName() == (
            "Workspace status: Check Workspace (Diagnostics). Suggested: Review First Warning (3). "
            "Review the first warning in Diagnostics. 3 warnings active."
        )
        assert panel._health_chip_action == "open_warning_diagnostics"
        assert panel._health_chip.toolTip() == "Open Warnings. 3 warnings active."
        assert panel._health_chip.property("iconKey") == "history"
        assert panel._health_title.text() == "Diagnostic Mix (4 total)"
        assert panel._health_summary_label.isHidden() is False
        assert panel._health_summary_label.text() == "Summary: 3 warnings, 1 info item need review. Warnings lead at 75%."
        assert panel._error_value.text() == "0 errors (0%)"
        assert panel._warning_value.text() == "3 warnings (75%)"
        assert panel._info_value.text() == "1 info item (25%)"
        assert panel._warning_bar.toolTip() == "Warnings share: 3 warnings (75%)"
        assert panel._runtime_label.isHidden() is False
        assert panel._runtime_label.text() == "Runtime failed"
        assert panel._runtime_label.toolTip() == "Runtime failed"
        assert panel._runtime_label.accessibleName() == "Runtime details: Runtime failed"
        assert panel._runtime_title.text() == "Runtime (Issue)"
        assert panel._runtime_title.toolTip() == "Runtime status: issue detected. Runtime failed"
        assert panel._runtime_title.accessibleName() == "Runtime title: Issue detected. Runtime failed"
        assert panel._runtime_chip.isHidden() is False
        assert panel._runtime_chip.text() == "Issue"
        assert panel._runtime_chip.property("chipTone") == "danger"
        assert panel._runtime_chip.toolTip() == "Open Debug Output. Runtime issue: Runtime failed"
        assert panel._runtime_chip.statusTip() == panel._runtime_chip.toolTip()
        assert panel._runtime_chip.accessibleName() == (
            "Runtime status: Issue. Open Debug Output. Runtime issue: Runtime failed"
        )
        assert panel._runtime_panel.toolTip() == "Open Debug Output. Runtime issue: Runtime failed"
        assert panel._runtime_panel.statusTip() == panel._runtime_panel.toolTip()
        assert panel._runtime_panel.accessibleName() == "Runtime section: Issue. Runtime failed"
        assert panel._diagnostic_jump_host.isHidden() is False
        assert panel._first_error_btn.isHidden() is True
        assert panel._first_warning_btn.isHidden() is False
        assert panel._first_error_btn.isEnabled() is False
        assert panel._first_warning_btn.isEnabled() is True
        assert panel._first_error_btn.text() == "Open First Error"
        assert panel._first_warning_btn.text() == "Open First Warning (3)"
        assert panel._diag_btn.text() == "Diagnostics (4 active)"
        assert panel._history_btn.text() == "History"
        assert panel._debug_btn.text() == "Debug Output (Issue)"
        assert panel._debug_btn.toolTip() == "Open Debug Output. Runtime issue: Runtime failed"
        assert panel._debug_btn.accessibleName() == (
            "Debug Output action: Debug Output (Issue). Open Debug Output. Runtime issue: Runtime failed"
        )
        assert panel._project_btn.text() == "Project (Setup)"
        assert panel._project_btn.accessibleName() == (
            "Project action: Project (Setup). Open Project. SDK root is missing or invalid."
        )
        assert panel._first_error_btn.toolTip() == "No errors are active."
        assert panel._first_warning_btn.toolTip() == "Jump to the first warning in Diagnostics. 3 warnings active."
        assert panel._diag_btn.accessibleName() == (
            "Diagnostics action: Diagnostics (4 active). Open Diagnostics. 0 errors, 3 warnings, 1 info item."
        )
        assert panel._history_btn.accessibleName() == (
            "History action: History. Open History. No dirty pages."
        )
        assert panel._first_error_btn.accessibleName() == (
            "First Error action unavailable: Open First Error. No errors are active."
        )
        assert panel._first_warning_btn.accessibleName() == (
            "First Warning action: Open First Warning (3). "
            "Jump to the first warning in Diagnostics. 3 warnings active."
        )

        panel.set_status(diagnostics_errors=0, diagnostics_warnings=0, diagnostics_infos=2, runtime_error="")

        assert panel._health_chip.isHidden() is False
        assert panel._health_chip.text() == "Info (2)"
        assert panel._health_chip.property("chipTone") == "accent"
        assert panel._workspace_chip.text() == "Check Workspace (Setup)"
        assert panel._workspace_chip.property("chipTone") == "warning"
        assert panel._workspace_chip.property("iconKey") == "project"
        assert panel._health_chip_action == "open_info_diagnostics"
        assert panel._health_chip.toolTip() == "Open Info. 2 info items active."
        assert panel._health_chip.property("iconKey") == "debug"
        assert panel._health_title.text() == "Diagnostic Mix (2 total)"
        assert panel._health_summary_label.isHidden() is False
        assert panel._health_summary_label.text() == "Summary: 2 info items available. Info lead at 100%."
        assert panel._error_value.text() == "0 errors (0%)"
        assert panel._warning_value.text() == "0 warnings (0%)"
        assert panel._info_value.text() == "2 info items (100%)"
        assert panel._info_bar.toolTip() == "Info share: 2 info items (100%)"
        assert panel._runtime_label.isHidden() is True
        assert panel._runtime_label.text() == "No runtime errors."
        assert panel._runtime_label.toolTip() == "No runtime errors."
        assert panel._runtime_label.accessibleName() == "Runtime details: No runtime errors."
        assert panel._runtime_chip.isHidden() is True
        assert panel._runtime_chip.text() == "Clear"
        assert panel._runtime_chip.property("chipTone") == "success"
        assert panel._runtime_chip.toolTip() == "Open Debug Output. No runtime errors."
        assert panel._runtime_chip.statusTip() == panel._runtime_chip.toolTip()
        assert panel._runtime_chip.accessibleName() == (
            "Runtime status: Clear. Open Debug Output. No runtime errors."
        )
        assert panel._runtime_panel.toolTip() == "Open Debug Output. No runtime errors."
        assert panel._runtime_panel.statusTip() == panel._runtime_panel.toolTip()
        assert panel._runtime_panel.accessibleName() == "Runtime section: Clear. No runtime errors."
        assert panel._diagnostic_jump_host.isHidden() is True
        assert panel._first_error_btn.isHidden() is True
        assert panel._first_warning_btn.isHidden() is True
        assert panel._first_error_btn.isEnabled() is False
        assert panel._first_warning_btn.isEnabled() is False
        assert panel._first_error_btn.text() == "Open First Error"
        assert panel._first_warning_btn.text() == "Open First Warning"
        assert panel._diag_btn.text() == "Diagnostics (2 active)"
        assert panel._history_btn.text() == "History"
        assert panel._debug_btn.text() == "Debug Output (Build)"
        assert panel._debug_btn.toolTip() == "Open Debug Output. Compile is unavailable."
        assert panel._debug_btn.accessibleName() == (
            "Debug Output action: Debug Output (Build). Open Debug Output. Compile is unavailable."
        )
        assert panel._project_btn.text() == "Project (Setup)"
        assert panel._project_btn.accessibleName() == (
            "Project action: Project (Setup). Open Project. SDK root is missing or invalid."
        )
        assert panel._first_error_btn.toolTip() == "No errors are active."
        assert panel._first_warning_btn.toolTip() == "No warnings are active."
        assert panel._diag_btn.accessibleName() == (
            "Diagnostics action: Diagnostics (2 active). Open Diagnostics. 0 errors, 0 warnings, 2 info items."
        )
        assert panel._first_error_btn.accessibleName() == (
            "First Error action unavailable: Open First Error. No errors are active."
        )
        assert panel._first_warning_btn.accessibleName() == (
            "First Warning action unavailable: Open First Warning. No warnings are active."
        )

        panel.set_status(diagnostics_errors=0, diagnostics_warnings=0, diagnostics_infos=0, runtime_error="")

        assert panel._health_chip.isHidden() is True
        assert panel._health_chip.text() == "Stable"
        assert panel._health_chip.property("chipTone") == "success"
        assert panel._workspace_chip.text() == "Check Workspace (Setup)"
        assert panel._workspace_chip.property("chipTone") == "warning"
        assert panel._workspace_chip.property("iconKey") == "project"
        assert panel._health_chip_action == "open_diagnostics"
        assert panel._health_chip.toolTip() == "Open Diagnostics. No active diagnostics."
        assert panel._health_chip.property("iconKey") == "diagnostics"
        assert panel._health_title.text() == "Diagnostic Mix"
        assert panel._health_summary_label.isHidden() is True
        assert panel._health_summary_label.text() == "Summary: Diagnostics are clear."
        assert panel._error_row.isHidden() is True
        assert panel._warning_row.isHidden() is True
        assert panel._info_row.isHidden() is True
        assert panel._error_value.text() == "No errors"
        assert panel._warning_value.text() == "No warnings"
        assert panel._info_value.text() == "No info items"
        assert panel._error_bar.toolTip() == "Errors share: No active diagnostics"
        assert panel._warning_bar.toolTip() == "Warnings share: No active diagnostics"
        assert panel._info_bar.toolTip() == "Info share: No active diagnostics"
        assert panel._error_bar.accessibleName() == "Errors share: No active diagnostics"
        assert panel._warning_bar.accessibleName() == "Warnings share: No active diagnostics"
        assert panel._info_bar.accessibleName() == "Info share: No active diagnostics"
        assert panel._runtime_label.isHidden() is True
        assert panel._runtime_label.text() == "No runtime errors."
        assert panel._runtime_label.toolTip() == "No runtime errors."
        assert panel._runtime_label.accessibleName() == "Runtime details: No runtime errors."
        assert panel._runtime_panel.accessibleName() == "Runtime section: Clear. No runtime errors."
        assert panel._runtime_chip.isHidden() is True
        assert panel._runtime_chip.text() == "Clear"
        assert panel._runtime_chip.property("chipTone") == "success"
        assert panel._error_row.toolTip() == "Open Errors. No errors active."
        assert panel._warning_row.toolTip() == "Open Warnings. No warnings active."
        assert panel._info_row.toolTip() == "Open Info. No info items active."
        assert panel._error_row.accessibleName() == "Errors diagnostics: No errors active"
        assert panel._warning_row.accessibleName() == "Warnings diagnostics: No warnings active"
        assert panel._info_row.accessibleName() == "Info diagnostics: No info items active"
        assert panel._diagnostic_jump_host.isHidden() is True
        assert panel._first_error_btn.isHidden() is True
        assert panel._first_warning_btn.isHidden() is True
        assert panel._first_error_btn.isEnabled() is False
        assert panel._first_warning_btn.isEnabled() is False
        assert panel._first_error_btn.text() == "Open First Error"
        assert panel._first_warning_btn.text() == "Open First Warning"
        assert panel._diag_btn.text() == "Diagnostics"
        assert panel._history_btn.text() == "History"
        assert panel._structure_btn.text() == "Structure"
        assert panel._diag_btn.toolTip() == "Open Diagnostics. No active diagnostics."
        assert panel._history_btn.toolTip() == "Open History. No dirty pages."
        assert panel._structure_btn.toolTip() == "Open Structure. No widgets selected."
        assert panel._diag_card.toolTip() == "Open Diagnostics. No active diagnostics."
        assert panel._dirty_card.toolTip() == "Open History. No dirty pages."
        assert panel._selection_card.toolTip() == "Open Structure. No widgets selected."
        assert panel._debug_btn.text() == "Debug Output (Build)"
        assert panel._debug_btn.toolTip() == "Open Debug Output. Compile is unavailable."
        assert panel._debug_btn.accessibleName() == (
            "Debug Output action: Debug Output (Build). Open Debug Output. Compile is unavailable."
        )
        assert panel._project_btn.text() == "Project (Setup)"
        assert panel._project_btn.accessibleName() == (
            "Project action: Project (Setup). Open Project. SDK root is missing or invalid."
        )
        assert panel._first_error_btn.toolTip() == "No errors are active."
        assert panel._first_warning_btn.toolTip() == "No warnings are active."
        assert panel._diag_btn.accessibleName() == (
            "Diagnostics action: Diagnostics. Open Diagnostics. No active diagnostics."
        )
        assert panel._history_btn.accessibleName() == (
            "History action: History. Open History. No dirty pages."
        )
        assert panel._structure_btn.accessibleName() == (
            "Structure action: Structure. Open Structure. No widgets selected."
        )
        assert panel._first_error_btn.accessibleName() == (
            "First Error action unavailable: Open First Error. No errors are active."
        )
        assert panel._first_warning_btn.accessibleName() == (
            "First Warning action unavailable: Open First Warning. No warnings are active."
        )
        panel.deleteLater()

    def test_metric_and_runtime_tooltips_reflect_workspace_state(self, qapp):
        from ui_designer.ui.status_center_panel import StatusCenterPanel

        panel = StatusCenterPanel()
        panel.set_status(
            sdk_ready=True,
            can_compile=True,
            dirty_pages=2,
            selection_count=1,
            preview_label="Preview Running",
            diagnostics_errors=2,
            diagnostics_warnings=1,
            diagnostics_infos=3,
            runtime_error="Bridge disconnected",
        )

        assert panel._workspace_summary_label.text() == (
            "Workspace: SDK ready, compile ready, Preview Running, runtime issue detected, 2 dirty pages, 1 widget selected, 6 diagnostics. Next: Fix First Error (2)."
        )
        assert panel._workspace_summary_label.accessibleName() == (
            "Workspace summary: Workspace: SDK ready, compile ready, Preview Running, runtime issue detected, 2 dirty pages, 1 widget selected, 6 diagnostics. Next: Fix First Error (2)."
        )
        assert panel._workspace_chip.isHidden() is False
        assert panel._workspace_chip.text() == "Action Needed (Diagnostics)"
        assert panel._workspace_chip.property("chipTone") == "danger"
        assert panel._workspace_chip.property("iconKey") == "diagnostics"
        assert panel._health_title.text() == "Diagnostic Mix (6 total)"
        assert panel._health_title.accessibleName() == "Diagnostic mix title: 6 total diagnostics."
        assert panel._runtime_title.text() == "Runtime (Issue)"
        assert panel._runtime_title.accessibleName() == "Runtime title: Issue detected. Bridge disconnected"
        assert panel._runtime_label.isHidden() is False
        assert panel._runtime_label.toolTip() == "Bridge disconnected"
        assert panel._runtime_label.accessibleName() == "Runtime details: Bridge disconnected"
        assert panel._runtime_panel.accessibleName() == "Runtime section: Issue. Bridge disconnected"
        assert panel._runtime_chip.isHidden() is False
        assert panel._sdk_value.toolTip() == "SDK: Ready"
        assert panel._sdk_value.accessibleName() == "SDK value: Ready"
        assert panel._sdk_card.accessibleName() == "SDK metric: Ready. Open Project. SDK workspace is ready."
        assert panel._compile_value.toolTip() == "Compile: Ready"
        assert panel._compile_card.accessibleName() == "Compile metric: Ready. Open Debug Output. Compile is ready."
        assert panel._preview_value.toolTip() == "Preview: Preview Running"
        assert panel._preview_card.accessibleName() == "Preview metric: Preview Running. Open Debug Output. Preview Running."
        assert panel._selection_value.toolTip() == "Selection: 1 widget"
        assert panel._selection_card.accessibleName() == (
            "Selection metric: 1 widget. Open Structure. 1 widget selected."
        )
        assert panel._dirty_value.toolTip() == "Dirty Pages: 2 dirty pages"
        assert panel._dirty_card.accessibleName() == (
            "Dirty Pages metric: 2 dirty pages. Open History. 2 dirty pages."
        )
        assert panel._sdk_card.toolTip() == "Open Project. SDK workspace is ready."
        assert panel._compile_card.toolTip() == "Open Debug Output. Compile is ready."
        assert panel._diag_card.toolTip() == "Open Diagnostics. 2 errors, 1 warning, 3 info items."
        assert panel._preview_card.toolTip() == "Open Debug Output. Preview Running."
        assert panel._selection_card.toolTip() == "Open Structure. 1 widget selected."
        assert panel._dirty_card.toolTip() == "Open History. 2 dirty pages."
        assert panel._error_value.text() == "2 errors (33%)"
        assert panel._warning_value.text() == "1 warning (17%)"
        assert panel._info_value.text() == "3 info items (50%)"
        assert panel._error_value.accessibleName() == "Errors value: 2 errors (33%)"
        assert panel._warning_value.accessibleName() == "Warnings value: 1 warning (17%)"
        assert panel._info_value.accessibleName() == "Info value: 3 info items (50%)"
        assert panel._diag_btn.text() == "Diagnostics (6 active)"
        assert panel._diag_btn.toolTip() == "Open Diagnostics. 2 errors, 1 warning, 3 info items."
        assert panel._diag_btn.accessibleName() == (
            "Diagnostics action: Diagnostics (6 active). Open Diagnostics. 2 errors, 1 warning, 3 info items."
        )
        assert panel._history_btn.text() == "History (2 dirty)"
        assert panel._history_btn.toolTip() == "Open History. 2 dirty pages."
        assert panel._history_btn.accessibleName() == (
            "History action: History (2 dirty). Open History. 2 dirty pages."
        )
        assert panel._debug_btn.text() == "Debug Output (Issue)"
        assert panel._debug_btn.toolTip() == "Open Debug Output. Runtime issue: Bridge disconnected"
        assert panel._debug_btn.accessibleName() == (
            "Debug Output action: Debug Output (Issue). Open Debug Output. Runtime issue: Bridge disconnected"
        )
        assert panel._project_btn.text() == "Project"
        assert panel._project_btn.accessibleName() == (
            "Project action: Project. Open Project. SDK workspace is ready."
        )
        assert panel._project_btn.toolTip() == "Open Project. SDK workspace is ready."
        assert panel._structure_btn.text() == "Structure (1 selected)"
        assert panel._structure_btn.toolTip() == "Open Structure. 1 widget selected."
        assert panel._structure_btn.accessibleName() == (
            "Structure action: Structure (1 selected). Open Structure. 1 widget selected."
        )
        assert panel._suggested_action_button.text() == "Fix First Error (2)"
        assert panel._suggested_action_button.property("iconKey") == "diagnostics"
        assert panel._suggested_action_button.toolTip() == "Start with the first error in Diagnostics. 2 errors active."
        assert panel._suggested_action_label.accessibleName() == (
            "Suggested next step (Diagnostics): Fix First Error (2). "
            "Start with the first error in Diagnostics. 2 errors active."
        )
        assert panel._suggested_action_button.accessibleName() == (
            "Suggested status action: Fix First Error (2). Context: Diagnostics. "
            "Start with the first error in Diagnostics. 2 errors active."
        )
        assert panel._suggested_action_summary_label.text() == (
            "Diagnostics guidance: Start with the first error in Diagnostics. 2 errors active."
        )
        assert panel._repeat_action_button.accessibleName() == (
            "Repeat action unavailable: No recent action yet."
        )
        assert panel._runtime_chip.text() == "Issue"
        assert panel._runtime_chip.toolTip() == "Open Debug Output. Runtime issue: Bridge disconnected"
        assert panel._runtime_panel.toolTip() == "Open Debug Output. Runtime issue: Bridge disconnected"
        assert panel._runtime_chip.statusTip() == panel._runtime_chip.toolTip()
        assert panel._runtime_panel.statusTip() == panel._runtime_panel.toolTip()
        assert panel._sdk_card.statusTip() == panel._sdk_card.toolTip()
        assert panel._dirty_card.statusTip() == panel._dirty_card.toolTip()
        assert panel._diag_btn.statusTip() == panel._diag_btn.toolTip()
        assert panel._history_btn.statusTip() == panel._history_btn.toolTip()
        assert panel._repeat_action_button.statusTip() == panel._repeat_action_button.toolTip()
        assert panel._workspace_summary_label.toolTip() == panel._workspace_summary_label.text()
        panel.deleteLater()

    def test_static_quick_action_buttons_expose_default_hints(self, qapp):
        from ui_designer.ui.status_center_panel import StatusCenterPanel

        panel = StatusCenterPanel()

        assert panel._workspace_summary_label.accessibleName() == (
            "Workspace summary: Workspace: SDK missing, compile unavailable, Preview idle, runtime clear, no dirty pages, no widgets selected, diagnostics clear. Next: Configure SDK."
        )
        assert panel._header_title.text() == "Status Center (Workspace)"
        assert panel._header_title.toolTip() == "Status Center focused on Workspace. Check Workspace (Setup)."
        assert panel._header_title.accessibleName() == (
            "Status Center title: Workspace. Current status: Check Workspace (Setup)."
        )
        assert panel._header_subtitle.text() == "Workspace checks are pending. Focus on Configure SDK."
        assert panel._header_subtitle.toolTip() == (
            "Status Center: Check Workspace (Setup). Open Project to configure the SDK workspace. SDK root is missing or invalid."
        )
        assert panel._header_subtitle.accessibleName() == (
            "Status Center summary: Workspace checks are pending. Focus on Configure SDK. "
            "Open Project to configure the SDK workspace. SDK root is missing or invalid."
        )
        assert panel._health_title.text() == "Diagnostic Mix"
        assert panel._health_title.accessibleName() == "Diagnostic mix title: No active diagnostics."
        assert panel._runtime_title.text() == "Runtime"
        assert panel._runtime_title.accessibleName() == "Runtime title: Clear. No runtime errors."
        assert panel._error_row.isHidden() is True
        assert panel._warning_row.isHidden() is True
        assert panel._info_row.isHidden() is True
        assert panel._runtime_label.isHidden() is True
        assert panel._runtime_chip.isHidden() is True
        assert panel._actions_title.text() == "Quick Actions"
        assert panel._actions_title.toolTip() == "Quick actions with no recent actions yet."
        assert panel._actions_title.accessibleName() == "Quick actions section: No recent actions yet."
        assert panel._diagnostic_jump_host.isHidden() is True
        assert panel._last_action_host.isHidden() is True
        assert panel._last_action_label.isHidden() is True
        assert panel._repeat_action_button.popupMode() == QToolButton.DelayedPopup
        assert panel._last_action_label.text() == "Last action: None"
        assert panel._last_action_label.toolTip() == "No recent action yet."
        assert panel._last_action_label.accessibleName() == "Last action: None. No recent actions yet."
        assert panel._recent_actions_label.text() == "Recent actions: none yet."
        assert panel._recent_actions_label.toolTip() == "No recent actions yet."
        assert panel._recent_actions_label.accessibleName() == "Recent actions: none yet."
        assert panel._recent_actions_label.isHidden() is True
        assert panel._suggested_action_label.text() == "Suggested next step (Workspace):"
        assert panel._suggested_action_label.toolTip() == (
            "Suggested next step in Workspace. Open Project to configure the SDK workspace. SDK root is missing or invalid."
        )
        assert panel._suggested_action_label.accessibleName() == (
            "Suggested next step (Workspace): Configure SDK. "
            "Open Project to configure the SDK workspace. SDK root is missing or invalid."
        )
        assert panel._suggested_action_button.text() == "Configure SDK"
        assert panel._suggested_action_button.property("iconKey") == "project"
        assert panel._suggested_action_button.toolTip() == (
            "Open Project to configure the SDK workspace. SDK root is missing or invalid."
        )
        assert panel._suggested_action_button.accessibleName() == (
            "Suggested status action: Configure SDK. Context: Workspace. "
            "Open Project to configure the SDK workspace. SDK root is missing or invalid."
        )
        assert panel._suggested_action_summary_label.text() == (
            "Workspace guidance: Open Project to configure the SDK workspace. SDK root is missing or invalid."
        )
        assert panel._suggested_action_summary_label.accessibleName() == (
            "Suggested action guidance: Workspace guidance: Open Project to configure the SDK workspace. SDK root is missing or invalid."
        )
        assert panel._workspace_chip.text() == "Check Workspace (Setup)"
        assert panel._workspace_chip.property("chipTone") == "warning"
        assert panel._workspace_chip.toolTip() == (
            "Check Workspace (Setup). Open Project to configure the SDK workspace. SDK root is missing or invalid."
        )
        assert panel._workspace_chip.property("iconKey") == "project"
        assert panel._workspace_chip.accessibleName() == (
            "Workspace status: Check Workspace (Setup). Suggested: Configure SDK. "
            "Open Project to configure the SDK workspace. SDK root is missing or invalid."
        )
        assert panel._repeat_action_button.accessibleName() == (
            "Repeat action unavailable: No recent action yet."
        )
        assert panel._repeat_action_button.property("iconKey") == "history"
        assert panel._repeat_action_button.statusTip() == panel._repeat_action_button.toolTip()
        assert panel._workspace_summary_label.text() == (
            "Workspace: SDK missing, compile unavailable, Preview idle, runtime clear, no dirty pages, no widgets selected, diagnostics clear. Next: Configure SDK."
        )
        assert panel._workspace_summary_label.isHidden() is False
        assert panel._sdk_value.toolTip() == "SDK: Missing"
        assert panel._compile_value.toolTip() == "Compile: Unavailable"
        assert panel._preview_value.toolTip() == "Preview: Preview idle"
        assert panel._diag_value.text() == "No active diagnostics"
        assert panel._diag_value.toolTip() == "Diagnostics: No active diagnostics"
        assert panel._diag_value.accessibleName() == "Diagnostics value: No active diagnostics"
        assert panel._diag_card.accessibleName() == (
            "Diagnostics metric: No active diagnostics. Open Diagnostics. No active diagnostics."
        )
        assert panel._selection_value.text() == "No widgets selected"
        assert panel._selection_value.toolTip() == "Selection: No widgets selected"
        assert panel._selection_value.accessibleName() == "Selection value: No widgets selected"
        assert panel._selection_card.accessibleName() == (
            "Selection metric: No widgets selected. Open Structure. No widgets selected."
        )
        assert panel._dirty_value.text() == "No dirty pages"
        assert panel._dirty_value.toolTip() == "Dirty Pages: No dirty pages"
        assert panel._dirty_value.accessibleName() == "Dirty Pages value: No dirty pages"
        assert panel._dirty_card.accessibleName() == (
            "Dirty Pages metric: No dirty pages. Open History. No dirty pages."
        )
        assert panel._health_summary_label.isHidden() is True
        assert panel._health_summary_label.accessibleName() == "Diagnostic summary: Summary: Diagnostics are clear."
        assert panel._health_chip.isHidden() is True
        assert panel._health_chip.accessibleName() == (
            "Diagnostic status: Stable. Open Diagnostics. No active diagnostics."
        )
        assert panel._health_chip.property("iconKey") == "diagnostics"
        assert panel._runtime_label.toolTip() == "No runtime errors."
        assert panel._runtime_label.accessibleName() == "Runtime details: No runtime errors."
        assert panel._runtime_chip.isHidden() is True
        assert panel._runtime_chip.text() == "Clear"
        assert panel._runtime_chip.toolTip() == "Open Debug Output. No runtime errors."
        assert panel._runtime_chip.accessibleName() == (
            "Runtime status: Clear. Open Debug Output. No runtime errors."
        )
        assert panel._debug_btn.text() == "Debug Output (Build)"
        assert panel._debug_btn.toolTip() == "Open Debug Output. Compile is unavailable."
        assert panel._debug_btn.accessibleName() == (
            "Debug Output action: Debug Output (Build). Open Debug Output. Compile is unavailable."
        )
        assert panel._project_btn.text() == "Project (Setup)"
        assert panel._project_btn.accessibleName() == (
            "Project action: Project (Setup). Open Project. SDK root is missing or invalid."
        )
        assert panel._diag_btn.text() == "Diagnostics"
        assert panel._history_btn.text() == "History"
        assert panel._structure_btn.text() == "Structure"
        assert panel._runtime_label.isHidden() is True
        assert panel._diag_btn.toolTip() == "Open Diagnostics. No active diagnostics."
        assert panel._history_btn.toolTip() == "Open History. No dirty pages."
        assert panel._structure_btn.toolTip() == "Open Structure. No widgets selected."
        assert panel._diag_card.toolTip() == "Open Diagnostics. No active diagnostics."
        assert panel._dirty_card.toolTip() == "Open History. No dirty pages."
        assert panel._selection_card.toolTip() == "Open Structure. No widgets selected."
        assert panel._runtime_panel.accessibleName() == "Runtime section: Clear. No runtime errors."
        assert panel._components_btn.toolTip() == "Open Widgets."
        assert panel._components_btn.statusTip() == "Open Widgets."
        assert panel._components_btn.accessibleName() == "Widgets action: Widgets. Open Widgets."
        assert panel._diag_btn.accessibleName() == (
            "Diagnostics action: Diagnostics. Open Diagnostics. No active diagnostics."
        )
        assert panel._history_btn.accessibleName() == (
            "History action: History. Open History. No dirty pages."
        )
        assert panel._structure_btn.accessibleName() == (
            "Structure action: Structure. Open Structure. No widgets selected."
        )
        assert panel._first_error_btn.accessibleName() == (
            "First Error action unavailable: Open First Error. No errors are active."
        )
        assert panel._first_warning_btn.accessibleName() == (
            "First Warning action unavailable: Open First Warning. No warnings are active."
        )
        assert panel._assets_btn.toolTip() == "Open Assets."
        assert panel._properties_btn.toolTip() == "Open Properties."
        assert panel._animations_btn.toolTip() == "Open Animations."
        assert panel._fields_btn.toolTip() == "Open Fields."
        assert panel._timers_btn.toolTip() == "Open Timers."
        panel.deleteLater()

    def test_suggested_action_updates_with_workspace_state(self, qapp):
        from ui_designer.ui.status_center_panel import StatusCenterPanel

        panel = StatusCenterPanel()

        assert panel._suggested_action_label.text() == "Suggested next step (Workspace):"
        assert panel._suggested_action_label.isHidden() is True
        assert panel._suggested_action_button.text() == "Configure SDK"
        assert panel._suggested_action_button.accessibleName() == (
            "Suggested status action: Configure SDK. Context: Workspace. "
            "Open Project to configure the SDK workspace. SDK root is missing or invalid."
        )
        assert panel._suggested_action_summary_label.text() == (
            "Workspace guidance: Open Project to configure the SDK workspace. SDK root is missing or invalid."
        )

        panel.set_status(sdk_ready=True, can_compile=True, diagnostics_errors=1)
        assert panel._header_title.text() == "Status Center (Diagnostics)"
        assert panel._header_subtitle.text() == "Action needed now. Focus on Fix First Error (1)."
        assert panel._suggested_action_label.text() == "Suggested next step (Diagnostics):"
        assert panel._suggested_action_label.isHidden() is True
        assert panel._suggested_action_button.text() == "Fix First Error (1)"
        assert panel._suggested_action_button.accessibleName() == (
            "Suggested status action: Fix First Error (1). Context: Diagnostics. "
            "Start with the first error in Diagnostics. 1 error active."
        )
        assert panel._debug_btn.text() == "Debug Output"
        assert panel._project_btn.text() == "Project"
        assert panel._diag_btn.text() == "Diagnostics (1 active)"
        assert panel._suggested_action_button.property("iconKey") == "diagnostics"
        assert panel._workspace_chip.property("iconKey") == "diagnostics"
        assert panel._suggested_action_summary_label.text() == (
            "Diagnostics guidance: Start with the first error in Diagnostics. 1 error active."
        )

        panel.set_status(sdk_ready=True, can_compile=True, diagnostics_warnings=2)
        assert panel._header_title.text() == "Status Center (Diagnostics)"
        assert panel._header_subtitle.text() == "Workspace checks are pending. Focus on Review First Warning (2)."
        assert panel._suggested_action_label.text() == "Suggested next step (Diagnostics):"
        assert panel._suggested_action_button.text() == "Review First Warning (2)"
        assert panel._suggested_action_button.property("iconKey") == "diagnostics"
        assert panel._workspace_chip.property("iconKey") == "diagnostics"
        assert panel._suggested_action_summary_label.text() == (
            "Diagnostics guidance: Review the first warning in Diagnostics. 2 warnings active."
        )

        panel.set_status(sdk_ready=True, can_compile=True, runtime_error="Bridge lost")
        assert panel._header_title.text() == "Status Center (Runtime)"
        assert panel._header_subtitle.text() == "Action needed now. Focus on Inspect Debug Output."
        assert panel._suggested_action_label.text() == "Suggested next step (Runtime):"
        assert panel._suggested_action_button.text() == "Inspect Debug Output"
        assert panel._suggested_action_button.accessibleName() == (
            "Suggested status action: Inspect Debug Output. Context: Runtime. "
            "Inspect the latest runtime output. Bridge lost"
        )
        assert panel._debug_btn.text() == "Debug Output (Issue)"
        assert panel._suggested_action_button.property("iconKey") == "debug"
        assert panel._workspace_chip.property("iconKey") == "debug"
        assert panel._suggested_action_summary_label.text() == (
            "Runtime guidance: Inspect the latest runtime output. Bridge lost"
        )

        panel.set_status(sdk_ready=True, can_compile=False)
        assert panel._header_title.text() == "Status Center (Build)"
        assert panel._header_subtitle.text() == "Workspace checks are pending. Focus on Inspect Compile Output."
        assert panel._suggested_action_label.text() == "Suggested next step (Build):"
        assert panel._suggested_action_button.text() == "Inspect Compile Output"
        assert panel._debug_btn.text() == "Debug Output (Build)"
        assert panel._suggested_action_button.property("iconKey") == "debug"
        assert panel._workspace_chip.property("iconKey") == "debug"
        assert panel._suggested_action_summary_label.text() == (
            "Build guidance: Open Debug Output to inspect compile output. Compile is unavailable."
        )

        panel.set_status(sdk_ready=True, can_compile=True, dirty_pages=2)
        assert panel._header_title.text() == "Status Center (History)"
        assert panel._header_subtitle.text() == "Work is in progress. Focus on Review History (2)."
        assert panel._suggested_action_label.text() == "Suggested next step (History):"
        assert panel._suggested_action_button.text() == "Review History (2)"
        assert panel._history_btn.text() == "History (2 dirty)"
        assert panel._suggested_action_button.property("iconKey") == "history"
        assert panel._workspace_chip.property("iconKey") == "history"
        assert panel._suggested_action_summary_label.text() == (
            "History guidance: Review unsaved changes in History. 2 dirty pages pending."
        )

        panel.set_status(sdk_ready=True, can_compile=True, selection_count=3)
        assert panel._header_title.text() == "Status Center (Selection)"
        assert panel._header_subtitle.text() == "Work is in progress. Focus on Inspect Selection (3)."
        assert panel._suggested_action_label.text() == "Suggested next step (Selection):"
        assert panel._suggested_action_button.text() == "Inspect Selection (3)"
        assert panel._structure_btn.text() == "Structure (3 selected)"
        assert panel._suggested_action_button.property("iconKey") == "structure"
        assert panel._workspace_chip.property("iconKey") == "structure"
        assert panel._suggested_action_summary_label.text() == (
            "Selection guidance: Open Structure for the current selection. 3 widgets selected."
        )

        panel.set_status(sdk_ready=True, can_compile=True, diagnostics_infos=2)
        assert panel._header_title.text() == "Status Center (Diagnostics)"
        assert panel._header_subtitle.text() == "Work is in progress. Focus on Inspect Info (2)."
        assert panel._suggested_action_label.text() == "Suggested next step (Diagnostics):"
        assert panel._suggested_action_button.text() == "Inspect Info (2)"
        assert panel._diag_btn.text() == "Diagnostics (2 active)"
        assert panel._suggested_action_button.property("iconKey") == "debug"
        assert panel._workspace_chip.property("iconKey") == "debug"
        assert panel._suggested_action_summary_label.text() == (
            "Diagnostics guidance: Inspect informational diagnostics. 2 info items active."
        )

        panel.set_status(sdk_ready=True, can_compile=True)
        assert panel._header_title.text() == "Status Center (Diagnostics)"
        assert panel._header_subtitle.text() == "Workspace looks ready. Open Diagnostics is available."
        assert panel._workspace_chip.isHidden() is True
        assert panel._workspace_summary_label.isHidden() is True
        assert panel._suggested_action_label.text() == "Suggested next step (Diagnostics):"
        assert panel._suggested_action_button.text() == "Open Diagnostics"
        assert panel._debug_btn.text() == "Debug Output"
        assert panel._suggested_action_button.property("iconKey") == "diagnostics"
        assert panel._workspace_chip.property("iconKey") == "diagnostics"
        assert panel._suggested_action_summary_label.text() == (
            "Diagnostics guidance: Open Diagnostics for a full health review."
        )
        panel.deleteLater()

    def test_suggested_action_button_emits_contextual_action(self, qapp):
        from ui_designer.ui.status_center_panel import StatusCenterPanel

        panel = StatusCenterPanel()
        emitted = []
        panel.action_requested.connect(emitted.append)

        panel.set_status(sdk_ready=True, can_compile=True, diagnostics_errors=1)
        panel._suggested_action_button.click()
        panel.set_status(sdk_ready=True, can_compile=True, dirty_pages=2)
        panel._suggested_action_button.click()
        panel.set_status(sdk_ready=True, can_compile=True, selection_count=1)
        panel._suggested_action_button.click()

        assert emitted == [
            "open_first_error",
            "open_history",
            "open_structure_panel",
        ]
        assert panel._repeat_action_button.text() == "Repeat Structure"
        panel.deleteLater()

    def test_workspace_chip_emits_suggested_action(self, qapp):
        from ui_designer.ui.status_center_panel import StatusCenterPanel

        panel = StatusCenterPanel()
        emitted = []
        panel.action_requested.connect(emitted.append)

        panel._workspace_chip.click()
        panel.set_status(sdk_ready=True, can_compile=True, diagnostics_errors=1)
        panel._workspace_chip.click()
        panel.set_status(sdk_ready=True, can_compile=True, dirty_pages=1)
        panel._workspace_chip.click()

        assert emitted == [
            "open_project_panel",
            "open_first_error",
            "open_history",
        ]
        assert panel._repeat_action_button.text() == "Repeat History"
        panel.deleteLater()

    def test_health_chip_emits_contextual_diagnostic_actions(self, qapp):
        from ui_designer.ui.status_center_panel import StatusCenterPanel

        panel = StatusCenterPanel()
        panel.show()
        emitted = []
        panel.action_requested.connect(emitted.append)

        panel.set_status(diagnostics_errors=2, diagnostics_warnings=1, diagnostics_infos=1)
        panel._health_chip.click()
        panel.set_status(diagnostics_errors=0, diagnostics_warnings=2, diagnostics_infos=0)
        panel._health_chip.click()
        panel.set_status(diagnostics_errors=0, diagnostics_warnings=0, diagnostics_infos=3)
        panel._health_chip.click()
        panel.set_status(diagnostics_errors=0, diagnostics_warnings=0, diagnostics_infos=0)
        assert panel._health_chip.isHidden() is True
        panel._diag_btn.click()

        assert emitted == [
            "open_error_diagnostics",
            "open_warning_diagnostics",
            "open_info_diagnostics",
            "open_diagnostics",
        ]
        assert panel._repeat_action_button.text() == "Repeat Diagnostics"
        panel.deleteLater()

    def test_status_updates_skip_no_op_refreshes(self, qapp, monkeypatch):
        from ui_designer.ui.status_center_panel import StatusCenterPanel

        panel = StatusCenterPanel()
        metric_updates = 0
        original_set_metric_context = panel._set_metric_context

        def counted_set_metric_context(*args, **kwargs):
            nonlocal metric_updates
            metric_updates += 1
            return original_set_metric_context(*args, **kwargs)

        monkeypatch.setattr(panel, "_set_metric_context", counted_set_metric_context)

        panel.set_status(sdk_ready=True, can_compile=True, preview_label="Preview idle")
        assert metric_updates == 6

        panel.set_status(sdk_ready=True, can_compile=True, preview_label="Preview idle")
        assert metric_updates == 6

        panel.set_status(sdk_ready=True, can_compile=True, preview_label="Preview idle", dirty_pages=1)
        assert metric_updates == 12
        panel.deleteLater()

    def test_workspace_navigation_buttons_emit_expected_actions(self, qapp):
        from ui_designer.ui.status_center_panel import StatusCenterPanel

        panel = StatusCenterPanel()
        emitted = []
        panel.action_requested.connect(emitted.append)

        panel._project_btn.click()
        panel._structure_btn.click()
        panel._components_btn.click()
        panel._assets_btn.click()

        assert emitted == [
            "open_project_panel",
            "open_structure_panel",
            "open_components_panel",
            "open_assets_panel",
        ]
        assert panel._last_action_label.text() == "Last action: Assets"
        assert panel._last_action_label.toolTip() == "Current action: Assets. 4 recent actions tracked."
        assert panel._last_action_label.accessibleName() == "Last action: Assets. 4 recent actions tracked."
        assert panel._actions_title.text() == "Quick Actions (4 recent actions)"
        assert panel._actions_title.toolTip() == "Quick actions with 4 recent actions tracked."
        assert panel._actions_title.accessibleName() == "Quick actions section: 4 recent actions tracked."
        assert panel._repeat_action_button.text() == "Repeat Assets"
        assert panel._repeat_action_button.accessibleName() == (
            "Repeat action: Assets. 4 recent actions tracked. Older actions are available in the menu."
        )
        assert panel._repeat_action_button.property("iconKey") == "assets"
        assert panel._recent_actions_label.text() == "Recent actions (4): Assets, Widgets, Structure, +1 more."
        assert panel._recent_actions_label.toolTip() == "4 recent actions: Assets, Widgets, Structure, Project"
        assert panel._recent_actions_label.accessibleName() == (
            "Recent actions summary: 4 recent actions tracked. Assets, Widgets, Structure, Project."
        )
        assert panel._recent_actions_label.isHidden() is False
        assert panel._repeat_action_button.toolTip() == (
            "Repeat Assets. 4 recent actions tracked. Use the menu arrow to replay an older action."
        )
        assert _menu_labels(panel._repeat_action_menu) == [
            "Assets",
            "Widgets",
            "Structure",
            "Project",
            "Clear Recent Actions (4)",
        ]
        panel.deleteLater()

    def test_inspector_navigation_buttons_emit_expected_actions(self, qapp):
        from ui_designer.ui.status_center_panel import StatusCenterPanel

        panel = StatusCenterPanel()
        emitted = []
        panel.action_requested.connect(emitted.append)

        panel._properties_btn.click()
        panel._animations_btn.click()
        panel._fields_btn.click()
        panel._timers_btn.click()

        assert emitted == [
            "open_properties_inspector",
            "open_animations_inspector",
            "open_page_fields",
            "open_page_timers",
        ]
        assert panel._last_action_label.text() == "Last action: Timers"
        assert panel._repeat_action_button.text() == "Repeat Timers"
        assert _menu_labels(panel._repeat_action_menu) == [
            "Timers",
            "Fields",
            "Animations",
            "Properties",
            "Clear Recent Actions (4)",
        ]
        panel.deleteLater()

    def test_metric_cards_emit_expected_actions(self, qapp):
        from ui_designer.ui.status_center_panel import StatusCenterPanel

        panel = StatusCenterPanel()
        panel.show()
        emitted = []
        panel.action_requested.connect(emitted.append)

        QTest.mouseClick(panel._sdk_card, Qt.LeftButton)
        QTest.mouseClick(panel._compile_card, Qt.LeftButton)
        QTest.mouseClick(panel._diag_card, Qt.LeftButton)
        QTest.mouseClick(panel._preview_card, Qt.LeftButton)
        QTest.mouseClick(panel._selection_card, Qt.LeftButton)
        QTest.mouseClick(panel._dirty_card, Qt.LeftButton)

        assert emitted == [
            "open_project_panel",
            "open_debug",
            "open_diagnostics",
            "open_debug",
            "open_structure_panel",
            "open_history",
        ]
        assert panel._last_action_label.text() == "Last action: History"
        assert panel._repeat_action_button.text() == "Repeat History"
        assert _menu_labels(panel._repeat_action_menu) == [
            "History",
            "Structure",
            "Debug Output",
            "Diagnostics",
            "Project",
            "Clear Recent Actions (5)",
        ]
        panel.deleteLater()

    def test_metric_cards_support_keyboard_activation(self, qapp):
        from ui_designer.ui.status_center_panel import StatusCenterPanel

        panel = StatusCenterPanel()
        panel.show()
        emitted = []
        panel.action_requested.connect(emitted.append)

        panel._diag_card.setFocus()
        assert panel._diag_card.focusPolicy() == Qt.StrongFocus
        QTest.keyClick(panel._diag_card, Qt.Key_Return)
        QTest.keyClick(panel._diag_card, Qt.Key_Space)

        assert emitted == [
            "open_diagnostics",
            "open_diagnostics",
        ]
        assert panel._diag_card.accessibleName() == (
            "Diagnostics metric: No active diagnostics. Open Diagnostics. No active diagnostics."
        )
        assert panel._repeat_action_button.text() == "Repeat Diagnostics"
        panel.deleteLater()

    def test_health_rows_emit_filtered_diagnostics_actions(self, qapp):
        from ui_designer.ui.status_center_panel import StatusCenterPanel

        panel = StatusCenterPanel()
        panel.show()
        emitted = []
        panel.action_requested.connect(emitted.append)

        QTest.mouseClick(panel._error_row, Qt.LeftButton)
        QTest.mouseClick(panel._warning_row, Qt.LeftButton)
        QTest.mouseClick(panel._info_row, Qt.LeftButton)

        assert emitted == [
            "open_error_diagnostics",
            "open_warning_diagnostics",
            "open_info_diagnostics",
        ]
        assert panel._info_row.accessibleName() == "Info diagnostics: No info items active"
        assert panel._last_action_label.text() == "Last action: Info"
        assert panel._repeat_action_button.text() == "Repeat Info"
        assert _menu_labels(panel._repeat_action_menu) == ["Info", "Warnings", "Errors", "Clear Recent Actions (3)"]
        panel.deleteLater()

    def test_health_rows_support_keyboard_activation(self, qapp):
        from ui_designer.ui.status_center_panel import StatusCenterPanel

        panel = StatusCenterPanel()
        panel.show()
        emitted = []
        panel.action_requested.connect(emitted.append)

        panel._warning_row.setFocus()
        assert panel._warning_row.focusPolicy() == Qt.StrongFocus
        QTest.keyClick(panel._warning_row, Qt.Key_Return)
        QTest.keyClick(panel._warning_row, Qt.Key_Space)

        assert emitted == [
            "open_warning_diagnostics",
            "open_warning_diagnostics",
        ]
        assert panel._warning_row.accessibleName() == "Warnings diagnostics: No warnings active"
        assert panel._repeat_action_button.text() == "Repeat Warnings"
        panel.deleteLater()

    def test_restore_view_state_updates_last_action_label(self, qapp):
        from ui_designer.ui.status_center_panel import StatusCenterPanel

        panel = StatusCenterPanel()

        assert panel._last_action_label.text() == "Last action: None"
        assert panel._last_action_label.toolTip() == "No recent action yet."
        assert panel._last_action_label.accessibleName() == "Last action: None. No recent actions yet."
        assert panel._repeat_action_button.isEnabled() is False
        assert panel._repeat_action_button.text() == "Repeat Action"
        assert _menu_labels(panel._repeat_action_menu) == ["No recent actions yet"]
        panel.restore_view_state({"last_action": "open_page_fields", "recent_actions": ["open_page_fields", "open_debug"]})
        assert panel._last_action_host.isHidden() is False
        assert panel._last_action_label.text() == "Last action: Fields"
        assert panel._last_action_label.isHidden() is False
        assert panel._repeat_action_button.popupMode() == QToolButton.MenuButtonPopup
        assert panel._last_action_label.toolTip() == "Current action: Fields. 2 recent actions tracked."
        assert panel._last_action_label.accessibleName() == "Last action: Fields. 2 recent actions tracked."
        assert panel._actions_title.text() == "Quick Actions (2 recent actions)"
        assert panel._actions_title.accessibleName() == "Quick actions section: 2 recent actions tracked."
        assert panel._repeat_action_button.isEnabled() is True
        assert panel._repeat_action_button.text() == "Repeat Fields"
        assert panel._repeat_action_button.accessibleName() == (
            "Repeat action: Fields. 2 recent actions tracked. Older actions are available in the menu."
        )
        assert panel._repeat_action_button.property("iconKey") == "page"
        assert panel._recent_actions_label.text() == "Recent actions (2): Fields, Debug Output."
        assert panel._recent_actions_label.toolTip() == "2 recent actions: Fields, Debug Output"
        assert panel._recent_actions_label.accessibleName() == (
            "Recent actions summary: 2 recent actions tracked. Fields, Debug Output."
        )
        assert panel._recent_actions_label.isHidden() is False
        assert panel._repeat_action_button.toolTip() == (
            "Repeat Fields. 2 recent actions tracked. Use the menu arrow to replay an older action."
        )
        assert panel.view_state() == {
            "last_action": "open_page_fields",
            "recent_actions": ["open_page_fields", "open_debug"],
        }
        assert _menu_labels(panel._repeat_action_menu) == ["Fields", "Debug Output", "Clear Recent Actions (2)"]

        panel.restore_view_state(None)
        assert panel._last_action_host.isHidden() is True
        assert panel._last_action_label.isHidden() is True
        assert panel._last_action_label.text() == "Last action: None"
        assert panel._last_action_label.toolTip() == "No recent action yet."
        assert panel._last_action_label.accessibleName() == "Last action: None. No recent actions yet."
        assert panel._actions_title.text() == "Quick Actions"
        assert panel._repeat_action_button.isEnabled() is False
        assert panel._repeat_action_button.text() == "Repeat Action"
        assert panel._recent_actions_label.text() == "Recent actions: none yet."
        assert panel._recent_actions_label.toolTip() == "No recent actions yet."
        assert panel._recent_actions_label.accessibleName() == "Recent actions: none yet."
        assert panel._recent_actions_label.isHidden() is True
        assert panel._repeat_action_button.toolTip() == "No recent action to repeat yet."
        assert panel.view_state() == {"last_action": "", "recent_actions": []}
        assert _menu_labels(panel._repeat_action_menu) == ["No recent actions yet"]
        panel.deleteLater()

    def test_last_action_hint_skips_no_op_rewrites(self, qapp, monkeypatch):
        from ui_designer.ui.status_center_panel import StatusCenterPanel

        panel = StatusCenterPanel()
        panel._last_action_label.setProperty("_status_center_hint_snapshot", None)

        tooltip_calls = 0
        original_set_tooltip = panel._last_action_label.setToolTip

        def counted_set_tooltip(text):
            nonlocal tooltip_calls
            tooltip_calls += 1
            return original_set_tooltip(text)

        monkeypatch.setattr(panel._last_action_label, "setToolTip", counted_set_tooltip)

        panel._set_last_action("open_assets_panel", ["open_assets_panel", "open_components_panel"])
        assert tooltip_calls == 1

        tooltip_calls = 0
        panel._set_last_action("open_assets_panel", ["open_assets_panel", "open_components_panel"])
        assert tooltip_calls == 0

        panel._set_last_action("open_debug", ["open_debug", "open_assets_panel"])
        assert tooltip_calls == 1
        assert panel._last_action_label.toolTip() == "Current action: Debug Output. 2 recent actions tracked."
        assert panel._last_action_label.statusTip() == panel._last_action_label.toolTip()
        panel.deleteLater()

    def test_recent_actions_visibility_skips_no_op_rewrites(self, qapp, monkeypatch):
        from ui_designer.ui.status_center_panel import StatusCenterPanel

        panel = StatusCenterPanel()
        panel._recent_actions_label.setProperty("_status_center_visible_snapshot", None)

        visible_calls = 0
        original_set_visible = panel._recent_actions_label.setVisible

        def counted_set_visible(value):
            nonlocal visible_calls
            visible_calls += 1
            return original_set_visible(value)

        monkeypatch.setattr(panel._recent_actions_label, "setVisible", counted_set_visible)

        panel._set_last_action("open_assets_panel", ["open_assets_panel", "open_components_panel"])
        assert visible_calls == 1

        visible_calls = 0
        panel._set_last_action("open_assets_panel", ["open_assets_panel", "open_components_panel"])
        assert visible_calls == 0

        panel._set_last_action("open_assets_panel", ["open_assets_panel"])
        assert visible_calls == 1
        assert panel._recent_actions_label.isHidden() is True
        panel.deleteLater()

    def test_health_chip_visibility_skips_no_op_rewrites(self, qapp, monkeypatch):
        from ui_designer.ui.status_center_panel import StatusCenterPanel

        panel = StatusCenterPanel()
        panel._health_chip.setProperty("_status_center_visible_snapshot", None)

        visible_calls = 0
        original_set_visible = panel._health_chip.setVisible

        def counted_set_visible(value):
            nonlocal visible_calls
            visible_calls += 1
            return original_set_visible(value)

        monkeypatch.setattr(panel._health_chip, "setVisible", counted_set_visible)

        panel.set_status(diagnostics_errors=1)
        assert visible_calls == 1

        visible_calls = 0
        panel.set_status(diagnostics_warnings=1)
        assert visible_calls == 0

        panel.set_status()
        assert visible_calls == 1
        assert panel._health_chip.isHidden() is True
        panel.deleteLater()

    def test_runtime_visibility_skips_no_op_rewrites(self, qapp, monkeypatch):
        from ui_designer.ui.status_center_panel import StatusCenterPanel

        panel = StatusCenterPanel()
        panel._runtime_label.setProperty("_status_center_visible_snapshot", None)
        panel._runtime_chip.setProperty("_status_center_visible_snapshot", None)

        label_visible_calls = 0
        chip_visible_calls = 0
        original_label_set_visible = panel._runtime_label.setVisible
        original_chip_set_visible = panel._runtime_chip.setVisible

        def counted_label_set_visible(value):
            nonlocal label_visible_calls
            label_visible_calls += 1
            return original_label_set_visible(value)

        def counted_chip_set_visible(value):
            nonlocal chip_visible_calls
            chip_visible_calls += 1
            return original_chip_set_visible(value)

        monkeypatch.setattr(panel._runtime_label, "setVisible", counted_label_set_visible)
        monkeypatch.setattr(panel._runtime_chip, "setVisible", counted_chip_set_visible)

        panel.set_status(runtime_error="Runtime failed")
        assert label_visible_calls == 1
        assert chip_visible_calls == 1

        label_visible_calls = 0
        chip_visible_calls = 0
        panel.set_status(runtime_error="Bridge lost")
        assert label_visible_calls == 0
        assert chip_visible_calls == 0

        panel.set_status()
        assert label_visible_calls == 1
        assert chip_visible_calls == 1
        assert panel._runtime_label.isHidden() is True
        assert panel._runtime_chip.isHidden() is True
        panel.deleteLater()

    def test_set_widget_icon_skips_no_op_icon_refreshes(self, qapp, monkeypatch):
        from ui_designer.ui.status_center_panel import StatusCenterPanel

        panel = StatusCenterPanel()

        icon_calls = 0
        original_set_icon = panel._suggested_action_button.setIcon

        def counted_set_icon(icon):
            nonlocal icon_calls
            icon_calls += 1
            return original_set_icon(icon)

        monkeypatch.setattr(panel._suggested_action_button, "setIcon", counted_set_icon)

        panel._set_widget_icon(panel._suggested_action_button, "diagnostics", size=16)
        assert icon_calls == 1

        panel._set_widget_icon(panel._suggested_action_button, "diagnostics", size=16)
        assert icon_calls == 1

        panel._set_widget_icon(panel._suggested_action_button, "history", size=16)
        assert icon_calls == 2

        panel.deleteLater()

    def test_repeat_action_menu_accessible_name_skips_no_op_rewrites(self, qapp, monkeypatch):
        from ui_designer.ui.status_center_panel import StatusCenterPanel

        panel = StatusCenterPanel()
        panel._repeat_action_menu.setProperty("_status_center_accessible_snapshot", None)

        accessible_calls = 0
        original_set_accessible_name = panel._repeat_action_menu.setAccessibleName

        def counted_set_accessible_name(text):
            nonlocal accessible_calls
            accessible_calls += 1
            return original_set_accessible_name(text)

        monkeypatch.setattr(panel._repeat_action_menu, "setAccessibleName", counted_set_accessible_name)

        panel._set_last_action("open_assets_panel", ["open_assets_panel", "open_components_panel"])
        assert accessible_calls == 1

        panel._set_last_action("open_assets_panel", ["open_assets_panel", "open_components_panel"])
        assert accessible_calls == 1

        panel._set_last_action("open_debug", ["open_debug", "open_assets_panel"])
        assert accessible_calls == 2

        panel.deleteLater()

    def test_metric_accessible_name_skips_no_op_rewrites(self, qapp, monkeypatch):
        from ui_designer.ui.status_center_panel import StatusCenterPanel

        panel = StatusCenterPanel()
        panel._sdk_value.setProperty("_status_center_accessible_snapshot", None)

        accessible_calls = 0
        original_set_accessible_name = panel._sdk_value.setAccessibleName

        def counted_set_accessible_name(text):
            nonlocal accessible_calls
            accessible_calls += 1
            return original_set_accessible_name(text)

        monkeypatch.setattr(panel._sdk_value, "setAccessibleName", counted_set_accessible_name)

        panel._set_metric_context("SDK", panel._sdk_value, panel._sdk_card, "Ready")
        assert accessible_calls == 1

        panel._set_metric_context("SDK", panel._sdk_value, panel._sdk_card, "Ready")
        assert accessible_calls == 1

        panel._set_metric_context("SDK", panel._sdk_value, panel._sdk_card, "Missing")
        assert accessible_calls == 2

        panel.deleteLater()

    def test_runtime_panel_accessible_name_skips_no_op_rewrites(self, qapp, monkeypatch):
        from ui_designer.ui.status_center_panel import StatusCenterPanel

        panel = StatusCenterPanel()
        panel._runtime_panel.setProperty("_status_center_accessible_snapshot", None)

        accessible_calls = 0
        original_set_accessible_name = panel._runtime_panel.setAccessibleName

        def counted_set_accessible_name(text):
            nonlocal accessible_calls
            accessible_calls += 1
            return original_set_accessible_name(text)

        monkeypatch.setattr(panel._runtime_panel, "setAccessibleName", counted_set_accessible_name)

        panel.set_status(runtime_error="Runtime failed", diagnostics_errors=1)
        assert accessible_calls == 1

        panel.set_status(runtime_error="Runtime failed", diagnostics_warnings=2)
        assert accessible_calls == 1

        panel.set_status(runtime_error="Bridge lost", diagnostics_warnings=2)
        assert accessible_calls == 2

        panel.deleteLater()

    def test_runtime_text_skips_no_op_rewrites(self, qapp, monkeypatch):
        from ui_designer.ui.status_center_panel import StatusCenterPanel

        panel = StatusCenterPanel()
        panel._runtime_title.setProperty("_status_center_text_snapshot", None)
        panel._runtime_label.setProperty("_status_center_text_snapshot", None)

        title_text_calls = 0
        label_text_calls = 0
        original_title_set_text = panel._runtime_title.setText
        original_label_set_text = panel._runtime_label.setText

        def counted_title_set_text(text):
            nonlocal title_text_calls
            title_text_calls += 1
            return original_title_set_text(text)

        def counted_label_set_text(text):
            nonlocal label_text_calls
            label_text_calls += 1
            return original_label_set_text(text)

        monkeypatch.setattr(panel._runtime_title, "setText", counted_title_set_text)
        monkeypatch.setattr(panel._runtime_label, "setText", counted_label_set_text)

        panel.set_status(runtime_error="Runtime failed", diagnostics_errors=1)
        assert title_text_calls == 1
        assert label_text_calls == 1

        panel.set_status(runtime_error="Runtime failed", diagnostics_warnings=2)
        assert title_text_calls == 1
        assert label_text_calls == 1

        panel.set_status(runtime_error="Bridge lost", diagnostics_warnings=2)
        assert title_text_calls == 1
        assert label_text_calls == 2

        panel.deleteLater()

    def test_last_action_text_skips_no_op_rewrites(self, qapp, monkeypatch):
        from ui_designer.ui.status_center_panel import StatusCenterPanel

        panel = StatusCenterPanel()
        panel._last_action_label.setProperty("_status_center_text_snapshot", None)

        text_calls = 0
        original_set_text = panel._last_action_label.setText

        def counted_set_text(text):
            nonlocal text_calls
            text_calls += 1
            return original_set_text(text)

        monkeypatch.setattr(panel._last_action_label, "setText", counted_set_text)

        panel._set_last_action("open_assets_panel", ["open_assets_panel", "open_components_panel"])
        assert text_calls == 1

        panel._set_last_action("open_assets_panel", ["open_assets_panel", "open_components_panel"])
        assert text_calls == 1

        panel._set_last_action("open_debug", ["open_debug", "open_assets_panel"])
        assert text_calls == 2

        panel.deleteLater()

    def test_repeat_action_popup_mode_skips_no_op_rewrites(self, qapp, monkeypatch):
        from ui_designer.ui.status_center_panel import StatusCenterPanel

        panel = StatusCenterPanel()
        panel._repeat_action_button.setProperty("_status_center_popup_mode_snapshot", None)

        popup_mode_calls = 0
        original_set_popup_mode = panel._repeat_action_button.setPopupMode

        def counted_set_popup_mode(mode):
            nonlocal popup_mode_calls
            popup_mode_calls += 1
            return original_set_popup_mode(mode)

        monkeypatch.setattr(panel._repeat_action_button, "setPopupMode", counted_set_popup_mode)

        panel._set_last_action("open_assets_panel", ["open_assets_panel", "open_components_panel"])
        assert popup_mode_calls == 1

        panel._set_last_action("open_assets_panel", ["open_assets_panel", "open_components_panel"])
        assert popup_mode_calls == 1

        panel._set_last_action("open_assets_panel", ["open_assets_panel"])
        assert popup_mode_calls == 2

        panel.deleteLater()

    def test_repeat_action_enabled_state_skips_no_op_rewrites(self, qapp, monkeypatch):
        from ui_designer.ui.status_center_panel import StatusCenterPanel

        panel = StatusCenterPanel()
        panel._repeat_action_button.setProperty("_status_center_enabled_snapshot", None)

        enabled_calls = 0
        original_set_enabled = panel._repeat_action_button.setEnabled

        def counted_set_enabled(value):
            nonlocal enabled_calls
            enabled_calls += 1
            return original_set_enabled(value)

        monkeypatch.setattr(panel._repeat_action_button, "setEnabled", counted_set_enabled)

        panel._set_last_action("open_assets_panel", ["open_assets_panel", "open_components_panel"])
        assert enabled_calls == 1

        panel._set_last_action("open_assets_panel", ["open_assets_panel", "open_components_panel"])
        assert enabled_calls == 1

        panel._set_last_action("", [])
        assert enabled_calls == 2

        panel.deleteLater()

    def test_last_action_accessible_name_skips_no_op_rewrites(self, qapp, monkeypatch):
        from ui_designer.ui.status_center_panel import StatusCenterPanel

        panel = StatusCenterPanel()
        panel._last_action_label.setProperty("_status_center_accessible_snapshot", None)

        accessible_calls = 0
        original_set_accessible_name = panel._last_action_label.setAccessibleName

        def counted_set_accessible_name(text):
            nonlocal accessible_calls
            accessible_calls += 1
            return original_set_accessible_name(text)

        monkeypatch.setattr(panel._last_action_label, "setAccessibleName", counted_set_accessible_name)

        panel._set_last_action("open_assets_panel", ["open_assets_panel", "open_components_panel"])
        assert accessible_calls == 1

        panel._set_last_action("open_assets_panel", ["open_assets_panel", "open_components_panel"])
        assert accessible_calls == 1

        panel._set_last_action("open_debug", ["open_debug", "open_assets_panel"])
        assert accessible_calls == 2

        panel.deleteLater()

    def test_runtime_panel_emits_debug_action(self, qapp):
        from ui_designer.ui.status_center_panel import StatusCenterPanel

        panel = StatusCenterPanel()
        panel.show()
        emitted = []
        panel.action_requested.connect(emitted.append)

        QTest.mouseClick(panel._runtime_panel, Qt.LeftButton)
        panel._runtime_panel.setFocus()
        assert panel._runtime_panel.focusPolicy() == Qt.StrongFocus
        QTest.keyClick(panel._runtime_panel, Qt.Key_Return)

        assert emitted == [
            "open_debug",
            "open_debug",
        ]
        assert panel._runtime_panel.accessibleName() == "Runtime section: Clear. No runtime errors."
        assert panel._runtime_chip.text() == "Clear"
        assert panel._runtime_chip.isHidden() is True
        assert panel._runtime_chip.accessibleName() == (
            "Runtime status: Clear. Open Debug Output. No runtime errors."
        )
        assert panel._last_action_label.text() == "Last action: Debug Output"
        assert panel._repeat_action_button.text() == "Repeat Debug Output"
        panel.deleteLater()

    def test_repeat_action_button_replays_last_action(self, qapp):
        from ui_designer.ui.status_center_panel import StatusCenterPanel

        panel = StatusCenterPanel()
        emitted = []
        panel.action_requested.connect(emitted.append)

        panel.restore_view_state({"last_action": "open_components_panel"})
        assert panel._last_action_host.isHidden() is False
        assert panel._last_action_label.isHidden() is True
        assert panel._repeat_action_button.popupMode() == QToolButton.DelayedPopup
        panel._repeat_action_button.click()

        assert emitted == ["open_components_panel"]
        assert panel._last_action_label.text() == "Last action: Widgets"
        assert panel._repeat_action_button.text() == "Repeat Widgets"
        assert panel._actions_title.text() == "Quick Actions"
        assert panel._actions_title.toolTip() == "Quick actions with the current action ready to repeat."
        assert panel._actions_title.accessibleName() == "Quick actions section: Current action ready to repeat."
        assert panel._recent_actions_label.isHidden() is True
        assert panel._repeat_action_button.accessibleName() == (
            "Repeat action: Widgets. 1 recent action tracked."
        )
        assert panel._repeat_action_button.property("iconKey") == "widgets"
        assert _menu_labels(panel._repeat_action_menu) == ["Widgets", "Clear Recent Actions (1)"]
        panel.deleteLater()

    def test_repeat_action_menu_replays_selected_recent_action(self, qapp):
        from ui_designer.ui.status_center_panel import StatusCenterPanel

        panel = StatusCenterPanel()
        emitted = []
        panel.action_requested.connect(emitted.append)

        panel._project_btn.click()
        panel._assets_btn.click()
        panel._debug_btn.click()
        panel._repeat_action_menu.actions()[1].trigger()

        assert emitted == [
            "open_project_panel",
            "open_assets_panel",
            "open_debug",
            "open_assets_panel",
        ]
        assert panel._last_action_label.text() == "Last action: Assets"
        assert panel._repeat_action_button.popupMode() == QToolButton.MenuButtonPopup
        assert panel._repeat_action_button.text() == "Repeat Assets"
        assert _menu_labels(panel._repeat_action_menu) == [
            "Assets",
            "Debug Output",
            "Project",
            "Clear Recent Actions (3)",
        ]
        replay_actions = [action for action in panel._repeat_action_menu.actions() if not action.isSeparator()]
        assert replay_actions[0].icon().isNull() is False
        assert replay_actions[-1].icon().isNull() is False
        panel.deleteLater()

    def test_repeat_action_menu_can_clear_recent_actions(self, qapp):
        from ui_designer.ui.status_center_panel import StatusCenterPanel

        panel = StatusCenterPanel()

        panel._project_btn.click()
        panel._assets_btn.click()
        clear_action = next(
            action for action in panel._repeat_action_menu.actions() if action.text().startswith("Clear Recent Actions")
        )
        clear_action.trigger()

        assert panel._last_action_host.isHidden() is True
        assert panel._last_action_label.isHidden() is True
        assert panel._last_action_label.text() == "Last action: None"
        assert panel._last_action_label.toolTip() == "No recent action yet."
        assert panel._actions_title.text() == "Quick Actions"
        assert panel._repeat_action_button.isEnabled() is False
        assert panel._repeat_action_button.text() == "Repeat Action"
        assert panel._recent_actions_label.text() == "Recent actions: none yet."
        assert panel._recent_actions_label.toolTip() == "No recent actions yet."
        assert panel._recent_actions_label.accessibleName() == "Recent actions: none yet."
        assert panel._recent_actions_label.isHidden() is True
        assert panel.view_state() == {"last_action": "", "recent_actions": []}
        assert _menu_labels(panel._repeat_action_menu) == ["No recent actions yet"]
        panel.deleteLater()

    def test_repeat_action_menu_tooltips_reflect_recent_history(self, qapp):
        from ui_designer.ui.status_center_panel import StatusCenterPanel

        panel = StatusCenterPanel()

        placeholder = panel._repeat_action_menu.actions()[0]
        assert placeholder.text() == "No recent actions yet"
        assert placeholder.toolTip() == "No recent actions yet."
        assert placeholder.statusTip() == placeholder.toolTip()
        assert placeholder.whatsThis() == placeholder.toolTip()
        assert panel._repeat_action_menu.accessibleName() == "Repeat action menu: no recent actions yet."
        assert panel._repeat_action_menu.toolTip() == panel._repeat_action_menu.accessibleName()
        assert panel._repeat_action_menu.statusTip() == panel._repeat_action_menu.toolTip()
        assert panel._repeat_action_button.toolTip() == "No recent action to repeat yet."

        panel._project_btn.click()
        panel._assets_btn.click()
        panel._debug_btn.click()

        menu_actions = [action for action in panel._repeat_action_menu.actions() if not action.isSeparator()]
        assert [action.text() for action in menu_actions] == [
            "Debug Output",
            "Assets",
            "Project",
            "Clear Recent Actions (3)",
        ]
        assert menu_actions[0].toolTip() == "Repeat the current action: Debug Output."
        assert menu_actions[0].statusTip() == menu_actions[0].toolTip()
        assert menu_actions[0].whatsThis() == menu_actions[0].toolTip()
        assert menu_actions[1].toolTip() == "Replay Assets from recent history."
        assert menu_actions[1].statusTip() == menu_actions[1].toolTip()
        assert menu_actions[1].whatsThis() == menu_actions[1].toolTip()
        assert menu_actions[-1].toolTip() == "Clear 3 recent actions."
        assert menu_actions[-1].statusTip() == menu_actions[-1].toolTip()
        assert menu_actions[-1].whatsThis() == menu_actions[-1].toolTip()
        assert panel._repeat_action_menu.accessibleName() == (
            "Repeat action menu: 3 recent actions. Current action: Debug Output. "
            "Actions: Debug Output, Assets, Project."
        )
        assert panel._repeat_action_menu.statusTip() == panel._repeat_action_menu.toolTip()
        panel.deleteLater()
