import pytest
from PyQt5.QtWidgets import QApplication

from ui_designer.ui.iconography import semantic_icon_keys
from ui_designer.ui.theme import (
    _build_stylesheet,
    _ensure_fluent_engineering_style_manager,
    theme_tokens,
)

try:
    from qfluentwidgets import ComboBox, PushButton, SearchLineEdit, SpinBox

    HAS_FLUENT = True
except ImportError:
    HAS_FLUENT = False


def _app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _assert_panel_surface(block: str, tokens: dict):
    assert (
        f"background-color: {tokens['panel']};" in block
        or f"background-color: {tokens['panel_raised']};" in block
    )


def _assert_default_border(block: str, tokens: dict):
    assert (
        f"border-color: {tokens['border']};" in block
        or f"border: 1px solid {tokens['border']};" in block
    )


def test_build_stylesheet_uses_surface_hover_tokens_for_light_theme():
    tokens = theme_tokens("light")

    stylesheet = _build_stylesheet("light")

    assert tokens["surface_hover"] in stylesheet
    assert tokens["surface_hover"] == "#DCE8F6"
    assert tokens["surface_hover"] in stylesheet.split("#status_center_metric_card:hover", 1)[1]
    assert tokens["surface_hover"] in stylesheet.split("#status_center_health_row:hover", 1)[1]


def test_stylesheet_shell_and_dialog_hint_tokens():
    for mode in ("light", "dark"):
        t = theme_tokens(mode)
        css = _build_stylesheet(mode)
        assert "QLabel[hintTone=" in css
        assert t["success"] in css.split('QLabel[hintTone="success"]', 1)[1].split("}", 1)[0]
        assert t["shell_bg"] in css.split("QMainWindow, QDialog", 1)[1].split("}", 1)[0]
        assert "QTabBar::tab:selected" in css
        assert t["panel_raised"] in css.split("QTabBar::tab:selected", 1)[1].split("}", 1)[0]
        nav = css.split("#workspace_nav_rail", 1)[1].split("}", 1)[0]
        assert str(t["space_xxs"]) in nav and str(t["space_xs"]) in nav
        indicator = css.split("QToolButton#workspace_summary_indicator {", 1)[1].split("}", 1)[0]
        assert str(t["space_xs"]) in indicator and str(t["space_sm"]) in indicator


def test_status_center_styles_reduce_resting_container_weight():
    for mode in ("light", "dark"):
        t = theme_tokens(mode)
        css = _build_stylesheet(mode)
        metrics = css.split("#status_center_metrics", 1)[1].split("}", 1)[0]
        actions = css.split("#status_center_actions", 1)[1].split("}", 1)[0]
        sections = css.split("#status_center_health,", 1)[1].split("}", 1)[0]
        metric_card = css.split("#status_center_metric_card {", 1)[1].split("}", 1)[0]
        health_row = css.split("#status_center_health_row {", 1)[1].split("}", 1)[0]
        health_bar = css.split("QProgressBar#status_center_health_error_bar,", 1)[1].split("}", 1)[0]
        health_chunk = css.split("QProgressBar#status_center_health_error_bar::chunk {", 1)[1].split("}", 1)[0]

        assert "background-color: transparent;" in metrics
        assert "border: none;" in metrics
        assert "background-color: transparent;" in actions
        assert "border: none;" in actions
        assert "background-color: transparent;" in sections
        assert "border: none;" in sections
        assert "border-radius: 0px;" in sections
        assert "background-color: transparent;" in metric_card
        assert "border: 1px solid transparent;" in metric_card
        assert "border-radius: 0px;" in metric_card
        assert "background-color: transparent;" in health_row
        assert "border: 1px solid transparent;" in health_row
        assert "border-radius: 0px;" in health_row
        assert f"background-color: {t['panel_alt']};" in health_bar
        assert "border-radius: 0px;" in health_bar
        assert "border-radius: 0px;" in health_chunk


def test_status_center_header_styles_use_engineering_surface_tokens():
    for mode in ("light", "dark"):
        t = theme_tokens(mode)
        css = _build_stylesheet(mode)

        header = css.split('#status_center_header[panelTone="status"] {', 1)[1].split("}", 1)[0]
        eyebrow = css.split("#status_center_eyebrow {", 1)[1].split("}", 1)[0]
        metrics = css.split("#status_center_header_metrics_strip {", 1)[1].split("}", 1)[0]

        _assert_panel_surface(header, t)
        _assert_default_border(header, t)
        assert "border-radius: 0px;" in header
        assert f"color: {t['accent_hover']};" in eyebrow
        assert "background-color: transparent;" in metrics
        assert "border: none;" in metrics
        assert "border-radius: 0px;" in metrics


def test_tokens_include_xxs_spacing_for_all_themes():
    for mode in ("light", "dark"):
        tokens = theme_tokens(mode)
        assert "space_xxs" in tokens
        assert int(tokens["space_xxs"]) == 4


def test_engineering_theme_radii_remove_pill_shapes():
    for mode in ("light", "dark"):
        tokens = theme_tokens(mode)
        css = _build_stylesheet(mode)

        assert int(tokens["r_sm"]) == 4
        assert int(tokens["r_md"]) == 6
        assert int(tokens["r_xl"]) == 8
        assert "999px" not in css

        chip = css.split("QToolButton#workspace_summary_indicator {", 1)[1].split("}", 1)[0]
        browser_card = css.split("#widget_browser_card {", 1)[1].split("}", 1)[0]
        metric_card = css.split("#status_center_metric_card {", 1)[1].split("}", 1)[0]
        health_row = css.split("#status_center_health_row {", 1)[1].split("}", 1)[0]
        health_bar = css.split("QProgressBar#status_center_health_error_bar,", 1)[1].split("}", 1)[0]

        assert "border-radius: 0px;" in chip
        assert "padding: 2px 8px;" in chip
        assert "min-height: 26px;" in chip
        assert "border-radius: 0px;" in browser_card
        assert "border-radius: 0px;" in metric_card
        assert "border-radius: 0px;" in health_row
        assert "border-radius: 0px;" in health_bar


