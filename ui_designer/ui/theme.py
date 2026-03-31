"""Token-driven application theme for EmbeddedGUI Designer."""

from __future__ import annotations

from PyQt5.QtWidgets import QApplication

try:
    from qfluentwidgets import Theme, setTheme

    HAS_FLUENT = True
except ImportError:
    HAS_FLUENT = False


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
        "r_sm": 6,
        "r_md": 8,
        "r_lg": 10,
        "r_xl": 12,
        "r_2xl": 14,
        "r_3xl": 16,
        "space_xs": 4,
        "space_sm": 8,
        "space_md": 12,
        "space_lg": 16,
        "pad_btn_v": 7,
        "pad_btn_h": 13,
        "pad_input_v": 6,
        "pad_input_h": 10,
        "h_tab_min": 28,
        "fs_panel_title": 13,
        "fs_caption": 11,
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
        "r_sm": 6,
        "r_md": 8,
        "r_lg": 10,
        "r_xl": 12,
        "r_2xl": 14,
        "r_3xl": 16,
        "space_xs": 4,
        "space_sm": 8,
        "space_md": 12,
        "space_lg": 16,
        "pad_btn_v": 7,
        "pad_btn_h": 13,
        "pad_input_v": 6,
        "pad_input_h": 10,
        "h_tab_min": 28,
        "fs_panel_title": 13,
        "fs_caption": 11,
    },
}


def theme_tokens(mode="dark"):
    """Return the active token map."""
    return dict(_TOKENS["light" if mode == "light" else "dark"])


def _build_stylesheet(mode="dark"):
    t = theme_tokens(mode)
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
}}

QLabel[hintTone="muted"] {{
    color: {t['text_soft']};
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
    padding: 6px 8px;
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
    font-weight: 600;
}}

QGroupBox#inspector_collapsible_group::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: {t['space_sm']}px;
    color: {t['text']};
}}

#workspace_command_bar,
#workspace_panel_header,
#widget_browser_header,
#workspace_bottom_header {{
    background-color: {t['panel']};
    border: 1px solid {t['border']};
    border-radius: {t['r_xl']}px;
}}

#workspace_command_bar {{
    background-color: {t['panel_alt']};
}}

QPushButton#project_workspace_view_button {{
    background-color: {t['panel_alt']};
    border: 1px solid {t['border']};
    border-radius: {t['r_md']}px;
    color: {t['text_muted']};
    padding: 8px 10px;
    text-align: left;
    min-height: 42px;
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
    background-color: {t['panel_alt']};
    border: 1px solid {t['border']};
    border-radius: {t['r_xl']}px;
}}

#workspace_nav_rail {{
    background-color: transparent;
    border: none;
    border-right: 1px solid {t['border']};
    padding: {t['space_sm']}px {t['space_xs']}px;
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
    padding: 9px 6px;
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
    border-radius: 999px;
    color: {t['text_muted']};
    padding: {t['space_xs']}px {t['space_sm']}px;
}}

QToolButton#workspace_status_chip {{
    background-color: {t['panel_soft']};
    border: 1px solid {t['border']};
    border-radius: 999px;
    color: {t['text_muted']};
    padding: {t['space_xs']}px {t['space_sm']}px;
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
    font-size: {t['fs_panel_title']}px;
    font-weight: 600;
}}

#workspace_section_subtitle {{
    color: {t['text_muted']};
    font-size: {t['fs_caption']}px;
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
    border-radius: 14px;
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
    border-radius: 8px;
    color: {t['text_muted']};
    padding: 6px 8px;
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
    border-radius: 8px;
    color: {t['text_muted']};
    padding: 4px 10px;
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
    border-radius: 999px;
    color: {t['text_muted']};
    padding: 3px 10px;
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
    border-radius: 999px;
    padding: 4px 10px;
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
    border-radius: 8px;
}}

#widget_browser_group_header {{
    background-color: transparent;
    border: none;
    border-radius: 0;
}}

#widget_browser_group_title {{
    color: {t['text_muted']};
    font-size: 11px;
    font-weight: 600;
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
    font-size: 12px;
    font-weight: 600;
    color: {t['text']};
}}

#widget_browser_card_meta {{
    color: {t['text_soft']};
    font-size: 10px;
}}

QPushButton#widget_browser_insert_button {{
    background-color: {t['panel_alt']};
    border: 1px solid {t['border']};
    border-radius: 8px;
    color: {t['text_muted']};
    padding: 2px 8px;
}}

QPushButton#widget_browser_insert_button:hover {{
    background-color: {t['surface_hover']};
    border-color: {t['border_strong']};
    color: {t['text']};
}}

QPushButton#widget_browser_insert_button:pressed {{
    background-color: {t['panel_soft']};
}}

#widget_browser_card_chip {{
    background-color: {t['panel_soft']};
    border: 1px solid {t['border']};
    border-radius: 999px;
    color: {t['text_muted']};
    padding: 2px 4px;
    font-size: 8px;
}}

#widget_browser_card_chip[chipTone="accent"] {{
    background-color: {t['accent_soft']};
    color: {t['accent_hover']};
    border-color: {t['accent']};
}}

#widget_browser_card_chip[chipTone="success"] {{
    color: {t['success']};
    border-color: {t['success']};
}}

#widget_browser_card_chip[chipTone="warning"] {{
    color: {t['warning']};
    border-color: {t['warning']};
}}

#widget_browser_card_chip[chipTone="danger"] {{
    color: {t['danger']};
    border-color: {t['danger']};
}}

#widget_browser_favorite_button {{
    border: none;
    background: transparent;
    color: {t['text_soft']};
    font-size: 16px;
    padding: 0;
}}

#widget_browser_favorite_button:checked {{
    color: {t['warning']};
}}

#status_center_header,
#status_center_metrics,
#status_center_health,
#status_center_actions,
#status_center_runtime {{
    background-color: {t['panel']};
    border: 1px solid {t['border']};
    border-radius: 14px;
}}

#status_center_metric_card {{
    background-color: {t['panel_alt']};
    border: 1px solid {t['border']};
    border-radius: 10px;
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
    font-size: 14px;
    font-weight: 600;
}}

#status_center_health_row {{
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 10px;
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
    font-size: 12px;
    font-weight: 600;
}}

QProgressBar#status_center_health_error_bar,
QProgressBar#status_center_health_warning_bar,
QProgressBar#status_center_health_info_bar {{
    background-color: {t['panel_alt']};
    border: 1px solid {t['border']};
    border-radius: 5px;
    min-height: 10px;
    max-height: 10px;
}}

QProgressBar#status_center_health_error_bar::chunk {{
    background-color: {t['danger']};
    border-radius: 4px;
}}

QProgressBar#status_center_health_warning_bar::chunk {{
    background-color: {t['warning']};
    border-radius: 4px;
}}

QProgressBar#status_center_health_info_bar::chunk {{
    background-color: {t['accent']};
    border-radius: 4px;
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


def apply_theme(app: QApplication, mode="dark"):
    """Apply the requested theme mode."""
    mode = "light" if mode == "light" else "dark"
    if HAS_FLUENT:
        setTheme(Theme.LIGHT if mode == "light" else Theme.DARK)
    app.setProperty("designer_theme_mode", mode)
    app.setStyleSheet(_build_stylesheet(mode))
