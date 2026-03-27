"""Qt UI tests for the widget browser panel."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtWidgets import QApplication, QLabel

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
