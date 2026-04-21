"""XML syntax highlighter for the Code view editor."""

from __future__ import annotations

from PyQt5.QtCore import QRegularExpression
from PyQt5.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat

from .theme import app_theme_tokens


def xml_syntax_palette(app=None):
    """Return the active XML syntax palette derived from theme tokens."""
    tokens = app_theme_tokens(app)
    return {
        "meta": tokens["syntax_meta"],
        "comment": tokens["syntax_comment"],
        "tag": tokens["syntax_tag"],
        "attr": tokens["syntax_attr"],
        "value": tokens["syntax_value"],
        "bracket": tokens["syntax_bracket"],
    }


class XmlSyntaxHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for XML layout files."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._palette = {}
        self._formats = {}
        self._rules = []
        self.refresh_formats()

    def current_palette(self):
        """Return the active color palette used by the highlighter."""
        return dict(self._palette)

    def format_for_role(self, role):
        """Return the configured text format for a syntax role."""
        return QTextCharFormat(self._formats[str(role)])

    def refresh_formats(self):
        """Rebuild formats from the active theme and rehighlight the document."""
        self._palette = xml_syntax_palette()

        fmt_meta = QTextCharFormat()
        fmt_meta.setForeground(QColor(self._palette["meta"]))

        fmt_comment = QTextCharFormat()
        fmt_comment.setForeground(QColor(self._palette["comment"]))
        fmt_comment.setFontItalic(True)

        fmt_tag = QTextCharFormat()
        fmt_tag.setForeground(QColor(self._palette["tag"]))
        fmt_tag.setFontWeight(QFont.Bold)

        fmt_attr = QTextCharFormat()
        fmt_attr.setForeground(QColor(self._palette["attr"]))

        fmt_value = QTextCharFormat()
        fmt_value.setForeground(QColor(self._palette["value"]))

        fmt_bracket = QTextCharFormat()
        fmt_bracket.setForeground(QColor(self._palette["bracket"]))

        self._formats = {
            "meta": fmt_meta,
            "comment": fmt_comment,
            "tag": fmt_tag,
            "attr": fmt_attr,
            "value": fmt_value,
            "bracket": fmt_bracket,
        }
        self._rules = [
            (QRegularExpression(r"<\?.*?\?>"), fmt_meta),
            (QRegularExpression(r"<!--.*?-->"), fmt_comment),
            (QRegularExpression(r"</?[\w:-]+"), fmt_tag),
            (QRegularExpression(r'\b[\w:-]+(?=\s*=)'), fmt_attr),
            (QRegularExpression(r'"[^"]*"'), fmt_value),
            (QRegularExpression(r"'[^']*'"), fmt_value),
            (QRegularExpression(r"[<>/?]"), fmt_bracket),
        ]
        self.rehighlight()

    def highlightBlock(self, text):
        for pattern, fmt in self._rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                match = it.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), fmt)
