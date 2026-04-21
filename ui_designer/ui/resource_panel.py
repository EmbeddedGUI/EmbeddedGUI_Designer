"""Resource panel -- image/font/text catalog browser for EmbeddedGUI Designer.

Independent QWidget designed to be placed inside a QDockWidget.
Manages the designer-side ``.eguiproject/resources/`` directory and
project-level ``resources.xml`` catalog.

Designer resource directory layout:
    .eguiproject/
        resources/
            images/
                star.png
            test.ttf
            supported_text.txt

This panel is a **catalog browser** only -- no per-resource config editors.
Resource configuration (format, alpha, pixelsize, etc.) is managed at the
widget level in the property panel.
"""

import os
import re
import json
import shutil

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QFileDialog, QMessageBox,
    QDialog, QDialogButtonBox, QMenu, QApplication,
    QSplitter, QSizePolicy, QAbstractItemView,
    QInputDialog, QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
    QComboBox, QCheckBox, QToolButton, QLineEdit, QPlainTextEdit, QPushButton,
)
from PyQt5.QtCore import (
    QEvent, Qt, QSize, pyqtSignal, QMimeData, QUrl, QTimer, QRect,
)
from PyQt5.QtGui import (
    QPixmap, QIcon, QPixmapCache, QFontDatabase, QFont,
    QPainter, QColor, QDrag, QPen,
)

from qfluentwidgets import TabWidget, CaptionLabel

from ..model.resource_catalog import ResourceCatalog, IMAGE_EXTENSIONS, FONT_EXTENSIONS, TEXT_EXTENSIONS
from ..model.resource_usage import (
    collect_unused_resource_names,
    collect_unused_string_keys,
    filter_resource_names,
    filter_string_keys,
)
from ..model.string_resource import StringResourceCatalog, DEFAULT_LOCALE
from ..services.font_charset_presets import (
    build_charset,
    charset_custom_chars_after_presets,
    charset_presets,
    infer_charset_presets_from_text,
    preview_charset_chars,
    serialize_charset_chars,
    suggest_charset_filename,
    summarize_charset_diff,
)
from ..utils.resource_config_overlay import DESIGNER_RESOURCE_DIRNAME, is_designer_resource_path
from ..utils.scaffold import preferred_resource_source_dir, resource_images_dir
from .theme import app_theme_tokens, designer_font_scale, designer_monospace_font, designer_ui_font, scaled_point_size


# -- Constants ----------------------------------------------------------

_IMAGE_EXTS = tuple(IMAGE_EXTENSIONS)
_FONT_EXTS = tuple(FONT_EXTENSIONS)
_TEXT_EXTS = tuple(TEXT_EXTENSIONS)

EGUI_RESOURCE_MIME = "application/x-egui-resource"

# Regex for validating English-only filenames
_VALID_FILENAME_RE = re.compile(r'^[A-Za-z0-9_\-]+\.[A-Za-z0-9]+$')
_DEFAULT_RESOURCE_PREVIEW_FONT_PT = 9
_RESOURCE_PANEL_CONTROL_HEIGHT = 22
_RESOURCE_DIALOG_SHELL_MARGINS = (12, 12, 12, 12)
_RESOURCE_DIALOG_SHELL_SPACING = 8
_RESOURCE_DIALOG_CONTENT_SPACING = 8


# -- Helpers ------------------------------------------------------------

def _file_size_str(path):
    """Human-readable file size."""
    try:
        size = os.path.getsize(path)
    except OSError:
        return "?"
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    else:
        return f"{size / (1024 * 1024):.2f} MB"


def _set_compact_control_height(widget, *, height=_RESOURCE_PANEL_CONTROL_HEIGHT):
    if widget is not None:
        widget.setFixedHeight(height)
    return widget


def _apply_resource_dialog_shell_layout(layout):
    left, top, right, bottom = _RESOURCE_DIALOG_SHELL_MARGINS
    layout.setContentsMargins(left, top, right, bottom)
    layout.setSpacing(_RESOURCE_DIALOG_SHELL_SPACING)


def _validate_english_filename(name):
    """Check filename is ASCII letters, digits, underscore, dash, one dot."""
    return bool(_VALID_FILENAME_RE.match(name))


def _reserved_resource_filename_error(name):
    normalized = str(name or "").strip()
    if not normalized or not is_designer_resource_path(normalized):
        return ""
    return (
        f"'{normalized}' is reserved for Designer-generated files.\n"
        "Choose a different filename."
    )


def _reserved_resource_path_label(path, *, root_dir=""):
    normalized = str(path or "").replace("\\", "/").strip()
    if not normalized:
        return ""
    normalized_root = str(root_dir or "").strip()
    if normalized_root:
        try:
            path_abs = os.path.abspath(path)
            root_abs = os.path.abspath(normalized_root)
            if os.path.commonpath([path_abs, root_abs]) == root_abs:
                return os.path.relpath(path_abs, root_abs).replace("\\", "/")
        except ValueError:
            pass
    parts = [part for part in normalized.split("/") if part and part != "."]
    if DESIGNER_RESOURCE_DIRNAME in parts:
        return "/".join(parts[parts.index(DESIGNER_RESOURCE_DIRNAME):])
    return os.path.basename(normalized)


def _reserved_resource_path_error(path, *, root_dir=""):
    normalized = str(path or "").replace("\\", "/").strip()
    if not normalized or not is_designer_resource_path(normalized):
        return ""
    label = _reserved_resource_path_label(normalized, root_dir=root_dir)
    return (
        f"'{label}' is reserved for Designer-generated files.\n"
        "Choose a different filename."
    )


def _set_widget_metadata(widget, *, tooltip=None, accessible_name=None):
    if tooltip is not None:
        hint = str(tooltip or "")
        if str(widget.property("_resource_panel_hint_snapshot") or "") != hint:
            widget.setToolTip(hint)
            widget.setStatusTip(hint)
            widget.setProperty("_resource_panel_hint_snapshot", hint)
    if accessible_name is not None:
        name = str(accessible_name or "")
        if str(widget.property("_resource_panel_accessible_snapshot") or "") != name:
            widget.setAccessibleName(name)
            widget.setProperty("_resource_panel_accessible_snapshot", name)


def _set_item_metadata(item, tooltip):
    hint = str(tooltip or "").strip()
    item.setToolTip(hint)
    item.setStatusTip(hint)
    item.setData(Qt.AccessibleTextRole, hint)


def _set_action_metadata(action, tooltip):
    hint = str(tooltip or "").strip()
    if str(action.property("_resource_panel_hint_snapshot") or "") != hint:
        action.setToolTip(hint)
        action.setStatusTip(hint)
        action.setProperty("_resource_panel_hint_snapshot", hint)


def _create_dialog_metric_card(layout, label_text):
    card = QFrame()
    card.setObjectName("resource_dialog_metric_card")
    card_layout = QVBoxLayout(card)
    card_layout.setContentsMargins(0, 0, 0, 0)
    card_layout.setSpacing(4)

    label = QLabel(label_text)
    label.setObjectName("resource_dialog_metric_label")
    card_layout.addWidget(label)

    value = QLabel("")
    value.setObjectName("resource_dialog_metric_value")
    value.setWordWrap(True)
    card_layout.addWidget(value)

    value._resource_dialog_metric_name = label_text
    value._resource_dialog_metric_label = label
    value._resource_dialog_metric_card = card
    _set_widget_metadata(
        label,
        tooltip=f"{label_text} metric label.",
        accessible_name=f"{label_text} metric label.",
    )
    layout.addWidget(card)
    return value


def _update_dialog_metric_metadata(metric_value):
    metric_name = getattr(metric_value, "_resource_dialog_metric_name", "Resource")
    metric_text = (metric_value.text() or "none").strip() or "none"
    summary = f"{metric_name}: {metric_text}."

    _set_widget_metadata(
        metric_value,
        tooltip=summary,
        accessible_name=f"Resource dialog metric: {metric_name}. {metric_text}.",
    )

    label = getattr(metric_value, "_resource_dialog_metric_label", None)
    if label is not None:
        _set_widget_metadata(
            label,
            tooltip=summary,
            accessible_name=f"{metric_name} metric label.",
        )

    card = getattr(metric_value, "_resource_dialog_metric_card", None)
    if card is not None:
        _set_widget_metadata(
            card,
            tooltip=summary,
            accessible_name=f"{metric_name} metric: {metric_text}.",
        )


def _prepare_dialog_table(table):
    table.setObjectName("resource_dialog_table")
    table.setAlternatingRowColors(False)


def _create_resource_panel_metric_card(layout, label_text):
    card = QFrame()
    card.setObjectName("resource_panel_metric_card")
    card_layout = QVBoxLayout(card)
    card_layout.setContentsMargins(4, 3, 4, 3)
    card_layout.setSpacing(2)

    label = QLabel(label_text)
    label.setObjectName("resource_panel_metric_label")
    card_layout.addWidget(label)

    value = QLabel("")
    value.setObjectName("resource_panel_metric_value")
    value.setWordWrap(True)
    card_layout.addWidget(value)

    value._resource_panel_metric_name = label_text
    value._resource_panel_metric_label = label
    value._resource_panel_metric_card = card
    _set_widget_metadata(
        label,
        tooltip=f"{label_text} metric label.",
        accessible_name=f"{label_text} metric label.",
    )
    layout.addWidget(card)
    return value


def _update_resource_panel_metric_metadata(metric_value):
    metric_name = getattr(metric_value, "_resource_panel_metric_name", "Resource")
    metric_text = (metric_value.text() or "none").strip() or "none"
    summary = f"{metric_name}: {metric_text}."

    _set_widget_metadata(
        metric_value,
        tooltip=summary,
        accessible_name=f"Resource panel metric: {metric_name}. {metric_text}.",
    )

    label = getattr(metric_value, "_resource_panel_metric_label", None)
    if label is not None:
        _set_widget_metadata(
            label,
            tooltip=summary,
            accessible_name=f"{metric_name} metric label.",
        )

    card = getattr(metric_value, "_resource_panel_metric_card", None)
    if card is not None:
        _set_widget_metadata(
            card,
            tooltip=summary,
            accessible_name=f"{metric_name} metric: {metric_text}.",
        )


def _prepare_resource_panel_table(table):
    table.setObjectName("resource_panel_table")
    table.setAlternatingRowColors(False)


def _prepare_resource_panel_list(widget, object_name="resource_panel_list"):
    widget.setObjectName(object_name)


def _count_label(count, singular, plural=None):
    value = max(int(count or 0), 0)
    noun = singular if value == 1 else (plural or f"{singular}s")
    return f"{value} {noun}"


def _compact_resource_title(title):
    text = str(title or "").strip()
    compact_map = {
        "Replace Missing Resources": "Replace Missing",
        "Replace Missing Resource": "Replace Missing",
        "Restore Missing Resources": "Restore Missing",
        "Restore Missing Resource": "Restore Missing",
        "Review Reference Impact": "Impact",
        "Review Batch Replace Impact": "Replace Impact",
    }
    return compact_map.get(text, text)


def _suggest_charset_filename_for_resource(resource_type, filename):
    name = str(filename or "").strip()
    if resource_type == "text" and name.lower().endswith(".txt"):
        return name
    if resource_type == "font":
        stem = os.path.splitext(os.path.basename(name))[0]
        safe_stem = re.sub(r"[^A-Za-z0-9_-]+", "_", stem).strip("_")
        if safe_stem:
            return f"{safe_stem}_charset.txt"
    return ""


_CN_FONT_KEYWORDS = (
    "noto", "sc", "hans", "cn", "chinese", "cjk", "simhei", "simsun",
    "source_han", "wenquanyi", "unifont", "wqy", "notosans",
)
_ICON_FONT_KEYWORDS = (
    "material", "symbol", "icon", "fontawesome", "fa-", "ionicon",
    "feather", "boxicon", "remixicon",
)


def _suggest_charset_presets_for_resource(resource_type, filename):
    if resource_type == "text":
        text_name = os.path.basename(str(filename or "")).strip().lower()
        for preset in charset_presets():
            default_name = preset.default_filename.lower()
            if text_name == default_name:
                return (preset.preset_id,)
            if default_name.endswith(".txt") and text_name == f"{default_name[:-4]}_custom.txt":
                return (preset.preset_id,)
        return ()

    if resource_type != "font":
        return ()

    name = os.path.basename(str(filename or "")).lower()
    if any(keyword in name for keyword in _ICON_FONT_KEYWORDS):
        return ()
    if "gbk" in name:
        return ("gbk_all",)
    if any(keyword in name for keyword in _CN_FONT_KEYWORDS):
        return ("gb2312_all",)
    return ("ascii_printable",)


# -- Lazy-loading image list --------------------------------------------

class _LazyImageList(QListWidget):
    """QListWidget that loads thumbnails lazily via QPixmapCache."""

    THUMB_SIZE = 48

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setViewMode(QListWidget.IconMode)
        self.setIconSize(QSize(self.THUMB_SIZE, self.THUMB_SIZE))
        self.setGridSize(QSize(self.THUMB_SIZE + 16, self.THUMB_SIZE + 28))
        self.setResizeMode(QListWidget.Adjust)
        self.setMovement(QListWidget.Static)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setDragEnabled(True)

        self._load_timer = QTimer(self)
        self._load_timer.setSingleShot(True)
        self._load_timer.setInterval(30)
        self._load_timer.timeout.connect(self._load_visible)

    def showEvent(self, event):
        super().showEvent(event)
        self._schedule_load()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._schedule_load()

    def scrollContentsBy(self, dx, dy):
        super().scrollContentsBy(dx, dy)
        self._schedule_load()

    def _schedule_load(self):
        if not self._load_timer.isActive():
            self._load_timer.start()

    def _load_visible(self):
        vr = self.viewport().rect()
        for i in range(self.count()):
            item = self.item(i)
            item_rect = self.visualItemRect(item)
            if not vr.intersects(item_rect):
                continue
            if item.data(Qt.UserRole + 10):
                continue
            path = item.data(Qt.UserRole)
            if not path:
                continue
            self._load_thumb(item, path)

    def _load_thumb(self, item, path):
        try:
            mtime = int(os.path.getmtime(path))
        except OSError:
            mtime = 0
        cache_key = f"egui_thumb:{path}:{mtime}"
        pm = QPixmapCache.find(cache_key)
        if pm is None or pm.isNull():
            pm = QPixmap(path)
            if pm.isNull():
                return
            pm = pm.scaled(self.THUMB_SIZE, self.THUMB_SIZE,
                           Qt.KeepAspectRatio, Qt.SmoothTransformation)
            QPixmapCache.insert(cache_key, pm)
        item.setIcon(QIcon(pm))
        item.setData(Qt.UserRole + 10, True)

    def startDrag(self, supportedActions):
        item = self.currentItem()
        if item is None:
            return
        filename = item.data(Qt.UserRole + 1)  # filename string
        if not filename:
            return
        path = item.data(Qt.UserRole) or ""

        mime = QMimeData()
        data = json.dumps({"type": "image", "filename": filename, "path": path})
        mime.setData(EGUI_RESOURCE_MIME, data.encode("utf-8"))
        mime.setText(filename)

        drag = QDrag(self)
        drag.setMimeData(mime)
        if not item.icon().isNull():
            drag.setPixmap(item.icon().pixmap(32, 32))
        drag.exec_(Qt.CopyAction)


# -- Drag-enabled font list ---------------------------------------------

class _DragResourceList(QListWidget):
    """QListWidget for simple resource types with drag-out support."""

    def __init__(self, resource_type, parent=None):
        super().__init__(parent)
        self._resource_type = resource_type
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setDragEnabled(True)

    def startDrag(self, supportedActions):
        item = self.currentItem()
        if item is None:
            return
        filename = item.data(Qt.UserRole + 1)  # filename string
        if not filename:
            return
        path = item.data(Qt.UserRole) or ""

        mime = QMimeData()
        data = json.dumps({"type": self._resource_type, "filename": filename, "path": path})
        mime.setData(EGUI_RESOURCE_MIME, data.encode("utf-8"))
        mime.setText(filename)

        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec_(Qt.CopyAction)


# -- Preview widget ------------------------------------------------------

class _PreviewWidget(QWidget):
    """Bottom preview area -- image large preview or font samples."""

    _SAMPLE_TEXT = "AaBbCc 0123"
    _FONT_SIZES = [12, 16, 24, 32]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setMinimumHeight(140)
        self._mode = None
        self._pixmap = None
        self._meta_lines = []
        self._font_family = None
        self._font_file = None
        self._text_lines = []

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.StyleChange, QEvent.PaletteChange):
            self.update()

    def _paint_palette(self):
        tokens = app_theme_tokens()
        return {
            "image_meta": QColor(tokens["text"]),
            "meta": QColor(tokens["text_muted"]),
            "preview_text": QColor(tokens["text"]),
        }

    def _ui_font_scale(self):
        app = QApplication.instance()
        return designer_font_scale(app, default_pt=_DEFAULT_RESOURCE_PREVIEW_FONT_PT)

    def _scaled_ui_font_point_size(self, base_point_size, minimum=1):
        app = QApplication.instance()
        return scaled_point_size(base_point_size, app=app, minimum=minimum, default_pt=_DEFAULT_RESOURCE_PREVIEW_FONT_PT)

    def _image_meta_font_point_size(self):
        return self._scaled_ui_font_point_size(9, minimum=8)

    def _meta_font_point_size(self):
        return self._scaled_ui_font_point_size(8, minimum=7)

    def _text_preview_font_point_size(self):
        return self._scaled_ui_font_point_size(9, minimum=8)

    def show_image(self, path):
        self._mode = "image"
        self._font_family = None
        pm = QPixmap(path)
        if pm.isNull():
            self._pixmap = None
            self.update()
            return

        orig_w, orig_h = pm.width(), pm.height()
        fname = os.path.basename(path)
        self._meta_lines = [
            fname,
            f"Size: {orig_w} \u00d7 {orig_h}",
            _file_size_str(path),
        ]

        self._pixmap = pm
        self.update()

    def show_font(self, path, font_family):
        self._mode = "font"
        self._pixmap = None
        self._font_family = font_family
        self._font_file = path
        self._text_lines = []
        self._meta_lines = [
            os.path.basename(path),
            font_family or "Unknown family",
            _file_size_str(path),
        ]
        self.update()

    def show_text(self, path):
        self._mode = "text"
        self._pixmap = None
        self._font_family = None
        self._font_file = None

        content = ""
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except UnicodeDecodeError:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except OSError:
            self.clear_preview()
            return

        lines = content.splitlines()
        self._text_lines = lines[:6] or ["(Empty file)"]
        self._meta_lines = [
            os.path.basename(path),
            _file_size_str(path),
            f"Lines: {len(lines)}",
        ]
        self.update()

    def clear_preview(self):
        self._mode = None
        self._pixmap = None
        self._font_family = None
        self._meta_lines = []
        self._text_lines = []
        self.update()

    def paintEvent(self, event):
        if self._mode is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        w, h = self.width(), self.height()
        if self._mode == "image" and self._pixmap:
            self._paint_image(painter, w, h)
        elif self._mode == "font" and self._font_family:
            self._paint_font(painter, w, h)
        elif self._mode == "text":
            self._paint_text(painter, w, h)
        painter.end()

    def _paint_image(self, painter, w, h):
        palette = self._paint_palette()
        pm = self._pixmap
        preview_w = max(w - 140, 60)
        preview_h = h - 8
        scaled = pm.scaled(preview_w, preview_h,
                           Qt.KeepAspectRatio, Qt.SmoothTransformation)
        x = 4
        y = (h - scaled.height()) // 2
        painter.drawPixmap(x, y, scaled)
        text_x = x + scaled.width() + 8
        painter.setPen(palette["image_meta"])
        painter.setFont(designer_ui_font(point_size=self._image_meta_font_point_size()))
        fm = painter.fontMetrics()
        ty = 8
        for line in self._meta_lines:
            painter.drawText(text_x, ty + fm.ascent(), line)
            ty += fm.height() + 2

    def _paint_font(self, painter, w, h):
        palette = self._paint_palette()
        painter.setPen(palette["meta"])
        painter.setFont(designer_ui_font(point_size=self._meta_font_point_size()))
        fm = painter.fontMetrics()
        ty = 4
        for line in self._meta_lines:
            painter.drawText(8, ty + fm.ascent(), line)
            ty += fm.height() + 1
        ty += 4
        painter.setPen(palette["preview_text"])
        for sz in self._FONT_SIZES:
            if ty > h - 4:
                break
            font = QFont(self._font_family, sz)
            painter.setFont(font)
            fm2 = painter.fontMetrics()
            painter.drawText(8, ty + fm2.ascent(), f"{sz}px: {self._SAMPLE_TEXT}")
            ty += fm2.height() + 2

    def _paint_text(self, painter, w, h):
        palette = self._paint_palette()
        painter.setPen(palette["meta"])
        painter.setFont(designer_ui_font(point_size=self._meta_font_point_size()))
        fm = painter.fontMetrics()
        ty = 4
        for line in self._meta_lines:
            painter.drawText(8, ty + fm.ascent(), line)
            ty += fm.height() + 1

        preview_rect = QRect(8, ty + 6, max(w - 16, 0), max(h - ty - 12, 0))
        painter.setPen(palette["preview_text"])
        painter.setFont(designer_monospace_font(point_size=self._text_preview_font_point_size()))
        painter.drawText(preview_rect, Qt.TextWordWrap | Qt.AlignTop | Qt.AlignLeft, "\n".join(self._text_lines))


