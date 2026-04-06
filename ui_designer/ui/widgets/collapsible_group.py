"""Reusable collapsible group box for inspector panels."""

from __future__ import annotations

from PyQt5.QtGui import QShowEvent
from PyQt5.QtWidgets import QGroupBox


class CollapsibleGroupBox(QGroupBox):
    """A QGroupBox that can be collapsed/expanded by clicking its title."""

    def __init__(self, title: str, parent=None):
        super().__init__(title, parent)
        self.setObjectName("inspector_collapsible_group")
        self.setCheckable(True)
        self.setChecked(True)
        self.toggled.connect(self._on_toggled)

    def apply_expanded_state(self, expanded: bool):
        """Set expanded/collapsed without emitting ``toggled``; updates child visibility."""
        self.blockSignals(True)
        try:
            self.setChecked(expanded)
            self._on_toggled(expanded)
        finally:
            self.blockSignals(False)

    def _set_layout_visibility(self, layout, visible: bool):
        if layout is None:
            return
        for i in range(layout.count()):
            item = layout.itemAt(i)
            widget = item.widget()
            child_layout = item.layout()
            if widget is not None:
                widget.setVisible(visible)
            if child_layout is not None:
                self._set_layout_visibility(child_layout, visible)

    def _collapsed_height(self) -> int:
        return max(32, self.fontMetrics().height() + 18)

    def showEvent(self, event: QShowEvent):
        super().showEvent(event)
        self._on_toggled(self.isChecked())

    def _on_toggled(self, checked: bool):
        layout = self.layout()
        if layout is None:
            return
        self._set_layout_visibility(layout, checked)
        if checked:
            self.setMaximumHeight(16777215)
        else:
            self.setMaximumHeight(self._collapsed_height())
        self.updateGeometry()
