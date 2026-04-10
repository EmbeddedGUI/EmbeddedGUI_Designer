"""Tests for the UI Designer live preview smoke helpers."""

import json
from pathlib import Path

from ui_designer_preview_smoke import (
    APP_NAME,
    DEFAULT_WORK_ROOT,
    PAGE_NAME,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    _scaffold_app_directory,
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
        project, meta = build_smoke_project(APP_NAME, "D:/sdk", "D:/workspace/DesignerPreviewSmoke")

        assert project.screen_width == SCREEN_WIDTH
        assert project.screen_height == SCREEN_HEIGHT
        assert project.startup_page == PAGE_NAME
        page = project.get_startup_page()
        assert page is not None
        widgets = {widget.name: widget for widget in page.get_all_widgets()}

        assert "status_label" in widgets
        assert widgets["action_button"].on_click == "smoke_on_action_button_click"
        assert widgets["animated_chip"].animations[0].anim_type == "translate"
        assert meta["button_center"] == (120, 130)
        assert meta["status_region"] == (20, 62, 200, 28)

    def test_build_main_page_user_source_wires_callback_and_text_updates(self):
        project, _ = build_smoke_project(APP_NAME, "D:/sdk", str(Path("D:/workspace") / APP_NAME))
        page = project.get_startup_page()
        assert page is not None

        source = build_main_page_user_source(page)

        assert "void smoke_on_action_button_click(egui_view_t *self)" in source
        assert '"Status: click ok"' in source
        assert '"Verified"' in source
        assert f"void {page.c_prefix}_user_init({page.c_struct_name} *page)" in source

    def test_default_work_dir_root_uses_repo_temp_directory(self):
        assert default_work_dir_root() == DEFAULT_WORK_ROOT

    def test_scaffold_app_directory_creates_missing_wrappers(self, tmp_path):
        app_dir = tmp_path / APP_NAME

        _scaffold_app_directory(app_dir, APP_NAME)

        assert (app_dir / "build.mk").is_file()
        assert (app_dir / "app_egui_config.h").is_file()
        assert (app_dir / ".designer" / "build_designer.mk").is_file()
        assert (app_dir / ".designer" / "app_egui_config_designer.h").is_file()
        assert (app_dir / "resource" / "src" / "app_resource_config.json").is_file()
        assert (app_dir / "resource" / "src" / ".designer" / "app_resource_config_designer.json").is_file()

    def test_scaffold_app_directory_preserves_user_wrappers_and_overlay(self, tmp_path):
        app_dir = tmp_path / APP_NAME
        resource_src = app_dir / "resource" / "src"
        designer_dir = app_dir / ".designer"
        resource_src.mkdir(parents=True)
        designer_dir.mkdir(parents=True)

        (app_dir / "build.mk").write_text("# custom build\nEGUI_CODE_SRC += local.c\n", encoding="utf-8")
        (app_dir / "app_egui_config.h").write_text("#define USER_FLAG 1\n", encoding="utf-8")
        (resource_src / "app_resource_config.json").write_text(
            json.dumps({"img": [{"name": "user_asset"}], "font": []}),
            encoding="utf-8",
        )
        (designer_dir / "build_designer.mk").write_text("# stale\n", encoding="utf-8")
        (designer_dir / "app_egui_config_designer.h").write_text("#define STALE 1\n", encoding="utf-8")

        _scaffold_app_directory(app_dir, APP_NAME)

        build_mk = (app_dir / "build.mk").read_text(encoding="utf-8")
        config_h = (app_dir / "app_egui_config.h").read_text(encoding="utf-8")
        overlay = json.loads((resource_src / "app_resource_config.json").read_text(encoding="utf-8"))
        designer_build = (designer_dir / "build_designer.mk").read_text(encoding="utf-8")
        designer_config = (designer_dir / "app_egui_config_designer.h").read_text(encoding="utf-8")

        assert "# custom build" in build_mk
        assert "EGUI_CODE_SRC += local.c" in build_mk
        assert ".designer/build_designer.mk" in build_mk
        assert "#define USER_FLAG 1" in config_h
        assert '#include ".designer/app_egui_config_designer.h"' in config_h
        assert overlay == {"img": [{"name": "user_asset"}], "font": []}
        assert "Designer-managed build inputs" in designer_build
        assert "# stale" not in designer_build
        assert "STALE" not in designer_config
        assert f"#define EGUI_CONFIG_SCEEN_WIDTH  {SCREEN_WIDTH}" in designer_config
        assert f"#define EGUI_CONFIG_SCEEN_HEIGHT {SCREEN_HEIGHT}" in designer_config

    def test_scaffold_app_directory_is_idempotent_for_migrated_user_files(self, tmp_path):
        app_dir = tmp_path / APP_NAME
        resource_src = app_dir / "resource" / "src"
        designer_dir = app_dir / ".designer"
        resource_src.mkdir(parents=True)
        designer_dir.mkdir(parents=True)

        build_mk_path = app_dir / "build.mk"
        config_h_path = app_dir / "app_egui_config.h"
        overlay_path = resource_src / "app_resource_config.json"

        build_mk_path.write_text(
            '# User build overrides for DesignerPreviewSmoke\n\n'
            'include $(EGUI_APP_PATH)/.designer/build_designer.mk\n\n'
            '# keep me\n',
            encoding="utf-8",
        )
        config_h_path.write_text(
            "#ifndef _APP_EGUI_CONFIG_H_\n"
            "#define _APP_EGUI_CONFIG_H_\n\n"
            "#define USER_FLAG 1\n\n"
            '/* Define user overrides above the Designer include. */\n'
            '#include ".designer/app_egui_config_designer.h"\n\n'
            "#endif /* _APP_EGUI_CONFIG_H_ */\n",
            encoding="utf-8",
        )
        overlay_path.write_text(
            json.dumps({"img": [{"name": "user_asset"}], "font": [{"name": "font_keep"}]}),
            encoding="utf-8",
        )

        _scaffold_app_directory(app_dir, APP_NAME)
        first_build = build_mk_path.read_text(encoding="utf-8")
        first_config = config_h_path.read_text(encoding="utf-8")
        first_overlay = overlay_path.read_text(encoding="utf-8")

        _scaffold_app_directory(app_dir, APP_NAME)
        second_build = build_mk_path.read_text(encoding="utf-8")
        second_config = config_h_path.read_text(encoding="utf-8")
        second_overlay = overlay_path.read_text(encoding="utf-8")

        assert first_build == second_build
        assert first_config == second_config
        assert first_overlay == second_overlay
        assert second_build.count(".designer/build_designer.mk") == 1
        assert second_config.count('.designer/app_egui_config_designer.h') == 1
