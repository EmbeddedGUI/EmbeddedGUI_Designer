"""Favorite component service backed by DesignerConfig."""

from __future__ import annotations

from ..model.config import DesignerConfig


class FavoriteService:
    """Tracks favorited component types."""

    def __init__(self, config: DesignerConfig):
        self._config = config

    def list_favorites(self) -> list[str]:
        return list(getattr(self._config, "widget_browser_favorites", []) or [])

    def is_favorite(self, type_name: str) -> bool:
        type_name = str(type_name or "").strip()
        return bool(type_name and type_name in set(self.list_favorites()))

    def toggle(self, type_name: str) -> bool:
        """Toggle favorite state and return enabled status."""
        return bool(self._config.toggle_widget_browser_favorite(str(type_name or "").strip()))
