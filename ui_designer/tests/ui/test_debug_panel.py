"""Qt UI tests for the debug panel."""

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
class TestDebugPanel:
    def test_panel_exposes_initial_accessibility_metadata(self, qapp):
        from ui_designer.ui.debug_panel import DebugPanel

        panel = DebugPanel()

        assert panel.accessibleName() == "Debug output: 0 lines. Last message: No output yet."
        assert panel.toolTip() == panel.accessibleName()
        assert panel.statusTip() == panel.toolTip()
        assert panel._clear_btn.toolTip() == "Debug output is already clear."
        assert panel._clear_btn.statusTip() == panel._clear_btn.toolTip()
        assert panel._clear_btn.accessibleName() == "Clear debug output unavailable"
        assert panel._title_label.toolTip() == "Debug output: 0 lines. Last message: No output yet."
        assert panel._title_label.statusTip() == panel._title_label.toolTip()
        assert panel._title_label.accessibleName() == "Debug output title: 0 lines"
        assert panel._output.toolTip() == "Debug output: 0 lines. Last message: No output yet."
        assert panel._output.statusTip() == panel._output.toolTip()
        assert panel._output.accessibleName() == "Debug output log: 0 lines. Last message: No output yet."
        panel.deleteLater()

    def test_append_and_clear_refresh_debug_output_summary(self, qapp):
        from ui_designer.ui.debug_panel import DebugPanel

        panel = DebugPanel()

        panel.append_text("Build started", "action")
        assert panel.accessibleName() == "Debug output: 1 line. Last message: Build started"
        assert panel.toolTip() == panel.accessibleName()
        assert panel._clear_btn.toolTip() == "Clear 1 line of debug output."
        assert panel._clear_btn.accessibleName() == "Clear debug output: 1 line"
        assert panel._output.toolTip() == "Debug output: 1 line. Last message: Build started"
        assert panel._output.accessibleName() == "Debug output log: 1 line. Last message: Build started"

        panel.append_text("", "info")
        assert panel.accessibleName() == "Debug output: 2 lines. Last message: blank line"
        assert panel._clear_btn.toolTip() == "Clear 2 lines of debug output."

        panel.clear()
        assert panel.accessibleName() == "Debug output: 0 lines. Last message: No output yet."
        assert panel._clear_btn.toolTip() == "Debug output is already clear."
        panel.deleteLater()
