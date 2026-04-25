"""Diagnostics dock widget for lightweight editor feedback."""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget

_SEVERITY_PREFIX = {
    "error": "Error",
    "warning": "Warning",
    "info": "Info",
}

_DEFAULT_HINT_TEXT = "Double-click a diagnostic to switch page or focus the widget."


def _format_entry_text(entry):
    scope = entry.page_name or "selection"
    widget = f"/{entry.widget_name}" if entry.widget_name else ""
    prefix = _SEVERITY_PREFIX.get(entry.severity, entry.severity.title())
    return f"[{prefix}] {scope}{widget}: {entry.message}"


def _activation_target(entry):
    target_page_name = str(getattr(entry, "target_page_name", "") or "")
    target_widget_name = str(getattr(entry, "target_widget_name", "") or "")
    page_name = str(getattr(entry, "page_name", "") or "")
    widget_name = str(getattr(entry, "widget_name", "") or "")
    if (target_page_name and target_widget_name) or page_name == "project":
        return target_page_name, target_widget_name
    if target_page_name and not widget_name:
        return target_page_name, ""
    return page_name or target_page_name, widget_name or target_widget_name


def _entry_key(entry):
    if entry is None:
        return None
    return (
        str(getattr(entry, "severity", "") or ""),
        str(getattr(entry, "code", "") or ""),
        str(getattr(entry, "message", "") or ""),
        str(getattr(entry, "page_name", "") or ""),
        str(getattr(entry, "widget_name", "") or ""),
        str(getattr(entry, "resource_type", "") or ""),
        str(getattr(entry, "resource_name", "") or ""),
        str(getattr(entry, "property_name", "") or ""),
        str(getattr(entry, "target_page_name", "") or ""),
        str(getattr(entry, "target_widget_name", "") or ""),
    )


def _is_navigable_entry(entry):
    page_name, _ = _activation_target(entry)
    return bool(page_name)


def _entry_location_label(entry):
    page_name = str(getattr(entry, "page_name", "") or "")
    widget_name = str(getattr(entry, "widget_name", "") or "")
    if page_name == "project":
        return "project"
    if page_name and widget_name:
        return f"{page_name}/{widget_name}"
    return page_name or widget_name or "selection"


