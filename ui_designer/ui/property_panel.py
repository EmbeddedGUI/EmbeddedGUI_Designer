"""Property editor panel for EmbeddedGUI Designer."""

import os
import re
import json

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLabel,
    QGroupBox, QScrollArea, QHBoxLayout,
    QGridLayout,
    QDialog, QListWidget, QListWidgetItem,
    QDialogButtonBox, QMessageBox, QFileDialog, QFrame,
)
from PyQt5.QtCore import pyqtSignal, Qt, QSignalBlocker
from PyQt5.QtGui import QFont

from qfluentwidgets import (
    ComboBox, EditableComboBox, SpinBox, LineEdit, CheckBox, ToolButton,
    ListWidget, SearchLineEdit,
)

from ..model.widget_model import (
    WidgetModel, BackgroundModel,
    COLORS, ALPHAS, FONTS, ALIGNS, BG_TYPES,
    IMAGE_FORMATS, IMAGE_ALPHAS, IMAGE_EXTERNALS,
    FONT_PIXELSIZES, FONT_BITSIZES, FONT_EXTERNALS,
)
from ..model.resource_binding import assign_resource_to_widget
from ..model.widget_name import resolve_widget_name, sanitize_widget_name, is_valid_widget_name
from ..model.widget_registry import WidgetRegistry
from ..settings.ui_prefs import _normalize_inspector_group_expanded
from .widgets.collapsible_group import CollapsibleGroupBox
from .widgets.color_picker import EguiColorPicker
from .widgets.font_selector import EguiFontSelector

# UI group display names
_UI_GROUP_LABELS = {
    "main": "Properties",
    "font_config": "Text",
    "image_config": "Appearance",
    "properties": "Properties",
    "style": "Appearance",
    "card_bg": "Appearance",
    "card_border": "Appearance",
}

_INSPECTOR_GROUP_PRIORITY = {
    "Layout": 0,
    "Appearance": 1,
    "Text": 2,
    "Behavior": 3,
    "Data": 4,
    "Callbacks": 5,
    "Designer": 6,
}

_CALLBACK_INVALID_MESSAGE = (
    "Callback name must be a valid C identifier using letters, numbers, and underscores, "
    "and it cannot start with a digit."
)

# UIX-005: default expanded groups <=2 — keep first-edit path focused.
_DEFAULT_EXPANDED_INSPECTOR_TITLES = frozenset({"Basic", "Layout"})

_MULTI_SUPPORTED_PROPERTY_TYPES = {
    "string",
    "int",
    "bool",
    "color",
    "alpha",
    "align",
    "orientation",
    "image_format",
    "image_alpha",
    "image_external",
    "font_pixelsize",
    "font_fontbitsize",
    "font_external",
    "image_file",
    "font_file",
    "text_file",
}

_DATA_PROPERTY_TYPES = {
    "image_file",
    "image_format",
    "image_alpha",
    "image_external",
    "font_file",
    "font_pixelsize",
    "font_fontbitsize",
    "font_external",
    "text_file",
}


def _set_widget_metadata(widget, *, tooltip=None, accessible_name=None):
    if tooltip is not None:
        resolved_tooltip = str(tooltip or "")
        current_tooltip = widget.property("_property_panel_tooltip_snapshot")
        if current_tooltip is None or str(current_tooltip) != resolved_tooltip:
            widget.setToolTip(resolved_tooltip)
            widget.setStatusTip(resolved_tooltip)
            widget.setProperty("_property_panel_tooltip_snapshot", resolved_tooltip)
    if accessible_name is not None:
        resolved_accessible_name = str(accessible_name or "")
        current_accessible_name = widget.property("_property_panel_accessible_snapshot")
        if current_accessible_name is None or str(current_accessible_name) != resolved_accessible_name:
            widget.setAccessibleName(resolved_accessible_name)
            widget.setProperty("_property_panel_accessible_snapshot", resolved_accessible_name)


def _count_label(count, singular, plural=None):
    value = max(int(count or 0), 0)
    noun = singular if value == 1 else (plural or f"{singular}s")
    return f"{value} {noun}"


def _inspector_form():
    """Consistent label/field rhythm for inspector property forms (readable balanced density)."""
    form = QFormLayout()
    form.setContentsMargins(0, 0, 0, 0)
    form.setSpacing(4)
    form.setHorizontalSpacing(0)
    form.setRowWrapPolicy(QFormLayout.WrapAllRows)
    form.setLabelAlignment(Qt.AlignLeft | Qt.AlignBottom)
    form.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
    return form


