"""Token-driven application theme for EmbeddedGUI Designer.

Aligned with ``UI_UIX_REDESIGN_MASTER_PLAN.md`` (UIX-001):
- Color roles: canvas bg, panel bg, text primary/muted/soft, accent, status.
- Typography scale: Display / Heading / Section / Body / Meta / Caption (px sizes).
- Spacing: 4pt baseline; 8/12/16/20/24 via space_* keys.
- Radii: r_sm=inputs(6), r_md/cards/buttons(8), r_xl≈elevated(12).
- Icons: icon_xs/sm/md/lg = 12/14/16/18 for tighter IDE/Figma density.
"""

from __future__ import annotations

import os
import sys

from PyQt5.QtCore import QEvent, QObject, QSize
from PyQt5.QtGui import QColor, QFont, QFontDatabase
from PyQt5.QtWidgets import QApplication, QWidget
try:
    from PyQt5 import sip as pyqt_sip
except ImportError:
    pyqt_sip = None

try:
    from qfluentwidgets import (
        Theme,
        setTheme,
        ComboBox as FluentComboBox,
        LineEdit as FluentLineEdit,
        PushButton as FluentPushButton,
        SpinBox as FluentSpinBox,
        ToolButton as FluentToolButton,
    )
    from qfluentwidgets.common.style_sheet import setCustomStyleSheet as set_fluent_custom_stylesheet

    HAS_FLUENT = True
except ImportError:
    HAS_FLUENT = False
    Theme = None
    setTheme = None
    FluentComboBox = None
    FluentLineEdit = None
    FluentPushButton = None
    FluentSpinBox = None
    FluentToolButton = None
    set_fluent_custom_stylesheet = None


_ENGINEERING_RADIUS_SM = 4
_ENGINEERING_RADIUS_MD = 6
_FLUENT_STYLE_MARKER = "_designer_fluent_engineering_style"
_PROPERTY_PANEL_SPIN_BUTTON_WIDTH = 20
_PROPERTY_PANEL_SPIN_BUTTON_HEIGHT = 20
_PROPERTY_PANEL_SPIN_ICON_SIZE = 7
_PROPERTY_PANEL_SPIN_LAYOUT_SPACING = 2
_PROPERTY_PANEL_SPIN_LAYOUT_RIGHT_MARGIN = 2
_PROPERTY_PANEL_SPIN_LAYOUT_VERTICAL_MARGIN = 3
_PROPERTY_PANEL_SPIN_BUTTON_QSS = (
    f"min-width: {_PROPERTY_PANEL_SPIN_BUTTON_WIDTH}px;"
    f"max-width: {_PROPERTY_PANEL_SPIN_BUTTON_WIDTH}px;"
    f"min-height: {_PROPERTY_PANEL_SPIN_BUTTON_HEIGHT}px;"
    f"max-height: {_PROPERTY_PANEL_SPIN_BUTTON_HEIGHT}px;"
    "padding: 0px;"
    "margin: 0px;"
    "border-radius: 0px;"
)
_ENGINEERING_FS_BODY_SENTINEL = "__FS_BODY__"
_ENGINEERING_RADIUS_SM_SENTINEL = "__R_SM__"
_ENGINEERING_INPUT_PAD_H_SENTINEL = "__PAD_INPUT_H__"

_FLUENT_BUTTON_RADIUS_QSS = f"""
PushButton,
ToolButton,
ToggleButton,
ToggleToolButton,
PrimaryPushButton,
PrimaryToolButton,
DropDownToolButton,
PrimaryDropDownToolButton,
DropDownPushButton,
PrimaryDropDownPushButton,
TransparentPushButton,
TransparentToolButton,
TransparentToggleButton,
TransparentToggleToolButton {{
    border-radius: {_ENGINEERING_RADIUS_SM_SENTINEL}px;
    font-size: {_ENGINEERING_FS_BODY_SENTINEL}px;
}}
"""

_FLUENT_PROPERTY_PANEL_BUTTON_QSS = """
PushButton,
ToolButton,
ToggleButton,
ToggleToolButton,
PrimaryPushButton,
PrimaryToolButton,
DropDownToolButton,
PrimaryDropDownToolButton,
DropDownPushButton,
PrimaryDropDownPushButton,
TransparentPushButton,
TransparentToolButton,
TransparentToggleButton,
TransparentToggleToolButton {
    border-radius: __R_SM__px;
    min-height: 22px;
    padding: 1px __PAD_INPUT_H__px;
}
"""

_FLUENT_LINE_EDIT_RADIUS_QSS = f"""
LineEdit,
TextEdit,
PlainTextEdit,
TextBrowser {{
    border-radius: {_ENGINEERING_RADIUS_SM_SENTINEL}px;
    padding: 0px {_ENGINEERING_INPUT_PAD_H_SENTINEL}px;
    font-size: {_ENGINEERING_FS_BODY_SENTINEL}px;
}}

#lineEditButton {{
    border-radius: {_ENGINEERING_RADIUS_SM_SENTINEL}px;
}}
"""

_FLUENT_PROPERTY_PANEL_LINE_EDIT_QSS = """
LineEdit,
TextEdit,
PlainTextEdit,
TextBrowser {
    border-radius: __R_SM__px;
    min-height: 24px;
    padding: 0px __PAD_INPUT_H__px;
}

#lineEditButton {
    border-radius: __R_SM__px;
    min-width: 18px;
}
"""

_FLUENT_COMBO_BOX_RADIUS_QSS = f"""
ComboBox,
ModelComboBox {{
    border-radius: {_ENGINEERING_RADIUS_SM_SENTINEL}px;
    min-height: 24px;
    padding: 0px {_ENGINEERING_INPUT_PAD_H_SENTINEL}px;
    font-size: {_ENGINEERING_FS_BODY_SENTINEL}px;
}}
"""

_FLUENT_PROPERTY_PANEL_COMBO_BOX_QSS = """
ComboBox,
ModelComboBox {
    border-radius: __R_SM__px;
    min-height: 24px;
    padding: 0px __PAD_INPUT_H__px;
}
"""

_FLUENT_SPIN_BOX_RADIUS_QSS = f"""
SpinBox,
DoubleSpinBox,
DateEdit,
DateTimeEdit,
TimeEdit,
CompactSpinBox,
CompactDoubleSpinBox,
CompactDateEdit,
CompactDateTimeEdit,
CompactTimeEdit {{
    border-radius: {_ENGINEERING_RADIUS_SM_SENTINEL}px;
    min-height: 24px;
    padding: 0px {_ENGINEERING_INPUT_PAD_H_SENTINEL}px;
    font-size: {_ENGINEERING_FS_BODY_SENTINEL}px;
}}

SpinButton {{
    border-radius: {_ENGINEERING_RADIUS_SM_SENTINEL}px;
}}
"""

_FLUENT_PROPERTY_PANEL_SPIN_BOX_QSS = """
SpinBox,
DoubleSpinBox,
DateEdit,
DateTimeEdit,
TimeEdit,
CompactSpinBox,
CompactDoubleSpinBox,
CompactDateEdit,
CompactDateTimeEdit,
CompactTimeEdit {
    border-radius: __R_SM__px;
    min-height: 24px;
    padding: 0px __PAD_INPUT_H__px;
}

SpinButton {
    border-radius: __R_SM__px;
    min-width: 18px;
}
"""

if HAS_FLUENT:
    _FLUENT_BUTTON_TYPES = (FluentPushButton, FluentToolButton)
    _FLUENT_LINE_EDIT_TYPES = (FluentLineEdit,)
    _FLUENT_COMBO_BOX_TYPES = (FluentComboBox,)
    _FLUENT_SPIN_BOX_TYPES = (FluentSpinBox,)
else:
    _FLUENT_BUTTON_TYPES = ()
    _FLUENT_LINE_EDIT_TYPES = ()
    _FLUENT_COMBO_BOX_TYPES = ()
    _FLUENT_SPIN_BOX_TYPES = ()


_TOKENS = {
    "dark": {
        # IDE-style redesign 2026-04-21: Tailwind zinc scale + blue-500 accent.
        "bg": "#09090B",
        "shell_bg": "#09090B",
        "sidebar_bg": "#27272A",
        "panel": "#18181B",
        "panel_alt": "#27272A",
        "panel_soft": "#3F3F46",
        "panel_raised": "#27272A",
        "surface": "#3F3F46",
        "surface_hover": "#52525B",
        "surface_pressed": "#71717A",
        "canvas_bg": "#09090B",
        "canvas_stage": "#09090B",
        "border": "#3F3F46",
        "border_strong": "#52525B",
        "focus_ring": "#3B82F6",
        "text": "#D4D4D8",
        "text_muted": "#A1A1AA",
        "text_soft": "#71717A",
        "accent": "#3B82F6",
        "accent_hover": "#60A5FA",
        "accent_soft": "rgba(59, 130, 246, 0.15)",
        "danger": "#EF4444",
        "success": "#22C55E",
        "warning": "#EAB308",
        "selection_text": "#BFDBFE",
        "syntax_meta": "#71717A",
        "syntax_comment": "#4ADE80",
        "syntax_tag": "#60A5FA",
        "syntax_attr": "#BFDBFE",
        "syntax_value": "#FDBA74",
        "syntax_bracket": "#A1A1AA",
        "selection": "rgba(59, 130, 246, 0.40)",
        "selection_hover": "rgba(59, 130, 246, 0.10)",
        "selection_soft": "rgba(59, 130, 246, 0.15)",
        "r_sm": 4,
        "r_md": 4,
        "r_lg": 4,
        "r_xl": 6,
        "r_2xl": 8,
        "r_3xl": 8,
        "space_3xs": 2,
        "space_xxs": 4,
        "space_xs": 4,
        "space_sm": 8,
        "space_md": 12,
        "space_lg": 16,
        "space_xl": 20,
        "space_2xl": 24,
        "pad_btn_v": 2,
        "pad_btn_h": 8,
        "pad_input_v": 2,
        "pad_input_h": 6,
        "pad_tab_compact_v": 1,
        "pad_tab_compact_h": 5,
        "pad_toolbar_h": 3,
        "space_toolbar_separator": 1,
        "h_tab_min": 24,
        "fs_display": 18,
        "fs_h1": 13,
        "fs_h2": 12,
        "fs_panel_title": 12,
        "fs_body": 12,
        "fs_body_sm": 11,
        "fs_caption": 10,
        "fs_micro": 10,
        "fw_regular": 400,
        "fw_medium": 500,
        "fw_semibold": 600,
        "fw_bold": 700,
        "icon_xs": 12,
        "icon_sm": 14,
        "icon_md": 16,
        "icon_lg": 18,
    },
    "light": {
        "bg": "#EEF2F6",
        "shell_bg": "#EEF2F6",
        "sidebar_bg": "#F6F8FA",
        "panel": "#FFFFFF",
        "panel_alt": "#F7F9FC",
        "panel_soft": "#EDF2F8",
        "panel_raised": "#FFFFFF",
        "surface": "#E7EDF5",
        "surface_hover": "#DCE8F6",
        "surface_pressed": "#D4E0EF",
        "canvas_bg": "#DDE5EE",
        "canvas_stage": "#F8FBFF",
        "border": "#CFD8E3",
        "border_strong": "#B4C0CE",
        "focus_ring": "#287DDA",
        "text": "#17212B",
        "text_muted": "#55606F",
        "text_soft": "#7B8696",
        "accent": "#287DDA",
        "accent_hover": "#3C8CE7",
        "accent_soft": "#DCEBFA",
        "danger": "#D9534F",
        "success": "#2E8B57",
        "warning": "#A5691A",
        "selection_text": "#1D4ED8",
        "syntax_meta": "#7B8696",
        "syntax_comment": "#2E8B57",
        "syntax_tag": "#287DDA",
        "syntax_attr": "#1D4ED8",
        "syntax_value": "#C2410C",
        "syntax_bracket": "#55606F",
        "selection": "#D8E7F9",
        "selection_hover": "rgba(59, 130, 246, 0.10)",
        "selection_soft": "#EDF4FD",
        "r_sm": 4,
        "r_md": 6,
        "r_lg": 8,
        "r_xl": 8,
        "r_2xl": 12,
        "r_3xl": 14,
        "space_3xs": 2,
        "space_xxs": 4,
        "space_xs": 4,
        "space_sm": 8,
        "space_md": 12,
        "space_lg": 16,
        "space_xl": 20,
        "space_2xl": 24,
        "pad_btn_v": 3,
        "pad_btn_h": 10,
        "pad_input_v": 3,
        "pad_input_h": 10,
        "pad_tab_compact_v": 1,
        "pad_tab_compact_h": 5,
        "pad_toolbar_h": 3,
        "space_toolbar_separator": 1,
        "h_tab_min": 24,
        "fs_display": 20,
        "fs_h1": 14,
        "fs_h2": 13,
        "fs_panel_title": 13,
        "fs_body": 13,
        "fs_body_sm": 12,
        "fs_caption": 12,
        "fs_micro": 11,
        "fw_regular": 400,
        "fw_medium": 500,
        "fw_semibold": 600,
        "fw_bold": 700,
        "icon_xs": 12,
        "icon_sm": 14,
        "icon_md": 16,
        "icon_lg": 18,
    },
}

