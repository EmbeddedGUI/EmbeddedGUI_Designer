"""Qt UI tests for the project workspace panel."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtWidgets import QApplication, QWidget

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
class TestProjectWorkspacePanel:
    def test_set_view_switches_stack_and_updates_view_chip(self, qapp):
        from ui_designer.ui.project_workspace import ProjectWorkspacePanel

        list_view = QWidget()
        thumb_view = QWidget()
        panel = ProjectWorkspacePanel(list_view, thumb_view)
        emitted = []
        panel.view_changed.connect(emitted.append)

        header_layout = panel._header.layout()
        header_margins = header_layout.contentsMargins()
        metrics_margins = panel._metrics_frame.layout().contentsMargins()

        assert panel.layout().spacing() == 4
        assert (header_margins.left(), header_margins.top(), header_margins.right(), header_margins.bottom()) == (4, 4, 4, 4)
        assert header_layout.spacing() == 2
        assert (metrics_margins.left(), metrics_margins.top(), metrics_margins.right(), metrics_margins.bottom()) == (0, 0, 0, 0)
        assert panel._metrics_frame.layout().spacing() == 2
        assert panel._view_toggle_row.spacing() == 2
        assert panel._view_chip.isHidden() is True
        assert panel._view_chip.text() == "List view"
        assert panel._view_chip.accessibleName() == "Workspace view: List view."
        assert panel._header_eyebrow.accessibleName() == "Project navigation workspace surface."
        assert panel._header_eyebrow.isHidden() is True
        assert panel._page_count_chip.text() == "0 pages"
        assert panel._page_count_chip.accessibleName() == "Page count: 0 pages."
        assert panel._dirty_chip.text() == "Clean"
        assert panel._dirty_chip.accessibleName() == "Dirty state: No dirty pages."
        assert panel._metrics_frame.accessibleName() == "Project workspace metrics: 0 pages. No dirty pages."
        assert panel._metrics_frame.isHidden() is True
        assert panel._summary_label.text() == "0 pages. Active: none. Clean."
        assert panel._summary_label.accessibleName() == "Pages summary: 0 pages. Active: none. Clean."
        assert panel._summary_label.isHidden() is True
        assert panel._meta_label.text() == "Startup: none"
        assert panel._meta_label.accessibleName() == "Pages startup summary: Startup: none"
        assert panel._meta_label.isHidden() is True
        assert panel._list_btn.toolTip() == "Currently showing the page list for structure-first editing."
        assert panel._list_btn.statusTip() == panel._list_btn.toolTip()
        assert panel._list_btn.accessibleName() == "Workspace view button: List. Structure first. Current view."
        assert panel._thumb_btn.toolTip() == "Switch to page thumbnails for a visual scan."
        assert panel._thumb_btn.statusTip() == panel._thumb_btn.toolTip()
        assert panel._thumb_btn.accessibleName() == "Workspace view button: Thumbnails. Visual scan. Available."
        assert panel._stack.accessibleName() == "Project workspace view stack: List view visible."
        assert panel._stack.toolTip() == panel._stack.accessibleName()
        assert panel._header.accessibleName() == f"Project workspace header. {panel.accessibleName()}"
        assert panel._header.statusTip() == panel._header.toolTip()
        assert panel._title_label.toolTip() == panel.accessibleName()
        assert panel._title_label.accessibleName() == "Project Workspace. List view."
        assert panel._subtitle_label.accessibleName() == (
            "Page navigation, startup flow, and visual scan."
        )
        assert panel._subtitle_label.isHidden() is True
        assert panel.accessibleName() == (
            "Project workspace: List view. Pages: 0 pages. Active page: none. Startup page: none. Dirty state: No dirty pages."
        )

        panel.set_view(ProjectWorkspacePanel.VIEW_THUMBNAILS)

        assert panel.current_view() == ProjectWorkspacePanel.VIEW_THUMBNAILS
        assert panel._stack.currentWidget() is thumb_view
        assert panel._view_chip.isHidden() is True
        assert panel._view_chip.text() == "Thumbnails"
        assert panel._view_chip.accessibleName() == "Workspace view: Thumbnails."
        assert panel._view_chip.statusTip() == panel._view_chip.toolTip()
        assert panel._list_btn.toolTip() == "Switch to the page list for structure-first editing."
        assert panel._list_btn.accessibleName() == "Workspace view button: List. Structure first. Available."
        assert panel._thumb_btn.toolTip() == "Currently showing page thumbnails for a visual scan."
        assert panel._thumb_btn.accessibleName() == "Workspace view button: Thumbnails. Visual scan. Current view."
        assert panel._stack.accessibleName() == "Project workspace view stack: Thumbnails visible."
        assert panel._header.accessibleName() == f"Project workspace header. {panel.accessibleName()}"
        assert panel._title_label.accessibleName() == "Project Workspace. Thumbnails."
        assert panel.accessibleName() == (
            "Project workspace: Thumbnails. Pages: 0 pages. Active page: none. Startup page: none. Dirty state: No dirty pages."
        )
        assert panel._list_btn.text() == "List"
        assert emitted[-1] == ProjectWorkspacePanel.VIEW_THUMBNAILS
        emitted_count = len(emitted)

        panel.set_view(ProjectWorkspacePanel.VIEW_THUMBNAILS)

        assert len(emitted) == emitted_count

        panel.set_view("unknown")

        assert panel.current_view() == ProjectWorkspacePanel.VIEW_LIST
        assert panel._stack.currentWidget() is list_view
        assert panel._view_chip.isHidden() is True
        assert panel._view_chip.text() == "List view"
        assert panel._view_chip.accessibleName() == "Workspace view: List view."
        assert panel._list_btn.toolTip() == "Currently showing the page list for structure-first editing."
        assert panel._thumb_btn.toolTip() == "Switch to page thumbnails for a visual scan."
        assert panel._stack.accessibleName() == "Project workspace view stack: List view visible."
        assert panel.accessibleName() == (
            "Project workspace: List view. Pages: 0 pages. Active page: none. Startup page: none. Dirty state: No dirty pages."
        )
        assert emitted[-1] == ProjectWorkspacePanel.VIEW_LIST
        emitted_count = len(emitted)

        panel.set_view(ProjectWorkspacePanel.VIEW_LIST)

        assert len(emitted) == emitted_count
        panel.deleteLater()

    def test_workspace_snapshot_chips_show_page_active_and_dirty_state(self, qapp):
        from ui_designer.ui.project_workspace import ProjectWorkspacePanel

        panel = ProjectWorkspacePanel(QWidget(), QWidget())

        panel.set_workspace_snapshot(page_count=3, active_page="main_page", startup_page="detail_page", dirty_pages=2)
        assert panel._summary_label.text() == "3 pages. Active: main_page. 2 dirty pages."
        assert panel._summary_label.accessibleName() == "Pages summary: 3 pages. Active: main_page. 2 dirty pages."
        assert panel._meta_label.text() == "Startup: detail_page"
        assert panel._meta_label.accessibleName() == "Pages startup summary: Startup: detail_page"
        assert panel._page_count_chip.text() == "3 pages"
        assert panel._dirty_chip.text() == "2 dirty pages"
        assert panel._metrics_frame.accessibleName() == "Project workspace metrics: 3 pages. 2 dirty pages."
        assert panel._header.accessibleName() == f"Project workspace header. {panel.accessibleName()}"
        assert panel._title_label.accessibleName() == "Project Workspace. List view."
        assert panel.accessibleName() == (
            "Project workspace: List view. Pages: 3 pages. Active page: main_page. Startup page: detail_page. Dirty state: 2 dirty pages."
        )

        panel.set_workspace_snapshot(page_count=1, active_page="main_page", dirty_pages=1)
        assert panel._summary_label.text() == "1 page. Active: main_page. 1 dirty page."
        assert panel._meta_label.text() == "Startup: none"

        panel.set_workspace_snapshot(page_count=0, active_page="", dirty_pages=0)
        assert panel._summary_label.text() == "0 pages. Active: none. Clean."
        assert panel._summary_label.accessibleName() == "Pages summary: 0 pages. Active: none. Clean."
        assert panel._meta_label.text() == "Startup: none"
        assert panel._meta_label.accessibleName() == "Pages startup summary: Startup: none"
        assert panel._page_count_chip.text() == "0 pages"
        assert panel._dirty_chip.text() == "Clean"
        assert panel.accessibleName() == (
            "Project workspace: List view. Pages: 0 pages. Active page: none. Startup page: none. Dirty state: No dirty pages."
        )
        panel.deleteLater()

    def test_workspace_snapshot_skips_no_op_metadata_refreshes(self, qapp, monkeypatch):
        from ui_designer.ui.project_workspace import ProjectWorkspacePanel

        panel = ProjectWorkspacePanel(QWidget(), QWidget())
        metadata_updates = 0
        original_update_panel_metadata = panel._update_panel_metadata

        def counted_update_panel_metadata():
            nonlocal metadata_updates
            metadata_updates += 1
            return original_update_panel_metadata()

        monkeypatch.setattr(panel, "_update_panel_metadata", counted_update_panel_metadata)

        panel.set_workspace_snapshot(page_count=2, active_page="main_page", startup_page="main_page", dirty_pages=1)
        assert metadata_updates == 1

        panel.set_workspace_snapshot(page_count=2, active_page="main_page", startup_page="main_page", dirty_pages=1)
        assert metadata_updates == 1

        panel.set_workspace_snapshot(page_count=2, active_page="main_page", startup_page="main_page", dirty_pages=2)
        assert metadata_updates == 2
        panel.deleteLater()

    def test_panel_metadata_helper_skips_no_op_tooltip_rewrites(self, qapp, monkeypatch):
        from ui_designer.ui.project_workspace import ProjectWorkspacePanel

        panel = ProjectWorkspacePanel(QWidget(), QWidget())
        panel._header.setProperty("_workspace_metadata_tooltip_snapshot", None)

        tooltip_calls = 0
        original_set_tooltip = panel._header.setToolTip

        def counted_set_tooltip(text):
            nonlocal tooltip_calls
            tooltip_calls += 1
            return original_set_tooltip(text)

        monkeypatch.setattr(panel._header, "setToolTip", counted_set_tooltip)

        panel._update_panel_metadata()
        assert tooltip_calls == 1

        tooltip_calls = 0
        panel._update_panel_metadata()
        assert tooltip_calls == 0

        panel.set_workspace_snapshot(page_count=2, active_page="main_page", startup_page="main_page", dirty_pages=1)
        assert tooltip_calls == 1
        assert panel._header.toolTip() == f"Project workspace header. {panel.accessibleName()}"
        assert panel._header.statusTip() == panel._header.toolTip()
        panel.deleteLater()

    def test_summary_label_metadata_skips_no_op_rewrites(self, qapp, monkeypatch):
        from ui_designer.ui.project_workspace import ProjectWorkspacePanel

        panel = ProjectWorkspacePanel(QWidget(), QWidget())
        panel._summary_label.setProperty("_workspace_metadata_tooltip_snapshot", None)

        tooltip_calls = 0
        original_set_tooltip = panel._summary_label.setToolTip

        def counted_set_tooltip(text):
            nonlocal tooltip_calls
            tooltip_calls += 1
            return original_set_tooltip(text)

        monkeypatch.setattr(panel._summary_label, "setToolTip", counted_set_tooltip)

        panel.set_workspace_snapshot(page_count=2, dirty_pages=1)
        assert tooltip_calls == 1

        tooltip_calls = 0
        panel.set_workspace_snapshot(page_count=2, dirty_pages=2)
        assert tooltip_calls == 1
        assert panel._summary_label.text() == "2 pages. Active: none. 2 dirty pages."

        tooltip_calls = 0
        panel.set_workspace_snapshot(page_count=2, dirty_pages=2)
        assert tooltip_calls == 0
        panel.deleteLater()
