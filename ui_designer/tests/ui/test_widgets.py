"""Tests for color_picker and font_selector utility functions.

Qt-independent tests run always. Qt-dependent tests are skipped if PyQt5 is missing.
"""

import re
import pytest


# ── Qt-independent tests (regex patterns) ─────────────────────

# Duplicate the regex patterns to avoid importing PyQt5-dependent modules
_HEX_RE = re.compile(r'^EGUI_COLOR_HEX\(\s*0x([0-9A-Fa-f]{6})\s*\)$')
_FONT_RE = re.compile(r'&egui_res_font_(\w+?)_(\d+)_(\d+)$')


def _font_display_info_local(font_expr):
    m = _FONT_RE.match(font_expr)
    if m:
        return m.group(1), m.group(2), m.group(3)
    return None


class TestHexRegex:
    """Test the EGUI_COLOR_HEX regex pattern."""

    def test_valid_hex(self):
        assert _HEX_RE.match("EGUI_COLOR_HEX(0xABCDEF)")

    def test_valid_hex_with_spaces(self):
        assert _HEX_RE.match("EGUI_COLOR_HEX( 0xABCDEF )")

    def test_invalid_short(self):
        assert _HEX_RE.match("EGUI_COLOR_HEX(0xABC)") is None

    def test_invalid_no_prefix(self):
        assert _HEX_RE.match("EGUI_COLOR_HEX(ABCDEF)") is None

    def test_extracts_hex_value(self):
        m = _HEX_RE.match("EGUI_COLOR_HEX(0xFF8000)")
        assert m.group(1) == "FF8000"

    def test_lowercase_hex(self):
        m = _HEX_RE.match("EGUI_COLOR_HEX(0xabcdef)")
        assert m.group(1) == "abcdef"


class TestFontDisplayInfo:
    """Test _font_display_info parsing."""

    def test_standard_font(self):
        assert _font_display_info_local("&egui_res_font_montserrat_14_4") == ("montserrat", "14", "4")

    def test_custom_font(self):
        assert _font_display_info_local("&egui_res_font_roboto_12_8") == ("roboto", "12", "8")

    def test_default_font_returns_none(self):
        assert _font_display_info_local("EGUI_CONFIG_FONT_DEFAULT") is None

    def test_empty_returns_none(self):
        assert _font_display_info_local("") is None

    def test_arbitrary_string_returns_none(self):
        assert _font_display_info_local("some_random_string") is None


# ── Qt-dependent tests ────────────────────────────────────────

try:
    import PyQt5
    _has_pyqt5 = True
except ImportError:
    _has_pyqt5 = False

_skip_no_qt = pytest.mark.skipif(not _has_pyqt5, reason="PyQt5 not available")


@pytest.fixture
def qapp():
    if not _has_pyqt5:
        yield None
        return
    from PyQt5.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
    app.processEvents()


@_skip_no_qt
class TestEguiColorToQColor:
    """Test egui_color_to_qcolor conversion (requires PyQt5)."""

    def test_named_color_black(self):
        from ui_designer.ui.widgets.color_picker import egui_color_to_qcolor
        qc = egui_color_to_qcolor("EGUI_COLOR_BLACK")
        assert qc is not None
        assert (qc.red(), qc.green(), qc.blue()) == (0, 0, 0)

    def test_hex_color(self):
        from ui_designer.ui.widgets.color_picker import egui_color_to_qcolor
        qc = egui_color_to_qcolor("EGUI_COLOR_HEX(0xFF8000)")
        assert (qc.red(), qc.green(), qc.blue()) == (255, 128, 0)

    def test_empty_returns_none(self):
        from ui_designer.ui.widgets.color_picker import egui_color_to_qcolor
        assert egui_color_to_qcolor("") is None

    def test_unknown_returns_none(self):
        from ui_designer.ui.widgets.color_picker import egui_color_to_qcolor
        assert egui_color_to_qcolor("NOT_A_COLOR") is None


@_skip_no_qt
class TestQColorToEguiHex:
    """Test qcolor_to_egui_hex conversion (requires PyQt5)."""

    def test_red(self):
        from PyQt5.QtGui import QColor
        from ui_designer.ui.widgets.color_picker import qcolor_to_egui_hex
        assert qcolor_to_egui_hex(QColor(255, 0, 0)) == "EGUI_COLOR_HEX(0xFF0000)"

    def test_custom_color(self):
        from PyQt5.QtGui import QColor
        from ui_designer.ui.widgets.color_picker import qcolor_to_egui_hex
        assert qcolor_to_egui_hex(QColor(18, 52, 86)) == "EGUI_COLOR_HEX(0x123456)"


