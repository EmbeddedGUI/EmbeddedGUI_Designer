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
    QVBoxLayout,
    QWidget,
)

from ..model.release import ReleaseConfig, ReleaseProfile


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