class _GenerateCharsetDialog(QDialog):
    """Create or overwrite a text resource from built-in charset presets."""

    def __init__(self, resource_dir, initial_filename="", source_label="", initial_preset_ids=(), initial_custom_text="", parent=None):
        super().__init__(parent)
        self.setObjectName("resource_dialog_shell")
        self._resource_dir = resource_dir or ""
        self._initial_filename = str(initial_filename or "").strip()
        self._source_label = str(source_label or "").strip()
        self._initial_preset_ids = tuple(initial_preset_ids or ())
        self._initial_custom_text = str(initial_custom_text or "")
        self._presets = charset_presets()
        self._preset_checks = {}
        self._filename_manual = False
        self._suggested_filename = ""
        self._save_and_assign_requested = False
        self._build_result = build_charset(())

        title_text = "Generate Charset"
        if self._source_label:
            title_text = f"Generate Charset for {self._source_label}"
        self.setWindowTitle(title_text)
        self.setMinimumSize(760, 620)
        self.resize(860, 680)

        layout = QVBoxLayout(self)
        _apply_resource_dialog_shell_layout(layout)

        self._header_frame = QFrame()
        self._header_frame.setObjectName("resource_dialog_header")
        header_layout = QHBoxLayout(self._header_frame)
        header_layout.setContentsMargins(12, 10, 12, 10)
        header_layout.setSpacing(12)

        hero_copy = QVBoxLayout()
        hero_copy.setContentsMargins(0, 0, 0, 0)
        hero_copy.setSpacing(4)

        self._eyebrow_label = QLabel("Font Charset Tool")
        self._eyebrow_label.setObjectName("resource_dialog_eyebrow")
        _set_widget_metadata(
            self._eyebrow_label,
            tooltip="Font charset generation workspace.",
            accessible_name="Font charset generation workspace.",
        )
        hero_copy.addWidget(self._eyebrow_label, 0, Qt.AlignLeft)

        self._title_label = QLabel(title_text)
        self._title_label.setObjectName("resource_dialog_title")
        _set_widget_metadata(
            self._title_label,
            tooltip=f"Font charset generator title: {title_text}.",
            accessible_name=f"Font charset generator title: {title_text}.",
        )
        hero_copy.addWidget(self._title_label)

        self._subtitle_label = QLabel(
            "Combine built-in presets and custom characters, then save them as a Text resource."
        )
        self._subtitle_label.setObjectName("resource_dialog_subtitle")
        self._subtitle_label.setWordWrap(True)
        _set_widget_metadata(
            self._subtitle_label,
            tooltip=self._subtitle_label.text(),
            accessible_name=self._subtitle_label.text(),
        )
        hero_copy.addWidget(self._subtitle_label)

        self._recommendation_label = QLabel(self._initial_recommendation_text())
        self._recommendation_label.setObjectName("resource_dialog_summary")
        self._recommendation_label.setWordWrap(True)
        _set_widget_metadata(
            self._recommendation_label,
            tooltip=self._recommendation_label.text(),
            accessible_name=self._recommendation_label.text(),
        )
        self._recommendation_label.setVisible(bool(self._recommendation_label.text().strip()))
        hero_copy.addWidget(self._recommendation_label)
        header_layout.addLayout(hero_copy, 3)

        metrics_layout = QVBoxLayout()
        metrics_layout.setContentsMargins(0, 0, 0, 0)
        metrics_layout.setSpacing(6)
        self._selection_metric = _create_dialog_metric_card(metrics_layout, "Selection")
        self._char_metric = _create_dialog_metric_card(metrics_layout, "Chars")
        self._file_metric = _create_dialog_metric_card(metrics_layout, "File")
        header_layout.addLayout(metrics_layout, 2)
        layout.addWidget(self._header_frame)

        self._preset_card = QFrame()
        self._preset_card.setObjectName("resource_dialog_card")
        preset_layout = QVBoxLayout(self._preset_card)
        preset_layout.setContentsMargins(12, 10, 12, 10)
        preset_layout.setSpacing(6)

        preset_title = QLabel("Built-in Presets")
        preset_title.setObjectName("workspace_section_title")
        _set_widget_metadata(
            preset_title,
            tooltip="Built-in charset presets.",
            accessible_name="Built-in charset presets.",
        )
        preset_layout.addWidget(preset_title)

        for preset in self._presets:
            count = len(build_charset((preset.preset_id,)).chars)
            checkbox = QCheckBox(f"{preset.label} ({count})")
            _set_widget_metadata(
                checkbox,
                tooltip=preset.description,
                accessible_name=f"Charset preset: {preset.label}. {preset.description}",
            )
            checkbox.toggled.connect(self._refresh_preview)
            preset_layout.addWidget(checkbox)
            self._preset_checks[preset.preset_id] = checkbox
        layout.addWidget(self._preset_card)

        self._custom_card = QFrame()
        self._custom_card.setObjectName("resource_dialog_card")
        custom_layout = QVBoxLayout(self._custom_card)
        custom_layout.setContentsMargins(12, 10, 12, 10)
        custom_layout.setSpacing(6)

        custom_title = QLabel("Custom Characters")
        custom_title.setObjectName("workspace_section_title")
        _set_widget_metadata(
            custom_title,
            tooltip="Custom characters to merge into the generated charset.",
            accessible_name="Custom characters to merge into the generated charset.",
        )
        custom_layout.addWidget(custom_title)

        custom_hint = QLabel(
            "Paste literal characters or &#xHHHH; entities. Line breaks are ignored; spaces are preserved."
        )
        custom_hint.setObjectName("workspace_section_subtitle")
        custom_hint.setWordWrap(True)
        _set_widget_metadata(
            custom_hint,
            tooltip=custom_hint.text(),
            accessible_name=custom_hint.text(),
        )
        custom_layout.addWidget(custom_hint)

        self._custom_input = QPlainTextEdit()
        self._custom_input.setObjectName("resource_charset_custom_input")
        self._custom_input.setPlaceholderText("例如：℃°你好&#x4E2D;")
        self._custom_input.textChanged.connect(self._refresh_preview)
        self._custom_input.setPlaceholderText("e.g. A&#x2103;&#x00B0;&#x4F60;&#x597D;")
        custom_layout.addWidget(self._custom_input, 1)
        layout.addWidget(self._custom_card, 1)

        self._output_card = QFrame()
        self._output_card.setObjectName("resource_dialog_card")
        output_layout = QVBoxLayout(self._output_card)
        output_layout.setContentsMargins(12, 10, 12, 10)
        output_layout.setSpacing(6)

        output_title = QLabel("Output")
        output_title.setObjectName("workspace_section_title")
        _set_widget_metadata(
            output_title,
            tooltip="Output settings for the generated charset resource.",
            accessible_name="Output settings for the generated charset resource.",
        )
        output_layout.addWidget(output_title)

        file_row = QHBoxLayout()
        file_row.setContentsMargins(0, 0, 0, 0)
        file_row.setSpacing(6)
        file_label = QLabel("Filename")
        file_label.setObjectName("resource_panel_field_label")
        _set_widget_metadata(
            file_label,
            tooltip="Filename for the generated charset resource.",
            accessible_name="Filename for the generated charset resource.",
        )
        file_row.addWidget(file_label)

        self._filename_edit = QLineEdit()
        self._filename_edit.setObjectName("resource_charset_filename")
        self._filename_edit.setPlaceholderText("charset_ascii_printable.txt")
        self._filename_edit.textEdited.connect(self._on_filename_edited)
        self._filename_edit.textChanged.connect(self._refresh_preview)
        _set_compact_control_height(self._filename_edit)
        file_row.addWidget(self._filename_edit, 1)
        output_layout.addLayout(file_row)

        self._summary_label = QLabel("")
        self._summary_label.setObjectName("resource_dialog_summary")
        self._summary_label.setWordWrap(True)
        output_layout.addWidget(self._summary_label)

        self._overwrite_summary = QLabel("")
        self._overwrite_summary.setObjectName("resource_dialog_summary")
        self._overwrite_summary.setWordWrap(True)
        output_layout.addWidget(self._overwrite_summary)

        self._preview_box = QPlainTextEdit()
        self._preview_box.setObjectName("resource_charset_preview")
        self._preview_box.setReadOnly(True)
        self._preview_box.setPlaceholderText("Select a preset or enter custom characters to preview the output.")
        self._preview_box.setMaximumHeight(140)
        output_layout.addWidget(self._preview_box)
        layout.addWidget(self._output_card)

        button_box = QDialogButtonBox(Qt.Horizontal)
        self._save_button = button_box.addButton("Save", QDialogButtonBox.AcceptRole)
        self._save_assign_button = button_box.addButton("Save and Bind Current Widget", QDialogButtonBox.AcceptRole)
        self._cancel_button = button_box.addButton(QDialogButtonBox.Cancel)
        for button in (self._save_button, self._save_assign_button, self._cancel_button):
            _set_compact_control_height(button)
        self._save_button.clicked.connect(self._accept_save)
        self._save_assign_button.clicked.connect(self._accept_save_and_assign)
        self._cancel_button.clicked.connect(self.reject)
        layout.addWidget(button_box)

        if self._initial_filename:
            self._filename_edit.setText(self._initial_filename)
            self._filename_manual = True
            self._suggested_filename = self._initial_filename

        if self._initial_custom_text:
            self._custom_input.blockSignals(True)
            self._custom_input.setPlainText(self._initial_custom_text)
            self._custom_input.blockSignals(False)

        for preset_id in self._initial_preset_ids:
            checkbox = self._preset_checks.get(preset_id)
            if checkbox is not None:
                checkbox.blockSignals(True)
                checkbox.setChecked(True)
                checkbox.blockSignals(False)

        self._refresh_preview()

    def selected_preset_ids(self):
        return tuple(
            preset.preset_id
            for preset in self._presets
            if self._preset_checks[preset.preset_id].isChecked()
        )

    def generated_chars(self):
        return self._build_result.chars

    def generated_text(self):
        return serialize_charset_chars(self.generated_chars())

    def filename(self):
        return self._normalized_filename()

    def save_and_assign(self):
        return self._save_and_assign_requested

    def overwrite_diff(self):
        filename = self.filename()
        if not filename:
            return summarize_charset_diff("", self.generated_chars())
        path = os.path.join(self._resource_dir, filename)
        if not os.path.isfile(path):
            return summarize_charset_diff("", self.generated_chars())
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                existing_text = handle.read()
        except OSError:
            existing_text = ""
        return summarize_charset_diff(existing_text, self.generated_chars())

    def _accept_save(self):
        self._save_and_assign_requested = False
        if self._validate_before_accept():
            self.accept()

    def _accept_save_and_assign(self):
        self._save_and_assign_requested = True
        if self._validate_before_accept():
            self.accept()

    def _validate_before_accept(self):
        error = self._filename_error()
        if error:
            QMessageBox.warning(self, "Invalid Filename", error)
            return False
        if not self.generated_chars():
            QMessageBox.warning(self, "Empty Charset", "Select at least one preset or enter custom characters.")
            return False
        return True

    def _on_filename_edited(self, _text):
        self._filename_manual = True
        self._refresh_preview()

    def _normalized_filename(self):
        name = (self._filename_edit.text() or "").strip()
        if name and "." not in name:
            name += ".txt"
        return name

    def _initial_recommendation_text(self):
        if not self._source_label:
            return ""
        if self._initial_preset_ids:
            label_map = {preset.preset_id: preset.label for preset in self._presets}
            labels = [label_map.get(preset_id, preset_id) for preset_id in self._initial_preset_ids]
            return f"Suggested for {self._source_label}: {', '.join(labels)}."
        return f"No default preset selected for {self._source_label}. Choose a preset or enter custom characters."

    def _filename_error(self):
        filename = self._normalized_filename()
        if not filename:
            return "Enter a filename for the generated charset resource."
        if not filename.lower().endswith(".txt"):
            return "Charset resources must use the .txt extension."
        if not _validate_english_filename(filename):
            return (
                f"'{filename}' is invalid.\n"
                "Use only ASCII letters, digits, underscore, and dash."
            )
        reserved_error = _reserved_resource_filename_error(filename)
        if reserved_error:
            return reserved_error
        return ""

    def _refresh_preview(self):
        preset_ids = self.selected_preset_ids()
        custom_text = self._custom_input.toPlainText()
        self._build_result = build_charset(preset_ids, custom_text)

        suggested = suggest_charset_filename(preset_ids, custom_text)
        current_text = (self._filename_edit.text() or "").strip()
        should_update_filename = (not self._filename_manual) or (not current_text) or (current_text == self._suggested_filename)
        self._suggested_filename = suggested
        if should_update_filename and suggested and current_text != suggested:
            self._filename_edit.blockSignals(True)
            self._filename_edit.setText(suggested)
            self._filename_edit.blockSignals(False)

        selection_parts = []
        if preset_ids:
            selection_parts.append(_count_label(len(preset_ids), "preset"))
        if any(item.source_id == "custom" for item in self._build_result.contributions):
            selection_parts.append("custom input")
        self._selection_metric.setText(", ".join(selection_parts) if selection_parts else "None")
        self._char_metric.setText(_count_label(self._build_result.total_chars, "char"))
        self._file_metric.setText(self.filename() or "None")
        _update_dialog_metric_metadata(self._selection_metric)
        _update_dialog_metric_metadata(self._char_metric)
        _update_dialog_metric_metadata(self._file_metric)

        contribution_lines = []
        for item in self._build_result.contributions:
            contribution_lines.append(f"{item.label}: {item.added_chars}/{item.total_chars} new")
        if contribution_lines:
            summary = " | ".join(contribution_lines)
        else:
            summary = "Choose presets or add custom characters to generate output."
        preview = preview_charset_chars(self._build_result.chars, limit=16) or "(empty)"
        self._summary_label.setText(
            f"{summary}\nPreview: {preview}"
        )

        filename_error = self._filename_error()
        diff = self.overwrite_diff()
        target_path = os.path.join(self._resource_dir, self.filename()) if self.filename() else ""
        if filename_error:
            overwrite_summary = filename_error.replace("\n", " ")
        elif target_path and os.path.isfile(target_path):
            overwrite_summary = (
                f"Overwrite existing file: {self.filename()} | "
                f"Existing {diff.existing_count} chars | New {diff.new_count} chars | "
                f"Added {diff.added_count} | Removed {diff.removed_count}"
            )
        elif self.filename():
            overwrite_summary = f"Create new file: {self.filename()} | {diff.new_count} chars"
        else:
            overwrite_summary = "Enter a filename to save the generated charset."
        self._overwrite_summary.setText(overwrite_summary)

        serialized = self.generated_text()
        self._preview_box.setPlainText(serialized[:2000].rstrip())

        can_save = bool(self.generated_chars()) and not filename_error
        self._save_button.setEnabled(can_save)
        self._save_assign_button.setEnabled(can_save)
        self._update_accessibility_summary()

    def _update_accessibility_summary(self):
        selected_count = len(self.selected_preset_ids())
        custom_contribution = next(
            (item for item in self._build_result.contributions if item.source_id == "custom"),
            None,
        )
        custom_count = custom_contribution.total_chars if custom_contribution is not None else 0
        filename = self.filename() or "none"
        char_summary = self._char_metric.text() or "0 chars"
        overwrite_text = (self._overwrite_summary.text() or "").strip() or "No overwrite summary available."
        source_summary = f" Source: {self._source_label}." if self._source_label else ""
        dialog_summary = (
            f"Generate Charset: {_count_label(selected_count, 'preset')} selected. "
            f"Custom chars: {custom_count}. {char_summary.capitalize()}. "
            f"File: {filename}.{source_summary} {overwrite_text}".strip()
        )
        _set_widget_metadata(self, tooltip=dialog_summary, accessible_name=dialog_summary)
        _set_widget_metadata(
            self._header_frame,
            tooltip=(
                f"Font charset dialog header: {_count_label(selected_count, 'preset')} selected. "
                f"{char_summary.capitalize()}. File: {filename}."
                f"{f' Source: {self._source_label}.' if self._source_label else ''}"
            ),
            accessible_name=(
                f"Font charset dialog header: {_count_label(selected_count, 'preset')} selected. "
                f"{char_summary.capitalize()}. File: {filename}."
                f"{f' Source: {self._source_label}.' if self._source_label else ''}"
            ),
        )
        _set_widget_metadata(
            self._preset_card,
            tooltip=f"Preset selection area. {_count_label(selected_count, 'preset')} selected.",
            accessible_name=f"Preset selection area. {_count_label(selected_count, 'preset')} selected.",
        )
        _set_widget_metadata(
            self._custom_card,
            tooltip=f"Custom character input area. {custom_count} custom chars entered.",
            accessible_name=f"Custom character input area. {custom_count} custom chars entered.",
        )
        _set_widget_metadata(
            self._custom_input,
            tooltip=(
                "Enter literal characters or &#xHHHH; entities. "
                f"Current custom chars: {custom_count}."
            ),
            accessible_name=f"Custom charset input: {custom_count} custom chars.",
        )
        _set_widget_metadata(
            self._output_card,
            tooltip=f"Output area for {filename}. {char_summary.capitalize()}.",
            accessible_name=f"Output area for {filename}. {char_summary.capitalize()}.",
        )
        _set_widget_metadata(
            self._filename_edit,
            tooltip=f"Charset output filename. Current value: {filename}.",
            accessible_name=f"Charset output filename: {filename}.",
        )
        summary_text = (self._summary_label.text() or "").replace("\n", " ").strip() or "No charset summary available."
        _set_widget_metadata(
            self._summary_label,
            tooltip=summary_text,
            accessible_name=f"Charset summary: {summary_text}",
        )
        _set_widget_metadata(
            self._overwrite_summary,
            tooltip=overwrite_text,
            accessible_name=f"Overwrite summary: {overwrite_text}",
        )
        preview_lines = max(1, len([line for line in self._preview_box.toPlainText().splitlines() if line]))
        _set_widget_metadata(
            self._preview_box,
            tooltip=f"Generated charset preview. Showing {preview_lines} line preview.",
            accessible_name=f"Generated charset preview. Showing {preview_lines} line preview.",
        )
        save_enabled = self._save_button.isEnabled()
        save_tooltip = f"Save charset resource to {filename}."
        save_assign_tooltip = f"Save charset resource to {filename} and bind it to the current widget."
        if not save_enabled:
            save_tooltip = "Select presets or enter custom characters, then provide a valid filename."
            save_assign_tooltip = save_tooltip
        _set_widget_metadata(
            self._save_button,
            tooltip=save_tooltip,
            accessible_name="Save charset resource" if save_enabled else "Save charset resource unavailable",
        )
        _set_widget_metadata(
            self._save_assign_button,
            tooltip=save_assign_tooltip,
            accessible_name=(
                "Save charset resource and bind current widget"
                if save_enabled
                else "Save charset resource and bind current widget unavailable"
            ),
        )
        _set_widget_metadata(
            self._cancel_button,
            tooltip="Close the charset generator without saving.",
            accessible_name="Cancel charset generation",
        )


