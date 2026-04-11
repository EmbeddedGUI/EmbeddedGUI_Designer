"""Tests for ResourceConfigGenerator."""

import json
import os
import pytest

from ui_designer.tests.page_builders import build_test_page_from_root
from ui_designer.tests.project_builders import build_test_project_from_pages
from ui_designer.model.widget_model import WidgetModel
from ui_designer.model.string_resource import StringResourceCatalog
from ui_designer.generator.resource_config_generator import ResourceConfigGenerator
from ui_designer.utils.resource_config_overlay import (
    APP_RESOURCE_CONFIG_DESIGNER_FILENAME,
    DESIGNER_RESOURCE_DIRNAME,
)


def _make_project_with_widgets(widgets, screen_w=240, screen_h=320):
    """Helper: create a project with a single page containing given widgets."""
    root = WidgetModel("group", name="root", x=0, y=0, width=screen_w, height=screen_h)
    for w in widgets:
        root.add_child(w)
    page = build_test_page_from_root("main_page", root=root)
    return build_test_project_from_pages(
        [page],
        screen_width=screen_w,
        screen_height=screen_h,
    )


class TestEmptyProject:
    """Test generation with empty project."""

    def test_empty_project_generates_empty_config(self):
        root = WidgetModel("group", name="root", x=0, y=0, width=240, height=320)
        page = build_test_page_from_root("main_page", root=root)
        proj = build_test_project_from_pages([page], app_name="Empty")

        gen = ResourceConfigGenerator()
        config = gen.generate(proj)
        assert config["img"] == []
        assert config["font"] == []


class TestImageCollection:
    """Test image config collection from widgets."""

    def test_single_image_widget(self):
        img = WidgetModel("image", name="icon", x=0, y=0, width=24, height=24)
        img.properties["image_file"] = "star.png"
        img.properties["image_format"] = "rgb565"
        img.properties["image_alpha"] = "4"

        proj = _make_project_with_widgets([img])
        gen = ResourceConfigGenerator()
        config = gen.generate(proj)

        assert len(config["img"]) == 1
        assert config["img"][0]["file"] == "star.png"
        assert config["img"][0]["format"] == "rgb565"

    def test_image_without_file_skipped(self):
        img = WidgetModel("image", name="empty", x=0, y=0, width=24, height=24)
        # No image_file set
        proj = _make_project_with_widgets([img])
        gen = ResourceConfigGenerator()
        config = gen.generate(proj)
        assert config["img"] == []

    def test_image_with_dim(self):
        img = WidgetModel("image", name="icon", x=0, y=0, width=48, height=48)
        img.properties["image_file"] = "star.png"
        img.properties["image_dim"] = "48,48"

        proj = _make_project_with_widgets([img])
        gen = ResourceConfigGenerator()
        config = gen.generate(proj)
        assert config["img"][0]["dim"] == "48,48"


class TestImageDeduplication:
    """Test image deduplication logic."""

    def test_duplicate_images_merged(self):
        img1 = WidgetModel("image", name="icon1", x=0, y=0, width=24, height=24)
        img1.properties["image_file"] = "star.png"
        img1.properties["image_format"] = "rgb565"

        img2 = WidgetModel("image", name="icon2", x=50, y=0, width=24, height=24)
        img2.properties["image_file"] = "star.png"
        img2.properties["image_format"] = "rgb565"

        proj = _make_project_with_widgets([img1, img2])
        gen = ResourceConfigGenerator()
        config = gen.generate(proj)
        assert len(config["img"]) == 1

    def test_same_file_different_dim_gets_suffix(self):
        img1 = WidgetModel("image", name="icon1", x=0, y=0, width=24, height=24)
        img1.properties["image_file"] = "star.png"
        img1.properties["image_dim"] = "24,24"

        img2 = WidgetModel("image", name="icon2", x=50, y=0, width=48, height=48)
        img2.properties["image_file"] = "star.png"
        img2.properties["image_dim"] = "48,48"

        proj = _make_project_with_widgets([img1, img2])
        gen = ResourceConfigGenerator()
        config = gen.generate(proj)
        assert len(config["img"]) == 2
        # At least one should have a name with dim suffix
        names = [c.get("name", "") for c in config["img"]]
        has_suffix = any("24x24" in n or "48x48" in n for n in names)
        assert has_suffix


