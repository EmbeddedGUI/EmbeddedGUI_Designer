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
        assert thumb._meta_label.isHidden() is True
        assert thumb._meta_label.toolTip() == "Available. No unsaved changes. Left click to open."
        assert thumb._meta_label.statusTip() == thumb._meta_label.toolTip()
        assert thumb._meta_label.accessibleName() == "Available. No unsaved changes. Left click to open."
        assert thumb._state_chip.isHidden() is True
        assert thumb._state_chip.accessibleName() == "Page state: Available."
        assert thumb._dirty_chip.isHidden() is True
        assert thumb._dirty_chip.accessibleName() == "Page save state: Saved."

        thumb.set_startup(True)
        assert thumb.toolTip() == "Open page: main_page. Startup page. Available. No unsaved changes."
        assert thumb.accessibleName() == "Page thumbnail: main_page. Startup page. Available. No unsaved changes."
        assert thumb._state_chip.accessibleName() == "Page state: Startup."

        thumb.set_selected(True)
        assert thumb.accessibleName() == "Page thumbnail: main_page. Startup page. Current page. No unsaved changes."
        assert thumb._meta_label.accessibleName() == "Startup page. Current page. No unsaved changes. Right click for actions."
        assert thumb._state_chip.accessibleName() == "Page state: Current."

        thumb.set_dirty(True)
        assert thumb._name_label.text() == "main_page*"
        assert thumb.toolTip() == "Open page: main_page. Startup page. Current page. Unsaved changes."
        assert thumb._name_label.accessibleName() == "Page name: main_page*. Startup page. Current page. Unsaved changes."
        assert thumb._meta_label.accessibleName() == "Startup page. Current page. Unsaved changes. Right click for actions."
        assert thumb._dirty_chip.accessibleName() == "Page save state: Dirty."
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

    def test_page_navigator_header_exposes_engineering_metadata(self, qapp):
        from ui_designer.ui.widgets.page_navigator import PageNavigator

        navigator = PageNavigator()

        assert navigator._header_frame.accessibleName() == (
            "Page navigator header. Page navigator: 0 pages. Current page: none. Startup page: none. No dirty pages."
        )
        assert navigator._eyebrow_label.accessibleName() == "Page flow workspace surface."
        assert navigator._eyebrow_label.isHidden() is True
        assert navigator._header_meta_label.accessibleName() == (
            "Current page: none. Startup page: none. Use the rail to scan visual state and jump between pages."
        )
        assert navigator._header_meta_label.isHidden() is True
        assert navigator._count_chip.isHidden() is True
        assert navigator._count_chip.accessibleName() == "Page count: 0 pages."
        assert navigator._startup_chip.isHidden() is True
        assert navigator._startup_chip.accessibleName() == "Startup page: none."
        assert navigator._dirty_chip.accessibleName() == "Dirty pages: No dirty pages."
        assert navigator._guidance_frame.accessibleName() == (
            "Page navigator guidance. Left click opens a page. Right click duplicates, deletes, or inserts a template after the selected page."
        )
        assert navigator._guidance_frame.isHidden() is True
        assert navigator._guidance_label.accessibleName() == (
            "Left click opens a page. Right click duplicates, deletes, or inserts a template after the selected page."
        )

        navigator.set_pages({"main_page": object(), "detail_page": object()})
        navigator.set_startup_page("main_page")
        navigator.set_current_page("detail_page")
        navigator.set_dirty_pages({"main_page"})

        assert navigator._header_frame.accessibleName() == (
            "Page navigator header. Page navigator: 2 pages. Current page: detail_page. Startup page: main_page. 1 dirty page."
        )
        assert navigator._header_meta_label.accessibleName() == (
            "Current page: detail_page. Startup page: main_page. Use the rail to scan visual state and jump between pages."
        )
        assert navigator._count_chip.isHidden() is True
        assert navigator._count_chip.accessibleName() == "Page count: 2 pages."
        assert navigator._startup_chip.isHidden() is True
        assert navigator._startup_chip.accessibleName() == "Startup page: main_page."
        assert navigator._dirty_chip.accessibleName() == "Dirty pages: 1 dirty page."
        navigator.deleteLater()

    def test_header_frame_hint_skips_no_op_rewrites(self, qapp, monkeypatch):
        from ui_designer.ui.widgets.page_navigator import PageNavigator

        navigator = PageNavigator()
        navigator._header_frame.setProperty("_page_navigator_hint_snapshot", None)

        hint_calls = 0
        original_set_tooltip = navigator._header_frame.setToolTip

        def counted_set_tooltip(text):
            nonlocal hint_calls
            hint_calls += 1
            return original_set_tooltip(text)

        monkeypatch.setattr(navigator._header_frame, "setToolTip", counted_set_tooltip)

        navigator._update_accessibility_summary()
        assert hint_calls == 1

        navigator._update_accessibility_summary()
        assert hint_calls == 1

        navigator.set_pages({"main_page": object()})
        assert hint_calls == 2
        navigator.deleteLater()

    def test_header_frame_accessible_name_skips_no_op_rewrites(self, qapp, monkeypatch):
        from ui_designer.ui.widgets.page_navigator import PageNavigator

        navigator = PageNavigator()
        navigator._header_frame.setProperty("_page_navigator_accessible_snapshot", None)

        accessible_calls = 0
        original_set_accessible_name = navigator._header_frame.setAccessibleName

        def counted_set_accessible_name(text):
            nonlocal accessible_calls
            accessible_calls += 1
            return original_set_accessible_name(text)

        monkeypatch.setattr(navigator._header_frame, "setAccessibleName", counted_set_accessible_name)

        navigator._update_accessibility_summary()
        assert accessible_calls == 1

        navigator._update_accessibility_summary()
        assert accessible_calls == 1

        navigator.set_pages({"main_page": object()})
        assert accessible_calls == 2
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
