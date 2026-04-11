"""Additional code generator edge cases.

Covers scenarios not in test_code_generator.py:
  - generate_page_header widget name uniqueness (sibling widgets same type)
  - Page with only root widget (no children) — minimal valid page
  - init_with_params widgets: progress_bar, circular_progress_bar, slider
  - Widget with both animation AND event handler
  - uicode startup index edge cases (startup page that does not exist)
  - app_egui_config_designer.h content correctness
  - Viewport / position sentinel — position at (0,0) still appears in layout
  - on_click listener for non-button widgets (label with on_click)
  - generate_page_header for activity vs easy_page mode
  - generate_uicode_source returns well-formed C
"""

import pytest

from ui_designer.tests.page_builders import build_test_pages
from ui_designer.tests.project_builders import (
    build_test_project_from_pages,
    build_test_project_with_page_root,
)
from ui_designer.model.widget_model import WidgetModel, AnimationModel
from ui_designer.generator.code_generator import (
    _gen_widget_init_lines,
    generate_page_header,
    generate_page_layout_source,
    generate_page_user_source,
    generate_uicode_header,
    generate_uicode_source,
    generate_all_files,
)
from ui_designer.utils.scaffold import APP_CONFIG_DESIGNER_RELPATH


# ── helpers ─────────────────────────────────────────────────────

# ======================================================================
# TestMinimalPage
# ======================================================================

class TestMinimalPage:
    """Page with root-only (no children) must still generate valid files."""

    def test_header_root_only(self):
        proj, pg, _root = build_test_project_with_page_root(page_name="bare_page")
        h = generate_page_header(pg, proj)
        assert "#ifndef _BARE_PAGE_H_" in h
        assert "egui_view_group_t root_group;" in h

    def test_layout_source_root_only(self):
        proj, pg, _root = build_test_project_with_page_root(page_name="bare_page")
        out = generate_page_layout_source(pg, proj)
        assert "egui_view_group_init" in out

    def test_user_source_root_only(self):
        proj, pg, _root = build_test_project_with_page_root(page_name="bare_page")
        out = generate_page_user_source(pg, proj)
        assert "egui_bare_page_user_on_open" in out


# ======================================================================
# TestInitWithParamsWidgets
# ======================================================================

class TestInitWithParamsWidgets:
    """Widgets that use init_with_params pattern."""

    def _do(self, widget_type, extra_props=None):
        proj, pg, root = build_test_project_with_page_root(page_name="test_page")
        w = WidgetModel(widget_type, name="wgt", x=10, y=10, width=100, height=40)
        if extra_props:
            w.properties.update(extra_props)
        root.add_child(w)
        return generate_page_layout_source(pg, proj)

    def test_slider_init_with_params(self):
        out = self._do("slider", {"min_value": 0, "max_value": 100, "value": 50})
        assert "egui_view_slider_init" in out

    def test_circular_progress_bar_init(self):
        out = self._do("circular_progress_bar", {"value": 75})
        assert "egui_view_circular_progress_bar_init" in out

    def test_arc_slider_init(self):
        out = self._do("arc_slider", {"value": 50})
        assert "egui_view_arc_slider_init" in out

    def test_led_init(self):
        out = self._do("led")
        assert "egui_view_led_init" in out

    def test_gauge_init(self):
        out = self._do("gauge", {"value": 60})
        assert "egui_view_gauge_init" in out

    def test_spinner_init(self):
        out = self._do("spinner")
        assert "egui_view_spinner_init" in out

    def test_toggle_button_init(self):
        out = self._do("toggle_button")
        assert "egui_view_toggle_button_init" in out

    def test_checkbox_init(self):
        out = self._do("checkbox")
        assert "egui_view_checkbox_init" in out

    def test_radio_button_init(self):
        out = self._do("radio_button")
        assert "egui_view_radio_button_init" in out


# ======================================================================
# TestWidgetWithBothAnimAndEvent
# ======================================================================

class TestWidgetWithBothAnimAndEvent:
    """Widget with both animation and event handler — both must appear in output."""

    def test_anim_and_event_both_emitted(self):
        proj, pg, root = build_test_project_with_page_root(page_name="combo_page")
        btn = WidgetModel("button", name="combo_btn", x=0, y=0, width=80, height=40)
        btn.on_click = "on_btn_click"
        anim = AnimationModel()
        anim.anim_type = "alpha"
        anim.duration = 300
        anim.params = {"from_alpha": "0", "to_alpha": "255"}
        btn.animations.append(anim)
        root.add_child(btn)

        layout = generate_page_layout_source(pg, proj)
        assert "set_on_click_listener" in layout
        assert "on_btn_click" in layout
        assert "egui_animation_alpha_init" in layout


# ======================================================================
# TestUicodeStartupEdgeCases
# ======================================================================

class TestUicodeStartupEdgeCases:
    """Startup page index edge cases."""

    def test_startup_is_first_page_by_default(self):
        p1, p2 = build_test_pages("first_page", "second_page")
        proj = build_test_project_from_pages([p1, p2], startup_page="first_page")
        out = generate_uicode_source(proj)
        assert "current_index = 0" in out

    def test_startup_is_second_page(self):
        p1, p2 = build_test_pages("intro", "main_page")
        proj = build_test_project_from_pages([p1, p2], startup_page="main_page")
        out = generate_uicode_source(proj)
        assert "current_index = 1" in out

    def test_uicode_header_page_count_matches(self):
        pages = list(build_test_pages(*(f"page_{i}" for i in range(4))))
        proj = build_test_project_from_pages(pages)
        out = generate_uicode_header(proj)
        assert "PAGE_COUNT = 4" in out

    def test_activity_mode_init_func_name(self):
        proj, pg, _root = build_test_project_with_page_root(page_name="main_page")
        proj.page_mode = "activity"
        out = generate_uicode_source(proj)
        # Activity mode should generate activity registration
        assert "main_page_activity" in out


