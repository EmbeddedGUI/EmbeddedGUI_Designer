"""Preview panel that embeds the exe window with draggable widget overlays."""

import bisect
import math
import sys
import json
import time
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QSizePolicy, QPushButton, QSplitter,
)
from PyQt5.QtCore import Qt, QRect, QPoint, QPointF, QTimer, pyqtSignal, QRectF, QEvent
from PyQt5.QtGui import QPainter, QPen, QColor, QFont, QBrush, QTransform, QPixmap, QImage, QRegion, QFontMetrics


from .theme import app_theme_tokens, designer_monospace_font, designer_ui_font
from ..model.resource_binding import assign_resource_to_widget
from ..model.widget_registry import WidgetRegistry
from ..engine.python_renderer import render_page


# Overlay display modes
MODE_VERTICAL = "vertical"
MODE_HORIZONTAL = "horizontal"
MODE_HIDDEN = "hidden"

# Resize handle positions
HANDLE_NONE = 0
HANDLE_TOP_LEFT = 1
HANDLE_TOP = 2
HANDLE_TOP_RIGHT = 3
HANDLE_RIGHT = 4
HANDLE_BOTTOM_RIGHT = 5
HANDLE_BOTTOM = 6
HANDLE_BOTTOM_LEFT = 7
HANDLE_LEFT = 8

# Handle size in pixels
HANDLE_SIZE = 8
HIT_TEST_BUCKET_SIZE = 64
DRAG_GEOMETRY_SIGNAL_INTERVAL_SEC = 1.0 / 30.0
DRAG_POINTER_SIGNAL_INTERVAL_SEC = 1.0 / 15.0


def _parent_has_layout(widget):
    """Check if widget's parent uses a layout function (LinearLayout etc)."""
    if widget.parent is None:
        return False
    type_info = WidgetRegistry.instance().get(widget.parent.widget_type)
    return type_info.get("layout_func") is not None


def _parent_is_horizontal(widget):
    """Check if widget's parent LinearLayout is horizontal."""
    if widget.parent is None:
        return False
    return widget.parent.properties.get("orientation", "vertical") == "horizontal"


def _snap_to_grid(value, grid_size):
    """Snap a value to the nearest grid point."""
    if grid_size <= 1:
        return value
    return round(value / grid_size) * grid_size


def _set_widget_metadata(widget, *, tooltip=None, accessible_name=None):
    if tooltip is not None:
        hint = str(tooltip or "")
        if str(widget.property("_preview_hint_snapshot") or "") != hint:
            widget.setToolTip(hint)
            widget.setStatusTip(hint)
            widget.setProperty("_preview_hint_snapshot", hint)
    if accessible_name is not None:
        name = str(accessible_name or "")
        if str(widget.property("_preview_accessible_snapshot") or "") != name:
            widget.setAccessibleName(name)
            widget.setProperty("_preview_accessible_snapshot", name)


def _theme_color(color_value, alpha=None):
    color = QColor(str(color_value or "").strip())
    if alpha is not None:
        color.setAlpha(int(alpha))
    return color


