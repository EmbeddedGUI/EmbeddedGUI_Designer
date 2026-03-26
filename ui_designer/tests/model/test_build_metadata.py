from ui_designer.model import build_metadata


def test_run_git_text_returns_empty_on_oserror(monkeypatch, tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    monkeypatch.setattr(build_metadata.shutil, "which", lambda name: "git.exe" if name == "git" else "")

    def _raise_oserror(*args, **kwargs):
        raise OSError("handles unavailable")

    monkeypatch.setattr(build_metadata, "_subprocess_run", _raise_oserror)

    assert build_metadata._run_git_text(repo_root, "rev-parse", "HEAD") == ""
