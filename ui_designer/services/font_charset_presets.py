"""Preset character-set builders for Designer-managed font text resources."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import re


_ENTITY_RE = re.compile(r"&#x([0-9A-Fa-f]+);")


@dataclass(frozen=True)
class CharsetPreset:
    """Descriptor for a built-in charset preset."""

    preset_id: str
    label: str
    description: str
    default_filename: str


@dataclass(frozen=True)
class CharsetContribution:
    """How many new chars a preset or custom input contributed."""

    source_id: str
    label: str
    total_chars: int
    added_chars: int


@dataclass(frozen=True)
class CharsetBuildResult:
    """Expanded result from combining presets and custom chars."""

    chars: tuple[str, ...]
    contributions: tuple[CharsetContribution, ...]

    @property
    def total_chars(self) -> int:
        return len(self.chars)


@dataclass(frozen=True)
class CharsetDiff:
    """Character-level diff summary for overwrite previews."""

    existing_count: int
    new_count: int
    added_count: int
    removed_count: int
    added_chars: tuple[str, ...]
    removed_chars: tuple[str, ...]


_PRESETS = (
    CharsetPreset(
        preset_id="ascii_printable",
        label="ASCII 可显示字符",
        description="95 个可打印 ASCII 字符（0x20-0x7E）。",
        default_filename="charset_ascii_printable.txt",
    ),
    CharsetPreset(
        preset_id="gb2312_fullwidth_symbols",
        label="GB2312 全角符号",
        description="GB2312 区位 01-09，共 682 个字符。",
        default_filename="charset_gb2312_fullwidth_symbols.txt",
    ),
    CharsetPreset(
        preset_id="gb2312_level1_hanzi",
        label="GB2312 一级汉字",
        description="GB2312 区位 16-55，共 3755 个字符。",
        default_filename="charset_gb2312_level1_hanzi.txt",
    ),
    CharsetPreset(
        preset_id="gb2312_level2_hanzi",
        label="GB2312 二级汉字",
        description="GB2312 区位 56-87，共 3008 个字符。",
        default_filename="charset_gb2312_level2_hanzi.txt",
    ),
    CharsetPreset(
        preset_id="gb2312_all",
        label="GB2312 全部字符",
        description="GB2312 全部有效双字节字符，并包含 ASCII 95 个字符，共 7540 个。",
        default_filename="charset_gb2312_all.txt",
    ),
    CharsetPreset(
        preset_id="gbk_all",
        label="GBK 全部字符",
        description="GBK 全部有效双字节字符，并包含 ASCII 95 个字符，共 21886 个。",
        default_filename="charset_gbk_all.txt",
    ),
)

_PRESET_MAP = {preset.preset_id: preset for preset in _PRESETS}


def charset_presets() -> tuple[CharsetPreset, ...]:
    """Return the built-in charset presets in UI order."""

    return _PRESETS


def get_charset_preset(preset_id: str) -> CharsetPreset:
    """Return a preset descriptor by id."""

    return _PRESET_MAP[preset_id]


def _dedupe_preserve(chars) -> tuple[str, ...]:
    seen = set()
    ordered = []
    for ch in chars:
        if not ch or ch in seen:
            continue
        seen.add(ch)
        ordered.append(ch)
    return tuple(ordered)


def _ascii_printable_chars() -> tuple[str, ...]:
    return tuple(chr(codepoint) for codepoint in range(0x20, 0x7F))


def _decode_bytes_char(encoding: str, hi: int, lo: int) -> str:
    try:
        decoded = bytes((hi, lo)).decode(encoding)
    except Exception:
        return ""
    return decoded if len(decoded) == 1 else ""


def _gb2312_zone_chars(zone_start: int, zone_end: int) -> tuple[str, ...]:
    chars = []
    for zone in range(zone_start, zone_end + 1):
        hi = 0xA0 + zone
        for pos in range(1, 95):
            lo = 0xA0 + pos
            ch = _decode_bytes_char("gb2312", hi, lo)
            if ch:
                chars.append(ch)
    return _dedupe_preserve(chars)


def _gb2312_all_double_byte_chars() -> tuple[str, ...]:
    chars = []
    for hi in range(0xA1, 0xF8):
        for lo in range(0xA1, 0xFF):
            ch = _decode_bytes_char("gb2312", hi, lo)
            if ch:
                chars.append(ch)
    return _dedupe_preserve(chars)


def _gbk_all_double_byte_chars() -> tuple[str, ...]:
    chars = []
    lows = tuple(range(0x40, 0x7F)) + tuple(range(0x80, 0xFF))
    for hi in range(0x81, 0xFF):
        for lo in lows:
            ch = _decode_bytes_char("gbk", hi, lo)
            if ch:
                chars.append(ch)
    return _dedupe_preserve(chars)


@lru_cache(maxsize=None)
def charset_chars_for_preset(preset_id: str) -> tuple[str, ...]:
    """Return the ordered chars for a preset."""

    if preset_id == "ascii_printable":
        return _ascii_printable_chars()
    if preset_id == "gb2312_fullwidth_symbols":
        return _gb2312_zone_chars(1, 9)
    if preset_id == "gb2312_level1_hanzi":
        return _gb2312_zone_chars(16, 55)
    if preset_id == "gb2312_level2_hanzi":
        return _gb2312_zone_chars(56, 87)
    if preset_id == "gb2312_all":
        return _dedupe_preserve(_ascii_printable_chars() + _gb2312_all_double_byte_chars())
    if preset_id == "gbk_all":
        return _dedupe_preserve(_ascii_printable_chars() + _gbk_all_double_byte_chars())
    raise KeyError(preset_id)


def charset_count_for_preset(preset_id: str) -> int:
    """Return the total char count for a preset."""

    return len(charset_chars_for_preset(preset_id))


def decode_charset_text(text: str) -> str:
    """Resolve ``&#xHHHH;`` entities while keeping literal text intact."""

    raw = str(text or "")
    return _ENTITY_RE.sub(lambda m: chr(int(m.group(1), 16)), raw)


