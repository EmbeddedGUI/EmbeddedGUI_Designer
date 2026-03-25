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
        def __init__(self, history_entries, open_path_callback=None, refresh_history_callback=None, project_key="", parent=None):
            captured["history_entries"] = history_entries
            captured["open_path_callback"] = open_path_callback
            captured["refresh_history_callback"] = refresh_history_callback
            captured["project_key"] = project_key
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
    assert callable(captured["refresh_history_callback"])
    assert captured["project_key"] == str(project_dir)
    assert captured["parent"] is window
    assert captured["shown"] is True


@_skip_no_qt
def test_release_history_dialog_previews_manifest_and_log(qapp, tmp_path):
    from ui_designer.ui.release_dialogs import ReleaseHistoryDialog

    manifest_path = tmp_path / "release-manifest.json"
    log_path = tmp_path / "build.log"
    manifest_path.write_text('{"status":"success","sdk":{"revision":"v1.0.0-310-g416d576"}}\n', encoding="utf-8")
    log_path.write_text("build ok\nline2\n", encoding="utf-8")

    dialog = ReleaseHistoryDialog(
        [
            {
                "build_id": "20260326T000000Z",
                "status": "success",
                "profile_id": "windows-pc",
                "manifest_path": str(manifest_path),
                "log_path": str(log_path),
            }
        ]
    )

    assert dialog._preview_label.text() == "Manifest Preview"
    assert '"status": "success"' in dialog._preview_edit.toPlainText()

    dialog._preview_selected_path("log_path", "Log")

    assert dialog._preview_label.text() == "Log Preview"
    assert "build ok" in dialog._preview_edit.toPlainText()


@_skip_no_qt
def test_release_history_dialog_preview_truncates_large_logs(qapp, tmp_path):
    from ui_designer.ui.release_dialogs import ReleaseHistoryDialog

    log_path = tmp_path / "build.log"
    log_path.write_text("x" * 70000, encoding="utf-8")

    dialog = ReleaseHistoryDialog(
        [
            {
                "build_id": "20260326T000000Z",
                "status": "failed",
                "profile_id": "windows-pc",
                "log_path": str(log_path),
            }
        ]
    )

    assert dialog._preview_label.text() == "Log Preview"
    assert "[truncated to first 65536 characters]" in dialog._preview_edit.toPlainText()


@_skip_no_qt
def test_release_history_dialog_copy_buttons_write_clipboard(qapp, tmp_path):
    from PyQt5.QtWidgets import QApplication
    from ui_designer.ui.release_dialogs import ReleaseHistoryDialog

    manifest_path = tmp_path / "release-manifest.json"
    manifest_path.write_text('{"status":"success"}\n', encoding="utf-8")

    dialog = ReleaseHistoryDialog(
        [
            {
                "build_id": "20260326T000000Z",
                "status": "success",
                "profile_id": "windows-pc",
                "manifest_path": str(manifest_path),
            }
        ]
    )

    QApplication.clipboard().clear()
    dialog._copy_details_button.click()
    assert "Build ID: 20260326T000000Z" in QApplication.clipboard().text()

    dialog._copy_preview_button.click()
    assert '"status": "success"' in QApplication.clipboard().text()

    dialog._copy_entry_json_button.click()
    copied_json = QApplication.clipboard().text()
    assert '"build_id": "20260326T000000Z"' in copied_json
    assert '"manifest_path":' in copied_json


