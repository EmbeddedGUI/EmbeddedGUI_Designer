"""Diagnostics dock widget for lightweight editor feedback."""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QComboBox, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget


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
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self._summary_label = QLabel("")
        self._severity_filter_combo = QComboBox()
        self._severity_filter_combo.addItem("Any", "")
        self._severity_filter_combo.addItem("Errors", "error")
        self._severity_filter_combo.addItem("Warnings", "warning")
        self._severity_filter_combo.addItem("Info", "info")
        self._severity_filter_combo.currentIndexChanged.connect(self._apply_filter)
        self._reset_view_button = QPushButton("Reset View")
        self._reset_view_button.clicked.connect(self._reset_view)
        self._open_selected_button = QPushButton("Open Selected")
        self._open_selected_button.clicked.connect(self._open_selected)
        self._open_first_error_button = QPushButton("Open First Error")
        self._open_first_error_button.clicked.connect(self._open_first_error)
        self._open_first_warning_button = QPushButton("Open First Warning")
        self._open_first_warning_button.clicked.connect(self._open_first_warning)
        self._copy_button = QPushButton("Copy Summary")
        self._copy_button.clicked.connect(self.copy_requested.emit)
        self._copy_json_button = QPushButton("Copy JSON")
        self._copy_json_button.clicked.connect(self.copy_json_requested.emit)
        self._export_button = QPushButton("Export Summary...")
        self._export_button.clicked.connect(self.export_requested.emit)
        self._export_json_button = QPushButton("Export JSON...")
        self._export_json_button.clicked.connect(self.export_json_requested.emit)
        self._hint_label = QLabel(_DEFAULT_HINT_TEXT)
        self._hint_label.setWordWrap(True)

        self._list = QListWidget()
        self._list.setFocusPolicy(Qt.NoFocus)
        self._list.itemDoubleClicked.connect(self._on_item_activated)
        self._list.itemSelectionChanged.connect(self._update_selection_actions)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.addWidget(self._summary_label, 1)
        header_layout.addWidget(self._severity_filter_combo)
        header_layout.addWidget(self._reset_view_button)
        header_layout.addWidget(self._open_selected_button)
        header_layout.addWidget(self._open_first_error_button)
        header_layout.addWidget(self._open_first_warning_button)
        header_layout.addWidget(self._copy_button)
        header_layout.addWidget(self._copy_json_button)
        header_layout.addWidget(self._export_button)
        header_layout.addWidget(self._export_json_button)

        layout.addLayout(header_layout)
        layout.addWidget(self._hint_label)
        layout.addWidget(self._list, 1)

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

    def entries(self):
        return list(self._visible_entries)

    def view_state(self):
        return {"severity_filter": self._current_filter_value()}

    def restore_view_state(self, state):
        view_state = state if isinstance(state, dict) else {}
        severity_value = str(view_state.get("severity_filter") or "")
        index = self._severity_filter_combo.findData(severity_value)
        self._severity_filter_combo.setCurrentIndex(index if index >= 0 else 0)

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
            self._list.addItem(item)
        self._restore_selection(selection_key)
        self._update_selection_actions()

    def _reset_view(self):
        self._severity_filter_combo.setCurrentIndex(0)

    def _update_selection_actions(self):
        current_item = self._list.currentItem()
        if current_item is not None:
            self._selection_anchor_key = _entry_key(current_item.data(Qt.UserRole + 1))
        self._open_selected_button.setEnabled(current_item is not None)

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

    def _open_selected(self):
        item = self._list.currentItem()
        if item is None:
            return
        self._on_item_activated(item)

    def _on_item_activated(self, item):
        self._activated_entry = item.data(Qt.UserRole + 1)
        self._selection_anchor_key = _entry_key(self._activated_entry)
        page_name, widget_name = item.data(Qt.UserRole) or ("", "")
        self.diagnostic_activated.emit(page_name or "", widget_name or "")
