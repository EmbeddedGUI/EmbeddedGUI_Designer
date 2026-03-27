"""Status center panel for workspace health and quick actions."""

from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

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
        self._first_error_btn.setEnabled(int(diagnostics_errors or 0) > 0)
        self._first_warning_btn.setEnabled(int(diagnostics_warnings or 0) > 0)
        runtime_text = str(runtime_error or "").strip()
        if runtime_text:
            self._runtime_label.setText(runtime_text)
        else:
            self._runtime_label.setText("No runtime errors.")
