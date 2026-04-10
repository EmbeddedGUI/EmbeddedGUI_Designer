"""Tests for destructive project reconstruction cleanup."""

from ui_designer.model.project_cleaner import clean_project_for_reconstruct


class TestProjectCleaner:
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
        (project_dir / "notes").mkdir()

        (project_dir / "CleanAllDemo.egui").write_text("<Project />\n", encoding="utf-8")
        (project_dir / ".eguiproject" / "layout" / "main_page.xml").write_text("<Page />\n", encoding="utf-8")
        (project_dir / ".eguiproject" / "resources" / "resources.xml").write_text("<resources />\n", encoding="utf-8")
        (project_dir / ".eguiproject" / "resources" / "images" / "hero.png").write_bytes(b"PNG")
        (project_dir / ".eguiproject" / "mockup" / "screen.png").write_bytes(b"PNG")
        (project_dir / ".eguiproject" / "release.json").write_text('{"schema_version": 1}\n', encoding="utf-8")
        (project_dir / "widgets" / "egui_view_chip.h").write_text("// header\n", encoding="utf-8")
        (project_dir / "widgets" / "egui_view_chip.c").write_text("// source\n", encoding="utf-8")
        (project_dir / "custom_widgets" / "chip.py").write_text("descriptor = {}\n", encoding="utf-8")

        (project_dir / "main_page.c").write_text("// generated\n", encoding="utf-8")
        (project_dir / "uicode.h").write_text("// generated\n", encoding="utf-8")
        (project_dir / "build.mk").write_text("EGUI_CODE_SRC += main_page.c\n", encoding="utf-8")
        (project_dir / "app_egui_config.h").write_text("#define EGUI_CONFIG_SCEEN_WIDTH 240\n", encoding="utf-8")
        (project_dir / ".designer").mkdir()
        (project_dir / ".designer" / "main_page.h").write_text("// generated\n", encoding="utf-8")
        (project_dir / ".designer" / "main_page_layout.c").write_text("// generated\n", encoding="utf-8")
        (project_dir / ".designer" / "uicode.h").write_text("// generated\n", encoding="utf-8")
        (project_dir / ".designer" / "build_designer.mk").write_text("EGUI_CODE_SRC += $(EGUI_APP_PATH)\n", encoding="utf-8")
        (project_dir / ".designer" / "app_egui_config_designer.h").write_text("#define EGUI_CONFIG_SCEEN_WIDTH 240\n", encoding="utf-8")
        (project_dir / "resource" / "src" / "app_resource_config.json").write_text("{}\n", encoding="utf-8")
        (project_dir / "resource" / "src" / ".designer").mkdir()
        (project_dir / "resource" / "src" / ".designer" / "app_resource_config_designer.json").write_text("{}\n", encoding="utf-8")
        (project_dir / "resource" / "src" / ".designer" / ".app_resource_config_merged.json").write_text("{}\n", encoding="utf-8")
        (project_dir / "resource" / "img" / "generated.c").write_text("// generated\n", encoding="utf-8")
        (project_dir / ".eguiproject" / "backup" / "old" / "main_page.c").write_text("// backup\n", encoding="utf-8")
        (project_dir / ".eguiproject" / "orphaned_user_code" / "main_page" / "main_page.c").write_text("// orphan\n", encoding="utf-8")
        (project_dir / "notes" / "todo.txt").write_text("remove me\n", encoding="utf-8")

        report = clean_project_for_reconstruct(str(project_dir))

        assert (project_dir / "CleanAllDemo.egui").is_file()
        assert (project_dir / ".eguiproject" / "layout" / "main_page.xml").is_file()
        assert (project_dir / ".eguiproject" / "resources" / "resources.xml").is_file()
        assert (project_dir / ".eguiproject" / "resources" / "images" / "hero.png").is_file()
        assert (project_dir / ".eguiproject" / "mockup" / "screen.png").is_file()
        assert (project_dir / ".eguiproject" / "release.json").is_file()
        assert (project_dir / "widgets" / "egui_view_chip.h").is_file()
        assert (project_dir / "widgets" / "egui_view_chip.c").is_file()
        assert (project_dir / "custom_widgets" / "chip.py").is_file()
        assert (project_dir / "build.mk").is_file()
        assert (project_dir / "app_egui_config.h").is_file()
        assert (project_dir / "resource").is_dir()
        assert (project_dir / "resource" / "src").is_dir()
        assert (project_dir / "resource" / "src" / "app_resource_config.json").is_file()

        assert not (project_dir / "main_page.c").exists()
        assert not (project_dir / "uicode.h").exists()
        assert not (project_dir / ".designer").exists()
        assert not (project_dir / "resource" / "src" / ".designer").exists()
        assert not (project_dir / "resource" / "img").exists()
        assert not (project_dir / ".eguiproject" / "backup").exists()
        assert not (project_dir / ".eguiproject" / "orphaned_user_code").exists()
        assert not (project_dir / "notes").exists()

        assert report.removed_files == 2
        assert report.removed_dirs == 6
        assert "CleanAllDemo.egui" in report.preserved_paths
        assert "resource" in report.preserved_paths
        assert "resource/src" in report.preserved_paths
        assert "resource/src/app_resource_config.json" in report.preserved_paths
        assert ".eguiproject/layout" in report.preserved_paths
        assert ".eguiproject/resources" in report.preserved_paths
        assert ".eguiproject/mockup" in report.preserved_paths
        assert ".eguiproject/release.json" in report.preserved_paths
        assert "build.mk" in report.preserved_paths
        assert "app_egui_config.h" in report.preserved_paths
        assert "widgets" in report.preserved_paths
        assert "custom_widgets" in report.preserved_paths
        assert "resource/img" in report.removed_paths
        assert ".designer" in report.removed_paths
        assert "resource/src/.designer" in report.removed_paths
        assert ".eguiproject/backup" in report.removed_paths
        assert ".eguiproject/orphaned_user_code" in report.removed_paths
        assert "main_page.c" in report.removed_paths
        assert "notes" in report.removed_paths