class PropertyPanel(QWidget):
    """Dynamic property editor for the selected widget."""

    property_changed = pyqtSignal()  # emits when any property changes
    resource_imported = pyqtSignal()  # emits when browse auto-import adds a new resource
    validation_message = pyqtSignal(str)  # emits lightweight validation/normalization feedback
    user_code_requested = pyqtSignal(str, str)  # emits callback_name, signature

    def __init__(self, parent=None):
        super().__init__(parent)
        self._widget = None
        self._selection = []
        self._primary_widget = None
        self._updating = False  # prevent signal loops
        self._editors = {}
        self._callback_open_buttons = {}
        self._resource_dir = ""      # resource/ dir (for generated font scanning)
        self._source_resource_dir = ""  # .eguiproject/resources/ (source files)
        self._last_external_file_dir = ""  # last browsed external file directory
        self._custom_fonts = []       # C expressions from project resource/
        self._resource_catalog = None  # ResourceCatalog instance
        self._string_keys = []        # list of i18n string keys for @string/ completions
        self._inspector_group_expanded = {}
        self._header_size_chip = None
        self.setAcceptDrops(True)
        self._init_ui()

    # ── Resource integration API ───────────────────────────────────

    def set_resource_dir(self, path):
        """Store the resource directory (resource/) for generated font scanning."""
        self._resource_dir = path or ""

    def set_source_resource_dir(self, path):
        """Store the source resource directory (.eguiproject/resources/)
        for file browsing, drag-drop resolution, and auto-import."""
        self._source_resource_dir = path or ""

    def set_resource_catalog(self, catalog):
        """Set the resource catalog for populating file selectors."""
        self._resource_catalog = catalog
        # Rebuild form if currently displaying a widget (to update combos)
        if self._primary_widget is not None:
            self._updating = True
            self._rebuild_form()
            self._updating = False

    def set_string_keys(self, keys):
        """Set i18n string keys for @string/ completions in text properties."""
        self._string_keys = list(keys) if keys else []
        # Rebuild form if currently displaying a label/button
        if (self._primary_widget is not None and
                self._primary_widget.widget_type in ("label", "button")):
            self._updating = True
            self._rebuild_form()
            self._updating = False

    def set_custom_fonts(self, font_exprs):
        """Set custom font C expressions from the project resource dir.

        The font QComboBox will show FONTS + these custom entries.
        """
        self._custom_fonts = list(font_exprs) if font_exprs else []
        # Rebuild form if currently displaying a widget (to update font combos)
        if self._primary_widget is not None:
            self._updating = True
            self._rebuild_form()
            self._updating = False

    def set_inspector_group_expanded_state(self, data):
        """Restore persisted Inspector collapsible group expanded flags (UI-D-003)."""
        self._inspector_group_expanded = _normalize_inspector_group_expanded(data)

    def inspector_group_expanded_snapshot(self):
        """Return flags to merge into workspace_state when saving the window."""
        return dict(self._inspector_group_expanded)

    def _inspector_group_storage_key(self, title: str) -> str:
        title = (title or "").strip()
        if len(self._selection) > 1:
            return f"__multi__\t{title}"
        if self._primary_widget is None:
            return f"__none__\t{title}"
        wt = (self._primary_widget.widget_type or "").strip()
        return f"{wt}\t{title}"

    def _inspector_group_default_expanded(self, title: str, key: str) -> bool:
        t = (title or "").strip()
        if t in _DEFAULT_EXPANDED_INSPECTOR_TITLES:
            return True
        # Keep callbacks discoverable for multi-select batch editing.
        if t == "Callbacks" and str(key).startswith("__multi__\t"):
            return True
        return False

    def _wire_inspector_collapsible_group(self, group: CollapsibleGroupBox, title: str):
        key = self._inspector_group_storage_key(title)
        default_open = self._inspector_group_default_expanded(title, key)
        expanded = bool(self._inspector_group_expanded.get(key, default_open))
        group.apply_expanded_state(expanded)
        group.toggled.connect(lambda checked, k=key: self._on_inspector_collapsible_toggled(k, checked))

    def _on_inspector_collapsible_toggled(self, key: str, checked: bool):
        if self._updating:
            return
        self._inspector_group_expanded[key] = checked

    def _merged_fonts(self):
        """Return built-in FONTS merged with generated font resources (no dups)."""
        seen = set(FONTS)
        merged = list(FONTS)

        # Scan generated font resources from resource/font/
        if self._resource_dir:
            font_dir = os.path.join(self._resource_dir, "font")
            if os.path.isdir(font_dir):
                pattern = re.compile(r'^(egui_res_font_\w+)\.c$')
                for fname in sorted(os.listdir(font_dir)):
                    m = pattern.match(fname)
                    if m:
                        res_name = m.group(1)
                        # Skip _bin variants (external storage)
                        if not res_name.endswith("_bin"):
                            expr = f"&{res_name}"
                            if expr not in seen:
                                merged.append(expr)
                                seen.add(expr)

        # Also include custom fonts from config (for backward compatibility)
        for f in self._custom_fonts:
            if f not in seen:
                merged.append(f)
                seen.add(f)

        return merged

    def _catalog_images(self):
        """Return list of image filenames from catalog."""
        if self._resource_catalog:
            return list(self._resource_catalog.images)
        return []

    def _catalog_fonts(self):
        """Return list of font filenames from catalog."""
        if self._resource_catalog:
            return list(self._resource_catalog.fonts)
        return []

    def _catalog_text_files(self):
        """Return list of text filenames from catalog."""
        if self._resource_catalog:
            return list(self._resource_catalog.text_files)
        return []

    # ── Drop target for resource MIME ──────────────────────────────

    def dragEnterEvent(self, event):
        from .resource_panel import EGUI_RESOURCE_MIME
        if event.mimeData().hasFormat(EGUI_RESOURCE_MIME):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        from .resource_panel import EGUI_RESOURCE_MIME
        if not event.mimeData().hasFormat(EGUI_RESOURCE_MIME):
            event.ignore()
            return
        try:
            raw = bytes(event.mimeData().data(EGUI_RESOURCE_MIME)).decode("utf-8")
            info = json.loads(raw)
        except Exception:
            event.ignore()
            return
        res_type = info.get("type", "")
        # Support both new (filename) and legacy (expr) payload formats
        filename = info.get("filename", "")
        expr = info.get("expr", "")
        if self._primary_widget is None:
            event.ignore()
            return

        if filename and assign_resource_to_widget(self._primary_widget, res_type, filename):
            self._rebuild_form()
            self.property_changed.emit()
            event.acceptProposedAction()
        elif res_type == "image" and "image_file" in self._primary_widget.properties:
            if expr:
                # Legacy: parse expr to extract filename
                from ..model.widget_model import parse_legacy_image_expr, _guess_filename_from_c_name
                parsed = parse_legacy_image_expr(expr)
                if parsed:
                    src_dir = os.path.join(self._source_resource_dir, "images") if self._source_resource_dir else ""
                    fn = _guess_filename_from_c_name(parsed["name"], [".png", ".bmp", ".jpg"], src_dir)
                    self._primary_widget.properties["image_file"] = fn
                    self._primary_widget.properties["image_format"] = parsed["format"]
                    self._primary_widget.properties["image_alpha"] = parsed["alpha"]
            self._rebuild_form()
            self.property_changed.emit()
            event.acceptProposedAction()
        elif res_type == "font" and "font_file" in self._primary_widget.properties:
            if expr:
                from ..model.widget_model import parse_legacy_font_expr, _guess_filename_from_c_name
                parsed = parse_legacy_font_expr(expr)
                if parsed and "montserrat" not in parsed["name"]:
                    src_dir = self._source_resource_dir or ""
                    fn = _guess_filename_from_c_name(parsed["name"], [".ttf", ".otf"], src_dir)
                    self._primary_widget.properties["font_file"] = fn
                    self._primary_widget.properties["font_pixelsize"] = parsed["pixelsize"]
                    self._primary_widget.properties["font_fontbitsize"] = parsed["fontbitsize"]
                elif parsed:
                    self._primary_widget.properties["font_builtin"] = expr
            self._rebuild_form()
            self.property_changed.emit()
            event.acceptProposedAction()
        else:
            event.ignore()

    def _init_ui(self):
        self.setObjectName("property_panel_root")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.setSpacing(4)

        self._context_frame = QWidget()
        self._context_frame.setObjectName("property_panel_context")
        context_layout = QVBoxLayout(self._context_frame)
        context_layout.setContentsMargins(0, 0, 0, 0)
        context_layout.setSpacing(2)

        self._overview_eyebrow = QLabel("Inspector")
        self._overview_eyebrow.setObjectName("property_panel_eyebrow")
        self._overview_eyebrow.hide()
        context_layout.addWidget(self._overview_eyebrow)

        self._context_title = QLabel("No selection")
        self._context_title.setObjectName("workspace_section_title")
        context_layout.addWidget(self._context_title)

        self._context_meta = QLabel("Select a widget to inspect properties, resources, and callbacks.")
        self._context_meta.setObjectName("workspace_section_subtitle")
        self._context_meta.setWordWrap(True)
        context_layout.addWidget(self._context_meta)
        outer.addWidget(self._context_frame)
        self._context_frame.setVisible(False)

        self._search_shell = QFrame()
        self._search_shell.setObjectName("property_panel_search_shell")
        search_layout = QVBoxLayout(self._search_shell)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(0)

        self._search_hint = QLabel(
            "Search labels, resource bindings, and callbacks for the current selection.",
            self._search_shell,
        )
        self._search_hint.setObjectName("workspace_section_subtitle")
        self._search_hint.setWordWrap(True)
        self._search_hint.hide()

        self._search_edit = SearchLineEdit()
        self._search_edit.setPlaceholderText("Select a widget to filter properties")
        self._search_edit.textChanged.connect(self._on_search_changed)
        self._search_edit.setVisible(False)
        search_layout.addWidget(self._search_edit)
        self._search_shell.setVisible(False)
        outer.addWidget(self._search_shell)

        scroll = QScrollArea()
        scroll.setObjectName("property_panel_scroll")
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)

        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(2, 4, 2, 4)
        self._layout.setSpacing(4)
        scroll.setWidget(self._container)

        self._no_selection_label = self._create_no_selection_label()
        self._layout.addWidget(self._no_selection_label)
        self._update_panel_metadata()

    def _on_search_changed(self, text):
        """Filter visible property rows by search text."""
        text = text.strip().lower()
        for i in range(self._layout.count()):
            item = self._layout.itemAt(i)
            w = item.widget()
            if not isinstance(w, QGroupBox):
                continue
            layout = w.layout()
            if not isinstance(layout, QFormLayout):
                w.setVisible(not text)
                continue
            any_visible = False
            for row in range(layout.rowCount()):
                label_item = layout.itemAt(row, QFormLayout.LabelRole)
                field_item = layout.itemAt(row, QFormLayout.FieldRole)
                label_text = ""
                if label_item and label_item.widget():
                    label_text = label_item.widget().text().lower()
                visible = not text or text in label_text
                if label_item and label_item.widget():
                    label_item.widget().setVisible(visible)
                if field_item and field_item.widget():
                    field_item.widget().setVisible(visible)
                if visible:
                    any_visible = True
            w.setVisible(any_visible or not text)
        self._update_panel_metadata()

    def set_widget(self, widget):
        """Set the widget to edit. None to clear."""
        self.set_selection([widget] if widget is not None else [], primary=widget)

    def set_selection(self, widgets, primary=None):
        widgets = [widget for widget in (widgets or []) if widget is not None]
        self._selection = widgets
        if primary is None or all(widget is not primary for widget in widgets):
            primary = widgets[-1] if widgets else None
        self._primary_widget = primary
        self._widget = primary
        self._rebuild_form()

    def _selection_matches(self, widgets, primary=None):
        widgets = [widget for widget in (widgets or []) if widget is not None]
        if primary is None or all(widget is not primary for widget in widgets):
            primary = widgets[-1] if widgets else None
        if primary is not self._primary_widget:
            return False
        if len(widgets) != len(self._selection):
            return False
        return all(current is incoming for current, incoming in zip(self._selection, widgets))

    def _update_numeric_editor_value(self, key, value):
        editor = self._editors.get(key)
        if editor is None or not hasattr(editor, "value") or not hasattr(editor, "setValue"):
            return
        try:
            current_value = int(editor.value())
        except Exception:
            current_value = None
        if current_value == int(value):
            return
        with QSignalBlocker(editor):
            editor.setValue(int(value))

    def refresh_live_geometry(self, widgets, primary=None):
        """Refresh geometry editors for the current selection without rebuilding the form."""
        if not self._selection_matches(widgets, primary=primary):
            return False
        if self._primary_widget is None:
            return False

        if len(self._selection) == 1:
            widget = self._primary_widget
            for field in ("x", "y", "width", "height"):
                self._update_numeric_editor_value(field, getattr(widget, field))
            if self._header_size_chip is not None:
                self._header_size_chip.setText(f"{widget.width}×{widget.height}")
                _set_widget_metadata(
                    self._header_size_chip,
                    tooltip=f"Widget size: {widget.width} by {widget.height}.",
                    accessible_name=f"Widget size: {widget.width} by {widget.height}.",
                )
            return True

        primary_widget = self._primary_widget
        for field in ("x", "y", "width", "height"):
            self._update_numeric_editor_value(f"multi_{field}", getattr(primary_widget, field))
        return True

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def _make_status_chip(self, text, tone=None):
        chip = QLabel(text)
        chip.setObjectName("workspace_status_chip")
        chip.setProperty("chipVariant", "property")
        if tone:
            chip.setProperty("chipTone", tone)
        return chip

    def _populate_chip_row(self, layout, items):
        self._clear_layout(layout)
        for text, tone in items:
            layout.addWidget(self._make_status_chip(text, tone))
        layout.addStretch()

    def _make_metric_card(self, label, value, tone=None):
        card = QFrame()
        card.setObjectName("property_panel_metric_card")
        if tone:
            card.setProperty("metricTone", tone)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(6, 3, 6, 3)
        layout.setSpacing(4)

        caption = QLabel(label)
        caption.setObjectName("property_panel_metric_label")
        metric_value = QLabel(value)
        metric_value.setObjectName("property_panel_metric_value")
        metric_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        layout.addWidget(caption)
        layout.addStretch(1)
        layout.addWidget(metric_value)
        summary = f"{label}: {value}"
        _set_widget_metadata(caption, tooltip=summary, accessible_name=f"{label} metric label")
        _set_widget_metadata(metric_value, tooltip=summary, accessible_name=f"{label} metric value: {value}")
        _set_widget_metadata(card, tooltip=summary, accessible_name=f"{label} metric: {value}")
        return card

    def _build_metric_grid(self, metrics):
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(2)
        grid.setVerticalSpacing(2)
        for index, (label, value, tone) in enumerate(metrics):
            grid.addWidget(self._make_metric_card(label, value, tone), index // 2, index % 2)
        return grid

    def _resource_binding_count(self, widget):
        descriptor = WidgetRegistry.instance().get(widget.widget_type)
        return sum(
            1
            for prop_name, prop_info in descriptor.get("properties", {}).items()
            if prop_info.get("type") in {"image_file", "font_file", "text_file"} and widget.properties.get(prop_name)
        )

    def _active_callback_count(self, widget):
        return sum(1 for entry in self._callback_entries(widget) if entry.get("value"))

    def _selection_mixed_field_count(self, callback_entries=None, common_props=None):
        if len(self._selection) <= 1:
            return 0

        callback_entries = list(callback_entries or self._collect_multi_callback_entries())
        common_props = list(common_props or self._collect_multi_common_properties())
        mixed_geometry = sum(
            1
            for field in ("x", "y", "width", "height")
            if self._is_mixed_values(getattr(widget, field) for widget in self._selection)
        )
        mixed_props = sum(
            1
            for prop_name, _ in common_props
            if self._is_mixed_values(widget.properties.get(prop_name) for widget in self._selection)
        )
        mixed_callbacks = sum(1 for entry in callback_entries if entry["is_mixed"])
        return mixed_geometry + mixed_props + mixed_callbacks

    def _create_no_selection_label(self):
        frame = QWidget()
        frame.setObjectName("property_panel_empty_state")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(6, 8, 6, 8)
        layout.setSpacing(2)
        eyebrow = QLabel("Inspector")
        eyebrow.setObjectName("property_panel_eyebrow")
        title = QLabel("No selection")
        title.setObjectName("workspace_section_title")
        sub = QLabel("Select a widget from the tree or canvas to edit its properties.")
        sub.setObjectName("workspace_section_subtitle")
        sub.setWordWrap(True)
        layout.addWidget(eyebrow)
        layout.addWidget(title)
        layout.addWidget(sub)
        eyebrow.hide()
        _set_widget_metadata(
            eyebrow,
            tooltip="Property inspection surface.",
            accessible_name="Property inspection surface.",
        )
        _set_widget_metadata(
            title,
            tooltip="No widget selected.",
            accessible_name="No widget selected.",
        )
        _set_widget_metadata(
            sub,
            tooltip=sub.text(),
            accessible_name=sub.text(),
        )
        _set_widget_metadata(
            frame,
            tooltip="Select a widget from the canvas or tree to edit its properties.",
            accessible_name="Property panel empty state: No widget selected.",
        )
        return frame

    def _current_search_summary(self):
        if not hasattr(self, "_search_edit"):
            return "none"
        text = self._search_edit.text().strip()
        return text or "none"

    def _property_label(self, prop_name):
        return prop_name.replace("_", " ").title()

    def _editor_value_summary(self, editor):
        text = editor.text().strip() if hasattr(editor, "text") else ""
        if text:
            return text
        placeholder = editor.placeholderText().strip() if hasattr(editor, "placeholderText") else ""
        if placeholder == "Mixed values":
            return "mixed values"
        return placeholder or "none"

    def _file_selector_tooltip(self, prop_name, value_text):
        return (
            f"{self._property_label(prop_name)}: {value_text}. "
            "Choose a project resource file or type a filename."
        )

    def _browse_button_tooltip(self, prop_name, file_filter):
        browse_target = (file_filter or "").split("(")[0].strip().lower() or "files"
        return f"Browse {browse_target} for {self._property_label(prop_name)}."

    def _mixed_value_tooltip(self):
        return "Selected widgets currently have different values. Editing here will normalize them."

    def _update_mixed_editor_metadata(self, editor, label, tooltip=None):
        _set_widget_metadata(
            editor,
            tooltip=tooltip or self._mixed_value_tooltip(),
            accessible_name=f"{label}: mixed values",
        )

    def _update_panel_metadata(self):
        search_summary = self._current_search_summary()
        self._update_overview_content()
        _set_widget_metadata(
            self._search_edit,
            tooltip=f"Filter visible property rows by label. Current filter: {search_summary}.",
            accessible_name=f"Property search: {search_summary}",
        )

        if self._primary_widget is None:
            panel_summary = f"Property panel: no widget selected. Search: {search_summary}."
        elif len(self._selection) > 1:
            panel_summary = (
                f"Property panel: {_count_label(len(self._selection), 'selected widget')}. "
                f"Primary widget: {self._primary_widget.name} ({self._primary_widget.widget_type}). "
                f"Search: {search_summary}."
            )
        else:
            panel_summary = (
                "Property panel: 1 selected widget. "
                f"Current widget: {self._primary_widget.name} ({self._primary_widget.widget_type}). "
                f"Search: {search_summary}."
            )
        _set_widget_metadata(
            self._context_title,
            tooltip=self._context_title.text(),
            accessible_name=self._context_title.text(),
        )
        _set_widget_metadata(
            self._context_meta,
            tooltip=self._context_meta.text(),
            accessible_name=self._context_meta.text(),
        )
        _set_widget_metadata(self, tooltip=panel_summary, accessible_name=panel_summary)

    def _update_overview_content(self):
        if not hasattr(self, "_context_title"):
            return

        if self._primary_widget is None:
            self._context_title.setText("No selection")
            self._context_meta.setText(
                "Select a widget to inspect properties, resources, and callbacks."
            )
            self._search_edit.setPlaceholderText("Select a widget to filter properties")
            self._search_hint.setText("Search becomes available after you select a widget.")
            self._search_hint.setVisible(False)
            return

        self._search_hint.setVisible(False)
        if len(self._selection) > 1:
            widget_types = sorted({widget.widget_type for widget in self._selection})
            callback_entries = self._collect_multi_callback_entries()
            common_props = self._collect_multi_common_properties()
            mixed_total = self._selection_mixed_field_count(callback_entries, common_props)
            primary_name = self._primary_widget.name if self._primary_widget else "none"
            self._context_title.setText(f"Selected {_count_label(len(self._selection), 'widget')}")
            self._context_meta.setText(
                f"Primary: {primary_name} | {_count_label(len(widget_types), 'type')} | {_count_label(mixed_total, 'mixed field')}."
            )
            self._search_edit.setPlaceholderText("Filter shared properties...")
            self._search_hint.setText("Search common fields, resource bindings, and callbacks for the current batch selection.")
            return

        widget = self._primary_widget
        layout_parent = self._layout_parent_name(widget)
        display_name = WidgetRegistry.instance().display_name(widget.widget_type)
        bound_assets = self._resource_binding_count(widget)
        active_callbacks = self._active_callback_count(widget)
        placement = f"Managed by {layout_parent}" if layout_parent else "Freeform"
        self._context_title.setText(widget.name)
        self._context_meta.setText(
            f"{display_name} ({widget.widget_type}) | {placement} | "
            f"{_count_label(bound_assets, 'asset binding')} | {_count_label(active_callbacks, 'active callback')}."
        )
        self._search_edit.setPlaceholderText("Filter widget properties...")
        self._search_hint.setText("Search fields, resource bindings, and callbacks for the current widget.")
        if self._header_size_chip is not None:
            self._header_size_chip.setText(f"{widget.width}×{widget.height}")
            _set_widget_metadata(
                self._header_size_chip,
                tooltip=f"Widget size: {widget.width} by {widget.height}.",
                accessible_name=f"Widget size: {widget.width} by {widget.height}.",
            )

    def _update_file_selector_metadata(self, prop_name, combo, tooltip=None):
        value_text = self._editor_value_summary(combo)
        _set_widget_metadata(
            combo,
            tooltip=tooltip or self._file_selector_tooltip(prop_name, value_text),
            accessible_name=f"{self._property_label(prop_name)} selector: {value_text}",
        )

    def _update_callback_editor_metadata(self, editor, event_name, tooltip):
        callback_label = self._humanize_callback_name(event_name)
        _set_widget_metadata(
            editor,
            tooltip=tooltip,
            accessible_name=f"{callback_label} callback: {self._editor_value_summary(editor)}",
        )

    def _update_callback_button_metadata(self, button, event_name, enabled, tooltip):
        callback_label = self._humanize_callback_name(event_name)
        accessible_name = (
            f"Open {callback_label} callback code"
            if enabled
            else f"Open {callback_label} callback code unavailable"
        )
        _set_widget_metadata(button, tooltip=tooltip, accessible_name=accessible_name)

    def _update_name_editor_metadata(self, editor, tooltip=None):
        name_text = editor.text().strip() or "none"
        accessible_name = f"Widget name: {name_text}"
        if tooltip:
            accessible_name = f"{accessible_name}. {tooltip}"
        _set_widget_metadata(editor, tooltip=tooltip, accessible_name=accessible_name)

    def _build_single_selection_header(self, widget):
        header = QFrame()
        header.setObjectName("workspace_panel_header")
        header.setProperty("panelTone", "property")
        layout = QVBoxLayout()
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        header.setLayout(layout)

        eyebrow = QLabel("Widget Profile")
        eyebrow.setObjectName("property_panel_header_eyebrow")
        layout.addWidget(eyebrow)

        title_col = QVBoxLayout()
        title_col.setContentsMargins(0, 0, 0, 0)
        title_col.setSpacing(1)
        title = QLabel(widget.name)
        title.setObjectName("workspace_section_title")
        title_col.addWidget(title)

        subtitle = QLabel(f"{WidgetRegistry.instance().display_name(widget.widget_type)} - {widget.widget_type}")
        subtitle.setObjectName("workspace_section_subtitle")
        subtitle.setWordWrap(True)
        title_col.addWidget(subtitle)
        layout.addLayout(title_col)

        header_meta = QLabel("Edit layout, behavior, resources, and callbacks.")
        header_meta.setObjectName("property_panel_header_meta")
        header_meta.setWordWrap(True)
        layout.addWidget(header_meta)
        eyebrow.hide()
        header_meta.hide()
        _set_widget_metadata(
            eyebrow,
            tooltip="Property inspection surface.",
            accessible_name="Property inspection surface.",
        )
        _set_widget_metadata(
            title,
            tooltip=f"Selected widget: {widget.name}.",
            accessible_name=f"Selected widget: {widget.name}.",
        )
        _set_widget_metadata(
            subtitle,
            tooltip=f"Widget type: {subtitle.text()}.",
            accessible_name=f"Widget type: {subtitle.text()}.",
        )
        subtitle.hide()
        _set_widget_metadata(
            header_meta,
            tooltip=header_meta.text(),
            accessible_name=header_meta.text(),
        )
        _set_widget_metadata(
            header,
            tooltip=f"Property header: {widget.name}. {subtitle.text()}.",
            accessible_name=f"Property header: {widget.name}. {subtitle.text()}.",
        )

        layout_parent = self._layout_parent_name(widget)
        bound_assets = self._resource_binding_count(widget)
        active_callbacks = self._active_callback_count(widget)
        metrics = [
            ("Origin", f"{widget.x}, {widget.y}", "accent"),
            ("Placement", "Layout-managed" if layout_parent else "Freeform", "warning" if layout_parent else "success"),
            ("Assets", _count_label(bound_assets, "binding"), "success" if bound_assets else None),
            ("Callbacks", _count_label(active_callbacks, "active callback"), "success" if active_callbacks else None),
        ]
        layout.addLayout(self._build_metric_grid(metrics))

        chips_row = QHBoxLayout()
        chips_row.setContentsMargins(0, 0, 0, 0)
        chips_row.setSpacing(2)
        self._header_size_chip = self._make_status_chip(f"{widget.width}×{widget.height}", "accent")
        _set_widget_metadata(
            self._header_size_chip,
            tooltip=f"Widget size: {widget.width} by {widget.height}.",
            accessible_name=f"Widget size: {widget.width} by {widget.height}.",
        )
        chips_row.addWidget(self._header_size_chip)
        self._header_size_chip.hide()
        if getattr(widget, "designer_locked", False):
            locked_chip = self._make_status_chip("Locked", "warning")
            _set_widget_metadata(locked_chip, tooltip="Designer state: Locked.", accessible_name="Designer state: Locked.")
            chips_row.addWidget(locked_chip)
        if getattr(widget, "designer_hidden", False):
            hidden_chip = self._make_status_chip("Hidden", "danger")
            _set_widget_metadata(hidden_chip, tooltip="Designer state: Hidden.", accessible_name="Designer state: Hidden.")
            chips_row.addWidget(hidden_chip)
        if layout_parent:
            layout_chip = self._make_status_chip(f"Managed by {layout_parent}", "warning")
            _set_widget_metadata(
                layout_chip,
                tooltip=f"Placement state: Managed by {layout_parent}.",
                accessible_name=f"Placement state: Managed by {layout_parent}.",
            )
            chips_row.addWidget(layout_chip)
        chips_row.addStretch()
        layout.addLayout(chips_row)

        return header

    def _build_multi_selection_header(self, callback_entries):
        common_props = self._collect_multi_common_properties()
        header = QFrame()
        header.setObjectName("workspace_panel_header")
        header.setProperty("panelTone", "property")
        layout = QVBoxLayout()
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        header.setLayout(layout)

        eyebrow = QLabel("Batch Inspector")
        eyebrow.setObjectName("property_panel_header_eyebrow")
        layout.addWidget(eyebrow)

        title = QLabel(f"Selected {_count_label(len(self._selection), 'widget')}")
        title.setObjectName("workspace_section_title")
        layout.addWidget(title)

        widget_types = sorted({widget.widget_type for widget in self._selection})
        subtitle = QLabel(
            f"Primary: {self._primary_widget.name if self._primary_widget else 'none'}"
            f" - Types: {', '.join(widget_types)}"
        )
        subtitle.setObjectName("workspace_section_subtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        header_meta = QLabel("Changes here apply to all selected widgets.")
        header_meta.setObjectName("property_panel_header_meta")
        header_meta.setWordWrap(True)
        layout.addWidget(header_meta)
        eyebrow.hide()
        header_meta.hide()
        _set_widget_metadata(
            eyebrow,
            tooltip="Batch property inspection surface.",
            accessible_name="Batch property inspection surface.",
        )
        _set_widget_metadata(
            title,
            tooltip=f"Batch selection: {title.text()}.",
            accessible_name=f"Batch selection: {title.text()}.",
        )
        _set_widget_metadata(
            subtitle,
            tooltip=subtitle.text(),
            accessible_name=subtitle.text(),
        )
        subtitle.hide()
        _set_widget_metadata(
            header_meta,
            tooltip=header_meta.text(),
            accessible_name=header_meta.text(),
        )
        _set_widget_metadata(
            header,
            tooltip=(
                f"Property batch header: {len(self._selection)} widgets selected. "
                f"Primary: {self._primary_widget.name if self._primary_widget else 'none'}. "
                f"{_count_label(len(widget_types), 'type')}."
            ),
            accessible_name=(
                f"Property batch header: {len(self._selection)} widgets selected. "
                f"Primary: {self._primary_widget.name if self._primary_widget else 'none'}. "
                f"{_count_label(len(widget_types), 'type')}."
            ),
        )

        mixed_total = self._selection_mixed_field_count(callback_entries, common_props)
        metrics = [
            ("Types", _count_label(len(widget_types), "type"), "accent"),
            ("Mixed", _count_label(mixed_total, "mixed field"), "warning"),
            ("Common", _count_label(len(common_props), "shared property"), "success" if common_props else None),
            ("Callbacks", _count_label(len(callback_entries), "shared callback"), None),
        ]
        layout.addLayout(self._build_metric_grid(metrics))

        chips_frame = QFrame()
        chips_frame.setObjectName("property_panel_batch_chips")
        chips_frame.hide()
        chips_row = QHBoxLayout(chips_frame)
        chips_row.setContentsMargins(0, 0, 0, 0)
        chips_row.setSpacing(2)
        types_chip = self._make_status_chip(_count_label(len(widget_types), "type"), "accent")
        _set_widget_metadata(
            types_chip,
            tooltip=f"Batch types: {_count_label(len(widget_types), 'type')}.",
            accessible_name=f"Batch types: {_count_label(len(widget_types), 'type')}.",
        )
        chips_row.addWidget(types_chip)
        mixed_chip = self._make_status_chip(_count_label(mixed_total, "mixed field"), "warning")
        _set_widget_metadata(
            mixed_chip,
            tooltip=f"Batch mixed state: {_count_label(mixed_total, 'mixed field')}.",
            accessible_name=f"Batch mixed state: {_count_label(mixed_total, 'mixed field')}.",
        )
        chips_row.addWidget(mixed_chip)
        batch_chip = self._make_status_chip("Batch edit", "success")
        _set_widget_metadata(
            batch_chip,
            tooltip="Batch edit state: Batch edit.",
            accessible_name="Batch edit state: Batch edit.",
        )
        chips_row.addWidget(batch_chip)
        chips_row.addStretch()
        layout.addWidget(chips_frame)

        return header

    def _build_inspector_group(self, title):
        group = CollapsibleGroupBox(title)
        form = _inspector_form()
        group.setLayout(form)
        self._wire_inspector_collapsible_group(group, title)
        return group, form

    def _build_selection_feedback_strip(self, messages):
        if not messages:
            return None

        frame = QFrame()
        frame.setObjectName("workspace_hint_strip")
        frame.setProperty("panelTone", "property")
        layout = QVBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(1)
        frame.setLayout(layout)

        eyebrow = QLabel("Interaction Notes")
        eyebrow.setObjectName("property_panel_header_eyebrow")
        layout.addWidget(eyebrow)
        eyebrow.hide()
        _set_widget_metadata(
            eyebrow,
            tooltip="Property interaction notes surface.",
            accessible_name="Property interaction notes surface.",
        )

        for message in messages:
            label = QLabel(message)
            label.setObjectName("workspace_section_subtitle")
            label.setWordWrap(True)
            _set_widget_metadata(label, tooltip=message, accessible_name=message)
            layout.addWidget(label)

        notes_summary = " ".join(message.strip() for message in messages if str(message).strip())
        _set_widget_metadata(
            frame,
            tooltip=f"Property interaction notes: {notes_summary}",
            accessible_name=f"Property interaction notes: {notes_summary}",
        )

        return frame

    def _rebuild_form(self):
        self._clear_layout(self._layout)
        self._editors = {}
        self._callback_open_buttons = {}
        self._header_size_chip = None

        if self._primary_widget is None:
            self._context_frame.setVisible(False)
            self._search_shell.setVisible(False)
            self._search_edit.setVisible(False)
            self._no_selection_label = self._create_no_selection_label()
            self._layout.addWidget(self._no_selection_label)
            self._update_panel_metadata()
            return

        self._context_frame.setVisible(False)
        self._search_shell.setVisible(True)
        self._search_edit.setVisible(True)
        if len(self._selection) > 1:
            header = self._build_multi_selection_header(self._collect_multi_callback_entries())
            header.hide()
            self._layout.addWidget(header)
            self._build_multi_selection_form()
            self._on_search_changed(self._search_edit.text())
            return

        w = self._primary_widget
        header = self._build_single_selection_header(w)
        header.hide()
        self._layout.addWidget(header)

        # Layout group
        layout_group = CollapsibleGroupBox("Layout")
        layout_form = _inspector_form()
        layout_group.setLayout(layout_form)
        self._wire_inspector_collapsible_group(layout_group, "Layout")
        for field, label in [("x", "X:"), ("y", "Y:"), ("width", "Width:"), ("height", "Height:")]:
            spin = SpinBox()
            spin.setRange(-9999, 9999)
            spin.setValue(getattr(w, field))
            spin.valueChanged.connect(lambda val, f=field: self._on_common_changed(f, val))
            layout_form.addRow(label, spin)
            self._editors[field] = spin
        self._layout.addWidget(layout_group)

        # Basic group
        basic_group = CollapsibleGroupBox("Basic")
        basic_form = _inspector_form()
        basic_group.setLayout(basic_form)
        self._wire_inspector_collapsible_group(basic_group, "Basic")

        name_edit = LineEdit()
        name_edit.setText(w.name)
        name_edit.editingFinished.connect(lambda editor=name_edit: self._on_name_editing_finished(editor))
        basic_form.addRow("Name:", name_edit)
        self._editors["name"] = name_edit
        self._update_name_editor_metadata(name_edit)
        self._layout.addWidget(basic_group)

        # Type-specific properties - grouped by data vs other
        type_info = WidgetRegistry.instance().get(w.widget_type)
        props = type_info.get("properties", {})

        if props:
            data_props = {
                name: info for name, info in props.items() if info.get("type") in _DATA_PROPERTY_TYPES
            }
            other_props = {
                name: info for name, info in props.items() if info.get("type") not in _DATA_PROPERTY_TYPES
            }
            if other_props:
                self._build_grouped_properties(w, other_props)
            if data_props:
                self._build_data_group(w, data_props)

        # Style properties
        bg_group = CollapsibleGroupBox("Appearance")
        bg_form = _inspector_form()
        bg_group.setLayout(bg_form)
        self._wire_inspector_collapsible_group(bg_group, "Appearance")

        bg = w.background or BackgroundModel()

        bg_type_combo = ComboBox()
        bg_type_combo.addItems(BG_TYPES)
        bg_type_combo.setCurrentText(bg.bg_type)
        bg_type_combo.currentTextChanged.connect(lambda val: self._on_bg_changed("bg_type", val))
        bg_form.addRow("Type:", bg_type_combo)
        self._editors["bg_type"] = bg_type_combo

        if bg.bg_type != "none":
            # Color
            bg_color = EguiColorPicker()
            bg_color.set_value(bg.color)
            bg_color.color_changed.connect(lambda val: self._on_bg_changed("color", val))
            bg_form.addRow("Color:", bg_color)

            # Alpha
            bg_alpha = ComboBox()
            bg_alpha.addItems(ALPHAS)
            bg_alpha.setCurrentText(bg.alpha)
            bg_alpha.currentTextChanged.connect(lambda val: self._on_bg_changed("alpha", val))
            bg_form.addRow("Alpha:", bg_alpha)

            # Radius (for round_rectangle and circle)
            if bg.bg_type in ("round_rectangle", "circle"):
                radius_spin = SpinBox()
                radius_spin.setRange(0, 999)
                radius_spin.setValue(bg.radius)
                radius_spin.valueChanged.connect(lambda val: self._on_bg_changed("radius", val))
                bg_form.addRow("Radius:", radius_spin)

            # Corner radii (for round_rectangle_corners)
            if bg.bg_type == "round_rectangle_corners":
                for corner in ["radius_left_top", "radius_left_bottom", "radius_right_top", "radius_right_bottom"]:
                    spin = SpinBox()
                    spin.setRange(0, 999)
                    spin.setValue(getattr(bg, corner))
                    spin.valueChanged.connect(lambda val, c=corner: self._on_bg_changed(c, val))
                    label = corner.replace("radius_", "").replace("_", " ").title() + ":"
                    bg_form.addRow(label, spin)

            # Stroke
            stroke_spin = SpinBox()
            stroke_spin.setRange(0, 50)
            stroke_spin.setValue(bg.stroke_width)
            stroke_spin.valueChanged.connect(lambda val: self._on_bg_changed("stroke_width", val))
            bg_form.addRow("Stroke Width:", stroke_spin)

            if bg.stroke_width > 0:
                stroke_color = EguiColorPicker()
                stroke_color.set_value(bg.stroke_color)
                stroke_color.color_changed.connect(lambda val: self._on_bg_changed("stroke_color", val))
                bg_form.addRow("Stroke Color:", stroke_color)

                stroke_alpha = ComboBox()
                stroke_alpha.addItems(ALPHAS)
                stroke_alpha.setCurrentText(bg.stroke_alpha)
                stroke_alpha.currentTextChanged.connect(lambda val: self._on_bg_changed("stroke_alpha", val))
                bg_form.addRow("Stroke Alpha:", stroke_alpha)

            # Pressed state
            pressed_check = CheckBox("Enable pressed state")
            pressed_check.setChecked(bg.has_pressed)
            pressed_check.toggled.connect(lambda val: self._on_bg_changed("has_pressed", val))
            bg_form.addRow(pressed_check)

            if bg.has_pressed:
                pressed_color = EguiColorPicker()
                pressed_color.set_value(bg.pressed_color)
                pressed_color.color_changed.connect(lambda val: self._on_bg_changed("pressed_color", val))
                bg_form.addRow("Pressed Color:", pressed_color)

        self._layout.addWidget(bg_group)

        callbacks_group = self._build_callbacks_group(w)
        if callbacks_group is not None:
            self._layout.addWidget(callbacks_group)

        self._layout.addWidget(self._build_designer_state_group())
        feedback_group = self._build_selection_feedback_group()
        if feedback_group is not None:
            self._layout.addWidget(feedback_group)
        self._layout.addStretch()
        self._on_search_changed(self._search_edit.text())

    def _build_multi_selection_form(self):
        callback_entries = self._collect_multi_callback_entries()

        geometry_group, geometry_form = self._build_inspector_group("Batch Geometry")
        for field, label in (("x", "X:"), ("y", "Y:"), ("width", "Width:"), ("height", "Height:")):
            spin = SpinBox()
            spin.setRange(-9999, 9999)
            spin.setValue(getattr(self._primary_widget, field))
            is_mixed = self._is_mixed_values(getattr(widget, field) for widget in self._selection)
            if is_mixed:
                self._update_mixed_editor_metadata(spin, f"Batch {label[:-1]}")
            spin.valueChanged.connect(lambda value, f=field: self._on_multi_common_changed(f, value))
            # UIX-005: mixed-state hint is centralized; avoid repeating "(Mixed)" on every row.
            geometry_form.addRow(label, spin)
            self._editors[f"multi_{field}"] = spin
        self._layout.addWidget(geometry_group)

        self._build_multi_common_properties_group()
        callbacks_group = self._build_multi_callbacks_group(callback_entries)
        if callbacks_group is not None:
            self._layout.addWidget(callbacks_group)
        self._layout.addWidget(self._build_designer_state_group())
        feedback_group = self._build_selection_feedback_group()
        if feedback_group is not None:
            self._layout.addWidget(feedback_group)
        self._layout.addStretch()

    def _build_designer_state_group(self):
        group, form = self._build_inspector_group("Designer")

        locked = CheckBox("Locked")
        locked.setChecked(all(getattr(widget, "designer_locked", False) for widget in self._selection) if self._selection else False)
        locked.toggled.connect(lambda value: self._on_designer_flag_changed("designer_locked", value))
        form.addRow(locked)

        hidden = CheckBox("Hidden")
        hidden.setChecked(all(getattr(widget, "designer_hidden", False) for widget in self._selection) if self._selection else False)
        hidden.toggled.connect(lambda value: self._on_designer_flag_changed("designer_hidden", value))
        form.addRow(hidden)

        return group

    def _layout_parent_name(self, widget):
        parent = getattr(widget, "parent", None)
        if parent is None:
            return ""
        type_info = WidgetRegistry.instance().get(parent.widget_type)
        if type_info.get("layout_func") is None:
            return ""
        return parent.widget_type

    def _selection_feedback_messages(self):
        if not self._selection:
            return []

        if len(self._selection) == 1:
            widget = self._selection[0]
            messages = []
            if getattr(widget, "designer_locked", False):
                messages.append("Locked: canvas drag and resize are disabled for this widget.")
            if getattr(widget, "designer_hidden", False):
                messages.append("Hidden: this widget is skipped by canvas hit testing.")
            layout_parent = self._layout_parent_name(widget)
            if layout_parent:
                messages.append(
                    f"Layout-managed: x/y come from parent {layout_parent}, so canvas handles are disabled."
                )
            return messages

        messages = []
        locked_count = sum(1 for widget in self._selection if getattr(widget, "designer_locked", False))
        hidden_count = sum(1 for widget in self._selection if getattr(widget, "designer_hidden", False))
        layout_count = sum(1 for widget in self._selection if self._layout_parent_name(widget))

        if locked_count:
            noun = "widget" if locked_count == 1 else "widgets"
            messages.append(
                f"Locked: {locked_count} selected {noun} cannot be moved or resized from the canvas."
            )
        if hidden_count:
            noun = "widget" if hidden_count == 1 else "widgets"
            verb = "is" if hidden_count == 1 else "are"
            messages.append(
                f"Hidden: {hidden_count} selected {noun} {verb} skipped by canvas hit testing."
            )
        if layout_count:
            noun = "widget" if layout_count == 1 else "widgets"
            messages.append(
                f"Layout-managed: {layout_count} selected {noun} use parent-controlled positioning."
            )

        return messages

    def _build_selection_feedback_group(self):
        return self._build_selection_feedback_strip(self._selection_feedback_messages())

    def _build_multi_common_properties_group(self):
        common_props = self._collect_multi_common_properties()
        if not common_props:
            return

        group, form = self._build_inspector_group("Common Properties")

        for prop_name, prop_info in common_props:
            current_value = self._primary_widget.properties.get(prop_name)
            values = [widget.properties.get(prop_name) for widget in self._selection]
            is_mixed = self._is_mixed_values(values)
            has_missing_file = any(self._is_missing_file_property(prop_name, prop_info, value) for value in values)
            editor = self._create_property_editor(
                prop_name,
                prop_info,
                current_value,
                prop_changed_handler=self._on_multi_prop_changed,
            )
            if editor is None:
                continue

            if is_mixed:
                self._apply_mixed_editor_state(editor, prop_name, prop_info, values)
            if has_missing_file:
                self._apply_missing_file_editor_state(editor, prop_name, prop_info, current_value, values=values)

            label = prop_name.replace("_", " ").title()
            if has_missing_file:
                label += " (Missing)"
            label += ":"
            form.addRow(label, editor)

        if form.rowCount() > 0:
            self._layout.addWidget(group)

    def _normalize_mixed_value(self, value):
        if isinstance(value, dict):
            return tuple(
                (key, self._normalize_mixed_value(item))
                for key, item in sorted(value.items())
            )
        if isinstance(value, (list, tuple)):
            return tuple(self._normalize_mixed_value(item) for item in value)
        if isinstance(value, set):
            return tuple(sorted(self._normalize_mixed_value(item) for item in value))
        return value

    def _is_mixed_values(self, values):
        iterator = iter(values)
        try:
            first_value = self._normalize_mixed_value(next(iterator))
        except StopIteration:
            return False

        for value in iterator:
            if self._normalize_mixed_value(value) != first_value:
                return True
        return False

    def _apply_mixed_editor_state(self, editor, prop_name, prop_info, values):
        del values

        tooltip = self._mixed_value_tooltip()
        _set_widget_metadata(editor, tooltip=tooltip)

        ptype = prop_info.get("type", "string")
        target = editor
        if ptype in {"image_file", "font_file", "text_file"}:
            target = self._editors.get(f"prop_{prop_name}", editor)
            with QSignalBlocker(target):
                if hasattr(target, "setPlaceholderText"):
                    target.setPlaceholderText("Mixed values")
                if hasattr(target, "setCurrentIndex"):
                    target.setCurrentIndex(-1)
            self._update_file_selector_metadata(prop_name, target, tooltip=tooltip)
            return

        if isinstance(target, LineEdit):
            with QSignalBlocker(target):
                target.clear()
                target.setPlaceholderText("Mixed values")
            self._update_mixed_editor_metadata(target, f"{self._property_label(prop_name)} property", tooltip=tooltip)
            return

        if isinstance(target, EditableComboBox):
            with QSignalBlocker(target):
                if hasattr(target, "setPlaceholderText"):
                    target.setPlaceholderText("Mixed values")
                if hasattr(target, "setCurrentIndex"):
                    target.setCurrentIndex(-1)
            self._update_mixed_editor_metadata(target, f"{self._property_label(prop_name)} property", tooltip=tooltip)
            return

        if isinstance(target, ComboBox):
            with QSignalBlocker(target):
                if hasattr(target, "setPlaceholderText"):
                    target.setPlaceholderText("Mixed values")
                if hasattr(target, "setCurrentIndex"):
                    target.setCurrentIndex(-1)
            self._update_mixed_editor_metadata(target, f"{self._property_label(prop_name)} property", tooltip=tooltip)
            return

        if isinstance(target, CheckBox):
            with QSignalBlocker(target):
                target.setTristate(True)
                target.setCheckState(Qt.PartiallyChecked)
            self._update_mixed_editor_metadata(target, f"{self._property_label(prop_name)} property", tooltip=tooltip)
            return

        self._update_mixed_editor_metadata(target, f"{self._property_label(prop_name)} property", tooltip=tooltip)

    def _is_missing_file_property(self, prop_name, prop_info, value):
        return bool(self._missing_file_property_reason(prop_name, prop_info, value))

    def _source_file_path_for_property(self, prop_info, value):
        if not value or not self._source_resource_dir:
            return ""

        ptype = prop_info.get("type", "")
        if ptype == "image_file":
            return os.path.join(self._source_resource_dir, "images", value)
        if ptype in {"font_file", "text_file"}:
            return os.path.join(self._source_resource_dir, value)
        return ""

    def _missing_file_property_reason(self, prop_name, prop_info, value):
        del prop_name

        if not value:
            return ""

        ptype = prop_info.get("type", "")
        if ptype == "image_file":
            if self._resource_catalog is not None and not self._resource_catalog.has_image(value):
                return "catalog"
        elif ptype == "font_file":
            if self._resource_catalog is not None and not self._resource_catalog.has_font(value):
                return "catalog"
        elif ptype == "text_file":
            if self._resource_catalog is not None and not self._resource_catalog.has_text_file(value):
                return "catalog"
        else:
            return ""

        source_path = self._source_file_path_for_property(prop_info, value)
        if source_path and not os.path.isfile(source_path):
            return "disk"
        return ""

    def _missing_file_message(self, reason, plural=False):
        if plural:
            return "One or more selected widgets reference resource files that are missing from the project catalog or source directory."
        if reason == "disk":
            return "Selected resource file is listed in the project catalog, but the source file is missing on disk. Restore it or choose another file."
        return "Selected resource file is not present in the project catalog. Re-import it or choose another file."

    def _apply_missing_file_editor_state(self, editor, prop_name, prop_info, current_value, values=None):
        reason = self._missing_file_property_reason(prop_name, prop_info, current_value)
        plural = False
        if values is not None:
            reasons = {
                self._missing_file_property_reason(prop_name, prop_info, value)
                for value in values
            }
            reasons.discard("")
            if not reasons:
                return
            if len(reasons) > 1 or len(values) > 1:
                plural = True
                reason = next(iter(reasons))
            elif not reason:
                reason = next(iter(reasons))

        if not reason:
            return

        target = editor
        if prop_info.get("type", "") in {"image_file", "font_file", "text_file"}:
            target = self._editors.get(f"prop_{prop_name}", editor)

        message = self._missing_file_message(reason, plural=plural)
        existing_tooltip = target.toolTip().strip()
        if existing_tooltip and message not in existing_tooltip:
            message = f"{existing_tooltip}\n{message}"
        if prop_info.get("type", "") in {"image_file", "font_file", "text_file"}:
            self._update_file_selector_metadata(prop_name, target, tooltip=message)
        else:
            _set_widget_metadata(target, tooltip=message)

    def _collect_multi_common_properties(self):
        if not self._selection:
            return []

        descriptors = [WidgetRegistry.instance().get(widget.widget_type) for widget in self._selection]
        if not descriptors:
            return []

        base_props = descriptors[0].get("properties", {})
        result = []
        for prop_name, prop_info in base_props.items():
            ptype = prop_info.get("type", "string")
            if ptype not in _MULTI_SUPPORTED_PROPERTY_TYPES:
                continue

            shared = True
            for widget, descriptor in zip(self._selection[1:], descriptors[1:]):
                other_info = descriptor.get("properties", {}).get(prop_name)
                if not other_info:
                    shared = False
                    break
                if other_info.get("type", "string") != ptype:
                    shared = False
                    break
                visible_when = other_info.get("ui_visible_when")
                if visible_when and not self._check_visibility(widget, visible_when):
                    shared = False
                    break

            visible_when = prop_info.get("ui_visible_when")
            if visible_when and not self._check_visibility(self._selection[0], visible_when):
                shared = False

            if shared:
                result.append((prop_name, prop_info))

        return result

    # ── Property group builders ───────────────────────────────────

    def _check_visibility(self, widget, condition):
        """Check ui_visible_when condition against widget properties.

        Supported conditions:
            {"prop_name": "empty"}   — visible when prop is empty/falsy
            {"prop_name": "!empty"}  — visible when prop is non-empty/truthy
        """
        for prop_name, rule in condition.items():
            val = widget.properties.get(prop_name, "")
            if rule == "empty":
                if val:
                    return False
            elif rule == "!empty":
                if not val:
                    return False
        return True

    def _build_grouped_properties(self, w, props):
        """Build property groups driven by ui_group and ui_visible_when descriptors.

        Properties are grouped by their ``ui_group`` value (default "properties").
        Properties with ``ui_visible_when`` are conditionally shown/hidden.
        Groups are rendered in encounter order.
        """
        from collections import OrderedDict
        groups = OrderedDict()

        for prop_name, prop_info in props.items():
            # Check visibility condition
            vis = prop_info.get("ui_visible_when")
            if vis and not self._check_visibility(w, vis):
                continue

            group_key = prop_info.get("ui_group", "properties")
            if group_key not in groups:
                groups[group_key] = []
            groups[group_key].append((prop_name, prop_info))

        def _group_sort_key(item):
            raw_label = _UI_GROUP_LABELS.get(item[0], item[0].replace("_", " ").title())
            normalized_label = "Behavior" if raw_label in {"Properties", "Main"} else raw_label
            return (_INSPECTOR_GROUP_PRIORITY.get(normalized_label, 99), item[0])

        sorted_groups = sorted(groups.items(), key=_group_sort_key)

        for group_key, group_props in sorted_groups:
            group_label = _UI_GROUP_LABELS.get(group_key, group_key.replace("_", " ").title())
            if group_label in {"Properties", "Main"}:
                group_label = "Behavior"
            group_box = CollapsibleGroupBox(group_label)
            form = _inspector_form()
            group_box.setLayout(form)
            self._wire_inspector_collapsible_group(group_box, group_label)

            for prop_name, prop_info in group_props:
                editor = self._create_property_editor(prop_name, prop_info, w.properties.get(prop_name))
                if editor:
                    # Derive a human-readable label from prop_name
                    label = prop_name
                    # Strip common prefixes for cleaner display
                    for prefix in ("image_", "font_"):
                        if label.startswith(prefix) and group_key != "main":
                            label = label[len(prefix):]
                            break
                    label = label.replace("_", " ").title()
                    if self._is_missing_file_property(prop_name, prop_info, w.properties.get(prop_name)):
                        label += " (Missing)"
                        self._apply_missing_file_editor_state(editor, prop_name, prop_info, w.properties.get(prop_name))
                    label += ":"
                    form.addRow(label, editor)

            self._layout.addWidget(group_box)

    def _build_data_group(self, w, props):
        group_box = CollapsibleGroupBox("Data")
        form = _inspector_form()
        group_box.setLayout(form)
        self._wire_inspector_collapsible_group(group_box, "Data")

        for prop_name, prop_info in props.items():
            vis = prop_info.get("ui_visible_when")
            if vis and not self._check_visibility(w, vis):
                continue
            editor = self._create_property_editor(prop_name, prop_info, w.properties.get(prop_name))
            if editor is None:
                continue
            label = prop_name
            for prefix in ("image_", "font_"):
                if label.startswith(prefix):
                    label = label[len(prefix):]
                    break
            label = label.replace("_", " ").title()
            if self._is_missing_file_property(prop_name, prop_info, w.properties.get(prop_name)):
                label += " (Missing)"
                self._apply_missing_file_editor_state(editor, prop_name, prop_info, w.properties.get(prop_name))
            form.addRow(f"{label}:", editor)

        if form.rowCount() > 0:
            self._layout.addWidget(group_box)

    def _humanize_callback_name(self, event_name):
        name = str(event_name or "").strip()
        if name.startswith("on") and len(name) > 2 and name[2].isupper():
            name = name[2:]
        name = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name)
        return name.strip().title() or "Callback"

    def _suggest_callback_name(self, widget, event_name):
        widget_name = sanitize_widget_name(getattr(widget, "name", "")) or getattr(widget, "widget_type", "widget")
        suffix = self._humanize_callback_name(event_name).lower().replace(" ", "_")
        return f"on_{widget_name}_{suffix}"

    def _callback_signature_preview(self, signature):
        if not signature:
            return ""
        try:
            return signature.format(func_name="callback_name")
        except Exception:
            return signature

    def _callback_tooltip(self, widget, event_name, signature):
        parts = [
            "Leave empty to disable this callback.",
            f"Suggested: {self._suggest_callback_name(widget, event_name)}",
        ]
        preview = self._callback_signature_preview(signature)
        if preview:
            parts.append(f"Signature: {preview}")
        return "\n".join(parts)

    def _callback_entries(self, widget):
        entries = [
            {
                "event_name": "onClick",
                "value": widget.on_click,
                "signature": "void {func_name}(egui_view_t *self)",
                "use_event_dict": False,
            }
        ]

        descriptor = WidgetRegistry.instance().get(widget.widget_type)
        for event_name, event_info in descriptor.get("events", {}).items():
            entries.append(
                {
                    "event_name": event_name,
                    "value": widget.events.get(event_name, ""),
                    "signature": event_info.get("signature", ""),
                    "use_event_dict": True,
                }
            )

        known_names = {entry["event_name"] for entry in entries}
        for event_name in sorted(widget.events):
            if event_name in known_names:
                continue
            entries.append(
                {
                    "event_name": event_name,
                    "value": widget.events.get(event_name, ""),
                    "signature": "",
                    "use_event_dict": True,
                }
            )

        return entries

    def _callback_entry_map(self, widget):
        return {entry["event_name"]: entry for entry in self._callback_entries(widget)}

    def _collect_multi_callback_entries(self):
        if not self._selection:
            return []

        entry_maps = [self._callback_entry_map(widget) for widget in self._selection]
        if not entry_maps:
            return []

        shared_names = set(entry_maps[0])
        for entry_map in entry_maps[1:]:
            shared_names &= set(entry_map)

        entries = []
        for event_name in sorted(shared_names, key=lambda name: (name != "onClick", self._humanize_callback_name(name))):
            base_entry = entry_maps[0][event_name]
            compatible = True
            for entry_map in entry_maps[1:]:
                other_entry = entry_map[event_name]
                if (
                    other_entry.get("use_event_dict") != base_entry.get("use_event_dict")
                    or other_entry.get("signature", "") != base_entry.get("signature", "")
                ):
                    compatible = False
                    break
            if not compatible:
                continue

            current_values = [
                self._current_callback_value(widget, event_name, base_entry.get("use_event_dict", False))
                for widget in self._selection
            ]
            entries.append(
                {
                    "event_name": event_name,
                    "signature": base_entry.get("signature", ""),
                    "use_event_dict": base_entry.get("use_event_dict", False),
                    "current_values": current_values,
                    "is_mixed": self._is_mixed_values(current_values),
                }
            )

        return entries

    def _build_callbacks_group(self, widget):
        entries = self._callback_entries(widget)
        if not entries:
            return None

        group = CollapsibleGroupBox("Callbacks")
        form = _inspector_form()
        group.setLayout(form)
        self._wire_inspector_collapsible_group(group, "Callbacks")

        for entry in entries:
            event_name = entry["event_name"]
            editor = LineEdit()
            editor.setText(entry["value"])
            editor.setPlaceholderText(self._suggest_callback_name(widget, event_name))
            self._update_callback_editor_metadata(
                editor,
                event_name,
                self._callback_tooltip(widget, event_name, entry["signature"]),
            )
            editor.editingFinished.connect(
                lambda editor=editor,
                current_widget=widget,
                event_name=event_name,
                signature=entry["signature"],
                use_event_dict=entry["use_event_dict"]: self._on_callback_editing_finished(
                    editor,
                    current_widget,
                    event_name,
                    signature,
                    use_event_dict,
                )
            )
            self._editors[f"callback_{event_name}"] = editor
            container, button = self._build_callback_editor_row(
                editor,
                event_name,
                lambda editor=editor,
                current_widget=widget,
                event_name=event_name,
                signature=entry["signature"]: self._request_single_callback_user_code(
                    editor,
                    current_widget,
                    event_name,
                    signature,
                ),
            )
            self._callback_open_buttons[f"callback_{event_name}"] = button
            form.addRow(f"{self._humanize_callback_name(event_name)}:", container)

        return group

    # ── Property editor factory ───────────────────────────────────

    def _suggest_multi_callback_name(self, event_name):
        suffix = self._humanize_callback_name(event_name).lower().replace(" ", "_")
        widget_types = sorted({widget.widget_type for widget in self._selection})
        if len(widget_types) == 1:
            return f"on_{sanitize_widget_name(widget_types[0])}_{suffix}"
        return f"on_selection_{suffix}"

    def _multi_callback_tooltip(self, event_name, signature, is_mixed):
        parts = []
        if is_mixed:
            parts.append("Selected widgets currently have different callback names. Editing here will normalize them.")
        parts.extend(
            [
                "Editing this field applies the same callback to all selected widgets.",
                "Leave empty to disable this callback for all selected widgets.",
                f"Suggested: {self._suggest_multi_callback_name(event_name)}",
            ]
        )
        preview = self._callback_signature_preview(signature)
        if preview:
            parts.append(f"Signature: {preview}")
        return "\n".join(parts)

    def _apply_multi_callback_editor_state(self, editor, event_name, signature, current_values):
        is_mixed = self._is_mixed_values(current_values)
        with QSignalBlocker(editor):
            if is_mixed:
                editor.clear()
                editor.setPlaceholderText("Mixed values")
            else:
                editor.setText(current_values[0] if current_values else "")
                editor.setPlaceholderText(self._suggest_multi_callback_name(event_name))
            if hasattr(editor, "setModified"):
                editor.setModified(False)
        tooltip = self._multi_callback_tooltip(event_name, signature, is_mixed)
        self._update_callback_editor_metadata(editor, event_name, tooltip)
        button = self._callback_open_buttons.get(f"callback_{event_name}")
        if button is not None:
            button.setVisible(not is_mixed)
            button.setEnabled(not is_mixed)
            if is_mixed:
                button_tooltip = "Normalize this callback first to open a single user function."
            else:
                button_tooltip = "Open or create this callback in the page user source."
            self._update_callback_button_metadata(button, event_name, not is_mixed, button_tooltip)

    def _build_multi_callbacks_group(self, entries=None):
        entries = list(entries or self._collect_multi_callback_entries())
        if not entries:
            return None

        group = CollapsibleGroupBox("Callbacks")
        form = _inspector_form()
        group.setLayout(form)
        self._wire_inspector_collapsible_group(group, "Callbacks")

        for entry in entries:
            event_name = entry["event_name"]
            editor = LineEdit()
            self._apply_multi_callback_editor_state(
                editor,
                event_name,
                entry["signature"],
                entry["current_values"],
            )
            editor.editingFinished.connect(
                lambda editor=editor,
                event_name=event_name,
                signature=entry["signature"],
                use_event_dict=entry["use_event_dict"]: self._on_multi_callback_editing_finished(
                    editor,
                    event_name,
                    signature,
                    use_event_dict,
                )
            )
            self._editors[f"callback_{event_name}"] = editor
            container, button = self._build_callback_editor_row(
                editor,
                event_name,
                lambda editor=editor,
                event_name=event_name,
                signature=entry["signature"],
                use_event_dict=entry["use_event_dict"]: self._request_multi_callback_user_code(
                    editor,
                    event_name,
                    signature,
                    use_event_dict,
                ),
                enabled=not entry["is_mixed"],
                tooltip="Open or create this callback in the page user source."
                if not entry["is_mixed"]
                else "Normalize this callback first to open a single user function.",
            )
            self._callback_open_buttons[f"callback_{event_name}"] = button
            label = self._humanize_callback_name(event_name)
            form.addRow(f"{label}:", container)

        return group

    def _build_callback_editor_row(
        self,
        editor,
        event_name,
        open_handler,
        enabled=True,
        tooltip="Open or create this callback in the page user source.",
    ):
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(editor, 1)

        button = ToolButton()
        button.setText("Open")
        button.setVisible(enabled)
        button.setEnabled(enabled)
        self._update_callback_button_metadata(button, event_name, enabled, tooltip)
        button.clicked.connect(open_handler)
        layout.addWidget(button)
        return container, button

    def _request_single_callback_user_code(self, editor, widget, event_name, signature):
        if widget is None:
            return
        callback_name = sanitize_widget_name(editor.text().strip() or self._suggest_callback_name(widget, event_name))
        if not callback_name:
            return
        self.user_code_requested.emit(callback_name, signature)

    def _request_multi_callback_user_code(self, editor, event_name, signature, use_event_dict):
        if not self._selection:
            return
        current_values = [
            self._current_callback_value(widget, event_name, use_event_dict)
            for widget in self._selection
        ]
        if self._is_mixed_values(current_values):
            return
        callback_name = sanitize_widget_name(editor.text().strip())
        if not callback_name and current_values:
            callback_name = sanitize_widget_name(current_values[0])
        if not callback_name:
            callback_name = sanitize_widget_name(self._suggest_multi_callback_name(event_name))
        if not callback_name:
            return
        self.user_code_requested.emit(callback_name, signature)

    def _create_property_editor(self, prop_name, prop_info, current_value, prop_changed_handler=None, file_prop_handler=None):
        ptype = prop_info.get("type", "string")
        prop_changed_handler = prop_changed_handler or self._on_prop_changed
        file_prop_handler = file_prop_handler or self._on_file_prop_changed

        if ptype == "string":
            # For "text" property on label/button, use EditableComboBox with @string/ completions
            if prop_name == "text" and self._string_keys:
                editor = EditableComboBox()
                # Add @string/key references from the i18n catalog
                for key in self._string_keys:
                    editor.addItem(f"@string/{key}")
                cur = str(current_value or "")
                if cur and editor.findText(cur) < 0:
                    editor.addItem(cur)
                editor.setCurrentText(cur)
                editor.currentTextChanged.connect(lambda val: prop_changed_handler(prop_name, val))
                self._editors[f"prop_{prop_name}"] = editor
                return editor
            else:
                editor = LineEdit()
                editor.setText(str(current_value or ""))
                editor.textChanged.connect(lambda val: prop_changed_handler(prop_name, val))
                self._editors[f"prop_{prop_name}"] = editor
                return editor

        elif ptype == "int":
            editor = SpinBox()
            editor.setRange(prop_info.get("min", 0), prop_info.get("max", 9999))
            editor.setValue(int(current_value or 0))
            editor.valueChanged.connect(lambda val: prop_changed_handler(prop_name, val))
            self._editors[f"prop_{prop_name}"] = editor
            return editor

        elif ptype == "bool":
            editor = CheckBox()
            editor.setChecked(bool(current_value))
            editor.toggled.connect(lambda val: prop_changed_handler(prop_name, val))
            self._editors[f"prop_{prop_name}"] = editor
            return editor

        elif ptype == "color":
            editor = EguiColorPicker()
            editor.set_value(str(current_value or COLORS[0]))
            editor.color_changed.connect(lambda val: prop_changed_handler(prop_name, val))
            self._editors[f"prop_{prop_name}"] = editor
            return editor

        elif ptype == "alpha":
            editor = ComboBox()
            editor.addItems(ALPHAS)
            editor.setCurrentText(str(current_value or "EGUI_ALPHA_100"))
            editor.currentTextChanged.connect(lambda val: prop_changed_handler(prop_name, val))
            self._editors[f"prop_{prop_name}"] = editor
            return editor

        elif ptype == "font":
            # Built-in font selector with preview
            merged = self._merged_fonts()
            editor = EguiFontSelector(fonts=merged)
            cur = str(current_value or merged[0] if merged else "")
            editor.set_value(cur)
            editor.font_changed.connect(lambda val: prop_changed_handler(prop_name, val))
            self._editors[f"prop_{prop_name}"] = editor
            return editor

        elif ptype == "align":
            editor = ComboBox()
            editor.addItems(ALIGNS)
            editor.setCurrentText(str(current_value or "EGUI_ALIGN_CENTER"))
            editor.currentTextChanged.connect(lambda val: prop_changed_handler(prop_name, val))
            self._editors[f"prop_{prop_name}"] = editor
            return editor

        elif ptype == "orientation":
            editor = ComboBox()
            editor.addItems(["vertical", "horizontal"])
            editor.setCurrentText(str(current_value or "vertical"))
            editor.currentTextChanged.connect(lambda val: prop_changed_handler(prop_name, val))
            self._editors[f"prop_{prop_name}"] = editor
            return editor

        # ── New resource-related property types ───────────────────

        elif ptype == "image_file":
            return self._create_file_selector(prop_name, current_value,
                                              self._catalog_images(), "Image files (*.png *.bmp *.jpg *.jpeg *.gif)", file_prop_handler=file_prop_handler)

        elif ptype == "image_format":
            editor = ComboBox()
            editor.addItems(IMAGE_FORMATS)
            editor.setCurrentText(str(current_value or "rgb565"))
            editor.currentTextChanged.connect(lambda val: prop_changed_handler(prop_name, val))
            self._editors[f"prop_{prop_name}"] = editor
            return editor

        elif ptype == "image_alpha":
            editor = ComboBox()
            editor.addItems(IMAGE_ALPHAS)
            editor.setCurrentText(str(current_value or "4"))
            editor.currentTextChanged.connect(lambda val: prop_changed_handler(prop_name, val))
            self._editors[f"prop_{prop_name}"] = editor
            return editor

        elif ptype == "image_external":
            editor = ComboBox()
            editor.addItems(IMAGE_EXTERNALS)
            editor.setCurrentText(str(current_value or "0"))
            editor.currentTextChanged.connect(lambda val: prop_changed_handler(prop_name, val))
            self._editors[f"prop_{prop_name}"] = editor
            return editor

        elif ptype == "font_file":
            return self._create_file_selector(prop_name, current_value,
                                              self._catalog_fonts(), "Font files (*.ttf *.otf)", file_prop_handler=file_prop_handler)

        elif ptype == "font_pixelsize":
            editor = EditableComboBox()
            editor.addItems(FONT_PIXELSIZES)
            editor.setCurrentText(str(current_value or "16"))
            editor.currentTextChanged.connect(lambda val: prop_changed_handler(prop_name, val))
            self._editors[f"prop_{prop_name}"] = editor
            return editor

        elif ptype == "font_fontbitsize":
            editor = ComboBox()
            editor.addItems(FONT_BITSIZES)
            editor.setCurrentText(str(current_value or "4"))
            editor.currentTextChanged.connect(lambda val: prop_changed_handler(prop_name, val))
            self._editors[f"prop_{prop_name}"] = editor
            return editor

        elif ptype == "font_external":
            editor = ComboBox()
            editor.addItems(FONT_EXTERNALS)
            editor.setCurrentText(str(current_value or "0"))
            editor.currentTextChanged.connect(lambda val: prop_changed_handler(prop_name, val))
            self._editors[f"prop_{prop_name}"] = editor
            return editor

        elif ptype == "text_file":
            return self._create_file_selector(prop_name, current_value,
                                              self._catalog_text_files(), "Text files (*.txt)", file_prop_handler=file_prop_handler)

        return None

    def _create_file_selector(self, prop_name, current_value, catalog_items, file_filter, file_prop_handler=None):
        """Create a ComboBox + '...' browse button for file selection."""
        file_prop_handler = file_prop_handler or self._on_file_prop_changed
        container = QWidget()
        h_layout = QHBoxLayout(container)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(2)

        combo = EditableComboBox()
        # Add empty option (none selected)
        items = [""] + catalog_items
        combo.addItems(items)
        cur = str(current_value or "")
        if cur and combo.findText(cur) < 0:
            combo.addItem(cur)
        combo.setCurrentText(cur)
        combo.currentTextChanged.connect(lambda val: file_prop_handler(prop_name, val))
        combo.currentTextChanged.connect(lambda _val, name=prop_name, target=combo: self._update_file_selector_metadata(name, target))
        h_layout.addWidget(combo, 1)

        browse_btn = ToolButton()
        browse_btn.setText("Browse")
        _set_widget_metadata(
            browse_btn,
            tooltip=self._browse_button_tooltip(prop_name, file_filter),
            accessible_name=f"Browse {self._property_label(prop_name)}",
        )
        browse_btn.clicked.connect(lambda: self._browse_file(combo, file_filter))
        h_layout.addWidget(browse_btn)

        self._editors[f"prop_{prop_name}"] = combo
        self._update_file_selector_metadata(prop_name, combo)
        return container

    def _browse_file(self, combo, file_filter):
        """Open a file dialog to select a file."""
        src_dir = self._default_file_browse_dir(file_filter)
        if not src_dir:
            QMessageBox.warning(
                self,
                "Resource Directory Missing",
                "Please save the project first so Designer has a resource directory for importing files.",
            )
            return

        path, _ = QFileDialog.getOpenFileName(self, "Select File", src_dir, file_filter)
        if path:
            filename = os.path.basename(path)
            path_dir = os.path.dirname(path)
            if path_dir and os.path.isdir(path_dir):
                self._last_external_file_dir = path_dir
            imported = False
            # Auto-import: copy to .eguiproject/resources/ if not there
            if self._source_resource_dir:
                # Images go in images/ subfolder, fonts/text go in root
                ext = os.path.splitext(filename)[1].lower()
                if ext in ('.png', '.bmp', '.jpg', '.jpeg'):
                    dest_dir = os.path.join(self._source_resource_dir, "images")
                else:
                    dest_dir = self._source_resource_dir
                dest = os.path.join(dest_dir, filename)
                if not os.path.isfile(dest):
                    import shutil
                    os.makedirs(dest_dir, exist_ok=True)
                    shutil.copy2(path, dest)
                    imported = True
                # Add to catalog
                if self._resource_catalog:
                    had_file = (
                        self._resource_catalog.has_image(filename)
                        or self._resource_catalog.has_font(filename)
                        or self._resource_catalog.has_text_file(filename)
                    )
                    self._resource_catalog.add_file(filename)
                    if not had_file:
                        imported = True

            # Ensure filename is in combo
            if combo.findText(filename) < 0:
                combo.addItem(filename)
            combo.setCurrentText(filename)
            if imported:
                self.resource_imported.emit()

    def _default_file_browse_dir(self, file_filter):
        if self._last_external_file_dir and os.path.isdir(self._last_external_file_dir):
            return self._last_external_file_dir

        src_dir = self._source_resource_dir or ""
        if not src_dir or not os.path.isdir(src_dir):
            return ""

        lower_filter = (file_filter or "").lower()
        if any(ext in lower_filter for ext in (".png", ".bmp", ".jpg", ".jpeg")):
            images_dir = os.path.join(src_dir, "images")
            if os.path.isdir(images_dir):
                return images_dir

        return src_dir

    def _on_file_prop_changed(self, prop_name, value):
        """Handle file property change - rebuild form if needed for conditional groups."""
        if self._updating or self._primary_widget is None:
            return
        self._primary_widget.properties[prop_name] = value

        # Changing font_file or image_file may show/hide config groups
        if prop_name in ("image_file", "font_file"):
            self._updating = True
            self._rebuild_form()
            self._updating = False

        self.property_changed.emit()

    def _on_common_changed(self, field, value):
        if self._updating or self._primary_widget is None:
            return
        if field == "name":
            self._primary_widget.name = value
        else:
            setattr(self._primary_widget, field, value)
        self.property_changed.emit()

    def _on_name_editing_finished(self, editor):
        if self._updating or self._primary_widget is None:
            return

        raw_name = editor.text()
        ok, resolved_name, message = resolve_widget_name(self._primary_widget, raw_name)
        current_name = self._primary_widget.name

        if not ok:
            with QSignalBlocker(editor):
                editor.setText(current_name)
            self._update_name_editor_metadata(editor, message)
            self.validation_message.emit(message)
            return

        name_changed = resolved_name != current_name
        text_changed = raw_name != resolved_name
        if name_changed:
            self._primary_widget.name = resolved_name

        if name_changed or text_changed:
            self._updating = True
            self._rebuild_form()
            self._updating = False
            refreshed = self._editors.get("name")
            if refreshed is not None and message:
                self._update_name_editor_metadata(refreshed, message)
        elif message:
            self._update_name_editor_metadata(editor, message)

        if message:
            self.validation_message.emit(message)

        if name_changed:
            self.property_changed.emit()

    def _current_callback_value(self, widget, event_name, use_event_dict):
        if use_event_dict:
            return widget.events.get(event_name, "")
        return widget.on_click

    def _set_callback_value(self, widget, event_name, use_event_dict, value):
        if use_event_dict:
            if value:
                widget.events[event_name] = value
            else:
                widget.events.pop(event_name, None)
            return
        widget.on_click = value

    def _on_callback_editing_finished(self, editor, widget, event_name, signature, use_event_dict):
        if self._updating or widget is None:
            return

        raw_name = editor.text()
        normalized = sanitize_widget_name(raw_name)
        current_value = self._current_callback_value(widget, event_name, use_event_dict)

        if normalized and not is_valid_widget_name(normalized):
            with QSignalBlocker(editor):
                editor.setText(current_value)
            self._update_callback_editor_metadata(
                editor,
                event_name,
                self._callback_tooltip(widget, event_name, signature),
            )
            self.validation_message.emit(_CALLBACK_INVALID_MESSAGE)
            return

        changed = normalized != current_value
        text_changed = raw_name != normalized

        if changed:
            self._set_callback_value(widget, event_name, use_event_dict, normalized)

        if changed or text_changed:
            with QSignalBlocker(editor):
                editor.setText(normalized)

        self._update_callback_editor_metadata(
            editor,
            event_name,
            self._callback_tooltip(widget, event_name, signature),
        )

        if text_changed and normalized:
            self.validation_message.emit(f"Callback name normalized to '{normalized}'.")

        if changed:
            self.property_changed.emit()

    def _on_multi_callback_editing_finished(self, editor, event_name, signature, use_event_dict):
        if self._updating or not self._selection:
            return

        current_values = [
            self._current_callback_value(widget, event_name, use_event_dict)
            for widget in self._selection
        ]
        is_mixed = self._is_mixed_values(current_values)
        raw_name = editor.text()
        if is_mixed and not raw_name and hasattr(editor, "isModified") and not editor.isModified():
            self._apply_multi_callback_editor_state(editor, event_name, signature, current_values)
            return

        normalized = sanitize_widget_name(raw_name)

        if normalized and not is_valid_widget_name(normalized):
            self._apply_multi_callback_editor_state(editor, event_name, signature, current_values)
            self.validation_message.emit(_CALLBACK_INVALID_MESSAGE)
            return

        changed = any(value != normalized for value in current_values)
        text_changed = raw_name != normalized

        if changed:
            for widget in self._selection:
                self._set_callback_value(widget, event_name, use_event_dict, normalized)
            current_values = [normalized for _ in self._selection]

        if changed or text_changed or is_mixed:
            self._apply_multi_callback_editor_state(editor, event_name, signature, current_values)

        if text_changed and normalized:
            self.validation_message.emit(f"Callback name normalized to '{normalized}'.")

        if changed:
            self.property_changed.emit()

    def _on_prop_changed(self, prop_name, value):
        if self._updating or self._primary_widget is None:
            return
        self._primary_widget.properties[prop_name] = value
        self.property_changed.emit()

    def _on_multi_common_changed(self, field, value):
        if self._updating or not self._selection:
            return
        for widget in self._selection:
            setattr(widget, field, value)
        self.property_changed.emit()

    def _on_multi_prop_changed(self, prop_name, value):
        if self._updating or not self._selection:
            return

        for widget in self._selection:
            if prop_name in widget.properties:
                widget.properties[prop_name] = value

        if self._multi_prop_requires_rebuild(prop_name):
            self._updating = True
            self._rebuild_form()
            self._updating = False

        self.property_changed.emit()

    def _multi_prop_requires_rebuild(self, prop_name):
        for widget in self._selection:
            descriptor = WidgetRegistry.instance().get(widget.widget_type)
            for info in descriptor.get("properties", {}).values():
                visible_when = info.get("ui_visible_when", {})
                if prop_name in visible_when:
                    return True
        return False

    def _on_bg_changed(self, field, value):
        if self._updating or self._primary_widget is None:
            return

        if self._primary_widget.background is None:
            self._primary_widget.background = BackgroundModel()

        bg = self._primary_widget.background
        setattr(bg, field, value)

        # If bg_type changed to "none", remove background
        if field == "bg_type" and value == "none":
            self._primary_widget.background = None

        # Rebuild form to show/hide dynamic fields
        if field in ("bg_type", "stroke_width", "has_pressed"):
            self._updating = True
            self._rebuild_form()
            self._updating = False

        self.property_changed.emit()

    def _on_designer_flag_changed(self, field, value):
        if self._updating or not self._selection:
            return
        for widget in self._selection:
            setattr(widget, field, bool(value))
        self.property_changed.emit()
