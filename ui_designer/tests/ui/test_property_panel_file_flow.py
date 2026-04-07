"""Qt UI tests for PropertyPanel file browsing and auto-import."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QApplication, QFormLayout, QFrame, QGroupBox, QHBoxLayout, QLabel, QWidget, QToolButton

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


def _find_group(panel, title):
    return panel.property_group(title)


def _form_labels(group):
    form = group.layout()
    labels = []
    for row in range(form.rowCount()):
        item = form.itemAt(row, QFormLayout.LabelRole)
        if item and item.widget():
            labels.append(item.widget().text())
    return labels


def _form_value_text(group, label_text):
    form = group.layout()
    for row in range(form.rowCount()):
        label_item = form.itemAt(row, QFormLayout.LabelRole)
        field_item = form.itemAt(row, QFormLayout.FieldRole)
        if label_item and label_item.widget() and label_item.widget().text() == label_text:
            if field_item and field_item.widget():
                return field_item.widget().text()
            break
    raise AssertionError(f"Form row not found: {label_text}")


def _group_label_texts(group):
    return [label.text() for label in group.findChildren(QLabel)]


def _find_hint_strip(panel):
    frame = panel.findChild(QFrame, "workspace_hint_strip")
    if frame is None:
        raise AssertionError("Hint strip not found")
    return frame


@_skip_no_qt
class TestPropertyPanelFileFlow:
    def test_rebuild_form_does_not_leave_stale_group_widgets_attached(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.property_panel import PropertyPanel

        first = WidgetModel("label", name="first")
        second = WidgetModel("label", name="second")

        panel = PropertyPanel()
        panel.set_widget(first)
        first_group_count = len(panel._property_sections)

        panel.set_widget(second)
        second_group_count = len(panel._property_sections)

        assert first_group_count > 0
        assert second_group_count == first_group_count
        panel.deleteLater()

    def test_property_metric_cards_use_compact_flat_layout(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.property_panel import PropertyPanel

        widget = WidgetModel("label", name="title", x=10, y=20, width=80, height=24)

        panel = PropertyPanel()
        panel.set_widget(widget)

        header = panel._layout.itemAt(0).widget()
        metric_grid = header.layout().itemAt(3).layout()
        metric_cards = header.findChildren(QFrame, "property_panel_metric_card")

        assert len(metric_cards) == 4
        assert metric_grid.horizontalSpacing() == 2
        assert metric_grid.verticalSpacing() == 2
        card_layout = metric_cards[0].layout()
        assert isinstance(card_layout, QHBoxLayout)
        assert card_layout.spacing() == 4
        assert card_layout.itemAt(0).widget().objectName() == "property_panel_metric_label"
        assert card_layout.itemAt(2).widget().objectName() == "property_panel_metric_value"
        margins = card_layout.contentsMargins()
        assert margins.left() == 6
        assert margins.top() == 3
        assert margins.right() == 6
        assert margins.bottom() == 3
        panel.deleteLater()

    def test_empty_state_and_search_metadata(self, qapp):
        from ui_designer.ui.property_panel import PropertyPanel

        panel = PropertyPanel()
        root_layout = panel.layout()
        empty_layout = panel._no_selection_label.layout()
        context_layout = panel._context_frame.layout()
        content_layout = panel._layout

        assert panel._search_edit.isHidden() is True
        assert panel.accessibleName() == "Property panel: no widget selected. Search: none."
        assert panel.toolTip() == panel.accessibleName()
        assert panel._context_frame.isHidden() is True
        assert (root_layout.contentsMargins().left(), root_layout.contentsMargins().top()) == (6, 6)
        assert (root_layout.contentsMargins().right(), root_layout.contentsMargins().bottom()) == (6, 6)
        assert root_layout.spacing() == 4
        assert (context_layout.contentsMargins().left(), context_layout.contentsMargins().top()) == (0, 0)
        assert (context_layout.contentsMargins().right(), context_layout.contentsMargins().bottom()) == (0, 0)
        assert context_layout.spacing() == 2
        assert (content_layout.contentsMargins().left(), content_layout.contentsMargins().top()) == (2, 4)
        assert (content_layout.contentsMargins().right(), content_layout.contentsMargins().bottom()) == (2, 4)
        assert content_layout.spacing() == 4
        assert (empty_layout.contentsMargins().left(), empty_layout.contentsMargins().top()) == (6, 8)
        assert (empty_layout.contentsMargins().right(), empty_layout.contentsMargins().bottom()) == (6, 8)
        assert empty_layout.spacing() == 2
        assert panel._search_edit.toolTip() == "Filter visible property rows by label. Current filter: none."
        assert panel._search_edit.statusTip() == panel._search_edit.toolTip()
        assert panel._search_edit.accessibleName() == "Property search: none"
        assert panel._overview_eyebrow.isHidden() is True
        assert panel._search_hint.isHidden() is True
        assert panel._no_selection_label.toolTip() == "Select a widget from the canvas or tree to edit its properties."
        assert panel._no_selection_label.accessibleName() == "Property panel empty state: No widget selected."
        empty_subtitle = next(
            label
            for label in panel._no_selection_label.findChildren(QLabel)
            if label.objectName() == "workspace_section_subtitle"
        )
        assert empty_subtitle.accessibleName() == empty_subtitle.text()
        assert empty_subtitle.isHidden() is False

        panel._search_edit.setText("font")

        assert panel._search_edit.accessibleName() == "Property search: font"
        assert panel.toolTip() == "Property panel: no widget selected. Search: font."
        panel.deleteLater()

    def test_single_selection_header_exposes_engineering_metadata(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.property_panel import PropertyPanel

        widget = WidgetModel("label", name="title", x=10, y=20, width=80, height=24)

        panel = PropertyPanel()
        panel.set_widget(widget)

        header = panel._layout.itemAt(0).widget()
        eyebrow = header.findChild(QLabel, "property_panel_header_eyebrow")
        meta = header.findChild(QLabel, "property_panel_header_meta")
        title = next(
            label
            for label in header.findChildren(QLabel)
            if label.objectName() == "workspace_section_title" and label.text() == "title"
        )
        subtitle = next(
            label
            for label in header.findChildren(QLabel)
            if label.objectName() == "workspace_section_subtitle"
        )
        chips = [label for label in header.findChildren(QLabel) if label.objectName() == "workspace_status_chip"]
        header_layout = header.layout()
        header_margins = header_layout.contentsMargins()
        chips_row = header_layout.itemAt(4).layout()

        assert header.objectName() == "workspace_panel_header"
        assert (header_margins.left(), header_margins.top(), header_margins.right(), header_margins.bottom()) == (6, 6, 6, 6)
        assert header_layout.spacing() == 4
        assert chips_row.spacing() == 2
        assert panel._context_frame.isHidden() is True
        assert header.accessibleName() == f"Property header: title. {subtitle.text()}."
        assert eyebrow.accessibleName() == "Property inspection surface."
        assert eyebrow.isHidden() is True
        assert title.accessibleName() == "Selected widget: title."
        assert subtitle.accessibleName() == f"Widget type: {subtitle.text()}."
        assert subtitle.isHidden() is True
        assert meta.accessibleName() == meta.text()
        assert meta.isHidden() is True
        assert panel._header_size_chip.isHidden() is True
        assert all(chip.property("chipVariant") == "property" for chip in chips)
        assert any(chip.accessibleName() == "Widget size: 80 by 24." for chip in chips)
        panel.deleteLater()

    def test_single_selection_groups_use_compact_inspector_form_layouts(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.property_panel import PropertyPanel

        widget = WidgetModel("label", name="title", x=10, y=20, width=80, height=24)

        panel = PropertyPanel()
        panel.set_widget(widget)

        for title in ("Layout", "Basic", "Data"):
            group = _find_group(panel, title)
            form = group.layout()
            margins = form.contentsMargins()
            body = group.content_frame()

            assert group.objectName() == "inspector_collapsible_group"
            assert body.objectName() == "inspector_group_body"
            assert group.content_indent() > 0
            assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (0, 0, 0, 0)
            assert form.verticalSpacing() == 4
            assert form.horizontalSpacing() == 0

        panel.deleteLater()

    def test_single_selection_appearance_group_uses_compact_row_labels(self, qapp):
        from qfluentwidgets import CheckBox
        from ui_designer.model.widget_model import BackgroundModel, WidgetModel
        from ui_designer.ui.property_panel import PropertyPanel

        widget = WidgetModel("label", name="title", x=10, y=20, width=80, height=24)
        bg = BackgroundModel()
        bg.bg_type = "round_rectangle_corners"
        bg.stroke_width = 2
        bg.has_pressed = True
        widget.background = bg

        panel = PropertyPanel()
        panel.set_widget(widget)

        appearance_group = _find_group(panel, "Appearance")
        labels = _form_labels(appearance_group)

        assert "Type:" in labels
        assert "Color:" in labels
        assert "Alpha:" in labels
        assert "TL:" in labels
        assert "BL:" in labels
        assert "TR:" in labels
        assert "BR:" in labels
        assert "Stroke:" in labels
        assert "Border:" in labels
        assert "Border A:" in labels
        assert "Pressed:" in labels
        assert "Left Top:" not in labels
        assert "Left Bottom:" not in labels
        assert "Right Top:" not in labels
        assert "Right Bottom:" not in labels
        assert "Stroke Width:" not in labels
        assert "Stroke Color:" not in labels
        assert "Stroke Alpha:" not in labels
        assert "Pressed Color:" not in labels
        pressed_toggle = next(box for box in appearance_group.findChildren(CheckBox) if box.text())
        assert pressed_toggle.text() == "Pressed state"
        panel.deleteLater()

    def test_single_selection_data_group_uses_compact_font_row_labels(self, qapp):
        from ui_designer.model.resource_catalog import ResourceCatalog
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.property_panel import PropertyPanel

        widget = WidgetModel("label", name="title")
        widget.properties["font_file"] = "demo.ttf"
        panel = PropertyPanel()
        catalog = ResourceCatalog()
        catalog.add_font("demo.ttf")
        panel.set_resource_catalog(catalog)
        panel.set_widget(widget)

        data_group = _find_group(panel, "Data")
        labels = _form_labels(data_group)

        assert "Font:" in labels
        assert "Px:" in labels
        assert "Bits:" in labels
        assert "Ext:" in labels
        assert "Text:" in labels
        assert "Pixelsize:" not in labels
        assert "Fontbitsize:" not in labels
        assert "External:" not in labels
        assert "Text File:" not in labels
        panel.deleteLater()

    def test_collapsed_groups_hide_nested_form_widgets(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.property_panel import PropertyPanel

        widget = WidgetModel("label", name="title")
        widget.properties["font_builtin"] = "&egui_res_font_montserrat_8_4"

        panel = PropertyPanel()
        panel.set_widget(widget)
        panel.show()
        qapp.processEvents()

        text_group = _find_group(panel, "Text")
        assert text_group.isChecked() is False
        assert text_group.title() == "Text"
        assert text_group.maximumHeight() >= 32
        assert all(not child.isVisible() for child in text_group.findChildren(QWidget))
        panel.deleteLater()

    def test_property_grid_section_click_toggles_expanded_state(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.property_panel import PropertyPanel

        widget = WidgetModel("label", name="title")
        panel = PropertyPanel()
        panel.set_widget(widget)

        group = _find_group(panel, "Text")
        item = panel._property_sections["Text"]["item"]

        assert group.isChecked() is False
        panel._on_property_tree_item_clicked(item, 0)
        assert group.isChecked() is True
        panel._on_property_tree_item_clicked(item, 0)
        assert group.isChecked() is False
        panel.deleteLater()

    def test_property_grid_focus_highlights_active_row(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.property_panel import PropertyPanel

        widget = WidgetModel("label", name="title", x=10, y=20, width=80, height=24)
        panel = PropertyPanel()
        panel.set_widget(widget)
        panel.show()
        qapp.processEvents()

        x_row = panel._property_grid_row_data(panel._editors["x"])
        name_row = panel._property_grid_row_data(panel._editors["name"])

        panel._editors["x"].setFocus()
        qapp.processEvents()
        assert x_row["label_frame"].property("focusActive") is True
        assert name_row["label_frame"].property("focusActive") in (False, None)

        panel._editors["name"].setFocus()
        qapp.processEvents()
        assert name_row["label_frame"].property("focusActive") is True
        assert x_row["label_frame"].property("focusActive") is False
        panel.deleteLater()

    def test_property_grid_hover_highlights_row(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.property_panel import PropertyPanel

        widget = WidgetModel("label", name="title", x=10, y=20, width=80, height=24)
        panel = PropertyPanel()
        panel.set_widget(widget)

        x_row = panel._property_grid_row_data(panel._editors["x"])
        panel._set_property_grid_row_hover(panel._editors["x"], True)
        assert x_row["label_frame"].property("hoverActive") is True
        panel._set_property_grid_row_hover(panel._editors["x"], False)
        assert x_row["label_frame"].property("hoverActive") is False
        panel.deleteLater()

    def test_property_grid_section_style_tracks_expanded_state(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.property_panel import PropertyPanel

        widget = WidgetModel("label", name="title")
        panel = PropertyPanel()
        panel.set_widget(widget)

        text_section = panel._property_sections["Text"]
        assert text_section["header_frame"].property("sectionExpanded") is False
        assert isinstance(text_section["arrow_label"], QToolButton)
        assert text_section["arrow_label"].arrowType() == Qt.RightArrow
        panel._on_property_tree_item_clicked(text_section["item"], 0)
        assert text_section["header_frame"].property("sectionExpanded") is True
        assert text_section["arrow_label"].arrowType() == Qt.DownArrow
        panel.deleteLater()

    def test_property_grid_section_hover_tracks_state(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.property_panel import PropertyPanel

        widget = WidgetModel("label", name="title")
        panel = PropertyPanel()
        panel.set_widget(widget)

        text_section = panel._property_sections["Text"]
        panel._refresh_property_section_hover(text_section, hovered=True)
        assert text_section["header_frame"].property("sectionHovered") is True
        panel._refresh_property_section_hover(text_section, hovered=False)
        assert text_section["header_frame"].property("sectionHovered") is False
        panel.deleteLater()

    def test_property_grid_preserves_name_column_width_across_rebuilds(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.property_panel import PropertyPanel

        first = WidgetModel("label", name="first")
        second = WidgetModel("label", name="second")

        panel = PropertyPanel()
        panel.set_widget(first)
        panel._property_tree.setColumnWidth(0, 214)
        panel._on_property_tree_section_resized(0, 176, 214)

        panel.set_widget(second)

        assert panel._property_tree.columnWidth(0) == 214
        panel.deleteLater()

    def test_property_grid_name_column_width_setter_clamps_and_applies(self, qapp):
        from ui_designer.ui.property_panel import PropertyPanel

        panel = PropertyPanel()
        panel.set_property_grid_name_column_width(96)
        assert panel.property_grid_name_column_width() == 120
        assert panel._property_tree.columnWidth(0) == 120

        panel.set_property_grid_name_column_width(248)
        assert panel.property_grid_name_column_width() == 248
        assert panel._property_tree.columnWidth(0) == 248
        panel.deleteLater()

    def test_panel_metadata_helper_skips_no_op_tooltip_rewrites(self, qapp, monkeypatch):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.property_panel import PropertyPanel

        panel = PropertyPanel()
        panel.setProperty("_property_panel_tooltip_snapshot", None)

        tooltip_calls = 0
        original_set_tooltip = panel.setToolTip

        def counted_set_tooltip(text):
            nonlocal tooltip_calls
            tooltip_calls += 1
            return original_set_tooltip(text)

        monkeypatch.setattr(panel, "setToolTip", counted_set_tooltip)

        panel._update_panel_metadata()
        assert tooltip_calls == 1

        tooltip_calls = 0
        panel._update_panel_metadata()
        assert tooltip_calls == 0

        panel.set_widget(WidgetModel("label", name="title"))
        assert tooltip_calls == 1
        assert panel.statusTip() == panel.toolTip()
        panel.deleteLater()

    def test_search_field_is_contextual_and_reapplies_after_form_rebuild(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.property_panel import PropertyPanel

        first = WidgetModel("label", name="first")
        second = WidgetModel("label", name="second")

        panel = PropertyPanel()
        assert panel._search_edit.isHidden() is True
        assert panel._context_frame.isHidden() is True
        assert panel._search_edit.placeholderText() == "Select a widget to filter properties"
        assert panel._context_meta.text() == "Select a widget to inspect properties, resources, and callbacks."

        panel.set_widget(first)
        assert panel._search_edit.isHidden() is False
        assert panel._context_frame.isHidden() is True
        assert panel._search_hint.isHidden() is True
        assert panel._search_edit.placeholderText() == "Filter widget properties..."
        assert panel._context_meta.text() == "Label (label) | Freeform | 0 asset bindings | 0 active callbacks."

        panel._search_edit.setText("name")
        assert _find_group(panel, "Basic").isHidden() is False
        assert _find_group(panel, "Data").isHidden() is True

        panel.set_widget(second)

        assert panel._search_edit.isHidden() is False
        assert panel._search_edit.text() == "name"
        assert panel._search_edit.placeholderText() == "Filter widget properties..."
        assert _find_group(panel, "Basic").isHidden() is False
        assert _find_group(panel, "Data").isHidden() is True

        panel.set_selection([first, second], primary=second)
        assert panel._search_edit.isHidden() is False
        assert panel._context_frame.isHidden() is True
        assert panel._search_hint.isHidden() is True
        assert panel._search_edit.placeholderText() == "Filter shared properties..."
        assert panel._context_meta.text().startswith("Primary: second | 1 type | ")
        assert "mixed field" in panel._context_meta.text()

        panel.set_widget(None)

        assert panel._search_edit.isHidden() is True
        assert panel._context_frame.isHidden() is True
        assert panel._context_meta.text() == "Select a widget to inspect properties, resources, and callbacks."
        panel.deleteLater()

    def test_file_selector_sets_accessibility_metadata(self, qapp):
        from qfluentwidgets import ToolButton
        from ui_designer.ui.property_panel import PropertyPanel

        panel = PropertyPanel()
        selector = panel._create_file_selector("font_file", "title.ttf", ["title.ttf"], "Font files (*.ttf *.otf)")
        combo = panel._editors["prop_font_file"]
        browse_btn = selector.findChild(ToolButton)

        assert combo.toolTip() == "Font File: title.ttf. Choose a project resource file or type a filename."
        assert combo.statusTip() == combo.toolTip()
        assert combo.accessibleName() == "Font File selector: title.ttf"
        assert browse_btn is not None
        assert browse_btn.text() == "Pick"
        assert browse_btn.toolTip() == "Pick font files for Font File."
        assert browse_btn.statusTip() == browse_btn.toolTip()
        assert browse_btn.accessibleName() == "Pick Font File"
        panel.deleteLater()

    def test_font_text_file_selector_exposes_generate_charset_button(self, qapp):
        from qfluentwidgets import ToolButton
        from ui_designer.ui.property_panel import PropertyPanel

        panel = PropertyPanel()
        selector = panel._create_file_selector("font_text_file", "chars.txt", ["chars.txt"], "Text files (*.txt)")
        buttons = selector.findChildren(ToolButton)

        assert len(buttons) == 2
        assert buttons[0].text() == "Pick"
        assert buttons[1].text() == "Gen"
        assert buttons[1].toolTip() == "Open the charset generator using the current font and text resource context."
        assert buttons[1].accessibleName() == "Generate charset for Text"
        panel.deleteLater()

    def test_generate_charset_button_emits_signal_with_font_context(self, qapp):
        from qfluentwidgets import ToolButton
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.property_panel import PropertyPanel

        widget = WidgetModel("label", name="title")
        widget.properties["font_file"] = "demo_font.ttf"
        widget.properties["font_text_file"] = "chars.txt"

        panel = PropertyPanel()
        panel.set_widget(widget)
        selector = panel._create_file_selector("font_text_file", "chars.txt", ["chars.txt"], "Text files (*.txt)")
        buttons = selector.findChildren(ToolButton)
        generated = []
        panel.generate_charset_requested.connect(lambda resource_type, source_name, initial_filename: generated.append((resource_type, source_name, initial_filename)))

        buttons[1].click()

        assert generated == [("font", "demo_font.ttf", "chars.txt")]
        panel.deleteLater()

    def test_browse_file_warns_when_project_resource_dir_is_missing(self, qapp, monkeypatch):
        from ui_designer.ui.property_panel import PropertyPanel

        panel = PropertyPanel()
        selector = panel._create_file_selector("image_file", "", [], "Images (*.png *.bmp *.jpg *.jpeg)")
        combo = panel._editors["prop_image_file"]
        warnings = []
        dialog_calls = []

        monkeypatch.setattr("ui_designer.ui.property_panel.QMessageBox.warning", lambda *args: warnings.append(args[1:]))
        monkeypatch.setattr(
            "ui_designer.ui.property_panel.QFileDialog.getOpenFileName",
            lambda *args, **kwargs: dialog_calls.append(args) or ("", ""),
        )

        panel._browse_file(combo, "Images (*.png *.bmp *.jpg *.jpeg)")

        assert warnings
        assert warnings[0][0] == "Resource Directory Missing"
        assert dialog_calls == []
        assert combo.currentText() == ""
        assert selector is not None
        panel.deleteLater()

    def test_browse_file_uses_images_subdir_as_default_directory(self, qapp, tmp_path, monkeypatch):
        from ui_designer.ui.property_panel import PropertyPanel

        resource_dir = tmp_path / "project" / ".eguiproject" / "resources"
        images_dir = resource_dir / "images"
        images_dir.mkdir(parents=True)
        captured = {}

        panel = PropertyPanel()
        panel.set_source_resource_dir(str(resource_dir))
        selector = panel._create_file_selector("image_file", "", [], "Images (*.png *.bmp *.jpg *.jpeg)")
        combo = panel._editors["prop_image_file"]

        def fake_get_open_file_name(parent, title, directory, filters):
            captured["title"] = title
            captured["directory"] = directory
            captured["filters"] = filters
            return "", ""

        monkeypatch.setattr("ui_designer.ui.property_panel.QFileDialog.getOpenFileName", fake_get_open_file_name)

        panel._browse_file(combo, "Images (*.png *.bmp *.jpg *.jpeg)")

        assert captured["title"] == "Select File"
        assert captured["directory"] == os.path.normpath(os.path.abspath(images_dir))
        assert "Images" in captured["filters"]
        assert selector is not None
        panel.deleteLater()

    def test_browse_file_auto_imports_image_and_emits_resource_imported(self, qapp, tmp_path, monkeypatch):
        from ui_designer.model.resource_catalog import ResourceCatalog
        from ui_designer.ui.property_panel import PropertyPanel

        resource_dir = tmp_path / "project" / ".eguiproject" / "resources"
        images_dir = resource_dir / "images"
        images_dir.mkdir(parents=True)
        external_dir = tmp_path / "external"
        external_dir.mkdir()
        image_path = external_dir / "star.png"
        image_path.write_bytes(b"PNG")

        panel = PropertyPanel()
        panel.set_source_resource_dir(str(resource_dir))
        catalog = ResourceCatalog()
        panel.set_resource_catalog(catalog)
        selector = panel._create_file_selector("image_file", "", [], "Images (*.png *.bmp *.jpg *.jpeg)")
        combo = panel._editors["prop_image_file"]
        imported_events = []
        panel.resource_imported.connect(lambda: imported_events.append("imported"))

        monkeypatch.setattr(
            "ui_designer.ui.property_panel.QFileDialog.getOpenFileName",
            lambda *args, **kwargs: (str(image_path), "Images (*.png *.bmp *.jpg *.jpeg)"),
        )

        panel._browse_file(combo, "Images (*.png *.bmp *.jpg *.jpeg)")

        assert (images_dir / "star.png").is_file()
        assert catalog.has_image("star.png")
        assert combo.currentText() == "star.png"
        assert imported_events == ["imported"]
        assert selector is not None
        panel.deleteLater()

    def test_browse_file_prefers_last_external_directory_after_import(self, qapp, tmp_path, monkeypatch):
        from ui_designer.model.resource_catalog import ResourceCatalog
        from ui_designer.ui.property_panel import PropertyPanel

        resource_dir = tmp_path / "project" / ".eguiproject" / "resources"
        images_dir = resource_dir / "images"
        images_dir.mkdir(parents=True)
        external_dir = tmp_path / "external"
        external_dir.mkdir()
        image_path = external_dir / "star.png"
        image_path.write_bytes(b"PNG")
        captured = {}

        panel = PropertyPanel()
        panel.set_source_resource_dir(str(resource_dir))
        panel.set_resource_catalog(ResourceCatalog())
        selector = panel._create_file_selector("image_file", "", [], "Images (*.png *.bmp *.jpg *.jpeg)")
        combo = panel._editors["prop_image_file"]

        monkeypatch.setattr(
            "ui_designer.ui.property_panel.QFileDialog.getOpenFileName",
            lambda *args, **kwargs: (str(image_path), "Images (*.png *.bmp *.jpg *.jpeg)"),
        )
        panel._browse_file(combo, "Images (*.png *.bmp *.jpg *.jpeg)")

        def fake_get_open_file_name_second(parent, title, directory, filters):
            captured["directory"] = directory
            return "", ""

        monkeypatch.setattr("ui_designer.ui.property_panel.QFileDialog.getOpenFileName", fake_get_open_file_name_second)
        panel._browse_file(combo, "Images (*.png *.bmp *.jpg *.jpeg)")

        assert captured["directory"] == os.path.normpath(os.path.abspath(external_dir))
        assert selector is not None
        panel.deleteLater()

    def test_browse_file_selects_existing_catalog_image_without_reimport(self, qapp, tmp_path, monkeypatch):
        from ui_designer.model.resource_catalog import ResourceCatalog
        from ui_designer.ui.property_panel import PropertyPanel

        resource_dir = tmp_path / "project" / ".eguiproject" / "resources"
        images_dir = resource_dir / "images"
        images_dir.mkdir(parents=True)
        image_path = images_dir / "star.png"
        image_path.write_bytes(b"PNG")

        panel = PropertyPanel()
        panel.set_source_resource_dir(str(resource_dir))
        catalog = ResourceCatalog()
        catalog.add_image("star.png")
        panel.set_resource_catalog(catalog)
        selector = panel._create_file_selector("image_file", "", ["star.png"], "Images (*.png *.bmp *.jpg *.jpeg)")
        combo = panel._editors["prop_image_file"]
        imported_events = []
        panel.resource_imported.connect(lambda: imported_events.append("imported"))

        monkeypatch.setattr(
            "ui_designer.ui.property_panel.QFileDialog.getOpenFileName",
            lambda *args, **kwargs: (str(image_path), "Images (*.png *.bmp *.jpg *.jpeg)"),
        )

        panel._browse_file(combo, "Images (*.png *.bmp *.jpg *.jpeg)")

        assert catalog.images == ["star.png"]
        assert combo.currentText() == "star.png"
        assert imported_events == []
        assert selector is not None
        panel.deleteLater()

    def test_browse_text_file_uses_resource_root_as_default_directory(self, qapp, tmp_path, monkeypatch):
        from ui_designer.ui.property_panel import PropertyPanel

        resource_dir = tmp_path / "project" / ".eguiproject" / "resources"
        resource_dir.mkdir(parents=True)
        captured = {}

        panel = PropertyPanel()
        panel.set_source_resource_dir(str(resource_dir))
        selector = panel._create_file_selector("font_text_file", "", [], "Text files (*.txt)")
        combo = panel._editors["prop_font_text_file"]

        def fake_get_open_file_name(parent, title, directory, filters):
            captured["title"] = title
            captured["directory"] = directory
            captured["filters"] = filters
            return "", ""

        monkeypatch.setattr("ui_designer.ui.property_panel.QFileDialog.getOpenFileName", fake_get_open_file_name)

        panel._browse_file(combo, "Text files (*.txt)")

        assert captured["title"] == "Select File"
        assert captured["directory"] == os.path.normpath(os.path.abspath(resource_dir))
        assert "Text files" in captured["filters"]
        assert selector is not None
        panel.deleteLater()

    def test_browse_text_file_auto_imports_and_emits_resource_imported(self, qapp, tmp_path, monkeypatch):
        from ui_designer.model.resource_catalog import ResourceCatalog
        from ui_designer.ui.property_panel import PropertyPanel

        resource_dir = tmp_path / "project" / ".eguiproject" / "resources"
        resource_dir.mkdir(parents=True)
        external_dir = tmp_path / "external"
        external_dir.mkdir()
        text_path = external_dir / "chars.txt"
        text_path.write_text("abc\n123\n", encoding="utf-8")

        panel = PropertyPanel()
        panel.set_source_resource_dir(str(resource_dir))
        catalog = ResourceCatalog()
        panel.set_resource_catalog(catalog)
        selector = panel._create_file_selector("font_text_file", "", [], "Text files (*.txt)")
        combo = panel._editors["prop_font_text_file"]
        imported_events = []
        panel.resource_imported.connect(lambda: imported_events.append("imported"))

        monkeypatch.setattr(
            "ui_designer.ui.property_panel.QFileDialog.getOpenFileName",
            lambda *args, **kwargs: (str(text_path), "Text files (*.txt)"),
        )

        panel._browse_file(combo, "Text files (*.txt)")

        assert (resource_dir / "chars.txt").is_file()
        assert catalog.has_text_file("chars.txt")
        assert combo.currentText() == "chars.txt"
        assert imported_events == ["imported"]
        assert selector is not None
        panel.deleteLater()

    def test_single_selection_marks_missing_file_property(self, qapp):
        from ui_designer.model.resource_catalog import ResourceCatalog
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.property_panel import PropertyPanel

        widget = WidgetModel("label", name="title")
        widget.properties["font_file"] = "missing.ttf"

        panel = PropertyPanel()
        panel.set_resource_catalog(ResourceCatalog())
        panel.set_widget(widget)

        data_group = _find_group(panel, "Data")
        editor = panel._editors["prop_font_file"]

        assert "Font (Missing):" in _form_labels(data_group)
        assert "not present in the project catalog" in editor.toolTip()
        assert editor.statusTip() == editor.toolTip()
        assert editor.accessibleName() == "Font File selector: missing.ttf"
        panel.deleteLater()

    def test_single_selection_marks_disk_missing_file_property(self, qapp, tmp_path):
        from ui_designer.model.resource_catalog import ResourceCatalog
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.property_panel import PropertyPanel

        resource_dir = tmp_path / "project" / ".eguiproject" / "resources"
        resource_dir.mkdir(parents=True)

        widget = WidgetModel("label", name="title")
        widget.properties["font_file"] = "missing.ttf"

        catalog = ResourceCatalog()
        catalog.add_font("missing.ttf")

        panel = PropertyPanel()
        panel.set_source_resource_dir(str(resource_dir))
        panel.set_resource_catalog(catalog)
        panel.set_widget(widget)

        data_group = _find_group(panel, "Data")
        editor = panel._editors["prop_font_file"]

        assert "Font (Missing):" in _form_labels(data_group)
        assert "source file is missing on disk" in editor.toolTip()
        assert editor.statusTip() == editor.toolTip()
        assert editor.accessibleName() == "Font File selector: missing.ttf"
        panel.deleteLater()

    def test_multi_selection_marks_missing_when_any_disk_file_is_missing(self, qapp, tmp_path):
        from ui_designer.model.resource_catalog import ResourceCatalog
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.property_panel import PropertyPanel

        resource_dir = tmp_path / "project" / ".eguiproject" / "resources"
        resource_dir.mkdir(parents=True)
        (resource_dir / "present.ttf").write_bytes(b"FONT")

        first = WidgetModel("label", name="first")
        second = WidgetModel("label", name="second")
        first.properties["font_file"] = "missing.ttf"
        second.properties["font_file"] = "present.ttf"

        catalog = ResourceCatalog()
        catalog.add_font("missing.ttf")
        catalog.add_font("present.ttf")

        panel = PropertyPanel()
        panel.set_source_resource_dir(str(resource_dir))
        panel.set_resource_catalog(catalog)
        panel.set_selection([first, second], primary=second)

        common_group = _find_group(panel, "Common Properties")
        editor = panel._editors["prop_font_file"]

        assert any(label.startswith("Font") and "(Missing)" in label for label in _form_labels(common_group))
        assert "missing from the project catalog or source directory" in editor.toolTip()
        assert editor.statusTip() == editor.toolTip()
        assert editor.accessibleName() == "Font File selector: mixed values"
        panel.deleteLater()

    def test_multi_selection_form_toggles_designer_flags_for_all_widgets(self, qapp):
        from qfluentwidgets import CheckBox
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.property_panel import PropertyPanel

        first = WidgetModel("label", name="first")
        second = WidgetModel("button", name="second")

        panel = PropertyPanel()
        panel.set_selection([first, second], primary=second)

        summary_header = panel._layout.itemAt(0).widget()
        assert summary_header.objectName() == "workspace_panel_header"
        assert "Selected 2 widgets" in _group_label_texts(summary_header)

        checkboxes = {checkbox.text(): checkbox for checkbox in panel.findChildren(CheckBox)}
        checkboxes["Locked"].setChecked(True)
        checkboxes["Hidden"].setChecked(True)

        assert first.designer_locked is True
        assert second.designer_locked is True
        assert first.designer_hidden is True
        assert second.designer_hidden is True
        panel.deleteLater()

    def test_multi_selection_header_and_feedback_strip_expose_metadata(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.property_panel import PropertyPanel

        first = WidgetModel("label", name="first")
        second = WidgetModel("button", name="second")
        first.designer_locked = True
        second.designer_hidden = True

        panel = PropertyPanel()
        panel.set_selection([first, second], primary=second)

        summary_header = panel._layout.itemAt(0).widget()
        eyebrow = summary_header.findChild(QLabel, "property_panel_header_eyebrow")
        title = next(
            label
            for label in summary_header.findChildren(QLabel)
            if label.objectName() == "workspace_section_title"
        )
        subtitle = next(
            label
            for label in summary_header.findChildren(QLabel)
            if label.objectName() == "workspace_section_subtitle"
        )
        meta = summary_header.findChild(QLabel, "property_panel_header_meta")
        chips_frame = summary_header.findChild(QFrame, "property_panel_batch_chips")
        chips = [label for label in summary_header.findChildren(QLabel) if label.objectName() == "workspace_status_chip"]
        hint_strip = _find_hint_strip(panel)
        hint_eyebrow = next(label for label in hint_strip.findChildren(QLabel) if label.text() == "Interaction Notes")
        summary_layout = summary_header.layout()
        summary_margins = summary_layout.contentsMargins()
        chips_row = chips_frame.layout()
        hint_layout = hint_strip.layout()

        assert (summary_margins.left(), summary_margins.top(), summary_margins.right(), summary_margins.bottom()) == (6, 6, 6, 6)
        assert summary_layout.spacing() == 4
        assert chips_row.spacing() == 2
        assert panel._context_frame.isHidden() is True
        assert (hint_layout.contentsMargins().left(), hint_layout.contentsMargins().top()) == (4, 4)
        assert (hint_layout.contentsMargins().right(), hint_layout.contentsMargins().bottom()) == (4, 4)
        assert hint_layout.spacing() == 1
        assert summary_header.accessibleName() == "Property batch header: 2 widgets selected. Primary: second. 2 types."
        assert eyebrow.accessibleName() == "Batch property inspection surface."
        assert eyebrow.isHidden() is True
        assert title.accessibleName() == "Batch selection: Selected 2 widgets."
        assert subtitle.accessibleName() == subtitle.text()
        assert subtitle.isHidden() is True
        assert meta.isHidden() is True
        assert chips_frame.isHidden() is True
        assert all(chip.property("chipVariant") == "property" for chip in chips)
        assert any(chip.accessibleName() == "Batch types: 2 types." for chip in chips)
        assert any(chip.accessibleName().startswith("Batch mixed state: ") for chip in chips)
        assert any(chip.accessibleName() == "Batch edit state: Batch edit." for chip in chips)
        assert hint_strip.accessibleName() == (
            "Property interaction notes: Locked: 1 selected widget cannot be moved or resized from the canvas. "
            "Hidden: 1 selected widget is skipped by canvas hit testing."
        )
        assert hint_eyebrow.accessibleName() == "Property interaction notes surface."
        assert hint_eyebrow.isHidden() is True
        panel.deleteLater()

    def test_multi_selection_groups_use_compact_inspector_form_layouts(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.property_panel import PropertyPanel

        first = WidgetModel("label", name="first", x=10, y=20, width=80, height=24)
        second = WidgetModel("label", name="second", x=10, y=20, width=80, height=24)

        panel = PropertyPanel()
        panel.set_selection([first, second], primary=second)

        for title in ("Batch Geometry", "Designer", "Common Properties"):
            group = _find_group(panel, title)
            form = group.layout()
            margins = form.contentsMargins()
            body = group.content_frame()

            assert group.objectName() == "inspector_collapsible_group"
            assert body.objectName() == "inspector_group_body"
            assert group.content_indent() > 0
            assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (0, 0, 0, 0)
            assert form.verticalSpacing() == 4
            assert form.horizontalSpacing() == 0

        panel.deleteLater()

    def test_multi_selection_common_geometry_and_text_update_all_widgets(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.property_panel import PropertyPanel

        first = WidgetModel("label", name="first", x=10, y=20, width=80, height=24)
        second = WidgetModel("button", name="second", x=30, y=40, width=90, height=28)

        panel = PropertyPanel()
        panel.set_selection([first, second], primary=second)

        panel._editors["multi_width"].setValue(120)
        panel._editors["prop_text"].setText("Shared")

        assert first.width == 120
        assert second.width == 120
        assert first.properties["text"] == "Shared"
        assert second.properties["text"] == "Shared"
        panel.deleteLater()

    def test_multi_selection_marks_mixed_text_state(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.property_panel import PropertyPanel

        first = WidgetModel("label", name="first", x=10, y=20, width=80, height=24)
        second = WidgetModel("label", name="second", x=10, y=20, width=80, height=24)
        first.properties["text"] = "Alpha"
        second.properties["text"] = "Beta"

        panel = PropertyPanel()
        panel.set_selection([first, second], primary=second)

        summary_header = panel._layout.itemAt(0).widget()
        common_group = _find_group(panel, "Common Properties")
        text_editor = panel._editors["prop_text"]

        assert "1 mixed field" in _group_label_texts(summary_header)
        assert "Text:" in _form_labels(common_group)
        assert text_editor.text() == ""
        assert text_editor.placeholderText() == "Mixed"
        assert "different values" in text_editor.toolTip()
        assert text_editor.statusTip() == text_editor.toolTip()
        assert text_editor.accessibleName() == "Text property: mixed values"
        panel.deleteLater()

    def test_multi_selection_marks_mixed_bool_state(self, qapp):
        from PyQt5.QtCore import Qt
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.property_panel import PropertyPanel

        first = WidgetModel("switch", name="first")
        second = WidgetModel("switch", name="second")
        first.properties["is_checked"] = False
        second.properties["is_checked"] = True

        panel = PropertyPanel()
        panel.set_selection([first, second], primary=second)

        common_group = _find_group(panel, "Common Properties")
        editor = panel._editors["prop_is_checked"]

        assert "Is Checked:" in _form_labels(common_group)
        assert editor.isTristate() is True
        assert editor.checkState() == Qt.PartiallyChecked
        assert "different values" in editor.toolTip()
        assert editor.statusTip() == editor.toolTip()
        assert editor.accessibleName() == "Is Checked property: mixed values"
        panel.deleteLater()

    def test_multi_selection_marks_mixed_file_state(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.property_panel import PropertyPanel

        first = WidgetModel("label", name="first")
        second = WidgetModel("label", name="second")
        first.properties["font_file"] = "alpha.ttf"
        second.properties["font_file"] = "beta.ttf"

        panel = PropertyPanel()
        panel.set_selection([first, second], primary=second)

        common_group = _find_group(panel, "Common Properties")
        editor = panel._editors["prop_font_file"]

        assert "Font:" in _form_labels(common_group)
        assert editor.currentIndex() == -1
        assert editor.placeholderText() == "Mixed"
        assert "different values" in editor.toolTip()
        assert editor.statusTip() == editor.toolTip()
        assert editor.accessibleName() == "Font File selector: mixed values"
        panel.deleteLater()

    def test_multi_selection_marks_mixed_geometry_state(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.property_panel import PropertyPanel

        first = WidgetModel("label", name="first", x=10, y=20, width=80, height=24)
        second = WidgetModel("label", name="second", x=10, y=20, width=96, height=24)

        panel = PropertyPanel()
        panel.set_selection([first, second], primary=second)

        summary_header = panel._layout.itemAt(0).widget()
        geometry_group = _find_group(panel, "Batch Geometry")
        editor = panel._editors["multi_width"]

        assert "1 mixed field" in _group_label_texts(summary_header)
        assert "Width:" in _form_labels(geometry_group)
        assert "different values" in editor.toolTip()
        assert editor.statusTip() == editor.toolTip()
        assert editor.accessibleName() == "Batch Width: mixed values"
        panel.deleteLater()

    def test_live_geometry_refresh_updates_single_selection_without_rebuild(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.property_panel import PropertyPanel

        widget = WidgetModel("switch", name="toggle", x=10, y=20, width=80, height=24)
        panel = PropertyPanel()
        panel.set_widget(widget)

        original_name_editor = panel._editors["name"]
        widget.x = 32
        widget.y = 48
        widget.width = 120
        widget.height = 36

        refreshed = panel.refresh_live_geometry([widget], primary=widget)

        assert refreshed is True
        assert panel._editors["name"] is original_name_editor
        assert panel._editors["x"].value() == 32
        assert panel._editors["y"].value() == 48
        assert panel._editors["width"].value() == 120
        assert panel._editors["height"].value() == 36
        assert panel._header_size_chip.text() == "120×36"
        assert panel._header_size_chip.isHidden() is True
        assert panel._header_size_chip.accessibleName() == "Widget size: 120 by 36."
        panel.deleteLater()

    def test_live_geometry_refresh_updates_multi_selection_primary_geometry_without_rebuild(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.property_panel import PropertyPanel

        first = WidgetModel("label", name="first", x=10, y=20, width=80, height=24)
        second = WidgetModel("button", name="second", x=30, y=40, width=96, height=28)

        panel = PropertyPanel()
        panel.set_selection([first, second], primary=second)

        original_editor = panel._editors["multi_width"]
        second.width = 144
        second.height = 40

        refreshed = panel.refresh_live_geometry([first, second], primary=second)

        assert refreshed is True
        assert panel._editors["multi_width"] is original_editor
        assert panel._editors["multi_width"].value() == 144
        assert panel._editors["multi_height"].value() == 40
        panel.deleteLater()

    def test_single_selection_shows_interaction_notes_for_locked_hidden_layout_widget(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.property_panel import PropertyPanel

        root = WidgetModel("linearlayout", name="root")
        child = WidgetModel("switch", name="child")
        child.designer_locked = True
        child.designer_hidden = True
        root.add_child(child)

        panel = PropertyPanel()
        panel.set_widget(child)

        notes = _group_label_texts(_find_hint_strip(panel))
        assert any(text.startswith("Locked:") for text in notes)
        assert any(text.startswith("Hidden:") for text in notes)
        assert any(text.startswith("Layout-managed:") for text in notes)
        panel.deleteLater()

    def test_multi_selection_shows_interaction_note_counts(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.property_panel import PropertyPanel

        root = WidgetModel("linearlayout", name="root")
        first = WidgetModel("label", name="first")
        second = WidgetModel("label", name="second")
        first.designer_locked = True
        second.designer_hidden = True
        root.add_child(first)
        root.add_child(second)

        panel = PropertyPanel()
        panel.set_selection([first, second], primary=second)

        notes = _group_label_texts(_find_hint_strip(panel))
        assert "Locked: 1 selected widget cannot be moved or resized from the canvas." in notes
        assert "Hidden: 1 selected widget is skipped by canvas hit testing." in notes
        assert "Layout-managed: 2 selected widgets use parent-controlled positioning." in notes
        panel.deleteLater()

    def test_single_selection_name_edit_rejects_invalid_identifier(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.property_panel import PropertyPanel

        widget = WidgetModel("switch", name="title")
        panel = PropertyPanel()
        messages = []
        panel.validation_message.connect(messages.append)
        panel.set_widget(widget)

        editor = panel._editors["name"]
        assert editor.accessibleName() == "Widget name: title"
        editor.setText("123 bad-name")
        editor.editingFinished.emit()

        assert widget.name == "title"
        assert panel._editors["name"].text() == "title"
        assert messages[-1].startswith("Widget name must be a valid C identifier")
        assert panel._editors["name"].statusTip() == panel._editors["name"].toolTip()
        assert panel._editors["name"].accessibleName().startswith("Widget name: title. Widget name must be a valid C identifier")
        panel.deleteLater()

    def test_single_selection_name_edit_resolves_duplicate_identifier(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.property_panel import PropertyPanel

        root = WidgetModel("group", name="root")
        first = WidgetModel("switch", name="title")
        second = WidgetModel("switch", name="subtitle")
        root.add_child(first)
        root.add_child(second)

        panel = PropertyPanel()
        messages = []
        panel.validation_message.connect(messages.append)
        panel.set_widget(second)

        editor = panel._editors["name"]
        assert editor.accessibleName() == "Widget name: subtitle"
        editor.setText("title")
        editor.editingFinished.emit()

        assert second.name == "title_2"
        assert panel._editors["name"].text() == "title_2"
        assert messages[-1] == "Widget name 'title' already exists. Renamed to 'title_2'."
        assert panel._editors["name"].statusTip() == panel._editors["name"].toolTip()
        assert panel._editors["name"].accessibleName() == (
            "Widget name: title_2. Widget name 'title' already exists. Renamed to 'title_2'."
        )
        panel.deleteLater()

    def test_single_selection_shows_callback_editors_for_click_and_widget_events(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.property_panel import PropertyPanel

        widget = WidgetModel("slider", name="volume_slider")
        widget.on_click = "on_slider_click"
        widget.events["onValueChanged"] = "on_slider_changed"

        panel = PropertyPanel()
        panel.set_widget(widget)

        group = _find_group(panel, "Callbacks")
        labels = _form_labels(group)

        assert "Click:" in labels
        assert "Change:" in labels
        assert panel._editors["callback_onClick"].text() == "on_slider_click"
        assert panel._editors["callback_onValueChanged"].text() == "on_slider_changed"
        assert "void callback_name(egui_view_t *self)" in panel._editors["callback_onClick"].toolTip()
        assert "uint8_t value" in panel._editors["callback_onValueChanged"].toolTip()
        panel.deleteLater()

    def test_single_selection_callback_editor_and_button_metadata(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.property_panel import PropertyPanel

        widget = WidgetModel("slider", name="volume_slider")
        widget.events["onValueChanged"] = "on_slider_changed"

        panel = PropertyPanel()
        panel.set_widget(widget)

        editor = panel._editors["callback_onValueChanged"]
        button = panel._callback_open_buttons["callback_onValueChanged"]

        assert editor.accessibleName() == "Value Changed callback: on_slider_changed"
        assert button.text() == "Open"
        assert button.accessibleName() == "Open Value Changed callback code"
        assert button.statusTip() == button.toolTip()
        panel.deleteLater()

    def test_single_selection_callback_edit_normalizes_and_updates_widget(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.property_panel import PropertyPanel

        widget = WidgetModel("slider", name="volume_slider")

        panel = PropertyPanel()
        property_events = []
        messages = []
        panel.property_changed.connect(lambda: property_events.append("changed"))
        panel.validation_message.connect(messages.append)
        panel.set_widget(widget)

        editor = panel._editors["callback_onValueChanged"]
        editor.setText("handle volume changed")
        editor.editingFinished.emit()

        assert widget.events["onValueChanged"] == "handle_volume_changed"
        assert editor.text() == "handle_volume_changed"
        assert property_events == ["changed"]
        assert messages[-1] == "Callback name normalized to 'handle_volume_changed'."
        panel.deleteLater()

    def test_single_selection_callback_open_user_code_emits_current_name_and_signature(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.property_panel import PropertyPanel

        widget = WidgetModel("slider", name="volume_slider")
        widget.events["onValueChanged"] = "on_slider_changed"

        panel = PropertyPanel()
        captured = []
        panel.user_code_requested.connect(lambda name, signature: captured.append((name, signature)))
        panel.set_widget(widget)

        button = panel._callback_open_buttons["callback_onValueChanged"]
        assert button is not None
        panel._request_single_callback_user_code(
            panel._editors["callback_onValueChanged"],
            widget,
            "onValueChanged",
            "void {func_name}(egui_view_t *self, uint8_t value)",
        )

        assert captured == [("on_slider_changed", "void {func_name}(egui_view_t *self, uint8_t value)")]
        panel.deleteLater()

    def test_single_selection_callback_edit_rejects_invalid_identifier(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.property_panel import PropertyPanel

        widget = WidgetModel("slider", name="volume_slider")
        widget.events["onValueChanged"] = "on_slider_changed"

        panel = PropertyPanel()
        property_events = []
        messages = []
        panel.property_changed.connect(lambda: property_events.append("changed"))
        panel.validation_message.connect(messages.append)
        panel.set_widget(widget)

        editor = panel._editors["callback_onValueChanged"]
        editor.setText("123 bad-name")
        editor.editingFinished.emit()

        assert widget.events["onValueChanged"] == "on_slider_changed"
        assert editor.text() == "on_slider_changed"
        assert property_events == []
        assert messages[-1].startswith("Callback name must be a valid C identifier")
        panel.deleteLater()

    def test_multi_selection_shows_shared_callback_editors_and_mixed_state(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.property_panel import PropertyPanel

        first = WidgetModel("slider", name="first_slider")
        second = WidgetModel("slider", name="second_slider")
        first.on_click = "on_first_click"
        second.on_click = "on_second_click"
        first.events["onValueChanged"] = "on_volume_changed"
        second.events["onValueChanged"] = "on_volume_changed"

        panel = PropertyPanel()
        panel.set_selection([first, second], primary=second)

        summary_header = panel._layout.itemAt(0).widget()
        callbacks_group = _find_group(panel, "Callbacks")
        click_editor = panel._editors["callback_onClick"]
        value_editor = panel._editors["callback_onValueChanged"]

        assert "1 mixed field" in _group_label_texts(summary_header)
        assert "Click:" in _form_labels(callbacks_group)
        assert "Change:" in _form_labels(callbacks_group)
        assert click_editor.text() == ""
        assert click_editor.placeholderText() == "Mixed"
        assert "different callback names" in click_editor.toolTip()
        assert value_editor.text() == "on_volume_changed"
        assert "applies the same callback to all selected widgets" in value_editor.toolTip()
        panel.deleteLater()

    def test_multi_selection_callback_open_user_code_is_disabled_for_mixed_values(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.property_panel import PropertyPanel

        first = WidgetModel("slider", name="first_slider")
        second = WidgetModel("slider", name="second_slider")
        first.on_click = "on_first_click"
        second.on_click = "on_second_click"

        panel = PropertyPanel()
        panel.set_selection([first, second], primary=second)

        editor = panel._editors["callback_onClick"]
        button = panel._callback_open_buttons["callback_onClick"]

        assert editor.accessibleName() == "Click callback: mixed values"
        assert button.text() == "Open"
        assert button.isHidden() is True
        assert button.isEnabled() is False
        assert button.accessibleName() == "Open Click callback code unavailable"
        panel.deleteLater()

    def test_multi_selection_callback_edit_updates_all_widgets(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.property_panel import PropertyPanel

        first = WidgetModel("slider", name="first_slider")
        second = WidgetModel("slider", name="second_slider")

        panel = PropertyPanel()
        property_events = []
        messages = []
        panel.property_changed.connect(lambda: property_events.append("changed"))
        panel.validation_message.connect(messages.append)
        panel.set_selection([first, second], primary=second)

        editor = panel._editors["callback_onValueChanged"]
        button = panel._callback_open_buttons["callback_onValueChanged"]
        editor.setText("handle volume changed")
        editor.editingFinished.emit()

        assert first.events["onValueChanged"] == "handle_volume_changed"
        assert second.events["onValueChanged"] == "handle_volume_changed"
        assert editor.text() == "handle_volume_changed"
        assert button.text() == "Open"
        assert button.isHidden() is False
        assert button.isEnabled() is True
        assert property_events == ["changed"]
        assert messages[-1] == "Callback name normalized to 'handle_volume_changed'."
        panel.deleteLater()

    def test_multi_selection_callback_edit_rejects_invalid_identifier(self, qapp):
        from ui_designer.model.widget_model import WidgetModel
        from ui_designer.ui.property_panel import PropertyPanel

        first = WidgetModel("slider", name="first_slider")
        second = WidgetModel("slider", name="second_slider")
        first.events["onValueChanged"] = "on_volume_changed"
        second.events["onValueChanged"] = "on_volume_changed"

        panel = PropertyPanel()
        property_events = []
        messages = []
        panel.property_changed.connect(lambda: property_events.append("changed"))
        panel.validation_message.connect(messages.append)
        panel.set_selection([first, second], primary=second)

        editor = panel._editors["callback_onValueChanged"]
        editor.setText("123 bad-name")
        editor.editingFinished.emit()

        assert first.events["onValueChanged"] == "on_volume_changed"
        assert second.events["onValueChanged"] == "on_volume_changed"
        assert editor.text() == "on_volume_changed"
        assert property_events == []
        assert messages[-1].startswith("Callback name must be a valid C identifier")
        panel.deleteLater()