_FONT_SCALE_DEFAULT_PT = 9
_FONT_SIZE_KEYS = (
    "fs_display",
    "fs_h1",
    "fs_h2",
    "fs_panel_title",
    "fs_body",
    "fs_body_sm",
    "fs_caption",
    "fs_micro",
)


def _resolve_engineering_fs_body_qss(template: str) -> str:
    return str(template).replace(_ENGINEERING_FS_BODY_SENTINEL, str(int(_TOKENS["dark"]["fs_body"])))


def _resolve_engineering_radius_sm_qss(template: str) -> str:
    return str(template).replace(_ENGINEERING_RADIUS_SM_SENTINEL, str(int(_TOKENS["dark"]["r_sm"])))


def _resolve_engineering_input_pad_h_qss(template: str) -> str:
    return str(template).replace(_ENGINEERING_INPUT_PAD_H_SENTINEL, str(int(_TOKENS["dark"]["pad_input_h"])))


_FLUENT_BUTTON_RADIUS_QSS = _resolve_engineering_fs_body_qss(_FLUENT_BUTTON_RADIUS_QSS)
_FLUENT_LINE_EDIT_RADIUS_QSS = _resolve_engineering_fs_body_qss(_FLUENT_LINE_EDIT_RADIUS_QSS)
_FLUENT_COMBO_BOX_RADIUS_QSS = _resolve_engineering_fs_body_qss(_FLUENT_COMBO_BOX_RADIUS_QSS)
_FLUENT_SPIN_BOX_RADIUS_QSS = _resolve_engineering_fs_body_qss(_FLUENT_SPIN_BOX_RADIUS_QSS)
_FLUENT_BUTTON_RADIUS_QSS = _resolve_engineering_radius_sm_qss(_FLUENT_BUTTON_RADIUS_QSS)
_FLUENT_PROPERTY_PANEL_BUTTON_QSS = _resolve_engineering_radius_sm_qss(_FLUENT_PROPERTY_PANEL_BUTTON_QSS)
_FLUENT_LINE_EDIT_RADIUS_QSS = _resolve_engineering_radius_sm_qss(_FLUENT_LINE_EDIT_RADIUS_QSS)
_FLUENT_PROPERTY_PANEL_LINE_EDIT_QSS = _resolve_engineering_radius_sm_qss(_FLUENT_PROPERTY_PANEL_LINE_EDIT_QSS)
_FLUENT_COMBO_BOX_RADIUS_QSS = _resolve_engineering_radius_sm_qss(_FLUENT_COMBO_BOX_RADIUS_QSS)
_FLUENT_PROPERTY_PANEL_COMBO_BOX_QSS = _resolve_engineering_radius_sm_qss(_FLUENT_PROPERTY_PANEL_COMBO_BOX_QSS)
_FLUENT_SPIN_BOX_RADIUS_QSS = _resolve_engineering_radius_sm_qss(_FLUENT_SPIN_BOX_RADIUS_QSS)
_FLUENT_PROPERTY_PANEL_SPIN_BOX_QSS = _resolve_engineering_radius_sm_qss(_FLUENT_PROPERTY_PANEL_SPIN_BOX_QSS)
_FLUENT_PROPERTY_PANEL_BUTTON_QSS = _resolve_engineering_input_pad_h_qss(_FLUENT_PROPERTY_PANEL_BUTTON_QSS)
_FLUENT_LINE_EDIT_RADIUS_QSS = _resolve_engineering_input_pad_h_qss(_FLUENT_LINE_EDIT_RADIUS_QSS)
_FLUENT_PROPERTY_PANEL_LINE_EDIT_QSS = _resolve_engineering_input_pad_h_qss(_FLUENT_PROPERTY_PANEL_LINE_EDIT_QSS)
_FLUENT_COMBO_BOX_RADIUS_QSS = _resolve_engineering_input_pad_h_qss(_FLUENT_COMBO_BOX_RADIUS_QSS)
_FLUENT_PROPERTY_PANEL_COMBO_BOX_QSS = _resolve_engineering_input_pad_h_qss(_FLUENT_PROPERTY_PANEL_COMBO_BOX_QSS)
_FLUENT_SPIN_BOX_RADIUS_QSS = _resolve_engineering_input_pad_h_qss(_FLUENT_SPIN_BOX_RADIUS_QSS)
_FLUENT_PROPERTY_PANEL_SPIN_BOX_QSS = _resolve_engineering_input_pad_h_qss(_FLUENT_PROPERTY_PANEL_SPIN_BOX_QSS)

_WINDOWS_FONTDIR_CANDIDATES = (
    os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"),
)
_MACOS_FONTDIR_CANDIDATES = (
    "/System/Library/Fonts",
    "/Library/Fonts",
)
_LINUX_FONTDIR_CANDIDATES = (
    "/usr/share/fonts",
    "/usr/local/share/fonts",
    os.path.expanduser("~/.local/share/fonts"),
    os.path.expanduser("~/.fonts"),
)

_WINDOWS_UI_FONT_CANDIDATES = (
    "Segoe UI Variable Text",
    "Segoe UI",
    "Microsoft YaHei UI",
    "Microsoft YaHei",
    "Arial",
)
_MACOS_UI_FONT_CANDIDATES = (
    "SF Pro Text",
    "PingFang SC",
    "Helvetica Neue",
    "Arial Unicode MS",
)
_LINUX_UI_FONT_CANDIDATES = (
    "Noto Sans CJK SC",
    "Noto Sans SC",
    "Noto Sans",
    "Source Han Sans SC",
    "WenQuanYi Micro Hei",
    "DejaVu Sans",
    "Arial",
)

_WINDOWS_MONO_FONT_CANDIDATES = (
    "Consolas",
    "Cascadia Mono",
    "Cascadia Code",
    "Lucida Console",
)
_MACOS_MONO_FONT_CANDIDATES = (
    "SF Mono",
    "Menlo",
    "Monaco",
)
_LINUX_MONO_FONT_CANDIDATES = (
    "Noto Sans Mono",
    "DejaVu Sans Mono",
    "Liberation Mono",
    "Monospace",
)


def _fontdir_candidates(platform_name: str | None = None):
    platform_name = platform_name or sys.platform
    if platform_name == "win32":
        return _WINDOWS_FONTDIR_CANDIDATES
    if platform_name == "darwin":
        return _MACOS_FONTDIR_CANDIDATES
    return _LINUX_FONTDIR_CANDIDATES


def _ui_font_candidates(platform_name: str | None = None):
    platform_name = platform_name or sys.platform
    if platform_name == "win32":
        return _WINDOWS_UI_FONT_CANDIDATES
    if platform_name == "darwin":
        return _MACOS_UI_FONT_CANDIDATES
    return _LINUX_UI_FONT_CANDIDATES


def _mono_font_candidates(platform_name: str | None = None):
    platform_name = platform_name or sys.platform
    if platform_name == "win32":
        return _WINDOWS_MONO_FONT_CANDIDATES
    if platform_name == "darwin":
        return _MACOS_MONO_FONT_CANDIDATES
    return _LINUX_MONO_FONT_CANDIDATES


def configure_platform_font_environment(environ=None, platform_name: str | None = None):
    """Point Qt at a real system font directory when the runtime doesn't provide one."""
    env = os.environ if environ is None else environ
    current = str(env.get("QT_QPA_FONTDIR", "") or "").strip()
    if current:
        return current

    for candidate in _fontdir_candidates(platform_name):
        if candidate and os.path.isdir(candidate):
            env["QT_QPA_FONTDIR"] = candidate
            return candidate
    return ""


def _available_font_families():
    try:
        return set(QFontDatabase().families())
    except Exception:
        return set()


def _select_font_family(candidates, available_families, fallback=""):
    for family in candidates:
        if family and family in available_families:
            return family
    return str(fallback or "").strip()


def designer_ui_font_family(app: QApplication | None = None, available_families=None, platform_name: str | None = None):
    """Resolve the preferred proportional UI font family for the current platform."""
    target_app = app if app is not None else QApplication.instance()
    families = set(available_families) if available_families is not None else _available_font_families()
    fallback = ""
    if target_app is not None:
        fallback = str(target_app.font().family() or "").strip()
    if not fallback:
        try:
            fallback = str(QFontDatabase.systemFont(QFontDatabase.GeneralFont).family() or "").strip()
        except Exception:
            fallback = ""
    return _select_font_family(_ui_font_candidates(platform_name), families, fallback) or "Sans Serif"


def designer_monospace_font_family(app: QApplication | None = None, available_families=None, platform_name: str | None = None):
    """Resolve the preferred monospace font family for the current platform."""
    target_app = app if app is not None else QApplication.instance()
    families = set(available_families) if available_families is not None else _available_font_families()
    fallback = ""
    try:
        fallback = str(QFontDatabase.systemFont(QFontDatabase.FixedFont).family() or "").strip()
    except Exception:
        fallback = ""
    if not fallback and target_app is not None:
        fallback = str(target_app.font().family() or "").strip()
    return _select_font_family(_mono_font_candidates(platform_name), families, fallback) or "Monospace"


def designer_ui_font(*, point_size=None, pixel_size=None, weight=None, app: QApplication | None = None):
    font = QFont(designer_ui_font_family(app))
    if point_size is not None and int(point_size) > 0:
        font.setPointSize(int(point_size))
    if pixel_size is not None and int(pixel_size) > 0:
        font.setPixelSize(int(pixel_size))
    if weight is not None:
        font.setWeight(int(weight))
    return font


def designer_monospace_font(*, point_size=None, pixel_size=None, weight=None, app: QApplication | None = None):
    font = QFont(designer_monospace_font_family(app))
    font.setStyleHint(QFont.Monospace)
    if point_size is not None and int(point_size) > 0:
        font.setPointSize(int(point_size))
    if pixel_size is not None and int(pixel_size) > 0:
        font.setPixelSize(int(pixel_size))
    if weight is not None:
        font.setWeight(int(weight))
    return font


def _normalize_density(density="standard"):
    value = str(density or "standard").strip().lower()
    if value in {"roomy_plus", "roomy+", "plus", "spacious"}:
        return "roomy_plus"
    if value in {"roomy", "comfortable", "relaxed"}:
        return "roomy"
    return "standard"


def _normalize_font_size_pt(font_size_pt=0):
    try:
        value = int(font_size_pt or 0)
    except (TypeError, ValueError):
        return 0
    return value if value > 0 else 0


def designer_font_size_pt(app: QApplication | None = None, default=0):
    """Return the persisted Designer font preference in points, or ``default``."""
    target_app = app if app is not None else QApplication.instance()
    value = _normalize_font_size_pt(target_app.property("designer_font_size_pt") if target_app is not None else 0)
    if value > 0:
        return value
    try:
        fallback = int(default or 0)
    except (TypeError, ValueError):
        fallback = 0
    return fallback if fallback > 0 else 0


def designer_font_scale(app: QApplication | None = None, default_pt=_FONT_SCALE_DEFAULT_PT):
    """Return the current Designer font scale relative to the default point size."""
    active_pt = designer_font_size_pt(app, default=default_pt)
    baseline = max(int(default_pt or _FONT_SCALE_DEFAULT_PT), 1)
    return float(active_pt or baseline) / float(baseline)


def scaled_point_size(base_point_size, *, app: QApplication | None = None, minimum=1, default_pt=_FONT_SCALE_DEFAULT_PT):
    """Scale a point size using the Designer font preference."""
    return max(int(minimum), int(round(float(base_point_size) * designer_font_scale(app, default_pt=default_pt))))


def qt_font_weight(weight):
    """Convert a CSS-like font weight token (100-900) to a Qt QFont weight."""
    try:
        numeric = int(weight)
    except (TypeError, ValueError):
        numeric = 400
    if numeric <= 150:
        return QFont.Thin
    if numeric <= 250:
        return QFont.ExtraLight
    if numeric <= 350:
        return QFont.Light
    if numeric <= 450:
        return QFont.Normal
    if numeric <= 550:
        return QFont.Medium
    if numeric <= 650:
        return QFont.DemiBold
    if numeric <= 750:
        return QFont.Bold
    if numeric <= 850:
        return QFont.ExtraBold
    return QFont.Black


