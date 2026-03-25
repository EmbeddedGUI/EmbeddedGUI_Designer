"""Release build dialogs."""

from __future__ import annotations

import json
import os
import shlex

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..model.release import ReleaseConfig, ReleaseProfile


_PREVIEW_CHAR_LIMIT = 65536


def _history_string(entry: dict[str, object], key: str) -> str:
    value = entry.get(key, "")
    return str(value).strip() if value is not None else ""


def _history_status(entry: dict[str, object]) -> str:
    status = _history_string(entry, "status")
    if status:
        return status
    if "success" in entry:
        return "success" if bool(entry.get("success")) else "failed"
    return "unknown"


def _history_sdk_label(entry: dict[str, object]) -> str:
    sdk = entry.get("sdk")
    if not isinstance(sdk, dict):
        return "unknown"
    revision = str(sdk.get("revision") or "").strip()
    commit_short = str(sdk.get("commit_short") or "").strip()
    commit = str(sdk.get("commit") or "").strip()
    label = revision or commit_short or commit[:12]
    if not label:
        label = "unknown"
    if sdk.get("dirty") and label != "unknown":
        label += " (dirty)"
    return label


def _history_list_label(entry: dict[str, object]) -> str:
    build_id = _history_string(entry, "build_id") or _history_string(entry, "created_at_utc") or "unknown-build"
    profile_id = _history_string(entry, "profile_id") or "unknown-profile"
    return f"{build_id} [{profile_id}] {_history_status(entry)} sdk {_history_sdk_label(entry)}"


def _history_detail_text(entry: dict[str, object]) -> str:
    lines = [
        f"Build ID: {_history_string(entry, 'build_id') or 'unknown'}",
        f"Created (UTC): {_history_string(entry, 'created_at_utc') or 'unknown'}",
        f"Status: {_history_status(entry)}",
        f"App: {_history_string(entry, 'app_name') or 'unknown'}",
        f"Profile: {_history_string(entry, 'profile_id') or 'unknown'}",
        f"SDK: {_history_sdk_label(entry)}",
    ]

    designer_revision = _history_string(entry, "designer_revision")
    if designer_revision:
        lines.append(f"Designer: {designer_revision}")

    warning_count = entry.get("warning_count")
    error_count = entry.get("error_count")
    if warning_count is not None or error_count is not None:
        lines.append(f"Diagnostics: warnings={warning_count or 0}, errors={error_count or 0}")

    sdk = entry.get("sdk")
    if isinstance(sdk, dict):
        commit = str(sdk.get("commit") or "").strip()
        remote = str(sdk.get("remote") or "").strip()
        if commit:
            lines.append(f"SDK Commit: {commit}")
        if remote:
            lines.append(f"SDK Remote: {remote}")

    for label, key in (
        ("Release Root", "release_root"),
        ("Dist", "dist_dir"),
        ("Manifest", "manifest_path"),
        ("Log", "log_path"),
        ("Package", "zip_path"),
    ):
        value = _history_string(entry, key)
        if value:
            lines.append(f"{label}: {value}")

    message = _history_string(entry, "message")
    if message:
        lines.append("")
        lines.append("Message:")
        lines.append(message)
    return "\n".join(lines)


