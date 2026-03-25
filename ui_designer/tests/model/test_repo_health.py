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
    assert repo_health.critical_repo_health_issues(payload) == [
        "SDK submodule is not initialized",
        "release smoke sample is missing",
    ]


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

    assert "[summary] 1 stale temp dir(s) detected" in rendered
    assert "[counts] critical=0 suggestions=1 stale=1 blocked=1" in rendered
    assert "[view] critical_only=false blocked_only=false" in rendered
    assert f"[repo] {tmp_path}" in rendered
    assert "sdk_submodule.initialized: true" in rendered
    assert "release_smoke.present: true" in rendered
    assert "stale_temp_dirs: 1 (blocked 1)" in rendered
    assert "suggestion: If git status is noisy, use: git status -uno" in rendered


def test_critical_repo_health_issues_empty_for_healthy_payload(tmp_path):
    payload = {
        "repo_root": str(tmp_path),
        "sdk_submodule": {"path": str(tmp_path / "sdk"), "present": True, "initialized": True, "status": "416d576 sdk/EmbeddedGUI"},
        "release_smoke_project": {"path": str(tmp_path / "samples" / "release_smoke" / "ReleaseSmokeApp"), "present": True},
        "stale_temp_dirs": [],
        "git_status_show_untracked": "no",
        "suggestions": [],
    }

    assert repo_health.critical_repo_health_issues(payload) == []


def test_repo_health_view_payload_can_focus_critical_issues(tmp_path):
    payload = {
        "repo_root": str(tmp_path),
        "sdk_submodule": {"path": str(tmp_path / "sdk"), "present": True, "initialized": False, "status": "-416d576 sdk/EmbeddedGUI"},
        "release_smoke_project": {"path": str(tmp_path / "samples" / "release_smoke" / "ReleaseSmokeApp"), "present": False},
        "stale_temp_dirs": [{"path": str(tmp_path / ".pytest-tmp-codex"), "accessible": False, "issue": "permission_denied"}],
        "git_status_show_untracked": "no",
        "suggestions": [
            "Run: git submodule update --init --recursive",
            "If git status is noisy, use: git status -uno",
        ],
    }

    focused = repo_health.repo_health_view_payload(payload, critical_only=True)

    assert focused["repo_root"] == str(tmp_path)
    assert focused["sdk_submodule"]["initialized"] is False
    assert focused["release_smoke_project"]["present"] is False
    assert focused["stale_temp_dirs"] == []
    assert focused["critical_issues"] == [
        "SDK submodule is not initialized",
        "release smoke sample is missing",
    ]
    assert focused["suggestions"] == [
        "Run: git submodule update --init --recursive",
        "Restore samples/release_smoke/ReleaseSmokeApp before running release smoke checks",
    ]


def test_repo_health_view_payload_can_focus_blocked_stale_dirs(tmp_path):
    payload = {
        "repo_root": str(tmp_path),
        "sdk_submodule": {"path": str(tmp_path / "sdk"), "present": True, "initialized": False, "status": "-416d576 sdk/EmbeddedGUI"},
        "release_smoke_project": {"path": str(tmp_path / "samples" / "release_smoke" / "ReleaseSmokeApp"), "present": False},
        "stale_temp_dirs": [
            {"path": str(tmp_path / ".pytest-tmp-codex"), "accessible": True, "issue": ""},
            {"path": str(tmp_path / "tmpxtayw0f6"), "accessible": False, "issue": "permission_denied"},
        ],
        "git_status_show_untracked": "no",
        "suggestions": [
            "Run: git submodule update --init --recursive",
            "If git status is noisy, use: git status -uno",
            "Restore samples/release_smoke/ReleaseSmokeApp before running release smoke checks",
        ],
    }

    focused = repo_health.repo_health_view_payload(payload, blocked_only=True)

    assert focused["repo_root"] == str(tmp_path)
    assert focused["sdk_submodule"]["initialized"] is False
    assert focused["release_smoke_project"]["present"] is False
    assert focused["stale_temp_dirs"] == [
        {"path": str(tmp_path / "tmpxtayw0f6"), "accessible": False, "issue": "permission_denied"},
    ]
    assert focused["suggestions"] == [
        "Run: git submodule update --init --recursive",
        "If git status is noisy, use: git status -uno",
        "To hide untracked noise locally, use: git config status.showUntrackedFiles no",
        "Remove stale ACL-broken temp dirs from an elevated shell if they keep reappearing",
        "Restore samples/release_smoke/ReleaseSmokeApp before running release smoke checks",
    ]


def test_repo_health_counts_reports_current_payload_sizes(tmp_path):
    payload = {
        "repo_root": str(tmp_path),
        "sdk_submodule": {"path": str(tmp_path / "sdk"), "present": True, "initialized": False, "status": "-416d576 sdk/EmbeddedGUI"},
        "release_smoke_project": {"path": str(tmp_path / "samples" / "release_smoke" / "ReleaseSmokeApp"), "present": False},
        "stale_temp_dirs": [{"path": str(tmp_path / ".pytest-tmp-codex"), "accessible": False, "issue": "permission_denied"}],
        "git_status_show_untracked": "no",
        "suggestions": ["Run: git submodule update --init --recursive"],
    }

    counts = repo_health.repo_health_counts(payload)

    assert counts == {"critical": 2, "suggestions": 1, "stale_dirs": 1, "blocked_stale_dirs": 1}


def test_format_repo_health_json_includes_metadata(tmp_path):
    import json

    payload = {
        "repo_root": str(tmp_path),
        "sdk_submodule": {"path": str(tmp_path / "sdk"), "present": True, "initialized": False, "status": "-416d576 sdk/EmbeddedGUI"},
        "release_smoke_project": {"path": str(tmp_path / "samples" / "release_smoke" / "ReleaseSmokeApp"), "present": False},
        "stale_temp_dirs": [],
        "git_status_show_untracked": "no",
        "suggestions": ["Run: git submodule update --init --recursive"],
    }

    rendered = json.loads(repo_health.format_repo_health_json(payload, critical_only=True))

    assert rendered["_summary"] == "SDK submodule is not initialized; release smoke sample is missing"
    assert rendered["_counts"] == {"critical": 2, "suggestions": 1, "stale_dirs": 0, "blocked_stale_dirs": 0}
    assert rendered["_view"] == {"critical_only": True, "blocked_only": False}
    assert rendered["repo_root"] == str(tmp_path)


def test_format_repo_health_summary_includes_counts(tmp_path):
    payload = {
        "repo_root": str(tmp_path),
        "sdk_submodule": {"path": str(tmp_path / "sdk"), "present": True, "initialized": False, "status": "-416d576 sdk/EmbeddedGUI"},
        "release_smoke_project": {"path": str(tmp_path / "samples" / "release_smoke" / "ReleaseSmokeApp"), "present": False},
        "stale_temp_dirs": [{"path": str(tmp_path / ".pytest-tmp-codex"), "accessible": False, "issue": "permission_denied"}],
        "git_status_show_untracked": "no",
        "suggestions": ["Run: git submodule update --init --recursive"],
    }

    rendered = repo_health.format_repo_health_summary(payload, critical_only=True)

    assert "SDK submodule is not initialized; release smoke sample is missing; 1 stale temp dir(s) detected" in rendered
    assert "critical=2" in rendered
    assert "suggestions=1" in rendered
    assert "stale=1" in rendered
    assert "blocked=1" in rendered
    assert "critical_only=true" in rendered
    assert "blocked_only=false" in rendered
