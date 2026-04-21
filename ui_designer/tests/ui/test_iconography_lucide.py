"""Lucide icon loader and routing tests."""

from __future__ import annotations

import importlib

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QPixmap

import ui_designer.ui.iconography as iconography
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


def test_theme_switch_clears_lucide_cache(qapp):
    module = _reload_iconography()
    module.load_lucide_icon("play", color="#D4D4D8", size=16)
    assert module._load_lucide_icon_cached.cache_info().currsize >= 1
    apply_theme(qapp, mode="dark")
    assert module._load_lucide_icon_cached.cache_info().currsize == 0
