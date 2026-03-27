"""Lightweight icon and preview drawing helpers for the designer UI."""

from __future__ import annotations

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PyQt5.QtWidgets import QApplication


_WIDGET_ICON_KEYS = {
    "activity_ring": "display",
    "analog_clock": "time",
    "animated_image": "image",
    "autocomplete": "input",
    "button": "button",
    "button_matrix": "grid",
    "card": "card",
    "chart": "chart",
    "chart_bar": "chart",
    "chart_line": "chart",
    "chart_pie": "chart",
    "chart_scatter": "chart",
    "checkbox": "toggle",
    "chips": "tag",
    "circular_progress_bar": "progress",
    "combobox": "input",
    "compass": "navigation",
    "digital_clock": "time",
    "divider": "divider",
    "dynamic_label": "text",
    "gauge": "chart",
    "gridlayout": "layout",
    "group": "layout",
    "heart_rate": "chart",
    "image": "image",
    "image_button": "button",
    "keyboard": "input",
    "label": "text",
    "led": "status",
    "line": "divider",
    "linearlayout": "layout",
    "list": "list",
    "menu": "navigation",
    "mini_calendar": "calendar",
    "mp4": "media",
    "notification_badge": "status",
    "number_picker": "input",
    "page_indicator": "navigation",
    "pattern_lock": "security",
    "progress_bar": "progress",
    "radio_button": "toggle",
    "roller": "input",
    "scale": "chart",
    "scroll": "layout",
    "segmented_control": "navigation",
    "slider": "input",
    "spangroup": "layout",
    "spinner": "progress",
    "stepper": "input",
    "stopwatch": "time",
    "switch": "toggle",
    "tab_bar": "navigation",
    "table": "table",
    "textblock": "text",
    "textinput": "input",
    "tileview": "grid",
    "toggle_button": "toggle",
    "viewpage": "page",
    "viewpage_cache": "page",
    "window": "window",
}


def _theme_mode() -> str:
    app = QApplication.instance()
    mode = app.property("designer_theme_mode") if app is not None else None
    return mode if mode in ("dark", "light") else "dark"


def _palette_for_mode(mode: str) -> dict:
    if mode == "light":
        return {
            "ink": QColor("#1F2329"),
            "muted": QColor("#5C6675"),
            "accent": QColor("#1E6FD9"),
            "accent_soft": QColor("#D9E8FF"),
            "danger": QColor("#C14A3A"),
            "success": QColor("#227A49"),
            "surface": QColor("#FFFFFF"),
            "surface_alt": QColor("#EEF3FA"),
            "stroke": QColor("#CDD8E6"),
        }
    return {
        "ink": QColor("#E7EDF7"),
        "muted": QColor("#93A4BA"),
        "accent": QColor("#63A5FF"),
        "accent_soft": QColor("#133A6C"),
        "danger": QColor("#FF7B72"),
        "success": QColor("#4CC38A"),
        "surface": QColor("#17202B"),
        "surface_alt": QColor("#223041"),
        "stroke": QColor("#314355"),
    }


def widget_icon_key(type_name: str) -> str:
    return _WIDGET_ICON_KEYS.get(str(type_name or "").strip(), "widget")


def make_icon(icon_key: str, size: int = 20, mode: str | None = None) -> QIcon:
    pixmap = make_pixmap(icon_key, size=size, mode=mode)
    return QIcon(pixmap)


def make_pixmap(icon_key: str, size: int = 20, mode: str | None = None) -> QPixmap:
    mode = mode or _theme_mode()
    palette = _palette_for_mode(mode)
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    _paint_icon(painter, icon_key, QRectF(1, 1, size - 2, size - 2), palette)
    painter.end()
    return pixmap


