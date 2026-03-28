"""Editor panel for page-level timers."""

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

from ..model.page_timers import (
    normalize_page_timers,
    suggest_page_timer_callback,
    suggest_page_timer_name,
    validate_page_timers,
)
from .iconography import make_icon


def _set_widget_metadata(widget, *, tooltip=None, accessible_name=None):
    if tooltip is not None:
        widget.setToolTip(tooltip)
        widget.setStatusTip(tooltip)
    if accessible_name is not None:
        widget.setAccessibleName(accessible_name)


def _set_item_metadata(item, tooltip):
    item.setToolTip(tooltip)
    item.setStatusTip(tooltip)
    item.setData(Qt.AccessibleTextRole, tooltip)


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
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self._summary_label = QLabel("")
        self._summary_label.setObjectName("workspace_section_title")
        self._hint_label = QLabel(
            "Page timers generate egui_timer_t members plus helper functions. Delay and period are raw C expressions in milliseconds."
        )
        self._hint_label.setObjectName("workspace_section_subtitle")
        self._hint_label.setWordWrap(True)

        self._table = QTableWidget(0, 5, self)
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

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(6)
        self._add_button = QPushButton("Add Timer")
        self._add_button.setIcon(make_icon("time"))
        self._remove_button = QPushButton("Remove Timer")
        self._remove_button.setIcon(make_icon("stop"))
        self._open_code_button = QPushButton("Open User Code")
        self._open_code_button.setIcon(make_icon("page"))
        self._add_button.clicked.connect(self._on_add_timer)
        self._remove_button.clicked.connect(self._on_remove_timer)
        self._open_code_button.clicked.connect(self._on_open_user_code)
        buttons.addWidget(self._add_button)
        buttons.addWidget(self._remove_button)
        buttons.addWidget(self._open_code_button)
        buttons.addStretch(1)

        layout.addWidget(self._summary_label)
        layout.addWidget(self._hint_label)
        layout.addWidget(self._table, 1)
        layout.addLayout(buttons)
        self._update_actions()

    def _update_accessibility_summary(self, summary_text):
        _set_widget_metadata(self, tooltip=summary_text, accessible_name=summary_text)
        _set_widget_metadata(self._summary_label, tooltip=summary_text, accessible_name=summary_text)
        _set_widget_metadata(
            self._hint_label,
            tooltip=self._hint_label.text(),
            accessible_name=self._hint_label.text(),
        )
        _set_widget_metadata(
            self._table,
            tooltip=summary_text,
            accessible_name=f"Page timers table: {summary_text}",
        )

    def _update_button_metadata(self, button, tooltip, accessible_name):
        _set_widget_metadata(button, tooltip=tooltip, accessible_name=accessible_name)

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
            self._update_accessibility_summary(summary_text)
            return
        count = len(self._timers)
        noun = "timer" if count == 1 else "timers"
        summary_text = f"Page Timers: {count} {noun} on {self._page.name}"
        self._summary_label.setText(summary_text)
        self._update_accessibility_summary(summary_text)

    def _update_actions(self):
        has_page = self._page is not None
        has_selection = bool(self._table.selectionModel() and self._table.selectionModel().selectedRows())
        self._table.setEnabled(has_page)
        self._add_button.setEnabled(has_page)
        self._remove_button.setEnabled(has_page and has_selection)
        self._open_code_button.setEnabled(has_page and has_selection)
        if has_page:
            add_hint = "Add a page timer."
        else:
            add_hint = "Open a page to manage timers."
        if has_page and has_selection:
            remove_hint = "Remove the selected page timer."
            code_hint = "Open user code for the selected timer callback."
        elif has_page:
            remove_hint = "Select a timer to remove it."
            code_hint = "Select a timer to open its user code."
        else:
            remove_hint = "Open a page to manage timers."
            code_hint = "Open a page to access timer user code."
        self._update_button_metadata(
            self._add_button,
            add_hint,
            "Add page timer" if has_page else "Add page timer unavailable",
        )
        self._update_button_metadata(
            self._remove_button,
            remove_hint,
            "Remove page timer" if has_page and has_selection else "Remove page timer unavailable",
        )
        self._update_button_metadata(
            self._open_code_button,
            code_hint,
            "Open timer user code" if has_page and has_selection else "Open timer user code unavailable",
        )

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
