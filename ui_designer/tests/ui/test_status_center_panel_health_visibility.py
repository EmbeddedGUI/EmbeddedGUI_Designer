"""Focused UI tests for status center health visibility simplification."""

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
def test_status_center_hides_redundant_health_chip_but_keeps_health_metadata(qapp):
    from ui_designer.ui.status_center_panel import StatusCenterPanel

    panel = StatusCenterPanel()

    assert panel._health_chip.isHidden() is True
    assert panel._health_chip.text() == "Stable"
    assert panel._health_chip.accessibleName() == (
        "Diagnostic status: Stable. Open Diagnostics. No active diagnostics."
    )

    panel.set_status(diagnostics_errors=2, diagnostics_warnings=1, diagnostics_infos=1)

    assert panel._health_chip.isHidden() is True
    assert panel._health_chip.text() == "Critical (2)"
    assert panel._health_chip.property("chipTone") == "danger"
    assert panel._health_chip.accessibleName() == (
        "Diagnostic status: Critical (2). Open Errors. 2 errors active."
    )
    assert panel._health_title.text() == "Diagnostic Mix (4 total)"
    assert panel._health_summary_label.isHidden() is False
    assert panel._error_row.isHidden() is False
    assert panel._warning_row.isHidden() is False
    assert panel._info_row.isHidden() is False
    panel.deleteLater()
