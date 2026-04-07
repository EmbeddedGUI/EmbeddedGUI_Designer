"""Python-based preview renderer using Pillow.

Renders a page's widget tree to a PIL Image for fast preview without
compiling C code. Supports basic shapes, text, and widget approximations.
"""

import re

from PIL import Image, ImageDraw, ImageFont

from ..model.widget_model import COLOR_RGB
from .layout_engine import compute_page_layout


# Default background color (dark grey)
_BG_COLOR = (42, 42, 42)

# Fallback font (Pillow default)
_DEFAULT_FONT = ImageFont.load_default()

_HEX_COLOR_RE = re.compile(r'EGUI_COLOR_HEX\(\s*0x([0-9A-Fa-f]{6})\s*\)')
_ALPHA_RE = re.compile(r'EGUI_ALPHA_(\d+)')


def _resolve_color(color_str):
    """Convert an EGUI color string to an RGB tuple."""
    if not color_str:
        return (200, 200, 200)
    rgb = COLOR_RGB.get(color_str)
    if rgb:
        return rgb

    m = _HEX_COLOR_RE.match(str(color_str))
    if m:
        h = m.group(1)
        return (int(h[:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    return (200, 200, 200)


def _resolve_alpha(alpha_str):
    """Convert an EGUI alpha string to a Pillow alpha value."""
    if not alpha_str:
        return 255
    m = _ALPHA_RE.match(str(alpha_str))
    if m:
        pct = int(m.group(1))
        return int(pct * 255 / 100)
    return 255


def _is_truthy(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _clamp_percent(value, default=0):
    try:
        return max(0, min(100, int(value)))
    except (TypeError, ValueError):
        return default


def _resolve_widget_color(props, *keys, default):
    for key in keys:
        value = props.get(key)
        if value not in (None, ""):
            return _resolve_color(value)
    return _resolve_color(default)


def _resolve_widget_alpha(props, *keys, default):
    for key in keys:
        value = props.get(key)
        if value not in (None, ""):
            return _resolve_alpha(value)
    return _resolve_alpha(default)


def _draw_text(draw, position, text, color, alpha, font):
    draw.text(position, str(text), fill=color + (alpha,), font=font)


def _draw_linear_gradient(img, bounds, start_color, end_color, alpha, direction):
    x0, y0, x1, y1 = bounds
    width = max(1, x1 - x0 + 1)
    height = max(1, y1 - y0 + 1)
    draw = ImageDraw.Draw(img, "RGBA")

    if direction == "horizontal":
        span = max(1, width - 1)
        for i in range(width):
            ratio = i / span
            color = tuple(int(start_color[c] + (end_color[c] - start_color[c]) * ratio) for c in range(3))
            draw.line([(x0 + i, y0), (x0 + i, y1)], fill=color + (alpha,))
        return

    span = max(1, height - 1)
    for i in range(height):
        ratio = i / span
        color = tuple(int(start_color[c] + (end_color[c] - start_color[c]) * ratio) for c in range(3))
        draw.line([(x0, y0 + i), (x1, y0 + i)], fill=color + (alpha,))


def _draw_background(img, widget, x, y, w, h):
    """Draw widget background if present."""
    bg = widget.background
    if bg is None or bg.bg_type == "none" or w <= 0 or h <= 0:
        return

    bounds = [x, y, x + w - 1, y + h - 1]
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay, "RGBA")

    bg_type = getattr(bg, "bg_type", "none")
    color = _resolve_color(getattr(bg, "color", ""))
    alpha = _resolve_alpha(getattr(bg, "alpha", "EGUI_ALPHA_100"))
    fill = color + (alpha,)

    if bg_type in ("solid", "rectangle"):
        draw.rectangle(bounds, fill=fill)
    elif bg_type == "gradient":
        _draw_linear_gradient(
            overlay,
            (bounds[0], bounds[1], bounds[2], bounds[3]),
            _resolve_color(getattr(bg, "start_color", "EGUI_COLOR_BLACK")),
            _resolve_color(getattr(bg, "end_color", "EGUI_COLOR_WHITE")),
            alpha,
            getattr(bg, "direction", "vertical"),
        )
    elif bg_type == "round_rectangle":
        radius = max(0, int(getattr(bg, "radius", 0)))
        draw.rounded_rectangle(bounds, radius=radius, fill=fill)
    elif bg_type == "round_rectangle_corners":
        radius = max(
            int(getattr(bg, "radius_left_top", 0)),
            int(getattr(bg, "radius_left_bottom", 0)),
            int(getattr(bg, "radius_right_top", 0)),
            int(getattr(bg, "radius_right_bottom", 0)),
        )
        draw.rounded_rectangle(bounds, radius=radius, fill=fill)
    elif bg_type == "circle":
        draw.ellipse(bounds, fill=fill)

    stroke_width = max(0, int(getattr(bg, "stroke_width", 0)))
    if stroke_width > 0:
        stroke = _resolve_color(getattr(bg, "stroke_color", "EGUI_COLOR_BLACK"))
        stroke_fill = stroke + (_resolve_alpha(getattr(bg, "stroke_alpha", "EGUI_ALPHA_100")),)
        if bg_type == "circle":
            draw.ellipse(bounds, outline=stroke_fill, width=stroke_width)
        elif bg_type in ("round_rectangle", "round_rectangle_corners"):
            radius = max(
                int(getattr(bg, "radius", 0)),
                int(getattr(bg, "radius_left_top", 0)),
                int(getattr(bg, "radius_left_bottom", 0)),
                int(getattr(bg, "radius_right_top", 0)),
                int(getattr(bg, "radius_right_bottom", 0)),
            )
            draw.rounded_rectangle(bounds, radius=radius, outline=stroke_fill, width=stroke_width)
        else:
            draw.rectangle(bounds, outline=stroke_fill, width=stroke_width)

    img.alpha_composite(overlay)


def _render_widget(img, widget, font):
    """Render a single widget onto the target image."""
    x = widget.display_x
    y = widget.display_y
    w = widget.width
    h = widget.height
    wtype = widget.widget_type
    props = widget.properties
    draw = ImageDraw.Draw(img, "RGBA")

    _draw_background(img, widget, x, y, w, h)

    if wtype == "label":
        text = props.get("text", widget.name)
        color = _resolve_widget_color(props, "color", "font_color", "text_color", default="EGUI_COLOR_WHITE")
        alpha = _resolve_widget_alpha(props, "alpha", "font_alpha", "text_alpha", default="EGUI_ALPHA_100")
        _draw_text(draw, (x + 2, y + 2), text, color, alpha, font)

    elif wtype == "button":
        if widget.background is None:
            draw.rounded_rectangle(
                [x, y, x + w - 1, y + h - 1],
                radius=10,
                fill=_resolve_color("EGUI_THEME_PRIMARY") + (255,),
                outline=_resolve_color("EGUI_THEME_PRIMARY_DARK") + (255,),
                width=1,
            )
        text = props.get("text", widget.name)
        color = _resolve_widget_color(props, "color", "font_color", "text_color", default="EGUI_COLOR_WHITE")
        alpha = _resolve_widget_alpha(props, "alpha", "font_alpha", "text_alpha", default="EGUI_ALPHA_100")
        bbox = font.getbbox(str(text))
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        tx = x + (w - tw) // 2
        ty = y + (h - th) // 2
        _draw_text(draw, (tx, ty), text, color, alpha, font)

    elif wtype == "image":
        draw.rectangle([x, y, x + w - 1, y + h - 1], fill=(60, 60, 80, 150))
        draw.line([(x, y), (x + w - 1, y + h - 1)], fill=(100, 100, 120), width=1)
        draw.line([(x + w - 1, y), (x, y + h - 1)], fill=(100, 100, 120), width=1)
        _draw_text(draw, (x + 2, y + 2), "IMG", (150, 150, 170), 255, font)

    elif wtype == "progress_bar":
        value = _clamp_percent(props.get("value", 50), default=50)
        draw.rounded_rectangle(
            [x, y, x + w - 1, y + h - 1],
            radius=3,
            fill=_resolve_color("EGUI_THEME_TRACK_BG") + (255,),
        )
        fill_w = max(1, int(w * value / 100))
        color = _resolve_widget_color(props, "progress_color", "color", default="EGUI_THEME_PRIMARY")
        draw.rounded_rectangle([x, y, x + fill_w - 1, y + h - 1], radius=3, fill=color + (255,))

    elif wtype == "switch":
        checked = _is_truthy(props.get("is_checked", props.get("checked")))
        track_color = _resolve_color("EGUI_THEME_PRIMARY" if checked else "EGUI_THEME_TRACK_OFF")
        draw.rounded_rectangle([x, y, x + w - 1, y + h - 1], radius=h // 2, fill=track_color + (255,))
        thumb_r = max(1, h // 2 - 2)
        cx = x + w - thumb_r - 4 if checked else x + thumb_r + 4
        cy = y + h // 2
        draw.ellipse(
            [cx - thumb_r, cy - thumb_r, cx + thumb_r, cy + thumb_r],
            fill=_resolve_color("EGUI_THEME_THUMB") + (255,),
            outline=_resolve_color("EGUI_THEME_BORDER") + (255,),
        )

    elif wtype == "slider":
        track_y = y + h // 2
        draw.line([(x + 4, track_y), (x + w - 4, track_y)], fill=_resolve_color("EGUI_THEME_TRACK_BG"), width=3)
        value = _clamp_percent(props.get("value", 50), default=50)
        thumb_x = x + 4 + int((w - 8) * value / 100)
        draw.line([(x + 4, track_y), (thumb_x, track_y)], fill=_resolve_color("EGUI_THEME_PRIMARY"), width=3)
        draw.ellipse(
            [thumb_x - 6, track_y - 6, thumb_x + 6, track_y + 6],
            fill=_resolve_color("EGUI_THEME_THUMB") + (255,),
            outline=_resolve_color("EGUI_THEME_BORDER") + (255,),
        )

    elif wtype == "circular_progress_bar":
        value = _clamp_percent(props.get("value", 50), default=50)
        track_color = _resolve_widget_color(props, "bk_color", default="EGUI_THEME_TRACK_BG")
        progress_color = _resolve_widget_color(props, "progress_color", "color", default="EGUI_THEME_PRIMARY")
        draw.ellipse([x + 2, y + 2, x + w - 3, y + h - 3], outline=track_color + (255,), width=3)
        draw.arc(
            [x + 2, y + 2, x + w - 3, y + h - 3],
            start=-90,
            end=-90 + int(360 * value / 100),
            fill=progress_color + (255,),
            width=4,
        )

    elif wtype == "checkbox":
        box_size = min(w, h, 20)
        bx = x + 2
        by = y + (h - box_size) // 2
        text_color = _resolve_widget_color(props, "text_color", "color", default="EGUI_THEME_TEXT_PRIMARY")
        draw.rectangle(
            [bx, by, bx + box_size, by + box_size],
            outline=_resolve_color("EGUI_THEME_BORDER") + (255,),
            width=2,
        )
        if _is_truthy(props.get("is_checked", props.get("checked"))):
            draw.line(
                [(bx + 3, by + box_size // 2), (bx + box_size // 2, by + box_size - 3)],
                fill=_resolve_color("EGUI_THEME_PRIMARY"),
                width=2,
            )
            draw.line(
                [(bx + box_size // 2, by + box_size - 3), (bx + box_size - 3, by + 3)],
                fill=_resolve_color("EGUI_THEME_PRIMARY"),
                width=2,
            )
        text = props.get("text")
        if text:
            _draw_text(draw, (bx + box_size + 6, y + 2), text, text_color, 255, font)

    elif wtype == "radio_button":
        box_size = min(w, h, 20)
        bx = x + 2
        by = y + (h - box_size) // 2
        text_color = _resolve_widget_color(props, "text_color", "color", default="EGUI_THEME_TEXT_PRIMARY")
        draw.ellipse(
            [bx, by, bx + box_size, by + box_size],
            outline=_resolve_color("EGUI_THEME_BORDER") + (255,),
            width=2,
        )
        if _is_truthy(props.get("is_checked", props.get("checked"))):
            inset = max(3, box_size // 4)
            draw.ellipse(
                [bx + inset, by + inset, bx + box_size - inset, by + box_size - inset],
                fill=_resolve_color("EGUI_THEME_PRIMARY") + (255,),
            )
        text = props.get("text")
        if text:
            _draw_text(draw, (bx + box_size + 6, y + 2), text, text_color, 255, font)


def render_page(page, screen_width=240, screen_height=320):
    """Render a Page to a PIL RGBA Image.

    Args:
        page: Page object with root_widget
        screen_width: Canvas width in pixels
        screen_height: Canvas height in pixels

    Returns:
        PIL.Image.Image in RGBA mode
    """
    if page.root_widget:
        compute_page_layout(page)

    img = Image.new("RGBA", (screen_width, screen_height), _BG_COLOR + (255,))
    if page.root_widget is None:
        return img

    def _collect(widget, out):
        out.append(widget)
        for child in widget.children:
            _collect(child, out)

    widgets = []
    _collect(page.root_widget, widgets)

    for w in widgets:
        _render_widget(img, w, _DEFAULT_FONT)

    return img


def render_page_to_bytes(page, screen_width=240, screen_height=320, fmt="PNG"):
    """Render a page and return raw image bytes."""
    import io
    img = render_page(page, screen_width, screen_height)
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()