@_skip_no_qt
def test_release_history_dialog_filters_entries(qapp):
    from ui_designer.ui.release_dialogs import ReleaseHistoryDialog

    dialog = ReleaseHistoryDialog(
        [
            {
                "build_id": "20260326T000000Z",
                "status": "success",
                "profile_id": "windows-pc",
                "message": "Release created",
                "sdk": {"revision": "sdk-good"},
                "warning_count": 0,
                "error_count": 0,
                "manifest_path": "/tmp/release-manifest.json",
            },
            {
                "build_id": "20260326T000100Z",
                "status": "failed",
                "profile_id": "esp32",
                "message": "Build failed",
                "sdk": {"revision": "sdk-fail"},
                "warning_count": 2,
                "error_count": 1,
                "log_path": "/tmp/build.log",
                "zip_path": "/tmp/release.zip",
            },
        ]
    )

    assert dialog._history_list.count() == 2
    assert dialog._result_count_label.text() == "2 / 2"
    assert dialog._status_breakdown_label.text() == "success 1 | failed 1 | unknown 0"
    assert dialog._artifact_breakdown_label.text() == "manifest 1 | log 1 | package 1"
    assert "20260326T000100Z" in dialog._history_list.item(0).text()

    dialog._status_filter_combo.setCurrentIndex(dialog._status_filter_combo.findData("failed"))
    assert dialog._history_list.count() == 1
    assert dialog._result_count_label.text() == "1 / 2"
    assert dialog._status_breakdown_label.text() == "success 0 | failed 1 | unknown 0"
    assert dialog._artifact_breakdown_label.text() == "manifest 0 | log 1 | package 1"
    assert "20260326T000100Z" in dialog._history_list.item(0).text()

    dialog._status_filter_combo.setCurrentIndex(dialog._status_filter_combo.findData(""))
    dialog._profile_filter_combo.setCurrentIndex(dialog._profile_filter_combo.findData("windows-pc"))
    assert dialog._history_list.count() == 1
    assert "20260326T000000Z" in dialog._history_list.item(0).text()

    dialog._profile_filter_combo.setCurrentIndex(dialog._profile_filter_combo.findData(""))
    dialog._artifact_filter_combo.setCurrentIndex(dialog._artifact_filter_combo.findData("manifest"))
    assert dialog._history_list.count() == 1
    assert "20260326T000000Z" in dialog._history_list.item(0).text()

    dialog._artifact_filter_combo.setCurrentIndex(dialog._artifact_filter_combo.findData("missing_manifest"))
    assert dialog._history_list.count() == 1
    assert "20260326T000100Z" in dialog._history_list.item(0).text()

    dialog._artifact_filter_combo.setCurrentIndex(dialog._artifact_filter_combo.findData(""))
    dialog._search_edit.setText("sdk-fail")
    assert dialog._history_list.count() == 1
    assert "20260326T000100Z" in dialog._history_list.item(0).text()

    dialog._search_edit.setText("esp32 fail")
    assert dialog._history_list.count() == 1
    assert "20260326T000100Z" in dialog._history_list.item(0).text()

    dialog._search_edit.clear()
    dialog._diagnostics_filter_combo.setCurrentIndex(dialog._diagnostics_filter_combo.findData("errors"))
    assert dialog._history_list.count() == 1
    assert "20260326T000100Z" in dialog._history_list.item(0).text()

    dialog._diagnostics_filter_combo.setCurrentIndex(dialog._diagnostics_filter_combo.findData("clean"))
    assert dialog._history_list.count() == 1
    assert "20260326T000000Z" in dialog._history_list.item(0).text()

    dialog._clear_filters_button.click()
    assert dialog._history_list.count() == 2
    assert dialog._result_count_label.text() == "2 / 2"
    assert dialog._status_breakdown_label.text() == "success 1 | failed 1 | unknown 0"
    assert dialog._artifact_breakdown_label.text() == "manifest 1 | log 1 | package 1"
    assert dialog._range_filter_combo.currentData() == ""
    assert dialog._status_filter_combo.currentData() == ""
    assert dialog._profile_filter_combo.currentData() == ""
    assert dialog._artifact_filter_combo.currentData() == ""
    assert dialog._diagnostics_filter_combo.currentData() == ""
    assert dialog._search_edit.text() == ""


