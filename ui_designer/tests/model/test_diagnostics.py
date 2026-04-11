"""Tests for ui_designer.model.diagnostics."""

from ui_designer.tests.page_builders import (
    add_test_widget,
    build_test_page,
    build_test_page_with_title,
    build_test_pages,
)

from ui_designer.model.diagnostics import (
    analyze_page,
    analyze_project_callback_conflicts,
    analyze_selection,
    diagnostic_entry_payload,
    diagnostic_target_payload,
)
from ui_designer.model.project import Project
from ui_designer.model.resource_catalog import ResourceCatalog
from ui_designer.model.string_resource import StringResourceCatalog
from ui_designer.model.widget_model import WidgetModel


class TestPageDiagnostics:
    def test_analyze_page_reports_invalid_duplicate_bounds_and_missing_resource(self, tmp_path):
        page = build_test_page()
        invalid = add_test_widget(page, name="bad-name", x=8, y=8, width=60, height=20)
        duplicate_a = add_test_widget(page, name="dup_name", x=20, y=40, width=60, height=20)
        duplicate_b = add_test_widget(page, name="dup_name", x=230, y=40, width=30, height=20)
        missing = add_test_widget(page, "image", name="missing_image", x=16, y=80, width=48, height=48)
        missing.properties["image_file"] = "ghost.png"

        catalog = ResourceCatalog()
        catalog.add_image("ghost.png")
        resource_dir = tmp_path / "resources"
        (resource_dir / "images").mkdir(parents=True)

        entries = analyze_page(page, resource_catalog=catalog, source_resource_dir=str(resource_dir))

        codes = [entry.code for entry in entries]
        assert codes.count("invalid_name") == 1
        assert codes.count("duplicate_name") == 2
        assert codes.count("bounds") == 1
        assert codes.count("missing_resource") == 1
        assert any(entry.code == "missing_resource" and "missing on disk" in entry.message for entry in entries)
        assert all(entry.page_name == "main_page" for entry in entries)
        assert any(entry.code == "invalid_name" and entry.target_page_name == "main_page" and entry.target_widget_name == "bad-name" for entry in entries)
        assert any(entry.code == "bounds" and entry.target_page_name == "main_page" and entry.target_widget_name == "dup_name" for entry in entries)
        missing_entry = next(entry for entry in entries if entry.code == "missing_resource")
        assert missing_entry.resource_type == "image"
        assert missing_entry.resource_name == "ghost.png"
        assert missing_entry.property_name == "image_file"
        assert missing_entry.target_page_name == "main_page"
        assert missing_entry.target_widget_name == "missing_image"

    def test_analyze_page_reports_invalid_page_fields(self):
        page, _title = build_test_page_with_title(x=8, y=8, width=60, height=20)
        page.user_fields = [
            {"name": "title", "type": "int"},
            {"name": "counter", "type": "int"},
            {"name": "counter", "type": "uint32_t"},
            {"name": "bad-name", "type": "int"},
        ]

        entries = analyze_page(page)

        codes = [entry.code for entry in entries]
        assert codes.count("page_field_conflict") == 1
        assert codes.count("page_field_duplicate_name") == 2
        assert codes.count("page_field_invalid_name") == 1
        assert any("auto-generated page member" in entry.message for entry in entries)
        assert any("already exists in this page" in entry.message for entry in entries)
        assert all(entry.target_page_name == "main_page" for entry in entries)

    def test_analyze_page_reports_invalid_page_timers(self):
        page, _title = build_test_page_with_title(x=8, y=8, width=60, height=20)
        page.user_fields = [{"name": "counter", "type": "int"}]
        page.timers = [
            {"name": "title", "callback": "tick_title", "delay_ms": "1000", "period_ms": "1000"},
            {"name": "refresh_timer", "callback": "", "delay_ms": "1000", "period_ms": "1000"},
        ]

        entries = analyze_page(page)

        codes = [entry.code for entry in entries]
        assert codes.count("page_timer_conflict") == 1
        assert codes.count("page_timer_missing_callback") == 1
        assert any("callback function name" in entry.message for entry in entries)
        assert all(entry.target_page_name == "main_page" for entry in entries)

    def test_analyze_page_reports_callback_signature_conflicts(self):
        page = build_test_page()
        button = add_test_widget(page, "button", name="confirm_button", x=8, y=8, width=80, height=28)
        slider = add_test_widget(page, "slider", name="volume_slider", x=8, y=48, width=120, height=24)
        button.on_click = "on_shared_action"
        slider.events["onValueChanged"] = "on_shared_action"

        entries = analyze_page(page)

        assert [entry.code for entry in entries] == ["callback_signature_conflict"]
        assert "on_shared_action" in entries[0].message
        assert "confirm_button.onClick" in entries[0].message
        assert "volume_slider.onValueChanged" in entries[0].message
        assert entries[0].target_page_name == "main_page"
        assert entries[0].target_widget_name == "confirm_button"

    def test_analyze_page_reports_missing_string_key_references(self):
        page, title = build_test_page_with_title(x=8, y=8, width=60, height=20)
        title.properties["text"] = "@string/missing_key"

        string_catalog = StringResourceCatalog()
        string_catalog.set("greeting", "Hello")

        entries = analyze_page(page, string_catalog=string_catalog)

        assert [entry.code for entry in entries] == ["missing_string_resource"]
        assert "missing_key" in entries[0].message
        assert entries[0].resource_type == "string"
        assert entries[0].resource_name == "missing_key"
        assert entries[0].property_name == "text"
        assert entries[0].target_page_name == "main_page"
        assert entries[0].target_widget_name == "title"


