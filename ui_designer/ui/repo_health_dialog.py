"""Repository health dialog for inspecting local workspace state."""

from __future__ import annotations

from pathlib import Path

from PyQt5.QtWidgets import QApplication, QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QMessageBox, QPushButton, QTextEdit, QVBoxLayout

from ..model.repo_health import collect_repo_health, format_repo_health_text, summarize_repo_health


class RepositoryHealthDialog(QDialog):
    """Inspect repository health and open relevant workspace paths."""

    def __init__(self, repo_root: str, open_path_callback=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Repository Health")
        self.resize(920, 520)
        self._repo_root = str(Path(repo_root).resolve())
        self._open_path_callback = open_path_callback
        self._payload: dict[str, object] = {}

        root_layout = QVBoxLayout(self)

        self._summary_label = QLabel()
        self._summary_label.setWordWrap(True)
        root_layout.addWidget(self._summary_label)

        self._details_edit = QTextEdit()
        self._details_edit.setReadOnly(True)
        root_layout.addWidget(self._details_edit, 1)

        action_row = QHBoxLayout()
        root_layout.addLayout(action_row)

        self._refresh_button = QPushButton("Refresh")
        self._copy_report_button = QPushButton("Copy Report")
        self._open_repo_button = QPushButton("Open Repo")
        self._open_sdk_button = QPushButton("Open SDK")
        self._open_smoke_button = QPushButton("Open Smoke Sample")

        self._refresh_button.clicked.connect(self.refresh)
        self._copy_report_button.clicked.connect(self._copy_report)
        self._open_repo_button.clicked.connect(lambda: self._open_payload_path("repo_root", "Repository Root"))
        self._open_sdk_button.clicked.connect(lambda: self._open_nested_payload_path("sdk_submodule", "path", "SDK Folder"))
        self._open_smoke_button.clicked.connect(lambda: self._open_nested_payload_path("release_smoke_project", "path", "Smoke Project"))

        for button in (self._refresh_button, self._copy_report_button, self._open_repo_button, self._open_sdk_button, self._open_smoke_button):
            action_row.addWidget(button)
        action_row.addStretch(1)

        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(self.reject)
        button_box.accepted.connect(self.accept)
        root_layout.addWidget(button_box)

        self.refresh()

    def refresh(self) -> None:
        self._payload = collect_repo_health(self._repo_root)
        self._summary_label.setText(summarize_repo_health(self._payload))
        self._details_edit.setPlainText(format_repo_health_text(self._payload))

        sdk = self._payload.get("sdk_submodule") if isinstance(self._payload.get("sdk_submodule"), dict) else {}
        smoke = self._payload.get("release_smoke_project") if isinstance(self._payload.get("release_smoke_project"), dict) else {}
        self._open_repo_button.setEnabled(bool(self._payload.get("repo_root")))
        self._open_sdk_button.setEnabled(bool(sdk.get("path")))
        self._open_smoke_button.setEnabled(bool(smoke.get("present")) and bool(smoke.get("path")))

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
