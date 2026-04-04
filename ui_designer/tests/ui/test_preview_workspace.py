"""Qt UI smoke tests for preview fallback and workspace-aware build gating."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtCore import QEvent, QPoint, QPointF, Qt
    from PyQt5.QtGui import QContextMenuEvent, QMouseEvent
    from PyQt5.QtWidgets import QApplication
    _has_pyqt5 = True
except ImportError:
    _has_pyqt5 = False

_skip_no_qt = pytest.mark.skipif(not _has_pyqt5, reason="PyQt5 not available")


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
    app.processEvents()


def _dispose_widget(widget):
    if widget is None:
        return
    stop_rendering = getattr(widget, "stop_rendering", None)
    if callable(stop_rendering):
        try:
            stop_rendering()
        except Exception:
            pass
    try:
        widget.close()
    except Exception:
        pass
    try:
        widget.deleteLater()
    except Exception:
        pass
    app = QApplication.instance()
    if app is not None:
        try:
            app.sendPostedEvents()
        except Exception:
            pass
        app.processEvents()


def _mouse_event(event_type, pos, *, button=Qt.LeftButton, buttons=Qt.LeftButton, modifiers=Qt.NoModifier):
    return QMouseEvent(event_type, QPointF(pos), button, buttons, modifiers)


@_skip_no_qt
class TestPreviewPanelFallback:
    def test_preview_panel_exposes_initial_accessibility_metadata(self, qapp):
        from ui_designer.ui.preview_panel import PreviewPanel

        panel = PreviewPanel(screen_width=240, screen_height=320)

        assert panel._zoom_label.text() == "100% (8px)"
        assert panel.accessibleName() == (
            "Preview panel: Preview - waiting for exe.... Mode: Horizontal split. "
            "Zoom: 100% (8px). Grid: on. Pointer: Pointer idle."
        )
        assert panel._eyebrow_label.accessibleName() == "Preview engineering workspace surface."
        assert panel._metrics_frame.accessibleName() == (
            "Preview metrics: Horizontal split. Grid on. Pointer status: Pointer idle."
        )
        assert panel._mode_chip.accessibleName() == "Preview mode: Horizontal split"
        assert panel._grid_chip.accessibleName() == "Preview grid: on"
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
        from ui_designer.model.page import Page
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.preview_panel import PreviewPanel

        root = WidgetModel("group", name="root", x=0, y=0, width=240, height=320)
        label = WidgetModel("label", name="label", x=10, y=10, width=100, height=20)
        label.properties["text"] = "Hello"
        root.add_child(label)
        page = Page(file_path="layout/main_page.xml", root_widget=root)

        panel = PreviewPanel(screen_width=240, screen_height=320)
        panel.show_python_preview(page, "fallback")

        assert panel.is_python_preview_active() is True
        assert panel._preview_label.pixmap() is not None
        assert "Python fallback" in panel.status_label.text()
        _dispose_widget(panel)

    def test_preview_summary_metadata_refreshes_with_pointer_and_grid_updates(self, qapp):
        from ui_designer.model.page import Page
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.preview_panel import PreviewPanel

        root = WidgetModel("group", name="root", x=0, y=0, width=240, height=320)
        label = WidgetModel("label", name="label", x=10, y=10, width=100, height=20)
        root.add_child(label)
        page = Page(file_path="layout/main_page.xml", root_widget=root)

        panel = PreviewPanel(screen_width=240, screen_height=320)
        panel.set_grid_size(12)
        panel.show_python_preview(page, "fallback")
        panel._update_status_label(12, 18, label)
        pointer_summary = panel._status_label.accessibleName().replace("Preview pointer status: ", "", 1)

        assert panel._zoom_label.text() == "100% (12px)"
        assert panel.status_label.accessibleName() == "Preview status: Preview - Python fallback (fallback)"
        assert panel._metrics_frame.accessibleName() == f"Preview metrics: Horizontal split. Grid on. Pointer status: {pointer_summary}."
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
    def _make_overlay(self):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.preview_panel import WidgetOverlay

        overlay = WidgetOverlay()
        overlay.set_base_size(240, 320)
        root = WidgetModel("group", name="root", x=0, y=0, width=240, height=320)
        first = WidgetModel("label", name="first", x=10, y=10, width=80, height=24)
        second = WidgetModel("button", name="second", x=10, y=60, width=90, height=28)
        third = WidgetModel("switch", name="third", x=120, y=60, width=70, height=24)
        root.add_child(first)
        root.add_child(second)
        root.add_child(third)
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
