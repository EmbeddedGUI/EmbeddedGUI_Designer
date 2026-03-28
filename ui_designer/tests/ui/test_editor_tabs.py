"""Qt UI tests for editor tab accessibility metadata."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtWidgets import QApplication, QWidget

    _has_pyqt5 = True
except ImportError:
    _has_pyqt5 = False

_skip_no_qt = pytest.mark.skipif(not _has_pyqt5, reason="PyQt5 not available")


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
    app.processEvents()


@_skip_no_qt
class TestEditorTabsAccessibility:
    def test_mode_switch_toolbar_exposes_accessible_mode_summary(self, qapp):
        from ui_designer.ui.editor_tabs import EditorTabs, MODE_CODE, MODE_DESIGN, MODE_SPLIT

        preview = QWidget()
        tabs = EditorTabs(preview, show_mode_switch=True)
        xml_text = "<page />\n<label />"
        xml_summary = f"XML source: {len(xml_text)} characters across 2 lines."

        assert tabs.accessibleName() == "Editor tabs: Design mode. XML source is empty. Mode switch visible."
        assert tabs._stack.accessibleName() == "Editor view stack: Design mode."
        assert tabs._design_container.accessibleName() == "Design editor surface: visible."
        assert tabs._design_container.toolTip() == "Design editor surface. Current state: visible."
        assert tabs._mode_toolbar.accessibleName() == "Editor mode switcher: Design mode."
        assert tabs._mode_buttons[MODE_DESIGN].toolTip() == "Currently showing Design mode."
        assert tabs._mode_buttons[MODE_DESIGN].accessibleName() == "Editor mode button: Design. Current mode."
        assert tabs._mode_buttons[MODE_CODE].statusTip() == "Switch to Code mode."
        assert tabs._mode_buttons[MODE_SPLIT].toolTip() == "Switch to Split mode."

        tabs.set_xml_text(xml_text)

        assert tabs.accessibleName() == f"Editor tabs: Design mode. {xml_summary} Mode switch visible."
        assert tabs._code_editor.accessibleName() == f"XML editor: Code mode. {xml_summary}"
        assert tabs._split_editor.accessibleName() == f"XML editor: Split mode. {xml_summary}"

        tabs.set_mode(MODE_CODE)

        assert tabs.mode == MODE_CODE
        assert tabs._stack.currentWidget() is tabs._code_editor
        assert tabs._stack.accessibleName() == "Editor view stack: Code mode."
        assert tabs._mode_toolbar.accessibleName() == "Editor mode switcher: Code mode."
        assert tabs._mode_buttons[MODE_CODE].accessibleName() == "Editor mode button: Code. Current mode."
        assert tabs._mode_buttons[MODE_DESIGN].toolTip() == "Switch to Design mode."

        tabs.set_mode(MODE_SPLIT)

        assert tabs.mode == MODE_SPLIT
        assert tabs._stack.currentWidget() is tabs._split_container
        assert tabs.preview.parent() is tabs._split_preview_container
        assert tabs._mode_toolbar.accessibleName() == "Editor mode switcher: Split mode."
        assert tabs._split_container.accessibleName() == f"Split editor view: visible. {xml_summary}"
        assert tabs._split_container.statusTip() == tabs._split_container.toolTip()
        assert tabs._split_preview_container.accessibleName() == "Split preview surface: visible."
        assert tabs._mode_buttons[MODE_SPLIT].toolTip() == "Currently showing Split mode."
        tabs.deleteLater()

    def test_accessibility_summary_mentions_hidden_mode_switch(self, qapp):
        from ui_designer.ui.editor_tabs import EditorTabs, MODE_CODE

        tabs = EditorTabs(QWidget(), show_mode_switch=False)

        assert tabs._mode_toolbar is None
        assert tabs.accessibleName() == "Editor tabs: Design mode. XML source is empty. Mode switch hidden."

        tabs.set_mode(MODE_CODE)

        assert tabs.accessibleName() == "Editor tabs: Code mode. XML source is empty. Mode switch hidden."
        assert tabs._stack.accessibleName() == "Editor view stack: Code mode."
        tabs.deleteLater()
