"""Editor tabs panel — Design / Split / Code tri-view.

Mimics Android Studio's layout editor mode switching:
  - Design: visual drag-and-drop canvas (PreviewPanel)
  - Code:   XML source editor with syntax highlighting
  - Split:  side-by-side XML editor + live canvas preview

Bidirectional sync:
  Design → Code: model changes regenerate XML text
  Code → Design: XML edits parse back into model (debounced)
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QPlainTextEdit, QSplitter, QPushButton, QButtonGroup,
    QLabel, QFrame,
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QPalette

from .xml_highlighter import XmlSyntaxHighlighter
from .preview_panel import PreviewPanel


# Editor modes
MODE_DESIGN = "design"
MODE_SPLIT = "split"
MODE_CODE = "code"


def _set_widget_metadata(widget, *, tooltip=None, accessible_name=None):
    if tooltip is not None:
        widget.setToolTip(tooltip)
        widget.setStatusTip(tooltip)
    if accessible_name is not None:
        widget.setAccessibleName(accessible_name)


class XmlEditor(QPlainTextEdit):
    """Plain text editor styled for XML editing."""

    def __init__(self, parent=None):
        super().__init__(parent)
        font = QFont("Consolas", 10)
        font.setStyleHint(QFont.Monospace)
        self.setFont(font)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.setTabStopDistance(
            self.fontMetrics().horizontalAdvance(" ") * 4
        )
        # Dark theme
        pal = self.palette()
        pal.setColor(QPalette.Base, QColor("#1E1E1E"))
        pal.setColor(QPalette.Text, QColor("#D4D4D4"))
        self.setPalette(pal)
        # Syntax highlighter
        self._highlighter = XmlSyntaxHighlighter(self.document())
        _set_widget_metadata(
            self,
            tooltip="XML editor for the current page source.",
            accessible_name="XML editor",
        )


class EditorTabs(QWidget):
    """Tri-view editor: Design / Split / Code.

    Signals:
        xml_changed(str): emitted when user edits XML (debounced)
        mode_changed(str): emitted when view mode switches
    """

    xml_changed = pyqtSignal(str)   # debounced XML text from code editor
    mode_changed = pyqtSignal(str)  # MODE_DESIGN / MODE_SPLIT / MODE_CODE
    save_requested = pyqtSignal()    # Ctrl+S pressed in the XML editor

    def __init__(self, preview_panel, parent=None, show_mode_switch=True):
        super().__init__(parent)
        self._preview = preview_panel
        self._mode = MODE_DESIGN
        self._syncing = False  # prevent feedback loops
        self._show_mode_switch = bool(show_mode_switch)
        self._mode_toolbar = None
        self._mode_buttons = {}

        # Debounce timer for Code → Design sync
        self._parse_timer = QTimer()
        self._parse_timer.setSingleShot(True)
        self._parse_timer.setInterval(300)
        self._parse_timer.timeout.connect(self._emit_xml_changed)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Stacked content area
        self._stack = QStackedWidget()
        layout.addWidget(self._stack, 1)

        # ── Design view (index 0) ──
        self._design_container = QWidget()
        design_layout = QVBoxLayout(self._design_container)
        design_layout.setContentsMargins(0, 0, 0, 0)
        # PreviewPanel is passed in and reparented here
        design_layout.addWidget(self._preview)
        _set_widget_metadata(
            self._design_container,
            tooltip="Design surface showing the live preview.",
            accessible_name="Design editor surface",
        )
        self._stack.addWidget(self._design_container)

        # ── Code view (index 1) ──
        self._code_editor = XmlEditor()
        self._code_editor.textChanged.connect(self._on_code_text_changed)
        self._stack.addWidget(self._code_editor)

        # ── Split view (index 2) ──
        self._split_container = QWidget()
        split_layout = QVBoxLayout(self._split_container)
        split_layout.setContentsMargins(0, 0, 0, 0)
        self._split = QSplitter(Qt.Horizontal)
        self._split_editor = XmlEditor()
        self._split_editor.textChanged.connect(self._on_code_text_changed)
        self._split_preview_container = QWidget()
        # Split preview will hold a duplicate reference managed externally
        self._split.addWidget(self._split_editor)
        self._split.addWidget(self._split_preview_container)
        self._split.setSizes([400, 400])
        _set_widget_metadata(
            self._split,
            tooltip="Split editor with XML source and preview side by side.",
            accessible_name="Split editor layout",
        )
        _set_widget_metadata(
            self._split_preview_container,
            tooltip="Preview surface used while split mode is active.",
            accessible_name="Split preview surface",
        )
        split_layout.addWidget(self._split)
        self._stack.addWidget(self._split_container)

        # ── Mode switch toolbar (bottom) ──
        self._btn_group = None
        if self._show_mode_switch:
            toolbar = QFrame()
            self._mode_toolbar = toolbar
            toolbar.setFrameStyle(QFrame.StyledPanel)
            toolbar.setMaximumHeight(36)
            tb_layout = QHBoxLayout(toolbar)
            tb_layout.setContentsMargins(4, 2, 4, 2)

            self._btn_group = QButtonGroup(self)
            self._btn_group.setExclusive(True)

            for label, mode in [("Code", MODE_CODE), ("Split", MODE_SPLIT), ("Design", MODE_DESIGN)]:
                btn = QPushButton(label)
                btn.setCheckable(True)
                btn.setMinimumWidth(70)
                btn.setStyleSheet("""
                    QPushButton { padding: 4px 12px; border: 1px solid #555; border-radius: 3px; }
                    QPushButton:checked { background-color: #0078D4; color: white; border-color: #0078D4; }
                """)
                if mode == MODE_DESIGN:
                    btn.setChecked(True)
                self._btn_group.addButton(btn)
                self._mode_buttons[mode] = btn
                tb_layout.addWidget(btn)
                btn.clicked.connect(lambda checked, m=mode: self.set_mode(m))

            tb_layout.addStretch()
            layout.addWidget(toolbar)

        self._update_accessibility_metadata()

        # Ctrl+S is handled by the main window QAction (no local QShortcut
        # here — creating one would cause an ambiguous shortcut conflict).

    # ── Public API ─────────────────────────────────────────────────

    def _mode_label(self, mode=None):
        mode = mode or self._mode
        return {
            MODE_DESIGN: "Design",
            MODE_SPLIT: "Split",
            MODE_CODE: "Code",
        }.get(mode, str(mode or "Unknown"))

    def _xml_source_summary(self):
        if self._mode == MODE_SPLIT:
            text = self._split_editor.toPlainText()
        else:
            text = self._code_editor.toPlainText()
        if not text.strip():
            return "XML source is empty."
        line_count = text.count("\n") + 1
        line_label = "line" if line_count == 1 else "lines"
        return f"XML source: {len(text)} characters across {line_count} {line_label}."

    def _update_mode_button_metadata(self):
        for mode, button in self._mode_buttons.items():
            label = self._mode_label(mode)
            if mode == self._mode:
                tooltip = f"Currently showing {label} mode."
                accessible_name = f"Editor mode button: {label}. Current mode."
            else:
                tooltip = f"Switch to {label} mode."
                accessible_name = f"Editor mode button: {label}."
            _set_widget_metadata(button, tooltip=tooltip, accessible_name=accessible_name)

    def _update_accessibility_metadata(self):
        mode_label = self._mode_label()
        xml_summary = self._xml_source_summary()
        switch_text = "visible" if self._show_mode_switch else "hidden"
        summary = f"Editor tabs: {mode_label} mode. {xml_summary} Mode switch {switch_text}."
        design_state = "visible" if self._mode == MODE_DESIGN else "hidden"
        split_state = "visible" if self._mode == MODE_SPLIT else "hidden"
        _set_widget_metadata(self, tooltip=summary, accessible_name=summary)
        _set_widget_metadata(
            self._stack,
            tooltip=f"Editor view stack. Current mode: {mode_label}.",
            accessible_name=f"Editor view stack: {mode_label} mode.",
        )
        _set_widget_metadata(
            self._design_container,
            tooltip=f"Design editor surface. Current state: {design_state}.",
            accessible_name=f"Design editor surface: {design_state}.",
        )
        _set_widget_metadata(
            self._code_editor,
            tooltip=f"Code view XML editor. {xml_summary}",
            accessible_name=f"XML editor: Code mode. {xml_summary}",
        )
        _set_widget_metadata(
            self._split_editor,
            tooltip=f"Split view XML editor. {xml_summary}",
            accessible_name=f"XML editor: Split mode. {xml_summary}",
        )
        _set_widget_metadata(
            self._split_container,
            tooltip=f"Split editor view with XML source and preview. Current state: {split_state}. {xml_summary}",
            accessible_name=f"Split editor view: {split_state}. {xml_summary}",
        )
        _set_widget_metadata(
            self._split_preview_container,
            tooltip=f"Split preview surface. Current state: {split_state}.",
            accessible_name=f"Split preview surface: {split_state}.",
        )
        if self._mode_toolbar is not None:
            _set_widget_metadata(
                self._mode_toolbar,
                tooltip=f"Editor mode switcher. Current mode: {mode_label}.",
                accessible_name=f"Editor mode switcher: {mode_label} mode.",
            )
            self._update_mode_button_metadata()

    @property
    def mode(self):
        return self._mode

    def set_mode(self, mode):
        """Switch between Design / Split / Code."""
        if mode == self._mode:
            return
        self._mode = mode
        if mode == MODE_DESIGN:
            # Flush pending XML changes before switching to Design
            if self._parse_timer.isActive():
                self._parse_timer.stop()
                self._emit_xml_changed()
            # Reparent preview back to design container
            self._design_container.layout().addWidget(self._preview)
            self._stack.setCurrentIndex(0)
        elif mode == MODE_CODE:
            self._stack.setCurrentIndex(1)
        elif mode == MODE_SPLIT:
            # Reparent preview to split right pane
            split_layout = self._split_preview_container.layout()
            if split_layout is None:
                split_layout = QVBoxLayout(self._split_preview_container)
                split_layout.setContentsMargins(0, 0, 0, 0)
            split_layout.addWidget(self._preview)
            self._stack.setCurrentIndex(2)
        self._update_accessibility_metadata()
        self.mode_changed.emit(mode)

    def set_xml_text(self, xml_text):
        """Update both XML editors with new text (Design → Code direction).

        Call this when the model changes from Design interactions.
        """
        self._syncing = True
        self._code_editor.setPlainText(xml_text)
        self._split_editor.setPlainText(xml_text)
        self._syncing = False
        self._update_accessibility_metadata()

    def get_xml_text(self):
        """Get current XML text from the active editor."""
        if self._mode == MODE_SPLIT:
            return self._split_editor.toPlainText()
        return self._code_editor.toPlainText()

    @property
    def code_editor(self):
        return self._code_editor

    @property
    def split_editor(self):
        return self._split_editor

    @property
    def preview(self):
        return self._preview

    # ── Internal ───────────────────────────────────────────────────

    def _on_code_text_changed(self):
        """User is typing in XML editor — debounce parse."""
        self._update_accessibility_metadata()
        if self._syncing:
            return
        self._parse_timer.start()

    def _emit_xml_changed(self):
        """Debounce expired — emit parsed XML."""
        text = self.get_xml_text()
        # Sync the other editor
        self._syncing = True
        if self._mode == MODE_CODE:
            self._split_editor.setPlainText(text)
        elif self._mode == MODE_SPLIT:
            self._code_editor.setPlainText(text)
        self._syncing = False
        self._update_accessibility_metadata()
        self.xml_changed.emit(text)
