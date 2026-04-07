"""Tests for workspace UI preferences serialization."""

from ui_designer.settings.ui_prefs import UIPreferences


def test_inspector_group_expanded_roundtrip():
    u = UIPreferences(inspector_group_expanded={"label\tBasic": False, "__multi__\tCallbacks": True})
    state = u.to_workspace_state()
    u2 = UIPreferences.from_workspace_state(state)
    assert u2.inspector_group_expanded == {"label\tBasic": False, "__multi__\tCallbacks": True}


def test_inspector_group_expanded_ignores_bad_payload():
    u = UIPreferences.from_workspace_state({"inspector_group_expanded": "nope"})
    assert u.inspector_group_expanded == {}


def test_property_grid_name_column_width_roundtrip_and_clamp():
    u = UIPreferences(property_grid_name_column_width=96)
    state = u.to_workspace_state()
    assert state["property_grid_name_column_width"] == 120

    u2 = UIPreferences.from_workspace_state({"property_grid_name_column_width": 512})
    assert u2.property_grid_name_column_width == 480
