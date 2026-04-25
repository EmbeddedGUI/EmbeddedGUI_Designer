"""Project Explorer dock — lists pages and resources.

Provides a tree view showing:
  Pages/
    main_page
    settings_page
  Resources/
    images/
    fonts/

Context menus allow adding, deleting, renaming, and copying pages,
as well as setting the startup page.
"""

import os
from PyQt5.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem,
    QMenu, QAction, QInputDialog, QMessageBox, QLabel, QHBoxLayout,
    QPushButton, QComboBox, QFrame,
)
from PyQt5.QtCore import QEvent, pyqtSignal, Qt

from .theme import app_theme_tokens, designer_ui_font

# Page names that collide with egui internal module names.
# A page named "test" generates egui_test_init() which conflicts with
# src/test/egui_test.h's egui_test_init(void).
_RESERVED_PAGE_NAMES = {
    "activity", "animation", "api", "background", "canvas", "common",
    "config", "core", "dialog", "display_driver", "dlist", "fixmath",
    "focus", "font", "i18n", "image", "input", "interpolator",
    "key_event", "mask", "motion_event", "oop", "page_base", "pfb_manager",
    "platform", "region", "resource", "rotation", "scroller", "shadow",
    "sprite", "slist", "style", "test", "theme", "timer", "toast",
    "touch_driver", "utils", "view",
}


def _set_widget_metadata(widget, *, tooltip=None, accessible_name=None):
    if tooltip is not None:
        hint = str(tooltip or "")
        if str(widget.property("_project_dock_hint_snapshot") or "") != hint:
            widget.setToolTip(hint)
            widget.setStatusTip(hint)
            widget.setProperty("_project_dock_hint_snapshot", hint)
    if accessible_name is not None:
        name = str(accessible_name or "")
        if str(widget.property("_project_dock_accessible_snapshot") or "") != name:
            widget.setAccessibleName(name)
            widget.setProperty("_project_dock_accessible_snapshot", name)


def _set_action_metadata(action, tooltip):
    action.setToolTip(tooltip)
    action.setStatusTip(tooltip)


def _combo_content_width(combo) -> int:
    labels = [
        str(combo.itemText(index) or "").strip()
        for index in range(combo.count())
    ]
    labels = [label for label in labels if label]
    if not labels:
        labels = [str(combo.currentText() or "").strip() or "No project"]
    tokens = app_theme_tokens()
    horizontal_padding = (
        int(tokens.get("space_sm", 8))
        + int(tokens.get("icon_sm", 14))
        + (int(tokens.get("pad_input_h", 6)) * 2)
    )
    try:
        widest = max(combo.fontMetrics().horizontalAdvance(label) for label in labels)
        return max(widest + horizontal_padding, 1)
    except Exception:
        return max(int(tokens.get("h_tab_min", 24)) * 4, 1)


def _button_content_width(button) -> int:
    tokens = app_theme_tokens()
    horizontal_padding = int(tokens.get("space_md", 12)) + int(tokens.get("space_sm", 8))
    try:
        label_width = button.fontMetrics().horizontalAdvance(str(button.text() or "").strip())
        return max(label_width + horizontal_padding, 1)
    except Exception:
        return max(int(tokens.get("h_tab_min", 24)) * 3, 1)


