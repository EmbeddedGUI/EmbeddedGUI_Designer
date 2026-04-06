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
    def test_panel_uses_designer_font_preference_for_output(self, qapp):
        from ui_designer.ui.debug_panel import DebugPanel

        qapp.setProperty("designer_font_size_pt", 12)
        panel = DebugPanel()

        try:
            assert panel.get_output_font().pointSize() == 12
        finally:
            panel.deleteLater()
            qapp.setProperty("designer_font_size_pt", 0)

    def test_panel_exposes_initial_accessibility_metadata(self, qapp):
        from ui_designer.ui.debug_panel import DebugPanel

        panel = DebugPanel()
        header_layout = panel._header_frame.layout()
        header_margins = header_layout.contentsMargins()
        title_row = header_layout.itemAt(1).layout()

        assert panel.accessibleName() == "Debug output: 0 lines. Last message: No output yet."
        assert panel.toolTip() == panel.accessibleName()
        assert panel.statusTip() == panel.toolTip()
        assert panel.layout().spacing() == 2
        assert (header_margins.left(), header_margins.top(), header_margins.right(), header_margins.bottom()) == (6, 4, 6, 4)
        assert title_row.spacing() == 2
        assert panel._controls_strip.layout().spacing() == 2
        assert panel._header_eyebrow.accessibleName() == "Runtime console workspace surface."
        assert panel._header_eyebrow.isHidden() is True
        assert panel._header_frame.accessibleName() == "Debug output header. Debug output: 0 lines. Last message: No output yet."
        assert panel._title_label.text() == "Debug"
        assert panel._meta_label.text() == "No output yet. Compile, preview, and bridge logs will appear here."
        assert panel._meta_label.accessibleName() == (
            "Debug output summary: No output yet. Compile, preview, and bridge logs will appear here."
        )
        assert panel._meta_label.isHidden() is True
        assert panel._line_count_chip.text() == "0 lines"
        assert panel._line_count_chip.isHidden() is True
        assert panel._line_count_chip.accessibleName() == "Debug output lines: 0 lines."
        assert panel._stream_state_chip.text() == "Idle"
        assert panel._stream_state_chip.isHidden() is True
        assert panel._stream_state_chip.accessibleName() == "Debug output state: Idle."
        assert panel._controls_strip.accessibleName() == "Debug output actions. 0 lines."
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
        assert panel._meta_label.text() == "Showing 1 line. Last message: Build started."
        assert panel._meta_label.isHidden() is True
        assert panel._line_count_chip.text() == "1 line"
        assert panel._stream_state_chip.text() == "Captured Output"
        assert panel._clear_btn.toolTip() == "Clear 1 line of debug output."
        assert panel._clear_btn.accessibleName() == "Clear debug output: 1 line"
        assert panel._output.toolTip() == "Debug output: 1 line. Last message: Build started"
        assert panel._output.accessibleName() == "Debug output log: 1 line. Last message: Build started"

        panel.append_text("", "info")
        assert panel.accessibleName() == "Debug output: 2 lines. Last message: blank line"
        assert panel._meta_label.text() == "Showing 2 lines. Last message: blank line."
        assert panel._line_count_chip.text() == "2 lines"
        assert panel._clear_btn.toolTip() == "Clear 2 lines of debug output."

        panel.clear()
        assert panel.accessibleName() == "Debug output: 0 lines. Last message: No output yet."
        assert panel._stream_state_chip.text() == "Idle"
        assert panel._clear_btn.toolTip() == "Debug output is already clear."
        panel.deleteLater()

    def test_header_frame_hint_skips_no_op_rewrites(self, qapp, monkeypatch):
        from ui_designer.ui.debug_panel import DebugPanel

        panel = DebugPanel()
        panel._header_frame.setProperty("_debug_panel_hint_snapshot", None)

        hint_calls = 0
        original_set_tooltip = panel._header_frame.setToolTip

        def counted_set_tooltip(text):
            nonlocal hint_calls
            hint_calls += 1
            return original_set_tooltip(text)

        monkeypatch.setattr(panel._header_frame, "setToolTip", counted_set_tooltip)

        panel._update_accessibility_summary("No output yet.")
        assert hint_calls == 1

        panel._update_accessibility_summary("No output yet.")
        assert hint_calls == 1

        panel.append_text("Build started", "action")
        assert hint_calls == 2
        panel.deleteLater()

    def test_header_frame_accessible_name_skips_no_op_rewrites(self, qapp, monkeypatch):
        from ui_designer.ui.debug_panel import DebugPanel

        panel = DebugPanel()
        panel._header_frame.setProperty("_debug_panel_accessible_snapshot", None)

        accessible_calls = 0
        original_set_accessible_name = panel._header_frame.setAccessibleName

        def counted_set_accessible_name(text):
            nonlocal accessible_calls
            accessible_calls += 1
            return original_set_accessible_name(text)

        monkeypatch.setattr(panel._header_frame, "setAccessibleName", counted_set_accessible_name)

        panel._update_accessibility_summary("No output yet.")
        assert accessible_calls == 1

        panel._update_accessibility_summary("No output yet.")
        assert accessible_calls == 1

        panel.append_text("Build started", "action")
        assert accessible_calls == 2
        panel.deleteLater()