def _density_adjusted_tokens(tokens: dict, density="standard"):
    """Return a copy of tokens adjusted for UI density profile."""
    out = dict(tokens or {})
    normalized = _normalize_density(density)
    if normalized == "standard":
        return out

    text_delta = 1 if normalized == "roomy" else 2
    control_delta = 1 if normalized == "roomy" else 2
    tab_delta = 2 if normalized == "roomy" else 4

    # Comfortable profiles: larger text and touch targets.
    for key in ("fs_h1", "fs_h2", "fs_panel_title", "fs_body", "fs_body_sm", "fs_caption", "fs_micro"):
        try:
            out[key] = int(out.get(key, 0)) + text_delta
        except Exception:
            pass
    for key in (
        "pad_btn_v",
        "pad_btn_h",
        "pad_input_v",
        "pad_input_h",
        "pad_tab_compact_v",
        "pad_tab_compact_h",
        "pad_toolbar_h",
    ):
        try:
            out[key] = int(out.get(key, 0)) + control_delta
        except Exception:
            pass
    for key, delta in (("h_tab_min", tab_delta), ("icon_sm", 0), ("icon_md", 0), ("icon_lg", 0)):
        try:
            out[key] = int(out.get(key, 0)) + int(delta)
        except Exception:
            pass
    return out


def _font_adjusted_tokens(tokens: dict, font_size_pt=0):
    """Return a copy of tokens scaled from the user font preference."""
    out = dict(tokens or {})
    normalized = _normalize_font_size_pt(font_size_pt)
    if normalized <= 0:
        return out

    scale = normalized / float(_FONT_SCALE_DEFAULT_PT)
    if abs(scale - 1.0) < 0.001:
        return out

    for key in _FONT_SIZE_KEYS:
        try:
            out[key] = max(1, int(round(float(out.get(key, 0)) * scale)))
        except Exception:
            pass

    for key in (
        "pad_btn_v",
        "pad_btn_h",
        "pad_input_v",
        "pad_input_h",
        "pad_tab_compact_v",
        "pad_tab_compact_h",
        "pad_toolbar_h",
    ):
        try:
            out[key] = max(1, int(round(float(out.get(key, 0)) * scale)))
        except Exception:
            pass

    for key in ("h_tab_min",):
        try:
            out[key] = max(1, int(round(float(out.get(key, 0)) * scale)))
        except Exception:
            pass

    return out


def theme_tokens(mode="dark", density="standard", font_size_pt=0):
    """Return the active token map."""
    base = dict(_TOKENS["light" if mode == "light" else "dark"])
    density_tokens = _density_adjusted_tokens(base, density)
    return _font_adjusted_tokens(density_tokens, font_size_pt=font_size_pt)


def app_theme_tokens(app: QApplication | None = None):
    """Return active theme tokens based on current application properties."""
    target_app = app if app is not None else QApplication.instance()
    mode = "dark"
    density = "standard"
    if target_app is not None:
        mode_prop = str(target_app.property("designer_theme_mode") or "dark").strip().lower()
        if mode_prop == "light":
            mode = "light"
        density_prop = str(target_app.property("designer_ui_density") or "standard").strip().lower()
        density = density_prop if density_prop in {"standard", "roomy", "roomy_plus"} else "standard"
    return theme_tokens(mode, density=density, font_size_pt=designer_font_size_pt(target_app, default=0))


def _windows_colorref(color_value: str) -> int:
    color = QColor(str(color_value or "").strip())
    if not color.isValid():
        return 0
    return (int(color.blue()) << 16) | (int(color.green()) << 8) | int(color.red())


def _qt_widget_is_usable(widget) -> bool:
    if widget is None or not isinstance(widget, QWidget):
        return False
    if pyqt_sip is not None:
        try:
            if pyqt_sip.isdeleted(widget):
                return False
        except Exception:
            return False
    return True


def sync_window_chrome_theme(window: QWidget | None) -> bool:
    """Best-effort sync of the native window chrome with the active Designer theme."""
    if not _qt_widget_is_usable(window) or sys.platform != "win32":
        return False

    try:
        hwnd = int(window.winId())
    except Exception:
        return False
    if hwnd <= 0:
        return False

    try:
        import ctypes
        from ctypes import wintypes

        dwmapi = ctypes.windll.dwmapi
    except Exception:
        return False

    app = QApplication.instance()
    mode = str(app.property("designer_theme_mode") or "dark").strip().lower() if app is not None else "dark"
    tokens = app_theme_tokens(app)
    dark_mode = 0 if mode == "light" else 1

    def _set_attribute(attribute: int, value, value_type) -> bool:
        payload = value_type(value)
        try:
            result = dwmapi.DwmSetWindowAttribute(
                wintypes.HWND(hwnd),
                ctypes.c_uint(attribute),
                ctypes.byref(payload),
                ctypes.sizeof(payload),
            )
        except Exception:
            return False
        return int(result) == 0

    applied = False
    for attribute in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE new/legacy
        applied = _set_attribute(attribute, dark_mode, ctypes.c_int) or applied

    caption_color = _windows_colorref(tokens.get("shell_bg", ""))
    text_color = _windows_colorref(tokens.get("text", ""))
    border_color = _windows_colorref(tokens.get("border", ""))
    applied = _set_attribute(35, caption_color, wintypes.DWORD) or applied  # DWMWA_CAPTION_COLOR
    applied = _set_attribute(36, text_color, wintypes.DWORD) or applied  # DWMWA_TEXT_COLOR
    applied = _set_attribute(34, border_color, wintypes.DWORD) or applied  # DWMWA_BORDER_COLOR
    return applied


# Semantic aliases (spec names → existing keys) for documentation and future refactors.
TOKEN_SEMANTIC_ALIASES = {
    "bg.canvas": "bg",
    "bg.panel": "panel",
    "bg.elevated": "panel_alt",
    "text.primary": "text",
    "text.secondary": "text_muted",
    "text.tertiary": "text_soft",
    "accent.primary": "accent",
    "status.success": "success",
    "status.warn": "warning",
    "status.error": "danger",
    "status.info": "accent",
}


def resolve_semantic_token(mode: str, semantic_name: str, tokens: dict | None = None):
    """Resolve a semantic token name (e.g. ``text.primary``) to a concrete value."""
    key = TOKEN_SEMANTIC_ALIASES.get(str(semantic_name or "").strip())
    if not key:
        return None
    t = tokens if isinstance(tokens, dict) else theme_tokens(mode)
    return t.get(key)


def _has_ancestor_object_name(widget: QWidget | None, object_name: str) -> bool:
    current = widget if _qt_widget_is_usable(widget) else None
    while current is not None:
        try:
            if current.objectName() == object_name:
                return True
            current = current.parentWidget()
        except Exception:
            return False
    return False


def _apply_fluent_engineering_style(widget):
    """Reduce Fluent widget radii so embedded controls match the shell theme."""
    if not HAS_FLUENT or not _qt_widget_is_usable(widget):
        return False

    in_property_panel = _has_ancestor_object_name(widget, "property_panel_root")
    style_kind = None
    custom_qss = ""
    if isinstance(widget, _FLUENT_BUTTON_TYPES):
        style_kind = "property_panel_button" if in_property_panel else "button"
        custom_qss = _FLUENT_PROPERTY_PANEL_BUTTON_QSS if in_property_panel else _FLUENT_BUTTON_RADIUS_QSS
    elif isinstance(widget, _FLUENT_LINE_EDIT_TYPES):
        style_kind = "property_panel_line_edit" if in_property_panel else "line_edit"
        custom_qss = _FLUENT_PROPERTY_PANEL_LINE_EDIT_QSS if in_property_panel else _FLUENT_LINE_EDIT_RADIUS_QSS
    elif isinstance(widget, _FLUENT_COMBO_BOX_TYPES):
        style_kind = "property_panel_combo_box" if in_property_panel else "combo_box"
        custom_qss = _FLUENT_PROPERTY_PANEL_COMBO_BOX_QSS if in_property_panel else _FLUENT_COMBO_BOX_RADIUS_QSS
    elif isinstance(widget, _FLUENT_SPIN_BOX_TYPES):
        style_kind = "property_panel_spin_box" if in_property_panel else "spin_box"
        custom_qss = _FLUENT_PROPERTY_PANEL_SPIN_BOX_QSS if in_property_panel else _FLUENT_SPIN_BOX_RADIUS_QSS

    if not style_kind:
        return False
    if widget.property(_FLUENT_STYLE_MARKER) == style_kind:
        return False

    set_fluent_custom_stylesheet(widget, custom_qss, custom_qss)
    if style_kind == "property_panel_spin_box":
        layout = getattr(widget, "hBoxLayout", None)
        if layout is not None:
            layout.setContentsMargins(
                0,
                _PROPERTY_PANEL_SPIN_LAYOUT_VERTICAL_MARGIN,
                _PROPERTY_PANEL_SPIN_LAYOUT_RIGHT_MARGIN,
                _PROPERTY_PANEL_SPIN_LAYOUT_VERTICAL_MARGIN,
            )
            layout.setSpacing(_PROPERTY_PANEL_SPIN_LAYOUT_SPACING)

        button_size = QSize(_PROPERTY_PANEL_SPIN_BUTTON_WIDTH, _PROPERTY_PANEL_SPIN_BUTTON_HEIGHT)
        icon_size = QSize(_PROPERTY_PANEL_SPIN_ICON_SIZE, _PROPERTY_PANEL_SPIN_ICON_SIZE)
        for attr_name in ("upButton", "downButton"):
            button = getattr(widget, attr_name, None)
            if button is None:
                continue
            button.setFixedSize(button_size)
            button.setMinimumSize(button_size)
            button.setMaximumSize(button_size)
            button.setIconSize(icon_size)
            button.setStyleSheet(_PROPERTY_PANEL_SPIN_BUTTON_QSS)
    widget.setProperty(_FLUENT_STYLE_MARKER, style_kind)
    return True


class _FluentEngineeringStyleManager(QObject):
    def refresh_widget_tree(self, root):
        if not HAS_FLUENT or not _qt_widget_is_usable(root):
            return
        _apply_fluent_engineering_style(root)
        for widget in root.findChildren(QWidget):
            _apply_fluent_engineering_style(widget)

    def refresh_all(self):
        if not HAS_FLUENT:
            return
        for widget in QApplication.allWidgets():
            _apply_fluent_engineering_style(widget)

    def eventFilter(self, obj, event):
        if HAS_FLUENT and _qt_widget_is_usable(obj) and event.type() in (QEvent.Polish, QEvent.Show):
            _apply_fluent_engineering_style(obj)
        return False


class _WindowChromeSyncManager(QObject):
    def refresh_all(self):
        app = QApplication.instance()
        if app is None:
            return
        for widget in list(app.topLevelWidgets()):
            sync_window_chrome_theme(widget)

    def eventFilter(self, obj, event):
        if not _qt_widget_is_usable(obj):
            return False
        try:
            is_window = obj.isWindow()
        except Exception:
            return False
        if is_window and event.type() in (QEvent.Polish, QEvent.Show, QEvent.WinIdChange, QEvent.StyleChange, QEvent.PaletteChange):
            sync_window_chrome_theme(obj)
        return False


def _ensure_fluent_engineering_style_manager(app):
    if not HAS_FLUENT or app is None:
        return None

    manager = getattr(app, "_designer_fluent_engineering_style_manager", None)
    if manager is None:
        manager = _FluentEngineeringStyleManager(app)
        app._designer_fluent_engineering_style_manager = manager
        app.installEventFilter(manager)
    return manager


def _ensure_window_chrome_sync_manager(app):
    if app is None:
        return None

    manager = getattr(app, "_designer_window_chrome_sync_manager", None)
    if manager is None:
        manager = _WindowChromeSyncManager(app)
        app._designer_window_chrome_sync_manager = manager
        app.installEventFilter(manager)
    return manager


