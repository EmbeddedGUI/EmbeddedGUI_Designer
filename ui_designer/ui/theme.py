"""Token-driven application theme for EmbeddedGUI Designer.

Aligned with ``UI_UIX_REDESIGN_MASTER_PLAN.md`` (UIX-001):
- Color roles: canvas bg, panel bg, text primary/muted/soft, accent, status.
- Typography scale: Display / Heading / Section / Body / Meta / Caption (px sizes).
- Spacing: 4pt baseline; 8/12/16/20/24 via space_* keys.
- Radii: r_sm=inputs(6), r_md/cards/buttons(8), r_xl≈elevated(12).
- Icons: icon_sm/md/lg = 16/18/20 (toolbar leans toward lg).
"""

from __future__ import annotations

from PyQt5.QtCore import QEvent, QObject
from PyQt5.QtWidgets import QApplication, QWidget

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
    border-radius: {_ENGINEERING_RADIUS_MD}px;
}}
"""

_FLUENT_LINE_EDIT_RADIUS_QSS = f"""
LineEdit,
TextEdit,
PlainTextEdit,
TextBrowser {{
    border-radius: {_ENGINEERING_RADIUS_MD}px;
}}

#lineEditButton {{
    border-radius: {_ENGINEERING_RADIUS_SM}px;
}}
"""

_FLUENT_COMBO_BOX_RADIUS_QSS = f"""
ComboBox,
ModelComboBox {{
    border-radius: {_ENGINEERING_RADIUS_MD}px;
}}
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
    border-radius: {_ENGINEERING_RADIUS_MD}px;
}}

SpinButton {{
    border-radius: {_ENGINEERING_RADIUS_SM}px;
}}
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
        "bg": "#12161B",
        "shell_bg": "#12161B",
        "sidebar_bg": "#161B21",
        "panel": "#1C232C",
        "panel_alt": "#202833",
        "panel_soft": "#283241",
        "panel_raised": "#242E3A",
        "surface": "#2D3947",
        "surface_hover": "#364453",
        "surface_pressed": "#3F4E60",
        "canvas_bg": "#101418",
        "canvas_stage": "#0D1116",
        "border": "#344150",
        "border_strong": "#425164",
        "focus_ring": "#4B9DFF",
        "text": "#F3F6FA",
        "text_muted": "#BCC7D4",
        "text_soft": "#93A1B2",
        "accent": "#4B9DFF",
        "accent_hover": "#78B5FF",
        "accent_soft": "#163451",
        "danger": "#FF6B5F",
        "success": "#46C98B",
        "warning": "#FFB84D",
        "selection": "#2B5F98",
        "selection_soft": "#1B2E46",
        "r_sm": 4,
        "r_md": 6,
        "r_lg": 8,
        "r_xl": 8,
        "r_2xl": 12,
        "r_3xl": 14,
        "space_xxs": 4,
        "space_xs": 4,
        "space_sm": 8,
        "space_md": 12,
        "space_lg": 16,
        "space_xl": 20,
        "space_2xl": 24,
        "pad_btn_v": 6,
        "pad_btn_h": 10,
        "pad_input_v": 6,
        "pad_input_h": 10,
        "h_tab_min": 28,
        "fs_display": 20,
        "fs_h1": 15,
        "fs_h2": 14,
        "fs_panel_title": 13,
        "fs_body": 13,
        "fs_body_sm": 12,
        "fs_caption": 12,
        "fs_micro": 11,
        "fw_regular": 400,
        "fw_medium": 500,
        "fw_semibold": 600,
        "fw_bold": 700,
        "icon_xs": 14,
        "icon_sm": 16,
        "icon_md": 18,
        "icon_lg": 20,
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
        "selection": "#D8E7F9",
        "selection_soft": "#EDF4FD",
        "r_sm": 4,
        "r_md": 6,
        "r_lg": 8,
        "r_xl": 8,
        "r_2xl": 12,
        "r_3xl": 14,
        "space_xxs": 4,
        "space_xs": 4,
        "space_sm": 8,
        "space_md": 12,
        "space_lg": 16,
        "space_xl": 20,
        "space_2xl": 24,
        "pad_btn_v": 6,
        "pad_btn_h": 10,
        "pad_input_v": 6,
        "pad_input_h": 10,
        "h_tab_min": 28,
        "fs_display": 20,
        "fs_h1": 15,
        "fs_h2": 14,
        "fs_panel_title": 13,
        "fs_body": 13,
        "fs_body_sm": 12,
        "fs_caption": 12,
        "fs_micro": 11,
        "fw_regular": 400,
        "fw_medium": 500,
        "fw_semibold": 600,
        "fw_bold": 700,
        "icon_xs": 14,
        "icon_sm": 16,
        "icon_md": 18,
        "icon_lg": 20,
    },
}


