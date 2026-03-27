"""Combined project workspace panel with page list and thumbnail views."""

from __future__ import annotations

from PyQt5.QtWidgets import QButtonGroup, QFrame, QPushButton, QStackedWidget, QVBoxLayout, QHBoxLayout, QWidget


class ProjectWorkspacePanel(QWidget):
    """Hosts project explorer list and page thumbnails in one panel."""

    VIEW_LIST = "list"
    VIEW_THUMBNAILS = "thumbnails"

    def __init__(self, list_view, thumbnail_view, parent=None):
        super().__init__(parent)
        self._list_view = list_view
        self._thumbnail_view = thumbnail_view
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        header = QFrame()
        header.setObjectName("workspace_panel_header")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(14, 14, 14, 14)
        header_layout.setSpacing(8)

        toggle_row = QHBoxLayout()
        toggle_row.setContentsMargins(0, 0, 0, 0)
        toggle_row.setSpacing(8)

        self._button_group = QButtonGroup(self)
        self._button_group.setExclusive(True)
        self._list_btn = QPushButton("List")
        self._list_btn.setCheckable(True)
        self._thumb_btn = QPushButton("Thumbnails")
        self._thumb_btn.setCheckable(True)
        self._button_group.addButton(self._list_btn)
        self._button_group.addButton(self._thumb_btn)
        self._list_btn.clicked.connect(lambda: self.set_view(self.VIEW_LIST))
        self._thumb_btn.clicked.connect(lambda: self.set_view(self.VIEW_THUMBNAILS))
        toggle_row.addWidget(self._list_btn)
        toggle_row.addWidget(self._thumb_btn)
        toggle_row.addStretch()
        header_layout.addLayout(toggle_row)
        layout.addWidget(header)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._list_view)
        self._stack.addWidget(self._thumbnail_view)
        layout.addWidget(self._stack, 1)

        self.set_view(self.VIEW_LIST)

    def set_view(self, view_name):
        if view_name == self.VIEW_THUMBNAILS:
            self._thumb_btn.setChecked(True)
            self._stack.setCurrentWidget(self._thumbnail_view)
        else:
            self._list_btn.setChecked(True)
            self._stack.setCurrentWidget(self._list_view)

    def current_view(self):
        if self._stack.currentWidget() is self._thumbnail_view:
            return self.VIEW_THUMBNAILS
        return self.VIEW_LIST
