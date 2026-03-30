"""Reusable collapsible group box for inspector panels."""

from __future__ import annotations

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

    def _on_toggled(self, checked: bool):
        layout = self.layout()
        if layout is None:
            return
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item.widget():
                item.widget().setVisible(checked)
        if checked:
            self.setMaximumHeight(16777215)
        else:
            self.setMaximumHeight(32)