def _normalize_density(density="standard"):
    value = str(density or "standard").strip().lower()
    if value in {"roomy_plus", "roomy+", "plus", "spacious"}:
        return "roomy_plus"
    if value in {"roomy", "comfortable", "relaxed"}:
        return "roomy"
    return "standard"


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
    for key in ("fs_h2", "fs_panel_title", "fs_body", "fs_body_sm", "fs_caption", "fs_micro"):
        try:
            out[key] = int(out.get(key, 0)) + text_delta
        except Exception:
            pass
    for key in ("pad_btn_v", "pad_btn_h", "pad_input_v", "pad_input_h"):
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


def theme_tokens(mode="dark", density="standard"):
    """Return the active token map."""
    base = dict(_TOKENS["light" if mode == "light" else "dark"])
    return _density_adjusted_tokens(base, density)


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


def _apply_fluent_engineering_style(widget):
    """Reduce Fluent widget radii so embedded controls match the shell theme."""
    if not HAS_FLUENT or widget is None or not isinstance(widget, QWidget):
        return False

    style_kind = None
    custom_qss = ""
    if isinstance(widget, _FLUENT_BUTTON_TYPES):
        style_kind = "button"
        custom_qss = _FLUENT_BUTTON_RADIUS_QSS
    elif isinstance(widget, _FLUENT_LINE_EDIT_TYPES):
        style_kind = "line_edit"
        custom_qss = _FLUENT_LINE_EDIT_RADIUS_QSS
    elif isinstance(widget, _FLUENT_COMBO_BOX_TYPES):
        style_kind = "combo_box"
        custom_qss = _FLUENT_COMBO_BOX_RADIUS_QSS
    elif isinstance(widget, _FLUENT_SPIN_BOX_TYPES):
        style_kind = "spin_box"
        custom_qss = _FLUENT_SPIN_BOX_RADIUS_QSS

    if not style_kind:
        return False
    if widget.property(_FLUENT_STYLE_MARKER) == style_kind:
        return False

    set_fluent_custom_stylesheet(widget, custom_qss, custom_qss)
    widget.setProperty(_FLUENT_STYLE_MARKER, style_kind)
    return True


class _FluentEngineeringStyleManager(QObject):
    def refresh_all(self):
        if not HAS_FLUENT:
            return
        for widget in QApplication.allWidgets():
            _apply_fluent_engineering_style(widget)

    def eventFilter(self, obj, event):
        if HAS_FLUENT and isinstance(obj, QWidget) and event.type() in (QEvent.Polish, QEvent.Show):
            _apply_fluent_engineering_style(obj)
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


def _build_stylesheet(mode="dark", density="standard"):
    t = theme_tokens(mode, density=density)
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
    border-radius: {t['r_md']}px;
    padding: {t['pad_input_v']}px {t['pad_input_h']}px;
    selection-background-color: {t['selection']};
    font-size: {t['fs_body']}px;
    font-weight: {t['fw_regular']};
}}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QAbstractSpinBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border: 1px solid {t['focus_ring']};
    background-color: {t['panel_raised']};
}}

QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled, QAbstractSpinBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {{
    color: {t['text_soft']};
    background-color: {t['panel_alt']};
}}

