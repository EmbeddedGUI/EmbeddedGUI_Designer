"""Qt UI tests for the widget browser panel."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
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
        first_tag = sorted(panel._tag_buttons.keys())[0]
        panel._tag_buttons[first_tag].setChecked(True)

        assert first_tag in [value.lower() for value in isolated_config.widget_browser_active_tags]
        for item in panel._filtered_items():
            item_tags = {str(tag).lower() for tag in item.get("tags", [])}
            assert first_tag in item_tags

        panel._clear_tags_btn.click()
        assert isolated_config.widget_browser_active_tags == []
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
        panel.deleteLater()

    def test_container_cards_include_visual_info_chips(self, qapp, isolated_config):
        from ui_designer.ui.widget_browser import WidgetBrowserPanel

        panel = WidgetBrowserPanel()
        container_card = next(card for card in panel._cards.values() if card.type_name == "linearlayout")
        chips = [
            label.text()
            for label in container_card.findChildren(QLabel)
            if label.objectName() == "widget_browser_card_chip"
        ]

        assert "Container" in chips
        assert len(chips) >= 2
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
        assert panel._category_list.accessibleName() == "Widget categories: All Widgets"
        assert panel._visible_count_chip.accessibleName() == f"Visible widgets: {panel._visible_count_chip.text()}"
        assert panel._clear_tags_btn.toolTip() == "No active widget tags to clear."
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
        assert favorites_lane.accessibleName() == "Quick lane: Favorites. 1 widget"

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
        buttons = {button.text(): button for button in empty_state.findChildren(QPushButton)}
        assert empty_state.accessibleName() == "No widgets match the current filters."
        assert panel._search.toolTip() == "Widget browser search. Current text: __no_widget_matches__."
        assert buttons["Reset Search"].toolTip() == "Clear the current widget browser search text."
        assert buttons["Show All Widgets"].toolTip() == "Reset every widget browser filter and show all widgets."
        panel.deleteLater()
