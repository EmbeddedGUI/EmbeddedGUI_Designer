"""Tests for destructive project reconstruction cleanup."""

import os
from pathlib import Path

import pytest

from ui_designer.model.project_cleaner import (
    DESIGNER_RECONSTRUCT_DELETE_SUMMARY,
    DESIGNER_SOURCE_PRESERVE_SUMMARY,
    clean_project_for_reconstruct,
    _remove_path,
)
from ui_designer.utils.resource_config_overlay import DESIGNER_RESOURCE_DIRNAME
from ui_designer.utils.scaffold import (
    APP_CONFIG_RELPATH,
    BACKUP_DIR_RELPATH,
    BUILD_MK_RELPATH,
    DESIGNER_PROJECT_DIRNAME,
    LAYOUT_DIR_RELPATH,
    MOCKUP_DIR_RELPATH,
    ORPHANED_USER_CODE_DIR_RELPATH,
    RELEASE_CONFIG_RELPATH,
    RESOURCE_CONFIG_RELPATH,
    RESOURCE_DIR_RELPATH,
    RESOURCE_FONT_DIR_RELPATH,
    RESOURCE_IMG_DIR_RELPATH,
    RESOURCE_SRC_DIR_RELPATH,
    SUPPORTED_TEXT_RELPATH,
    project_resource_catalog_path,
)