QPushButton, QToolButton {{
    background-color: {t['panel_raised']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: {t['r_md']}px;
    padding: {t['pad_btn_v']}px {t['pad_btn_h']}px;
    font-size: {t['fs_body_sm']}px;
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
    background-color: {t['panel_alt']};
    border-color: {t['border']};
}}

QListView, QTreeView, QTableView, QListWidget, QTreeWidget, QTableWidget {{
    background-color: {t['panel_raised']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: {t['r_xl']}px;
    outline: none;
}}

QListView::item, QTreeView::item, QTableView::item, QListWidget::item, QTreeWidget::item {{
    padding: 6px 8px;
    min-height: 28px;
}}

QListView::item:hover, QTreeView::item:hover, QTableView::item:hover, QListWidget::item:hover, QTreeWidget::item:hover {{
    background-color: {t['surface_hover']};
}}

QListView::item:selected, QTreeView::item:selected, QTableView::item:selected, QListWidget::item:selected, QTreeWidget::item:selected {{
    background-color: {t['selection']};
    color: {t['text']};
}}

QListView::item:selected:!active, QTreeView::item:selected:!active, QTableView::item:selected:!active,
QListWidget::item:selected:!active, QTreeWidget::item:selected:!active, QTableWidget::item:selected:!active {{
    background-color: {t['selection_soft']};
    color: {t['text']};
}}

QListView::item:selected:hover, QTreeView::item:selected:hover, QTableView::item:selected:hover,
QListWidget::item:selected:hover, QTreeWidget::item:selected:hover, QTableWidget::item:selected:hover {{
    background-color: {t['selection']};
}}

QHeaderView::section {{
    background-color: {t['panel_alt']};
    color: {t['text_muted']};
    padding: 6px 8px;
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
    background-color: transparent;
    color: {t['text_muted']};
    padding: {t['space_xs']}px {t['space_sm']}px;
    margin-right: {t['space_xs']}px;
    min-height: {t['h_tab_min']}px;
    border: 1px solid transparent;
    border-radius: {t['r_md']}px;
}}

QTabBar::tab:selected {{
    background-color: {t['panel_raised']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-bottom-color: {t['border']};
}}

QTabBar::tab:hover:!selected {{
    background-color: {t['surface_hover']};
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

QMenu::separator {{
    height: 1px;
    background: {t['border']};
    margin: 6px 8px;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 12px;
    margin: 2px;
}}

QScrollBar::handle:vertical {{
    background: {t['border_strong']};
    min-height: 24px;
    border-radius: {t['r_sm']}px;
}}

QScrollBar::handle:vertical:hover {{
    background: {t['text_soft']};
}}

QScrollBar:horizontal {{
    background: transparent;
    height: 12px;
    margin: 2px;
}}

QScrollBar::handle:horizontal {{
    background: {t['border_strong']};
    min-width: 24px;
    border-radius: {t['r_sm']}px;
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
    font-size: {t['fs_body_sm']}px;
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
    border-radius: {t['r_md']}px;
}}

QFrame#property_panel_search_shell {{
    background-color: transparent;
    border: 1px solid {t['border']};
    border-radius: 0px;
}}

#property_panel_eyebrow,
#property_panel_header_eyebrow {{
    color: {t['accent_hover']};
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_semibold']};
}}

#property_panel_title {{
    color: {t['text']};
    font-size: {t['fs_h1']}px;
    font-weight: {t['fw_regular']};
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
    margin-top: {t['space_xs']}px;
    padding-top: {t['space_sm']}px;
    font-size: {t['fs_panel_title']}px;
    font-weight: {t['fw_semibold']};
}}

QGroupBox#inspector_collapsible_group::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: {t['space_xs']}px;
    color: {t['text_muted']};
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
    font-weight: {t['fw_semibold']};
}}

#workspace_command_title {{
    color: {t['text']};
    font-size: {t['fs_h2']}px;
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
}}

#workspace_hint_strip[panelTone="property"] {{
    background-color: {t['panel_soft']};
    border-color: {t['border']};
}}

#widget_browser_header[panelTone="components"] {{
    background-color: {t['panel']};
    border-color: {t['border']};
}}

#widget_browser_header_eyebrow {{
    color: {t['accent_hover']};
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_semibold']};
}}

