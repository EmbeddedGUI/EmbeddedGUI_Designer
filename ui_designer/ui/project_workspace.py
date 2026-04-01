"""Combined project workspace panel with page list and thumbnail views."""

from __future__ import annotations

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QButtonGroup, QFrame, QLabel, QPushButton, QStackedWidget, QVBoxLayout, QHBoxLayout, QWidget

from .iconography import make_icon


def _set_widget_metadata(widget, *, tooltip=None, accessible_name=None):
    if tooltip is not None:
        widget.setToolTip(tooltip)
        widget.setStatusTip(tooltip)
    if accessible_name is not None:
        widget.setAccessibleName(accessible_name)


class ProjectWorkspacePanel(QWidget):
    """Hosts project explorer list and page thumbnails in one panel."""

    view_changed = pyqtSignal(str)

    VIEW_LIST = "list"
    VIEW_THUMBNAILS = "thumbnails"

    def __init__(self, list_view, thumbnail_view, parent=None):
        super().__init__(parent)
        self._list_view = list_view
        self._thumbnail_view = thumbnail_view
        self._current_page_count = 0
        self._current_active_page = ""
        self._current_startup_page = ""
        self._current_dirty_pages = 0
        self._current_view_name = ""
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self._header = QFrame()
        self._header.setObjectName("workspace_panel_header")
        header_layout = QVBoxLayout(self._header)
        header_layout.setContentsMargins(14, 14, 14, 14)
        header_layout.setSpacing(8)

        self._title_label = QLabel("Project Workspace")
        self._title_label.setObjectName("workspace_section_title")
        header_layout.addWidget(self._title_label)

        self._subtitle_label = QLabel("Switch between fast list management and visual page thumbnails.")
        self._subtitle_label.setObjectName("workspace_section_subtitle")
        self._subtitle_label.setWordWrap(True)
        header_layout.addWidget(self._subtitle_label)

        chips_row = QHBoxLayout()
        chips_row.setContentsMargins(0, 0, 0, 0)
        chips_row.setSpacing(6)
        self._page_count_chip = QLabel("0 pages")
        self._page_count_chip.setObjectName("workspace_status_chip")
        chips_row.addWidget(self._page_count_chip)
        self._active_page_chip = QLabel("No active page")
        self._active_page_chip.setObjectName("workspace_status_chip")
        self._active_page_chip.setProperty("chipTone", "accent")
        chips_row.addWidget(self._active_page_chip)
        self._dirty_pages_chip = QLabel("No dirty pages")
        self._dirty_pages_chip.setObjectName("workspace_status_chip")
        self._dirty_pages_chip.setProperty("chipTone", "success")
        chips_row.addWidget(self._dirty_pages_chip)
        self._view_chip = QLabel("List view")
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
        self._list_btn = QPushButton("List\nStructure first")
        self._list_btn.setObjectName("project_workspace_view_button")
        self._list_btn.setCheckable(True)
        self._list_btn.setIcon(make_icon("project"))
        _set_widget_metadata(
            self._list_btn,
            tooltip="Show the page list for structure-first editing.",
            accessible_name="Workspace view button: List. Structure first.",
        )
        self._thumb_btn = QPushButton("Thumbnails\nVisual scan")
        self._thumb_btn.setObjectName("project_workspace_view_button")
        self._thumb_btn.setCheckable(True)
        self._thumb_btn.setIcon(make_icon("image"))
        _set_widget_metadata(
            self._thumb_btn,
            tooltip="Show page thumbnails for a visual scan.",
            accessible_name="Workspace view button: Thumbnails. Visual scan.",
        )
        self._button_group.addButton(self._list_btn)
        self._button_group.addButton(self._thumb_btn)
        self._list_btn.clicked.connect(lambda: self.set_view(self.VIEW_LIST))
        self._thumb_btn.clicked.connect(lambda: self.set_view(self.VIEW_THUMBNAILS))
        toggle_row.addWidget(self._list_btn)
        toggle_row.addWidget(self._thumb_btn)
        toggle_row.addStretch()
        header_layout.addLayout(toggle_row)
        layout.addWidget(self._header)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._list_view)
        self._stack.addWidget(self._thumbnail_view)
        layout.addWidget(self._stack, 1)

        self.set_view(self.VIEW_LIST)
        self.set_workspace_snapshot()

    def _set_chip(self, chip, text, tone=None, accessible_name=None):
        chip.setText(str(text or ""))
        metadata_text = str(accessible_name or text or "")
        _set_widget_metadata(chip, tooltip=metadata_text, accessible_name=metadata_text)
        if tone is not None:
            chip.setProperty("chipTone", str(tone or "accent"))
        chip.style().unpolish(chip)
        chip.style().polish(chip)
        chip.update()

    def _update_panel_metadata(self):
        view_label = self._view_chip.text() or "List view"
        page_label = self._page_count_chip.text() or "0 pages"
        active_text = self._current_active_page or "none"
        startup_text = self._current_startup_page or "none"
        dirty_text = self._dirty_pages_chip.text() or "No dirty pages"
        summary = (
            f"Project workspace: {view_label}. "
            f"Pages: {page_label}. Active page: {active_text}. Startup page: {startup_text}. Dirty state: {dirty_text}."
        )
        _set_widget_metadata(self, tooltip=summary, accessible_name=summary)
        _set_widget_metadata(self._header, tooltip=summary, accessible_name=summary)
        _set_widget_metadata(
            self._title_label,
            tooltip=summary,
            accessible_name=f"Project Workspace. {view_label}.",
        )
        _set_widget_metadata(
            self._subtitle_label,
            tooltip=self._subtitle_label.text(),
            accessible_name=self._subtitle_label.text(),
        )

    def _update_view_button_metadata(self, current_view):
        button_specs = (
            (
                self._list_btn,
                self.VIEW_LIST,
                "List",
                "Structure first",
                "the page list for structure-first editing",
            ),
            (
                self._thumb_btn,
                self.VIEW_THUMBNAILS,
                "Thumbnails",
                "Visual scan",
                "page thumbnails for a visual scan",
            ),
        )
        for button, view_name, label, detail, description in button_specs:
            is_current = current_view == view_name
            if is_current:
                tooltip = f"Currently showing {description}."
                accessible_name = f"Workspace view button: {label}. {detail}. Current view."
            else:
                tooltip = f"Switch to {description}."
                accessible_name = f"Workspace view button: {label}. {detail}. Available."
            _set_widget_metadata(button, tooltip=tooltip, accessible_name=accessible_name)

    def _update_stack_metadata(self, view_label):
        summary = f"Project workspace view stack: {view_label} visible."
        _set_widget_metadata(self._stack, tooltip=summary, accessible_name=summary)

    def set_view(self, view_name):
        view_name = self.VIEW_THUMBNAILS if view_name == self.VIEW_THUMBNAILS else self.VIEW_LIST
        if self._current_view_name == view_name:
            return
        if view_name == self.VIEW_THUMBNAILS:
            self._thumb_btn.setChecked(True)
            self._stack.setCurrentWidget(self._thumbnail_view)
        else:
            self._list_btn.setChecked(True)
            self._stack.setCurrentWidget(self._list_view)
        view_label = "Thumbnails" if view_name == self.VIEW_THUMBNAILS else "List view"
        self._set_chip(self._view_chip, view_label, "accent", accessible_name=f"Workspace view: {view_label}.")
        self._update_view_button_metadata(view_name)
        self._update_stack_metadata(view_label)
        self._update_panel_metadata()
        self._current_view_name = view_name
        self.view_changed.emit(view_name)

    def current_view(self):
        if self._stack.currentWidget() is self._thumbnail_view:
            return self.VIEW_THUMBNAILS
        return self.VIEW_LIST

    def set_workspace_snapshot(self, *, page_count=0, active_page="", startup_page="", dirty_pages=0):
        pages = max(int(page_count or 0), 0)
        dirty = max(int(dirty_pages or 0), 0)
        active = str(active_page or "").strip() or "None"
        startup = str(startup_page or "").strip() or "None"
        self._current_page_count = pages
        self._current_active_page = "" if active == "None" else active
        self._current_startup_page = "" if startup == "None" else startup
        self._current_dirty_pages = dirty
        page_label = f"{pages} page" if pages == 1 else f"{pages} pages"
        self._set_chip(
            self._page_count_chip,
            page_label,
            "success" if pages > 0 else "warning",
            accessible_name=f"Workspace pages: {page_label}.",
        )
        if active != "None":
            self._active_page_chip.setVisible(True)
            self._set_chip(
                self._active_page_chip,
                f"Active: {active}",
                "accent",
                accessible_name=f"Workspace active page: {active}.",
            )
        else:
            self._active_page_chip.setVisible(False)
            self._set_chip(
                self._active_page_chip,
                "No active page",
                "warning",
                accessible_name="Workspace active page: none.",
            )
        if dirty > 0:
            self._dirty_pages_chip.setVisible(True)
            dirty_label = f"{dirty} dirty page" if dirty == 1 else f"{dirty} dirty pages"
            self._set_chip(
                self._dirty_pages_chip,
                dirty_label,
                "warning",
                accessible_name=f"Workspace dirty pages: {dirty_label}.",
            )
        else:
            self._dirty_pages_chip.setVisible(False)
            self._set_chip(
                self._dirty_pages_chip,
                "No dirty pages",
                "success",
                accessible_name="Workspace dirty pages: no dirty pages.",
            )
        self._update_panel_metadata()
