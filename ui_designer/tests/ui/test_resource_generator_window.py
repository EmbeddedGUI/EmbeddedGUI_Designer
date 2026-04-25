import json
import os
from types import SimpleNamespace

import pytest

from ui_designer.model.resource_generation_session import infer_generation_paths
from ui_designer.tests.qt_test_utils import HAS_PYQT5, skip_if_no_qt
from ui_designer.tests.sdk_builders import build_test_sdk_root
from ui_designer.tests.ui.window_test_helpers import close_test_window as _close_window

if HAS_PYQT5:
    from PyQt5.QtCore import QEvent, Qt, QUrl
    from PyQt5.QtTest import QTest
    from PyQt5.QtWidgets import QApplication, QAbstractItemView, QGroupBox, QHeaderView, QLabel, QMessageBox, QPushButton


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


def _layout_margins_tuple(layout):
    margins = layout.contentsMargins()
    return (margins.left(), margins.top(), margins.right(), margins.bottom())


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
        simple_button_texts = {button.text() for button in window._simple_page.findChildren(QPushButton)}
        assert {"Import & Setup", "Batch Fixes", "Preview & Export", "Image Tools", "Selection"} <= group_titles
        assert [window._simple_action_tabs.tabText(index) for index in range(window._simple_action_tabs.count())] == [
            "Start",
            "Clean",
            "Inspect",
            "Transforms",
            "Selection",
        ]
        assert "Preview Selected Asset" not in simple_button_texts
        assert not any(text.startswith("Auto ") for text in simple_button_texts)
        _close_window(window)

    @_skip_no_qt
    def test_simple_mode_uses_resizable_vertical_panels_and_compact_category_headers(self, qapp):
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow
        from ui_designer.ui.theme import app_theme_tokens

        window = ResourceGeneratorWindow("")
        tab_bar = window._simple_action_tabs.tabBar()
        tokens = app_theme_tokens()

        assert window._simple_workspace_splitter.orientation() == Qt.Vertical
        assert window._simple_workspace_splitter.count() == 3
        assert window._simple_workspace_splitter.childrenCollapsible() is False
        assert window._simple_workspace_splitter.handleWidth() == 8
        assert window._simple_action_tabs.documentMode() is True
        assert window._simple_actions_scroll.widget() is window._simple_action_tabs
        assert (
            f"QTabBar::tab {{ min-height: 18px; padding: {tokens['pad_tab_compact_v']}px {tokens['space_sm']}px; }}"
            in window._simple_action_tabs.styleSheet()
        )
        assert tab_bar.minimumHeight() == 24
        assert tab_bar.maximumHeight() == 24
        assert tab_bar.font().pixelSize() == 10
        _close_window(window)

    @_skip_no_qt
    def test_simple_mode_action_tab_bar_height_follows_runtime_tokens(self, qapp, monkeypatch):
        import ui_designer.ui.resource_generator_window as resource_generator_window_module
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        tab_tokens = dict(resource_generator_window_module.app_theme_tokens())
        tab_tokens["h_tab_min"] = 26
        monkeypatch.setattr(resource_generator_window_module, "app_theme_tokens", lambda *args, **kwargs: tab_tokens)

        window = ResourceGeneratorWindow("")

        assert window._simple_action_tabs.tabBar().minimumHeight() == 26
        assert window._simple_action_tabs.tabBar().maximumHeight() == 26
        _close_window(window)

    @_skip_no_qt
    def test_simple_preview_panel_heights_follow_runtime_metrics(self, qapp):
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        window = ResourceGeneratorWindow("")
        try:
            assert window._simple_asset_preview_label.minimumHeight() == (
                window._simple_asset_preview_label_minimum_height_target()
            )
            assert window._simple_asset_meta.minimumHeight() == window._simple_asset_meta_minimum_height_target()
        finally:
            _close_window(window)

    @_skip_no_qt
    def test_simple_action_buttons_follow_runtime_metrics(self, qapp):
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        window = ResourceGeneratorWindow("")
        try:
            assert window._import_assets_button.minimumHeight() == (
                window._simple_action_button_minimum_height_target(window._import_assets_button)
            )
            assert window._generate_thumbnails_button.minimumHeight() == (
                window._simple_action_button_minimum_height_target(window._generate_thumbnails_button)
            )
        finally:
            _close_window(window)

    @_skip_no_qt
    def test_simple_action_buttons_resync_on_font_change(self, qapp, monkeypatch):
        import ui_designer.ui.resource_generator_window as resource_generator_window_module
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        window = ResourceGeneratorWindow("")
        try:
            baseline_import_height = window._import_assets_button.minimumHeight()
            baseline_thumbnail_height = window._generate_thumbnails_button.minimumHeight()

            action_tokens = dict(resource_generator_window_module.app_theme_tokens())
            action_tokens["h_tab_min"] = 28
            action_tokens["pad_btn_v"] = 3
            action_tokens["space_md"] = 16
            monkeypatch.setattr(
                resource_generator_window_module,
                "app_theme_tokens",
                lambda *args, **kwargs: action_tokens,
            )

            window.changeEvent(QEvent(QEvent.FontChange))

            assert window._import_assets_button.minimumHeight() == (
                window._simple_action_button_minimum_height_target(window._import_assets_button)
            )
            assert window._generate_thumbnails_button.minimumHeight() == (
                window._simple_action_button_minimum_height_target(window._generate_thumbnails_button)
            )
            assert window._import_assets_button.minimumHeight() > baseline_import_height
            assert window._generate_thumbnails_button.minimumHeight() > baseline_thumbnail_height
        finally:
            _close_window(window)

    @_skip_no_qt
    def test_simple_preview_panel_heights_resync_on_font_change(self, qapp, monkeypatch):
        import ui_designer.ui.resource_generator_window as resource_generator_window_module
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        window = ResourceGeneratorWindow("")
        try:
            baseline_preview_height = window._simple_asset_preview_label.minimumHeight()
            baseline_meta_height = window._simple_asset_meta.minimumHeight()

            preview_tokens = dict(resource_generator_window_module.app_theme_tokens())
            preview_tokens["h_tab_min"] = 34
            preview_tokens["space_xxs"] = 4
            preview_tokens["space_sm"] = 10
            preview_tokens["space_md"] = 16
            monkeypatch.setattr(
                resource_generator_window_module,
                "app_theme_tokens",
                lambda *args, **kwargs: preview_tokens,
            )

            window.changeEvent(QEvent(QEvent.FontChange))

            assert window._simple_asset_preview_label.minimumHeight() == (
                window._simple_asset_preview_label_minimum_height_target()
            )
            assert window._simple_asset_meta.minimumHeight() == window._simple_asset_meta_minimum_height_target()
            assert window._simple_asset_preview_label.minimumHeight() > baseline_preview_height
            assert window._simple_asset_meta.minimumHeight() > baseline_meta_height
        finally:
            _close_window(window)

    @_skip_no_qt
    def test_simple_mode_filter_counts_use_dense_ui_typography(self, qapp):
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow
        from ui_designer.ui.theme import app_theme_tokens, designer_ui_font

        window = ResourceGeneratorWindow("")

        try:
            tokens = app_theme_tokens()
            expected_px = int(tokens["fs_body_sm"])
            expected_family = designer_ui_font().family()

            for label in (
                window._simple_image_count,
                window._simple_font_count,
                window._simple_mp4_count,
                window._simple_attention_count,
            ):
                assert label.font().pixelSize() == expected_px
                assert label.font().family() == expected_family
                assert label.font().bold() is False

            window._update_simple_attention_count(2)
            assert window._simple_attention_count.font().pixelSize() == expected_px
            assert window._simple_attention_count.font().family() == expected_family
            assert window._simple_attention_count.font().bold() is True

            window._update_simple_attention_count(0)
            assert window._simple_attention_count.font().pixelSize() == expected_px
            assert window._simple_attention_count.font().family() == expected_family
            assert window._simple_attention_count.font().bold() is False
        finally:
            _close_window(window)

    @_skip_no_qt
    def test_resource_generator_uses_compact_workspace_shell_spacing(self, qapp):
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        window = ResourceGeneratorWindow("")
        try:
            path_group = next(group for group in window.findChildren(QGroupBox) if group.title() == "Paths")
            quick_mode_group = next(group for group in window._simple_page.findChildren(QGroupBox) if group.title() == "Quick Mode")
            assets_group = next(group for group in window._simple_page.findChildren(QGroupBox) if group.title() == "Assets")
            action_group = next(group for group in window._simple_page.findChildren(QGroupBox) if group.title() == "Import & Setup")
            asset_preview_group = next(group for group in window._simple_page.findChildren(QGroupBox) if group.title() == "Asset Preview")
            merged_preview_group = next(group for group in window._simple_page.findChildren(QGroupBox) if group.title() == "Merged Preview")
            sections_group = next(group for group in window._professional_page.findChildren(QGroupBox) if group.title() == "Sections")
            entries_group = next(group for group in window._professional_page.findChildren(QGroupBox) if group.title() == "Entries")
            editor_group = next(group for group in window._professional_page.findChildren(QGroupBox) if group.title() == "Entry Editor")
            toolbar_layout = window.layout().itemAt(0).layout()
            quick_counts_row = quick_mode_group.layout().itemAt(2).layout()
            empty_state_buttons = window._simple_asset_empty_state.layout().itemAt(3).layout()
            asset_toolbar = assets_group.layout().itemAt(0).layout()
            preview_header = asset_preview_group.layout().itemAt(0).layout()

            assert _layout_margins_tuple(window.layout()) == (12, 12, 12, 12)
            assert window.layout().spacing() == 4
            assert toolbar_layout.spacing() == 4
            assert window._simple_page.layout().spacing() == 4
            assert window._professional_page.layout().spacing() == 4
            assert path_group.layout().horizontalSpacing() == 4
            assert path_group.layout().verticalSpacing() == 4
            assert _layout_margins_tuple(quick_mode_group.layout()) == (12, 12, 12, 12)
            assert quick_mode_group.layout().spacing() == 4
            assert quick_counts_row.spacing() == 10
            assert _layout_margins_tuple(window._simple_asset_empty_state.layout()) == (10, 8, 10, 8)
            assert window._simple_asset_empty_state.layout().spacing() == 4
            assert empty_state_buttons.spacing() == 4
            assert _layout_margins_tuple(assets_group.layout()) == (6, 6, 6, 6)
            assert assets_group.layout().spacing() == 4
            assert asset_toolbar.spacing() == 4
            assert _layout_margins_tuple(action_group.layout()) == (6, 6, 6, 6)
            assert action_group.layout().horizontalSpacing() == 4
            assert action_group.layout().verticalSpacing() == 4
            assert window._simple_action_tabs.widget(0).layout().spacing() == 4
            assert _layout_margins_tuple(asset_preview_group.layout()) == (6, 6, 6, 6)
            assert asset_preview_group.layout().spacing() == 4
            assert preview_header.spacing() == 4
            assert _layout_margins_tuple(merged_preview_group.layout()) == (6, 6, 6, 6)
            assert merged_preview_group.layout().spacing() == 4
            assert _layout_margins_tuple(sections_group.layout()) == (6, 6, 6, 6)
            assert _layout_margins_tuple(entries_group.layout()) == (6, 6, 6, 6)
            assert entries_group.layout().spacing() == 4
            assert _layout_margins_tuple(editor_group.layout()) == (6, 6, 6, 6)
            assert editor_group.layout().spacing() == 4
            assert window._form_layout.spacing() == 4
        finally:
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
        assert header.font().pixelSize() == 10
        assert window._simple_asset_table.verticalHeader().defaultSectionSize() >= window.fontMetrics().height() + 12
        _close_window(window)

    @_skip_no_qt
    def test_resource_generator_tables_use_theme_palette_for_unselected_rows(self, qapp):
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow
        from ui_designer.ui.theme import app_theme_tokens

        window = ResourceGeneratorWindow("")
        tokens = app_theme_tokens()

        simple_palette = window._simple_asset_table.palette()
        assert simple_palette.base().color().name().lower() == tokens["panel_raised"].lower()
        assert simple_palette.alternateBase().color().name().lower() == tokens["panel_alt"].lower()
        assert simple_palette.text().color().name().lower() == tokens["text"].lower()

        entry_palette = window._entry_table.palette()
        assert entry_palette.base().color().name().lower() == tokens["panel_alt"].lower()
        assert entry_palette.alternateBase().color().name().lower() == tokens["panel_raised"].lower()
        assert entry_palette.text().color().name().lower() == tokens["text"].lower()
        _close_window(window)

    @_skip_no_qt
    def test_simple_mode_shows_empty_state_before_assets_are_imported(self, qapp):
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        window = ResourceGeneratorWindow("")

        assert window._simple_asset_content_stack.currentWidget() is window._simple_asset_empty_state
        assert window._simple_asset_empty_title.text() == "No assets imported yet."
        assert window._simple_asset_empty_title.font().pixelSize() == 13
        assert window._simple_asset_empty_title.font().bold() is True
        assert window._simple_asset_empty_import_button.isHidden() is False
        assert window._simple_asset_empty_scan_button.isHidden() is False
        assert window._simple_asset_empty_clear_button.isHidden() is True
        assert window._simple_attention_count.text() == "Needs Attention: 0"
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
    def test_simple_mode_asset_filter_includes_missing_and_generated_views(self, qapp, tmp_path):
        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        generated_dir = source_dir / "thumbnails"
        source_dir.mkdir(parents=True)
        generated_dir.mkdir(parents=True)
        (source_dir / "hero.png").write_bytes(b"png")
        (generated_dir / "hero_thumb.png").write_bytes(b"png")

        window = ResourceGeneratorWindow("")
        assert [window._simple_asset_type_filter.itemData(index) for index in range(window._simple_asset_type_filter.count())] == [
            "all",
            "img",
            "font",
            "mp4",
            "attention",
            "missing",
            "generated",
        ]

        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {
                "img": [
                    {"file": "hero.png", "name": "hero"},
                    {"file": "missing.png", "name": "missing"},
                    {"file": "thumbnails/hero_thumb.png", "name": "hero_thumb"},
                ],
                "font": [{"file": "display.ttf", "name": "display"}],
            },
            dirty=False,
        )

        window._simple_asset_type_filter.setCurrentIndex(window._simple_asset_type_filter.findData("missing"))
        qapp.processEvents()
        assert [window._simple_asset_table.item(row, 1).text() for row in range(window._simple_asset_table.rowCount())] == [
            "missing",
            "display",
        ]
        assert window._simple_asset_result_label.text() == "Showing 2 of 4 assets"

        window._simple_asset_type_filter.setCurrentIndex(window._simple_asset_type_filter.findData("generated"))
        qapp.processEvents()
        assert [window._simple_asset_table.item(row, 1).text() for row in range(window._simple_asset_table.rowCount())] == [
            "hero_thumb",
        ]
        assert window._simple_asset_result_label.text() == "Showing 1 of 4 assets"
        _close_window(window)

    @_skip_no_qt
    def test_simple_mode_attention_filter_highlights_incomplete_resources(self, qapp, tmp_path):
        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow
        from ui_designer.ui.theme import app_theme_tokens

        source_dir = tmp_path / "resource" / "src"
        (source_dir / "charset").mkdir(parents=True)
        (source_dir / "hero.png").write_bytes(b"png")
        (source_dir / "display.ttf").write_bytes(b"ttf")
        (source_dir / "intro.mp4").write_bytes(b"mp4")

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {
                "img": [{"file": "hero.png", "name": "hero"}],
                "font": [{"file": "display.ttf", "name": "display", "text": ""}],
                "mp4": [{"file": "intro.mp4", "name": "intro", "fps": 24, "width": 0, "height": 180}],
            },
            dirty=False,
        )

        assert [window._simple_asset_table.item(row, 0).text() for row in range(window._simple_asset_table.rowCount())] == [
            "Images",
            "! Fonts",
            "! MP4",
        ]
        window._simple_asset_type_filter.setCurrentIndex(window._simple_asset_type_filter.findData("attention"))
        qapp.processEvents()

        assert [window._simple_asset_table.item(row, 1).text() for row in range(window._simple_asset_table.rowCount())] == [
            "display",
            "intro",
        ]
        assert [window._simple_asset_table.item(row, 0).text() for row in range(window._simple_asset_table.rowCount())] == [
            "! Fonts",
            "! MP4",
        ]
        assert window._simple_attention_count.text() == "Needs Attention: 2"
        assert "Show > Needs Attention" in window._simple_attention_count.toolTip()
        assert window._simple_asset_result_label.text() == "Showing 2 of 3 assets"
        assert window._simple_asset_table.item(0, 0).toolTip() == (
            "Font text file is not linked.\n"
            "Fix: Use Edit Font Text... to create the charset file."
        )
        assert window._simple_asset_table.item(1, 0).toolTip() == (
            "Video metadata is incomplete: width\n"
            "Fix: Use Detect Video Info to fill fps, width, and height."
        )
        tokens = app_theme_tokens()
        assert window._simple_asset_table.item(0, 0).font().bold() is True
        assert window._simple_asset_table.item(0, 0).foreground().color().name().lower() == tokens["warning"].lower()
        assert window._simple_asset_table.item(0, 1).background().color().alpha() > 0
        assert window._simple_asset_table.item(0, 3).background().color().alpha() > 0

        window._simple_asset_table.selectRow(0)
        qapp.processEvents()

        assert "Attention: Font text file is not linked." in window._simple_asset_meta.toPlainText()
        assert "Suggested Fix: Use Edit Font Text... to create the charset file." in window._simple_asset_meta.toPlainText()
        _close_window(window)

    @_skip_no_qt
    def test_simple_mode_attention_highlights_svg_rasterization_without_dim(self, qapp, tmp_path):
        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        (source_dir / "icon.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24"></svg>\n',
            encoding="utf-8",
        )

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {
                "img": [{"file": "icon.svg", "name": "icon", "format": "rgb565", "alpha": "4"}],
                "font": [],
                "mp4": [],
            },
            dirty=False,
        )

        assert window._simple_asset_table.item(0, 0).text() == "! Images"
        assert window._simple_attention_count.text() == "Needs Attention: 1"
        assert window._simple_asset_table.item(0, 0).toolTip() == (
            "SVG rasterization is missing a dim value.\n"
            "Fix: Set Dim in Professional Mode so the SVG can be rasterized."
        )
        assert "Attention: SVG rasterization is missing a dim value." in window._simple_asset_meta.toPlainText()
        _close_window(window)

    @_skip_no_qt
    def test_simple_mode_attention_search_matches_issue_and_fix_text(self, qapp, tmp_path):
        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        (source_dir / "display.ttf").write_bytes(b"ttf")
        (source_dir / "intro.mp4").write_bytes(b"mp4")

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {
                "font": [{"file": "display.ttf", "name": "display", "text": ""}],
                "mp4": [{"file": "intro.mp4", "name": "intro", "fps": 24, "width": 0, "height": 180}],
            },
            dirty=False,
        )

        window._simple_asset_search_edit.setText("font text")
        qapp.processEvents()
        assert window._simple_asset_table.rowCount() == 0

        window._simple_asset_type_filter.setCurrentIndex(window._simple_asset_type_filter.findData("attention"))
        qapp.processEvents()
        assert window._simple_asset_table.rowCount() == 1
        assert window._simple_asset_table.item(0, 1).text() == "display"

        window._simple_asset_search_edit.setText("detect video info")
        qapp.processEvents()
        assert window._simple_asset_table.rowCount() == 1
        assert window._simple_asset_table.item(0, 1).text() == "intro"
        _close_window(window)

    @_skip_no_qt
    def test_simple_mode_attention_filter_empty_state_confirms_all_assets_ready(self, qapp, tmp_path):
        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        (source_dir / "fonts").mkdir(parents=True)
        (source_dir / "hero.png").write_bytes(b"png")
        (source_dir / "fonts" / "display.ttf").write_bytes(b"ttf")
        (source_dir / "fonts" / "display.txt").write_text("ABC", encoding="utf-8")
        (source_dir / "intro.mp4").write_bytes(b"mp4")

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

        window._simple_asset_type_filter.setCurrentIndex(window._simple_asset_type_filter.findData("attention"))
        qapp.processEvents()

        assert window._simple_asset_table.rowCount() == 0
        assert window._simple_asset_content_stack.currentWidget() is window._simple_asset_empty_state
        assert window._simple_asset_empty_title.text() == "No assets need attention right now."
        assert "no missing files" in window._simple_asset_empty_description.text().lower()
        assert window._simple_attention_count.text() == "Needs Attention: 0"
        assert window._simple_attention_count.toolTip() == "No assets currently need attention."
        _close_window(window)

    @_skip_no_qt
    def test_simple_mode_count_labels_switch_filters(self, qapp, tmp_path):
        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        (source_dir / "fonts").mkdir(parents=True)
        (source_dir / "hero.png").write_bytes(b"png")
        (source_dir / "fonts" / "display.ttf").write_bytes(b"ttf")
        (source_dir / "intro.mp4").write_bytes(b"mp4")

        window = ResourceGeneratorWindow("")
        window.show()
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {
                "img": [{"file": "hero.png", "name": "hero"}],
                "font": [{"file": "fonts/display.ttf", "name": "display", "text": ""}],
                "mp4": [{"file": "intro.mp4", "name": "intro", "fps": 24, "width": 0, "height": 180}],
            },
            dirty=False,
        )
        qapp.processEvents()

        QTest.mouseClick(window._simple_font_count, Qt.LeftButton)
        qapp.processEvents()
        assert window._simple_asset_type_filter.currentData() == "font"
        assert window._simple_asset_table.rowCount() == 1
        assert window._simple_asset_table.item(0, 1).text() == "display"
        assert window._simple_asset_table.selectionModel().selectedRows()[0].row() == 0
        assert window._simple_asset_preview_title.text() == "Fonts: display"

        QTest.mouseClick(window._simple_mp4_count, Qt.LeftButton)
        qapp.processEvents()
        assert window._simple_asset_type_filter.currentData() == "mp4"
        assert window._simple_asset_table.rowCount() == 1
        assert window._simple_asset_table.item(0, 1).text() == "intro"
        assert window._simple_asset_preview_title.text() == "MP4: intro"

        QTest.mouseClick(window._simple_attention_count, Qt.LeftButton)
        qapp.processEvents()
        assert window._simple_asset_type_filter.currentData() == "attention"
        assert [window._simple_asset_table.item(row, 1).text() for row in range(window._simple_asset_table.rowCount())] == [
            "display",
            "intro",
        ]
        assert window._simple_asset_table.selectionModel().selectedRows()[0].row() == 1
        assert window._simple_asset_preview_title.text() == "MP4: intro"

        QTest.mouseClick(window._simple_image_count, Qt.LeftButton)
        qapp.processEvents()
        assert window._simple_asset_type_filter.currentData() == "img"
        assert window._simple_asset_table.rowCount() == 1
        assert window._simple_asset_table.item(0, 1).text() == "hero"
        assert window._simple_asset_preview_title.text() == "Images: hero"
        _close_window(window)

    @_skip_no_qt
    def test_simple_mode_asset_header_click_cycles_view_sort(self, qapp, tmp_path):
        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {
                "img": [
                    {"file": "zeta.png", "name": "zeta"},
                    {"file": "alpha.png", "name": "alpha"},
                    {"file": "mid.png", "name": "mid"},
                ]
            },
            dirty=False,
        )
        header = window._simple_asset_table.horizontalHeader()

        assert [window._simple_asset_table.item(row, 1).text() for row in range(window._simple_asset_table.rowCount())] == [
            "zeta",
            "alpha",
            "mid",
        ]
        assert header.isSortIndicatorShown() is False

        window._toggle_simple_asset_sort(1)
        qapp.processEvents()
        assert [window._simple_asset_table.item(row, 1).text() for row in range(window._simple_asset_table.rowCount())] == [
            "alpha",
            "mid",
            "zeta",
        ]
        assert header.isSortIndicatorShown() is True
        assert header.sortIndicatorSection() == 1
        assert header.sortIndicatorOrder() == Qt.AscendingOrder

        window._toggle_simple_asset_sort(1)
        qapp.processEvents()
        assert [window._simple_asset_table.item(row, 1).text() for row in range(window._simple_asset_table.rowCount())] == [
            "zeta",
            "mid",
            "alpha",
        ]
        assert header.sortIndicatorOrder() == Qt.DescendingOrder

        window._toggle_simple_asset_sort(1)
        qapp.processEvents()
        assert [window._simple_asset_table.item(row, 1).text() for row in range(window._simple_asset_table.rowCount())] == [
            "zeta",
            "alpha",
            "mid",
        ]
        assert header.isSortIndicatorShown() is False
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
    def test_simple_mode_preview_primary_action_button_tracks_selected_asset(self, qapp, tmp_path):
        from PyQt5.QtGui import QPixmap

        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        image_path = source_dir / "hero.png"
        pixmap = QPixmap(12, 8)
        assert pixmap.save(str(image_path), "PNG")
        (source_dir / "display.ttf").write_bytes(b"ttf")
        (source_dir / "intro.mp4").write_bytes(b"mp4")

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {
                "img": [{"file": "hero.png", "name": "hero"}],
                "font": [{"file": "display.ttf", "name": "display", "text": ""}],
                "mp4": [{"file": "intro.mp4", "name": "intro", "fps": 24, "width": 0, "height": 180}],
            },
            dirty=False,
        )

        window._simple_asset_table.clearSelection()
        qapp.processEvents()
        assert window._simple_asset_primary_action_button.isHidden() is True
        assert window._simple_asset_more_actions_button.isHidden() is True

        window._simple_asset_table.selectRow(0)
        qapp.processEvents()
        assert window._simple_asset_primary_action_button.isHidden() is False
        assert window._simple_asset_more_actions_button.isHidden() is False
        assert window._simple_asset_primary_action_button.text() == "Open Asset"

        window._simple_asset_table.selectRow(1)
        qapp.processEvents()
        assert window._simple_asset_primary_action_button.text() == "Edit Font Text..."

        window._simple_asset_table.selectRow(2)
        qapp.processEvents()
        assert window._simple_asset_primary_action_button.text() == "Detect Video Info"
        _close_window(window)

    @_skip_no_qt
    def test_simple_mode_disables_raster_image_tools_for_svg_assets(self, qapp, tmp_path):
        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        (source_dir / "icon.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24"></svg>\n',
            encoding="utf-8",
        )

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {"img": [{"file": "icon.svg", "name": "icon", "format": "svg"}], "font": [], "mp4": []},
            dirty=False,
        )

        window._simple_asset_table.selectRow(0)
        qapp.processEvents()

        assert window._duplicate_simple_asset_button.isEnabled() is True
        assert window._resize_image_button.isEnabled() is False
        assert window._rotate_image_button.isEnabled() is False
        assert window._resize_image_button.toolTip() == "Raster image tools are unavailable for SVG source assets."
        assert "Mode: Raw SVG" in window._simple_asset_meta.toPlainText()
        _close_window(window)

    @_skip_no_qt
    def test_simple_mode_preview_primary_action_button_uses_missing_file_recovery(self, qapp, monkeypatch, tmp_path):
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

        triggered = []
        monkeypatch.setattr(window, "_open_selected_asset_folder", lambda: triggered.append("folder"))

        assert window._simple_asset_primary_action_button.text() == "Open Asset Folder"
        window._simple_asset_primary_action_button.click()

        assert triggered == ["folder"]
        _close_window(window)

    @_skip_no_qt
    def test_simple_mode_preview_more_actions_button_opens_context_menu(self, qapp, monkeypatch, tmp_path):
        from PyQt5.QtWidgets import QMenu

        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        (source_dir / "hero.png").write_bytes(b"png")

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {"img": [{"file": "hero.png", "name": "hero"}]},
            dirty=False,
        )
        window._simple_asset_table.selectRow(0)
        qapp.processEvents()

        executed = []

        class _FakeMenu(QMenu):
            def exec_(self, pos):
                executed.append((pos.x(), pos.y()))

        monkeypatch.setattr(window, "_build_simple_asset_context_menu", lambda row=None: _FakeMenu(window))

        window._simple_asset_more_actions_button.click()

        assert len(executed) == 1
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
        assert set(window._window_shortcuts) >= {"Ctrl+F", "Delete", "Ctrl+D", "Ctrl+E", "Return", "Enter", "Shift+F10"}

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
    def test_simple_asset_table_shortcuts_trigger_primary_and_more_actions(self, qapp, monkeypatch, tmp_path):
        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        (source_dir / "hero.png").write_bytes(b"png")

        window = ResourceGeneratorWindow("")
        window.show()
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {"img": [{"file": "hero.png", "name": "hero"}]},
            dirty=False,
        )
        window._simple_asset_table.selectRow(0)
        window._simple_asset_table.setFocus()
        qapp.processEvents()

        activated = []
        monkeypatch.setattr(window, "_open_selected_asset_in_external_editor", lambda: activated.append("open"))

        menus = []

        class _FakeMenu:
            def exec_(self, pos):
                menus.append((pos.x(), pos.y()))

        monkeypatch.setattr(window, "_build_simple_asset_context_menu", lambda row=None: _FakeMenu())

        window._window_shortcuts["Return"].activated.emit()
        window._window_shortcuts["Shift+F10"].activated.emit()

        assert activated == ["open"]
        assert len(menus) == 1
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
        window._toggle_simple_asset_sort(2)
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
        assert reopened._simple_asset_sort_column == 2
        assert reopened._simple_asset_sort_descending is False
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
    def test_resource_generator_rejects_drag_for_designer_managed_paths(self, qapp, tmp_path):
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        designer_dir = tmp_path / "resource" / "src" / ".designer"
        designer_dir.mkdir(parents=True)
        (designer_dir / "display.ttf").write_bytes(b"ttf")
        window = ResourceGeneratorWindow("")
        file_event = _FakeUrlDropEvent([designer_dir / "display.ttf"])
        dir_event = _FakeUrlDropEvent([designer_dir])

        window.dragEnterEvent(file_event)
        window.dragEnterEvent(dir_event)

        assert file_event.accepted is False
        assert file_event.ignored is True
        assert dir_event.accepted is False
        assert dir_event.ignored is True
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

        assert {
            "Open Asset",
            "Open Asset Folder",
            "Edit Font Text",
            "Manage Text Files",
            "Copy Resource Name",
            "Copy Asset Path",
            "Copy Full Path",
            "Duplicate",
            "Remove",
            "Open Professional Mode",
        } <= set(action_map)
        assert not any(action.text().startswith("Suggested Fix:") for action in menu.actions() if action.text())
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

        assert "Suggested Fix: Open Asset Folder" in action_map
        assert action_map["Open Asset"].isEnabled() is False
        assert action_map["Open Asset Folder"].isEnabled() is True
        assert action_map["Copy Asset Path"].isEnabled() is True
        assert action_map["Copy Full Path"].isEnabled() is True
        assert window._simple_asset_table.item(0, 0).toolTip() == (
            "Asset file is missing.\n"
            "Fix: Use Open Asset Folder to restore the missing file, or remove the asset from the config."
        )
        _close_window(window)

    @_skip_no_qt
    def test_simple_asset_context_menu_exposes_font_fix_action_for_missing_text(self, qapp, tmp_path):
        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        fonts_dir = source_dir / "fonts"
        fonts_dir.mkdir(parents=True)
        (fonts_dir / "display.ttf").write_bytes(b"ttf")

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {"font": [{"file": "fonts/display.ttf", "name": "display", "text": ""}]},
            dirty=False,
        )
        window._simple_asset_table.selectRow(0)
        qapp.processEvents()

        menu = window._build_simple_asset_context_menu()
        action_texts = [action.text() for action in menu.actions() if action.text()]

        assert action_texts[0] == "Suggested Fix: Edit Font Text..."
        assert "Edit Font Text" not in action_texts
        _close_window(window)

    @_skip_no_qt
    def test_copy_full_path_for_missing_asset_uses_expected_target(self, qapp, tmp_path):
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

        QApplication.clipboard().clear()
        window._copy_selected_simple_asset_absolute_path()

        assert QApplication.clipboard().text() == str(source_dir / "images" / "missing.png")
        assert window._status_label.text() == f"Copied expected full asset path '{source_dir / 'images' / 'missing.png'}'."
        _close_window(window)

    @_skip_no_qt
    def test_simple_asset_context_menu_suggested_fix_updates_video_metadata(self, qapp, monkeypatch, tmp_path):
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
            {"img": [], "font": [], "mp4": [{"file": "intro.mp4", "name": "intro", "fps": 24, "width": 0, "height": 180}]},
            dirty=False,
        )
        window._simple_asset_table.selectRow(0)
        qapp.processEvents()

        menu = window._build_simple_asset_context_menu()
        action_map = {action.text(): action for action in menu.actions() if action.text()}

        assert "Suggested Fix: Detect Video Info" in action_map
        action_map["Suggested Fix: Detect Video Info"].trigger()

        entry = window._session.section_entries("mp4")[0]
        assert entry["width"] == 320
        assert entry["height"] == 180
        assert window._status_label.text() == "Updated video metadata for 'intro' (24fps 320x180)."
        _close_window(window)

    @_skip_no_qt
    def test_activate_selected_simple_asset_uses_font_fix_action(self, qapp, monkeypatch, tmp_path):
        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        fonts_dir = source_dir / "fonts"
        fonts_dir.mkdir(parents=True)
        (fonts_dir / "display.ttf").write_bytes(b"ttf")

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {"font": [{"file": "fonts/display.ttf", "name": "display", "text": ""}]},
            dirty=False,
        )
        window._simple_asset_table.selectRow(0)
        qapp.processEvents()

        activated = []
        monkeypatch.setattr(window, "_open_selected_font_text_resource", lambda: activated.append("font_text"))

        window._activate_selected_simple_asset()

        assert activated == ["font_text"]
        _close_window(window)

    @_skip_no_qt
    def test_activate_selected_simple_asset_opens_existing_asset(self, qapp, monkeypatch, tmp_path):
        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        (source_dir / "hero.png").write_bytes(b"png")

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {"img": [{"file": "hero.png", "name": "hero"}]},
            dirty=False,
        )
        window._simple_asset_table.selectRow(0)
        qapp.processEvents()

        opened = []
        monkeypatch.setattr(window, "_open_selected_asset_in_external_editor", lambda: opened.append("asset"))

        window._activate_selected_simple_asset()

        assert opened == ["asset"]
        _close_window(window)

    @_skip_no_qt
    def test_activate_selected_simple_asset_opens_asset_folder_for_missing_file(self, qapp, monkeypatch, tmp_path):
        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {"img": [{"file": "missing.png", "name": "missing"}]},
            dirty=False,
        )
        window._simple_asset_table.selectRow(0)
        qapp.processEvents()

        opened = []
        monkeypatch.setattr(window, "_open_selected_asset_folder", lambda: opened.append("folder"))

        window._activate_selected_simple_asset()

        assert opened == ["folder"]
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
        assert all(_layout_margins_tuple(card.layout()) == (6, 6, 6, 6) for card in cards)
        assert all(card.layout().spacing() == 4 for card in cards)
        meta_labels = dialog.findChildren(QLabel, "quick_preview_meta")
        assert any("Image Size: 12 x 8" in label.text() for label in meta_labels)
        assert any("Preview Source: fonts/display.txt" in label.text() for label in meta_labels)
        assert any("Video: 24fps 320x180" in label.text() for label in meta_labels)
        dialog.close()
        _close_window(window)

    @_skip_no_qt
    def test_quick_preview_board_palette_uses_active_theme_tokens(self, qapp):
        from ui_designer.ui.resource_generator_window import _quick_preview_board_palette
        from ui_designer.ui.theme import app_theme_tokens

        tokens = app_theme_tokens(qapp)
        palette = _quick_preview_board_palette()

        assert palette["page_bg"].name().lower() == tokens["bg"].lower()
        assert palette["title_text"].name().lower() == tokens["text"].lower()
        assert palette["subtitle_text"].name().lower() == tokens["text_muted"].lower()
        assert palette["card_border"].name().lower() == tokens["border"].lower()
        assert palette["card_fill"].name().lower() == tokens["panel_raised"].lower()
        assert palette["preview_border"].name().lower() == tokens["border_strong"].lower()
        assert palette["preview_fill"].name().lower() == tokens["panel_alt"].lower()
        assert palette["meta_text"].name().lower() == tokens["text_soft"].lower()

    def test_quick_preview_board_typography_uses_compact_scale(self):
        from ui_designer.ui.resource_generator_window import _quick_preview_board_font_sizes

        assert _quick_preview_board_font_sizes() == {
            "title": 18,
            "subtitle": 10,
            "card_title": 11,
            "preview": 10,
            "meta": 10,
        }

    @_skip_no_qt
    def test_quick_preview_board_fonts_use_designer_ui_pixels(self, qapp):
        from PyQt5.QtGui import QFont

        from ui_designer.ui.resource_generator_window import _quick_preview_board_font

        title_font = _quick_preview_board_font("title", bold=True)
        subtitle_font = _quick_preview_board_font("subtitle")
        card_title_font = _quick_preview_board_font("card_title", bold=True)
        preview_font = _quick_preview_board_font("preview")
        meta_font = _quick_preview_board_font("meta")

        assert title_font.pixelSize() == 18
        assert title_font.weight() == QFont.Bold
        assert subtitle_font.pixelSize() == 10
        assert card_title_font.pixelSize() == 11
        assert card_title_font.weight() == QFont.Bold
        assert preview_font.pixelSize() == 10
        assert meta_font.pixelSize() == 10

    @_skip_no_qt
    def test_resource_generator_headings_use_designer_ui_font_family(self, qapp):
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow
        from ui_designer.ui.theme import designer_ui_font

        window = ResourceGeneratorWindow("")

        try:
            expected_family = designer_ui_font().family()
            assert window._simple_action_tabs.tabBar().font().family() == expected_family
            assert window._simple_asset_empty_title.font().family() == expected_family
            assert window._simple_asset_table.horizontalHeader().font().family() == expected_family
        finally:
            _close_window(window)

    @_skip_no_qt
    def test_quick_placeholder_palette_chooses_theme_aware_contrast_text(self, qapp):
        from PyQt5.QtGui import QColor

        from ui_designer.ui.resource_generator_window import _quick_placeholder_palette
        from ui_designer.ui.theme import app_theme_tokens

        dark_palette = _quick_placeholder_palette("Hero Banner")
        dark_tokens = app_theme_tokens(qapp)
        dark_expected = max(
            (QColor(dark_tokens["text"]), QColor(dark_tokens["bg"])),
            key=lambda color: abs(int(dark_palette["background"].lightness()) - int(color.lightness())),
        )
        assert dark_palette["text"].name().lower() == dark_expected.name().lower()

        qapp.setProperty("designer_theme_mode", "light")
        try:
            light_palette = _quick_placeholder_palette("Hero Banner")
            light_tokens = app_theme_tokens(qapp)
            light_expected = max(
                (QColor(light_tokens["text"]), QColor(light_tokens["bg"])),
                key=lambda color: abs(int(light_palette["background"].lightness()) - int(color.lightness())),
            )
            assert light_palette["text"].name().lower() == light_expected.name().lower()
        finally:
            qapp.setProperty("designer_theme_mode", None)

    @_skip_no_qt
    def test_quick_placeholder_pixmap_uses_pixel_sized_designer_ui_font(self, qapp, monkeypatch):
        from PyQt5.QtGui import QFont

        import ui_designer.ui.resource_generator_window as resource_generator_window_module

        captured = {}
        original_designer_ui_font = resource_generator_window_module.designer_ui_font

        def _capture_font(*, point_size=None, pixel_size=None, weight=None, app=None):
            captured["point_size"] = point_size
            captured["pixel_size"] = pixel_size
            captured["weight"] = weight
            return original_designer_ui_font(
                point_size=point_size,
                pixel_size=pixel_size,
                weight=weight,
                app=app,
            )

        monkeypatch.setattr(resource_generator_window_module, "designer_ui_font", _capture_font)

        pixmap = resource_generator_window_module._build_quick_placeholder_pixmap(
            "Hero Banner",
            width=220,
            height=120,
        )

        assert pixmap.isNull() is False
        assert pixmap.width() == 220
        assert pixmap.height() == 120
        assert captured["point_size"] is None
        assert captured["pixel_size"] == 20
        assert captured["weight"] == QFont.Bold

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
    def test_quick_preview_board_dialog_uses_compact_spacing(self, qapp):
        from PyQt5.QtWidgets import QLabel

        from ui_designer.ui.resource_generator_window import _QuickPreviewBoardDialog

        cards = [QLabel(f"Asset {index}") for index in range(4)]
        dialog = _QuickPreviewBoardDialog(cards, total_assets=len(cards), parent=None)
        try:
            layout = dialog.layout()
            assert _layout_margins_tuple(layout) == (12, 12, 12, 12)
            assert layout.spacing() == 4
            assert dialog._cards_layout.horizontalSpacing() == 4
            assert dialog._cards_layout.verticalSpacing() == 4
        finally:
            dialog.close()

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
    def test_config_path_edit_rejects_designer_managed_path(self, qapp, monkeypatch, tmp_path):
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        original_config = tmp_path / "OldApp" / "resource" / "src" / "app_resource_config.json"
        reserved_config = tmp_path / "OldApp" / "resource" / "src" / ".designer" / "app_resource_config_designer.json"
        warnings = []

        monkeypatch.setattr(
            QMessageBox,
            "warning",
            lambda *args: warnings.append((args[1], args[2])) or QMessageBox.Ok,
        )
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)

        window = ResourceGeneratorWindow("")
        window.open_with_paths(infer_generation_paths(str(original_config)), load_existing=False)
        qapp.processEvents()
        expected = infer_generation_paths(str(original_config))
        window._config_path_edit.setText(str(reserved_config))

        window._on_path_edited("config_path", window._config_path_edit)

        assert window._session.paths.config_path == expected.config_path
        assert window._config_path_edit.text() == expected.config_path
        assert warnings
        assert warnings[-1][0] == "Config Path"
        assert "Designer-managed" in warnings[-1][1]
        assert str((reserved_config.parent.parent / "app_resource_config.json").resolve()) in warnings[-1][1]
        _close_window(window)

    @_skip_no_qt
    def test_sync_path_widgets_to_session_rejects_designer_managed_config_path(self, qapp, monkeypatch, tmp_path):
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        original_config = tmp_path / "OldApp" / "resource" / "src" / "app_resource_config.json"
        reserved_config = tmp_path / "OldApp" / "resource" / "src" / ".designer" / "app_resource_config_designer.json"
        warnings = []

        monkeypatch.setattr(
            QMessageBox,
            "warning",
            lambda *args: warnings.append((args[1], args[2])) or QMessageBox.Ok,
        )
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)

        window = ResourceGeneratorWindow("")
        window.open_with_paths(infer_generation_paths(str(original_config)), load_existing=False)
        qapp.processEvents()
        expected = infer_generation_paths(str(original_config))
        window._config_path_edit.setText(str(reserved_config))

        synced = window._sync_path_widgets_to_session()

        assert synced is False
        assert window._session.paths.config_path == expected.config_path
        assert window._config_path_edit.text() == expected.config_path
        assert warnings
        assert warnings[-1][0] == "Config Path"
        assert "Designer-managed" in warnings[-1][1]
        assert str((reserved_config.parent.parent / "app_resource_config.json").resolve()) in warnings[-1][1]
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
    def test_save_as_rejects_designer_managed_config_path(self, qapp, monkeypatch, tmp_path):
        from PyQt5.QtWidgets import QFileDialog

        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        warnings = []
        monkeypatch.setattr(
            QMessageBox,
            "warning",
            lambda *args: warnings.append((args[1], args[2])) or QMessageBox.Ok,
        )
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)

        original_config = tmp_path / "OldApp" / "resource" / "src" / "app_resource_config.json"
        reserved_config = tmp_path / "OldApp" / "resource" / "src" / ".designer" / "app_resource_config_designer.json"

        window = ResourceGeneratorWindow("")
        window.open_with_paths(infer_generation_paths(str(original_config)), load_existing=False)
        qapp.processEvents()

        monkeypatch.setattr(
            QFileDialog,
            "getSaveFileName",
            lambda *args, **kwargs: (str(reserved_config), "Resource Config (*.json)"),
        )

        assert window._save_config_as() is False
        assert warnings
        assert warnings[-1][0] == "Save Resource Config"
        assert "Designer-managed" in warnings[-1][1]
        assert str((reserved_config.parent.parent / "app_resource_config.json").resolve()) in warnings[-1][1]
        assert not reserved_config.exists()
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
    def test_scan_assets_from_directory_rejects_designer_root_as_source_dir(self, qapp, monkeypatch, tmp_path):
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        designer_dir = tmp_path / "imports" / ".designer"
        designer_dir.mkdir(parents=True)
        (designer_dir / "display.ttf").write_bytes(b"ttf")
        warnings = []

        monkeypatch.setattr(
            QMessageBox,
            "warning",
            lambda *args: warnings.append((args[1], args[2])) or QMessageBox.Ok,
        )

        window = ResourceGeneratorWindow("")
        window._scan_assets_from_directory(str(designer_dir))

        assert window._session.paths.source_dir == ""
        assert window._session.section_entries("font") == []
        assert warnings == [
            (
                "Source Dir",
                "'.designer' is Designer-managed and cannot be used as Source Dir.\nChoose a parent folder outside .designer.",
            )
        ]
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
    def test_import_assets_from_files_defaults_svg_entries_to_raw_svg_mode(self, qapp, monkeypatch, tmp_path):
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        import_dir = tmp_path / "imports"
        import_dir.mkdir(parents=True)
        (import_dir / "logo.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24"></svg>\n',
            encoding="utf-8",
        )
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)

        window = ResourceGeneratorWindow("")
        window._import_assets_from_files([str(import_dir / "logo.svg")])

        entry = window._session.section_entries("img")[0]
        assert entry["file"] == "logo.svg"
        assert entry["format"] == "svg"
        assert "alpha" not in entry
        assert "dim" not in entry
        assert window._simple_asset_table.rowCount() == 1
        assert window._simple_asset_table.item(0, 3).text() == "raw svg"
        assert window._status_label.text() == "Imported 1 assets, added 1, updated Source Dir."
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
    def test_on_path_edited_rejects_designer_source_dir(self, qapp, monkeypatch, tmp_path):
        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        designer_dir = source_dir / ".designer"
        source_dir.mkdir(parents=True)
        designer_dir.mkdir(parents=True)
        warnings = []

        monkeypatch.setattr(
            QMessageBox,
            "warning",
            lambda *args: warnings.append((args[1], args[2])) or QMessageBox.Ok,
        )

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {"img": [], "font": [], "mp4": []},
            dirty=False,
        )
        window._source_dir_edit.setText(str(designer_dir))

        window._on_path_edited("source_dir", window._source_dir_edit)

        assert window._session.paths.source_dir == str(source_dir.resolve())
        assert window._source_dir_edit.text() == str(source_dir.resolve())
        assert warnings == [
            (
                "Source Dir",
                "'.designer' is Designer-managed and cannot be used as Source Dir.\nChoose a parent folder outside .designer.",
            )
        ]
        _close_window(window)

    @_skip_no_qt
    def test_sync_path_widgets_to_session_rejects_designer_source_dir(self, qapp, monkeypatch, tmp_path):
        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        designer_dir = source_dir / ".designer"
        source_dir.mkdir(parents=True)
        designer_dir.mkdir(parents=True)
        warnings = []

        monkeypatch.setattr(
            QMessageBox,
            "warning",
            lambda *args: warnings.append((args[1], args[2])) or QMessageBox.Ok,
        )

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {"img": [], "font": [], "mp4": []},
            dirty=False,
        )
        window._source_dir_edit.setText(str(designer_dir))

        synced = window._sync_path_widgets_to_session()

        assert synced is False
        assert window._session.paths.source_dir == str(source_dir.resolve())
        assert window._source_dir_edit.text() == str(source_dir.resolve())
        assert warnings == [
            (
                "Source Dir",
                "'.designer' is Designer-managed and cannot be used as Source Dir.\nChoose a parent folder outside .designer.",
            )
        ]
        _close_window(window)

    @_skip_no_qt
    def test_on_path_edited_rejects_designer_workspace_dir(self, qapp, monkeypatch, tmp_path):
        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        workspace_dir = tmp_path / "workspace"
        designer_workspace_dir = source_dir / ".designer" / "workspace"
        source_dir.mkdir(parents=True)
        workspace_dir.mkdir(parents=True)
        designer_workspace_dir.mkdir(parents=True)
        warnings = []

        monkeypatch.setattr(
            QMessageBox,
            "warning",
            lambda *args: warnings.append((args[1], args[2])) or QMessageBox.Ok,
        )

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir), workspace_dir=str(workspace_dir)),
            {"img": [], "font": [], "mp4": []},
            dirty=False,
        )
        window._workspace_dir_edit.setText(str(designer_workspace_dir))

        window._on_path_edited("workspace_dir", window._workspace_dir_edit)

        assert window._session.paths.workspace_dir == str(workspace_dir.resolve())
        assert window._workspace_dir_edit.text() == str(workspace_dir.resolve())
        assert warnings == [
            (
                "Workspace Dir",
                "'.designer/workspace' is Designer-managed and cannot be used as Workspace Dir.\nChoose a folder outside Designer-managed paths.",
            )
        ]
        _close_window(window)

    @_skip_no_qt
    def test_sync_path_widgets_to_session_rejects_designer_bin_output_dir(self, qapp, monkeypatch, tmp_path):
        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        bin_output_dir = tmp_path / "bin"
        designer_bin_dir = source_dir / ".designer" / "bin"
        source_dir.mkdir(parents=True)
        bin_output_dir.mkdir(parents=True)
        designer_bin_dir.mkdir(parents=True)
        warnings = []

        monkeypatch.setattr(
            QMessageBox,
            "warning",
            lambda *args: warnings.append((args[1], args[2])) or QMessageBox.Ok,
        )

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir), bin_output_dir=str(bin_output_dir)),
            {"img": [], "font": [], "mp4": []},
            dirty=False,
        )
        window._bin_output_dir_edit.setText(str(designer_bin_dir))

        synced = window._sync_path_widgets_to_session()

        assert synced is False
        assert window._session.paths.bin_output_dir == str(bin_output_dir.resolve())
        assert window._bin_output_dir_edit.text() == str(bin_output_dir.resolve())
        assert warnings == [
            (
                "Bin Output Dir",
                "'.designer/bin' is Designer-managed and cannot be used as Bin Output Dir.\nChoose a folder outside Designer-managed paths.",
            )
        ]
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
    def test_simple_mode_attention_preview_suggests_detect_video_info(self, qapp, tmp_path):
        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        (source_dir / "intro.mp4").write_bytes(b"mp4")

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {"img": [], "font": [], "mp4": [{"file": "intro.mp4", "name": "intro", "fps": 24, "width": 0, "height": 180}]},
            dirty=False,
        )

        window._simple_asset_type_filter.setCurrentIndex(window._simple_asset_type_filter.findData("attention"))
        qapp.processEvents()

        assert window._simple_asset_preview_title.text() == "MP4: intro"
        assert "Suggested Fix: Use Detect Video Info to fill fps, width, and height." in window._simple_asset_meta.toPlainText()
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
    def test_pack_assets_into_source_dir_rejects_designer_managed_external_paths_without_partial_copies(
        self, qapp, monkeypatch, tmp_path
    ):
        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        external_dir = tmp_path / "imports"
        external_dir.mkdir(parents=True)
        external_image = external_dir / "hero.png"
        external_image.write_bytes(b"png")
        designer_text = external_dir / ".designer" / "display.txt"
        designer_text.parent.mkdir(parents=True)
        designer_text.write_text("ABC", encoding="utf-8")
        warnings = []

        monkeypatch.setattr(
            QMessageBox,
            "warning",
            lambda *args: warnings.append((args[1], args[2])) or QMessageBox.Ok,
        )

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {
                "img": [{"file": str(external_image), "name": "hero"}],
                "font": [{"file": "display.ttf", "name": "display", "text": str(designer_text)}],
                "mp4": [],
            },
            dirty=False,
        )

        window._pack_assets_into_source_dir()

        assert warnings == [
            (
                "Pack Into Source Dir",
                "'.designer/display.txt' is reserved for Designer-generated files.\nChoose a different filename.",
            )
        ]
        assert not (source_dir / "hero.png").exists()
        assert not (source_dir / "display.txt").exists()
        assert window._session.section_entries("img")[0]["file"] == str(external_image)
        assert window._session.section_entries("font")[0]["text"] == str(designer_text)
        assert window.has_unsaved_changes() is False
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
    def test_organize_assets_into_standard_folders_rejects_designer_managed_paths(self, qapp, monkeypatch, tmp_path):
        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        (source_dir / "hero.png").write_bytes(b"png")
        (source_dir / "display.ttf").write_bytes(b"ttf")
        designer_text = source_dir / ".designer" / "display.txt"
        designer_text.parent.mkdir(parents=True)
        designer_text.write_text("ABC", encoding="utf-8")
        warnings = []

        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)
        monkeypatch.setattr(
            QMessageBox,
            "warning",
            lambda *args: warnings.append((args[1], args[2])) or QMessageBox.Ok,
        )

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {
                "img": [{"file": "hero.png", "name": "hero"}],
                "font": [{"file": "display.ttf", "name": "display", "text": ".designer/display.txt"}],
                "mp4": [],
            },
            dirty=False,
        )

        window._organize_assets_into_standard_folders()

        assert warnings == [
            (
                "Organize Folders",
                "'.designer/display.txt' is reserved for Designer-generated files.\nChoose a different filename.",
            )
        ]
        assert (source_dir / "hero.png").read_bytes() == b"png"
        assert (source_dir / "display.ttf").read_bytes() == b"ttf"
        assert designer_text.read_text(encoding="utf-8") == "ABC"
        assert not (source_dir / "images" / "hero.png").exists()
        assert window._session.section_entries("img")[0]["file"] == "hero.png"
        assert window._session.section_entries("font")[0]["text"] == ".designer/display.txt"
        assert window.has_unsaved_changes() is False
        _close_window(window)

    @_skip_no_qt
    def test_open_selected_font_text_resource_uses_active_font_and_detected_sibling_text(self, qapp, monkeypatch, tmp_path):
        from PyQt5.QtWidgets import QDialog

        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        fonts_dir = source_dir / "fonts"
        fonts_dir.mkdir(parents=True)
        (fonts_dir / "display.ttf").write_bytes(b"ttf")
        text_path = fonts_dir / "display.txt"
        text_path.write_text("ABC", encoding="utf-8")

        captured = {}

        class _FakeDialog:
            def __init__(self, *, filename, initial_text, is_new_file, parent=None):
                captured["filename"] = filename
                captured["initial_text"] = initial_text
                captured["is_new_file"] = is_new_file

            def exec_(self):
                return QDialog.Accepted

            def text_value(self):
                return "ABCD\n"

        monkeypatch.setattr("ui_designer.ui.resource_generator_window._FontTextEditorDialog", _FakeDialog)
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {"img": [], "font": [{"file": "fonts/display.ttf", "name": "display", "text": ""}], "mp4": []},
            dirty=False,
        )
        window._set_ui_mode("professional")
        window._active_section = "font"
        window._active_entry_index = 0
        window._refresh_section_selection()
        window._refresh_entry_table()
        window._update_form()
        window._simple_asset_table.clearSelection()
        qapp.processEvents()

        window._open_selected_font_text_resource()

        assert captured["filename"] == "fonts/display.txt"
        assert captured["initial_text"] == "ABC"
        assert captured["is_new_file"] is False
        assert text_path.read_text(encoding="utf-8") == "ABCD\n"
        assert window._session.section_entries("font")[0]["text"] == "fonts/display.txt"
        assert window.has_unsaved_changes() is True
        assert window._status_label.text() == "Saved font text 'fonts/display.txt'."
        _close_window(window)

    @_skip_no_qt
    def test_open_selected_font_text_resource_can_create_missing_file(self, qapp, monkeypatch, tmp_path):
        from PyQt5.QtWidgets import QDialog

        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        (source_dir / "display.ttf").write_bytes(b"ttf")

        captured = {}

        class _FakeDialog:
            def __init__(self, *, filename, initial_text, is_new_file, parent=None):
                captured["filename"] = filename
                captured["initial_text"] = initial_text
                captured["is_new_file"] = is_new_file

            def exec_(self):
                return QDialog.Accepted

            def text_value(self):
                return "HELLO\nWORLD\n"

        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)
        monkeypatch.setattr("ui_designer.ui.resource_generator_window._FontTextEditorDialog", _FakeDialog)

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
        assert captured["filename"] == "display_charset.txt"
        assert captured["is_new_file"] is True
        assert "HELLO" in captured["initial_text"]
        assert "Quick Brown Fox" in captured["initial_text"]
        assert text_path.read_text(encoding="utf-8") == "HELLO\nWORLD\n"
        assert window._session.section_entries("font")[0]["text"] == "display_charset.txt"
        assert window.has_unsaved_changes() is True
        assert window._status_label.text() == "Created and saved font text 'display_charset.txt'."
        _close_window(window)

    @_skip_no_qt
    def test_open_selected_font_text_resource_prompts_for_multi_text_target(self, qapp, monkeypatch, tmp_path):
        from PyQt5.QtWidgets import QDialog, QInputDialog

        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        (source_dir / "display.ttf").write_bytes(b"ttf")
        first_text = source_dir / "ui_text.txt"
        second_text = source_dir / "charset.txt"
        first_text.write_text("ABC", encoding="utf-8")
        second_text.write_text("XYZ", encoding="utf-8")

        captured = {}

        class _FakeDialog:
            def __init__(self, *, filename, initial_text, is_new_file, parent=None):
                captured["filename"] = filename
                captured["initial_text"] = initial_text
                captured["is_new_file"] = is_new_file

            def exec_(self):
                return QDialog.Accepted

            def text_value(self):
                return "XYZ+\n"

        monkeypatch.setattr("ui_designer.ui.resource_generator_window._FontTextEditorDialog", _FakeDialog)
        monkeypatch.setattr(QInputDialog, "getItem", lambda *args, **kwargs: ("charset.txt", True))

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {"img": [], "font": [{"file": "display.ttf", "name": "display", "text": "ui_text.txt,charset.txt"}], "mp4": []},
            dirty=False,
        )
        window._simple_asset_table.selectRow(0)
        qapp.processEvents()

        window._open_selected_font_text_resource()

        assert captured["filename"] == "charset.txt"
        assert captured["initial_text"] == "XYZ"
        assert captured["is_new_file"] is False
        assert first_text.read_text(encoding="utf-8") == "ABC"
        assert second_text.read_text(encoding="utf-8") == "XYZ+\n"
        assert window._status_label.text() == "Saved font text 'charset.txt'."
        _close_window(window)

    @_skip_no_qt
    def test_open_selected_font_text_links_editor_updates_entry_and_status(self, qapp, monkeypatch, tmp_path):
        from PyQt5.QtWidgets import QDialog, QMessageBox

        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        source_dir_text = str(source_dir)

        class _FakeDialog:
            def __init__(self, *, initial_items, source_dir, normalize_file_callback=None, edit_file_callback=None, parent=None):
                assert initial_items == ["ui_text.txt"]
                assert source_dir == source_dir_text
                assert callable(normalize_file_callback)
                assert callable(edit_file_callback)

            def exec_(self):
                return QDialog.Accepted

            def text_value(self):
                return "ui_text.txt\ncharset.txt\n"

        monkeypatch.setattr("ui_designer.ui.resource_generator_window._FontTextLinksDialog", _FakeDialog)
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {"img": [], "font": [{"file": "display.ttf", "name": "display", "text": "ui_text.txt"}], "mp4": []},
            dirty=False,
        )
        window._active_section = "font"
        window._active_entry_index = 0
        window._set_ui_mode("professional")
        window._refresh_entry_table()
        window._update_form()

        window._open_selected_font_text_links_editor()

        entry = window._session.section_entries("font")[0]
        assert entry["text"] == "ui_text.txt,charset.txt"
        assert window.has_unsaved_changes() is True
        assert window._status_label.text() == "Updated font text links for 'display'."
        _close_window(window)

    @_skip_no_qt
    def test_open_selected_font_text_links_editor_keeps_clean_state_when_value_is_unchanged(self, qapp, monkeypatch, tmp_path):
        from PyQt5.QtWidgets import QDialog

        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)

        class _FakeDialog:
            def __init__(self, *, initial_items, source_dir, normalize_file_callback=None, edit_file_callback=None, parent=None):
                assert initial_items == ["ui_text.txt", "charset.txt"]
                assert callable(edit_file_callback)

            def exec_(self):
                return QDialog.Accepted

            def text_value(self):
                return " ui_text.txt ;\ncharset.txt "

        monkeypatch.setattr("ui_designer.ui.resource_generator_window._FontTextLinksDialog", _FakeDialog)

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {"img": [], "font": [{"file": "display.ttf", "name": "display", "text": "ui_text.txt,charset.txt"}], "mp4": []},
            dirty=False,
        )
        window._active_section = "font"
        window._active_entry_index = 0
        window._set_ui_mode("professional")
        window._refresh_entry_table()
        window._update_form()
        previous_status = window._status_label.text()

        window._open_selected_font_text_links_editor()

        entry = window._session.section_entries("font")[0]
        assert entry["text"] == "ui_text.txt,charset.txt"
        assert window.has_unsaved_changes() is False
        assert window._status_label.text() == previous_status
        _close_window(window)

    @_skip_no_qt
    def test_open_specific_font_text_resource_can_skip_assignment_for_links_dialog(self, qapp, monkeypatch, tmp_path):
        from PyQt5.QtWidgets import QDialog, QMessageBox

        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)

        class _FakeDialog:
            def __init__(self, *, filename, initial_text, is_new_file, parent=None):
                assert filename == "charset.txt"
                assert is_new_file is True
                assert initial_text.startswith("HELLO")

            def exec_(self):
                return QDialog.Accepted

            def text_value(self):
                return "ABC\n"

        monkeypatch.setattr("ui_designer.ui.resource_generator_window._FontTextEditorDialog", _FakeDialog)
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected create confirmation")))

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {"img": [], "font": [{"file": "display.ttf", "name": "display", "text": "ui_text.txt"}], "mp4": []},
            dirty=False,
        )

        entry = window._session.section_entries("font")[0]
        result = window._open_specific_font_text_resource(
            0,
            entry,
            "charset.txt",
            assign_to_font=False,
            confirm_create=False,
        )

        assert result is True
        assert entry["text"] == "ui_text.txt"
        assert window.has_unsaved_changes() is False
        assert (source_dir / "charset.txt").read_text(encoding="utf-8") == "ABC\n"
        assert window._status_label.text() == "Created and saved font text 'charset.txt'."
        _close_window(window)

    @_skip_no_qt
    def test_font_text_links_dialog_supports_add_edit_remove_and_reorder(self, qapp, monkeypatch, tmp_path):
        from PyQt5.QtWidgets import QInputDialog

        from ui_designer.ui.resource_generator_window import _FontTextLinksDialog

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        (source_dir / "ui_text.txt").write_text("abc", encoding="utf-8")

        prompts = iter(
            [
                ("extra.txt", True),
                ("renamed.txt", True),
            ]
        )
        monkeypatch.setattr(QInputDialog, "getText", lambda *args, **kwargs: next(prompts))

        dialog = _FontTextLinksDialog(initial_items=["ui_text.txt", "missing.txt"], source_dir=str(source_dir), parent=None)

        assert dialog._list_widget.dragDropMode() == QAbstractItemView.InternalMove
        assert dialog._count_label.text() == "Linked text files: 2 | Missing: 1"
        assert dialog._remove_missing_button.isEnabled() is True
        assert dialog.text_value() == "ui_text.txt\nmissing.txt"

        dialog._add_path()
        assert dialog.text_value() == "ui_text.txt\nmissing.txt\nextra.txt"
        assert dialog._count_label.text() == "Linked text files: 3 | Missing: 2"

        dialog._list_widget.setCurrentRow(2)
        dialog._edit_selected_path()
        assert dialog.text_value() == "ui_text.txt\nmissing.txt\nrenamed.txt"

        dialog._list_widget.setCurrentRow(2)
        dialog._move_selected_path(-1)
        assert dialog.text_value() == "ui_text.txt\nrenamed.txt\nmissing.txt"

        dialog._list_widget.setCurrentRow(2)
        dialog._remove_selected_path()
        assert dialog.text_value() == "ui_text.txt\nrenamed.txt"
        assert dialog._count_label.text() == "Linked text files: 2 | Missing: 1"

        dialog._remove_missing_paths()
        assert dialog.text_value() == "ui_text.txt"
        assert dialog._count_label.text() == "Linked text files: 1"
        assert dialog._remove_missing_button.isEnabled() is False
        dialog.close()

    @_skip_no_qt
    @pytest.mark.parametrize(
        ("dialog_name", "kwargs"),
        [
            ("_QuickImageResizeDialog", {"width": 320, "height": 240, "output_filename": "hero.png"}),
            ("_QuickImageRotateDialog", {"width": 320, "height": 240, "output_filename": "hero.png"}),
            ("_QuickImageFlipDialog", {"output_filename": "hero.png"}),
            ("_QuickImageCropDialog", {"width": 320, "height": 240, "output_filename": "hero.png"}),
            ("_QuickImageBorderDialog", {"output_filename": "hero.png"}),
            ("_QuickImageBackgroundDialog", {"output_filename": "hero.png"}),
            ("_QuickImageRoundCornersDialog", {"width": 320, "height": 240, "output_filename": "hero.png"}),
            ("_QuickImageOpacityDialog", {"output_filename": "hero.png"}),
            ("_QuickThumbnailBatchDialog", {"width": 320, "height": 240, "output_folder": "thumbnails", "suffix": "_thumb"}),
            ("_QuickImageNormalizeDialog", {"output_folder": "normalized", "suffix": "_normalized"}),
            ("_QuickImageCompressDialog", {"output_folder": "compressed", "suffix": "_compressed", "colors": 64}),
            ("_QuickFontPrerenderDialog", {"output_folder": "font_previews", "suffix": "_preview", "sample_text": ""}),
            ("_QuickImagePlaceholderDialog", {"width": 320, "height": 240, "output_folder": "placeholders"}),
        ],
    )
    def test_quick_resource_dialogs_use_compact_shell_and_form_spacing(self, qapp, dialog_name, kwargs):
        from PyQt5.QtWidgets import QFormLayout

        import ui_designer.ui.resource_generator_window as resource_generator_window_module

        dialog_cls = getattr(resource_generator_window_module, dialog_name)
        dialog = dialog_cls(parent=None, **kwargs)
        try:
            layout = dialog.layout()
            assert _layout_margins_tuple(layout) == (12, 12, 12, 12)
            assert layout.spacing() == 6

            form = next(
                (
                    child_layout
                    for index in range(layout.count())
                    if (child_layout := layout.itemAt(index).layout()) is not None and isinstance(child_layout, QFormLayout)
                ),
                None,
            )
            assert form is not None
            assert form.spacing() == 4
        finally:
            dialog.close()

    @_skip_no_qt
    def test_font_text_dialogs_use_compact_shell_spacing(self, qapp, tmp_path):
        from ui_designer.ui.resource_generator_window import _FontTextEditorDialog, _FontTextLinksDialog

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        (source_dir / "ui_text.txt").write_text("HELLO", encoding="utf-8")

        editor_dialog = _FontTextEditorDialog(
            filename="charset/ui_text.txt",
            initial_text="HELLO",
            is_new_file=False,
            parent=None,
        )
        links_dialog = _FontTextLinksDialog(
            initial_items=["ui_text.txt"],
            source_dir=str(source_dir),
            parent=None,
        )
        try:
            editor_layout = editor_dialog.layout()
            assert _layout_margins_tuple(editor_layout) == (12, 12, 12, 12)
            assert editor_layout.spacing() == 6

            links_layout = links_dialog.layout()
            assert _layout_margins_tuple(links_layout) == (12, 12, 12, 12)
            assert links_layout.spacing() == 6

            content_row = next(
                (
                    child_layout
                    for index in range(links_layout.count())
                    if (child_layout := links_layout.itemAt(index).layout()) is not None
                    and child_layout.count() > 0
                    and child_layout.itemAt(0).widget() is links_dialog._list_widget
                ),
                None,
            )
            assert content_row is not None
            assert content_row.spacing() == 4
            assert content_row.itemAt(1).layout().spacing() == 4
            assert links_dialog._preview_splitter.widget(0).layout().spacing() == 4
            assert links_dialog._preview_splitter.widget(1).layout().spacing() == 4
        finally:
            editor_dialog.close()
            links_dialog.close()

    @_skip_no_qt
    def test_font_text_links_dialog_updates_preview_for_selected_item(self, qapp, tmp_path):
        from ui_designer.ui.resource_generator_window import _FontTextLinksDialog

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        (source_dir / "ui_text.txt").write_text("HELLO\nDesigner\n", encoding="utf-8")

        dialog = _FontTextLinksDialog(
            initial_items=["ui_text.txt", "missing.txt"],
            source_dir=str(source_dir),
            parent=None,
        )

        assert dialog._preview_splitter.orientation() == Qt.Vertical
        assert dialog._preview_splitter.childrenCollapsible() is False
        assert dialog._edit_file_button.text() == "Edit File..."
        assert dialog._preview_sample_label.text() == "Preview Sample: HELLO Designer\nPreview Source: ui_text.txt"
        assert dialog._preview_info_label.text() == "Preview: 2 line(s), 15 char(s)"
        assert dialog._preview_text_edit.minimumHeight() == dialog._text_preview_minimum_height(
            dialog._preview_text_edit,
            visible_lines=4,
        )
        assert dialog._preview_text_edit.toPlainText() == "HELLO\nDesigner\n"
        assert dialog._combined_preview_info_label.text() == "Combined Preview: 1 file(s), 1 missing"
        assert dialog._combined_preview_text_edit.minimumHeight() == dialog._text_preview_minimum_height(
            dialog._combined_preview_text_edit,
            visible_lines=5,
        )
        assert dialog._combined_preview_text_edit.toPlainText() == "[ui_text.txt]\nHELLO\nDesigner\n\n[missing.txt]\n(missing)"

        dialog._list_widget.setCurrentRow(1)

        assert dialog._edit_file_button.text() == "Edit File..."
        assert dialog._preview_sample_label.text() == "Preview Sample: HELLO Designer\nPreview Source: ui_text.txt"
        assert dialog._preview_info_label.text() == "Preview: File is missing."
        assert dialog._preview_text_edit.toPlainText() == ""
        dialog.close()

    @_skip_no_qt
    def test_font_text_links_dialog_preview_heights_follow_runtime_tokens(self, qapp, monkeypatch, tmp_path):
        import ui_designer.ui.resource_generator_window as resource_generator_window_module
        from ui_designer.ui.resource_generator_window import _FontTextLinksDialog

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)

        baseline_dialog = _FontTextLinksDialog(initial_items=[], source_dir=str(source_dir), parent=None)
        baseline_preview_height = baseline_dialog._preview_text_edit.minimumHeight()
        baseline_combined_height = baseline_dialog._combined_preview_text_edit.minimumHeight()
        baseline_dialog.close()

        preview_tokens = dict(resource_generator_window_module.app_theme_tokens())
        preview_tokens["h_tab_min"] = 28
        preview_tokens["space_xxs"] = 5
        preview_tokens["space_sm"] = 10
        monkeypatch.setattr(resource_generator_window_module, "app_theme_tokens", lambda *args, **kwargs: preview_tokens)

        dialog = _FontTextLinksDialog(initial_items=[], source_dir=str(source_dir), parent=None)

        assert dialog._preview_text_edit.minimumHeight() == dialog._text_preview_minimum_height(
            dialog._preview_text_edit,
            visible_lines=4,
        )
        assert dialog._combined_preview_text_edit.minimumHeight() == dialog._text_preview_minimum_height(
            dialog._combined_preview_text_edit,
            visible_lines=5,
        )
        assert dialog._preview_text_edit.minimumHeight() > baseline_preview_height
        assert dialog._combined_preview_text_edit.minimumHeight() > baseline_combined_height
        dialog.close()

    @_skip_no_qt
    def test_font_text_links_dialog_can_create_new_file_via_callback(self, qapp, monkeypatch, tmp_path):
        from PyQt5.QtWidgets import QInputDialog

        from ui_designer.ui.resource_generator_window import _FontTextLinksDialog

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        (source_dir / "ui_text.txt").write_text("abc", encoding="utf-8")
        created_path = source_dir / "charset" / "new.txt"
        captured = []

        def _edit_file(value):
            captured.append(value)
            created_path.parent.mkdir(parents=True, exist_ok=True)
            created_path.write_text("ABC", encoding="utf-8")
            return True

        monkeypatch.setattr(QInputDialog, "getText", lambda *args, **kwargs: ("charset/new.txt", True))

        dialog = _FontTextLinksDialog(
            initial_items=["ui_text.txt"],
            source_dir=str(source_dir),
            edit_file_callback=_edit_file,
            parent=None,
        )

        dialog._new_file()

        assert captured == ["charset/new.txt"]
        assert created_path.read_text(encoding="utf-8") == "ABC"
        assert dialog.text_value() == "ui_text.txt\ncharset/new.txt"
        assert dialog._count_label.text() == "Linked text files: 2"
        dialog.close()

    @_skip_no_qt
    def test_font_text_links_dialog_does_not_add_new_file_when_creation_is_canceled(self, qapp, monkeypatch, tmp_path):
        from PyQt5.QtWidgets import QInputDialog

        from ui_designer.ui.resource_generator_window import _FontTextLinksDialog

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        (source_dir / "ui_text.txt").write_text("abc", encoding="utf-8")
        captured = []

        def _edit_file(value):
            captured.append(value)
            return False

        monkeypatch.setattr(QInputDialog, "getText", lambda *args, **kwargs: ("charset/new.txt", True))

        dialog = _FontTextLinksDialog(
            initial_items=["ui_text.txt"],
            source_dir=str(source_dir),
            edit_file_callback=_edit_file,
            parent=None,
        )

        dialog._new_file()

        assert captured == ["charset/new.txt"]
        assert dialog.text_value() == "ui_text.txt"
        assert dialog._count_label.text() == "Linked text files: 1"
        assert not (source_dir / "charset" / "new.txt").exists()
        dialog.close()

    @_skip_no_qt
    def test_font_text_links_dialog_activation_prefers_editing_file_when_available(self, qapp, tmp_path):
        from ui_designer.ui.resource_generator_window import _FontTextLinksDialog

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        (source_dir / "ui_text.txt").write_text("abc", encoding="utf-8")
        captured = []

        def _edit_file(value):
            captured.append(value)
            return True

        dialog = _FontTextLinksDialog(
            initial_items=["ui_text.txt"],
            source_dir=str(source_dir),
            edit_file_callback=_edit_file,
            parent=None,
        )
        dialog._list_widget.setCurrentRow(0)

        dialog._activate_selected_item()

        assert captured == ["ui_text.txt"]
        assert dialog.text_value() == "ui_text.txt"
        dialog.close()

    @_skip_no_qt
    def test_font_text_links_dialog_activation_falls_back_to_editing_path(self, qapp, monkeypatch, tmp_path):
        from PyQt5.QtWidgets import QInputDialog

        from ui_designer.ui.resource_generator_window import _FontTextLinksDialog

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        (source_dir / "ui_text.txt").write_text("abc", encoding="utf-8")
        monkeypatch.setattr(QInputDialog, "getText", lambda *args, **kwargs: ("renamed.txt", True))

        dialog = _FontTextLinksDialog(
            initial_items=["ui_text.txt"],
            source_dir=str(source_dir),
            parent=None,
        )
        dialog._list_widget.setCurrentRow(0)

        dialog._activate_selected_item()

        assert dialog.text_value() == "renamed.txt"
        dialog.close()

    @_skip_no_qt
    def test_font_text_links_dialog_can_edit_selected_file_via_callback(self, qapp, tmp_path):
        from ui_designer.ui.resource_generator_window import _FontTextLinksDialog

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        missing_path = source_dir / "missing.txt"
        captured = []

        def _edit_file(value):
            captured.append(value)
            missing_path.write_text("abc", encoding="utf-8")

        dialog = _FontTextLinksDialog(
            initial_items=["missing.txt"],
            source_dir=str(source_dir),
            edit_file_callback=_edit_file,
            parent=None,
        )
        dialog._list_widget.setCurrentRow(0)

        assert dialog._count_label.text() == "Linked text files: 1 | Missing: 1"
        assert dialog._edit_file_button.text() == "Create File..."
        dialog._edit_selected_file()

        assert captured == ["missing.txt"]
        assert dialog._count_label.text() == "Linked text files: 1"
        assert dialog._list_widget.item(0).text() == "missing.txt"
        assert dialog._edit_file_button.text() == "Edit File..."
        assert dialog._preview_sample_label.text() == "Preview Sample: abc\nPreview Source: missing.txt"
        assert dialog._preview_info_label.text() == "Preview: 1 line(s), 3 char(s)"
        assert dialog._preview_text_edit.toPlainText() == "abc"
        assert dialog._combined_preview_info_label.text() == "Combined Preview: 1 file(s)"
        assert dialog._combined_preview_text_edit.toPlainText() == "[missing.txt]\nabc"
        dialog.close()

    @_skip_no_qt
    def test_font_text_links_dialog_combined_preview_respects_current_order(self, qapp, tmp_path):
        from ui_designer.ui.resource_generator_window import _FontTextLinksDialog

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        (source_dir / "ui_text.txt").write_text("A\nB\n", encoding="utf-8")
        (source_dir / "charset.txt").write_text("1\n2\n", encoding="utf-8")

        dialog = _FontTextLinksDialog(
            initial_items=["ui_text.txt", "charset.txt"],
            source_dir=str(source_dir),
            parent=None,
        )

        assert dialog._preview_sample_label.text() == "Preview Sample: AB12\nPreview Source: ui_text.txt, charset.txt"
        assert dialog._combined_preview_info_label.text() == "Combined Preview: 2 file(s)"
        assert dialog._combined_preview_text_edit.toPlainText() == "[ui_text.txt]\nA\nB\n\n[charset.txt]\n1\n2"

        dialog._list_widget.setCurrentRow(1)
        moved_item = dialog._list_widget.takeItem(1)
        dialog._list_widget.insertItem(0, moved_item)
        dialog._list_widget.setCurrentRow(0)
        dialog._handle_list_order_changed()

        assert dialog.text_value() == "charset.txt\nui_text.txt"
        assert dialog._preview_sample_label.text() == "Preview Sample: 12AB\nPreview Source: charset.txt, ui_text.txt"
        assert dialog._combined_preview_text_edit.toPlainText() == "[charset.txt]\n1\n2\n\n[ui_text.txt]\nA\nB"
        dialog.close()

    @_skip_no_qt
    def test_font_text_links_dialog_shortcuts_reorder_and_remove_selected_item(self, qapp, tmp_path):
        from ui_designer.ui.resource_generator_window import _FontTextLinksDialog

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        (source_dir / "ui_text.txt").write_text("A\nB\n", encoding="utf-8")
        (source_dir / "charset.txt").write_text("1\n2\n", encoding="utf-8")

        dialog = _FontTextLinksDialog(
            initial_items=["ui_text.txt", "charset.txt", "missing.txt"],
            source_dir=str(source_dir),
            parent=None,
        )
        dialog.show()
        qapp.processEvents()

        dialog._list_widget.setCurrentRow(1)
        dialog._list_widget.setFocus()
        QTest.keyClick(dialog._list_widget, Qt.Key_Up, Qt.ControlModifier | Qt.ShiftModifier)

        assert dialog.text_value() == "charset.txt\nui_text.txt\nmissing.txt"
        assert dialog._preview_sample_label.text() == "Preview Sample: 12AB\nPreview Source: charset.txt, ui_text.txt"

        QTest.keyClick(dialog._list_widget, Qt.Key_Delete)

        assert dialog.text_value() == "ui_text.txt\nmissing.txt"
        assert dialog._count_label.text() == "Linked text files: 2 | Missing: 1"
        dialog.close()

    @_skip_no_qt
    def test_font_text_links_dialog_shortcuts_activate_and_rename_selected_item(self, qapp, monkeypatch, tmp_path):
        from PyQt5.QtWidgets import QInputDialog

        from ui_designer.ui.resource_generator_window import _FontTextLinksDialog

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        (source_dir / "ui_text.txt").write_text("abc", encoding="utf-8")
        captured = []

        def _edit_file(value):
            captured.append(value)
            return True

        monkeypatch.setattr(QInputDialog, "getText", lambda *args, **kwargs: ("renamed.txt", True))

        dialog = _FontTextLinksDialog(
            initial_items=["ui_text.txt"],
            source_dir=str(source_dir),
            edit_file_callback=_edit_file,
            parent=None,
        )
        dialog.show()
        qapp.processEvents()

        dialog._list_widget.setCurrentRow(0)
        dialog._list_widget.setFocus()
        QTest.keyClick(dialog._list_widget, Qt.Key_Return)
        QTest.keyClick(dialog._list_widget, Qt.Key_F2)

        assert captured == ["ui_text.txt"]
        assert dialog.text_value() == "renamed.txt"
        dialog.close()

    @_skip_no_qt
    def test_font_text_links_dialog_context_menu_exposes_expected_actions(self, qapp, tmp_path):
        from ui_designer.ui.resource_generator_window import _FontTextLinksDialog

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        (source_dir / "ui_text.txt").write_text("abc", encoding="utf-8")

        dialog = _FontTextLinksDialog(
            initial_items=["ui_text.txt", "missing.txt"],
            source_dir=str(source_dir),
            edit_file_callback=lambda value: True,
            parent=None,
        )
        dialog._list_widget.setCurrentRow(1)

        menu = dialog._build_list_context_menu()
        actions = [action for action in menu.actions() if not action.isSeparator()]
        action_map = {action.text(): action for action in actions}

        assert [action.text() for action in actions[:4]] == ["New File...", "Add Files...", "Paste Paths", "Add Path..."]
        assert "Create File..." in action_map
        assert action_map["Create File..."].isEnabled() is True
        assert action_map["Move Up"].isEnabled() is True
        assert action_map["Move Down"].isEnabled() is False
        assert action_map["Remove Missing"].isEnabled() is True
        dialog.close()

    @_skip_no_qt
    def test_font_text_links_dialog_can_paste_paths_from_clipboard(self, qapp, tmp_path):
        from PyQt5.QtWidgets import QApplication

        from ui_designer.ui.resource_generator_window import _FontTextLinksDialog

        source_dir = tmp_path / "resource" / "src"
        extra_dir = source_dir / "charset"
        extra_dir.mkdir(parents=True)
        (source_dir / "ui_text.txt").write_text("A\nB\n", encoding="utf-8")
        extra_file = extra_dir / "external_charset.txt"
        extra_file.write_text("1\n2\n", encoding="utf-8")

        dialog = _FontTextLinksDialog(
            initial_items=["ui_text.txt"],
            source_dir=str(source_dir),
            normalize_file_callback=lambda path: os.path.relpath(path, str(source_dir)).replace("\\", "/")
            if os.path.isabs(path)
            else path,
            parent=None,
        )
        dialog.show()
        qapp.processEvents()

        QApplication.clipboard().setText(f'ui_text.txt\n"{extra_file}"\nui_text.txt')
        dialog._list_widget.setFocus()
        QTest.keyClick(dialog._list_widget, Qt.Key_V, Qt.ControlModifier)

        assert dialog.text_value() == "ui_text.txt\ncharset/external_charset.txt"
        assert dialog._preview_sample_label.text() == "Preview Sample: AB12\nPreview Source: ui_text.txt, charset/external_charset.txt"
        assert dialog._combined_preview_text_edit.toPlainText() == "[ui_text.txt]\nA\nB\n\n[charset/external_charset.txt]\n1\n2"
        dialog.close()

    @_skip_no_qt
    def test_font_text_links_dialog_context_menu_selects_clicked_item(self, qapp, monkeypatch, tmp_path):
        from PyQt5.QtWidgets import QMenu

        from ui_designer.ui.resource_generator_window import _FontTextLinksDialog

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        (source_dir / "ui_text.txt").write_text("abc", encoding="utf-8")

        captured = []
        monkeypatch.setattr(QMenu, "exec_", lambda self, *args, **kwargs: captured.append([action.text() for action in self.actions()]))

        dialog = _FontTextLinksDialog(
            initial_items=["ui_text.txt", "missing.txt"],
            source_dir=str(source_dir),
            edit_file_callback=lambda value: True,
            parent=None,
        )
        dialog._list_widget.setCurrentRow(0)

        target_item = dialog._list_widget.item(1)
        dialog._open_list_context_menu(dialog._list_widget.visualItemRect(target_item).center())

        assert dialog._selected_row() == 1
        assert any("Create File..." in items for items in captured)
        dialog.close()

    @_skip_no_qt
    def test_font_text_links_dialog_can_copy_full_path_and_open_folder(self, qapp, monkeypatch, tmp_path):
        from PyQt5.QtWidgets import QApplication

        from ui_designer.ui.resource_generator_window import QDesktopServices, _FontTextLinksDialog
        from ui_designer.model.workspace import normalize_path

        source_dir = tmp_path / "resource" / "src"
        text_dir = source_dir / "charset"
        text_dir.mkdir(parents=True)
        text_path = text_dir / "basic.txt"
        text_path.write_text("abc", encoding="utf-8")
        opened = []

        monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened.append(url.toLocalFile()) or True)

        dialog = _FontTextLinksDialog(initial_items=["charset/basic.txt"], source_dir=str(source_dir), parent=None)
        dialog._list_widget.setCurrentRow(0)

        QApplication.clipboard().clear()
        dialog._copy_selected_path()
        dialog._open_selected_folder()

        assert QApplication.clipboard().text() == str(text_path)
        assert [normalize_path(path) for path in opened] == [normalize_path(str(text_dir))]
        dialog.close()

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
    def test_simple_mode_selection_uses_english_builtin_font_preview_sample_when_text_is_missing(self, qapp, monkeypatch, tmp_path):
        from PyQt5.QtGui import QPixmap

        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        font_path = source_dir / "display.ttf"
        font_path.write_bytes(b"ttf")

        captured = {}

        def _fake_render(self, font_file, sample_text, entry=None):
            captured["font_file"] = font_file
            captured["sample_text"] = sample_text
            pixmap = QPixmap(96, 36)
            pixmap.fill()
            return pixmap

        monkeypatch.setattr(ResourceGeneratorWindow, "_build_font_preview_pixmap", _fake_render)

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {"img": [], "font": [{"file": "display.ttf", "name": "display", "text": ""}], "mp4": []},
            dirty=False,
        )

        window._simple_asset_table.selectRow(0)
        qapp.processEvents()

        assert captured["font_file"] == str(font_path.resolve())
        assert captured["sample_text"] == "HELLO Designer 1234"
        assert "Preview Text: HELLO Designer 1234" in window._simple_asset_meta.toPlainText()
        assert "Preview Source: built-in sample" in window._simple_asset_meta.toPlainText()
        _close_window(window)

    @_skip_no_qt
    def test_simple_mode_selection_combines_multiple_font_text_files_for_preview(self, qapp, monkeypatch, tmp_path):
        from PyQt5.QtGui import QPixmap

        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        font_path = source_dir / "display.ttf"
        font_path.write_bytes(b"ttf")
        (source_dir / "ui_text.txt").write_text("A\nB\n", encoding="utf-8")
        (source_dir / "charset.txt").write_text("1\n2\n", encoding="utf-8")

        captured = {}

        def _fake_render(self, font_file, sample_text, entry=None):
            captured["font_file"] = font_file
            captured["sample_text"] = sample_text
            pixmap = QPixmap(96, 36)
            pixmap.fill()
            return pixmap

        monkeypatch.setattr(ResourceGeneratorWindow, "_build_font_preview_pixmap", _fake_render)

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {"img": [], "font": [{"file": "display.ttf", "name": "display", "text": "ui_text.txt,charset.txt"}], "mp4": []},
            dirty=False,
        )

        window._simple_asset_table.selectRow(0)
        qapp.processEvents()

        assert captured["font_file"] == str(font_path.resolve())
        assert captured["sample_text"] == "AB12"
        assert "Preview Text: AB12" in window._simple_asset_meta.toPlainText()
        assert "Preview Source: ui_text.txt, charset.txt" in window._simple_asset_meta.toPlainText()
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
    def test_generate_thumbnails_helper_rejects_designer_managed_output_folder(self, qapp, monkeypatch, tmp_path):
        from PyQt5.QtGui import QPixmap
        from PyQt5.QtWidgets import QDialog, QMessageBox

        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        hero_path = source_dir / "hero.png"
        hero = QPixmap(12, 8)
        assert hero.save(str(hero_path), "PNG")
        warnings = []
        generated_calls = []

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
                return ".designer"

            def filename_suffix(self):
                return "_thumb"

        monkeypatch.setattr("ui_designer.ui.resource_generator_window._QuickThumbnailBatchDialog", _FakeDialog)
        monkeypatch.setattr(
            "ui_designer.ui.resource_generator_window.ResourceGeneratorWindow._generate_thumbnail_images_for_quick_mode",
            lambda *args, **kwargs: generated_calls.append((args, kwargs)),
        )
        monkeypatch.setattr(
            QMessageBox,
            "warning",
            lambda *args: warnings.append((args[1], args[2])) or QMessageBox.Ok,
        )

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {"img": [{"file": "hero.png", "name": "hero"}], "font": [], "mp4": []},
            dirty=False,
        )

        window._open_generate_thumbnails_helper()

        assert warnings == [
            (
                "Generate Thumbnails",
                "'.designer' is reserved for Designer-generated files.\nChoose a different folder.",
            )
        ]
        assert generated_calls == []
        assert not (source_dir / ".designer" / "hero_thumb.png").exists()
        assert window.has_unsaved_changes() is False
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
    def test_generate_placeholders_helper_rejects_designer_managed_existing_target_path_without_partial_writes(
        self, qapp, monkeypatch, tmp_path
    ):
        from PyQt5.QtWidgets import QMessageBox

        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        warnings = []

        monkeypatch.setattr(
            QMessageBox,
            "warning",
            lambda *args: warnings.append((args[1], args[2])) or QMessageBox.Ok,
        )

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {
                "img": [
                    {"file": "hero.png", "name": "Hero Banner"},
                    {"file": ".designer/logo.png", "name": "Logo"},
                ],
                "font": [],
                "mp4": [],
            },
            dirty=False,
        )

        window._generate_placeholder_images_for_quick_mode(width=64, height=48, output_folder="placeholders")

        assert warnings == [
            (
                "Generate Placeholders",
                "'.designer/logo.png' is reserved for Designer-generated files.\nChoose a different filename.",
            )
        ]
        assert not (source_dir / "hero.png").exists()
        assert not (source_dir / ".designer" / "logo.png").exists()
        assert [entry["file"] for entry in window._session.section_entries("img")] == ["hero.png", ".designer/logo.png"]
        assert window.has_unsaved_changes() is False
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
    def test_resize_image_helper_rejects_designer_managed_output_path(self, qapp, monkeypatch, tmp_path):
        from PyQt5.QtGui import QPixmap
        from PyQt5.QtWidgets import QDialog

        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        image_path = source_dir / "hero.png"
        pixmap = QPixmap(12, 8)
        assert pixmap.save(str(image_path), "PNG")
        warnings = []

        class _FakeDialog:
            def __init__(self, *, width, height, output_filename, parent=None):
                assert width == 12
                assert height == 8
                assert output_filename == "hero.png"

            def exec_(self):
                return QDialog.Accepted

            def output_filename(self):
                return ".designer/hero_small.png"

            def width_value(self):
                return 5

            def height_value(self):
                return 3

        monkeypatch.setattr("ui_designer.ui.resource_generator_window._QuickImageResizeDialog", _FakeDialog)
        monkeypatch.setattr(
            QMessageBox,
            "warning",
            lambda *args: warnings.append((args[1], args[2])) or QMessageBox.Ok,
        )

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {"img": [{"file": "hero.png", "name": "hero"}], "font": [], "mp4": []},
            dirty=False,
        )
        window._simple_asset_table.selectRow(0)
        qapp.processEvents()

        window._open_resize_image_helper()

        assert warnings == [
            (
                "Resize Image",
                "'.designer/hero_small.png' is reserved for Designer-generated files.\nChoose a different filename.",
            )
        ]
        assert not (source_dir / ".designer" / "hero_small.png").exists()
        assert [entry["file"] for entry in window._session.section_entries("img")] == ["hero.png"]
        assert window.has_unsaved_changes() is False
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
    def test_normalize_selected_font_text_rejects_designer_reserved_filename(self, qapp, monkeypatch, tmp_path):
        from ui_designer.model.resource_generation_session import RESOURCE_SECTION_SPECS
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        reserved_file = tmp_path / "imports" / "_generated_text_demo_16_4.txt"
        reserved_file.parent.mkdir(parents=True)
        reserved_file.write_text("demo\n", encoding="utf-8")

        warnings = []
        monkeypatch.setattr(
            QMessageBox,
            "warning",
            lambda *args: warnings.append((args[1], args[2])) or QMessageBox.Ok,
        )

        text_field = next(field for field in RESOURCE_SECTION_SPECS["font"].fields if field.name == "text")

        window = ResourceGeneratorWindow("")
        window._session.paths.source_dir = str(source_dir)

        result = window._normalize_selected_resource_path(text_field, str(reserved_file))

        assert result is None
        assert warnings == [
            (
                "Choose Text",
                "'_generated_text_demo_16_4.txt' is reserved for Designer-generated files.\nChoose a different filename.",
            )
        ]
        assert not (source_dir / "_generated_text_demo_16_4.txt").exists()
        _close_window(window)

    @_skip_no_qt
    def test_normalize_selected_resource_path_rejects_designer_directory_file(self, qapp, monkeypatch, tmp_path):
        from ui_designer.model.resource_generation_session import RESOURCE_SECTION_SPECS
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        designer_file = source_dir / ".designer" / "scratch.txt"
        designer_file.parent.mkdir(parents=True)
        designer_file.write_text("designer-only\n", encoding="utf-8")

        warnings = []
        monkeypatch.setattr(
            QMessageBox,
            "warning",
            lambda *args: warnings.append((args[1], args[2])) or QMessageBox.Ok,
        )

        window = ResourceGeneratorWindow("")
        window._session.paths.source_dir = str(source_dir)

        result = window._normalize_selected_resource_path(RESOURCE_SECTION_SPECS["img"].fields[0], str(designer_file))

        assert result is None
        assert warnings == [
            (
                "Choose File",
                "'.designer/scratch.txt' is reserved for Designer-generated files.\nChoose a different filename.",
            )
        ]
        _close_window(window)

    @_skip_no_qt
    def test_normalize_selected_resource_path_rejects_external_designer_directory_file(self, qapp, monkeypatch, tmp_path):
        from ui_designer.model.resource_generation_session import RESOURCE_SECTION_SPECS
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        designer_file = tmp_path / "imports" / ".designer" / "scratch.txt"
        designer_file.parent.mkdir(parents=True)
        designer_file.write_text("designer-only\n", encoding="utf-8")

        warnings = []
        monkeypatch.setattr(
            QMessageBox,
            "warning",
            lambda *args: warnings.append((args[1], args[2])) or QMessageBox.Ok,
        )

        window = ResourceGeneratorWindow("")
        window._session.paths.source_dir = str(source_dir)

        result = window._normalize_selected_resource_path(RESOURCE_SECTION_SPECS["img"].fields[0], str(designer_file))

        assert result is None
        assert warnings == [
            (
                "Choose File",
                "'.designer/scratch.txt' is reserved for Designer-generated files.\nChoose a different filename.",
            )
        ]
        assert not (source_dir / "scratch.txt").exists()
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
    def test_classify_selected_asset_files_ignores_designer_reserved_files(self, qapp, tmp_path):
        from ui_designer.ui.resource_generator_window import _classify_selected_asset_files

        asset_dir = tmp_path / "assets"
        asset_dir.mkdir(parents=True)
        normal_font = asset_dir / "display.ttf"
        reserved_text = asset_dir / "_generated_text_display_16_4.txt"
        normal_font.write_bytes(b"font")
        reserved_text.write_text("demo\n", encoding="utf-8")

        discovered_assets, discovered_texts, skipped_paths = _classify_selected_asset_files(
            [str(normal_font), str(reserved_text)]
        )

        assert discovered_assets == [("font", str(normal_font.resolve()))]
        assert discovered_texts == []
        assert skipped_paths == [str(reserved_text.resolve())]

    @_skip_no_qt
    def test_classify_selected_asset_files_ignores_designer_directory_files(self, qapp, tmp_path):
        from ui_designer.ui.resource_generator_window import _classify_selected_asset_files

        asset_dir = tmp_path / "assets"
        designer_file = asset_dir / ".designer" / "scratch.txt"
        designer_file.parent.mkdir(parents=True)
        designer_file.write_text("designer-only\n", encoding="utf-8")

        discovered_assets, discovered_texts, skipped_paths = _classify_selected_asset_files(
            [str(designer_file)]
        )

        assert discovered_assets == []
        assert discovered_texts == []
        assert skipped_paths == [str(designer_file.resolve())]

    @_skip_no_qt
    def test_discover_supported_assets_ignores_designer_reserved_files(self, qapp, tmp_path):
        from ui_designer.ui.resource_generator_window import _discover_supported_assets

        asset_dir = tmp_path / "assets"
        designer_dir = asset_dir / ".designer"
        asset_dir.mkdir(parents=True)
        designer_dir.mkdir(parents=True)
        (asset_dir / "display.ttf").write_bytes(b"font")
        (designer_dir / "_generated_text_display_16_4.txt").write_text("demo\n", encoding="utf-8")
        (asset_dir / "labels.txt").write_text("hello\n", encoding="utf-8")

        discovered_assets, discovered_texts = _discover_supported_assets(str(asset_dir))

        assert discovered_assets == [("font", str((asset_dir / "display.ttf").resolve()))]
        assert discovered_texts == [str((asset_dir / "labels.txt").resolve())]

    @_skip_no_qt
    def test_discover_supported_assets_skips_designer_directory_contents(self, qapp, tmp_path):
        from ui_designer.ui.resource_generator_window import _discover_supported_assets

        asset_dir = tmp_path / "assets"
        designer_dir = asset_dir / ".designer"
        asset_dir.mkdir(parents=True)
        designer_dir.mkdir(parents=True)
        (asset_dir / "display.ttf").write_bytes(b"font")
        (designer_dir / "scratch.txt").write_text("designer-only\n", encoding="utf-8")

        discovered_assets, discovered_texts = _discover_supported_assets(str(asset_dir))

        assert discovered_assets == [("font", str((asset_dir / "display.ttf").resolve()))]
        assert discovered_texts == []

    @_skip_no_qt
    def test_discover_supported_assets_skips_designer_root_directory(self, qapp, tmp_path):
        from ui_designer.ui.resource_generator_window import _discover_supported_assets

        designer_dir = tmp_path / "assets" / ".designer"
        designer_dir.mkdir(parents=True)
        (designer_dir / "scratch.txt").write_text("designer-only\n", encoding="utf-8")

        discovered_assets, discovered_texts = _discover_supported_assets(str(designer_dir))

        assert discovered_assets == []
        assert discovered_texts == []

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
            "getOpenFileNames",
            lambda *args, **kwargs: ([str(text_file)], text_field.file_filter),
        )

        window._browse_entry_field(text_field)

        entry = window._session.section_entries("font")[0]
        assert entry["text"] == "charset/basic.txt"
        assert window.has_unsaved_changes() is False
        _close_window(window)

    @_skip_no_qt
    def test_browse_font_text_multiple_files_appends_and_normalizes(self, qapp, monkeypatch, tmp_path):
        from PyQt5.QtWidgets import QFileDialog, QMessageBox

        from ui_designer.model.resource_generation_session import GenerationPaths, RESOURCE_SECTION_SPECS
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        first_text = source_dir / "charset" / "basic.txt"
        second_text = source_dir / "charset" / "extra.txt"
        first_text.parent.mkdir(parents=True)
        first_text.write_text("abc", encoding="utf-8")
        second_text.write_text("xyz", encoding="utf-8")

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
            "getOpenFileNames",
            lambda *args, **kwargs: ([str(second_text), str(first_text)], text_field.file_filter),
        )
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)

        window._browse_entry_field(text_field)

        entry = window._session.section_entries("font")[0]
        assert entry["text"] == "charset/basic.txt,charset/extra.txt"
        assert window.has_unsaved_changes() is True
        _close_window(window)

    @_skip_no_qt
    def test_commit_font_text_field_normalizes_value_without_dirty_when_effective_text_is_unchanged(self, qapp, tmp_path):
        from PyQt5.QtWidgets import QLineEdit

        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)

        window = ResourceGeneratorWindow("")
        window._apply_paths_and_data(
            GenerationPaths(source_dir=str(source_dir)),
            {"img": [], "font": [{"file": "display.ttf", "text": "charset/basic.txt,charset/extra.txt"}], "mp4": []},
            dirty=False,
        )
        window._active_section = "font"
        window._active_entry_index = 0
        window._refresh_entry_table()

        edit = window._active_field_widgets["text"]
        assert isinstance(edit, QLineEdit)
        assert edit.parentWidget().layout().spacing() == 4
        edit.setText(" charset/basic.txt ;\r\n charset/extra.txt ")

        window._commit_font_text_field("text", edit)

        entry = window._session.section_entries("font")[0]
        assert entry["text"] == "charset/basic.txt,charset/extra.txt"
        assert edit.text() == "charset/basic.txt,charset/extra.txt"
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
    def test_generate_charset_helper_rejects_designer_managed_output_path(self, qapp, monkeypatch, tmp_path):
        from PyQt5.QtWidgets import QDialog

        from ui_designer.model.resource_generation_session import GenerationPaths
        from ui_designer.ui.resource_generator_window import ResourceGeneratorWindow

        source_dir = tmp_path / "resource" / "src"
        source_dir.mkdir(parents=True)
        warnings = []

        class _FakeDialog:
            def __init__(self, resource_dir, initial_filename="", source_label="", initial_preset_ids=(), parent=None):
                pass

            def exec_(self):
                return QDialog.Accepted

            def filename(self):
                return ".designer/display_charset.txt"

            def generated_text(self):
                return "A\nB\n"

            def overwrite_diff(self):
                return SimpleNamespace(existing_count=0, new_count=2, added_count=2, removed_count=0)

        monkeypatch.setattr("ui_designer.ui.resource_generator_window._GenerateCharsetDialog", _FakeDialog)
        monkeypatch.setattr(
            QMessageBox,
            "warning",
            lambda *args: warnings.append((args[1], args[2])) or QMessageBox.Ok,
        )

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

        assert warnings == [
            (
                "Generate Font Text",
                "'.designer/display_charset.txt' is reserved for Designer-generated files.\nChoose a different filename.",
            )
        ]
        assert not (source_dir / ".designer" / "display_charset.txt").exists()
        assert window._session.section_entries("font")[0]["text"] == ""
        assert window.has_unsaved_changes() is False
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