@_skip_no_qt
def test_release_history_dialog_copy_filtered_summary_uses_current_filter(qapp):
    from PyQt5.QtWidgets import QApplication
    from ui_designer.ui.release_dialogs import ReleaseHistoryDialog

    dialog = ReleaseHistoryDialog(
        [
            {
                "build_id": "20260326T000000Z",
                "status": "success",
                "profile_id": "windows-pc",
                "message": "Release created",
                "sdk": {"revision": "sdk-good"},
                "warning_count": 0,
                "error_count": 0,
            },
            {
                "build_id": "20260326T000100Z",
                "status": "failed",
                "profile_id": "esp32",
                "message": "Build failed",
                "sdk": {"revision": "sdk-fail"},
                "warning_count": 2,
                "error_count": 1,
                "zip_path": "/tmp/release.zip",
            },
        ]
    )

    dialog._status_filter_combo.setCurrentIndex(dialog._status_filter_combo.findData("failed"))
    dialog._artifact_filter_combo.setCurrentIndex(dialog._artifact_filter_combo.findData("package"))

    QApplication.clipboard().clear()
    dialog._copy_filtered_button.click()
    copied = QApplication.clipboard().text()

    assert "matched_entries=1" in copied
    assert "status_counts: success=0 failed=1 unknown=0" in copied
    assert "artifact_counts: manifest=0 log=0 package=1" in copied
    assert "filters: range=all, status=failed, profile=all, artifact=package, diagnostics=all, sort=newest, search=-" in copied
    assert "20260326T000100Z | failed | esp32 | sdk sdk-fail | Build failed" in copied
    assert "20260326T000000Z | success | windows-pc | sdk sdk-good | Release created" not in copied


@_skip_no_qt
def test_release_history_dialog_copy_filtered_json_uses_current_filter(qapp):
    import json

    from PyQt5.QtWidgets import QApplication
    from ui_designer.ui.release_dialogs import ReleaseHistoryDialog

    dialog = ReleaseHistoryDialog(
        [
            {
                "build_id": "20260326T000000Z",
                "status": "success",
                "profile_id": "windows-pc",
                "message": "Release created",
                "sdk": {"revision": "sdk-good"},
                "warning_count": 0,
                "error_count": 0,
            },
            {
                "build_id": "20260326T000100Z",
                "status": "failed",
                "profile_id": "esp32",
                "message": "Build failed",
                "sdk": {"revision": "sdk-fail"},
                "warning_count": 2,
                "error_count": 1,
                "zip_path": "/tmp/release.zip",
            },
        ]
    )

    dialog._artifact_filter_combo.setCurrentIndex(dialog._artifact_filter_combo.findData("package"))

    QApplication.clipboard().clear()
    dialog._copy_filtered_json_button.click()
    copied = json.loads(QApplication.clipboard().text())

    assert copied["matched_entries"] == 1
    assert copied["filters"]["artifact"] == "package"
    assert copied["filters"]["diagnostics"] == "all"
    assert copied["entries"][0]["build_id"] == "20260326T000100Z"


@_skip_no_qt
def test_release_history_dialog_exports_filtered_summary_to_file(qapp, tmp_path, monkeypatch):
    from ui_designer.ui.release_dialogs import ReleaseHistoryDialog

    export_path = tmp_path / "release-history-summary.txt"
    captured = {}
    dialog = ReleaseHistoryDialog(
        [
            {
                "build_id": "20260326T000000Z",
                "status": "success",
                "profile_id": "windows-pc",
                "message": "Release created",
                "sdk": {"revision": "sdk-good"},
                "warning_count": 0,
                "error_count": 0,
            },
            {
                "build_id": "20260326T000100Z",
                "status": "failed",
                "profile_id": "esp32",
                "message": "Build failed",
                "sdk": {"revision": "sdk-fail"},
                "warning_count": 2,
                "error_count": 1,
                "zip_path": "/tmp/release.zip",
            },
        ]
    )

    dialog._status_filter_combo.setCurrentIndex(dialog._status_filter_combo.findData("failed"))
    dialog._artifact_filter_combo.setCurrentIndex(dialog._artifact_filter_combo.findData("package"))
    monkeypatch.setattr(
        "ui_designer.ui.release_dialogs.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: (
            captured.setdefault("default_name", args[2]) and str(export_path),
            "Text Files (*.txt)",
        ),
    )

    dialog._export_filtered_button.click()

    exported = export_path.read_text(encoding="utf-8")
    assert captured["default_name"] == "release-history-summary-failed-package.txt"
    assert "matched_entries=1" in exported
    assert "status_counts: success=0 failed=1 unknown=0" in exported
    assert "artifact_counts: manifest=0 log=0 package=1" in exported
    assert "filters: range=all, status=failed, profile=all, artifact=package, diagnostics=all, sort=newest, search=-" in exported
    assert "20260326T000100Z | failed | esp32 | sdk sdk-fail | Build failed" in exported
    assert "20260326T000000Z | success | windows-pc | sdk sdk-good | Release created" not in exported