class TestFontCollection:
    """Test font config collection from widgets."""

    def test_label_with_font(self):
        lbl = WidgetModel("label", name="title", x=0, y=0, width=100, height=30)
        lbl.properties["text"] = "Hello"
        lbl.properties["font_file"] = "test.ttf"
        lbl.properties["font_pixelsize"] = "18"
        lbl.properties["font_fontbitsize"] = "4"

        proj = _make_project_with_widgets([lbl])
        gen = ResourceConfigGenerator()
        config = gen.generate(proj)

        assert len(config["font"]) == 1
        assert config["font"][0]["file"] == "test.ttf"
        assert config["font"][0]["pixelsize"] == "18"

    def test_label_without_font_file_skipped(self):
        lbl = WidgetModel("label", name="title", x=0, y=0, width=100, height=30)
        lbl.properties["text"] = "Hello"
        # No font_file set
        proj = _make_project_with_widgets([lbl])
        gen = ResourceConfigGenerator()
        config = gen.generate(proj)
        assert config["font"] == []

    def test_button_with_font(self):
        btn = WidgetModel("button", name="btn", x=0, y=0, width=80, height=40)
        btn.properties["text"] = "Click"
        btn.properties["font_file"] = "test.ttf"
        btn.properties["font_pixelsize"] = "14"
        btn.properties["font_fontbitsize"] = "4"

        proj = _make_project_with_widgets([btn])
        gen = ResourceConfigGenerator()
        config = gen.generate(proj)
        assert len(config["font"]) == 1

    @pytest.mark.parametrize(
        ("widget_type", "expected_inline_char"),
        (
            ("textblock", "段"),
            ("gauge", "9"),
            ("digital_clock", "8"),
        ),
    )
    def test_non_label_widgets_with_font_file_are_included(self, widget_type, expected_inline_char):
        widget = WidgetModel(widget_type, name=f"{widget_type}_1", x=0, y=0, width=100, height=40)
        widget.properties["font_file"] = "test.ttf"
        widget.properties["font_pixelsize"] = "16"
        widget.properties["font_fontbitsize"] = "4"
        widget.properties["font_text"] = expected_inline_char
        widget.properties["font_text_file"] = "chars.txt"
        if "text" in widget.properties:
            widget.properties["text"] = expected_inline_char

        proj = _make_project_with_widgets([widget])
        gen = ResourceConfigGenerator()
        config = gen.generate(proj)

        assert len(config["font"]) == 1
        assert config["font"][0]["file"] == "test.ttf"
        assert config["font"][0]["text"].startswith(".designer/_generated_text_")
        assert config["font"][0]["_extra_text_files"] == ["chars.txt"]
        assert expected_inline_char in config["font"][0].get("_generated_text_content", "")


class TestFontMerging:
    """Test font config merging logic."""

    def test_same_font_merged_chars_unioned(self):
        lbl1 = WidgetModel("label", name="lbl1", x=0, y=0, width=100, height=30)
        lbl1.properties["text"] = "AB"
        lbl1.properties["font_file"] = "test.ttf"
        lbl1.properties["font_pixelsize"] = "16"
        lbl1.properties["font_fontbitsize"] = "4"

        lbl2 = WidgetModel("label", name="lbl2", x=0, y=40, width=100, height=30)
        lbl2.properties["text"] = "BC"
        lbl2.properties["font_file"] = "test.ttf"
        lbl2.properties["font_pixelsize"] = "16"
        lbl2.properties["font_fontbitsize"] = "4"

        proj = _make_project_with_widgets([lbl1, lbl2])
        gen = ResourceConfigGenerator()
        config = gen.generate(proj)

        assert len(config["font"]) == 1
        # The generated text file should contain union of chars: A, B, C
        text_content = config["font"][0].get("_generated_text_content", "")
        assert "A" in text_content
        assert "B" in text_content
        assert "C" in text_content

    def test_different_pixelsize_not_merged(self):
        lbl1 = WidgetModel("label", name="lbl1", x=0, y=0, width=100, height=30)
        lbl1.properties["text"] = "A"
        lbl1.properties["font_file"] = "test.ttf"
        lbl1.properties["font_pixelsize"] = "16"
        lbl1.properties["font_fontbitsize"] = "4"

        lbl2 = WidgetModel("label", name="lbl2", x=0, y=40, width=100, height=30)
        lbl2.properties["text"] = "B"
        lbl2.properties["font_file"] = "test.ttf"
        lbl2.properties["font_pixelsize"] = "24"
        lbl2.properties["font_fontbitsize"] = "4"

        proj = _make_project_with_widgets([lbl1, lbl2])
        gen = ResourceConfigGenerator()
        config = gen.generate(proj)
        assert len(config["font"]) == 2


class TestStringRefResolution:
    """Test @string/ reference resolution in font text collection."""

    def test_string_ref_collects_all_locales(self):
        lbl = WidgetModel("label", name="title", x=0, y=0, width=100, height=30)
        lbl.properties["text"] = "@string/greeting"
        lbl.properties["font_file"] = "test.ttf"
        lbl.properties["font_pixelsize"] = "16"
        lbl.properties["font_fontbitsize"] = "4"

        proj = _make_project_with_widgets([lbl])
        # Add string catalog
        string_cat = StringResourceCatalog()
        string_cat.set("greeting", "Hello", "")
        string_cat.set("greeting", "Hola", "es")
        proj.string_catalog = string_cat

        gen = ResourceConfigGenerator()
        config = gen.generate(proj)

        assert len(config["font"]) == 1
        text_content = config["font"][0].get("_generated_text_content", "")
        # Should contain chars from both "Hello" and "Hola"
        assert "H" in text_content
        assert "e" in text_content
        assert "o" in text_content
        assert "a" in text_content


