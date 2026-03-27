"""Widget browser with categories, search, favorites, recents, and preview cards."""

from __future__ import annotations

from collections import Counter

from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
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

        chips_row = QHBoxLayout()
        chips_row.setContentsMargins(0, 0, 0, 0)
        chips_row.setSpacing(6)
        scenario = str(self._item.get("scenario", "") or "").strip()
        if scenario:
            chips_row.addWidget(self._build_info_chip(scenario, "accent"))
        complexity = str(self._item.get("complexity", "") or "").strip().lower()
        complexity_tone = {"basic": "success", "intermediate": "warning", "advanced": "danger"}.get(complexity, "accent")
        if complexity:
            chips_row.addWidget(self._build_info_chip(complexity.title(), complexity_tone))
        if bool(self._item.get("is_container")):
            chips_row.addWidget(self._build_info_chip("Container", "success"))
        chips_row.addStretch()
        layout.addLayout(chips_row)

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

    def _build_info_chip(self, text, tone):
        chip = QLabel(str(text or "").strip())
        chip.setObjectName("widget_browser_card_chip")
        chip.setProperty("chipTone", str(tone or "accent"))
        return chip

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
        ("containers", "Containers"),
    )
    _SORT_MODES = (
        ("relevance", "Recommended"),
        ("name", "A-Z"),
        ("complexity", "Complexity"),
    )
    _COMPLEXITY_LEVELS = (
        ("all", "All"),
        ("basic", "Basic"),
        ("intermediate", "Intermediate"),
        ("advanced", "Advanced"),
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self._config = get_config()
        self._registry = WidgetRegistry.instance()
        self._selected_type = ""
        self._insert_target_label = "Current page root"
        self._cards = {}
        self._tag_buttons = {}
        self._lane_buttons = {}
        self._sort_buttons = {}
        self._complexity_buttons = {}
        self._sort_mode = "relevance"
        self._complexity_filter = "all"
        self._suspend_filter_persist = False
        self._init_ui()
        self._populate_categories()
        self._populate_quick_lanes()
        self._populate_tags()
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

        subtitle = QLabel("Browse by scenario, filter by tags, and insert directly into the selected target.")
        subtitle.setObjectName("workspace_section_subtitle")
        subtitle.setWordWrap(True)
        header_layout.addWidget(subtitle)

        self._insert_target = QLabel("")
        self._insert_target.setObjectName("workspace_status_chip")
        self._insert_target.setWordWrap(True)
        header_layout.addWidget(self._insert_target)

        stats_row = QHBoxLayout()
        stats_row.setContentsMargins(0, 0, 0, 0)
        stats_row.setSpacing(8)
        self._visible_count_chip = QLabel("Visible 0")
        self._visible_count_chip.setObjectName("workspace_status_chip")
        self._visible_count_chip.setProperty("chipTone", "accent")
        self._favorites_count_chip = QLabel("Favorites 0")
        self._favorites_count_chip.setObjectName("workspace_status_chip")
        self._favorites_count_chip.setProperty("chipTone", "success")
        self._recent_count_chip = QLabel("Recent 0")
        self._recent_count_chip.setObjectName("workspace_status_chip")
        self._recent_count_chip.setProperty("chipTone", "warning")
        for chip in (self._visible_count_chip, self._favorites_count_chip, self._recent_count_chip):
            stats_row.addWidget(chip)
        stats_row.addStretch()
        header_layout.addLayout(stats_row)
        layout.addWidget(header)

        search_row = QHBoxLayout()
        search_row.setContentsMargins(0, 0, 0, 0)
        search_row.setSpacing(8)

        self._search = SearchLineEdit()
        self._search.setPlaceholderText("Search widgets by name, category, or keyword")
        self._search.textChanged.connect(self.refresh)
        search_row.addWidget(self._search, 1)
        layout.addLayout(search_row)

        lanes_frame = QFrame()
        lanes_frame.setObjectName("widget_browser_lanes")
        lanes_layout = QVBoxLayout(lanes_frame)
        lanes_layout.setContentsMargins(10, 10, 10, 10)
        lanes_layout.setSpacing(8)
        lanes_title = QLabel("Quick Lanes")
        lanes_title.setObjectName("workspace_section_subtitle")
        lanes_layout.addWidget(lanes_title)
        self._lanes_grid_host = QWidget()
        self._lanes_grid = QGridLayout(self._lanes_grid_host)
        self._lanes_grid.setContentsMargins(0, 0, 0, 0)
        self._lanes_grid.setHorizontalSpacing(8)
        self._lanes_grid.setVerticalSpacing(8)
        lanes_layout.addWidget(self._lanes_grid_host)
        layout.addWidget(lanes_frame)

        organize_frame = QFrame()
        organize_frame.setObjectName("widget_browser_organize")
        organize_layout = QVBoxLayout(organize_frame)
        organize_layout.setContentsMargins(10, 8, 10, 8)
        organize_layout.setSpacing(8)

        sort_row = QHBoxLayout()
        sort_row.setContentsMargins(0, 0, 0, 0)
        sort_row.setSpacing(6)
        sort_title = QLabel("Sort")
        sort_title.setObjectName("workspace_section_subtitle")
        sort_row.addWidget(sort_title)
        self._sort_host = QWidget()
        self._sort_layout = QHBoxLayout(self._sort_host)
        self._sort_layout.setContentsMargins(0, 0, 0, 0)
        self._sort_layout.setSpacing(6)
        sort_row.addWidget(self._sort_host, 1)
        organize_layout.addLayout(sort_row)

        complexity_row = QHBoxLayout()
        complexity_row.setContentsMargins(0, 0, 0, 0)
        complexity_row.setSpacing(6)
        complexity_title = QLabel("Complexity")
        complexity_title.setObjectName("workspace_section_subtitle")
        complexity_row.addWidget(complexity_title)
        self._complexity_host = QWidget()
        self._complexity_layout = QHBoxLayout(self._complexity_host)
        self._complexity_layout.setContentsMargins(0, 0, 0, 0)
        self._complexity_layout.setSpacing(6)
        complexity_row.addWidget(self._complexity_host, 1)
        organize_layout.addLayout(complexity_row)
        layout.addWidget(organize_frame)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(12)

        self._category_list = QListWidget()
        self._category_list.setObjectName("widget_browser_categories")
        self._category_list.setFixedWidth(168)
        self._category_list.currentRowChanged.connect(self._on_category_changed)
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

        tags_frame = QFrame()
        tags_frame.setObjectName("widget_browser_tags")
        tags_layout = QHBoxLayout(tags_frame)
        tags_layout.setContentsMargins(10, 8, 10, 8)
        tags_layout.setSpacing(6)
        tags_title = QLabel("Tags")
        tags_title.setObjectName("workspace_section_subtitle")
        tags_layout.addWidget(tags_title)
        self._tags_host = QWidget()
        self._tags_layout = QHBoxLayout(self._tags_host)
        self._tags_layout.setContentsMargins(0, 0, 0, 0)
        self._tags_layout.setSpacing(6)
        tags_layout.addWidget(self._tags_host, 1)
        self._clear_tags_btn = QToolButton()
        self._clear_tags_btn.setText("Clear")
        self._clear_tags_btn.clicked.connect(self._clear_active_tags)
        tags_layout.addWidget(self._clear_tags_btn, 0)
        layout.addWidget(tags_frame)
        self._update_insert_target()
        self._populate_organizers()

    def _populate_categories(self):
        self._suspend_filter_persist = True
        self._category_list.clear()
        for category_id, label in self._SPECIAL_CATEGORIES:
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, category_id)
            icon_key = {
                "all": "widgets",
                "favorites": "tag",
                "recent": "history",
                "containers": "layout",
            }.get(category_id, "widgets")
            item.setIcon(make_icon(icon_key, size=18))
            self._category_list.addItem(item)
        for label in self._registry.browser_scenarios():
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, f"scenario:{label}")
            icon_key = self._scenario_icon_key(label)
            item.setIcon(make_icon(icon_key, size=18))
            self._category_list.addItem(item)
        default_id = str(getattr(self._config, "widget_browser_active_scenario", "all") or "all")
        selected_row = 0
        for row in range(self._category_list.count()):
            row_item = self._category_list.item(row)
            if row_item is None:
                continue
            if str(row_item.data(Qt.UserRole) or "").strip().lower() == default_id.strip().lower():
                selected_row = row
                break
        self._category_list.setCurrentRow(selected_row)
        self._suspend_filter_persist = False

    @staticmethod
    def _scenario_icon_key(label):
        return {
            "Layout & Containers": "layout",
            "Input & Forms": "input",
            "Navigation & Flow": "navigation",
            "Data & Visualization": "chart",
            "Feedback & Status": "status",
            "Media & Content": "media",
            "Decoration": "assets",
        }.get(label, "widgets")

    @staticmethod
    def _scenario_short_label(label):
        text = str(label or "").strip()
        if not text:
            return "Scenario"
        return text.split("&", 1)[0].strip().split(" ", 1)[0]

    def _lane_definitions(self):
        lanes = [
            ("all", "All", "widgets"),
            ("favorites", "Favorites", "tag"),
            ("recent", "Recent", "history"),
            ("containers", "Containers", "layout"),
        ]
        for scenario in self._registry.browser_scenarios():
            lane_id = f"scenario:{scenario}"
            lanes.append((lane_id, self._scenario_short_label(scenario), self._scenario_icon_key(scenario)))
        return lanes[:8]

    def _populate_quick_lanes(self):
        while self._lanes_grid.count():
            item = self._lanes_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._lane_buttons = {}
        columns = 4
        for index, (lane_id, label, icon_key) in enumerate(self._lane_definitions()):
            button = QToolButton()
            button.setObjectName("widget_browser_lane")
            button.setCheckable(True)
            button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            button.setIcon(make_icon(icon_key, size=18))
            button.setText(str(label))
            button.clicked.connect(lambda checked=False, value=lane_id: self._set_category_by_id(value))
            row = index // columns
            column = index % columns
            self._lanes_grid.addWidget(button, row, column)
            self._lane_buttons[lane_id.lower()] = button
        for col in range(columns):
            self._lanes_grid.setColumnStretch(col, 1)

    def _populate_organizers(self):
        while self._sort_layout.count():
            item = self._sort_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._sort_buttons = {}
        for mode, label in self._SORT_MODES:
            button = QToolButton()
            button.setObjectName("widget_browser_sort_button")
            button.setText(label)
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, value=mode: self._set_sort_mode(value))
            self._sort_layout.addWidget(button)
            self._sort_buttons[mode] = button
        self._sort_layout.addStretch()

        while self._complexity_layout.count():
            item = self._complexity_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._complexity_buttons = {}
        for level, label in self._COMPLEXITY_LEVELS:
            button = QToolButton()
            button.setObjectName("widget_browser_complexity_button")
            button.setText(label)
            button.setProperty("level", level)
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, value=level: self._set_complexity_filter(value))
            self._complexity_layout.addWidget(button)
            self._complexity_buttons[level] = button
        self._complexity_layout.addStretch()
        self._sync_organizers()

    def _sync_organizers(self):
        for mode, button in self._sort_buttons.items():
            button.blockSignals(True)
            button.setChecked(mode == self._sort_mode)
            button.blockSignals(False)
        for level, button in self._complexity_buttons.items():
            button.blockSignals(True)
            button.setChecked(level == self._complexity_filter)
            button.blockSignals(False)

    def _set_sort_mode(self, mode, refresh=True):
        value = str(mode or "").strip().lower()
        valid = {key for key, _label in self._SORT_MODES}
        self._sort_mode = value if value in valid else "relevance"
        self._sync_organizers()
        if refresh:
            self.refresh()

    def _set_complexity_filter(self, level, refresh=True):
        value = str(level or "").strip().lower()
        valid = {key for key, _label in self._COMPLEXITY_LEVELS}
        self._complexity_filter = value if value in valid else "all"
        self._sync_organizers()
        if refresh:
            self.refresh()

    def _reset_organizers(self):
        changed = False
        if self._sort_mode != "relevance":
            self._set_sort_mode("relevance", refresh=False)
            changed = True
        if self._complexity_filter != "all":
            self._set_complexity_filter("all", refresh=False)
            changed = True
        if changed:
            self.refresh()

    def _populate_tags(self):
        while self._tags_layout.count():
            item = self._tags_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._tag_buttons = {}
        for tag in self._available_tags():
            button = QToolButton()
            button.setObjectName("widget_browser_tag")
            button.setText(tag)
            button.setCheckable(True)
            button.toggled.connect(lambda checked, value=tag: self._on_tag_toggled(value, checked))
            self._tags_layout.addWidget(button)
            self._tag_buttons[tag.lower()] = button
        self._tags_layout.addStretch()
        self._sync_tags_from_config()

    def _available_tags(self):
        counts = Counter()
        for item in self._registry.browser_items(addable_only=True):
            for tag in item.get("tags", []):
                text = str(tag or "").strip()
                if text:
                    counts[text] += 1
        ranked = sorted(counts.items(), key=lambda entry: (-entry[1], entry[0].lower()))
        return [text for text, _count in ranked[:18]]

    def _active_tag_values(self):
        return [str(tag or "").strip().lower() for tag in getattr(self._config, "widget_browser_active_tags", []) if str(tag or "").strip()]

    def _sync_tags_from_config(self):
        active = set(self._active_tag_values())
        for tag, button in self._tag_buttons.items():
            button.blockSignals(True)
            button.setChecked(tag in active)
            button.blockSignals(False)
        self._clear_tags_btn.setEnabled(bool(active))

    def _on_tag_toggled(self, tag, checked):
        current = self._active_tag_values()
        tag_key = str(tag or "").strip().lower()
        if not tag_key:
            return
        if checked and tag_key not in current:
            current.append(tag_key)
        elif not checked and tag_key in current:
            current = [item for item in current if item != tag_key]
        self._config.set_widget_browser_filters(tags=current)
        self.refresh()

    def _clear_active_tags(self):
        self._config.set_widget_browser_filters(tags=[])
        self._sync_tags_from_config()
        self.refresh()

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
        self._sync_organizers()
        self._sync_tags_from_config()
        items = self._filtered_items()
        self._rebuild_cards(items)
        self._update_browser_stats(len(items))
        self._update_quick_lanes()

    def _update_insert_target(self):
        self._insert_target.setText(f"Insert target: {self._insert_target_label}")

    def _set_chip_text(self, chip, text, tone=None):
        chip.setText(text)
        if tone is not None:
            chip.setProperty("chipTone", tone)
        chip.style().unpolish(chip)
        chip.style().polish(chip)
        chip.update()

    def _update_browser_stats(self, visible_count):
        total = len(self._registry.browser_items(addable_only=True))
        favorites = len(self._config.widget_browser_favorites)
        recent = len(self._config.widget_browser_recent)
        active_filters = (
            bool((self._search.text() or "").strip())
            or bool(self._active_tag_values())
            or self._selected_category() != "all"
            or self._complexity_filter != "all"
        )
        tone = "accent" if active_filters else "success"
        self._set_chip_text(self._visible_count_chip, f"Visible {visible_count}/{total}", tone)
        self._set_chip_text(self._favorites_count_chip, f"Favorites {favorites}", "success" if favorites else "accent")
        self._set_chip_text(self._recent_count_chip, f"Recent {recent}", "warning" if recent else "accent")

    def _lane_counts(self):
        items = self._registry.browser_items(addable_only=True)
        favorites = set(self._config.widget_browser_favorites)
        recent = set(self._config.widget_browser_recent)
        counts = {
            "all": len(items),
            "favorites": 0,
            "recent": 0,
            "containers": 0,
        }
        for item in items:
            type_name = item.get("type_name")
            if type_name in favorites:
                counts["favorites"] += 1
            if type_name in recent:
                counts["recent"] += 1
            if bool(item.get("is_container")):
                counts["containers"] += 1
            scenario = str(item.get("scenario", "") or "").strip()
            if scenario:
                lane_id = f"scenario:{scenario}".lower()
                counts[lane_id] = counts.get(lane_id, 0) + 1
        return counts

    def _update_quick_lanes(self):
        if not self._lane_buttons:
            return
        selected = str(self._selected_category() or "all").strip().lower()
        counts = self._lane_counts()
        for lane_id, button in self._lane_buttons.items():
            base_label = button.text().split("\n", 1)[0]
            count = int(counts.get(lane_id, 0) or 0)
            button.setText(f"{base_label}\n{count}")
            button.blockSignals(True)
            button.setChecked(lane_id == selected)
            button.blockSignals(False)
            button.setProperty("emptyLane", count == 0)
            button.style().unpolish(button)
            button.style().polish(button)
            button.update()

    def _on_category_changed(self, _row):
        if self._suspend_filter_persist:
            return
        category = self._selected_category()
        self._config.set_widget_browser_filters(scenario=category)
        self.refresh()

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
        elif category == "containers":
            items = [item for item in items if item.get("is_container")]
        elif str(category).startswith("scenario:"):
            selected_scenario = str(category).split(":", 1)[1].strip().lower()
            items = [item for item in items if str(item.get("scenario", "")).strip().lower() == selected_scenario]
        elif category != "all":
            items = [item for item in items if str(item.get("category", "")).strip().lower() == str(category).strip().lower()]

        active_tags = set(self._active_tag_values())
        if active_tags:
            tagged_items = []
            for item in items:
                item_tags = {str(tag or "").strip().lower() for tag in item.get("tags", []) if str(tag or "").strip()}
                if active_tags.issubset(item_tags):
                    tagged_items.append(item)
            items = tagged_items

        if self._complexity_filter != "all":
            selected_complexity = str(self._complexity_filter or "").strip().lower()
            items = [item for item in items if str(item.get("complexity", "") or "").strip().lower() == selected_complexity]

        if search:
            filtered = []
            for item in items:
                haystack = " ".join(
                    [
                        item.get("display_name", ""),
                        item.get("type_name", ""),
                        item.get("category", ""),
                        item.get("scenario", ""),
                    ]
                    + list(item.get("keywords", []))
                    + list(item.get("tags", []))
                ).lower()
                if search in haystack:
                    filtered.append(item)
            items = filtered

        if category != "recent":
            items = self._sort_items(items, search, favorite_types, recent_types, self._sort_mode)

        return items

    def _sort_items(self, items, search, favorite_types, recent_types, sort_mode="relevance"):
        mode = str(sort_mode or "relevance").strip().lower()
        if mode == "name":
            return sorted(
                items,
                key=lambda item: (
                    str(item.get("display_name", "")).lower(),
                    int(item.get("browse_priority", 999) or 999),
                ),
            )
        if mode == "complexity":
            rank = {"basic": 0, "intermediate": 1, "advanced": 2}
            return sorted(
                items,
                key=lambda item: (
                    rank.get(str(item.get("complexity", "") or "").strip().lower(), 9),
                    str(item.get("display_name", "")).lower(),
                    int(item.get("browse_priority", 999) or 999),
                ),
            )

        search_text = str(search or "").strip().lower()
        recent_order = {name: index for index, name in enumerate(recent_types)}

        def _score(item):
            display_name = str(item.get("display_name", "") or "").lower()
            type_name = str(item.get("type_name", "") or "").lower()
            is_exact = 0 if search_text and search_text in {display_name, type_name} else 1
            is_prefix = 0 if search_text and (display_name.startswith(search_text) or type_name.startswith(search_text)) else 1
            favorite_rank = 0 if item.get("type_name") in favorite_types else 1
            recent_rank = recent_order.get(item.get("type_name"), 999)
            browse_priority = int(item.get("browse_priority", 999) or 999)
            return (
                is_exact,
                is_prefix,
                favorite_rank,
                recent_rank,
                browse_priority,
                display_name,
            )

        return sorted(items, key=_score)

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
            empty = QFrame()
            empty.setObjectName("widget_browser_empty_state")
            empty_layout = QVBoxLayout(empty)
            empty_layout.setContentsMargins(20, 20, 20, 20)
            empty_layout.setSpacing(10)

            icon_label = QLabel()
            icon_label.setAlignment(Qt.AlignCenter)
            icon_label.setPixmap(make_icon("widgets", size=36).pixmap(36, 36))
            empty_layout.addWidget(icon_label)

            title = QLabel("No widgets match the current filters.")
            title.setObjectName("workspace_section_title")
            title.setAlignment(Qt.AlignCenter)
            empty_layout.addWidget(title)

            hint = QLabel("Try clearing search text, removing tags, changing complexity, or switching to All Widgets.")
            hint.setObjectName("workspace_section_subtitle")
            hint.setWordWrap(True)
            hint.setAlignment(Qt.AlignCenter)
            empty_layout.addWidget(hint)

            action_row = QHBoxLayout()
            action_row.setContentsMargins(0, 0, 0, 0)
            action_row.setSpacing(8)
            reset_search_btn = QPushButton("Reset Search")
            reset_search_btn.clicked.connect(self._reset_search_only)
            action_row.addWidget(reset_search_btn)
            clear_tags_btn = QPushButton("Clear Tags")
            clear_tags_btn.clicked.connect(self._clear_active_tags)
            action_row.addWidget(clear_tags_btn)
            reset_organize_btn = QPushButton("Reset Organize")
            reset_organize_btn.clicked.connect(self._reset_organizers)
            action_row.addWidget(reset_organize_btn)
            show_all_btn = QPushButton("Show All Widgets")
            show_all_btn.clicked.connect(self._reset_all_filters)
            action_row.addWidget(show_all_btn)
            empty_layout.addLayout(action_row)
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

    def _set_category_by_id(self, category_id):
        target = str(category_id or "").strip().lower()
        for row in range(self._category_list.count()):
            item = self._category_list.item(row)
            value = str(item.data(Qt.UserRole) or "").strip().lower() if item is not None else ""
            if value == target:
                self._category_list.setCurrentRow(row)
                return

    def _reset_search_only(self):
        if self._search.text():
            self._search.setText("")

    def _reset_all_filters(self):
        self._suspend_filter_persist = True
        self._config.set_widget_browser_filters(scenario="all", tags=[])
        self._suspend_filter_persist = False
        self._set_sort_mode("relevance", refresh=False)
        self._set_complexity_filter("all", refresh=False)
        self._search.setText("")
        self._sync_tags_from_config()
        self._set_category_by_id("all")
        self.refresh()
