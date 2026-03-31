"""Widget browser with categories, search, favorites, recents, and preview cards."""

from __future__ import annotations

from PyQt5.QtCore import pyqtSignal, Qt, QPoint, QMimeData
from PyQt5.QtGui import QDrag
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

from qfluentwidgets import SearchLineEdit

from ..model.config import get_config
from ..model.widget_registry import WidgetRegistry
from ..services.component_catalog import ComponentCatalog
from ..services.search_service import SearchService, SearchQuery
from ..services.recent_service import RecentService
from ..services.favorite_service import FavoriteService
from .iconography import make_icon, widget_icon_key


def _set_widget_metadata(widget, *, tooltip=None, accessible_name=None):
    if tooltip is not None:
        widget.setToolTip(tooltip)
        widget.setStatusTip(tooltip)
    if accessible_name is not None:
        widget.setAccessibleName(accessible_name)


def _set_item_metadata(item, tooltip):
    hint = str(tooltip or "").strip()
    item.setToolTip(hint)
    item.setStatusTip(hint)
    item.setData(Qt.AccessibleTextRole, hint)


def _count_label(count, singular, plural=None):
    value = max(int(count or 0), 0)
    noun = singular if value == 1 else (plural or f"{singular}s")
    return f"{value} {noun}"


class WidgetBrowserCard(QFrame):
    """Single widget entry card used by the browser grid."""

    clicked = pyqtSignal(str)
    insert_requested = pyqtSignal(str)
    favorite_toggled = pyqtSignal(str)
    menu_requested = pyqtSignal(str, object)
    drag_requested = pyqtSignal(str, QPoint)

    def __init__(self, item, parent=None):
        super().__init__(parent)
        self._item = dict(item or {})
        self._selected = False
        self._drag_start_pos = QPoint()
        self._init_ui()

    @property
    def type_name(self):
        return self._item.get("type_name", "")

    def _init_ui(self):
        self.setObjectName("widget_browser_card")
        self.setProperty("selected", False)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        self._icon_label = QLabel()
        self._icon_label.setPixmap(make_icon(self._item.get("icon_key") or widget_icon_key(self.type_name), size=18).pixmap(18, 18))
        layout.addWidget(self._icon_label, 0, Qt.AlignVCenter)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(1)

        self._title_label = QLabel(self._item.get("display_name", self.type_name))
        self._title_label.setObjectName("widget_browser_card_title")
        text_layout.addWidget(self._title_label)

        scenario = str(self._item.get("scenario", "") or "").strip()
        meta_parts = []
        if scenario:
            meta_parts.append(self._shorten_scenario_label(scenario))
        if bool(self._item.get("is_container")):
            meta_parts.append("Container")
        self._has_meta = bool(meta_parts)
        self._meta_label = QLabel(" · ".join(meta_parts))
        self._meta_label.setObjectName("widget_browser_card_meta")
        self._meta_label.setVisible(False)
        text_layout.addWidget(self._meta_label)

        layout.addLayout(text_layout, 1)

        self._insert_btn = QPushButton("Insert")
        self._insert_btn.setObjectName("widget_browser_insert_button")
        self._insert_btn.clicked.connect(lambda: self.insert_requested.emit(self.type_name))
        layout.addWidget(self._insert_btn, 0, Qt.AlignVCenter)

        self._favorite_btn = QToolButton()
        self._favorite_btn.setObjectName("widget_browser_favorite_button")
        self._favorite_btn.setCheckable(True)
        self._favorite_btn.setText("*")
        self._favorite_btn.toggled.connect(lambda _checked: self.favorite_toggled.emit(self.type_name))
        layout.addWidget(self._favorite_btn, 0, Qt.AlignVCenter)

        self._update_accessibility_summary()

    @staticmethod
    def _shorten_scenario_label(scenario: str) -> str:
        """Shorten scenario pill text for card visual simplicity."""
        s = (scenario or "").strip()
        mapping = {
            "Feedback & Status": "Status",
            "Data & Visualization": "Data",
            "Media & Content": "Media",
            "Navigation & Flow": "Navigation",
            "Input & Forms": "Input",
            "Layout & Containers": "Layout",
            "Decoration": "Decor",
        }
        return mapping.get(s, s.split("&", 1)[0].strip() or s)

    def _display_name(self):
        return str(self._item.get("display_name", self.type_name) or self.type_name)

    def _card_summary(self):
        category = str(self._item.get("category", "") or "Uncategorized").strip() or "Uncategorized"
        scenario = str(self._item.get("scenario", "") or "General").strip() or "General"
        complexity = str(self._item.get("complexity", "") or "unknown").strip().title() or "Unknown"
        container_text = "yes" if bool(self._item.get("is_container")) else "no"
        favorite_text = "yes" if self._favorite_btn.isChecked() else "no"
        selected_text = "yes" if self._selected else "no"
        return (
            f"Widget card: {self._display_name()}. Category {category}. Scenario {scenario}. "
            f"Complexity {complexity}. Container {container_text}. Favorite {favorite_text}. Selected {selected_text}."
        )

    def _update_accessibility_summary(self):
        display_name = self._display_name()
        summary = self._card_summary()
        favorite_hint = (
            f"Remove {display_name} from favorites."
            if self._favorite_btn.isChecked()
            else f"Add {display_name} to favorites."
        )
        self._meta_label.setVisible(self._selected and self._has_meta)
        self._insert_btn.setVisible(self._selected)
        self._favorite_btn.setVisible(self._selected or self._favorite_btn.isChecked())
        self._icon_label.setVisible(self._selected)
        _set_widget_metadata(
            self,
            tooltip=f"{summary} Click to select. Double-click to insert.",
            accessible_name=summary,
        )
        _set_widget_metadata(self._title_label, tooltip=summary, accessible_name=f"Widget name: {display_name}")
        # keywords_label intentionally removed for visual simplicity
        _set_widget_metadata(
            self._favorite_btn,
            tooltip=favorite_hint,
            accessible_name=f"Favorite toggle: {display_name}",
        )
        _set_widget_metadata(
            self._insert_btn,
            tooltip=f"Insert {display_name} into the current target.",
            accessible_name=f"Insert {display_name}",
        )
        _set_widget_metadata(
            self,
            tooltip=f"{summary} Drag to insert {display_name} into the canvas.",
            accessible_name=summary,
        )

    def set_selected(self, selected):
        self._selected = bool(selected)
        self.setProperty("selected", self._selected)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()
        self._update_accessibility_summary()

    def set_favorite(self, favorite):
        self._favorite_btn.blockSignals(True)
        self._favorite_btn.setChecked(bool(favorite))
        self._favorite_btn.blockSignals(False)
        self._update_accessibility_summary()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start_pos = event.pos()
            self.clicked.emit(self.type_name)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton):
            super().mouseMoveEvent(event)
            return
        if (event.pos() - self._drag_start_pos).manhattanLength() < 8:
            super().mouseMoveEvent(event)
            return
        self.drag_requested.emit(self.type_name, event.globalPos())
        super().mouseMoveEvent(event)

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

    WIDGET_DRAG_MIME = "application/x-egui-widget-type"

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
        self._catalog = ComponentCatalog(self._registry)
        self._search_service = SearchService()
        self._recent_service = RecentService(self._config)
        self._favorite_service = FavoriteService(self._config)
        self._selected_type = ""
        self._insert_target_label = "Current page root"
        self._cards = {}
        self._tag_buttons = {}
        self._lane_buttons = {}
        self._sort_buttons = {}
        self._complexity_buttons = {}
        self._sort_mode = self._normalize_sort_mode(getattr(self._config, "widget_browser_sort_mode", "relevance"))
        self._complexity_filter = self._normalize_complexity_filter(
            getattr(self._config, "widget_browser_complexity_filter", "all")
        )
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

        self._title_label = QLabel("Widget Browser")
        self._title_label.setObjectName("workspace_section_title")
        header_layout.addWidget(self._title_label)

        self._subtitle_label = QLabel("Browse by scenario, filter by tags, and insert directly into the selected target.")
        self._subtitle_label.setObjectName("workspace_section_subtitle")
        self._subtitle_label.setWordWrap(True)
        header_layout.addWidget(self._subtitle_label)

        self._insert_target = QLabel("")
        self._insert_target.setObjectName("workspace_status_chip")
        self._insert_target.setWordWrap(True)
        header_layout.addWidget(self._insert_target)

        stats_row = QHBoxLayout()
        stats_row.setContentsMargins(0, 0, 0, 0)
        stats_row.setSpacing(8)
        self._visible_count_chip = QLabel("Visible 0")
        self._visible_count_chip.setObjectName("widget_browser_stat_text")
        self._favorites_count_chip = QLabel("Favorites 0")
        self._favorites_count_chip.setObjectName("widget_browser_stat_text")
        self._recent_count_chip = QLabel("Recent 0")
        self._recent_count_chip.setObjectName("widget_browser_stat_text")
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
        self._lanes_title = QLabel("Quick Lanes")
        self._lanes_title.setObjectName("workspace_section_subtitle")
        lanes_layout.addWidget(self._lanes_title)
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
        self._sort_title = QLabel("Sort")
        self._sort_title.setObjectName("workspace_section_subtitle")
        sort_row.addWidget(self._sort_title)
        self._sort_host = QWidget()
        self._sort_layout = QHBoxLayout(self._sort_host)
        self._sort_layout.setContentsMargins(0, 0, 0, 0)
        self._sort_layout.setSpacing(6)
        sort_row.addWidget(self._sort_host, 1)
        organize_layout.addLayout(sort_row)

        complexity_row = QHBoxLayout()
        complexity_row.setContentsMargins(0, 0, 0, 0)
        complexity_row.setSpacing(6)
        self._complexity_title = QLabel("Complexity")
        self._complexity_title.setObjectName("workspace_section_subtitle")
        complexity_row.addWidget(self._complexity_title)
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
        self._cards_layout.setHorizontalSpacing(0)
        self._cards_layout.setVerticalSpacing(6)
        self._scroll.setWidget(self._cards_container)

        layout.addLayout(body, 1)

        tags_frame = QFrame()
        tags_frame.setObjectName("widget_browser_tags")
        tags_layout = QHBoxLayout(tags_frame)
        tags_layout.setContentsMargins(10, 8, 10, 8)
        tags_layout.setSpacing(6)
        self._tags_title = QLabel("Tags")
        self._tags_title.setObjectName("workspace_section_subtitle")
        tags_layout.addWidget(self._tags_title)
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

        self._category_list.setAccessibleName("Widget categories")
        self._scroll.setAccessibleName("Widget browser results")
        self._cards_container.setAccessibleName("Widget browser cards")
        self._search.setAccessibleName("Widget browser search")
        self._clear_tags_btn.setAccessibleName("Clear widget tags")
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
            _set_item_metadata(item, f"Show {label} in the widget browser.")
            self._category_list.addItem(item)
        for label in self._catalog.browser_scenarios():
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, f"scenario:{label}")
            icon_key = self._scenario_icon_key(label)
            item.setIcon(make_icon(icon_key, size=18))
            _set_item_metadata(item, f"Show widgets for the {label} scenario.")
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
        for scenario in self._catalog.browser_scenarios():
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
            is_current = mode == self._sort_mode
            tooltip = f"Sort visible widgets by {button.text()}."
            if is_current:
                tooltip += " Current sort mode."
            accessible_name = f"Sort mode: {button.text()}. {'Current.' if is_current else 'Available.'}"
            _set_widget_metadata(
                button,
                tooltip=tooltip,
                accessible_name=accessible_name,
            )
        for level, button in self._complexity_buttons.items():
            button.blockSignals(True)
            button.setChecked(level == self._complexity_filter)
            button.blockSignals(False)
            is_current = level == self._complexity_filter
            tooltip = f"Filter visible widgets by {button.text()} complexity."
            if is_current:
                tooltip += " Current complexity filter."
            accessible_name = f"Complexity filter: {button.text()}. {'Current.' if is_current else 'Available.'}"
            _set_widget_metadata(
                button,
                tooltip=tooltip,
                accessible_name=accessible_name,
            )

    def _normalize_sort_mode(self, mode):
        value = str(mode or "").strip().lower()
        valid = {key for key, _label in self._SORT_MODES}
        return value if value in valid else "relevance"

    def _normalize_complexity_filter(self, level):
        value = str(level or "").strip().lower()
        valid = {key for key, _label in self._COMPLEXITY_LEVELS}
        return value if value in valid else "all"

    def _set_sort_mode(self, mode, refresh=True, persist=True):
        normalized = self._normalize_sort_mode(mode)
        changed = normalized != self._sort_mode
        self._sort_mode = normalized
        self._sync_organizers()
        if changed and persist:
            self._config.set_widget_browser_organizers(sort_mode=self._sort_mode)
        if refresh:
            self.refresh()

    def _set_complexity_filter(self, level, refresh=True, persist=True):
        normalized = self._normalize_complexity_filter(level)
        changed = normalized != self._complexity_filter
        self._complexity_filter = normalized
        self._sync_organizers()
        if changed and persist:
            self._config.set_widget_browser_organizers(complexity=self._complexity_filter)
        if refresh:
            self.refresh()

    def _reset_organizers(self):
        changed = False
        if self._sort_mode != "relevance":
            self._set_sort_mode("relevance", refresh=False, persist=False)
            changed = True
        if self._complexity_filter != "all":
            self._set_complexity_filter("all", refresh=False, persist=False)
            changed = True
        if changed:
            self._config.set_widget_browser_organizers(sort_mode=self._sort_mode, complexity=self._complexity_filter)
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
        return self._catalog.top_tags(addable_only=True, limit=18)

    def _active_tag_values(self):
        return [str(tag or "").strip().lower() for tag in getattr(self._config, "widget_browser_active_tags", []) if str(tag or "").strip()]

    def _sync_tags_from_config(self):
        active = set(self._active_tag_values())
        for tag, button in self._tag_buttons.items():
            button.blockSignals(True)
            button.setChecked(tag in active)
            button.blockSignals(False)
            tooltip = f"Filter widgets by tag {button.text()}."
            tooltip += " Tag is active." if tag in active else " Tag is inactive."
            accessible_name = f"Widget tag: {button.text()}. {'Active.' if tag in active else 'Inactive.'}"
            _set_widget_metadata(
                button,
                tooltip=tooltip,
                accessible_name=accessible_name,
            )
        self._clear_tags_btn.setEnabled(bool(active))
        clear_hint = "Clear active widget tags." if active else "No active widget tags to clear."
        _set_widget_metadata(
            self._clear_tags_btn,
            tooltip=clear_hint,
            accessible_name="Clear widget tags" if active else "Clear widget tags unavailable",
        )

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
        self._recent_service.record_insert(widget_type)
        self.refresh()

    def recent_types(self):
        return list(self._recent_service.list_recent_types())

    def favorite_types(self):
        return self._favorite_service.list_favorites()

    def refresh(self):
        self._sync_organizers()
        self._sync_tags_from_config()
        items = self._filtered_items()
        self._rebuild_cards(items)
        self._update_browser_stats(len(items))
        self._update_quick_lanes()
        self._update_accessibility_summary(len(items))

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
        _set_widget_metadata(
            self._visible_count_chip,
            tooltip=f"Visible widgets: {visible_count} of {total}.",
            accessible_name=f"Visible widgets: {self._visible_count_chip.text()}",
        )
        _set_widget_metadata(
            self._favorites_count_chip,
            tooltip=f"Favorite widget types: {favorites}.",
            accessible_name=f"Favorite widgets: {self._favorites_count_chip.text()}",
        )
        _set_widget_metadata(
            self._recent_count_chip,
            tooltip=f"Recently inserted widget types: {recent}.",
            accessible_name=f"Recent widgets: {self._recent_count_chip.text()}",
        )

    def _lane_counts(self):
        return self._catalog.lane_counts(
            addable_only=True,
            favorite_types=set(self._config.widget_browser_favorites),
            recent_types=list(self._config.widget_browser_recent),
        )

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
            count_text = _count_label(count, "widget")
            tooltip = f"Quick lane {base_label}: {count_text}."
            if lane_id == selected:
                tooltip += " Current lane."
            elif count == 0:
                tooltip += " No widgets available."
            accessible_name = (
                f"Quick lane: {base_label}. {count_text}. Current lane."
                if lane_id == selected
                else f"Quick lane: {base_label}. {count_text}. {'No widgets available.' if count == 0 else 'Available.'}"
            )
            _set_widget_metadata(
                button,
                tooltip=tooltip,
                accessible_name=accessible_name,
            )

    def _sort_label(self):
        return {key: label for key, label in self._SORT_MODES}.get(self._sort_mode, "Recommended")

    def _complexity_label(self):
        return {key: label for key, label in self._COMPLEXITY_LEVELS}.get(self._complexity_filter, "All")

    def _selected_category_label(self):
        item = self._category_list.currentItem()
        return str(item.text() or "All Widgets") if item is not None else "All Widgets"

    def _selected_tag_labels(self):
        return sorted(button.text() for button in self._tag_buttons.values() if button.isChecked())

    def _selected_card_label(self):
        for card in self._cards.values():
            if card.type_name == self._selected_type:
                return str(card._item.get("display_name", card.type_name) or card.type_name)
        return ""

    def _update_accessibility_summary(self, visible_count=None):
        visible = len(self._cards) if visible_count is None else max(int(visible_count or 0), 0)
        category_label = self._selected_category_label()
        search_text = str(self._search.text() or "").strip() or "none"
        tags_text = ", ".join(self._selected_tag_labels()) or "none"
        selected_text = self._selected_card_label() or "none"
        visible_text = _count_label(visible, "visible widget", "visible widgets")
        summary = (
            f"Widget Browser: {visible_text}. Category: {category_label}. Search: {search_text}. "
            f"Sort: {self._sort_label()}. Complexity: {self._complexity_label()}. "
            f"Tags: {tags_text}. Insert target: {self._insert_target_label}. Selected: {selected_text}."
        )
        results_summary = f"Widget browser results: {_count_label(visible, 'card')} visible."
        if selected_text != "none":
            results_summary += f" Selected widget: {selected_text}."

        _set_widget_metadata(self, tooltip=summary, accessible_name=summary)
        _set_widget_metadata(self._title_label, tooltip=summary, accessible_name=self._title_label.text())
        _set_widget_metadata(
            self._subtitle_label,
            tooltip=self._subtitle_label.text(),
            accessible_name=self._subtitle_label.text(),
        )
        _set_widget_metadata(
            self._insert_target,
            tooltip=f"Current insert target: {self._insert_target_label}",
            accessible_name=f"Insert target: {self._insert_target_label}",
        )
        _set_widget_metadata(
            self._search,
            tooltip=f"Widget browser search. Current text: {search_text}.",
            accessible_name=f"Widget browser search: {search_text}.",
        )
        _set_widget_metadata(
            self._category_list,
            tooltip=f"Widget categories. Current category: {category_label}.",
            accessible_name=f"Widget categories: {category_label}",
        )
        _set_widget_metadata(self._scroll, tooltip=results_summary, accessible_name=results_summary)
        _set_widget_metadata(self._cards_container, tooltip=results_summary, accessible_name=results_summary)
        _set_widget_metadata(
            self._lanes_title,
            tooltip="Quick lanes switch the main widget browser category.",
            accessible_name=f"Quick Lanes: current category {category_label}.",
        )
        _set_widget_metadata(
            self._sort_title,
            tooltip=f"Current sort mode: {self._sort_label()}",
            accessible_name=f"Sort: {self._sort_label()}",
        )
        _set_widget_metadata(
            self._complexity_title,
            tooltip=f"Current complexity filter: {self._complexity_label()}",
            accessible_name=f"Complexity: {self._complexity_label()}",
        )
        _set_widget_metadata(
            self._tags_title,
            tooltip=f"Active widget tags: {tags_text}.",
            accessible_name=f"Tags: {tags_text}.",
        )

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
        search = (self._search.text() or "").strip()
        category = str(self._selected_category() or "all").strip().lower()
        favorite_types = set(self._favorite_service.list_favorites())
        recent_types = list(self._recent_service.list_recent_types())
        recent_lookup = set(recent_types)
        metas = self._catalog.list_components(addable_only=True)

        scenario_filter = "all"
        category_filter = "all"
        if category == "favorites":
            metas = [item for item in metas if item.type_name in favorite_types]
        elif category == "recent":
            order = {name: index for index, name in enumerate(recent_types)}
            metas = [item for item in metas if item.type_name in recent_lookup]
            metas.sort(key=lambda item: order.get(item.type_name, 999))
        elif category == "containers":
            category_filter = "containers"
        elif category.startswith("scenario:"):
            scenario_filter = category
        elif category != "all":
            category_filter = category

        query = SearchQuery(
            text=search,
            category=category_filter,
            scenario=scenario_filter,
            complexity=self._complexity_filter,
            tags=tuple(self._active_tag_values()),
            sort_mode=self._sort_mode,
        )
        if category != "recent":
            metas = self._search_service.filter_and_sort(
                metas,
                query,
                favorite_types=favorite_types,
                recent_types=recent_types,
            )
        else:
            metas = self._search_service.filter_and_sort(
                metas,
                SearchQuery(
                    text=search,
                    category="all",
                    scenario="all",
                    complexity=self._complexity_filter,
                    tags=tuple(self._active_tag_values()),
                    sort_mode="relevance",
                ),
                favorite_types=favorite_types,
                recent_types=recent_types,
            )

        return [
            {
                "type_name": item.type_name,
                "display_name": item.display_name,
                "category": item.category,
                "scenario": item.scenario,
                "tags": list(item.tags),
                "keywords": list(item.keywords),
                "complexity": item.complexity,
                "icon_key": item.icon_key,
                "preview_kind": item.preview_kind,
                "browse_priority": item.browse_priority,
                "is_container": item.is_container,
            }
            for item in metas
        ]

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

    def _build_group_header(self, scenario, item_count):
        frame = QFrame()
        frame.setObjectName("widget_browser_group_header")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(8)
        icon_label = QLabel()
        icon_label.setPixmap(make_icon(self._scenario_icon_key(scenario), size=16).pixmap(16, 16))
        layout.addWidget(icon_label, 0, Qt.AlignVCenter)
        title = QLabel(str(scenario or "Other"))
        title.setObjectName("widget_browser_group_title")
        layout.addWidget(title, 0, Qt.AlignVCenter)
        count_chip = QLabel(str(max(int(item_count or 0), 0)))
        count_chip.setObjectName("workspace_status_chip")
        count_chip.setProperty("chipTone", "accent")
        layout.addWidget(count_chip, 0, Qt.AlignVCenter)
        layout.addStretch()
        group_summary = f"Scenario group: {scenario or 'Other'}. {_count_label(item_count, 'widget')}."
        _set_widget_metadata(frame, tooltip=group_summary, accessible_name=group_summary)
        _set_widget_metadata(title, tooltip=group_summary, accessible_name=f"Scenario group: {title.text()}")
        _set_widget_metadata(
            count_chip,
            tooltip=group_summary,
            accessible_name=f"Scenario group count: {count_chip.text()}",
        )
        return frame

    def _should_group_by_scenario(self):
        return (
            self._selected_category() == "all"
            and not bool((self._search.text() or "").strip())
            and not bool(self._active_tag_values())
            and self._complexity_filter == "all"
            and self._sort_mode == "relevance"
        )


    def _rebuild_cards(self, items):
        self._clear_cards()
        favorites = set(self._config.widget_browser_favorites)
        columns = 1
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
            _set_widget_metadata(
                reset_search_btn,
                tooltip="Clear the current widget browser search text.",
                accessible_name="Reset widget browser search",
            )
            action_row.addWidget(reset_search_btn)
            clear_tags_btn = QPushButton("Clear Tags")
            clear_tags_btn.clicked.connect(self._clear_active_tags)
            _set_widget_metadata(
                clear_tags_btn,
                tooltip="Clear active widget browser tags.",
                accessible_name="Clear widget browser tags",
            )
            action_row.addWidget(clear_tags_btn)
            reset_organize_btn = QPushButton("Reset Organize")
            reset_organize_btn.clicked.connect(self._reset_organizers)
            _set_widget_metadata(
                reset_organize_btn,
                tooltip="Reset sort mode and complexity filters.",
                accessible_name="Reset widget browser organize filters",
            )
            action_row.addWidget(reset_organize_btn)
            show_all_btn = QPushButton("Show All Widgets")
            show_all_btn.clicked.connect(self._reset_all_filters)
            _set_widget_metadata(
                show_all_btn,
                tooltip="Reset every widget browser filter and show all widgets.",
                accessible_name="Show all widgets",
            )
            action_row.addWidget(show_all_btn)
            empty_layout.addLayout(action_row)
            _set_widget_metadata(
                empty,
                tooltip="No widgets match the current widget browser filters.",
                accessible_name="No widgets match the current filters.",
            )
            _set_widget_metadata(title, tooltip=title.text(), accessible_name=title.text())
            _set_widget_metadata(hint, tooltip=hint.text(), accessible_name=hint.text())
            self._cards_layout.addWidget(empty, 0, 0, 1, columns)
            return

        visible_types = [item.get("type_name", "") for item in items]
        if self._selected_type not in visible_types:
            self._selected_type = visible_types[0]

        grouped = self._catalog.group_by_scenario(items) if self._should_group_by_scenario() else [("", items)]
        row = 0
        column = 0
        card_index = 0
        for scenario, group_items in grouped:
            if scenario:
                header = self._build_group_header(scenario, len(group_items))
                self._cards_layout.addWidget(header, row, 0, 1, columns)
                row += 1
                column = 0
            for item in group_items:
                card = WidgetBrowserCard(item)
                card.set_favorite(item.get("type_name") in favorites)
                card.clicked.connect(self._select_card)
                card.insert_requested.connect(self.insert_requested.emit)
                card.favorite_toggled.connect(self._toggle_favorite)
                card.menu_requested.connect(self._show_card_menu)
                card.drag_requested.connect(self._start_widget_drag)
                self._cards_layout.addWidget(card, row, column)
                self._cards[card_index] = card
                card.set_selected(card.type_name == self._selected_type)
                card_index += 1
                column += 1
                if column >= columns:
                    column = 0
                    row += 1
            if column != 0:
                row += 1
                column = 0

        self._cards_layout.setColumnStretch(0, 1)

    def _select_card(self, widget_type):
        self._selected_type = widget_type
        for card in self._cards.values():
            card.set_selected(card.type_name == widget_type)
        self._update_accessibility_summary()

    def _toggle_favorite(self, widget_type):
        self._favorite_service.toggle(widget_type)
        self.refresh()

    def _show_card_menu(self, widget_type, global_pos):
        self._select_card(widget_type)
        is_favorite = widget_type in set(self._config.widget_browser_favorites)
        menu = QMenu(self)
        insert_action = menu.addAction("Insert")
        favorite_action = menu.addAction("Unfavorite" if is_favorite else "Favorite")
        reveal_action = menu.addAction("Reveal in Structure")
        drag_action = menu.addAction("Drag to Canvas")
        chosen = menu.exec_(global_pos)
        if chosen == insert_action:
            self.insert_requested.emit(widget_type)
        elif chosen == favorite_action:
            self._toggle_favorite(widget_type)
        elif chosen == reveal_action:
            self.reveal_requested.emit(widget_type)
        elif chosen == drag_action:
            self._start_widget_drag(widget_type, global_pos)

    def _start_widget_drag(self, widget_type, global_pos=None):
        widget_type = str(widget_type or "").strip()
        if not widget_type:
            return
        self._select_card(widget_type)
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData(self.WIDGET_DRAG_MIME, widget_type.encode("utf-8"))
        drag.setMimeData(mime)
        item = self._catalog.by_type(widget_type)
        if item is not None:
            drag.setPixmap(make_icon(item.icon_key or widget_icon_key(widget_type), size=18).pixmap(18, 18))
            drag.setHotSpot(QPoint(9, 9))
        if global_pos is not None:
            self.statusTip()  # keep QObject state touched for accessibility update rhythm
        drag.exec_(Qt.CopyAction)

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
        self._set_sort_mode("relevance", refresh=False, persist=False)
        self._set_complexity_filter("all", refresh=False, persist=False)
        self._config.set_widget_browser_organizers(sort_mode=self._sort_mode, complexity=self._complexity_filter)
        self._search.setText("")
        self._sync_tags_from_config()
        self._set_category_by_id("all")
        self.refresh()
