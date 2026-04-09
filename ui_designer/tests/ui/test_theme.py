import pytest
from PyQt5.QtWidgets import QApplication, QSpinBox

from ui_designer.ui.iconography import semantic_icon_keys
from ui_designer.ui.typography import apply_typography_role
from ui_designer.ui.theme import (
    _build_stylesheet,
    _ensure_fluent_engineering_style_manager,
    app_theme_tokens,
    apply_theme,
    designer_ui_font_family,
    qt_font_weight,
    designer_font_scale,
    designer_font_size_pt,
    scaled_point_size,
    theme_tokens,
)

try:
    from qfluentwidgets import ComboBox, PushButton, SearchLineEdit, SpinBox, ToolButton

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
    assert tokens["surface_hover"] in stylesheet.split("#welcome_recent_item:hover", 1)[1]
    assert tokens["surface_hover"] in stylesheet.split("QPushButton#widget_browser_insert_button:hover", 1)[1]


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
        nav_button = css.split('QPushButton[workspaceNav="true"] {', 1)[1].split("}", 1)[0]
        compact_panel_title = css.split("QWidget#project_workspace_panel QLabel#workspace_section_title,", 1)[1].split("}", 1)[0]
        assert str(t["space_xxs"]) in nav and str(t["space_xs"]) in nav
        assert f"font-size: {t['fs_body_sm']}px;" in nav_button
        assert f"font-size: {t['fs_body_sm']}px;" in compact_panel_title
        indicator = css.split("QToolButton#workspace_summary_indicator {", 1)[1].split("}", 1)[0]
        metrics = css.split("#preview_metrics_strip {", 1)[1].split("}", 1)[0]
        assert str(t["space_xs"]) in indicator


        assert "border-radius: 0px;" in metrics


def test_tokens_include_xxs_spacing_for_all_themes():
    for mode in ("light", "dark"):
        tokens = theme_tokens(mode)
        assert "space_xxs" in tokens
        assert int(tokens["space_xxs"]) == 4


def test_compact_typography_scale_stays_consistent():
    for mode in ("light", "dark"):
        t = theme_tokens(mode)
        roomy = theme_tokens(mode, "roomy")
        roomy_plus = theme_tokens(mode, "roomy_plus")
        css = _build_stylesheet(mode)

        property_title = css.split("#property_panel_title {", 1)[1].split("}", 1)[0]
        command_title = css.split("#workspace_command_title {", 1)[1].split("}", 1)[0]
        resource_title = css.split("#resource_panel_title {", 1)[1].split("}", 1)[0]
        project_title = css.split("#project_dock_title {", 1)[1].split("}", 1)[0]
        app_selector_title = css.split("#app_selector_title {", 1)[1].split("}", 1)[0]
        resource_dialog_title = css.split("#resource_dialog_title {", 1)[1].split("}", 1)[0]
        new_project_title = css.split("#new_project_title {", 1)[1].split("}", 1)[0]
        welcome_title = css.split("#welcome_hero_title {", 1)[1].split("}", 1)[0]
        welcome_subtitle = css.split("#welcome_hero_subtitle {", 1)[1].split("}", 1)[0]
        preview_title = css.split("#preview_title {", 1)[1].split("}", 1)[0]

        assert int(t["fs_h1"]) == 14
        assert int(t["fs_h2"]) == 13
        assert int(t["fs_panel_title"]) == 13
        assert int(t["fs_body"]) == 13
        assert int(t["fs_body_sm"]) == 12
        assert int(t["fs_caption"]) == 12
        assert int(roomy["fs_h1"]) == int(t["fs_h1"]) + 1
        assert int(roomy_plus["fs_h1"]) == int(t["fs_h1"]) + 2

        assert f"font-size: {t['fs_panel_title']}px;" in property_title
        assert f"font-weight: {t['fw_semibold']};" in property_title
        assert f"font-size: {t['fs_panel_title']}px;" in command_title
        assert f"font-size: {t['fs_panel_title']}px;" in resource_title
        assert f"font-size: {t['fs_panel_title']}px;" in project_title
        assert f"font-size: {t['fs_panel_title']}px;" in preview_title

        assert f"font-size: {t['fs_h1']}px;" in app_selector_title
        assert f"font-weight: {t['fw_semibold']};" in app_selector_title
        assert f"font-size: {t['fs_h1']}px;" in resource_dialog_title
        assert f"font-weight: {t['fw_semibold']};" in resource_dialog_title
        assert f"font-size: {t['fs_h1']}px;" in new_project_title
        assert f"font-size: {t['fs_h1']}px;" in welcome_title

        assert f"font-size: {t['fs_body']}px;" in welcome_subtitle
        assert f"font-weight: {t['fw_regular']};" in welcome_subtitle


