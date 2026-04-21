"""Debug output panel for EmbeddedGUI Designer."""

import datetime

from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QLabel,
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QTextCharFormat, QColor

from .theme import designer_font_size_pt, designer_monospace_font, theme_tokens


_TOKENS = theme_tokens("dark")
_SPACE_XS = int(_TOKENS.get("space_xs", 4))
_SPACE_SM = int(_TOKENS.get("space_sm", 8))
_SPACE_MD = int(_TOKENS.get("space_md", 12))
_DEFAULT_DEBUG_FONT_PT = 9


def _debug_font_size_pt():
    return designer_font_size_pt(QApplication.instance(), default=_DEFAULT_DEBUG_FONT_PT)



def _set_widget_metadata(widget, *, tooltip=None, accessible_name=None):
    if tooltip is not None:
        hint = str(tooltip or "")
        if str(widget.property("_debug_panel_hint_snapshot") or "") != hint:
            widget.setToolTip(hint)
            widget.setStatusTip(hint)
            widget.setProperty("_debug_panel_hint_snapshot", hint)
    if accessible_name is not None:
        name = str(accessible_name or "")
        if str(widget.property("_debug_panel_accessible_snapshot") or "") != name:
            widget.setAccessibleName(name)
            widget.setProperty("_debug_panel_accessible_snapshot", name)


