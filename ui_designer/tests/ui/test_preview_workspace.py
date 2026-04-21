"""Qt UI smoke tests for preview fallback and workspace-aware build gating."""

import pytest

from ui_designer.tests.page_builders import (
    build_test_page_root_with_widgets,
    build_test_page_with_widget,
)
from ui_designer.tests.qt_test_utils import HAS_PYQT5, skip_if_no_qt
from ui_designer.tests.ui.window_test_helpers import close_test_window as _dispose_widget
from ui_designer.utils.scaffold import add_widget_children

if HAS_PYQT5:
    from PyQt5.QtCore import QEvent, QPoint, QPointF, QRect, Qt
    from PyQt5.QtGui import QContextMenuEvent, QMouseEvent
    from PyQt5.QtWidgets import QScrollArea

_skip_no_qt = skip_if_no_qt


def _mouse_event(event_type, pos, *, button=Qt.LeftButton, buttons=Qt.LeftButton, modifiers=Qt.NoModifier):
    return QMouseEvent(event_type, QPointF(pos), button, buttons, modifiers)


@_skip_no_qt
class TestPreviewPanelFallback:
    def test_preview_canvas_shells_use_compact_layouts(self, qapp):
        from ui_designer.ui.preview_panel import PreviewPanel

        panel = PreviewPanel(screen_width=240, screen_height=320)

        content_margins = panel._content.layout().contentsMargins()
        preview_shell_margins = panel._preview_shell.layout().contentsMargins()
        overlay_shell_margins = panel._overlay_shell.layout().contentsMargins()

        assert content_margins.left() == 2
        assert content_margins.top() == 2
        assert content_margins.right() == 2
        assert content_margins.bottom() == 2
        assert panel._content.layout().spacing() == 2
        assert preview_shell_margins.left() == 2
        assert preview_shell_margins.top() == 2
        assert preview_shell_margins.right() == 2
        assert preview_shell_margins.bottom() == 2
        assert overlay_shell_margins.left() == 2
        assert overlay_shell_margins.top() == 2
        assert overlay_shell_margins.right() == 2
        assert overlay_shell_margins.bottom() == 2
        _dispose_widget(panel)

    def test_preview_metrics_strip_uses_flat_compact_layout(self, qapp):
        from ui_designer.ui.preview_panel import PreviewPanel

        panel = PreviewPanel(screen_width=240, screen_height=320)

        margins = panel._metrics_frame.layout().contentsMargins()

        assert margins.left() == 2
        assert margins.top() == 2
        assert margins.right() == 2
        assert margins.bottom() == 2
        assert panel._metrics_frame.layout().spacing() == 2
        _dispose_widget(panel)

    def test_preview_status_bar_uses_compact_flat_controls(self, qapp):
        from ui_designer.ui.preview_panel import PreviewPanel

        panel = PreviewPanel(screen_width=240, screen_height=320)

        margins = panel._status_bar.layout().contentsMargins()

        assert margins.left() == 2
        assert margins.top() == 2
        assert margins.right() == 2
        assert margins.bottom() == 2
        assert panel._status_bar.layout().spacing() == 2
        assert panel._btn_zoom_out.width() == 24
        assert panel._btn_zoom_out.height() == 24
        assert panel._btn_zoom_in.width() == 24
        assert panel._btn_zoom_in.height() == 24
        _dispose_widget(panel)

    def test_preview_panel_exposes_initial_accessibility_metadata(self, qapp):
        from ui_designer.ui.preview_panel import PreviewPanel

        panel = PreviewPanel(screen_width=240, screen_height=320)
        header_layout = panel._header_frame.layout()
        header_margins = header_layout.contentsMargins()

        assert panel._zoom_label.text() == "100% (8px)"
        assert panel._main_layout.spacing() == 2
        assert header_margins.left() == 6
        assert header_margins.top() == 6
        assert header_margins.right() == 6
        assert header_margins.bottom() == 6
        assert header_layout.spacing() == 2
        assert panel.accessibleName() == (
            "Preview panel: Preview - waiting for exe.... Mode: Horizontal split. "
            "Zoom: 100% (8px). Grid: on. Pointer: Pointer idle."
        )
        assert panel._eyebrow_label.accessibleName() == "Preview workspace."
        assert panel._eyebrow_label.isHidden() is True
        assert panel._header_frame.accessibleName() == f"Preview header. {panel.accessibleName()}"
        assert panel._header_meta_label.accessibleName() == panel._header_meta_label.text()
        assert panel._header_meta_label.isHidden() is True
        assert panel._metrics_frame.isHidden() is True
        assert panel._metrics_frame.accessibleName() == (
            "Preview metrics: Horizontal split. Grid on. Pointer status: Pointer idle."
        )
        assert panel._mode_chip.isHidden() is True
        assert panel._mode_chip.accessibleName() == "Preview mode: Horizontal split"
        assert panel._grid_chip.isHidden() is True
        assert panel._grid_chip.accessibleName() == "Preview grid: on"
        assert panel._pointer_chip.isHidden() is True
        assert panel._pointer_chip.accessibleName() == "Preview pointer summary: Pointer idle"
        assert panel.status_label.accessibleName() == "Preview status: Preview - waiting for exe..."
        assert panel.preview_frame.accessibleName() == "Preview frame: Preview - waiting for exe.... Mode: Horizontal split."
        assert panel._preview_label.accessibleName() == "Rendered preview surface: Preview - waiting for exe..."
        assert panel.overlay.accessibleName() == "Preview overlay: Horizontal split. Zoom: 100% (8px). Grid: on."
        assert panel._overlay_scroll.accessibleName() == "Preview overlay canvas: Horizontal split. Zoom: 100% (8px). Grid: on."
        assert panel._status_bar.accessibleName() == "Preview controls: Zoom 100% (8px). Pointer Pointer idle."
        assert panel._btn_zoom_out.toolTip() == "Zoom out preview (Ctrl+-). Current zoom: 100% (8px)."
        assert panel._btn_zoom_in.toolTip() == "Zoom in preview (Ctrl+=). Current zoom: 100% (8px)."
        assert panel._btn_zoom_out.accessibleName() == "Zoom out preview: current zoom 100% (8px)"
        assert panel._btn_zoom_in.accessibleName() == "Zoom in preview: current zoom 100% (8px)"
        _dispose_widget(panel)

    def test_show_python_preview_sets_pixmap_and_status(self, qapp):
        from ui_designer.ui.preview_panel import PreviewPanel

        page, label = build_test_page_with_widget(
            "main_page",
            name="label",
            x=10,
            y=10,
            width=100,
            height=20,
        )
        label.properties["text"] = "Hello"

        panel = PreviewPanel(screen_width=240, screen_height=320)
        panel.show_python_preview(page, "fallback")

        assert panel.is_python_preview_active() is True
        assert panel._preview_label.pixmap() is not None
        assert "Python fallback" in panel.status_label.text()
        _dispose_widget(panel)

    def test_preview_summary_metadata_refreshes_with_pointer_and_grid_updates(self, qapp):
        from ui_designer.ui.preview_panel import PreviewPanel

        page, label = build_test_page_with_widget(
            "main_page",
            name="label",
            x=10,
            y=10,
            width=100,
            height=20,
        )

        panel = PreviewPanel(screen_width=240, screen_height=320)
        panel.set_grid_size(12)
        panel.show_python_preview(page, "fallback")
        panel._update_status_label(12, 18, label)
        pointer_summary = panel._status_label.accessibleName().replace("Preview pointer status: ", "", 1)

        assert panel._zoom_label.text() == "100% (12px)"
        assert panel.status_label.accessibleName() == "Preview status: Preview - Python fallback (fallback)"
        assert panel._header_frame.accessibleName() == f"Preview header. {panel.accessibleName()}"
        assert panel._header_meta_label.accessibleName() == panel._header_meta_label.text()
        assert panel._metrics_frame.isHidden() is True
        assert panel._metrics_frame.accessibleName() == f"Preview metrics: Horizontal split. Grid on. Pointer status: {pointer_summary}."
        assert panel._mode_chip.isHidden() is True
        assert panel._grid_chip.isHidden() is True
        assert panel._pointer_chip.isHidden() is True
        assert panel._pointer_chip.text() == "Pointer active"
        assert panel._pointer_chip.accessibleName() == f"Preview pointer summary: {pointer_summary}"
        assert panel.preview_frame.accessibleName() == (
            "Preview frame: Preview - Python fallback (fallback). Mode: Horizontal split."
        )
        assert panel.overlay.accessibleName() == "Preview overlay: Horizontal split. Zoom: 100% (12px). Grid: on."
        assert panel._status_label.accessibleName() == (
            "Preview pointer status: (12, 18)  |  label: label  [10, 10, 100×20]"
        )
        assert panel._btn_zoom_in.toolTip() == "Zoom in preview (Ctrl+=). Current zoom: 100% (12px)."
        assert panel._btn_zoom_in.accessibleName() == "Zoom in preview: current zoom 100% (12px)"
        assert panel.accessibleName() == (
            "Preview panel: Preview - Python fallback (fallback). Mode: Horizontal split. "
            "Zoom: 100% (12px). Grid: on. Pointer: (12, 18)  |  label: label  [10, 10, 100×20]."
        )
        _dispose_widget(panel)

    def test_pointer_status_updates_are_throttled_during_drag(self, qapp, monkeypatch):
        from ui_designer.ui import preview_panel as preview_panel_module
        from ui_designer.ui.preview_panel import PreviewPanel

        panel = PreviewPanel(screen_width=240, screen_height=320)
        panel.overlay._dragging = True
        ticks = iter([0.0, 0.01, 0.05])
        monkeypatch.setattr(preview_panel_module.time, "monotonic", lambda: next(ticks))

        panel._update_status_label(10, 10, None)
        first_text = panel._status_label.text()
        panel._update_status_label(20, 20, None)
        assert panel._status_label.text() == first_text
        panel._update_status_label(30, 30, None)
        assert panel._status_label.text() == "(30, 30)"
        _dispose_widget(panel)

    def test_header_frame_hint_skips_no_op_rewrites(self, qapp, monkeypatch):
        from ui_designer.ui.preview_panel import PreviewPanel

        panel = PreviewPanel(screen_width=240, screen_height=320)
        panel._header_frame.setProperty("_preview_hint_snapshot", None)

        hint_calls = 0
        original_set_tooltip = panel._header_frame.setToolTip

        def counted_set_tooltip(text):
            nonlocal hint_calls
            hint_calls += 1
            return original_set_tooltip(text)

        monkeypatch.setattr(panel._header_frame, "setToolTip", counted_set_tooltip)

        panel._update_accessibility_summary()
        assert hint_calls == 1

        panel._update_accessibility_summary()
        assert hint_calls == 1

        panel._update_status_label(12, 18, None)
        assert hint_calls == 2
        _dispose_widget(panel)

    def test_header_frame_accessible_name_skips_no_op_rewrites(self, qapp, monkeypatch):
        from ui_designer.ui.preview_panel import PreviewPanel

        panel = PreviewPanel(screen_width=240, screen_height=320)
        panel._header_frame.setProperty("_preview_accessible_snapshot", None)

        accessible_calls = 0
        original_set_accessible_name = panel._header_frame.setAccessibleName

        def counted_set_accessible_name(text):
            nonlocal accessible_calls
            accessible_calls += 1
            return original_set_accessible_name(text)

        monkeypatch.setattr(panel._header_frame, "setAccessibleName", counted_set_accessible_name)

        panel._update_accessibility_summary()
        assert accessible_calls == 1

        panel._update_accessibility_summary()
        assert accessible_calls == 1

        panel._update_status_label(12, 18, None)
        assert accessible_calls == 2
        _dispose_widget(panel)

    def test_runtime_failed_emits_after_repeated_frame_failures(self, qapp):
        from ui_designer.ui.preview_panel import PreviewPanel

        class FakeCompiler:
            def __init__(self):
                self.calls = 0

            def get_frame(self):
                self.calls += 1
                return None

            def get_last_runtime_error(self):
                return "bridge lost"

        panel = PreviewPanel(screen_width=240, screen_height=320)
        compiler = FakeCompiler()
        reasons = []
        panel.runtime_failed.connect(reasons.append)
        panel.start_rendering(compiler)

        panel._refresh_frame()
        panel._refresh_frame()
        panel._refresh_frame()

        assert reasons == ["bridge lost"]
        assert panel.is_embedded is False
        _dispose_widget(panel)

    def test_grid_size_uses_configured_value(self, qapp):
        from ui_designer.ui.preview_panel import PreviewPanel

        panel = PreviewPanel(screen_width=240, screen_height=320)
        panel.set_grid_size(12)

        assert panel.grid_size() == 12
        assert panel.overlay._effective_grid_size() == 12

        panel.overlay.set_zoom(2.0)
        assert panel.overlay._effective_grid_size() == 12
        _dispose_widget(panel)

    def test_zoom_buttons_reflect_zoom_limits_in_accessibility_metadata(self, qapp):
        from ui_designer.ui.preview_panel import PreviewPanel

        panel = PreviewPanel(screen_width=240, screen_height=320)

        panel.overlay.set_zoom(panel.overlay._zoom_min)

        assert panel._zoom_label.text() == "25% (8px)"
        assert panel._btn_zoom_out.isEnabled() is False
        assert panel._btn_zoom_out.toolTip() == (
            "Zoom out preview (Ctrl+-). Current zoom: 25% (8px). "
            "Unavailable: already at minimum zoom."
        )
        assert panel._btn_zoom_out.statusTip() == panel._btn_zoom_out.toolTip()
        assert panel._btn_zoom_out.accessibleName() == "Zoom out preview unavailable: current zoom 25% (8px)"
        assert panel._btn_zoom_in.isEnabled() is True

        panel.overlay.set_zoom(panel.overlay._zoom_max)

        assert panel._zoom_label.text() == "400% (8px)"
        assert panel._btn_zoom_in.isEnabled() is False
        assert panel._btn_zoom_in.toolTip() == (
            "Zoom in preview (Ctrl+=). Current zoom: 400% (8px). "
            "Unavailable: already at maximum zoom."
        )
        assert panel._btn_zoom_in.statusTip() == panel._btn_zoom_in.toolTip()
        assert panel._btn_zoom_in.accessibleName() == "Zoom in preview unavailable: current zoom 400% (8px)"
        assert panel._btn_zoom_out.isEnabled() is True
        _dispose_widget(panel)


