"""Renderer abstraction for preview engines."""

from __future__ import annotations

from typing import Protocol


class IRenderer(Protocol):
    """Common preview renderer contract."""

    name: str

    def mount(self, host_widget) -> None:
        ...

    def render(self, schema: dict) -> None:
        ...

    def select_node(self, node_id: str | None) -> None:
        ...

    def update_node(self, node_id: str, patch: dict) -> None:
        ...

    def snapshot(self) -> bytes:
        ...

    def dispose(self) -> None:
        ...
