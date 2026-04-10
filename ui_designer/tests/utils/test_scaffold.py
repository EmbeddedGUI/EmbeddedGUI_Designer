from ui_designer.utils.scaffold import (
    DESIGNER_CODEGEN_STALE_STRING_RELPATHS,
    legacy_designer_codegen_cleanup_relpaths,
)


class TestLegacyDesignerCodegenCleanupRelpaths:
    def test_maps_designer_outputs_to_legacy_root_cleanup_paths(self):
        cleanup = legacy_designer_codegen_cleanup_relpaths(
            {
                ".designer/main_page.h": "",
                ".designer/main_page_layout.c": "",
                ".designer/uicode.h": "",
                ".designer/uicode.c": "",
                ".designer/build_designer.mk": "",
                ".designer/app_egui_config_designer.h": "",
                "main_page.c": "",
            }
        )

        assert cleanup == (
            "app_egui_config_designer.h",
            "build_designer.mk",
            "main_page.h",
            "main_page_layout.c",
            "uicode.c",
            "uicode.h",
        )

    def test_adds_stale_string_cleanup_when_string_outputs_are_absent(self):
        cleanup = legacy_designer_codegen_cleanup_relpaths(
            [".designer/uicode.c", ".designer/uicode.h"],
            remove_stale_strings=True,
        )

        assert cleanup == (
            ".designer/egui_strings.c",
            ".designer/egui_strings.h",
            "egui_strings.c",
            "egui_strings.h",
            "uicode.c",
            "uicode.h",
        )

    def test_string_outputs_clean_root_copies_without_duplicate_entries(self):
        cleanup = legacy_designer_codegen_cleanup_relpaths(
            [
                ".designer/uicode.c",
                ".designer/uicode.h",
                ".designer/egui_strings.h",
                ".designer/egui_strings.c",
            ],
            remove_stale_strings=True,
        )

        assert cleanup == (
            "egui_strings.c",
            "egui_strings.h",
            "uicode.c",
            "uicode.h",
        )
        assert ".designer/egui_strings.h" not in cleanup
        assert ".designer/egui_strings.c" not in cleanup
        assert {
            DESIGNER_CODEGEN_STALE_STRING_RELPATHS[2],
            DESIGNER_CODEGEN_STALE_STRING_RELPATHS[3],
        }.issubset(set(cleanup))
