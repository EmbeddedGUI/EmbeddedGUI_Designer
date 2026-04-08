"""Tests for the repository doctor CLI."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_module():
    module_path = Path(__file__).resolve().parents[2] / "scripts" / "ui_designer" / "repo_doctor.py"
    spec = importlib.util.spec_from_file_location("repo_doctor_cli", str(module_path))
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _payload(*, initialized: bool, stale_temp_dirs: list[dict[str, object]] | None = None, suggestions: list[str] | None = None):
    return {
        "repo_root": "D:/repo",
        "sdk_submodule": {
            "path": "D:/repo/sdk/EmbeddedGUI",
            "present": True,
            "initialized": initialized,
            "status": "416d576 sdk/EmbeddedGUI" if initialized else "-416d576 sdk/EmbeddedGUI",
        },
        "runtime_paths": {},
        "stale_temp_dirs": stale_temp_dirs or [],
        "git_status_show_untracked": "default",
        "suggestions": suggestions or [],
    }


def test_repo_doctor_main_emits_json(monkeypatch, capsys):
    module = _load_module()
    payload = _payload(initialized=True)

    monkeypatch.setattr(module, "_parse_args", lambda: type("Args", (), {"json": True, "summary": False, "critical_only": False, "blocked_only": False, "strict": False})())
    monkeypatch.setattr(module, "collect_repo_health", lambda: payload)
    monkeypatch.setattr(module, "repo_health_view_payload", lambda arg, critical_only=False, blocked_only=False: arg)
    monkeypatch.setattr(module, "format_repo_health_json", lambda arg, critical_only=False, blocked_only=False: '{"repo_root": "D:/repo", "sdk_submodule": {"initialized": true}}')

    exit_code = module.main()
    content = capsys.readouterr().out

    assert exit_code == 0
    assert '"repo_root": "D:/repo"' in content
    assert '"initialized": true' in content


def test_repo_doctor_main_emits_human_text(monkeypatch, capsys):
    module = _load_module()
    payload = _payload(initialized=False, suggestions=["Run: git submodule update --init --recursive"])

    monkeypatch.setattr(module, "_parse_args", lambda: type("Args", (), {"json": False, "summary": False, "critical_only": False, "blocked_only": False, "strict": False})())
    monkeypatch.setattr(module, "collect_repo_health", lambda: payload)
    monkeypatch.setattr(module, "repo_health_view_payload", lambda arg, critical_only=False, blocked_only=False: arg)
    monkeypatch.setattr(module, "format_repo_health_text", lambda arg, critical_only=False, blocked_only=False: "[repo] D:/repo\nsdk_submodule.initialized: false")

    exit_code = module.main()
    content = capsys.readouterr().out

    assert exit_code == 0
    assert "[repo] D:/repo" in content
    assert "sdk_submodule.initialized: false" in content


def test_repo_doctor_main_strict_returns_nonzero(monkeypatch, capsys):
    module = _load_module()
    payload = _payload(initialized=False)

    monkeypatch.setattr(module, "_parse_args", lambda: type("Args", (), {"json": True, "summary": False, "critical_only": False, "blocked_only": False, "strict": True})())
    monkeypatch.setattr(module, "collect_repo_health", lambda: payload)
    monkeypatch.setattr(module, "repo_health_view_payload", lambda arg, critical_only=False, blocked_only=False: arg)
    monkeypatch.setattr(module, "format_repo_health_json", lambda arg, critical_only=False, blocked_only=False: '{"repo_root": "D:/repo"}')
    monkeypatch.setattr(module, "critical_repo_health_issues", lambda arg: ["SDK submodule is not initialized"])

    exit_code = module.main()
    content = capsys.readouterr().out

    assert exit_code == module.EXIT_HEALTH_ERROR
    assert '"repo_root": "D:/repo"' in content


def test_repo_doctor_main_can_focus_critical_output(monkeypatch, capsys):
    module = _load_module()
    payload = _payload(
        initialized=False,
        stale_temp_dirs=[{"path": "D:/repo/.pytest-tmp-codex", "accessible": False, "issue": "permission_denied"}],
    )
    focused = {
        **payload,
        "stale_temp_dirs": [],
        "suggestions": ["Run: git submodule update --init --recursive"],
        "critical_issues": ["SDK submodule is not initialized"],
    }

    monkeypatch.setattr(module, "_parse_args", lambda: type("Args", (), {"json": False, "summary": False, "critical_only": True, "blocked_only": False, "strict": False})())
    monkeypatch.setattr(module, "collect_repo_health", lambda: payload)
    monkeypatch.setattr(module, "repo_health_view_payload", lambda arg, critical_only=False, blocked_only=False: focused if critical_only else arg)
    monkeypatch.setattr(module, "format_repo_health_text", lambda arg, critical_only=False, blocked_only=False: f"critical_only={critical_only}\nblocked_only={blocked_only}\nstale_temp_dirs={len(arg['stale_temp_dirs'])}")

    exit_code = module.main()
    content = capsys.readouterr().out

    assert exit_code == 0
    assert "critical_only=True" in content
    assert "blocked_only=False" in content
    assert "stale_temp_dirs=0" in content


def test_repo_doctor_main_can_focus_blocked_output(monkeypatch, capsys):
    module = _load_module()
    payload = _payload(
        initialized=True,
        stale_temp_dirs=[
            {"path": "D:/repo/.pytest-tmp-codex", "accessible": True, "issue": ""},
            {"path": "D:/repo/tmpxtayw0f6", "accessible": False, "issue": "permission_denied"},
        ],
    )
    focused = {
        **payload,
        "stale_temp_dirs": [{"path": "D:/repo/tmpxtayw0f6", "accessible": False, "issue": "permission_denied"}],
        "suggestions": ["If git status is noisy, use: git status -uno"],
    }

    monkeypatch.setattr(module, "_parse_args", lambda: type("Args", (), {"json": False, "summary": False, "critical_only": False, "blocked_only": True, "strict": False})())
    monkeypatch.setattr(module, "collect_repo_health", lambda: payload)
    monkeypatch.setattr(module, "repo_health_view_payload", lambda arg, critical_only=False, blocked_only=False: focused if blocked_only else arg)
    monkeypatch.setattr(module, "format_repo_health_text", lambda arg, critical_only=False, blocked_only=False: f"critical_only={critical_only}\nblocked_only={blocked_only}\nstale_temp_dirs={len(arg['stale_temp_dirs'])}")

    exit_code = module.main()
    content = capsys.readouterr().out

    assert exit_code == 0
    assert "critical_only=False" in content
    assert "blocked_only=True" in content
    assert "stale_temp_dirs=1" in content


def test_repo_doctor_main_can_emit_summary(monkeypatch, capsys):
    module = _load_module()
    payload = _payload(initialized=False)

    monkeypatch.setattr(module, "_parse_args", lambda: type("Args", (), {"json": False, "summary": True, "critical_only": True, "blocked_only": False, "strict": False})())
    monkeypatch.setattr(module, "collect_repo_health", lambda: payload)
    monkeypatch.setattr(module, "repo_health_view_payload", lambda arg, critical_only=False, blocked_only=False: arg)
    monkeypatch.setattr(module, "format_repo_health_summary", lambda arg, critical_only=False, blocked_only=False: f"summary critical_only={critical_only} blocked_only={blocked_only}")

    exit_code = module.main()
    content = capsys.readouterr().out

    assert exit_code == 0
    assert "summary critical_only=True" in content
    assert "blocked_only=False" in content