#widget_browser_header_meta {{
    color: {t['text_muted']};
    font-size: {t['fs_body_sm']}px;
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
    padding: 2px 8px;
    text-align: left;
    min-height: 24px;
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

#workspace_nav_rail {{
    background-color: transparent;
    border: none;
    border-right: 1px solid {t['border']};
    padding: {t['space_xxs']}px {t['space_xs']}px;
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
    spacing: 2px;
    background: transparent;
    border: none;
}}

QToolBar#main_toolbar::separator {{
    background-color: {t['border']};
    width: 1px;
    margin: 2px 2px;
}}

QToolBar#main_toolbar QToolButton {{
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 0px;
    color: {t['text_muted']};
    padding: 2px 6px;
    min-height: 24px;
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
}}

QPushButton#workspace_mode_button {{
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 0px;
    color: {t['text_muted']};
    padding: 3px {t['space_sm']}px;
    min-width: 60px;
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

#editor_tabs_header {{
    background-color: {t['panel_raised']};
    border: 1px solid {t['border']};
    border-radius: 0px;
}}

#editor_tabs_eyebrow {{
    color: {t['accent_hover']};
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_semibold']};
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
    margin-left: 6px;
    margin-right: 6px;
}}

QToolButton[workspaceNav="true"] {{
    background-color: transparent;
    color: {t['text_muted']};
    border: 1px solid transparent;
    border-radius: 0px;
    font-size: {t['fs_body_sm']}px;
    font-weight: {t['fw_medium']};
    padding: 2px 0;
    min-width: 64px;
    max-width: 64px;
    min-height: 28px;
    max-height: 28px;
}}

QToolButton[workspaceNav="true"]:hover {{
    background-color: {t['surface_hover']};
    border-color: {t['border_strong']};
    color: {t['text']};
}}

QToolButton[workspaceNav="true"]:pressed {{
    background-color: {t['surface_pressed']};
}}

QToolButton[workspaceNav="true"]:checked {{
    background-color: {t['accent_soft']};
    color: {t['accent_hover']};
    border: 1px solid {t['accent']};
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
    min-height: 24px;
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

QFrame#property_panel_metric_card {{
    background-color: transparent;
    border: 1px solid {t['border']};
    border-radius: 0px;
}}

QFrame#property_panel_metric_card[metricTone="accent"] {{
    background-color: {t['selection_soft']};
    border-color: {t['accent']};
}}

QFrame#property_panel_metric_card[metricTone="success"] {{
    background-color: {t['selection_soft']};
    border-color: {t['success']};
}}

QFrame#property_panel_metric_card[metricTone="warning"] {{
    background-color: {t['accent_soft']};
    border-color: {t['warning']};
}}

QFrame#property_panel_metric_card[metricTone="danger"] {{
    background-color: {t['accent_soft']};
    border-color: {t['danger']};
}}

#property_panel_metric_label {{
    color: {t['text_soft']};
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_medium']};
}}

#property_panel_metric_value {{
    color: {t['text']};
    font-size: {t['fs_panel_title']}px;
    font-weight: {t['fw_semibold']};
}}

QToolButton#workspace_summary_indicator {{
    background-color: transparent;
    border: 1px solid {t['border']};
    border-radius: 0px;
    color: {t['text']};
    font-size: {t['fs_body_sm']}px;
    font-weight: {t['fw_medium']};
    padding: 4px {t['space_sm']}px;
    min-height: 28px;
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

#workspace_section_subtitle {{
    color: {t['text_muted']};
    font-size: {t['fs_body_sm']}px;
    font-weight: {t['fw_regular']};
}}

#workspace_empty_state {{
    color: {t['text_soft']};
    padding: 20px;
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
    font-weight: {t['fw_semibold']};
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
    background-color: {t['panel_alt']};
    border: 1px dashed {t['border']};
    border-radius: 0px;
}}

#resource_panel_shell {{
    background-color: transparent;
}}

#resource_panel_header {{
    background-color: {t['panel']};
    border: 1px solid {t['border']};
    border-radius: 0px;
}}

#resource_panel_eyebrow {{
    color: {t['accent_hover']};
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_semibold']};
}}

