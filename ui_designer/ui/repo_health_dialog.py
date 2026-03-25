"""Repository health dialog for inspecting local workspace state."""

from __future__ import annotations

import os
from pathlib import Path

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
        self._copy_report_button = QPushButton("Copy Report")
        self._copy_json_button = QPushButton("Copy JSON")
        self._export_report_button = QPushButton("Export Report...")
        self._open_repo_button = QPushButton("Open Repo")
        self._open_sdk_button = QPushButton("Open SDK")
        self._open_smoke_button = QPushButton("Open Smoke Sample")
        self._stale_dir_combo = QComboBox()
        self._open_stale_button = QPushButton("Open Stale Dir")
        self._stale_dir_combo.setMinimumContentsLength(28)

        self._refresh_button.clicked.connect(self.refresh)
        self._reset_view_button.clicked.connect(self._reset_view)
        self._critical_only_check.toggled.connect(self._render_details)
        self._blocked_only_check.toggled.connect(self._render_details)
        self._show_json_check.toggled.connect(self._render_details)
        self._stale_dir_combo.currentIndexChanged.connect(self._on_stale_dir_selected)
        self._copy_summary_button.clicked.connect(self._copy_summary)
        self._copy_report_button.clicked.connect(self._copy_report)
        self._copy_json_button.clicked.connect(self._copy_json)
        self._export_report_button.clicked.connect(self._export_report)
        self._open_repo_button.clicked.connect(lambda: self._open_payload_path("repo_root", "Repository Root"))
        self._open_sdk_button.clicked.connect(lambda: self._open_nested_payload_path("sdk_submodule", "path", "SDK Folder"))
        self._open_smoke_button.clicked.connect(lambda: self._open_nested_payload_path("release_smoke_project", "path", "Smoke Project"))
        self._open_stale_button.clicked.connect(self._open_selected_stale_dir)

        action_row.addWidget(self._refresh_button)
        action_row.addWidget(self._reset_view_button)
        action_row.addWidget(self._critical_only_check)
        action_row.addWidget(self._blocked_only_check)
        action_row.addWidget(self._show_json_check)
        for button in (
            self._copy_summary_button,
            self._copy_report_button,
            self._copy_json_button,
            self._export_report_button,
            self._open_repo_button,
            self._open_sdk_button,
            self._open_smoke_button,
        ):
            action_row.addWidget(button)
        action_row.addWidget(self._stale_dir_combo, 1)
        action_row.addWidget(self._open_stale_button)
        action_row.addStretch(1)

        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(self.reject)
        button_box.accepted.connect(self.accept)
        root_layout.addWidget(button_box)

        self._restore_view_state()
        self.refresh()

    def refresh(self) -> None:
        self._payload = collect_repo_health(self._repo_root)
        self._render_details()

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
        self._open_repo_button.setEnabled(bool(repo_root and os.path.isdir(repo_root)))
        self._open_sdk_button.setEnabled(bool(sdk.get("present")) and bool(sdk_path and os.path.isdir(sdk_path)))
        self._open_smoke_button.setEnabled(bool(smoke.get("present")) and bool(smoke_path and os.path.isdir(smoke_path)))
        self._open_stale_button.setEnabled(bool(stale_path and os.path.exists(stale_path)))
        if self._show_json_check.isChecked():
            self._details_edit.setPlainText(format_repo_health_json(view_payload, **view_options))
            return
        self._details_edit.setPlainText(format_repo_health_text(view_payload, **view_options))

    def _open_payload_path(self, key: str, label: str) -> None:
        path = str(self._payload.get(key) or "").strip()
        if not path:
            return
        self._open_path(path, label)

    def _open_nested_payload_path(self, section_key: str, key: str, label: str) -> None:
        section = self._payload.get(section_key)
        if not isinstance(section, dict):
            return
        path = str(section.get(key) or "").strip()
        if not path:
            return
        self._open_path(path, label)

    def _open_path(self, path: str, label: str) -> None:
        if self._open_path_callback is None:
            return
        try:
            self._open_path_callback(path)
        except Exception as exc:
            QMessageBox.warning(self, f"Open {label} Failed", str(exc))

    def _copy_report(self) -> None:
        QApplication.clipboard().setText(self._details_edit.toPlainText())

    def _copy_json(self) -> None:
        view_options = self._view_options()
        view_payload = repo_health_view_payload(self._payload, **view_options)
        QApplication.clipboard().setText(format_repo_health_json(view_payload, **view_options))

    def _copy_summary(self) -> None:
        view_options = self._view_options()
        view_payload = repo_health_view_payload(self._payload, **view_options)
        QApplication.clipboard().setText(format_repo_health_summary(view_payload, **view_options))

    def _selected_stale_path(self) -> str:
        return str(self._stale_dir_combo.currentData() or "").strip()

    def _on_stale_dir_selected(self) -> None:
        self._preferred_stale_path = self._selected_stale_path()
        stale_path = self._selected_stale_path()
        self._open_stale_button.setEnabled(bool(stale_path and os.path.exists(stale_path)))

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
            if not bool(entry.get("accessible", False)):
                issue = str(entry.get("issue") or "blocked")
                label = f"{label} [{issue}]"
            self._stale_dir_combo.addItem(label, path)
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
            if "JSON" in str(selected_filter):
                selected_path = selected_path if os.path.splitext(selected_path)[1] else selected_path + ".json"
            elif "Text" in str(selected_filter):
                selected_path = selected_path if os.path.splitext(selected_path)[1] else selected_path + ".txt"
            resolved_path = os.path.abspath(os.path.normpath(selected_path))
            parent_dir = os.path.dirname(resolved_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
            with open(resolved_path, "w", encoding="utf-8") as f:
                f.write(self._details_edit.toPlainText().rstrip() + "\n")
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
