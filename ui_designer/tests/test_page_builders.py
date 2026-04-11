"""Tests for shared test page builders."""

from ui_designer.tests.page_builders import build_test_page_with_title, build_test_page_with_widget
from ui_designer.utils.scaffold import require_page_root


class TestPageBuilders:
    def test_build_test_page_with_widget_accepts_page_name_and_widget_name(self):
        page, widget = build_test_page_with_widget(
            page_name="home",
            name="subtitle",
            x=20,
            y=24,
            width=120,
            height=28,
        )
        root = require_page_root(page, "home")

        assert page.name == "home"
        assert widget.name == "subtitle"
        assert widget in root.children
        assert widget.x == 20
        assert widget.y == 24

    def test_build_test_page_with_title_preserves_custom_widget_name(self):
        page, title = build_test_page_with_title(
            page_name="detail",
            name="heading",
        )
        root = require_page_root(page, "detail")

        assert page.name == "detail"
        assert title.name == "heading"
        assert title in root.children
