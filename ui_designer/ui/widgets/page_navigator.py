"""Page navigator widget with thumbnails for multi-page management."""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QScrollArea, QLabel, QMenu, QAction,
    QInputDialog, QMessageBox,
)
from PyQt5.QtCore import pyqtSignal, Qt, QSize
from PyQt5.QtGui import QPixmap, QImage, QPainter, QPen, QColor

from ...engine.python_renderer import render_page


# Thumbnail size (kept minimal; preview is secondary to page names)
THUMB_WIDTH = 96
THUMB_HEIGHT = 128


def _pil_to_qpixmap(pil_image):
    """Convert a PIL Image to QPixmap."""
    data = pil_image.tobytes("raw", "RGBA")
    qimg = QImage(data, pil_image.width, pil_image.height, QImage.Format_RGBA8888)
    return QPixmap.fromImage(qimg)


def _set_widget_metadata(widget, *, tooltip=None, accessible_name=None):
    if tooltip is not None:
        widget.setToolTip(tooltip)
        widget.setStatusTip(tooltip)
    if accessible_name is not None:
        widget.setAccessibleName(accessible_name)


def _set_action_metadata(action, tooltip):
    action.setToolTip(tooltip)
    action.setStatusTip(tooltip)


class PageThumbnail(QWidget):
    """Single page thumbnail with label and click selection."""

    clicked = pyqtSignal(str)  # page_name
    context_menu_requested = pyqtSignal(str, object)  # page_name, QPoint

    def __init__(self, page_name, parent=None):
        super().__init__(parent)
        self.page_name = page_name
        self._dirty = False
        self._selected = False
        self._startup = False
        self.setFixedSize(THUMB_WIDTH + 8, THUMB_HEIGHT + 24)
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(1)

        self._thumb_label = QLabel()
        self._thumb_label.setFixedSize(THUMB_WIDTH, THUMB_HEIGHT)
        self._thumb_label.setAlignment(Qt.AlignCenter)
        # Keep thumbnail container subtle; the rendered pixmap is the actual content.
        self._thumb_label.setStyleSheet("border: 1px solid #E5E7EB; background: transparent;")
        layout.addWidget(self._thumb_label)

        self._name_label = QLabel(page_name)
        self._name_label.setAlignment(Qt.AlignCenter)
        self._name_label.setStyleSheet("color: #6B7280; font-size: 10px;")
        layout.addWidget(self._name_label)
        self._update_accessibility()

    def _state_summary(self):
        parts = []
        if self._startup:
            parts.append("Startup page")
        parts.append("Current page" if self._selected else "Available")
        parts.append("Unsaved changes" if self._dirty else "No unsaved changes")
        return ". ".join(parts) + "."

    def _update_accessibility(self):
        summary = self._state_summary()
        tooltip = f"Open page: {self.page_name}. {summary}"
        _set_widget_metadata(
            self,
            tooltip=tooltip,
            accessible_name=f"Page thumbnail: {self.page_name}. {summary}",
        )
        _set_widget_metadata(
            self._thumb_label,
            tooltip=tooltip,
            accessible_name=f"Page preview: {self.page_name}. {summary}",
        )
        _set_widget_metadata(
            self._name_label,
            tooltip=tooltip,
            accessible_name=f"Page name: {self._name_label.text()}. {summary}",
        )

    def set_selected(self, selected):
        self._selected = selected
        border = "2px solid #007AFF" if selected else "1px solid #E5E7EB"
        self._thumb_label.setStyleSheet(f"border: {border}; background: transparent;")
        self._update_accessibility()

    def set_thumbnail(self, pixmap):
        scaled = pixmap.scaled(THUMB_WIDTH, THUMB_HEIGHT, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._thumb_label.setPixmap(scaled)

    def set_dirty(self, dirty):
        self._dirty = bool(dirty)
        self._name_label.setText(f"{self.page_name}*" if self._dirty else self.page_name)
        self._update_accessibility()

    def set_startup(self, startup):
        self._startup = bool(startup)
        self._update_accessibility()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.page_name)
        elif event.button() == Qt.RightButton:
            self.context_menu_requested.emit(self.page_name, event.globalPos())

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.page_name)


