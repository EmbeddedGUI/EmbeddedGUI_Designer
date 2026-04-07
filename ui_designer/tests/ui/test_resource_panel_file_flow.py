"""Qt UI tests for ResourcePanel import dialog defaults."""

import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtCore import QTimer, Qt
    from PyQt5.QtWidgets import QApplication, QFrame, QLabel, QMessageBox

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


@_skip_no_qt
class TestResourcePanelFileFlow:
    def test_preview_widget_font_sizes_follow_designer_font_preference(self, qapp):
        from ui_designer.ui.resource_panel import _PreviewWidget

        qapp.setProperty("designer_font_size_pt", 12)
        preview = _PreviewWidget()

        try:
            assert preview._image_meta_font_point_size() == 12
            assert preview._meta_font_point_size() == 11
            assert preview._text_preview_font_point_size() == 12
        finally:
            preview.deleteLater()
            qapp.setProperty("designer_font_size_pt", 0)

    def test_header_exposes_workspace_and_metric_metadata(self, qapp, tmp_path):
        from ui_designer.model.resource_catalog import ResourceCatalog
        from ui_designer.ui.resource_panel import ResourcePanel

        resource_dir = tmp_path / "project" / ".eguiproject" / "resources"
        images_dir = resource_dir / "images"
        images_dir.mkdir(parents=True)
        (images_dir / "present.png").write_bytes(b"PNG")

        catalog = ResourceCatalog()
        catalog.add_image("present.png")
        catalog.add_image("missing.png")
        catalog.add_font("demo.ttf")

        panel = ResourcePanel()
        panel.set_resource_dir(str(resource_dir))
        panel.set_resource_catalog(catalog)

        header = panel.findChild(QFrame, "resource_panel_header")
        header_margins = header.layout().contentsMargins()
        eyebrow = header.findChild(QLabel, "resource_panel_eyebrow")
        title = header.findChild(QLabel, "resource_panel_title")
        subtitle = header.findChild(QLabel, "resource_panel_subtitle")
        status = header.findChild(QLabel, "resource_panel_status")
        top_card = panel.findChild(QFrame, "resource_panel_card")
        metrics_layout = panel._panel_metrics_frame.layout()
        metric_margins = panel._catalog_metric_value._resource_panel_metric_card.layout().contentsMargins()

        assert panel.accessibleName() == (
            "Resource panel: Workspace configured. Active tab: Images. "
            "Catalog: 3 assets. Missing: 2 missing files. Selection: Images: none."
        )
        assert panel.layout().spacing() == 4
        assert (header_margins.left(), header_margins.top(), header_margins.right(), header_margins.bottom()) == (4, 4, 4, 4)
        assert header.layout().spacing() == 4
        assert top_card.layout().spacing() == 2
        assert panel._tabs.widget(0).layout().spacing() == 2
        assert panel._tabs.widget(1).layout().spacing() == 2
        assert panel._tabs.widget(2).layout().spacing() == 2
        assert panel._tabs.widget(3).layout().spacing() == 2
        assert metrics_layout.spacing() == 2
        assert (
            metric_margins.left(),
            metric_margins.top(),
            metric_margins.right(),
            metric_margins.bottom(),
        ) == (6, 4, 6, 4)
        preview_layout = panel._details_tabs.widget(0).layout()
        usage_layout = panel._details_tabs.widget(1).layout()
        usage_filter_layout = usage_layout.itemAt(1).layout()
        assert preview_layout.spacing() == 2
        assert usage_layout.spacing() == 2
        assert (preview_layout.contentsMargins().left(), preview_layout.contentsMargins().top(), preview_layout.contentsMargins().right(), preview_layout.contentsMargins().bottom()) == (2, 2, 2, 2)
        assert (usage_layout.contentsMargins().left(), usage_layout.contentsMargins().top(), usage_layout.contentsMargins().right(), usage_layout.contentsMargins().bottom()) == (2, 2, 2, 2)
        assert usage_filter_layout.spacing() == 2
        assert title.text() == "Resources"
        assert header.accessibleName() == "Resource header: Project Resources. Workspace configured. Active tab: Images."
        assert eyebrow.accessibleName() == "Resource pipeline workspace."
        assert eyebrow.isHidden() is True
        assert title.accessibleName() == "Resource panel title: Project Resources."
        assert subtitle.accessibleName() == subtitle.text()
        assert subtitle.isHidden() is True
        assert status.accessibleName() == "Resource workspace state: configured. Active tab: Images"
        assert status.isHidden() is True
        assert panel._panel_metrics_frame.isHidden() is True
        assert panel._catalog_hint.isHidden() is True
        assert panel._preview_hint.isHidden() is True
        assert panel._usage_hint.isHidden() is True
        assert panel._catalog_metric_value.accessibleName() == "Resource panel metric: Catalog. 3 assets."
        assert panel._catalog_metric_value.toolTip() == "Catalog: 3 assets."
        assert panel._catalog_metric_value._resource_panel_metric_label.accessibleName() == "Catalog metric label."
        assert panel._catalog_metric_value._resource_panel_metric_card.accessibleName() == "Catalog metric: 3 assets."
        assert panel._catalog_metric_value._resource_panel_metric_card.isHidden() is True
        assert panel._missing_metric_value.accessibleName() == "Resource panel metric: Missing. 2 missing files."
        assert panel._missing_metric_value._resource_panel_metric_card.isHidden() is True
        assert panel._selection_metric_value.accessibleName() == "Resource panel metric: Selection. Images: none."
        assert panel._selection_metric_value._resource_panel_metric_card.isHidden() is True
        assert len(header.findChildren(QFrame, "resource_panel_metric_card")) == 3
        panel.deleteLater()

    def test_more_button_hint_skips_no_op_rewrites(self, qapp, monkeypatch):
        from ui_designer.ui.resource_panel import ResourcePanel

        panel = ResourcePanel()
        button = panel._resource_more_menus["image"]["button"]
        source_buttons = panel._resource_action_buttons["image"]
        for key in ("restore", "replace", "next_missing"):
            source_buttons[key].setEnabled(False)
        button.setProperty("_resource_panel_hint_snapshot", None)

        hint_calls = 0
        original_set_tooltip = button.setToolTip

        def counted_set_tooltip(text):
            nonlocal hint_calls
            hint_calls += 1
            return original_set_tooltip(text)

        monkeypatch.setattr(button, "setToolTip", counted_set_tooltip)

        panel._sync_resource_more_menu("image")
        assert hint_calls == 1
        assert button.toolTip() == "Save or open a project first to manage image resources."

        panel._sync_resource_more_menu("image")
        assert hint_calls == 1

        source_buttons["restore"].setEnabled(True)
        panel._sync_resource_more_menu("image")
        assert hint_calls == 2
        assert button.toolTip() == "Open more image actions."
        panel.deleteLater()

    def test_more_button_accessible_name_skips_no_op_rewrites(self, qapp, monkeypatch):
        from ui_designer.ui.resource_panel import ResourcePanel

        panel = ResourcePanel()
        button = panel._resource_more_menus["image"]["button"]
        source_buttons = panel._resource_action_buttons["image"]
        for key in ("restore", "replace", "next_missing"):
            source_buttons[key].setEnabled(False)
        button.setProperty("_resource_panel_accessible_snapshot", None)

        accessible_calls = 0
        original_set_accessible_name = button.setAccessibleName

        def counted_set_accessible_name(text):
            nonlocal accessible_calls
            accessible_calls += 1
            return original_set_accessible_name(text)

        monkeypatch.setattr(button, "setAccessibleName", counted_set_accessible_name)

        panel._sync_resource_more_menu("image")
        assert accessible_calls == 1
        assert button.accessibleName() == "More image actions unavailable"

        panel._sync_resource_more_menu("image")
        assert accessible_calls == 1

        source_buttons["restore"].setEnabled(True)
        panel._sync_resource_more_menu("image")
        assert accessible_calls == 2
        assert button.accessibleName() == "More image actions"
        panel.deleteLater()

    def test_resource_more_menu_uses_compact_visible_labels(self, qapp):
        from ui_designer.ui.resource_panel import ResourcePanel

        panel = ResourcePanel()
        actions = panel._resource_more_menus["image"]["actions"]

        assert actions["restore"].text() == "Restore"
        assert actions["replace"].text() == "Replace"
        assert actions["next_missing"].text() == "Next"
        panel.deleteLater()

    def test_more_menu_action_hint_skips_no_op_rewrites(self, qapp, monkeypatch):
        from ui_designer.ui.resource_panel import ResourcePanel

        panel = ResourcePanel()
        action = panel._resource_more_menus["image"]["actions"]["restore"]
        source_button = panel._resource_action_buttons["image"]["restore"]
        action.setProperty("_resource_panel_hint_snapshot", None)

        hint_calls = 0
        original_set_tooltip = action.setToolTip

        def counted_set_tooltip(text):
            nonlocal hint_calls
            hint_calls += 1
            return original_set_tooltip(text)

        monkeypatch.setattr(action, "setToolTip", counted_set_tooltip)

        panel._sync_resource_more_menu("image")
        assert hint_calls == 1

        panel._sync_resource_more_menu("image")
        assert hint_calls == 1

        source_button.setToolTip("Restore missing image resources. 1 missing image resource.")
        source_button.setStatusTip(source_button.toolTip())
        panel._sync_resource_more_menu("image")
        assert hint_calls == 2
        assert action.toolTip() == "Restore missing image resources. 1 missing image resource."
        panel.deleteLater()

    def test_import_image_warns_before_opening_dialog_when_resource_dir_missing(self, qapp, monkeypatch):
        from ui_designer.ui.resource_panel import ResourcePanel

        panel = ResourcePanel()
        warnings = []
        dialog_calls = []

        monkeypatch.setattr("ui_designer.ui.resource_panel.QMessageBox.warning", lambda *args: warnings.append(args[1:]))
        monkeypatch.setattr(
            "ui_designer.ui.resource_panel.QFileDialog.getOpenFileNames",
            lambda *args, **kwargs: dialog_calls.append(args) or ([], ""),
        )

        panel._on_import_image()

        assert warnings
        assert warnings[0][0] == "Error"
        assert "No resource directory configured" in warnings[0][1]
        assert dialog_calls == []
        panel.deleteLater()

    def test_import_image_dialog_uses_project_images_dir_by_default(self, qapp, tmp_path, monkeypatch):
        from ui_designer.ui.resource_panel import ResourcePanel

        resource_dir = tmp_path / "project" / ".eguiproject" / "resources"
        images_dir = resource_dir / "images"
        images_dir.mkdir(parents=True)
        captured = {}

        panel = ResourcePanel()
        panel.set_resource_dir(str(resource_dir))

        def fake_get_open_file_names(parent, title, directory, filters):
            captured["title"] = title
            captured["directory"] = directory
            captured["filters"] = filters
            return [], ""

        monkeypatch.setattr("ui_designer.ui.resource_panel.QFileDialog.getOpenFileNames", fake_get_open_file_names)

        panel._on_import_image()

        assert captured["title"] == "Import Images"
        assert captured["directory"] == os.path.normpath(os.path.abspath(images_dir))
        assert "Images" in captured["filters"]
        panel.deleteLater()

    def test_import_font_dialog_prefers_last_external_import_directory(self, qapp, tmp_path, monkeypatch):
        from ui_designer.ui.resource_panel import ResourcePanel

        resource_dir = tmp_path / "project" / ".eguiproject" / "resources"
        resource_dir.mkdir(parents=True)
        external_dir = tmp_path / "external_fonts"
        external_dir.mkdir()
        font_path = external_dir / "demo.ttf"
        font_path.write_bytes(b"FONT")
        captured = {}

        panel = ResourcePanel()
        panel.set_resource_dir(str(resource_dir))
        monkeypatch.setattr("ui_designer.ui.resource_panel.QInputDialog.getText", lambda *args, **kwargs: ("demo.ttf", True))

        def fake_get_open_file_names_first(parent, title, directory, filters):
            captured["first_directory"] = directory
            return [str(font_path)], ""

        def fake_get_open_file_names_second(parent, title, directory, filters):
            captured["second_directory"] = directory
            return [], ""

        monkeypatch.setattr("ui_designer.ui.resource_panel.QFileDialog.getOpenFileNames", fake_get_open_file_names_first)
        panel._on_import_font()

        monkeypatch.setattr("ui_designer.ui.resource_panel.QFileDialog.getOpenFileNames", fake_get_open_file_names_second)
        panel._on_import_font()

        assert captured["first_directory"] == os.path.normpath(os.path.abspath(resource_dir))
        assert captured["second_directory"] == os.path.normpath(os.path.abspath(external_dir))
        panel.deleteLater()

    def test_set_resource_dir_populates_text_tab_and_emits_selection(self, qapp, tmp_path):
        from ui_designer.model.resource_catalog import ResourceCatalog
        from ui_designer.ui.resource_panel import ResourcePanel

        resource_dir = tmp_path / "project" / ".eguiproject" / "resources"
        resource_dir.mkdir(parents=True)
        text_path = resource_dir / "supported_text.txt"
        text_path.write_text("Hello\nWorld\n", encoding="utf-8")

        catalog = ResourceCatalog()
        catalog.add_text_file("supported_text.txt")

        panel = ResourcePanel()
        panel.set_resource_dir(str(resource_dir))
        panel.set_resource_catalog(catalog)

        captured = []
        panel.resource_selected.connect(lambda res_type, filename: captured.append((res_type, filename)))

        assert panel._text_list.count() == 1
        assert panel._tabs.tabText(2) == "Text (1)"

        item = panel._text_list.item(0)
        assert item.toolTip() == "supported_text.txt"
        assert item.statusTip() == item.toolTip()
        assert item.data(Qt.AccessibleTextRole) == item.toolTip()
        panel._on_text_clicked(item)

        assert captured == [("text", "supported_text.txt")]
        panel.deleteLater()

    def test_set_resource_catalog_preserves_entries_before_resource_dir_is_configured(self, qapp):
        from ui_designer.model.resource_catalog import ResourceCatalog
        from ui_designer.ui.resource_panel import ResourcePanel

        catalog = ResourceCatalog()
        catalog.add_image("star.png")

        panel = ResourcePanel()
        panel.set_resource_catalog(catalog)

        assert panel.get_resource_catalog().images == ["star.png"]
        panel.deleteLater()

    def test_resource_action_buttons_expose_unavailable_accessibility_metadata_without_resource_dir(self, qapp):
        from ui_designer.ui.resource_panel import ResourcePanel

        panel = ResourcePanel()
        buttons = panel._resource_action_buttons["text"]

        assert buttons["import"].text() == "Import..."
        assert buttons["import"].toolTip() == "Save or open a project first to import text resources."
        assert buttons["import"].statusTip() == buttons["import"].toolTip()
        assert buttons["import"].accessibleName() == "Import text resources unavailable"
        assert buttons["restore"].toolTip() == "Save or open a project first to restore missing text resources."
        assert buttons["restore"].statusTip() == buttons["restore"].toolTip()
        assert buttons["restore"].accessibleName() == "Restore missing text resources unavailable"
        assert buttons["replace"].toolTip() == "Save or open a project first to replace missing text resources."
        assert buttons["replace"].statusTip() == buttons["replace"].toolTip()
        assert buttons["replace"].accessibleName() == "Replace missing text resources unavailable"
        assert buttons["next_missing"].toolTip() == "Save or open a project first to navigate missing text resources."
        assert buttons["next_missing"].statusTip() == buttons["next_missing"].toolTip()
        assert buttons["next_missing"].accessibleName() == "Next missing text resource unavailable"
        assert panel._generate_charset_btn.toolTip() == "Save or open a project first to generate font charset resources."
        assert panel._generate_charset_text_btn.toolTip() == panel._generate_charset_btn.toolTip()
        assert panel._generate_charset_text_btn.accessibleName() == "Generate font charset resource unavailable"
        panel.deleteLater()

    def test_text_tab_exposes_generate_charset_entry_alongside_import(self, qapp):
        from ui_designer.ui.resource_panel import ResourcePanel

        panel = ResourcePanel()

        assert panel._generate_charset_text_btn.text() == "Generate Charset..."
        assert panel._generate_charset_text_btn.toolTip() == panel._generate_charset_btn.toolTip()
        panel.deleteLater()

    def test_text_resource_context_menu_can_open_generate_charset_for_selected_file(self, qapp, tmp_path, monkeypatch):
        from ui_designer.model.resource_catalog import ResourceCatalog
        from ui_designer.ui.resource_panel import ResourcePanel

        resource_dir = tmp_path / "project" / ".eguiproject" / "resources"
        resource_dir.mkdir(parents=True)
        text_path = resource_dir / "charset_existing.txt"
        text_path.write_text("A\n", encoding="utf-8")

        catalog = ResourceCatalog()
        catalog.add_text_file("charset_existing.txt")

        panel = ResourcePanel()
        panel.set_resource_dir(str(resource_dir))
        panel.set_resource_catalog(catalog)
        panel.resize(480, 320)
        panel.show()
        qapp.processEvents()

        item = panel._text_list.item(0)
        pos = panel._text_list.visualItemRect(item).center()
        captured = {}

        monkeypatch.setattr(panel, "_open_generate_charset_dialog", lambda initial_filename="": captured.setdefault("filename", initial_filename))

        def fake_exec(menu, *args, **kwargs):
            actions = [action.text() for action in menu.actions() if not action.isSeparator()]
            captured["actions"] = actions
            for action in menu.actions():
                if action.text() == "Generate Charset...":
                    action.trigger()
                    break
            return None

        monkeypatch.setattr("ui_designer.ui.resource_panel.QMenu.exec_", fake_exec)

        panel._show_context_menu(pos, "text")

        assert "Generate Charset..." in captured["actions"]
        assert captured["filename"] == "charset_existing.txt"
        panel.deleteLater()

    def test_font_resource_context_menu_can_open_generate_charset_with_suggested_filename(self, qapp, tmp_path, monkeypatch):
        from ui_designer.model.resource_catalog import ResourceCatalog
        from ui_designer.ui.resource_panel import ResourcePanel

        resource_dir = tmp_path / "project" / ".eguiproject" / "resources"
        resource_dir.mkdir(parents=True)
        font_path = resource_dir / "demo_font.ttf"
        font_path.write_bytes(b"FONT")

        catalog = ResourceCatalog()
        catalog.add_font("demo_font.ttf")

        panel = ResourcePanel()
        panel.set_resource_dir(str(resource_dir))
        panel.set_resource_catalog(catalog)
        panel.resize(480, 320)
        panel.show()
        qapp.processEvents()

        item = panel._font_list.item(0)
        pos = panel._font_list.visualItemRect(item).center()
        captured = {}

        monkeypatch.setattr(panel, "_open_generate_charset_dialog", lambda initial_filename="": captured.setdefault("filename", initial_filename))

        def fake_exec(menu, *args, **kwargs):
            actions = [action.text() for action in menu.actions() if not action.isSeparator()]
            captured["actions"] = actions
            for action in menu.actions():
                if action.text() == "Generate Charset...":
                    action.trigger()
                    break
            return None

        monkeypatch.setattr("ui_designer.ui.resource_panel.QMenu.exec_", fake_exec)

        panel._show_context_menu(pos, "font")

        assert "Generate Charset..." in captured["actions"]
        assert captured["filename"] == "demo_font_charset.txt"
        panel.deleteLater()

    def test_resource_action_buttons_update_accessibility_metadata_with_missing_resources(self, qapp, tmp_path):
        from ui_designer.model.resource_catalog import ResourceCatalog
        from ui_designer.ui.resource_panel import ResourcePanel

        resource_dir = tmp_path / "project" / ".eguiproject" / "resources"
        images_dir = resource_dir / "images"
        images_dir.mkdir(parents=True)
        (images_dir / "present.png").write_bytes(b"PNG")

        restore_source = tmp_path / "restore_sources" / "missing.png"
        restore_source.parent.mkdir(parents=True)
        restore_source.write_bytes(b"PNG")

        catalog = ResourceCatalog()
        catalog.add_image("present.png")
        catalog.add_image("missing.png")

        panel = ResourcePanel()
        panel.set_resource_dir(str(resource_dir))
        panel.set_resource_catalog(catalog)

        buttons = panel._resource_action_buttons["image"]

        assert buttons["import"].text() == "Import..."
        assert buttons["import"].toolTip() == (
            "Import image files into the project resource catalog. 2 image resources listed. "
            "1 missing image resource."
        )
        assert buttons["import"].statusTip() == buttons["import"].toolTip()
        assert buttons["import"].accessibleName() == (
            "Import image resources. 2 image resources listed. 1 missing image resource."
        )
        assert buttons["restore"].toolTip() == (
            "Restore missing image files by matching selected filenames against missing catalog entries. "
            "1 missing image resource."
        )
        assert buttons["restore"].accessibleName() == "Restore missing image resources. 1 missing image resource."
        assert buttons["replace"].toolTip() == (
            "Replace missing image resources with new files and rewrite widget references to the new filenames. "
            "1 missing image resource."
        )
        assert buttons["replace"].accessibleName() == "Replace missing image resources. 1 missing image resource."
        assert buttons["next_missing"].toolTip() == (
            "Select the next missing image resource in this tab. 1 missing image resource."
        )
        assert buttons["next_missing"].accessibleName() == "Next missing image resource. 1 missing image resource."

        restored, unmatched, failures = panel._restore_missing_resources_from_paths("image", [str(restore_source)])

        assert restored == ["missing.png"]
        assert unmatched == []
        assert failures == []
        assert buttons["restore"].toolTip() == "No missing image resources to restore in this tab."
        assert buttons["restore"].statusTip() == buttons["restore"].toolTip()
        assert buttons["restore"].accessibleName() == "Restore missing image resources unavailable"
        assert buttons["replace"].toolTip() == "No missing image resources to replace in this tab."
        assert buttons["replace"].accessibleName() == "Replace missing image resources unavailable"
        assert buttons["next_missing"].toolTip() == "No missing image resources to select in this tab."
        assert buttons["next_missing"].accessibleName() == "Next missing image resource unavailable"
        panel.deleteLater()

    def test_usage_table_updates_for_selected_resource(self, qapp, tmp_path):
        from ui_designer.model.resource_catalog import ResourceCatalog
        from ui_designer.model.resource_usage import ResourceUsageEntry
        from ui_designer.ui.resource_panel import ResourcePanel

        resource_dir = tmp_path / "project" / ".eguiproject" / "resources"
        images_dir = resource_dir / "images"
        images_dir.mkdir(parents=True)

        catalog = ResourceCatalog()
        catalog.add_image("star.png")

        panel = ResourcePanel()
        panel.set_resource_catalog(catalog)
        panel.set_resource_dir(str(resource_dir))
        panel.set_resource_usage_index(
            {
                ("image", "star.png"): [
                    ResourceUsageEntry("image", "star.png", "main_page", "hero_image", "image_file", "image"),
                    ResourceUsageEntry("image", "star.png", "detail_page", "badge", "image_file", "image"),
                ]
            }
        )

        panel._select_resource_item("image", "star.png")

        assert panel._usage_summary.text() == "2 widgets across 2 pages | star.png"
        assert panel._usage_current_page_only.text() == "This Page"
        assert panel._usage_current_page_only.toolTip() == "Open or select a page to filter usages to the current page."
        assert panel._usage_current_page_only.accessibleName() == "Usage filter unavailable: Current Page Only"
        assert panel._usage_summary.accessibleName() == (
            "Resource usage summary: 2 widgets across 2 pages | star.png"
        )
        assert panel._usage_table.rowCount() == 2
        assert panel._usage_table.accessibleName() == (
            "Resource usage table: 2 rows. Current selection: main_page/hero_image (image) [image_file]."
        )
        assert panel._usage_table.item(0, 0).text() == "main_page"
        assert panel._usage_table.item(0, 1).text() == "hero_image (image)"
        assert panel._usage_table.item(0, 1).toolTip() == (
            "Page: main_page. Widget: hero_image (image). Property: image_file."
        )
        assert panel._usage_table.item(0, 1).statusTip() == panel._usage_table.item(0, 1).toolTip()
        assert panel._usage_table.item(0, 1).data(Qt.AccessibleTextRole) == panel._usage_table.item(0, 1).toolTip()
        assert panel._usage_table.item(1, 0).text() == "detail_page"
        panel.deleteLater()

    def test_usage_table_can_filter_to_current_page(self, qapp, tmp_path):
        from ui_designer.model.resource_catalog import ResourceCatalog
        from ui_designer.model.resource_usage import ResourceUsageEntry
        from ui_designer.ui.resource_panel import ResourcePanel

        resource_dir = tmp_path / "project" / ".eguiproject" / "resources"
        images_dir = resource_dir / "images"
        images_dir.mkdir(parents=True)

        catalog = ResourceCatalog()
        catalog.add_image("star.png")

        panel = ResourcePanel()
        panel.set_resource_catalog(catalog)
        panel.set_resource_dir(str(resource_dir))
        panel.set_resource_usage_index(
            {
                ("image", "star.png"): [
                    ResourceUsageEntry("image", "star.png", "main_page", "hero_image", "image_file", "image"),
                    ResourceUsageEntry("image", "star.png", "detail_page", "badge", "image_file", "image"),
                ]
            }
        )
        panel.set_usage_page_context("detail_page")
        panel._select_resource_item("image", "star.png")

        panel._usage_current_page_only.setChecked(True)

        assert panel._usage_current_page_only.text() == "This Page"
        assert panel._usage_summary.text() == "1 widget on this page | 2 total across 2 pages | star.png"
        assert panel._usage_current_page_only.toolTip() == "Showing only usages on the current page: detail_page."
        assert panel._usage_current_page_only.accessibleName() == "Usage filter: current page only on for detail_page"
        assert panel._usage_summary.accessibleName() == (
            "Resource usage summary: 1 widget on this page | 2 total across 2 pages | star.png"
        )
        assert panel._usage_table.rowCount() == 1
        assert panel._usage_table.accessibleName() == (
            "Resource usage table: 1 row. Current selection: detail_page/badge (image) [image_file]."
        )
        assert panel._usage_table.item(0, 0).text() == "detail_page"
        assert panel._usage_table.item(0, 1).statusTip() == panel._usage_table.item(0, 1).toolTip()
        assert panel._usage_table.item(0, 1).data(Qt.AccessibleTextRole) == panel._usage_table.item(0, 1).toolTip()
        panel.deleteLater()

    def test_usage_table_double_click_emits_navigation_signal(self, qapp, tmp_path):
        from ui_designer.model.resource_catalog import ResourceCatalog
        from ui_designer.model.resource_usage import ResourceUsageEntry
        from ui_designer.ui.resource_panel import ResourcePanel

        resource_dir = tmp_path / "project" / ".eguiproject" / "resources"
        fonts_dir = resource_dir
        fonts_dir.mkdir(parents=True)

        catalog = ResourceCatalog()
        catalog.add_font("demo.ttf")

        panel = ResourcePanel()
        panel.set_resource_catalog(catalog)
        panel.set_resource_dir(str(resource_dir))
        panel.set_resource_usage_index(
            {
                ("font", "demo.ttf"): [
                    ResourceUsageEntry("font", "demo.ttf", "main_page", "title", "font_file", "label"),
                ]
            }
        )
        panel._select_resource_item("font", "demo.ttf")

        activated = []
        panel.usage_activated.connect(lambda page_name, widget_name: activated.append((page_name, widget_name)))

        panel._on_usage_item_activated(panel._usage_table.item(0, 0))

        assert activated == [("main_page", "title")]
        panel.deleteLater()

    def test_string_usage_table_updates_for_selected_key(self, qapp):
        from ui_designer.model.resource_usage import ResourceUsageEntry
        from ui_designer.model.string_resource import DEFAULT_LOCALE, StringResourceCatalog
        from ui_designer.ui.resource_panel import ResourcePanel

        string_catalog = StringResourceCatalog()
        string_catalog.set("greeting", "Hello", DEFAULT_LOCALE)

        panel = ResourcePanel()
        panel.set_string_catalog(string_catalog)
        panel.set_resource_usage_index(
            {
                ("string", "greeting"): [
                    ResourceUsageEntry("string", "greeting", "main_page", "title", "text", "label"),
                ]
            }
        )

        panel._select_resource_item("string", "greeting")

        assert panel._tabs.currentIndex() == 3
        assert panel._usage_summary.text() == "1 widget across 1 page | greeting"
        assert panel._usage_table.rowCount() == 1
        assert panel._usage_table.item(0, 1).text() == "title (label)"
        panel.deleteLater()

    def test_remove_string_key_with_usages_emits_rewrite_signal(self, qapp, monkeypatch):
        from ui_designer.model.resource_usage import ResourceUsageEntry
        from ui_designer.model.string_resource import DEFAULT_LOCALE, StringResourceCatalog
        from ui_designer.ui.resource_panel import ResourcePanel

        string_catalog = StringResourceCatalog()
        string_catalog.set("greeting", "Hello", DEFAULT_LOCALE)
        string_catalog.set("greeting", "Ni Hao", "zh")

        panel = ResourcePanel()
        panel.set_string_catalog(string_catalog)
        panel.set_resource_usage_index(
            {
                ("string", "greeting"): [
                    ResourceUsageEntry("string", "greeting", "main_page", "title", "text", "label"),
                    ResourceUsageEntry("string", "greeting", "detail_page", "subtitle", "text", "label"),
                ]
            }
        )
        panel._select_resource_item("string", "greeting")

        prompts = []
        rewrites = []
        imported = []
        monkeypatch.setattr(
            panel,
            "_confirm_reference_impact",
            lambda *args: prompts.append(args) or True,
        )
        panel.string_key_deleted.connect(lambda key, replacement: rewrites.append((key, replacement)))
        panel.resource_imported.connect(lambda: imported.append(True))

        panel._on_remove_string_key()

        assert prompts
        assert prompts[0][0] == "Remove String Key"
        assert prompts[0][1] == "greeting"
        assert len(prompts[0][2]) == 2
        assert "default-locale literal text" in prompts[0][4]
        assert rewrites == [("greeting", "Hello")]
        assert imported == [True]
        assert "greeting" not in panel.get_string_catalog().all_keys
        panel.deleteLater()

    def test_rename_string_key_updates_catalog_and_emits_signal(self, qapp, monkeypatch):
        from ui_designer.model.string_resource import DEFAULT_LOCALE, StringResourceCatalog
        from ui_designer.ui.resource_panel import ResourcePanel

        string_catalog = StringResourceCatalog()
        string_catalog.set("greeting", "Hello", DEFAULT_LOCALE)
        string_catalog.set("greeting", "Ni Hao", "zh")

        panel = ResourcePanel()
        panel.set_string_catalog(string_catalog)
        panel._select_resource_item("string", "greeting")

        renamed = []
        imported = []
        monkeypatch.setattr(
            "ui_designer.ui.resource_panel.QInputDialog.getText",
            lambda *args, **kwargs: ("salutation", True),
        )
        panel.string_key_renamed.connect(lambda old, new: renamed.append((old, new)))
        panel.resource_imported.connect(lambda: imported.append(True))

        panel._on_rename_string_key()

        assert panel.get_string_catalog().get("salutation", DEFAULT_LOCALE) == "Hello"
        assert panel.get_string_catalog().get("salutation", "zh") == "Ni Hao"
        assert "greeting" not in panel.get_string_catalog().all_keys
        assert renamed == [("greeting", "salutation")]
        assert imported == [True]
        assert panel._string_table.item(panel._string_table.currentRow(), 0).text() == "salutation"
        panel.deleteLater()

    def test_rename_string_key_with_usages_uses_shared_impact_confirmation(self, qapp, monkeypatch):
        from ui_designer.model.resource_usage import ResourceUsageEntry
        from ui_designer.model.string_resource import DEFAULT_LOCALE, StringResourceCatalog
        from ui_designer.ui.resource_panel import ResourcePanel

        string_catalog = StringResourceCatalog()
        string_catalog.set("greeting", "Hello", DEFAULT_LOCALE)

        panel = ResourcePanel()
        panel.set_string_catalog(string_catalog)
        panel.set_resource_usage_index(
            {
                ("string", "greeting"): [
                    ResourceUsageEntry("string", "greeting", "detail_page", "subtitle", "text", "label"),
                ]
            }
        )
        panel._select_resource_item("string", "greeting")

        prompts = []
        monkeypatch.setattr(
            "ui_designer.ui.resource_panel.QInputDialog.getText",
            lambda *args, **kwargs: ("salutation", True),
        )
        monkeypatch.setattr(
            panel,
            "_confirm_reference_impact",
            lambda *args: prompts.append(args) or True,
        )

        panel._on_rename_string_key()

        assert prompts
        assert prompts[0][0] == "Rename String Key"
        assert prompts[0][1] == "greeting"
        assert len(prompts[0][2]) == 1
        assert "salutation" in prompts[0][4]
        assert panel.get_string_catalog().get("salutation", DEFAULT_LOCALE) == "Hello"
        panel.deleteLater()

    def test_string_action_buttons_expose_unavailable_accessibility_metadata_without_selection(self, qapp):
        from ui_designer.ui.resource_panel import ResourcePanel

        panel = ResourcePanel()

        assert panel._locale_combo.accessibleName() == "String locale selector: Default. 0 locales configured."
        assert panel._locale_combo.toolTip() == panel._locale_combo.accessibleName()
        assert panel._string_table.accessibleName() == (
            "String resource table: 0 string keys. Current locale: Default. Current key: none."
        )
        assert panel._add_locale_btn.text() == "Add..."
        assert panel._remove_locale_btn.text() == "Remove"
        assert panel._add_key_btn.text() == "Add..."
        assert panel._rename_key_btn.text() == "Rename..."
        assert panel._remove_key_btn.text() == "Remove"
        assert panel._add_locale_btn.toolTip() == "Add a new locale for translated string values. 0 locales configured."
        assert panel._add_locale_btn.accessibleName() == "Add locale from Default. 0 locales configured."
        assert panel._remove_locale_btn.toolTip() == "Select a non-default locale to remove it."
        assert panel._remove_locale_btn.accessibleName() == "Remove locale unavailable: Default"
        assert panel._add_key_btn.toolTip() == "Add a new string key across all locales. 0 string keys defined."
        assert panel._add_key_btn.accessibleName() == "Add string key in Default. 0 string keys defined."
        assert panel._rename_key_btn.toolTip() == "Select a string key to rename it across all locales."
        assert panel._rename_key_btn.accessibleName() == "Rename string key unavailable in Default"
        assert panel._remove_key_btn.toolTip() == "Select a string key to remove it from all locales."
        assert panel._remove_key_btn.accessibleName() == "Remove string key unavailable in Default"
        panel.deleteLater()

    def test_string_action_buttons_update_accessibility_metadata_for_selected_key_and_locale(self, qapp):
        from ui_designer.model.resource_usage import ResourceUsageEntry
        from ui_designer.model.string_resource import DEFAULT_LOCALE, StringResourceCatalog
        from ui_designer.ui.resource_panel import ResourcePanel

        string_catalog = StringResourceCatalog()
        string_catalog.set("greeting", "Hello", DEFAULT_LOCALE)
        string_catalog.set("farewell", "Bye", DEFAULT_LOCALE)
        string_catalog.set("greeting", "Ni Hao", "zh")

        panel = ResourcePanel()
        panel.set_string_catalog(string_catalog)
        panel.set_resource_usage_index(
            {
                ("string", "greeting"): [
                    ResourceUsageEntry("string", "greeting", "main_page", "title", "text", "label"),
                    ResourceUsageEntry("string", "greeting", "detail_page", "subtitle", "text", "label"),
                ]
            }
        )
        panel._select_resource_item("string", "greeting")

        assert panel._locale_combo.accessibleName() == "String locale selector: Default. 2 locales configured."
        assert panel._string_table.accessibleName() == (
            "String resource table: 2 string keys. Current locale: Default. Current key: greeting."
        )
        assert panel._add_locale_btn.text() == "Add..."
        assert panel._remove_locale_btn.text() == "Remove"
        assert panel._add_key_btn.text() == "Add..."
        assert panel._rename_key_btn.text() == "Rename..."
        assert panel._remove_key_btn.text() == "Remove"
        assert panel._add_locale_btn.toolTip() == "Add a new locale for translated string values. 2 locales configured."
        assert panel._add_locale_btn.statusTip() == panel._add_locale_btn.toolTip()
        assert panel._add_locale_btn.accessibleName() == "Add locale from Default. 2 locales configured."
        assert panel._remove_locale_btn.toolTip() == "Select a non-default locale to remove it."
        assert panel._remove_locale_btn.accessibleName() == "Remove locale unavailable: Default"
        assert panel._add_key_btn.toolTip() == "Add a new string key across all locales. 2 string keys defined."
        assert panel._add_key_btn.accessibleName() == "Add string key in Default. 2 string keys defined."
        assert panel._rename_key_btn.toolTip() == "Rename string key greeting across all locales. 2 usages will be updated."
        assert panel._rename_key_btn.statusTip() == panel._rename_key_btn.toolTip()
        assert panel._rename_key_btn.accessibleName() == "Rename string key: greeting in Default. 2 usages."
        assert panel._remove_key_btn.toolTip() == "Remove string key greeting from all locales. 2 usages will be updated."
        assert panel._remove_key_btn.accessibleName() == "Remove string key: greeting in Default. 2 usages."

        panel._locale_combo.setCurrentIndex(panel._locale_combo.findData("zh"))
        qapp.processEvents()

        assert panel._locale_combo.accessibleName() == "String locale selector: zh. 2 locales configured."
        assert panel._string_table.accessibleName() == (
            "String resource table: 2 string keys. Current locale: zh. Current key: greeting."
        )
        assert panel._add_locale_btn.accessibleName() == "Add locale from zh. 2 locales configured."
        assert panel._remove_locale_btn.toolTip() == "Remove locale zh and all its translations."
        assert panel._remove_locale_btn.statusTip() == panel._remove_locale_btn.toolTip()
        assert panel._remove_locale_btn.accessibleName() == "Remove locale: zh"
        assert panel._add_key_btn.accessibleName() == "Add string key in zh. 2 string keys defined."
        assert panel._rename_key_btn.accessibleName() == "Rename string key: greeting in zh. 2 usages."
        assert panel._remove_key_btn.accessibleName() == "Remove string key: greeting in zh. 2 usages."
        panel.deleteLater()

    def test_tab_title_shows_missing_resource_count(self, qapp, tmp_path):
        from ui_designer.model.resource_catalog import ResourceCatalog
        from ui_designer.ui.resource_panel import ResourcePanel

        resource_dir = tmp_path / "project" / ".eguiproject" / "resources"
        images_dir = resource_dir / "images"
        images_dir.mkdir(parents=True)
        (images_dir / "present.png").write_bytes(b"PNG")

        catalog = ResourceCatalog()
        catalog.add_image("missing.png")
        catalog.add_image("present.png")

        panel = ResourcePanel()
        panel.set_resource_dir(str(resource_dir))
        panel.set_resource_catalog(catalog)

        assert panel._tabs.tabText(0) == "Images (2, 1 missing)"
        panel.deleteLater()

    def test_focus_missing_resource_cycles_through_missing_items(self, qapp, tmp_path):
        from ui_designer.model.resource_catalog import ResourceCatalog
        from ui_designer.ui.resource_panel import ResourcePanel

        resource_dir = tmp_path / "project" / ".eguiproject" / "resources"
        images_dir = resource_dir / "images"
        images_dir.mkdir(parents=True)
        (images_dir / "present.png").write_bytes(b"PNG")

        catalog = ResourceCatalog()
        catalog.add_image("missing_a.png")
        catalog.add_image("missing_b.png")
        catalog.add_image("present.png")

        panel = ResourcePanel()
        panel.set_resource_dir(str(resource_dir))
        panel.set_resource_catalog(catalog)

        feedback = []
        panel.feedback_message.connect(lambda message: feedback.append(message))

        first = panel._focus_missing_resource("image")
        second = panel._focus_missing_resource("image")

        assert first == "missing_a.png"
        assert second == "missing_b.png"
        assert panel._image_list.currentItem().text() == "missing_b.png"
        assert feedback == [
            "Focused missing image resource 1/2: missing_a.png.",
            "Focused missing image resource 2/2: missing_b.png.",
        ]
        panel.deleteLater()

    def test_import_text_refreshes_text_tab_and_catalog(self, qapp, tmp_path, monkeypatch):
        from ui_designer.ui.resource_panel import ResourcePanel

        resource_dir = tmp_path / "project" / ".eguiproject" / "resources"
        resource_dir.mkdir(parents=True)
        external_dir = tmp_path / "external_text"
        external_dir.mkdir()
        text_path = external_dir / "demo.txt"
        text_path.write_text("abc\n123\n", encoding="utf-8")

        panel = ResourcePanel()
        panel.set_resource_dir(str(resource_dir))

        imported = []
        panel.resource_imported.connect(lambda: imported.append(True))

        monkeypatch.setattr(
            "ui_designer.ui.resource_panel.QFileDialog.getOpenFileNames",
            lambda *args, **kwargs: ([str(text_path)], ""),
        )
        monkeypatch.setattr(
            "ui_designer.ui.resource_panel.QInputDialog.getText",
            lambda *args, **kwargs: ("demo.txt", True),
        )

        panel._on_import_text()

        assert (resource_dir / "demo.txt").is_file()
        assert panel.get_resource_catalog().text_files == ["demo.txt"]
        assert panel._text_list.count() == 1
        assert imported == [True]
        panel.deleteLater()

    def test_restore_missing_image_copies_file_and_clears_missing_state(self, qapp, tmp_path, monkeypatch):
        from ui_designer.model.resource_catalog import ResourceCatalog
        from ui_designer.ui.resource_panel import ResourcePanel

        resource_dir = tmp_path / "project" / ".eguiproject" / "resources"
        images_dir = resource_dir / "images"
        images_dir.mkdir(parents=True)
        external_dir = tmp_path / "external_images"
        external_dir.mkdir()
        source_path = external_dir / "external.png"
        source_path.write_bytes(b"PNG")

        catalog = ResourceCatalog()
        catalog.add_image("missing.png")

        panel = ResourcePanel()
        panel.set_resource_dir(str(resource_dir))
        panel.set_resource_catalog(catalog)

        imported = []
        panel.resource_imported.connect(lambda: imported.append(True))
        monkeypatch.setattr(
            "ui_designer.ui.resource_panel.QFileDialog.getOpenFileName",
            lambda *args, **kwargs: (str(source_path), "Images (*.png *.bmp *.jpg *.jpeg)"),
        )

        panel._restore_missing_resource("missing.png", "image")

        restored_path = images_dir / "missing.png"
        assert restored_path.is_file()
        assert restored_path.read_bytes() == b"PNG"
        assert imported == [True]
        item = panel._image_list.item(0)
        assert "File not found!" not in item.toolTip()
        assert item.statusTip() == item.toolTip()
        assert item.data(Qt.AccessibleTextRole) == item.toolTip()
        panel.deleteLater()

    def test_restore_missing_font_rejects_extension_mismatch(self, qapp, tmp_path, monkeypatch):
        from ui_designer.model.resource_catalog import ResourceCatalog
        from ui_designer.ui.resource_panel import ResourcePanel

        resource_dir = tmp_path / "project" / ".eguiproject" / "resources"
        resource_dir.mkdir(parents=True)
        external_dir = tmp_path / "external_fonts"
        external_dir.mkdir()
        source_path = external_dir / "replacement.otf"
        source_path.write_bytes(b"FONT")

        catalog = ResourceCatalog()
        catalog.add_font("missing.ttf")

        panel = ResourcePanel()
        panel.set_resource_dir(str(resource_dir))
        panel.set_resource_catalog(catalog)

        warnings = []
        monkeypatch.setattr(
            "ui_designer.ui.resource_panel.QFileDialog.getOpenFileName",
            lambda *args, **kwargs: (str(source_path), "Fonts (*.ttf *.otf)"),
        )
        monkeypatch.setattr("ui_designer.ui.resource_panel.QMessageBox.warning", lambda *args: warnings.append(args[1:]))

        panel._restore_missing_resource("missing.ttf", "font")

        assert not (resource_dir / "missing.ttf").exists()
        assert warnings
        assert warnings[0][0] == "Extension Mismatch"
        assert "Expected a '.ttf' file to restore 'missing.ttf'." in warnings[0][1]
        panel.deleteLater()

    def test_restore_missing_resources_batch_restores_only_matching_files(self, qapp, tmp_path, monkeypatch):
        from ui_designer.model.resource_catalog import ResourceCatalog
        from ui_designer.ui.resource_panel import ResourcePanel

        resource_dir = tmp_path / "project" / ".eguiproject" / "resources"
        images_dir = resource_dir / "images"
        images_dir.mkdir(parents=True)
        external_dir = tmp_path / "external_images"
        external_dir.mkdir()
        first_match = external_dir / "missing_a.png"
        first_match.write_bytes(b"A")
        no_match = external_dir / "extra.png"
        no_match.write_bytes(b"X")

        catalog = ResourceCatalog()
        catalog.add_image("missing_a.png")
        catalog.add_image("missing_b.png")

        panel = ResourcePanel()
        panel.set_resource_dir(str(resource_dir))
        panel.set_resource_catalog(catalog)

        imported = []
        feedback = []
        panel.resource_imported.connect(lambda: imported.append(True))
        panel.feedback_message.connect(lambda message: feedback.append(message))
        monkeypatch.setattr(
            "ui_designer.ui.resource_panel.QFileDialog.getOpenFileNames",
            lambda *args, **kwargs: ([str(first_match), str(no_match)], "Images (*.png *.bmp *.jpg *.jpeg)"),
        )

        panel._restore_missing_resources("image")

        assert (images_dir / "missing_a.png").is_file()
        assert not (images_dir / "missing_b.png").exists()
        assert imported == [True]
        assert feedback == ["Restored image resources: 1 restored, 1 unmatched, 1 remaining missing."]
        first_item = panel._image_list.item(0)
        second_item = panel._image_list.item(1)
        assert "File not found!" not in first_item.toolTip()
        assert "File not found!" in second_item.toolTip()
        assert first_item.statusTip() == first_item.toolTip()
        assert second_item.data(Qt.AccessibleTextRole) == second_item.toolTip()
        panel.deleteLater()

    def test_restore_missing_resources_warns_when_no_matching_files_selected(self, qapp, tmp_path, monkeypatch):
        from ui_designer.model.resource_catalog import ResourceCatalog
        from ui_designer.ui.resource_panel import ResourcePanel

        resource_dir = tmp_path / "project" / ".eguiproject" / "resources"
        resource_dir.mkdir(parents=True)
        external_dir = tmp_path / "external_fonts"
        external_dir.mkdir()
        no_match = external_dir / "other.ttf"
        no_match.write_bytes(b"FONT")

        catalog = ResourceCatalog()
        catalog.add_font("missing.ttf")

        panel = ResourcePanel()
        panel.set_resource_dir(str(resource_dir))
        panel.set_resource_catalog(catalog)

        warnings = []
        monkeypatch.setattr(
            "ui_designer.ui.resource_panel.QFileDialog.getOpenFileNames",
            lambda *args, **kwargs: ([str(no_match)], "Fonts (*.ttf *.otf)"),
        )
        monkeypatch.setattr("ui_designer.ui.resource_panel.QMessageBox.warning", lambda *args: warnings.append(args[1:]))

        panel._restore_missing_resources("font")

        assert not (resource_dir / "missing.ttf").exists()
        assert warnings
        assert warnings[0][0] == "Restore Missing Resources"
        assert "No matching missing font resources were found in the selected files." in warnings[0][1]
        panel.deleteLater()

    def test_replace_missing_image_updates_catalog_and_emits_rename(self, qapp, tmp_path, monkeypatch):
        from ui_designer.model.resource_catalog import ResourceCatalog
        from ui_designer.ui.resource_panel import ResourcePanel

        resource_dir = tmp_path / "project" / ".eguiproject" / "resources"
        images_dir = resource_dir / "images"
        images_dir.mkdir(parents=True)
        external_dir = tmp_path / "external_images"
        external_dir.mkdir()
        source_path = external_dir / "replacement.png"
        source_path.write_bytes(b"PNG")

        catalog = ResourceCatalog()
        catalog.add_image("missing.png")

        panel = ResourcePanel()
        panel.set_resource_dir(str(resource_dir))
        panel.set_resource_catalog(catalog)

        imported = []
        renamed = []
        feedback = []
        panel.resource_imported.connect(lambda: imported.append(True))
        panel.resource_renamed.connect(lambda res_type, old, new: renamed.append((res_type, old, new)))
        panel.feedback_message.connect(lambda message: feedback.append(message))
        monkeypatch.setattr(
            "ui_designer.ui.resource_panel.QFileDialog.getOpenFileName",
            lambda *args, **kwargs: (str(source_path), "Images (*.png *.bmp *.jpg *.jpeg)"),
        )

        panel._replace_missing_resource("missing.png", "image")

        assert not panel.get_resource_catalog().has_image("missing.png")
        assert panel.get_resource_catalog().has_image("replacement.png")
        assert (images_dir / "replacement.png").is_file()
        assert imported == [True]
        assert renamed == [("image", "missing.png", "replacement.png")]
        assert feedback == ["Replaced image resources: 1 renamed."]
        assert panel._tabs.tabText(0) == "Images (1)"
        panel.deleteLater()

    def test_replace_missing_resources_from_mapping_supports_restore_and_rename(self, qapp, tmp_path):
        from ui_designer.model.resource_catalog import ResourceCatalog
        from ui_designer.ui.resource_panel import ResourcePanel

        resource_dir = tmp_path / "project" / ".eguiproject" / "resources"
        images_dir = resource_dir / "images"
        images_dir.mkdir(parents=True)
        external_dir = tmp_path / "external_images"
        external_dir.mkdir()
        renamed_path = external_dir / "renamed.png"
        renamed_path.write_bytes(b"NEW")
        restored_path = external_dir / "missing_b.png"
        restored_path.write_bytes(b"OLD")

        catalog = ResourceCatalog()
        catalog.add_image("missing_a.png")
        catalog.add_image("missing_b.png")

        panel = ResourcePanel()
        panel.set_resource_dir(str(resource_dir))
        panel.set_resource_catalog(catalog)

        imported = []
        renamed = []
        feedback = []
        panel.resource_imported.connect(lambda: imported.append(True))
        panel.resource_renamed.connect(lambda res_type, old, new: renamed.append((res_type, old, new)))
        panel.feedback_message.connect(lambda message: feedback.append(message))

        restored, renamed_pairs, failures = panel._replace_missing_resources_from_mapping(
            "image",
            {
                "missing_a.png": str(renamed_path),
                "missing_b.png": str(restored_path),
            },
        )

        assert restored == ["missing_b.png"]
        assert renamed_pairs == [("missing_a.png", "renamed.png")]
        assert failures == []
        assert imported == [True]
        assert renamed == [("image", "missing_a.png", "renamed.png")]
        assert feedback == ["Replaced image resources: 1 renamed, 1 restored."]
        assert panel.get_resource_catalog().has_image("missing_b.png")
        assert panel.get_resource_catalog().has_image("renamed.png")
        assert not panel.get_resource_catalog().has_image("missing_a.png")
        assert (images_dir / "renamed.png").is_file()
        assert (images_dir / "missing_b.png").is_file()
        panel.deleteLater()

    def test_batch_replace_impact_confirmation_can_open_selected_usage(self, qapp):
        from ui_designer.model.resource_usage import ResourceUsageEntry
        from ui_designer.ui.resource_panel import ResourcePanel

        panel = ResourcePanel()
        panel.set_resource_usage_index(
            {
                ("image", "missing.png"): [
                    ResourceUsageEntry("image", "missing.png", "detail_page", "hero", "image_file", "image"),
                ]
            }
        )

        activated = []
        panel.usage_activated.connect(lambda page_name, widget_name: activated.append((page_name, widget_name)))
        impacts, total_rename_count = panel._collect_batch_replace_impacts(
            "image",
            {"missing.png": os.path.join("C:\\temp", "replacement.png")},
        )

        def open_selected_usage():
            dialog = QApplication.activeModalWidget()
            assert dialog is not None
            dialog._open_selected_usage()

        QTimer.singleShot(0, open_selected_usage)
        confirmed = panel._confirm_batch_replace_impact("image", impacts, total_rename_count)

        assert confirmed is False
        assert total_rename_count == 1
        assert activated == [("detail_page", "hero")]
        panel.deleteLater()

    def test_missing_resource_replace_dialog_exposes_accessibility_metadata(self, qapp, monkeypatch):
        from PyQt5.QtWidgets import QLabel
        from ui_designer.ui.resource_panel import _MissingResourceReplaceDialog

        monkeypatch.setattr("ui_designer.ui.resource_panel.CaptionLabel", QLabel)

        source_a = os.path.join("C:\\temp", "missing.png")
        source_b = os.path.join("C:\\temp", "hero.png")

        dialog = _MissingResourceReplaceDialog(
            ["missing.png", "icon.png"],
            [source_a, source_b],
        )

        first_combo = dialog._combos[0][1]
        second_combo = dialog._combos[1][1]

        assert "2 missing resources." in dialog.accessibleName()
        assert "2 candidate files available." in dialog.accessibleName()
        assert "1 replacement selected." in dialog.accessibleName()
        assert dialog._header_frame.accessibleName() == (
            "Resource dialog header. Replace missing resources: 2 missing resources. "
            "2 candidate files available. 1 replacement selected."
        )
        assert dialog._eyebrow_label.isHidden()
        assert dialog._subtitle_label.isHidden()
        assert dialog._metrics_frame.isHidden()
        assert dialog._eyebrow_label.accessibleName() == "Resource recovery workspace."
        assert dialog._title_label.text() == "Replace Missing"
        assert dialog._title_label.accessibleName() == "Resource replacement title: Replace Missing Resources."
        assert dialog._subtitle_label.accessibleName() == dialog._subtitle_label.text()
        assert dialog._missing_metric_value.accessibleName() == "Resource dialog metric: Missing. 2 resources."
        assert dialog._missing_metric_value._resource_dialog_metric_label.accessibleName() == "Missing metric label."
        assert dialog._missing_metric_value._resource_dialog_metric_card.accessibleName() == "Missing metric: 2 resources."
        assert dialog._candidate_metric_value.accessibleName() == "Resource dialog metric: Candidates. 2 files."
        assert dialog._candidate_metric_value._resource_dialog_metric_label.accessibleName() == "Candidates metric label."
        assert dialog._candidate_metric_value._resource_dialog_metric_card.accessibleName() == "Candidates metric: 2 files."
        assert dialog._selected_metric_value.accessibleName() == "Resource dialog metric: Selection. 1 replacement."
        assert dialog._selected_metric_value._resource_dialog_metric_label.accessibleName() == "Selection metric label."
        assert dialog._selected_metric_value._resource_dialog_metric_card.accessibleName() == "Selection metric: 1 replacement."
        assert len(dialog.findChildren(QFrame, "resource_dialog_metric_card")) == 3
        assert dialog._caption.isHidden()
        assert dialog._caption.accessibleName() == (
            "Replace missing resources help: Choose replacement files for missing resources. "
            "The selected file names become the new project resource names."
        )
        assert dialog._table.accessibleName() == "Missing resource replacement table: 2 rows. 1 replacement selected."
        assert first_combo.toolTip() == "Choose replacement file for missing.png. Current selection: missing.png."
        assert second_combo.toolTip() == "Choose replacement file for icon.png. Current selection: (Skip)."
        assert dialog._ok_button.toolTip() == "Apply the selected replacement files."
        assert dialog._ok_button.accessibleName() == "Confirm replacement files"

        second_combo.setCurrentIndex(1)
        qapp.processEvents()

        assert "1 duplicate replacement file selected." in dialog.accessibleName()
        assert dialog._header_frame.accessibleName() == (
            "Resource dialog header. Replace missing resources: 2 missing resources. "
            "2 candidate files available. 2 replacements selected. 1 duplicate replacement file selected."
        )
        assert dialog._selected_metric_value.accessibleName() == (
            "Resource dialog metric: Selection. 2 replacements | 1 duplicate."
        )
        assert dialog._selected_metric_value._resource_dialog_metric_card.accessibleName() == (
            "Selection metric: 2 replacements | 1 duplicate."
        )
        assert dialog._ok_button.toolTip() == "Resolve duplicate replacement files before continuing."
        assert dialog._ok_button.accessibleName() == "Confirm replacement files unavailable"
        dialog.deleteLater()

    def test_replace_dialog_header_hint_skips_no_op_rewrites(self, qapp, monkeypatch):
        from PyQt5.QtWidgets import QLabel
        from ui_designer.ui.resource_panel import _MissingResourceReplaceDialog

        monkeypatch.setattr("ui_designer.ui.resource_panel.CaptionLabel", QLabel)

        source_a = os.path.join("C:\\temp", "missing.png")
        source_b = os.path.join("C:\\temp", "hero.png")

        dialog = _MissingResourceReplaceDialog(
            ["missing.png", "icon.png"],
            [source_a, source_b],
        )
        dialog._header_frame.setProperty("_resource_panel_hint_snapshot", None)

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

        dialog._combos[1][1].setCurrentIndex(1)
        qapp.processEvents()
        assert hint_calls == 2
        dialog.deleteLater()

    def test_replace_dialog_header_accessible_name_skips_no_op_rewrites(self, qapp, monkeypatch):
        from PyQt5.QtWidgets import QLabel
        from ui_designer.ui.resource_panel import _MissingResourceReplaceDialog

        monkeypatch.setattr("ui_designer.ui.resource_panel.CaptionLabel", QLabel)

        source_a = os.path.join("C:\\temp", "missing.png")
        source_b = os.path.join("C:\\temp", "hero.png")

        dialog = _MissingResourceReplaceDialog(
            ["missing.png", "icon.png"],
            [source_a, source_b],
        )
        dialog._header_frame.setProperty("_resource_panel_accessible_snapshot", None)

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

        dialog._combos[1][1].setCurrentIndex(1)
        qapp.processEvents()
        assert accessible_calls == 2
        dialog.deleteLater()

    def test_reference_impact_dialog_exposes_accessibility_metadata(self, qapp):
        from ui_designer.model.resource_usage import ResourceUsageEntry
        from ui_designer.ui.resource_panel import _ReferenceImpactDialog

        usages = [
            ResourceUsageEntry("image", "missing.png", "main_page", "hero", "image_file", "image"),
            ResourceUsageEntry("image", "missing.png", "detail_page", "title", "image_file", "label"),
        ]

        dialog = _ReferenceImpactDialog(
            None,
            "Delete Resource",
            "This action updates 2 widget references.",
            usages,
            "Delete",
        )

        assert dialog.accessibleName() == "Delete Resource: 2 affected usages. Current selection: main_page/hero (image)."
        assert dialog._header_frame.accessibleName() == (
            "Resource dialog header. Delete Resource: 2 affected usages. Current selection: main_page/hero (image)."
        )
        assert dialog._eyebrow_label.isHidden()
        assert dialog._subtitle_label.isHidden()
        assert dialog._metrics_frame.isHidden()
        assert dialog._eyebrow_label.accessibleName() == "Resource impact workspace."
        assert dialog._title_label.accessibleName() == "Reference impact title: Delete Resource."
        assert dialog._subtitle_label.accessibleName() == dialog._subtitle_label.text()
        assert dialog._usage_metric_value.accessibleName() == "Resource dialog metric: Affected Usages. 2 usages."
        assert dialog._usage_metric_value._resource_dialog_metric_label.accessibleName() == "Affected Usages metric label."
        assert dialog._usage_metric_value._resource_dialog_metric_card.accessibleName() == "Affected Usages metric: 2 usages."
        assert dialog._selection_metric_value.accessibleName() == (
            "Resource dialog metric: Selection. main_page/hero (image)."
        )
        assert dialog._selection_metric_value._resource_dialog_metric_card.accessibleName() == (
            "Selection metric: main_page/hero (image)."
        )
        assert dialog._action_metric_value.accessibleName() == "Resource dialog metric: Action. Delete."
        assert dialog._action_metric_value._resource_dialog_metric_card.accessibleName() == "Action metric: Delete."
        assert len(dialog.findChildren(QFrame, "resource_dialog_metric_card")) == 3
        assert dialog._summary_label.isHidden()
        assert dialog._summary_label.accessibleName() == (
            "Reference impact summary: This action updates 2 widget references."
        )
        assert dialog._open_usage_button.text() == "Open"
        assert dialog._table.accessibleName() == (
            "Affected usages table: 2 rows. Current selection: main_page/hero (image)."
        )
        assert dialog._table.item(0, 1).toolTip() == (
            "Page: main_page. Widget: hero (image). Property: image_file."
        )
        assert dialog._table.item(0, 1).statusTip() == dialog._table.item(0, 1).toolTip()
        assert dialog._table.item(0, 1).data(Qt.AccessibleTextRole) == dialog._table.item(0, 1).toolTip()
        assert dialog._open_usage_button.toolTip() == "Open the selected usage to review it in the editor."
        assert dialog._open_usage_button.accessibleName() == "Open selected usage"
        assert dialog._ok_button.accessibleName() == "Delete"

        dialog._table.selectRow(1)
        qapp.processEvents()

        assert dialog.accessibleName() == "Delete Resource: 2 affected usages. Current selection: detail_page/title (label)."
        assert dialog._header_frame.accessibleName() == (
            "Resource dialog header. Delete Resource: 2 affected usages. Current selection: detail_page/title (label)."
        )
        assert dialog._selection_metric_value.accessibleName() == (
            "Resource dialog metric: Selection. detail_page/title (label)."
        )
        dialog.deleteLater()

    def test_batch_replace_impact_dialog_exposes_accessibility_metadata(self, qapp):
        from ui_designer.model.resource_usage import ResourceUsageEntry
        from ui_designer.ui.resource_panel import _BatchReplaceImpactDialog

        impacts = [
            {
                "old_name": "missing_a.png",
                "new_name": "renamed_a.png",
                "usages": [
                    ResourceUsageEntry("image", "missing_a.png", "main_page", "hero_main", "image_file", "image"),
                ],
                "widget_count": 1,
                "page_count": 1,
            },
            {
                "old_name": "missing_b.png",
                "new_name": "renamed_b.png",
                "usages": [
                    ResourceUsageEntry("image", "missing_b.png", "detail_page", "hero_detail", "image_file", "image"),
                ],
                "widget_count": 1,
                "page_count": 1,
            },
        ]

        dialog = _BatchReplaceImpactDialog(
            None,
            "Replace Missing Resources",
            "image",
            impacts,
            2,
            "Replace",
            current_page_name="detail_page",
        )

        assert "2 visible rename impacts." in dialog.accessibleName()
        assert "Current rename: missing_a.png -> renamed_a.png." in dialog.accessibleName()
        assert dialog._header_frame.accessibleName() == (
            "Resource dialog header. Replace Missing Resources: 2 visible rename impacts. 2 visible usages shown. "
            "Current page only: off. Current rename: missing_a.png -> renamed_a.png. "
            "Current usage: main_page/hero_main (image) [image_file]."
        )
        assert dialog._eyebrow_label.isHidden()
        assert dialog._subtitle_label.isHidden()
        assert dialog._metrics_frame.isHidden()
        assert dialog._eyebrow_label.accessibleName() == "Batch rename impact workspace."
        assert dialog._title_label.text() == "Replace Missing"
        assert dialog._title_label.accessibleName() == "Batch replace impact title: Replace Missing Resources."
        assert dialog._subtitle_label.accessibleName() == dialog._subtitle_label.text()
        assert dialog._rename_metric_value.accessibleName() == "Resource dialog metric: Visible Renames. 2 renames."
        assert dialog._rename_metric_value._resource_dialog_metric_label.accessibleName() == "Visible Renames metric label."
        assert dialog._rename_metric_value._resource_dialog_metric_card.accessibleName() == "Visible Renames metric: 2 renames."
        assert dialog._usage_metric_value.accessibleName() == "Resource dialog metric: Visible Usages. 2 usages."
        assert dialog._usage_metric_value._resource_dialog_metric_card.accessibleName() == "Visible Usages metric: 2 usages."
        assert dialog._filter_metric_value.accessibleName() == "Resource dialog metric: Page Filter. All pages."
        assert dialog._filter_metric_value._resource_dialog_metric_card.accessibleName() == "Page Filter metric: All pages."
        assert len(dialog.findChildren(QFrame, "resource_dialog_metric_card")) == 3
        assert dialog._summary_label.isHidden()
        assert dialog._summary_label.accessibleName().startswith(
            "Batch replace summary: The selected replacements will rename 2 missing image resources."
        )
        assert dialog._current_page_only.text() == "This Page"
        assert dialog._group_caption.text() == "Impacts"
        assert dialog._usage_caption.text() == "Usages"
        assert dialog._current_page_only.toolTip() == "Filter impacts to the current page: detail_page."
        assert dialog._impact_table.accessibleName() == (
            "Rename impact table: 2 rows. Current selection: missing_a.png -> renamed_a.png."
        )
        assert dialog._usage_table.accessibleName() == (
            "Affected usages table: 1 row. Current selection: main_page/hero_main (image) [image_file]."
        )
        assert dialog._impact_table.item(0, 0).toolTip() == (
            "Rename missing_a.png to renamed_a.png. 1 widget affected across 1 page."
        )
        assert dialog._impact_table.item(0, 0).statusTip() == dialog._impact_table.item(0, 0).toolTip()
        assert dialog._impact_table.item(0, 0).data(Qt.AccessibleTextRole) == dialog._impact_table.item(0, 0).toolTip()
        assert dialog._usage_table.item(0, 1).statusTip() == dialog._usage_table.item(0, 1).toolTip()
        assert dialog._usage_table.item(0, 1).data(Qt.AccessibleTextRole) == dialog._usage_table.item(0, 1).toolTip()
        assert dialog._open_usage_button.text() == "Open"
        assert dialog._open_usage_button.toolTip() == "Open the selected affected usage in the editor."
        assert dialog._open_usage_button.accessibleName() == "Open selected affected usage"
        assert dialog._ok_button.accessibleName() == "Replace"

        dialog._current_page_only.setChecked(True)
        qapp.processEvents()

        assert dialog._current_page_only.toolTip() == "Showing only impacts on the current page: detail_page."
        assert dialog._header_frame.accessibleName() == (
            "Resource dialog header. Replace Missing Resources: 1 visible rename impact. 1 visible usage shown. "
            "Current page only: on. Current rename: missing_b.png -> renamed_b.png. "
            "Current usage: detail_page/hero_detail (image) [image_file]."
        )
        assert dialog._impact_table.accessibleName() == (
            "Rename impact table: 1 row. Current selection: missing_b.png -> renamed_b.png."
        )
        assert dialog._usage_table.accessibleName() == (
            "Affected usages table: 1 row. Current selection: detail_page/hero_detail (image) [image_file]."
        )
        assert dialog._filter_metric_value.accessibleName() == "Resource dialog metric: Page Filter. Current page only."
        assert dialog._filter_metric_value._resource_dialog_metric_card.accessibleName() == (
            "Page Filter metric: Current page only."
        )
        dialog.deleteLater()

    def test_batch_replace_impact_dialog_can_filter_to_current_page(self, qapp):
        from ui_designer.model.resource_usage import ResourceUsageEntry
        from ui_designer.ui.resource_panel import _BatchReplaceImpactDialog

        impacts = [
            {
                "old_name": "missing_a.png",
                "new_name": "renamed_a.png",
                "usages": [
                    ResourceUsageEntry("image", "missing_a.png", "main_page", "hero_main", "image_file", "image"),
                ],
                "widget_count": 1,
                "page_count": 1,
            },
            {
                "old_name": "missing_b.png",
                "new_name": "renamed_b.png",
                "usages": [
                    ResourceUsageEntry("image", "missing_b.png", "detail_page", "hero_detail", "image_file", "image"),
                ],
                "widget_count": 1,
                "page_count": 1,
            },
        ]

        dialog = _BatchReplaceImpactDialog(
            None,
            "Replace Missing Resources",
            "image",
            impacts,
            2,
            "Replace",
            current_page_name="detail_page",
        )

        assert dialog._impact_table.rowCount() == 2

        dialog._current_page_only.setChecked(True)

        assert dialog._impact_table.rowCount() == 1
        assert dialog._impact_table.item(0, 0).text() == "missing_b.png"
        assert dialog._usage_table.rowCount() == 1
        assert dialog._usage_table.item(0, 0).text() == "detail_page"
        assert dialog._current_page_only.text() == "This Page"
        assert "Showing impacts on the current page: detail_page." in dialog._summary_label.text()
        dialog.deleteLater()

    def test_batch_replace_impact_confirmation_uses_current_page_filter_for_navigation(self, qapp):
        from ui_designer.model.resource_usage import ResourceUsageEntry
        from ui_designer.ui.resource_panel import ResourcePanel

        panel = ResourcePanel()
        panel.set_usage_page_context("detail_page")
        panel.set_resource_usage_index(
            {
                ("image", "missing_a.png"): [
                    ResourceUsageEntry("image", "missing_a.png", "main_page", "hero_main", "image_file", "image"),
                ],
                ("image", "missing_b.png"): [
                    ResourceUsageEntry("image", "missing_b.png", "detail_page", "hero_detail", "image_file", "image"),
                ],
            }
        )

        activated = []
        panel.usage_activated.connect(lambda page_name, widget_name: activated.append((page_name, widget_name)))
        impacts, total_rename_count = panel._collect_batch_replace_impacts(
            "image",
            {
                "missing_a.png": os.path.join("C:\\temp", "renamed_a.png"),
                "missing_b.png": os.path.join("C:\\temp", "renamed_b.png"),
            },
        )

        def open_selected_usage():
            dialog = QApplication.activeModalWidget()
            assert dialog is not None
            dialog._current_page_only.setChecked(True)
            dialog._open_selected_usage()

        QTimer.singleShot(0, open_selected_usage)
        confirmed = panel._confirm_batch_replace_impact("image", impacts, total_rename_count)

        assert confirmed is False
        assert activated == [("detail_page", "hero_detail")]
        panel.deleteLater()

    def test_replace_missing_resources_shows_batch_impact_preview_before_apply(self, qapp, tmp_path, monkeypatch):
        from ui_designer.model.resource_catalog import ResourceCatalog
        from ui_designer.model.resource_usage import ResourceUsageEntry
        from ui_designer.ui.resource_panel import ResourcePanel

        resource_dir = tmp_path / "project" / ".eguiproject" / "resources"
        images_dir = resource_dir / "images"
        images_dir.mkdir(parents=True)
        replacement_dir = tmp_path / "external_images"
        replacement_dir.mkdir()
        replacement_path = replacement_dir / "renamed.png"
        replacement_path.write_bytes(b"PNG")

        catalog = ResourceCatalog()
        catalog.add_image("missing.png")

        panel = ResourcePanel()
        panel.set_resource_dir(str(resource_dir))
        panel.set_resource_catalog(catalog)
        panel.set_resource_usage_index(
            {
                ("image", "missing.png"): [
                    ResourceUsageEntry("image", "missing.png", "main_page", "hero", "image_file", "image"),
                ]
            }
        )

        captured = {}
        preview_calls = []
        apply_calls = []

        class FakeDialog:
            def __init__(self, missing_names, source_paths, parent=None):
                captured["missing_names"] = list(missing_names)
                captured["source_paths"] = list(source_paths)

            def exec_(self):
                return 1

            def selected_mapping(self):
                return {"missing.png": str(replacement_path)}

        monkeypatch.setattr(
            "ui_designer.ui.resource_panel.QFileDialog.getOpenFileNames",
            lambda *args, **kwargs: ([str(replacement_path)], "Images (*.png *.bmp *.jpg *.jpeg)"),
        )
        monkeypatch.setattr("ui_designer.ui.resource_panel._MissingResourceReplaceDialog", FakeDialog)
        monkeypatch.setattr(
            panel,
            "_confirm_batch_replace_impact",
            lambda resource_type, impacts, total_rename_count: preview_calls.append((resource_type, impacts, total_rename_count)) or True,
        )
        monkeypatch.setattr(
            panel,
            "_replace_missing_resources_from_mapping",
            lambda resource_type, replacements: apply_calls.append((resource_type, replacements)) or ([], [], []),
        )

        panel._replace_missing_resources("image")

        assert captured["missing_names"] == ["missing.png"]
        assert captured["source_paths"] == [str(replacement_path)]
        assert len(preview_calls) == 1
        assert preview_calls[0][0] == "image"
        assert preview_calls[0][2] == 1
        assert preview_calls[0][1][0]["old_name"] == "missing.png"
        assert preview_calls[0][1][0]["new_name"] == "renamed.png"
        assert apply_calls == [("image", {"missing.png": str(replacement_path)})]
        panel.deleteLater()

    def test_replace_missing_resources_can_cancel_batch_impact_preview(self, qapp, tmp_path, monkeypatch):
        from ui_designer.model.resource_catalog import ResourceCatalog
        from ui_designer.model.resource_usage import ResourceUsageEntry
        from ui_designer.ui.resource_panel import ResourcePanel

        resource_dir = tmp_path / "project" / ".eguiproject" / "resources"
        images_dir = resource_dir / "images"
        images_dir.mkdir(parents=True)
        replacement_dir = tmp_path / "external_images"
        replacement_dir.mkdir()
        replacement_path = replacement_dir / "renamed.png"
        replacement_path.write_bytes(b"PNG")

        catalog = ResourceCatalog()
        catalog.add_image("missing.png")

        panel = ResourcePanel()
        panel.set_resource_dir(str(resource_dir))
        panel.set_resource_catalog(catalog)
        panel.set_resource_usage_index(
            {
                ("image", "missing.png"): [
                    ResourceUsageEntry("image", "missing.png", "main_page", "hero", "image_file", "image"),
                ]
            }
        )

        preview_calls = []

        class FakeDialog:
            def __init__(self, missing_names, source_paths, parent=None):
                pass

            def exec_(self):
                return 1

            def selected_mapping(self):
                return {"missing.png": str(replacement_path)}

        monkeypatch.setattr(
            "ui_designer.ui.resource_panel.QFileDialog.getOpenFileNames",
            lambda *args, **kwargs: ([str(replacement_path)], "Images (*.png *.bmp *.jpg *.jpeg)"),
        )
        monkeypatch.setattr("ui_designer.ui.resource_panel._MissingResourceReplaceDialog", FakeDialog)
        monkeypatch.setattr(
            panel,
            "_confirm_batch_replace_impact",
            lambda resource_type, impacts, total_rename_count: preview_calls.append((resource_type, impacts, total_rename_count)) or False,
        )
        monkeypatch.setattr(
            panel,
            "_replace_missing_resources_from_mapping",
            lambda *args, **kwargs: pytest.fail("_replace_missing_resources_from_mapping should not be called"),
        )

        panel._replace_missing_resources("image")

        assert len(preview_calls) == 1
        panel.deleteLater()

    def test_replace_missing_resources_skips_batch_impact_preview_for_restore_only(self, qapp, tmp_path, monkeypatch):
        from ui_designer.model.resource_catalog import ResourceCatalog
        from ui_designer.ui.resource_panel import ResourcePanel

        resource_dir = tmp_path / "project" / ".eguiproject" / "resources"
        images_dir = resource_dir / "images"
        images_dir.mkdir(parents=True)
        replacement_dir = tmp_path / "external_images"
        replacement_dir.mkdir()
        replacement_path = replacement_dir / "missing.png"
        replacement_path.write_bytes(b"PNG")

        catalog = ResourceCatalog()
        catalog.add_image("missing.png")

        panel = ResourcePanel()
        panel.set_resource_dir(str(resource_dir))
        panel.set_resource_catalog(catalog)

        apply_calls = []

        class FakeDialog:
            def __init__(self, missing_names, source_paths, parent=None):
                pass

            def exec_(self):
                return 1

            def selected_mapping(self):
                return {"missing.png": str(replacement_path)}

        monkeypatch.setattr(
            "ui_designer.ui.resource_panel.QFileDialog.getOpenFileNames",
            lambda *args, **kwargs: ([str(replacement_path)], "Images (*.png *.bmp *.jpg *.jpeg)"),
        )
        monkeypatch.setattr("ui_designer.ui.resource_panel._MissingResourceReplaceDialog", FakeDialog)
        monkeypatch.setattr(
            panel,
            "_confirm_batch_replace_impact",
            lambda *args, **kwargs: pytest.fail("_confirm_batch_replace_impact should not be called"),
        )
        monkeypatch.setattr(
            panel,
            "_replace_missing_resources_from_mapping",
            lambda resource_type, replacements: apply_calls.append((resource_type, replacements)) or ([], [], []),
        )

        panel._replace_missing_resources("image")

        assert apply_calls == [("image", {"missing.png": str(replacement_path)})]
        panel.deleteLater()

    def test_replace_missing_resource_shows_batch_impact_preview_before_apply(self, qapp, tmp_path, monkeypatch):
        from ui_designer.model.resource_catalog import ResourceCatalog
        from ui_designer.model.resource_usage import ResourceUsageEntry
        from ui_designer.ui.resource_panel import ResourcePanel

        resource_dir = tmp_path / "project" / ".eguiproject" / "resources"
        images_dir = resource_dir / "images"
        images_dir.mkdir(parents=True)
        replacement_dir = tmp_path / "external_images"
        replacement_dir.mkdir()
        replacement_path = replacement_dir / "renamed.png"
        replacement_path.write_bytes(b"PNG")

        catalog = ResourceCatalog()
        catalog.add_image("missing.png")

        panel = ResourcePanel()
        panel.set_resource_dir(str(resource_dir))
        panel.set_resource_catalog(catalog)
        panel.set_resource_usage_index(
            {
                ("image", "missing.png"): [
                    ResourceUsageEntry("image", "missing.png", "main_page", "hero", "image_file", "image"),
                ]
            }
        )

        preview_calls = []
        apply_calls = []

        monkeypatch.setattr(
            "ui_designer.ui.resource_panel.QFileDialog.getOpenFileName",
            lambda *args, **kwargs: (str(replacement_path), "Images (*.png *.bmp *.jpg *.jpeg)"),
        )
        monkeypatch.setattr(
            panel,
            "_confirm_batch_replace_impact",
            lambda resource_type, impacts, total_rename_count: preview_calls.append((resource_type, impacts, total_rename_count)) or True,
        )
        monkeypatch.setattr(
            panel,
            "_replace_missing_resources_from_mapping",
            lambda resource_type, replacements: apply_calls.append((resource_type, replacements)) or ([], [], []),
        )

        panel._replace_missing_resource("missing.png", "image")

        assert len(preview_calls) == 1
        assert preview_calls[0][0] == "image"
        assert preview_calls[0][2] == 1
        assert preview_calls[0][1][0]["old_name"] == "missing.png"
        assert preview_calls[0][1][0]["new_name"] == "renamed.png"
        assert apply_calls == [("image", {"missing.png": str(replacement_path)})]
        panel.deleteLater()

    def test_replace_missing_resource_can_cancel_batch_impact_preview(self, qapp, tmp_path, monkeypatch):
        from ui_designer.model.resource_catalog import ResourceCatalog
        from ui_designer.model.resource_usage import ResourceUsageEntry
        from ui_designer.ui.resource_panel import ResourcePanel

        resource_dir = tmp_path / "project" / ".eguiproject" / "resources"
        images_dir = resource_dir / "images"
        images_dir.mkdir(parents=True)
        replacement_dir = tmp_path / "external_images"
        replacement_dir.mkdir()
        replacement_path = replacement_dir / "renamed.png"
        replacement_path.write_bytes(b"PNG")

        catalog = ResourceCatalog()
        catalog.add_image("missing.png")

        panel = ResourcePanel()
        panel.set_resource_dir(str(resource_dir))
        panel.set_resource_catalog(catalog)
        panel.set_resource_usage_index(
            {
                ("image", "missing.png"): [
                    ResourceUsageEntry("image", "missing.png", "main_page", "hero", "image_file", "image"),
                ]
            }
        )

        preview_calls = []

        monkeypatch.setattr(
            "ui_designer.ui.resource_panel.QFileDialog.getOpenFileName",
            lambda *args, **kwargs: (str(replacement_path), "Images (*.png *.bmp *.jpg *.jpeg)"),
        )
        monkeypatch.setattr(
            panel,
            "_confirm_batch_replace_impact",
            lambda resource_type, impacts, total_rename_count: preview_calls.append((resource_type, impacts, total_rename_count)) or False,
        )
        monkeypatch.setattr(
            panel,
            "_replace_missing_resources_from_mapping",
            lambda *args, **kwargs: pytest.fail("_replace_missing_resources_from_mapping should not be called"),
        )

        panel._replace_missing_resource("missing.png", "image")

        assert len(preview_calls) == 1
        panel.deleteLater()

    def test_rename_text_resource_updates_catalog_and_emits_signal(self, qapp, tmp_path, monkeypatch):
        from ui_designer.model.resource_catalog import ResourceCatalog
        from ui_designer.ui.resource_panel import ResourcePanel

        resource_dir = tmp_path / "project" / ".eguiproject" / "resources"
        resource_dir.mkdir(parents=True)
        old_path = resource_dir / "chars.txt"
        old_path.write_text("abc\n", encoding="utf-8")

        catalog = ResourceCatalog()
        catalog.add_text_file("chars.txt")

        panel = ResourcePanel()
        panel.set_resource_dir(str(resource_dir))
        panel.set_resource_catalog(catalog)

        renamed = []
        imported = []
        panel.resource_renamed.connect(lambda res_type, old, new: renamed.append((res_type, old, new)))
        panel.resource_imported.connect(lambda: imported.append(True))
        monkeypatch.setattr(
            "ui_designer.ui.resource_panel.QInputDialog.getText",
            lambda *args, **kwargs: ("chars_new.txt", True),
        )

        panel._rename_resource("chars.txt", "text")

        assert not old_path.exists()
        assert (resource_dir / "chars_new.txt").is_file()
        assert panel.get_resource_catalog().text_files == ["chars_new.txt"]
        assert renamed == [("text", "chars.txt", "chars_new.txt")]
        assert imported == [True]
        panel.deleteLater()

    def test_delete_text_resource_updates_catalog_and_emits_signal(self, qapp, tmp_path, monkeypatch):
        from ui_designer.model.resource_catalog import ResourceCatalog
        from ui_designer.ui.resource_panel import ResourcePanel

        resource_dir = tmp_path / "project" / ".eguiproject" / "resources"
        resource_dir.mkdir(parents=True)
        text_path = resource_dir / "chars.txt"
        text_path.write_text("abc\n", encoding="utf-8")

        catalog = ResourceCatalog()
        catalog.add_text_file("chars.txt")

        panel = ResourcePanel()
        panel.set_resource_dir(str(resource_dir))
        panel.set_resource_catalog(catalog)

        deleted = []
        imported = []
        panel.resource_deleted.connect(lambda res_type, filename: deleted.append((res_type, filename)))
        panel.resource_imported.connect(lambda: imported.append(True))
        monkeypatch.setattr("ui_designer.ui.resource_panel.QMessageBox.question", lambda *args, **kwargs: QMessageBox.Yes)

        panel._delete_resource("chars.txt", "text")

        assert not text_path.exists()
        assert panel.get_resource_catalog().text_files == []
        assert panel._text_list.count() == 0
        assert deleted == [("text", "chars.txt")]
        assert imported == [True]
        panel.deleteLater()

    def test_rename_text_resource_with_usages_uses_shared_impact_confirmation(self, qapp, tmp_path, monkeypatch):
        from ui_designer.model.resource_catalog import ResourceCatalog
        from ui_designer.model.resource_usage import ResourceUsageEntry
        from ui_designer.ui.resource_panel import ResourcePanel

        resource_dir = tmp_path / "project" / ".eguiproject" / "resources"
        resource_dir.mkdir(parents=True)
        old_path = resource_dir / "chars.txt"
        old_path.write_text("abc\n", encoding="utf-8")

        catalog = ResourceCatalog()
        catalog.add_text_file("chars.txt")

        panel = ResourcePanel()
        panel.set_resource_dir(str(resource_dir))
        panel.set_resource_catalog(catalog)
        panel.set_resource_usage_index(
            {
                ("text", "chars.txt"): [
                    ResourceUsageEntry("text", "chars.txt", "main_page", "title", "font_text_file", "label"),
                ]
            }
        )

        prompts = []
        monkeypatch.setattr(
            "ui_designer.ui.resource_panel.QInputDialog.getText",
            lambda *args, **kwargs: ("chars_new.txt", True),
        )
        monkeypatch.setattr(
            panel,
            "_confirm_reference_impact",
            lambda *args: prompts.append(args) or True,
        )

        panel._rename_resource("chars.txt", "text")

        assert prompts
        assert prompts[0][0] == "Rename Resource"
        assert prompts[0][1] == "chars.txt"
        assert len(prompts[0][2]) == 1
        assert "chars_new.txt" in prompts[0][4]
        assert not old_path.exists()
        assert (resource_dir / "chars_new.txt").is_file()
        panel.deleteLater()

    def test_delete_resource_with_usages_uses_shared_impact_confirmation(self, qapp, tmp_path, monkeypatch):
        from ui_designer.model.resource_catalog import ResourceCatalog
        from ui_designer.model.resource_usage import ResourceUsageEntry
        from ui_designer.ui.resource_panel import ResourcePanel

        resource_dir = tmp_path / "project" / ".eguiproject" / "resources"
        resource_dir.mkdir(parents=True)
        text_path = resource_dir / "chars.txt"
        text_path.write_text("abc\n", encoding="utf-8")

        catalog = ResourceCatalog()
        catalog.add_text_file("chars.txt")

        panel = ResourcePanel()
        panel.set_resource_dir(str(resource_dir))
        panel.set_resource_catalog(catalog)
        panel.set_resource_usage_index(
            {
                ("text", "chars.txt"): [
                    ResourceUsageEntry("text", "chars.txt", "main_page", "title", "font_text_file", "label"),
                ]
            }
        )

        prompts = []
        deleted = []
        monkeypatch.setattr(
            panel,
            "_confirm_reference_impact",
            lambda *args: prompts.append(args) or True,
        )
        panel.resource_deleted.connect(lambda res_type, filename: deleted.append((res_type, filename)))

        panel._delete_resource("chars.txt", "text")

        assert prompts
        assert prompts[0][0] == "Delete Resource"
        assert prompts[0][1] == "chars.txt"
        assert len(prompts[0][2]) == 1
        assert "clear those widget references" in prompts[0][4]
        assert deleted == [("text", "chars.txt")]
        assert not text_path.exists()
        panel.deleteLater()

    def test_reference_impact_confirmation_can_open_selected_usage(self, qapp):
        from ui_designer.model.resource_usage import ResourceUsageEntry
        from ui_designer.ui.resource_panel import ResourcePanel

        panel = ResourcePanel()
        activated = []
        panel.usage_activated.connect(lambda page_name, widget_name: activated.append((page_name, widget_name)))

        usages = [
            ResourceUsageEntry("string", "greeting", "detail_page", "subtitle", "text", "label"),
        ]

        def open_selected_usage():
            dialog = QApplication.activeModalWidget()
            assert dialog is not None
            dialog._open_selected_usage()

        QTimer.singleShot(0, open_selected_usage)
        confirmed = panel._confirm_reference_impact(
            "Remove String Key",
            "greeting",
            usages,
            "unused prompt",
            "Removing it will convert those references to literal text.",
            "Remove",
        )

        assert confirmed is False
        assert activated == [("detail_page", "subtitle")]
        panel.deleteLater()

    def test_generate_charset_dialog_updates_preview_and_overwrite_summary(self, qapp, tmp_path):
        from ui_designer.ui.resource_panel import _GenerateCharsetDialog

        resource_dir = tmp_path / "project" / ".eguiproject" / "resources"
        resource_dir.mkdir(parents=True)
        existing_path = resource_dir / "charset_ascii_printable.txt"
        existing_path.write_text("A\n", encoding="utf-8")

        dialog = _GenerateCharsetDialog(str(resource_dir))
        try:
            dialog._preset_checks["ascii_printable"].setChecked(True)

            assert dialog.filename() == "charset_ascii_printable.txt"
            assert len(dialog.generated_chars()) == 95
            assert dialog._char_metric.text() == "95 chars"
            assert "Overwrite existing file" in dialog._overwrite_summary.text()
            assert "Existing 1 chars" in dialog._overwrite_summary.text()
        finally:
            dialog.deleteLater()

    def test_generate_charset_dialog_exposes_accessibility_metadata(self, qapp, tmp_path):
        from ui_designer.ui.resource_panel import _GenerateCharsetDialog

        resource_dir = tmp_path / "project" / ".eguiproject" / "resources"
        resource_dir.mkdir(parents=True)

        dialog = _GenerateCharsetDialog(str(resource_dir))
        try:
            dialog._preset_checks["ascii_printable"].setChecked(True)
            dialog._custom_input.setPlainText("中")

            assert dialog.accessibleName().startswith("Generate Charset: 1 preset selected.")
            assert dialog._header_frame.accessibleName() == (
                "Font charset dialog header: 1 preset selected. 96 chars. File: charset_ascii_printable_custom.txt."
            )
            assert dialog._eyebrow_label.accessibleName() == "Font charset generation workspace."
            assert dialog._title_label.accessibleName() == "Font charset generator title: Generate Charset."
            assert dialog._subtitle_label.accessibleName() == dialog._subtitle_label.text()
            assert dialog._selection_metric.accessibleName() == "Resource dialog metric: Selection. 1 preset, custom input."
            assert dialog._char_metric.accessibleName() == "Resource dialog metric: Chars. 96 chars."
            assert dialog._file_metric.accessibleName() == (
                "Resource dialog metric: File. charset_ascii_printable_custom.txt."
            )
            assert dialog._custom_input.accessibleName() == "Custom charset input: 1 custom chars."
            assert dialog._filename_edit.accessibleName() == (
                "Charset output filename: charset_ascii_printable_custom.txt."
            )
            assert dialog._preview_box.accessibleName() == "Generated charset preview. Showing 96 line preview."
            assert dialog._save_button.toolTip() == "Save charset resource to charset_ascii_printable_custom.txt."
            assert dialog._save_button.accessibleName() == "Save charset resource"
            assert dialog._save_assign_button.accessibleName() == "Save charset resource and bind current widget"
            assert dialog._cancel_button.accessibleName() == "Cancel charset generation"
            assert dialog._custom_input.placeholderText() == "e.g. A&#x2103;&#x00B0;&#x4F60;&#x597D;"
        finally:
            dialog.deleteLater()

    def test_generate_charset_creates_text_resource_refreshes_panel_and_emits_signals(self, qapp, tmp_path, monkeypatch):
        from ui_designer.model.resource_catalog import ResourceCatalog
        from ui_designer.ui.resource_panel import ResourcePanel

        resource_dir = tmp_path / "project" / ".eguiproject" / "resources"
        resource_dir.mkdir(parents=True)

        panel = ResourcePanel()
        panel.set_resource_dir(str(resource_dir))
        panel.set_resource_catalog(ResourceCatalog())

        imported = []
        selected = []
        messages = []
        panel.resource_imported.connect(lambda: imported.append(True))
        panel.resource_selected.connect(lambda res_type, filename: selected.append((res_type, filename)))
        panel.feedback_message.connect(messages.append)

        class FakeDialog:
            def __init__(self, resource_dir_arg, initial_filename="", parent=None):
                assert resource_dir_arg == str(resource_dir)
                assert initial_filename == ""

            def exec_(self):
                return 1

            def filename(self):
                return "charset_combo.txt"

            def generated_chars(self):
                return tuple("AB中")

            def generated_text(self):
                return "A\nB\n&#x4E2D;\n"

            def generated_chars(self):
                return ("A", "B", "\u4E2D")

            def overwrite_diff(self):
                return SimpleNamespace(existing_count=0, new_count=3, added_count=3, removed_count=0)

            def save_and_assign(self):
                return True

        monkeypatch.setattr("ui_designer.ui.resource_panel._GenerateCharsetDialog", FakeDialog)

        panel._on_generate_charset()

        assert (resource_dir / "charset_combo.txt").read_text(encoding="utf-8") == "A\nB\n&#x4E2D;\n"
        assert panel.get_resource_catalog().text_files == ["charset_combo.txt"]
        assert panel._tabs.currentIndex() == 2
        assert panel._text_list.currentItem().data(Qt.UserRole + 1) == "charset_combo.txt"
        assert imported == [True]
        assert selected == [("text", "charset_combo.txt")]
        assert messages == ["Generated and assigned text resource 'charset_combo.txt' with 3 chars."]
        panel.deleteLater()

    def test_generate_charset_requires_confirmation_before_overwriting_existing_file(self, qapp, tmp_path, monkeypatch):
        from ui_designer.model.resource_catalog import ResourceCatalog
        from ui_designer.ui.resource_panel import ResourcePanel

        resource_dir = tmp_path / "project" / ".eguiproject" / "resources"
        resource_dir.mkdir(parents=True)
        existing_path = resource_dir / "charset_ascii_printable.txt"
        existing_path.write_text("A\n", encoding="utf-8")

        catalog = ResourceCatalog()
        catalog.add_text_file("charset_ascii_printable.txt")

        panel = ResourcePanel()
        panel.set_resource_dir(str(resource_dir))
        panel.set_resource_catalog(catalog)

        imported = []
        panel.resource_imported.connect(lambda: imported.append(True))

        class FakeDialog:
            def __init__(self, resource_dir_arg, initial_filename="", parent=None):
                assert resource_dir_arg == str(resource_dir)
                assert initial_filename == ""

            def exec_(self):
                return 1

            def filename(self):
                return "charset_ascii_printable.txt"

            def generated_chars(self):
                return tuple("AB")

            def generated_text(self):
                return "A\nB\n"

            def overwrite_diff(self):
                return SimpleNamespace(existing_count=1, new_count=2, added_count=1, removed_count=0)

            def save_and_assign(self):
                return False

        monkeypatch.setattr("ui_designer.ui.resource_panel._GenerateCharsetDialog", FakeDialog)
        monkeypatch.setattr("ui_designer.ui.resource_panel.QMessageBox.question", lambda *args, **kwargs: QMessageBox.No)

        panel._on_generate_charset()

        assert existing_path.read_text(encoding="utf-8") == "A\n"
        assert imported == []
        panel.deleteLater()

    def test_generate_charset_prefills_selected_text_filename_from_text_tab(self, qapp, tmp_path, monkeypatch):
        from ui_designer.model.resource_catalog import ResourceCatalog
        from ui_designer.ui.resource_panel import ResourcePanel

        resource_dir = tmp_path / "project" / ".eguiproject" / "resources"
        resource_dir.mkdir(parents=True)
        text_path = resource_dir / "charset_existing.txt"
        text_path.write_text("A\n", encoding="utf-8")

        catalog = ResourceCatalog()
        catalog.add_text_file("charset_existing.txt")

        panel = ResourcePanel()
        panel.set_resource_dir(str(resource_dir))
        panel.set_resource_catalog(catalog)
        panel._select_resource_item("text", "charset_existing.txt")

        captured = {}

        class FakeDialog:
            def __init__(self, resource_dir_arg, initial_filename="", parent=None):
                captured["resource_dir"] = resource_dir_arg
                captured["initial_filename"] = initial_filename

            def exec_(self):
                return 0

        monkeypatch.setattr("ui_designer.ui.resource_panel._GenerateCharsetDialog", FakeDialog)

        panel._on_generate_charset()

        assert captured == {
            "resource_dir": str(resource_dir),
            "initial_filename": "charset_existing.txt",
        }
        panel.deleteLater()

    def test_generate_charset_prefills_suggested_filename_from_selected_font_tab(self, qapp, tmp_path, monkeypatch):
        from ui_designer.model.resource_catalog import ResourceCatalog
        from ui_designer.ui.resource_panel import ResourcePanel

        resource_dir = tmp_path / "project" / ".eguiproject" / "resources"
        resource_dir.mkdir(parents=True)
        font_path = resource_dir / "demo_font.ttf"
        font_path.write_bytes(b"FONT")

        catalog = ResourceCatalog()
        catalog.add_font("demo_font.ttf")

        panel = ResourcePanel()
        panel.set_resource_dir(str(resource_dir))
        panel.set_resource_catalog(catalog)
        panel._select_resource_item("font", "demo_font.ttf")

        captured = {}

        class FakeDialog:
            def __init__(self, resource_dir_arg, initial_filename="", parent=None):
                captured["resource_dir"] = resource_dir_arg
                captured["initial_filename"] = initial_filename

            def exec_(self):
                return 0

        monkeypatch.setattr("ui_designer.ui.resource_panel._GenerateCharsetDialog", FakeDialog)

        panel._on_generate_charset()

        assert captured == {
            "resource_dir": str(resource_dir),
            "initial_filename": "demo_font_charset.txt",
        }
        panel.deleteLater()
