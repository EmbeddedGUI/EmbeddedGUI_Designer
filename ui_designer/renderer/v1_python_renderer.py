"""Adapter for existing Python renderer to IRenderer."""

from __future__ import annotations

from typing import Callable

from .base import IRenderer
from ..engine.python_renderer import render_page_to_bytes


class V1PythonRenderer(IRenderer):
    name = "v1"

    def __init__(self, page_provider: Callable[[], object | None]):
        self._page_provider = page_provider
        self._last_snapshot: bytes = b""

    def mount(self, host_widget) -> None:
        # The legacy preview panel owns display; no mount needed.
        return None

    def render(self, schema: dict) -> None:
        page = self._page_provider()
        if page is None:
            self._last_snapshot = b""
            return
        screen_width = int(schema.get("screen_width", 240) or 240)
        screen_height = int(schema.get("screen_height", 320) or 320)
        self._last_snapshot = render_page_to_bytes(page, screen_width, screen_height)

    def select_node(self, node_id: str | None) -> None:
        return None

    def update_node(self, node_id: str, patch: dict) -> None:
        return None

    def snapshot(self) -> bytes:
        return self._last_snapshot

    def dispose(self) -> None:
        self._last_snapshot = b""
