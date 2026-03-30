"""Workspace UI preferences helpers for shell layout persistence."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _normalize_inspector_group_expanded(raw: Any) -> dict[str, bool]:
    """Load inspector collapsible group expanded flags from workspace_state JSON."""
    if not isinstance(raw, dict):
        return {}
    out: dict[str, bool] = {}
    for k, v in raw.items():
        sk = str(k).strip()
        if not sk or len(sk) > 240:
            continue
        out[sk] = bool(v)
    if len(out) > 256:
        out = dict(list(out.items())[-256:])
    return out


@dataclass
class UIPreferences:
    """Serializable workspace panel preferences."""

    top_splitter: str = ""
    workspace_splitter: str = ""
    inspector_tab_index: int = 0
    page_tools_tab_index: int = 0
    bottom_tab_index: int = 0
    bottom_panel_visible: bool = False
    focus_canvas_enabled: bool = False
    active_left_panel: str = "project"
    panel_layout: dict[str, Any] = field(default_factory=dict)
    inspector_group_expanded: dict[str, bool] = field(default_factory=dict)

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
            focus_canvas_enabled=bool(data.get("focus_canvas_enabled", False)),
            active_left_panel=str(data.get("active_left_panel", "project") or "project"),
            panel_layout=data.get("panel_layout", {}) if isinstance(data.get("panel_layout", {}), dict) else {},
            inspector_group_expanded=_normalize_inspector_group_expanded(data.get("inspector_group_expanded")),
        )

    def to_workspace_state(self) -> dict[str, Any]:
        return {
            "top_splitter": self.top_splitter,
            "workspace_splitter": self.workspace_splitter,
            "inspector_tab_index": int(self.inspector_tab_index),
            "page_tools_tab_index": int(self.page_tools_tab_index),
            "bottom_tab_index": int(self.bottom_tab_index),
            "bottom_panel_visible": bool(self.bottom_panel_visible),
            "focus_canvas_enabled": bool(self.focus_canvas_enabled),
            "active_left_panel": self.active_left_panel,
            "panel_layout": self.panel_layout,
            "inspector_group_expanded": dict(self.inspector_group_expanded),
        }
