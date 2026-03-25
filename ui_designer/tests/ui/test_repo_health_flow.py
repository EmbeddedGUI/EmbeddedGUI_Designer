"""GUI tests for repository health workflow wiring."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtWidgets import QApplication, QDialog
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


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    from ui_designer.model.config import DesignerConfig

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_path = config_dir / "config.json"
    monkeypatch.setattr("ui_designer.model.config._get_config_dir", lambda: str(config_dir))
    monkeypatch.setattr("ui_designer.model.config._get_config_path", lambda: str(config_path))
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
    assert f"[repo] {tmp_path}" in copied
    assert "sdk_submodule.initialized: true" in copied


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
    assert '"repo_root"' in dialog._details_edit.toPlainText()
    assert '"sdk_submodule"' in dialog._details_edit.toPlainText()

    QApplication.clipboard().clear()
    dialog._copy_report_button.click()
    copied = QApplication.clipboard().text()
    assert '"repo_root"' in copied
    assert '"sdk_submodule"' in copied


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

    dialog._critical_only_check.setChecked(True)
    focused_text = dialog._details_edit.toPlainText()
    assert "critical: SDK submodule is not initialized" in focused_text
    assert "critical: release smoke sample is missing" in focused_text
    assert "stale_temp_dirs: 0" in focused_text
    assert "If git status is noisy, use: git status -uno" not in focused_text

    dialog._show_json_check.setChecked(True)
    focused_json = dialog._details_edit.toPlainText()
    assert '"critical_issues"' in focused_json
    assert '"stale_temp_dirs": []' in focused_json
