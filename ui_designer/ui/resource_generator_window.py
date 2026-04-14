"""Standalone Resource Generator window."""

from __future__ import annotations

import copy
import filecmp
import json
import math
import os
import re
import shutil
import subprocess

from PyQt5.QtCore import QEvent, QTimer, Qt, QSignalBlocker, QUrl, pyqtSignal
from PyQt5.QtGui import QColor, QDesktopServices, QFont, QImage, QKeySequence, QPainter, QPalette, QPen, QPixmap
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QInputDialog,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QShortcut,
    QSplitter,
    QStackedWidget,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..model.resource_generation_session import (
    GenerationPaths,
    KNOWN_RESOURCE_SECTIONS,
    RESOURCE_SECTION_SPECS,
    ResourceGenerationSession,
    default_entry_for_section,
    infer_generation_paths,
    section_entry_label,
)
from ..model.config import get_config
from ..model.workspace import normalize_path
from ..utils.font_preview_renderer import render_font_preview_image
from ..utils.resource_config_overlay import APP_RESOURCE_CONFIG_FILENAME, make_empty_resource_config
from .resource_panel import (
    _GenerateCharsetDialog,
    _suggest_charset_filename_for_resource,
    _suggest_charset_presets_for_resource,
)
from .theme import app_theme_tokens, sync_window_chrome_theme


_IMAGE_FILE_EXTENSIONS = {".png", ".bmp", ".jpg", ".jpeg", ".gif", ".webp"}
_FONT_FILE_EXTENSIONS = {".ttf", ".otf"}
_VIDEO_FILE_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}
_TEXT_FILE_EXTENSIONS = {".txt"}
_QUICK_GENERATED_ASSET_FOLDERS = ("thumbnails", "normalized", "compressed", "font_previews")
_QUICK_GENERATED_ASSET_FOLDER_SET = {folder.lower() for folder in _QUICK_GENERATED_ASSET_FOLDERS}
_STANDARD_SOURCE_DIR_FOLDERS = {
    "img": "images",
    "font": "fonts",
    "mp4": "videos",
}
_RESOURCE_GENERATOR_VIEW_STATE_KEY = "resource_generator_view"
_DEFAULT_SIMPLE_WORKSPACE_SPLITTER_SIZES = [220, 320, 220]
_DEFAULT_SIMPLE_PREVIEW_SPLITTER_SIZES = [460, 460]
_DEFAULT_SIMPLE_ASSET_COLUMN_WIDTHS = [88, 220, 360, 280]
_FONT_TEXT_PREVIEW_CHAR_LIMIT = 4096
_FONT_TEXT_COMBINED_PREVIEW_CHAR_LIMIT = 8192


class _ClickableLabel(QLabel):
    clicked = pyqtSignal()

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.rect().contains(event.pos()):
            self.clicked.emit()
        super().mouseReleaseEvent(event)


def _pil_image_to_qpixmap(image) -> QPixmap:
    rgba = image.convert("RGBA")
    data = rgba.tobytes("raw", "RGBA")
    qimage = QImage(data, rgba.width, rgba.height, QImage.Format_RGBA8888)
    return QPixmap.fromImage(qimage.copy())