def test_secondary_typography_uses_lighter_weights_for_dense_views():
    for mode in ("light", "dark"):
        t = theme_tokens(mode)
        css = _build_stylesheet(mode)

        property_grid_section = css.split("\n#property_grid_section_text {", 1)[1].split("}", 1)[0]
        resource_metric_label = css.split("#resource_panel_metric_label,", 1)[1].split("}", 1)[0]
        resource_metric_value = css.split("#resource_panel_metric_value {", 1)[1].split("}", 1)[0]
        resource_table_header = css.split("QTableWidget#resource_panel_table QHeaderView::section {", 1)[1].split("}", 1)[0]
        app_selector_label = css.split("#app_selector_metric_label,", 1)[1].split("}", 1)[0]
        app_selector_item_title = css.split("#app_selector_item_title {", 1)[1].split("}", 1)[0]
        app_selector_item_kind = css.split("#app_selector_item_kind {", 1)[1].split("}", 1)[0]
        welcome_eyebrow = css.split("#welcome_eyebrow {", 1)[1].split("}", 1)[0]
        welcome_metric_label = css.split("#welcome_metric_label {", 1)[1].split("}", 1)[0]
        welcome_metric_value = css.split("#welcome_metric_value {", 1)[1].split("}", 1)[0]
        welcome_recent_name = css.split("#welcome_recent_name {", 1)[1].split("}", 1)[0]

        assert f"font-weight: {t['fw_medium']};" in property_grid_section
        assert f"font-weight: {t['fw_regular']};" in resource_metric_label
        assert f"font-weight: {t['fw_medium']};" in resource_metric_value
        assert f"font-weight: {t['fw_medium']};" in resource_table_header
        assert f"font-weight: {t['fw_regular']};" in app_selector_label
        assert f"font-weight: {t['fw_medium']};" in app_selector_item_title
        assert f"font-weight: {t['fw_medium']};" in app_selector_item_kind
        assert f"font-weight: {t['fw_medium']};" in welcome_eyebrow
        assert f"font-weight: {t['fw_regular']};" in welcome_metric_label
        assert f"font-weight: {t['fw_medium']};" in welcome_metric_value
        assert f"font-weight: {t['fw_medium']};" in welcome_recent_name


def test_font_preference_scales_typography_tokens_consistently():
    base = theme_tokens("dark")
    scaled = theme_tokens("dark", font_size_pt=12)
    css = _build_stylesheet("dark", font_size_pt=12)

    welcome_title = css.split("#welcome_hero_title {", 1)[1].split("}", 1)[0]
    body = css.split("QLabel, QCheckBox, QRadioButton {", 1)[1].split("}", 1)[0]

    assert int(scaled["fs_body"]) > int(base["fs_body"])
    assert int(scaled["fs_h1"]) > int(base["fs_h1"])
    assert f"font-size: {scaled['fs_h1']}px;" in welcome_title
    assert f"font-size: {scaled['fs_body']}px;" in body


def test_font_scale_helpers_follow_app_preference():
    app = _app()
    app.setProperty("designer_font_size_pt", 12)
    app.setProperty("designer_theme_mode", "light")
    app.setProperty("designer_ui_density", "roomy")
    try:
        assert designer_font_size_pt(app, default=9) == 12
        assert designer_font_scale(app, default_pt=9) == pytest.approx(12 / 9)
        assert scaled_point_size(7, app=app, default_pt=9, minimum=1) == 9
        tokens = app_theme_tokens(app)
        assert int(tokens["fs_body"]) > int(theme_tokens("light")["fs_body"])
    finally:
        app.setProperty("designer_font_size_pt", 0)
        app.setProperty("designer_theme_mode", None)
        app.setProperty("designer_ui_density", None)


