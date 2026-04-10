"""Tests for helper-side resource sync filtering in html2egui_helper.py."""

import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..")))

import html2egui_helper as h


class _FakePage:
    def __init__(self, widgets):
        self._widgets = list(widgets)

    def get_all_widgets(self):
        return list(self._widgets)


class TestHelperResourceSync:
    def test_build_egui_project_xml_uses_canonical_sdk_root_attribute(self):
        xml = h._build_egui_project_xml("DemoApp", 320, 240, "../../sdk/EmbeddedGUI", pages=["main_page"])

        assert 'sdk_root="../../sdk/EmbeddedGUI"' in xml
        assert 'egui_root="' not in xml

    def test_ensure_app_scaffold_exists_runs_scaffold_only_when_missing(self, tmp_path, monkeypatch):
        sdk_root = tmp_path / "sdk"
        existing_app_dir = sdk_root / "example" / "ExistingApp"
        existing_app_dir.mkdir(parents=True)
        calls = []

        monkeypatch.setattr(h, "cmd_scaffold", lambda args: calls.append(args))

        existing = h._ensure_app_scaffold_exists(str(sdk_root), "ExistingApp", 320, 240)
        created = h._ensure_app_scaffold_exists(str(sdk_root), "NewApp", 320, 240)

        assert existing == str(existing_app_dir)
        assert created == str(sdk_root / "example" / "NewApp")
        assert len(calls) == 1
        assert calls[0].app == "NewApp"
        assert calls[0].width == 320
        assert calls[0].height == 240
        assert calls[0].color_depth == 16
        assert calls[0].force is False

    def test_ensure_resource_config_file_uses_shared_default_content(self, tmp_path):
        config_path = tmp_path / "resource" / "src" / "app_resource_config.json"

        created = h._ensure_resource_config_file(str(config_path))
        created_again = h._ensure_resource_config_file(str(config_path))

        assert created is True
        assert created_again is False
        assert config_path.read_text(encoding="utf-8") == h.make_empty_resource_config_content()

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

        updated_configs = []

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
            "_update_resource_config",
            lambda config_path, names, size, image_format="rgb565", suffix="": updated_configs.append(
                (config_path, list(names), size, image_format, suffix)
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
        assert updated_configs == []
