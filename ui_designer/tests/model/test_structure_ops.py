from ui_designer.model.project import Project
from ui_designer.model.structure_ops import (
    can_move_widgets_to_parent_index,
    describe_structure_actions,
    group_selection,
    lift_to_parent,
    move_into_container,
    move_selection_by_step,
    move_widgets_to_parent_index,
    ungroup_selection,
)
from ui_designer.model.widget_model import WidgetModel


def _build_project(app_name="StructureOpsDemo"):
    project = Project(screen_width=240, screen_height=320, app_name=app_name)
    page = project.create_new_page("main_page")
    return project, page.root_widget


def test_group_and_ungroup_selection_round_trip_free_layout():
    project, root = _build_project()
    first = WidgetModel("label", name="first", x=10, y=20, width=30, height=10)
    second = WidgetModel("button", name="second", x=60, y=40, width=20, height=20)
    root.add_child(first)
    root.add_child(second)

    grouped = group_selection(project, [first, second])

    assert grouped.changed is True
    assert grouped.source == "group selection"
    group = grouped.primary
    assert group.widget_type == "group"
    assert group.name == "group"
    assert group.parent is root
    assert root.children == [group]
    assert group.x == 10
    assert group.y == 20
    assert group.width == 70
    assert group.height == 40
    assert first.parent is group
    assert second.parent is group
    assert (first.x, first.y) == (0, 0)
    assert (second.x, second.y) == (50, 20)

    ungrouped = ungroup_selection(project, [group])

    assert ungrouped.changed is True
    assert ungrouped.source == "ungroup selection"
    assert root.children == [first, second]
    assert first.parent is root
    assert second.parent is root
    assert (first.x, first.y) == (10, 20)
    assert (second.x, second.y) == (60, 40)


def test_group_selection_blocks_non_contiguous_layout_siblings():
    project = Project(screen_width=240, screen_height=320, app_name="LayoutGroupDemo")
    page = project.create_new_page("main_page")
    root = WidgetModel("linearlayout", name="root_layout", x=0, y=0, width=200, height=120)
    root.properties["orientation"] = "vertical"
    page.root_widget = root

    first = WidgetModel("label", name="first", width=80, height=20)
    second = WidgetModel("label", name="second", width=80, height=20)
    third = WidgetModel("label", name="third", width=80, height=20)
    root.add_child(first)
    root.add_child(second)
    root.add_child(third)

    result = group_selection(project, [first, third])

    assert result.changed is False
    assert result.message == "Cannot group selection: layout-managed siblings must be contiguous."
    assert root.children == [first, second, third]


def test_move_into_container_preserves_absolute_position_for_free_layout():
    project, root = _build_project()
    target = WidgetModel("group", name="target", x=100, y=30, width=80, height=80)
    child = WidgetModel("label", name="child", x=10, y=15, width=20, height=10)
    root.add_child(target)
    root.add_child(child)

    result = move_into_container(project, [child], target)

    assert result.changed is True
    assert child.parent is target
    assert (child.display_x, child.display_y) == (10, 15)
    assert (child.x, child.y) == (-90, -15)
    assert result.message == "Moved 1 widget(s) into target."


def test_lift_to_parent_moves_widgets_after_their_container():
    project, root = _build_project()
    container = WidgetModel("group", name="container", x=40, y=50, width=100, height=100)
    child = WidgetModel("label", name="child", x=10, y=12, width=20, height=10)
    container.add_child(child)
    root.add_child(container)

    result = lift_to_parent(project, [child])

    assert result.changed is True
    assert root.children == [container, child]
    assert child.parent is root
    assert (child.x, child.y) == (50, 62)
    assert result.message == "Lifted 1 widget(s) to the parent container."


def test_move_selection_by_step_moves_selected_block():
    project, root = _build_project()
    first = WidgetModel("label", name="first")
    second = WidgetModel("label", name="second")
    third = WidgetModel("label", name="third")
    fourth = WidgetModel("label", name="fourth")
    root.add_child(first)
    root.add_child(second)
    root.add_child(third)
    root.add_child(fourth)

    moved_down = move_selection_by_step(project, [second, third], 1)

    assert moved_down.changed is True
    assert [widget.name for widget in root.children] == ["first", "fourth", "second", "third"]
    assert moved_down.message == "Moved 2 widget(s) down."

    moved_up = move_selection_by_step(project, [second, third], -1)

    assert moved_up.changed is True
    assert [widget.name for widget in root.children] == ["first", "second", "third", "fourth"]
    assert moved_up.message == "Moved 2 widget(s) up."