def test_page_navigator_styles_use_token_driven_cards():
    for mode in ("light", "dark"):
        t = theme_tokens(mode)
        css = _build_stylesheet(mode)

        header = css.split("#page_navigator_header {", 1)[1].split("}", 1)[0]
        guidance = css.split("#page_navigator_guidance {", 1)[1].split("}", 1)[0]
        scroll_shell = css.split("#page_navigator_scroll_shell {", 1)[1].split("}", 1)[0]
        thumb = css.split("#page_navigator_thumbnail {", 1)[1].split("}", 1)[0]
        selected = css.split('#page_navigator_thumbnail[selected="true"] {', 1)[1].split("}", 1)[0]
        empty = css.split("#page_navigator_empty_state {", 1)[1].split("}", 1)[0]
        thumb_label = css.split("QLabel#page_navigator_thumb_label {", 1)[1].split("}", 1)[0]

        _assert_panel_surface(header, t)
        assert "border-radius: 0px;" in header
        assert "background-color: transparent;" in guidance
        assert "border: none;" in guidance
        assert "border-radius: 0px;" in guidance
        assert "background-color: transparent;" in scroll_shell
        assert "border: none;" in scroll_shell
        assert "border-radius: 0px;" in scroll_shell
        assert "background-color: transparent;" in thumb
        assert "border: 1px solid transparent;" in thumb
        assert "border-radius: 0px;" in thumb
        assert f"border-color: {t['accent']};" in selected
        assert f"border: 1px solid {t['border']};" in empty
        assert "border-radius: 0px;" in empty
        assert "padding: 12px;" in empty
        assert "border-radius: 0px;" in thumb_label
        assert "padding: 2px;" in thumb_label


def test_page_fields_panel_styles_use_engineering_surface_tokens():
    for mode in ("light", "dark"):
        t = theme_tokens(mode)
        css = _build_stylesheet(mode)

        header = css.split('#page_fields_header[panelTone="fields"] {', 1)[1].split("}", 1)[0]
        eyebrow = css.split("#page_fields_eyebrow {", 1)[1].split("}", 1)[0]
        metrics = css.split("#page_fields_metrics_strip {", 1)[1].split("}", 1)[0]
        sections = css.split("#page_editor_section,", 1)[1].split("}", 1)[0]
        table = css.split("#page_editor_table {", 1)[1].split("}", 1)[0]
        buttons = css.split("#page_editor_actions QPushButton,", 1)[1].split("}", 1)[0]

        _assert_panel_surface(header, t)
        _assert_default_border(header, t)
        assert "border-radius: 0px;" in header
        assert f"color: {t['accent_hover']};" in eyebrow
        assert "background-color: transparent;" in metrics
        assert "border: none;" in metrics
        assert "border-radius: 0px;" in metrics
        assert "background-color: transparent;" in sections
        assert "border: none;" in sections
        assert "border-radius: 0px;" in sections
        assert f"background-color: {t['panel_alt']};" in table
        assert f"border: 1px solid {t['border']};" in table
        assert "border-radius: 0px;" in table
        assert "border-radius: 0px;" in buttons
        assert "min-height: 28px;" in buttons
        assert f"padding: 3px {t['space_sm']}px;" in buttons


def test_page_timers_panel_styles_use_engineering_surface_tokens():
    for mode in ("light", "dark"):
        t = theme_tokens(mode)
        css = _build_stylesheet(mode)

        header = css.split('#page_timers_header[panelTone="timers"] {', 1)[1].split("}", 1)[0]
        eyebrow = css.split("#page_timers_eyebrow {", 1)[1].split("}", 1)[0]
        metrics = css.split("#page_timers_metrics_strip {", 1)[1].split("}", 1)[0]
        sections = css.split("#page_editor_section,", 1)[1].split("}", 1)[0]
        table = css.split("#page_editor_table {", 1)[1].split("}", 1)[0]
        buttons = css.split("#page_editor_actions QPushButton,", 1)[1].split("}", 1)[0]

        _assert_panel_surface(header, t)
        _assert_default_border(header, t)
        assert "border-radius: 0px;" in header
        assert f"color: {t['accent_hover']};" in eyebrow
        assert "background-color: transparent;" in metrics
        assert "border: none;" in metrics
        assert "border-radius: 0px;" in metrics
        assert "background-color: transparent;" in sections
        assert "border: none;" in sections
        assert "border-radius: 0px;" in sections
        assert f"background-color: {t['panel_alt']};" in table
        assert f"border: 1px solid {t['border']};" in table
        assert "border-radius: 0px;" in table
        assert "border-radius: 0px;" in buttons
        assert "min-height: 28px;" in buttons
        assert f"padding: 3px {t['space_sm']}px;" in buttons


def test_editor_tabs_styles_use_engineering_shell_tokens():
    for mode in ("light", "dark"):
        t = theme_tokens(mode)
        css = _build_stylesheet(mode)

        header = css.split("#editor_tabs_header {", 1)[1].split("}", 1)[0]
        eyebrow = css.split("#editor_tabs_eyebrow {", 1)[1].split("}", 1)[0]
        mode_strip = css.split("#editor_tabs_mode_strip {", 1)[1].split("}", 1)[0]
        shell = css.split("#editor_tabs_shell,", 1)[1].split("}", 1)[0]
        editor = css.split("QPlainTextEdit#editor_tabs_xml_editor {", 1)[1].split("}", 1)[0]

        assert "border-radius: 0px;" in header
        assert f"background-color: {t['panel_raised']};" in header
        assert f"color: {t['accent_hover']};" in eyebrow
        assert f"background-color: {t['panel_soft']};" in mode_strip
        assert f"background-color: {t['panel_raised']};" in shell
        assert "border-radius: 0px;" in shell
        assert f"background-color: {t['canvas_stage']};" in editor
        assert f"border-radius: {t['r_sm']}px;" in editor


