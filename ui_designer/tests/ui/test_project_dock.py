"""Qt UI tests for the project explorer dock."""

import pytest

from ui_designer.tests.project_builders import build_test_project
from ui_designer.tests.qt_test_utils import HAS_PYQT5, skip_if_no_qt

if HAS_PYQT5:
    from PyQt5.QtCore import QEvent, Qt
    from PyQt5.QtGui import QFont

_skip_no_qt = skip_if_no_qt
@_skip_no_qt
class TestProjectExplorerDock:
    def test_compact_mode_uses_dense_page_tree_font(self, qapp):
        from ui_designer.ui.project_dock import ProjectExplorerDock
        from ui_designer.ui.theme import app_theme_tokens, designer_ui_font

        dock = ProjectExplorerDock()
        dock.set_compact_mode(True)
        dock.set_project(build_test_project(pages=["main_page", "detail_page"]))

        tokens = app_theme_tokens()
        expected_px = int(tokens["fs_body_sm"])
        expected_family = designer_ui_font().family()
        first = dock._page_tree.topLevelItem(0)
        second = dock._page_tree.topLevelItem(1)

        assert dock._page_tree.font().pixelSize() == expected_px
        assert dock._page_tree.font().family() == expected_family
        assert first.font(0).pixelSize() == expected_px
        assert second.font(0).pixelSize() == expected_px
        dock.deleteLater()

    def test_change_event_refreshes_tree_typography(self, qapp):
        from ui_designer.ui.project_dock import ProjectExplorerDock

        dock = ProjectExplorerDock()
        dock.set_project(build_test_project(pages=["main_page", "detail_page"]))
        dock.set_current_page("main_page")

        font = QFont(dock._page_tree.font())
        font.setPointSize(15)
        dock._page_tree.setFont(font)
        dock.changeEvent(QEvent(QEvent.FontChange))

        first = dock._page_tree.topLevelItem(0)
        second = dock._page_tree.topLevelItem(1)
        assert first.font(0).pointSize() == 15
        assert second.font(0).pointSize() == 15
        assert first.font(0).bold() is True
        assert second.font(0).bold() is False
        dock.deleteLater()

    def test_refresh_tree_typography_reuses_current_tree_font(self, qapp):
        from ui_designer.ui.project_dock import ProjectExplorerDock

        dock = ProjectExplorerDock()
        dock.set_project(build_test_project(pages=["main_page", "detail_page"]))
        dock.set_current_page("main_page")

        font = QFont(dock._page_tree.font())
        font.setPointSize(15)
        dock._page_tree.setFont(font)
        dock.refresh_tree_typography()

        first = dock._page_tree.topLevelItem(0)
        second = dock._page_tree.topLevelItem(1)
        assert first.font(0).pointSize() == 15
        assert second.font(0).pointSize() == 15
        assert first.font(0).bold() is True
        assert second.font(0).bold() is False
        dock.deleteLater()

    def test_header_exposes_project_overview_and_metric_metadata(self, qapp):
        from ui_designer.ui.project_dock import ProjectExplorerDock

        dock = ProjectExplorerDock()
        root_layout = dock.widget().layout()
        header_margins = dock._header_frame.layout().contentsMargins()
        mode_layout = dock._settings_group.layout().itemAt(0).layout()

        assert root_layout.spacing() == 2
        assert (header_margins.left(), header_margins.top(), header_margins.right(), header_margins.bottom()) == (2, 2, 2, 2)
        assert dock._header_frame.layout().spacing() == 2
        assert dock._settings_group.layout().spacing() == 2
        assert mode_layout.spacing() == 2
        assert dock._mode_combo.objectName() == "project_dock_mode_combo"
        assert dock._display_target_combo.objectName() == "project_dock_display_target_combo"
        assert dock._add_page_button.objectName() == "project_dock_add_page_button"
        assert dock._header_frame.accessibleName() == (
            "Project explorer header. Project Explorer: 0 pages. Current page: none. Startup page: none. No dirty pages."
        )
        assert dock._display_metric_value.text() == "No project"
        assert dock._primary_metric_value.text() == "Not set"
        assert dock._display_detail_label.text() == "Load or create a project to inspect displays."
        assert dock._display_target_combo.count() == 1
        assert dock._display_target_combo.currentText() == "No project"
        assert dock._display_target_combo.isEnabled() is False
        assert dock._title_label.accessibleName() == "Project panel title."
        assert dock._subtitle_label.accessibleName() == dock._subtitle_label.text()
        assert dock._subtitle_label.isHidden() is True
        assert dock._status_label.accessibleName() == "Project explorer status: mode easy_page. Current page: none"
        assert dock._status_label.isHidden() is True
        assert dock._pages_hint.isHidden() is True

        dock.set_project(build_test_project(pages=["main_page", "detail_page"]))
        dock.set_current_page("main_page")
        dock.set_dirty_pages({"detail_page"})

        assert dock._header_frame.accessibleName() == (
            "Project explorer header. Project Explorer: 2 pages. Current page: main_page. Startup page: main_page. 1 dirty page."
        )
        assert dock._display_metric_value.text() == "1 display"
        assert dock._primary_metric_value.text() == "240 x 320"
        assert dock._display_detail_label.text() == "Primary display only."
        assert dock._status_label.accessibleName() == "Project explorer status: mode easy_page. Current page: main_page"
        dock.deleteLater()

    def test_accessibility_summary_tracks_project_current_and_dirty_pages(self, qapp):
        from ui_designer.ui.project_dock import ProjectExplorerDock

        dock = ProjectExplorerDock()

        assert dock.accessibleName() == "Project Explorer: 0 pages. Current page: none. Startup page: none. No dirty pages."
        assert dock._settings_group.toolTip() == (
            "Project settings: 0 pages. Current mode: easy_page. Displays: No project. "
            "Primary canvas: Not set. Load or create a project to inspect displays."
        )
        assert dock._settings_group.statusTip() == dock._settings_group.toolTip()
        assert dock._settings_group.accessibleName() == dock._settings_group.toolTip()
        assert dock._mode_label.toolTip() == "Choose how pages are generated for the current project. Current mode: easy_page."
        assert dock._mode_label.statusTip() == dock._mode_label.toolTip()
        assert dock._mode_label.accessibleName() == (
            "Page mode label. Current mode: easy_page. "
            "Choose how pages are generated for the current project. Current mode: easy_page."
        )
        assert dock._display_metric_value.toolTip() == "Displays: No project."
        assert dock._display_metric_value.accessibleName() == "Displays: No project."
        assert dock._primary_metric_value.toolTip() == "Primary canvas: Not set."
        assert dock._primary_metric_value.accessibleName() == "Primary canvas: Not set."
        assert dock._display_detail_label.toolTip() == "Display summary: Load or create a project to inspect displays."
        assert dock._display_detail_label.accessibleName() == "Display summary: Load or create a project to inspect displays."
        assert dock._display_target_label.toolTip() == "Edit target label."
        assert dock._display_target_label.accessibleName() == "Edit target label."
        assert dock._display_target_combo.toolTip() == (
            "Display target selector unavailable. Load or create a project to inspect displays."
        )
        assert dock._display_target_combo.statusTip() == dock._display_target_combo.toolTip()
        assert dock._display_target_combo.accessibleName() == dock._display_target_combo.toolTip()
        assert dock._display_target_combo.currentText() == "No project"
        assert dock._page_tree.accessibleName() == "Project pages: 0 pages. Current page: none. Startup page: none. No dirty pages."
        assert dock._mode_combo.toolTip() == "Choose how pages are generated for the current project. Current mode: easy_page."
        assert dock._mode_combo.statusTip() == dock._mode_combo.toolTip()
        assert dock._mode_combo.accessibleName() == (
            "Project page mode: easy_page. "
            "Choose how pages are generated for the current project. Current mode: easy_page."
        )
        assert dock._add_page_button.toolTip() == "Create the first page for a new project. Current mode: easy_page."
        assert dock._add_page_button.statusTip() == dock._add_page_button.toolTip()
        assert dock._add_page_button.accessibleName() == (
            "New page action: easy_page mode. "
            "Create the first page for a new project. Current mode: easy_page."
        )

        dock.set_project(build_test_project(pages=["main_page", "detail_page"]))
        dock.set_current_page("main_page")
        dock.set_dirty_pages({"detail_page"})

        assert dock.accessibleName() == "Project Explorer: 2 pages. Current page: main_page. Startup page: main_page. 1 dirty page."
        assert dock._settings_group.toolTip() == (
            "Project settings: 2 pages. Current mode: easy_page. Displays: 1 display. "
            "Primary canvas: 240 x 320. Primary display only."
        )
        assert dock._settings_group.accessibleName() == dock._settings_group.toolTip()
        assert dock._mode_label.accessibleName() == (
            "Page mode label. Current mode: easy_page. "
            "Choose how pages are generated for the current project. Current mode: easy_page."
        )
        assert dock._display_metric_value.toolTip() == "Displays: 1 display."
        assert dock._display_metric_value.accessibleName() == "Displays: 1 display."
        assert dock._primary_metric_value.toolTip() == "Primary canvas: 240 x 320."
        assert dock._primary_metric_value.accessibleName() == "Primary canvas: 240 x 320."
        assert dock._display_detail_label.toolTip() == "Display summary: Primary display only."
        assert dock._display_detail_label.accessibleName() == "Display summary: Primary display only."
        assert dock._display_target_combo.toolTip() == "Display target selector: Display 0: 240 x 320 (Primary)."
        assert dock._display_target_combo.accessibleName() == dock._display_target_combo.toolTip()
        assert dock._display_target_combo.currentText() == "Display 0: 240 x 320 (Primary)"
        assert dock._pages_label.toolTip() == dock.accessibleName()
        assert dock._pages_label.accessibleName() == "Pages: 2 pages. Current page: main_page. Startup page: main_page."
        assert dock._page_tree.toolTip() == dock.accessibleName()
        assert dock._page_tree.accessibleName() == "Project pages: 2 pages. Current page: main_page. Startup page: main_page. 1 dirty page."
        assert dock._add_page_button.toolTip() == "Create a new page in the current project. Current mode: easy_page."
        assert dock._add_page_button.accessibleName() == (
            "New page action: easy_page mode. "
            "Create a new page in the current project. Current mode: easy_page."
        )

        dock._mode_combo.setCurrentText("activity")

        assert dock._mode_combo.toolTip() == "Choose how pages are generated for the current project. Current mode: activity."
        assert dock._mode_combo.accessibleName() == (
            "Project page mode: activity. "
            "Choose how pages are generated for the current project. Current mode: activity."
        )
        assert dock._settings_group.toolTip() == (
            "Project settings: 2 pages. Current mode: activity. Displays: 1 display. "
            "Primary canvas: 240 x 320. Primary display only."
        )
        assert dock._settings_group.accessibleName() == dock._settings_group.toolTip()
        assert dock._mode_label.toolTip() == "Choose how pages are generated for the current project. Current mode: activity."
        assert dock._mode_label.accessibleName() == (
            "Page mode label. Current mode: activity. "
            "Choose how pages are generated for the current project. Current mode: activity."
        )
        assert dock._add_page_button.toolTip() == "Create a new page in the current project. Current mode: activity."
        assert dock._add_page_button.accessibleName() == (
            "New page action: activity mode. "
            "Create a new page in the current project. Current mode: activity."
        )

        first = dock._page_tree.topLevelItem(0)
        second = dock._page_tree.topLevelItem(1)
        assert first.toolTip(0) == "Page: main_page. Startup page. Current page. No unsaved changes."
        assert second.toolTip(0) == "Page: detail_page. Unsaved changes."
        assert first.data(0, Qt.AccessibleTextRole) == first.toolTip(0)
        assert second.data(0, Qt.AccessibleTextRole) == second.toolTip(0)
        dock.deleteLater()

    def test_display_metrics_summarize_multi_display_projects(self, qapp):
        from ui_designer.ui.project_dock import ProjectExplorerDock

        dock = ProjectExplorerDock()
        project = build_test_project(pages=["main_page", "detail_page"])
        project.displays = [
            {"width": 320, "height": 240},
            {"width": 128, "height": 64, "pfb_width": 16, "pfb_height": 7},
        ]

        dock.set_project(project)

        assert dock._display_metric_value.text() == "2 displays"
        assert dock._display_metric_value.accessibleName() == "Displays: 2 displays."
        assert dock._primary_metric_value.text() == "320 x 240"
        assert dock._primary_metric_value.accessibleName() == "Primary canvas: 320 x 240."
        assert dock._display_detail_label.text() == (
            "Secondary displays: 1: 128 x 64. Editing/preview: primary display only."
        )
        assert dock._display_detail_label.accessibleName() == (
            "Display summary: Secondary displays: 1: 128 x 64. Editing/preview: primary display only."
        )
        assert dock._display_target_combo.count() == 2
        assert dock._display_target_combo.currentText() == "Display 0: 320 x 240 (Primary)"
        assert dock._display_target_combo.itemText(1) == "Display 1: 128 x 64"
        assert dock._display_target_combo.toolTip() == (
            "Display target selector: Display 0: 320 x 240 (Primary). "
            "Editing and preview are fixed to the primary display."
        )
        assert dock.accessibleName() == (
            "Project Explorer: 2 pages. Current page: none. Startup page: main_page. No dirty pages. "
            "Editing/preview: primary display only."
        )
        assert dock._header_frame.accessibleName() == (
            "Project explorer header. Project Explorer: 2 pages. Current page: none. Startup page: main_page. No dirty pages. "
            "Editing/preview: primary display only."
        )
        assert dock._pages_label.accessibleName() == (
            "Pages: 2 pages. Current page: none. Startup page: main_page. Editing/preview: primary display only."
        )
        assert dock._page_tree.accessibleName() == (
            "Project pages: 2 pages. Current page: none. Startup page: main_page. No dirty pages. "
            "Editing/preview: primary display only."
        )
        assert dock._status_label.accessibleName() == (
            "Project explorer status: mode easy_page. Current page: none. Editing/preview: primary display only."
        )
        assert dock._settings_group.toolTip() == (
            "Project settings: 2 pages. Current mode: easy_page. Displays: 2 displays. "
            "Primary canvas: 320 x 240. Secondary displays: 1: 128 x 64. Editing/preview: primary display only."
        )
        dock.deleteLater()

    def test_page_context_menu_actions_expose_dynamic_hints(self, qapp):
        from ui_designer.ui.project_dock import ProjectExplorerDock

        dock = ProjectExplorerDock()

        empty_menu = dock._build_page_context_menu(None)
        empty_actions = {action.text(): action for action in empty_menu.actions()}
        assert empty_actions["New Page..."].toolTip() == "Create the first page for a new project. Current mode: easy_page."
        assert empty_actions["New Page..."].statusTip() == empty_actions["New Page..."].toolTip()
        empty_menu.deleteLater()

        dock.set_project(build_test_project(pages=["main_page", "detail_page"]))
        dock.set_current_page("main_page")
        dock.set_dirty_pages({"detail_page"})

        current_item = dock._page_tree.topLevelItem(0)
        current_menu = dock._build_page_context_menu(current_item)
        current_actions = {action.text(): action for action in current_menu.actions() if action.text()}
        assert current_actions["Rename"].toolTip() == "Rename page: main_page."
        assert current_actions["Duplicate"].toolTip() == "Duplicate page: main_page."
        assert current_actions["Set as Startup Page"].toolTip() == "Current startup page: main_page."
        assert current_actions["Delete"].toolTip() == "Delete page: main_page. This cannot be undone."
        assert current_actions["Delete"].statusTip() == current_actions["Delete"].toolTip()
        current_menu.deleteLater()

        dirty_item = dock._page_tree.topLevelItem(1)
        dirty_menu = dock._build_page_context_menu(dirty_item)
        dirty_actions = {action.text(): action for action in dirty_menu.actions() if action.text()}
        assert dirty_actions["Rename"].toolTip() == "Rename page: detail_page."
        assert dirty_actions["Duplicate"].toolTip() == "Duplicate page: detail_page."
        assert dirty_actions["Set as Startup Page"].toolTip() == "Set detail_page as the startup page."
        assert dirty_actions["Delete"].toolTip() == "Delete page: detail_page. Unsaved changes will be lost."
        assert dirty_actions["Delete"].statusTip() == dirty_actions["Delete"].toolTip()
        dirty_menu.deleteLater()
        dock.deleteLater()

    def test_header_frame_hint_skips_no_op_rewrites(self, qapp, monkeypatch):
        from ui_designer.ui.project_dock import ProjectExplorerDock

        dock = ProjectExplorerDock()
        dock._header_frame.setProperty("_project_dock_hint_snapshot", None)

        hint_calls = 0
        original_set_tooltip = dock._header_frame.setToolTip

        def counted_set_tooltip(text):
            nonlocal hint_calls
            hint_calls += 1
            return original_set_tooltip(text)

        monkeypatch.setattr(dock._header_frame, "setToolTip", counted_set_tooltip)

        dock._update_accessibility_summary()
        assert hint_calls == 1

        dock._update_accessibility_summary()
        assert hint_calls == 1

        dock.set_project(build_test_project(pages=["main_page", "detail_page"]))
        assert hint_calls == 2
        dock.deleteLater()

    def test_header_frame_accessible_name_skips_no_op_rewrites(self, qapp, monkeypatch):
        from ui_designer.ui.project_dock import ProjectExplorerDock

        dock = ProjectExplorerDock()
        dock._header_frame.setProperty("_project_dock_accessible_snapshot", None)

        accessible_calls = 0
        original_set_accessible_name = dock._header_frame.setAccessibleName

        def counted_set_accessible_name(text):
            nonlocal accessible_calls
            accessible_calls += 1
            return original_set_accessible_name(text)

        monkeypatch.setattr(dock._header_frame, "setAccessibleName", counted_set_accessible_name)

        dock._update_accessibility_summary()
        assert accessible_calls == 1

        dock._update_accessibility_summary()
        assert accessible_calls == 1

        dock.set_project(build_test_project(pages=["main_page", "detail_page"]))
        assert accessible_calls == 2
        dock.deleteLater()
