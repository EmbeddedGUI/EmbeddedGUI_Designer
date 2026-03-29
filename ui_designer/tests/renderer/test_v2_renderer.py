"""Tests for the V2 preview renderer."""

import io

from PIL import Image

from ui_designer.model.page import Page
from ui_designer.model.widget_model import WidgetModel
from ui_designer.renderer.v2_renderer_qml import V2RendererQml


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