class DebugPanel(QWidget):
    """Panel for displaying compile output and debug information."""

    rebuild_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rebuild_action_visible = False
        self._rebuild_action_enabled = False
        self._rebuild_button_tooltip = ""
        self._rebuild_button_accessible_name = ""
        self._init_ui()
        self._update_accessibility_summary("No output yet.")

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self._header_frame = QFrame()
        self._header_frame.setObjectName("debug_panel_header")
        self._header_frame.setProperty("panelTone", "runtime")
        header_layout = QVBoxLayout(self._header_frame)
        header_layout.setContentsMargins(6, _SPACE_XS, 6, _SPACE_XS)
        header_layout.setSpacing(_SPACE_XS)

        self._header_eyebrow = QLabel("Runtime")
        self._header_eyebrow.setObjectName("debug_panel_eyebrow")
        header_layout.addWidget(self._header_eyebrow)
        self._header_eyebrow.hide()

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(2)

        self._title_label = QLabel("Debug")
        self._title_label.setObjectName("workspace_section_title")
        self._title_label.setAccessibleName("Debug Output")
        title_row.addWidget(self._title_label)

        title_row.addStretch(1)

        self._line_count_chip = QLabel("0 lines")
        self._line_count_chip.setObjectName("workspace_status_chip")
        self._line_count_chip.setProperty("chipTone", "accent")
        title_row.addWidget(self._line_count_chip, 0, Qt.AlignVCenter)

        self._stream_state_chip = QLabel("Idle")
        self._stream_state_chip.setObjectName("workspace_status_chip")
        self._stream_state_chip.setProperty("chipTone", "success")
        title_row.addWidget(self._stream_state_chip, 0, Qt.AlignVCenter)
        header_layout.addLayout(title_row)

        self._meta_label = QLabel("No output yet.")
        self._meta_label.setObjectName("debug_panel_header_meta")
        self._meta_label.setWordWrap(True)
        header_layout.addWidget(self._meta_label)
        self._meta_label.hide()
        self._line_count_chip.hide()
        self._stream_state_chip.hide()

        self._controls_strip = QFrame()
        self._controls_strip.setObjectName("debug_panel_controls_strip")
        controls_layout = QHBoxLayout(self._controls_strip)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(2)

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.clicked.connect(self.clear)
        controls_layout.addWidget(self._clear_btn)

        self._rebuild_btn = QPushButton("Rebuild Project")
        self._rebuild_btn.clicked.connect(self.rebuild_requested.emit)
        self._rebuild_btn.hide()
        controls_layout.addWidget(self._rebuild_btn)

        controls_layout.addStretch(1)
        header_layout.addWidget(self._controls_strip)

        layout.addWidget(self._header_frame)

        # Output text area
        self._output = QPlainTextEdit()
        self._output.setObjectName("debug_output_surface")
        self._output.setReadOnly(True)
        self._output.setFont(designer_monospace_font(point_size=_debug_font_size_pt()))
        self._output.setLineWrapMode(QPlainTextEdit.NoWrap)
        self._output.setMaximumBlockCount(5000)  # Limit lines
        layout.addWidget(self._output)

        # Formats for different message types
        self._error_format = QTextCharFormat()
        self._error_format.setForeground(QColor("#ff6b6b"))

        self._success_format = QTextCharFormat()
        self._success_format.setForeground(QColor("#69db7c"))

        self._info_format = QTextCharFormat()
        self._info_format.setForeground(QColor("#a0a0a0"))

        self._action_format = QTextCharFormat()
        self._action_format.setForeground(QColor("#74c0fc"))

        self._cmd_format = QTextCharFormat()
        self._cmd_format.setForeground(QColor("#ffd43b"))

    def _current_last_message(self):
        lines = self._output.toPlainText().splitlines()
        if not lines:
            return "No output yet."
        return lines[-1]

    def set_rebuild_action_state(self, *, visible=False, enabled=False, tooltip="", accessible_name=""):
        self._rebuild_action_visible = bool(visible)
        self._rebuild_action_enabled = bool(enabled) and self._rebuild_action_visible
        self._rebuild_button_tooltip = str(tooltip or "")
        self._rebuild_button_accessible_name = str(accessible_name or "")
        self._rebuild_btn.setVisible(self._rebuild_action_visible)
        self._rebuild_btn.setEnabled(self._rebuild_action_enabled)
        self._update_accessibility_summary(self._current_last_message())

    def is_rebuild_action_visible(self):
        return bool(self._rebuild_action_visible)

    def _update_accessibility_summary(self, last_message):
        lines = self._output.toPlainText().splitlines()
        line_count = len(lines)
        line_label = f"{line_count} line" if line_count == 1 else f"{line_count} lines"
        last_summary = str(last_message or "").strip() or "blank line"
        summary = f"Debug output: {line_label}. Last message: {last_summary}"
        meta_text = (
            "No output yet. Compile, preview, and bridge logs will appear here."
            if line_count == 0
            else f"Showing {line_label}. Last message: {last_summary}."
        )
        stream_state = "Idle" if line_count == 0 else "Captured Output"
        self._line_count_chip.setText(line_label)
        self._stream_state_chip.setText(stream_state)
        self._stream_state_chip.setProperty("chipTone", "success" if line_count == 0 else "warning")
        self._stream_state_chip.style().unpolish(self._stream_state_chip)
        self._stream_state_chip.style().polish(self._stream_state_chip)
        if self._meta_label.text() != meta_text:
            self._meta_label.setText(meta_text)
        _set_widget_metadata(self, tooltip=summary, accessible_name=summary)
        _set_widget_metadata(
            self._header_frame,
            tooltip=summary,
            accessible_name=f"Debug output header. {summary}",
        )
        _set_widget_metadata(
            self._header_eyebrow,
            tooltip="Runtime console workspace surface.",
            accessible_name="Runtime console workspace surface.",
        )
        _set_widget_metadata(
            self._title_label,
            tooltip=summary,
            accessible_name=f"Debug output title: {line_label}",
        )
        _set_widget_metadata(
            self._meta_label,
            tooltip=meta_text,
            accessible_name=f"Debug output summary: {meta_text}",
        )
        _set_widget_metadata(
            self._line_count_chip,
            tooltip=f"Debug output lines: {line_label}.",
            accessible_name=f"Debug output lines: {line_label}.",
        )
        _set_widget_metadata(
            self._stream_state_chip,
            tooltip=f"Debug output state: {stream_state}.",
            accessible_name=f"Debug output state: {stream_state}.",
        )
        _set_widget_metadata(
            self._output,
            tooltip=summary,
            accessible_name=f"Debug output log: {line_label}. Last message: {last_summary}",
        )
        if line_count == 0:
            clear_tooltip = "Debug output is already clear."
            clear_accessible_name = "Clear debug output unavailable"
        else:
            clear_tooltip = f"Clear {line_label} of debug output."
            clear_accessible_name = f"Clear debug output: {line_label}"
        _set_widget_metadata(
            self._clear_btn,
            tooltip=clear_tooltip,
            accessible_name=clear_accessible_name,
        )
        controls_summary = f"Debug output actions. {line_label}."
        if self._rebuild_action_visible:
            rebuild_tooltip = self._rebuild_button_tooltip or "Clean and rebuild the EGUI project."
            if self._rebuild_action_enabled:
                rebuild_accessible_name = self._rebuild_button_accessible_name or "Rebuild EGUI project from debug output"
                controls_summary += " Recovery rebuild available."
            else:
                rebuild_accessible_name = (
                    self._rebuild_button_accessible_name
                    or "Rebuild EGUI project from debug output unavailable"
                )
                controls_summary += " Recovery rebuild unavailable."
            _set_widget_metadata(
                self._rebuild_btn,
                tooltip=rebuild_tooltip,
                accessible_name=rebuild_accessible_name,
            )
        _set_widget_metadata(
            self._controls_strip,
            tooltip=controls_summary,
            accessible_name=controls_summary,
        )

    def _timestamp(self):
        """Get current timestamp string with milliseconds."""
        return datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]

    def clear(self):
        """Clear all output."""
        self._output.clear()
        self._update_accessibility_summary("No output yet.")

    def get_output_font(self):
        """Get the current font used in the debug output."""
        return self._output.font()

    def set_output_font_size(self, pixel_size):
        """Set the debug output font size (pixels)."""
        font = self._output.font()
        font.setPixelSize(int(pixel_size))
        self._output.setFont(font)

    def set_output_font_size_pt(self, point_size):
        """Set the debug output font size (points)."""
        font = self._output.font()
        font.setPointSize(int(point_size))
        self._output.setFont(font)

    def append_text(self, text, msg_type="info"):
        """Append text to the output.

        Args:
            text: Text to append
            msg_type: "info", "error", "success", "action", or "cmd"
        """
        text = str(text or "")
        cursor = self._output.textCursor()
        cursor.movePosition(cursor.End)

        fmt = self._info_format
        if msg_type == "error":
            fmt = self._error_format
        elif msg_type == "success":
            fmt = self._success_format
        elif msg_type == "action":
            fmt = self._action_format
        elif msg_type == "cmd":
            fmt = self._cmd_format

        cursor.insertText(text + "\n", fmt)

        # Auto-scroll to bottom
        self._output.setTextCursor(cursor)
        self._output.ensureCursorVisible()
        self._update_accessibility_summary(text)

    def log(self, message, msg_type="info"):
        """Log a message with timestamp.

        Args:
            message: Message to log
            msg_type: "info", "error", "success", "action", or "cmd"
        """
        self.append_text(f"[{self._timestamp()}] {message}", msg_type)

    def log_action(self, action):
        """Log an action (e.g., 'Starting compile...')."""
        self.log(action, "action")

    def log_cmd(self, cmd):
        """Log a command being executed."""
        self.log(f"$ {cmd}", "cmd")

    def log_success(self, message):
        """Log a success message."""
        self.log(message, "success")

    def log_error(self, message):
        """Log an error message."""
        self.log(message, "error")

    def log_info(self, message):
        """Log an info message."""
        self.log(message, "info")

    def log_compile_output(self, success, output):
        """Log compile output with appropriate formatting.

        Args:
            success: Whether compilation succeeded
            output: Full compile output text
        """
        self.append_text("")

        if success:
            self.append_text("=== Compilation Successful ===", "success")
        else:
            self.append_text("=== Compilation Failed ===", "error")

        self.append_text("")

        # Add output lines
        for line in output.split("\n"):
            if not line.strip():
                continue

            # Detect error/warning lines
            line_lower = line.lower()
            if "error:" in line_lower or "error " in line_lower:
                self.append_text(line, "error")
            elif "warning:" in line_lower:
                self.append_text(line, "info")
            else:
                self.append_text(line, "info")
