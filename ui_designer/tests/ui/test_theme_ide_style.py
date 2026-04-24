"""IDE-style redesign token assertions (dark only).

Locks in the exact token values defined in the 2026-04-21 design spec so that
any regression is caught by pytest before it ships.
"""

from ui_designer.ui import theme as _theme_mod
from ui_designer.ui.theme import theme_tokens


def test_dark_palette_uses_zinc_and_blue500():
    t = theme_tokens("dark")
    # zinc scale
    assert t["bg"] == "#09090B"
    assert t["shell_bg"] == "#09090B"
    assert t["sidebar_bg"] == "#27272A"
    assert t["panel"] == "#18181B"
    assert t["panel_alt"] == "#27272A"
    assert t["panel_soft"] == "#3F3F46"
    assert t["panel_raised"] == "#27272A"
    assert t["surface"] == "#3F3F46"
    assert t["surface_hover"] == "#52525B"
    assert t["surface_pressed"] == "#71717A"
    assert t["canvas_bg"] == "#09090B"
    assert t["canvas_stage"] == "#09090B"
    assert t["border"] == "#3F3F46"
    assert t["border_strong"] == "#52525B"
    # blue-500 accent
    assert t["focus_ring"] == "#3B82F6"
    assert t["accent"] == "#3B82F6"
    assert t["accent_hover"] == "#60A5FA"
    # text
    assert t["text"] == "#D4D4D8"
    assert t["text_muted"] == "#A1A1AA"
    assert t["text_soft"] == "#71717A"
    # status colors
    assert t["danger"] == "#EF4444"
    assert t["success"] == "#22C55E"
    assert t["warning"] == "#EAB308"


def test_dark_selection_uses_rgba_blue500():
    t = theme_tokens("dark")
    assert t["selection"] == "rgba(59, 130, 246, 0.40)"
    assert t["selection_hover"] == "rgba(59, 130, 246, 0.10)"
    assert t["selection_soft"] == "rgba(59, 130, 246, 0.15)"
    assert t["selection_text"] == "#BFDBFE"
    assert t["accent_soft"] == "rgba(59, 130, 246, 0.15)"


def test_dark_typography_uses_compact_ide_scale():
    t = theme_tokens("dark")
    assert t["fs_display"] == 18
    assert t["fs_h1"] == 13
    assert t["fs_h2"] == 12
    assert t["fs_panel_title"] == 12
    assert t["fs_body"] == 12
    assert t["fs_body_sm"] == 11
    assert t["fs_caption"] == 10
    assert t["fs_micro"] == 10


def test_dark_spacing_and_radii_tightened():
    t = theme_tokens("dark")
    assert t["space_3xs"] == 2
    assert t["pad_btn_v"] == 2
    assert t["pad_btn_h"] == 8
    assert t["pad_input_v"] == 2
    assert t["pad_input_h"] == 6
    assert t["pad_tab_compact_v"] == 1
    assert t["pad_tab_compact_h"] == 5
    assert t["pad_toolbar_h"] == 3
    assert t["space_toolbar_separator"] == 1
    assert t["r_sm"] == 4
    assert t["r_md"] == 4
    assert t["r_lg"] == 4
    assert t["r_xl"] == 6
    assert t["r_2xl"] == 8
    assert t["r_3xl"] == 8


def test_light_palette_unchanged():
    """D2 decision: light theme must NOT be touched in this pass."""
    t = theme_tokens("light")
    assert t["bg"] == "#EEF2F6"
    assert t["accent"] == "#287DDA"
    assert t["selection_text"] == "#1D4ED8"
    assert t["fs_body"] == 13


def test_fluent_qss_templates_use_4px_radius_and_12px_font():
    """Buttons/inputs/combos must have 4px radius and 12px font (IDE density)."""
    expected_radius_px = theme_tokens("dark")["r_sm"]
    expected_font_px = theme_tokens("dark")["fs_body"]
    expected_input_pad_h = theme_tokens("dark")["pad_input_h"]
    fragments = [
        _theme_mod._FLUENT_BUTTON_RADIUS_QSS,
        _theme_mod._FLUENT_LINE_EDIT_RADIUS_QSS,
        _theme_mod._FLUENT_COMBO_BOX_RADIUS_QSS,
        _theme_mod._FLUENT_SPIN_BOX_RADIUS_QSS,
    ]
    for qss in fragments:
        assert f"border-radius: {expected_radius_px}px" in qss, f"missing token radius: {qss[:80]}"
        assert f"font-size: {expected_font_px}px" in qss, f"missing token body font: {qss[:80]}"
        assert "border-radius: 0px" not in qss
    for qss in (
        _theme_mod._FLUENT_LINE_EDIT_RADIUS_QSS,
        _theme_mod._FLUENT_COMBO_BOX_RADIUS_QSS,
        _theme_mod._FLUENT_SPIN_BOX_RADIUS_QSS,
    ):
        assert f"padding: 0px {expected_input_pad_h}px" in qss


def test_property_panel_qss_templates_use_4px_radius():
    expected_radius_px = theme_tokens("dark")["r_sm"]
    expected_input_pad_h = theme_tokens("dark")["pad_input_h"]
    fragments = [
        _theme_mod._FLUENT_PROPERTY_PANEL_BUTTON_QSS,
        _theme_mod._FLUENT_PROPERTY_PANEL_LINE_EDIT_QSS,
        _theme_mod._FLUENT_PROPERTY_PANEL_COMBO_BOX_QSS,
        _theme_mod._FLUENT_PROPERTY_PANEL_SPIN_BOX_QSS,
    ]
    for qss in fragments:
        assert f"border-radius: {expected_radius_px}px" in qss
        assert "border-radius: 0px" not in qss
    for qss in (
        _theme_mod._FLUENT_PROPERTY_PANEL_LINE_EDIT_QSS,
        _theme_mod._FLUENT_PROPERTY_PANEL_COMBO_BOX_QSS,
        _theme_mod._FLUENT_PROPERTY_PANEL_SPIN_BOX_QSS,
    ):
        assert f"padding: 0px {expected_input_pad_h}px" in qss


def test_dark_stylesheet_includes_ide_accent_features():
    css = _theme_mod._build_stylesheet("dark")
    # 顶部 2px 蓝条激活态
    assert "QTabBar::tab:selected" in css
    assert (
        "border-top: 2px solid #3B82F6" in css
        or "border-top: 2px solid rgb(59, 130, 246)" in css
    )
    # 半透明蓝选中
    assert "rgba(59, 130, 246, 0.15)" in css or "rgba(59, 130, 246, 0.40)" in css
    # 亮蓝文字（blue-200 #BFDBFE）
    assert "#BFDBFE" in css
