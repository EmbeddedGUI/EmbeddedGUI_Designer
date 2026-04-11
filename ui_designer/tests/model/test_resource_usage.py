"""Tests for ui_designer.model.resource_usage."""

from ui_designer.tests.project_builders import (
    build_test_project_only_with_page_widgets,
    build_test_project_only_with_widgets,
    build_test_project_with_widgets,
)
from ui_designer.model.resource_usage import (
    collect_unused_resource_names,
    collect_unused_string_keys,
    collect_page_resource_usages,
    collect_project_resource_usages,
    filter_resource_names,
    filter_string_keys,
    find_resource_usages,
    rewrite_project_resource_references,
    rewrite_project_string_references,
)
from ui_designer.model.string_resource import DEFAULT_LOCALE, StringResourceCatalog
from ui_designer.model.widget_model import WidgetModel

class TestResourceUsage:
    def test_collect_page_resource_usages_tracks_all_resource_property_types(self):
        image = WidgetModel("image", name="hero")
        image.properties["image_file"] = "hero.png"

        label = WidgetModel("label", name="title")
        label.properties["font_file"] = "demo.ttf"
        label.properties["font_text_file"] = "chars.txt"
        project, page, _root = build_test_project_with_widgets("UsageDemo", widgets=[image, label])

        usages = collect_page_resource_usages(page)
        summary = {(entry.resource_type, entry.resource_name, entry.widget_name, entry.property_name) for entry in usages}

        assert summary == {
            ("image", "hero.png", "hero", "image_file"),
            ("font", "demo.ttf", "title", "font_file"),
            ("text", "chars.txt", "title", "font_text_file"),
        }

    def test_collect_project_resource_usages_groups_entries_by_resource_name(self):
        label_a = WidgetModel("label", name="title")
        label_a.properties["font_file"] = "demo.ttf"

        label_b = WidgetModel("label", name="subtitle")
        label_b.properties["font_file"] = "demo.ttf"

        image = WidgetModel("image", name="hero")
        image.properties["image_file"] = "hero.png"
        project = build_test_project_only_with_page_widgets(
            "UsageDemo",
            page_widgets={
                "main_page": [label_a],
                "detail_page": [label_b, image],
            },
        )

        usage_index = collect_project_resource_usages(project)
        font_usages = usage_index[("font", "demo.ttf")]
        image_usages = find_resource_usages(project, "image", "hero.png")

        assert [(entry.page_name, entry.widget_name) for entry in font_usages] == [
            ("main_page", "title"),
            ("detail_page", "subtitle"),
        ]
        assert [(entry.page_name, entry.widget_name, entry.property_name) for entry in image_usages] == [
            ("detail_page", "hero", "image_file"),
        ]

    def test_collect_unused_resource_names_and_filter_resource_names(self):
        usage_index = {
            ("image", "hero.png"): ["used"],
            ("image", "missing_used.png"): ["used"],
        }
        names = ["hero.png", "missing_used.png", "spare.png", "ghost.png"]

        assert collect_unused_resource_names(names, usage_index, "image") == ["spare.png", "ghost.png"]
        assert filter_resource_names(
            names,
            usage_index,
            "image",
            search_text="sp",
            status="all",
            missing_names={"ghost.png", "missing_used.png"},
        ) == ["spare.png"]
        assert filter_resource_names(
            names,
            usage_index,
            "image",
            status="missing",
            missing_names={"ghost.png", "missing_used.png"},
        ) == ["missing_used.png", "ghost.png"]
        assert filter_resource_names(
            names,
            usage_index,
            "image",
            status="unused",
            missing_names={"ghost.png", "missing_used.png"},
        ) == ["spare.png", "ghost.png"]

    def test_collect_unused_string_keys_and_filter_string_keys(self):
        catalog = StringResourceCatalog()
        catalog.set("greeting", "Hello", DEFAULT_LOCALE)
        catalog.set("greeting", "Ni Hao", "zh")
        catalog.set("notes", "Spare", DEFAULT_LOCALE)
        catalog.set("notes", "Bei Yong", "zh")
        catalog.set("debug", "Trace", DEFAULT_LOCALE)

        usage_index = {
            ("string", "greeting"): ["used"],
        }

        assert collect_unused_string_keys(catalog, usage_index) == ["debug", "notes"]
        assert filter_string_keys(
            catalog,
            usage_index,
            locale=DEFAULT_LOCALE,
            search_text="spare",
            status="all",
        ) == ["notes"]
        assert filter_string_keys(
            catalog,
            usage_index,
            locale="zh",
            search_text="bei",
            status="all",
        ) == ["notes"]
        assert filter_string_keys(
            catalog,
            usage_index,
            locale=DEFAULT_LOCALE,
            status="unused",
        ) == ["debug", "notes"]

    def test_rewrite_project_resource_references_updates_all_matching_widgets(self):
        label_a = WidgetModel("label", name="title")
        label_a.properties["font_file"] = "demo.ttf"
        label_a.properties["font_text_file"] = "chars.txt"

        label_b = WidgetModel("label", name="subtitle")
        label_b.properties["font_file"] = "demo.ttf"
        label_b.properties["font_text_file"] = "chars.txt"

        untouched = WidgetModel("label", name="caption")
        untouched.properties["font_file"] = "demo.ttf"
        untouched.properties["font_text_file"] = "other.txt"
        project = build_test_project_only_with_page_widgets(
            "RewriteDemo",
            page_widgets={
                "main_page": [label_a],
                "detail_page": [label_b, untouched],
            },
        )

        touched_pages, rewrite_count = rewrite_project_resource_references(project, "text", "chars.txt", "chars_new.txt")

        assert [page.name for page in touched_pages] == ["main_page", "detail_page"]
        assert rewrite_count == 2
        assert label_a.properties["font_text_file"] == "chars_new.txt"
        assert label_b.properties["font_text_file"] == "chars_new.txt"
        assert untouched.properties["font_text_file"] == "other.txt"

    def test_rewrite_project_resource_references_can_clear_references(self):
        image = WidgetModel("image", name="hero")
        image.properties["image_file"] = "missing.png"
        project = build_test_project_only_with_widgets("RewriteDemo", widgets=[image])

        touched_pages, rewrite_count = rewrite_project_resource_references(project, "image", "missing.png", "")

        assert [entry.name for entry in touched_pages] == ["main_page"]
        assert rewrite_count == 1
        assert image.properties["image_file"] == ""

    def test_collect_and_rewrite_string_references(self):
        title = WidgetModel("label", name="title")
        title.properties["text"] = "@string/greeting"

        subtitle = WidgetModel("label", name="subtitle")
        subtitle.properties["text"] = "@string/greeting"
        project = build_test_project_only_with_page_widgets(
            "StringUsageDemo",
            page_widgets={
                "main_page": [title],
                "detail_page": [subtitle],
            },
        )

        usages = find_resource_usages(project, "string", "greeting")
        assert [(entry.page_name, entry.widget_name, entry.property_name) for entry in usages] == [
            ("main_page", "title", "text"),
            ("detail_page", "subtitle", "text"),
        ]

        touched_pages, rewrite_count = rewrite_project_string_references(
            project,
            "greeting",
            replacement_text="Hello",
        )

        assert [page.name for page in touched_pages] == ["main_page", "detail_page"]
        assert rewrite_count == 2
        assert title.properties["text"] == "Hello"
        assert subtitle.properties["text"] == "Hello"

    def test_rewrite_string_references_to_new_key(self):
        title = WidgetModel("label", name="title")
        title.properties["text"] = "@string/greeting"
        project = build_test_project_only_with_widgets("StringRenameDemo", widgets=[title])

        touched_pages, rewrite_count = rewrite_project_string_references(
            project,
            "greeting",
            new_key="salutation",
        )

        assert [item.name for item in touched_pages] == ["main_page"]
        assert rewrite_count == 1
        assert title.properties["text"] == "@string/salutation"
