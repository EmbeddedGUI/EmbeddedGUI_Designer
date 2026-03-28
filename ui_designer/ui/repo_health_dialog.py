"""Repository health dialog for inspecting local workspace state."""

from __future__ import annotations

import os
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton, QTextEdit, QVBoxLayout

from ..model.config import get_config
from ..model.repo_health import (
    collect_repo_health,
    format_repo_health_json,
    format_repo_health_summary,
    format_repo_health_text,
    repo_health_counts,
    repo_health_view_payload,
    summarize_repo_health,
)


def _set_widget_metadata(widget, *, tooltip=None, accessible_name=None) -> None:
    if tooltip is not None:
        widget.setToolTip(tooltip)
        widget.setStatusTip(tooltip)
    if accessible_name is not None:
        widget.setAccessibleName(accessible_name)


class RepositoryHealthDialog(QDialog):
    """Inspect repository health and open relevant workspace paths."""

    def __init__(self, repo_root: str, open_path_callback=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Repository Health")
        self.resize(920, 520)
        self._config = get_config()
        self._repo_root = str(Path(repo_root).resolve())
        self._open_path_callback = open_path_callback
        self._preferred_stale_path = ""
        self._payload: dict[str, object] = {}

        root_layout = QVBoxLayout(self)

        self._summary_label = QLabel()
        self._summary_label.setWordWrap(True)
        root_layout.addWidget(self._summary_label)

        self._overview_label = QLabel("critical 0 | suggestions 0 | stale 0 | blocked 0")
        self._overview_label.setWordWrap(True)
        root_layout.addWidget(self._overview_label)

        self._details_edit = QTextEdit()
        self._details_edit.setReadOnly(True)
        root_layout.addWidget(self._details_edit, 1)

        action_row = QHBoxLayout()
        root_layout.addLayout(action_row)

        self._refresh_button = QPushButton("Refresh")
        self._reset_view_button = QPushButton("Reset View")
        self._critical_only_check = QCheckBox("Critical Only")
        self._blocked_only_check = QCheckBox("Blocked Only")
        self._show_json_check = QCheckBox("Show JSON")
        self._copy_summary_button = QPushButton("Copy Summary")
        self._export_summary_button = QPushButton("Export Summary...")
        self._copy_report_button = QPushButton("Copy Report")
        self._copy_json_button = QPushButton("Copy JSON")
        self._export_report_button = QPushButton("Export Report...")
        self._copy_repo_button = QPushButton("Copy Repo")
        self._open_repo_button = QPushButton("Open Repo")
        self._copy_sdk_button = QPushButton("Copy SDK")
        self._open_sdk_button = QPushButton("Open SDK")
        self._copy_smoke_button = QPushButton("Copy Smoke")
        self._open_smoke_button = QPushButton("Open Smoke Sample")
        self._stale_dir_combo = QComboBox()
        self._copy_stale_path_button = QPushButton("Copy Stale Path")
        self._open_stale_button = QPushButton("Open Stale Dir")
        self._stale_dir_combo.setMinimumContentsLength(28)

        self._refresh_button.clicked.connect(self.refresh)
        self._reset_view_button.clicked.connect(self._reset_view)
        self._critical_only_check.toggled.connect(self._render_details)
        self._blocked_only_check.toggled.connect(self._render_details)
        self._show_json_check.toggled.connect(self._render_details)
        self._stale_dir_combo.currentIndexChanged.connect(self._on_stale_dir_selected)
        self._copy_summary_button.clicked.connect(self._copy_summary)
        self._export_summary_button.clicked.connect(self._export_summary)
        self._copy_report_button.clicked.connect(self._copy_report)
        self._copy_json_button.clicked.connect(self._copy_json)
        self._export_report_button.clicked.connect(self._export_report)
        self._copy_repo_button.clicked.connect(lambda: self._copy_payload_path("repo_root"))
        self._open_repo_button.clicked.connect(lambda: self._open_payload_path("repo_root", "Repository Root"))
        self._copy_sdk_button.clicked.connect(lambda: self._copy_nested_payload_path("sdk_submodule", "path"))
        self._open_sdk_button.clicked.connect(lambda: self._open_nested_payload_path("sdk_submodule", "path", "SDK Folder"))
        self._copy_smoke_button.clicked.connect(lambda: self._copy_nested_payload_path("release_smoke_project", "path"))
        self._open_smoke_button.clicked.connect(lambda: self._open_nested_payload_path("release_smoke_project", "path", "Smoke Project"))
        self._copy_stale_path_button.clicked.connect(self._copy_selected_stale_path)
        self._open_stale_button.clicked.connect(self._open_selected_stale_dir)

        action_row.addWidget(self._refresh_button)
        action_row.addWidget(self._reset_view_button)
        action_row.addWidget(self._critical_only_check)
        action_row.addWidget(self._blocked_only_check)
        action_row.addWidget(self._show_json_check)
        for button in (
            self._copy_summary_button,
            self._export_summary_button,
            self._copy_report_button,
            self._copy_json_button,
            self._export_report_button,
            self._copy_repo_button,
            self._open_repo_button,
            self._copy_sdk_button,
            self._open_sdk_button,
            self._copy_smoke_button,
            self._open_smoke_button,
        ):
            action_row.addWidget(button)
        action_row.addWidget(self._stale_dir_combo, 1)
        action_row.addWidget(self._copy_stale_path_button)
        action_row.addWidget(self._open_stale_button)
        action_row.addStretch(1)

        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(self.reject)
        button_box.accepted.connect(self.accept)
        root_layout.addWidget(button_box)
        close_button = button_box.button(QDialogButtonBox.Close)

        self._refresh_button.setAccessibleName("Refresh repository health")
        self._reset_view_button.setAccessibleName("Reset repository health view")
        self._critical_only_check.setAccessibleName("Critical only filter")
        self._blocked_only_check.setAccessibleName("Blocked stale directories filter")
        self._show_json_check.setAccessibleName("Show JSON report")
        self._copy_summary_button.setAccessibleName("Copy repository health summary")
        self._export_summary_button.setAccessibleName("Export repository health summary")
        self._copy_report_button.setAccessibleName("Copy repository health report")
        self._copy_json_button.setAccessibleName("Copy repository health JSON")
        self._export_report_button.setAccessibleName("Export repository health report")
        self._copy_repo_button.setAccessibleName("Copy repository root path")
        self._open_repo_button.setAccessibleName("Open repository root")
        self._copy_sdk_button.setAccessibleName("Copy SDK folder path")
        self._open_sdk_button.setAccessibleName("Open SDK folder")
        self._copy_smoke_button.setAccessibleName("Copy release smoke sample path")
        self._open_smoke_button.setAccessibleName("Open release smoke sample")
        self._stale_dir_combo.setAccessibleName("Stale temp directories")
        self._copy_stale_path_button.setAccessibleName("Copy selected stale temp directory path")
        self._open_stale_button.setAccessibleName("Open selected stale temp directory")
        if close_button is not None:
            _set_widget_metadata(
                close_button,
                tooltip="Close the repository health dialog.",
                accessible_name="Close repository health dialog",
            )

        self._restore_view_state()
        self.refresh()

    def refresh(self) -> None:
        self._payload = collect_repo_health(self._repo_root)
        self._render_details()

    def _count_label(self, count: int, singular: str, plural: str | None = None) -> str:
        value = max(int(count or 0), 0)
        noun = singular if value == 1 else (plural or f"{singular}s")
        return f"{value} {noun}"

    def _toggle_state_label(self, checked: bool) -> str:
        return "on" if checked else "off"

    def _view_mode_label(self) -> str:
        return "JSON" if self._show_json_check.isChecked() else "text"

    def _refresh_hint(self) -> str:
        return "Refresh repository health, runtime path checks, and stale temp directory scan."

    def _has_custom_view_state(self) -> bool:
        has_non_default_stale_selection = self._stale_dir_combo.count() > 0 and self._stale_dir_combo.currentIndex() > 0
        return bool(
            self._critical_only_check.isChecked()
            or self._blocked_only_check.isChecked()
            or self._show_json_check.isChecked()
            or has_non_default_stale_selection
        )

    def _reset_view_hint(self) -> str:
        if self._has_custom_view_state():
            return "Reset repository health filters, JSON view, and stale-directory selection."
        return "Repository health already shows the full text report."

    def _copy_path_hint(self, label: str, path: str) -> str:
        if path:
            return f"Copy the {label} path."
        return f"No {label} path is available to copy."

    def _open_path_hint(self, label: str, path: str) -> str:
        if path and os.path.exists(path):
            return f"Open the {label} in the system file browser."
        return f"The {label} path is unavailable or missing."

    def _stale_dir_hint(self) -> str:
        count = self._stale_dir_combo.count()
        if count <= 0:
            return "No stale temp directories are available in the current view."
        current_selection = str(self._stale_dir_combo.currentText() or "none").strip() or "none"
        count_text = self._count_label(count, "entry")
        return f"Select a stale temp directory to copy or open. {count_text}. Current selection: {current_selection}."

    def _copy_stale_path_hint(self) -> str:
        if self._selected_stale_path():
            return "Copy the selected stale temp directory path."
        return "No stale temp directory is selected to copy."

    def _open_stale_path_hint(self) -> str:
        return self._open_path_hint("selected stale temp directory", self._selected_stale_path())

    def _update_accessibility_summary(self) -> None:
        view_payload = self._current_view_payload()
        counts = repo_health_counts(view_payload)
        summary_text = str(self._summary_label.text() or "Repository health looks good.").strip() or "Repository health looks good."
        counts_text = (
            "Repository health counts: "
            f"{self._count_label(counts['critical'], 'critical issue')}, "
            f"{self._count_label(counts['suggestions'], 'suggestion')}, "
            f"{self._count_label(counts['stale_dirs'], 'stale directory')}, "
            f"{self._count_label(counts['blocked_stale_dirs'], 'blocked stale directory')}."
        )
        counts_accessible = counts_text.removeprefix("Repository health counts: ").rstrip(".")
        view_text = (
            "Filters: "
            f"critical {self._toggle_state_label(self._critical_only_check.isChecked())}, "
            f"blocked {self._toggle_state_label(self._blocked_only_check.isChecked())}. "
            f"View: {self._view_mode_label()}."
        )
        dialog_summary = f"Repository health: {summary_text} {counts_text} {view_text}"
        if self._stale_dir_combo.count() > 0:
            current_selection = str(self._stale_dir_combo.currentText() or "none").strip() or "none"
            dialog_summary += f" Current stale selection: {current_selection}."

        details_summary = (
            f"Repository health details: {self._view_mode_label()} view. "
            f"Filters: critical {self._toggle_state_label(self._critical_only_check.isChecked())}, "
            f"blocked {self._toggle_state_label(self._blocked_only_check.isChecked())}."
        )
        stale_summary = self._stale_dir_hint()
        repo_root = str(self._payload.get("repo_root") or "").strip()
        sdk = self._payload.get("sdk_submodule") if isinstance(self._payload.get("sdk_submodule"), dict) else {}
        smoke = self._payload.get("release_smoke_project") if isinstance(self._payload.get("release_smoke_project"), dict) else {}
        sdk_path = str(sdk.get("path") or "").strip()
        smoke_path = str(smoke.get("path") or "").strip()
        reset_available = self._has_custom_view_state()
        can_copy_repo = bool(repo_root)
        can_open_repo = bool(repo_root and os.path.isdir(repo_root))
        can_copy_sdk = bool(sdk_path)
        can_open_sdk = bool(sdk.get("present")) and bool(sdk_path and os.path.isdir(sdk_path))
        can_copy_smoke = bool(smoke_path)
        can_open_smoke = bool(smoke.get("present")) and bool(smoke_path and os.path.isdir(smoke_path))
        can_copy_stale = bool(self._selected_stale_path())
        can_open_stale = bool(self._selected_stale_path() and os.path.exists(self._selected_stale_path()))
        report_mode = self._view_mode_label()

        _set_widget_metadata(self, tooltip=dialog_summary, accessible_name=dialog_summary)
        _set_widget_metadata(
            self._summary_label,
            tooltip=summary_text,
            accessible_name=f"Repository health summary: {summary_text}",
        )
        _set_widget_metadata(self._overview_label, tooltip=counts_text, accessible_name=counts_text)
        _set_widget_metadata(self._details_edit, tooltip=details_summary, accessible_name=details_summary)
        _set_widget_metadata(self._refresh_button, tooltip=self._refresh_hint())
        _set_widget_metadata(
            self._reset_view_button,
            tooltip=self._reset_view_hint(),
            accessible_name="Reset repository health view" if reset_available else "Reset repository health view unavailable",
        )
        _set_widget_metadata(
            self._critical_only_check,
            tooltip=(
                "Showing only critical repository health issues."
                if self._critical_only_check.isChecked()
                else "Filter the report to critical repository health issues."
            ),
            accessible_name=f"Critical only filter: {self._toggle_state_label(self._critical_only_check.isChecked())}",
        )
        _set_widget_metadata(
            self._blocked_only_check,
            tooltip=(
                "Showing only stale temp directories blocked by access errors."
                if self._blocked_only_check.isChecked()
                else "Filter the report to stale temp directories blocked by access errors."
            ),
            accessible_name=f"Blocked stale directories filter: {self._toggle_state_label(self._blocked_only_check.isChecked())}",
        )
        _set_widget_metadata(
            self._show_json_check,
            tooltip=(
                "Showing the repository health report as JSON."
                if self._show_json_check.isChecked()
                else "Show the repository health report as JSON."
            ),
            accessible_name=f"Show JSON report: {self._toggle_state_label(self._show_json_check.isChecked())}",
        )
        _set_widget_metadata(
            self._copy_summary_button,
            tooltip="Copy the current repository health summary.",
            accessible_name=f"Copy repository health summary: {counts_accessible}",
        )
        _set_widget_metadata(
            self._export_summary_button,
            tooltip="Export the current repository health summary to a text file.",
            accessible_name=f"Export repository health summary: {counts_accessible}",
        )
        _set_widget_metadata(
            self._copy_report_button,
            tooltip=f"Copy the current repository health {self._view_mode_label()} report.",
            accessible_name=f"Copy repository health {report_mode} report",
        )
        _set_widget_metadata(
            self._copy_json_button,
            tooltip="Copy the current repository health report as JSON.",
            accessible_name=f"Copy repository health JSON report: {counts_accessible}",
        )
        _set_widget_metadata(
            self._export_report_button,
            tooltip=f"Export the current repository health {self._view_mode_label()} report.",
            accessible_name=f"Export repository health {report_mode} report",
        )
        _set_widget_metadata(
            self._copy_repo_button,
            tooltip=self._copy_path_hint("repository root", repo_root),
            accessible_name="Copy repository root path" if can_copy_repo else "Copy repository root path unavailable",
        )
        _set_widget_metadata(
            self._open_repo_button,
            tooltip=self._open_path_hint("repository root", repo_root),
            accessible_name="Open repository root" if can_open_repo else "Open repository root unavailable",
        )
        _set_widget_metadata(
            self._copy_sdk_button,
            tooltip=self._copy_path_hint("SDK folder", sdk_path),
            accessible_name="Copy SDK folder path" if can_copy_sdk else "Copy SDK folder path unavailable",
        )
        _set_widget_metadata(
            self._open_sdk_button,
            tooltip=self._open_path_hint("SDK folder", sdk_path),
            accessible_name="Open SDK folder" if can_open_sdk else "Open SDK folder unavailable",
        )
        _set_widget_metadata(
            self._copy_smoke_button,
            tooltip=self._copy_path_hint("release smoke sample", smoke_path),
            accessible_name=(
                "Copy release smoke sample path"
                if can_copy_smoke
                else "Copy release smoke sample path unavailable"
            ),
        )
        _set_widget_metadata(
            self._open_smoke_button,
            tooltip=self._open_path_hint("release smoke sample", smoke_path),
            accessible_name="Open release smoke sample" if can_open_smoke else "Open release smoke sample unavailable",
        )
        _set_widget_metadata(
            self._stale_dir_combo,
            tooltip=stale_summary,
            accessible_name=f"Stale temp directories: {stale_summary.removesuffix('.')}.",
        )
        _set_widget_metadata(
            self._copy_stale_path_button,
            tooltip=self._copy_stale_path_hint(),
            accessible_name=(
                "Copy selected stale temp directory path"
                if can_copy_stale
                else "Copy selected stale temp directory path unavailable"
            ),
        )
        _set_widget_metadata(
            self._open_stale_button,
            tooltip=self._open_stale_path_hint(),
            accessible_name=(
                "Open selected stale temp directory"
                if can_open_stale
                else "Open selected stale temp directory unavailable"
            ),
        )

    def _view_options(self) -> dict[str, bool]:
        return {
            "critical_only": self._critical_only_check.isChecked(),
            "blocked_only": self._blocked_only_check.isChecked(),
        }

    def _reset_view(self) -> None:
        self._preferred_stale_path = ""
        self._critical_only_check.setChecked(False)
        self._blocked_only_check.setChecked(False)
        self._show_json_check.setChecked(False)
        if self._stale_dir_combo.count():
            self._stale_dir_combo.setCurrentIndex(0)
        else:
            self._on_stale_dir_selected()

    def _render_details(self) -> None:
        view_options = self._view_options()
        view_payload = repo_health_view_payload(self._payload, **view_options)
        counts = repo_health_counts(view_payload)
        self._summary_label.setText(summarize_repo_health(view_payload))
        self._overview_label.setText(
            (
                f"critical {counts['critical']} | "
                f"suggestions {counts['suggestions']} | "
                f"stale {counts['stale_dirs']} | "
                f"blocked {counts['blocked_stale_dirs']}"
            )
        )
        sdk = self._payload.get("sdk_submodule") if isinstance(self._payload.get("sdk_submodule"), dict) else {}
        smoke = self._payload.get("release_smoke_project") if isinstance(self._payload.get("release_smoke_project"), dict) else {}
        stale_dirs = view_payload.get("stale_temp_dirs") if isinstance(view_payload.get("stale_temp_dirs"), list) else []
        selected_stale_path = self._selected_stale_path() or self._preferred_stale_path
        self._sync_stale_dir_combo(stale_dirs, selected_stale_path)
        self._preferred_stale_path = self._selected_stale_path()
        repo_root = str(self._payload.get("repo_root") or "").strip()
        sdk_path = str(sdk.get("path") or "").strip()
        smoke_path = str(smoke.get("path") or "").strip()
        stale_path = self._selected_stale_path()
        self._copy_repo_button.setEnabled(bool(repo_root))
        self._copy_sdk_button.setEnabled(bool(sdk_path))
        self._copy_smoke_button.setEnabled(bool(smoke_path))
        self._open_repo_button.setEnabled(bool(repo_root and os.path.isdir(repo_root)))
        self._open_sdk_button.setEnabled(bool(sdk.get("present")) and bool(sdk_path and os.path.isdir(sdk_path)))
        self._open_smoke_button.setEnabled(bool(smoke.get("present")) and bool(smoke_path and os.path.isdir(smoke_path)))
        self._copy_stale_path_button.setEnabled(bool(stale_path))
        self._open_stale_button.setEnabled(bool(stale_path and os.path.exists(stale_path)))
        details_text = format_repo_health_text(view_payload, **view_options)
        if self._show_json_check.isChecked():
            details_text = format_repo_health_json(view_payload, **view_options)
        self._details_edit.setPlainText(details_text)
        self._update_accessibility_summary()

    def _open_payload_path(self, key: str, label: str) -> None:
        path = str(self._payload.get(key) or "").strip()
        if not path:
            return
        self._open_path(path, label)

    def _copy_payload_path(self, key: str) -> None:
        self._copy_text(str(self._payload.get(key) or "").strip())

    def _open_nested_payload_path(self, section_key: str, key: str, label: str) -> None:
        section = self._payload.get(section_key)
        if not isinstance(section, dict):
            return
        path = str(section.get(key) or "").strip()
        if not path:
            return
        self._open_path(path, label)

    def _copy_nested_payload_path(self, section_key: str, key: str) -> None:
        section = self._payload.get(section_key)
        if not isinstance(section, dict):
            self._copy_text("")
            return
        self._copy_text(str(section.get(key) or "").strip())

    def _open_path(self, path: str, label: str) -> None:
        if self._open_path_callback is None:
            return
        try:
            self._open_path_callback(path)
        except Exception as exc:
            QMessageBox.warning(self, f"Open {label} Failed", str(exc))

    def _copy_report(self) -> None:
        self._copy_text(self._details_edit.toPlainText())

    def _current_view_payload(self) -> dict[str, object]:
        return repo_health_view_payload(self._payload, **self._view_options())

    def _report_text(self, *, show_json: bool) -> str:
        view_options = self._view_options()
        view_payload = self._current_view_payload()
        if show_json:
            return format_repo_health_json(view_payload, **view_options)
        return format_repo_health_text(view_payload, **view_options)

    def _copy_json(self) -> None:
        self._copy_text(self._report_text(show_json=True))

    def _copy_summary(self) -> None:
        view_options = self._view_options()
        self._copy_text(format_repo_health_summary(self._current_view_payload(), **view_options))

    def _summary_text(self) -> str:
        view_options = self._view_options()
        return format_repo_health_summary(self._current_view_payload(), **view_options).rstrip() + "\n"

    def _export_summary(self) -> None:
        selected_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Repository Health Summary",
            self._default_summary_export_filename(),
            "Text Files (*.txt);;All Files (*)",
        )
        if not selected_path:
            return
        try:
            if "Text" in str(selected_filter):
                selected_path = selected_path if os.path.splitext(selected_path)[1] else selected_path + ".txt"
            resolved_path = os.path.abspath(os.path.normpath(selected_path))
            parent_dir = os.path.dirname(resolved_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
            with open(resolved_path, "w", encoding="utf-8") as f:
                f.write(self._summary_text())
        except OSError as exc:
            QMessageBox.warning(self, "Export Repository Health Failed", str(exc))

    def _copy_selected_stale_path(self) -> None:
        self._copy_text(self._selected_stale_path())

    def _selected_stale_path(self) -> str:
        return str(self._stale_dir_combo.currentData() or "").strip()

    def _on_stale_dir_selected(self) -> None:
        self._preferred_stale_path = self._selected_stale_path()
        stale_path = self._selected_stale_path()
        self._copy_stale_path_button.setEnabled(bool(stale_path))
        self._open_stale_button.setEnabled(bool(stale_path and os.path.exists(stale_path)))
        self._update_accessibility_summary()

    def _sync_stale_dir_combo(self, stale_dirs: list[object], selected_path: str = "") -> None:
        self._stale_dir_combo.blockSignals(True)
        self._stale_dir_combo.clear()
        for entry in stale_dirs:
            if not isinstance(entry, dict):
                continue
            path = str(entry.get("path") or "").strip()
            if not path:
                continue
            label = Path(path).name or path
            accessible_text = f"Stale temp directory: {label}. Path: {path}."
            if not bool(entry.get("accessible", False)):
                issue = str(entry.get("issue") or "blocked")
                label = f"{label} [{issue}]"
                accessible_text = f"Stale temp directory: {label}. Path: {path}. Issue: {issue}."
            self._stale_dir_combo.addItem(label, path)
            index = self._stale_dir_combo.count() - 1
            tooltip = f"{label}\n{path}"
            self._stale_dir_combo.setItemData(index, tooltip, Qt.ToolTipRole)
            self._stale_dir_combo.setItemData(index, tooltip, Qt.StatusTipRole)
            self._stale_dir_combo.setItemData(index, accessible_text, Qt.AccessibleTextRole)
        match_index = self._stale_dir_combo.findData(selected_path) if selected_path else -1
        if match_index >= 0:
            self._stale_dir_combo.setCurrentIndex(match_index)
        elif self._stale_dir_combo.count():
            self._stale_dir_combo.setCurrentIndex(0)
        self._stale_dir_combo.setEnabled(self._stale_dir_combo.count() > 0)
        self._stale_dir_combo.blockSignals(False)

    def _open_selected_stale_dir(self) -> None:
        path = self._selected_stale_path()
        if not path:
            return
        self._open_path(path, "Stale Temp Directory")

    def _export_report(self) -> None:
        default_name = self._default_export_filename()
        selected_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Repository Health Report",
            default_name,
            "JSON Files (*.json);;Text Files (*.txt);;All Files (*)",
        )
        if not selected_path:
            return
        try:
            export_json = self._show_json_check.isChecked()
            if "JSON" in str(selected_filter):
                selected_path = selected_path if os.path.splitext(selected_path)[1] else selected_path + ".json"
                export_json = True
            elif "Text" in str(selected_filter):
                selected_path = selected_path if os.path.splitext(selected_path)[1] else selected_path + ".txt"
                export_json = False
            resolved_path = os.path.abspath(os.path.normpath(selected_path))
            parent_dir = os.path.dirname(resolved_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
            with open(resolved_path, "w", encoding="utf-8") as f:
                f.write(self._report_text(show_json=export_json).rstrip() + "\n")
        except OSError as exc:
            QMessageBox.warning(self, "Export Repository Health Failed", str(exc))

    def _default_export_filename(self) -> str:
        parts = ["repo-health"]
        if self._critical_only_check.isChecked():
            parts.append("critical")
        if self._blocked_only_check.isChecked():
            parts.append("blocked")
        if self._show_json_check.isChecked():
            return "-".join(parts) + ".json"
        return "-".join(parts) + ".txt"

    def _default_summary_export_filename(self) -> str:
        parts = ["repo-health-summary"]
        if self._critical_only_check.isChecked():
            parts.append("critical")
        if self._blocked_only_check.isChecked():
            parts.append("blocked")
        return "-".join(parts) + ".txt"

    def _restore_view_state(self) -> None:
        state = self._config.repo_health_view if isinstance(self._config.repo_health_view, dict) else {}
        self._critical_only_check.setChecked(bool(state.get("critical_only", False)))
        self._blocked_only_check.setChecked(bool(state.get("blocked_only", False)))
        self._show_json_check.setChecked(bool(state.get("show_json", False)))
        self._preferred_stale_path = str(state.get("selected_stale_path") or "")

    def _save_view_state(self) -> None:
        self._config.repo_health_view = {
            "critical_only": self._critical_only_check.isChecked(),
            "blocked_only": self._blocked_only_check.isChecked(),
            "show_json": self._show_json_check.isChecked(),
            "selected_stale_path": self._selected_stale_path(),
        }
        self._config.save()

    def done(self, result: int) -> None:
        self._save_view_state()
        super().done(result)

    def _copy_text(self, text: str) -> None:
        QApplication.clipboard().setText(text or "")
