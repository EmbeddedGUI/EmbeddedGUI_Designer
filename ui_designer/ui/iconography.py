"""Lightweight icon and preview drawing helpers for the designer UI."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from PyQt5.QtCore import QByteArray, QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QFont, QFontDatabase, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PyQt5.QtWidgets import QApplication
try:
    from PyQt5.QtSvg import QSvgRenderer
except Exception:  # optional runtime dependency path
    QSvgRenderer = None

try:
    from qfluentwidgets import FluentIcon as FIF
except Exception:  # optional runtime dependency path
    FIF = None


_WIDGET_ICON_KEYS = {
    "activity_ring": "display",
    "analog_clock": "time",
    "animated_image": "image",
    "autocomplete": "input",
    "button": "button",
    "button_matrix": "grid",
    "card": "card",
    "chart": "chart",
    "chart_bar": "chart",
    "chart_line": "chart",
    "chart_pie": "chart",
    "chart_scatter": "chart",
    "checkbox": "toggle",
    "chips": "tag",
    "circular_progress_bar": "progress",
    "combobox": "input",
    "compass": "navigation",
    "digital_clock": "time",
    "divider": "divider",
    "dynamic_label": "text",
    "gauge": "chart",
    "gridlayout": "layout",
    "group": "layout",
    "heart_rate": "chart",
    "image": "image",
    "image_button": "button",
    "keyboard": "input",
    "label": "text",
    "led": "status",
    "line": "divider",
    "linearlayout": "layout",
    "list": "list",
    "menu": "navigation",
    "mini_calendar": "calendar",
    "mp4": "media",
    "notification_badge": "status",
    "number_picker": "input",
    "page_indicator": "navigation",
    "pattern_lock": "security",
    "progress_bar": "progress",
    "radio_button": "toggle",
    "roller": "input",
    "scale": "chart",
    "scroll": "layout",
    "segmented_control": "navigation",
    "slider": "input",
    "spangroup": "layout",
    "spinner": "progress",
    "stepper": "input",
    "stopwatch": "time",
    "switch": "toggle",
    "tab_bar": "navigation",
    "table": "table",
    "textblock": "text",
    "textinput": "input",
    "tileview": "grid",
    "toggle_button": "toggle",
    "viewpage": "page",
    "viewpage_cache": "page",
    "window": "window",
}

# ICON guideline v1: same-semantics-single-icon + rounded outlined style.
# Canonical semantic IDs (toolbar/nav/layout/state) are mapped to Material glyphs.
_ICON_DEFINITIONS = {
    # Toolbar P0
    "toolbar.new": {"glyph": "add_circle", "size": 20, "token": "default"},
    "toolbar.open": {"glyph": "folder_open", "size": 20, "token": "default"},
    "toolbar.save": {"glyph": "save", "size": 20, "token": "default"},
    "toolbar.undo": {"glyph": "undo", "size": 20, "token": "default"},
    "toolbar.redo": {"glyph": "redo", "size": 20, "token": "default"},
    "toolbar.copy": {"glyph": "content_copy", "size": 20, "token": "default"},
    "toolbar.paste": {"glyph": "content_paste", "size": 20, "token": "default"},
    "toolbar.delete": {"glyph": "delete_outline", "size": 20, "token": "default"},
    "toolbar.preview": {"glyph": "visibility", "size": 20, "token": "default"},
    "toolbar.compile": {"glyph": "play_circle", "size": 20, "token": "default"},
    "toolbar.stop": {"glyph": "stop", "size": 20, "token": "default"},
    "toolbar.export": {"glyph": "upload", "size": 20, "token": "default"},
    "toolbar.settings.project": {"glyph": "settings", "size": 20, "token": "default"},
    "toolbar.settings.global": {"glyph": "tune", "size": 20, "token": "default"},

    # Navigation P0
    "nav.project": {"glyph": "folder", "size": 20, "token": "default"},
    "nav.structure": {"glyph": "account_tree", "size": 20, "token": "default"},
    "nav.page": {"glyph": "description", "size": 20, "token": "default"},
    "nav.page_group": {"glyph": "folder", "size": 20, "token": "default"},
    "nav.template": {"glyph": "dashboard", "size": 20, "token": "default"},
    "nav.component_library": {"glyph": "widgets", "size": 20, "token": "default"},
    "nav.resource": {"glyph": "perm_media", "size": 20, "token": "default"},
    "nav.expand": {"glyph": "chevron_right", "size": 20, "token": "muted"},
    "nav.collapse": {"glyph": "expand_more", "size": 20, "token": "muted"},

    # Inspector/layout P0
    "layout.align.left": {"glyph": "format_align_left", "size": 18, "token": "default"},
    "layout.align.center": {"glyph": "format_align_center", "size": 18, "token": "default"},
    "layout.align.right": {"glyph": "format_align_right", "size": 18, "token": "default"},
    "layout.align.top": {"glyph": "vertical_align_top", "size": 18, "token": "default"},
    "layout.align.middle": {"glyph": "vertical_align_center", "size": 18, "token": "default"},
    "layout.align.bottom": {"glyph": "vertical_align_bottom", "size": 18, "token": "default"},
    "layout.distribute.h": {"glyph": "view_week", "size": 18, "token": "default"},
    "layout.distribute.v": {"glyph": "view_stream", "size": 18, "token": "default"},
    "edit.visible": {"glyph": "visibility", "size": 18, "token": "default"},
    "edit.hidden": {"glyph": "visibility_off", "size": 18, "token": "muted"},
    "edit.lock": {"glyph": "lock", "size": 18, "token": "default"},
    "edit.unlock": {"glyph": "lock_open", "size": 18, "token": "default"},

    # State/status
    "state.success": {"glyph": "check_circle", "size": 16, "token": "success"},
    "state.warn": {"glyph": "warning_amber", "size": 16, "token": "warn"},
    "state.error": {"glyph": "error", "size": 16, "token": "error"},
    "state.info": {"glyph": "info", "size": 16, "token": "info"},
    "state.progress": {"glyph": "hourglass_empty", "size": 16, "token": "info"},

    # Canvas operations P1
    "canvas.select": {"glyph": "ads_click", "size": 18, "token": "default"},
    "canvas.drag": {"glyph": "pan_tool", "size": 18, "token": "default"},
    "canvas.zoom_in": {"glyph": "zoom_in", "size": 18, "token": "default"},
    "canvas.zoom_out": {"glyph": "zoom_out", "size": 18, "token": "default"},
    "canvas.rotate": {"glyph": "rotate_right", "size": 18, "token": "default"},
    "canvas.layer.up": {"glyph": "vertical_align_top", "size": 18, "token": "default"},
    "canvas.layer.down": {"glyph": "vertical_align_bottom", "size": 18, "token": "default"},
    "canvas.layer.top": {"glyph": "vertical_align_top", "size": 18, "token": "default"},
    "canvas.layer.bottom": {"glyph": "vertical_align_bottom", "size": 18, "token": "default"},
    "canvas.grid": {"glyph": "grid_view", "size": 18, "token": "muted"},
    "canvas.snap": {"glyph": "my_location", "size": 18, "token": "muted"},
    "canvas.ruler": {"glyph": "straighten", "size": 18, "token": "muted"},
    "canvas.guides": {"glyph": "grid_view", "size": 18, "token": "muted"},
}

# Legacy key compatibility: all old callsites still route to canonical semantics.
_ICON_ALIASES = {
    "project": "nav.project",
    "structure": "nav.structure",
    "widgets": "nav.component_library",
    "assets": "nav.resource",
    "properties": "toolbar.settings.global",
    "animation": "toolbar.preview",
    "page": "nav.page",
    "diagnostics": "state.error",
    "history": "state.info",
    "debug": "state.warn",
    "save": "toolbar.save",
    "compile": "toolbar.compile",
    "stop": "toolbar.stop",
    "undo": "toolbar.undo",
    "redo": "toolbar.redo",
    "copy": "toolbar.copy",
    "paste": "toolbar.paste",
    "more": "toolbar.settings.global",
    "settings": "toolbar.settings.global",
    "warning": "state.warn",
    "success": "state.success",
    "info": "state.info",
    "resource": "nav.resource",
    "resources": "nav.resource",
    "zoom_in": "canvas.zoom_in",
    "zoom_out": "canvas.zoom_out",
    "grid": "canvas.grid",
    "ruler": "canvas.ruler",
    "preview": "toolbar.preview",
    "add": "toolbar.new",
    "remove": "toolbar.delete",
    # Widget semantics fallback
    "button": "nav.component_library",
    "layout": "layout.align.left",
    "input": "nav.component_library",
    "toggle": "edit.visible",
    "navigation": "nav.page",
    "chart": "nav.template",
    "media": "toolbar.preview",
    "image": "nav.resource",
    "text": "nav.page",
    "list": "nav.page",
    "grid": "nav.template",
    "status": "state.info",
    "progress": "state.progress",
    "divider": "layout.distribute.h",
    "calendar": "nav.template",
    "security": "edit.lock",
    "window": "nav.template",
    "time": "state.progress",
    "table": "nav.template",
    "tag": "nav.template",
    "card": "nav.template",
    "widget": "nav.component_library",
}

ICON_SEMANTIC_MAP = {k: v["glyph"] for k, v in _ICON_DEFINITIONS.items()}

_FLUENT_ICON_MAP = {
    "toolbar.new": "ADD",
    "toolbar.open": "FOLDER",
    "toolbar.save": "SAVE",
    "toolbar.undo": "RETURN",
    "toolbar.redo": "SYNC",
    "toolbar.copy": "COPY",
    "toolbar.paste": "PASTE",
    "toolbar.delete": "DELETE",
    "toolbar.preview": "VIEW",
    "toolbar.compile": "PLAY",
    "toolbar.stop": "STOP_WATCH",
    "toolbar.export": "SHARE",
    "toolbar.settings.project": "SETTING",
    "toolbar.settings.global": "SETTING",

    "nav.project": "FOLDER",
    "nav.structure": "MENU",
    "nav.page": "DOCUMENT",
    "nav.page_group": "FOLDER",
    "nav.template": "LAYOUT",
    "nav.component_library": "LIBRARY",
    "nav.resource": "IMAGE_EXPORT",
    "nav.expand": "CHEVRON_RIGHT",
    "nav.collapse": "CHEVRON_DOWN_MED",

    "layout.align.left": "LEFT",
    "layout.align.center": "ALIGNMENT",
    "layout.align.right": "RIGHT",
    "layout.align.top": "UP",
    "layout.align.middle": "ALIGNMENT",
    "layout.align.bottom": "DOWN",
    "layout.distribute.h": "TILES",
    "layout.distribute.v": "LAYOUT",

    "edit.visible": "VIEW",
    "edit.hidden": "HIDE",
    "edit.lock": "PIN",
    "edit.unlock": "UNPIN",

    "state.success": "COMPLETED",
    "state.warn": "IMPORTANT",
    "state.error": "CANCEL_MEDIUM",
    "state.info": "INFO",
    "state.progress": "HISTORY",

    "canvas.select": "CLIPPING_TOOL",
    "canvas.drag": "MOVE",
    "canvas.zoom_in": "ZOOM_IN",
    "canvas.zoom_out": "ZOOM_OUT",
    "canvas.rotate": "ROTATE",
    "canvas.layer.up": "UP",
    "canvas.layer.down": "DOWN",
    "canvas.layer.top": "UP",
    "canvas.layer.bottom": "DOWN",
    "canvas.grid": "TILES",
    "canvas.snap": "PIN",
    "canvas.ruler": "UNIT",
    "canvas.guides": "LAYOUT",
}

_LUCIDE_DIR = Path(__file__).resolve().parent.parent / "assets" / "icons" / "lucide"

_LUCIDE_KEY_MAP = {
    # Toolbar / command semantics
    "toolbar.new": "plus",
    "toolbar.open": "folder-open",
    "toolbar.save": "save",
    "toolbar.undo": "undo-2",
    "toolbar.redo": "redo-2",
    "toolbar.copy": "copy",
    "toolbar.paste": "clipboard-paste",
    "toolbar.delete": "trash-2",
    "toolbar.preview": "view",
    "toolbar.compile": "play",
    "toolbar.stop": "square",
    "toolbar.export": "upload",
    "toolbar.settings.project": "wrench",
    "toolbar.settings.global": "settings-2",

    # Navigation / dock semantics
    "nav.project": "folder-tree",
    "nav.structure": "workflow",
    "nav.page": "file-text",
    "nav.page_group": "folder-root",
    "nav.template": "layout-template",
    "nav.component_library": "component",
    "nav.resource": "image",
    "nav.expand": "chevron-right",
    "nav.collapse": "chevron-down",

    # Inspector / layout commands
    "layout.align.left": "align-left",
    "layout.align.center": "align-center-horizontal",
    "layout.align.right": "align-right",
    "layout.align.top": "align-start-vertical",
    "layout.align.middle": "align-center-vertical",
    "layout.align.bottom": "align-end-vertical",
    "layout.distribute.h": "align-horizontal-distribute-center",
    "layout.distribute.v": "align-vertical-distribute-center",
    "edit.visible": "eye",
    "edit.hidden": "eye-off",
    "edit.lock": "lock",
    "edit.unlock": "unlock",

    # Status / state
    "state.success": "circle-check-big",
    "state.warn": "triangle-alert",
    "state.error": "circle-alert",
    "state.info": "info",
    "state.progress": "loader-circle",

    # Canvas operations
    "canvas.select": "mouse-pointer-click",
    "canvas.drag": "move",
    "canvas.zoom_in": "zoom-in",
    "canvas.zoom_out": "zoom-out",
    "canvas.rotate": "rotate-cw",
    "canvas.layer.up": "arrow-up",
    "canvas.layer.down": "arrow-down",
    "canvas.layer.top": "arrow-up-to-line",
    "canvas.layer.bottom": "arrow-down-to-line",
    "canvas.grid": "grid-3x3",
    "canvas.snap": "crosshair",
    "canvas.ruler": "ruler",
    "canvas.guides": "layout-panel-left",

    # Widget semantic groups
    "button": "square-minus",
    "calendar": "calendar",
    "card": "square-stack",
    "chart": "activity",
    "display": "monitor",
    "divider": "separator-horizontal",
    "grid": "grid-3x3",
    "image": "image",
    "input": "text-cursor-input",
    "layout": "layout-panel-top",
    "list": "list",
    "media": "play",
    "navigation": "waypoints",
    "page": "file-text",
    "progress": "loader-circle",
    "security": "shield",
    "status": "badge-info",
    "table": "table",
    "tag": "tag",
    "text": "type",
    "time": "clock",
    "toggle": "toggle-left",
    "window": "app-window",
}

_MATERIAL_FONT_FAMILY = "Material Symbols Rounded"
_MATERIAL_FONT_FALLBACKS = (
    "Material Symbols Rounded",
    "Material Symbols Outlined",
    "Material Symbols Sharp",
)
_MATERIAL_FONT_LOADED = False
_MATERIAL_ACTIVE_FONT_FAMILY = _MATERIAL_FONT_FAMILY


def _icon_scale_tokens() -> dict:
    from .theme import theme_tokens

    tokens = theme_tokens("dark")
    return {
        "xs": max(int(tokens.get("icon_xs", 12)), 1),
        "sm": max(int(tokens.get("icon_sm", 14)), 1),
        "md": max(int(tokens.get("icon_md", 16)), 1),
        "lg": max(int(tokens.get("icon_lg", 18)), 1),
    }


def _default_semantic_icon_size() -> int:
    return _icon_scale_tokens()["md"]


def _default_widget_icon_size() -> int:
    return _icon_scale_tokens()["sm"]


def _theme_mode() -> str:
    app = QApplication.instance()
    mode = app.property("designer_theme_mode") if app is not None else None
    return mode if mode in ("dark", "light") else "dark"


def _palette_for_mode(mode: str) -> dict:
    from .theme import theme_tokens

    tokens = theme_tokens("light" if mode == "light" else "dark")
    accent = QColor(tokens["accent"])
    accent_soft = QColor(accent)
    accent_soft.setAlphaF(0.15)
    return {
        "ink": QColor(tokens["text"]),
        "muted": QColor(tokens["text_soft"]),
        "accent": accent,
        "accent_soft": accent_soft,
        "danger": QColor(tokens["danger"]),
        "success": QColor(tokens["success"]),
        "surface": QColor(tokens["panel"]),
        "surface_alt": QColor(tokens["panel_alt"]),
        "stroke": QColor(tokens["border"]),
        "warn": QColor(tokens["warning"]),
        "info": QColor(tokens["accent"]),
    }


def _ensure_material_font_loaded() -> bool:
    global _MATERIAL_FONT_LOADED, _MATERIAL_ACTIVE_FONT_FAMILY
    if _MATERIAL_FONT_LOADED:
        return True
    families = set(QFontDatabase().families())
    for family in _MATERIAL_FONT_FALLBACKS:
        if family in families:
            _MATERIAL_ACTIVE_FONT_FAMILY = family
            _MATERIAL_FONT_LOADED = True
            return True
    return False


def semantic_icon_keys() -> tuple[str, ...]:
    """Return sorted semantic icon keys for consistency checks (UIX-003)."""
    return tuple(sorted(ICON_SEMANTIC_MAP.keys()))


def _resolve_icon_spec(icon_key: str) -> dict | None:
    key = str(icon_key or "").strip()
    if not key:
        return None
    canonical = _ICON_ALIASES.get(key, key)
    return _ICON_DEFINITIONS.get(canonical)


def _material_glyph_for_icon(icon_key: str) -> str | None:
    spec = _resolve_icon_spec(icon_key)
    if spec is None:
        return None
    return str(spec.get("glyph") or "").strip() or None


def _fallback_paint_key(icon_key: str) -> str:
    """Map semantic icon keys back to legacy painter keys for no-font fallback."""
    key = str(icon_key or "").strip()
    canonical = _ICON_ALIASES.get(key, key)
    semantic_to_legacy = {
        "toolbar.new": "button",
        "toolbar.open": "project",
        "toolbar.save": "save",
        "toolbar.undo": "undo",
        "toolbar.redo": "redo",
        "toolbar.copy": "page",
        "toolbar.paste": "page",
        "toolbar.delete": "stop",
        "toolbar.preview": "animation",
        "toolbar.compile": "compile",
        "toolbar.stop": "stop",
        "toolbar.export": "save",
        "toolbar.settings.project": "properties",
        "toolbar.settings.global": "properties",
        "nav.page": "page",
        "nav.page_group": "project",
        "nav.template": "layout",
        "nav.component_library": "widgets",
        "nav.resource": "assets",
        "layout.align.left": "layout",
        "layout.align.center": "layout",
        "layout.align.right": "layout",
        "layout.align.top": "layout",
        "layout.align.middle": "layout",
        "layout.align.bottom": "layout",
        "layout.distribute.h": "grid",
        "layout.distribute.v": "grid",
        "edit.visible": "status",
        "edit.hidden": "status",
        "edit.lock": "security",
        "edit.unlock": "security",
        "state.success": "status",
        "state.warn": "diagnostics",
        "state.error": "diagnostics",
        "state.info": "info",
        "state.progress": "time",
        "canvas.select": "navigation",
        "canvas.drag": "navigation",
        "canvas.zoom_in": "navigation",
        "canvas.zoom_out": "navigation",
        "canvas.rotate": "navigation",
        "canvas.layer.up": "layout",
        "canvas.layer.down": "layout",
        "canvas.layer.top": "layout",
        "canvas.layer.bottom": "layout",
        "canvas.grid": "grid",
        "canvas.snap": "grid",
        "canvas.ruler": "divider",
        "canvas.guides": "grid",
    }
    return semantic_to_legacy.get(canonical, key or "widget")


def _icon_token_for_key(icon_key: str) -> str:
    spec = _resolve_icon_spec(icon_key)
    if spec is None:
        return "default"
    token = str(spec.get("token") or "default").strip()
    return token if token in {"default", "muted", "active", "disabled", "success", "warn", "error", "info"} else "default"


def _icon_color_for_token(palette: dict, token: str) -> QColor:
    token_to_palette = {
        "default": "ink",
        "muted": "muted",
        "active": "accent",
        "disabled": "stroke",
        "success": "success",
        "warn": "warn",
        "error": "danger",
        "info": "info",
    }
    return palette.get(token_to_palette.get(token, "ink"), palette["ink"])


def widget_icon_key(type_name: str) -> str:
    return _WIDGET_ICON_KEYS.get(str(type_name or "").strip(), "widget")


def _legacy_icon_mode_enabled() -> bool:
    return os.environ.get("EMBEDDEDGUI_LEGACY_ICONS", "0") == "1"


def _normalize_icon_color(color) -> str:
    qcolor = color if isinstance(color, QColor) else QColor(str(color or "").strip())
    if isinstance(qcolor, QColor) and qcolor.isValid():
        return qcolor.name(QColor.HexArgb) if qcolor.alpha() != 255 else qcolor.name().upper()
    return str(color or "").strip()


def _widget_semantic_key(icon_key: str) -> str | None:
    key = str(icon_key or "").strip()
    if not key:
        return None
    if key in _WIDGET_ICON_KEYS.values():
        return key
    return _WIDGET_ICON_KEYS.get(key)


def _lucide_name_for_key(icon_key: str) -> str | None:
    key = str(icon_key or "").strip()
    if not key:
        return None
    widget_semantic = _widget_semantic_key(key)
    if widget_semantic:
        lucide_name = _LUCIDE_KEY_MAP.get(widget_semantic)
        if lucide_name:
            return lucide_name
    canonical = _ICON_ALIASES.get(key, key)
    return _LUCIDE_KEY_MAP.get(canonical) or _LUCIDE_KEY_MAP.get(key)


def _icon_color_value(icon_key: str, mode: str | None = None, color=None) -> str:
    if color is not None:
        return _normalize_icon_color(color)
    palette = _palette_for_mode(mode or _theme_mode())
    token = _icon_token_for_key(icon_key)
    return _normalize_icon_color(_icon_color_for_token(palette, token))


@lru_cache(maxsize=512)
def _load_lucide_icon_cached(name: str, color: str, size: int) -> QIcon:
    if QSvgRenderer is None:
        return QIcon()
    svg_path = _LUCIDE_DIR / f"{name}.svg"
    if not svg_path.is_file():
        return QIcon()

    svg = svg_path.read_text(encoding="utf-8")
    svg = svg.replace('stroke="currentColor"', f'stroke="{color}"')
    svg = svg.replace('fill="currentColor"', f'fill="{color}"')
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    if not renderer.isValid():
        return QIcon()

    pixmap = QPixmap(int(size), int(size))
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.TextAntialiasing)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


def load_lucide_icon(name: str, color=None, size: int = 16) -> QIcon:
    """Load a Lucide SVG icon tinted to the requested color."""
    if color is None:
        from .theme import app_theme_tokens

        color = app_theme_tokens()["text_soft"]
    return _load_lucide_icon_cached(str(name), _normalize_icon_color(color), int(size))


def _fluent_icon_for_key(icon_key: str) -> QIcon | None:
    if FIF is None:
        return None
    spec = _resolve_icon_spec(icon_key)
    key = str(icon_key or "").strip()
    canonical = _ICON_ALIASES.get(key, key)
    if spec is None:
        return None

    fluent_name = _FLUENT_ICON_MAP.get(canonical)
    if not fluent_name:
        # Full modern replacement policy: semantic keys always use Fluent fallback.
        fluent_name = "APPLICATION"

    fluent_icon = getattr(FIF, fluent_name, None)
    if fluent_icon is None:
        fluent_icon = getattr(FIF, "APPLICATION", None)
    if fluent_icon is None:
        return None
    try:
        return fluent_icon.icon()
    except Exception:
        return None


def _legacy_make_icon(icon_key: str, size: int | None = None, mode: str | None = None) -> QIcon:
    size = _default_semantic_icon_size() if size is None else max(int(size), 1)
    spec = _resolve_icon_spec(icon_key)
    if spec is not None:
        # Full modern replacement: semantic keys do NOT fall back to legacy painter path.
        fluent_icon = _fluent_icon_for_key(icon_key)
        if fluent_icon is not None:
            return fluent_icon
        # If Fluent is unavailable at runtime, use Material as a modern second choice.
        pixmap = _legacy_make_pixmap(icon_key, size=size, mode=mode)
        return QIcon(pixmap)

    # Non-semantic or custom keys keep compatibility behavior.
    pixmap = _legacy_make_pixmap(icon_key, size=size, mode=mode)
    return QIcon(pixmap)


def _legacy_make_pixmap(icon_key: str, size: int | None = None, mode: str | None = None) -> QPixmap:
    size = _default_semantic_icon_size() if size is None else max(int(size), 1)
    mode = mode or _theme_mode()
    palette = _palette_for_mode(mode)
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    glyph_name = _material_glyph_for_icon(icon_key)
    token = _icon_token_for_key(icon_key)
    icon_color = _icon_color_for_token(palette, token)
    if glyph_name and _ensure_material_font_loaded():
        font = QFont(_MATERIAL_ACTIVE_FONT_FAMILY)
        font.setPixelSize(max(12, size - 2))
        font.setStyleStrategy(QFont.PreferAntialias)
        painter.setFont(font)
        painter.setPen(QPen(icon_color))
        painter.drawText(QRectF(0, 0, size, size), Qt.AlignCenter, glyph_name)
    else:
        # Legacy painter fallback is intentionally removed for semantic keys.
        # Keep only a neutral modern placeholder for unresolved rendering cases.
        rect = QRectF(2, 2, size - 4, size - 4)
        pen = QPen(icon_color, 1.8)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect, 5, 5)

    painter.end()
    return pixmap


def icon_for_semantic(icon_key: str, *, color=None, size: int | None = None, mode: str | None = None) -> QIcon:
    size = _default_semantic_icon_size() if size is None else max(int(size), 1)
    lucide_name = None if _legacy_icon_mode_enabled() else _lucide_name_for_key(icon_key)
    if lucide_name:
        icon = load_lucide_icon(lucide_name, color=_icon_color_value(icon_key, mode=mode, color=color), size=size)
        if not icon.isNull():
            return icon
    return _legacy_make_icon(icon_key, size=size, mode=mode)


def icon_for_widget(widget_key: str, *, color=None, size: int | None = None, mode: str | None = None) -> QIcon:
    size = _default_widget_icon_size() if size is None else max(int(size), 1)
    key = str(widget_key or "").strip()
    semantic = _WIDGET_ICON_KEYS.get(key, key)
    return icon_for_semantic(semantic, color=color, size=size, mode=mode)


def make_icon(icon_key: str, size: int | None = None, mode: str | None = None) -> QIcon:
    return icon_for_semantic(icon_key, size=size, mode=mode)


def make_pixmap(icon_key: str, size: int | None = None, mode: str | None = None) -> QPixmap:
    size = _default_semantic_icon_size() if size is None else max(int(size), 1)
    icon = icon_for_semantic(icon_key, size=size, mode=mode)
    if not icon.isNull():
        pixmap = icon.pixmap(size, size)
        if not pixmap.isNull():
            return pixmap
    return _legacy_make_pixmap(icon_key, size=size, mode=mode)


def make_widget_preview(preview_kind: str, size=(180, 120), mode: str | None = None) -> QPixmap:
    mode = mode or _theme_mode()
    palette = _palette_for_mode(mode)
    width, height = size
    pixmap = QPixmap(width, height)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    rect = QRectF(0.5, 0.5, width - 1.0, height - 1.0)
    painter.setPen(QPen(palette["stroke"], 1))
    painter.setBrush(palette["surface"])
    painter.drawRoundedRect(rect, 12, 12)

    inner = rect.adjusted(12, 12, -12, -12)
    kind = (preview_kind or "widget").strip()
    if kind == "layout":
        painter.setPen(Qt.NoPen)
        painter.setBrush(palette["accent_soft"])
        painter.drawRoundedRect(QRectF(inner.left(), inner.top(), inner.width(), 26), 8, 8)
        painter.drawRoundedRect(QRectF(inner.left(), inner.top() + 34, inner.width() * 0.58, inner.height() - 34), 8, 8)
        painter.drawRoundedRect(QRectF(inner.left() + inner.width() * 0.64, inner.top() + 34, inner.width() * 0.36, inner.height() - 34), 8, 8)
    elif kind == "chart":
        pen = QPen(palette["accent"], 3)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        path = QPainterPath(QPointF(inner.left(), inner.bottom() - 8))
        path.lineTo(inner.left() + inner.width() * 0.24, inner.top() + inner.height() * 0.52)
        path.lineTo(inner.left() + inner.width() * 0.48, inner.top() + inner.height() * 0.72)
        path.lineTo(inner.left() + inner.width() * 0.68, inner.top() + inner.height() * 0.28)
        path.lineTo(inner.right(), inner.top() + inner.height() * 0.44)
        painter.drawPath(path)
    elif kind == "navigation":
        painter.setPen(QPen(palette["stroke"], 1.4))
        painter.setBrush(palette["surface_alt"])
        painter.drawRoundedRect(QRectF(inner.left(), inner.top(), inner.width(), 28), 8, 8)
        for index in range(3):
            x = inner.left() + 14 + index * 42
            painter.drawRoundedRect(QRectF(x, inner.top() + 8, 28, 12), 6, 6)
        painter.setPen(Qt.NoPen)
        painter.setBrush(palette["accent_soft"])
        painter.drawRoundedRect(QRectF(inner.left(), inner.top() + 40, inner.width(), inner.height() - 40), 10, 10)
    elif kind == "input":
        painter.setPen(QPen(palette["stroke"], 1.5))
        painter.setBrush(palette["surface_alt"])
        painter.drawRoundedRect(QRectF(inner.left(), inner.center().y() - 14, inner.width(), 28), 9, 9)
        pen = QPen(palette["accent"], 4)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawLine(QPointF(inner.left() + 18, inner.center().y()), QPointF(inner.left() + inner.width() * 0.58, inner.center().y()))
        painter.setBrush(palette["accent"])
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(inner.left() + inner.width() * 0.72, inner.center().y()), 8, 8)
    elif kind == "media":
        painter.setPen(Qt.NoPen)
        painter.setBrush(palette["surface_alt"])
        painter.drawRoundedRect(QRectF(inner.left(), inner.top(), inner.width(), inner.height()), 10, 10)
        triangle = QPainterPath()
        triangle.moveTo(inner.left() + inner.width() * 0.42, inner.top() + inner.height() * 0.28)
        triangle.lineTo(inner.left() + inner.width() * 0.42, inner.top() + inner.height() * 0.72)
        triangle.lineTo(inner.left() + inner.width() * 0.72, inner.center().y())
        triangle.closeSubpath()
        painter.setBrush(palette["accent"])
        painter.drawPath(triangle)
    else:
        painter.setPen(QPen(palette["stroke"], 1.4))
        painter.setBrush(palette["surface_alt"])
        painter.drawRoundedRect(QRectF(inner.left(), inner.top() + 12, inner.width(), inner.height() - 24), 10, 10)
        pen = QPen(palette["muted"], 2)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawLine(QPointF(inner.left() + 16, inner.top() + 34), QPointF(inner.right() - 16, inner.top() + 34))
        painter.drawLine(QPointF(inner.left() + 16, inner.top() + 54), QPointF(inner.right() - 36, inner.top() + 54))
        painter.drawLine(QPointF(inner.left() + 16, inner.top() + 74), QPointF(inner.right() - 22, inner.top() + 74))

    painter.end()
    return pixmap


def _paint_icon(painter: QPainter, icon_key: str, rect: QRectF, palette: dict) -> None:
    pen = QPen(palette["ink"], 1.8)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    key = (icon_key or "widget").strip()
    if key == "project":
        painter.setBrush(palette["surface_alt"])
        painter.drawRoundedRect(rect.adjusted(2, 5, -2, -1), 4, 4)
        painter.drawRoundedRect(QRectF(rect.left() + 3, rect.top() + 3, rect.width() * 0.44, 6), 3, 3)
    elif key == "structure":
        x = rect.left() + rect.width() * 0.28
        right = rect.left() + rect.width() * 0.72
        mid = rect.center().x()
        top = rect.top() + 4
        bottom = rect.bottom() - 4
        painter.drawLine(QPointF(mid, top + 2), QPointF(mid, bottom - 2))
        painter.drawLine(QPointF(mid, rect.center().y()), QPointF(right, rect.center().y()))
        painter.drawLine(QPointF(mid, rect.top() + rect.height() * 0.28), QPointF(x, rect.top() + rect.height() * 0.28))
        painter.drawEllipse(QRectF(mid - 3, top, 6, 6))
        painter.drawEllipse(QRectF(x - 3, rect.top() + rect.height() * 0.28 - 3, 6, 6))
        painter.drawEllipse(QRectF(right - 3, rect.center().y() - 3, 6, 6))
        painter.drawEllipse(QRectF(mid - 3, bottom - 6, 6, 6))
    elif key == "widgets":
        painter.setBrush(palette["accent_soft"])
        size = rect.width() / 2.7
        gap = rect.width() / 8
        start_x = rect.left() + 3
        start_y = rect.top() + 3
        for row in range(2):
            for col in range(2):
                painter.drawRoundedRect(
                    QRectF(start_x + col * (size + gap), start_y + row * (size + gap), size, size), 2.5, 2.5
                )
    elif key == "assets":
        painter.drawRoundedRect(rect.adjusted(2.5, 3, -2.5, -2.5), 4, 4)
        painter.drawEllipse(QRectF(rect.left() + 5, rect.top() + 6, 4.5, 4.5))
        painter.drawLine(QPointF(rect.left() + 5, rect.bottom() - 5), QPointF(rect.center().x(), rect.top() + 10))
        painter.drawLine(QPointF(rect.center().x(), rect.top() + 10), QPointF(rect.right() - 5, rect.bottom() - 6))
    elif key == "properties":
        for y in (rect.top() + 5, rect.center().y(), rect.bottom() - 5):
            painter.drawLine(QPointF(rect.left() + 4, y), QPointF(rect.right() - 4, y))
        painter.setBrush(palette["accent"])
        painter.drawEllipse(QRectF(rect.left() + 7, rect.top() + 2, 6, 6))
        painter.drawEllipse(QRectF(rect.center().x() - 3, rect.center().y() - 3, 6, 6))
        painter.drawEllipse(QRectF(rect.right() - 13, rect.bottom() - 8, 6, 6))
    elif key == "animation":
        path = QPainterPath(QPointF(rect.left() + 3, rect.bottom() - 4))
        path.cubicTo(
            QPointF(rect.left() + 6, rect.top() + 8),
            QPointF(rect.center().x(), rect.top() + 4),
            QPointF(rect.right() - 4, rect.center().y()),
        )
        painter.drawPath(path)
        painter.setBrush(palette["accent"])
        painter.drawEllipse(QRectF(rect.right() - 7, rect.center().y() - 3, 6, 6))
    elif key == "page":
        painter.setBrush(palette["surface_alt"])
        painter.drawRoundedRect(rect.adjusted(4, 2, -4, -2), 3, 3)
        painter.drawLine(QPointF(rect.left() + 7, rect.top() + 8), QPointF(rect.right() - 7, rect.top() + 8))
        painter.drawLine(QPointF(rect.left() + 7, rect.top() + 12), QPointF(rect.right() - 11, rect.top() + 12))
    elif key == "diagnostics":
        painter.setBrush(palette["accent_soft"])
        path = QPainterPath()
        path.moveTo(rect.center().x(), rect.top() + 3)
        path.lineTo(rect.right() - 3, rect.bottom() - 3)
        path.lineTo(rect.left() + 3, rect.bottom() - 3)
        path.closeSubpath()
        painter.drawPath(path)
        painter.setPen(QPen(palette["accent"], 2.1, cap=Qt.RoundCap))
        painter.drawLine(QPointF(rect.center().x(), rect.top() + 7), QPointF(rect.center().x(), rect.center().y() + 1))
        painter.drawPoint(QPointF(rect.center().x(), rect.bottom() - 7))
    elif key == "history":
        painter.drawEllipse(rect.adjusted(3, 3, -3, -3))
        painter.drawLine(QPointF(rect.center().x(), rect.center().y()), QPointF(rect.center().x(), rect.top() + 6))
        painter.drawLine(QPointF(rect.center().x(), rect.center().y()), QPointF(rect.right() - 5, rect.center().y()))
    elif key == "debug":
        painter.drawRoundedRect(rect.adjusted(2.5, 4, -2.5, -3), 4, 4)
        painter.drawLine(QPointF(rect.left() + 5, rect.bottom() - 6), QPointF(rect.right() - 5, rect.bottom() - 6))
        painter.drawLine(QPointF(rect.left() + 7, rect.top() + 8), QPointF(rect.center().x() - 1, rect.center().y()))
        painter.drawLine(QPointF(rect.center().x() - 1, rect.center().y()), QPointF(rect.left() + 7, rect.bottom() - 10))
        painter.drawLine(QPointF(rect.right() - 7, rect.top() + 8), QPointF(rect.center().x() + 1, rect.center().y()))
    elif key == "save":
        painter.setBrush(palette["surface_alt"])
        painter.drawRoundedRect(rect.adjusted(3, 2, -3, -2), 3, 3)
        painter.drawRect(QRectF(rect.left() + 6, rect.top() + 4, rect.width() - 12, 5))
        painter.drawRect(QRectF(rect.left() + 6, rect.center().y() - 1, rect.width() - 12, rect.height() / 3))
    elif key == "compile":
        painter.setBrush(palette["accent_soft"])
        path = QPainterPath()
        path.moveTo(rect.left() + 6, rect.top() + 4)
        path.lineTo(rect.right() - 5, rect.center().y())
        path.lineTo(rect.left() + 6, rect.bottom() - 4)
        path.closeSubpath()
        painter.drawPath(path)
    elif key == "stop":
        painter.setBrush(palette["danger"])
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(rect.adjusted(5, 5, -5, -5), 3, 3)
    elif key == "undo":
        painter.drawArc(rect.adjusted(4, 4, -5, -4), 40 * 16, 240 * 16)
        painter.drawLine(QPointF(rect.left() + 4, rect.top() + 9), QPointF(rect.left() + 8, rect.top() + 5))
        painter.drawLine(QPointF(rect.left() + 4, rect.top() + 9), QPointF(rect.left() + 10, rect.top() + 10))
    elif key == "redo":
        painter.drawArc(rect.adjusted(5, 4, -4, -4), -100 * 16, -240 * 16)
        painter.drawLine(QPointF(rect.right() - 4, rect.top() + 9), QPointF(rect.right() - 8, rect.top() + 5))
        painter.drawLine(QPointF(rect.right() - 4, rect.top() + 9), QPointF(rect.right() - 10, rect.top() + 10))
    elif key == "button":
        painter.setBrush(palette["surface_alt"])
        painter.drawRoundedRect(rect.adjusted(3, 5, -3, -5), 6, 6)
        painter.drawLine(QPointF(rect.left() + 7, rect.center().y()), QPointF(rect.right() - 7, rect.center().y()))
    elif key == "layout":
        painter.setBrush(palette["surface_alt"])
        painter.drawRoundedRect(rect.adjusted(2, 3, -2, -3), 3, 3)
        painter.drawLine(QPointF(rect.center().x(), rect.top() + 4), QPointF(rect.center().x(), rect.bottom() - 4))
        painter.drawLine(QPointF(rect.left() + 4, rect.center().y()), QPointF(rect.right() - 4, rect.center().y()))
    elif key == "input":
        painter.drawRoundedRect(rect.adjusted(3, 6, -3, -6), 5, 5)
        painter.drawLine(QPointF(rect.left() + 7, rect.center().y()), QPointF(rect.right() - 9, rect.center().y()))
    elif key == "toggle":
        painter.drawRoundedRect(QRectF(rect.left() + 3, rect.center().y() - 4, rect.width() - 6, 8), 4, 4)
        painter.setBrush(palette["accent"])
        painter.drawEllipse(QRectF(rect.left() + 4, rect.center().y() - 5, 10, 10))
    elif key == "navigation":
        painter.drawLine(QPointF(rect.center().x(), rect.top() + 3), QPointF(rect.center().x(), rect.bottom() - 3))
        painter.drawLine(QPointF(rect.left() + 4, rect.center().y()), QPointF(rect.right() - 4, rect.center().y()))
        painter.drawLine(QPointF(rect.center().x(), rect.top() + 3), QPointF(rect.right() - 5, rect.center().y()))
    elif key == "chart":
        painter.drawLine(QPointF(rect.left() + 4, rect.bottom() - 4), QPointF(rect.left() + 8, rect.top() + 9))
        painter.drawLine(QPointF(rect.left() + 8, rect.top() + 9), QPointF(rect.center().x(), rect.bottom() - 8))
        painter.drawLine(QPointF(rect.center().x(), rect.bottom() - 8), QPointF(rect.right() - 5, rect.top() + 5))
    elif key == "media":
        path = QPainterPath()
        path.moveTo(rect.left() + 6, rect.top() + 4)
        path.lineTo(rect.right() - 5, rect.center().y())
        path.lineTo(rect.left() + 6, rect.bottom() - 4)
        path.closeSubpath()
        painter.setBrush(palette["accent_soft"])
        painter.drawPath(path)
    elif key == "image":
        painter.drawRoundedRect(rect.adjusted(3, 4, -3, -4), 3, 3)
        painter.drawEllipse(QRectF(rect.left() + 6, rect.top() + 6, 4, 4))
        painter.drawLine(QPointF(rect.left() + 6, rect.bottom() - 7), QPointF(rect.center().x(), rect.top() + 11))
        painter.drawLine(QPointF(rect.center().x(), rect.top() + 11), QPointF(rect.right() - 5, rect.bottom() - 7))
    elif key == "text":
        painter.drawLine(QPointF(rect.left() + 5, rect.top() + 6), QPointF(rect.right() - 5, rect.top() + 6))
        painter.drawLine(QPointF(rect.left() + 8, rect.center().y()), QPointF(rect.right() - 8, rect.center().y()))
        painter.drawLine(QPointF(rect.left() + 6, rect.bottom() - 6), QPointF(rect.right() - 10, rect.bottom() - 6))
    elif key == "list":
        for row in range(3):
            y = rect.top() + 5 + row * 5
            painter.drawEllipse(QRectF(rect.left() + 4, y - 1.5, 3, 3))
            painter.drawLine(QPointF(rect.left() + 10, y), QPointF(rect.right() - 4, y))
    elif key == "grid":
        painter.setBrush(palette["surface_alt"])
        size = rect.width() / 3.5
        gap = 2.5
        for row in range(2):
            for col in range(2):
                painter.drawRoundedRect(
                    QRectF(rect.left() + 3 + col * (size + gap), rect.top() + 3 + row * (size + gap), size, size), 1.8, 1.8
                )
    elif key == "status":
        painter.setBrush(palette["accent_soft"])
        painter.drawRoundedRect(rect.adjusted(3, 5, -3, -5), 5, 5)
        painter.setBrush(palette["success"])
        painter.drawEllipse(QRectF(rect.center().x() - 4, rect.center().y() - 4, 8, 8))
    elif key == "progress":
        painter.drawRoundedRect(QRectF(rect.left() + 3, rect.center().y() - 3, rect.width() - 6, 6), 3, 3)
        painter.setBrush(palette["accent"])
        painter.drawRoundedRect(QRectF(rect.left() + 3, rect.center().y() - 3, rect.width() * 0.58, 6), 3, 3)
    elif key == "divider":
        painter.drawLine(QPointF(rect.left() + 4, rect.center().y()), QPointF(rect.right() - 4, rect.center().y()))
    elif key == "calendar":
        painter.drawRoundedRect(rect.adjusted(3, 3, -3, -3), 3, 3)
        painter.drawLine(QPointF(rect.left() + 5, rect.top() + 8), QPointF(rect.right() - 5, rect.top() + 8))
        for row in range(2):
            for col in range(3):
                painter.drawPoint(QPointF(rect.left() + 7 + col * 4.2, rect.top() + 12 + row * 4.2))
    elif key == "security":
        painter.drawEllipse(QRectF(rect.left() + 5, rect.top() + 5, rect.width() - 10, rect.height() - 10))
        painter.drawLine(QPointF(rect.left() + 6, rect.top() + 6), QPointF(rect.right() - 6, rect.bottom() - 6))
    elif key == "window":
        painter.drawRoundedRect(rect.adjusted(2.5, 3, -2.5, -3), 3, 3)
        painter.drawLine(QPointF(rect.left() + 3, rect.top() + 7), QPointF(rect.right() - 3, rect.top() + 7))
        for index in range(3):
            painter.drawPoint(QPointF(rect.left() + 6 + index * 3, rect.top() + 5))
    elif key == "time":
        painter.drawEllipse(rect.adjusted(3, 3, -3, -3))
        painter.drawLine(QPointF(rect.center().x(), rect.center().y()), QPointF(rect.center().x(), rect.top() + 6))
        painter.drawLine(QPointF(rect.center().x(), rect.center().y()), QPointF(rect.right() - 6, rect.center().y() + 2))
    elif key == "table":
        painter.drawRoundedRect(rect.adjusted(3, 4, -3, -4), 2, 2)
        painter.drawLine(QPointF(rect.left() + 3, rect.top() + 9), QPointF(rect.right() - 3, rect.top() + 9))
        painter.drawLine(QPointF(rect.center().x(), rect.top() + 4), QPointF(rect.center().x(), rect.bottom() - 4))
        painter.drawLine(QPointF(rect.left() + 3, rect.center().y()), QPointF(rect.right() - 3, rect.center().y()))
    elif key == "tag":
        path = QPainterPath()
        path.moveTo(rect.left() + 5, rect.top() + 6)
        path.lineTo(rect.center().x(), rect.top() + 6)
        path.lineTo(rect.right() - 4, rect.center().y())
        path.lineTo(rect.center().x(), rect.bottom() - 6)
        path.lineTo(rect.left() + 5, rect.bottom() - 6)
        path.closeSubpath()
        painter.setBrush(palette["surface_alt"])
        painter.drawPath(path)
        painter.drawEllipse(QRectF(rect.left() + 8, rect.center().y() - 1.5, 3, 3))
    elif key == "card":
        painter.setBrush(palette["surface_alt"])
        painter.drawRoundedRect(rect.adjusted(2.5, 3, -2.5, -3), 5, 5)
        painter.drawLine(QPointF(rect.left() + 6, rect.top() + 9), QPointF(rect.right() - 6, rect.top() + 9))
        painter.drawLine(QPointF(rect.left() + 6, rect.center().y()), QPointF(rect.right() - 10, rect.center().y()))
    else:
        painter.drawRoundedRect(rect.adjusted(3, 3, -3, -3), 5, 5)
        from .theme import designer_ui_font
        painter.setFont(designer_ui_font(pixel_size=max(int(rect.height() * 0.44), 8), weight=QFont.DemiBold))
        painter.drawText(rect, Qt.AlignCenter, "W")
