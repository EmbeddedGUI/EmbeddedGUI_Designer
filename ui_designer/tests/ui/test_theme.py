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
        metric_card = css.split("#status_center_metric_card {", 1)[1].split("}", 1)[0]

        assert "background-color: transparent;" in metrics
        assert "border: none;" in metrics
        assert "background-color: transparent;" in actions
        assert "border: none;" in actions
        assert f"background-color: {t['panel_soft']};" in metric_card
        assert "border: 1px solid transparent;" in metric_card


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
        assert int(tokens["r_md"]) == 8
        assert int(tokens["r_xl"]) == 10
        assert "999px" not in css

        chip = css.split("QToolButton#workspace_summary_indicator {", 1)[1].split("}", 1)[0]
        browser_card = css.split("#widget_browser_card {", 1)[1].split("}", 1)[0]
        metric_card = css.split("#status_center_metric_card {", 1)[1].split("}", 1)[0]

        assert f"border-radius: {tokens['r_md']}px;" in chip
        assert f"border-radius: {tokens['r_md']}px;" in browser_card
        assert f"border-radius: {tokens['r_md']}px;" in metric_card


def test_page_navigator_styles_use_token_driven_cards():
    for mode in ("light", "dark"):
        t = theme_tokens(mode)
        css = _build_stylesheet(mode)

        header = css.split("#page_navigator_header {", 1)[1].split("}", 1)[0]
        thumb = css.split("#page_navigator_thumbnail {", 1)[1].split("}", 1)[0]
        selected = css.split('#page_navigator_thumbnail[selected="true"] {', 1)[1].split("}", 1)[0]
        empty = css.split("#page_navigator_empty_state {", 1)[1].split("}", 1)[0]

        assert t["accent_soft"] in header or t["selection_soft"] in header
        assert f"border-radius: {t['r_xl']}px;" in header
        assert f"background-color: {t['panel_alt']};" in thumb
        assert f"border-radius: {t['r_xl']}px;" in thumb
        assert f"border-color: {t['accent']};" in selected
        assert f"border: 1px dashed {t['border']};" in empty


def test_editor_tabs_styles_use_engineering_shell_tokens():
    for mode in ("light", "dark"):
        t = theme_tokens(mode)
        css = _build_stylesheet(mode)

        header = css.split("#editor_tabs_header {", 1)[1].split("}", 1)[0]
        mode_strip = css.split("#editor_tabs_mode_strip {", 1)[1].split("}", 1)[0]
        editor = css.split("QPlainTextEdit#editor_tabs_xml_editor {", 1)[1].split("}", 1)[0]

        assert f"border-radius: {t['r_xl']}px;" in header
        assert t["selection_soft"] in header
        assert f"background-color: {t['panel_soft']};" in mode_strip
        assert f"background-color: {t['canvas_stage']};" in editor
        assert f"border-radius: {t['r_md']}px;" in editor


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
