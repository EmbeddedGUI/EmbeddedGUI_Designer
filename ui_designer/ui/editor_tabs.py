"""Editor tabs panel for Design / Split / Code workflows."""

from PyQt5.QtCore import QEvent, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .preview_panel import PreviewPanel
from .theme import designer_font_size_pt, designer_monospace_font, theme_tokens
from .xml_highlighter import XmlSyntaxHighlighter


MODE_DESIGN = "design"
MODE_SPLIT = "split"
MODE_CODE = "code"

_DEFAULT_UI_TOKENS = theme_tokens("dark")
_SPACE_XS = int(_DEFAULT_UI_TOKENS.get("space_xs", 4))
_SPACE_SM = int(_DEFAULT_UI_TOKENS.get("space_sm", 8))
_SPACE_MD = int(_DEFAULT_UI_TOKENS.get("space_md", 12))
_DEFAULT_EDITOR_FONT_PT = 9


def _editor_font_size_pt():
    return designer_font_size_pt(QApplication.instance(), default=_DEFAULT_EDITOR_FONT_PT)


def _set_widget_metadata(widget, *, tooltip=None, accessible_name=None):
    if tooltip is not None:
        hint = str(tooltip or "")
        if str(widget.property("_editor_tabs_hint_snapshot") or "") != hint:
            widget.setToolTip(hint)
            widget.setStatusTip(hint)
            widget.setProperty("_editor_tabs_hint_snapshot", hint)
    if accessible_name is not None:
        name = str(accessible_name or "")
        if str(widget.property("_editor_tabs_accessible_snapshot") or "") != name:
            widget.setAccessibleName(name)
            widget.setProperty("_editor_tabs_accessible_snapshot", name)


