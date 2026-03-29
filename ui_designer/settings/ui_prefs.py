"""Workspace UI preferences helpers for shell layout persistence."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class UIPreferences:
    """Serializable workspace panel preferences."""

    top_splitter: str = ""
    workspace_splitter: str = ""
    inspector_tab_index: int = 0
    page_tools_tab_index: int = 0
    bottom_tab_index: int = 0
    bottom_panel_visible: bool = False
    active_left_panel: str = "project"
    panel_layout: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_workspace_state(cls, state: dict[str, Any] | None) -> "UIPreferences":
        data = state if isinstance(state, dict) else {}
        return cls(
            top_splitter=str(data.get("top_splitter", "") or ""),
            workspace_splitter=str(data.get("workspace_splitter", "") or ""),
            inspector_tab_index=int(data.get("inspector_tab_index", 0) or 0),
            page_tools_tab_index=int(data.get("page_tools_tab_index", 0) or 0),
            bottom_tab_index=int(data.get("bottom_tab_index", 0) or 0),
            bottom_panel_visible=bool(data.get("bottom_panel_visible", False)),
            active_left_panel=str(data.get("active_left_panel", "project") or "project"),
            panel_layout=data.get("panel_layout", {}) if isinstance(data.get("panel_layout", {}), dict) else {},
        )

    def to_workspace_state(self) -> dict[str, Any]:
        return {
            "top_splitter": self.top_splitter,
            "workspace_splitter": self.workspace_splitter,
            "inspector_tab_index": int(self.inspector_tab_index),
            "page_tools_tab_index": int(self.page_tools_tab_index),
            "bottom_tab_index": int(self.bottom_tab_index),
            "bottom_panel_visible": bool(self.bottom_panel_visible),
            "active_left_panel": self.active_left_panel,
            "panel_layout": self.panel_layout,
        }