def test_preview_panel_styles_use_engineering_surface_tokens():
    for mode in ("light", "dark"):
        t = theme_tokens(mode)
        css = _build_stylesheet(mode)

        header = css.split("#preview_header {", 1)[1].split("}", 1)[0]
        metrics = css.split("#preview_metrics_strip {", 1)[1].split("}", 1)[0]
        content = css.split("#preview_content {", 1)[1].split("}", 1)[0]
        overlay = css.split('QWidget#preview_overlay_surface[solidBackground="true"] {', 1)[1].split("}", 1)[0]
        status_shell = css.split("#preview_status_shell {", 1)[1].split("}", 1)[0]
        status_button = css.split("QPushButton#preview_status_button {", 1)[1].split("}", 1)[0]

        _assert_panel_surface(header, t)
        assert "background-color: transparent;" in metrics
        assert "border: none;" in metrics
        assert "border-radius: 0px;" in metrics
        assert "border-radius: 0px;" in header
        assert f"background-color: {t['canvas_bg']};" in content
        assert f"background-color: {t['canvas_stage']};" in overlay
        assert "border-radius: 0px;" in overlay
        assert "border-radius: 0px;" in content
        assert f"background-color: {t['panel_raised']};" in status_shell
        assert "border-radius: 0px;" in status_shell
        assert f"background-color: {t['panel_alt']};" in status_button
        assert "border-radius: 0px;" in status_button


def test_workspace_command_bar_styles_use_engineering_surface_tokens():
    for mode in ("light", "dark"):
        t = theme_tokens(mode)
        css = _build_stylesheet(mode)

        command_bar = css.split("#workspace_command_bar {", 1)[1].split("}", 1)[0]
        context = css.split("#workspace_context_card {", 1)[1].split("}", 1)[0]
        toolbar = css.split("QToolBar#main_toolbar {", 1)[1].split("}", 1)[0]
        toolbar_separator = css.split("QToolBar#main_toolbar::separator {", 1)[1].split("}", 1)[0]
        toolbar_button = css.split("QToolBar#main_toolbar QToolButton {", 1)[1].split("}", 1)[0]
        toolbar_button_hover = css.split("QToolBar#main_toolbar QToolButton:hover {", 1)[1].split("}", 1)[0]
        host_separator = css.split("QFrame#toolbar_host_separator {", 1)[1].split("}", 1)[0]
        insert_button = css.split("QPushButton#workspace_insert_button {", 1)[1].split("}", 1)[0]
        insert_button_hover = css.split("QPushButton#workspace_insert_button:hover {", 1)[1].split("}", 1)[0]
        mode_strip = css.split("#workspace_mode_switch {", 1)[1].split("}", 1)[0]

        assert f"background-color: {t['panel']};" in command_bar
        assert "border-radius: 0px;" in command_bar
        assert "background-color: transparent;" in context
        assert "border: none;" in context
        assert f"border-radius: {t['r_md']}px;" in context
        assert "spacing: 1px;" in toolbar
        assert "width: 1px;" in toolbar_separator
        assert "margin: 1px 1px;" in toolbar_separator
        assert "background-color: transparent;" in toolbar_button
        assert "border-radius: 0px;" in toolbar_button
        assert "padding: 1px 5px;" in toolbar_button
        assert "min-height: 22px;" in toolbar_button
        assert f"background-color: {t['surface_hover']};" in toolbar_button_hover
        assert "min-width: 1px;" in host_separator
        assert "max-width: 1px;" in host_separator
        assert "margin-left: 4px;" in host_separator
        assert "margin-right: 4px;" in host_separator
        assert "background-color: transparent;" in insert_button
        assert "border-radius: 0px;" in insert_button
        assert "padding: 2px 8px;" in insert_button
        assert "min-width: 56px;" in insert_button
        assert "max-width: 56px;" in insert_button
        assert "min-height: 26px;" in insert_button
        assert "max-height: 26px;" in insert_button
        assert f"background-color: {t['surface_hover']};" in insert_button_hover
        assert "background-color: transparent;" in mode_strip
        assert "border: none;" in mode_strip
        assert "border-radius: 0px;" in mode_strip


