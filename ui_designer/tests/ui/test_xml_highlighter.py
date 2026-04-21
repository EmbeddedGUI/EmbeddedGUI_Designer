"""Qt UI tests for XML syntax highlighting."""

from ui_designer.tests.qt_test_utils import skip_if_no_qt

_skip_no_qt = skip_if_no_qt


@_skip_no_qt
class TestXmlSyntaxHighlighter:
    def test_highlighter_uses_active_theme_tokens(self, qapp):
        from PyQt5.QtGui import QFont, QTextDocument

        from ui_designer.ui.theme import app_theme_tokens
        from ui_designer.ui.xml_highlighter import XmlSyntaxHighlighter, xml_syntax_palette

        qapp.setProperty("designer_theme_mode", "dark")
        document = QTextDocument()
        highlighter = XmlSyntaxHighlighter(document)

        try:
            expected = xml_syntax_palette(qapp)
            tokens = app_theme_tokens(qapp)

            assert highlighter.current_palette() == expected
            assert highlighter.format_for_role("meta").foreground().color().name().lower() == tokens["syntax_meta"].lower()
            assert highlighter.format_for_role("comment").foreground().color().name().lower() == tokens["syntax_comment"].lower()
            assert highlighter.format_for_role("comment").fontItalic() is True
            assert highlighter.format_for_role("tag").foreground().color().name().lower() == tokens["syntax_tag"].lower()
            assert highlighter.format_for_role("tag").fontWeight() == QFont.Bold
            assert highlighter.format_for_role("attr").foreground().color().name().lower() == tokens["syntax_attr"].lower()
            assert highlighter.format_for_role("value").foreground().color().name().lower() == tokens["syntax_value"].lower()
            assert highlighter.format_for_role("bracket").foreground().color().name().lower() == tokens["syntax_bracket"].lower()
        finally:
            highlighter.setDocument(None)
            document.deleteLater()
            qapp.setProperty("designer_theme_mode", None)

    def test_highlighter_refreshes_when_theme_changes(self, qapp):
        from PyQt5.QtGui import QTextDocument

        from ui_designer.ui.theme import app_theme_tokens
        from ui_designer.ui.xml_highlighter import XmlSyntaxHighlighter

        qapp.setProperty("designer_theme_mode", "dark")
        document = QTextDocument()
        highlighter = XmlSyntaxHighlighter(document)

        try:
            dark_palette = highlighter.current_palette()

            qapp.setProperty("designer_theme_mode", "light")
            highlighter.refresh_formats()

            light_tokens = app_theme_tokens(qapp)
            light_palette = highlighter.current_palette()

            assert light_palette["tag"] == light_tokens["syntax_tag"]
            assert light_palette["comment"] == light_tokens["syntax_comment"]
            assert light_palette["value"] == light_tokens["syntax_value"]
            assert light_palette != dark_palette
        finally:
            highlighter.setDocument(None)
            document.deleteLater()
            qapp.setProperty("designer_theme_mode", None)
