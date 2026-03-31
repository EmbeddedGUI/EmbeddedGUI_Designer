"""Minimal V2 renderer implementation for high-frequency widgets."""

from __future__ import annotations

import io

from PIL import Image, ImageDraw, ImageFont

from ..engine.layout_engine import compute_page_layout


_BG_COLOR = (28, 28, 30, 255)
_DEFAULT_FONT = ImageFont.load_default()


def _node_name(widget) -> str:
    return str(getattr(widget, "name", "") or getattr(widget, "widget_type", "widget"))


def _hex_to_rgba(hex_text: str, alpha: int = 255) -> tuple[int, int, int, int]:
    text = str(hex_text or "").strip().lstrip("#")
    if len(text) != 6:
        return (96, 96, 96, alpha)
    try:
        return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16), alpha)
    except Exception:
        return (96, 96, 96, alpha)


def _widget_frame(widget) -> tuple[int, int, int, int]:
    x = int(getattr(widget, "display_x", getattr(widget, "x", 0)) or 0)
    y = int(getattr(widget, "display_y", getattr(widget, "y", 0)) or 0)
    w = max(1, int(getattr(widget, "width", 1) or 1))
    h = max(1, int(getattr(widget, "height", 1) or 1))
    return x, y, w, h


class V2RendererQml:
    """Experimental renderer placeholder for V2 rollout."""

    name = "v2"

    def __init__(self):
        self._host = None
        self._last_snapshot = b""
        self._last_render_error = ""

    @property
    def last_render_error(self) -> str:
        return self._last_render_error

    def mount(self, host_widget) -> None:
        self._host = host_widget

    def render(self, schema: dict) -> None:
        self._last_render_error = ""
        page = schema.get("page")
        width = int(schema.get("screen_width", 240) or 240)
        height = int(schema.get("screen_height", 320) or 320)

        if page is None:
            self._last_snapshot = b""
            return

        try:
            compute_page_layout(page)
            image = Image.new("RGBA", (width, height), _BG_COLOR)
            draw = ImageDraw.Draw(image, "RGBA")

            for widget in page.get_all_widgets() or []:
                self._draw_widget(draw, widget)

            out = io.BytesIO()
            image.save(out, format="PNG")
            self._last_snapshot = out.getvalue()
        except Exception as exc:
            self._last_snapshot = b""
            self._last_render_error = str(exc)

    def _draw_widget(self, draw: ImageDraw.ImageDraw, widget) -> None:
        x, y, w, h = _widget_frame(widget)
        wtype = str(getattr(widget, "widget_type", "") or "").strip().lower()
        props = getattr(widget, "properties", {}) or {}

        if wtype == "label":
            text = str(props.get("text", _node_name(widget)))
            draw.text((x + 2, y + 2), text, fill=(225, 225, 230, 255), font=_DEFAULT_FONT)
            return

        if wtype == "button":
            draw.rounded_rectangle([x, y, x + w - 1, y + h - 1], radius=6, fill=(66, 101, 167, 255), outline=(118, 145, 196, 255), width=1)
            text = str(props.get("text", _node_name(widget)))
            bbox = _DEFAULT_FONT.getbbox(text)
            tw = max(1, bbox[2] - bbox[0])
            th = max(1, bbox[3] - bbox[1])
            tx = x + max(0, (w - tw) // 2)
            ty = y + max(0, (h - th) // 2)
            draw.text((tx, ty), text, fill=(242, 245, 252, 255), font=_DEFAULT_FONT)
            return

        if wtype == "image":
            draw.rectangle([x, y, x + w - 1, y + h - 1], fill=(48, 56, 74, 255), outline=(118, 132, 160, 255), width=1)
            draw.line([(x, y), (x + w - 1, y + h - 1)], fill=(138, 152, 180, 255), width=1)
            draw.line([(x + w - 1, y), (x, y + h - 1)], fill=(138, 152, 180, 255), width=1)
            draw.text((x + 4, y + 4), "IMG", fill=(190, 200, 225, 255), font=_DEFAULT_FONT)
            return

        if wtype == "progress_bar":
            value = int(props.get("value", 40) or 40)
            value = max(0, min(100, value))
            draw.rounded_rectangle([x, y, x + w - 1, y + h - 1], radius=4, fill=(55, 58, 64, 255), outline=(80, 84, 92, 255), width=1)
            fill_w = max(1, int((w - 2) * value / 100.0))
            draw.rounded_rectangle([x + 1, y + 1, x + fill_w, y + h - 2], radius=4, fill=(87, 194, 121, 255))
            return

        if wtype == "slider":
            mid = y + max(2, h // 2)
            draw.line([(x + 4, mid), (x + w - 4, mid)], fill=(126, 130, 136, 255), width=3)
            value = int(props.get("value", 50) or 50)
            value = max(0, min(100, value))
            knob_x = x + 4 + int((max(1, w - 8) * value) / 100.0)
            draw.ellipse([knob_x - 6, mid - 6, knob_x + 6, mid + 6], fill=(200, 206, 218, 255), outline=(102, 108, 124, 255), width=1)
            return

        # Fallback generic widget box
        accent = _hex_to_rgba("#4f5562")
        draw.rectangle([x, y, x + w - 1, y + h - 1], fill=(56, 60, 68, 180), outline=accent, width=1)
        draw.text((x + 3, y + 3), wtype or "widget", fill=(205, 210, 218, 255), font=_DEFAULT_FONT)

    def select_node(self, node_id: str | None) -> None:
        return None

    def update_node(self, node_id: str, patch: dict) -> None:
        return None

    def snapshot(self) -> bytes:
        return self._last_snapshot

    def dispose(self) -> None:
        self._host = None
        self._last_snapshot = b""
        self._last_render_error = ""
