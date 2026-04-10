"""Example selection dialog for EmbeddedGUI Designer."""

from __future__ import annotations

import os

from PyQt5.QtCore import Qt
from PyQt5.QtCore import QSize
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from qfluentwidgets import LineEdit, PrimaryPushButton, PushButton

from ..model.config import get_config
from ..model.sdk_bootstrap import (
    default_sdk_install_dir,
    describe_sdk_source_hint,
    sdk_root_source_kind,
)
from ..model.workspace import (
    describe_sdk_root,
    is_valid_sdk_root,
    list_designer_example_entries,
    normalize_path,
    resolve_configured_sdk_root,
    resolve_sdk_root_candidate,
)
def _set_widget_metadata(widget, *, tooltip=None, accessible_name=None):
    if tooltip is not None:
        hint = str(tooltip or "")
        if str(widget.property("_app_selector_hint_snapshot") or "") != hint:
            widget.setToolTip(hint)
            widget.setStatusTip(hint)
            widget.setProperty("_app_selector_hint_snapshot", hint)
    if accessible_name is not None:
        name = str(accessible_name or "")
        if str(widget.property("_app_selector_accessible_snapshot") or "") != name:
            widget.setAccessibleName(name)
            widget.setProperty("_app_selector_accessible_snapshot", name)


def _set_label_hint_tone(widget, tone):
    """Theme-driven hint colors via QSS property ``hintTone``."""
    widget.setProperty("hintTone", tone or "")
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)


def _set_item_metadata(item, *, tooltip=None, accessible_text=None):
    if tooltip is not None:
        item.setToolTip(tooltip)
        item.setStatusTip(tooltip)
    description = accessible_text if accessible_text is not None else (tooltip or item.text())
    item.setData(Qt.AccessibleTextRole, description)


def _condense_path(path, *, tail_segments=4):
    normalized = normalize_path(path)
    if not normalized:
        return ""

    drive, tail = os.path.splitdrive(normalized)
    parts = [part for part in tail.replace("/", os.sep).split(os.sep) if part]
    if len(parts) <= tail_segments:
        return normalized

    if drive:
        prefix = f"{drive}{os.sep}..."
    elif normalized.startswith(os.sep):
        prefix = f"{os.sep}..."
    else:
        prefix = "..."
    return f"{prefix}{os.sep}{os.sep.join(parts[-tail_segments:])}"