def test_describe_structure_actions_reports_precise_capabilities():
    project, root = _build_project()
    first = WidgetModel("label", name="first")
    second = WidgetModel("label", name="second")
    target = WidgetModel("group", name="target")
    nested = WidgetModel("label", name="nested")
    target.add_child(nested)
    root.add_child(first)
    root.add_child(second)
    root.add_child(target)

    sibling_state = describe_structure_actions(project, [first, second])

    assert sibling_state.widgets == [first, second]
    assert sibling_state.can_group is True
    assert sibling_state.can_ungroup is False
    assert sibling_state.can_move_into is True
    assert sibling_state.can_lift is False
    assert sibling_state.can_move_up is False
    assert sibling_state.can_move_down is True

    nested_state = describe_structure_actions(project, [nested])

    assert nested_state.widgets == [nested]
    assert nested_state.can_group is False
    assert nested_state.can_ungroup is False
    assert nested_state.can_move_into is True
    assert nested_state.can_lift is True
    assert nested_state.can_move_up is False
    assert nested_state.can_move_down is False


def test_describe_structure_actions_blocks_root_and_locked_selection():
    project, root = _build_project()
    target = WidgetModel("group", name="target")
    locked = WidgetModel("label", name="locked")
    locked.designer_locked = True
    root.add_child(target)
    root.add_child(locked)

    root_state = describe_structure_actions(project, [root])

    assert root_state.widgets == []
    assert root_state.can_group is False
    assert root_state.can_ungroup is False
    assert root_state.can_move_into is False
    assert root_state.can_lift is False
    assert root_state.can_move_up is False
    assert root_state.can_move_down is False

    locked_state = describe_structure_actions(project, [locked])

    assert locked_state.widgets == [locked]
    assert locked_state.can_group is False
    assert locked_state.can_ungroup is False
    assert locked_state.can_move_into is False
    assert locked_state.can_lift is False
    assert locked_state.can_move_up is False
    assert locked_state.can_move_down is False


def test_move_widgets_to_parent_index_reorders_selection_block():
    project, root = _build_project()
    first = WidgetModel("label", name="first")
    second = WidgetModel("label", name="second")
    third = WidgetModel("label", name="third")
    fourth = WidgetModel("label", name="fourth")
    root.add_child(first)
    root.add_child(second)
    root.add_child(third)
    root.add_child(fourth)

    result = move_widgets_to_parent_index(project, [second, third], root, 4)

    assert result.changed is True
    assert result.source == "tree move"
    assert [widget.name for widget in root.children] == ["first", "fourth", "second", "third"]
    assert result.message == "Moved 2 widget(s) in the widget tree."


def test_can_move_widgets_to_parent_index_blocks_noop_and_locked_selection():
    project, root = _build_project()
    first = WidgetModel("label", name="first")
    second = WidgetModel("label", name="second")
    locked = WidgetModel("label", name="locked")
    locked.designer_locked = True
    root.add_child(first)
    root.add_child(second)
    root.add_child(locked)

    assert can_move_widgets_to_parent_index(project, [first], root, 0) is False
    assert can_move_widgets_to_parent_index(project, [locked], root, 0) is False
    assert can_move_widgets_to_parent_index(project, [first], root, 2) is True


def test_move_widgets_to_parent_index_moves_into_new_parent_preserving_absolute_position():
    project, root = _build_project()
    target = WidgetModel("group", name="target", x=100, y=30, width=80, height=80)
    existing = WidgetModel("label", name="existing", x=10, y=10, width=20, height=10)
    child = WidgetModel("label", name="child", x=15, y=25, width=20, height=10)
    target.add_child(existing)
    root.add_child(target)
    root.add_child(child)

    result = move_widgets_to_parent_index(project, [child], target, 0)

    assert result.changed is True
    assert target.children == [child, existing]
    assert child.parent is target
    assert (child.display_x, child.display_y) == (15, 25)
    assert (child.x, child.y) == (-85, -5)


def test_move_widgets_to_parent_index_blocks_noop_position():
    project, root = _build_project()
    first = WidgetModel("label", name="first")
    second = WidgetModel("label", name="second")
    root.add_child(first)
    root.add_child(second)

    result = move_widgets_to_parent_index(project, [first], root, 0)

    assert result.changed is False
    assert result.message == "Cannot move selection in tree: widgets are already in that position."
    assert root.children == [first, second]
