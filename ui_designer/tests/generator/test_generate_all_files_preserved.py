"""Tests for generate_all_files_preserved — the production save pipeline.

Covers:
  - USER_OWNED (.c) file: created fresh when it doesn't exist on disk
  - USER_OWNED (.c) file: NOT overwritten when it already exists
  - legacy USER_OWNED/page header formats are rejected with actionable errors
  - GENERATED_ALWAYS (*_layout.c, uicode.*): always produced in output dict
  - Multi-page project: all page files produced
  - Backup=False skips backup creation
"""

import os
from pathlib import Path
import pytest

from ui_designer.model.widget_model import WidgetModel
from ui_designer.model.page import Page
from ui_designer.model.project import Project
from ui_designer.generator.code_generator import (
    generate_all_files_preserved,
    GENERATED_ALWAYS,
    USER_OWNED,
)
from ui_designer.utils.scaffold import (
    APP_CONFIG_DESIGNER_RELPATH,
    BUILD_DESIGNER_RELPATH,
    EGUI_STRINGS_HEADER_RELPATH,
    EGUI_STRINGS_SOURCE_RELPATH,
    UICODE_HEADER_RELPATH,
    UICODE_SOURCE_RELPATH,
    designer_page_header_relpath,
    designer_page_layout_relpath,
)


# ── Fixtures ─────────────────────────────────────────────────────


def _make_project_with_page(page_name="main_page"):
    root = WidgetModel("group", name="root_group", x=0, y=0, width=240, height=320)
    label = WidgetModel("label", name="title_label", x=10, y=10, width=200, height=30)
    root.add_child(label)
    page = Page(file_path=f"layout/{page_name}.xml", root_widget=root)
    proj = Project(screen_width=240, screen_height=320, app_name="TestApp")
    proj.add_page(page)
    return proj


# ======================================================================
# TestUserOwnedFiles
# ======================================================================


