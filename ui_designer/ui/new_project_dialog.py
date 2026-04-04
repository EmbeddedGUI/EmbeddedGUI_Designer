"""Dialog for creating a new standard EmbeddedGUI app project."""

from __future__ import annotations

import os

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QSpinBox,
    QVBoxLayout,
)

from qfluentwidgets import LineEdit, PrimaryPushButton, PushButton

from .iconography import make_icon
from ..model.config import get_config
from ..model.sdk_bootstrap import default_sdk_install_dir
from ..model.workspace import is_valid_sdk_root, normalize_path, resolve_configured_sdk_root, resolve_sdk_root_candidate


def _set_widget_metadata(widget, *, tooltip=None, accessible_name=None):
    if tooltip is not None:
        widget.setToolTip(tooltip)
        widget.setStatusTip(tooltip)
    if accessible_name is not None:
        widget.setAccessibleName(accessible_name)


def _set_label_hint_tone(widget, tone):
    widget.setProperty("hintTone", tone or "")
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)


class NewProjectDialog(QDialog):
    """Collect parameters for a new project."""

    def __init__(self, parent=None, sdk_root="", default_parent_dir=""):
        super().__init__(parent)
        self.setWindowTitle("New Project")
        self.setMinimumSize(760, 520)
        self.resize(840, 560)

        config = get_config()
        self._sdk_root = resolve_configured_sdk_root(
            sdk_root,
            config.sdk_root,
            config.egui_root,
            cached_sdk_root=default_sdk_install_dir(),
            preserve_invalid=True,
        )
        default_parent_dir = normalize_path(default_parent_dir)
        sdk_parent_dir = self._default_parent_dir_for_sdk(self._sdk_root)
        self._parent_dir = default_parent_dir or sdk_parent_dir
        self._parent_dir_auto_managed = not default_parent_dir or default_parent_dir == sdk_parent_dir

        self._init_ui()

    def _default_parent_dir_for_sdk(self, sdk_root):
        sdk_root = normalize_path(sdk_root)
        if not is_valid_sdk_root(sdk_root):
            return ""
        return os.path.join(sdk_root, "example")

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        self._header_frame = QFrame()
        self._header_frame.setObjectName("new_project_header")
        header_layout = QHBoxLayout(self._header_frame)
        header_layout.setContentsMargins(24, 22, 24, 22)
        header_layout.setSpacing(24)

        hero_copy = QVBoxLayout()
        hero_copy.setContentsMargins(0, 0, 0, 0)
        hero_copy.setSpacing(6)

        self._eyebrow_label = QLabel("Project Scaffold")
        self._eyebrow_label.setObjectName("new_project_eyebrow")
        _set_widget_metadata(
            self._eyebrow_label,
            tooltip="New project scaffold workspace.",
            accessible_name="New project scaffold workspace.",
        )
        hero_copy.addWidget(self._eyebrow_label, 0, Qt.AlignLeft)

        self._title_label = QLabel("Create EmbeddedGUI App")
        self._title_label.setFont(QFont("Segoe UI", 26, QFont.Light))
        self._title_label.setObjectName("new_project_title")
        _set_widget_metadata(
            self._title_label,
            tooltip="New project dialog title: Create EmbeddedGUI App.",
            accessible_name="New project dialog title: Create EmbeddedGUI App.",
        )
        hero_copy.addWidget(self._title_label)

        self._subtitle_label = QLabel(
            "Bind an SDK, choose a workspace location, and define the first canvas in one structured flow."
        )
        self._subtitle_label.setObjectName("new_project_subtitle")
        self._subtitle_label.setWordWrap(True)
        _set_widget_metadata(
            self._subtitle_label,
            tooltip=self._subtitle_label.text(),
            accessible_name=self._subtitle_label.text(),
        )
        hero_copy.addWidget(self._subtitle_label)
        hero_copy.addStretch(1)
        header_layout.addLayout(hero_copy, 3)

        metrics_layout = QVBoxLayout()
        metrics_layout.setContentsMargins(0, 0, 0, 0)
        metrics_layout.setSpacing(8)
        self._sdk_metric_value = self._create_header_metric(metrics_layout, "Preview Mode")
        self._location_metric_value = self._create_header_metric(metrics_layout, "Parent Directory")
        self._canvas_metric_value = self._create_header_metric(metrics_layout, "Canvas")
        header_layout.addLayout(metrics_layout, 2)
        layout.addWidget(self._header_frame)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(16)

        workspace_card = QFrame()
        workspace_card.setObjectName("new_project_form_card")
        workspace_layout = QVBoxLayout(workspace_card)
        workspace_layout.setContentsMargins(22, 22, 22, 22)
        workspace_layout.setSpacing(12)

        workspace_title = QLabel("Workspace Binding")
        workspace_title.setObjectName("workspace_section_title")
        workspace_layout.addWidget(workspace_title)

        workspace_hint = QLabel("Attach an SDK if you want compile-backed preview from the first project open.")
        workspace_hint.setObjectName("workspace_section_subtitle")
        workspace_hint.setWordWrap(True)
        workspace_layout.addWidget(workspace_hint)

        sdk_label = QLabel("SDK Root")
        sdk_label.setObjectName("new_project_field_label")
        workspace_layout.addWidget(sdk_label)

        self._sdk_edit = LineEdit()
        self._sdk_edit.setReadOnly(True)
        self._sdk_edit.setText(self._sdk_root)
        sdk_row = QHBoxLayout()
        sdk_row.addWidget(self._sdk_edit, 1)
        self._sdk_browse_btn = PushButton("Browse...")
        self._sdk_browse_btn.setIcon(make_icon("toolbar.open"))
        self._sdk_browse_btn.clicked.connect(self._browse_sdk_root)
        sdk_row.addWidget(self._sdk_browse_btn)
        self._sdk_clear_btn = PushButton("Clear")
        self._sdk_clear_btn.setIcon(make_icon("toolbar.delete"))
        self._sdk_clear_btn.clicked.connect(self._clear_sdk_root)
        sdk_row.addWidget(self._sdk_clear_btn)
        workspace_layout.addLayout(sdk_row)

        self._sdk_hint_label = QLabel("")
        self._sdk_hint_label.setObjectName("dialog_muted_hint")
        self._sdk_hint_label.setWordWrap(True)
        workspace_layout.addWidget(self._sdk_hint_label)

        parent_label = QLabel("Parent Directory")
        parent_label.setObjectName("new_project_field_label")
        workspace_layout.addSpacing(8)
        workspace_layout.addWidget(parent_label)

        self._parent_edit = LineEdit()
        self._parent_edit.setReadOnly(True)
        self._parent_edit.setText(self._parent_dir)
        parent_row = QHBoxLayout()
        parent_row.addWidget(self._parent_edit, 1)
        self._parent_browse_btn = PushButton("Browse...")
        self._parent_browse_btn.setIcon(make_icon("toolbar.open"))
        self._parent_browse_btn.clicked.connect(self._browse_parent_dir)
        parent_row.addWidget(self._parent_browse_btn)
        workspace_layout.addLayout(parent_row)
        workspace_layout.addStretch(1)
        content_layout.addWidget(workspace_card, 3)

        right_column = QVBoxLayout()
        right_column.setContentsMargins(0, 0, 0, 0)
        right_column.setSpacing(16)

        project_card = QFrame()
        project_card.setObjectName("new_project_form_card")
        project_layout = QVBoxLayout(project_card)
        project_layout.setContentsMargins(22, 22, 22, 22)
        project_layout.setSpacing(12)

        project_title = QLabel("Project Profile")
        project_title.setObjectName("workspace_section_title")
        project_layout.addWidget(project_title)

        project_hint = QLabel("Start with an explicit app name and target canvas size.")
        project_hint.setObjectName("workspace_section_subtitle")
        project_hint.setWordWrap(True)
        project_layout.addWidget(project_hint)

        app_name_label = QLabel("App Name")
        app_name_label.setObjectName("new_project_field_label")
        project_layout.addWidget(app_name_label)

        self._app_name_edit = LineEdit()
        self._app_name_edit.setPlaceholderText("e.g. MyDashboard")
        self._app_name_edit.textChanged.connect(self._update_accessibility_summary)
        project_layout.addWidget(self._app_name_edit)

        self._width_spin = QSpinBox()
        self._width_spin.setRange(16, 4096)
        self._width_spin.setValue(240)
        self._width_spin.valueChanged.connect(self._update_accessibility_summary)

        self._height_spin = QSpinBox()
        self._height_spin.setRange(16, 4096)
        self._height_spin.setValue(320)
        self._height_spin.valueChanged.connect(self._update_accessibility_summary)

        dimensions_layout = QHBoxLayout()
        dimensions_layout.setSpacing(12)
        dimensions_layout.addWidget(self._create_dimension_editor("Width", self._width_spin))
        dimensions_layout.addWidget(self._create_dimension_editor("Height", self._height_spin))
        project_layout.addLayout(dimensions_layout)
        right_column.addWidget(project_card)

        self._summary_card = QFrame()
        self._summary_card.setObjectName("new_project_summary_card")
        summary_layout = QVBoxLayout(self._summary_card)
        summary_layout.setContentsMargins(22, 22, 22, 22)
        summary_layout.setSpacing(10)

        summary_title = QLabel("Create Target")
        summary_title.setObjectName("workspace_section_title")
        summary_layout.addWidget(summary_title)

        summary_hint = QLabel("Review where the project lands and whether the current configuration is ready.")
        summary_hint.setObjectName("workspace_section_subtitle")
        summary_hint.setWordWrap(True)
        summary_layout.addWidget(summary_hint)

        target_caption = QLabel("Project Path")
        target_caption.setObjectName("new_project_summary_caption")
        summary_layout.addWidget(target_caption)

        self._target_value_label = QLabel("")
        self._target_value_label.setObjectName("new_project_summary_value")
        self._target_value_label.setWordWrap(True)
        summary_layout.addWidget(self._target_value_label)

        mode_caption = QLabel("Startup Mode")
        mode_caption.setObjectName("new_project_summary_caption")
        summary_layout.addWidget(mode_caption)

        self._mode_value_label = QLabel("")
        self._mode_value_label.setObjectName("new_project_summary_value")
        self._mode_value_label.setWordWrap(True)
        summary_layout.addWidget(self._mode_value_label)

        validation_caption = QLabel("Validation")
        validation_caption.setObjectName("new_project_summary_caption")
        summary_layout.addWidget(validation_caption)

        self._validation_value_label = QLabel("")
        self._validation_value_label.setObjectName("new_project_summary_value")
        self._validation_value_label.setWordWrap(True)
        summary_layout.addWidget(self._validation_value_label)
        right_column.addWidget(self._summary_card, 1)
        content_layout.addLayout(right_column, 2)
        layout.addLayout(content_layout, 1)

        buttons = QHBoxLayout()
        buttons.addStretch()
        self._cancel_btn = PushButton("Cancel")
        self._cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(self._cancel_btn)
        self._create_btn = PrimaryPushButton("Create")
        self._create_btn.setIcon(make_icon("toolbar.new"))
        self._create_btn.clicked.connect(self._accept_if_valid)
        buttons.addWidget(self._create_btn)
        layout.addLayout(buttons)
        self._sdk_edit.setAccessibleName("SDK root")
        self._parent_edit.setAccessibleName("Project parent directory")
        self._app_name_edit.setAccessibleName("Application name")
        self._width_spin.setAccessibleName("Project width")
        self._height_spin.setAccessibleName("Project height")
        _set_widget_metadata(
            self._sdk_browse_btn,
            tooltip="Browse to an EmbeddedGUI SDK root.",
            accessible_name="Browse SDK root",
        )
        _set_widget_metadata(
            self._sdk_clear_btn,
            tooltip="Clear the current SDK root and create an editing-only project.",
            accessible_name="Clear SDK root",
        )
        _set_widget_metadata(
            self._parent_browse_btn,
            tooltip="Browse to the parent directory where the new project will be created.",
            accessible_name="Browse parent directory",
        )
        _set_widget_metadata(self._cancel_btn, tooltip="Close this dialog without creating a project.", accessible_name="Cancel")
        self._update_accessibility_summary()

    def _create_header_metric(self, layout, label_text):
        card = QFrame()
        card.setObjectName("new_project_metric_card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(4)

        label = QLabel(label_text)
        label.setObjectName("new_project_metric_label")
        card_layout.addWidget(label)

        value = QLabel("")
        value.setObjectName("new_project_metric_value")
        value.setWordWrap(True)
        card_layout.addWidget(value)

        value._new_project_metric_name = label_text
        value._new_project_metric_label = label
        value._new_project_metric_card = card
        _set_widget_metadata(
            label,
            tooltip=f"{label_text} metric label.",
            accessible_name=f"{label_text} metric label.",
        )
        layout.addWidget(card)
        return value

    def _update_header_metric_metadata(self, metric_value, metric_text, *, tooltip_text=None):
        metric_name = getattr(metric_value, "_new_project_metric_name", "Project")
        normalized_text = str(metric_text or "none").strip() or "none"
        summary = f"{metric_name}: {normalized_text}."

        _set_widget_metadata(
            metric_value,
            tooltip=tooltip_text or summary,
            accessible_name=f"New project metric: {metric_name}. {normalized_text}.",
        )

        label = getattr(metric_value, "_new_project_metric_label", None)
        if label is not None:
            _set_widget_metadata(
                label,
                tooltip=summary,
                accessible_name=f"{metric_name} metric label.",
            )

        card = getattr(metric_value, "_new_project_metric_card", None)
        if card is not None:
            _set_widget_metadata(
                card,
                tooltip=summary,
                accessible_name=f"{metric_name} metric: {normalized_text}.",
            )

    def _create_dimension_editor(self, label_text, spin_box):
        card = QFrame()
        card.setObjectName("new_project_dimension_card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 14, 16, 14)
        card_layout.setSpacing(8)

        label = QLabel(label_text)
        label.setObjectName("new_project_field_label")
        card_layout.addWidget(label)
        card_layout.addWidget(spin_box)
        return card

    def _sdk_clear_metadata(self):
        if self._sdk_root:
            return (
                "Clear the current SDK root and create an editing-only project.",
                "Clear SDK root. Clear the current SDK root and create an editing-only project.",
            )
        return (
            "SDK root is already empty. The project will use editing-only mode until you set an SDK.",
            "Clear SDK root unavailable. SDK root is already empty. The project will use editing-only mode until you set an SDK.",
        )

    def _create_button_metadata(self):
        app_name = self.app_name
        parent_dir = self._parent_dir or ""
        if self._sdk_root and not is_valid_sdk_root(self._sdk_root):
            return (
                "Select a valid EmbeddedGUI SDK root or clear it before creating the project.",
                "Create project unavailable. Select a valid EmbeddedGUI SDK root or clear it before creating the project.",
            )
        if not parent_dir:
            return (
                "Select a parent directory before creating the project.",
                "Create project unavailable. Select a parent directory before creating the project.",
            )
        if not app_name:
            return (
                "Enter an application name before creating the project.",
                "Create project unavailable. Enter an application name before creating the project.",
            )
        if not app_name.replace("_", "").isalnum():
            return (
                "Application name must use letters, numbers, and underscores before the project can be created.",
                "Create project unavailable. Application name must use letters, numbers, and underscores before the project can be created.",
            )
        return (
            f"Create project {app_name} in {parent_dir} at {self.screen_width} by {self.screen_height}.",
            f"Create project: {app_name}. Create project {app_name} in {parent_dir} at {self.screen_width} by {self.screen_height}.",
        )

    def _browse_sdk_root(self):
        previous_default_parent = self._default_parent_dir_for_sdk(self._sdk_root)
        path = QFileDialog.getExistingDirectory(self, "Select SDK Root", self._sdk_root or "")
        if not path:
            return
        path = resolve_sdk_root_candidate(path)
        if not path:
            QMessageBox.warning(
                self,
                "Invalid SDK Root",
                "The selected directory does not contain a valid EmbeddedGUI SDK root.",
            )
            return
        self._sdk_root = path
        self._sdk_edit.setText(path)
        if self._parent_dir_auto_managed or self._parent_dir == previous_default_parent:
            self._parent_dir = self._default_parent_dir_for_sdk(path)
            self._parent_edit.setText(self._parent_dir)
            self._parent_dir_auto_managed = True
        self._update_accessibility_summary()

    def _clear_sdk_root(self):
        self._sdk_root = ""
        self._sdk_edit.setText("")
        self._update_accessibility_summary()

    def _browse_parent_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Select Parent Directory", self._parent_dir or "")
        if not path:
            return
        self._parent_dir = normalize_path(path)
        self._parent_edit.setText(self._parent_dir)
        self._parent_dir_auto_managed = False
        self._update_accessibility_summary()

    def _sdk_mode_summary(self):
        if self._sdk_root and is_valid_sdk_root(self._sdk_root):
            return (
                "Compile-backed preview",
                "Ready: new projects start with compile-backed preview using the selected SDK.",
                "success",
            )
        if self._sdk_root:
            return (
                "SDK path needs attention",
                "Invalid: select a valid EmbeddedGUI SDK root or clear it to create an editing-only project.",
                "warning",
            )
        return (
            "Editing-only start",
            "Optional. Leave empty to create an editing-only project and set the SDK later.",
            "muted",
        )

    def _validation_summary(self):
        if self._sdk_root and not is_valid_sdk_root(self._sdk_root):
            return "Select a valid SDK root or clear it", "warning"
        if not self._parent_dir:
            return "Parent directory required", "warning"
        if not self.app_name:
            return "App name required", "warning"
        if not self.app_name.replace("_", "").isalnum():
            return "Use letters, numbers, and underscores", "warning"
        return "Ready to create", "success"

    def _target_path_summary(self):
        if not self._parent_dir:
            return "Select a parent directory"
        app_name = self.app_name or "<app_name>"
        return os.path.join(self._parent_dir, app_name)

    def _condensed_path(self, path, *, tail_segments=4):
        normalized = normalize_path(path)
        if not normalized:
            return "Not set"

        drive, tail = os.path.splitdrive(normalized)
        separators = [part for part in tail.replace("/", os.sep).split(os.sep) if part]
        if len(separators) <= tail_segments:
            return normalized

        prefix = f"{drive}{os.sep}" if drive else (os.sep if normalized.startswith(os.sep) else "")
        return f"{prefix}...{os.sep}{os.sep.join(separators[-tail_segments:])}"

    def _update_accessibility_summary(self):
        mode_text, sdk_hint, sdk_tone = self._sdk_mode_summary()
        validation_text, validation_tone = self._validation_summary()
        target_path = self._target_path_summary()
        canvas_text = f"{self.screen_width} x {self.screen_height}"
        condensed_parent_dir = self._condensed_path(self._parent_dir, tail_segments=4)
        condensed_target_path = self._condensed_path(target_path, tail_segments=5)

        self._sdk_hint_label.setText(sdk_hint)
        _set_label_hint_tone(self._sdk_hint_label, sdk_tone)
        self._sdk_metric_value.setText(mode_text)
        self._location_metric_value.setText(condensed_parent_dir)
        self._canvas_metric_value.setText(canvas_text)
        self._target_value_label.setText(condensed_target_path)
        self._mode_value_label.setText(mode_text)
        _set_label_hint_tone(self._mode_value_label, sdk_tone)
        self._validation_value_label.setText(validation_text)
        _set_label_hint_tone(self._validation_value_label, validation_tone)

        sdk_root = self._sdk_root or "none"
        parent_dir = self._parent_dir or "none"
        app_name = self.app_name or "none"
        summary = (
            f"New Project dialog: SDK root {sdk_root}. Parent directory {parent_dir}. "
            f"App name {app_name}. Size {self.screen_width} by {self.screen_height}."
        )
        _set_widget_metadata(self, tooltip=summary, accessible_name=summary)
        _set_widget_metadata(
            self._header_frame,
            tooltip=f"New project header. {summary}",
            accessible_name=f"New project header. {summary}",
        )
        _set_widget_metadata(
            self._sdk_edit,
            tooltip=f"SDK root: {sdk_root}",
            accessible_name=f"SDK root: {sdk_root}",
        )
        _set_widget_metadata(
            self._sdk_hint_label,
            tooltip=self._sdk_hint_label.text(),
            accessible_name=self._sdk_hint_label.text(),
        )
        _set_widget_metadata(
            self._parent_edit,
            tooltip=f"Project parent directory: {parent_dir}",
            accessible_name=f"Project parent directory: {parent_dir}",
        )
        _set_widget_metadata(
            self._app_name_edit,
            tooltip=f"Application name: {app_name}",
            accessible_name=f"Application name: {app_name}",
        )
        _set_widget_metadata(
            self._width_spin,
            tooltip=f"Project width: {self.screen_width}",
            accessible_name=f"Project width: {self.screen_width}",
        )
        _set_widget_metadata(
            self._height_spin,
            tooltip=f"Project height: {self.screen_height}",
            accessible_name=f"Project height: {self.screen_height}",
        )
        self._update_header_metric_metadata(self._sdk_metric_value, mode_text)
        self._update_header_metric_metadata(
            self._location_metric_value,
            parent_dir,
            tooltip_text=self._parent_dir or "No parent directory selected.",
        )
        self._update_header_metric_metadata(self._canvas_metric_value, canvas_text)
        _set_widget_metadata(
            self._target_value_label,
            tooltip=target_path,
            accessible_name=f"Project path summary: {target_path}",
        )
        _set_widget_metadata(
            self._mode_value_label,
            tooltip=self._mode_value_label.text(),
            accessible_name=f"Startup mode summary: {self._mode_value_label.text()}",
        )
        _set_widget_metadata(
            self._validation_value_label,
            tooltip=self._validation_value_label.text(),
            accessible_name=f"Validation summary: {self._validation_value_label.text()}",
        )
        clear_tooltip, clear_name = self._sdk_clear_metadata()
        _set_widget_metadata(
            self._sdk_clear_btn,
            tooltip=clear_tooltip,
            accessible_name=clear_name,
        )
        create_tooltip, create_name = self._create_button_metadata()
        _set_widget_metadata(
            self._create_btn,
            tooltip=create_tooltip,
            accessible_name=create_name,
        )

    def _accept_if_valid(self):
        app_name = self.app_name
        if self._sdk_root and not is_valid_sdk_root(self._sdk_root):
            QMessageBox.warning(self, "Invalid SDK Root", "Please select a valid EmbeddedGUI SDK root or clear it.")
            return
        if not self._parent_dir:
            QMessageBox.warning(self, "Parent Directory", "Please select a parent directory.")
            return
        if not app_name:
            QMessageBox.warning(self, "App Name", "Please enter an app name.")
            return
        if not app_name.replace("_", "").isalnum():
            QMessageBox.warning(self, "App Name", "App name can only contain letters, numbers, and underscores.")
            return
        self.accept()

    @property
    def sdk_root(self):
        return self._sdk_root

    @property
    def parent_dir(self):
        return self._parent_dir

    @property
    def app_name(self):
        return self._app_name_edit.text().strip()

    @property
    def screen_width(self):
        return self._width_spin.value()

    @property
    def screen_height(self):
        return self._height_spin.value()
