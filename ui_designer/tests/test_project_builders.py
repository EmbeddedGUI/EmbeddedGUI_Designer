"""Tests for shared test project builders."""

from ui_designer.tests.page_builders import build_test_pages
from ui_designer.tests.project_builders import (
    build_saved_test_project,
    build_test_project,
    build_test_project_with_page_roots,
    build_test_project_with_root,
    build_test_project_from_pages,
)
from ui_designer.utils.scaffold import require_project_page_root


class TestProjectBuilders:
    def test_build_test_project_uses_shared_empty_project_model(self):
        project = build_test_project(
            "BuilderDemo",
            320,
            240,
            sdk_root="D:/sdk",
            project_dir="D:/workspace/BuilderDemo",
            pages=["home", "detail"],
        )
        page, root = require_project_page_root(project)

        assert project.app_name == "BuilderDemo"
        assert project.startup_page == "home"
        assert [page.name for page in project.pages] == ["home", "detail"]
        assert page.name == "home"
        assert root.width == 320
        assert root.height == 240

    def test_build_saved_test_project_writes_project_on_disk(self, tmp_path):
        project_dir = tmp_path / "SavedBuilderDemo"

        project = build_saved_test_project(project_dir, "SavedBuilderDemo", pages=["main_page", "settings"])

        assert project.project_dir == str(project_dir)
        assert (project_dir / "SavedBuilderDemo.egui").is_file()
        assert (project_dir / ".eguiproject" / "layout" / "main_page.xml").is_file()
        assert (project_dir / ".eguiproject" / "layout" / "settings.xml").is_file()

    def test_build_saved_test_project_can_include_designer_scaffold(self, tmp_path):
        project_dir = tmp_path / "ScaffoldedSavedBuilderDemo"

        project = build_saved_test_project(
            project_dir,
            "ScaffoldedSavedBuilderDemo",
            pages=["main_page", "settings"],
            with_designer_scaffold=True,
        )

        assert project.project_dir == str(project_dir)
        assert (project_dir / "ScaffoldedSavedBuilderDemo.egui").is_file()
        assert (project_dir / ".eguiproject" / "layout" / "main_page.xml").is_file()
        assert (project_dir / "build.mk").is_file()
        assert (project_dir / "app_egui_config.h").is_file()
        assert (project_dir / ".designer" / "build_designer.mk").is_file()
        assert (project_dir / ".designer" / "app_egui_config_designer.h").is_file()
        assert (project_dir / "resource" / "src" / "app_resource_config.json").is_file()
        assert (project_dir / "resource" / "src" / ".designer" / "app_resource_config_designer.json").is_file()

    def test_build_test_project_from_pages_preserves_page_mode_and_startup(self):
        home_page, detail_page = build_test_pages("home", "detail")

        project = build_test_project_from_pages(
            [home_page, detail_page],
            app_name="BuilderDemo",
            page_mode="activity",
            startup_page="detail",
        )

        assert project.app_name == "BuilderDemo"
        assert project.page_mode == "activity"
        assert project.startup_page == "detail"
        assert [page.name for page in project.pages] == ["home", "detail"]

    def test_build_test_project_from_pages_accepts_legacy_startup_alias(self):
        home_page, detail_page = build_test_pages("home", "detail")

        project = build_test_project_from_pages(
            [home_page, detail_page],
            startup="detail",
        )

        assert project.startup_page == "detail"

    def test_build_test_project_with_root_returns_startup_root_widget(self):
        project, root = build_test_project_with_root(
            "RootBuilderDemo",
            page_name="home",
            screen_width=320,
            screen_height=240,
        )
        page, startup_root = require_project_page_root(project)

        assert project.app_name == "RootBuilderDemo"
        assert project.startup_page == "home"
        assert page.name == "home"
        assert root is startup_root
        assert root.width == 320
        assert root.height == 240

    def test_build_test_project_with_page_roots_returns_all_named_roots(self):
        project, roots = build_test_project_with_page_roots(
            "MultiRootBuilderDemo",
            pages=["home", "detail"],
            screen_width=320,
            screen_height=240,
        )

        assert project.app_name == "MultiRootBuilderDemo"
        assert project.startup_page == "home"
        assert list(roots) == ["home", "detail"]
        assert roots["home"].width == 320
        assert roots["detail"].height == 240
