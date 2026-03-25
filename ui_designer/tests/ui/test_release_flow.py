"""GUI tests for release workflow wiring."""

from __future__ import annotations

import os
from pathlib import Path

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


def _create_sdk_root(root: Path):
    (root / "src").mkdir(parents=True)
    (root / "porting" / "designer").mkdir(parents=True)
    (root / "Makefile").write_text("all:\n", encoding="utf-8")


class _DisabledCompiler:
    def can_build(self):
        return False

    def is_preview_running(self):
        return False

    def stop_exe(self):
        return None

    def cleanup(self):
        return None

    def get_build_error(self):
        return "preview disabled for test"

    def set_screen_size(self, width, height):
        return None


@_skip_no_qt
def test_release_build_action_uses_release_engine(qapp, isolated_config, tmp_path, monkeypatch):
    from ui_designer.model.project import Project
    from ui_designer.model.release import ReleaseArtifact, ReleaseResult
    from ui_designer.ui.main_window import MainWindow

    sdk_root = tmp_path / "sdk"
    project_dir = sdk_root / "example" / "ReleaseDemo"
    _create_sdk_root(sdk_root)
    project_dir.mkdir(parents=True)

    project = Project(app_name="ReleaseDemo")
    project.sdk_root = str(sdk_root)
    project.project_dir = str(project_dir)
    project.create_new_page("main_page")
    project.save(str(project_dir))

    window = MainWindow(str(sdk_root))
    monkeypatch.setattr(window, "_trigger_compile", lambda: None)
    monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
    window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)

    class FakeDialog:
        def __init__(self, *args, **kwargs):
            self.selected_profile_id = "windows-pc"
            self.warnings_as_errors = False
            self.package_release = False

        def exec_(self):
            return QDialog.Accepted

    captured = {}

    def fake_release_project(request):
        captured["profile_id"] = request.profile.id
        captured["sdk_root"] = request.sdk_root
        return ReleaseResult(
            success=True,
            message="Release created",
            build_id="20260325T000000Z",
            profile_id=request.profile.id,
            release_root=str(project_dir / "output" / "ui_designer_release"),
            dist_dir=str(project_dir / "output" / "ui_designer_release" / "dist"),
            manifest_path=str(project_dir / "output" / "ui_designer_release" / "release-manifest.json"),
            log_path=str(project_dir / "output" / "ui_designer_release" / "logs" / "build.log"),
            history_path=str(project_dir / "output" / "ui_designer_release" / "history.json"),
            artifacts=[ReleaseArtifact(path="dist/ReleaseDemo.exe", sha256="abc")],
        )

    monkeypatch.setattr("ui_designer.ui.main_window.ReleaseBuildDialog", FakeDialog)
    monkeypatch.setattr("ui_designer.ui.main_window.release_project", fake_release_project)
    monkeypatch.setattr(window, "_save_project", lambda: None)
    monkeypatch.setattr("ui_designer.ui.main_window.QMessageBox.information", lambda *args, **kwargs: None)

    window._release_build()

    assert captured["profile_id"] == "windows-pc"
    assert captured["sdk_root"] == os.path.normpath(os.path.abspath(sdk_root))
    assert window._release_build_action.isEnabled() is True
    assert window._sdk_status_label.text().startswith("SDK:")


@_skip_no_qt
def test_release_history_action_opens_dialog(qapp, isolated_config, tmp_path, monkeypatch):
    from ui_designer.model.project import Project
    from ui_designer.ui.main_window import MainWindow

    sdk_root = tmp_path / "sdk"
    project_dir = sdk_root / "example" / "ReleaseDemo"
    _create_sdk_root(sdk_root)
    project_dir.mkdir(parents=True)

    project = Project(app_name="ReleaseDemo")
    project.sdk_root = str(sdk_root)
    project.project_dir = str(project_dir)
    project.create_new_page("main_page")
    project.save(str(project_dir))

    window = MainWindow(str(sdk_root))
    monkeypatch.setattr(window, "_trigger_compile", lambda: None)
    monkeypatch.setattr(window, "_recreate_compiler", lambda: setattr(window, "compiler", _DisabledCompiler()))
    window._open_loaded_project(project, str(project_dir), preferred_sdk_root=str(sdk_root), silent=True)

    captured = {}
    history_entry = {
        "build_id": "20260326T000000Z",
        "status": "success",
        "profile_id": "windows-pc",
        "app_name": "ReleaseDemo",
        "created_at_utc": "2026-03-26T00:00:00Z",
        "designer_revision": "designer@abc1234",
        "sdk": {"revision": "v1.0.0-310-g416d576", "commit": "416d5766100ab935e7d5197ce296370a6ad966a7"},
        "release_root": str(project_dir / "output" / "ui_designer_release" / "windows-pc" / "20260326T000000Z"),
        "manifest_path": str(project_dir / "output" / "ui_designer_release" / "windows-pc" / "20260326T000000Z" / "release-manifest.json"),
        "log_path": str(project_dir / "output" / "ui_designer_release" / "windows-pc" / "20260326T000000Z" / "logs" / "build.log"),
        "zip_path": str(project_dir / "output" / "ui_designer_release" / "windows-pc" / "20260326T000000Z" / "dist.zip"),
        "message": "Release created",
    }

    def fake_load_release_history(project_dir_arg, output_dir=""):
        captured["project_dir"] = project_dir_arg
        captured["output_dir"] = output_dir
        return [history_entry]

    class FakeHistoryDialog:
        def __init__(self, history_entries, open_path_callback=None, parent=None):
            captured["history_entries"] = history_entries
            captured["open_path_callback"] = open_path_callback
            captured["parent"] = parent

        def exec_(self):
            captured["shown"] = True
            return QDialog.Accepted

    monkeypatch.setattr("ui_designer.ui.main_window.load_release_history", fake_load_release_history)
    monkeypatch.setattr("ui_designer.ui.main_window.ReleaseHistoryDialog", FakeHistoryDialog)

    window._show_release_history()

    assert captured["project_dir"] == str(project_dir)
    assert captured["output_dir"].endswith(os.path.join("output", "ui_designer_release"))
    assert captured["history_entries"][0]["sdk"]["revision"] == "v1.0.0-310-g416d576"
    assert captured["open_path_callback"] == window._open_path_in_shell
    assert captured["parent"] is window
    assert captured["shown"] is True