class TestSelectionDiagnostics:
    def test_analyze_selection_reports_locked_hidden_and_layout_managed(self):
        layout_parent = WidgetModel("linearlayout", name="layout_parent", x=0, y=0, width=240, height=80)
        managed = WidgetModel("label", name="managed_widget", x=12, y=8, width=80, height=20)
        managed.designer_locked = True
        managed.designer_hidden = True
        layout_parent.add_child(managed)

        entries = analyze_selection([managed])

        codes = [entry.code for entry in entries]
        assert codes == [
            "selection_locked",
            "selection_hidden",
            "selection_layout_managed",
        ]
        assert entries[0].severity == "info"
        assert "canvas drag and resize are disabled" in entries[0].message
        assert "canvas hit testing" in entries[1].message
        assert "layout-managed by linearlayout" in entries[2].message


class TestProjectDiagnostics:
    def test_analyze_project_reports_duplicate_callbacks_across_pages(self):
        project = Project(screen_width=240, screen_height=320, app_name="DiagApp")
        main_page, detail_page = build_test_pages("main_page", "detail_page")
        main_button = add_test_widget(main_page, "button", name="confirm_button", x=8, y=8, width=80, height=28)
        detail_button = add_test_widget(detail_page, "button", name="confirm_button_2", x=8, y=8, width=80, height=28)
        main_button.on_click = "on_confirm"
        detail_button.on_click = "on_confirm"
        project.add_page(main_page)
        project.add_page(detail_page)

        entries = analyze_project_callback_conflicts(project)

        assert [entry.code for entry in entries] == ["project_callback_duplicate"]
        assert "main_page/confirm_button.onClick" in entries[0].message
        assert "detail_page/confirm_button_2.onClick" in entries[0].message
        assert entries[0].target_page_name == "detail_page"
        assert entries[0].target_widget_name == "confirm_button_2"

    def test_analyze_project_reports_callback_signature_conflicts_across_pages(self):
        project = Project(screen_width=240, screen_height=320, app_name="DiagApp")
        main_page, detail_page = build_test_pages("main_page", "detail_page")
        main_button = add_test_widget(main_page, "button", name="confirm_button", x=8, y=8, width=80, height=28)
        detail_slider = add_test_widget(detail_page, "slider", name="volume_slider", x=8, y=8, width=120, height=24)
        main_button.on_click = "on_shared_action"
        detail_slider.events["onValueChanged"] = "on_shared_action"
        project.add_page(main_page)
        project.add_page(detail_page)

        entries = analyze_project_callback_conflicts(project)

        assert [entry.code for entry in entries] == ["project_callback_signature_conflict"]
        assert "main_page/confirm_button.onClick" in entries[0].message
        assert "detail_page/volume_slider.onValueChanged" in entries[0].message
        assert entries[0].target_page_name == "detail_page"
        assert entries[0].target_widget_name == "volume_slider"


class TestDiagnosticPayloads:
    def test_diagnostic_target_payload_classifies_resource_and_project_entries(self):
        resource_entry = type(
            "Entry",
            (),
            {
                "code": "missing_resource",
                "page_name": "main_page",
                "widget_name": "missing_image",
                "target_page_name": "main_page",
                "target_widget_name": "missing_image",
                "resource_type": "image",
                "resource_name": "ghost.png",
            },
        )()
        project_entry = type(
            "Entry",
            (),
            {
                "code": "project_callback_duplicate",
                "page_name": "project",
                "widget_name": "on_confirm",
                "target_page_name": "",
                "target_widget_name": "",
                "resource_type": "",
                "resource_name": "",
            },
        )()

        assert diagnostic_target_payload(resource_entry) == {
            "target_kind": "resource",
            "target_page_name": "main_page",
            "target_widget_name": "missing_image",
        }
        assert diagnostic_target_payload(project_entry) == {
            "target_kind": "project",
            "target_page_name": "",
            "target_widget_name": "",
        }

    def test_diagnostic_entry_payload_includes_target_metadata(self):
        entry = type(
            "Entry",
            (),
            {
                "severity": "error",
                "code": "page_timer_missing_callback",
                "message": "Page timer metadata is invalid.",
                "page_name": "main_page",
                "widget_name": "refresh_timer",
                "resource_type": "",
                "resource_name": "",
                "property_name": "",
                "target_page_name": "main_page",
                "target_widget_name": "",
            },
        )()

        assert diagnostic_entry_payload(entry) == {
            "severity": "error",
            "code": "page_timer_missing_callback",
            "message": "Page timer metadata is invalid.",
            "page_name": "main_page",
            "widget_name": "refresh_timer",
            "resource_type": "",
            "resource_name": "",
            "property_name": "",
            "target_kind": "page_timer",
            "target_page_name": "main_page",
            "target_widget_name": "",
        }
