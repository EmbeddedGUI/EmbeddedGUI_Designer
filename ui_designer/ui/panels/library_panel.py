"""Library panel wrapper for component browsing and insertion."""

from __future__ import annotations

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QVBoxLayout, QWidget

from ..widget_browser import WidgetBrowserPanel


class LibraryPanel(QWidget):
    """Thin wrapper around ``WidgetBrowserPanel`` for shell composition."""

    insert_requested = pyqtSignal(str)
    reveal_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._browser = WidgetBrowserPanel(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._browser)
        self._browser.insert_requested.connect(self.insert_requested)
        self._browser.reveal_requested.connect(self.reveal_requested)

    def set_insert_target_label(self, label: str) -> None:
        self._browser.set_insert_target_label(label)

    def focus_search(self) -> None:
        self._browser.focus_search()

    def select_widget_type(self, widget_type: str) -> None:
        self._browser.select_widget_type(widget_type)

    def record_insert(self, widget_type: str) -> None:
        self._browser.record_insert(widget_type)

    def refresh(self) -> None:
        self._browser.refresh()
