"""Standalone Resource Generator window."""

from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess

from PyQt5.QtCore import Qt, QSignalBlocker, QUrl
from PyQt5.QtGui import QDesktopServices, QImage, QPixmap
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
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
from ..model.workspace import normalize_path
from ..utils.resource_config_overlay import APP_RESOURCE_CONFIG_FILENAME, make_empty_resource_config
from .resource_panel import (
    _GenerateCharsetDialog,
    _suggest_charset_filename_for_resource,
    _suggest_charset_presets_for_resource,
)


_IMAGE_FILE_EXTENSIONS = {".png", ".bmp", ".jpg", ".jpeg", ".gif", ".webp"}
_FONT_FILE_EXTENSIONS = {".ttf", ".otf"}
_VIDEO_FILE_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}
_TEXT_FILE_EXTENSIONS = {".txt"}


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


class ResourceGeneratorWindow(QDialog):
    """Modeless standalone window for editing and generating resources."""

    def __init__(self, sdk_root: str = "", parent=None):
        super().__init__(parent)
        self.setWindowFlags(self.windowFlags() | Qt.Window)
        self.setObjectName("resource_generator_window")
        self.resize(1360, 860)

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

        self._build_ui()
        self._apply_paths_and_data(GenerationPaths(), make_empty_resource_config(), dirty=False)

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
        self._new_button.clicked.connect(self._new_config)
        layout.addWidget(self._new_button)

        self._open_button = QPushButton("Open...")
        self._open_button.clicked.connect(self._open_config_dialog)
        layout.addWidget(self._open_button)

        self._save_button = QPushButton("Save")
        self._save_button.clicked.connect(self._save_config)
        layout.addWidget(self._save_button)

        self._save_as_button = QPushButton("Save As...")
        self._save_as_button.clicked.connect(self._save_config_as)
        layout.addWidget(self._save_as_button)

        self._generate_button = QPushButton("Generate")
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
            "Use quick helpers to scan an asset folder, generate font text files, and build resources without editing every field manually."
        )
        intro.setWordWrap(True)
        intro_layout.addWidget(intro)

        helper_row = QHBoxLayout()
        helper_row.setContentsMargins(0, 0, 0, 0)
        helper_row.setSpacing(8)

        self._import_assets_button = QPushButton("Import Files...")
        self._import_assets_button.clicked.connect(self._import_asset_files_dialog)
        helper_row.addWidget(self._import_assets_button)

        self._scan_assets_button = QPushButton("Scan Asset Folder...")
        self._scan_assets_button.clicked.connect(self._scan_assets_directory_dialog)
        helper_row.addWidget(self._scan_assets_button)

        self._generate_font_text_button = QPushButton("Generate Font Text...")
        self._generate_font_text_button.clicked.connect(self._open_generate_charset_helper)
        helper_row.addWidget(self._generate_font_text_button)

        self._auto_fill_button = QPushButton("Auto Fill Missing Info")
        self._auto_fill_button.clicked.connect(self._auto_fill_missing_resource_info)
        helper_row.addWidget(self._auto_fill_button)

        self._sort_assets_button = QPushButton("Sort Assets")
        self._sort_assets_button.clicked.connect(self._sort_assets_for_quick_mode)
        helper_row.addWidget(self._sort_assets_button)

        self._open_font_text_button = QPushButton("Open Font Text...")
        self._open_font_text_button.clicked.connect(self._open_selected_font_text_resource)
        helper_row.addWidget(self._open_font_text_button)

        self._preview_asset_button = QPushButton("Preview Selected Asset")
        self._preview_asset_button.clicked.connect(self._preview_selected_simple_asset)
        helper_row.addWidget(self._preview_asset_button)

        self._detect_video_info_button = QPushButton("Detect Video Info")
        self._detect_video_info_button.clicked.connect(self._detect_selected_video_metadata)
        helper_row.addWidget(self._detect_video_info_button)

        self._edit_asset_button = QPushButton("Edit / Open Asset...")
        self._edit_asset_button.clicked.connect(self._open_selected_asset_in_external_editor)
        helper_row.addWidget(self._edit_asset_button)

        self._open_asset_folder_button = QPushButton("Open Asset Folder...")
        self._open_asset_folder_button.clicked.connect(self._open_selected_asset_folder)
        helper_row.addWidget(self._open_asset_folder_button)

        self._resize_image_button = QPushButton("Resize Image...")
        self._resize_image_button.clicked.connect(self._open_resize_image_helper)
        helper_row.addWidget(self._resize_image_button)

        self._rotate_image_button = QPushButton("Rotate Image...")
        self._rotate_image_button.clicked.connect(self._open_rotate_image_helper)
        helper_row.addWidget(self._rotate_image_button)

        self._flip_image_button = QPushButton("Flip Image...")
        self._flip_image_button.clicked.connect(self._open_flip_image_helper)
        helper_row.addWidget(self._flip_image_button)

        self._crop_image_button = QPushButton("Crop Image...")
        self._crop_image_button.clicked.connect(self._open_crop_image_helper)
        helper_row.addWidget(self._crop_image_button)

        self._duplicate_simple_asset_button = QPushButton("Duplicate Selected")
        self._duplicate_simple_asset_button.clicked.connect(self._duplicate_selected_simple_asset)
        helper_row.addWidget(self._duplicate_simple_asset_button)

        self._remove_simple_asset_button = QPushButton("Remove Selected")
        self._remove_simple_asset_button.clicked.connect(self._remove_selected_simple_asset)
        helper_row.addWidget(self._remove_simple_asset_button)

        self._open_professional_button = QPushButton("Open Professional Mode")
        self._open_professional_button.clicked.connect(lambda: self._set_ui_mode("professional"))
        helper_row.addWidget(self._open_professional_button)

        helper_row.addStretch(1)
        intro_layout.addLayout(helper_row)

        counts_row = QHBoxLayout()
        counts_row.setContentsMargins(0, 0, 0, 0)
        counts_row.setSpacing(16)
        self._simple_image_count = QLabel("Images: 0")
        counts_row.addWidget(self._simple_image_count)
        self._simple_font_count = QLabel("Fonts: 0")
        counts_row.addWidget(self._simple_font_count)
        self._simple_mp4_count = QLabel("MP4: 0")
        counts_row.addWidget(self._simple_mp4_count)
        counts_row.addStretch(1)
        intro_layout.addLayout(counts_row)
        layout.addWidget(intro_group)

        self._simple_asset_table = QTableWidget(0, 4)
        self._simple_asset_table.setHorizontalHeaderLabels(["Type", "Name", "File", "Details"])
        self._simple_asset_table.verticalHeader().setVisible(False)
        self._simple_asset_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._simple_asset_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._simple_asset_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._simple_asset_table.itemSelectionChanged.connect(self._on_simple_asset_selection_changed)
        self._simple_asset_table.itemDoubleClicked.connect(self._open_simple_selection_in_professional_mode)
        simple_header = self._simple_asset_table.horizontalHeader()
        simple_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        simple_header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        simple_header.setSectionResizeMode(2, QHeaderView.Stretch)
        simple_header.setSectionResizeMode(3, QHeaderView.Stretch)
        layout.addWidget(self._simple_asset_table, 1)

        preview_splitter = QSplitter(Qt.Horizontal)

        asset_preview_group = QGroupBox("Asset Preview")
        asset_preview_layout = QVBoxLayout(asset_preview_group)
        asset_preview_layout.setContentsMargins(8, 8, 8, 8)
        asset_preview_layout.setSpacing(8)

        self._simple_asset_preview_title = QLabel("No asset selected.")
        asset_preview_layout.addWidget(self._simple_asset_preview_title)

        self._simple_asset_preview_label = QLabel("Select an image, font, or video entry to inspect it here.")
        self._simple_asset_preview_label.setAlignment(Qt.AlignCenter)
        self._simple_asset_preview_label.setMinimumHeight(180)
        self._simple_asset_preview_label.setWordWrap(True)
        asset_preview_layout.addWidget(self._simple_asset_preview_label, 1)

        self._simple_asset_meta = QPlainTextEdit()
        self._simple_asset_meta.setReadOnly(True)
        self._simple_asset_meta.setMinimumHeight(140)
        asset_preview_layout.addWidget(self._simple_asset_meta, 1)
        preview_splitter.addWidget(asset_preview_group)

        preview_group = QGroupBox("Merged Preview")
        preview_layout = QVBoxLayout(preview_group)
        preview_layout.setContentsMargins(8, 8, 8, 8)
        self._simple_preview = QPlainTextEdit()
        self._simple_preview.setReadOnly(True)
        preview_layout.addWidget(self._simple_preview)
        preview_splitter.addWidget(preview_group)
        preview_splitter.setStretchFactor(0, 1)
        preview_splitter.setStretchFactor(1, 1)
        preview_splitter.setSizes([460, 460])
        layout.addWidget(preview_splitter, 1)
        return page

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
        layout.addWidget(edit, 1)
        self._active_field_widgets[field_spec.name] = edit

        if field_spec.name in {"file", "text"}:
            button = QPushButton("Browse...")
            button.clicked.connect(lambda _checked=False, spec=field_spec: self._browse_entry_field(spec))
            layout.addWidget(button)

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
            text_value = str(entry.get("text", "") or "").strip()
            if text_value:
                lines.extend(["", "Text Files:"])
                for item in text_value.split(","):
                    candidate = item.strip()
                    if not candidate:
                        continue
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

    def _update_current_entry_field(self, field_name: str, value):
        self._session.update_entry_value(self._active_section, self._active_entry_index, field_name, value)
        self._mark_dirty()
        self._refresh_current_table_row()
        self._update_merged_preview()
        self._update_raw_editor()

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

        rows: list[tuple[str, int, dict]] = []
        for section in KNOWN_RESOURCE_SECTIONS:
            for index, entry in enumerate(self._session.section_entries(section)):
                if isinstance(entry, dict):
                    rows.append((section, index, entry))

        self._simple_row_map = [(section, index) for section, index, _entry in rows]
        selected_row = -1
        for row, (section, index) in enumerate(self._simple_row_map):
            if section == self._active_section and index == self._active_entry_index:
                selected_row = row
                break
        with QSignalBlocker(self._simple_asset_table):
            self._simple_asset_table.setRowCount(len(rows))
            for row, (section, index, entry) in enumerate(rows):
                detail = ""
                if section == "font":
                    detail = str(entry.get("text", "") or "")
                elif section == "mp4":
                    fps = str(entry.get("fps", "") or "")
                    width = str(entry.get("width", "") or "")
                    height = str(entry.get("height", "") or "")
                    if fps or width or height:
                        detail = f"{fps}fps {width}x{height}".strip()
                self._simple_asset_table.setItem(row, 0, QTableWidgetItem(RESOURCE_SECTION_SPECS[section].label))
                self._simple_asset_table.setItem(row, 1, QTableWidgetItem(section_entry_label(section, entry, index)))
                self._simple_asset_table.setItem(row, 2, QTableWidgetItem(str(entry.get("file", "") or "")))
                self._simple_asset_table.setItem(row, 3, QTableWidgetItem(detail))
            if 0 <= selected_row < len(rows):
                self._simple_asset_table.selectRow(selected_row)
        self._update_simple_asset_preview()

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
        self._update_simple_asset_preview()

    def _preview_selected_simple_asset(self):
        section, index, entry = self._selected_simple_asset_context()
        if entry is None:
            QMessageBox.warning(self, "Preview Asset", "Select an asset in Simple mode first.")
            return
        self._active_section = section or self._active_section
        self._active_entry_index = index
        self._update_simple_asset_preview()

    def _update_simple_asset_preview(self):
        section, index, entry = self._selected_simple_asset_context()
        self._simple_asset_preview_label.setPixmap(QPixmap())
        if entry is None or not section:
            self._simple_asset_preview_title.setText("No asset selected.")
            self._simple_asset_preview_label.setText("Select an image, font, or video entry to inspect it here.")
            self._simple_asset_meta.setPlainText("")
            return

        file_name = str(entry.get("file", "") or "").strip()
        resolved_path = self._resolve_entry_path(section, "file", file_name)
        exists = bool(resolved_path and os.path.exists(resolved_path))
        label = section_entry_label(section, entry, index)
        self._simple_asset_preview_title.setText(f"{RESOURCE_SECTION_SPECS[section].label}: {label}")

        meta_lines = [
            f"Section: {section}",
            f"Name: {label}",
            f"File: {file_name or '(empty)'}",
            f"Resolved: {resolved_path or '(unresolved)'}",
            f"Exists: {'yes' if exists else 'no'}",
        ]
        if section == "font":
            meta_lines.append(f"Text: {str(entry.get('text', '') or '(none)')}")
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

        if section == "img" and exists:
            pixmap = QPixmap(resolved_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(360, 220, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self._simple_asset_preview_label.setPixmap(scaled)
                self._simple_asset_preview_label.setText("")
                meta_lines.append(f"Image Size: {pixmap.width()} x {pixmap.height()}")
            else:
                self._simple_asset_preview_label.setText("Image file exists but Qt could not decode it.")
        elif section == "font" and exists:
            preview_text, preview_source = self._font_preview_sample(entry)
            meta_lines.append(f"Preview Text: {preview_text}")
            meta_lines.append(f"Preview Source: {preview_source}")
            pixmap = self._build_font_preview_pixmap(resolved_path, preview_text)
            if pixmap is not None and not pixmap.isNull():
                scaled = pixmap.scaled(360, 220, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self._simple_asset_preview_label.setPixmap(scaled)
                self._simple_asset_preview_label.setText("")
            else:
                self._simple_asset_preview_label.setText("Font file exists but quick preview could not render it.")
        elif exists:
            kind = "font" if section == "font" else "video"
            self._simple_asset_preview_label.setText(
                f"External preview is not embedded for this {kind}.\nUse 'Edit / Open Asset...' to inspect it in the system app."
            )
        else:
            self._simple_asset_preview_label.setText("File is missing. Fix the path or re-import the asset.")

        self._simple_asset_meta.setPlainText("\n".join(meta_lines).strip())

    def _font_preview_sample(self, entry: dict) -> tuple[str, str]:
        text_value = str(entry.get("text", "") or "").strip()
        for item in [candidate.strip() for candidate in text_value.split(",") if candidate.strip()]:
            resolved = self._resolve_entry_path("font", "text", item)
            if not resolved or not os.path.isfile(resolved):
                continue
            try:
                with open(resolved, "r", encoding="utf-8") as handle:
                    raw_text = handle.read()
            except OSError:
                continue
            lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
            if lines and all(len(line) == 1 for line in lines[: min(len(lines), 24)]):
                sample = "".join(lines[:24])
            else:
                sample = " ".join(raw_text.split())
            sample = sample.strip()
            if len(sample) > 48:
                sample = sample[:45].rstrip() + "..."
            if sample:
                return sample, item
        return "AaBb 123", "built-in sample"

    def _build_font_preview_pixmap(self, font_path: str, sample_text: str) -> QPixmap | None:
        try:
            from PIL import Image, ImageDraw, ImageFont
        except Exception:
            return None

        try:
            font = ImageFont.truetype(font_path, size=34)
        except Exception:
            return None

        width = 480
        height = 220
        padding = 18
        image = Image.new("RGBA", (width, height), (247, 246, 241, 255))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((0, 0, width - 1, height - 1), radius=14, outline=(205, 201, 191, 255), width=2)

        lines = self._wrap_font_preview_text(draw, sample_text, font, width - (padding * 2), max_lines=3)
        y = padding
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            draw.text((padding, y), line, font=font, fill=(35, 35, 35, 255))
            y += max(bbox[3] - bbox[1], 28) + 10

        return _pil_image_to_qpixmap(image)

    def _wrap_font_preview_text(self, draw, text: str, font, max_width: int, *, max_lines: int) -> list[str]:
        compact = " ".join(str(text or "").split()).strip() or "AaBb 123"
        lines = []
        position = 0
        while position < len(compact) and len(lines) < max_lines:
            end = position + 1
            while end <= len(compact):
                candidate = compact[position:end]
                bbox = draw.textbbox((0, 0), candidate, font=font)
                if bbox[2] - bbox[0] > max_width and end > position + 1:
                    end -= 1
                    break
                if bbox[2] - bbox[0] > max_width:
                    break
                end += 1
            if end <= position:
                end = position + 1

            if len(lines) == max_lines - 1 and end < len(compact):
                line = compact[position:]
                while line and draw.textbbox((0, 0), line + "...", font=font)[2] > max_width:
                    line = line[:-1]
                lines.append((line.rstrip() + "...") if line else "...")
                return lines

            line = compact[position:end].rstrip()
            if not line:
                break
            lines.append(line)
            position = end
            while position < len(compact) and compact[position] == " ":
                position += 1

        return lines or [compact]

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
        if not resolved_path or not os.path.exists(resolved_path):
            QMessageBox.warning(self, "Open Asset Folder", f"Asset file does not exist:\n{resolved_path or file_name}")
            return
        target_dir = os.path.dirname(resolved_path)
        self._active_section = section or self._active_section
        self._active_entry_index = index
        self._update_simple_asset_preview()
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(target_dir)):
            QMessageBox.warning(self, "Open Asset Folder", f"Failed to open asset folder:\n{target_dir}")
            return
        self._set_status(f"Opened asset folder '{target_dir}'.")

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

        metadata = _detect_video_metadata(resolved_path)
        if not metadata:
            QMessageBox.warning(
                self,
                "Detect Video Info",
                "Could not read video width, height, and fps. Make sure ffprobe is available in PATH.",
            )
            return

        changed = False
        for field_name in ("fps", "width", "height"):
            incoming = metadata.get(field_name)
            if incoming in (None, "", 0):
                continue
            existing = entry.get(field_name, "")
            if str(existing or "").strip() == str(incoming).strip():
                continue
            self._session.update_entry_value("mp4", index, field_name, incoming)
            changed = True

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

    def _auto_fill_missing_resource_info(self):
        if not self._commit_raw_json_if_needed():
            return

        updates = {
            "name": 0,
            "font_text": 0,
            "video_meta": 0,
        }

        for section in KNOWN_RESOURCE_SECTIONS:
            entries = self._session.section_entries(section)
            for index, entry in enumerate(entries):
                if not isinstance(entry, dict):
                    continue
                if self._auto_fill_entry_name(section, index, entry):
                    updates["name"] += 1
                if section == "font" and self._auto_fill_font_text(section, index, entry):
                    updates["font_text"] += 1
                if section == "mp4" and self._auto_fill_video_metadata(index, entry):
                    updates["video_meta"] += 1

        total_updates = sum(updates.values())
        if not total_updates:
            self._set_status("No missing asset info needed to be filled.")
            return

        self._mark_dirty()
        self._refresh_entry_table()
        self._update_merged_preview()
        self._update_raw_editor()

        summary = [f"Filled {total_updates} missing fields"]
        if updates["name"]:
            summary.append(f"names {updates['name']}")
        if updates["font_text"]:
            summary.append(f"font texts {updates['font_text']}")
        if updates["video_meta"]:
            summary.append(f"video metadata {updates['video_meta']}")
        self._set_status(", ".join(summary) + ".")

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

    def _auto_fill_entry_name(self, section: str, index: int, entry: dict) -> bool:
        if str(entry.get("name", "") or "").strip():
            return False
        file_name = str(entry.get("file", "") or "").strip()
        if not file_name:
            return False
        suggested = os.path.splitext(os.path.basename(file_name.replace("\\", "/")))[0].strip()
        if not suggested:
            return False
        self._session.update_entry_value(section, index, "name", suggested)
        return True

    def _auto_fill_font_text(self, section: str, index: int, entry: dict) -> bool:
        if str(entry.get("text", "") or "").strip():
            return False
        file_name = str(entry.get("file", "") or "").strip()
        resolved_font = self._resolve_entry_path(section, "file", file_name)
        if not resolved_font or not os.path.isfile(resolved_font):
            return False

        source_dir = self._session.paths.source_dir
        candidates = [normalize_path(os.path.splitext(resolved_font)[0] + ".txt")]
        if source_dir:
            basename = os.path.splitext(os.path.basename(file_name.replace("\\", "/")))[0]
            candidates.append(normalize_path(os.path.join(source_dir, f"{basename}.txt")))

        for candidate in candidates:
            if not candidate or not os.path.isfile(candidate):
                continue
            stored = candidate
            if source_dir and _is_subpath(candidate, source_dir):
                stored = os.path.relpath(candidate, source_dir).replace("\\", "/")
            self._session.update_entry_value(section, index, "text", stored)
            return True
        return False

    def _auto_fill_video_metadata(self, index: int, entry: dict) -> bool:
        missing_fields = [field for field in ("fps", "width", "height") if entry.get(field, "") in ("", None, 0)]
        if not missing_fields:
            return False

        file_name = str(entry.get("file", "") or "").strip()
        resolved_path = self._resolve_entry_path("mp4", "file", file_name)
        if not resolved_path or not os.path.isfile(resolved_path):
            return False

        metadata = _detect_video_metadata(resolved_path)
        changed = False
        for field_name in missing_fields:
            incoming = metadata.get(field_name)
            if incoming in (None, "", 0):
                continue
            self._session.update_entry_value("mp4", index, field_name, incoming)
            changed = True
        return changed

    def _open_selected_font_text_resource(self):
        section, index, entry = self._selected_simple_asset_context()
        if entry is None or section != "font":
            QMessageBox.warning(self, "Open Font Text", "Select a font asset in Simple mode first.")
            return

        target_filename, resolved_path = self._preferred_font_text_target(entry)
        if not target_filename or not resolved_path:
            QMessageBox.warning(
                self,
                "Open Font Text",
                "Set Source Dir first, or generate a font text file before opening it.",
            )
            return

        created = False
        if not os.path.isfile(resolved_path):
            answer = QMessageBox.question(
                self,
                "Create Font Text",
                f"Create a new font text resource?\n\n{target_filename}",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if answer != QMessageBox.Yes:
                return
            os.makedirs(os.path.dirname(resolved_path), exist_ok=True)
            with open(resolved_path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("")
            self._active_section = "font"
            self._active_entry_index = index
            self._assign_generated_text_to_font(target_filename)
            created = True

        self._active_section = "font"
        self._active_entry_index = index
        self._update_simple_asset_preview()
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(resolved_path)):
            QMessageBox.warning(self, "Open Font Text", f"Failed to open text file with the system editor:\n{resolved_path}")
            return
        action = "Created and opened" if created else "Opened"
        self._set_status(f"{action} font text '{target_filename}'.")

    def _preferred_font_text_target(self, entry: dict) -> tuple[str, str]:
        text_value = str(entry.get("text", "") or "").strip()
        candidates = [item.strip() for item in text_value.split(",") if item.strip()]
        for item in candidates:
            resolved = self._resolve_entry_path("font", "text", item)
            if resolved and os.path.isfile(resolved):
                return item, resolved

        if candidates:
            first = candidates[0]
            return first, self._resolve_entry_path("font", "text", first)

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
        path, _ = QFileDialog.getOpenFileName(self, f"Choose {field_spec.label}", start_dir, field_spec.file_filter)
        if not path:
            return
        stored_value = self._normalize_selected_resource_path(field_spec, normalize_path(path))
        if stored_value is None:
            return
        if field_spec.name == "text" and self._active_section == "font":
            existing = str(current_entry.get("text", "") or "").strip()
            if existing:
                items = [item.strip() for item in existing.split(",") if item.strip()]
                if stored_value not in items:
                    items.append(stored_value)
                stored_value = ",".join(items)
        current_value = str(current_entry.get(field_spec.name, "") or "")
        if current_value == stored_value:
            return
        self._session.update_entry_value(self._active_section, self._active_entry_index, field_spec.name, stored_value)
        self._mark_dirty()
        self._refresh_entry_table()
        self._update_merged_preview()
        self._update_raw_editor()

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
        super().closeEvent(event)


def _is_subpath(path: str, root: str) -> bool:
    path = normalize_path(path)
    root = normalize_path(root)
    if not path or not root:
        return False
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:
        return False


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
        file_name = str(item.get("file", "") or "").replace("\\", "/").strip()
        base_name = os.path.splitext(os.path.basename(file_name))[0].strip()
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
