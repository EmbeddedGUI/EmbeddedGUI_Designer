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

        panel.set_view(ProjectWorkspacePanel.VIEW_THUMBNAILS)

        assert panel.current_view() == ProjectWorkspacePanel.VIEW_THUMBNAILS
        assert panel._stack.currentWidget() is thumb_view
        assert panel._view_chip.text() == "Thumbnails"
        assert emitted[-1] == ProjectWorkspacePanel.VIEW_THUMBNAILS

        panel.set_view("unknown")

        assert panel.current_view() == ProjectWorkspacePanel.VIEW_LIST
        assert panel._stack.currentWidget() is list_view
        assert panel._view_chip.text() == "List View"
        assert emitted[-1] == ProjectWorkspacePanel.VIEW_LIST
        panel.deleteLater()

    def test_workspace_snapshot_chips_show_page_active_and_dirty_state(self, qapp):
        from ui_designer.ui.project_workspace import ProjectWorkspacePanel

        panel = ProjectWorkspacePanel(QWidget(), QWidget())

        panel.set_workspace_snapshot(page_count=3, active_page="main_page", dirty_pages=2)
        assert panel._page_count_chip.text() == "3 pages"
        assert panel._active_page_chip.text() == "Active main_page"
        assert panel._dirty_pages_chip.text() == "2 dirty pages"

        panel.set_workspace_snapshot(page_count=1, active_page="main_page", dirty_pages=1)
        assert panel._page_count_chip.text() == "1 page"
        assert panel._dirty_pages_chip.text() == "1 dirty page"

        panel.set_workspace_snapshot(page_count=0, active_page="", dirty_pages=0)
        assert panel._page_count_chip.text() == "0 pages"
        assert panel._active_page_chip.text() == "No active page"
        assert panel._dirty_pages_chip.text() == "No dirty pages"
        panel.deleteLater()
