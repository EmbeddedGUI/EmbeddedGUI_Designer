"""Focused UI tests for status center runtime visibility simplification."""

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
def test_status_center_hides_redundant_runtime_chip_but_keeps_runtime_metadata(qapp):
    from ui_designer.ui.status_center_panel import StatusCenterPanel

    panel = StatusCenterPanel()

    assert panel._runtime_chip.isHidden() is True
    assert panel._runtime_chip.text() == "Clear"
    assert panel._runtime_chip.accessibleName() == (
        "Runtime status: Clear. Open Debug Output. No runtime errors."
    )

    panel.set_status(sdk_ready=True, can_compile=True, runtime_error="Bridge lost")

    assert panel._runtime_section.isHidden() is False
    assert panel._runtime_title.text() == "Runtime (Issue)"
    assert panel._runtime_label.isHidden() is False
    assert panel._runtime_label.text() == "Bridge lost"
    assert panel._runtime_chip.isHidden() is True
    assert panel._runtime_chip.text() == "Issue"
    assert panel._runtime_chip.property("chipTone") == "danger"
    assert panel._runtime_chip.accessibleName() == (
        "Runtime status: Issue. Open Debug Output. Runtime issue: Bridge lost"
    )
    assert panel._runtime_panel.accessibleName() == "Runtime section: Issue. Bridge lost"
    panel.deleteLater()