def test_windows_ui_font_family_prefers_segoe_for_designer_surfaces():
    family = designer_ui_font_family(
        available_families={"Segoe UI Variable Text", "Segoe UI", "Microsoft YaHei UI", "Arial"},
        platform_name="win32",
    )
    assert family == "Segoe UI Variable Text"


def test_windows_ui_font_family_falls_back_to_yahei_when_segoe_is_unavailable():
    family = designer_ui_font_family(
        available_families={"Microsoft YaHei UI", "Arial"},
        platform_name="win32",
    )
    assert family == "Microsoft YaHei UI"


def test_apply_typography_role_uses_active_density_and_font_preference():
    from PyQt5.QtWidgets import QLabel

    app = _app()
    app.setProperty("designer_theme_mode", "light")
    app.setProperty("designer_ui_density", "roomy")
    app.setProperty("designer_font_size_pt", 12)
    label = QLabel("Meta")
    try:
        expected = theme_tokens("light", density="roomy", font_size_pt=12)

        assert apply_typography_role(label, "meta") is True
        assert label.font().pixelSize() == int(expected["fs_body_sm"])
        assert label.font().weight() == int(qt_font_weight(expected["fw_regular"]))
    finally:
        label.deleteLater()
        app.setProperty("designer_theme_mode", None)
        app.setProperty("designer_ui_density", None)
        app.setProperty("designer_font_size_pt", 0)


