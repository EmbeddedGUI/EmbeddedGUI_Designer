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