def custom_chars_from_text(text: str) -> tuple[str, ...]:
    """Expand freeform input into ordered chars, ignoring line breaks only."""

    decoded = decode_charset_text(text)
    chars = []
    for ch in decoded:
        if ch in "\r\n":
            continue
        chars.append(ch)
    return _dedupe_preserve(chars)


def build_charset(preset_ids, custom_text: str = "") -> CharsetBuildResult:
    """Combine selected presets and custom chars with stable first-seen order."""

    seen = set()
    chars = []
    contributions = []

    for preset_id in preset_ids:
        preset = get_charset_preset(preset_id)
        preset_chars = charset_chars_for_preset(preset_id)
        added = 0
        for ch in preset_chars:
            if ch in seen:
                continue
            seen.add(ch)
            chars.append(ch)
            added += 1
        contributions.append(
            CharsetContribution(
                source_id=preset_id,
                label=preset.label,
                total_chars=len(preset_chars),
                added_chars=added,
            )
        )

    custom_chars = custom_chars_from_text(custom_text)
    if custom_chars:
        added = 0
        for ch in custom_chars:
            if ch in seen:
                continue
            seen.add(ch)
            chars.append(ch)
            added += 1
        contributions.append(
            CharsetContribution(
                source_id="custom",
                label="自定义补充",
                total_chars=len(custom_chars),
                added_chars=added,
            )
        )

    return CharsetBuildResult(chars=tuple(chars), contributions=tuple(contributions))


def serialize_charset_chars(chars) -> str:
    """Serialize chars as one codepoint per line for stable project resources."""

    lines = [_serialize_charset_char(ch) for ch in chars]
    return ("\n".join(lines) + "\n") if lines else ""


def _serialize_charset_char(ch: str) -> str:
    if not ch:
        return ""
    codepoint = ord(ch)
    if 0x21 <= codepoint <= 0x7E:
        return ch
    return f"&#x{codepoint:04X};"


def preview_charset_chars(chars, limit: int = 12) -> str:
    """Return a compact preview snippet for UI summaries."""

    tokens = [_serialize_charset_char(ch) for ch in tuple(chars)[: max(int(limit or 0), 0)]]
    return " ".join(tokens)


def suggest_charset_filename(preset_ids, custom_text: str = "") -> str:
    """Return a stable suggested filename for the current selection."""

    preset_ids = tuple(preset_ids)
    has_custom = bool(custom_chars_from_text(custom_text))
    if len(preset_ids) == 1 and not has_custom:
        return get_charset_preset(preset_ids[0]).default_filename
    if len(preset_ids) == 1 and has_custom:
        preset = get_charset_preset(preset_ids[0])
        stem, _ext = preset.default_filename.rsplit(".", 1)
        return f"{stem}_custom.txt"
    if not preset_ids and has_custom:
        return "charset_custom.txt"
    if preset_ids and has_custom:
        return "charset_combo_custom.txt"
    if len(preset_ids) > 1:
        return "charset_combo.txt"
    return "charset.txt"


def summarize_charset_diff(existing_text: str, new_chars) -> CharsetDiff:
    """Compare an existing text file body with a newly generated charset."""

    existing_chars = custom_chars_from_text(existing_text)
    new_chars = _dedupe_preserve(new_chars)

    existing_set = set(existing_chars)
    new_set = set(new_chars)
    added_chars = tuple(ch for ch in new_chars if ch not in existing_set)
    removed_chars = tuple(ch for ch in existing_chars if ch not in new_set)

    return CharsetDiff(
        existing_count=len(existing_chars),
        new_count=len(new_chars),
        added_count=len(added_chars),
        removed_count=len(removed_chars),
        added_chars=added_chars,
        removed_chars=removed_chars,
    )