def _preview_file_text(path: str, *, prefer_json: bool = False, char_limit: int = _PREVIEW_CHAR_LIMIT) -> str:
    resolved_path = os.path.abspath(os.path.normpath(path))
    if not os.path.isfile(resolved_path):
        return f"File not found:\n{resolved_path}"

    try:
        with open(resolved_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(char_limit + 1)
    except OSError as exc:
        return f"Failed to read file:\n{resolved_path}\n\n{exc}"

    truncated = len(content) > char_limit
    if truncated:
        content = content[:char_limit]

    if prefer_json:
        try:
            parsed = json.loads(content)
            content = json.dumps(parsed, indent=2, ensure_ascii=False)
        except (ValueError, TypeError):
            pass

    if truncated:
        content = content.rstrip() + f"\n\n[truncated to first {char_limit} characters]"
    return content


class ReleaseBuildDialog(QDialog):
    """Confirm a release build and choose a release profile."""

    def __init__(self, release_config: ReleaseConfig, sdk_label: str, output_root: str, warning_count: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Release Build")
        self.resize(560, 260)
        self._release_config = release_config

        layout = QVBoxLayout(self)

        form = QFormLayout()
        self._profile_combo = QComboBox()
        for profile in release_config.profiles:
            self._profile_combo.addItem(f"{profile.name} ({profile.id})", profile.id)
        selected_profile = release_config.get_profile().id
        index = self._profile_combo.findData(selected_profile)
        if index >= 0:
            self._profile_combo.setCurrentIndex(index)
        form.addRow("Profile", self._profile_combo)

        self._sdk_label = QLabel(sdk_label or "SDK: unknown")
        self._sdk_label.setWordWrap(True)
        form.addRow("SDK", self._sdk_label)

        self._output_label = QLabel(output_root or "")
        self._output_label.setWordWrap(True)
        form.addRow("Output", self._output_label)

        warnings_text = f"{warning_count} warning(s)" if warning_count else "No warnings"
        self._warnings_label = QLabel(warnings_text)
        form.addRow("Diagnostics", self._warnings_label)
        layout.addLayout(form)

        self._warnings_as_errors = QCheckBox("Treat warnings as errors")
        layout.addWidget(self._warnings_as_errors)

        self._package_release = QCheckBox("Create zip package")
        self._package_release.setChecked(True)
        layout.addWidget(self._package_release)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    @property
    def selected_profile_id(self) -> str:
        return str(self._profile_combo.currentData() or "")

    @property
    def warnings_as_errors(self) -> bool:
        return self._warnings_as_errors.isChecked()

    @property
    def package_release(self) -> bool:
        return self._package_release.isChecked()


class ReleaseProfilesDialog(QDialog):
    """Edit project release profiles."""

    def __init__(self, release_config: ReleaseConfig, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Release Profiles")
        self.resize(760, 420)
        self._release_config = ReleaseConfig.from_dict(release_config.to_dict())

        root_layout = QVBoxLayout(self)
        content_layout = QHBoxLayout()
        root_layout.addLayout(content_layout, 1)

        left_panel = QVBoxLayout()
        content_layout.addLayout(left_panel, 1)

        self._profile_list = QListWidget()
        self._profile_list.currentRowChanged.connect(self._load_profile_into_form)
        left_panel.addWidget(self._profile_list, 1)

        left_actions = QHBoxLayout()
        add_btn = QPushButton("Add")
        copy_btn = QPushButton("Copy")
        delete_btn = QPushButton("Delete")
        set_default_btn = QPushButton("Set Default")
        add_btn.clicked.connect(self._add_profile)
        copy_btn.clicked.connect(self._copy_profile)
        delete_btn.clicked.connect(self._delete_profile)
        set_default_btn.clicked.connect(self._set_default_profile)
        for button in (add_btn, copy_btn, delete_btn, set_default_btn):
            left_actions.addWidget(button)
        left_panel.addLayout(left_actions)

        form_container = QWidget()
        form_layout = QFormLayout(form_container)
        content_layout.addWidget(form_container, 2)

        self._id_edit = QLineEdit()
        self._name_edit = QLineEdit()
        self._port_edit = QLineEdit()
        self._make_target_edit = QLineEdit()
        self._package_format_combo = QComboBox()
        self._package_format_combo.addItem("Directory Only", "dir")
        self._package_format_combo.addItem("Directory + Zip", "dir+zip")
        self._extra_args_edit = QLineEdit()
        self._copy_resource_check = QCheckBox("Copy resource directory into dist")

        self._id_edit.textEdited.connect(self._sync_current_profile)
        self._name_edit.textEdited.connect(self._sync_current_profile)
        self._port_edit.textEdited.connect(self._sync_current_profile)
        self._make_target_edit.textEdited.connect(self._sync_current_profile)
        self._package_format_combo.currentIndexChanged.connect(self._sync_current_profile)
        self._extra_args_edit.textEdited.connect(self._sync_current_profile)
        self._copy_resource_check.toggled.connect(self._sync_current_profile)

        form_layout.addRow("Profile ID", self._id_edit)
        form_layout.addRow("Name", self._name_edit)
        form_layout.addRow("Port", self._port_edit)
        form_layout.addRow("Make Target", self._make_target_edit)
        form_layout.addRow("Package", self._package_format_combo)
        form_layout.addRow("Extra Make Args", self._extra_args_edit)
        form_layout.addRow("", self._copy_resource_check)

        self._default_label = QLabel()
        self._default_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        root_layout.addWidget(self._default_label)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self._accept_with_validation)
        button_box.rejected.connect(self.reject)
        root_layout.addWidget(button_box)

        self._rebuild_profile_list()
        if self._profile_list.count():
            self._profile_list.setCurrentRow(0)

    @property
    def release_config(self) -> ReleaseConfig:
        return self._release_config

    def _current_profile(self) -> ReleaseProfile | None:
        row = self._profile_list.currentRow()
        if row < 0 or row >= len(self._release_config.profiles):
            return None
        return self._release_config.profiles[row]

    def _rebuild_profile_list(self) -> None:
        self._profile_list.blockSignals(True)
        current_profile = self._current_profile()
        current_id = current_profile.id if current_profile else ""
        self._profile_list.clear()
        for profile in self._release_config.profiles:
            label = profile.name or profile.id
            if profile.id == self._release_config.default_profile:
                label += " [default]"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, profile.id)
            self._profile_list.addItem(item)
        self._profile_list.blockSignals(False)

        if current_id:
            for row in range(self._profile_list.count()):
                item = self._profile_list.item(row)
                if item.data(Qt.UserRole) == current_id:
                    self._profile_list.setCurrentRow(row)
                    break
        self._default_label.setText(f"Default Profile: {self._release_config.default_profile}")

    def _load_profile_into_form(self, row: int) -> None:
        if row < 0 or row >= len(self._release_config.profiles):
            return
        profile = self._release_config.profiles[row]
        self._id_edit.blockSignals(True)
        self._name_edit.blockSignals(True)
        self._port_edit.blockSignals(True)
        self._make_target_edit.blockSignals(True)
        self._package_format_combo.blockSignals(True)
        self._extra_args_edit.blockSignals(True)
        self._copy_resource_check.blockSignals(True)

        self._id_edit.setText(profile.id)
        self._name_edit.setText(profile.name)
        self._port_edit.setText(profile.port)
        self._make_target_edit.setText(profile.make_target)
        combo_index = self._package_format_combo.findData(profile.package_format)
        self._package_format_combo.setCurrentIndex(combo_index if combo_index >= 0 else 1)
        self._extra_args_edit.setText(" ".join(profile.extra_make_args))
        self._copy_resource_check.setChecked(profile.copy_resource_dir)

        self._id_edit.blockSignals(False)
        self._name_edit.blockSignals(False)
        self._port_edit.blockSignals(False)
        self._make_target_edit.blockSignals(False)
        self._package_format_combo.blockSignals(False)
        self._extra_args_edit.blockSignals(False)
        self._copy_resource_check.blockSignals(False)

    def _sync_current_profile(self) -> None:
        profile = self._current_profile()
        if profile is None:
            return
        profile.id = self._id_edit.text().strip()
        profile.name = self._name_edit.text().strip()
        profile.port = self._port_edit.text().strip() or "pc"
        profile.make_target = self._make_target_edit.text().strip() or "all"
        profile.package_format = str(self._package_format_combo.currentData() or "dir+zip")
        try:
            profile.extra_make_args = [item for item in shlex.split(self._extra_args_edit.text().strip()) if item]
        except ValueError:
            profile.extra_make_args = [token for token in self._extra_args_edit.text().split(" ") if token]
        profile.copy_resource_dir = self._copy_resource_check.isChecked()
        self._rebuild_profile_list()

    def _add_profile(self) -> None:
        base = "windows-pc"
        suffix = 1
        existing_ids = {profile.id for profile in self._release_config.profiles}
        candidate = base
        while candidate in existing_ids:
            suffix += 1
            candidate = f"{base}-{suffix}"
        self._release_config.profiles.append(
            ReleaseProfile(
                id=candidate,
                name=f"Windows PC {suffix}",
                port="pc",
                make_target="all",
                package_format="dir+zip",
                extra_make_args=[],
                copy_resource_dir=True,
            )
        )
        self._rebuild_profile_list()
        self._profile_list.setCurrentRow(self._profile_list.count() - 1)

    def _copy_profile(self) -> None:
        profile = self._current_profile()
        if profile is None:
            return
        suffix = 1
        existing_ids = {item.id for item in self._release_config.profiles}
        candidate = f"{profile.id}-copy"
        while candidate in existing_ids:
            suffix += 1
            candidate = f"{profile.id}-copy-{suffix}"
        cloned = ReleaseProfile.from_dict(profile.to_dict())
        cloned.id = candidate
        cloned.name = f"{profile.name} Copy"
        self._release_config.profiles.append(cloned)
        self._rebuild_profile_list()
        self._profile_list.setCurrentRow(self._profile_list.count() - 1)

    def _delete_profile(self) -> None:
        if len(self._release_config.profiles) == 1:
            QMessageBox.warning(self, "Delete Profile", "At least one release profile is required.")
            return
        row = self._profile_list.currentRow()
        if row < 0:
            return
        removed = self._release_config.profiles.pop(row)
        if self._release_config.default_profile == removed.id:
            self._release_config.default_profile = self._release_config.profiles[0].id
        self._rebuild_profile_list()
        self._profile_list.setCurrentRow(max(0, row - 1))

    def _set_default_profile(self) -> None:
        profile = self._current_profile()
        if profile is None:
            return
        self._release_config.default_profile = profile.id
        self._rebuild_profile_list()

    def _accept_with_validation(self) -> None:
        self._sync_current_profile()
        profile_ids = [profile.id for profile in self._release_config.profiles]
        if any(not profile_id for profile_id in profile_ids):
            QMessageBox.warning(self, "Invalid Profiles", "Profile ID cannot be empty.")
            return
        if len(set(profile_ids)) != len(profile_ids):
            QMessageBox.warning(self, "Invalid Profiles", "Profile ID must be unique.")
            return
        if self._release_config.default_profile not in set(profile_ids):
            self._release_config.default_profile = profile_ids[0]
        self.accept()


class ReleaseHistoryDialog(QDialog):
    """Browse recent release builds and open related artifacts."""

    def __init__(self, history_entries: list[dict[str, object]], open_path_callback=None, refresh_history_callback=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Release History")
        self.resize(1040, 680)
        self._open_path_callback = open_path_callback
        self._refresh_history_callback = refresh_history_callback
        self._all_history_entries: list[dict[str, object]] = []

        root_layout = QVBoxLayout(self)

        filter_row = QHBoxLayout()
        root_layout.addLayout(filter_row)

        filter_row.addWidget(QLabel("Status"))
        self._status_filter_combo = QComboBox()
        self._status_filter_combo.addItem("All", "")
        self._status_filter_combo.addItem("Success", "success")
        self._status_filter_combo.addItem("Failed", "failed")
        self._status_filter_combo.addItem("Unknown", "unknown")
        self._status_filter_combo.currentIndexChanged.connect(self._apply_history_filter)
        filter_row.addWidget(self._status_filter_combo)

        filter_row.addWidget(QLabel("Profile"))
        self._profile_filter_combo = QComboBox()
        self._profile_filter_combo.currentIndexChanged.connect(self._apply_history_filter)
        filter_row.addWidget(self._profile_filter_combo)

        filter_row.addWidget(QLabel("Search"))
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("build id, message, SDK revision...")
        self._search_edit.textChanged.connect(self._apply_history_filter)
        filter_row.addWidget(self._search_edit, 1)

        self._result_count_label = QLabel("0 / 0")
        filter_row.addWidget(self._result_count_label)

        self._clear_filters_button = QPushButton("Clear Filters")
        self._clear_filters_button.clicked.connect(self._clear_filters)
        filter_row.addWidget(self._clear_filters_button)

        self._refresh_button = QPushButton("Refresh")
        self._refresh_button.setEnabled(self._refresh_history_callback is not None)
        self._refresh_button.clicked.connect(self._reload_history_entries)
        filter_row.addWidget(self._refresh_button)

        content_layout = QHBoxLayout()
        root_layout.addLayout(content_layout, 1)

        self._history_list = QListWidget()
        self._history_list.currentRowChanged.connect(self._update_current_entry)
        content_layout.addWidget(self._history_list, 2)

        right_layout = QVBoxLayout()
        content_layout.addLayout(right_layout, 3)

        self._summary_label = QLabel("Select a release entry to inspect its metadata.")
        self._summary_label.setWordWrap(True)
        right_layout.addWidget(self._summary_label)

        self._details_edit = QTextEdit()
        self._details_edit.setReadOnly(True)
        right_layout.addWidget(self._details_edit, 1)

        self._preview_label = QLabel("Preview")
        right_layout.addWidget(self._preview_label)

        self._preview_edit = QTextEdit()
        self._preview_edit.setReadOnly(True)
        right_layout.addWidget(self._preview_edit, 2)

        action_row = QHBoxLayout()
        right_layout.addLayout(action_row)

        self._preview_manifest_button = QPushButton("Preview Manifest")
        self._preview_log_button = QPushButton("Preview Log")
        self._copy_details_button = QPushButton("Copy Details")
        self._copy_preview_button = QPushButton("Copy Preview")
        self._open_folder_button = QPushButton("Open Folder")
        self._open_manifest_button = QPushButton("Open Manifest")
        self._open_log_button = QPushButton("Open Log")
        self._open_package_button = QPushButton("Open Package")
        self._preview_manifest_button.clicked.connect(lambda: self._preview_selected_path("manifest_path", "Manifest", prefer_json=True))
        self._preview_log_button.clicked.connect(lambda: self._preview_selected_path("log_path", "Log"))
        self._copy_details_button.clicked.connect(lambda: self._copy_text(self._details_edit.toPlainText()))
        self._copy_preview_button.clicked.connect(lambda: self._copy_text(self._preview_edit.toPlainText()))
        self._open_folder_button.clicked.connect(lambda: self._open_selected_path("release_root", "Release Folder"))
        self._open_manifest_button.clicked.connect(lambda: self._open_selected_path("manifest_path", "Release Manifest"))
        self._open_log_button.clicked.connect(lambda: self._open_selected_path("log_path", "Release Log"))
        self._open_package_button.clicked.connect(lambda: self._open_selected_path("zip_path", "Release Package"))
        for button in (
            self._preview_manifest_button,
            self._preview_log_button,
            self._copy_details_button,
            self._copy_preview_button,
            self._open_folder_button,
            self._open_manifest_button,
            self._open_log_button,
            self._open_package_button,
        ):
            action_row.addWidget(button)
        action_row.addStretch(1)

        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(self.reject)
        button_box.accepted.connect(self.accept)
        root_layout.addWidget(button_box)

        self._load_history_entries(history_entries)

    def _current_entry(self) -> dict[str, object] | None:
        item = self._history_list.currentItem()
        if item is None:
            return None
        entry = item.data(Qt.UserRole)
        return entry if isinstance(entry, dict) else None

    def _load_history_entries(self, history_entries: list[dict[str, object]] | None) -> None:
        self._all_history_entries = [entry for entry in (history_entries or []) if isinstance(entry, dict)]
        self._rebuild_profile_filter_options()
        self._apply_history_filter()

    def _rebuild_profile_filter_options(self) -> None:
        current_profile = str(self._profile_filter_combo.currentData() or "")
        profile_ids = []
        seen = set()
        for entry in self._all_history_entries:
            profile_id = _history_string(entry, "profile_id")
            if not profile_id or profile_id in seen:
                continue
            seen.add(profile_id)
            profile_ids.append(profile_id)

        self._profile_filter_combo.blockSignals(True)
        self._profile_filter_combo.clear()
        self._profile_filter_combo.addItem("All", "")
        for profile_id in profile_ids:
            self._profile_filter_combo.addItem(profile_id, profile_id)
        index = self._profile_filter_combo.findData(current_profile)
        self._profile_filter_combo.setCurrentIndex(index if index >= 0 else 0)
        self._profile_filter_combo.blockSignals(False)

    def _matches_history_filter(self, entry: dict[str, object], status_filter: str, profile_filter: str, search_text: str) -> bool:
        if status_filter and _history_status(entry) != status_filter:
            return False
        if profile_filter and _history_string(entry, "profile_id") != profile_filter:
            return False
        if search_text:
            searchable = " ".join(
                filter(
                    None,
                    (
                        _history_string(entry, "build_id"),
                        _history_string(entry, "profile_id"),
                        _history_string(entry, "app_name"),
                        _history_string(entry, "message"),
                        _history_string(entry, "designer_revision"),
                        _history_sdk_label(entry),
                        _history_string(entry.get("sdk") if isinstance(entry.get("sdk"), dict) else {}, "commit"),
                    ),
                )
            ).lower()
            if search_text not in searchable:
                return False
        return True

    def _apply_history_filter(self) -> None:
        wanted_status = str(self._status_filter_combo.currentData() or "")
        wanted_profile = str(self._profile_filter_combo.currentData() or "")
        search_text = self._search_edit.text().strip().lower()
        current_entry = self._current_entry()
        current_build_id = _history_string(current_entry, "build_id") if current_entry else ""

        filtered_entries = [
            entry
            for entry in self._all_history_entries
            if self._matches_history_filter(entry, wanted_status, wanted_profile, search_text)
        ]
        self._result_count_label.setText(f"{len(filtered_entries)} / {len(self._all_history_entries)}")

        self._history_list.blockSignals(True)
        self._history_list.clear()
        selected_row = -1
        for row, entry in enumerate(filtered_entries):
            item = QListWidgetItem(_history_list_label(entry))
            item.setData(Qt.UserRole, entry)
            self._history_list.addItem(item)
            if current_build_id and _history_string(entry, "build_id") == current_build_id:
                selected_row = row
        self._history_list.blockSignals(False)

        if self._history_list.count():
            self._history_list.setCurrentRow(selected_row if selected_row >= 0 else 0)
            return

        if self._all_history_entries:
            self._summary_label.setText("No release entries match the current filters.")
            self._details_edit.setPlainText("Adjust Status, Profile, or Search to see matching release builds.")
            self._preview_label.setText("Preview")
            self._preview_edit.setPlainText("No manifest or build log is available because the filtered result set is empty.")
        else:
            self._summary_label.setText("No release history available for this project.")
            self._details_edit.setPlainText("Run Build -> Release Build... to create the first tracked release.")
            self._preview_label.setText("Preview")
            self._preview_edit.setPlainText("Select a release entry to preview its manifest or build log.")
        self._set_open_buttons(None)

    def _reload_history_entries(self) -> None:
        if self._refresh_history_callback is None:
            return
        try:
            history_entries = self._refresh_history_callback()
        except Exception as exc:
            QMessageBox.warning(self, "Refresh Release History Failed", str(exc))
            return
        self._load_history_entries(history_entries)

    def _clear_filters(self) -> None:
        self._status_filter_combo.setCurrentIndex(0)
        self._profile_filter_combo.setCurrentIndex(0)
        self._search_edit.clear()

    def _set_open_buttons(self, entry: dict[str, object] | None) -> None:
        self._preview_manifest_button.setEnabled(bool(entry and _history_string(entry, "manifest_path")))
        self._preview_log_button.setEnabled(bool(entry and _history_string(entry, "log_path")))
        self._copy_details_button.setEnabled(bool(entry))
        self._copy_preview_button.setEnabled(bool(entry))
        self._open_folder_button.setEnabled(bool(entry and _history_string(entry, "release_root")))
        self._open_manifest_button.setEnabled(bool(entry and _history_string(entry, "manifest_path")))
        self._open_log_button.setEnabled(bool(entry and _history_string(entry, "log_path")))
        self._open_package_button.setEnabled(bool(entry and _history_string(entry, "zip_path")))

    def _update_current_entry(self, row: int) -> None:
        if row < 0:
            self._summary_label.setText("No release entry selected.")
            self._details_edit.clear()
            self._preview_label.setText("Preview")
            self._preview_edit.clear()
            self._set_open_buttons(None)
            return
        entry = self._current_entry()
        if entry is None:
            self._summary_label.setText("No release entry selected.")
            self._details_edit.clear()
            self._preview_label.setText("Preview")
            self._preview_edit.clear()
            self._set_open_buttons(None)
            return
        self._summary_label.setText(_history_list_label(entry))
        self._details_edit.setPlainText(_history_detail_text(entry))
        self._set_open_buttons(entry)
        if _history_string(entry, "manifest_path"):
            self._preview_selected_path("manifest_path", "Manifest", prefer_json=True)
        elif _history_string(entry, "log_path"):
            self._preview_selected_path("log_path", "Log")
        else:
            self._preview_label.setText("Preview")
            self._preview_edit.setPlainText("No manifest or build log is recorded for this release entry.")

    def _open_selected_path(self, key: str, label: str) -> None:
        if self._open_path_callback is None:
            return
        entry = self._current_entry()
        path = _history_string(entry or {}, key)
        if not path:
            return
        try:
            self._open_path_callback(path)
        except Exception as exc:
            QMessageBox.warning(self, f"Open {label} Failed", str(exc))

    def _preview_selected_path(self, key: str, label: str, *, prefer_json: bool = False) -> None:
        entry = self._current_entry()
        path = _history_string(entry or {}, key)
        self._preview_label.setText(f"{label} Preview")
        if not path:
            self._preview_edit.setPlainText(f"No {label.lower()} path recorded for this release entry.")
            return
        self._preview_edit.setPlainText(_preview_file_text(path, prefer_json=prefer_json))

    def _copy_text(self, text: str) -> None:
        QApplication.clipboard().setText(text or "")