class _QuickImageResizeDialog(QDialog):
    def __init__(self, *, width: int, height: int, output_filename: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Resize Image")
        self.setMinimumWidth(360)
        self._aspect_ratio = (float(width) / float(height)) if width and height else 1.0
        self._syncing_size = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        summary = QLabel(f"Current size: {width} x {height}")
        layout.addWidget(summary)

        form = QFormLayout()
        form.setSpacing(8)

        self._width_spin = QSpinBox()
        self._width_spin.setRange(1, 8192)
        self._width_spin.setValue(max(int(width or 1), 1))
        self._width_spin.valueChanged.connect(self._on_width_changed)
        form.addRow("Width", self._width_spin)

        self._height_spin = QSpinBox()
        self._height_spin.setRange(1, 8192)
        self._height_spin.setValue(max(int(height or 1), 1))
        self._height_spin.valueChanged.connect(self._on_height_changed)
        form.addRow("Height", self._height_spin)

        self._keep_ratio_check = QCheckBox("Keep aspect ratio")
        self._keep_ratio_check.setChecked(True)
        form.addRow("", self._keep_ratio_check)

        self._filename_edit = QLineEdit(str(output_filename or "").strip())
        form.addRow("Output File", self._filename_edit)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_width_changed(self, value: int):
        if self._syncing_size or not self._keep_ratio_check.isChecked():
            return
        self._syncing_size = True
        try:
            height = max(1, int(round(float(value) / self._aspect_ratio))) if self._aspect_ratio else self._height_spin.value()
            self._height_spin.setValue(height)
        finally:
            self._syncing_size = False

    def _on_height_changed(self, value: int):
        if self._syncing_size or not self._keep_ratio_check.isChecked():
            return
        self._syncing_size = True
        try:
            width = max(1, int(round(float(value) * self._aspect_ratio))) if self._aspect_ratio else self._width_spin.value()
            self._width_spin.setValue(width)
        finally:
            self._syncing_size = False

    def width_value(self) -> int:
        return int(self._width_spin.value())

    def height_value(self) -> int:
        return int(self._height_spin.value())

    def output_filename(self) -> str:
        return str(self._filename_edit.text() or "").strip()


class _QuickImageRotateDialog(QDialog):
    def __init__(self, *, width: int, height: int, output_filename: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Rotate Image")
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        self._summary = QLabel("")
        layout.addWidget(self._summary)

        form = QFormLayout()
        form.setSpacing(8)

        self._rotation_combo = QComboBox()
        self._rotation_combo.addItem("90 Right", 90)
        self._rotation_combo.addItem("90 Left", 270)
        self._rotation_combo.addItem("180", 180)
        self._rotation_combo.currentIndexChanged.connect(lambda _index: self._update_summary(width, height))
        form.addRow("Rotation", self._rotation_combo)

        self._filename_edit = QLineEdit(str(output_filename or "").strip())
        form.addRow("Output File", self._filename_edit)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._update_summary(width, height)

    def _update_summary(self, width: int, height: int):
        rotation = self.rotation_degrees()
        target_width = height if rotation in {90, 270} else width
        target_height = width if rotation in {90, 270} else height
        self._summary.setText(f"Current size: {width} x {height}\nResult size: {target_width} x {target_height}")

    def rotation_degrees(self) -> int:
        return int(self._rotation_combo.currentData() or 90)

    def output_filename(self) -> str:
        return str(self._filename_edit.text() or "").strip()


class _QuickImageFlipDialog(QDialog):
    def __init__(self, *, output_filename: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Flip Image")
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        summary = QLabel("Choose how to mirror the current image.")
        summary.setWordWrap(True)
        layout.addWidget(summary)

        form = QFormLayout()
        form.setSpacing(8)

        self._mode_combo = QComboBox()
        self._mode_combo.addItem("Horizontal", "horizontal")
        self._mode_combo.addItem("Vertical", "vertical")
        form.addRow("Flip", self._mode_combo)

        self._filename_edit = QLineEdit(str(output_filename or "").strip())
        form.addRow("Output File", self._filename_edit)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def flip_mode(self) -> str:
        return str(self._mode_combo.currentData() or "horizontal")

    def output_filename(self) -> str:
        return str(self._filename_edit.text() or "").strip()


class _QuickImageCropDialog(QDialog):
    def __init__(self, *, width: int, height: int, output_filename: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Crop Image")
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        summary = QLabel(f"Current size: {width} x {height}")
        layout.addWidget(summary)

        form = QFormLayout()
        form.setSpacing(8)

        self._x_spin = QSpinBox()
        self._x_spin.setRange(0, max(int(width) - 1, 0))
        self._x_spin.setValue(0)
        form.addRow("Left", self._x_spin)

        self._y_spin = QSpinBox()
        self._y_spin.setRange(0, max(int(height) - 1, 0))
        self._y_spin.setValue(0)
        form.addRow("Top", self._y_spin)

        self._width_spin = QSpinBox()
        self._width_spin.setRange(1, max(int(width), 1))
        self._width_spin.setValue(max(int(width), 1))
        form.addRow("Width", self._width_spin)

        self._height_spin = QSpinBox()
        self._height_spin.setRange(1, max(int(height), 1))
        self._height_spin.setValue(max(int(height), 1))
        form.addRow("Height", self._height_spin)

        self._filename_edit = QLineEdit(str(output_filename or "").strip())
        form.addRow("Output File", self._filename_edit)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def x_value(self) -> int:
        return int(self._x_spin.value())

    def y_value(self) -> int:
        return int(self._y_spin.value())

    def width_value(self) -> int:
        return int(self._width_spin.value())

    def height_value(self) -> int:
        return int(self._height_spin.value())

    def output_filename(self) -> str:
        return str(self._filename_edit.text() or "").strip()


class _QuickImageBorderDialog(QDialog):
    def __init__(self, *, output_filename: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Border")
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        summary = QLabel("Extend the image with a simple solid-color border.")
        summary.setWordWrap(True)
        layout.addWidget(summary)

        form = QFormLayout()
        form.setSpacing(8)

        self._border_spin = QSpinBox()
        self._border_spin.setRange(1, 512)
        self._border_spin.setValue(8)
        form.addRow("Border Size", self._border_spin)

        self._color_edit = QLineEdit("#FFFFFF")
        self._color_edit.setPlaceholderText("#RRGGBB or #RRGGBBAA")
        form.addRow("Border Color", self._color_edit)

        self._filename_edit = QLineEdit(str(output_filename or "").strip())
        form.addRow("Output File", self._filename_edit)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def border_size(self) -> int:
        return int(self._border_spin.value())

    def color_value(self) -> str:
        return str(self._color_edit.text() or "").strip()

    def output_filename(self) -> str:
        return str(self._filename_edit.text() or "").strip()


class _QuickImageBackgroundDialog(QDialog):
    def __init__(self, *, output_filename: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Background")
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        summary = QLabel("Fill transparent areas with a solid background color while keeping the image size unchanged.")
        summary.setWordWrap(True)
        layout.addWidget(summary)

        form = QFormLayout()
        form.setSpacing(8)

        self._color_edit = QLineEdit("#FFFFFF")
        self._color_edit.setPlaceholderText("#RRGGBB or #RRGGBBAA")
        form.addRow("Background Color", self._color_edit)

        self._filename_edit = QLineEdit(str(output_filename or "").strip())
        form.addRow("Output File", self._filename_edit)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def color_value(self) -> str:
        return str(self._color_edit.text() or "").strip()

    def output_filename(self) -> str:
        return str(self._filename_edit.text() or "").strip()


class _QuickImageRoundCornersDialog(QDialog):
    def __init__(self, *, width: int, height: int, output_filename: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Round Corners")
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        summary = QLabel(f"Make the outer corners transparent while keeping the image size unchanged ({width} x {height}).")
        summary.setWordWrap(True)
        layout.addWidget(summary)

        form = QFormLayout()
        form.setSpacing(8)

        max_radius = max(1, int(math.ceil(min(max(int(width or 1), 1), max(int(height or 1), 1)) / 2.0)))
        self._radius_spin = QSpinBox()
        self._radius_spin.setRange(1, max_radius)
        self._radius_spin.setValue(min(max_radius, max(1, min(max(int(width or 1), 1), max(int(height or 1), 1)) // 4)))
        form.addRow("Corner Radius", self._radius_spin)

        self._filename_edit = QLineEdit(str(output_filename or "").strip())
        form.addRow("Output File", self._filename_edit)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def radius_value(self) -> int:
        return int(self._radius_spin.value())

    def output_filename(self) -> str:
        return str(self._filename_edit.text() or "").strip()


class _QuickImageOpacityDialog(QDialog):
    def __init__(self, *, output_filename: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Adjust Opacity")
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        summary = QLabel("Scale the image alpha to quickly make faded or disabled-looking variants.")
        summary.setWordWrap(True)
        layout.addWidget(summary)

        form = QFormLayout()
        form.setSpacing(8)

        self._opacity_spin = QSpinBox()
        self._opacity_spin.setRange(1, 100)
        self._opacity_spin.setSuffix("%")
        self._opacity_spin.setValue(50)
        form.addRow("Opacity", self._opacity_spin)

        self._filename_edit = QLineEdit(str(output_filename or "").strip())
        form.addRow("Output File", self._filename_edit)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def opacity_percent(self) -> int:
        return int(self._opacity_spin.value())

    def output_filename(self) -> str:
        return str(self._filename_edit.text() or "").strip()


class _QuickThumbnailBatchDialog(QDialog):
    def __init__(self, *, width: int, height: int, output_folder: str, suffix: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Generate Thumbnails")
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        summary = QLabel("Create resized thumbnail images for every image asset in quick mode.")
        summary.setWordWrap(True)
        layout.addWidget(summary)

        form = QFormLayout()
        form.setSpacing(8)

        self._width_spin = QSpinBox()
        self._width_spin.setRange(1, 4096)
        self._width_spin.setValue(max(int(width or 1), 1))
        form.addRow("Max Width", self._width_spin)

        self._height_spin = QSpinBox()
        self._height_spin.setRange(1, 4096)
        self._height_spin.setValue(max(int(height or 1), 1))
        form.addRow("Max Height", self._height_spin)

        self._folder_edit = QLineEdit(str(output_folder or "").strip())
        form.addRow("Output Folder", self._folder_edit)

        self._suffix_edit = QLineEdit(str(suffix or "").strip())
        form.addRow("Filename Suffix", self._suffix_edit)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def width_value(self) -> int:
        return int(self._width_spin.value())

    def height_value(self) -> int:
        return int(self._height_spin.value())

    def output_folder(self) -> str:
        return str(self._folder_edit.text() or "").strip()

    def filename_suffix(self) -> str:
        return str(self._suffix_edit.text() or "").strip()


class _QuickImageNormalizeDialog(QDialog):
    def __init__(self, *, output_folder: str, suffix: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Normalize Images")
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        summary = QLabel("Create normalized PNG copies for every image asset in quick mode.")
        summary.setWordWrap(True)
        layout.addWidget(summary)

        form = QFormLayout()
        form.setSpacing(8)

        self._folder_edit = QLineEdit(str(output_folder or "").strip())
        form.addRow("Output Folder", self._folder_edit)

        self._suffix_edit = QLineEdit(str(suffix or "").strip())
        form.addRow("Filename Suffix", self._suffix_edit)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def output_folder(self) -> str:
        return str(self._folder_edit.text() or "").strip()

    def filename_suffix(self) -> str:
        return str(self._suffix_edit.text() or "").strip()


class _QuickImageCompressDialog(QDialog):
    def __init__(self, *, output_folder: str, suffix: str, colors: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Compress Images")
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        summary = QLabel("Create compressed PNG copies for every image asset in quick mode.")
        summary.setWordWrap(True)
        layout.addWidget(summary)

        form = QFormLayout()
        form.setSpacing(8)

        self._folder_edit = QLineEdit(str(output_folder or "").strip())
        form.addRow("Output Folder", self._folder_edit)

        self._suffix_edit = QLineEdit(str(suffix or "").strip())
        form.addRow("Filename Suffix", self._suffix_edit)

        self._color_spin = QSpinBox()
        self._color_spin.setRange(2, 256)
        self._color_spin.setValue(max(min(int(colors or 64), 256), 2))
        form.addRow("Max Colors", self._color_spin)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def output_folder(self) -> str:
        return str(self._folder_edit.text() or "").strip()

    def filename_suffix(self) -> str:
        return str(self._suffix_edit.text() or "").strip()

    def color_limit(self) -> int:
        return int(self._color_spin.value())


class _QuickFontPrerenderDialog(QDialog):
    def __init__(self, *, output_folder: str, suffix: str, sample_text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pre-Render Fonts")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        summary = QLabel("Render each font asset into a PNG preview card so quick mode users can compare fonts visually.")
        summary.setWordWrap(True)
        layout.addWidget(summary)

        form = QFormLayout()
        form.setSpacing(8)

        self._folder_edit = QLineEdit(str(output_folder or "").strip())
        form.addRow("Output Folder", self._folder_edit)

        self._suffix_edit = QLineEdit(str(suffix or "").strip())
        form.addRow("Filename Suffix", self._suffix_edit)

        self._sample_edit = QLineEdit(str(sample_text or "").strip())
        self._sample_edit.setPlaceholderText("Leave empty to use the linked text file or built-in sample")
        form.addRow("Sample Text", self._sample_edit)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def output_folder(self) -> str:
        return str(self._folder_edit.text() or "").strip()

    def filename_suffix(self) -> str:
        return str(self._suffix_edit.text() or "").strip()

    def sample_text(self) -> str:
        return str(self._sample_edit.text() or "").strip()


class _QuickImagePlaceholderDialog(QDialog):
    def __init__(self, *, width: int, height: int, output_folder: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Generate Placeholders")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        summary = QLabel("Create simple PNG placeholders for image entries whose files are currently missing.")
        summary.setWordWrap(True)
        layout.addWidget(summary)

        form = QFormLayout()
        form.setSpacing(8)

        self._width_spin = QSpinBox()
        self._width_spin.setRange(16, 4096)
        self._width_spin.setValue(max(int(width or 1), 16))
        form.addRow("Width", self._width_spin)

        self._height_spin = QSpinBox()
        self._height_spin.setRange(16, 4096)
        self._height_spin.setValue(max(int(height or 1), 16))
        form.addRow("Height", self._height_spin)

        self._folder_edit = QLineEdit(str(output_folder or "").strip())
        self._folder_edit.setPlaceholderText("Used when an image entry has no file path yet")
        form.addRow("Fallback Folder", self._folder_edit)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def width_value(self) -> int:
        return int(self._width_spin.value())

    def height_value(self) -> int:
        return int(self._height_spin.value())

    def output_folder(self) -> str:
        return str(self._folder_edit.text() or "").strip()


class _QuickPreviewBoardDialog(QDialog):
    def __init__(self, cards, *, total_assets: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Quick Preview Board")
        self.resize(1080, 760)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self._summary_label = QLabel(f"Previewing {total_assets} assets from quick mode.")
        self._summary_label.setWordWrap(True)
        layout.addWidget(self._summary_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll, 1)

        container = QWidget()
        self._cards_layout = QGridLayout(container)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setHorizontalSpacing(10)
        self._cards_layout.setVerticalSpacing(10)

        columns = 3
        for index, card in enumerate(cards):
            self._cards_layout.addWidget(card, index // columns, index % columns)
        for column in range(columns):
            self._cards_layout.setColumnStretch(column, 1)
        self._cards_layout.setRowStretch((len(cards) + columns - 1) // columns, 1)
        scroll.setWidget(container)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class _FontTextEditorDialog(QDialog):
    def __init__(self, *, filename: str, initial_text: str, is_new_file: bool, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Font Text")
        self.setMinimumSize(560, 420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        summary = QLabel(
            "Edit the UTF-8 text content used to generate glyphs for this font."
            + (" A new text file will be created when you save." if is_new_file else "")
        )
        summary.setWordWrap(True)
        layout.addWidget(summary)

        filename_label = QLabel(f"Target: {filename}")
        filename_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(filename_label)

        self._editor = QPlainTextEdit()
        self._editor.setPlainText(str(initial_text or ""))
        layout.addWidget(self._editor, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def text_value(self) -> str:
        return self._editor.toPlainText()


class _FontTextLinksDialog(QDialog):
    def __init__(
        self,
        *,
        initial_items: list[str],
        source_dir: str = "",
        normalize_file_callback=None,
        edit_file_callback=None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Font Text Files")
        self.setMinimumSize(720, 520)
        self._normalize_file_callback = normalize_file_callback
        self._edit_file_callback = edit_file_callback
        self._source_dir = str(source_dir or "").strip()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        summary = QLabel("Manage linked UTF-8 text files. Enter one path per line. Duplicates are removed when you save.")
        summary.setWordWrap(True)
        layout.addWidget(summary)

        if source_dir:
            source_label = QLabel(f"Source Dir: {source_dir}")
            source_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            layout.addWidget(source_label)

        self._count_label = QLabel("")
        layout.addWidget(self._count_label)

        content_row = QHBoxLayout()
        content_row.setContentsMargins(0, 0, 0, 0)
        content_row.setSpacing(10)
        layout.addLayout(content_row, 1)

        self._list_widget = QListWidget()
        self._list_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        self._list_widget.itemSelectionChanged.connect(self._refresh_action_state)
        self._list_widget.itemDoubleClicked.connect(lambda _item: self._activate_selected_item())
        content_row.addWidget(self._list_widget, 1)

        actions_col = QVBoxLayout()
        actions_col.setContentsMargins(0, 0, 0, 0)
        actions_col.setSpacing(8)
        content_row.addLayout(actions_col)

        self._new_file_button = QPushButton("New File...")
        self._new_file_button.setEnabled(callable(edit_file_callback))
        self._new_file_button.clicked.connect(self._new_file)
        actions_col.addWidget(self._new_file_button)

        self._add_files_button = QPushButton("Add Files...")
        self._add_files_button.setEnabled(callable(normalize_file_callback))
        self._add_files_button.clicked.connect(self._add_files)
        actions_col.addWidget(self._add_files_button)

        self._add_path_button = QPushButton("Add Path...")
        self._add_path_button.clicked.connect(self._add_path)
        actions_col.addWidget(self._add_path_button)

        self._edit_path_button = QPushButton("Edit Path...")
        self._edit_path_button.clicked.connect(self._edit_selected_path)
        actions_col.addWidget(self._edit_path_button)

        self._edit_file_button = QPushButton("Edit File...")
        self._edit_file_button.clicked.connect(self._edit_selected_file)
        actions_col.addWidget(self._edit_file_button)

        self._copy_path_button = QPushButton("Copy Full Path")
        self._copy_path_button.clicked.connect(self._copy_selected_path)
        actions_col.addWidget(self._copy_path_button)

        self._open_folder_button = QPushButton("Open Folder")
        self._open_folder_button.clicked.connect(self._open_selected_folder)
        actions_col.addWidget(self._open_folder_button)

        self._remove_path_button = QPushButton("Remove")
        self._remove_path_button.clicked.connect(self._remove_selected_path)
        actions_col.addWidget(self._remove_path_button)

        self._move_up_button = QPushButton("Move Up")
        self._move_up_button.clicked.connect(lambda: self._move_selected_path(-1))
        actions_col.addWidget(self._move_up_button)

        self._move_down_button = QPushButton("Move Down")
        self._move_down_button.clicked.connect(lambda: self._move_selected_path(1))
        actions_col.addWidget(self._move_down_button)

        actions_col.addStretch(1)

        self._path_label = QLabel("")
        self._path_label.setWordWrap(True)
        self._path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self._path_label)

        self._preview_info_label = QLabel("")
        self._preview_info_label.setWordWrap(True)
        layout.addWidget(self._preview_info_label)

        self._preview_text_edit = QPlainTextEdit()
        self._preview_text_edit.setReadOnly(True)
        self._preview_text_edit.setMinimumHeight(120)
        self._preview_text_edit.setPlaceholderText("Select a linked text file to preview its UTF-8 contents.")
        layout.addWidget(self._preview_text_edit)

        self._combined_preview_info_label = QLabel("")
        self._combined_preview_info_label.setWordWrap(True)
        layout.addWidget(self._combined_preview_info_label)

        self._combined_preview_text_edit = QPlainTextEdit()
        self._combined_preview_text_edit.setReadOnly(True)
        self._combined_preview_text_edit.setMinimumHeight(160)
        self._combined_preview_text_edit.setPlaceholderText(
            "The combined linked text preview will appear here in the current file order."
        )
        layout.addWidget(self._combined_preview_text_edit)

        self._set_items(initial_items or [], selected_index=0)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _split_items(self, value: str) -> list[str]:
        items = []
        for item in re.split(r"[,;\r\n\uFF0C\uFF1B]+", str(value or "")):
            normalized = item.strip()
            if normalized and normalized not in items:
                items.append(normalized)
        return items

    def _normalize_manual_item(self, value: str) -> str:
        items = self._split_items(value)
        if not items:
            return ""
        return str(items[0]).replace("\\", "/")

    def _validated_manual_item(self, value: str, *, title: str) -> str:
        normalized = self._normalize_manual_item(value)
        if not normalized:
            return ""
        if os.path.isabs(normalized) or not self._source_dir:
            return normalized
        resolved = self._resolved_item_path(normalized)
        if resolved and _is_subpath(resolved, self._source_dir):
            return normalized
        QMessageBox.warning(self, title, "Relative text file paths must stay inside Source Dir.")
        return ""

    def _current_values(self) -> list[str]:
        values = []
        for row in range(self._list_widget.count()):
            item = self._list_widget.item(row)
            raw_value = str(item.data(Qt.UserRole) or "").strip()
            if raw_value and raw_value not in values:
                values.append(raw_value)
        return values

    def _resolved_item_path(self, raw_value: str) -> str:
        raw = str(raw_value or "").strip()
        if not raw:
            return ""
        if os.path.isabs(raw):
            return normalize_path(raw)
        if self._source_dir:
            return normalize_path(os.path.join(self._source_dir, raw))
        return raw

    def _item_label(self, raw_value: str) -> str:
        raw = str(raw_value or "").strip()
        resolved = self._resolved_item_path(raw)
        if resolved and os.path.exists(resolved):
            return raw
        return f"{raw} (missing)"

    def _set_items(self, values: list[str], *, selected_index: int = -1):
        items = []
        for value in values:
            normalized = self._normalize_manual_item(value)
            if normalized and normalized not in items:
                items.append(normalized)

        with QSignalBlocker(self._list_widget):
            self._list_widget.clear()
            for raw_value in items:
                item = QListWidgetItem(self._item_label(raw_value))
                item.setData(Qt.UserRole, raw_value)
                item.setToolTip(self._resolved_item_path(raw_value))
                self._list_widget.addItem(item)
            if self._list_widget.count() > 0:
                target_row = selected_index if 0 <= selected_index < self._list_widget.count() else 0
                self._list_widget.setCurrentRow(target_row)
        self._update_count_label()
        self._refresh_action_state()

    def _selected_row(self) -> int:
        return int(self._list_widget.currentRow())

    def _selected_value(self) -> str:
        row = self._selected_row()
        if row < 0:
            return ""
        item = self._list_widget.item(row)
        return str(item.data(Qt.UserRole) or "").strip() if item is not None else ""

    def _display_path_for_value(self, raw_value: str) -> str:
        raw = str(raw_value or "").strip()
        if not raw:
            return ""
        resolved = self._resolved_item_path(raw)
        return resolved or raw

    def _folder_path_for_value(self, raw_value: str) -> str:
        raw = str(raw_value or "").strip()
        if not raw:
            return ""
        resolved = self._resolved_item_path(raw)
        candidates = []
        if resolved:
            candidates.append(resolved if os.path.isdir(resolved) else os.path.dirname(resolved))
        if not os.path.isabs(raw):
            if self._source_dir:
                relative_dir = os.path.dirname(raw)
                candidates.append(normalize_path(os.path.join(self._source_dir, relative_dir)) if relative_dir else self._source_dir)
        else:
            candidates.append(os.path.dirname(raw))

        seen = set()
        for candidate in candidates:
            normalized = normalize_path(candidate)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            current = normalized
            while current and not os.path.exists(current):
                parent = os.path.dirname(current)
                if not parent or parent == current:
                    current = ""
                    break
                current = parent
            if current and os.path.isdir(current):
                return current
        return ""

    def _update_count_label(self):
        values = self._current_values()
        missing = 0
        for value in values:
            resolved = self._resolved_item_path(value)
            if not resolved or not os.path.exists(resolved):
                missing += 1
        summary = f"Linked text files: {len(values)}"
        if missing:
            summary += f" | Missing: {missing}"
        self._count_label.setText(summary)

    def _refresh_action_state(self):
        row = self._selected_row()
        has_selection = row >= 0
        count = self._list_widget.count()
        self._edit_path_button.setEnabled(has_selection)
        self._edit_file_button.setEnabled(has_selection and callable(self._edit_file_callback))
        self._copy_path_button.setEnabled(has_selection)
        self._open_folder_button.setEnabled(bool(self._folder_path_for_value(self._selected_value())))
        self._remove_path_button.setEnabled(has_selection)
        self._move_up_button.setEnabled(has_selection and row > 0)
        self._move_down_button.setEnabled(has_selection and 0 <= row < count - 1)

        raw_value = self._selected_value()
        resolved = self._resolved_item_path(raw_value)
        if callable(self._edit_file_callback) and has_selection:
            self._edit_file_button.setText("Edit File..." if resolved and os.path.isfile(resolved) else "Create File...")
        else:
            self._edit_file_button.setText("Edit File...")
        if raw_value:
            if resolved and resolved != raw_value:
                self._path_label.setText(f"Resolved: {resolved}")
            else:
                self._path_label.setText(f"Path: {raw_value}")
        else:
            self._path_label.setText("Select a linked text file to inspect or reorder it.")
        self._update_preview(raw_value, resolved)
        self._update_combined_preview()

    def _update_preview(self, raw_value: str, resolved_path: str):
        raw = str(raw_value or "").strip()
        resolved = str(resolved_path or "").strip()
        if not raw:
            self._preview_info_label.setText("Preview: Select a linked text file.")
            self._preview_text_edit.clear()
            return
        if not resolved or not os.path.exists(resolved):
            self._preview_info_label.setText("Preview: File is missing.")
            self._preview_text_edit.setPlainText("")
            return
        if os.path.isdir(resolved):
            self._preview_info_label.setText("Preview: Selected path is a folder.")
            self._preview_text_edit.setPlainText("")
            return

        try:
            with open(resolved, "r", encoding="utf-8", errors="replace") as handle:
                content = handle.read(_FONT_TEXT_PREVIEW_CHAR_LIMIT + 1)
        except OSError as exc:
            self._preview_info_label.setText("Preview: Failed to read file.")
            self._preview_text_edit.setPlainText(str(exc))
            return

        truncated = len(content) > _FONT_TEXT_PREVIEW_CHAR_LIMIT
        if truncated:
            content = content[:_FONT_TEXT_PREVIEW_CHAR_LIMIT]
        line_count = len(content.splitlines()) or (1 if content else 0)
        summary = f"Preview: {line_count} line(s), {len(content)} char(s)"
        if truncated:
            summary += " shown (truncated)"
            content = content.rstrip("\n") + "\n..."
        self._preview_info_label.setText(summary)
        self._preview_text_edit.setPlainText(content)

    def _update_combined_preview(self):
        values = self._current_values()
        if not values:
            self._combined_preview_info_label.setText("Combined Preview: No linked text files.")
            self._combined_preview_text_edit.clear()
            return

        blocks = []
        available = 0
        missing = 0
        used_chars = 0
        truncated = False

        for value in values:
            resolved = self._resolved_item_path(value)
            header = f"[{value}]"
            if not resolved or not os.path.isfile(resolved):
                missing += 1
                blocks.append(f"{header}\n(missing)")
                continue

            available += 1
            remaining = max(0, _FONT_TEXT_COMBINED_PREVIEW_CHAR_LIMIT - used_chars)
            if remaining <= 0:
                truncated = True
                break
            try:
                with open(resolved, "r", encoding="utf-8", errors="replace") as handle:
                    content = handle.read(remaining + 1)
            except OSError as exc:
                blocks.append(f"{header}\n(read failed: {exc})")
                continue

            if len(content) > remaining:
                truncated = True
                content = content[:remaining]
            used_chars += len(content)
            blocks.append(f"{header}\n{content.rstrip()}" if content.strip() else f"{header}\n(empty)")

        summary = f"Combined Preview: {available} file(s)"
        if missing:
            summary += f", {missing} missing"
        if truncated:
            summary += " (truncated)"
            blocks.append("...")
        self._combined_preview_info_label.setText(summary)
        self._combined_preview_text_edit.setPlainText("\n\n".join(blocks).strip())

    def _add_files(self):
        if not callable(self._normalize_file_callback):
            return
        start_dir = self._source_dir or os.getcwd()
        paths, _ = QFileDialog.getOpenFileNames(self, "Add Font Text Files", start_dir, "Text files (*.txt);;All files (*)")
        if not paths:
            return
        items = self._current_values()
        for path in paths:
            normalized = self._normalize_file_callback(normalize_path(path))
            if normalized and normalized not in items:
                items.append(normalized)
        self._set_items(items, selected_index=len(items) - 1)

    def _prompt_path(self, *, title: str, initial_value: str = "") -> str:
        text, accepted = QInputDialog.getText(
            self,
            title,
            "Text file path relative to Source Dir:",
            QLineEdit.Normal,
            str(initial_value or ""),
        )
        if not accepted:
            return ""
        return self._validated_manual_item(text, title=title)

    def _new_file(self):
        if not callable(self._edit_file_callback):
            return

        value = self._prompt_path(title="New Font Text File")
        if not value:
            return

        items = self._current_values()
        if value in items:
            self._set_items(items, selected_index=items.index(value))
            self._edit_selected_file()
            return

        resolved_path = self._resolved_item_path(value)
        if resolved_path and os.path.isdir(resolved_path):
            QMessageBox.warning(self, "New Font Text File", f"Selected path is a folder:\n{resolved_path}")
            return

        existed_before = bool(resolved_path and os.path.isfile(resolved_path))
        result = self._edit_file_callback(value)
        file_exists_after_edit = bool(resolved_path and os.path.isfile(resolved_path))
        if result is False:
            return
        if not existed_before and not file_exists_after_edit and result is not True:
            return

        items.append(value)
        self._set_items(items, selected_index=len(items) - 1)

    def _add_path(self):
        value = self._prompt_path(title="Add Font Text Path")
        if not value:
            return
        items = self._current_values()
        if value in items:
            return
        items.append(value)
        self._set_items(items, selected_index=len(items) - 1)

    def _edit_selected_path(self):
        row = self._selected_row()
        if row < 0:
            return
        items = self._current_values()
        current_value = items[row]
        updated_value = self._prompt_path(title="Edit Font Text Path", initial_value=current_value)
        if not updated_value:
            return
        if updated_value in items and updated_value != current_value:
            items = [value for index, value in enumerate(items) if index != row]
            target_index = items.index(updated_value)
            self._set_items(items, selected_index=target_index)
            return
        items[row] = updated_value
        self._set_items(items, selected_index=row)

    def _remove_selected_path(self):
        row = self._selected_row()
        if row < 0:
            return
        items = self._current_values()
        items.pop(row)
        self._set_items(items, selected_index=min(row, len(items) - 1))

    def _activate_selected_item(self):
        if callable(self._edit_file_callback):
            self._edit_selected_file()
            return
        self._edit_selected_path()

    def _edit_selected_file(self):
        if not callable(self._edit_file_callback):
            return
        row = self._selected_row()
        raw_value = self._selected_value()
        if row < 0 or not raw_value:
            return
        self._edit_file_callback(raw_value)
        self._set_items(self._current_values(), selected_index=row)

    def _copy_selected_path(self):
        path = self._display_path_for_value(self._selected_value())
        if path:
            QApplication.clipboard().setText(path)

    def _open_selected_folder(self):
        folder_path = self._folder_path_for_value(self._selected_value())
        if folder_path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder_path))

    def _move_selected_path(self, delta: int):
        row = self._selected_row()
        if row < 0:
            return
        target = row + int(delta)
        items = self._current_values()
        if not (0 <= target < len(items)):
            return
        items[row], items[target] = items[target], items[row]
        self._set_items(items, selected_index=target)

    def text_value(self) -> str:
        return "\n".join(self._current_values())


class ResourceGeneratorWindow(QDialog):
    """Modeless standalone window for editing and generating resources."""

    def __init__(self, sdk_root: str = "", parent=None):
        super().__init__(parent)
        self.setWindowFlag(Qt.Window, True)
        self.setWindowFlag(Qt.WindowMinMaxButtonsHint, True)
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, True)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setObjectName("resource_generator_window")
        self.resize(1360, 860)

        self._config = get_config()
        self._session = ResourceGenerationSession(sdk_root=sdk_root)
        self._dirty = False
        self._raw_dirty = False
        self._syncing_raw = False
        self._active_section = "img"
        self._active_entry_index = -1
        self._active_field_widgets: dict[str, QWidget] = {}
        self._last_tab_index = 0
        self._clean_paths = GenerationPaths()
        self._clean_user_data = make_empty_resource_config()
        self._ui_mode = "simple"
        self._simple_row_map: list[tuple[str, int]] = []
        self._simple_asset_sort_column = -1
        self._simple_asset_sort_descending = False
        self._window_shortcuts: dict[str, QShortcut] = {}
        self._view_state_updates_enabled = False
        self._pending_simple_workspace_splitter_sizes: list[int] | None = None
        self._pending_simple_preview_splitter_sizes: list[int] | None = None
        self._pending_simple_asset_column_widths: list[int] | None = None

        self._build_ui()
        self._configure_drop_targets()
        self._configure_shortcuts()
        self._restore_view_state()
        self._apply_paths_and_data(GenerationPaths(), make_empty_resource_config(), dirty=False)
        self._view_state_updates_enabled = True
        QTimer.singleShot(0, self._apply_pending_view_state_layouts)

    def showEvent(self, event):
        super().showEvent(event)
        self._apply_pending_view_state_layouts()
        self._sync_window_chrome_theme()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in {QEvent.StyleChange, QEvent.PaletteChange}:
            self._sync_window_chrome_theme()
            self._apply_resource_table_palettes()
            if getattr(self, "_simple_asset_table", None) is not None:
                self._refresh_simple_page()

    def dragEnterEvent(self, event):
        if self._accepts_external_asset_drop(event.mimeData()):
            event.acceptProposedAction()
            return
        event.ignore()

    def dragMoveEvent(self, event):
        if self._accepts_external_asset_drop(event.mimeData()):
            event.acceptProposedAction()
            return
        event.ignore()

    def dropEvent(self, event):
        if not self._accepts_external_asset_drop(event.mimeData()):
            event.ignore()
            return
        self._handle_external_asset_drop(event.mimeData())
        event.acceptProposedAction()

    def eventFilter(self, watched, event):
        if event.type() == QEvent.DragEnter:
            if self._accepts_external_asset_drop(event.mimeData()):
                event.acceptProposedAction()
                return True
            return False
        if event.type() == QEvent.DragMove:
            if self._accepts_external_asset_drop(event.mimeData()):
                event.acceptProposedAction()
                return True
            return False
        if event.type() == QEvent.Drop:
            if not self._accepts_external_asset_drop(event.mimeData()):
                return False
            self._handle_external_asset_drop(event.mimeData())
            event.acceptProposedAction()
            return True
        return super().eventFilter(watched, event)

    def _sync_window_chrome_theme(self):
        sync_window_chrome_theme(self)

    # -- Public API -----------------------------------------------------

    def open_with_paths(self, paths: GenerationPaths, *, sdk_root: str = "", load_existing: bool = True):
        if sdk_root:
            self._session.set_sdk_root(sdk_root)
        normalized_paths = (paths or GenerationPaths()).normalized()
        if load_existing and normalized_paths.config_path and os.path.isfile(normalized_paths.config_path):
            self._session.load_from_file(
                normalized_paths.config_path,
                source_dir=normalized_paths.source_dir,
                workspace_dir=normalized_paths.workspace_dir,
                bin_output_dir=normalized_paths.bin_output_dir,
            )
            self._apply_session_state(dirty=False)
            return
        self._apply_paths_and_data(normalized_paths, make_empty_resource_config(), dirty=False)

    def has_unsaved_changes(self) -> bool:
        return bool(self._dirty or self._raw_dirty)

    # -- UI setup -------------------------------------------------------

    def _build_ui(self):
        self.setWindowTitle("Resource Generator")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        layout.addLayout(self._build_toolbar())
        layout.addWidget(self._build_path_group())
        layout.addWidget(self._build_workspace_stack(), 1)

        self._status_label = QLabel("")
        layout.addWidget(self._status_label)

    def _build_toolbar(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._new_button = QPushButton("New")
        self._new_button.setShortcut(QKeySequence("Ctrl+N"))
        self._new_button.clicked.connect(self._new_config)
        layout.addWidget(self._new_button)

        self._open_button = QPushButton("Open...")
        self._open_button.setShortcut(QKeySequence("Ctrl+O"))
        self._open_button.clicked.connect(self._open_config_dialog)
        layout.addWidget(self._open_button)

        self._save_button = QPushButton("Save")
        self._save_button.setShortcut(QKeySequence("Ctrl+S"))
        self._save_button.clicked.connect(self._save_config)
        layout.addWidget(self._save_button)

        self._save_as_button = QPushButton("Save As...")
        self._save_as_button.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self._save_as_button.clicked.connect(self._save_config_as)
        layout.addWidget(self._save_as_button)

        self._generate_button = QPushButton("Generate")
        self._generate_button.setShortcut(QKeySequence("Ctrl+Return"))
        self._generate_button.clicked.connect(self._generate_resources)
        layout.addWidget(self._generate_button)

        layout.addSpacing(16)
        layout.addWidget(QLabel("Mode"))

        self._mode_combo = QComboBox()
        self._mode_combo.addItem("Simple", "simple")
        self._mode_combo.addItem("Professional", "professional")
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        layout.addWidget(self._mode_combo)

        layout.addStretch(1)
        return layout

    def _build_workspace_stack(self):
        self._workspace_stack = QStackedWidget()
        self._simple_page = self._build_simple_page()
        self._professional_page = self._build_professional_page()
        self._workspace_stack.addWidget(self._simple_page)
        self._workspace_stack.addWidget(self._professional_page)
        return self._workspace_stack

    def _build_simple_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        intro_group = QGroupBox("Quick Mode")
        intro_layout = QVBoxLayout(intro_group)
        intro_layout.setContentsMargins(12, 12, 12, 12)
        intro_layout.setSpacing(8)

        intro = QLabel(
            "Use quick helpers to scan an asset folder, edit font text files, and build resources without editing every field manually."
        )
        intro.setWordWrap(True)
        intro_layout.addWidget(intro)

        self._simple_drop_hint_label = QLabel("Tip: drag files or asset folders into this window to import them directly.")
        self._simple_drop_hint_label.setWordWrap(True)
        intro_layout.addWidget(self._simple_drop_hint_label)

        self._import_assets_button = QPushButton("Import Files...")
        self._import_assets_button.clicked.connect(self._import_asset_files_dialog)

        self._scan_assets_button = QPushButton("Scan Asset Folder...")
        self._scan_assets_button.clicked.connect(self._scan_assets_directory_dialog)

        self._pack_assets_button = QPushButton("Pack Into Source Dir")
        self._pack_assets_button.clicked.connect(self._pack_assets_into_source_dir)

        self._organize_folders_button = QPushButton("Organize Folders")
        self._organize_folders_button.clicked.connect(self._organize_assets_into_standard_folders)

        self._generate_font_text_button = QPushButton("Generate Font Text...")
        self._generate_font_text_button.clicked.connect(self._open_generate_charset_helper)

        self._rename_assets_button = QPushButton("Rename Names From Files")
        self._rename_assets_button.clicked.connect(self._rename_asset_names_from_files)

        self._sort_assets_button = QPushButton("Sort Assets")
        self._sort_assets_button.clicked.connect(self._sort_assets_for_quick_mode)

        self._dedupe_assets_button = QPushButton("Remove Duplicates")
        self._dedupe_assets_button.clicked.connect(self._remove_duplicate_assets_for_quick_mode)

        self._remove_missing_assets_button = QPushButton("Remove Missing")
        self._remove_missing_assets_button.clicked.connect(self._remove_missing_assets_for_quick_mode)

        self._clean_helper_outputs_button = QPushButton("Clean Helper Outputs")
        self._clean_helper_outputs_button.clicked.connect(self._remove_generated_helper_outputs_for_quick_mode)

        self._open_font_text_button = QPushButton("Edit Font Text...")
        self._open_font_text_button.clicked.connect(self._open_selected_font_text_resource)

        self._preview_board_button = QPushButton("Preview Board...")
        self._preview_board_button.clicked.connect(self._open_quick_preview_board)

        self._export_preview_board_button = QPushButton("Export Preview PNG...")
        self._export_preview_board_button.clicked.connect(self._export_quick_preview_board_dialog)

        self._detect_video_info_button = QPushButton("Detect Video Info")
        self._detect_video_info_button.clicked.connect(self._detect_selected_video_metadata)

        self._edit_asset_button = QPushButton("Edit / Open Asset...")
        self._edit_asset_button.clicked.connect(self._open_selected_asset_in_external_editor)

        self._open_asset_folder_button = QPushButton("Open Asset Folder...")
        self._open_asset_folder_button.clicked.connect(self._open_selected_asset_folder)

        self._resize_image_button = QPushButton("Resize Image...")
        self._resize_image_button.clicked.connect(self._open_resize_image_helper)

        self._add_border_image_button = QPushButton("Add Border...")
        self._add_border_image_button.clicked.connect(self._open_border_image_helper)

        self._add_background_image_button = QPushButton("Add Background...")
        self._add_background_image_button.clicked.connect(self._open_background_image_helper)

        self._round_corners_image_button = QPushButton("Round Corners...")
        self._round_corners_image_button.clicked.connect(self._open_round_corners_image_helper)

        self._adjust_opacity_image_button = QPushButton("Adjust Opacity...")
        self._adjust_opacity_image_button.clicked.connect(self._open_opacity_image_helper)

        self._generate_thumbnails_button = QPushButton("Generate Thumbnails...")
        self._generate_thumbnails_button.clicked.connect(self._open_generate_thumbnails_helper)

        self._generate_placeholders_button = QPushButton("Generate Placeholders...")
        self._generate_placeholders_button.clicked.connect(self._open_generate_placeholders_helper)

        self._normalize_images_button = QPushButton("Normalize Images...")
        self._normalize_images_button.clicked.connect(self._open_normalize_images_helper)

        self._compress_images_button = QPushButton("Compress Images...")
        self._compress_images_button.clicked.connect(self._open_compress_images_helper)

        self._prerender_fonts_button = QPushButton("Pre-Render Fonts...")
        self._prerender_fonts_button.clicked.connect(self._open_prerender_fonts_helper)

        self._rotate_image_button = QPushButton("Rotate Image...")
        self._rotate_image_button.clicked.connect(self._open_rotate_image_helper)

        self._flip_image_button = QPushButton("Flip Image...")
        self._flip_image_button.clicked.connect(self._open_flip_image_helper)

        self._crop_image_button = QPushButton("Crop Image...")
        self._crop_image_button.clicked.connect(self._open_crop_image_helper)

        self._duplicate_simple_asset_button = QPushButton("Duplicate Selected")
        self._duplicate_simple_asset_button.clicked.connect(self._duplicate_selected_simple_asset)

        self._remove_simple_asset_button = QPushButton("Remove Selected")
        self._remove_simple_asset_button.clicked.connect(self._remove_selected_simple_asset)

        self._open_professional_button = QPushButton("Open Professional Mode")
        self._open_professional_button.clicked.connect(self._open_current_simple_selection_in_professional_mode)

        counts_row = QHBoxLayout()
        counts_row.setContentsMargins(0, 0, 0, 0)
        counts_row.setSpacing(16)
        self._simple_image_count = _ClickableLabel("Images: 0")
        self._simple_image_count.setToolTip("Show only image assets.")
        self._simple_image_count.clicked.connect(lambda: self._set_simple_asset_filter("img"))
        counts_row.addWidget(self._simple_image_count)
        self._simple_font_count = _ClickableLabel("Fonts: 0")
        self._simple_font_count.setToolTip("Show only font assets.")
        self._simple_font_count.clicked.connect(lambda: self._set_simple_asset_filter("font"))
        counts_row.addWidget(self._simple_font_count)
        self._simple_mp4_count = _ClickableLabel("MP4: 0")
        self._simple_mp4_count.setToolTip("Show only video assets.")
        self._simple_mp4_count.clicked.connect(lambda: self._set_simple_asset_filter("mp4"))
        counts_row.addWidget(self._simple_mp4_count)
        self._simple_attention_count = _ClickableLabel("Needs Attention: 0")
        self._simple_attention_count.setToolTip("No assets currently need attention.")
        self._simple_attention_count.clicked.connect(lambda: self._set_simple_asset_filter("attention"))
        counts_row.addWidget(self._simple_attention_count)
        counts_row.addStretch(1)
        intro_layout.addLayout(counts_row)

        self._simple_action_tabs = QTabWidget()
        self._simple_action_tabs.setDocumentMode(True)
        self._simple_action_tabs.setStyleSheet("QTabBar::tab { min-height: 18px; padding: 1px 8px; }")
        tab_bar = self._simple_action_tabs.tabBar()
        tab_font = QFont(tab_bar.font())
        tab_font.setPointSize(9)
        tab_bar.setFont(tab_font)
        tab_bar.setExpanding(False)
        tab_bar.setUsesScrollButtons(False)
        tab_bar.setFixedHeight(24)
        self._simple_action_tabs.addTab(
            self._build_simple_action_tab(
                "Start",
                "Import resources, organize files, and prepare font text content.",
                [
                    self._build_simple_action_group(
                        "Import & Setup",
                        [
                            self._import_assets_button,
                            self._scan_assets_button,
                            self._pack_assets_button,
                            self._organize_folders_button,
                            self._generate_font_text_button,
                        ],
                        columns=3,
                    )
                ],
            ),
            "Start",
        )
        self._simple_action_tabs.addTab(
            self._build_simple_action_tab(
                "Clean",
                "Keep the asset set tidy without bulk auto-fixing hidden fields.",
                [
                    self._build_simple_action_group(
                        "Batch Fixes",
                        [
                            self._rename_assets_button,
                            self._sort_assets_button,
                            self._dedupe_assets_button,
                            self._remove_missing_assets_button,
                            self._clean_helper_outputs_button,
                        ],
                        columns=3,
                    )
                ],
            ),
            "Clean",
        )
        self._simple_action_tabs.addTab(
            self._build_simple_action_tab(
                "Inspect",
                "Selection preview updates automatically. Use the preview panel for asset actions, or export a board for the whole set.",
                [
                    self._build_simple_action_group(
                        "Preview & Export",
                        [
                            self._preview_board_button,
                            self._export_preview_board_button,
                        ],
                        columns=2,
                    )
                ],
            ),
            "Inspect",
        )
        self._simple_action_tabs.addTab(
            self._build_simple_action_tab(
                "Transforms",
                "Generate helper outputs or batch image/font derivatives.",
                [
                    self._build_simple_action_group(
                        "Image Tools",
                        [
                            self._resize_image_button,
                            self._add_border_image_button,
                            self._add_background_image_button,
                            self._round_corners_image_button,
                            self._adjust_opacity_image_button,
                            self._generate_thumbnails_button,
                            self._generate_placeholders_button,
                            self._normalize_images_button,
                            self._compress_images_button,
                            self._prerender_fonts_button,
                            self._rotate_image_button,
                            self._flip_image_button,
                            self._crop_image_button,
                        ],
                        columns=2,
                    )
                ],
            ),
            "Transforms",
        )
        self._simple_action_tabs.addTab(
            self._build_simple_action_tab(
                "Selection",
                "Operate on the currently selected asset or jump into professional mode.",
                [
                    self._build_simple_action_group(
                        "Selection",
                        [
                            self._duplicate_simple_asset_button,
                            self._remove_simple_asset_button,
                            self._open_professional_button,
                        ],
                        columns=3,
                    )
                ],
            ),
            "Selection",
        )
        self._simple_actions_scroll = QScrollArea()
        self._simple_actions_scroll.setWidgetResizable(True)
        self._simple_actions_scroll.setFrameShape(QFrame.NoFrame)
        self._simple_actions_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._simple_actions_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._simple_actions_scroll.setWidget(self._simple_action_tabs)
        intro_layout.addWidget(self._simple_actions_scroll, 1)

        assets_group = QGroupBox("Assets")
        assets_layout = QVBoxLayout(assets_group)
        assets_layout.setContentsMargins(10, 10, 10, 10)
        assets_layout.setSpacing(8)

        asset_toolbar = QHBoxLayout()
        asset_toolbar.setContentsMargins(0, 0, 0, 0)
        asset_toolbar.setSpacing(8)
        asset_toolbar.addWidget(QLabel("Show"))
        self._simple_asset_type_filter = QComboBox()
        self._simple_asset_type_filter.addItem("All Assets", "all")
        self._simple_asset_type_filter.addItem("Images", "img")
        self._simple_asset_type_filter.addItem("Fonts", "font")
        self._simple_asset_type_filter.addItem("MP4", "mp4")
        self._simple_asset_type_filter.addItem("Needs Attention", "attention")
        self._simple_asset_type_filter.addItem("Missing Files", "missing")
        self._simple_asset_type_filter.addItem("Generated Helpers", "generated")
        self._simple_asset_type_filter.currentIndexChanged.connect(self._on_simple_asset_filter_changed)
        asset_toolbar.addWidget(self._simple_asset_type_filter)

        asset_toolbar.addWidget(QLabel("Search"))
        self._simple_asset_search_edit = QLineEdit()
        self._simple_asset_search_edit.setPlaceholderText("Filter by name, file, text file, format, size...")
        self._simple_asset_search_edit.textChanged.connect(self._on_simple_asset_search_changed)
        asset_toolbar.addWidget(self._simple_asset_search_edit, 1)

        self._simple_asset_clear_filters_button = QPushButton("Clear Filters")
        self._simple_asset_clear_filters_button.clicked.connect(self._clear_simple_asset_filters)
        asset_toolbar.addWidget(self._simple_asset_clear_filters_button)

        self._simple_asset_result_label = QLabel("Showing 0 of 0 assets")
        asset_toolbar.addWidget(self._simple_asset_result_label)
        assets_layout.addLayout(asset_toolbar)

        self._simple_asset_table = QTableWidget(0, 4)
        self._simple_asset_table.setHorizontalHeaderLabels(["Type", "Name", "File", "Details"])
        self._simple_asset_table.itemSelectionChanged.connect(self._on_simple_asset_selection_changed)
        self._simple_asset_table.itemDoubleClicked.connect(self._activate_selected_simple_asset)
        self._simple_asset_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._simple_asset_table.customContextMenuRequested.connect(self._show_simple_asset_context_menu)
        self._configure_simple_asset_table()
        self._simple_asset_empty_state = self._build_simple_asset_empty_state()
        self._simple_asset_content_stack = QStackedWidget()
        self._simple_asset_content_stack.addWidget(self._simple_asset_table)
        self._simple_asset_content_stack.addWidget(self._simple_asset_empty_state)
        assets_layout.addWidget(self._simple_asset_content_stack, 1)

        self._simple_preview_splitter = QSplitter(Qt.Horizontal)
        self._simple_preview_splitter.setChildrenCollapsible(False)
        self._simple_preview_splitter.setHandleWidth(8)

        asset_preview_group = QGroupBox("Asset Preview")
        asset_preview_layout = QVBoxLayout(asset_preview_group)
        asset_preview_layout.setContentsMargins(8, 8, 8, 8)
        asset_preview_layout.setSpacing(8)

        preview_header = QHBoxLayout()
        preview_header.setContentsMargins(0, 0, 0, 0)
        preview_header.setSpacing(8)
        self._simple_asset_preview_title = QLabel("No asset selected.")
        preview_header.addWidget(self._simple_asset_preview_title, 1)

        self._simple_asset_primary_action_button = QPushButton("Open Asset")
        self._simple_asset_primary_action_button.clicked.connect(self._trigger_selected_simple_asset_primary_action)
        self._simple_asset_primary_action_button.hide()
        preview_header.addWidget(self._simple_asset_primary_action_button, 0, Qt.AlignRight)

        self._simple_asset_more_actions_button = QPushButton("More...")
        self._simple_asset_more_actions_button.clicked.connect(self._show_selected_simple_asset_actions_menu)
        self._simple_asset_more_actions_button.hide()
        preview_header.addWidget(self._simple_asset_more_actions_button, 0, Qt.AlignRight)
        asset_preview_layout.addLayout(preview_header)

        self._simple_asset_preview_label = QLabel("Select an image, font, or video entry to inspect it here.")
        self._simple_asset_preview_label.setAlignment(Qt.AlignCenter)
        self._simple_asset_preview_label.setMinimumHeight(96)
        self._simple_asset_preview_label.setWordWrap(True)
        asset_preview_layout.addWidget(self._simple_asset_preview_label, 1)

        self._simple_asset_meta = QPlainTextEdit()
        self._simple_asset_meta.setReadOnly(True)
        self._simple_asset_meta.setMinimumHeight(72)
        asset_preview_layout.addWidget(self._simple_asset_meta, 1)
        self._simple_preview_splitter.addWidget(asset_preview_group)

        preview_group = QGroupBox("Merged Preview")
        preview_layout = QVBoxLayout(preview_group)
        preview_layout.setContentsMargins(8, 8, 8, 8)
        self._simple_preview = QPlainTextEdit()
        self._simple_preview.setReadOnly(True)
        preview_layout.addWidget(self._simple_preview)
        self._simple_preview_splitter.addWidget(preview_group)
        self._simple_preview_splitter.setStretchFactor(0, 1)
        self._simple_preview_splitter.setStretchFactor(1, 1)
        self._simple_preview_splitter.setSizes(_DEFAULT_SIMPLE_PREVIEW_SPLITTER_SIZES)
        self._simple_preview_splitter.setMinimumHeight(120)
        self._simple_workspace_splitter = QSplitter(Qt.Vertical)
        self._simple_workspace_splitter.setChildrenCollapsible(False)
        self._simple_workspace_splitter.setHandleWidth(8)
        self._simple_workspace_splitter.addWidget(intro_group)
        self._simple_workspace_splitter.addWidget(assets_group)
        self._simple_workspace_splitter.addWidget(self._simple_preview_splitter)
        intro_group.setMinimumHeight(120)
        assets_group.setMinimumHeight(140)
        self._simple_workspace_splitter.setStretchFactor(0, 0)
        self._simple_workspace_splitter.setStretchFactor(1, 1)
        self._simple_workspace_splitter.setStretchFactor(2, 1)
        self._simple_workspace_splitter.setSizes(_DEFAULT_SIMPLE_WORKSPACE_SPLITTER_SIZES)
        self._simple_workspace_splitter.splitterMoved.connect(lambda _pos, _index: self._remember_view_state())
        self._simple_preview_splitter.splitterMoved.connect(lambda _pos, _index: self._remember_view_state())
        layout.addWidget(self._simple_workspace_splitter, 1)
        self._update_simple_action_button_states()
        return page

    def _configure_shortcuts(self):
        self._register_window_shortcut("Ctrl+F", self._focus_simple_asset_search)
        self._register_window_shortcut("Delete", self._shortcut_remove_selected_simple_asset)
        self._register_window_shortcut("Ctrl+D", self._shortcut_duplicate_simple_asset)
        self._register_window_shortcut("Ctrl+E", self._shortcut_open_simple_selection_in_professional_mode)
        self._register_simple_asset_shortcut("Return", self._trigger_selected_simple_asset_primary_action)
        self._register_simple_asset_shortcut("Enter", self._trigger_selected_simple_asset_primary_action)
        self._register_simple_asset_shortcut("Shift+F10", self._show_selected_simple_asset_actions_menu)

    def _configure_drop_targets(self):
        for widget in self._drop_target_widgets():
            widget.setAcceptDrops(True)
            if widget is not self:
                widget.installEventFilter(self)

    def _drop_target_widgets(self):
        widgets = [
            self,
            getattr(self, "_workspace_stack", None),
            getattr(self, "_simple_page", None),
            getattr(self, "_professional_page", None),
            getattr(self, "_simple_workspace_splitter", None),
            getattr(self, "_simple_preview_splitter", None),
            getattr(self, "_simple_asset_table", None),
            getattr(self, "_entry_table", None),
            getattr(self, "_section_list", None),
            getattr(self, "_simple_actions_scroll", None),
            getattr(self, "_simple_preview", None),
            getattr(self, "_simple_asset_meta", None),
            getattr(self, "_simple_asset_preview_label", None),
        ]
        for widget in (getattr(self, "_simple_asset_table", None), getattr(self, "_entry_table", None), getattr(self, "_section_list", None)):
            viewport = widget.viewport() if widget is not None and hasattr(widget, "viewport") else None
            widgets.append(viewport)
        seen: set[int] = set()
        ordered_widgets = []
        for widget in widgets:
            if widget is None:
                continue
            marker = id(widget)
            if marker in seen:
                continue
            seen.add(marker)
            ordered_widgets.append(widget)
        return ordered_widgets

    def _accepts_external_asset_drop(self, mime_data) -> bool:
        local_paths = _local_paths_from_mime_data(mime_data)
        if not local_paths:
            return False
        for path in local_paths:
            if os.path.isdir(path):
                return True
            if not os.path.isfile(path):
                continue
            extension = os.path.splitext(path)[1].lower()
            if extension in _TEXT_FILE_EXTENSIONS or extension in _IMAGE_FILE_EXTENSIONS or extension in _FONT_FILE_EXTENSIONS or extension in _VIDEO_FILE_EXTENSIONS:
                return True
        return False

    def _handle_external_asset_drop(self, mime_data):
        local_paths = _local_paths_from_mime_data(mime_data)
        if not local_paths:
            return

        directories, import_files = _collect_importable_drop_files(local_paths)
        direct_files = [path for path in local_paths if os.path.isfile(path)]
        if len(directories) == 1 and not direct_files:
            self._scan_assets_from_directory(directories[0])
            return
        if import_files:
            self._import_assets_from_files(import_files)
            return
        if len(directories) == 1:
            self._scan_assets_from_directory(directories[0])
            return
        self._set_status("Dropped items did not include supported image, font, video, or text files.")

    def _register_window_shortcut(self, sequence: str, callback):
        shortcut = QShortcut(QKeySequence(sequence), self)
        shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        shortcut.activated.connect(callback)
        self._window_shortcuts[str(sequence)] = shortcut

    def _register_simple_asset_shortcut(self, sequence: str, callback):
        shortcut = QShortcut(QKeySequence(sequence), self._simple_asset_table)
        shortcut.setContext(Qt.WidgetShortcut)
        shortcut.activated.connect(callback)
        self._window_shortcuts[str(sequence)] = shortcut

    def _focus_simple_asset_search(self):
        if self._ui_mode != "simple":
            return
        self._simple_asset_search_edit.setFocus()
        self._simple_asset_search_edit.selectAll()

    def _shortcut_remove_selected_simple_asset(self):
        if self._ui_mode == "simple" and self._remove_simple_asset_button.isEnabled():
            self._remove_selected_simple_asset()

    def _shortcut_duplicate_simple_asset(self):
        if self._ui_mode == "simple" and self._duplicate_simple_asset_button.isEnabled():
            self._duplicate_selected_simple_asset()

    def _shortcut_open_simple_selection_in_professional_mode(self):
        if self._ui_mode == "simple" and self._open_professional_button.isEnabled():
            self._open_current_simple_selection_in_professional_mode()

    def _build_simple_action_group(self, title: str, buttons, *, columns: int) -> QGroupBox:
        group = QGroupBox(title)
        layout = QGridLayout(group)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setHorizontalSpacing(8)
        layout.setVerticalSpacing(8)
        for index, button in enumerate(buttons):
            button.setMinimumHeight(30)
            layout.addWidget(button, index // columns, index % columns)
        for column in range(columns):
            layout.setColumnStretch(column, 1)
        return group

    def _build_simple_action_tab(self, title: str, description: str, groups) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        summary = QLabel(description)
        summary.setWordWrap(True)
        layout.addWidget(summary)

        for group in groups:
            layout.addWidget(group)
        layout.addStretch(1)
        return page

    def _configure_simple_asset_table(self):
        self._apply_resource_table_palettes()
        self._simple_asset_table.verticalHeader().setVisible(False)
        self._simple_asset_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._simple_asset_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._simple_asset_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._simple_asset_table.setAlternatingRowColors(True)
        self._simple_asset_table.setShowGrid(False)
        self._simple_asset_table.setWordWrap(False)
        self._simple_asset_table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self._simple_asset_table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self._simple_asset_table.setTextElideMode(Qt.ElideMiddle)
        row_height = max(30, self.fontMetrics().height() + 12)
        vertical_header = self._simple_asset_table.verticalHeader()
        vertical_header.setDefaultSectionSize(row_height)
        vertical_header.setMinimumSectionSize(row_height)

        simple_header = self._simple_asset_table.horizontalHeader()
        header_font = QFont(simple_header.font())
        header_font.setPointSize(10)
        simple_header.setFont(header_font)
        simple_header.setMinimumHeight(max(24, simple_header.fontMetrics().height() + 10))
        simple_header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        simple_header.setStretchLastSection(False)
        simple_header.setSectionsClickable(True)
        for column in range(self._simple_asset_table.columnCount()):
            simple_header.setSectionResizeMode(column, QHeaderView.Interactive)
        simple_header.sectionResized.connect(lambda _index, _old_size, _new_size: self._remember_view_state())
        simple_header.sectionClicked.connect(self._toggle_simple_asset_sort)
        for column, width in enumerate(_DEFAULT_SIMPLE_ASSET_COLUMN_WIDTHS):
            simple_header.resizeSection(column, width)
        self._apply_simple_asset_sort_indicator()

    def _apply_resource_table_palette(self, table: QTableWidget | None, *, use_alt_background: bool):
        if table is None:
            return
        tokens = app_theme_tokens()
        palette = QPalette(table.palette())
        base_color = QColor(tokens["panel_alt"] if use_alt_background else tokens["panel_raised"])
        alternate_color = QColor(tokens["panel_raised"] if use_alt_background else tokens["panel_alt"])
        text_color = QColor(tokens["text"])
        muted_color = QColor(tokens["text_soft"])
        highlight_color = QColor(tokens["selection"])
        inactive_highlight_color = QColor(tokens["selection_soft"])
        palette.setColor(QPalette.Base, base_color)
        palette.setColor(QPalette.AlternateBase, alternate_color)
        palette.setColor(QPalette.Window, base_color)
        palette.setColor(QPalette.Text, text_color)
        palette.setColor(QPalette.WindowText, text_color)
        palette.setColor(QPalette.ButtonText, text_color)
        palette.setColor(QPalette.Highlight, highlight_color)
        palette.setColor(QPalette.HighlightedText, text_color)
        palette.setColor(QPalette.Disabled, QPalette.Text, muted_color)
        palette.setColor(QPalette.Disabled, QPalette.WindowText, muted_color)
        palette.setColor(QPalette.Inactive, QPalette.Highlight, inactive_highlight_color)
        palette.setColor(QPalette.Inactive, QPalette.HighlightedText, text_color)
        table.setPalette(palette)
        viewport = table.viewport() if hasattr(table, "viewport") else None
        if viewport is not None:
            viewport.setPalette(palette)
            viewport.setAutoFillBackground(True)

    def _apply_resource_table_palettes(self):
        self._apply_resource_table_palette(getattr(self, "_simple_asset_table", None), use_alt_background=False)
        self._apply_resource_table_palette(getattr(self, "_entry_table", None), use_alt_background=True)

    def _build_simple_asset_empty_state(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)
        layout.addStretch(1)

        self._simple_asset_empty_title = QLabel("No assets imported yet.")
        empty_title_font = QFont(self._simple_asset_empty_title.font())
        empty_title_font.setPointSize(max(empty_title_font.pointSize(), 12))
        empty_title_font.setBold(True)
        self._simple_asset_empty_title.setFont(empty_title_font)
        self._simple_asset_empty_title.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._simple_asset_empty_title)

        self._simple_asset_empty_description = QLabel(
            "Drag files or asset folders here, import files, or scan an asset folder to start building resources."
        )
        self._simple_asset_empty_description.setAlignment(Qt.AlignCenter)
        self._simple_asset_empty_description.setWordWrap(True)
        layout.addWidget(self._simple_asset_empty_description)

        buttons_row = QHBoxLayout()
        buttons_row.setContentsMargins(0, 0, 0, 0)
        buttons_row.setSpacing(8)
        buttons_row.addStretch(1)

        self._simple_asset_empty_import_button = QPushButton("Import Files...")
        self._simple_asset_empty_import_button.clicked.connect(self._import_asset_files_dialog)
        buttons_row.addWidget(self._simple_asset_empty_import_button)

        self._simple_asset_empty_scan_button = QPushButton("Scan Asset Folder...")
        self._simple_asset_empty_scan_button.clicked.connect(self._scan_assets_directory_dialog)
        buttons_row.addWidget(self._simple_asset_empty_scan_button)

        self._simple_asset_empty_clear_button = QPushButton("Clear Filters")
        self._simple_asset_empty_clear_button.clicked.connect(self._clear_simple_asset_filters)
        buttons_row.addWidget(self._simple_asset_empty_clear_button)

        buttons_row.addStretch(1)
        layout.addLayout(buttons_row)
        layout.addStretch(1)
        return page

    def _update_simple_asset_empty_state(self, *, total_assets: int, visible_assets: int, has_filters: bool):
        if visible_assets > 0:
            self._simple_asset_content_stack.setCurrentWidget(self._simple_asset_table)
            return

        self._simple_asset_content_stack.setCurrentWidget(self._simple_asset_empty_state)
        active_filter = str(self._simple_asset_type_filter.currentData() or "all")
        if total_assets <= 0:
            self._simple_asset_empty_title.setText("No assets imported yet.")
            self._simple_asset_empty_description.setText(
                "Drag files or asset folders here, import files, or scan an asset folder to start building resources."
            )
            self._simple_asset_empty_import_button.setVisible(True)
            self._simple_asset_empty_scan_button.setVisible(True)
            self._simple_asset_empty_clear_button.setVisible(False)
            return

        if has_filters:
            if active_filter == "attention":
                self._simple_asset_empty_title.setText("No assets need attention right now.")
                self._simple_asset_empty_description.setText(
                    "The current resource list has no missing files, missing font text, or incomplete video metadata."
                )
            else:
                self._simple_asset_empty_title.setText("No assets match the current filters.")
                self._simple_asset_empty_description.setText(
                    "Clear the search or asset type filter to bring matching resources back into view."
                )
            self._simple_asset_empty_import_button.setVisible(False)
            self._simple_asset_empty_scan_button.setVisible(False)
            self._simple_asset_empty_clear_button.setVisible(True)
            return

        self._simple_asset_empty_title.setText("No visible assets in the current view.")
        self._simple_asset_empty_description.setText(
            "Import files or scan an asset folder to populate the quick resource list."
        )
        self._simple_asset_empty_import_button.setVisible(True)
        self._simple_asset_empty_scan_button.setVisible(True)
        self._simple_asset_empty_clear_button.setVisible(False)

    def _show_simple_asset_context_menu(self, pos):
        menu = self._build_simple_asset_context_menu(row=self._simple_asset_table.rowAt(pos.y()))
        if menu is None:
            return
        menu.exec_(self._simple_asset_table.viewport().mapToGlobal(pos))

    def _toggle_simple_asset_sort(self, column: int):
        if not (0 <= int(column) < self._simple_asset_table.columnCount()):
            return
        if self._simple_asset_sort_column != int(column):
            self._simple_asset_sort_column = int(column)
            self._simple_asset_sort_descending = False
        elif not self._simple_asset_sort_descending:
            self._simple_asset_sort_descending = True
        else:
            self._simple_asset_sort_column = -1
            self._simple_asset_sort_descending = False
        self._apply_simple_asset_sort_indicator()
        self._refresh_simple_page()
        self._remember_view_state()

    def _apply_simple_asset_sort_indicator(self):
        header = self._simple_asset_table.horizontalHeader()
        if self._simple_asset_sort_column < 0:
            header.setSortIndicatorShown(False)
            return
        header.setSortIndicatorShown(True)
        header.setSortIndicator(
            self._simple_asset_sort_column,
            Qt.DescendingOrder if self._simple_asset_sort_descending else Qt.AscendingOrder,
        )

    def _simple_asset_row_sort_key(self, row_payload) -> tuple:
        values = (
            str(row_payload["type_label"] or "").strip().lower(),
            str(row_payload["name_label"] or "").strip().lower(),
            str(row_payload["file_label"] or "").strip().lower(),
            str(row_payload["detail_label"] or "").strip().lower(),
        )
        sort_index = self._simple_asset_sort_column if 0 <= self._simple_asset_sort_column < len(values) else 1
        return (
            values[sort_index],
            values[1],
            values[2],
            values[3],
            values[0],
            int(row_payload["index"]),
        )

    def _simple_asset_attention_messages(self, section: str, entry: dict, *, file_label: str = "") -> tuple[str, ...]:
        messages: list[str] = []
        normalized_file = str(file_label or entry.get("file", "") or "").strip()
        resolved_path = self._resolve_entry_path(section, "file", normalized_file)
        if not normalized_file:
            messages.append("Asset file is empty.")
        elif not resolved_path:
            messages.append("Asset file path could not be resolved.")
        elif not os.path.exists(resolved_path):
            messages.append("Asset file is missing.")

        if section == "font":
            text_items = self._font_text_items_from_value(entry.get("text", ""))
            if not text_items:
                messages.append("Font text file is not linked.")
            else:
                missing_text_items = []
                for item in text_items:
                    resolved_text = self._resolve_entry_path("font", "text", item)
                    if not resolved_text or not os.path.exists(resolved_text):
                        missing_text_items.append(item)
                if missing_text_items:
                    if len(missing_text_items) == 1:
                        messages.append(f"Font text file is missing: {missing_text_items[0]}")
                    else:
                        messages.append(f"{len(missing_text_items)} font text files are missing.")

        if section == "mp4":
            missing_fields = []
            for field_name in ("fps", "width", "height"):
                raw_value = str(entry.get(field_name, "") or "").strip()
                try:
                    numeric_value = int(raw_value)
                except Exception:
                    numeric_value = 0
                if numeric_value <= 0:
                    missing_fields.append(field_name)
            if missing_fields:
                messages.append("Video metadata is incomplete: " + ", ".join(missing_fields))

        return tuple(messages)

    def _simple_asset_recommended_fixes(self, section: str, entry: dict, *, file_label: str = "") -> tuple[str, ...]:
        suggestions: list[str] = []
        normalized_file = str(file_label or entry.get("file", "") or "").strip()
        resolved_path = self._resolve_entry_path(section, "file", normalized_file)
        file_exists = bool(resolved_path and os.path.exists(resolved_path))
        target_dir = self._simple_asset_target_folder(section, file_label=normalized_file)

        if not normalized_file:
            suggestions.append("Set the File field in Professional Mode.")
        elif not resolved_path:
            suggestions.append("Set Source Dir or correct the asset path in Professional Mode.")
        elif not file_exists:
            if target_dir:
                suggestions.append("Use Open Asset Folder to restore the missing file, or remove the asset from the config.")
            else:
                suggestions.append("Restore the missing file or remove the asset from the config.")

        if section == "font":
            text_value = str(entry.get("text", "") or "").strip()
            text_items = self._font_text_items_from_value(text_value)
            if not text_items:
                suggestions.append("Use Edit Font Text... to create the charset file.")
            else:
                missing_text_items = []
                for item in text_items:
                    resolved_text = self._resolve_entry_path("font", "text", item)
                    if not resolved_text or not os.path.exists(resolved_text):
                        missing_text_items.append(item)
                if missing_text_items:
                    suggestions.append("Use Edit Font Text... to create or update the charset file.")
                matched_text = self._matched_font_text_path("font", entry)
                if matched_text and matched_text != text_value:
                    suggestions.append("Use Professional Mode to relink the detected charset file.")

        if section == "mp4":
            missing_fields = []
            for field_name in ("fps", "width", "height"):
                raw_value = str(entry.get(field_name, "") or "").strip()
                try:
                    numeric_value = int(raw_value)
                except Exception:
                    numeric_value = 0
                if numeric_value <= 0:
                    missing_fields.append(field_name)
            if missing_fields:
                suggestions.append("Use Detect Video Info to fill fps, width, and height.")

        return tuple(dict.fromkeys(item for item in suggestions if item))

    def _simple_asset_target_folder(self, section: str, *, file_label: str = "") -> str:
        resolved_path = self._resolve_entry_path(section, "file", file_label)
        candidates = []
        if resolved_path:
            candidates.append(os.path.dirname(resolved_path))
        source_dir = normalize_path(self._session.paths.source_dir)
        if source_dir:
            candidates.append(source_dir)

        for candidate in candidates:
            current = normalize_path(candidate)
            while current:
                if os.path.isdir(current):
                    return current
                parent = normalize_path(os.path.dirname(current))
                if not parent or parent == current:
                    break
                current = parent
        return ""

    def _simple_asset_primary_fix_action(self, section: str, entry: dict, *, file_label: str = "") -> tuple[str, callable] | None:
        normalized_file = str(file_label or entry.get("file", "") or "").strip()
        resolved_path = self._resolve_entry_path(section, "file", normalized_file)
        file_exists = bool(resolved_path and os.path.exists(resolved_path))
        target_dir = self._simple_asset_target_folder(section, file_label=normalized_file)
        if normalized_file and resolved_path and not file_exists and target_dir:
            return "Suggested Fix: Open Asset Folder", self._open_selected_asset_folder
        if not normalized_file or not resolved_path or not file_exists:
            return "Suggested Fix: Open Professional Mode", self._open_current_simple_selection_in_professional_mode

        if section == "font":
            text_value = str(entry.get("text", "") or "").strip()
            text_items = self._font_text_items_from_value(text_value)
            missing_text_items = []
            for item in text_items:
                resolved_text = self._resolve_entry_path("font", "text", item)
                if not resolved_text or not os.path.exists(resolved_text):
                    missing_text_items.append(item)
            if not text_items or missing_text_items:
                return "Suggested Fix: Edit Font Text...", self._open_selected_font_text_resource
            matched_text = self._matched_font_text_path("font", entry)
            if matched_text and matched_text != text_value:
                return "Suggested Fix: Open Professional Mode", self._open_current_simple_selection_in_professional_mode

        if section == "mp4":
            for field_name in ("fps", "width", "height"):
                raw_value = str(entry.get(field_name, "") or "").strip()
                try:
                    numeric_value = int(raw_value)
                except Exception:
                    numeric_value = 0
                if numeric_value <= 0:
                    return "Suggested Fix: Detect Video Info", self._detect_selected_video_metadata

        return None

    def _simple_asset_primary_action_label(self, action_text: str) -> str:
        normalized = str(action_text or "").strip()
        prefix = "Suggested Fix: "
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :].strip()
        return normalized or "Open Asset"

    def _simple_asset_primary_action(self, section: str, entry: dict, *, file_label: str = "") -> tuple[str, callable] | None:
        primary_fix = self._simple_asset_primary_fix_action(section, entry, file_label=file_label)
        if primary_fix is not None:
            action_text, callback = primary_fix
            return self._simple_asset_primary_action_label(action_text), callback

        resolved_path = self._resolve_entry_path(section, "file", file_label)
        if resolved_path and os.path.exists(resolved_path):
            return "Open Asset", self._open_selected_asset_in_external_editor

        return "Open Professional Mode", self._open_current_simple_selection_in_professional_mode

    def _simple_asset_search_blob(
        self,
        section_filter: str,
        *,
        type_label: str,
        name_label: str,
        file_label: str,
        detail_label: str,
        attention_messages: tuple[str, ...] = (),
        recommended_fixes: tuple[str, ...] = (),
    ) -> str:
        parts = [type_label, name_label, file_label, detail_label]
        if str(section_filter or "") == "attention":
            parts.extend(attention_messages)
            parts.extend(recommended_fixes)
        return " ".join(part for part in parts if part).lower()

    def _style_simple_asset_table_item(self, item: QTableWidgetItem, *, has_attention: bool, column: int):
        if not has_attention:
            return
        tokens = app_theme_tokens()
        warning_color = QColor(tokens["warning"])
        background_color = QColor(warning_color)
        background_color.setAlpha(42 if QColor(tokens["bg"]).lightness() < 128 else 24)
        item.setBackground(background_color)
        if column == 0:
            item.setForeground(warning_color)
            font = QFont(item.font())
            font.setBold(True)
            item.setFont(font)

    def _update_simple_attention_count(self, attention_count: int):
        count = max(0, int(attention_count))
        self._simple_attention_count.setText(f"Needs Attention: {count}")
        tooltip = (
            "Use Show > Needs Attention to review missing files, missing font text, and incomplete video metadata."
            if count > 0
            else "No assets currently need attention."
        )
        self._simple_attention_count.setToolTip(tooltip)
        font = QFont(self._simple_attention_count.font())
        font.setBold(count > 0)
        self._simple_attention_count.setFont(font)
        if count > 0:
            tokens = app_theme_tokens()
            self._simple_attention_count.setStyleSheet(f"color: {tokens['warning']};")
        else:
            self._simple_attention_count.setStyleSheet("")

    def _simple_asset_matches_filter(self, section_filter: str, section: str, entry: dict, *, file_label: str) -> bool:
        normalized_filter = str(section_filter or "all")
        if normalized_filter in {"all", ""}:
            return True
        if normalized_filter in KNOWN_RESOURCE_SECTIONS:
            return section == normalized_filter
        if normalized_filter == "attention":
            return bool(self._simple_asset_attention_messages(section, entry, file_label=file_label))
        if normalized_filter == "missing":
            resolved_path = self._resolve_entry_path(section, "file", file_label)
            return not file_label or not resolved_path or not os.path.exists(resolved_path)
        if normalized_filter == "generated":
            return section == "img" and _is_quick_generated_helper_path(file_label)
        return True

    def _build_simple_asset_context_menu(self, *, row: int | None = None) -> QMenu | None:
        if row is not None and row >= 0:
            self._simple_asset_table.selectRow(row)
        section, _index, entry = self._selected_simple_asset_context()
        if entry is None or not section:
            return None

        file_name = str(entry.get("file", "") or "").strip()
        resolved_path = self._resolve_entry_path(section, "file", file_name)
        has_file_value = bool(file_name)
        has_resolved_file = bool(resolved_path and os.path.exists(resolved_path))
        target_dir = self._simple_asset_target_folder(section, file_label=file_name)
        has_target_dir = bool(target_dir)
        has_expected_full_path = bool(resolved_path)

        menu = QMenu(self)
        primary_fix = self._simple_asset_primary_fix_action(section, entry, file_label=file_name)
        primary_fix_text = primary_fix[0] if primary_fix is not None else ""
        if primary_fix is not None:
            action_text, callback = primary_fix
            fix_action = menu.addAction(action_text)
            fix_action.triggered.connect(callback)
            menu.addSeparator()

        open_asset_action = menu.addAction("Open Asset")
        open_asset_action.setEnabled(has_resolved_file)
        open_asset_action.triggered.connect(self._open_selected_asset_in_external_editor)

        open_folder_action = menu.addAction("Open Asset Folder")
        open_folder_action.setEnabled(has_target_dir)
        open_folder_action.triggered.connect(self._open_selected_asset_folder)

        if section == "font" and primary_fix_text != "Suggested Fix: Edit Font Text...":
            open_text_action = menu.addAction("Edit Font Text")
            open_text_action.triggered.connect(self._open_selected_font_text_resource)
        if section == "font":
            manage_text_action = menu.addAction("Manage Text Files")
            manage_text_action.triggered.connect(self._open_selected_font_text_links_editor)

        menu.addSeparator()

        copy_name_action = menu.addAction("Copy Resource Name")
        copy_name_action.triggered.connect(self._copy_selected_simple_asset_name)

        copy_asset_path_action = menu.addAction("Copy Asset Path")
        copy_asset_path_action.setEnabled(has_file_value)
        copy_asset_path_action.triggered.connect(self._copy_selected_simple_asset_relative_path)

        copy_full_path_action = menu.addAction("Copy Full Path")
        copy_full_path_action.setEnabled(has_expected_full_path)
        copy_full_path_action.triggered.connect(self._copy_selected_simple_asset_absolute_path)

        menu.addSeparator()

        duplicate_action = menu.addAction("Duplicate")
        duplicate_action.triggered.connect(self._duplicate_selected_simple_asset)

        remove_action = menu.addAction("Remove")
        remove_action.triggered.connect(self._remove_selected_simple_asset)

        open_professional_action = menu.addAction("Open Professional Mode")
        open_professional_action.triggered.connect(self._open_current_simple_selection_in_professional_mode)

        return menu

    def _show_selected_simple_asset_actions_menu(self):
        menu = self._build_simple_asset_context_menu()
        if menu is None:
            return
        anchor = self._simple_asset_more_actions_button
        menu.exec_(anchor.mapToGlobal(anchor.rect().bottomLeft()))

    def _on_simple_asset_filter_changed(self, _index: int):
        self._refresh_simple_page()
        self._remember_view_state()

    def _on_simple_asset_search_changed(self, _text: str):
        self._refresh_simple_page()
        self._remember_view_state()

    def _set_simple_asset_filter(self, filter_value: str):
        target_index = self._simple_asset_type_filter.findData(str(filter_value or "all"))
        if target_index < 0:
            return
        if self._simple_asset_type_filter.currentIndex() == target_index:
            self._simple_asset_table.setFocus()
            return
        self._simple_asset_type_filter.setCurrentIndex(target_index)
        self._simple_asset_table.setFocus()

    def _clear_simple_asset_filters(self):
        with QSignalBlocker(self._simple_asset_type_filter):
            self._simple_asset_type_filter.setCurrentIndex(0)
        with QSignalBlocker(self._simple_asset_search_edit):
            self._simple_asset_search_edit.clear()
        self._refresh_simple_page()

    def _build_professional_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(self._build_center_splitter(), 1)
        layout.addWidget(self._build_bottom_tabs(), 1)
        return page

    def _build_path_group(self):
        group = QGroupBox("Paths")
        grid = QGridLayout(group)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)

        self._config_path_edit = self._add_path_row(
            grid,
            0,
            "Config",
            self._browse_config_target_path,
            "Path to the editable user config file.",
            "config_path",
        )
        self._source_dir_edit = self._add_path_row(
            grid,
            1,
            "Source Dir",
            lambda: self._browse_directory_path("source_dir"),
            "Directory containing source images, fonts, text files, and optional .designer overlay.",
            "source_dir",
        )
        self._workspace_dir_edit = self._add_path_row(
            grid,
            2,
            "Workspace",
            lambda: self._browse_directory_path("workspace_dir"),
            "Generation workspace that will contain src/img/font and generated files.",
            "workspace_dir",
        )
        self._bin_output_dir_edit = self._add_path_row(
            grid,
            3,
            "Bin Output",
            lambda: self._browse_directory_path("bin_output_dir"),
            "Output directory for the merged resource bin.",
            "bin_output_dir",
        )
        return group

    def _add_path_row(self, grid: QGridLayout, row: int, label: str, handler, tooltip: str, path_field: str):
        grid.addWidget(QLabel(label), row, 0)
        edit = QLineEdit()
        edit.setToolTip(tooltip)
        edit.editingFinished.connect(lambda field=path_field, widget=edit: self._on_path_edited(field, widget))
        grid.addWidget(edit, row, 1)
        button = QPushButton("Browse...")
        button.clicked.connect(handler)
        grid.addWidget(button, row, 2)
        return edit

    def _build_center_splitter(self):
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_section_panel())
        splitter.addWidget(self._build_entry_panel())
        splitter.addWidget(self._build_editor_panel())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 1)
        splitter.setSizes([170, 360, 520])
        return splitter

    def _build_section_panel(self):
        container = QGroupBox("Sections")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        self._section_list = QListWidget()
        self._section_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._section_list.currentRowChanged.connect(self._on_section_changed)
        for section in KNOWN_RESOURCE_SECTIONS:
            item = QListWidgetItem(RESOURCE_SECTION_SPECS[section].label)
            item.setData(Qt.UserRole, section)
            self._section_list.addItem(item)
        layout.addWidget(self._section_list)
        return container

    def _build_entry_panel(self):
        container = QGroupBox("Entries")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        header_layout = QHBoxLayout()
        self._add_entry_button = QPushButton("Add")
        self._add_entry_button.clicked.connect(self._add_entry)
        header_layout.addWidget(self._add_entry_button)
        self._remove_entry_button = QPushButton("Remove")
        self._remove_entry_button.clicked.connect(self._remove_entry)
        header_layout.addWidget(self._remove_entry_button)
        header_layout.addStretch(1)
        layout.addLayout(header_layout)

        self._entry_table = QTableWidget(0, 2)
        self._entry_table.setHorizontalHeaderLabels(["Name", "File"])
        self._entry_table.verticalHeader().setVisible(False)
        self._entry_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._entry_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._entry_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._entry_table.itemSelectionChanged.connect(self._on_entry_selection_changed)
        header = self._entry_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        self._apply_resource_table_palettes()
        layout.addWidget(self._entry_table, 1)
        return container

    def _build_editor_panel(self):
        container = QGroupBox("Entry Editor")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self._entry_summary = QPlainTextEdit()
        self._entry_summary.setReadOnly(True)
        self._entry_summary.setMinimumHeight(180)
        layout.addWidget(self._entry_summary)

        self._form_host = QWidget()
        self._form_layout = QFormLayout(self._form_host)
        self._form_layout.setContentsMargins(0, 0, 0, 0)
        self._form_layout.setSpacing(8)
        layout.addWidget(self._form_host, 1)
        return container

    def _build_bottom_tabs(self):
        self._bottom_tabs = QTabWidget()
        self._bottom_tabs.currentChanged.connect(self._on_bottom_tab_changed)

        self._raw_editor = QPlainTextEdit()
        self._raw_editor.textChanged.connect(self._on_raw_text_changed)
        self._bottom_tabs.addTab(self._raw_editor, "Raw JSON")

        self._merged_preview = QPlainTextEdit()
        self._merged_preview.setReadOnly(True)
        self._bottom_tabs.addTab(self._merged_preview, "Merged Preview")

        self._log_output = QPlainTextEdit()
        self._log_output.setReadOnly(True)
        self._bottom_tabs.addTab(self._log_output, "Generation Log")
        return self._bottom_tabs

    # -- Session/path loading ------------------------------------------

    def _apply_paths_and_data(self, paths: GenerationPaths, user_data: dict, *, dirty: bool):
        self._session.reset(paths, user_data)
        self._apply_session_state(dirty=dirty)

    def _apply_session_state(self, *, dirty: bool):
        self._dirty = dirty
        self._raw_dirty = False
        self._syncing_raw = False
        if not dirty:
            self._capture_clean_snapshot()
        self._refresh_path_fields()
        self._refresh_section_selection()
        self._refresh_entry_table()
        self._update_form()
        self._update_raw_editor(force=True)
        self._update_merged_preview()
        self._refresh_simple_page()
        self._set_ui_mode(self._ui_mode)
        self._set_status("Ready.")
        self._update_title()

    def _on_path_edited(self, field_name: str, widget: QLineEdit):
        value = widget.text().strip()
        previous_paths = GenerationPaths(
            config_path=self._session.paths.config_path,
            source_dir=self._session.paths.source_dir,
            workspace_dir=self._session.paths.workspace_dir,
            bin_output_dir=self._session.paths.bin_output_dir,
        )
        self._session.update_path(field_name, value)
        if field_name == "config_path":
            self._rebase_inferred_paths(previous_paths, self._session.paths.config_path)
            self._refresh_path_fields()
        if self._session.paths != previous_paths:
            self._mark_dirty()
        self._update_merged_preview()
        self._update_form()

    def _sync_path_widgets_to_session(self):
        self._session.set_paths(
            GenerationPaths(
                config_path=self._config_path_edit.text().strip(),
                source_dir=self._source_dir_edit.text().strip(),
                workspace_dir=self._workspace_dir_edit.text().strip(),
                bin_output_dir=self._bin_output_dir_edit.text().strip(),
            )
        )

    def _refresh_path_fields(self):
        self._config_path_edit.setText(self._session.paths.config_path)
        self._source_dir_edit.setText(self._session.paths.source_dir)
        self._workspace_dir_edit.setText(self._session.paths.workspace_dir)
        self._bin_output_dir_edit.setText(self._session.paths.bin_output_dir)

    # -- Entry/section views -------------------------------------------

    def _refresh_section_selection(self):
        for row in range(self._section_list.count()):
            item = self._section_list.item(row)
            if item.data(Qt.UserRole) == self._active_section:
                self._section_list.setCurrentRow(row)
                return
        self._active_section = KNOWN_RESOURCE_SECTIONS[0]
        self._section_list.setCurrentRow(0)

    def _refresh_entry_table(self):
        entries = self._session.section_entries(self._active_section)
        with QSignalBlocker(self._entry_table):
            self._entry_table.setRowCount(len(entries))
            for row, entry in enumerate(entries):
                label_item = QTableWidgetItem(section_entry_label(self._active_section, entry, row))
                file_item = QTableWidgetItem(str((entry or {}).get("file", "") or ""))
                self._entry_table.setItem(row, 0, label_item)
                self._entry_table.setItem(row, 1, file_item)

        if entries:
            if not (0 <= self._active_entry_index < len(entries)):
                self._active_entry_index = 0
            self._entry_table.selectRow(self._active_entry_index)
        else:
            self._active_entry_index = -1
        self._update_form()
        self._refresh_simple_page()

    def _refresh_current_table_row(self):
        entry = self._current_entry()
        row = self._active_entry_index
        if entry is None or row < 0:
            return
        if self._entry_table.rowCount() <= row:
            return
        name_item = self._entry_table.item(row, 0)
        if name_item is None:
            name_item = QTableWidgetItem()
            self._entry_table.setItem(row, 0, name_item)
        name_item.setText(section_entry_label(self._active_section, entry, row))
        file_item = self._entry_table.item(row, 1)
        if file_item is None:
            file_item = QTableWidgetItem()
            self._entry_table.setItem(row, 1, file_item)
        file_item.setText(str(entry.get("file", "") or ""))
        self._refresh_simple_page()

    def _current_entry(self) -> dict | None:
        entries = self._session.section_entries(self._active_section)
        if 0 <= self._active_entry_index < len(entries):
            entry = entries[self._active_entry_index]
            return entry if isinstance(entry, dict) else None
        return None

    def _update_form(self):
        self._clear_form()
        entry = self._current_entry()
        if entry is None:
            self._entry_summary.setPlainText("No entry selected.")
            return

        self._entry_summary.setPlainText(self._entry_summary_text(entry))
        section_spec = RESOURCE_SECTION_SPECS[self._active_section]
        for field_spec in section_spec.fields:
            self._form_layout.addRow(field_spec.label, self._create_field_editor(field_spec, entry))

    def _create_field_editor(self, field_spec, entry: dict):
        value = entry.get(field_spec.name, "")
        if field_spec.editor == "combo":
            combo = QComboBox()
            combo.addItems(list(field_spec.choices))
            current_text = str(value if value is not None else "")
            if current_text and combo.findText(current_text) < 0:
                combo.addItem(current_text)
            combo.setCurrentText(current_text)
            combo.currentTextChanged.connect(
                lambda text, field_name=field_spec.name: self._update_current_entry_field(field_name, text)
            )
            self._active_field_widgets[field_spec.name] = combo
            return combo

        wrapper = QWidget()
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        edit = QLineEdit(str(value if value is not None else ""))
        if field_spec.placeholder:
            edit.setPlaceholderText(field_spec.placeholder)
        edit.textEdited.connect(lambda text, field_name=field_spec.name: self._update_current_entry_field(field_name, text))
        if self._active_section == "font" and field_spec.name == "text":
            edit.editingFinished.connect(lambda field_name=field_spec.name, widget=edit: self._commit_font_text_field(field_name, widget))
        layout.addWidget(edit, 1)
        self._active_field_widgets[field_spec.name] = edit

        if field_spec.name in {"file", "text"}:
            button = QPushButton("Browse...")
            button.clicked.connect(lambda _checked=False, spec=field_spec: self._browse_entry_field(spec))
            layout.addWidget(button)
        if self._active_section == "font" and field_spec.name == "text":
            links_button = QPushButton("Links...")
            links_button.clicked.connect(self._open_selected_font_text_links_editor)
            layout.addWidget(links_button)
            edit_button = QPushButton("Edit...")
            edit_button.clicked.connect(self._open_selected_font_text_resource)
            layout.addWidget(edit_button)

        return wrapper

    def _entry_summary_text(self, entry: dict) -> str:
        lines = [
            f"Section: {RESOURCE_SECTION_SPECS[self._active_section].label}",
            f"Entry: {self._active_entry_index + 1}",
            "",
            json.dumps(entry, indent=4, ensure_ascii=False),
        ]
        file_name = str(entry.get("file", "") or "").strip()
        if file_name:
            resolved_path = self._resolve_entry_path(self._active_section, "file", file_name)
            lines.extend(
                [
                    "",
                    f"Resolved File: {resolved_path or file_name}",
                    f"Exists: {'yes' if resolved_path and os.path.exists(resolved_path) else 'no'}",
                ]
            )
        if self._active_section == "font":
            text_items = self._font_text_items_from_value(entry.get("text", ""))
            if text_items:
                lines.extend(["", "Text Files:"])
                for candidate in text_items:
                    resolved = self._resolve_entry_path(self._active_section, "text", candidate)
                    exists = bool(resolved and os.path.exists(resolved))
                    lines.append(f"- {candidate} ({'ok' if exists else 'missing'})")
        return "\n".join(lines)

    def _clear_form(self):
        self._active_field_widgets = {}
        while self._form_layout.rowCount():
            self._form_layout.removeRow(0)

    # -- Button handlers -----------------------------------------------

    def _new_config(self):
        if not self._confirm_discard_changes():
            return
        self._sync_path_widgets_to_session()
        self._apply_paths_and_data(self._session.paths, make_empty_resource_config(), dirty=False)
        self._set_status("New resource config ready.")

    def _open_config_dialog(self):
        if not self._confirm_discard_changes():
            return
        start_dir = self._default_open_dir()
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Resource Config",
            start_dir,
            "Resource Config (*.json);;All files (*)",
        )
        if not path:
            return
        self._open_config_path(path)

    def _open_config_path(self, path: str):
        try:
            self._session.load_from_file(path)
        except Exception as exc:
            QMessageBox.warning(self, "Open Resource Config", str(exc))
            return
        self._apply_session_state(dirty=False)
        self._set_status(f"Opened {normalize_path(path)}.")

    def _scan_assets_directory_dialog(self):
        start_dir = self._session.paths.source_dir or self._default_open_dir()
        directory = QFileDialog.getExistingDirectory(self, "Scan Asset Folder", start_dir)
        if not directory:
            return
        self._scan_assets_from_directory(directory)

    def _import_asset_files_dialog(self):
        start_dir = self._session.paths.source_dir or self._default_open_dir()
        paths, _selected_filter = QFileDialog.getOpenFileNames(
            self,
            "Import Asset Files",
            start_dir,
            _supported_asset_file_filter(),
        )
        if not paths:
            return
        self._import_assets_from_files(paths)

    def _import_assets_from_files(self, file_paths):
        asset_paths, text_paths, skipped_paths = _classify_selected_asset_files(file_paths)
        if not asset_paths:
            QMessageBox.warning(
                self,
                "Import Asset Files",
                "Select at least one supported image, font, or video file.",
            )
            return

        previous_paths = GenerationPaths(
            config_path=self._session.paths.config_path,
            source_dir=self._session.paths.source_dir,
            workspace_dir=self._session.paths.workspace_dir,
            bin_output_dir=self._session.paths.bin_output_dir,
        )
        source_changed = False
        source_dir = normalize_path(self._session.paths.source_dir)
        copied_files = 0
        selected_support_files = [path for _section, path in asset_paths] + list(text_paths)
        import_root = _common_parent_directory(selected_support_files)

        all_inside_source_dir = bool(source_dir) and all(
            _is_subpath(path, source_dir) for path in selected_support_files
        )

        if not source_dir:
            self._apply_source_dir_change(import_root)
            source_dir = self._session.paths.source_dir
            source_changed = self._session.paths != previous_paths
        elif not all_inside_source_dir:
            answer = QMessageBox.question(
                self,
                "Import Asset Files",
                (
                    "Selected files are outside the current Source Dir.\n\n"
                    f"Yes: copy supported files into:\n{source_dir}\n\n"
                    f"No: switch Source Dir to:\n{import_root}\n\n"
                    "Cancel: keep the current config unchanged."
                ),
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.Yes,
            )
            if answer == QMessageBox.Cancel:
                return
            if answer == QMessageBox.No:
                self._apply_source_dir_change(import_root)
                source_dir = self._session.paths.source_dir
                source_changed = self._session.paths != previous_paths
            else:
                asset_paths, text_paths, copied_files = self._copy_supported_assets_into_source_dir(
                    import_root,
                    source_dir,
                    asset_paths,
                    text_paths,
                )

        entries_by_section = self._build_entries_from_asset_paths(asset_paths, text_paths, source_dir)
        added, updated = self._merge_discovered_entries(entries_by_section)
        if source_changed or added or updated:
            self._mark_dirty()
            self._refresh_path_fields()
            self._refresh_entry_table()
            self._update_merged_preview()
            self._update_raw_editor()

        imported_total = sum(len(items) for items in entries_by_section.values())
        if not imported_total and not source_changed:
            self._set_status("No supported assets were imported from the selected files.")
            return

        summary = [f"Imported {imported_total} assets"]
        if copied_files:
            summary.append(f"copied {copied_files} files")
        if added:
            summary.append(f"added {added}")
        if updated:
            summary.append(f"updated {updated}")
        if source_changed:
            summary.append("updated Source Dir")
        if skipped_paths:
            summary.append(f"ignored {len(skipped_paths)} unsupported files")
        self._set_status(", ".join(summary) + ".")

    def _scan_assets_from_directory(self, directory: str):
        import_root = normalize_path(directory)
        if not import_root or not os.path.isdir(import_root):
            QMessageBox.warning(self, "Scan Asset Folder", f"Folder does not exist:\n{directory}")
            return

        previous_paths = GenerationPaths(
            config_path=self._session.paths.config_path,
            source_dir=self._session.paths.source_dir,
            workspace_dir=self._session.paths.workspace_dir,
            bin_output_dir=self._session.paths.bin_output_dir,
        )
        source_changed = False
        source_dir = normalize_path(self._session.paths.source_dir)
        asset_paths: list[tuple[str, str]] = []
        text_paths: list[str] = []
        copied_files = 0

        if not source_dir:
            self._apply_source_dir_change(import_root)
            source_dir = self._session.paths.source_dir
            source_changed = self._session.paths != previous_paths
            asset_paths, text_paths = _discover_supported_assets(import_root)
        elif import_root == source_dir or _is_subpath(import_root, source_dir):
            asset_paths, text_paths = _discover_supported_assets(import_root)
        else:
            answer = QMessageBox.question(
                self,
                "Import Asset Folder",
                (
                    f"{import_root}\n\n"
                    f"Yes: copy supported assets into the current Source Dir:\n{source_dir}\n\n"
                    "No: switch Source Dir to this folder and scan in place."
                ),
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.Yes,
            )
            if answer == QMessageBox.Cancel:
                return
            if answer == QMessageBox.No:
                self._apply_source_dir_change(import_root)
                source_dir = self._session.paths.source_dir
                source_changed = self._session.paths != previous_paths
                asset_paths, text_paths = _discover_supported_assets(import_root)
            else:
                discovered_assets, discovered_texts = _discover_supported_assets(import_root)
                asset_paths, text_paths, copied_files = self._copy_supported_assets_into_source_dir(
                    import_root,
                    source_dir,
                    discovered_assets,
                    discovered_texts,
                )

        entries_by_section = self._build_entries_from_asset_paths(asset_paths, text_paths, source_dir)
        added, updated = self._merge_discovered_entries(entries_by_section)
        if source_changed or added or updated:
            self._mark_dirty()
            self._refresh_path_fields()
            self._refresh_entry_table()
            self._update_merged_preview()
            self._update_raw_editor()

        discovered_total = sum(len(items) for items in entries_by_section.values())
        if not discovered_total and not source_changed:
            self._set_status("No supported assets found in the selected folder.")
            return

        summary = [f"Imported {discovered_total} assets"]
        if copied_files:
            summary.append(f"copied {copied_files} files")
        if added:
            summary.append(f"added {added}")
        if updated:
            summary.append(f"updated {updated}")
        if source_changed:
            summary.append("updated Source Dir")
        self._set_status(", ".join(summary) + ".")

    def _open_generate_charset_helper(self):
        source_dir = self._session.paths.source_dir
        if not source_dir:
            QMessageBox.warning(
                self,
                "Generate Font Text",
                "Set Source Dir first, or scan an asset folder so Designer knows where to save the generated text file.",
            )
            return

        resource_type, source_name = self._charset_helper_context()
        dialog = _GenerateCharsetDialog(
            source_dir,
            initial_filename=_suggest_charset_filename_for_resource(resource_type, source_name),
            source_label=source_name if resource_type in {"font", "text"} else "",
            initial_preset_ids=_suggest_charset_presets_for_resource(resource_type, source_name),
            parent=self,
        )
        if dialog.exec_() != QDialog.Accepted:
            return

        filename = dialog.filename()
        target_path = os.path.join(source_dir, filename)
        if os.path.isfile(target_path):
            diff = dialog.overwrite_diff()
            reply = QMessageBox.question(
                self,
                "Overwrite Charset Resource",
                (
                    f"Overwrite '{filename}'?\n\n"
                    f"Existing chars: {diff.existing_count}\n"
                    f"New chars: {diff.new_count}\n"
                    f"Added: {diff.added_count}\n"
                    f"Removed: {diff.removed_count}"
                ),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(target_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(dialog.generated_text())

        assigned = self._assign_generated_text_to_font(filename)
        self._update_merged_preview()
        self._update_raw_editor()
        if assigned:
            self._set_status(f"Generated '{filename}' and linked it to a font entry.")
        else:
            self._set_status(f"Generated '{filename}'.")

    def _save_config(self):
        if not self._commit_raw_json_if_needed():
            return False
        self._sync_path_widgets_to_session()
        if not self._session.paths.config_path:
            return self._save_config_as()
        try:
            self._session.save_user_config()
        except Exception as exc:
            QMessageBox.warning(self, "Save Resource Config", str(exc))
            return False
        self._dirty = False
        self._capture_clean_snapshot()
        self._update_title()
        self._refresh_path_fields()
        self._set_status("Resource config saved.")
        return True

    def _save_config_as(self):
        if not self._commit_raw_json_if_needed():
            return False
        self._sync_path_widgets_to_session()
        start_dir = self._default_open_dir()
        default_name = self._session.paths.config_path or os.path.join(start_dir, APP_RESOURCE_CONFIG_FILENAME)
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Resource Config As",
            default_name,
            "Resource Config (*.json);;All files (*)",
        )
        if not path:
            return False
        try:
            previous_paths = GenerationPaths(
                config_path=self._session.paths.config_path,
                source_dir=self._session.paths.source_dir,
                workspace_dir=self._session.paths.workspace_dir,
                bin_output_dir=self._session.paths.bin_output_dir,
            )
            self._session.save_user_config(path)
            self._rebase_inferred_paths(previous_paths, path)
        except Exception as exc:
            QMessageBox.warning(self, "Save Resource Config", str(exc))
            return False
        self._dirty = False
        self._capture_clean_snapshot()
        self._refresh_path_fields()
        self._update_merged_preview()
        self._update_title()
        self._set_status(f"Saved {normalize_path(path)}.")
        return True

    def _generate_resources(self):
        if not self._commit_raw_json_if_needed():
            return
        self._sync_path_widgets_to_session()
        self._update_merged_preview()
        issues = self._session.validation_issues(for_generation=True)
        if any(issue.severity == "error" for issue in issues):
            self._log_validation_issues(issues, prefix="Generation blocked")
            self._bottom_tabs.setCurrentWidget(self._log_output)
            QMessageBox.warning(
                self,
                "Generate Resources",
                "\n".join(issue.message for issue in issues if issue.severity == "error"),
            )
            return

        self._append_log("Running resource generation...")
        result = self._session.run_generation()
        command_text = " ".join(result.command)
        if command_text:
            self._append_log(command_text)
        if result.stdout:
            self._append_log(result.stdout.rstrip())
        if result.stderr:
            self._append_log(result.stderr.rstrip())
        if result.issues:
            self._log_validation_issues(result.issues, prefix="Validation")
        if result.success:
            self._append_log("Resource generation completed successfully.")
            self._set_status("Resource generation completed.")
        else:
            self._append_log(f"Resource generation failed (rc={result.returncode}).")
            self._set_status("Resource generation failed.")
            QMessageBox.warning(
                self,
                "Generate Resources",
                result.stderr or result.stdout or "Resource generation failed.",
            )
        self._bottom_tabs.setCurrentWidget(self._log_output)

    def _add_entry(self):
        if not self._commit_raw_json_if_needed():
            return False
        index = self._session.add_entry(self._active_section, default_entry_for_section(self._active_section))
        self._active_entry_index = index
        self._mark_dirty()
        self._refresh_entry_table()
        self._update_merged_preview()
        self._update_raw_editor()
        self._set_status(f"Added new {_resource_kind_label(self._active_section)} entry.")
        return True

    def _remove_entry(self):
        if not self._commit_raw_json_if_needed():
            return False
        if self._active_entry_index < 0:
            return False
        entry = self._current_entry() or {}
        label = section_entry_label(self._active_section, entry, self._active_entry_index)
        section = self._active_section
        self._session.remove_entry(self._active_section, self._active_entry_index)
        self._active_entry_index = max(-1, self._active_entry_index - 1)
        self._mark_dirty()
        self._refresh_entry_table()
        self._update_merged_preview()
        self._update_raw_editor()
        self._set_status(f"Removed {_resource_kind_label(section)} '{label}'.")
        return True

    # -- Signals/field updates -----------------------------------------

    def _on_section_changed(self, row: int):
        if row < 0 or row >= self._section_list.count():
            return
        item = self._section_list.item(row)
        section = item.data(Qt.UserRole)
        if not section:
            return
        self._active_section = section
        self._active_entry_index = 0 if self._session.section_entries(section) else -1
        self._refresh_entry_table()

    def _on_entry_selection_changed(self):
        selected = self._entry_table.selectionModel().selectedRows()
        self._active_entry_index = selected[0].row() if selected else -1
        self._update_form()

    def _update_current_entry_field(
        self,
        field_name: str,
        value,
        *,
        normalize_font_text: bool = False,
        sync_widget_text: bool = False,
    ):
        entry = self._current_entry() or {}
        before = str(entry.get(field_name, "") or "")
        next_value = value
        if normalize_font_text and self._active_section == "font" and field_name == "text":
            next_value = self._normalize_font_text_value(value)

        self._session.update_entry_value(self._active_section, self._active_entry_index, field_name, next_value)
        updated_entry = self._current_entry() or {}
        after = str(updated_entry.get(field_name, "") or "")
        if sync_widget_text:
            self._sync_active_field_widget(field_name, after)
        if before == after:
            return
        self._mark_dirty()
        current_entry = self._current_entry()
        if current_entry is not None:
            self._entry_summary.setPlainText(self._entry_summary_text(current_entry))
        self._refresh_current_table_row()
        self._update_merged_preview()
        self._update_raw_editor()

    def _commit_font_text_field(self, field_name: str, widget: QLineEdit):
        self._update_current_entry_field(field_name, widget.text(), normalize_font_text=True, sync_widget_text=True)

    def _sync_active_field_widget(self, field_name: str, value: str):
        widget = self._active_field_widgets.get(field_name)
        if isinstance(widget, QLineEdit):
            if widget.text() == value:
                return
            with QSignalBlocker(widget):
                widget.setText(value)

    def _on_raw_text_changed(self):
        if self._syncing_raw:
            return
        self._raw_dirty = True
        self._dirty = True
        self._update_title()

    def _on_bottom_tab_changed(self, index: int):
        raw_index = self._bottom_tabs.indexOf(self._raw_editor)
        if self._last_tab_index == raw_index and index != raw_index:
            if not self._commit_raw_json_if_needed():
                with QSignalBlocker(self._bottom_tabs):
                    self._bottom_tabs.setCurrentIndex(raw_index)
                return
        self._last_tab_index = index
        if index == raw_index:
            self._update_raw_editor(force=not self._raw_dirty)

    # -- Raw/preview sync ----------------------------------------------

    def _commit_raw_json_if_needed(self) -> bool:
        if not self._raw_dirty:
            return True
        try:
            self._session.apply_raw_json_text(self._raw_editor.toPlainText())
        except Exception as exc:
            QMessageBox.warning(self, "Raw JSON", f"Invalid resource config JSON:\n{exc}")
            return False
        self._raw_dirty = False
        self._refresh_entry_table()
        self._update_merged_preview()
        self._set_status("Applied raw JSON changes.")
        return True

    def _update_raw_editor(self, *, force: bool = False):
        if self._raw_dirty and not force:
            return
        self._syncing_raw = True
        self._raw_editor.setPlainText(self._session.to_user_json_text())
        self._syncing_raw = False
        if force:
            self._raw_dirty = False

    def _update_merged_preview(self):
        self._merged_preview.setPlainText(self._session.merged_json_text())
        self._simple_preview.setPlainText(self._session.merged_json_text())
        if self._current_entry() is not None:
            self._entry_summary.setPlainText(self._entry_summary_text(self._current_entry()))

    def _refresh_simple_page(self):
        counts = {section: len(self._session.section_entries(section)) for section in KNOWN_RESOURCE_SECTIONS}
        self._simple_image_count.setText(f"Images: {counts['img']}")
        self._simple_font_count.setText(f"Fonts: {counts['font']}")
        self._simple_mp4_count.setText(f"MP4: {counts['mp4']}")

        section_filter = str(self._simple_asset_type_filter.currentData() or "all")
        search_text = str(self._simple_asset_search_edit.text() or "").strip().lower()
        has_filters = section_filter != "all" or bool(search_text)
        total_assets = sum(counts.values())
        attention_count = 0
        rows = []
        for section in KNOWN_RESOURCE_SECTIONS:
            for index, entry in enumerate(self._session.section_entries(section)):
                if not isinstance(entry, dict):
                    continue
                type_label = RESOURCE_SECTION_SPECS[section].label
                name_label = section_entry_label(section, entry, index)
                file_label = str(entry.get("file", "") or "")
                attention_messages = self._simple_asset_attention_messages(section, entry, file_label=file_label)
                recommended_fixes = self._simple_asset_recommended_fixes(section, entry, file_label=file_label)
                type_display_label = f"! {type_label}" if attention_messages else type_label
                if attention_messages:
                    attention_count += 1
                if not self._simple_asset_matches_filter(section_filter, section, entry, file_label=file_label):
                    continue
                detail = self._simple_asset_detail_text(section, entry)
                search_blob = self._simple_asset_search_blob(
                    section_filter,
                    type_label=type_label,
                    name_label=name_label,
                    file_label=file_label,
                    detail_label=detail,
                    attention_messages=attention_messages,
                    recommended_fixes=recommended_fixes,
                )
                if search_text and search_text not in search_blob:
                    continue
                rows.append(
                    {
                        "section": section,
                        "index": index,
                        "entry": entry,
                        "type_label": type_label,
                        "type_display_label": type_display_label,
                        "name_label": name_label,
                        "file_label": file_label,
                        "detail_label": detail,
                        "attention_messages": attention_messages,
                        "recommended_fixes": recommended_fixes,
                    }
                )

        if self._simple_asset_sort_column >= 0:
            rows.sort(key=self._simple_asset_row_sort_key, reverse=self._simple_asset_sort_descending)

        self._update_simple_attention_count(attention_count)
        self._simple_row_map = [(row["section"], row["index"]) for row in rows]
        self._simple_asset_result_label.setText(f"Showing {len(rows)} of {total_assets} assets")
        selected_row = -1
        for row, (section, index) in enumerate(self._simple_row_map):
            if section == self._active_section and index == self._active_entry_index:
                selected_row = row
                break
        if selected_row < 0 and rows and has_filters:
            selected_row = 0
        with QSignalBlocker(self._simple_asset_table):
            self._simple_asset_table.setRowCount(len(rows))
            for row, payload in enumerate(rows):
                if payload["attention_messages"]:
                    tooltip_lines = list(payload["attention_messages"])
                    tooltip_lines.extend(f"Fix: {item}" for item in payload["recommended_fixes"])
                    tooltip_text = "\n".join(item for item in tooltip_lines if item)
                else:
                    tooltip_text = payload["detail_label"] or payload["file_label"]
                for column, value in enumerate(
                    (
                        payload["type_display_label"],
                        payload["name_label"],
                        payload["file_label"],
                        payload["detail_label"],
                    )
                ):
                    item = QTableWidgetItem(value)
                    if tooltip_text:
                        item.setToolTip(tooltip_text)
                    self._style_simple_asset_table_item(
                        item,
                        has_attention=bool(payload["attention_messages"]),
                        column=column,
                    )
                    self._simple_asset_table.setItem(row, column, item)
            if 0 <= selected_row < len(rows):
                self._simple_asset_table.selectRow(selected_row)
                selected_section, selected_index = self._simple_row_map[selected_row]
                self._active_section = selected_section
                self._active_entry_index = selected_index
            else:
                self._simple_asset_table.clearSelection()
        self._update_simple_asset_empty_state(total_assets=total_assets, visible_assets=len(rows), has_filters=has_filters)
        self._update_simple_action_button_states()
        self._update_simple_asset_preview()

    def _simple_asset_detail_text(self, section: str, entry: dict) -> str:
        if section == "font":
            parts = []
            pixel_size = str(entry.get("pixelsize", "") or "").strip()
            font_bit_size = str(entry.get("fontbitsize", "") or "").strip()
            weight = str(entry.get("weight", "") or "").strip()
            text_items = self._font_text_items_from_value(entry.get("text", ""))
            if pixel_size:
                parts.append(f"{pixel_size}px")
            if font_bit_size:
                parts.append(f"{font_bit_size}-bit")
            if weight:
                parts.append(f"w{weight}")
            if len(text_items) == 1:
                parts.append(text_items[0])
            elif len(text_items) > 1:
                parts.append(f"{len(text_items)} text files")
            return " | ".join(parts)

        if section == "mp4":
            parts = []
            fps = str(entry.get("fps", "") or "").strip()
            width = str(entry.get("width", "") or "").strip()
            height = str(entry.get("height", "") or "").strip()
            format_name = str(entry.get("format", "") or "").strip()
            alpha = str(entry.get("alpha", "") or "").strip()
            if fps:
                parts.append(f"{fps}fps")
            if width or height:
                parts.append(f"{width or '?'}x{height or '?'}")
            if format_name:
                parts.append(format_name)
            if alpha:
                parts.append(f"a{alpha}")
            return " | ".join(parts)

        if section == "img":
            parts = []
            format_name = str(entry.get("format", "") or "").strip()
            alpha = str(entry.get("alpha", "") or "").strip()
            dim = str(entry.get("dim", "") or "").strip()
            compress = str(entry.get("compress", "") or "").strip()
            if format_name:
                parts.append(format_name)
            if alpha:
                parts.append(f"a{alpha}")
            if dim:
                parts.append(dim)
            if compress and compress != "none":
                parts.append(compress)
            return " | ".join(parts)

        return ""

    def _on_mode_changed(self, _index: int):
        self._set_ui_mode(self._mode_combo.currentData() or "simple")

    def _set_ui_mode(self, mode: str):
        normalized_mode = "professional" if mode == "professional" else "simple"
        self._ui_mode = normalized_mode
        target_index = 1 if normalized_mode == "professional" else 0
        self._workspace_stack.setCurrentIndex(target_index)
        combo_index = 1 if normalized_mode == "professional" else 0
        if self._mode_combo.currentIndex() != combo_index:
            with QSignalBlocker(self._mode_combo):
                self._mode_combo.setCurrentIndex(combo_index)
        self._remember_view_state()

    def _open_simple_selection_in_professional_mode(self, item):
        row = item.row() if item is not None else -1
        if not (0 <= row < len(self._simple_row_map)):
            return
        section, index = self._simple_row_map[row]
        self._active_section = section
        self._active_entry_index = index
        self._refresh_section_selection()
        self._refresh_entry_table()
        self._set_ui_mode("professional")

    def _open_current_simple_selection_in_professional_mode(self):
        section, index, entry = self._selected_simple_asset_context()
        if section and entry is not None:
            self._active_section = section
            self._active_entry_index = index
            self._refresh_section_selection()
            self._refresh_entry_table()
        self._set_ui_mode("professional")

    def _activate_selected_simple_asset(self, _item=None):
        self._trigger_selected_simple_asset_primary_action()

    def _trigger_selected_simple_asset_primary_action(self):
        section, index, entry = self._selected_simple_asset_context()
        if entry is None or not section:
            return
        self._active_section = section
        self._active_entry_index = index
        file_name = str(entry.get("file", "") or "").strip()
        action = self._simple_asset_primary_action(section, entry, file_label=file_name)
        if action is None:
            return
        _action_text, callback = action
        callback()

    def _selected_simple_asset_context(self):
        selected = self._simple_asset_table.selectionModel().selectedRows() if self._simple_asset_table.selectionModel() else []
        row = selected[0].row() if selected else -1
        if not (0 <= row < len(self._simple_row_map)):
            return None, -1, None
        section, index = self._simple_row_map[row]
        entries = self._session.section_entries(section)
        if not (0 <= index < len(entries)):
            return section, index, None
        entry = entries[index]
        return section, index, entry if isinstance(entry, dict) else None

    def _on_simple_asset_selection_changed(self):
        section, index, _entry = self._selected_simple_asset_context()
        if section:
            self._active_section = section
            self._active_entry_index = index
        self._update_simple_action_button_states()
        self._update_simple_asset_preview()

    def _update_simple_action_button_states(self):
        section, _index, entry = self._selected_simple_asset_context()
        has_selection = bool(section and entry is not None)
        any_selection_buttons = (
            self._edit_asset_button,
            self._open_asset_folder_button,
            self._duplicate_simple_asset_button,
            self._remove_simple_asset_button,
            self._open_professional_button,
        )
        image_buttons = (
            self._resize_image_button,
            self._add_border_image_button,
            self._add_background_image_button,
            self._round_corners_image_button,
            self._adjust_opacity_image_button,
            self._rotate_image_button,
            self._flip_image_button,
            self._crop_image_button,
        )
        font_buttons = (self._open_font_text_button,)
        video_buttons = (self._detect_video_info_button,)

        for button in any_selection_buttons:
            button.setEnabled(has_selection)
        for button in image_buttons:
            button.setEnabled(has_selection and section == "img")
        for button in font_buttons:
            button.setEnabled(has_selection and section == "font")
        for button in video_buttons:
            button.setEnabled(has_selection and section == "mp4")

    def _open_quick_preview_board(self):
        if not self._commit_raw_json_if_needed():
            return
        dialog = self._build_quick_preview_board_dialog()
        if dialog is None:
            QMessageBox.information(self, "Quick Preview Board", "Import or create some assets first.")
            return
        self._set_status(f"Opened preview board for {dialog._cards_layout.count()} assets.")
        dialog.exec_()

    def _export_quick_preview_board_dialog(self):
        if not self._commit_raw_json_if_needed():
            return

        start_dir = self._session.paths.source_dir or self._default_open_dir()
        suggested_path = normalize_path(os.path.join(start_dir, "resource_preview_board.png"))
        path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Preview Board",
            suggested_path,
            "PNG Image (*.png);;All files (*)",
        )
        if not path:
            return
        self._export_quick_preview_board_image(path)

    def _build_quick_preview_board_dialog(self):
        cards = []
        for section in KNOWN_RESOURCE_SECTIONS:
            for index, entry in enumerate(self._session.section_entries(section)):
                if not isinstance(entry, dict):
                    continue
                cards.append(self._build_quick_preview_card(section, index, entry))
        if not cards:
            return None
        return _QuickPreviewBoardDialog(cards, total_assets=len(cards), parent=self)

    def _export_quick_preview_board_image(self, path: str) -> bool:
        image = self._render_quick_preview_board_image()
        if image is None:
            self._set_status("No assets available for preview export.")
            return False

        target_path = normalize_path(path)
        if not target_path.lower().endswith(".png"):
            target_path += ".png"
        target_dir = os.path.dirname(target_path)
        if target_dir:
            os.makedirs(target_dir, exist_ok=True)
        if not image.save(target_path, "PNG"):
            QMessageBox.warning(self, "Export Preview Board", f"Failed to save preview board image:\n{target_path}")
            return False

        self._set_status(f"Exported preview board to '{target_path}'.")
        return True

    def _render_quick_preview_board_image(self) -> QImage | None:
        payloads = []
        for section in KNOWN_RESOURCE_SECTIONS:
            for index, entry in enumerate(self._session.section_entries(section)):
                if not isinstance(entry, dict):
                    continue
                payloads.append(self._asset_preview_payload(section, index, entry))
        if not payloads:
            return None

        columns = 3
        gap = 18
        page_margin = 24
        card_width = 360
        card_height = 320
        header_height = 56
        rows = max(1, int(math.ceil(len(payloads) / float(columns))))
        image_width = (page_margin * 2) + (card_width * columns) + (gap * (columns - 1))
        image_height = (page_margin * 2) + header_height + (card_height * rows) + (gap * max(rows - 1, 0))

        image = QImage(image_width, image_height, QImage.Format_ARGB32)
        image.fill(QColor(246, 244, 238))

        painter = QPainter(image)
        try:
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

            title_font = QFont()
            title_font.setPointSize(18)
            title_font.setBold(True)
            painter.setFont(title_font)
            painter.setPen(QColor(39, 39, 39))
            painter.drawText(page_margin, page_margin + 28, "Quick Preview Board")

            subtitle_font = QFont()
            subtitle_font.setPointSize(10)
            painter.setFont(subtitle_font)
            painter.setPen(QColor(96, 96, 96))
            painter.drawText(
                page_margin,
                page_margin + 48,
                f"Assets: {len(payloads)}  Source Dir: {self._session.paths.source_dir or '(unset)'}",
            )

            for card_index, payload in enumerate(payloads):
                row = card_index // columns
                column = card_index % columns
                x = page_margin + (column * (card_width + gap))
                y = page_margin + header_height + (row * (card_height + gap))
                self._paint_quick_preview_card(
                    painter,
                    x,
                    y,
                    card_width,
                    card_height,
                    payload,
                )
        finally:
            painter.end()
        return image

    def _build_quick_preview_card(self, section: str, index: int, entry: dict) -> QGroupBox:
        payload = self._asset_preview_payload(section, index, entry)
        card = QGroupBox(payload["title"])
        card.setObjectName("quick_preview_card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        preview_label = QLabel("")
        preview_label.setAlignment(Qt.AlignCenter)
        preview_label.setMinimumHeight(150)
        preview_label.setWordWrap(True)
        self._apply_preview_payload(preview_label, payload, max_width=260, max_height=150)
        layout.addWidget(preview_label)

        meta_label = QLabel(payload["meta_text"])
        meta_label.setObjectName("quick_preview_meta")
        meta_label.setWordWrap(True)
        meta_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(meta_label)
        return card

    def _paint_quick_preview_card(self, painter: QPainter, x: int, y: int, width: int, height: int, payload: dict):
        painter.save()
        try:
            painter.setPen(QPen(QColor(214, 208, 196), 1))
            painter.setBrush(QColor(255, 252, 247))
            painter.drawRoundedRect(x, y, width, height, 12, 12)

            title_font = QFont()
            title_font.setPointSize(11)
            title_font.setBold(True)
            painter.setFont(title_font)
            painter.setPen(QColor(45, 45, 45))
            title_rect = painter.boundingRect(x + 14, y + 12, width - 28, 40, Qt.TextWordWrap, payload["title"])
            painter.drawText(title_rect, Qt.TextWordWrap, payload["title"])

            preview_rect_top = title_rect.bottom() + 12
            preview_rect_height = 138
            preview_rect = (x + 14, preview_rect_top, width - 28, preview_rect_height)
            painter.setPen(QPen(QColor(226, 220, 210), 1))
            painter.setBrush(QColor(248, 246, 241))
            painter.drawRoundedRect(preview_rect[0], preview_rect[1], preview_rect[2], preview_rect[3], 10, 10)

            pixmap = payload.get("pixmap")
            if pixmap is not None and not pixmap.isNull():
                scaled = pixmap.scaled(preview_rect[2] - 16, preview_rect[3] - 16, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                px = preview_rect[0] + max(0, (preview_rect[2] - scaled.width()) // 2)
                py = preview_rect[1] + max(0, (preview_rect[3] - scaled.height()) // 2)
                painter.drawPixmap(px, py, scaled)
            else:
                painter.setPen(QColor(106, 106, 106))
                preview_font = QFont()
                preview_font.setPointSize(9)
                painter.setFont(preview_font)
                painter.drawText(
                    preview_rect[0] + 10,
                    preview_rect[1] + 10,
                    preview_rect[2] - 20,
                    preview_rect[3] - 20,
                    Qt.AlignCenter | Qt.TextWordWrap,
                    str(payload.get("preview_text", "") or ""),
                )

            meta_font = QFont()
            meta_font.setPointSize(8)
            painter.setFont(meta_font)
            painter.setPen(QColor(78, 78, 78))
            meta_top = preview_rect[1] + preview_rect[3] + 10
            painter.drawText(
                x + 14,
                meta_top,
                width - 28,
                (y + height - 12) - meta_top,
                Qt.TextWordWrap,
                payload["meta_text"],
            )
        finally:
            painter.restore()

    def _update_simple_asset_preview(self):
        section, index, entry = self._selected_simple_asset_context()
        self._simple_asset_preview_label.setPixmap(QPixmap())
        if entry is None or not section:
            self._simple_asset_preview_title.setText("No asset selected.")
            self._simple_asset_preview_label.setText("Select an image, font, or video entry to inspect it here.")
            self._simple_asset_meta.setPlainText("")
            self._simple_asset_primary_action_button.hide()
            self._simple_asset_primary_action_button.setEnabled(False)
            self._simple_asset_more_actions_button.hide()
            self._simple_asset_more_actions_button.setEnabled(False)
            return

        payload = self._asset_preview_payload(section, index, entry)
        self._simple_asset_preview_title.setText(payload["title"])
        self._apply_preview_payload(self._simple_asset_preview_label, payload, max_width=360, max_height=220)
        self._simple_asset_meta.setPlainText(payload["meta_text"])
        file_name = str(entry.get("file", "") or "").strip()
        action = self._simple_asset_primary_action(section, entry, file_label=file_name)
        if action is None:
            self._simple_asset_primary_action_button.hide()
            self._simple_asset_primary_action_button.setEnabled(False)
        else:
            action_text, _callback = action
            self._simple_asset_primary_action_button.setText(action_text)
            self._simple_asset_primary_action_button.setToolTip(action_text)
            self._simple_asset_primary_action_button.setEnabled(True)
            self._simple_asset_primary_action_button.show()
        self._simple_asset_more_actions_button.setToolTip("Open more actions for the selected asset.")
        self._simple_asset_more_actions_button.setEnabled(True)
        self._simple_asset_more_actions_button.show()

    def _asset_preview_payload(self, section: str, index: int, entry: dict) -> dict:
        file_name = str(entry.get("file", "") or "").strip()
        resolved_path = self._resolve_entry_path(section, "file", file_name)
        exists = bool(resolved_path and os.path.exists(resolved_path))
        label = section_entry_label(section, entry, index)
        title = f"{RESOURCE_SECTION_SPECS[section].label}: {label}"

        meta_lines = []
        attention_messages = self._simple_asset_attention_messages(section, entry, file_label=file_name)
        if attention_messages:
            meta_lines.append("Attention: " + " | ".join(attention_messages))
            recommended_fixes = self._simple_asset_recommended_fixes(section, entry, file_label=file_name)
            if recommended_fixes:
                meta_lines.append("Suggested Fix: " + " | ".join(recommended_fixes))
        meta_lines.extend(
            [
                f"File: {file_name or '(empty)'}",
                f"Resolved: {resolved_path or '(unresolved)'}",
                f"Exists: {'yes' if exists else 'no'}",
            ]
        )
        if section == "font":
            meta_lines.append(f"Text: {str(entry.get('text', '') or '(none)')}")
            meta_lines.append(f"Pixel Size: {self._font_preview_pixel_size(entry)}")
            meta_lines.append(f"Bit Size: {self._font_preview_bit_size(entry)}")
            if self._font_preview_weight(entry) is not None:
                meta_lines.append(f"Weight: {self._font_preview_weight(entry)}")
        if section == "mp4":
            meta_lines.append(
                "Video: "
                + " ".join(
                    part
                    for part in (
                        f"{entry.get('fps', '')}fps" if str(entry.get("fps", "") or "").strip() else "",
                        f"{entry.get('width', '')}x{entry.get('height', '')}"
                        if str(entry.get("width", "") or "").strip() or str(entry.get("height", "") or "").strip()
                        else "",
                    )
                    if part
                ).strip()
            )

        preview_pixmap = None
        preview_text = ""
        if section == "img" and exists:
            pixmap = QPixmap(resolved_path)
            if not pixmap.isNull():
                preview_pixmap = pixmap
                meta_lines.append(f"Image Size: {pixmap.width()} x {pixmap.height()}")
            else:
                preview_text = "Image file exists but Qt could not decode it."
        elif section == "font" and exists:
            sample_text, preview_source = self._font_preview_sample(entry)
            meta_lines.append(f"Preview Text: {sample_text}")
            meta_lines.append(f"Preview Source: {preview_source}")
            pixmap = self._build_font_preview_pixmap(resolved_path, sample_text, entry=entry)
            if pixmap is not None and not pixmap.isNull():
                preview_pixmap = pixmap
            else:
                preview_text = "Font file exists but quick preview could not render it."
        elif exists:
            kind = "font" if section == "font" else "video"
            preview_text = (
                f"External preview is not embedded for this {kind}.\n"
                "Use 'Edit / Open Asset...' to inspect it in the system app."
            )
        else:
            preview_text = "File is missing. Fix the path or re-import the asset."

        return {
            "title": title,
            "meta_text": "\n".join(meta_lines).strip(),
            "pixmap": preview_pixmap,
            "preview_text": preview_text,
        }

    def _apply_preview_payload(self, label: QLabel, payload: dict, *, max_width: int, max_height: int):
        label.setPixmap(QPixmap())
        pixmap = payload.get("pixmap")
        if pixmap is not None and not pixmap.isNull():
            scaled = pixmap.scaled(max_width, max_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            label.setPixmap(scaled)
            label.setText("")
            return
        label.setText(str(payload.get("preview_text", "") or ""))

    def _font_preview_sample(self, entry: dict) -> tuple[str, str]:
        preview_sources = []
        preview_chunks = []
        for item, resolved in self._font_text_targets(entry):
            if not resolved or not os.path.isfile(resolved):
                continue
            try:
                with open(resolved, "r", encoding="utf-8") as handle:
                    preview_chunks.append(self._decode_font_preview_entities(handle.read()))
            except OSError:
                continue
            preview_sources.append(item)
        if preview_chunks:
            sample = self._build_font_preview_sample_text("\n".join(preview_chunks))
            if sample:
                return sample, ", ".join(preview_sources)
        return _default_quick_font_preview_text(), "built-in sample"

    def _build_font_preview_sample_text(self, raw_text: str) -> str:
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        if lines and all(len(line) == 1 for line in lines[: min(len(lines), 24)]):
            sample = "".join(lines[:24])
        else:
            sample = " ".join(raw_text.split())
        sample = sample.strip()
        if len(sample) > 48:
            sample = sample[:45].rstrip() + "..."
        return sample

    def _decode_font_preview_entities(self, raw_text: str) -> str:
        return re.sub(r"&#x([0-9A-Fa-f]+);", lambda match: chr(int(match.group(1), 16)), str(raw_text or ""))

    def _font_preview_pixel_size(self, entry: dict | None) -> int:
        raw_value = str((entry or {}).get("pixelsize", "") or "").strip()
        try:
            parsed = int(raw_value)
        except Exception:
            parsed = 16
        return max(parsed, 4)

    def _font_preview_bit_size(self, entry: dict | None) -> int:
        raw_value = str((entry or {}).get("fontbitsize", "") or "").strip()
        try:
            parsed = int(raw_value)
        except Exception:
            parsed = 4
        return parsed if parsed in {1, 2, 4, 8} else 4

    def _font_preview_weight(self, entry: dict | None) -> int | None:
        raw_value = str((entry or {}).get("weight", "") or "").strip()
        if not raw_value:
            return None
        try:
            return int(raw_value)
        except Exception:
            return None

    def _build_font_preview_pixmap(self, font_path: str, sample_text: str, *, entry: dict | None = None) -> QPixmap | None:
        image = render_font_preview_image(
            sdk_root=self._session.sdk_root,
            font_path=font_path,
            sample_text=sample_text,
            pixel_size=self._font_preview_pixel_size(entry),
            font_bit_size=self._font_preview_bit_size(entry),
            weight=self._font_preview_weight(entry),
        )
        if image is None:
            return None
        return _pil_image_to_qpixmap(image)

    def _open_selected_asset_in_external_editor(self):
        section, index, entry = self._selected_simple_asset_context()
        if entry is None:
            QMessageBox.warning(self, "Open Asset", "Select an asset in Simple mode first.")
            return
        file_name = str(entry.get("file", "") or "").strip()
        resolved_path = self._resolve_entry_path(section or "", "file", file_name)
        if not resolved_path or not os.path.exists(resolved_path):
            QMessageBox.warning(self, "Open Asset", f"Asset file does not exist:\n{resolved_path or file_name}")
            return
        self._active_section = section or self._active_section
        self._active_entry_index = index
        self._update_simple_asset_preview()
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(resolved_path)):
            QMessageBox.warning(self, "Open Asset", f"Failed to open asset with the system editor:\n{resolved_path}")

    def _open_selected_asset_folder(self):
        section, index, entry = self._selected_simple_asset_context()
        if entry is None:
            QMessageBox.warning(self, "Open Asset Folder", "Select an asset in Simple mode first.")
            return
        file_name = str(entry.get("file", "") or "").strip()
        resolved_path = self._resolve_entry_path(section or "", "file", file_name)
        target_dir = self._simple_asset_target_folder(section or "", file_label=file_name)
        if not target_dir:
            QMessageBox.warning(self, "Open Asset Folder", f"Asset folder could not be resolved:\n{resolved_path or file_name}")
            return
        self._active_section = section or self._active_section
        self._active_entry_index = index
        self._update_simple_asset_preview()
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(target_dir)):
            QMessageBox.warning(self, "Open Asset Folder", f"Failed to open asset folder:\n{target_dir}")
            return
        self._set_status(f"Opened asset folder '{target_dir}'.")

    def _copy_selected_simple_asset_name(self):
        section, index, entry = self._selected_simple_asset_context()
        if entry is None or not section:
            QMessageBox.warning(self, "Copy Resource Name", "Select an asset in Simple mode first.")
            return
        name = section_entry_label(section, entry, index)
        QApplication.clipboard().setText(name)
        self._set_status(f"Copied resource name '{name}'.")

    def _copy_selected_simple_asset_relative_path(self):
        section, _index, entry = self._selected_simple_asset_context()
        if entry is None or not section:
            QMessageBox.warning(self, "Copy Asset Path", "Select an asset in Simple mode first.")
            return
        file_name = str(entry.get("file", "") or "").strip()
        if not file_name:
            QMessageBox.warning(self, "Copy Asset Path", "The selected asset does not have a file path.")
            return
        QApplication.clipboard().setText(file_name)
        self._set_status(f"Copied asset path '{file_name}'.")

    def _copy_selected_simple_asset_absolute_path(self):
        section, _index, entry = self._selected_simple_asset_context()
        if entry is None or not section:
            QMessageBox.warning(self, "Copy Full Path", "Select an asset in Simple mode first.")
            return
        file_name = str(entry.get("file", "") or "").strip()
        resolved_path = self._resolve_entry_path(section, "file", file_name)
        if not resolved_path:
            QMessageBox.warning(self, "Copy Full Path", f"Asset path could not be resolved:\n{file_name}")
            return
        QApplication.clipboard().setText(resolved_path)
        if os.path.exists(resolved_path):
            self._set_status(f"Copied full asset path '{resolved_path}'.")
        else:
            self._set_status(f"Copied expected full asset path '{resolved_path}'.")

    def _duplicate_selected_simple_asset(self):
        section, index, entry = self._selected_simple_asset_context()
        if entry is None or not section:
            QMessageBox.warning(self, "Duplicate Asset", "Select an asset in Simple mode first.")
            return

        entries = self._session.section_entries(section)
        duplicate = copy.deepcopy(entry if isinstance(entry, dict) else {})
        duplicate["name"] = _duplicated_resource_name(section, duplicate, entries)
        insert_index = max(index + 1, 0)
        entries.insert(insert_index, duplicate)

        self._active_section = section
        self._active_entry_index = insert_index
        self._mark_dirty()
        self._refresh_entry_table()
        self._update_merged_preview()
        self._update_raw_editor()
        self._set_status(f"Duplicated {_resource_kind_label(section)} '{duplicate['name']}'.")

    def _remove_selected_simple_asset(self):
        section, index, entry = self._selected_simple_asset_context()
        if entry is None or not section:
            QMessageBox.warning(self, "Remove Asset", "Select an asset in Simple mode first.")
            return
        label = section_entry_label(section, entry, index)
        answer = QMessageBox.question(
            self,
            "Remove Asset",
            f"Remove {_resource_kind_label(section)} '{label}' from the config?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self._active_section = section
        self._active_entry_index = index
        self._remove_entry()

    def _detect_selected_video_metadata(self):
        section, index, entry = self._selected_simple_asset_context()
        if entry is None or section != "mp4":
            QMessageBox.warning(self, "Detect Video Info", "Select a video asset in Simple mode first.")
            return
        file_name = str(entry.get("file", "") or "").strip()
        resolved_path = self._resolve_entry_path("mp4", "file", file_name)
        if not resolved_path or not os.path.isfile(resolved_path):
            QMessageBox.warning(self, "Detect Video Info", f"Video file does not exist:\n{resolved_path or file_name}")
            return

        changed, metadata = self._sync_video_metadata(index, entry, overwrite_existing=True)
        if not metadata:
            QMessageBox.warning(
                self,
                "Detect Video Info",
                "Could not read video width, height, and fps. Make sure ffprobe is available in PATH.",
            )
            return

        self._active_section = "mp4"
        self._active_entry_index = index
        if changed:
            self._mark_dirty()
            self._refresh_entry_table()
            self._update_merged_preview()
            self._update_raw_editor()
            self._set_status(
                f"Updated video metadata for '{section_entry_label('mp4', self._current_entry() or entry, index)}' "
                f"({metadata.get('fps', 0)}fps {metadata.get('width', 0)}x{metadata.get('height', 0)})."
            )
            return

        self._refresh_simple_page()
        self._set_status(f"Video metadata already up to date for '{section_entry_label('mp4', entry, index)}'.")

    def _pack_assets_into_source_dir(self):
        if not self._commit_raw_json_if_needed():
            return

        source_dir = normalize_path(self._session.paths.source_dir)
        if not source_dir:
            QMessageBox.warning(
                self,
                "Pack Into Source Dir",
                "Set Source Dir first so Designer knows where to copy external assets.",
            )
            return

        copied_files = 0
        updated_links = 0

        for section in KNOWN_RESOURCE_SECTIONS:
            for index, entry in enumerate(self._session.section_entries(section)):
                if not isinstance(entry, dict):
                    continue

                file_value = str(entry.get("file", "") or "").strip()
                if file_value:
                    resolved_file = self._resolve_entry_path(section, "file", file_value)
                    if resolved_file and os.path.isfile(resolved_file) and not _is_subpath(resolved_file, source_dir):
                        stored_file, copied = _copy_file_into_source_dir(resolved_file, source_dir)
                        if stored_file and stored_file != file_value:
                            self._session.update_entry_value(section, index, "file", stored_file)
                            updated_links += 1
                        if copied:
                            copied_files += 1

                if section != "font":
                    continue

                text_items = self._font_text_items_from_value(entry.get("text", ""))
                if not text_items:
                    continue

                rewritten_items = []
                field_changed = False
                for item in text_items:
                    resolved_text = self._resolve_entry_path("font", "text", item)
                    if not resolved_text or not os.path.isfile(resolved_text) or _is_subpath(resolved_text, source_dir):
                        rewritten_items.append(item)
                        continue

                    stored_text, copied = _copy_file_into_source_dir(resolved_text, source_dir)
                    rewritten_items.append(stored_text or item)
                    if copied:
                        copied_files += 1
                    if stored_text and stored_text != item:
                        field_changed = True

                if field_changed:
                    self._session.update_entry_value("font", index, "text", ",".join(rewritten_items))
                    updated_links += 1

        if not copied_files and not updated_links:
            self._set_status("All asset files already live inside Source Dir.")
            return

        self._mark_dirty()
        self._refresh_entry_table()
        self._update_merged_preview()
        self._update_raw_editor()
        self._set_status(f"Packed {copied_files} files into Source Dir, updated {updated_links} links.")

    def _organize_assets_into_standard_folders(self):
        if not self._commit_raw_json_if_needed():
            return

        source_dir = normalize_path(self._session.paths.source_dir)
        if not source_dir:
            QMessageBox.warning(
                self,
                "Organize Folders",
                "Set Source Dir first so Designer knows which asset files should be reorganized.",
            )
            return

        candidate_paths: set[str] = set()
        for section, target_folder in _STANDARD_SOURCE_DIR_FOLDERS.items():
            for entry in self._session.section_entries(section):
                if not isinstance(entry, dict):
                    continue

                file_value = str(entry.get("file", "") or "").strip()
                resolved_file = _organized_source_dir_candidate(
                    file_value,
                    target_folder,
                    source_dir,
                    skip_generated=section == "img",
                )
                if resolved_file:
                    candidate_paths.add(resolved_file)

                if section != "font":
                    continue
                for item in [candidate.strip() for candidate in str(entry.get("text", "") or "").split(",") if candidate.strip()]:
                    resolved_text = _organized_source_dir_candidate(item, target_folder, source_dir)
                    if resolved_text:
                        candidate_paths.add(resolved_text)

        if not candidate_paths:
            self._set_status("Assets already use standard source folders.")
            return

        answer = QMessageBox.question(
            self,
            "Organize Folders",
            f"Move {len(candidate_paths)} linked files into standard folders under Source Dir?\n\n"
            "images/\nfonts/\nvideos/",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if answer != QMessageBox.Yes:
            return

        relocated_paths: dict[str, str] = {}
        moved_files = 0
        updated_links = 0

        for section, target_folder in _STANDARD_SOURCE_DIR_FOLDERS.items():
            for index, entry in enumerate(self._session.section_entries(section)):
                if not isinstance(entry, dict):
                    continue

                file_value = str(entry.get("file", "") or "").strip()
                relocated_file, moved = _move_source_dir_asset_to_standard_folder(
                    file_value,
                    target_folder,
                    source_dir,
                    relocated_paths,
                    skip_generated=section == "img",
                )
                if moved:
                    moved_files += 1
                if relocated_file and relocated_file != file_value:
                    self._session.update_entry_value(section, index, "file", relocated_file)
                    updated_links += 1

                if section != "font":
                    continue

                text_items = self._font_text_items_from_value(entry.get("text", ""))
                if not text_items:
                    continue

                rewritten_items = []
                field_changed = False
                for item in text_items:
                    relocated_text, moved = _move_source_dir_asset_to_standard_folder(
                        item,
                        target_folder,
                        source_dir,
                        relocated_paths,
                    )
                    rewritten_items.append(relocated_text or item)
                    if moved:
                        moved_files += 1
                    if relocated_text and relocated_text != item:
                        field_changed = True

                if field_changed:
                    self._session.update_entry_value("font", index, "text", ",".join(rewritten_items))
                    updated_links += 1

        if not moved_files and not updated_links:
            self._set_status("Assets already use standard source folders.")
            return

        self._mark_dirty()
        self._refresh_entry_table()
        self._update_merged_preview()
        self._update_raw_editor()
        self._set_status(f"Organized {moved_files} files into standard folders, updated {updated_links} links.")

    def _sort_assets_for_quick_mode(self):
        if not self._commit_raw_json_if_needed():
            return

        total_sorted = 0
        changed = False
        for section in KNOWN_RESOURCE_SECTIONS:
            entries = self._session.section_entries(section)
            if len(entries) < 2:
                continue
            before = [copy.deepcopy(entry) for entry in entries]
            entries.sort(key=lambda entry: _resource_sort_key(section, entry))
            if entries != before:
                changed = True
                total_sorted += len(entries)

        if not changed:
            self._set_status("Assets are already sorted.")
            return

        self._mark_dirty()
        self._refresh_entry_table()
        self._update_merged_preview()
        self._update_raw_editor()
        self._set_status(f"Sorted {total_sorted} assets across quick mode sections.")

    def _rename_asset_names_from_files(self):
        if not self._commit_raw_json_if_needed():
            return

        renamed = 0
        for section in KNOWN_RESOURCE_SECTIONS:
            for index, entry in enumerate(self._session.section_entries(section)):
                if not isinstance(entry, dict):
                    continue
                suggested = _resource_name_from_file(entry.get("file", ""))
                if not suggested:
                    continue
                existing = str(entry.get("name", "") or "").strip()
                if existing == suggested:
                    continue
                self._session.update_entry_value(section, index, "name", suggested)
                renamed += 1

        if not renamed:
            self._set_status("Asset names already match filenames.")
            return

        self._mark_dirty()
        self._refresh_entry_table()
        self._update_merged_preview()
        self._update_raw_editor()
        self._set_status(f"Renamed {renamed} assets from filenames.")

    def _remove_duplicate_assets_for_quick_mode(self):
        if not self._commit_raw_json_if_needed():
            return

        removed = 0
        merged_fields = 0
        changed = False

        for section in KNOWN_RESOURCE_SECTIONS:
            entries = self._session.section_entries(section)
            if len(entries) < 2:
                continue

            deduped = []
            seen: dict[tuple[str, str], int] = {}
            section_changed = False

            for entry in entries:
                key = _resource_dedupe_key(section, entry)
                if key is None:
                    deduped.append(entry)
                    continue

                existing_index = seen.get(key)
                if existing_index is None:
                    seen[key] = len(deduped)
                    deduped.append(entry)
                    continue

                existing = deduped[existing_index]
                merged_fields += _merge_missing_resource_fields(existing, entry)
                removed += 1
                section_changed = True

            if section_changed:
                entries[:] = deduped
                changed = True

        if not changed:
            self._set_status("No duplicate assets found.")
            return

        self._mark_dirty()
        self._refresh_entry_table()
        self._update_merged_preview()
        self._update_raw_editor()
        summary = [f"Removed {removed} duplicate assets"]
        if merged_fields:
            summary.append(f"merged {merged_fields} missing fields")
        self._set_status(", ".join(summary) + ".")

    def _remove_missing_assets_for_quick_mode(self):
        if not self._commit_raw_json_if_needed():
            return

        missing_by_section: dict[str, list[int]] = {}
        total_missing = 0
        for section in KNOWN_RESOURCE_SECTIONS:
            missing_indices: list[int] = []
            for index, entry in enumerate(self._session.section_entries(section)):
                if not isinstance(entry, dict):
                    continue
                file_name = str(entry.get("file", "") or "").strip()
                resolved = self._resolve_entry_path(section, "file", file_name)
                if not file_name or not resolved or not os.path.exists(resolved):
                    missing_indices.append(index)
            if missing_indices:
                missing_by_section[section] = missing_indices
                total_missing += len(missing_indices)

        if not total_missing:
            self._set_status("No missing asset entries found.")
            return

        answer = QMessageBox.question(
            self,
            "Remove Missing Assets",
            f"Remove {total_missing} entries whose asset files are missing?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        for section, indices in missing_by_section.items():
            entries = self._session.section_entries(section)
            for index in reversed(indices):
                if 0 <= index < len(entries):
                    entries.pop(index)

        self._mark_dirty()
        self._refresh_entry_table()
        self._update_merged_preview()
        self._update_raw_editor()
        self._set_status(f"Removed {total_missing} missing asset entries.")

    def _remove_generated_helper_outputs_for_quick_mode(self):
        if not self._commit_raw_json_if_needed():
            return

        source_dir = normalize_path(self._session.paths.source_dir)
        if not source_dir:
            QMessageBox.warning(self, "Clean Helper Outputs", "Set Source Dir before cleaning generated helper outputs.")
            return

        removable_indices: list[int] = []
        for index, entry in enumerate(self._session.section_entries("img")):
            if not isinstance(entry, dict):
                continue
            file_name = str(entry.get("file", "") or "").replace("\\", "/").strip().lstrip("/")
            if _is_quick_generated_helper_path(file_name):
                removable_indices.append(index)

        removable_dirs = []
        for folder_name in _QUICK_GENERATED_ASSET_FOLDERS:
            folder_path = normalize_path(os.path.join(source_dir, folder_name))
            if os.path.isdir(folder_path):
                removable_dirs.append(folder_path)

        if not removable_indices and not removable_dirs:
            self._set_status("No generated helper outputs found.")
            return

        folder_list = "\n".join(f"- {os.path.basename(path)}" for path in removable_dirs) if removable_dirs else "- none on disk"
        answer = QMessageBox.question(
            self,
            "Clean Helper Outputs",
            f"Remove {len(removable_indices)} generated asset entries and delete {len(removable_dirs)} helper folders?\n\n{folder_list}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        deleted_files = 0
        deleted_dirs = 0
        for folder_path in removable_dirs:
            for _root, _dirs, files in os.walk(folder_path):
                deleted_files += len(files)
            try:
                shutil.rmtree(folder_path, ignore_errors=False)
            except OSError as exc:
                QMessageBox.warning(self, "Clean Helper Outputs", f"Failed to delete helper folder:\n{folder_path}\n\n{exc}")
                return
            deleted_dirs += 1

        image_entries = self._session.section_entries("img")
        for index in reversed(removable_indices):
            if 0 <= index < len(image_entries):
                image_entries.pop(index)

        self._mark_dirty()
        self._refresh_entry_table()
        self._update_merged_preview()
        self._update_raw_editor()
        self._set_status(
            f"Cleaned {len(removable_indices)} generated helper assets, deleted {deleted_files} files in {deleted_dirs} folders."
        )

    def _sync_video_metadata(self, index: int, entry: dict, *, overwrite_existing: bool) -> tuple[bool, dict]:
        file_name = str(entry.get("file", "") or "").strip()
        resolved_path = self._resolve_entry_path("mp4", "file", file_name)
        if not resolved_path or not os.path.isfile(resolved_path):
            return False, {}

        metadata = _detect_video_metadata(resolved_path)
        if not metadata:
            return False, {}

        changed = False
        for field_name in ("fps", "width", "height"):
            incoming = metadata.get(field_name)
            if incoming in (None, "", 0):
                continue
            existing = entry.get(field_name, "")
            if not overwrite_existing and existing not in ("", None, 0):
                continue
            if str(existing or "").strip() == str(incoming).strip():
                continue
            self._session.update_entry_value("mp4", index, field_name, incoming)
            changed = True
        return changed, metadata

    def _matched_font_text_path(self, section: str, entry: dict) -> str:
        file_name = str(entry.get("file", "") or "").strip()
        resolved_font = self._resolve_entry_path(section, "file", file_name)
        if not resolved_font or not os.path.isfile(resolved_font):
            return ""

        source_dir = self._session.paths.source_dir
        candidates = [normalize_path(os.path.splitext(resolved_font)[0] + ".txt")]
        if source_dir:
            basename = _resource_name_from_file(file_name)
            candidates.append(normalize_path(os.path.join(source_dir, f"{basename}.txt")))

        for candidate in candidates:
            if not candidate or not os.path.isfile(candidate):
                continue
            if source_dir and _is_subpath(candidate, source_dir):
                return os.path.relpath(candidate, source_dir).replace("\\", "/")
            return candidate
        return ""

    def _selected_font_text_context(self) -> tuple[int, dict | None]:
        section, index, entry = self._selected_simple_asset_context()
        if section == "font" and entry is not None:
            return index, entry
        if self._active_section == "font":
            return self._active_entry_index, self._current_entry()
        return -1, None

    def _font_text_field_spec(self):
        return next((field for field in RESOURCE_SECTION_SPECS["font"].fields if field.name == "text"), None)

    def _normalize_selected_font_text_path(self, selected_path: str) -> str | None:
        field_spec = self._font_text_field_spec()
        if field_spec is None:
            return None
        return self._normalize_selected_resource_path(field_spec, selected_path)

    def _open_selected_font_text_links_editor(self):
        index, entry = self._selected_font_text_context()
        if entry is None:
            QMessageBox.warning(self, "Font Text Files", "Select a font asset first.")
            return

        previous_value = self._normalize_font_text_value(entry.get("text", ""))
        dialog = _FontTextLinksDialog(
            initial_items=self._font_text_items_from_value(previous_value),
            source_dir=self._session.paths.source_dir,
            normalize_file_callback=self._normalize_selected_font_text_path,
            edit_file_callback=lambda item, item_index=index, item_entry=entry: self._open_specific_font_text_resource(
                item_index,
                item_entry,
                item,
                assign_to_font=False,
                confirm_create=False,
            ),
            parent=self,
        )
        if dialog.exec_() != QDialog.Accepted:
            return

        self._active_section = "font"
        self._active_entry_index = index
        self._update_current_entry_field("text", dialog.text_value(), normalize_font_text=True, sync_widget_text=True)
        current_entry = self._current_entry() or {}
        current_value = self._normalize_font_text_value(current_entry.get("text", ""))
        if current_value != previous_value:
            font_label = section_entry_label("font", current_entry, index)
            self._set_status(f"Updated font text links for '{font_label}'.")

    def _open_specific_font_text_resource(
        self,
        index: int,
        entry: dict,
        target_filename: str,
        *,
        assign_to_font: bool = True,
        confirm_create: bool = True,
    ):
        if not target_filename:
            return False
        resolved_path = self._resolve_entry_path("font", "text", target_filename)
        return self._open_font_text_resource_target(
            index,
            entry,
            target_filename,
            resolved_path,
            assign_to_font=assign_to_font,
            confirm_create=confirm_create,
        )

    def _open_selected_font_text_resource(self):
        index, entry = self._selected_font_text_context()
        if entry is None:
            QMessageBox.warning(self, "Edit Font Text", "Select a font asset first.")
            return

        target_filename, resolved_path = self._choose_font_text_target(entry)
        if target_filename is None:
            return
        self._open_font_text_resource_target(index, entry, target_filename, resolved_path)

    def _open_font_text_resource_target(
        self,
        index: int,
        entry: dict,
        target_filename: str,
        resolved_path: str,
        *,
        assign_to_font: bool = True,
        confirm_create: bool = True,
    ):
        if not target_filename or not resolved_path:
            QMessageBox.warning(
                self,
                "Edit Font Text",
                "Set Source Dir first so Designer knows where to save the font text file.",
            )
            return False
        if os.path.isdir(resolved_path):
            QMessageBox.warning(self, "Edit Font Text", f"Selected path is a folder:\n{resolved_path}")
            return False

        source_dir = normalize_path(self._session.paths.source_dir)
        if source_dir and not os.path.isabs(str(target_filename or "").strip()) and not _is_subpath(resolved_path, source_dir):
            QMessageBox.warning(self, "Edit Font Text", "Font text paths must stay inside Source Dir.")
            return False

        is_new_file = not os.path.isfile(resolved_path)
        initial_text = ""
        if is_new_file:
            if confirm_create:
                answer = QMessageBox.question(
                    self,
                    "Create Font Text",
                    f"Create a new font text resource?\n\n{target_filename}",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes,
                )
                if answer != QMessageBox.Yes:
                    return False
            initial_text = _default_new_font_text_file_body()
        else:
            try:
                with open(resolved_path, "r", encoding="utf-8") as handle:
                    initial_text = handle.read()
            except OSError as exc:
                QMessageBox.warning(self, "Edit Font Text", f"Failed to read text file:\n{resolved_path}\n\n{exc}")
                return False

        dialog = _FontTextEditorDialog(
            filename=target_filename,
            initial_text=initial_text,
            is_new_file=is_new_file,
            parent=self,
        )
        if dialog.exec_() != QDialog.Accepted:
            return False

        content = str(dialog.text_value() or "").replace("\r\n", "\n").replace("\r", "\n")
        os.makedirs(os.path.dirname(resolved_path), exist_ok=True)
        try:
            with open(resolved_path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(content)
        except OSError as exc:
            QMessageBox.warning(self, "Edit Font Text", f"Failed to write text file:\n{resolved_path}\n\n{exc}")
            return False

        self._active_section = "font"
        self._active_entry_index = index
        if assign_to_font:
            self._assign_generated_text_to_font(target_filename)
        self._refresh_simple_page()
        self._update_form()
        self._update_simple_asset_preview()
        action = "Created and saved" if is_new_file else "Saved"
        self._set_status(f"{action} font text '{target_filename}'.")
        return True

    def _font_text_items_from_value(self, value) -> list[str]:
        items = []
        for item in re.split(r"[,;\r\n\uFF0C\uFF1B]+", str(value or "")):
            normalized = item.strip()
            if normalized and normalized not in items:
                items.append(normalized)
        return items

    def _normalize_font_text_value(self, value) -> str:
        return ",".join(self._font_text_items_from_value(value))

    def _font_text_targets(self, entry: dict) -> list[tuple[str, str]]:
        targets = []
        seen = set()
        for item in self._font_text_items_from_value(entry.get("text", "")):
            if item in seen:
                continue
            seen.add(item)
            targets.append((item, self._resolve_entry_path("font", "text", item)))
        return targets

    def _choose_font_text_target(self, entry: dict) -> tuple[str | None, str]:
        targets = self._font_text_targets(entry)
        if len(targets) <= 1:
            return self._preferred_font_text_target(entry)

        labels = []
        labeled_targets = {}
        for item, resolved in targets:
            label = item if resolved and os.path.isfile(resolved) else f"{item} (missing)"
            if label in labeled_targets:
                label = f"{label} [{len(labels) + 1}]"
            labels.append(label)
            labeled_targets[label] = (item, resolved)

        selected_label, accepted = QInputDialog.getItem(
            self,
            "Edit Font Text",
            "Choose which linked text file to edit:",
            labels,
            0,
            False,
        )
        if not accepted:
            return None, ""
        return labeled_targets.get(selected_label, (None, ""))

    def _preferred_font_text_target(self, entry: dict) -> tuple[str, str]:
        candidates = self._font_text_targets(entry)
        for item, resolved in candidates:
            if resolved and os.path.isfile(resolved):
                return item, resolved

        if candidates:
            return candidates[0]

        matched_text = self._matched_font_text_path("font", entry)
        if matched_text:
            resolved_path = self._resolve_entry_path("font", "text", matched_text)
            if resolved_path:
                return matched_text, resolved_path

        source_dir = self._session.paths.source_dir
        if not source_dir:
            return "", ""
        suggested = _suggest_charset_filename_for_resource("font", str(entry.get("file", "") or ""))
        return suggested, normalize_path(os.path.join(source_dir, suggested))

    def _open_resize_image_helper(self):
        section, index, entry = self._selected_simple_asset_context()
        if entry is None or section != "img":
            QMessageBox.warning(self, "Resize Image", "Select an image asset in Simple mode first.")
            return
        file_name = str(entry.get("file", "") or "").strip()
        resolved_path = self._resolve_entry_path("img", "file", file_name)
        if not resolved_path or not os.path.isfile(resolved_path):
            QMessageBox.warning(self, "Resize Image", f"Image file does not exist:\n{resolved_path or file_name}")
            return

        pixmap = QPixmap(resolved_path)
        if pixmap.isNull():
            QMessageBox.warning(self, "Resize Image", f"Qt could not decode the selected image:\n{resolved_path}")
            return

        dialog = _QuickImageResizeDialog(
            width=pixmap.width(),
            height=pixmap.height(),
            output_filename=file_name,
            parent=self,
        )
        if dialog.exec_() != QDialog.Accepted:
            return

        output_filename = dialog.output_filename()
        width = dialog.width_value()
        height = dialog.height_value()
        if not output_filename:
            QMessageBox.warning(self, "Resize Image", "Enter an output filename.")
            return
        if os.path.isabs(output_filename):
            QMessageBox.warning(self, "Resize Image", "Output filename must stay inside Source Dir.")
            return

        normalized_output = output_filename.replace("\\", "/").strip().lstrip("/")
        if not normalized_output or normalized_output.startswith(".."):
            QMessageBox.warning(self, "Resize Image", "Output filename must stay inside Source Dir.")
            return

        self._apply_image_resize(entry, index, resolved_path, normalized_output, width, height)

    def _open_border_image_helper(self):
        section, index, entry = self._selected_simple_asset_context()
        if entry is None or section != "img":
            QMessageBox.warning(self, "Add Border", "Select an image asset in Simple mode first.")
            return
        file_name = str(entry.get("file", "") or "").strip()
        resolved_path = self._resolve_entry_path("img", "file", file_name)
        if not resolved_path or not os.path.isfile(resolved_path):
            QMessageBox.warning(self, "Add Border", f"Image file does not exist:\n{resolved_path or file_name}")
            return

        pixmap = QPixmap(resolved_path)
        if pixmap.isNull():
            QMessageBox.warning(self, "Add Border", f"Qt could not decode the selected image:\n{resolved_path}")
            return

        dialog = _QuickImageBorderDialog(output_filename=file_name, parent=self)
        if dialog.exec_() != QDialog.Accepted:
            return

        output_filename = dialog.output_filename()
        if not output_filename:
            QMessageBox.warning(self, "Add Border", "Enter an output filename.")
            return
        if os.path.isabs(output_filename):
            QMessageBox.warning(self, "Add Border", "Output filename must stay inside Source Dir.")
            return

        normalized_output = output_filename.replace("\\", "/").strip().lstrip("/")
        if not normalized_output or normalized_output.startswith(".."):
            QMessageBox.warning(self, "Add Border", "Output filename must stay inside Source Dir.")
            return

        color = QColor(dialog.color_value())
        if not color.isValid():
            QMessageBox.warning(self, "Add Border", "Enter a valid border color like #FFFFFF or #11223344.")
            return

        self._apply_image_border(
            entry,
            index,
            resolved_path,
            normalized_output,
            dialog.border_size(),
            color,
        )

    def _open_background_image_helper(self):
        section, index, entry = self._selected_simple_asset_context()
        if entry is None or section != "img":
            QMessageBox.warning(self, "Add Background", "Select an image asset in Simple mode first.")
            return
        file_name = str(entry.get("file", "") or "").strip()
        resolved_path = self._resolve_entry_path("img", "file", file_name)
        if not resolved_path or not os.path.isfile(resolved_path):
            QMessageBox.warning(self, "Add Background", f"Image file does not exist:\n{resolved_path or file_name}")
            return

        pixmap = QPixmap(resolved_path)
        if pixmap.isNull():
            QMessageBox.warning(self, "Add Background", f"Qt could not decode the selected image:\n{resolved_path}")
            return

        dialog = _QuickImageBackgroundDialog(output_filename=file_name, parent=self)
        if dialog.exec_() != QDialog.Accepted:
            return

        output_filename = dialog.output_filename()
        if not output_filename:
            QMessageBox.warning(self, "Add Background", "Enter an output filename.")
            return
        if os.path.isabs(output_filename):
            QMessageBox.warning(self, "Add Background", "Output filename must stay inside Source Dir.")
            return

        normalized_output = output_filename.replace("\\", "/").strip().lstrip("/")
        if not normalized_output or normalized_output.startswith(".."):
            QMessageBox.warning(self, "Add Background", "Output filename must stay inside Source Dir.")
            return

        color = QColor(dialog.color_value())
        if not color.isValid():
            QMessageBox.warning(self, "Add Background", "Enter a valid background color like #FFFFFF or #11223344.")
            return

        self._apply_image_background(
            entry,
            index,
            resolved_path,
            normalized_output,
            color,
        )

    def _open_round_corners_image_helper(self):
        section, index, entry = self._selected_simple_asset_context()
        if entry is None or section != "img":
            QMessageBox.warning(self, "Round Corners", "Select an image asset in Simple mode first.")
            return
        file_name = str(entry.get("file", "") or "").strip()
        resolved_path = self._resolve_entry_path("img", "file", file_name)
        if not resolved_path or not os.path.isfile(resolved_path):
            QMessageBox.warning(self, "Round Corners", f"Image file does not exist:\n{resolved_path or file_name}")
            return

        pixmap = QPixmap(resolved_path)
        if pixmap.isNull():
            QMessageBox.warning(self, "Round Corners", f"Qt could not decode the selected image:\n{resolved_path}")
            return

        dialog = _QuickImageRoundCornersDialog(
            width=pixmap.width(),
            height=pixmap.height(),
            output_filename=file_name,
            parent=self,
        )
        if dialog.exec_() != QDialog.Accepted:
            return

        output_filename = dialog.output_filename()
        if not output_filename:
            QMessageBox.warning(self, "Round Corners", "Enter an output filename.")
            return
        if os.path.isabs(output_filename):
            QMessageBox.warning(self, "Round Corners", "Output filename must stay inside Source Dir.")
            return

        normalized_output = output_filename.replace("\\", "/").strip().lstrip("/")
        if not normalized_output or normalized_output.startswith(".."):
            QMessageBox.warning(self, "Round Corners", "Output filename must stay inside Source Dir.")
            return

        self._apply_image_round_corners(
            entry,
            index,
            resolved_path,
            normalized_output,
            dialog.radius_value(),
        )

    def _open_opacity_image_helper(self):
        section, index, entry = self._selected_simple_asset_context()
        if entry is None or section != "img":
            QMessageBox.warning(self, "Adjust Opacity", "Select an image asset in Simple mode first.")
            return
        file_name = str(entry.get("file", "") or "").strip()
        resolved_path = self._resolve_entry_path("img", "file", file_name)
        if not resolved_path or not os.path.isfile(resolved_path):
            QMessageBox.warning(self, "Adjust Opacity", f"Image file does not exist:\n{resolved_path or file_name}")
            return

        pixmap = QPixmap(resolved_path)
        if pixmap.isNull():
            QMessageBox.warning(self, "Adjust Opacity", f"Qt could not decode the selected image:\n{resolved_path}")
            return

        dialog = _QuickImageOpacityDialog(output_filename=file_name, parent=self)
        if dialog.exec_() != QDialog.Accepted:
            return

        output_filename = dialog.output_filename()
        if not output_filename:
            QMessageBox.warning(self, "Adjust Opacity", "Enter an output filename.")
            return
        if os.path.isabs(output_filename):
            QMessageBox.warning(self, "Adjust Opacity", "Output filename must stay inside Source Dir.")
            return

        normalized_output = output_filename.replace("\\", "/").strip().lstrip("/")
        if not normalized_output or normalized_output.startswith(".."):
            QMessageBox.warning(self, "Adjust Opacity", "Output filename must stay inside Source Dir.")
            return

        self._apply_image_opacity(
            entry,
            index,
            resolved_path,
            normalized_output,
            dialog.opacity_percent(),
        )

    def _open_generate_thumbnails_helper(self):
        if not self._commit_raw_json_if_needed():
            return

        image_entries = [
            entry
            for entry in self._session.section_entries("img")
            if isinstance(entry, dict) and str(entry.get("file", "") or "").strip()
        ]
        if not image_entries:
            QMessageBox.information(self, "Generate Thumbnails", "Import or create some image assets first.")
            return

        dialog = _QuickThumbnailBatchDialog(
            width=160,
            height=160,
            output_folder="thumbnails",
            suffix="_thumb",
            parent=self,
        )
        if dialog.exec_() != QDialog.Accepted:
            return

        output_folder = dialog.output_folder().replace("\\", "/").strip().strip("/")
        suffix = dialog.filename_suffix().strip()
        if not output_folder:
            QMessageBox.warning(self, "Generate Thumbnails", "Enter an output folder inside Source Dir.")
            return
        if output_folder.startswith("..") or os.path.isabs(output_folder):
            QMessageBox.warning(self, "Generate Thumbnails", "Output folder must stay inside Source Dir.")
            return
        if not suffix:
            QMessageBox.warning(self, "Generate Thumbnails", "Enter a filename suffix for generated thumbnails.")
            return

        self._generate_thumbnail_images_for_quick_mode(
            max_width=dialog.width_value(),
            max_height=dialog.height_value(),
            output_folder=output_folder,
            filename_suffix=suffix,
        )

    def _open_generate_placeholders_helper(self):
        if not self._commit_raw_json_if_needed():
            return

        image_entries = [
            entry
            for entry in self._session.section_entries("img")
            if isinstance(entry, dict)
        ]
        if not image_entries:
            QMessageBox.information(self, "Generate Placeholders", "Import or create some image assets first.")
            return

        dialog = _QuickImagePlaceholderDialog(
            width=160,
            height=120,
            output_folder="placeholders",
            parent=self,
        )
        if dialog.exec_() != QDialog.Accepted:
            return

        output_folder = dialog.output_folder().replace("\\", "/").strip().strip("/")
        if not output_folder:
            QMessageBox.warning(self, "Generate Placeholders", "Enter a fallback folder inside Source Dir.")
            return
        if output_folder.startswith("..") or os.path.isabs(output_folder):
            QMessageBox.warning(self, "Generate Placeholders", "Fallback folder must stay inside Source Dir.")
            return

        self._generate_placeholder_images_for_quick_mode(
            width=dialog.width_value(),
            height=dialog.height_value(),
            output_folder=output_folder,
        )

    def _open_normalize_images_helper(self):
        if not self._commit_raw_json_if_needed():
            return

        image_entries = [
            entry
            for entry in self._session.section_entries("img")
            if isinstance(entry, dict) and str(entry.get("file", "") or "").strip()
        ]
        if not image_entries:
            QMessageBox.information(self, "Normalize Images", "Import or create some image assets first.")
            return

        dialog = _QuickImageNormalizeDialog(
            output_folder="normalized",
            suffix="_norm",
            parent=self,
        )
        if dialog.exec_() != QDialog.Accepted:
            return

        output_folder = dialog.output_folder().replace("\\", "/").strip().strip("/")
        suffix = dialog.filename_suffix().strip()
        if not output_folder:
            QMessageBox.warning(self, "Normalize Images", "Enter an output folder inside Source Dir.")
            return
        if output_folder.startswith("..") or os.path.isabs(output_folder):
            QMessageBox.warning(self, "Normalize Images", "Output folder must stay inside Source Dir.")
            return
        if not suffix:
            QMessageBox.warning(self, "Normalize Images", "Enter a filename suffix for normalized images.")
            return

        self._normalize_images_for_quick_mode(
            output_folder=output_folder,
            filename_suffix=suffix,
        )

    def _open_compress_images_helper(self):
        if not self._commit_raw_json_if_needed():
            return

        image_entries = [
            entry
            for entry in self._session.section_entries("img")
            if isinstance(entry, dict) and str(entry.get("file", "") or "").strip()
        ]
        if not image_entries:
            QMessageBox.information(self, "Compress Images", "Import or create some image assets first.")
            return

        dialog = _QuickImageCompressDialog(
            output_folder="compressed",
            suffix="_cmp",
            colors=64,
            parent=self,
        )
        if dialog.exec_() != QDialog.Accepted:
            return

        output_folder = dialog.output_folder().replace("\\", "/").strip().strip("/")
        suffix = dialog.filename_suffix().strip()
        if not output_folder:
            QMessageBox.warning(self, "Compress Images", "Enter an output folder inside Source Dir.")
            return
        if output_folder.startswith("..") or os.path.isabs(output_folder):
            QMessageBox.warning(self, "Compress Images", "Output folder must stay inside Source Dir.")
            return
        if not suffix:
            QMessageBox.warning(self, "Compress Images", "Enter a filename suffix for compressed images.")
            return

        self._compress_images_for_quick_mode(
            output_folder=output_folder,
            filename_suffix=suffix,
            color_limit=dialog.color_limit(),
        )

    def _open_prerender_fonts_helper(self):
        if not self._commit_raw_json_if_needed():
            return

        font_entries = [
            entry
            for entry in self._session.section_entries("font")
            if isinstance(entry, dict) and str(entry.get("file", "") or "").strip()
        ]
        if not font_entries:
            QMessageBox.information(self, "Pre-Render Fonts", "Import or create some font assets first.")
            return

        dialog = _QuickFontPrerenderDialog(
            output_folder="font_previews",
            suffix="_preview",
            sample_text="",
            parent=self,
        )
        if dialog.exec_() != QDialog.Accepted:
            return

        output_folder = dialog.output_folder().replace("\\", "/").strip().strip("/")
        suffix = dialog.filename_suffix().strip()
        if not output_folder:
            QMessageBox.warning(self, "Pre-Render Fonts", "Enter an output folder inside Source Dir.")
            return
        if output_folder.startswith("..") or os.path.isabs(output_folder):
            QMessageBox.warning(self, "Pre-Render Fonts", "Output folder must stay inside Source Dir.")
            return
        if not suffix:
            QMessageBox.warning(self, "Pre-Render Fonts", "Enter a filename suffix for rendered previews.")
            return

        self._prerender_fonts_for_quick_mode(
            output_folder=output_folder,
            filename_suffix=suffix,
            sample_text_override=dialog.sample_text(),
        )

    def _generate_thumbnail_images_for_quick_mode(self, *, max_width: int, max_height: int, output_folder: str, filename_suffix: str):
        try:
            from PIL import Image, ImageOps
        except Exception as exc:
            QMessageBox.warning(self, "Generate Thumbnails", f"Pillow is required for thumbnail generation:\n{exc}")
            return

        source_dir = normalize_path(self._session.paths.source_dir)
        if not source_dir:
            QMessageBox.warning(self, "Generate Thumbnails", "Set Source Dir before generating thumbnails.")
            return

        generated_assets: list[tuple[str, str]] = []
        generated_files = 0

        normalized_folder = output_folder.replace("\\", "/").strip().strip("/")
        size = (max(max_width, 1), max(max_height, 1))

        for entry in self._session.section_entries("img"):
            if not isinstance(entry, dict):
                continue

            file_name = str(entry.get("file", "") or "").strip()
            resolved_path = self._resolve_entry_path("img", "file", file_name)
            if not resolved_path or not os.path.isfile(resolved_path):
                continue

            base_name = _resource_name_from_file(file_name or resolved_path)
            if not base_name:
                continue

            relative_output = f"{normalized_folder}/{base_name}{filename_suffix}.png"
            relative_output = relative_output.replace("//", "/")
            target_path = normalize_path(os.path.join(source_dir, relative_output.replace("/", os.sep)))
            if normalize_path(resolved_path) == target_path:
                continue

            try:
                with Image.open(resolved_path) as image:
                    prepared = ImageOps.exif_transpose(image)
                    thumbnail = prepared.copy()
                    thumbnail.thumbnail(size, Image.LANCZOS)
                    if thumbnail.mode not in {"RGB", "RGBA"}:
                        thumbnail = thumbnail.convert("RGBA")
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    thumbnail.save(target_path, "PNG")
            except Exception as exc:
                QMessageBox.warning(self, "Generate Thumbnails", f"Failed to generate thumbnail for:\n{resolved_path}\n\n{exc}")
                return

            generated_files += 1
            generated_assets.append(("img", target_path))

        if not generated_assets:
            self._set_status("No image assets were available for thumbnail generation.")
            return

        entries_by_section = self._build_entries_from_asset_paths(generated_assets, [], source_dir)
        added, updated = self._merge_discovered_entries(entries_by_section)
        self._mark_dirty()
        self._refresh_entry_table()
        self._update_merged_preview()
        self._update_raw_editor()

        summary = [f"Generated {generated_files} thumbnails"]
        if added:
            summary.append(f"added {added} assets")
        if updated:
            summary.append(f"updated {updated} assets")
        self._set_status(", ".join(summary) + ".")

    def _generate_placeholder_images_for_quick_mode(self, *, width: int, height: int, output_folder: str):
        source_dir = normalize_path(self._session.paths.source_dir)
        if not source_dir:
            QMessageBox.warning(self, "Generate Placeholders", "Set Source Dir before generating placeholder images.")
            return

        generated_files = 0
        updated_links = 0
        skipped_assets = 0
        normalized_folder = output_folder.replace("\\", "/").strip().strip("/")

        for index, entry in enumerate(self._session.section_entries("img")):
            if not isinstance(entry, dict):
                continue

            file_name = str(entry.get("file", "") or "").strip()
            resolved_path = self._resolve_entry_path("img", "file", file_name) if file_name else ""
            if resolved_path and os.path.isfile(resolved_path):
                continue

            target_relative = ""
            if file_name:
                if os.path.isabs(file_name):
                    if resolved_path and _is_subpath(resolved_path, source_dir):
                        target_relative = os.path.relpath(resolved_path, source_dir).replace("\\", "/")
                    else:
                        skipped_assets += 1
                        continue
                else:
                    normalized_output = file_name.replace("\\", "/").strip().lstrip("/")
                    if not normalized_output or normalized_output.startswith(".."):
                        skipped_assets += 1
                        continue
                    target_relative = normalized_output
            else:
                stem = _safe_quick_placeholder_stem(
                    str(entry.get("name", "") or "") or _resource_name_from_file(entry.get("file", "")),
                    fallback=f"image_{index + 1}",
                )
                target_relative = f"{normalized_folder}/{stem}_placeholder.png"

            target_path = normalize_path(os.path.join(source_dir, target_relative.replace("/", os.sep)))
            if not _is_subpath(target_path, source_dir):
                skipped_assets += 1
                continue

            pixmap = _build_quick_placeholder_pixmap(
                str(entry.get("name", "") or "") or _resource_name_from_file(target_relative) or "Placeholder",
                width=max(int(width), 16),
                height=max(int(height), 16),
            )
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            if not pixmap.save(target_path, "PNG"):
                QMessageBox.warning(self, "Generate Placeholders", f"Failed to save placeholder image:\n{target_path}")
                return

            generated_files += 1
            if target_relative != file_name:
                self._session.update_entry_value("img", index, "file", target_relative)
                updated_links += 1

        if not generated_files:
            self._set_status("No missing image assets needed placeholders.")
            return

        if updated_links:
            self._mark_dirty()
            self._refresh_entry_table()
            self._update_merged_preview()
            self._update_raw_editor()
        else:
            self._refresh_simple_page()

        summary = [f"Generated {generated_files} placeholders"]
        if updated_links:
            summary.append(f"updated {updated_links} links")
        if skipped_assets:
            summary.append(f"skipped {skipped_assets} assets")
        self._set_status(", ".join(summary) + ".")

    def _prerender_fonts_for_quick_mode(self, *, output_folder: str, filename_suffix: str, sample_text_override: str):
        source_dir = normalize_path(self._session.paths.source_dir)
        if not source_dir:
            QMessageBox.warning(self, "Pre-Render Fonts", "Set Source Dir before rendering font previews.")
            return

        generated_assets: list[tuple[str, str]] = []
        rendered_files = 0
        normalized_folder = output_folder.replace("\\", "/").strip().strip("/")
        shared_sample = str(sample_text_override or "").strip()

        for entry in self._session.section_entries("font"):
            if not isinstance(entry, dict):
                continue

            file_name = str(entry.get("file", "") or "").strip()
            resolved_path = self._resolve_entry_path("font", "file", file_name)
            if not resolved_path or not os.path.isfile(resolved_path):
                continue

            base_name = str(entry.get("name", "") or "").strip()
            if not base_name:
                normalized_name = os.path.splitext(str(file_name or "").replace("\\", "/").strip().lstrip("/"))[0]
                base_name = normalized_name.replace("/", "_").strip() or _resource_name_from_file(resolved_path)
            if not base_name:
                continue

            sample_text = shared_sample or self._font_preview_sample(entry)[0]
            preview_pixmap = self._build_font_preview_pixmap(resolved_path, sample_text, entry=entry)
            if preview_pixmap is None or preview_pixmap.isNull():
                QMessageBox.warning(
                    self,
                    "Pre-Render Fonts",
                    f"Failed to render a font preview for:\n{resolved_path}\n\nCheck that the font file is valid and the SDK preview pipeline is available.",
                )
                return

            relative_output = f"{normalized_folder}/{base_name}{filename_suffix}.png"
            relative_output = relative_output.replace("//", "/")
            target_path = normalize_path(os.path.join(source_dir, relative_output.replace("/", os.sep)))

            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            if not preview_pixmap.save(target_path, "PNG"):
                QMessageBox.warning(self, "Pre-Render Fonts", f"Failed to save rendered preview:\n{target_path}")
                return

            rendered_files += 1
            generated_assets.append(("img", target_path))

        if not generated_assets:
            self._set_status("No font assets were available for pre-rendering.")
            return

        entries_by_section = self._build_entries_from_asset_paths(generated_assets, [], source_dir)
        added, updated = self._merge_discovered_entries(entries_by_section)
        self._mark_dirty()
        self._refresh_entry_table()
        self._update_merged_preview()
        self._update_raw_editor()

        summary = [f"Pre-rendered {rendered_files} fonts"]
        if added:
            summary.append(f"added {added} assets")
        if updated:
            summary.append(f"updated {updated} assets")
        self._set_status(", ".join(summary) + ".")

    def _compress_images_for_quick_mode(self, *, output_folder: str, filename_suffix: str, color_limit: int):
        try:
            from PIL import Image, ImageOps
        except Exception as exc:
            QMessageBox.warning(self, "Compress Images", f"Pillow is required for image compression:\n{exc}")
            return

        source_dir = normalize_path(self._session.paths.source_dir)
        if not source_dir:
            QMessageBox.warning(self, "Compress Images", "Set Source Dir before compressing images.")
            return

        generated_assets: list[tuple[str, str]] = []
        compressed_files = 0
        normalized_folder = output_folder.replace("\\", "/").strip().strip("/")

        for entry in self._session.section_entries("img"):
            if not isinstance(entry, dict):
                continue

            file_name = str(entry.get("file", "") or "").strip()
            resolved_path = self._resolve_entry_path("img", "file", file_name)
            if not resolved_path or not os.path.isfile(resolved_path):
                continue

            base_name = str(entry.get("name", "") or "").strip()
            if not base_name:
                normalized_name = os.path.splitext(str(file_name or "").replace("\\", "/").strip().lstrip("/"))[0]
                base_name = normalized_name.replace("/", "_").strip() or _resource_name_from_file(resolved_path)
            if not base_name:
                continue

            relative_output = f"{normalized_folder}/{base_name}{filename_suffix}.png"
            relative_output = relative_output.replace("//", "/")
            target_path = normalize_path(os.path.join(source_dir, relative_output.replace("/", os.sep)))
            if normalize_path(resolved_path) == target_path:
                continue

            try:
                with Image.open(resolved_path) as image:
                    compressed = ImageOps.exif_transpose(image)
                    if compressed.mode not in {"RGB", "RGBA"}:
                        compressed = compressed.convert("RGBA")
                    if "A" in compressed.getbands():
                        flattened = compressed.convert("RGBA").quantize(colors=max(min(int(color_limit), 256), 2))
                    else:
                        flattened = compressed.convert("RGB").quantize(colors=max(min(int(color_limit), 256), 2))
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    flattened.save(target_path, "PNG", optimize=True, compress_level=9)
            except Exception as exc:
                QMessageBox.warning(self, "Compress Images", f"Failed to compress image:\n{resolved_path}\n\n{exc}")
                return

            compressed_files += 1
            generated_assets.append(("img", target_path))

        if not generated_assets:
            self._set_status("No image assets were available for compression.")
            return

        entries_by_section = self._build_entries_from_asset_paths(generated_assets, [], source_dir)
        added, updated = self._merge_discovered_entries(entries_by_section)
        self._mark_dirty()
        self._refresh_entry_table()
        self._update_merged_preview()
        self._update_raw_editor()

        summary = [f"Compressed {compressed_files} images"]
        if added:
            summary.append(f"added {added} assets")
        if updated:
            summary.append(f"updated {updated} assets")
        self._set_status(", ".join(summary) + ".")

    def _normalize_images_for_quick_mode(self, *, output_folder: str, filename_suffix: str):
        try:
            from PIL import Image, ImageOps
        except Exception as exc:
            QMessageBox.warning(self, "Normalize Images", f"Pillow is required for image normalization:\n{exc}")
            return

        source_dir = normalize_path(self._session.paths.source_dir)
        if not source_dir:
            QMessageBox.warning(self, "Normalize Images", "Set Source Dir before normalizing images.")
            return

        generated_assets: list[tuple[str, str]] = []
        normalized_files = 0
        normalized_folder = output_folder.replace("\\", "/").strip().strip("/")

        for entry in self._session.section_entries("img"):
            if not isinstance(entry, dict):
                continue

            file_name = str(entry.get("file", "") or "").strip()
            resolved_path = self._resolve_entry_path("img", "file", file_name)
            if not resolved_path or not os.path.isfile(resolved_path):
                continue

            base_name = str(entry.get("name", "") or "").strip()
            if not base_name:
                normalized_name = os.path.splitext(str(file_name or "").replace("\\", "/").strip().lstrip("/"))[0]
                base_name = normalized_name.replace("/", "_").strip() or _resource_name_from_file(resolved_path)
            if not base_name:
                continue

            relative_output = f"{normalized_folder}/{base_name}{filename_suffix}.png"
            relative_output = relative_output.replace("//", "/")
            target_path = normalize_path(os.path.join(source_dir, relative_output.replace("/", os.sep)))
            if normalize_path(resolved_path) == target_path:
                continue

            try:
                with Image.open(resolved_path) as image:
                    normalized = ImageOps.exif_transpose(image)
                    if normalized.mode not in {"RGB", "RGBA"}:
                        normalized = normalized.convert("RGBA")
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    normalized.save(target_path, "PNG")
            except Exception as exc:
                QMessageBox.warning(self, "Normalize Images", f"Failed to normalize image:\n{resolved_path}\n\n{exc}")
                return

            normalized_files += 1
            generated_assets.append(("img", target_path))

        if not generated_assets:
            self._set_status("No image assets were available for normalization.")
            return

        entries_by_section = self._build_entries_from_asset_paths(generated_assets, [], source_dir)
        added, updated = self._merge_discovered_entries(entries_by_section)
        self._mark_dirty()
        self._refresh_entry_table()
        self._update_merged_preview()
        self._update_raw_editor()

        summary = [f"Normalized {normalized_files} images"]
        if added:
            summary.append(f"added {added} assets")
        if updated:
            summary.append(f"updated {updated} assets")
        self._set_status(", ".join(summary) + ".")

    def _apply_image_resize(self, entry: dict, index: int, source_path: str, output_filename: str, width: int, height: int):
        try:
            from PIL import Image
        except Exception as exc:
            QMessageBox.warning(self, "Resize Image", f"Pillow is required for image resizing:\n{exc}")
            return

        source_dir = self._session.paths.source_dir
        if not source_dir:
            QMessageBox.warning(self, "Resize Image", "Set Source Dir before resizing images.")
            return

        target_path = normalize_path(os.path.join(source_dir, output_filename))
        if not _is_subpath(target_path, source_dir) and normalize_path(target_path) != normalize_path(source_path):
            QMessageBox.warning(self, "Resize Image", "Output filename must stay inside Source Dir.")
            return

        existed_before = os.path.isfile(target_path)
        if normalize_path(target_path) != normalize_path(source_path) and existed_before:
            answer = QMessageBox.question(
                self,
                "Overwrite Image",
                f"Overwrite existing image?\n\n{output_filename}",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return

        try:
            with Image.open(source_path) as image:
                resized = image.resize((max(int(width), 1), max(int(height), 1)), Image.LANCZOS)
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                resized.save(target_path)
        except Exception as exc:
            QMessageBox.warning(self, "Resize Image", f"Failed to resize image:\n{exc}")
            return

        action = "Created" if output_filename != str(entry.get("file", "") or "").replace("\\", "/") else "Updated"
        self._finalize_saved_image_output(
            entry,
            index,
            output_filename,
            f"{action} resized image '{output_filename}' ({width} x {height}).",
        )

    def _apply_image_border(self, entry: dict, index: int, source_path: str, output_filename: str, border_size: int, color: QColor):
        try:
            from PIL import Image, ImageOps
        except Exception as exc:
            QMessageBox.warning(self, "Add Border", f"Pillow is required for border editing:\n{exc}")
            return

        source_dir = self._session.paths.source_dir
        if not source_dir:
            QMessageBox.warning(self, "Add Border", "Set Source Dir before editing images.")
            return

        target_path = normalize_path(os.path.join(source_dir, output_filename))
        if not _is_subpath(target_path, source_dir) and normalize_path(target_path) != normalize_path(source_path):
            QMessageBox.warning(self, "Add Border", "Output filename must stay inside Source Dir.")
            return

        existed_before = os.path.isfile(target_path)
        if normalize_path(target_path) != normalize_path(source_path) and existed_before:
            answer = QMessageBox.question(
                self,
                "Overwrite Image",
                f"Overwrite existing image?\n\n{output_filename}",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return

        try:
            rgba = (color.red(), color.green(), color.blue(), color.alpha())
            with Image.open(source_path) as image:
                bordered = ImageOps.expand(image, border=max(int(border_size), 1), fill=rgba)
                width, height = bordered.size
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                bordered.save(target_path)
        except Exception as exc:
            QMessageBox.warning(self, "Add Border", f"Failed to add border:\n{exc}")
            return

        action = "Created" if output_filename != str(entry.get("file", "") or "").replace("\\", "/") else "Updated"
        self._finalize_saved_image_output(
            entry,
            index,
            output_filename,
            f"{action} bordered image '{output_filename}' ({width} x {height}).",
        )

    def _apply_image_background(self, entry: dict, index: int, source_path: str, output_filename: str, color: QColor):
        try:
            from PIL import Image
        except Exception as exc:
            QMessageBox.warning(self, "Add Background", f"Pillow is required for background editing:\n{exc}")
            return

        source_dir = self._session.paths.source_dir
        if not source_dir:
            QMessageBox.warning(self, "Add Background", "Set Source Dir before editing images.")
            return

        target_path = normalize_path(os.path.join(source_dir, output_filename))
        if not _is_subpath(target_path, source_dir) and normalize_path(target_path) != normalize_path(source_path):
            QMessageBox.warning(self, "Add Background", "Output filename must stay inside Source Dir.")
            return

        existed_before = os.path.isfile(target_path)
        if normalize_path(target_path) != normalize_path(source_path) and existed_before:
            answer = QMessageBox.question(
                self,
                "Overwrite Image",
                f"Overwrite existing image?\n\n{output_filename}",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return

        try:
            rgba = (color.red(), color.green(), color.blue(), color.alpha())
            with Image.open(source_path) as image:
                overlay = image.convert("RGBA")
                background = Image.new("RGBA", overlay.size, rgba)
                composited = Image.alpha_composite(background, overlay)
                width, height = composited.size
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                composited.save(target_path)
        except Exception as exc:
            QMessageBox.warning(self, "Add Background", f"Failed to add background:\n{exc}")
            return

        action = "Created" if output_filename != str(entry.get("file", "") or "").replace("\\", "/") else "Updated"
        self._finalize_saved_image_output(
            entry,
            index,
            output_filename,
            f"{action} background image '{output_filename}' ({width} x {height}).",
        )

    def _apply_image_round_corners(self, entry: dict, index: int, source_path: str, output_filename: str, radius: int):
        try:
            from PIL import Image, ImageChops, ImageDraw
        except Exception as exc:
            QMessageBox.warning(self, "Round Corners", f"Pillow is required for corner rounding:\n{exc}")
            return

        source_dir = self._session.paths.source_dir
        if not source_dir:
            QMessageBox.warning(self, "Round Corners", "Set Source Dir before editing images.")
            return

        target_path = normalize_path(os.path.join(source_dir, output_filename))
        if not _is_subpath(target_path, source_dir) and normalize_path(target_path) != normalize_path(source_path):
            QMessageBox.warning(self, "Round Corners", "Output filename must stay inside Source Dir.")
            return

        existed_before = os.path.isfile(target_path)
        if normalize_path(target_path) != normalize_path(source_path) and existed_before:
            answer = QMessageBox.question(
                self,
                "Overwrite Image",
                f"Overwrite existing image?\n\n{output_filename}",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return

        try:
            with Image.open(source_path) as image:
                rounded = image.convert("RGBA")
                width, height = rounded.size
                max_radius = max(1, int(math.ceil(min(max(width, 1), max(height, 1)) / 2.0)))
                clamped_radius = min(max(int(radius or 1), 1), max_radius)
                mask = Image.new("L", rounded.size, 0)
                draw = ImageDraw.Draw(mask)
                draw.rounded_rectangle((0, 0, max(width - 1, 0), max(height - 1, 0)), radius=clamped_radius, fill=255)
                rounded.putalpha(ImageChops.multiply(rounded.getchannel("A"), mask))
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                rounded.save(target_path)
        except Exception as exc:
            QMessageBox.warning(self, "Round Corners", f"Failed to round image corners:\n{exc}")
            return

        action = "Created" if output_filename != str(entry.get("file", "") or "").replace("\\", "/") else "Updated"
        self._finalize_saved_image_output(
            entry,
            index,
            output_filename,
            f"{action} rounded image '{output_filename}' ({width} x {height}).",
        )

    def _apply_image_opacity(self, entry: dict, index: int, source_path: str, output_filename: str, opacity_percent: int):
        try:
            from PIL import Image
        except Exception as exc:
            QMessageBox.warning(self, "Adjust Opacity", f"Pillow is required for opacity editing:\n{exc}")
            return

        source_dir = self._session.paths.source_dir
        if not source_dir:
            QMessageBox.warning(self, "Adjust Opacity", "Set Source Dir before editing images.")
            return

        target_path = normalize_path(os.path.join(source_dir, output_filename))
        if not _is_subpath(target_path, source_dir) and normalize_path(target_path) != normalize_path(source_path):
            QMessageBox.warning(self, "Adjust Opacity", "Output filename must stay inside Source Dir.")
            return

        existed_before = os.path.isfile(target_path)
        if normalize_path(target_path) != normalize_path(source_path) and existed_before:
            answer = QMessageBox.question(
                self,
                "Overwrite Image",
                f"Overwrite existing image?\n\n{output_filename}",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return

        try:
            factor = max(1, min(int(opacity_percent or 100), 100)) / 100.0
            with Image.open(source_path) as image:
                faded = image.convert("RGBA")
                alpha = faded.getchannel("A").point(lambda value: max(0, min(255, int(round(float(value) * factor)))))
                faded.putalpha(alpha)
                width, height = faded.size
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                faded.save(target_path)
        except Exception as exc:
            QMessageBox.warning(self, "Adjust Opacity", f"Failed to adjust opacity:\n{exc}")
            return

        action = "Created" if output_filename != str(entry.get("file", "") or "").replace("\\", "/") else "Updated"
        self._finalize_saved_image_output(
            entry,
            index,
            output_filename,
            f"{action} image opacity for '{output_filename}' ({opacity_percent}% alpha, {width} x {height}).",
        )

    def _open_rotate_image_helper(self):
        section, index, entry = self._selected_simple_asset_context()
        if entry is None or section != "img":
            QMessageBox.warning(self, "Rotate Image", "Select an image asset in Simple mode first.")
            return
        file_name = str(entry.get("file", "") or "").strip()
        resolved_path = self._resolve_entry_path("img", "file", file_name)
        if not resolved_path or not os.path.isfile(resolved_path):
            QMessageBox.warning(self, "Rotate Image", f"Image file does not exist:\n{resolved_path or file_name}")
            return

        pixmap = QPixmap(resolved_path)
        if pixmap.isNull():
            QMessageBox.warning(self, "Rotate Image", f"Qt could not decode the selected image:\n{resolved_path}")
            return

        dialog = _QuickImageRotateDialog(
            width=pixmap.width(),
            height=pixmap.height(),
            output_filename=file_name,
            parent=self,
        )
        if dialog.exec_() != QDialog.Accepted:
            return

        output_filename = dialog.output_filename()
        if not output_filename:
            QMessageBox.warning(self, "Rotate Image", "Enter an output filename.")
            return
        if os.path.isabs(output_filename):
            QMessageBox.warning(self, "Rotate Image", "Output filename must stay inside Source Dir.")
            return

        normalized_output = output_filename.replace("\\", "/").strip().lstrip("/")
        if not normalized_output or normalized_output.startswith(".."):
            QMessageBox.warning(self, "Rotate Image", "Output filename must stay inside Source Dir.")
            return

        self._apply_image_rotation(entry, index, resolved_path, normalized_output, dialog.rotation_degrees())

    def _apply_image_rotation(self, entry: dict, index: int, source_path: str, output_filename: str, rotation_degrees: int):
        try:
            from PIL import Image
        except Exception as exc:
            QMessageBox.warning(self, "Rotate Image", f"Pillow is required for image rotation:\n{exc}")
            return

        source_dir = self._session.paths.source_dir
        if not source_dir:
            QMessageBox.warning(self, "Rotate Image", "Set Source Dir before rotating images.")
            return

        target_path = normalize_path(os.path.join(source_dir, output_filename))
        if not _is_subpath(target_path, source_dir) and normalize_path(target_path) != normalize_path(source_path):
            QMessageBox.warning(self, "Rotate Image", "Output filename must stay inside Source Dir.")
            return

        existed_before = os.path.isfile(target_path)
        if normalize_path(target_path) != normalize_path(source_path) and existed_before:
            answer = QMessageBox.question(
                self,
                "Overwrite Image",
                f"Overwrite existing image?\n\n{output_filename}",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return

        try:
            with Image.open(source_path) as image:
                rotated = image.rotate(-int(rotation_degrees), expand=True)
                width, height = rotated.size
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                rotated.save(target_path)
        except Exception as exc:
            QMessageBox.warning(self, "Rotate Image", f"Failed to rotate image:\n{exc}")
            return

        action = "Created" if output_filename != str(entry.get("file", "") or "").replace("\\", "/") else "Updated"
        self._finalize_saved_image_output(
            entry,
            index,
            output_filename,
            f"{action} rotated image '{output_filename}' ({width} x {height}).",
        )

    def _open_flip_image_helper(self):
        section, index, entry = self._selected_simple_asset_context()
        if entry is None or section != "img":
            QMessageBox.warning(self, "Flip Image", "Select an image asset in Simple mode first.")
            return
        file_name = str(entry.get("file", "") or "").strip()
        resolved_path = self._resolve_entry_path("img", "file", file_name)
        if not resolved_path or not os.path.isfile(resolved_path):
            QMessageBox.warning(self, "Flip Image", f"Image file does not exist:\n{resolved_path or file_name}")
            return

        pixmap = QPixmap(resolved_path)
        if pixmap.isNull():
            QMessageBox.warning(self, "Flip Image", f"Qt could not decode the selected image:\n{resolved_path}")
            return

        dialog = _QuickImageFlipDialog(output_filename=file_name, parent=self)
        if dialog.exec_() != QDialog.Accepted:
            return

        output_filename = dialog.output_filename()
        if not output_filename:
            QMessageBox.warning(self, "Flip Image", "Enter an output filename.")
            return
        if os.path.isabs(output_filename):
            QMessageBox.warning(self, "Flip Image", "Output filename must stay inside Source Dir.")
            return

        normalized_output = output_filename.replace("\\", "/").strip().lstrip("/")
        if not normalized_output or normalized_output.startswith(".."):
            QMessageBox.warning(self, "Flip Image", "Output filename must stay inside Source Dir.")
            return

        self._apply_image_flip(entry, index, resolved_path, normalized_output, dialog.flip_mode())

    def _apply_image_flip(self, entry: dict, index: int, source_path: str, output_filename: str, flip_mode: str):
        try:
            from PIL import Image
        except Exception as exc:
            QMessageBox.warning(self, "Flip Image", f"Pillow is required for image flipping:\n{exc}")
            return

        source_dir = self._session.paths.source_dir
        if not source_dir:
            QMessageBox.warning(self, "Flip Image", "Set Source Dir before flipping images.")
            return

        target_path = normalize_path(os.path.join(source_dir, output_filename))
        if not _is_subpath(target_path, source_dir) and normalize_path(target_path) != normalize_path(source_path):
            QMessageBox.warning(self, "Flip Image", "Output filename must stay inside Source Dir.")
            return

        existed_before = os.path.isfile(target_path)
        if normalize_path(target_path) != normalize_path(source_path) and existed_before:
            answer = QMessageBox.question(
                self,
                "Overwrite Image",
                f"Overwrite existing image?\n\n{output_filename}",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return

        try:
            with Image.open(source_path) as image:
                if flip_mode == "vertical":
                    transformed = image.transpose(Image.FLIP_TOP_BOTTOM)
                else:
                    transformed = image.transpose(Image.FLIP_LEFT_RIGHT)
                width, height = transformed.size
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                transformed.save(target_path)
        except Exception as exc:
            QMessageBox.warning(self, "Flip Image", f"Failed to flip image:\n{exc}")
            return

        action = "Created" if output_filename != str(entry.get("file", "") or "").replace("\\", "/") else "Updated"
        direction = "vertical" if flip_mode == "vertical" else "horizontal"
        self._finalize_saved_image_output(
            entry,
            index,
            output_filename,
            f"{action} {direction}-flipped image '{output_filename}' ({width} x {height}).",
        )

    def _open_crop_image_helper(self):
        section, index, entry = self._selected_simple_asset_context()
        if entry is None or section != "img":
            QMessageBox.warning(self, "Crop Image", "Select an image asset in Simple mode first.")
            return
        file_name = str(entry.get("file", "") or "").strip()
        resolved_path = self._resolve_entry_path("img", "file", file_name)
        if not resolved_path or not os.path.isfile(resolved_path):
            QMessageBox.warning(self, "Crop Image", f"Image file does not exist:\n{resolved_path or file_name}")
            return

        pixmap = QPixmap(resolved_path)
        if pixmap.isNull():
            QMessageBox.warning(self, "Crop Image", f"Qt could not decode the selected image:\n{resolved_path}")
            return

        dialog = _QuickImageCropDialog(
            width=pixmap.width(),
            height=pixmap.height(),
            output_filename=file_name,
            parent=self,
        )
        if dialog.exec_() != QDialog.Accepted:
            return

        output_filename = dialog.output_filename()
        if not output_filename:
            QMessageBox.warning(self, "Crop Image", "Enter an output filename.")
            return
        if os.path.isabs(output_filename):
            QMessageBox.warning(self, "Crop Image", "Output filename must stay inside Source Dir.")
            return

        normalized_output = output_filename.replace("\\", "/").strip().lstrip("/")
        if not normalized_output or normalized_output.startswith(".."):
            QMessageBox.warning(self, "Crop Image", "Output filename must stay inside Source Dir.")
            return

        x = dialog.x_value()
        y = dialog.y_value()
        width = dialog.width_value()
        height = dialog.height_value()
        if x < 0 or y < 0 or width <= 0 or height <= 0 or x + width > pixmap.width() or y + height > pixmap.height():
            QMessageBox.warning(self, "Crop Image", "Crop rectangle must stay inside the image bounds.")
            return

        self._apply_image_crop(entry, index, resolved_path, normalized_output, x, y, width, height)

    def _apply_image_crop(self, entry: dict, index: int, source_path: str, output_filename: str, x: int, y: int, width: int, height: int):
        try:
            from PIL import Image
        except Exception as exc:
            QMessageBox.warning(self, "Crop Image", f"Pillow is required for image cropping:\n{exc}")
            return

        source_dir = self._session.paths.source_dir
        if not source_dir:
            QMessageBox.warning(self, "Crop Image", "Set Source Dir before cropping images.")
            return

        target_path = normalize_path(os.path.join(source_dir, output_filename))
        if not _is_subpath(target_path, source_dir) and normalize_path(target_path) != normalize_path(source_path):
            QMessageBox.warning(self, "Crop Image", "Output filename must stay inside Source Dir.")
            return

        existed_before = os.path.isfile(target_path)
        if normalize_path(target_path) != normalize_path(source_path) and existed_before:
            answer = QMessageBox.question(
                self,
                "Overwrite Image",
                f"Overwrite existing image?\n\n{output_filename}",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return

        try:
            with Image.open(source_path) as image:
                cropped = image.crop((int(x), int(y), int(x + width), int(y + height)))
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                cropped.save(target_path)
        except Exception as exc:
            QMessageBox.warning(self, "Crop Image", f"Failed to crop image:\n{exc}")
            return

        action = "Created" if output_filename != str(entry.get("file", "") or "").replace("\\", "/") else "Updated"
        self._finalize_saved_image_output(
            entry,
            index,
            output_filename,
            f"{action} cropped image '{output_filename}' ({width} x {height}).",
        )

    def _finalize_saved_image_output(self, entry: dict, index: int, output_filename: str, status_message: str):
        current_file = str(entry.get("file", "") or "").replace("\\", "/")
        if output_filename != current_file:
            new_entry = copy.deepcopy(entry if isinstance(entry, dict) else {})
            new_entry["file"] = output_filename
            new_entry["name"] = os.path.splitext(os.path.basename(output_filename))[0]
            self._session.section_entries("img").append(new_entry)
            self._active_section = "img"
            self._active_entry_index = len(self._session.section_entries("img")) - 1
            self._mark_dirty()
        else:
            self._active_section = "img"
            self._active_entry_index = index

        self._refresh_entry_table()
        self._update_merged_preview()
        self._update_raw_editor()
        self._set_status(status_message)

    # -- Browsing helpers ----------------------------------------------

    def _browse_config_target_path(self):
        start_dir = self._default_open_dir()
        default_name = self._config_path_edit.text().strip() or os.path.join(start_dir, APP_RESOURCE_CONFIG_FILENAME)
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Choose Resource Config Path",
            default_name,
            "Resource Config (*.json);;All files (*)",
        )
        if not path:
            return
        self._config_path_edit.setText(normalize_path(path))
        self._on_path_edited("config_path", self._config_path_edit)

    def _browse_directory_path(self, field_name: str):
        start_dir = self._directory_value_for_field(field_name) or self._default_open_dir()
        path = QFileDialog.getExistingDirectory(self, "Choose Directory", start_dir)
        if not path:
            return
        widget = self._path_widget_for_field(field_name)
        widget.setText(normalize_path(path))
        self._on_path_edited(field_name, widget)

    def _browse_entry_field(self, field_spec):
        current_entry = self._current_entry()
        if current_entry is None:
            return
        start_dir = self._entry_browse_start_dir(field_spec, current_entry)
        if field_spec.name == "text" and self._active_section == "font":
            paths, _ = QFileDialog.getOpenFileNames(self, f"Choose {field_spec.label}", start_dir, field_spec.file_filter)
            if not paths:
                return
            items = self._font_text_items_from_value(current_entry.get("text", ""))
            for path in paths:
                stored_item = self._normalize_selected_resource_path(field_spec, normalize_path(path))
                if stored_item is None or stored_item in items:
                    continue
                items.append(stored_item)
            stored_value = ",".join(items)
        else:
            path, _ = QFileDialog.getOpenFileName(self, f"Choose {field_spec.label}", start_dir, field_spec.file_filter)
            if not path:
                return
            stored_value = self._normalize_selected_resource_path(field_spec, normalize_path(path))
            if stored_value is None:
                return
        current_value = str(current_entry.get(field_spec.name, "") or "")
        if current_value == stored_value:
            return
        self._update_current_entry_field(
            field_spec.name,
            stored_value,
            normalize_font_text=(field_spec.name == "text" and self._active_section == "font"),
            sync_widget_text=(field_spec.name == "text" and self._active_section == "font"),
        )

    def _normalize_selected_resource_path(self, field_spec, selected_path: str):
        source_dir = self._session.paths.source_dir
        selected_path = normalize_path(selected_path)
        if field_spec.name == "file" and self._active_section == "font":
            if not source_dir or _is_subpath(selected_path, source_dir):
                return selected_path if not source_dir else os.path.relpath(selected_path, source_dir).replace("\\", "/")
            return selected_path

        if not source_dir:
            QMessageBox.warning(
                self,
                "Source Directory Missing",
                "Set Source Dir before importing files that must be stored relative to it.",
            )
            return None

        if _is_subpath(selected_path, source_dir):
            return os.path.relpath(selected_path, source_dir).replace("\\", "/")

        answer = QMessageBox.question(
            self,
            "Copy Into Source Dir",
            f"{selected_path}\n\nCopy this file into:\n{source_dir}\n\nRequired for generation.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if answer != QMessageBox.Yes:
            return None

        os.makedirs(source_dir, exist_ok=True)
        filename = os.path.basename(selected_path)
        target_path = os.path.join(source_dir, filename)
        if normalize_path(selected_path) != normalize_path(target_path):
            shutil.copy2(selected_path, target_path)
        return filename.replace("\\", "/")

    # -- Utility --------------------------------------------------------

    def _default_open_dir(self) -> str:
        for candidate in (
            self._session.paths.config_path,
            self._session.paths.source_dir,
            self._session.paths.workspace_dir,
            os.getcwd(),
        ):
            if not candidate:
                continue
            existing = normalize_path(candidate)
            while existing and not os.path.exists(existing):
                parent = os.path.dirname(existing)
                if parent == existing:
                    existing = ""
                    break
                existing = parent
            if existing:
                return existing if os.path.isdir(existing) else os.path.dirname(existing)
        return normalize_path(os.getcwd())

    def _directory_value_for_field(self, field_name: str) -> str:
        value = getattr(self._session.paths, field_name, "")
        return value or self._default_open_dir()

    def _path_widget_for_field(self, field_name: str):
        return {
            "config_path": self._config_path_edit,
            "source_dir": self._source_dir_edit,
            "workspace_dir": self._workspace_dir_edit,
            "bin_output_dir": self._bin_output_dir_edit,
        }[field_name]

    def _entry_browse_start_dir(self, field_spec, entry: dict) -> str:
        if field_spec.name == "text" and self._active_section == "font":
            return self._session.paths.source_dir or self._default_open_dir()
        file_name = str(entry.get(field_spec.name, "") or "").strip()
        if file_name:
            resolved = self._resolve_entry_path(self._active_section, field_spec.name, file_name)
            if resolved and os.path.exists(resolved):
                return os.path.dirname(resolved)
        return self._session.paths.source_dir or self._default_open_dir()

    def _resolve_entry_path(self, section: str, field_name: str, value: str) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        if os.path.isabs(raw):
            return normalize_path(raw)
        if section == "font" and field_name == "file" and raw.replace("\\", "/").startswith("build_in/"):
            generator_script = self._session.sdk_root and os.path.join(self._session.sdk_root, "scripts", "tools", "app_resource_generate.py")
            if generator_script and os.path.isfile(generator_script):
                return normalize_path(os.path.join(os.path.dirname(generator_script), "build_in", raw.replace("\\", "/")[len("build_in/"):]))
            return raw
        source_dir = self._session.paths.source_dir
        if not source_dir:
            return ""
        return normalize_path(os.path.join(source_dir, raw))

    def _apply_source_dir_change(self, new_source_dir: str):
        previous_paths = GenerationPaths(
            config_path=self._session.paths.config_path,
            source_dir=self._session.paths.source_dir,
            workspace_dir=self._session.paths.workspace_dir,
            bin_output_dir=self._session.paths.bin_output_dir,
        )
        normalized_source_dir = normalize_path(new_source_dir)
        self._session.paths.source_dir = normalized_source_dir

        previous_defaults = infer_generation_paths(
            previous_paths.config_path,
            source_dir=previous_paths.source_dir,
        )
        new_defaults = infer_generation_paths(
            previous_paths.config_path,
            source_dir=normalized_source_dir,
        )
        if previous_paths.workspace_dir in {"", previous_defaults.workspace_dir}:
            self._session.paths.workspace_dir = new_defaults.workspace_dir
        if previous_paths.bin_output_dir in {"", previous_defaults.bin_output_dir}:
            self._session.paths.bin_output_dir = new_defaults.bin_output_dir

    def _copy_supported_assets_into_source_dir(self, import_root: str, source_dir: str, asset_paths, text_paths):
        copied_assets: list[tuple[str, str]] = []
        copied_texts: list[str] = []
        copied_files = 0

        for text_path in text_paths:
            relative_path = _relative_import_path(text_path, import_root)
            target_path = normalize_path(os.path.join(source_dir, relative_path))
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            if normalize_path(text_path) != target_path:
                shutil.copy2(text_path, target_path)
                copied_files += 1
            copied_texts.append(target_path)

        for section, asset_path in asset_paths:
            relative_path = _relative_import_path(asset_path, import_root)
            target_path = normalize_path(os.path.join(source_dir, relative_path))
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            if normalize_path(asset_path) != target_path:
                shutil.copy2(asset_path, target_path)
                copied_files += 1
            copied_assets.append((section, target_path))

        return copied_assets, copied_texts, copied_files

    def _build_entries_from_asset_paths(self, asset_paths, text_paths, source_dir: str):
        text_lookup: dict[tuple[str, str], str] = {}
        for text_path in text_paths:
            relative_text = os.path.relpath(text_path, source_dir).replace("\\", "/")
            key = (
                os.path.dirname(relative_text).replace("\\", "/"),
                os.path.splitext(os.path.basename(relative_text))[0].lower(),
            )
            text_lookup[key] = relative_text

        entries_by_section = {section: [] for section in KNOWN_RESOURCE_SECTIONS}
        for section, asset_path in sorted(asset_paths, key=lambda item: (item[0], item[1].lower())):
            relative_file = os.path.relpath(asset_path, source_dir).replace("\\", "/")
            entry = default_entry_for_section(section)
            entry["file"] = relative_file
            entry["name"] = os.path.splitext(os.path.basename(relative_file))[0]
            if section == "font":
                text_key = (
                    os.path.dirname(relative_file).replace("\\", "/"),
                    os.path.splitext(os.path.basename(relative_file))[0].lower(),
                )
                matched_text = text_lookup.get(text_key)
                if matched_text:
                    entry["text"] = matched_text
            elif section == "mp4":
                for field_name, value in _detect_video_metadata(asset_path).items():
                    if value not in (None, "", 0):
                        entry[field_name] = value
            entries_by_section[section].append(entry)
        return entries_by_section

    def _merge_discovered_entries(self, entries_by_section):
        added = 0
        updated = 0
        for section in KNOWN_RESOURCE_SECTIONS:
            existing_entries = self._session.section_entries(section)
            file_index: dict[str, dict] = {}
            for entry in existing_entries:
                if not isinstance(entry, dict):
                    continue
                key = str(entry.get("file", "") or "").replace("\\", "/").lower()
                if key:
                    file_index[key] = entry

            for entry in entries_by_section.get(section, []):
                key = str(entry.get("file", "") or "").replace("\\", "/").lower()
                if not key:
                    continue
                existing = file_index.get(key)
                if existing is None:
                    existing_entries.append(copy.deepcopy(entry))
                    file_index[key] = existing_entries[-1]
                    added += 1
                    continue

                changed = False
                for field_name in ("name", "text"):
                    incoming = str(entry.get(field_name, "") or "").strip()
                    if incoming and not str(existing.get(field_name, "") or "").strip():
                        existing[field_name] = incoming
                        changed = True
                if section == "mp4":
                    for field_name in ("fps", "width", "height"):
                        incoming = entry.get(field_name, "")
                        current = existing.get(field_name, "")
                        if incoming in (None, "", 0) or current not in (None, "", 0):
                            continue
                        existing[field_name] = incoming
                        changed = True
                if changed:
                    updated += 1
        return added, updated

    def _charset_helper_context(self):
        entry = self._current_entry()
        if self._active_section == "font" and entry is not None:
            return "font", str(entry.get("file", "") or "")
        font_entries = self._session.section_entries("font")
        if len(font_entries) == 1 and isinstance(font_entries[0], dict):
            return "font", str(font_entries[0].get("file", "") or "")
        return "text", ""

    def _assign_generated_text_to_font(self, filename: str) -> bool:
        target_index = -1
        if self._active_section == "font" and self._current_entry() is not None:
            target_index = self._active_entry_index
        else:
            font_entries = self._session.section_entries("font")
            if len(font_entries) == 1:
                target_index = 0
        if target_index < 0:
            return False

        font_entries = self._session.section_entries("font")
        if not (0 <= target_index < len(font_entries)):
            return False
        entry = font_entries[target_index]
        if not isinstance(entry, dict):
            return False

        existing = str(entry.get("text", "") or "").strip()
        items = [item.strip() for item in existing.split(",") if item.strip()]
        if filename in items:
            return False
        items.append(filename)
        self._session.update_entry_value("font", target_index, "text", ",".join(items))
        self._active_section = "font"
        self._active_entry_index = target_index
        self._mark_dirty()
        self._refresh_section_selection()
        self._refresh_entry_table()
        self._update_form()
        self._refresh_simple_page()
        return True

    def _mark_dirty(self):
        self._dirty = True
        self._update_title()

    def _set_status(self, message: str):
        self._status_label.setText(message or "")

    def _append_log(self, message: str):
        if message:
            self._log_output.appendPlainText(message)

    def _log_validation_issues(self, issues, *, prefix: str):
        if not issues:
            return
        self._append_log(f"{prefix}:")
        for issue in issues:
            scope = issue.section or "session"
            if issue.entry_index >= 0:
                scope = f"{scope}[{issue.entry_index}]"
            if issue.field:
                scope = f"{scope}.{issue.field}"
            self._append_log(f"- {scope}: {issue.message}")

    def _update_title(self):
        config_path = self._session.paths.config_path or "Untitled"
        suffix = " *" if self.has_unsaved_changes() else ""
        self.setWindowTitle(f"Resource Generator - {config_path}{suffix}")

    def _capture_clean_snapshot(self):
        self._clean_paths = GenerationPaths(
            config_path=self._session.paths.config_path,
            source_dir=self._session.paths.source_dir,
            workspace_dir=self._session.paths.workspace_dir,
            bin_output_dir=self._session.paths.bin_output_dir,
        )
        self._clean_user_data = copy.deepcopy(self._session.user_data)

    def _restore_clean_snapshot(self):
        self._apply_paths_and_data(self._clean_paths, copy.deepcopy(self._clean_user_data), dirty=False)

    def _rebase_inferred_paths(self, previous_paths: GenerationPaths, new_config_path: str):
        previous_defaults = infer_generation_paths(previous_paths.config_path)
        new_defaults = infer_generation_paths(new_config_path)

        if previous_paths.source_dir in {"", previous_defaults.source_dir}:
            self._session.paths.source_dir = new_defaults.source_dir
        if previous_paths.workspace_dir in {"", previous_defaults.workspace_dir}:
            self._session.paths.workspace_dir = new_defaults.workspace_dir
        if previous_paths.bin_output_dir in {"", previous_defaults.bin_output_dir}:
            self._session.paths.bin_output_dir = new_defaults.bin_output_dir

    def _confirm_discard_changes(self) -> bool:
        if not self.has_unsaved_changes():
            return True
        answer = QMessageBox.question(
            self,
            "Discard Changes",
            "Discard unsaved resource config changes?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            self._restore_clean_snapshot()
        return answer == QMessageBox.Yes

    def closeEvent(self, event):
        if not self._confirm_discard_changes():
            event.ignore()
            return
        self._save_view_state()
        super().closeEvent(event)

    def _restore_view_state(self):
        workspace_state = self._config.workspace_state if isinstance(self._config.workspace_state, dict) else {}
        saved_state = workspace_state.get(_RESOURCE_GENERATOR_VIEW_STATE_KEY, {})
        if not isinstance(saved_state, dict):
            return

        self._ui_mode = "professional" if saved_state.get("ui_mode") == "professional" else "simple"
        filter_value = str(saved_state.get("simple_asset_type_filter", "all") or "all")
        filter_index = self._simple_asset_type_filter.findData(filter_value)
        with QSignalBlocker(self._simple_asset_type_filter):
            self._simple_asset_type_filter.setCurrentIndex(filter_index if filter_index >= 0 else 0)
        with QSignalBlocker(self._simple_asset_search_edit):
            self._simple_asset_search_edit.setText(str(saved_state.get("simple_asset_search", "") or ""))
        try:
            restored_sort_column = int(saved_state.get("simple_asset_sort_column", -1))
        except (TypeError, ValueError):
            restored_sort_column = -1
        if not (-1 <= restored_sort_column < self._simple_asset_table.columnCount()):
            restored_sort_column = -1
        self._simple_asset_sort_column = restored_sort_column
        self._simple_asset_sort_descending = bool(saved_state.get("simple_asset_sort_descending", False)) if restored_sort_column >= 0 else False
        self._apply_simple_asset_sort_indicator()

        self._pending_simple_workspace_splitter_sizes = _coerce_int_list(
            saved_state.get("simple_workspace_splitter_sizes"),
            expected_length=3,
            minimum=0,
            require_nonzero_sum=True,
        )
        self._pending_simple_preview_splitter_sizes = _coerce_int_list(
            saved_state.get("simple_preview_splitter_sizes"),
            expected_length=2,
            minimum=0,
            require_nonzero_sum=True,
        )
        self._pending_simple_asset_column_widths = _coerce_int_list(
            saved_state.get("simple_asset_column_widths"),
            expected_length=self._simple_asset_table.columnCount(),
            minimum=24,
        )

    def _apply_pending_view_state_layouts(self):
        if self._pending_simple_workspace_splitter_sizes:
            self._simple_workspace_splitter.setSizes(self._pending_simple_workspace_splitter_sizes)
            self._pending_simple_workspace_splitter_sizes = None
        if self._pending_simple_preview_splitter_sizes:
            self._simple_preview_splitter.setSizes(self._pending_simple_preview_splitter_sizes)
            self._pending_simple_preview_splitter_sizes = None
        if self._pending_simple_asset_column_widths:
            header = self._simple_asset_table.horizontalHeader()
            for column, width in enumerate(self._pending_simple_asset_column_widths):
                header.resizeSection(column, width)
            self._pending_simple_asset_column_widths = None

    def _capture_view_state(self) -> dict:
        workspace_state = self._config.workspace_state if isinstance(self._config.workspace_state, dict) else {}
        saved_state = workspace_state.get(_RESOURCE_GENERATOR_VIEW_STATE_KEY, {})
        saved_state = saved_state if isinstance(saved_state, dict) else {}
        use_live_simple_layout = self._ui_mode == "simple" and self._workspace_stack.currentWidget() is self._simple_page
        return {
            "ui_mode": self._ui_mode,
            "simple_workspace_splitter_sizes": (
                _coerce_int_list(
                    self._simple_workspace_splitter.sizes(),
                    expected_length=3,
                    minimum=0,
                    require_nonzero_sum=True,
                )
                if use_live_simple_layout
                else None
            ) or _coerce_int_list(
                saved_state.get("simple_workspace_splitter_sizes"),
                expected_length=3,
                minimum=0,
                require_nonzero_sum=True,
            ) or list(_DEFAULT_SIMPLE_WORKSPACE_SPLITTER_SIZES),
            "simple_preview_splitter_sizes": (
                _coerce_int_list(
                    self._simple_preview_splitter.sizes(),
                    expected_length=2,
                    minimum=0,
                    require_nonzero_sum=True,
                )
                if use_live_simple_layout
                else None
            ) or _coerce_int_list(
                saved_state.get("simple_preview_splitter_sizes"),
                expected_length=2,
                minimum=0,
                require_nonzero_sum=True,
            ) or list(_DEFAULT_SIMPLE_PREVIEW_SPLITTER_SIZES),
            "simple_asset_column_widths": _coerce_int_list(
                [self._simple_asset_table.columnWidth(column) for column in range(self._simple_asset_table.columnCount())],
                expected_length=self._simple_asset_table.columnCount(),
                minimum=24,
            ) or _coerce_int_list(
                saved_state.get("simple_asset_column_widths"),
                expected_length=self._simple_asset_table.columnCount(),
                minimum=24,
            ) or list(_DEFAULT_SIMPLE_ASSET_COLUMN_WIDTHS),
            "simple_asset_type_filter": str(self._simple_asset_type_filter.currentData() or "all"),
            "simple_asset_search": str(self._simple_asset_search_edit.text() or ""),
            "simple_asset_sort_column": self._simple_asset_sort_column,
            "simple_asset_sort_descending": self._simple_asset_sort_descending,
        }

    def _remember_view_state(self):
        if not self._view_state_updates_enabled:
            return
        if not isinstance(self._config.workspace_state, dict):
            self._config.workspace_state = {}
        self._config.workspace_state[_RESOURCE_GENERATOR_VIEW_STATE_KEY] = self._capture_view_state()

    def _save_view_state(self):
        self._remember_view_state()
        self._config.save()


def _is_subpath(path: str, root: str) -> bool:
    path = normalize_path(path)
    root = normalize_path(root)
    if not path or not root:
        return False
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:
        return False


def _coerce_int_list(values, *, expected_length: int, minimum: int, require_nonzero_sum: bool = False) -> list[int] | None:
    if not isinstance(values, (list, tuple)) or len(values) != expected_length:
        return None
    normalized = []
    for value in values:
        try:
            number = int(value)
        except (TypeError, ValueError):
            return None
        if number < minimum:
            return None
        normalized.append(number)
    if require_nonzero_sum and sum(normalized) <= 0:
        return None
    return normalized


def _local_paths_from_mime_data(mime_data) -> list[str]:
    if mime_data is None or not hasattr(mime_data, "hasUrls") or not mime_data.hasUrls():
        return []
    paths: list[str] = []
    seen: set[str] = set()
    for url in mime_data.urls():
        path = normalize_path(url.toLocalFile()) if hasattr(url, "toLocalFile") else ""
        if not path or path in seen:
            continue
        seen.add(path)
        paths.append(path)
    return paths


def _collect_importable_drop_files(local_paths) -> tuple[list[str], list[str]]:
    directories: list[str] = []
    import_files: list[str] = []
    seen_files: set[str] = set()

    def _append_file(path: str):
        normalized = normalize_path(path)
        if not normalized or normalized in seen_files or not os.path.isfile(normalized):
            return
        seen_files.add(normalized)
        import_files.append(normalized)

    for raw_path in local_paths:
        full_path = normalize_path(raw_path)
        if not full_path:
            continue
        if os.path.isdir(full_path):
            if full_path not in directories:
                directories.append(full_path)
            continue

    direct_assets, direct_texts, _skipped_paths = _classify_selected_asset_files(
        [path for path in local_paths if normalize_path(path) and os.path.isfile(normalize_path(path))]
    )
    for _section, path in direct_assets:
        _append_file(path)
    for path in direct_texts:
        _append_file(path)

    for directory in directories:
        discovered_assets, discovered_texts = _discover_supported_assets(directory)
        for _section, path in discovered_assets:
            _append_file(path)
        for path in discovered_texts:
            _append_file(path)

    return directories, import_files


def _discover_supported_assets(root_dir: str):
    discovered_assets: list[tuple[str, str]] = []
    discovered_texts: list[str] = []
    for current_root, _dirs, files in os.walk(root_dir):
        for filename in files:
            full_path = normalize_path(os.path.join(current_root, filename))
            extension = os.path.splitext(filename)[1].lower()
            if extension in _TEXT_FILE_EXTENSIONS:
                discovered_texts.append(full_path)
                continue
            section = _section_for_asset_extension(extension)
            if section:
                discovered_assets.append((section, full_path))
    return discovered_assets, discovered_texts


def _classify_selected_asset_files(file_paths):
    discovered_assets: list[tuple[str, str]] = []
    discovered_texts: list[str] = []
    skipped_paths: list[str] = []
    seen_paths: set[str] = set()
    seen_texts: set[str] = set()

    for raw_path in file_paths:
        full_path = normalize_path(raw_path)
        if not full_path or full_path in seen_paths:
            continue
        seen_paths.add(full_path)

        if not os.path.isfile(full_path):
            skipped_paths.append(full_path)
            continue

        extension = os.path.splitext(full_path)[1].lower()
        if extension in _TEXT_FILE_EXTENSIONS:
            if full_path not in seen_texts:
                discovered_texts.append(full_path)
                seen_texts.add(full_path)
            continue

        section = _section_for_asset_extension(extension)
        if not section:
            skipped_paths.append(full_path)
            continue

        discovered_assets.append((section, full_path))
        if section == "font":
            sibling_text = normalize_path(os.path.splitext(full_path)[0] + ".txt")
            if sibling_text and os.path.isfile(sibling_text) and sibling_text not in seen_texts:
                discovered_texts.append(sibling_text)
                seen_texts.add(sibling_text)

    return discovered_assets, discovered_texts, skipped_paths


def _common_parent_directory(paths) -> str:
    normalized_paths = [normalize_path(path) for path in paths if path]
    if not normalized_paths:
        return ""
    try:
        common_path = os.path.commonpath(normalized_paths)
    except ValueError:
        common_path = os.path.dirname(normalized_paths[0])
    if not os.path.isdir(common_path):
        common_path = os.path.dirname(common_path)
    return normalize_path(common_path)


def _relative_import_path(path: str, import_root: str) -> str:
    full_path = normalize_path(path)
    root = normalize_path(import_root)
    if root and _is_subpath(full_path, root):
        return os.path.relpath(full_path, root).replace("\\", "/")
    return os.path.basename(full_path)


def _supported_asset_file_filter() -> str:
    all_extensions = sorted(_IMAGE_FILE_EXTENSIONS | _FONT_FILE_EXTENSIONS | _VIDEO_FILE_EXTENSIONS | _TEXT_FILE_EXTENSIONS)
    image_extensions = sorted(_IMAGE_FILE_EXTENSIONS)
    font_extensions = sorted(_FONT_FILE_EXTENSIONS)
    video_extensions = sorted(_VIDEO_FILE_EXTENSIONS)
    text_extensions = sorted(_TEXT_FILE_EXTENSIONS)

    def _pattern(extensions):
        return " ".join(f"*{extension}" for extension in extensions)

    return (
        f"Supported Assets ({_pattern(all_extensions)});;"
        f"Images ({_pattern(image_extensions)});;"
        f"Fonts ({_pattern(font_extensions)});;"
        f"Videos ({_pattern(video_extensions)});;"
        f"Text Files ({_pattern(text_extensions)});;"
        "All files (*)"
    )


def _resource_kind_label(section: str) -> str:
    return {
        "img": "image",
        "font": "font",
        "mp4": "video",
    }.get(str(section or ""), str(section or "asset"))


def _resource_sort_key(section: str, entry) -> tuple[str, str]:
    item = entry if isinstance(entry, dict) else {}
    file_name = str(item.get("file", "") or "").replace("\\", "/").strip().lower()
    label = section_entry_label(section, item, 0).strip().lower()
    return file_name, label


def _duplicated_resource_name(section: str, entry, existing_entries) -> str:
    item = entry if isinstance(entry, dict) else {}
    base_name = str(item.get("name", "") or "").strip()
    if not base_name:
        base_name = _resource_name_from_file(item.get("file", ""))
    if not base_name:
        base_name = _resource_kind_label(section)

    existing_names = {
        str((candidate or {}).get("name", "") or "").strip().lower()
        for candidate in existing_entries
        if isinstance(candidate, dict)
    }
    attempt = f"{base_name}_copy"
    suffix = 2
    while attempt.strip().lower() in existing_names:
        attempt = f"{base_name}_copy{suffix}"
        suffix += 1
    return attempt


def _resource_name_from_file(file_name) -> str:
    normalized = str(file_name or "").replace("\\", "/").strip()
    if not normalized:
        return ""
    return os.path.splitext(os.path.basename(normalized))[0].strip()


def _quick_font_text_sample_lines() -> list[str]:
    return [
        "HELLO",
        "Designer",
        "Quick Brown Fox",
        "1234",
    ]


def _default_new_font_text_file_body() -> str:
    lines = _quick_font_text_sample_lines()
    return "\n".join(lines) + ("\n" if lines else "")


def _default_quick_font_preview_text() -> str:
    return "HELLO Designer 1234"


def _safe_quick_placeholder_stem(value: str, *, fallback: str) -> str:
    cleaned = []
    for character in str(value or "").strip():
        if character.isalnum() or character in {"-", "_"}:
            cleaned.append(character)
        else:
            cleaned.append("_")
    stem = "".join(cleaned).strip("_")
    while "__" in stem:
        stem = stem.replace("__", "_")
    return stem or str(fallback or "placeholder")


def _build_quick_placeholder_pixmap(label: str, *, width: int, height: int) -> QPixmap:
    safe_width = max(int(width or 0), 16)
    safe_height = max(int(height or 0), 16)
    text = str(label or "").strip() or "Placeholder"
    seed = sum((index + 1) * ord(character) for index, character in enumerate(text))
    hue = seed % 360

    background = QColor.fromHsv(hue, 48, 232)
    border = QColor.fromHsv(hue, 92, 150)
    accent = QColor.fromHsv((hue + 28) % 360, 64, 246)

    pixmap = QPixmap(safe_width, safe_height)
    pixmap.fill(background)

    painter = QPainter(pixmap)
    try:
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)
        painter.setBrush(accent)
        painter.drawRect(0, 0, safe_width, max(10, safe_height // 6))

        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(border, 2))
        painter.drawRect(1, 1, safe_width - 2, safe_height - 2)

        font = QFont()
        font.setBold(True)
        font.setPointSize(max(10, min(safe_width // 11, safe_height // 5)))
        painter.setFont(font)
        painter.setPen(QColor(48, 45, 40))
        painter.drawText(
            pixmap.rect().adjusted(10, max(12, safe_height // 5), -10, -10),
            Qt.AlignCenter | Qt.TextWordWrap,
            text,
        )
    finally:
        painter.end()

    return pixmap


def _is_quick_generated_helper_path(file_name) -> bool:
    normalized = str(file_name or "").replace("\\", "/").strip().lstrip("/")
    if not normalized:
        return False
    first_segment = normalized.split("/", 1)[0].strip().lower()
    return first_segment in _QUICK_GENERATED_ASSET_FOLDER_SET


def _organized_source_dir_candidate(file_name, target_folder: str, source_dir: str, *, skip_generated: bool = False) -> str:
    normalized = str(file_name or "").replace("\\", "/").strip().lstrip("/")
    if not normalized or os.path.isabs(str(file_name or "").strip()) or not target_folder or not source_dir:
        return ""
    if normalized.startswith("build_in/"):
        return ""
    if skip_generated and _is_quick_generated_helper_path(normalized):
        return ""
    if normalized.split("/", 1)[0].strip().lower() == str(target_folder or "").strip().lower():
        return ""

    resolved_path = normalize_path(os.path.join(source_dir, normalized))
    if not resolved_path or not os.path.isfile(resolved_path) or not _is_subpath(resolved_path, source_dir):
        return ""
    return resolved_path


def _move_source_dir_asset_to_standard_folder(
    file_name,
    target_folder: str,
    source_dir: str,
    relocated_paths: dict[str, str],
    *,
    skip_generated: bool = False,
) -> tuple[str, bool]:
    normalized = str(file_name or "").replace("\\", "/").strip().lstrip("/")
    if not normalized:
        return "", False

    resolved_path = normalize_path(os.path.join(source_dir, normalized)) if source_dir and not os.path.isabs(str(file_name or "").strip()) else ""
    if resolved_path and resolved_path in relocated_paths:
        return relocated_paths[resolved_path], False

    candidate_path = _organized_source_dir_candidate(
        file_name,
        target_folder,
        source_dir,
        skip_generated=skip_generated,
    )
    if not candidate_path:
        return normalized, False

    target_path = normalize_path(os.path.join(source_dir, target_folder, os.path.basename(candidate_path)))
    if os.path.exists(target_path):
        target_path = _next_available_copy_path(target_path)

    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    shutil.move(candidate_path, target_path)
    relative_target = os.path.relpath(target_path, source_dir).replace("\\", "/")
    relocated_paths[candidate_path] = relative_target
    return relative_target, True


def _copy_file_into_source_dir(source_path: str, source_dir: str) -> tuple[str, bool]:
    normalized_source = normalize_path(source_path)
    normalized_dir = normalize_path(source_dir)
    if not normalized_source or not normalized_dir:
        return "", False

    basename = os.path.basename(normalized_source)
    target_path = normalize_path(os.path.join(normalized_dir, basename))
    if normalize_path(target_path) == normalized_source:
        return os.path.relpath(target_path, normalized_dir).replace("\\", "/"), False

    if os.path.isfile(target_path):
        try:
            if filecmp.cmp(normalized_source, target_path, shallow=False):
                return os.path.relpath(target_path, normalized_dir).replace("\\", "/"), False
        except OSError:
            pass
        target_path = _next_available_copy_path(target_path)

    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    shutil.copy2(normalized_source, target_path)
    return os.path.relpath(target_path, normalized_dir).replace("\\", "/"), True


def _next_available_copy_path(path: str) -> str:
    directory = os.path.dirname(path)
    filename = os.path.basename(path)
    stem, extension = os.path.splitext(filename)
    counter = 2
    candidate = path
    while os.path.exists(candidate):
        candidate = normalize_path(os.path.join(directory, f"{stem}_{counter}{extension}"))
        counter += 1
    return candidate


def _resource_dedupe_key(section: str, entry) -> tuple[str, str] | None:
    item = entry if isinstance(entry, dict) else {}
    file_name = str(item.get("file", "") or "").replace("\\", "/").strip().lower()
    if not file_name:
        return None
    return section, file_name


def _merge_missing_resource_fields(target, incoming) -> int:
    if not isinstance(target, dict) or not isinstance(incoming, dict):
        return 0

    merged = 0
    for field_name, value in incoming.items():
        if field_name == "file":
            continue
        if _resource_field_is_missing(field_name, value):
            continue
        if not _resource_field_is_missing(field_name, target.get(field_name)):
            continue
        target[field_name] = copy.deepcopy(value)
        merged += 1
    return merged


def _resource_field_is_missing(field_name: str, value) -> bool:
    if value is None:
        return True
    if field_name in {"fps", "width", "height"} and value == 0:
        return True
    if isinstance(value, str):
        return not value.strip()
    return False


def _detect_video_metadata(video_path: str) -> dict:
    ffprobe = _ffprobe_command()
    if not ffprobe:
        return {}

    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height,avg_frame_rate,r_frame_rate",
                "-of",
                "json",
                video_path,
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception:
        return {}

    if result.returncode != 0:
        return {}

    try:
        payload = json.loads(result.stdout or "{}")
    except Exception:
        return {}

    streams = payload.get("streams") if isinstance(payload, dict) else None
    if not isinstance(streams, list) or not streams:
        return {}

    stream = streams[0] if isinstance(streams[0], dict) else {}
    width = _safe_positive_int(stream.get("width"))
    height = _safe_positive_int(stream.get("height"))
    fps = _parse_video_fps(stream.get("avg_frame_rate")) or _parse_video_fps(stream.get("r_frame_rate"))

    metadata = {}
    if fps:
        metadata["fps"] = fps
    if width:
        metadata["width"] = width
    if height:
        metadata["height"] = height
    return metadata


def _ffprobe_command() -> str:
    command = shutil.which("ffprobe")
    if command:
        return normalize_path(command)
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return ""
    suffix = os.path.splitext(ffmpeg)[1]
    sibling = os.path.join(os.path.dirname(ffmpeg), f"ffprobe{suffix}")
    return normalize_path(sibling) if os.path.isfile(sibling) else ""


def _safe_positive_int(value) -> int:
    try:
        parsed = int(str(value).strip())
    except Exception:
        return 0
    return parsed if parsed > 0 else 0


def _parse_video_fps(value) -> int:
    raw = str(value or "").strip()
    if not raw or raw in {"0/0", "N/A"}:
        return 0
    try:
        if "/" in raw:
            numerator, denominator = raw.split("/", 1)
            denominator_value = float(denominator)
            if denominator_value == 0:
                return 0
            fps = float(numerator) / denominator_value
        else:
            fps = float(raw)
    except Exception:
        return 0
    if fps <= 0:
        return 0
    return max(int(round(fps)), 1)


def _section_for_asset_extension(extension: str) -> str:
    ext = str(extension or "").lower()
    if ext in _IMAGE_FILE_EXTENSIONS:
        return "img"
    if ext in _FONT_FILE_EXTENSIONS:
        return "font"
    if ext in _VIDEO_FILE_EXTENSIONS:
        return "mp4"
    return ""