def _build_stylesheet(mode="dark", density="standard", font_size_pt=0):
    t = theme_tokens(mode, density=density, font_size_pt=font_size_pt)
    return f"""
QMainWindow, QDialog {{
    background-color: {t['shell_bg']};
    color: {t['text']};
}}

QWidget {{
    background-color: {t['shell_bg']};
    color: {t['text']};
}}

QFrame, QScrollArea {{
    background-color: transparent;
    border: none;
}}

QLabel, QCheckBox, QRadioButton {{
    color: {t['text']};
    background: transparent;
    font-size: {t['fs_body']}px;
    font-weight: {t['fw_regular']};
}}

QLabel[hintTone="muted"] {{
    color: {t['text_soft']};
    font-size: {t['fs_caption']}px;
}}

QLabel[hintTone="success"] {{
    color: {t['success']};
}}

QLabel[hintTone="warning"] {{
    color: {t['warning']};
}}

QLabel[hintTone="danger"] {{
    color: {t['danger']};
}}

QLabel#dialog_muted_hint {{
    color: {t['text_soft']};
}}

QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox, QSpinBox, QDoubleSpinBox, QComboBox {{
    background-color: {t['panel_raised']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: {t['r_sm']}px;
    padding: {t['pad_input_v']}px {t['pad_input_h']}px;
    selection-background-color: {t['selection']};
    font-size: {t['fs_body']}px;
    font-weight: {t['fw_regular']};
}}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QAbstractSpinBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border: 1px solid {t['focus_ring']};
    background-color: {t['panel_raised']};
}}

QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled, QAbstractSpinBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {{
    color: {t['text_soft']};
    background-color: {t['shell_bg']};
    border-color: {t['border_strong']};
}}

QSpinBox[propertyPanelSpin="true"], QDoubleSpinBox[propertyPanelSpin="true"] {{
    border-radius: {t['r_sm']}px;
    min-height: 24px;
    padding: 0px 52px 0px 6px;
}}

QSpinBox[propertyPanelSpin="true"]::up-button, QSpinBox[propertyPanelSpin="true"]::down-button,
QDoubleSpinBox[propertyPanelSpin="true"]::up-button, QDoubleSpinBox[propertyPanelSpin="true"]::down-button {{
    subcontrol-origin: border;
    width: 20px;
    border: none;
    background-color: transparent;
}}

QSpinBox[propertyPanelSpin="true"]::up-button, QDoubleSpinBox[propertyPanelSpin="true"]::up-button {{
    subcontrol-position: top right;
    margin: 2px 2px 0px 0px;
}}

QSpinBox[propertyPanelSpin="true"]::down-button, QDoubleSpinBox[propertyPanelSpin="true"]::down-button {{
    subcontrol-position: bottom right;
    margin: 0px 2px 2px 0px;
}}

QSpinBox[propertyPanelSpin="true"]::up-button:hover, QSpinBox[propertyPanelSpin="true"]::down-button:hover,
QDoubleSpinBox[propertyPanelSpin="true"]::up-button:hover, QDoubleSpinBox[propertyPanelSpin="true"]::down-button:hover {{
    background-color: {t['surface_hover']};
}}

QSpinBox[propertyPanelSpin="true"]::up-button:pressed, QSpinBox[propertyPanelSpin="true"]::down-button:pressed,
QDoubleSpinBox[propertyPanelSpin="true"]::up-button:pressed, QDoubleSpinBox[propertyPanelSpin="true"]::down-button:pressed {{
    background-color: {t['surface_pressed']};
}}

QSpinBox[propertyPanelSpin="true"]::up-arrow, QSpinBox[propertyPanelSpin="true"]::down-arrow,
QDoubleSpinBox[propertyPanelSpin="true"]::up-arrow, QDoubleSpinBox[propertyPanelSpin="true"]::down-arrow {{
    width: {_PROPERTY_PANEL_SPIN_ICON_SIZE}px;
    height: {_PROPERTY_PANEL_SPIN_ICON_SIZE}px;
}}

QPushButton, QToolButton {{
    background-color: {t['panel_raised']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: {t['r_sm']}px;
    padding: {t['pad_btn_v']}px {t['pad_btn_h']}px;
    font-size: {t['fs_body']}px;
    font-weight: {t['fw_medium']};
}}

QPushButton:hover, QToolButton:hover {{
    background-color: {t['surface_hover']};
}}

QPushButton:pressed, QToolButton:pressed {{
    background-color: {t['surface_pressed']};
    border-color: {t['border_strong']};
}}

QPushButton:disabled, QToolButton:disabled {{
    color: {t['text_soft']};
    background-color: {t['shell_bg']};
    border-color: {t['border_strong']};
}}

QListView, QTreeView, QTableView, QListWidget, QTreeWidget, QTableWidget {{
    background-color: {t['panel_raised']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: {t['r_xl']}px;
    outline: none;
}}

QListView::item, QTreeView::item, QTableView::item, QListWidget::item, QTreeWidget::item {{
    padding: {t['space_xxs']}px {t['space_sm']}px;
    min-height: 24px;
}}

QListView::item:hover, QTreeView::item:hover, QListWidget::item:hover, QTreeWidget::item:hover {{
    background-color: {t['selection_hover']};
}}

QTableView::item:hover, QTableWidget::item:hover {{
    background-color: {t['surface_hover']};
}}

QListView::item:selected, QTreeView::item:selected, QListWidget::item:selected, QTreeWidget::item:selected {{
    background-color: {t['selection']};
    color: {t['selection_text']};
}}

QTableView::item:selected, QTableWidget::item:selected {{
    background-color: {t['selection']};
    color: {t['text']};
}}

QListView::item:selected:!active, QTreeView::item:selected:!active,
QListWidget::item:selected:!active, QTreeWidget::item:selected:!active {{
    background-color: {t['selection_soft']};
    color: {t['selection_text']};
}}

QTableView::item:selected:!active, QTableWidget::item:selected:!active {{
    background-color: {t['selection_soft']};
    color: {t['text']};
}}

QListView::item:selected:hover, QTreeView::item:selected:hover,
QListWidget::item:selected:hover, QTreeWidget::item:selected:hover {{
    background-color: {t['selection']};
    color: {t['selection_text']};
}}

QTableView::item:selected:hover, QTableWidget::item:selected:hover {{
    background-color: {t['selection']};
}}

QHeaderView::section {{
    background-color: {t['panel_alt']};
    color: {t['text_muted']};
    padding: {t['space_sm'] - t['space_3xs']}px {t['space_sm']}px;
    border: none;
    border-right: 1px solid {t['border']};
    border-bottom: 1px solid {t['border']};
}}

QTabWidget::pane {{
    border: 1px solid {t['border']};
    border-radius: {t['r_xl']}px;
    background-color: {t['panel_alt']};
    top: -1px;
}}

QTabBar::tab {{
    background-color: {t['sidebar_bg']};
    color: {t['text_soft']};
    padding: {t['space_xxs']}px {t['space_md']}px;
    margin-right: {t['space_xs']}px;
    min-height: {t['h_tab_min']}px;
    border: 1px solid transparent;
    border-top: 2px solid transparent;
    border-radius: 0px;
}}

QTabBar::tab:selected {{
    background-color: {t['panel']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-top: 2px solid {t['accent']};
    border-bottom-color: {t['border']};
}}

QTabBar::tab:hover:!selected {{
    background-color: {t['surface_hover']};
    color: {t['text_muted']};
}}

QMenuBar {{
    background-color: {t['panel_raised']};
    color: {t['text']};
    border-bottom: 1px solid {t['border']};
}}

QMenuBar::item {{
    padding: {t['pad_input_v']}px {t['space_md']}px;
    background: transparent;
    border-radius: {t['r_sm']}px;
}}

QMenuBar::item:selected {{
    background-color: {t['surface_hover']};
}}

QMenu {{
    background-color: {t['panel_raised']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: {t['r_xl']}px;
}}

QMenu::item {{
    padding: 7px 26px 7px 12px;
}}

QMenu::item:selected {{
    background-color: {t['selection']};
}}

QMenu::item:disabled {{
    color: {t['text_soft']};
    background-color: {t['shell_bg']};
}}

QMenu::item:selected:disabled {{
    color: {t['text_soft']};
    background-color: {t['shell_bg']};
}}

QMenu::separator {{
    height: 1px;
    background: {t['border']};
    margin: {t['space_sm'] - t['space_3xs']}px {t['space_sm']}px;
}}

QScrollBar:vertical {{
    background-color: {t['panel_alt']};
    width: 10px;
    margin: 0px;
    border: none;
}}

QScrollBar::handle:vertical {{
    background-color: {t['border_strong']};
    min-height: 24px;
    border: none;
    border-radius: 0px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {t['text_soft']};
}}

QScrollBar::handle:vertical:pressed {{
    background-color: {t['accent']};
}}

QScrollBar::handle:vertical:disabled {{
    background-color: {t['surface_hover']};
}}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    background-color: transparent;
    border: none;
    height: 0px;
}}

QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {{
    background-color: transparent;
}}

QScrollBar:horizontal {{
    background-color: {t['panel_alt']};
    height: 10px;
    margin: 0px;
    border: none;
}}

QScrollBar::handle:horizontal {{
    background-color: {t['border_strong']};
    min-width: 24px;
    border: none;
    border-radius: 0px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {t['text_soft']};
}}

QScrollBar::handle:horizontal:pressed {{
    background-color: {t['accent']};
}}

QScrollBar::handle:horizontal:disabled {{
    background-color: {t['surface_hover']};
}}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {{
    background-color: transparent;
    border: none;
    width: 0px;
}}

QScrollBar::add-page:horizontal,
QScrollBar::sub-page:horizontal {{
    background-color: transparent;
}}

QAbstractScrollArea::corner {{
    background-color: {t['panel_alt']};
    border: none;
}}

QTableCornerButton::section {{
    background-color: {t['panel_alt']};
    border: 1px solid {t['border']};
    border-radius: 0px;
}}

QToolTip {{
    background-color: {t['panel_raised']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: {t['r_md']}px;
    padding: {t['pad_input_v']}px {t['space_sm']}px;
}}

QStatusBar {{
    background-color: {t['panel']};
    color: {t['text_muted']};
    border-top: 1px solid {t['border']};
    padding: 0 {t['space_sm']}px;
}}

QStatusBar QLabel {{
    color: {t['text_muted']};
    font-size: {t['fs_caption']}px;
}}

QGroupBox {{
    background-color: {t['panel']};
    border: 1px solid {t['border']};
    border-radius: {t['r_md']}px;
    margin-top: {t['space_md']}px;
    padding-top: {t['space_sm']}px;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: {t['space_md']}px;
    top: 0px;
    color: {t['text_muted']};
    font-size: {t['fs_panel_title']}px;
    font-weight: {t['fw_medium']};
    padding: 0 {t['r_sm']}px;
}}

QWidget#property_panel_root {{
    background-color: transparent;
}}

QFrame#property_panel_overview {{
    background-color: {t['panel']};
    border: 1px solid {t['border']};
    border-top: none;
    border-radius: {t['r_md']}px;
}}

QFrame#property_panel_search_shell {{
    background-color: transparent;
    border: none;
    border-radius: 0px;
}}

QTreeWidget#property_panel_tree {{
    background-color: transparent;
    border: none;
    padding: 0px;
}}

QTreeWidget#property_panel_tree::item {{
    border-bottom: 1px solid {t['border']};
    padding: 0px;
    min-height: 24px;
}}

QTreeWidget#property_panel_tree::item:selected {{
    background-color: transparent;
    color: {t['text']};
}}

QTreeWidget#property_panel_tree QHeaderView::section {{
    background-color: {t['panel_alt']};
    color: {t['text_muted']};
    border: none;
    border-bottom: 1px solid {t['border']};
    padding: 3px 6px;
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_medium']};
}}

QFrame#property_grid_section_cell {{
    background-color: {t['panel_alt']};
    border: none;
    border-top: 1px solid {t['border_strong']};
    border-bottom: 1px solid {t['border']};
}}

QFrame#property_grid_section_cell[sectionExpanded="true"] {{
    background-color: {t['panel_raised']};
    border-bottom: 1px solid {t['accent']};
}}

QFrame#property_grid_section_fill {{
    background-color: {t['panel_alt']};
    border: none;
    border-left: 1px solid {t['border_strong']};
    border-top: 1px solid {t['border_strong']};
    border-bottom: 1px solid {t['border']};
}}

QFrame#property_grid_section_fill[sectionExpanded="true"] {{
    background-color: {t['panel_raised']};
    border-left: 1px solid {t['border_strong']};
    border-bottom: 1px solid {t['accent']};
}}

QFrame#property_grid_section_cell[sectionHovered="true"],
QFrame#property_grid_section_fill[sectionHovered="true"] {{
    background-color: {t['surface_hover']};
}}

#property_grid_section_text {{
    color: {t['text']};
    font-size: {t['fs_h2']}px;
    font-weight: {t['fw_semibold']};
}}

#property_grid_section_text[sectionExpanded="true"] {{
    color: {t['accent_hover']};
}}

QToolButton#property_grid_section_indicator {{
    background-color: transparent;
    border: none;
    padding: 0px;
    min-width: 12px;
    min-height: 12px;
    max-width: 12px;
    max-height: 12px;
}}

QToolButton#property_grid_section_indicator::menu-indicator {{
    image: none;
}}

#property_grid_section_indicator {{
    color: {t['text_soft']};
    font-size: {t['fs_body_sm']}px;
    font-weight: {t['fw_medium']};
}}

#property_grid_section_indicator[sectionExpanded="true"] {{
    color: {t['accent_hover']};
}}

#property_grid_section_text[sectionHovered="true"],
#property_grid_section_indicator[sectionHovered="true"] {{
    color: {t['text']};
}}

QFrame#property_grid_label_cell {{
    background-color: {t['panel']};
    border: none;
    border-right: 1px solid {t['border_strong']};
    border-bottom: 1px solid {t['border']};
}}

QFrame#property_grid_label_cell[rowStripe="odd"],
QFrame#property_grid_editor_cell[rowStripe="odd"] {{
    background-color: {t['panel_alt']};
}}

#property_grid_label_text {{
    color: {t['text_muted']};
    font-size: {t['fs_body_sm']}px;
}}

QFrame#property_grid_editor_cell {{
    background-color: {t['panel_raised']};
    border: none;
    border-bottom: 1px solid {t['border']};
}}

QFrame#property_grid_label_cell[rowTone="accent"],
QFrame#property_grid_editor_cell[rowTone="accent"] {{
    background-color: {t['accent_soft']};
}}

QFrame#property_grid_label_cell[rowTone="warning"],
QFrame#property_grid_editor_cell[rowTone="warning"] {{
    background-color: {t['panel_soft']};
}}

QFrame#property_grid_label_cell[rowTone="danger"],
QFrame#property_grid_editor_cell[rowTone="danger"] {{
    background-color: {t['selection_soft']};
}}

QFrame#property_grid_label_cell[hoverActive="true"],
QFrame#property_grid_editor_cell[hoverActive="true"] {{
    background-color: {t['surface_hover']};
}}

QFrame#property_grid_label_cell[focusActive="true"] {{
    background-color: {t['panel_soft']};
    border-left: 2px solid {t['focus_ring']};
    border-right: 1px solid {t['border']};
    border-bottom: 1px solid {t['border']};
}}

QFrame#property_grid_editor_cell[focusActive="true"] {{
    background-color: {t['panel_soft']};
    border-bottom: 1px solid {t['border']};
}}

#property_grid_label_text[rowTone="accent"] {{
    color: {t['accent_hover']};
}}

#property_grid_label_text[rowTone="warning"] {{
    color: {t['warning']};
}}

#property_grid_label_text[rowTone="danger"] {{
    color: {t['danger']};
}}

#property_grid_label_text[focusActive="true"] {{
    color: {t['text']};
}}

#property_panel_eyebrow,
#property_panel_header_eyebrow {{
    color: {t['accent_hover']};
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_medium']};
}}

#property_panel_title {{
    color: {t['text']};
    font-size: {t['fs_panel_title']}px;
    font-weight: {t['fw_semibold']};
}}

#property_panel_meta,
#property_panel_search_hint,
#property_panel_header_meta {{
    color: {t['text_muted']};
    font-size: {t['fs_body_sm']}px;
}}

#property_panel_search_label {{
    color: {t['text']};
    font-size: {t['fs_panel_title']}px;
    font-weight: {t['fw_medium']};
}}

QScrollArea#property_panel_scroll {{
    background-color: transparent;
    border: none;
}}

QGroupBox#inspector_collapsible_group {{
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 0px;
    margin-top: 12px;
    padding-top: {t['space_3xs']}px;
    font-size: {t['fs_panel_title']}px;
    font-weight: {t['fw_medium']};
}}

QGroupBox#inspector_collapsible_group::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 0px;
    color: {t['text']};
    padding: 0px 0px 1px 0px;
}}

QGroupBox#inspector_collapsible_group::indicator {{
    width: 0px;
    height: 0px;
}}

QFrame#inspector_group_body {{
    background-color: transparent;
    border: none;
    border-left: 1px solid {t['border_strong']};
    margin-top: 1px;
}}

#workspace_panel_header,
#workspace_hint_strip,
#widget_browser_header,
#workspace_bottom_header {{
    background-color: {t['panel']};
    border: 1px solid {t['border']};
    border-radius: 0px;
}}

#workspace_command_bar {{
    background-color: {t['panel']};
    border: 1px solid {t['border']};
    border-radius: 0px;
}}

#workspace_command_header,
#workspace_command_heading,
#workspace_command_body,
#workspace_command_context_value,
#workspace_command_meta,
#workspace_command_title,
#workspace_command_eyebrow,
#workspace_command_context_eyebrow {{
    background-color: transparent;
    border: none;
}}

#workspace_command_eyebrow,
#workspace_command_context_eyebrow {{
    color: {t['accent_hover']};
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_medium']};
}}

#workspace_command_title {{
    color: {t['text']};
    font-size: {t['fs_panel_title']}px;
    font-weight: {t['fw_semibold']};
}}

#workspace_command_meta {{
    color: {t['text_muted']};
    font-size: {t['fs_body_sm']}px;
}}

#workspace_context_card {{
    background-color: transparent;
    border: none;
    border-radius: {t['r_md']}px;
}}

#workspace_command_body {{
    background-color: transparent;
    border: none;
    border-radius: 0px;
}}

#workspace_command_context_value {{
    color: {t['text']};
    font-size: {t['fs_body']}px;
    font-weight: {t['fw_medium']};
}}

#workspace_hint_strip {{
    background-color: {t['panel_alt']};
    border-color: {t['border']};
}}

#workspace_panel_header[panelTone="property"] {{
    background-color: {t['panel_raised']};
    border-color: {t['border']};
    border-top: none;
}}

#workspace_hint_strip[panelTone="property"] {{
    background-color: transparent;
    border-top: none;
    border-right: none;
    border-bottom: none;
    border-left: 2px solid {t['border_strong']};
}}

#widget_browser_header[panelTone="components"] {{
    background-color: {t['panel']};
    border-color: {t['border']};
}}

#widget_browser_header_eyebrow {{
    color: {t['accent_hover']};
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_medium']};
}}

#widget_browser_header_meta {{
    color: {t['text_muted']};
    font-size: {t['fs_caption']}px;
}}

#widget_browser_header_target {{
    background-color: transparent;
    border: none;
    color: {t['text_soft']};
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_medium']};
    padding: 0px;
}}

#widget_browser_metrics_strip {{
    background-color: transparent;
    border: none;
    border-radius: 0px;
}}

#widget_browser_filter_bar {{
    background-color: transparent;
    border: none;
    border-radius: 0px;
}}

QPushButton#project_workspace_view_button {{
    background-color: transparent;
    border: 1px solid {t['border']};
    border-radius: 0px;
    color: {t['text_muted']};
    font-size: {t['fs_body_sm']}px;
    padding: 0px {t['space_xs']}px;
    text-align: center;
    min-height: 20px;
    max-height: 20px;
}}

QPushButton#project_workspace_view_button:hover {{
    background-color: {t['surface_hover']};
    border-color: {t['border_strong']};
    color: {t['text']};
}}

QPushButton#project_workspace_view_button:checked {{
    background-color: {t['accent_soft']};
    border-color: {t['accent']};
    color: {t['accent_hover']};
}}

#workspace_shell, #workspace_center_shell, #workspace_right_shell, #workspace_bottom_shell {{
    background-color: transparent;
}}

#workspace_left_shell {{
    background-color: {t['sidebar_bg']};
    border: 1px solid {t['border']};
    border-radius: 0px;
}}

#workspace_mode_switch {{
    background-color: transparent;
    border: none;
    border-radius: 0px;
}}

#workspace_indicator_strip {{
    background-color: transparent;
    border: none;
}}

QToolBar#main_toolbar {{
    spacing: 1px;
    background: transparent;
    border: none;
}}

QToolBar#main_toolbar::separator {{
    background-color: {t['border']};
    width: 1px;
    margin: {t['space_toolbar_separator']}px {t['space_toolbar_separator']}px;
}}

QToolBar#main_toolbar QToolButton {{
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 0px;
    color: {t['text_muted']};
    padding: 0px {t['pad_toolbar_h']}px;
    min-height: 20px;
    max-height: 20px;
    font-size: {t['fs_body_sm']}px;
}}

QToolBar#main_toolbar QToolButton:hover {{
    background-color: {t['surface_hover']};
    border-color: {t['border_strong']};
    color: {t['text']};
}}

QToolBar#main_toolbar QToolButton:pressed {{
    background-color: {t['surface_pressed']};
    border-color: {t['border_strong']};
}}

QToolBar#main_toolbar QToolButton:focus {{
    background-color: {t['surface_hover']};
    border-color: {t['focus_ring']};
}}

QToolBar#main_toolbar QToolButton:disabled {{
    color: {t['text_soft']};
    background-color: {t['shell_bg']};
    border-color: {t['border_strong']};
}}

QPushButton#workspace_mode_button {{
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 0px;
    color: {t['text_muted']};
    padding: 0px {t['pad_input_h']}px;
    min-width: 48px;
    max-width: 48px;
    min-height: 20px;
    max-height: 20px;
}}

QPushButton#workspace_mode_button:hover {{
    background-color: {t['surface_hover']};
    color: {t['text']};
}}

QPushButton#workspace_mode_button:checked {{
    background-color: {t['accent_soft']};
    border-color: {t['accent']};
    color: {t['accent_hover']};
}}

QPushButton#workspace_bottom_toggle_button {{
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 0px;
    color: {t['text_muted']};
    padding: 0px {t['pad_input_h']}px;
    min-width: 48px;
    min-height: 20px;
    max-height: 20px;
}}

QPushButton#workspace_bottom_toggle_button:hover {{
    background-color: {t['surface_hover']};
    border-color: {t['border_strong']};
    color: {t['text']};
}}

QPushButton#workspace_bottom_toggle_button:pressed {{
    background-color: {t['surface_pressed']};
    border-color: {t['border_strong']};
}}

QPushButton#workspace_bottom_toggle_button:focus {{
    background-color: {t['surface_hover']};
    border-color: {t['focus_ring']};
}}

QPushButton#workspace_insert_button {{
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 0px;
    color: {t['text_muted']};
    padding: 0px {t['pad_input_h']}px;
    min-width: 48px;
    max-width: 48px;
    min-height: 20px;
    max-height: 20px;
}}

QPushButton#workspace_insert_button:hover {{
    background-color: {t['surface_hover']};
    border-color: {t['border_strong']};
    color: {t['text']};
}}

QPushButton#workspace_insert_button:pressed {{
    background-color: {t['surface_pressed']};
    border-color: {t['border_strong']};
}}

QPushButton#workspace_insert_button:focus {{
    background-color: {t['surface_hover']};
    border-color: {t['focus_ring']};
}}

#editor_tabs_header {{
    background-color: {t['panel_raised']};
    border: 1px solid {t['border']};
    border-radius: 0px;
}}

#editor_tabs_eyebrow {{
    color: {t['accent_hover']};
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_medium']};
}}

#editor_tabs_meta,
#editor_tabs_summary {{
    color: {t['text_muted']};
    font-size: {t['fs_body_sm']}px;
}}

#editor_tabs_mode_strip {{
    background-color: {t['panel_soft']};
    border: 1px solid {t['border']};
    border-radius: {t['r_sm']}px;
}}

#editor_tabs_shell,
#editor_tabs_surface,
#editor_tabs_preview_surface {{
    background-color: {t['panel_raised']};
    border: 1px solid {t['border']};
    border-radius: 0px;
}}

QPlainTextEdit#editor_tabs_xml_editor {{
    background-color: {t['canvas_stage']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: {t['r_sm']}px;
    selection-background-color: {t['selection']};
}}

QSplitter#editor_tabs_splitter::handle {{
    background-color: {t['border']};
    margin: {t['space_xs']}px;
}}

#page_inspector_scroll {{
    background-color: transparent;
    border: none;
}}

QFrame#toolbar_host_separator {{
    background-color: {t['border']};
    min-width: 1px;
    max-width: 1px;
    border: none;
    margin-left: {t['space_3xs']}px;
    margin-right: {t['space_3xs']}px;
}}

QTabWidget#workspace_left_tabs::pane {{
    background-color: transparent;
    border: none;
    border-radius: 0px;
    padding: 0px;
    top: 0px;
}}

QTabWidget#workspace_left_tabs QTabBar::tab {{
    border-radius: 0px;
    margin-right: 0px;
    min-height: 24px;
    padding: {t['pad_tab_compact_v']}px {t['pad_tab_compact_h']}px;
}}

QTabWidget#workspace_inspector_tabs::pane {{
    background-color: transparent;
    border: none;
    border-radius: 0px;
    padding: 0px;
    top: 0px;
}}

QTabWidget#workspace_inspector_tabs QTabBar::tab {{
    border-radius: 0px;
    margin-right: 0px;
    min-height: 24px;
    padding: {t['pad_tab_compact_v']}px {t['pad_tab_compact_h']}px;
}}

QTabWidget#workspace_bottom_tabs::pane {{
    background-color: transparent;
    border: none;
    border-radius: 0px;
    padding: 0px;
    top: 0px;
}}

QTabWidget#workspace_bottom_tabs QTabBar::tab {{
    border-radius: 0px;
    margin-right: 0px;
    min-height: 24px;
    padding: {t['pad_tab_compact_v']}px {t['pad_tab_compact_h']}px;
}}

#workspace_status_chip {{
    background-color: transparent;
    border: 1px solid {t['border']};
    border-radius: 0px;
    color: {t['text_muted']};
    padding: {t['space_xxs']}px {t['space_xs']}px;
}}

QToolButton#workspace_status_chip {{
    background-color: transparent;
    border: 1px solid {t['border']};
    border-radius: 0px;
    color: {t['text_muted']};
    font-size: {t['fs_body_sm']}px;
    padding: {t['space_xxs']}px {t['space_xs']}px;
    min-height: 22px;
}}

QToolButton#workspace_status_chip:hover {{
    background-color: {t['surface_hover']};
    border-color: {t['border_strong']};
}}

QToolButton#workspace_status_chip:pressed {{
    background-color: {t['surface_pressed']};
    border-color: {t['border_strong']};
}}

QToolButton#workspace_status_chip:focus {{
    border-color: {t['accent']};
    background-color: {t['surface_hover']};
}}

#workspace_status_chip[chipTone="accent"] {{
    background-color: {t['selection_soft']};
    color: {t['accent_hover']};
    border-color: {t['accent']};
}}

#workspace_status_chip[chipTone="success"] {{
    background-color: transparent;
    color: {t['success']};
    border-color: {t['success']};
}}

#workspace_status_chip[chipTone="warning"] {{
    background-color: transparent;
    color: {t['warning']};
    border-color: {t['warning']};
}}

#workspace_status_chip[chipTone="danger"] {{
    background-color: transparent;
    color: {t['danger']};
    border-color: {t['danger']};
}}

#workspace_status_chip[chipVariant="property"] {{
    background-color: transparent;
    border-top: 1px solid {t['border']};
    border-right: none;
    border-bottom: none;
    border-left: none;
    color: {t['text_muted']};
    padding: {t['pad_tab_compact_v']}px {t['space_xs']}px;
}}

#workspace_status_chip[chipVariant="property"][chipTone="accent"] {{
    background-color: transparent;
    color: {t['accent']};
    border-top-color: {t['accent']};
}}

#workspace_status_chip[chipVariant="property"][chipTone="success"] {{
    background-color: transparent;
    color: {t['success']};
    border-top-color: {t['success']};
}}

#workspace_status_chip[chipVariant="property"][chipTone="warning"] {{
    background-color: transparent;
    color: {t['warning']};
    border-top-color: {t['warning']};
}}

#workspace_status_chip[chipVariant="property"][chipTone="danger"] {{
    background-color: transparent;
    color: {t['danger']};
    border-top-color: {t['danger']};
}}

QFrame#property_panel_metric_card {{
    background-color: transparent;
    border-top: 1px solid {t['border']};
    border-right: none;
    border-bottom: none;
    border-left: none;
    border-radius: 0px;
}}

QFrame#property_panel_metric_card[metricTone="accent"] {{
    background-color: transparent;
    border-top-color: {t['accent']};
}}

QFrame#property_panel_metric_card[metricTone="success"] {{
    background-color: transparent;
    border-top-color: {t['success']};
}}

QFrame#property_panel_metric_card[metricTone="warning"] {{
    background-color: transparent;
    border-top-color: {t['warning']};
}}

QFrame#property_panel_metric_card[metricTone="danger"] {{
    background-color: transparent;
    border-top-color: {t['danger']};
}}

#property_panel_metric_label {{
    color: {t['text_muted']};
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_medium']};
}}

#property_panel_metric_value {{
    color: {t['text']};
    font-size: {t['fs_body_sm']}px;
    font-weight: {t['fw_medium']};
}}

QToolButton#workspace_summary_indicator {{
    background-color: transparent;
    border: 1px solid {t['border']};
    border-radius: 0px;
    color: {t['text']};
    font-size: {t['fs_body_sm']}px;
    font-weight: {t['fw_medium']};
    padding: {t['pad_tab_compact_v']}px {t['space_xs']}px;
    min-height: 24px;
}}

QToolButton#workspace_summary_indicator:hover {{
    background-color: {t['surface_hover']};
    border-color: {t['border_strong']};
}}

QToolButton#workspace_summary_indicator:focus {{
    border-color: {t['focus_ring']};
}}

QToolButton#workspace_summary_indicator[indicatorTone="success"] {{
    background-color: {t['selection_soft']};
    color: {t['success']};
    border-color: {t['success']};
}}

QToolButton#workspace_summary_indicator[indicatorTone="warning"] {{
    background-color: {t['accent_soft']};
    color: {t['warning']};
    border-color: {t['warning']};
}}

QToolButton#workspace_summary_indicator[indicatorTone="danger"] {{
    background-color: {t['accent_soft']};
    color: {t['danger']};
    border-color: {t['danger']};
}}

#workspace_section_title {{
    color: {t['text']};
    font-size: {t['fs_body']}px;
    font-weight: {t['fw_semibold']};
}}

QWidget#project_workspace_panel QLabel#workspace_section_title,
QWidget#widget_tree_dock QLabel#workspace_section_title,
QWidget#animations_dock QLabel#workspace_section_title,
QWidget#page_fields_dock QLabel#workspace_section_title,
QWidget#page_timers_dock QLabel#workspace_section_title,
QFrame#workspace_bottom_header QLabel#workspace_section_title {{
    font-size: {t['fs_panel_title']}px;
}}

#workspace_section_subtitle {{
    color: {t['text_muted']};
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_regular']};
}}

#workspace_empty_state {{
    color: {t['text_soft']};
    padding: {t['space_xl']}px;
}}

#project_workspace_summary {{
    color: {t['text']};
    font-size: {t['fs_body_sm']}px;
    font-weight: {t['fw_medium']};
}}

#workspace_panel_header[panelTone="project"] {{
    background-color: {t['panel']};
    border-color: {t['border']};
}}

#project_workspace_eyebrow {{
    color: {t['accent_hover']};
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_medium']};
}}

#project_workspace_metrics_strip {{
    background-color: transparent;
    border: none;
    border-radius: 0px;
}}

#project_workspace_meta {{
    color: {t['text_soft']};
    font-size: {t['fs_caption']}px;
}}

#property_panel_empty_state {{
    background-color: transparent;
    border-top: none;
    border-right: none;
    border-bottom: none;
    border-left: none;
    border-radius: 0px;
}}

#resource_panel_shell {{
    background-color: transparent;
}}

#resource_panel_shell QPushButton,
#resource_panel_shell QToolButton,
#resource_panel_shell QComboBox,
#resource_dialog_shell QPushButton,
#resource_dialog_shell QToolButton,
#resource_dialog_shell QComboBox {{
    border-radius: 0px;
    padding: 0px {t['pad_input_h']}px;
    min-height: 20px;
    max-height: 20px;
    font-size: {t['fs_body_sm']}px;
}}

#resource_panel_header {{
    background-color: {t['panel']};
    border: 1px solid {t['border']};
    border-radius: 0px;
}}

#resource_panel_eyebrow {{
    color: {t['accent_hover']};
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_medium']};
}}

#resource_panel_title {{
    color: {t['text']};
    font-size: {t['fs_panel_title']}px;
    font-weight: {t['fw_semibold']};
}}

#resource_panel_subtitle,
#resource_panel_status,
#resource_panel_summary {{
    color: {t['text_muted']};
    font-size: {t['fs_caption']}px;
}}

#resource_panel_card {{
    background-color: transparent;
    border: none;
    border-radius: 0px;
}}

#resource_panel_metric_card {{
    background-color: transparent;
    border: 1px solid {t['border']};
    border-radius: 0px;
}}

#resource_panel_metric_label,
#resource_panel_field_label {{
    color: {t['text_soft']};
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_regular']};
}}

#resource_panel_metric_value {{
    color: {t['text']};
    font-size: {t['fs_body_sm']}px;
    font-weight: {t['fw_medium']};
}}

QListWidget#resource_panel_list,
QListWidget#resource_panel_image_list,
QTableWidget#resource_panel_table {{
    background-color: {t['panel_alt']};
    border: 1px solid {t['border']};
    border-radius: 0px;
    gridline-color: {t['border']};
}}

QListWidget#resource_panel_list::item,
QListWidget#resource_panel_image_list::item,
QTreeWidget#project_dock_tree::item {{
    min-height: 26px;
}}

QTabWidget#resource_panel_tabs::pane {{
    background-color: transparent;
    border: none;
    border-radius: 0px;
    padding: 0px;
}}

QTabWidget#resource_panel_tabs QTabBar::tab {{
    border-radius: 0px;
    margin-right: 0px;
    min-height: 26px;
    padding: {t['space_xxs']}px {t['pad_btn_h']}px;
}}

QTabWidget#resource_panel_details_tabs::pane {{
    background-color: transparent;
    border: none;
    border-radius: 0px;
    padding: 0px;
}}

QTabWidget#resource_panel_details_tabs QTabBar::tab {{
    border-radius: 0px;
    margin-right: 0px;
    min-height: 26px;
    padding: {t['space_xxs']}px {t['pad_btn_h']}px;
}}

QTableWidget#resource_panel_table QHeaderView::section {{
    background-color: {t['panel_soft']};
    color: {t['text_muted']};
    border: none;
    border-bottom: 1px solid {t['border']};
    padding: {t['space_sm']}px;
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_medium']};
}}

#resource_panel_preview {{
    background-color: {t['panel_alt']};
    border: 1px solid {t['border']};
    border-radius: 0px;
}}

#project_dock_shell {{
    background-color: transparent;
}}

#project_dock_header {{
    background-color: {t['panel']};
    border: 1px solid {t['border']};
    border-radius: 0px;
}}

#project_dock_eyebrow {{
    color: {t['accent_hover']};
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_medium']};
}}

#project_dock_title {{
    color: {t['text']};
    font-size: {t['fs_panel_title']}px;
    font-weight: {t['fw_semibold']};
}}

#project_dock_subtitle,
#project_dock_status {{
    color: {t['text_muted']};
    font-size: {t['fs_body_sm']}px;
}}

#project_dock_settings_group {{
    background-color: transparent;
    border: none;
    border-radius: 0px;
}}

QComboBox#project_dock_mode_combo,
QPushButton#project_dock_add_page_button {{
    background-color: transparent;
    border: 1px solid {t['border']};
    border-radius: 0px;
    color: {t['text_muted']};
    padding: {t['pad_btn_v']}px {t['pad_input_h']}px;
    min-height: 26px;
}}

QComboBox#project_dock_mode_combo:hover,
QPushButton#project_dock_add_page_button:hover {{
    background-color: {t['surface_hover']};
    border-color: {t['border_strong']};
    color: {t['text']};
}}

QPushButton#project_dock_add_page_button:disabled {{
    color: {t['text_soft']};
    background-color: {t['shell_bg']};
    border-color: {t['border_strong']};
}}

#project_dock_metric_card {{
    background-color: transparent;
    border: none;
    border-radius: 0px;
}}

#project_dock_metric_label,
#project_dock_field_label {{
    color: {t['text_soft']};
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_regular']};
}}

#project_dock_metric_value {{
    color: {t['text']};
    font-size: {t['fs_body_sm']}px;
    font-weight: {t['fw_medium']};
}}

QTreeWidget#project_dock_tree {{
    background-color: {t['panel_alt']};
    border: 1px solid {t['border']};
    border-radius: 0px;
}}

#workspace_panel_header[panelTone="structure"] {{
    background-color: {t['panel_raised']};
    border-color: {t['border']};
}}

#structure_header_eyebrow {{
    color: {t['accent_hover']};
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_medium']};
}}

#structure_header_meta,
#structure_panel_hint {{
    color: {t['text_muted']};
    font-size: {t['fs_body_sm']}px;
}}

#structure_panel_label {{
    color: {t['text']};
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_medium']};
}}

#structure_metrics_strip {{
    background-color: transparent;
    border: none;
    border-radius: 0px;
}}

#structure_primary_strip,
#structure_filter_bar,
#structure_selection_strip {{
    background-color: transparent;
    border: none;
    border-radius: 0px;
}}

#structure_drag_hint_strip {{
    background-color: transparent;
    border: none;
    border-radius: 0px;
}}

#structure_primary_strip QPushButton,
#structure_primary_strip QToolButton,
#structure_selection_strip QPushButton,
#structure_selection_strip QToolButton,
#structure_filter_bar QPushButton {{
    background-color: transparent;
    border: 1px solid {t['border']};
    border-radius: 0px;
    color: {t['text_muted']};
    padding: {t['space_3xs']}px {t['space_sm']}px;
    min-height: 26px;
}}

#structure_primary_strip QPushButton:hover,
#structure_primary_strip QToolButton:hover,
#structure_selection_strip QPushButton:hover,
#structure_selection_strip QToolButton:hover,
#structure_filter_bar QPushButton:hover {{
    background-color: {t['surface_hover']};
    border-color: {t['border_strong']};
    color: {t['text']};
}}

#structure_primary_strip QPushButton:disabled,
#structure_primary_strip QToolButton:disabled,
#structure_selection_strip QPushButton:disabled,
#structure_selection_strip QToolButton:disabled,
#structure_filter_bar QPushButton:disabled {{
    color: {t['text_soft']};
    background-color: {t['shell_bg']};
    border-color: {t['border_strong']};
}}

#diagnostics_header {{
    background-color: {t['panel']};
    border: 1px solid {t['border']};
    border-top: none;
    border-radius: 0px;
}}

#diagnostics_header[panelTone="diagnostics"] {{
    background-color: {t['panel']};
    border-color: {t['border']};
}}

#diagnostics_header_eyebrow {{
    color: {t['accent_hover']};
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_medium']};
}}

#diagnostics_header_meta {{
    color: {t['text_muted']};
    font-size: {t['fs_caption']}px;
}}

#diagnostics_controls_strip,
#diagnostics_export_strip {{
    background-color: transparent;
    border: none;
    border-radius: 0px;
}}

#diagnostics_controls_strip QComboBox,
#diagnostics_controls_strip QPushButton,
#diagnostics_export_strip QPushButton {{
    background-color: transparent;
    border: 1px solid {t['border']};
    border-radius: 0px;
    color: {t['text_muted']};
    padding: {t['pad_tab_compact_v']}px {t['space_sm']}px;
    min-height: 24px;
}}

#diagnostics_controls_strip QComboBox:hover,
#diagnostics_controls_strip QPushButton:hover,
#diagnostics_export_strip QPushButton:hover {{
    background-color: {t['surface_hover']};
    border-color: {t['border_strong']};
    color: {t['text']};
}}

#diagnostics_controls_strip QComboBox:disabled,
#diagnostics_controls_strip QPushButton:disabled,
#diagnostics_export_strip QPushButton:disabled {{
    color: {t['text_soft']};
    background-color: {t['shell_bg']};
    border-color: {t['border_strong']};
}}

QListWidget#diagnostics_list {{
    background-color: {t['panel_alt']};
    border: 1px solid {t['border']};
    border-radius: 0px;
    padding: {t['space_xxs']}px;
}}

#debug_panel_header {{
    background-color: {t['panel']};
    border: 1px solid {t['border']};
    border-top: none;
    border-radius: 0px;
}}

#debug_panel_header[panelTone="runtime"] {{
    background-color: {t['panel']};
    border-color: {t['border']};
}}

#debug_panel_eyebrow {{
    color: {t['accent_hover']};
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_medium']};
}}

#debug_panel_header_meta {{
    color: {t['text_muted']};
    font-size: {t['fs_caption']}px;
}}

#debug_panel_controls_strip {{
    background-color: transparent;
    border: none;
    border-radius: 0px;
}}

#debug_panel_controls_strip QPushButton {{
    background-color: transparent;
    border: 1px solid {t['border']};
    border-radius: 0px;
    color: {t['text_muted']};
    padding: {t['pad_tab_compact_v']}px {t['space_sm']}px;
    min-height: 24px;
}}

#debug_panel_controls_strip QPushButton:hover {{
    background-color: {t['surface_hover']};
    border-color: {t['border_strong']};
    color: {t['text']};
}}

#debug_panel_controls_strip QPushButton:disabled {{
    color: {t['text_soft']};
    background-color: {t['shell_bg']};
    border-color: {t['border_strong']};
}}

QPlainTextEdit#debug_output_surface {{
    background-color: {t['canvas_stage']};
    border: 1px solid {t['border']};
    border-radius: 0px;
    padding: {t['space_xxs']}px;
}}

#history_panel_header {{
    background-color: {t['panel']};
    border: 1px solid {t['border']};
    border-top: none;
    border-radius: 0px;
}}

#history_panel_header[panelTone="history"] {{
    background-color: {t['panel']};
    border-color: {t['border']};
}}

#history_panel_eyebrow {{
    color: {t['accent_hover']};
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_medium']};
}}

#history_panel_meta {{
    color: {t['text_muted']};
    font-size: {t['fs_caption']}px;
}}

QListWidget#history_panel_list {{
    background-color: {t['panel_alt']};
    border: 1px solid {t['border']};
    border-radius: 0px;
    padding: {t['space_xxs']}px;
}}

#animations_panel_header {{
    background-color: {t['panel']};
    border: 1px solid {t['border']};
    border-top: none;
    border-radius: 0px;
}}

#animations_panel_header[panelTone="animations"] {{
    background-color: {t['panel']};
    border-color: {t['border']};
}}

#animations_panel_eyebrow {{
    color: {t['accent_hover']};
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_medium']};
}}

#animations_panel_meta {{
    color: {t['text_muted']};
    font-size: {t['fs_body_sm']}px;
}}

#animations_panel_actions_strip {{
    background-color: transparent;
    border: none;
    border-radius: 0px;
}}

#animations_panel_actions_strip QPushButton {{
    background-color: transparent;
    border: 1px solid {t['border']};
    border-radius: 0px;
    color: {t['text_muted']};
    padding: 0px {t['space_sm']}px;
    min-height: 20px;
    max-height: 20px;
    font-size: {t['fs_body_sm']}px;
}}

#animations_panel_actions_strip QPushButton:hover {{
    background-color: {t['surface_hover']};
    border-color: {t['border_strong']};
    color: {t['text']};
}}

#animations_panel_actions_strip QPushButton:disabled {{
    color: {t['text_soft']};
    background-color: {t['shell_bg']};
    border-color: {t['border_strong']};
}}

QTableWidget#animations_panel_table {{
    background-color: {t['panel_alt']};
    border: 1px solid {t['border']};
    border-radius: 0px;
    padding: {t['space_xxs']}px;
}}

QTableWidget#animations_panel_table QHeaderView::section,
QTableWidget#page_editor_table QHeaderView::section {{
    padding: {t['pad_btn_v']}px {t['pad_input_h']}px;
    font-size: {t['fs_caption']}px;
}}

QGroupBox#animations_panel_detail_group {{
    background-color: transparent;
    border: none;
    border-radius: 0px;
    margin-top: 0px;
    padding-top: 0px;
}}

QWidget#animations_dock QComboBox,
QWidget#animations_dock QSpinBox,
QWidget#animations_dock QLineEdit {{
    border-radius: 0px;
    padding: 0px {t['pad_input_h']}px;
    min-height: 20px;
    max-height: 20px;
    font-size: {t['fs_body_sm']}px;
}}

QWidget#animations_dock QCheckBox {{
    min-height: 20px;
    font-size: {t['fs_body_sm']}px;
}}

QTreeWidget#widget_tree_panel_tree {{
    background-color: {t['panel_alt']};
    border: 1px solid {t['border']};
    border-radius: 0px;
    padding: 0px;
}}

#page_editor_header {{
    background-color: {t['panel_raised']};
    border: 1px solid {t['border']};
    border-radius: 0px;
}}

#page_fields_header[panelTone="fields"] {{
    background-color: {t['panel_raised']};
    border: 1px solid {t['border']};
    border-top: none;
    border-radius: 0px;
}}

#page_fields_eyebrow {{
    color: {t['accent_hover']};
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_medium']};
}}

#page_fields_meta {{
    color: {t['text_muted']};
    font-size: {t['fs_body_sm']}px;
}}

#page_fields_metrics_strip {{
    background-color: transparent;
    border: none;
    border-radius: 0px;
}}

#page_timers_header[panelTone="timers"] {{
    background-color: {t['panel_raised']};
    border: 1px solid {t['border']};
    border-top: none;
    border-radius: 0px;
}}

#page_timers_eyebrow {{
    color: {t['accent_hover']};
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_medium']};
}}

#page_timers_meta {{
    color: {t['text_muted']};
    font-size: {t['fs_body_sm']}px;
}}

#page_timers_metrics_strip {{
    background-color: transparent;
    border: none;
    border-radius: 0px;
}}

#page_editor_eyebrow {{
    color: {t['accent_hover']};
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_medium']};
}}

#page_editor_meta {{
    color: {t['text_muted']};
    font-size: {t['fs_body_sm']}px;
}}

#page_editor_section,
#page_editor_actions,
#page_editor_table_shell {{
    background-color: transparent;
    border: none;
    border-radius: 0px;
}}

#page_editor_section_label {{
    color: {t['text']};
    font-size: {t['fs_body_sm']}px;
    font-weight: {t['fw_medium']};
}}

#page_editor_table {{
    background-color: {t['panel_alt']};
    border: 1px solid {t['border']};
    border-radius: 0px;
}}

#page_editor_actions QPushButton,
#page_editor_section QPushButton,
#page_editor_table_shell QPushButton {{
    background-color: transparent;
    border: 1px solid {t['border']};
    border-radius: 0px;
    color: {t['text_muted']};
    padding: 0px {t['space_sm']}px;
    min-height: 20px;
    max-height: 20px;
    font-size: {t['fs_body_sm']}px;
}}

#page_editor_actions QPushButton:hover,
#page_editor_section QPushButton:hover,
#page_editor_table_shell QPushButton:hover {{
    background-color: {t['surface_hover']};
    border-color: {t['border_strong']};
    color: {t['text']};
}}

#page_editor_actions QPushButton:disabled,
#page_editor_section QPushButton:disabled,
#page_editor_table_shell QPushButton:disabled {{
    color: {t['text_soft']};
    background-color: {t['shell_bg']};
    border-color: {t['border_strong']};
}}

#page_navigator_header {{
    background-color: {t['panel']};
    border: 1px solid {t['border']};
    border-radius: 0px;
}}

#page_navigator_eyebrow {{
    color: {t['accent_hover']};
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_medium']};
}}

#page_navigator_meta,
#page_navigator_page_meta,
#page_navigator_guidance_text {{
    color: {t['text_muted']};
    font-size: {t['fs_body_sm']}px;
}}

#page_navigator_guidance {{
    background-color: transparent;
    border: none;
    border-radius: 0px;
}}

#page_navigator_scroll_shell {{
    background-color: transparent;
    border: none;
    border-radius: 0px;
}}

QScrollArea#page_navigator_scroll,
#page_navigator_list {{
    background-color: transparent;
    border: none;
    border-radius: 0px;
}}

#page_navigator_empty_state {{
    background-color: transparent;
    border: 1px solid {t['border']};
    border-radius: 0px;
    color: {t['text_soft']};
    padding: {t['space_md']}px;
}}

#page_navigator_thumbnail {{
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 0px;
}}

#page_navigator_thumbnail:hover {{
    background-color: {t['surface_hover']};
    border-color: {t['border']};
}}

#page_navigator_thumbnail[startup="true"] {{
    border-color: {t['success']};
}}

#page_navigator_thumbnail[selected="true"] {{
    background-color: {t['selection_soft']};
    border-color: {t['accent']};
}}

QFrame#page_navigator_thumb_surface {{
    background-color: transparent;
    border: none;
    border-radius: 0px;
}}

QFrame#page_navigator_thumb_surface[startup="true"] {{
    border-color: {t['success']};
}}

QFrame#page_navigator_thumb_surface[selected="true"] {{
    background-color: {t['selection_soft']};
    border-color: {t['accent']};
}}

QLabel#page_navigator_thumb_label {{
    background-color: {t['canvas_stage']};
    border: 1px solid {t['border']};
    border-radius: 0px;
    padding: {t['space_3xs']}px;
}}

QLabel#page_navigator_thumb_label[startup="true"] {{
    border-color: {t['success']};
}}

QLabel#page_navigator_thumb_label[selected="true"] {{
    border-color: {t['accent']};
}}

#page_navigator_page_name {{
    color: {t['text']};
    font-size: {t['fs_body_sm']}px;
    font-weight: {t['fw_medium']};
}}

#page_navigator_page_name[dirty="true"] {{
    color: {t['warning']};
}}

#app_selector_header {{
    background-color: {t['panel']};
    border: 1px solid {t['border']};
    border-radius: 0px;
}}

#app_selector_eyebrow {{
    color: {t['accent_hover']};
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_medium']};
}}

#app_selector_title {{
    color: {t['text']};
    font-size: {t['fs_h1']}px;
    font-weight: {t['fw_semibold']};
}}

#app_selector_subtitle {{
    color: {t['text_muted']};
    font-size: {t['fs_body']}px;
    font-weight: {t['fw_regular']};
}}

#app_selector_root_card,
#app_selector_options_card,
#app_selector_browser_card,
#app_selector_selection_card {{
    background-color: transparent;
    border: none;
    border-radius: 0px;
}}

#app_selector_metric_card {{
    background-color: transparent;
    border: none;
    border-radius: 0px;
}}

#app_selector_metric_label,
#app_selector_field_label {{
    color: {t['text_soft']};
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_regular']};
}}

#app_selector_metric_value,
#app_selector_status_value,
#app_selector_selection_value {{
    color: {t['text']};
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_medium']};
}}

QListWidget#app_selector_list {{
    background-color: transparent;
    border: none;
    outline: none;
}}

QListWidget#app_selector_list::item {{
    padding: 0;
    margin: 0;
    border: none;
}}

QListWidget#app_selector_list::item:selected,
QListWidget#app_selector_list::item:hover {{
    background-color: transparent;
}}

#app_selector_item_card {{
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 0px;
}}

#app_selector_item_card[selected="true"] {{
    background-color: {t['selection_soft']};
    border-color: {t['accent']};
}}

#app_selector_item_title {{
    color: {t['text']};
    font-size: {t['fs_body']}px;
    font-weight: {t['fw_medium']};
}}

#app_selector_item_meta {{
    color: {t['text_soft']};
    font-size: {t['fs_caption']}px;
}}

#app_selector_item_kind {{
    background-color: transparent;
    border: 1px solid {t['border']};
    border-radius: {t['r_md']}px;
    color: {t['text_muted']};
    font-size: {t['fs_micro']}px;
    font-weight: {t['fw_medium']};
    padding: {t['space_xxs']}px {t['space_sm']}px;
}}

#app_selector_item_kind[entryKind="project"] {{
    color: {t['success']};
    border-color: {t['success']};
}}

#app_selector_item_kind[entryKind="legacy"] {{
    color: {t['warning']};
    border-color: {t['warning']};
}}

#resource_dialog_header {{
    background-color: {t['panel']};
    border: 1px solid {t['border']};
    border-radius: 0px;
}}

#resource_dialog_eyebrow {{
    color: {t['accent_hover']};
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_medium']};
}}

#resource_dialog_title {{
    color: {t['text']};
    font-size: {t['fs_h1']}px;
    font-weight: {t['fw_semibold']};
}}

#resource_dialog_subtitle {{
    color: {t['text_muted']};
    font-size: {t['fs_body']}px;
    font-weight: {t['fw_regular']};
}}

#resource_dialog_card {{
    background-color: transparent;
    border: none;
    border-radius: 0px;
}}

#resource_dialog_metric_card {{
    background-color: transparent;
    border: none;
    border-radius: 0px;
}}

#resource_dialog_metric_label {{
    color: {t['text_soft']};
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_regular']};
}}

#resource_dialog_metric_value {{
    color: {t['text']};
    font-size: {t['fs_body_sm']}px;
    font-weight: {t['fw_medium']};
}}

#resource_dialog_summary {{
    color: {t['text_muted']};
    font-size: {t['fs_caption']}px;
}}

QTableWidget#resource_dialog_table {{
    background-color: {t['panel_alt']};
    border: 1px solid {t['border']};
    border-radius: 0px;
    gridline-color: {t['border']};
}}

QTableWidget#resource_dialog_table QHeaderView::section {{
    background-color: {t['panel_soft']};
    color: {t['text_muted']};
    border: none;
    border-bottom: 1px solid {t['border']};
    padding: {t['space_sm']}px;
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_medium']};
}}

#new_project_header {{
    background-color: {t['panel']};
    border: 1px solid {t['border']};
    border-radius: 0px;
}}

#new_project_eyebrow {{
    color: {t['accent_hover']};
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_medium']};
}}

#new_project_title {{
    color: {t['text']};
    font-size: {t['fs_h1']}px;
    font-weight: {t['fw_semibold']};
}}

#new_project_subtitle {{
    color: {t['text_muted']};
    font-size: {t['fs_body']}px;
    font-weight: {t['fw_regular']};
}}

#new_project_form_card,
#new_project_summary_card {{
    background-color: transparent;
    border: none;
    border-radius: 0px;
}}

#new_project_metric_card,
#new_project_dimension_card {{
    background-color: transparent;
    border: none;
    border-radius: 0px;
}}

#new_project_metric_label,
#new_project_summary_caption,
#new_project_field_label {{
    color: {t['text_soft']};
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_regular']};
}}

#new_project_metric_value,
#new_project_summary_value {{
    color: {t['text']};
    font-size: {t['fs_body_sm']}px;
    font-weight: {t['fw_medium']};
}}

#welcome_shell,
#welcome_center {{
    background-color: transparent;
    border: none;
}}

#welcome_hero {{
    background-color: {t['panel']};
    border: 1px solid {t['border']};
    border-radius: 0px;
}}

#welcome_eyebrow {{
    color: {t['accent_hover']};
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_medium']};
}}

#welcome_hero_title {{
    color: {t['text']};
    font-size: {t['fs_h1']}px;
    font-weight: {t['fw_semibold']};
}}

#welcome_hero_subtitle {{
    color: {t['text_muted']};
    font-size: {t['fs_body']}px;
    font-weight: {t['fw_regular']};
}}

#welcome_hero_hint {{
    color: {t['text_soft']};
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_regular']};
}}

#welcome_action_panel,
#welcome_recent_panel {{
    background-color: transparent;
    border: none;
    border-radius: 0px;
}}

#welcome_sdk_panel {{
    background-color: transparent;
    border: none;
    border-radius: 0px;
}}

#welcome_metric_card {{
    background-color: transparent;
    border: none;
    border-radius: 0px;
}}

#welcome_metric_label {{
    color: {t['text_soft']};
    font-size: {t['fs_micro']}px;
    font-weight: {t['fw_regular']};
}}

#welcome_metric_value {{
    color: {t['text']};
    font-size: {t['fs_body_sm']}px;
    font-weight: {t['fw_medium']};
}}

#welcome_recent_item {{
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 0px;
}}

#welcome_recent_item:hover {{
    background-color: {t['surface_hover']};
    border-color: {t['border']};
}}

#welcome_recent_item:focus {{
    border-color: {t['focus_ring']};
}}

#welcome_recent_icon_shell {{
    background-color: {t['accent_soft']};
    border: 1px solid {t['border']};
    border-radius: {t['r_md']}px;
}}

#welcome_recent_name {{
    color: {t['text']};
    font-size: {t['fs_body']}px;
    font-weight: {t['fw_medium']};
}}

#welcome_recent_path {{
    color: {t['text_soft']};
    font-size: {t['fs_caption']}px;
}}

#welcome_recent_status {{
    background-color: transparent;
    border: none;
    border-radius: 0px;
    color: {t['text_muted']};
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_medium']};
    padding: 0px;
}}

#welcome_recent_status[chipTone="success"] {{
    color: {t['success']};
    border-color: {t['success']};
}}

#welcome_recent_status[chipTone="warning"] {{
    color: {t['warning']};
    border-color: {t['warning']};
}}

#welcome_recent_status[chipTone="danger"] {{
    color: {t['danger']};
    border-color: {t['danger']};
}}

#welcome_recent_empty {{
    background-color: transparent;
    border: 1px dashed {t['border']};
    border-radius: 0px;
    padding: {t['space_lg'] + t['space_3xs']}px;
}}

#widget_browser_results,
#widget_browser_results_host {{
    background-color: transparent;
    border: none;
}}

#widget_browser_card {{
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 0px;
}}

#widget_browser_card:hover {{
    background-color: {t['panel_soft']};
}}

#widget_browser_card[selected="true"] {{
    border: 1px solid {t['accent_soft']};
    background-color: {t['selection_soft']};
}}

#widget_browser_card_title {{
    font-size: {t['fs_body']}px;
    font-weight: {t['fw_medium']};
    color: {t['text']};
}}

#widget_browser_card_meta {{
    color: {t['text_soft']};
    font-size: {t['fs_caption']}px;
}}

#widget_browser_empty_state {{
    background-color: transparent;
    border: 1px dashed {t['border']};
    border-radius: 0px;
}}

QPushButton#widget_browser_insert_button {{
    background-color: transparent;
    border: 1px solid {t['border']};
    border-radius: 0px;
    color: {t['text_muted']};
    font-size: {t['fs_body_sm']}px;
    padding: {t['pad_btn_v']}px {t['space_xs']}px;
}}

QPushButton#widget_browser_insert_button:hover {{
    background-color: {t['surface_hover']};
    border-color: {t['border_strong']};
    color: {t['text']};
}}

QPushButton#widget_browser_insert_button:pressed {{
    background-color: {t['panel_soft']};
}}

#widget_browser_favorite_button {{
    border: none;
    background: transparent;
    color: {t['text_soft']};
    font-size: {t['icon_xs']}px;
    padding: 0;
}}

#widget_browser_favorite_button:checked {{
    color: {t['warning']};
}}

#preview_header {{
    background-color: {t['panel_raised']};
    border: 1px solid {t['border']};
    border-radius: 0px;
}}

#preview_eyebrow {{
    color: {t['accent_hover']};
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_medium']};
}}

#preview_meta {{
    color: {t['text_muted']};
    font-size: {t['fs_body_sm']}px;
}}

#preview_metrics_strip {{
    background-color: transparent;
    border: none;
    border-radius: 0px;
}}

#preview_title {{
    color: {t['text']};
    font-size: {t['fs_panel_title']}px;
    font-weight: {t['fw_semibold']};
}}

#preview_content {{
    background-color: {t['canvas_bg']};
    border: 1px solid {t['border']};
    border-radius: 0px;
}}

#preview_stage_shell,
#preview_overlay_shell {{
    background-color: {t['panel_raised']};
    border: 1px solid {t['border']};
    border-radius: 0px;
}}

QScrollArea#preview_overlay_scroll {{
    background-color: transparent;
    border: none;
}}

QWidget#preview_overlay_surface[solidBackground="true"] {{
    background-color: {t['canvas_stage']};
    border: 1px solid {t['border']};
    border-radius: 0px;
}}

QWidget#preview_overlay_surface[solidBackground="false"] {{
    background-color: transparent;
    border: none;
}}

#preview_stage_frame {{
    background-color: {t['canvas_stage']};
    border: 1px solid {t['border']};
    border-radius: 0px;
}}

QSplitter#preview_splitter::handle {{
    background-color: {t['border']};
    margin: {t['space_xs']}px;
}}

#preview_status_shell {{
    background-color: {t['panel_raised']};
    border: 1px solid {t['border']};
    border-radius: 0px;
}}

#preview_status_value {{
    color: {t['text_muted']};
    font-size: {t['fs_caption']}px;
}}

QPushButton#preview_status_button {{
    background-color: {t['panel_alt']};
    border: 1px solid {t['border']};
    border-radius: 0px;
    padding: 0;
}}

QPushButton#preview_status_button:hover {{
    background-color: {t['surface_hover']};
}}

"""