def test_qt_font_weight_maps_css_scale_to_qfont_weights():
    assert int(qt_font_weight(400)) > 0
    assert int(qt_font_weight(500)) > int(qt_font_weight(400))
    assert int(qt_font_weight(700)) > int(qt_font_weight(500))


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
        insert_button = css.split("QPushButton#widget_browser_insert_button {", 1)[1].split("}", 1)[0]
        status_button = css.split("QPushButton#preview_status_button {", 1)[1].split("}", 1)[0]

        assert "border-radius: 0px;" in chip
        assert "padding: 1px 4px;" in chip
        assert "min-height: 24px;" in chip
        assert "border-radius: 0px;" in browser_card
        assert "border-radius: 0px;" in insert_button
        assert "border-radius: 0px;" in status_button


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
        page_name = css.split("#page_navigator_page_name {", 1)[1].split("}", 1)[0]

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
        assert f"font-size: {t['fs_body_sm']}px;" in page_name


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
        assert "min-height: 20px;" in buttons
        assert "max-height: 20px;" in buttons
        assert f"padding: 0px {t['space_sm']}px;" in buttons


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
        assert "min-height: 20px;" in buttons
        assert "max-height: 20px;" in buttons
        assert f"padding: 0px {t['space_sm']}px;" in buttons


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
        assert "padding: 0px 4px;" in toolbar_button
        assert "min-height: 20px;" in toolbar_button
        assert f"background-color: {t['surface_hover']};" in toolbar_button_hover
        assert "min-width: 1px;" in host_separator
        assert "max-width: 1px;" in host_separator
        assert "margin-left: 2px;" in host_separator
        assert "margin-right: 2px;" in host_separator
        assert "background-color: transparent;" in insert_button
        assert "border-radius: 0px;" in insert_button
        assert "padding: 0px 8px;" in insert_button
        assert "min-width: 52px;" in insert_button
        assert "max-width: 52px;" in insert_button
        assert "min-height: 20px;" in insert_button
        assert "max-height: 20px;" in insert_button
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
        nav_button = css.split('QPushButton[workspaceNav="true"] {', 1)[1].split("}", 1)[0]
        status_chip = css.split("#workspace_status_chip {", 1)[1].split("}", 1)[0]
        search_shell = css.split("QFrame#property_panel_search_shell {", 1)[1].split("}", 1)[0]
        empty_state = css.split("#property_panel_empty_state {", 1)[1].split("}", 1)[0]
        resource_tabs_pane = css.split("QTabWidget#resource_panel_tabs::pane {", 1)[1].split("}", 1)[0]
        resource_tabs_tab = css.split("QTabWidget#resource_panel_tabs QTabBar::tab {", 1)[1].split("}", 1)[0]
        resource_details_pane = css.split("QTabWidget#resource_panel_details_tabs::pane {", 1)[1].split("}", 1)[0]
        resource_details_tab = css.split("QTabWidget#resource_panel_details_tabs QTabBar::tab {", 1)[1].split("}", 1)[0]
        resource_control_shell = css.split("#resource_panel_shell QPushButton,", 1)[1].split("}", 1)[0]
        resource_dialog_control_shell = css.split("#resource_dialog_shell QPushButton,", 1)[1].split("}", 1)[0]
        inspector_tabs_pane = css.split("QTabWidget#workspace_inspector_tabs::pane {", 1)[1].split("}", 1)[0]
        inspector_tabs_tab = css.split("QTabWidget#workspace_inspector_tabs QTabBar::tab {", 1)[1].split("}", 1)[0]
        bottom_tabs_pane = css.split("QTabWidget#workspace_bottom_tabs::pane {", 1)[1].split("}", 1)[0]
        bottom_tabs_tab = css.split("QTabWidget#workspace_bottom_tabs QTabBar::tab {", 1)[1].split("}", 1)[0]
        thumb_surface = css.split("QFrame#page_navigator_thumb_surface {", 1)[1].split("}", 1)[0]
        thumb_label = css.split("QLabel#page_navigator_thumb_label {", 1)[1].split("}", 1)[0]

        assert "border-radius: 0px;" in mode_button
        assert "min-width: 52px;" in mode_button
        assert "max-width: 52px;" in mode_button
        assert "min-height: 20px;" in mode_button
        assert "max-height: 20px;" in mode_button
        assert "border-radius: 0px;" in bottom_toggle_button
        assert "min-width: 48px;" in bottom_toggle_button
        assert "min-height: 20px;" in bottom_toggle_button
        assert "max-height: 20px;" in bottom_toggle_button
        assert "border-radius: 0px;" in nav_button
        assert "min-width: 56px;" in nav_button
        assert "max-width: 56px;" in nav_button
        assert "min-height: 20px;" in nav_button
        assert "max-height: 20px;" in nav_button
        assert "border-radius: 0px;" in status_chip
        assert "background-color: transparent;" in empty_state
        assert "border-top: 1px solid" in empty_state
        assert "border-right: none;" in empty_state
        assert "border-bottom: none;" in empty_state
        assert "border-left: none;" in empty_state
        assert "background-color: transparent;" in search_shell
        assert "border: none;" in search_shell
        assert "border-radius: 0px;" in search_shell
        assert "border-radius: 0px;" in empty_state
        assert "background-color: transparent;" in resource_tabs_pane
        assert "border: none;" in resource_tabs_pane
        assert "border-radius: 0px;" in resource_tabs_pane
        assert "border-radius: 0px;" in resource_control_shell
        assert "border-radius: 0px;" in resource_dialog_control_shell
        assert "border-radius: 0px;" in resource_tabs_tab
        assert "margin-right: 0px;" in resource_tabs_tab
        assert "min-height: 26px;" in resource_tabs_tab
        assert "padding: 4px 10px;" in resource_tabs_tab
        assert "background-color: transparent;" in resource_details_pane
        assert "border: none;" in resource_details_pane
        assert "border-radius: 0px;" in resource_details_pane
        assert "border-radius: 0px;" in resource_details_tab
        assert "margin-right: 0px;" in resource_details_tab
        assert "min-height: 26px;" in resource_details_tab
        assert "padding: 4px 10px;" in resource_details_tab
        assert "background-color: transparent;" in inspector_tabs_pane
        assert "border: none;" in inspector_tabs_pane
        assert "border-radius: 0px;" in inspector_tabs_pane
        assert "padding: 0px;" in inspector_tabs_pane
        assert "top: 0px;" in inspector_tabs_pane
        assert "border-radius: 0px;" in inspector_tabs_tab
        assert "margin-right: 0px;" in inspector_tabs_tab
        assert "min-height: 24px;" in inspector_tabs_tab
        assert "padding: 2px 6px;" in inspector_tabs_tab
        assert "background-color: transparent;" in bottom_tabs_pane
        assert "border: none;" in bottom_tabs_pane
        assert "border-radius: 0px;" in bottom_tabs_pane
        assert "padding: 0px;" in bottom_tabs_pane
        assert "top: 0px;" in bottom_tabs_pane
        assert "border-radius: 0px;" in bottom_tabs_tab
        assert "margin-right: 0px;" in bottom_tabs_tab
        assert "min-height: 24px;" in bottom_tabs_tab
        assert "padding: 2px 6px;" in bottom_tabs_tab
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
        metric_accent = css.split('QFrame#property_panel_metric_card[metricTone="accent"] {', 1)[1].split("}", 1)[0]
        metric_success = css.split('QFrame#property_panel_metric_card[metricTone="success"] {', 1)[1].split("}", 1)[0]
        metric_warning = css.split('QFrame#property_panel_metric_card[metricTone="warning"] {', 1)[1].split("}", 1)[0]
        metric_danger = css.split('QFrame#property_panel_metric_card[metricTone="danger"] {', 1)[1].split("}", 1)[0]
        property_chip = css.split('#workspace_status_chip[chipVariant="property"] {', 1)[1].split("}", 1)[0]
        property_chip_accent = css.split('#workspace_status_chip[chipVariant="property"][chipTone="accent"] {', 1)[1].split("}", 1)[0]
        property_chip_success = css.split('#workspace_status_chip[chipVariant="property"][chipTone="success"] {', 1)[1].split("}", 1)[0]
        property_chip_warning = css.split('#workspace_status_chip[chipVariant="property"][chipTone="warning"] {', 1)[1].split("}", 1)[0]
        property_chip_danger = css.split('#workspace_status_chip[chipVariant="property"][chipTone="danger"] {', 1)[1].split("}", 1)[0]
        metric_label = css.split("#property_panel_metric_label {", 1)[1].split("}", 1)[0]
        metric_value = css.split("#property_panel_metric_value {", 1)[1].split("}", 1)[0]
        inspector_group = css.split("QGroupBox#inspector_collapsible_group {", 1)[1].split("}", 1)[0]
        inspector_group_title = css.split("QGroupBox#inspector_collapsible_group::title {", 1)[1].split("}", 1)[0]
        inspector_group_indicator = css.split("QGroupBox#inspector_collapsible_group::indicator {", 1)[1].split("}", 1)[0]
        property_tree = css.split("QTreeWidget#property_panel_tree {", 1)[1].split("}", 1)[0]
        property_tree_item = css.split("QTreeWidget#property_panel_tree::item {", 1)[1].split("}", 1)[0]
        property_tree_header = css.split("QTreeWidget#property_panel_tree QHeaderView::section {", 1)[1].split("}", 1)[0]
        property_grid_section = css.split("QFrame#property_grid_section_cell {", 1)[1].split("}", 1)[0]
        property_grid_section_expanded = css.split('QFrame#property_grid_section_cell[sectionExpanded="true"] {', 1)[1].split("}", 1)[0]
        property_grid_section_fill = css.split("QFrame#property_grid_section_fill {", 1)[1].split("}", 1)[0]
        property_grid_section_fill_expanded = css.split('QFrame#property_grid_section_fill[sectionExpanded="true"] {', 1)[1].split("}", 1)[0]
        property_grid_section_hover = css.split('QFrame#property_grid_section_cell[sectionHovered="true"],', 1)[1].split("}", 1)[0]
        property_grid_section_text = css.split("\n#property_grid_section_text {", 1)[1].split("}", 1)[0]
        property_grid_section_text_expanded = css.split('\n#property_grid_section_text[sectionExpanded="true"] {', 1)[1].split("}", 1)[0]
        property_grid_section_indicator_button = css.split("QToolButton#property_grid_section_indicator {", 1)[1].split("}", 1)[0]
        property_grid_section_indicator = css.split("\n#property_grid_section_indicator {", 1)[1].split("}", 1)[0]
        property_grid_section_indicator_expanded = css.split('#property_grid_section_indicator[sectionExpanded="true"] {', 1)[1].split("}", 1)[0]
        property_grid_section_indicator_hover = css.split('#property_grid_section_text[sectionHovered="true"],', 1)[1].split("}", 1)[0]
        property_grid_label = css.split("QFrame#property_grid_label_cell {", 1)[1].split("}", 1)[0]
        property_grid_odd = css.split('QFrame#property_grid_label_cell[rowStripe="odd"],', 1)[1].split("}", 1)[0]
        property_grid_label_text = css.split("#property_grid_label_text {", 1)[1].split("}", 1)[0]
        property_grid_accent = css.split('QFrame#property_grid_label_cell[rowTone="accent"],', 1)[1].split("}", 1)[0]
        property_grid_warning = css.split('QFrame#property_grid_label_cell[rowTone="warning"],', 1)[1].split("}", 1)[0]
        property_grid_danger = css.split('QFrame#property_grid_label_cell[rowTone="danger"],', 1)[1].split("}", 1)[0]
        property_grid_hover = css.split('QFrame#property_grid_label_cell[hoverActive="true"],', 1)[1].split("}", 1)[0]
        property_grid_focus = css.split('QFrame#property_grid_label_cell[focusActive="true"] {', 1)[1].split("}", 1)[0]
        search_shell = css.split("QFrame#property_panel_search_shell {", 1)[1].split("}", 1)[0]

        _assert_panel_surface(header, t)
        _assert_default_border(header, t)
        assert "background-color: transparent;" in hint_strip
        assert "border-top: none;" in hint_strip
        assert "border-right: none;" in hint_strip
        assert "border-bottom: none;" in hint_strip
        assert f"border-left: 2px solid {t['border_strong']};" in hint_strip
        assert "background-color: transparent;" in search_shell
        assert "border: none;" in search_shell
        assert "background-color: transparent;" in property_tree
        assert "border: none;" in property_tree
        assert "padding: 0px;" in property_tree
        assert f"border-bottom: 1px solid {t['border']};" in property_tree_item
        assert "min-height: 24px;" in property_tree_item
        assert f"background-color: {t['panel_alt']};" in property_tree_header
        assert f"color: {t['text_muted']};" in property_tree_header
        assert f"background-color: {t['panel_alt']};" in property_grid_section
        assert f"border-top: 1px solid {t['border_strong']};" in property_grid_section
        assert f"background-color: {t['panel_raised']};" in property_grid_section_expanded
        assert f"border-bottom: 1px solid {t['accent']};" in property_grid_section_expanded
        assert f"background-color: {t['panel_alt']};" in property_grid_section_fill
        assert f"border-left: 1px solid {t['border_strong']};" in property_grid_section_fill
        assert f"background-color: {t['panel_raised']};" in property_grid_section_fill_expanded
        assert f"background-color: {t['surface_hover']};" in property_grid_section_hover
        assert f"color: {t['text']};" in property_grid_section_text
        assert f"color: {t['accent_hover']};" in property_grid_section_text_expanded
        assert "background-color: transparent;" in property_grid_section_indicator_button
        assert "border: none;" in property_grid_section_indicator_button
        assert f"color: {t['text_soft']};" in property_grid_section_indicator
        assert f"color: {t['accent_hover']};" in property_grid_section_indicator_expanded
        assert f"color: {t['text']};" in property_grid_section_indicator_hover
        assert f"background-color: {t['panel']};" in property_grid_label
        assert f"border-right: 1px solid {t['border_strong']};" in property_grid_label
        assert f"border-bottom: 1px solid {t['border']};" in property_grid_label
        assert f"background-color: {t['panel_alt']};" in property_grid_odd
        assert f"color: {t['text_muted']};" in property_grid_label_text
        assert f"background-color: {t['accent_soft']};" in property_grid_accent
        assert f"background-color: {t['panel_soft']};" in property_grid_warning
        assert f"background-color: {t['selection_soft']};" in property_grid_danger
        assert f"background-color: {t['surface_hover']};" in property_grid_hover
        assert f"border-left: 2px solid {t['focus_ring']};" in property_grid_focus
        assert "background-color: transparent;" in property_chip
        assert f"border-top: 1px solid {t['border']};" in property_chip
        assert "border-right: none;" in property_chip
        assert "border-bottom: none;" in property_chip
        assert "border-left: none;" in property_chip
        assert "background-color: transparent;" in property_chip_accent
        assert f"border-top-color: {t['accent']};" in property_chip_accent
        assert "background-color: transparent;" in property_chip_success
        assert f"border-top-color: {t['success']};" in property_chip_success
        assert "background-color: transparent;" in property_chip_warning
        assert f"border-top-color: {t['warning']};" in property_chip_warning
        assert "background-color: transparent;" in property_chip_danger
        assert f"border-top-color: {t['danger']};" in property_chip_danger
        assert "background-color: transparent;" in metric_card
        assert f"border-top: 1px solid {t['border']};" in metric_card
        assert "border-right: none;" in metric_card
        assert "border-bottom: none;" in metric_card
        assert "border-left: none;" in metric_card
        assert "border-radius: 0px;" in metric_card
        assert "background-color: transparent;" in metric_accent
        assert f"border-top-color: {t['accent']};" in metric_accent
        assert "background-color: transparent;" in metric_success
        assert f"border-top-color: {t['success']};" in metric_success
        assert "background-color: transparent;" in metric_warning
        assert f"border-top-color: {t['warning']};" in metric_warning
        assert "background-color: transparent;" in metric_danger
        assert f"border-top-color: {t['danger']};" in metric_danger
        assert f"color: {t['text_muted']};" in metric_label
        assert f"font-size: {t['fs_caption']}px;" in metric_label
        assert f"font-size: {t['fs_body_sm']}px;" in metric_value
        assert f"font-weight: {t['fw_medium']};" in metric_value
        assert "background-color: transparent;" in inspector_group
        assert "border: 1px solid transparent;" in inspector_group
        assert "border-radius: 0px;" in inspector_group
        assert "margin-top: 14px;" in inspector_group
        assert "padding-top: 4px;" in inspector_group
        assert "left: 0px;" in inspector_group_title
        assert "padding: 0px 0px 2px 0px;" in inspector_group_title
        assert "width: 0px;" in inspector_group_indicator
        assert "height: 0px;" in inspector_group_indicator


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
        assert "padding: 2px 6px;" in controls
        assert "min-height: 26px;" in controls
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




