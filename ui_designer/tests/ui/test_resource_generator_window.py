import json
from types import SimpleNamespace

import pytest

from ui_designer.model.resource_generation_session import infer_generation_paths
from ui_designer.tests.qt_test_utils import HAS_PYQT5, skip_if_no_qt
from ui_designer.tests.sdk_builders import build_test_sdk_root
from ui_designer.tests.ui.window_test_helpers import close_test_window as _close_window

if HAS_PYQT5:
    from PyQt5.QtWidgets import QMessageBox


_skip_no_qt = skip_if_no_qt


@pytest.mark.usefixtures("isolated_config")
class TestResourceGeneratorWindow:
    @_skip_no_qt
    def test_resource_generator_starts_in_simple_mode_and_can_switch_to_professional(self, qapp):
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        window = ResourceGeneratorWindow("")

        assert window._mode_combo.currentData() == "simple"
        assert window._workspace_stack.currentWidget() is window._simple_page

        window._set_ui_mode("professional")

        assert window._mode_combo.currentData() == "professional"
        assert window._workspace_stack.currentWidget() is window._professional_page
        _close_window(window)

    @_skip_no_qt
    def test_invalid_raw_json_blocks_tab_switch(self, qapp, monkeypatch):
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        warnings = []
        monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args[2]) or QMessageBox.Ok)
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)

        window = ResourceGeneratorWindow("")
        window._raw_editor.setPlainText("{ invalid")
        qapp.processEvents()

        raw_index = window._bottom_tabs.indexOf(window._raw_editor)
        merged_index = window._bottom_tabs.indexOf(window._merged_preview)
        window._bottom_tabs.setCurrentIndex(merged_index)
        qapp.processEvents()

        assert window._bottom_tabs.currentIndex() == raw_index
        assert warnings
        _close_window(window)

    @_skip_no_qt
    def test_main_window_resource_generator_prefills_current_project_paths(self, qapp, monkeypatch, tmp_path):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = build_test_sdk_root(tmp_path / "sdk")
        resource_src = tmp_path / "DemoApp" / "resource" / "src"
        resource_dir = resource_src.parent
        resource_src.mkdir(parents=True)
        config_path = resource_src / "app_resource_config.json"
        config_path.write_text(json.dumps({"img": [], "font": [], "mp4": []}, indent=4), encoding="utf-8")

        monkeypatch.setattr("ui_designer.ui.main_window.designer_runtime_root", lambda repo_root=None: str(tmp_path / "runtime"))
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)

        class _FakeProject:
            def get_resource_dir(self):
                return str(resource_dir)

            def get_resource_src_dir(self):
                return str(resource_src)

            def get_user_resource_config_path(self):
                return str(config_path)

        window = MainWindow(str(sdk_root))
        window.project = _FakeProject()
        window._project_dir = str(tmp_path / "DemoApp")

        window._open_resource_generator_window()
        qapp.processEvents()

        generator_window = window._resource_generator_window
        assert generator_window is not None
        assert generator_window._session.paths.config_path == str(config_path.resolve())
        assert generator_window._session.paths.source_dir == str(resource_src.resolve())
        assert generator_window._session.paths.workspace_dir == str(resource_dir.resolve())
        _close_window(generator_window)
        _close_window(window)

    @_skip_no_qt
    def test_main_window_resource_generator_opens_without_project(self, qapp, monkeypatch, tmp_path):
        from ui_designer.ui.main_window import MainWindow

        sdk_root = build_test_sdk_root(tmp_path / "sdk")
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)

        window = MainWindow(str(sdk_root))

        window._open_resource_generator_window()
        qapp.processEvents()

        generator_window = window._resource_generator_window
        assert generator_window is not None
        assert generator_window._session.paths.config_path == ""
        assert generator_window._session.paths.source_dir == ""
        assert generator_window._session.paths.workspace_dir == ""
        assert generator_window._session.paths.bin_output_dir == ""
        assert window._resource_generator_action.isEnabled() is True
        _close_window(generator_window)
        _close_window(window)

    @_skip_no_qt
    def test_config_path_edit_rebases_default_paths_with_new_location(self, qapp, monkeypatch, tmp_path):
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        monkeypatch.setattr(QMessageBox, "warning", lambda *args: QMessageBox.Ok)
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)

        original_config = tmp_path / "OldApp" / "resource" / "src" / "app_resource_config.json"
        new_config = tmp_path / "NewApp" / "resource" / "src" / "app_resource_config.json"

        window = ResourceGeneratorWindow("")
        window.open_with_paths(infer_generation_paths(str(original_config)), load_existing=False)
        qapp.processEvents()

        window._config_path_edit.setText(str(new_config))
        window._on_path_edited("config_path", window._config_path_edit)

        expected = infer_generation_paths(str(new_config))
        assert window._session.paths.config_path == expected.config_path
        assert window._session.paths.source_dir == expected.source_dir
        assert window._session.paths.workspace_dir == expected.workspace_dir
        assert window._session.paths.bin_output_dir == expected.bin_output_dir
        assert window.has_unsaved_changes() is True
        assert window.windowTitle().endswith(" *")
        _close_window(window)

    @_skip_no_qt
    def test_save_as_rebases_default_paths_with_new_config_location(self, qapp, monkeypatch, tmp_path):
        from PyQt5.QtWidgets import QFileDialog

        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        monkeypatch.setattr(QMessageBox, "warning", lambda *args: QMessageBox.Ok)
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)

        original_config = tmp_path / "OldApp" / "resource" / "src" / "app_resource_config.json"
        new_config = tmp_path / "NewApp" / "resource" / "src" / "app_resource_config.json"

        window = ResourceGeneratorWindow("")
        window.open_with_paths(infer_generation_paths(str(original_config)), load_existing=False)
        qapp.processEvents()

        monkeypatch.setattr(
            QFileDialog,
            "getSaveFileName",
            lambda *args, **kwargs: (str(new_config), "Resource Config (*.json)"),
        )

        assert window._save_config_as() is True

        expected = infer_generation_paths(str(new_config))
        assert window._session.paths.config_path == expected.config_path
        assert window._session.paths.source_dir == expected.source_dir
        assert window._session.paths.workspace_dir == expected.workspace_dir
        assert window._session.paths.bin_output_dir == expected.bin_output_dir
        assert new_config.is_file()
        _close_window(window)

    @_skip_no_qt
    def test_scan_assets_from_directory_sets_source_dir_and_populates_entries(self, qapp, monkeypatch, tmp_path):
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        import_dir = tmp_path / "imports"
        import_dir.mkdir(parents=True)
        (import_dir / "hero.png").write_bytes(b"png")
        (import_dir / "display.ttf").write_bytes(b"ttf")
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)

        window = ResourceGeneratorWindow("")
        window._scan_assets_from_directory(str(import_dir))

        assert window._session.paths.source_dir == str(import_dir.resolve())
        assert [entry["file"] for entry in window._session.section_entries("img")] == ["hero.png"]
        assert [entry["file"] for entry in window._session.section_entries("font")] == ["display.ttf"]
        assert window._simple_asset_table.rowCount() == 2
        assert window.has_unsaved_changes() is True
        _close_window(window)

    @_skip_no_qt
    def test_scan_assets_from_directory_can_copy_into_existing_source_dir(self, qapp, monkeypatch, tmp_path):
        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        import_dir = tmp_path / "imports"
        (import_dir / "fonts").mkdir(parents=True)
        (import_dir / "fonts" / "display.ttf").write_bytes(b"ttf")
        (import_dir / "fonts" / "display.txt").write_text("ABC", encoding="utf-8")
        (import_dir / "images").mkdir(parents=True)
        (import_dir / "images" / "hero.png").write_bytes(b"png")

        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(GenerationPaths(source_dir=str(source_dir)), {"img": [], "font": [], "mp4": []}, dirty=False)

        window._scan_assets_from_directory(str(import_dir))

        assert (source_dir / "fonts" / "display.ttf").read_bytes() == b"ttf"
        assert (source_dir / "fonts" / "display.txt").read_text(encoding="utf-8") == "ABC"
        assert (source_dir / "images" / "hero.png").read_bytes() == b"png"
        font_entry = window._session.section_entries("font")[0]
        assert font_entry["file"] == "fonts/display.ttf"
        assert font_entry["text"] == "fonts/display.txt"
        assert window._session.section_entries("img")[0]["file"] == "images/hero.png"
        _close_window(window)

    @_skip_no_qt
    def test_import_assets_from_files_sets_source_dir_and_pairs_font_text(self, qapp, monkeypatch, tmp_path):
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        import_dir = tmp_path / "imports"
        import_dir.mkdir(parents=True)
        (import_dir / "hero.png").write_bytes(b"png")
        (import_dir / "display.ttf").write_bytes(b"ttf")
        (import_dir / "display.txt").write_text("ABC", encoding="utf-8")
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)

        window = ResourceGeneratorWindow("")
        window._import_assets_from_files(
            [
                str(import_dir / "hero.png"),
                str(import_dir / "display.ttf"),
            ]
        )

        assert window._session.paths.source_dir == str(import_dir.resolve())
        assert [entry["file"] for entry in window._session.section_entries("img")] == ["hero.png"]
        font_entry = window._session.section_entries("font")[0]
        assert font_entry["file"] == "display.ttf"
        assert font_entry["text"] == "display.txt"
        assert window._simple_asset_table.rowCount() == 2
        assert window.has_unsaved_changes() is True
        assert window._status_label.text() == "Imported 2 assets, added 2, updated Source Dir."
        _close_window(window)

    @_skip_no_qt
    def test_import_assets_from_files_can_copy_into_existing_source_dir(self, qapp, monkeypatch, tmp_path):
        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        import_dir = tmp_path / "imports"
        (import_dir / "fonts").mkdir(parents=True)
        (import_dir / "fonts" / "display.ttf").write_bytes(b"ttf")
        (import_dir / "fonts" / "display.txt").write_text("ABC", encoding="utf-8")
        (import_dir / "images").mkdir(parents=True)
        (import_dir / "images" / "hero.png").write_bytes(b"png")

        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(GenerationPaths(source_dir=str(source_dir)), {"img": [], "font": [], "mp4": []}, dirty=False)

        window._import_assets_from_files(
            [
                str(import_dir / "fonts" / "display.ttf"),
                str(import_dir / "images" / "hero.png"),
            ]
        )

        assert (source_dir / "fonts" / "display.ttf").read_bytes() == b"ttf"
        assert (source_dir / "fonts" / "display.txt").read_text(encoding="utf-8") == "ABC"
        assert (source_dir / "images" / "hero.png").read_bytes() == b"png"
        font_entry = window._session.section_entries("font")[0]
        assert font_entry["file"] == "fonts/display.ttf"
        assert font_entry["text"] == "fonts/display.txt"
        assert window._session.section_entries("img")[0]["file"] == "images/hero.png"
        assert window._status_label.text() == "Imported 2 assets, copied 3 files, added 2."
        _close_window(window)

    @_skip_no_qt
    def test_import_assets_from_files_populates_video_metadata(self, qapp, monkeypatch, tmp_path):
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        import_dir = tmp_path / "imports"
        import_dir.mkdir(parents=True)
        (import_dir / "intro.mp4").write_bytes(b"mp4")
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)
        monkeypatch.setattr(
            "ui_designer.ui.resource_generator_window._detect_video_metadata",
            lambda path: {"fps": 24, "width": 320, "height": 180},
        )

        window = ResourceGeneratorWindow("")
        window._import_assets_from_files([str(import_dir / "intro.mp4")])

        entry = window._session.section_entries("mp4")[0]
        assert entry["file"] == "intro.mp4"
        assert entry["fps"] == 24
        assert entry["width"] == 320
        assert entry["height"] == 180
        assert window._simple_asset_table.rowCount() == 1
        assert window._simple_asset_table.item(0, 3).text() == "24fps 320x180"
        _close_window(window)

    @_skip_no_qt
    def test_remove_selected_simple_asset_updates_session_and_preview(self, qapp, monkeypatch, tmp_path):
        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        (source_dir / "hero.png").write_bytes(b"png")
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {"img": [{"file": "hero.png", "name": "hero"}], "font": [], "mp4": []},
            dirty=False,
        )
        window._simple_asset_table.selectRow(0)
        qapp.processEvents()

        window._remove_selected_simple_asset()

        assert window._session.section_entries("img") == []
        assert window._simple_asset_table.rowCount() == 0
        assert "hero.png" not in window._simple_preview.toPlainText()
        assert "hero.png" not in window._merged_preview.toPlainText()
        assert window._status_label.text() == "Removed image 'hero'."
        _close_window(window)

    @_skip_no_qt
    def test_duplicate_selected_simple_asset_creates_new_entry(self, qapp, monkeypatch, tmp_path):
        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        (source_dir / "hero.png").write_bytes(b"png")
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {"img": [{"file": "hero.png", "name": "hero"}], "font": [], "mp4": []},
            dirty=False,
        )
        window._simple_asset_table.selectRow(0)
        qapp.processEvents()

        window._duplicate_selected_simple_asset()

        entries = window._session.section_entries("img")
        assert len(entries) == 2
        assert entries[0]["name"] == "hero"
        assert entries[1]["name"] == "hero_copy"
        assert entries[1]["file"] == "hero.png"
        assert window._simple_asset_table.item(1, 1).text() == "hero_copy"
        assert window.has_unsaved_changes() is True
        assert window._status_label.text() == "Duplicated image 'hero_copy'."
        _close_window(window)

    @_skip_no_qt
    def test_duplicate_selected_simple_asset_increments_copy_suffix(self, qapp, monkeypatch, tmp_path):
        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        (source_dir / "hero.png").write_bytes(b"png")
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {"img": [{"file": "hero.png", "name": "hero"}, {"file": "hero.png", "name": "hero_copy"}], "font": [], "mp4": []},
            dirty=False,
        )
        window._simple_asset_table.selectRow(0)
        qapp.processEvents()

        window._duplicate_selected_simple_asset()

        names = [entry["name"] for entry in window._session.section_entries("img")]
        assert names == ["hero", "hero_copy2", "hero_copy"]
        assert window._status_label.text() == "Duplicated image 'hero_copy2'."
        _close_window(window)

    @_skip_no_qt
    def test_detect_selected_video_metadata_updates_entry(self, qapp, monkeypatch, tmp_path):
        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        (source_dir / "intro.mp4").write_bytes(b"mp4")
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)
        monkeypatch.setattr(
            "ui_designer.ui.resource_generator_window._detect_video_metadata",
            lambda path: {"fps": 24, "width": 320, "height": 180},
        )

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {"img": [], "font": [], "mp4": [{"file": "intro.mp4", "name": "intro"}]},
            dirty=False,
        )
        window._simple_asset_table.selectRow(0)
        qapp.processEvents()

        window._detect_selected_video_metadata()

        entry = window._session.section_entries("mp4")[0]
        assert entry["fps"] == 24
        assert entry["width"] == 320
        assert entry["height"] == 180
        assert window.has_unsaved_changes() is True
        assert window._status_label.text() == "Updated video metadata for 'intro' (24fps 320x180)."
        assert "Video: 24fps 320x180" in window._simple_asset_meta.toPlainText()
        _close_window(window)

    @_skip_no_qt
    def test_open_selected_font_text_resource_opens_existing_file(self, qapp, monkeypatch, tmp_path):
        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        (source_dir / "charset").mkdir(parents=True)
        (source_dir / "display.ttf").write_bytes(b"ttf")
        text_path = source_dir / "charset" / "basic.txt"
        text_path.write_text("ABC", encoding="utf-8")

        opened = []
        monkeypatch.setattr(
            "ui_designer.ui.resource_generator_window.QDesktopServices.openUrl",
            lambda url: opened.append(url.toLocalFile()) or True,
        )

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {"img": [], "font": [{"file": "display.ttf", "name": "display", "text": "charset/basic.txt"}], "mp4": []},
            dirty=False,
        )
        window._simple_asset_table.selectRow(0)
        qapp.processEvents()

        window._open_selected_font_text_resource()

        assert opened == [text_path.resolve().as_posix()]
        assert window._status_label.text() == "Opened font text 'charset/basic.txt'."
        _close_window(window)

    @_skip_no_qt
    def test_open_selected_font_text_resource_can_create_missing_file(self, qapp, monkeypatch, tmp_path):
        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        (source_dir / "display.ttf").write_bytes(b"ttf")

        opened = []
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)
        monkeypatch.setattr(
            "ui_designer.ui.resource_generator_window.QDesktopServices.openUrl",
            lambda url: opened.append(url.toLocalFile()) or True,
        )

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {"img": [], "font": [{"file": "display.ttf", "name": "display"}], "mp4": []},
            dirty=False,
        )
        window._simple_asset_table.selectRow(0)
        qapp.processEvents()

        window._open_selected_font_text_resource()

        text_path = source_dir / "display_charset.txt"
        assert text_path.is_file()
        assert opened == [text_path.resolve().as_posix()]
        assert window._session.section_entries("font")[0]["text"] == "display_charset.txt"
        assert window.has_unsaved_changes() is True
        assert window._status_label.text() == "Created and opened font text 'display_charset.txt'."
        _close_window(window)

    @_skip_no_qt
    def test_auto_fill_missing_resource_info_updates_names_font_text_and_video_metadata(self, qapp, monkeypatch, tmp_path):
        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        (source_dir / "hero.png").write_bytes(b"png")
        (source_dir / "display.ttf").write_bytes(b"ttf")
        (source_dir / "display.txt").write_text("ABC", encoding="utf-8")
        (source_dir / "intro.mp4").write_bytes(b"mp4")

        monkeypatch.setattr(
            "ui_designer.ui.resource_generator_window._detect_video_metadata",
            lambda path: {"fps": 24, "width": 320, "height": 180},
        )
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {
                "img": [{"file": "hero.png"}],
                "font": [{"file": "display.ttf"}],
                "mp4": [{"file": "intro.mp4"}],
            },
            dirty=False,
        )

        window._auto_fill_missing_resource_info()

        assert window._session.section_entries("img")[0]["name"] == "hero"
        font_entry = window._session.section_entries("font")[0]
        assert font_entry["name"] == "display"
        assert font_entry["text"] == "display.txt"
        video_entry = window._session.section_entries("mp4")[0]
        assert video_entry["name"] == "intro"
        assert video_entry["fps"] == 24
        assert video_entry["width"] == 320
        assert video_entry["height"] == 180
        assert window.has_unsaved_changes() is True
        assert window._status_label.text() == "Filled 5 missing fields, names 3, font texts 1, video metadata 1."
        _close_window(window)

    @_skip_no_qt
    def test_sort_assets_for_quick_mode_reorders_entries_and_table(self, qapp, monkeypatch, tmp_path):
        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {
                "img": [
                    {"file": "zeta.png", "name": "zeta"},
                    {"file": "alpha.png", "name": "alpha"},
                ],
                "font": [
                    {"file": "display_b.ttf", "name": "display_b"},
                    {"file": "display_a.ttf", "name": "display_a"},
                ],
                "mp4": [],
            },
            dirty=False,
        )

        window._sort_assets_for_quick_mode()

        assert [entry["file"] for entry in window._session.section_entries("img")] == ["alpha.png", "zeta.png"]
        assert [entry["file"] for entry in window._session.section_entries("font")] == ["display_a.ttf", "display_b.ttf"]
        assert window._simple_asset_table.item(0, 2).text() == "alpha.png"
        assert window._simple_asset_table.item(1, 2).text() == "zeta.png"
        assert window._simple_asset_table.item(2, 2).text() == "display_a.ttf"
        assert window._simple_asset_table.item(3, 2).text() == "display_b.ttf"
        assert window.has_unsaved_changes() is True
        assert window._status_label.text() == "Sorted 4 assets across quick mode sections."
        _close_window(window)

    @_skip_no_qt
    def test_simple_mode_selection_updates_image_preview(self, qapp, tmp_path):
        from PyQt5.QtGui import QPixmap

        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        image_path = source_dir / "hero.png"
        pixmap = QPixmap(12, 8)
        assert pixmap.save(str(image_path), "PNG")

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {"img": [{"file": "hero.png", "name": "hero"}], "font": [], "mp4": []},
            dirty=False,
        )

        window._simple_asset_table.selectRow(0)
        qapp.processEvents()

        assert window._simple_asset_preview_title.text() == "Images: hero"
        assert window._simple_asset_preview_label.pixmap() is not None
        assert "Image Size: 12 x 8" in window._simple_asset_meta.toPlainText()
        _close_window(window)

    @_skip_no_qt
    def test_simple_mode_selection_renders_font_preview(self, qapp, monkeypatch, tmp_path):
        from PyQt5.QtGui import QPixmap

        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        (source_dir / "charset").mkdir(parents=True)
        font_path = source_dir / "display.ttf"
        font_path.write_bytes(b"ttf")
        (source_dir / "charset" / "basic.txt").write_text("A\nB\n", encoding="utf-8")

        captured = {}

        def _fake_render(self, font_file, sample_text):
            captured["font_file"] = font_file
            captured["sample_text"] = sample_text
            pixmap = QPixmap(96, 36)
            pixmap.fill()
            return pixmap

        monkeypatch.setattr(ResourceGeneratorWindow, "_build_font_preview_pixmap", _fake_render)

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {"img": [], "font": [{"file": "display.ttf", "name": "display", "text": "charset/basic.txt"}], "mp4": []},
            dirty=False,
        )

        window._simple_asset_table.selectRow(0)
        qapp.processEvents()

        assert captured["font_file"] == str(font_path.resolve())
        assert captured["sample_text"] == "AB"
        assert window._simple_asset_preview_title.text() == "Fonts: display"
        assert window._simple_asset_preview_label.pixmap() is not None
        assert "Preview Text: AB" in window._simple_asset_meta.toPlainText()
        assert "Preview Source: charset/basic.txt" in window._simple_asset_meta.toPlainText()
        _close_window(window)

    @_skip_no_qt
    def test_open_selected_asset_in_external_editor_uses_desktop_services(self, qapp, monkeypatch, tmp_path):
        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        image_path = source_dir / "hero.png"
        image_path.write_bytes(b"png")

        opened = []
        monkeypatch.setattr(
            "ui_designer.ui.resource_generator_window.QDesktopServices.openUrl",
            lambda url: opened.append(url.toLocalFile()) or True,
        )

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {"img": [{"file": "hero.png", "name": "hero"}], "font": [], "mp4": []},
            dirty=False,
        )
        window._simple_asset_table.selectRow(0)
        qapp.processEvents()

        window._open_selected_asset_in_external_editor()

        assert opened == [image_path.resolve().as_posix()]
        _close_window(window)

    @_skip_no_qt
    def test_open_selected_asset_folder_uses_desktop_services(self, qapp, monkeypatch, tmp_path):
        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src" / "images"
        source_dir.mkdir(parents=True)
        image_path = source_dir / "hero.png"
        image_path.write_bytes(b"png")

        opened = []
        monkeypatch.setattr(
            "ui_designer.ui.resource_generator_window.QDesktopServices.openUrl",
            lambda url: opened.append(url.toLocalFile()) or True,
        )

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir.parent)),
            {"img": [{"file": "images/hero.png", "name": "hero"}], "font": [], "mp4": []},
            dirty=False,
        )
        window._simple_asset_table.selectRow(0)
        qapp.processEvents()

        window._open_selected_asset_folder()

        assert opened == [source_dir.resolve().as_posix()]
        _close_window(window)

    @_skip_no_qt
    def test_resize_image_helper_overwrites_selected_image(self, qapp, monkeypatch, tmp_path):
        from PyQt5.QtGui import QPixmap
        from PyQt5.QtWidgets import QDialog

        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        image_path = source_dir / "hero.png"
        pixmap = QPixmap(12, 8)
        assert pixmap.save(str(image_path), "PNG")

        class _FakeDialog:
            def __init__(self, *, width, height, output_filename, parent=None):
                assert width == 12
                assert height == 8
                assert output_filename == "hero.png"

            def exec_(self):
                return QDialog.Accepted

            def output_filename(self):
                return "hero.png"

            def width_value(self):
                return 6

            def height_value(self):
                return 4

        monkeypatch.setattr("ui_designer.ui.resource_generator_window._QuickImageResizeDialog", _FakeDialog)

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {"img": [{"file": "hero.png", "name": "hero"}], "font": [], "mp4": []},
            dirty=False,
        )
        window._simple_asset_table.selectRow(0)
        qapp.processEvents()

        window._open_resize_image_helper()

        resized = QPixmap(str(image_path))
        assert resized.width() == 6
        assert resized.height() == 4
        assert len(window._session.section_entries("img")) == 1
        assert window._status_label.text() == "Updated resized image 'hero.png' (6 x 4)."
        _close_window(window)

    @_skip_no_qt
    def test_resize_image_helper_can_create_new_image_entry(self, qapp, monkeypatch, tmp_path):
        from PyQt5.QtGui import QPixmap
        from PyQt5.QtWidgets import QDialog, QMessageBox

        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        image_path = source_dir / "hero.png"
        pixmap = QPixmap(12, 8)
        assert pixmap.save(str(image_path), "PNG")

        class _FakeDialog:
            def __init__(self, *, width, height, output_filename, parent=None):
                assert width == 12
                assert height == 8
                assert output_filename == "hero.png"

            def exec_(self):
                return QDialog.Accepted

            def output_filename(self):
                return "variants/hero_small.png"

            def width_value(self):
                return 5

            def height_value(self):
                return 3

        monkeypatch.setattr("ui_designer.ui.resource_generator_window._QuickImageResizeDialog", _FakeDialog)
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {"img": [{"file": "hero.png", "name": "hero"}], "font": [], "mp4": []},
            dirty=False,
        )
        window._simple_asset_table.selectRow(0)
        qapp.processEvents()

        window._open_resize_image_helper()

        resized_path = source_dir / "variants" / "hero_small.png"
        resized = QPixmap(str(resized_path))
        assert resized.width() == 5
        assert resized.height() == 3
        files = [entry["file"] for entry in window._session.section_entries("img")]
        assert files == ["hero.png", "variants/hero_small.png"]
        assert window.has_unsaved_changes() is True
        assert window._status_label.text() == "Created resized image 'variants/hero_small.png' (5 x 3)."
        _close_window(window)

    @_skip_no_qt
    def test_rotate_image_helper_overwrites_selected_image(self, qapp, monkeypatch, tmp_path):
        from PyQt5.QtGui import QPixmap
        from PyQt5.QtWidgets import QDialog

        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        image_path = source_dir / "hero.png"
        pixmap = QPixmap(12, 8)
        assert pixmap.save(str(image_path), "PNG")

        class _FakeDialog:
            def __init__(self, *, width, height, output_filename, parent=None):
                assert width == 12
                assert height == 8
                assert output_filename == "hero.png"

            def exec_(self):
                return QDialog.Accepted

            def output_filename(self):
                return "hero.png"

            def rotation_degrees(self):
                return 90

        monkeypatch.setattr("ui_designer.ui.resource_generator_window._QuickImageRotateDialog", _FakeDialog)

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {"img": [{"file": "hero.png", "name": "hero"}], "font": [], "mp4": []},
            dirty=False,
        )
        window._simple_asset_table.selectRow(0)
        qapp.processEvents()

        window._open_rotate_image_helper()

        rotated = QPixmap(str(image_path))
        assert rotated.width() == 8
        assert rotated.height() == 12
        assert len(window._session.section_entries("img")) == 1
        assert window._status_label.text() == "Updated rotated image 'hero.png' (8 x 12)."
        _close_window(window)

    @_skip_no_qt
    def test_rotate_image_helper_can_create_new_image_entry(self, qapp, monkeypatch, tmp_path):
        from PyQt5.QtGui import QPixmap
        from PyQt5.QtWidgets import QDialog, QMessageBox

        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        image_path = source_dir / "hero.png"
        pixmap = QPixmap(12, 8)
        assert pixmap.save(str(image_path), "PNG")

        class _FakeDialog:
            def __init__(self, *, width, height, output_filename, parent=None):
                assert width == 12
                assert height == 8
                assert output_filename == "hero.png"

            def exec_(self):
                return QDialog.Accepted

            def output_filename(self):
                return "variants/hero_right.png"

            def rotation_degrees(self):
                return 90

        monkeypatch.setattr("ui_designer.ui.resource_generator_window._QuickImageRotateDialog", _FakeDialog)
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {"img": [{"file": "hero.png", "name": "hero"}], "font": [], "mp4": []},
            dirty=False,
        )
        window._simple_asset_table.selectRow(0)
        qapp.processEvents()

        window._open_rotate_image_helper()

        rotated_path = source_dir / "variants" / "hero_right.png"
        rotated = QPixmap(str(rotated_path))
        assert rotated.width() == 8
        assert rotated.height() == 12
        files = [entry["file"] for entry in window._session.section_entries("img")]
        assert files == ["hero.png", "variants/hero_right.png"]
        assert window.has_unsaved_changes() is True
        assert window._status_label.text() == "Created rotated image 'variants/hero_right.png' (8 x 12)."
        _close_window(window)

    @_skip_no_qt
    def test_flip_image_helper_overwrites_selected_image(self, qapp, monkeypatch, tmp_path):
        from PyQt5.QtGui import QPixmap
        from PyQt5.QtWidgets import QDialog

        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        image_path = source_dir / "hero.png"
        pixmap = QPixmap(12, 8)
        assert pixmap.save(str(image_path), "PNG")

        class _FakeDialog:
            def __init__(self, *, output_filename, parent=None):
                assert output_filename == "hero.png"

            def exec_(self):
                return QDialog.Accepted

            def output_filename(self):
                return "hero.png"

            def flip_mode(self):
                return "horizontal"

        monkeypatch.setattr("ui_designer.ui.resource_generator_window._QuickImageFlipDialog", _FakeDialog)

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {"img": [{"file": "hero.png", "name": "hero"}], "font": [], "mp4": []},
            dirty=False,
        )
        window._simple_asset_table.selectRow(0)
        qapp.processEvents()

        window._open_flip_image_helper()

        flipped = QPixmap(str(image_path))
        assert flipped.width() == 12
        assert flipped.height() == 8
        assert len(window._session.section_entries("img")) == 1
        assert window._status_label.text() == "Updated horizontal-flipped image 'hero.png' (12 x 8)."
        _close_window(window)

    @_skip_no_qt
    def test_flip_image_helper_can_create_new_image_entry(self, qapp, monkeypatch, tmp_path):
        from PyQt5.QtGui import QPixmap
        from PyQt5.QtWidgets import QDialog, QMessageBox

        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        image_path = source_dir / "hero.png"
        pixmap = QPixmap(12, 8)
        assert pixmap.save(str(image_path), "PNG")

        class _FakeDialog:
            def __init__(self, *, output_filename, parent=None):
                assert output_filename == "hero.png"

            def exec_(self):
                return QDialog.Accepted

            def output_filename(self):
                return "variants/hero_mirror.png"

            def flip_mode(self):
                return "vertical"

        monkeypatch.setattr("ui_designer.ui.resource_generator_window._QuickImageFlipDialog", _FakeDialog)
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {"img": [{"file": "hero.png", "name": "hero"}], "font": [], "mp4": []},
            dirty=False,
        )
        window._simple_asset_table.selectRow(0)
        qapp.processEvents()

        window._open_flip_image_helper()

        flipped_path = source_dir / "variants" / "hero_mirror.png"
        flipped = QPixmap(str(flipped_path))
        assert flipped.width() == 12
        assert flipped.height() == 8
        files = [entry["file"] for entry in window._session.section_entries("img")]
        assert files == ["hero.png", "variants/hero_mirror.png"]
        assert window.has_unsaved_changes() is True
        assert window._status_label.text() == "Created vertical-flipped image 'variants/hero_mirror.png' (12 x 8)."
        _close_window(window)

    @_skip_no_qt
    def test_crop_image_helper_overwrites_selected_image(self, qapp, monkeypatch, tmp_path):
        from PyQt5.QtGui import QPixmap
        from PyQt5.QtWidgets import QDialog

        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        image_path = source_dir / "hero.png"
        pixmap = QPixmap(12, 8)
        assert pixmap.save(str(image_path), "PNG")

        class _FakeDialog:
            def __init__(self, *, width, height, output_filename, parent=None):
                assert width == 12
                assert height == 8
                assert output_filename == "hero.png"

            def exec_(self):
                return QDialog.Accepted

            def output_filename(self):
                return "hero.png"

            def x_value(self):
                return 2

            def y_value(self):
                return 1

            def width_value(self):
                return 6

            def height_value(self):
                return 4

        monkeypatch.setattr("ui_designer.ui.resource_generator_window._QuickImageCropDialog", _FakeDialog)

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {"img": [{"file": "hero.png", "name": "hero"}], "font": [], "mp4": []},
            dirty=False,
        )
        window._simple_asset_table.selectRow(0)
        qapp.processEvents()

        window._open_crop_image_helper()

        cropped = QPixmap(str(image_path))
        assert cropped.width() == 6
        assert cropped.height() == 4
        assert len(window._session.section_entries("img")) == 1
        assert window._status_label.text() == "Updated cropped image 'hero.png' (6 x 4)."
        _close_window(window)

    @_skip_no_qt
    def test_crop_image_helper_can_create_new_image_entry(self, qapp, monkeypatch, tmp_path):
        from PyQt5.QtGui import QPixmap
        from PyQt5.QtWidgets import QDialog, QMessageBox

        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        image_path = source_dir / "hero.png"
        pixmap = QPixmap(12, 8)
        assert pixmap.save(str(image_path), "PNG")

        class _FakeDialog:
            def __init__(self, *, width, height, output_filename, parent=None):
                assert width == 12
                assert height == 8
                assert output_filename == "hero.png"

            def exec_(self):
                return QDialog.Accepted

            def output_filename(self):
                return "variants/hero_crop.png"

            def x_value(self):
                return 1

            def y_value(self):
                return 2

            def width_value(self):
                return 5

            def height_value(self):
                return 3

        monkeypatch.setattr("ui_designer.ui.resource_generator_window._QuickImageCropDialog", _FakeDialog)
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {"img": [{"file": "hero.png", "name": "hero"}], "font": [], "mp4": []},
            dirty=False,
        )
        window._simple_asset_table.selectRow(0)
        qapp.processEvents()

        window._open_crop_image_helper()

        cropped_path = source_dir / "variants" / "hero_crop.png"
        cropped = QPixmap(str(cropped_path))
        assert cropped.width() == 5
        assert cropped.height() == 3
        files = [entry["file"] for entry in window._session.section_entries("img")]
        assert files == ["hero.png", "variants/hero_crop.png"]
        assert window.has_unsaved_changes() is True
        assert window._status_label.text() == "Created cropped image 'variants/hero_crop.png' (5 x 3)."
        _close_window(window)

    @_skip_no_qt
    def test_normalize_selected_image_requires_source_dir(self, qapp, monkeypatch, tmp_path):
        from ui_designer.model.resource_generation_session import RESOURCE_SECTION_SPECS
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        image_path = tmp_path / "hero.png"
        image_path.write_bytes(b"png")

        warnings = []
        monkeypatch.setattr(
            QMessageBox,
            "warning",
            lambda *args: warnings.append((args[1], args[2])) or QMessageBox.Ok,
        )

        window = ResourceGeneratorWindow("")

        result = window._normalize_selected_resource_path(RESOURCE_SECTION_SPECS["img"].fields[0], str(image_path))

        assert result is None
        assert warnings == [
            (
                "Source Directory Missing",
                "Set Source Dir before importing files that must be stored relative to it.",
            )
        ]
        _close_window(window)

    @_skip_no_qt
    def test_normalize_selected_image_copies_external_file_into_source_dir(self, qapp, monkeypatch, tmp_path):
        from ui_designer.model.resource_generation_session import RESOURCE_SECTION_SPECS
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        external_file = tmp_path / "imports" / "hero.png"
        external_file.parent.mkdir(parents=True)
        external_file.write_bytes(b"image-data")

        prompts = []
        monkeypatch.setattr(
            QMessageBox,
            "question",
            lambda *args, **kwargs: prompts.append((args[1], args[2])) or QMessageBox.Yes,
        )

        window = ResourceGeneratorWindow("")
        window._session.paths.source_dir = str(source_dir)

        result = window._normalize_selected_resource_path(RESOURCE_SECTION_SPECS["img"].fields[0], str(external_file))

        copied_file = source_dir / external_file.name
        assert result == external_file.name
        assert copied_file.read_bytes() == b"image-data"
        assert prompts == [
            (
                "Copy Into Source Dir",
                f"{external_file}\n\nCopy this file into:\n{source_dir}\n\nRequired for generation.",
            )
        ]
        _close_window(window)

    @_skip_no_qt
    def test_normalize_selected_font_file_keeps_absolute_path_outside_source_dir(self, qapp, monkeypatch, tmp_path):
        from ui_designer.model.resource_generation_session import RESOURCE_SECTION_SPECS
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow
        from ui_designer.model.workspace import normalize_path

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        external_font = tmp_path / "fonts" / "display.ttf"
        external_font.parent.mkdir(parents=True)
        external_font.write_bytes(b"font-data")

        prompts = []
        monkeypatch.setattr(
            QMessageBox,
            "question",
            lambda *args, **kwargs: prompts.append((args[1], args[2])) or QMessageBox.Yes,
        )

        window = ResourceGeneratorWindow("")
        window._active_section = "font"
        window._session.paths.source_dir = str(source_dir)

        result = window._normalize_selected_resource_path(RESOURCE_SECTION_SPECS["font"].fields[0], str(external_font))

        assert result == normalize_path(str(external_font))
        assert prompts == []
        _close_window(window)

    @_skip_no_qt
    def test_browse_font_text_duplicate_keeps_clean_state(self, qapp, monkeypatch, tmp_path):
        from PyQt5.QtWidgets import QFileDialog

        from ui_designer.model.resource_generation_session import GenerationPaths, RESOURCE_SECTION_SPECS
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        text_file = source_dir / "charset" / "basic.txt"
        text_file.parent.mkdir(parents=True)
        text_file.write_text("abc", encoding="utf-8")

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {"img": [], "font": [{"file": "display.ttf", "text": "charset/basic.txt"}], "mp4": []},
            dirty=False,
        )
        window._active_section = "font"
        window._active_entry_index = 0
        window._refresh_entry_table()

        text_field = next(field for field in RESOURCE_SECTION_SPECS["font"].fields if field.name == "text")
        monkeypatch.setattr(
            QFileDialog,
            "getOpenFileName",
            lambda *args, **kwargs: (str(text_file), text_field.file_filter),
        )

        window._browse_entry_field(text_field)

        entry = window._session.section_entries("font")[0]
        assert entry["text"] == "charset/basic.txt"
        assert window.has_unsaved_changes() is False
        _close_window(window)

    @_skip_no_qt
    def test_generate_charset_helper_writes_text_file_and_assigns_current_font(self, qapp, monkeypatch, tmp_path):
        from PyQt5.QtWidgets import QDialog

        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        captured = {}

        class _FakeDialog:
            def __init__(self, resource_dir, initial_filename="", source_label="", initial_preset_ids=(), parent=None):
                captured["resource_dir"] = resource_dir
                captured["initial_filename"] = initial_filename
                captured["source_label"] = source_label
                captured["initial_preset_ids"] = tuple(initial_preset_ids or ())

            def exec_(self):
                return QDialog.Accepted

            def filename(self):
                return "display_charset.txt"

            def generated_text(self):
                return "A\nB\n"

            def overwrite_diff(self):
                return SimpleNamespace(existing_count=0, new_count=2, added_count=2, removed_count=0)

        monkeypatch.setattr("ui_designer.ui.resource_generator_window._GenerateCharsetDialog", _FakeDialog)
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {"img": [], "font": [{"file": "display.ttf", "text": ""}], "mp4": []},
            dirty=False,
        )
        window._active_section = "font"
        window._active_entry_index = 0
        window._refresh_entry_table()

        window._open_generate_charset_helper()

        assert captured["resource_dir"] == str(source_dir)
        assert captured["initial_filename"] == "display_charset.txt"
        assert captured["source_label"] == "display.ttf"
        assert (source_dir / "display_charset.txt").read_text(encoding="utf-8") == "A\nB\n"
        assert window._session.section_entries("font")[0]["text"] == "display_charset.txt"
        assert window.has_unsaved_changes() is True
        _close_window(window)

    @_skip_no_qt
    def test_new_config_clears_entries_but_keeps_paths(self, qapp, tmp_path):
        from ui_designer.model.resource_generation_session import infer_generation_paths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow
        from ui_designer.utils.resource_config_overlay import make_empty_resource_config

        config_path = tmp_path / "DemoApp" / "resource" / "src" / "app_resource_config.json"
        paths = infer_generation_paths(str(config_path))

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            paths,
            {
                "img": [{"file": "hero.png", "format": "rgb565"}],
                "font": [{"file": "display.ttf", "text": "charset/basic.txt"}],
                "mp4": [{"file": "intro.mp4"}],
            },
            dirty=False,
        )

        window._new_config()

        assert window._session.paths == paths
        assert window._session.user_data == make_empty_resource_config()
        assert window.has_unsaved_changes() is False
        assert window._status_label.text() == "New resource config ready."
        assert window.windowTitle() == f"Resource Generator - {paths.config_path}"
        _close_window(window)

    @_skip_no_qt
    def test_main_window_close_is_blocked_when_resource_generator_cancelled(self, qapp, monkeypatch, tmp_path):
        from PyQt5.QtGui import QCloseEvent

        from ui_designer.ui.main_window import MainWindow

        sdk_root = build_test_sdk_root(tmp_path / "sdk")
        window = MainWindow(str(sdk_root))

        window._open_resource_generator_window()
        qapp.processEvents()
        generator_window = window._resource_generator_window
        assert generator_window is not None
        generator_window._dirty = True

        monkeypatch.setattr("ui_designer.ui.resource_generator_window.QMessageBox.question", lambda *args, **kwargs: QMessageBox.No)

        event = QCloseEvent()
        window.closeEvent(event)

        assert event.isAccepted() is False
        assert window._is_closing is False
        assert generator_window.isVisible() is True

        monkeypatch.setattr("ui_designer.ui.resource_generator_window.QMessageBox.question", lambda *args, **kwargs: QMessageBox.Yes)
        _close_window(generator_window)
        _close_window(window)

    @_skip_no_qt
    def test_close_event_prompts_for_path_only_changes(self, qapp, monkeypatch):
        from PyQt5.QtGui import QCloseEvent

        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        prompts = []
        monkeypatch.setattr(
            QMessageBox,
            "question",
            lambda *args, **kwargs: prompts.append(args[1:3]) or QMessageBox.No,
        )

        window = ResourceGeneratorWindow("")
        window.show()
        qapp.processEvents()
        window._config_path_edit.setText("D:/tmp/app_resource_config.json")
        window._on_path_edited("config_path", window._config_path_edit)

        event = QCloseEvent()
        window.closeEvent(event)

        assert window.has_unsaved_changes() is True
        assert prompts == [("Discard Changes", "Discard unsaved resource config changes?")]
        assert event.isAccepted() is False

        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)
        _close_window(window)

    @_skip_no_qt
    def test_main_window_close_is_blocked_by_path_only_changes_in_resource_generator(self, qapp, monkeypatch, tmp_path):
        from PyQt5.QtGui import QCloseEvent

        from ui_designer.ui.main_window import MainWindow

        sdk_root = build_test_sdk_root(tmp_path / "sdk")
        window = MainWindow(str(sdk_root))

        window._open_resource_generator_window()
        qapp.processEvents()
        generator_window = window._resource_generator_window
        assert generator_window is not None
        generator_window._config_path_edit.setText("D:/tmp/app_resource_config.json")
        generator_window._on_path_edited("config_path", generator_window._config_path_edit)

        monkeypatch.setattr("ui_designer.ui.resource_generator_window.QMessageBox.question", lambda *args, **kwargs: QMessageBox.No)

        event = QCloseEvent()
        window.closeEvent(event)

        assert generator_window.has_unsaved_changes() is True
        assert event.isAccepted() is False
        assert window._is_closing is False
        assert generator_window.isVisible() is True

        monkeypatch.setattr("ui_designer.ui.resource_generator_window.QMessageBox.question", lambda *args, **kwargs: QMessageBox.Yes)
        _close_window(generator_window)
        _close_window(window)

    @_skip_no_qt
    def test_generate_resources_logs_success_result(self, qapp, monkeypatch, tmp_path):
        from ui_designer.model.resource_generation_session import ResourceGenerationResult
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        warnings = []
        monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args[2]) or QMessageBox.Ok)
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)

        window = ResourceGeneratorWindow("")
        monkeypatch.setattr(window._session, "validation_issues", lambda for_generation=True: [])
        monkeypatch.setattr(
            window._session,
            "run_generation",
            lambda: ResourceGenerationResult(
                success=True,
                command=["python", "app_resource_generate.py", "-r", str(tmp_path / "resource"), "-o", str(tmp_path / "output")],
                stdout="generated from staged config\n",
                stderr="",
                issues=[],
            ),
        )

        window._generate_resources()
        qapp.processEvents()

        log_text = window._log_output.toPlainText()
        assert "Resource generation completed successfully." in log_text
        assert "generated from staged config" in log_text
        assert "app_resource_generate.py" in log_text
        assert window._status_label.text() == "Resource generation completed."
        assert warnings == []
        _close_window(window)
