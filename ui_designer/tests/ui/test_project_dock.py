"""Qt UI tests for the project explorer dock."""

import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtCore import Qt
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
        assert dock._settings_group.toolTip() == "Project settings: 0 pages. Current mode: easy_page."
        assert dock._settings_group.statusTip() == dock._settings_group.toolTip()
        assert dock._settings_group.accessibleName() == "Project settings: 0 pages. Current mode: easy_page."
        assert dock._mode_label.toolTip() == "Choose how pages are generated for the current project. Current mode: easy_page."
        assert dock._mode_label.statusTip() == dock._mode_label.toolTip()
        assert dock._mode_label.accessibleName() == (
            "Page mode label. Current mode: easy_page. "
            "Choose how pages are generated for the current project. Current mode: easy_page."
        )
        assert dock._page_tree.accessibleName() == "Project pages: 0 pages. Current page: none. No dirty pages."
        assert dock._mode_combo.toolTip() == "Choose how pages are generated for the current project. Current mode: easy_page."
        assert dock._mode_combo.statusTip() == dock._mode_combo.toolTip()
        assert dock._mode_combo.accessibleName() == (
            "Project page mode: easy_page. "
            "Choose how pages are generated for the current project. Current mode: easy_page."
        )
        assert dock._add_page_button.toolTip() == "Create the first page for a new project. Current mode: easy_page."
        assert dock._add_page_button.statusTip() == dock._add_page_button.toolTip()
        assert dock._add_page_button.accessibleName() == (
            "New page action: easy_page mode. "
            "Create the first page for a new project. Current mode: easy_page."
        )

        dock.set_project(_build_project())
        dock.set_current_page("main_page")
        dock.set_dirty_pages({"detail_page"})

        assert dock.accessibleName() == "Project Explorer: 2 pages. Current page: main_page. 1 dirty page."
        assert dock._settings_group.toolTip() == "Project settings: 2 pages. Current mode: easy_page."
        assert dock._settings_group.accessibleName() == "Project settings: 2 pages. Current mode: easy_page."
        assert dock._mode_label.accessibleName() == (
            "Page mode label. Current mode: easy_page. "
            "Choose how pages are generated for the current project. Current mode: easy_page."
        )
        assert dock._pages_label.toolTip() == dock.accessibleName()
        assert dock._pages_label.accessibleName() == "Pages: 2 pages. Current page: main_page."
        assert dock._page_tree.toolTip() == dock.accessibleName()
        assert dock._page_tree.accessibleName() == "Project pages: 2 pages. Current page: main_page. 1 dirty page."
        assert dock._add_page_button.toolTip() == "Create a new page in the current project. Current mode: easy_page."
        assert dock._add_page_button.accessibleName() == (
            "New page action: easy_page mode. "
            "Create a new page in the current project. Current mode: easy_page."
        )

        dock._mode_combo.setCurrentText("activity")

        assert dock._mode_combo.toolTip() == "Choose how pages are generated for the current project. Current mode: activity."
        assert dock._mode_combo.accessibleName() == (
            "Project page mode: activity. "
            "Choose how pages are generated for the current project. Current mode: activity."
        )
        assert dock._settings_group.toolTip() == "Project settings: 2 pages. Current mode: activity."
        assert dock._settings_group.accessibleName() == "Project settings: 2 pages. Current mode: activity."
        assert dock._mode_label.toolTip() == "Choose how pages are generated for the current project. Current mode: activity."
        assert dock._mode_label.accessibleName() == (
            "Page mode label. Current mode: activity. "
            "Choose how pages are generated for the current project. Current mode: activity."
        )
        assert dock._add_page_button.toolTip() == "Create a new page in the current project. Current mode: activity."
        assert dock._add_page_button.accessibleName() == (
            "New page action: activity mode. "
            "Create a new page in the current project. Current mode: activity."
        )

        first = dock._page_tree.topLevelItem(0)
        second = dock._page_tree.topLevelItem(1)
        assert first.toolTip(0) == "Page: main_page. Startup page. Current page. No unsaved changes."
        assert second.toolTip(0) == "Page: detail_page. Unsaved changes."
        assert first.data(0, Qt.AccessibleTextRole) == first.toolTip(0)
        assert second.data(0, Qt.AccessibleTextRole) == second.toolTip(0)
        dock.deleteLater()

    def test_page_context_menu_actions_expose_dynamic_hints(self, qapp):
        from ui_designer.ui.project_dock import ProjectExplorerDock

        dock = ProjectExplorerDock()

        empty_menu = dock._build_page_context_menu(None)
        empty_actions = {action.text(): action for action in empty_menu.actions()}
        assert empty_actions["New Page..."].toolTip() == "Create the first page for a new project. Current mode: easy_page."
        assert empty_actions["New Page..."].statusTip() == empty_actions["New Page..."].toolTip()
        empty_menu.deleteLater()

        dock.set_project(_build_project())
        dock.set_current_page("main_page")
        dock.set_dirty_pages({"detail_page"})

        current_item = dock._page_tree.topLevelItem(0)
        current_menu = dock._build_page_context_menu(current_item)
        current_actions = {action.text(): action for action in current_menu.actions() if action.text()}
        assert current_actions["Rename"].toolTip() == "Rename page: main_page."
        assert current_actions["Duplicate"].toolTip() == "Duplicate page: main_page."
        assert current_actions["Set as Startup Page"].toolTip() == "Current startup page: main_page."
        assert current_actions["Delete"].toolTip() == "Delete page: main_page. This cannot be undone."
        assert current_actions["Delete"].statusTip() == current_actions["Delete"].toolTip()
        current_menu.deleteLater()

        dirty_item = dock._page_tree.topLevelItem(1)
        dirty_menu = dock._build_page_context_menu(dirty_item)
        dirty_actions = {action.text(): action for action in dirty_menu.actions() if action.text()}
        assert dirty_actions["Rename"].toolTip() == "Rename page: detail_page."
        assert dirty_actions["Duplicate"].toolTip() == "Duplicate page: detail_page."
        assert dirty_actions["Set as Startup Page"].toolTip() == "Set detail_page as the startup page."
        assert dirty_actions["Delete"].toolTip() == "Delete page: detail_page. Unsaved changes will be lost."
        assert dirty_actions["Delete"].statusTip() == dirty_actions["Delete"].toolTip()
        dirty_menu.deleteLater()
        dock.deleteLater()
