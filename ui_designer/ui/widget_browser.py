"""Simplified widget browser with search, type categories, favorites, and recents."""

from __future__ import annotations

from PyQt5.QtCore import QMimeData, QPoint, QSignalBlocker, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QDrag
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from qfluentwidgets import ComboBox, SearchLineEdit

from ..model.config import get_config
from ..services.component_catalog import ComponentCatalog
from ..services.favorite_service import FavoriteService
from ..services.recent_service import RecentService
from ..services.search_service import SearchQuery, SearchService
from .iconography import make_icon, widget_icon_key
from .theme import theme_tokens

_DEFAULT_UI_TOKENS = theme_tokens("dark")
_SPACE_XXS = int(_DEFAULT_UI_TOKENS.get("space_xxs", 2))
_SPACE_XS = int(_DEFAULT_UI_TOKENS.get("space_xs", 4))
_SPACE_SM = int(_DEFAULT_UI_TOKENS.get("space_sm", 8))
_SPACE_MD = int(_DEFAULT_UI_TOKENS.get("space_md", 12))
_SPACE_LG = int(_DEFAULT_UI_TOKENS.get("space_lg", 16))
_ICON_MD = int(_DEFAULT_UI_TOKENS.get("icon_md", 18))


def _set_widget_metadata(widget, *, tooltip=None, accessible_name=None):
    if tooltip is not None:
        resolved_tooltip = str(tooltip or "")
        current_tooltip = widget.property("_widget_browser_tooltip_snapshot")
        if current_tooltip is None or str(current_tooltip) != resolved_tooltip:
            widget.setToolTip(resolved_tooltip)
            widget.setStatusTip(resolved_tooltip)
            widget.setProperty("_widget_browser_tooltip_snapshot", resolved_tooltip)
    if accessible_name is not None:
        resolved_accessible_name = str(accessible_name or "")
        current_accessible_name = widget.property("_widget_browser_accessible_snapshot")
        if current_accessible_name is None or str(current_accessible_name) != resolved_accessible_name:
            widget.setAccessibleName(resolved_accessible_name)
            widget.setProperty("_widget_browser_accessible_snapshot", resolved_accessible_name)


def _set_widget_visible(widget, visible):
    value = bool(visible)
    current_value = widget.property("_widget_browser_visible_snapshot")
    if current_value is not None and bool(current_value) == value:
        return
    widget.setVisible(value)
    widget.setProperty("_widget_browser_visible_snapshot", value)


def _count_label(count, singular, plural=None):
    value = max(int(count or 0), 0)
    noun = singular if value == 1 else (plural or f"{singular}s")
    return f"{value} {noun}"


