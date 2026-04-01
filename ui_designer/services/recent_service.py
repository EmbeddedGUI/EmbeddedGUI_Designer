"""Recent component service backed by DesignerConfig."""

from __future__ import annotations

from ..model.config import DesignerConfig


class RecentService:
    """Tracks recently inserted component types."""

    def __init__(self, config: DesignerConfig):
        self._config = config

    def list_recent_types(self) -> list[str]:
        return list(getattr(self._config, "widget_browser_recent", []) or [])

    def record_insert(self, type_name: str) -> bool:
        return bool(self._config.record_widget_browser_recent(str(type_name or "").strip()))
