"""Combined project workspace panel with page list and thumbnail views."""

from __future__ import annotations

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QButtonGroup, QFrame, QLabel, QPushButton, QStackedWidget, QVBoxLayout, QHBoxLayout, QWidget

from .theme import theme_tokens


_TOKENS = theme_tokens("dark")
_SPACE_XS = int(_TOKENS.get("space_xs", 4))
_SPACE_SM = int(_TOKENS.get("space_sm", 8))
_SPACE_MD = int(_TOKENS.get("space_md", 12))
_PROJECT_WORKSPACE_BUTTON_HEIGHT = 22


def _set_widget_metadata(widget, *, tooltip=None, accessible_name=None):
    if tooltip is not None:
        resolved_tooltip = str(tooltip or "")
        current_tooltip = widget.property("_workspace_metadata_tooltip_snapshot")
        if current_tooltip is None or str(current_tooltip) != resolved_tooltip:
            widget.setToolTip(resolved_tooltip)
            widget.setStatusTip(resolved_tooltip)
            widget.setProperty("_workspace_metadata_tooltip_snapshot", resolved_tooltip)
    if accessible_name is not None:
        resolved_accessible_name = str(accessible_name or "")
        current_accessible_name = widget.property("_workspace_metadata_accessible_snapshot")
        if current_accessible_name is None or str(current_accessible_name) != resolved_accessible_name:
            widget.setAccessibleName(resolved_accessible_name)
            widget.setProperty("_workspace_metadata_accessible_snapshot", resolved_accessible_name)