#resource_panel_title {{
    color: {t['text']};
    font-size: {t['fs_h1']}px;
    font-weight: {t['fw_regular']};
}}

#resource_panel_subtitle,
#resource_panel_status,
#resource_panel_summary {{
    color: {t['text_muted']};
    font-size: {t['fs_body_sm']}px;
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
    font-weight: {t['fw_semibold']};
}}

#resource_panel_metric_value {{
    color: {t['text']};
    font-size: {t['fs_body_sm']}px;
    font-weight: {t['fw_semibold']};
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
    min-height: 28px;
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
    min-height: 28px;
    padding: 6px 10px;
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
    min-height: 28px;
    padding: 6px 10px;
}}

QTableWidget#resource_panel_table QHeaderView::section {{
    background-color: {t['panel_soft']};
    color: {t['text_muted']};
    border: none;
    border-bottom: 1px solid {t['border']};
    padding: 8px;
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_semibold']};
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
    font-weight: {t['fw_semibold']};
}}

#project_dock_title {{
    color: {t['text']};
    font-size: {t['fs_h1']}px;
    font-weight: {t['fw_regular']};
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
    padding: 3px {t['space_sm']}px;
    min-height: 28px;
}}

QComboBox#project_dock_mode_combo:hover,
QPushButton#project_dock_add_page_button:hover {{
    background-color: {t['surface_hover']};
    border-color: {t['border_strong']};
    color: {t['text']};
}}

QPushButton#project_dock_add_page_button:disabled {{
    color: {t['text_soft']};
    border-color: {t['border']};
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
    font-weight: {t['fw_semibold']};
}}

#project_dock_metric_value {{
    color: {t['text']};
    font-size: {t['fs_body_sm']}px;
    font-weight: {t['fw_semibold']};
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
    font-weight: {t['fw_semibold']};
}}

#structure_header_meta,
#structure_panel_hint {{
    color: {t['text_muted']};
    font-size: {t['fs_body_sm']}px;
}}

#structure_panel_label {{
    color: {t['text']};
    font-size: {t['fs_panel_title']}px;
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
    padding: 3px {t['space_sm']}px;
    min-height: 28px;
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
    border-color: {t['border']};
}}

#diagnostics_header {{
    background-color: {t['panel']};
    border: 1px solid {t['border']};
    border-radius: 0px;
}}

#diagnostics_header[panelTone="diagnostics"] {{
    background-color: {t['panel']};
    border-color: {t['border']};
}}

#diagnostics_header_eyebrow {{
    color: {t['accent_hover']};
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_semibold']};
}}

#diagnostics_header_meta {{
    color: {t['text_muted']};
    font-size: {t['fs_body_sm']}px;
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
    padding: 2px {t['space_sm']}px;
    min-height: 26px;
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
    border-color: {t['border']};
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
    border-radius: 0px;
}}

#debug_panel_header[panelTone="runtime"] {{
    background-color: {t['panel']};
    border-color: {t['border']};
}}

#debug_panel_eyebrow {{
    color: {t['accent_hover']};
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_semibold']};
}}

#debug_panel_header_meta {{
    color: {t['text_muted']};
    font-size: {t['fs_body_sm']}px;
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
    padding: 2px {t['space_sm']}px;
    min-height: 26px;
}}

#debug_panel_controls_strip QPushButton:hover {{
    background-color: {t['surface_hover']};
    border-color: {t['border_strong']};
    color: {t['text']};
}}

#debug_panel_controls_strip QPushButton:disabled {{
    color: {t['text_soft']};
    border-color: {t['border']};
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
    border-radius: 0px;
}}

#history_panel_header[panelTone="history"] {{
    background-color: {t['panel']};
    border-color: {t['border']};
}}

#history_panel_eyebrow {{
    color: {t['accent_hover']};
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_semibold']};
}}

#history_panel_meta {{
    color: {t['text_muted']};
    font-size: {t['fs_body_sm']}px;
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
    border-radius: 0px;
}}

#animations_panel_header[panelTone="animations"] {{
    background-color: {t['panel']};
    border-color: {t['border']};
}}

