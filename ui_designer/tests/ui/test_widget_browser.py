"""Qt UI tests for the simplified widget browser panel."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
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
    for index, value in enumerate(panel._category_ids):
        if str(value or "").strip().lower() == str(category_id).strip().lower():
            panel._category_combo.setCurrentIndex(index)
            return
    raise AssertionError(f"category {category_id!r} not found")


def _find_empty_state(panel):
    for index in range(panel._cards_layout.count()):
        layout_item = panel._cards_layout.itemAt(index)
        widget = layout_item.widget() if layout_item is not None else None
        if widget is not None and widget.objectName() == "widget_browser_empty_state":
            return widget
    raise AssertionError("widget_browser_empty_state not found")


@_skip_no_qt
class TestWidgetBrowserPanel:
    def test_browser_uses_compact_header_and_card_layouts(self, qapp, isolated_config):
        from ui_designer.ui.widget_browser import WidgetBrowserPanel

        panel = WidgetBrowserPanel()
        header_layout = panel._header_frame.layout()
        header_margins = header_layout.contentsMargins()
        title_row = header_layout.itemAt(1).layout()
        metrics_layout = panel._metrics_frame.layout()
        filter_layout = panel._filter_bar.layout()
        button_card = next(card for card in panel._cards.values() if card.type_name == "button")
        card_layout = button_card.layout()
        card_margins = card_layout.contentsMargins()

        assert panel.layout().spacing() == 2
        assert (header_margins.left(), header_margins.top(), header_margins.right(), header_margins.bottom()) == (2, 2, 2, 2)
        assert header_layout.spacing() == 2
        assert title_row.spacing() == 2
        assert metrics_layout.spacing() == 2
        assert filter_layout.spacing() == 2
        assert panel._cards_layout.spacing() == 2
        assert panel._category_combo.minimumWidth() == 160
        assert (card_margins.left(), card_margins.top(), card_margins.right(), card_margins.bottom()) == (2, 2, 2, 2)
        assert card_layout.spacing() == 2
        panel.deleteLater()

    def test_category_combo_exposes_expected_simplified_options(self, qapp, isolated_config):
        from ui_designer.ui.widget_browser import WidgetBrowserPanel

        panel = WidgetBrowserPanel()

        options = [
            (panel._category_ids[index], panel._category_combo.itemText(index))
            for index in range(panel._category_combo.count())
        ]

        assert options == [
            ("all", "All"),
            ("favorites", "Favorites"),
            ("recent", "Recent"),
            ("containers", "Containers"),
            ("basics", "Basics"),
            ("layout", "Layout"),
            ("input", "Input"),
            ("navigation", "Navigation"),
            ("display & data", "Display & Data"),
            ("media", "Media"),
            ("decoration", "Decoration"),
            ("custom", "Custom"),
        ]
        panel.deleteLater()

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

    def test_fixed_category_filter_uses_widget_type_categories(self, qapp, isolated_config):
        from ui_designer.ui.widget_browser import WidgetBrowserPanel

        panel = WidgetBrowserPanel()
        _select_category(panel, "layout")
        panel.refresh()

        assert isolated_config.widget_browser_active_category == "layout"
        assert len(panel._cards) > 0
        assert all(str(item.get("category", "")).lower() == "layout" for item in panel._filtered_items())
        panel.deleteLater()

    def test_search_and_insert_target_update_visible_cards(self, qapp, isolated_config):
        from ui_designer.ui.widget_browser import WidgetBrowserPanel

        panel = WidgetBrowserPanel()
        panel.set_insert_target_label("root_group / content")
        panel._search.setText("slider")
        panel.refresh()

        assert panel._insert_target.isHidden() is False
        assert panel._insert_target.text() == "Target: root_group / content"
        assert "slider" in [card.type_name for card in panel._cards.values()]

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
        initial_types = [card.type_name for card in panel._cards.values()]

        panel._search.setText("__no_widget_matches__")

        assert panel._search_refresh_timer.isActive() is True
        assert [card.type_name for card in panel._cards.values()] == initial_types

        QTest.qWait(panel._SEARCH_REFRESH_DEBOUNCE_MS + 40)
        qapp.processEvents()

        assert panel._search_refresh_timer.isActive() is False
        assert panel._cards == {}
        panel.deleteLater()

    def test_record_insert_skips_refresh_when_recent_order_does_not_change(self, qapp, isolated_config, monkeypatch):
        from ui_designer.ui.widget_browser import WidgetBrowserPanel

        isolated_config.widget_browser_recent = ["button", "slider"]
        panel = WidgetBrowserPanel()
        refresh_calls = 0
        original_refresh = panel.refresh

        def counted_refresh():
            nonlocal refresh_calls
            refresh_calls += 1
            return original_refresh()

        monkeypatch.setattr(panel, "refresh", counted_refresh)

        panel.record_insert("button")

        assert refresh_calls == 0
        assert isolated_config.widget_browser_recent == ["button", "slider"]

        panel.record_insert("slider")

        assert refresh_calls == 1
        assert isolated_config.widget_browser_recent[:2] == ["slider", "button"]
        panel.deleteLater()

    def test_card_context_menu_can_reveal_and_toggle_favorite(self, qapp, isolated_config, monkeypatch):
        from ui_designer.ui.widget_browser import WidgetBrowserPanel

        panel = WidgetBrowserPanel()
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

        assert panel._selected_type == "slider"
        assert panel._selected_type in {card.type_name for card in panel._cards.values()}
        panel.deleteLater()

    def test_container_cards_keep_hidden_meta_metadata(self, qapp, isolated_config):
        from ui_designer.ui.widget_browser import WidgetBrowserPanel

        panel = WidgetBrowserPanel()
        panel._select_card("linearlayout")
        container_card = next(card for card in panel._cards.values() if card.type_name == "linearlayout")
        meta_label = next(
            label for label in container_card.findChildren(QLabel) if label.objectName() == "widget_browser_card_meta"
        )

        assert meta_label.text() == "Container"
        assert meta_label.isHidden() is True
        assert meta_label.toolTip() == "Container"
        assert meta_label.accessibleName() == "Widget hint: Container"
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
            f"Widget Browser: {visible_text}. Category: All. Search: none. "
            f"Insert target: Current page root. Selected: {selected_label}."
        )
        assert panel._search.toolTip() == "Widget browser search. Current text: none."
        assert panel._search.accessibleName() == "Widget browser search: none."
        assert panel._category_combo.accessibleName() == "Widget categories: All"
        assert panel._insert_target.isHidden() is True
        assert panel._scroll.toolTip().startswith("Widget browser results: ")
        panel.deleteLater()

    def test_browser_header_context_tracks_scope_search_and_insert_target(self, qapp, isolated_config):
        from ui_designer.ui.widget_browser import WidgetBrowserPanel

        isolated_config.widget_browser_favorites = ["button"]
        panel = WidgetBrowserPanel()

        selected_label = next(
            (
                str(card._item.get("display_name", card.type_name) or card.type_name)
                for card in panel._cards.values()
                if card.type_name == panel._selected_type
            ),
            "none",
        )
        visible_label = f"{len(panel._cards)} component" if len(panel._cards) == 1 else f"{len(panel._cards)} components"
        initial_meta = f"Showing {visible_label} in All. Insert target: Current page root. Selected: {selected_label}."

        assert panel._header_eyebrow.accessibleName() == "Component catalog workspace surface."
        assert panel._header_eyebrow.isHidden() is True
        assert panel._subtitle_label.text() == initial_meta
        assert panel._subtitle_label.isHidden() is True
        assert panel._header_frame.accessibleName() == f"Components header. {initial_meta}"
        assert panel._visible_count_chip.text() == f"{len(panel._cards)} visible"
        assert panel._category_summary_chip.text() == "All Components"
        assert panel._metrics_frame.isHidden() is True
        assert panel._metrics_frame.accessibleName() == (
            f"Component browser metrics: {visible_label}. Scope: All Components."
        )

        panel.set_insert_target_label("root_group / content")
        _select_category(panel, "favorites")
        panel._search.setText("button")
        panel.refresh()

        selected_label = next(
            (
                str(card._item.get("display_name", card.type_name) or card.type_name)
                for card in panel._cards.values()
                if card.type_name == panel._selected_type
            ),
            "none",
        )
        scoped_meta = (
            f"Showing 1 component in Favorites. Insert target: root_group / content. "
            f"Search: button. Selected: {selected_label}."
        )

        assert panel._subtitle_label.text() == scoped_meta
        assert panel._subtitle_label.toolTip() == scoped_meta
        assert panel._subtitle_label.isHidden() is True
        assert panel._header_frame.accessibleName() == f"Components header. {scoped_meta}"
        assert panel._insert_target.toolTip() == "Current insert target: root_group / content"
        assert panel._visible_count_chip.text() == "1 visible"
        assert panel._category_summary_chip.text() == "Favorites + Search"
        assert panel._metrics_frame.accessibleName() == (
            "Component browser metrics: 1 component. Scope: Favorites + Search."
        )
        panel.deleteLater()

    def test_browser_metadata_helper_skips_no_op_tooltip_rewrites(self, qapp, isolated_config, monkeypatch):
        from ui_designer.ui.widget_browser import WidgetBrowserPanel

        panel = WidgetBrowserPanel()
        panel._scroll.setProperty("_widget_browser_tooltip_snapshot", None)

        tooltip_calls = 0
        original_set_tooltip = panel._scroll.setToolTip

        def counted_set_tooltip(text):
            nonlocal tooltip_calls
            tooltip_calls += 1
            return original_set_tooltip(text)

        monkeypatch.setattr(panel._scroll, "setToolTip", counted_set_tooltip)

        panel._update_accessibility_summary(len(panel._cards))
        assert tooltip_calls == 1

        tooltip_calls = 0
        panel._update_accessibility_summary(len(panel._cards))
        assert tooltip_calls == 0

        panel._search.setText("slider")
        panel.refresh()
        assert tooltip_calls == 1
        assert panel._scroll.statusTip() == panel._scroll.toolTip()
        panel.deleteLater()

    def test_card_insert_visibility_skips_no_op_rewrites(self, qapp, isolated_config, monkeypatch):
        from ui_designer.ui.widget_browser import WidgetBrowserPanel

        panel = WidgetBrowserPanel()
        button_card = next(card for card in panel._cards.values() if card.type_name == "button")
        button_card._insert_btn.setProperty("_widget_browser_visible_snapshot", None)

        visible_calls = 0
        original_set_visible = button_card._insert_btn.setVisible

        def counted_set_visible(value):
            nonlocal visible_calls
            visible_calls += 1
            return original_set_visible(value)

        monkeypatch.setattr(button_card._insert_btn, "setVisible", counted_set_visible)

        button_card.set_selected(True)
        assert visible_calls == 1

        visible_calls = 0
        button_card.set_selected(True)
        assert visible_calls == 0

        button_card.set_selected(False)
        assert visible_calls == 1
        assert button_card._insert_btn.isHidden() is True
        panel.deleteLater()

    def test_insert_target_visibility_skips_no_op_rewrites(self, qapp, isolated_config, monkeypatch):
        from ui_designer.ui.widget_browser import WidgetBrowserPanel

        panel = WidgetBrowserPanel()
        panel._insert_target.setProperty("_widget_browser_visible_snapshot", None)

        visible_calls = 0
        original_set_visible = panel._insert_target.setVisible

        def counted_set_visible(value):
            nonlocal visible_calls
            visible_calls += 1
            return original_set_visible(value)

        monkeypatch.setattr(panel._insert_target, "setVisible", counted_set_visible)

        panel.set_insert_target_label("root_group / content")
        assert visible_calls == 1

        visible_calls = 0
        panel.set_insert_target_label("root_group / footer")
        assert visible_calls == 0

        panel.set_insert_target_label("Current page root")
        assert visible_calls == 1
        assert panel._insert_target.isHidden() is True
        panel.deleteLater()

    def test_card_metadata_tracks_selection_and_favorite_state(self, qapp, isolated_config):
        from ui_designer.ui.widget_browser import WidgetBrowserPanel

        panel = WidgetBrowserPanel()
        panel._select_card("button")
        button_card = next(card for card in panel._cards.values() if card.type_name == "button")
        display_name = str(button_card._item.get("display_name", button_card.type_name) or button_card.type_name)
        category = str(button_card._item.get("category", "") or "Uncategorized").strip() or "Uncategorized"
        container_text = "yes" if bool(button_card._item.get("is_container")) else "no"

        assert button_card.accessibleName() == (
            f"Widget row: {display_name}. Category {category}. Container {container_text}. Favorite no. Selected yes."
        )
        assert button_card._favorite_btn.toolTip() == f"Add {display_name} to favorites."
        assert button_card._insert_btn.toolTip() == f"Insert {display_name} into the current target."

        panel._toggle_favorite("button")
        button_card = next(card for card in panel._cards.values() if card.type_name == "button")
        assert button_card._favorite_btn.toolTip() == f"Remove {display_name} from favorites."
        assert f"Selected: {display_name}." in panel.accessibleName()
        panel.deleteLater()

    def test_empty_state_for_search_uses_clear_search_action(self, qapp, isolated_config):
        from ui_designer.ui.widget_browser import WidgetBrowserPanel

        panel = WidgetBrowserPanel()
        panel._search.setText("__no_widget_matches__")
        panel.refresh()

        empty_state = _find_empty_state(panel)
        empty_layout = empty_state.layout()
        empty_margins = empty_layout.contentsMargins()
        hint = next(
            label for label in empty_state.findChildren(QLabel) if label.objectName() == "workspace_section_subtitle"
        )
        buttons = {button.text(): button for button in empty_state.findChildren(QPushButton)}

        assert (empty_margins.left(), empty_margins.top(), empty_margins.right(), empty_margins.bottom()) == (12, 12, 12, 12)
        assert empty_layout.spacing() == 4
        assert hint.text() == "No matching widgets. Clear search to show matching widgets."
        assert sorted(buttons) == ["Clear Search"]
        assert buttons["Clear Search"].toolTip() == "Clear the widget browser search."
        panel.deleteLater()

    def test_empty_state_for_category_uses_show_all_action(self, qapp, isolated_config):
        from ui_designer.ui.widget_browser import WidgetBrowserPanel

        panel = WidgetBrowserPanel()
        _select_category(panel, "favorites")
        panel.refresh()

        empty_state = _find_empty_state(panel)
        hint = next(
            label for label in empty_state.findChildren(QLabel) if label.objectName() == "workspace_section_subtitle"
        )
        buttons = {button.text(): button for button in empty_state.findChildren(QPushButton)}

        assert hint.text() == "No matching widgets. Switch back to All to browse the full widget catalog."
        assert sorted(buttons) == ["Show All Components"]

        buttons["Show All Components"].click()

        assert panel._selected_category() == "all"
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
