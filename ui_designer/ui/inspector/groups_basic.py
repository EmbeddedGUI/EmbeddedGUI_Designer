"""Basic property group for InspectorPanel."""

from __future__ import annotations

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QFormLayout, QLineEdit, QWidget


class BasicGroup(QWidget):
    """Edits basic node metadata fields."""

    patch_requested = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._node_id = None
        self._patching = False

        layout = QFormLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._name_input = QLineEdit(self)
        self._type_input = QLineEdit(self)
        self._type_input.setReadOnly(True)
        layout.addRow("Name", self._name_input)
        layout.addRow("Type", self._type_input)

        self._name_input.editingFinished.connect(self._emit_patch)

    def set_context(self, node: dict | None) -> None:
        self._patching = True
        node = node or {}
        self._node_id = node.get("id")
        self._name_input.setText(str(node.get("name", "") or ""))
        self._type_input.setText(str(node.get("type", "") or ""))
        self._patching = False

    def _emit_patch(self) -> None:
        if self._patching or not self._node_id:
            return
        self.patch_requested.emit({"id": self._node_id, "patch": {"name": self._name_input.text().strip()}})