def test_workspace_chrome_corner_radii_stay_flat():
    for mode in ("light", "dark"):
        t = theme_tokens(mode)
        css = _build_stylesheet(mode)

        mode_button = css.split("QPushButton#workspace_mode_button {", 1)[1].split("}", 1)[0]
        bottom_toggle_button = css.split("QPushButton#workspace_bottom_toggle_button {", 1)[1].split("}", 1)[0]
        nav_button = css.split('QToolButton[workspaceNav="true"] {', 1)[1].split("}", 1)[0]
        status_chip = css.split("#workspace_status_chip {", 1)[1].split("}", 1)[0]
        search_shell = css.split("QFrame#property_panel_search_shell {", 1)[1].split("}", 1)[0]
        empty_state = css.split("#property_panel_empty_state {", 1)[1].split("}", 1)[0]
        resource_tabs_pane = css.split("QTabWidget#resource_panel_tabs::pane {", 1)[1].split("}", 1)[0]
        resource_tabs_tab = css.split("QTabWidget#resource_panel_tabs QTabBar::tab {", 1)[1].split("}", 1)[0]
        resource_details_pane = css.split("QTabWidget#resource_panel_details_tabs::pane {", 1)[1].split("}", 1)[0]
        resource_details_tab = css.split("QTabWidget#resource_panel_details_tabs QTabBar::tab {", 1)[1].split("}", 1)[0]
        inspector_tabs_pane = css.split("QTabWidget#workspace_inspector_tabs::pane {", 1)[1].split("}", 1)[0]
        inspector_tabs_tab = css.split("QTabWidget#workspace_inspector_tabs QTabBar::tab {", 1)[1].split("}", 1)[0]
        bottom_tabs_pane = css.split("QTabWidget#workspace_bottom_tabs::pane {", 1)[1].split("}", 1)[0]
        bottom_tabs_tab = css.split("QTabWidget#workspace_bottom_tabs QTabBar::tab {", 1)[1].split("}", 1)[0]
        thumb_surface = css.split("QFrame#page_navigator_thumb_surface {", 1)[1].split("}", 1)[0]
        thumb_label = css.split("QLabel#page_navigator_thumb_label {", 1)[1].split("}", 1)[0]

        assert "border-radius: 0px;" in mode_button
        assert "min-width: 56px;" in mode_button
        assert "max-width: 56px;" in mode_button
        assert "min-height: 26px;" in mode_button
        assert "max-height: 26px;" in mode_button
        assert "border-radius: 0px;" in bottom_toggle_button
        assert "min-width: 48px;" in bottom_toggle_button
        assert "min-height: 26px;" in bottom_toggle_button
        assert "border-radius: 0px;" in nav_button
        assert "min-width: 60px;" in nav_button
        assert "max-width: 60px;" in nav_button
        assert "min-height: 26px;" in nav_button
        assert "max-height: 26px;" in nav_button
        assert "border-radius: 0px;" in status_chip
        assert "border-radius: 0px;" in search_shell
        assert "border-radius: 0px;" in empty_state
        assert "background-color: transparent;" in resource_tabs_pane
        assert "border: none;" in resource_tabs_pane
        assert "border-radius: 0px;" in resource_tabs_pane
        assert "border-radius: 0px;" in resource_tabs_tab
        assert "margin-right: 0px;" in resource_tabs_tab
        assert "min-height: 28px;" in resource_tabs_tab
        assert "padding: 6px 10px;" in resource_tabs_tab
        assert "background-color: transparent;" in resource_details_pane
        assert "border: none;" in resource_details_pane
        assert "border-radius: 0px;" in resource_details_pane
        assert "border-radius: 0px;" in resource_details_tab
        assert "margin-right: 0px;" in resource_details_tab
        assert "min-height: 28px;" in resource_details_tab
        assert "padding: 6px 10px;" in resource_details_tab
        assert "background-color: transparent;" in inspector_tabs_pane
        assert "border: none;" in inspector_tabs_pane
        assert "border-radius: 0px;" in inspector_tabs_pane
        assert "padding: 0px;" in inspector_tabs_pane
        assert "top: 0px;" in inspector_tabs_pane
        assert "border-radius: 0px;" in inspector_tabs_tab
        assert "margin-right: 0px;" in inspector_tabs_tab
        assert "min-height: 26px;" in inspector_tabs_tab
        assert "padding: 3px 8px;" in inspector_tabs_tab
        assert "background-color: transparent;" in bottom_tabs_pane
        assert "border: none;" in bottom_tabs_pane
        assert "border-radius: 0px;" in bottom_tabs_pane
        assert "padding: 0px;" in bottom_tabs_pane
        assert "top: 0px;" in bottom_tabs_pane
        assert "border-radius: 0px;" in bottom_tabs_tab
        assert "margin-right: 0px;" in bottom_tabs_tab
        assert "min-height: 26px;" in bottom_tabs_tab
        assert "padding: 3px 8px;" in bottom_tabs_tab
        assert "background-color: transparent;" in thumb_surface
        assert "border: none;" in thumb_surface
        assert "border-radius: 0px;" in thumb_surface
        assert "border-radius: 0px;" in thumb_label


def test_property_panel_styles_use_engineering_surface_tokens():
    for mode in ("light", "dark"):
        t = theme_tokens(mode)
        css = _build_stylesheet(mode)

        header = css.split('#workspace_panel_header[panelTone="property"] {', 1)[1].split("}", 1)[0]
        hint_strip = css.split('#workspace_hint_strip[panelTone="property"] {', 1)[1].split("}", 1)[0]
        metric_card = css.split("QFrame#property_panel_metric_card {", 1)[1].split("}", 1)[0]
        inspector_group = css.split("QGroupBox#inspector_collapsible_group {", 1)[1].split("}", 1)[0]

        _assert_panel_surface(header, t)
        _assert_default_border(header, t)
        assert f"background-color: {t['panel_soft']};" in hint_strip
        assert "background-color: transparent;" in metric_card
        assert "border-radius: 0px;" in metric_card
        assert "background-color: transparent;" in inspector_group
        assert "border: 1px solid transparent;" in inspector_group
        assert "border-radius: 0px;" in inspector_group


