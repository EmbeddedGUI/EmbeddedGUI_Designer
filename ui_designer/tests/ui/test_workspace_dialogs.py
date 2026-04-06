"""Qt UI tests for workspace-related dialogs and welcome page."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QApplication, QFrame, QLabel, QWidget
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


@pytest.fixture(autouse=True)
def bind_ui_config(isolated_config, monkeypatch):
    import ui_designer.ui.app_selector as app_selector_module
    import ui_designer.ui.new_project_dialog as new_project_dialog_module
    import ui_designer.ui.welcome_page as welcome_page_module

    monkeypatch.setattr(app_selector_module, "get_config", lambda: isolated_config)
    monkeypatch.setattr(new_project_dialog_module, "get_config", lambda: isolated_config)
    monkeypatch.setattr(welcome_page_module, "get_config", lambda: isolated_config)


def _create_sdk_root(root):
    (root / "src").mkdir(parents=True)
    (root / "porting" / "designer").mkdir(parents=True)
    (root / "Makefile").write_text("all:\n")


def _mark_bundled_sdk(root):
    (root / ".designer_sdk_bundle.json").write_text('{"source_root": "D:/sdk/EmbeddedGUI"}\n', encoding="utf-8")


def _find_label_by_text(root, text):
    for label in root.findChildren(QLabel):
        if label.text() == text:
            return label
    raise AssertionError(f"Label not found: {text}")


@_skip_no_qt
class TestAppSelectorDialog:
    def test_refresh_app_list_does_not_leave_stale_row_widgets_attached(self, qapp, isolated_config, tmp_path):
        from ui_designer.ui.app_selector import AppEntryRowWidget, AppSelectorDialog

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        modern_dir = sdk_root / "example" / "HelloModern"
        modern_dir.mkdir(parents=True)
        (modern_dir / "build.mk").write_text("all:\n", encoding="utf-8")
        (modern_dir / "HelloModern.egui").write_text("<project />", encoding="utf-8")

        dialog = AppSelectorDialog(egui_root=str(sdk_root))
        initial_count = len(dialog.findChildren(AppEntryRowWidget))

        dialog._search_edit.setText("HelloModern")
        filtered_count = len(dialog.findChildren(AppEntryRowWidget))

        dialog._search_edit.setText("")
        restored_count = len(dialog.findChildren(AppEntryRowWidget))

        assert initial_count == 1
        assert filtered_count == 1
        assert restored_count == 1
        assert dialog._app_list.item(0).sizeHint().height() >= 28
        dialog.deleteLater()

    def test_header_exposes_sdk_example_workspace_metadata(self, qapp, isolated_config):
        from ui_designer.ui.app_selector import AppSelectorDialog

        isolated_config.sdk_root = ""
        isolated_config.egui_root = ""
        dialog = AppSelectorDialog(egui_root="")

        assert dialog._header_frame.accessibleName() == (
            "SDK example header. Open SDK Example dialog: SDK root none. Search none. "
            "Legacy examples off. Examples list: 1 entry. Selection: none."
        )
        assert dialog._eyebrow_label.isHidden()
        assert dialog._subtitle_label.isHidden()
        assert dialog._metrics_frame.isHidden()
        assert dialog._eyebrow_label.accessibleName() == "SDK example browser workspace."
        assert dialog._title_label.text() == "Open Example"
        assert dialog._title_label.accessibleName() == "SDK example browser title: Open EmbeddedGUI SDK Example."
        assert dialog._subtitle_label.accessibleName() == dialog._subtitle_label.text()
        assert dialog._root_metric_value.accessibleName() == (
            f"App selector metric: SDK Status. {dialog._root_metric_value.text()}."
        )
        assert dialog._root_metric_value.toolTip() == f"SDK Status: {dialog._root_metric_value.text()}."
        assert dialog._root_metric_value._app_selector_metric_label.accessibleName() == "SDK Status metric label."
        assert dialog._root_metric_value._app_selector_metric_card.accessibleName() == (
            f"SDK Status metric: {dialog._root_metric_value.text()}."
        )
        assert dialog._results_metric_value.accessibleName() == (
            f"App selector metric: Visible Examples. {dialog._results_metric_value.text()}."
        )
        assert dialog._selection_metric_value.accessibleName() == (
            f"App selector metric: Action. {dialog._selection_metric_value.text()}."
        )
        assert _find_label_by_text(
            dialog,
            "Examples come from the current SDK workspace. Switch roots here when you need a different application catalog.",
        ).isHidden()
        assert _find_label_by_text(
            dialog,
            "Keep the browser focused on Designer-ready projects, or widen the list to include legacy apps that still need import.",
        ).isHidden()
        assert _find_label_by_text(
            dialog,
            "Search by app name and use the list below as the single entry point into existing SDK projects.",
        ).isHidden()
        assert _find_label_by_text(
            dialog,
            "Review the selected example path and import mode before opening it in the workspace.",
        ).isHidden()
        assert _find_label_by_text(dialog, "SDK") is not None
        assert _find_label_by_text(dialog, "Filters") is not None
        assert _find_label_by_text(dialog, "Examples") is not None
        assert dialog._show_legacy.text() == "Show legacy"
        assert dialog._download_btn.text() == "Download..."
        assert dialog._search_edit.placeholderText() == "Search examples..."
        assert len(dialog.findChildren(QFrame, "app_selector_metric_card")) == 3
        dialog.deleteLater()

    def test_exposes_accessibility_metadata_when_sdk_root_is_missing(self, qapp, isolated_config):
        from ui_designer.ui.app_selector import AppSelectorDialog

        isolated_config.sdk_root = ""
        isolated_config.egui_root = ""
        dialog = AppSelectorDialog(egui_root="")

        assert dialog.accessibleName() == (
            "Open SDK Example dialog: SDK root none. Search none. "
            "Legacy examples off. Examples list: 1 entry. Selection: none."
        )
        assert dialog._search_edit.toolTip() == "Filter SDK examples by name. Current search: none."
        assert dialog._app_list.accessibleName() == "SDK examples list: 1 entry. Current selection: none."
        assert dialog._open_btn.toolTip() == "Select an SDK example to open it."
        assert dialog._open_btn.accessibleName() == (
            "Open action unavailable: Open. Select an SDK example to open it."
        )
        assert dialog._browse_btn.icon().isNull()
        assert dialog._download_btn.toolTip() == (
            "Download SDK unavailable because this dialog was opened without an SDK download handler."
        )
        assert dialog._download_btn.statusTip() == dialog._download_btn.toolTip()
        assert dialog._download_btn.accessibleName() == (
            "Download SDK unavailable. "
            "Download SDK unavailable because this dialog was opened without an SDK download handler."
        )
        assert dialog._download_btn.icon().isNull()
        assert dialog._show_legacy.accessibleName() == "Show legacy SDK examples: off"
        assert dialog._root_status_label.accessibleName() == f"SDK root status: {dialog._root_status_label.text()}"
        assert dialog._app_list.item(0).data(Qt.AccessibleTextRole) == (
            "SDK examples list item: Set or download an SDK root first."
        )
        dialog.deleteLater()

    def test_header_frame_hint_skips_no_op_rewrites(self, qapp, isolated_config, monkeypatch):
        from ui_designer.ui.app_selector import AppSelectorDialog

        isolated_config.sdk_root = ""
        isolated_config.egui_root = ""
        dialog = AppSelectorDialog(egui_root="")
        dialog._header_frame.setProperty("_app_selector_hint_snapshot", None)

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

        dialog._search_edit.blockSignals(True)
        dialog._search_edit.setText("show")
        dialog._search_edit.blockSignals(False)
        dialog._update_accessibility_summary()
        assert hint_calls == 2
        dialog.deleteLater()

    def test_header_frame_accessible_name_skips_no_op_rewrites(self, qapp, isolated_config, monkeypatch):
        from ui_designer.ui.app_selector import AppSelectorDialog

        isolated_config.sdk_root = ""
        isolated_config.egui_root = ""
        dialog = AppSelectorDialog(egui_root="")
        dialog._header_frame.setProperty("_app_selector_accessible_snapshot", None)

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

        dialog._search_edit.blockSignals(True)
        dialog._search_edit.setText("show")
        dialog._search_edit.blockSignals(False)
        dialog._update_accessibility_summary()
        assert accessible_calls == 2
        dialog.deleteLater()

    def test_filters_legacy_examples_by_default(self, qapp, isolated_config, tmp_path):
        from ui_designer.ui.app_selector import AppSelectorDialog

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        example_dir = sdk_root / "example"
        example_dir.mkdir()

        modern = example_dir / "ModernApp"
        modern.mkdir()
        (modern / "build.mk").write_text("")
        (modern / "ModernApp.egui").write_text("")

        legacy = example_dir / "LegacyApp"
        legacy.mkdir()
        (legacy / "build.mk").write_text("")

        isolated_config.sdk_root = str(sdk_root)
        isolated_config.last_app = "ModernApp"
        isolated_config.show_all_examples = False

        dialog = AppSelectorDialog(egui_root=str(sdk_root))
        assert dialog._app_list.count() == 1
        assert dialog._app_list.item(0).text() == "ModernApp"
        assert dialog._app_list.currentItem().text() == "ModernApp"
        modern_widget = dialog._app_list.itemWidget(dialog._app_list.item(0))
        modern_path_label = modern_widget.findChild(QLabel, "app_selector_item_meta")
        modern_kind_label = modern_widget.findChild(QLabel, "app_selector_item_kind")
        assert modern_widget.findChild(QFrame, "app_selector_item_icon_shell") is None
        assert modern_path_label.isHidden()
        assert "ModernApp.egui" in modern_path_label.accessibleName()
        assert modern_kind_label.isHidden()
        assert modern_kind_label.accessibleName() == "SDK example kind: Designer Project"
        dialog.deleteLater()

    def test_shows_placeholder_when_sdk_root_missing(self, qapp, isolated_config):
        from ui_designer.ui.app_selector import AppSelectorDialog

        isolated_config.sdk_root = ""
        isolated_config.egui_root = ""
        dialog = AppSelectorDialog(egui_root="")

        assert dialog._app_list.count() == 1
        assert dialog._app_list.item(0).text() == "(Set or download an SDK root first)"
        assert "Missing" in dialog._root_status_label.text()
        assert "GitHub archive" in dialog._root_status_label.text()
        assert dialog._open_btn.isEnabled() is False
        dialog.deleteLater()

    def test_shows_invalid_placeholder_when_sdk_root_is_invalid(self, qapp, isolated_config, tmp_path):
        from ui_designer.ui.app_selector import AppSelectorDialog

        isolated_config.sdk_root = ""
        isolated_config.egui_root = ""
        dialog = AppSelectorDialog(egui_root=str(tmp_path / "not_sdk"))

        assert dialog._app_list.count() == 1
        assert dialog._app_list.item(0).text() == "(Current SDK root is invalid)"
        assert "Invalid" in dialog._root_status_label.text()
        assert dialog._open_btn.isEnabled() is False
        assert dialog._app_list.item(0).data(Qt.AccessibleTextRole) == (
            "SDK examples list item: Current SDK root is invalid."
        )
        dialog.deleteLater()

    def test_toggle_legacy_updates_list_and_config(self, qapp, isolated_config, tmp_path):
        from ui_designer.ui.app_selector import AppSelectorDialog

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        example_dir = sdk_root / "example"
        example_dir.mkdir()

        modern = example_dir / "ModernApp"
        modern.mkdir()
        (modern / "build.mk").write_text("")
        (modern / "ModernApp.egui").write_text("")

        legacy = example_dir / "LegacyApp"
        legacy.mkdir()
        (legacy / "build.mk").write_text("")

        isolated_config.sdk_root = str(sdk_root)
        dialog = AppSelectorDialog(egui_root=str(sdk_root))
        dialog._show_legacy.setChecked(True)

        assert isolated_config.show_all_examples is True
        assert dialog._app_list.count() == 2
        assert dialog._show_legacy.toolTip() == (
            "Showing legacy SDK examples that do not yet have Designer project files."
        )
        assert dialog._show_legacy.accessibleName() == "Show legacy SDK examples: on"
        texts = [dialog._app_list.item(i).text() for i in range(dialog._app_list.count())]
        assert "LegacyApp [Legacy]" in texts
        legacy_item = next(
            dialog._app_list.item(i)
            for i in range(dialog._app_list.count())
            if dialog._app_list.item(i).text() == "LegacyApp [Legacy]"
        )
        assert legacy_item.data(Qt.AccessibleTextRole) == (
            f"SDK example: LegacyApp [Legacy]. Legacy example path: {legacy}. "
            "Opening it will initialize a Designer project."
        )
        legacy_widget = dialog._app_list.itemWidget(legacy_item)
        legacy_path_label = legacy_widget.findChild(QLabel, "app_selector_item_meta")
        legacy_kind_label = legacy_widget.findChild(QLabel, "app_selector_item_kind")
        assert legacy_widget.findChild(QFrame, "app_selector_item_icon_shell") is None
        assert legacy_path_label.isHidden()
        assert legacy_path_label.accessibleName().startswith("SDK example path: ")
        assert "LegacyApp" in legacy_path_label.accessibleName()
        assert legacy_kind_label.isHidden()
        assert legacy_kind_label.accessibleName() == "SDK example kind: Legacy Import"
        dialog.deleteLater()

    def test_selection_updates_selected_entry_and_enables_open(self, qapp, isolated_config, tmp_path):
        from ui_designer.ui.app_selector import AppSelectorDialog

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        example_dir = sdk_root / "example"
        example_dir.mkdir()

        modern = example_dir / "ModernApp"
        modern.mkdir()
        (modern / "build.mk").write_text("")
        (modern / "ModernApp.egui").write_text("")

        isolated_config.sdk_root = str(sdk_root)
        dialog = AppSelectorDialog(egui_root=str(sdk_root))
        dialog._app_list.setCurrentRow(0)

        assert dialog.selected_entry["app_name"] == "ModernApp"
        assert dialog._open_btn.isEnabled() is True
        dialog.deleteLater()

    def test_browse_root_auto_resolves_parent_directory(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.app_selector import AppSelectorDialog

        sdk_parent = tmp_path / "tools"
        sdk_root = sdk_parent / "EmbeddedGUI-main"
        _create_sdk_root(sdk_root)
        (sdk_root / "example").mkdir()

        dialog = AppSelectorDialog(egui_root="")
        monkeypatch.setattr("ui_designer.ui.app_selector.QFileDialog.getExistingDirectory", lambda *args, **kwargs: str(sdk_parent))

        dialog._browse_root()

        assert dialog.egui_root == os.path.normpath(os.path.abspath(sdk_root))
        assert dialog._root_edit.text() == os.path.normpath(os.path.abspath(sdk_root))
        dialog.deleteLater()

    def test_search_filters_examples_by_name(self, qapp, isolated_config, tmp_path):
        from ui_designer.ui.app_selector import AppSelectorDialog

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        example_dir = sdk_root / "example"
        example_dir.mkdir()

        for name in ("HelloVirtual", "HelloShowcase", "HelloSimple"):
            app_dir = example_dir / name
            app_dir.mkdir()
            (app_dir / "build.mk").write_text("")
            (app_dir / f"{name}.egui").write_text("")

        isolated_config.sdk_root = str(sdk_root)
        dialog = AppSelectorDialog(egui_root=str(sdk_root))
        dialog._search_edit.setText("show")

        assert dialog._app_list.count() == 1
        assert dialog._app_list.item(0).text() == "HelloShowcase"
        assert dialog.selected_entry["app_name"] == "HelloShowcase"
        dialog.deleteLater()

    def test_search_shows_empty_state_when_no_example_matches(self, qapp, isolated_config, tmp_path):
        from ui_designer.ui.app_selector import AppSelectorDialog

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        example_dir = sdk_root / "example"
        example_dir.mkdir()

        app_dir = example_dir / "HelloVirtual"
        app_dir.mkdir()
        (app_dir / "build.mk").write_text("")
        (app_dir / "HelloVirtual.egui").write_text("")

        isolated_config.sdk_root = str(sdk_root)
        dialog = AppSelectorDialog(egui_root=str(sdk_root))
        dialog._search_edit.setText("missing")

        assert dialog._app_list.count() == 1
        assert dialog._app_list.item(0).text() == "(No matching examples)"
        assert dialog._open_btn.isEnabled() is False
        assert dialog.selected_entry is None
        dialog.deleteLater()

    def test_double_click_placeholder_item_does_not_accept_dialog(self, qapp, isolated_config, tmp_path):
        from ui_designer.ui.app_selector import AppSelectorDialog

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        (sdk_root / "example").mkdir()

        dialog = AppSelectorDialog(egui_root=str(sdk_root))
        placeholder_item = dialog._app_list.item(0)
        accepted = []
        dialog.accept = lambda: accepted.append(True)

        dialog._on_item_double_clicked(placeholder_item)

        assert placeholder_item.text() == "(No SDK examples found)"
        assert accepted == []
        assert dialog.selected_entry is None
        dialog.deleteLater()

    def test_shows_empty_state_when_sdk_has_no_examples(self, qapp, isolated_config, tmp_path):
        from ui_designer.ui.app_selector import AppSelectorDialog

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        (sdk_root / "example").mkdir()

        dialog = AppSelectorDialog(egui_root=str(sdk_root))

        assert dialog._app_list.count() == 1
        assert dialog._app_list.item(0).text() == "(No SDK examples found)"
        assert dialog._open_btn.isEnabled() is False
        dialog.deleteLater()

    def test_legacy_selection_updates_open_button_and_hint(self, qapp, isolated_config, tmp_path):
        from ui_designer.ui.app_selector import AppSelectorDialog

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        example_dir = sdk_root / "example"
        example_dir.mkdir()

        modern = example_dir / "ModernApp"
        modern.mkdir()
        (modern / "build.mk").write_text("")
        (modern / "ModernApp.egui").write_text("")

        legacy = example_dir / "LegacyApp"
        legacy.mkdir()
        (legacy / "build.mk").write_text("")

        dialog = AppSelectorDialog(egui_root=str(sdk_root))
        dialog._show_legacy.setChecked(True)

        for index in range(dialog._app_list.count()):
            if dialog._app_list.item(index).text() == "LegacyApp [Legacy]":
                dialog._app_list.setCurrentRow(index)
                break

        assert dialog.selected_entry["app_name"] == "LegacyApp"
        assert dialog._open_btn.text() == "Import"
        assert dialog._open_btn.toolTip() == "Import the selected legacy example into a Designer project."
        assert dialog._open_btn.accessibleName() == (
            "Open action: Import. Import the selected legacy example into a Designer project."
        )
        assert "initialize a Designer project" in dialog._selection_hint_label.text()
        assert str(legacy) in dialog._selection_hint_label.text()
        dialog.deleteLater()

    def test_download_sdk_callback_updates_root_and_examples(self, qapp, isolated_config, tmp_path):
        from ui_designer.ui.app_selector import AppSelectorDialog

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        example_dir = sdk_root / "example"
        example_dir.mkdir()
        app_dir = example_dir / "HelloVirtual"
        app_dir.mkdir()
        (app_dir / "build.mk").write_text("")
        (app_dir / "HelloVirtual.egui").write_text("")

        dialog = AppSelectorDialog(egui_root="", on_download_sdk=lambda: str(sdk_root))

        assert "GitHub archive" in dialog._download_btn.toolTip()
        assert dialog._download_btn.statusTip() == dialog._download_btn.toolTip()
        assert dialog._download_btn.accessibleName() == f"Download SDK. {dialog._download_btn.toolTip()}"
        assert dialog._download_btn.icon().isNull()
        dialog._download_btn.click()

        assert dialog.egui_root == os.path.normpath(os.path.abspath(sdk_root))
        assert dialog._root_edit.text() == os.path.normpath(os.path.abspath(sdk_root))
        assert dialog._app_list.count() == 1
        assert dialog._app_list.item(0).text() == "HelloVirtual"
        assert dialog._app_list.item(0).data(Qt.AccessibleTextRole) == (
            f"SDK example: HelloVirtual. Project path: {app_dir / 'HelloVirtual.egui'}"
        )
        assert "Ready" in dialog._root_status_label.text()
        dialog.deleteLater()

    def test_shows_bundled_sdk_status_when_using_runtime_sdk(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.app_selector import AppSelectorDialog

        runtime_dir = tmp_path / "EmbeddedGUI-Designer"
        sdk_root = runtime_dir / "sdk" / "EmbeddedGUI"
        _create_sdk_root(sdk_root)
        _mark_bundled_sdk(sdk_root)
        (sdk_root / "example").mkdir()

        monkeypatch.setattr("ui_designer.ui.app_selector.default_sdk_install_dir", lambda: str(sdk_root))
        monkeypatch.setattr("ui_designer.model.sdk_bootstrap.sys.frozen", True, raising=False)
        monkeypatch.setattr("ui_designer.model.sdk_bootstrap.sys.executable", str(runtime_dir / "EmbeddedGUI-Designer.exe"))

        dialog = AppSelectorDialog(egui_root=str(sdk_root))

        assert "bundled SDK" in dialog._root_status_label.text()
        assert "switch to another SDK root" in dialog._root_status_label.text()
        dialog.deleteLater()

    def test_uses_default_sdk_cache_when_configured_root_is_missing(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.app_selector import AppSelectorDialog

        sdk_root = tmp_path / "config" / "sdk" / "EmbeddedGUI"
        _create_sdk_root(sdk_root)
        example_dir = sdk_root / "example"
        example_dir.mkdir()
        app_dir = example_dir / "HelloShowcase"
        app_dir.mkdir()
        (app_dir / "build.mk").write_text("")
        (app_dir / "HelloShowcase.egui").write_text("")

        isolated_config.sdk_root = str(tmp_path / "missing_sdk")
        isolated_config.egui_root = str(tmp_path / "missing_sdk")
        monkeypatch.setattr("ui_designer.model.sdk_bootstrap._get_config_dir", lambda: str(tmp_path / "config"))

        dialog = AppSelectorDialog(egui_root="")

        assert dialog.egui_root == os.path.normpath(os.path.abspath(sdk_root))
        assert dialog._root_edit.text() == os.path.normpath(os.path.abspath(sdk_root))
        assert dialog._app_list.count() == 1
        assert dialog._app_list.item(0).text() == "HelloShowcase"
        assert "auto-downloaded SDK cache" in dialog._root_status_label.text()
        dialog.deleteLater()


@_skip_no_qt
class TestNewProjectDialog:
    def test_header_exposes_new_project_workspace_metadata(self, qapp, isolated_config, tmp_path):
        from ui_designer.ui.new_project_dialog import NewProjectDialog

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("ui_designer.ui.new_project_dialog.default_sdk_install_dir", lambda: "")
            dialog = NewProjectDialog(sdk_root="", default_parent_dir=str(tmp_path))

        normalized_parent = os.path.normpath(os.path.abspath(tmp_path))
        assert dialog._header_frame.accessibleName() == (
            f"New project header. New Project dialog: SDK root none. Parent directory {normalized_parent}. "
            "App name none. Size 240 by 320."
        )
        assert dialog._eyebrow_label.isHidden()
        assert dialog._subtitle_label.isHidden()
        assert dialog._eyebrow_label.accessibleName() == "New project scaffold workspace."
        assert dialog._title_label.accessibleName() == "New project dialog title: Create EmbeddedGUI App."
        assert dialog._subtitle_label.accessibleName() == dialog._subtitle_label.text()
        assert dialog._metrics_frame.isHidden()
        assert dialog._sdk_metric_value.accessibleName() == (
            f"New project metric: Preview Mode. {dialog._sdk_metric_value.text()}."
        )
        assert dialog._sdk_metric_value._new_project_metric_label.accessibleName() == "Preview Mode metric label."
        assert dialog._sdk_metric_value._new_project_metric_card.accessibleName() == (
            f"Preview Mode metric: {dialog._sdk_metric_value.text()}."
        )
        assert dialog._location_metric_value.accessibleName() == (
            f"New project metric: Parent Directory. {normalized_parent}."
        )
        assert dialog._canvas_metric_value.accessibleName() == (
            f"New project metric: Canvas. {dialog._canvas_metric_value.text()}."
        )
        assert _find_label_by_text(
            dialog,
            "Attach an SDK if you want compile-backed preview from the first project open.",
        ).isHidden()
        assert _find_label_by_text(
            dialog,
            "Start with an explicit app name and target canvas size.",
        ).isHidden()
        assert _find_label_by_text(
            dialog,
            "Review where the project lands and whether the current configuration is ready.",
        ).isHidden()
        assert len(dialog.findChildren(QFrame, "new_project_metric_card")) == 3
        dialog.deleteLater()

    def test_exposes_accessibility_metadata_and_updates_with_form_values(self, qapp, isolated_config, tmp_path):
        from ui_designer.ui.new_project_dialog import NewProjectDialog

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("ui_designer.ui.new_project_dialog.default_sdk_install_dir", lambda: "")
            dialog = NewProjectDialog(sdk_root="", default_parent_dir=str(tmp_path))

        normalized_parent = os.path.normpath(os.path.abspath(tmp_path))
        assert dialog.accessibleName() == (
            f"New Project dialog: SDK root none. Parent directory {normalized_parent}. "
            "App name none. Size 240 by 320."
        )
        assert dialog._sdk_browse_btn.toolTip() == "Browse to an EmbeddedGUI SDK root."
        assert dialog._sdk_browse_btn.icon().isNull()
        assert dialog._sdk_clear_btn.icon().isNull()
        assert dialog._parent_browse_btn.icon().isNull()
        assert dialog._parent_edit.accessibleName() == f"Project parent directory: {normalized_parent}"

        dialog._app_name_edit.setText("DemoApp")
        dialog._width_spin.setValue(320)
        dialog._height_spin.setValue(240)

        assert dialog._app_name_edit.accessibleName() == "Application name: DemoApp"
        assert dialog._width_spin.accessibleName() == "Project width: 320"
        assert dialog._height_spin.accessibleName() == "Project height: 240"
        assert dialog.accessibleName() == (
            f"New Project dialog: SDK root none. Parent directory {normalized_parent}. "
            "App name DemoApp. Size 320 by 240."
        )
        assert dialog._sdk_clear_btn.toolTip() == (
            "SDK root is already empty. The project will use editing-only mode until you set an SDK."
        )
        assert dialog._sdk_clear_btn.accessibleName() == (
            "Clear SDK root unavailable. SDK root is already empty. "
            "The project will use editing-only mode until you set an SDK."
        )
        assert dialog._create_btn.toolTip() == (
            f"Create project DemoApp in {normalized_parent} at 320 by 240."
        )
        assert dialog._create_btn.accessibleName() == (
            f"Create project: DemoApp. Create project DemoApp in {normalized_parent} at 320 by 240."
        )
        assert dialog._create_btn.icon().isNull()
        dialog.deleteLater()

    def test_header_frame_hint_skips_no_op_rewrites(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.new_project_dialog import NewProjectDialog

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("ui_designer.ui.new_project_dialog.default_sdk_install_dir", lambda: "")
            dialog = NewProjectDialog(sdk_root="", default_parent_dir=str(tmp_path))
        dialog._header_frame.setProperty("_new_project_hint_snapshot", None)

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

        dialog._app_name_edit.setText("DemoApp")
        assert hint_calls == 2
        dialog.deleteLater()

    def test_header_frame_accessible_name_skips_no_op_rewrites(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.new_project_dialog import NewProjectDialog

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("ui_designer.ui.new_project_dialog.default_sdk_install_dir", lambda: "")
            dialog = NewProjectDialog(sdk_root="", default_parent_dir=str(tmp_path))
        dialog._header_frame.setProperty("_new_project_accessible_snapshot", None)

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

        dialog._app_name_edit.setText("DemoApp")
        assert accessible_calls == 2
        dialog.deleteLater()

    def test_create_button_reports_missing_fields_and_invalid_name(self, qapp, isolated_config, tmp_path):
        from ui_designer.ui.new_project_dialog import NewProjectDialog

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("ui_designer.ui.new_project_dialog.default_sdk_install_dir", lambda: "")
            dialog = NewProjectDialog(sdk_root="", default_parent_dir="")

        assert dialog._create_btn.toolTip() == "Select a parent directory before creating the project."
        assert dialog._create_btn.accessibleName() == (
            "Create project unavailable. Select a parent directory before creating the project."
        )

        dialog._parent_dir = os.path.normpath(os.path.abspath(tmp_path))
        dialog._parent_edit.setText(dialog._parent_dir)
        dialog._update_accessibility_summary()
        assert dialog._create_btn.toolTip() == "Enter an application name before creating the project."

        dialog._app_name_edit.setText("bad name!")
        assert dialog._create_btn.toolTip() == (
            "Application name must use letters, numbers, and underscores before the project can be created."
        )
        assert dialog._create_btn.accessibleName() == (
            "Create project unavailable. Application name must use letters, numbers, and underscores before the project can be created."
        )
        dialog.deleteLater()

    def test_create_button_reports_invalid_sdk_root_before_submit(self, qapp, isolated_config, tmp_path):
        from ui_designer.ui.new_project_dialog import NewProjectDialog

        dialog = NewProjectDialog(sdk_root=str(tmp_path / "invalid_sdk"), default_parent_dir=str(tmp_path))
        dialog._app_name_edit.setText("DemoApp")

        assert dialog._create_btn.toolTip() == (
            "Select a valid EmbeddedGUI SDK root or clear it before creating the project."
        )
        assert dialog._create_btn.accessibleName() == (
            "Create project unavailable. Select a valid EmbeddedGUI SDK root or clear it before creating the project."
        )
        dialog.deleteLater()

    def test_accept_requires_parent_directory(self, qapp, isolated_config):
        from ui_designer.ui.new_project_dialog import NewProjectDialog

        warnings = []
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("ui_designer.ui.new_project_dialog.default_sdk_install_dir", lambda: "")
            dialog = NewProjectDialog(sdk_root="", default_parent_dir="")
        dialog._app_name_edit.setText("DemoApp")

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("ui_designer.ui.new_project_dialog.QMessageBox.warning", lambda *args: warnings.append(args[1:]))
            dialog._accept_if_valid()

        assert dialog.result() == 0
        assert warnings
        assert warnings[0][0] == "Parent Directory"
        dialog.deleteLater()

    def test_accept_succeeds_without_sdk_root(self, qapp, isolated_config, tmp_path):
        from ui_designer.ui.new_project_dialog import NewProjectDialog

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("ui_designer.ui.new_project_dialog.default_sdk_install_dir", lambda: "")
            dialog = NewProjectDialog(sdk_root="", default_parent_dir=str(tmp_path))
        dialog._app_name_edit.setText("DemoApp")
        dialog._accept_if_valid()

        assert dialog.result() == dialog.Accepted
        assert dialog.sdk_root == ""
        assert dialog.parent_dir == os.path.normpath(os.path.abspath(tmp_path))
        dialog.deleteLater()

    def test_accept_requires_valid_app_name(self, qapp, isolated_config, tmp_path):
        from ui_designer.ui.new_project_dialog import NewProjectDialog

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        warnings = []
        dialog = NewProjectDialog(sdk_root=str(sdk_root), default_parent_dir=str(tmp_path))
        dialog._app_name_edit.setText("bad name!")

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("ui_designer.ui.new_project_dialog.QMessageBox.warning", lambda *args: warnings.append(args[1:]))
            dialog._accept_if_valid()

        assert dialog.result() == 0
        assert warnings[0][0] == "App Name"
        dialog.deleteLater()

    def test_browse_sdk_root_auto_resolves_parent_directory(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.new_project_dialog import NewProjectDialog

        sdk_parent = tmp_path / "tools"
        sdk_root = sdk_parent / "sdk" / "EmbeddedGUI-main"
        _create_sdk_root(sdk_root)

        dialog = NewProjectDialog(sdk_root="", default_parent_dir=str(tmp_path))
        monkeypatch.setattr("ui_designer.ui.new_project_dialog.QFileDialog.getExistingDirectory", lambda *args, **kwargs: str(sdk_parent))

        dialog._browse_sdk_root()

        assert dialog.sdk_root == os.path.normpath(os.path.abspath(sdk_root))
        assert dialog._sdk_edit.text() == os.path.normpath(os.path.abspath(sdk_root))
        dialog.deleteLater()

    def test_accept_succeeds_with_valid_values(self, qapp, isolated_config, tmp_path):
        from ui_designer.ui.new_project_dialog import NewProjectDialog

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)

        dialog = NewProjectDialog(sdk_root=str(sdk_root), default_parent_dir=str(tmp_path))
        dialog._app_name_edit.setText("DemoApp")
        dialog._width_spin.setValue(320)
        dialog._height_spin.setValue(240)
        dialog._accept_if_valid()

        assert dialog.result() == dialog.Accepted
        assert dialog.app_name == "DemoApp"
        assert dialog.screen_width == 320
        assert dialog.screen_height == 240
        dialog.deleteLater()

    def test_prefills_default_sdk_cache_when_available(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.new_project_dialog import NewProjectDialog

        sdk_root = tmp_path / "cache" / "EmbeddedGUI"
        _create_sdk_root(sdk_root)
        isolated_config.sdk_root = str(tmp_path / "missing_sdk")
        isolated_config.egui_root = str(tmp_path / "missing_sdk")
        monkeypatch.setattr("ui_designer.ui.new_project_dialog.default_sdk_install_dir", lambda: str(sdk_root))

        dialog = NewProjectDialog(sdk_root="", default_parent_dir="")

        assert dialog.sdk_root == os.path.normpath(os.path.abspath(sdk_root))
        assert dialog._sdk_edit.text() == os.path.normpath(os.path.abspath(sdk_root))
        dialog.deleteLater()

    def test_defaults_parent_dir_to_sdk_example_when_sdk_root_is_set(self, qapp, isolated_config, tmp_path):
        from ui_designer.ui.new_project_dialog import NewProjectDialog

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)

        dialog = NewProjectDialog(sdk_root=str(sdk_root), default_parent_dir="")

        assert dialog.parent_dir == os.path.join(os.path.normpath(os.path.abspath(sdk_root)), "example")
        dialog.deleteLater()

    def test_browse_sdk_root_updates_auto_managed_parent_dir(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.new_project_dialog import NewProjectDialog

        old_sdk_root = tmp_path / "sdk_old"
        new_sdk_root = tmp_path / "sdk_new"
        _create_sdk_root(old_sdk_root)
        _create_sdk_root(new_sdk_root)

        dialog = NewProjectDialog(sdk_root=str(old_sdk_root), default_parent_dir=os.path.join(str(old_sdk_root), "example"))
        monkeypatch.setattr("ui_designer.ui.new_project_dialog.QFileDialog.getExistingDirectory", lambda *args, **kwargs: str(new_sdk_root))

        dialog._browse_sdk_root()

        assert dialog.sdk_root == os.path.normpath(os.path.abspath(new_sdk_root))
        assert dialog.parent_dir == os.path.join(os.path.normpath(os.path.abspath(new_sdk_root)), "example")
        dialog.deleteLater()

    def test_browse_sdk_root_keeps_manual_parent_dir(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.new_project_dialog import NewProjectDialog

        old_sdk_root = tmp_path / "sdk_old"
        new_sdk_root = tmp_path / "sdk_new"
        custom_parent = tmp_path / "workspace"
        _create_sdk_root(old_sdk_root)
        _create_sdk_root(new_sdk_root)
        custom_parent.mkdir()

        dialog = NewProjectDialog(sdk_root=str(old_sdk_root), default_parent_dir=os.path.join(str(old_sdk_root), "example"))
        monkeypatch.setattr("ui_designer.ui.new_project_dialog.QFileDialog.getExistingDirectory", lambda *args, **kwargs: str(custom_parent))
        dialog._browse_parent_dir()

        monkeypatch.setattr("ui_designer.ui.new_project_dialog.QFileDialog.getExistingDirectory", lambda *args, **kwargs: str(new_sdk_root))
        dialog._browse_sdk_root()

        assert dialog.sdk_root == os.path.normpath(os.path.abspath(new_sdk_root))
        assert dialog.parent_dir == os.path.normpath(os.path.abspath(custom_parent))
        dialog.deleteLater()


@_skip_no_qt
class TestWelcomePage:
    def test_exposes_welcome_page_accessibility_summary(self, qapp, isolated_config, tmp_path):
        from ui_designer.ui.welcome_page import WelcomePage

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        isolated_config.sdk_root = str(sdk_root)

        page = WelcomePage()
        shell_layout = page.layout().itemAt(1).widget().layout()
        center_widget = shell_layout.itemAt(0).widget()
        center_layout = center_widget.layout()
        hero_layout = page._hero.layout()

        assert page.accessibleName() == (
            f"Welcome page: Ready: using selected SDK root. SDK path: {sdk_root}. No recent projects."
        )
        assert (shell_layout.contentsMargins().left(), shell_layout.contentsMargins().top(), shell_layout.contentsMargins().right(), shell_layout.contentsMargins().bottom()) == (16, 16, 16, 16)
        assert shell_layout.spacing() == 10
        assert center_layout.spacing() == 10
        assert (hero_layout.contentsMargins().left(), hero_layout.contentsMargins().top(), hero_layout.contentsMargins().right(), hero_layout.contentsMargins().bottom()) == (12, 10, 12, 10)
        assert hero_layout.spacing() == 12
        assert page._hero.accessibleName() == (
            f"Welcome hero. Welcome page: Ready: using selected SDK root. SDK path: {sdk_root}. No recent projects."
        )
        assert page._eyebrow_label.isHidden()
        assert page._subtitle_label.isHidden()
        assert page._hero_hint_label.isHidden()
        assert page._overview_metrics_frame.isHidden()
        assert page._start_hint_label.isHidden()
        assert page._recent_hint_label.isHidden()
        assert page._footer_label.isHidden()
        assert page._eyebrow_label.accessibleName() == "Workspace launch surface."
        assert page._title_label.accessibleName() == "Welcome page title: EmbeddedGUI Designer."
        assert page._subtitle_label.accessibleName() == page._subtitle_label.text()
        assert page._sdk_status_label.accessibleName() == "SDK status: Ready: using selected SDK root"
        assert page._sdk_path_label.accessibleName() == f"SDK path: {sdk_root}"
        assert page._sdk_hint_label.isHidden()
        assert page._recent_label.accessibleName() == "Recent Projects: No recent projects."
        assert page._overview_sdk_value.accessibleName() == "Welcome metric: SDK Binding. Ready: using selected SDK root."
        assert page._overview_sdk_value._welcome_metric_label.accessibleName() == "SDK Binding metric label."
        assert page._overview_sdk_value._welcome_metric_card.accessibleName() == "SDK Binding metric: Ready: using selected SDK root."
        assert page._overview_preview_value.accessibleName() == "Welcome metric: Preview Mode. Compile-backed preview ready."
        assert page._overview_preview_value._welcome_metric_label.accessibleName() == "Preview Mode metric label."
        assert page._overview_preview_value._welcome_metric_card.accessibleName() == (
            "Preview Mode metric: Compile-backed preview ready."
        )
        assert page._overview_recent_value.accessibleName() == "Welcome metric: Recent Work. No recent projects."
        assert page._overview_recent_value._welcome_metric_label.accessibleName() == "Recent Work metric label."
        assert page._overview_recent_value._welcome_metric_card.accessibleName() == "Recent Work metric: No recent projects."
        assert len(page.findChildren(QFrame, "welcome_metric_card")) == 3
        assert page._new_project_btn.toolTip() == "Create a new EmbeddedGUI Designer project."
        assert page._new_project_btn.accessibleName() == (
            "Create new project action. Create a new EmbeddedGUI Designer project."
        )
        assert page._open_project_btn.text() == "Open Project..."
        assert page._open_project_btn.toolTip() == "Open an existing .egui project file."
        assert page._open_project_btn.accessibleName() == (
            "Open project file action. Open an existing .egui project file."
        )
        assert page._open_app_btn.text() == "Open Example..."
        assert page._open_app_btn.toolTip() == "Open an SDK example project or legacy example."
        assert page._open_app_btn.statusTip() == page._open_app_btn.toolTip()
        assert page._open_app_btn.accessibleName() == (
            "Open SDK example action. Open an SDK example project or legacy example."
        )
        assert page._set_sdk_root_btn.text() == "Set SDK..."
        assert page._set_sdk_root_btn.toolTip() == "Change the EmbeddedGUI SDK root used for compile preview."
        assert page._set_sdk_root_btn.accessibleName() == (
            "Set SDK root action. Change the EmbeddedGUI SDK root used for compile preview."
        )
        assert page._download_sdk_btn.text() == "Download..."
        assert page._download_sdk_btn.statusTip() == page._download_sdk_btn.toolTip()
        assert page._download_sdk_btn.accessibleName() == (
            f"Download SDK action. {page._download_sdk_btn.toolTip()}"
        )
        assert page._recent_label.text() == "Recent"
        page.deleteLater()

    def test_hero_hint_skips_no_op_rewrites(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.welcome_page import WelcomePage

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        isolated_config.sdk_root = str(sdk_root)

        page = WelcomePage()
        page._hero.setProperty("_welcome_hint_snapshot", None)

        hint_calls = 0
        original_set_tooltip = page._hero.setToolTip

        def counted_set_tooltip(text):
            nonlocal hint_calls
            hint_calls += 1
            return original_set_tooltip(text)

        monkeypatch.setattr(page._hero, "setToolTip", counted_set_tooltip)

        page._update_accessibility_summary()
        assert hint_calls == 1

        page._update_accessibility_summary()
        assert hint_calls == 1

        project_path = tmp_path / "DemoApp" / "DemoApp.egui"
        project_path.parent.mkdir()
        project_path.write_text("")
        isolated_config.recent_projects = [
            {
                "project_path": str(project_path),
                "sdk_root": str(sdk_root),
                "display_name": "DemoApp",
            }
        ]
        page._refresh_recent_list()
        assert hint_calls == 2
        page.deleteLater()

    def test_hero_accessible_name_skips_no_op_rewrites(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.welcome_page import WelcomePage

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        isolated_config.sdk_root = str(sdk_root)

        page = WelcomePage()
        page._hero.setProperty("_welcome_accessible_snapshot", None)

        accessible_calls = 0
        original_set_accessible_name = page._hero.setAccessibleName

        def counted_set_accessible_name(text):
            nonlocal accessible_calls
            accessible_calls += 1
            return original_set_accessible_name(text)

        monkeypatch.setattr(page._hero, "setAccessibleName", counted_set_accessible_name)

        page._update_accessibility_summary()
        assert accessible_calls == 1

        page._update_accessibility_summary()
        assert accessible_calls == 1

        project_path = tmp_path / "DemoApp" / "DemoApp.egui"
        project_path.parent.mkdir()
        project_path.write_text("")
        isolated_config.recent_projects = [
            {
                "project_path": str(project_path),
                "sdk_root": str(sdk_root),
                "display_name": "DemoApp",
            }
        ]
        page._refresh_recent_list()
        assert accessible_calls == 2
        page.deleteLater()

    def test_recent_project_item_exposes_accessibility_summary(self, qapp, isolated_config, tmp_path):
        from ui_designer.ui.welcome_page import WelcomePage

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_path = tmp_path / "DemoApp" / "DemoApp.egui"
        project_path.parent.mkdir()
        project_path.write_text("")
        isolated_config.recent_projects = [
            {
                "project_path": str(project_path),
                "sdk_root": str(sdk_root),
                "display_name": "DemoApp",
            }
        ]

        page = WelcomePage()
        widget = page._recent_list.itemAt(0).widget()

        assert widget is not None
        recent_margins = widget.layout().contentsMargins()
        assert widget.minimumHeight() == 84
        assert (recent_margins.left(), recent_margins.top(), recent_margins.right(), recent_margins.bottom()) == (0, 0, 0, 0)
        assert widget.layout().spacing() == 8
        assert page._recent_list.spacing() == 4
        assert widget.accessibleName() == (
            f"Recent project: DemoApp. Project ready. SDK ready. Path: {project_path}."
        )
        assert widget._path_label.isHidden()
        assert widget._path_label.accessibleName() == f"Recent project path: {project_path}"
        assert page._hero.accessibleName() == (
            f"Welcome hero. Welcome page: Missing: editing only, Python preview fallback. SDK path: No SDK root configured. 1 recent item."
        )
        assert widget._status_label.accessibleName() == (
            "Recent project status: Project: ready  |  SDK: ready (selected SDK root)"
        )
        assert page._recent_label.accessibleName() == "Recent Projects: 1 recent item."
        assert page._overview_recent_value.accessibleName() == "Welcome metric: Recent Work. 1 recent item."
        assert page._overview_recent_value._welcome_metric_card.accessibleName() == "Recent Work metric: 1 recent item."
        assert "1 recent item." in page.accessibleName()
        page.deleteLater()

    def test_refresh_shows_no_recent_state(self, qapp, isolated_config):
        from ui_designer.ui.welcome_page import WelcomePage

        isolated_config.recent_projects = []
        page = WelcomePage()

        assert page._recent_list.count() == 1
        widget = page._recent_list.itemAt(0).widget()
        assert widget is not None
        assert "No recent projects" in (widget.accessibleName() or "")
        assert any("No recent projects" in (lb.text() or "") for lb in widget.findChildren(QLabel))
        assert _find_label_by_text(widget, "Open a .egui file or create a project - it will appear here.").isHidden()
        assert "No recent projects." in page.accessibleName()
        assert page._recent_label.accessibleName() == "Recent Projects: No recent projects."
        page.deleteLater()

    def test_refresh_replaces_empty_recent_state_without_stale_widgets(self, qapp, isolated_config, tmp_path):
        from ui_designer.ui.welcome_page import WelcomePage

        isolated_config.recent_projects = []
        page = WelcomePage()

        assert page.findChildren(QWidget, "welcome_recent_empty")

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        project_path = tmp_path / "DemoApp" / "DemoApp.egui"
        project_path.parent.mkdir()
        project_path.write_text("")
        isolated_config.recent_projects = [
            {
                "project_path": str(project_path),
                "sdk_root": str(sdk_root),
                "display_name": "DemoApp",
            }
        ]

        page.refresh()

        assert not page.findChildren(QWidget, "welcome_recent_empty")
        assert page._recent_list.count() == 1
        widget = page._recent_list.itemAt(0).widget()
        assert widget is not None
        assert widget.display_name == "DemoApp"
        page.deleteLater()

    def test_recent_click_emits_project_path_and_sdk(self, qapp, isolated_config, tmp_path):
        from ui_designer.ui.welcome_page import WelcomePage

        project_path = str(tmp_path / "DemoApp" / "DemoApp.egui")
        sdk_root = str(tmp_path / "sdk")
        isolated_config.recent_projects = []

        page = WelcomePage()
        emitted = []
        page.open_recent.connect(lambda project, sdk: emitted.append((project, sdk)))
        page._on_recent_clicked(project_path, sdk_root)

        assert emitted == [(project_path, sdk_root)]
        page.deleteLater()

    def test_recent_project_item_uses_cached_sdk_when_saved_sdk_is_invalid(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.welcome_page import WelcomePage

        cache_dir = tmp_path / "cache" / "EmbeddedGUI"
        _create_sdk_root(cache_dir)
        project_path = str(tmp_path / "DemoApp" / "DemoApp.egui")
        isolated_config.recent_projects = [
            {
                "project_path": project_path,
                "sdk_root": str(tmp_path / "missing_sdk"),
                "display_name": "DemoApp",
            }
        ]
        monkeypatch.setattr("ui_designer.ui.welcome_page.default_sdk_install_dir", lambda: str(cache_dir))

        page = WelcomePage()
        widget = page._recent_list.itemAt(0).widget()

        assert widget is not None
        assert widget.sdk_root == os.path.normpath(os.path.abspath(cache_dir))
        assert "ready" in widget._status_label.text().lower()
        page.deleteLater()

    def test_recent_project_item_marks_missing_project_path(self, qapp, isolated_config, tmp_path):
        from ui_designer.ui.welcome_page import WelcomePage

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        missing_project = tmp_path / "MissingApp" / "MissingApp.egui"
        isolated_config.recent_projects = [
            {
                "project_path": str(missing_project),
                "sdk_root": str(sdk_root),
                "display_name": "MissingApp",
            }
        ]

        page = WelcomePage()
        widget = page._recent_list.itemAt(0).widget()

        assert widget is not None
        assert "project: missing" in widget._status_label.text().lower()
        assert "sdk: ready" in widget._status_label.text().lower()
        page.deleteLater()

    def test_refresh_shows_sdk_status_and_path(self, qapp, isolated_config, tmp_path):
        from ui_designer.ui.welcome_page import WelcomePage

        sdk_root = tmp_path / "sdk"
        _create_sdk_root(sdk_root)
        isolated_config.sdk_root = str(sdk_root)

        page = WelcomePage()

        assert "Ready" in page._sdk_status_label.text()
        assert str(sdk_root) in page._sdk_path_label.text()
        page.deleteLater()

    def test_refresh_shows_default_download_cache_when_sdk_missing(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.welcome_page import WelcomePage

        cache_dir = tmp_path / "cache" / "EmbeddedGUI"
        isolated_config.sdk_root = ""
        isolated_config.egui_root = ""
        monkeypatch.setattr("ui_designer.ui.welcome_page.default_sdk_install_dir", lambda: str(cache_dir))

        page = WelcomePage()

        assert "Missing" in page._sdk_status_label.text()
        assert str(cache_dir) in page._sdk_hint_label.text()
        assert "GitHub archive" in page._sdk_hint_label.text()
        assert page._open_app_btn.toolTip() == "Set or download an SDK before browsing SDK examples."
        assert page._open_app_btn.accessibleName() == (
            "Open SDK example action. Set or download an SDK before browsing SDK examples."
        )
        assert page._set_sdk_root_btn.toolTip() == "Choose the EmbeddedGUI SDK root used for compile preview."
        assert page._set_sdk_root_btn.accessibleName() == (
            "Set SDK root action. Choose the EmbeddedGUI SDK root used for compile preview."
        )
        page.deleteLater()

    def test_refresh_uses_default_sdk_cache_when_config_is_invalid(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.welcome_page import WelcomePage

        cache_dir = tmp_path / "config" / "sdk" / "EmbeddedGUI"
        _create_sdk_root(cache_dir)
        isolated_config.sdk_root = str(tmp_path / "missing_sdk")
        isolated_config.egui_root = str(tmp_path / "missing_sdk")
        monkeypatch.setattr("ui_designer.model.sdk_bootstrap._get_config_dir", lambda: str(tmp_path / "config"))

        page = WelcomePage()

        assert "auto-downloaded SDK cache" in page._sdk_status_label.text()
        assert str(cache_dir) in page._sdk_path_label.text()
        assert str(cache_dir) in page._sdk_hint_label.text()
        page.deleteLater()

    def test_refresh_shows_bundled_sdk_status_when_using_runtime_sdk(self, qapp, isolated_config, tmp_path, monkeypatch):
        from ui_designer.ui.welcome_page import WelcomePage

        runtime_dir = tmp_path / "EmbeddedGUI-Designer"
        sdk_root = runtime_dir / "sdk" / "EmbeddedGUI"
        _create_sdk_root(sdk_root)
        _mark_bundled_sdk(sdk_root)
        isolated_config.sdk_root = str(sdk_root)
        isolated_config.egui_root = str(sdk_root)
        monkeypatch.setattr("ui_designer.ui.welcome_page.default_sdk_install_dir", lambda: str(sdk_root))
        monkeypatch.setattr("ui_designer.model.sdk_bootstrap.sys.frozen", True, raising=False)
        monkeypatch.setattr("ui_designer.model.sdk_bootstrap.sys.executable", str(runtime_dir / "EmbeddedGUI-Designer.exe"))

        page = WelcomePage()

        assert "bundled SDK" in page._sdk_status_label.text()
        assert "Packaged with Designer" in page._sdk_hint_label.text()
        page.deleteLater()

    def test_quick_action_buttons_emit_signals(self, qapp, isolated_config):
        from ui_designer.ui.welcome_page import WelcomePage

        page = WelcomePage()
        events = []
        page.new_project.connect(lambda: events.append("new"))
        page.open_project.connect(lambda: events.append("open_project"))
        page.open_app.connect(lambda: events.append("open_app"))
        page.set_sdk_root.connect(lambda: events.append("set_sdk"))
        page.download_sdk.connect(lambda: events.append("download_sdk"))

        page._new_project_btn.click()
        page._open_project_btn.click()
        page._open_app_btn.click()
        page._set_sdk_root_btn.click()
        page._download_sdk_btn.click()

        assert events == ["new", "open_project", "open_app", "set_sdk", "download_sdk"]
        page.deleteLater()
