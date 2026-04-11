import os

from ui_designer.utils.scaffold import (
    APP_CONFIG_DESIGNER_RELPATH,
    APP_CONFIG_RELPATH,
    BUILD_DESIGNER_RELPATH,
    BUILD_MK_RELPATH,
    DESIGNER_RESOURCE_CONFIG_RELPATH,
    DESIGNER_CODEGEN_STALE_STRING_RELPATHS,
    RESOURCE_CATALOG_RELPATH,
    RESOURCE_CONFIG_RELPATH,
    apply_designer_project_scaffold,
    build_empty_project_model,
    build_empty_project_model_with_root,
    build_empty_project_xml,
    default_scaffold_circle_radius,
    require_project_page_root,
    normalize_scaffold_pages,
    project_file_relpath,
    project_layout_xml_relpath,
    scaffold_designer_project,
    sync_project_scaffold_core_files,
    legacy_designer_codegen_cleanup_relpaths,
    sync_project_scaffold_sidecars,
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
        assert project_file_relpath("DemoApp") == "DemoApp.egui"
        assert project_layout_xml_relpath("main_page") == ".eguiproject/layout/main_page.xml"
        assert default_scaffold_circle_radius(320, 240) == 120

    def test_build_empty_project_model_creates_default_startup_page(self):
        project = build_empty_project_model(
            "DemoApp",
            320,
            240,
            sdk_root="D:/sdk",
            project_dir="D:/workspace/DemoApp",
            pages=["home", "settings"],
        )

        assert project.sdk_root == os.path.normpath("D:/sdk")
        assert project.project_dir == os.path.normpath("D:/workspace/DemoApp")
        assert project.startup_page == "home"
        assert [page.name for page in project.pages] == ["home", "settings"]
        assert project.get_startup_page().root_widget.width == 320
        assert project.get_startup_page().root_widget.height == 240

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
        assert (project_dir / ".eguiproject" / "resources" / "resources.xml").is_file()
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
