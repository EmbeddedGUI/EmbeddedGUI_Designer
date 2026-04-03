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


_ENGINEERING_RADIUS_SM = 1
_ENGINEERING_RADIUS_MD = 2
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
        "bg": "#1C1C1E",
        "panel": "#2C2C2E",
        "panel_alt": "#3A3A3C",
        "panel_soft": "#45454C",
        "surface": "#323235",
        "surface_hover": "#3D3D41",
        "surface_pressed": "#4A4A50",
        "border": "#5A5A63",
        "border_strong": "#6A6A74",
        "text": "#F2F2F7",
        "text_muted": "#D0D0D8",
        "text_soft": "#ACACB6",
        "accent": "#0A84FF",
        "accent_hover": "#6AB1FF",
        "accent_soft": "#1A436D",
        "danger": "#FF453A",
        "success": "#30D158",
        "warning": "#FFD60A",
        "selection": "#2E5EA7",
        "selection_soft": "#2A4262",
        "r_sm": 1,
        "r_md": 2,
        "r_lg": 2,
        "r_xl": 2,
        "r_2xl": 2,
        "r_3xl": 2,
        "space_xxs": 2,
        "space_xs": 4,
        "space_sm": 8,
        "space_md": 12,
        "space_lg": 16,
        "space_xl": 20,
        "space_2xl": 24,
        "pad_btn_v": 8,
        "pad_btn_h": 14,
        "pad_input_v": 7,
        "pad_input_h": 11,
        "h_tab_min": 28,
        "fs_display": 24,
        "fs_h1": 18,
        "fs_h2": 16,
        "fs_panel_title": 14,
        "fs_body": 14,
        "fs_body_sm": 13,
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
        "bg": "#F5F5F7",
        "panel": "#FFFFFF",
        "panel_alt": "#F2F3F5",
        "panel_soft": "#E9EAED",
        "surface": "#F3F4F6",
        "surface_hover": "#E8F0FA",
        "surface_pressed": "#E1E3E8",
        "border": "#E0E1E6",
        "border_strong": "#C7C9D1",
        "text": "#1C1C1E",
        "text_muted": "#5B5C61",
        "text_soft": "#8E8E93",
        "accent": "#0A84FF",
        "accent_hover": "#2F8CFF",
        "accent_soft": "#D6E7FF",
        "danger": "#D92D20",
        "success": "#1F8F4C",
        "warning": "#A56B00",
        "selection": "#D6E7FF",
        "selection_soft": "#EEF5FF",
        "r_sm": 1,
        "r_md": 2,
        "r_lg": 2,
        "r_xl": 2,
        "r_2xl": 2,
        "r_3xl": 2,
        "space_xxs": 2,
        "space_xs": 4,
        "space_sm": 8,
        "space_md": 12,
        "space_lg": 16,
        "space_xl": 20,
        "space_2xl": 24,
        "pad_btn_v": 8,
        "pad_btn_h": 14,
        "pad_input_v": 7,
        "pad_input_h": 11,
        "h_tab_min": 28,
        "fs_display": 24,
        "fs_h1": 18,
        "fs_h2": 16,
        "fs_panel_title": 14,
        "fs_body": 14,
        "fs_body_sm": 13,
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
    background-color: {t['bg']};
    color: {t['text']};
}}

QWidget {{
    background-color: {t['bg']};
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
    background-color: {t['panel']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: {t['r_md']}px;
    padding: {t['pad_input_v']}px {t['pad_input_h']}px;
    selection-background-color: {t['selection']};
    font-size: {t['fs_body']}px;
    font-weight: {t['fw_regular']};
}}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QAbstractSpinBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border: 1px solid {t['accent']};
    background-color: {t['panel']};
}}

QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled, QAbstractSpinBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {{
    color: {t['text_soft']};
    background-color: {t['panel_alt']};
}}

QPushButton, QToolButton {{
    background-color: {t['surface']};
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
    background-color: {t['panel']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: {t['r_xl']}px;
    outline: none;
}}

QListView::item, QTreeView::item, QTableView::item, QListWidget::item, QTreeWidget::item {{
    padding: 7px 9px;
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
    padding: 8px 10px;
    border: none;
    border-right: 1px solid {t['border']};
    border-bottom: 1px solid {t['border']};
}}

QTabWidget::pane {{
    border: 1px solid {t['border']};
    border-radius: {t['r_xl']}px;
    background-color: {t['panel']};
    top: -1px;
}}

QTabBar::tab {{
    background-color: transparent;
    color: {t['text_muted']};
    padding: {t['space_sm']}px {t['space_md']}px;
    margin-right: {t['space_sm']}px;
    min-height: {t['h_tab_min']}px;
    border: 1px solid transparent;
    border-bottom: none;
    border-top-left-radius: {t['r_md']}px;
    border-top-right-radius: {t['r_md']}px;
}}

QTabBar::tab:selected {{
    background-color: {t['panel']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-bottom-color: {t['panel']};
    margin-bottom: -1px;
}}

QTabBar::tab:hover:!selected {{
    background-color: {t['surface_hover']};
}}

QMenuBar {{
    background-color: {t['panel']};
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
    background-color: {t['panel']};
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
    background-color: {t['panel']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: {t['r_md']}px;
    padding: {t['pad_input_v']}px {t['space_sm']}px;
}}

QStatusBar {{
    background-color: {t['panel']};
    color: {t['text_muted']};
    border-top: 1px solid {t['border']};
}}

QGroupBox {{
    background-color: {t['panel']};
    border: 1px solid {t['border']};
    border-radius: {t['r_xl']}px;
    margin-top: {t['space_lg']}px;
    padding-top: {t['space_md']}px;
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

QScrollArea#property_panel_scroll {{
    background-color: transparent;
    border: none;
}}

QGroupBox#inspector_collapsible_group {{
    border-radius: {t['r_md']}px;
    margin-top: {t['space_sm']}px;
    padding-top: {t['space_md']}px;
    font-size: {t['fs_panel_title']}px;
    font-weight: {t['fw_semibold']};
}}

QGroupBox#inspector_collapsible_group::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: {t['space_sm']}px;
    color: {t['text']};
}}