@_skip_no_qt
class TestEguiFontSelector:
    """Test EguiFontSelector fallback behavior when qfluentwidgets state is stale."""

    def test_preview_label_falls_back_when_body_label_raises_runtime_error(self, qapp, monkeypatch):
        from PyQt5.QtWidgets import QLabel
        from ui_designer.ui.widgets import font_selector as font_selector_module

        def _raise_runtime_error(*_args, **_kwargs):
            raise RuntimeError("wrapped C/C++ object of type QConfig has been deleted")

        monkeypatch.setattr(font_selector_module, "BodyLabel", _raise_runtime_error)

        selector = font_selector_module.EguiFontSelector(fonts=["EGUI_CONFIG_FONT_DEFAULT"])

        assert isinstance(selector._preview, QLabel)
        selector.deleteLater()

    def test_accessibility_metadata_updates_with_font_value(self, qapp):
        from PyQt5.QtCore import Qt
        from ui_designer.ui.widgets.font_selector import EguiFontSelector

        selector = EguiFontSelector(fonts=["EGUI_CONFIG_FONT_DEFAULT", "&egui_res_font_montserrat_14_4"])

        selector.set_value("&egui_res_font_montserrat_14_4")

        assert selector.accessibleName() == "Font selector: montserrat 14px 4bpp."
        assert selector._combo.toolTip() == (
            "Choose or type an EGUI font. Current value: &egui_res_font_montserrat_14_4."
        )
        assert selector._combo.statusTip() == selector._combo.toolTip()
        assert selector._combo.accessibleName() == "Font value: &egui_res_font_montserrat_14_4"
        assert selector._preview.toolTip() == "Font preview: 14px."
        assert selector._preview.accessibleName() == "Font preview: 14px. montserrat 14px 4bpp."
        assert selector._preview.alignment() == (Qt.AlignRight | Qt.AlignVCenter)

        selector.set_value("custom_font_expr")

        assert selector.accessibleName() == "Font selector: Custom font expression: custom_font_expr."
        assert selector._preview.accessibleName() == (
            "Font preview: Custom. Custom font expression: custom_font_expr."
        )
        selector.deleteLater()

    def test_selector_uses_compact_preview_layout(self, qapp):
        from PyQt5.QtCore import Qt
        from ui_designer.ui.widgets.font_selector import EguiFontSelector

        selector = EguiFontSelector(fonts=["EGUI_CONFIG_FONT_DEFAULT", "&egui_res_font_montserrat_14_4"])
        layout = selector.layout()

        assert layout.spacing() == 2
        assert selector._preview.width() == 60
        assert selector._preview.minimumWidth() == 60
        assert selector._preview.maximumWidth() == 60
        assert selector._preview.alignment() == (Qt.AlignRight | Qt.AlignVCenter)
        selector.deleteLater()

    def test_selector_preview_font_size_respects_ui_floor(self, qapp):
        from ui_designer.ui.widgets.font_selector import EguiFontSelector

        qapp.setProperty("designer_font_size_pt", 12)
        selector = EguiFontSelector(fonts=["&egui_res_font_montserrat_8_4", "&egui_res_font_montserrat_20_4"])

        try:
            selector.set_value("&egui_res_font_montserrat_8_4")
            assert f"font-size: {selector._preview_font_floor_px()}px;" in selector._preview.styleSheet()

            selector.set_value("&egui_res_font_montserrat_20_4")
            assert "font-size: 20px;" in selector._preview.styleSheet()
        finally:
            selector.deleteLater()
            qapp.setProperty("designer_font_size_pt", 0)

    def test_selector_can_refresh_preview_after_ui_scale_changes(self, qapp):
        from ui_designer.ui.widgets.font_selector import EguiFontSelector

        selector = EguiFontSelector(fonts=["&egui_res_font_montserrat_8_4"])
        try:
            selector.set_value("&egui_res_font_montserrat_8_4")
            initial_style = selector._preview.styleSheet()

            qapp.setProperty("designer_font_size_pt", 12)
            selector.refresh_theme_metrics()

            assert selector._preview.styleSheet() != initial_style
            assert f"font-size: {selector._preview_font_floor_px()}px;" in selector._preview.styleSheet()
        finally:
            selector.deleteLater()
            qapp.setProperty("designer_font_size_pt", 0)

    def test_selector_hint_skips_no_op_rewrites(self, qapp, monkeypatch):
        from ui_designer.ui.widgets.font_selector import EguiFontSelector

        selector = EguiFontSelector(fonts=["EGUI_CONFIG_FONT_DEFAULT", "&egui_res_font_montserrat_14_4"])
        selector.setProperty("_font_selector_hint_snapshot", None)

        hint_calls = 0
        original_set_tooltip = selector.setToolTip

        def counted_set_tooltip(text):
            nonlocal hint_calls
            hint_calls += 1
            return original_set_tooltip(text)

        monkeypatch.setattr(selector, "setToolTip", counted_set_tooltip)

        selector._update_accessibility_metadata("&egui_res_font_montserrat_14_4")
        assert hint_calls == 1

        selector._update_accessibility_metadata("&egui_res_font_montserrat_14_4")
        assert hint_calls == 1

        selector.set_value("custom_font_expr")
        assert hint_calls == 2
        selector.deleteLater()

    def test_selector_accessible_name_skips_no_op_rewrites(self, qapp, monkeypatch):
        from ui_designer.ui.widgets.font_selector import EguiFontSelector

        selector = EguiFontSelector(fonts=["EGUI_CONFIG_FONT_DEFAULT", "&egui_res_font_montserrat_14_4"])
        selector.setProperty("_font_selector_accessible_snapshot", None)

        accessible_calls = 0
        original_set_accessible_name = selector.setAccessibleName

        def counted_set_accessible_name(text):
            nonlocal accessible_calls
            accessible_calls += 1
            return original_set_accessible_name(text)

        monkeypatch.setattr(selector, "setAccessibleName", counted_set_accessible_name)

        selector._update_accessibility_metadata("&egui_res_font_montserrat_14_4")
        assert accessible_calls == 1

        selector._update_accessibility_metadata("&egui_res_font_montserrat_14_4")
        assert accessible_calls == 1

        selector.set_value("custom_font_expr")
        assert accessible_calls == 2
        selector.deleteLater()