@_skip_no_qt
def test_release_history_dialog_exports_filtered_entries_as_json(qapp, tmp_path, monkeypatch):
    import json

    from ui_designer.ui.release_dialogs import ReleaseHistoryDialog

    export_path = tmp_path / "release-history-summary.json"
    dialog = ReleaseHistoryDialog(
        [
            {
                "build_id": "20260326T000000Z",
                "status": "success",
                "profile_id": "windows-pc",
                "message": "Release created",
                "sdk": {"revision": "sdk-good"},
                "warning_count": 0,
                "error_count": 0,
            },
            {
                "build_id": "20260326T000100Z",
                "status": "failed",
                "profile_id": "esp32",
                "message": "Build failed",
                "sdk": {"revision": "sdk-fail"},
                "warning_count": 2,
                "error_count": 1,
                "zip_path": "/tmp/release.zip",
            },
        ]
    )

    dialog._artifact_filter_combo.setCurrentIndex(dialog._artifact_filter_combo.findData("package"))
    monkeypatch.setattr(
        "ui_designer.ui.release_dialogs.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: (str(export_path), "JSON Files (*.json)"),
    )

    dialog._export_filtered_button.click()

    exported = json.loads(export_path.read_text(encoding="utf-8"))
    assert exported["matched_entries"] == 1
    assert exported["status_counts"] == {"success": 0, "failed": 1, "unknown": 0}
    assert exported["artifact_counts"] == {"manifest": 0, "log": 0, "package": 1}
    assert exported["filters"]["artifact"] == "package"
    assert exported["filters"]["diagnostics"] == "all"
    assert exported["filters"]["sort"] == "newest"
    assert exported["entries"][0]["build_id"] == "20260326T000100Z"


@_skip_no_qt
def test_release_history_dialog_can_sort_entries(qapp):
    from ui_designer.ui.release_dialogs import ReleaseHistoryDialog

    dialog = ReleaseHistoryDialog(
        [
            {
                "build_id": "20260326T000000Z",
                "created_at_utc": "2026-03-26T00:00:00Z",
                "status": "success",
                "profile_id": "windows-pc",
                "message": "Newest success",
                "sdk": {"revision": "sdk-good"},
            },
            {
                "build_id": "20260324T000000Z",
                "created_at_utc": "2026-03-24T00:00:00Z",
                "status": "failed",
                "profile_id": "esp32",
                "message": "Older failed",
                "sdk": {"revision": "sdk-fail"},
            },
            {
                "build_id": "20260320T000000Z",
                "created_at_utc": "2026-03-20T00:00:00Z",
                "status": "unknown",
                "profile_id": "linux-sdl",
                "message": "Oldest unknown",
                "sdk": {"revision": "sdk-unknown"},
            },
        ]
    )

    assert "20260326T000000Z" in dialog._history_list.item(0).text()

    dialog._sort_combo.setCurrentIndex(dialog._sort_combo.findData("oldest"))
    assert "20260320T000000Z" in dialog._history_list.item(0).text()

    dialog._sort_combo.setCurrentIndex(dialog._sort_combo.findData("status"))
    assert "20260324T000000Z" in dialog._history_list.item(0).text()

    dialog._sort_combo.setCurrentIndex(dialog._sort_combo.findData("profile"))
    assert "20260324T000000Z" in dialog._history_list.item(0).text()


