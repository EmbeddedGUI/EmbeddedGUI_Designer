"""GUI tests for repository health workflow wiring."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtWidgets import QApplication, QDialog, QLabel

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


def _payload(
    tmp_path,
    *,
    sdk_initialized: bool = True,
    stale_temp_dirs: list[dict[str, object]] | None = None,
    suggestions: list[str] | None = None,
    sdk_path: str | None = None,
) -> dict[str, object]:
    return {
        "repo_root": str(tmp_path),
        "sdk_submodule": {
            "path": sdk_path or str(tmp_path / "sdk" / "EmbeddedGUI"),
            "present": True,
            "initialized": sdk_initialized,
            "status": "416d576 sdk/EmbeddedGUI" if sdk_initialized else "-416d576 sdk/EmbeddedGUI",
        },
        "runtime_paths": {},
        "stale_temp_dirs": stale_temp_dirs or [],
        "git_status_show_untracked": "no",
        "suggestions": suggestions or [],
    }


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
def test_repository_health_dialog_copies_summary_and_filters_critical(qapp, monkeypatch, tmp_path):
    from PyQt5.QtWidgets import QApplication

    from ui_designer.ui.repo_health_dialog import RepositoryHealthDialog

    payload = _payload(
        tmp_path,
        sdk_initialized=False,
        stale_temp_dirs=[{"path": str(tmp_path / ".pytest-tmp-codex"), "accessible": False, "issue": "permission_denied"}],
        suggestions=["Run: git submodule update --init --recursive"],
    )

    monkeypatch.setattr("ui_designer.ui.repo_health_dialog.collect_repo_health", lambda repo_root: payload)

    dialog = RepositoryHealthDialog(str(tmp_path))

    QApplication.clipboard().clear()
    dialog._copy_summary_button.click()
    copied = QApplication.clipboard().text()
    assert "SDK submodule is not initialized; 1 stale temp dir(s) detected" in copied
    assert "critical=1" in copied
    assert "blocked=1" in copied
    assert "critical_only=false" in copied

    dialog._critical_only_check.setChecked(True)
    dialog._copy_summary_button.click()
    copied = QApplication.clipboard().text()
    assert "SDK submodule is not initialized" in copied
    assert "stale=0" in copied
    assert "blocked=0" in copied
    assert "critical_only=true" in copied


@_skip_no_qt
def test_repository_health_dialog_exposes_current_metadata(qapp, monkeypatch, tmp_path):
    from ui_designer.ui.repo_health_dialog import RepositoryHealthDialog

    payload = _payload(
        tmp_path,
        sdk_initialized=False,
        stale_temp_dirs=[{"path": str(tmp_path / ".pytest-tmp-codex"), "accessible": False, "issue": "permission_denied"}],
        suggestions=["Run: git submodule update --init --recursive"],
    )

    monkeypatch.setattr("ui_designer.ui.repo_health_dialog.collect_repo_health", lambda repo_root: payload)

    dialog = RepositoryHealthDialog(str(tmp_path))

    assert not hasattr(dialog, "_copy_smoke_button")
    assert not hasattr(dialog, "_open_smoke_button")
    assert "SDK submodule is not initialized; 1 stale temp dir(s) detected" in dialog.accessibleName()
    assert "Filters: critical off, blocked off. View: text." in dialog.accessibleName()
    assert dialog._summary_label.accessibleName() == "Repository health summary: SDK submodule is not initialized; 1 stale temp dir(s) detected"
    assert dialog._overview_label.accessibleName() == (
        "Repository health counts: 1 critical issue, 1 suggestion, 1 stale directory, 1 blocked stale directory."
    )
    assert dialog._refresh_button.toolTip() == "Refresh repository health, runtime path checks, and stale temp directory scan."
    assert dialog._reset_view_button.toolTip() == "Repository health already shows the full text report."
    assert dialog._copy_repo_button.accessibleName() == "Copy repository root path"
    assert dialog._copy_sdk_button.accessibleName() == "Copy SDK folder path"
    assert dialog._open_sdk_button.accessibleName() == "Open SDK folder unavailable"
    assert dialog._stale_dir_combo.toolTip() == (
        "Select a stale temp directory to copy or open. 1 entry. Current selection: .pytest-tmp-codex [permission_denied]."
    )
    assert dialog._copy_stale_path_button.accessibleName() == "Copy selected stale temp directory path"
    assert dialog._open_stale_button.accessibleName() == "Open selected stale temp directory unavailable"
    assert _find_label_by_text(dialog, "Paths") is not None
    assert _find_label_by_text(
        dialog,
        "Jump directly to repository and SDK locations without leaving the diagnostics context.",
    ).isHidden()


@_skip_no_qt
def test_repository_health_dialog_can_open_selected_stale_dir(qapp, monkeypatch, tmp_path):
    from ui_designer.ui.repo_health_dialog import RepositoryHealthDialog

    stale_dir = tmp_path / ".pytest-tmp-codex"
    stale_dir.mkdir()
    payload = _payload(
        tmp_path,
        stale_temp_dirs=[{"path": str(stale_dir), "accessible": False, "issue": "permission_denied"}],
    )
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

    payload = _payload(
        tmp_path,
        sdk_path=str(tmp_path / "missing-sdk" / "EmbeddedGUI"),
    )

    monkeypatch.setattr("ui_designer.ui.repo_health_dialog.collect_repo_health", lambda repo_root: payload)

    dialog = RepositoryHealthDialog(str(tmp_path))

    assert dialog._copy_repo_button.isEnabled() is True
    assert dialog._copy_sdk_button.isEnabled() is True
    assert dialog._open_repo_button.isEnabled() is True
    assert dialog._open_sdk_button.isEnabled() is False
    assert dialog._copy_stale_path_button.isEnabled() is False
    assert dialog._open_stale_button.isEnabled() is False
    assert not hasattr(dialog, "_copy_smoke_button")
    assert not hasattr(dialog, "_open_smoke_button")


@_skip_no_qt
def test_repository_health_dialog_can_switch_to_json_view_and_reset(qapp, monkeypatch, tmp_path):
    from PyQt5.QtWidgets import QApplication

    from ui_designer.ui.repo_health_dialog import RepositoryHealthDialog

    first_stale = tmp_path / ".pytest-tmp-codex"
    second_stale = tmp_path / "tmpxtayw0f6"
    payload = _payload(
        tmp_path,
        sdk_initialized=False,
        stale_temp_dirs=[
            {"path": str(first_stale), "accessible": True, "issue": ""},
            {"path": str(second_stale), "accessible": False, "issue": "permission_denied"},
        ],
        suggestions=["Run: git submodule update --init --recursive"],
    )

    monkeypatch.setattr("ui_designer.ui.repo_health_dialog.collect_repo_health", lambda repo_root: payload)

    dialog = RepositoryHealthDialog(str(tmp_path))

    dialog._blocked_only_check.setChecked(True)
    dialog._show_json_check.setChecked(True)
    assert '"_view": {' in dialog._details_edit.toPlainText()
    assert '"blocked_only": true' in dialog._details_edit.toPlainText()

    QApplication.clipboard().clear()
    dialog._copy_json_button.click()
    copied = QApplication.clipboard().text()
    assert '"repo_root"' in copied
    assert '"sdk_submodule"' in copied
    assert '"blocked_only": true' in copied

    dialog._reset_view_button.click()
    assert dialog._blocked_only_check.isChecked() is False
    assert dialog._show_json_check.isChecked() is False
    assert dialog._overview_label.text() == "critical 1 | suggestions 1 | stale 2 | blocked 1"
    assert "[view] critical_only=false blocked_only=false" in dialog._details_edit.toPlainText()


@_skip_no_qt
def test_repository_health_dialog_exports_summary(qapp, monkeypatch, tmp_path):
    from ui_designer.ui.repo_health_dialog import RepositoryHealthDialog

    payload = _payload(
        tmp_path,
        sdk_initialized=False,
        suggestions=["Run: git submodule update --init --recursive"],
    )
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
    assert "SDK submodule is not initialized" in exported
    assert "critical=1" in exported
    assert "blocked_only=false" in exported


@_skip_no_qt
def test_repository_health_dialog_exports_current_report_format(qapp, monkeypatch, tmp_path):
    from ui_designer.ui.repo_health_dialog import RepositoryHealthDialog

    payload = _payload(tmp_path)
    export_path = tmp_path / "repo-health-report"

    monkeypatch.setattr("ui_designer.ui.repo_health_dialog.collect_repo_health", lambda repo_root: payload)
    monkeypatch.setattr(
        "ui_designer.ui.repo_health_dialog.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: (str(export_path), "JSON Files (*.json)"),
    )

    dialog = RepositoryHealthDialog(str(tmp_path))
    dialog._show_json_check.setChecked(True)
    dialog._export_report_button.click()

    exported = (tmp_path / "repo-health-report.json").read_text(encoding="utf-8")
    assert '"_summary": "Repository health looks good."' in exported
    assert '"repo_root"' in exported
    assert '"sdk_submodule"' in exported


@_skip_no_qt
def test_repository_health_dialog_restores_saved_view_state(qapp, isolated_config, monkeypatch, tmp_path):
    from ui_designer.ui.repo_health_dialog import RepositoryHealthDialog

    payload = _payload(
        tmp_path,
        sdk_initialized=False,
        suggestions=["Run: git submodule update --init --recursive"],
    )

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
    payload = _payload(
        tmp_path,
        stale_temp_dirs=[
            {"path": str(first_stale_dir), "accessible": True, "issue": ""},
            {"path": str(second_stale_dir), "accessible": False, "issue": "permission_denied"},
        ],
    )

    monkeypatch.setattr("ui_designer.ui.repo_health_dialog.collect_repo_health", lambda repo_root: payload)

    dialog = RepositoryHealthDialog(str(tmp_path))
    dialog._stale_dir_combo.setCurrentIndex(1)
    dialog.done(QDialog.Accepted)

    restored = RepositoryHealthDialog(str(tmp_path))

    assert restored._stale_dir_combo.currentData() == str(second_stale_dir)
