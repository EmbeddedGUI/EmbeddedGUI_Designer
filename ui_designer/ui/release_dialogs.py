"""Release build dialogs."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
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
    QFileDialog,
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

from ..model.config import get_config
from ..model.release import ReleaseConfig, ReleaseProfile


_PREVIEW_CHAR_LIMIT = 65536


def _history_string(entry: dict[str, object], key: str) -> str:
    value = entry.get(key, "")
    return str(value).strip() if value is not None else ""


def _history_int(entry: dict[str, object], key: str) -> int | None:
    value = entry.get(key)
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


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
    parts = [f"{build_id} [{profile_id}] {_history_status(entry)} sdk {_history_sdk_label(entry)}"]
    warning_count = _history_int(entry, "warning_count")
    error_count = _history_int(entry, "error_count")
    if (warning_count or 0) > 0:
        parts.append(f"warn {warning_count}")
    if (error_count or 0) > 0:
        parts.append(f"err {error_count}")
    return " ".join(parts)


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

    version_path = _history_version_path(entry)
    if version_path:
        lines.append(f"Version: {version_path}")

    message = _history_string(entry, "message")
    if message:
        lines.append("")
        lines.append("Message:")
        lines.append(message)
    return "\n".join(lines)


def _history_version_path(entry: dict[str, object]) -> str:
    dist_dir = _history_string(entry, "dist_dir")
    if dist_dir:
        candidate = os.path.join(dist_dir, "VERSION.txt")
        if os.path.isfile(candidate):
            return candidate

    release_root = _history_string(entry, "release_root")
    if release_root:
        candidate = os.path.join(release_root, "VERSION.txt")
        if os.path.isfile(candidate):
            return candidate
    return ""


def _history_summary_line(entry: dict[str, object]) -> str:
    build_id = _history_string(entry, "build_id") or "unknown-build"
    status = _history_status(entry)
    profile_id = _history_string(entry, "profile_id") or "unknown-profile"
    sdk_label = _history_sdk_label(entry)
    message = _history_string(entry, "message") or "-"
    return f"{build_id} | {status} | {profile_id} | sdk {sdk_label} | {message}"


def _history_status_counts(entries: list[dict[str, object]]) -> dict[str, int]:
    counts = {"success": 0, "failed": 0, "unknown": 0}
    for entry in entries:
        status = _history_status(entry)
        if status not in counts:
            status = "unknown"
        counts[status] += 1
    return counts


def _history_artifact_counts(entries: list[dict[str, object]]) -> dict[str, int]:
    counts = {"manifest": 0, "log": 0, "package": 0, "version": 0}
    for entry in entries:
        if _history_string(entry, "manifest_path"):
            counts["manifest"] += 1
        if _history_string(entry, "log_path"):
            counts["log"] += 1
        if _history_string(entry, "zip_path"):
            counts["package"] += 1
        if _history_version_path(entry):
            counts["version"] += 1
    return counts


def _history_diagnostics_counts(entries: list[dict[str, object]]) -> dict[str, int]:
    counts = {"clean": 0, "warnings": 0, "errors": 0, "unknown": 0}
    for entry in entries:
        if _history_matches_diagnostics(entry, "unknown"):
            counts["unknown"] += 1
        if _history_matches_diagnostics(entry, "clean"):
            counts["clean"] += 1
        if _history_matches_diagnostics(entry, "warnings"):
            counts["warnings"] += 1
        if _history_matches_diagnostics(entry, "errors"):
            counts["errors"] += 1
    return counts


def _history_timestamp_value(entry: dict[str, object]) -> float | None:
    timestamp = _history_timestamp(entry)
    return timestamp.timestamp() if timestamp is not None else None


def _history_matches_diagnostics(entry: dict[str, object], diagnostics_filter: str) -> bool:
    warning_count = _history_int(entry, "warning_count")
    error_count = _history_int(entry, "error_count")

    if not diagnostics_filter:
        return True
    if diagnostics_filter == "clean":
        return warning_count == 0 and error_count == 0
    if diagnostics_filter == "warnings":
        return (warning_count or 0) > 0
    if diagnostics_filter == "errors":
        return (error_count or 0) > 0
    if diagnostics_filter == "issues":
        return (warning_count or 0) > 0 or (error_count or 0) > 0
    if diagnostics_filter == "unknown":
        return warning_count is None and error_count is None
    return True


def _history_has_artifact(entry: dict[str, object], artifact_filter: str) -> bool:
    missing = artifact_filter.startswith("missing_")
    normalized_filter = artifact_filter[8:] if missing else artifact_filter
    if normalized_filter == "version":
        has_artifact = bool(_history_version_path(entry))
        return not has_artifact if missing else has_artifact
    artifact_key = {
        "manifest": "manifest_path",
        "log": "log_path",
        "package": "zip_path",
    }.get(normalized_filter)
    if not artifact_key:
        return True
    has_artifact = bool(_history_string(entry, artifact_key))
    return not has_artifact if missing else has_artifact


def _sorted_history_entries(entries: list[dict[str, object]], sort_mode: str) -> list[dict[str, object]]:
    if sort_mode == "oldest":
        return sorted(
            entries,
            key=lambda entry: (
                _history_timestamp_value(entry) is None,
                _history_timestamp_value(entry) or 0.0,
                _history_string(entry, "build_id"),
            ),
        )

    if sort_mode == "status":
        status_order = {"failed": 0, "unknown": 1, "success": 2}
        return sorted(
            entries,
            key=lambda entry: (
                status_order.get(_history_status(entry), 3),
                _history_string(entry, "profile_id").lower(),
                _history_timestamp_value(entry) is None,
                -(_history_timestamp_value(entry) or 0.0),
                _history_string(entry, "build_id"),
            ),
        )

    if sort_mode == "diagnostics":
        def diagnostics_rank(entry: dict[str, object]) -> int:
            if _history_matches_diagnostics(entry, "errors"):
                return 0
            if _history_matches_diagnostics(entry, "warnings"):
                return 1
            if _history_matches_diagnostics(entry, "unknown"):
                return 2
            return 3

        return sorted(
            entries,
            key=lambda entry: (
                diagnostics_rank(entry),
                _history_string(entry, "profile_id").lower(),
                _history_timestamp_value(entry) is None,
                -(_history_timestamp_value(entry) or 0.0),
                _history_string(entry, "build_id"),
            ),
        )

    if sort_mode == "profile":
        return sorted(
            entries,
            key=lambda entry: (
                _history_string(entry, "profile_id").lower(),
                _history_timestamp_value(entry) is None,
                -(_history_timestamp_value(entry) or 0.0),
                _history_string(entry, "build_id"),
            ),
        )

    return sorted(
        entries,
        key=lambda entry: (
            _history_timestamp_value(entry) is None,
            -(_history_timestamp_value(entry) or 0.0),
            _history_string(entry, "build_id"),
        ),
    )


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _history_timestamp(entry: dict[str, object]) -> datetime | None:
    created_at = _history_string(entry, "created_at_utc")
    if created_at:
        try:
            return datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    build_id = _history_string(entry, "build_id")
    if build_id:
        try:
            return datetime.strptime(build_id, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return None


def _build_filtered_history_summary(
    filtered_entries: list[dict[str, object]],
    all_entries: list[dict[str, object]],
    *,
    range_filter: str,
    status_filter: str,
    profile_filter: str,
    artifact_filter: str,
    diagnostics_filter: str,
    sort_mode: str,
    search_text: str,
) -> str:
    status_counts = _history_status_counts(filtered_entries)
    artifact_counts = _history_artifact_counts(filtered_entries)
    diagnostics_counts = _history_diagnostics_counts(filtered_entries)
    lines = [
        "Release History Summary",
        f"matched_entries={len(filtered_entries)}",
        f"total_entries={len(all_entries)}",
        (
            "status_counts: "
            f"success={status_counts['success']} "
            f"failed={status_counts['failed']} "
            f"unknown={status_counts['unknown']}"
        ),
        (
            "artifact_counts: "
            f"manifest={artifact_counts['manifest']} "
            f"log={artifact_counts['log']} "
            f"package={artifact_counts['package']} "
            f"version={artifact_counts['version']}"
        ),
        (
            "diagnostics_counts: "
            f"clean={diagnostics_counts['clean']} "
            f"warnings={diagnostics_counts['warnings']} "
            f"errors={diagnostics_counts['errors']} "
            f"unknown={diagnostics_counts['unknown']}"
        ),
        (
            "filters: "
            f"range={range_filter or 'all'}, "
            f"status={status_filter or 'all'}, "
            f"profile={profile_filter or 'all'}, "
            f"artifact={artifact_filter or 'all'}, "
            f"diagnostics={diagnostics_filter or 'all'}, "
            f"sort={sort_mode or 'newest'}, "
            f"search={search_text or '-'}"
        ),
        "",
    ]
    lines.extend(_history_summary_line(entry) for entry in filtered_entries)
    return "\n".join(lines).rstrip() + "\n"


def _build_filtered_history_json(
    filtered_entries: list[dict[str, object]],
    all_entries: list[dict[str, object]],
    *,
    range_filter: str,
    status_filter: str,
    profile_filter: str,
    artifact_filter: str,
    diagnostics_filter: str,
    sort_mode: str,
    search_text: str,
) -> str:
    payload = {
        "matched_entries": len(filtered_entries),
        "total_entries": len(all_entries),
        "status_counts": _history_status_counts(filtered_entries),
        "artifact_counts": _history_artifact_counts(filtered_entries),
        "diagnostics_counts": _history_diagnostics_counts(filtered_entries),
        "filters": {
            "range": range_filter or "all",
            "status": status_filter or "all",
            "profile": profile_filter or "all",
            "artifact": artifact_filter or "all",
            "diagnostics": diagnostics_filter or "all",
            "sort": sort_mode or "newest",
            "search": search_text or "-",
        },
        "entries": filtered_entries,
    }
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def _write_text_file(path: str, content: str) -> None:
    resolved_path = os.path.abspath(os.path.normpath(path))
    parent_dir = os.path.dirname(resolved_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)
    with open(resolved_path, "w", encoding="utf-8") as f:
        f.write(content)


def _append_suffix_if_missing(path: str, suffix: str) -> str:
    if not path:
        return ""
    root, ext = os.path.splitext(path)
    if ext:
        return path
    return root + suffix


def _safe_filename_part(text: str) -> str:
    normalized = "".join(char.lower() if char.isalnum() else "-" for char in (text or "").strip())
    collapsed = "-".join(part for part in normalized.split("-") if part)
    return collapsed[:40]


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

    def __init__(
        self,
        history_entries: list[dict[str, object]],
        open_path_callback=None,
        history_path: str = "",
        refresh_history_callback=None,
        project_key: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Release History")
        self.resize(1040, 680)
        self._config = get_config()
        self._open_path_callback = open_path_callback
        self._history_path = os.path.abspath(os.path.normpath(history_path)) if history_path else ""
        self._refresh_history_callback = refresh_history_callback
        self._project_key = str(project_key or "").strip()
        self._preview_mode = "auto"
        self._all_history_entries: list[dict[str, object]] = []
        self._filtered_history_entries: list[dict[str, object]] = []

        root_layout = QVBoxLayout(self)

        filter_row = QHBoxLayout()
        root_layout.addLayout(filter_row)

        filter_row.addWidget(QLabel("Range"))
        self._range_filter_combo = QComboBox()
        self._range_filter_combo.addItem("Any", "")
        self._range_filter_combo.addItem("Last 24h", "24h")
        self._range_filter_combo.addItem("Last 7d", "7d")
        self._range_filter_combo.addItem("Last 30d", "30d")
        self._range_filter_combo.currentIndexChanged.connect(self._apply_history_filter)
        filter_row.addWidget(self._range_filter_combo)

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

        filter_row.addWidget(QLabel("Artifact"))
        self._artifact_filter_combo = QComboBox()
        self._artifact_filter_combo.addItem("Any", "")
        self._artifact_filter_combo.addItem("Has Manifest", "manifest")
        self._artifact_filter_combo.addItem("Missing Manifest", "missing_manifest")
        self._artifact_filter_combo.addItem("Has Log", "log")
        self._artifact_filter_combo.addItem("Missing Log", "missing_log")
        self._artifact_filter_combo.addItem("Has Package", "package")
        self._artifact_filter_combo.addItem("Missing Package", "missing_package")
        self._artifact_filter_combo.addItem("Has Version", "version")
        self._artifact_filter_combo.addItem("Missing Version", "missing_version")
        self._artifact_filter_combo.currentIndexChanged.connect(self._apply_history_filter)
        filter_row.addWidget(self._artifact_filter_combo)

        filter_row.addWidget(QLabel("Diagnostics"))
        self._diagnostics_filter_combo = QComboBox()
        self._diagnostics_filter_combo.addItem("Any", "")
        self._diagnostics_filter_combo.addItem("Clean", "clean")
        self._diagnostics_filter_combo.addItem("Warnings", "warnings")
        self._diagnostics_filter_combo.addItem("Errors", "errors")
        self._diagnostics_filter_combo.addItem("Issues", "issues")
        self._diagnostics_filter_combo.addItem("Unknown", "unknown")
        self._diagnostics_filter_combo.currentIndexChanged.connect(self._apply_history_filter)
        filter_row.addWidget(self._diagnostics_filter_combo)

        filter_row.addWidget(QLabel("Sort"))
        self._sort_combo = QComboBox()
        self._sort_combo.addItem("Newest First", "newest")
        self._sort_combo.addItem("Oldest First", "oldest")
        self._sort_combo.addItem("Status", "status")
        self._sort_combo.addItem("Diagnostics", "diagnostics")
        self._sort_combo.addItem("Profile", "profile")
        self._sort_combo.currentIndexChanged.connect(self._apply_history_filter)
        filter_row.addWidget(self._sort_combo)

        filter_row.addWidget(QLabel("Search"))
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("build id, message, SDK revision...")
        self._search_edit.textChanged.connect(self._apply_history_filter)
        filter_row.addWidget(self._search_edit, 1)

        self._result_count_label = QLabel("0 / 0")
        filter_row.addWidget(self._result_count_label)

        self._status_breakdown_label = QLabel("success 0 | failed 0 | unknown 0")
        filter_row.addWidget(self._status_breakdown_label)

        self._artifact_breakdown_label = QLabel("manifest 0 | log 0 | package 0 | version 0")
        filter_row.addWidget(self._artifact_breakdown_label)

        self._diagnostics_breakdown_label = QLabel("clean 0 | warnings 0 | errors 0 | unknown 0")
        filter_row.addWidget(self._diagnostics_breakdown_label)

        self._clear_filters_button = QPushButton("Clear Filters")
        self._clear_filters_button.clicked.connect(self._clear_filters)
        filter_row.addWidget(self._clear_filters_button)

        self._reset_view_button = QPushButton("Reset View")
        self._reset_view_button.clicked.connect(self._reset_view)
        filter_row.addWidget(self._reset_view_button)

        self._copy_filtered_button = QPushButton("Copy Filtered")
        self._copy_filtered_button.clicked.connect(self._copy_filtered_summary)
        filter_row.addWidget(self._copy_filtered_button)

        self._copy_filtered_json_button = QPushButton("Copy Filtered JSON")
        self._copy_filtered_json_button.clicked.connect(self._copy_filtered_json)
        filter_row.addWidget(self._copy_filtered_json_button)

        self._export_filtered_button = QPushButton("Export Filtered...")
        self._export_filtered_button.clicked.connect(self._export_filtered_summary)
        filter_row.addWidget(self._export_filtered_button)

        self._open_history_file_button = QPushButton("Open History File")
        self._open_history_file_button.clicked.connect(self._open_history_file)
        filter_row.addWidget(self._open_history_file_button)

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

        self._preview_auto_button = QPushButton("Auto Preview")
        self._preview_manifest_button = QPushButton("Preview Manifest")
        self._preview_log_button = QPushButton("Preview Log")
        self._preview_version_button = QPushButton("Preview Version")
        self._copy_summary_button = QPushButton("Copy Summary")
        self._copy_details_button = QPushButton("Copy Details")
        self._copy_preview_button = QPushButton("Copy Preview")
        self._copy_entry_json_button = QPushButton("Copy Entry JSON")
        self._export_entry_json_button = QPushButton("Export Entry JSON...")
        self._open_folder_button = QPushButton("Open Folder")
        self._open_dist_button = QPushButton("Open Dist")
        self._open_version_button = QPushButton("Open Version")
        self._open_manifest_button = QPushButton("Open Manifest")
        self._open_log_button = QPushButton("Open Log")
        self._open_package_button = QPushButton("Open Package")
        for button in (
            self._preview_auto_button,
            self._preview_manifest_button,
            self._preview_log_button,
            self._preview_version_button,
        ):
            button.setCheckable(True)
        self._preview_auto_button.clicked.connect(lambda: self._activate_preview_mode("auto"))
        self._preview_manifest_button.clicked.connect(lambda: self._activate_preview_mode("manifest"))
        self._preview_log_button.clicked.connect(lambda: self._activate_preview_mode("log"))
        self._preview_version_button.clicked.connect(lambda: self._activate_preview_mode("version"))
        self._copy_summary_button.clicked.connect(self._copy_entry_summary)
        self._copy_details_button.clicked.connect(lambda: self._copy_text(self._details_edit.toPlainText()))
        self._copy_preview_button.clicked.connect(lambda: self._copy_text(self._preview_edit.toPlainText()))
        self._copy_entry_json_button.clicked.connect(self._copy_entry_json)
        self._export_entry_json_button.clicked.connect(self._export_entry_json)
        self._open_folder_button.clicked.connect(lambda: self._open_selected_path("release_root", "Release Folder"))
        self._open_dist_button.clicked.connect(lambda: self._open_selected_path("dist_dir", "Release Dist"))
        self._open_version_button.clicked.connect(self._open_selected_version)
        self._open_manifest_button.clicked.connect(lambda: self._open_selected_path("manifest_path", "Release Manifest"))
        self._open_log_button.clicked.connect(lambda: self._open_selected_path("log_path", "Release Log"))
        self._open_package_button.clicked.connect(lambda: self._open_selected_path("zip_path", "Release Package"))
        for button in (
            self._preview_auto_button,
            self._preview_manifest_button,
            self._preview_log_button,
            self._preview_version_button,
            self._copy_summary_button,
            self._copy_details_button,
            self._copy_preview_button,
            self._copy_entry_json_button,
            self._export_entry_json_button,
            self._open_folder_button,
            self._open_dist_button,
            self._open_version_button,
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
        self._restore_view_state()
        self._update_history_file_button()
        self._sync_preview_mode_buttons()

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
        self._update_history_file_button()

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

    def _matches_history_filter(
        self,
        entry: dict[str, object],
        range_filter: str,
        status_filter: str,
        profile_filter: str,
        artifact_filter: str,
        diagnostics_filter: str,
        search_text: str,
    ) -> bool:
        if range_filter:
            entry_timestamp = _history_timestamp(entry)
            if entry_timestamp is None:
                return False
            now = _utc_now()
            if range_filter == "24h":
                cutoff = now - timedelta(hours=24)
            elif range_filter == "7d":
                cutoff = now - timedelta(days=7)
            elif range_filter == "30d":
                cutoff = now - timedelta(days=30)
            else:
                cutoff = None
            if cutoff is not None and entry_timestamp < cutoff:
                return False
        if status_filter and _history_status(entry) != status_filter:
            return False
        if profile_filter and _history_string(entry, "profile_id") != profile_filter:
            return False
        if artifact_filter and not _history_has_artifact(entry, artifact_filter):
            return False
        if diagnostics_filter and not _history_matches_diagnostics(entry, diagnostics_filter):
            return False
        if search_text:
            search_tokens = [token for token in search_text.split() if token]
            searchable = " ".join(
                filter(
                    None,
                    (
                        _history_string(entry, "build_id"),
                        _history_status(entry),
                        _history_string(entry, "profile_id"),
                        _history_string(entry, "app_name"),
                        _history_string(entry, "message"),
                        _history_string(entry, "designer_revision"),
                        str(_history_int(entry, "warning_count") or ""),
                        str(_history_int(entry, "error_count") or ""),
                        "clean" if _history_matches_diagnostics(entry, "clean") else "",
                        "warnings" if _history_matches_diagnostics(entry, "warnings") else "",
                        "errors" if _history_matches_diagnostics(entry, "errors") else "",
                        "issues" if _history_matches_diagnostics(entry, "issues") else "",
                        _history_sdk_label(entry),
                        _history_string(entry.get("sdk") if isinstance(entry.get("sdk"), dict) else {}, "commit"),
                        "manifest" if _history_string(entry, "manifest_path") else "",
                        "log" if _history_string(entry, "log_path") else "",
                        "package" if _history_string(entry, "zip_path") else "",
                        "version" if _history_version_path(entry) else "",
                    ),
                )
            ).lower()
            if any(token not in searchable for token in search_tokens):
                return False
        return True

    def _apply_history_filter(self) -> None:
        wanted_range = str(self._range_filter_combo.currentData() or "")
        wanted_status = str(self._status_filter_combo.currentData() or "")
        wanted_profile = str(self._profile_filter_combo.currentData() or "")
        wanted_artifact = str(self._artifact_filter_combo.currentData() or "")
        wanted_diagnostics = str(self._diagnostics_filter_combo.currentData() or "")
        sort_mode = str(self._sort_combo.currentData() or "newest")
        search_text = self._search_edit.text().strip().lower()
        current_entry = self._current_entry()
        current_build_id = _history_string(current_entry, "build_id") if current_entry else ""

        filtered_entries = _sorted_history_entries(
            [
                entry
                for entry in self._all_history_entries
                if self._matches_history_filter(
                    entry,
                    wanted_range,
                    wanted_status,
                    wanted_profile,
                    wanted_artifact,
                    wanted_diagnostics,
                    search_text,
                )
            ],
            sort_mode,
        )
        self._filtered_history_entries = list(filtered_entries)
        self._result_count_label.setText(f"{len(filtered_entries)} / {len(self._all_history_entries)}")
        status_counts = _history_status_counts(self._filtered_history_entries)
        artifact_counts = _history_artifact_counts(self._filtered_history_entries)
        diagnostics_counts = _history_diagnostics_counts(self._filtered_history_entries)
        self._status_breakdown_label.setText(
            f"success {status_counts['success']} | failed {status_counts['failed']} | unknown {status_counts['unknown']}"
        )
        self._artifact_breakdown_label.setText(
            (
                f"manifest {artifact_counts['manifest']} | "
                f"log {artifact_counts['log']} | "
                f"package {artifact_counts['package']} | "
                f"version {artifact_counts['version']}"
            )
        )
        self._diagnostics_breakdown_label.setText(
            (
                f"clean {diagnostics_counts['clean']} | "
                f"warnings {diagnostics_counts['warnings']} | "
                f"errors {diagnostics_counts['errors']} | "
                f"unknown {diagnostics_counts['unknown']}"
            )
        )
        self._copy_filtered_button.setEnabled(bool(filtered_entries))
        self._copy_filtered_json_button.setEnabled(bool(filtered_entries))
        self._export_filtered_button.setEnabled(bool(filtered_entries))

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
            self._details_edit.setPlainText(
                "Adjust Range, Status, Profile, Artifact, Diagnostics, Sort, or Search to see matching release builds."
            )
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
        self._range_filter_combo.setCurrentIndex(0)
        self._status_filter_combo.setCurrentIndex(0)
        self._profile_filter_combo.setCurrentIndex(0)
        self._artifact_filter_combo.setCurrentIndex(0)
        self._diagnostics_filter_combo.setCurrentIndex(0)
        self._sort_combo.setCurrentIndex(self._sort_combo.findData("newest"))
        self._search_edit.clear()

    def _reset_view(self) -> None:
        self._clear_filters()
        self._activate_preview_mode("auto")
        if self._history_list.count():
            self._history_list.setCurrentRow(0)

    def _copy_filtered_summary(self) -> None:
        self._copy_text(self._filtered_summary_text())

    def _copy_filtered_json(self) -> None:
        self._copy_text(self._filtered_entries_json_text())

    def _export_filtered_summary(self) -> None:
        if not self._filtered_history_entries:
            return
        selected_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Release History Summary",
            self._default_filtered_export_filename(),
            "Text Files (*.txt);;JSON Files (*.json);;All Files (*)",
        )
        if not selected_path:
            return
        try:
            if "JSON" in str(selected_filter):
                selected_path = _append_suffix_if_missing(selected_path, ".json")
            elif "Text" in str(selected_filter):
                selected_path = _append_suffix_if_missing(selected_path, ".txt")
            content = self._filtered_export_text(selected_path)
            _write_text_file(selected_path, content)
        except OSError as exc:
            QMessageBox.warning(self, "Export Release History Failed", str(exc))

    def _filtered_summary_text(self) -> str:
        return _build_filtered_history_summary(
            self._filtered_history_entries,
            self._all_history_entries,
            range_filter=str(self._range_filter_combo.currentData() or ""),
            status_filter=str(self._status_filter_combo.currentData() or ""),
            profile_filter=str(self._profile_filter_combo.currentData() or ""),
            artifact_filter=str(self._artifact_filter_combo.currentData() or ""),
            diagnostics_filter=str(self._diagnostics_filter_combo.currentData() or ""),
            sort_mode=str(self._sort_combo.currentData() or "newest"),
            search_text=self._search_edit.text().strip(),
        )

    def _filtered_entries_json_text(self) -> str:
        return _build_filtered_history_json(
            self._filtered_history_entries,
            self._all_history_entries,
            range_filter=str(self._range_filter_combo.currentData() or ""),
            status_filter=str(self._status_filter_combo.currentData() or ""),
            profile_filter=str(self._profile_filter_combo.currentData() or ""),
            artifact_filter=str(self._artifact_filter_combo.currentData() or ""),
            diagnostics_filter=str(self._diagnostics_filter_combo.currentData() or ""),
            sort_mode=str(self._sort_combo.currentData() or "newest"),
            search_text=self._search_edit.text().strip(),
        )

    def _filtered_export_text(self, selected_path: str) -> str:
        if str(selected_path).lower().endswith(".json"):
            return self._filtered_entries_json_text()
        return self._filtered_summary_text()

    def _default_filtered_export_filename(self) -> str:
        parts = ["release-history-summary"]
        for value in (
            str(self._range_filter_combo.currentData() or ""),
            str(self._status_filter_combo.currentData() or ""),
            str(self._profile_filter_combo.currentData() or ""),
            str(self._artifact_filter_combo.currentData() or ""),
            str(self._diagnostics_filter_combo.currentData() or ""),
            "" if str(self._sort_combo.currentData() or "newest") == "newest" else str(self._sort_combo.currentData() or ""),
            self._search_edit.text().strip(),
        ):
            safe_value = _safe_filename_part(value)
            if safe_value:
                parts.append(safe_value)
        return "-".join(parts) + ".txt"

    def _restore_view_state(self) -> None:
        state = self._config.release_history_view if isinstance(self._config.release_history_view, dict) else {}
        if self._project_key:
            projects = state.get("projects", {}) if isinstance(state.get("projects", {}), dict) else {}
            state = projects.get(self._project_key, {}) if isinstance(projects.get(self._project_key, {}), dict) else {}
        range_value = str(state.get("range_filter") or "")
        status_value = str(state.get("status_filter") or "")
        profile_value = str(state.get("profile_filter") or "")
        artifact_value = str(state.get("artifact_filter") or "")
        diagnostics_value = str(state.get("diagnostics_filter") or "")
        sort_value = str(state.get("sort_mode") or "newest")
        search_text = str(state.get("search_text") or "")
        selected_build_id = str(state.get("selected_build_id") or "")
        self._preview_mode = str(state.get("preview_mode") or "auto").strip().lower()
        if self._preview_mode not in {"auto", "manifest", "log", "version"}:
            self._preview_mode = "auto"

        index = self._range_filter_combo.findData(range_value)
        self._range_filter_combo.setCurrentIndex(index if index >= 0 else 0)

        index = self._status_filter_combo.findData(status_value)
        self._status_filter_combo.setCurrentIndex(index if index >= 0 else 0)

        index = self._profile_filter_combo.findData(profile_value)
        self._profile_filter_combo.setCurrentIndex(index if index >= 0 else 0)

        index = self._artifact_filter_combo.findData(artifact_value)
        self._artifact_filter_combo.setCurrentIndex(index if index >= 0 else 0)

        index = self._diagnostics_filter_combo.findData(diagnostics_value)
        self._diagnostics_filter_combo.setCurrentIndex(index if index >= 0 else 0)

        index = self._sort_combo.findData(sort_value)
        self._sort_combo.setCurrentIndex(index if index >= 0 else 0)

        self._search_edit.setText(search_text)
        self._select_history_entry_by_build_id(selected_build_id)
        if self._current_entry():
            self._refresh_selected_preview()

    def _save_view_state(self) -> None:
        current_entry = self._current_entry()
        view_state = {
            "range_filter": str(self._range_filter_combo.currentData() or ""),
            "status_filter": str(self._status_filter_combo.currentData() or ""),
            "profile_filter": str(self._profile_filter_combo.currentData() or ""),
            "artifact_filter": str(self._artifact_filter_combo.currentData() or ""),
            "diagnostics_filter": str(self._diagnostics_filter_combo.currentData() or ""),
            "sort_mode": str(self._sort_combo.currentData() or "newest"),
            "search_text": self._search_edit.text(),
            "preview_mode": self._preview_mode,
            "selected_build_id": _history_string(current_entry or {}, "build_id"),
        }
        current_state = self._config.release_history_view if isinstance(self._config.release_history_view, dict) else {}
        if self._project_key:
            next_state = dict(current_state)
            projects = current_state.get("projects", {}) if isinstance(current_state.get("projects", {}), dict) else {}
            next_projects = dict(projects)
            next_projects[self._project_key] = dict(view_state)
            next_state["projects"] = next_projects
            self._config.release_history_view = next_state
        else:
            next_state = dict(view_state)
            projects = current_state.get("projects", {}) if isinstance(current_state.get("projects", {}), dict) else {}
            if projects:
                next_state["projects"] = dict(projects)
            self._config.release_history_view = next_state
        self._config.save()

    def done(self, result: int) -> None:
        self._save_view_state()
        super().done(result)

    def _copy_entry_json(self) -> None:
        self._copy_text(self._entry_json_text())

    def _entry_json_text(self) -> str:
        entry = self._current_entry()
        if not entry:
            return ""
        return json.dumps(entry, indent=2, ensure_ascii=False) + "\n"

    def _export_entry_json(self) -> None:
        if not self._current_entry():
            return
        selected_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Release Entry JSON",
            self._default_entry_export_filename(),
            "JSON Files (*.json);;All Files (*)",
        )
        if not selected_path:
            return
        try:
            if "JSON" in str(selected_filter):
                selected_path = _append_suffix_if_missing(selected_path, ".json")
            _write_text_file(selected_path, self._entry_json_text())
        except OSError as exc:
            QMessageBox.warning(self, "Export Release Entry Failed", str(exc))

    def _default_entry_export_filename(self) -> str:
        entry = self._current_entry() or {}
        parts = [
            "release-entry",
            _safe_filename_part(_history_string(entry, "build_id") or "unknown-build"),
            _safe_filename_part(_history_string(entry, "profile_id") or "unknown-profile"),
        ]
        status_part = _safe_filename_part(_history_status(entry))
        if status_part:
            parts.append(status_part)
        return "-".join(part for part in parts if part) + ".json"

    def _copy_entry_summary(self) -> None:
        entry = self._current_entry()
        if not entry:
            self._copy_text("")
            return
        self._copy_text(_history_summary_line(entry) + "\n")

    def _activate_preview_mode(self, mode: str) -> None:
        self._preview_mode = mode if mode in {"auto", "manifest", "log", "version"} else "auto"
        self._sync_preview_mode_buttons()
        self._refresh_selected_preview()

    def _select_history_entry_by_build_id(self, build_id: str) -> None:
        wanted_build_id = str(build_id or "").strip()
        if not wanted_build_id:
            return
        for row in range(self._history_list.count()):
            item = self._history_list.item(row)
            if item is None:
                continue
            entry = item.data(Qt.UserRole)
            if isinstance(entry, dict) and _history_string(entry, "build_id") == wanted_build_id:
                self._history_list.setCurrentRow(row)
                return

    def _refresh_selected_preview(self) -> None:
        entry = self._current_entry()
        if entry is None:
            self._preview_label.setText("Preview")
            self._preview_edit.clear()
            return
        if self._preview_mode == "manifest":
            self._preview_selected_path("manifest_path", "Manifest", prefer_json=True)
            return
        if self._preview_mode == "log":
            self._preview_selected_path("log_path", "Log")
            return
        if self._preview_mode == "version":
            self._preview_selected_version()
            return
        if _history_string(entry, "manifest_path"):
            self._preview_selected_path("manifest_path", "Manifest", prefer_json=True)
        elif _history_string(entry, "log_path"):
            self._preview_selected_path("log_path", "Log")
        elif _history_version_path(entry):
            self._preview_selected_version()
        else:
            self._preview_label.setText("Preview")
            self._preview_edit.setPlainText("No manifest, version file, or build log is recorded for this release entry.")

    def _sync_preview_mode_buttons(self) -> None:
        self._preview_auto_button.setChecked(self._preview_mode == "auto")
        self._preview_manifest_button.setChecked(self._preview_mode == "manifest")
        self._preview_log_button.setChecked(self._preview_mode == "log")
        self._preview_version_button.setChecked(self._preview_mode == "version")

    def _update_history_file_button(self) -> None:
        self._open_history_file_button.setEnabled(bool(self._open_path_callback and self._history_path and os.path.isfile(self._history_path)))

    def _open_history_file(self) -> None:
        if self._open_path_callback is None or not self._history_path or not os.path.isfile(self._history_path):
            return
        try:
            self._open_path_callback(self._history_path)
        except Exception as exc:
            QMessageBox.warning(self, "Open Release History File Failed", str(exc))

    def _set_open_buttons(self, entry: dict[str, object] | None) -> None:
        release_root = _history_string(entry or {}, "release_root")
        dist_dir = _history_string(entry or {}, "dist_dir")
        manifest_path = _history_string(entry or {}, "manifest_path")
        log_path = _history_string(entry or {}, "log_path")
        package_path = _history_string(entry or {}, "zip_path")
        self._preview_auto_button.setEnabled(bool(entry))
        self._preview_manifest_button.setEnabled(bool(entry and _history_string(entry, "manifest_path")))
        self._preview_log_button.setEnabled(bool(entry and _history_string(entry, "log_path")))
        self._preview_version_button.setEnabled(bool(entry and _history_version_path(entry)))
        self._copy_summary_button.setEnabled(bool(entry))
        self._copy_details_button.setEnabled(bool(entry))
        self._copy_preview_button.setEnabled(bool(entry))
        self._copy_entry_json_button.setEnabled(bool(entry))
        self._export_entry_json_button.setEnabled(bool(entry))
        self._open_folder_button.setEnabled(bool(release_root and os.path.isdir(release_root)))
        self._open_dist_button.setEnabled(bool(dist_dir and os.path.isdir(dist_dir)))
        self._open_version_button.setEnabled(bool(entry and _history_version_path(entry)))
        self._open_manifest_button.setEnabled(bool(manifest_path and os.path.isfile(manifest_path)))
        self._open_log_button.setEnabled(bool(log_path and os.path.isfile(log_path)))
        self._open_package_button.setEnabled(bool(package_path and os.path.isfile(package_path)))

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
        self._refresh_selected_preview()

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

    def _open_selected_version(self) -> None:
        if self._open_path_callback is None:
            return
        entry = self._current_entry()
        path = _history_version_path(entry or {})
        if not path:
            return
        try:
            self._open_path_callback(path)
        except Exception as exc:
            QMessageBox.warning(self, "Open Release Version Failed", str(exc))

    def _preview_selected_path(self, key: str, label: str, *, prefer_json: bool = False) -> None:
        entry = self._current_entry()
        path = _history_string(entry or {}, key)
        self._preview_label.setText(f"{label} Preview")
        if not path:
            self._preview_edit.setPlainText(f"No {label.lower()} path recorded for this release entry.")
            return
        self._preview_edit.setPlainText(_preview_file_text(path, prefer_json=prefer_json))

    def _preview_selected_version(self) -> None:
        entry = self._current_entry()
        path = _history_version_path(entry or {})
        self._preview_label.setText("Version Preview")
        if not path:
            self._preview_edit.setPlainText("No version file is available for this release entry.")
            return
        self._preview_edit.setPlainText(_preview_file_text(path))

    def _copy_text(self, text: str) -> None:
        QApplication.clipboard().setText(text or "")
