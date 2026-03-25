"""Tests for the repository doctor CLI."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_module():
    module_path = Path(__file__).resolve().parents[2] / "scripts" / "ui_designer" / "repo_doctor.py"
    spec = importlib.util.spec_from_file_location("repo_doctor_cli", str(module_path))
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_collect_repo_health_reports_missing_submodule_and_stale_dirs(tmp_path, monkeypatch):
    module = _load_module()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    stale_dir = repo_root / ".pytest-tmp-codex"
    stale_dir.mkdir()

    def fake_run_git_text(_repo_root, *args):
        if args == ("submodule", "status", "--", str(module.SDK_SUBMODULE_PATH)):
            return "-416d576 sdk/EmbeddedGUI"
        if args == ("config", "--get", "status.showUntrackedFiles"):
            return "default"
        return ""

    monkeypatch.setattr(module, "_run_git_text", fake_run_git_text)
    monkeypatch.setattr(module.Path, "iterdir", lambda self: (_ for _ in ()).throw(PermissionError()) if self == stale_dir else iter(()))

    payload = module.collect_repo_health(repo_root)

    assert payload["sdk_submodule"]["initialized"] is False
    assert payload["release_smoke_project"]["present"] is False
    assert payload["stale_temp_dirs"][0]["issue"] == "permission_denied"
    assert any("git submodule update --init --recursive" in item for item in payload["suggestions"])


def test_repo_doctor_main_emits_json(monkeypatch, capsys):
    module = _load_module()
    payload = {
        "repo_root": "D:/repo",
        "sdk_submodule": {"path": "D:/repo/sdk/EmbeddedGUI", "present": True, "initialized": True, "status": " 416d576 sdk/EmbeddedGUI"},
        "release_smoke_project": {"path": "D:/repo/samples/release_smoke/ReleaseSmokeApp", "present": True},
        "stale_temp_dirs": [],
        "git_status_show_untracked": "no",
        "suggestions": [],
    }

    monkeypatch.setattr(module, "_parse_args", lambda: type("Args", (), {"json": True})())
    monkeypatch.setattr(module, "collect_repo_health", lambda: payload)

    exit_code = module.main()
    content = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert content["repo_root"] == "D:/repo"
    assert content["sdk_submodule"]["initialized"] is True
