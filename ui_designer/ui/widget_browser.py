"""Widget browser with categories, search, favorites, recents, and preview cards."""

from __future__ import annotations

from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from qfluentwidgets import PrimaryPushButton, SearchLineEdit

from ..model.config import get_config
from ..model.widget_registry import WidgetRegistry
from .iconography import make_icon, make_widget_preview, widget_icon_key


class WidgetBrowserCard(QFrame):
    """Single widget entry card used by the browser grid."""

    clicked = pyqtSignal(str)
    insert_requested = pyqtSignal(str)
    favorite_toggled = pyqtSignal(str)
    menu_requested = pyqtSignal(str, object)

    def __init__(self, item, parent=None):
        super().__init__(parent)
        self._item = dict(item or {})
        self._selected = False
        self._init_ui()

    @property
    def type_name(self):
        return self._item.get("type_name", "")

    def _init_ui(self):
        self.setObjectName("widget_browser_card")
        self.setProperty("selected", False)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(8)

        icon_label = QLabel()
        icon_label.setPixmap(make_icon(self._item.get("icon_key") or widget_icon_key(self.type_name), size=22).pixmap(22, 22))
        header.addWidget(icon_label, 0, Qt.AlignTop)

        title_layout = QVBoxLayout()
        title_layout.setSpacing(2)
        title = QLabel(self._item.get("display_name", self.type_name))
        title.setObjectName("widget_browser_card_title")
        title_layout.addWidget(title)

        meta = QLabel(self._item.get("category", ""))
        meta.setObjectName("widget_browser_card_meta")
        title_layout.addWidget(meta)
        header.addLayout(title_layout, 1)

        self._favorite_btn = QToolButton()
        self._favorite_btn.setObjectName("widget_browser_favorite_button")
        self._favorite_btn.setCheckable(True)
        self._favorite_btn.setText("*")
        self._favorite_btn.toggled.connect(lambda _checked: self.favorite_toggled.emit(self.type_name))
        header.addWidget(self._favorite_btn, 0, Qt.AlignTop)
        layout.addLayout(header)

        preview = QLabel()
        preview.setObjectName("widget_browser_preview")
        preview.setAlignment(Qt.AlignCenter)
        preview.setPixmap(make_widget_preview(self._item.get("preview_kind", "widget"), size=(180, 104)))
        layout.addWidget(preview)

        keywords = ", ".join(self._item.get("keywords", [])[:4])
        keywords_label = QLabel(keywords)
        keywords_label.setObjectName("widget_browser_keywords")
        keywords_label.setWordWrap(True)
        layout.addWidget(keywords_label)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        insert_btn = PrimaryPushButton("Insert")
        insert_btn.clicked.connect(lambda: self.insert_requested.emit(self.type_name))
        action_row.addWidget(insert_btn)
        action_row.addStretch()
        layout.addLayout(action_row)

    def set_selected(self, selected):
        self._selected = bool(selected)
        self.setProperty("selected", self._selected)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def set_favorite(self, favorite):
        self._favorite_btn.blockSignals(True)
        self._favorite_btn.setChecked(bool(favorite))
        self._favorite_btn.blockSignals(False)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.type_name)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.insert_requested.emit(self.type_name)
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event):
        self.menu_requested.emit(self.type_name, event.globalPos())
        event.accept()