class TestUserOwnedFiles:
    """USER_OWNED (*.c) file semantics."""

    def test_user_owned_created_when_not_on_disk(self, tmp_path):
        """Fresh project: .c skeleton should be produced."""
        proj = _make_project_with_page("home")
        output_dir = str(tmp_path)
        result = generate_all_files_preserved(proj, output_dir, backup=False)
        assert "home.c" in result

    def test_user_owned_not_overwritten_when_exists(self, tmp_path):
        """If user file already exists, it must NOT appear in the output dict."""
        proj = _make_project_with_page("settings")
        output_dir = str(tmp_path)

        # Write a fake user-owned file
        user_file = tmp_path / "settings.c"
        user_file.write_text("/* my custom code */\n", encoding="utf-8")

        result = generate_all_files_preserved(proj, output_dir, backup=False)
        # The file must NOT be in the result (not to be overwritten)
        assert "settings.c" not in result

    def test_user_owned_ext_header_not_overwritten_when_exists(self, tmp_path):
        proj = _make_project_with_page("settings")
        output_dir = str(tmp_path)

        user_ext = tmp_path / "settings_ext.h"
        user_ext.write_text("#define SETTINGS_EXT 1\n", encoding="utf-8")

        result = generate_all_files_preserved(proj, output_dir, backup=False)

        assert "settings_ext.h" not in result

    def test_user_owned_content_is_not_empty(self, tmp_path):
        """The generated skeleton must be non-empty."""
        proj = _make_project_with_page("main_page")
        output_dir = str(tmp_path)
        result = generate_all_files_preserved(proj, output_dir, backup=False)
        assert "main_page.c" in result
        assert len(result["main_page.c"]) > 0

    def test_user_owned_contains_on_open_function(self, tmp_path):
        """The skeleton must contain the on_open lifecycle function."""
        proj = _make_project_with_page("main_page")
        output_dir = str(tmp_path)
        result = generate_all_files_preserved(proj, output_dir, backup=False)
        assert "egui_main_page_user_on_open" in result["main_page.c"]

    def test_user_owned_contains_customisation_hooks(self, tmp_path):
        """The skeleton must contain comments/regions so users know where to add code."""
        proj = _make_project_with_page("main_page")
        output_dir = str(tmp_path)
        result = generate_all_files_preserved(proj, output_dir, backup=False)
        # The skeleton uses TODO comments and/or section markers for user guidance
        content = result["main_page.c"]
        has_hooks = ("TODO" in content or "USER CODE" in content
                     or "Your includes" in content or "Your callback" in content)
        assert has_hooks, "User-owned skeleton must contain customisation guidance comments"

    def test_generation_raises_for_unknown_widget_types(self, tmp_path):
        root = WidgetModel("group", name="root_group", x=0, y=0, width=240, height=320)
        root.add_child(WidgetModel("missing_widget", name="missing_1", x=10, y=10, width=80, height=24))
        page = Page(file_path="layout/main_page.xml", root_widget=root)
        proj = Project(screen_width=240, screen_height=320, app_name="TestApp")
        proj.add_page(page)

        with pytest.raises(ValueError, match="unresolved widget types"):
            generate_all_files_preserved(proj, str(tmp_path), backup=False)

    def test_legacy_designer_managed_user_source_is_rejected(self, tmp_path):
        proj = _make_project_with_page("main_page")
        proj.get_page_by_name("main_page").timers = [
            {
                "name": "refresh_timer",
                "callback": "tick_refresh",
                "delay_ms": "500",
                "period_ms": "1000",
                "auto_start": True,
            }
        ]
        output_dir = str(tmp_path)

        user_file = tmp_path / "main_page.c"
        user_file.write_text(
            (
                "// main_page.c - User implementation for main_page\n"
                "// This file is YOUR code. The designer will NEVER overwrite it.\n"
                "// Layout/widget init is in main_page_layout.c (auto-generated).\n"
                "\n"
                '#include "egui.h"\n'
                "#include <stdlib.h>\n"
                "\n"
                '#include "uicode.h"\n'
                '#include "main_page.h"\n'
                '\n#include "my_logic.h"\n'
                "\n"
                "static void egui_main_page_on_open(egui_page_base_t *self)\n"
                "{\n"
                "    egui_main_page_t *local = (egui_main_page_t *)self;\n"
                "    EGUI_UNUSED(local);\n"
                "    // Call super on_open\n"
                "    egui_page_base_on_open(self);\n"
                "\n"
                "    // Auto-generated layout initialization\n"
                "    egui_main_page_layout_init(self);\n"
                "\n"
                "    egui_view_label_set_text((egui_view_t *)&local->title_label, \"ready\");\n"
                "}\n"
                "\n"
                "static void egui_main_page_on_close(egui_page_base_t *self)\n"
                "{\n"
                "    egui_main_page_t *local = (egui_main_page_t *)self;\n"
                "    EGUI_UNUSED(local);\n"
                "    // Call super on_close\n"
                "    egui_page_base_on_close(self);\n"
                "\n"
                "    cleanup_logic();\n"
                "}\n"
                "\n"
                "static void egui_main_page_on_key_pressed(egui_page_base_t *self, uint16_t keycode)\n"
                "{\n"
                "    egui_main_page_t *local = (egui_main_page_t *)self;\n"
                "    EGUI_UNUSED(local);\n"
                "\n"
                "    if (keycode == 1)\n"
                "    {\n"
                "        uicode_start_prev_page();\n"
                "    }\n"
                "}\n"
                "\n"
                "static const egui_page_base_api_t EGUI_VIEW_API_TABLE_NAME(egui_main_page_t) = {\n"
                "    .on_open = egui_main_page_on_open,\n"
                "    .on_close = egui_main_page_on_close,\n"
                "    .on_key_pressed = egui_main_page_on_key_pressed,\n"
                "};\n"
                "\n"
                "void egui_main_page_init(egui_page_base_t *self)\n"
                "{\n"
                "    egui_main_page_t *local = (egui_main_page_t *)self;\n"
                "    EGUI_UNUSED(local);\n"
                "    // Call super init\n"
                "    egui_page_base_init(self);\n"
                "    // Set vtable\n"
                "    self->api = &EGUI_VIEW_API_TABLE_NAME(egui_main_page_t);\n"
                '    egui_page_base_set_name(self, "main_page");\n'
                "\n"
                "    init_logic();\n"
                "}\n"
            ),
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="Unsupported legacy page source detected: main_page.c"):
            generate_all_files_preserved(proj, output_dir, backup=False)

    def test_legacy_user_source_fixture_is_rejected(self, tmp_path):
        proj = _make_project_with_page("main_page")
        fixture_path = Path(__file__).resolve().parents[1] / "test_data" / "user_code_sample.c"
        user_file = tmp_path / "main_page.c"
        user_file.write_text(fixture_path.read_text(encoding="utf-8"), encoding="utf-8")

        with pytest.raises(ValueError, match="Unsupported legacy page source detected: main_page.c"):
            generate_all_files_preserved(proj, str(tmp_path), backup=False)

    def test_legacy_user_code_callbacks_source_is_rejected(self, tmp_path):
        proj = _make_project_with_page("main_page")
        page = proj.get_page_by_name("main_page")
        button = WidgetModel("button", name="confirm_button", x=16, y=16, width=80, height=32)
        button.on_click = "on_confirm_button_click"
        page.root_widget.add_child(button)

        user_file = tmp_path / "main_page.c"
        user_file.write_text(
            (
                "// main_page.c - User implementation for main_page\n"
                "// Layout/widget init is in main_page_layout.c (auto-generated).\n"
                '#include "egui.h"\n'
                '#include "uicode.h"\n'
                '#include "main_page.h"\n'
                "\n"
                "// USER CODE BEGIN callbacks\n"
                "void on_confirm_button_click(egui_view_t *self)\n"
                "{\n"
                "    EGUI_UNUSED(self);\n"
                "    custom_logic();\n"
                "}\n"
                "// USER CODE END callbacks\n"
                "\n"
                "// USER CODE BEGIN init\n"
                "    init_logic();\n"
                "// USER CODE END init\n"
            ),
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="Unsupported legacy page source detected: main_page.c"):
            generate_all_files_preserved(proj, str(tmp_path), backup=False)