def _set_compact_button_height(button):
    button.setFixedHeight(_PROJECT_WORKSPACE_BUTTON_HEIGHT)
    return button


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
        self._has_project_dirty = False
        self._project_dirty_reason = ""
        self._current_view_name = ""
        self._workspace_snapshot_initialized = False
        self._init_ui()

    def _init_ui(self):
        for child in (self._list_view, self._thumbnail_view):
            if hasattr(child, "set_compact_mode"):
                child.set_compact_mode(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self._header = QFrame()
        self._header.setObjectName("workspace_panel_header")
        self._header.setProperty("panelTone", "project")
        header_layout = QHBoxLayout(self._header)
        header_layout.setContentsMargins(2, 2, 2, 2)
        header_layout.setSpacing(2)

        self._header_eyebrow = QLabel("Pages", self._header)
        self._header_eyebrow.setObjectName("project_workspace_eyebrow")
        self._header_eyebrow.hide()

        self._title_label = QLabel("Pages")
        self._title_label.setObjectName("workspace_section_title")
        header_layout.addWidget(self._title_label, 1)

        self._subtitle_label = QLabel("Page navigation, startup flow, and visual scan.", self._header)
        self._subtitle_label.setObjectName("workspace_section_subtitle")
        self._subtitle_label.hide()

        self._metrics_frame = QFrame(self._header)
        self._metrics_frame.setObjectName("project_workspace_metrics_strip")
        self._metrics_frame.hide()
        metrics_layout = QHBoxLayout(self._metrics_frame)
        metrics_layout.setContentsMargins(0, 0, 0, 0)
        metrics_layout.setSpacing(2)

        self._view_chip = QLabel("List view", self._metrics_frame)
        self._view_chip.setObjectName("workspace_status_chip")
        self._view_chip.hide()
        metrics_layout.addWidget(self._view_chip)

        self._page_count_chip = QLabel("0 pages", self._metrics_frame)
        self._page_count_chip.setObjectName("workspace_status_chip")
        self._page_count_chip.hide()
        metrics_layout.addWidget(self._page_count_chip)

        self._dirty_chip = QLabel("Clean", self._metrics_frame)
        self._dirty_chip.setObjectName("workspace_status_chip")
        self._dirty_chip.hide()
        metrics_layout.addWidget(self._dirty_chip)

        self._summary_label = QLabel("0 pages. Active: none. Clean.", self._header)
        self._summary_label.setObjectName("workspace_section_subtitle")
        self._summary_label.hide()

        self._meta_label = QLabel("Startup: none", self._header)
        self._meta_label.setObjectName("project_workspace_meta")
        self._meta_label.hide()

        toggle_row = QHBoxLayout()
        self._view_toggle_row = toggle_row
        toggle_row.setContentsMargins(0, 0, 0, 0)
        toggle_row.setSpacing(2)

        self._button_group = QButtonGroup(self)
        self._button_group.setExclusive(True)
        self._settings_btn = _set_compact_button_height(QPushButton("Settings"))
        self._settings_btn.setObjectName("project_workspace_view_button")
        self._settings_btn.clicked.connect(self._toggle_project_settings)
        _set_widget_metadata(
            self._settings_btn,
            tooltip="Show or hide low-frequency project settings.",
            accessible_name="Project settings button",
        )
        self._list_btn = _set_compact_button_height(QPushButton("List"))
        self._list_btn.setObjectName("project_workspace_view_button")
        self._list_btn.setCheckable(True)
        _set_widget_metadata(
            self._list_btn,
            tooltip="Show the page list for structure-first editing.",
            accessible_name="Workspace view button: List. Structure first.",
        )
        self._thumb_btn = _set_compact_button_height(QPushButton("Thumbs"))
        self._thumb_btn.setObjectName("project_workspace_view_button")
        self._thumb_btn.setCheckable(True)
        _set_widget_metadata(
            self._thumb_btn,
            tooltip="Show page thumbnails for a visual scan.",
            accessible_name="Workspace view button: Thumbnails. Visual scan.",
        )
        self._button_group.addButton(self._list_btn)
        self._button_group.addButton(self._thumb_btn)
        self._list_btn.clicked.connect(lambda: self.set_view(self.VIEW_LIST))
        self._thumb_btn.clicked.connect(lambda: self.set_view(self.VIEW_THUMBNAILS))
        toggle_row.addWidget(self._settings_btn)
        toggle_row.addWidget(self._list_btn)
        toggle_row.addWidget(self._thumb_btn)
        header_layout.addLayout(toggle_row)
        layout.addWidget(self._header)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._list_view)
        self._stack.addWidget(self._thumbnail_view)
        layout.addWidget(self._stack, 1)

        self.set_view(self.VIEW_LIST)
        self.set_workspace_snapshot()

    def _update_panel_metadata(self):
        view_label = "Thumbnails" if self._current_view_name == self.VIEW_THUMBNAILS else "List view"
        page_label = f"{self._current_page_count} page" if self._current_page_count == 1 else f"{self._current_page_count} pages"
        active_text = self._current_active_page or "none"
        startup_text = self._current_startup_page or "none"
        dirty_count = int(self._current_dirty_pages or 0)
        has_project_dirty = bool(self._has_project_dirty)
        project_dirty_reason = str(self._project_dirty_reason or "").strip()
        project_dirty_suffix = f" ({project_dirty_reason})" if project_dirty_reason else ""
        if dirty_count == 0 and not has_project_dirty:
            dirty_text = "No dirty pages"
            summary_dirty_text = "Clean"
            chip_text = "Clean"
        elif dirty_count == 0:
            dirty_text = f"Project changes pending{project_dirty_suffix}"
            summary_dirty_text = dirty_text
            chip_text = dirty_text
        elif has_project_dirty:
            dirty_pages_text = f"{dirty_count} dirty page" if dirty_count == 1 else f"{dirty_count} dirty pages"
            dirty_text = f"{dirty_pages_text} + project changes{project_dirty_suffix}"
            summary_dirty_text = dirty_text
            chip_text = dirty_text
        else:
            dirty_text = f"{dirty_count} dirty page" if dirty_count == 1 else f"{dirty_count} dirty pages"
            summary_dirty_text = dirty_text
            chip_text = dirty_text
        summary = (
            f"Project workspace: {view_label}. "
            f"Pages: {page_label}. Active page: {active_text}. Startup page: {startup_text}. Dirty state: {dirty_text}."
        )
        self._view_chip.setText(view_label)
        self._page_count_chip.setText(page_label)
        self._dirty_chip.setText(chip_text)
        self._summary_label.setText(f"{page_label}. Active: {active_text}. {summary_dirty_text}.")
        self._meta_label.setText(f"Startup: {startup_text}")

        _set_widget_metadata(self, tooltip=summary, accessible_name=summary)
        _set_widget_metadata(
            self._header,
            tooltip=f"Project workspace header. {summary}",
            accessible_name=f"Project workspace header. {summary}",
        )
        _set_widget_metadata(
            self._title_label,
            tooltip=summary,
            accessible_name=f"Project Workspace. {view_label}.",
        )
        _set_widget_metadata(
            self._header_eyebrow,
            tooltip="Project navigation workspace surface.",
            accessible_name="Project navigation workspace surface.",
        )
        _set_widget_metadata(
            self._subtitle_label,
            tooltip=self._subtitle_label.text(),
            accessible_name=self._subtitle_label.text(),
        )
        _set_widget_metadata(
            self._view_chip,
            tooltip=f"Workspace view: {view_label}.",
            accessible_name=f"Workspace view: {view_label}.",
        )
        _set_widget_metadata(
            self._page_count_chip,
            tooltip=f"Page count: {page_label}.",
            accessible_name=f"Page count: {page_label}.",
        )
        _set_widget_metadata(
            self._dirty_chip,
            tooltip=f"Dirty state: {dirty_text}.",
            accessible_name=f"Dirty state: {dirty_text}.",
        )
        _set_widget_metadata(
            self._metrics_frame,
            tooltip=f"Project workspace metrics: {page_label}. {dirty_text}.",
            accessible_name=f"Project workspace metrics: {page_label}. {dirty_text}.",
        )
        _set_widget_metadata(
            self._summary_label,
            tooltip=f"Pages summary: {self._summary_label.text()}",
            accessible_name=f"Pages summary: {self._summary_label.text()}",
        )
        _set_widget_metadata(
            self._meta_label,
            tooltip=f"Pages startup summary: {self._meta_label.text()}",
            accessible_name=f"Pages startup summary: {self._meta_label.text()}",
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
        if hasattr(self, "_settings_btn"):
            _set_widget_metadata(
                self._settings_btn,
                tooltip="Show or hide low-frequency project settings.",
                accessible_name="Project settings button",
            )

    def _update_stack_metadata(self, view_label):
        summary = f"Project workspace view stack: {view_label} visible."
        _set_widget_metadata(self._stack, tooltip=summary, accessible_name=summary)

    def _toggle_project_settings(self):
        if hasattr(self._list_view, "_settings_group"):
            self.set_view(self.VIEW_LIST)
            current_visible = bool(self._list_view._settings_group.isVisible())
            self._list_view._settings_group.setVisible(not current_visible)

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
        self._current_view_name = view_name
        view_label = "Thumbnails" if view_name == self.VIEW_THUMBNAILS else "List view"
        self._update_view_button_metadata(view_name)
        self._update_stack_metadata(view_label)
        self._update_panel_metadata()
        self.view_changed.emit(view_name)

    def current_view(self):
        if self._stack.currentWidget() is self._thumbnail_view:
            return self.VIEW_THUMBNAILS
        return self.VIEW_LIST

    def set_workspace_snapshot(
        self,
        *,
        page_count=0,
        active_page="",
        startup_page="",
        dirty_pages=0,
        project_dirty=False,
        project_dirty_reason="",
    ):
        pages = max(int(page_count or 0), 0)
        dirty = max(int(dirty_pages or 0), 0)
        has_project_dirty = bool(project_dirty)
        dirty_reason = str(project_dirty_reason or "").strip()
        active = str(active_page or "").strip() or "None"
        startup = str(startup_page or "").strip() or "None"
        normalized_active = "" if active == "None" else active
        normalized_startup = "" if startup == "None" else startup
        if (
            self._workspace_snapshot_initialized
            and self._current_page_count == pages
            and self._current_active_page == normalized_active
            and self._current_startup_page == normalized_startup
            and self._current_dirty_pages == dirty
            and self._has_project_dirty == has_project_dirty
            and self._project_dirty_reason == dirty_reason
        ):
            return
        self._current_page_count = pages
        self._current_active_page = normalized_active
        self._current_startup_page = normalized_startup
        self._current_dirty_pages = dirty
        self._has_project_dirty = has_project_dirty
        self._project_dirty_reason = dirty_reason
        self._workspace_snapshot_initialized = True
        self._update_panel_metadata()
