"""Tests for the release CLI entry point."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace


def _load_module():
    module_path = Path(__file__).resolve().parents[2] / "scripts" / "ui_designer" / "release_project.py"
    spec = importlib.util.spec_from_file_location("release_project_cli", str(module_path))
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_release_cli_emits_json(monkeypatch, tmp_path, capsys):
    module = _load_module()

    fake_project = SimpleNamespace(
        sdk_root=str(tmp_path / "sdk"),
        release_config=SimpleNamespace(get_profile=lambda profile_id="": SimpleNamespace(id="windows-pc")),
    )

    monkeypatch.setattr(module, "_parse_args", lambda: SimpleNamespace(project=str(tmp_path / "Demo.egui"), profile="", sdk_root="", output_dir="", warnings_as_errors=False, no_package=True, json=True))
    monkeypatch.setattr(module.Project, "load", lambda path: fake_project)
    monkeypatch.setattr(module, "find_sdk_root", lambda **kwargs: str(tmp_path / "sdk"))
    monkeypatch.setattr(
        module,
        "release_project",
        lambda request: SimpleNamespace(
            success=True,
            message="ok",
            build_id="20260325T000000Z",
            profile_id="windows-pc",
            release_root=str(tmp_path / "release"),
            dist_dir=str(tmp_path / "release" / "dist"),
            manifest_path=str(tmp_path / "release" / "release-manifest.json"),
            log_path=str(tmp_path / "release" / "logs" / "build.log"),
            history_path=str(tmp_path / "release" / "history.json"),
            designer_revision="designer-main-123",
            sdk={
                "source_kind": "submodule",
                "source_root": "D:/workspace/gitee/EmbeddedGUI_Designer/sdk/EmbeddedGUI",
                "revision": "sdk-main-456",
                "commit": "abcdef123456",
                "remote": "https://github.com/EmbeddedGUI/EmbeddedGUI.git",
                "dirty": False,
            },
            zip_path="",
            warnings=[],
            errors=[],
            artifacts=[],
            diagnostics_summary={"errors": 0, "warnings": 1, "total": 1},
            diagnostics_entries=[
                {
                    "severity": "warning",
                    "code": "missing_resource",
                    "message": "ghost.png is missing",
                    "page_name": "main_page",
                    "widget_name": "hero",
                    "resource_type": "image",
                    "resource_name": "ghost.png",
                    "property_name": "image_file",
                    "target_kind": "resource",
                    "target_page_name": "main_page",
                    "target_widget_name": "hero",
                }
            ],
        ),
    )

    exit_code = module.main()
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == module.EXIT_OK
    assert payload["success"] is True
    assert payload["profile_id"] == "windows-pc"
    assert payload["designer_revision"] == "designer-main-123"
    assert payload["sdk_source_kind"] == "submodule"
    assert payload["sdk_source_root"] == "D:/workspace/gitee/EmbeddedGUI_Designer/sdk/EmbeddedGUI"
    assert payload["sdk_revision"] == "sdk-main-456"
    assert payload["sdk_commit"] == "abcdef123456"
    assert payload["sdk_remote"] == "https://github.com/EmbeddedGUI/EmbeddedGUI.git"
    assert payload["sdk_dirty"] is False
    assert payload["sdk"]["revision"] == "sdk-main-456"
    assert payload["diagnostics_warning_count"] == 1
    assert payload["diagnostics_error_count"] == 0
    assert payload["diagnostics_total"] == 1
    assert payload["first_diagnostic"] == "warning main_page/hero: ghost.png is missing"
    assert payload["diagnostics"]["summary"] == {"errors": 0, "warnings": 1, "total": 1}
    assert payload["diagnostics"]["entries"][0]["code"] == "missing_resource"
    assert payload["diagnostics"]["entries"][0]["target_kind"] == "resource"


def test_release_cli_emits_text_diagnostics_summary(monkeypatch, tmp_path, capsys):
    module = _load_module()

    fake_project = SimpleNamespace(
        sdk_root=str(tmp_path / "sdk"),
        release_config=SimpleNamespace(get_profile=lambda profile_id="": SimpleNamespace(id="windows-pc")),
    )

    monkeypatch.setattr(
        module,
        "_parse_args",
        lambda: SimpleNamespace(
            project=str(tmp_path / "Demo.egui"),
            profile="",
            sdk_root="",
            output_dir="",
            warnings_as_errors=False,
            no_package=False,
            json=False,
        ),
    )
    monkeypatch.setattr(module.Project, "load", lambda path: fake_project)
    monkeypatch.setattr(module, "find_sdk_root", lambda **kwargs: str(tmp_path / "sdk"))
    monkeypatch.setattr(
        module,
        "release_project",
        lambda request: SimpleNamespace(
            success=True,
            message="ok",
            build_id="20260325T000000Z",
            profile_id="windows-pc",
            release_root=str(tmp_path / "release"),
            dist_dir=str(tmp_path / "release" / "dist"),
            manifest_path=str(tmp_path / "release" / "release-manifest.json"),
            log_path=str(tmp_path / "release" / "logs" / "build.log"),
            history_path=str(tmp_path / "release" / "history.json"),
            designer_revision="designer-main-123",
            sdk={"source_kind": "submodule", "revision": "sdk-main-456"},
            zip_path=str(tmp_path / "release" / "ReleaseDemo.zip"),
            warnings=["warning a"],
            errors=[],
            artifacts=[],
            diagnostics_summary={},
            diagnostics_entries=[],
        ),
    )

    exit_code = module.main()
    output = capsys.readouterr().out

    assert exit_code == module.EXIT_OK
    assert "[OK] ok" in output
    assert "[INFO] build_id: 20260325T000000Z" in output
    assert "[INFO] profile: windows-pc" in output
    assert "[INFO] package:" in output
    assert "[INFO] history:" in output
    assert "[INFO] designer_revision: designer-main-123" in output
    assert "[INFO] sdk_source: submodule" in output
    assert "[INFO] sdk_revision: sdk-main-456" in output
    assert "[INFO] diagnostics: warnings=1, errors=0, total=1" in output
    assert "[INFO] first_diagnostic: warning: warning a" in output
