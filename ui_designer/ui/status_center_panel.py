"""Status center panel for workspace health and quick actions."""

from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QMenu, QProgressBar, QPushButton, QToolButton, QVBoxLayout, QWidget

from .iconography import make_icon


class _ClickableFrame(QFrame):
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.rect().contains(event.pos()):
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.clicked.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class StatusCenterPanel(QWidget):
    """Workspace status dashboard with quick-open actions."""

    action_requested = pyqtSignal(str)
    _MAX_RECENT_ACTIONS = 6
    _ACTION_LABELS = {
        "open_project_panel": "Project",
        "open_structure_panel": "Structure",
        "open_components_panel": "Widgets",
        "open_assets_panel": "Assets",
        "open_properties_inspector": "Properties",
        "open_animations_inspector": "Animations",
        "open_page_fields": "Fields",
        "open_page_timers": "Timers",
        "open_diagnostics": "Diagnostics",
        "open_error_diagnostics": "Errors",
        "open_warning_diagnostics": "Warnings",
        "open_info_diagnostics": "Info",
        "open_history": "History",
        "open_debug": "Debug Output",
        "open_first_error": "First Error",
        "open_first_warning": "First Warning",
    }
    _ACTION_ICONS = {
        "open_project_panel": "project",
        "open_structure_panel": "structure",
        "open_components_panel": "widgets",
        "open_assets_panel": "assets",
        "open_properties_inspector": "properties",
        "open_animations_inspector": "animation",
        "open_page_fields": "page",
        "open_page_timers": "time",
        "open_diagnostics": "diagnostics",
        "open_error_diagnostics": "diagnostics",
        "open_warning_diagnostics": "history",
        "open_info_diagnostics": "debug",
        "open_history": "history",
        "open_debug": "debug",
        "open_first_error": "diagnostics",
        "open_first_warning": "diagnostics",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._last_action = ""
        self._recent_actions = []
        self._health_chip_action = "open_diagnostics"
        self._suggested_action_key = "open_diagnostics"
        self._status_snapshot = None
        self._status_snapshot_initialized = False
        self._init_ui()
        self._set_last_action("", [])
        self.set_status()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        header = QFrame()
        header.setObjectName("status_center_header")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(14, 14, 14, 14)
        header_layout.setSpacing(6)

        header_title_row = QHBoxLayout()
        header_title_row.setContentsMargins(0, 0, 0, 0)
        header_title_row.setSpacing(8)
        self._header_title = QLabel("Status Center")
        self._header_title.setObjectName("workspace_section_title")
        self._header_title.setAccessibleName("Status Center")
        header_title_row.addWidget(self._header_title)
        self._workspace_chip = QToolButton()
        self._workspace_chip.setText("Check Workspace")
        self._workspace_chip.setObjectName("workspace_status_chip")
        self._workspace_chip.setProperty("chipTone", "warning")
        self._workspace_chip.setCursor(Qt.PointingHandCursor)
        self._workspace_chip.setAccessibleName("Workspace status chip")
        self._workspace_chip.clicked.connect(self._trigger_suggested_action)
        header_title_row.addStretch()
        header_title_row.addWidget(self._workspace_chip)
        header_layout.addLayout(header_title_row)

        self._header_subtitle = QLabel("Monitor diagnostics, preview runtime, and jump to key tooling quickly.")
        self._header_subtitle.setObjectName("workspace_section_subtitle")
        self._header_subtitle.setWordWrap(True)
        self._header_subtitle.setAccessibleName("Status Center summary")
        header_layout.addWidget(self._header_subtitle)
        self._workspace_summary_label = QLabel(
            "Workspace: SDK missing, compile unavailable, Preview idle, no dirty pages, no widgets selected."
        )
        self._workspace_summary_label.setObjectName("workspace_section_subtitle")
        self._workspace_summary_label.setWordWrap(True)
        self._workspace_summary_label.setAccessibleName("Workspace summary")
        header_layout.addWidget(self._workspace_summary_label)
        layout.addWidget(header)

        metrics = QFrame()
        metrics.setObjectName("status_center_metrics")
        metrics_layout = QGridLayout(metrics)
        metrics_layout.setContentsMargins(10, 10, 10, 10)
        metrics_layout.setHorizontalSpacing(10)
        metrics_layout.setVerticalSpacing(10)
        self._sdk_value, self._sdk_card = self._create_metric(
            metrics_layout, 0, 0, "SDK", "Missing", "assets", "open_project_panel"
        )
        self._compile_value, self._compile_card = self._create_metric(
            metrics_layout, 0, 1, "Compile", "Unavailable", "compile", "open_debug"
        )
        self._diag_value, self._diag_card = self._create_metric(
            metrics_layout, 1, 0, "Diagnostics", "No active diagnostics", "diagnostics", "open_diagnostics"
        )
        self._preview_value, self._preview_card = self._create_metric(
            metrics_layout, 1, 1, "Preview", "Preview idle", "debug", "open_debug"
        )
        self._selection_value, self._selection_card = self._create_metric(
            metrics_layout, 2, 0, "Selection", "No widgets selected", "structure", "open_structure_panel"
        )
        self._dirty_value, self._dirty_card = self._create_metric(
            metrics_layout, 2, 1, "Dirty Pages", "No dirty pages", "history", "open_history"
        )
        layout.addWidget(metrics)

        health = QFrame()
        health.setObjectName("status_center_health")
        health_layout = QVBoxLayout(health)
        health_layout.setContentsMargins(12, 12, 12, 12)
        health_layout.setSpacing(8)

        health_title_row = QHBoxLayout()
        health_title_row.setContentsMargins(0, 0, 0, 0)
        health_title_row.setSpacing(8)
        self._health_title = QLabel("Diagnostic Mix")
        self._health_title.setObjectName("workspace_section_title")
        self._health_title.setAccessibleName("Diagnostic Mix")
        health_title_row.addWidget(self._health_title)
        self._health_chip = QToolButton()
        self._health_chip.setText("Stable")
        self._health_chip.setObjectName("workspace_status_chip")
        self._health_chip.setProperty("chipTone", "success")
        self._health_chip.setCursor(Qt.PointingHandCursor)
        self._health_chip.clicked.connect(self._open_health_chip_target)
        health_title_row.addStretch()
        health_title_row.addWidget(self._health_chip)
        health_layout.addLayout(health_title_row)

        self._error_value, self._error_bar, self._error_row = self._create_health_row(
            health_layout, "Errors", "diagnostics", "status_center_health_error_bar", "open_error_diagnostics"
        )
        self._warning_value, self._warning_bar, self._warning_row = self._create_health_row(
            health_layout, "Warnings", "history", "status_center_health_warning_bar", "open_warning_diagnostics"
        )
        self._info_value, self._info_bar, self._info_row = self._create_health_row(
            health_layout, "Info", "debug", "status_center_health_info_bar", "open_info_diagnostics"
        )
        self._health_summary_label = QLabel("Summary: Diagnostics are clear.")
        self._health_summary_label.setObjectName("workspace_section_subtitle")
        self._health_summary_label.setWordWrap(True)
        self._health_summary_label.setAccessibleName("Diagnostic summary")
        health_layout.addWidget(self._health_summary_label)
        layout.addWidget(health)

        quick_actions = QFrame()
        quick_actions.setObjectName("status_center_actions")
        quick_layout = QVBoxLayout(quick_actions)
        quick_layout.setContentsMargins(12, 12, 12, 12)
        quick_layout.setSpacing(8)

        self._actions_title = QLabel("Quick Actions")
        self._actions_title.setObjectName("workspace_section_title")
        self._actions_title.setAccessibleName("Quick actions title")
        quick_layout.addWidget(self._actions_title)
        self._last_action_host = QWidget()
        self._last_action_host.setObjectName("status_center_last_action_host")
        last_action_row = QHBoxLayout(self._last_action_host)
        last_action_row.setContentsMargins(0, 0, 0, 0)
        last_action_row.setSpacing(8)
        self._last_action_label = QLabel("Last action: None")
        self._last_action_label.setObjectName("workspace_section_subtitle")
        last_action_row.addWidget(self._last_action_label, 0)
        last_action_row.addStretch(1)
        self._repeat_action_menu = QMenu(self)
        self._repeat_action_button = QToolButton()
        self._repeat_action_button.setIcon(make_icon("history"))
        self._repeat_action_button.setPopupMode(QToolButton.MenuButtonPopup)
        self._repeat_action_button.setMenu(self._repeat_action_menu)
        self._repeat_action_button.setEnabled(False)
        self._repeat_action_button.clicked.connect(self._repeat_last_action)
        last_action_row.addWidget(self._repeat_action_button, 0)
        quick_layout.addWidget(self._last_action_host)
        self._recent_actions_label = QLabel("Recent actions: none yet.")
        self._recent_actions_label.setObjectName("workspace_section_subtitle")
        self._recent_actions_label.setWordWrap(True)
        quick_layout.addWidget(self._recent_actions_label)
        suggested_row = QHBoxLayout()
        suggested_row.setContentsMargins(0, 0, 0, 0)
        suggested_row.setSpacing(8)
        self._suggested_action_label = QLabel("Suggested next step:")
        self._suggested_action_label.setObjectName("workspace_section_subtitle")
        self._suggested_action_label.setVisible(False)
        suggested_row.addWidget(self._suggested_action_label, 0)
        self._suggested_action_button = QPushButton("Open Diagnostics")
        self._suggested_action_button.setIcon(make_icon("diagnostics"))
        self._suggested_action_button.setAccessibleName("Suggested status action")
        self._suggested_action_button.clicked.connect(self._trigger_suggested_action)
        suggested_row.addWidget(self._suggested_action_button, 0)
        suggested_row.addStretch()
        quick_layout.addLayout(suggested_row)
        self._suggested_action_summary_label = QLabel("Guidance: Open Project to configure the SDK workspace.")
        self._suggested_action_summary_label.setObjectName("workspace_section_subtitle")
        self._suggested_action_summary_label.setWordWrap(True)
        self._suggested_action_summary_label.setAccessibleName("Suggested action guidance")
        quick_layout.addWidget(self._suggested_action_summary_label)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        self._diag_btn = self._build_action_button("Diagnostics", "diagnostics", "open_diagnostics")
        self._history_btn = self._build_action_button("History", "history", "open_history")
        self._debug_btn = self._build_action_button("Debug Output", "debug", "open_debug")
        row.addWidget(self._diag_btn)
        row.addWidget(self._history_btn)
        row.addWidget(self._debug_btn)
        quick_layout.addLayout(row)

        self._diagnostic_jump_host = QWidget()
        self._diagnostic_jump_host.setObjectName("status_center_diagnostic_jump_host")
        row2 = QHBoxLayout(self._diagnostic_jump_host)
        row2.setContentsMargins(0, 0, 0, 0)
        row2.setSpacing(8)
        self._first_error_btn = self._build_action_button("Open First Error", "diagnostics", "open_first_error")
        self._first_warning_btn = self._build_action_button("Open First Warning", "diagnostics", "open_first_warning")
        row2.addWidget(self._first_error_btn)
        row2.addWidget(self._first_warning_btn)
        row2.addStretch()
        quick_layout.addWidget(self._diagnostic_jump_host)

        row3 = QHBoxLayout()
        row3.setContentsMargins(0, 0, 0, 0)
        row3.setSpacing(8)
        self._project_btn = self._build_action_button("Project", "project", "open_project_panel")
        self._structure_btn = self._build_action_button("Structure", "structure", "open_structure_panel")
        self._components_btn = self._build_action_button("Widgets", "widgets", "open_components_panel")
        self._assets_btn = self._build_action_button("Assets", "assets", "open_assets_panel")
        row3.addWidget(self._project_btn)
        row3.addWidget(self._structure_btn)
        row3.addWidget(self._components_btn)
        row3.addWidget(self._assets_btn)
        row3.addStretch()
        quick_layout.addLayout(row3)

        row4 = QHBoxLayout()
        row4.setContentsMargins(0, 0, 0, 0)
        row4.setSpacing(8)
        self._properties_btn = self._build_action_button("Properties", "properties", "open_properties_inspector")
        self._animations_btn = self._build_action_button("Animations", "animation", "open_animations_inspector")
        self._fields_btn = self._build_action_button("Fields", "page", "open_page_fields")
        self._timers_btn = self._build_action_button("Timers", "time", "open_page_timers")
        row4.addWidget(self._properties_btn)
        row4.addWidget(self._animations_btn)
        row4.addWidget(self._fields_btn)
        row4.addWidget(self._timers_btn)
        row4.addStretch()
        quick_layout.addLayout(row4)
        layout.addWidget(quick_actions)

        runtime = _ClickableFrame()
        runtime.setObjectName("status_center_runtime")
        runtime.clicked.connect(lambda: self._emit_action("open_debug"))
        self._set_hint(runtime, "Open Debug Output")
        runtime.setAccessibleName("Runtime section")
        runtime_layout = QVBoxLayout(runtime)
        runtime_layout.setContentsMargins(12, 12, 12, 12)
        runtime_layout.setSpacing(6)
        runtime_title_row = QHBoxLayout()
        runtime_title_row.setContentsMargins(0, 0, 0, 0)
        runtime_title_row.setSpacing(8)
        self._runtime_title = QLabel("Runtime")
        self._runtime_title.setObjectName("workspace_section_title")
        self._runtime_title.setAccessibleName("Runtime")
        runtime_title_row.addWidget(self._runtime_title)
        self._runtime_chip = QToolButton()
        self._runtime_chip.setText("Clear")
        self._runtime_chip.setObjectName("workspace_status_chip")
        self._runtime_chip.setProperty("chipTone", "success")
        self._runtime_chip.setCursor(Qt.PointingHandCursor)
        self._runtime_chip.setAccessibleName("Runtime status: Clear")
        self._runtime_chip.clicked.connect(lambda: self._emit_action("open_debug"))
        runtime_title_row.addStretch()
        runtime_title_row.addWidget(self._runtime_chip)
        runtime_layout.addLayout(runtime_title_row)
        self._runtime_label = QLabel("No runtime errors.")
        self._runtime_label.setObjectName("workspace_section_subtitle")
        self._runtime_label.setWordWrap(True)
        runtime_layout.addWidget(self._runtime_label)
        self._runtime_panel = runtime
        layout.addWidget(runtime)

        layout.addStretch()

    def _create_metric(self, grid_layout, row, col, label, value, icon_key, action_key=""):
        card = _ClickableFrame() if action_key else QFrame()
        card.setObjectName("status_center_metric_card")
        if action_key:
            card.clicked.connect(lambda key=action_key: self._emit_action(key))
            self._set_hint(card, f"Open {label}")
            card.setAccessibleName(f"{label} metric")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 10, 10, 10)
        card_layout.setSpacing(6)
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(6)
        icon_label = QLabel()
        icon_label.setPixmap(make_icon(icon_key, size=16).pixmap(16, 16))
        top.addWidget(icon_label, 0, Qt.AlignVCenter)
        title = QLabel(label)
        title.setObjectName("workspace_section_subtitle")
        top.addWidget(title, 1)
        card_layout.addLayout(top)
        value_label = QLabel(value)
        value_label.setObjectName("status_center_metric_value")
        value_label.setAccessibleName(f"{label} value")
        card_layout.addWidget(value_label)
        grid_layout.addWidget(card, row, col)
        return value_label, card

    def _create_health_row(self, host_layout, label, icon_key, bar_object_name, action_key=""):
        row = _ClickableFrame() if action_key else QFrame()
        row.setObjectName("status_center_health_row")
        if action_key:
            row.clicked.connect(lambda key=action_key: self._emit_action(key))
            self._set_hint(row, f"Open {label}")
            row.setAccessibleName(f"{label} diagnostics")
        row_layout = QVBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(4)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(6)
        icon_label = QLabel()
        icon_label.setPixmap(make_icon(icon_key, size=14).pixmap(14, 14))
        top.addWidget(icon_label, 0, Qt.AlignVCenter)
        title = QLabel(label)
        title.setObjectName("workspace_section_subtitle")
        top.addWidget(title, 1)
        value_label = QLabel("0")
        value_label.setObjectName("status_center_health_value")
        value_label.setAccessibleName(f"{label} diagnostics value")
        top.addWidget(value_label, 0, Qt.AlignRight)
        row_layout.addLayout(top)

        bar = QProgressBar()
        bar.setObjectName(bar_object_name)
        bar.setTextVisible(False)
        bar.setRange(0, 100)
        bar.setValue(0)
        bar.setAccessibleName(f"{label} diagnostics share")
        row_layout.addWidget(bar)
        host_layout.addWidget(row)
        return value_label, bar, row

    def _set_chip_text(self, chip, text, tone=None):
        chip.setText(str(text or ""))
        if tone is not None:
            chip.setProperty("chipTone", str(tone or "accent"))
        chip.style().unpolish(chip)
        chip.style().polish(chip)
        chip.update()

    def _set_widget_icon(self, widget, icon_key, size=16):
        key = str(icon_key or "history").strip() or "history"
        widget.setProperty("iconKey", key)
        widget.setIcon(make_icon(key, size=size))

    def _build_action_button(self, text, icon_key, action_key):
        button = QPushButton(text)
        button.setProperty("baseText", text)
        button.setIcon(make_icon(icon_key))
        default_hint = f"Open {self._action_label(action_key)}."
        button.setAccessibleName(
            self._action_button_accessible_name(action_key, text, hint=default_hint)
        )
        self._set_hint(button, default_hint)
        button.clicked.connect(lambda checked=False, key=action_key: self._emit_action(key))
        return button

    def _action_label(self, action_key):
        action = str(action_key or "").strip()
        if not action:
            return "None"
        return self._ACTION_LABELS.get(action, action.replace("_", " ").title())

    def _action_icon_key(self, action_key):
        action = str(action_key or "").strip()
        if not action:
            return "history"
        return self._ACTION_ICONS.get(action, "history")

    def _normalize_recent_actions(self, recent_actions, prepend_action=""):
        normalized = []
        candidates = []
        prepend = str(prepend_action or "").strip()
        if prepend:
            candidates.append(prepend)
        if isinstance(recent_actions, (list, tuple)):
            candidates.extend(recent_actions)
        for raw_action in candidates:
            action = str(raw_action or "").strip()
            if not action or action in normalized:
                continue
            normalized.append(action)
            if len(normalized) >= self._MAX_RECENT_ACTIONS:
                break
        return normalized

    def _refresh_repeat_action_menu(self):
        self._repeat_action_menu.clear()
        if not self._recent_actions:
            empty_action = self._repeat_action_menu.addAction("No recent actions yet")
            empty_action.setEnabled(False)
            self._set_action_hint(empty_action, self._recent_actions_tooltip())
            self._update_repeat_action_menu_metadata()
            return
        for action_key in self._recent_actions:
            action_label = self._action_label(action_key)
            menu_action = self._repeat_action_menu.addAction(action_label)
            menu_action.setIcon(make_icon(self._action_icon_key(action_key), size=16))
            if action_key == self._last_action:
                menu_tooltip = f"Repeat the current action: {action_label}."
            else:
                menu_tooltip = f"Replay {action_label} from recent history."
            self._set_action_hint(menu_action, menu_tooltip)
            menu_action.triggered.connect(lambda checked=False, key=action_key: self._emit_action(key))
        self._repeat_action_menu.addSeparator()
        clear_action = self._repeat_action_menu.addAction(self._clear_recent_actions_label())
        clear_action.setIcon(make_icon("history", size=16))
        self._set_action_hint(clear_action, self._clear_recent_actions_tooltip())
        clear_action.triggered.connect(self._clear_recent_actions)
        self._update_repeat_action_menu_metadata()

    def _recent_actions_summary(self):
        count = len(self._recent_actions)
        if count <= 0:
            return "Recent actions: none yet."
        labels = [self._action_label(action_key) for action_key in self._recent_actions]
        if len(labels) > 3:
            labels = labels[:3] + [f"+{count - 3} more"]
        return f"Recent actions ({count}): {', '.join(labels)}."

    def _recent_actions_title(self):
        count = len(self._recent_actions)
        if count <= 1:
            return "Quick Actions"
        return f"Quick Actions ({count} recent actions)"

    def _recent_actions_title_tooltip(self):
        count = len(self._recent_actions)
        if count <= 0:
            return "Quick actions with no recent actions yet."
        if count == 1:
            return "Quick actions with the current action ready to repeat."
        return f"Quick actions with {count} recent actions tracked."

    def _recent_actions_title_accessible_name(self):
        count = len(self._recent_actions)
        if count <= 0:
            return "Quick actions section: No recent actions yet."
        if count == 1:
            return "Quick actions section: Current action ready to repeat."
        return f"Quick actions section: {count} recent actions tracked."

    def _show_recent_actions_summary(self):
        return len(self._recent_actions) > 1

    def _recent_actions_tooltip(self):
        count = len(self._recent_actions)
        if count <= 0:
            return "No recent actions yet."
        noun = "action" if count == 1 else "actions"
        labels = ", ".join(self._action_label(action_key) for action_key in self._recent_actions)
        return f"{count} recent {noun}: {labels}"

    def _repeat_action_menu_summary(self):
        count = len(self._recent_actions)
        if count <= 0:
            return "Repeat action menu: no recent actions yet."
        noun = "action" if count == 1 else "actions"
        labels = ", ".join(self._action_label(action_key) for action_key in self._recent_actions)
        current_label = self._action_label(self._last_action)
        return (
            f"Repeat action menu: {count} recent {noun}. "
            f"Current action: {current_label}. Actions: {labels}."
        )

    def _update_repeat_action_menu_metadata(self):
        summary = self._repeat_action_menu_summary()
        self._set_hint(self._repeat_action_menu, summary)
        self._repeat_action_menu.setAccessibleName(summary)

    def _recent_actions_accessible_name(self):
        count = len(self._recent_actions)
        if count <= 0:
            return "Recent actions: none yet."
        noun = "recent action" if count == 1 else "recent actions"
        labels = ", ".join(self._action_label(action_key) for action_key in self._recent_actions)
        return f"Recent actions summary: {count} {noun} tracked. {labels}."

    def _clear_recent_actions_tooltip(self):
        count = len(self._recent_actions)
        noun = "action" if count == 1 else "actions"
        return f"Clear {count} recent {noun}."

    def _clear_recent_actions_label(self):
        count = len(self._recent_actions)
        return f"Clear Recent Actions ({count})" if count > 0 else "Clear Recent Actions"

    def _repeat_action_tooltip(self, action_label):
        if not self._last_action:
            return "No recent action to repeat yet."
        count = len(self._recent_actions)
        noun = "action" if count == 1 else "actions"
        if count > 1:
            return (
                f"Repeat {action_label}. {count} recent {noun} tracked. "
                "Use the menu arrow to replay an older action."
            )
        return f"Repeat {action_label}. {count} recent {noun} tracked."

    def _repeat_action_accessible_name(self, action_label):
        if not self._last_action:
            return "Repeat action unavailable: No recent action yet."
        count = len(self._recent_actions)
        noun = "recent action" if count == 1 else "recent actions"
        if count > 1:
            return (
                f"Repeat action: {action_label}. {count} {noun} tracked. "
                "Older actions are available in the menu."
            )
        return f"Repeat action: {action_label}. {count} {noun} tracked."

    def _last_action_tooltip(self, action_label):
        if not self._last_action:
            return "No recent action yet."
        count = len(self._recent_actions)
        noun = "recent action" if count == 1 else "recent actions"
        return f"Current action: {action_label}. {count} {noun} tracked."

    def _last_action_accessible_name(self, action_label):
        if not self._last_action:
            return "Last action: None. No recent actions yet."
        count = len(self._recent_actions)
        noun = "recent action" if count == 1 else "recent actions"
        return f"Last action: {action_label}. {count} {noun} tracked."

    def _set_hint(self, widget, text):
        hint = str(text or "").strip()
        widget.setToolTip(hint)
        widget.setStatusTip(hint)

    def _set_action_hint(self, action, text):
        hint = str(text or "").strip()
        action.setToolTip(hint)
        action.setStatusTip(hint)
        action.setWhatsThis(hint)

    def _count_label(self, count, singular, plural):
        value = max(int(count or 0), 0)
        return f"{value} {singular if value == 1 else plural}"

    def _active_count_hint(self, count, singular, plural):
        value = max(int(count or 0), 0)
        if value <= 0:
            return f"No {plural} active."
        return f"{self._count_label(value, singular, plural)} active."

    def _count_with_percent(self, count, total, singular, plural):
        value = max(int(count or 0), 0)
        total_value = max(int(total or 0), 0)
        if total_value <= 0:
            if value <= 0:
                return f"No {plural}"
            return self._count_label(value, singular, plural)
        percent = int(round((value * 100.0) / total_value))
        return f"{self._count_label(value, singular, plural)} ({percent}%)"

    def _diagnostic_metric_text(self, error_count, warning_count, info_count):
        total = max(int(error_count or 0), 0) + max(int(warning_count or 0), 0) + max(int(info_count or 0), 0)
        if total <= 0:
            return "No active diagnostics"
        return ", ".join(
            [
                self._count_label(error_count, "error", "errors"),
                self._count_label(warning_count, "warning", "warnings"),
                self._count_label(info_count, "info item", "info items"),
            ]
        )

    def _diagnostic_metric_summary(self, error_count, warning_count, info_count):
        total = max(int(error_count or 0), 0) + max(int(warning_count or 0), 0) + max(int(info_count or 0), 0)
        if total <= 0:
            return "No active diagnostics"
        return self._diagnostic_metric_text(error_count, warning_count, info_count)

    def _debug_button_text(self, can_compile, runtime_text):
        if str(runtime_text or "").strip():
            return "Debug Output (Issue)"
        if not can_compile:
            return "Debug Output (Build)"
        return "Debug Output"

    def _debug_button_hint(self, can_compile, runtime_text, preview_text):
        message = str(runtime_text or "").strip()
        if message:
            return f"Open Debug Output. Runtime issue: {message}"
        if not can_compile:
            return "Open Debug Output. Compile is unavailable."
        return f"Open Debug Output. {preview_text}."

    def _project_button_text(self, sdk_ready):
        return "Project" if sdk_ready else "Project (Setup)"

    def _counted_label(self, base_text, count=0):
        value = max(int(count or 0), 0)
        return f"{base_text} ({value})" if value > 0 else str(base_text or "").strip()

    def _diagnostics_button_text(self, total_count):
        total = max(int(total_count or 0), 0)
        return f"Diagnostics ({total} active)" if total > 0 else "Diagnostics"

    def _history_button_text(self, dirty_count):
        total = max(int(dirty_count or 0), 0)
        return f"History ({total} dirty)" if total > 0 else "History"

    def _structure_button_text(self, selection_total):
        total = max(int(selection_total or 0), 0)
        return f"Structure ({total} selected)" if total > 0 else "Structure"

    def _diagnostics_hint(self, error_count, warning_count, info_count):
        total = max(int(error_count or 0), 0) + max(int(warning_count or 0), 0) + max(int(info_count or 0), 0)
        if total <= 0:
            return "Open Diagnostics. No active diagnostics."
        return (
            "Open Diagnostics. "
            f"{self._count_label(error_count, 'error', 'errors')}, "
            f"{self._count_label(warning_count, 'warning', 'warnings')}, "
            f"{self._count_label(info_count, 'info item', 'info items')}."
        )

    def _history_hint(self, dirty_count):
        total = max(int(dirty_count or 0), 0)
        if total <= 0:
            return "Open History. No dirty pages."
        return f"Open History. {self._count_label(total, 'dirty page', 'dirty pages')}."

    def _structure_hint(self, selection_total):
        total = max(int(selection_total or 0), 0)
        if total <= 0:
            return "Open Structure. No widgets selected."
        return f"Open Structure. {self._count_label(total, 'widget', 'widgets')} selected."

    def _selection_metric_summary(self, selection_total):
        total = max(int(selection_total or 0), 0)
        if total <= 0:
            return "No widgets selected"
        return self._count_label(total, "widget", "widgets")

    def _dirty_metric_summary(self, dirty_count):
        total = max(int(dirty_count or 0), 0)
        if total <= 0:
            return "No dirty pages"
        return self._count_label(total, "dirty page", "dirty pages")

    def _selection_metric_text(self, selection_total):
        total = max(int(selection_total or 0), 0)
        if total <= 0:
            return "No widgets selected"
        return self._count_label(total, "widget", "widgets")

    def _dirty_metric_text(self, dirty_count):
        total = max(int(dirty_count or 0), 0)
        if total <= 0:
            return "No dirty pages"
        return self._count_label(total, "dirty page", "dirty pages")

    def _compile_metric_text(self, can_compile):
        return "Ready" if bool(can_compile) else "Unavailable"

    def _set_metric_context(self, label, value_label, card, summary):
        summary_text = str(summary or "").strip()
        label_text = str(label or "").strip() or "Metric"
        self._set_hint(value_label, f"{label_text}: {summary_text}")
        value_label.setAccessibleName(f"{label_text} value: {summary_text}")
        self._set_hint(card, f"Open {label_text}. {summary_text}")
        card.setAccessibleName(f"{label_text} metric: {summary_text}")

    def _metric_card_accessible_name(self, label, summary, hint):
        label_text = str(label or "").strip() or "Metric"
        summary_text = str(summary or "").strip()
        hint_text = str(hint or "").strip()
        base = f"{label_text} metric: {summary_text}" if summary_text else f"{label_text} metric"
        if hint_text:
            return f"{base}. {hint_text}"
        return base

    def _diagnostic_summary_text(self, error_count, warning_count, info_count):
        errors = max(int(error_count or 0), 0)
        warnings = max(int(warning_count or 0), 0)
        infos = max(int(info_count or 0), 0)
        total = errors + warnings + infos
        parts = []
        if errors > 0:
            parts.append(self._count_label(errors, "error", "errors"))
        if warnings > 0:
            parts.append(self._count_label(warnings, "warning", "warnings"))
        if infos > 0:
            parts.append(self._count_label(infos, "info item", "info items"))
        if not parts:
            return "Summary: Diagnostics are clear."
        dominant_label = ""
        dominant_count = 0
        if errors >= warnings and errors >= infos:
            dominant_label = "Errors"
            dominant_count = errors
        elif warnings >= infos:
            dominant_label = "Warnings"
            dominant_count = warnings
        else:
            dominant_label = "Info"
            dominant_count = infos
        dominant_share = int(round((dominant_count * 100.0) / max(total, 1)))
        if errors > 0:
            return f"Summary: {', '.join(parts)} need attention. {dominant_label} lead at {dominant_share}%."
        if warnings > 0:
            return f"Summary: {', '.join(parts)} need review. {dominant_label} lead at {dominant_share}%."
        return f"Summary: {', '.join(parts)} available. {dominant_label} lead at {dominant_share}%."

    def _diagnostic_title_text(self, total_count):
        total = max(int(total_count or 0), 0)
        return f"Diagnostic Mix ({total} total)" if total > 0 else "Diagnostic Mix"

    def _diagnostic_title_tooltip(self, total_count):
        total = max(int(total_count or 0), 0)
        if total <= 0:
            return "Diagnostic mix with no active diagnostics."
        return f"Diagnostic mix with {total} total diagnostics."

    def _diagnostic_title_accessible_name(self, total_count):
        total = max(int(total_count or 0), 0)
        if total <= 0:
            return "Diagnostic mix title: No active diagnostics."
        return f"Diagnostic mix title: {total} total diagnostics."

    def _runtime_title_text(self, runtime_text):
        return "Runtime (Issue)" if str(runtime_text or "").strip() else "Runtime"

    def _runtime_title_tooltip(self, runtime_text):
        message = str(runtime_text or "").strip()
        if message:
            return f"Runtime status: issue detected. {message}"
        return "Runtime status: clear."

    def _runtime_title_accessible_name(self, runtime_text):
        message = str(runtime_text or "").strip()
        if message:
            return f"Runtime title: Issue detected. {message}"
        return "Runtime title: Clear. No runtime errors."

    def _workspace_summary_text(
        self,
        sdk_ready,
        can_compile,
        dirty_count,
        selection_total,
        preview_text,
        diag_total=0,
        runtime_text="",
        suggested_label="",
    ):
        sdk_text = "SDK ready" if sdk_ready else "SDK missing"
        compile_text = "compile ready" if can_compile else "compile unavailable"
        preview_value = str(preview_text or "Preview idle").strip() or "Preview idle"
        runtime_summary = "runtime issue detected" if str(runtime_text or "").strip() else "runtime clear"
        dirty_summary = (
            self._count_label(dirty_count, "dirty page", "dirty pages")
            if int(dirty_count or 0) > 0
            else "no dirty pages"
        )
        selection_summary = (
            f"{self._count_label(selection_total, 'widget', 'widgets')} selected"
            if int(selection_total or 0) > 0
            else "no widgets selected"
        )
        diag_summary = "diagnostics clear" if int(diag_total or 0) <= 0 else self._count_label(diag_total, "diagnostic", "diagnostics")
        summary = (
            f"Workspace: {sdk_text}, {compile_text}, {preview_value}, {runtime_summary}, "
            f"{dirty_summary}, {selection_summary}, {diag_summary}."
        )
        suggested = str(suggested_label or "").strip()
        if suggested:
            summary = f"{summary} Next: {suggested}."
        return summary

    def _workspace_chip_state(
        self,
        *,
        sdk_ready,
        can_compile,
        dirty_count,
        selection_total,
        error_count,
        warning_count,
        info_count,
        runtime_text,
    ):
        if error_count > 0:
            return ("Action Needed (Diagnostics)", "danger")
        if warning_count > 0 and runtime_text:
            return ("Check Workspace (Diagnostics)", "danger")
        if warning_count > 0:
            return ("Check Workspace (Diagnostics)", "warning")
        if runtime_text:
            return ("Action Needed (Runtime)", "danger")
        if not sdk_ready:
            return ("Check Workspace (Setup)", "warning")
        if not can_compile:
            return ("Check Workspace (Build)", "warning")
        if dirty_count > 0:
            return ("In Progress (History)", "accent")
        if selection_total > 0:
            return ("In Progress (Selection)", "accent")
        if info_count > 0:
            return ("In Progress (Diagnostics)", "accent")
        return ("Ready", "success")

    def _header_subtitle_text(self, workspace_chip_label, suggested_label):
        status = str(workspace_chip_label or "").strip()
        focus = str(suggested_label or "").strip() or "Open Diagnostics"
        if status.startswith("Action Needed"):
            return f"Action needed now. Focus on {focus}."
        if status.startswith("Check Workspace"):
            return f"Workspace checks are pending. Focus on {focus}."
        if status.startswith("In Progress"):
            return f"Work is in progress. Focus on {focus}."
        return f"Workspace looks ready. {focus} is available."

    def _header_subtitle_tooltip(self, workspace_chip_label, suggested_hint):
        status = str(workspace_chip_label or "").strip() or "Ready"
        hint = str(suggested_hint or "").strip()
        if hint:
            return f"Status Center: {status}. {hint}"
        return f"Status Center: {status}."

    def _header_subtitle_accessible_name(self, workspace_chip_label, suggested_label, suggested_hint):
        summary = self._header_subtitle_text(workspace_chip_label, suggested_label)
        hint = str(suggested_hint or "").strip()
        if hint:
            return f"Status Center summary: {summary} {hint}"
        return f"Status Center summary: {summary}"

    def _header_title_text(self, suggested_context):
        context = str(suggested_context or "").strip()
        return f"Status Center ({context})" if context else "Status Center"

    def _header_title_tooltip(self, suggested_context, workspace_chip_label):
        context = str(suggested_context or "").strip() or "Status"
        status = str(workspace_chip_label or "").strip() or "Ready"
        return f"Status Center focused on {context}. {status}."

    def _header_title_accessible_name(self, suggested_context, workspace_chip_label):
        context = str(suggested_context or "").strip() or "Status"
        status = str(workspace_chip_label or "").strip() or "Ready"
        return f"Status Center title: {context}. Current status: {status}."

    def _workspace_chip_accessible_name(self, workspace_chip_label, suggested_label, suggested_hint):
        status = str(workspace_chip_label or "").strip() or "Ready"
        label = str(suggested_label or "").strip() or "Open Diagnostics"
        hint = str(suggested_hint or "").strip()
        if hint:
            return f"Workspace status: {status}. Suggested: {label}. {hint}"
        return f"Workspace status: {status}. Suggested: {label}."

    def _summary_accessible_name(self, label, summary_text):
        prefix = str(label or "").strip() or "Summary"
        summary = str(summary_text or "").strip()
        return f"{prefix}: {summary}" if summary else prefix

    def _action_button_accessible_name(self, action_key, button_text, available=True, hint=""):
        label = self._action_label(action_key)
        text = str(button_text or "").strip() or label
        summary = str(hint or "").strip()
        if not available:
            base = f"{label} action unavailable: {text}"
        else:
            base = f"{label} action: {text}"
        if summary:
            return f"{base}. {summary}"
        return base

    def _health_row_accessible_name(self, label, value_text, inactive_hint=""):
        row_label = str(label or "").strip() or "Diagnostics"
        if str(inactive_hint or "").strip():
            return f"{row_label} diagnostics: {str(inactive_hint).strip()}"
        value = str(value_text or "").strip()
        return f"{row_label} diagnostics: {value}" if value else f"{row_label} diagnostics"

    def _health_share_summary(self, label, value_text, total_count):
        share_label = str(label or "").strip() or "Diagnostics"
        total = max(int(total_count or 0), 0)
        if total <= 0:
            return f"{share_label} share: No active diagnostics"
        value = str(value_text or "").strip()
        return f"{share_label} share: {value}" if value else f"{share_label} share"

    def _runtime_panel_accessible_name(self, runtime_text):
        message = str(runtime_text or "").strip()
        if message:
            return f"Runtime section: Issue. {message}"
        return "Runtime section: Clear. No runtime errors."

    def _runtime_chip_accessible_name(self, runtime_text):
        message = str(runtime_text or "").strip()
        if message:
            return f"Runtime status: Issue. Open Debug Output. Runtime issue: {message}"
        return "Runtime status: Clear. Open Debug Output. No runtime errors."

    def _health_chip_accessible_name(self, status_text, health_hint):
        status = str(status_text or "").strip() or "Stable"
        hint = str(health_hint or "").strip()
        if hint:
            return f"Diagnostic status: {status}. {hint}"
        return f"Diagnostic status: {status}"

    def _suggested_action_state(
        self,
        *,
        sdk_ready,
        can_compile,
        dirty_count,
        selection_total,
        error_count,
        warning_count,
        info_count,
        runtime_text,
    ):
        if error_count > 0:
            return (
                "open_first_error",
                self._counted_label("Fix First Error", error_count),
                "Diagnostics",
                "diagnostics",
                f"Start with the first error in Diagnostics. {self._active_count_hint(error_count, 'error', 'errors')}",
            )
        if warning_count > 0:
            return (
                "open_first_warning",
                self._counted_label("Review First Warning", warning_count),
                "Diagnostics",
                "diagnostics",
                f"Review the first warning in Diagnostics. {self._active_count_hint(warning_count, 'warning', 'warnings')}",
            )
        if runtime_text:
            return (
                "open_debug",
                "Inspect Debug Output",
                "Runtime",
                "debug",
                f"Inspect the latest runtime output. {runtime_text}",
            )
        if not sdk_ready:
            return (
                "open_project_panel",
                "Configure SDK",
                "Workspace",
                "project",
                "Open Project to configure the SDK workspace. SDK root is missing or invalid.",
            )
        if not can_compile:
            return (
                "open_debug",
                "Inspect Compile Output",
                "Build",
                "debug",
                "Open Debug Output to inspect compile output. Compile is unavailable.",
            )
        if dirty_count > 0:
            return (
                "open_history",
                self._counted_label("Review History", dirty_count),
                "History",
                "history",
                f"Review unsaved changes in History. {self._count_label(dirty_count, 'dirty page', 'dirty pages')} pending.",
            )
        if selection_total > 0:
            return (
                "open_structure_panel",
                self._counted_label("Inspect Selection", selection_total),
                "Selection",
                "structure",
                f"Open Structure for the current selection. {self._count_label(selection_total, 'widget', 'widgets')} selected.",
            )
        if info_count > 0:
            return (
                "open_info_diagnostics",
                self._counted_label("Inspect Info", info_count),
                "Diagnostics",
                "debug",
                f"Inspect informational diagnostics. {self._active_count_hint(info_count, 'info item', 'info items')}",
            )
        return (
            "open_diagnostics",
            "Open Diagnostics",
            "Diagnostics",
            "diagnostics",
            "Open Diagnostics for a full health review.",
        )

    def _suggested_action_title_text(self, suggested_context):
        context = str(suggested_context or "").strip() or "Status"
        return f"Suggested next step ({context}):"

    def _suggested_action_title_tooltip(self, suggested_context, suggested_hint):
        context = str(suggested_context or "").strip() or "status"
        hint = str(suggested_hint or "").strip()
        if hint:
            return f"Suggested next step in {context}. {hint}"
        return f"Suggested next step in {context}."

    def _suggested_action_title_accessible_name(self, suggested_context, suggested_label, suggested_hint):
        title = self._suggested_action_title_text(suggested_context)
        label = str(suggested_label or "").strip()
        hint = str(suggested_hint or "").strip()
        summary = f"{title} {label}".strip()
        if hint:
            return f"{summary}. {hint}"
        return summary

    def _suggested_action_summary_text(self, suggested_context, suggested_hint):
        context = str(suggested_context or "").strip()
        prefix = f"{context} guidance" if context else "Guidance"
        hint = str(suggested_hint or "").strip()
        return f"{prefix}: {hint}" if hint else f"{prefix}:"

    def _suggested_action_button_accessible_name(self, suggested_context, suggested_label, suggested_hint):
        label = str(suggested_label or "").strip() or "Open Diagnostics"
        context = str(suggested_context or "").strip() or "Status"
        hint = str(suggested_hint or "").strip()
        if hint:
            return f"Suggested status action: {label}. Context: {context}. {hint}"
        return f"Suggested status action: {label}. Context: {context}."

    def _set_last_action(self, action_key, recent_actions=None):
        self._last_action = str(action_key or "").strip()
        self._recent_actions = self._normalize_recent_actions(
            self._recent_actions if recent_actions is None else recent_actions,
            prepend_action=self._last_action,
        )
        action_label = self._action_label(self._last_action)
        self._last_action_label.setText(f"Last action: {action_label}")
        self._set_hint(self._last_action_label, self._last_action_tooltip(action_label))
        self._last_action_label.setAccessibleName(self._last_action_accessible_name(action_label))
        self._actions_title.setText(self._recent_actions_title())
        self._set_hint(self._actions_title, self._recent_actions_title_tooltip())
        self._actions_title.setAccessibleName(self._recent_actions_title_accessible_name())
        self._recent_actions_label.setText(self._recent_actions_summary())
        self._set_hint(self._recent_actions_label, self._recent_actions_tooltip())
        self._recent_actions_label.setAccessibleName(self._recent_actions_accessible_name())
        self._recent_actions_label.setVisible(self._show_recent_actions_summary())
        has_action = bool(self._last_action)
        self._last_action_label.setVisible(len(self._recent_actions) > 1)
        self._last_action_host.setVisible(has_action)
        self._repeat_action_button.setPopupMode(
            QToolButton.MenuButtonPopup if len(self._recent_actions) > 1 else QToolButton.DelayedPopup
        )
        self._repeat_action_button.setEnabled(has_action)
        self._repeat_action_button.setText(f"Repeat {action_label}" if has_action else "Repeat Action")
        self._set_widget_icon(
            self._repeat_action_button,
            self._action_icon_key(self._last_action if has_action else "history"),
            size=20,
        )
        self._set_hint(self._repeat_action_button, self._repeat_action_tooltip(action_label))
        self._repeat_action_button.setAccessibleName(self._repeat_action_accessible_name(action_label))
        self._refresh_repeat_action_menu()

    def _repeat_last_action(self):
        if not self._last_action:
            return
        self._emit_action(self._last_action)

    def _clear_recent_actions(self):
        self._set_last_action("", [])

    def _open_health_chip_target(self):
        self._emit_action(self._health_chip_action or "open_diagnostics")

    def _trigger_suggested_action(self):
        self._emit_action(self._suggested_action_key or "open_diagnostics")

    def _emit_action(self, action_key):
        self._set_last_action(action_key)
        self.action_requested.emit(action_key)

    def view_state(self):
        return {
            "last_action": self._last_action,
            "recent_actions": list(self._recent_actions),
        }

    def restore_view_state(self, state):
        if not isinstance(state, dict):
            self._set_last_action("", [])
            return
        self._set_last_action(state.get("last_action", ""), state.get("recent_actions", []))

    def set_status(
        self,
        *,
        sdk_ready=False,
        can_compile=False,
        dirty_pages=0,
        selection_count=0,
        preview_label="Preview idle",
        diagnostics_errors=0,
        diagnostics_warnings=0,
        diagnostics_infos=0,
        runtime_error="",
    ):
        sdk_ready = bool(sdk_ready)
        can_compile = bool(can_compile)
        dirty_count = max(int(dirty_pages or 0), 0)
        selection_total = max(int(selection_count or 0), 0)
        preview_text = str(preview_label or "Preview idle")
        error_count = max(int(diagnostics_errors or 0), 0)
        warning_count = max(int(diagnostics_warnings or 0), 0)
        info_count = max(int(diagnostics_infos or 0), 0)
        diag_total = error_count + warning_count + info_count
        runtime_text = str(runtime_error or "").strip()
        status_snapshot = (
            sdk_ready,
            can_compile,
            dirty_count,
            selection_total,
            preview_text,
            error_count,
            warning_count,
            info_count,
            runtime_text,
        )
        if self._status_snapshot_initialized and self._status_snapshot == status_snapshot:
            return

        self._sdk_value.setText("Ready" if sdk_ready else "Missing")
        self._compile_value.setText(self._compile_metric_text(can_compile))
        self._dirty_value.setText(self._dirty_metric_text(dirty_count))
        self._selection_value.setText(self._selection_metric_text(selection_total))
        self._preview_value.setText(preview_text)
        self._diag_value.setText(self._diagnostic_metric_text(error_count, warning_count, info_count))
        total = max(error_count + warning_count + info_count, 1)
        self._error_value.setText(self._count_with_percent(error_count, diag_total, "error", "errors"))
        self._warning_value.setText(self._count_with_percent(warning_count, diag_total, "warning", "warnings"))
        self._info_value.setText(self._count_with_percent(info_count, diag_total, "info item", "info items"))
        self._error_bar.setValue(int(round((error_count * 100.0) / total)))
        self._warning_bar.setValue(int(round((warning_count * 100.0) / total)))
        self._info_bar.setValue(int(round((info_count * 100.0) / total)))
        self._diag_btn.setText(self._diagnostics_button_text(diag_total))
        self._history_btn.setText(self._history_button_text(dirty_count))
        self._structure_btn.setText(self._structure_button_text(selection_total))
        self._debug_btn.setText(self._debug_button_text(can_compile, runtime_text))
        self._project_btn.setText(self._project_button_text(sdk_ready))
        self._set_metric_context("SDK", self._sdk_value, self._sdk_card, self._sdk_value.text())
        self._set_metric_context("Compile", self._compile_value, self._compile_card, self._compile_value.text())
        self._set_metric_context(
            "Diagnostics",
            self._diag_value,
            self._diag_card,
            self._diagnostic_metric_summary(error_count, warning_count, info_count),
        )
        self._set_metric_context("Preview", self._preview_value, self._preview_card, self._preview_value.text())
        self._set_metric_context(
            "Selection",
            self._selection_value,
            self._selection_card,
            self._selection_metric_summary(selection_total),
        )
        self._set_metric_context(
            "Dirty Pages",
            self._dirty_value,
            self._dirty_card,
            self._dirty_metric_summary(dirty_count),
        )
        self._set_hint(
            self._sdk_card,
            "Open Project. SDK workspace is ready." if sdk_ready else "Open Project. SDK root is missing or invalid.",
        )
        self._set_hint(
            self._compile_card,
            "Open Debug Output. Compile is ready."
            if can_compile
            else "Open Debug Output. Compile is unavailable.",
        )
        diag_hint = self._diagnostics_hint(error_count, warning_count, info_count)
        self._set_hint(self._diag_card, diag_hint)
        self._set_hint(self._diag_btn, diag_hint)
        preview_hint = f"Open Debug Output. {preview_text}."
        self._set_hint(self._preview_card, preview_hint)
        debug_hint = self._debug_button_hint(can_compile, runtime_text, preview_text)
        self._set_hint(
            self._debug_btn,
            debug_hint,
        )
        structure_hint = self._structure_hint(selection_total)
        self._set_hint(self._selection_card, structure_hint)
        history_hint = self._history_hint(dirty_count)
        self._set_hint(self._dirty_card, history_hint)
        self._set_hint(self._history_btn, history_hint)
        project_hint = (
            "Open Project. SDK workspace is ready." if sdk_ready else "Open Project. SDK root is missing or invalid."
        )
        self._set_hint(
            self._project_btn,
            project_hint,
        )
        self._set_hint(self._structure_btn, structure_hint)
        self._sdk_card.setAccessibleName(
            self._metric_card_accessible_name("SDK", self._sdk_value.text(), self._sdk_card.toolTip())
        )
        self._compile_card.setAccessibleName(
            self._metric_card_accessible_name("Compile", self._compile_value.text(), self._compile_card.toolTip())
        )
        self._diag_card.setAccessibleName(
            self._metric_card_accessible_name(
                "Diagnostics",
                self._diagnostic_metric_summary(error_count, warning_count, info_count),
                self._diag_card.toolTip(),
            )
        )
        self._preview_card.setAccessibleName(
            self._metric_card_accessible_name("Preview", self._preview_value.text(), preview_hint)
        )
        self._selection_card.setAccessibleName(
            self._metric_card_accessible_name(
                "Selection",
                self._selection_metric_summary(selection_total),
                self._selection_card.toolTip(),
            )
        )
        self._dirty_card.setAccessibleName(
            self._metric_card_accessible_name(
                "Dirty Pages",
                self._dirty_metric_summary(dirty_count),
                self._dirty_card.toolTip(),
            )
        )
        self._diag_btn.setAccessibleName(
            self._action_button_accessible_name(
                "open_diagnostics",
                self._diag_btn.text(),
                hint=diag_hint,
            )
        )
        self._history_btn.setAccessibleName(
            self._action_button_accessible_name(
                "open_history",
                self._history_btn.text(),
                hint=history_hint,
            )
        )
        self._debug_btn.setAccessibleName(
            self._action_button_accessible_name(
                "open_debug",
                self._debug_btn.text(),
                hint=debug_hint,
            )
        )
        self._project_btn.setAccessibleName(
            self._action_button_accessible_name(
                "open_project_panel",
                self._project_btn.text(),
                hint=project_hint,
            )
        )
        self._structure_btn.setAccessibleName(
            self._action_button_accessible_name(
                "open_structure_panel",
                self._structure_btn.text(),
                hint=structure_hint,
            )
        )
        (
            self._suggested_action_key,
            suggested_label,
            suggested_context,
            suggested_icon,
            suggested_hint,
        ) = self._suggested_action_state(
            sdk_ready=sdk_ready,
            can_compile=can_compile,
            dirty_count=dirty_count,
            selection_total=selection_total,
            error_count=error_count,
            warning_count=warning_count,
            info_count=info_count,
            runtime_text=runtime_text,
        )
        self._suggested_action_label.setText(self._suggested_action_title_text(suggested_context))
        self._set_hint(self._suggested_action_label, self._suggested_action_title_tooltip(suggested_context, suggested_hint))
        self._suggested_action_label.setAccessibleName(
            self._suggested_action_title_accessible_name(
                suggested_context,
                suggested_label,
                suggested_hint,
            )
        )
        self._suggested_action_button.setText(suggested_label)
        self._set_widget_icon(self._suggested_action_button, suggested_icon)
        self._suggested_action_button.setAccessibleName(
            self._suggested_action_button_accessible_name(
                suggested_context,
                suggested_label,
                suggested_hint,
            )
        )
        self._set_hint(self._suggested_action_button, suggested_hint)
        suggested_summary = self._suggested_action_summary_text(suggested_context, suggested_hint)
        self._suggested_action_summary_label.setText(suggested_summary)
        self._set_hint(self._suggested_action_summary_label, suggested_summary)
        self._suggested_action_summary_label.setAccessibleName(
            self._summary_accessible_name("Suggested action guidance", suggested_summary)
        )
        workspace_chip_label, workspace_chip_tone = self._workspace_chip_state(
            sdk_ready=sdk_ready,
            can_compile=can_compile,
            dirty_count=dirty_count,
            selection_total=selection_total,
            error_count=error_count,
            warning_count=warning_count,
            info_count=info_count,
            runtime_text=runtime_text,
        )
        self._header_title.setText(self._header_title_text(suggested_context))
        self._set_hint(
            self._header_title,
            self._header_title_tooltip(suggested_context, workspace_chip_label),
        )
        self._header_title.setAccessibleName(
            self._header_title_accessible_name(suggested_context, workspace_chip_label)
        )
        header_subtitle = self._header_subtitle_text(workspace_chip_label, suggested_label)
        self._header_subtitle.setText(header_subtitle)
        self._set_hint(
            self._header_subtitle,
            self._header_subtitle_tooltip(workspace_chip_label, suggested_hint),
        )
        self._header_subtitle.setAccessibleName(
            self._header_subtitle_accessible_name(
                workspace_chip_label,
                suggested_label,
                suggested_hint,
            )
        )
        self._set_chip_text(self._workspace_chip, workspace_chip_label, workspace_chip_tone)
        self._set_widget_icon(self._workspace_chip, suggested_icon, size=16)
        self._workspace_chip.setAccessibleName(
            self._workspace_chip_accessible_name(
                workspace_chip_label,
                suggested_label,
                suggested_hint,
            )
        )
        self._set_hint(self._workspace_chip, f"{workspace_chip_label}. {suggested_hint}")
        self._workspace_chip.setVisible(workspace_chip_label != "Ready")
        workspace_summary = self._workspace_summary_text(
            sdk_ready,
            can_compile,
            dirty_count,
            selection_total,
            preview_text,
            diag_total,
            runtime_text,
            suggested_label,
        )
        self._workspace_summary_label.setText(workspace_summary)
        self._set_hint(self._workspace_summary_label, workspace_summary)
        self._workspace_summary_label.setAccessibleName(
            self._summary_accessible_name("Workspace summary", workspace_summary)
        )
        is_workspace_fully_ready = (
            sdk_ready
            and can_compile
            and dirty_count <= 0
            and selection_total <= 0
            and diag_total <= 0
            and not runtime_text
        )
        self._workspace_summary_label.setVisible(not is_workspace_fully_ready)
        show_health_rows = diag_total > 0
        self._error_row.setVisible(show_health_rows)
        self._warning_row.setVisible(show_health_rows)
        self._info_row.setVisible(show_health_rows)
        self._set_hint(self._error_row, f"Open Errors. {self._active_count_hint(error_count, 'error', 'errors')}")
        self._set_hint(self._warning_row, f"Open Warnings. {self._active_count_hint(warning_count, 'warning', 'warnings')}")
        self._set_hint(self._info_row, f"Open Info. {self._active_count_hint(info_count, 'info item', 'info items')}")
        self._error_row.setAccessibleName(
            self._health_row_accessible_name(
                "Errors",
                self._error_value.text(),
                "No errors active" if error_count <= 0 else "",
            )
        )
        self._warning_row.setAccessibleName(
            self._health_row_accessible_name(
                "Warnings",
                self._warning_value.text(),
                "No warnings active" if warning_count <= 0 else "",
            )
        )
        self._info_row.setAccessibleName(
            self._health_row_accessible_name(
                "Info",
                self._info_value.text(),
                "No info items active" if info_count <= 0 else "",
            )
        )
        self._set_hint(self._error_value, "Errors: " + self._error_value.text())
        self._set_hint(self._warning_value, "Warnings: " + self._warning_value.text())
        self._set_hint(self._info_value, "Info: " + self._info_value.text())
        self._error_value.setAccessibleName(f"Errors value: {self._error_value.text()}")
        self._warning_value.setAccessibleName(f"Warnings value: {self._warning_value.text()}")
        self._info_value.setAccessibleName(f"Info value: {self._info_value.text()}")
        error_share = self._health_share_summary("Errors", self._error_value.text(), diag_total)
        warning_share = self._health_share_summary("Warnings", self._warning_value.text(), diag_total)
        info_share = self._health_share_summary("Info", self._info_value.text(), diag_total)
        self._set_hint(self._error_bar, error_share)
        self._set_hint(self._warning_bar, warning_share)
        self._set_hint(self._info_bar, info_share)
        self._error_bar.setAccessibleName(error_share)
        self._warning_bar.setAccessibleName(warning_share)
        self._info_bar.setAccessibleName(info_share)
        self._health_title.setText(self._diagnostic_title_text(diag_total))
        self._set_hint(self._health_title, self._diagnostic_title_tooltip(diag_total))
        self._health_title.setAccessibleName(self._diagnostic_title_accessible_name(diag_total))
        health_summary = self._diagnostic_summary_text(error_count, warning_count, info_count)
        self._health_summary_label.setText(health_summary)
        self._health_summary_label.setVisible(diag_total > 0)
        self._set_hint(self._health_summary_label, health_summary)
        self._health_summary_label.setAccessibleName(
            self._summary_accessible_name("Diagnostic summary", health_summary)
        )
        if error_count > 0:
            self._health_chip_action = "open_error_diagnostics"
            self._set_chip_text(self._health_chip, self._counted_label("Critical", error_count), "danger")
            health_hint = f"Open Errors. {self._active_count_hint(error_count, 'error', 'errors')}"
        elif warning_count > 0:
            self._health_chip_action = "open_warning_diagnostics"
            self._set_chip_text(self._health_chip, self._counted_label("Attention", warning_count), "warning")
            health_hint = f"Open Warnings. {self._active_count_hint(warning_count, 'warning', 'warnings')}"
        elif info_count > 0:
            self._health_chip_action = "open_info_diagnostics"
            self._set_chip_text(self._health_chip, self._counted_label("Info", info_count), "accent")
            health_hint = f"Open Info. {self._active_count_hint(info_count, 'info item', 'info items')}"
        else:
            self._health_chip_action = "open_diagnostics"
            self._set_chip_text(self._health_chip, "Stable", "success")
            health_hint = "Open Diagnostics. No active diagnostics."
        self._set_widget_icon(self._health_chip, self._action_icon_key(self._health_chip_action), size=16)
        self._set_hint(self._health_chip, health_hint)
        self._health_chip.setAccessibleName(
            self._health_chip_accessible_name(self._health_chip.text(), health_hint)
        )
        self._health_chip.setVisible(diag_total > 0)
        show_error_jump = error_count > 0
        show_warning_jump = warning_count > 0
        self._diagnostic_jump_host.setVisible(show_error_jump or show_warning_jump)
        self._first_error_btn.setVisible(show_error_jump)
        self._first_warning_btn.setVisible(show_warning_jump)
        self._first_error_btn.setEnabled(show_error_jump)
        self._first_error_btn.setText(
            f"Open First Error ({error_count})" if error_count > 0 else "Open First Error"
        )
        first_error_hint = (
            "Jump to the first error in Diagnostics. "
            f"{self._active_count_hint(error_count, 'error', 'errors')}"
            if error_count > 0
            else "No errors are active."
        )
        self._set_hint(
            self._first_error_btn,
            first_error_hint,
        )
        self._first_error_btn.setAccessibleName(
            self._action_button_accessible_name(
                "open_first_error",
                self._first_error_btn.text(),
                error_count > 0,
                hint=first_error_hint,
            )
        )
        self._first_warning_btn.setEnabled(show_warning_jump)
        self._first_warning_btn.setText(
            f"Open First Warning ({warning_count})" if warning_count > 0 else "Open First Warning"
        )
        first_warning_hint = (
            "Jump to the first warning in Diagnostics. "
            f"{self._active_count_hint(warning_count, 'warning', 'warnings')}"
            if warning_count > 0
            else "No warnings are active."
        )
        self._set_hint(
            self._first_warning_btn,
            first_warning_hint,
        )
        self._first_warning_btn.setAccessibleName(
            self._action_button_accessible_name(
                "open_first_warning",
                self._first_warning_btn.text(),
                warning_count > 0,
                hint=first_warning_hint,
            )
        )
        if runtime_text:
            self._runtime_title.setText(self._runtime_title_text(runtime_text))
            self._set_hint(self._runtime_title, self._runtime_title_tooltip(runtime_text))
            self._runtime_title.setAccessibleName(self._runtime_title_accessible_name(runtime_text))
            self._runtime_label.setVisible(True)
            self._runtime_label.setText(runtime_text)
            self._set_hint(self._runtime_label, runtime_text)
            self._runtime_label.setAccessibleName(f"Runtime details: {runtime_text}")
            self._runtime_panel.setAccessibleName(self._runtime_panel_accessible_name(runtime_text))
            self._set_chip_text(self._runtime_chip, "Issue", "danger")
            self._set_widget_icon(self._runtime_chip, "debug", size=16)
            self._set_hint(self._runtime_chip, f"Open Debug Output. Runtime issue: {runtime_text}")
            self._runtime_chip.setAccessibleName(self._runtime_chip_accessible_name(runtime_text))
            self._runtime_chip.setVisible(True)
            self._set_hint(self._runtime_panel, f"Open Debug Output. Runtime issue: {runtime_text}")
        else:
            self._runtime_title.setText(self._runtime_title_text(""))
            self._set_hint(self._runtime_title, self._runtime_title_tooltip(""))
            self._runtime_title.setAccessibleName(self._runtime_title_accessible_name(""))
            self._runtime_label.setVisible(False)
            self._runtime_label.setText("No runtime errors.")
            self._set_hint(self._runtime_label, "No runtime errors.")
            self._runtime_label.setAccessibleName("Runtime details: No runtime errors.")
            self._runtime_panel.setAccessibleName(self._runtime_panel_accessible_name(""))
            self._set_chip_text(self._runtime_chip, "Clear", "success")
            self._set_widget_icon(self._runtime_chip, "debug", size=16)
            self._set_hint(self._runtime_chip, "Open Debug Output. No runtime errors.")
            self._runtime_chip.setAccessibleName(self._runtime_chip_accessible_name(""))
            self._runtime_chip.setVisible(False)
            self._set_hint(self._runtime_panel, "Open Debug Output. No runtime errors.")
        self._status_snapshot = status_snapshot
        self._status_snapshot_initialized = True