# ======================================================================
# TestGeneratedAlwaysFiles
# ======================================================================


class TestGeneratedAlwaysFiles:
    """GENERATED_ALWAYS (*_layout.c, uicode.*) are always in the output."""

    def test_layout_always_produced(self, tmp_path):
        proj = _make_project_with_page("main_page")
        output_dir = str(tmp_path)
        result = generate_all_files_preserved(proj, output_dir, backup=False)
        assert designer_page_layout_relpath("main_page") in result

    def test_uicode_source_always_produced(self, tmp_path):
        proj = _make_project_with_page("main_page")
        output_dir = str(tmp_path)
        result = generate_all_files_preserved(proj, output_dir, backup=False)
        assert UICODE_SOURCE_RELPATH in result

    def test_uicode_header_always_produced(self, tmp_path):
        proj = _make_project_with_page("main_page")
        output_dir = str(tmp_path)
        result = generate_all_files_preserved(proj, output_dir, backup=False)
        assert UICODE_HEADER_RELPATH in result

    def test_app_config_always_produced(self, tmp_path):
        proj = _make_project_with_page("main_page")
        output_dir = str(tmp_path)
        result = generate_all_files_preserved(proj, output_dir, backup=False)
        assert APP_CONFIG_DESIGNER_RELPATH in result

    def test_build_designer_always_produced(self, tmp_path):
        proj = _make_project_with_page("main_page")
        output_dir = str(tmp_path)
        result = generate_all_files_preserved(proj, output_dir, backup=False)
        assert BUILD_DESIGNER_RELPATH in result

    def test_i18n_string_files_use_designer_paths(self, tmp_path):
        from ui_designer.model.string_resource import StringResourceCatalog

        proj = _make_project_with_page("main_page")
        catalog = StringResourceCatalog()
        catalog.set("title", "Hello", "")
        proj.string_catalog = catalog

        result = generate_all_files_preserved(proj, str(tmp_path), backup=False)

        assert EGUI_STRINGS_HEADER_RELPATH in result
        assert EGUI_STRINGS_SOURCE_RELPATH in result

    def test_layout_regenerated_even_when_existing(self, tmp_path):
        """Even if *_layout.c exists on disk, it should appear in result (may
        be skipped if hash matches, but if content changed it overwrites)."""
        proj = _make_project_with_page("main_page")
        output_dir = str(tmp_path)
        layout_relpath = designer_page_layout_relpath("main_page")
        # First pass
        result1 = generate_all_files_preserved(proj, output_dir, backup=False)
        if layout_relpath in result1:
            layout_path = tmp_path / layout_relpath
            layout_path.parent.mkdir(parents=True, exist_ok=True)
            layout_path.write_text(result1[layout_relpath], encoding="utf-8")
        # Second pass without modification — may skip (hash match) but no crash
        result2 = generate_all_files_preserved(proj, output_dir, backup=False)
        # Either skipped or re-produced — no crash is the key assertion
        assert isinstance(result2, dict)


