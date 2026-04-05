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
    QFrame,
    QFormLayout,
    QGridLayout,
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

from .iconography import make_icon
from ..model.config import get_config
from ..model.release import ReleaseConfig, ReleaseProfile


_PREVIEW_CHAR_LIMIT = 65536
_LIST_DIAGNOSTIC_LIMIT = 72


def _set_widget_metadata(widget, *, tooltip=None, accessible_name=None) -> None:
    if tooltip is not None:
        hint = str(tooltip or "")
        if str(widget.property("_release_dialog_hint_snapshot") or "") != hint:
            widget.setToolTip(hint)
            widget.setStatusTip(hint)
            widget.setProperty("_release_dialog_hint_snapshot", hint)
    if accessible_name is not None:
        name = str(accessible_name or "")
        if str(widget.property("_release_dialog_accessible_snapshot") or "") != name:
            widget.setAccessibleName(name)
            widget.setProperty("_release_dialog_accessible_snapshot", name)


def _count_label(count: int, singular: str, plural: str | None = None) -> str:
    value = max(int(count or 0), 0)
    noun = singular if value == 1 else (plural or f"{singular}s")
    return f"{value} {noun}"


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


def _history_sdk_export_payload(entry: dict[str, object]) -> dict[str, object]:
    sdk = entry.get("sdk")
    if not isinstance(sdk, dict):
        return {
            "sdk_source_kind": "",
            "sdk_source_root": "",
            "sdk_revision": "",
            "sdk_commit": "",
            "sdk_remote": "",
            "sdk_dirty": False,
        }
    return {
        "sdk_source_kind": str(sdk.get("source_kind") or "").strip(),
        "sdk_source_root": str(sdk.get("source_root") or "").strip(),
        "sdk_revision": str(sdk.get("revision") or sdk.get("commit_short") or sdk.get("commit") or "").strip(),
        "sdk_commit": str(sdk.get("commit") or "").strip(),
        "sdk_remote": str(sdk.get("remote") or "").strip(),
        "sdk_dirty": bool(sdk.get("dirty", False)),
    }


def _truncate_history_text(text: str, limit: int) -> str:
    normalized = str(text or "").strip()
    if limit <= 0 or len(normalized) <= limit:
        return normalized
    if limit <= 3:
        return normalized[:limit]
    return normalized[: limit - 3].rstrip() + "..."


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
    first_diagnostic = _history_string(entry, "first_diagnostic")
    if first_diagnostic:
        parts.append(f"diag {_truncate_history_text(first_diagnostic, _LIST_DIAGNOSTIC_LIMIT)}")
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
    diagnostics_total = entry.get("diagnostics_total")
    if diagnostics_total not in (None, ""):
        lines.append(f"Diagnostics Total: {diagnostics_total}")
    first_diagnostic = _history_string(entry, "first_diagnostic")
    if first_diagnostic:
        lines.append(f"First Diagnostic: {first_diagnostic}")

    sdk = entry.get("sdk")
    if isinstance(sdk, dict):
        source_kind = str(sdk.get("source_kind") or "").strip()
        source_root = str(sdk.get("source_root") or "").strip()
        commit = str(sdk.get("commit") or "").strip()
        remote = str(sdk.get("remote") or "").strip()
        if source_kind:
            lines.append(f"SDK Source: {source_kind}")
        if source_root:
            lines.append(f"SDK Source Root: {source_root}")
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
    line = f"{build_id} | {status} | {profile_id} | sdk {sdk_label} | {message}"
    first_diagnostic = _history_string(entry, "first_diagnostic")
    if first_diagnostic:
        line += f" | diag {first_diagnostic}"
    return line


def _history_searchable_text(entry: dict[str, object]) -> str:
    return " ".join(
        filter(
            None,
            (
                _history_summary_line(entry),
                _history_list_label(entry),
                _history_detail_text(entry),
                "clean" if _history_matches_diagnostics(entry, "clean") else "",
                "warnings" if _history_matches_diagnostics(entry, "warnings") else "",
                "errors" if _history_matches_diagnostics(entry, "errors") else "",
                "issues" if _history_matches_diagnostics(entry, "issues") else "",
                "manifest" if _history_string(entry, "manifest_path") else "",
                "log" if _history_string(entry, "log_path") else "",
                "package" if _history_string(entry, "zip_path") else "",
                "version" if _history_version_path(entry) else "",
            ),
        )
    ).lower()


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
    summary_text = _build_filtered_history_summary(
        filtered_entries,
        all_entries,
        range_filter=range_filter,
        status_filter=status_filter,
        profile_filter=profile_filter,
        artifact_filter=artifact_filter,
        diagnostics_filter=diagnostics_filter,
        sort_mode=sort_mode,
        search_text=search_text,
    )
    export_entries = []
    for entry in filtered_entries:
        export_entries.append(_history_entry_export_payload(entry, include_details=True))

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
        "summary_text": summary_text,
        "entries": export_entries,
    }
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def _history_entry_export_payload(entry: dict[str, object], *, include_details: bool = False) -> dict[str, object]:
    payload_entry = dict(entry or {})
    payload_entry.update(_history_sdk_export_payload(entry or {}))
    payload_entry["summary_line"] = _history_summary_line(entry or {})
    payload_entry["list_label"] = _history_list_label(entry or {})
    if include_details:
        payload_entry["details_text"] = _history_detail_text(entry or {})
    return payload_entry


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


def _preview_file_text(path: str, *, prefer_json: bool = False, char_limit: int | None = _PREVIEW_CHAR_LIMIT) -> str:
    resolved_path = os.path.abspath(os.path.normpath(path))
    if not os.path.isfile(resolved_path):
        return f"File not found:\n{resolved_path}"

    try:
        with open(resolved_path, "r", encoding="utf-8", errors="replace") as f:
            if char_limit is None:
                content = f.read()
                truncated = False
            else:
                content = f.read(char_limit + 1)
                truncated = len(content) > char_limit
    except OSError as exc:
        return f"Failed to read file:\n{resolved_path}\n\n{exc}"

    if char_limit is not None and truncated:
        content = content[:char_limit]

    if prefer_json:
        try:
            parsed = json.loads(content)
            content = json.dumps(parsed, indent=2, ensure_ascii=False)
        except (ValueError, TypeError):
            pass

    if char_limit is not None and truncated:
        content = content.rstrip() + f"\n\n[truncated to first {char_limit} characters]"
    return content