#workspace_command_bar,
#workspace_panel_header,
#workspace_hint_strip,
#widget_browser_header,
#workspace_bottom_header {{
    background-color: {t['panel']};
    border: 1px solid {t['border']};
    border-radius: {t['r_xl']}px;
}}

#workspace_command_bar {{
    background-color: {t['panel']};
    border-color: {t['border_strong']};
}}

#workspace_hint_strip {{
    background-color: {t['panel_alt']};
}}

QPushButton#project_workspace_view_button {{
    background-color: {t['panel_alt']};
    border: 1px solid {t['border']};
    border-radius: {t['r_md']}px;
    color: {t['text_muted']};
    font-size: {t['fs_body_sm']}px;
    padding: 9px 12px;
    text-align: left;
    min-height: 46px;
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
    background-color: {t['panel']};
    border: 1px solid {t['border']};
    border-radius: {t['r_xl']}px;
}}

#workspace_nav_rail {{
    background-color: transparent;
    border: none;
    border-right: 1px solid {t['border']};
    padding: {t['space_xs']}px {t['space_xs']}px;
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
    border: none;
    border-radius: {t['r_md']}px;
    font-size: {t['fs_body_sm']}px;
    padding: 8px 8px;
    min-height: 32px;
}}

QToolButton[workspaceNav="true"]:hover {{
    background-color: {t['surface_hover']};
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
    background-color: {t['panel_soft']};
    border: 1px solid {t['border']};
    border-radius: {t['r_md']}px;
    color: {t['text_muted']};
    padding: {t['space_xs']}px {t['space_sm']}px;
}}

QToolButton#workspace_status_chip {{
    background-color: {t['panel_soft']};
    border: 1px solid {t['border']};
    border-radius: {t['r_md']}px;
    color: {t['text_muted']};
    font-size: {t['fs_body_sm']}px;
    padding: {t['space_xs']}px {t['space_sm']}px;
    min-height: 28px;
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
    background-color: {t['accent_soft']};
    color: {t['accent_hover']};
    border-color: {t['accent']};
}}

#workspace_status_chip[chipTone="success"] {{
    background-color: {t['panel_soft']};
    color: {t['success']};
    border-color: {t['success']};
}}

#workspace_status_chip[chipTone="warning"] {{
    background-color: {t['panel_soft']};
    color: {t['warning']};
    border-color: {t['warning']};
}}

#workspace_status_chip[chipTone="danger"] {{
    background-color: {t['panel_soft']};
    color: {t['danger']};
    border-color: {t['danger']};
}}

#workspace_section_title {{
    color: {t['text']};
    font-size: {t['fs_h2']}px;
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

#property_panel_empty_state {{
    background-color: {t['panel_alt']};
    border: 1px dashed {t['border']};
    border-radius: {t['r_md']}px;
}}

#welcome_recent_empty {{
    padding: 4px 0 0 0;
}}

#widget_browser_categories {{
    background-color: {t['panel']};
    border: 1px solid {t['border']};
    border-radius: {t['r_xl']}px;
}}

#widget_browser_tags {{
    background-color: transparent;
    border: none;
    border-radius: 0;
}}

#widget_browser_organize {{
    background-color: transparent;
    border: none;
    border-radius: 0;
}}

#widget_browser_lanes {{
    background-color: transparent;
    border: none;
    border-radius: 0;
}}

QToolButton#widget_browser_lane {{
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: {t['r_md']}px;
    color: {t['text_muted']};
    font-size: {t['fs_body_sm']}px;
    padding: 7px 9px;
    min-height: 32px;
    text-align: left;
}}

QToolButton#widget_browser_lane:hover {{
    background-color: {t['surface_hover']};
    border-color: {t['border']};
    color: {t['text']};
}}

QToolButton#widget_browser_lane:checked {{
    background-color: {t['accent_soft']};
    border-color: {t['accent']};
    color: {t['accent_hover']};
}}

QToolButton#widget_browser_lane[emptyLane="true"] {{
    color: {t['text_soft']};
}}

