"""Tests for the release/package inspection CLI."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_module():
    module_path = Path(__file__).resolve().parents[2] / "scripts" / "ui_designer" / "inspect_release.py"
    spec = importlib.util.spec_from_file_location("inspect_release_cli", str(module_path))
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_inspect_release_manifest_emits_json(monkeypatch, tmp_path, capsys):
    module = _load_module()

    manifest_path = tmp_path / "release" / "release-manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps(
            {
                "build_id": "20260325T000000Z",
                "status": "success",
                "app_name": "DemoApp",
                "profile_id": "windows-pc",
                "designer_revision": "designer-main-123",
                "sdk": {
                    "source_kind": "submodule",
                    "source_root": "D:/workspace/gitee/EmbeddedGUI_Designer/sdk/EmbeddedGUI",
                    "revision": "sdk-main-456",
                    "commit": "abcdef123456",
                    "remote": "https://github.com/EmbeddedGUI/EmbeddedGUI.git",
                    "dirty": False,
                },
                "workspace": {
                    "git_commit": "deadbeef",
                    "dirty": True,
                },
                "artifacts": [
                    {"path": "dist/DemoApp.exe", "sha256": "abc"},
                ],
                "diagnostics": {
                    "summary": {
                        "warnings": 2,
                        "errors": 1,
                        "total": 3,
                    },
                    "entries": [
                        {
                            "severity": "error",
                            "message": "bad callback",
                            "page_name": "main_page",
                            "widget_name": "hero",
                            "target_page_name": "main_page",
                            "target_widget_name": "hero",
                        }
                    ],
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(module, "_parse_args", lambda: type("Args", (), {"path": str(manifest_path), "json": True})())

    exit_code = module.main()
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == module.EXIT_OK
    assert payload["kind"] == "release_manifest"
    assert payload["designer_revision"] == "designer-main-123"
    assert payload["sdk_source_root"] == "D:/workspace/gitee/EmbeddedGUI_Designer/sdk/EmbeddedGUI"
    assert payload["sdk_revision"] == "sdk-main-456"
    assert payload["artifact_count"] == 1
    assert payload["diagnostics_warning_count"] == 2
    assert payload["diagnostics_error_count"] == 1
    assert payload["diagnostics_total"] == 3
    assert payload["first_diagnostic"] == "error main_page/hero: bad callback"


def test_inspect_packaged_app_emits_json(monkeypatch, tmp_path, capsys):
    module = _load_module()

    app_dir = tmp_path / "dist" / "EmbeddedGUI-Designer"
    app_dir.mkdir(parents=True)
    (app_dir / module.DESIGNER_BUILD_METADATA_NAME).write_text(
        json.dumps(
            {
                "git_commit": "1234567890abcdef",
                "git_commit_short": "1234567",
                "git_describe": "designer-main-1234567",
                "git_dirty": True,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    bundled_sdk_root = app_dir / "sdk" / "EmbeddedGUI"
    bundled_sdk_root.mkdir(parents=True)
    (bundled_sdk_root / module.BUNDLED_SDK_METADATA_NAME).write_text(
        json.dumps(
            {
                "git_commit": "abcdef1234567890",
                "git_commit_short": "abcdef1",
                "git_describe": "sdk-main-abcdef1",
                "git_remote_url": "https://github.com/EmbeddedGUI/EmbeddedGUI.git",
                "git_dirty": False,
                "source_root": "D:/sdk/EmbeddedGUI",
                "file_count": 42,
                "total_size_bytes": 2048,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(module, "_parse_args", lambda: type("Args", (), {"path": str(app_dir), "json": True})())

    exit_code = module.main()
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == module.EXIT_OK
    assert payload["kind"] == "packaged_app"
    assert payload["designer_revision"] == "designer-main-1234567"
    assert payload["designer_dirty"] is True
    assert payload["sdk_source_kind"] == "bundled"
    assert payload["sdk_revision"] == "sdk-main-abcdef1"
    assert payload["sdk_remote"] == "https://github.com/EmbeddedGUI/EmbeddedGUI.git"
    assert payload["file_count"] == 42


def test_inspect_version_file_emits_json(monkeypatch, tmp_path, capsys):
    module = _load_module()

    version_path = tmp_path / "release" / "VERSION.txt"
    version_path.parent.mkdir(parents=True)
    version_path.write_text(
        "\n".join(
            (
                "app=DemoApp",
                "profile=windows-pc",
                "designer_revision=designer-main-123",
                "sdk_source_kind=submodule",
                "sdk_revision=sdk-main-456",
                "sdk_commit=abcdef1234567890",
                "sdk_remote=https://github.com/EmbeddedGUI/EmbeddedGUI.git",
                "build_id=20260325T000000Z",
                "",
            )
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(module, "_parse_args", lambda: type("Args", (), {"path": str(version_path), "json": True})())

    exit_code = module.main()
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == module.EXIT_OK
    assert payload["kind"] == "release_version"
    assert payload["app_name"] == "DemoApp"
    assert payload["profile_id"] == "windows-pc"
    assert payload["designer_revision"] == "designer-main-123"
    assert payload["sdk_source_kind"] == "submodule"
    assert payload["sdk_revision"] == "sdk-main-456"
    assert payload["sdk_commit"] == "abcdef1234567890"
    assert payload["sdk_remote"] == "https://github.com/EmbeddedGUI/EmbeddedGUI.git"
    assert payload["build_id"] == "20260325T000000Z"


def test_inspect_profile_directory_uses_latest_build(monkeypatch, tmp_path, capsys):
    module = _load_module()

    profile_dir = tmp_path / "release" / "windows-pc"
    build_a = profile_dir / "20260325T000000Z"
    build_b = profile_dir / "20260325T000100Z"
    build_a.mkdir(parents=True)
    build_b.mkdir(parents=True)

    (build_a / "release-manifest.json").write_text(
        json.dumps({"build_id": "20260325T000000Z", "status": "success", "app_name": "DemoA"}, indent=2),
        encoding="utf-8",
    )
    (build_b / "release-manifest.json").write_text(
        json.dumps({"build_id": "20260325T000100Z", "status": "success", "app_name": "DemoB"}, indent=2),
        encoding="utf-8",
    )

    monkeypatch.setattr(module, "_parse_args", lambda: type("Args", (), {"path": str(profile_dir), "json": True})())

    exit_code = module.main()
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == module.EXIT_OK
    assert payload["kind"] == "release_manifest"
    assert payload["build_id"] == "20260325T000100Z"
    assert payload["app_name"] == "DemoB"
