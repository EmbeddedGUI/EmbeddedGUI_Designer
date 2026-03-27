"""Qt UI tests for the status center panel."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtCore import Qt
    from PyQt5.QtTest import QTest
    from PyQt5.QtWidgets import QApplication

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

        assert panel._health_chip.text() == "Critical (2)"
        assert panel._health_chip.property("chipTone") == "danger"
        assert panel._workspace_chip.text() == "Action Needed"
        assert panel._workspace_chip.property("chipTone") == "danger"
        assert panel._health_title.text() == "Diagnostic Mix (4 total)"
        assert panel._health_title.toolTip() == "Diagnostic mix with 4 total diagnostics."
        assert panel._runtime_title.text() == "Runtime (Clear)"
        assert panel._runtime_title.toolTip() == "Runtime status: clear."
        assert panel._diag_value.toolTip() == "Diagnostics: 2 errors, 1 warnings, 1 info"
        assert panel._diag_value.accessibleName() == "Diagnostics value: 2 errors, 1 warnings, 1 info"
        assert panel._diag_card.accessibleName() == "Diagnostics metric: 2 errors, 1 warnings, 1 info"
        assert panel._error_bar.value() == 50
        assert panel._warning_bar.value() == 25
        assert panel._info_bar.value() == 25
        assert panel._error_value.text() == "2 errors (50%)"
        assert panel._warning_value.text() == "1 warning (25%)"
        assert panel._info_value.text() == "1 info item (25%)"
        assert panel._error_value.toolTip() == "Errors: 2 errors (50%)"
        assert panel._warning_value.toolTip() == "Warnings: 1 warning (25%)"
        assert panel._info_value.toolTip() == "Info: 1 info item (25%)"
        assert panel._error_bar.toolTip() == "Errors share: 2 errors (50%)"
        assert panel._warning_bar.toolTip() == "Warnings share: 1 warning (25%)"
        assert panel._info_bar.toolTip() == "Info share: 1 info item (25%)"
        assert panel._error_bar.accessibleName() == "Errors share: 2 errors (50%)"
        assert panel._warning_bar.accessibleName() == "Warnings share: 1 warning (25%)"
        assert panel._info_bar.accessibleName() == "Info share: 1 info item (25%)"
        assert panel._first_error_btn.isEnabled() is True
        assert panel._first_warning_btn.isEnabled() is True
        assert panel._first_error_btn.text() == "Open First Error (2)"
        assert panel._first_warning_btn.text() == "Open First Warning (1)"
        assert panel._health_chip_action == "open_error_diagnostics"
        assert panel._workspace_chip.property("iconKey") == "diagnostics"
        assert panel._workspace_chip.accessibleName() == "Workspace status: Action Needed (Fix First Error (2))"
        assert panel._health_chip.toolTip() == "Open Errors. 2 errors active."
        assert panel._health_chip.property("iconKey") == "diagnostics"
        assert panel._health_chip.accessibleName() == "Diagnostic status: Critical (2)"
        assert panel._workspace_chip.toolTip() == "Action Needed. Start with the first error in Diagnostics. 2 errors active."
        assert panel._health_summary_label.text() == "Summary: 2 errors, 1 warning, 1 info item need attention. Errors lead at 50%."
        assert panel._health_summary_label.toolTip() == panel._health_summary_label.text()
        assert panel._health_summary_label.accessibleName() == (
            "Diagnostic summary: Summary: 2 errors, 1 warning, 1 info item need attention. Errors lead at 50%."
        )
        assert panel._runtime_label.toolTip() == "No runtime errors."
        assert panel._runtime_label.accessibleName() == "Runtime details: No runtime errors."
        assert panel._error_row.toolTip() == "Open Errors. 2 errors active."
        assert panel._warning_row.toolTip() == "Open Warnings. 1 warning active."
        assert panel._info_row.toolTip() == "Open Info. 1 info item active."
        assert panel._first_error_btn.toolTip() == "Jump to the first error in Diagnostics. 2 errors active."
        assert panel._first_warning_btn.toolTip() == "Jump to the first warning in Diagnostics. 1 warning active."
        assert panel._first_error_btn.accessibleName() == "First Error action: Open First Error (2)"
        assert panel._first_warning_btn.accessibleName() == "First Warning action: Open First Warning (1)"
        panel.deleteLater()

    def test_health_chip_runtime_and_buttons_update_across_status_changes(self, qapp):
        from ui_designer.ui.status_center_panel import StatusCenterPanel

        panel = StatusCenterPanel()
        panel.set_status(diagnostics_errors=0, diagnostics_warnings=3, diagnostics_infos=1, runtime_error="Runtime failed")

        assert panel._health_chip.text() == "Attention (3)"
        assert panel._health_chip.property("chipTone") == "warning"
        assert panel._workspace_chip.text() == "Action Needed"
        assert panel._workspace_chip.property("chipTone") == "danger"
        assert panel._workspace_chip.property("iconKey") == "diagnostics"
        assert panel._health_chip_action == "open_warning_diagnostics"
        assert panel._health_chip.toolTip() == "Open Warnings. 3 warnings active."
        assert panel._health_chip.property("iconKey") == "history"
        assert panel._health_title.text() == "Diagnostic Mix (4 total)"
        assert panel._health_summary_label.text() == "Summary: 3 warnings, 1 info item need review. Warnings lead at 75%."
        assert panel._error_value.text() == "0 errors (0%)"
        assert panel._warning_value.text() == "3 warnings (75%)"
        assert panel._info_value.text() == "1 info item (25%)"
        assert panel._warning_bar.toolTip() == "Warnings share: 3 warnings (75%)"
        assert panel._runtime_label.text() == "Runtime failed"
        assert panel._runtime_label.toolTip() == "Runtime failed"
        assert panel._runtime_label.accessibleName() == "Runtime details: Runtime failed"
        assert panel._runtime_title.text() == "Runtime (Issue)"
        assert panel._runtime_title.toolTip() == "Runtime status: issue detected. Runtime failed"
        assert panel._runtime_chip.text() == "Issue"
        assert panel._runtime_chip.property("chipTone") == "danger"
        assert panel._runtime_chip.toolTip() == "Open Debug Output. Runtime issue: Runtime failed"
        assert panel._runtime_chip.accessibleName() == "Runtime status: Issue"
        assert panel._runtime_panel.toolTip() == "Open Debug Output. Runtime issue: Runtime failed"
        assert panel._first_error_btn.isEnabled() is False
        assert panel._first_warning_btn.isEnabled() is True
        assert panel._first_error_btn.text() == "Open First Error"
        assert panel._first_warning_btn.text() == "Open First Warning (3)"
        assert panel._diag_btn.text() == "Diagnostics (4)"
        assert panel._history_btn.text() == "History"
        assert panel._first_error_btn.toolTip() == "Unavailable: no errors are active."
        assert panel._first_warning_btn.toolTip() == "Jump to the first warning in Diagnostics. 3 warnings active."
        assert panel._diag_btn.accessibleName() == "Diagnostics action: Diagnostics (4)"
        assert panel._history_btn.accessibleName() == "History action: History"
        assert panel._first_error_btn.accessibleName() == "First Error action unavailable: Open First Error"
        assert panel._first_warning_btn.accessibleName() == "First Warning action: Open First Warning (3)"

        panel.set_status(diagnostics_errors=0, diagnostics_warnings=0, diagnostics_infos=2, runtime_error="")

        assert panel._health_chip.text() == "Info (2)"
        assert panel._health_chip.property("chipTone") == "accent"
        assert panel._workspace_chip.text() == "Check Workspace"
        assert panel._workspace_chip.property("chipTone") == "warning"
        assert panel._workspace_chip.property("iconKey") == "project"
        assert panel._health_chip_action == "open_info_diagnostics"
        assert panel._health_chip.toolTip() == "Open Info. 2 info items active."
        assert panel._health_chip.property("iconKey") == "debug"
        assert panel._health_title.text() == "Diagnostic Mix (2 total)"
        assert panel._health_summary_label.text() == "Summary: 2 info items available. Info lead at 100%."
        assert panel._error_value.text() == "0 errors (0%)"
        assert panel._warning_value.text() == "0 warnings (0%)"
        assert panel._info_value.text() == "2 info items (100%)"
        assert panel._info_bar.toolTip() == "Info share: 2 info items (100%)"
        assert panel._runtime_label.text() == "No runtime errors."
        assert panel._runtime_label.toolTip() == "No runtime errors."
        assert panel._runtime_label.accessibleName() == "Runtime details: No runtime errors."
        assert panel._runtime_chip.text() == "Clear"
        assert panel._runtime_chip.property("chipTone") == "success"
        assert panel._runtime_chip.toolTip() == "Open Debug Output. No runtime errors."
        assert panel._runtime_chip.accessibleName() == "Runtime status: Clear"
        assert panel._runtime_panel.toolTip() == "Open Debug Output. No runtime errors."
        assert panel._first_error_btn.isEnabled() is False
        assert panel._first_warning_btn.isEnabled() is False
        assert panel._first_error_btn.text() == "Open First Error"
        assert panel._first_warning_btn.text() == "Open First Warning"
        assert panel._diag_btn.text() == "Diagnostics (2)"
        assert panel._history_btn.text() == "History"
        assert panel._first_error_btn.toolTip() == "Unavailable: no errors are active."
        assert panel._first_warning_btn.toolTip() == "Unavailable: no warnings are active."
        assert panel._diag_btn.accessibleName() == "Diagnostics action: Diagnostics (2)"
        assert panel._first_error_btn.accessibleName() == "First Error action unavailable: Open First Error"
        assert panel._first_warning_btn.accessibleName() == "First Warning action unavailable: Open First Warning"

        panel.set_status(diagnostics_errors=0, diagnostics_warnings=0, diagnostics_infos=0, runtime_error="")

        assert panel._health_chip.text() == "Stable"
        assert panel._health_chip.property("chipTone") == "success"
        assert panel._workspace_chip.text() == "Check Workspace"
        assert panel._workspace_chip.property("chipTone") == "warning"
        assert panel._workspace_chip.property("iconKey") == "project"
        assert panel._health_chip_action == "open_diagnostics"
        assert panel._health_chip.toolTip() == "Open Diagnostics. No active diagnostics."
        assert panel._health_chip.property("iconKey") == "diagnostics"
        assert panel._health_title.text() == "Diagnostic Mix"
        assert panel._health_summary_label.text() == "Summary: Diagnostics are clear."
        assert panel._error_value.text() == "0 errors"
        assert panel._warning_value.text() == "0 warnings"
        assert panel._info_value.text() == "0 info items"
        assert panel._error_bar.toolTip() == "Errors share: 0 errors"
        assert panel._warning_bar.toolTip() == "Warnings share: 0 warnings"
        assert panel._info_bar.toolTip() == "Info share: 0 info items"
        assert panel._runtime_label.text() == "No runtime errors."
        assert panel._runtime_label.toolTip() == "No runtime errors."
        assert panel._runtime_label.accessibleName() == "Runtime details: No runtime errors."
        assert panel._runtime_chip.text() == "Clear"
        assert panel._runtime_chip.property("chipTone") == "success"
        assert panel._error_row.toolTip() == "Open Errors. No errors active."
        assert panel._warning_row.toolTip() == "Open Warnings. No warnings active."
        assert panel._info_row.toolTip() == "Open Info. No info items active."
        assert panel._first_error_btn.isEnabled() is False
        assert panel._first_warning_btn.isEnabled() is False
        assert panel._first_error_btn.text() == "Open First Error"
        assert panel._first_warning_btn.text() == "Open First Warning"
        assert panel._diag_btn.text() == "Diagnostics"
        assert panel._history_btn.text() == "History"
        assert panel._first_error_btn.toolTip() == "Unavailable: no errors are active."
        assert panel._first_warning_btn.toolTip() == "Unavailable: no warnings are active."
        assert panel._diag_btn.accessibleName() == "Diagnostics action: Diagnostics"
        assert panel._history_btn.accessibleName() == "History action: History"
        assert panel._first_error_btn.accessibleName() == "First Error action unavailable: Open First Error"
        assert panel._first_warning_btn.accessibleName() == "First Warning action unavailable: Open First Warning"
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
            "Workspace: SDK ready, compile available, Preview Running, runtime issue detected, 2 dirty pages, 1 widget selected, 6 diagnostics. Next: Fix First Error (2)."
        )
        assert panel._workspace_summary_label.accessibleName() == (
            "Workspace summary: Workspace: SDK ready, compile available, Preview Running, runtime issue detected, 2 dirty pages, 1 widget selected, 6 diagnostics. Next: Fix First Error (2)."
        )
        assert panel._workspace_chip.text() == "Action Needed"
        assert panel._workspace_chip.property("chipTone") == "danger"
        assert panel._workspace_chip.property("iconKey") == "diagnostics"
        assert panel._health_title.text() == "Diagnostic Mix (6 total)"
        assert panel._runtime_title.text() == "Runtime (Issue)"
        assert panel._runtime_title.accessibleName() == "Runtime (Issue)"
        assert panel._runtime_label.toolTip() == "Bridge disconnected"
        assert panel._runtime_label.accessibleName() == "Runtime details: Bridge disconnected"
        assert panel._sdk_value.toolTip() == "SDK: SDK Ready"
        assert panel._sdk_value.accessibleName() == "SDK value: SDK Ready"
        assert panel._sdk_card.accessibleName() == "SDK metric: SDK Ready"
        assert panel._compile_value.toolTip() == "Compile: Available"
        assert panel._compile_card.accessibleName() == "Compile metric: Available"
        assert panel._preview_value.toolTip() == "Preview: Preview Running"
        assert panel._preview_card.accessibleName() == "Preview metric: Preview Running"
        assert panel._selection_value.toolTip() == "Selection: 1 widgets"
        assert panel._selection_card.accessibleName() == "Selection metric: 1 widgets"
        assert panel._dirty_value.toolTip() == "Dirty Pages: 2"
        assert panel._dirty_card.accessibleName() == "Dirty Pages metric: 2"
        assert panel._sdk_card.toolTip() == "Open Project. SDK workspace is ready."
        assert panel._compile_card.toolTip() == "Open Debug Output. Compile pipeline is available."
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
        assert panel._diag_btn.text() == "Diagnostics (6)"
        assert panel._diag_btn.toolTip() == "Open Diagnostics. 2 errors, 1 warning, 3 info items."
        assert panel._diag_btn.accessibleName() == "Diagnostics action: Diagnostics (6)"
        assert panel._history_btn.text() == "History (2)"
        assert panel._history_btn.toolTip() == "Open History. 2 dirty pages."
        assert panel._history_btn.accessibleName() == "History action: History (2)"
        assert panel._debug_btn.toolTip() == "Open Debug Output. Runtime issue: Bridge disconnected"
        assert panel._project_btn.toolTip() == "Open Project. SDK workspace is ready."
        assert panel._structure_btn.text() == "Structure (1)"
        assert panel._structure_btn.toolTip() == "Open Structure. 1 widget selected."
        assert panel._structure_btn.accessibleName() == "Structure action: Structure (1)"
        assert panel._suggested_action_button.text() == "Fix First Error (2)"
        assert panel._suggested_action_button.property("iconKey") == "diagnostics"
        assert panel._suggested_action_button.toolTip() == "Start with the first error in Diagnostics. 2 errors active."
        assert panel._suggested_action_button.accessibleName() == "Suggested status action: Fix First Error (2)"
        assert panel._suggested_action_summary_label.text() == (
            "Guidance: Start with the first error in Diagnostics. 2 errors active."
        )
        assert panel._repeat_action_button.accessibleName() == "Repeat last action"
        assert panel._runtime_chip.text() == "Issue"
        assert panel._runtime_chip.toolTip() == "Open Debug Output. Runtime issue: Bridge disconnected"
        assert panel._runtime_panel.toolTip() == "Open Debug Output. Runtime issue: Bridge disconnected"
        assert panel._sdk_card.statusTip() == panel._sdk_card.toolTip()
        assert panel._dirty_card.statusTip() == panel._dirty_card.toolTip()
        assert panel._diag_btn.statusTip() == panel._diag_btn.toolTip()
        assert panel._history_btn.statusTip() == panel._history_btn.toolTip()
        assert panel._workspace_summary_label.toolTip() == panel._workspace_summary_label.text()
        panel.deleteLater()

    def test_static_quick_action_buttons_expose_default_hints(self, qapp):
        from ui_designer.ui.status_center_panel import StatusCenterPanel

        panel = StatusCenterPanel()

        assert panel._workspace_summary_label.accessibleName() == (
            "Workspace summary: Workspace: SDK missing, compile unavailable, Preview Idle, runtime clear, 0 dirty pages, 0 widgets selected, diagnostics clear. Next: Configure SDK."
        )
        assert panel._header_title.text() == "Status Center (Workspace)"
        assert panel._header_title.toolTip() == "Status Center focused on Workspace. Check Workspace."
        assert panel._header_title.accessibleName() == "Status Center (Workspace)"
        assert panel._header_subtitle.text() == "Workspace checks are pending. Focus on Configure SDK."
        assert panel._header_subtitle.toolTip() == (
            "Status Center: Check Workspace. Open Project to configure the SDK workspace. SDK root is missing or invalid."
        )
        assert panel._header_subtitle.accessibleName() == "Workspace checks are pending. Focus on Configure SDK."
        assert panel._health_title.text() == "Diagnostic Mix"
        assert panel._health_title.accessibleName() == "Diagnostic Mix"
        assert panel._runtime_title.text() == "Runtime (Clear)"
        assert panel._runtime_title.accessibleName() == "Runtime (Clear)"
        assert panel._actions_title.text() == "Quick Actions"
        assert panel._actions_title.toolTip() == "Quick actions with no saved recent status center actions."
        assert panel._actions_title.accessibleName() == "Quick Actions"
        assert panel._last_action_label.text() == "Last action: None"
        assert panel._last_action_label.toolTip() == "No recent status center action is available yet."
        assert panel._last_action_label.accessibleName() == "Last action: None. No recent actions saved."
        assert panel._recent_actions_label.text() == "Recent actions: none saved."
        assert panel._recent_actions_label.toolTip() == "Status center has not saved any recent actions yet."
        assert panel._recent_actions_label.accessibleName() == "Recent actions: none saved."
        assert panel._suggested_action_label.text() == "Suggested next step (Workspace):"
        assert panel._suggested_action_label.toolTip() == (
            "Suggested next step in Workspace. Open Project to configure the SDK workspace. SDK root is missing or invalid."
        )
        assert panel._suggested_action_label.accessibleName() == "Suggested next step (Workspace): Configure SDK"
        assert panel._suggested_action_button.text() == "Configure SDK"
        assert panel._suggested_action_button.property("iconKey") == "project"
        assert panel._suggested_action_button.toolTip() == (
            "Open Project to configure the SDK workspace. SDK root is missing or invalid."
        )
        assert panel._suggested_action_button.accessibleName() == "Suggested status action: Configure SDK"
        assert panel._suggested_action_summary_label.text() == (
            "Guidance: Open Project to configure the SDK workspace. SDK root is missing or invalid."
        )
        assert panel._suggested_action_summary_label.accessibleName() == (
            "Suggested action guidance: Guidance: Open Project to configure the SDK workspace. SDK root is missing or invalid."
        )
        assert panel._workspace_chip.text() == "Check Workspace"
        assert panel._workspace_chip.property("chipTone") == "warning"
        assert panel._workspace_chip.toolTip() == (
            "Check Workspace. Open Project to configure the SDK workspace. SDK root is missing or invalid."
        )
        assert panel._workspace_chip.property("iconKey") == "project"
        assert panel._workspace_chip.accessibleName() == "Workspace status: Check Workspace (Configure SDK)"
        assert panel._repeat_action_button.accessibleName() == "Repeat last action"
        assert panel._repeat_action_button.property("iconKey") == "history"
        assert panel._workspace_summary_label.text() == (
            "Workspace: SDK missing, compile unavailable, Preview Idle, runtime clear, 0 dirty pages, 0 widgets selected, diagnostics clear. Next: Configure SDK."
        )
        assert panel._sdk_value.toolTip() == "SDK: SDK Missing"
        assert panel._compile_value.toolTip() == "Compile: Unavailable"
        assert panel._preview_value.toolTip() == "Preview: Preview Idle"
        assert panel._selection_value.toolTip() == "Selection: 0 widgets"
        assert panel._dirty_value.toolTip() == "Dirty Pages: 0"
        assert panel._health_summary_label.accessibleName() == "Diagnostic summary: Summary: Diagnostics are clear."
        assert panel._health_chip.accessibleName() == "Diagnostic status: Stable"
        assert panel._health_chip.property("iconKey") == "diagnostics"
        assert panel._runtime_label.toolTip() == "No runtime errors."
        assert panel._runtime_label.accessibleName() == "Runtime details: No runtime errors."
        assert panel._runtime_chip.text() == "Clear"
        assert panel._runtime_chip.toolTip() == "Open Debug Output. No runtime errors."
        assert panel._runtime_chip.accessibleName() == "Runtime status: Clear"
        assert panel._components_btn.toolTip() == "Open Components."
        assert panel._components_btn.statusTip() == "Open Components."
        assert panel._components_btn.accessibleName() == "Components action: Components"
        assert panel._diag_btn.accessibleName() == "Diagnostics action: Diagnostics"
        assert panel._history_btn.accessibleName() == "History action: History"
        assert panel._structure_btn.accessibleName() == "Structure action: Structure"
        assert panel._first_error_btn.accessibleName() == "First Error action unavailable: Open First Error"
        assert panel._first_warning_btn.accessibleName() == "First Warning action unavailable: Open First Warning"
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
        assert panel._suggested_action_button.text() == "Configure SDK"
        assert panel._suggested_action_summary_label.text() == (
            "Guidance: Open Project to configure the SDK workspace. SDK root is missing or invalid."
        )

        panel.set_status(sdk_ready=True, can_compile=True, diagnostics_errors=1)
        assert panel._header_title.text() == "Status Center (Diagnostics)"
        assert panel._header_subtitle.text() == "Action needed now. Focus on Fix First Error (1)."
        assert panel._suggested_action_label.text() == "Suggested next step (Diagnostics):"
        assert panel._suggested_action_button.text() == "Fix First Error (1)"
        assert panel._suggested_action_button.property("iconKey") == "diagnostics"
        assert panel._workspace_chip.property("iconKey") == "diagnostics"
        assert panel._suggested_action_summary_label.text() == (
            "Guidance: Start with the first error in Diagnostics. 1 error active."
        )

        panel.set_status(sdk_ready=True, can_compile=True, diagnostics_warnings=2)
        assert panel._header_title.text() == "Status Center (Diagnostics)"
        assert panel._header_subtitle.text() == "Workspace checks are pending. Focus on Review First Warning (2)."
        assert panel._suggested_action_label.text() == "Suggested next step (Diagnostics):"
        assert panel._suggested_action_button.text() == "Review First Warning (2)"
        assert panel._suggested_action_button.property("iconKey") == "diagnostics"
        assert panel._workspace_chip.property("iconKey") == "diagnostics"
        assert panel._suggested_action_summary_label.text() == (
            "Guidance: Review the first warning in Diagnostics. 2 warnings active."
        )

        panel.set_status(sdk_ready=True, can_compile=True, runtime_error="Bridge lost")
        assert panel._header_title.text() == "Status Center (Runtime)"
        assert panel._header_subtitle.text() == "Action needed now. Focus on Inspect Debug Output."
        assert panel._suggested_action_label.text() == "Suggested next step (Runtime):"
        assert panel._suggested_action_button.text() == "Inspect Debug Output"
        assert panel._suggested_action_button.property("iconKey") == "debug"
        assert panel._workspace_chip.property("iconKey") == "debug"
        assert panel._suggested_action_summary_label.text() == "Guidance: Inspect the latest runtime output. Bridge lost"

        panel.set_status(sdk_ready=True, can_compile=False)
        assert panel._header_title.text() == "Status Center (Build)"
        assert panel._header_subtitle.text() == "Workspace checks are pending. Focus on Check Compile Output."
        assert panel._suggested_action_label.text() == "Suggested next step (Build):"
        assert panel._suggested_action_button.text() == "Check Compile Output"
        assert panel._suggested_action_button.property("iconKey") == "debug"
        assert panel._workspace_chip.property("iconKey") == "debug"
        assert panel._suggested_action_summary_label.text() == (
            "Guidance: Open Debug Output to inspect compile availability. Compile pipeline is unavailable."
        )

        panel.set_status(sdk_ready=True, can_compile=True, dirty_pages=2)
        assert panel._header_title.text() == "Status Center (History)"
        assert panel._header_subtitle.text() == "Work is in progress. Focus on Review History (2)."
        assert panel._suggested_action_label.text() == "Suggested next step (History):"
        assert panel._suggested_action_button.text() == "Review History (2)"
        assert panel._suggested_action_button.property("iconKey") == "history"
        assert panel._workspace_chip.property("iconKey") == "history"
        assert panel._suggested_action_summary_label.text() == "Guidance: Review unsaved changes in History. 2 dirty pages pending."

        panel.set_status(sdk_ready=True, can_compile=True, selection_count=3)
        assert panel._header_title.text() == "Status Center (Selection)"
        assert panel._header_subtitle.text() == "Work is in progress. Focus on Inspect Selection (3)."
        assert panel._suggested_action_label.text() == "Suggested next step (Selection):"
        assert panel._suggested_action_button.text() == "Inspect Selection (3)"
        assert panel._suggested_action_button.property("iconKey") == "structure"
        assert panel._workspace_chip.property("iconKey") == "structure"
        assert panel._suggested_action_summary_label.text() == "Guidance: Open Structure for the current selection. 3 widgets selected."

        panel.set_status(sdk_ready=True, can_compile=True, diagnostics_infos=2)
        assert panel._header_title.text() == "Status Center (Diagnostics)"
        assert panel._header_subtitle.text() == "Work is in progress. Focus on Inspect Info (2)."
        assert panel._suggested_action_label.text() == "Suggested next step (Diagnostics):"
        assert panel._suggested_action_button.text() == "Inspect Info (2)"
        assert panel._suggested_action_button.property("iconKey") == "debug"
        assert panel._workspace_chip.property("iconKey") == "debug"
        assert panel._suggested_action_summary_label.text() == "Guidance: Inspect informational diagnostics. 2 info items active."

        panel.set_status(sdk_ready=True, can_compile=True)
        assert panel._header_title.text() == "Status Center (Diagnostics)"
        assert panel._header_subtitle.text() == "Workspace looks ready. Open Diagnostics remains available."
        assert panel._suggested_action_label.text() == "Suggested next step (Diagnostics):"
        assert panel._suggested_action_button.text() == "Open Diagnostics"
        assert panel._suggested_action_button.property("iconKey") == "diagnostics"
        assert panel._workspace_chip.property("iconKey") == "diagnostics"
        assert panel._suggested_action_summary_label.text() == "Guidance: Open Diagnostics for a full health review."
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
        panel._health_chip.click()

        assert emitted == [
            "open_error_diagnostics",
            "open_warning_diagnostics",
            "open_info_diagnostics",
            "open_diagnostics",
        ]
        assert panel._repeat_action_button.text() == "Repeat Diagnostics"
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
        assert panel._last_action_label.toolTip() == "Current status center action: Assets. 4 recent actions saved."
        assert panel._last_action_label.accessibleName() == "Last action: Assets. 4 recent actions saved."
        assert panel._actions_title.text() == "Quick Actions (4 recent actions)"
        assert panel._actions_title.toolTip() == "Quick actions with 4 saved recent status center actions."
        assert panel._repeat_action_button.text() == "Repeat Assets"
        assert panel._repeat_action_button.accessibleName() == "Repeat Assets action"
        assert panel._repeat_action_button.property("iconKey") == "assets"
        assert panel._recent_actions_label.text() == "Recent actions (4): Assets, Components, Structure, +1 more."
        assert panel._recent_actions_label.toolTip() == (
            "4 recent status center actions: Assets, Components, Structure, Project"
        )
        assert panel._recent_actions_label.accessibleName() == (
            "Recent actions summary: 4 recent actions saved. Assets, Components, Structure, Project."
        )
        assert panel._repeat_action_button.toolTip() == (
            "Repeat Assets. 4 recent status center actions saved. Use the menu arrow to replay an older action."
        )
        assert _menu_labels(panel._repeat_action_menu) == [
            "Assets",
            "Components",
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
        assert panel._diag_card.accessibleName() == "Diagnostics metric: 0 errors, 0 warnings, 0 info"
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
        assert panel._info_row.accessibleName() == "Info diagnostics"
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
        assert panel._warning_row.accessibleName() == "Warnings diagnostics"
        assert panel._repeat_action_button.text() == "Repeat Warnings"
        panel.deleteLater()

    def test_restore_view_state_updates_last_action_label(self, qapp):
        from ui_designer.ui.status_center_panel import StatusCenterPanel

        panel = StatusCenterPanel()

        assert panel._last_action_label.text() == "Last action: None"
        assert panel._last_action_label.toolTip() == "No recent status center action is available yet."
        assert panel._last_action_label.accessibleName() == "Last action: None. No recent actions saved."
        assert panel._repeat_action_button.isEnabled() is False
        assert panel._repeat_action_button.text() == "Repeat Action"
        assert _menu_labels(panel._repeat_action_menu) == ["No recent actions"]
        panel.restore_view_state({"last_action": "open_page_fields", "recent_actions": ["open_page_fields", "open_debug"]})
        assert panel._last_action_label.text() == "Last action: Fields"
        assert panel._last_action_label.toolTip() == "Current status center action: Fields. 2 recent actions saved."
        assert panel._last_action_label.accessibleName() == "Last action: Fields. 2 recent actions saved."
        assert panel._actions_title.text() == "Quick Actions (2 recent actions)"
        assert panel._repeat_action_button.isEnabled() is True
        assert panel._repeat_action_button.text() == "Repeat Fields"
        assert panel._repeat_action_button.accessibleName() == "Repeat Fields action"
        assert panel._repeat_action_button.property("iconKey") == "page"
        assert panel._recent_actions_label.text() == "Recent actions (2): Fields, Debug Output."
        assert panel._recent_actions_label.toolTip() == "2 recent status center actions: Fields, Debug Output"
        assert panel._recent_actions_label.accessibleName() == (
            "Recent actions summary: 2 recent actions saved. Fields, Debug Output."
        )
        assert panel._repeat_action_button.toolTip() == (
            "Repeat Fields. 2 recent status center actions saved. Use the menu arrow to replay an older action."
        )
        assert panel.view_state() == {
            "last_action": "open_page_fields",
            "recent_actions": ["open_page_fields", "open_debug"],
        }
        assert _menu_labels(panel._repeat_action_menu) == ["Fields", "Debug Output", "Clear Recent Actions (2)"]

        panel.restore_view_state(None)
        assert panel._last_action_label.text() == "Last action: None"
        assert panel._last_action_label.toolTip() == "No recent status center action is available yet."
        assert panel._last_action_label.accessibleName() == "Last action: None. No recent actions saved."
        assert panel._actions_title.text() == "Quick Actions"
        assert panel._repeat_action_button.isEnabled() is False
        assert panel._repeat_action_button.text() == "Repeat Action"
        assert panel._recent_actions_label.text() == "Recent actions: none saved."
        assert panel._recent_actions_label.toolTip() == "Status center has not saved any recent actions yet."
        assert panel._recent_actions_label.accessibleName() == "Recent actions: none saved."
        assert panel._repeat_action_button.toolTip() == "No recent action to repeat."
        assert panel.view_state() == {"last_action": "", "recent_actions": []}
        assert _menu_labels(panel._repeat_action_menu) == ["No recent actions"]
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
        assert panel._runtime_panel.accessibleName() == "Runtime section"
        assert panel._runtime_chip.text() == "Clear"
        assert panel._runtime_chip.accessibleName() == "Runtime status: Clear"
        assert panel._last_action_label.text() == "Last action: Debug Output"
        assert panel._repeat_action_button.text() == "Repeat Debug Output"
        panel.deleteLater()

    def test_repeat_action_button_replays_last_action(self, qapp):
        from ui_designer.ui.status_center_panel import StatusCenterPanel

        panel = StatusCenterPanel()
        emitted = []
        panel.action_requested.connect(emitted.append)

        panel.restore_view_state({"last_action": "open_components_panel"})
        panel._repeat_action_button.click()

        assert emitted == ["open_components_panel"]
        assert panel._last_action_label.text() == "Last action: Components"
        assert panel._repeat_action_button.text() == "Repeat Components"
        assert panel._repeat_action_button.accessibleName() == "Repeat Components action"
        assert panel._repeat_action_button.property("iconKey") == "widgets"
        assert _menu_labels(panel._repeat_action_menu) == ["Components", "Clear Recent Actions (1)"]
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

        assert panel._last_action_label.text() == "Last action: None"
        assert panel._last_action_label.toolTip() == "No recent status center action is available yet."
        assert panel._actions_title.text() == "Quick Actions"
        assert panel._repeat_action_button.isEnabled() is False
        assert panel._repeat_action_button.text() == "Repeat Action"
        assert panel._recent_actions_label.text() == "Recent actions: none saved."
        assert panel._recent_actions_label.toolTip() == "Status center has not saved any recent actions yet."
        assert panel._recent_actions_label.accessibleName() == "Recent actions: none saved."
        assert panel.view_state() == {"last_action": "", "recent_actions": []}
        assert _menu_labels(panel._repeat_action_menu) == ["No recent actions"]
        panel.deleteLater()

    def test_repeat_action_menu_tooltips_reflect_recent_history(self, qapp):
        from ui_designer.ui.status_center_panel import StatusCenterPanel

        panel = StatusCenterPanel()

        placeholder = panel._repeat_action_menu.actions()[0]
        assert placeholder.text() == "No recent actions"
        assert placeholder.toolTip() == "Status center has not saved any recent actions yet."
        assert panel._repeat_action_button.toolTip() == "No recent action to repeat."

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
        assert menu_actions[1].toolTip() == "Replay Assets from recent status center history."
        assert menu_actions[-1].toolTip() == "Forget 3 recent status center actions."
        panel.deleteLater()
