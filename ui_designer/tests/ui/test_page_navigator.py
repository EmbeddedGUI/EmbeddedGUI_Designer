"""Qt UI tests for the page navigator widget."""

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
class TestPageNavigator:
    def test_page_thumbnail_accessibility_tracks_selected_and_dirty_state(self, qapp):
        from ui_designer.ui.widgets.page_navigator import PageThumbnail

        thumb = PageThumbnail("main_page")

        assert thumb.toolTip() == "Open page: main_page. Available. No unsaved changes."
        assert thumb.statusTip() == thumb.toolTip()
        assert thumb.accessibleName() == "Page thumbnail: main_page. Available. No unsaved changes."
        assert thumb._thumb_label.toolTip() == thumb.toolTip()
        assert thumb._thumb_label.statusTip() == thumb._thumb_label.toolTip()
        assert thumb._thumb_label.accessibleName() == "Page preview: main_page. Available. No unsaved changes."
        assert thumb._name_label.toolTip() == thumb.toolTip()
        assert thumb._name_label.statusTip() == thumb._name_label.toolTip()
        assert thumb._name_label.accessibleName() == "Page name: main_page. Available. No unsaved changes."

        thumb.set_startup(True)
        assert thumb.toolTip() == "Open page: main_page. Startup page. Available. No unsaved changes."
        assert thumb.accessibleName() == "Page thumbnail: main_page. Startup page. Available. No unsaved changes."

        thumb.set_selected(True)
        assert thumb.accessibleName() == "Page thumbnail: main_page. Startup page. Current page. No unsaved changes."

        thumb.set_dirty(True)
        assert thumb._name_label.text() == "main_page*"
        assert thumb.toolTip() == "Open page: main_page. Startup page. Current page. Unsaved changes."
        assert thumb._name_label.accessibleName() == "Page name: main_page*. Startup page. Current page. Unsaved changes."
        thumb.deleteLater()

    def test_page_navigator_accessibility_summarizes_pages_current_and_dirty_state(self, qapp):
        from ui_designer.ui.widgets.page_navigator import PageNavigator

        navigator = PageNavigator()

        assert navigator.accessibleName() == "Page navigator: 0 pages. Current page: none. Startup page: none. No dirty pages."
        assert navigator.toolTip() == navigator.accessibleName()
        assert navigator.statusTip() == navigator.toolTip()
        assert navigator._scroll_area.accessibleName() == "Page thumbnails view: 0 pages. Current page: none. Startup page: none. No dirty pages."
        assert navigator._container.accessibleName() == "Page thumbnail list: 0 pages. Current page: none. Startup page: none. No dirty pages."
        assert navigator._scroll_area.toolTip() == "Page thumbnails view: 0 pages. Current page: none. Startup page: none. No dirty pages."
        assert navigator._container.toolTip() == "Page thumbnail list: 0 pages. Current page: none. Startup page: none. No dirty pages."

        navigator.set_pages({"main_page": object(), "detail_page": object()})
        assert navigator.accessibleName() == "Page navigator: 2 pages. Current page: none. Startup page: none. No dirty pages."
        assert navigator._title_label.toolTip() == navigator.accessibleName()
        assert navigator._title_label.statusTip() == navigator._title_label.toolTip()
        assert navigator._title_label.accessibleName() == "Pages: 2 pages. Current page: none. Startup page: none."

        navigator.set_startup_page("main_page")
        assert navigator.accessibleName() == "Page navigator: 2 pages. Current page: none. Startup page: main_page. No dirty pages."
        assert navigator._thumbnails["main_page"].accessibleName() == "Page thumbnail: main_page. Startup page. Available. No unsaved changes."

        navigator.set_current_page("detail_page")
        assert navigator.accessibleName() == "Page navigator: 2 pages. Current page: detail_page. Startup page: main_page. No dirty pages."
        assert navigator._thumbnails["detail_page"].accessibleName() == "Page thumbnail: detail_page. Current page. No unsaved changes."
        assert navigator._scroll_area.statusTip() == navigator._scroll_area.toolTip()
        assert navigator._scroll_area.accessibleName() == "Page thumbnails view: 2 pages. Current page: detail_page. Startup page: main_page. No dirty pages."

        navigator.set_dirty_pages({"main_page"})
        assert navigator.accessibleName() == "Page navigator: 2 pages. Current page: detail_page. Startup page: main_page. 1 dirty page."
        assert navigator._thumbnails["main_page"].accessibleName() == "Page thumbnail: main_page. Startup page. Available. Unsaved changes."
        assert navigator._thumbnails["main_page"]._name_label.text() == "main_page*"
        assert navigator._container.toolTip() == "Page thumbnail list: 2 pages. Current page: detail_page. Startup page: main_page. 1 dirty page."
        assert navigator._container.accessibleName() == "Page thumbnail list: 2 pages. Current page: detail_page. Startup page: main_page. 1 dirty page."
        navigator.deleteLater()

    def test_page_thumbnail_context_menu_actions_expose_dynamic_hints(self, qapp):
        from ui_designer.ui.widgets.page_navigator import PageNavigator

        navigator = PageNavigator()
        navigator.set_pages({"main_page": object(), "detail_page": object()})
        navigator.set_current_page("detail_page")
        navigator.set_dirty_pages({"main_page"})

        dirty_menu = navigator._build_context_menu("main_page")
        dirty_actions = {action.text(): action for action in dirty_menu.actions() if action.text()}
        assert dirty_actions["Copy Page"].toolTip() == "Duplicate page: main_page."
        assert dirty_actions["Copy Page"].statusTip() == dirty_actions["Copy Page"].toolTip()
        assert dirty_actions["Delete Page"].toolTip() == "Delete page: main_page. Unsaved changes will be lost."
        assert dirty_actions["Delete Page"].statusTip() == dirty_actions["Delete Page"].toolTip()
        template_menu = dirty_actions["Add Page from Template"].menu()
        assert dirty_actions["Add Page from Template"].toolTip() == (
            "Add a new page from a built-in template after main_page."
        )
        assert template_menu.actions()[0].toolTip() == "Add Blank after main_page."
        assert template_menu.actions()[0].statusTip() == template_menu.actions()[0].toolTip()
        dirty_menu.deleteLater()

        clean_menu = navigator._build_context_menu("detail_page")
        clean_actions = {action.text(): action for action in clean_menu.actions() if action.text()}
        assert clean_actions["Delete Page"].toolTip() == "Delete page: detail_page. This cannot be undone."
        clean_menu.deleteLater()
        navigator.deleteLater()
