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
        panel.deleteLater()

    def test_health_chip_runtime_and_buttons_update_across_status_changes(self, qapp):
        from ui_designer.ui.status_center_panel import StatusCenterPanel

        panel = StatusCenterPanel()
        panel.set_status(diagnostics_errors=0, diagnostics_warnings=3, diagnostics_infos=1, runtime_error="Runtime failed")

        assert panel._health_chip.text() == "Attention"
        assert panel._health_chip.property("chipTone") == "warning"
        assert panel._runtime_label.text() == "Runtime failed"
        assert panel._first_error_btn.isEnabled() is False
        assert panel._first_warning_btn.isEnabled() is True

        panel.set_status(diagnostics_errors=0, diagnostics_warnings=0, diagnostics_infos=0, runtime_error="")

        assert panel._health_chip.text() == "Stable"
        assert panel._health_chip.property("chipTone") == "success"
        assert panel._runtime_label.text() == "No runtime errors."
        assert panel._first_error_btn.isEnabled() is False
        assert panel._first_warning_btn.isEnabled() is False
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
        panel.deleteLater()

    def test_restore_view_state_updates_last_action_label(self, qapp):
        from ui_designer.ui.status_center_panel import StatusCenterPanel

        panel = StatusCenterPanel()

        assert panel._last_action_label.text() == "Last action: None"
        panel.restore_view_state({"last_action": "open_page_fields"})
        assert panel._last_action_label.text() == "Last action: Fields"
        assert panel.view_state() == {"last_action": "open_page_fields"}

        panel.restore_view_state(None)
        assert panel._last_action_label.text() == "Last action: None"
        assert panel.view_state() == {"last_action": ""}
        panel.deleteLater()
