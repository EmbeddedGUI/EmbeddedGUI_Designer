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

        assert panel._health_chip.text() == "Critical"
        assert panel._health_chip.property("chipTone") == "danger"
        assert panel._error_bar.value() == 50
        assert panel._warning_bar.value() == 25
        assert panel._info_bar.value() == 25
        assert panel._first_error_btn.isEnabled() is True
        assert panel._first_warning_btn.isEnabled() is True
        assert panel._first_error_btn.text() == "Open First Error (2)"
        assert panel._first_warning_btn.text() == "Open First Warning (1)"
        assert panel._health_chip_action == "open_error_diagnostics"
        assert panel._health_chip.toolTip() == "Open Errors. 2 errors active."
        assert panel._error_row.toolTip() == "Open Errors. 2 errors active."
        assert panel._warning_row.toolTip() == "Open Warnings. 1 warning active."
        assert panel._info_row.toolTip() == "Open Info. 1 info item active."
        assert panel._first_error_btn.toolTip() == "Jump to the first error in Diagnostics. 2 errors active."
        assert panel._first_warning_btn.toolTip() == "Jump to the first warning in Diagnostics. 1 warning active."
        panel.deleteLater()

    def test_health_chip_runtime_and_buttons_update_across_status_changes(self, qapp):
        from ui_designer.ui.status_center_panel import StatusCenterPanel

        panel = StatusCenterPanel()
        panel.set_status(diagnostics_errors=0, diagnostics_warnings=3, diagnostics_infos=1, runtime_error="Runtime failed")

        assert panel._health_chip.text() == "Attention"
        assert panel._health_chip.property("chipTone") == "warning"
        assert panel._health_chip_action == "open_warning_diagnostics"
        assert panel._health_chip.toolTip() == "Open Warnings. 3 warnings active."
        assert panel._runtime_label.text() == "Runtime failed"
        assert panel._runtime_panel.toolTip() == "Open Debug Output. Runtime issue: Runtime failed"
        assert panel._first_error_btn.isEnabled() is False
        assert panel._first_warning_btn.isEnabled() is True
        assert panel._first_error_btn.text() == "Open First Error"
        assert panel._first_warning_btn.text() == "Open First Warning (3)"
        assert panel._first_error_btn.toolTip() == "Unavailable: no errors are active."
        assert panel._first_warning_btn.toolTip() == "Jump to the first warning in Diagnostics. 3 warnings active."

        panel.set_status(diagnostics_errors=0, diagnostics_warnings=0, diagnostics_infos=2, runtime_error="")

        assert panel._health_chip.text() == "Info"
        assert panel._health_chip.property("chipTone") == "accent"
        assert panel._health_chip_action == "open_info_diagnostics"
        assert panel._health_chip.toolTip() == "Open Info. 2 info items active."
        assert panel._runtime_label.text() == "No runtime errors."
        assert panel._runtime_panel.toolTip() == "Open Debug Output. No runtime errors."
        assert panel._first_error_btn.isEnabled() is False
        assert panel._first_warning_btn.isEnabled() is False
        assert panel._first_error_btn.text() == "Open First Error"
        assert panel._first_warning_btn.text() == "Open First Warning"
        assert panel._first_error_btn.toolTip() == "Unavailable: no errors are active."
        assert panel._first_warning_btn.toolTip() == "Unavailable: no warnings are active."

        panel.set_status(diagnostics_errors=0, diagnostics_warnings=0, diagnostics_infos=0, runtime_error="")

        assert panel._health_chip.text() == "Stable"
        assert panel._health_chip.property("chipTone") == "success"
        assert panel._health_chip_action == "open_diagnostics"
        assert panel._health_chip.toolTip() == "Open Diagnostics. No active diagnostics."
        assert panel._runtime_label.text() == "No runtime errors."
        assert panel._error_row.toolTip() == "Open Errors. No errors active."
        assert panel._warning_row.toolTip() == "Open Warnings. No warnings active."
        assert panel._info_row.toolTip() == "Open Info. No info items active."
        assert panel._first_error_btn.isEnabled() is False
        assert panel._first_warning_btn.isEnabled() is False
        assert panel._first_error_btn.text() == "Open First Error"
        assert panel._first_warning_btn.text() == "Open First Warning"
        assert panel._first_error_btn.toolTip() == "Unavailable: no errors are active."
        assert panel._first_warning_btn.toolTip() == "Unavailable: no warnings are active."
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

        assert panel._sdk_card.toolTip() == "Open Project. SDK workspace is ready."
        assert panel._compile_card.toolTip() == "Open Debug Output. Compile pipeline is available."
        assert panel._diag_card.toolTip() == "Open Diagnostics. 2 errors, 1 warning, 3 info items."
        assert panel._preview_card.toolTip() == "Open Debug Output. Preview Running."
        assert panel._selection_card.toolTip() == "Open Structure. 1 widget selected."
        assert panel._dirty_card.toolTip() == "Open History. 2 dirty pages."
        assert panel._runtime_panel.toolTip() == "Open Debug Output. Runtime issue: Bridge disconnected"
        assert panel._sdk_card.statusTip() == panel._sdk_card.toolTip()
        assert panel._dirty_card.statusTip() == panel._dirty_card.toolTip()
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
        assert panel._repeat_action_button.text() == "Repeat Assets"
        assert panel._recent_actions_label.text() == "Recent actions: Assets, Components, Structure, +1 more."
        assert panel._recent_actions_label.toolTip() == (
            "4 recent status center actions: Assets, Components, Structure, Project"
        )
        assert panel._repeat_action_button.toolTip() == (
            "Repeat Assets. 4 recent status center actions saved. Use the menu arrow to replay an older action."
        )
        assert _menu_labels(panel._repeat_action_menu) == [
            "Assets",
            "Components",
            "Structure",
            "Project",
            "Clear Recent Actions",
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
            "Clear Recent Actions",
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
            "Clear Recent Actions",
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
        assert panel._diag_card.accessibleName() == "Diagnostics metric"
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
        assert _menu_labels(panel._repeat_action_menu) == ["Info", "Warnings", "Errors", "Clear Recent Actions"]
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
        assert panel._repeat_action_button.isEnabled() is False
        assert panel._repeat_action_button.text() == "Repeat Action"
        assert _menu_labels(panel._repeat_action_menu) == ["No recent actions"]
        panel.restore_view_state({"last_action": "open_page_fields", "recent_actions": ["open_page_fields", "open_debug"]})
        assert panel._last_action_label.text() == "Last action: Fields"
        assert panel._repeat_action_button.isEnabled() is True
        assert panel._repeat_action_button.text() == "Repeat Fields"
        assert panel._recent_actions_label.text() == "Recent actions: Fields, Debug Output."
        assert panel._recent_actions_label.toolTip() == "2 recent status center actions: Fields, Debug Output"
        assert panel._repeat_action_button.toolTip() == (
            "Repeat Fields. 2 recent status center actions saved. Use the menu arrow to replay an older action."
        )
        assert panel.view_state() == {
            "last_action": "open_page_fields",
            "recent_actions": ["open_page_fields", "open_debug"],
        }
        assert _menu_labels(panel._repeat_action_menu) == ["Fields", "Debug Output", "Clear Recent Actions"]

        panel.restore_view_state(None)
        assert panel._last_action_label.text() == "Last action: None"
        assert panel._repeat_action_button.isEnabled() is False
        assert panel._repeat_action_button.text() == "Repeat Action"
        assert panel._recent_actions_label.text() == "Recent actions: none saved."
        assert panel._recent_actions_label.toolTip() == "Status center has not saved any recent actions yet."
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
        assert _menu_labels(panel._repeat_action_menu) == ["Components", "Clear Recent Actions"]
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
            "Clear Recent Actions",
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
        clear_action = next(action for action in panel._repeat_action_menu.actions() if action.text() == "Clear Recent Actions")
        clear_action.trigger()

        assert panel._last_action_label.text() == "Last action: None"
        assert panel._repeat_action_button.isEnabled() is False
        assert panel._repeat_action_button.text() == "Repeat Action"
        assert panel._recent_actions_label.text() == "Recent actions: none saved."
        assert panel._recent_actions_label.toolTip() == "Status center has not saved any recent actions yet."
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
            "Clear Recent Actions",
        ]
        assert menu_actions[0].toolTip() == "Repeat the current action: Debug Output."
        assert menu_actions[1].toolTip() == "Replay Assets from recent status center history."
        assert menu_actions[-1].toolTip() == "Forget 3 recent status center actions."
        panel.deleteLater()
