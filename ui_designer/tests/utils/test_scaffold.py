import json
import os
from pathlib import Path

import pytest

from ui_designer.utils.scaffold import (
    APP_CONFIG_DESIGNER_RELPATH,
    APP_CONFIG_RELPATH,
    BACKUP_DIR_RELPATH,
    BUILD_DESIGNER_RELPATH,
    BUILD_MK_RELPATH,
    DESIGNER_RESOURCE_CONFIG_RELPATH,
    DESIGNER_CODEGEN_STALE_STRING_RELPATHS,
    EGUIPROJECT_DIRNAME,
    MOCKUP_DIR_RELPATH,
    ORPHANED_USER_CODE_DIR_RELPATH,
    REFERENCE_FRAMES_DIR_RELPATH,
    RELEASE_CONFIG_RELPATH,
    REGRESSION_REPORT_RELPATH,
    REGRESSION_RESULTS_RELPATH,
    RESOURCE_CATALOG_RELPATH,
    RESOURCE_CATALOG_FILENAME,
    RESOURCE_CONFIG_RELPATH,
    RESOURCE_DIR_RELPATH,
    RESOURCE_SRC_DIR_RELPATH,
    SUPPORTED_TEXT_RELPATH,
    add_page_widget,
    add_widget_children,
    apply_designer_project_scaffold,
    bind_project_storage,
    build_basic_widget_model,
    build_page_model_from_root,
    build_page_model_from_root_with_widgets,
    build_page_model_only_with_widget,
    build_page_model_root_with_widgets,
    build_page_model_with_root_widget,
    build_project_model_and_page_with_widget,
    build_project_model_and_page_with_widgets,
    build_project_model_and_root_with_widgets,
    build_project_model_only_with_page_widgets,
    build_project_model_only_with_widget,
    build_project_model_only_with_widgets,
    build_project_model_with_page_widgets,
    build_project_model_from_pages,
    build_project_model_from_root,
    build_project_model_only_from_root_with_widgets,
    build_project_model_from_root_with_widgets,
    build_project_model_with_widget,
    build_project_model_with_widgets,
    build_page_model_with_widget,
    build_page_model_with_widgets,
    build_empty_project_model,
    build_empty_project_model_with_root,
    build_empty_project_xml,
    default_scaffold_circle_radius,
    designer_conversion_scaffold_kwargs,
    designer_scaffold_kwargs,
    generate_designer_resource_config,
    ensure_conversion_project_scaffold_with_sdk_root,
    require_page_root,
    require_project_page_root,
    normalize_scaffold_pages,
    project_config_dir,
    project_config_backup_dir,
    project_config_images_dir,
    project_config_layout_dir,
    project_config_layout_xml_relpath,
    project_config_mockup_dir,
    project_config_mockup_path,
    project_config_mockup_relpath,
    project_config_orphaned_user_code_dir,
    project_config_orphaned_user_page_dir,
    project_config_path,
    project_config_reference_frames_dir,
    project_config_regression_report_path,
    project_config_regression_results_path,
    project_config_resource_dir,
    project_app_config_path,
    project_build_mk_path,
    project_designer_resource_config_path,
    project_designer_resource_dir,
    project_file_path,
    project_generated_font_dir,
    project_generated_img_dir,
    project_generated_resource_dir,
    project_layout_xml_path,
    project_orphaned_user_page_relpath,
    project_resource_catalog_path,
    project_resource_src_dir,
    project_supported_text_path,
    project_user_resource_config_path,
    resource_catalog_path,
    generated_resource_font_dir,
    generated_resource_img_dir,
    resource_images_dir,
    resource_source_path,
    project_file_relpath,
    project_layout_xml_relpath,
    cleanup_legacy_designer_codegen_files,
    copy_project_sidecar_files,
    materialize_generated_project_files,
    materialize_project_codegen_outputs,
    prepare_project_codegen_outputs,
    save_project_model,
    save_project_and_materialize_codegen,
    save_empty_project_with_designer_scaffold,
    scaffold_conversion_project_with_sdk_root,
    scaffold_designer_project,
    ensure_designer_project_scaffold_with_sdk_root,
    scaffold_designer_project_with_sdk_root,
    save_project_with_designer_scaffold,
    sdk_example_reference_frames_dir,
    sdk_example_config_dir,
    sdk_example_layout_dir,
    sdk_example_layout_xml_path,
    sdk_example_config_resource_dir,
    sdk_example_generated_font_dir,
    sdk_example_generated_img_dir,
    sdk_example_resource_images_dir,
    sdk_example_generated_resource_dir,
    sdk_example_resource_src_dir,
    sdk_example_supported_text_path,
    sdk_example_resource_catalog_path,
    sdk_example_user_resource_config_path,
    sdk_example_designer_resource_config_path,
    sdk_example_app_config_path,
    sdk_example_build_mk_path,
    sdk_example_project_file_path,
    sdk_example_regression_report_path,
    sdk_example_regression_results_path,
    sync_project_resources_and_generate_designer_resource_config,
    sync_project_scaffold_core_files,
    legacy_designer_codegen_cleanup_relpaths,
    sync_project_scaffold_sidecars,
    write_generated_project_files,
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


class TestGeneratedProjectFileHelpers:
    def test_write_generated_project_files_creates_nested_outputs(self, tmp_path):
        project_dir = tmp_path / "GeneratedFilesDemo"

        written = write_generated_project_files(
            str(project_dir),
            {
                ".designer/uicode.c": "int generated(void) { return 1; }\n",
                "main_page.c": "// user skeleton\n",
            },
            newline="\n",
        )

        assert written == (".designer/uicode.c", "main_page.c")
        assert (project_dir / ".designer" / "uicode.c").read_text(encoding="utf-8") == (
            "int generated(void) { return 1; }\n"
        )
        assert (project_dir / "main_page.c").read_text(encoding="utf-8") == "// user skeleton\n"

    def test_cleanup_legacy_designer_codegen_files_removes_root_copies_and_stale_strings(self, tmp_path):
        project_dir = tmp_path / "CleanupDemo"
        designer_dir = project_dir / ".designer"
        designer_dir.mkdir(parents=True)
        (designer_dir / "uicode.c").write_text("// nested ui\n", encoding="utf-8")
        (designer_dir / "egui_strings.h").write_text("// stale string header\n", encoding="utf-8")
        (designer_dir / "egui_strings.c").write_text("// stale string source\n", encoding="utf-8")
        (project_dir / "uicode.c").write_text("// legacy root copy\n", encoding="utf-8")

        removed = cleanup_legacy_designer_codegen_files(
            str(project_dir),
            [".designer/uicode.c"],
            remove_stale_strings=True,
        )

        assert removed == (
            ".designer/egui_strings.c",
            ".designer/egui_strings.h",
            "uicode.c",
        )
        assert not (project_dir / "uicode.c").exists()
        assert not (designer_dir / "egui_strings.h").exists()
        assert not (designer_dir / "egui_strings.c").exists()
        assert (designer_dir / "uicode.c").is_file()

    def test_cleanup_legacy_designer_codegen_files_can_backup_removed_files(self, tmp_path):
        project_dir = tmp_path / "CleanupBackupDemo"
        designer_dir = project_dir / ".designer"
        designer_dir.mkdir(parents=True)
        (designer_dir / "uicode.c").write_text("// nested ui\n", encoding="utf-8")
        (project_dir / "uicode.c").write_text("// legacy root copy\n", encoding="utf-8")

        removed = cleanup_legacy_designer_codegen_files(
            str(project_dir),
            [".designer/uicode.c"],
            backup_existing=True,
        )

        backup_matches = list((project_dir / ".eguiproject" / "backup").glob("*/uicode.c"))

        assert removed == ("uicode.c",)
        assert not (project_dir / "uicode.c").exists()
        assert len(backup_matches) == 1

    def test_materialize_generated_project_files_writes_outputs_and_cleans_legacy_copies(self, tmp_path):
        project_dir = tmp_path / "MaterializeDemo"
        designer_dir = project_dir / ".designer"
        designer_dir.mkdir(parents=True)
        (project_dir / "uicode.c").write_text("// legacy root copy\n", encoding="utf-8")

        written, removed = materialize_generated_project_files(
            str(project_dir),
            {".designer/uicode.c": "int generated(void) { return 1; }\n"},
            [".designer/uicode.c"],
            newline="\n",
        )

        assert written == (".designer/uicode.c",)
        assert removed == ("uicode.c",)
        assert (designer_dir / "uicode.c").read_text(encoding="utf-8") == "int generated(void) { return 1; }\n"
        assert not (project_dir / "uicode.c").exists()


class TestProjectSidecarCopyHelpers:
    def test_copy_project_sidecar_files_copies_user_sidecars_and_filters_designer_resources(self, tmp_path):
        src_dir = tmp_path / "SrcDemo"
        dst_dir = tmp_path / "DstDemo"
        resource_dir = src_dir / ".eguiproject" / "resources"
        images_dir = resource_dir / "images"
        mockup_dir = src_dir / ".eguiproject" / "mockup"
        resource_src_dir = src_dir / "resource" / "src"

        images_dir.mkdir(parents=True)
        mockup_dir.mkdir(parents=True)
        resource_src_dir.mkdir(parents=True)
        dst_dir.mkdir(parents=True)

        (src_dir / "build.mk").write_text("# custom build\n", encoding="utf-8")
        (src_dir / "app_egui_config.h").write_text("#define CUSTOM_CFG 1\n", encoding="utf-8")
        (resource_src_dir / "app_resource_config.json").write_text(
            json.dumps({"img": [{"file": "legacy.png"}], "font": []}, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        (images_dir / "legacy.png").write_bytes(b"PNG")
        (images_dir / "_generated_text_preview.png").write_bytes(b"BAD")
        (resource_dir / "_generated_text_demo_16_4.txt").write_text("designer\n", encoding="utf-8")
        (resource_dir / "keep.txt").write_text("keep\n", encoding="utf-8")
        (mockup_dir / "legacy.txt").write_text("mock\n", encoding="utf-8")

        (dst_dir / "build.mk").write_text("# existing build\n", encoding="utf-8")

        copy_project_sidecar_files(str(src_dir), str(dst_dir))

        assert (dst_dir / "build.mk").read_text(encoding="utf-8") == "# existing build\n"
        assert (dst_dir / "app_egui_config.h").read_text(encoding="utf-8") == "#define CUSTOM_CFG 1\n"
        assert json.loads((dst_dir / "resource" / "src" / "app_resource_config.json").read_text(encoding="utf-8")) == {
            "img": [{"file": "legacy.png"}],
            "font": [],
        }
        assert (dst_dir / ".eguiproject" / "resources" / "images" / "legacy.png").read_bytes() == b"PNG"
        assert not (dst_dir / ".eguiproject" / "resources" / "images" / "_generated_text_preview.png").exists()
        assert not (dst_dir / ".eguiproject" / "resources" / "_generated_text_demo_16_4.txt").exists()
        assert (dst_dir / ".eguiproject" / "resources" / "keep.txt").read_text(encoding="utf-8") == "keep\n"
        assert (dst_dir / ".eguiproject" / "mockup" / "legacy.txt").read_text(encoding="utf-8") == "mock\n"


class TestSyncProjectScaffoldSidecars:
    def test_creates_missing_sidecars_and_reports_actions(self, tmp_path):
        project_dir = tmp_path / "TestApp"

        actions = sync_project_scaffold_sidecars(
            str(project_dir),
            "TestApp",
            320,
            240,
            refresh_user_wrappers=True,
            refresh_designer_resource_config=True,
        )

        assert actions[BUILD_MK_RELPATH] == "created"
        assert actions[APP_CONFIG_RELPATH] == "created"
        assert actions[BUILD_DESIGNER_RELPATH] == "created"
        assert actions[APP_CONFIG_DESIGNER_RELPATH] == "created"
        assert actions[RESOURCE_CONFIG_RELPATH] == "created"
        assert actions[DESIGNER_RESOURCE_CONFIG_RELPATH] == "created"
        assert (project_dir / "build.mk").is_file()
        assert (project_dir / "app_egui_config.h").is_file()
        assert (project_dir / ".designer" / "build_designer.mk").is_file()
        assert (project_dir / ".designer" / "app_egui_config_designer.h").is_file()
        assert (project_dir / "resource" / "src" / "app_resource_config.json").is_file()
        assert (project_dir / "resource" / "src" / ".designer" / "app_resource_config_designer.json").is_file()

    def test_migrates_wrappers_preserves_user_overlay_and_removes_legacy_files(self, tmp_path):
        project_dir = tmp_path / "LegacyApp"
        resource_src_dir = project_dir / "resource" / "src"
        designer_dir = project_dir / ".designer"
        designer_resource_dir = resource_src_dir / ".designer"

        designer_dir.mkdir(parents=True)
        designer_resource_dir.mkdir(parents=True)
        (project_dir / "build.mk").write_text("# custom build\nEGUI_CODE_SRC += local.c\n", encoding="utf-8")
        (project_dir / "app_egui_config.h").write_text("#define USER_FLAG 1\n", encoding="utf-8")
        (project_dir / "build_designer.mk").write_text("# legacy designer build\n", encoding="utf-8")
        (project_dir / "app_egui_config_designer.h").write_text("#define LEGACY_CFG 1\n", encoding="utf-8")
        (designer_dir / "build_designer.mk").write_text("# stale nested build\n", encoding="utf-8")
        (designer_dir / "app_egui_config_designer.h").write_text("#define STALE_CFG 1\n", encoding="utf-8")
        (resource_src_dir / "app_resource_config.json").write_text(
            '{"img": [{"name": "user_asset"}], "font": []}\n',
            encoding="utf-8",
        )
        (designer_resource_dir / "app_resource_config_designer.json").write_text(
            '{"img": [{"name": "stale_asset"}], "font": []}\n',
            encoding="utf-8",
        )

        actions = sync_project_scaffold_sidecars(
            str(project_dir),
            "LegacyApp",
            320,
            240,
            refresh_user_wrappers=True,
            refresh_designer_resource_config=True,
            remove_legacy_designer_files=True,
        )

        assert actions[BUILD_MK_RELPATH] == "updated"
        assert actions[APP_CONFIG_RELPATH] == "updated"
        assert actions[BUILD_DESIGNER_RELPATH] == "updated"
        assert actions[APP_CONFIG_DESIGNER_RELPATH] == "updated"
        assert actions[RESOURCE_CONFIG_RELPATH] == "unchanged"
        assert actions[DESIGNER_RESOURCE_CONFIG_RELPATH] == "updated"
        assert actions["build_designer.mk"] == "removed"
        assert actions["app_egui_config_designer.h"] == "removed"
        assert ".designer/build_designer.mk" in (project_dir / "build.mk").read_text(encoding="utf-8")
        assert "EGUI_CODE_SRC += local.c" in (project_dir / "build.mk").read_text(encoding="utf-8")
        assert '#include ".designer/app_egui_config_designer.h"' in (
            project_dir / "app_egui_config.h"
        ).read_text(encoding="utf-8")
        assert "#define USER_FLAG 1" in (project_dir / "app_egui_config.h").read_text(encoding="utf-8")
        assert (project_dir / "build_designer.mk").exists() is False
        assert (project_dir / "app_egui_config_designer.h").exists() is False
        assert '"user_asset"' in (resource_src_dir / "app_resource_config.json").read_text(encoding="utf-8")
        assert (designer_resource_dir / "app_resource_config_designer.json").read_text(encoding="utf-8") == (
            '{\n    "img": [],\n    "font": []\n}\n'
        )


class TestCoreProjectScaffold:
    def test_normalize_scaffold_pages_uses_default_and_strips_empty_names(self):
        assert normalize_scaffold_pages() == ["main_page"]
        assert normalize_scaffold_pages(["", " home ", " ", "detail"]) == ["home", "detail"]

    def test_scaffold_relpath_helpers_use_project_layout_conventions(self):
        assert os.path.normpath(project_config_dir("D:/workspace/DemoApp")) == os.path.normpath(
            "D:/workspace/DemoApp/.eguiproject"
        )
        assert os.path.normpath(project_config_path("D:/workspace/DemoApp", "layout", "main_page.xml")) == os.path.normpath(
            "D:/workspace/DemoApp/.eguiproject/layout/main_page.xml"
        )
        assert os.path.normpath(project_config_layout_dir("D:/workspace/DemoApp")) == os.path.normpath(
            "D:/workspace/DemoApp/.eguiproject/layout"
        )
        assert project_config_layout_xml_relpath("main_page") == "layout/main_page.xml"
        assert os.path.normpath(project_layout_xml_path("D:/workspace/DemoApp", "main_page")) == os.path.normpath(
            "D:/workspace/DemoApp/.eguiproject/layout/main_page.xml"
        )
        assert os.path.normpath(project_config_mockup_dir("D:/workspace/DemoApp")) == os.path.normpath(
            "D:/workspace/DemoApp/.eguiproject/mockup"
        )
        assert project_config_mockup_relpath("design.png") == "mockup/design.png"
        assert os.path.normpath(project_config_mockup_path("D:/workspace/DemoApp", "design.png")) == os.path.normpath(
            "D:/workspace/DemoApp/.eguiproject/mockup/design.png"
        )
        assert os.path.normpath(project_config_backup_dir("D:/workspace/DemoApp")) == os.path.normpath(
            "D:/workspace/DemoApp/.eguiproject/backup"
        )
        assert os.path.normpath(project_config_orphaned_user_code_dir("D:/workspace/DemoApp")) == os.path.normpath(
            "D:/workspace/DemoApp/.eguiproject/orphaned_user_code"
        )
        assert project_orphaned_user_page_relpath("main_page") == ".eguiproject/orphaned_user_code/main_page"
        assert os.path.normpath(
            project_config_orphaned_user_page_dir("D:/workspace/DemoApp", "main_page")
        ) == os.path.normpath(
            "D:/workspace/DemoApp/.eguiproject/orphaned_user_code/main_page"
        )
        assert os.path.normpath(project_config_reference_frames_dir("D:/workspace/DemoApp")) == os.path.normpath(
            "D:/workspace/DemoApp/.eguiproject/reference_frames"
        )
        assert os.path.normpath(project_config_regression_report_path("D:/workspace/DemoApp")) == os.path.normpath(
            "D:/workspace/DemoApp/.eguiproject/regression_report.html"
        )
        assert os.path.normpath(project_config_regression_results_path("D:/workspace/DemoApp")) == os.path.normpath(
            "D:/workspace/DemoApp/.eguiproject/regression_results.json"
        )
        assert os.path.normpath(project_config_resource_dir("D:/workspace/DemoApp")) == os.path.normpath(
            "D:/workspace/DemoApp/.eguiproject/resources"
        )
        assert os.path.normpath(resource_catalog_path("D:/workspace/DemoApp/.eguiproject/resources")) == os.path.normpath(
            "D:/workspace/DemoApp/.eguiproject/resources/resources.xml"
        )
        assert os.path.normpath(project_resource_catalog_path("D:/workspace/DemoApp")) == os.path.normpath(
            "D:/workspace/DemoApp/.eguiproject/resources/resources.xml"
        )
        assert os.path.normpath(project_config_images_dir("D:/workspace/DemoApp")) == os.path.normpath(
            "D:/workspace/DemoApp/.eguiproject/resources/images"
        )
        assert os.path.normpath(project_generated_resource_dir("D:/workspace/DemoApp")) == os.path.normpath(
            "D:/workspace/DemoApp/resource"
        )
        assert os.path.normpath(generated_resource_img_dir("D:/workspace/DemoApp/resource")) == os.path.normpath(
            "D:/workspace/DemoApp/resource/img"
        )
        assert os.path.normpath(generated_resource_font_dir("D:/workspace/DemoApp/resource")) == os.path.normpath(
            "D:/workspace/DemoApp/resource/font"
        )
        assert os.path.normpath(project_generated_img_dir("D:/workspace/DemoApp")) == os.path.normpath(
            "D:/workspace/DemoApp/resource/img"
        )
        assert os.path.normpath(project_generated_font_dir("D:/workspace/DemoApp")) == os.path.normpath(
            "D:/workspace/DemoApp/resource/font"
        )
        assert os.path.normpath(project_resource_src_dir("D:/workspace/DemoApp")) == os.path.normpath(
            "D:/workspace/DemoApp/resource/src"
        )
        assert os.path.normpath(project_user_resource_config_path("D:/workspace/DemoApp")) == os.path.normpath(
            "D:/workspace/DemoApp/resource/src/app_resource_config.json"
        )
        assert os.path.normpath(project_designer_resource_dir("D:/workspace/DemoApp")) == os.path.normpath(
            "D:/workspace/DemoApp/resource/src/.designer"
        )
        assert os.path.normpath(project_designer_resource_config_path("D:/workspace/DemoApp")) == os.path.normpath(
            "D:/workspace/DemoApp/resource/src/.designer/app_resource_config_designer.json"
        )
        assert os.path.normpath(project_supported_text_path("D:/workspace/DemoApp")) == os.path.normpath(
            "D:/workspace/DemoApp/resource/src/supported_text.txt"
        )
        assert os.path.normpath(resource_images_dir("D:/workspace/DemoApp/.eguiproject/resources")) == os.path.normpath(
            "D:/workspace/DemoApp/.eguiproject/resources/images"
        )
        assert os.path.normpath(
            resource_source_path("D:/workspace/DemoApp/.eguiproject/resources", "image_file", "hero.png")
        ) == os.path.normpath("D:/workspace/DemoApp/.eguiproject/resources/images/hero.png")
        assert os.path.normpath(
            resource_source_path("D:/workspace/DemoApp/.eguiproject/resources", "font_file", "demo.ttf")
        ) == os.path.normpath("D:/workspace/DemoApp/.eguiproject/resources/demo.ttf")
        assert os.path.normpath(project_build_mk_path("D:/workspace/DemoApp")) == os.path.normpath(
            "D:/workspace/DemoApp/build.mk"
        )
        assert os.path.normpath(project_app_config_path("D:/workspace/DemoApp")) == os.path.normpath(
            "D:/workspace/DemoApp/app_egui_config.h"
        )
        assert EGUIPROJECT_DIRNAME == ".eguiproject"
        assert RESOURCE_DIR_RELPATH == ".eguiproject/resources"
        assert RESOURCE_CATALOG_FILENAME == "resources.xml"
        assert MOCKUP_DIR_RELPATH == ".eguiproject/mockup"
        assert BACKUP_DIR_RELPATH == ".eguiproject/backup"
        assert ORPHANED_USER_CODE_DIR_RELPATH == ".eguiproject/orphaned_user_code"
        assert REFERENCE_FRAMES_DIR_RELPATH == ".eguiproject/reference_frames"
        assert RELEASE_CONFIG_RELPATH == ".eguiproject/release.json"
        assert REGRESSION_REPORT_RELPATH == ".eguiproject/regression_report.html"
        assert REGRESSION_RESULTS_RELPATH == ".eguiproject/regression_results.json"
        assert RESOURCE_SRC_DIR_RELPATH == "resource/src"
        assert SUPPORTED_TEXT_RELPATH == "resource/src/supported_text.txt"
        assert project_file_relpath("DemoApp") == "DemoApp.egui"
        assert os.path.normpath(project_file_path("D:/workspace/DemoApp", "DemoApp")) == os.path.normpath(
            "D:/workspace/DemoApp/DemoApp.egui"
        )

    def test_sdk_example_scaffold_path_helpers_use_sdk_example_layout(self):
        sdk_root = "D:/sdk/EmbeddedGUI"

        assert os.path.normpath(sdk_example_config_dir(sdk_root, "DemoApp")) == os.path.normpath(
            "D:/sdk/EmbeddedGUI/example/DemoApp/.eguiproject"
        )
        assert os.path.normpath(sdk_example_layout_dir(sdk_root, "DemoApp")) == os.path.normpath(
            "D:/sdk/EmbeddedGUI/example/DemoApp/.eguiproject/layout"
        )
        assert os.path.normpath(sdk_example_layout_xml_path(sdk_root, "DemoApp", "main_page")) == os.path.normpath(
            "D:/sdk/EmbeddedGUI/example/DemoApp/.eguiproject/layout/main_page.xml"
        )
        assert os.path.normpath(sdk_example_config_resource_dir(sdk_root, "DemoApp")) == os.path.normpath(
            "D:/sdk/EmbeddedGUI/example/DemoApp/.eguiproject/resources"
        )
        assert os.path.normpath(sdk_example_resource_images_dir(sdk_root, "DemoApp")) == os.path.normpath(
            "D:/sdk/EmbeddedGUI/example/DemoApp/.eguiproject/resources/images"
        )
        assert os.path.normpath(sdk_example_generated_resource_dir(sdk_root, "DemoApp")) == os.path.normpath(
            "D:/sdk/EmbeddedGUI/example/DemoApp/resource"
        )
        assert os.path.normpath(sdk_example_generated_img_dir(sdk_root, "DemoApp")) == os.path.normpath(
            "D:/sdk/EmbeddedGUI/example/DemoApp/resource/img"
        )
        assert os.path.normpath(sdk_example_generated_font_dir(sdk_root, "DemoApp")) == os.path.normpath(
            "D:/sdk/EmbeddedGUI/example/DemoApp/resource/font"
        )
        assert os.path.normpath(sdk_example_resource_src_dir(sdk_root, "DemoApp")) == os.path.normpath(
            "D:/sdk/EmbeddedGUI/example/DemoApp/resource/src"
        )
        assert os.path.normpath(sdk_example_supported_text_path(sdk_root, "DemoApp")) == os.path.normpath(
            "D:/sdk/EmbeddedGUI/example/DemoApp/resource/src/supported_text.txt"
        )
        assert os.path.normpath(sdk_example_resource_catalog_path(sdk_root, "DemoApp")) == os.path.normpath(
            "D:/sdk/EmbeddedGUI/example/DemoApp/.eguiproject/resources/resources.xml"
        )
        assert os.path.normpath(sdk_example_user_resource_config_path(sdk_root, "DemoApp")) == os.path.normpath(
            "D:/sdk/EmbeddedGUI/example/DemoApp/resource/src/app_resource_config.json"
        )
        assert os.path.normpath(
            sdk_example_designer_resource_config_path(sdk_root, "DemoApp")
        ) == os.path.normpath(
            "D:/sdk/EmbeddedGUI/example/DemoApp/resource/src/.designer/app_resource_config_designer.json"
        )
        assert os.path.normpath(sdk_example_app_config_path(sdk_root, "DemoApp")) == os.path.normpath(
            "D:/sdk/EmbeddedGUI/example/DemoApp/app_egui_config.h"
        )
        assert os.path.normpath(sdk_example_build_mk_path(sdk_root, "DemoApp")) == os.path.normpath(
            "D:/sdk/EmbeddedGUI/example/DemoApp/build.mk"
        )
        assert os.path.normpath(sdk_example_project_file_path(sdk_root, "DemoApp")) == os.path.normpath(
            "D:/sdk/EmbeddedGUI/example/DemoApp/DemoApp.egui"
        )
        assert os.path.normpath(sdk_example_reference_frames_dir(sdk_root, "DemoApp")) == os.path.normpath(
            "D:/sdk/EmbeddedGUI/example/DemoApp/.eguiproject/reference_frames"
        )
        assert os.path.normpath(sdk_example_regression_report_path(sdk_root, "DemoApp")) == os.path.normpath(
            "D:/sdk/EmbeddedGUI/example/DemoApp/.eguiproject/regression_report.html"
        )
        assert os.path.normpath(sdk_example_regression_results_path(sdk_root, "DemoApp")) == os.path.normpath(
            "D:/sdk/EmbeddedGUI/example/DemoApp/.eguiproject/regression_results.json"
        )
        assert project_layout_xml_relpath("main_page") == ".eguiproject/layout/main_page.xml"
        assert default_scaffold_circle_radius(320, 240) == 120

    def test_designer_scaffold_kwargs_normalizes_shared_defaults(self):
        kwargs = designer_scaffold_kwargs(
            320,
            240,
            overwrite=True,
            color_depth=32,
            extra_config_macros=[("EGUI_CONFIG_FUNCTION_SUPPORT_SHADOW", "1")],
            refresh_designer_resource_config=False,
        )

        assert kwargs == {
            "overwrite": True,
            "color_depth": 32,
            "circle_radius": 120,
            "extra_config_macros": [("EGUI_CONFIG_FUNCTION_SUPPORT_SHADOW", "1")],
            "refresh_designer_resource_config": False,
        }

    def test_designer_conversion_scaffold_kwargs_enables_shadow_support_defaults(self):
        kwargs = designer_conversion_scaffold_kwargs(320, 240)

        assert kwargs == {
            "overwrite": True,
            "color_depth": 16,
            "circle_radius": 120,
            "extra_config_macros": [("EGUI_CONFIG_FUNCTION_SUPPORT_SHADOW", "1")],
            "refresh_designer_resource_config": False,
        }

    def test_bind_project_storage_normalizes_project_dir_and_optional_sdk_root(self):
        project = build_empty_project_model("BindingDemo", 320, 240)

        bind_project_storage(project, "D:/workspace/BindingDemo", sdk_root="D:/sdk")

        assert project.project_dir == os.path.normpath("D:/workspace/BindingDemo")
        assert project.sdk_root == os.path.normpath("D:/sdk")

    def test_build_empty_project_model_creates_default_startup_page(self):
        project = build_empty_project_model(
            "DemoApp",
            320,
            240,
            sdk_root="D:/sdk",
            project_dir="D:/workspace/DemoApp",
            pages=["home", "settings"],
        )
        page, root = require_project_page_root(project)

        assert project.sdk_root == os.path.normpath("D:/sdk")
        assert project.project_dir == os.path.normpath("D:/workspace/DemoApp")
        assert project.startup_page == "home"
        assert [page.name for page in project.pages] == ["home", "settings"]
        assert page.name == "home"
        assert root.width == 320
        assert root.height == 240

    def test_require_project_page_root_uses_startup_page_by_default(self):
        project = build_empty_project_model(
            "DemoApp",
            320,
            240,
            pages=["home", "settings"],
        )

        page, root = require_project_page_root(project)

        assert page.name == "home"
        assert root is page.root_widget
        assert root.width == 320
        assert root.height == 240

    def test_require_project_page_root_returns_named_page_and_root(self):
        project = build_empty_project_model(
            "DemoApp",
            320,
            240,
            pages=["home", "settings"],
        )

        page, root = require_project_page_root(project, "settings")

        assert page.name == "settings"
        assert root is page.root_widget
        assert root.width == 320
        assert root.height == 240

    def test_require_page_root_returns_page_root_widget(self):
        project = build_empty_project_model(
            "DemoApp",
            320,
            240,
            pages=["home"],
        )
        page, _root = require_project_page_root(project, "home")

        root = require_page_root(page)

        assert root is page.root_widget
        assert root.width == 320
        assert root.height == 240

    def test_require_page_root_raises_when_page_is_missing(self):
        with pytest.raises(RuntimeError, match="Scaffold page 'settings' was not created"):
            require_page_root(None, "settings")

    def test_require_page_root_raises_when_page_root_is_missing(self):
        project = build_empty_project_model(
            "DemoApp",
            320,
            240,
            pages=["home"],
        )
        page = project.get_page_by_name("home")
        assert page is not None
        page.root_widget = None

        with pytest.raises(RuntimeError, match="Scaffold page 'home' did not create a root widget"):
            require_page_root(page)

    def test_require_project_page_root_raises_when_startup_page_is_missing(self):
        from ui_designer.model.project import Project

        project = Project(app_name="DemoApp")
        project.startup_page = "home"

        with pytest.raises(RuntimeError, match="Scaffold project did not create a startup page"):
            require_project_page_root(project)

    def test_require_project_page_root_raises_when_named_page_is_missing(self):
        project = build_empty_project_model(
            "DemoApp",
            320,
            240,
            pages=["home"],
        )

        with pytest.raises(RuntimeError, match="Scaffold project did not create page 'settings'"):
            require_project_page_root(project, "settings")

    def test_require_project_page_root_raises_when_page_root_is_missing(self):
        project = build_empty_project_model(
            "DemoApp",
            320,
            240,
            pages=["home"],
        )
        page = project.get_page_by_name("home")
        assert page is not None
        page.root_widget = None

        with pytest.raises(RuntimeError, match="Scaffold page 'home' did not create a root widget"):
            require_project_page_root(project, "home")

    def test_build_empty_project_model_with_root_returns_project_page_and_root(self):
        project, page, root = build_empty_project_model_with_root(
            "DemoApp",
            320,
            240,
            sdk_root="D:/sdk",
            project_dir="D:/workspace/DemoApp",
            page_name="home",
        )

        assert project.sdk_root == os.path.normpath("D:/sdk")
        assert project.project_dir == os.path.normpath("D:/workspace/DemoApp")
        assert project.startup_page == "home"
        assert page.name == "home"
        assert root is page.root_widget
        assert root.width == 320
        assert root.height == 240

    def test_build_basic_widget_model_uses_shared_defaults(self):
        widget = build_basic_widget_model("button")

        assert widget.widget_type == "button"
        assert widget.name == "title"
        assert widget.x == 12
        assert widget.y == 16
        assert widget.width == 100
        assert widget.height == 24

    def test_add_page_widget_attaches_widget_to_page_root(self):
        project = build_empty_project_model(
            "DemoApp",
            320,
            240,
            pages=["home"],
        )
        page, root = require_project_page_root(project, "home")

        widget = add_page_widget(
            page,
            "label",
            name="subtitle",
            x=20,
            y=24,
            width=120,
            height=28,
        )

        assert widget in root.children
        assert root.children == [widget]

    def test_add_widget_children_attaches_widgets_in_order(self):
        from ui_designer.model.widget_model import WidgetModel

        root = WidgetModel("group", name="root")
        first = WidgetModel("label", name="first")
        second = WidgetModel("button", name="second")

        attached_root = add_widget_children(root, [first, second])

        assert attached_root is root
        assert root.children == [first, second]

    def test_build_page_model_from_root_wraps_supplied_root(self):
        from ui_designer.model.widget_model import WidgetModel

        root = WidgetModel("linearlayout", name="root_layout", x=0, y=0, width=200, height=120)

        page = build_page_model_from_root("detail", root=root)

        assert page.name == "detail"
        assert page.root_widget is root

    def test_build_page_model_from_root_with_widgets_populates_supplied_root(self):
        from ui_designer.model.widget_model import WidgetModel

        root = WidgetModel("linearlayout", name="root_layout", x=0, y=0, width=200, height=120)
        first = WidgetModel("label", name="first")
        second = WidgetModel("button", name="second")

        page, resolved_root = build_page_model_from_root_with_widgets(
            "detail",
            root=root,
            widgets=[first, second],
        )

        assert page.name == "detail"
        assert resolved_root is root
        assert root.children == [first, second]

    def test_build_page_model_with_widget_creates_page_and_attached_widget(self):
        page, widget = build_page_model_with_widget(
            "home",
            "button",
            screen_width=320,
            screen_height=240,
            name="cta",
            x=16,
            y=24,
            width=96,
            height=40,
        )
        root = require_page_root(page, "home")

        assert page.name == "home"
        assert root.width == 320
        assert root.height == 240
        assert widget in root.children
        assert widget.name == "cta"
        assert widget.widget_type == "button"

    def test_build_page_model_only_with_widget_returns_attached_widget(self):
        widget = build_page_model_only_with_widget(
            "home",
            "button",
            screen_width=320,
            screen_height=240,
            name="cta",
            x=16,
            y=24,
            width=96,
            height=40,
        )

        assert widget.name == "cta"
        assert widget.widget_type == "button"
        assert widget.parent is not None

    def test_build_page_model_with_root_widget_supports_custom_root(self):
        page, root = build_page_model_with_root_widget(
            "detail",
            "linearlayout",
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

    def test_build_page_model_with_widgets_attaches_children_to_custom_root(self):
        from ui_designer.model.widget_model import WidgetModel

        first = WidgetModel("label", name="first")
        second = WidgetModel("button", name="second")

        page, root = build_page_model_with_widgets(
            "detail",
            screen_width=200,
            screen_height=120,
            root_widget_type="linearlayout",
            root_name="root_layout",
            widgets=[first, second],
        )

        assert page.name == "detail"
        assert root is page.root_widget
        assert root.widget_type == "linearlayout"
        assert root.children == [first, second]

    def test_build_page_model_root_with_widgets_returns_populated_root(self):
        from ui_designer.model.widget_model import WidgetModel

        first = WidgetModel("label", name="first")
        second = WidgetModel("button", name="second")

        root = build_page_model_root_with_widgets(
            "detail",
            screen_width=200,
            screen_height=120,
            root_widget_type="linearlayout",
            root_name="root_layout",
            widgets=[first, second],
        )

        assert root.widget_type == "linearlayout"
        assert root.name == "root_layout"
        assert root.children == [first, second]

    def test_build_project_model_from_pages_preserves_page_mode_and_startup(self):
        from ui_designer.model.widget_model import WidgetModel

        home_page = build_page_model_from_root("home")
        detail_page = build_page_model_from_root(
            "detail",
            root=WidgetModel("group", name="detail_root", x=0, y=0, width=320, height=240),
        )

        project = build_project_model_from_pages(
            [home_page, detail_page],
            app_name="DemoApp",
            page_mode="activity",
            startup_page="detail",
        )

        assert project.app_name == "DemoApp"
        assert project.page_mode == "activity"
        assert project.startup_page == "detail"
        assert [page.name for page in project.pages] == ["home", "detail"]

    def test_build_project_model_from_root_wraps_supplied_root_as_single_page_project(self):
        from ui_designer.model.widget_model import WidgetModel

        root = WidgetModel("linearlayout", name="root_layout", x=0, y=0, width=200, height=120)

        project, page = build_project_model_from_root(
            root,
            page_name="main_page",
            app_name="LayoutGroupDemo",
            page_mode="activity",
        )

        assert project.app_name == "LayoutGroupDemo"
        assert project.page_mode == "activity"
        assert project.startup_page == "main_page"
        assert project.screen_width == 200
        assert project.screen_height == 120
        assert page.name == "main_page"
        assert page.root_widget is root

    def test_build_project_model_from_root_with_widgets_populates_supplied_root(self):
        from ui_designer.model.widget_model import WidgetModel

        root = WidgetModel("linearlayout", name="root_layout", x=0, y=0, width=200, height=120)
        first = WidgetModel("label", name="first")
        second = WidgetModel("label", name="second")

        project, page = build_project_model_from_root_with_widgets(
            root,
            page_name="main_page",
            app_name="LayoutGroupDemo",
            widgets=[first, second],
        )

        assert project.app_name == "LayoutGroupDemo"
        assert page.name == "main_page"
        assert page.root_widget is root
        assert root.children == [first, second]

    def test_build_project_model_only_from_root_with_widgets_returns_populated_project(self):
        from ui_designer.model.widget_model import WidgetModel

        root = WidgetModel("linearlayout", name="root_layout", x=0, y=0, width=200, height=120)
        first = WidgetModel("label", name="first")
        second = WidgetModel("label", name="second")

        project = build_project_model_only_from_root_with_widgets(
            root,
            page_name="main_page",
            app_name="LayoutGroupDemo",
            widgets=[first, second],
        )
        page, resolved_root = require_project_page_root(project, "main_page")

        assert project.app_name == "LayoutGroupDemo"
        assert page.name == "main_page"
        assert resolved_root is root
        assert root.children == [first, second]

    def test_build_project_model_with_widgets_attaches_widgets_and_applies_customizers(self):
        from ui_designer.model.widget_model import WidgetModel

        label = WidgetModel("label", name="title", x=10, y=10, width=120, height=24)
        badge = WidgetModel("label", name="badge", x=10, y=40, width=60, height=20)

        def _customize_page(page, root):
            page.user_fields = [{"name": "counter", "type": "int", "default": "0"}]
            add_widget_children(root, [badge])

        def _customize_project(project):
            project.string_catalog.set("greeting", "Hello", "default")

        project, page, root = build_project_model_with_widgets(
            "DemoApp",
            320,
            240,
            page_name="home",
            widgets=[label],
            page_customizer=_customize_page,
            project_customizer=_customize_project,
        )

        assert project.app_name == "DemoApp"
        assert page.name == "home"
        assert root.children == [label, badge]
        assert page.user_fields == [{"name": "counter", "type": "int", "default": "0"}]
        assert project.string_catalog.get("greeting", "default") == "Hello"

    def test_build_project_model_and_page_with_widgets_returns_project_and_page(self):
        from ui_designer.model.widget_model import WidgetModel

        label = WidgetModel("label", name="title", x=10, y=10, width=120, height=24)

        project, page = build_project_model_and_page_with_widgets(
            "DemoApp",
            320,
            240,
            page_name="home",
            widgets=[label],
        )

        assert project.app_name == "DemoApp"
        assert page.name == "home"
        assert page.root_widget.children == [label]

    def test_build_project_model_and_root_with_widgets_returns_project_and_root(self):
        from ui_designer.model.widget_model import WidgetModel

        label = WidgetModel("label", name="title", x=10, y=10, width=120, height=24)

        project, root = build_project_model_and_root_with_widgets(
            "DemoApp",
            320,
            240,
            page_name="home",
            widgets=[label],
        )

        assert project.app_name == "DemoApp"
        assert [child.name for child in root.children] == ["title"]

    def test_build_project_model_only_with_widgets_returns_populated_project(self):
        from ui_designer.model.widget_model import WidgetModel

        label = WidgetModel("label", name="title", x=10, y=10, width=120, height=24)

        project = build_project_model_only_with_widgets(
            "DemoApp",
            320,
            240,
            page_name="home",
            widgets=[label],
        )
        page, root = require_project_page_root(project, "home")

        assert project.app_name == "DemoApp"
        assert page.name == "home"
        assert root.children == [label]

    def test_build_project_model_with_widget_creates_requested_widget_and_applies_customizers(self):
        def _customize_page(page, root):
            page.timers = [{"name": "tick", "callback": "on_tick", "delay_ms": "500", "period_ms": "500"}]
            assert [child.name for child in root.children] == ["cta"]

        def _customize_project(project):
            project.string_catalog.set("greeting", "Hello", "default")

        project, page, widget = build_project_model_with_widget(
            "DemoApp",
            "button",
            page_name="home",
            name="cta",
            x=16,
            y=24,
            width=96,
            height=40,
            page_customizer=_customize_page,
            project_customizer=_customize_project,
        )

        assert project.app_name == "DemoApp"
        assert page.name == "home"
        assert widget.name == "cta"
        assert widget.widget_type == "button"
        assert widget in page.root_widget.children
        assert page.timers == [{"name": "tick", "callback": "on_tick", "delay_ms": "500", "period_ms": "500"}]
        assert project.string_catalog.get("greeting", "default") == "Hello"

    def test_build_project_model_and_page_with_widget_returns_project_and_page(self):
        project, page = build_project_model_and_page_with_widget(
            "DemoApp",
            "button",
            page_name="home",
            name="cta",
            x=16,
            y=24,
            width=96,
            height=40,
        )

        assert project.app_name == "DemoApp"
        assert page.name == "home"
        assert [child.name for child in page.root_widget.children] == ["cta"]
        assert page.root_widget.children[0].widget_type == "button"

    def test_build_project_model_only_with_widget_returns_project_for_requested_widget(self):
        project = build_project_model_only_with_widget(
            "DemoApp",
            "button",
            page_name="home",
            name="cta",
            x=16,
            y=24,
            width=96,
            height=40,
        )
        page, root = require_project_page_root(project, "home")

        assert project.app_name == "DemoApp"
        assert page.name == "home"
        assert [child.name for child in root.children] == ["cta"]
        assert root.children[0].widget_type == "button"

    def test_build_project_model_with_page_widgets_populates_pages_and_customizers(self):
        from ui_designer.model.widget_model import WidgetModel

        home_label = WidgetModel("label", name="home_title", x=10, y=10, width=120, height=24)
        detail_button = WidgetModel("button", name="detail_cta", x=10, y=48, width=80, height=32)

        def _customize_detail(page, root):
            page.timers = [{"name": "tick", "callback": "on_tick", "delay_ms": "500", "period_ms": "500"}]
            assert root.children == [detail_button]

        def _customize_project(project):
            project.resource_catalog.add_image("hero.png")

        project, roots = build_project_model_with_page_widgets(
            "DemoApp",
            320,
            240,
            pages=["home"],
            page_widgets={
                "home": [home_label],
                "detail": [detail_button],
            },
            page_customizers={"detail": _customize_detail},
            project_customizer=_customize_project,
        )
        detail_page, _detail_root = require_project_page_root(project, "detail")

        assert list(roots) == ["home", "detail"]
        assert roots["home"].children == [home_label]
        assert roots["detail"].children == [detail_button]
        assert detail_page.timers == [{"name": "tick", "callback": "on_tick", "delay_ms": "500", "period_ms": "500"}]
        assert project.resource_catalog.has_image("hero.png") is True

    def test_build_project_model_only_with_page_widgets_returns_populated_project(self):
        from ui_designer.model.widget_model import WidgetModel

        home_label = WidgetModel("label", name="home_title", x=10, y=10, width=120, height=24)
        detail_button = WidgetModel("button", name="detail_cta", x=10, y=48, width=80, height=32)

        project = build_project_model_only_with_page_widgets(
            "DemoApp",
            320,
            240,
            page_widgets={
                "home": [home_label],
                "detail": [detail_button],
            },
        )
        _home_page, home_root = require_project_page_root(project, "home")
        _detail_page, detail_root = require_project_page_root(project, "detail")

        assert project.app_name == "DemoApp"
        assert home_root.children == [home_label]
        assert detail_root.children == [detail_button]

    def test_build_empty_project_xml_uses_canonical_sdk_root_attribute(self):
        xml = build_empty_project_xml(
            "DemoApp",
            320,
            240,
            stored_sdk_root="../../sdk/EmbeddedGUI",
            pages=["main_page"],
        )

        assert 'sdk_root="../../sdk/EmbeddedGUI"' in xml
        assert 'egui_root="' not in xml

    def test_sync_project_scaffold_core_files_preserves_existing_page_templates(self, tmp_path):
        project_dir = tmp_path / "CoreApp"
        page_path = project_dir / ".eguiproject" / "layout" / "main_page.xml"
        page_path.parent.mkdir(parents=True)
        page_path.write_text("<Page><Legacy /></Page>\n", encoding="utf-8")

        actions = sync_project_scaffold_core_files(
            str(project_dir),
            "CoreApp",
            320,
            240,
            stored_sdk_root="../../sdk/EmbeddedGUI",
        )

        assert actions["CoreApp.egui"] == "created"
        assert actions[RESOURCE_CATALOG_RELPATH] == "created"
        assert actions[".eguiproject/layout/main_page.xml"] == "unchanged"
        assert 'sdk_root="../../sdk/EmbeddedGUI"' in (project_dir / "CoreApp.egui").read_text(encoding="utf-8")
        assert Path(project_resource_catalog_path(str(project_dir))).is_file()
        assert page_path.read_text(encoding="utf-8") == "<Page><Legacy /></Page>\n"


class TestApplyDesignerProjectScaffold:
    def test_overwrite_defaults_to_refreshing_designer_resource_config(self, tmp_path):
        project_dir = tmp_path / "SmokeApp"
        designer_resource_path = (
            project_dir / "resource" / "src" / ".designer" / "app_resource_config_designer.json"
        )
        designer_resource_path.parent.mkdir(parents=True)
        designer_resource_path.write_text('{"img": [{"name": "stale"}], "font": []}\n', encoding="utf-8")

        actions = apply_designer_project_scaffold(
            str(project_dir),
            "SmokeApp",
            240,
            240,
            overwrite=True,
        )

        assert actions[BUILD_MK_RELPATH] == "created"
        assert actions[DESIGNER_RESOURCE_CONFIG_RELPATH] == "updated"
        assert designer_resource_path.read_text(encoding="utf-8") == '{\n    "img": [],\n    "font": []\n}\n'

    def test_can_preserve_designer_resource_config_while_refreshing_wrappers(self, tmp_path):
        project_dir = tmp_path / "HelperApp"
        designer_resource_path = (
            project_dir / "resource" / "src" / ".designer" / "app_resource_config_designer.json"
        )
        designer_resource_path.parent.mkdir(parents=True)
        designer_resource_path.write_text('{"img": [{"name": "keep_me"}], "font": []}\n', encoding="utf-8")

        actions = apply_designer_project_scaffold(
            str(project_dir),
            "HelperApp",
            320,
            240,
            overwrite=True,
            refresh_designer_resource_config=False,
        )

        assert actions[BUILD_MK_RELPATH] == "created"
        assert actions[DESIGNER_RESOURCE_CONFIG_RELPATH] == "unchanged"
        assert '"keep_me"' in designer_resource_path.read_text(encoding="utf-8")

    def test_save_project_with_designer_scaffold_writes_sidecars_and_project_files(self, tmp_path):
        project_dir = tmp_path / "SavedHelperApp"
        project = build_empty_project_model(
            "SavedHelperApp",
            320,
            240,
            sdk_root="D:/sdk",
            project_dir=str(project_dir),
            pages=["home"],
        )

        actions = save_project_with_designer_scaffold(project, str(project_dir))

        assert actions[BUILD_MK_RELPATH] == "created"
        assert actions[APP_CONFIG_RELPATH] == "created"
        assert actions[BUILD_DESIGNER_RELPATH] == "created"
        assert actions[APP_CONFIG_DESIGNER_RELPATH] == "created"
        assert (project_dir / "SavedHelperApp.egui").is_file()
        assert (project_dir / ".eguiproject" / "layout" / "home.xml").is_file()
        assert (project_dir / ".designer" / "build_designer.mk").is_file()
        assert (project_dir / ".designer" / "app_egui_config_designer.h").is_file()

    def test_save_project_with_designer_scaffold_refreshes_designer_resource_config_on_overwrite(self, tmp_path):
        project_dir = tmp_path / "OverwriteHelperApp"
        designer_resource_path = (
            project_dir / "resource" / "src" / ".designer" / "app_resource_config_designer.json"
        )
        designer_resource_path.parent.mkdir(parents=True)
        designer_resource_path.write_text('{"img": [{"name": "stale"}], "font": []}\n', encoding="utf-8")
        project = build_empty_project_model(
            "OverwriteHelperApp",
            320,
            240,
            pages=["main_page"],
        )

        actions = save_project_with_designer_scaffold(project, str(project_dir), overwrite=True)

        assert actions[DESIGNER_RESOURCE_CONFIG_RELPATH] == "updated"
        assert designer_resource_path.read_text(encoding="utf-8") == '{\n    "img": [],\n    "font": []\n}\n'

    def test_generate_designer_resource_config_creates_user_overlay_and_designer_file(self, tmp_path):
        src_dir = tmp_path / "resource" / "src"
        designer_config_path = src_dir / ".designer" / "app_resource_config_designer.json"
        project = build_empty_project_model(
            "GeneratedResourceConfigHelperApp",
            320,
            240,
            pages=["home"],
        )

        created, config_path = generate_designer_resource_config(project, str(src_dir))
        created_again, config_path_again = generate_designer_resource_config(project, str(src_dir))

        assert created is True
        assert created_again is False
        assert os.path.normpath(config_path) == os.path.normpath(str(designer_config_path))
        assert os.path.normpath(config_path_again) == os.path.normpath(str(designer_config_path))
        assert (src_dir / "app_resource_config.json").read_text(encoding="utf-8") == '{\n    "img": [],\n    "font": []\n}\n'
        assert json.loads(designer_config_path.read_text(encoding="utf-8")) == {
            "img": [],
            "font": [],
        }

    def test_sync_project_resources_and_generate_designer_resource_config_syncs_resources_first(self, tmp_path):
        project_dir = tmp_path / "SyncedResourceConfigHelperApp"
        resources_dir = project_dir / ".eguiproject" / "resources"
        images_dir = resources_dir / "images"
        images_dir.mkdir(parents=True)
        (images_dir / "icon.png").write_bytes(b"PNG")
        project = build_empty_project_model(
            "SyncedResourceConfigHelperApp",
            320,
            240,
            pages=["home"],
        )

        created, config_path = sync_project_resources_and_generate_designer_resource_config(
            project,
            str(project_dir),
        )

        assert created is True
        assert (project_dir / "resource" / "src" / "icon.png").read_bytes() == b"PNG"
        assert os.path.normpath(config_path) == os.path.normpath(
            str(project_dir / "resource" / "src" / ".designer" / "app_resource_config_designer.json")
        )

    def test_sync_project_resources_and_generate_designer_resource_config_runs_before_generate_hook_after_sync(
        self,
        tmp_path,
    ):
        project_dir = tmp_path / "HookedResourceConfigHelperApp"
        resources_dir = project_dir / ".eguiproject" / "resources"
        images_dir = resources_dir / "images"
        images_dir.mkdir(parents=True)
        (images_dir / "icon.png").write_bytes(b"PNG")
        project = build_empty_project_model(
            "HookedResourceConfigHelperApp",
            320,
            240,
            pages=["home"],
        )
        hook_calls = []

        created, _config_path = sync_project_resources_and_generate_designer_resource_config(
            project,
            str(project_dir),
            before_generate=lambda output_dir: hook_calls.append(
                ((Path(output_dir) / "resource" / "src" / "icon.png").read_bytes(), output_dir)
            ),
        )

        assert created is True
        assert hook_calls == [(b"PNG", str(project_dir))]

    def test_save_project_and_materialize_codegen_writes_scaffold_and_generated_outputs(self, tmp_path):
        project_dir = tmp_path / "SavedGeneratedHelperApp"
        project = build_empty_project_model(
            "SavedGeneratedHelperApp",
            320,
            240,
            sdk_root="D:/sdk",
            project_dir=str(project_dir),
            pages=["home"],
        )
        callback_calls = []

        materialized = save_project_and_materialize_codegen(
            project,
            str(project_dir),
            overwrite=True,
            backup=False,
            extra_files={"home.c": "// custom home source\n"},
            before_materialize=lambda output_dir: callback_calls.append(output_dir),
        )

        assert callback_calls == [str(project_dir)]
        assert (project_dir / "SavedGeneratedHelperApp.egui").is_file()
        assert (project_dir / ".designer" / "build_designer.mk").is_file()
        assert (project_dir / ".designer" / "home.h").is_file()
        assert (project_dir / ".designer" / "home_layout.c").is_file()
        assert (project_dir / "home.c").read_text(encoding="utf-8") == "// custom home source\n"
        assert "home_ext.h" in materialized.files

    def test_materialize_project_codegen_outputs_runs_before_materialize_hook(self, tmp_path):
        project_dir = tmp_path / "MaterializeHookHelperApp"
        project = build_empty_project_model(
            "MaterializeHookHelperApp",
            320,
            240,
            sdk_root="D:/sdk",
            project_dir=str(project_dir),
            pages=["home"],
        )
        hook_calls = []

        materialized = materialize_project_codegen_outputs(
            project,
            str(project_dir),
            backup=False,
            before_materialize=lambda output_dir: hook_calls.append(output_dir),
        )

        assert hook_calls == [str(project_dir)]
        assert (project_dir / ".designer" / "home.h").is_file()
        assert "home.c" in materialized.files

    def test_prepare_project_codegen_outputs_runs_before_prepare_hook_and_cleans_legacy(self, tmp_path):
        project_dir = tmp_path / "PrepareHookHelperApp"
        project = build_empty_project_model(
            "PrepareHookHelperApp",
            320,
            240,
            sdk_root="D:/sdk",
            project_dir=str(project_dir),
            pages=["home"],
        )
        hook_calls = []
        legacy_root_uicode = project_dir / "uicode.c"
        legacy_root_uicode.parent.mkdir(parents=True, exist_ok=True)
        legacy_root_uicode.write_text("// stale legacy root uicode\n", encoding="utf-8")

        prepared = prepare_project_codegen_outputs(
            project,
            str(project_dir),
            backup=False,
            before_prepare=lambda output_dir: hook_calls.append(output_dir),
            cleanup_legacy=True,
        )

        assert hook_calls == [str(project_dir)]
        assert "home.c" in prepared.files
        assert not legacy_root_uicode.exists()

    def test_save_project_model_saves_project_without_scaffold_when_disabled(self, tmp_path):
        project_dir = tmp_path / "PlainSaveHelperApp"
        project = build_empty_project_model(
            "PlainSaveHelperApp",
            320,
            240,
            pages=["home"],
        )

        actions = save_project_model(project, str(project_dir))

        assert actions == {}
        assert project.project_dir == os.path.normpath(str(project_dir))
        assert (project_dir / "PlainSaveHelperApp.egui").is_file()
        assert (project_dir / ".eguiproject" / "layout" / "home.xml").is_file()
        assert (project_dir / ".designer" / "build_designer.mk").exists() is False

    def test_save_project_model_binds_sdk_root_and_runs_before_save_hook(self, tmp_path):
        project_dir = tmp_path / "PlainSaveHookHelperApp"
        project = build_empty_project_model(
            "PlainSaveHookHelperApp",
            320,
            240,
            pages=["home"],
        )
        hook_calls = []

        actions = save_project_model(
            project,
            str(project_dir),
            sdk_root="D:/sdk",
            before_save=lambda output_dir: hook_calls.append(
                (output_dir, project.project_dir, project.sdk_root)
            ),
        )

        assert actions == {}
        assert hook_calls == [
            (
                os.path.normpath(str(project_dir)),
                os.path.normpath(str(project_dir)),
                os.path.normpath("D:/sdk"),
            )
        ]
        assert project.project_dir == os.path.normpath(str(project_dir))
        assert project.sdk_root == os.path.normpath("D:/sdk")
        assert (project_dir / "PlainSaveHookHelperApp.egui").is_file()

    def test_save_project_model_can_include_designer_scaffold(self, tmp_path):
        project_dir = tmp_path / "ScaffoldSaveHelperApp"
        project = build_empty_project_model(
            "ScaffoldSaveHelperApp",
            320,
            240,
            pages=["home"],
        )

        actions = save_project_model(
            project,
            str(project_dir),
            with_designer_scaffold=True,
            overwrite_scaffold=True,
        )

        assert actions[BUILD_MK_RELPATH] == "created"
        assert actions[APP_CONFIG_RELPATH] == "created"
        assert project.project_dir == os.path.normpath(str(project_dir))
        assert (project_dir / "ScaffoldSaveHelperApp.egui").is_file()
        assert (project_dir / ".designer" / "build_designer.mk").is_file()

    def test_save_project_and_materialize_codegen_runs_before_save_hook_after_binding(self, tmp_path):
        project_dir = tmp_path / "SavedGeneratedHookHelperApp"
        project = build_empty_project_model(
            "SavedGeneratedHookHelperApp",
            320,
            240,
            pages=["home"],
        )
        hook_calls = []

        materialized = save_project_and_materialize_codegen(
            project,
            str(project_dir),
            sdk_root="D:/sdk",
            before_save=lambda output_dir: hook_calls.append(
                (output_dir, project.project_dir, project.sdk_root)
            ),
            backup=False,
        )

        assert hook_calls == [
            (
                os.path.normpath(str(project_dir)),
                os.path.normpath(str(project_dir)),
                os.path.normpath("D:/sdk"),
            )
        ]
        assert project.project_dir == os.path.normpath(str(project_dir))
        assert project.sdk_root == os.path.normpath("D:/sdk")
        assert (project_dir / "SavedGeneratedHookHelperApp.egui").is_file()
        assert (project_dir / ".designer" / "home.h").is_file()
        assert "home_ext.h" in materialized.files

    def test_save_empty_project_with_designer_scaffold_builds_and_saves_project(self, tmp_path):
        project_dir = tmp_path / "EmptyScaffoldHelperApp"

        project = save_empty_project_with_designer_scaffold(
            "EmptyScaffoldHelperApp",
            str(project_dir),
            480,
            272,
            sdk_root="D:/sdk",
            pages=["home", "settings"],
            remove_legacy_designer_files=True,
        )

        assert project.project_dir == os.path.normpath(str(project_dir))
        assert project.sdk_root == os.path.normpath("D:/sdk")
        assert project.screen_width == 480
        assert project.screen_height == 272
        assert (project_dir / "EmptyScaffoldHelperApp.egui").is_file()
        assert (project_dir / ".eguiproject" / "layout" / "home.xml").is_file()
        assert (project_dir / ".eguiproject" / "layout" / "settings.xml").is_file()
        assert (project_dir / ".designer" / "build_designer.mk").is_file()

    def test_save_empty_project_with_designer_scaffold_applies_project_customizer(self, tmp_path):
        project_dir = tmp_path / "CustomizedEmptyScaffoldHelperApp"

        project = save_empty_project_with_designer_scaffold(
            "CustomizedEmptyScaffoldHelperApp",
            str(project_dir),
            project_customizer=lambda project: project.string_catalog.set("greeting", "Hello", "default"),
        )

        assert project.string_catalog.get("greeting", "default") == "Hello"
        reloaded = project.__class__.load(str(project_dir))
        assert reloaded.string_catalog.get("greeting", "default") == "Hello"

    def test_scaffold_designer_project_combines_sidecars_and_core_templates(self, tmp_path):
        project_dir = tmp_path / "FullApp"

        actions = scaffold_designer_project(
            str(project_dir),
            "FullApp",
            320,
            240,
            stored_sdk_root="../../sdk/EmbeddedGUI",
            pages=["home", "settings"],
            overwrite=True,
        )

        assert actions[BUILD_MK_RELPATH] == "created"
        assert actions["FullApp.egui"] == "created"
        assert actions[RESOURCE_CATALOG_RELPATH] == "created"
        assert actions[".eguiproject/layout/home.xml"] == "created"
        assert actions[".eguiproject/layout/settings.xml"] == "created"
        assert (project_dir / ".designer" / "build_designer.mk").is_file()
        assert (project_dir / ".eguiproject" / "layout" / "home.xml").is_file()
        assert (project_dir / ".eguiproject" / "resources" / "images").is_dir()
        assert (project_dir / "resource" / "img").is_dir()
        assert (project_dir / "resource" / "font").is_dir()

    def test_scaffold_designer_project_with_sdk_root_serializes_relative_sdk_path(self, tmp_path):
        sdk_root = tmp_path / "sdk" / "EmbeddedGUI"
        project_dir = sdk_root / "example" / "SdkApp"

        actions = scaffold_designer_project_with_sdk_root(
            str(project_dir),
            "SdkApp",
            str(sdk_root),
            320,
            240,
            overwrite=True,
        )
        egui_content = (project_dir / "SdkApp.egui").read_text(encoding="utf-8")

        assert actions[BUILD_MK_RELPATH] == "created"
        assert actions["SdkApp.egui"] == "created"
        assert 'sdk_root="../.."' in egui_content

    def test_scaffold_conversion_project_with_sdk_root_applies_conversion_defaults(self, tmp_path):
        sdk_root = tmp_path / "sdk" / "EmbeddedGUI"
        project_dir = sdk_root / "example" / "ConversionApp"

        actions = scaffold_conversion_project_with_sdk_root(
            str(project_dir),
            "ConversionApp",
            str(sdk_root),
            320,
            240,
            pages=["home", "detail"],
            color_depth=32,
        )

        designer_config = (project_dir / ".designer" / "app_egui_config_designer.h").read_text(encoding="utf-8")
        assert actions[BUILD_MK_RELPATH] == "created"
        assert actions["ConversionApp.egui"] == "created"
        assert actions[".eguiproject/layout/home.xml"] == "created"
        assert actions[".eguiproject/layout/detail.xml"] == "created"
        assert "#define EGUI_CONFIG_COLOR_DEPTH 32" in designer_config
        assert "#define EGUI_CONFIG_FUNCTION_SUPPORT_SHADOW 1" in designer_config

    def test_ensure_designer_project_scaffold_with_sdk_root_only_creates_missing_dirs(self, tmp_path):
        sdk_root = tmp_path / "sdk" / "EmbeddedGUI"
        existing_dir = sdk_root / "example" / "ExistingApp"
        new_dir = sdk_root / "example" / "NewApp"
        existing_dir.mkdir(parents=True)

        existing_created, existing_actions = ensure_designer_project_scaffold_with_sdk_root(
            str(existing_dir),
            "ExistingApp",
            str(sdk_root),
            320,
            240,
            **designer_scaffold_kwargs(
                320,
                240,
                overwrite=True,
            ),
        )
        new_created, new_actions = ensure_designer_project_scaffold_with_sdk_root(
            str(new_dir),
            "NewApp",
            str(sdk_root),
            320,
            240,
            **designer_scaffold_kwargs(
                320,
                240,
                overwrite=True,
            ),
        )

        assert existing_created is False
        assert existing_actions == {}
        assert new_created is True
        assert new_actions[BUILD_MK_RELPATH] == "created"
        assert new_actions["NewApp.egui"] == "created"
        assert (new_dir / ".designer" / "build_designer.mk").is_file()

    def test_ensure_conversion_project_scaffold_with_sdk_root_only_creates_missing_dirs(self, tmp_path):
        sdk_root = tmp_path / "sdk" / "EmbeddedGUI"
        existing_dir = sdk_root / "example" / "ExistingConversionApp"
        new_dir = sdk_root / "example" / "NewConversionApp"
        existing_dir.mkdir(parents=True)

        existing_created, existing_actions = ensure_conversion_project_scaffold_with_sdk_root(
            str(existing_dir),
            "ExistingConversionApp",
            str(sdk_root),
            320,
            240,
        )
        new_created, new_actions = ensure_conversion_project_scaffold_with_sdk_root(
            str(new_dir),
            "NewConversionApp",
            str(sdk_root),
            320,
            240,
            color_depth=32,
        )

        assert existing_created is False
        assert existing_actions == {}
        assert new_created is True
        assert new_actions[BUILD_MK_RELPATH] == "created"
        assert new_actions["NewConversionApp.egui"] == "created"
        designer_config = (new_dir / ".designer" / "app_egui_config_designer.h").read_text(encoding="utf-8")
        assert "#define EGUI_CONFIG_COLOR_DEPTH 32" in designer_config
        assert "#define EGUI_CONFIG_FUNCTION_SUPPORT_SHADOW 1" in designer_config
