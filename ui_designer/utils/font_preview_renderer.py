"""Render font preview cards using the SDK glyph generator when available."""

from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass

try:
    from PIL import Image, ImageDraw, ImageFont
except Exception:  # pragma: no cover - optional dependency
    Image = None
    ImageDraw = None
    ImageFont = None


_TTF2C_MODULE_CACHE: dict[str, object | None] = {}
_CARD_BG = (247, 246, 241, 255)
_CARD_BORDER = (205, 201, 191, 255)
_TEXT_FILL = (35, 35, 35, 255)


@dataclass(frozen=True)
class _GlyphPreview:
    width: int
    height: int
    advance: int
    offset_x: int
    offset_y: int
    data: bytes


def render_font_preview_image(
    *,
    sdk_root: str,
    font_path: str,
    sample_text: str,
    pixel_size: int = 16,
    font_bit_size: int = 4,
    weight: int | None = None,
    width: int = 480,
    height: int = 220,
    padding: int = 18,
    max_lines: int = 3,
):
    """Return a PIL preview image for a font, or ``None`` when rendering fails."""

    if Image is None or ImageDraw is None:
        return None

    compact_text = _compact_preview_text(sample_text)
    image = Image.new("RGBA", (max(int(width), 120), max(int(height), 96)), _CARD_BG)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        (0, 0, image.width - 1, image.height - 1),
        radius=14,
        outline=_CARD_BORDER,
        width=2,
    )

    bounds = (padding, padding, image.width - padding, image.height - padding)
    normalized_size = max(int(pixel_size or 16), 4)
    normalized_bits = _normalize_font_bit_size(font_bit_size)

    if _draw_sdk_preview(
        image,
        sdk_root=sdk_root,
        font_path=font_path,
        sample_text=compact_text,
        pixel_size=normalized_size,
        font_bit_size=normalized_bits,
        weight=weight,
        bounds=bounds,
        max_lines=max_lines,
    ):
        return image

    if _draw_pillow_preview(
        image,
        font_path=font_path,
        sample_text=compact_text,
        pixel_size=normalized_size,
        bounds=bounds,
        max_lines=max_lines,
    ):
        return image

    return None


