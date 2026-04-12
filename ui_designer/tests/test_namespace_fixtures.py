"""Tests for shared namespace-backed test doubles."""

from ui_designer.tests.namespace_fixtures import (
    build_namespace_stub,
    build_overwrite_diff,
    build_project_stub,
    build_widget_stub,
)


class TestNamespaceFixtures:
    def test_build_namespace_stub_sets_attributes(self):
        result = build_namespace_stub(app="DemoApp", size=24)

        assert result.app == "DemoApp"
        assert result.size == 24

    def test_build_project_stub_copies_pages(self):
        pages = ["main_page"]

        result = build_project_stub(pages=pages, sdk_root="D:/sdk")
        pages.append("detail_page")

        assert result.pages == ["main_page"]
        assert result.sdk_root == "D:/sdk"

    def test_build_widget_stub_merges_properties(self):
        result = build_widget_stub(properties={"font_file": "demo.ttf"}, text_file="demo.txt")

        assert result.properties == {
            "font_file": "demo.ttf",
            "text_file": "demo.txt",
        }

    def test_build_overwrite_diff_defaults_to_namespace_shape(self):
        result = build_overwrite_diff(new_count=2, added_count=1)

        assert result.existing_count == 0
        assert result.new_count == 2
        assert result.added_count == 1
        assert result.removed_count == 0
