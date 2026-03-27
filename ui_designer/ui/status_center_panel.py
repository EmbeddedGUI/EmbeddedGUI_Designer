"""Status center panel for workspace health and quick actions."""

from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget

from .iconography import make_icon


class StatusCenterPanel(QWidget):
    """Workspace status dashboard with quick-open actions."""

    action_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._last_action = ""
        self._init_ui()
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
        self._sdk_value = self._create_metric(metrics_layout, 0, 0, "SDK", "SDK Missing", "assets")
        self._compile_value = self._create_metric(metrics_layout, 0, 1, "Compile", "Unavailable", "compile")
        self._diag_value = self._create_metric(metrics_layout, 1, 0, "Diagnostics", "0 errors", "diagnostics")
        self._preview_value = self._create_metric(metrics_layout, 1, 1, "Preview", "Preview Idle", "debug")
        self._selection_value = self._create_metric(metrics_layout, 2, 0, "Selection", "0 widgets", "structure")
        self._dirty_value = self._create_metric(metrics_layout, 2, 1, "Dirty Pages", "0", "history")
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
        self._health_chip = QLabel("Stable")
        self._health_chip.setObjectName("workspace_status_chip")
        self._health_chip.setProperty("chipTone", "success")
        health_title_row.addStretch()
        health_title_row.addWidget(self._health_chip)
        health_layout.addLayout(health_title_row)

        self._error_value, self._error_bar = self._create_health_row(health_layout, "Errors", "diagnostics", "status_center_health_error_bar")
        self._warning_value, self._warning_bar = self._create_health_row(health_layout, "Warnings", "history", "status_center_health_warning_bar")
        self._info_value, self._info_bar = self._create_health_row(health_layout, "Info", "debug", "status_center_health_info_bar")
        layout.addWidget(health)

        quick_actions = QFrame()
        quick_actions.setObjectName("status_center_actions")
        quick_layout = QVBoxLayout(quick_actions)
        quick_layout.setContentsMargins(12, 12, 12, 12)
        quick_layout.setSpacing(8)

        actions_title = QLabel("Quick Actions")
        actions_title.setObjectName("workspace_section_title")
        quick_layout.addWidget(actions_title)

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

        runtime = QFrame()
        runtime.setObjectName("status_center_runtime")
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
        layout.addWidget(runtime)

        layout.addStretch()

    def _create_metric(self, grid_layout, row, col, label, value, icon_key):
        card = QFrame()
        card.setObjectName("status_center_metric_card")
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
        return value_label

    def _create_health_row(self, host_layout, label, icon_key, bar_object_name):
        row = QFrame()
        row.setObjectName("status_center_health_row")
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
        return value_label, bar

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

    def _emit_action(self, action_key):
        self._last_action = action_key
        self.action_requested.emit(action_key)

    def view_state(self):
        return {"last_action": self._last_action}

    def restore_view_state(self, state):
        if not isinstance(state, dict):
            self._last_action = ""
            return
        self._last_action = str(state.get("last_action", "") or "")

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
            self._set_chip_text(self._health_chip, "Critical", "danger")
        elif warning_count > 0:
            self._set_chip_text(self._health_chip, "Attention", "warning")
        else:
            self._set_chip_text(self._health_chip, "Stable", "success")
        self._first_error_btn.setEnabled(int(diagnostics_errors or 0) > 0)
        self._first_warning_btn.setEnabled(int(diagnostics_warnings or 0) > 0)
        runtime_text = str(runtime_error or "").strip()
        if runtime_text:
            self._runtime_label.setText(runtime_text)
        else:
            self._runtime_label.setText("No runtime errors.")
