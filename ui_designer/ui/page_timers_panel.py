"""Editor panel for page-level timers."""

from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..model.page_timers import (
    normalize_page_timers,
    suggest_page_timer_callback,
    suggest_page_timer_name,
    validate_page_timers,
)


_PAGE_TIMERS_CONTROL_HEIGHT = 22


def _set_widget_metadata(widget, *, tooltip=None, accessible_name=None):
    if tooltip is not None:
        hint = str(tooltip or "")
        if str(widget.property("_page_timers_hint_snapshot") or "") != hint:
            widget.setToolTip(hint)
            widget.setStatusTip(hint)
            widget.setProperty("_page_timers_hint_snapshot", hint)
    if accessible_name is not None:
        name = str(accessible_name or "")
        if str(widget.property("_page_timers_accessible_snapshot") or "") != name:
            widget.setAccessibleName(name)
            widget.setProperty("_page_timers_accessible_snapshot", name)


def _set_item_metadata(item, tooltip):
    item.setToolTip(tooltip)
    item.setStatusTip(tooltip)
    item.setData(Qt.AccessibleTextRole, tooltip)


def _set_compact_button_metrics(button):
    button.setFixedHeight(_PAGE_TIMERS_CONTROL_HEIGHT)
    button.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
    return button


class PageTimersPanel(QWidget):
    """Editable list of page-level timers stored in Page.timers."""

    timers_changed = pyqtSignal(list)
    validation_message = pyqtSignal(str)
    user_code_requested = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._page = None
        self._timers = []
        self._updating = False
        self._init_ui()
        self.clear()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self._header_frame = QWidget()
        self._header_frame.setObjectName("page_timers_header")
        self._header_frame.setProperty("panelTone", "timers")
        header_layout = QVBoxLayout(self._header_frame)
        header_layout.setContentsMargins(2, 2, 2, 2)
        header_layout.setSpacing(2)

        self._eyebrow_label = QLabel("Timers")
        self._eyebrow_label.setObjectName("page_timers_eyebrow")
        header_layout.addWidget(self._eyebrow_label)

        self._summary_label = QLabel("")
        self._summary_label.setObjectName("workspace_section_title")
        header_layout.addWidget(self._summary_label)

        self._header_meta_label = QLabel(
            "Edit timer scheduling for the current page."
        )
        self._header_meta_label.setObjectName("page_timers_meta")
        self._header_meta_label.setWordWrap(True)
        header_layout.addWidget(self._header_meta_label)

        self._metrics_frame = QWidget()
        self._metrics_frame.setObjectName("page_timers_metrics_strip")
        self._header_chip_row = QHBoxLayout(self._metrics_frame)
        self._header_chip_row.setContentsMargins(0, 0, 0, 0)
        self._header_chip_row.setSpacing(2)
        self._count_chip = self._make_status_chip("0 timers", "accent")
        self._selection_chip = self._make_status_chip("No selection", "warning")
        self._header_chip_row.addWidget(self._count_chip)
        self._header_chip_row.addWidget(self._selection_chip)
        self._header_chip_row.addStretch(1)
        header_layout.addWidget(self._metrics_frame)
        layout.addWidget(self._header_frame)

        self._table_frame = QWidget()
        self._table_frame.setObjectName("page_editor_table_shell")
        table_layout = QVBoxLayout(self._table_frame)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(2)
        self._table_label = QLabel("Timer Definitions")
        self._table_label.setObjectName("page_editor_section_label")
        table_layout.addWidget(self._table_label)
        self._table_label.hide()

        self._hint_label = QLabel(
            "Delay and period are raw C expressions in milliseconds."
        )
        self._hint_label.setObjectName("workspace_section_subtitle")
        self._hint_label.setWordWrap(True)
        table_layout.addWidget(self._hint_label)

        self._table = QTableWidget(0, 5, self)
        self._table.setObjectName("page_editor_table")
        self._table.setHorizontalHeaderLabels(["Name", "Callback", "Delay", "Period", "Auto Start"])
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self._table.itemChanged.connect(self._on_item_changed)
        self._table.itemSelectionChanged.connect(self._update_actions)
        self._table.setAccessibleName("Page timers table")
        table_layout.addWidget(self._table, 1)

        self._actions_frame = QWidget()
        self._actions_frame.setObjectName("page_editor_actions")
        actions_layout = QVBoxLayout(self._actions_frame)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(2)
        self._actions_label = QLabel("Timer Actions")
        self._actions_label.setObjectName("page_editor_section_label")
        actions_layout.addWidget(self._actions_label)
        self._actions_label.hide()
        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(2)
        self._add_button = QPushButton("Add Timer")
        self._remove_button = QPushButton("Remove Timer")
        self._open_code_button = QPushButton("Open User Code")
        for button in (self._add_button, self._remove_button, self._open_code_button):
            _set_compact_button_metrics(button)
        self._add_button.clicked.connect(self._on_add_timer)
        self._remove_button.clicked.connect(self._on_remove_timer)
        self._open_code_button.clicked.connect(self._on_open_user_code)
        buttons.addWidget(self._add_button)
        buttons.addWidget(self._remove_button)
        buttons.addWidget(self._open_code_button)
        buttons.addStretch(1)
        actions_layout.addLayout(buttons)
        table_layout.addWidget(self._actions_frame)

        layout.addWidget(self._table_frame, 1)
        self._eyebrow_label.hide()
        self._header_meta_label.hide()
        self._metrics_frame.hide()
        self._hint_label.hide()
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
        count = len(self._timers)
        selected_timer = self._selected_timer()
        selected_name = str(selected_timer.get("name", "") or "").strip()
        count_text = f"{count} {'timer' if count == 1 else 'timers'}"
        selection_text = selected_name or "No selection"
        self._set_status_chip_state(self._count_chip, f"{count} {'timer' if count == 1 else 'timers'}", "accent" if self._page is not None else "warning")
        self._set_status_chip_state(self._selection_chip, selection_text, "accent" if selected_name else "warning")
        if self._page is None:
            meta = "Open a page to configure timer scheduling and callback entry points."
        elif selected_name:
            meta = f"Editing timer scheduling for {self._page.name}. Selected timer: {selected_name}."
        else:
            meta = f"Editing timer scheduling for {self._page.name}. Select a timer to inspect or open its callback."
        self._header_meta_label.setText(meta)
        selection_summary = f"Selected timer: {selected_name}." if selected_name else "No timer selected."
        _set_widget_metadata(
            self._eyebrow_label,
            tooltip="Page timers engineering surface.",
            accessible_name="Page timers engineering surface.",
        )
        _set_widget_metadata(
            self._count_chip,
            tooltip=f"Timer count: {count_text}.",
            accessible_name=f"Timer count: {count_text}.",
        )
        _set_widget_metadata(
            self._selection_chip,
            tooltip=f"Timer selection: {selection_summary}",
            accessible_name=f"Timer selection: {selection_summary}",
        )
        _set_widget_metadata(
            self._metrics_frame,
            tooltip=f"Page timers metrics: {count_text}. {selection_summary}",
            accessible_name=f"Page timers metrics: {count_text}. {selection_summary}",
        )

    def _update_accessibility_summary(self, summary_text):
        selection_summary = self._selection_accessibility_summary()
        panel_summary = summary_text if not selection_summary else f"{summary_text}. {selection_summary}"
        _set_widget_metadata(self, tooltip=panel_summary, accessible_name=panel_summary)
        _set_widget_metadata(
            self._header_frame,
            tooltip=f"Page timers header. {panel_summary}",
            accessible_name=f"Page timers header. {panel_summary}",
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
            self._table,
            tooltip=panel_summary,
            accessible_name=f"Page timers table: {panel_summary}",
        )

    def _update_button_metadata(self, button, tooltip, accessible_name):
        _set_widget_metadata(button, tooltip=tooltip, accessible_name=accessible_name)

    def _selected_timer(self):
        if self._table.selectionModel() is None:
            return {}
        selected_rows = self._table.selectionModel().selectedRows()
        if not selected_rows:
            return {}
        row = selected_rows[0].row()
        if row < 0 or row >= len(self._timers):
            return {}
        return dict(self._timers[row])

    def _selection_accessibility_summary(self):
        if self._page is None:
            return ""
        selected_timer = self._selected_timer()
        selected_timer_name = str(selected_timer.get("name", "") or "").strip() or "none"
        return f"Selected timer: {selected_timer_name}."

    def clear(self):
        self.set_page(None)

    def set_page(self, page):
        self._page = page
        self._timers = normalize_page_timers(getattr(page, "timers", []))
        self._rebuild_table()

    def _rebuild_table(self):
        self._updating = True
        self._table.setRowCount(len(self._timers))
        for row, timer in enumerate(self._timers):
            items = (
                QTableWidgetItem(timer.get("name", "")),
                QTableWidgetItem(timer.get("callback", "")),
                QTableWidgetItem(timer.get("delay_ms", "")),
                QTableWidgetItem(timer.get("period_ms", "")),
                QTableWidgetItem("true" if timer.get("auto_start") else "false"),
            )
            hints = (
                f"Page timer Name: {timer.get('name', '') or 'none'}.",
                f"Page timer Callback: {timer.get('callback', '') or 'none'}.",
                f"Page timer Delay: {timer.get('delay_ms', '') or 'none'}.",
                f"Page timer Period: {timer.get('period_ms', '') or 'none'}.",
                f"Page timer Auto Start: {'true' if timer.get('auto_start') else 'false'}.",
            )
            for column, (item, hint) in enumerate(zip(items, hints)):
                _set_item_metadata(item, hint)
                self._table.setItem(row, column, item)
        self._updating = False
        self._update_summary()
        self._update_actions()

    def _update_summary(self):
        if self._page is None:
            summary_text = "Page Timers: no active page"
            self._summary_label.setText(summary_text)
            self._update_header_state()
            self._update_accessibility_summary(summary_text)
            return
        count = len(self._timers)
        noun = "timer" if count == 1 else "timers"
        summary_text = f"Page Timers: {count} {noun} on {self._page.name}"
        self._summary_label.setText(summary_text)
        self._update_header_state()
        self._update_accessibility_summary(summary_text)

    def _update_actions(self):
        has_page = self._page is not None
        selected_timer = self._selected_timer()
        selected_timer_name = str(selected_timer.get("name", "") or "").strip()
        selected_callback = str(selected_timer.get("callback", "") or "").strip()
        has_selection = bool(selected_timer_name)
        self._table.setEnabled(has_page)
        self._add_button.setEnabled(has_page)
        self._remove_button.setEnabled(has_page and has_selection)
        self._open_code_button.setEnabled(has_page and has_selection)
        if has_page:
            add_hint = "Add a page timer."
            page_name = str(self._page.name or "current page")
        else:
            add_hint = "Open a page to manage timers."
            page_name = ""
        if has_page and has_selection:
            remove_hint = f"Remove the selected page timer: {selected_timer_name}."
            code_hint = f"Open user code for timer callback: {selected_callback or 'none'}."
        elif has_page:
            remove_hint = "Select a timer to remove it."
            code_hint = "Select a timer to open its user code."
        else:
            remove_hint = "Open a page to manage timers."
            code_hint = "Open a page to access timer user code."
        self._update_button_metadata(
            self._add_button,
            add_hint,
            f"Add page timer to {page_name}" if has_page else "Add page timer unavailable",
        )
        self._update_button_metadata(
            self._remove_button,
            remove_hint,
            f"Remove page timer: {selected_timer_name}" if has_page and has_selection else "Remove page timer unavailable",
        )
        self._update_button_metadata(
            self._open_code_button,
            code_hint,
            (
                f"Open timer user code: {selected_callback}"
                if has_page and has_selection and selected_callback
                else "Open timer user code unavailable"
            ),
        )
        self._update_header_state()
        summary_text = self._summary_label.text().strip()
        if summary_text:
            self._update_accessibility_summary(summary_text)

    def _table_timers(self):
        timers = []
        for row in range(self._table.rowCount()):
            name_item = self._table.item(row, 0)
            callback_item = self._table.item(row, 1)
            delay_item = self._table.item(row, 2)
            period_item = self._table.item(row, 3)
            auto_start_item = self._table.item(row, 4)
            timers.append(
                {
                    "name": name_item.text() if name_item is not None else "",
                    "callback": callback_item.text() if callback_item is not None else "",
                    "delay_ms": delay_item.text() if delay_item is not None else "",
                    "period_ms": period_item.text() if period_item is not None else "",
                    "auto_start": auto_start_item.text() if auto_start_item is not None else "",
                }
            )
        return timers

    def _commit_table_timers(self):
        timers = self._table_timers()
        ok, normalized_timers, message = validate_page_timers(self._page, timers)
        if not ok:
            self.validation_message.emit(message)
            self._rebuild_table()
            return

        normalization_changed = normalized_timers != timers
        changed = normalized_timers != self._timers
        self._timers = normalized_timers

        if normalization_changed:
            self._rebuild_table()

        self._update_summary()
        if changed:
            self.timers_changed.emit(list(self._timers))

    def _on_item_changed(self, item):
        del item
        if self._updating or self._page is None:
            return
        self._commit_table_timers()

    def _on_add_timer(self):
        if self._page is None:
            return
        timer_name = suggest_page_timer_name(self._page, self._timers, base_name="timer")
        callback_name = suggest_page_timer_callback(self._page, timer_name)
        self._timers = self._timers + [
            {
                "name": timer_name,
                "callback": callback_name,
                "delay_ms": "1000",
                "period_ms": "1000",
                "auto_start": False,
            }
        ]
        self._rebuild_table()
        self.timers_changed.emit(list(self._timers))
        row = len(self._timers) - 1
        if row >= 0:
            self._table.selectRow(row)

    def _on_remove_timer(self):
        if self._page is None:
            return
        selected_rows = self._table.selectionModel().selectedRows() if self._table.selectionModel() else []
        if not selected_rows:
            return
        row = selected_rows[0].row()
        self._timers = [timer for index, timer in enumerate(self._timers) if index != row]
        self._rebuild_table()
        self.timers_changed.emit(list(self._timers))

    def _on_open_user_code(self):
        if self._page is None:
            return
        selected_rows = self._table.selectionModel().selectedRows() if self._table.selectionModel() else []
        if not selected_rows:
            return
        row = selected_rows[0].row()
        if row < 0 or row >= len(self._timers):
            return
        callback_name = (self._timers[row].get("callback", "") or "").strip()
        if not callback_name:
            return
        self.user_code_requested.emit(callback_name, "void {func_name}(egui_timer_t *timer)")

    def select_timer(self, timer_name):
        if self._page is None:
            return False
        wanted_name = str(timer_name or "")
        if not wanted_name:
            return False
        for row, timer in enumerate(self._timers):
            if str(timer.get("name", "")) != wanted_name:
                continue
            self._table.selectRow(row)
            item = self._table.item(row, 0)
            if item is not None:
                self._table.scrollToItem(item)
            return True
        return False
