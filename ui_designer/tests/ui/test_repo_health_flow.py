"""GUI tests for repository health workflow wiring."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QApplication, QDialog, QFrame, QLabel
    _has_pyqt5 = True
except ImportError:
    _has_pyqt5 = False


_skip_no_qt = pytest.mark.skipif(not _has_pyqt5, reason="PyQt5 not available")


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
    app.processEvents()
    for widget in list(QApplication.topLevelWidgets()):
        try:
            widget.close()
            widget.deleteLater()
        except Exception:
            pass
    app.processEvents()


def _find_label_by_text(root, text):
    for label in root.findChildren(QLabel):
        if label.text() == text:
            return label
    raise AssertionError(f"Label not found: {text}")


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    from ui_designer.model.config import DesignerConfig

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_path = config_dir / "config.json"
    legacy_config_dir = tmp_path / "legacy_config"
    legacy_config_path = legacy_config_dir / "config.json"
    monkeypatch.setattr("ui_designer.model.config._get_config_dir", lambda: str(config_dir))
    monkeypatch.setattr("ui_designer.model.config._get_config_path", lambda: str(config_path))
    monkeypatch.setattr("ui_designer.model.config._get_legacy_config_dir", lambda: str(legacy_config_dir))
    monkeypatch.setattr("ui_designer.model.config._get_legacy_config_path", lambda: str(legacy_config_path))
    monkeypatch.setattr("ui_designer.model.config._get_load_config_paths", lambda: [str(config_path), str(legacy_config_path)])
    DesignerConfig._instance = None
    config = DesignerConfig.instance()
    yield config
    DesignerConfig._instance = None


@_skip_no_qt
def test_repository_health_action_opens_dialog(qapp, isolated_config, monkeypatch):
    from ui_designer.ui.main_window import MainWindow

    window = MainWindow("")
    captured = {}

    class FakeRepositoryHealthDialog:
        def __init__(self, repo_root, open_path_callback=None, parent=None):
            captured["repo_root"] = repo_root
            captured["open_path_callback"] = open_path_callback
            captured["parent"] = parent

        def exec_(self):
            captured["shown"] = True
            return QDialog.Accepted

    monkeypatch.setattr("ui_designer.ui.main_window.RepositoryHealthDialog", FakeRepositoryHealthDialog)

    window._show_repository_health()

    assert captured["repo_root"]
    assert captured["open_path_callback"] == window._open_path_in_shell
    assert captured["parent"] is window
    assert captured["shown"] is True


@_skip_no_qt
def test_repository_health_dialog_copy_summary_writes_clipboard(qapp, monkeypatch, tmp_path):
    from PyQt5.QtWidgets import QApplication
    from ui_designer.ui.repo_health_dialog import RepositoryHealthDialog

    payload = {
        "repo_root": str(tmp_path),
        "sdk_submodule": {"path": str(tmp_path / "sdk" / "EmbeddedGUI"), "present": True, "initialized": False, "status": "-416d576 sdk/EmbeddedGUI"},
        "release_smoke_project": {"path": str(tmp_path / "samples" / "release_smoke" / "ReleaseSmokeApp"), "present": False},
        "stale_temp_dirs": [{"path": str(tmp_path / ".pytest-tmp-codex"), "accessible": False, "issue": "permission_denied"}],
        "git_status_show_untracked": "no",
        "suggestions": ["Run: git submodule update --init --recursive"],
    }

    monkeypatch.setattr("ui_designer.ui.repo_health_dialog.collect_repo_health", lambda repo_root: payload)

    dialog = RepositoryHealthDialog(str(tmp_path))

    QApplication.clipboard().clear()
    dialog._copy_summary_button.click()

    copied = QApplication.clipboard().text()
    assert "SDK submodule is not initialized; release smoke sample is missing; 1 stale temp dir(s) detected" in copied
    assert "critical=2" in copied
    assert "blocked=1" in copied
    assert "critical_only=false" in copied
    assert "blocked_only=false" in copied

    dialog._critical_only_check.setChecked(True)
    dialog._copy_summary_button.click()
    copied = QApplication.clipboard().text()
    assert "critical_only=true" in copied
    assert "blocked_only=false" in copied
    assert "stale=0" in copied
    assert "blocked=0" in copied


@_skip_no_qt
def test_repository_health_dialog_exposes_accessibility_metadata(qapp, monkeypatch, tmp_path):
    from ui_designer.ui.repo_health_dialog import RepositoryHealthDialog

    payload = {
        "repo_root": str(tmp_path),
        "sdk_submodule": {"path": str(tmp_path / "sdk" / "EmbeddedGUI"), "present": True, "initialized": False, "status": "-416d576 sdk/EmbeddedGUI"},
        "release_smoke_project": {"path": str(tmp_path / "samples" / "release_smoke" / "ReleaseSmokeApp"), "present": False},
        "stale_temp_dirs": [{"path": str(tmp_path / ".pytest-tmp-codex"), "accessible": False, "issue": "permission_denied"}],
        "git_status_show_untracked": "no",
        "suggestions": ["Run: git submodule update --init --recursive"],
    }

    monkeypatch.setattr("ui_designer.ui.repo_health_dialog.collect_repo_health", lambda repo_root: payload)

    dialog = RepositoryHealthDialog(str(tmp_path))

    assert "SDK submodule is not initialized; release smoke sample is missing; 1 stale temp dir(s) detected" in dialog.accessibleName()
    assert "Filters: critical off, blocked off. View: text." in dialog.accessibleName()
    assert dialog._summary_label.accessibleName() == (
        "Repository health summary: SDK submodule is not initialized; release smoke sample is missing; "
        "1 stale temp dir(s) detected"
    )
    assert dialog._summary_label.isHidden()
    assert dialog._overview_label.isHidden()
    assert dialog._overview_label.accessibleName() == (
        "Repository health counts: 2 critical issues, 1 suggestion, 1 stale directory, 1 blocked stale directory."
    )
    assert dialog._details_edit.accessibleName() == "Repository health details: text view. Filters: critical off, blocked off."
    assert dialog._refresh_button.toolTip() == "Refresh repository health, runtime path checks, and stale temp directory scan."
    assert dialog._refresh_button.accessibleName() == "Refresh repository health: text view"
    assert dialog._refresh_button.icon().isNull()
    assert dialog._reset_view_button.toolTip() == "Repository health already shows the full text report."
    assert dialog._reset_view_button.accessibleName() == "Reset repository health view unavailable"
    assert dialog._reset_view_button.icon().isNull()
    assert dialog._critical_only_check.toolTip() == "Filter the report to critical repository health issues."
    assert dialog._blocked_only_check.toolTip() == "Filter the report to stale temp directories blocked by access errors."
    assert dialog._show_json_check.toolTip() == "Show the repository health report as JSON."
    assert dialog._copy_summary_button.icon().isNull()
    assert dialog._export_summary_button.icon().isNull()
    assert dialog._copy_report_button.toolTip() == "Copy the current repository health text report."
    assert dialog._copy_summary_button.accessibleName() == (
        "Copy repository health summary: 2 critical issues, 1 suggestion, 1 stale directory, 1 blocked stale directory"
    )
    assert dialog._export_summary_button.accessibleName() == (
        "Export repository health summary: 2 critical issues, 1 suggestion, 1 stale directory, 1 blocked stale directory"
    )
    assert dialog._copy_report_button.accessibleName() == "Copy repository health text report"
    assert dialog._copy_json_button.accessibleName() == (
        "Copy repository health JSON report: 2 critical issues, 1 suggestion, 1 stale directory, 1 blocked stale directory"
    )
    assert dialog._copy_report_button.icon().isNull()
    assert dialog._copy_json_button.icon().isNull()
    assert dialog._export_report_button.icon().isNull()
    assert dialog._copy_repo_button.toolTip() == "Copy the repository root path."
    assert dialog._copy_repo_button.accessibleName() == "Copy repository root path"
    assert dialog._copy_sdk_button.accessibleName() == "Copy SDK folder path"
    assert dialog._open_repo_button.accessibleName() == "Open repository root"
    assert dialog._open_sdk_button.toolTip() == "The SDK folder path is unavailable or missing."
    assert dialog._open_sdk_button.accessibleName() == "Open SDK folder unavailable"
    assert dialog._open_smoke_button.accessibleName() == "Open release smoke sample unavailable"
    assert dialog._stale_dir_combo.toolTip() == (
        "Select a stale temp directory to copy or open. 1 entry. Current selection: .pytest-tmp-codex [permission_denied]."
    )
    assert dialog._stale_dir_combo.accessibleName() == (
        "Stale temp directories: Select a stale temp directory to copy or open. 1 entry. "
        "Current selection: .pytest-tmp-codex [permission_denied]."
    )
    assert dialog._stale_dir_combo.itemData(0, Qt.ToolTipRole) == (
        f".pytest-tmp-codex [permission_denied]\n{tmp_path / '.pytest-tmp-codex'}"
    )
    assert dialog._stale_dir_combo.itemData(0, Qt.AccessibleTextRole) == (
        f"Stale temp directory: .pytest-tmp-codex [permission_denied]. "
        f"Path: {tmp_path / '.pytest-tmp-codex'}. Issue: permission_denied."
    )
    assert dialog._copy_stale_path_button.accessibleName() == "Copy selected stale temp directory path"
    assert dialog._open_stale_button.accessibleName() == "Open selected stale temp directory unavailable"


@_skip_no_qt
def test_repository_health_header_exposes_workspace_metadata(qapp, monkeypatch, tmp_path):
    from ui_designer.ui.repo_health_dialog import RepositoryHealthDialog

    payload = {
        "repo_root": str(tmp_path),
        "sdk_submodule": {"path": str(tmp_path / "sdk" / "EmbeddedGUI"), "present": True, "initialized": False, "status": "-416d576 sdk/EmbeddedGUI"},
        "release_smoke_project": {"path": str(tmp_path / "samples" / "release_smoke" / "ReleaseSmokeApp"), "present": False},
        "stale_temp_dirs": [{"path": str(tmp_path / ".pytest-tmp-codex"), "accessible": False, "issue": "permission_denied"}],
        "git_status_show_untracked": "no",
        "suggestions": ["Run: git submodule update --init --recursive"],
    }

    monkeypatch.setattr("ui_designer.ui.repo_health_dialog.collect_repo_health", lambda repo_root: payload)

    dialog = RepositoryHealthDialog(str(tmp_path))

    assert dialog._header_frame.accessibleName().startswith("Repository health header. Repository health: ")
    assert dialog._eyebrow_label.isHidden()
    assert dialog._subtitle_label.isHidden()
    assert dialog._summary_label.isHidden()
    assert dialog._overview_label.isHidden()
    assert dialog._eyebrow_label.accessibleName() == "Repository diagnostics workspace."
    assert dialog._title_label.accessibleName() == "Repository health title: Repository Health."
    assert dialog._subtitle_label.accessibleName() == dialog._subtitle_label.text()
    assert _find_label_by_text(
        dialog,
        "Use text view for a compact operator report, or switch to JSON when you need the raw diagnostic payload.",
    ).isHidden()
    assert _find_label_by_text(
        dialog,
        "Refresh diagnostics, reset filtered state, and switch between focused views without leaving this surface.",
    ).isHidden()
    assert _find_label_by_text(
        dialog,
        "Copy or export either the summary line or the full diagnostic report in text or JSON form.",
    ).isHidden()
    assert _find_label_by_text(
        dialog,
        "Jump directly to repository, SDK, and smoke-sample locations without leaving the diagnostics context.",
    ).isHidden()
    assert _find_label_by_text(
        dialog,
        "Inspect directories left behind by prior checks and open or copy the currently selected stale path.",
    ).isHidden()
    assert dialog._critical_metric_value.accessibleName() == "Repository health metric: Critical. 2."
    assert dialog._critical_metric_value._repo_health_metric_label.accessibleName() == "Critical metric label."
    assert dialog._critical_metric_value._repo_health_metric_card.accessibleName() == "Critical metric: 2."
    assert dialog._suggestions_metric_value.accessibleName() == "Repository health metric: Suggestions. 1."
    assert dialog._stale_metric_value.accessibleName() == "Repository health metric: Stale Dirs. 1."
    assert dialog._blocked_metric_value.accessibleName() == "Repository health metric: Blocked. 1."
    assert len(dialog.findChildren(QFrame, "repo_health_metric_card")) == 4


@_skip_no_qt
def test_repository_health_header_hint_skips_no_op_rewrites(qapp, monkeypatch, tmp_path):
    from ui_designer.ui.repo_health_dialog import RepositoryHealthDialog

    payload = {
        "repo_root": str(tmp_path),
        "sdk_submodule": {"path": str(tmp_path / "sdk" / "EmbeddedGUI"), "present": True, "initialized": False, "status": "-416d576 sdk/EmbeddedGUI"},
        "release_smoke_project": {"path": str(tmp_path / "samples" / "release_smoke" / "ReleaseSmokeApp"), "present": False},
        "stale_temp_dirs": [{"path": str(tmp_path / ".pytest-tmp-codex"), "accessible": False, "issue": "permission_denied"}],
        "git_status_show_untracked": "no",
        "suggestions": ["Run: git submodule update --init --recursive"],
    }

    monkeypatch.setattr("ui_designer.ui.repo_health_dialog.collect_repo_health", lambda repo_root: payload)

    dialog = RepositoryHealthDialog(str(tmp_path))
    dialog._header_frame.setProperty("_repo_health_hint_snapshot", None)

    hint_calls = 0
    original_set_tooltip = dialog._header_frame.setToolTip

    def counted_set_tooltip(text):
        nonlocal hint_calls
        hint_calls += 1
        return original_set_tooltip(text)

    monkeypatch.setattr(dialog._header_frame, "setToolTip", counted_set_tooltip)

    dialog._update_accessibility_summary()
    assert hint_calls == 1

    dialog._update_accessibility_summary()
    assert hint_calls == 1

    dialog._critical_only_check.setChecked(True)
    assert hint_calls == 2


@_skip_no_qt
def test_repository_health_header_accessible_name_skips_no_op_rewrites(qapp, monkeypatch, tmp_path):
    from ui_designer.ui.repo_health_dialog import RepositoryHealthDialog

    payload = {
        "repo_root": str(tmp_path),
        "sdk_submodule": {"path": str(tmp_path / "sdk" / "EmbeddedGUI"), "present": True, "initialized": False, "status": "-416d576 sdk/EmbeddedGUI"},
        "release_smoke_project": {"path": str(tmp_path / "samples" / "release_smoke" / "ReleaseSmokeApp"), "present": False},
        "stale_temp_dirs": [{"path": str(tmp_path / ".pytest-tmp-codex"), "accessible": False, "issue": "permission_denied"}],
        "git_status_show_untracked": "no",
        "suggestions": ["Run: git submodule update --init --recursive"],
    }

    monkeypatch.setattr("ui_designer.ui.repo_health_dialog.collect_repo_health", lambda repo_root: payload)

    dialog = RepositoryHealthDialog(str(tmp_path))
    dialog._header_frame.setProperty("_repo_health_accessible_snapshot", None)

    accessible_calls = 0
    original_set_accessible_name = dialog._header_frame.setAccessibleName

    def counted_set_accessible_name(text):
        nonlocal accessible_calls
        accessible_calls += 1
        return original_set_accessible_name(text)

    monkeypatch.setattr(dialog._header_frame, "setAccessibleName", counted_set_accessible_name)

    dialog._update_accessibility_summary()
    assert accessible_calls == 1

    dialog._update_accessibility_summary()
    assert accessible_calls == 1

    dialog._critical_only_check.setChecked(True)
    assert accessible_calls == 2


@_skip_no_qt
def test_repository_health_dialog_can_open_first_stale_dir(qapp, monkeypatch, tmp_path):
    from ui_designer.ui.repo_health_dialog import RepositoryHealthDialog

    stale_dir = tmp_path / ".pytest-tmp-codex"
    stale_dir.mkdir()
    payload = {
        "repo_root": str(tmp_path),
        "sdk_submodule": {"path": str(tmp_path / "sdk" / "EmbeddedGUI"), "present": True, "initialized": True, "status": "416d576 sdk/EmbeddedGUI"},
        "release_smoke_project": {"path": str(tmp_path / "samples" / "release_smoke" / "ReleaseSmokeApp"), "present": True},
        "stale_temp_dirs": [{"path": str(stale_dir), "accessible": False, "issue": "permission_denied"}],
        "git_status_show_untracked": "no",
        "suggestions": [],
    }
    opened_paths = []

    monkeypatch.setattr("ui_designer.ui.repo_health_dialog.collect_repo_health", lambda repo_root: payload)

    dialog = RepositoryHealthDialog(str(tmp_path), open_path_callback=lambda path: opened_paths.append(path))

    assert dialog._stale_dir_combo.currentData() == str(stale_dir)
    assert dialog._open_stale_button.isEnabled() is True
    dialog._open_stale_button.click()

    assert opened_paths == [str(stale_dir)]


@_skip_no_qt
def test_repository_health_dialog_open_buttons_require_existing_paths(qapp, monkeypatch, tmp_path):
    from ui_designer.ui.repo_health_dialog import RepositoryHealthDialog

    payload = {
        "repo_root": str(tmp_path),
        "sdk_submodule": {"path": str(tmp_path / "sdk" / "EmbeddedGUI"), "present": True, "initialized": True, "status": "416d576 sdk/EmbeddedGUI"},
        "release_smoke_project": {"path": str(tmp_path / "samples" / "release_smoke" / "ReleaseSmokeApp"), "present": True},
        "stale_temp_dirs": [],
        "git_status_show_untracked": "no",
        "suggestions": [],
    }

    monkeypatch.setattr("ui_designer.ui.repo_health_dialog.collect_repo_health", lambda repo_root: payload)

    dialog = RepositoryHealthDialog(str(tmp_path))

    assert dialog._copy_repo_button.isEnabled() is True
    assert dialog._copy_sdk_button.isEnabled() is True
    assert dialog._copy_smoke_button.isEnabled() is True
    assert dialog._open_repo_button.isEnabled() is True
    assert dialog._open_sdk_button.isEnabled() is False
    assert dialog._open_smoke_button.isEnabled() is False
    assert dialog._open_stale_button.isEnabled() is False
    assert dialog._copy_repo_button.accessibleName() == "Copy repository root path"
    assert dialog._copy_sdk_button.accessibleName() == "Copy SDK folder path"
    assert dialog._copy_smoke_button.accessibleName() == "Copy release smoke sample path"
    assert dialog._open_repo_button.accessibleName() == "Open repository root"
    assert dialog._open_sdk_button.accessibleName() == "Open SDK folder unavailable"
    assert dialog._open_smoke_button.accessibleName() == "Open release smoke sample unavailable"
    assert dialog._open_stale_button.accessibleName() == "Open selected stale temp directory unavailable"


@_skip_no_qt
def test_repository_health_dialog_can_open_selected_stale_dir(qapp, monkeypatch, tmp_path):
    from ui_designer.ui.repo_health_dialog import RepositoryHealthDialog

    first_stale_dir = tmp_path / ".pytest-tmp-codex"
    second_stale_dir = tmp_path / "tmpxtayw0f6"
    first_stale_dir.mkdir()
    second_stale_dir.mkdir()
    payload = {
        "repo_root": str(tmp_path),
        "sdk_submodule": {"path": str(tmp_path / "sdk" / "EmbeddedGUI"), "present": True, "initialized": True, "status": "416d576 sdk/EmbeddedGUI"},
        "release_smoke_project": {"path": str(tmp_path / "samples" / "release_smoke" / "ReleaseSmokeApp"), "present": True},
        "stale_temp_dirs": [
            {"path": str(first_stale_dir), "accessible": True, "issue": ""},
            {"path": str(second_stale_dir), "accessible": False, "issue": "permission_denied"},
        ],
        "git_status_show_untracked": "no",
        "suggestions": [],
    }
    opened_paths = []

    monkeypatch.setattr("ui_designer.ui.repo_health_dialog.collect_repo_health", lambda repo_root: payload)

    dialog = RepositoryHealthDialog(str(tmp_path), open_path_callback=lambda path: opened_paths.append(path))
    dialog._stale_dir_combo.setCurrentIndex(1)
    dialog._open_stale_button.click()

    assert dialog._stale_dir_combo.currentData() == str(second_stale_dir)
    assert opened_paths == [str(second_stale_dir)]


@_skip_no_qt
def test_repository_health_dialog_updates_open_button_for_selected_stale_dir(qapp, monkeypatch, tmp_path):
    from ui_designer.ui.repo_health_dialog import RepositoryHealthDialog

    existing_stale_dir = tmp_path / ".pytest-tmp-codex"
    missing_stale_dir = tmp_path / "tmpxtayw0f6"
    existing_stale_dir.mkdir()
    payload = {
        "repo_root": str(tmp_path),
        "sdk_submodule": {"path": str(tmp_path / "sdk" / "EmbeddedGUI"), "present": True, "initialized": True, "status": "416d576 sdk/EmbeddedGUI"},
        "release_smoke_project": {"path": str(tmp_path / "samples" / "release_smoke" / "ReleaseSmokeApp"), "present": True},
        "stale_temp_dirs": [
            {"path": str(existing_stale_dir), "accessible": True, "issue": ""},
            {"path": str(missing_stale_dir), "accessible": False, "issue": "permission_denied"},
        ],
        "git_status_show_untracked": "no",
        "suggestions": [],
    }

    monkeypatch.setattr("ui_designer.ui.repo_health_dialog.collect_repo_health", lambda repo_root: payload)

    dialog = RepositoryHealthDialog(str(tmp_path))

    assert dialog._open_stale_button.isEnabled() is True
    dialog._stale_dir_combo.setCurrentIndex(1)
    assert dialog._stale_dir_combo.currentData() == str(missing_stale_dir)
    assert dialog._copy_stale_path_button.isEnabled() is True
    assert dialog._open_stale_button.isEnabled() is False


@_skip_no_qt
def test_repository_health_dialog_updates_accessibility_metadata_for_view_changes(qapp, monkeypatch, tmp_path):
    from ui_designer.ui.repo_health_dialog import RepositoryHealthDialog

    accessible_stale_dir = tmp_path / ".pytest-tmp-codex"
    missing_stale_dir = tmp_path / "tmpxtayw0f6"
    accessible_stale_dir.mkdir()
    payload = {
        "repo_root": str(tmp_path),
        "sdk_submodule": {"path": str(tmp_path / "sdk" / "EmbeddedGUI"), "present": True, "initialized": False, "status": "-416d576 sdk/EmbeddedGUI"},
        "release_smoke_project": {"path": str(tmp_path / "samples" / "release_smoke" / "ReleaseSmokeApp"), "present": False},
        "stale_temp_dirs": [
            {"path": str(accessible_stale_dir), "accessible": True, "issue": ""},
            {"path": str(missing_stale_dir), "accessible": False, "issue": "permission_denied"},
        ],
        "git_status_show_untracked": "no",
        "suggestions": ["Run: git submodule update --init --recursive"],
    }

    monkeypatch.setattr("ui_designer.ui.repo_health_dialog.collect_repo_health", lambda repo_root: payload)

    dialog = RepositoryHealthDialog(str(tmp_path))
    dialog._stale_dir_combo.setCurrentIndex(1)
    qapp.processEvents()

    assert dialog._stale_dir_combo.itemData(0, Qt.AccessibleTextRole) == (
        f"Stale temp directory: .pytest-tmp-codex. Path: {accessible_stale_dir}."
    )
    assert dialog._stale_dir_combo.itemData(1, Qt.AccessibleTextRole) == (
        f"Stale temp directory: tmpxtayw0f6 [permission_denied]. "
        f"Path: {missing_stale_dir}. Issue: permission_denied."
    )
    assert dialog._copy_stale_path_button.toolTip() == "Copy the selected stale temp directory path."
    assert dialog._open_stale_button.toolTip() == "The selected stale temp directory path is unavailable or missing."
    assert dialog._copy_stale_path_button.accessibleName() == "Copy selected stale temp directory path"
    assert dialog._open_stale_button.accessibleName() == "Open selected stale temp directory unavailable"

    dialog._critical_only_check.setChecked(True)
    qapp.processEvents()

    assert dialog._critical_only_check.toolTip() == "Showing only critical repository health issues."
    assert dialog._reset_view_button.toolTip() == "Reset repository health filters, JSON view, and stale-directory selection."
    assert dialog._reset_view_button.accessibleName() == "Reset repository health view"
    assert dialog._stale_dir_combo.toolTip() == "No stale temp directories are available in the current view."
    assert dialog._stale_dir_combo.accessibleName() == (
        "Stale temp directories: No stale temp directories are available in the current view."
    )
    assert dialog._copy_stale_path_button.accessibleName() == "Copy selected stale temp directory path unavailable"
    assert dialog._open_stale_button.accessibleName() == "Open selected stale temp directory unavailable"

    dialog._show_json_check.setChecked(True)
    qapp.processEvents()

    assert dialog._show_json_check.toolTip() == "Showing the repository health report as JSON."
    assert dialog._details_edit.accessibleName() == "Repository health details: JSON view. Filters: critical on, blocked off."
    assert dialog._refresh_button.accessibleName() == "Refresh repository health: JSON view"
    assert dialog._copy_report_button.toolTip() == "Copy the current repository health JSON report."
    assert dialog._copy_report_button.accessibleName() == "Copy repository health JSON report"
    assert "View: JSON." in dialog.accessibleName()


@_skip_no_qt
def test_repository_health_dialog_blocked_only_filters_stale_dirs(qapp, monkeypatch, tmp_path):
    from ui_designer.ui.repo_health_dialog import RepositoryHealthDialog

    accessible_stale_dir = tmp_path / ".pytest-tmp-codex"
    blocked_stale_dir = tmp_path / "tmpxtayw0f6"
    accessible_stale_dir.mkdir()
    blocked_stale_dir.mkdir()
    payload = {
        "repo_root": str(tmp_path),
        "sdk_submodule": {"path": str(tmp_path / "sdk" / "EmbeddedGUI"), "present": True, "initialized": True, "status": "416d576 sdk/EmbeddedGUI"},
        "release_smoke_project": {"path": str(tmp_path / "samples" / "release_smoke" / "ReleaseSmokeApp"), "present": True},
        "stale_temp_dirs": [
            {"path": str(accessible_stale_dir), "accessible": True, "issue": ""},
            {"path": str(blocked_stale_dir), "accessible": False, "issue": "permission_denied"},
        ],
        "git_status_show_untracked": "no",
        "suggestions": [],
    }
    opened_paths = []

    monkeypatch.setattr("ui_designer.ui.repo_health_dialog.collect_repo_health", lambda repo_root: payload)

    dialog = RepositoryHealthDialog(str(tmp_path), open_path_callback=lambda path: opened_paths.append(path))
    dialog._blocked_only_check.setChecked(True)
    filtered_text = dialog._details_edit.toPlainText()

    assert "[view] critical_only=false blocked_only=true" in filtered_text
    assert dialog._summary_label.text() == "1 stale temp dir(s) detected"
    assert dialog._overview_label.text() == "critical 0 | suggestions 3 | stale 1 | blocked 1"
    assert dialog._stale_dir_combo.count() == 1
    assert dialog._stale_dir_combo.currentData() == str(blocked_stale_dir)
    assert str(accessible_stale_dir) not in filtered_text
    assert str(blocked_stale_dir) in filtered_text

    dialog._open_stale_button.click()
    assert opened_paths == [str(blocked_stale_dir)]


@_skip_no_qt
def test_repository_health_dialog_can_copy_selected_stale_path(qapp, monkeypatch, tmp_path):
    from PyQt5.QtWidgets import QApplication
    from ui_designer.ui.repo_health_dialog import RepositoryHealthDialog

    first_stale_dir = tmp_path / ".pytest-tmp-codex"
    missing_stale_dir = tmp_path / "tmpxtayw0f6"
    first_stale_dir.mkdir()
    payload = {
        "repo_root": str(tmp_path),
        "sdk_submodule": {"path": str(tmp_path / "sdk" / "EmbeddedGUI"), "present": True, "initialized": True, "status": "416d576 sdk/EmbeddedGUI"},
        "release_smoke_project": {"path": str(tmp_path / "samples" / "release_smoke" / "ReleaseSmokeApp"), "present": True},
        "stale_temp_dirs": [
            {"path": str(first_stale_dir), "accessible": True, "issue": ""},
            {"path": str(missing_stale_dir), "accessible": False, "issue": "permission_denied"},
        ],
        "git_status_show_untracked": "no",
        "suggestions": [],
    }

    monkeypatch.setattr("ui_designer.ui.repo_health_dialog.collect_repo_health", lambda repo_root: payload)

    dialog = RepositoryHealthDialog(str(tmp_path))
    dialog._stale_dir_combo.setCurrentIndex(1)

    QApplication.clipboard().clear()
    dialog._copy_stale_path_button.click()

    assert QApplication.clipboard().text() == str(missing_stale_dir)


@_skip_no_qt
def test_repository_health_dialog_can_copy_repo_sdk_and_smoke_paths(qapp, monkeypatch, tmp_path):
    from PyQt5.QtWidgets import QApplication
    from ui_designer.ui.repo_health_dialog import RepositoryHealthDialog

    sdk_path = tmp_path / "sdk" / "EmbeddedGUI"
    smoke_path = tmp_path / "samples" / "release_smoke" / "ReleaseSmokeApp"
    payload = {
        "repo_root": str(tmp_path),
        "sdk_submodule": {"path": str(sdk_path), "present": True, "initialized": True, "status": "416d576 sdk/EmbeddedGUI"},
        "release_smoke_project": {"path": str(smoke_path), "present": True},
        "stale_temp_dirs": [],
        "git_status_show_untracked": "no",
        "suggestions": [],
    }

    monkeypatch.setattr("ui_designer.ui.repo_health_dialog.collect_repo_health", lambda repo_root: payload)

    dialog = RepositoryHealthDialog(str(tmp_path))

    QApplication.clipboard().clear()
    dialog._copy_repo_button.click()
    assert QApplication.clipboard().text() == str(tmp_path)

    dialog._copy_sdk_button.click()
    assert QApplication.clipboard().text() == str(sdk_path)

    dialog._copy_smoke_button.click()
    assert QApplication.clipboard().text() == str(smoke_path)


@_skip_no_qt
def test_repository_health_dialog_copy_report_writes_clipboard(qapp, monkeypatch, tmp_path):
    from PyQt5.QtWidgets import QApplication
    from ui_designer.ui.repo_health_dialog import RepositoryHealthDialog

    payload = {
        "repo_root": str(tmp_path),
        "sdk_submodule": {"path": str(tmp_path / "sdk" / "EmbeddedGUI"), "present": True, "initialized": True, "status": "416d576 sdk/EmbeddedGUI"},
        "release_smoke_project": {"path": str(tmp_path / "samples" / "release_smoke" / "ReleaseSmokeApp"), "present": True},
        "stale_temp_dirs": [],
        "git_status_show_untracked": "no",
        "suggestions": [],
    }

    monkeypatch.setattr("ui_designer.ui.repo_health_dialog.collect_repo_health", lambda repo_root: payload)

    dialog = RepositoryHealthDialog(str(tmp_path))

    QApplication.clipboard().clear()
    dialog._copy_report_button.click()

    copied = QApplication.clipboard().text()
    assert "[summary] Repository health looks good." in copied
    assert "[counts] critical=0 suggestions=0 stale=0" in copied
    assert f"[repo] {tmp_path}" in copied
    assert "sdk_submodule.initialized: true" in copied


@_skip_no_qt
def test_repository_health_dialog_copy_json_writes_json_clipboard(qapp, monkeypatch, tmp_path):
    from PyQt5.QtWidgets import QApplication
    from ui_designer.ui.repo_health_dialog import RepositoryHealthDialog

    payload = {
        "repo_root": str(tmp_path),
        "sdk_submodule": {"path": str(tmp_path / "sdk" / "EmbeddedGUI"), "present": True, "initialized": False, "status": "-416d576 sdk/EmbeddedGUI"},
        "release_smoke_project": {"path": str(tmp_path / "samples" / "release_smoke" / "ReleaseSmokeApp"), "present": False},
        "stale_temp_dirs": [{"path": str(tmp_path / ".pytest-tmp-codex"), "accessible": False, "issue": "permission_denied"}],
        "git_status_show_untracked": "no",
        "suggestions": ["Run: git submodule update --init --recursive"],
    }

    monkeypatch.setattr("ui_designer.ui.repo_health_dialog.collect_repo_health", lambda repo_root: payload)

    dialog = RepositoryHealthDialog(str(tmp_path))

    QApplication.clipboard().clear()
    dialog._copy_json_button.click()

    copied = QApplication.clipboard().text()
    assert '"repo_root"' in copied
    assert '"sdk_submodule"' in copied
    assert '"_view": {' in copied
    assert '"critical_only": false' in copied

    dialog._critical_only_check.setChecked(True)
    dialog._copy_json_button.click()
    copied = QApplication.clipboard().text()
    assert '"critical_only": true' in copied
    assert '"blocked_only": false' in copied
    assert '"stale_temp_dirs": []' in copied


@_skip_no_qt
def test_repository_health_dialog_can_switch_to_json_view(qapp, monkeypatch, tmp_path):
    from PyQt5.QtWidgets import QApplication
    from ui_designer.ui.repo_health_dialog import RepositoryHealthDialog

    payload = {
        "repo_root": str(tmp_path),
        "sdk_submodule": {"path": str(tmp_path / "sdk" / "EmbeddedGUI"), "present": True, "initialized": True, "status": "416d576 sdk/EmbeddedGUI"},
        "release_smoke_project": {"path": str(tmp_path / "samples" / "release_smoke" / "ReleaseSmokeApp"), "present": True},
        "stale_temp_dirs": [],
        "git_status_show_untracked": "no",
        "suggestions": [],
    }

    monkeypatch.setattr("ui_designer.ui.repo_health_dialog.collect_repo_health", lambda repo_root: payload)

    dialog = RepositoryHealthDialog(str(tmp_path))

    dialog._show_json_check.setChecked(True)
    assert '"_summary": "Repository health looks good."' in dialog._details_edit.toPlainText()
    assert '"_counts": {' in dialog._details_edit.toPlainText()
    assert '"repo_root"' in dialog._details_edit.toPlainText()
    assert '"sdk_submodule"' in dialog._details_edit.toPlainText()

    QApplication.clipboard().clear()
    dialog._copy_report_button.click()
    copied = QApplication.clipboard().text()
    assert '"_view": {' in copied
    assert '"repo_root"' in copied
    assert '"sdk_submodule"' in copied


@_skip_no_qt
def test_repository_health_dialog_can_reset_view(qapp, monkeypatch, tmp_path):
    from ui_designer.ui.repo_health_dialog import RepositoryHealthDialog

    payload = {
        "repo_root": str(tmp_path),
        "sdk_submodule": {"path": str(tmp_path / "sdk" / "EmbeddedGUI"), "present": True, "initialized": False, "status": "-416d576 sdk/EmbeddedGUI"},
        "release_smoke_project": {"path": str(tmp_path / "samples" / "release_smoke" / "ReleaseSmokeApp"), "present": False},
        "stale_temp_dirs": [{"path": str(tmp_path / ".pytest-tmp-codex"), "accessible": False, "issue": "permission_denied"}],
        "git_status_show_untracked": "no",
        "suggestions": ["Run: git submodule update --init --recursive"],
    }

    monkeypatch.setattr("ui_designer.ui.repo_health_dialog.collect_repo_health", lambda repo_root: payload)

    dialog = RepositoryHealthDialog(str(tmp_path))
    dialog._critical_only_check.setChecked(True)
    dialog._blocked_only_check.setChecked(True)
    dialog._show_json_check.setChecked(True)
    dialog._stale_dir_combo.setCurrentIndex(1)

    dialog._reset_view_button.click()

    assert dialog._critical_only_check.isChecked() is False
    assert dialog._blocked_only_check.isChecked() is False
    assert dialog._show_json_check.isChecked() is False
    assert dialog._stale_dir_combo.currentIndex() == 0
    assert dialog._overview_label.text() == "critical 2 | suggestions 1 | stale 1 | blocked 1"
    assert "[view] critical_only=false blocked_only=false" in dialog._details_edit.toPlainText()


@_skip_no_qt
def test_repository_health_dialog_can_focus_critical_issues(qapp, monkeypatch, tmp_path):
    from ui_designer.ui.repo_health_dialog import RepositoryHealthDialog

    payload = {
        "repo_root": str(tmp_path),
        "sdk_submodule": {"path": str(tmp_path / "sdk" / "EmbeddedGUI"), "present": True, "initialized": False, "status": "-416d576 sdk/EmbeddedGUI"},
        "release_smoke_project": {"path": str(tmp_path / "samples" / "release_smoke" / "ReleaseSmokeApp"), "present": False},
        "stale_temp_dirs": [{"path": str(tmp_path / ".pytest-tmp-codex"), "accessible": False, "issue": "permission_denied"}],
        "git_status_show_untracked": "no",
        "suggestions": [
            "Run: git submodule update --init --recursive",
            "If git status is noisy, use: git status -uno",
        ],
    }

    monkeypatch.setattr("ui_designer.ui.repo_health_dialog.collect_repo_health", lambda repo_root: payload)

    dialog = RepositoryHealthDialog(str(tmp_path))
    assert dialog._overview_label.text() == "critical 2 | suggestions 2 | stale 1 | blocked 1"

    dialog._critical_only_check.setChecked(True)
    focused_text = dialog._details_edit.toPlainText()
    assert "[view] critical_only=true blocked_only=false" in focused_text
    assert dialog._overview_label.text() == "critical 2 | suggestions 2 | stale 0 | blocked 0"
    assert dialog._summary_label.text() == "SDK submodule is not initialized; release smoke sample is missing"
    assert "critical: SDK submodule is not initialized" in focused_text
    assert "critical: release smoke sample is missing" in focused_text
    assert "stale_temp_dirs: 0 (blocked 0)" in focused_text
    assert "If git status is noisy, use: git status -uno" not in focused_text

    dialog._show_json_check.setChecked(True)
    focused_json = dialog._details_edit.toPlainText()
    assert '"_view": {' in focused_json
    assert '"critical_issues"' in focused_json
    assert '"stale_temp_dirs": []' in focused_json


@_skip_no_qt
def test_repository_health_dialog_exports_current_text_view(qapp, monkeypatch, tmp_path):
    from ui_designer.ui.repo_health_dialog import RepositoryHealthDialog

    payload = {
        "repo_root": str(tmp_path),
        "sdk_submodule": {"path": str(tmp_path / "sdk" / "EmbeddedGUI"), "present": True, "initialized": True, "status": "416d576 sdk/EmbeddedGUI"},
        "release_smoke_project": {"path": str(tmp_path / "samples" / "release_smoke" / "ReleaseSmokeApp"), "present": True},
        "stale_temp_dirs": [],
        "git_status_show_untracked": "no",
        "suggestions": [],
    }
    export_path = tmp_path / "repo-health.txt"
    captured = {}

    monkeypatch.setattr("ui_designer.ui.repo_health_dialog.collect_repo_health", lambda repo_root: payload)
    monkeypatch.setattr(
        "ui_designer.ui.repo_health_dialog.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: (
            captured.setdefault("default_name", args[2]) and str(export_path),
            "Text Files (*.txt)",
        ),
    )

    dialog = RepositoryHealthDialog(str(tmp_path))
    dialog._export_report_button.click()

    exported = export_path.read_text(encoding="utf-8")
    assert captured["default_name"] == "repo-health.txt"
    assert "[summary] Repository health looks good." in exported
    assert f"[repo] {tmp_path}" in exported
    assert "sdk_submodule.initialized: true" in exported


@_skip_no_qt
def test_repository_health_dialog_exports_summary(qapp, monkeypatch, tmp_path):
    from ui_designer.ui.repo_health_dialog import RepositoryHealthDialog

    payload = {
        "repo_root": str(tmp_path),
        "sdk_submodule": {"path": str(tmp_path / "sdk" / "EmbeddedGUI"), "present": True, "initialized": False, "status": "-416d576 sdk/EmbeddedGUI"},
        "release_smoke_project": {"path": str(tmp_path / "samples" / "release_smoke" / "ReleaseSmokeApp"), "present": False},
        "stale_temp_dirs": [{"path": str(tmp_path / ".pytest-tmp-codex"), "accessible": False, "issue": "permission_denied"}],
        "git_status_show_untracked": "no",
        "suggestions": ["Run: git submodule update --init --recursive"],
    }
    export_path = tmp_path / "repo-health-summary.txt"
    captured = {}

    monkeypatch.setattr("ui_designer.ui.repo_health_dialog.collect_repo_health", lambda repo_root: payload)
    monkeypatch.setattr(
        "ui_designer.ui.repo_health_dialog.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: (
            captured.setdefault("default_name", args[2]) and str(export_path),
            "Text Files (*.txt)",
        ),
    )

    dialog = RepositoryHealthDialog(str(tmp_path))
    dialog._critical_only_check.setChecked(True)
    dialog._export_summary_button.click()

    exported = export_path.read_text(encoding="utf-8")
    assert captured["default_name"] == "repo-health-summary-critical.txt"
    assert "SDK submodule is not initialized; release smoke sample is missing" in exported
    assert "critical=2" in exported
    assert "blocked_only=false" in exported


@_skip_no_qt
def test_repository_health_dialog_export_summary_appends_txt_suffix(qapp, monkeypatch, tmp_path):
    from ui_designer.ui.repo_health_dialog import RepositoryHealthDialog

    payload = {
        "repo_root": str(tmp_path),
        "sdk_submodule": {"path": str(tmp_path / "sdk" / "EmbeddedGUI"), "present": True, "initialized": True, "status": "416d576 sdk/EmbeddedGUI"},
        "release_smoke_project": {"path": str(tmp_path / "samples" / "release_smoke" / "ReleaseSmokeApp"), "present": True},
        "stale_temp_dirs": [],
        "git_status_show_untracked": "no",
        "suggestions": [],
    }
    export_path = tmp_path / "repo-health-summary"

    monkeypatch.setattr("ui_designer.ui.repo_health_dialog.collect_repo_health", lambda repo_root: payload)
    monkeypatch.setattr(
        "ui_designer.ui.repo_health_dialog.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: (str(export_path), "Text Files (*.txt)"),
    )

    dialog = RepositoryHealthDialog(str(tmp_path))
    dialog._export_summary_button.click()

    exported = (tmp_path / "repo-health-summary.txt").read_text(encoding="utf-8")
    assert "Repository health looks good." in exported
    assert "critical=0" in exported


@_skip_no_qt
def test_repository_health_dialog_export_uses_selected_json_format(qapp, monkeypatch, tmp_path):
    from ui_designer.ui.repo_health_dialog import RepositoryHealthDialog

    payload = {
        "repo_root": str(tmp_path),
        "sdk_submodule": {"path": str(tmp_path / "sdk" / "EmbeddedGUI"), "present": True, "initialized": True, "status": "416d576 sdk/EmbeddedGUI"},
        "release_smoke_project": {"path": str(tmp_path / "samples" / "release_smoke" / "ReleaseSmokeApp"), "present": True},
        "stale_temp_dirs": [],
        "git_status_show_untracked": "no",
        "suggestions": [],
    }
    export_path = tmp_path / "repo-health-report"

    monkeypatch.setattr("ui_designer.ui.repo_health_dialog.collect_repo_health", lambda repo_root: payload)
    monkeypatch.setattr(
        "ui_designer.ui.repo_health_dialog.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: (str(export_path), "JSON Files (*.json)"),
    )

    dialog = RepositoryHealthDialog(str(tmp_path))
    dialog._show_json_check.setChecked(False)
    dialog._export_report_button.click()

    exported = (tmp_path / "repo-health-report.json").read_text(encoding="utf-8")
    assert '"_summary": "Repository health looks good."' in exported
    assert '"_view": {' in exported


@_skip_no_qt
def test_repository_health_dialog_exports_current_json_view(qapp, monkeypatch, tmp_path):
    from ui_designer.ui.repo_health_dialog import RepositoryHealthDialog

    payload = {
        "repo_root": str(tmp_path),
        "sdk_submodule": {"path": str(tmp_path / "sdk" / "EmbeddedGUI"), "present": True, "initialized": True, "status": "416d576 sdk/EmbeddedGUI"},
        "release_smoke_project": {"path": str(tmp_path / "samples" / "release_smoke" / "ReleaseSmokeApp"), "present": True},
        "stale_temp_dirs": [],
        "git_status_show_untracked": "no",
        "suggestions": [],
    }
    export_path = tmp_path / "repo-health.json"
    captured = {}

    monkeypatch.setattr("ui_designer.ui.repo_health_dialog.collect_repo_health", lambda repo_root: payload)
    monkeypatch.setattr(
        "ui_designer.ui.repo_health_dialog.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: (
            captured.setdefault("default_name", args[2]) and str(export_path),
            "JSON Files (*.json)",
        ),
    )

    dialog = RepositoryHealthDialog(str(tmp_path))
    dialog._show_json_check.setChecked(True)
    dialog._export_report_button.click()

    exported = export_path.read_text(encoding="utf-8")
    assert captured["default_name"] == "repo-health.json"
    assert '"_summary": "Repository health looks good."' in exported
    assert '"repo_root"' in exported
    assert '"sdk_submodule"' in exported


@_skip_no_qt
def test_repository_health_dialog_export_uses_selected_text_format(qapp, monkeypatch, tmp_path):
    from ui_designer.ui.repo_health_dialog import RepositoryHealthDialog

    payload = {
        "repo_root": str(tmp_path),
        "sdk_submodule": {"path": str(tmp_path / "sdk" / "EmbeddedGUI"), "present": True, "initialized": True, "status": "416d576 sdk/EmbeddedGUI"},
        "release_smoke_project": {"path": str(tmp_path / "samples" / "release_smoke" / "ReleaseSmokeApp"), "present": True},
        "stale_temp_dirs": [],
        "git_status_show_untracked": "no",
        "suggestions": [],
    }
    export_path = tmp_path / "repo-health-report"

    monkeypatch.setattr("ui_designer.ui.repo_health_dialog.collect_repo_health", lambda repo_root: payload)
    monkeypatch.setattr(
        "ui_designer.ui.repo_health_dialog.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: (str(export_path), "Text Files (*.txt)"),
    )

    dialog = RepositoryHealthDialog(str(tmp_path))
    dialog._show_json_check.setChecked(True)
    dialog._export_report_button.click()

    exported = (tmp_path / "repo-health-report.txt").read_text(encoding="utf-8")
    assert "[summary] Repository health looks good." in exported
    assert '"_summary": "Repository health looks good."' not in exported


@_skip_no_qt
def test_repository_health_dialog_export_appends_selected_suffix(qapp, monkeypatch, tmp_path):
    from ui_designer.ui.repo_health_dialog import RepositoryHealthDialog

    payload = {
        "repo_root": str(tmp_path),
        "sdk_submodule": {"path": str(tmp_path / "sdk" / "EmbeddedGUI"), "present": True, "initialized": True, "status": "416d576 sdk/EmbeddedGUI"},
        "release_smoke_project": {"path": str(tmp_path / "samples" / "release_smoke" / "ReleaseSmokeApp"), "present": True},
        "stale_temp_dirs": [],
        "git_status_show_untracked": "no",
        "suggestions": [],
    }
    export_path = tmp_path / "repo-health"

    monkeypatch.setattr("ui_designer.ui.repo_health_dialog.collect_repo_health", lambda repo_root: payload)
    monkeypatch.setattr(
        "ui_designer.ui.repo_health_dialog.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: (str(export_path), "JSON Files (*.json)"),
    )

    dialog = RepositoryHealthDialog(str(tmp_path))
    dialog._show_json_check.setChecked(True)
    dialog._export_report_button.click()

    exported = (tmp_path / "repo-health.json").read_text(encoding="utf-8")
    assert '"_summary": "Repository health looks good."' in exported


@_skip_no_qt
def test_repository_health_dialog_export_filename_tracks_critical_json_state(qapp, monkeypatch, tmp_path):
    from ui_designer.ui.repo_health_dialog import RepositoryHealthDialog

    payload = {
        "repo_root": str(tmp_path),
        "sdk_submodule": {"path": str(tmp_path / "sdk" / "EmbeddedGUI"), "present": True, "initialized": False, "status": "-416d576 sdk/EmbeddedGUI"},
        "release_smoke_project": {"path": str(tmp_path / "samples" / "release_smoke" / "ReleaseSmokeApp"), "present": False},
        "stale_temp_dirs": [],
        "git_status_show_untracked": "no",
        "suggestions": [],
    }

    monkeypatch.setattr("ui_designer.ui.repo_health_dialog.collect_repo_health", lambda repo_root: payload)

    dialog = RepositoryHealthDialog(str(tmp_path))
    dialog._critical_only_check.setChecked(True)
    dialog._blocked_only_check.setChecked(True)
    dialog._show_json_check.setChecked(True)

    assert dialog._default_export_filename() == "repo-health-critical-blocked.json"


@_skip_no_qt
def test_repository_health_dialog_restores_saved_view_state(qapp, isolated_config, monkeypatch, tmp_path):
    from ui_designer.ui.repo_health_dialog import RepositoryHealthDialog

    payload = {
        "repo_root": str(tmp_path),
        "sdk_submodule": {"path": str(tmp_path / "sdk" / "EmbeddedGUI"), "present": True, "initialized": False, "status": "-416d576 sdk/EmbeddedGUI"},
        "release_smoke_project": {"path": str(tmp_path / "samples" / "release_smoke" / "ReleaseSmokeApp"), "present": False},
        "stale_temp_dirs": [],
        "git_status_show_untracked": "no",
        "suggestions": [],
    }

    monkeypatch.setattr("ui_designer.ui.repo_health_dialog.collect_repo_health", lambda repo_root: payload)

    dialog = RepositoryHealthDialog(str(tmp_path))
    dialog._critical_only_check.setChecked(True)
    dialog._blocked_only_check.setChecked(True)
    dialog._show_json_check.setChecked(True)
    dialog.done(QDialog.Accepted)

    restored = RepositoryHealthDialog(str(tmp_path))

    assert restored._critical_only_check.isChecked() is True
    assert restored._blocked_only_check.isChecked() is True
    assert restored._show_json_check.isChecked() is True
    assert '"critical_issues"' in restored._details_edit.toPlainText()


@_skip_no_qt
def test_repository_health_dialog_restores_selected_stale_dir(qapp, isolated_config, monkeypatch, tmp_path):
    from ui_designer.ui.repo_health_dialog import RepositoryHealthDialog

    first_stale_dir = tmp_path / ".pytest-tmp-codex"
    second_stale_dir = tmp_path / "tmpxtayw0f6"
    first_stale_dir.mkdir()
    second_stale_dir.mkdir()
    payload = {
        "repo_root": str(tmp_path),
        "sdk_submodule": {"path": str(tmp_path / "sdk" / "EmbeddedGUI"), "present": True, "initialized": True, "status": "416d576 sdk/EmbeddedGUI"},
        "release_smoke_project": {"path": str(tmp_path / "samples" / "release_smoke" / "ReleaseSmokeApp"), "present": True},
        "stale_temp_dirs": [
            {"path": str(first_stale_dir), "accessible": True, "issue": ""},
            {"path": str(second_stale_dir), "accessible": False, "issue": "permission_denied"},
        ],
        "git_status_show_untracked": "no",
        "suggestions": [],
    }

    monkeypatch.setattr("ui_designer.ui.repo_health_dialog.collect_repo_health", lambda repo_root: payload)

    dialog = RepositoryHealthDialog(str(tmp_path))
    dialog._stale_dir_combo.setCurrentIndex(1)
    dialog.done(QDialog.Accepted)

    restored = RepositoryHealthDialog(str(tmp_path))

    assert restored._stale_dir_combo.currentData() == str(second_stale_dir)