class ReleaseBuildDialog(QDialog):
    """Confirm a release build and choose a release profile."""

    def __init__(self, release_config: ReleaseConfig, sdk_label: str, output_root: str, warning_count: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Release Build")
        self.setMinimumSize(860, 560)
        self.resize(920, 600)
        self._release_config = release_config

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        self._header_frame = QFrame()
        self._header_frame.setObjectName("release_build_header")
        header_layout = QHBoxLayout(self._header_frame)
        header_layout.setContentsMargins(24, 22, 24, 22)
        header_layout.setSpacing(24)

        hero_copy = QVBoxLayout()
        hero_copy.setContentsMargins(0, 0, 0, 0)
        hero_copy.setSpacing(6)

        self._eyebrow_label = QLabel("Release Pipeline")
        self._eyebrow_label.setObjectName("release_build_eyebrow")
        _set_widget_metadata(
            self._eyebrow_label,
            tooltip="Release pipeline workspace.",
            accessible_name="Release pipeline workspace.",
        )
        hero_copy.addWidget(self._eyebrow_label, 0, Qt.AlignLeft)

        self._title_label = QLabel("Prepare Release Build")
        self._title_label.setObjectName("release_build_title")
        _set_widget_metadata(
            self._title_label,
            tooltip="Release build title: Prepare Release Build.",
            accessible_name="Release build title: Prepare Release Build.",
        )
        hero_copy.addWidget(self._title_label)

        self._subtitle_label = QLabel(
            "Confirm the profile, verify SDK binding and output location, then decide how strict packaging should be for this release run."
        )
        self._subtitle_label.setObjectName("release_build_subtitle")
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

        metrics_layout = QVBoxLayout()
        metrics_layout.setContentsMargins(0, 0, 0, 0)
        metrics_layout.setSpacing(8)
        self._profile_metric_value = self._create_metric_card(metrics_layout, "Profile")
        self._diagnostics_metric_value = self._create_metric_card(metrics_layout, "Diagnostics")
        self._package_metric_value = self._create_metric_card(metrics_layout, "Packaging")
        header_layout.addLayout(metrics_layout, 2)
        layout.addWidget(self._header_frame)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(16)

        context_card = QFrame()
        context_card.setObjectName("release_build_card")
        context_layout = QVBoxLayout(context_card)
        context_layout.setContentsMargins(22, 22, 22, 22)
        context_layout.setSpacing(12)

        context_title = QLabel("Build Context")
        context_title.setObjectName("workspace_section_title")
        context_layout.addWidget(context_title)

        context_hint = QLabel("The selected profile drives target settings, while the SDK and output path define the actual packaging workspace.")
        context_hint.setObjectName("workspace_section_subtitle")
        context_hint.setWordWrap(True)
        context_layout.addWidget(context_hint)
        context_hint.hide()

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        form.setLabelAlignment(Qt.AlignLeft | Qt.AlignTop)
        form.setFormAlignment(Qt.AlignTop)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(12)
        self._profile_combo = QComboBox()
        for profile in release_config.profiles:
            self._profile_combo.addItem(f"{profile.name} ({profile.id})", profile.id)
        selected_profile = release_config.get_profile().id
        index = self._profile_combo.findData(selected_profile)
        if index >= 0:
            self._profile_combo.setCurrentIndex(index)
        self._profile_combo.currentIndexChanged.connect(self._update_accessibility_summary)
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
        context_layout.addLayout(form)
        context_layout.addStretch(1)
        content_layout.addWidget(context_card, 3)

        options_card = QFrame()
        options_card.setObjectName("release_build_card")
        options_layout = QVBoxLayout(options_card)
        options_layout.setContentsMargins(22, 22, 22, 22)
        options_layout.setSpacing(12)

        options_title = QLabel("Build Options")
        options_title.setObjectName("workspace_section_title")
        options_layout.addWidget(options_title)

        options_hint = QLabel("Choose whether warnings should block the build and whether the output should also be packaged as a zip artifact.")
        options_hint.setObjectName("workspace_section_subtitle")
        options_hint.setWordWrap(True)
        options_layout.addWidget(options_hint)
        options_hint.hide()

        self._warnings_as_errors = QCheckBox("Treat warnings as errors")
        self._warnings_as_errors.toggled.connect(self._update_accessibility_summary)
        options_layout.addWidget(self._warnings_as_errors)

        self._package_release = QCheckBox("Create zip package")
        self._package_release.setChecked(True)
        self._package_release.toggled.connect(self._update_accessibility_summary)
        options_layout.addWidget(self._package_release)

        self._release_note_label = QLabel(
            "Release build runs against the current project state. Review warnings before enabling stricter failure rules."
        )
        self._release_note_label.setObjectName("workspace_section_subtitle")
        self._release_note_label.setWordWrap(True)
        options_layout.addWidget(self._release_note_label)
        self._release_note_label.hide()
        options_layout.addStretch(1)
        content_layout.addWidget(options_card, 2)
        layout.addLayout(content_layout, 1)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self._ok_button = button_box.button(QDialogButtonBox.Ok)
        self._cancel_button = button_box.button(QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        self._update_accessibility_summary()

    def _create_metric_card(self, layout: QVBoxLayout, label_text: str) -> QLabel:
        card = QFrame()
        card.setObjectName("release_build_metric_card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(4)

        label = QLabel(label_text)
        label.setObjectName("release_build_metric_label")
        card_layout.addWidget(label)

        value = QLabel("")
        value.setObjectName("release_build_metric_value")
        value.setWordWrap(True)
        card_layout.addWidget(value)

        value._release_build_metric_name = label_text
        value._release_build_metric_label = label
        value._release_build_metric_card = card
        _set_widget_metadata(
            label,
            tooltip=f"{label_text} metric label.",
            accessible_name=f"{label_text} metric label.",
        )
        layout.addWidget(card)
        return value

    def _update_metric_card_metadata(self, metric_value: QLabel) -> None:
        metric_name = getattr(metric_value, "_release_build_metric_name", "Release")
        metric_text = (metric_value.text() or "none").strip() or "none"
        summary = f"{metric_name}: {metric_text}."

        _set_widget_metadata(
            metric_value,
            tooltip=summary,
            accessible_name=f"Release build metric: {metric_name}. {metric_text}.",
        )

        label = getattr(metric_value, "_release_build_metric_label", None)
        if label is not None:
            _set_widget_metadata(
                label,
                tooltip=summary,
                accessible_name=f"{metric_name} metric label.",
            )

        card = getattr(metric_value, "_release_build_metric_card", None)
        if card is not None:
            _set_widget_metadata(
                card,
                tooltip=summary,
                accessible_name=f"{metric_name} metric: {metric_text}.",
            )

    def _update_accessibility_summary(self) -> None:
        profile_text = self._profile_combo.currentText() or "none"
        output_root = self._output_label.text() or "none"
        diagnostics_text = self._warnings_label.text()
        release_context = f"Current profile: {profile_text}. Output root: {output_root}. Diagnostics: {diagnostics_text}."
        self._profile_metric_value.setText(profile_text)
        self._diagnostics_metric_value.setText(diagnostics_text)
        self._package_metric_value.setText(
            "Zip + directory" if self._package_release.isChecked() else "Directory only"
        )
        summary = (
            f"Release build: profile {profile_text}. "
            f"{self._sdk_label.text() or 'SDK: unknown'}. "
            f"Output: {output_root}. "
            f"Diagnostics: {diagnostics_text}. "
            f"Warnings as errors {'on' if self._warnings_as_errors.isChecked() else 'off'}. "
            f"Create zip package {'on' if self._package_release.isChecked() else 'off'}."
        )
        _set_widget_metadata(self, tooltip=summary, accessible_name=summary)
        _set_widget_metadata(
            self._header_frame,
            tooltip=f"Release build header. {summary}",
            accessible_name=f"Release build header. {summary}",
        )
        _set_widget_metadata(
            self._profile_combo,
            tooltip=f"Choose the release profile. {release_context}",
            accessible_name=f"Release profile: {profile_text}",
        )
        _set_widget_metadata(
            self._sdk_label,
            tooltip=f"{self._sdk_label.text()}. {release_context}",
            accessible_name=f"Release SDK: {self._sdk_label.text()}",
        )
        _set_widget_metadata(
            self._output_label,
            tooltip=f"Release output root: {output_root}. Current profile: {profile_text}. Diagnostics: {diagnostics_text}.",
            accessible_name=f"Release output root: {self._output_label.text() or 'none'}",
        )
        _set_widget_metadata(
            self._warnings_label,
            tooltip=f"Release diagnostics summary: {diagnostics_text}. Current profile: {profile_text}. Output root: {output_root}.",
            accessible_name=f"Release diagnostics summary: {self._warnings_label.text()}",
        )
        _set_widget_metadata(
            self._warnings_as_errors,
            tooltip=(
                f"Treat release warnings as build errors. {release_context}"
                if self._warnings_as_errors.isChecked()
                else f"Allow release builds to continue when warnings are present. {release_context}"
            ),
            accessible_name=f"Treat warnings as errors: {'on' if self._warnings_as_errors.isChecked() else 'off'}",
        )
        _set_widget_metadata(
            self._package_release,
            tooltip=(
                f"Create a zip package in addition to the release directory. {release_context}"
                if self._package_release.isChecked()
                else f"Create only the release directory without a zip package. {release_context}"
            ),
            accessible_name=f"Create zip package: {'on' if self._package_release.isChecked() else 'off'}",
        )
        if self._ok_button is not None:
            _set_widget_metadata(
                self._ok_button,
                tooltip=(
                    f"Start the release build with profile {profile_text}. "
                    f"Output root: {output_root}. Diagnostics: {diagnostics_text}. "
                    f"Warnings as errors {'on' if self._warnings_as_errors.isChecked() else 'off'}. "
                    f"Create zip package {'on' if self._package_release.isChecked() else 'off'}."
                ),
                accessible_name=f"Start release build: {profile_text}",
            )
        if self._cancel_button is not None:
            _set_widget_metadata(
                self._cancel_button,
                tooltip=f"Cancel the release build. {release_context}",
                accessible_name="Cancel release build",
            )
        self._update_metric_card_metadata(self._profile_metric_value)
        self._update_metric_card_metadata(self._diagnostics_metric_value)
        self._update_metric_card_metadata(self._package_metric_value)

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
        self.setMinimumSize(980, 680)
        self.resize(1040, 720)
        self._release_config = ReleaseConfig.from_dict(release_config.to_dict())

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(24, 24, 24, 24)
        root_layout.setSpacing(16)

        self._header_frame = QFrame()
        self._header_frame.setObjectName("release_profiles_header")
        header_layout = QHBoxLayout(self._header_frame)
        header_layout.setContentsMargins(24, 22, 24, 22)
        header_layout.setSpacing(24)

        hero_copy = QVBoxLayout()
        hero_copy.setContentsMargins(0, 0, 0, 0)
        hero_copy.setSpacing(6)

        self._eyebrow_label = QLabel("Release Configuration")
        self._eyebrow_label.setObjectName("release_profiles_eyebrow")
        _set_widget_metadata(
            self._eyebrow_label,
            tooltip="Release configuration workspace.",
            accessible_name="Release configuration workspace.",
        )
        hero_copy.addWidget(self._eyebrow_label, 0, Qt.AlignLeft)

        self._title_label = QLabel("Manage Release Profiles")
        self._title_label.setObjectName("release_profiles_title")
        _set_widget_metadata(
            self._title_label,
            tooltip="Release profiles title: Manage Release Profiles.",
            accessible_name="Release profiles title: Manage Release Profiles.",
        )
        hero_copy.addWidget(self._title_label)

        self._subtitle_label = QLabel(
            "Define packaging targets, ports, and output behavior per release profile, then mark the one that should be used by default."
        )
        self._subtitle_label.setObjectName("release_profiles_subtitle")
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

        metrics_layout = QVBoxLayout()
        metrics_layout.setContentsMargins(0, 0, 0, 0)
        metrics_layout.setSpacing(8)
        self._profile_count_metric_value = self._create_metric_card(metrics_layout, "Profiles")
        self._default_metric_value = self._create_metric_card(metrics_layout, "Default")
        self._selection_metric_value = self._create_metric_card(metrics_layout, "Selection")
        header_layout.addLayout(metrics_layout, 2)
        root_layout.addWidget(self._header_frame)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(16)
        root_layout.addLayout(content_layout, 1)

        left_card = QFrame()
        left_card.setObjectName("release_profiles_card")
        left_panel = QVBoxLayout(left_card)
        left_panel.setContentsMargins(22, 22, 22, 22)
        left_panel.setSpacing(12)

        left_title = QLabel("Profiles")
        left_title.setObjectName("workspace_section_title")
        left_panel.addWidget(left_title)

        left_hint = QLabel("Use this list as the single source of release targets. Default state is shown directly in the item label.")
        left_hint.setObjectName("workspace_section_subtitle")
        left_hint.setWordWrap(True)
        left_panel.addWidget(left_hint)
        left_hint.hide()

        self._profile_list = QListWidget()
        self._profile_list.setObjectName("release_profiles_list")
        self._profile_list.setSpacing(8)
        self._profile_list.currentRowChanged.connect(self._load_profile_into_form)
        left_panel.addWidget(self._profile_list, 1)

        left_actions = QGridLayout()
        left_actions.setHorizontalSpacing(10)
        left_actions.setVerticalSpacing(10)
        self._add_btn = QPushButton("Add")
        self._add_btn.setIcon(make_icon("toolbar.new"))
        self._copy_btn = QPushButton("Copy")
        self._copy_btn.setIcon(make_icon("toolbar.copy"))
        self._delete_btn = QPushButton("Delete")
        self._delete_btn.setIcon(make_icon("toolbar.delete"))
        self._set_default_btn = QPushButton("Set Default")
        self._set_default_btn.setIcon(make_icon("state.success"))
        self._add_btn.clicked.connect(self._add_profile)
        self._copy_btn.clicked.connect(self._copy_profile)
        self._delete_btn.clicked.connect(self._delete_profile)
        self._set_default_btn.clicked.connect(self._set_default_profile)
        left_actions.addWidget(self._add_btn, 0, 0)
        left_actions.addWidget(self._copy_btn, 0, 1)
        left_actions.addWidget(self._delete_btn, 1, 0)
        left_actions.addWidget(self._set_default_btn, 1, 1)
        left_panel.addLayout(left_actions)
        content_layout.addWidget(left_card, 3)

        right_column = QVBoxLayout()
        right_column.setContentsMargins(0, 0, 0, 0)
        right_column.setSpacing(16)

        form_container = QFrame()
        form_container.setObjectName("release_profiles_card")
        form_shell = QVBoxLayout(form_container)
        form_shell.setContentsMargins(22, 22, 22, 22)
        form_shell.setSpacing(12)

        form_title = QLabel("Profile Details")
        form_title.setObjectName("workspace_section_title")
        form_shell.addWidget(form_title)

        form_hint = QLabel("Edit the selected profile fields below. Changes are applied to the in-memory release configuration immediately.")
        form_hint.setObjectName("workspace_section_subtitle")
        form_hint.setWordWrap(True)
        form_shell.addWidget(form_hint)
        form_hint.hide()

        form_layout = QFormLayout()
        form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        form_layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignTop)
        form_layout.setFormAlignment(Qt.AlignTop)
        form_layout.setHorizontalSpacing(16)
        form_layout.setVerticalSpacing(12)

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
        form_shell.addLayout(form_layout)
        right_column.addWidget(form_container, 3)

        summary_card = QFrame()
        summary_card.setObjectName("release_profiles_card")
        summary_layout = QVBoxLayout(summary_card)
        summary_layout.setContentsMargins(22, 22, 22, 22)
        summary_layout.setSpacing(10)

        summary_title = QLabel("Profile Summary")
        summary_title.setObjectName("workspace_section_title")
        summary_layout.addWidget(summary_title)

        summary_hint = QLabel("Keep track of the default profile and the current selection before saving the release configuration.")
        summary_hint.setObjectName("workspace_section_subtitle")
        summary_hint.setWordWrap(True)
        summary_layout.addWidget(summary_hint)
        summary_hint.hide()

        self._default_label = QLabel()
        self._default_label.setObjectName("release_profiles_summary_value")
        self._default_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        summary_layout.addWidget(self._default_label)
        right_column.addWidget(summary_card, 1)
        content_layout.addLayout(right_column, 5)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self._ok_button = button_box.button(QDialogButtonBox.Ok)
        self._cancel_button = button_box.button(QDialogButtonBox.Cancel)
        button_box.accepted.connect(self._accept_with_validation)
        button_box.rejected.connect(self.reject)
        root_layout.addWidget(button_box)

        self._rebuild_profile_list()
        if self._profile_list.count():
            self._profile_list.setCurrentRow(0)
        self._update_accessibility_summary()

    def _create_metric_card(self, layout: QVBoxLayout, label_text: str) -> QLabel:
        card = QFrame()
        card.setObjectName("release_profiles_metric_card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(4)

        label = QLabel(label_text)
        label.setObjectName("release_profiles_metric_label")
        card_layout.addWidget(label)

        value = QLabel("")
        value.setObjectName("release_profiles_metric_value")
        value.setWordWrap(True)
        card_layout.addWidget(value)

        value._release_profiles_metric_name = label_text
        value._release_profiles_metric_label = label
        value._release_profiles_metric_card = card
        _set_widget_metadata(
            label,
            tooltip=f"{label_text} metric label.",
            accessible_name=f"{label_text} metric label.",
        )
        layout.addWidget(card)
        return value

    def _update_metric_card_metadata(self, metric_value: QLabel) -> None:
        metric_name = getattr(metric_value, "_release_profiles_metric_name", "Release")
        metric_text = (metric_value.text() or "none").strip() or "none"
        summary = f"{metric_name}: {metric_text}."

        _set_widget_metadata(
            metric_value,
            tooltip=summary,
            accessible_name=f"Release profiles metric: {metric_name}. {metric_text}.",
        )

        label = getattr(metric_value, "_release_profiles_metric_label", None)
        if label is not None:
            _set_widget_metadata(
                label,
                tooltip=summary,
                accessible_name=f"{metric_name} metric label.",
            )

        card = getattr(metric_value, "_release_profiles_metric_card", None)
        if card is not None:
            _set_widget_metadata(
                card,
                tooltip=summary,
                accessible_name=f"{metric_name} metric: {metric_text}.",
            )

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
            item_tooltip = (
                f"Release profile {profile.id}: {profile.name or profile.id}. "
                f"Port {profile.port or 'pc'}. Target {profile.make_target or 'all'}. "
                f"Package {profile.package_format or 'dir+zip'}."
            )
            if profile.id == self._release_config.default_profile:
                item_tooltip += " Default profile."
            item.setToolTip(item_tooltip)
            item.setStatusTip(item_tooltip)
            item.setData(Qt.AccessibleTextRole, item_tooltip)
            self._profile_list.addItem(item)
        self._profile_list.blockSignals(False)

        if current_id:
            for row in range(self._profile_list.count()):
                item = self._profile_list.item(row)
                if item.data(Qt.UserRole) == current_id:
                    self._profile_list.setCurrentRow(row)
                    break
        self._default_label.setText(f"Default Profile: {self._release_config.default_profile}")
        self._update_accessibility_summary()

    def _load_profile_into_form(self, row: int) -> None:
        if row < 0 or row >= len(self._release_config.profiles):
            self._update_accessibility_summary()
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
        self._update_accessibility_summary()

    def _sync_current_profile(self) -> None:
        profile = self._current_profile()
        if profile is None:
            self._update_accessibility_summary()
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

    def _current_profile_label(self) -> str:
        profile = self._current_profile()
        if profile is None:
            return "none"
        name = profile.name or profile.id or "unnamed"
        label = f"{name} [{profile.id or 'missing id'}]"
        if profile.id == self._release_config.default_profile:
            label += " default"
        return label

    def _update_accessibility_summary(self) -> None:
        current_profile_label = self._current_profile_label()
        current_profile = self._current_profile()
        self._profile_count_metric_value.setText(_count_label(len(self._release_config.profiles), "profile"))
        self._default_metric_value.setText(self._release_config.default_profile or "none")
        self._selection_metric_value.setText(current_profile_label)
        can_copy_profile = current_profile is not None
        can_delete_profile = current_profile is not None and len(self._release_config.profiles) > 1
        can_set_default_profile = (
            current_profile is not None and current_profile.id != self._release_config.default_profile
        )
        current_profile_context = f"Current profile: {current_profile_label}."
        summary = (
            f"Release profiles: {_count_label(len(self._release_config.profiles), 'profile')}. "
            f"Default profile: {self._release_config.default_profile}. "
            f"Current profile: {current_profile_label}."
        )
        _set_widget_metadata(self, tooltip=summary, accessible_name=summary)
        _set_widget_metadata(
            self._header_frame,
            tooltip=f"Release profiles header. {summary}",
            accessible_name=f"Release profiles header. {summary}",
        )
        _set_widget_metadata(
            self._profile_list,
            tooltip=f"Release profile list: {_count_label(self._profile_list.count(), 'entry', 'entries')}. Current profile: {current_profile_label}.",
            accessible_name=f"Release profile list: {_count_label(self._profile_list.count(), 'entry', 'entries')}. Current profile: {current_profile_label}.",
        )
        _set_widget_metadata(self._default_label, tooltip=self._default_label.text(), accessible_name=self._default_label.text())
        _set_widget_metadata(self._add_btn, tooltip=f"Add a new release profile. {summary}", accessible_name="Add release profile")
        _set_widget_metadata(
            self._copy_btn,
            tooltip=(
                f"Copy the current release profile. {current_profile_context}"
                if can_copy_profile
                else f"Select a release profile to copy it. {current_profile_context}"
            ),
            accessible_name="Copy release profile" if can_copy_profile else "Copy release profile unavailable",
        )
        _set_widget_metadata(
            self._delete_btn,
            tooltip=(
                f"At least one release profile is required. {current_profile_context}"
                if not can_delete_profile
                else f"Delete the current release profile. {current_profile_context}"
            ),
            accessible_name="Delete release profile" if can_delete_profile else "Delete release profile unavailable",
        )
        _set_widget_metadata(
            self._set_default_btn,
            tooltip=(
                f"The current profile is already the default release profile. {current_profile_context}"
                if not can_set_default_profile
                else f"Set the current profile as the default release profile. {current_profile_context}"
            ),
            accessible_name=(
                "Set default release profile"
                if can_set_default_profile
                else "Set default release profile unavailable"
            ),
        )
        _set_widget_metadata(
            self._id_edit,
            tooltip=f"Release profile ID: {self._id_edit.text() or 'empty'}. {current_profile_context}",
            accessible_name=f"Release profile ID: {self._id_edit.text() or 'empty'}",
        )
        _set_widget_metadata(
            self._name_edit,
            tooltip=f"Release profile name: {self._name_edit.text() or 'empty'}. {current_profile_context}",
            accessible_name=f"Release profile name: {self._name_edit.text() or 'empty'}",
        )
        _set_widget_metadata(
            self._port_edit,
            tooltip=f"Release port: {self._port_edit.text() or 'pc'}. {current_profile_context}",
            accessible_name=f"Release port: {self._port_edit.text() or 'pc'}",
        )
        _set_widget_metadata(
            self._make_target_edit,
            tooltip=f"Release make target: {self._make_target_edit.text() or 'all'}. {current_profile_context}",
            accessible_name=f"Release make target: {self._make_target_edit.text() or 'all'}",
        )
        _set_widget_metadata(
            self._package_format_combo,
            tooltip=f"Release package format: {self._package_format_combo.currentText() or 'Directory + Zip'}. {current_profile_context}",
            accessible_name=f"Release package format: {self._package_format_combo.currentText() or 'Directory + Zip'}",
        )
        _set_widget_metadata(
            self._extra_args_edit,
            tooltip=f"Extra make arguments: {self._extra_args_edit.text() or 'none'}. {current_profile_context}",
            accessible_name=f"Extra make arguments: {self._extra_args_edit.text() or 'none'}",
        )
        _set_widget_metadata(
            self._copy_resource_check,
            tooltip=(
                f"Copy the resource directory into the release dist output. {current_profile_context}"
                if self._copy_resource_check.isChecked()
                else f"Do not copy the resource directory into the release dist output. {current_profile_context}"
            ),
            accessible_name=f"Copy resource directory into dist: {'on' if self._copy_resource_check.isChecked() else 'off'}",
        )
        if self._ok_button is not None:
            _set_widget_metadata(
                self._ok_button,
                tooltip=f"Save the release profile changes. {summary}",
                accessible_name=self._ok_button.text() or "OK",
            )
        if self._cancel_button is not None:
            _set_widget_metadata(
                self._cancel_button,
                tooltip=f"Discard the release profile changes. {summary}",
                accessible_name="Cancel release profile changes",
            )
        self._update_metric_card_metadata(self._profile_count_metric_value)
        self._update_metric_card_metadata(self._default_metric_value)
        self._update_metric_card_metadata(self._selection_metric_value)

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
        self.setMinimumSize(1120, 760)
        self.resize(1220, 820)
        self._config = get_config()
        self._open_path_callback = open_path_callback
        self._history_path = os.path.abspath(os.path.normpath(history_path)) if history_path else ""
        self._refresh_history_callback = refresh_history_callback
        self._project_key = str(project_key or "").strip()
        self._preview_mode = "auto"
        self._all_history_entries: list[dict[str, object]] = []
        self._filtered_history_entries: list[dict[str, object]] = []

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(24, 24, 24, 24)
        root_layout.setSpacing(16)

        self._header_frame = QFrame()
        self._header_frame.setObjectName("release_history_header")
        header_layout = QHBoxLayout(self._header_frame)
        header_layout.setContentsMargins(24, 22, 24, 22)
        header_layout.setSpacing(24)

        hero_copy = QVBoxLayout()
        hero_copy.setContentsMargins(0, 0, 0, 0)
        hero_copy.setSpacing(6)

        self._eyebrow_label = QLabel("Release Intelligence")
        self._eyebrow_label.setObjectName("release_history_eyebrow")
        _set_widget_metadata(
            self._eyebrow_label,
            tooltip="Release history workspace.",
            accessible_name="Release history workspace.",
        )
        hero_copy.addWidget(self._eyebrow_label, 0, Qt.AlignLeft)

        self._title_label = QLabel("Inspect Release History")
        self._title_label.setObjectName("release_history_title")
        _set_widget_metadata(
            self._title_label,
            tooltip="Release history title: Inspect Release History.",
            accessible_name="Release history title: Inspect Release History.",
        )
        hero_copy.addWidget(self._title_label)

        self._subtitle_label = QLabel(
            "Audit recent release runs, isolate failures with structured filters, and open the exact manifest, log, or packaged output behind each build."
        )
        self._subtitle_label.setObjectName("release_history_subtitle")
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

        metrics_layout = QVBoxLayout()
        metrics_layout.setContentsMargins(0, 0, 0, 0)
        metrics_layout.setSpacing(8)
        self._result_metric_value = self._create_metric_card(metrics_layout, "Visible")
        self._selection_metric_value = self._create_metric_card(metrics_layout, "Selection")
        self._preview_metric_value = self._create_metric_card(metrics_layout, "Preview")
        header_layout.addLayout(metrics_layout, 2)
        root_layout.addWidget(self._header_frame)

        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(16)
        root_layout.addLayout(controls_layout)

        filters_card = QFrame()
        filters_card.setObjectName("release_history_card")
        filters_layout = QVBoxLayout(filters_card)
        filters_layout.setContentsMargins(22, 22, 22, 22)
        filters_layout.setSpacing(12)

        filters_title = QLabel("Filter Stack")
        filters_title.setObjectName("workspace_section_title")
        filters_layout.addWidget(filters_title)

        filters_hint = QLabel(
            "Use time range, release state, artifact presence, diagnostics, and text search together to narrow the list before drilling into a single run."
        )
        filters_hint.setObjectName("workspace_section_subtitle")
        filters_hint.setWordWrap(True)
        filters_layout.addWidget(filters_hint)
        filters_hint.hide()

        filters_grid = QGridLayout()
        filters_grid.setHorizontalSpacing(12)
        filters_grid.setVerticalSpacing(8)

        range_label = QLabel("Range")
        range_label.setObjectName("release_history_field_label")
        filters_grid.addWidget(range_label, 0, 0)
        self._range_filter_combo = QComboBox()
        self._range_filter_combo.addItem("Any", "")
        self._range_filter_combo.addItem("Last 24h", "24h")
        self._range_filter_combo.addItem("Last 7d", "7d")
        self._range_filter_combo.addItem("Last 30d", "30d")
        self._range_filter_combo.currentIndexChanged.connect(self._apply_history_filter)
        filters_grid.addWidget(self._range_filter_combo, 1, 0)

        status_label = QLabel("Status")
        status_label.setObjectName("release_history_field_label")
        filters_grid.addWidget(status_label, 0, 1)
        self._status_filter_combo = QComboBox()
        self._status_filter_combo.addItem("All", "")
        self._status_filter_combo.addItem("Success", "success")
        self._status_filter_combo.addItem("Failed", "failed")
        self._status_filter_combo.addItem("Unknown", "unknown")
        self._status_filter_combo.currentIndexChanged.connect(self._apply_history_filter)
        filters_grid.addWidget(self._status_filter_combo, 1, 1)

        profile_label = QLabel("Profile")
        profile_label.setObjectName("release_history_field_label")
        filters_grid.addWidget(profile_label, 0, 2)
        self._profile_filter_combo = QComboBox()
        self._profile_filter_combo.currentIndexChanged.connect(self._apply_history_filter)
        filters_grid.addWidget(self._profile_filter_combo, 1, 2)

        artifact_label = QLabel("Artifact")
        artifact_label.setObjectName("release_history_field_label")
        filters_grid.addWidget(artifact_label, 0, 3)
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
        filters_grid.addWidget(self._artifact_filter_combo, 1, 3)

        diagnostics_label = QLabel("Diagnostics")
        diagnostics_label.setObjectName("release_history_field_label")
        filters_grid.addWidget(diagnostics_label, 2, 0)
        self._diagnostics_filter_combo = QComboBox()
        self._diagnostics_filter_combo.addItem("Any", "")
        self._diagnostics_filter_combo.addItem("Clean", "clean")
        self._diagnostics_filter_combo.addItem("Warnings", "warnings")
        self._diagnostics_filter_combo.addItem("Errors", "errors")
        self._diagnostics_filter_combo.addItem("Issues", "issues")
        self._diagnostics_filter_combo.addItem("Unknown", "unknown")
        self._diagnostics_filter_combo.currentIndexChanged.connect(self._apply_history_filter)
        filters_grid.addWidget(self._diagnostics_filter_combo, 3, 0)

        sort_label = QLabel("Sort")
        sort_label.setObjectName("release_history_field_label")
        filters_grid.addWidget(sort_label, 2, 1)
        self._sort_combo = QComboBox()
        self._sort_combo.addItem("Newest First", "newest")
        self._sort_combo.addItem("Oldest First", "oldest")
        self._sort_combo.addItem("Status", "status")
        self._sort_combo.addItem("Diagnostics", "diagnostics")
        self._sort_combo.addItem("Profile", "profile")
        self._sort_combo.currentIndexChanged.connect(self._apply_history_filter)
        filters_grid.addWidget(self._sort_combo, 3, 1)

        search_label = QLabel("Search")
        search_label.setObjectName("release_history_field_label")
        filters_grid.addWidget(search_label, 2, 2, 1, 2)
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("build id, message, SDK revision...")
        self._search_edit.textChanged.connect(self._apply_history_filter)
        filters_grid.addWidget(self._search_edit, 3, 2, 1, 2)
        filters_grid.setColumnStretch(0, 1)
        filters_grid.setColumnStretch(1, 1)
        filters_grid.setColumnStretch(2, 1)
        filters_grid.setColumnStretch(3, 1)
        filters_layout.addLayout(filters_grid)
        controls_layout.addWidget(filters_card, 5)

        overview_card = QFrame()
        overview_card.setObjectName("release_history_card")
        overview_layout = QVBoxLayout(overview_card)
        overview_layout.setContentsMargins(22, 22, 22, 22)
        overview_layout.setSpacing(12)

        overview_title = QLabel("History State")
        overview_title.setObjectName("workspace_section_title")
        overview_layout.addWidget(overview_title)

        overview_hint = QLabel(
            "Track filtered volume, artifact coverage, and history file availability before copying or exporting a batch."
        )
        overview_hint.setObjectName("workspace_section_subtitle")
        overview_hint.setWordWrap(True)
        overview_layout.addWidget(overview_hint)
        overview_hint.hide()

        stats_grid = QGridLayout()
        stats_grid.setHorizontalSpacing(12)
        stats_grid.setVerticalSpacing(8)
        self._result_count_label = QLabel("0 / 0")
        self._result_count_label.setObjectName("release_history_stat_value")
        stats_grid.addWidget(QLabel("Results"), 0, 0)
        stats_grid.itemAtPosition(0, 0).widget().setObjectName("release_history_field_label")
        stats_grid.addWidget(self._result_count_label, 0, 1)

        self._status_breakdown_label = QLabel("success 0 | failed 0 | unknown 0")
        self._status_breakdown_label.setObjectName("release_history_stat_value")
        self._status_breakdown_label.setWordWrap(True)
        stats_grid.addWidget(QLabel("Status"), 1, 0)
        stats_grid.itemAtPosition(1, 0).widget().setObjectName("release_history_field_label")
        stats_grid.addWidget(self._status_breakdown_label, 1, 1)

        self._artifact_breakdown_label = QLabel("manifest 0 | log 0 | package 0 | version 0")
        self._artifact_breakdown_label.setObjectName("release_history_stat_value")
        self._artifact_breakdown_label.setWordWrap(True)
        stats_grid.addWidget(QLabel("Artifacts"), 2, 0)
        stats_grid.itemAtPosition(2, 0).widget().setObjectName("release_history_field_label")
        stats_grid.addWidget(self._artifact_breakdown_label, 2, 1)

        self._diagnostics_breakdown_label = QLabel("clean 0 | warnings 0 | errors 0 | unknown 0")
        self._diagnostics_breakdown_label.setObjectName("release_history_stat_value")
        self._diagnostics_breakdown_label.setWordWrap(True)
        stats_grid.addWidget(QLabel("Diagnostics"), 3, 0)
        stats_grid.itemAtPosition(3, 0).widget().setObjectName("release_history_field_label")
        stats_grid.addWidget(self._diagnostics_breakdown_label, 3, 1)

        self._history_file_value_label = QLabel("")
        self._history_file_value_label.setObjectName("release_history_file_path")
        self._history_file_value_label.setWordWrap(True)
        stats_grid.addWidget(QLabel("History File"), 4, 0)
        stats_grid.itemAtPosition(4, 0).widget().setObjectName("release_history_field_label")
        stats_grid.addWidget(self._history_file_value_label, 4, 1)
        stats_grid.setColumnStretch(1, 1)
        overview_layout.addLayout(stats_grid)

        actions_grid = QGridLayout()
        actions_grid.setHorizontalSpacing(10)
        actions_grid.setVerticalSpacing(10)

        self._clear_filters_button = QPushButton("Clear Filters")
        self._clear_filters_button.setIcon(make_icon("toolbar.delete"))
        self._clear_filters_button.clicked.connect(self._clear_filters)
        actions_grid.addWidget(self._clear_filters_button, 0, 0)

        self._reset_view_button = QPushButton("Reset View")
        self._reset_view_button.setIcon(make_icon("toolbar.undo"))
        self._reset_view_button.clicked.connect(self._reset_view)
        actions_grid.addWidget(self._reset_view_button, 0, 1)

        self._copy_filtered_button = QPushButton("Copy Filtered")
        self._copy_filtered_button.setIcon(make_icon("toolbar.copy"))
        self._copy_filtered_button.clicked.connect(self._copy_filtered_summary)
        actions_grid.addWidget(self._copy_filtered_button, 1, 0)

        self._copy_filtered_json_button = QPushButton("Copy Filtered JSON")
        self._copy_filtered_json_button.setIcon(make_icon("toolbar.copy"))
        self._copy_filtered_json_button.clicked.connect(self._copy_filtered_json)
        actions_grid.addWidget(self._copy_filtered_json_button, 1, 1)

        self._export_filtered_button = QPushButton("Export Filtered...")
        self._export_filtered_button.setIcon(make_icon("toolbar.export"))
        self._export_filtered_button.clicked.connect(self._export_filtered_summary)
        actions_grid.addWidget(self._export_filtered_button, 2, 0)

        self._copy_history_file_button = QPushButton("Copy History Path")
        self._copy_history_file_button.setIcon(make_icon("toolbar.copy"))
        self._copy_history_file_button.clicked.connect(self._copy_history_file_path)
        actions_grid.addWidget(self._copy_history_file_button, 3, 0)

        self._copy_history_json_button = QPushButton("Copy History JSON")
        self._copy_history_json_button.setIcon(make_icon("toolbar.copy"))
        self._copy_history_json_button.clicked.connect(self._copy_history_file_json)
        actions_grid.addWidget(self._copy_history_json_button, 3, 1)

        self._export_history_json_button = QPushButton("Export History JSON...")
        self._export_history_json_button.setIcon(make_icon("toolbar.export"))
        self._export_history_json_button.clicked.connect(self._export_history_file_json)
        actions_grid.addWidget(self._export_history_json_button, 4, 0)

        self._open_history_file_button = QPushButton("Open History File")
        self._open_history_file_button.setIcon(make_icon("toolbar.open"))
        self._open_history_file_button.clicked.connect(self._open_history_file)
        actions_grid.addWidget(self._open_history_file_button, 4, 1)

        self._refresh_button = QPushButton("Refresh")
        self._refresh_button.setIcon(make_icon("state.info"))
        self._refresh_button.setEnabled(self._refresh_history_callback is not None)
        self._refresh_button.clicked.connect(self._reload_history_entries)
        actions_grid.addWidget(self._refresh_button, 2, 1)
        actions_grid.setColumnStretch(0, 1)
        actions_grid.setColumnStretch(1, 1)
        overview_layout.addLayout(actions_grid)
        controls_layout.addWidget(overview_card, 4)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(16)
        root_layout.addLayout(content_layout, 1)

        history_card = QFrame()
        history_card.setObjectName("release_history_card")
        history_layout = QVBoxLayout(history_card)
        history_layout.setContentsMargins(22, 22, 22, 22)
        history_layout.setSpacing(12)

        history_title = QLabel("Release Runs")
        history_title.setObjectName("workspace_section_title")
        history_layout.addWidget(history_title)

        history_hint = QLabel(
            "Entries stay sorted by the active rule, with each row surfacing profile, SDK revision, and the first diagnostic signal."
        )
        history_hint.setObjectName("workspace_section_subtitle")
        history_hint.setWordWrap(True)
        history_layout.addWidget(history_hint)
        history_hint.hide()

        self._history_list = QListWidget()
        self._history_list.setObjectName("release_history_list")
        self._history_list.setSpacing(8)
        self._history_list.currentRowChanged.connect(self._update_current_entry)
        history_layout.addWidget(self._history_list, 1)
        content_layout.addWidget(history_card, 3)

        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(16)
        content_layout.addLayout(right_layout, 5)

        details_card = QFrame()
        details_card.setObjectName("release_history_card")
        details_layout = QVBoxLayout(details_card)
        details_layout.setContentsMargins(22, 22, 22, 22)
        details_layout.setSpacing(12)

        details_title = QLabel("Selection Details")
        details_title.setObjectName("workspace_section_title")
        details_layout.addWidget(details_title)

        details_hint = QLabel(
            "The selected release row expands into a structured summary and raw metadata so build context remains visible while exporting."
        )
        details_hint.setObjectName("workspace_section_subtitle")
        details_hint.setWordWrap(True)
        details_layout.addWidget(details_hint)
        details_hint.hide()

        self._summary_label = QLabel("Select a release entry to inspect its metadata.")
        self._summary_label.setObjectName("release_history_summary")
        self._summary_label.setWordWrap(True)
        details_layout.addWidget(self._summary_label)
        self._summary_label.hide()

        self._details_edit = QTextEdit()
        self._details_edit.setObjectName("release_history_details")
        self._details_edit.setReadOnly(True)
        details_layout.addWidget(self._details_edit, 1)

        details_actions = QGridLayout()
        details_actions.setHorizontalSpacing(10)
        details_actions.setVerticalSpacing(10)

        self._preview_auto_button = QPushButton("Auto Preview")
        self._preview_auto_button.setIcon(make_icon("toolbar.preview"))
        self._preview_manifest_button = QPushButton("Preview Manifest")
        self._preview_manifest_button.setIcon(make_icon("nav.page"))
        self._preview_log_button = QPushButton("Preview Log")
        self._preview_log_button.setIcon(make_icon("state.info"))
        self._preview_version_button = QPushButton("Preview Version")
        self._preview_version_button.setIcon(make_icon("state.progress"))
        self._copy_summary_button = QPushButton("Copy Summary")
        self._copy_summary_button.setIcon(make_icon("toolbar.copy"))
        self._export_summary_button = QPushButton("Export Summary...")
        self._export_summary_button.setIcon(make_icon("toolbar.export"))
        self._copy_details_button = QPushButton("Copy Details")
        self._copy_details_button.setIcon(make_icon("toolbar.copy"))
        self._copy_preview_button = QPushButton("Copy Preview")
        self._copy_preview_button.setIcon(make_icon("toolbar.copy"))
        self._copy_preview_path_button = QPushButton("Copy Preview Path")
        self._copy_preview_path_button.setIcon(make_icon("toolbar.copy"))
        self._export_preview_button = QPushButton("Export Preview...")
        self._export_preview_button.setIcon(make_icon("toolbar.export"))
        self._open_preview_button = QPushButton("Open Preview")
        self._open_preview_button.setIcon(make_icon("toolbar.open"))
        self._copy_folder_path_button = QPushButton("Copy Folder Path")
        self._copy_folder_path_button.setIcon(make_icon("toolbar.copy"))
        self._copy_dist_path_button = QPushButton("Copy Dist Path")
        self._copy_dist_path_button.setIcon(make_icon("toolbar.copy"))
        self._copy_package_path_button = QPushButton("Copy Package Path")
        self._copy_package_path_button.setIcon(make_icon("toolbar.copy"))
        self._export_details_button = QPushButton("Export Details...")
        self._export_details_button.setIcon(make_icon("toolbar.export"))
        self._copy_entry_json_button = QPushButton("Copy Entry JSON")
        self._copy_entry_json_button.setIcon(make_icon("toolbar.copy"))
        self._export_entry_json_button = QPushButton("Export Entry JSON...")
        self._export_entry_json_button.setIcon(make_icon("toolbar.export"))
        self._open_folder_button = QPushButton("Open Folder")
        self._open_folder_button.setIcon(make_icon("toolbar.open"))
        self._open_dist_button = QPushButton("Open Dist")
        self._open_dist_button.setIcon(make_icon("toolbar.open"))
        self._open_version_button = QPushButton("Open Version")
        self._open_version_button.setIcon(make_icon("toolbar.open"))
        self._open_manifest_button = QPushButton("Open Manifest")
        self._open_manifest_button.setIcon(make_icon("toolbar.open"))
        self._open_log_button = QPushButton("Open Log")
        self._open_log_button.setIcon(make_icon("toolbar.open"))
        self._open_package_button = QPushButton("Open Package")
        self._open_package_button.setIcon(make_icon("toolbar.open"))
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
        self._export_summary_button.clicked.connect(self._export_entry_summary)
        self._copy_details_button.clicked.connect(lambda: self._copy_text(self._details_edit.toPlainText()))
        self._copy_preview_button.clicked.connect(self._copy_preview_text)
        self._copy_preview_path_button.clicked.connect(self._copy_preview_path)
        self._export_preview_button.clicked.connect(self._export_preview)
        self._open_preview_button.clicked.connect(self._open_preview)
        self._copy_folder_path_button.clicked.connect(lambda: self._copy_selected_path("release_root"))
        self._copy_dist_path_button.clicked.connect(lambda: self._copy_selected_path("dist_dir"))
        self._copy_package_path_button.clicked.connect(self._copy_package_path)
        self._export_details_button.clicked.connect(self._export_entry_details)
        self._copy_entry_json_button.clicked.connect(self._copy_entry_json)
        self._export_entry_json_button.clicked.connect(self._export_entry_json)
        self._open_folder_button.clicked.connect(lambda: self._open_selected_path("release_root", "Release Folder"))
        self._open_dist_button.clicked.connect(lambda: self._open_selected_path("dist_dir", "Release Dist"))
        self._open_version_button.clicked.connect(self._open_selected_version)
        self._open_manifest_button.clicked.connect(lambda: self._open_selected_path("manifest_path", "Release Manifest"))
        self._open_log_button.clicked.connect(lambda: self._open_selected_path("log_path", "Release Log"))
        self._open_package_button.clicked.connect(lambda: self._open_selected_path("zip_path", "Release Package"))

        details_actions.addWidget(self._copy_summary_button, 0, 0)
        details_actions.addWidget(self._export_summary_button, 0, 1)
        details_actions.addWidget(self._copy_details_button, 0, 2)
        details_actions.addWidget(self._export_details_button, 1, 0)
        details_actions.addWidget(self._copy_entry_json_button, 1, 1)
        details_actions.addWidget(self._export_entry_json_button, 1, 2)
        details_actions.setColumnStretch(0, 1)
        details_actions.setColumnStretch(1, 1)
        details_actions.setColumnStretch(2, 1)
        details_layout.addLayout(details_actions)
        right_layout.addWidget(details_card, 3)

        preview_card = QFrame()
        preview_card.setObjectName("release_history_card")
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(22, 22, 22, 22)
        preview_layout.setSpacing(12)

        preview_title = QLabel("Artifacts & Preview")
        preview_title.setObjectName("workspace_section_title")
        preview_layout.addWidget(preview_title)

        preview_hint = QLabel(
            "Switch preview modes without losing selection, then copy paths or open the exact release folder, dist directory, or artifact file."
        )
        preview_hint.setObjectName("workspace_section_subtitle")
        preview_hint.setWordWrap(True)
        preview_layout.addWidget(preview_hint)
        preview_hint.hide()

        self._preview_label = QLabel("Preview")
        self._preview_label.setObjectName("release_history_preview_label")
        preview_layout.addWidget(self._preview_label)

        self._preview_edit = QTextEdit()
        self._preview_edit.setObjectName("release_history_preview")
        self._preview_edit.setReadOnly(True)
        preview_layout.addWidget(self._preview_edit, 1)

        preview_mode_row = QHBoxLayout()
        preview_mode_row.setContentsMargins(0, 0, 0, 0)
        preview_mode_row.setSpacing(10)
        preview_mode_row.addWidget(self._preview_auto_button)
        preview_mode_row.addWidget(self._preview_manifest_button)
        preview_mode_row.addWidget(self._preview_log_button)
        preview_mode_row.addWidget(self._preview_version_button)
        preview_mode_row.addStretch(1)
        preview_layout.addLayout(preview_mode_row)

        preview_actions = QGridLayout()
        preview_actions.setHorizontalSpacing(10)
        preview_actions.setVerticalSpacing(10)
        preview_actions.addWidget(self._copy_preview_button, 0, 0)
        preview_actions.addWidget(self._copy_preview_path_button, 0, 1)
        preview_actions.addWidget(self._export_preview_button, 0, 2)
        preview_actions.addWidget(self._open_preview_button, 0, 3)
        preview_actions.addWidget(self._copy_folder_path_button, 1, 0)
        preview_actions.addWidget(self._copy_dist_path_button, 1, 1)
        preview_actions.addWidget(self._copy_package_path_button, 1, 2)
        preview_actions.addWidget(self._open_folder_button, 1, 3)
        preview_actions.addWidget(self._open_dist_button, 2, 0)
        preview_actions.addWidget(self._open_version_button, 2, 1)
        preview_actions.addWidget(self._open_manifest_button, 2, 2)
        preview_actions.addWidget(self._open_log_button, 2, 3)
        preview_actions.addWidget(self._open_package_button, 3, 0)
        preview_actions.setColumnStretch(0, 1)
        preview_actions.setColumnStretch(1, 1)
        preview_actions.setColumnStretch(2, 1)
        preview_actions.setColumnStretch(3, 1)
        preview_layout.addLayout(preview_actions)
        right_layout.addWidget(preview_card, 4)

        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(self.reject)
        button_box.accepted.connect(self.accept)
        root_layout.addWidget(button_box)
        close_button = button_box.button(QDialogButtonBox.Close)
        self._close_button = close_button

        self._range_filter_combo.setAccessibleName("Release history range filter")
        self._status_filter_combo.setAccessibleName("Release history status filter")
        self._profile_filter_combo.setAccessibleName("Release history profile filter")
        self._artifact_filter_combo.setAccessibleName("Release history artifact filter")
        self._diagnostics_filter_combo.setAccessibleName("Release history diagnostics filter")
        self._sort_combo.setAccessibleName("Release history sort order")
        self._search_edit.setAccessibleName("Release history search")
        self._history_list.setAccessibleName("Release history list")
        self._summary_label.setAccessibleName("Release entry summary")
        self._details_edit.setAccessibleName("Release entry details")
        self._preview_label.setAccessibleName("Release preview label")
        self._preview_edit.setAccessibleName("Release preview")
        for button, accessible_name in (
            (self._clear_filters_button, "Clear release history filters"),
            (self._reset_view_button, "Reset release history view"),
            (self._copy_filtered_button, "Copy filtered release history summary"),
            (self._copy_filtered_json_button, "Copy filtered release history JSON"),
            (self._export_filtered_button, "Export filtered release history"),
            (self._copy_history_file_button, "Copy release history file path"),
            (self._copy_history_json_button, "Copy release history JSON"),
            (self._export_history_json_button, "Export release history JSON"),
            (self._open_history_file_button, "Open release history file"),
            (self._refresh_button, "Refresh release history"),
            (self._preview_auto_button, "Auto preview"),
            (self._preview_manifest_button, "Preview manifest"),
            (self._preview_log_button, "Preview build log"),
            (self._preview_version_button, "Preview version file"),
            (self._copy_summary_button, "Copy selected release summary"),
            (self._export_summary_button, "Export selected release summary"),
            (self._copy_details_button, "Copy selected release details"),
            (self._copy_preview_button, "Copy current preview text"),
            (self._copy_preview_path_button, "Copy current preview path"),
            (self._export_preview_button, "Export current preview"),
            (self._open_preview_button, "Open current preview file"),
            (self._copy_folder_path_button, "Copy selected release folder path"),
            (self._copy_dist_path_button, "Copy selected dist path"),
            (self._copy_package_path_button, "Copy selected package path"),
            (self._export_details_button, "Export selected release details"),
            (self._copy_entry_json_button, "Copy selected release entry JSON"),
            (self._export_entry_json_button, "Export selected release entry JSON"),
            (self._open_folder_button, "Open selected release folder"),
            (self._open_dist_button, "Open selected dist folder"),
            (self._open_version_button, "Open selected version file"),
            (self._open_manifest_button, "Open selected manifest"),
            (self._open_log_button, "Open selected build log"),
            (self._open_package_button, "Open selected package"),
        ):
            button.setAccessibleName(accessible_name)
        if close_button is not None:
            _set_widget_metadata(
                close_button,
                tooltip="Close the release history dialog.",
                accessible_name="Close release history dialog",
            )

        self._load_history_entries(history_entries)
        self._restore_view_state()
        self._update_history_file_button()
        self._sync_preview_mode_buttons()

    def _create_metric_card(self, layout: QVBoxLayout, label_text: str) -> QLabel:
        card = QFrame()
        card.setObjectName("release_history_metric_card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(4)

        label = QLabel(label_text)
        label.setObjectName("release_history_metric_label")
        card_layout.addWidget(label)

        value = QLabel("")
        value.setObjectName("release_history_metric_value")
        value.setWordWrap(True)
        card_layout.addWidget(value)

        value._release_history_metric_name = label_text
        value._release_history_metric_label = label
        value._release_history_metric_card = card
        _set_widget_metadata(
            label,
            tooltip=f"{label_text} metric label.",
            accessible_name=f"{label_text} metric label.",
        )
        layout.addWidget(card)
        return value

    def _update_metric_card_metadata(self, metric_value: QLabel) -> None:
        metric_name = getattr(metric_value, "_release_history_metric_name", "Release")
        metric_text = (metric_value.text() or "none").strip() or "none"
        summary = f"{metric_name}: {metric_text}."

        _set_widget_metadata(
            metric_value,
            tooltip=summary,
            accessible_name=f"Release history metric: {metric_name}. {metric_text}.",
        )

        label = getattr(metric_value, "_release_history_metric_label", None)
        if label is not None:
            _set_widget_metadata(
                label,
                tooltip=summary,
                accessible_name=f"{metric_name} metric label.",
            )

        card = getattr(metric_value, "_release_history_metric_card", None)
        if card is not None:
            _set_widget_metadata(
                card,
                tooltip=summary,
                accessible_name=f"{metric_name} metric: {metric_text}.",
            )

    def _count_label(self, count: int, singular: str, plural: str | None = None) -> str:
        value = max(int(count or 0), 0)
        noun = singular if value == 1 else (plural or f"{singular}s")
        return f"{value} {noun}"

    def _current_search_label(self) -> str:
        text = self._search_edit.text().strip()
        return text if text else "none"

    def _current_selection_label(self) -> str:
        entry = self._current_entry()
        return _history_list_label(entry) if entry else "none"

    def _filters_are_active(self) -> bool:
        return any(
            (
                str(self._range_filter_combo.currentData() or ""),
                str(self._status_filter_combo.currentData() or ""),
                str(self._profile_filter_combo.currentData() or ""),
                str(self._artifact_filter_combo.currentData() or ""),
                str(self._diagnostics_filter_combo.currentData() or ""),
                "" if str(self._sort_combo.currentData() or "newest") == "newest" else str(self._sort_combo.currentData() or ""),
                self._search_edit.text().strip(),
            )
        )

    def _default_view_is_active(self) -> bool:
        current_row = self._history_list.currentRow()
        default_row = 0 if self._history_list.count() else -1
        return not self._filters_are_active() and self._preview_mode == "auto" and current_row == default_row

    def _history_file_exists(self) -> bool:
        return bool(self._history_path and os.path.isfile(self._history_path))

    def _copy_path_hint(self, label: str, path: str) -> str:
        if path:
            return f"Copy the {label} path. Current path: {path}."
        return f"No {label} path is available to copy. Current path: none."

    def _open_path_hint(self, label: str, path: str, *, directory: bool = False) -> str:
        exists = os.path.isdir(path) if directory else os.path.isfile(path)
        if path and exists:
            return f"Open the {label}. Path state: available. Current path: {path}."
        if path:
            return f"The {label} is unavailable or missing. Path state: missing. Current path: {path}."
        return f"The {label} is unavailable or missing. Path state: unavailable. Current path: none."

    def _preview_mode_hint(self, mode: str) -> str:
        entry = self._current_entry()
        if entry is None:
            return "Select a release entry to preview its artifacts. Path state: unavailable. Current path: none."
        preview_label = {
            "auto": "best available artifact",
            "manifest": "manifest",
            "log": "build log",
            "version": "version file",
        }[mode]
        preview_path = ""
        if mode == "manifest":
            preview_path = _history_string(entry, "manifest_path")
            if not preview_path:
                return "No manifest is recorded for the selected release entry. Path state: unavailable. Current path: none."
        elif mode == "log":
            preview_path = _history_string(entry, "log_path")
            if not preview_path:
                return "No build log is recorded for the selected release entry. Path state: unavailable. Current path: none."
        elif mode == "version":
            preview_path = _history_version_path(entry)
            if not preview_path:
                return "No version file is recorded for the selected release entry. Path state: unavailable. Current path: none."
        else:
            _preview_label, preview_path, _prefer_json, _suffix = self._current_preview_target_options(entry)
        preview_state = "available" if preview_path else "unavailable"
        if self._preview_mode == mode:
            if mode == "auto":
                return (
                    "Showing the best available preview for the selected release entry. "
                    f"Path state: {preview_state}. Current path: {preview_path or 'none'}."
                )
            return (
                f"Showing the selected release {preview_label} preview. "
                f"Path state: {preview_state}. Current path: {preview_path or 'none'}."
            )
        if mode == "auto":
            return (
                "Automatically preview the best available artifact for the selected release entry. "
                f"Path state: {preview_state}. Current path: {preview_path or 'none'}."
            )
        return (
            f"Preview the selected release {preview_label}. "
            f"Path state: {preview_state}. Current path: {preview_path or 'none'}."
        )

    def _preview_empty_state_text(self, message: str, *, path: str = "", state: str | None = None) -> str:
        resolved_path = str(path or "").strip()
        resolved_state = str(state or ("missing" if resolved_path else "unavailable")).strip() or "unavailable"
        return (
            f"Preview mode: {self._preview_mode}. "
            f"Path state: {resolved_state}. "
            f"Current path: {resolved_path or 'none'}. "
            f"{message}"
        )

    def _update_accessibility_summary(self) -> None:
        visible_entries = len(self._filtered_history_entries)
        total_entries = len(self._all_history_entries)
        result_summary = f"{visible_entries} of {total_entries} entries"
        visible_entries_context = f"Visible entries: {visible_entries} of {total_entries}."
        search_context = f"Current search: {self._current_search_label()}."
        refresh_context = f"History file: {self._history_path or 'none'}. {visible_entries_context}"
        filter_context = (
            f"Current filters: range {self._range_filter_combo.currentText()}, "
            f"status {self._status_filter_combo.currentText()}, "
            f"profile {self._profile_filter_combo.currentText() or 'All'}, "
            f"artifact {self._artifact_filter_combo.currentText()}, "
            f"diagnostics {self._diagnostics_filter_combo.currentText()}, "
            f"sort {self._sort_combo.currentText()}. "
            f"{search_context}"
        )
        selection_label = self._current_selection_label()
        dialog_summary = (
            f"Release history: {result_summary}. "
            f"Filters: range {self._range_filter_combo.currentText()}, status {self._status_filter_combo.currentText()}, "
            f"profile {self._profile_filter_combo.currentText() or 'All'}, artifact {self._artifact_filter_combo.currentText()}, "
            f"diagnostics {self._diagnostics_filter_combo.currentText()}, sort {self._sort_combo.currentText()}, "
            f"search {self._current_search_label()}. "
            f"Preview mode: {self._preview_mode}. Current selection: {selection_label}."
        )
        list_summary = f"Release history list: {self._count_label(visible_entries, 'visible entry', 'visible entries')}. Current selection: {selection_label}."
        summary_text = str(self._summary_label.text() or "No release entry selected.").strip() or "No release entry selected."
        details_summary = (
            f"Release entry details: {selection_label}."
            if self._current_entry() is not None
            else "Release entry details: no release entry selected."
        )
        preview_title = str(self._preview_label.text() or "Preview").strip() or "Preview"
        preview_summary = f"Release preview: {preview_title}."
        history_exists = self._history_file_exists()
        preview_label_text, preview_path = self._current_preview_target()
        preview_label_lower = preview_label_text.lower()
        selection_context = f"Current selection: {selection_label}."
        has_filters = self._filters_are_active()
        default_view_active = self._default_view_is_active()
        history_state = "available" if history_exists else ("missing" if self._history_path else "unavailable")

        self._result_metric_value.setText(f"{visible_entries} / {total_entries}")
        self._selection_metric_value.setText(selection_label)
        self._preview_metric_value.setText(f"{self._preview_mode.title()} | {preview_label_text}")
        self._history_file_value_label.setText(f"{history_state} | {self._history_path or 'No history file configured'}")

        _set_widget_metadata(self, tooltip=dialog_summary, accessible_name=dialog_summary)
        _set_widget_metadata(
            self._header_frame,
            tooltip=f"Release history header. {dialog_summary}",
            accessible_name=f"Release history header. {dialog_summary}",
        )
        self._update_metric_card_metadata(self._result_metric_value)
        self._update_metric_card_metadata(self._selection_metric_value)
        self._update_metric_card_metadata(self._preview_metric_value)
        _set_widget_metadata(
            self._history_file_value_label,
            tooltip=f"Release history file state: {history_state}. Current path: {self._history_path or 'none'}.",
            accessible_name=f"Release history file state: {history_state}",
        )
        if getattr(self, "_close_button", None) is not None:
            _set_widget_metadata(
                self._close_button,
                tooltip=(
                    f"Close the release history dialog. {visible_entries_context} "
                    f"Current selection: {selection_label}. Preview mode: {self._preview_mode}."
                ),
                accessible_name="Close release history dialog",
            )
        _set_widget_metadata(
            self._range_filter_combo,
            tooltip=f"Filter release history by age. Current filter: {self._range_filter_combo.currentText()}.",
            accessible_name=f"Release history range filter: {self._range_filter_combo.currentText()}",
        )
        _set_widget_metadata(
            self._status_filter_combo,
            tooltip=f"Filter release history by status. Current filter: {self._status_filter_combo.currentText()}.",
            accessible_name=f"Release history status filter: {self._status_filter_combo.currentText()}",
        )
        _set_widget_metadata(
            self._profile_filter_combo,
            tooltip=f"Filter release history by build profile. Current filter: {self._profile_filter_combo.currentText() or 'All'}.",
            accessible_name=f"Release history profile filter: {self._profile_filter_combo.currentText() or 'All'}",
        )
        _set_widget_metadata(
            self._artifact_filter_combo,
            tooltip=f"Filter release history by artifact availability. Current filter: {self._artifact_filter_combo.currentText()}.",
            accessible_name=f"Release history artifact filter: {self._artifact_filter_combo.currentText()}",
        )
        _set_widget_metadata(
            self._diagnostics_filter_combo,
            tooltip=f"Filter release history by diagnostics state. Current filter: {self._diagnostics_filter_combo.currentText()}.",
            accessible_name=f"Release history diagnostics filter: {self._diagnostics_filter_combo.currentText()}",
        )
        _set_widget_metadata(
            self._sort_combo,
            tooltip=f"Choose how filtered release entries are sorted. Current sort: {self._sort_combo.currentText()}.",
            accessible_name=f"Release history sort order: {self._sort_combo.currentText()}",
        )
        _set_widget_metadata(
            self._search_edit,
            tooltip=f"Filter release history by build ID, message, SDK revision, or artifact path. Current search: {self._current_search_label()}.",
            accessible_name=f"Release history search: {self._current_search_label()}",
        )
        _set_widget_metadata(
            self._result_count_label,
            tooltip=f"Release history results: {result_summary}. {filter_context}",
            accessible_name=f"Release history results: {result_summary}",
        )
        _set_widget_metadata(
            self._status_breakdown_label,
            tooltip=f"{self._status_breakdown_label.text()}. {visible_entries_context} {filter_context}",
            accessible_name=f"Status breakdown: {self._status_breakdown_label.text()}",
        )
        _set_widget_metadata(
            self._artifact_breakdown_label,
            tooltip=f"{self._artifact_breakdown_label.text()}. {visible_entries_context} {filter_context}",
            accessible_name=f"Artifact breakdown: {self._artifact_breakdown_label.text()}",
        )
        _set_widget_metadata(
            self._diagnostics_breakdown_label,
            tooltip=f"{self._diagnostics_breakdown_label.text()}. {visible_entries_context} {filter_context}",
            accessible_name=f"Diagnostics breakdown: {self._diagnostics_breakdown_label.text()}",
        )
        _set_widget_metadata(
            self._clear_filters_button,
            tooltip=(
                f"Clear the current release history filters and search text. {visible_entries_context} {search_context}"
                if has_filters
                else f"Release history filters already show every entry. {visible_entries_context} {search_context}"
            ),
            accessible_name=(
                "Clear release history filters"
                if has_filters
                else "Clear release history filters unavailable"
            ),
        )
        _set_widget_metadata(
            self._reset_view_button,
            tooltip=(
                f"Reset release history filters, preview mode, and selection. {visible_entries_context} {search_context} Preview mode: {self._preview_mode}. Current selection: {selection_label}."
                if not default_view_active
                else f"Release history already shows the default view. {visible_entries_context} {search_context} Preview mode: {self._preview_mode}. Current selection: {selection_label}."
            ),
            accessible_name=(
                "Reset release history view"
                if not default_view_active
                else "Reset release history view unavailable"
            ),
        )
        _set_widget_metadata(
            self._copy_filtered_button,
            tooltip=(
                f"Copy the filtered release history summary. {visible_entries_context}"
                if self._filtered_history_entries
                else f"No filtered release entries are available to copy. {visible_entries_context}"
            ),
            accessible_name=(
                "Copy filtered release history summary"
                if self._filtered_history_entries
                else "Copy filtered release history summary unavailable"
            ),
        )
        _set_widget_metadata(
            self._copy_filtered_json_button,
            tooltip=(
                f"Copy the filtered release history as JSON. {visible_entries_context}"
                if self._filtered_history_entries
                else f"No filtered release entries are available to copy as JSON. {visible_entries_context}"
            ),
            accessible_name=(
                "Copy filtered release history JSON"
                if self._filtered_history_entries
                else "Copy filtered release history JSON unavailable"
            ),
        )
        _set_widget_metadata(
            self._export_filtered_button,
            tooltip=(
                f"Export the filtered release history. {visible_entries_context}"
                if self._filtered_history_entries
                else f"No filtered release entries are available to export. {visible_entries_context}"
            ),
            accessible_name=(
                "Export filtered release history"
                if self._filtered_history_entries
                else "Export filtered release history unavailable"
            ),
        )
        _set_widget_metadata(
            self._copy_history_file_button,
            tooltip=self._copy_path_hint("release history file", self._history_path),
            accessible_name=(
                "Copy release history file path"
                if self._history_path
                else "Copy release history file path unavailable"
            ),
        )
        _set_widget_metadata(
            self._copy_history_json_button,
            tooltip=(
                f"Copy the release history JSON file. Path state: available. Current path: {self._history_path}."
                if history_exists
                else (
                    f"No readable release history JSON file is available to copy. "
                    f"Path state: {'missing' if self._history_path else 'unavailable'}. Current path: {self._history_path or 'none'}."
                )
            ),
            accessible_name=(
                "Copy release history JSON"
                if history_exists
                else "Copy release history JSON unavailable"
            ),
        )
        _set_widget_metadata(
            self._export_history_json_button,
            tooltip=(
                f"Export the release history JSON file. Path state: available. Current path: {self._history_path}."
                if history_exists
                else (
                    f"No readable release history JSON file is available to export. "
                    f"Path state: {'missing' if self._history_path else 'unavailable'}. Current path: {self._history_path or 'none'}."
                )
            ),
            accessible_name=(
                "Export release history JSON"
                if history_exists
                else "Export release history JSON unavailable"
            ),
        )
        _set_widget_metadata(
            self._open_history_file_button,
            tooltip=(
                self._open_path_hint("release history JSON file", self._history_path)
                if self._open_path_callback is not None
                else (
                    f"The release history JSON file is unavailable or cannot be opened here. "
                    f"Path state: {'missing' if self._history_path else 'unavailable'}. Current path: {self._history_path or 'none'}."
                )
            ),
            accessible_name=(
                "Open release history file"
                if history_exists and self._open_path_callback is not None
                else "Open release history file unavailable"
            ),
        )
        _set_widget_metadata(
            self._refresh_button,
            tooltip=(
                f"Reload release history from disk. {refresh_context}"
                if self._refresh_history_callback is not None
                else f"Refresh unavailable because no history reload callback was provided. {refresh_context}"
            ),
            accessible_name=(
                "Refresh release history"
                if self._refresh_history_callback is not None
                else "Refresh release history unavailable"
            ),
        )
        _set_widget_metadata(self._history_list, tooltip=list_summary, accessible_name=list_summary)
        _set_widget_metadata(self._summary_label, tooltip=summary_text, accessible_name=f"Selected release summary: {summary_text}")
        _set_widget_metadata(self._details_edit, tooltip=details_summary, accessible_name=details_summary)
        _set_widget_metadata(self._preview_label, tooltip=preview_title, accessible_name=f"Release preview label: {preview_title}")
        _set_widget_metadata(self._preview_edit, tooltip=preview_summary, accessible_name=preview_summary)
        _set_widget_metadata(
            self._preview_auto_button,
            tooltip=self._preview_mode_hint("auto"),
            accessible_name="Auto preview" if self._preview_auto_button.isEnabled() else "Auto preview unavailable",
        )
        _set_widget_metadata(
            self._preview_manifest_button,
            tooltip=self._preview_mode_hint("manifest"),
            accessible_name="Preview manifest" if self._preview_manifest_button.isEnabled() else "Preview manifest unavailable",
        )
        _set_widget_metadata(
            self._preview_log_button,
            tooltip=self._preview_mode_hint("log"),
            accessible_name="Preview build log" if self._preview_log_button.isEnabled() else "Preview build log unavailable",
        )
        _set_widget_metadata(
            self._preview_version_button,
            tooltip=self._preview_mode_hint("version"),
            accessible_name="Preview version file" if self._preview_version_button.isEnabled() else "Preview version file unavailable",
        )
        _set_widget_metadata(
            self._copy_summary_button,
            tooltip=(
                f"Copy the selected release summary. {selection_context}"
                if self._current_entry() is not None
                else f"Select a release entry to copy its summary. {selection_context}"
            ),
        )
        _set_widget_metadata(
            self._export_summary_button,
            tooltip=(
                f"Export the selected release summary. {selection_context}"
                if self._current_entry() is not None
                else f"Select a release entry to export its summary. {selection_context}"
            ),
        )
        _set_widget_metadata(
            self._copy_details_button,
            tooltip=(
                f"Copy the selected release details. {selection_context}"
                if self._current_entry() is not None
                else f"Select a release entry to copy its details. {selection_context}"
            ),
        )
        _set_widget_metadata(
            self._copy_preview_button,
            tooltip=(
                f"Copy the full {preview_label_lower} preview text. {selection_context}"
                if self._current_entry() is not None
                else f"Select a release entry to copy its preview. {selection_context}"
            ),
        )
        _set_widget_metadata(
            self._copy_preview_path_button,
            tooltip=(
                f"Copy the current {preview_label_lower} preview path. Current path: {preview_path}."
                if preview_path
                else f"No {preview_label_lower} preview path is available to copy. Current path: none."
            ),
            accessible_name=(
                "Copy current preview path"
                if preview_path
                else "Copy current preview path unavailable"
            ),
        )
        _set_widget_metadata(
            self._export_preview_button,
            tooltip=(
                f"Export the current {preview_label_lower} preview. Path state: available. Current path: {preview_path}."
                if preview_path and os.path.isfile(preview_path)
                else (
                    f"No {preview_label_lower} preview file is available to export. "
                    f"Path state: {'missing' if preview_path else 'unavailable'}. Current path: {preview_path or 'none'}."
                )
            ),
        )
        _set_widget_metadata(
            self._open_preview_button,
            tooltip=(
                f"Open the current {preview_label_lower} preview file. Path state: available. Current path: {preview_path}."
                if self._open_path_callback is not None and preview_path and os.path.isfile(preview_path)
                else (
                    f"The current {preview_label_lower} preview file is unavailable or missing. "
                    f"Path state: {'missing' if preview_path else 'unavailable'}. Current path: {preview_path or 'none'}."
                )
            ),
            accessible_name=(
                "Open current preview file"
                if self._open_path_callback is not None and preview_path and os.path.isfile(preview_path)
                else "Open current preview file unavailable"
            ),
        )
        entry = self._current_entry() or {}
        release_root = _history_string(entry, "release_root")
        dist_dir = _history_string(entry, "dist_dir")
        package_path = _history_string(entry, "zip_path")
        manifest_path = _history_string(entry, "manifest_path")
        log_path = _history_string(entry, "log_path")
        version_path = _history_version_path(entry)
        _set_widget_metadata(self._copy_folder_path_button, tooltip=self._copy_path_hint("release folder", release_root))
        _set_widget_metadata(self._copy_dist_path_button, tooltip=self._copy_path_hint("release dist folder", dist_dir))
        _set_widget_metadata(self._copy_package_path_button, tooltip=self._copy_path_hint("release package", package_path))
        _set_widget_metadata(
            self._export_details_button,
            tooltip=(
                f"Export the selected release details. {selection_context}"
                if self._current_entry() is not None
                else f"Select a release entry to export its details. {selection_context}"
            ),
        )
        _set_widget_metadata(
            self._copy_entry_json_button,
            tooltip=(
                f"Copy the selected release entry as JSON. {selection_context}"
                if self._current_entry() is not None
                else f"Select a release entry to copy its JSON. {selection_context}"
            ),
        )
        _set_widget_metadata(
            self._export_entry_json_button,
            tooltip=(
                f"Export the selected release entry as JSON. {selection_context}"
                if self._current_entry() is not None
                else f"Select a release entry to export its JSON. {selection_context}"
            ),
        )
        _set_widget_metadata(self._open_folder_button, tooltip=self._open_path_hint("selected release folder", release_root, directory=True))
        _set_widget_metadata(self._open_dist_button, tooltip=self._open_path_hint("selected dist folder", dist_dir, directory=True))
        _set_widget_metadata(self._open_version_button, tooltip=self._open_path_hint("selected version file", version_path))
        _set_widget_metadata(self._open_manifest_button, tooltip=self._open_path_hint("selected manifest file", manifest_path))
        _set_widget_metadata(self._open_log_button, tooltip=self._open_path_hint("selected build log", log_path))
        _set_widget_metadata(self._open_package_button, tooltip=self._open_path_hint("selected package", package_path))

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
            searchable = _history_searchable_text(entry)
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
            item_tooltip = _history_summary_line(entry)
            item.setToolTip(item_tooltip)
            item.setStatusTip(item_tooltip)
            item.setData(Qt.AccessibleTextRole, item_tooltip)
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
            self._preview_edit.setPlainText(
                self._preview_empty_state_text(
                    "No manifest, version file, or build log is available because the filtered result set is empty."
                )
            )
        else:
            self._summary_label.setText("No release history available for this project.")
            self._details_edit.setPlainText("Run Build -> Release Build... to create the first tracked release.")
            self._preview_label.setText("Preview")
            self._preview_edit.setPlainText(
                self._preview_empty_state_text(
                    "Select a release entry to preview its manifest, version file, or build log."
                )
            )
        self._set_open_buttons(None)
        self._update_accessibility_summary()

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
        return json.dumps(_history_entry_export_payload(entry, include_details=True), indent=2, ensure_ascii=False) + "\n"

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

    def _export_entry_details(self) -> None:
        if not self._current_entry():
            return
        selected_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Release Entry Details",
            self._default_entry_text_export_filename(),
            "Text Files (*.txt);;All Files (*)",
        )
        if not selected_path:
            return
        try:
            if "Text" in str(selected_filter):
                selected_path = _append_suffix_if_missing(selected_path, ".txt")
            _write_text_file(selected_path, self._entry_details_text())
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

    def _default_entry_text_export_filename(self) -> str:
        return os.path.splitext(self._default_entry_export_filename())[0] + ".txt"

    def _copy_entry_summary(self) -> None:
        self._copy_text(self._entry_summary_text())

    def _entry_summary_text(self) -> str:
        entry = self._current_entry()
        if not entry:
            return ""
        return _history_summary_line(entry) + "\n"

    def _default_entry_summary_export_filename(self) -> str:
        return os.path.splitext(self._default_entry_export_filename())[0] + "-summary.txt"

    def _export_entry_summary(self) -> None:
        if not self._current_entry():
            return
        selected_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Release Entry Summary",
            self._default_entry_summary_export_filename(),
            "Text Files (*.txt);;All Files (*)",
        )
        if not selected_path:
            return
        try:
            if "Text" in str(selected_filter):
                selected_path = _append_suffix_if_missing(selected_path, ".txt")
            _write_text_file(selected_path, self._entry_summary_text())
        except OSError as exc:
            QMessageBox.warning(self, "Export Release Entry Failed", str(exc))

    def _entry_details_text(self) -> str:
        entry = self._current_entry()
        if not entry:
            return ""
        return _history_detail_text(entry).rstrip() + "\n"

    def _current_preview_target_options(self, entry: dict[str, object] | None = None) -> tuple[str, str, bool, str]:
        selected_entry = entry if entry is not None else self._current_entry()
        if selected_entry is None:
            return "Preview", "", False, ".txt"

        if self._preview_mode == "manifest":
            return "Manifest", _history_string(selected_entry, "manifest_path"), True, ".json"
        if self._preview_mode == "log":
            return "Log", _history_string(selected_entry, "log_path"), False, ".log"
        if self._preview_mode == "version":
            return "Version", _history_version_path(selected_entry), False, ".txt"

        manifest_path = _history_string(selected_entry, "manifest_path")
        if manifest_path:
            return "Manifest", manifest_path, True, ".json"

        log_path = _history_string(selected_entry, "log_path")
        if log_path:
            return "Log", log_path, False, ".log"

        version_path = _history_version_path(selected_entry)
        if version_path:
            return "Version", version_path, False, ".txt"
        return "Preview", "", False, ".txt"

    def _current_preview_target(self, entry: dict[str, object] | None = None) -> tuple[str, str]:
        label, path, _prefer_json, _suffix = self._current_preview_target_options(entry)
        return label, path

    def _update_preview_path_button(self, entry: dict[str, object] | None = None) -> None:
        label, path = self._current_preview_target(entry)
        self._copy_preview_path_button.setText(f"Copy {label} Path")
        self._copy_preview_path_button.setEnabled(bool(path))

    def _update_preview_export_button(self, entry: dict[str, object] | None = None) -> None:
        label, path, _prefer_json, _suffix = self._current_preview_target_options(entry)
        self._export_preview_button.setText(f"Export {label}...")
        self._export_preview_button.setEnabled(bool(path and os.path.isfile(path)))

    def _update_preview_open_button(self, entry: dict[str, object] | None = None) -> None:
        label, path, _prefer_json, _suffix = self._current_preview_target_options(entry)
        self._open_preview_button.setText(f"Open {label}")
        self._open_preview_button.setEnabled(bool(self._open_path_callback and path and os.path.isfile(path)))

    def _update_preview_target_buttons(self, entry: dict[str, object] | None = None) -> None:
        self._update_preview_path_button(entry)
        self._update_preview_export_button(entry)
        self._update_preview_open_button(entry)

    def _copy_preview_path(self) -> None:
        _, path = self._current_preview_target()
        self._copy_text(path + "\n" if path else "")

    def _default_preview_export_filename(self) -> str:
        base = os.path.splitext(self._default_entry_export_filename())[0]
        label, _path, _prefer_json, suffix = self._current_preview_target_options()
        label_part = _safe_filename_part(label or "preview")
        return f"{base}-{label_part}{suffix}"

    def _current_preview_text(self, *, full_content: bool = False) -> str:
        _label, path, prefer_json, _suffix = self._current_preview_target_options()
        if not path:
            return self._preview_edit.toPlainText()
        char_limit = None if full_content else _PREVIEW_CHAR_LIMIT
        return _preview_file_text(path, prefer_json=prefer_json, char_limit=char_limit)

    def _copy_preview_text(self) -> None:
        self._copy_text(self._current_preview_text(full_content=True))

    def _preview_export_text(self) -> str:
        return self._current_preview_text(full_content=True).rstrip() + "\n"

    def _export_preview(self) -> None:
        label, path, _prefer_json, default_suffix = self._current_preview_target_options()
        if not path or not os.path.isfile(path):
            return
        selected_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            f"Export {label} Preview",
            self._default_preview_export_filename(),
            "JSON Files (*.json);;Log Files (*.log);;Text Files (*.txt);;All Files (*)",
        )
        if not selected_path:
            return
        try:
            suffix = default_suffix
            if "JSON" in str(selected_filter):
                suffix = ".json"
            elif "Log" in str(selected_filter):
                suffix = ".log"
            elif "Text" in str(selected_filter):
                suffix = ".txt"
            selected_path = _append_suffix_if_missing(selected_path, suffix)
            _write_text_file(selected_path, self._preview_export_text())
        except OSError as exc:
            QMessageBox.warning(self, "Export Release Preview Failed", str(exc))

    def _open_preview(self) -> None:
        label, path, _prefer_json, _suffix = self._current_preview_target_options()
        if self._open_path_callback is None or not path or not os.path.isfile(path):
            return
        try:
            self._open_path_callback(path)
        except Exception as exc:
            QMessageBox.warning(self, f"Open {label} Failed", str(exc))

    def _copy_package_path(self) -> None:
        entry = self._current_entry()
        path = _history_string(entry or {}, "zip_path")
        self._copy_text(path + "\n" if path else "")

    def _copy_selected_path(self, key: str) -> None:
        entry = self._current_entry()
        path = _history_string(entry or {}, key)
        self._copy_text(path + "\n" if path else "")

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
            self._preview_edit.setPlainText(
                self._preview_empty_state_text(
                    "Select a release entry to preview its manifest, version file, or build log."
                )
            )
            self._update_preview_target_buttons(None)
            self._update_accessibility_summary()
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
            self._preview_edit.setPlainText(
                self._preview_empty_state_text(
                    "No manifest, version file, or build log is recorded for this release entry."
                )
            )
            self._update_preview_target_buttons(entry)
            self._update_accessibility_summary()

    def _sync_preview_mode_buttons(self) -> None:
        self._preview_auto_button.setChecked(self._preview_mode == "auto")
        self._preview_manifest_button.setChecked(self._preview_mode == "manifest")
        self._preview_log_button.setChecked(self._preview_mode == "log")
        self._preview_version_button.setChecked(self._preview_mode == "version")

    def _update_history_file_button(self) -> None:
        self._copy_history_file_button.setEnabled(bool(self._history_path))
        history_exists = bool(self._history_path and os.path.isfile(self._history_path))
        self._copy_history_json_button.setEnabled(history_exists)
        self._export_history_json_button.setEnabled(history_exists)
        self._open_history_file_button.setEnabled(bool(self._open_path_callback and history_exists))
        self._update_accessibility_summary()

    def _copy_history_file_path(self) -> None:
        self._copy_text(self._history_path + "\n" if self._history_path else "")

    def _copy_history_file_json(self) -> None:
        if not self._history_path or not os.path.isfile(self._history_path):
            self._copy_text("")
            return
        self._copy_text(_preview_file_text(self._history_path, prefer_json=True, char_limit=None).rstrip() + "\n")

    def _default_history_json_export_filename(self) -> str:
        if self._history_path:
            basename = os.path.basename(self._history_path).strip()
            if basename:
                return basename
        return "history.json"

    def _export_history_file_json(self) -> None:
        if not self._history_path or not os.path.isfile(self._history_path):
            return
        selected_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Release History JSON",
            self._default_history_json_export_filename(),
            "JSON Files (*.json);;All Files (*)",
        )
        if not selected_path:
            return
        try:
            if "JSON" in str(selected_filter):
                selected_path = _append_suffix_if_missing(selected_path, ".json")
            _write_text_file(selected_path, _preview_file_text(self._history_path, prefer_json=True, char_limit=None).rstrip() + "\n")
        except OSError as exc:
            QMessageBox.warning(self, "Export Release History Failed", str(exc))

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
        self._export_summary_button.setEnabled(bool(entry))
        self._copy_details_button.setEnabled(bool(entry))
        self._copy_preview_button.setEnabled(bool(entry))
        self._copy_folder_path_button.setEnabled(bool(release_root))
        self._copy_dist_path_button.setEnabled(bool(dist_dir))
        self._copy_package_path_button.setEnabled(bool(package_path))
        self._export_details_button.setEnabled(bool(entry))
        self._copy_entry_json_button.setEnabled(bool(entry))
        self._export_entry_json_button.setEnabled(bool(entry))
        self._update_preview_target_buttons(entry)
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
            self._preview_edit.setPlainText(
                self._preview_empty_state_text(
                    "Select a release entry to preview its manifest, version file, or build log."
                )
            )
            self._set_open_buttons(None)
            self._update_accessibility_summary()
            return
        entry = self._current_entry()
        if entry is None:
            self._summary_label.setText("No release entry selected.")
            self._details_edit.clear()
            self._preview_label.setText("Preview")
            self._preview_edit.setPlainText(
                self._preview_empty_state_text(
                    "Select a release entry to preview its manifest, version file, or build log."
                )
            )
            self._set_open_buttons(None)
            self._update_accessibility_summary()
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
            self._preview_edit.setPlainText(
                self._preview_empty_state_text(
                    f"No {label.lower()} path is recorded for this release entry."
                )
            )
            self._update_preview_target_buttons(entry)
            self._update_accessibility_summary()
            return
        self._preview_edit.setPlainText(_preview_file_text(path, prefer_json=prefer_json))
        self._update_preview_target_buttons(entry)
        self._update_accessibility_summary()

    def _preview_selected_version(self) -> None:
        entry = self._current_entry()
        path = _history_version_path(entry or {})
        self._preview_label.setText("Version Preview")
        if not path:
            self._preview_edit.setPlainText(
                self._preview_empty_state_text("No version file is available for this release entry.")
            )
            self._update_preview_target_buttons(entry)
            self._update_accessibility_summary()
            return
        self._preview_edit.setPlainText(_preview_file_text(path))
        self._update_preview_target_buttons(entry)
        self._update_accessibility_summary()

    def _copy_text(self, text: str) -> None:
        QApplication.clipboard().setText(text or "")