@_skip_no_qt
class TestEguiColorPicker:
    def test_accessibility_metadata_updates_with_color_value(self, qapp):
        from ui_designer.ui.widgets.color_picker import EguiColorPicker

        picker = EguiColorPicker()

        picker.set_value("EGUI_COLOR_RED")

        assert picker.accessibleName() == "Color picker: EGUI_COLOR_RED (#FF0000)"
        assert picker._combo.toolTip() == "Choose or type an EGUI color. Current value: EGUI_COLOR_RED."
        assert picker._combo.statusTip() == picker._combo.toolTip()
        assert picker._combo.accessibleName() == "Color value: EGUI_COLOR_RED"
        assert picker._swatch.accessibleName() == "Color swatch: EGUI_COLOR_RED (#FF0000)"
        assert picker._btn.text() == "Pick"
        assert picker._btn.toolTip() == "Open the custom color dialog. Current color: EGUI_COLOR_RED (#FF0000)"
        assert picker._btn.accessibleName() == "Open color dialog: EGUI_COLOR_RED (#FF0000)"

        picker.set_value("NOT_A_COLOR")

        assert picker.accessibleName() == "Color picker: NOT_A_COLOR. Preview unavailable."
        assert picker._swatch.accessibleName() == "Color swatch: NOT_A_COLOR. Preview unavailable."
        picker.deleteLater()

    def test_picker_uses_compact_square_swatch_and_text_button(self, qapp):
        from ui_designer.ui.widgets.color_picker import EguiColorPicker

        picker = EguiColorPicker()
        layout = picker.layout()

        assert layout.spacing() == 2
        assert picker._swatch.width() == 20
        assert picker._swatch.height() == 20
        assert picker._btn.text() == "Pick"
        picker.deleteLater()

    def test_picker_swatch_uses_soft_border_color(self, qapp):
        from ui_designer.ui.widgets.color_picker import EguiColorPicker

        picker = EguiColorPicker()
        border = picker._swatch._border_color()

        assert border.isValid() is True
        assert border.alpha() == 96
        picker.deleteLater()

    def test_picker_hint_skips_no_op_rewrites(self, qapp, monkeypatch):
        from ui_designer.ui.widgets.color_picker import EguiColorPicker

        picker = EguiColorPicker()
        picker.setProperty("_color_picker_hint_snapshot", None)

        hint_calls = 0
        original_set_tooltip = picker.setToolTip

        def counted_set_tooltip(text):
            nonlocal hint_calls
            hint_calls += 1
            return original_set_tooltip(text)

        monkeypatch.setattr(picker, "setToolTip", counted_set_tooltip)

        picker._update_accessibility_metadata("EGUI_COLOR_RED")
        assert hint_calls == 1

        picker._update_accessibility_metadata("EGUI_COLOR_RED")
        assert hint_calls == 1

        picker.set_value("EGUI_COLOR_BLUE")
        assert hint_calls == 2
        picker.deleteLater()

    def test_picker_accessible_name_skips_no_op_rewrites(self, qapp, monkeypatch):
        from ui_designer.ui.widgets.color_picker import EguiColorPicker

        picker = EguiColorPicker()
        picker.setProperty("_color_picker_accessible_snapshot", None)

        accessible_calls = 0
        original_set_accessible_name = picker.setAccessibleName

        def counted_set_accessible_name(text):
            nonlocal accessible_calls
            accessible_calls += 1
            return original_set_accessible_name(text)

        monkeypatch.setattr(picker, "setAccessibleName", counted_set_accessible_name)

        picker._update_accessibility_metadata("EGUI_COLOR_RED")
        assert accessible_calls == 1

        picker._update_accessibility_metadata("EGUI_COLOR_RED")
        assert accessible_calls == 1

        picker.set_value("EGUI_COLOR_BLUE")
        assert accessible_calls == 2
        picker.deleteLater()
