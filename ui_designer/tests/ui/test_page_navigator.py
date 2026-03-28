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
        assert thumb._thumb_label.accessibleName() == "Page preview: main_page. Available. No unsaved changes."
        assert thumb._name_label.accessibleName() == "Page name: main_page. Available. No unsaved changes."

        thumb.set_selected(True)
        assert thumb.accessibleName() == "Page thumbnail: main_page. Current page. No unsaved changes."

        thumb.set_dirty(True)
        assert thumb._name_label.text() == "main_page*"
        assert thumb.toolTip() == "Open page: main_page. Current page. Unsaved changes."
        assert thumb._name_label.accessibleName() == "Page name: main_page*. Current page. Unsaved changes."
        thumb.deleteLater()

    def test_page_navigator_accessibility_summarizes_pages_current_and_dirty_state(self, qapp):
        from ui_designer.ui.widgets.page_navigator import PageNavigator

        navigator = PageNavigator()

        assert navigator.accessibleName() == "Page navigator: 0 pages. Current page: none. No dirty pages."
        assert navigator.toolTip() == navigator.accessibleName()
        assert navigator._scroll_area.accessibleName() == "Page thumbnails"
        assert navigator._container.accessibleName() == "Page thumbnail list"
        assert navigator._scroll_area.toolTip() == "Page thumbnails view: 0 pages. Current page: none. No dirty pages."
        assert navigator._container.toolTip() == "Page thumbnail list: 0 pages. Current page: none. No dirty pages."

        navigator.set_pages({"main_page": object(), "detail_page": object()})
        assert navigator.accessibleName() == "Page navigator: 2 pages. Current page: none. No dirty pages."
        assert navigator._title_label.toolTip() == navigator.accessibleName()
        assert navigator._title_label.accessibleName() == "Pages: 2 pages. Current page: none."

        navigator.set_current_page("detail_page")
        assert navigator.accessibleName() == "Page navigator: 2 pages. Current page: detail_page. No dirty pages."
        assert navigator._thumbnails["detail_page"].accessibleName() == "Page thumbnail: detail_page. Current page. No unsaved changes."
        assert navigator._scroll_area.statusTip() == navigator._scroll_area.toolTip()

        navigator.set_dirty_pages({"main_page"})
        assert navigator.accessibleName() == "Page navigator: 2 pages. Current page: detail_page. 1 dirty page."
        assert navigator._thumbnails["main_page"].accessibleName() == "Page thumbnail: main_page. Available. Unsaved changes."
        assert navigator._thumbnails["main_page"]._name_label.text() == "main_page*"
        assert navigator._container.toolTip() == "Page thumbnail list: 2 pages. Current page: detail_page. 1 dirty page."
        navigator.deleteLater()