class XmlEditor(QPlainTextEdit):
    """Plain text editor styled for XML editing."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("editor_tabs_xml_editor")
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.set_editor_font_size_pt(_editor_font_size_pt())
        self._highlighter = XmlSyntaxHighlighter(self.document())
        _set_widget_metadata(
            self,
            tooltip="XML editor for the current page source.",
            accessible_name="XML editor",
        )

    def set_editor_font_size_pt(self, point_size):
        font = designer_monospace_font(point_size=int(point_size))
        self.setFont(font)
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(" ") * 4)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.StyleChange, QEvent.PaletteChange):
            self._highlighter.refresh_formats()


class EditorTabs(QWidget):
    """Tri-view editor: Design / Split / Code."""

    xml_changed = pyqtSignal(str)
    mode_changed = pyqtSignal(str)
    save_requested = pyqtSignal()

    def __init__(self, preview_panel, parent=None, show_mode_switch=True):
        super().__init__(parent)
        self._preview = preview_panel
        self._mode = MODE_DESIGN
        self._syncing = False
        self._show_mode_switch = bool(show_mode_switch)
        self._mode_toolbar = None
        self._mode_buttons = {}

        self._parse_timer = QTimer()
        self._parse_timer.setSingleShot(True)
        self._parse_timer.setInterval(300)
        self._parse_timer.timeout.connect(self._emit_xml_changed)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self._header_frame = QFrame(self)
        self._header_frame.setObjectName("editor_tabs_header")
        self._header_frame.hide()
        header_layout = QVBoxLayout(self._header_frame)
        header_layout.setContentsMargins(6, 6, 6, 6)
        header_layout.setSpacing(2)

        self._eyebrow_label = QLabel("Editor")
        self._eyebrow_label.setObjectName("editor_tabs_eyebrow")
        self._eyebrow_label.hide()
        header_layout.addWidget(self._eyebrow_label)

        self._meta_label = QLabel(
            "Switch between visual layout, split inspection, and raw XML editing without losing page context."
        )
        self._meta_label.setObjectName("editor_tabs_meta")
        self._meta_label.setWordWrap(True)
        self._meta_label.hide()
        header_layout.addWidget(self._meta_label)

        self._summary_label = QLabel("XML source is empty.")
        self._summary_label.setObjectName("editor_tabs_summary")
        self._summary_label.setWordWrap(True)
        self._summary_label.hide()
        header_layout.addWidget(self._summary_label)

        self._mode_chip = QLabel("Design")
        self._mode_chip.setObjectName("workspace_status_chip")
        self._mode_chip.hide()
        header_layout.addWidget(self._mode_chip)

        self._btn_group = None
        if self._show_mode_switch:
            self._mode_toolbar = QFrame()
            self._mode_toolbar.setObjectName("editor_tabs_mode_strip")
            toolbar_layout = QHBoxLayout(self._mode_toolbar)
            toolbar_layout.setContentsMargins(2, 2, 2, 2)
            toolbar_layout.setSpacing(2)

            self._btn_group = QButtonGroup(self)
            self._btn_group.setExclusive(True)
            for label, mode in (("Design", MODE_DESIGN), ("Split", MODE_SPLIT), ("Code", MODE_CODE)):
                button = QPushButton(label)
                button.setObjectName("workspace_mode_button")
                button.setCheckable(True)
                if mode == MODE_DESIGN:
                    button.setChecked(True)
                self._btn_group.addButton(button)
                self._mode_buttons[mode] = button
                toolbar_layout.addWidget(button)
                button.clicked.connect(lambda checked, m=mode: self.set_mode(m))
            toolbar_layout.addStretch(1)
            layout.addWidget(self._mode_toolbar)

        self._stack_shell = QFrame()
        self._stack_shell.setObjectName("editor_tabs_shell")
        stack_shell_layout = QVBoxLayout(self._stack_shell)
        stack_shell_layout.setContentsMargins(2, 2, 2, 2)
        stack_shell_layout.setSpacing(0)

        self._stack = QStackedWidget()
        self._stack.setObjectName("editor_tabs_stack")
        stack_shell_layout.addWidget(self._stack, 1)
        layout.addWidget(self._stack_shell, 1)

        self._design_container = QWidget()
        self._design_container.setObjectName("editor_tabs_surface")
        design_layout = QVBoxLayout(self._design_container)
        design_layout.setContentsMargins(0, 0, 0, 0)
        design_layout.addWidget(self._preview)
        _set_widget_metadata(
            self._design_container,
            tooltip="Design surface showing the live preview.",
            accessible_name="Design editor surface",
        )
        self._stack.addWidget(self._design_container)

        self._code_editor = XmlEditor()
        self._stack.addWidget(self._code_editor)

        self._split_container = QWidget()
        self._split_container.setObjectName("editor_tabs_surface")
        split_layout = QVBoxLayout(self._split_container)
        split_layout.setContentsMargins(0, 0, 0, 0)
        self._split = QSplitter(Qt.Horizontal)
        self._split.setObjectName("editor_tabs_splitter")
        self._split_editor = XmlEditor()
        self._split_preview_container = QWidget()
        self._split_preview_container.setObjectName("editor_tabs_preview_surface")
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

        self._code_editor.textChanged.connect(self._on_code_text_changed)
        self._split_editor.textChanged.connect(self._on_code_text_changed)
        self._update_accessibility_metadata()

    def _mode_label(self, mode=None):
        mode = mode or self._mode
        return {
            MODE_DESIGN: "Design",
            MODE_SPLIT: "Split",
            MODE_CODE: "Code",
        }.get(mode, str(mode or "Unknown"))

    def _xml_source_summary(self):
        text = self._split_editor.toPlainText() if self._mode == MODE_SPLIT else self._code_editor.toPlainText()
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

        self._summary_label.setText(xml_summary)
        self._mode_chip.setText(mode_label)

        _set_widget_metadata(self, tooltip=summary, accessible_name=summary)
        _set_widget_metadata(
            self._header_frame,
            tooltip=f"Editor tabs header. {summary}",
            accessible_name=f"Editor tabs header. {summary}",
        )
        _set_widget_metadata(
            self._eyebrow_label,
            tooltip="Editor engineering workspace surface.",
            accessible_name="Editor engineering workspace surface.",
        )
        _set_widget_metadata(
            self._meta_label,
            tooltip=self._meta_label.text(),
            accessible_name=self._meta_label.text(),
        )
        _set_widget_metadata(
            self._summary_label,
            tooltip=xml_summary,
            accessible_name=xml_summary,
        )
        _set_widget_metadata(
            self._mode_chip,
            tooltip=f"Current editor mode: {mode_label}",
            accessible_name=f"Current editor mode: {mode_label}",
        )
        _set_widget_metadata(self._stack_shell, tooltip=summary, accessible_name=summary)
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

    def set_editor_font_size_pt(self, point_size):
        self._code_editor.set_editor_font_size_pt(point_size)
        self._split_editor.set_editor_font_size_pt(point_size)

    def set_mode(self, mode):
        """Switch between Design / Split / Code."""
        if mode == self._mode:
            return
        self._mode = mode
        if mode == MODE_DESIGN:
            if self._parse_timer.isActive():
                self._parse_timer.stop()
                self._emit_xml_changed()
            self._design_container.layout().addWidget(self._preview)
            self._stack.setCurrentIndex(0)
        elif mode == MODE_CODE:
            self._stack.setCurrentIndex(1)
        elif mode == MODE_SPLIT:
            split_layout = self._split_preview_container.layout()
            if split_layout is None:
                split_layout = QVBoxLayout(self._split_preview_container)
                split_layout.setContentsMargins(0, 0, 0, 0)
            split_layout.addWidget(self._preview)
            self._stack.setCurrentIndex(2)
        self._update_accessibility_metadata()
        self.mode_changed.emit(mode)

    def set_xml_text(self, xml_text):
        """Update both XML editors with new text from design changes."""
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

    def _on_code_text_changed(self):
        """User is typing in XML editor; debounce parse."""
        self._update_accessibility_metadata()
        if self._syncing:
            return
        self._parse_timer.start()

    def _emit_xml_changed(self):
        """Debounce expired; emit parsed XML."""
        text = self.get_xml_text()
        self._syncing = True
        if self._mode == MODE_CODE:
            self._split_editor.setPlainText(text)
        elif self._mode == MODE_SPLIT:
            self._code_editor.setPlainText(text)
        self._syncing = False
        self._update_accessibility_metadata()
        self.xml_changed.emit(text)
