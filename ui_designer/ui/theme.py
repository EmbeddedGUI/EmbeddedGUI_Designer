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
        "bg": "#0F141B",
        "panel": "#16202B",
        "panel_alt": "#1B2735",
        "panel_soft": "#223041",
        "surface": "#1F2C3A",
        "surface_hover": "#28384A",
        "surface_pressed": "#304257",
        "border": "#314355",
        "border_strong": "#3C5168",
        "text": "#E8EEF8",
        "text_muted": "#97A8BC",
        "text_soft": "#70849B",
        "accent": "#63A5FF",
        "accent_hover": "#7EB4FF",
        "accent_soft": "#163861",
        "danger": "#FF7B72",
        "success": "#4CC38A",
        "warning": "#F2C572",
        "selection": "#2D67A9",
        "selection_soft": "#14314F",
    },
    "light": {
        "bg": "#F4F8FC",
        "panel": "#FFFFFF",
        "panel_alt": "#F7FAFD",
        "panel_soft": "#EDF3FA",
        "surface": "#F3F7FB",
        "surface_hover": "#E8F0FA",
        "surface_pressed": "#DCE8F6",
        "border": "#D5E0EB",
        "border_strong": "#BCCBDA",
        "text": "#1D2630",
        "text_muted": "#617185",
        "text_soft": "#7A8CA1",
        "accent": "#1E6FD9",
        "accent_hover": "#2D7AE2",
        "accent_soft": "#DCEAFD",
        "danger": "#BE4B3F",
        "success": "#22804D",
        "warning": "#A77000",
        "selection": "#CFE4FF",
        "selection_soft": "#E7F1FF",
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

QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox, QSpinBox, QDoubleSpinBox, QComboBox {{
    background-color: {t['panel']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: 8px;
    padding: 6px 8px;
    selection-background-color: {t['selection']};
}}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QAbstractSpinBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border: 1px solid {t['accent']};
}}

QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled, QAbstractSpinBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {{
    color: {t['text_soft']};
    background-color: {t['panel_alt']};
}}

QPushButton, QToolButton {{
    background-color: {t['panel']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: 9px;
    padding: 6px 12px;
}}

QPushButton:hover, QToolButton:hover {{
    background-color: {t['surface_hover']};
    border-color: {t['border_strong']};
}}

QPushButton:pressed, QToolButton:pressed {{
    background-color: {t['surface_pressed']};
}}

QPushButton:checked {{
    background-color: {t['accent_soft']};
    border-color: {t['accent']};
}}

QPushButton:disabled, QToolButton:disabled {{
    color: {t['text_soft']};
    background-color: {t['panel_alt']};
}}

QListView, QTreeView, QTableView, QListWidget, QTreeWidget, QTableWidget {{
    background-color: {t['panel']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: 10px;
    outline: none;
}}

QListView::item, QTreeView::item, QTableView::item, QListWidget::item, QTreeWidget::item {{
    padding: 5px 6px;
}}

QListView::item:hover, QTreeView::item:hover, QTableView::item:hover, QListWidget::item:hover, QTreeWidget::item:hover {{
    background-color: {t['surface_hover']};
}}

QListView::item:selected, QTreeView::item:selected, QTableView::item:selected, QListWidget::item:selected, QTreeWidget::item:selected {{
    background-color: {t['selection']};
    color: {t['text']};
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
    border-radius: 12px;
    background-color: {t['panel']};
    top: -1px;
}}

QTabBar::tab {{
    background-color: transparent;
    color: {t['text_muted']};
    padding: 8px 14px;
    margin-right: 4px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
}}

QTabBar::tab:selected {{
    background-color: {t['panel']};
    color: {t['text']};
}}

QMenuBar {{
    background-color: {t['panel']};
    color: {t['text']};
    border-bottom: 1px solid {t['border']};
}}

QMenuBar::item {{
    padding: 6px 10px;
    background: transparent;
}}

QMenuBar::item:selected {{
    background-color: {t['surface_hover']};
}}

QMenu {{
    background-color: {t['panel']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: 10px;
}}

QMenu::item {{
    padding: 7px 24px 7px 12px;
}}

QMenu::item:selected {{
    background-color: {t['selection']};
}}

QMenu::separator {{
    height: 1px;
    background: {t['border']};
    margin: 5px 8px;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 12px;
    margin: 2px;
}}

QScrollBar::handle:vertical {{
    background: {t['border_strong']};
    min-height: 24px;
    border-radius: 6px;
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
    border-radius: 6px;
}}

QToolTip {{
    background-color: {t['panel']};
    color: {t['text']};
    border: 1px solid {t['border']};
    padding: 6px 8px;
}}

QStatusBar {{
    background-color: {t['panel']};
    color: {t['text_muted']};
    border-top: 1px solid {t['border']};
}}

QGroupBox {{
    background-color: {t['panel']};
    border: 1px solid {t['border']};
    border-radius: 12px;
    margin-top: 18px;
    padding-top: 10px;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    top: 0px;
    color: {t['text_muted']};
    padding: 0 6px;
}}

#workspace_command_bar,
#workspace_panel_header,
#widget_browser_header,
#workspace_bottom_header {{
    background-color: {t['panel']};
    border: 1px solid {t['border']};
    border-radius: 14px;
}}

QPushButton#project_workspace_view_button {{
    background-color: {t['panel_alt']};
    border: 1px solid {t['border']};
    border-radius: 10px;
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

#workspace_shell, #workspace_center_shell, #workspace_right_shell, #workspace_bottom_shell, #workspace_left_shell {{
    background-color: transparent;
}}

