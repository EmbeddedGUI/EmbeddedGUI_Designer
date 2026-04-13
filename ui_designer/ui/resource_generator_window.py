"""Standalone Resource Generator window."""

from __future__ import annotations

import copy
import json
import os
import shutil

from PyQt5.QtCore import Qt, QSignalBlocker
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
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
        layout.addWidget(self._build_center_splitter(), 1)
        layout.addWidget(self._build_bottom_tabs(), 1)

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

        layout.addStretch(1)
        return layout

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
            return
        index = self._session.add_entry(self._active_section, default_entry_for_section(self._active_section))
        self._active_entry_index = index
        self._mark_dirty()
        self._refresh_entry_table()

    def _remove_entry(self):
        if not self._commit_raw_json_if_needed():
            return
        if self._active_entry_index < 0:
            return
        self._session.remove_entry(self._active_section, self._active_entry_index)
        self._active_entry_index = max(-1, self._active_entry_index - 1)
        self._mark_dirty()
        self._refresh_entry_table()

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
        if self._current_entry() is not None:
            self._entry_summary.setPlainText(self._entry_summary_text(self._current_entry()))

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