def test_resource_panel_styles_use_engineering_surface_tokens():
    for mode in ("light", "dark"):
        t = theme_tokens(mode)
        css = _build_stylesheet(mode)

        header = css.split("#resource_panel_header {", 1)[1].split("}", 1)[0]
        card = css.split("#resource_panel_card {", 1)[1].split("}", 1)[0]
        metric_card = css.split("#resource_panel_metric_card {", 1)[1].split("}", 1)[0]
        list_surface = css.split("QListWidget#resource_panel_list,", 1)[1].split("}", 1)[0]
        preview = css.split("#resource_panel_preview {", 1)[1].split("}", 1)[0]

        _assert_panel_surface(header, t)
        assert "border-radius: 0px;" in header
        assert "background-color: transparent;" in card
        assert "border: none;" in card
        assert "border-radius: 0px;" in card
        assert "background-color: transparent;" in metric_card
        assert "border-radius: 0px;" in metric_card
        assert f"background-color: {t['panel_alt']};" in list_surface
        assert f"background-color: {t['panel_alt']};" in preview
        assert "border-radius: 0px;" in preview
        assert "border-radius: 0px;" in list_surface


def test_resource_dialog_styles_use_engineering_surface_tokens():
    for mode in ("light", "dark"):
        t = theme_tokens(mode)
        css = _build_stylesheet(mode)

        header = css.split("#resource_dialog_header {", 1)[1].split("}", 1)[0]
        card = css.split("#resource_dialog_card {", 1)[1].split("}", 1)[0]
        metric_card = css.split("#resource_dialog_metric_card {", 1)[1].split("}", 1)[0]
        table = css.split("QTableWidget#resource_dialog_table {", 1)[1].split("}", 1)[0]

        _assert_panel_surface(header, t)
        assert "border-radius: 0px;" in header
        assert "background-color: transparent;" in card
        assert "border: none;" in card
        assert "border-radius: 0px;" in card
        assert "background-color: transparent;" in metric_card
        assert "border: none;" in metric_card
        assert "border-radius: 0px;" in metric_card
        assert f"background-color: {t['panel_alt']};" in table
        assert "border-radius: 0px;" in table


def test_welcome_page_styles_use_engineering_surface_tokens():
    for mode in ("light", "dark"):
        t = theme_tokens(mode)
        css = _build_stylesheet(mode)

        hero = css.split("#welcome_hero {", 1)[1].split("}", 1)[0]
        card = css.split("#welcome_action_panel,", 1)[1].split("}", 1)[0]
        sdk = css.split("#welcome_sdk_panel {", 1)[1].split("}", 1)[0]
        metric_card = css.split("#welcome_metric_card {", 1)[1].split("}", 1)[0]
        recent_item = css.split("#welcome_recent_item {", 1)[1].split("}", 1)[0]
        recent_status = css.split("#welcome_recent_status {", 1)[1].split("}", 1)[0]
        empty = css.split("#welcome_recent_empty {", 1)[1].split("}", 1)[0]

        assert f"background-color: {t['panel']};" in hero
        assert "border-radius: 0px;" in hero
        assert "background-color: transparent;" in card
        assert "border: none;" in card
        assert "border-radius: 0px;" in card
        assert "background-color: transparent;" in sdk
        assert "border: none;" in sdk
        assert "border-radius: 0px;" in sdk
        assert "background-color: transparent;" in metric_card
        assert "border: none;" in metric_card
        assert "border-radius: 0px;" in metric_card
        assert "background-color: transparent;" in recent_item
        assert "border: 1px solid transparent;" in recent_item
        assert "border-radius: 0px;" in recent_item
        assert "background-color: transparent;" in recent_status
        assert "border: none;" in recent_status
        assert "border-radius: 0px;" in recent_status
        assert "padding: 0px;" in recent_status
        assert f"border: 1px dashed {t['border']};" in empty
        assert "border-radius: 0px;" in empty


def test_project_dock_styles_use_engineering_surface_tokens():
    for mode in ("light", "dark"):
        t = theme_tokens(mode)
        css = _build_stylesheet(mode)

        header = css.split("#project_dock_header {", 1)[1].split("}", 1)[0]
        settings = css.split("#project_dock_settings_group {", 1)[1].split("}", 1)[0]
        controls = css.split("QComboBox#project_dock_mode_combo,", 1)[1].split("}", 1)[0]
        metric_card = css.split("#project_dock_metric_card {", 1)[1].split("}", 1)[0]
        tree = css.split("QTreeWidget#project_dock_tree {", 1)[1].split("}", 1)[0]

        _assert_panel_surface(header, t)
        assert "border-radius: 0px;" in header
        assert "background-color: transparent;" in settings
        assert "border: none;" in settings
        assert "border-radius: 0px;" in settings
        assert "border-radius: 0px;" in controls
        assert f"padding: 3px {t['space_sm']}px;" in controls
        assert "min-height: 28px;" in controls
        assert "background-color: transparent;" in metric_card
        assert "border: none;" in metric_card
        assert "border-radius: 0px;" in metric_card
        assert f"background-color: {t['panel_alt']};" in tree
        assert "border-radius: 0px;" in tree


def test_app_selector_styles_use_engineering_surface_tokens():
    for mode in ("light", "dark"):
        t = theme_tokens(mode)
        css = _build_stylesheet(mode)

        header = css.split("#app_selector_header {", 1)[1].split("}", 1)[0]
        card = css.split("#app_selector_root_card,", 1)[1].split("}", 1)[0]
        metric_card = css.split("#app_selector_metric_card {", 1)[1].split("}", 1)[0]
        item_card = css.split("#app_selector_item_card {", 1)[1].split("}", 1)[0]

        _assert_panel_surface(header, t)
        assert "border-radius: 0px;" in header
        assert "background-color: transparent;" in card
        assert "border: none;" in card
        assert "border-radius: 0px;" in card
        assert "background-color: transparent;" in metric_card
        assert "border: none;" in metric_card
        assert "border-radius: 0px;" in metric_card
        assert "background-color: transparent;" in item_card
        assert "border: 1px solid transparent;" in item_card
        assert "border-radius: 0px;" in item_card


