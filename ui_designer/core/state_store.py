"""Minimal editor state store for cross-panel selection sync."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class EditorState:
    current_page_id: str | None = None
    selected_node_id: str | None = None
    active_left_tab: str = "project"
    active_bottom_tab: str = "Diagnostics"
    preview_engine: str = "v1"
    panel_layout: dict[str, Any] = field(default_factory=dict)


class StateStore:
    """In-memory state container with lightweight subscriptions."""

    def __init__(self):
        self._state = EditorState()
        self._listeners: list[Callable[[EditorState], None]] = []

    @property
    def state(self) -> EditorState:
        return self._state

    def subscribe(self, listener: Callable[[EditorState], None]) -> Callable[[], None]:
        self._listeners.append(listener)

        def _unsubscribe() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return _unsubscribe

    def set_current_page(self, page_id: str | None) -> None:
        self._state.current_page_id = page_id
        self._notify()

    def set_selection(self, node_id: str | None) -> None:
        self._state.selected_node_id = node_id
        self._notify()

    def set_left_tab(self, tab_name: str) -> None:
        self._state.active_left_tab = str(tab_name or "project")
        self._notify()

    def set_bottom_tab(self, tab_name: str) -> None:
        self._state.active_bottom_tab = str(tab_name or "Diagnostics")
        self._notify()

    def set_panel_layout(self, panel_layout: dict[str, Any] | None) -> None:
        self._state.panel_layout = panel_layout if isinstance(panel_layout, dict) else {}
        self._notify()

    def set_preview_engine(self, engine_name: str) -> None:
        self._state.preview_engine = str(engine_name or "v1")
        self._notify()

    def _notify(self) -> None:
        for listener in list(self._listeners):
            try:
                listener(self._state)
            except Exception:
                continue
