"""Layout property group for InspectorPanel."""

from __future__ import annotations

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QFormLayout, QSpinBox, QWidget


class LayoutGroup(QWidget):
    """Edits layout properties (x/y/width/height)."""

    patch_requested = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._node_id = None
        self._patching = False

        layout = QFormLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._x_input = QSpinBox(self)
        self._x_input.setRange(-9999, 9999)
        self._y_input = QSpinBox(self)
        self._y_input.setRange(-9999, 9999)
        self._w_input = QSpinBox(self)
        self._w_input.setRange(0, 9999)
        self._h_input = QSpinBox(self)
        self._h_input.setRange(0, 9999)

        layout.addRow("X", self._x_input)
        layout.addRow("Y", self._y_input)
        layout.addRow("Width", self._w_input)
        layout.addRow("Height", self._h_input)

        for widget in (self._x_input, self._y_input, self._w_input, self._h_input):
            widget.valueChanged.connect(self._emit_patch)

    def set_context(self, node: dict | None) -> None:
        self._patching = True
        node = node or {}
        self._node_id = node.get("id")
        self._x_input.setValue(int(node.get("x", 0) or 0))
        self._y_input.setValue(int(node.get("y", 0) or 0))
        self._w_input.setValue(int(node.get("width", 0) or 0))
        self._h_input.setValue(int(node.get("height", 0) or 0))
        self._patching = False

    def _emit_patch(self) -> None:
        if self._patching or not self._node_id:
            return
        self.patch_requested.emit(
            {
                "id": self._node_id,
                "patch": {
                    "x": int(self._x_input.value()),
                    "y": int(self._y_input.value()),
                    "width": int(self._w_input.value()),
                    "height": int(self._h_input.value()),
                },
            }
        )