#animations_panel_eyebrow {{
    color: {t['accent_hover']};
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_semibold']};
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
    padding: 2px {t['space_sm']}px;
    min-height: 26px;
}}

#animations_panel_actions_strip QPushButton:hover {{
    background-color: {t['surface_hover']};
    border-color: {t['border_strong']};
    color: {t['text']};
}}

#animations_panel_actions_strip QPushButton:disabled {{
    color: {t['text_soft']};
    border-color: {t['border']};
}}

QTableWidget#animations_panel_table {{
    background-color: {t['panel_alt']};
    border: 1px solid {t['border']};
    border-radius: 0px;
    padding: {t['space_xxs']}px;
}}

QGroupBox#animations_panel_detail_group {{
    background-color: transparent;
    border: none;
    border-radius: 0px;
    margin-top: 0px;
    padding-top: 0px;
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
    border-radius: 0px;
}}

#page_fields_eyebrow {{
    color: {t['accent_hover']};
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_semibold']};
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
    border-radius: 0px;
}}

#page_timers_eyebrow {{
    color: {t['accent_hover']};
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_semibold']};
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
    font-weight: {t['fw_semibold']};
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
    font-size: {t['fs_panel_title']}px;
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
    padding: 3px {t['space_sm']}px;
    min-height: 28px;
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
    border-color: {t['border']};
}}

#page_navigator_header {{
    background-color: {t['panel']};
    border: 1px solid {t['border']};
    border-radius: 0px;
}}

#page_navigator_eyebrow {{
    color: {t['accent_hover']};
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_semibold']};
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
    padding: 12px;
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
    padding: 2px;
}}

QLabel#page_navigator_thumb_label[startup="true"] {{
    border-color: {t['success']};
}}

QLabel#page_navigator_thumb_label[selected="true"] {{
    border-color: {t['accent']};
}}

#page_navigator_page_name {{
    color: {t['text']};
    font-size: {t['fs_body']}px;
    font-weight: {t['fw_semibold']};
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
    font-weight: {t['fw_semibold']};
}}

#app_selector_title {{
    color: {t['text']};
    font-size: {t['fs_display'] + 3}px;
    font-weight: {t['fw_regular']};
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
    font-weight: {t['fw_semibold']};
}}

#app_selector_metric_value,
#app_selector_status_value,
#app_selector_selection_value {{
    color: {t['text']};
    font-size: {t['fs_body_sm']}px;
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
    font-weight: {t['fw_semibold']};
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
    font-weight: {t['fw_semibold']};
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
    font-weight: {t['fw_semibold']};
}}

#resource_dialog_title {{
    color: {t['text']};
    font-size: {t['fs_display'] + 6}px;
    font-weight: {t['fw_regular']};
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
    font-weight: {t['fw_semibold']};
}}

#resource_dialog_metric_value {{
    color: {t['text']};
    font-size: {t['fs_body_sm']}px;
    font-weight: {t['fw_semibold']};
}}

#resource_dialog_summary {{
    color: {t['text_muted']};
    font-size: {t['fs_body_sm']}px;
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
    padding: 8px;
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_semibold']};
}}

#repo_health_header {{
    background-color: {t['panel']};
    border: 1px solid {t['border']};
    border-radius: 0px;
}}

#repo_health_eyebrow {{
    color: {t['accent_hover']};
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_semibold']};
}}

#repo_health_title {{
    color: {t['text']};
    font-size: {t['fs_display'] + 6}px;
    font-weight: {t['fw_regular']};
}}

#repo_health_subtitle,
#repo_health_summary_text,
#repo_health_overview_text {{
    color: {t['text_muted']};
    font-size: {t['fs_body_sm']}px;
}}

#repo_health_details_card,
#repo_health_tool_card {{
    background-color: transparent;
    border: none;
    border-radius: 0px;
}}

#repo_health_metric_card {{
    background-color: transparent;
    border: none;
    border-radius: 0px;
}}

#repo_health_metric_label {{
    color: {t['text_soft']};
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_semibold']};
}}

#repo_health_metric_value {{
    color: {t['text']};
    font-size: {t['fs_h2']}px;
    font-weight: {t['fw_semibold']};
}}

