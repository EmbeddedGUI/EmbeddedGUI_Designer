"""Qt UI tests for the status center panel."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
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
