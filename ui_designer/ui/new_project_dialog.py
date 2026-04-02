"""Dialog for creating a new standard EmbeddedGUI app project."""

from __future__ import annotations

import os

from PyQt5.QtWidgets import (
    QDialog,
    QFileDialog,
    QFormLayout,
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


class NewProjectDialog(QDialog):
    """Collect parameters for a new project."""

    def __init__(self, parent=None, sdk_root="", default_parent_dir=""):
        super().__init__(parent)
        self.setWindowTitle("New Project")
        self.resize(560, 260)

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
        form = QFormLayout()
        form.setSpacing(12)

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
        form.addRow("SDK Root", sdk_row)

        self._sdk_hint_label = QLabel("Optional. Leave empty to create an editing-only project and set the SDK later.")
        self._sdk_hint_label.setObjectName("dialog_muted_hint")
        self._sdk_hint_label.setWordWrap(True)
        form.addRow("", self._sdk_hint_label)

        self._parent_edit = LineEdit()
        self._parent_edit.setReadOnly(True)
        self._parent_edit.setText(self._parent_dir)
        parent_row = QHBoxLayout()
        parent_row.addWidget(self._parent_edit, 1)
        self._parent_browse_btn = PushButton("Browse...")
        self._parent_browse_btn.setIcon(make_icon("toolbar.open"))
        self._parent_browse_btn.clicked.connect(self._browse_parent_dir)
        parent_row.addWidget(self._parent_browse_btn)
        form.addRow("Parent Dir", parent_row)

        self._app_name_edit = LineEdit()
        self._app_name_edit.setPlaceholderText("e.g. MyDashboard")
        self._app_name_edit.textChanged.connect(self._update_accessibility_summary)
        form.addRow("App Name", self._app_name_edit)

        self._width_spin = QSpinBox()
        self._width_spin.setRange(16, 4096)
        self._width_spin.setValue(240)
        self._width_spin.valueChanged.connect(self._update_accessibility_summary)
        form.addRow("Width", self._width_spin)

        self._height_spin = QSpinBox()
        self._height_spin.setRange(16, 4096)
        self._height_spin.setValue(320)
        self._height_spin.valueChanged.connect(self._update_accessibility_summary)
        form.addRow("Height", self._height_spin)

        layout.addLayout(form)

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

    def _update_accessibility_summary(self):
        sdk_root = self._sdk_root or "none"
        parent_dir = self._parent_dir or "none"
        app_name = self.app_name or "none"
        summary = (
            f"New Project dialog: SDK root {sdk_root}. Parent directory {parent_dir}. "
            f"App name {app_name}. Size {self.screen_width} by {self.screen_height}."
        )
        _set_widget_metadata(self, tooltip=summary, accessible_name=summary)
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