class WidgetBrowserPanel(QWidget):
    """Panel that organizes widgets with search, favorites, and recents."""

    insert_requested = pyqtSignal(str)
    reveal_requested = pyqtSignal(str)

    _SPECIAL_CATEGORIES = (
        ("all", "All Widgets"),
        ("favorites", "Favorites"),
        ("recent", "Recent"),
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self._config = get_config()
        self._registry = WidgetRegistry.instance()
        self._selected_type = ""
        self._insert_target_label = "Current page root"
        self._cards = {}
        self._init_ui()
        self._populate_categories()
        self.refresh()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        header = QFrame()
        header.setObjectName("widget_browser_header")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(14, 14, 14, 14)
        header_layout.setSpacing(6)

        title = QLabel("Widget Browser")
        title.setObjectName("workspace_section_title")
        header_layout.addWidget(title)

        subtitle = QLabel("Browse by category, search by keyword, and insert directly into the current target.")
        subtitle.setObjectName("workspace_section_subtitle")
        subtitle.setWordWrap(True)
        header_layout.addWidget(subtitle)

        self._insert_target = QLabel("")
        self._insert_target.setObjectName("workspace_status_chip")
        self._insert_target.setWordWrap(True)
        header_layout.addWidget(self._insert_target)
        layout.addWidget(header)

        search_row = QHBoxLayout()
        search_row.setContentsMargins(0, 0, 0, 0)
        search_row.setSpacing(8)

        self._search = SearchLineEdit()
        self._search.setPlaceholderText("Search widgets by name, category, or keyword")
        self._search.textChanged.connect(self.refresh)
        search_row.addWidget(self._search, 1)
        layout.addLayout(search_row)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(12)

        self._category_list = QListWidget()
        self._category_list.setObjectName("widget_browser_categories")
        self._category_list.setFixedWidth(168)
        self._category_list.currentRowChanged.connect(lambda _row: self.refresh())
        body.addWidget(self._category_list, 0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        body.addWidget(self._scroll, 1)

        self._cards_container = QWidget()
        self._cards_layout = QGridLayout(self._cards_container)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setHorizontalSpacing(12)
        self._cards_layout.setVerticalSpacing(12)
        self._scroll.setWidget(self._cards_container)

        layout.addLayout(body, 1)
        self._update_insert_target()

    def _populate_categories(self):
        self._category_list.clear()
        for category_id, label in self._SPECIAL_CATEGORIES:
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, category_id)
            item.setIcon(make_icon(category_id if category_id != "all" else "widgets", size=18))
            self._category_list.addItem(item)
        for label in self._registry.browser_categories():
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, label)
            icon_key = {
                "Basics": "widgets",
                "Layout": "layout",
                "Input": "input",
                "Navigation": "navigation",
                "Display & Data": "chart",
                "Media": "media",
                "Decoration": "assets",
                "Custom": "widget",
            }.get(label, "widgets")
            item.setIcon(make_icon(icon_key, size=18))
            self._category_list.addItem(item)
        self._category_list.setCurrentRow(0)

    def set_insert_target_label(self, label):
        self._insert_target_label = (label or "").strip() or "Current page root"
        self._update_insert_target()

    def focus_search(self):
        self._search.setFocus()
        self._search.selectAll()

    def select_widget_type(self, widget_type):
        widget_type = str(widget_type or "").strip()
        if not widget_type:
            return
        self._selected_type = widget_type
        for card in self._cards.values():
            card.set_selected(card.type_name == widget_type)

    def record_insert(self, widget_type):
        self._config.record_widget_browser_recent(widget_type)
        self.refresh()

    def recent_types(self):
        return list(self._config.widget_browser_recent)

    def favorite_types(self):
        return list(self._config.widget_browser_favorites)

    def refresh(self):
        self._rebuild_cards(self._filtered_items())

    def _update_insert_target(self):
        self._insert_target.setText(f"Insert target: {self._insert_target_label}")

    def _selected_category(self):
        item = self._category_list.currentItem()
        if item is None:
            return "all"
        return item.data(Qt.UserRole) or "all"

    def _filtered_items(self):
        search = (self._search.text() or "").strip().lower()
        category = self._selected_category()
        favorite_types = set(self._config.widget_browser_favorites)
        recent_types = list(self._config.widget_browser_recent)
        recent_lookup = set(recent_types)
        items = self._registry.browser_items(addable_only=True)

        if category == "favorites":
            items = [item for item in items if item.get("type_name") in favorite_types]
        elif category == "recent":
            order = {name: index for index, name in enumerate(recent_types)}
            items = [item for item in items if item.get("type_name") in recent_lookup]
            items.sort(key=lambda item: order.get(item.get("type_name"), 999))
        elif category != "all":
            items = [item for item in items if item.get("category") == category]

        if search:
            filtered = []
            for item in items:
                haystack = " ".join(
                    [item.get("display_name", ""), item.get("type_name", ""), item.get("category", "")]
                    + list(item.get("keywords", []))
                ).lower()
                if search in haystack:
                    filtered.append(item)
            items = filtered

        return items

    def _clear_cards(self):
        while self._cards_layout.count():
            item = self._cards_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._cards = {}

    def _rebuild_cards(self, items):
        self._clear_cards()
        favorites = set(self._config.widget_browser_favorites)
        columns = 2
        if not items:
            self._selected_type = ""
            empty = QLabel("No widgets match the current filters.")
            empty.setObjectName("workspace_empty_state")
            empty.setAlignment(Qt.AlignCenter)
            self._cards_layout.addWidget(empty, 0, 0, 1, columns)
            return

        visible_types = [item.get("type_name", "") for item in items]
        if self._selected_type not in visible_types:
            self._selected_type = visible_types[0]

        for index, item in enumerate(items):
            card = WidgetBrowserCard(item)
            card.set_favorite(item.get("type_name") in favorites)
            card.clicked.connect(self._select_card)
            card.insert_requested.connect(self.insert_requested.emit)
            card.favorite_toggled.connect(self._toggle_favorite)
            card.menu_requested.connect(self._show_card_menu)
            row = index // columns
            column = index % columns
            self._cards_layout.addWidget(card, row, column)
            self._cards[index] = card
            card.set_selected(card.type_name == self._selected_type)

        self._cards_layout.setColumnStretch(columns, 1)

    def _select_card(self, widget_type):
        self._selected_type = widget_type
        for card in self._cards.values():
            card.set_selected(card.type_name == widget_type)

    def _toggle_favorite(self, widget_type):
        self._config.toggle_widget_browser_favorite(widget_type)
        self.refresh()

    def _show_card_menu(self, widget_type, global_pos):
        self._select_card(widget_type)
        is_favorite = widget_type in set(self._config.widget_browser_favorites)
        menu = QMenu(self)
        insert_action = menu.addAction("Insert")
        favorite_action = menu.addAction("Unfavorite" if is_favorite else "Favorite")
        reveal_action = menu.addAction("Reveal in Structure")
        chosen = menu.exec_(global_pos)
        if chosen == insert_action:
            self.insert_requested.emit(widget_type)
        elif chosen == favorite_action:
            self._toggle_favorite(widget_type)
        elif chosen == reveal_action:
            self.reveal_requested.emit(widget_type)