def test_new_project_dialog_styles_use_engineering_surface_tokens():
    for mode in ("light", "dark"):
        t = theme_tokens(mode)
        css = _build_stylesheet(mode)

        header = css.split("#new_project_header {", 1)[1].split("}", 1)[0]
        card = css.split("#new_project_form_card,", 1)[1].split("}", 1)[0]
        metric_card = css.split("#new_project_metric_card,", 1)[1].split("}", 1)[0]

        _assert_panel_surface(header, t)
        assert "border-radius: 0px;" in header
        assert "background-color: transparent;" in card
        assert "border: none;" in card
        assert "border-radius: 0px;" in card
        assert "background-color: transparent;" in metric_card
        assert "border: none;" in metric_card
        assert "border-radius: 0px;" in metric_card


def test_repository_health_dialog_styles_use_engineering_surface_tokens():
    for mode in ("light", "dark"):
        t = theme_tokens(mode)
        css = _build_stylesheet(mode)

        header = css.split("#repo_health_header {", 1)[1].split("}", 1)[0]
        card = css.split("#repo_health_details_card,", 1)[1].split("}", 1)[0]
        metric_card = css.split("#repo_health_metric_card {", 1)[1].split("}", 1)[0]
        details = css.split("QTextEdit#repo_health_details {", 1)[1].split("}", 1)[0]

        _assert_panel_surface(header, t)
        assert "border-radius: 0px;" in header
        assert "background-color: transparent;" in card
        assert "border: none;" in card
        assert "border-radius: 0px;" in card
        assert "background-color: transparent;" in metric_card
        assert "border: none;" in metric_card
        assert "border-radius: 0px;" in metric_card
        assert f"background-color: {t['panel_alt']};" in details
        assert "border-radius: 0px;" in details


def test_release_build_dialog_styles_use_engineering_surface_tokens():
    for mode in ("light", "dark"):
        t = theme_tokens(mode)
        css = _build_stylesheet(mode)

        header = css.split("#release_build_header {", 1)[1].split("}", 1)[0]
        card = css.split("#release_build_card {", 1)[1].split("}", 1)[0]
        metric_card = css.split("#release_build_metric_card {", 1)[1].split("}", 1)[0]

        _assert_panel_surface(header, t)
        assert "border-radius: 0px;" in header
        assert "background-color: transparent;" in card
        assert "border: none;" in card
        assert "border-radius: 0px;" in card
        assert "background-color: transparent;" in metric_card
        assert "border: none;" in metric_card
        assert "border-radius: 0px;" in metric_card


def test_release_profiles_dialog_styles_use_engineering_surface_tokens():
    for mode in ("light", "dark"):
        t = theme_tokens(mode)
        css = _build_stylesheet(mode)

        header = css.split("#release_profiles_header {", 1)[1].split("}", 1)[0]
        card = css.split("#release_profiles_card {", 1)[1].split("}", 1)[0]
        metric_card = css.split("#release_profiles_metric_card {", 1)[1].split("}", 1)[0]

        _assert_panel_surface(header, t)
        assert "border-radius: 0px;" in header
        assert "background-color: transparent;" in card
        assert "border: none;" in card
        assert "border-radius: 0px;" in card
        assert "background-color: transparent;" in metric_card
        assert "border: none;" in metric_card
        assert "border-radius: 0px;" in metric_card


def test_release_history_dialog_styles_use_engineering_surface_tokens():
    for mode in ("light", "dark"):
        t = theme_tokens(mode)
        css = _build_stylesheet(mode)

        header = css.split("#release_history_header {", 1)[1].split("}", 1)[0]
        card = css.split("#release_history_card {", 1)[1].split("}", 1)[0]
        metric_card = css.split("#release_history_metric_card {", 1)[1].split("}", 1)[0]
        history_list = css.split("QListWidget#release_history_list {", 1)[1].split("}", 1)[0]
        details = css.split("QTextEdit#release_history_details,", 1)[1].split("}", 1)[0]

        _assert_panel_surface(header, t)
        assert "border-radius: 0px;" in header
        assert "background-color: transparent;" in card
        assert "border: none;" in card
        assert "border-radius: 0px;" in card
        assert "background-color: transparent;" in metric_card
        assert "border: none;" in metric_card
        assert "border-radius: 0px;" in metric_card
        assert f"background-color: {t['panel_alt']};" in history_list
        assert "border-radius: 0px;" in history_list
        assert f"background-color: {t['panel_alt']};" in details
        assert "border-radius: 0px;" in details


def test_widget_browser_styles_use_engineering_panel_tokens():
    for mode in ("light", "dark"):
        t = theme_tokens(mode)
        css = _build_stylesheet(mode)

        header = css.split("#workspace_panel_header,", 1)[1].split("}", 1)[0]
        tone_header = css.split('#widget_browser_header[panelTone="components"] {', 1)[1].split("}", 1)[0]
        meta = css.split("#widget_browser_header_meta {", 1)[1].split("}", 1)[0]
        metrics = css.split("#widget_browser_metrics_strip {", 1)[1].split("}", 1)[0]
        filter_bar = css.split("#widget_browser_filter_bar {", 1)[1].split("}", 1)[0]
        card = css.split("#widget_browser_card {", 1)[1].split("}", 1)[0]
        insert_button = css.split("QPushButton#widget_browser_insert_button {", 1)[1].split("}", 1)[0]

        _assert_panel_surface(header, t)
        _assert_default_border(header, t)
        assert "border-radius: 0px;" in header
        assert f"background-color: {t['panel']};" in tone_header
        assert f"border-color: {t['border']};" in tone_header
        assert f"color: {t['text_muted']};" in meta
        assert "background-color: transparent;" in metrics
        assert "border: none;" in metrics
        assert "border-radius: 0px;" in metrics
        assert "background-color: transparent;" in filter_bar
        assert "border: none;" in filter_bar
        assert "border-radius: 0px;" in filter_bar
        assert "background-color: transparent;" in card
        assert "border-radius: 0px;" in card
        assert "border-radius: 0px;" in insert_button
        assert "padding: 2px 4px;" in insert_button


