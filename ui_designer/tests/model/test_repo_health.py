"""Tests for repository health helpers."""

from __future__ import annotations

import json

from ui_designer.model import repo_health


def _payload(
    tmp_path,
    *,
    sdk_initialized: bool = True,
    stale_temp_dirs: list[dict[str, object]] | None = None,
    suggestions: list[str] | None = None,
    runtime_paths: dict[str, dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "repo_root": str(tmp_path),
        "sdk_submodule": {
            "path": str(tmp_path / "sdk" / "EmbeddedGUI"),
            "present": True,
            "initialized": sdk_initialized,
            "status": "416d576 sdk/EmbeddedGUI" if sdk_initialized else "-416d576 sdk/EmbeddedGUI",
        },
        "runtime_paths": runtime_paths or {},
        "stale_temp_dirs": stale_temp_dirs or [],
        "git_status_show_untracked": "no",
        "suggestions": suggestions or [],
    }


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
    monkeypatch.setattr(repo_health, "collect_runtime_paths", lambda _repo_root: {})
    monkeypatch.setattr(
        repo_health.Path,
        "iterdir",
        lambda self: (_ for _ in ()).throw(PermissionError()) if self == stale_dir else iter(()),
    )

    payload = repo_health.collect_repo_health(repo_root)

    assert payload["sdk_submodule"]["initialized"] is False
    assert set(payload) == {
        "repo_root",
        "sdk_submodule",
        "runtime_paths",
        "stale_temp_dirs",
        "git_status_show_untracked",
        "suggestions",
    }
    assert payload["stale_temp_dirs"] == [
        {"path": str(stale_dir), "accessible": False, "issue": "permission_denied"},
    ]
    assert payload["suggestions"] == [
        "Run: git submodule update --init --recursive",
        "If git status is noisy, use: git status -uno",
        "To hide untracked noise locally, use: git config status.showUntrackedFiles no",
        "Remove stale ACL-broken temp dirs from an elevated shell if they keep reappearing",
    ]
    assert repo_health.summarize_repo_health(payload) == "SDK submodule is not initialized; 1 stale temp dir(s) detected"
    assert repo_health.critical_repo_health_issues(payload) == ["SDK submodule is not initialized"]


def test_inspect_problem_dirs_includes_blocked_temp_subdirectories(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    blocked = repo_root / "temp" / "pytest" / "run-001"
    blocked.mkdir(parents=True)

    original_iterdir = repo_health.Path.iterdir

    def fake_iterdir(self):
        if self == blocked:
            raise PermissionError()
        return original_iterdir(self)

    monkeypatch.setattr(repo_health.Path, "iterdir", fake_iterdir)

    assert repo_health.inspect_problem_dirs(repo_root) == [
        {"path": str(blocked), "accessible": False, "issue": "permission_denied"},
    ]


def test_format_repo_health_text_includes_expected_sections(tmp_path):
    payload = _payload(
        tmp_path,
        stale_temp_dirs=[{"path": str(tmp_path / ".pytest-tmp-codex"), "accessible": False, "issue": "permission_denied"}],
        suggestions=["If git status is noisy, use: git status -uno"],
        runtime_paths={
            "config_dir": {
                "path": str(tmp_path / "config"),
                "exists": False,
                "writable": True,
                "issue": "",
            },
            "pytest_temp_root": {
                "path": str(tmp_path / "pytest"),
                "exists": True,
                "writable": False,
                "issue": "permission_denied",
            },
        },
    )

    rendered = repo_health.format_repo_health_text(payload)

    assert "[summary] config dir is not writable" not in rendered
    assert "[summary] pytest temp root is not writable; 1 stale temp dir(s) detected" in rendered
    assert "[counts] critical=0 suggestions=1 stale=1 blocked=1" in rendered
    assert "[view] critical_only=false blocked_only=false" in rendered
    assert f"[repo] {tmp_path}" in rendered
    assert "sdk_submodule.initialized: true" in rendered
    assert f"runtime_paths.config_dir: path={tmp_path / 'config'} exists=false writable=true" in rendered
    assert (
        f"runtime_paths.pytest_temp_root: path={tmp_path / 'pytest'} exists=true "
        "writable=false issue=permission_denied"
    ) in rendered
    assert "stale_temp_dirs: 1 (blocked 1)" in rendered
    assert "suggestion: If git status is noisy, use: git status -uno" in rendered


def test_critical_repo_health_issues_empty_for_healthy_payload(tmp_path):
    assert repo_health.critical_repo_health_issues(_payload(tmp_path)) == []


def test_repo_health_view_payload_can_focus_critical_issues(tmp_path):
    payload = _payload(
        tmp_path,
        sdk_initialized=False,
        stale_temp_dirs=[{"path": str(tmp_path / ".pytest-tmp-codex"), "accessible": False, "issue": "permission_denied"}],
        suggestions=[
            "Run: git submodule update --init --recursive",
            "If git status is noisy, use: git status -uno",
        ],
    )

    focused = repo_health.repo_health_view_payload(payload, critical_only=True)

    assert focused["repo_root"] == str(tmp_path)
    assert focused["sdk_submodule"]["initialized"] is False
    assert focused["stale_temp_dirs"] == []
    assert focused["critical_issues"] == ["SDK submodule is not initialized"]
    assert focused["suggestions"] == ["Run: git submodule update --init --recursive"]


def test_repo_health_view_payload_can_focus_blocked_stale_dirs(tmp_path):
    payload = _payload(
        tmp_path,
        stale_temp_dirs=[
            {"path": str(tmp_path / ".pytest-tmp-codex"), "accessible": True, "issue": ""},
            {"path": str(tmp_path / "tmpxtayw0f6"), "accessible": False, "issue": "permission_denied"},
        ],
        suggestions=[
            "If git status is noisy, use: git status -uno",
            "To hide untracked noise locally, use: git config status.showUntrackedFiles no",
        ],
    )

    focused = repo_health.repo_health_view_payload(payload, blocked_only=True)

    assert focused["repo_root"] == str(tmp_path)
    assert focused["sdk_submodule"]["initialized"] is True
    assert focused["stale_temp_dirs"] == [
        {"path": str(tmp_path / "tmpxtayw0f6"), "accessible": False, "issue": "permission_denied"},
    ]
    assert focused["suggestions"] == [
        "If git status is noisy, use: git status -uno",
        "To hide untracked noise locally, use: git config status.showUntrackedFiles no",
        "Remove stale ACL-broken temp dirs from an elevated shell if they keep reappearing",
    ]


def test_repo_health_counts_reports_current_payload_sizes(tmp_path):
    counts = repo_health.repo_health_counts(
        _payload(
            tmp_path,
            sdk_initialized=False,
            stale_temp_dirs=[{"path": str(tmp_path / ".pytest-tmp-codex"), "accessible": False, "issue": "permission_denied"}],
            suggestions=["Run: git submodule update --init --recursive"],
        )
    )

    assert counts == {"critical": 1, "suggestions": 1, "stale_dirs": 1, "blocked_stale_dirs": 1}


def test_format_repo_health_json_includes_metadata(tmp_path):
    payload = _payload(
        tmp_path,
        sdk_initialized=False,
        suggestions=["Run: git submodule update --init --recursive"],
    )

    rendered = json.loads(repo_health.format_repo_health_json(payload, critical_only=True))

    assert rendered["_summary"] == "SDK submodule is not initialized"
    assert rendered["_counts"] == {"critical": 1, "suggestions": 1, "stale_dirs": 0, "blocked_stale_dirs": 0}
    assert rendered["_view"] == {"critical_only": True, "blocked_only": False}
    assert rendered["repo_root"] == str(tmp_path)


def test_format_repo_health_summary_includes_counts(tmp_path):
    payload = _payload(
        tmp_path,
        sdk_initialized=False,
        stale_temp_dirs=[{"path": str(tmp_path / ".pytest-tmp-codex"), "accessible": False, "issue": "permission_denied"}],
        suggestions=["Run: git submodule update --init --recursive"],
    )

    rendered = repo_health.format_repo_health_summary(payload, critical_only=True)

    assert "SDK submodule is not initialized; 1 stale temp dir(s) detected" in rendered
    assert "critical=1" in rendered
    assert "suggestions=1" in rendered
    assert "stale=1" in rendered
    assert "blocked=1" in rendered
    assert "critical_only=true" in rendered
    assert "blocked_only=false" in rendered


def test_collect_repo_health_reports_runtime_path_issues(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    def fake_run_git_text(_repo_root, *args):
        if args == ("submodule", "status", "--", str(repo_health.SDK_SUBMODULE_PATH)):
            return "416d576 sdk/EmbeddedGUI"
        if args == ("config", "--get", "status.showUntrackedFiles"):
            return "default"
        return ""

    runtime_paths = {
        "config_dir": {
            "path": str(tmp_path / "config"),
            "exists": False,
            "writable": False,
            "issue": "permission_denied",
        },
        "pytest_temp_root": {
            "path": str(tmp_path / "pytest"),
            "exists": False,
            "writable": False,
            "issue": "permission_denied",
        },
    }

    monkeypatch.setattr(repo_health, "_run_git_text", fake_run_git_text)
    monkeypatch.setattr(repo_health, "collect_runtime_paths", lambda _repo_root: runtime_paths)

    payload = repo_health.collect_repo_health(repo_root)

    assert payload["runtime_paths"] == runtime_paths
    assert repo_health.summarize_repo_health(payload) == "config dir is not writable; pytest temp root is not writable"
    assert any("EMBEDDEDGUI_DESIGNER_CONFIG_DIR" in item for item in payload["suggestions"])
    assert any("--basetemp-root" in item for item in payload["suggestions"])