class WidgetBrowserCard(QFrame):
    """Single simplified widget row."""

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
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(0)

        self._title_label = QLabel(self._item.get("display_name", self.type_name))
        self._title_label.setObjectName("widget_browser_card_title")
        text_layout.addWidget(self._title_label)

        meta_text = "Container" if bool(self._item.get("is_container")) else ""
        self._meta_label = QLabel(meta_text)
        self._meta_label.setObjectName("widget_browser_card_meta")
        self._meta_label.hide()
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

    def _display_name(self):
        return str(self._item.get("display_name", self.type_name) or self.type_name)

    def _card_summary(self):
        category = str(self._item.get("category", "") or "Uncategorized").strip() or "Uncategorized"
        container_text = "yes" if bool(self._item.get("is_container")) else "no"
        favorite_text = "yes" if self._favorite_btn.isChecked() else "no"
        selected_text = "yes" if self._selected else "no"
        return (
            f"Widget row: {self._display_name()}. Category {category}. "
            f"Container {container_text}. Favorite {favorite_text}. Selected {selected_text}."
        )

    def _update_accessibility_summary(self):
        display_name = self._display_name()
        summary = self._card_summary()
        favorite_hint = (
            f"Remove {display_name} from favorites."
            if self._favorite_btn.isChecked()
            else f"Add {display_name} to favorites."
        )
        _set_widget_visible(self._insert_btn, self._selected)
        _set_widget_visible(self._favorite_btn, self._selected or self._favorite_btn.isChecked())
        _set_widget_metadata(self._title_label, tooltip=summary, accessible_name=f"Widget name: {display_name}")
        _set_widget_metadata(
            self._meta_label,
            tooltip=self._meta_label.text(),
            accessible_name=f"Widget hint: {self._meta_label.text()}" if self._meta_label.text() else "Widget hint: none",
        )
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
    """Compact widget picker with category filter and search."""

    insert_requested = pyqtSignal(str)
    reveal_requested = pyqtSignal(str)

    WIDGET_DRAG_MIME = "application/x-egui-widget-type"
    _SEARCH_REFRESH_DEBOUNCE_MS = 90
    _CATEGORY_OPTIONS = (
        ("all", "All"),
        ("favorites", "Favorites"),
        ("recent", "Recent"),
        ("containers", "Containers"),
        ("basics", "Basics"),
        ("layout", "Layout"),
        ("input", "Input"),
        ("navigation", "Navigation"),
        ("display & data", "Display & Data"),
        ("media", "Media"),
        ("decoration", "Decoration"),
        ("custom", "Custom"),
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self._config = get_config()
        self._catalog = ComponentCatalog()
        self._search_service = SearchService()
        self._recent_service = RecentService(self._config)
        self._favorite_service = FavoriteService(self._config)
        self._selected_type = ""
        self._insert_target_label = "Current page root"
        self._cards = {}
        self._category_ids = []
        self._search_refresh_timer = QTimer(self)
        self._search_refresh_timer.setSingleShot(True)
        self._search_refresh_timer.timeout.connect(self.refresh)
        self._init_ui()
        self._populate_categories()
        self.refresh()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self._header_frame = QFrame()
        self._header_frame.setObjectName("widget_browser_header")
        self._header_frame.setProperty("panelTone", "components")
        header_layout = QVBoxLayout(self._header_frame)
        header_layout.setContentsMargins(2, 2, 2, 2)
        header_layout.setSpacing(2)

        self._header_eyebrow = QLabel("Components")
        self._header_eyebrow.setObjectName("widget_browser_header_eyebrow")
        header_layout.addWidget(self._header_eyebrow)
        self._header_eyebrow.hide()

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(2)

        self._title_label = QLabel("Components")
        self._title_label.setObjectName("workspace_section_title")
        title_row.addWidget(self._title_label)

        self._insert_target = QLabel("")
        self._insert_target.setObjectName("widget_browser_header_target")
        self._insert_target.setWordWrap(False)
        self._insert_target.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._insert_target.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        title_row.addStretch()
        title_row.addWidget(self._insert_target, 0, Qt.AlignVCenter)
        header_layout.addLayout(title_row)

        self._subtitle_label = QLabel("Browse by category and insert into the current target.")
        self._subtitle_label.setObjectName("widget_browser_header_meta")
        self._subtitle_label.setWordWrap(True)
        header_layout.addWidget(self._subtitle_label)
        self._subtitle_label.hide()

        self._metrics_frame = QFrame()
        self._metrics_frame.setObjectName("widget_browser_metrics_strip")
        metrics_layout = QHBoxLayout(self._metrics_frame)
        metrics_layout.setContentsMargins(0, 0, 0, 0)
        metrics_layout.setSpacing(2)

        self._visible_count_chip = QLabel("0 visible")
        self._visible_count_chip.setObjectName("workspace_status_chip")
        self._visible_count_chip.setProperty("chipTone", "accent")
        metrics_layout.addWidget(self._visible_count_chip)

        self._category_summary_chip = QLabel("All Components")
        self._category_summary_chip.setObjectName("workspace_status_chip")
        metrics_layout.addWidget(self._category_summary_chip)
        metrics_layout.addStretch()
        header_layout.addWidget(self._metrics_frame)

        self._filter_bar = QFrame()
        self._filter_bar.setObjectName("widget_browser_filter_bar")
        filter_layout = QHBoxLayout(self._filter_bar)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.setSpacing(2)

        self._search = SearchLineEdit()
        self._search.setPlaceholderText("Search")
        self._search.textChanged.connect(self._schedule_search_refresh)
        filter_layout.addWidget(self._search, 1)

        self._category_combo = ComboBox()
        self._category_combo.setObjectName("widget_browser_category_combo")
        self._category_combo.setMinimumWidth(144)
        self._category_combo.currentIndexChanged.connect(self._on_category_changed)
        filter_layout.addWidget(self._category_combo, 0)
        header_layout.addWidget(self._filter_bar)
        layout.addWidget(self._header_frame)

        self._scroll = QScrollArea()
        self._scroll.setObjectName("widget_browser_results")
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        layout.addWidget(self._scroll, 1)

        self._cards_container = QWidget()
        self._cards_container.setObjectName("widget_browser_results_host")
        self._cards_layout = QVBoxLayout(self._cards_container)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(2)
        self._scroll.setWidget(self._cards_container)

        self._search.setAccessibleName("Widget browser search")
        self._category_combo.setAccessibleName("Widget category picker")
        self._scroll.setAccessibleName("Widget browser results")
        self._cards_container.setAccessibleName("Widget browser cards")
        self._metrics_frame.hide()
        self._update_insert_target()

    def _normalize_category(self, category):
        value = str(category or "").strip().lower()
        valid = {category_id for category_id, _label in self._CATEGORY_OPTIONS}
        return value if value in valid else "all"

    def _populate_categories(self):
        blocker = QSignalBlocker(self._category_combo)
        self._category_combo.clear()
        self._category_ids = []
        for category_id, label in self._CATEGORY_OPTIONS:
            self._category_combo.addItem(label)
            self._category_ids.append(category_id)
        self._set_category_by_id(getattr(self._config, "widget_browser_active_category", "all"))
        del blocker

    def _selected_category(self):
        index = self._category_combo.currentIndex()
        if 0 <= index < len(self._category_ids):
            return self._normalize_category(self._category_ids[index])
        return "all"

    def _selected_category_label(self):
        label = str(self._category_combo.currentText() or "").strip()
        return label or "All"

    def _set_category_by_id(self, category_id):
        target = self._normalize_category(category_id)
        for index, value in enumerate(self._category_ids):
            value = self._normalize_category(value)
            if value == target:
                self._category_combo.setCurrentIndex(index)
                return

    def _schedule_search_refresh(self):
        if self._search_refresh_timer.isActive():
            self._search_refresh_timer.stop()
        self._search_refresh_timer.start(self._SEARCH_REFRESH_DEBOUNCE_MS)

    def _on_category_changed(self, _index):
        category = self._selected_category()
        if category != getattr(self._config, "widget_browser_active_category", "all"):
            self._config.set_widget_browser_active_category(category)
        self.refresh()

    def focus_search(self):
        self._search.setFocus()
        self._search.selectAll()

    def set_insert_target_label(self, label):
        self._insert_target_label = (label or "").strip() or "Current page root"
        self._update_insert_target()
        self._update_accessibility_summary(len(self._cards))

    def select_widget_type(self, widget_type):
        widget_type = str(widget_type or "").strip()
        if not widget_type:
            return
        self._selected_type = widget_type
        for card in self._cards.values():
            card.set_selected(card.type_name == widget_type)

    def record_insert(self, widget_type):
        if self._recent_service.record_insert(widget_type):
            self.refresh()

    def recent_types(self):
        return list(self._recent_service.list_recent_types())

    def favorite_types(self):
        return self._favorite_service.list_favorites()

    def refresh(self):
        if self._search_refresh_timer.isActive():
            self._search_refresh_timer.stop()
        items = self._filtered_items()
        self._rebuild_cards(items)
        self._update_accessibility_summary(len(items))

    def _update_insert_target(self):
        _set_widget_visible(self._insert_target, self._insert_target_label != "Current page root")
        self._insert_target.setText(f"Into {self._insert_target_label}")

    def _selected_display_name(self):
        return next(
            (
                str(card._item.get("display_name", card.type_name) or card.type_name)
                for card in self._cards.values()
                if card.type_name == self._selected_type
            ),
            "none",
        )

    def _category_scope_text(self, category_label, search_text):
        scope = "All Components" if category_label == "All" else category_label
        if search_text != "none":
            return f"{scope} + Search"
        return scope

    def _header_meta_text(self, visible, category_label, search_text, selected_text):
        visible_text = _count_label(visible, "component", "components")
        if visible == 0:
            summary = f"No components match the current filters. Insert target: {self._insert_target_label}."
        else:
            summary = f"Showing {visible_text} in {category_label}. Insert target: {self._insert_target_label}."
        if search_text != "none":
            summary += f" Search: {search_text}."
        if selected_text != "none":
            summary += f" Selected: {selected_text}."
        return summary

    def _update_header_context(self, visible, category_label, search_text, selected_text):
        visible_text = _count_label(visible, "component", "components")
        scope_text = self._category_scope_text(category_label, search_text)
        header_meta = self._header_meta_text(visible, category_label, search_text, selected_text)

        if self._subtitle_label.text() != header_meta:
            self._subtitle_label.setText(header_meta)
        if self._visible_count_chip.text() != f"{visible} visible":
            self._visible_count_chip.setText(f"{visible} visible")
        if self._category_summary_chip.text() != scope_text:
            self._category_summary_chip.setText(scope_text)

        _set_widget_metadata(
            self._header_frame,
            tooltip=header_meta,
            accessible_name=f"Components header. {header_meta}",
        )
        _set_widget_metadata(
            self._header_eyebrow,
            tooltip="Component catalog workspace surface.",
            accessible_name="Component catalog workspace surface.",
        )
        _set_widget_metadata(
            self._metrics_frame,
            tooltip=f"Visible components: {visible_text}. Scope: {scope_text}.",
            accessible_name=f"Component browser metrics: {visible_text}. Scope: {scope_text}.",
        )
        _set_widget_metadata(
            self._visible_count_chip,
            tooltip=f"Visible components: {visible_text}.",
            accessible_name=f"Visible components: {visible_text}.",
        )
        _set_widget_metadata(
            self._category_summary_chip,
            tooltip=f"Active component scope: {scope_text}.",
            accessible_name=f"Component scope: {scope_text}.",
        )

    def _update_accessibility_summary(self, visible_count=None):
        visible = len(self._cards) if visible_count is None else max(int(visible_count or 0), 0)
        category_label = self._selected_category_label()
        search_text = str(self._search.text() or "").strip() or "none"
        selected_text = self._selected_display_name()
        visible_text = _count_label(visible, "visible widget", "visible widgets")
        summary = (
            f"Widget Browser: {visible_text}. Category: {category_label}. Search: {search_text}. "
            f"Insert target: {self._insert_target_label}. Selected: {selected_text}."
        )
        results_summary = f"Widget browser results: {_count_label(visible, 'row')} visible."
        if selected_text != "none":
            results_summary += f" Selected widget: {selected_text}."

        self._update_header_context(visible, category_label, search_text, selected_text)
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
            self._category_combo,
            tooltip=f"Widget categories. Current category: {category_label}.",
            accessible_name=f"Widget categories: {category_label}",
        )
        _set_widget_metadata(self._scroll, tooltip=results_summary, accessible_name=results_summary)
        _set_widget_metadata(self._cards_container, tooltip=results_summary, accessible_name=results_summary)

    def _filtered_component_metas(self):
        category = self._selected_category()
        search = str(self._search.text() or "").strip()
        favorite_types = set(self._favorite_service.list_favorites())
        recent_types = list(self._recent_service.list_recent_types())
        recent_lookup = set(recent_types)
        metas = self._catalog.list_components(addable_only=True)

        if category == "favorites":
            filtered = [item for item in metas if item.type_name in favorite_types]
        elif category == "recent":
            recent_order = {name: index for index, name in enumerate(recent_types)}
            filtered = [item for item in metas if item.type_name in recent_lookup]
            filtered.sort(key=lambda item: recent_order.get(item.type_name, 999))
        elif category == "containers":
            filtered = [item for item in metas if item.is_container]
        elif category == "all":
            filtered = metas
        else:
            filtered = [item for item in metas if item.category.lower() == category]

        if not search:
            return filtered

        return self._search_service.filter_and_sort(
            filtered,
            SearchQuery(text=search, category="all", scenario="all", complexity="all", tags=(), sort_mode="relevance"),
            favorite_types=favorite_types,
            recent_types=recent_types,
        )

    def _filtered_items(self):
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
            for item in self._filtered_component_metas()
        ]

    def _clear_cards(self):
        while self._cards_layout.count():
            item = self._cards_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        self._cards = {}

    def _empty_state_hint_text(self):
        search_active = bool((self._search.text() or "").strip())
        category_active = self._selected_category() != "all"
        if search_active and category_active:
            return "Clear search or switch back to All to show more widgets."
        if search_active:
            return "Clear search to show matching widgets."
        if category_active:
            return "Switch back to All to browse the full widget catalog."
        return "No widgets are available right now."

    def _reset_search_only(self):
        if self._search.text():
            blocker = QSignalBlocker(self._search)
            self._search.setText("")
            del blocker
            self.refresh()

    def _reset_to_all_categories(self):
        blocker = QSignalBlocker(self._category_combo)
        self._set_category_by_id("all")
        del blocker
        if getattr(self._config, "widget_browser_active_category", "all") != "all":
            self._config.set_widget_browser_active_category("all")
        self.refresh()

    def _rebuild_cards(self, items):
        self._clear_cards()
        favorites = set(self._config.widget_browser_favorites)
        if not items:
            self._selected_type = ""
            empty = QFrame()
            empty.setObjectName("widget_browser_empty_state")
            empty_layout = QVBoxLayout(empty)
            empty_layout.setContentsMargins(_SPACE_MD, _SPACE_MD, _SPACE_MD, _SPACE_MD)
            empty_layout.setSpacing(_SPACE_XS)

            summary = QLabel(f"No matching widgets. {self._empty_state_hint_text()}")
            summary.setObjectName("workspace_section_subtitle")
            summary.setWordWrap(True)
            summary.setAlignment(Qt.AlignCenter)
            empty_layout.addWidget(summary)

            if self._search.text():
                primary = QPushButton("Clear Search")
                primary.clicked.connect(self._reset_search_only)
                _set_widget_metadata(
                    primary,
                    tooltip="Clear the widget browser search.",
                    accessible_name="Clear widget search",
                )
                empty_layout.addWidget(primary, alignment=Qt.AlignCenter)
            elif self._selected_category() != "all":
                primary = QPushButton("Show All")
                primary.clicked.connect(self._reset_to_all_categories)
                _set_widget_metadata(
                    primary,
                    tooltip="Switch back to All and show the full catalog.",
                    accessible_name="Show all components",
                )
                empty_layout.addWidget(primary, alignment=Qt.AlignCenter)

            _set_widget_metadata(
                empty,
                tooltip="No widgets match the current widget browser filters.",
                accessible_name="No widgets match the current filters.",
            )
            _set_widget_metadata(summary, tooltip=summary.text(), accessible_name="Widget browser empty state.")
            self._cards_layout.addWidget(empty, 1)
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
            card.drag_requested.connect(self._start_widget_drag)
            self._cards_layout.addWidget(card)
            self._cards[index] = card
            card.set_selected(card.type_name == self._selected_type)


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
            icon_key = item.icon_key or widget_icon_key(widget_type)
            drag.setPixmap(make_icon(icon_key, size=_ICON_MD).pixmap(_ICON_MD, _ICON_MD))
            drag.setHotSpot(QPoint(9, 9))
        if global_pos is not None:
            self.statusTip()
        drag.exec_(Qt.CopyAction)
