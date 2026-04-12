from pathlib import Path

from ui_designer.utils.runtime_temp import create_temp_workspace, repo_temp_dir


class TestRuntimeTempHelpers:
    def test_repo_temp_dir_uses_repo_temp_subdir(self, tmp_path):
        repo_root = tmp_path / "repo"
        repo_root.mkdir()

        assert repo_temp_dir(repo_root) == repo_root.resolve() / "temp"
        assert repo_temp_dir(repo_root, "preview_smoke") == repo_root.resolve() / "temp" / "preview_smoke"

    def test_create_temp_workspace_creates_directory_under_parent(self, tmp_path):
        parent = tmp_path / "parent"

        workspace = create_temp_workspace(parent, "demo_")

        assert workspace.is_dir()
        assert workspace.parent == parent.resolve()
        assert workspace.name.startswith("demo_")