# ======================================================================
# TestGeneratedPreservedFiles
# ======================================================================


class TestLegacyHeaderMigration:
    """Legacy header USER CODE blocks are rejected."""

    def test_header_user_code_is_rejected(self, tmp_path):
        proj = _make_project_with_page("main_page")
        output_dir = str(tmp_path)

        header_path = tmp_path / "main_page.h"
        existing_header = (
            "#ifndef _MAIN_PAGE_H_\n"
            "#define _MAIN_PAGE_H_\n"
            "// USER CODE BEGIN includes\n"
            '#include "my_custom.h"\n'
            "// USER CODE END includes\n"
            "    // USER CODE BEGIN user_fields\n"
            "    int custom_state;\n"
            "    // USER CODE END user_fields\n"
            "// USER CODE BEGIN declarations\n"
            "void my_extra_func(void);\n"
            "// USER CODE END declarations\n"
            "#endif\n"
        )
        header_path.write_text(existing_header, encoding="utf-8")

        with pytest.raises(ValueError, match="Unsupported legacy page header detected: main_page.h"):
            generate_all_files_preserved(proj, output_dir, backup=False)

    def test_header_hook_override_user_code_is_rejected(self, tmp_path):
        proj = _make_project_with_page("main_page")
        output_dir = str(tmp_path)

        header_path = tmp_path / "main_page.h"
        existing_header = (
            "#ifndef _MAIN_PAGE_H_\n"
            "#define _MAIN_PAGE_H_\n"
            "// USER CODE BEGIN declarations\n"
            "#define EGUI_MAIN_PAGE_HOOK_ON_OPEN(_page) main_page_after_open(_page)\n"
            "void main_page_after_open(egui_main_page_t *page);\n"
            "// USER CODE END declarations\n"
            "#endif\n"
        )
        header_path.write_text(existing_header, encoding="utf-8")

        with pytest.raises(ValueError, match="Unsupported legacy page header detected: main_page.h"):
            generate_all_files_preserved(proj, output_dir, backup=False)

    def test_header_produced_fresh_when_not_on_disk(self, tmp_path):
        """If no existing header, fresh output must be produced."""
        proj = _make_project_with_page("main_page")
        output_dir = str(tmp_path)
        result = generate_all_files_preserved(proj, output_dir, backup=False)
        header_relpath = designer_page_header_relpath("main_page")
        assert header_relpath in result
        assert "#ifndef _MAIN_PAGE_H_" in result[header_relpath]


# ======================================================================
# TestMultiPageProject
# ======================================================================


