"""Tests for helper-side resource sync filtering in html2egui_helper.py."""

import json
import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..")))

import html2egui_helper as h
from ui_designer.utils.resource_config_overlay import make_empty_resource_config_content


class _FakePage:
    def __init__(self, widgets):
        self._widgets = list(widgets)

    def get_all_widgets(self):
        return list(self._widgets)


class TestHelperResourceSync:
    def test_app_path_helpers_use_shared_project_layout(self, tmp_path):
        sdk_root = tmp_path / "sdk"

        app_dir = h._get_app_dir(str(sdk_root), "DemoApp")

        assert app_dir == str(sdk_root / "example" / "DemoApp")
        assert h._get_app_config_dir(app_dir) == str(
            sdk_root / "example" / "DemoApp" / ".eguiproject"
        )
        assert h._get_app_layout_dir(app_dir) == str(
            sdk_root / "example" / "DemoApp" / ".eguiproject" / "layout"
        )
        assert h._get_app_config_resource_dir(app_dir) == str(
            sdk_root / "example" / "DemoApp" / ".eguiproject" / "resources"
        )
        assert h._get_app_resource_images_dir(app_dir) == str(
            sdk_root / "example" / "DemoApp" / ".eguiproject" / "resources" / "images"
        )
        assert h._get_app_generated_resource_dir(app_dir) == str(
            sdk_root / "example" / "DemoApp" / "resource"
        )
        assert h._get_app_resource_src_dir(app_dir) == str(
            sdk_root / "example" / "DemoApp" / "resource" / "src"
        )

    def test_helper_app_command_uses_standard_cli_format(self):
        assert h._helper_app_command("generate-code", "DemoApp") == (
            "python html2egui_helper.py generate-code --app DemoApp"
        )

    def test_print_numbered_steps_formats_ordered_list(self, capsys):
        h._print_numbered_steps(["Step A", "Step B"])

        assert capsys.readouterr().out == (
            "\nNext steps:\n"
            "  1. Step A\n"
            "  2. Step B\n"
        )

    def test_resolve_export_image_output_dir_prefers_explicit_output(self, tmp_path):
        sdk_root = tmp_path / "sdk"
        explicit = tmp_path / "custom-output"

        assert h._resolve_export_image_output_dir(
            str(sdk_root),
            output_path=str(explicit),
            app_name="DemoApp",
        ) == str(explicit)

    def test_resolve_export_image_output_dir_uses_app_images_dir(self, tmp_path):
        sdk_root = tmp_path / "sdk"

        assert h._resolve_export_image_output_dir(
            str(sdk_root),
            app_name="DemoApp",
        ) == str(
            sdk_root / "example" / "DemoApp" / ".eguiproject" / "resources" / "images"
        )

    def test_resolve_export_image_output_dir_requires_output_or_app(self, tmp_path):
        with pytest.raises(ValueError, match="Must specify either --output or --app"):
            h._resolve_export_image_output_dir(str(tmp_path / "sdk"))

    def test_resolve_extract_text_output_path_prefers_explicit_output(self, tmp_path):
        sdk_root = tmp_path / "sdk"
        explicit = tmp_path / "supported_text.txt"

        assert h._resolve_extract_text_output_path(
            str(sdk_root),
            output_path=str(explicit),
            app_name="DemoApp",
        ) == str(explicit)

    def test_resolve_extract_text_output_path_uses_app_resource_src_dir(self, tmp_path):
        sdk_root = tmp_path / "sdk"

        out_path = h._resolve_extract_text_output_path(
            str(sdk_root),
            app_name="DemoApp",
        )

        assert out_path == str(
            sdk_root / "example" / "DemoApp" / "resource" / "src" / "supported_text.txt"
        )
        assert (sdk_root / "example" / "DemoApp" / "resource" / "src").is_dir()

    def test_resolve_extract_text_output_path_allows_stdout_fallback(self, tmp_path):
        assert h._resolve_extract_text_output_path(str(tmp_path / "sdk")) == ""

    def test_resolve_existing_app_dir_returns_sdk_and_app_paths(self, tmp_path, monkeypatch):
        sdk_root = tmp_path / "sdk"
        app_dir = sdk_root / "example" / "DemoApp"
        app_dir.mkdir(parents=True)

        monkeypatch.setattr(h, "_find_sdk_root", lambda: str(sdk_root))

        resolved_sdk_root, resolved_app_dir = h._resolve_existing_app_dir("DemoApp")

        assert resolved_sdk_root == str(sdk_root)
        assert resolved_app_dir == str(app_dir)

    def test_resolve_existing_app_dir_exits_when_app_missing(self, tmp_path, monkeypatch):
        sdk_root = tmp_path / "sdk"
        monkeypatch.setattr(h, "_find_sdk_root", lambda: str(sdk_root))

        with pytest.raises(SystemExit, match="1"):
            h._resolve_existing_app_dir("MissingApp")

    def test_read_required_text_file_returns_file_contents(self, tmp_path):
        html_path = tmp_path / "demo.html"
        html_path.write_text("<div>Hello</div>", encoding="utf-8")

        assert h._read_required_text_file(str(html_path), error_label="HTML file") == "<div>Hello</div>"

    def test_require_existing_file_returns_path_when_present(self, tmp_path):
        html_path = tmp_path / "demo.html"
        html_path.write_text("<div>Hello</div>", encoding="utf-8")

        assert h._require_existing_file(str(html_path), error_label="HTML file") == str(html_path)

    def test_require_existing_file_exits_with_error_message(self, tmp_path, capsys):
        missing = tmp_path / "missing.html"

        with pytest.raises(SystemExit, match="1"):
            h._require_existing_file(str(missing), error_label="HTML file")

        assert capsys.readouterr().out == f"ERROR: HTML file not found: {missing}\n"

    def test_read_required_text_file_exits_with_error_message(self, tmp_path, capsys):
        missing = tmp_path / "missing.html"

        with pytest.raises(SystemExit, match="1"):
            h._read_required_text_file(str(missing), error_label="HTML file")

        assert capsys.readouterr().out == f"ERROR: HTML file not found: {missing}\n"

    def test_emit_text_output_writes_file_and_optional_status_message(self, tmp_path, capsys):
        output_path = tmp_path / "text.txt"

        h._emit_text_output(
            str(output_path),
            "plain text",
            written_message="Saved text to: {path}",
        )

        captured = capsys.readouterr()
        assert output_path.read_text(encoding="utf-8") == "plain text"
        assert captured.out == ""
        assert captured.err == f"Saved text to: {output_path}\n"

    def test_emit_text_output_writes_stdout_when_path_missing(self, capsys):
        h._emit_text_output("", "plain text")

        captured = capsys.readouterr()
        assert captured.out == "plain text\n"
        assert captured.err == ""

    def test_emit_json_output_writes_file_and_status_message(self, tmp_path, capsys):
        output_path = tmp_path / "layout.json"

        h._emit_json_output(
            str(output_path),
            '{"screen":{}}',
            written_message="Saved to: {path}",
        )

        captured = capsys.readouterr()
        assert output_path.read_text(encoding="utf-8") == '{"screen":{}}'
        assert captured.out == ""
        assert captured.err == f"Saved to: {output_path}\n"

    def test_emit_json_output_writes_stdout_when_path_missing(self, capsys):
        h._emit_json_output("", '{"screen":{}}', written_message="ignored: {path}")

        captured = capsys.readouterr()
        assert captured.out == '{"screen":{}}\n'
        assert captured.err == ""

    def test_ensure_app_scaffold_exists_runs_scaffold_only_when_missing(self, tmp_path, monkeypatch):
        sdk_root = tmp_path / "sdk"
        existing_app_dir = sdk_root / "example" / "ExistingApp"
        existing_app_dir.mkdir(parents=True)
        calls = []

        def fake_ensure(*args, **kwargs):
            calls.append((args, kwargs))
            return args[1] == "NewApp", {}

        monkeypatch.setattr(h, "ensure_conversion_project_scaffold_with_sdk_root", fake_ensure)

        existing = h._ensure_app_scaffold_exists(str(sdk_root), "ExistingApp", 320, 240)
        created = h._ensure_app_scaffold_exists(str(sdk_root), "NewApp", 320, 240)

        assert existing == str(existing_app_dir)
        assert created == str(sdk_root / "example" / "NewApp")
        assert len(calls) == 2

        existing_args, existing_kwargs = calls[0]
        assert existing_args == (
            str(existing_app_dir),
            "ExistingApp",
            str(sdk_root),
            320,
            240,
        )
        assert existing_kwargs == {}

        created_args, created_kwargs = calls[1]
        assert created_args == (
            str(sdk_root / "example" / "NewApp"),
            "NewApp",
            str(sdk_root),
            320,
            240,
        )
        assert created_kwargs == {}

    def test_ensure_resource_config_file_uses_shared_default_content(self, tmp_path):
        config_path = tmp_path / "resource" / "src" / "app_resource_config.json"

        created = h.ensure_resource_config_file(str(config_path))
        created_again = h.ensure_resource_config_file(str(config_path))

        assert created is True
        assert created_again is False
        assert config_path.read_text(encoding="utf-8") == make_empty_resource_config_content()

    def test_sync_exported_pngs_skips_reserved_filenames(self, tmp_path):
        output_dir = tmp_path / "out"
        src_dir = tmp_path / "src"
        output_dir.mkdir()
        (output_dir / "kept.png").write_bytes(b"PNG")
        (output_dir / "_generated_text_demo_16_4.png").write_bytes(b"BAD")

        synced = h._sync_exported_pngs(
            str(output_dir),
            str(src_dir),
            ["kept.png", "_generated_text_demo_16_4.png"],
            reserved_label="SVG",
        )

        assert synced == ["kept.png"]
        assert (src_dir / "kept.png").is_file()
        assert not (src_dir / "_generated_text_demo_16_4.png").exists()

    def test_update_resource_config_files_appends_only_missing_entries(self, tmp_path):
        config_path = tmp_path / "app_resource_config.json"
        config_path.write_text(
            json.dumps(
                {
                    "img": [
                        {
                            "file": "icon_wifi.png",
                            "external": "0",
                            "format": "alpha",
                            "alpha": "4",
                            "dim": "24,24",
                        }
                    ],
                    "font": [],
                },
                indent=4,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        h._update_resource_config_files(
            str(config_path),
            ["icon_wifi.png", "icon_alarm.png", "icon_alarm.png"],
            24,
            image_format="alpha",
            entry_label="icon",
        )

        saved = json.loads(config_path.read_text(encoding="utf-8"))
        assert [entry["file"] for entry in saved["img"]] == [
            "icon_wifi.png",
            "icon_alarm.png",
        ]
        assert saved["img"][1]["format"] == "alpha"
        assert saved["img"][1]["dim"] == "24,24"

    def test_ensure_and_update_resource_config_creates_file_and_appends_entries(self, tmp_path):
        config_path = tmp_path / "app_resource_config.json"

        created = h._ensure_and_update_resource_config(
            str(config_path),
            ["icon_alarm.png"],
            24,
            image_format="alpha",
            entry_label="icon",
        )
        created_again = h._ensure_and_update_resource_config(
            str(config_path),
            ["icon_alarm.png", "icon_wifi.png"],
            24,
            image_format="alpha",
            entry_label="icon",
        )

        saved = json.loads(config_path.read_text(encoding="utf-8"))
        assert created is True
        assert created_again is False
        assert [entry["file"] for entry in saved["img"]] == [
            "icon_alarm.png",
            "icon_wifi.png",
        ]
        assert saved["img"][0]["format"] == "alpha"
        assert saved["img"][0]["dim"] == "24,24"

    def test_sync_font_files_skips_reserved_filename(self, tmp_path):
        sdk_root = tmp_path / "sdk"
        tools_dir = sdk_root / "scripts" / "tools"
        tools_dir.mkdir(parents=True)
        (tools_dir / "_generated_text_demo_16_4.ttf").write_bytes(b"BAD")
        (tools_dir / "kept.ttf").write_bytes(b"OK")

        project = SimpleNamespace(
            pages=[
                _FakePage(
                    [
                        SimpleNamespace(properties={"font_file": "_generated_text_demo_16_4.ttf"}),
                        SimpleNamespace(properties={"font_file": "kept.ttf"}),
                    ]
                )
            ]
        )
        src_dir = tmp_path / "project" / "resource" / "src"

        h._sync_font_files(project, str(sdk_root), str(src_dir))

        assert (src_dir / "kept.ttf").is_file()
        assert not (src_dir / "_generated_text_demo_16_4.ttf").exists()

    def test_export_svgs_skips_reserved_filename_when_syncing_to_project(self, tmp_path, monkeypatch):
        html_path = tmp_path / "demo.html"
        html_path.write_text("<div><svg></svg></div>", encoding="utf-8")

        app_dir = tmp_path / "example" / "DemoApp"
        output_dir = app_dir / ".eguiproject" / "resources" / "images"
        src_dir = app_dir / "resource" / "src"
        output_dir.mkdir(parents=True)

        def fake_render(svg_str, out_path, size):
            with open(out_path, "wb") as f:
                f.write(b"PNG")

        monkeypatch.setattr(h, "_find_sdk_root", lambda: str(tmp_path))
        monkeypatch.setattr(h, "_get_svg_renderer", lambda: ("fake", fake_render))
        monkeypatch.setattr(
            h,
            "_extract_svgs_from_html",
            lambda *_args, **_kwargs: [{"name": "_generated_text_demo_16_4", "svg": "<svg />"}],
        )
        monkeypatch.setattr(h, "_resolve_current_color", lambda svg, *_args, **_kwargs: svg)
        monkeypatch.setattr(h, "_ensure_svg_dimensions", lambda svg, _size: svg)
        monkeypatch.setattr(
            h,
            "_update_resource_config_files",
            lambda config_path, filenames, size, image_format="rgb565", image_alpha="4", entry_label="image": (_ for _ in ()).throw(
                AssertionError("resource config should not be updated for reserved-only SVG exports")
            ),
        )

        args = SimpleNamespace(
            input=str(html_path),
            output=None,
            app="DemoApp",
            size=24,
            prefix="",
            image_format="rgb565",
        )

        h.cmd_export_svgs(args)

        assert (output_dir / "_generated_text_demo_16_4.png").is_file()
        assert not (src_dir / "_generated_text_demo_16_4.png").exists()
        assert not (src_dir / "app_resource_config.json").exists()
