"""Lucide icon loader and routing tests."""

from __future__ import annotations

import importlib

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QPixmap

import ui_designer.ui.iconography as iconography
import ui_designer.ui.theme as theme
from ui_designer.ui.theme import apply_theme


def _reload_iconography():
    return importlib.reload(iconography)


def _sentinel_icon(size: int = 16) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.white)
    return QIcon(pixmap)


def test_load_lucide_icon_returns_valid_qicon(qapp):
    module = _reload_iconography()
    icon = module.load_lucide_icon("play", color="#D4D4D8", size=16)
    assert isinstance(icon, QIcon)
    assert not icon.isNull()


def test_load_lucide_icon_caches_by_key(qapp):
    module = _reload_iconography()
    a = module.load_lucide_icon("play", color="#D4D4D8", size=16)
    b = module.load_lucide_icon("play", color="#D4D4D8", size=16)
    assert a is b


def test_load_lucide_icon_recolors_via_stroke(qapp):
    module = _reload_iconography()
    a = module.load_lucide_icon("play", color="#D4D4D8", size=16)
    b = module.load_lucide_icon("play", color="#3B82F6", size=16)
    assert a is not b


def test_load_lucide_icon_missing_returns_fallback(qapp):
    module = _reload_iconography()
    icon = module.load_lucide_icon("definitely_not_a_real_lucide_name", color="#FFFFFF", size=16)
    assert isinstance(icon, QIcon)


def test_lucide_mapping_covers_widget_semantic_keys():
    module = _reload_iconography()
    missing = sorted(set(module._WIDGET_ICON_KEYS.values()) - set(module._LUCIDE_KEY_MAP))
    assert missing == []


def test_lucide_mapping_covers_canonical_semantics_and_assets():
    module = _reload_iconography()
    missing_semantics = sorted(set(module._ICON_DEFINITIONS) - set(module._LUCIDE_KEY_MAP))
    missing_assets = sorted(
        name
        for name in set(module._LUCIDE_KEY_MAP.values())
        if not (module._LUCIDE_DIR / f"{name}.svg").is_file()
    )

    assert missing_semantics == []
    assert missing_assets == []


def test_load_lucide_icon_uses_theme_text_soft_by_default(qapp, monkeypatch):
    module = _reload_iconography()
    sentinel = _sentinel_icon(size=20)
    captured = {}

    monkeypatch.setattr(theme, "app_theme_tokens", lambda *args, **kwargs: {"text_soft": "#123456"})

    def _capture(name, color, size):
        captured["args"] = (name, color, size)
        return sentinel

    monkeypatch.setattr(module, "_load_lucide_icon_cached", _capture)

    icon = module.load_lucide_icon("play", size=20)

    assert icon is sentinel
    assert captured["args"] == ("play", "#123456", 20)


def test_make_icon_uses_lucide_by_default(qapp, monkeypatch):
    module = _reload_iconography()
    monkeypatch.delenv("EMBEDDEDGUI_LEGACY_ICONS", raising=False)
    sentinel = _sentinel_icon()
    monkeypatch.setattr(module, "load_lucide_icon", lambda *args, **kwargs: sentinel)

    def _unexpected_legacy(*args, **kwargs):
        raise AssertionError("legacy fallback should not be used when lucide is enabled")

    monkeypatch.setattr(module, "_legacy_make_icon", _unexpected_legacy)
    icon = module.make_icon("button")
    assert icon is sentinel


def test_legacy_icon_mode_falls_back(qapp, monkeypatch):
    module = _reload_iconography()
    monkeypatch.setenv("EMBEDDEDGUI_LEGACY_ICONS", "1")

    def _unexpected_lucide(*args, **kwargs):
        raise AssertionError("lucide loader should be bypassed in legacy mode")

    monkeypatch.setattr(module, "load_lucide_icon", _unexpected_lucide)
    icon = module.make_icon("button")
    assert isinstance(icon, QIcon)
    assert not icon.isNull()


def test_legacy_icon_mode_renders_all_canonical_semantic_icons(qapp, monkeypatch):
    module = _reload_iconography()
    monkeypatch.setenv("EMBEDDEDGUI_LEGACY_ICONS", "1")

    for key in module.semantic_icon_keys():
        icon = module.make_icon(key)
        assert isinstance(icon, QIcon), key
        assert not icon.isNull(), key


def test_legacy_icon_mode_renders_all_widget_icons(qapp, monkeypatch):
    module = _reload_iconography()
    monkeypatch.setenv("EMBEDDEDGUI_LEGACY_ICONS", "1")

    for widget_key in sorted(module._WIDGET_ICON_KEYS):
        icon = module.icon_for_widget(widget_key)
        assert isinstance(icon, QIcon), widget_key
        assert not icon.isNull(), widget_key


def test_theme_switch_clears_lucide_cache(qapp):
    module = _reload_iconography()
    original_stylesheet = qapp.styleSheet()
    original_mode = qapp.property("designer_theme_mode")
    original_density = qapp.property("designer_ui_density")
    original_font_size = qapp.property("designer_font_size_pt")
    original_fluent_mode = qapp.property("_designer_fluent_theme_mode")

    try:
        module.load_lucide_icon("play", color="#D4D4D8", size=16)
        assert module._load_lucide_icon_cached.cache_info().currsize >= 1
        apply_theme(qapp, mode="dark")
        assert module._load_lucide_icon_cached.cache_info().currsize == 0
    finally:
        qapp.setStyleSheet(original_stylesheet)
        qapp.setProperty("designer_theme_mode", original_mode)
        qapp.setProperty("designer_ui_density", original_density)
        qapp.setProperty("designer_font_size_pt", original_font_size)
        qapp.setProperty("_designer_fluent_theme_mode", original_fluent_mode)