# Page templates
PAGE_TEMPLATES = {
    "blank": {"name": "Blank", "widgets": []},
    "list": {"name": "List Page", "widgets": [
        {"type": "label", "name": "title", "x": 10, "y": 10, "w": 220, "h": 30, "text": "Title"},
        {"type": "scroll", "name": "list_scroll", "x": 0, "y": 50, "w": 240, "h": 270},
    ]},
    "detail": {"name": "Detail Page", "widgets": [
        {"type": "label", "name": "title", "x": 10, "y": 10, "w": 220, "h": 30, "text": "Detail"},
        {"type": "image", "name": "hero_image", "x": 10, "y": 50, "w": 220, "h": 120},
        {"type": "label", "name": "description", "x": 10, "y": 180, "w": 220, "h": 100, "text": "Description"},
    ]},
    "settings": {"name": "Settings Page", "widgets": [
        {"type": "label", "name": "title", "x": 10, "y": 10, "w": 220, "h": 30, "text": "Settings"},
        {"type": "switch", "name": "option_1", "x": 180, "y": 60, "w": 50, "h": 24},
        {"type": "switch", "name": "option_2", "x": 180, "y": 100, "w": 50, "h": 24},
    ]},
}


class PageNavigator(QWidget):
    """Sidebar widget showing page thumbnails with navigation.

    Signals:
        page_selected(str): Emitted when a page is clicked
        page_copy_requested(str): Emitted when copy is requested
        page_delete_requested(str): Emitted when delete is requested
        page_add_requested(str, str): Emitted with (template_key, page_name)
    """

    page_selected = pyqtSignal(str)
    page_copy_requested = pyqtSignal(str)
    page_delete_requested = pyqtSignal(str)
    page_add_requested = pyqtSignal(str, str)  # template_key, page_name

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pages = {}  # page_name -> Page
        self._thumbnails = {}  # page_name -> PageThumbnail
        self._current_page = None
        self._startup_page = ""
        self._dirty_pages = set()
        self._screen_width = 240
        self._screen_height = 320
        self._init_ui()

    def _init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(3, 3, 3, 3)

        self._title_label = QLabel("Pages")
        self._title_label.setStyleSheet("font-weight: 600; color: #4B5563; font-size: 12px;")
        self._title_label.setAccessibleName("Pages")
        outer.addWidget(self._title_label)

        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll_area.setAccessibleName("Page thumbnails")
        outer.addWidget(self._scroll_area)

        self._container = QWidget()
        self._container.setAccessibleName("Page thumbnail list")
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(4)
        self._layout.addStretch()
        self._scroll_area.setWidget(self._container)
        self._update_accessibility_summary()

    def _update_accessibility_summary(self):
        page_count = len(self._pages)
        page_label = f"{page_count} page" if page_count == 1 else f"{page_count} pages"
        current_page = self._current_page if self._current_page in self._pages else "none"
        startup_page = self._startup_page if self._startup_page in self._pages else "none"
        dirty_count = len(self._dirty_pages)
        dirty_label = "No dirty pages" if dirty_count == 0 else (f"{dirty_count} dirty page" if dirty_count == 1 else f"{dirty_count} dirty pages")
        summary = f"Page navigator: {page_label}. Current page: {current_page}. Startup page: {startup_page}. {dirty_label}."
        _set_widget_metadata(self, tooltip=summary, accessible_name=summary)
        _set_widget_metadata(
            self._title_label,
            tooltip=summary,
            accessible_name=f"Pages: {page_label}. Current page: {current_page}. Startup page: {startup_page}.",
        )
        _set_widget_metadata(
            self._scroll_area,
            tooltip=f"Page thumbnails view: {page_label}. Current page: {current_page}. Startup page: {startup_page}. {dirty_label}.",
            accessible_name=f"Page thumbnails view: {page_label}. Current page: {current_page}. Startup page: {startup_page}. {dirty_label}.",
        )
        _set_widget_metadata(
            self._container,
            tooltip=f"Page thumbnail list: {page_label}. Current page: {current_page}. Startup page: {startup_page}. {dirty_label}.",
            accessible_name=f"Page thumbnail list: {page_label}. Current page: {current_page}. Startup page: {startup_page}. {dirty_label}.",
        )

    def set_screen_size(self, w, h):
        self._screen_width = w
        self._screen_height = h

    def set_pages(self, pages_dict):
        """Set all pages. pages_dict: {page_name: Page}."""
        self._pages = dict(pages_dict)
        self._rebuild()
        self._update_accessibility_summary()

    def set_current_page(self, page_name):
        self._current_page = page_name
        for name, thumb in self._thumbnails.items():
            thumb.set_selected(name == page_name)
        self._update_accessibility_summary()

    def set_startup_page(self, page_name):
        self._startup_page = page_name or ""
        for name, thumb in self._thumbnails.items():
            thumb.set_startup(name == self._startup_page)
        self._update_accessibility_summary()

    def set_dirty_pages(self, page_names):
        self._dirty_pages = set(page_names or [])
        for name, thumb in self._thumbnails.items():
            thumb.set_dirty(name in self._dirty_pages)
        self._update_accessibility_summary()

    def refresh_thumbnail(self, page_name):
        """Re-render thumbnail for a specific page."""
        if page_name not in self._pages or page_name not in self._thumbnails:
            return
        page = self._pages[page_name]
        try:
            img = render_page(page, self._screen_width, self._screen_height)
            pixmap = _pil_to_qpixmap(img)
            self._thumbnails[page_name].set_thumbnail(pixmap)
        except Exception:
            pass

    def refresh_all(self):
        for name in self._pages:
            self.refresh_thumbnail(name)

    def _rebuild(self):
        # Clear existing thumbnails
        for thumb in self._thumbnails.values():
            thumb.setParent(None)
            thumb.deleteLater()
        self._thumbnails.clear()

        # Remove stretch
        while self._layout.count():
            item = self._layout.takeAt(0)

        # Add thumbnails
        for name, page in self._pages.items():
            thumb = PageThumbnail(name)
            thumb.clicked.connect(self._on_thumb_clicked)
            thumb.context_menu_requested.connect(self._on_context_menu)
            thumb.set_selected(name == self._current_page)
            thumb.set_startup(name == self._startup_page)
            thumb.set_dirty(name in self._dirty_pages)
            self._thumbnails[name] = thumb
            self._layout.addWidget(thumb)

            # Render thumbnail
            try:
                img = render_page(page, self._screen_width, self._screen_height)
                pixmap = _pil_to_qpixmap(img)
                thumb.set_thumbnail(pixmap)
            except Exception:
                pass

        self._layout.addStretch()
        self._update_accessibility_summary()

    def _on_thumb_clicked(self, page_name):
        self.set_current_page(page_name)
        self.page_selected.emit(page_name)

    def _on_context_menu(self, page_name, pos):
        menu = self._build_context_menu(page_name)
        chosen = menu.exec_(pos)
        if chosen is None:
            return
        action_key = chosen.data()
        if action_key == "copy":
            self.page_copy_requested.emit(page_name)
        elif action_key == "delete":
            self.page_delete_requested.emit(page_name)
        elif isinstance(action_key, str) and action_key.startswith("template:"):
            self.page_add_requested.emit(action_key.split(":", 1)[1], page_name)

    def _context_action_hint(self, action_key, page_name="", template_name=""):
        page_label = str(page_name or "").strip() or "current page"
        if action_key == "copy":
            return f"Duplicate page: {page_label}."
        if action_key == "delete":
            if page_label in self._dirty_pages:
                return f"Delete page: {page_label}. Unsaved changes will be lost."
            return f"Delete page: {page_label}. This cannot be undone."
        if action_key == "template_menu":
            return f"Add a new page from a built-in template after {page_label}."
        return f"Add {template_name or 'page'} after {page_label}."

    def _build_context_menu(self, page_name):
        menu = QMenu(self)
        menu.setToolTipsVisible(True)

        copy_action = menu.addAction("Copy Page")
        copy_action.setData("copy")
        _set_action_metadata(copy_action, self._context_action_hint("copy", page_name))

        delete_action = menu.addAction("Delete Page")
        delete_action.setData("delete")
        _set_action_metadata(delete_action, self._context_action_hint("delete", page_name))

        menu.addSeparator()

        template_menu = menu.addMenu("Add Page from Template")
        template_menu.setToolTipsVisible(True)
        _set_action_metadata(template_menu.menuAction(), self._context_action_hint("template_menu", page_name))
        for key, tmpl in PAGE_TEMPLATES.items():
            action = template_menu.addAction(tmpl["name"])
            action.setData(f"template:{key}")
            _set_action_metadata(action, self._context_action_hint("template", page_name, tmpl["name"]))

        return menu