QToolButton#widget_browser_sort_button {{
    background-color: {t['panel_alt']};
    border: 1px solid {t['border']};
    border-radius: {t['r_md']}px;
    color: {t['text_muted']};
    font-size: {t['fs_body_sm']}px;
    padding: 4px 9px;
}}

QToolButton#widget_browser_sort_button:hover {{
    background-color: {t['surface_hover']};
    border-color: {t['border_strong']};
    color: {t['text']};
}}

QToolButton#widget_browser_sort_button:checked {{
    background-color: {t['accent_soft']};
    border-color: {t['accent']};
    color: {t['accent_hover']};
}}

QToolButton#widget_browser_complexity_button {{
    background-color: {t['panel_soft']};
    border: 1px solid {t['border']};
    border-radius: {t['r_md']}px;
    color: {t['text_muted']};
    font-size: {t['fs_body_sm']}px;
    padding: 4px 9px;
    min-height: 26px;
}}

QToolButton#widget_browser_complexity_button:hover {{
    background-color: {t['surface_hover']};
    border-color: {t['border_strong']};
    color: {t['text']};
}}

QToolButton#widget_browser_complexity_button:checked {{
    background-color: {t['accent_soft']};
    border-color: {t['accent']};
    color: {t['accent_hover']};
}}

QToolButton#widget_browser_complexity_button[level="basic"]:checked {{
    border-color: {t['success']};
    color: {t['success']};
}}

QToolButton#widget_browser_complexity_button[level="intermediate"]:checked {{
    border-color: {t['warning']};
    color: {t['warning']};
}}

QToolButton#widget_browser_complexity_button[level="advanced"]:checked {{
    border-color: {t['danger']};
    color: {t['danger']};
}}

QToolButton#widget_browser_tag {{
    background-color: {t['panel_soft']};
    border: 1px solid {t['border']};
    color: {t['text_muted']};
    border-radius: {t['r_md']}px;
    font-size: {t['fs_body_sm']}px;
    padding: 4px 9px;
    min-height: 26px;
}}

QToolButton#widget_browser_tag:hover {{
    background-color: {t['surface_hover']};
    border-color: {t['border_strong']};
}}

QToolButton#widget_browser_tag:checked {{
    background-color: {t['accent_soft']};
    color: {t['accent_hover']};
    border-color: {t['accent']};
}}

#widget_browser_card {{
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: {t['r_md']}px;
}}

#widget_browser_group_header {{
    background-color: transparent;
    border: none;
    border-radius: 0;
}}

#widget_browser_group_title {{
    color: {t['text_muted']};
    font-size: {t['fs_caption']}px;
    font-weight: 600;
}}

#widget_browser_stats {{
    color: {t['text_soft']};
    font-size: {t['fs_caption']}px;
}}

#widget_browser_card:hover {{
    border-color: {t['border']};
    background-color: {t['surface_hover']};
}}

#widget_browser_card[selected="true"] {{
    border: 1px solid {t['accent']};
    background-color: {t['accent_soft']};
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

QPushButton#widget_browser_insert_button {{
    background-color: {t['panel_alt']};
    border: 1px solid {t['border']};
    border-radius: {t['r_md']}px;
    color: {t['text_muted']};
    font-size: {t['fs_body_sm']}px;
    padding: 4px 9px;
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

#status_center_header,
#status_center_health,
#status_center_runtime {{
    background-color: {t['panel']};
    border: 1px solid {t['border']};
    border-radius: {t['r_xl']}px;
}}

#status_center_metrics,
#status_center_actions {{
    background-color: transparent;
    border: none;
}}

#status_center_metric_card {{
    background-color: {t['panel_alt']};
    border: 1px solid transparent;
    border-radius: {t['r_md']}px;
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

#status_center_health_row {{
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: {t['r_md']}px;
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
    border-radius: {t['r_sm']}px;
    min-height: 10px;
    max-height: 10px;
}}

QProgressBar#status_center_health_error_bar::chunk {{
    background-color: {t['danger']};
    border-radius: {t['r_sm']}px;
}}

QProgressBar#status_center_health_warning_bar::chunk {{
    background-color: {t['warning']};
    border-radius: {t['r_sm']}px;
}}

QProgressBar#status_center_health_info_bar::chunk {{
    background-color: {t['accent']};
    border-radius: {t['r_sm']}px;
}}

#status_center_runtime:hover {{
    border-color: {t['accent_soft']};
    background-color: {t['panel_alt']};
}}

#status_center_runtime:focus {{
    border-color: {t['accent']};
    background-color: {t['panel_alt']};
}}
"""


def apply_theme(app: QApplication, mode="dark", density="standard"):
    """Apply the requested theme mode and density profile."""
    mode = "light" if mode == "light" else "dark"
    density = _normalize_density(density)
    if HAS_FLUENT:
        setTheme(Theme.LIGHT if mode == "light" else Theme.DARK)
    app.setProperty("designer_theme_mode", mode)
    app.setProperty("designer_ui_density", density)
    app.setStyleSheet(_build_stylesheet(mode, density=density))
    manager = _ensure_fluent_engineering_style_manager(app)
    if manager is not None:
        manager.refresh_all()