class TestGenerateAndSave:
    """Test generate_and_save() file output."""

    def test_writes_json_file(self, tmp_path):
        img = WidgetModel("image", name="icon", x=0, y=0, width=24, height=24)
        img.properties["image_file"] = "star.png"

        proj = _make_project_with_widgets([img])
        gen = ResourceConfigGenerator()
        gen.generate_and_save(proj, str(tmp_path))

        config_path = tmp_path / DESIGNER_RESOURCE_DIRNAME / APP_RESOURCE_CONFIG_DESIGNER_FILENAME
        assert config_path.is_file()

        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert len(data["img"]) == 1
        assert data["img"][0]["file"] == "star.png"

    def test_writes_generated_text_file(self, tmp_path):
        lbl = WidgetModel("label", name="title", x=0, y=0, width=100, height=30)
        lbl.properties["text"] = "Hello"
        lbl.properties["font_file"] = "test.ttf"
        lbl.properties["font_pixelsize"] = "16"
        lbl.properties["font_fontbitsize"] = "4"

        proj = _make_project_with_widgets([lbl])
        gen = ResourceConfigGenerator()
        gen.generate_and_save(proj, str(tmp_path))

        # Should have created a generated text file
        txt_root = tmp_path / DESIGNER_RESOURCE_DIRNAME
        txt_files = [f for f in os.listdir(str(txt_root)) if f.startswith("_generated_text_")]
        assert len(txt_files) == 1

    def test_unicode_chars_escaped_in_text_file(self, tmp_path):
        lbl = WidgetModel("label", name="title", x=0, y=0, width=100, height=30)
        lbl.properties["text"] = "\u4f60\u597d"  # Chinese characters
        lbl.properties["font_file"] = "test.ttf"
        lbl.properties["font_pixelsize"] = "16"
        lbl.properties["font_fontbitsize"] = "4"

        proj = _make_project_with_widgets([lbl])
        gen = ResourceConfigGenerator()
        gen.generate_and_save(proj, str(tmp_path))

        txt_root = tmp_path / DESIGNER_RESOURCE_DIRNAME
        txt_files = [f for f in os.listdir(str(txt_root)) if f.startswith("_generated_text_")]
        assert len(txt_files) == 1
        content = (txt_root / txt_files[0]).read_text(encoding="utf-8")
        # Non-ASCII chars should be escaped as &#xHHHH;
        assert "&#x" in content

    def test_removes_stale_generated_text_files(self, tmp_path):
        lbl = WidgetModel("label", name="title", x=0, y=0, width=100, height=30)
        lbl.properties["text"] = "Hello"
        lbl.properties["font_file"] = "test.ttf"
        lbl.properties["font_pixelsize"] = "16"
        lbl.properties["font_fontbitsize"] = "4"

        gen = ResourceConfigGenerator()
        gen.generate_and_save(_make_project_with_widgets([lbl]), str(tmp_path))

        txt_root = tmp_path / DESIGNER_RESOURCE_DIRNAME
        txt_files = [f for f in os.listdir(str(txt_root)) if f.startswith("_generated_text_")]
        assert len(txt_files) == 1

        gen.generate_and_save(_make_project_with_widgets([]), str(tmp_path))

        txt_files = [f for f in os.listdir(str(txt_root)) if f.startswith("_generated_text_")]
        assert txt_files == []

    def test_keeps_active_generated_text_files_and_unrelated_designer_files(self, tmp_path):
        title = WidgetModel("label", name="title", x=0, y=0, width=100, height=30)
        title.properties["text"] = "Hello"
        title.properties["font_file"] = "test.ttf"
        title.properties["font_pixelsize"] = "16"
        title.properties["font_fontbitsize"] = "4"

        subtitle = WidgetModel("label", name="subtitle", x=0, y=40, width=100, height=30)
        subtitle.properties["text"] = "World"
        subtitle.properties["font_file"] = "test.ttf"
        subtitle.properties["font_pixelsize"] = "20"
        subtitle.properties["font_fontbitsize"] = "4"

        gen = ResourceConfigGenerator()
        gen.generate_and_save(_make_project_with_widgets([title, subtitle]), str(tmp_path))

        txt_root = tmp_path / DESIGNER_RESOURCE_DIRNAME
        generated_before = sorted(f for f in os.listdir(str(txt_root)) if f.startswith("_generated_text_"))
        assert len(generated_before) == 2
        (txt_root / "notes.txt").write_text("keep me\n", encoding="utf-8")

        gen.generate_and_save(_make_project_with_widgets([title]), str(tmp_path))

        generated_after = sorted(f for f in os.listdir(str(txt_root)) if f.startswith("_generated_text_"))
        assert len(generated_after) == 1
        assert generated_after[0] in generated_before
        assert (txt_root / "notes.txt").is_file()
