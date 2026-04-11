"""Tests for shared test project builders."""

from ui_designer.tests.page_builders import build_test_pages
from ui_designer.tests.project_builders import (
    build_saved_test_project,
    build_test_project,
    build_test_project_from_pages,
)


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

        assert project.app_name == "BuilderDemo"
        assert project.startup_page == "home"
        assert [page.name for page in project.pages] == ["home", "detail"]
        assert project.get_startup_page().root_widget.width == 320
        assert project.get_startup_page().root_widget.height == 240

    def test_build_saved_test_project_writes_project_on_disk(self, tmp_path):
        project_dir = tmp_path / "SavedBuilderDemo"

        project = build_saved_test_project(project_dir, "SavedBuilderDemo", pages=["main_page", "settings"])

        assert project.project_dir == str(project_dir)
        assert (project_dir / "SavedBuilderDemo.egui").is_file()
        assert (project_dir / ".eguiproject" / "layout" / "main_page.xml").is_file()
        assert (project_dir / ".eguiproject" / "layout" / "settings.xml").is_file()

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