class WidgetOverlay(QWidget):
    """Overlay showing widget bounds with drag, resize, and grid snap.

    Features:
    - Dual-mode drag: free drag for Group, reorder drag for LinearLayout
    - Resize handles on selected widget (8 handles: corners + edges)
    - Grid snap with configurable grid size
    - Coordinate display while dragging/resizing
    - Snap guide lines
    """

    widget_moved = pyqtSignal(object, int, int)  # widget, new_x, new_y
    widget_resized = pyqtSignal(object, int, int)  # widget, new_width, new_height
    widget_selected = pyqtSignal(object)  # widget
    selection_changed = pyqtSignal(list, object)  # widgets, primary
    context_menu_requested = pyqtSignal(object, object)  # widget, global_pos
    widget_reordered = pyqtSignal(object, int)  # widget, new_index
    zoom_changed = pyqtSignal(float)  # zoom factor
    resource_dropped = pyqtSignal(object, str, str)  # widget, res_type, filename
    widget_type_dropped = pyqtSignal(str, int, int, object)  # widget_type, x, y, target_widget
    mouse_position_changed = pyqtSignal(int, int, object)  # x, y, widget_under_cursor (or None)
    drag_started = pyqtSignal()   # emitted when drag or resize begins
    drag_finished = pyqtSignal()  # emitted when drag or resize ends

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("preview_overlay_surface")
        self.setProperty("solidBackground", False)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self.setAcceptDrops(True)
        self._solid_background = False

        self._widgets = []  # list of WidgetModel
        self._visible_widgets = []
        self._interactive_widgets = []
        self._interactive_widgets_reversed = []
        self._hit_test_buckets = {}
        self._selection_buckets = {}
        self._visible_non_root_widgets = False
        self._root_widget = None
        self._snap_target_edges = []
        self._snap_edges_x = []
        self._snap_edges_x_values = []
        self._snap_edges_y = []
        self._snap_edges_y_values = []
        self._snap_edges_x_lookup_by_parent = {}
        self._snap_edges_x_values_lookup_by_parent = {}
        self._snap_edges_y_lookup_by_parent = {}
        self._snap_edges_y_values_lookup_by_parent = {}
        self._selected = None
        self._hovered = None
        self._multi_selected = set()  # secondary selected WidgetModel values
        self._active_paint_widgets = []
        self._active_paint_widget_ids = set()
        self._passive_cache_widget_list = []
        self._passive_cache_widget_ids = set()
        self._passive_bounds_cache = None
        self._passive_bounds_cache_key = None
        self._passive_bounds_cache_rect = QRect()
        self._passive_cache_warmup_serial = 0
        self._paint_palette_cache = None
        self._font_pixel_size_cache = {}
        self._label_font_cache = None
        self._label_font_cache_px = None
        self._coord_font_cache = None
        self._coord_font_cache_px = None
        self._widget_label_text_by_id = {}
        self._visible_widget_order_by_id = {}

        # Zoom state
        self._zoom = 1.0
        self._zoom_min = 0.25
        self._zoom_max = 4.0
        self._base_width = 240   # set by PreviewPanel later
        self._base_height = 320

        # Drag state
        self._dragging = False
        self._pressed_widget = None
        self._press_pos = QPoint()
        self._press_drag_offset = QPoint()
        self._drag_offset = QPoint()
        self._reorder_mode = False
        self._insert_index = -1
        self._insert_line_rect = None

        # Resize state
        self._resizing = False
        self._resize_handle = HANDLE_NONE
        self._resize_start_rect = None  # Original widget rect before resize
        self._resize_start_pos = None  # Mouse position at resize start

        # Grid snap settings
        self._grid_size = 8  # Snap to 8px grid
        self._show_grid = True
        self._snap_guides = []  # List of (orientation, position) for snap lines
        self._snap_guide_rects = []

        # Coordinate display
        self._show_coords = False  # True while dragging/resizing
        self._last_geometry_signal_ts = -1.0
        self._pending_move_signal = None
        self._pending_resize_signal = None
        self._last_pointer_signal_ts = -1.0

        # Background mockup image
        self._bg_image = None       # QPixmap or None
        self._bg_image_visible = True
        self._bg_image_opacity = 0.3  # 0.0 ~ 1.0

        # Rubber-band selection
        self._rubber_band = False
        self._rubber_start = QPoint()
        self._rubber_rect = QRect()
        self._rubber_mode = "replace"
        self._rubber_base_selection = []
        self._rubber_base_primary = None
        self.setFocusPolicy(Qt.StrongFocus)  # Enable keyboard events

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.StyleChange, QEvent.PaletteChange):
            self._paint_palette_cache = None
            self._invalidate_font_metrics_cache()
            self._invalidate_passive_bounds_cache()
            self.update()
        elif event.type() == QEvent.FontChange:
            self._invalidate_font_metrics_cache()
            self._invalidate_passive_bounds_cache()

    def _invalidate_font_metrics_cache(self):
        self._font_pixel_size_cache.clear()
        self._label_font_cache = None
        self._label_font_cache_px = None
        self._coord_font_cache = None
        self._coord_font_cache_px = None

    def _paint_palette(self):
        if self._paint_palette_cache is not None:
            return self._paint_palette_cache
        tokens = app_theme_tokens()
        self._paint_palette_cache = {
            "selected_border": _theme_color(tokens["danger"], 200),
            "selected_fill": _theme_color(tokens["danger"], 40),
            "multi_border": _theme_color(tokens["warning"], 200),
            "multi_fill": _theme_color(tokens["warning"], 40),
            "hover_border": _theme_color(tokens["accent"], 180),
            "hover_fill": _theme_color(tokens["accent"], 30),
            "passive_border_solid": _theme_color(tokens["text_soft"], 180),
            "passive_fill_solid": _theme_color(tokens["accent"], 28),
            "passive_border_clear": _theme_color(tokens["text_soft"], 100),
            "passive_fill_clear": _theme_color(tokens["accent"], 20),
            "grid": _theme_color(tokens["border"], 100),
            "label_bg_full": _theme_color(tokens["panel"], 180),
            "label_text_full": _theme_color(tokens["text"]),
            "label_bg_focus": _theme_color(tokens["panel_raised"], 200),
            "label_text_focus": _theme_color(tokens["text"], 240),
            "snap_guide": _theme_color(tokens["danger"], 180),
            "insert_line": _theme_color(tokens["accent"], 200),
            "rubber_band_border": _theme_color(tokens["accent"], 200),
            "rubber_band_fill": _theme_color(tokens["accent"], 40),
            "handle_border": _theme_color(tokens["text"]),
            "handle_fill": _theme_color(tokens["accent"]),
            "tooltip_bg": _theme_color(tokens["panel"], 240),
            "tooltip_border": _theme_color(tokens["accent"]),
            "tooltip_text": _theme_color(tokens["text"]),
        }
        return self._paint_palette_cache

    def _token_font_pixel_size(self, token_key, fallback):
        cache_key = (token_key, int(fallback))
        if cache_key in self._font_pixel_size_cache:
            return self._font_pixel_size_cache[cache_key]
        tokens = app_theme_tokens(QApplication.instance())
        try:
            value = max(int(tokens.get(token_key, fallback)), 1)
        except (TypeError, ValueError):
            value = max(int(fallback), 1)
        self._font_pixel_size_cache[cache_key] = value
        return value

    def _widget_label_font_pixel_size(self):
        return self._token_font_pixel_size("fs_micro", 10)

    def _coord_tooltip_font_pixel_size(self):
        return self._token_font_pixel_size("fs_micro", 10)

    def _is_lightweight_interaction_active(self):
        return self._dragging or self._resizing or self._rubber_band

    def _show_full_label_overlay(self):
        return True

    def _show_full_bounds_overlay(self):
        return True

    def _show_snap_guides(self):
        return True

    def _dynamic_paint_widgets(self):
        return self._active_paint_widgets

    def _should_use_passive_bounds_cache(self, *, force=False):
        return (force or self._is_lightweight_interaction_active()) and bool(self._visible_widgets)

    def _passive_cache_widgets(self, *, force=False):
        if not self._should_use_passive_bounds_cache(force=force):
            return []
        return self._passive_cache_widget_list

    def _paint_candidate_widgets(self):
        if self._should_use_passive_bounds_cache():
            return self._active_paint_widgets
        return self._visible_widgets

    def _reset_geometry_signal_state(self):
        self._last_geometry_signal_ts = -1.0
        self._pending_move_signal = None
        self._pending_resize_signal = None

    def _reset_pointer_signal_state(self):
        self._last_pointer_signal_ts = -1.0

    def _drag_start_distance(self):
        app = QApplication.instance()
        if app is None:
            return 8
        try:
            return max(int(app.startDragDistance() or 0), 1)
        except Exception:
            return 8

    def _clear_pending_drag_state(self):
        self._pressed_widget = None
        self._press_pos = QPoint()
        self._press_drag_offset = QPoint()

    def _begin_widget_drag(self, widget):
        if widget is None:
            return False
        self._dragging = True
        self._drag_offset = QPoint(self._press_drag_offset)
        self._reorder_mode = _parent_has_layout(widget)
        self._insert_index = -1
        self._insert_line_rect = None
        self._show_coords = not self._reorder_mode
        self._reset_geometry_signal_state()
        if self._reorder_mode:
            self.setCursor(Qt.ClosedHandCursor)
        else:
            self.setCursor(Qt.SizeAllCursor)
        self._clear_pending_drag_state()
        self.drag_started.emit()
        return True

    def _flush_pending_geometry_signals(self):
        if self._pending_move_signal is not None:
            widget, new_x, new_y = self._pending_move_signal
            self.widget_moved.emit(widget, new_x, new_y)
        if self._pending_resize_signal is not None:
            widget, new_w, new_h = self._pending_resize_signal
            self.widget_resized.emit(widget, new_w, new_h)
        self._reset_geometry_signal_state()

    def _emit_geometry_signals(self, widget, new_x, new_y, *, new_w=None, new_h=None):
        if widget is None:
            return
        now = time.monotonic()
        move_payload = (widget, new_x, new_y)
        resize_payload = (widget, new_w, new_h) if new_w is not None and new_h is not None else None
        if (
            self._last_geometry_signal_ts >= 0.0
            and (now - self._last_geometry_signal_ts) < DRAG_GEOMETRY_SIGNAL_INTERVAL_SEC
        ):
            self._pending_move_signal = move_payload
            if resize_payload is not None:
                self._pending_resize_signal = resize_payload
            return
        self.widget_moved.emit(widget, new_x, new_y)
        if resize_payload is not None:
            self.widget_resized.emit(widget, new_w, new_h)
        self._pending_move_signal = None
        self._pending_resize_signal = None
        self._last_geometry_signal_ts = now

    def _refresh_paint_widget_cache(self):
        active_ids = set()
        if self._selected is not None:
            active_ids.add(id(self._selected))
        if self._hovered is not None:
            active_ids.add(id(self._hovered))
        active_ids.update(id(widget) for widget in self._multi_selected)
        if not active_ids:
            self._active_paint_widgets = []
            self._active_paint_widget_ids = set()
            self._passive_cache_widget_list = list(self._visible_widgets)
            self._passive_cache_widget_ids = {id(widget) for widget in self._passive_cache_widget_list}
            return
        self._active_paint_widgets = [widget for widget in self._visible_widgets if id(widget) in active_ids]
        self._active_paint_widget_ids = {id(widget) for widget in self._active_paint_widgets}
        self._passive_cache_widget_list = [widget for widget in self._visible_widgets if id(widget) not in active_ids]
        self._passive_cache_widget_ids = {id(widget) for widget in self._passive_cache_widget_list}

    def _set_hovered_widget(self, widget):
        if widget is self._hovered:
            return False
        self._hovered = widget
        self._refresh_paint_widget_cache()
        return True

    def _widget_label_font(self):
        pixel_size = self._widget_label_font_pixel_size()
        if self._label_font_cache is None or self._label_font_cache_px != pixel_size:
            self._label_font_cache = designer_ui_font(pixel_size=pixel_size)
            self._label_font_cache_px = pixel_size
        return self._label_font_cache

    def _coord_tooltip_font(self):
        pixel_size = self._coord_tooltip_font_pixel_size()
        if self._coord_font_cache is None or self._coord_font_cache_px != pixel_size:
            self._coord_font_cache = designer_monospace_font(pixel_size=pixel_size)
            self._coord_font_cache_px = pixel_size
        return self._coord_font_cache

    def _widget_label_text(self, widget):
        return self._widget_label_text_by_id.get(id(widget), f"{widget.widget_type} : {widget.name}")

    def _bucket_range_for_widget(self, widget):
        cell_size = HIT_TEST_BUCKET_SIZE
        left = int(widget.display_x // cell_size)
        right = int((max(widget.display_x + widget.width - 1, widget.display_x)) // cell_size)
        top = int(widget.display_y // cell_size)
        bottom = int((max(widget.display_y + widget.height - 1, widget.display_y)) // cell_size)
        return left, right, top, bottom

    def _rebuild_hit_test_buckets(self):
        self._hit_test_buckets = {}
        for widget in self._interactive_widgets_reversed:
            left, right, top, bottom = self._bucket_range_for_widget(widget)
            for bx in range(left, right + 1):
                for by in range(top, bottom + 1):
                    self._hit_test_buckets.setdefault((bx, by), []).append(widget)

    def _rebuild_selection_buckets(self):
        self._selection_buckets = {}
        for widget in self._visible_widgets:
            left, right, top, bottom = self._bucket_range_for_widget(widget)
            for bx in range(left, right + 1):
                for by in range(top, bottom + 1):
                    self._selection_buckets.setdefault((bx, by), []).append(widget)

    def _hit_test_candidates(self, pos):
        cell_size = HIT_TEST_BUCKET_SIZE
        return self._hit_test_buckets.get((int(pos.x() // cell_size), int(pos.y() // cell_size)), [])

    def _selection_candidates_for_rect(self, rect):
        if rect is None or rect.isNull():
            return []
        cell_size = HIT_TEST_BUCKET_SIZE
        left = int(rect.left() // cell_size)
        right = int(rect.right() // cell_size)
        top = int(rect.top() // cell_size)
        bottom = int(rect.bottom() // cell_size)
        seen = set()
        candidates = []
        for bx in range(left, right + 1):
            for by in range(top, bottom + 1):
                for widget in self._selection_buckets.get((bx, by), ()):
                    widget_id = id(widget)
                    if widget_id in seen:
                        continue
                    seen.add(widget_id)
                    candidates.append(widget)
        return candidates

    def _visible_candidates_for_rect(self, rect):
        candidates = self._selection_candidates_for_rect(rect)
        if not candidates:
            return []
        return sorted(candidates, key=lambda widget: self._visible_widget_order_by_id.get(id(widget), 1 << 30))

    def _paint_widgets_for_visible_rect(self, widgets, visible_logical_rect, *, widget_ids=None):
        if visible_logical_rect is None or visible_logical_rect.isNull():
            return widgets
        if len(widgets) <= 12:
            return widgets
        candidates = self._visible_candidates_for_rect(visible_logical_rect)
        if widgets is self._visible_widgets:
            return candidates
        allowed_ids = widget_ids if widget_ids is not None else {id(widget) for widget in widgets}
        return [widget for widget in candidates if id(widget) in allowed_ids]

    @staticmethod
    def _point_hits_widget(pos, widget):
        x = pos.x()
        y = pos.y()
        return (
            widget.display_x <= x < (widget.display_x + widget.width)
            and widget.display_y <= y < (widget.display_y + widget.height)
        )

    @staticmethod
    def _rect_intersects_widget(rect, widget):
        if rect is None or rect.isNull():
            return False
        left = widget.display_x
        top = widget.display_y
        right = left + widget.width
        bottom = top + widget.height
        return not (
            rect.right() < left
            or rect.left() >= right
            or rect.bottom() < top
            or rect.top() >= bottom
        )

    @staticmethod
    def _widget_intersects_visible_rect(widget, visible_logical_rect):
        if visible_logical_rect is None or visible_logical_rect.isNull():
            return True
        left = widget.display_x
        top = widget.display_y
        right = left + widget.width
        bottom = top + widget.height
        return not (
            visible_logical_rect.right() < left
            or visible_logical_rect.left() >= right
            or visible_logical_rect.bottom() < top
            or visible_logical_rect.top() >= bottom
        )

    def _widget_edge_triplets(self, widget, *, axis="x"):
        if axis == "y":
            start = widget.display_y
            size = widget.height
        else:
            start = widget.display_x
            size = widget.width
        return (start, start + size // 2, start + size)

    def _logical_visible_rect(self, screen_rect, zoom):
        if zoom <= 0:
            return QRectF()
        margin = 8.0 / zoom
        return QRectF(
            (screen_rect.x() / zoom) - margin,
            (screen_rect.y() / zoom) - margin,
            (screen_rect.width() / zoom) + margin * 2,
            (screen_rect.height() / zoom) + margin * 2,
        )

    def _screen_rect_for_logical_bounds(self, x, y, w, h, *, padding=24):
        sx = int(x * self._zoom)
        sy = int(y * self._zoom)
        sw = max(int(w * self._zoom), 1)
        sh = max(int(h * self._zoom), 1)
        rect = QRect(sx - padding, sy - padding - 20, sw + padding * 2, sh + padding * 2 + 40)
        return rect.intersected(self.rect())

    def _screen_rect_for_logical_rect(self, rect, *, padding=12):
        if rect is None or rect.isNull():
            return QRect()
        return self._screen_rect_for_logical_bounds(rect.x(), rect.y(), rect.width(), rect.height(), padding=padding)

    def _screen_rect_for_guides(self, guides):
        rects = []
        for orientation, pos in guides or []:
            if orientation == 'v':
                x = int(pos * self._zoom)
                rects.append(QRect(x - 3, 0, 7, self.height()).intersected(self.rect()))
            else:
                y = int(pos * self._zoom)
                rects.append(QRect(0, y - 3, self.width(), 7).intersected(self.rect()))
        return rects

    def _set_snap_guides(self, guides):
        self._snap_guides = list(guides or [])
        self._snap_guide_rects = self._screen_rect_for_guides(self._snap_guides)

    def _update_regions(self, *rects):
        first_rect = None
        dirty_region = None
        for rect in rects:
            if isinstance(rect, QRect) and not rect.isNull():
                if first_rect is None:
                    first_rect = rect
                elif dirty_region is None:
                    dirty_region = QRegion(first_rect).united(QRegion(rect))
                else:
                    dirty_region = dirty_region.united(QRegion(rect))
        if dirty_region is not None and not dirty_region.isEmpty():
            self.update(dirty_region)
        elif first_rect is not None:
            self.update(first_rect)

    def _update_regions_for_guides(self, guides):
        self._update_regions(*self._screen_rect_for_guides(guides))

    def _update_regions_for_guide_rects(self, rects):
        self._update_regions(*(rects or ()))

    def _update_regions_for_geometry_and_guides(self, geometry_rects, old_guide_rects=None, new_guide_rects=None):
        rects = list(geometry_rects or ())
        if old_guide_rects:
            rects.extend(old_guide_rects)
        if new_guide_rects:
            rects.extend(new_guide_rects)
        self._update_regions(*rects)

    def _invalidate_passive_bounds_cache(self):
        self._passive_bounds_cache = None
        self._passive_bounds_cache_key = None
        self._passive_bounds_cache_rect = QRect()
        self._passive_cache_warmup_serial += 1

    def _schedule_passive_bounds_cache_warmup(self):
        if not self._visible_widgets or self._pressed_widget is None:
            return
        self._passive_cache_warmup_serial += 1
        serial = self._passive_cache_warmup_serial
        QTimer.singleShot(0, lambda serial=serial: self._warm_passive_bounds_cache(serial))

    def _warm_passive_bounds_cache(self, serial):
        if serial != self._passive_cache_warmup_serial:
            return
        if self._pressed_widget is None or self._dragging or self._resizing or self._rubber_band:
            return
        self._ensure_passive_bounds_cache(force=True)

    def _visible_screen_rect_for_cache(self):
        visible_region = self.visibleRegion()
        if visible_region.isEmpty():
            return self.rect()
        rect = visible_region.boundingRect().intersected(self.rect())
        if rect.isNull():
            return self.rect()
        return rect

    def _passive_bounds_cache_state_key(self, cache_rect=None):
        if cache_rect is None:
            cache_rect = self._visible_screen_rect_for_cache()
        bg_cache_key = 0
        if self._bg_image is not None:
            cache_key_getter = getattr(self._bg_image, "cacheKey", None)
            if callable(cache_key_getter):
                bg_cache_key = int(cache_key_getter())
            else:
                bg_cache_key = id(self._bg_image)
        return (
            cache_rect.x(),
            cache_rect.y(),
            cache_rect.width(),
            cache_rect.height(),
            round(float(self._zoom), 4),
            bool(self._solid_background),
            bool(self._show_grid),
            int(self._grid_size),
            bool(self._bg_image is not None and self._bg_image_visible),
            round(float(self._bg_image_opacity), 3),
            bg_cache_key,
            self._widget_label_font_pixel_size(),
        )

    def _widget_bounds_style(self, widget, z, *, passive_only=False, palette=None):
        palette = self._paint_palette() if palette is None else palette
        if not passive_only:
            if widget == self._selected:
                return (
                    QPen(palette["selected_border"], 2.0 / z, Qt.SolidLine),
                    QColor(palette["selected_fill"]),
                )
            if widget in self._multi_selected:
                return (
                    QPen(palette["multi_border"], 2.0 / z, Qt.SolidLine),
                    QColor(palette["multi_fill"]),
                )
            if widget == self._hovered:
                return (
                    QPen(palette["hover_border"], 1.5 / z, Qt.DashLine),
                    QColor(palette["hover_fill"]),
                )

        if self._solid_background:
            return (
                QPen(palette["passive_border_solid"], 1.0 / z, Qt.DotLine),
                QColor(palette["passive_fill_solid"]),
            )
        return (
            QPen(palette["passive_border_clear"], 1.0 / z, Qt.DotLine),
            QColor(palette["passive_fill_clear"]),
        )

    def _draw_widget_bounds(self, painter, widgets, z, *, visible_logical_rect=None, passive_only=False, palette=None):
        palette = self._paint_palette() if palette is None else palette
        widget_ids = None
        if widgets is self._passive_cache_widget_list:
            widget_ids = self._passive_cache_widget_ids
        elif widgets is self._active_paint_widgets:
            widget_ids = self._active_paint_widget_ids
        for widget in self._paint_widgets_for_visible_rect(widgets, visible_logical_rect, widget_ids=widget_ids):
            if not self._widget_intersects_visible_rect(widget, visible_logical_rect):
                continue
            rect = QRect(widget.display_x, widget.display_y, widget.width, widget.height)
            pen, fill = self._widget_bounds_style(widget, z, passive_only=passive_only, palette=palette)
            painter.setPen(pen)
            painter.setBrush(fill)
            painter.drawRect(rect)

    @staticmethod
    def _grid_line_positions(limit, grid_size, visible_logical_rect, axis):
        if grid_size < 1 or limit <= 0:
            return []
        if visible_logical_rect is None or visible_logical_rect.isNull():
            start = 0
            end = limit
        else:
            start_value = visible_logical_rect.left() if axis == "x" else visible_logical_rect.top()
            end_value = visible_logical_rect.right() if axis == "x" else visible_logical_rect.bottom()
            start = max(0, int(math.floor(start_value / grid_size)) * grid_size)
            end = min(limit, int(math.ceil(end_value / grid_size)) * grid_size + grid_size)
        return range(start, max(start, end), grid_size)

    def _draw_background_and_grid(self, painter, z, bw, bh, *, visible_logical_rect=None, palette=None):
        palette = self._paint_palette() if palette is None else palette
        if self._bg_image is not None and self._bg_image_visible:
            painter.save()
            painter.setOpacity(self._bg_image_opacity)
            painter.drawPixmap(0, 0, self._bg_image)
            painter.restore()

        eff_grid = self._effective_grid_size()
        if self._show_grid and eff_grid >= 1 and self._solid_background:
            painter.setPen(QPen(palette["grid"], 1.0 / z, Qt.DotLine))
            for x in self._grid_line_positions(bw, eff_grid, visible_logical_rect, "x"):
                painter.drawLine(x, 0, x, bh)
            for y in self._grid_line_positions(bh, eff_grid, visible_logical_rect, "y"):
                painter.drawLine(0, y, bw, y)

    def _draw_widget_labels(
        self,
        painter,
        widgets,
        z,
        *,
        event_rect,
        visible_logical_rect=None,
        show_full_labels=None,
        palette=None,
    ):
        palette = self._paint_palette() if palette is None else palette
        painter.setFont(self._widget_label_font())
        fm = painter.fontMetrics()
        lh = fm.height() + 2
        show_full = self._show_full_label_overlay() if show_full_labels is None else bool(show_full_labels)

        widget_ids = None
        if widgets is self._passive_cache_widget_list:
            widget_ids = self._passive_cache_widget_ids
        elif widgets is self._active_paint_widgets:
            widget_ids = self._active_paint_widget_ids
        for w in self._paint_widgets_for_visible_rect(widgets, visible_logical_rect, widget_ids=widget_ids):
            if not self._widget_intersects_visible_rect(w, visible_logical_rect):
                continue
            if not show_full and w not in {self._selected, self._hovered} and w not in self._multi_selected:
                continue
            sx = int(w.display_x * z)
            sy = int(w.display_y * z)
            sw = int(w.width * z)
            sh = int(w.height * z)
            label_text = self._widget_label_text(w)

            if self._solid_background and show_full:
                if sh < lh:
                    continue
                label_rect = QRect(sx, sy, sw, lh)
                if not event_rect.intersects(label_rect):
                    continue
                painter.fillRect(label_rect, palette["label_bg_full"])
                painter.setPen(palette["label_text_full"])
                text_rect = QRect(sx + 3, sy, max(sw - 6, 0), lh)
                painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, label_text)
            elif w == self._selected or w == self._hovered:
                lw = max(sw, fm.horizontalAdvance(label_text) + 8)
                label_rect = QRect(sx, sy - lh, lw, lh)
                if not event_rect.intersects(label_rect):
                    continue
                painter.fillRect(label_rect, palette["label_bg_focus"])
                painter.setPen(palette["label_text_focus"])
                painter.drawText(label_rect, Qt.AlignCenter, label_text)

    def _ensure_passive_bounds_cache(self, *, force=False):
        if not self._should_use_passive_bounds_cache(force=force):
            return None
        cache_rect = self._visible_screen_rect_for_cache()
        if cache_rect.width() <= 0 or cache_rect.height() <= 0:
            return None
        cache_key = self._passive_bounds_cache_state_key(cache_rect)
        if self._passive_bounds_cache is not None and self._passive_bounds_cache_key == cache_key:
            return self._passive_bounds_cache

        pixmap = QPixmap(cache_rect.size())
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.scale(self._zoom, self._zoom)
        painter.translate(-(cache_rect.x() / self._zoom), -(cache_rect.y() / self._zoom))
        self._draw_background_and_grid(
            painter,
            self._zoom,
            self._base_width,
            self._base_height,
            visible_logical_rect=self._logical_visible_rect(cache_rect, self._zoom),
        )
        self._draw_widget_bounds(
            painter,
            self._passive_cache_widgets(force=force),
            self._zoom,
            visible_logical_rect=self._logical_visible_rect(cache_rect, self._zoom),
            passive_only=True,
        )
        painter.resetTransform()
        painter.translate(-cache_rect.x(), -cache_rect.y())
        self._draw_widget_labels(
            painter,
            self._passive_cache_widgets(force=force),
            self._zoom,
            event_rect=cache_rect,
            visible_logical_rect=self._logical_visible_rect(cache_rect, self._zoom),
            show_full_labels=True,
        )
        painter.end()
        self._passive_bounds_cache = pixmap
        self._passive_bounds_cache_key = cache_key
        self._passive_bounds_cache_rect = cache_rect
        return self._passive_bounds_cache

    def _nearest_snap_hit(self, edge_values, edge_entries, target_edge, threshold, widget_id):
        if not edge_values:
            return None
        values = edge_values
        entries = edge_entries
        total = len(values)
        best_edge = None
        best_delta = None
        right = bisect.bisect_left(values, target_edge)
        left = right - 1

        while left >= 0 or right < total:
            left_delta = None
            if left >= 0:
                left_delta = target_edge - values[left]
            right_delta = None
            if right < total:
                right_delta = values[right] - target_edge

            use_left = right_delta is None or (left_delta is not None and left_delta <= right_delta)
            if use_left:
                delta = left_delta
                idx = left
                left -= 1
            else:
                delta = right_delta
                idx = right
                right += 1

            if delta is None or delta >= threshold:
                if best_delta is not None:
                    break
                if (left_delta is None or left_delta >= threshold) and (right_delta is None or right_delta >= threshold):
                    break
                continue

            if best_delta is not None and delta > best_delta:
                break

            edge, owner_id = entries[idx]
            if owner_id == widget_id:
                continue
            if best_delta is None or delta < best_delta:
                best_edge = edge
                best_delta = delta
                if best_delta == 0:
                    break
        return best_edge

    def _snap_lookup_for_widget(self, widget, axis):
        if widget is None or widget.parent is None:
            if axis == "y":
                return self._snap_edges_y_values, self._snap_edges_y
            return self._snap_edges_x_values, self._snap_edges_x

        parent_id = id(widget.parent)
        if axis == "y":
            return (
                self._snap_edges_y_values_lookup_by_parent.get(parent_id, self._snap_edges_y_values),
                self._snap_edges_y_lookup_by_parent.get(parent_id, self._snap_edges_y),
            )
        return (
            self._snap_edges_x_values_lookup_by_parent.get(parent_id, self._snap_edges_x_values),
            self._snap_edges_x_lookup_by_parent.get(parent_id, self._snap_edges_x),
        )

    def _parent_display_origin(self, widget):
        parent = getattr(widget, "parent", None)
        if parent is None:
            return 0, 0
        return int(getattr(parent, "display_x", parent.x)), int(getattr(parent, "display_y", parent.y))

    def _snap_drag_axis(
        self,
        widget,
        proposed_pos,
        size,
        *,
        axis,
        eff_grid,
        min_pos,
        max_pos,
    ):
        snap_threshold = 5
        widget_id = id(widget) if widget is not None else 0
        edge_values, edge_entries = self._snap_lookup_for_widget(widget, axis)
        max_pos = max(min_pos, max_pos)
        best_hit = None
        best_offset = 0
        best_delta = None

        for offset in (0, size // 2, size):
            target_edge = proposed_pos + offset
            hit = self._nearest_snap_hit(
                edge_values,
                edge_entries,
                target_edge,
                snap_threshold,
                widget_id,
            )
            if hit is None:
                continue
            snapped_pos = hit - offset
            if snapped_pos < min_pos or snapped_pos > max_pos:
                continue
            delta = abs(target_edge - hit)
            if best_delta is None or delta < best_delta:
                best_hit = hit
                best_offset = offset
                best_delta = delta

        if best_hit is not None:
            return best_hit - best_offset, best_hit
        if eff_grid >= 1:
            return max(min_pos, min(max_pos, _snap_to_grid(proposed_pos, eff_grid))), None
        return max(min_pos, min(max_pos, proposed_pos)), None

    def _snap_resize_edge(
        self,
        widget,
        proposed_edge,
        *,
        axis,
        eff_grid,
        min_pos,
        max_pos,
    ):
        snap_threshold = 5
        widget_id = id(widget) if widget is not None else 0
        edge_values, edge_entries = self._snap_lookup_for_widget(widget, axis)
        max_pos = max(min_pos, max_pos)
        hit = self._nearest_snap_hit(
            edge_values,
            edge_entries,
            proposed_edge,
            snap_threshold,
            widget_id,
        )
        if hit is not None and min_pos <= hit <= max_pos:
            return hit, hit
        if eff_grid >= 1:
            return max(min_pos, min(max_pos, _snap_to_grid(proposed_edge, eff_grid))), None
        return max(min_pos, min(max_pos, proposed_edge)), None

    def _refresh_surface_style(self):
        self.setProperty("solidBackground", bool(self._solid_background))
        self.style().unpolish(self)
        self.style().polish(self)
        self._invalidate_passive_bounds_cache()
        self.update()

    # ── Zoom helpers ───────────────────────────────────────────────

    def set_base_size(self, w, h):
        """Set the logical (unscaled) canvas size."""
        self._base_width = w
        self._base_height = h
        self._apply_zoom()

    def _apply_zoom(self):
        """Resize the widget according to the current zoom factor."""
        new_w = int(self._base_width * self._zoom)
        new_h = int(self._base_height * self._zoom)
        self.setFixedSize(new_w, new_h)
        self._invalidate_passive_bounds_cache()
        if self._snap_guides:
            self._snap_guide_rects = self._screen_rect_for_guides(self._snap_guides)
        self.update()

    def set_zoom(self, factor):
        factor = max(self._zoom_min, min(self._zoom_max, factor))
        if factor != self._zoom:
            self._zoom = factor
            self._apply_zoom()
            self.zoom_changed.emit(self._zoom)

    def zoom_in(self):
        self.set_zoom(self._zoom * 1.15)

    def zoom_out(self):
        self.set_zoom(self._zoom / 1.15)

    def zoom_reset(self):
        self.set_zoom(1.0)

    def _to_logical(self, pos):
        """Convert screen-space mouse position to logical (unscaled) position."""
        return QPoint(int(pos.x() / self._zoom), int(pos.y() / self._zoom))

    def wheelEvent(self, event):
        """Ctrl+Scroll to zoom in/out."""
        if event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom_in()
            elif delta < 0:
                self.zoom_out()
            event.accept()
        else:
            super().wheelEvent(event)

    def set_grid_size(self, size):
        """Set base grid snap size (0 to disable)."""
        self._grid_size = max(0, size)
        self._invalidate_passive_bounds_cache()
        self.update()

    def _effective_grid_size(self):
        """Return the configured logical grid size."""
        if self._grid_size <= 0:
            return 0
        return self._grid_size

    def set_show_grid(self, show):
        """Toggle grid visibility."""
        self._show_grid = show
        self._invalidate_passive_bounds_cache()
        self.update()

    def show_grid(self):
        return self._show_grid

    def grid_size(self):
        return self._grid_size

    def set_solid_background(self, solid):
        """Switch between transparent overlay and solid background mode."""
        self._solid_background = solid
        self.setAttribute(Qt.WA_TranslucentBackground, not solid)
        self.setAutoFillBackground(bool(solid))
        self._refresh_surface_style()

    # ── Background mockup image ──────────────────────────────────

    def set_background_image(self, pixmap):
        """Set the background mockup image (QPixmap). None to clear."""
        self._bg_image = pixmap
        self._invalidate_passive_bounds_cache()
        self.update()

    def set_background_image_visible(self, visible):
        """Toggle background image visibility."""
        self._bg_image_visible = visible
        self._invalidate_passive_bounds_cache()
        self.update()

    def set_background_image_opacity(self, opacity):
        """Set background image opacity (0.0 to 1.0)."""
        self._bg_image_opacity = max(0.0, min(1.0, opacity))
        self._invalidate_passive_bounds_cache()
        self.update()

    def clear_background_image(self):
        """Remove the background image."""
        self._bg_image = None
        self._invalidate_passive_bounds_cache()
        self.update()

    def set_widgets(self, widgets):
        """Set the flat list of widgets to display."""
        self._widgets = widgets or []
        self._visible_widgets = [widget for widget in self._widgets if not self._is_hidden(widget)]
        self._interactive_widgets = [widget for widget in self._visible_widgets if not self._is_locked(widget)]
        self._interactive_widgets_reversed = list(reversed(self._interactive_widgets))
        self._rebuild_hit_test_buckets()
        self._rebuild_selection_buckets()
        self._visible_non_root_widgets = any(widget.parent is not None for widget in self._visible_widgets)
        self._root_widget = next((widget for widget in self._visible_widgets if widget.parent is None), None)
        self._widget_label_text_by_id = {}
        self._visible_widget_order_by_id = {id(widget): index for index, widget in enumerate(self._visible_widgets)}
        for widget in self._visible_widgets:
            label_text = f"{widget.widget_type} : {widget.name}"
            if self._is_locked(widget):
                label_text += " [L]"
            self._widget_label_text_by_id[id(widget)] = label_text
        self._snap_target_edges = [
            (widget, self._widget_edge_triplets(widget, axis="x"), self._widget_edge_triplets(widget, axis="y"))
            for widget in self._visible_widgets
        ]
        self._snap_edges_x = sorted(
            (edge, id(widget))
            for widget, x_edges, _ in self._snap_target_edges
            for edge in x_edges
        )
        self._snap_edges_y = sorted(
            (edge, id(widget))
            for widget, _, y_edges in self._snap_target_edges
            for edge in y_edges
        )
        self._snap_edges_x_values = [edge for edge, _ in self._snap_edges_x]
        self._snap_edges_y_values = [edge for edge, _ in self._snap_edges_y]
        root_entries_x = []
        root_entries_y = []
        if self._root_widget is not None:
            root_id = id(self._root_widget)
            root_entries_x = [(edge, root_id) for edge in self._widget_edge_triplets(self._root_widget, axis="x")]
            root_entries_y = [(edge, root_id) for edge in self._widget_edge_triplets(self._root_widget, axis="y")]
        self._snap_edges_x_lookup_by_parent = {}
        self._snap_edges_x_values_lookup_by_parent = {}
        self._snap_edges_y_lookup_by_parent = {}
        self._snap_edges_y_values_lookup_by_parent = {}
        widgets_by_parent = {}
        for widget in self._visible_widgets:
            if widget.parent is not None:
                widgets_by_parent.setdefault(id(widget.parent), []).append(widget)
        for parent_id, widgets in widgets_by_parent.items():
            entries_x = sorted(
                [(edge, id(widget)) for widget in widgets for edge in self._widget_edge_triplets(widget, axis="x")] + root_entries_x
            )
            entries_y = sorted(
                [(edge, id(widget)) for widget in widgets for edge in self._widget_edge_triplets(widget, axis="y")] + root_entries_y
            )
            self._snap_edges_x_lookup_by_parent[parent_id] = entries_x
            self._snap_edges_x_values_lookup_by_parent[parent_id] = [edge for edge, _ in entries_x]
            self._snap_edges_y_lookup_by_parent[parent_id] = entries_y
            self._snap_edges_y_values_lookup_by_parent[parent_id] = [edge for edge, _ in entries_y]
        valid_ids = {id(widget) for widget in self._widgets}
        self._multi_selected = {widget for widget in self._multi_selected if id(widget) in valid_ids}
        if self._selected is not None and id(self._selected) not in valid_ids:
            self._selected = None
        if self._hovered is not None and id(self._hovered) not in valid_ids:
            self._hovered = None
        self._refresh_paint_widget_cache()
        self._invalidate_passive_bounds_cache()
        self.update()

    def set_selected(self, widget):
        """Set the currently selected widget."""
        self.set_selection([widget] if widget is not None else [], primary=widget)

    def set_selection(self, widgets, primary=None):
        widgets = [widget for widget in (widgets or []) if widget is not None]
        if not widgets:
            if self._selected is None and not self._multi_selected:
                return
            self._selected = None
            self._multi_selected.clear()
            self._refresh_paint_widget_cache()
            self._invalidate_passive_bounds_cache()
            self.update()
            return
        if primary is None or all(widget is not primary for widget in widgets):
            primary = widgets[-1]
        next_multi = {widget for widget in widgets if widget is not primary}
        if primary is self._selected and next_multi == self._multi_selected:
            return
        self._selected = primary
        self._multi_selected = next_multi
        self._refresh_paint_widget_cache()
        self._invalidate_passive_bounds_cache()
        self.update()

    def selected_widgets(self):
        ordered = []
        for widget in self._widgets:
            if widget is self._selected or widget in self._multi_selected:
                ordered.append(widget)
        if self._selected is not None and all(widget is not self._selected for widget in ordered):
            ordered.append(self._selected)
        return ordered

    def _emit_selection_changed(self):
        widgets = self.selected_widgets()
        self.widget_selected.emit(self._selected)
        self.selection_changed.emit(widgets, self._selected)

    def _emit_mouse_position_changed(self, x, y, widget):
        if self._dragging or self._resizing or self._rubber_band:
            now = time.monotonic()
            if (
                self._last_pointer_signal_ts >= 0.0
                and (now - self._last_pointer_signal_ts) < DRAG_POINTER_SIGNAL_INTERVAL_SEC
            ):
                return
            self._last_pointer_signal_ts = now
        else:
            self._reset_pointer_signal_state()
        self.mouse_position_changed.emit(x, y, widget)

    def _is_hidden(self, widget):
        return bool(getattr(widget, "designer_hidden", False))

    def _is_locked(self, widget):
        return bool(getattr(widget, "designer_locked", False))

    def _has_visible_non_root_widgets(self):
        return self._visible_non_root_widgets

    def _widget_at(self, pos, *, allow_root=True):
        """Find widget at given position using display coordinates."""
        hide_root = not allow_root and self._has_visible_non_root_widgets()
        for w in self._hit_test_candidates(pos):
            if hide_root and w.parent is None:
                continue
            if self._point_hits_widget(pos, w):
                return w
        return None

    def _ordered_widgets(self, widgets):
        widget_ids = {id(widget) for widget in widgets if widget is not None}
        return [widget for widget in self._widgets if id(widget) in widget_ids]

    def _filter_bulk_selection_widgets(self, widgets):
        filtered = [widget for widget in widgets if widget is not None and not self._is_hidden(widget)]
        if any(widget.parent is not None for widget in filtered):
            filtered = [widget for widget in filtered if widget.parent is not None]
        return filtered

    def _selection_after_rubber_band(self, matched_widgets):
        matched = self._ordered_widgets(self._filter_bulk_selection_widgets(matched_widgets))
        previous_primary = self._rubber_base_primary
        base_selection = self._ordered_widgets(self._rubber_base_selection)

        if self._rubber_mode == "add":
            final = base_selection + [widget for widget in matched if widget not in base_selection]
            if previous_primary in final:
                return final, previous_primary
            if matched:
                return final, matched[-1]
            if final:
                return final, final[-1]
            return [], None

        if self._rubber_mode == "toggle":
            final = [widget for widget in base_selection if widget not in matched]
            final.extend(widget for widget in matched if widget not in base_selection)
            if previous_primary in final:
                return final, previous_primary
            if final:
                return final, final[-1]
            return [], None

        if previous_primary in matched:
            return matched, previous_primary
        if matched:
            return matched, matched[-1]
        return [], None

    def _get_handle_rects(self, widget):
        """Get rectangles for all 8 resize handles of a widget.

        Returns rects in *logical* space but handle size is divided by the
        current zoom so that handles appear as constant screen-pixels.
        """
        if widget is None:
            return {}
        x, y = widget.display_x, widget.display_y
        w, h = widget.width, widget.height
        hs = HANDLE_SIZE / self._zoom   # constant screen size
        hh = hs / 2.0

        def _r(cx, cy):
            return QRectF(cx - hh, cy - hh, hs, hs)

        return {
            HANDLE_TOP_LEFT:     _r(x, y),
            HANDLE_TOP:          _r(x + w / 2, y),
            HANDLE_TOP_RIGHT:    _r(x + w, y),
            HANDLE_RIGHT:        _r(x + w, y + h / 2),
            HANDLE_BOTTOM_RIGHT: _r(x + w, y + h),
            HANDLE_BOTTOM:       _r(x + w / 2, y + h),
            HANDLE_BOTTOM_LEFT:  _r(x, y + h),
            HANDLE_LEFT:         _r(x, y + h / 2),
        }

    def _handle_at(self, pos):
        """Check if position is over a resize handle of the selected widget.

        Returns HANDLE_NONE if widget is in a layout container (no resize allowed).
        """
        if self._selected is None:
            return HANDLE_NONE
        # No resize handles for widgets inside LinearLayout etc.
        if _parent_has_layout(self._selected) or self._is_locked(self._selected):
            return HANDLE_NONE
        handles = self._get_handle_rects(self._selected)
        posf = QPointF(pos)
        for handle_id, rect in handles.items():
            if rect.contains(posf):
                return handle_id
        return HANDLE_NONE

    def _cursor_for_handle(self, handle):
        """Get appropriate cursor for a resize handle."""
        cursors = {
            HANDLE_TOP_LEFT: Qt.SizeFDiagCursor,
            HANDLE_TOP: Qt.SizeVerCursor,
            HANDLE_TOP_RIGHT: Qt.SizeBDiagCursor,
            HANDLE_RIGHT: Qt.SizeHorCursor,
            HANDLE_BOTTOM_RIGHT: Qt.SizeFDiagCursor,
            HANDLE_BOTTOM: Qt.SizeVerCursor,
            HANDLE_BOTTOM_LEFT: Qt.SizeBDiagCursor,
            HANDLE_LEFT: Qt.SizeHorCursor,
        }
        return cursors.get(handle, Qt.ArrowCursor)

    def _compute_insert_index(self, widget, mouse_pos):
        """Compute the target insertion index based on mouse position."""
        parent = widget.parent
        if parent is None or not parent.children:
            return -1, None

        siblings = parent.children
        is_horizontal = _parent_is_horizontal(widget)
        best_index = len(siblings)
        best_rect = None

        for i, sibling in enumerate(siblings):
            if is_horizontal:
                center_x = sibling.display_x + sibling.width // 2
                if mouse_pos.x() < center_x:
                    best_index = i
                    best_rect = QRect(sibling.display_x - 2, sibling.display_y, 4, sibling.height)
                    break
            else:
                center_y = sibling.display_y + sibling.height // 2
                if mouse_pos.y() < center_y:
                    best_index = i
                    best_rect = QRect(sibling.display_x, sibling.display_y - 2, sibling.width, 4)
                    break

        if best_rect is None and siblings:
            last = siblings[-1]
            if is_horizontal:
                best_rect = QRect(last.display_x + last.width - 2, last.display_y, 4, last.height)
            else:
                best_rect = QRect(last.display_x, last.display_y + last.height - 2, last.width, 4)

        return best_index, best_rect

    def _find_snap_guides(self, widget, new_x, new_y, new_w, new_h):
        """Find snap guide lines based on other widgets' edges."""
        if not self._show_snap_guides():
            return []
        snap_threshold = 5
        widget_id = id(widget) if widget is not None else 0
        edge_values_x, edge_entries_x = self._snap_lookup_for_widget(widget, "x")
        edge_values_y, edge_entries_y = self._snap_lookup_for_widget(widget, "y")
        vertical_guides = set()
        horizontal_guides = set()

        edges_x = [new_x, new_x + new_w // 2, new_x + new_w]  # left, center, right
        edges_y = [new_y, new_y + new_h // 2, new_y + new_h]  # top, center, bottom

        for ex in edges_x:
            hit = self._nearest_snap_hit(
                edge_values_x,
                edge_entries_x,
                ex,
                snap_threshold,
                widget_id,
            )
            if hit is not None:
                vertical_guides.add(hit)
        for ey in edges_y:
            hit = self._nearest_snap_hit(
                edge_values_y,
                edge_entries_y,
                ey,
                snap_threshold,
                widget_id,
            )
            if hit is not None:
                horizontal_guides.add(hit)

        guides = [('v', pos) for pos in sorted(vertical_guides)]
        guides.extend(('h', pos) for pos in sorted(horizontal_guides))
        return guides

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, not self._is_lightweight_interaction_active())
        painter.setRenderHint(QPainter.TextAntialiasing)

        z = self._zoom
        bw, bh = self._base_width, self._base_height
        visible_logical_rect = self._logical_visible_rect(event.rect(), z)
        use_passive_bounds_cache = self._should_use_passive_bounds_cache()
        palette = self._paint_palette()

        # ── Phase 1: Scaled space (geometry) ──────────────────────
        painter.scale(z, z)

        if use_passive_bounds_cache:
            painter.resetTransform()
            passive_cache = self._ensure_passive_bounds_cache()
            if passive_cache is not None:
                cache_rect = self._passive_bounds_cache_rect
                target_rect = event.rect().intersected(cache_rect)
                if not target_rect.isNull():
                    source_rect = target_rect.translated(-cache_rect.x(), -cache_rect.y())
                    painter.drawPixmap(target_rect, passive_cache, source_rect)
            painter.scale(z, z)
        else:
            self._draw_background_and_grid(
                painter,
                z,
                bw,
                bh,
                visible_logical_rect=visible_logical_rect,
                palette=palette,
            )

        self._draw_widget_bounds(
            painter,
            self._paint_candidate_widgets(),
            z,
            visible_logical_rect=visible_logical_rect,
            palette=palette,
        )

        # Draw snap guide lines (in logical space)
        if self._snap_guides:
            painter.setPen(QPen(palette["snap_guide"], 1.0 / z, Qt.DashLine))
            for orientation, pos in self._snap_guides:
                if orientation == 'v':
                    painter.drawLine(pos, 0, pos, bh)
                else:
                    painter.drawLine(0, pos, bw, pos)

        # Draw insertion indicator line for reorder mode
        if self._reorder_mode and self._insert_line_rect is not None:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(palette["insert_line"]))
            painter.drawRect(self._insert_line_rect)

        # Draw rubber-band selection rectangle
        if self._rubber_band and not self._rubber_rect.isNull():
            painter.setPen(QPen(palette["rubber_band_border"], 1.0 / z, Qt.DashLine))
            painter.setBrush(QBrush(palette["rubber_band_fill"]))
            painter.drawRect(self._rubber_rect)

        # ── Phase 2: Screen space (text, handles, tooltips) ──────
        painter.resetTransform()

        # Helper: logical → screen coordinate conversion
        def _s(v):
            return int(v * z)

        label_widgets = self._paint_candidate_widgets() if use_passive_bounds_cache else self._visible_widgets
        self._draw_widget_labels(
            painter,
            label_widgets,
            z,
            event_rect=event.rect(),
            visible_logical_rect=visible_logical_rect,
            palette=palette,
        )

        # Draw resize handles in screen space (constant pixel size)
        if self._selected and not _parent_has_layout(self._selected) and not self._is_locked(self._selected):
            sel = self._selected
            sx, sy = _s(sel.display_x), _s(sel.display_y)
            sw, sh = _s(sel.width), _s(sel.height)
            hs = HANDLE_SIZE
            hh = hs // 2
            screen_handles = [
                QRect(sx - hh, sy - hh, hs, hs),                     # top-left
                QRect(sx + sw // 2 - hh, sy - hh, hs, hs),           # top
                QRect(sx + sw - hh, sy - hh, hs, hs),                # top-right
                QRect(sx + sw - hh, sy + sh // 2 - hh, hs, hs),      # right
                QRect(sx + sw - hh, sy + sh - hh, hs, hs),           # bottom-right
                QRect(sx + sw // 2 - hh, sy + sh - hh, hs, hs),      # bottom
                QRect(sx - hh, sy + sh - hh, hs, hs),                # bottom-left
                QRect(sx - hh, sy + sh // 2 - hh, hs, hs),           # left
            ]
            painter.setPen(QPen(palette["handle_border"], 1))
            painter.setBrush(QBrush(palette["handle_fill"]))
            for r in screen_handles:
                painter.drawRect(r)

        # Draw coordinate tooltip in screen space while dragging/resizing
        if self._show_coords and self._selected:
            w = self._selected
            coord_text = f"({w.x}, {w.y})  {w.width}\u00d7{w.height}"
            painter.setFont(self._coord_tooltip_font())
            fm2 = painter.fontMetrics()
            tw = fm2.horizontalAdvance(coord_text) + 8
            th = fm2.height() + 4

            tip_sx = _s(w.display_x)
            tip_sy = _s(w.display_y) - th - 4
            if tip_sy < 0:
                tip_sy = _s(w.display_y + w.height) + 4

            tip_rect = QRect(tip_sx, tip_sy, tw, th)
            painter.fillRect(tip_rect, palette["tooltip_bg"])
            painter.setPen(QPen(palette["tooltip_border"], 1))
            painter.drawRect(tip_rect)
            painter.setPen(palette["tooltip_text"])
            painter.drawText(tip_rect, Qt.AlignCenter, coord_text)


    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return

        pos = self._to_logical(event.pos())
        ctrl = bool(event.modifiers() & Qt.ControlModifier)
        shift = bool(event.modifiers() & Qt.ShiftModifier)
        self._clear_pending_drag_state()

        # Check for resize handle first
        handle = self._handle_at(pos)
        if handle != HANDLE_NONE and self._selected and not _parent_has_layout(self._selected):
            self._resizing = True
            self._resize_handle = handle
            self._resize_start_rect = QRect(
                self._selected.display_x, self._selected.display_y,
                self._selected.width, self._selected.height
            )
            self._resize_start_pos = pos
            self._show_coords = True
            self._reset_geometry_signal_state()
            self.drag_started.emit()
            self.update()
            return

        # Check for widget selection/drag
        w = self._widget_at(pos, allow_root=False)
        if w:
            if ctrl:
                # Ctrl+Click: toggle multi-select
                if w is self._selected:
                    if self._multi_selected:
                        self._selected = next(iter(self._multi_selected))
                        self._multi_selected.discard(self._selected)
                    else:
                        self._selected = None
                elif w in self._multi_selected:
                    self._multi_selected.discard(w)
                else:
                    if self._selected is not None:
                        self._multi_selected.add(self._selected)
                    self._selected = w
                self._refresh_paint_widget_cache()
                self._invalidate_passive_bounds_cache()
                self._emit_selection_changed()
                self.update()
                return

            # Normal click: single select + start drag
            selection_changed = w is not self._selected or bool(self._multi_selected)
            if selection_changed:
                self._selected = w
                self._multi_selected.clear()
                self._refresh_paint_widget_cache()
                self._invalidate_passive_bounds_cache()
            # Plain press should select immediately, but drag visuals wait for a real move threshold.
            self._pressed_widget = w
            self._press_pos = QPoint(pos)
            self._press_drag_offset = pos - QPoint(w.display_x, w.display_y)
            self._schedule_passive_bounds_cache_warmup()
            if selection_changed:
                self._emit_selection_changed()
                self.update()
            return

        # Click on empty space: start rubber-band selection
        self._rubber_mode = "toggle" if ctrl else "add" if shift else "replace"
        self._rubber_base_selection = self.selected_widgets()
        self._rubber_base_primary = self._selected
        self._rubber_band = True
        self._rubber_start = pos
        self._rubber_rect = QRect()
        if self._rubber_mode == "replace":
            self._selected = None
            self._multi_selected.clear()
            self._refresh_paint_widget_cache()
            self._invalidate_passive_bounds_cache()
            self._emit_selection_changed()
        self.update()

    def mouseMoveEvent(self, event):
        pos = self._to_logical(event.pos())

        # Emit mouse position for status bar (always, even when not dragging)
        if self._dragging or self._resizing:
            widget_under = self._selected
        elif self._rubber_band:
            widget_under = None
        else:
            widget_under = self._widget_at(pos, allow_root=False)
        self._emit_mouse_position_changed(pos.x(), pos.y(), widget_under)

        if self._rubber_band:
            old_rect = QRect(self._rubber_rect)
            self._rubber_rect = QRect(self._rubber_start, pos).normalized()
            self._update_regions(
                self._screen_rect_for_logical_rect(old_rect),
                self._screen_rect_for_logical_rect(self._rubber_rect),
            )
            return

        if self._resizing and self._selected:
            self._do_resize(pos)
            return

        if (
            not self._dragging
            and self._pressed_widget is not None
            and (event.buttons() & Qt.LeftButton)
        ):
            if (pos - self._press_pos).manhattanLength() >= self._drag_start_distance():
                self._begin_widget_drag(self._pressed_widget)
            else:
                return

        if self._dragging and self._selected:
            if self._reorder_mode:
                old_rect = QRect(self._insert_line_rect) if self._insert_line_rect is not None else QRect()
                idx, rect = self._compute_insert_index(self._selected, pos)
                if idx != self._insert_index or rect != self._insert_line_rect:
                    self._insert_index = idx
                    self._insert_line_rect = rect
                    self._update_regions(
                        self._screen_rect_for_logical_rect(old_rect),
                        self._screen_rect_for_logical_rect(rect),
                    )
            else:
                self._do_free_drag(pos)
            return

        # Hover detection and cursor update
        handle = self._handle_at(pos)
        if handle != HANDLE_NONE:
            self.setCursor(self._cursor_for_handle(handle))
        else:
            w = self._widget_at(pos, allow_root=False)
            if w is not None:
                # Show move cursor when hovering over a draggable widget
                if _parent_has_layout(w):
                    # In layout container: show grab cursor for reorder
                    self.setCursor(Qt.OpenHandCursor)
                else:
                    # Free positioning: show move cursor
                    self.setCursor(Qt.SizeAllCursor)
            else:
                self.setCursor(Qt.ArrowCursor)
            if w != self._hovered:
                old_hover = self._hovered
                self._set_hovered_widget(w)
                self._update_regions(
                    self._screen_rect_for_logical_bounds(
                        old_hover.display_x, old_hover.display_y, old_hover.width, old_hover.height
                    ) if old_hover is not None else QRect(),
                    self._screen_rect_for_logical_bounds(w.display_x, w.display_y, w.width, w.height) if w is not None else QRect(),
                )

    def _do_free_drag(self, pos):
        """Handle free drag movement with object/page snap and grid fallback."""
        old_display_x = self._selected.display_x
        old_display_y = self._selected.display_y
        old_guides = list(self._snap_guides)
        old_guide_rects = list(self._snap_guide_rects)
        new_pos = pos - self._drag_offset
        eff_grid = self._effective_grid_size()
        new_display_x, guide_x = self._snap_drag_axis(
            self._selected,
            new_pos.x(),
            self._selected.width,
            axis="x",
            eff_grid=eff_grid,
            min_pos=0,
            max_pos=self._base_width - self._selected.width,
        )
        new_display_y, guide_y = self._snap_drag_axis(
            self._selected,
            new_pos.y(),
            self._selected.height,
            axis="y",
            eff_grid=eff_grid,
            min_pos=0,
            max_pos=self._base_height - self._selected.height,
        )
        new_guides = []
        if guide_x is not None:
            new_guides.append(("v", guide_x))
        if guide_y is not None:
            new_guides.append(("h", guide_y))
        self._set_snap_guides(new_guides)
        new_guide_rects = list(self._snap_guide_rects)

        parent_display_x, parent_display_y = self._parent_display_origin(self._selected)
        new_x = new_display_x - parent_display_x
        new_y = new_display_y - parent_display_y

        if new_display_x != old_display_x or new_display_y != old_display_y:
            self._selected.x = new_x
            self._selected.y = new_y
            self._selected.display_x = new_display_x
            self._selected.display_y = new_display_y
            self._emit_geometry_signals(self._selected, new_x, new_y)
            geometry_rects = [
                self._screen_rect_for_logical_bounds(
                    old_display_x, old_display_y, self._selected.width, self._selected.height
                ),
                self._screen_rect_for_logical_bounds(
                    new_display_x, new_display_y, self._selected.width, self._selected.height
                ),
            ]
            if new_guides != old_guides:
                self._update_regions_for_geometry_and_guides(geometry_rects, old_guide_rects, new_guide_rects)
            else:
                self._update_regions(*geometry_rects)
        elif new_guides != old_guides:
            self._update_regions_for_guide_rects(old_guide_rects)
            self._update_regions_for_guide_rects(new_guide_rects)

    def _do_resize(self, pos):
        """Handle resize with object/page snap and grid fallback."""
        dx = pos.x() - self._resize_start_pos.x()
        dy = pos.y() - self._resize_start_pos.y()
        r = self._resize_start_rect
        h = self._resize_handle
        old_guides = list(self._snap_guides)
        old_guide_rects = list(self._snap_guide_rects)

        min_size = 10  # Minimum widget size
        eff_grid = self._effective_grid_size()
        left = r.x()
        right = r.x() + r.width()
        top = r.y()
        bottom = r.y() + r.height()
        guide_x = None
        guide_y = None

        if h in (HANDLE_LEFT, HANDLE_TOP_LEFT, HANDLE_BOTTOM_LEFT):
            left, guide_x = self._snap_resize_edge(
                self._selected,
                r.x() + dx,
                axis="x",
                eff_grid=eff_grid,
                min_pos=0,
                max_pos=min(right - min_size, self._base_width - min_size),
            )
        elif h in (HANDLE_RIGHT, HANDLE_TOP_RIGHT, HANDLE_BOTTOM_RIGHT):
            right, guide_x = self._snap_resize_edge(
                self._selected,
                r.x() + r.width() + dx,
                axis="x",
                eff_grid=eff_grid,
                min_pos=max(left + min_size, min_size),
                max_pos=self._base_width,
            )
        if h in (HANDLE_TOP, HANDLE_TOP_LEFT, HANDLE_TOP_RIGHT):
            top, guide_y = self._snap_resize_edge(
                self._selected,
                r.y() + dy,
                axis="y",
                eff_grid=eff_grid,
                min_pos=0,
                max_pos=min(bottom - min_size, self._base_height - min_size),
            )
        elif h in (HANDLE_BOTTOM, HANDLE_BOTTOM_LEFT, HANDLE_BOTTOM_RIGHT):
            bottom, guide_y = self._snap_resize_edge(
                self._selected,
                r.y() + r.height() + dy,
                axis="y",
                eff_grid=eff_grid,
                min_pos=max(top + min_size, min_size),
                max_pos=self._base_height,
            )

        new_display_x = left
        new_display_y = top
        new_w = max(min_size, right - left)
        new_h = max(min_size, bottom - top)

        new_guides = []
        if guide_x is not None:
            new_guides.append(("v", guide_x))
        if guide_y is not None:
            new_guides.append(("h", guide_y))
        self._set_snap_guides(new_guides)
        new_guide_rects = list(self._snap_guide_rects)

        parent_display_x, parent_display_y = self._parent_display_origin(self._selected)
        new_x = new_display_x - parent_display_x
        new_y = new_display_y - parent_display_y
        changed = False
        if new_display_x != self._selected.display_x or new_display_y != self._selected.display_y:
            self._selected.x = new_x
            self._selected.y = new_y
            self._selected.display_x = new_display_x
            self._selected.display_y = new_display_y
            changed = True
        if new_w != self._selected.width or new_h != self._selected.height:
            self._selected.width = new_w
            self._selected.height = new_h
            changed = True

        if changed:
            self._emit_geometry_signals(self._selected, new_x, new_y, new_w=new_w, new_h=new_h)
            geometry_rects = [
                self._screen_rect_for_logical_bounds(r.x(), r.y(), r.width(), r.height()),
                self._screen_rect_for_logical_bounds(new_display_x, new_display_y, new_w, new_h),
            ]
            if new_guides != old_guides:
                self._update_regions_for_geometry_and_guides(geometry_rects, old_guide_rects, new_guide_rects)
            else:
                self._update_regions(*geometry_rects)
        elif new_guides != old_guides:
            self._update_regions_for_guide_rects(old_guide_rects)
            self._update_regions_for_guide_rects(new_guide_rects)

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton:
            return

        if self._rubber_band:
            # Complete rubber-band selection
            self._rubber_band = False
            rect = self._rubber_rect
            matched = []
            for w in self._selection_candidates_for_rect(rect):
                if self._rect_intersects_widget(rect, w):
                    matched.append(w)
            widgets, primary = self._selection_after_rubber_band(matched)
            self.set_selection(widgets, primary=primary)
            self._emit_selection_changed()
            self._rubber_rect = QRect()
            self._rubber_mode = "replace"
            self._rubber_base_selection = []
            self._rubber_base_primary = None
            self._update_regions(self._screen_rect_for_logical_rect(rect))
            self._reset_pointer_signal_state()
            return

        if self._resizing:
            old_guides = list(self._snap_guides)
            old_guide_rects = list(self._snap_guide_rects)
            old_rect = QRect(
                self._selected.display_x if self._selected is not None else 0,
                self._selected.display_y if self._selected is not None else 0,
                self._selected.width if self._selected is not None else 0,
                self._selected.height if self._selected is not None else 0,
            )
            self._flush_pending_geometry_signals()
            self._resizing = False
            self._resize_handle = HANDLE_NONE
            self._resize_start_rect = None
            self._resize_start_pos = None
            self._show_coords = False
            self._set_snap_guides([])
            self.setCursor(Qt.ArrowCursor)
            self.drag_finished.emit()
            self._update_regions(self._screen_rect_for_logical_rect(old_rect))
            self._update_regions_for_guide_rects(old_guide_rects)
            self._reset_pointer_signal_state()
            return

        if self._dragging:
            old_insert_rect = QRect(self._insert_line_rect) if self._insert_line_rect is not None else QRect()
            old_guides = list(self._snap_guides)
            old_guide_rects = list(self._snap_guide_rects)
            old_rect = QRect(
                self._selected.display_x if self._selected is not None else 0,
                self._selected.display_y if self._selected is not None else 0,
                self._selected.width if self._selected is not None else 0,
                self._selected.height if self._selected is not None else 0,
            )
            if not self._reorder_mode:
                self._flush_pending_geometry_signals()
            if self._reorder_mode and self._selected:
                if self._insert_index >= 0 and self._selected.parent:
                    parent = self._selected.parent
                    old_index = parent.children.index(self._selected)
                    if old_index != self._insert_index and old_index != self._insert_index - 1:
                        parent.children.remove(self._selected)
                        new_idx = self._insert_index
                        if old_index < new_idx:
                            new_idx -= 1
                        parent.children.insert(new_idx, self._selected)
                        self.widget_reordered.emit(self._selected, new_idx)

            self._dragging = False
            self._reorder_mode = False
            self._insert_index = -1
            self._insert_line_rect = None
            self._show_coords = False
            self._set_snap_guides([])
            self.setCursor(Qt.ArrowCursor)
            self.drag_finished.emit()
            self._update_regions(
                self._screen_rect_for_logical_rect(old_insert_rect),
                self._screen_rect_for_logical_rect(old_rect),
            )
            self._update_regions_for_guide_rects(old_guide_rects)
            self._reset_pointer_signal_state()
            return

        if self._pressed_widget is not None:
            self._clear_pending_drag_state()

    def leaveEvent(self, event):
        old_hover = self._hovered
        self._set_hovered_widget(None)
        self.setCursor(Qt.ArrowCursor)
        self._reset_pointer_signal_state()
        self.mouse_position_changed.emit(-1, -1, None)  # Clear position display
        if old_hover is not None:
            self._update_regions(
                self._screen_rect_for_logical_bounds(old_hover.display_x, old_hover.display_y, old_hover.width, old_hover.height)
            )

    def contextMenuEvent(self, event):
        widget = self._widget_at(self._to_logical(event.pos()), allow_root=False)
        if widget is not None and widget not in self.selected_widgets():
            self.set_selection([widget], primary=widget)
            self._emit_selection_changed()
        self.context_menu_requested.emit(widget, event.globalPos())
        event.accept()

    def keyPressEvent(self, event):
        """Handle keyboard nudge for selected widget(s)."""
        targets = self._get_move_targets()
        if not targets:
            super().keyPressEvent(event)
            return

        key = event.key()
        if key not in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down):
            super().keyPressEvent(event)
            return

        step = 10 if event.modifiers() & Qt.ShiftModifier else 1
        dx, dy = 0, 0
        if key == Qt.Key_Left:
            dx = -step
        elif key == Qt.Key_Right:
            dx = step
        elif key == Qt.Key_Up:
            dy = -step
        elif key == Qt.Key_Down:
            dy = step

        for w in targets:
            if _parent_has_layout(w):
                continue
            new_x = max(0, min(w.x + dx, self._base_width - w.width))
            new_y = max(0, min(w.y + dy, self._base_height - w.height))
            if new_x != w.x or new_y != w.y:
                w.x = new_x
                w.y = new_y
                w.display_x = new_x
                w.display_y = new_y
                self.widget_moved.emit(w, new_x, new_y)
        self.update()
        event.accept()

    def _get_move_targets(self):
        """Get list of widgets to move (multi-select or single selected)."""
        widgets = [
            widget for widget in self.selected_widgets()
            if not self._is_hidden(widget) and not self._is_locked(widget)
        ]
        if widgets:
            return widgets
        if self._selected and not self._is_hidden(self._selected) and not self._is_locked(self._selected):
            return [self._selected]
        return []

    # ── Resource drag-drop onto canvas ─────────────────────────────

    def dragEnterEvent(self, event):
        from .resource_panel import EGUI_RESOURCE_MIME
        from .widget_browser import WidgetBrowserPanel
        if event.mimeData().hasFormat(EGUI_RESOURCE_MIME) or event.mimeData().hasFormat(WidgetBrowserPanel.WIDGET_DRAG_MIME):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        from .resource_panel import EGUI_RESOURCE_MIME
        from .widget_browser import WidgetBrowserPanel
        if event.mimeData().hasFormat(EGUI_RESOURCE_MIME) or event.mimeData().hasFormat(WidgetBrowserPanel.WIDGET_DRAG_MIME):
            # Highlight widget under cursor
            pos = self._to_logical(event.pos())
            w = self._widget_at(pos, allow_root=False)
            if self._set_hovered_widget(w):
                self.update()
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        from .resource_panel import EGUI_RESOURCE_MIME
        from .widget_browser import WidgetBrowserPanel
        if event.mimeData().hasFormat(WidgetBrowserPanel.WIDGET_DRAG_MIME):
            try:
                widget_type = bytes(event.mimeData().data(WidgetBrowserPanel.WIDGET_DRAG_MIME)).decode("utf-8").strip()
            except Exception:
                event.ignore()
                return
            if not widget_type:
                event.ignore()
                return
            pos = self._to_logical(event.pos())
            target = self._widget_at(pos, allow_root=False)
            self.widget_type_dropped.emit(widget_type, pos.x(), pos.y(), target)
            self._set_hovered_widget(None)
            self.update()
            event.acceptProposedAction()
            return
        if not event.mimeData().hasFormat(EGUI_RESOURCE_MIME):
            event.ignore()
            return
        try:
            raw = bytes(event.mimeData().data(EGUI_RESOURCE_MIME)).decode("utf-8")
            info = json.loads(raw)
        except Exception:
            event.ignore()
            return
        res_type = info.get("type", "")
        filename = info.get("filename", "")
        if not filename:
            event.ignore()
            return

        # Find target widget under drop position
        pos = self._to_logical(event.pos())
        target = self._widget_at(pos, allow_root=False)
        if target is None:
            event.ignore()
            return

        assigned = bool(assign_resource_to_widget(target, res_type, filename))

        if assigned:
            self._selected = target
            self._multi_selected.clear()
            self._refresh_paint_widget_cache()
            self._emit_selection_changed()
        else:
            event.ignore()
            return
        self.resource_dropped.emit(target, res_type, filename)
        self._set_hovered_widget(None)
        self.update()
        event.acceptProposedAction()


class PreviewPanel(QWidget):
    """Panel that embeds the exe window with overlay for widget manipulation.

    Supports multiple display modes:
    - vertical:   exe on top, overlay below (splitter adjustable)
    - horizontal: exe on left, overlay on right (splitter adjustable)
    - hidden:     overlay only, exe preview hidden
    """

    widget_moved = pyqtSignal(object, int, int)
    widget_resized = pyqtSignal(object, int, int)
    widget_selected = pyqtSignal(object)
    selection_changed = pyqtSignal(list, object)
    context_menu_requested = pyqtSignal(object, object)
    widget_reordered = pyqtSignal(object, int)
    resource_dropped = pyqtSignal(object, str, str)  # widget, res_type, filename
    widget_type_dropped = pyqtSignal(str, int, int, object)  # widget_type, x, y, target_widget
    drag_started = pyqtSignal()
    drag_finished = pyqtSignal()
    runtime_failed = pyqtSignal(str)

    def __init__(self, screen_width=240, screen_height=320, parent=None):
        super().__init__(parent)
        self.screen_width = screen_width
        self.screen_height = screen_height
        self._exe_hwnd = None
        self._embedded = False
        self._mode = MODE_HORIZONTAL
        self._splitter = None
        self._flipped = True  # wireframe first (left in horizontal, top in vertical)
        self._compiler = None  # set by start_rendering()
        self._render_timer = QTimer(self)
        self._render_timer.timeout.connect(self._refresh_frame)
        self._python_preview_active = False
        self._frame_failure_count = 0
        self._runtime_error_emitted = False
        self._last_pointer_status_ts = -1.0

        self._init_ui()

    def _init_ui(self):
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(2)

        self._header_frame = QFrame(self)
        self._header_frame.setObjectName("preview_header")
        self._header_frame.hide()
        header_layout = QVBoxLayout(self._header_frame)
        header_layout.setContentsMargins(2, 2, 2, 2)
        header_layout.setSpacing(2)

        self._eyebrow_label = QLabel("Preview")
        self._eyebrow_label.setObjectName("preview_eyebrow")
        self._eyebrow_label.hide()
        header_layout.addWidget(self._eyebrow_label)

        self._header_meta_label = QLabel(
            "Preview layout, fallback state, and pointer details remain available in the bottom status row."
        )
        self._header_meta_label.setObjectName("preview_header_meta")
        self._header_meta_label.setWordWrap(True)
        self._header_meta_label.hide()
        header_layout.addWidget(self._header_meta_label)

        self._metrics_frame = QFrame(self)
        self._metrics_frame.setObjectName("preview_metrics_strip")
        self._metrics_frame.hide()
        metrics_layout = QHBoxLayout(self._metrics_frame)
        metrics_layout.setContentsMargins(2, 2, 2, 2)
        metrics_layout.setSpacing(2)

        self._mode_chip = QLabel("Horizontal split")
        self._mode_chip.setObjectName("workspace_status_chip")
        self._mode_chip.hide()
        metrics_layout.addWidget(self._mode_chip)

        self._grid_chip = QLabel("Grid on")
        self._grid_chip.setObjectName("workspace_status_chip")
        self._grid_chip.hide()
        metrics_layout.addWidget(self._grid_chip)

        self._pointer_chip = QLabel("Pointer idle")
        self._pointer_chip.setObjectName("workspace_status_chip")
        self._pointer_chip.hide()
        metrics_layout.addWidget(self._pointer_chip)

        self._content = QFrame()
        self._content.setObjectName("preview_content")
        self._main_layout.addWidget(self._content, 1)

        self.preview_frame = QFrame()
        self.preview_frame.setObjectName("preview_stage_frame")
        self.preview_frame.setFixedSize(self.screen_width + 4, self.screen_height + 4)

        self._preview_label = QLabel(self.preview_frame)
        self._preview_label.setObjectName("preview_surface_label")
        self._preview_label.setGeometry(2, 2, self.screen_width, self.screen_height)
        self._preview_label.setMouseTracking(True)
        self._preview_label.installEventFilter(self)
        self._mouse_pressed = False

        self._preview_shell = QFrame()
        self._preview_shell.setObjectName("preview_stage_shell")
        preview_shell_layout = QVBoxLayout(self._preview_shell)
        preview_shell_layout.setContentsMargins(2, 2, 2, 2)
        preview_shell_layout.setSpacing(0)
        preview_shell_layout.addWidget(self.preview_frame, 0, Qt.AlignCenter)

        # Create the overlay (always exists) — zoomable
        self.overlay = WidgetOverlay()
        self.overlay.set_base_size(self.screen_width, self.screen_height)
        self.overlay.widget_moved.connect(self.widget_moved.emit)
        self.overlay.widget_resized.connect(self.widget_resized.emit)
        self.overlay.widget_selected.connect(self.widget_selected.emit)
        self.overlay.selection_changed.connect(self.selection_changed.emit)
        self.overlay.context_menu_requested.connect(self.context_menu_requested.emit)
        self.overlay.widget_reordered.connect(self.widget_reordered.emit)
        self.overlay.resource_dropped.connect(self.resource_dropped.emit)
        self.overlay.drag_started.connect(self.drag_started.emit)
        self.overlay.drag_finished.connect(self.drag_finished.emit)
        self.overlay.widget_type_dropped.connect(self.widget_type_dropped.emit)

        self._overlay_scroll = QScrollArea()
        self._overlay_scroll.setObjectName("preview_overlay_scroll")
        self._overlay_scroll.setWidgetResizable(False)
        self._overlay_scroll.setAlignment(Qt.AlignCenter)
        self._overlay_scroll.setWidget(self.overlay)

        self._overlay_shell = QFrame()
        self._overlay_shell.setObjectName("preview_overlay_shell")
        overlay_shell_layout = QVBoxLayout(self._overlay_shell)
        overlay_shell_layout.setContentsMargins(2, 2, 2, 2)
        overlay_shell_layout.setSpacing(0)
        overlay_shell_layout.addWidget(self._overlay_scroll, 1)

        self._status_bar = QWidget()
        self._status_bar.setObjectName("preview_status_shell")
        sbl = QHBoxLayout(self._status_bar)
        sbl.setContentsMargins(2, 2, 2, 2)
        sbl.setSpacing(2)

        self.status_label = QLabel("Preview - waiting for exe...")
        self.status_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.status_label.setObjectName("preview_status_value")
        sbl.addWidget(self.status_label)

        self._status_label = QLabel("")
        self._status_label.setObjectName("preview_status_value")
        sbl.addWidget(self._status_label)

        sbl.addStretch()
        status_button_size = max(int(app_theme_tokens().get("h_tab_min", 24)), 1)

        self._btn_zoom_out = QPushButton("-")
        self._btn_zoom_out.setObjectName("preview_status_button")
        self._btn_zoom_out.setFixedSize(status_button_size, status_button_size)
        self._btn_zoom_out.clicked.connect(self._on_zoom_out)

        self._zoom_label = QLabel("100% (4px)")
        self._zoom_label.setObjectName("preview_status_value")
        self._zoom_label.setAlignment(Qt.AlignCenter)

        self._btn_zoom_in = QPushButton("+")
        self._btn_zoom_in.setObjectName("preview_status_button")
        self._btn_zoom_in.setFixedSize(status_button_size, status_button_size)
        self._btn_zoom_in.clicked.connect(self._on_zoom_in)

        sbl.addWidget(self._btn_zoom_out)
        sbl.addWidget(self._zoom_label)
        sbl.addWidget(self._btn_zoom_in)
        self._sync_status_text_widths()

        self._main_layout.addWidget(self._status_bar)

        # Connect signals
        self.overlay.zoom_changed.connect(self._update_zoom_label)
        self.overlay.mouse_position_changed.connect(self._update_status_label)
        self.overlay.drag_finished.connect(self._update_accessibility_summary)

        # Apply initial layout mode
        self._apply_mode()
        self._update_zoom_label()
        self._update_accessibility_summary()

    def _clear_content_layout(self):
        """Remove all widgets from the content layout without deleting them."""
        # Detach splitter children first so they aren't deleted
        if hasattr(self, '_splitter') and self._splitter is not None:
            # Remove widgets from splitter by reparenting
            for i in range(self._splitter.count() - 1, -1, -1):
                w = self._splitter.widget(i)
                if w:
                    w.setParent(None)
            self._splitter.setParent(None)
            self._splitter = None

        old_layout = self._content.layout()
        if old_layout is not None:
            # Reparent children so they aren't deleted with the layout
            while old_layout.count():
                item = old_layout.takeAt(0)
                w = item.widget()
                if w:
                    w.setParent(None)
            # Delete the old layout by assigning it to a temporary widget
            QWidget().setLayout(old_layout)

    def _apply_mode(self):
        """Rebuild the content layout based on current mode."""
        self._clear_content_layout()

        if self._mode == MODE_VERTICAL:
            layout = QVBoxLayout(self._content)
            layout.setContentsMargins(2, 2, 2, 2)
            layout.setSpacing(2)
            self._splitter = QSplitter(Qt.Vertical)
            self._splitter.setObjectName("preview_splitter")
            self.overlay.set_solid_background(True)
            self._overlay_shell.setParent(None)
            self._preview_shell.setParent(None)
            if self._flipped:
                self._splitter.addWidget(self._overlay_shell)
                self._splitter.addWidget(self._preview_shell)
                self._splitter.setStretchFactor(0, 1)
                self._splitter.setStretchFactor(1, 0)
            else:
                self._splitter.addWidget(self._preview_shell)
                self._splitter.addWidget(self._overlay_shell)
                self._splitter.setStretchFactor(0, 0)
                self._splitter.setStretchFactor(1, 1)
            layout.addWidget(self._splitter, 1)
            self._preview_shell.show()
            self._overlay_shell.show()
            self._status_bar.show()

        elif self._mode == MODE_HORIZONTAL:
            layout = QVBoxLayout(self._content)
            layout.setContentsMargins(2, 2, 2, 2)
            layout.setSpacing(2)
            self._splitter = QSplitter(Qt.Horizontal)
            self._splitter.setObjectName("preview_splitter")
            self.overlay.set_solid_background(True)
            self._overlay_shell.setParent(None)
            self._preview_shell.setParent(None)
            if self._flipped:
                self._splitter.addWidget(self._overlay_shell)
                self._splitter.addWidget(self._preview_shell)
                self._splitter.setStretchFactor(0, 1)
                self._splitter.setStretchFactor(1, 0)
            else:
                self._splitter.addWidget(self._preview_shell)
                self._splitter.addWidget(self._overlay_shell)
                self._splitter.setStretchFactor(0, 0)
                self._splitter.setStretchFactor(1, 1)
            layout.addWidget(self._splitter, 1)
            self._preview_shell.show()
            self._overlay_shell.show()
            self._status_bar.show()

        elif self._mode == MODE_HIDDEN:
            layout = QVBoxLayout(self._content)
            layout.setContentsMargins(2, 2, 2, 2)
            layout.setSpacing(2)
            self.overlay.set_solid_background(True)
            self._overlay_shell.setParent(self._content)
            layout.addWidget(self._overlay_shell, 1)
            self._preview_shell.setParent(self._content)
            self._preview_shell.hide()
            self._overlay_shell.show()
            self._status_bar.show()
        self._update_accessibility_summary()

    def update_screen_size(self, width, height):
        """Update the logical screen size and resize all preview components."""
        self.screen_width = width
        self.screen_height = height
        self.preview_frame.setFixedSize(width + 4, height + 4)
        self._preview_label.setGeometry(2, 2, width, height)
        self.overlay.set_base_size(width, height)

    def set_overlay_mode(self, mode):
        """Switch overlay display mode."""
        if mode == self._mode:
            return
        self._mode = mode
        self._apply_mode()

    def flip_layout(self):
        """Swap the position of exe preview and overlay in splitter modes."""
        if self._mode == MODE_HIDDEN:
            return
        self._flipped = not self._flipped
        self._apply_mode()

    @property
    def overlay_mode(self):
        return self._mode

    # ── Zoom helpers (delegate to overlay) ─────────────────────────

    def _on_zoom_in(self):
        self.overlay.zoom_in()

    def _on_zoom_out(self):
        self.overlay.zoom_out()

    def _mode_summary(self):
        return {
            MODE_VERTICAL: "Vertical split",
            MODE_HORIZONTAL: "Horizontal split",
            MODE_HIDDEN: "Overlay only",
        }.get(self._mode, str(self._mode or "Preview"))

    def _zoom_button_metadata(self, direction, zoom_text):
        if direction == "out":
            enabled = self.overlay._zoom > (self.overlay._zoom_min + 1e-9)
            tooltip = f"Zoom out preview (Ctrl+-). Current zoom: {zoom_text}."
            if not enabled:
                tooltip += " Unavailable: already at minimum zoom."
            accessible_name = (
                f"Zoom out preview: current zoom {zoom_text}"
                if enabled
                else f"Zoom out preview unavailable: current zoom {zoom_text}"
            )
            return enabled, tooltip, accessible_name

        enabled = self.overlay._zoom < (self.overlay._zoom_max - 1e-9)
        tooltip = f"Zoom in preview (Ctrl+=). Current zoom: {zoom_text}."
        if not enabled:
            tooltip += " Unavailable: already at maximum zoom."
        accessible_name = (
            f"Zoom in preview: current zoom {zoom_text}"
            if enabled
            else f"Zoom in preview unavailable: current zoom {zoom_text}"
        )
        return enabled, tooltip, accessible_name

    def _update_accessibility_summary(self):
        status_text = str(self.status_label.text() or "Preview status unavailable").strip() or "Preview status unavailable"
        zoom_text = str(self._zoom_label.text() or "100%").strip() or "100%"
        pointer_text = str(self._status_label.text() or "").strip() or "Pointer idle"
        grid_text = "on" if self.show_grid() else "off"
        mode_text = self._mode_summary()
        pointer_chip_text = "Pointer idle" if pointer_text == "Pointer idle" else "Pointer active"
        self._mode_chip.setText(mode_text)
        self._grid_chip.setText(f"Grid {grid_text}")
        self._pointer_chip.setText(pointer_chip_text)
        summary = (
            f"Preview panel: {status_text}. Mode: {mode_text}. "
            f"Zoom: {zoom_text}. Grid: {grid_text}. Pointer: {pointer_text}."
        )
        controls_summary = f"Preview controls: Zoom {zoom_text}. Pointer {pointer_text}."
        _set_widget_metadata(self, tooltip=summary, accessible_name=summary)
        _set_widget_metadata(
            self._header_frame,
            tooltip=f"Preview header. {summary}",
            accessible_name=f"Preview header. {summary}",
        )
        _set_widget_metadata(
            self._eyebrow_label,
            tooltip="Preview workspace.",
            accessible_name="Preview workspace.",
        )
        _set_widget_metadata(
            self._header_meta_label,
            tooltip=self._header_meta_label.text(),
            accessible_name=self._header_meta_label.text(),
        )
        _set_widget_metadata(
            self._metrics_frame,
            tooltip=f"Preview metrics: {mode_text}. Grid {grid_text}. Pointer status: {pointer_text}.",
            accessible_name=f"Preview metrics: {mode_text}. Grid {grid_text}. Pointer status: {pointer_text}.",
        )
        _set_widget_metadata(
            self._mode_chip,
            tooltip=f"Preview mode: {mode_text}",
            accessible_name=f"Preview mode: {mode_text}",
        )
        _set_widget_metadata(
            self._grid_chip,
            tooltip=f"Preview grid: {grid_text}",
            accessible_name=f"Preview grid: {grid_text}",
        )
        _set_widget_metadata(
            self._pointer_chip,
            tooltip=f"Preview pointer summary: {pointer_text}",
            accessible_name=f"Preview pointer summary: {pointer_text}",
        )
        _set_widget_metadata(
            self.status_label,
            tooltip=status_text,
            accessible_name=f"Preview status: {status_text}",
        )
        _set_widget_metadata(
            self.preview_frame,
            tooltip=f"Rendered preview surface. {status_text}. Mode: {mode_text}.",
            accessible_name=f"Preview frame: {status_text}. Mode: {mode_text}.",
        )
        _set_widget_metadata(
            self._preview_label,
            tooltip=f"Rendered preview surface. {status_text}.",
            accessible_name=f"Rendered preview surface: {status_text}",
        )
        _set_widget_metadata(
            self.overlay,
            tooltip=f"Preview overlay. Mode: {mode_text}. Zoom: {zoom_text}. Grid: {grid_text}.",
            accessible_name=f"Preview overlay: {mode_text}. Zoom: {zoom_text}. Grid: {grid_text}.",
        )
        _set_widget_metadata(
            self._overlay_scroll,
            tooltip=f"Preview overlay canvas. Mode: {mode_text}. Zoom: {zoom_text}. Grid: {grid_text}.",
            accessible_name=f"Preview overlay canvas: {mode_text}. Zoom: {zoom_text}. Grid: {grid_text}.",
        )
        _set_widget_metadata(
            self._preview_shell,
            tooltip=f"Preview renderer shell. Mode: {mode_text}.",
            accessible_name=f"Preview renderer shell: {mode_text}.",
        )
        _set_widget_metadata(
            self._overlay_shell,
            tooltip=f"Preview overlay shell. Mode: {mode_text}. Zoom: {zoom_text}.",
            accessible_name=f"Preview overlay shell: {mode_text}. Zoom: {zoom_text}.",
        )
        _set_widget_metadata(
            self._status_bar,
            tooltip=controls_summary,
            accessible_name=controls_summary,
        )
        _set_widget_metadata(
            self._status_label,
            tooltip=f"Preview pointer status: {pointer_text}",
            accessible_name=f"Preview pointer status: {pointer_text}",
        )
        _set_widget_metadata(
            self._zoom_label,
            tooltip=f"Preview zoom: {zoom_text}",
            accessible_name=f"Preview zoom: {zoom_text}",
        )
        can_zoom_out, zoom_out_tooltip, zoom_out_accessible_name = self._zoom_button_metadata("out", zoom_text)
        can_zoom_in, zoom_in_tooltip, zoom_in_accessible_name = self._zoom_button_metadata("in", zoom_text)
        self._btn_zoom_out.setEnabled(can_zoom_out)
        self._btn_zoom_in.setEnabled(can_zoom_in)
        _set_widget_metadata(
            self._btn_zoom_out,
            tooltip=zoom_out_tooltip,
            accessible_name=zoom_out_accessible_name,
        )
        _set_widget_metadata(
            self._btn_zoom_in,
            tooltip=zoom_in_tooltip,
            accessible_name=zoom_in_accessible_name,
        )

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.StyleChange, QEvent.FontChange, QEvent.PaletteChange):
            self._sync_status_text_widths()
            self._sync_zoom_label_width()

    def _status_text_min_width(self, label, samples) -> int:
        tokens = app_theme_tokens()
        horizontal_padding = max(int(tokens.get("space_md", 12)), 0)
        try:
            metrics = QFontMetrics(label.font())
            widest = max(metrics.horizontalAdvance(sample) for sample in samples if str(sample or "").strip())
            return max(widest + horizontal_padding, 1)
        except Exception:
            return max(int(tokens.get("h_tab_min", 24)) * 4, 1)

    def _preview_status_label_target_width(self) -> int:
        return self._status_text_min_width(
            self.status_label,
            (
                str(self.status_label.text() or "").strip() or "Preview - waiting for exe...",
                "Preview - waiting for exe...",
                "Preview - Python fallback (fallback)",
                "Preview - headless rendering",
            ),
        )

    def _pointer_status_label_target_width(self) -> int:
        return self._status_text_min_width(
            self._status_label,
            (
                str(self._status_label.text() or "").strip() or "Pointer idle",
                "Pointer idle",
            ),
        )

    def _sync_status_text_widths(self):
        preview_status_width = self._preview_status_label_target_width()
        if self.status_label.minimumWidth() != preview_status_width:
            self.status_label.setMinimumWidth(preview_status_width)
        pointer_status_width = self._pointer_status_label_target_width()
        if self._status_label.minimumWidth() != pointer_status_width:
            self._status_label.setMinimumWidth(pointer_status_width)

    def _set_preview_status_text(self, text):
        if self.status_label.text() != text:
            self.status_label.setText(text)
        self._sync_status_text_widths()

    def _set_pointer_status_text(self, text):
        if self._status_label.text() != text:
            self._status_label.setText(text)
        self._sync_status_text_widths()

    def _zoom_label_target_width(self) -> int:
        zoom_min_pct = int(self.overlay._zoom_min * 100)
        zoom_max_pct = int(self.overlay._zoom_max * 100)
        grid = int(self.overlay._effective_grid_size())
        samples = (
            str(self._zoom_label.text() or "").strip() or "100% (8px)",
            f"{zoom_min_pct}% ({grid}px)",
            f"{zoom_max_pct}% ({grid}px)",
        )
        tokens = app_theme_tokens()
        horizontal_padding = max(int(tokens.get("space_md", 12)), 0)
        try:
            metrics = QFontMetrics(self._zoom_label.font())
            widest = max(metrics.horizontalAdvance(sample) for sample in samples)
            return max(widest + horizontal_padding, 1)
        except Exception:
            return max(int(tokens.get("h_tab_min", 24)) * 3, 1)

    def _sync_zoom_label_width(self):
        target_width = self._zoom_label_target_width()
        if self._zoom_label.minimumWidth() == target_width and self._zoom_label.maximumWidth() == target_width:
            return
        self._zoom_label.setFixedWidth(target_width)

    def _update_zoom_label(self, factor=None):
        del factor
        pct = int(self.overlay._zoom * 100)
        grid = self.overlay._effective_grid_size()
        self._zoom_label.setText(f"{pct}% ({grid}px)")
        self._sync_zoom_label_width()
        self._update_accessibility_summary()

    def _update_status_label(self, x, y, widget):
        """Update status bar with mouse position and widget info."""
        if self.overlay._dragging or self.overlay._resizing or self.overlay._rubber_band:
            now = time.monotonic()
            if (
                self._last_pointer_status_ts >= 0.0
                and (now - self._last_pointer_status_ts) < DRAG_POINTER_SIGNAL_INTERVAL_SEC
            ):
                return
            self._last_pointer_status_ts = now
        else:
            self._last_pointer_status_ts = -1.0

        if x < 0 or y < 0:
            self._set_pointer_status_text("Pointer idle")
            self._update_accessibility_summary()
            return

        if widget is not None:
            # Show widget info: position, size, and name
            text = f"({x}, {y})  |  {widget.widget_type}: {widget.name}  [{widget.x}, {widget.y}, {widget.width}\u00d7{widget.height}]"
        else:
            # Just show mouse position
            text = f"({x}, {y})"

        self._set_pointer_status_text(text)
        if not (self.overlay._dragging or self.overlay._resizing or self.overlay._rubber_band):
            self._update_accessibility_summary()

    def set_widgets(self, widgets):
        """Update the widget list for overlay display."""
        self.overlay.set_widgets(widgets)

    def set_selected(self, widget):
        """Set the selected widget for highlighting."""
        self.overlay.set_selected(widget)

    def set_selection(self, widgets, primary=None):
        """Set the selected widgets for highlighting."""
        self.overlay.set_selection(widgets, primary=primary)

    def selected_widgets(self):
        return self.overlay.selected_widgets()

    def set_show_grid(self, show):
        self.overlay.set_show_grid(show)
        self._update_zoom_label()

    def show_grid(self):
        return self.overlay.show_grid()

    def set_grid_size(self, size):
        self.overlay.set_grid_size(size)
        self._update_zoom_label()

    def grid_size(self):
        return self.overlay.grid_size()

    # ── Background mockup image (delegate to overlay) ─────────

    def set_background_image(self, pixmap):
        """Set background mockup image on overlay."""
        self.overlay.set_background_image(pixmap)

    def set_background_image_visible(self, visible):
        """Toggle background image visibility."""
        self.overlay.set_background_image_visible(visible)

    def set_background_image_opacity(self, opacity):
        """Set background image opacity (0.0 to 1.0)."""
        self.overlay.set_background_image_opacity(opacity)

    def clear_background_image(self):
        """Remove the background image."""
        self.overlay.clear_background_image()

    def embed_window(self, hwnd):
        """Legacy method - no longer needed with headless rendering."""
        return True

    def release_window(self):
        """Legacy method - no longer needed with headless rendering."""
        self._exe_hwnd = None
        self._embedded = False

    @property
    def is_embedded(self):
        return self._embedded

    # ── Headless frame rendering ────────────────────────────

    def start_rendering(self, compiler):
        """Start periodic frame refresh from headless bridge."""
        self.clear_python_preview_mode()
        self._compiler = compiler
        self._frame_failure_count = 0
        self._runtime_error_emitted = False
        self._render_timer.start(33)  # ~30fps
        self._embedded = True
        self._set_preview_status_text("Preview - headless rendering")
        self._update_accessibility_summary()

    def stop_rendering(self, *, update_accessibility=True):
        """Stop frame refresh."""
        self._render_timer.stop()
        self._compiler = None
        self._embedded = False
        self._frame_failure_count = 0
        self._runtime_error_emitted = False
        if update_accessibility:
            self._update_accessibility_summary()

    def _set_preview_pixmap(self, pixmap):
        self._preview_label.setPixmap(pixmap)

    def show_python_preview_image(self, image, reason=""):
        """Display an already-rendered PIL image as the Python fallback preview."""
        if image is None:
            self.show_python_preview(None, reason)
            return
        if getattr(image, "mode", "RGBA") != "RGBA":
            image = image.convert("RGBA")
        raw = image.tobytes("raw", "RGBA")
        qimage = QImage(raw, image.width, image.height, image.width * 4, QImage.Format_RGBA8888).copy()
        self.show_image_preview(qimage, reason=reason, label_prefix="Python fallback")

    def show_python_preview(self, page, reason=""):
        """Render the current page with the Python fallback renderer."""
        if page is None:
            self.stop_rendering(update_accessibility=False)
            self._python_preview_active = True
            self._preview_label.clear()
            self._set_preview_status_text("Preview - Python fallback")
            self._update_accessibility_summary()
            return

        image = render_page(page, self.screen_width, self.screen_height)
        self.show_python_preview_image(image, reason=reason)

    def show_image_preview(self, qimage, reason="", label_prefix="Renderer"):
        """Display a pre-rendered QImage in the preview area."""
        self.stop_rendering(update_accessibility=False)
        self._python_preview_active = True

        if qimage is None or qimage.isNull():
            self._preview_label.clear()
            self._set_preview_status_text(f"Preview - {label_prefix}")
            self._update_accessibility_summary()
            return

        self._set_preview_pixmap(QPixmap.fromImage(qimage))
        if reason:
            self._set_preview_status_text(f"Preview - {label_prefix} ({reason})")
        else:
            self._set_preview_status_text(f"Preview - {label_prefix}")
        self._update_accessibility_summary()

    def clear_python_preview_mode(self):
        """Leave Python fallback mode without clearing the current frame."""
        self._python_preview_active = False

    def is_python_preview_active(self):
        """Return True when the panel shows Python-rendered preview."""
        return self._python_preview_active

    def _refresh_frame(self):
        """Fetch frame from bridge and display as QPixmap."""
        if self._compiler is None:
            return
        frame_data = self._compiler.get_frame()
        if not frame_data:
            self._frame_failure_count += 1
            if self._frame_failure_count >= 3 and not self._runtime_error_emitted:
                self._render_timer.stop()
                self._embedded = False
                self._runtime_error_emitted = True
                reason = ""
                if self._compiler is not None:
                    reason = self._compiler.get_last_runtime_error()
                self.runtime_failed.emit(reason or "Headless preview stopped responding")
            return

        expected = self.screen_width * self.screen_height * 3
        if len(frame_data) != expected:
            self._frame_failure_count += 1
            if self._frame_failure_count >= 3 and not self._runtime_error_emitted:
                self._render_timer.stop()
                self._embedded = False
                self._runtime_error_emitted = True
                self.runtime_failed.emit(
                    f"Headless preview returned invalid frame size: {len(frame_data)} != {expected}"
                )
            return

        self._frame_failure_count = 0
        self._runtime_error_emitted = False
        img = QImage(
            frame_data,
            self.screen_width,
            self.screen_height,
            self.screen_width * 3,
            QImage.Format_RGB888,
        )
        self._set_preview_pixmap(QPixmap.fromImage(img))

    def eventFilter(self, obj, event):
        """Capture mouse events on _preview_label and forward to bridge."""
        if obj is self._preview_label and self._embedded:
            etype = event.type()
            if etype == QEvent.MouseButtonPress:
                pos = event.pos()
                self._mouse_pressed = True
                self.preview_mouse_press(pos.x(), pos.y())
                return True
            elif etype == QEvent.MouseButtonRelease:
                pos = event.pos()
                self._mouse_pressed = False
                self.preview_mouse_release(pos.x(), pos.y())
                return True
            elif etype == QEvent.MouseMove and self._mouse_pressed:
                pos = event.pos()
                self.preview_mouse_move(pos.x(), pos.y())
                return True
        return super().eventFilter(obj, event)

    def preview_mouse_press(self, x, y):
        """Forward mouse press to bridge as touch down."""
        from ..engine.designer_bridge import TOUCH_DOWN
        if self._compiler:
            self._compiler.inject_touch(TOUCH_DOWN, x, y)

    def preview_mouse_release(self, x, y):
        """Forward mouse release to bridge as touch up."""
        from ..engine.designer_bridge import TOUCH_UP
        if self._compiler:
            self._compiler.inject_touch(TOUCH_UP, x, y)

    def preview_mouse_move(self, x, y):
        """Forward mouse move to bridge as touch move."""
        from ..engine.designer_bridge import TOUCH_MOVE
        if self._compiler:
            self._compiler.inject_touch(TOUCH_MOVE, x, y)