class DiagnosticsPanel(QWidget):
    """Read-only list of diagnostics with optional widget focusing."""

    diagnostic_activated = pyqtSignal(str, str)  # page_name, widget_name
    copy_requested = pyqtSignal()
    copy_json_requested = pyqtSignal()
    export_requested = pyqtSignal()
    export_json_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._entries = []
        self._visible_entries = []
        self._activated_entry = None
        self._selection_anchor_key = None
        self._init_ui()
        self.clear()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self._header_frame = QFrame()
        self._header_frame.setObjectName("diagnostics_header")
        self._header_frame.setProperty("panelTone", "diagnostics")
        header_layout = QVBoxLayout(self._header_frame)
        header_layout.setContentsMargins(2, 2, 2, 2)
        header_layout.setSpacing(2)

        self._header_eyebrow = QLabel("Diagnostics")
        self._header_eyebrow.setObjectName("diagnostics_header_eyebrow")
        header_layout.addWidget(self._header_eyebrow)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(2)
        self._summary_label = QLabel("")
        self._summary_label.setObjectName("workspace_section_title")
        title_row.addWidget(self._summary_label, 1)

        self._visible_count_chip = QLabel("0 visible")
        self._visible_count_chip.setObjectName("workspace_status_chip")
        self._visible_count_chip.setProperty("chipTone", "accent")
        title_row.addWidget(self._visible_count_chip, 0, Qt.AlignVCenter)
        self._visible_count_chip.hide()

        self._filter_chip = QLabel("Any Severity")
        self._filter_chip.setObjectName("workspace_status_chip")
        title_row.addWidget(self._filter_chip, 0, Qt.AlignVCenter)
        self._filter_chip.hide()
        header_layout.addLayout(title_row)

        self._severity_filter_combo = QComboBox()
        self._severity_filter_combo.addItem("Any", "")
        self._severity_filter_combo.addItem("Error", "error")
        self._severity_filter_combo.addItem("Warning", "warning")
        self._severity_filter_combo.addItem("Info", "info")
        self._severity_filter_combo.currentIndexChanged.connect(self._apply_filter)
        self._reset_view_button = QPushButton("Reset")
        self._reset_view_button.clicked.connect(self._reset_view)
        self._open_selected_button = QPushButton("Open")
        self._open_selected_button.clicked.connect(self._open_selected)
        self._open_first_error_button = QPushButton("First Error")
        self._open_first_error_button.clicked.connect(self._open_first_error)
        self._open_first_warning_button = QPushButton("First Warn")
        self._open_first_warning_button.clicked.connect(self._open_first_warning)
        self._copy_button = QPushButton("Copy")
        self._copy_button.clicked.connect(self.copy_requested.emit)
        self._copy_json_button = QPushButton("Copy JSON")
        self._copy_json_button.clicked.connect(self.copy_json_requested.emit)
        self._export_button = QPushButton("Export")
        self._export_button.clicked.connect(self.export_requested.emit)
        self._export_json_button = QPushButton("Export JSON")
        self._export_json_button.clicked.connect(self.export_json_requested.emit)
        self._hint_label = QLabel(_DEFAULT_HINT_TEXT)
        self._hint_label.setObjectName("diagnostics_header_meta")
        self._hint_label.setWordWrap(True)
        header_layout.addWidget(self._hint_label)
        self._header_eyebrow.hide()
        self._hint_label.hide()

        self._list = QListWidget()
        self._list.setObjectName("diagnostics_list")
        self._list.setFocusPolicy(Qt.NoFocus)
        self._list.itemDoubleClicked.connect(self._on_item_activated)
        self._list.itemSelectionChanged.connect(self._update_selection_actions)

        self._controls_primary_strip = QFrame()
        self._controls_primary_strip.setObjectName("diagnostics_controls_strip")
        primary_layout = QHBoxLayout(self._controls_primary_strip)
        primary_layout.setContentsMargins(0, 0, 0, 0)
        primary_layout.setSpacing(2)
        primary_layout.addWidget(self._severity_filter_combo)
        primary_layout.addWidget(self._reset_view_button)
        primary_layout.addWidget(self._open_selected_button)
        primary_layout.addWidget(self._open_first_error_button)
        primary_layout.addWidget(self._open_first_warning_button)
        primary_layout.addStretch(1)
        header_layout.addWidget(self._controls_primary_strip)

        self._controls_secondary_strip = QFrame()
        self._controls_secondary_strip.setObjectName("diagnostics_export_strip")
        secondary_layout = QHBoxLayout(self._controls_secondary_strip)
        secondary_layout.setContentsMargins(0, 0, 0, 0)
        secondary_layout.setSpacing(2)
        secondary_layout.addWidget(self._copy_button)
        secondary_layout.addWidget(self._copy_json_button)
        secondary_layout.addWidget(self._export_button)
        secondary_layout.addWidget(self._export_json_button)
        secondary_layout.addStretch(1)
        header_layout.addWidget(self._controls_secondary_strip)

        layout.addWidget(self._header_frame)
        layout.addWidget(self._list, 1)

        self._reset_view_button.setAccessibleName("Reset diagnostics view")
        self._open_selected_button.setAccessibleName("Open selected diagnostic")
        self._open_first_error_button.setAccessibleName("Open first error diagnostic")
        self._open_first_warning_button.setAccessibleName("Open first warning diagnostic")
        self._copy_button.setAccessibleName("Copy diagnostics summary")
        self._copy_json_button.setAccessibleName("Copy diagnostics JSON")
        self._export_button.setAccessibleName("Export diagnostics summary")
        self._export_json_button.setAccessibleName("Export diagnostics JSON")

    def clear(self):
        self._entries = []
        self._visible_entries = []
        self._activated_entry = None
        self._selection_anchor_key = None
        self._summary_label.setText("Diagnostics: no active issues")
        self._hint_label.setText(_DEFAULT_HINT_TEXT)
        self._reset_view_button.setEnabled(bool(self._current_filter_value()))
        self._open_selected_button.setEnabled(False)
        self._open_first_error_button.setEnabled(False)
        self._open_first_warning_button.setEnabled(False)
        self._copy_button.setEnabled(False)
        self._copy_json_button.setEnabled(False)
        self._export_button.setEnabled(False)
        self._export_json_button.setEnabled(False)
        self._list.clear()
        self._update_accessibility_summary()

    def set_entries(self, entries):
        self._entries = list(entries or [])
        self._activated_entry = None
        self._apply_filter()

    def has_entries(self):
        return bool(self._visible_entries)

    def summary_text(self):
        if not self._entries:
            return self._summary_label.text()
        lines = [self._summary_label.text()]
        filter_value = self._current_filter_value()
        if filter_value:
            lines.append(f"Filter: {self._severity_filter_combo.currentText().lower()} ({len(self._visible_entries)} item(s))")
        if not self._visible_entries:
            return "\n".join(lines)
        return "\n".join(lines + [_format_entry_text(entry) for entry in self._visible_entries])

    def current_activated_entry(self):
        return self._activated_entry

    def current_selected_entry(self):
        item = self._list.currentItem()
        if item is None:
            return None
        return item.data(Qt.UserRole + 1)

    def set_severity_filter(self, severity):
        severity_value = str(severity or "")
        index = self._severity_filter_combo.findData(severity_value)
        self._severity_filter_combo.setCurrentIndex(index if index >= 0 else 0)

    def entries(self):
        return list(self._visible_entries)

    def severity_counts(self):
        return {
            "error": sum(1 for entry in self._entries if getattr(entry, "severity", "") == "error"),
            "warning": sum(1 for entry in self._entries if getattr(entry, "severity", "") == "warning"),
            "info": sum(1 for entry in self._entries if getattr(entry, "severity", "") == "info"),
        }

    def view_state(self):
        return {"severity_filter": self._current_filter_value()}

    def restore_view_state(self, state):
        view_state = state if isinstance(state, dict) else {}
        severity_value = str(view_state.get("severity_filter") or "")
        index = self._severity_filter_combo.findData(severity_value)
        self._severity_filter_combo.setCurrentIndex(index if index >= 0 else 0)

    def _set_widget_metadata(self, widget, *, tooltip=None, accessible_name=None):
        if tooltip is not None:
            hint = str(tooltip or "")
            if str(widget.property("_diagnostics_hint_snapshot") or "") != hint:
                widget.setToolTip(hint)
                widget.setStatusTip(hint)
                widget.setProperty("_diagnostics_hint_snapshot", hint)
        if accessible_name is not None:
            name = str(accessible_name or "")
            if str(widget.property("_diagnostics_accessible_snapshot") or "") != name:
                widget.setAccessibleName(name)
                widget.setProperty("_diagnostics_accessible_snapshot", name)

    def _count_label(self, count, singular, plural=None):
        value = max(int(count or 0), 0)
        noun = singular if value == 1 else (plural or f"{singular}s")
        return f"{value} {noun}"

    def _current_filter_label(self):
        return str(self._severity_filter_combo.currentText() or "Any")

    def _entry_tooltip(self, entry):
        prefix = _SEVERITY_PREFIX.get(getattr(entry, "severity", ""), str(getattr(entry, "severity", "") or "").title())
        page_name = str(getattr(entry, "page_name", "") or "")
        widget_name = str(getattr(entry, "widget_name", "") or "")
        if page_name == "project":
            location = "project"
        elif page_name and widget_name:
            location = f"{page_name}/{widget_name}"
        else:
            location = page_name or widget_name or "selection"
        navigation_hint = "Double-click to open." if _is_navigable_entry(entry) else "Navigation unavailable."
        return f"{prefix} diagnostic: {location}. {entry.message} {navigation_hint}"

    def _reset_view_hint(self):
        if self._current_filter_value():
            return "Reset the diagnostics filter and show every severity."
        return "Diagnostics already show every severity."

    def _open_selected_hint(self):
        current_item = self._list.currentItem()
        if current_item is None:
            return "Select a diagnostic to open its target."
        entry = current_item.data(Qt.UserRole + 1)
        if not _is_navigable_entry(entry):
            return "The selected diagnostic has no page or widget target to open."
        return "Open the selected diagnostic target."

    def _copy_summary_hint(self):
        if self._visible_entries:
            return "Copy the visible diagnostics as summary text."
        if self._entries and self._current_filter_value():
            return "No diagnostics match the current filter to copy."
        return "No diagnostics available to copy."

    def _copy_json_hint(self):
        if self._visible_entries:
            return "Copy the visible diagnostics as JSON."
        if self._entries and self._current_filter_value():
            return "No diagnostics match the current filter to copy as JSON."
        return "No diagnostics available to copy as JSON."

    def _export_summary_hint(self):
        if self._visible_entries:
            return "Export the visible diagnostics summary to a text file."
        if self._entries and self._current_filter_value():
            return "No diagnostics match the current filter to export."
        return "No diagnostics available to export."

    def _export_json_hint(self):
        if self._visible_entries:
            return "Export the visible diagnostics as JSON."
        if self._entries and self._current_filter_value():
            return "No diagnostics match the current filter to export as JSON."
        return "No diagnostics available to export as JSON."

    def _visible_items_accessible_label(self):
        return self._count_label(len(self._visible_entries), "visible item", "visible items")

    def _update_accessibility_summary(self):
        summary_text = str(self._summary_label.text() or "Diagnostics: no active issues").strip() or "Diagnostics: no active issues"
        hint_text = str(self._hint_label.text() or _DEFAULT_HINT_TEXT).strip() or _DEFAULT_HINT_TEXT
        filter_label = self._current_filter_label()
        visible_summary = self._count_label(len(self._visible_entries), "visible item", "visible items")
        panel_summary = f"{summary_text}. Severity filter: {filter_label}. {visible_summary}."
        list_summary = f"Diagnostics list: {visible_summary}. Severity filter: {filter_label}."
        filter_chip_text = "Any Severity" if filter_label == "Any" else f"{filter_label} Only"
        visible_chip_text = f"{len(self._visible_entries)} visible"
        if self._visible_entries:
            list_summary += " Double-click a diagnostic to open its target when available."
        current_item = self._list.currentItem()
        current_entry = current_item.data(Qt.UserRole + 1) if current_item is not None else None
        has_filter = bool(self._current_filter_value())
        has_navigable_error = self._first_navigable_error(self._entries) is not None
        has_navigable_warning = self._first_navigable_warning(self._entries) is not None
        can_open_selected = current_item is not None and _is_navigable_entry(current_entry)
        has_visible_entries = bool(self._visible_entries)
        first_error_entry = self._first_navigable_error(self._entries)
        first_warning_entry = self._first_navigable_warning(self._entries)
        selected_location = _entry_location_label(current_entry) if can_open_selected else ""
        visible_accessible_label = self._visible_items_accessible_label()

        self._visible_count_chip.setText(visible_chip_text)
        self._filter_chip.setText(filter_chip_text)

        self._set_widget_metadata(self, tooltip=panel_summary, accessible_name=panel_summary)
        self._set_widget_metadata(
            self._header_frame,
            tooltip=f"{summary_text}. {hint_text}",
            accessible_name=f"Diagnostics header. {panel_summary}",
        )
        self._set_widget_metadata(
            self._header_eyebrow,
            tooltip="Workspace diagnostics surface.",
            accessible_name="Workspace diagnostics surface.",
        )
        self._set_widget_metadata(self._summary_label, tooltip=summary_text, accessible_name=summary_text)
        self._set_widget_metadata(
            self._hint_label,
            tooltip=hint_text,
            accessible_name=f"Diagnostics hint: {hint_text}",
        )
        self._set_widget_metadata(
            self._visible_count_chip,
            tooltip=f"Visible diagnostics: {visible_summary}.",
            accessible_name=f"Visible diagnostics: {visible_summary}.",
        )
        self._set_widget_metadata(
            self._filter_chip,
            tooltip=f"Current severity scope: {filter_chip_text}.",
            accessible_name=f"Severity scope: {filter_chip_text}.",
        )
        self._set_widget_metadata(
            self._severity_filter_combo,
            tooltip=f"Filter diagnostics by severity. Current filter: {filter_label}.",
            accessible_name=f"Diagnostics severity filter: {filter_label}",
        )
        self._set_widget_metadata(
            self._reset_view_button,
            tooltip=self._reset_view_hint(),
            accessible_name=(
                f"Reset diagnostics view: {filter_label}"
                if has_filter
                else "Reset diagnostics view unavailable"
            ),
        )
        self._set_widget_metadata(
            self._open_selected_button,
            tooltip=self._open_selected_hint(),
            accessible_name=(
                f"Open selected diagnostic: {selected_location}"
                if can_open_selected
                else "Open selected diagnostic unavailable"
            ),
        )
        self._set_widget_metadata(
            self._open_first_error_button,
            tooltip=(
                "Open the first navigable error diagnostic."
                if has_navigable_error
                else "No navigable error diagnostics available."
            ),
            accessible_name=(
                f"Open first error diagnostic: {_entry_location_label(first_error_entry)}"
                if has_navigable_error
                else "Open first error diagnostic unavailable"
            ),
        )
        self._set_widget_metadata(
            self._open_first_warning_button,
            tooltip=(
                "Open the first navigable warning diagnostic."
                if has_navigable_warning
                else "No navigable warning diagnostics available."
            ),
            accessible_name=(
                f"Open first warning diagnostic: {_entry_location_label(first_warning_entry)}"
                if has_navigable_warning
                else "Open first warning diagnostic unavailable"
            ),
        )
        self._set_widget_metadata(
            self._copy_button,
            tooltip=self._copy_summary_hint(),
            accessible_name=(
                f"Copy diagnostics summary: {visible_accessible_label}"
                if has_visible_entries
                else "Copy diagnostics summary unavailable"
            ),
        )
        self._set_widget_metadata(
            self._copy_json_button,
            tooltip=self._copy_json_hint(),
            accessible_name=(
                f"Copy diagnostics JSON: {visible_accessible_label}"
                if has_visible_entries
                else "Copy diagnostics JSON unavailable"
            ),
        )
        self._set_widget_metadata(
            self._export_button,
            tooltip=self._export_summary_hint(),
            accessible_name=(
                f"Export diagnostics summary: {visible_accessible_label}"
                if has_visible_entries
                else "Export diagnostics summary unavailable"
            ),
        )
        self._set_widget_metadata(
            self._export_json_button,
            tooltip=self._export_json_hint(),
            accessible_name=(
                f"Export diagnostics JSON: {visible_accessible_label}"
                if has_visible_entries
                else "Export diagnostics JSON unavailable"
            ),
        )
        self._set_widget_metadata(
            self._controls_primary_strip,
            tooltip=f"Diagnostics actions: filter, reset, and open diagnostics. Current filter: {filter_label}.",
            accessible_name=f"Diagnostics primary actions. Current filter: {filter_label}.",
        )
        self._set_widget_metadata(
            self._controls_secondary_strip,
            tooltip=f"Diagnostics export actions. {visible_summary}.",
            accessible_name=f"Diagnostics export actions. {visible_summary}.",
        )
        self._set_widget_metadata(self._list, tooltip=list_summary, accessible_name=list_summary)

    def _current_filter_value(self):
        return str(self._severity_filter_combo.currentData() or "")

    def _apply_filter(self):
        selection_key = self._selection_anchor_key
        self._list.clear()
        self._visible_entries = [
            entry for entry in self._entries
            if not self._current_filter_value() or entry.severity == self._current_filter_value()
        ]
        self._reset_view_button.setEnabled(bool(self._current_filter_value()))
        self._open_first_error_button.setEnabled(self._first_navigable_error(self._entries) is not None)
        self._open_first_warning_button.setEnabled(self._first_navigable_warning(self._entries) is not None)
        self._copy_button.setEnabled(bool(self._visible_entries))
        self._copy_json_button.setEnabled(bool(self._visible_entries))
        self._export_button.setEnabled(bool(self._visible_entries))
        self._export_json_button.setEnabled(bool(self._visible_entries))

        if not self._entries:
            self._summary_label.setText("Diagnostics: no active issues")
            self._hint_label.setText(_DEFAULT_HINT_TEXT)
            self._selection_anchor_key = None
            self._open_selected_button.setEnabled(False)
            self._update_accessibility_summary()
            return

        errors = sum(1 for entry in self._entries if entry.severity == "error")
        warnings = sum(1 for entry in self._entries if entry.severity == "warning")
        infos = sum(1 for entry in self._entries if entry.severity == "info")
        self._summary_label.setText(f"Diagnostics: {errors} error(s), {warnings} warning(s), {infos} info item(s)")
        if self._visible_entries:
            self._hint_label.setText(_DEFAULT_HINT_TEXT)
        else:
            self._hint_label.setText("No diagnostics match the current severity filter.")

        for entry in self._visible_entries:
            item = QListWidgetItem(_format_entry_text(entry))
            item.setData(Qt.UserRole, _activation_target(entry))
            item.setData(Qt.UserRole + 1, entry)
            item_tooltip = self._entry_tooltip(entry)
            item.setToolTip(item_tooltip)
            item.setStatusTip(item_tooltip)
            item.setData(Qt.AccessibleTextRole, item_tooltip)
            self._list.addItem(item)
        self._restore_selection(selection_key)
        self._update_selection_actions()

    def _reset_view(self):
        self._severity_filter_combo.setCurrentIndex(0)

    def _update_selection_actions(self):
        current_item = self._list.currentItem()
        current_entry = current_item.data(Qt.UserRole + 1) if current_item is not None else None
        if current_item is not None:
            self._selection_anchor_key = _entry_key(current_entry)
        self._open_selected_button.setEnabled(current_item is not None and _is_navigable_entry(current_entry))
        self._update_accessibility_summary()

    def _restore_selection(self, selection_key):
        if selection_key is None:
            self._list.clearSelection()
            self._list.setCurrentRow(-1)
            return
        for row in range(self._list.count()):
            item = self._list.item(row)
            if _entry_key(item.data(Qt.UserRole + 1)) == selection_key:
                self._list.setCurrentItem(item)
                return
        self._list.clearSelection()
        self._list.setCurrentRow(-1)

    def _first_navigable_error(self, entries):
        for entry in entries or []:
            if getattr(entry, "severity", "") == "error" and _is_navigable_entry(entry):
                return entry
        return None

    def _first_navigable_warning(self, entries):
        for entry in entries or []:
            if getattr(entry, "severity", "") == "warning" and _is_navigable_entry(entry):
                return entry
        return None

    def _open_first_error(self):
        target_entry = self._first_navigable_error(self._entries)
        if target_entry is None:
            return
        if self._current_filter_value() != "error":
            error_index = self._severity_filter_combo.findData("error")
            if error_index >= 0:
                self._severity_filter_combo.setCurrentIndex(error_index)
        for row in range(self._list.count()):
            item = self._list.item(row)
            if item.data(Qt.UserRole + 1) is target_entry:
                self._list.setCurrentItem(item)
                self._on_item_activated(item)
                return

    def open_first_error(self):
        self._open_first_error()

    def _open_first_warning(self):
        target_entry = self._first_navigable_warning(self._entries)
        if target_entry is None:
            return
        if self._current_filter_value() != "warning":
            warning_index = self._severity_filter_combo.findData("warning")
            if warning_index >= 0:
                self._severity_filter_combo.setCurrentIndex(warning_index)
        for row in range(self._list.count()):
            item = self._list.item(row)
            if item.data(Qt.UserRole + 1) is target_entry:
                self._list.setCurrentItem(item)
                self._on_item_activated(item)
                return

    def open_first_warning(self):
        self._open_first_warning()

    def _open_selected(self):
        item = self._list.currentItem()
        if item is None:
            return
        entry = item.data(Qt.UserRole + 1)
        if not _is_navigable_entry(entry):
            return
        self._on_item_activated(item)

    def _on_item_activated(self, item):
        self._activated_entry = item.data(Qt.UserRole + 1)
        self._selection_anchor_key = _entry_key(self._activated_entry)
        if not _is_navigable_entry(self._activated_entry):
            return
        page_name, widget_name = item.data(Qt.UserRole) or ("", "")
        self.diagnostic_activated.emit(page_name or "", widget_name or "")
