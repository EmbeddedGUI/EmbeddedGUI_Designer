"""Renderer manager for preview engine registration and switching."""

from __future__ import annotations

from typing import Any

from .base import IRenderer


class RendererManager:
    """Runtime manager for renderer lifecycle and failover."""

    def __init__(self):
        self._renderers: dict[str, IRenderer] = {}
        self._active_name: str = ""

    @property
    def active_name(self) -> str:
        return self._active_name

    def register(self, renderer: IRenderer) -> None:
        name = str(getattr(renderer, "name", "") or "").strip()
        if not name:
            raise ValueError("Renderer name must be non-empty")
        self._renderers[name] = renderer
        if not self._active_name:
            self._active_name = name

    def names(self) -> list[str]:
        return list(self._renderers.keys())

    def get(self, name: str) -> IRenderer | None:
        return self._renderers.get(str(name or "").strip())

    def active(self) -> IRenderer | None:
        return self.get(self._active_name)

    def switch(self, name: str, *, fallback: str = "") -> str:
        target = str(name or "").strip()
        if target in self._renderers:
            self._active_name = target
            return self._active_name
        fallback_name = str(fallback or "").strip()
        if fallback_name in self._renderers:
            self._active_name = fallback_name
            return self._active_name
        if self._active_name in self._renderers:
            return self._active_name
        if self._renderers:
            self._active_name = next(iter(self._renderers.keys()))
        return self._active_name

    def mount_active(self, host_widget: Any) -> None:
        renderer = self.active()
        if renderer is not None:
            renderer.mount(host_widget)

    def render_active(self, schema: dict) -> None:
        renderer = self.active()
        if renderer is not None:
            renderer.render(schema)

    def dispose_all(self) -> None:
        for renderer in list(self._renderers.values()):
            try:
                renderer.dispose()
            except Exception:
                continue