def make_widget_preview(preview_kind: str, size=(180, 120), mode: str | None = None) -> QPixmap:
    mode = mode or _theme_mode()
    palette = _palette_for_mode(mode)
    width, height = size
    pixmap = QPixmap(width, height)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    rect = QRectF(0.5, 0.5, width - 1.0, height - 1.0)
    painter.setPen(QPen(palette["stroke"], 1))
    painter.setBrush(palette["surface"])
    painter.drawRoundedRect(rect, 12, 12)

    inner = rect.adjusted(12, 12, -12, -12)
    kind = (preview_kind or "widget").strip()
    if kind == "layout":
        painter.setPen(Qt.NoPen)
        painter.setBrush(palette["accent_soft"])
        painter.drawRoundedRect(QRectF(inner.left(), inner.top(), inner.width(), 26), 8, 8)
        painter.drawRoundedRect(QRectF(inner.left(), inner.top() + 34, inner.width() * 0.58, inner.height() - 34), 8, 8)
        painter.drawRoundedRect(QRectF(inner.left() + inner.width() * 0.64, inner.top() + 34, inner.width() * 0.36, inner.height() - 34), 8, 8)
    elif kind == "chart":
        pen = QPen(palette["accent"], 3)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        path = QPainterPath(QPointF(inner.left(), inner.bottom() - 8))
        path.lineTo(inner.left() + inner.width() * 0.24, inner.top() + inner.height() * 0.52)
        path.lineTo(inner.left() + inner.width() * 0.48, inner.top() + inner.height() * 0.72)
        path.lineTo(inner.left() + inner.width() * 0.68, inner.top() + inner.height() * 0.28)
        path.lineTo(inner.right(), inner.top() + inner.height() * 0.44)
        painter.drawPath(path)
    elif kind == "navigation":
        painter.setPen(QPen(palette["stroke"], 1.4))
        painter.setBrush(palette["surface_alt"])
        painter.drawRoundedRect(QRectF(inner.left(), inner.top(), inner.width(), 28), 8, 8)
        for index in range(3):
            x = inner.left() + 14 + index * 42
            painter.drawRoundedRect(QRectF(x, inner.top() + 8, 28, 12), 6, 6)
        painter.setPen(Qt.NoPen)
        painter.setBrush(palette["accent_soft"])
        painter.drawRoundedRect(QRectF(inner.left(), inner.top() + 40, inner.width(), inner.height() - 40), 10, 10)
    elif kind == "input":
        painter.setPen(QPen(palette["stroke"], 1.5))
        painter.setBrush(palette["surface_alt"])
        painter.drawRoundedRect(QRectF(inner.left(), inner.center().y() - 14, inner.width(), 28), 9, 9)
        pen = QPen(palette["accent"], 4)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawLine(QPointF(inner.left() + 18, inner.center().y()), QPointF(inner.left() + inner.width() * 0.58, inner.center().y()))
        painter.setBrush(palette["accent"])
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(inner.left() + inner.width() * 0.72, inner.center().y()), 8, 8)
    elif kind == "media":
        painter.setPen(Qt.NoPen)
        painter.setBrush(palette["surface_alt"])
        painter.drawRoundedRect(QRectF(inner.left(), inner.top(), inner.width(), inner.height()), 10, 10)
        triangle = QPainterPath()
        triangle.moveTo(inner.left() + inner.width() * 0.42, inner.top() + inner.height() * 0.28)
        triangle.lineTo(inner.left() + inner.width() * 0.42, inner.top() + inner.height() * 0.72)
        triangle.lineTo(inner.left() + inner.width() * 0.72, inner.center().y())
        triangle.closeSubpath()
        painter.setBrush(palette["accent"])
        painter.drawPath(triangle)
    else:
        painter.setPen(QPen(palette["stroke"], 1.4))
        painter.setBrush(palette["surface_alt"])
        painter.drawRoundedRect(QRectF(inner.left(), inner.top() + 12, inner.width(), inner.height() - 24), 10, 10)
        pen = QPen(palette["muted"], 2)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawLine(QPointF(inner.left() + 16, inner.top() + 34), QPointF(inner.right() - 16, inner.top() + 34))
        painter.drawLine(QPointF(inner.left() + 16, inner.top() + 54), QPointF(inner.right() - 36, inner.top() + 54))
        painter.drawLine(QPointF(inner.left() + 16, inner.top() + 74), QPointF(inner.right() - 22, inner.top() + 74))

    painter.end()
    return pixmap


