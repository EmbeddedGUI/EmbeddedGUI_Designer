"""Tests for the pytest wrapper CLI."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace


def _load_module():
    module_path = Path(__file__).resolve().parents[2] / "scripts" / "ui_designer" / "run_pytest.py"
    spec = importlib.util.spec_from_file_location("run_pytest_cli", str(module_path))
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build_pytest_command_includes_config_and_basetemp(tmp_path):
    module = _load_module()

    command = module.build_pytest_command(
        ["ui_designer/tests/test_release_project_cli.py"],
        basetemp=tmp_path / "tmp",
        extra_args=["-q"],
    )

    assert command[:3] == [module.sys.executable, "-m", "pytest"]
    assert "-c" in command
    assert str(module.DEFAULT_PYTEST_CONFIG) in command
    assert "ui_designer/tests/test_release_project_cli.py" in command
    assert "--basetemp" in command
    assert str((tmp_path / "tmp").resolve()) in command
    assert command[-1] == "-q"


def test_run_pytest_sets_safe_temp_env_and_cleans_directory(tmp_path, monkeypatch):
    module = _load_module()

    captured = {}

    def fake_run(command, cwd, env, check=False):
        captured["command"] = command
        captured["cwd"] = cwd
        captured["env"] = env
        captured["basetemp"] = Path(command[command.index("--basetemp") + 1])
        captured["basetemp"].mkdir(parents=True, exist_ok=True)
        (captured["basetemp"] / "touch.txt").write_text("ok", encoding="utf-8")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    rc = module.run_pytest(
        test_paths=["ui_designer/tests/test_release.py"],
        basetemp_root=tmp_path / "baseroot",
        extra_args=["-q"],
        keep_basetemp=False,
    )

    assert rc == 0
    assert captured["cwd"] == module.REPO_ROOT
    assert captured["env"]["TMP"] == str(captured["basetemp"])
    assert captured["env"]["TEMP"] == str(captured["basetemp"])
    assert captured["env"]["QT_QPA_PLATFORM"] == "offscreen"
    assert not captured["basetemp"].exists()
