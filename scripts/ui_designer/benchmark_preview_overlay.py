import argparse
import json
import os
from pathlib import Path
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from PyQt5.QtCore import QPoint, QRect
from PyQt5.QtGui import QColor, QPixmap
from PyQt5.QtWidgets import QApplication, QScrollArea

from ui_designer.model.widget_model import WidgetModel
from ui_designer.ui.preview_panel import HANDLE_RIGHT, WidgetOverlay


def _parse_args():
    parser = argparse.ArgumentParser(description="Benchmark UI Designer preview overlay operations.")
    parser.add_argument("--rows", type=int, default=80, help="Number of widget rows in the synthetic page.")
    parser.add_argument("--cols", type=int, default=80, help="Number of widget columns in the synthetic page.")
    parser.add_argument("--canvas-width", type=int, default=4000, help="Logical canvas width.")
    parser.add_argument("--canvas-height", type=int, default=4000, help="Logical canvas height.")
    parser.add_argument("--viewport-width", type=int, default=800, help="Visible viewport width.")
    parser.add_argument("--viewport-height", type=int, default=600, help="Visible viewport height.")
    parser.add_argument("--cell-step", type=int, default=38, help="Spacing between synthetic widgets.")
    parser.add_argument("--widget-width", type=int, default=30, help="Synthetic widget width.")
    parser.add_argument("--widget-height", type=int, default=24, help="Synthetic widget height.")
    parser.add_argument("--widget-at-iterations", type=int, default=5000, help="Hit-test loop count.")
    parser.add_argument("--selection-iterations", type=int, default=500, help="Selection candidate loop count.")
    parser.add_argument("--drag-iterations", type=int, default=2000, help="Drag loop count.")
    parser.add_argument("--resize-iterations", type=int, default=2000, help="Resize loop count.")
    parser.add_argument("--with-background", action="store_true", help="Include a full-size background mockup pixmap.")
    return parser.parse_args()


def _build_widgets(args):
    root = WidgetModel("group", name="root", x=0, y=0, width=args.canvas_width, height=args.canvas_height)
    widgets = []
    for row in range(args.rows):
        for col in range(args.cols):
            widget = WidgetModel(
                "label",
                name=f"w_{row}_{col}",
                x=col * args.cell_step,
                y=row * args.cell_step,
                width=args.widget_width,
                height=args.widget_height,
            )
            root.add_child(widget)
            widgets.append(widget)
    return root, widgets


def _measure_ms(fn):
    start = time.perf_counter()
    result = fn()
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    return result, elapsed_ms


def main():
    args = _parse_args()
    app = QApplication.instance() or QApplication([])

    scroll = QScrollArea()
    scroll.resize(args.viewport_width, args.viewport_height)
    overlay = WidgetOverlay()
    overlay.set_base_size(args.canvas_width, args.canvas_height)
    overlay.set_solid_background(True)
    scroll.setWidget(overlay)
    scroll.show()

    if args.with_background:
        bg = QPixmap(args.canvas_width, args.canvas_height)
        bg.fill(QColor(24, 28, 40))
        overlay.set_background_image(bg)

    root, widgets = _build_widgets(args)

    _, set_widgets_ms = _measure_ms(lambda: overlay.set_widgets(root.get_all_widgets_flat()))
    overlay.set_selection([widgets[0]], primary=widgets[0])
    overlay._dragging = True
    app.processEvents()

    _, first_cache_ms = _measure_ms(overlay._ensure_passive_bounds_cache)
    _, second_cache_ms = _measure_ms(overlay._ensure_passive_bounds_cache)

    widget_at_points = [
        QPoint((i * 17) % max(args.canvas_width - 20, 1) + 5, (i * 29) % max(args.canvas_height - 20, 1) + 5)
        for i in range(args.widget_at_iterations)
    ]
    _, widget_at_ms = _measure_ms(lambda: [overlay._widget_at(point, allow_root=False) for point in widget_at_points])

    selection_rects = [
        QRect((i * 13) % max(args.canvas_width - 160, 1), (i * 19) % max(args.canvas_height - 120, 1), 120, 90)
        for i in range(args.selection_iterations)
    ]
    _, selection_candidates_ms = _measure_ms(
        lambda: [overlay._selection_candidates_for_rect(rect) for rect in selection_rects]
    )

    drag_positions = [
        QPoint((i * 17) % max(args.canvas_width - 200, 1) + 5, (i * 29) % max(args.canvas_height - 200, 1) + 5)
        for i in range(args.drag_iterations)
    ]
    overlay._drag_offset = QPoint()
    _, drag_ms = _measure_ms(lambda: [overlay._do_free_drag(point) for point in drag_positions])

    overlay._dragging = False
    overlay._resizing = True
    overlay._resize_handle = HANDLE_RIGHT
    overlay._resize_start_rect = QRect(widgets[0].display_x, widgets[0].display_y, widgets[0].width, widgets[0].height)
    overlay._resize_start_pos = QPoint()
    resize_positions = [QPoint((i * 7) % 200, 0) for i in range(args.resize_iterations)]
    _, resize_ms = _measure_ms(lambda: [overlay._do_resize(point) for point in resize_positions])

    result = {
        "widget_count": len(root.get_all_widgets_flat()),
        "viewport_rect": [
            overlay._passive_bounds_cache_rect.x(),
            overlay._passive_bounds_cache_rect.y(),
            overlay._passive_bounds_cache_rect.width(),
            overlay._passive_bounds_cache_rect.height(),
        ],
        "set_widgets_ms": round(set_widgets_ms, 2),
        "first_passive_cache_ms": round(first_cache_ms, 2),
        "second_passive_cache_ms": round(second_cache_ms, 4),
        "widget_at_total_ms": round(widget_at_ms, 2),
        "selection_candidates_total_ms": round(selection_candidates_ms, 2),
        "drag_total_ms": round(drag_ms, 2),
        "resize_total_ms": round(resize_ms, 2),
        "with_background": bool(args.with_background),
    }
    print(json.dumps(result, indent=2))

    scroll.close()
    app.processEvents()
    return 0


if __name__ == "__main__":
    sys.exit(main())
