"""Focused UI tests for main window runtime indicator visibility simplification."""

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


def _close_window(window):
    try:
        window.close()
        window.deleteLater()
    except Exception:
        pass


@_skip_no_qt
def test_main_window_hides_redundant_runtime_indicator_but_keeps_runtime_metadata(qapp):
    from ui_designer.ui.main_window import MainWindow

    window = MainWindow("")

    assert window._runtime_chip.isHidden() is True
    assert window._runtime_chip.text() == "Preview Idle"
    assert window._runtime_chip.accessibleName() == "Preview runtime indicator: Preview Idle."

    window._last_runtime_error_text = "Bridge lost"
    window._update_workspace_chips()

    assert window._runtime_chip.isHidden() is True
    assert window._runtime_chip.text() == "Runtime Issue"
    assert window._runtime_chip.toolTip() == "Open Debug Output. Runtime issue: Bridge lost"
    assert window._runtime_chip.accessibleName() == "Preview runtime indicator: Runtime Issue."
    _close_window(window)