def test_widget_browser_styles_use_engineering_panel_tokens():
    for mode in ("light", "dark"):
        t = theme_tokens(mode)
        css = _build_stylesheet(mode)

        header = css.split("#workspace_panel_header,", 1)[1].split("}", 1)[0]
        tone_header = css.split('#widget_browser_header[panelTone="components"] {', 1)[1].split("}", 1)[0]
        meta = css.split("#widget_browser_header_meta {", 1)[1].split("}", 1)[0]
        target = css.split("#widget_browser_header_target {", 1)[1].split("}", 1)[0]
        metrics = css.split("#widget_browser_metrics_strip {", 1)[1].split("}", 1)[0]
        filter_bar = css.split("#widget_browser_filter_bar {", 1)[1].split("}", 1)[0]
        card = css.split("#widget_browser_card {", 1)[1].split("}", 1)[0]
        card_title = css.split("#widget_browser_card_title {", 1)[1].split("}", 1)[0]
        insert_button = css.split("QPushButton#widget_browser_insert_button {", 1)[1].split("}", 1)[0]

        _assert_panel_surface(header, t)
        _assert_default_border(header, t)
        assert "border-radius: 0px;" in header
        assert f"background-color: {t['panel']};" in tone_header
        assert f"border-color: {t['border']};" in tone_header
        assert f"color: {t['text_muted']};" in meta
        assert "background-color: transparent;" in target
        assert "border: none;" in target
        assert f"color: {t['text_soft']};" in target
        assert f"font-size: {t['fs_body_sm']}px;" in target
        assert "background-color: transparent;" in metrics
        assert "border: none;" in metrics
        assert "border-radius: 0px;" in metrics
        assert "background-color: transparent;" in filter_bar
        assert "border: none;" in filter_bar
        assert "border-radius: 0px;" in filter_bar
        assert "background-color: transparent;" in card
        assert "border-radius: 0px;" in card
        assert f"font-size: {t['fs_body']}px;" in card_title
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
        structure_label = css.split("#structure_panel_label {", 1)[1].split("}", 1)[0]
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
        assert f"font-size: {t['fs_body_sm']}px;" in structure_label
        assert "border-radius: 0px;" in buttons
        assert "min-height: 26px;" in buttons
        assert f"padding: 2px {t['space_sm']}px;" in buttons
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
        assert "min-height: 24px;" in buttons
        assert f"padding: 1px {t['space_sm']}px;" in buttons
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
        assert "min-height: 24px;" in button
        assert f"padding: 1px {t['space_sm']}px;" in button
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
        assert "min-height: 20px;" in buttons
        assert "max-height: 20px;" in buttons
        assert f"padding: 0px {t['space_sm']}px;" in buttons
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
        assert f"font-size: {t['fs_body']}px;" in buttons
        assert "padding: 0px 6px;" in buttons
        assert "min-height: 20px;" in buttons
        assert "max-height: 20px;" in buttons


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

        assert "border-radius: 0px;" in widgets[0][1].styleSheet()
        assert "border-radius: 0px;" in widgets[1][1].styleSheet()
        assert "#lineEditButton" in widgets[1][1].styleSheet()
        assert "border-radius: 0px;" in widgets[1][1].styleSheet()
        assert "border-radius: 0px;" in widgets[2][1].styleSheet()
        assert "SpinButton" in widgets[3][1].styleSheet()
        assert "border-radius: 0px;" in widgets[3][1].styleSheet()
        assert "border-radius: 0px;" in widgets[3][1].styleSheet()
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
        assert "border-radius: 0px;" in button.styleSheet()
        assert "border-radius: 0px;" in search.styleSheet()
    finally:
        button.close()
        button.deleteLater()
        search.close()
        search.deleteLater()
        app.processEvents()


