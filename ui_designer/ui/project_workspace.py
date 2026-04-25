"""Combined project workspace panel with page list and thumbnail views."""

from __future__ import annotations

from PyQt5.QtCore import QEvent, pyqtSignal
from PyQt5.QtWidgets import (
    QButtonGroup,
    QFrame,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
)

from .theme import app_theme_tokens

_PROJECT_WORKSPACE_METRICS_SPACING = 1


def _project_workspace_button_height() -> int:
    tokens = app_theme_tokens()
    return max(int(tokens.get("h_tab_min", 24)) - int(tokens.get("space_3xs", 2)), 1)


def _project_workspace_button_target_width(button) -> int:
    tokens = app_theme_tokens()
    horizontal_padding = (int(tokens.get("space_xxs", 4)) * 2) + (int(tokens.get("space_3xs", 2)) * 2)
    try:
        text_width = button.fontMetrics().horizontalAdvance(str(button.text() or "").strip())
        compact_floor = _project_workspace_button_height() + (int(tokens.get("space_3xs", 2)) * 2)
        return max(text_width + horizontal_padding, compact_floor, 1)
    except Exception:
        return max(_project_workspace_button_height() + horizontal_padding, 1)


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


def _set_compact_button_chrome(button, *, width=0):
    button.setFixedHeight(_project_workspace_button_height())
    if width:
        button.setFixedWidth(int(width))
    button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
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
        self._current_display_count = 0
        self._has_project_dirty = False
        self._project_dirty_reason = ""
        self._current_view_name = ""
        self._workspace_snapshot_initialized = False
        self._init_ui()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.StyleChange, QEvent.FontChange):
            self._sync_button_metrics()

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
        self._title_label.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        header_layout.addWidget(self._title_label)

        self._subtitle_label = QLabel("Page navigation, startup flow, and visual scan.", self._header)
        self._subtitle_label.setObjectName("workspace_section_subtitle")
        self._subtitle_label.hide()

        self._metrics_frame = QFrame(self._header)
        self._metrics_frame.setObjectName("project_workspace_metrics_strip")
        self._metrics_frame.hide()
        self._metrics_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        metrics_layout = QHBoxLayout(self._metrics_frame)
        metrics_layout.setContentsMargins(0, 0, 0, 0)
        metrics_layout.setSpacing(_PROJECT_WORKSPACE_METRICS_SPACING)

        self._view_chip = QLabel("List view", self._metrics_frame)
        self._view_chip.setObjectName("workspace_status_chip")
        self._view_chip.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._view_chip.hide()
        metrics_layout.addWidget(self._view_chip)

        self._page_count_chip = QLabel("0 pages", self._metrics_frame)
        self._page_count_chip.setObjectName("workspace_status_chip")
        self._page_count_chip.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._page_count_chip.hide()
        metrics_layout.addWidget(self._page_count_chip)

        self._dirty_chip = QLabel("Clean", self._metrics_frame)
        self._dirty_chip.setObjectName("workspace_status_chip")
        self._dirty_chip.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._dirty_chip.hide()
        metrics_layout.addWidget(self._dirty_chip)

        self._display_target_chip = QLabel("Display 0", self._metrics_frame)
        self._display_target_chip.setObjectName("workspace_status_chip")
        self._display_target_chip.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._display_target_chip.hide()
        metrics_layout.addWidget(self._display_target_chip)

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
        self._settings_btn = QPushButton("Prefs")
        self._settings_btn.setObjectName("project_workspace_view_button")
        self._settings_btn.clicked.connect(self._toggle_project_settings)
        _set_widget_metadata(
            self._settings_btn,
            tooltip="Show or hide low-frequency project settings.",
            accessible_name="Project settings button",
        )
        self._list_btn = QPushButton("List")
        self._list_btn.setObjectName("project_workspace_view_button")
        self._list_btn.setCheckable(True)
        _set_widget_metadata(
            self._list_btn,
            tooltip="Show the page list for structure-first editing.",
            accessible_name="Workspace view button: List. Structure first.",
        )
        self._thumb_btn = QPushButton("Thumbs")
        self._thumb_btn.setObjectName("project_workspace_view_button")
        self._thumb_btn.setCheckable(True)
        _set_widget_metadata(
            self._thumb_btn,
            tooltip="Show page thumbnails for a visual scan.",
            accessible_name="Workspace view button: Thumbnails. Visual scan.",
        )
        self._sync_button_metrics()
        self._button_group.addButton(self._list_btn)
        self._button_group.addButton(self._thumb_btn)
        self._list_btn.clicked.connect(lambda: self.set_view(self.VIEW_LIST))
        self._thumb_btn.clicked.connect(lambda: self.set_view(self.VIEW_THUMBNAILS))
        header_layout.addWidget(self._metrics_frame, 1)
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

    def _sync_button_metrics(self):
        for button in (getattr(self, "_settings_btn", None), getattr(self, "_list_btn", None), getattr(self, "_thumb_btn", None)):
            if button is None:
                continue
            _set_compact_button_chrome(button, width=_project_workspace_button_target_width(button))

    def _update_panel_metadata(self):
        is_thumbnail_view = self._current_view_name == self.VIEW_THUMBNAILS
        view_summary_label = "Thumbnails" if is_thumbnail_view else "List view"
        view_chip_label = "Thumbs" if is_thumbnail_view else "List"
        page_label = f"{self._current_page_count} page" if self._current_page_count == 1 else f"{self._current_page_count} pages"
        active_text = self._current_active_page or "none"
        startup_text = self._current_startup_page or "none"
        dirty_count = int(self._current_dirty_pages or 0)
        display_count = max(int(self._current_display_count or 0), 0)
        has_project_dirty = bool(self._has_project_dirty)
        project_dirty_reason = str(self._project_dirty_reason or "").strip()
        project_dirty_suffix = f" ({project_dirty_reason})" if project_dirty_reason else ""
        multi_display = display_count > 1
        display_count_text = f"{display_count} display" if display_count == 1 else f"{display_count} displays"
        display_scope_text = (
            f"{display_count_text}; editing and preview target the primary display"
            if multi_display
            else ""
        )
        display_chip_text = "Primary" if multi_display else "Display 0"
        display_chip_summary = "Display target: Display 0. Editing and preview use the primary display."
        if dirty_count == 0 and not has_project_dirty:
            dirty_text = "No dirty pages"
            summary_dirty_text = "Clean"
            chip_text = "Clean"
        elif dirty_count == 0:
            dirty_text = f"Project changes pending{project_dirty_suffix}"
            summary_dirty_text = dirty_text
            chip_text = "Project"
        elif has_project_dirty:
            dirty_pages_text = f"{dirty_count} dirty page" if dirty_count == 1 else f"{dirty_count} dirty pages"
            dirty_text = f"{dirty_pages_text} + project changes{project_dirty_suffix}"
            summary_dirty_text = dirty_text
            chip_text = f"{dirty_count} dirty + proj"
        else:
            dirty_text = f"{dirty_count} dirty page" if dirty_count == 1 else f"{dirty_count} dirty pages"
            summary_dirty_text = dirty_text
            chip_text = f"{dirty_count} dirty"
        if multi_display:
            summary = (
                f"Project workspace: {view_summary_label}. "
                f"Pages: {page_label}. Active page: {active_text}. Startup page: {startup_text}. "
                f"Dirty state: {dirty_text}. Display scope: {display_scope_text}."
            )
            view_chip_text = view_chip_label
            view_chip_summary = (
                f"Workspace view: {view_summary_label}. Multi-display project: editing and preview use the primary display."
            )
            metrics_summary = (
                f"Project workspace metrics: {page_label}. {dirty_text}. Display scope: {display_scope_text}."
            )
            meta_parts = [
                f"Startup: {startup_text}",
                display_count_text,
                "Editing/preview: primary display only",
            ]
        else:
            summary = (
                f"Project workspace: {view_summary_label}. "
                f"Pages: {page_label}. Active page: {active_text}. Startup page: {startup_text}. Dirty state: {dirty_text}."
            )
            view_chip_text = view_chip_label
            view_chip_summary = f"Workspace view: {view_summary_label}."
            metrics_summary = f"Project workspace metrics: {page_label}. {dirty_text}."
            meta_parts = [f"Startup: {startup_text}"]
        self._view_chip.setText(view_chip_text)
        self._page_count_chip.setText(page_label)
        self._dirty_chip.setText(chip_text)
        self._display_target_chip.setText(display_chip_text)
        self._display_target_chip.setVisible(multi_display)
        self._summary_label.setText(f"{page_label}. Active: {active_text}. {summary_dirty_text}.")
        self._meta_label.setText(" | ".join(meta_parts))

        _set_widget_metadata(self, tooltip=summary, accessible_name=summary)
        _set_widget_metadata(
            self._header,
            tooltip=f"Project workspace header. {summary}",
            accessible_name=f"Project workspace header. {summary}",
        )
        _set_widget_metadata(
            self._title_label,
            tooltip=summary,
            accessible_name=f"Project Workspace. {view_summary_label}.",
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
            tooltip=view_chip_summary,
            accessible_name=view_chip_summary,
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
            self._display_target_chip,
            tooltip=display_chip_summary,
            accessible_name=display_chip_summary,
        )
        _set_widget_metadata(
            self._metrics_frame,
            tooltip=metrics_summary,
            accessible_name=metrics_summary,
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
        display_count=0,
        project_dirty=False,
        project_dirty_reason="",
    ):
        pages = max(int(page_count or 0), 0)
        dirty = max(int(dirty_pages or 0), 0)
        displays = max(int(display_count or 0), 0)
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
            and self._current_display_count == displays
            and self._has_project_dirty == has_project_dirty
            and self._project_dirty_reason == dirty_reason
        ):
            return
        self._current_page_count = pages
        self._current_active_page = normalized_active
        self._current_startup_page = normalized_startup
        self._current_dirty_pages = dirty
        self._current_display_count = displays
        self._has_project_dirty = has_project_dirty
        self._project_dirty_reason = dirty_reason
        self._workspace_snapshot_initialized = True
        self._update_panel_metadata()
