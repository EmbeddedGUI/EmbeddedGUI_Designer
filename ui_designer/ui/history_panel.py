"""History dock widget for undo/redo visualization."""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QLabel, QListWidget, QListWidgetItem, QVBoxLayout, QWidget, QHBoxLayout

from .iconography import make_icon


class HistoryPanel(QWidget):
    """Read-only panel that visualizes the current page undo stack."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self.clear()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)

        page_icon = QLabel()
        page_icon.setPixmap(make_icon("history", size=20).pixmap(20, 20))
        top_row.addWidget(page_icon, 0, Qt.AlignTop)

        self._page_value = QLabel("")
        self._page_value.setObjectName("workspace_section_title")
        top_row.addWidget(self._page_value, 1)
        layout.addLayout(top_row)

        self._stack_value = QLabel("")
        self._stack_value.setObjectName("workspace_status_chip")
        self._dirty_value = QLabel("")
        self._dirty_value.setObjectName("workspace_status_chip")
        self._source_value = QLabel("")
        self._source_value.setObjectName("workspace_section_subtitle")
        self._history_list = QListWidget()
        self._history_list.setSelectionMode(QListWidget.NoSelection)
        self._history_list.setFocusPolicy(Qt.NoFocus)
        self._history_list.setAccessibleName("History entries")

        layout.addWidget(self._stack_value)
        layout.addWidget(self._dirty_value)
        layout.addWidget(self._source_value)
        layout.addWidget(self._history_list, 1)

    def _set_label_metadata(self, widget, *, tooltip, accessible_name):
        widget.setToolTip(tooltip)
        widget.setStatusTip(tooltip)
        widget.setAccessibleName(accessible_name)

    def _current_entry_label(self, entries):
        for entry in entries or []:
            if entry.get("is_current"):
                return str(entry.get("label") or "State capture")
        return "none"

    def _update_accessibility_summary(
        self,
        *,
        page_name,
        entry_count,
        dirty,
        dirty_source,
        can_undo=False,
        can_redo=False,
        current_entry="none",
    ):
        summary = (
            f"History panel: Page {page_name}. {entry_count} entries. "
            f"Dirty {'yes' if dirty else 'no'}. Source {dirty_source}."
        )
        self.setAccessibleName(summary)
        self.setToolTip(summary)
        self.setStatusTip(summary)
        self._set_label_metadata(
            self._page_value,
            tooltip=f"History page: {page_name}",
            accessible_name=f"History page: {page_name}",
        )
        self._set_label_metadata(
            self._stack_value,
            tooltip=f"History entries: {entry_count}. Undo: {'Yes' if can_undo else 'No'}. Redo: {'Yes' if can_redo else 'No'}.",
            accessible_name=f"History summary: {entry_count} entries. Undo {'yes' if can_undo else 'no'}. Redo {'yes' if can_redo else 'no'}.",
        )
        self._set_label_metadata(
            self._dirty_value,
            tooltip=f"History dirty state: {'Yes' if dirty else 'No'}",
            accessible_name=f"History dirty state: {'Yes' if dirty else 'No'}",
        )
        self._set_label_metadata(
            self._source_value,
            tooltip=f"History source: {dirty_source}",
            accessible_name=f"History source: {dirty_source}",
        )
        list_tooltip = f"History entries: {entry_count} items for page {page_name}. Current entry: {current_entry}."
        self._history_list.setToolTip(list_tooltip)
        self._history_list.setStatusTip(list_tooltip)
        self._history_list.setAccessibleName(
            f"History entries for {page_name}: {entry_count} items. Current entry: {current_entry}"
        )

    def clear(self):
        self._page_value.setText("Page: -")
        self._stack_value.setText("History: 0 entries")
        self._dirty_value.setText("Dirty: No")
        self._source_value.setText("Source: Saved state")
        self._dirty_value.setProperty("chipTone", "success")
        self._history_list.clear()
        self._update_accessibility_summary(
            page_name="-",
            entry_count=0,
            dirty=False,
            dirty_source="Saved state",
            current_entry="none",
        )

    def set_history(self, page_name, entries, dirty=False, dirty_source="", can_undo=False, can_redo=False):
        page_name = page_name or "-"
        dirty = bool(dirty)
        entries = list(entries or [])

        self._page_value.setText(f"Page: {page_name}")
        self._stack_value.setText(
            f"History: {len(entries)} entries | Undo: {'Yes' if can_undo else 'No'} | Redo: {'Yes' if can_redo else 'No'}"
        )
        self._dirty_value.setText(f"Dirty: {'Yes' if dirty else 'No'}")
        self._source_value.setText(f"Source: {dirty_source or 'Saved state'}")
        self._dirty_value.setProperty("chipTone", "warning" if dirty else "success")
        self._dirty_value.style().unpolish(self._dirty_value)
        self._dirty_value.style().polish(self._dirty_value)
        self._update_accessibility_summary(
            page_name=page_name,
            entry_count=len(entries),
            dirty=dirty,
            dirty_source=dirty_source or "Saved state",
            can_undo=can_undo,
            can_redo=can_redo,
            current_entry=self._current_entry_label(entries),
        )

        self._history_list.clear()
        for entry in reversed(entries):
            markers = []
            if entry.get("is_current"):
                markers.append("Current")
            if entry.get("is_saved"):
                markers.append("Saved")

            marker_prefix = f"[{'/'.join(markers)}] " if markers else ""
            label = entry.get("label") or "State capture"
            item = QListWidgetItem(f"{marker_prefix}{entry.get('index', 0) + 1}. {label}")
            icon_key = "history"
            if entry.get("is_current"):
                icon_key = "navigation"
            elif entry.get("is_saved"):
                icon_key = "save"
            item.setIcon(make_icon(icon_key, size=16))
            marker_summary = ". ".join(markers) + ". " if markers else ""
            item_tooltip = f"History entry {entry.get('index', 0) + 1}. {marker_summary}{label}"
            item.setToolTip(item_tooltip)
            item.setStatusTip(item_tooltip)
            item.setData(Qt.AccessibleTextRole, item_tooltip)
            self._history_list.addItem(item)
