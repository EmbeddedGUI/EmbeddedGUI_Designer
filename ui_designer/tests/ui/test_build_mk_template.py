"""Tests for split user/designer scaffold content generators."""

import pytest


class TestBuildMkContent:
    @pytest.fixture
    def wrapper(self):
        from ui_designer.utils.scaffold import make_app_build_mk_content

        return make_app_build_mk_content("MyTestApp")

    @pytest.fixture
    def designer(self):
        from ui_designer.utils.scaffold import make_app_build_designer_mk_content

        return make_app_build_designer_mk_content("MyTestApp")

    def test_wrapper_includes_designer_file(self, wrapper):
        from ui_designer.utils.scaffold import BUILD_DESIGNER_RELPATH

        assert "MyTestApp" in wrapper
        assert "build_designer.mk" in wrapper
        assert f"include $(EGUI_APP_PATH)/{BUILD_DESIGNER_RELPATH}" in wrapper
        assert "EGUI_CODE_SRC" not in wrapper
        assert "EGUI_CODE_INCLUDE" not in wrapper

    def test_designer_file_contains_build_paths(self, designer):
        assert "EGUI_CODE_SRC" in designer
        assert "EGUI_CODE_INCLUDE" in designer
        assert "$(EGUI_APP_PATH)/.designer" in designer
        assert "$(EGUI_APP_PATH)/resource/img" in designer
        assert "$(EGUI_APP_PATH)/resource/font" in designer
        assert "-I$(EGUI_APP_PATH)" not in designer

    def test_migrate_legacy_build_mk_preserves_custom_lines(self):
        from ui_designer.utils.scaffold import BUILD_DESIGNER_RELPATH, migrate_app_build_mk_content

        migrated = migrate_app_build_mk_content(
            (
                "# legacy build\n"
                "EGUI_CODE_SRC += $(EGUI_APP_PATH)\n"
                "EGUI_CODE_INCLUDE += $(EGUI_APP_PATH)\n"
                "USER_CFLAGS += -DAPP_FLAG=1\n"
            ),
            "LegacyApp",
        )

        assert f"include $(EGUI_APP_PATH)/{BUILD_DESIGNER_RELPATH}" in migrated
        assert "USER_CFLAGS += -DAPP_FLAG=1" in migrated
        assert "EGUI_CODE_SRC += $(EGUI_APP_PATH)" not in migrated
        assert "EGUI_CODE_INCLUDE += $(EGUI_APP_PATH)" not in migrated

    def test_migrate_rewrites_legacy_designer_include_path(self):
        from ui_designer.utils.scaffold import BUILD_DESIGNER_RELPATH, migrate_app_build_mk_content

        migrated = migrate_app_build_mk_content(
            (
                "include $(EGUI_APP_PATH)/build_designer.mk\n"
                "USER_CFLAGS += -DAPP_FLAG=1\n"
            ),
            "LegacyApp",
        )

        assert f"include $(EGUI_APP_PATH)/{BUILD_DESIGNER_RELPATH}" in migrated
        assert "include $(EGUI_APP_PATH)/build_designer.mk" not in migrated
        assert "USER_CFLAGS += -DAPP_FLAG=1" in migrated

    def test_migrate_is_idempotent_for_existing_wrapper_header(self):
        from ui_designer.utils.scaffold import migrate_app_build_mk_content

        existing = (
            "# User build overrides for LegacyApp\n\n"
            "include $(EGUI_APP_PATH)/.designer/build_designer.mk\n\n"
            "# keep me\n"
        )

        migrated = migrate_app_build_mk_content(existing, "LegacyApp")

        assert migrated == existing

    def test_build_wrapper_detection_ignores_legacy_root_include(self):
        from ui_designer.utils.scaffold import build_mk_designer_include_target

        assert build_mk_designer_include_target("include $(EGUI_APP_PATH)/build_designer.mk\n") == ""


