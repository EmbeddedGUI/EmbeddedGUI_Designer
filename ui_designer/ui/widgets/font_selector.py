"""Font selector widget with preview label for EmbeddedGUI Designer."""

import re

from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel
from PyQt5.QtCore import pyqtSignal, Qt

from qfluentwidgets import EditableComboBox, BodyLabel

from ...model.widget_model import FONTS


# Parse font resource name to extract display info
# e.g. "&egui_res_font_montserrat_14_4" -> "montserrat 14px 4bpp"
_FONT_RE = re.compile(r'&egui_res_font_(\w+?)_(\d+)_(\d+)$')


def _set_widget_metadata(widget, *, tooltip=None, accessible_name=None):
    if tooltip is not None:
        hint = str(tooltip or "")
        if str(widget.property("_font_selector_hint_snapshot") or "") != hint:
            widget.setToolTip(hint)
            widget.setStatusTip(hint)
            widget.setProperty("_font_selector_hint_snapshot", hint)
    if accessible_name is not None:
        name = str(accessible_name or "")
        if str(widget.property("_font_selector_accessible_snapshot") or "") != name:
            widget.setAccessibleName(name)
            widget.setProperty("_font_selector_accessible_snapshot", name)


def _font_display_info(font_expr):
    """Extract human-readable info from a font expression.

    Returns (family, size, bpp) or None.
    """
    m = _FONT_RE.match(font_expr)
    if m:
        return m.group(1), m.group(2), m.group(3)
    return None


class EguiFontSelector(QWidget):
    """Editable combo box for font selection with a preview label.

    Emits ``font_changed(str)`` with the EGUI font expression.
    """

    font_changed = pyqtSignal(str)

    def __init__(self, fonts=None, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self._combo = EditableComboBox()
        items = list(fonts) if fonts else list(FONTS)
        self._combo.addItems(items)
        self._combo.currentTextChanged.connect(self._on_changed)
        layout.addWidget(self._combo, 1)

        self._preview = self._create_preview_label()
        self._preview.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._preview.setFixedWidth(60)
        layout.addWidget(self._preview)
        self._update_preview(self.value())
        self._update_accessibility_metadata(self.value())

    @staticmethod
    def _create_preview_label():
        """Build a preview label while tolerating stale qfluentwidgets globals."""
        try:
            return BodyLabel("Abc")
        except RuntimeError:
            return QLabel("Abc")

    def set_value(self, value):
        """Set the current font value."""
        value = str(value or "")
        if value and self._combo.findText(value) < 0:
            self._combo.addItem(value)
        self._combo.setCurrentText(value)
        self._update_preview(value)
        self._update_accessibility_metadata(value)

    def value(self):
        return self._combo.currentText()

    def _on_changed(self, text):
        self._update_preview(text)
        self._update_accessibility_metadata(text)
        self.font_changed.emit(text)

    def _update_preview(self, text):
        info = _font_display_info(text)
        if info:
            _family, size, _bpp = info
            self._preview.setText(f"{size}px")
            try:
                pt = max(8, min(int(size), 20))
                self._preview.setStyleSheet(f"font-size: {pt}px;")
            except ValueError:
                self._preview.setStyleSheet("")
        elif text == "EGUI_CONFIG_FONT_DEFAULT":
            self._preview.setText("Default")
            self._preview.setStyleSheet("")
        else:
            self._preview.setText("Custom")
            self._preview.setStyleSheet("")

    def _font_summary(self, text):
        text = str(text or "").strip()
        info = _font_display_info(text)
        if info:
            family, size, bpp = info
            return f"{family} {size}px {bpp}bpp"
        if text == "EGUI_CONFIG_FONT_DEFAULT":
            return "Default font"
        if text:
            return f"Custom font expression: {text}"
        return "No font selected"

    def _update_accessibility_metadata(self, text):
        value_text = str(text or "").strip() or "none"
        summary = self._font_summary(text)
        preview_text = str(self._preview.text() or "Custom").strip() or "Custom"
        _set_widget_metadata(
            self,
            tooltip=f"Font selector. {summary}.",
            accessible_name=f"Font selector: {summary}.",
        )
        _set_widget_metadata(
            self._combo,
            tooltip=f"Choose or type an EGUI font. Current value: {value_text}.",
            accessible_name=f"Font value: {value_text}",
        )
        _set_widget_metadata(
            self._preview,
            tooltip=f"Font preview: {preview_text}.",
            accessible_name=f"Font preview: {preview_text}. {summary}.",
        )