@_skip_no_qt
def test_release_history_dialog_filters_entries_by_time_range(qapp, monkeypatch):
    from datetime import datetime, timezone
    from ui_designer.ui.release_dialogs import ReleaseHistoryDialog

    monkeypatch.setattr(
        "ui_designer.ui.release_dialogs._utc_now",
        lambda: datetime(2026, 3, 26, 12, 0, 0, tzinfo=timezone.utc),
    )

    dialog = ReleaseHistoryDialog(
        [
            {
                "build_id": "20260326T000000Z",
                "created_at_utc": "2026-03-26T00:00:00Z",
                "status": "success",
                "profile_id": "windows-pc",
                "message": "Recent release",
                "sdk": {"revision": "sdk-recent"},
            },
            {
                "build_id": "20260310T000000Z",
                "created_at_utc": "2026-03-10T00:00:00Z",
                "status": "success",
                "profile_id": "windows-pc",
                "message": "Old release",
                "sdk": {"revision": "sdk-old"},
            },
        ]
    )

    dialog._range_filter_combo.setCurrentIndex(dialog._range_filter_combo.findData("7d"))

    assert dialog._history_list.count() == 1
    assert dialog._result_count_label.text() == "1 / 2"
    assert dialog._artifact_breakdown_label.text() == "manifest 0 | log 0 | package 0"
    assert "20260326T000000Z" in dialog._history_list.item(0).text()


@_skip_no_qt
def test_release_history_dialog_refreshes_entries(qapp):
    from ui_designer.ui.release_dialogs import ReleaseHistoryDialog

    refreshed = [
        {
            "build_id": "20260326T000200Z",
            "status": "success",
            "profile_id": "linux-sdl",
            "message": "Release refreshed",
            "sdk": {"revision": "sdk-new"},
        }
    ]

    dialog = ReleaseHistoryDialog(
        [
            {
                "build_id": "20260326T000000Z",
                "status": "success",
                "profile_id": "windows-pc",
                "message": "Release created",
                "sdk": {"revision": "sdk-old"},
            }
        ],
        refresh_history_callback=lambda: refreshed,
    )

    dialog._refresh_button.click()

    assert dialog._history_list.count() == 1
    assert "20260326T000200Z" in dialog._history_list.item(0).text()
    assert dialog._profile_filter_combo.findData("linux-sdl") >= 0


@_skip_no_qt
def test_release_history_action_allows_empty_history(qapp, isolated_config, tmp_path, monkeypatch):
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

    def fake_load_release_history(project_dir_arg, output_dir=""):
        captured["project_dir"] = project_dir_arg
        captured["output_dir"] = output_dir
        return []

    class FakeHistoryDialog:
        def __init__(self, history_entries, open_path_callback=None, refresh_history_callback=None, project_key="", parent=None):
            captured["history_entries"] = history_entries
            captured["refresh_history_callback"] = refresh_history_callback
            captured["project_key"] = project_key
            captured["parent"] = parent

        def exec_(self):
            captured["shown"] = True
            return QDialog.Accepted

    monkeypatch.setattr("ui_designer.ui.main_window.load_release_history", fake_load_release_history)
    monkeypatch.setattr("ui_designer.ui.main_window.ReleaseHistoryDialog", FakeHistoryDialog)

    window._update_compile_availability()
    assert window._release_history_action.isEnabled() is True

    window._show_release_history()

    assert captured["project_dir"] == str(project_dir)
    assert captured["history_entries"] == []
    assert callable(captured["refresh_history_callback"])
    assert captured["project_key"] == str(project_dir)
    assert captured["parent"] is window
    assert captured["shown"] is True


