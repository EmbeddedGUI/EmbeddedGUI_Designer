"""Qt UI tests for the widget browser panel."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtCore import Qt
    from PyQt5.QtTest import QTest
    from PyQt5.QtWidgets import QApplication, QLabel, QPushButton

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
def bind_widget_browser_config(isolated_config, monkeypatch):
    import ui_designer.ui.widget_browser as widget_browser_module

    monkeypatch.setattr(widget_browser_module, "get_config", lambda: isolated_config)


def _select_category(panel, category_id):
    for row in range(panel._category_list.count()):
        item = panel._category_list.item(row)
        if item.data(0x0100) == category_id:
            panel._category_list.setCurrentRow(row)
            return
    raise AssertionError(f"category {category_id!r} not found")


def _layout_group_headers(panel):
    headers = []
    for index in range(panel._cards_layout.count()):
        layout_item = panel._cards_layout.itemAt(index)
        widget = layout_item.widget() if layout_item is not None else None
        if widget is not None and widget.objectName() == "widget_browser_group_header":
            headers.append(widget)
    return headers


@_skip_no_qt
class TestWidgetBrowserPanel:
    def test_favorites_filter_uses_configured_widget_types(self, qapp, isolated_config):
        from ui_designer.ui.widget_browser import WidgetBrowserPanel

        isolated_config.widget_browser_favorites = ["button"]
        panel = WidgetBrowserPanel()

        _select_category(panel, "favorites")
        panel.refresh()

        assert [card.type_name for card in panel._cards.values()] == ["button"]
        panel.deleteLater()

    def test_recent_filter_preserves_recent_order(self, qapp, isolated_config):
        from ui_designer.ui.widget_browser import WidgetBrowserPanel

        isolated_config.widget_browser_recent = ["slider", "label", "button"]
        panel = WidgetBrowserPanel()

        _select_category(panel, "recent")
        panel.refresh()

        assert [card.type_name for card in panel._cards.values()] == ["slider", "label", "button"]
        panel.deleteLater()

    def test_search_and_insert_target_update_visible_cards(self, qapp, isolated_config):
        from ui_designer.ui.widget_browser import WidgetBrowserPanel

        panel = WidgetBrowserPanel()
        panel.set_insert_target_label("root_group / content")
        panel._search.setText("slider")
        panel.refresh()

        assert "root_group / content" in panel._insert_target.text()
        visible_types = [card.type_name for card in panel._cards.values()]
        assert "slider" in visible_types

        inserted = []
        panel.insert_requested.connect(inserted.append)
        slider_card = next(card for card in panel._cards.values() if card.type_name == "slider")
        slider_card.insert_requested.emit(slider_card.type_name)

        assert inserted == ["slider"]
        panel.deleteLater()

    def test_search_input_debounces_result_refresh(self, qapp, isolated_config):
        from ui_designer.ui.widget_browser import WidgetBrowserPanel

        panel = WidgetBrowserPanel()
        assert panel._cards
        initial_types = list(panel._cards.keys())

        panel._search.setText("__no_widget_matches__")

        assert panel._search_refresh_timer.isActive() is True
        assert list(panel._cards.keys()) == initial_types

        QTest.qWait(panel._SEARCH_REFRESH_DEBOUNCE_MS + 40)
        qapp.processEvents()

        assert panel._search_refresh_timer.isActive() is False
        assert panel._cards == {}
        panel.deleteLater()

    def test_card_context_menu_can_reveal_and_toggle_favorite(self, qapp, isolated_config, monkeypatch):
        from ui_designer.ui.widget_browser import WidgetBrowserPanel

        panel = WidgetBrowserPanel()
        card = next(card for card in panel._cards.values() if card.type_name == "button")
        emitted = []
        panel.reveal_requested.connect(emitted.append)

        chosen_labels = iter(["Favorite", "Reveal in Structure"])

        def fake_exec(menu, *_args, **_kwargs):
            target = next(chosen_labels)
            for action in menu.actions():
                if action.text() == target:
                    return action
            return None

        monkeypatch.setattr("ui_designer.ui.widget_browser.QMenu.exec_", fake_exec)

        panel._show_card_menu("button", None)
        assert "button" in isolated_config.widget_browser_favorites

        panel._show_card_menu("button", None)
        assert emitted == ["button"]
        panel.deleteLater()

    def test_filtering_selects_first_visible_card_when_previous_selection_disappears(self, qapp, isolated_config):
        from ui_designer.ui.widget_browser import WidgetBrowserPanel

        panel = WidgetBrowserPanel()
        panel._select_card("button")

        panel._search.setText("slider")
        panel.refresh()

        assert panel._selected_type in {card.type_name for card in panel._cards.values()}
        assert panel._selected_type == "slider"
        panel.deleteLater()

    def test_scenario_selection_persists_active_filter(self, qapp, isolated_config):
        from ui_designer.ui.widget_browser import WidgetBrowserPanel

        panel = WidgetBrowserPanel()
        scenario_row = None
        scenario_id = ""
        for row in range(panel._category_list.count()):
            item = panel._category_list.item(row)
            value = str(item.data(0x0100) or "")
            if value.startswith("scenario:"):
                scenario_row = row
                scenario_id = value
                break

        assert scenario_row is not None
        panel._category_list.setCurrentRow(scenario_row)

        assert isolated_config.widget_browser_active_scenario == scenario_id.lower()
        panel.deleteLater()

    def test_tag_filter_updates_config_and_constrains_results(self, qapp, isolated_config):
        from ui_designer.ui.widget_browser import WidgetBrowserPanel

        panel = WidgetBrowserPanel()
        assert panel._tag_buttons
        assert panel._clear_tags_btn.isHidden() is True
        first_tag = sorted(panel._tag_buttons.keys())[0]
        first_tag_button = panel._tag_buttons[first_tag]
        first_tag_button.setChecked(True)

        assert first_tag in [value.lower() for value in isolated_config.widget_browser_active_tags]
        assert first_tag_button.accessibleName() == f"Widget tag: {first_tag_button.text()}. Active."
        assert panel._clear_tags_btn.toolTip() == "Clear active widget tags."
        assert panel._clear_tags_btn.accessibleName() == "Clear widget tags"
        assert panel._clear_tags_btn.isHidden() is False
        for item in panel._filtered_items():
            item_tags = {str(tag).lower() for tag in item.get("tags", [])}
            assert first_tag in item_tags

        panel._clear_tags_btn.click()
        assert isolated_config.widget_browser_active_tags == []
        assert first_tag_button.accessibleName() == f"Widget tag: {first_tag_button.text()}. Inactive."
        assert panel._clear_tags_btn.accessibleName() == "Clear widget tags unavailable"
        assert panel._clear_tags_btn.isHidden() is True
        panel.deleteLater()

    def test_clear_active_tags_syncs_metadata_once(self, qapp, isolated_config, monkeypatch):
        from ui_designer.ui.widget_browser import WidgetBrowserPanel

        panel = WidgetBrowserPanel()
        first_tag = sorted(panel._tag_buttons.keys())[0]
        panel._tag_buttons[first_tag].setChecked(True)

        sync_calls = 0
        original_sync = panel._sync_tags_from_config

        def counted_sync():
            nonlocal sync_calls
            sync_calls += 1
            return original_sync()

        monkeypatch.setattr(panel, "_sync_tags_from_config", counted_sync)

        panel._clear_tags_btn.click()

        assert isolated_config.widget_browser_active_tags == []
        assert sync_calls == 1
        panel.deleteLater()

    def test_quick_lane_click_updates_active_category_and_results(self, qapp, isolated_config):
        from ui_designer.ui.widget_browser import WidgetBrowserPanel

        isolated_config.widget_browser_favorites = ["button"]
        panel = WidgetBrowserPanel()
        favorites_lane = panel._lane_buttons.get("favorites")

        assert favorites_lane is not None
        favorites_lane.click()

        assert panel._selected_category() == "favorites"
        assert [card.type_name for card in panel._cards.values()] == ["button"]
        assert favorites_lane.isChecked() is True
        assert favorites_lane.toolTip() == "Quick lane Favorites: 1 widget. Current lane."
        assert favorites_lane.accessibleName() == "Quick lane: Favorites. 1 widget. Current lane."
        assert favorites_lane.statusTip() == favorites_lane.toolTip()
        panel.deleteLater()

    def test_container_cards_expose_compact_meta_text(self, qapp, isolated_config):
        from ui_designer.ui.widget_browser import WidgetBrowserPanel

        panel = WidgetBrowserPanel()
        panel._select_card("linearlayout")
        container_card = next(card for card in panel._cards.values() if card.type_name == "linearlayout")
        meta_label = next(
            label
            for label in container_card.findChildren(QLabel)
            if label.objectName() == "widget_browser_card_meta"
        )

        assert "Container" in meta_label.text()
        assert meta_label.text().strip() != ""
        assert meta_label.isHidden() is False
        panel.deleteLater()

    def test_complexity_filter_limits_visible_results(self, qapp, isolated_config):
        from ui_designer.ui.widget_browser import WidgetBrowserPanel

        panel = WidgetBrowserPanel()
        panel._set_complexity_filter("intermediate")

        assert panel._complexity_filter == "intermediate"
        assert panel._complexity_buttons["intermediate"].isChecked() is True
        assert isolated_config.widget_browser_complexity_filter == "intermediate"
        assert len(panel._cards) > 0
        for item in panel._filtered_items():
            assert str(item.get("complexity", "")).lower() == "intermediate"
        panel.deleteLater()

    def test_sort_mode_name_orders_visible_cards_alphabetically(self, qapp, isolated_config):
        from ui_designer.ui.widget_browser import WidgetBrowserPanel

        panel = WidgetBrowserPanel()
        panel._set_sort_mode("name")

        assert panel._sort_mode == "name"
        assert panel._sort_buttons["name"].isChecked() is True
        assert isolated_config.widget_browser_sort_mode == "name"
        names = [str(card._item.get("display_name", "")).lower() for card in panel._cards.values()]
        assert names == sorted(names)
        panel.deleteLater()

    def test_reset_all_filters_also_resets_complexity_and_sort_mode(self, qapp, isolated_config):
        from ui_designer.ui.widget_browser import WidgetBrowserPanel

        panel = WidgetBrowserPanel()
        panel._search.setText("slider")
        panel._set_sort_mode("name")
        panel._set_complexity_filter("advanced")
        panel._reset_all_filters()

        assert panel._selected_category() == "all"
        assert panel._search.text() == ""
        assert panel._sort_mode == "relevance"
        assert panel._complexity_filter == "all"
        assert isolated_config.widget_browser_sort_mode == "relevance"
        assert isolated_config.widget_browser_complexity_filter == "all"
        assert panel._sort_buttons["relevance"].isChecked() is True
        assert panel._complexity_buttons["all"].isChecked() is True
        panel.deleteLater()

    def test_reset_all_filters_refreshes_results_once(self, qapp, isolated_config, monkeypatch):
        from ui_designer.ui.widget_browser import WidgetBrowserPanel

        panel = WidgetBrowserPanel()
        panel._search.setText("slider")
        panel._set_sort_mode("name")
        panel._set_complexity_filter("advanced")
        panel._tag_buttons[sorted(panel._tag_buttons.keys())[0]].setChecked(True)

        refresh_calls = 0
        original_refresh = panel.refresh

        def counted_refresh():
            nonlocal refresh_calls
            refresh_calls += 1
            return original_refresh()

        monkeypatch.setattr(panel, "refresh", counted_refresh)

        panel._reset_all_filters()

        assert refresh_calls == 1
        assert panel._search_refresh_timer.isActive() is False
        panel.deleteLater()

    def test_organizers_restore_from_config(self, qapp, isolated_config):
        from ui_designer.ui.widget_browser import WidgetBrowserPanel

        isolated_config.widget_browser_sort_mode = "complexity"
        isolated_config.widget_browser_complexity_filter = "advanced"
        panel = WidgetBrowserPanel()

        assert panel._sort_mode == "complexity"
        assert panel._complexity_filter == "advanced"
        assert panel._sort_buttons["complexity"].isChecked() is True
        assert panel._complexity_buttons["advanced"].isChecked() is True
        panel.deleteLater()

    def test_default_recommended_view_groups_cards_by_scenario(self, qapp, isolated_config):
        from ui_designer.ui.widget_browser import WidgetBrowserPanel

        panel = WidgetBrowserPanel()
        headers = _layout_group_headers(panel)

        assert len(headers) >= 2
        panel.deleteLater()

    def test_non_recommended_sort_hides_scenario_group_headers(self, qapp, isolated_config):
        from ui_designer.ui.widget_browser import WidgetBrowserPanel

        panel = WidgetBrowserPanel()
        panel._set_sort_mode("name")
        headers = _layout_group_headers(panel)

        assert headers == []
        panel.deleteLater()

    def test_browser_exposes_summary_and_filter_metadata(self, qapp, isolated_config):
        from ui_designer.ui.widget_browser import WidgetBrowserPanel

        panel = WidgetBrowserPanel()
        selected_label = next(
            (
                str(card._item.get("display_name", card.type_name) or card.type_name)
                for card in panel._cards.values()
                if card.type_name == panel._selected_type
            ),
            "none",
        )
        visible_text = f"{len(panel._cards)} visible widget" if len(panel._cards) == 1 else f"{len(panel._cards)} visible widgets"

        assert panel.accessibleName() == (
            f"Widget Browser: {visible_text}. Category: All Widgets. Search: none. "
            f"Sort: Recommended. Complexity: All. Tags: none. "
            f"Insert target: Current page root. Selected: {selected_label}."
        )
        assert panel._search.toolTip() == "Widget browser search. Current text: none."
        assert panel._search.accessibleName() == "Widget browser search: none."
        assert panel._category_list.accessibleName() == "Widget categories: All Widgets"
        assert panel._lanes_title.accessibleName() == "Quick Lanes: current category All Widgets."
        assert panel._sort_title.accessibleName() == "Sort: Recommended"
        assert panel._complexity_title.accessibleName() == "Complexity: All"
        assert panel._tags_title.accessibleName() == "Tags: none."
        first_category = panel._category_list.item(0)
        assert first_category.toolTip() == "Show All Widgets in the widget browser."
        assert first_category.statusTip() == first_category.toolTip()
        assert first_category.data(Qt.AccessibleTextRole) == first_category.toolTip()
        assert panel._stats_summary_label.accessibleName() == (
            f"Widget browser stats: {panel._stats_summary_label.text()}."
        )
        assert panel._clear_tags_btn.toolTip() == "No active widget tags to clear."
        assert panel._clear_tags_btn.accessibleName() == "Clear widget tags unavailable"
        assert panel._clear_tags_btn.isHidden() is True
        assert panel._sort_buttons["relevance"].accessibleName() == "Sort mode: Recommended. Current."
        assert panel._sort_buttons["name"].accessibleName() == "Sort mode: A-Z. Available."
        assert panel._complexity_buttons["all"].accessibleName() == "Complexity filter: All. Current."
        assert panel._complexity_buttons["advanced"].accessibleName() == "Complexity filter: Advanced. Available."
        assert panel._lane_buttons["favorites"].accessibleName() == "Quick lane: Favorites. 0 widgets. No widgets available."

        scenario_item = next(
            panel._category_list.item(row)
            for row in range(panel._category_list.count())
            if str(panel._category_list.item(row).data(Qt.UserRole) or "").startswith("scenario:")
        )
        assert scenario_item.statusTip() == scenario_item.toolTip()
        assert scenario_item.data(Qt.AccessibleTextRole) == scenario_item.toolTip()
        panel.deleteLater()

    def test_browser_stats_summary_compacts_counts_and_marks_active_filters(self, qapp, isolated_config):
        from ui_designer.ui.widget_browser import WidgetBrowserPanel

        isolated_config.widget_browser_favorites = ["button", "slider"]
        isolated_config.widget_browser_recent = ["label"]
        panel = WidgetBrowserPanel()

        assert "Favorites 2" in panel._stats_summary_label.text()
        assert "Recent 1" in panel._stats_summary_label.text()
        assert panel._stats_summary_label.accessibleName() == (
            f"Widget browser stats: {panel._stats_summary_label.text()}."
        )
        initial_summary = panel._stats_summary_label.text()

        panel._search.setText("slider")
        panel.refresh()

        assert panel._stats_summary_label.text() != initial_summary
        assert panel._stats_summary_label.toolTip().endswith("Filters active.")
        assert panel._stats_summary_label.accessibleName().endswith("Filters active.")
        panel.deleteLater()

    def test_card_metadata_tracks_selection_and_favorite_state(self, qapp, isolated_config):
        from ui_designer.ui.widget_browser import WidgetBrowserPanel

        panel = WidgetBrowserPanel()
        panel._select_card("button")
        button_card = next(card for card in panel._cards.values() if card.type_name == "button")
        display_name = str(button_card._item.get("display_name", button_card.type_name) or button_card.type_name)
        category = str(button_card._item.get("category", "") or "Uncategorized").strip() or "Uncategorized"
        scenario = str(button_card._item.get("scenario", "") or "General").strip() or "General"
        complexity = str(button_card._item.get("complexity", "") or "unknown").strip().title() or "Unknown"
        container_text = "yes" if bool(button_card._item.get("is_container")) else "no"

        assert button_card.accessibleName() == (
            f"Widget card: {display_name}. Category {category}. Scenario {scenario}. "
            f"Complexity {complexity}. Container {container_text}. Favorite no. Selected yes."
        )
        assert button_card._favorite_btn.toolTip() == f"Add {display_name} to favorites."
        assert button_card._insert_btn.toolTip() == f"Insert {display_name} into the current target."

        panel._toggle_favorite("button")
        button_card = next(card for card in panel._cards.values() if card.type_name == "button")
        assert button_card._favorite_btn.toolTip() == f"Remove {display_name} from favorites."
        assert f"Selected: {display_name}." in panel.accessibleName()
        panel.deleteLater()

    def test_empty_state_and_quick_lane_metadata_refresh_with_filters(self, qapp, isolated_config):
        from ui_designer.ui.widget_browser import WidgetBrowserPanel

        isolated_config.widget_browser_favorites = ["button"]
        panel = WidgetBrowserPanel()
        favorites_lane = panel._lane_buttons["favorites"]

        assert favorites_lane.toolTip() == "Quick lane Favorites: 1 widget."
        assert favorites_lane.accessibleName() == "Quick lane: Favorites. 1 widget. Available."

        panel._search.setText("__no_widget_matches__")
        panel.refresh()

        assert "Widget Browser: 0 visible widgets." in panel.accessibleName()
        assert panel._scroll.toolTip() == "Widget browser results: 0 cards visible."
        empty_state = next(
            widget
            for widget in (
                panel._cards_layout.itemAt(index).widget()
                for index in range(panel._cards_layout.count())
            )
            if widget is not None and widget.objectName() == "widget_browser_empty_state"
        )
        hint = next(
            label
            for label in empty_state.findChildren(QLabel)
            if label.objectName() == "workspace_section_subtitle"
        )
        buttons = {button.text(): button for button in empty_state.findChildren(QPushButton)}
        assert empty_state.accessibleName() == "No widgets match the current filters."
        assert hint.text() == "Clear search to show matching widgets."
        assert panel._search.toolTip() == "Widget browser search. Current text: __no_widget_matches__."
        assert panel._search.accessibleName() == "Widget browser search: __no_widget_matches__."
        assert sorted(buttons) == ["Reset Search"]
        assert buttons["Reset Search"].toolTip() == "Clear the current widget browser search text."
        panel.deleteLater()

    def test_empty_state_shows_all_widgets_action_for_non_default_category(self, qapp, isolated_config):
        from ui_designer.ui.widget_browser import WidgetBrowserPanel

        panel = WidgetBrowserPanel()
        _select_category(panel, "favorites")
        panel.refresh()

        empty_state = next(
            widget
            for widget in (
                panel._cards_layout.itemAt(index).widget()
                for index in range(panel._cards_layout.count())
            )
            if widget is not None and widget.objectName() == "widget_browser_empty_state"
        )
        hint = next(
            label
            for label in empty_state.findChildren(QLabel)
            if label.objectName() == "workspace_section_subtitle"
        )
        buttons = {button.text(): button for button in empty_state.findChildren(QPushButton)}

        assert hint.text() == "Show all widgets to leave the current category."
        assert sorted(buttons) == ["Show All Widgets"]
        assert buttons["Show All Widgets"].toolTip() == "Reset every widget browser filter and show all widgets."
        panel.deleteLater()

    def test_reset_search_only_refreshes_immediately(self, qapp, isolated_config):
        from ui_designer.ui.widget_browser import WidgetBrowserPanel

        panel = WidgetBrowserPanel()
        panel._search.setText("__no_widget_matches__")
        panel.refresh()

        assert panel._cards == {}

        panel._reset_search_only()

        assert panel._search.text() == ""
        assert panel._search_refresh_timer.isActive() is False
        assert panel._cards
        panel.deleteLater()