class TestAppConfigContent:
    @pytest.fixture
    def wrapper(self):
        from ui_designer.utils.scaffold import make_app_config_h_content

        return make_app_config_h_content("TestApp")

    @pytest.fixture
    def designer(self):
        from ui_designer.utils.scaffold import make_app_config_designer_h_content

        return make_app_config_designer_h_content("TestApp", 240, 320)

    def test_wrapper_uses_designer_include(self, wrapper):
        from ui_designer.utils.scaffold import APP_CONFIG_DESIGNER_RELPATH

        assert "#ifndef _APP_EGUI_CONFIG_H_" in wrapper
        assert f'#include "{APP_CONFIG_DESIGNER_RELPATH}"' in wrapper
        assert "EGUI_CONFIG_SCREEN_WIDTH" not in wrapper

    def test_designer_file_has_default_macros(self, designer):
        assert "#ifndef _APP_EGUI_CONFIG_DESIGNER_H_" in designer
        assert "EGUI_CONFIG_SCREEN_WIDTH  240" in designer
        assert "EGUI_CONFIG_SCREEN_HEIGHT 320" in designer
        assert "EGUI_CONFIG_PFB_WIDTH  (EGUI_CONFIG_SCREEN_WIDTH / 8)" in designer
        assert "EGUI_CONFIG_PFB_HEIGHT (EGUI_CONFIG_SCREEN_HEIGHT / 8)" in designer
        assert "EGUI_CONFIG_FUNCTION_SUPPORT_MASK 1" in designer

    def test_designer_file_emits_multi_display_macros(self):
        from ui_designer.utils.scaffold import make_app_config_designer_h_content

        designer = make_app_config_designer_h_content(
            "TestApp",
            240,
            320,
            displays=[
                {"width": 240, "height": 320},
                {"width": 128, "height": 64, "pfb_width": 12, "pfb_height": 7},
            ],
        )

        assert "EGUI_CONFIG_MAX_DISPLAY_COUNT 2" in designer
        assert "EGUI_CONFIG_SCREEN_1_WIDTH  128" in designer
        assert "EGUI_CONFIG_SCREEN_1_HEIGHT 64" in designer
        assert "EGUI_CONFIG_PFB_1_WIDTH    12" in designer
        assert "EGUI_CONFIG_PFB_1_HEIGHT   7" in designer

    def test_designer_file_emits_custom_primary_pfb_macros(self):
        from ui_designer.utils.scaffold import make_app_config_designer_h_content

        designer = make_app_config_designer_h_content(
            "TestApp",
            240,
            320,
            displays=[
                {"width": 240, "height": 320, "pfb_width": 20, "pfb_height": 24},
            ],
        )

        assert "EGUI_CONFIG_PFB_WIDTH  20" in designer
        assert "EGUI_CONFIG_PFB_HEIGHT 24" in designer

    def test_migrate_config_preserves_custom_override_only(self):
        from ui_designer.utils.scaffold import APP_CONFIG_DESIGNER_RELPATH, migrate_app_config_h_content

        migrated = migrate_app_config_h_content(
            (
                "#ifndef _APP_EGUI_CONFIG_H_\n"
                "#define _APP_EGUI_CONFIG_H_\n"
                "#define EGUI_CONFIG_SCREEN_WIDTH  240\n"
                "#define EGUI_CONFIG_SCREEN_HEIGHT 320\n"
                "#define EGUI_CONFIG_PFB_WIDTH    30\n"
                "#define EGUI_CONFIG_PFB_HEIGHT   40\n"
                "#define EGUI_CONFIG_DEBUG_LOG_LEVEL EGUI_LOG_IMPL_LEVEL_INF\n"
                "#endif\n"
            ),
            "LegacyApp",
            240,
            320,
        )

        assert f'#include "{APP_CONFIG_DESIGNER_RELPATH}"' in migrated
        assert "EGUI_CONFIG_DEBUG_LOG_LEVEL" in migrated
        assert "EGUI_CONFIG_SCREEN_WIDTH" not in migrated
        assert "EGUI_CONFIG_SCREEN_HEIGHT" not in migrated
        assert "EGUI_CONFIG_PFB_WIDTH" not in migrated
        assert "EGUI_CONFIG_PFB_HEIGHT" not in migrated

    def test_migrate_legacy_typo_config_preserves_custom_override_only(self):
        from ui_designer.utils.scaffold import APP_CONFIG_DESIGNER_RELPATH, migrate_app_config_h_content

        migrated = migrate_app_config_h_content(
            (
                "#ifndef _APP_EGUI_CONFIG_H_\n"
                "#define _APP_EGUI_CONFIG_H_\n"
                "#define EGUI_CONFIG_SCEEN_WIDTH  240\n"
                "#define EGUI_CONFIG_SCEEN_HEIGHT 320\n"
                "#define EGUI_CONFIG_PFB_WIDTH    (EGUI_CONFIG_SCEEN_WIDTH / 8)\n"
                "#define EGUI_CONFIG_PFB_HEIGHT   (EGUI_CONFIG_SCEEN_HEIGHT / 8)\n"
                "#define CUSTOM_FLAG 1\n"
                "#endif\n"
            ),
            "LegacyApp",
            240,
            320,
        )

        assert f'#include "{APP_CONFIG_DESIGNER_RELPATH}"' in migrated
        assert "#define CUSTOM_FLAG 1" in migrated
        assert "EGUI_CONFIG_SCEEN_WIDTH" not in migrated
        assert "EGUI_CONFIG_SCEEN_HEIGHT" not in migrated
        assert "EGUI_CONFIG_PFB_WIDTH" not in migrated
        assert "EGUI_CONFIG_PFB_HEIGHT" not in migrated

    def test_migrate_multi_display_config_preserves_only_user_overrides(self):
        from ui_designer.utils.scaffold import APP_CONFIG_DESIGNER_RELPATH, migrate_app_config_h_content

        migrated = migrate_app_config_h_content(
            (
                "#ifndef _APP_EGUI_CONFIG_H_\n"
                "#define _APP_EGUI_CONFIG_H_\n"
                "#define EGUI_CONFIG_MAX_DISPLAY_COUNT 2\n"
                "#define EGUI_CONFIG_SCREEN_WIDTH  240\n"
                "#define EGUI_CONFIG_SCREEN_HEIGHT 320\n"
                "#define EGUI_CONFIG_PFB_WIDTH    30\n"
                "#define EGUI_CONFIG_PFB_HEIGHT   40\n"
                "#define EGUI_CONFIG_SCREEN_1_WIDTH  128\n"
                "#define EGUI_CONFIG_SCREEN_1_HEIGHT 64\n"
                "#define EGUI_CONFIG_PFB_1_WIDTH    12\n"
                "#define EGUI_CONFIG_PFB_1_HEIGHT   7\n"
                "#define CUSTOM_FLAG 1\n"
                "#endif\n"
            ),
            "LegacyApp",
            240,
            320,
            displays=[
                {"width": 240, "height": 320},
                {"width": 128, "height": 64, "pfb_width": 12, "pfb_height": 7},
            ],
        )

        assert f'#include "{APP_CONFIG_DESIGNER_RELPATH}"' in migrated
        assert "#define CUSTOM_FLAG 1" in migrated
        assert "EGUI_CONFIG_MAX_DISPLAY_COUNT" not in migrated
        assert "EGUI_CONFIG_SCREEN_1_WIDTH" not in migrated
        assert "EGUI_CONFIG_PFB_1_HEIGHT" not in migrated

    def test_migrate_legacy_config_keeps_user_conditional_blocks(self):
        from ui_designer.utils.scaffold import migrate_app_config_h_content

        migrated = migrate_app_config_h_content(
            (
                "#ifndef _APP_EGUI_CONFIG_H_\n"
                "#define _APP_EGUI_CONFIG_H_\n"
                "#if defined(ENABLE_TRACE)\n"
                "#define EGUI_CONFIG_DEBUG_LOG_LEVEL EGUI_LOG_IMPL_LEVEL_DBG\n"
                "#endif\n"
                "#endif\n"
            ),
            "LegacyApp",
            240,
            320,
        )

        assert "#if defined(ENABLE_TRACE)" in migrated
        assert "#define EGUI_CONFIG_DEBUG_LOG_LEVEL EGUI_LOG_IMPL_LEVEL_DBG" in migrated
        assert migrated.count("#endif") >= 2

    def test_migrate_rewrites_legacy_config_include_path(self):
        from ui_designer.utils.scaffold import APP_CONFIG_DESIGNER_RELPATH, migrate_app_config_h_content

        migrated = migrate_app_config_h_content(
            (
                "#ifndef _APP_EGUI_CONFIG_H_\n"
                "#define _APP_EGUI_CONFIG_H_\n"
                '#include "app_egui_config_designer.h"\n'
                "#define CUSTOM_FLAG 1\n"
                "#endif\n"
            ),
            "LegacyApp",
            240,
            320,
        )

        assert f'#include "{APP_CONFIG_DESIGNER_RELPATH}"' in migrated
        assert '#include "app_egui_config_designer.h"' not in migrated
        assert "#define CUSTOM_FLAG 1" in migrated

    def test_migrate_config_is_idempotent_for_existing_wrapper_comment(self):
        from ui_designer.utils.scaffold import migrate_app_config_h_content

        existing = (
            "#ifndef _APP_EGUI_CONFIG_H_\n"
            "#define _APP_EGUI_CONFIG_H_\n\n"
            "#define CUSTOM_FLAG 1\n\n"
            "/* Define user overrides above the Designer include. */\n"
            '#include ".designer/app_egui_config_designer.h"\n\n'
            "#endif /* _APP_EGUI_CONFIG_H_ */\n"
        )

        migrated = migrate_app_config_h_content(existing, "LegacyApp", 240, 320)

        assert migrated == existing

    def test_config_wrapper_detection_ignores_legacy_root_include(self):
        from ui_designer.utils.scaffold import app_config_designer_include_target

        assert app_config_designer_include_target('#include "app_egui_config_designer.h"\n') == ""

    def test_read_dimensions_follows_designer_include(self, tmp_path):
        from ui_designer.utils.scaffold import APP_CONFIG_DESIGNER_RELPATH, read_app_config_dimensions

        config_h = tmp_path / "app_egui_config.h"
        config_h.write_text(
            f'#include "{APP_CONFIG_DESIGNER_RELPATH}"\n',
            encoding="utf-8",
        )
        (tmp_path / ".designer").mkdir(exist_ok=True)
        (tmp_path / APP_CONFIG_DESIGNER_RELPATH).write_text(
            "#define EGUI_CONFIG_SCREEN_WIDTH  480\n"
            "#define EGUI_CONFIG_SCREEN_HEIGHT 272\n",
            encoding="utf-8",
        )

        assert read_app_config_dimensions(str(config_h)) == (480, 272)

    def test_read_dimensions_prefers_wrapper_override(self, tmp_path):
        from ui_designer.utils.scaffold import APP_CONFIG_DESIGNER_RELPATH, read_app_config_dimensions

        config_h = tmp_path / "app_egui_config.h"
        config_h.write_text(
            (
                "#define EGUI_CONFIG_SCREEN_WIDTH  320\n"
                f'#include "{APP_CONFIG_DESIGNER_RELPATH}"\n'
            ),
            encoding="utf-8",
        )
        (tmp_path / ".designer").mkdir(exist_ok=True)
        (tmp_path / APP_CONFIG_DESIGNER_RELPATH).write_text(
            "#define EGUI_CONFIG_SCREEN_WIDTH  480\n"
            "#define EGUI_CONFIG_SCREEN_HEIGHT 272\n",
            encoding="utf-8",
        )

        assert read_app_config_dimensions(str(config_h)) == (320, 272)

    def test_read_dimensions_ignores_legacy_root_designer_header(self, tmp_path):
        from ui_designer.utils.scaffold import read_app_config_dimensions

        config_h = tmp_path / "app_egui_config.h"
        config_h.write_text(
            '#include "app_egui_config_designer.h"\n',
            encoding="utf-8",
        )
        (tmp_path / "app_egui_config_designer.h").write_text(
            "#define EGUI_CONFIG_SCREEN_WIDTH  400\n"
            "#define EGUI_CONFIG_SCREEN_HEIGHT 300\n",
            encoding="utf-8",
        )

        assert read_app_config_dimensions(str(config_h)) == (240, 320)

    def test_read_displays_resolves_multi_display_macros_and_wrapper_overrides(self, tmp_path):
        from ui_designer.utils.scaffold import APP_CONFIG_DESIGNER_RELPATH, read_app_config_displays

        config_h = tmp_path / "app_egui_config.h"
        config_h.write_text(
            (
                "#define EGUI_CONFIG_SCREEN_WIDTH  320\n"
                "#define EGUI_CONFIG_PFB_1_WIDTH 10\n"
                f'#include "{APP_CONFIG_DESIGNER_RELPATH}"\n'
            ),
            encoding="utf-8",
        )
        (tmp_path / ".designer").mkdir(exist_ok=True)
        (tmp_path / APP_CONFIG_DESIGNER_RELPATH).write_text(
            (
                "#define EGUI_CONFIG_SCREEN_WIDTH  480\n"
                "#define EGUI_CONFIG_SCREEN_HEIGHT 272\n"
                "#define EGUI_CONFIG_PFB_WIDTH  (EGUI_CONFIG_SCREEN_WIDTH / 8)\n"
                "#define EGUI_CONFIG_PFB_HEIGHT (EGUI_CONFIG_SCREEN_HEIGHT / 8)\n"
                "#define EGUI_CONFIG_MAX_DISPLAY_COUNT 2\n"
                "#define EGUI_CONFIG_SCREEN_1_WIDTH  128\n"
                "#define EGUI_CONFIG_SCREEN_1_HEIGHT 64\n"
                "#define EGUI_CONFIG_PFB_1_WIDTH    (EGUI_CONFIG_SCREEN_1_WIDTH / 8)\n"
                "#define EGUI_CONFIG_PFB_1_HEIGHT   (EGUI_CONFIG_SCREEN_1_HEIGHT / 8)\n"
            ),
            encoding="utf-8",
        )

        assert read_app_config_displays(str(config_h)) == [
            {"id": 0, "width": 320, "height": 272, "pfb_width": 40, "pfb_height": 34},
            {"id": 1, "width": 128, "height": 64, "pfb_width": 10, "pfb_height": 8},
        ]