#workspace_nav_rail {{
    background-color: {t['panel']};
    border: 1px solid {t['border']};
    border-radius: 16px;
}}

QToolButton[workspaceNav="true"] {{
    background-color: transparent;
    color: {t['text_muted']};
    border: none;
    border-radius: 12px;
    padding: 10px 6px;
}}

QToolButton[workspaceNav="true"]:hover {{
    background-color: {t['surface_hover']};
    color: {t['text']};
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
    padding: 5px 10px;
}}

QToolButton#workspace_status_chip {{
    background-color: {t['panel_soft']};
    border: 1px solid {t['border']};
    border-radius: 999px;
    color: {t['text_muted']};
    padding: 5px 10px;
}}

QToolButton#workspace_status_chip:hover {{
    background-color: {t['surface_hover']};
    border-color: {t['border_strong']};
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
    font-size: 15px;
    font-weight: 600;
}}

#workspace_section_subtitle {{
    color: {t['text_muted']};
    font-size: 12px;
}}

#workspace_empty_state {{
    color: {t['text_soft']};
    padding: 20px;
}}

#widget_browser_categories {{
    background-color: {t['panel']};
    border: 1px solid {t['border']};
    border-radius: 14px;
}}

#widget_browser_tags {{
    background-color: {t['panel']};
    border: 1px solid {t['border']};
    border-radius: 12px;
}}

#widget_browser_lanes {{
    background-color: {t['panel']};
    border: 1px solid {t['border']};
    border-radius: 12px;
}}

QToolButton#widget_browser_lane {{
    background-color: {t['panel_alt']};
    border: 1px solid {t['border']};
    border-radius: 10px;
    color: {t['text_muted']};
    padding: 8px 10px;
    text-align: left;
}}

QToolButton#widget_browser_lane:hover {{
    background-color: {t['surface_hover']};
    border-color: {t['border_strong']};
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
    background-color: {t['panel']};
    border: 1px solid {t['border']};
    border-radius: 16px;
}}

#widget_browser_card:hover {{
    border-color: {t['border_strong']};
    background-color: {t['panel_alt']};
}}

#widget_browser_card[selected="true"] {{
    border: 1px solid {t['accent']};
    background-color: {t['accent_soft']};
}}

#widget_browser_card_title {{
    font-size: 14px;
    font-weight: 600;
    color: {t['text']};
}}

#widget_browser_card_meta {{
    color: {t['text_muted']};
    font-size: 11px;
}}

#widget_browser_keywords {{
    color: {t['text_soft']};
    font-size: 11px;
}}

#widget_browser_card_chip {{
    background-color: {t['panel_soft']};
    border: 1px solid {t['border']};
    border-radius: 999px;
    color: {t['text_muted']};
    padding: 2px 8px;
    font-size: 10px;
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

#widget_browser_preview {{
    background-color: transparent;
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

#status_center_metric_value {{
    color: {t['text']};
    font-size: 14px;
    font-weight: 600;
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
"""


def apply_theme(app: QApplication, mode="dark"):
    """Apply the requested theme mode."""
    mode = "light" if mode == "light" else "dark"
    if HAS_FLUENT:
        setTheme(Theme.LIGHT if mode == "light" else Theme.DARK)
    app.setProperty("designer_theme_mode", mode)
    app.setStyleSheet(_build_stylesheet(mode))
