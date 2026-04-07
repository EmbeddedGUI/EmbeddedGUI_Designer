"""Reusable collapsible group box for inspector panels."""

from __future__ import annotations

from PyQt5.QtGui import QShowEvent
from PyQt5.QtWidgets import QFrame, QGroupBox, QVBoxLayout


class CollapsibleGroupBox(QGroupBox):
    """A QGroupBox that can be collapsed/expanded by clicking its title."""

    _CONTENT_INDENT = 18

    def __init__(self, title: str, parent=None):
        super().__init__("", parent)
        self._base_title = str(title or "").strip()
        self._content_layout = None
        self.setObjectName("inspector_collapsible_group")
        self.setCheckable(True)
        self.setChecked(True)

        self._content_frame = QFrame(self)
        self._content_frame.setObjectName("inspector_group_body")
        self._content_frame.setFrameShape(QFrame.NoFrame)

        outer_layout = QVBoxLayout()
        outer_layout.setContentsMargins(self._CONTENT_INDENT, 0, 0, 0)
        outer_layout.setSpacing(0)
        outer_layout.addWidget(self._content_frame)
        super().setLayout(outer_layout)

        self.toggled.connect(self._on_toggled)
        self._sync_title()

    def title(self):
        return self._base_title

    def setTitle(self, title):
        self._base_title = str(title or "").strip()
        self._sync_title()

    def setLayout(self, layout):
        if layout is None:
            return
        self._content_layout = layout
        self._content_frame.setLayout(layout)

    def layout(self):
        return self._content_layout

    def content_frame(self):
        return self._content_frame

    def content_indent(self):
        return self._CONTENT_INDENT

    def _sync_title(self):
        arrow = "▼" if self.isChecked() else "▶"
        label = self._base_title or ""
        super().setTitle(f"{arrow} {label}".strip())

    def apply_expanded_state(self, expanded: bool):
        """Set expanded/collapsed without emitting ``toggled``; updates child visibility."""
        self.blockSignals(True)
        try:
            self.setChecked(expanded)
            self._on_toggled(expanded)
        finally:
            self.blockSignals(False)

    def _collapsed_height(self) -> int:
        return max(32, self.fontMetrics().height() + 18)

    def showEvent(self, event: QShowEvent):
        super().showEvent(event)
        self._on_toggled(self.isChecked())

    def _on_toggled(self, checked: bool):
        if self._content_layout is None:
            return
        self._sync_title()
        self._content_frame.setVisible(checked)
        if checked:
            self.setMaximumHeight(16777215)
        else:
            self.setMaximumHeight(self._collapsed_height())
        self.updateGeometry()