def test_widget_tree_styles_use_engineering_surface_tokens():
    for mode in ("light", "dark"):
        t = theme_tokens(mode)
        css = _build_stylesheet(mode)

        header = css.split("#workspace_panel_header,", 1)[1].split("}", 1)[0]
        tone_header = css.split('#workspace_panel_header[panelTone="structure"] {', 1)[1].split("}", 1)[0]
        eyebrow = css.split("#structure_header_eyebrow {", 1)[1].split("}", 1)[0]
        metrics = css.split("#structure_metrics_strip {", 1)[1].split("}", 1)[0]
        strips = css.split("#structure_primary_strip,", 1)[1].split("}", 1)[0]
        drag_hint = css.split("#structure_drag_hint_strip {", 1)[1].split("}", 1)[0]
        buttons = css.split("#structure_primary_strip QPushButton,", 1)[1].split("}", 1)[0]
        tree = css.split("QTreeWidget#widget_tree_panel_tree {", 1)[1].split("}", 1)[0]

        _assert_panel_surface(header, t)
        _assert_default_border(header, t)
        assert "border-radius: 0px;" in header
        assert f"background-color: {t['panel_raised']};" in tone_header
        assert f"border-color: {t['border']};" in tone_header
        assert f"color: {t['accent_hover']};" in eyebrow
        assert "background-color: transparent;" in metrics
        assert "border: none;" in metrics
        assert "border-radius: 0px;" in metrics
        assert "background-color: transparent;" in strips
        assert "border: none;" in strips
        assert "border-radius: 0px;" in strips
        assert "background-color: transparent;" in drag_hint
        assert "border: none;" in drag_hint
        assert "border-radius: 0px;" in drag_hint
        assert "border-radius: 0px;" in buttons
        assert "min-height: 28px;" in buttons
        assert f"padding: 3px {t['space_sm']}px;" in buttons
        assert f"background-color: {t['panel_alt']};" in tree
        _assert_default_border(tree, t)
        assert "border-radius: 0px;" in tree
        assert "padding: 0px;" in tree


def test_diagnostics_panel_styles_use_engineering_surface_tokens():
    for mode in ("light", "dark"):
        t = theme_tokens(mode)
        css = _build_stylesheet(mode)

        header = css.split("#diagnostics_header {", 1)[1].split("}", 1)[0]
        tone_header = css.split('#diagnostics_header[panelTone="diagnostics"] {', 1)[1].split("}", 1)[0]
        meta = css.split("#diagnostics_header_meta {", 1)[1].split("}", 1)[0]
        controls = css.split("#diagnostics_controls_strip,", 1)[1].split("}", 1)[0]
        buttons = css.split("#diagnostics_controls_strip QComboBox,", 1)[1].split("}", 1)[0]
        list_block = css.split("QListWidget#diagnostics_list {", 1)[1].split("}", 1)[0]

        _assert_panel_surface(header, t)
        _assert_default_border(header, t)
        assert "border-radius: 0px;" in header
        assert f"background-color: {t['panel']};" in tone_header
        assert f"border-color: {t['border']};" in tone_header
        assert f"color: {t['text_muted']};" in meta
        assert "background-color: transparent;" in controls
        assert "border: none;" in controls
        assert "border-radius: 0px;" in controls
        assert "border-radius: 0px;" in buttons
        assert "min-height: 26px;" in buttons
        assert f"padding: 2px {t['space_sm']}px;" in buttons
        assert f"background-color: {t['panel_alt']};" in list_block
        assert "border-radius: 0px;" in list_block


def test_debug_panel_styles_use_engineering_surface_tokens():
    for mode in ("light", "dark"):
        t = theme_tokens(mode)
        css = _build_stylesheet(mode)

        header = css.split("#debug_panel_header {", 1)[1].split("}", 1)[0]
        tone_header = css.split('#debug_panel_header[panelTone="runtime"] {', 1)[1].split("}", 1)[0]
        meta = css.split("#debug_panel_header_meta {", 1)[1].split("}", 1)[0]
        controls = css.split("#debug_panel_controls_strip {", 1)[1].split("}", 1)[0]
        button = css.split("#debug_panel_controls_strip QPushButton {", 1)[1].split("}", 1)[0]
        surface = css.split("QPlainTextEdit#debug_output_surface {", 1)[1].split("}", 1)[0]

        _assert_panel_surface(header, t)
        _assert_default_border(header, t)
        assert "border-radius: 0px;" in header
        assert f"background-color: {t['panel']};" in tone_header
        assert f"border-color: {t['border']};" in tone_header
        assert f"color: {t['text_muted']};" in meta
        assert "background-color: transparent;" in controls
        assert "border: none;" in controls
        assert "border-radius: 0px;" in controls
        assert "border-radius: 0px;" in button
        assert "min-height: 26px;" in button
        assert f"padding: 2px {t['space_sm']}px;" in button
        assert f"background-color: {t['canvas_stage']};" in surface
        assert "border-radius: 0px;" in surface