@_skip_no_qt
def test_release_history_dialog_restores_saved_view_state(qapp, isolated_config):
    from ui_designer.ui.release_dialogs import ReleaseHistoryDialog

    dialog = ReleaseHistoryDialog(
        [
            {
                "build_id": "20260326T000000Z",
                "status": "failed",
                "profile_id": "esp32",
                "message": "Build failed",
                "sdk": {"revision": "sdk-fail"},
                "warning_count": 2,
                "error_count": 1,
            }
        ]
    )
    dialog._range_filter_combo.setCurrentIndex(dialog._range_filter_combo.findData("7d"))
    dialog._status_filter_combo.setCurrentIndex(dialog._status_filter_combo.findData("failed"))
    dialog._profile_filter_combo.setCurrentIndex(dialog._profile_filter_combo.findData("esp32"))
    dialog._artifact_filter_combo.setCurrentIndex(dialog._artifact_filter_combo.findData("package"))
    dialog._diagnostics_filter_combo.setCurrentIndex(dialog._diagnostics_filter_combo.findData("errors"))
    dialog._sort_combo.setCurrentIndex(dialog._sort_combo.findData("status"))
    dialog._search_edit.setText("sdk-fail")
    dialog.done(QDialog.Accepted)

    restored = ReleaseHistoryDialog(
        [
            {
                "build_id": "20260326T000000Z",
                "status": "failed",
                "profile_id": "esp32",
                "message": "Build failed",
                "sdk": {"revision": "sdk-fail"},
                "warning_count": 2,
                "error_count": 1,
            }
        ]
    )

    assert restored._range_filter_combo.currentData() == "7d"
    assert restored._status_filter_combo.currentData() == "failed"
    assert restored._profile_filter_combo.currentData() == "esp32"
    assert restored._artifact_filter_combo.currentData() == "package"
    assert restored._diagnostics_filter_combo.currentData() == "errors"
    assert restored._sort_combo.currentData() == "status"
    assert restored._search_edit.text() == "sdk-fail"


@_skip_no_qt
def test_release_history_dialog_restores_project_specific_view_state(qapp, isolated_config):
    from ui_designer.ui.release_dialogs import ReleaseHistoryDialog

    entries = [
        {
            "build_id": "20260326T000000Z",
            "status": "success",
            "profile_id": "windows-pc",
            "message": "Release created",
            "sdk": {"revision": "sdk-good"},
            "warning_count": 0,
            "error_count": 0,
            "manifest_path": "/tmp/release-manifest.json",
        },
        {
            "build_id": "20260326T000100Z",
            "status": "failed",
            "profile_id": "esp32",
            "message": "Build failed",
            "sdk": {"revision": "sdk-fail"},
            "warning_count": 2,
            "error_count": 1,
            "zip_path": "/tmp/release.zip",
        },
    ]

    dialog = ReleaseHistoryDialog(entries, project_key="project-a")
    dialog._status_filter_combo.setCurrentIndex(dialog._status_filter_combo.findData("failed"))
    dialog._artifact_filter_combo.setCurrentIndex(dialog._artifact_filter_combo.findData("package"))
    dialog._diagnostics_filter_combo.setCurrentIndex(dialog._diagnostics_filter_combo.findData("issues"))
    dialog._sort_combo.setCurrentIndex(dialog._sort_combo.findData("oldest"))
    dialog._search_edit.setText("sdk-fail")
    dialog.done(QDialog.Accepted)

    other_project = ReleaseHistoryDialog(entries, project_key="project-b")
    assert other_project._status_filter_combo.currentData() == ""
    assert other_project._artifact_filter_combo.currentData() == ""
    assert other_project._diagnostics_filter_combo.currentData() == ""
    assert other_project._sort_combo.currentData() == "newest"
    assert other_project._search_edit.text() == ""

    restored = ReleaseHistoryDialog(entries, project_key="project-a")
    assert restored._status_filter_combo.currentData() == "failed"
    assert restored._artifact_filter_combo.currentData() == "package"
    assert restored._diagnostics_filter_combo.currentData() == "issues"
    assert restored._sort_combo.currentData() == "oldest"
    assert restored._search_edit.text() == "sdk-fail"
