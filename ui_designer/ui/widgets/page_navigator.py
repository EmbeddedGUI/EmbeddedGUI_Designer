"""Page navigator widget with thumbnails for multi-page management."""

from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QMenu, QScrollArea, QSizePolicy, QVBoxLayout, QWidget
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QPixmap, QImage

from ...engine.python_renderer import render_page
from ..iconography import make_widget_preview
from ..theme import theme_tokens


# Thumbnail size (kept minimal; preview is secondary to page names)
THUMB_WIDTH = 76
THUMB_HEIGHT = 100

_TOKENS = theme_tokens("dark")
_SPACE_XS = int(_TOKENS.get("space_xs", 4))
_SPACE_SM = int(_TOKENS.get("space_sm", 8))
_SPACE_MD = int(_TOKENS.get("space_md", 12))


def _pil_to_qpixmap(pil_image):
    """Convert a PIL Image to QPixmap."""
    data = pil_image.tobytes("raw", "RGBA")
    qimg = QImage(data, pil_image.width, pil_image.height, QImage.Format_RGBA8888)
    return QPixmap.fromImage(qimg)


def _set_widget_metadata(widget, *, tooltip=None, accessible_name=None):
    if tooltip is not None:
        hint = str(tooltip or "")
        if str(widget.property("_page_navigator_hint_snapshot") or "") != hint:
            widget.setToolTip(hint)
            widget.setStatusTip(hint)
            widget.setProperty("_page_navigator_hint_snapshot", hint)
    if accessible_name is not None:
        name = str(accessible_name or "")
        if str(widget.property("_page_navigator_accessible_snapshot") or "") != name:
            widget.setAccessibleName(name)
            widget.setProperty("_page_navigator_accessible_snapshot", name)


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
        self.setObjectName("page_navigator_thumbnail")
        self.setProperty("selected", False)
        self.setProperty("dirty", False)
        self.setProperty("startup", False)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(THUMB_HEIGHT + 8)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        self._preview_frame = QFrame()
        self._preview_frame.setObjectName("page_navigator_thumb_surface")
        self._preview_frame.setProperty("selected", False)
        self._preview_frame.setProperty("dirty", False)
        self._preview_frame.setProperty("startup", False)
        self._preview_frame.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        preview_layout = QVBoxLayout(self._preview_frame)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(0)

        self._thumb_label = QLabel()
        self._thumb_label.setObjectName("page_navigator_thumb_label")
        self._thumb_label.setProperty("selected", False)
        self._thumb_label.setProperty("dirty", False)
        self._thumb_label.setProperty("startup", False)
        self._thumb_label.setFixedSize(THUMB_WIDTH, THUMB_HEIGHT)
        self._thumb_label.setAlignment(Qt.AlignCenter)
        self._thumb_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        preview_layout.addWidget(self._thumb_label, 0, Qt.AlignCenter)
        layout.addWidget(self._preview_frame, 0, Qt.AlignTop)

        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(2)

        self._name_label = QLabel(page_name)
        self._name_label.setObjectName("page_navigator_page_name")
        self._name_label.setWordWrap(True)
        self._name_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        content_layout.addWidget(self._name_label)

        self._meta_label = QLabel("")
        self._meta_label.setObjectName("page_navigator_page_meta")
        self._meta_label.setWordWrap(True)
        self._meta_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        content_layout.addWidget(self._meta_label)
        self._meta_label.hide()

        chip_row = QHBoxLayout()
        chip_row.setContentsMargins(0, 0, 0, 0)
        chip_row.setSpacing(2)
        self._state_chip = self._make_chip("Available")
        self._dirty_chip = self._make_chip("Saved")
        chip_row.addWidget(self._state_chip)
        chip_row.addWidget(self._dirty_chip)
        chip_row.addStretch(1)
        content_layout.addLayout(chip_row)
        self._state_chip.hide()
        self._dirty_chip.hide()
        content_layout.addStretch(1)
        layout.addLayout(content_layout, 1)

        self._set_placeholder_thumbnail()
        self._refresh_visual_state()
        self._update_accessibility()

    def _make_chip(self, text):
        chip = QLabel(str(text or ""))
        chip.setObjectName("workspace_status_chip")
        chip.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        return chip

    def _set_chip_state(self, chip, text, tone=None):
        chip.setText(str(text or ""))
        chip.setProperty("chipTone", tone if tone else None)
        self._refresh_style(chip)

    def _refresh_style(self, widget):
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()

    def _set_style_state(self, widget):
        widget.setProperty("selected", self._selected)
        widget.setProperty("dirty", self._dirty)
        widget.setProperty("startup", self._startup)
        self._refresh_style(widget)

    def _set_placeholder_thumbnail(self):
        placeholder = make_widget_preview("navigation", size=(THUMB_WIDTH - 8, THUMB_HEIGHT - 8))
        self._thumb_label.setPixmap(placeholder)

    def _state_chip_text_and_tone(self):
        if self._selected:
            return "Current", "accent"
        if self._startup:
            return "Startup", "success"
        return "Available", None

    def _meta_summary(self):
        summary = self._state_summary()
        if self._selected:
            return f"{summary} Right click for actions."
        return f"{summary} Left click to open."

    def _refresh_visual_state(self):
        self._set_style_state(self)
        self._set_style_state(self._preview_frame)
        self._set_style_state(self._thumb_label)
        self._name_label.setProperty("dirty", self._dirty)
        self._refresh_style(self._name_label)
        self._meta_label.setText(self._meta_summary())
        state_text, state_tone = self._state_chip_text_and_tone()
        self._set_chip_state(self._state_chip, state_text, state_tone)
        self._set_chip_state(self._dirty_chip, "Dirty" if self._dirty else "Saved", "warning" if self._dirty else None)

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
        _set_widget_metadata(
            self._meta_label,
            tooltip=self._meta_label.text(),
            accessible_name=self._meta_label.text(),
        )
        _set_widget_metadata(
            self._state_chip,
            tooltip=f"Page state: {self._state_chip.text()}.",
            accessible_name=f"Page state: {self._state_chip.text()}.",
        )
        _set_widget_metadata(
            self._dirty_chip,
            tooltip=f"Page save state: {self._dirty_chip.text()}.",
            accessible_name=f"Page save state: {self._dirty_chip.text()}.",
        )

    def set_selected(self, selected):
        self._selected = selected
        self._refresh_visual_state()
        self._update_accessibility()

    def set_thumbnail(self, pixmap):
        scaled = pixmap.scaled(THUMB_WIDTH, THUMB_HEIGHT, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._thumb_label.setPixmap(scaled)

    def set_dirty(self, dirty):
        self._dirty = bool(dirty)
        self._name_label.setText(f"{self.page_name}*" if self._dirty else self.page_name)
        self._refresh_visual_state()
        self._update_accessibility()

    def set_startup(self, startup):
        self._startup = bool(startup)
        self._refresh_visual_state()
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

    def set_compact_mode(self, compact=True):
        compact = bool(compact)
        if hasattr(self, "_header_frame"):
            self._header_frame.setVisible(not compact)

    def _init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(4)

        self._header_frame = QFrame()
        self._header_frame.setObjectName("page_navigator_header")
        header_layout = QVBoxLayout(self._header_frame)
        header_layout.setContentsMargins(8, 8, 8, 8)
        header_layout.setSpacing(4)

        self._eyebrow_label = QLabel("Page Flow")
        self._eyebrow_label.setObjectName("page_navigator_eyebrow")
        _set_widget_metadata(
            self._eyebrow_label,
            tooltip="Page flow workspace surface.",
            accessible_name="Page flow workspace surface.",
        )
        header_layout.addWidget(self._eyebrow_label)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(4)
        self._title_label = QLabel("Thumbnail Rail")
        self._title_label.setObjectName("workspace_section_title")
        self._title_label.setAccessibleName("Pages")
        title_row.addWidget(self._title_label)
        title_row.addStretch(1)
        self._count_chip = self._make_status_chip("0 pages", tone="warning")
        title_row.addWidget(self._count_chip)
        self._count_chip.hide()
        header_layout.addLayout(title_row)

        self._header_meta_label = QLabel(
            "Scan startup flow, current selection, and modified pages without leaving the workspace."
        )
        self._header_meta_label.setObjectName("page_navigator_meta")
        self._header_meta_label.setWordWrap(True)
        header_layout.addWidget(self._header_meta_label)

        chip_row = QHBoxLayout()
        chip_row.setContentsMargins(0, 0, 0, 0)
        chip_row.setSpacing(_SPACE_XS)
        self._startup_chip = self._make_status_chip("Startup: none")
        self._dirty_chip = self._make_status_chip("Clean")
        chip_row.addWidget(self._startup_chip)
        chip_row.addWidget(self._dirty_chip)
        chip_row.addStretch(1)
        header_layout.addLayout(chip_row)
        self._startup_chip.hide()
        self._dirty_chip.hide()

        self._guidance_frame = QFrame()
        self._guidance_frame.setObjectName("page_navigator_guidance")
        guidance_layout = QVBoxLayout(self._guidance_frame)
        guidance_layout.setContentsMargins(0, 0, 0, 0)
        guidance_layout.setSpacing(0)
        self._guidance_label = QLabel(
            "Left click opens a page. Right click duplicates, deletes, or inserts a template after the selected page."
        )
        self._guidance_label.setObjectName("page_navigator_guidance_text")
        self._guidance_label.setWordWrap(True)
        guidance_layout.addWidget(self._guidance_label)
        header_layout.addWidget(self._guidance_frame)
        self._eyebrow_label.hide()
        self._header_meta_label.hide()
        self._guidance_frame.hide()
        outer.addWidget(self._header_frame)

        self._scroll_shell = QFrame()
        self._scroll_shell.setObjectName("page_navigator_scroll_shell")
        scroll_shell_layout = QVBoxLayout(self._scroll_shell)
        scroll_shell_layout.setContentsMargins(0, 0, 0, 0)
        scroll_shell_layout.setSpacing(0)

        self._scroll_area = QScrollArea()
        self._scroll_area.setObjectName("page_navigator_scroll")
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll_area.setAccessibleName("Page thumbnails")
        scroll_shell_layout.addWidget(self._scroll_area)
        outer.addWidget(self._scroll_shell, 1)

        self._container = QWidget()
        self._container.setObjectName("page_navigator_list")
        self._container.setAccessibleName("Page thumbnail list")
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(4)
        self._scroll_area.setWidget(self._container)
        self._update_accessibility_summary()

    def _make_status_chip(self, text, tone=None):
        chip = QLabel(str(text or ""))
        chip.setObjectName("workspace_status_chip")
        if tone:
            chip.setProperty("chipTone", tone)
        return chip

    def _set_status_chip_state(self, chip, text, tone=None):
        chip.setText(str(text or ""))
        chip.setProperty("chipTone", tone if tone else None)
        chip.style().unpolish(chip)
        chip.style().polish(chip)
        chip.update()

    def _update_accessibility_summary(self):
        page_count = len(self._pages)
        page_label = f"{page_count} page" if page_count == 1 else f"{page_count} pages"
        current_page = self._current_page if self._current_page in self._pages else "none"
        startup_page = self._startup_page if self._startup_page in self._pages else "none"
        dirty_count = len(self._dirty_pages)
        dirty_label = "No dirty pages" if dirty_count == 0 else (f"{dirty_count} dirty page" if dirty_count == 1 else f"{dirty_count} dirty pages")
        summary = f"Page navigator: {page_label}. Current page: {current_page}. Startup page: {startup_page}. {dirty_label}."
        self._set_status_chip_state(self._count_chip, page_label, "accent" if page_count else "warning")
        self._set_status_chip_state(
            self._startup_chip,
            f"Startup: {startup_page}",
            "success" if startup_page != "none" else None,
        )
        self._set_status_chip_state(
            self._dirty_chip,
            "Clean" if dirty_count == 0 else (f"{dirty_count} dirty" if dirty_count == 1 else f"{dirty_count} dirty pages"),
            "success" if dirty_count == 0 else "warning",
        )
        self._header_meta_label.setText(
            f"Current page: {current_page}. Startup page: {startup_page}. Use the rail to scan visual state and jump between pages."
        )
        _set_widget_metadata(self, tooltip=summary, accessible_name=summary)
        _set_widget_metadata(
            self._header_frame,
            tooltip=f"Page navigator header. {summary}",
            accessible_name=f"Page navigator header. {summary}",
        )
        _set_widget_metadata(
            self._title_label,
            tooltip=summary,
            accessible_name=f"Pages: {page_label}. Current page: {current_page}. Startup page: {startup_page}.",
        )
        _set_widget_metadata(
            self._header_meta_label,
            tooltip=self._header_meta_label.text(),
            accessible_name=self._header_meta_label.text(),
        )
        _set_widget_metadata(
            self._count_chip,
            tooltip=f"Page count: {page_label}.",
            accessible_name=f"Page count: {page_label}.",
        )
        _set_widget_metadata(
            self._startup_chip,
            tooltip=f"Startup page: {startup_page}.",
            accessible_name=f"Startup page: {startup_page}.",
        )
        _set_widget_metadata(
            self._dirty_chip,
            tooltip=f"Dirty pages: {dirty_label}.",
            accessible_name=f"Dirty pages: {dirty_label}.",
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
        _set_widget_metadata(
            self._guidance_frame,
            tooltip=f"Page navigator guidance. {self._guidance_label.text()}",
            accessible_name=f"Page navigator guidance. {self._guidance_label.text()}",
        )
        _set_widget_metadata(
            self._guidance_label,
            tooltip=self._guidance_label.text(),
            accessible_name=self._guidance_label.text(),
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

        # Remove old layout contents
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

        if not self._pages:
            empty_state = QLabel(
                "No pages yet. Add a page, duplicate an existing flow, or insert a template from the context menu."
            )
            empty_state.setObjectName("page_navigator_empty_state")
            empty_state.setWordWrap(True)
            empty_state.setAlignment(Qt.AlignCenter)
            self._layout.addWidget(empty_state)
            self._layout.addStretch()
            self._update_accessibility_summary()
            return

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
