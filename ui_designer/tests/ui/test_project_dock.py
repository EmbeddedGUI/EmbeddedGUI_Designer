"""Qt UI tests for the project explorer dock."""

import os
from types import SimpleNamespace

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


def _build_project():
    pages = [SimpleNamespace(name="main_page"), SimpleNamespace(name="detail_page")]

    def get_page_by_name(name):
        for page in pages:
            if page.name == name:
                return page
        return None

    return SimpleNamespace(
        pages=pages,
        page_mode="easy_page",
        startup_page="main_page",
        get_page_by_name=get_page_by_name,
    )


@_skip_no_qt
class TestProjectExplorerDock:
    def test_accessibility_summary_tracks_project_current_and_dirty_pages(self, qapp):
        from ui_designer.ui.project_dock import ProjectExplorerDock

        dock = ProjectExplorerDock()

        assert dock.accessibleName() == "Project Explorer: 0 pages. Current page: none. No dirty pages."
        assert dock._page_tree.accessibleName() == "Project pages: 0 pages. Current page: none. No dirty pages."
        assert dock._mode_combo.toolTip() == "Choose how pages are generated for the current project. Current mode: easy_page."
        assert dock._mode_combo.statusTip() == dock._mode_combo.toolTip()
        assert dock._mode_combo.accessibleName() == "Project page mode: easy_page"
        assert dock._add_page_button.toolTip() == "Create the first page for a new project. Current mode: easy_page."
        assert dock._add_page_button.statusTip() == dock._add_page_button.toolTip()
        assert dock._add_page_button.accessibleName() == "New page action: easy_page mode"

        dock.set_project(_build_project())
        dock.set_current_page("main_page")
        dock.set_dirty_pages({"detail_page"})

        assert dock.accessibleName() == "Project Explorer: 2 pages. Current page: main_page. 1 dirty page."
        assert dock._pages_label.toolTip() == dock.accessibleName()
        assert dock._pages_label.accessibleName() == "Pages: 2 pages. Current page: main_page."
        assert dock._page_tree.toolTip() == dock.accessibleName()
        assert dock._page_tree.accessibleName() == "Project pages: 2 pages. Current page: main_page. 1 dirty page."
        assert dock._add_page_button.toolTip() == "Create a new page in the current project. Current mode: easy_page."

        dock._mode_combo.setCurrentText("activity")

        assert dock._mode_combo.toolTip() == "Choose how pages are generated for the current project. Current mode: activity."
        assert dock._mode_combo.accessibleName() == "Project page mode: activity"
        assert dock._add_page_button.toolTip() == "Create a new page in the current project. Current mode: activity."
        assert dock._add_page_button.accessibleName() == "New page action: activity mode"

        first = dock._page_tree.topLevelItem(0)
        second = dock._page_tree.topLevelItem(1)
        assert first.toolTip(0) == "Page: main_page. Startup page. Current page. No unsaved changes."
        assert second.toolTip(0) == "Page: detail_page. Unsaved changes."
        dock.deleteLater()