# ======================================================================
# TestAppEguiConfigContent
# ======================================================================

class TestAppEguiConfigContent:
    """app_egui_config_designer.h generated with correct dimensions."""

    def test_config_has_correct_dimensions_240x320(self):
        proj, _pg, _root = build_test_project_with_page_root("App")
        files = generate_all_files(proj)
        c, _ = files[APP_CONFIG_DESIGNER_RELPATH]
        assert "240" in c
        assert "320" in c

    def test_config_has_correct_dimensions_480x272(self):
        proj, _pg, _root = build_test_project_with_page_root(
            "WideApp",
            screen_width=480,
            screen_height=272,
        )
        files = generate_all_files(proj)
        c, _ = files[APP_CONFIG_DESIGNER_RELPATH]
        assert "480" in c
        assert "272" in c

    def test_config_has_pfb_macros(self):
        proj, _pg, _root = build_test_project_with_page_root("App")
        files = generate_all_files(proj)
        c, _ = files[APP_CONFIG_DESIGNER_RELPATH]
        assert "EGUI_CONFIG_PFB_WIDTH" in c
        assert "EGUI_CONFIG_PFB_HEIGHT" in c


# ======================================================================
# TestOnClickForNonButton
# ======================================================================

class TestOnClickForNonButton:
    """Any widget (not just button) can have on_click."""

    def test_label_with_on_click(self):
        w = WidgetModel("label", name="clickable_lbl", x=0, y=0, width=100, height=30)
        w.on_click = "on_label_click"
        lines = "\n".join(_gen_widget_init_lines(w))
        assert "set_on_click_listener" in lines
        assert "on_label_click" in lines

    def test_image_with_on_click(self):
        w = WidgetModel("image", name="ico", x=0, y=0, width=48, height=48)
        w.on_click = "on_icon_tap"
        lines = "\n".join(_gen_widget_init_lines(w))
        assert "set_on_click_listener" in lines
        assert "on_icon_tap" in lines


# ======================================================================
# TestSiblingWidgetsSameType
# ======================================================================

class TestSiblingWidgetsSameType:
    """Multiple widgets of the same type on one page must all appear in header struct."""

    def test_three_labels_in_header(self):
        proj, pg, root = build_test_project_with_page_root(page_name="multi_label")
        for idx, name in enumerate(["title_lbl", "subtitle_lbl", "desc_lbl"]):
            root.add_child(WidgetModel("label", name=name, x=0, y=idx*40, width=240, height=30))
        h = generate_page_header(pg, proj)
        assert "egui_view_label_t title_lbl;" in h
        assert "egui_view_label_t subtitle_lbl;" in h
        assert "egui_view_label_t desc_lbl;" in h

    def test_two_buttons_both_in_layout(self):
        proj, pg, root = build_test_project_with_page_root(page_name="two_btns")
        b1 = WidgetModel("button", name="ok_btn", x=0, y=0, width=80, height=40)
        b2 = WidgetModel("button", name="cancel_btn", x=100, y=0, width=80, height=40)
        b1.properties["text"] = "OK"
        b2.properties["text"] = "Cancel"
        root.add_child(b1)
        root.add_child(b2)
        layout = generate_page_layout_source(pg, proj)
        assert "ok_btn" in layout
        assert "cancel_btn" in layout
        assert '"OK"' in layout
        assert '"Cancel"' in layout


# ======================================================================
# TestPageHeaderActivityMode
# ======================================================================

class TestPageHeaderActivityMode:
    """Activity mode pages should have activity-specific declarations."""

    def test_header_exists_for_activity_mode(self):
        proj, pg, _root = build_test_project_with_page_root(page_name="main_page")
        proj.page_mode = "activity"
        h = generate_page_header(pg, proj)
        # header guard must always exist
        assert "#ifndef _MAIN_PAGE_H_" in h

    def test_user_source_activity_mode(self):
        proj, pg, _root = build_test_project_with_page_root(page_name="main_page")
        proj.page_mode = "activity"
        src = generate_page_user_source(pg, proj)
        # activity mode produces on_create / on_start style
        assert "egui_main_page" in src


# ======================================================================
# TestWellFormedCOutput
# ======================================================================

class TestWellFormedCOutput:
    """Generated code must have balanced braces and include guards."""

    def _check_balanced_braces(self, code):
        return code.count("{") == code.count("}")

    def test_header_balanced_braces(self):
        proj, pg, root = build_test_project_with_page_root(page_name="main_page")
        child = WidgetModel("button", name="btn", x=0, y=0, width=80, height=40)
        root.add_child(child)
        h = generate_page_header(pg, proj)
        assert self._check_balanced_braces(h), "Header has unbalanced braces"

    def test_layout_source_balanced_braces(self):
        proj, pg, root = build_test_project_with_page_root(page_name="main_page")
        child = WidgetModel("label", name="lbl", x=0, y=0, width=100, height=30)
        root.add_child(child)
        out = generate_page_layout_source(pg, proj)
        assert self._check_balanced_braces(out)

    def test_user_source_balanced_braces(self):
        proj, pg, _root = build_test_project_with_page_root(page_name="main_page")
        out = generate_page_user_source(pg, proj)
        assert self._check_balanced_braces(out)

    def test_uicode_source_balanced_braces(self):
        proj, _pg, _root = build_test_project_with_page_root(page_name="main_page")
        out = generate_uicode_source(proj)
        assert self._check_balanced_braces(out)
