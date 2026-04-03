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
    inspector_section: str = "properties"
    page_tools_tab_index: int = 0
    bottom_tab_index: int = 0
    bottom_panel_kind: str = "diagnostics"
    bottom_panel_visible: bool = False
    focus_canvas_enabled: bool = False
    active_left_panel: str = "project"
    panel_layout: dict[str, Any] = field(default_factory=dict)
    inspector_group_expanded: dict[str, bool] = field(default_factory=dict)

    @classmethod
    def from_workspace_state(cls, state: dict[str, Any] | None) -> "UIPreferences":
        data = state if isinstance(state, dict) else {}
        active_left_panel = str(data.get("active_left_panel", "project") or "project")
        if active_left_panel == "components":
            active_left_panel = "widgets"
        elif active_left_panel == "status":
            active_left_panel = "project"
        inspector_section = str(data.get("inspector_section", "") or "").strip().lower()
        if inspector_section not in {"properties", "animations", "page"}:
            inspector_index = int(data.get("inspector_tab_index", 0) or 0)
            inspector_section = {1: "animations", 2: "page"}.get(inspector_index, "properties")
        bottom_panel_kind = str(data.get("bottom_panel_kind", "") or "").strip().lower()
        if bottom_panel_kind not in {"diagnostics", "history", "debug_output"}:
            bottom_index = int(data.get("bottom_tab_index", 0) or 0)
            bottom_panel_kind = {1: "history", 2: "debug_output"}.get(bottom_index, "diagnostics")
        return cls(
            top_splitter=str(data.get("top_splitter", "") or ""),
            workspace_splitter=str(data.get("workspace_splitter", "") or ""),
            inspector_tab_index=int(data.get("inspector_tab_index", 0) or 0),
            inspector_section=inspector_section,
            page_tools_tab_index=int(data.get("page_tools_tab_index", 0) or 0),
            bottom_tab_index=int(data.get("bottom_tab_index", 0) or 0),
            bottom_panel_kind=bottom_panel_kind,
            bottom_panel_visible=bool(data.get("bottom_panel_visible", False)),
            focus_canvas_enabled=bool(data.get("focus_canvas_enabled", False)),
            active_left_panel=active_left_panel,
            panel_layout=data.get("panel_layout", {}) if isinstance(data.get("panel_layout", {}), dict) else {},
            inspector_group_expanded=_normalize_inspector_group_expanded(data.get("inspector_group_expanded")),
        )

    def to_workspace_state(self) -> dict[str, Any]:
        return {
            "top_splitter": self.top_splitter,
            "workspace_splitter": self.workspace_splitter,
            "inspector_tab_index": int(self.inspector_tab_index),
            "inspector_section": str(self.inspector_section or "properties"),
            "page_tools_tab_index": int(self.page_tools_tab_index),
            "bottom_tab_index": int(self.bottom_tab_index),
            "bottom_panel_kind": str(self.bottom_panel_kind or "diagnostics"),
            "bottom_panel_visible": bool(self.bottom_panel_visible),
            "focus_canvas_enabled": bool(self.focus_canvas_enabled),
            "active_left_panel": "project" if str(self.active_left_panel or "project") == "status" else self.active_left_panel,
            "panel_layout": self.panel_layout,
            "inspector_group_expanded": dict(self.inspector_group_expanded),
        }