class _MissingResourceReplaceDialog(QDialog):
    """Map missing project resources to external replacement files."""

    def __init__(self, missing_names, source_paths, parent=None):
        super().__init__(parent)
        self.setObjectName("resource_dialog_shell")
        self._missing_names = list(missing_names)
        self._source_paths = list(source_paths)
        self._combos = []
        self.setWindowTitle("Replace Missing Resources")
        self.setMinimumSize(760, 520)
        self.resize(820, 560)

        layout = QVBoxLayout(self)
        _apply_resource_dialog_shell_layout(layout)

        self._header_frame = QFrame()
        self._header_frame.setObjectName("resource_dialog_header")
        header_layout = QHBoxLayout(self._header_frame)
        header_layout.setContentsMargins(12, 10, 12, 10)
        header_layout.setSpacing(12)

        hero_copy = QVBoxLayout()
        hero_copy.setContentsMargins(0, 0, 0, 0)
        hero_copy.setSpacing(4)

        self._eyebrow_label = QLabel("Resource Recovery")
        self._eyebrow_label.setObjectName("resource_dialog_eyebrow")
        _set_widget_metadata(
            self._eyebrow_label,
            tooltip="Resource recovery workspace.",
            accessible_name="Resource recovery workspace.",
        )
        hero_copy.addWidget(self._eyebrow_label, 0, Qt.AlignLeft)

        full_title = "Replace Missing Resources"
        self._title_label = QLabel(_compact_resource_title(full_title))
        self._title_label.setObjectName("resource_dialog_title")
        _set_widget_metadata(
            self._title_label,
            tooltip=f"Resource replacement title: {full_title}.",
            accessible_name=f"Resource replacement title: {full_title}.",
        )
        hero_copy.addWidget(self._title_label)

        self._subtitle_label = QLabel(
            "Map each missing project asset to an external file before the replacement batch updates resource names inside the project."
        )
        self._subtitle_label.setObjectName("resource_dialog_subtitle")
        self._subtitle_label.setWordWrap(True)
        _set_widget_metadata(
            self._subtitle_label,
            tooltip=self._subtitle_label.text(),
            accessible_name=self._subtitle_label.text(),
        )
        hero_copy.addWidget(self._subtitle_label)
        self._eyebrow_label.hide()
        self._subtitle_label.hide()
        hero_copy.addStretch(1)
        header_layout.addLayout(hero_copy, 3)

        self._metrics_frame = QFrame()
        self._metrics_frame.setObjectName("resource_dialog_metrics_frame")
        metrics_layout = QVBoxLayout(self._metrics_frame)
        metrics_layout.setContentsMargins(0, 0, 0, 0)
        metrics_layout.setSpacing(6)
        self._missing_metric_value = _create_dialog_metric_card(metrics_layout, "Missing")
        self._candidate_metric_value = _create_dialog_metric_card(metrics_layout, "Candidates")
        self._selected_metric_value = _create_dialog_metric_card(metrics_layout, "Selection")
        header_layout.addWidget(self._metrics_frame, 2)
        layout.addWidget(self._header_frame)

        content_card = QFrame()
        content_card.setObjectName("resource_dialog_card")
        content_layout = QVBoxLayout(content_card)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(_RESOURCE_DIALOG_CONTENT_SPACING)

        self._caption = CaptionLabel(
            "Choose replacement files for missing resources. "
            "The selected file names become the new project resource names."
        )
        self._caption.setObjectName("resource_dialog_summary")
        self._caption.setWordWrap(True)
        content_layout.addWidget(self._caption)
        self._caption.hide()

        self._table = QTableWidget(len(self._missing_names), 2, self)
        _prepare_dialog_table(self._table)
        self._table.setHorizontalHeaderLabels(["Missing Resource", "Replacement File"])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionMode(QAbstractItemView.NoSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        content_layout.addWidget(self._table, 1)

        for row, missing_name in enumerate(self._missing_names):
            name_item = QTableWidgetItem(missing_name)
            name_item.setFlags(Qt.ItemIsEnabled)
            self._table.setItem(row, 0, name_item)

            combo = QComboBox(self._table)
            combo.addItem("(Skip)", "")
            for source_path in self._source_paths:
                combo.addItem(os.path.basename(source_path), source_path)

            exact_index = 0
            for index in range(1, combo.count()):
                source_path = combo.itemData(index)
                if os.path.basename(source_path).lower() == missing_name.lower():
                    exact_index = index
                    break
            if exact_index == 0 and len(self._missing_names) == 1 and len(self._source_paths) == 1:
                exact_index = 1
            combo.setCurrentIndex(exact_index)
            combo.currentIndexChanged.connect(self._update_accessibility_summary)

            self._table.setCellWidget(row, 1, combo)
            self._combos.append((missing_name, combo))
        layout.addWidget(content_card, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        self._ok_button = buttons.button(QDialogButtonBox.Ok)
        self._cancel_button = buttons.button(QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._metrics_frame.hide()
        self._update_accessibility_summary()

    def _selected_paths(self):
        return [combo.currentData() for _, combo in self._combos if combo.currentData()]

    def _duplicate_selected_paths(self):
        seen = set()
        duplicates = set()
        for path in self._selected_paths():
            if path in seen:
                duplicates.add(path)
            else:
                seen.add(path)
        return duplicates

    def _update_accessibility_summary(self):
        selected_count = len(self._selected_paths())
        duplicate_count = len(self._duplicate_selected_paths())
        summary = (
            f"Replace missing resources: {_count_label(len(self._missing_names), 'missing resource')}. "
            f"{_count_label(len(self._source_paths), 'candidate file')} available. "
            f"{_count_label(selected_count, 'replacement')} selected."
        )
        if duplicate_count:
            summary += f" {_count_label(duplicate_count, 'duplicate replacement file')} selected."

        self._missing_metric_value.setText(_count_label(len(self._missing_names), "resource"))
        self._candidate_metric_value.setText(_count_label(len(self._source_paths), "file"))
        self._selected_metric_value.setText(
            f"{_count_label(selected_count, 'replacement')} | {_count_label(duplicate_count, 'duplicate')}"
            if duplicate_count
            else _count_label(selected_count, "replacement")
        )

        _set_widget_metadata(self, tooltip=summary, accessible_name=summary)
        _set_widget_metadata(
            self._header_frame,
            tooltip=f"Resource dialog header. {summary}",
            accessible_name=f"Resource dialog header. {summary}",
        )
        _update_dialog_metric_metadata(self._missing_metric_value)
        _update_dialog_metric_metadata(self._candidate_metric_value)
        _update_dialog_metric_metadata(self._selected_metric_value)
        _set_widget_metadata(
            self._caption,
            tooltip=self._caption.text(),
            accessible_name=f"Replace missing resources help: {self._caption.text()}",
        )
        _set_widget_metadata(
            self._table,
            tooltip=(
                f"Missing resource replacement table: {_count_label(len(self._missing_names), 'row')}. "
                f"{_count_label(selected_count, 'replacement')} selected."
            ),
            accessible_name=(
                f"Missing resource replacement table: {_count_label(len(self._missing_names), 'row')}. "
                f"{_count_label(selected_count, 'replacement')} selected."
            ),
        )
        for missing_name, combo in self._combos:
            selection_text = combo.currentText() or "(Skip)"
            _set_widget_metadata(
                combo,
                tooltip=f"Choose replacement file for {missing_name}. Current selection: {selection_text}.",
                accessible_name=f"Replacement for {missing_name}: {selection_text}",
            )
        if self._ok_button is not None:
            if duplicate_count:
                tooltip = "Resolve duplicate replacement files before continuing."
            elif selected_count:
                tooltip = "Apply the selected replacement files."
            else:
                tooltip = "Choose at least one replacement file to continue."
            _set_widget_metadata(
                self._ok_button,
                tooltip=tooltip,
                accessible_name=(
                    "Confirm replacement files"
                    if selected_count and not duplicate_count
                    else "Confirm replacement files unavailable"
                ),
            )
        if self._cancel_button is not None:
            _set_widget_metadata(
                self._cancel_button,
                tooltip="Cancel replacing missing resources.",
                accessible_name="Cancel replacing missing resources",
            )

    def selected_mapping(self):
        mapping = {}
        for missing_name, combo in self._combos:
            source_path = combo.currentData()
            if source_path:
                mapping[missing_name] = source_path
        return mapping

    def accept(self):
        selected_paths = []
        for _, combo in self._combos:
            source_path = combo.currentData()
            if not source_path:
                continue
            if source_path in selected_paths:
                QMessageBox.warning(
                    self,
                    "Duplicate Replacement",
                    "Each replacement file can only be used once in a batch replace.",
                )
                return
            selected_paths.append(source_path)

        if not selected_paths:
            QMessageBox.warning(
                self,
                "No Replacements Selected",
                "Choose at least one replacement file or cancel the dialog.",
            )
            return

        super().accept()


class _ReferenceImpactDialog(QDialog):
    """Confirm destructive actions and show impacted references."""

    NAVIGATE_RESULT = 2

    def __init__(self, parent, title, summary, usages, confirm_text):
        super().__init__(parent)
        self.setObjectName("resource_dialog_shell")
        self._usages = list(usages)
        self._selected_usage = ("", "")
        self.setWindowTitle(title)
        self.setMinimumSize(760, 520)
        self.resize(860, 560)

        layout = QVBoxLayout(self)
        _apply_resource_dialog_shell_layout(layout)

        self._header_frame = QFrame()
        self._header_frame.setObjectName("resource_dialog_header")
        header_layout = QHBoxLayout(self._header_frame)
        header_layout.setContentsMargins(12, 10, 12, 10)
        header_layout.setSpacing(12)

        hero_copy = QVBoxLayout()
        hero_copy.setContentsMargins(0, 0, 0, 0)
        hero_copy.setSpacing(4)

        self._eyebrow_label = QLabel("Impact Review")
        self._eyebrow_label.setObjectName("resource_dialog_eyebrow")
        _set_widget_metadata(
            self._eyebrow_label,
            tooltip="Resource impact workspace.",
            accessible_name="Resource impact workspace.",
        )
        hero_copy.addWidget(self._eyebrow_label, 0, Qt.AlignLeft)

        full_title = title or "Review Reference Impact"
        self._title_label = QLabel(_compact_resource_title(full_title))
        self._title_label.setObjectName("resource_dialog_title")
        _set_widget_metadata(
            self._title_label,
            tooltip=f"Reference impact title: {full_title}.",
            accessible_name=f"Reference impact title: {full_title}.",
        )
        hero_copy.addWidget(self._title_label)

        self._subtitle_label = QLabel(
            "Inspect every affected widget reference before confirming a destructive resource operation or navigating directly to a usage."
        )
        self._subtitle_label.setObjectName("resource_dialog_subtitle")
        self._subtitle_label.setWordWrap(True)
        _set_widget_metadata(
            self._subtitle_label,
            tooltip=self._subtitle_label.text(),
            accessible_name=self._subtitle_label.text(),
        )
        hero_copy.addWidget(self._subtitle_label)
        self._eyebrow_label.hide()
        self._subtitle_label.hide()
        hero_copy.addStretch(1)
        header_layout.addLayout(hero_copy, 3)

        self._metrics_frame = QFrame()
        self._metrics_frame.setObjectName("resource_dialog_metrics_frame")
        metrics_layout = QVBoxLayout(self._metrics_frame)
        metrics_layout.setContentsMargins(0, 0, 0, 0)
        metrics_layout.setSpacing(6)
        self._usage_metric_value = _create_dialog_metric_card(metrics_layout, "Affected Usages")
        self._selection_metric_value = _create_dialog_metric_card(metrics_layout, "Selection")
        self._action_metric_value = _create_dialog_metric_card(metrics_layout, "Action")
        header_layout.addWidget(self._metrics_frame, 2)
        layout.addWidget(self._header_frame)

        content_card = QFrame()
        content_card.setObjectName("resource_dialog_card")
        content_layout = QVBoxLayout(content_card)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(_RESOURCE_DIALOG_CONTENT_SPACING)

        self._summary_label = QLabel(summary)
        self._summary_label.setObjectName("resource_dialog_summary")
        self._summary_label.setWordWrap(True)
        content_layout.addWidget(self._summary_label)
        self._summary_label.hide()

        self._table = QTableWidget(len(usages), 3, self)
        _prepare_dialog_table(self._table)
        self._table.setHorizontalHeaderLabels(["Page", "Widget", "Property"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        for row, entry in enumerate(usages):
            page_item = QTableWidgetItem(entry.page_name)
            widget_text = entry.widget_name
            if entry.widget_type:
                widget_text = f"{entry.widget_name} ({entry.widget_type})"
            widget_item = QTableWidgetItem(widget_text)
            prop_item = QTableWidgetItem(entry.property_name)
            item_tooltip = f"Page: {entry.page_name}. Widget: {widget_text}. Property: {entry.property_name}."
            _set_item_metadata(page_item, item_tooltip)
            _set_item_metadata(widget_item, item_tooltip)
            _set_item_metadata(prop_item, item_tooltip)
            self._table.setItem(row, 0, page_item)
            self._table.setItem(row, 1, widget_item)
            self._table.setItem(row, 2, prop_item)

        if usages:
            self._table.selectRow(0)
        self._table.itemDoubleClicked.connect(lambda *_args: self._open_selected_usage())
        self._table.itemSelectionChanged.connect(self._update_accessibility_summary)
        content_layout.addWidget(self._table, 1)
        layout.addWidget(content_card, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        self._open_usage_button = buttons.addButton("Open", QDialogButtonBox.ActionRole)
        self._ok_button = buttons.button(QDialogButtonBox.Ok)
        if self._ok_button is not None:
            self._ok_button.setText(confirm_text or "Continue")
        self._cancel_button = buttons.button(QDialogButtonBox.Cancel)
        if self._cancel_button is not None:
            self._cancel_button.setText("Cancel")
        for button in (self._open_usage_button, self._ok_button, self._cancel_button):
            _set_compact_control_height(button)
        self._open_usage_button.clicked.connect(self._open_selected_usage)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._metrics_frame.hide()
        self._update_accessibility_summary()

    def selected_usage(self):
        return self._selected_usage

    def _current_usage_label(self):
        row = self._table.currentRow()
        if row < 0 or row >= len(self._usages):
            return "none"
        entry = self._usages[row]
        widget_text = entry.widget_name
        if entry.widget_type:
            widget_text = f"{entry.widget_name} ({entry.widget_type})"
        return f"{entry.page_name}/{widget_text}"

    def _update_accessibility_summary(self):
        selection_label = self._current_usage_label()
        summary = (
            f"{self.windowTitle()}: {_count_label(len(self._usages), 'affected usage')}. "
            f"Current selection: {selection_label}."
        )
        self._usage_metric_value.setText(_count_label(len(self._usages), "usage"))
        self._selection_metric_value.setText(selection_label)
        self._action_metric_value.setText(self._ok_button.text() if self._ok_button is not None else "Continue")
        _set_widget_metadata(self, tooltip=summary, accessible_name=summary)
        _set_widget_metadata(
            self._header_frame,
            tooltip=f"Resource dialog header. {summary}",
            accessible_name=f"Resource dialog header. {summary}",
        )
        _update_dialog_metric_metadata(self._usage_metric_value)
        _update_dialog_metric_metadata(self._selection_metric_value)
        _update_dialog_metric_metadata(self._action_metric_value)
        _set_widget_metadata(
            self._summary_label,
            tooltip=self._summary_label.text(),
            accessible_name=f"Reference impact summary: {self._summary_label.text()}",
        )
        _set_widget_metadata(
            self._table,
            tooltip=f"Affected usages table: {_count_label(len(self._usages), 'row')}. Current selection: {selection_label}.",
            accessible_name=f"Affected usages table: {_count_label(len(self._usages), 'row')}. Current selection: {selection_label}.",
        )
        _set_widget_metadata(
            self._open_usage_button,
            tooltip=(
                "Open the selected usage to review it in the editor."
                if selection_label != "none"
                else "Select a usage to open it in the editor."
            ),
            accessible_name="Open selected usage" if selection_label != "none" else "Open selected usage unavailable",
        )
        if self._ok_button is not None:
            _set_widget_metadata(self._ok_button, tooltip="Continue with this action.", accessible_name=self._ok_button.text() or "Continue")
        if self._cancel_button is not None:
            _set_widget_metadata(self._cancel_button, tooltip="Cancel this action.", accessible_name="Cancel")

    def _open_selected_usage(self):
        row = self._table.currentRow()
        if row < 0 or row >= len(self._usages):
            return
        entry = self._usages[row]
        self._selected_usage = (entry.page_name, entry.widget_name)
        self.done(self.NAVIGATE_RESULT)


class _BatchReplaceImpactDialog(QDialog):
    """Preview grouped rename impacts before batch replacement."""

    NAVIGATE_RESULT = 2

    def __init__(self, parent, title, resource_type, impacts, total_rename_count, confirm_text, current_page_name=""):
        super().__init__(parent)
        self.setObjectName("resource_dialog_shell")
        self._all_impacts = list(impacts)
        self._visible_impacts = []
        self._selected_usage = ("", "")
        self._resource_type = resource_type or ""
        self._total_rename_count = total_rename_count
        self._current_page_name = current_page_name or ""
        self.setWindowTitle(title)
        self.setMinimumSize(920, 660)
        self.resize(980, 720)

        layout = QVBoxLayout(self)
        _apply_resource_dialog_shell_layout(layout)

        self._header_frame = QFrame()
        self._header_frame.setObjectName("resource_dialog_header")
        header_layout = QHBoxLayout(self._header_frame)
        header_layout.setContentsMargins(12, 10, 12, 10)
        header_layout.setSpacing(12)

        hero_copy = QVBoxLayout()
        hero_copy.setContentsMargins(0, 0, 0, 0)
        hero_copy.setSpacing(4)

        self._eyebrow_label = QLabel("Batch Rename Impact")
        self._eyebrow_label.setObjectName("resource_dialog_eyebrow")
        _set_widget_metadata(
            self._eyebrow_label,
            tooltip="Batch rename impact workspace.",
            accessible_name="Batch rename impact workspace.",
        )
        hero_copy.addWidget(self._eyebrow_label, 0, Qt.AlignLeft)

        full_title = title or "Review Batch Replace Impact"
        self._title_label = QLabel(_compact_resource_title(full_title))
        self._title_label.setObjectName("resource_dialog_title")
        _set_widget_metadata(
            self._title_label,
            tooltip=f"Batch replace impact title: {full_title}.",
            accessible_name=f"Batch replace impact title: {full_title}.",
        )
        hero_copy.addWidget(self._title_label)

        self._subtitle_label = QLabel(
            "Review grouped rename effects, optionally focus the current page, and inspect the downstream widget usages before applying the batch."
        )
        self._subtitle_label.setObjectName("resource_dialog_subtitle")
        self._subtitle_label.setWordWrap(True)
        _set_widget_metadata(
            self._subtitle_label,
            tooltip=self._subtitle_label.text(),
            accessible_name=self._subtitle_label.text(),
        )
        hero_copy.addWidget(self._subtitle_label)
        self._eyebrow_label.hide()
        self._subtitle_label.hide()
        hero_copy.addStretch(1)
        header_layout.addLayout(hero_copy, 3)

        self._metrics_frame = QFrame()
        self._metrics_frame.setObjectName("resource_dialog_metrics_frame")
        metrics_layout = QVBoxLayout(self._metrics_frame)
        metrics_layout.setContentsMargins(0, 0, 0, 0)
        metrics_layout.setSpacing(6)
        self._rename_metric_value = _create_dialog_metric_card(metrics_layout, "Visible Renames")
        self._usage_metric_value = _create_dialog_metric_card(metrics_layout, "Visible Usages")
        self._filter_metric_value = _create_dialog_metric_card(metrics_layout, "Page Filter")
        header_layout.addWidget(self._metrics_frame, 2)
        layout.addWidget(self._header_frame)

        summary_card = QFrame()
        summary_card.setObjectName("resource_dialog_card")
        summary_layout = QVBoxLayout(summary_card)
        summary_layout.setContentsMargins(0, 0, 0, 0)
        summary_layout.setSpacing(_RESOURCE_DIALOG_CONTENT_SPACING)

        self._summary_label = QLabel("")
        self._summary_label.setObjectName("resource_dialog_summary")
        self._summary_label.setWordWrap(True)
        summary_layout.addWidget(self._summary_label)
        self._summary_label.hide()

        if self._current_page_name:
            filter_row = QHBoxLayout()
            filter_row.setContentsMargins(0, 0, 0, 0)
            filter_row.setSpacing(8)
            self._current_page_only = QCheckBox("This Page")
            self._current_page_only.toggled.connect(self._refresh_impact_view)
            filter_row.addWidget(self._current_page_only)
            filter_row.addStretch()
            summary_layout.addLayout(filter_row)
        else:
            self._current_page_only = None
        layout.addWidget(summary_card)

        impact_card = QFrame()
        impact_card.setObjectName("resource_dialog_card")
        impact_layout = QVBoxLayout(impact_card)
        impact_layout.setContentsMargins(0, 0, 0, 0)
        impact_layout.setSpacing(_RESOURCE_DIALOG_CONTENT_SPACING)

        self._group_caption = QLabel("Impacts")
        self._group_caption.setObjectName("workspace_section_title")
        impact_layout.addWidget(self._group_caption)

        self._impact_table = QTableWidget(0, 4, self)
        _prepare_dialog_table(self._impact_table)
        self._impact_table.setHorizontalHeaderLabels(["Missing Resource", "Replacement File", "Widgets", "Pages"])
        self._impact_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._impact_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._impact_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._impact_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._impact_table.verticalHeader().setVisible(False)
        self._impact_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._impact_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._impact_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._impact_table.setMinimumHeight(160)
        self._impact_table.itemSelectionChanged.connect(self._refresh_usage_view)
        impact_layout.addWidget(self._impact_table, 1)
        layout.addWidget(impact_card, 1)

        usage_card = QFrame()
        usage_card.setObjectName("resource_dialog_card")
        usage_layout = QVBoxLayout(usage_card)
        usage_layout.setContentsMargins(0, 0, 0, 0)
        usage_layout.setSpacing(_RESOURCE_DIALOG_CONTENT_SPACING)

        self._usage_caption = QLabel("Usages")
        self._usage_caption.setObjectName("workspace_section_title")
        usage_layout.addWidget(self._usage_caption)

        self._usage_table = QTableWidget(0, 3, self)
        _prepare_dialog_table(self._usage_table)
        self._usage_table.setHorizontalHeaderLabels(["Page", "Widget", "Property"])
        self._usage_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._usage_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._usage_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._usage_table.verticalHeader().setVisible(False)
        self._usage_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._usage_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._usage_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._usage_table.itemDoubleClicked.connect(lambda *_args: self._open_selected_usage())
        self._usage_table.itemSelectionChanged.connect(self._update_accessibility_summary)
        usage_layout.addWidget(self._usage_table, 1)
        layout.addWidget(usage_card, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        self._open_usage_button = buttons.addButton("Open", QDialogButtonBox.ActionRole)
        self._ok_button = buttons.button(QDialogButtonBox.Ok)
        if self._ok_button is not None:
            self._ok_button.setText(confirm_text or "Continue")
        self._cancel_button = buttons.button(QDialogButtonBox.Cancel)
        if self._cancel_button is not None:
            self._cancel_button.setText("Cancel")
        for button in (self._open_usage_button, self._ok_button, self._cancel_button):
            _set_compact_control_height(button)
        self._open_usage_button.clicked.connect(self._open_selected_usage)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._metrics_frame.hide()
        self._refresh_impact_view()

    def selected_usage(self):
        return self._selected_usage

    def _filter_to_current_page(self):
        return self._current_page_only is not None and self._current_page_only.isChecked() and bool(self._current_page_name)

    def _current_impact_label(self):
        impact = self._current_impact()
        if impact is None:
            return "none"
        return f"{impact['old_name']} -> {impact['new_name']}"

    def _current_usage_label(self):
        row = self._usage_table.currentRow()
        impact = self._current_impact()
        usages = [] if impact is None else impact["usages"]
        if row < 0 or row >= len(usages):
            return "none"
        entry = usages[row]
        widget_text = entry.widget_name
        if entry.widget_type:
            widget_text = f"{entry.widget_name} ({entry.widget_type})"
        return f"{entry.page_name}/{widget_text} [{entry.property_name}]"

    def _update_accessibility_summary(self):
        impact_label = self._current_impact_label()
        usage_label = self._current_usage_label()
        total_usage_count = sum(len(entry["usages"]) for entry in self._visible_impacts)
        current_usage_count = self._usage_table.rowCount()
        filter_summary = (
            f"Current page only: {'on' if self._filter_to_current_page() else 'off'}."
            if self._current_page_only is not None
            else "Current page filter unavailable."
        )
        dialog_summary = (
            f"{self.windowTitle()}: {_count_label(len(self._visible_impacts), 'visible rename impact')}. "
            f"{_count_label(total_usage_count, 'visible usage')} shown. "
            f"{filter_summary} Current rename: {impact_label}. Current usage: {usage_label}."
        )
        self._rename_metric_value.setText(_count_label(len(self._visible_impacts), "rename"))
        self._usage_metric_value.setText(_count_label(total_usage_count, "usage"))
        self._filter_metric_value.setText("Current page only" if self._filter_to_current_page() else "All pages")
        _set_widget_metadata(self, tooltip=dialog_summary, accessible_name=dialog_summary)
        _set_widget_metadata(
            self._header_frame,
            tooltip=f"Resource dialog header. {dialog_summary}",
            accessible_name=f"Resource dialog header. {dialog_summary}",
        )
        _update_dialog_metric_metadata(self._rename_metric_value)
        _update_dialog_metric_metadata(self._usage_metric_value)
        _update_dialog_metric_metadata(self._filter_metric_value)
        _set_widget_metadata(
            self._summary_label,
            tooltip=self._summary_label.text(),
            accessible_name=f"Batch replace summary: {self._summary_label.text()}",
        )
        if self._current_page_only is not None:
            _set_widget_metadata(
                self._current_page_only,
                tooltip=(
                    f"Showing only impacts on the current page: {self._current_page_name}."
                    if self._current_page_only.isChecked()
                    else f"Filter impacts to the current page: {self._current_page_name}."
                ),
                accessible_name=f"Current page only filter: {'on' if self._current_page_only.isChecked() else 'off'}",
            )
        _set_widget_metadata(self._group_caption, tooltip=self._group_caption.text(), accessible_name=self._group_caption.text())
        _set_widget_metadata(self._usage_caption, tooltip=self._usage_caption.text(), accessible_name=self._usage_caption.text())
        _set_widget_metadata(
            self._impact_table,
            tooltip=f"Rename impact table: {_count_label(len(self._visible_impacts), 'row')}. Current selection: {impact_label}.",
            accessible_name=f"Rename impact table: {_count_label(len(self._visible_impacts), 'row')}. Current selection: {impact_label}.",
        )
        _set_widget_metadata(
            self._usage_table,
            tooltip=f"Affected usages table: {_count_label(current_usage_count, 'row')}. Current selection: {usage_label}.",
            accessible_name=f"Affected usages table: {_count_label(current_usage_count, 'row')}. Current selection: {usage_label}.",
        )
        _set_widget_metadata(
            self._open_usage_button,
            tooltip=(
                "Open the selected affected usage in the editor."
                if usage_label != "none"
                else "Select an affected usage to open it in the editor."
            ),
            accessible_name=(
                "Open selected affected usage"
                if usage_label != "none"
                else "Open selected affected usage unavailable"
            ),
        )
        if self._ok_button is not None:
            _set_widget_metadata(
                self._ok_button,
                tooltip="Apply the selected batch replacements.",
                accessible_name=(self._ok_button.text() or "Continue") if self._visible_impacts else f"{self._ok_button.text() or 'Continue'} unavailable",
            )
        if self._cancel_button is not None:
            _set_widget_metadata(
                self._cancel_button,
                tooltip="Cancel reviewing batch replacement impacts.",
                accessible_name="Cancel batch replacement impact review",
            )

    def _build_visible_impacts(self):
        impacts = []
        for entry in self._all_impacts:
            usages = list(entry["usages"])
            if self._filter_to_current_page():
                usages = [usage for usage in usages if usage.page_name == self._current_page_name]
            if not usages:
                continue

            impacts.append(
                {
                    "old_name": entry["old_name"],
                    "new_name": entry["new_name"],
                    "usages": usages,
                    "widget_count": len(usages),
                    "page_count": len({usage.page_name for usage in usages}),
                }
            )
        return impacts

    def _update_summary(self):
        total_impacted_rename_count = len(self._all_impacts)
        total_widget_count = sum(entry["widget_count"] for entry in self._all_impacts)
        total_page_count = len(
            {
                usage.page_name
                for entry in self._all_impacts
                for usage in entry["usages"]
            }
        )
        rename_noun = "resource" if self._total_rename_count == 1 else "resources"
        impacted_noun = "rename" if total_impacted_rename_count == 1 else "renames"
        widget_noun = "widget reference" if total_widget_count == 1 else "widget references"
        page_noun = "page" if total_page_count == 1 else "pages"

        summary_lines = [f"The selected replacements will rename {self._total_rename_count} missing {self._resource_type} {rename_noun}."]
        if total_impacted_rename_count != self._total_rename_count:
            summary_lines.append(f"{total_impacted_rename_count} {impacted_noun} affect widget references.")

        if not self._filter_to_current_page():
            summary_lines.append(
                f"Those renames affect {total_widget_count} {widget_noun} across {total_page_count} {page_noun}. "
                "Select a rename to inspect the impacted widgets before continuing."
            )
            self._summary_label.setText("\n".join(summary_lines))
            return

        visible_rename_count = len(self._visible_impacts)
        visible_widget_count = sum(entry["widget_count"] for entry in self._visible_impacts)
        current_page_widget_noun = "widget reference" if visible_widget_count == 1 else "widget references"
        current_page_rename_noun = "rename" if visible_rename_count == 1 else "renames"
        summary_lines.append(f"Showing impacts on the current page: {self._current_page_name}.")
        if not self._visible_impacts:
            summary_lines.append(
                f"No affected usages were found on the current page ({total_widget_count} total {widget_noun} across {total_page_count} {page_noun})."
            )
            summary_lines.append("Uncheck This Page to inspect all project usages.")
            self._summary_label.setText("\n".join(summary_lines))
            return

        summary_lines.append(
            f"{visible_rename_count} {current_page_rename_noun} affect {visible_widget_count} {current_page_widget_noun} on the current page "
            f"({total_widget_count} total across {total_page_count} {page_noun})."
        )
        summary_lines.append("Select a rename to inspect the impacted widgets before continuing.")
        self._summary_label.setText("\n".join(summary_lines))

    def _refresh_impact_view(self):
        selected_key = None
        current_impact = self._current_impact()
        if current_impact is not None:
            selected_key = (current_impact["old_name"], current_impact["new_name"])

        self._visible_impacts = self._build_visible_impacts()
        self._impact_table.setRowCount(len(self._visible_impacts))
        target_row = 0
        matched_row = False
        for row, entry in enumerate(self._visible_impacts):
            old_item = QTableWidgetItem(entry["old_name"])
            new_item = QTableWidgetItem(entry["new_name"])
            widget_item = QTableWidgetItem(str(entry["widget_count"]))
            page_item = QTableWidgetItem(str(entry["page_count"]))
            item_tooltip = (
                f"Rename {entry['old_name']} to {entry['new_name']}. "
                f"{_count_label(entry['widget_count'], 'widget')} affected across {_count_label(entry['page_count'], 'page')}."
            )
            _set_item_metadata(old_item, item_tooltip)
            _set_item_metadata(new_item, item_tooltip)
            _set_item_metadata(widget_item, item_tooltip)
            _set_item_metadata(page_item, item_tooltip)
            self._impact_table.setItem(row, 0, old_item)
            self._impact_table.setItem(row, 1, new_item)
            self._impact_table.setItem(row, 2, widget_item)
            self._impact_table.setItem(row, 3, page_item)
            if selected_key == (entry["old_name"], entry["new_name"]):
                target_row = row
                matched_row = True

        self._update_summary()
        if self._visible_impacts:
            self._impact_table.selectRow(target_row if matched_row else 0)
        self._refresh_usage_view()

    def _current_impact(self):
        row = self._impact_table.currentRow()
        if row < 0 or row >= len(self._visible_impacts):
            return None
        return self._visible_impacts[row]

    def _refresh_usage_view(self):
        impact = self._current_impact()
        usages = [] if impact is None else impact["usages"]
        self._usage_table.setRowCount(len(usages))
        for row, entry in enumerate(usages):
            page_item = QTableWidgetItem(entry.page_name)
            widget_text = entry.widget_name
            if entry.widget_type:
                widget_text = f"{entry.widget_name} ({entry.widget_type})"
            widget_item = QTableWidgetItem(widget_text)
            prop_item = QTableWidgetItem(entry.property_name)
            item_tooltip = f"Page: {entry.page_name}. Widget: {widget_text}. Property: {entry.property_name}."
            _set_item_metadata(page_item, item_tooltip)
            _set_item_metadata(widget_item, item_tooltip)
            _set_item_metadata(prop_item, item_tooltip)
            self._usage_table.setItem(row, 0, page_item)
            self._usage_table.setItem(row, 1, widget_item)
            self._usage_table.setItem(row, 2, prop_item)
        has_usages = bool(usages)
        self._open_usage_button.setEnabled(has_usages)
        if has_usages:
            self._usage_table.selectRow(0)
        self._update_accessibility_summary()

    def _open_selected_usage(self):
        impact = self._current_impact()
        if impact is None:
            return
        usages = impact["usages"]
        row = self._usage_table.currentRow()
        if row < 0 or row >= len(usages):
            return
        entry = usages[row]
        self._selected_usage = (entry.page_name, entry.widget_name)
        self.done(self.NAVIGATE_RESULT)


class _CleanupUnusedDialog(QDialog):
    """Preview unused resources that will be removed from the current tab."""

    def __init__(self, parent, title, scope_label, names, *, search_text="", status_label="All"):
        super().__init__(parent)
        self._names = list(names)
        self._scope_label = str(scope_label or "")
        self._search_text = str(search_text or "").strip()
        self._status_label = str(status_label or "All")
        self.setWindowTitle(title or "Clean Unused")
        self.setMinimumSize(640, 420)
        self.resize(720, 480)

        layout = QVBoxLayout(self)
        _apply_resource_dialog_shell_layout(layout)

        self._title_label = QLabel(title or "Clean Unused")
        self._title_label.setObjectName("resource_dialog_title")
        layout.addWidget(self._title_label)

        search_label = self._search_text or "none"
        self._summary_label = QLabel(
            f"Remove {_count_label(len(self._names), 'unused item')} from {self._scope_label}. "
            f"Search: {search_label}. Status: {self._status_label}."
        )
        self._summary_label.setWordWrap(True)
        layout.addWidget(self._summary_label)

        self._table = QTableWidget(len(self._names), 1, self)
        _prepare_dialog_table(self._table)
        self._table.setHorizontalHeaderLabels(["Name"])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        for row, name in enumerate(self._names):
            item = QTableWidgetItem(name)
            _set_item_metadata(item, name)
            self._table.setItem(row, 0, item)
        if self._names:
            self._table.selectRow(0)
        layout.addWidget(self._table, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        ok_button = buttons.button(QDialogButtonBox.Ok)
        cancel_button = buttons.button(QDialogButtonBox.Cancel)
        if ok_button is not None:
            ok_button.setText("Clean")
        if cancel_button is not None:
            cancel_button.setText("Cancel")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


# -- Main ResourcePanel --------------------------------------------------

class ResourcePanel(QWidget):
    """Catalog browser for project resources.

    Displays images, fonts, and text files from the resource catalog (resources.xml).
    No per-resource configuration -- config is at widget level in property panel.

    Signals:
        resource_selected(str, str): (resource_type, filename)
        resource_renamed(str, str, str): (resource_type, old_name, new_name)
        resource_deleted(str, str): (resource_type, filename)
        resource_imported():         files were imported, refresh needed
        feedback_message(str):       user-facing operation summary for status bars
        usage_activated(str, str):   (page_name, widget_name)
        string_key_renamed(str, str): (old_key, new_key)
        string_key_deleted(str, str): (key, replacement_text)
    """

    resource_selected = pyqtSignal(str, str)
    resource_renamed = pyqtSignal(str, str, str)
    resource_deleted = pyqtSignal(str, str)
    resource_imported = pyqtSignal()
    feedback_message = pyqtSignal(str)
    usage_activated = pyqtSignal(str, str)
    string_key_renamed = pyqtSignal(str, str)
    string_key_deleted = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._resource_dir = ""      # .eguiproject/resources/ base directory
        self._src_dir = ""           # same as _resource_dir (fonts/text root)
        self._images_dir = ""        # .eguiproject/resources/images/ subfolder
        self._last_external_import_dir = ""
        self._catalog = ResourceCatalog()
        self._string_catalog = StringResourceCatalog()
        self._font_id_cache = {}
        self._font_family_cache = {}
        self._string_table_updating = False  # guard against cellChanged feedback
        self._resource_usage_index = {}
        self._current_resource_type = ""
        self._current_resource_name = ""
        self._usage_page_name = ""
        self._resource_action_buttons = {}
        self._resource_more_menus = {}
        self._resource_search_inputs = {}
        self._resource_status_filters = {}
        self._resource_filter_summaries = {}
        self._resource_filter_reset_buttons = {}
        self._cleanup_unused_buttons = {}
        self.setAcceptDrops(True)
        self._init_ui()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.StyleChange, QEvent.PaletteChange):
            for resource_type in ("image", "font", "text"):
                self._refresh_resource_list(resource_type, selection_fallback="keep")

    # -- UI construction --

    def _init_ui(self):
        self.setObjectName("resource_panel_shell")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._panel_header = QFrame(self)
        self._panel_header.setObjectName("resource_panel_header")
        header_layout = QHBoxLayout(self._panel_header)
        header_layout.setContentsMargins(4, 4, 4, 4)
        header_layout.setSpacing(4)

        hero_copy = QVBoxLayout()
        hero_copy.setContentsMargins(0, 0, 0, 0)
        hero_copy.setSpacing(2)

        self._panel_eyebrow = QLabel("Resources")
        self._panel_eyebrow.setObjectName("resource_panel_eyebrow")
        _set_widget_metadata(
            self._panel_eyebrow,
            tooltip="Resource pipeline workspace.",
            accessible_name="Resource pipeline workspace.",
        )
        hero_copy.addWidget(self._panel_eyebrow, 0, Qt.AlignLeft)

        self._panel_title = QLabel("Resources")
        self._panel_title.setObjectName("resource_panel_title")
        _set_widget_metadata(
            self._panel_title,
            tooltip="Resource panel title: Project Resources.",
            accessible_name="Resource panel title: Project Resources.",
        )
        hero_copy.addWidget(self._panel_title)

        self._panel_subtitle = QLabel(
            "Manage image, font, text, and string files."
        )
        self._panel_subtitle.setObjectName("resource_panel_subtitle")
        self._panel_subtitle.setWordWrap(True)
        _set_widget_metadata(
            self._panel_subtitle,
            tooltip=self._panel_subtitle.text(),
            accessible_name=self._panel_subtitle.text(),
        )
        hero_copy.addWidget(self._panel_subtitle)

        self._panel_status = QLabel("")
        self._panel_status.setObjectName("resource_panel_status")
        self._panel_status.setWordWrap(True)
        hero_copy.addWidget(self._panel_status)
        header_layout.addLayout(hero_copy, 3)

        self._panel_metrics_frame = QFrame()
        self._panel_metrics_frame.setObjectName("resource_panel_metrics_frame")
        metrics_layout = QVBoxLayout(self._panel_metrics_frame)
        metrics_layout.setContentsMargins(0, 0, 0, 0)
        metrics_layout.setSpacing(2)
        self._catalog_metric_value = _create_resource_panel_metric_card(metrics_layout, "Catalog")
        self._missing_metric_value = _create_resource_panel_metric_card(metrics_layout, "Missing")
        self._selection_metric_value = _create_resource_panel_metric_card(metrics_layout, "Selection")
        header_layout.addWidget(self._panel_metrics_frame, 2)
        self._panel_header.hide()

        splitter = QSplitter(Qt.Vertical)
        splitter.setObjectName("resource_panel_splitter")
        splitter.setChildrenCollapsible(False)
        layout.addWidget(splitter, 1)

        # -- Top: Tabs --
        top_widget = QFrame()
        top_widget.setObjectName("resource_panel_card")
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(2)

        catalog_title = QLabel("Resource Catalog")
        catalog_title.setObjectName("workspace_section_title")
        top_layout.addWidget(catalog_title)
        catalog_title.hide()

        self._catalog_hint = QLabel(
            "Choose a tab, then import, restore missing files, or replace missing files."
        )
        self._catalog_hint.setObjectName("workspace_section_subtitle")
        self._catalog_hint.setWordWrap(True)
        top_layout.addWidget(self._catalog_hint)

        self._tabs = TabWidget()
        self._tabs.setObjectName("resource_panel_tabs")
        self._tabs.currentChanged.connect(self._on_panel_tab_changed)

        # Images tab
        img_tab = QWidget()
        img_tab_layout = QVBoxLayout(img_tab)
        img_tab_layout.setContentsMargins(0, 0, 0, 0)
        img_tab_layout.setSpacing(2)

        self._add_resource_filter_row(
            img_tab_layout,
            "image",
            (
                ("All", "all"),
                ("Missing", "missing"),
                ("Unused", "unused"),
            ),
        )

        self._image_list = _LazyImageList()
        _prepare_resource_panel_list(self._image_list, "resource_panel_image_list")
        self._image_list.itemClicked.connect(self._on_image_clicked)
        self._image_list.itemDoubleClicked.connect(self._on_image_double_clicked)
        self._image_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self._image_list.customContextMenuRequested.connect(
            lambda pos: self._show_context_menu(pos, "image")
        )
        img_tab_layout.addWidget(self._image_list, 1)

        img_btn_layout = QHBoxLayout()
        img_btn_layout.setSpacing(2)
        import_img_btn = QPushButton("Import...")
        import_img_btn.clicked.connect(self._on_import_image)
        img_btn_layout.addWidget(import_img_btn)
        copy_img_btn = QPushButton("Copy Names")
        copy_img_btn.clicked.connect(lambda: self._copy_visible_names("image"))
        img_btn_layout.addWidget(copy_img_btn)
        restore_img_btn = QPushButton("Restore Missing...")
        restore_img_btn.clicked.connect(lambda: self._restore_missing_resources("image"))
        img_btn_layout.addWidget(restore_img_btn)
        replace_img_btn = QPushButton("Replace Missing...")
        replace_img_btn.clicked.connect(lambda: self._replace_missing_resources("image"))
        img_btn_layout.addWidget(replace_img_btn)
        next_missing_img_btn = QPushButton("Next Missing")
        next_missing_img_btn.clicked.connect(lambda: self._focus_missing_resource("image"))
        img_btn_layout.addWidget(next_missing_img_btn)
        clean_unused_img_btn = QPushButton("Clean Unused...")
        clean_unused_img_btn.clicked.connect(lambda: self._clean_unused_resources("image"))
        img_btn_layout.addWidget(clean_unused_img_btn)
        image_more_btn = self._create_resource_more_button(
            "image",
            {
                "restore": restore_img_btn,
                "replace": replace_img_btn,
                "next_missing": next_missing_img_btn,
            },
        )
        img_btn_layout.addWidget(image_more_btn)
        restore_img_btn.hide()
        replace_img_btn.hide()
        next_missing_img_btn.hide()
        img_btn_layout.addStretch()
        img_tab_layout.addLayout(img_btn_layout)
        self._resource_action_buttons["image"] = {
            "import": import_img_btn,
            "copy_visible": copy_img_btn,
            "restore": restore_img_btn,
            "replace": replace_img_btn,
            "next_missing": next_missing_img_btn,
            "clean_unused": clean_unused_img_btn,
        }
        self._cleanup_unused_buttons["image"] = clean_unused_img_btn
        self._tabs.addTab(img_tab, "Images")

        # Fonts tab
        font_tab = QWidget()
        font_tab_layout = QVBoxLayout(font_tab)
        font_tab_layout.setContentsMargins(0, 0, 0, 0)
        font_tab_layout.setSpacing(2)

        self._add_resource_filter_row(
            font_tab_layout,
            "font",
            (
                ("All", "all"),
                ("Missing", "missing"),
                ("Unused", "unused"),
            ),
        )

        self._font_list = _DragResourceList("font")
        _prepare_resource_panel_list(self._font_list)
        self._font_list.itemClicked.connect(self._on_font_clicked)
        self._font_list.itemDoubleClicked.connect(self._on_font_double_clicked)
        self._font_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self._font_list.customContextMenuRequested.connect(
            lambda pos: self._show_context_menu(pos, "font")
        )
        font_tab_layout.addWidget(self._font_list, 1)

        font_btn_layout = QHBoxLayout()
        font_btn_layout.setSpacing(2)
        import_font_btn = QPushButton("Import...")
        import_font_btn.clicked.connect(self._on_import_font)
        font_btn_layout.addWidget(import_font_btn)
        copy_font_btn = QPushButton("Copy Names")
        copy_font_btn.clicked.connect(lambda: self._copy_visible_names("font"))
        font_btn_layout.addWidget(copy_font_btn)
        self._generate_charset_btn = QPushButton("Generate Charset...")
        self._generate_charset_btn.clicked.connect(self._on_generate_charset)
        font_btn_layout.addWidget(self._generate_charset_btn)
        restore_font_btn = QPushButton("Restore Missing...")
        restore_font_btn.clicked.connect(lambda: self._restore_missing_resources("font"))
        font_btn_layout.addWidget(restore_font_btn)
        replace_font_btn = QPushButton("Replace Missing...")
        replace_font_btn.clicked.connect(lambda: self._replace_missing_resources("font"))
        font_btn_layout.addWidget(replace_font_btn)
        next_missing_font_btn = QPushButton("Next Missing")
        next_missing_font_btn.clicked.connect(lambda: self._focus_missing_resource("font"))
        font_btn_layout.addWidget(next_missing_font_btn)
        clean_unused_font_btn = QPushButton("Clean Unused...")
        clean_unused_font_btn.clicked.connect(lambda: self._clean_unused_resources("font"))
        font_btn_layout.addWidget(clean_unused_font_btn)
        font_more_btn = self._create_resource_more_button(
            "font",
            {
                "restore": restore_font_btn,
                "replace": replace_font_btn,
                "next_missing": next_missing_font_btn,
            },
        )
        font_btn_layout.addWidget(font_more_btn)
        restore_font_btn.hide()
        replace_font_btn.hide()
        next_missing_font_btn.hide()
        font_btn_layout.addStretch()
        font_tab_layout.addLayout(font_btn_layout)
        self._resource_action_buttons["font"] = {
            "import": import_font_btn,
            "copy_visible": copy_font_btn,
            "restore": restore_font_btn,
            "replace": replace_font_btn,
            "next_missing": next_missing_font_btn,
            "clean_unused": clean_unused_font_btn,
        }
        self._cleanup_unused_buttons["font"] = clean_unused_font_btn
        self._tabs.addTab(font_tab, "Fonts")

        # Text tab
        text_tab = QWidget()
        text_tab_layout = QVBoxLayout(text_tab)
        text_tab_layout.setContentsMargins(0, 0, 0, 0)
        text_tab_layout.setSpacing(2)

        self._add_resource_filter_row(
            text_tab_layout,
            "text",
            (
                ("All", "all"),
                ("Missing", "missing"),
                ("Unused", "unused"),
            ),
        )

        self._text_list = _DragResourceList("text")
        _prepare_resource_panel_list(self._text_list)
        self._text_list.itemClicked.connect(self._on_text_clicked)
        self._text_list.itemDoubleClicked.connect(self._on_text_double_clicked)
        self._text_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self._text_list.customContextMenuRequested.connect(
            lambda pos: self._show_context_menu(pos, "text")
        )
        text_tab_layout.addWidget(self._text_list, 1)

        text_btn_layout = QHBoxLayout()
        text_btn_layout.setSpacing(2)
        import_text_btn = QPushButton("Import...")
        import_text_btn.clicked.connect(self._on_import_text)
        text_btn_layout.addWidget(import_text_btn)
        copy_text_btn = QPushButton("Copy Names")
        copy_text_btn.clicked.connect(lambda: self._copy_visible_names("text"))
        text_btn_layout.addWidget(copy_text_btn)
        self._generate_charset_text_btn = QPushButton("Generate Charset...")
        self._generate_charset_text_btn.clicked.connect(self._on_generate_charset)
        text_btn_layout.addWidget(self._generate_charset_text_btn)
        restore_text_btn = QPushButton("Restore Missing...")
        restore_text_btn.clicked.connect(lambda: self._restore_missing_resources("text"))
        text_btn_layout.addWidget(restore_text_btn)
        replace_text_btn = QPushButton("Replace Missing...")
        replace_text_btn.clicked.connect(lambda: self._replace_missing_resources("text"))
        text_btn_layout.addWidget(replace_text_btn)
        next_missing_text_btn = QPushButton("Next Missing")
        next_missing_text_btn.clicked.connect(lambda: self._focus_missing_resource("text"))
        text_btn_layout.addWidget(next_missing_text_btn)
        clean_unused_text_btn = QPushButton("Clean Unused...")
        clean_unused_text_btn.clicked.connect(lambda: self._clean_unused_resources("text"))
        text_btn_layout.addWidget(clean_unused_text_btn)
        text_more_btn = self._create_resource_more_button(
            "text",
            {
                "restore": restore_text_btn,
                "replace": replace_text_btn,
                "next_missing": next_missing_text_btn,
            },
        )
        text_btn_layout.addWidget(text_more_btn)
        restore_text_btn.hide()
        replace_text_btn.hide()
        next_missing_text_btn.hide()
        text_btn_layout.addStretch()
        text_tab_layout.addLayout(text_btn_layout)
        self._resource_action_buttons["text"] = {
            "import": import_text_btn,
            "copy_visible": copy_text_btn,
            "restore": restore_text_btn,
            "replace": replace_text_btn,
            "next_missing": next_missing_text_btn,
            "clean_unused": clean_unused_text_btn,
        }
        self._cleanup_unused_buttons["text"] = clean_unused_text_btn
        self._tabs.addTab(text_tab, "Text")

        # Strings (i18n) tab
        strings_tab = QWidget()
        strings_tab_layout = QVBoxLayout(strings_tab)
        strings_tab_layout.setContentsMargins(0, 0, 0, 0)
        strings_tab_layout.setSpacing(2)

        # Locale selector
        locale_row = QHBoxLayout()
        locale_row.setSpacing(2)
        locale_label = QLabel("Locale")
        locale_label.setObjectName("resource_panel_field_label")
        locale_row.addWidget(locale_label)
        self._locale_combo = QComboBox()
        self._locale_combo.setMinimumWidth(96)
        self._locale_combo.currentIndexChanged.connect(self._on_locale_changed)
        locale_row.addWidget(self._locale_combo)
        self._add_locale_btn = QPushButton("Add...")
        self._add_locale_btn.clicked.connect(self._on_add_locale)
        locale_row.addWidget(self._add_locale_btn)
        self._remove_locale_btn = QPushButton("Remove")
        self._remove_locale_btn.clicked.connect(self._on_remove_locale)
        locale_row.addWidget(self._remove_locale_btn)
        locale_row.addStretch()
        strings_tab_layout.addLayout(locale_row)

        self._add_resource_filter_row(
            strings_tab_layout,
            "string",
            (
                ("All", "all"),
                ("Unused", "unused"),
            ),
        )

        # String table
        self._string_table = QTableWidget()
        _prepare_resource_panel_table(self._string_table)
        self._string_table.setColumnCount(2)
        self._string_table.setHorizontalHeaderLabels(["Key", "Value"])
        self._string_table.horizontalHeader().setStretchLastSection(True)
        self._string_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeToContents
        )
        self._string_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._string_table.setSelectionMode(QTableWidget.SingleSelection)
        self._string_table.cellChanged.connect(self._on_string_cell_changed)
        self._string_table.currentCellChanged.connect(self._on_string_current_cell_changed)
        self._string_table.itemSelectionChanged.connect(self._refresh_usage_view)
        strings_tab_layout.addWidget(self._string_table, 1)

        # Buttons
        str_btn_layout = QHBoxLayout()
        str_btn_layout.setSpacing(2)
        self._add_key_btn = QPushButton("Add...")
        self._add_key_btn.clicked.connect(self._on_add_string_key)
        str_btn_layout.addWidget(self._add_key_btn)
        self._rename_key_btn = QPushButton("Rename...")
        self._rename_key_btn.clicked.connect(self._on_rename_string_key)
        str_btn_layout.addWidget(self._rename_key_btn)
        self._remove_key_btn = QPushButton("Remove")
        self._remove_key_btn.clicked.connect(self._on_remove_string_key)
        str_btn_layout.addWidget(self._remove_key_btn)
        self._copy_visible_string_btn = QPushButton("Copy Keys")
        self._copy_visible_string_btn.clicked.connect(self._copy_visible_string_keys)
        str_btn_layout.addWidget(self._copy_visible_string_btn)
        self._clean_unused_string_btn = QPushButton("Clean Unused...")
        self._clean_unused_string_btn.clicked.connect(self._clean_unused_string_keys)
        str_btn_layout.addWidget(self._clean_unused_string_btn)
        str_btn_layout.addStretch()
        strings_tab_layout.addLayout(str_btn_layout)
        self._cleanup_unused_buttons["string"] = self._clean_unused_string_btn

        self._tabs.addTab(strings_tab, "Strings")

        top_layout.addWidget(self._tabs, 1)
        splitter.addWidget(top_widget)

        # -- Bottom: Preview + usage area --
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(0)

        self._details_tabs = TabWidget()
        self._details_tabs.setObjectName("resource_panel_details_tabs")
        bottom_layout.addWidget(self._details_tabs, 1)

        preview_tab = QWidget()
        preview_tab_layout = QVBoxLayout(preview_tab)
        preview_tab_layout.setContentsMargins(2, 2, 2, 2)
        preview_tab_layout.setSpacing(2)

        self._preview_hint = QLabel("Preview the selected asset.")
        self._preview_hint.setObjectName("workspace_section_subtitle")
        self._preview_hint.hide()
        preview_tab_layout.addWidget(self._preview_hint)

        self._preview = _PreviewWidget()
        self._preview.setObjectName("resource_panel_preview")
        self._preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        preview_tab_layout.addWidget(self._preview, 1)
        self._details_tabs.addTab(preview_tab, "Preview")

        usage_tab = QWidget()
        usage_layout = QVBoxLayout(usage_tab)
        usage_layout.setContentsMargins(2, 2, 2, 2)
        usage_layout.setSpacing(2)

        self._usage_hint = QLabel("Review where the selected asset is used.")
        self._usage_hint.setObjectName("workspace_section_subtitle")
        self._usage_hint.hide()
        usage_layout.addWidget(self._usage_hint)

        usage_filter_row = QHBoxLayout()
        usage_filter_row.setSpacing(2)
        self._usage_current_page_only = QCheckBox("This Page")
        self._usage_current_page_only.toggled.connect(self._refresh_usage_view)
        self._usage_current_page_only.toggled.connect(self._update_usage_accessibility_metadata)
        usage_filter_row.addWidget(self._usage_current_page_only)
        usage_filter_row.addStretch()
        usage_layout.addLayout(usage_filter_row)

        self._usage_summary = QLabel("Select a resource to inspect usages.")
        self._usage_summary.setObjectName("resource_panel_summary")
        self._usage_summary.setWordWrap(True)
        usage_layout.addWidget(self._usage_summary)

        self._usage_table = QTableWidget()
        _prepare_resource_panel_table(self._usage_table)
        self._usage_table.setColumnCount(3)
        self._usage_table.setHorizontalHeaderLabels(["Page", "Widget", "Property"])
        self._usage_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._usage_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._usage_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._usage_table.verticalHeader().setVisible(False)
        self._usage_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._usage_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._usage_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._usage_table.itemDoubleClicked.connect(self._on_usage_item_activated)
        self._usage_table.itemSelectionChanged.connect(self._update_usage_accessibility_metadata)
        usage_layout.addWidget(self._usage_table, 1)
        self._details_tabs.addTab(usage_tab, "Usage")

        splitter.addWidget(bottom_widget)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        self._apply_compact_shell_metrics()
        self._update_resource_action_metadata()
        self._update_string_action_metadata()
        self._update_usage_accessibility_metadata()
        self._update_panel_overview()
        self._panel_eyebrow.hide()
        self._panel_subtitle.hide()
        self._panel_status.hide()
        self._panel_metrics_frame.hide()
        self._catalog_hint.hide()
        for metric_value in (
            self._catalog_metric_value,
            self._missing_metric_value,
            self._selection_metric_value,
        ):
            card = getattr(metric_value, "_resource_panel_metric_card", None)
            if card is not None:
                card.hide()

    def _apply_compact_shell_metrics(self):
        for widget in self._resource_search_inputs.values():
            _set_compact_control_height(widget)
        for widget in self._resource_status_filters.values():
            _set_compact_control_height(widget)
        for widget in self._resource_filter_reset_buttons.values():
            _set_compact_control_height(widget)
        for buttons in self._resource_action_buttons.values():
            for widget in buttons.values():
                _set_compact_control_height(widget)
        for spec in self._resource_more_menus.values():
            _set_compact_control_height(spec.get("button"))
        for widget in (
            self._locale_combo,
            self._add_locale_btn,
            self._remove_locale_btn,
            self._add_key_btn,
            self._rename_key_btn,
            self._remove_key_btn,
            self._copy_visible_string_btn,
            self._clean_unused_string_btn,
            self._generate_charset_btn,
            self._generate_charset_text_btn,
        ):
            _set_compact_control_height(widget)

    def _add_resource_filter_row(self, parent_layout, resource_type, statuses):
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(2)

        search_edit = QLineEdit()
        search_edit.setObjectName(f"resource_panel_{resource_type}_search")
        search_edit.setPlaceholderText("Search")
        search_edit.textChanged.connect(lambda _text, kind=resource_type: self._on_resource_filter_changed(kind))
        row.addWidget(search_edit, 1)

        status_combo = QComboBox()
        status_combo.setObjectName(f"resource_panel_{resource_type}_status")
        for label, value in statuses:
            status_combo.addItem(label, value)
        status_combo.currentIndexChanged.connect(lambda _index, kind=resource_type: self._on_resource_filter_changed(kind))
        row.addWidget(status_combo)

        reset_button = QPushButton("Reset")
        reset_button.clicked.connect(lambda checked=False, kind=resource_type: self._reset_resource_filter(kind))
        row.addWidget(reset_button)

        parent_layout.addLayout(row)
        summary_label = QLabel("")
        summary_label.setObjectName("workspace_section_subtitle")
        summary_label.setWordWrap(True)
        parent_layout.addWidget(summary_label)

        self._resource_search_inputs[resource_type] = search_edit
        self._resource_status_filters[resource_type] = status_combo
        self._resource_filter_summaries[resource_type] = summary_label
        self._resource_filter_reset_buttons[resource_type] = reset_button

    def _resource_search_text(self, resource_type):
        widget = self._resource_search_inputs.get(resource_type)
        return widget.text().strip() if widget is not None else ""

    def _resource_status_value(self, resource_type):
        widget = self._resource_status_filters.get(resource_type)
        if widget is None:
            return "all"
        value = widget.currentData()
        return str(value or "all")

    def _has_active_resource_filter(self, resource_type):
        return bool(self._resource_search_text(resource_type)) or self._resource_status_value(resource_type) != "all"

    def _resource_filter_summary_text(self, resource_type):
        search_label = self._resource_search_text(resource_type) or "none"
        status_widget = self._resource_status_filters.get(resource_type)
        status_label = status_widget.currentText() if status_widget is not None else "All"

        if resource_type == "string":
            total_count = len(self._string_catalog.all_keys)
            visible_count = len(self._filtered_string_keys())
            unused_count = len(self._unused_string_keys())
            locale_label = self._selected_locale_label()
            return (
                f"Showing {visible_count} of {total_count} string keys. "
                f"Unused: {unused_count}. Locale: {locale_label}. "
                f"Search: {search_label}. Status: {status_label}."
            )

        total_count = len(self._resource_names_for_type(resource_type))
        visible_count = len(self._filtered_resource_names(resource_type))
        missing_count = len(self._missing_resource_names(resource_type))
        unused_count = len(self._unused_resource_names(resource_type))
        resource_label = {
            "image": "image resources",
            "font": "font resources",
            "text": "text resources",
        }.get(resource_type, "resources")
        return (
            f"Showing {visible_count} of {total_count} {resource_label}. "
            f"Missing: {missing_count}. Unused: {unused_count}. "
            f"Search: {search_label}. Status: {status_label}."
        )

    def _update_resource_filter_metadata(self, resource_type):
        summary_label = self._resource_filter_summaries.get(resource_type)
        reset_button = self._resource_filter_reset_buttons.get(resource_type)
        summary_text = self._resource_filter_summary_text(resource_type)

        if summary_label is not None:
            summary_label.setText(summary_text)
            _set_widget_metadata(
                summary_label,
                tooltip=summary_text,
                accessible_name=f"Resource filter summary: {summary_text}",
            )

        if reset_button is not None:
            is_active = self._has_active_resource_filter(resource_type)
            reset_button.setEnabled(is_active)
            if resource_type == "string":
                noun = "string filters"
            else:
                noun = f"{resource_type} resource filters"
            if is_active:
                tooltip = f"Reset {noun} to the default view."
                accessible_name = f"Reset {noun}"
            else:
                tooltip = f"{noun.capitalize()} are already at the default view."
                accessible_name = f"Reset {noun} unavailable"
            _set_widget_metadata(
                reset_button,
                tooltip=tooltip,
                accessible_name=accessible_name,
            )

    def _reset_resource_filter(self, resource_type):
        search_edit = self._resource_search_inputs.get(resource_type)
        status_combo = self._resource_status_filters.get(resource_type)
        if search_edit is not None:
            search_edit.setText("")
        if status_combo is not None:
            default_index = status_combo.findData("all")
            if default_index >= 0:
                status_combo.setCurrentIndex(default_index)
        if resource_type == "string":
            self._refresh_string_table(selection_fallback="keep")
            self._update_string_action_metadata()
            return
        self._refresh_resource_list(resource_type, selection_fallback="keep")

    def _create_resource_more_button(self, resource_type, buttons):
        button = QToolButton()
        button.setText("More")
        button.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(button)
        menu.setToolTipsVisible(True)
        actions = {}
        for key, label in (
            ("restore", "Restore"),
            ("replace", "Replace"),
            ("next_missing", "Next"),
        ):
            action = menu.addAction(label)
            action.triggered.connect(lambda checked=False, source_button=buttons[key]: source_button.click())
            actions[key] = action
        button.setMenu(menu)
        _set_widget_metadata(
            button,
            tooltip=f"Open more {resource_type} actions.",
            accessible_name=f"More {resource_type} actions",
        )
        self._resource_more_menus[resource_type] = {"button": button, "actions": actions}
        return button

    def _sync_resource_more_menu(self, resource_type):
        spec = self._resource_more_menus.get(resource_type)
        buttons = self._resource_action_buttons.get(resource_type, {})
        if not spec or not buttons:
            return
        enabled_count = 0
        for action_key, action in spec["actions"].items():
            source_button = buttons.get(action_key)
            if source_button is None:
                action.setEnabled(False)
                continue
            action.setEnabled(source_button.isEnabled())
            tooltip = source_button.toolTip() or source_button.statusTip() or ""
            _set_action_metadata(action, tooltip)
            if source_button.isEnabled():
                enabled_count += 1
        button = spec["button"]
        button.setEnabled(enabled_count > 0 or bool(self._resource_dir))
        if button.isEnabled():
            tooltip = f"Open more {resource_type} actions."
            accessible_name = f"More {resource_type} actions"
        else:
            tooltip = f"Save or open a project first to manage {resource_type} resources."
            accessible_name = f"More {resource_type} actions unavailable"
        _set_widget_metadata(button, tooltip=tooltip, accessible_name=accessible_name)

    def _active_panel_tab_label(self):
        if not hasattr(self, "_tabs"):
            return "Resources"
        labels = {0: "Images", 1: "Fonts", 2: "Text", 3: "Strings"}
        return labels.get(self._tabs.currentIndex(), "Resources")

    def _current_panel_selection_label(self):
        if not hasattr(self, "_tabs"):
            return "none"
        active_type, active_name = self._selected_resource_for_active_tab()
        if active_name:
            return active_name
        if self._current_resource_name and (
            (active_type == self._current_resource_type) or not active_type
        ):
            return self._current_resource_name
        return "none"

    def _update_panel_overview(self):
        if not hasattr(self, "_catalog_metric_value"):
            return

        total_resources = (
            len(self._catalog.images)
            + len(self._catalog.fonts)
            + len(self._catalog.text_files)
            + len(self._string_catalog.all_keys)
        )
        total_missing = sum(len(self._missing_resource_names(resource_type)) for resource_type in ("image", "font", "text"))
        active_tab = self._active_panel_tab_label()
        selection_label = self._current_panel_selection_label()
        workspace_state = "configured" if self._resource_dir else "not configured"

        self._panel_status.setText(f"Workspace {workspace_state} | Active tab: {active_tab}")
        self._catalog_metric_value.setText(_count_label(total_resources, "asset"))
        self._missing_metric_value.setText(_count_label(total_missing, "missing file"))
        self._selection_metric_value.setText(f"{active_tab}: {selection_label}")

        panel_summary = (
            f"Resource panel: Workspace {workspace_state}. Active tab: {active_tab}. "
            f"Catalog: {self._catalog_metric_value.text()}. "
            f"Missing: {self._missing_metric_value.text()}. "
            f"Selection: {self._selection_metric_value.text()}."
        )
        _set_widget_metadata(self, tooltip=panel_summary, accessible_name=panel_summary)
        _set_widget_metadata(
            self._panel_header,
            tooltip=f"Resource header: Project Resources. Workspace {workspace_state}. Active tab: {active_tab}.",
            accessible_name=f"Resource header: Project Resources. Workspace {workspace_state}. Active tab: {active_tab}.",
        )

        _set_widget_metadata(
            self._panel_status,
            tooltip=f"Resource workspace state: {workspace_state}. Active tab: {active_tab}.",
            accessible_name=f"Resource workspace state: {workspace_state}. Active tab: {active_tab}",
        )
        _update_resource_panel_metric_metadata(self._catalog_metric_value)
        _update_resource_panel_metric_metadata(self._missing_metric_value)
        _update_resource_panel_metric_metadata(self._selection_metric_value)

    def _on_panel_tab_changed(self, _index):
        self._refresh_usage_view()
        self._update_panel_overview()

    def _on_resource_filter_changed(self, resource_type):
        if resource_type == "string":
            self._refresh_string_table(selection_fallback="keep")
            self._update_string_action_metadata()
            return
        self._refresh_resource_list(resource_type, selection_fallback="keep")

    def _build_resource_list_item(self, resource_type, fname):
        if resource_type == "image":
            full_path = os.path.join(self._images_dir, fname)
            item = QListWidgetItem(fname)
            item.setData(Qt.UserRole + 10, False)
        else:
            full_path = os.path.join(self._src_dir, fname)
            item = QListWidgetItem(fname)

        item.setData(Qt.UserRole, full_path)
        item.setData(Qt.UserRole + 1, fname)
        tooltip = fname
        if resource_type == "font":
            family = self._load_font(full_path) if os.path.isfile(full_path) else ""
            if family:
                tooltip += f"\nFamily: {family}"
        if not os.path.isfile(full_path):
            tooltip += "\n\u26a0 File not found!"
            item.setForeground(QColor(app_theme_tokens()["danger"]))
        _set_item_metadata(item, tooltip)
        return item

    def _apply_resource_item_selection(self, resource_type, item, *, emit_signal=False):
        if item is None:
            self._preview.clear_preview()
            self._update_current_resource("", "")
            return

        path = item.data(Qt.UserRole)
        filename = item.data(Qt.UserRole + 1)
        if resource_type == "image" and path and os.path.isfile(path):
            self._preview.show_image(path)
        elif resource_type == "font" and path and os.path.isfile(path):
            self._preview.show_font(path, self._font_family_cache.get(path, ""))
        elif resource_type == "text" and path and os.path.isfile(path):
            self._preview.show_text(path)
        else:
            self._preview.clear_preview()
        self._update_current_resource(resource_type, filename)
        if emit_signal:
            self.resource_selected.emit(resource_type, filename)

    def _refresh_resource_list(self, resource_type, selection_fallback="keep"):
        list_widget = self._list_widget_for_resource_type(resource_type)
        if list_widget is None:
            return

        if selection_fallback == "clear":
            selected_name = ""
        else:
            current_item = list_widget.currentItem()
            selected_name = current_item.data(Qt.UserRole + 1) if current_item is not None else ""
            if not selected_name and self._current_resource_type == resource_type:
                selected_name = self._current_resource_name

        visible_names = self._filtered_resource_names(resource_type)
        list_widget.clear()
        for fname in visible_names:
            list_widget.addItem(self._build_resource_list_item(resource_type, fname))

        if selected_name:
            matches = list_widget.findItems(selected_name, Qt.MatchExactly)
            if matches:
                list_widget.setCurrentItem(matches[0])
                self._apply_resource_item_selection(resource_type, matches[0], emit_signal=False)
            elif self._current_resource_type == resource_type:
                self._preview.clear_preview()
                self._update_current_resource("", "")
        elif self._current_resource_type == resource_type:
            self._preview.clear_preview()
            self._update_current_resource("", "")

        self._update_tab_titles()
        self._refresh_usage_view()

    # -- Public API --

    def set_resource_dir(self, resource_dir):
        """Set the source directory for resource files and reload.

        The directory should be .eguiproject/resources/ which contains:
          - images/  subfolder for image files
          - font/text files directly
        """
        selected_type = self._current_resource_type
        selected_name = self._current_resource_name
        self._resource_dir = resource_dir or ""
        self._src_dir = resource_dir or ""
        self._images_dir = resource_images_dir(resource_dir)
        self._image_list.clear()
        self._font_list.clear()
        self._text_list.clear()
        self._preview.clear_preview()

        if not self._src_dir or not os.path.isdir(self._src_dir):
            self._catalog = ResourceCatalog()
            self._update_tab_titles()
            self._refresh_usage_view()
            return

        self._refresh_resource_list("image")
        self._refresh_resource_list("font")
        self._refresh_resource_list("text")
        if selected_type and selected_name:
            self._select_resource_item(selected_type, selected_name)
        self._refresh_usage_view()

    def set_resource_catalog(self, catalog):
        """Set the resource catalog and refresh the panel."""
        self._catalog = catalog or ResourceCatalog()
        if self._resource_dir:
            self.set_resource_dir(self._resource_dir)
            return

        self._update_tab_titles()
        self._refresh_usage_view()

    def get_resource_catalog(self):
        """Return the current resource catalog."""
        return self._catalog

    def get_resource_dir(self):
        return self._resource_dir

    def get_src_dir(self):
        return self._src_dir

    def set_string_catalog(self, catalog):
        """Set the i18n string catalog and refresh the Strings tab."""
        self._string_catalog = catalog or StringResourceCatalog()
        self._refresh_string_tab()

    def get_string_catalog(self):
        """Return the current string catalog."""
        return self._string_catalog

    def set_resource_usage_index(self, usage_index):
        """Set the current project resource usage map."""
        self._resource_usage_index = usage_index or {}
        if self._resource_dir:
            for resource_type in ("image", "font", "text"):
                self._refresh_resource_list(resource_type, selection_fallback="keep")
        if hasattr(self, "_string_table"):
            self._refresh_string_table(selection_fallback="keep")
        self._refresh_usage_view()
        self._update_resource_action_metadata()
        self._update_string_action_metadata()

    def set_usage_page_context(self, page_name):
        """Set the current page name used by usage filtering."""
        self._usage_page_name = page_name or ""
        self._refresh_usage_view()

    # -- Internal helpers --

    def _format_resource_tab_title(self, label, total, missing):
        if missing <= 0:
            return f"{label} ({total})"
        return f"{label} ({total}, {missing} missing)"

    def _resource_names_for_type(self, resource_type):
        if resource_type == "image":
            return list(self._catalog.images)
        if resource_type == "font":
            return list(self._catalog.fonts)
        if resource_type == "text":
            return list(self._catalog.text_files)
        return []

    def _unused_resource_names(self, resource_type):
        return collect_unused_resource_names(
            self._resource_names_for_type(resource_type),
            self._resource_usage_index,
            resource_type,
        )

    def _unused_string_keys(self):
        return collect_unused_string_keys(self._string_catalog, self._resource_usage_index)

    def _filtered_resource_names(self, resource_type):
        return filter_resource_names(
            self._resource_names_for_type(resource_type),
            self._resource_usage_index,
            resource_type,
            search_text=self._resource_search_text(resource_type),
            status=self._resource_status_value(resource_type),
            missing_names=self._missing_resource_names(resource_type),
        )

    def _filtered_string_keys(self):
        return filter_string_keys(
            self._string_catalog,
            self._resource_usage_index,
            locale=self._get_selected_locale(),
            search_text=self._resource_search_text("string"),
            status=self._resource_status_value("string"),
        )

    def _visible_unused_names(self, resource_type):
        if resource_type == "string":
            unused_names = set(self._unused_string_keys())
            return [name for name in self._filtered_string_keys() if name in unused_names]
        unused_names = set(self._unused_resource_names(resource_type))
        return [name for name in self._filtered_resource_names(resource_type) if name in unused_names]

    def _resource_count_label(self, resource_type, count, *, missing=False):
        singular = {
            "image": "image resource",
            "font": "font resource",
            "text": "text resource",
        }.get(resource_type, "resource")
        plural = {
            "image": "image resources",
            "font": "font resources",
            "text": "text resources",
        }.get(resource_type, "resources")
        if missing:
            singular = f"missing {singular}"
            plural = f"missing {plural}"
        return _count_label(count, singular, plural)

    def _resource_action_label(self, action, resource_type):
        if action == "import":
            return f"Import {resource_type} resources"
        if action == "restore":
            return f"Restore missing {resource_type} resources"
        if action == "replace":
            return f"Replace missing {resource_type} resources"
        return f"Next missing {resource_type} resource"

    def _resource_action_base_tooltip(self, action, resource_type):
        action_tooltips = {
            "import": {
                "image": "Import image files into the project resource catalog.",
                "font": "Import font files into the project resource catalog.",
                "text": "Import supported-text .txt files into the project resource catalog.",
            },
            "restore": {
                "image": "Restore missing image files by matching selected filenames against missing catalog entries.",
                "font": "Restore missing font files by matching selected filenames against missing catalog entries.",
                "text": "Restore missing text files by matching selected filenames against missing catalog entries.",
            },
            "replace": {
                "image": "Replace missing image resources with new files and rewrite widget references to the new filenames.",
                "font": "Replace missing font resources with new files and rewrite widget references to the new filenames.",
                "text": "Replace missing text resources with new files and rewrite widget references to the new filenames.",
            },
            "next_missing": {
                "image": "Select the next missing image resource in this tab.",
                "font": "Select the next missing font resource in this tab.",
                "text": "Select the next missing text resource in this tab.",
            },
        }
        return action_tooltips.get(action, {}).get(resource_type, "")

    def _resource_action_unavailable_tooltip(self, action, resource_type):
        if not self._resource_dir:
            if action == "next_missing":
                return f"Save or open a project first to navigate missing {resource_type} resources."
            action_label = self._resource_action_label(action, resource_type).lower()
            return f"Save or open a project first to {action_label}."
        if action == "next_missing":
            return f"No missing {resource_type} resources to select in this tab."
        return f"No missing {resource_type} resources to {action} in this tab."

    def _update_resource_action_metadata(self):
        if not self._resource_action_buttons:
            return

        for resource_type, buttons in self._resource_action_buttons.items():
            total_count = len(self._resource_names_for_type(resource_type))
            missing_count = len(self._missing_resource_names(resource_type))
            visible_missing_count = len(self._visible_missing_resource_names(resource_type))
            visible_count = len(self._visible_names_for_type(resource_type))
            visible_unused_count = len(self._visible_unused_names(resource_type))
            total_label = self._resource_count_label(resource_type, total_count)
            missing_label = self._resource_count_label(resource_type, missing_count, missing=True)
            visible_missing_label = self._resource_count_label(resource_type, visible_missing_count, missing=True)

            import_tooltip = self._resource_action_unavailable_tooltip("import", resource_type)
            import_accessible_name = f"Import {resource_type} resources unavailable"
            if self._resource_dir:
                import_tooltip = f"{self._resource_action_base_tooltip('import', resource_type)} {total_label.capitalize()} listed."
                if missing_count:
                    import_tooltip += f" {missing_label.capitalize()}."
                import_accessible_name = f"Import {resource_type} resources. {total_label.capitalize()} listed."
                if missing_count:
                    import_accessible_name += f" {missing_label.capitalize()}."
            _set_widget_metadata(buttons["import"], tooltip=import_tooltip, accessible_name=import_accessible_name)

            copy_visible_button = buttons.get("copy_visible")
            if copy_visible_button is not None:
                copy_visible_button.setEnabled(visible_count > 0)
                if visible_count > 0:
                    tooltip = (
                        f"Copy the currently visible {resource_type} resource names. "
                        f"{visible_count} item{'s' if visible_count != 1 else ''} will be copied."
                    )
                    accessible_name = f"Copy visible {resource_type} resource names. {visible_count} visible items."
                else:
                    tooltip = f"No {resource_type} resources match the current filters."
                    accessible_name = f"Copy visible {resource_type} resource names unavailable"
                _set_widget_metadata(copy_visible_button, tooltip=tooltip, accessible_name=accessible_name)

            for action in ("restore", "replace", "next_missing"):
                action_label = self._resource_action_label(action, resource_type)
                buttons[action].setEnabled(bool(self._resource_dir and visible_missing_count > 0))
                if self._resource_dir and visible_missing_count > 0:
                    tooltip = f"{self._resource_action_base_tooltip(action, resource_type)} {visible_missing_label.capitalize()}."
                    if visible_missing_count != missing_count:
                        tooltip += f" {missing_label.capitalize()} total."
                    accessible_name = f"{action_label}. {visible_missing_label.capitalize()}."
                else:
                    tooltip = self._resource_action_unavailable_tooltip(action, resource_type)
                    if self._resource_dir and missing_count > 0 and self._has_active_resource_filter(resource_type):
                        tooltip = f"No missing {resource_type} resources match the current filters."
                    accessible_name = f"{action_label} unavailable"
                _set_widget_metadata(buttons[action], tooltip=tooltip, accessible_name=accessible_name)

            clean_unused_button = buttons.get("clean_unused")
            if clean_unused_button is not None:
                if self._resource_dir and visible_unused_count > 0:
                    tooltip = (
                        f"Preview and remove unused {resource_type} resources visible in the current filters. "
                        f"{visible_unused_count} unused item{'s' if visible_unused_count != 1 else ''} will be affected."
                    )
                    accessible_name = f"Clean unused {resource_type} resources. {visible_unused_count} visible unused items."
                elif self._resource_dir:
                    tooltip = f"No unused {resource_type} resources match the current filters."
                    accessible_name = f"Clean unused {resource_type} resources unavailable"
                else:
                    tooltip = f"Save or open a project first to clean unused {resource_type} resources."
                    accessible_name = f"Clean unused {resource_type} resources unavailable"
                clean_unused_button.setEnabled(bool(self._resource_dir and visible_unused_count > 0))
                _set_widget_metadata(clean_unused_button, tooltip=tooltip, accessible_name=accessible_name)

            search_edit = self._resource_search_inputs.get(resource_type)
            status_combo = self._resource_status_filters.get(resource_type)
            if search_edit is not None:
                search_text = self._resource_search_text(resource_type) or "none"
                tooltip = f"Search {resource_type} resources by filename. Current search: {search_text}."
                _set_widget_metadata(search_edit, tooltip=tooltip, accessible_name=tooltip)
            if status_combo is not None:
                status_label = status_combo.currentText() or "All"
                tooltip = f"Filter {resource_type} resources by status. Current filter: {status_label}."
                _set_widget_metadata(status_combo, tooltip=tooltip, accessible_name=tooltip)
            self._update_resource_filter_metadata(resource_type)
            self._sync_resource_more_menu(resource_type)

        charset_buttons = []
        if hasattr(self, "_generate_charset_btn"):
            charset_buttons.append(self._generate_charset_btn)
        if hasattr(self, "_generate_charset_text_btn"):
            charset_buttons.append(self._generate_charset_text_btn)
        if charset_buttons:
            if self._resource_dir:
                tooltip = (
                    "Generate a supported-text .txt resource from built-in charset presets, "
                    "then optionally bind it to the current widget."
                )
                accessible_name = "Generate font charset resource"
            else:
                tooltip = "Save or open a project first to generate font charset resources."
                accessible_name = "Generate font charset resource unavailable"
            for button in charset_buttons:
                _set_widget_metadata(
                    button,
                    tooltip=tooltip,
                    accessible_name=accessible_name,
                )

    def _selected_string_key(self):
        if not hasattr(self, "_string_table"):
            return ""
        row = self._string_table.currentRow()
        key_item = self._string_table.item(row, 0) if row >= 0 else None
        return key_item.text().strip() if key_item is not None else ""

    def _selected_locale_label(self):
        if not hasattr(self, "_locale_combo"):
            return "Default"
        idx = self._locale_combo.currentIndex()
        if idx >= 0:
            label = (self._locale_combo.currentText() or "").strip()
            if label:
                return label
            locale_code = self._locale_combo.itemData(idx)
            if locale_code == DEFAULT_LOCALE:
                return "Default"
            if locale_code:
                return locale_code
        return self._string_catalog.locale_display_names.get(DEFAULT_LOCALE, "Default")

    def _selected_string_usage_count(self):
        key = self._selected_string_key()
        if not key:
            return 0
        return len(self._resource_usage_index.get(("string", key), []))

    def _update_string_action_metadata(self):
        if not hasattr(self, "_locale_combo"):
            return

        locale_label = self._selected_locale_label()
        locale_count = len(self._string_catalog.locales)
        locale_count_label = _count_label(locale_count, "locale")
        key_count = len(self._string_catalog.all_keys)
        key_count_label = _count_label(key_count, "string key")
        selected_key = self._selected_string_key()
        usage_count = self._selected_string_usage_count()
        usage_label = _count_label(usage_count, "usage")
        current_key_label = selected_key or "none"

        locale_summary = f"String locale selector: {locale_label}. {locale_count_label.capitalize()} configured."
        _set_widget_metadata(self._locale_combo, tooltip=locale_summary, accessible_name=locale_summary)

        table_summary = (
            f"String resource table: {key_count_label.capitalize()}. "
            f"Current locale: {locale_label}. Current key: {current_key_label}."
        )
        _set_widget_metadata(self._string_table, tooltip=table_summary, accessible_name=table_summary)

        add_locale_tooltip = f"Add a new locale for translated string values. {locale_count_label.capitalize()} configured."
        _set_widget_metadata(
            self._add_locale_btn,
            tooltip=add_locale_tooltip,
            accessible_name=f"Add locale from {locale_label}. {locale_count_label.capitalize()} configured.",
        )

        if self._get_selected_locale() == DEFAULT_LOCALE:
            remove_locale_tooltip = "Select a non-default locale to remove it."
            remove_locale_name = f"Remove locale unavailable: {locale_label}"
        else:
            remove_locale_tooltip = f"Remove locale {locale_label} and all its translations."
            remove_locale_name = f"Remove locale: {locale_label}"
        _set_widget_metadata(
            self._remove_locale_btn,
            tooltip=remove_locale_tooltip,
            accessible_name=remove_locale_name,
        )

        add_key_tooltip = f"Add a new string key across all locales. {key_count_label.capitalize()} defined."
        _set_widget_metadata(
            self._add_key_btn,
            tooltip=add_key_tooltip,
            accessible_name=f"Add string key in {locale_label}. {key_count_label.capitalize()} defined.",
        )

        if selected_key:
            rename_key_tooltip = f"Rename string key {selected_key} across all locales."
            remove_key_tooltip = f"Remove string key {selected_key} from all locales."
            rename_key_name = f"Rename string key: {selected_key} in {locale_label}"
            remove_key_name = f"Remove string key: {selected_key} in {locale_label}"
            if usage_count:
                rename_key_tooltip += f" {usage_label.capitalize()} will be updated."
                remove_key_tooltip += f" {usage_label.capitalize()} will be updated."
                rename_key_name += f". {usage_label.capitalize()}."
                remove_key_name += f". {usage_label.capitalize()}."
        else:
            rename_key_tooltip = "Select a string key to rename it across all locales."
            remove_key_tooltip = "Select a string key to remove it from all locales."
            rename_key_name = f"Rename string key unavailable in {locale_label}"
            remove_key_name = f"Remove string key unavailable in {locale_label}"
        _set_widget_metadata(
            self._rename_key_btn,
            tooltip=rename_key_tooltip,
            accessible_name=rename_key_name,
        )
        _set_widget_metadata(
            self._remove_key_btn,
            tooltip=remove_key_tooltip,
            accessible_name=remove_key_name,
        )

        search_edit = self._resource_search_inputs.get("string")
        if search_edit is not None:
            search_text = self._resource_search_text("string") or "none"
            tooltip = f"Search string keys or values. Current locale: {locale_label}. Current search: {search_text}."
            _set_widget_metadata(search_edit, tooltip=tooltip, accessible_name=tooltip)

        status_combo = self._resource_status_filters.get("string")
        if status_combo is not None:
            status_label = status_combo.currentText() or "All"
            tooltip = f"Filter string keys by status. Current filter: {status_label}."
            _set_widget_metadata(status_combo, tooltip=tooltip, accessible_name=tooltip)

        clean_unused_count = len(self._visible_unused_names("string"))
        visible_string_count = len(self._visible_names_for_type("string"))
        if hasattr(self, "_copy_visible_string_btn"):
            self._copy_visible_string_btn.setEnabled(visible_string_count > 0)
            if visible_string_count > 0:
                tooltip = (
                    f"Copy the currently visible string keys. {visible_string_count} "
                    f"item{'s' if visible_string_count != 1 else ''} will be copied."
                )
                accessible_name = f"Copy visible string keys. {visible_string_count} visible items."
            else:
                tooltip = "No string keys match the current filters."
                accessible_name = "Copy visible string keys unavailable"
            _set_widget_metadata(
                self._copy_visible_string_btn,
                tooltip=tooltip,
                accessible_name=accessible_name,
            )
        if hasattr(self, "_clean_unused_string_btn"):
            if clean_unused_count > 0:
                tooltip = (
                    "Preview and remove unused string keys visible in the current filters. "
                    f"{clean_unused_count} unused item{'s' if clean_unused_count != 1 else ''} will be affected."
                )
                accessible_name = f"Clean unused string keys. {clean_unused_count} visible unused items."
            else:
                tooltip = "No unused string keys match the current filters."
                accessible_name = "Clean unused string keys unavailable"
            self._clean_unused_string_btn.setEnabled(clean_unused_count > 0)
            _set_widget_metadata(
                self._clean_unused_string_btn,
                tooltip=tooltip,
                accessible_name=accessible_name,
            )
        self._update_resource_filter_metadata("string")

    def _current_usage_selection_label(self):
        if not hasattr(self, "_usage_table"):
            return "none"
        row = self._usage_table.currentRow()
        if row < 0:
            return "none"
        page_item = self._usage_table.item(row, 0)
        widget_item = self._usage_table.item(row, 1)
        prop_item = self._usage_table.item(row, 2)
        if page_item is None or widget_item is None or prop_item is None:
            return "none"
        return f"{page_item.text()}/{widget_item.text()} [{prop_item.text()}]"

    def _update_usage_accessibility_metadata(self):
        if not hasattr(self, "_usage_table"):
            return

        if self._usage_page_name:
            if self._usage_current_page_only.isChecked():
                usage_filter_tooltip = f"Showing only usages on the current page: {self._usage_page_name}."
                usage_filter_name = f"Usage filter: current page only on for {self._usage_page_name}"
            else:
                usage_filter_tooltip = f"Filter usages to the current page: {self._usage_page_name}."
                usage_filter_name = f"Usage filter: current page only off for {self._usage_page_name}"
        else:
            usage_filter_tooltip = "Open or select a page to filter usages to the current page."
            usage_filter_name = "Usage filter unavailable: Current Page Only"
        _set_widget_metadata(
            self._usage_current_page_only,
            tooltip=usage_filter_tooltip,
            accessible_name=usage_filter_name,
        )

        summary_text = (self._usage_summary.text() or "").strip() or "No usage summary available."
        _set_widget_metadata(
            self._usage_summary,
            tooltip=summary_text,
            accessible_name=f"Resource usage summary: {summary_text}",
        )

        row_count = self._usage_table.rowCount()
        selection_label = self._current_usage_selection_label()
        table_summary = f"Resource usage table: {_count_label(row_count, 'row')}. Current selection: {selection_label}."
        _set_widget_metadata(self._usage_table, tooltip=table_summary, accessible_name=table_summary)
        self._update_panel_overview()

    def _update_tab_titles(self):
        n_img = len(self._catalog.images)
        n_font = len(self._catalog.fonts)
        n_text = len(self._catalog.text_files)
        missing_img = len(self._missing_resource_names("image"))
        missing_font = len(self._missing_resource_names("font"))
        missing_text = len(self._missing_resource_names("text"))
        n_str = len(self._string_catalog.all_keys)
        self._tabs.setTabText(0, self._format_resource_tab_title("Images", n_img, missing_img))
        self._tabs.setTabText(1, self._format_resource_tab_title("Fonts", n_font, missing_font))
        self._tabs.setTabText(2, self._format_resource_tab_title("Text", n_text, missing_text))
        self._tabs.setTabText(3, f"Strings ({n_str})")
        self._update_resource_action_metadata()
        self._update_panel_overview()

    def _selected_resource_for_active_tab(self):
        current_index = self._tabs.currentIndex()
        if current_index == 0:
            item = self._image_list.currentItem()
            return "image", item.data(Qt.UserRole + 1) if item is not None else ""
        if current_index == 1:
            item = self._font_list.currentItem()
            return "font", item.data(Qt.UserRole + 1) if item is not None else ""
        if current_index == 2:
            item = self._text_list.currentItem()
            return "text", item.data(Qt.UserRole + 1) if item is not None else ""
        if current_index == 3:
            row = self._string_table.currentRow()
            key_item = self._string_table.item(row, 0) if row >= 0 else None
            return "string", key_item.text() if key_item is not None else ""
        return "", ""

    def _update_current_resource(self, resource_type, filename):
        self._current_resource_type = resource_type or ""
        self._current_resource_name = filename or ""
        self._refresh_usage_view()
        self._update_panel_overview()

    def _clear_usage_view(self, summary):
        self._usage_summary.setText(summary)
        self._usage_table.setRowCount(0)
        self._update_usage_accessibility_metadata()

    def _refresh_usage_view(self):
        if not hasattr(self, "_usage_table"):
            return

        resource_type = self._current_resource_type
        resource_name = self._current_resource_name
        active_type, active_name = self._selected_resource_for_active_tab()
        if active_name:
            resource_type = active_type
            resource_name = active_name
            self._current_resource_type = active_type
            self._current_resource_name = active_name

        if not resource_type or not resource_name:
            self._clear_usage_view("Select an image, font, text resource, or string key to inspect references.")
            return

        all_usages = list(self._resource_usage_index.get((resource_type, resource_name), []))
        if not all_usages:
            self._clear_usage_view(f"'{resource_name}' is currently unused.")
            return

        usages = all_usages
        filter_to_current_page = self._usage_current_page_only.isChecked() and bool(self._usage_page_name)
        if filter_to_current_page:
            usages = [entry for entry in all_usages if entry.page_name == self._usage_page_name]
            if not usages:
                self._clear_usage_view(f"'{resource_name}' has no references on the current page.")
                return

        page_count = len({entry.page_name for entry in usages})
        widget_count = len(usages)
        page_noun = "page" if page_count == 1 else "pages"
        widget_noun = "widget" if widget_count == 1 else "widgets"
        if filter_to_current_page:
            total_widget_count = len(all_usages)
            total_page_count = len({entry.page_name for entry in all_usages})
            total_page_noun = "page" if total_page_count == 1 else "pages"
            self._usage_summary.setText(
                f"{widget_count} {widget_noun} on this page | {total_widget_count} total across {total_page_count} {total_page_noun} | {resource_name}"
            )
        else:
            self._usage_summary.setText(
                f"{widget_count} {widget_noun} across {page_count} {page_noun} | {resource_name}"
            )
        self._usage_table.setRowCount(len(usages))
        for row, entry in enumerate(usages):
            page_item = QTableWidgetItem(entry.page_name)
            page_item.setData(Qt.UserRole, entry.page_name)
            page_item.setData(Qt.UserRole + 1, entry.widget_name)
            widget_text = entry.widget_name
            if entry.widget_type:
                widget_text = f"{entry.widget_name} ({entry.widget_type})"
            widget_item = QTableWidgetItem(widget_text)
            prop_item = QTableWidgetItem(entry.property_name)
            item_tooltip = (
                f"Page: {entry.page_name}. Widget: {widget_text}. Property: {entry.property_name}."
            )
            _set_item_metadata(page_item, item_tooltip)
            _set_item_metadata(widget_item, item_tooltip)
            _set_item_metadata(prop_item, item_tooltip)
            self._usage_table.setItem(row, 0, page_item)
            self._usage_table.setItem(row, 1, widget_item)
            self._usage_table.setItem(row, 2, prop_item)
        if self._usage_table.rowCount() > 0:
            self._usage_table.selectRow(0)
        self._update_usage_accessibility_metadata()

    def _on_usage_item_activated(self, item):
        if item is None:
            return
        page_item = self._usage_table.item(item.row(), 0)
        if page_item is None:
            return
        page_name = page_item.data(Qt.UserRole) or ""
        widget_name = page_item.data(Qt.UserRole + 1) or ""
        if page_name and widget_name:
            self.usage_activated.emit(page_name, widget_name)

    def _target_dir_for_resource_type(self, resource_type):
        return self._images_dir if resource_type == "image" else self._src_dir

    def _list_widget_for_resource_type(self, resource_type):
        if resource_type == "image":
            return self._image_list
        if resource_type == "font":
            return self._font_list
        if resource_type == "text":
            return self._text_list
        return None

    def _missing_resource_names(self, resource_type):
        target_dir = self._target_dir_for_resource_type(resource_type)
        if resource_type == "image":
            names = self._catalog.images
        elif resource_type == "font":
            names = self._catalog.fonts
        elif resource_type == "text":
            names = self._catalog.text_files
        else:
            return []
        return [name for name in names if not os.path.isfile(os.path.join(target_dir, name))]

    def _visible_missing_resource_names(self, resource_type):
        missing_names = set(self._missing_resource_names(resource_type))
        return [name for name in self._filtered_resource_names(resource_type) if name in missing_names]

    def _visible_names_for_type(self, resource_type):
        if resource_type == "string":
            return self._filtered_string_keys()
        return self._filtered_resource_names(resource_type)

    def _is_resource_visible_under_filters(self, resource_type, filename):
        if not resource_type or not filename:
            return False
        if resource_type == "string":
            return filename in self._filtered_string_keys()
        return filename in self._filtered_resource_names(resource_type)

    def _ensure_resource_visible(self, resource_type, filename):
        if not resource_type or not filename:
            return
        if not self._is_resource_visible_under_filters(resource_type, filename):
            self._reset_resource_filter(resource_type)
        self._select_resource_item(resource_type, filename)

    def _select_resource_item(self, resource_type, filename, emit_signal=False):
        if resource_type == "image":
            self._tabs.setCurrentIndex(0)
        elif resource_type == "font":
            self._tabs.setCurrentIndex(1)
        elif resource_type == "text":
            self._tabs.setCurrentIndex(2)
        elif resource_type == "string":
            self._tabs.setCurrentIndex(3)
            matches = self._string_table.findItems(filename, Qt.MatchExactly)
            key_match = next((item for item in matches if item.column() == 0), None)
            if key_match is not None:
                self._string_table.setCurrentItem(key_match)
                self._update_current_resource(resource_type, filename)
                if emit_signal:
                    self.resource_selected.emit(resource_type, filename)
            else:
                self._string_table.clearSelection()
                self._string_table.setCurrentCell(-1, -1)
                self._update_current_resource(resource_type, filename)
            return
        lst = self._list_widget_for_resource_type(resource_type)
        if lst is None:
            return
        matches = lst.findItems(filename, Qt.MatchExactly)
        if matches:
            lst.setCurrentItem(matches[0])
            self._apply_resource_item_selection(resource_type, matches[0], emit_signal=emit_signal)
        else:
            lst.clearSelection()
            self._preview.clear_preview()
            self._update_current_resource(resource_type, filename)

    def _focus_missing_resource(self, resource_type):
        lst = self._list_widget_for_resource_type(resource_type)
        if lst is None:
            return ""

        missing_names = self._visible_missing_resource_names(resource_type)
        if not missing_names:
            self.feedback_message.emit(f"No missing {resource_type} resources were found.")
            return ""

        current_item = lst.currentItem()
        current_name = current_item.data(Qt.UserRole + 1) if current_item is not None else ""
        if current_name in missing_names:
            target_index = (missing_names.index(current_name) + 1) % len(missing_names)
        else:
            target_index = 0

        target_name = missing_names[target_index]
        matches = lst.findItems(target_name, Qt.MatchExactly)
        if matches:
            lst.setCurrentItem(matches[0])
            lst.scrollToItem(matches[0])
            self._apply_resource_item_selection(resource_type, matches[0], emit_signal=False)
        self.feedback_message.emit(
            f"Focused missing {resource_type} resource {target_index + 1}/{len(missing_names)}: {target_name}."
        )
        return target_name

    def _emit_operation_summary(self, action, resource_type, restored=None, renamed=None, unmatched=None, failures=None, remaining_missing=0):
        parts = []
        if renamed:
            parts.append(f"{len(renamed)} renamed")
        if restored:
            parts.append(f"{len(restored)} restored")
        if unmatched:
            parts.append(f"{len(unmatched)} unmatched")
        if failures:
            parts.append(f"{len(failures)} failed")
        if remaining_missing:
            parts.append(f"{remaining_missing} remaining missing")
        if not parts:
            return
        self.feedback_message.emit(f"{action} {resource_type} resources: {', '.join(parts)}.")

    def _copy_visible_names(self, resource_type):
        names = self._visible_names_for_type(resource_type)
        if not names:
            return
        QApplication.clipboard().setText("\n".join(names))
        self.feedback_message.emit(
            f"Copied {len(names)} visible {resource_type} resource name{'s' if len(names) != 1 else ''}."
        )

    def _copy_visible_string_keys(self):
        keys = self._visible_names_for_type("string")
        if not keys:
            return
        QApplication.clipboard().setText("\n".join(keys))
        self.feedback_message.emit(
            f"Copied {len(keys)} visible string key{'s' if len(keys) != 1 else ''}."
        )

    def _confirm_reference_impact(self, title, resource_name, usages, unused_prompt, impact_text, confirm_text):
        if not usages:
            if not unused_prompt:
                return True
            reply = QMessageBox.question(
                self,
                title,
                unused_prompt,
                QMessageBox.Yes | QMessageBox.No,
            )
            return reply == QMessageBox.Yes

        page_count = len({entry.page_name for entry in usages})
        widget_count = len(usages)
        page_noun = "page" if page_count == 1 else "pages"
        widget_noun = "widget" if widget_count == 1 else "widgets"
        summary = (
            f"'{resource_name}' is used by {widget_count} {widget_noun} across {page_count} {page_noun}.\n"
            f"{impact_text}"
        )
        dialog = _ReferenceImpactDialog(self, title, summary, usages, confirm_text)
        result = dialog.exec_()
        if result == _ReferenceImpactDialog.NAVIGATE_RESULT:
            page_name, widget_name = dialog.selected_usage()
            if page_name and widget_name:
                self.usage_activated.emit(page_name, widget_name)
            return False
        return result == QDialog.Accepted

    def _collect_batch_replace_impacts(self, resource_type, replacements):
        impacts = []
        total_rename_count = 0
        for old_name, source_path in replacements.items():
            new_name = os.path.basename(source_path or "")
            if not new_name or new_name == old_name:
                continue

            total_rename_count += 1
            usages = list(self._resource_usage_index.get((resource_type, old_name), []))
            if not usages:
                continue

            impacts.append(
                {
                    "old_name": old_name,
                    "new_name": new_name,
                    "usages": usages,
                    "widget_count": len(usages),
                    "page_count": len({entry.page_name for entry in usages}),
                }
            )

        impacts.sort(key=lambda entry: (entry["old_name"].lower(), entry["new_name"].lower()))
        return impacts, total_rename_count

    def _confirm_batch_replace_impact(self, resource_type, impacts, total_rename_count):
        if not impacts:
            return True

        dialog = _BatchReplaceImpactDialog(
            self,
            "Replace Missing Resources",
            resource_type,
            impacts,
            total_rename_count,
            "Replace",
            current_page_name=self._usage_page_name,
        )
        result = dialog.exec_()
        if result == _BatchReplaceImpactDialog.NAVIGATE_RESULT:
            page_name, widget_name = dialog.selected_usage()
            if page_name and widget_name:
                self.usage_activated.emit(page_name, widget_name)
            return False
        return result == QDialog.Accepted

    def _dialog_filter_for_resource_type(self, resource_type):
        if resource_type == "image":
            return "Images (*.png *.bmp *.jpg *.jpeg)"
        if resource_type == "font":
            return "Fonts (*.ttf *.otf)"
        if resource_type == "text":
            return "Text Files (*.txt);;All Files (*.*)"
        return "All Files (*.*)"

    def _allowed_extensions_for_resource_type(self, resource_type):
        if resource_type == "image":
            return IMAGE_EXTENSIONS
        if resource_type == "font":
            return FONT_EXTENSIONS
        if resource_type == "text":
            return TEXT_EXTENSIONS
        return set()

    def _validate_unique_source_filenames(self, source_paths):
        seen = {}
        duplicates = []
        for source_path in source_paths:
            filename = os.path.basename(source_path).lower()
            if filename in seen:
                duplicates.append(os.path.basename(source_path))
            else:
                seen[filename] = source_path
        if duplicates:
            dup_list = ", ".join(sorted(set(duplicates)))
            QMessageBox.warning(
                self,
                "Duplicate Replacement Filenames",
                f"Selected replacement files must have unique filenames.\nDuplicates: {dup_list}",
            )
            return False
        return True

    def _validate_replacement_filenames(self, replacements):
        for source_path in replacements.values():
            reserved_error = _reserved_resource_path_error(source_path, root_dir=self._src_dir)
            if reserved_error:
                QMessageBox.warning(self, "Reserved Filename", reserved_error)
                return False
        return True

    def _replace_missing_resource_with_path(self, old_name, resource_type, source_path):
        reserved_error = _reserved_resource_path_error(source_path, root_dir=self._src_dir)
        if reserved_error:
            return "", reserved_error
        new_name = os.path.basename(source_path)
        if not _validate_english_filename(new_name):
            return "", f"'{new_name}' is invalid. Use only ASCII letters, digits, underscore, and dash."
        reserved_error = _reserved_resource_filename_error(new_name)
        if reserved_error:
            return "", reserved_error

        extension = os.path.splitext(new_name)[1].lower()
        if extension not in self._allowed_extensions_for_resource_type(resource_type):
            return "", f"'{new_name}' is not a supported {resource_type} resource."

        target_dir = self._target_dir_for_resource_type(resource_type)
        old_path = os.path.join(target_dir, old_name)
        target_path = os.path.join(target_dir, new_name)
        if new_name != old_name and os.path.exists(target_path):
            return "", f"'{new_name}' already exists."

        try:
            shutil.copy2(source_path, old_path if new_name == old_name else target_path)
        except OSError as exc:
            return "", str(exc)

        if new_name != old_name:
            self._catalog.remove_file(old_name)
        self._catalog.add_file(new_name)
        return new_name, ""

    def _replace_missing_resources_from_mapping(self, resource_type, replacements):
        if not self._ensure_src_dir():
            return [], [], [("__all__", "No resource directory configured.")]

        restored = []
        renamed = []
        failures = []
        first_selected_name = ""

        for old_name, source_path in replacements.items():
            new_name, error = self._replace_missing_resource_with_path(old_name, resource_type, source_path)
            if error:
                failures.append((old_name, error))
                continue

            if not first_selected_name:
                first_selected_name = new_name
            if new_name == old_name:
                restored.append(old_name)
            else:
                renamed.append((old_name, new_name))

        if restored or renamed:
            self.set_resource_dir(self._resource_dir)
            if first_selected_name:
                self._ensure_resource_visible(resource_type, first_selected_name)
            self.resource_imported.emit()
            for old_name, new_name in renamed:
                self.resource_renamed.emit(resource_type, old_name, new_name)
            remaining_missing = len(self._missing_resource_names(resource_type))
            self._emit_operation_summary(
                "Replaced",
                resource_type,
                restored=restored,
                renamed=renamed,
                failures=failures,
                remaining_missing=remaining_missing,
            )

        return restored, renamed, failures

    def _load_font(self, path):
        if path in self._font_id_cache:
            return self._font_family_cache.get(path, "")
        fid = QFontDatabase.addApplicationFont(path)
        self._font_id_cache[path] = fid
        if fid >= 0:
            families = QFontDatabase.applicationFontFamilies(fid)
            family = families[0] if families else ""
        else:
            family = ""
        self._font_family_cache[path] = family
        return family

    def _ensure_src_dir(self):
        if not self._resource_dir:
            QMessageBox.warning(self, "Error",
                                "No resource directory configured.\n"
                                "Please save the project first or open an existing project.")
            return False
        self._src_dir = self._resource_dir
        self._images_dir = resource_images_dir(self._resource_dir)
        os.makedirs(self._src_dir, exist_ok=True)
        os.makedirs(self._images_dir, exist_ok=True)
        return True

    def _default_external_import_dir(self, resource_type=""):
        candidate = self._last_external_import_dir
        if candidate and os.path.isdir(candidate):
            return candidate

        if resource_type == "image":
            preferred_dir = preferred_resource_source_dir(self._src_dir)
            if preferred_dir:
                return preferred_dir

        if self._src_dir and os.path.isdir(self._src_dir):
            return self._src_dir

        return os.path.normpath(os.getcwd())

    def _remember_external_import_paths(self, paths):
        if not paths:
            return
        first_path = paths[0]
        parent_dir = os.path.dirname(first_path)
        if parent_dir and os.path.isdir(parent_dir):
            self._last_external_import_dir = parent_dir

    # -- Selection / double-click --

    def _on_image_clicked(self, item):
        self._apply_resource_item_selection("image", item, emit_signal=True)

    def _on_font_clicked(self, item):
        self._apply_resource_item_selection("font", item, emit_signal=True)

    def _on_text_clicked(self, item):
        self._apply_resource_item_selection("text", item, emit_signal=True)

    def _on_image_double_clicked(self, item):
        filename = item.data(Qt.UserRole + 1)
        self._update_current_resource("image", filename)
        self.resource_selected.emit("image", filename)

    def _on_font_double_clicked(self, item):
        filename = item.data(Qt.UserRole + 1)
        self._update_current_resource("font", filename)
        self.resource_selected.emit("font", filename)

    def _on_text_double_clicked(self, item):
        filename = item.data(Qt.UserRole + 1)
        self._update_current_resource("text", filename)
        self.resource_selected.emit("text", filename)

    # -- Import (buttons) --

    def _on_import_image(self):
        if not self._ensure_src_dir():
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Import Images", self._default_external_import_dir("image"),
            self._dialog_filter_for_resource_type("image")
        )
        if paths:
            self._remember_external_import_paths(paths)
            self._do_import(paths, "image")

    def _on_import_font(self):
        if not self._ensure_src_dir():
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Import Fonts", self._default_external_import_dir("font"),
            self._dialog_filter_for_resource_type("font")
        )
        if paths:
            self._remember_external_import_paths(paths)
            self._do_import(paths, "font")

    def _on_import_text(self):
        if not self._ensure_src_dir():
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Import Text Files", self._default_external_import_dir("text"),
            self._dialog_filter_for_resource_type("text")
        )
        if paths:
            self._remember_external_import_paths(paths)
            self._do_import(paths, "text")

    def _on_generate_charset(self):
        if not self._ensure_src_dir():
            return

        active_type, active_name = self._selected_resource_for_active_tab()
        initial_filename = _suggest_charset_filename_for_resource(active_type, active_name)
        source_label = active_name if active_type in {"font", "text"} else ""
        initial_preset_ids = _suggest_charset_presets_for_resource(active_type, active_name)
        self.open_generate_charset_dialog_for_resource(
            active_type,
            active_name,
            initial_filename=initial_filename,
            initial_preset_ids=initial_preset_ids,
        )

    def open_generate_charset_dialog_for_resource(self, resource_type="", source_name="", initial_filename="", initial_preset_ids=()):
        if not self._ensure_src_dir():
            return
        normalized_initial = str(initial_filename or "").strip()
        source_name = str(source_name or "").strip()
        existing_text = ""
        if not normalized_initial:
            normalized_initial = _suggest_charset_filename_for_resource(resource_type, source_name)
        if normalized_initial:
            existing_text_path = os.path.join(self._src_dir, normalized_initial)
            if os.path.isfile(existing_text_path):
                try:
                    with open(existing_text_path, "r", encoding="utf-8", errors="replace") as handle:
                        existing_text = handle.read()
                except OSError:
                    existing_text = ""
        if not initial_preset_ids:
            initial_preset_ids = _suggest_charset_presets_for_resource("text", normalized_initial)
            if not initial_preset_ids and existing_text:
                initial_preset_ids = infer_charset_presets_from_text(existing_text)
            if not initial_preset_ids:
                initial_preset_ids = _suggest_charset_presets_for_resource(resource_type, source_name)
        initial_custom_text = ""
        if existing_text:
            if initial_preset_ids:
                initial_custom_text = serialize_charset_chars(
                    charset_custom_chars_after_presets(existing_text, initial_preset_ids)
                ).rstrip()
            else:
                initial_custom_text = existing_text.rstrip()
        self._open_generate_charset_dialog(
            initial_filename=normalized_initial,
            source_label=source_name if resource_type in {"font", "text"} else "",
            initial_preset_ids=initial_preset_ids,
            initial_custom_text=initial_custom_text,
        )

    def _open_generate_charset_dialog(self, initial_filename="", source_label="", initial_preset_ids=(), initial_custom_text=""):
        dialog = _GenerateCharsetDialog(
            self._src_dir,
            initial_filename=initial_filename,
            source_label=source_label,
            initial_preset_ids=initial_preset_ids,
            initial_custom_text=initial_custom_text,
            parent=self,
        )
        if dialog.exec_() != QDialog.Accepted:
            return

        filename = dialog.filename()
        reserved_error = _reserved_resource_filename_error(filename)
        if reserved_error:
            QMessageBox.warning(self, "Reserved Filename", reserved_error)
            return
        target_path = os.path.join(self._src_dir, filename)
        chars = dialog.generated_chars()
        diff = dialog.overwrite_diff()
        existed_before = bool(target_path and os.path.isfile(target_path))

        if os.path.isfile(target_path):
            confirm_text = (
                f"Overwrite '{filename}'?\n\n"
                f"Existing chars: {diff.existing_count}\n"
                f"New chars: {diff.new_count}\n"
                f"Added: {diff.added_count}\n"
                f"Removed: {diff.removed_count}"
            )
            reply = QMessageBox.question(
                self,
                "Overwrite Charset Resource",
                confirm_text,
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        with open(target_path, "w", encoding="utf-8") as handle:
            handle.write(dialog.generated_text())

        self._catalog.add_file(filename)
        self.set_resource_dir(self._resource_dir)
        self._ensure_resource_visible("text", filename)
        self.resource_imported.emit()

        if dialog.save_and_assign():
            self.resource_selected.emit("text", filename)

        action = "Updated" if existed_before else "Created"
        if dialog.save_and_assign():
            action += " and assigned"
        message = f"{action} text resource '{filename}' with {len(chars)} chars."
        source_label = str(getattr(dialog, "_source_label", "") or "").strip()
        if source_label:
            message += f" Source: {source_label}."
        self.feedback_message.emit(message)

    def _restore_missing_resources_from_paths(self, resource_type, source_paths, target_names=None):
        target_dir = self._target_dir_for_resource_type(resource_type)
        if target_names is None:
            target_names = self._missing_resource_names(resource_type)
        missing_map = {name.lower(): name for name in target_names}
        restored = []
        unmatched = []
        failures = []

        for source_path in source_paths:
            source_name = os.path.basename(source_path)
            target_name = missing_map.get(source_name.lower())
            if not target_name:
                unmatched.append(source_name)
                continue
            reserved_error = _reserved_resource_path_error(source_path, root_dir=self._src_dir)
            if reserved_error:
                failures.append((target_name, reserved_error))
                continue

            target_path = os.path.join(target_dir, target_name)
            try:
                shutil.copy2(source_path, target_path)
            except OSError as exc:
                failures.append((target_name, str(exc)))
                continue

            self._catalog.add_file(target_name)
            restored.append(target_name)
            missing_map.pop(source_name.lower(), None)

        if restored:
            self.set_resource_dir(self._resource_dir)
            self._ensure_resource_visible(resource_type, restored[0])
            self.resource_imported.emit()
            remaining_missing = len(self._missing_resource_names(resource_type))
            self._emit_operation_summary(
                "Restored",
                resource_type,
                restored=restored,
                unmatched=unmatched,
                failures=failures,
                remaining_missing=remaining_missing,
            )

        return restored, unmatched, failures

    def _restore_missing_resources(self, resource_type):
        if not self._ensure_src_dir():
            return

        missing_names = self._visible_missing_resource_names(resource_type)
        if not missing_names:
            message = f"No missing {resource_type} resources were found."
            if self._has_active_resource_filter(resource_type):
                message = f"No missing {resource_type} resources match the current filters."
            QMessageBox.information(
                self,
                "Restore Missing Resources",
                message,
            )
            return

        source_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Restore Missing Resources",
            self._default_external_import_dir(resource_type),
            self._dialog_filter_for_resource_type(resource_type),
        )
        if not source_paths:
            return

        self._remember_external_import_paths(source_paths)
        restored, unmatched, failures = self._restore_missing_resources_from_paths(resource_type, source_paths, target_names=missing_names)
        if restored:
            return

        message = f"No matching missing {resource_type} resources were found in the selected files."
        if self._has_active_resource_filter(resource_type):
            message = f"{message}\n\nCurrent filters limited the target missing resources to: {', '.join(missing_names)}"
        if failures:
            details = "\n".join(f"{name}: {error}" for name, error in failures)
            message = f"{message}\n\nFailed copies:\n{details}"
        elif unmatched:
            message = f"{message}\n\nSelected files: {', '.join(unmatched)}"
        QMessageBox.warning(self, "Restore Missing Resources", message)

    def _restore_missing_resource(self, filename, resource_type):
        if not self._ensure_src_dir():
            return

        target_dir = self._target_dir_for_resource_type(resource_type)
        target_path = os.path.join(target_dir, filename)
        if os.path.isfile(target_path):
            return

        source_path, _ = QFileDialog.getOpenFileName(
            self,
            "Restore Missing Resource",
            self._default_external_import_dir(resource_type),
            self._dialog_filter_for_resource_type(resource_type),
        )
        if not source_path:
            return
        self._remember_external_import_paths([source_path])

        expected_ext = os.path.splitext(filename)[1].lower()
        source_ext = os.path.splitext(source_path)[1].lower()
        if expected_ext and source_ext != expected_ext:
            QMessageBox.warning(
                self,
                "Extension Mismatch",
                f"Expected a '{expected_ext}' file to restore '{filename}'.",
            )
            return
        reserved_error = _reserved_resource_path_error(source_path, root_dir=self._src_dir)
        if reserved_error:
            QMessageBox.warning(self, "Reserved Filename", reserved_error)
            return

        try:
            shutil.copy2(source_path, target_path)
        except OSError as exc:
            QMessageBox.warning(self, "Error", f"Restore failed: {exc}")
            return

        self._catalog.add_file(filename)
        self.set_resource_dir(self._resource_dir)
        self._ensure_resource_visible(resource_type, filename)

        self.resource_imported.emit()

    def _replace_missing_resources(self, resource_type):
        if not self._ensure_src_dir():
            return

        missing_names = self._visible_missing_resource_names(resource_type)
        if not missing_names:
            message = f"No missing {resource_type} resources were found."
            if self._has_active_resource_filter(resource_type):
                message = f"No missing {resource_type} resources match the current filters."
            QMessageBox.information(
                self,
                "Replace Missing Resources",
                message,
            )
            return

        source_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Replace Missing Resources",
            self._default_external_import_dir(resource_type),
            self._dialog_filter_for_resource_type(resource_type),
        )
        if not source_paths:
            return
        self._remember_external_import_paths(source_paths)

        if not self._validate_unique_source_filenames(source_paths):
            return

        dialog = _MissingResourceReplaceDialog(missing_names, source_paths, self)
        if dialog.exec_() != QDialog.Accepted:
            return

        replacements = dialog.selected_mapping()
        if not self._validate_replacement_filenames(replacements):
            return
        impacts, total_rename_count = self._collect_batch_replace_impacts(resource_type, replacements)
        if impacts and not self._confirm_batch_replace_impact(resource_type, impacts, total_rename_count):
            return

        restored, renamed, failures = self._replace_missing_resources_from_mapping(resource_type, replacements)
        if restored or renamed:
            if failures:
                details = "\n".join(f"{name}: {error}" for name, error in failures)
                QMessageBox.warning(
                    self,
                    "Replace Missing Resources",
                    f"Some replacements could not be applied:\n{details}",
                )
            return

        if failures:
            details = "\n".join(f"{name}: {error}" for name, error in failures)
            QMessageBox.warning(self, "Replace Missing Resources", details)

    def _replace_missing_resource(self, filename, resource_type):
        if not self._ensure_src_dir():
            return

        source_path, _ = QFileDialog.getOpenFileName(
            self,
            "Replace Missing Resource",
            self._default_external_import_dir(resource_type),
            self._dialog_filter_for_resource_type(resource_type),
        )
        if not source_path:
            return
        self._remember_external_import_paths([source_path])

        replacements = {filename: source_path}
        if not self._validate_replacement_filenames(replacements):
            return
        impacts, total_rename_count = self._collect_batch_replace_impacts(resource_type, replacements)
        if impacts and not self._confirm_batch_replace_impact(resource_type, impacts, total_rename_count):
            return

        restored, renamed, failures = self._replace_missing_resources_from_mapping(
            resource_type,
            replacements,
        )
        if restored or renamed:
            return

        if failures:
            QMessageBox.warning(self, "Replace Missing Resource", failures[0][1])

    def _do_import(self, source_paths, resource_type):
        if not self._ensure_src_dir():
            return
        self._remember_external_import_paths(source_paths)
        imported = 0
        first_imported_name = ""
        target_dir = self._target_dir_for_resource_type(resource_type)
        for src in source_paths:
            reserved_error = _reserved_resource_path_error(src, root_dir=self._src_dir)
            if reserved_error:
                QMessageBox.warning(self, "Reserved Filename", reserved_error)
                continue
            fname = os.path.basename(src)
            # Show rename dialog for each file
            new_name, ok = QInputDialog.getText(
                self, "Rename Resource",
                f"Import '{fname}' as:",
                text=fname,
            )
            if not ok or not new_name:
                continue
            fname = new_name
            if not _validate_english_filename(fname):
                QMessageBox.warning(
                    self, "Invalid Filename",
                    f"'{fname}' is invalid.\n"
                    "Use only ASCII letters, digits, underscore, and dash."
                )
                continue
            reserved_error = _reserved_resource_filename_error(fname)
            if reserved_error:
                QMessageBox.warning(self, "Reserved Filename", reserved_error)
                continue
            dst = os.path.join(target_dir, fname)
            if os.path.exists(dst):
                QMessageBox.warning(self, "Error", f"'{fname}' already exists.")
                continue
            shutil.copy2(src, dst)
            # Add to catalog
            self._catalog.add_file(fname)
            if not first_imported_name:
                first_imported_name = fname
            imported += 1
        if imported > 0:
            self.set_resource_dir(self._resource_dir)
            if first_imported_name:
                self._ensure_resource_visible(resource_type, first_imported_name)
            self.resource_imported.emit()

    # -- Drag-drop import from OS --

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                lower = path.lower()
                if lower.endswith(_IMAGE_EXTS + _FONT_EXTS + _TEXT_EXTS):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        if not event.mimeData().hasUrls():
            event.ignore()
            return
        images = []
        fonts = []
        texts = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if not path or not os.path.isfile(path):
                continue
            lower = path.lower()
            if lower.endswith(_IMAGE_EXTS):
                images.append(path)
            elif lower.endswith(_FONT_EXTS):
                fonts.append(path)
            elif lower.endswith(_TEXT_EXTS):
                texts.append(path)

        did_import = False
        if images:
            self._do_import(images, "image")
            did_import = True
        if fonts:
            self._do_import(fonts, "font")
            did_import = True
        if texts:
            self._do_import(texts, "text")
            did_import = True

        if did_import:
            event.acceptProposedAction()
        else:
            event.ignore()

    # -- Right-click context menu --

    def _show_context_menu(self, pos, resource_type):
        lst = self._list_widget_for_resource_type(resource_type)
        if lst is None:
            return

        item = lst.itemAt(pos)
        if item is None:
            return

        filename = item.data(Qt.UserRole + 1)
        path = item.data(Qt.UserRole) or ""

        menu = QMenu(self)

        assign_act = menu.addAction("Assign")
        assign_act.triggered.connect(lambda: self.resource_selected.emit(resource_type, filename))

        copy_act = menu.addAction("Copy Name")
        copy_act.triggered.connect(lambda: QApplication.clipboard().setText(filename))

        if resource_type in {"font", "text"}:
            menu.addSeparator()
            generate_charset_act = menu.addAction("Generate Charset...")
            generate_charset_act.triggered.connect(
                lambda: self._open_generate_charset_dialog(
                    initial_filename=_suggest_charset_filename_for_resource(resource_type, filename),
                    source_label=filename,
                    initial_preset_ids=_suggest_charset_presets_for_resource(resource_type, filename),
                )
            )

        menu.addSeparator()

        if not os.path.isfile(path):
            restore_act = menu.addAction("Restore...")
            restore_act.triggered.connect(lambda: self._restore_missing_resource(filename, resource_type))
            replace_act = menu.addAction("Replace...")
            replace_act.triggered.connect(lambda: self._replace_missing_resource(filename, resource_type))
            menu.addSeparator()

        reveal_act = menu.addAction("Reveal")
        reveal_act.triggered.connect(lambda: self._reveal_in_explorer(path))

        menu.addSeparator()

        rename_act = menu.addAction("Rename...")
        rename_act.triggered.connect(lambda: self._rename_resource(filename, resource_type))

        delete_act = menu.addAction("Delete")
        delete_act.triggered.connect(lambda: self._delete_resource(filename, resource_type))

        menu.exec_(lst.viewport().mapToGlobal(pos))

    def _reveal_in_explorer(self, path):
        import subprocess
        import sys as _sys
        if _sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
        elif _sys.platform == "darwin":
            subprocess.Popen(["open", "-R", path])
        else:
            folder = os.path.dirname(path)
            subprocess.Popen(["xdg-open", folder])

    def _rename_resource(self, old_name, resource_type):
        new_name, ok = QInputDialog.getText(
            self, "Rename Resource", "New filename:", text=old_name
        )
        if not ok or not new_name or new_name == old_name:
            return
        if not _validate_english_filename(new_name):
            QMessageBox.warning(
                self, "Invalid Filename",
                f"'{new_name}' is invalid.\n"
                "Use only ASCII letters, digits, underscore, and dash."
            )
            return
        reserved_error = _reserved_resource_filename_error(new_name)
        if reserved_error:
            QMessageBox.warning(self, "Reserved Filename", reserved_error)
            return
        file_dir = self._target_dir_for_resource_type(resource_type)
        old_path = os.path.join(file_dir, old_name)
        new_path = os.path.join(file_dir, new_name)
        if os.path.exists(new_path):
            QMessageBox.warning(self, "Error", f"'{new_name}' already exists.")
            return
        usages = list(self._resource_usage_index.get((resource_type, old_name), []))
        confirmed = self._confirm_reference_impact(
            "Rename Resource",
            old_name,
            usages,
            "",
            f"Renaming it to '{new_name}' will update those widget references.",
            "Rename",
        )
        if not confirmed:
            return
        try:
            if os.path.exists(old_path):
                os.rename(old_path, new_path)
            # Update catalog
            self._catalog.remove_file(old_name)
            self._catalog.add_file(new_name)
            self.set_resource_dir(self._resource_dir)
            self._ensure_resource_visible(resource_type, new_name)
            self.resource_renamed.emit(resource_type, old_name, new_name)
            self.resource_imported.emit()
        except OSError as e:
            QMessageBox.warning(self, "Error", f"Rename failed: {e}")

    def _delete_resource(self, filename, resource_type):
        usages = list(self._resource_usage_index.get((resource_type, filename), []))
        confirmed = self._confirm_reference_impact(
            "Delete Resource",
            filename,
            usages,
            f"Remove '{filename}' from catalog and delete the file?\nThis cannot be undone.",
            "Deleting it will clear those widget references.",
            "Delete",
        )
        if not confirmed:
            return
        self._catalog.remove_file(filename)
        file_dir = self._target_dir_for_resource_type(resource_type)
        file_path = os.path.join(file_dir, filename)
        if os.path.isfile(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass
        self.set_resource_dir(self._resource_dir)
        self.resource_deleted.emit(resource_type, filename)
        self.resource_imported.emit()

    def _confirm_cleanup_unused(self, resource_type, names):
        dialog = _CleanupUnusedDialog(
            self,
            f"Clean Unused {self._active_panel_tab_label()}",
            self._active_panel_tab_label(),
            names,
            search_text=self._resource_search_text(resource_type),
            status_label=self._resource_status_filters.get(resource_type).currentText() if self._resource_status_filters.get(resource_type) is not None else "All",
        )
        return dialog.exec_() == QDialog.Accepted

    def _clean_unused_resources(self, resource_type):
        if not self._ensure_src_dir():
            return

        names = self._visible_unused_names(resource_type)
        if not names:
            QMessageBox.information(
                self,
                "Clean Unused Resources",
                f"No unused {resource_type} resources match the current filters.",
            )
            return

        if not self._confirm_cleanup_unused(resource_type, names):
            return

        target_dir = self._target_dir_for_resource_type(resource_type)
        removed = []
        failures = []
        for name in names:
            file_path = os.path.join(target_dir, name)
            if os.path.isfile(file_path):
                try:
                    os.remove(file_path)
                except OSError as exc:
                    failures.append((name, str(exc)))
                    continue
            self._catalog.remove_file(name)
            removed.append(name)

        if removed:
            self.set_resource_dir(self._resource_dir)
            for name in removed:
                self.resource_deleted.emit(resource_type, name)
            self.resource_imported.emit()
            message = f"Cleaned unused {resource_type} resources: {len(removed)} removed."
            if failures:
                message += f" {len(failures)} failed."
            self.feedback_message.emit(message)

        if failures:
            details = "\n".join(f"{name}: {error}" for name, error in failures)
            QMessageBox.warning(self, "Clean Unused Resources", details)

    def _clean_unused_string_keys(self):
        names = self._visible_unused_names("string")
        if not names:
            QMessageBox.information(
                self,
                "Clean Unused String Keys",
                "No unused string keys match the current filters.",
            )
            return

        if not self._confirm_cleanup_unused("string", names):
            return

        removed = []
        for key in names:
            replacement_text = self._string_catalog.get(key, DEFAULT_LOCALE)
            self._string_catalog.remove_key(key)
            removed.append((key, replacement_text))

        if not removed:
            return

        self._refresh_string_tab()
        for key, replacement_text in removed:
            self.string_key_deleted.emit(key, replacement_text)
        self.resource_imported.emit()
        self.feedback_message.emit(f"Cleaned unused string keys: {len(removed)} removed.")

    # -- Strings tab methods --

    def _refresh_string_tab(self):
        """Refresh locale combo and string table from the catalog."""
        self._string_table_updating = True
        try:
            # Refresh locale combo
            prev_locale = self._get_selected_locale()
            self._locale_combo.blockSignals(True)
            self._locale_combo.clear()
            names = self._string_catalog.locale_display_names
            for locale_code in self._string_catalog.locales:
                display = names.get(locale_code, locale_code or "Default")
                self._locale_combo.addItem(display, locale_code)
            # Restore selection
            idx = self._locale_combo.findData(prev_locale)
            if idx >= 0:
                self._locale_combo.setCurrentIndex(idx)
            self._locale_combo.blockSignals(False)

            self._refresh_string_table()
            self._update_tab_titles()
        finally:
            self._string_table_updating = False
        self._refresh_usage_view()
        self._update_string_action_metadata()

    def _get_selected_locale(self):
        """Get the locale code of the currently selected combo item."""
        idx = self._locale_combo.currentIndex()
        if idx < 0:
            return DEFAULT_LOCALE
        return self._locale_combo.itemData(idx) or DEFAULT_LOCALE

    def _refresh_string_table(self, selection_fallback="keep"):
        """Repopulate the table for the selected locale."""
        self._string_table_updating = True
        try:
            locale = self._get_selected_locale()
            keys = self._filtered_string_keys()
            prev_key = ""
            if selection_fallback != "clear":
                current_row = self._string_table.currentRow()
                current_key_item = self._string_table.item(current_row, 0) if current_row >= 0 else None
                if current_key_item is not None:
                    prev_key = current_key_item.text()
                elif self._current_resource_type == "string":
                    prev_key = self._current_resource_name

            self._string_table.setRowCount(len(keys))
            for row, key in enumerate(keys):
                # Key column (read-only)
                key_item = QTableWidgetItem(key)
                key_item.setFlags(key_item.flags() & ~Qt.ItemIsEditable)
                self._string_table.setItem(row, 0, key_item)

                # Value column (editable)
                value = self._string_catalog.get(key, locale)
                val_item = QTableWidgetItem(value)
                self._string_table.setItem(row, 1, val_item)

            if prev_key and prev_key in keys:
                target_row = keys.index(prev_key)
                self._string_table.setCurrentCell(target_row, 0)
                self._update_current_resource("string", prev_key)
            elif selection_fallback == "first" and keys:
                self._string_table.setCurrentCell(0, 0)
                self._update_current_resource("string", keys[0])
            else:
                self._string_table.clearSelection()
                self._string_table.setCurrentCell(-1, -1)
                self._update_current_resource("", "")
        finally:
            self._string_table_updating = False

    def _on_locale_changed(self, index):
        """Locale combo selection changed."""
        if not self._string_table_updating:
            self._refresh_string_table(selection_fallback="keep")
        self._update_string_action_metadata()

    def _on_string_current_cell_changed(self, current_row, current_column, previous_row, previous_column):
        del current_column, previous_row, previous_column
        if self._string_table_updating:
            return
        key_item = self._string_table.item(current_row, 0) if current_row >= 0 else None
        key = key_item.text() if key_item is not None else ""
        self._preview.clear_preview()
        self._update_current_resource("string" if key else "", key)
        self._update_string_action_metadata()

    def _on_string_cell_changed(self, row, col):
        """Handle user editing a string value in the table."""
        if self._string_table_updating:
            return
        if col != 1:
            return
        locale = self._get_selected_locale()
        key_item = self._string_table.item(row, 0)
        val_item = self._string_table.item(row, 1)
        if key_item and val_item:
            key = key_item.text()
            value = val_item.text()
            self._string_catalog.set(key, value, locale)
            self._refresh_string_table(selection_fallback="keep")
            self.resource_imported.emit()

    def _on_add_string_key(self):
        """Add a new string key to all locales."""
        key, ok = QInputDialog.getText(
            self, "Add String Key",
            "Enter string key name (e.g. app_name):"
        )
        if not ok or not key:
            return
        key = key.strip()

        # Ensure default locale exists
        if DEFAULT_LOCALE not in self._string_catalog.strings:
            self._string_catalog.add_locale(DEFAULT_LOCALE)
            self._refresh_string_tab()

        try:
            self._string_catalog.add_key(key, "")
        except ValueError as e:
            QMessageBox.warning(self, "Invalid Key", str(e))
            return

        self._refresh_string_tab()
        self._ensure_resource_visible("string", key)
        self.resource_imported.emit()

    def _on_rename_string_key(self):
        """Rename the selected string key across all locales."""
        row = self._string_table.currentRow()
        if row < 0:
            return
        key_item = self._string_table.item(row, 0)
        if key_item is None:
            return
        old_key = key_item.text().strip()
        if not old_key:
            return

        new_key, ok = QInputDialog.getText(
            self,
            "Rename String Key",
            "Enter new string key name:",
            text=old_key,
        )
        if not ok:
            return
        new_key = new_key.strip()
        if not new_key or new_key == old_key:
            return
        usages = list(self._resource_usage_index.get(("string", old_key), []))
        confirmed = self._confirm_reference_impact(
            "Rename String Key",
            old_key,
            usages,
            "",
            f"Renaming it to '{new_key}' will update those string references.",
            "Rename",
        )
        if not confirmed:
            return

        try:
            self._string_catalog.rename_key(old_key, new_key)
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Key", str(exc))
            return

        self._refresh_string_tab()
        self._ensure_resource_visible("string", new_key)
        self.string_key_renamed.emit(old_key, new_key)
        self.resource_imported.emit()

    def _on_remove_string_key(self):
        """Remove the selected string key from all locales."""
        row = self._string_table.currentRow()
        if row < 0:
            return
        key_item = self._string_table.item(row, 0)
        if not key_item:
            return
        key = key_item.text()
        usages = list(self._resource_usage_index.get(("string", key), []))
        replacement_text = self._string_catalog.get(key, DEFAULT_LOCALE)
        rewrite_text = "convert those references to the default-locale literal text" if replacement_text else "clear those references"
        confirmed = self._confirm_reference_impact(
            "Remove String Key",
            key,
            usages,
            f"Remove key '{key}' from all locales?",
            f"Removing it will {rewrite_text}.",
            "Remove",
        )
        if not confirmed:
            return
        self._string_catalog.remove_key(key)
        self._refresh_string_tab()
        self.string_key_deleted.emit(key, replacement_text)
        self.resource_imported.emit()

    def _on_add_locale(self):
        """Add a new locale (e.g. 'zh', 'ja', 'fr')."""
        locale, ok = QInputDialog.getText(
            self, "Add Locale",
            "Enter locale code (e.g. zh, ja, fr, de):"
        )
        if not ok or not locale:
            return
        locale = locale.strip().lower()
        if not locale:
            return

        # Ensure default locale exists first
        if DEFAULT_LOCALE not in self._string_catalog.strings:
            self._string_catalog.add_locale(DEFAULT_LOCALE)

        self._string_catalog.add_locale(locale)
        self._refresh_string_tab()

        # Select the new locale
        idx = self._locale_combo.findData(locale)
        if idx >= 0:
            self._locale_combo.setCurrentIndex(idx)

        self.resource_imported.emit()

    def _on_remove_locale(self):
        """Remove the currently selected locale."""
        locale = self._get_selected_locale()
        if locale == DEFAULT_LOCALE:
            QMessageBox.information(
                self, "Cannot Remove",
                "The default locale cannot be removed."
            )
            return
        reply = QMessageBox.question(
            self, "Remove Locale",
            f"Remove locale '{locale}' and all its translations?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        self._string_catalog.remove_locale(locale)
        self._refresh_string_tab()
        self.resource_imported.emit()
