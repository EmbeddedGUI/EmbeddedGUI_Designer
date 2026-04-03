from ui_designer.ui.iconography import semantic_icon_keys
from ui_designer.ui.theme import _build_stylesheet, theme_tokens


def test_build_stylesheet_uses_surface_hover_tokens_for_light_theme():
    tokens = theme_tokens("light")

    stylesheet = _build_stylesheet("light")

    assert tokens["surface_hover"] in stylesheet
    assert tokens["surface_hover"] == "#E8F0FA"
    assert tokens["surface_hover"] in stylesheet.split("#status_center_metric_card:hover", 1)[1]
    assert tokens["surface_hover"] in stylesheet.split("#status_center_health_row:hover", 1)[1]


def test_stylesheet_shell_and_dialog_hint_tokens():
    for mode in ("light", "dark"):
        t = theme_tokens(mode)
        css = _build_stylesheet(mode)
        assert "QLabel[hintTone=" in css
        assert t["success"] in css.split('QLabel[hintTone="success"]', 1)[1].split("}", 1)[0]
        assert "QTabBar::tab:selected" in css
        assert t["panel"] in css.split("QTabBar::tab:selected", 1)[1].split("}", 1)[0]
        nav = css.split("#workspace_nav_rail", 1)[1].split("}}", 1)[0]
        assert str(t["space_sm"]) in nav and str(t["space_xs"]) in nav
        chip = css.split("#workspace_status_chip {", 1)[1].split("}", 1)[0]
        assert str(t["space_xs"]) in chip and str(t["space_sm"]) in chip


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
        assert f"background-color: {t['panel_alt']};" in metric_card
        assert "border: 1px solid transparent;" in metric_card


def test_tokens_include_xxs_spacing_for_all_themes():
    for mode in ("light", "dark"):
        tokens = theme_tokens(mode)
        assert "space_xxs" in tokens
        assert int(tokens["space_xxs"]) == 2


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