@_skip_no_qt
class TestMainWindowBuildAvailability:
    def test_compile_actions_disabled_when_compiler_cannot_build(self, qapp):
        from ui_designer.model.project import Project
        from ui_designer.ui.main_window import MainWindow

        class FakeCompiler:
            def can_build(self):
                return False

            def is_preview_running(self):
                return False

        window = MainWindow("", app_name="HelloDesigner")
        window.project = Project()
        window.compiler = FakeCompiler()
        window._update_compile_availability()

        assert window._compile_action.isEnabled() is False
        assert window.auto_compile_action.isEnabled() is False
        assert window._stop_action.isEnabled() is False
        _dispose_widget(window)


@_skip_no_qt
class TestWidgetOverlaySelection:
    def test_overlay_auxiliary_font_sizes_follow_designer_font_preference(self, qapp):
        from ui_designer.ui.preview_panel import WidgetOverlay

        qapp.setProperty("designer_font_size_pt", 12)
        overlay = WidgetOverlay()

        try:
            assert overlay._widget_label_font_point_size() == 9
            assert overlay._coord_tooltip_font_point_size() == 9
            assert overlay.focusPolicy() == Qt.StrongFocus
        finally:
            _dispose_widget(overlay)
            qapp.setProperty("designer_font_size_pt", 0)

    def test_overlay_paint_palette_tracks_theme_tokens(self, qapp):
        from ui_designer.ui.theme import app_theme_tokens

        overlay, root, first, second, third = self._make_overlay()
        overlay.set_selection([first, second], primary=first)
        overlay._set_hovered_widget(third)

        try:
            tokens = app_theme_tokens(qapp)
            palette = overlay._paint_palette()
            selected_pen, selected_fill = overlay._widget_bounds_style(first, 1.0, palette=palette)
            multi_pen, multi_fill = overlay._widget_bounds_style(second, 1.0, palette=palette)
            hover_pen, hover_fill = overlay._widget_bounds_style(third, 1.0, palette=palette)

            assert selected_pen.color().name().lower() == tokens["danger"].lower()
            assert selected_fill.name().lower() == tokens["danger"].lower()
            assert multi_pen.color().name().lower() == tokens["warning"].lower()
            assert multi_fill.name().lower() == tokens["warning"].lower()
            assert hover_pen.color().name().lower() == tokens["accent"].lower()
            assert hover_fill.name().lower() == tokens["accent"].lower()
            assert palette["grid"].name().lower() == tokens["border"].lower()
            assert palette["tooltip_border"].name().lower() == tokens["accent"].lower()
            assert palette["tooltip_text"].name().lower() == tokens["text"].lower()

            overlay.set_solid_background(True)
            passive_pen, passive_fill = overlay._widget_bounds_style(root, 1.0, passive_only=True)
            assert passive_pen.color().name().lower() == tokens["text_soft"].lower()
            assert passive_fill.name().lower() == tokens["accent"].lower()
        finally:
            _dispose_widget(overlay)

    def test_overlay_theme_change_updates_palette_and_requests_repaint(self, qapp, monkeypatch):
        from ui_designer.ui.preview_panel import WidgetOverlay
        from ui_designer.ui.theme import app_theme_tokens

        overlay = WidgetOverlay()
        update_calls = 0
        original_update = overlay.update

        def counted_update():
            nonlocal update_calls
            update_calls += 1
            return original_update()

        monkeypatch.setattr(overlay, "update", counted_update)

        try:
            dark_palette = overlay._paint_palette()

            qapp.setProperty("designer_theme_mode", "light")
            overlay.changeEvent(QEvent(QEvent.StyleChange))

            light_tokens = app_theme_tokens(qapp)
            light_palette = overlay._paint_palette()

            assert update_calls == 1
            assert light_palette["hover_border"].name().lower() == light_tokens["accent"].lower()
            assert light_palette["selected_border"].name().lower() == light_tokens["danger"].lower()
            assert light_palette["tooltip_bg"].name().lower() == light_tokens["panel"].lower()
            assert light_palette["hover_border"].name().lower() != dark_palette["hover_border"].name().lower()

            overlay.changeEvent(QEvent(QEvent.FontChange))
            assert update_calls == 1
        finally:
            _dispose_widget(overlay)
            qapp.setProperty("designer_theme_mode", None)

    def test_overlay_keeps_full_feedback_during_drag_states(self, qapp):
        from ui_designer.ui.preview_panel import WidgetOverlay

        overlay = WidgetOverlay()

        try:
            assert overlay._show_full_label_overlay() is True
            assert overlay._show_full_bounds_overlay() is True
            overlay._dragging = True
            assert overlay._show_full_label_overlay() is True
            assert overlay._show_full_bounds_overlay() is True
            overlay._dragging = False
            overlay._resizing = True
            assert overlay._show_full_label_overlay() is True
            assert overlay._show_full_bounds_overlay() is True
            overlay._resizing = False
            overlay._rubber_band = True
            assert overlay._show_full_label_overlay() is True
            assert overlay._show_full_bounds_overlay() is True
        finally:
            _dispose_widget(overlay)

    def test_overlay_uses_passive_bounds_cache_to_keep_other_widgets_visible_during_drag(self, qapp):
        overlay, _root, first, second, third = self._make_overlay()
        overlay.set_selection([first, second], primary=first)

        try:
            assert overlay._paint_candidate_widgets() == overlay._visible_widgets

            overlay._dragging = True
            assert overlay._should_use_passive_bounds_cache() is True
            assert overlay._paint_candidate_widgets() == [first, second]
            assert overlay._passive_cache_widgets() == [_root, third]
            overlay._ensure_passive_bounds_cache()
            assert overlay._passive_bounds_cache is not None
        finally:
            _dispose_widget(overlay)

    def test_overlay_invalidates_passive_bounds_cache_when_selection_changes(self, qapp):
        overlay, _root, first, second, _third = self._make_overlay()
        overlay.set_selection([first], primary=first)
        overlay._dragging = True

        try:
            overlay._ensure_passive_bounds_cache()
            assert overlay._passive_bounds_cache is not None
            overlay.set_selection([second], primary=second)
            assert overlay._passive_bounds_cache is None
        finally:
            _dispose_widget(overlay)

    def test_overlay_invalidates_passive_bounds_cache_when_grid_state_changes(self, qapp):
        overlay, _root, first, _second, _third = self._make_overlay()
        overlay.set_selection([first], primary=first)
        overlay._dragging = True
        overlay.set_solid_background(True)

        try:
            overlay._ensure_passive_bounds_cache()
            assert overlay._passive_bounds_cache is not None
            overlay.set_grid_size(12)
            assert overlay._passive_bounds_cache is None
        finally:
            _dispose_widget(overlay)

    def test_overlay_passive_cache_uses_visible_scroll_viewport(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.preview_panel import WidgetOverlay

        scroll = QScrollArea()
        scroll.resize(320, 240)
        overlay = WidgetOverlay()
        overlay.set_base_size(1200, 1200)
        overlay.set_solid_background(True)
        scroll.setWidget(overlay)
        scroll.show()

        moving = WidgetModel("label", name="moving", x=10, y=10, width=80, height=24)
        other = WidgetModel("button", name="other", x=300, y=300, width=90, height=28)
        root = build_test_page_root_with_widgets(
            "main_page",
            screen_width=1200,
            screen_height=1200,
            root_name="root",
            widgets=[moving, other],
        )

        try:
            overlay.set_widgets(root.get_all_widgets_flat())
            overlay.set_selection([moving], primary=moving)
            overlay._dragging = True
            qapp.processEvents()

            overlay._ensure_passive_bounds_cache()

            assert overlay._passive_bounds_cache_rect.width() < overlay.width()
            assert overlay._passive_bounds_cache_rect.height() < overlay.height()
        finally:
            _dispose_widget(scroll)

    def test_overlay_batches_dirty_rect_updates_into_single_update_call(self, qapp, monkeypatch):
        from PyQt5.QtCore import QRect
        from ui_designer.ui.preview_panel import WidgetOverlay

        overlay = WidgetOverlay()
        calls = []

        monkeypatch.setattr(overlay, "update", lambda *args: calls.append(args))

        try:
            overlay._update_regions(QRect(0, 0, 10, 10), QRect(20, 20, 10, 10))
            assert len(calls) == 1
        finally:
            _dispose_widget(overlay)

    def test_overlay_keeps_snap_guides_visible_during_drag_and_resize(self, qapp):
        from ui_designer.ui.preview_panel import WidgetOverlay

        overlay = WidgetOverlay()

        try:
            assert overlay._show_snap_guides() is True
            overlay._dragging = True
            assert overlay._show_snap_guides() is True
            overlay._dragging = False
            overlay._resizing = True
            assert overlay._show_snap_guides() is True
        finally:
            _dispose_widget(overlay)

    def test_overlay_caches_visible_and_interactive_widgets(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.preview_panel import WidgetOverlay

        overlay = WidgetOverlay()
        visible_child = WidgetModel("label", name="visible", x=10, y=10, width=80, height=24)
        hidden_child = WidgetModel("button", name="hidden", x=10, y=40, width=80, height=24)
        locked_child = WidgetModel("button", name="locked", x=10, y=70, width=80, height=24)
        hidden_child.designer_hidden = True
        locked_child.designer_locked = True
        root = build_test_page_root_with_widgets(
            "main_page",
            root_name="root",
            widgets=[visible_child, hidden_child, locked_child],
        )

        try:
            overlay.set_widgets(root.get_all_widgets_flat())
            assert overlay._visible_non_root_widgets is True
            assert visible_child in overlay._visible_widgets
            assert hidden_child not in overlay._visible_widgets
            assert visible_child in overlay._interactive_widgets
            assert locked_child not in overlay._interactive_widgets
            assert len(overlay._snap_target_edges) == len(overlay._visible_widgets)
            assert len(overlay._snap_edges_x) == len(overlay._visible_widgets) * 3
            assert len(overlay._snap_edges_y) == len(overlay._visible_widgets) * 3
        finally:
            _dispose_widget(overlay)

    def test_snap_guides_keep_only_nearest_hit_per_axis(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.preview_panel import WidgetOverlay

        overlay = WidgetOverlay()
        moving = WidgetModel("label", name="moving", x=10, y=10, width=20, height=20)
        near_a = WidgetModel("label", name="near_a", x=39, y=40, width=20, height=20)
        near_b = WidgetModel("label", name="near_b", x=42, y=43, width=20, height=20)
        root = build_test_page_root_with_widgets(
            "main_page",
            root_name="root",
            widgets=[moving, near_a, near_b],
        )

        try:
            overlay.set_widgets(root.get_all_widgets_flat())
            guides = overlay._find_snap_guides(moving, 20, 20, moving.width, moving.height)
            vertical = [pos for axis, pos in guides if axis == "v"]
            horizontal = [pos for axis, pos in guides if axis == "h"]
            assert len(vertical) <= 1
            assert len(horizontal) <= 1
        finally:
            _dispose_widget(overlay)

    def test_drag_snap_prefers_widget_guides_over_grid_and_grids_unmatched_axis(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.preview_panel import WidgetOverlay

        overlay = WidgetOverlay()
        overlay.set_base_size(240, 320)
        moving = WidgetModel("label", name="moving", x=12, y=12, width=20, height=20)
        target = WidgetModel("label", name="target", x=58, y=80, width=24, height=20)
        root = build_test_page_root_with_widgets(
            "main_page",
            root_name="root",
            widgets=[moving, target],
        )

        try:
            overlay.set_widgets(root.get_all_widgets_flat())
            overlay.set_selection([moving], primary=moving)
            overlay._dragging = True
            overlay._drag_offset = QPoint()

            overlay._do_free_drag(QPoint(57, 14))

            assert moving.x == 58
            assert moving.y == 16
            assert moving.display_x == 58
            assert moving.display_y == 16
            assert overlay._snap_guides == [("v", 58)]
        finally:
            _dispose_widget(overlay)

    def test_drag_does_not_reinvalidate_unchanged_guides(self, qapp, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui import preview_panel as preview_panel_module
        from ui_designer.ui.preview_panel import WidgetOverlay

        overlay = WidgetOverlay()
        overlay.set_base_size(240, 320)
        moving = WidgetModel("label", name="moving", x=12, y=12, width=20, height=20)
        target = WidgetModel("label", name="target", x=58, y=80, width=24, height=20)
        root = build_test_page_root_with_widgets(
            "main_page",
            root_name="root",
            widgets=[moving, target],
        )

        guide_updates = []

        try:
            overlay.set_widgets(root.get_all_widgets_flat())
            overlay.set_selection([moving], primary=moving)
            overlay._dragging = True
            overlay._drag_offset = QPoint()
            monkeypatch.setattr(
                overlay,
                "_update_regions_for_geometry_and_guides",
                lambda geometry_rects, old_guide_rects=None, new_guide_rects=None: guide_updates.append(
                    [list(geometry_rects), list(old_guide_rects or ()), list(new_guide_rects or ())]
                ),
            )
            monkeypatch.setattr(overlay, "_update_regions_for_guide_rects", lambda rects: guide_updates.append(list(rects)))

            overlay._do_free_drag(QPoint(57, 14))
            assert guide_updates
            guide_updates.clear()

            overlay._do_free_drag(QPoint(57, 18))
            assert guide_updates == []
        finally:
            _dispose_widget(overlay)

    def test_drag_geometry_signals_are_throttled_but_flush_on_release(self, qapp, monkeypatch):
        from ui_designer.ui import preview_panel as preview_panel_module

        overlay, _root, first, _second, _third = self._make_overlay()
        overlay.set_selection([first], primary=first)
        overlay.set_grid_size(0)
        overlay._dragging = True
        overlay._drag_offset = QPoint()
        moved = []
        overlay.widget_moved.connect(lambda widget, x, y: moved.append((widget, x, y)))
        ticks = iter([0.0, 0.005])
        monkeypatch.setattr(preview_panel_module.time, "monotonic", lambda: next(ticks))

        try:
            overlay._do_free_drag(QPoint(20, 20))
            overlay._do_free_drag(QPoint(25, 25))
            assert len(moved) == 1

            overlay.mouseReleaseEvent(_mouse_event(QEvent.MouseButtonRelease, QPoint(25, 25), buttons=Qt.NoButton))
            qapp.processEvents()

            assert len(moved) == 2
            assert moved[-1][1:] == (25, 25)
        finally:
            _dispose_widget(overlay)

    def test_drag_snap_uses_page_center_when_grid_is_disabled(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.preview_panel import WidgetOverlay

        overlay = WidgetOverlay()
        overlay.set_base_size(240, 320)
        overlay.set_grid_size(0)
        moving = WidgetModel("label", name="moving", x=10, y=10, width=20, height=20)
        root = build_test_page_root_with_widgets(
            "main_page",
            root_name="root",
            widgets=[moving],
        )

        try:
            overlay.set_widgets(root.get_all_widgets_flat())
            overlay.set_selection([moving], primary=moving)
            overlay._dragging = True
            overlay._drag_offset = QPoint()

            overlay._do_free_drag(QPoint(108, 148))

            assert moving.x == 110
            assert moving.y == 150
            assert moving.display_x == 110
            assert moving.display_y == 150
            assert ("v", 120) in overlay._snap_guides
            assert ("h", 160) in overlay._snap_guides
        finally:
            _dispose_widget(overlay)

    def test_resize_snap_preserves_anchor_and_uses_guides_before_grid(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.preview_panel import HANDLE_RIGHT, WidgetOverlay

        overlay = WidgetOverlay()
        overlay.set_base_size(240, 320)
        moving = WidgetModel("label", name="moving", x=20, y=20, width=20, height=20)
        target = WidgetModel("label", name="target", x=60, y=80, width=24, height=20)
        root = build_test_page_root_with_widgets(
            "main_page",
            root_name="root",
            widgets=[moving, target],
        )

        try:
            overlay.set_widgets(root.get_all_widgets_flat())
            overlay.set_selection([moving], primary=moving)
            overlay._resizing = True
            overlay._resize_handle = HANDLE_RIGHT
            overlay._resize_start_rect = QRect(moving.display_x, moving.display_y, moving.width, moving.height)
            overlay._resize_start_pos = QPoint()

            overlay._do_resize(QPoint(18, 0))

            assert moving.x == 20
            assert moving.y == 20
            assert moving.width == 40
            assert moving.height == 20
            assert moving.display_x == 20
            assert moving.display_y == 20
            assert overlay._snap_guides == [("v", 60)]
        finally:
            _dispose_widget(overlay)

    def test_drag_updates_nested_widget_relative_and_display_positions(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.preview_panel import WidgetOverlay

        overlay = WidgetOverlay()
        overlay.set_base_size(240, 320)
        overlay.set_grid_size(0)
        container = WidgetModel("group", name="container", x=40, y=50, width=120, height=120)
        child = WidgetModel("label", name="child", x=10, y=10, width=20, height=20)
        add_widget_children(container, [child])
        root = build_test_page_root_with_widgets(
            "main_page",
            root_name="root",
            widgets=[container],
        )
        root.display_x = root.x
        root.display_y = root.y
        container.display_x = container.x
        container.display_y = container.y
        child.display_x = container.display_x + child.x
        child.display_y = container.display_y + child.y

        try:
            overlay.set_widgets(root.get_all_widgets_flat())
            overlay.set_selection([child], primary=child)
            overlay._dragging = True
            overlay._drag_offset = QPoint()

            overlay._do_free_drag(QPoint(63, 74))

            assert child.x == 23
            assert child.y == 24
            assert child.display_x == 63
            assert child.display_y == 74
        finally:
            _dispose_widget(overlay)

    def test_nested_drag_ignores_snap_targets_from_other_parent_branches(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.preview_panel import WidgetOverlay

        overlay = WidgetOverlay()
        overlay.set_base_size(240, 320)
        overlay.set_grid_size(0)
        left_branch = WidgetModel("group", name="left_branch", x=20, y=20, width=80, height=80)
        right_branch = WidgetModel("group", name="right_branch", x=130, y=20, width=80, height=80)
        moving = WidgetModel("label", name="moving", x=8, y=8, width=20, height=20)
        cousin = WidgetModel("label", name="cousin", x=0, y=0, width=20, height=20)
        add_widget_children(left_branch, [moving])
        add_widget_children(right_branch, [cousin])
        root = build_test_page_root_with_widgets(
            "main_page",
            root_name="root",
            widgets=[left_branch, right_branch],
        )

        root.display_x = root.x
        root.display_y = root.y
        left_branch.display_x = left_branch.x
        left_branch.display_y = left_branch.y
        right_branch.display_x = right_branch.x
        right_branch.display_y = right_branch.y
        moving.display_x = left_branch.display_x + moving.x
        moving.display_y = left_branch.display_y + moving.y
        cousin.display_x = right_branch.display_x + cousin.x
        cousin.display_y = right_branch.display_y + cousin.y

        try:
            overlay.set_widgets(root.get_all_widgets_flat())
            overlay.set_selection([moving], primary=moving)
            overlay._dragging = True
            overlay._drag_offset = QPoint()

            overlay._do_free_drag(QPoint(128, 31))

            assert moving.display_x == 128
            assert moving.x == 108
            assert overlay._snap_guides == []
        finally:
            _dispose_widget(overlay)

    def test_widget_hit_test_prefers_topmost_overlapping_widget(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.preview_panel import WidgetOverlay

        overlay = WidgetOverlay()
        bottom = WidgetModel("label", name="bottom", x=20, y=20, width=80, height=40)
        top = WidgetModel("button", name="top", x=30, y=30, width=80, height=40)
        root = build_test_page_root_with_widgets(
            "main_page",
            root_name="root",
            widgets=[bottom, top],
        )

        try:
            overlay.set_widgets(root.get_all_widgets_flat())
            assert overlay._widget_at(QPoint(40, 40), allow_root=False) is top
        finally:
            _dispose_widget(overlay)

    def test_widget_hit_test_finds_widget_spanning_multiple_buckets(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.preview_panel import WidgetOverlay

        overlay = WidgetOverlay()
        wide = WidgetModel("group", name="wide", x=10, y=70, width=180, height=30)
        root = build_test_page_root_with_widgets(
            "main_page",
            screen_width=320,
            screen_height=320,
            root_name="root",
            widgets=[wide],
        )

        try:
            overlay.set_widgets(root.get_all_widgets_flat())
            assert overlay._widget_at(QPoint(170, 80), allow_root=False) is wide
        finally:
            _dispose_widget(overlay)

    def test_visible_candidates_for_rect_keep_widget_order(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.preview_panel import WidgetOverlay

        overlay = WidgetOverlay()
        first = WidgetModel("label", name="first", x=10, y=70, width=180, height=30)
        second = WidgetModel("button", name="second", x=20, y=90, width=40, height=20)
        root = build_test_page_root_with_widgets(
            "main_page",
            screen_width=320,
            screen_height=320,
            root_name="root",
            widgets=[first, second],
        )

        try:
            overlay.set_widgets(root.get_all_widgets_flat())
            candidates = overlay._visible_candidates_for_rect(QRect(0, 64, 200, 64))
            assert candidates == [root, first, second]
        finally:
            _dispose_widget(overlay)

    def test_grid_line_positions_are_limited_to_visible_rect(self, qapp):
        from PyQt5.QtCore import QRectF
        from ui_designer.ui.preview_panel import WidgetOverlay

        overlay = WidgetOverlay()

        try:
            visible_rect = QRectF(70.0, 130.0, 100.0, 80.0)
            xs = list(overlay._grid_line_positions(500, 8, visible_rect, "x"))
            ys = list(overlay._grid_line_positions(500, 8, visible_rect, "y"))
            assert xs[0] == 64
            assert xs[-1] == 176
            assert ys[0] == 128
            assert ys[-1] == 216
        finally:
            _dispose_widget(overlay)

    def _make_overlay(self):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.preview_panel import WidgetOverlay

        overlay = WidgetOverlay()
        overlay.set_base_size(240, 320)
        first = WidgetModel("label", name="first", x=10, y=10, width=80, height=24)
        second = WidgetModel("button", name="second", x=10, y=60, width=90, height=28)
        third = WidgetModel("switch", name="third", x=120, y=60, width=70, height=24)
        root = build_test_page_root_with_widgets(
            "main_page",
            root_name="root",
            widgets=[first, second, third],
        )
        overlay.set_widgets(root.get_all_widgets_flat())
        return overlay, root, first, second, third

    def test_context_menu_selects_unselected_widget_before_emitting(self, qapp):
        overlay, _root, first, second, _third = self._make_overlay()
        overlay.set_selection([first], primary=first)
        captured = []
        overlay.context_menu_requested.connect(lambda widget, global_pos: captured.append((widget, global_pos)))

        event = QContextMenuEvent(QContextMenuEvent.Mouse, QPoint(20, 70), QPoint(320, 420))
        overlay.contextMenuEvent(event)
        qapp.processEvents()

        assert overlay.selected_widgets() == [second]
        assert captured[0][0] is second
        assert captured[0][1] == QPoint(320, 420)
        _dispose_widget(overlay)

    def test_click_selection_does_not_start_drag_or_show_coords(self, qapp):
        overlay, _root, first, second, _third = self._make_overlay()
        overlay.set_selection([first], primary=first)
        drag_events = []

        overlay.drag_started.connect(lambda: drag_events.append("start"))
        overlay.drag_finished.connect(lambda: drag_events.append("finish"))

        overlay.mousePressEvent(_mouse_event(QEvent.MouseButtonPress, QPoint(20, 70)))
        qapp.processEvents()

        assert overlay.selected_widgets() == [second]
        assert overlay._dragging is False
        assert overlay._show_coords is False
        assert drag_events == []

        overlay.mouseReleaseEvent(_mouse_event(QEvent.MouseButtonRelease, QPoint(20, 70), buttons=Qt.NoButton))
        qapp.processEvents()

        assert overlay._dragging is False
        assert overlay._show_coords is False
        assert drag_events == []
        _dispose_widget(overlay)

    def test_widget_drag_starts_only_after_move_threshold(self, qapp):
        overlay, _root, _first, second, _third = self._make_overlay()
        drag_events = []
        threshold = overlay._drag_start_distance()

        overlay.drag_started.connect(lambda: drag_events.append("start"))
        overlay.drag_finished.connect(lambda: drag_events.append("finish"))

        overlay.mousePressEvent(_mouse_event(QEvent.MouseButtonPress, QPoint(20, 70)))
        overlay.mouseMoveEvent(
            _mouse_event(
                QEvent.MouseMove,
                QPoint(20 + max(threshold - 1, 0), 70),
                button=Qt.NoButton,
                buttons=Qt.LeftButton,
            )
        )
        qapp.processEvents()

        assert overlay.selected_widgets() == [second]
        assert overlay._dragging is False
        assert overlay._show_coords is False
        assert drag_events == []

        overlay.mouseMoveEvent(
            _mouse_event(
                QEvent.MouseMove,
                QPoint(20 + threshold + 4, 70),
                button=Qt.NoButton,
                buttons=Qt.LeftButton,
            )
        )
        qapp.processEvents()

        assert overlay._dragging is True
        assert overlay._show_coords is True
        assert drag_events == ["start"]

        overlay.mouseReleaseEvent(
            _mouse_event(QEvent.MouseButtonRelease, QPoint(20 + threshold + 4, 70), buttons=Qt.NoButton)
        )
        qapp.processEvents()

        assert overlay._dragging is False
        assert overlay._show_coords is False
        assert drag_events == ["start", "finish"]
        _dispose_widget(overlay)

    def test_rubber_band_replace_excludes_root_widget(self, qapp):
        overlay, root, first, second, third = self._make_overlay()

        overlay.mousePressEvent(_mouse_event(QEvent.MouseButtonPress, QPoint(1, 1)))
        overlay.mouseMoveEvent(_mouse_event(QEvent.MouseMove, QPoint(210, 120), button=Qt.NoButton, buttons=Qt.LeftButton))
        overlay.mouseReleaseEvent(_mouse_event(QEvent.MouseButtonRelease, QPoint(210, 120), buttons=Qt.NoButton))
        qapp.processEvents()

        assert overlay.selected_widgets() == [first, second, third]
        assert root not in overlay.selected_widgets()
        _dispose_widget(overlay)

    def test_rubber_band_shift_adds_to_selection(self, qapp):
        overlay, _root, first, second, _third = self._make_overlay()
        overlay.set_selection([first], primary=first)

        overlay.mousePressEvent(_mouse_event(QEvent.MouseButtonPress, QPoint(1, 40), modifiers=Qt.ShiftModifier))
        overlay.mouseMoveEvent(_mouse_event(QEvent.MouseMove, QPoint(110, 100), button=Qt.NoButton, buttons=Qt.LeftButton, modifiers=Qt.ShiftModifier))
        overlay.mouseReleaseEvent(_mouse_event(QEvent.MouseButtonRelease, QPoint(110, 100), buttons=Qt.NoButton, modifiers=Qt.ShiftModifier))
        qapp.processEvents()

        assert overlay.selected_widgets() == [first, second]
        _dispose_widget(overlay)

    def test_rubber_band_ctrl_toggles_matching_widgets(self, qapp):
        overlay, _root, first, second, _third = self._make_overlay()
        overlay.set_selection([first, second], primary=first)

        overlay.mousePressEvent(_mouse_event(QEvent.MouseButtonPress, QPoint(1, 40), modifiers=Qt.ControlModifier))
        overlay.mouseMoveEvent(_mouse_event(QEvent.MouseMove, QPoint(110, 100), button=Qt.NoButton, buttons=Qt.LeftButton, modifiers=Qt.ControlModifier))
        overlay.mouseReleaseEvent(_mouse_event(QEvent.MouseButtonRelease, QPoint(110, 100), buttons=Qt.NoButton, modifiers=Qt.ControlModifier))
        qapp.processEvents()

        assert overlay.selected_widgets() == [first]
        _dispose_widget(overlay)

    def test_rubber_band_selects_widget_spanning_multiple_selection_buckets(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.preview_panel import WidgetOverlay

        overlay = WidgetOverlay()
        overlay.set_base_size(320, 320)
        wide = WidgetModel("group", name="wide", x=10, y=70, width=180, height=30)
        root = build_test_page_root_with_widgets(
            "main_page",
            screen_width=320,
            screen_height=320,
            root_name="root",
            widgets=[wide],
        )
        overlay.set_widgets(root.get_all_widgets_flat())

        overlay.mousePressEvent(_mouse_event(QEvent.MouseButtonPress, QPoint(160, 60)))
        overlay.mouseMoveEvent(_mouse_event(QEvent.MouseMove, QPoint(200, 120), button=Qt.NoButton, buttons=Qt.LeftButton))
        overlay.mouseReleaseEvent(_mouse_event(QEvent.MouseButtonRelease, QPoint(200, 120), buttons=Qt.NoButton))
        qapp.processEvents()

        assert overlay.selected_widgets() == [wide]
        _dispose_widget(overlay)
