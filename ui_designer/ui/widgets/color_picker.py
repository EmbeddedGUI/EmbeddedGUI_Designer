"""Color picker widget supporting EGUI named colors and EGUI_COLOR_HEX format."""

import re

from PyQt5.QtWidgets import QWidget, QHBoxLayout, QColorDialog
from PyQt5.QtCore import pyqtSignal, Qt, QSize
from PyQt5.QtGui import QColor, QPainter, QBrush, QPalette

from ...model.widget_model import COLORS, COLOR_RGB
from ..theme import app_theme_tokens


# Regex to parse EGUI_COLOR_HEX(0xRRGGBB)
_HEX_RE = re.compile(r'^EGUI_COLOR_HEX\(\s*0x([0-9A-Fa-f]{6})\s*\)$')


def _set_widget_metadata(widget, *, tooltip=None, accessible_name=None):
    if tooltip is not None:
        hint = str(tooltip or "")
        if str(widget.property("_color_picker_hint_snapshot") or "") != hint:
            widget.setToolTip(hint)
            widget.setStatusTip(hint)
            widget.setProperty("_color_picker_hint_snapshot", hint)
    if accessible_name is not None:
        name = str(accessible_name or "")
        if str(widget.property("_color_picker_accessible_snapshot") or "") != name:
            widget.setAccessibleName(name)
            widget.setProperty("_color_picker_accessible_snapshot", name)


def egui_color_to_qcolor(value):
    """Convert an EGUI color string to a QColor.

    Supports named colors (EGUI_COLOR_RED) and hex (EGUI_COLOR_HEX(0xFF0000)).
    Returns None if the value cannot be parsed.
    """
    if not value:
        return None
    # Named color
    rgb = COLOR_RGB.get(value)
    if rgb:
        return QColor(*rgb)
    # Hex color
    m = _HEX_RE.match(value)
    if m:
        hex_str = m.group(1)
        return QColor(int(hex_str[:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16))
    return None


def qcolor_to_egui_hex(qcolor):
    """Convert a QColor to EGUI_COLOR_HEX(0xRRGGBB) string."""
    return f"EGUI_COLOR_HEX(0x{qcolor.red():02X}{qcolor.green():02X}{qcolor.blue():02X})"


def _color_swatch_size() -> int:
    tokens = app_theme_tokens()
    try:
        return max(int(tokens.get("space_xl", 20)), 1)
    except (TypeError, ValueError):
        return 20


def _color_picker_spacing() -> int:
    tokens = app_theme_tokens()
    try:
        return max(int(tokens.get("space_3xs", 2)), 0)
    except (TypeError, ValueError):
        return 2


class ColorSwatch(QWidget):
    """Small square widget that displays a solid color."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._color = QColor(Qt.white)
        swatch_size = _color_swatch_size()
        self.setFixedSize(QSize(swatch_size, swatch_size))
        _set_widget_metadata(
            self,
            tooltip="Color swatch preview.",
            accessible_name="Color swatch preview",
        )

    def set_color(self, qcolor):
        if qcolor and qcolor.isValid():
            self._color = qcolor
        else:
            self._color = QColor(Qt.white)
        self.update()

    def _border_color(self):
        border = QColor(self.palette().color(QPalette.Mid))
        if not border.isValid():
            border = QColor(Qt.gray)
        border.setAlpha(96)
        return border

    def paintEvent(self, event):
        p = QPainter(self)
        p.setBrush(QBrush(self._color))
        p.setPen(self._border_color())
        p.drawRect(self.rect().adjusted(1, 1, -1, -1))
        p.end()


class EguiColorPicker(QWidget):
    """Combo box with color swatch and a text button to open a color dialog.

    Emits ``color_changed(str)`` with the EGUI color expression.
    """

    color_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        from qfluentwidgets import EditableComboBox, ToolButton

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(_color_picker_spacing())

        self._swatch = ColorSwatch()
        layout.addWidget(self._swatch)

        self._combo = EditableComboBox()
        self._combo.addItems(COLORS)
        self._combo.currentTextChanged.connect(self._on_text_changed)
        layout.addWidget(self._combo, 1)

        self._btn = ToolButton()
        self._btn.setText("Pick")
        self._btn.clicked.connect(self._open_dialog)
        layout.addWidget(self._btn)
        self._update_accessibility_metadata(self.value())

    def set_value(self, value):
        """Set the current color value (EGUI expression)."""
        value = str(value or COLORS[0])
        if self._combo.findText(value) < 0:
            self._combo.addItem(value)
        self._combo.setCurrentText(value)
        self._update_swatch(value)
        self._update_accessibility_metadata(value)

    def value(self):
        return self._combo.currentText()

    def _on_text_changed(self, text):
        self._update_swatch(text)
        self._update_accessibility_metadata(text)
        self.color_changed.emit(text)

    def _update_swatch(self, text):
        qc = egui_color_to_qcolor(text)
        self._swatch.set_color(qc)

    def _open_dialog(self):
        initial = egui_color_to_qcolor(self._combo.currentText()) or QColor(Qt.white)
        color = QColorDialog.getColor(initial, self, "Select Color")
        if color.isValid():
            # Check if it matches a named color
            for name, rgb in COLOR_RGB.items():
                if (color.red(), color.green(), color.blue()) == rgb:
                    self.set_value(name)
                    return
            self.set_value(qcolor_to_egui_hex(color))

    def _color_summary(self, text):
        value_text = str(text or "").strip()
        qc = egui_color_to_qcolor(value_text)
        if qc is None:
            if value_text:
                return f"{value_text}. Preview unavailable."
            return "No color selected. Preview unavailable."
        return f"{value_text} ({qc.name().upper()})"

    def _update_accessibility_metadata(self, text):
        value_text = str(text or "").strip() or str(COLORS[0])
        summary = self._color_summary(text)
        _set_widget_metadata(
            self,
            tooltip=f"Color picker. Current color: {summary}",
            accessible_name=f"Color picker: {summary}",
        )
        _set_widget_metadata(
            self._combo,
            tooltip=f"Choose or type an EGUI color. Current value: {value_text}.",
            accessible_name=f"Color value: {value_text}",
        )
        _set_widget_metadata(
            self._swatch,
            tooltip=f"Color swatch preview: {summary}",
            accessible_name=f"Color swatch: {summary}",
        )
        _set_widget_metadata(
            self._btn,
            tooltip=f"Open the custom color dialog. Current color: {summary}",
            accessible_name=f"Open color dialog: {summary}",
        )
