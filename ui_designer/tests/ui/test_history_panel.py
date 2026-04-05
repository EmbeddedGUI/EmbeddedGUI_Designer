"""Qt UI tests for the history panel."""

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
class TestHistoryPanel:
    def test_clear_state_exposes_summary_metadata(self, qapp):
        from ui_designer.ui.history_panel import HistoryPanel

        panel = HistoryPanel()

        assert panel.accessibleName() == (
            "History panel: Page -. 0 entries. Current entry none. Undo no. Redo no. Dirty no. Source Saved state."
        )
        assert panel.toolTip() == panel.accessibleName()
        assert panel.statusTip() == panel.toolTip()
        assert panel._header_eyebrow.accessibleName() == "Undo timeline workspace surface."
        assert panel._header_eyebrow.isHidden() is True
        assert panel._header_frame.accessibleName() == (
            "History header. History panel: Page -. 0 entries. Current entry none. Undo no. Redo no. Dirty no. Source Saved state."
        )
        assert panel._page_value.toolTip() == "History page: -"
        assert panel._page_value.statusTip() == panel._page_value.toolTip()
        assert panel._stack_value.accessibleName() == "History summary: 0 entries. Undo no. Redo no."
        assert panel._dirty_value.accessibleName() == "History dirty state: No"
        assert panel._source_value.accessibleName() == "History source: Saved state"
        assert panel._source_value.isHidden() is True
        assert panel._history_list.toolTip() == "History entries: 0 items for page -. Current entry: none."
        assert panel._history_list.statusTip() == panel._history_list.toolTip()
        assert panel._history_list.accessibleName() == "History entries for -: 0 items. Current entry: none"
        assert panel._history_list.count() == 0
        panel.deleteLater()

    def test_history_entries_expose_tooltips_and_accessibility(self, qapp):
        from PyQt5.QtCore import Qt
        from ui_designer.ui.history_panel import HistoryPanel

        panel = HistoryPanel()
        entries = [
            {"index": 0, "label": "Saved state", "is_saved": True},
            {"index": 1, "label": "xml edit", "is_current": True},
        ]

        panel.set_history(
            "main_page",
            entries,
            dirty=True,
            dirty_source="xml edit",
            can_undo=True,
            can_redo=False,
        )

        assert panel.accessibleName() == (
            "History panel: Page main_page. 2 entries. Current entry xml edit. Undo yes. Redo no. Dirty yes. Source xml edit."
        )
        assert panel.toolTip() == panel.accessibleName()
        assert panel._header_frame.accessibleName() == (
            "History header. History panel: Page main_page. 2 entries. Current entry xml edit. Undo yes. Redo no. Dirty yes. Source xml edit."
        )
        assert panel._stack_value.toolTip() == "History entries: 2. Undo: Yes. Redo: No."
        assert panel._history_list.accessibleName() == "History entries for main_page: 2 items. Current entry: xml edit"
        assert panel._history_list.toolTip() == "History entries: 2 items for page main_page. Current entry: xml edit."
        assert panel._history_list.statusTip() == panel._history_list.toolTip()
        assert panel._history_list.item(0).toolTip() == "History entry 2. Current. xml edit"
        assert panel._history_list.item(1).toolTip() == "History entry 1. Saved. Saved state"
        assert panel._history_list.item(0).data(Qt.AccessibleTextRole) == "History entry 2. Current. xml edit"
        assert panel._history_list.item(1).data(Qt.AccessibleTextRole) == "History entry 1. Saved. Saved state"
        panel.deleteLater()

    def test_header_frame_hint_skips_no_op_rewrites(self, qapp, monkeypatch):
        from ui_designer.ui.history_panel import HistoryPanel

        panel = HistoryPanel()
        panel._header_frame.setProperty("_history_panel_hint_snapshot", None)

        hint_calls = 0
        original_set_tooltip = panel._header_frame.setToolTip

        def counted_set_tooltip(text):
            nonlocal hint_calls
            hint_calls += 1
            return original_set_tooltip(text)

        monkeypatch.setattr(panel._header_frame, "setToolTip", counted_set_tooltip)

        panel._update_accessibility_summary(
            page_name="-",
            entry_count=0,
            dirty=False,
            dirty_source="Saved state",
            current_entry="none",
        )
        assert hint_calls == 1

        panel._update_accessibility_summary(
            page_name="-",
            entry_count=0,
            dirty=False,
            dirty_source="Saved state",
            current_entry="none",
        )
        assert hint_calls == 1

        panel.set_history("main_page", [{"index": 0, "label": "xml edit", "is_current": True}], dirty=True, dirty_source="xml edit", can_undo=True)
        assert hint_calls == 2
        panel.deleteLater()

    def test_header_frame_accessible_name_skips_no_op_rewrites(self, qapp, monkeypatch):
        from ui_designer.ui.history_panel import HistoryPanel

        panel = HistoryPanel()
        panel._header_frame.setProperty("_history_panel_accessible_snapshot", None)

        accessible_calls = 0
        original_set_accessible_name = panel._header_frame.setAccessibleName

        def counted_set_accessible_name(text):
            nonlocal accessible_calls
            accessible_calls += 1
            return original_set_accessible_name(text)

        monkeypatch.setattr(panel._header_frame, "setAccessibleName", counted_set_accessible_name)

        panel._update_accessibility_summary(
            page_name="-",
            entry_count=0,
            dirty=False,
            dirty_source="Saved state",
            current_entry="none",
        )
        assert accessible_calls == 1

        panel._update_accessibility_summary(
            page_name="-",
            entry_count=0,
            dirty=False,
            dirty_source="Saved state",
            current_entry="none",
        )
        assert accessible_calls == 1

        panel.set_history("main_page", [{"index": 0, "label": "xml edit", "is_current": True}], dirty=True, dirty_source="xml edit", can_undo=True)
        assert accessible_calls == 2
        panel.deleteLater()
