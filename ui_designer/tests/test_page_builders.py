"""Tests for shared test page builders."""

from ui_designer.tests.page_builders import (
    build_test_page_from_root_with_widgets,
    build_test_page_only_with_widget,
    build_test_page_root_with_widgets,
    build_test_page_with_root,
    build_test_page_with_root_widget,
    build_test_page_with_title,
    build_test_page_with_widget,
    build_test_page_with_widgets,
)
from ui_designer.model.widget_model import WidgetModel
from ui_designer.utils.scaffold import require_page_root


class TestPageBuilders:
    def test_build_test_page_with_root_returns_page_and_root(self):
        page, root = build_test_page_with_root(
            page_name="home",
            screen_width=320,
            screen_height=240,
        )

        assert page.name == "home"
        assert root is page.root_widget
        assert root.width == 320
        assert root.height == 240

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

    def test_build_test_page_only_with_widget_returns_attached_widget(self):
        widget = build_test_page_only_with_widget(
            page_name="home",
            name="subtitle",
            x=20,
            y=24,
            width=120,
            height=28,
        )

        assert widget.name == "subtitle"
        assert widget.widget_type == "label"
        assert widget.parent is not None

    def test_build_test_page_with_root_widget_supports_custom_root_type(self):
        page, root = build_test_page_with_root_widget(
            page_name="detail",
            root_widget_type="linearlayout",
            root_name="root_layout",
            width=200,
            height=120,
        )

        assert page.name == "detail"
        assert root is page.root_widget
        assert root.widget_type == "linearlayout"
        assert root.name == "root_layout"
        assert root.width == 200
        assert root.height == 120

    def test_build_test_page_from_root_with_widgets_populates_custom_root(self):
        root = WidgetModel("linearlayout", name="root_layout", x=0, y=0, width=200, height=120)
        first = WidgetModel("label", name="first")
        second = WidgetModel("button", name="second")

        page, resolved_root = build_test_page_from_root_with_widgets(
            "detail",
            root=root,
            widgets=[first, second],
        )

        assert page.name == "detail"
        assert resolved_root is root
        assert root.children == [first, second]

    def test_build_test_page_with_title_preserves_custom_widget_name(self):
        page, title = build_test_page_with_title(
            page_name="detail",
            name="heading",
        )
        root = require_page_root(page, "detail")

        assert page.name == "detail"
        assert title.name == "heading"
        assert title in root.children

    def test_build_test_page_with_widgets_supports_custom_root_and_children(self):
        first = WidgetModel("label", name="first")
        second = WidgetModel("button", name="second")

        page, root = build_test_page_with_widgets(
            page_name="detail",
            screen_width=200,
            screen_height=120,
            root_widget_type="linearlayout",
            root_name="root_layout",
            widgets=[first, second],
        )

        assert page.name == "detail"
        assert root is page.root_widget
        assert root.widget_type == "linearlayout"
        assert root.name == "root_layout"
        assert root.width == 200
        assert root.height == 120
        assert root.children == [first, second]

    def test_build_test_page_root_with_widgets_returns_populated_root(self):
        first = WidgetModel("label", name="first")
        second = WidgetModel("button", name="second")

        root = build_test_page_root_with_widgets(
            page_name="detail",
            screen_width=200,
            screen_height=120,
            root_widget_type="linearlayout",
            root_name="root_layout",
            widgets=[first, second],
        )

        assert root.widget_type == "linearlayout"
        assert root.name == "root_layout"
        assert root.width == 200
        assert root.height == 120
        assert root.children == [first, second]