def test_history_panel_styles_use_engineering_surface_tokens():
    for mode in ("light", "dark"):
        t = theme_tokens(mode)
        css = _build_stylesheet(mode)

        header = css.split("#history_panel_header {", 1)[1].split("}", 1)[0]
        tone_header = css.split('#history_panel_header[panelTone="history"] {', 1)[1].split("}", 1)[0]
        meta = css.split("#history_panel_meta {", 1)[1].split("}", 1)[0]
        list_block = css.split("QListWidget#history_panel_list {", 1)[1].split("}", 1)[0]

        _assert_panel_surface(header, t)
        _assert_default_border(header, t)
        assert "border-radius: 0px;" in header
        assert f"background-color: {t['panel']};" in tone_header
        assert f"border-color: {t['border']};" in tone_header
        assert f"color: {t['text_muted']};" in meta
        assert f"background-color: {t['panel_alt']};" in list_block
        assert "border-radius: 0px;" in list_block


def test_animations_panel_styles_use_engineering_surface_tokens():
    for mode in ("light", "dark"):
        t = theme_tokens(mode)
        css = _build_stylesheet(mode)

        header = css.split("#animations_panel_header {", 1)[1].split("}", 1)[0]
        tone_header = css.split('#animations_panel_header[panelTone="animations"] {', 1)[1].split("}", 1)[0]
        meta = css.split("#animations_panel_meta {", 1)[1].split("}", 1)[0]
        actions = css.split("#animations_panel_actions_strip {", 1)[1].split("}", 1)[0]
        buttons = css.split("#animations_panel_actions_strip QPushButton {", 1)[1].split("}", 1)[0]
        table = css.split("QTableWidget#animations_panel_table {", 1)[1].split("}", 1)[0]
        detail = css.split("QGroupBox#animations_panel_detail_group {", 1)[1].split("}", 1)[0]

        _assert_panel_surface(header, t)
        _assert_default_border(header, t)
        assert "border-radius: 0px;" in header
        assert f"background-color: {t['panel']};" in tone_header
        assert f"border-color: {t['border']};" in tone_header
        assert f"color: {t['text_muted']};" in meta
        assert "background-color: transparent;" in actions
        assert "border: none;" in actions
        assert "border-radius: 0px;" in actions
        assert "border-radius: 0px;" in buttons
        assert "min-height: 26px;" in buttons
        assert f"padding: 2px {t['space_sm']}px;" in buttons
        assert f"background-color: {t['panel_alt']};" in table
        assert "border-radius: 0px;" in table
        assert "background-color: transparent;" in detail
        assert "border: none;" in detail
        assert "border-radius: 0px;" in detail


def test_project_workspace_styles_use_engineering_surface_tokens():
    for mode in ("light", "dark"):
        t = theme_tokens(mode)
        css = _build_stylesheet(mode)

        header = css.split('#workspace_panel_header[panelTone="project"] {', 1)[1].split("}", 1)[0]
        eyebrow = css.split("#project_workspace_eyebrow {", 1)[1].split("}", 1)[0]
        metrics = css.split("#project_workspace_metrics_strip {", 1)[1].split("}", 1)[0]
        buttons = css.split("QPushButton#project_workspace_view_button {", 1)[1].split("}", 1)[0]

        _assert_panel_surface(header, t)
        _assert_default_border(header, t)
        assert f"color: {t['accent_hover']};" in eyebrow
        assert "background-color: transparent;" in metrics
        assert "border: none;" in metrics
        assert "border-radius: 0px;" in metrics
        assert "border-radius: 0px;" in buttons
        assert "padding: 2px 8px;" in buttons
        assert "min-height: 24px;" in buttons


@pytest.mark.skipif(not HAS_FLUENT, reason="qfluentwidgets not installed")
def test_apply_theme_patches_existing_fluent_widgets_with_engineering_radii():
    app = _app()
    widgets = [
        ("button", PushButton("Test")),
        ("line_edit", SearchLineEdit()),
        ("combo_box", ComboBox()),
        ("spin_box", SpinBox()),
    ]

    try:
        manager = _ensure_fluent_engineering_style_manager(app)
        assert manager is not None
        for _, widget in widgets:
            widget.show()
        app.processEvents()
        manager.refresh_all()
        app.processEvents()

        for expected_kind, widget in widgets:
            assert widget.property("_designer_fluent_engineering_style") == expected_kind

        assert "border-radius: 6px;" in widgets[0][1].styleSheet()
        assert "border-radius: 6px;" in widgets[1][1].styleSheet()
        assert "#lineEditButton" in widgets[1][1].styleSheet()
        assert "border-radius: 4px;" in widgets[1][1].styleSheet()
        assert "border-radius: 6px;" in widgets[2][1].styleSheet()
        assert "SpinButton" in widgets[3][1].styleSheet()
        assert "border-radius: 6px;" in widgets[3][1].styleSheet()
        assert "border-radius: 4px;" in widgets[3][1].styleSheet()
    finally:
        for _, widget in widgets:
            widget.close()
            widget.deleteLater()
        app.processEvents()


@pytest.mark.skipif(not HAS_FLUENT, reason="qfluentwidgets not installed")
def test_apply_theme_patches_new_fluent_widgets_after_theme_install():
    app = _app()
    manager = _ensure_fluent_engineering_style_manager(app)
    assert manager is not None

    button = PushButton("Later")
    search = SearchLineEdit()
    try:
        button.show()
        search.show()
        app.processEvents()

        assert button.property("_designer_fluent_engineering_style") == "button"
        assert search.property("_designer_fluent_engineering_style") == "line_edit"
        assert "border-radius: 6px;" in button.styleSheet()
        assert "border-radius: 6px;" in search.styleSheet()
    finally:
        button.close()
        button.deleteLater()
        search.close()
        search.deleteLater()
        app.processEvents()


def test_icon_semantic_dictionary_contains_core_workspace_keys():
    keys = set(semantic_icon_keys())
    assert {
        "nav.page_group",
        "nav.component_library",
        "nav.resource",
        "state.error",
        "state.warn",
        "state.info",
    }.issubset(keys)
