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

        assert panel._dirty_pages_chip.isHidden() is True
        assert panel._list_btn.toolTip() == "Currently showing the page list for structure-first editing."
        assert panel._list_btn.statusTip() == panel._list_btn.toolTip()
        assert panel._list_btn.accessibleName() == "Workspace view button: List. Structure first. Current view."
        assert panel._thumb_btn.toolTip() == "Switch to page thumbnails for a visual scan."
        assert panel._thumb_btn.statusTip() == panel._thumb_btn.toolTip()
        assert panel._thumb_btn.accessibleName() == "Workspace view button: Thumbnails. Visual scan. Available."
        assert panel._stack.accessibleName() == "Project workspace view stack: List view visible."
        assert panel._stack.toolTip() == panel._stack.accessibleName()
        assert panel._header.accessibleName() == panel.accessibleName()
        assert panel._header.statusTip() == panel._header.toolTip()
        assert panel._title_label.toolTip() == panel.accessibleName()
        assert panel._title_label.accessibleName() == "Project Workspace. List view."
        assert panel._subtitle_label.accessibleName() == (
            "Switch between fast list management and visual page thumbnails."
        )
        assert panel.accessibleName() == (
            "Project workspace: List view. Pages: 0 pages. Active page: none. Startup page: none. Dirty state: No dirty pages."
        )

        panel.set_view(ProjectWorkspacePanel.VIEW_THUMBNAILS)

        assert panel.current_view() == ProjectWorkspacePanel.VIEW_THUMBNAILS
        assert panel._stack.currentWidget() is thumb_view
        assert panel._view_chip.text() == "Thumbnails"
        assert panel._view_chip.accessibleName() == "Workspace view: Thumbnails."
        assert panel._view_chip.statusTip() == panel._view_chip.toolTip()
        assert panel._list_btn.toolTip() == "Switch to the page list for structure-first editing."
        assert panel._list_btn.accessibleName() == "Workspace view button: List. Structure first. Available."
        assert panel._thumb_btn.toolTip() == "Currently showing page thumbnails for a visual scan."
        assert panel._thumb_btn.accessibleName() == "Workspace view button: Thumbnails. Visual scan. Current view."
        assert panel._stack.accessibleName() == "Project workspace view stack: Thumbnails visible."
        assert panel._header.accessibleName() == panel.accessibleName()
        assert panel._title_label.accessibleName() == "Project Workspace. Thumbnails."
        assert panel.accessibleName() == (
            "Project workspace: Thumbnails. Pages: 0 pages. Active page: none. Startup page: none. Dirty state: No dirty pages."
        )
        assert panel._list_btn.text() == "List\nStructure first"
        assert emitted[-1] == ProjectWorkspacePanel.VIEW_THUMBNAILS
        emitted_count = len(emitted)

        panel.set_view(ProjectWorkspacePanel.VIEW_THUMBNAILS)

        assert len(emitted) == emitted_count

        panel.set_view("unknown")

        assert panel.current_view() == ProjectWorkspacePanel.VIEW_LIST
        assert panel._stack.currentWidget() is list_view
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
        assert panel._page_count_chip.text() == "3 pages"
        assert panel._page_count_chip.accessibleName() == "Workspace pages: 3 pages."
        assert panel._page_count_chip.statusTip() == panel._page_count_chip.toolTip()
        assert panel._active_page_chip.text() == "Active: main_page"
        assert panel._active_page_chip.accessibleName() == "Workspace active page: main_page."
        assert panel._dirty_pages_chip.isHidden() is False
        assert panel._dirty_pages_chip.text() == "2 dirty pages"
        assert panel._dirty_pages_chip.accessibleName() == "Workspace dirty pages: 2 dirty pages."
        assert panel._header.accessibleName() == panel.accessibleName()
        assert panel._title_label.accessibleName() == "Project Workspace. List view."
        assert panel.accessibleName() == (
            "Project workspace: List view. Pages: 3 pages. Active page: main_page. Startup page: detail_page. Dirty state: 2 dirty pages."
        )

        panel.set_workspace_snapshot(page_count=1, active_page="main_page", dirty_pages=1)
        assert panel._page_count_chip.text() == "1 page"
        assert panel._dirty_pages_chip.text() == "1 dirty page"

        panel.set_workspace_snapshot(page_count=0, active_page="", dirty_pages=0)
        assert panel._page_count_chip.text() == "0 pages"
        assert panel._page_count_chip.accessibleName() == "Workspace pages: 0 pages."
        assert panel._active_page_chip.text() == "No active page"
        assert panel._active_page_chip.accessibleName() == "Workspace active page: none."
        assert panel._dirty_pages_chip.isHidden() is True
        assert panel._dirty_pages_chip.text() == "No dirty pages"
        assert panel._dirty_pages_chip.accessibleName() == "Workspace dirty pages: no dirty pages."
        assert panel.accessibleName() == (
            "Project workspace: List view. Pages: 0 pages. Active page: none. Startup page: none. Dirty state: No dirty pages."
        )
        panel.deleteLater()
