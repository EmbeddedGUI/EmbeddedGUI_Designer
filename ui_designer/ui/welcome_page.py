"""Welcome page for EmbeddedGUI Designer."""

from __future__ import annotations

import os

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QFrame, QLabel, QHBoxLayout, QVBoxLayout, QWidget

from qfluentwidgets import PrimaryPushButton, PushButton

from ..model.config import get_config
from ..model.sdk_bootstrap import (
    default_sdk_install_dir,
    describe_auto_download_plan,
    describe_sdk_source,
    describe_sdk_source_hint,
    sdk_root_source_kind,
)
from ..model.workspace import describe_sdk_root, resolve_configured_sdk_root
from .iconography import make_icon


def _set_widget_metadata(widget, *, tooltip=None, accessible_name=None):
    if tooltip is not None:
        widget.setToolTip(tooltip)
        widget.setStatusTip(tooltip)
    if accessible_name is not None:
        widget.setAccessibleName(accessible_name)


class RecentProjectItem(QWidget):
    """Card widget for a recent project entry."""

    item_clicked = pyqtSignal(str, str)

    def __init__(self, project_path, sdk_root, display_name, parent=None):
        super().__init__(parent)
        self.project_path = project_path
        self.sdk_root = sdk_root
        self.display_name = display_name
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAttribute(Qt.WA_Hover, True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(96)
        self.setObjectName("welcome_recent_item")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(14)

        icon_shell = QFrame()
        icon_shell.setObjectName("welcome_recent_icon_shell")
        icon_shell.setFixedSize(44, 44)
        icon_layout = QVBoxLayout(icon_shell)
        icon_layout.setContentsMargins(0, 0, 0, 0)

        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setPixmap(make_icon("nav.page_group", size=28).pixmap(28, 28))
        icon_layout.addWidget(icon_label)
        layout.addWidget(icon_shell, 0, Qt.AlignTop)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(6)

        self._name_label = QLabel(display_name)
        self._name_label.setFont(QFont("Segoe UI", 11, QFont.DemiBold))
        self._name_label.setObjectName("welcome_recent_name")
        text_layout.addWidget(self._name_label)

        self._path_label = QLabel(project_path)
        self._path_label.setObjectName("welcome_recent_path")
        self._path_label.setWordWrap(True)
        text_layout.addWidget(self._path_label)

        self._project_status = "ready" if os.path.exists(project_path) else "missing"
        self._sdk_status = describe_sdk_root(sdk_root)
        sdk_source = describe_sdk_source(sdk_root) if self._sdk_status == "ready" else self._sdk_status
        self._status_label = QLabel(
            f"Project: {self._project_status}  |  SDK: {self._sdk_status} ({sdk_source})"
        )
        self._status_label.setObjectName("welcome_recent_status")
        self._status_label.setWordWrap(True)
        if self._project_status != "ready":
            self._status_label.setProperty("chipTone", "danger")
        elif self._sdk_status == "ready":
            self._status_label.setProperty("chipTone", "success")
        elif self._sdk_status == "invalid":
            self._status_label.setProperty("chipTone", "warning")
        else:
            self._status_label.setProperty("chipTone", "danger")
        self._status_label.style().unpolish(self._status_label)
        self._status_label.style().polish(self._status_label)
        text_layout.addWidget(self._status_label)

        layout.addLayout(text_layout, 1)
        self._update_accessibility_summary()

    def _update_accessibility_summary(self):
        summary = (
            f"Recent project: {self.display_name}. Project {self._project_status}. "
            f"SDK {self._sdk_status}. Path: {self.project_path}."
        )
        _set_widget_metadata(self, tooltip=summary, accessible_name=summary)
        _set_widget_metadata(
            self._name_label,
            tooltip=summary,
            accessible_name=f"Recent project name: {self.display_name}",
        )
        _set_widget_metadata(
            self._path_label,
            tooltip=f"Recent project path: {self.project_path}",
            accessible_name=f"Recent project path: {self.project_path}",
        )
        _set_widget_metadata(
            self._status_label,
            tooltip=self._status_label.text(),
            accessible_name=f"Recent project status: {self._status_label.text()}",
        )

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.item_clicked.emit(self.project_path, self.sdk_root)
        super().mouseReleaseEvent(event)


class WelcomePage(QWidget):
    """Welcome page shown when no project is loaded."""

    open_recent = pyqtSignal(str, str)
    new_project = pyqtSignal()
    open_project = pyqtSignal()
    open_app = pyqtSignal()
    set_sdk_root = pyqtSignal()
    download_sdk = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._config = get_config()
        self._recent_project_count = 0
        self._init_ui()

    def _init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        shell = QWidget()
        shell.setAttribute(Qt.WA_StyledBackground, True)
        shell.setObjectName("welcome_shell")
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(28, 28, 28, 28)
        shell_layout.setSpacing(18)

        center_widget = QWidget()
        center_widget.setAttribute(Qt.WA_StyledBackground, True)
        center_widget.setObjectName("welcome_center")
        center_widget.setMaximumWidth(1180)
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(18)

        self._hero = QFrame()
        self._hero.setObjectName("welcome_hero")
        hero_layout = QHBoxLayout(self._hero)
        hero_layout.setContentsMargins(28, 26, 28, 26)
        hero_layout.setSpacing(24)

        hero_copy = QVBoxLayout()
        hero_copy.setContentsMargins(0, 0, 0, 0)
        hero_copy.setSpacing(8)

        self._eyebrow_label = QLabel("Workspace Launcher")
        self._eyebrow_label.setObjectName("welcome_eyebrow")
        hero_copy.addWidget(self._eyebrow_label, 0, Qt.AlignLeft)

        self._title_label = QLabel("EmbeddedGUI Designer")
        self._title_label.setFont(QFont("Segoe UI", 28, QFont.Light))
        self._title_label.setObjectName("welcome_hero_title")
        hero_copy.addWidget(self._title_label)

        self._subtitle_label = QLabel("Visual UI design, compile-backed preview, and SDK workspace control in one shell")
        self._subtitle_label.setFont(QFont("Segoe UI", 12))
        self._subtitle_label.setObjectName("welcome_hero_subtitle")
        self._subtitle_label.setWordWrap(True)
        hero_copy.addWidget(self._subtitle_label)

        self._hero_hint_label = QLabel(
            "Create a project, reopen recent work, or attach an SDK example. The launch surface stays lightweight while the editor shell stays canvas-first."
        )
        self._hero_hint_label.setObjectName("welcome_hero_hint")
        self._hero_hint_label.setWordWrap(True)
        hero_copy.addWidget(self._hero_hint_label)
        hero_copy.addStretch(1)
        hero_layout.addLayout(hero_copy, 3)

        hero_metrics = QVBoxLayout()
        hero_metrics.setContentsMargins(0, 0, 0, 0)
        hero_metrics.setSpacing(10)
        self._overview_sdk_value = self._create_overview_metric(hero_metrics, "SDK Binding")
        self._overview_preview_value = self._create_overview_metric(hero_metrics, "Preview Mode")
        self._overview_recent_value = self._create_overview_metric(hero_metrics, "Recent Work")
        hero_layout.addLayout(hero_metrics, 2)
        center_layout.addWidget(self._hero)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(18)

        left_card = QFrame()
        left_card.setObjectName("welcome_action_panel")
        left_col = QVBoxLayout(left_card)
        left_col.setContentsMargins(22, 22, 22, 22)
        left_col.setSpacing(12)

        self._start_label = QLabel("Start")
        self._start_label.setFont(QFont("Segoe UI", 14, QFont.DemiBold))
        self._start_label.setObjectName("workspace_section_title")
        left_col.addWidget(self._start_label)

        self._start_hint_label = QLabel("Open the main editor through a clean, single-path launch surface.")
        self._start_hint_label.setObjectName("workspace_section_subtitle")
        self._start_hint_label.setWordWrap(True)
        left_col.addWidget(self._start_hint_label)

        self._new_project_btn = PrimaryPushButton("New Project...")
        self._new_project_btn.setIcon(make_icon("toolbar.new"))
        self._new_project_btn.clicked.connect(self.new_project.emit)
        left_col.addWidget(self._new_project_btn)

        self._open_project_btn = PushButton("Open Project File...")
        self._open_project_btn.setIcon(make_icon("toolbar.open"))
        self._open_project_btn.clicked.connect(self.open_project.emit)
        left_col.addWidget(self._open_project_btn)

        self._open_app_btn = PushButton("Open SDK Example...")
        self._open_app_btn.setIcon(make_icon("nav.page"))
        self._open_app_btn.clicked.connect(self.open_app.emit)
        left_col.addWidget(self._open_app_btn)

        self._set_sdk_root_btn = PushButton("Set SDK Root...")
        self._set_sdk_root_btn.setIcon(make_icon("toolbar.settings.project"))
        self._set_sdk_root_btn.clicked.connect(self.set_sdk_root.emit)
        left_col.addWidget(self._set_sdk_root_btn)

        self._download_sdk_btn = PushButton("Download SDK...")
        self._download_sdk_btn.setIcon(make_icon("toolbar.compile"))
        self._download_sdk_btn.clicked.connect(self.download_sdk.emit)
        self._download_sdk_btn.setToolTip(describe_auto_download_plan())
        self._download_sdk_btn.setStatusTip(self._download_sdk_btn.toolTip())
        left_col.addWidget(self._download_sdk_btn)

        self._sdk_card = QFrame()
        self._sdk_card.setObjectName("welcome_sdk_panel")
        sdk_layout = QVBoxLayout(self._sdk_card)
        sdk_layout.setContentsMargins(18, 16, 18, 16)
        sdk_layout.setSpacing(8)

        self._sdk_title_label = QLabel("SDK Status")
        self._sdk_title_label.setFont(QFont("Segoe UI", 11, QFont.DemiBold))
        self._sdk_title_label.setObjectName("workspace_section_title")
        sdk_layout.addWidget(self._sdk_title_label)

        self._sdk_status_label = QLabel("")
        self._sdk_status_label.setObjectName("workspace_status_chip")
        self._sdk_status_label.setWordWrap(True)
        sdk_layout.addWidget(self._sdk_status_label)

        self._sdk_path_label = QLabel("")
        self._sdk_path_label.setWordWrap(True)
        self._sdk_path_label.setObjectName("workspace_section_subtitle")
        sdk_layout.addWidget(self._sdk_path_label)

        self._sdk_hint_label = QLabel("")
        self._sdk_hint_label.setWordWrap(True)
        self._sdk_hint_label.setObjectName("workspace_section_subtitle")
        sdk_layout.addWidget(self._sdk_hint_label)

        left_col.addSpacing(10)
        left_col.addWidget(self._sdk_card)
        left_col.addStretch()
        content_layout.addWidget(left_card, 3)

        right_card = QFrame()
        right_card.setObjectName("welcome_recent_panel")
        right_col = QVBoxLayout(right_card)
        right_col.setContentsMargins(22, 22, 22, 22)
        right_col.setSpacing(12)

        self._recent_label = QLabel("Recent Projects")
        self._recent_label.setFont(QFont("Segoe UI", 14, QFont.DemiBold))
        self._recent_label.setObjectName("workspace_section_title")
        right_col.addWidget(self._recent_label)

        self._recent_hint_label = QLabel("Return to active projects quickly with path and SDK health visible at a glance.")
        self._recent_hint_label.setObjectName("workspace_section_subtitle")
        self._recent_hint_label.setWordWrap(True)
        right_col.addWidget(self._recent_hint_label)

        self._recent_list = QVBoxLayout()
        self._recent_list.setSpacing(8)
        right_col.addLayout(self._recent_list)
        right_col.addStretch()
        content_layout.addWidget(right_card, 4)

        center_layout.addLayout(content_layout, 1)

        self._footer_label = QLabel("Press Ctrl+Shift+O to open an SDK example, Ctrl+O to open a .egui project, or Ctrl+N to create a new project")
        self._footer_label.setObjectName("workspace_section_subtitle")
        self._footer_label.setAlignment(Qt.AlignCenter)
        center_layout.addWidget(self._footer_label)

        shell_layout.addWidget(center_widget, 0, Qt.AlignCenter)
        main_layout.addStretch()
        main_layout.addWidget(shell, 1)
        main_layout.addStretch()
        self._new_project_btn.setAccessibleName("Create new project action")
        self._open_project_btn.setAccessibleName("Open project file action")
        self._open_app_btn.setAccessibleName("Open SDK example")
        self._set_sdk_root_btn.setAccessibleName("Set SDK root")
        self._download_sdk_btn.setAccessibleName("Download SDK")
        _set_widget_metadata(
            self._new_project_btn,
            tooltip="Create a new EmbeddedGUI Designer project.",
            accessible_name="Create new project action. Create a new EmbeddedGUI Designer project.",
        )
        _set_widget_metadata(
            self._open_project_btn,
            tooltip="Open an existing .egui project file.",
            accessible_name="Open project file action. Open an existing .egui project file.",
        )
        _set_widget_metadata(self._open_app_btn, tooltip="Open an SDK example project or legacy example.", accessible_name="Open SDK example")
        _set_widget_metadata(self._set_sdk_root_btn, tooltip="Choose the EmbeddedGUI SDK root used for compile preview.", accessible_name="Set SDK root")

        self._refresh_sdk_status()
        self._refresh_recent_list()

    def _create_overview_metric(self, layout, label_text):
        card = QFrame()
        card.setObjectName("welcome_metric_card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(4)

        label = QLabel(label_text)
        label.setObjectName("welcome_metric_label")
        card_layout.addWidget(label)

        value = QLabel("")
        value.setObjectName("welcome_metric_value")
        value.setWordWrap(True)
        card_layout.addWidget(value)

        layout.addWidget(card)
        return value

    def _set_sdk_chip_tone(self, tone):
        self._sdk_status_label.setProperty("chipTone", tone)
        self._sdk_status_label.style().unpolish(self._sdk_status_label)
        self._sdk_status_label.style().polish(self._sdk_status_label)
        self._sdk_status_label.update()

    def _refresh_sdk_status(self):
        sdk_root = resolve_configured_sdk_root(
            self._config.sdk_root,
            self._config.egui_root,
            cached_sdk_root=default_sdk_install_dir(),
            preserve_invalid=True,
        )
        sdk_status = describe_sdk_root(sdk_root)
        default_cache_dir = default_sdk_install_dir()
        auto_download_plan = describe_auto_download_plan(default_cache_dir)
        if sdk_status == "ready":
            source_kind = sdk_root_source_kind(sdk_root)
            if source_kind == "bundled":
                self._sdk_status_label.setText("Ready: using bundled SDK copy")
            elif source_kind == "runtime_local":
                self._sdk_status_label.setText("Ready: using SDK stored beside the application")
            elif source_kind == "cached":
                self._sdk_status_label.setText("Ready: using auto-downloaded SDK cache")
            else:
                self._sdk_status_label.setText("Ready: using selected SDK root")
            self._sdk_hint_label.setText(describe_sdk_source_hint(sdk_root))
            self._set_sdk_chip_tone("success")
        elif sdk_status == "invalid":
            self._sdk_status_label.setText("Invalid: SDK path needs attention")
            self._set_sdk_chip_tone("warning")
            self._sdk_hint_label.setText(
                "Select a valid SDK root, or download one automatically to restore compile preview.\n"
                f"{auto_download_plan}"
            )
        else:
            self._sdk_status_label.setText("Missing: editing only, Python preview fallback")
            self._set_sdk_chip_tone("danger")
            self._sdk_hint_label.setText(
                "You can still edit projects, but compile preview stays disabled until you set or download an SDK.\n"
                f"{auto_download_plan}"
            )

        self._sdk_path_label.setText(sdk_root or "No SDK root configured")
        preview_summary = "Compile-backed preview ready" if sdk_status == "ready" else "Python preview fallback"
        self._overview_sdk_value.setText(self._sdk_status_label.text())
        self._overview_preview_value.setText(preview_summary)
        self._update_accessibility_summary()

    def _resolve_display_sdk_root(self, sdk_root=""):
        return resolve_configured_sdk_root(
            sdk_root,
            cached_sdk_root=default_sdk_install_dir(),
            preserve_invalid=True,
        )

    def _refresh_recent_list(self):
        while self._recent_list.count():
            item = self._recent_list.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()

        recent = list(self._config.recent_projects or [])
        visible_recent = recent[:8]
        self._recent_project_count = len(visible_recent)
        self._overview_recent_value.setText(self._recent_projects_summary())
        if not visible_recent:
            empty = QWidget()
            empty.setObjectName("welcome_recent_empty")
            el = QVBoxLayout(empty)
            el.setContentsMargins(0, 4, 0, 0)
            el.setSpacing(6)
            no_recent = QLabel("No recent projects")
            no_recent.setObjectName("workspace_section_title")
            sub = QLabel("Open a .egui file or create a project - it will appear here.")
            sub.setObjectName("workspace_section_subtitle")
            sub.setWordWrap(True)
            el.addWidget(no_recent)
            el.addWidget(sub)
            summary = "No recent projects. Open a project to see it listed here."
            _set_widget_metadata(empty, tooltip=summary, accessible_name=summary)
            self._recent_list.addWidget(empty)
            self._update_accessibility_summary()
            return

        for item_data in visible_recent:
            project_path = item_data.get("project_path", "")
            sdk_root = self._resolve_display_sdk_root(item_data.get("sdk_root", ""))
            display_name = item_data.get("display_name") or os.path.splitext(os.path.basename(project_path))[0]
            item = RecentProjectItem(project_path, sdk_root, display_name)
            item.item_clicked.connect(self._on_recent_clicked)
            self._recent_list.addWidget(item)
        self._update_accessibility_summary()

    def _on_recent_clicked(self, project_path, sdk_root):
        self.open_recent.emit(project_path, sdk_root)

    def refresh(self):
        self._refresh_sdk_status()
        self._refresh_recent_list()

    def _recent_projects_summary(self):
        if self._recent_project_count == 0:
            return "No recent projects"
        if self._recent_project_count == 1:
            return "1 recent item"
        return f"{self._recent_project_count} recent items"

    def _update_accessibility_summary(self):
        recent_text = self._recent_projects_summary()
        sdk_status = self._sdk_status_label.text().strip() or "SDK status unavailable."
        sdk_path = self._sdk_path_label.text().strip() or "No SDK root configured"
        summary = f"Welcome page: {sdk_status}. SDK path: {sdk_path}. {recent_text}."
        _set_widget_metadata(self, tooltip=summary, accessible_name=summary)
        _set_widget_metadata(self._title_label, tooltip=summary, accessible_name=self._title_label.text())
        _set_widget_metadata(self._subtitle_label, tooltip=self._subtitle_label.text(), accessible_name=self._subtitle_label.text())
        _set_widget_metadata(self._hero_hint_label, tooltip=self._hero_hint_label.text(), accessible_name=self._hero_hint_label.text())
        _set_widget_metadata(self._eyebrow_label, tooltip=self._eyebrow_label.text(), accessible_name=self._eyebrow_label.text())
        _set_widget_metadata(self._start_label, tooltip=self._start_label.text(), accessible_name=self._start_label.text())
        _set_widget_metadata(self._start_hint_label, tooltip=self._start_hint_label.text(), accessible_name=self._start_hint_label.text())
        _set_widget_metadata(self._sdk_card, tooltip=sdk_status, accessible_name=f"SDK card: {sdk_status}")
        _set_widget_metadata(self._sdk_title_label, tooltip=self._sdk_title_label.text(), accessible_name=self._sdk_title_label.text())
        _set_widget_metadata(
            self._sdk_status_label,
            tooltip=self._sdk_status_label.text(),
            accessible_name=f"SDK status: {self._sdk_status_label.text()}",
        )
        _set_widget_metadata(
            self._sdk_path_label,
            tooltip=self._sdk_path_label.text(),
            accessible_name=f"SDK path: {self._sdk_path_label.text()}",
        )
        _set_widget_metadata(
            self._sdk_hint_label,
            tooltip=self._sdk_hint_label.text(),
            accessible_name=f"SDK hint: {self._sdk_hint_label.text()}",
        )
        if sdk_status.startswith("Ready:"):
            open_app_hint = "Open an SDK example project or legacy example."
            set_sdk_hint = "Change the EmbeddedGUI SDK root used for compile preview."
        elif sdk_status.startswith("Invalid:"):
            open_app_hint = "SDK root needs attention before browsing SDK examples."
            set_sdk_hint = "Choose a valid EmbeddedGUI SDK root used for compile preview."
        else:
            open_app_hint = "Set or download an SDK before browsing SDK examples."
            set_sdk_hint = "Choose the EmbeddedGUI SDK root used for compile preview."
        _set_widget_metadata(
            self._open_app_btn,
            tooltip=open_app_hint,
            accessible_name=f"Open SDK example action. {open_app_hint}",
        )
        _set_widget_metadata(
            self._set_sdk_root_btn,
            tooltip=set_sdk_hint,
            accessible_name=f"Set SDK root action. {set_sdk_hint}",
        )
        download_hint = describe_auto_download_plan(default_sdk_install_dir())
        _set_widget_metadata(
            self._download_sdk_btn,
            tooltip=download_hint,
            accessible_name=f"Download SDK action. {download_hint}",
        )
        recent_label_summary = f"Recent Projects: {recent_text}."
        _set_widget_metadata(
            self._recent_label,
            tooltip=recent_label_summary,
            accessible_name=recent_label_summary,
        )
        _set_widget_metadata(
            self._recent_hint_label,
            tooltip=self._recent_hint_label.text(),
            accessible_name=self._recent_hint_label.text(),
        )
        _set_widget_metadata(
            self._overview_sdk_value,
            tooltip=self._overview_sdk_value.text(),
            accessible_name=f"Welcome metric: SDK binding. {self._overview_sdk_value.text()}",
        )
        _set_widget_metadata(
            self._overview_preview_value,
            tooltip=self._overview_preview_value.text(),
            accessible_name=f"Welcome metric: Preview mode. {self._overview_preview_value.text()}",
        )
        _set_widget_metadata(
            self._overview_recent_value,
            tooltip=self._overview_recent_value.text(),
            accessible_name=f"Welcome metric: Recent work. {self._overview_recent_value.text()}",
        )
        _set_widget_metadata(self._footer_label, tooltip=self._footer_label.text(), accessible_name=self._footer_label.text())
