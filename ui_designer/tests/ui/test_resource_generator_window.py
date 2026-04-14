import json
from types import SimpleNamespace

import pytest

from ui_designer.model.resource_generation_session import infer_generation_paths
from ui_designer.tests.qt_test_utils import HAS_PYQT5, skip_if_no_qt
from ui_designer.tests.sdk_builders import build_test_sdk_root
from ui_designer.tests.ui.window_test_helpers import close_test_window as _close_window

if HAS_PYQT5:
    from PyQt5.QtCore import QEvent, Qt, QUrl
    from PyQt5.QtWidgets import QApplication, QGroupBox, QHeaderView, QLabel, QMessageBox


_skip_no_qt = skip_if_no_qt


class _FakeUrlMimeData:
    def __init__(self, paths):
        self._urls = [QUrl.fromLocalFile(str(path)) for path in paths]

    def hasUrls(self):
        return True

    def urls(self):
        return self._urls


class _FakeUrlDropEvent:
    def __init__(self, paths):
        self._mime = _FakeUrlMimeData(paths)
        self.accepted = False
        self.ignored = False

    def mimeData(self):
        return self._mime

    def acceptProposedAction(self):
        self.accepted = True

    def ignore(self):
        self.ignored = True


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
    def test_resource_generator_window_supports_maximize_and_syncs_native_chrome_theme(self, qapp, monkeypatch):
        import ui_designer.ui.resource_generator_window as resource_generator_window_module

        synced_windows = []
        monkeypatch.setattr(
            resource_generator_window_module,
            "sync_window_chrome_theme",
            lambda window: synced_windows.append(window) or True,
        )

        window = resource_generator_window_module.ResourceGeneratorWindow("")

        assert window.windowFlags() & Qt.Window
        assert window.windowFlags() & Qt.WindowMinMaxButtonsHint
        assert window.windowFlags() & Qt.WindowMaximizeButtonHint

        window.show()
        qapp.processEvents()
        assert synced_windows == [window]

        window.changeEvent(QEvent(QEvent.StyleChange))
        assert synced_windows[-1] is window
        assert len(synced_windows) >= 2
        _close_window(window)

    @_skip_no_qt
    def test_simple_mode_groups_actions_for_guided_flow(self, qapp):
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        window = ResourceGeneratorWindow("")

        group_titles = {group.title() for group in window._simple_page.findChildren(QGroupBox)}
        assert {"Import & Setup", "Batch Fixes", "Preview & Open", "Image Tools", "Selection"} <= group_titles
        assert [window._simple_action_tabs.tabText(index) for index in range(window._simple_action_tabs.count())] == [
            "Start",
            "Clean",
            "Inspect",
            "Transforms",
            "Selection",
        ]
        _close_window(window)

    @_skip_no_qt
    def test_simple_mode_uses_resizable_vertical_panels_and_compact_category_headers(self, qapp):
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        window = ResourceGeneratorWindow("")
        tab_bar = window._simple_action_tabs.tabBar()

        assert window._simple_workspace_splitter.orientation() == Qt.Vertical
        assert window._simple_workspace_splitter.count() == 3
        assert window._simple_workspace_splitter.childrenCollapsible() is False
        assert window._simple_workspace_splitter.handleWidth() == 8
        assert window._simple_action_tabs.documentMode() is True
        assert window._simple_actions_scroll.widget() is window._simple_action_tabs
        assert tab_bar.minimumHeight() == 24
        assert tab_bar.maximumHeight() == 24
        assert tab_bar.font().pointSize() == 9
        _close_window(window)

    @_skip_no_qt
    def test_simple_mode_asset_table_allows_interactive_column_resize(self, qapp):
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        window = ResourceGeneratorWindow("")
        header = window._simple_asset_table.horizontalHeader()

        assert header.sectionResizeMode(0) == QHeaderView.Interactive
        assert header.sectionResizeMode(1) == QHeaderView.Interactive
        assert header.sectionResizeMode(2) == QHeaderView.Interactive
        assert header.sectionResizeMode(3) == QHeaderView.Interactive
        assert header.height() >= 24
        assert header.font().pointSize() == 10
        assert window._simple_asset_table.verticalHeader().defaultSectionSize() >= window.fontMetrics().height() + 12
        _close_window(window)

    @_skip_no_qt
    def test_simple_mode_shows_empty_state_before_assets_are_imported(self, qapp):
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        window = ResourceGeneratorWindow("")

        assert window._simple_asset_content_stack.currentWidget() is window._simple_asset_empty_state
        assert window._simple_asset_empty_title.text() == "No assets imported yet."
        assert window._simple_asset_empty_import_button.isHidden() is False
        assert window._simple_asset_empty_scan_button.isHidden() is False
        assert window._simple_asset_empty_clear_button.isHidden() is True
        _close_window(window)

    @_skip_no_qt
    def test_simple_mode_asset_filters_reduce_visible_rows(self, qapp, tmp_path):
        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {
                "img": [{"file": "hero.png", "name": "hero", "format": "rgb565", "alpha": "4"}],
                "font": [{"file": "display.ttf", "name": "display", "pixelsize": "18", "fontbitsize": "4", "text": "charset/display.txt"}],
                "mp4": [{"file": "intro.mp4", "name": "intro", "fps": 24, "width": 320, "height": 180}],
            },
            dirty=False,
        )

        window._simple_asset_type_filter.setCurrentIndex(window._simple_asset_type_filter.findData("font"))
        window._simple_asset_search_edit.setText("display")
        qapp.processEvents()

        assert window._simple_asset_table.rowCount() == 1
        assert window._simple_asset_table.item(0, 1).text() == "display"
        assert window._simple_asset_table.item(0, 3).text() == "18px | 4-bit | charset/display.txt"
        assert window._simple_asset_result_label.text() == "Showing 1 of 3 assets"
        _close_window(window)

    @_skip_no_qt
    def test_simple_mode_empty_state_switches_to_clear_filters_when_search_has_no_results(self, qapp, tmp_path):
        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {"img": [{"file": "hero.png", "name": "hero"}]},
            dirty=False,
        )

        assert window._simple_asset_content_stack.currentWidget() is window._simple_asset_table

        window._simple_asset_search_edit.setText("missing")
        qapp.processEvents()

        assert window._simple_asset_content_stack.currentWidget() is window._simple_asset_empty_state
        assert window._simple_asset_empty_title.text() == "No assets match the current filters."
        assert window._simple_asset_empty_import_button.isHidden() is True
        assert window._simple_asset_empty_scan_button.isHidden() is True
        assert window._simple_asset_empty_clear_button.isHidden() is False

        window._simple_asset_empty_clear_button.click()
        qapp.processEvents()

        assert window._simple_asset_search_edit.text() == ""
        assert window._simple_asset_content_stack.currentWidget() is window._simple_asset_table
        _close_window(window)

    @_skip_no_qt
    def test_simple_mode_selection_actions_track_selected_asset_type(self, qapp, tmp_path):
        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {
                "img": [{"file": "hero.png", "name": "hero"}],
                "font": [{"file": "display.ttf", "name": "display", "text": "charset/display.txt"}],
                "mp4": [{"file": "intro.mp4", "name": "intro", "fps": 24, "width": 320, "height": 180}],
            },
            dirty=False,
        )

        window._simple_asset_table.clearSelection()
        qapp.processEvents()

        assert window._duplicate_simple_asset_button.isEnabled() is False
        assert window._remove_simple_asset_button.isEnabled() is False
        assert window._resize_image_button.isEnabled() is False
        assert window._open_font_text_button.isEnabled() is False
        assert window._detect_video_info_button.isEnabled() is False

        window._simple_asset_table.selectRow(0)
        qapp.processEvents()
        assert window._duplicate_simple_asset_button.isEnabled() is True
        assert window._remove_simple_asset_button.isEnabled() is True
        assert window._resize_image_button.isEnabled() is True
        assert window._open_font_text_button.isEnabled() is False
        assert window._detect_video_info_button.isEnabled() is False

        window._simple_asset_table.selectRow(1)
        qapp.processEvents()
        assert window._resize_image_button.isEnabled() is False
        assert window._open_font_text_button.isEnabled() is True
        assert window._detect_video_info_button.isEnabled() is False

        window._simple_asset_table.selectRow(2)
        qapp.processEvents()
        assert window._resize_image_button.isEnabled() is False
        assert window._open_font_text_button.isEnabled() is False
        assert window._detect_video_info_button.isEnabled() is True
        _close_window(window)

    @_skip_no_qt
    def test_resource_generator_exposes_keyboard_shortcuts_for_common_resource_actions(self, qapp, monkeypatch):
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        window = ResourceGeneratorWindow("")
        window.show()
        qapp.processEvents()

        assert window._new_button.shortcut().toString() == "Ctrl+N"
        assert window._open_button.shortcut().toString() == "Ctrl+O"
        assert window._save_button.shortcut().toString() == "Ctrl+S"
        assert window._save_as_button.shortcut().toString() == "Ctrl+Shift+S"
        assert window._generate_button.shortcut().toString() == "Ctrl+Return"
        assert set(window._window_shortcuts) >= {"Ctrl+F", "Delete", "Ctrl+D", "Ctrl+E"}

        activated = []
        monkeypatch.setattr(window, "_remove_selected_simple_asset", lambda: activated.append("delete"))
        monkeypatch.setattr(window, "_duplicate_selected_simple_asset", lambda: activated.append("duplicate"))

        window._remove_simple_asset_button.setEnabled(True)
        window._duplicate_simple_asset_button.setEnabled(True)
        window._window_shortcuts["Delete"].activated.emit()
        window._window_shortcuts["Ctrl+D"].activated.emit()
        window._window_shortcuts["Ctrl+F"].activated.emit()
        qapp.processEvents()

        assert activated == ["delete", "duplicate"]
        assert window._simple_asset_search_edit.hasFocus() is True
        _close_window(window)

    @_skip_no_qt
    def test_resource_generator_persists_and_restores_quick_view_state(self, qapp, isolated_config, tmp_path):
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        window = ResourceGeneratorWindow("")
        window.show()
        qapp.processEvents()

        window._simple_asset_type_filter.setCurrentIndex(window._simple_asset_type_filter.findData("font"))
        window._simple_asset_search_edit.setText("display")
        header = window._simple_asset_table.horizontalHeader()
        header.resizeSection(0, 104)
        header.resizeSection(1, 248)
        header.resizeSection(2, 432)
        header.resizeSection(3, 308)
        window._simple_workspace_splitter.setSizes([160, 420, 260])
        window._simple_preview_splitter.setSizes([280, 620])
        window._set_ui_mode("professional")
        qapp.processEvents()

        expected_state = window._capture_view_state()
        _close_window(window)

        assert isolated_config.workspace_state["resource_generator_view"] == expected_state
        saved_config = json.loads((tmp_path / "config" / "config.json").read_text(encoding="utf-8"))
        assert saved_config["workspace_state"]["resource_generator_view"] == expected_state

        reopened = ResourceGeneratorWindow("")
        reopened.show()
        qapp.processEvents()

        assert reopened._workspace_stack.currentWidget() is reopened._professional_page
        assert reopened._capture_view_state() == expected_state
        _close_window(reopened)

    @_skip_no_qt
    def test_resource_generator_accepts_drag_for_supported_asset_file(self, qapp, tmp_path):
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        image_path = tmp_path / "hero.png"
        image_path.write_bytes(b"png")
        window = ResourceGeneratorWindow("")
        event = _FakeUrlDropEvent([image_path])

        window.dragEnterEvent(event)

        assert event.accepted is True
        assert event.ignored is False
        _close_window(window)

    @_skip_no_qt
    def test_resource_generator_drop_single_directory_scans_assets(self, qapp, monkeypatch, tmp_path):
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        asset_dir = tmp_path / "bundle"
        asset_dir.mkdir()
        window = ResourceGeneratorWindow("")
        scanned = []
        imported = []
        monkeypatch.setattr(window, "_scan_assets_from_directory", lambda path: scanned.append(path))
        monkeypatch.setattr(window, "_import_assets_from_files", lambda paths: imported.append(list(paths)))
        event = _FakeUrlDropEvent([asset_dir])

        window.dropEvent(event)

        assert scanned == [str(asset_dir)]
        assert imported == []
        assert event.accepted is True
        assert event.ignored is False
        _close_window(window)

    @_skip_no_qt
    def test_resource_generator_drop_mixed_files_and_directories_imports_supported_assets(self, qapp, monkeypatch, tmp_path):
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        asset_dir = tmp_path / "bundle"
        asset_dir.mkdir()
        nested_dir = asset_dir / "nested"
        nested_dir.mkdir()
        image_path = asset_dir / "hero.png"
        font_path = nested_dir / "display.ttf"
        text_path = nested_dir / "display.txt"
        external_video = tmp_path / "intro.mp4"
        unsupported = tmp_path / "notes.md"
        image_path.write_bytes(b"png")
        font_path.write_bytes(b"ttf")
        text_path.write_text("ABCD", encoding="utf-8")
        external_video.write_bytes(b"mp4")
        unsupported.write_text("ignore", encoding="utf-8")

        window = ResourceGeneratorWindow("")
        imported = []
        scanned = []
        monkeypatch.setattr(window, "_import_assets_from_files", lambda paths: imported.append(list(paths)))
        monkeypatch.setattr(window, "_scan_assets_from_directory", lambda path: scanned.append(path))
        event = _FakeUrlDropEvent([asset_dir, external_video, unsupported])

        window.dropEvent(event)

        assert scanned == []
        assert len(imported) == 1
        assert imported[0][0] == str(external_video)
        assert set(imported[0][1:]) == {str(image_path), str(font_path), str(text_path)}
        assert event.accepted is True
        assert event.ignored is False
        _close_window(window)

    @_skip_no_qt
    def test_simple_asset_context_menu_exposes_copy_and_open_actions(self, qapp, tmp_path):
        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        fonts_dir = source_dir / "fonts"
        fonts_dir.mkdir(parents=True)
        font_path = fonts_dir / "display.ttf"
        text_path = fonts_dir / "display.txt"
        font_path.write_bytes(b"ttf")
        text_path.write_text("ABCD", encoding="utf-8")

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {"font": [{"file": "fonts/display.ttf", "name": "display", "text": "fonts/display.txt"}]},
            dirty=False,
        )
        window._simple_asset_table.selectRow(0)
        qapp.processEvents()

        menu = window._build_simple_asset_context_menu()
        action_map = {action.text(): action for action in menu.actions() if action.text()}

        assert {"Preview Asset", "Open Asset", "Open Asset Folder", "Open Font Text", "Copy Resource Name", "Copy Asset Path", "Copy Full Path", "Duplicate", "Remove", "Open Professional Mode"} <= set(action_map)
        assert action_map["Open Asset"].isEnabled() is True
        assert action_map["Copy Full Path"].isEnabled() is True

        QApplication.clipboard().clear()
        action_map["Copy Resource Name"].trigger()
        assert QApplication.clipboard().text() == "display"

        action_map["Copy Asset Path"].trigger()
        assert QApplication.clipboard().text() == "fonts/display.ttf"

        action_map["Copy Full Path"].trigger()
        assert QApplication.clipboard().text() == str(font_path)
        _close_window(window)

    @_skip_no_qt
    def test_simple_asset_context_menu_disables_file_actions_for_missing_asset(self, qapp, tmp_path):
        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {"img": [{"file": "images/missing.png", "name": "missing"}]},
            dirty=False,
        )
        window._simple_asset_table.selectRow(0)
        qapp.processEvents()

        menu = window._build_simple_asset_context_menu()
        action_map = {action.text(): action for action in menu.actions() if action.text()}

        assert action_map["Open Asset"].isEnabled() is False
        assert action_map["Open Asset Folder"].isEnabled() is False
        assert action_map["Copy Asset Path"].isEnabled() is True
        assert action_map["Copy Full Path"].isEnabled() is False
        _close_window(window)

    @_skip_no_qt
    def test_build_quick_preview_board_dialog_includes_all_assets(self, qapp, monkeypatch, tmp_path):
        from PyQt5.QtGui import QPixmap

        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        (source_dir / "fonts").mkdir(parents=True)
        image_path = source_dir / "hero.png"
        pixmap = QPixmap(12, 8)
        assert pixmap.save(str(image_path), "PNG")
        (source_dir / "fonts" / "display.ttf").write_bytes(b"ttf")
        (source_dir / "fonts" / "display.txt").write_text("ABCD", encoding="utf-8")
        (source_dir / "intro.mp4").write_bytes(b"mp4")
        monkeypatch.setattr(
            "ui_designer.ui.resource_generator_window.ResourceGeneratorWindow._build_font_preview_pixmap",
            lambda self, font_path, sample_text, entry=None: QPixmap(32, 20),
        )

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {
                "img": [{"file": "hero.png", "name": "hero"}],
                "font": [{"file": "fonts/display.ttf", "name": "display", "text": "fonts/display.txt"}],
                "mp4": [{"file": "intro.mp4", "name": "intro", "fps": 24, "width": 320, "height": 180}],
            },
            dirty=False,
        )

        dialog = window._build_quick_preview_board_dialog()

        assert dialog is not None
        assert dialog._summary_label.text() == "Previewing 3 assets from quick mode."
        cards = dialog.findChildren(QGroupBox, "quick_preview_card")
        assert {card.title() for card in cards} == {"Images: hero", "Fonts: display", "MP4: intro"}
        meta_labels = dialog.findChildren(QLabel, "quick_preview_meta")
        assert any("Image Size: 12 x 8" in label.text() for label in meta_labels)
        assert any("Preview Source: fonts/display.txt" in label.text() for label in meta_labels)
        assert any("Video: 24fps 320x180" in label.text() for label in meta_labels)
        dialog.close()
        _close_window(window)

    @_skip_no_qt
    def test_export_quick_preview_board_image_writes_png(self, qapp, monkeypatch, tmp_path):
        from PyQt5.QtGui import QImage, QPixmap

        from ui_designer.model.workspace import normalize_path
        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        (source_dir / "fonts").mkdir(parents=True)
        image_path = source_dir / "hero.png"
        pixmap = QPixmap(16, 10)
        assert pixmap.save(str(image_path), "PNG")
        (source_dir / "fonts" / "display.ttf").write_bytes(b"ttf")
        (source_dir / "fonts" / "display.txt").write_text("ABCD", encoding="utf-8")
        (source_dir / "intro.mp4").write_bytes(b"mp4")
        monkeypatch.setattr(
            "ui_designer.ui.resource_generator_window.ResourceGeneratorWindow._build_font_preview_pixmap",
            lambda self, font_path, sample_text, entry=None: QPixmap(40, 24),
        )

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {
                "img": [{"file": "hero.png", "name": "hero"}],
                "font": [{"file": "fonts/display.ttf", "name": "display", "text": "fonts/display.txt"}],
                "mp4": [{"file": "intro.mp4", "name": "intro", "fps": 24, "width": 320, "height": 180}],
            },
            dirty=False,
        )

        output_path = tmp_path / "preview_board.png"
        assert window._export_quick_preview_board_image(str(output_path)) is True

        exported = QImage(str(output_path))
        assert output_path.is_file()
        assert exported.isNull() is False
        assert exported.width() > 500
        assert exported.height() > 300
        assert window._status_label.text() == f"Exported preview board to '{normalize_path(str(output_path))}'."
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
        assert window._simple_asset_table.item(0, 3).text() == "24fps | 320x180 | rgb565 | a0"
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
    def test_refresh_all_video_metadata_updates_entries_and_simple_table(self, qapp, monkeypatch, tmp_path):
        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        (source_dir / "intro.mp4").write_bytes(b"mp4")
        (source_dir / "loop.mp4").write_bytes(b"mp4")
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)
        monkeypatch.setattr(
            "ui_designer.ui.resource_generator_window._detect_video_metadata",
            lambda path: (
                {"fps": 24, "width": 320, "height": 180}
                if path.endswith("intro.mp4")
                else {"fps": 12, "width": 160, "height": 90}
            ),
        )

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {
                "img": [],
                "font": [],
                "mp4": [
                    {"file": "intro.mp4", "name": "intro", "fps": 1, "width": 2, "height": 3},
                    {"file": "loop.mp4", "name": "loop"},
                ],
            },
            dirty=False,
        )

        window._refresh_all_video_metadata()

        intro = window._session.section_entries("mp4")[0]
        loop = window._session.section_entries("mp4")[1]
        assert intro["fps"] == 24
        assert intro["width"] == 320
        assert intro["height"] == 180
        assert loop["fps"] == 12
        assert loop["width"] == 160
        assert loop["height"] == 90
        assert window._simple_asset_table.item(0, 3).text() == "24fps | 320x180"
        assert window._simple_asset_table.item(1, 3).text() == "12fps | 160x90"
        assert window.has_unsaved_changes() is True
        assert window._status_label.text() == "Refreshed video metadata for 2 videos."
        _close_window(window)

    @_skip_no_qt
    def test_refresh_font_text_links_updates_entries_and_simple_table(self, qapp, monkeypatch, tmp_path):
        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        (source_dir / "fonts").mkdir(parents=True)
        (source_dir / "fonts" / "display.ttf").write_bytes(b"ttf")
        (source_dir / "fonts" / "display.txt").write_text("ABC", encoding="utf-8")
        (source_dir / "title.ttf").write_bytes(b"ttf")
        (source_dir / "title.txt").write_text("XYZ", encoding="utf-8")
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {
                "img": [],
                "font": [
                    {"file": "fonts/display.ttf", "name": "display", "text": "stale.txt"},
                    {"file": "title.ttf", "name": "title"},
                ],
                "mp4": [],
            },
            dirty=False,
        )

        window._refresh_font_text_links()

        display = window._session.section_entries("font")[0]
        title = window._session.section_entries("font")[1]
        assert display["text"] == "fonts/display.txt"
        assert title["text"] == "title.txt"
        assert window._simple_asset_table.item(0, 3).text() == "fonts/display.txt"
        assert window._simple_asset_table.item(1, 3).text() == "title.txt"
        assert window.has_unsaved_changes() is True
        assert window._status_label.text() == "Refreshed font text links for 2 fonts."
        _close_window(window)

    @_skip_no_qt
    def test_auto_create_font_text_resources_creates_missing_files_and_updates_links(self, qapp, monkeypatch, tmp_path):
        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.services.font_charset_presets import build_charset, serialize_charset_chars
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        (source_dir / "display.ttf").write_bytes(b"ttf")
        (source_dir / "title.ttf").write_bytes(b"ttf")
        (source_dir / "title.txt").write_text("XYZ", encoding="utf-8")
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {
                "img": [],
                "font": [
                    {"file": "display.ttf", "name": "display"},
                    {"file": "title.ttf", "name": "title"},
                ],
                "mp4": [],
            },
            dirty=False,
        )

        window._auto_create_font_text_resources()

        expected_charset = serialize_charset_chars(build_charset(("ascii_printable",)).chars)
        display_entry = window._session.section_entries("font")[0]
        title_entry = window._session.section_entries("font")[1]
        assert display_entry["text"] == "display_charset.txt"
        assert title_entry["text"] == "title.txt"
        assert (source_dir / "display_charset.txt").read_text(encoding="utf-8") == expected_charset
        assert (source_dir / "title.txt").read_text(encoding="utf-8") == "XYZ"
        assert window._simple_asset_table.item(0, 3).text() == "display_charset.txt"
        assert window._simple_asset_table.item(1, 3).text() == "title.txt"
        assert window.has_unsaved_changes() is True
        assert window._status_label.text() == "Prepared font text for 2 fonts, created 1 files, updated 2 links."
        _close_window(window)

    @_skip_no_qt
    def test_auto_generate_font_text_samples_writes_current_resource_names(self, qapp, monkeypatch, tmp_path):
        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        (source_dir / "fonts").mkdir(parents=True)
        (source_dir / "fonts" / "display.ttf").write_bytes(b"ttf")
        (source_dir / "hero.png").write_bytes(b"png")
        (source_dir / "intro.mp4").write_bytes(b"mp4")
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {
                "img": [{"file": "hero.png", "name": "Hero Banner"}],
                "font": [{"file": "fonts/display.ttf", "name": "Display Font", "text": ""}],
                "mp4": [{"file": "intro.mp4", "name": "Intro Clip"}],
            },
            dirty=False,
        )

        window._auto_generate_font_text_samples()

        text_path = source_dir / "fonts" / "display_charset.txt"
        content = text_path.read_text(encoding="utf-8")
        assert text_path.is_file()
        assert "AaBb 123\n" in content
        assert "Hero Banner\n" in content
        assert "Display Font\n" in content
        assert "Intro Clip\n" in content
        assert window._session.section_entries("font")[0]["text"] == "fonts/display_charset.txt"
        assert window._simple_asset_table.item(1, 3).text() == "fonts/display_charset.txt"
        assert window.has_unsaved_changes() is True
        assert window._status_label.text() == "Generated sample text for 1 fonts, created 1 files, added 4 lines, updated 1 links."
        _close_window(window)

    @_skip_no_qt
    def test_pack_assets_into_source_dir_copies_external_files_and_updates_links(self, qapp, monkeypatch, tmp_path):
        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        external_dir = tmp_path / "imports"
        external_dir.mkdir(parents=True)
        external_image = external_dir / "hero.png"
        external_image.write_bytes(b"png")
        external_font = external_dir / "display.ttf"
        external_font.write_bytes(b"ttf")
        external_text = external_dir / "display.txt"
        external_text.write_text("ABC", encoding="utf-8")
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {
                "img": [{"file": str(external_image), "name": "hero"}],
                "font": [{"file": str(external_font), "name": "display", "text": str(external_text)}],
                "mp4": [],
            },
            dirty=False,
        )

        window._pack_assets_into_source_dir()

        assert (source_dir / "hero.png").read_bytes() == b"png"
        assert (source_dir / "display.ttf").read_bytes() == b"ttf"
        assert (source_dir / "display.txt").read_text(encoding="utf-8") == "ABC"
        assert window._session.section_entries("img")[0]["file"] == "hero.png"
        assert window._session.section_entries("font")[0]["file"] == "display.ttf"
        assert window._session.section_entries("font")[0]["text"] == "display.txt"
        assert window._simple_asset_table.item(0, 2).text() == "hero.png"
        assert window._simple_asset_table.item(1, 2).text() == "display.ttf"
        assert window._simple_asset_table.item(1, 3).text() == "display.txt"
        assert window.has_unsaved_changes() is True
        assert window._status_label.text() == "Packed 3 files into Source Dir, updated 3 links."
        _close_window(window)

    @_skip_no_qt
    def test_organize_assets_into_standard_folders_moves_files_and_updates_links(self, qapp, monkeypatch, tmp_path):
        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        (source_dir / "hero.png").write_bytes(b"png")
        (source_dir / "display.ttf").write_bytes(b"ttf")
        (source_dir / "display.txt").write_text("ABC", encoding="utf-8")
        (source_dir / "intro.mp4").write_bytes(b"mp4")
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {
                "img": [{"file": "hero.png", "name": "hero"}],
                "font": [{"file": "display.ttf", "name": "display", "text": "display.txt"}],
                "mp4": [{"file": "intro.mp4", "name": "intro"}],
            },
            dirty=False,
        )

        window._organize_assets_into_standard_folders()

        assert (source_dir / "images" / "hero.png").read_bytes() == b"png"
        assert (source_dir / "fonts" / "display.ttf").read_bytes() == b"ttf"
        assert (source_dir / "fonts" / "display.txt").read_text(encoding="utf-8") == "ABC"
        assert (source_dir / "videos" / "intro.mp4").read_bytes() == b"mp4"
        assert window._session.section_entries("img")[0]["file"] == "images/hero.png"
        assert window._session.section_entries("font")[0]["file"] == "fonts/display.ttf"
        assert window._session.section_entries("font")[0]["text"] == "fonts/display.txt"
        assert window._session.section_entries("mp4")[0]["file"] == "videos/intro.mp4"
        assert window.has_unsaved_changes() is True
        assert window._status_label.text() == "Organized 4 files into standard folders, updated 4 links."
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
    def test_rename_asset_names_from_files_updates_session_and_simple_table(self, qapp, monkeypatch, tmp_path):
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
                    {"file": "hero_banner.png", "name": "home_hero"},
                    {"file": "", "name": "keep_manual"},
                ],
                "font": [{"file": "display.ttf", "name": "headline"}],
                "mp4": [{"file": "intro.mp4"}],
            },
            dirty=False,
        )

        window._rename_asset_names_from_files()

        assert window._session.section_entries("img")[0]["name"] == "hero_banner"
        assert window._session.section_entries("img")[1]["name"] == "keep_manual"
        assert window._session.section_entries("font")[0]["name"] == "display"
        assert window._session.section_entries("mp4")[0]["name"] == "intro"
        assert window._simple_asset_table.item(0, 1).text() == "hero_banner"
        assert window._simple_asset_table.item(1, 1).text() == "keep_manual"
        assert window._simple_asset_table.item(2, 1).text() == "display"
        assert window._simple_asset_table.item(3, 1).text() == "intro"
        assert window.has_unsaved_changes() is True
        assert window._status_label.text() == "Renamed 3 assets from filenames."
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
    def test_remove_duplicate_assets_for_quick_mode_merges_missing_fields(self, qapp, monkeypatch, tmp_path):
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
                    {"file": "hero.png", "name": "hero"},
                    {"file": "hero.png", "format": "argb8888"},
                ],
                "font": [
                    {"file": "display.ttf", "name": "display"},
                    {"file": "display.ttf", "text": "display.txt"},
                ],
                "mp4": [],
            },
            dirty=False,
        )

        window._remove_duplicate_assets_for_quick_mode()

        assert len(window._session.section_entries("img")) == 1
        assert window._session.section_entries("img")[0]["format"] == "argb8888"
        assert len(window._session.section_entries("font")) == 1
        assert window._session.section_entries("font")[0]["text"] == "display.txt"
        assert window._simple_asset_table.rowCount() == 2
        assert window.has_unsaved_changes() is True
        assert window._status_label.text() == "Removed 2 duplicate assets, merged 2 missing fields."
        _close_window(window)

    @_skip_no_qt
    def test_remove_missing_assets_for_quick_mode_removes_broken_entries(self, qapp, monkeypatch, tmp_path):
        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        (source_dir / "hero.png").write_bytes(b"png")
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {
                "img": [{"file": "hero.png", "name": "hero"}, {"file": "ghost.png", "name": "ghost"}],
                "font": [{"file": "display.ttf", "name": "display"}],
                "mp4": [],
            },
            dirty=False,
        )

        window._remove_missing_assets_for_quick_mode()

        assert [entry["file"] for entry in window._session.section_entries("img")] == ["hero.png"]
        assert window._session.section_entries("font") == []
        assert window._simple_asset_table.rowCount() == 1
        assert window.has_unsaved_changes() is True
        assert window._status_label.text() == "Removed 2 missing asset entries."
        _close_window(window)

    @_skip_no_qt
    def test_clean_helper_outputs_removes_generated_folders_and_img_entries(self, qapp, monkeypatch, tmp_path):
        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        (source_dir / "thumbnails").mkdir(parents=True)
        (source_dir / "font_previews").mkdir(parents=True)
        (source_dir / "hero.png").write_bytes(b"png")
        (source_dir / "thumbnails" / "hero_thumb.png").write_bytes(b"png")
        (source_dir / "font_previews" / "display_preview.png").write_bytes(b"png")
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {
                "img": [
                    {"file": "hero.png", "name": "hero"},
                    {"file": "thumbnails/hero_thumb.png", "name": "hero_thumb"},
                    {"file": "font_previews/display_preview.png", "name": "display_preview"},
                ],
                "font": [{"file": "display.ttf", "name": "display"}],
                "mp4": [],
            },
            dirty=False,
        )

        window._remove_generated_helper_outputs_for_quick_mode()

        assert (source_dir / "hero.png").is_file()
        assert (source_dir / "thumbnails").exists() is False
        assert (source_dir / "font_previews").exists() is False
        assert [entry["file"] for entry in window._session.section_entries("img")] == ["hero.png"]
        assert [entry["file"] for entry in window._session.section_entries("font")] == ["display.ttf"]
        assert window._simple_asset_table.rowCount() == 2
        assert window.has_unsaved_changes() is True
        assert window._status_label.text() == "Cleaned 2 generated helper assets, deleted 2 files in 2 folders."
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

        def _fake_render(self, font_file, sample_text, entry=None):
            captured["font_file"] = font_file
            captured["sample_text"] = sample_text
            captured["entry"] = entry
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
        assert captured["entry"]["text"] == "charset/basic.txt"
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
    def test_generate_thumbnails_helper_creates_batch_thumbnail_entries(self, qapp, monkeypatch, tmp_path):
        from PyQt5.QtGui import QPixmap
        from PyQt5.QtWidgets import QDialog, QMessageBox

        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        hero_path = source_dir / "hero.png"
        hero = QPixmap(12, 8)
        assert hero.save(str(hero_path), "PNG")
        logo_path = source_dir / "logo.png"
        logo = QPixmap(10, 20)
        assert logo.save(str(logo_path), "PNG")

        class _FakeDialog:
            def __init__(self, *, width, height, output_folder, suffix, parent=None):
                assert width == 160
                assert height == 160
                assert output_folder == "thumbnails"
                assert suffix == "_thumb"

            def exec_(self):
                return QDialog.Accepted

            def width_value(self):
                return 5

            def height_value(self):
                return 3

            def output_folder(self):
                return "thumbnails"

            def filename_suffix(self):
                return "_thumb"

        monkeypatch.setattr("ui_designer.ui.resource_generator_window._QuickThumbnailBatchDialog", _FakeDialog)
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {"img": [{"file": "hero.png", "name": "hero"}, {"file": "logo.png", "name": "logo"}], "font": [], "mp4": []},
            dirty=False,
        )

        window._open_generate_thumbnails_helper()

        hero_thumb = QPixmap(str(source_dir / "thumbnails" / "hero_thumb.png"))
        logo_thumb = QPixmap(str(source_dir / "thumbnails" / "logo_thumb.png"))
        assert hero_thumb.width() == 4
        assert hero_thumb.height() == 3
        assert logo_thumb.width() == 2
        assert logo_thumb.height() == 3
        files = [entry["file"] for entry in window._session.section_entries("img")]
        assert files == ["hero.png", "logo.png", "thumbnails/hero_thumb.png", "thumbnails/logo_thumb.png"]
        assert window.has_unsaved_changes() is True
        assert window._status_label.text() == "Generated 2 thumbnails, added 2 assets."
        _close_window(window)

    @_skip_no_qt
    def test_generate_placeholders_helper_fills_missing_image_entries(self, qapp, monkeypatch, tmp_path):
        from PyQt5.QtGui import QPixmap
        from PyQt5.QtWidgets import QDialog, QMessageBox

        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        keep_path = source_dir / "keep.png"
        keep = QPixmap(12, 8)
        assert keep.save(str(keep_path), "PNG")

        class _FakeDialog:
            def __init__(self, *, width, height, output_folder, parent=None):
                assert width == 160
                assert height == 120
                assert output_folder == "placeholders"

            def exec_(self):
                return QDialog.Accepted

            def width_value(self):
                return 64

            def height_value(self):
                return 48

            def output_folder(self):
                return "placeholders"

        monkeypatch.setattr("ui_designer.ui.resource_generator_window._QuickImagePlaceholderDialog", _FakeDialog)
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {
                "img": [
                    {"file": "hero.png", "name": "Hero Banner"},
                    {"file": "", "name": "Logo Mark"},
                    {"file": "keep.png", "name": "Keep"},
                ],
                "font": [],
                "mp4": [],
            },
            dirty=False,
        )

        window._open_generate_placeholders_helper()

        hero_placeholder = QPixmap(str(source_dir / "hero.png"))
        logo_placeholder = QPixmap(str(source_dir / "placeholders" / "Logo_Mark_placeholder.png"))
        assert hero_placeholder.width() == 64
        assert hero_placeholder.height() == 48
        assert logo_placeholder.width() == 64
        assert logo_placeholder.height() == 48
        files = [entry["file"] for entry in window._session.section_entries("img")]
        assert files == ["hero.png", "placeholders/Logo_Mark_placeholder.png", "keep.png"]
        assert window.has_unsaved_changes() is True
        assert window._status_label.text() == "Generated 2 placeholders, updated 1 links."
        _close_window(window)

    @_skip_no_qt
    def test_normalize_images_helper_creates_batch_png_entries(self, qapp, monkeypatch, tmp_path):
        from PyQt5.QtGui import QPixmap
        from PyQt5.QtWidgets import QDialog, QMessageBox

        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        hero_path = source_dir / "hero.png"
        hero = QPixmap(12, 8)
        assert hero.save(str(hero_path), "PNG")
        banner_path = source_dir / "banner.png"
        banner = QPixmap(20, 6)
        assert banner.save(str(banner_path), "PNG")

        class _FakeDialog:
            def __init__(self, *, output_folder, suffix, parent=None):
                assert output_folder == "normalized"
                assert suffix == "_norm"

            def exec_(self):
                return QDialog.Accepted

            def output_folder(self):
                return "normalized"

            def filename_suffix(self):
                return "_norm"

        monkeypatch.setattr("ui_designer.ui.resource_generator_window._QuickImageNormalizeDialog", _FakeDialog)
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {"img": [{"file": "hero.png", "name": "hero"}, {"file": "banner.png", "name": "banner"}], "font": [], "mp4": []},
            dirty=False,
        )

        window._open_normalize_images_helper()

        hero_norm = QPixmap(str(source_dir / "normalized" / "hero_norm.png"))
        banner_norm = QPixmap(str(source_dir / "normalized" / "banner_norm.png"))
        assert hero_norm.width() == 12
        assert hero_norm.height() == 8
        assert banner_norm.width() == 20
        assert banner_norm.height() == 6
        files = [entry["file"] for entry in window._session.section_entries("img")]
        assert files == ["hero.png", "banner.png", "normalized/banner_norm.png", "normalized/hero_norm.png"]
        assert window.has_unsaved_changes() is True
        assert window._status_label.text() == "Normalized 2 images, added 2 assets."
        _close_window(window)

    @_skip_no_qt
    def test_compress_images_helper_creates_batch_png_entries(self, qapp, monkeypatch, tmp_path):
        from PyQt5.QtGui import QPixmap
        from PyQt5.QtWidgets import QDialog, QMessageBox

        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        hero_path = source_dir / "hero.png"
        hero = QPixmap(12, 8)
        hero.fill()
        assert hero.save(str(hero_path), "PNG")
        logo_path = source_dir / "logo.png"
        logo = QPixmap(9, 9)
        logo.fill()
        assert logo.save(str(logo_path), "PNG")

        class _FakeDialog:
            def __init__(self, *, output_folder, suffix, colors, parent=None):
                assert output_folder == "compressed"
                assert suffix == "_cmp"
                assert colors == 64

            def exec_(self):
                return QDialog.Accepted

            def output_folder(self):
                return "compressed"

            def filename_suffix(self):
                return "_cmp"

            def color_limit(self):
                return 32

        monkeypatch.setattr("ui_designer.ui.resource_generator_window._QuickImageCompressDialog", _FakeDialog)
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {"img": [{"file": "hero.png", "name": "hero"}, {"file": "logo.png", "name": "logo"}], "font": [], "mp4": []},
            dirty=False,
        )

        window._open_compress_images_helper()

        hero_cmp = QPixmap(str(source_dir / "compressed" / "hero_cmp.png"))
        logo_cmp = QPixmap(str(source_dir / "compressed" / "logo_cmp.png"))
        assert hero_cmp.isNull() is False
        assert logo_cmp.isNull() is False
        files = [entry["file"] for entry in window._session.section_entries("img")]
        assert files == ["hero.png", "logo.png", "compressed/hero_cmp.png", "compressed/logo_cmp.png"]
        assert window.has_unsaved_changes() is True
        assert window._status_label.text() == "Compressed 2 images, added 2 assets."
        _close_window(window)

    @_skip_no_qt
    def test_prerender_fonts_helper_creates_batch_png_entries(self, qapp, monkeypatch, tmp_path):
        from PyQt5.QtGui import QPixmap
        from PyQt5.QtWidgets import QDialog, QMessageBox

        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        fonts_dir = source_dir / "fonts"
        fonts_dir.mkdir(parents=True)
        (fonts_dir / "display.ttf").write_bytes(b"ttf")
        (fonts_dir / "title.ttf").write_bytes(b"ttf")

        class _FakeDialog:
            def __init__(self, *, output_folder, suffix, sample_text, parent=None):
                assert output_folder == "font_previews"
                assert suffix == "_preview"
                assert sample_text == ""

            def exec_(self):
                return QDialog.Accepted

            def output_folder(self):
                return "font_previews"

            def filename_suffix(self):
                return "_preview"

            def sample_text(self):
                return "Hello Designer"

        rendered = []

        def _fake_build_font_preview(self, font_path, sample_text, entry=None):
            rendered.append((font_path.replace("\\", "/"), sample_text, entry["name"]))
            pixmap = QPixmap(72, 30)
            pixmap.fill()
            return pixmap

        monkeypatch.setattr("ui_designer.ui.resource_generator_window._QuickFontPrerenderDialog", _FakeDialog)
        monkeypatch.setattr(
            "ui_designer.ui.resource_generator_window.ResourceGeneratorWindow._build_font_preview_pixmap",
            _fake_build_font_preview,
        )
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {
                "img": [],
                "font": [
                    {"file": "fonts/display.ttf", "name": "display"},
                    {"file": "fonts/title.ttf", "name": "title"},
                ],
                "mp4": [],
            },
            dirty=False,
        )

        window._open_prerender_fonts_helper()

        display_preview = QPixmap(str(source_dir / "font_previews" / "display_preview.png"))
        title_preview = QPixmap(str(source_dir / "font_previews" / "title_preview.png"))
        assert display_preview.isNull() is False
        assert title_preview.isNull() is False
        assert rendered == [
            ((fonts_dir / "display.ttf").resolve().as_posix(), "Hello Designer", "display"),
            ((fonts_dir / "title.ttf").resolve().as_posix(), "Hello Designer", "title"),
        ]
        files = [entry["file"] for entry in window._session.section_entries("img")]
        assert files == ["font_previews/display_preview.png", "font_previews/title_preview.png"]
        assert window.has_unsaved_changes() is True
        assert window._status_label.text() == "Pre-rendered 2 fonts, added 2 assets."
        _close_window(window)

    @_skip_no_qt
    def test_add_border_image_helper_overwrites_selected_image(self, qapp, monkeypatch, tmp_path):
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

            def border_size(self):
                return 2

            def color_value(self):
                return "#FF0000"

        monkeypatch.setattr("ui_designer.ui.resource_generator_window._QuickImageBorderDialog", _FakeDialog)

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {"img": [{"file": "hero.png", "name": "hero"}], "font": [], "mp4": []},
            dirty=False,
        )
        window._simple_asset_table.selectRow(0)
        qapp.processEvents()

        window._open_border_image_helper()

        bordered = QPixmap(str(image_path))
        assert bordered.width() == 16
        assert bordered.height() == 12
        assert len(window._session.section_entries("img")) == 1
        assert window._status_label.text() == "Updated bordered image 'hero.png' (16 x 12)."
        _close_window(window)

    @_skip_no_qt
    def test_add_border_image_helper_can_create_new_image_entry(self, qapp, monkeypatch, tmp_path):
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
                return "variants/hero_border.png"

            def border_size(self):
                return 3

            def color_value(self):
                return "#00FF00"

        monkeypatch.setattr("ui_designer.ui.resource_generator_window._QuickImageBorderDialog", _FakeDialog)
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {"img": [{"file": "hero.png", "name": "hero"}], "font": [], "mp4": []},
            dirty=False,
        )
        window._simple_asset_table.selectRow(0)
        qapp.processEvents()

        window._open_border_image_helper()

        bordered_path = source_dir / "variants" / "hero_border.png"
        bordered = QPixmap(str(bordered_path))
        assert bordered.width() == 18
        assert bordered.height() == 14
        files = [entry["file"] for entry in window._session.section_entries("img")]
        assert files == ["hero.png", "variants/hero_border.png"]
        assert window.has_unsaved_changes() is True
        assert window._status_label.text() == "Created bordered image 'variants/hero_border.png' (18 x 14)."
        _close_window(window)

    @_skip_no_qt
    def test_add_background_image_helper_overwrites_selected_image(self, qapp, monkeypatch, tmp_path):
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

            def color_value(self):
                return "#112233"

        monkeypatch.setattr("ui_designer.ui.resource_generator_window._QuickImageBackgroundDialog", _FakeDialog)

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {"img": [{"file": "hero.png", "name": "hero"}], "font": [], "mp4": []},
            dirty=False,
        )
        window._simple_asset_table.selectRow(0)
        qapp.processEvents()

        window._open_background_image_helper()

        backgrounded = QPixmap(str(image_path))
        assert backgrounded.width() == 12
        assert backgrounded.height() == 8
        assert len(window._session.section_entries("img")) == 1
        assert window._status_label.text() == "Updated background image 'hero.png' (12 x 8)."
        _close_window(window)

    @_skip_no_qt
    def test_add_background_image_helper_can_create_new_image_entry(self, qapp, monkeypatch, tmp_path):
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
                return "variants/hero_bg.png"

            def color_value(self):
                return "#445566"

        monkeypatch.setattr("ui_designer.ui.resource_generator_window._QuickImageBackgroundDialog", _FakeDialog)
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {"img": [{"file": "hero.png", "name": "hero"}], "font": [], "mp4": []},
            dirty=False,
        )
        window._simple_asset_table.selectRow(0)
        qapp.processEvents()

        window._open_background_image_helper()

        backgrounded_path = source_dir / "variants" / "hero_bg.png"
        backgrounded = QPixmap(str(backgrounded_path))
        assert backgrounded.width() == 12
        assert backgrounded.height() == 8
        files = [entry["file"] for entry in window._session.section_entries("img")]
        assert files == ["hero.png", "variants/hero_bg.png"]
        assert window.has_unsaved_changes() is True
        assert window._status_label.text() == "Created background image 'variants/hero_bg.png' (12 x 8)."
        _close_window(window)

    @_skip_no_qt
    def test_round_corners_image_helper_overwrites_selected_image(self, qapp, monkeypatch, tmp_path):
        from PyQt5.QtGui import QColor, QImage, QPixmap
        from PyQt5.QtWidgets import QDialog

        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        image_path = source_dir / "hero.png"
        pixmap = QPixmap(12, 8)
        pixmap.fill(QColor("#FF8844"))
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

            def radius_value(self):
                return 3

        monkeypatch.setattr("ui_designer.ui.resource_generator_window._QuickImageRoundCornersDialog", _FakeDialog)

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {"img": [{"file": "hero.png", "name": "hero"}], "font": [], "mp4": []},
            dirty=False,
        )
        window._simple_asset_table.selectRow(0)
        qapp.processEvents()

        window._open_round_corners_image_helper()

        rounded = QImage(str(image_path))
        assert rounded.width() == 12
        assert rounded.height() == 8
        assert rounded.pixelColor(0, 0).alpha() == 0
        assert rounded.pixelColor(6, 4).alpha() == 255
        assert len(window._session.section_entries("img")) == 1
        assert window._status_label.text() == "Updated rounded image 'hero.png' (12 x 8)."
        _close_window(window)

    @_skip_no_qt
    def test_round_corners_image_helper_can_create_new_image_entry(self, qapp, monkeypatch, tmp_path):
        from PyQt5.QtGui import QColor, QImage, QPixmap
        from PyQt5.QtWidgets import QDialog, QMessageBox

        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        image_path = source_dir / "hero.png"
        pixmap = QPixmap(12, 8)
        pixmap.fill(QColor("#88CC22"))
        assert pixmap.save(str(image_path), "PNG")

        class _FakeDialog:
            def __init__(self, *, width, height, output_filename, parent=None):
                assert width == 12
                assert height == 8
                assert output_filename == "hero.png"

            def exec_(self):
                return QDialog.Accepted

            def output_filename(self):
                return "variants/hero_round.png"

            def radius_value(self):
                return 2

        monkeypatch.setattr("ui_designer.ui.resource_generator_window._QuickImageRoundCornersDialog", _FakeDialog)
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {"img": [{"file": "hero.png", "name": "hero"}], "font": [], "mp4": []},
            dirty=False,
        )
        window._simple_asset_table.selectRow(0)
        qapp.processEvents()

        window._open_round_corners_image_helper()

        rounded_path = source_dir / "variants" / "hero_round.png"
        rounded = QImage(str(rounded_path))
        assert rounded.width() == 12
        assert rounded.height() == 8
        assert rounded.pixelColor(0, 0).alpha() == 0
        assert rounded.pixelColor(6, 4).alpha() == 255
        files = [entry["file"] for entry in window._session.section_entries("img")]
        assert files == ["hero.png", "variants/hero_round.png"]
        assert window.has_unsaved_changes() is True
        assert window._status_label.text() == "Created rounded image 'variants/hero_round.png' (12 x 8)."
        _close_window(window)

    @_skip_no_qt
    def test_adjust_opacity_image_helper_overwrites_selected_image(self, qapp, monkeypatch, tmp_path):
        from PyQt5.QtGui import QColor, QImage, QPixmap
        from PyQt5.QtWidgets import QDialog

        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        image_path = source_dir / "hero.png"
        pixmap = QPixmap(12, 8)
        pixmap.fill(QColor("#4477CC"))
        assert pixmap.save(str(image_path), "PNG")

        class _FakeDialog:
            def __init__(self, *, output_filename, parent=None):
                assert output_filename == "hero.png"

            def exec_(self):
                return QDialog.Accepted

            def output_filename(self):
                return "hero.png"

            def opacity_percent(self):
                return 40

        monkeypatch.setattr("ui_designer.ui.resource_generator_window._QuickImageOpacityDialog", _FakeDialog)

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {"img": [{"file": "hero.png", "name": "hero"}], "font": [], "mp4": []},
            dirty=False,
        )
        window._simple_asset_table.selectRow(0)
        qapp.processEvents()

        window._open_opacity_image_helper()

        faded = QImage(str(image_path))
        assert faded.width() == 12
        assert faded.height() == 8
        assert faded.pixelColor(6, 4).alpha() == 102
        assert len(window._session.section_entries("img")) == 1
        assert window._status_label.text() == "Updated image opacity for 'hero.png' (40% alpha, 12 x 8)."
        _close_window(window)

    @_skip_no_qt
    def test_adjust_opacity_image_helper_can_create_new_image_entry(self, qapp, monkeypatch, tmp_path):
        from PyQt5.QtGui import QColor, QImage, QPixmap
        from PyQt5.QtWidgets import QDialog, QMessageBox

        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        image_path = source_dir / "hero.png"
        pixmap = QPixmap(12, 8)
        pixmap.fill(QColor("#CC7744"))
        assert pixmap.save(str(image_path), "PNG")

        class _FakeDialog:
            def __init__(self, *, output_filename, parent=None):
                assert output_filename == "hero.png"

            def exec_(self):
                return QDialog.Accepted

            def output_filename(self):
                return "variants/hero_faded.png"

            def opacity_percent(self):
                return 25

        monkeypatch.setattr("ui_designer.ui.resource_generator_window._QuickImageOpacityDialog", _FakeDialog)
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {"img": [{"file": "hero.png", "name": "hero"}], "font": [], "mp4": []},
            dirty=False,
        )
        window._simple_asset_table.selectRow(0)
        qapp.processEvents()

        window._open_opacity_image_helper()

        faded_path = source_dir / "variants" / "hero_faded.png"
        faded = QImage(str(faded_path))
        assert faded.width() == 12
        assert faded.height() == 8
        assert faded.pixelColor(6, 4).alpha() == 64
        files = [entry["file"] for entry in window._session.section_entries("img")]
        assert files == ["hero.png", "variants/hero_faded.png"]
        assert window.has_unsaved_changes() is True
        assert window._status_label.text() == "Created image opacity for 'variants/hero_faded.png' (25% alpha, 12 x 8)."
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