QTextEdit#repo_health_details {{
    background-color: {t['panel_alt']};
    border: 1px solid {t['border']};
    border-radius: 0px;
}}

#release_build_header {{
    background-color: {t['panel']};
    border: 1px solid {t['border']};
    border-radius: 0px;
}}

#release_profiles_header {{
    background-color: {t['panel']};
    border: 1px solid {t['border']};
    border-radius: 0px;
}}

#release_history_header {{
    background-color: {t['panel']};
    border: 1px solid {t['border']};
    border-radius: 0px;
}}

#release_build_eyebrow,
#release_profiles_eyebrow,
#release_history_eyebrow {{
    color: {t['accent_hover']};
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_semibold']};
}}

#release_build_title,
#release_profiles_title,
#release_history_title {{
    color: {t['text']};
    font-size: {t['fs_display'] + 6}px;
    font-weight: {t['fw_regular']};
}}

#release_build_subtitle,
#release_profiles_subtitle,
#release_history_subtitle {{
    color: {t['text_muted']};
    font-size: {t['fs_body']}px;
    font-weight: {t['fw_regular']};
}}

#release_build_card {{
    background-color: transparent;
    border: none;
    border-radius: 0px;
}}

#release_profiles_card {{
    background-color: transparent;
    border: none;
    border-radius: 0px;
}}

#release_history_card {{
    background-color: transparent;
    border: none;
    border-radius: 0px;
}}

#release_build_metric_card {{
    background-color: transparent;
    border: none;
    border-radius: 0px;
}}

#release_profiles_metric_card {{
    background-color: transparent;
    border: none;
    border-radius: 0px;
}}

#release_history_metric_card {{
    background-color: transparent;
    border: none;
    border-radius: 0px;
}}

#release_build_metric_label,
#release_profiles_metric_label,
#release_history_metric_label,
#release_history_field_label {{
    color: {t['text_soft']};
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_semibold']};
}}

#release_build_metric_value,
#release_profiles_metric_value,
#release_profiles_summary_value,
#release_history_metric_value,
#release_history_summary,
#release_history_stat_value,
#release_history_file_path,
#release_history_preview_label {{
    color: {t['text']};
    font-size: {t['fs_body_sm']}px;
    font-weight: {t['fw_semibold']};
}}

QListWidget#release_profiles_list,
QListWidget#release_profiles_list {{
    background-color: transparent;
    border: 1px solid {t['border']};
    border-radius: {t['r_md']}px;
}}

QListWidget#release_history_list {{
    background-color: {t['panel_alt']};
    border: 1px solid {t['border']};
    border-radius: 0px;
}}

QTextEdit#release_history_details,
QTextEdit#release_history_preview {{
    background-color: {t['panel_alt']};
    border: 1px solid {t['border']};
    border-radius: 0px;
}}

#new_project_header {{
    background-color: {t['panel']};
    border: 1px solid {t['border']};
    border-radius: 0px;
}}

#new_project_eyebrow {{
    color: {t['accent_hover']};
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_semibold']};
}}

#new_project_title {{
    color: {t['text']};
    font-size: {t['fs_display'] + 6}px;
    font-weight: {t['fw_regular']};
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
    font-weight: {t['fw_semibold']};
}}

#new_project_metric_value,
#new_project_summary_value {{
    color: {t['text']};
    font-size: {t['fs_body_sm']}px;
    font-weight: {t['fw_semibold']};
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
    font-weight: {t['fw_semibold']};
}}

#welcome_hero_title {{
    color: {t['text']};
    font-size: {t['fs_display'] + 4}px;
    font-weight: {t['fw_regular']};
}}

#welcome_hero_subtitle {{
    color: {t['text_muted']};
    font-size: {t['fs_h2']}px;
    font-weight: {t['fw_medium']};
}}

#welcome_hero_hint {{
    color: {t['text_soft']};
    font-size: {t['fs_body_sm']}px;
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
    font-weight: {t['fw_semibold']};
}}

