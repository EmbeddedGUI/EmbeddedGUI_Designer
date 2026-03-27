"""Combined project workspace panel with page list and thumbnail views."""

from __future__ import annotations

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QButtonGroup, QFrame, QLabel, QPushButton, QStackedWidget, QVBoxLayout, QHBoxLayout, QWidget

from .iconography import make_icon


class ProjectWorkspacePanel(QWidget):
    """Hosts project explorer list and page thumbnails in one panel."""

    view_changed = pyqtSignal(str)

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

        title = QLabel("Project Workspace")
        title.setObjectName("workspace_section_title")
        header_layout.addWidget(title)

        subtitle = QLabel("Switch between fast list management and visual page thumbnails.")
        subtitle.setObjectName("workspace_section_subtitle")
        subtitle.setWordWrap(True)
        header_layout.addWidget(subtitle)

        chips_row = QHBoxLayout()
        chips_row.setContentsMargins(0, 0, 0, 0)
        chips_row.setSpacing(6)
        self._page_count_chip = QLabel("Pages 0")
        self._page_count_chip.setObjectName("workspace_status_chip")
        chips_row.addWidget(self._page_count_chip)
        self._active_page_chip = QLabel("Active None")
        self._active_page_chip.setObjectName("workspace_status_chip")
        self._active_page_chip.setProperty("chipTone", "accent")
        chips_row.addWidget(self._active_page_chip)
        self._dirty_pages_chip = QLabel("Clean")
        self._dirty_pages_chip.setObjectName("workspace_status_chip")
        self._dirty_pages_chip.setProperty("chipTone", "success")
        chips_row.addWidget(self._dirty_pages_chip)
        self._view_chip = QLabel("List View")
        self._view_chip.setObjectName("workspace_status_chip")
        self._view_chip.setProperty("chipTone", "accent")
        chips_row.addWidget(self._view_chip)
        chips_row.addStretch()
        header_layout.addLayout(chips_row)

        toggle_row = QHBoxLayout()
        toggle_row.setContentsMargins(0, 0, 0, 0)
        toggle_row.setSpacing(8)

        self._button_group = QButtonGroup(self)
        self._button_group.setExclusive(True)
        self._list_btn = QPushButton("List\nStructure-first")
        self._list_btn.setObjectName("project_workspace_view_button")
        self._list_btn.setCheckable(True)
        self._list_btn.setIcon(make_icon("project"))
        self._thumb_btn = QPushButton("Thumbnails\nVisual scan")
        self._thumb_btn.setObjectName("project_workspace_view_button")
        self._thumb_btn.setCheckable(True)
        self._thumb_btn.setIcon(make_icon("image"))
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
        self.set_workspace_snapshot()

    def _set_chip(self, chip, text, tone=None):
        chip.setText(str(text or ""))
        if tone is not None:
            chip.setProperty("chipTone", str(tone or "accent"))
        chip.style().unpolish(chip)
        chip.style().polish(chip)
        chip.update()

    def set_view(self, view_name):
        if view_name == self.VIEW_THUMBNAILS:
            self._thumb_btn.setChecked(True)
            self._stack.setCurrentWidget(self._thumbnail_view)
        else:
            self._list_btn.setChecked(True)
            self._stack.setCurrentWidget(self._list_view)
            view_name = self.VIEW_LIST
        self._set_chip(self._view_chip, "Thumbnails" if view_name == self.VIEW_THUMBNAILS else "List View", "accent")
        self.view_changed.emit(view_name)

    def current_view(self):
        if self._stack.currentWidget() is self._thumbnail_view:
            return self.VIEW_THUMBNAILS
        return self.VIEW_LIST

    def set_workspace_snapshot(self, *, page_count=0, active_page="", dirty_pages=0):
        pages = max(int(page_count or 0), 0)
        dirty = max(int(dirty_pages or 0), 0)
        active = str(active_page or "").strip() or "None"
        self._set_chip(self._page_count_chip, f"Pages {pages}", "success" if pages > 0 else "warning")
        self._set_chip(self._active_page_chip, f"Active {active}", "accent" if active != "None" else "warning")
        if dirty > 0:
            self._set_chip(self._dirty_pages_chip, f"Dirty {dirty}", "warning")
        else:
            self._set_chip(self._dirty_pages_chip, "Clean", "success")
