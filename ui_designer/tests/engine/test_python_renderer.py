"""Tests for the Python preview renderer."""

import pytest
from PIL import Image
from PIL import ImageFont

from ui_designer.engine.python_renderer import (
    _resolve_color,
    _resolve_alpha,
    _render_widget,
    render_page,
    render_page_to_bytes,
)
from ui_designer.tests.page_builders import build_test_page, build_test_page_with_root, build_test_page_with_widget
from ui_designer.model.widget_model import WidgetModel, BackgroundModel
from ui_designer.model.page import Page


class TestResolveColor:
    def test_named_color(self):
        assert _resolve_color("EGUI_COLOR_RED") == (255, 0, 0)

    def test_theme_color(self):
        assert _resolve_color("EGUI_THEME_PRIMARY") == (0x25, 0x63, 0xEB)

    def test_hex_color(self):
        assert _resolve_color("EGUI_COLOR_HEX(0x123456)") == (18, 52, 86)

    def test_unknown_color(self):
        assert _resolve_color("UNKNOWN") == (200, 200, 200)

    def test_empty(self):
        assert _resolve_color("") == (200, 200, 200)
        assert _resolve_color(None) == (200, 200, 200)


class TestResolveAlpha:
    def test_alpha_100(self):
        assert _resolve_alpha("EGUI_ALPHA_100") == 255

    def test_alpha_50(self):
        assert _resolve_alpha("EGUI_ALPHA_50") == 127

    def test_alpha_0(self):
        assert _resolve_alpha("EGUI_ALPHA_0") == 0

    def test_empty(self):
        assert _resolve_alpha("") == 255
        assert _resolve_alpha(None) == 255


class TestRenderPage:
    class RecordingDraw:
        def __init__(self):
            self.calls = []

        def text(self, position, text, fill=None, font=None):
            self.calls.append(("text", position, text, fill))

        def rounded_rectangle(self, *args, **kwargs):
            self.calls.append(("rounded_rectangle", args, kwargs))

        def rectangle(self, *args, **kwargs):
            self.calls.append(("rectangle", args, kwargs))

        def line(self, *args, **kwargs):
            self.calls.append(("line", args, kwargs))

        def ellipse(self, *args, **kwargs):
            self.calls.append(("ellipse", args, kwargs))

        def arc(self, *args, **kwargs):
            self.calls.append(("arc", args, kwargs))

    def test_empty_page(self):
        page = Page(file_path="test.xml", root_widget=None)
        img = render_page(page, 240, 320)
        assert isinstance(img, Image.Image)
        assert img.size == (240, 320)
        assert img.mode == "RGBA"

    def test_page_with_label(self):
        page, label = build_test_page_with_widget(
            "test",
            name="lbl",
            x=10,
            y=10,
            width=100,
            height=30,
        )
        label.properties["text"] = "Hello"
        img = render_page(page, 240, 320)
        assert img.size == (240, 320)

    def test_page_with_button(self):
        page, btn = build_test_page_with_widget(
            "test",
            "button",
            name="btn",
            x=10,
            y=50,
            width=100,
            height=40,
        )
        btn.properties["text"] = "Click"
        img = render_page(page, 240, 320)
        assert img.size == (240, 320)

    def test_page_with_progress_bar(self):
        page, pb = build_test_page_with_widget(
            "test",
            "progress_bar",
            name="pb",
            x=10,
            y=100,
            width=200,
            height=20,
        )
        pb.properties["value"] = 75
        img = render_page(page, 240, 320)
        assert img.size == (240, 320)

    def test_page_with_background(self):
        page, root = build_test_page_with_root("test")
        root.name = "root"
        root.background = BackgroundModel()
        root.background.bg_type = "solid"
        root.background.color = "EGUI_COLOR_BLUE"
        img = render_page(page, 240, 320)
        assert img.size == (240, 320)
        assert img.getpixel((20, 20))[:3] == (0, 0, 255)

    def test_render_page_can_skip_layout_when_already_ready(self, monkeypatch):
        page = build_test_page("test")
        calls = {"compute_page_layout": 0}

        def fake_compute_page_layout(_page):
            calls["compute_page_layout"] += 1

        monkeypatch.setattr("ui_designer.engine.python_renderer.compute_page_layout", fake_compute_page_layout)

        render_page(page, 240, 320, layout_ready=True)

        assert calls == {"compute_page_layout": 0}

    def test_label_uses_color_property_for_text(self, monkeypatch):
        recorded = self.RecordingDraw()
        monkeypatch.setattr("ui_designer.engine.python_renderer.ImageDraw.Draw", lambda *args, **kwargs: recorded)

        label = WidgetModel("label", name="lbl", x=10, y=10, width=100, height=30)
        label.properties["text"] = "Hello"
        label.properties["color"] = "EGUI_COLOR_BLACK"
        label.display_x = 10
        label.display_y = 10

        _render_widget(Image.new("RGBA", (120, 40), (0, 0, 0, 0)), label, ImageFont.load_default())

        text_calls = [call for call in recorded.calls if call[0] == "text"]
        assert text_calls
        assert text_calls[0][3] == (0, 0, 0, 255)

    def test_button_uses_color_property_for_text(self, monkeypatch):
        recorded = self.RecordingDraw()
        monkeypatch.setattr("ui_designer.engine.python_renderer.ImageDraw.Draw", lambda *args, **kwargs: recorded)

        button = WidgetModel("button", name="btn", x=10, y=10, width=100, height=30)
        button.properties["text"] = "Click"
        button.properties["color"] = "EGUI_COLOR_BLACK"
        button.display_x = 10
        button.display_y = 10

        _render_widget(Image.new("RGBA", (140, 50), (0, 0, 0, 0)), button, ImageFont.load_default())

        rounded_calls = [call for call in recorded.calls if call[0] == "rounded_rectangle"]
        text_calls = [call for call in recorded.calls if call[0] == "text"]
        assert rounded_calls
        assert rounded_calls[0][2]["fill"] == (0x25, 0x63, 0xEB, 255)
        assert text_calls
        assert text_calls[0][3] == (0, 0, 0, 255)

    def test_render_to_bytes(self):
        page = build_test_page("test")
        data = render_page_to_bytes(page, 240, 320)
        assert isinstance(data, bytes)
        assert len(data) > 0
        # Verify it's valid PNG
        assert data[:4] == b'\x89PNG'