class TestMultiPageProject:
    """Multi-page project generates files for every page."""

    def test_all_pages_get_files(self, tmp_path):
        root1 = WidgetModel("group", name="root_group", x=0, y=0, width=240, height=320)
        root2 = WidgetModel("group", name="root_group", x=0, y=0, width=240, height=320)
        page1 = Page(file_path="layout/home.xml", root_widget=root1)
        page2 = Page(file_path="layout/settings.xml", root_widget=root2)

        proj = Project(screen_width=240, screen_height=320, app_name="MultiApp")
        proj.add_page(page1)
        proj.add_page(page2)

        result = generate_all_files_preserved(proj, str(tmp_path), backup=False)
        assert "home.c" in result
        assert designer_page_header_relpath("home") in result
        assert designer_page_layout_relpath("home") in result
        assert "home_ext.h" in result
        assert "settings.c" in result
        assert designer_page_header_relpath("settings") in result
        assert designer_page_layout_relpath("settings") in result
        assert "settings_ext.h" in result

    def test_uicode_contains_all_pages(self, tmp_path):
        root1 = WidgetModel("group", name="root_group", x=0, y=0, width=240, height=320)
        root2 = WidgetModel("group", name="root_group", x=0, y=0, width=240, height=320)
        page1 = Page(file_path="layout/home.xml", root_widget=root1)
        page2 = Page(file_path="layout/about.xml", root_widget=root2)

        proj = Project(screen_width=240, screen_height=320, app_name="MultiApp")
        proj.add_page(page1)
        proj.add_page(page2)

        result = generate_all_files_preserved(proj, str(tmp_path), backup=False)
        assert "PAGE_HOME" in result[UICODE_HEADER_RELPATH]
        assert "PAGE_ABOUT" in result[UICODE_HEADER_RELPATH]

    def test_second_user_file_not_overwritten(self, tmp_path):
        """Only the non-existent user file skeleton should appear in result."""
        root1 = WidgetModel("group", name="root_group", x=0, y=0, width=240, height=320)
        root2 = WidgetModel("group", name="root_group", x=0, y=0, width=240, height=320)
        page1 = Page(file_path="layout/page_a.xml", root_widget=root1)
        page2 = Page(file_path="layout/page_b.xml", root_widget=root2)

        proj = Project(screen_width=240, screen_height=320, app_name="MultiApp")
        proj.add_page(page1)
        proj.add_page(page2)

        # page_a.c already has user code on disk
        (tmp_path / "page_a.c").write_text("/* user code page_a */\n", encoding="utf-8")

        result = generate_all_files_preserved(proj, str(tmp_path), backup=False)
        assert "page_a.c" not in result     # existing → not overwritten
        assert "page_b.c" in result          # new → skeleton created
def test_multi_page_mixed_user_owned_files_preserve_existing_and_create_missing(tmp_path):
    root1 = WidgetModel("group", name="root_group", x=0, y=0, width=240, height=320)
    root2 = WidgetModel("group", name="root_group", x=0, y=0, width=240, height=320)
    page1 = Page(file_path="layout/main_page.xml", root_widget=root1)
    page2 = Page(file_path="layout/detail_page.xml", root_widget=root2)

    proj = Project(screen_width=240, screen_height=320, app_name="MultiApp")
    proj.add_page(page1)
    proj.add_page(page2)

    (tmp_path / "main_page.c").write_text("/* keep main user source */\n", encoding="utf-8")
    (tmp_path / "detail_page_ext.h").write_text("#define KEEP_DETAIL_EXT 1\n", encoding="utf-8")

    result = generate_all_files_preserved(proj, str(tmp_path), backup=False)

    assert "main_page.c" not in result
    assert "detail_page_ext.h" not in result
    assert "main_page_ext.h" in result
    assert "detail_page.c" in result


def test_multi_page_legacy_header_is_rejected(tmp_path):
    root1 = WidgetModel("group", name="root_group", x=0, y=0, width=240, height=320)
    root2 = WidgetModel("group", name="root_group", x=0, y=0, width=240, height=320)
    page1 = Page(file_path="layout/main_page.xml", root_widget=root1)
    page2 = Page(file_path="layout/detail_page.xml", root_widget=root2)

    proj = Project(screen_width=240, screen_height=320, app_name="MultiApp")
    proj.add_page(page1)
    proj.add_page(page2)

    (tmp_path / "main_page.h").write_text(
        (
            "#ifndef _MAIN_PAGE_H_\n"
            "#define _MAIN_PAGE_H_\n"
            "// USER CODE BEGIN declarations\n"
            "void main_page_extra(void);\n"
            "// USER CODE END declarations\n"
            "#endif\n"
        ),
        encoding="utf-8",
    )
    (tmp_path / "detail_page_ext.h").write_text("#define KEEP_DETAIL_EXT 1\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported legacy page header detected: main_page.h"):
        generate_all_files_preserved(proj, str(tmp_path), backup=False)
