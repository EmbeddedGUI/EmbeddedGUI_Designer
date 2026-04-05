"""Focused UI tests for status center header visibility simplification."""

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
def test_status_center_header_hides_redundant_eyebrow_and_metrics(qapp):
    from ui_designer.ui.status_center_panel import StatusCenterPanel

    panel = StatusCenterPanel()

    assert panel._header_eyebrow.text() == "Workspace"
    assert panel._header_eyebrow.isHidden() is True
    assert panel._header_eyebrow.accessibleName() == "Workspace health command surface."
    assert panel._header_metrics_frame.isHidden() is True
    assert panel._header_metrics_frame.accessibleName() == (
        "Status center header metrics: Focus: Workspace. 0 recent actions."
    )

    panel.set_status(sdk_ready=True, can_compile=True, dirty_pages=2)

    assert panel._header_eyebrow.isHidden() is True
    assert panel._header_metrics_frame.isHidden() is True
    assert panel._header_metrics_frame.accessibleName() == (
        "Status center header metrics: Focus: History. 0 recent actions."
    )
    panel.deleteLater()
