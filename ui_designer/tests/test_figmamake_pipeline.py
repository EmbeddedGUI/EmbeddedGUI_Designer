"""Tests for figmamake helper scripts using canonical sdk_root naming."""

import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..")))

from figmamake import figmamake2egui as pipeline
from figmamake import figmamake_codegen as codegen_module
from ui_designer.model.workspace import sdk_runtime_check_output_dir
from ui_designer.utils.scaffold import (
    project_config_reference_frames_dir,
    project_config_regression_report_path,
    project_config_regression_results_path,
    project_resource_catalog_path,
)


class _FakeAnimExtractor:
    def extract_all(self, project_dir):
        return {
            "pages": [{"page": "home_page", "animations": []}],
            "has_extensions_needed": False,
            "extensions_needed": [],
        }


def test_figmamake_codegen_writes_project_with_canonical_sdk_root(tmp_path, monkeypatch):
    sdk_root = tmp_path / "sdk"
    (sdk_root / "example").mkdir(parents=True)

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    page_file = project_dir / "HomePage.tsx"
    page_file.write_text("export default function HomePage() {}", encoding="utf-8")

    monkeypatch.setattr(codegen_module, "_find_sdk_root", lambda: str(sdk_root))
    monkeypatch.setattr(
        codegen_module,
        "_discover_figmamake_pages",
        lambda _project_dir: {
            "pages": [{"name": "HomePage", "file": str(page_file), "path": "/"}],
            "root_bg_color": "060608",
        },
    )
    monkeypatch.setattr(codegen_module, "AnimExtractor", _FakeAnimExtractor)
    monkeypatch.setattr(
        codegen_module,
        "_prepare_figmamake_page_markup",
        lambda _tsx, component_name=None: {
            "lucide_imports": {},
            "jsx_text": "<div>Hello</div>",
            "comments": [],
            "pseudo_html": "<div>Hello</div>",
        },
    )

    result = codegen_module.FigmaMakeCodegen("DemoApp", 320, 240).run(
        str(project_dir),
        skip_c_gen=True,
    )

    egui_path = sdk_root / "example" / "DemoApp" / "DemoApp.egui"
    xml = egui_path.read_text(encoding="utf-8")
    resources_xml_path = Path(project_resource_catalog_path(str(sdk_root / "example" / "DemoApp")))
    resources_xml = resources_xml_path.read_text(encoding="utf-8")

    assert result["pages"] == ["home_page"]
    assert 'sdk_root="../.."' in xml
    assert 'egui_root="' not in xml
    assert (sdk_root / "example" / "DemoApp" / ".eguiproject" / "layout" / "home_page.xml").is_file()
    assert resources_xml.startswith('<?xml version="1.0" encoding="utf-8"?>\n')
    assert "<Resources" in resources_xml


def test_figmamake_pipeline_reports_sdk_root_label(tmp_path, monkeypatch, capsys):
    sdk_root = tmp_path / "sdk"
    (sdk_root / "example" / "DemoApp").mkdir(parents=True)
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    previous_cwd = os.getcwd()

    seen = {}

    monkeypatch.setattr(pipeline, "_find_sdk_root", lambda: str(sdk_root))
    monkeypatch.setattr(
        pipeline,
        "stage_convert",
        lambda project_dir_arg, app_name, width, height, sdk_root_arg, skip_c_gen=False: seen.update(
            {
                "project_dir": project_dir_arg,
                "app_name": app_name,
                "width": width,
                "height": height,
                "sdk_root": sdk_root_arg,
                "skip_c_gen": skip_c_gen,
            }
        )
        or {"extensions_needed": []},
    )
    monkeypatch.setattr(sys, "argv", [
        "figmamake2egui.py",
        "--project-dir", str(project_dir),
        "--app", "DemoApp",
        "--convert-only",
    ])

    try:
        with pytest.raises(SystemExit) as exc:
            pipeline.main()
    finally:
        os.chdir(previous_cwd)

    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "SDK root:" in out
    assert "EGUI root:" not in out
    assert seen["project_dir"] == str(project_dir)
    assert seen["sdk_root"] == str(sdk_root)


def test_figmamake_stage_build_and_run_uses_shared_runtime_output_dir(tmp_path, monkeypatch):
    sdk_root = tmp_path / "sdk"
    sdk_root.mkdir(parents=True)
    expected_rendered_dir = sdk_runtime_check_output_dir(str(sdk_root), "DemoApp", "regression")
    seen = {}

    monkeypatch.setattr(pipeline, "_ensure_sdk_scripts_on_path", lambda _sdk_root: None)
    monkeypatch.setattr(
        pipeline.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )
    monkeypatch.setitem(
        sys.modules,
        "code_runtime_check",
        SimpleNamespace(
            compile_app=lambda app_name: app_name == "DemoApp",
            capture_animation_frames=lambda app_name, rendered_dir, fps=0, duration=0, speed=0: (
                seen.update(
                    {
                        "app_name": app_name,
                        "rendered_dir": rendered_dir,
                        "fps": fps,
                        "duration": duration,
                        "speed": speed,
                    }
                )
                or True,
                12,
                "captured 12 frames",
            ),
        ),
    )

    success, rendered_dir = pipeline.stage_build_and_run("DemoApp", str(sdk_root), 320, 240)

    assert success is True
    assert rendered_dir == expected_rendered_dir
    assert seen == {
        "app_name": "DemoApp",
        "rendered_dir": expected_rendered_dir,
        "fps": 10,
        "duration": 5,
        "speed": 1,
    }


def test_figmamake_stage_capture_uses_shared_project_config_dir(tmp_path, monkeypatch):
    sdk_root = tmp_path / "sdk"
    sdk_root.mkdir(parents=True)
    expected_ref_dir = project_config_reference_frames_dir(str(sdk_root / "example" / "DemoApp"))
    seen = {}

    monkeypatch.setattr(
        pipeline.subprocess,
        "run",
        lambda cmd, **kwargs: seen.update({"cmd": cmd, "kwargs": kwargs}) or SimpleNamespace(returncode=0, stdout="", stderr=""),
    )

    success, ref_dir = pipeline.stage_capture("https://example.test/file", "DemoApp", 320, 240, str(sdk_root))

    assert success is True
    assert ref_dir == expected_ref_dir
    assert seen["cmd"][5] == expected_ref_dir


def test_figmamake_stage_verify_writes_report_files_under_shared_project_config_dir(tmp_path, monkeypatch):
    sdk_root = tmp_path / "sdk"
    app_dir = sdk_root / "example" / "DemoApp"
    app_dir.mkdir(parents=True)
    expected_report_path = project_config_regression_report_path(str(app_dir))
    expected_json_path = project_config_regression_results_path(str(app_dir))
    seen = {}

    monkeypatch.setitem(
        sys.modules,
        "figmamake_regression",
        SimpleNamespace(
            RegressionVerifier=lambda ref_dir, rendered_dir: SimpleNamespace(
                verify_all=lambda: {
                    "results": [{"name": "frame_000", "status": "PASS", "ssim": 0.99}],
                    "passed": 1,
                    "failed": 0,
                    "warned": 0,
                    "total": 1,
                }
            ),
            generate_html_report=lambda summary, output_path: seen.update(
                {"summary": summary, "report_path": output_path}
            ),
        ),
    )

    summary = pipeline.stage_verify("ref-dir", "render-dir", "DemoApp", str(sdk_root))

    assert seen["report_path"] == expected_report_path
    assert summary["passed"] == 1
    assert Path(expected_json_path).is_file()
