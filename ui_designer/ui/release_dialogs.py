"""Release build dialogs."""

from __future__ import annotations

import shlex

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
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

    def __init__(self, history_entries: list[dict[str, object]], open_path_callback=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Release History")
        self.resize(920, 520)
        self._open_path_callback = open_path_callback

        root_layout = QVBoxLayout(self)
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

        action_row = QHBoxLayout()
        right_layout.addLayout(action_row)

        self._open_folder_button = QPushButton("Open Folder")
        self._open_manifest_button = QPushButton("Open Manifest")
        self._open_log_button = QPushButton("Open Log")
        self._open_package_button = QPushButton("Open Package")
        self._open_folder_button.clicked.connect(lambda: self._open_selected_path("release_root", "Release Folder"))
        self._open_manifest_button.clicked.connect(lambda: self._open_selected_path("manifest_path", "Release Manifest"))
        self._open_log_button.clicked.connect(lambda: self._open_selected_path("log_path", "Release Log"))
        self._open_package_button.clicked.connect(lambda: self._open_selected_path("zip_path", "Release Package"))
        for button in (
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

        for entry in history_entries or []:
            if not isinstance(entry, dict):
                continue
            item = QListWidgetItem(_history_list_label(entry))
            item.setData(Qt.UserRole, entry)
            self._history_list.addItem(item)

        if self._history_list.count():
            self._history_list.setCurrentRow(0)
        else:
            self._summary_label.setText("No release history available for this project.")
            self._details_edit.setPlainText("Run Build -> Release Build... to create the first tracked release.")
            self._set_open_buttons(None)

    def _current_entry(self) -> dict[str, object] | None:
        item = self._history_list.currentItem()
        if item is None:
            return None
        entry = item.data(Qt.UserRole)
        return entry if isinstance(entry, dict) else None

    def _set_open_buttons(self, entry: dict[str, object] | None) -> None:
        self._open_folder_button.setEnabled(bool(entry and _history_string(entry, "release_root")))
        self._open_manifest_button.setEnabled(bool(entry and _history_string(entry, "manifest_path")))
        self._open_log_button.setEnabled(bool(entry and _history_string(entry, "log_path")))
        self._open_package_button.setEnabled(bool(entry and _history_string(entry, "zip_path")))

    def _update_current_entry(self, row: int) -> None:
        if row < 0:
            self._summary_label.setText("No release entry selected.")
            self._details_edit.clear()
            self._set_open_buttons(None)
            return
        entry = self._current_entry()
        if entry is None:
            self._summary_label.setText("No release entry selected.")
            self._details_edit.clear()
            self._set_open_buttons(None)
            return
        self._summary_label.setText(_history_list_label(entry))
        self._details_edit.setPlainText(_history_detail_text(entry))
        self._set_open_buttons(entry)

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
