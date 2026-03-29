"""Tests for the V2 preview renderer."""

import io

from PIL import Image

from ui_designer.model.page import Page
from ui_designer.model.widget_model import WidgetModel
from ui_designer.renderer import v2_renderer_qml as v2_mod
from ui_designer.renderer.v2_renderer_qml import V2RendererQml


_BG_COLOR = (28, 28, 30, 255)


def _render_snapshot(root: WidgetModel, width=240, height=320) -> bytes:
    page = Page(file_path="test.xml", root_widget=root)
    renderer = V2RendererQml()
    renderer.render({"page": page, "screen_width": width, "screen_height": height})
    return renderer.snapshot()


def test_v2_renders_label_button_image():
    root = WidgetModel("group", name="root", x=0, y=0, width=240, height=320)

    label = WidgetModel("label", name="lbl", x=10, y=10, width=120, height=30)
    label.properties["text"] = "Hello"

    button = WidgetModel("button", name="btn", x=10, y=60, width=120, height=40)
    button.properties["text"] = "Tap"

    image = WidgetModel("image", name="img", x=10, y=120, width=80, height=60)

    root.add_child(label)
    root.add_child(button)
    root.add_child(image)

    data = _render_snapshot(root)
    assert isinstance(data, bytes)
    assert data[:4] == b"\x89PNG"

    img = Image.open(io.BytesIO(data))
    assert img.size == (240, 320)
    assert img.mode == "RGBA"


def test_v2_renders_progress_and_slider_with_visible_non_background_pixels():
    root = WidgetModel("group", name="root", x=0, y=0, width=240, height=320)

    progress = WidgetModel("progress_bar", name="pb", x=20, y=30, width=140, height=18)
    progress.properties["value"] = 70

    slider = WidgetModel("slider", name="sd", x=20, y=70, width=140, height=24)
    slider.properties["value"] = 35

    root.add_child(progress)
    root.add_child(slider)

    data = _render_snapshot(root)
    img = Image.open(io.BytesIO(data)).convert("RGBA")

    progress_pixels = [img.getpixel((px, 38)) for px in range(20, 160)]
    assert any(pixel != _BG_COLOR for pixel in progress_pixels)

    slider_pixels = [img.getpixel((px, 82)) for px in range(20, 160)]
    assert any(pixel != _BG_COLOR for pixel in slider_pixels)


def test_v2_reports_error_and_clears_snapshot_when_layout_raises(monkeypatch):
    root = WidgetModel("group", name="root", x=0, y=0, width=240, height=320)
    root.add_child(WidgetModel("label", name="lbl", x=8, y=8, width=100, height=20))
    page = Page(file_path="test.xml", root_widget=root)

    renderer = V2RendererQml()

    def _raise_layout(_page):
        raise RuntimeError("layout boom")

    monkeypatch.setattr(v2_mod, "compute_page_layout", _raise_layout)

    renderer.render({"page": page, "screen_width": 240, "screen_height": 320})

    assert renderer.snapshot() == b""
    assert "layout boom" in renderer.last_render_error