#welcome_metric_value {{
    color: {t['text']};
    font-size: {t['fs_body_sm']}px;
    font-weight: {t['fw_semibold']};
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
    font-weight: {t['fw_semibold']};
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
    padding: 18px;
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
    font-size: {t['fs_body_sm']}px;
    font-weight: 600;
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
    padding: 2px 4px;
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
    font-size: {t['icon_sm']}px;
    padding: 0;
}}

#widget_browser_favorite_button:checked {{
    color: {t['warning']};
}}

#status_center_header[panelTone="status"] {{
    background-color: {t['panel']};
    border: 1px solid {t['border']};
    border-radius: 0px;
}}

#status_center_eyebrow {{
    color: {t['accent_hover']};
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_semibold']};
}}

#status_center_header_metrics_strip {{
    background-color: transparent;
    border: none;
    border-radius: 0px;
}}

#status_center_health,
#status_center_runtime {{
    background-color: transparent;
    border: none;
    border-radius: 0px;
}}

#status_center_metrics,
#status_center_actions {{
    background-color: transparent;
    border: none;
}}

#status_center_metric_card {{
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 0px;
}}

#status_center_metric_card:hover {{
    border-color: {t['accent_soft']};
    background-color: {t['surface_hover']};
}}

#status_center_metric_card:focus {{
    border-color: {t['accent']};
    background-color: {t['surface_hover']};
}}

#status_center_metric_value {{
    color: {t['text']};
    font-size: {t['fs_body']}px;
    font-weight: 600;
}}

#preview_header {{
    background-color: {t['panel_raised']};
    border: 1px solid {t['border']};
    border-radius: 0px;
}}

#preview_eyebrow {{
    color: {t['accent_hover']};
    font-size: {t['fs_caption']}px;
    font-weight: {t['fw_semibold']};
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
    font-size: {t['fs_h2']}px;
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
    font-size: {t['fs_body_sm']}px;
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

#status_center_health_row {{
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 0px;
}}

#status_center_health_row:hover {{
    border-color: {t['accent_soft']};
    background-color: {t['surface_hover']};
}}

#status_center_health_row:focus {{
    border-color: {t['accent']};
    background-color: {t['surface_hover']};
}}

#status_center_health_value {{
    color: {t['text']};
    font-size: {t['fs_body_sm']}px;
    font-weight: 600;
}}

QProgressBar#status_center_health_error_bar,
QProgressBar#status_center_health_warning_bar,
QProgressBar#status_center_health_info_bar {{
    background-color: {t['panel_alt']};
    border: 1px solid {t['border']};
    border-radius: 0px;
    min-height: 8px;
    max-height: 8px;
}}

QProgressBar#status_center_health_error_bar::chunk {{
    background-color: {t['danger']};
    border-radius: 0px;
}}

QProgressBar#status_center_health_warning_bar::chunk {{
    background-color: {t['warning']};
    border-radius: 0px;
}}

QProgressBar#status_center_health_info_bar::chunk {{
    background-color: {t['accent']};
    border-radius: 0px;
}}

#status_center_runtime:hover {{
    border: 1px solid {t['accent_soft']};
    background-color: {t['panel_soft']};
}}

#status_center_runtime:focus {{
    border: 1px solid {t['accent']};
    background-color: {t['panel_soft']};
}}
"""


def apply_theme(app: QApplication, mode="dark", density="standard"):
    """Apply the requested theme mode and density profile."""
    mode = "light" if mode == "light" else "dark"
    density = _normalize_density(density)
    if HAS_FLUENT:
        try:
            setTheme(Theme.LIGHT if mode == "light" else Theme.DARK)
        except RuntimeError as exc:
            # qfluentwidgets keeps a process-global QConfig that can outlive a
            # prior QApplication in tests; keep applying Designer theming even
            # if Fluent's theme dispatcher is already invalid.
            if "QConfig" not in str(exc):
                raise
    app.setProperty("designer_theme_mode", mode)
    app.setProperty("designer_ui_density", density)
    app.setStyleSheet(_build_stylesheet(mode, density=density))
    manager = _ensure_fluent_engineering_style_manager(app)
    if manager is not None:
        manager.refresh_all()
