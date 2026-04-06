"""Editor panel for page-level user fields."""

from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..model.page_fields import COMMON_PAGE_FIELD_TYPES, normalize_page_fields, suggest_page_field_name, validate_page_fields


def _set_widget_metadata(widget, *, tooltip=None, accessible_name=None):
    if tooltip is not None:
        hint = str(tooltip or "")
        if str(widget.property("_page_fields_hint_snapshot") or "") != hint:
            widget.setToolTip(hint)
            widget.setStatusTip(hint)
            widget.setProperty("_page_fields_hint_snapshot", hint)
    if accessible_name is not None:
        name = str(accessible_name or "")
        if str(widget.property("_page_fields_accessible_snapshot") or "") != name:
            widget.setAccessibleName(name)
            widget.setProperty("_page_fields_accessible_snapshot", name)


def _set_item_metadata(item, tooltip):
    item.setToolTip(tooltip)
    item.setStatusTip(tooltip)
    item.setData(Qt.AccessibleTextRole, tooltip)


class PageFieldsPanel(QWidget):
    """Editable list of page-level fields stored in Page.user_fields."""

    fields_changed = pyqtSignal(list)
    validation_message = pyqtSignal(str)
    user_code_section_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._page = None
        self._fields = []
        self._updating = False
        self._init_ui()
        self.clear()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self._header_frame = QWidget()
        self._header_frame.setObjectName("page_fields_header")
        self._header_frame.setProperty("panelTone", "fields")
        header_layout = QVBoxLayout(self._header_frame)
        header_layout.setContentsMargins(2, 2, 2, 2)
        header_layout.setSpacing(2)

        self._eyebrow_label = QLabel("Fields")
        self._eyebrow_label.setObjectName("page_fields_eyebrow")
        header_layout.addWidget(self._eyebrow_label)

        self._summary_label = QLabel("")
        self._summary_label.setObjectName("workspace_section_title")
        header_layout.addWidget(self._summary_label)

        self._header_meta_label = QLabel(
            "Page fields are generated members for the current page."
        )
        self._header_meta_label.setObjectName("page_fields_meta")
        self._header_meta_label.setWordWrap(True)
        header_layout.addWidget(self._header_meta_label)

        self._metrics_frame = QWidget()
        self._metrics_frame.setObjectName("page_fields_metrics_strip")
        self._header_chip_row = QHBoxLayout(self._metrics_frame)
        self._header_chip_row.setContentsMargins(0, 0, 0, 0)
        self._header_chip_row.setSpacing(2)
        self._count_chip = self._make_status_chip("0 fields", "accent")
        self._selection_chip = self._make_status_chip("No selection", "warning")
        self._header_chip_row.addWidget(self._count_chip)
        self._header_chip_row.addWidget(self._selection_chip)
        self._header_chip_row.addStretch(1)
        header_layout.addWidget(self._metrics_frame)

        layout.addWidget(self._header_frame)

        self._code_frame = QWidget()
        self._code_frame.setObjectName("page_editor_section")
        code_frame_layout = QVBoxLayout(self._code_frame)
        code_frame_layout.setContentsMargins(0, 0, 0, 0)
        code_frame_layout.setSpacing(2)
        self._code_label = QLabel("Lifecycle Hooks")
        self._code_label.setObjectName("page_editor_section_label")
        code_frame_layout.addWidget(self._code_label)
        self._code_label.hide()

        self._hint_label = QLabel(
            "Defaults are raw C expressions applied when the page opens."
        )
        self._hint_label.setObjectName("workspace_section_subtitle")
        self._hint_label.setWordWrap(True)

        self._code_hint_label = QLabel("Lifecycle hooks are in {page}.c. Open a section to edit setup and teardown.")
        self._code_hint_label.setObjectName("workspace_section_subtitle")
        self._code_hint_label.setWordWrap(True)
        _set_widget_metadata(
            self._code_hint_label,
            tooltip=self._code_hint_label.text(),
            accessible_name=self._code_hint_label.text(),
        )
        code_frame_layout.addWidget(self._code_hint_label)

        code_buttons = QHBoxLayout()
        code_buttons.setContentsMargins(0, 0, 0, 0)
        code_buttons.setSpacing(2)
        self._open_on_open_button = QPushButton("Open on_open")
        self._open_on_close_button = QPushButton("Open on_close")
        self._open_init_button = QPushButton("Open init")
        self._open_on_open_button.clicked.connect(lambda: self._request_section("on_open"))
        self._open_on_close_button.clicked.connect(lambda: self._request_section("on_close"))
        self._open_init_button.clicked.connect(lambda: self._request_section("init"))
        code_buttons.addWidget(self._open_on_open_button)
        code_buttons.addWidget(self._open_on_close_button)
        code_buttons.addWidget(self._open_init_button)
        code_buttons.addStretch(1)
        code_frame_layout.addLayout(code_buttons)
        layout.addWidget(self._code_frame)

        self._table_frame = QWidget()
        self._table_frame.setObjectName("page_editor_table_shell")
        table_layout = QVBoxLayout(self._table_frame)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(2)
        self._table_label = QLabel("Field Definitions")
        self._table_label.setObjectName("page_editor_section_label")
        table_layout.addWidget(self._table_label)
        self._table_label.hide()
        table_layout.addWidget(self._hint_label)

        self._table = QTableWidget(0, 3, self)
        self._table.setObjectName("page_editor_table")
        self._table.setHorizontalHeaderLabels(["Name", "Type", "Default"])
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self._table.itemChanged.connect(self._on_item_changed)
        self._table.itemSelectionChanged.connect(self._update_actions)
        self._table.setAccessibleName("Page fields table")
        table_layout.addWidget(self._table, 1)

        self._actions_frame = QWidget()
        self._actions_frame.setObjectName("page_editor_actions")
        actions_layout = QVBoxLayout(self._actions_frame)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(2)
        self._actions_label = QLabel("Field Actions")
        self._actions_label.setObjectName("page_editor_section_label")
        actions_layout.addWidget(self._actions_label)
        self._actions_label.hide()
        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(2)
        self._add_button = QPushButton("Add Field")
        self._remove_button = QPushButton("Remove Field")
        self._add_button.clicked.connect(self._on_add_field)
        self._remove_button.clicked.connect(self._on_remove_field)
        buttons.addWidget(self._add_button)
        buttons.addWidget(self._remove_button)
        buttons.addStretch(1)
        actions_layout.addLayout(buttons)
        table_layout.addWidget(self._actions_frame)

        layout.addWidget(self._table_frame, 1)
        self._eyebrow_label.hide()
        self._header_meta_label.hide()
        self._metrics_frame.hide()
        self._hint_label.hide()
        self._code_hint_label.hide()
        self._update_actions()

    def _make_status_chip(self, text, tone=None):
        chip = QLabel(text)
        chip.setObjectName("workspace_status_chip")
        if tone:
            chip.setProperty("chipTone", tone)
        return chip

    def _set_status_chip_state(self, chip, text, tone=None):
        chip.setText(text)
        chip.setProperty("chipTone", tone)
        chip.style().unpolish(chip)
        chip.style().polish(chip)
        chip.update()

    def _update_header_state(self):
        count = len(self._fields)
        selected_name = self._selected_field_name()
        count_text = f"{count} {'field' if count == 1 else 'fields'}"
        selection_text = selected_name or "No selection"
        self._set_status_chip_state(self._count_chip, f"{count} {'field' if count == 1 else 'fields'}", "accent" if self._page is not None else "warning")
        self._set_status_chip_state(self._selection_chip, selection_text, "accent" if selected_name else "warning")
        if self._page is None:
            meta = "Open a page to define generated members and page lifecycle code."
        elif selected_name:
            meta = f"Editing generated members for {self._page.name}. Selected field: {selected_name}."
        else:
            meta = f"Editing generated members for {self._page.name}. Select a field to inspect or remove it."
        self._header_meta_label.setText(meta)
        selection_summary = f"Selected field: {selected_name}." if selected_name else "No field selected."
        _set_widget_metadata(
            self._eyebrow_label,
            tooltip="Page fields engineering surface.",
            accessible_name="Page fields engineering surface.",
        )
        _set_widget_metadata(
            self._count_chip,
            tooltip=f"Field count: {count_text}.",
            accessible_name=f"Field count: {count_text}.",
        )
        _set_widget_metadata(
            self._selection_chip,
            tooltip=f"Field selection: {selection_summary}",
            accessible_name=f"Field selection: {selection_summary}",
        )
        _set_widget_metadata(
            self._metrics_frame,
            tooltip=f"Page fields metrics: {count_text}. {selection_summary}",
            accessible_name=f"Page fields metrics: {count_text}. {selection_summary}",
        )

    def _update_accessibility_summary(self, summary_text):
        selection_summary = self._selection_accessibility_summary()
        panel_summary = summary_text if not selection_summary else f"{summary_text}. {selection_summary}"
        _set_widget_metadata(self, tooltip=panel_summary, accessible_name=panel_summary)
        _set_widget_metadata(
            self._header_frame,
            tooltip=f"Page fields header. {panel_summary}",
            accessible_name=f"Page fields header. {panel_summary}",
        )
        _set_widget_metadata(self._summary_label, tooltip=summary_text, accessible_name=summary_text)
        _set_widget_metadata(
            self._header_meta_label,
            tooltip=self._header_meta_label.text(),
            accessible_name=self._header_meta_label.text(),
        )
        _set_widget_metadata(
            self._hint_label,
            tooltip=self._hint_label.text(),
            accessible_name=self._hint_label.text(),
        )
        _set_widget_metadata(
            self._code_hint_label,
            tooltip=self._code_hint_label.text(),
            accessible_name=self._code_hint_label.text(),
        )
        _set_widget_metadata(
            self._table,
            tooltip=panel_summary,
            accessible_name=f"Page fields table: {panel_summary}",
        )

    def _update_button_metadata(self, button, tooltip, accessible_name):
        _set_widget_metadata(button, tooltip=tooltip, accessible_name=accessible_name)

    def _selected_field_name(self):
        if self._table.selectionModel() is None:
            return ""
        selected_rows = self._table.selectionModel().selectedRows()
        if not selected_rows:
            return ""
        row = selected_rows[0].row()
        if row < 0 or row >= len(self._fields):
            return ""
        return str(self._fields[row].get("name", "") or "").strip()

    def _selection_accessibility_summary(self):
        if self._page is None:
            return ""
        selected_field_name = self._selected_field_name() or "none"
        return f"Selected field: {selected_field_name}."

    def clear(self):
        self.set_page(None)

    def set_page(self, page):
        self._page = page
        self._fields = normalize_page_fields(getattr(page, "user_fields", []))
        self._rebuild_table()

    def _rebuild_table(self):
        self._updating = True
        self._table.setRowCount(len(self._fields))
        for row, field in enumerate(self._fields):
            items = (
                QTableWidgetItem(field.get("name", "")),
                QTableWidgetItem(field.get("type", "")),
                QTableWidgetItem(field.get("default", "")),
            )
            hints = (
                f"Page field Name: {field.get('name', '') or 'none'}.",
                f"Page field Type: {field.get('type', '') or 'none'}.",
                f"Page field Default: {field.get('default', '') or 'none'}.",
            )
            for column, (item, hint) in enumerate(zip(items, hints)):
                _set_item_metadata(item, hint)
                self._table.setItem(row, column, item)
        self._updating = False
        self._update_summary()
        self._update_actions()

    def _update_summary(self):
        if self._page is None:
            summary_text = "Page Fields: no active page"
            self._summary_label.setText(summary_text)
            self._update_header_state()
            self._update_accessibility_summary(summary_text)
            return
        count = len(self._fields)
        noun = "field" if count == 1 else "fields"
        summary_text = f"Page Fields: {count} {noun} on {self._page.name}"
        self._summary_label.setText(summary_text)
        self._update_header_state()
        self._update_accessibility_summary(summary_text)

    def _update_actions(self):
        has_page = self._page is not None
        selected_field_name = self._selected_field_name()
        has_selection = bool(selected_field_name)
        self._table.setEnabled(has_page)
        self._add_button.setEnabled(has_page)
        self._remove_button.setEnabled(has_page and has_selection)
        self._open_on_open_button.setEnabled(has_page)
        self._open_on_close_button.setEnabled(has_page)
        self._open_init_button.setEnabled(has_page)
        if has_page:
            add_hint = "Add a page field."
            page_name = str(self._page.name or "current page")
            on_open_hint = f"Open the on_open section in {page_name} user code."
            on_close_hint = f"Open the on_close section in {page_name} user code."
            init_hint = f"Open the init section in {page_name} user code."
        else:
            add_hint = "Open a page to manage fields."
            page_name = ""
            on_open_hint = "Open a page to edit the on_open section."
            on_close_hint = "Open a page to edit the on_close section."
            init_hint = "Open a page to edit the init section."
        if has_page and has_selection:
            remove_hint = f"Remove the selected page field: {selected_field_name}."
        elif has_page:
            remove_hint = "Select a field to remove it."
        else:
            remove_hint = "Open a page to manage fields."
        self._update_button_metadata(
            self._add_button,
            add_hint,
            f"Add page field to {page_name}" if has_page else "Add page field unavailable",
        )
        self._update_button_metadata(
            self._remove_button,
            remove_hint,
            f"Remove page field: {selected_field_name}" if has_page and has_selection else "Remove page field unavailable",
        )
        self._update_button_metadata(
            self._open_on_open_button,
            on_open_hint,
            f"Open on_open user code for {page_name}" if has_page else "Open on_open user code unavailable",
        )
        self._update_button_metadata(
            self._open_on_close_button,
            on_close_hint,
            f"Open on_close user code for {page_name}" if has_page else "Open on_close user code unavailable",
        )
        self._update_button_metadata(
            self._open_init_button,
            init_hint,
            f"Open init user code for {page_name}" if has_page else "Open init user code unavailable",
        )
        self._update_header_state()
        summary_text = self._summary_label.text().strip()
        if summary_text:
            self._update_accessibility_summary(summary_text)

    def _table_fields(self):
        fields = []
        for row in range(self._table.rowCount()):
            name_item = self._table.item(row, 0)
            type_item = self._table.item(row, 1)
            default_item = self._table.item(row, 2)
            fields.append(
                {
                    "name": name_item.text() if name_item is not None else "",
                    "type": type_item.text() if type_item is not None else "",
                    "default": default_item.text() if default_item is not None else "",
                }
            )
        return fields

    def _commit_table_fields(self):
        fields = self._table_fields()
        ok, normalized_fields, message = validate_page_fields(self._page, fields)
        if not ok:
            self.validation_message.emit(message)
            self._rebuild_table()
            return

        normalization_changed = normalized_fields != fields
        changed = normalized_fields != self._fields
        self._fields = normalized_fields

        if normalization_changed:
            self._rebuild_table()

        self._update_summary()
        if changed:
            self.fields_changed.emit(list(self._fields))

    def _on_item_changed(self, item):
        del item
        if self._updating or self._page is None:
            return
        self._commit_table_fields()

    def _on_add_field(self):
        if self._page is None:
            return
        field_name = suggest_page_field_name(self._page, self._fields, base_name="field")
        default_value = "0"
        field_type = COMMON_PAGE_FIELD_TYPES[0] if COMMON_PAGE_FIELD_TYPES else "int"
        self._fields = self._fields + [{"name": field_name, "type": field_type, "default": default_value}]
        self._rebuild_table()
        self.fields_changed.emit(list(self._fields))
        row = len(self._fields) - 1
        if row >= 0:
            self._table.selectRow(row)

    def _on_remove_field(self):
        if self._page is None:
            return
        selected_rows = self._table.selectionModel().selectedRows() if self._table.selectionModel() else []
        if not selected_rows:
            return
        row = selected_rows[0].row()
        self._fields = [field for index, field in enumerate(self._fields) if index != row]
        self._rebuild_table()
        self.fields_changed.emit(list(self._fields))

    def _request_section(self, section_name):
        if self._page is None or not section_name:
            return
        self.user_code_section_requested.emit(section_name)

    def select_field(self, field_name):
        if self._page is None:
            return False
        wanted_name = str(field_name or "")
        if not wanted_name:
            return False
        for row, field in enumerate(self._fields):
            if str(field.get("name", "")) != wanted_name:
                continue
            self._table.selectRow(row)
            item = self._table.item(row, 0)
            if item is not None:
                self._table.scrollToItem(item)
            return True
        return False
