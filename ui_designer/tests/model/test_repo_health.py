"""Tests for repository health helpers."""

from __future__ import annotations

from pathlib import Path

from ui_designer.model import repo_health


def test_collect_repo_health_reports_missing_submodule_and_stale_dirs(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    stale_dir = repo_root / ".pytest-tmp-codex"
    stale_dir.mkdir()

    def fake_run_git_text(_repo_root, *args):
        if args == ("submodule", "status", "--", str(repo_health.SDK_SUBMODULE_PATH)):
            return "-416d576 sdk/EmbeddedGUI"
        if args == ("config", "--get", "status.showUntrackedFiles"):
            return "default"
        return ""

    monkeypatch.setattr(repo_health, "_run_git_text", fake_run_git_text)
    monkeypatch.setattr(repo_health.Path, "iterdir", lambda self: (_ for _ in ()).throw(PermissionError()) if self == stale_dir else iter(()))

    payload = repo_health.collect_repo_health(repo_root)

    assert payload["sdk_submodule"]["initialized"] is False
    assert payload["release_smoke_project"]["present"] is False
    assert payload["stale_temp_dirs"][0]["issue"] == "permission_denied"
    assert any("git submodule update --init --recursive" in item for item in payload["suggestions"])
    assert "stale temp dir" in repo_health.summarize_repo_health(payload)


def test_format_repo_health_text_includes_expected_sections(tmp_path):
    payload = {
        "repo_root": str(tmp_path),
        "sdk_submodule": {
            "path": str(tmp_path / "sdk" / "EmbeddedGUI"),
            "present": True,
            "initialized": True,
            "status": "416d576 sdk/EmbeddedGUI",
        },
        "release_smoke_project": {
            "path": str(tmp_path / "samples" / "release_smoke" / "ReleaseSmokeApp"),
            "present": True,
        },
        "stale_temp_dirs": [{"path": str(tmp_path / ".pytest-tmp-codex"), "accessible": False, "issue": "permission_denied"}],
        "git_status_show_untracked": "no",
        "suggestions": ["If git status is noisy, use: git status -uno"],
    }

    rendered = repo_health.format_repo_health_text(payload)

    assert f"[repo] {tmp_path}" in rendered
    assert "sdk_submodule.initialized: true" in rendered
    assert "release_smoke.present: true" in rendered
    assert "stale_temp_dirs: 1" in rendered
    assert "suggestion: If git status is noisy, use: git status -uno" in rendered