def _draw_sdk_preview(image, *, sdk_root: str, font_path: str, sample_text: str, pixel_size: int, font_bit_size: int, weight: int | None, bounds, max_lines: int) -> bool:
    module = _load_ttf2c_module(sdk_root)
    if module is None or not hasattr(module, "generate_glyphs_data"):
        return False

    try:
        glyphs_data, _char_max_width, char_max_height = module.generate_glyphs_data(
            font_path,
            sample_text,
            pixel_size,
            font_bit_size,
            weight,
            None,
        )
    except Exception:
        return False

    glyph_map = {
        char: _GlyphPreview(
            width=int(width),
            height=int(height),
            advance=max(int(round(advance_width)), 1),
            offset_x=int(offset_x),
            offset_y=int(offset_y),
            data=bytes(data),
        )
        for char, data, width, height, advance_width, offset_x, offset_y, _utf8_encoding in glyphs_data
    }
    if not glyph_map:
        return False

    content_width = max(1, int(bounds[2] - bounds[0]))
    content_height = max(1, int(bounds[3] - bounds[1]))
    fallback_advance = max(1, pixel_size // 2)
    lines = _wrap_sdk_lines(sample_text, glyph_map, content_width, fallback_advance=fallback_advance, max_lines=max_lines)
    line_gap = max(6, pixel_size // 3)
    line_height = max(int(char_max_height), pixel_size)
    total_text_height = (line_height * len(lines)) + (line_gap * max(len(lines) - 1, 0))
    cursor_y = bounds[1] + max(0, (content_height - total_text_height) // 2)

    for line in lines:
        cursor_x = bounds[0]
        for char in line:
            glyph = glyph_map.get(char)
            if glyph is None:
                cursor_x += fallback_advance
                continue
            mask = _glyph_mask(glyph, font_bit_size)
            if mask is not None:
                fill = Image.new("RGBA", mask.size, _TEXT_FILL)
                image.paste(fill, (int(cursor_x + glyph.offset_x), int(cursor_y + glyph.offset_y)), mask)
            cursor_x += glyph.advance
        cursor_y += line_height + line_gap
    return True


def _draw_pillow_preview(image, *, font_path: str, sample_text: str, pixel_size: int, bounds, max_lines: int) -> bool:
    if ImageFont is None or ImageDraw is None:
        return False

    try:
        font = ImageFont.truetype(font_path, size=max(pixel_size, 10))
    except Exception:
        return False

    draw = ImageDraw.Draw(image)
    max_width = max(1, int(bounds[2] - bounds[0]))
    lines = _wrap_pillow_lines(draw, sample_text, font, max_width=max_width, max_lines=max_lines)
    line_sizes = [draw.textbbox((0, 0), line, font=font) for line in lines]
    line_heights = [max(bbox[3] - bbox[1], pixel_size) for bbox in line_sizes]
    line_gap = max(6, pixel_size // 3)
    total_text_height = sum(line_heights) + (line_gap * max(len(line_heights) - 1, 0))
    cursor_y = bounds[1] + max(0, ((bounds[3] - bounds[1]) - total_text_height) // 2)

    for line, bbox, line_height in zip(lines, line_sizes, line_heights):
        draw.text((bounds[0], cursor_y), line, font=font, fill=_TEXT_FILL)
        cursor_y += line_height + line_gap
    return True


def _wrap_sdk_lines(text: str, glyph_map: dict[str, _GlyphPreview], max_width: int, *, fallback_advance: int, max_lines: int) -> list[str]:
    compact = _compact_preview_text(text)
    lines: list[str] = []
    position = 0

    while position < len(compact) and len(lines) < max_lines:
        end = position + 1
        last_space = -1
        while end <= len(compact):
            candidate = compact[position:end]
            if _measure_sdk_text_width(candidate, glyph_map, fallback_advance=fallback_advance) > max_width and end > position + 1:
                if last_space > position:
                    end = last_space
                else:
                    end -= 1
                break
            if end - 1 >= position and compact[end - 1] == " ":
                last_space = end - 1
            end += 1

        if end <= position:
            end = position + 1

        if len(lines) == max_lines - 1 and end < len(compact):
            line = compact[position:]
            while line and _measure_sdk_text_width(f"{line}...", glyph_map, fallback_advance=fallback_advance) > max_width:
                line = line[:-1]
            lines.append(f"{line.rstrip()}..." if line else "...")
            return lines

        line = compact[position:end].rstrip()
        if not line:
            break
        lines.append(line)
        position = end
        while position < len(compact) and compact[position] == " ":
            position += 1

    return lines or [compact]


def _wrap_pillow_lines(draw, text: str, font, *, max_width: int, max_lines: int) -> list[str]:
    compact = _compact_preview_text(text)
    lines: list[str] = []
    position = 0

    while position < len(compact) and len(lines) < max_lines:
        end = position + 1
        last_space = -1
        while end <= len(compact):
            candidate = compact[position:end]
            bbox = draw.textbbox((0, 0), candidate, font=font)
            if bbox[2] - bbox[0] > max_width and end > position + 1:
                if last_space > position:
                    end = last_space
                else:
                    end -= 1
                break
            if end - 1 >= position and compact[end - 1] == " ":
                last_space = end - 1
            end += 1

        if end <= position:
            end = position + 1

        if len(lines) == max_lines - 1 and end < len(compact):
            line = compact[position:]
            while line and draw.textbbox((0, 0), f"{line}...", font=font)[2] > max_width:
                line = line[:-1]
            lines.append(f"{line.rstrip()}..." if line else "...")
            return lines

        line = compact[position:end].rstrip()
        if not line:
            break
        lines.append(line)
        position = end
        while position < len(compact) and compact[position] == " ":
            position += 1

    return lines or [compact]


def _measure_sdk_text_width(text: str, glyph_map: dict[str, _GlyphPreview], *, fallback_advance: int) -> int:
    width = 0
    for char in text:
        glyph = glyph_map.get(char)
        width += glyph.advance if glyph is not None else fallback_advance
    return width


def _glyph_mask(glyph: _GlyphPreview, font_bit_size: int):
    if glyph.width <= 0 or glyph.height <= 0:
        return None
    decoded = _decode_glyph_alpha(glyph.data, glyph.width, glyph.height, font_bit_size)
    if decoded is None:
        return None
    return Image.frombytes("L", (glyph.width, glyph.height), bytes(decoded))


def _decode_glyph_alpha(data: bytes, width: int, height: int, font_bit_size: int) -> bytearray | None:
    if width <= 0 or height <= 0:
        return bytearray()

    pixels = bytearray(width * height)
    if font_bit_size == 8:
        expected = width * height
        if len(data) < expected:
            return None
        pixels[:expected] = data[:expected]
        return pixels

    if font_bit_size == 4:
        row_bytes = (width + 1) // 2
        if len(data) < row_bytes * height:
            return None
        for y in range(height):
            row = data[y * row_bytes : (y + 1) * row_bytes]
            for x in range(width):
                value = (row[x // 2] >> ((x % 2) * 4)) & 0x0F
                pixels[(y * width) + x] = value * 17
        return pixels

    if font_bit_size == 2:
        row_bytes = (width + 3) // 4
        if len(data) < row_bytes * height:
            return None
        for y in range(height):
            row = data[y * row_bytes : (y + 1) * row_bytes]
            for x in range(width):
                value = (row[x // 4] >> ((x % 4) * 2)) & 0x03
                pixels[(y * width) + x] = value * 85
        return pixels

    if font_bit_size == 1:
        row_bytes = (width + 7) // 8
        if len(data) < row_bytes * height:
            return None
        for y in range(height):
            row = data[y * row_bytes : (y + 1) * row_bytes]
            for x in range(width):
                value = (row[x // 8] >> (x % 8)) & 0x01
                pixels[(y * width) + x] = 255 if value else 0
        return pixels

    return None


def _load_ttf2c_module(sdk_root: str):
    script_path = _ttf2c_script_path(sdk_root)
    if not script_path:
        return None
    cached = _TTF2C_MODULE_CACHE.get(script_path, None)
    if script_path in _TTF2C_MODULE_CACHE:
        return cached

    try:
        spec = importlib.util.spec_from_file_location("_embeddedgui_ttf2c_preview", script_path)
        if spec is None or spec.loader is None:
            _TTF2C_MODULE_CACHE[script_path] = None
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception:
        _TTF2C_MODULE_CACHE[script_path] = None
        return None

    _TTF2C_MODULE_CACHE[script_path] = module
    return module


def _ttf2c_script_path(sdk_root: str) -> str:
    normalized_root = os.path.abspath(os.path.normpath(str(sdk_root or "")))
    if not normalized_root:
        return ""
    candidate = os.path.join(normalized_root, "scripts", "tools", "ttf2c.py")
    return candidate if os.path.isfile(candidate) else ""


def _compact_preview_text(text: str) -> str:
    compact = " ".join(str(text or "").split()).strip()
    return compact or "AaBb 123"


def _normalize_font_bit_size(value) -> int:
    try:
        parsed = int(str(value or "").strip())
    except Exception:
        return 4
    return parsed if parsed in {1, 2, 4, 8} else 4
