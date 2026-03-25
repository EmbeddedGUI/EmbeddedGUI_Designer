"""Tests for the release build engine."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from ui_designer.engine.release_engine import release_project
from ui_designer.model.project import Project
from ui_designer.model.release import ReleaseRequest


def _create_sdk_root(root: Path):
    (root / "src").mkdir(parents=True)
    (root / "porting" / "designer").mkdir(parents=True)
    (root / "Makefile").write_text("all:\n", encoding="utf-8")


def _create_project(project_dir: Path, sdk_root: Path):
    project = Project(app_name="ReleaseDemo")
    project.sdk_root = str(sdk_root)
    project.project_dir = str(project_dir)
    project.create_new_page("main_page")
    project.save(str(project_dir))
    return project


def test_release_project_creates_manifest_and_history(tmp_path, monkeypatch):
    sdk_root = tmp_path / "sdk"
    project_dir = sdk_root / "example" / "ReleaseDemo"
    _create_sdk_root(sdk_root)
    project_dir.mkdir(parents=True)
    project = _create_project(project_dir, sdk_root)

    monkeypatch.setattr(
        "ui_designer.engine.release_engine.collect_release_diagnostics",
        lambda project: {"entries": [], "errors": [], "warnings": []},
    )
    monkeypatch.setattr(
        "ui_designer.engine.release_engine.generate_all_files_preserved",
        lambda project, project_dir, backup=True: {"ui_demo.c": "// generated\n"},
    )

    def fake_resource_generation(project, project_dir, sdk_root):
        output_dir = Path(sdk_root) / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        merged = output_dir / "app_egui_resource_merge.bin"
        merged.write_bytes(b"resource")
        return [str(merged)], "resource ok\n"

    monkeypatch.setattr("ui_designer.engine.release_engine._run_resource_generation", fake_resource_generation)

    def fake_run(cmd, cwd, capture_output, text, timeout, check=False):
        assert cmd[0] == "make"
        output_dir = Path(cwd) / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "main.exe").write_bytes(b"exe")
        return SimpleNamespace(returncode=0, stdout="build ok\n", stderr="")

    monkeypatch.setattr("ui_designer.engine.release_engine.subprocess.run", fake_run)

    result = release_project(
        ReleaseRequest(
            project=project,
            project_dir=str(project_dir),
            sdk_root=str(sdk_root),
            profile=project.release_config.get_profile(),
            designer_root=str(tmp_path / "designer_repo"),
            package_release=True,
        )
    )

    assert result.success is True
    assert Path(result.manifest_path).is_file()
    assert Path(result.history_path).is_file()
    assert Path(result.zip_path).is_file()

    manifest = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))
    assert manifest["status"] == "success"
    assert manifest["profile_id"] == "windows-pc"
    assert manifest["workspace"]["ui_input_digest"]
    assert manifest["workspace"]["generated_digest"]
    assert any(artifact["path"].endswith("ReleaseDemo.exe") for artifact in manifest["artifacts"])


def test_release_project_blocks_on_diagnostics(tmp_path, monkeypatch):
    sdk_root = tmp_path / "sdk"
    project_dir = sdk_root / "example" / "ReleaseDemo"
    _create_sdk_root(sdk_root)
    project_dir.mkdir(parents=True)
    project = _create_project(project_dir, sdk_root)

    monkeypatch.setattr(
        "ui_designer.engine.release_engine.collect_release_diagnostics",
        lambda project: {
            "entries": [],
            "errors": [SimpleNamespace(page_name="main_page", widget_name="hero", message="bad callback")],
            "warnings": [],
        },
    )

    result = release_project(
        ReleaseRequest(
            project=project,
            project_dir=str(project_dir),
            sdk_root=str(sdk_root),
            profile=project.release_config.get_profile(),
            designer_root=str(tmp_path / "designer_repo"),
            package_release=False,
        )
    )

    assert result.success is False
    assert "diagnostics" in result.message.lower()
    manifest = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))
    assert manifest["status"] == "failed"