@pytest.mark.skipif(not HAS_FLUENT, reason="qfluentwidgets not installed")
def test_apply_theme_flattens_property_panel_fluent_widgets():
    from ui_designer.model.widget_model import WidgetModel
    from ui_designer.ui.property_panel import PropertyPanel

    app = _app()
    apply_theme(app)

    panel = PropertyPanel()
    panel.set_widget(WidgetModel("label", name="title", x=10, y=20, width=80, height=24))

    try:
        panel.show()
        app.processEvents()

        search = panel._search_edit
        name_edit = panel._editors["name"]
        alpha_combo = panel._editors["prop_alpha"]
        x_spin = panel._editors["x"]
        browse_button = next(
            button for button in panel.findChildren(ToolButton) if button.text() == "Pick"
        )

        assert search.property("_designer_fluent_engineering_style") == "property_panel_line_edit"
        assert name_edit.property("_designer_fluent_engineering_style") == "property_panel_line_edit"
        assert alpha_combo.property("_designer_fluent_engineering_style") == "property_panel_combo_box"
        assert isinstance(x_spin, QSpinBox)
        assert x_spin.property("propertyPanelSpin") is True
        assert browse_button.property("_designer_fluent_engineering_style") == "property_panel_button"

        assert "#lineEditButton" in search.styleSheet()
        assert "border-radius: 0px;" in search.styleSheet()
        assert "min-height: 24px;" in search.styleSheet()
        assert "padding: 0px 6px;" in search.styleSheet()
        assert "min-width: 18px;" in search.styleSheet()
        assert "border-radius: 0px;" in name_edit.styleSheet()
        assert "min-height: 24px;" in name_edit.styleSheet()
        assert "border-radius: 0px;" in alpha_combo.styleSheet()
        assert "min-height: 24px;" in alpha_combo.styleSheet()
        assert x_spin.minimumHeight() >= 24
        assert "border-radius: 0px;" in browse_button.styleSheet()
        assert "min-height: 22px;" in browse_button.styleSheet()
        assert "padding: 1px 6px;" in browse_button.styleSheet()
    finally:
        panel.close()
        panel.deleteLater()
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