class TestProjectCleaner:
    def test_cleanup_summaries_stay_aligned_with_shared_scaffold_paths(self):
        assert f"{BUILD_MK_RELPATH} and {APP_CONFIG_RELPATH} user override wrappers" in DESIGNER_SOURCE_PRESERVE_SUMMARY
        assert "project-root custom user code files outside Designer-managed page outputs" in DESIGNER_SOURCE_PRESERVE_SUMMARY
        assert f"{RESOURCE_CONFIG_RELPATH} user overlay config" in DESIGNER_SOURCE_PRESERVE_SUMMARY
        assert f"{SUPPORTED_TEXT_RELPATH} extracted charset text" in DESIGNER_SOURCE_PRESERVE_SUMMARY
        assert f"{RESOURCE_SRC_DIR_RELPATH}/** non-designer app resource sources" in DESIGNER_SOURCE_PRESERVE_SUMMARY
        assert f"{LAYOUT_DIR_RELPATH}/*.xml page layouts" in DESIGNER_SOURCE_PRESERVE_SUMMARY
        assert f"{RESOURCE_DIR_RELPATH}/** source assets and resource metadata" in DESIGNER_SOURCE_PRESERVE_SUMMARY
        assert f"{MOCKUP_DIR_RELPATH}/** preview mockups" in DESIGNER_SOURCE_PRESERVE_SUMMARY
        assert f"{ORPHANED_USER_CODE_DIR_RELPATH}/** archived user page code" in DESIGNER_SOURCE_PRESERVE_SUMMARY
        assert f"{RELEASE_CONFIG_RELPATH} release packaging profiles" in DESIGNER_SOURCE_PRESERVE_SUMMARY
        assert (
            f"{RESOURCE_IMG_DIR_RELPATH}, {RESOURCE_FONT_DIR_RELPATH}, and other synced/generated resource outputs"
            in DESIGNER_RECONSTRUCT_DELETE_SUMMARY
        )
        assert (
            f"{RESOURCE_SRC_DIR_RELPATH}/{DESIGNER_RESOURCE_DIRNAME}/** designer-generated resource metadata"
            in DESIGNER_RECONSTRUCT_DELETE_SUMMARY
        )
        assert (
            f"{DESIGNER_PROJECT_DIRNAME}/** generated code and scaffold files (legacy root designer files also removed)"
            in DESIGNER_RECONSTRUCT_DELETE_SUMMARY
        )
        assert (
            f"{BACKUP_DIR_RELPATH} and other generated caches"
            in DESIGNER_RECONSTRUCT_DELETE_SUMMARY
        )

    def test_clean_project_for_reconstruct_preserves_designer_state_and_deletes_outputs(self, tmp_path):
        project_dir = tmp_path / "CleanAllDemo"
        (project_dir / ".eguiproject" / "layout").mkdir(parents=True)
        (project_dir / ".eguiproject" / "resources" / "images").mkdir(parents=True)
        (project_dir / ".eguiproject" / "mockup").mkdir(parents=True)
        (project_dir / ".eguiproject" / "backup" / "old").mkdir(parents=True)
        (project_dir / ".eguiproject" / "orphaned_user_code" / "main_page").mkdir(parents=True)
        (project_dir / "resource" / "src").mkdir(parents=True)
        (project_dir / "resource" / "img").mkdir(parents=True)
        (project_dir / "widgets").mkdir()
        (project_dir / "custom_widgets").mkdir()
        (project_dir / "feature").mkdir()
        (project_dir / "notes").mkdir()

        (project_dir / "CleanAllDemo.egui").write_text("<Project />\n", encoding="utf-8")
        (project_dir / ".eguiproject" / "layout" / "main_page.xml").write_text("<Page />\n", encoding="utf-8")
        Path(project_resource_catalog_path(str(project_dir))).write_text("<resources />\n", encoding="utf-8")
        (project_dir / ".eguiproject" / "resources" / "images" / "hero.png").write_bytes(b"PNG")
        (project_dir / ".eguiproject" / "mockup" / "screen.png").write_bytes(b"PNG")
        (project_dir / ".eguiproject" / "release.json").write_text('{"schema_version": 1}\n', encoding="utf-8")
        (project_dir / "widgets" / "egui_view_chip.h").write_text("// header\n", encoding="utf-8")
        (project_dir / "widgets" / "egui_view_chip.c").write_text("// source\n", encoding="utf-8")
        (project_dir / "custom_widgets" / "chip.py").write_text("descriptor = {}\n", encoding="utf-8")

        (project_dir / "main_page.c").write_text("// generated\n", encoding="utf-8")
        (project_dir / "local.c").write_text("int local(void) { return 1; }\n", encoding="utf-8")
        (project_dir / "local.h").write_text("#define LOCAL_FLAG 1\n", encoding="utf-8")
        (project_dir / "legacy_logic.h").write_text("#define LEGACY_LOGIC 1\n", encoding="utf-8")
        (project_dir / "uicode.h").write_text("// generated\n", encoding="utf-8")
        (project_dir / "build.mk").write_text(
            "EGUI_CODE_SRC += main_page.c\nEGUI_CODE_SRC += local.c\nEGUI_CODE_SRC += feature\nEGUI_CODE_INCLUDE += feature\n",
            encoding="utf-8",
        )
        (project_dir / "app_egui_config.h").write_text("#define EGUI_CONFIG_SCEEN_WIDTH 240\n", encoding="utf-8")
        (project_dir / ".designer").mkdir()
        (project_dir / ".designer" / "main_page.h").write_text("// generated\n", encoding="utf-8")
        (project_dir / ".designer" / "main_page_layout.c").write_text("// generated\n", encoding="utf-8")
        (project_dir / ".designer" / "uicode.h").write_text("// generated\n", encoding="utf-8")
        (project_dir / ".designer" / "build_designer.mk").write_text("EGUI_CODE_SRC += $(EGUI_APP_PATH)\n", encoding="utf-8")
        (project_dir / ".designer" / "app_egui_config_designer.h").write_text("#define EGUI_CONFIG_SCEEN_WIDTH 240\n", encoding="utf-8")
        (project_dir / "resource" / "src" / "app_resource_config.json").write_text("{}\n", encoding="utf-8")
        (project_dir / "resource" / "src" / "supported_text.txt").write_text("abc123\n", encoding="utf-8")
        (project_dir / "resource" / "src" / ".designer").mkdir()
        (project_dir / "resource" / "src" / ".designer" / "app_resource_config_designer.json").write_text("{}\n", encoding="utf-8")
        (project_dir / "resource" / "src" / ".designer" / ".app_resource_config_merged.json").write_text("{}\n", encoding="utf-8")
        (project_dir / "resource" / "img" / "generated.c").write_text("// generated\n", encoding="utf-8")
        (project_dir / ".eguiproject" / "backup" / "old" / "main_page.c").write_text("// backup\n", encoding="utf-8")
        (project_dir / ".eguiproject" / "orphaned_user_code" / "main_page" / "main_page.c").write_text("// orphan\n", encoding="utf-8")
        (project_dir / "feature" / "helper.c").write_text("int helper(void) { return 1; }\n", encoding="utf-8")
        (project_dir / "feature" / "helper.h").write_text("#define FEATURE_HELPER 1\n", encoding="utf-8")
        (project_dir / "notes" / "todo.txt").write_text("remove me\n", encoding="utf-8")

        report = clean_project_for_reconstruct(str(project_dir))

        assert (project_dir / "CleanAllDemo.egui").is_file()
        assert (project_dir / ".eguiproject" / "layout" / "main_page.xml").is_file()
        assert Path(project_resource_catalog_path(str(project_dir))).is_file()
        assert (project_dir / ".eguiproject" / "resources" / "images" / "hero.png").is_file()
        assert (project_dir / ".eguiproject" / "mockup" / "screen.png").is_file()
        assert (project_dir / ".eguiproject" / "release.json").is_file()
        assert (project_dir / "widgets" / "egui_view_chip.h").is_file()
        assert (project_dir / "widgets" / "egui_view_chip.c").is_file()
        assert (project_dir / "custom_widgets" / "chip.py").is_file()
        assert (project_dir / "feature" / "helper.c").is_file()
        assert (project_dir / "feature" / "helper.h").is_file()
        assert (project_dir / "build.mk").is_file()
        assert (project_dir / "app_egui_config.h").is_file()
        assert (project_dir / "local.c").is_file()
        assert (project_dir / "local.h").is_file()
        assert (project_dir / "legacy_logic.h").is_file()
        assert (project_dir / "resource").is_dir()
        assert (project_dir / "resource" / "src").is_dir()
        assert (project_dir / "resource" / "src" / "app_resource_config.json").is_file()
        assert (project_dir / "resource" / "src" / "supported_text.txt").is_file()
        assert (project_dir / ".eguiproject" / "orphaned_user_code" / "main_page" / "main_page.c").is_file()

        assert not (project_dir / "main_page.c").exists()
        assert not (project_dir / "uicode.h").exists()
        assert not (project_dir / ".designer").exists()
        assert not (project_dir / "resource" / "src" / ".designer").exists()
        assert not (project_dir / "resource" / "img").exists()
        assert not (project_dir / ".eguiproject" / "backup").exists()
        assert not (project_dir / "notes").exists()

        assert report.removed_files == 2
        assert report.removed_dirs == 5
        assert "CleanAllDemo.egui" in report.preserved_paths
        assert "resource" in report.preserved_paths
        assert "resource/src" in report.preserved_paths
        assert "resource/src/app_resource_config.json" in report.preserved_paths
        assert SUPPORTED_TEXT_RELPATH in report.preserved_paths
        assert ".eguiproject/layout" in report.preserved_paths
        assert ".eguiproject/resources" in report.preserved_paths
        assert ".eguiproject/mockup" in report.preserved_paths
        assert ".eguiproject/orphaned_user_code" in report.preserved_paths
        assert ".eguiproject/release.json" in report.preserved_paths
        assert "build.mk" in report.preserved_paths
        assert "app_egui_config.h" in report.preserved_paths
        assert "local.c" in report.preserved_paths
        assert "local.h" in report.preserved_paths
        assert "legacy_logic.h" in report.preserved_paths
        assert "widgets" in report.preserved_paths
        assert "custom_widgets" in report.preserved_paths
        assert "feature" in report.preserved_paths
        assert "resource/img" in report.removed_paths
        assert ".designer" in report.removed_paths
        assert "resource/src/.designer" in report.removed_paths
        assert ".eguiproject/backup" in report.removed_paths
        assert "main_page.c" in report.removed_paths
        assert "notes" in report.removed_paths

    def test_clean_project_for_reconstruct_preserves_non_designer_resource_source_files(self, tmp_path):
        project_dir = tmp_path / "ResourceSourceCleanDemo"
        source_dir = project_dir / "resource" / "src"
        nested_dir = source_dir / "custom_assets"
        nested_dir.mkdir(parents=True)
        (project_dir / ".eguiproject" / "layout").mkdir(parents=True)

        (project_dir / "ResourceSourceCleanDemo.egui").write_text("<Project />\n", encoding="utf-8")
        (project_dir / ".eguiproject" / "layout" / "main_page.xml").write_text("<Page />\n", encoding="utf-8")
        (source_dir / "app_resource_config.json").write_text("{}\n", encoding="utf-8")
        (source_dir / "supported_text.txt").write_text("abc\n", encoding="utf-8")
        (source_dir / "user_palette.txt").write_text("palette\n", encoding="utf-8")
        (nested_dir / "hero.png").write_bytes(b"PNG")
        (nested_dir / "notes.txt").write_text("notes\n", encoding="utf-8")
        (nested_dir / "_generated_text_preview.png").write_bytes(b"BAD")
        (source_dir / ".designer").mkdir()
        (source_dir / ".designer" / "app_resource_config_designer.json").write_text("{}\n", encoding="utf-8")

        report = clean_project_for_reconstruct(str(project_dir))

        assert (source_dir / "app_resource_config.json").is_file()
        assert (source_dir / "supported_text.txt").is_file()
        assert (source_dir / "user_palette.txt").is_file()
        assert (nested_dir / "hero.png").is_file()
        assert (nested_dir / "notes.txt").is_file()
        assert not (nested_dir / "_generated_text_preview.png").exists()
        assert not (source_dir / ".designer").exists()
        assert "resource/src/custom_assets" in report.preserved_paths
        assert "resource/src/custom_assets/hero.png" in report.preserved_paths
        assert "resource/src/custom_assets/notes.txt" in report.preserved_paths
        assert "resource/src/custom_assets/_generated_text_preview.png" in report.removed_paths
        assert "resource/src/.designer" in report.removed_paths

    def test_clean_project_for_reconstruct_removes_legacy_designer_wrapper_files(self, tmp_path):
        project_dir = tmp_path / "LegacyWrapperCleanupDemo"
        (project_dir / ".eguiproject" / "layout").mkdir(parents=True)
        (project_dir / "resource" / "src").mkdir(parents=True)

        (project_dir / "LegacyWrapperCleanupDemo.egui").write_text("<Project />\n", encoding="utf-8")
        (project_dir / ".eguiproject" / "layout" / "main_page.xml").write_text("<Page />\n", encoding="utf-8")
        (project_dir / "build.mk").write_text("include $(EGUI_APP_PATH)/.designer/build_designer.mk\n", encoding="utf-8")
        (project_dir / "app_egui_config.h").write_text('#include ".designer/app_egui_config_designer.h"\n', encoding="utf-8")
        (project_dir / "build_designer.mk").write_text("# legacy designer build\n", encoding="utf-8")
        (project_dir / "app_egui_config_designer.h").write_text("#define LEGACY_CONFIG 1\n", encoding="utf-8")
        (project_dir / "resource" / "src" / "app_resource_config.json").write_text("{ }\n", encoding="utf-8")
        (project_dir / "resource" / "src" / "app_resource_config_designer.json").write_text("{ }\n", encoding="utf-8")

        report = clean_project_for_reconstruct(str(project_dir))

        assert (project_dir / "build.mk").is_file()
        assert (project_dir / "app_egui_config.h").is_file()
        assert (project_dir / "resource" / "src" / "app_resource_config.json").is_file()
        assert not (project_dir / "build_designer.mk").exists()
        assert not (project_dir / "app_egui_config_designer.h").exists()
        assert not (project_dir / "resource" / "src" / "app_resource_config_designer.json").exists()
        assert "build_designer.mk" in report.removed_paths
        assert "app_egui_config_designer.h" in report.removed_paths
        assert "resource/src/app_resource_config_designer.json" in report.removed_paths

    def test_remove_path_unlinks_symlink_without_recursing_into_target(self, tmp_path, monkeypatch):
        project_dir = tmp_path / "LinkCleanupDemo"
        project_dir.mkdir()
        link_path = project_dir / "generated_link"
        removed_paths = []
        calls = []

        monkeypatch.setattr("ui_designer.model.project_cleaner.os.path.islink", lambda path: path == str(link_path))
        monkeypatch.setattr("ui_designer.model.project_cleaner.os.unlink", lambda path: calls.append(path))

        removed_files, removed_dirs = _remove_path(str(project_dir), str(link_path), removed_paths)

        assert removed_files == 1
        assert removed_dirs == 0
        assert calls == [str(link_path)]
        assert removed_paths == ["generated_link"]

    def test_remove_path_allows_internal_symlink_even_if_target_resolves_outside_project(self, tmp_path, monkeypatch):
        project_dir = tmp_path / "LinkCleanupDemo"
        project_dir.mkdir()
        link_path = project_dir / "generated_link"
        removed_paths = []
        calls = []

        monkeypatch.setattr("ui_designer.model.project_cleaner.os.path.islink", lambda path: path == str(link_path))
        monkeypatch.setattr("ui_designer.model.project_cleaner._is_within_project", lambda project_root, path: False)
        monkeypatch.setattr("ui_designer.model.project_cleaner.os.unlink", lambda path: calls.append(path))

        removed_files, removed_dirs = _remove_path(str(project_dir), str(link_path), removed_paths)

        assert removed_files == 1
        assert removed_dirs == 0
        assert calls == [str(link_path)]
        assert removed_paths == ["generated_link"]

    def test_remove_path_rejects_paths_outside_project(self, tmp_path):
        project_dir = tmp_path / "SafeProject"
        project_dir.mkdir()
        outside_path = tmp_path / "outside.txt"
        outside_path.write_text("nope\n", encoding="utf-8")

        with pytest.raises(ValueError, match="outside project"):
            _remove_path(str(project_dir), str(outside_path), [])
