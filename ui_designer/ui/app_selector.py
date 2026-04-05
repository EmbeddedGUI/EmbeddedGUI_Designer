"""SDK example selection dialog for EmbeddedGUI Designer."""

from __future__ import annotations

import os

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
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
    describe_auto_download_plan,
    describe_sdk_source_hint,
    sdk_root_source_kind,
)
from ..model.workspace import (
    describe_sdk_root,
    is_valid_sdk_root,
    normalize_path,
    resolve_configured_sdk_root,
    resolve_sdk_root_candidate,
)
from .iconography import make_icon


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
    """Styled row widget for SDK example entries."""

    def __init__(self, *, title, path_text, kind_text, kind_key="project", parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("app_selector_item_card")
        self.setProperty("selected", "false")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        icon_shell = QFrame()
        icon_shell.setObjectName("app_selector_item_icon_shell")
        icon_shell.setFixedSize(42, 42)
        icon_layout = QVBoxLayout(icon_shell)
        icon_layout.setContentsMargins(0, 0, 0, 0)

        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignCenter)
        icon_name = "nav.page" if kind_key == "legacy" else "nav.page_group"
        icon_label.setPixmap(make_icon(icon_name, size=24).pixmap(24, 24))
        icon_layout.addWidget(icon_label)
        layout.addWidget(icon_shell, 0, Qt.AlignTop)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(5)

        self._title_label = QLabel(title)
        self._title_label.setFont(QFont("Segoe UI", 11, QFont.DemiBold))
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
        summary = f"SDK example row: {title}. {kind_text}. Path: {path_text}."
        _set_widget_metadata(self, tooltip=summary, accessible_name=summary)
        _set_widget_metadata(
            self._title_label,
            tooltip=summary,
            accessible_name=f"SDK example title: {title}",
        )
        _set_widget_metadata(
            self._path_label,
            tooltip=f"SDK example path: {path_text}",
            accessible_name=f"SDK example path: {path_text}",
        )
        _set_widget_metadata(
            self._kind_label,
            tooltip=kind_text,
            accessible_name=f"SDK example kind: {kind_text}",
        )

    def set_selected(self, selected):
        self.setProperty("selected", "true" if selected else "false")
        style = self.style()
        style.unpolish(self)
        style.polish(self)
        self.update()