def _paint_icon(painter: QPainter, icon_key: str, rect: QRectF, palette: dict) -> None:
    pen = QPen(palette["ink"], 1.8)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    key = (icon_key or "widget").strip()
    if key == "project":
        painter.setBrush(palette["surface_alt"])
        painter.drawRoundedRect(rect.adjusted(2, 5, -2, -1), 4, 4)
        painter.drawRoundedRect(QRectF(rect.left() + 3, rect.top() + 3, rect.width() * 0.44, 6), 3, 3)
    elif key == "structure":
        x = rect.left() + rect.width() * 0.28
        right = rect.left() + rect.width() * 0.72
        mid = rect.center().x()
        top = rect.top() + 4
        bottom = rect.bottom() - 4
        painter.drawLine(QPointF(mid, top + 2), QPointF(mid, bottom - 2))
        painter.drawLine(QPointF(mid, rect.center().y()), QPointF(right, rect.center().y()))
        painter.drawLine(QPointF(mid, rect.top() + rect.height() * 0.28), QPointF(x, rect.top() + rect.height() * 0.28))
        painter.drawEllipse(QRectF(mid - 3, top, 6, 6))
        painter.drawEllipse(QRectF(x - 3, rect.top() + rect.height() * 0.28 - 3, 6, 6))
        painter.drawEllipse(QRectF(right - 3, rect.center().y() - 3, 6, 6))
        painter.drawEllipse(QRectF(mid - 3, bottom - 6, 6, 6))
    elif key == "widgets":
        painter.setBrush(palette["accent_soft"])
        size = rect.width() / 2.7
        gap = rect.width() / 8
        start_x = rect.left() + 3
        start_y = rect.top() + 3
        for row in range(2):
            for col in range(2):
                painter.drawRoundedRect(
                    QRectF(start_x + col * (size + gap), start_y + row * (size + gap), size, size), 2.5, 2.5
                )
    elif key == "assets":
        painter.drawRoundedRect(rect.adjusted(2.5, 3, -2.5, -2.5), 4, 4)
        painter.drawEllipse(QRectF(rect.left() + 5, rect.top() + 6, 4.5, 4.5))
        painter.drawLine(QPointF(rect.left() + 5, rect.bottom() - 5), QPointF(rect.center().x(), rect.top() + 10))
        painter.drawLine(QPointF(rect.center().x(), rect.top() + 10), QPointF(rect.right() - 5, rect.bottom() - 6))
    elif key == "properties":
        for y in (rect.top() + 5, rect.center().y(), rect.bottom() - 5):
            painter.drawLine(QPointF(rect.left() + 4, y), QPointF(rect.right() - 4, y))
        painter.setBrush(palette["accent"])
        painter.drawEllipse(QRectF(rect.left() + 7, rect.top() + 2, 6, 6))
        painter.drawEllipse(QRectF(rect.center().x() - 3, rect.center().y() - 3, 6, 6))
        painter.drawEllipse(QRectF(rect.right() - 13, rect.bottom() - 8, 6, 6))
    elif key == "animation":
        path = QPainterPath(QPointF(rect.left() + 3, rect.bottom() - 4))
        path.cubicTo(
            QPointF(rect.left() + 6, rect.top() + 8),
            QPointF(rect.center().x(), rect.top() + 4),
            QPointF(rect.right() - 4, rect.center().y()),
        )
        painter.drawPath(path)
        painter.setBrush(palette["accent"])
        painter.drawEllipse(QRectF(rect.right() - 7, rect.center().y() - 3, 6, 6))
    elif key == "page":
        painter.setBrush(palette["surface_alt"])
        painter.drawRoundedRect(rect.adjusted(4, 2, -4, -2), 3, 3)
        painter.drawLine(QPointF(rect.left() + 7, rect.top() + 8), QPointF(rect.right() - 7, rect.top() + 8))
        painter.drawLine(QPointF(rect.left() + 7, rect.top() + 12), QPointF(rect.right() - 11, rect.top() + 12))
    elif key == "diagnostics":
        painter.setBrush(palette["accent_soft"])
        path = QPainterPath()
        path.moveTo(rect.center().x(), rect.top() + 3)
        path.lineTo(rect.right() - 3, rect.bottom() - 3)
        path.lineTo(rect.left() + 3, rect.bottom() - 3)
        path.closeSubpath()
        painter.drawPath(path)
        painter.setPen(QPen(palette["accent"], 2.1, cap=Qt.RoundCap))
        painter.drawLine(QPointF(rect.center().x(), rect.top() + 7), QPointF(rect.center().x(), rect.center().y() + 1))
        painter.drawPoint(QPointF(rect.center().x(), rect.bottom() - 7))
    elif key == "history":
        painter.drawEllipse(rect.adjusted(3, 3, -3, -3))
        painter.drawLine(QPointF(rect.center().x(), rect.center().y()), QPointF(rect.center().x(), rect.top() + 6))
        painter.drawLine(QPointF(rect.center().x(), rect.center().y()), QPointF(rect.right() - 5, rect.center().y()))
    elif key == "debug":
        painter.drawRoundedRect(rect.adjusted(2.5, 4, -2.5, -3), 4, 4)
        painter.drawLine(QPointF(rect.left() + 5, rect.bottom() - 6), QPointF(rect.right() - 5, rect.bottom() - 6))
        painter.drawLine(QPointF(rect.left() + 7, rect.top() + 8), QPointF(rect.center().x() - 1, rect.center().y()))
        painter.drawLine(QPointF(rect.center().x() - 1, rect.center().y()), QPointF(rect.left() + 7, rect.bottom() - 10))
        painter.drawLine(QPointF(rect.right() - 7, rect.top() + 8), QPointF(rect.center().x() + 1, rect.center().y()))
    elif key == "save":
        painter.setBrush(palette["surface_alt"])
        painter.drawRoundedRect(rect.adjusted(3, 2, -3, -2), 3, 3)
        painter.drawRect(QRectF(rect.left() + 6, rect.top() + 4, rect.width() - 12, 5))
        painter.drawRect(QRectF(rect.left() + 6, rect.center().y() - 1, rect.width() - 12, rect.height() / 3))
    elif key == "compile":
        painter.setBrush(palette["accent_soft"])
        path = QPainterPath()
        path.moveTo(rect.left() + 6, rect.top() + 4)
        path.lineTo(rect.right() - 5, rect.center().y())
        path.lineTo(rect.left() + 6, rect.bottom() - 4)
        path.closeSubpath()
        painter.drawPath(path)
    elif key == "stop":
        painter.setBrush(palette["danger"])
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(rect.adjusted(5, 5, -5, -5), 3, 3)
    elif key == "undo":
        painter.drawArc(rect.adjusted(4, 4, -5, -4), 40 * 16, 240 * 16)
        painter.drawLine(QPointF(rect.left() + 4, rect.top() + 9), QPointF(rect.left() + 8, rect.top() + 5))
        painter.drawLine(QPointF(rect.left() + 4, rect.top() + 9), QPointF(rect.left() + 10, rect.top() + 10))
    elif key == "redo":
        painter.drawArc(rect.adjusted(5, 4, -4, -4), -100 * 16, -240 * 16)
        painter.drawLine(QPointF(rect.right() - 4, rect.top() + 9), QPointF(rect.right() - 8, rect.top() + 5))
        painter.drawLine(QPointF(rect.right() - 4, rect.top() + 9), QPointF(rect.right() - 10, rect.top() + 10))
    elif key == "button":
        painter.setBrush(palette["surface_alt"])
        painter.drawRoundedRect(rect.adjusted(3, 5, -3, -5), 6, 6)
        painter.drawLine(QPointF(rect.left() + 7, rect.center().y()), QPointF(rect.right() - 7, rect.center().y()))
    elif key == "layout":
        painter.setBrush(palette["surface_alt"])
        painter.drawRoundedRect(rect.adjusted(2, 3, -2, -3), 3, 3)
        painter.drawLine(QPointF(rect.center().x(), rect.top() + 4), QPointF(rect.center().x(), rect.bottom() - 4))
        painter.drawLine(QPointF(rect.left() + 4, rect.center().y()), QPointF(rect.right() - 4, rect.center().y()))
    elif key == "input":
        painter.drawRoundedRect(rect.adjusted(3, 6, -3, -6), 5, 5)
        painter.drawLine(QPointF(rect.left() + 7, rect.center().y()), QPointF(rect.right() - 9, rect.center().y()))
    elif key == "toggle":
        painter.drawRoundedRect(QRectF(rect.left() + 3, rect.center().y() - 4, rect.width() - 6, 8), 4, 4)
        painter.setBrush(palette["accent"])
        painter.drawEllipse(QRectF(rect.left() + 4, rect.center().y() - 5, 10, 10))
    elif key == "navigation":
        painter.drawLine(QPointF(rect.center().x(), rect.top() + 3), QPointF(rect.center().x(), rect.bottom() - 3))
        painter.drawLine(QPointF(rect.left() + 4, rect.center().y()), QPointF(rect.right() - 4, rect.center().y()))
        painter.drawLine(QPointF(rect.center().x(), rect.top() + 3), QPointF(rect.right() - 5, rect.center().y()))
    elif key == "chart":
        painter.drawLine(QPointF(rect.left() + 4, rect.bottom() - 4), QPointF(rect.left() + 8, rect.top() + 9))
        painter.drawLine(QPointF(rect.left() + 8, rect.top() + 9), QPointF(rect.center().x(), rect.bottom() - 8))
        painter.drawLine(QPointF(rect.center().x(), rect.bottom() - 8), QPointF(rect.right() - 5, rect.top() + 5))
    elif key == "media":
        path = QPainterPath()
        path.moveTo(rect.left() + 6, rect.top() + 4)
        path.lineTo(rect.right() - 5, rect.center().y())
        path.lineTo(rect.left() + 6, rect.bottom() - 4)
        path.closeSubpath()
        painter.setBrush(palette["accent_soft"])
        painter.drawPath(path)
    elif key == "image":
        painter.drawRoundedRect(rect.adjusted(3, 4, -3, -4), 3, 3)
        painter.drawEllipse(QRectF(rect.left() + 6, rect.top() + 6, 4, 4))
        painter.drawLine(QPointF(rect.left() + 6, rect.bottom() - 7), QPointF(rect.center().x(), rect.top() + 11))
        painter.drawLine(QPointF(rect.center().x(), rect.top() + 11), QPointF(rect.right() - 5, rect.bottom() - 7))
    elif key == "text":
        painter.drawLine(QPointF(rect.left() + 5, rect.top() + 6), QPointF(rect.right() - 5, rect.top() + 6))
        painter.drawLine(QPointF(rect.left() + 8, rect.center().y()), QPointF(rect.right() - 8, rect.center().y()))
        painter.drawLine(QPointF(rect.left() + 6, rect.bottom() - 6), QPointF(rect.right() - 10, rect.bottom() - 6))
    elif key == "list":
        for row in range(3):
            y = rect.top() + 5 + row * 5
            painter.drawEllipse(QRectF(rect.left() + 4, y - 1.5, 3, 3))
            painter.drawLine(QPointF(rect.left() + 10, y), QPointF(rect.right() - 4, y))
    elif key == "grid":
        painter.setBrush(palette["surface_alt"])
        size = rect.width() / 3.5
        gap = 2.5
        for row in range(2):
            for col in range(2):
                painter.drawRoundedRect(
                    QRectF(rect.left() + 3 + col * (size + gap), rect.top() + 3 + row * (size + gap), size, size), 1.8, 1.8
                )
    elif key == "status":
        painter.setBrush(palette["accent_soft"])
        painter.drawRoundedRect(rect.adjusted(3, 5, -3, -5), 5, 5)
        painter.setBrush(palette["success"])
        painter.drawEllipse(QRectF(rect.center().x() - 4, rect.center().y() - 4, 8, 8))
    elif key == "progress":
        painter.drawRoundedRect(QRectF(rect.left() + 3, rect.center().y() - 3, rect.width() - 6, 6), 3, 3)
        painter.setBrush(palette["accent"])
        painter.drawRoundedRect(QRectF(rect.left() + 3, rect.center().y() - 3, rect.width() * 0.58, 6), 3, 3)
    elif key == "divider":
        painter.drawLine(QPointF(rect.left() + 4, rect.center().y()), QPointF(rect.right() - 4, rect.center().y()))
    elif key == "calendar":
        painter.drawRoundedRect(rect.adjusted(3, 3, -3, -3), 3, 3)
        painter.drawLine(QPointF(rect.left() + 5, rect.top() + 8), QPointF(rect.right() - 5, rect.top() + 8))
        for row in range(2):
            for col in range(3):
                painter.drawPoint(QPointF(rect.left() + 7 + col * 4.2, rect.top() + 12 + row * 4.2))
    elif key == "security":
        painter.drawEllipse(QRectF(rect.left() + 5, rect.top() + 5, rect.width() - 10, rect.height() - 10))
        painter.drawLine(QPointF(rect.left() + 6, rect.top() + 6), QPointF(rect.right() - 6, rect.bottom() - 6))
    elif key == "window":
        painter.drawRoundedRect(rect.adjusted(2.5, 3, -2.5, -3), 3, 3)
        painter.drawLine(QPointF(rect.left() + 3, rect.top() + 7), QPointF(rect.right() - 3, rect.top() + 7))
        for index in range(3):
            painter.drawPoint(QPointF(rect.left() + 6 + index * 3, rect.top() + 5))
    elif key == "time":
        painter.drawEllipse(rect.adjusted(3, 3, -3, -3))
        painter.drawLine(QPointF(rect.center().x(), rect.center().y()), QPointF(rect.center().x(), rect.top() + 6))
        painter.drawLine(QPointF(rect.center().x(), rect.center().y()), QPointF(rect.right() - 6, rect.center().y() + 2))
    elif key == "table":
        painter.drawRoundedRect(rect.adjusted(3, 4, -3, -4), 2, 2)
        painter.drawLine(QPointF(rect.left() + 3, rect.top() + 9), QPointF(rect.right() - 3, rect.top() + 9))
        painter.drawLine(QPointF(rect.center().x(), rect.top() + 4), QPointF(rect.center().x(), rect.bottom() - 4))
        painter.drawLine(QPointF(rect.left() + 3, rect.center().y()), QPointF(rect.right() - 3, rect.center().y()))
    elif key == "tag":
        path = QPainterPath()
        path.moveTo(rect.left() + 5, rect.top() + 6)
        path.lineTo(rect.center().x(), rect.top() + 6)
        path.lineTo(rect.right() - 4, rect.center().y())
        path.lineTo(rect.center().x(), rect.bottom() - 6)
        path.lineTo(rect.left() + 5, rect.bottom() - 6)
        path.closeSubpath()
        painter.setBrush(palette["surface_alt"])
        painter.drawPath(path)
        painter.drawEllipse(QRectF(rect.left() + 8, rect.center().y() - 1.5, 3, 3))
    elif key == "card":
        painter.setBrush(palette["surface_alt"])
        painter.drawRoundedRect(rect.adjusted(2.5, 3, -2.5, -3), 5, 5)
        painter.drawLine(QPointF(rect.left() + 6, rect.top() + 9), QPointF(rect.right() - 6, rect.top() + 9))
        painter.drawLine(QPointF(rect.left() + 6, rect.center().y()), QPointF(rect.right() - 10, rect.center().y()))
    else:
        painter.drawRoundedRect(rect.adjusted(3, 3, -3, -3), 5, 5)
        painter.setFont(QFont("Segoe UI", max(int(rect.height() * 0.44), 8), QFont.DemiBold))
        painter.drawText(rect, Qt.AlignCenter, "W")