class ProjectExplorerDock(QDockWidget):
    """Dock widget showing project pages and resources.

    Signals:
        page_selected(str):    page name selected (filename without ext)
        page_added(str):       new page name
        page_duplicated(str,str): (source_name, new page name)
        page_removed(str):     removed page name
        page_renamed(str,str): (old_name, new_name)
        startup_changed(str):  new startup page name
        page_mode_changed(str): "easy_page" or "activity"
    """

    page_selected = pyqtSignal(str)
    page_added = pyqtSignal(str)
    page_duplicated = pyqtSignal(str, str)
    page_removed = pyqtSignal(str)
    page_renamed = pyqtSignal(str, str)
    startup_changed = pyqtSignal(str)
    page_mode_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__("Project Explorer", parent)
        self.setAllowedAreas(Qt.AllDockWidgetAreas)

        self._project = None
        self._current_page_name = None
        self._dirty_pages = set()
        self._compact_mode = False
        self._init_ui()

    def set_compact_mode(self, compact=True):
        compact = bool(compact)
        self._compact_mode = compact
        if hasattr(self, "_header_frame"):
            self._header_frame.setVisible(not compact)
        if hasattr(self, "_settings_group"):
            self._settings_group.setVisible(not compact)
        if hasattr(self, "_page_tree"):
            self._apply_page_tree_font(compact=compact)
            self.refresh_tree_typography()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.StyleChange, QEvent.PaletteChange):
            self._apply_page_tree_font(compact=self._compact_mode)
            self.refresh_tree_typography()
            self._sync_minimum_width()
        elif event.type() == QEvent.FontChange:
            self.refresh_tree_typography()
            self._sync_minimum_width()

    def _init_ui(self):
        container = QWidget()
        container.setObjectName("project_dock_shell")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self._header_frame = QFrame()
        self._header_frame.setObjectName("project_dock_header")
        header_layout = QVBoxLayout(self._header_frame)
        header_layout.setContentsMargins(2, 2, 2, 2)
        header_layout.setSpacing(2)

        self._title_label = QLabel("Project")
        self._title_label.setObjectName("project_dock_title")
        _set_widget_metadata(
            self._title_label,
            tooltip="Project panel title.",
            accessible_name="Project panel title.",
        )
        header_layout.addWidget(self._title_label)

        self._subtitle_label = QLabel("Pages and startup settings")
        self._subtitle_label.setObjectName("project_dock_subtitle")
        self._subtitle_label.setWordWrap(True)
        _set_widget_metadata(
            self._subtitle_label,
            tooltip=self._subtitle_label.text(),
            accessible_name=self._subtitle_label.text(),
        )
        header_layout.addWidget(self._subtitle_label)

        self._status_label = QLabel("")
        self._status_label.setObjectName("project_dock_status")
        self._status_label.setWordWrap(True)
        header_layout.addWidget(self._status_label)

        layout.addWidget(self._header_frame)

        self._settings_group = QFrame()
        self._settings_group.setObjectName("project_dock_settings_group")
        self._settings_group.setAccessibleName("Project settings")
        settings_layout = QVBoxLayout(self._settings_group)
        settings_layout.setContentsMargins(0, 0, 0, 0)
        settings_layout.setSpacing(2)

        # Page mode selector
        mode_layout = QHBoxLayout()
        mode_layout.setContentsMargins(0, 0, 0, 0)
        mode_layout.setSpacing(2)
        self._mode_label = QLabel("Mode")
        _set_widget_metadata(
            self._mode_label,
            tooltip="Project page generation mode.",
            accessible_name="Page mode label",
        )
        self._mode_label.setObjectName("project_dock_field_label")
        mode_layout.addWidget(self._mode_label)
        self._mode_combo = QComboBox()
        self._mode_combo.setObjectName("project_dock_mode_combo")
        self._mode_combo.addItems(["easy_page", "activity"])
        self._mode_combo.currentTextChanged.connect(self._on_mode_changed)
        mode_layout.addWidget(self._mode_combo)
        settings_layout.addLayout(mode_layout)

        metrics_row = QHBoxLayout()
        metrics_row.setContentsMargins(0, 0, 0, 0)
        metrics_row.setSpacing(2)

        self._display_metric_card = QFrame()
        self._display_metric_card.setObjectName("project_dock_metric_card")
        display_metric_layout = QVBoxLayout(self._display_metric_card)
        display_metric_layout.setContentsMargins(0, 0, 0, 0)
        display_metric_layout.setSpacing(2)
        self._display_metric_label = QLabel("Displays")
        self._display_metric_label.setObjectName("project_dock_field_label")
        self._display_metric_value = QLabel("No project")
        self._display_metric_value.setObjectName("project_dock_metric_value")
        self._display_metric_value.setWordWrap(True)
        display_metric_layout.addWidget(self._display_metric_label)
        display_metric_layout.addWidget(self._display_metric_value)
        metrics_row.addWidget(self._display_metric_card, 1)

        self._primary_metric_card = QFrame()
        self._primary_metric_card.setObjectName("project_dock_metric_card")
        primary_metric_layout = QVBoxLayout(self._primary_metric_card)
        primary_metric_layout.setContentsMargins(0, 0, 0, 0)
        primary_metric_layout.setSpacing(2)
        self._primary_metric_label = QLabel("Primary")
        self._primary_metric_label.setObjectName("project_dock_field_label")
        self._primary_metric_value = QLabel("Not set")
        self._primary_metric_value.setObjectName("project_dock_metric_value")
        self._primary_metric_value.setWordWrap(True)
        primary_metric_layout.addWidget(self._primary_metric_label)
        primary_metric_layout.addWidget(self._primary_metric_value)
        metrics_row.addWidget(self._primary_metric_card, 1)

        settings_layout.addLayout(metrics_row)

        self._display_detail_label = QLabel("Load or create a project to inspect displays.")
        self._display_detail_label.setObjectName("project_dock_metric_value")
        self._display_detail_label.setWordWrap(True)
        settings_layout.addWidget(self._display_detail_label)

        display_target_layout = QHBoxLayout()
        display_target_layout.setContentsMargins(0, 0, 0, 0)
        display_target_layout.setSpacing(2)
        self._display_target_label = QLabel("Edit Target")
        self._display_target_label.setObjectName("project_dock_field_label")
        self._display_target_combo = QComboBox()
        self._display_target_combo.setObjectName("project_dock_display_target_combo")
        self._display_target_combo.setEnabled(False)
        display_target_layout.addWidget(self._display_target_label)
        display_target_layout.addWidget(self._display_target_combo, 1)
        settings_layout.addLayout(display_target_layout)
        layout.addWidget(self._settings_group)

        # Page tree
        self._pages_label = QLabel("Pages")
        self._pages_label.setObjectName("workspace_section_title")
        layout.addWidget(self._pages_label)

        self._pages_hint = QLabel("Right click a page to rename, duplicate, set startup, or delete.")
        self._pages_hint.setObjectName("workspace_section_subtitle")
        self._pages_hint.setWordWrap(True)
        layout.addWidget(self._pages_hint)

        self._page_tree = QTreeWidget()
        self._page_tree.setObjectName("project_dock_tree")
        self._page_tree.setHeaderHidden(True)
        self._page_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self._page_tree.customContextMenuRequested.connect(self._on_page_context_menu)
        self._page_tree.currentItemChanged.connect(self._on_page_item_changed)
        self._apply_page_tree_font(compact=self._compact_mode)
        layout.addWidget(self._page_tree, 1)

        # Add page button
        self._add_page_button = QPushButton("New Page")
        self._add_page_button.setObjectName("project_dock_add_page_button")
        self._add_page_button.clicked.connect(self._on_add_page)
        layout.addWidget(self._add_page_button)

        self._subtitle_label.hide()
        self._status_label.hide()
        self._pages_hint.hide()

        self.setWidget(container)
        self._update_accessibility_summary()

    def _minimum_width_target(self) -> int:
        tokens = app_theme_tokens()
        row_spacing = 2
        row_widths = [
            self._mode_label.fontMetrics().horizontalAdvance(self._mode_label.text())
            + row_spacing
            + _combo_content_width(self._mode_combo),
            self._display_target_label.fontMetrics().horizontalAdvance(self._display_target_label.text())
            + row_spacing
            + _combo_content_width(self._display_target_combo),
            _button_content_width(self._add_page_button),
        ]
        token_floor = (int(tokens.get("h_tab_min", 24)) * 7) + int(tokens.get("space_xxs", 4))
        token_ceiling = (int(tokens.get("h_tab_min", 24)) * 10) + int(tokens.get("space_md", 12))
        return min(max(*row_widths, token_floor, 1), max(token_ceiling, token_floor, 1))

    def _sync_minimum_width(self):
        target_width = self._minimum_width_target()
        current_width = self.minimumWidth()
        managed_width = int(getattr(self, "_managed_minimum_width", 0) or 0)
        if current_width > managed_width:
            self._managed_minimum_width = target_width
            return
        if current_width == target_width:
            self._managed_minimum_width = target_width
            return
        self.setMinimumWidth(target_width)
        self._managed_minimum_width = target_width

    def _project_displays(self):
        if not self._project:
            return []

        displays = list(getattr(self._project, "displays", None) or [])
        if displays:
            return displays
        return [
            {
                "width": int(getattr(self._project, "screen_width", 240) or 240),
                "height": int(getattr(self._project, "screen_height", 320) or 320),
            }
        ]

    def _display_settings_summary(self):
        displays = self._project_displays()
        if not displays:
            return "No project", "Not set", "Load or create a project to inspect displays."

        display_count = len(displays)
        primary = displays[0]
        display_count_text = f"{display_count} display" if display_count == 1 else f"{display_count} displays"
        primary_text = f"{int(primary['width'])} x {int(primary['height'])}"
        if display_count == 1:
            detail_text = "Primary display only."
        else:
            secondary_parts = [
                f"{int(display.get('id', index))}: {int(display['width'])} x {int(display['height'])}"
                for index, display in enumerate(displays[1:], start=1)
            ]
            detail_text = (
                f"Secondary displays: {', '.join(secondary_parts)}. "
                "Editing/preview: primary display only."
            )
        return display_count_text, primary_text, detail_text

    def _display_target_selector_summary(self):
        displays = self._project_displays()
        if not displays:
            return ["No project"], 0, "Display target selector unavailable. Load or create a project to inspect displays."

        items = []
        for index, display in enumerate(displays):
            display_id = int(display.get("id", index))
            size_text = f"{int(display['width'])} x {int(display['height'])}"
            suffix = " (Primary)" if index == 0 else ""
            items.append(f"Display {display_id}: {size_text}{suffix}")

        primary = displays[0]
        primary_id = int(primary.get("id", 0))
        primary_size = f"{int(primary['width'])} x {int(primary['height'])}"
        if len(displays) == 1:
            summary = f"Display target selector: Display {primary_id}: {primary_size} (Primary)."
        else:
            summary = (
                f"Display target selector: Display {primary_id}: {primary_size} (Primary). "
                "Editing and preview are fixed to the primary display."
            )
        return items, 0, summary

    def _primary_display_scope_note(self):
        displays = self._project_displays()
        if len(displays) <= 1:
            return ""
        return " Editing/preview: primary display only."

    def _update_accessibility_summary(self):
        page_count = len(getattr(self._project, "pages", []) or [])
        page_label = f"{page_count} page" if page_count == 1 else f"{page_count} pages"
        current_page = self._current_page_name or "none"
        project_pages = getattr(self._project, "pages", []) or []
        startup_value = str(getattr(self._project, "startup_page", "") or "").strip()
        startup_page = startup_value if any(getattr(page, "name", None) == startup_value for page in project_pages) else "none"
        dirty_count = len(self._dirty_pages)
        dirty_label = "No dirty pages" if dirty_count == 0 else (f"{dirty_count} dirty page" if dirty_count == 1 else f"{dirty_count} dirty pages")
        mode = str(self._mode_combo.currentText() or "easy_page").strip() or "easy_page"
        display_count_text, primary_text, display_detail = self._display_settings_summary()
        display_scope_note = self._primary_display_scope_note()
        summary = f"Project Explorer: {page_label}. Current page: {current_page}. Startup page: {startup_page}. {dirty_label}.{display_scope_note}"
        settings_summary = (
            f"Project settings: {page_label}. Current mode: {mode}. "
            f"Displays: {display_count_text}. Primary canvas: {primary_text}. {display_detail}"
        )
        mode_hint = f"Choose how pages are generated for the current project. Current mode: {mode}."
        add_page_hint = self._new_page_action_hint()
        self._status_label.setText(f"Mode {mode} | Current {current_page}")
        self._display_metric_value.setText(display_count_text)
        self._primary_metric_value.setText(primary_text)
        self._display_detail_label.setText(display_detail)
        display_target_items, display_target_index, display_target_summary = self._display_target_selector_summary()
        self._display_target_combo.blockSignals(True)
        self._display_target_combo.clear()
        self._display_target_combo.addItems(display_target_items)
        self._display_target_combo.setCurrentIndex(max(int(display_target_index), 0))
        self._display_target_combo.setEnabled(False)
        self._display_target_combo.blockSignals(False)
        _set_widget_metadata(self, tooltip=summary, accessible_name=summary)
        _set_widget_metadata(
            self._header_frame,
            tooltip=f"Project explorer header. {summary}",
            accessible_name=f"Project explorer header. {summary}",
        )
        _set_widget_metadata(
            self._settings_group,
            tooltip=settings_summary,
            accessible_name=settings_summary,
        )
        _set_widget_metadata(
            self._mode_label,
            tooltip=mode_hint,
            accessible_name=f"Page mode label. Current mode: {mode}. {mode_hint}",
        )
        _set_widget_metadata(
            self._pages_label,
            tooltip=summary,
            accessible_name=f"Pages: {page_label}. Current page: {current_page}. Startup page: {startup_page}.{display_scope_note}",
        )
        _set_widget_metadata(
            self._page_tree,
            tooltip=summary,
            accessible_name=f"Project pages: {page_label}. Current page: {current_page}. Startup page: {startup_page}. {dirty_label}.{display_scope_note}",
        )
        _set_widget_metadata(
            self._mode_combo,
            tooltip=mode_hint,
            accessible_name=f"Project page mode: {mode}. {mode_hint}",
        )
        _set_widget_metadata(
            self._display_metric_label,
            tooltip="Display count label.",
            accessible_name="Display count label.",
        )
        _set_widget_metadata(
            self._display_metric_value,
            tooltip=f"Displays: {display_count_text}.",
            accessible_name=f"Displays: {display_count_text}.",
        )
        _set_widget_metadata(
            self._display_metric_card,
            tooltip=f"Display count: {display_count_text}.",
            accessible_name=f"Display count: {display_count_text}.",
        )
        _set_widget_metadata(
            self._primary_metric_label,
            tooltip="Primary display label.",
            accessible_name="Primary display label.",
        )
        _set_widget_metadata(
            self._primary_metric_value,
            tooltip=f"Primary canvas: {primary_text}.",
            accessible_name=f"Primary canvas: {primary_text}.",
        )
        _set_widget_metadata(
            self._primary_metric_card,
            tooltip=f"Primary canvas: {primary_text}.",
            accessible_name=f"Primary canvas: {primary_text}.",
        )
        _set_widget_metadata(
            self._display_detail_label,
            tooltip=f"Display summary: {display_detail}",
            accessible_name=f"Display summary: {display_detail}",
        )
        _set_widget_metadata(
            self._display_target_label,
            tooltip="Edit target label.",
            accessible_name="Edit target label.",
        )
        _set_widget_metadata(
            self._display_target_combo,
            tooltip=display_target_summary,
            accessible_name=display_target_summary,
        )
        _set_widget_metadata(
            self._add_page_button,
            tooltip=add_page_hint,
            accessible_name=f"New page action: {mode} mode. {add_page_hint}",
        )
        status_summary = f"Project explorer status: mode {mode}. Current page: {current_page}"
        if display_scope_note:
            status_summary = f"{status_summary}.{display_scope_note}"
        _set_widget_metadata(
            self._status_label,
            tooltip=status_summary,
            accessible_name=status_summary,
        )
        self._sync_minimum_width()

    def _apply_page_item_metadata(self, item, page_name):
        item.setText(0, self._page_item_text(page_name))
        tooltip = self._page_item_tooltip(page_name)
        item.setToolTip(0, tooltip)
        item.setStatusTip(0, tooltip)
        item.setData(0, Qt.AccessibleTextRole, tooltip)

    def _new_page_action_hint(self):
        mode = str(self._mode_combo.currentText() or "easy_page").strip() or "easy_page"
        if self._project:
            return f"Create a new page in the current project. Current mode: {mode}."
        return f"Create the first page for a new project. Current mode: {mode}."

    def _page_item_tooltip(self, page_name):
        parts = [f"Page: {page_name}."]
        startup = self._project.startup_page if self._project else ""
        if page_name == startup:
            parts.append("Startup page.")
        if page_name == self._current_page_name:
            parts.append("Current page.")
        parts.append("Unsaved changes." if page_name in self._dirty_pages else "No unsaved changes.")
        return " ".join(parts)

    def _page_item_font(self, is_current=False):
        font = self._page_tree.font()
        font.setBold(bool(is_current))
        return font

    def _apply_page_tree_font(self, compact=False):
        tokens = app_theme_tokens()
        key = "fs_body_sm" if compact else "fs_body"
        fallback = 12 if compact else 13
        try:
            px = max(int(tokens.get(key, fallback)), 1)
        except (TypeError, ValueError):
            px = fallback
        font = designer_ui_font(pixel_size=px)
        self._page_tree.setFont(font)

    def _page_context_action_hint(self, action_key, page_name=""):
        page_label = str(page_name or "").strip() or "current page"
        startup = self._project.startup_page if self._project else ""
        if action_key == "rename":
            return f"Rename page: {page_label}."
        if action_key == "duplicate":
            return f"Duplicate page: {page_label}."
        if action_key == "startup":
            if page_label == startup:
                return f"Current startup page: {page_label}."
            return f"Set {page_label} as the startup page."
        if action_key == "delete":
            if self._project and len(getattr(self._project, "pages", []) or []) <= 1:
                return f"Cannot delete the last page: {page_label}."
            if page_label in self._dirty_pages:
                return f"Delete page: {page_label}. Unsaved changes will be lost."
            return f"Delete page: {page_label}. This cannot be undone."
        return self._new_page_action_hint()

    # ── Public API ─────────────────────────────────────────────────

    def set_project(self, project):
        """Refresh the explorer from the given Project."""
        self._project = project
        self._mode_combo.blockSignals(True)
        if project:
            self._mode_combo.setCurrentText(project.page_mode)
        else:
            self._mode_combo.setCurrentIndex(0)
        self._mode_combo.blockSignals(False)
        self._rebuild_page_tree()
        self._rebuild_resource_tree()
        self._update_accessibility_summary()

    def set_current_page(self, page_name):
        """Highlight the current page in the tree."""
        self._current_page_name = page_name
        for i in range(self._page_tree.topLevelItemCount()):
            item = self._page_tree.topLevelItem(i)
            name = item.data(0, Qt.UserRole)
            item.setFont(0, self._page_item_font(name == page_name))
            if name:
                self._apply_page_item_metadata(item, name)
        self._update_accessibility_summary()

    def refresh_tree_typography(self):
        """Re-apply page item emphasis using the current tree font."""
        for i in range(self._page_tree.topLevelItemCount()):
            item = self._page_tree.topLevelItem(i)
            name = item.data(0, Qt.UserRole)
            item.setFont(0, self._page_item_font(name == self._current_page_name))

    def set_dirty_pages(self, page_names):
        self._dirty_pages = set(page_names or [])
        for i in range(self._page_tree.topLevelItemCount()):
            item = self._page_tree.topLevelItem(i)
            name = item.data(0, Qt.UserRole)
            if name:
                self._apply_page_item_metadata(item, name)
        self._update_accessibility_summary()

    # ── Internal ───────────────────────────────────────────────────

    def _rebuild_page_tree(self):
        self._page_tree.clear()
        if not self._project:
            return
        for page in self._project.pages:
            name = page.name
            item = QTreeWidgetItem([self._page_item_text(name)])
            item.setData(0, Qt.UserRole, name)
            item.setFont(0, self._page_item_font(name == self._current_page_name))
            self._apply_page_item_metadata(item, name)
            self._page_tree.addTopLevelItem(item)

    def _page_item_text(self, page_name):
        startup = self._project.startup_page if self._project else ""
        dirty_suffix = "*" if page_name in self._dirty_pages else ""
        startup_suffix = " (startup)" if page_name == startup else ""
        return f"{page_name}{startup_suffix}{dirty_suffix}"

    def _rebuild_resource_tree(self):
        # Resources are managed by the independent ResourcePanel dock
        pass

    def _on_page_item_changed(self, current, previous):
        if current is None:
            return
        name = current.data(0, Qt.UserRole)
        if name:
            self.page_selected.emit(name)

    def _on_page_context_menu(self, pos):
        item = self._page_tree.itemAt(pos)
        menu = self._build_page_context_menu(item)
        menu.exec_(self._page_tree.viewport().mapToGlobal(pos))

    def _build_page_context_menu(self, item=None):
        menu = QMenu(self)
        menu.setToolTipsVisible(True)

        if item:
            name = item.data(0, Qt.UserRole)

            rename_act = QAction("Rename", self)
            _set_action_metadata(rename_act, self._page_context_action_hint("rename", name))
            rename_act.triggered.connect(lambda: self._rename_page(name))
            menu.addAction(rename_act)

            dup_act = QAction("Duplicate", self)
            _set_action_metadata(dup_act, self._page_context_action_hint("duplicate", name))
            dup_act.triggered.connect(lambda: self._duplicate_page(name))
            menu.addAction(dup_act)

            startup_act = QAction("Set as Startup Page", self)
            _set_action_metadata(startup_act, self._page_context_action_hint("startup", name))
            startup_act.triggered.connect(lambda: self._set_startup(name))
            menu.addAction(startup_act)

            menu.addSeparator()

            del_act = QAction("Delete", self)
            _set_action_metadata(del_act, self._page_context_action_hint("delete", name))
            del_act.triggered.connect(lambda: self._delete_page(name))
            menu.addAction(del_act)
            return menu

        add_act = QAction("New Page...", self)
        _set_action_metadata(add_act, self._new_page_action_hint())
        add_act.triggered.connect(self._on_add_page)
        menu.addAction(add_act)
        return menu

    def _on_add_page(self):
        name, ok = QInputDialog.getText(
            self, "New Page", "Page name (e.g. settings_page):"
        )
        if ok and name:
            # Sanitize: remove extension, replace spaces
            name = name.replace(" ", "_").replace(".xml", "")
            if name in _RESERVED_PAGE_NAMES:
                QMessageBox.warning(
                    self, "Reserved Name",
                    f"'{name}' is a reserved egui module name and cannot be used as a page name.\n"
                    f"Please choose a different name (e.g. '{name}_page')."
                )
                return
            if self._project and self._project.get_page_by_name(name):
                QMessageBox.warning(self, "Error", f"Page '{name}' already exists.")
                return
            self.page_added.emit(name)

    def _rename_page(self, old_name):
        new_name, ok = QInputDialog.getText(
            self, "Rename Page", "New name:", text=old_name
        )
        if ok and new_name and new_name != old_name:
            new_name = new_name.replace(" ", "_").replace(".xml", "")
            if new_name in _RESERVED_PAGE_NAMES:
                QMessageBox.warning(
                    self, "Reserved Name",
                    f"'{new_name}' is a reserved egui module name and cannot be used as a page name.\n"
                    f"Please choose a different name (e.g. '{new_name}_page')."
                )
                return
            if self._project and self._project.get_page_by_name(new_name):
                QMessageBox.warning(self, "Error", f"Page '{new_name}' already exists.")
                return
            self.page_renamed.emit(old_name, new_name)

    def _duplicate_page(self, name):
        new_name = f"{name}_copy"
        counter = 1
        while self._project and self._project.get_page_by_name(new_name):
            counter += 1
            new_name = f"{name}_copy{counter}"
        self.page_duplicated.emit(name, new_name)

    def _delete_page(self, name):
        if self._project and len(self._project.pages) <= 1:
            QMessageBox.warning(self, "Error", "Cannot delete the last page.")
            return
        reply = QMessageBox.question(
            self, "Delete Page",
            f"Delete page '{name}'? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.page_removed.emit(name)

    def _set_startup(self, name):
        self.startup_changed.emit(name)

    def _on_mode_changed(self, mode):
        self._update_accessibility_summary()
        self.page_mode_changed.emit(mode)