class AppSelectorDialog(QDialog):
    """Dialog for opening Designer-aware or legacy SDK examples."""

    def __init__(self, parent=None, egui_root=None, on_download_sdk=None):
        super().__init__(parent)
        self.setWindowTitle("Open SDK Example")
        self.setMinimumSize(860, 620)
        self.resize(980, 680)

        self._config = get_config()
        self._egui_root = resolve_configured_sdk_root(
            egui_root,
            self._config.sdk_root,
            self._config.egui_root,
            cached_sdk_root=default_sdk_install_dir(),
            preserve_invalid=True,
        )
        self._selected_entry = None
        self._on_download_sdk = on_download_sdk
        self._visible_entry_count = 0

        self._init_ui()
        self._refresh_app_list()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        self._header_frame = QFrame()
        self._header_frame.setObjectName("app_selector_header")
        header_layout = QHBoxLayout(self._header_frame)
        header_layout.setContentsMargins(24, 22, 24, 22)
        header_layout.setSpacing(24)

        hero_copy = QVBoxLayout()
        hero_copy.setContentsMargins(0, 0, 0, 0)
        hero_copy.setSpacing(6)

        self._eyebrow_label = QLabel("Example Browser")
        self._eyebrow_label.setObjectName("app_selector_eyebrow")
        _set_widget_metadata(
            self._eyebrow_label,
            tooltip="SDK example browser workspace.",
            accessible_name="SDK example browser workspace.",
        )
        hero_copy.addWidget(self._eyebrow_label, 0, Qt.AlignLeft)

        self._title_label = QLabel("Open EmbeddedGUI SDK Example")
        self._title_label.setFont(QFont("Segoe UI", 26, QFont.Light))
        self._title_label.setObjectName("app_selector_title")
        _set_widget_metadata(
            self._title_label,
            tooltip="SDK example browser title: Open EmbeddedGUI SDK Example.",
            accessible_name="SDK example browser title: Open EmbeddedGUI SDK Example.",
        )
        hero_copy.addWidget(self._title_label)

        self._subtitle_label = QLabel(
            "Attach a valid SDK workspace, filter available examples, and choose between opening Designer projects or importing legacy apps."
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

        metrics_layout = QVBoxLayout()
        metrics_layout.setContentsMargins(0, 0, 0, 0)
        metrics_layout.setSpacing(8)
        self._root_metric_value = self._create_header_metric(metrics_layout, "SDK Status")
        self._results_metric_value = self._create_header_metric(metrics_layout, "Visible Examples")
        self._selection_metric_value = self._create_header_metric(metrics_layout, "Action")
        header_layout.addLayout(metrics_layout, 2)
        layout.addWidget(self._header_frame)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(16)

        left_column = QVBoxLayout()
        left_column.setContentsMargins(0, 0, 0, 0)
        left_column.setSpacing(16)

        root_card = QFrame()
        root_card.setObjectName("app_selector_root_card")
        root_layout = QVBoxLayout(root_card)
        root_layout.setContentsMargins(22, 22, 22, 22)
        root_layout.setSpacing(12)

        root_title = QLabel("SDK Binding")
        root_title.setObjectName("workspace_section_title")
        root_layout.addWidget(root_title)

        root_hint = QLabel("Examples come from the current SDK workspace. Switch roots here when you need a different application catalog.")
        root_hint.setObjectName("workspace_section_subtitle")
        root_hint.setWordWrap(True)
        root_layout.addWidget(root_hint)
        root_hint.hide()

        root_label = QLabel("SDK Root")
        root_label.setObjectName("app_selector_field_label")
        root_layout.addWidget(root_label)

        self._root_edit = LineEdit()
        self._root_edit.setText(self._egui_root)
        self._root_edit.setReadOnly(True)
        root_layout.addWidget(self._root_edit)

        actions_row = QHBoxLayout()
        actions_row.setSpacing(10)

        self._browse_btn = PushButton("Browse...")
        self._browse_btn.setIcon(make_icon("toolbar.open"))
        self._browse_btn.clicked.connect(self._browse_root)
        _set_widget_metadata(
            self._browse_btn,
            tooltip="Browse to an EmbeddedGUI SDK root.",
            accessible_name="Browse SDK root",
        )
        actions_row.addWidget(self._browse_btn)

        self._download_btn = PushButton("Download SDK...")
        self._download_btn.setIcon(make_icon("toolbar.compile"))
        self._download_btn.clicked.connect(self._download_sdk)
        _set_widget_metadata(
            self._download_btn,
            tooltip=describe_auto_download_plan(),
            accessible_name="Download SDK",
        )
        actions_row.addWidget(self._download_btn)
        root_layout.addLayout(actions_row)

        self._root_status_label = QLabel("")
        self._root_status_label.setObjectName("app_selector_status_value")
        self._root_status_label.setWordWrap(True)
        root_layout.addWidget(self._root_status_label)
        left_column.addWidget(root_card)

        options_card = QFrame()
        options_card.setObjectName("app_selector_options_card")
        options_layout = QVBoxLayout(options_card)
        options_layout.setContentsMargins(22, 22, 22, 22)
        options_layout.setSpacing(12)

        options_title = QLabel("Catalog Filters")
        options_title.setObjectName("workspace_section_title")
        options_layout.addWidget(options_title)

        options_hint = QLabel("Keep the browser focused on Designer-ready projects, or widen the list to include legacy apps that still need import.")
        options_hint.setObjectName("workspace_section_subtitle")
        options_hint.setWordWrap(True)
        options_layout.addWidget(options_hint)
        options_hint.hide()

        self._show_legacy = QCheckBox("Show legacy examples without .egui")
        self._show_legacy.setChecked(self._config.show_all_examples)
        self._show_legacy.toggled.connect(self._on_toggle_legacy)
        _set_widget_metadata(
            self._show_legacy,
            tooltip="Include legacy SDK examples that do not yet have Designer project files.",
            accessible_name="Show legacy SDK examples",
        )
        options_layout.addWidget(self._show_legacy)
        options_layout.addStretch(1)
        left_column.addWidget(options_card)
        left_column.addStretch(1)
        content_layout.addLayout(left_column, 3)

        right_column = QVBoxLayout()
        right_column.setContentsMargins(0, 0, 0, 0)
        right_column.setSpacing(16)

        browser_card = QFrame()
        browser_card.setObjectName("app_selector_browser_card")
        browser_layout = QVBoxLayout(browser_card)
        browser_layout.setContentsMargins(22, 22, 22, 22)
        browser_layout.setSpacing(12)

        browser_title = QLabel("SDK Examples")
        browser_title.setObjectName("workspace_section_title")
        browser_layout.addWidget(browser_title)

        browser_hint = QLabel("Search by app name and use the list below as the single entry point into existing SDK projects.")
        browser_hint.setObjectName("workspace_section_subtitle")
        browser_hint.setWordWrap(True)
        browser_layout.addWidget(browser_hint)
        browser_hint.hide()

        self._search_edit = LineEdit()
        self._search_edit.setPlaceholderText("Filter examples by name...")
        self._search_edit.textChanged.connect(self._refresh_app_list)
        self._search_edit.setAccessibleName("SDK example search")
        browser_layout.addWidget(self._search_edit)

        self._app_list = QListWidget()
        self._app_list.setObjectName("app_selector_list")
        self._app_list.setSpacing(8)
        self._app_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._app_list.currentItemChanged.connect(self._on_selection_changed)
        self._app_list.setAccessibleName("SDK examples")
        browser_layout.addWidget(self._app_list, 1)
        right_column.addWidget(browser_card, 1)

        selection_card = QFrame()
        selection_card.setObjectName("app_selector_selection_card")
        selection_layout = QVBoxLayout(selection_card)
        selection_layout.setContentsMargins(22, 22, 22, 22)
        selection_layout.setSpacing(10)

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
        self._open_btn.setAccessibleName("Open selected SDK example")
        buttons.addWidget(self._open_btn)
        layout.addLayout(buttons)

        self._root_edit.setAccessibleName("EmbeddedGUI SDK root")
        self._root_status_label.setAccessibleName("SDK root status")
        self._selection_hint_label.setAccessibleName("SDK example selection hint")
        self._update_accessibility_summary()

    def _create_header_metric(self, layout, label_text):
        card = QFrame()
        card.setObjectName("app_selector_metric_card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 12, 14, 12)
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
        kind_key = "legacy" if entry["is_legacy"] else "project"
        kind_text = "Legacy Import" if entry["is_legacy"] else "Designer Project"
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
        path = QFileDialog.getExistingDirectory(self, "Select EmbeddedGUI SDK Root", self._egui_root or "")
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
        self._egui_root = path
        self._root_edit.setText(path)
        self._refresh_app_list()

    def _download_sdk(self):
        if self._on_download_sdk is None:
            QMessageBox.warning(
                self,
                "Download Unavailable",
                "This dialog was opened without an SDK download handler.",
            )
            return

        path = self._on_download_sdk()
        path = resolve_sdk_root_candidate(path) or normalize_path(path)
        if not path:
            return

        self._egui_root = path
        self._root_edit.setText(path)
        self._refresh_app_list()

    def _on_toggle_legacy(self, checked):
        self._config.show_all_examples = checked
        self._config.save()
        self._refresh_app_list()

    def _add_placeholder_item(self, text, *, tooltip, accessible_text):
        item = QListWidgetItem(text)
        item.setFlags(Qt.NoItemFlags)
        _set_item_metadata(item, tooltip=tooltip, accessible_text=accessible_text)
        self._app_list.addItem(item)

    def _refresh_app_list(self):
        previous_app = self._selected_entry.get("app_name", "") if self._selected_entry else ""

        self._app_list.clear()
        self._visible_entry_count = 0
        self._set_selection_feedback(None)
        self._refresh_root_status()

        if not self._egui_root:
            self._add_placeholder_item(
                "(Set or download an SDK root first)",
                tooltip="Set or download an SDK root first.",
                accessible_text="SDK examples list item: Set or download an SDK root first.",
            )
            self._sync_item_card_states()
            self._update_accessibility_summary()
            return

        if not is_valid_sdk_root(self._egui_root):
            self._add_placeholder_item(
                "(Current SDK root is invalid)",
                tooltip="Current SDK root is invalid.",
                accessible_text="SDK examples list item: Current SDK root is invalid.",
            )
            self._sync_item_card_states()
            self._update_accessibility_summary()
            return

        search_text = self._search_edit.text().strip().lower()
        entries = self._config.list_available_app_entries(
            sdk_root=self._egui_root,
            include_legacy=self._show_legacy.isChecked(),
        )
        for entry in entries:
            if search_text and search_text not in entry["app_name"].lower():
                continue
            label = entry["app_name"]
            if entry["is_legacy"]:
                label += " [Legacy]"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, entry)
            if entry["has_project"]:
                _set_item_metadata(
                    item,
                    tooltip=entry["project_path"],
                    accessible_text=f"SDK example: {label}. Project path: {entry['project_path']}",
                )
            else:
                _set_item_metadata(
                    item,
                    tooltip=f"{entry['app_dir']}\nLegacy example without .egui. Opening it will initialize a Designer project.",
                    accessible_text=(
                        f"SDK example: {label}. Legacy example path: {entry['app_dir']}. "
                        "Opening it will initialize a Designer project."
                    ),
                )
            self._app_list.addItem(item)
            item_widget = self._create_entry_row(entry, label)
            item.setSizeHint(item_widget.sizeHint())
            self._app_list.setItemWidget(item, item_widget)
            self._visible_entry_count += 1

        if self._visible_entry_count == 0:
            placeholder_text = "(No matching examples)" if search_text else "(No SDK examples found)"
            self._add_placeholder_item(
                placeholder_text,
                tooltip=placeholder_text,
                accessible_text=f"SDK examples list item: {placeholder_text}",
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
        status = describe_sdk_root(self._egui_root)
        if status == "ready":
            source_kind = sdk_root_source_kind(self._egui_root)
            if source_kind == "bundled":
                self._root_status_label.setText("Ready: using bundled SDK examples below.")
            elif source_kind == "runtime_local":
                self._root_status_label.setText("Ready: using SDK stored beside the application.")
            elif source_kind == "cached":
                self._root_status_label.setText("Ready: using auto-downloaded SDK cache.")
            else:
                self._root_status_label.setText("Ready: using selected SDK root.")
            self._root_status_label.setText(
                f"{self._root_status_label.text()}\n{describe_sdk_source_hint(self._egui_root)}"
            )
            _set_label_hint_tone(self._root_status_label, "success")
            return

        if status == "invalid":
            self._root_status_label.setText(
                "Invalid: current SDK root needs attention. Browse to a valid SDK root or download a fresh copy.\n"
                f"{describe_auto_download_plan()}"
            )
            _set_label_hint_tone(self._root_status_label, "warning")
            return

        self._root_status_label.setText(
            "Missing: no SDK root selected. Browse to an existing SDK or download one now.\n"
            f"{describe_auto_download_plan()}"
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
                "Select a Designer project or a legacy example from the list."
            )
            _set_label_hint_tone(self._selection_hint_label, "muted")
            self._update_accessibility_summary()
            return

        if entry.get("is_legacy"):
            self._open_btn.setText("Import Legacy Example")
            self._selection_hint_label.setText(
                f"Legacy example path:\n{entry.get('app_dir', '')}\n\n"
                "Opening it will initialize a Designer project in this app directory."
            )
            _set_label_hint_tone(self._selection_hint_label, "warning")
            self._update_accessibility_summary()
            return

        self._open_btn.setText("Open")
        self._selection_hint_label.setText(
            f"Designer project path:\n{entry.get('project_path', '')}"
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
        if self._selected_entry.get("is_legacy"):
            return "Import legacy example"
        return "Open Designer project"

    def _update_accessibility_summary(self):
        root_value = self._egui_root or "none"
        root_status = self._root_status_label.text().strip() or "SDK root status unavailable."
        root_status_summary = root_status.splitlines()[0]
        search_text = self._search_edit.text().strip() or "none"
        selection_name = self._selected_entry.get("app_name", "none") if self._selected_entry else "none"
        list_count = self._app_list.count()
        list_text = "1 entry" if list_count == 1 else f"{list_count} entries"
        legacy_text = "on" if self._show_legacy.isChecked() else "off"

        self._root_metric_value.setText(root_status_summary)
        self._results_metric_value.setText(self._visible_examples_summary())
        self._selection_metric_value.setText(self._selection_action_summary())

        summary = (
            f"Open SDK Example dialog: SDK root {root_value}. Search {search_text}. "
            f"Legacy examples {legacy_text}. Examples list: {list_text}. Selection: {selection_name}."
        )
        _set_widget_metadata(self, tooltip=summary, accessible_name=summary)
        _set_widget_metadata(
            self._header_frame,
            tooltip=f"SDK example header. {summary}",
            accessible_name=f"SDK example header. {summary}",
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
            tooltip=f"Filter SDK examples by name. Current search: {search_text}.",
            accessible_name=f"SDK example search: {search_text}",
        )
        _set_widget_metadata(
            self._app_list,
            tooltip=f"SDK examples list: {list_text}. Current selection: {selection_name}.",
            accessible_name=f"SDK examples list: {list_text}. Current selection: {selection_name}.",
        )
        _set_widget_metadata(
            self._selection_hint_label,
            tooltip=self._selection_hint_label.text(),
            accessible_name=f"Selection hint: {self._selection_hint_label.text()}",
        )
        self._update_header_metric_metadata(self._root_metric_value)
        self._update_header_metric_metadata(self._results_metric_value)
        self._update_header_metric_metadata(self._selection_metric_value)
        legacy_hint = (
            "Showing legacy SDK examples that do not yet have Designer project files."
            if self._show_legacy.isChecked()
            else "Include legacy SDK examples that do not yet have Designer project files."
        )
        _set_widget_metadata(
            self._show_legacy,
            tooltip=legacy_hint,
            accessible_name=f"Show legacy SDK examples: {'on' if self._show_legacy.isChecked() else 'off'}",
        )
        download_hint = describe_auto_download_plan()
        download_name = "Download SDK"
        if self._on_download_sdk is None:
            download_hint = "Download SDK unavailable because this dialog was opened without an SDK download handler."
            download_name = "Download SDK unavailable"
        _set_widget_metadata(
            self._download_btn,
            tooltip=download_hint,
            accessible_name=f"{download_name}. {download_hint}",
        )
        if not self._selected_entry:
            open_hint = "Select an SDK example to open it."
        elif self._selected_entry.get("is_legacy"):
            open_hint = "Import the selected legacy example into a Designer project."
        else:
            open_hint = "Open the selected Designer project."
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
    def egui_root(self):
        return self._egui_root
