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
        "open_components_panel": "Components",
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

    def __init__(self, parent=None):
        super().__init__(parent)
        self._last_action = ""
        self._recent_actions = []
        self._health_chip_action = "open_diagnostics"
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

        title = QLabel("Status Center")
        title.setObjectName("workspace_section_title")
        header_layout.addWidget(title)

        subtitle = QLabel("Monitor diagnostics, preview runtime, and jump to key tooling quickly.")
        subtitle.setObjectName("workspace_section_subtitle")
        subtitle.setWordWrap(True)
        header_layout.addWidget(subtitle)
        layout.addWidget(header)

        metrics = QFrame()
        metrics.setObjectName("status_center_metrics")
        metrics_layout = QGridLayout(metrics)
        metrics_layout.setContentsMargins(10, 10, 10, 10)
        metrics_layout.setHorizontalSpacing(10)
        metrics_layout.setVerticalSpacing(10)
        self._sdk_value, self._sdk_card = self._create_metric(
            metrics_layout, 0, 0, "SDK", "SDK Missing", "assets", "open_project_panel"
        )
        self._compile_value, self._compile_card = self._create_metric(
            metrics_layout, 0, 1, "Compile", "Unavailable", "compile", "open_debug"
        )
        self._diag_value, self._diag_card = self._create_metric(
            metrics_layout, 1, 0, "Diagnostics", "0 errors", "diagnostics", "open_diagnostics"
        )
        self._preview_value, self._preview_card = self._create_metric(
            metrics_layout, 1, 1, "Preview", "Preview Idle", "debug", "open_debug"
        )
        self._selection_value, self._selection_card = self._create_metric(
            metrics_layout, 2, 0, "Selection", "0 widgets", "structure", "open_structure_panel"
        )
        self._dirty_value, self._dirty_card = self._create_metric(
            metrics_layout, 2, 1, "Dirty Pages", "0", "history", "open_history"
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
        health_title = QLabel("Diagnostic Mix")
        health_title.setObjectName("workspace_section_title")
        health_title_row.addWidget(health_title)
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
        layout.addWidget(health)

        quick_actions = QFrame()
        quick_actions.setObjectName("status_center_actions")
        quick_layout = QVBoxLayout(quick_actions)
        quick_layout.setContentsMargins(12, 12, 12, 12)
        quick_layout.setSpacing(8)

        actions_title = QLabel("Quick Actions")
        actions_title.setObjectName("workspace_section_title")
        quick_layout.addWidget(actions_title)
        last_action_row = QHBoxLayout()
        last_action_row.setContentsMargins(0, 0, 0, 0)
        last_action_row.setSpacing(8)
        self._last_action_label = QLabel("Last action: None")
        self._last_action_label.setObjectName("workspace_section_subtitle")
        last_action_row.addWidget(self._last_action_label, 1)
        self._repeat_action_menu = QMenu(self)
        self._repeat_action_button = QToolButton()
        self._repeat_action_button.setIcon(make_icon("history"))
        self._repeat_action_button.setPopupMode(QToolButton.MenuButtonPopup)
        self._repeat_action_button.setMenu(self._repeat_action_menu)
        self._repeat_action_button.setEnabled(False)
        self._repeat_action_button.clicked.connect(self._repeat_last_action)
        last_action_row.addWidget(self._repeat_action_button, 0)
        quick_layout.addLayout(last_action_row)

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

        row2 = QHBoxLayout()
        row2.setContentsMargins(0, 0, 0, 0)
        row2.setSpacing(8)
        self._first_error_btn = self._build_action_button("Open First Error", "diagnostics", "open_first_error")
        self._first_warning_btn = self._build_action_button("Open First Warning", "diagnostics", "open_first_warning")
        row2.addWidget(self._first_error_btn)
        row2.addWidget(self._first_warning_btn)
        row2.addStretch()
        quick_layout.addLayout(row2)

        row3 = QHBoxLayout()
        row3.setContentsMargins(0, 0, 0, 0)
        row3.setSpacing(8)
        self._project_btn = self._build_action_button("Project", "project", "open_project_panel")
        self._structure_btn = self._build_action_button("Structure", "structure", "open_structure_panel")
        self._components_btn = self._build_action_button("Components", "widgets", "open_components_panel")
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
        runtime.setToolTip("Open Debug Output")
        runtime.setAccessibleName("Runtime section")
        runtime_layout = QVBoxLayout(runtime)
        runtime_layout.setContentsMargins(12, 12, 12, 12)
        runtime_layout.setSpacing(6)
        runtime_title = QLabel("Runtime")
        runtime_title.setObjectName("workspace_section_title")
        runtime_layout.addWidget(runtime_title)
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
            card.setToolTip(f"Open {label}")
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
        card_layout.addWidget(value_label)
        grid_layout.addWidget(card, row, col)
        return value_label, card

    def _create_health_row(self, host_layout, label, icon_key, bar_object_name, action_key=""):
        row = _ClickableFrame() if action_key else QFrame()
        row.setObjectName("status_center_health_row")
        if action_key:
            row.clicked.connect(lambda key=action_key: self._emit_action(key))
            row.setToolTip(f"Open {label}")
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
        top.addWidget(value_label, 0, Qt.AlignRight)
        row_layout.addLayout(top)

        bar = QProgressBar()
        bar.setObjectName(bar_object_name)
        bar.setTextVisible(False)
        bar.setRange(0, 100)
        bar.setValue(0)
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

    def _build_action_button(self, text, icon_key, action_key):
        button = QPushButton(text)
        button.setIcon(make_icon(icon_key))
        button.clicked.connect(lambda checked=False, key=action_key: self._emit_action(key))
        return button

    def _action_label(self, action_key):
        action = str(action_key or "").strip()
        if not action:
            return "None"
        return self._ACTION_LABELS.get(action, action.replace("_", " ").title())

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
            empty_action = self._repeat_action_menu.addAction("No recent actions")
            empty_action.setEnabled(False)
            return
        for action_key in self._recent_actions:
            action_label = self._action_label(action_key)
            menu_action = self._repeat_action_menu.addAction(action_label)
            menu_action.setToolTip(f"Replay {action_label}")
            menu_action.triggered.connect(lambda checked=False, key=action_key: self._emit_action(key))
        self._repeat_action_menu.addSeparator()
        clear_action = self._repeat_action_menu.addAction("Clear Recent Actions")
        clear_action.setToolTip("Forget the recent status center actions.")
        clear_action.triggered.connect(self._clear_recent_actions)

    def _set_last_action(self, action_key, recent_actions=None):
        self._last_action = str(action_key or "").strip()
        self._recent_actions = self._normalize_recent_actions(
            self._recent_actions if recent_actions is None else recent_actions,
            prepend_action=self._last_action,
        )
        action_label = self._action_label(self._last_action)
        self._last_action_label.setText(f"Last action: {action_label}")
        has_action = bool(self._last_action)
        self._repeat_action_button.setEnabled(has_action)
        self._repeat_action_button.setText(f"Repeat {action_label}" if has_action else "Repeat Action")
        self._repeat_action_button.setToolTip(
            f"Repeat {action_label}" if has_action else "No recent action to repeat."
        )
        self._refresh_repeat_action_menu()

    def _repeat_last_action(self):
        if not self._last_action:
            return
        self._emit_action(self._last_action)

    def _clear_recent_actions(self):
        self._set_last_action("", [])

    def _open_health_chip_target(self):
        self._emit_action(self._health_chip_action or "open_diagnostics")

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
        preview_label="Preview Idle",
        diagnostics_errors=0,
        diagnostics_warnings=0,
        diagnostics_infos=0,
        runtime_error="",
    ):
        self._sdk_value.setText("SDK Ready" if sdk_ready else "SDK Missing")
        self._compile_value.setText("Available" if can_compile else "Unavailable")
        self._dirty_value.setText(str(max(int(dirty_pages or 0), 0)))
        self._selection_value.setText(f"{max(int(selection_count or 0), 0)} widgets")
        self._preview_value.setText(str(preview_label or "Preview Idle"))
        self._diag_value.setText(
            f"{max(int(diagnostics_errors or 0), 0)} errors, "
            f"{max(int(diagnostics_warnings or 0), 0)} warnings, "
            f"{max(int(diagnostics_infos or 0), 0)} info"
        )
        error_count = max(int(diagnostics_errors or 0), 0)
        warning_count = max(int(diagnostics_warnings or 0), 0)
        info_count = max(int(diagnostics_infos or 0), 0)
        total = max(error_count + warning_count + info_count, 1)
        self._error_value.setText(str(error_count))
        self._warning_value.setText(str(warning_count))
        self._info_value.setText(str(info_count))
        self._error_bar.setValue(int(round((error_count * 100.0) / total)))
        self._warning_bar.setValue(int(round((warning_count * 100.0) / total)))
        self._info_bar.setValue(int(round((info_count * 100.0) / total)))
        if error_count > 0:
            self._health_chip_action = "open_error_diagnostics"
            self._set_chip_text(self._health_chip, "Critical", "danger")
        elif warning_count > 0:
            self._health_chip_action = "open_warning_diagnostics"
            self._set_chip_text(self._health_chip, "Attention", "warning")
        elif info_count > 0:
            self._health_chip_action = "open_info_diagnostics"
            self._set_chip_text(self._health_chip, "Info", "accent")
        else:
            self._health_chip_action = "open_diagnostics"
            self._set_chip_text(self._health_chip, "Stable", "success")
        self._health_chip.setToolTip(f"Open {self._action_label(self._health_chip_action)}")
        self._first_error_btn.setEnabled(int(diagnostics_errors or 0) > 0)
        self._first_warning_btn.setEnabled(int(diagnostics_warnings or 0) > 0)
        runtime_text = str(runtime_error or "").strip()
        if runtime_text:
            self._runtime_label.setText(runtime_text)
        else:
            self._runtime_label.setText("No runtime errors.")
