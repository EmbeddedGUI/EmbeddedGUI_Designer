"""Tests for figmamake helper scripts using canonical sdk_root naming."""

import os
import sys

import pytest

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..")))

from figmamake import figmamake2egui as pipeline
from figmamake import figmamake_codegen as codegen_module


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
    monkeypatch.setattr(codegen_module, "_extract_lucide_imports", lambda _tsx: {})
    monkeypatch.setattr(codegen_module, "_extract_jsx_return", lambda _tsx, _page_name=None: "<div>Hello</div>")
    monkeypatch.setattr(codegen_module, "_extract_jsx_comments", lambda jsx: (jsx, []))
    monkeypatch.setattr(codegen_module, "_jsx_to_pseudo_html", lambda jsx, _imports: jsx)

    result = codegen_module.FigmaMakeCodegen("DemoApp", 320, 240).run(
        str(project_dir),
        skip_c_gen=True,
    )

    egui_path = sdk_root / "example" / "DemoApp" / "DemoApp.egui"
    xml = egui_path.read_text(encoding="utf-8")
    resources_xml_path = sdk_root / "example" / "DemoApp" / ".eguiproject" / "resources" / "resources.xml"
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