class AppEntryRowWidget(QWidget):
    """Styled row widget for example entries."""

    def __init__(self, *, title, path_text, kind_text, kind_key="project", parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("app_selector_item_card")
        self.setProperty("selected", "false")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(4)

        self._title_label = QLabel(title)
        self._title_label.setObjectName("app_selector_item_title")
        text_layout.addWidget(self._title_label)

        self._path_label = QLabel(path_text)
        self._path_label.setObjectName("app_selector_item_meta")
        self._path_label.setWordWrap(True)
        text_layout.addWidget(self._path_label)
        self._path_label.hide()

        self._kind_label = QLabel(kind_text)
        self._kind_label.setObjectName("app_selector_item_kind")
        self._kind_label.setProperty("entryKind", kind_key)
        text_layout.addWidget(self._kind_label, 0, Qt.AlignLeft)
        self._kind_label.hide()

        layout.addLayout(text_layout, 1)
        summary = f"Example row: {title}. {kind_text}. Path: {path_text}."
        _set_widget_metadata(self, tooltip=summary, accessible_name=summary)
        _set_widget_metadata(
            self._title_label,
            tooltip=summary,
            accessible_name=f"Example title: {title}",
        )
        _set_widget_metadata(
            self._path_label,
            tooltip=f"Example path: {path_text}",
            accessible_name=f"Example path: {path_text}",
        )
        _set_widget_metadata(
            self._kind_label,
            tooltip=kind_text,
            accessible_name=f"Example kind: {kind_text}",
        )

    def sizeHint(self):
        size = super().sizeHint()
        return QSize(size.width(), max(size.height(), 28))

    def set_selected(self, selected):
        self.setProperty("selected", "true" if selected else "false")
        style = self.style()
        style.unpolish(self)
        style.polish(self)
        self.update()


class AppSelectorDialog(QDialog):
    """Dialog for opening bundled, Designer-aware, or unmanaged SDK examples."""

    def __init__(self, parent=None, sdk_root=None):
        super().__init__(parent)
        self.setWindowTitle("Open Example")
        self.setMinimumSize(860, 620)
        self.resize(980, 680)

        self._config = get_config()
        self._sdk_root = resolve_configured_sdk_root(
            sdk_root,
            self._config.sdk_root,
            cached_sdk_root=default_sdk_install_dir(),
            preserve_invalid=True,
        )
        self._selected_entry = None
        self._visible_entry_count = 0

        self._init_ui()
        self._refresh_app_list()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        self._header_frame = QFrame()
        self._header_frame.setObjectName("app_selector_header")
        header_layout = QHBoxLayout(self._header_frame)
        header_layout.setContentsMargins(16, 14, 16, 14)
        header_layout.setSpacing(16)

        hero_copy = QVBoxLayout()
        hero_copy.setContentsMargins(0, 0, 0, 0)
        hero_copy.setSpacing(4)

        self._eyebrow_label = QLabel("Example Browser")
        self._eyebrow_label.setObjectName("app_selector_eyebrow")
        _set_widget_metadata(
            self._eyebrow_label,
            tooltip="Example browser workspace.",
            accessible_name="Example browser workspace.",
        )
        hero_copy.addWidget(self._eyebrow_label, 0, Qt.AlignLeft)

        self._title_label = QLabel("Open Example")
        self._title_label.setObjectName("app_selector_title")
        _set_widget_metadata(
            self._title_label,
            tooltip="Example browser title: Open EmbeddedGUI Example.",
            accessible_name="Example browser title: Open EmbeddedGUI Example.",
        )
        hero_copy.addWidget(self._title_label)

        self._subtitle_label = QLabel(
            "Browse bundled Designer examples, or attach a valid SDK workspace to open Designer projects and initialize unmanaged SDK examples."
        )
        self._subtitle_label.setObjectName("app_selector_subtitle")
        self._subtitle_label.setWordWrap(True)
        _set_widget_metadata(
            self._subtitle_label,
            tooltip=self._subtitle_label.text(),
            accessible_name=self._subtitle_label.text(),
        )
        hero_copy.addWidget(self._subtitle_label)
        self._eyebrow_label.hide()
        self._subtitle_label.hide()
        hero_copy.addStretch(1)
        header_layout.addLayout(hero_copy, 3)

        self._metrics_frame = QFrame()
        self._metrics_frame.setObjectName("app_selector_metrics_frame")
        metrics_layout = QVBoxLayout(self._metrics_frame)
        metrics_layout.setContentsMargins(0, 0, 0, 0)
        metrics_layout.setSpacing(6)
        self._root_metric_value = self._create_header_metric(metrics_layout, "SDK Status")
        self._results_metric_value = self._create_header_metric(metrics_layout, "Visible Examples")
        self._selection_metric_value = self._create_header_metric(metrics_layout, "Action")
        header_layout.addWidget(self._metrics_frame, 2)
        layout.addWidget(self._header_frame)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(12)

        left_column = QVBoxLayout()
        left_column.setContentsMargins(0, 0, 0, 0)
        left_column.setSpacing(12)

        root_card = QFrame()
        root_card.setObjectName("app_selector_root_card")
        root_layout = QVBoxLayout(root_card)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(10)

        root_title = QLabel("SDK")
        root_title.setObjectName("workspace_section_title")
        root_layout.addWidget(root_title)

        root_hint = QLabel("Bundled examples live beside the Designer. SDK examples come from the current SDK workspace when a root is available.")
        root_hint.setObjectName("workspace_section_subtitle")
        root_hint.setWordWrap(True)
        root_layout.addWidget(root_hint)
        root_hint.hide()

        root_label = QLabel("Root")
        root_label.setObjectName("app_selector_field_label")
        root_layout.addWidget(root_label)

        self._root_edit = LineEdit()
        self._root_edit.setText(self._sdk_root)
        self._root_edit.setReadOnly(True)
        root_layout.addWidget(self._root_edit)

        actions_row = QHBoxLayout()
        actions_row.setSpacing(8)

        self._browse_btn = PushButton("Browse...")
        self._browse_btn.clicked.connect(self._browse_root)
        _set_widget_metadata(
            self._browse_btn,
            tooltip="Browse to an EmbeddedGUI SDK root.",
            accessible_name="Browse SDK root",
        )
        actions_row.addWidget(self._browse_btn)
        root_layout.addLayout(actions_row)

        self._root_status_label = QLabel("")
        self._root_status_label.setObjectName("app_selector_status_value")
        self._root_status_label.setWordWrap(True)
        root_layout.addWidget(self._root_status_label)
        left_column.addWidget(root_card)

        options_card = QFrame()
        options_card.setObjectName("app_selector_options_card")
        options_layout = QVBoxLayout(options_card)
        options_layout.setContentsMargins(0, 0, 0, 0)
        options_layout.setSpacing(10)

        options_title = QLabel("Filters")
        options_title.setObjectName("workspace_section_title")
        options_layout.addWidget(options_title)

        options_hint = QLabel(
            "Keep the browser focused on ready-to-open projects, or widen the SDK section to include "
            "unmanaged SDK examples that still need Designer initialization."
        )
        options_hint.setObjectName("workspace_section_subtitle")
        options_hint.setWordWrap(True)
        options_layout.addWidget(options_hint)
        options_hint.hide()

        self._show_unmanaged = QCheckBox("Show unmanaged")
        self._show_unmanaged.setChecked(self._config.show_all_examples)
        self._show_unmanaged.toggled.connect(self._on_toggle_unmanaged)
        _set_widget_metadata(
            self._show_unmanaged,
            tooltip="Include SDK examples that do not yet have Designer project files.",
            accessible_name="Show unmanaged SDK examples",
        )
        options_layout.addWidget(self._show_unmanaged)
        options_layout.addStretch(1)
        left_column.addWidget(options_card)
        left_column.addStretch(1)
        content_layout.addLayout(left_column, 3)

        right_column = QVBoxLayout()
        right_column.setContentsMargins(0, 0, 0, 0)
        right_column.setSpacing(12)

        browser_card = QFrame()
        browser_card.setObjectName("app_selector_browser_card")
        browser_layout = QVBoxLayout(browser_card)
        browser_layout.setContentsMargins(0, 0, 0, 0)
        browser_layout.setSpacing(10)

        browser_title = QLabel("Examples")
        browser_title.setObjectName("workspace_section_title")
        browser_layout.addWidget(browser_title)

        browser_hint = QLabel("Search by app name and use the list below as the single entry point into bundled examples and existing SDK projects.")
        browser_hint.setObjectName("workspace_section_subtitle")
        browser_hint.setWordWrap(True)
        browser_layout.addWidget(browser_hint)
        browser_hint.hide()

        self._search_edit = LineEdit()
        self._search_edit.setPlaceholderText("Search examples...")
        self._search_edit.textChanged.connect(self._refresh_app_list)
        self._search_edit.setAccessibleName("Example search")
        browser_layout.addWidget(self._search_edit)

        self._app_list = QListWidget()
        self._app_list.setObjectName("app_selector_list")
        self._app_list.setSpacing(8)
        self._app_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._app_list.currentItemChanged.connect(self._on_selection_changed)
        self._app_list.setAccessibleName("Examples")
        browser_layout.addWidget(self._app_list, 1)
        right_column.addWidget(browser_card, 1)

        selection_card = QFrame()
        selection_card.setObjectName("app_selector_selection_card")
        selection_layout = QVBoxLayout(selection_card)
        selection_layout.setContentsMargins(0, 0, 0, 0)
        selection_layout.setSpacing(8)

        selection_title = QLabel("Selection")
        selection_title.setObjectName("workspace_section_title")
        selection_layout.addWidget(selection_title)

        selection_hint = QLabel("Review the selected example path and import mode before opening it in the workspace.")
        selection_hint.setObjectName("workspace_section_subtitle")
        selection_hint.setWordWrap(True)
        selection_layout.addWidget(selection_hint)
        selection_hint.hide()

        self._selection_hint_label = QLabel("")
        self._selection_hint_label.setObjectName("app_selector_selection_value")
        self._selection_hint_label.setWordWrap(True)
        selection_layout.addWidget(self._selection_hint_label)
        right_column.addWidget(selection_card)
        content_layout.addLayout(right_column, 5)

        layout.addLayout(content_layout, 1)

        buttons = QHBoxLayout()
        buttons.addStretch()

        self._cancel_btn = PushButton("Cancel")
        self._cancel_btn.clicked.connect(self.reject)
        _set_widget_metadata(
            self._cancel_btn,
            tooltip="Close this dialog without opening an example.",
            accessible_name="Cancel",
        )
        buttons.addWidget(self._cancel_btn)

        self._open_btn = PrimaryPushButton("Open")
        self._open_btn.clicked.connect(self._on_open)
        self._open_btn.setEnabled(False)
        self._open_btn.setAccessibleName("Open selected example")
        buttons.addWidget(self._open_btn)
        layout.addLayout(buttons)

        self._root_edit.setAccessibleName("EmbeddedGUI SDK root")
        self._root_status_label.setAccessibleName("SDK root status")
        self._selection_hint_label.setAccessibleName("Example selection hint")
        self._metrics_frame.hide()
        self._update_accessibility_summary()

    def _create_header_metric(self, layout, label_text):
        card = QFrame()
        card.setObjectName("app_selector_metric_card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(4)

        label = QLabel(label_text)
        label.setObjectName("app_selector_metric_label")
        card_layout.addWidget(label)

        value = QLabel("")
        value.setObjectName("app_selector_metric_value")
        value.setWordWrap(True)
        card_layout.addWidget(value)

        value._app_selector_metric_name = label_text
        value._app_selector_metric_label = label
        value._app_selector_metric_card = card
        _set_widget_metadata(
            label,
            tooltip=f"{label_text} metric label.",
            accessible_name=f"{label_text} metric label.",
        )
        layout.addWidget(card)
        return value

    def _update_header_metric_metadata(self, metric_value):
        metric_name = getattr(metric_value, "_app_selector_metric_name", "SDK")
        metric_text = (metric_value.text() or "none").strip() or "none"
        summary = f"{metric_name}: {metric_text}."

        _set_widget_metadata(
            metric_value,
            tooltip=summary,
            accessible_name=f"App selector metric: {metric_name}. {metric_text}.",
        )

        label = getattr(metric_value, "_app_selector_metric_label", None)
        if label is not None:
            _set_widget_metadata(
                label,
                tooltip=summary,
                accessible_name=f"{metric_name} metric label.",
            )

        card = getattr(metric_value, "_app_selector_metric_card", None)
        if card is not None:
            _set_widget_metadata(
                card,
                tooltip=summary,
                accessible_name=f"{metric_name} metric: {metric_text}.",
            )

    def _create_entry_row(self, entry, label):
        path_text = entry["project_path"] if entry["has_project"] else entry["app_dir"]
        if entry.get("source") == "designer":
            kind_key = "designer"
            kind_text = "Designer Example"
        elif entry["is_unmanaged"]:
            kind_key = "unmanaged"
            kind_text = "Needs Initialization"
        else:
            kind_key = "project"
            kind_text = "SDK Project"
        return AppEntryRowWidget(
            title=label,
            path_text=_condense_path(path_text, tail_segments=5),
            kind_text=kind_text,
            kind_key=kind_key,
        )

    def _sync_item_card_states(self):
        current_item = self._app_list.currentItem()
        for index in range(self._app_list.count()):
            item = self._app_list.item(index)
            widget = self._app_list.itemWidget(item)
            if widget is not None and hasattr(widget, "set_selected"):
                widget.set_selected(item is current_item)

    def _browse_root(self):
        path = QFileDialog.getExistingDirectory(self, "Select EmbeddedGUI SDK Root", self._sdk_root or "")
        if not path:
            return
        path = resolve_sdk_root_candidate(path)
        if not path:
            QMessageBox.warning(
                self,
                "Invalid SDK Root",
                "This directory does not appear to contain a valid EmbeddedGUI SDK root.",
            )
            return
        self._sdk_root = path
        self._root_edit.setText(path)
        self._refresh_app_list()

    def _on_toggle_unmanaged(self, checked):
        self._config.show_all_examples = checked
        self._config.save()
        self._refresh_app_list()

    def _add_placeholder_item(self, text, *, tooltip, accessible_text):
        item = QListWidgetItem(text)
        item.setFlags(Qt.NoItemFlags)
        _set_item_metadata(item, tooltip=tooltip, accessible_text=accessible_text)
        self._app_list.addItem(item)

    def _clear_app_list_items(self):
        while self._app_list.count():
            item = self._app_list.item(0)
            widget = self._app_list.itemWidget(item)
            if widget is not None:
                self._app_list.removeItemWidget(item)
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
            item = self._app_list.takeItem(0)
            del item

    def _refresh_app_list(self):
        previous_app = self._selected_entry.get("app_name", "") if self._selected_entry else ""

        self._clear_app_list_items()
        self._visible_entry_count = 0
        self._set_selection_feedback(None)
        self._refresh_root_status()

        bundled_entries = list_designer_example_entries()
        has_valid_sdk = bool(self._sdk_root and is_valid_sdk_root(self._sdk_root))

        if not bundled_entries and not self._sdk_root:
            self._add_placeholder_item(
                "(Set an SDK root first)",
                tooltip="Set an SDK root first.",
                accessible_text="Examples list item: Set an SDK root first.",
            )
            self._sync_item_card_states()
            self._update_accessibility_summary()
            return

        if not bundled_entries and self._sdk_root and not has_valid_sdk:
            self._add_placeholder_item(
                "(Current SDK root is invalid)",
                tooltip="Current SDK root is invalid.",
                accessible_text="Examples list item: Current SDK root is invalid.",
            )
            self._sync_item_card_states()
            self._update_accessibility_summary()
            return

        search_text = self._search_edit.text().strip().lower()
        entries = list(bundled_entries)
        if has_valid_sdk:
            entries.extend(
                self._config.list_available_app_entries(
                    sdk_root=self._sdk_root,
                    include_unmanaged=self._show_unmanaged.isChecked(),
                )
            )
        for entry in entries:
            if search_text and search_text not in entry["app_name"].lower():
                continue
            label = entry["app_name"]
            if entry["is_unmanaged"]:
                label += " [Unmanaged]"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, entry)
            if entry["has_project"]:
                _set_item_metadata(
                    item,
                    tooltip=entry["project_path"],
                    accessible_text=f"Example: {label}. Project path: {entry['project_path']}",
                )
            else:
                _set_item_metadata(
                    item,
                    tooltip=(
                        f"{entry['app_dir']}\n"
                        "SDK example without .egui. Opening it will initialize a Designer project."
                    ),
                    accessible_text=(
                        f"Example: {label}. SDK example path: {entry['app_dir']}. "
                        "Opening it will initialize a Designer project."
                    ),
                )
            self._app_list.addItem(item)
            item.setForeground(QColor(0, 0, 0, 0))
            item_widget = self._create_entry_row(entry, label)
            item.setSizeHint(item_widget.sizeHint())
            self._app_list.setItemWidget(item, item_widget)
            self._visible_entry_count += 1

        if self._visible_entry_count == 0:
            placeholder_text = "(No matching examples)" if search_text else "(No examples found)"
            self._add_placeholder_item(
                placeholder_text,
                tooltip=placeholder_text,
                accessible_text=f"Examples list item: {placeholder_text}",
            )
            self._sync_item_card_states()
            self._update_accessibility_summary()
            return

        preferred_app = previous_app or self._config.last_app
        for index in range(self._app_list.count()):
            item = self._app_list.item(index)
            entry = item.data(Qt.UserRole) or {}
            if entry.get("app_name") == preferred_app:
                self._app_list.setCurrentRow(index)
                break
        else:
            self._app_list.setCurrentRow(0)

        self._sync_item_card_states()
        self._update_accessibility_summary()

    def _refresh_root_status(self):
        status = describe_sdk_root(self._sdk_root)
        if status == "ready":
            source_kind = sdk_root_source_kind(self._sdk_root)
            if source_kind == "bundled":
                self._root_status_label.setText("Ready: using bundled SDK workspace.")
            elif source_kind == "runtime_local":
                self._root_status_label.setText("Ready: using SDK stored beside the application.")
            elif source_kind == "cached":
                self._root_status_label.setText("Ready: using default SDK cache.")
            else:
                self._root_status_label.setText("Ready: using selected SDK root.")
            self._root_status_label.setText(
                f"{self._root_status_label.text()}\n{describe_sdk_source_hint(self._sdk_root)}"
            )
            _set_label_hint_tone(self._root_status_label, "success")
            return

        if status == "invalid":
            self._root_status_label.setText(
                "Invalid: current SDK root needs attention. Bundled Designer examples remain available below."
            )
            _set_label_hint_tone(self._root_status_label, "warning")
            return

        self._root_status_label.setText(
            "Missing: no SDK root selected. Bundled Designer examples remain available below."
        )
        _set_label_hint_tone(self._root_status_label, "danger")

    def _on_selection_changed(self, current, previous):
        del previous
        self._set_selection_feedback(current.data(Qt.UserRole) if current else None)
        self._sync_item_card_states()

    def _on_item_double_clicked(self, item):
        entry = item.data(Qt.UserRole)
        if entry is None:
            return
        self._set_selection_feedback(entry)
        self.accept()

    def _on_open(self):
        if self._selected_entry:
            self.accept()

    def _set_selection_feedback(self, entry):
        self._selected_entry = entry
        self._open_btn.setEnabled(entry is not None)
        if not entry:
            self._open_btn.setText("Open")
            self._selection_hint_label.setText(
                "Select an example project or an unmanaged SDK example from the list."
            )
            _set_label_hint_tone(self._selection_hint_label, "muted")
            self._update_accessibility_summary()
            return

        if entry.get("is_unmanaged"):
            self._open_btn.setText("Initialize")
            self._selection_hint_label.setText(
                f"SDK example path:\n{entry.get('app_dir', '')}\n\n"
                "This initializes a fresh Designer project scaffold here. Existing app pages, "
                "resources, and business code are not migrated."
            )
            _set_label_hint_tone(self._selection_hint_label, "warning")
            self._update_accessibility_summary()
            return

        self._open_btn.setText("Open")
        self._selection_hint_label.setText(
            f"Project path:\n{entry.get('project_path', '')}"
        )
        _set_label_hint_tone(self._selection_hint_label, "success")
        self._update_accessibility_summary()

    def _visible_examples_summary(self):
        if self._visible_entry_count == 0:
            return "No examples"
        if self._visible_entry_count == 1:
            return "1 example"
        return f"{self._visible_entry_count} examples"

    def _selection_action_summary(self):
        if not self._selected_entry:
            return "Selection required"
        if self._selected_entry.get("is_unmanaged"):
            return "Initialize Designer project"
        return "Open example project"

    def _update_accessibility_summary(self):
        root_value = self._sdk_root or "none"
        root_status = self._root_status_label.text().strip() or "SDK root status unavailable."
        root_status_summary = root_status.splitlines()[0]
        search_text = self._search_edit.text().strip() or "none"
        selection_name = self._selected_entry.get("app_name", "none") if self._selected_entry else "none"
        list_count = self._app_list.count()
        list_text = "1 entry" if list_count == 1 else f"{list_count} entries"
        unmanaged_text = "on" if self._show_unmanaged.isChecked() else "off"

        self._root_metric_value.setText(root_status_summary)
        self._results_metric_value.setText(self._visible_examples_summary())
        self._selection_metric_value.setText(self._selection_action_summary())

        summary = (
            f"Open Example dialog: SDK root {root_value}. Search {search_text}. "
            f"Unmanaged SDK examples {unmanaged_text}. Examples list: {list_text}. Selection: {selection_name}."
        )
        _set_widget_metadata(self, tooltip=summary, accessible_name=summary)
        _set_widget_metadata(
            self._header_frame,
            tooltip=f"Example header. {summary}",
            accessible_name=f"Example header. {summary}",
        )
        _set_widget_metadata(
            self._root_edit,
            tooltip=f"EmbeddedGUI SDK root: {root_value}",
            accessible_name=f"EmbeddedGUI SDK root: {root_value}",
        )
        _set_widget_metadata(
            self._root_status_label,
            tooltip=root_status,
            accessible_name=f"SDK root status: {root_status}",
        )
        _set_widget_metadata(
            self._search_edit,
            tooltip=f"Filter examples by name. Current search: {search_text}.",
            accessible_name=f"Example search: {search_text}",
        )
        _set_widget_metadata(
            self._app_list,
            tooltip=f"Examples list: {list_text}. Current selection: {selection_name}.",
            accessible_name=f"Examples list: {list_text}. Current selection: {selection_name}.",
        )
        _set_widget_metadata(
            self._selection_hint_label,
            tooltip=self._selection_hint_label.text(),
            accessible_name=f"Selection hint: {self._selection_hint_label.text()}",
        )
        self._update_header_metric_metadata(self._root_metric_value)
        self._update_header_metric_metadata(self._results_metric_value)
        self._update_header_metric_metadata(self._selection_metric_value)
        unmanaged_hint = (
            "Showing SDK examples that do not yet have Designer project files."
            if self._show_unmanaged.isChecked()
            else "Include SDK examples that do not yet have Designer project files."
        )
        _set_widget_metadata(
            self._show_unmanaged,
            tooltip=unmanaged_hint,
            accessible_name=f"Show unmanaged SDK examples: {'on' if self._show_unmanaged.isChecked() else 'off'}",
        )
        if not self._selected_entry:
            open_hint = "Select an example to open it."
        elif self._selected_entry.get("is_unmanaged"):
            open_hint = (
                "Initialize a fresh Designer project scaffold in the selected SDK example directory. "
                "Existing app pages, resources, and business code are not migrated."
            )
        else:
            open_hint = "Open the selected example project."
        _set_widget_metadata(
            self._open_btn,
            tooltip=open_hint,
            accessible_name=(
                f"Open action: {self._open_btn.text()}. {open_hint}"
                if self._selected_entry
                else f"Open action unavailable: {self._open_btn.text()}. {open_hint}"
            ),
        )

    @property
    def selected_entry(self):
        return self._selected_entry

    @property
    def selected_app(self):
        if self._selected_entry:
            return self._selected_entry.get("app_name")
        return None

    @property
    def sdk_root(self):
        return self._sdk_root
