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
        lambda project: {
            "entries": [
                SimpleNamespace(
                    severity="warning",
                    code="missing_resource",
                    message="Widget 'hero' references image_file='ghost.png', but it is missing from the resource catalog.",
                    page_name="main_page",
                    widget_name="hero",
                    resource_type="image",
                    resource_name="ghost.png",
                    property_name="image_file",
                    target_page_name="main_page",
                    target_widget_name="hero",
                )
            ],
            "errors": [],
            "warnings": [
                SimpleNamespace(
                    page_name="main_page",
                    widget_name="hero",
                    message="Widget 'hero' references image_file='ghost.png', but it is missing from the resource catalog.",
                )
            ],
        },
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
    assert result.diagnostics_summary == {"errors": 0, "warnings": 1, "total": 1}
    assert result.diagnostics_entries[0]["code"] == "missing_resource"
    assert result.diagnostics_entries[0]["target_kind"] == "resource"
    assert Path(result.manifest_path).is_file()
    assert Path(result.history_path).is_file()
    assert Path(result.zip_path).is_file()

    manifest = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))
    assert manifest["status"] == "success"
    assert manifest["profile_id"] == "windows-pc"
    assert manifest["workspace"]["ui_input_digest"]
    assert manifest["workspace"]["generated_digest"]
    assert manifest["diagnostics"]["summary"] == {"errors": 0, "warnings": 1, "total": 1}
    assert manifest["diagnostics"]["entries"][0]["code"] == "missing_resource"
    assert manifest["diagnostics"]["entries"][0]["target_kind"] == "resource"
    assert manifest["diagnostics"]["entries"][0]["target_page_name"] == "main_page"
    assert manifest["diagnostics"]["entries"][0]["target_widget_name"] == "hero"
    assert any(artifact["path"].endswith("ReleaseDemo.exe") for artifact in manifest["artifacts"])

    history = json.loads(Path(result.history_path).read_text(encoding="utf-8"))
    assert history[0]["status"] == "success"
    assert "designer_revision" in history[0]
    assert history[0]["manifest_path"].endswith("release-manifest.json")
    assert history[0]["log_path"].endswith("build.log")
    assert history[0]["dist_dir"].endswith("dist")
    assert "sdk" in history[0]
    assert "revision" in history[0]["sdk"]


def test_release_project_blocks_on_diagnostics(tmp_path, monkeypatch):
    sdk_root = tmp_path / "sdk"
    project_dir = sdk_root / "example" / "ReleaseDemo"
    _create_sdk_root(sdk_root)
    project_dir.mkdir(parents=True)
    project = _create_project(project_dir, sdk_root)

    monkeypatch.setattr(
        "ui_designer.engine.release_engine.collect_release_diagnostics",
        lambda project: {
            "entries": [
                SimpleNamespace(
                    severity="error",
                    code="invalid_name",
                    message="bad callback",
                    page_name="main_page",
                    widget_name="hero",
                    resource_type="",
                    resource_name="",
                    property_name="",
                    target_page_name="main_page",
                    target_widget_name="hero",
                )
            ],
            "errors": [
                SimpleNamespace(
                    page_name="main_page",
                    widget_name="hero",
                    message="bad callback",
                )
            ],
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
    assert result.diagnostics_summary == {"errors": 1, "warnings": 0, "total": 1}
    assert result.diagnostics_entries[0]["code"] == "invalid_name"
    assert result.diagnostics_entries[0]["target_kind"] == "widget"
    manifest = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))
    assert manifest["status"] == "failed"
    assert manifest["diagnostics"]["summary"] == {"errors": 1, "warnings": 0, "total": 1}
    assert manifest["diagnostics"]["entries"][0]["target_kind"] == "widget"
    assert manifest["diagnostics"]["entries"][0]["target_page_name"] == "main_page"
    assert manifest["diagnostics"]["entries"][0]["target_widget_name"] == "hero"
