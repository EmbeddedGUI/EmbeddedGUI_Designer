"""Tests for release models and project persistence."""

from __future__ import annotations

from ui_designer.model.project import Project
from ui_designer.model.release import DEFAULT_RELEASE_PROFILE_ID, ReleaseConfig


def test_release_config_round_trip(tmp_path):
    project_dir = tmp_path / "Demo"
    config = ReleaseConfig.default()
    config.save(str(project_dir))

    loaded = ReleaseConfig.load(str(project_dir))

    assert loaded.default_profile == DEFAULT_RELEASE_PROFILE_ID
    assert len(loaded.profiles) == 1
    assert loaded.get_profile().port == "pc"


def test_project_save_writes_release_config_and_load_recovers_it(tmp_path):
    project_dir = tmp_path / "ProjectDemo"
    project = Project(app_name="ProjectDemo")
    project.create_new_page("main_page")
    project.save(str(project_dir))

    release_path = project_dir / ".eguiproject" / "release.json"
    assert release_path.is_file()

    loaded = Project.load(str(project_dir))

    assert loaded.release_config.default_profile == DEFAULT_RELEASE_PROFILE_ID
    assert loaded.release_config.get_profile().package_format == "dir+zip"