def _apply_app_base_font(app: QApplication, tokens: dict):
    """Set the application baseline font so unstylized widgets match theme body text."""
    if app is None:
        return
    font = app.font()
    font.setFamily(designer_ui_font_family(app))
    try:
        pixel_size = int(tokens.get("fs_body", 13))
    except (TypeError, ValueError):
        pixel_size = 13
    try:
        weight = int(tokens.get("fw_regular", 400))
    except (TypeError, ValueError):
        weight = 400
    font.setPixelSize(max(pixel_size, 1))
    font.setWeight(qt_font_weight(weight))
    app.setFont(font)


def apply_theme(app: QApplication, mode="dark", density="standard"):
    """Apply the requested theme mode and density profile."""
    mode = "light" if mode == "light" else "dark"
    density = _normalize_density(density)
    font_size_pt = _normalize_font_size_pt(app.property("designer_font_size_pt") if app is not None else 0)
    if HAS_FLUENT and app is not None:
        fluent_mode = app.property("_designer_fluent_theme_mode")
        if fluent_mode != mode:
            platform_name = ""
            try:
                platform_name = str(app.platformName() or "").lower()
            except Exception:
                platform_name = ""
            if platform_name != "offscreen":
                try:
                    setTheme(Theme.LIGHT if mode == "light" else Theme.DARK)
                except RuntimeError as exc:
                    # qfluentwidgets keeps a process-global QConfig that can outlive a
                    # prior QApplication in tests; keep applying Designer theming even
                    # if Fluent's theme dispatcher is already invalid.
                    if "QConfig" not in str(exc):
                        raise
            app.setProperty("_designer_fluent_theme_mode", mode)
    app.setProperty("designer_theme_mode", mode)
    app.setProperty("designer_ui_density", density)
    app.setProperty("designer_font_size_pt", font_size_pt)
    tokens = theme_tokens(mode, density=density, font_size_pt=font_size_pt)
    _apply_app_base_font(app, tokens)
    stylesheet = _build_stylesheet(mode, density=density, font_size_pt=font_size_pt)
    if app.styleSheet() != stylesheet:
        app.setStyleSheet(stylesheet)
    try:
        from .iconography import _load_lucide_icon_cached

        _load_lucide_icon_cached.cache_clear()
    except Exception:
        pass
    chrome_manager = _ensure_window_chrome_sync_manager(app)
    manager = _ensure_fluent_engineering_style_manager(app)
    if manager is not None:
        manager.refresh_all()
    if chrome_manager is not None:
        chrome_manager.refresh_all()
