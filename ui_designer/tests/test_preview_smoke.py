"""Tests for the UI Designer live preview smoke helpers."""

import os
from pathlib import Path

from ui_designer_preview_smoke import (
    APP_NAME,
    DEFAULT_WORK_ROOT,
    PAGE_NAME,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    build_materialized_smoke_project,
    build_main_page_user_source,
    build_smoke_project,
    default_work_dir_root,
    extract_region,
)


class TestPreviewSmokeHelpers:
    def test_extract_region_returns_expected_rgb888_slice(self):
        width = 4
        height = 3
        frame = bytes(range(width * height * 3))

        region = extract_region(frame, width, 1, 1, 2, 2)

        expected = b"".join(
            frame[(row * width + 1) * 3:(row * width + 3) * 3]
            for row in (1, 2)
        )
        assert region == expected

    def test_build_smoke_project_creates_expected_widgets_and_metadata(self):
        project, page, meta = build_smoke_project(
            APP_NAME,
            "D:/sdk",
            "D:/workspace/DesignerPreviewSmoke",
        )

        assert project.screen_width == SCREEN_WIDTH
        assert project.screen_height == SCREEN_HEIGHT
        assert project.startup_page == PAGE_NAME
        widgets = {widget.name: widget for widget in page.get_all_widgets()}

        assert "status_label" in widgets
        assert widgets["action_button"].on_click == "smoke_on_action_button_click"
        assert widgets["animated_chip"].animations[0].anim_type == "translate"
        assert meta["button_center"] == (120, 130)
        assert meta["status_region"] == (20, 62, 200, 28)

    def test_build_main_page_user_source_wires_callback_and_text_updates(self):
        _project, page, _meta = build_smoke_project(
            APP_NAME,
            "D:/sdk",
            str(Path("D:/workspace") / APP_NAME),
        )

        source = build_main_page_user_source(page)

        assert "void smoke_on_action_button_click(egui_view_t *self)" in source
        assert '"Status: click ok"' in source
        assert '"Verified"' in source
        assert f"void {page.c_prefix}_user_init({page.c_struct_name} *page)" in source

    def test_build_materialized_smoke_project_writes_scaffold_and_user_source(self, tmp_path):
        project_dir = tmp_path / APP_NAME

        project, page, meta, materialized = build_materialized_smoke_project(
            "D:/sdk",
            str(project_dir),
        )

        assert project.project_dir == str(project_dir)
        assert project.sdk_root == os.path.normpath("D:/sdk")
        assert page.name == PAGE_NAME
        assert meta["status_region"] == (20, 62, 200, 28)
        assert (project_dir / f"{APP_NAME}.egui").is_file()
        assert (project_dir / ".designer" / f"{PAGE_NAME}.h").is_file()
        assert (project_dir / ".designer" / f"{PAGE_NAME}_layout.c").is_file()
        source = (project_dir / f"{PAGE_NAME}.c").read_text(encoding="utf-8")
        assert "void smoke_on_action_button_click(egui_view_t *self)" in source
        assert '"Status: click ok"' in source
        assert "main_page_ext.h" in materialized.files

    def test_default_work_dir_root_uses_repo_temp_directory(self):
        assert default_work_dir_root() == DEFAULT_WORK_ROOT
