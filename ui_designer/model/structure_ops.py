from dataclasses import dataclass, field

from ..engine.layout_engine import compute_layout
from .widget_model import WidgetModel
from .widget_name import make_unique_widget_name


@dataclass(frozen=True)
class ContainerChoice:
    label: str
    widget: WidgetModel


@dataclass
class StructureOperationResult:
    changed: bool = False
    source: str = ""
    message: str = ""
    widgets: list = field(default_factory=list)
    primary: WidgetModel = None


@dataclass
class StructureActionState:
    widgets: list = field(default_factory=list)
    can_group: bool = False
    can_ungroup: bool = False
    can_move_into: bool = False
    can_lift: bool = False
    can_move_up: bool = False
    can_move_down: bool = False


def _failure(message):
    return StructureOperationResult(changed=False, message=message)


def _root_widgets(project_like):
    if project_like is None:
        return []
    return list(getattr(project_like, "root_widgets", []) or [])


def _iter_widgets(project_like):
    for root in _root_widgets(project_like):
        yield from root.get_all_widgets_flat()


def _recompute_layout(project_like):
    if project_like is None:
        return
    compute_layout(project_like)


def _unique_widgets(widgets):
    result = []
    seen = set()
    for widget in widgets or []:
        if widget is None or id(widget) in seen:
            continue
        seen.add(id(widget))
        result.append(widget)
    return result


def _top_level_widgets(widgets, exclude_roots=None):
    widgets = _unique_widgets(widgets)
    selected_ids = {id(widget) for widget in widgets}
    excluded_root_ids = {id(widget) for widget in (exclude_roots or [])}
    result = []
    for widget in widgets:
        if id(widget) in excluded_root_ids:
            continue
        parent = widget.parent
        skip = False
        while parent is not None:
            if id(parent) in selected_ids:
                skip = True
                break
            parent = parent.parent
        if not skip:
            result.append(widget)
    return result


def _tree_order_map(project_like):
    return {id(widget): index for index, widget in enumerate(_iter_widgets(project_like))}


def _sort_by_tree_order(project_like, widgets):
    order_map = _tree_order_map(project_like)
    return sorted(
        _unique_widgets(widgets),
        key=lambda widget: (order_map.get(id(widget), 1 << 30), getattr(widget, "name", "")),
    )


def _existing_widget_names(project_like, exclude_widgets=None):
    excluded_ids = {id(widget) for widget in (exclude_widgets or []) if widget is not None}
    names = set()
    for widget in _iter_widgets(project_like):
        if id(widget) in excluded_ids:
            continue
        if getattr(widget, "name", ""):
            names.add(widget.name)
    return names


def _parent_uses_layout(parent):
    if parent is None:
        return False
    return WidgetModel._get_type_info(parent.widget_type).get("layout_func") is not None


def _insert_child(parent, index, child):
    child.parent = parent
    parent.children.insert(index, child)


def _remove_child(parent, child):
    parent.children.remove(child)
    child.parent = None


def _subtree_ids(widget):
    return {id(current) for current in widget.get_all_widgets_flat()}


def _has_locked_widgets(widgets):
    return any(bool(getattr(widget, "designer_locked", False)) for widget in widgets)


def _widget_path(widget):
    names = []
    current = widget
    while current is not None:
        names.append(current.name or current.widget_type)
        current = current.parent
    return " / ".join(reversed(names))


def available_move_targets(project_like, widgets):
    roots = _root_widgets(project_like)
    selected = _sort_by_tree_order(project_like, _top_level_widgets(widgets, exclude_roots=roots))
    if not selected:
        return []

    excluded_ids = set()
    for widget in selected:
        excluded_ids.update(_subtree_ids(widget))

    result = []
    for widget in _iter_widgets(project_like):
        if not widget.is_container or id(widget) in excluded_ids:
            continue
        if all(selected_widget.parent is widget for selected_widget in selected):
            continue
        result.append(ContainerChoice(f"{_widget_path(widget)} ({widget.widget_type})", widget))
    return result


def _normalized_selection(project_like, widgets):
    roots = _root_widgets(project_like)
    return _sort_by_tree_order(project_like, _top_level_widgets(widgets, exclude_roots=roots))


def _shared_parent(widgets):
    if not widgets:
        return None
    parent = widgets[0].parent
    if parent is None:
        return None
    if any(widget.parent is not parent for widget in widgets[1:]):
        return None
    return parent


def _can_group_widgets(project_like, widgets):
    if len(widgets) < 2 or _has_locked_widgets(widgets):
        return False

    parent = _shared_parent(widgets)
    if parent is None:
        return False

    if _parent_uses_layout(parent):
        indices = [parent.children.index(widget) for widget in widgets]
        return indices == list(range(min(indices), max(indices) + 1))
    return True


def _can_ungroup_widgets(widgets):
    if not widgets or _has_locked_widgets(widgets):
        return False
    return all(widget.widget_type == "group" and widget.parent is not None for widget in widgets)


def _can_move_into_container(project_like, widgets):
    return bool(widgets) and not _has_locked_widgets(widgets) and bool(available_move_targets(project_like, widgets))


def _can_lift_widgets(widgets):
    if not widgets or _has_locked_widgets(widgets):
        return False
    return all(widget.parent is not None and widget.parent.parent is not None for widget in widgets)


def _can_move_by_step(widgets, step):
    if not widgets or _has_locked_widgets(widgets) or step not in (-1, 1):
        return False

    grouped = {}
    for widget in widgets:
        if widget.parent is None:
            continue
        grouped.setdefault(id(widget.parent), (widget.parent, set()))[1].add(widget)

    if not grouped:
        return False

    for parent, selected_set in grouped.values():
        children = parent.children
        if step < 0:
            for index in range(1, len(children)):
                if children[index] in selected_set and children[index - 1] not in selected_set:
                    return True
        else:
            for index in range(len(children) - 2, -1, -1):
                if children[index] in selected_set and children[index + 1] not in selected_set:
                    return True
    return False


def describe_structure_actions(project_like, widgets):
    widgets = _normalized_selection(project_like, widgets)
    return StructureActionState(
        widgets=widgets,
        can_group=_can_group_widgets(project_like, widgets),
        can_ungroup=_can_ungroup_widgets(widgets),
        can_move_into=_can_move_into_container(project_like, widgets),
        can_lift=_can_lift_widgets(widgets),
        can_move_up=_can_move_by_step(widgets, -1),
        can_move_down=_can_move_by_step(widgets, 1),
    )


def group_selection(project_like, widgets, base_name="group"):
    roots = _root_widgets(project_like)
    widgets = _sort_by_tree_order(project_like, _top_level_widgets(widgets, exclude_roots=roots))
    if len(widgets) < 2:
        return _failure("Cannot group selection: select at least 2 widgets.")
    if _has_locked_widgets(widgets):
        return _failure("Cannot group selection: locked widgets cannot be regrouped.")

    parent = widgets[0].parent
    if parent is None or any(widget.parent is not parent for widget in widgets[1:]):
        return _failure("Cannot group selection: selected widgets must share the same direct parent.")

    if _parent_uses_layout(parent):
        indices = [parent.children.index(widget) for widget in widgets]
        expected = list(range(min(indices), max(indices) + 1))
        if indices != expected:
            return _failure("Cannot group selection: layout-managed siblings must be contiguous.")

    _recompute_layout(project_like)

    min_x = min(widget.display_x for widget in widgets)
    min_y = min(widget.display_y for widget in widgets)
    max_x = max(widget.display_x + widget.width for widget in widgets)
    max_y = max(widget.display_y + widget.height for widget in widgets)

    existing_names = _existing_widget_names(project_like)
    group_name = make_unique_widget_name(base_name, existing_names)
    existing_names.add(group_name)

    group = WidgetModel(
        "group",
        name=group_name,
        x=0,
        y=0,
        width=max_x - min_x,
        height=max_y - min_y,
    )

    if not _parent_uses_layout(parent):
        group.x = min_x - parent.display_x
        group.y = min_y - parent.display_y

    insert_index = min(parent.children.index(widget) for widget in widgets)
    _insert_child(parent, insert_index, group)

    for widget in widgets:
        abs_x = widget.display_x
        abs_y = widget.display_y
        _remove_child(parent, widget)
        widget.x = abs_x - min_x
        widget.y = abs_y - min_y
        group.add_child(widget)

    _recompute_layout(project_like)
    return StructureOperationResult(
        changed=True,
        source="group selection",
        message=f"Grouped {len(widgets)} widget(s) into {group.name}.",
        widgets=[group],
        primary=group,
    )


def ungroup_selection(project_like, widgets):
    roots = _root_widgets(project_like)
    widgets = _sort_by_tree_order(project_like, _top_level_widgets(widgets, exclude_roots=roots))
    if not widgets:
        return _failure("Cannot ungroup selection: no groups are selected.")
    if any(widget.widget_type != "group" for widget in widgets):
        return _failure("Cannot ungroup selection: selection must only include groups.")
    if _has_locked_widgets(widgets):
        return _failure("Cannot ungroup selection: locked groups cannot be regrouped.")
    if any(widget.parent is None for widget in widgets):
        return _failure("Cannot ungroup selection: the root group cannot be ungrouped.")

    _recompute_layout(project_like)

    lifted_children = []
    for group in widgets:
        parent = group.parent
        parent_uses_layout = _parent_uses_layout(parent)
        parent_abs_x = getattr(parent, "display_x", 0)
        parent_abs_y = getattr(parent, "display_y", 0)
        insert_index = parent.children.index(group)
        children = list(group.children)
        child_positions = [(child, child.display_x, child.display_y) for child in children]

        _remove_child(parent, group)
        for offset, (child, abs_x, abs_y) in enumerate(child_positions):
            _remove_child(group, child)
            if parent_uses_layout:
                child.x = 0
                child.y = 0
            else:
                child.x = abs_x - parent_abs_x
                child.y = abs_y - parent_abs_y
            _insert_child(parent, insert_index + offset, child)
            lifted_children.append(child)

    _recompute_layout(project_like)
    message = f"Ungrouped {len(widgets)} group(s)."
    if lifted_children:
        message = f"Ungrouped {len(widgets)} group(s) into {len(lifted_children)} widget(s)."
    primary = lifted_children[-1] if lifted_children else None
    return StructureOperationResult(
        changed=True,
        source="ungroup selection",
        message=message,
        widgets=lifted_children,
        primary=primary,
    )


def move_into_container(project_like, widgets, target_container):
    roots = _root_widgets(project_like)
    widgets = _sort_by_tree_order(project_like, _top_level_widgets(widgets, exclude_roots=roots))
    if not widgets:
        return _failure("Cannot move into container: no widgets are selected.")
    if _has_locked_widgets(widgets):
        return _failure("Cannot move into container: locked widgets cannot be moved.")
    if target_container is None or not getattr(target_container, "is_container", False):
        return _failure("Cannot move into container: choose a valid target container.")

    excluded_ids = set()
    for widget in widgets:
        excluded_ids.update(_subtree_ids(widget))
    if id(target_container) in excluded_ids:
        return _failure("Cannot move into container: target container is inside the current selection.")

    _recompute_layout(project_like)

    target_uses_layout = _parent_uses_layout(target_container)
    target_abs_x = getattr(target_container, "display_x", 0)
    target_abs_y = getattr(target_container, "display_y", 0)

    for widget in widgets:
        abs_x = widget.display_x
        abs_y = widget.display_y
        if widget.parent is not None:
            _remove_child(widget.parent, widget)
        if target_uses_layout:
            widget.x = 0
            widget.y = 0
        else:
            widget.x = abs_x - target_abs_x
            widget.y = abs_y - target_abs_y
        target_container.add_child(widget)

    _recompute_layout(project_like)
    return StructureOperationResult(
        changed=True,
        source="move into container",
        message=f"Moved {len(widgets)} widget(s) into {target_container.name}.",
        widgets=widgets,
        primary=widgets[-1],
    )


def _prepare_move_to_parent_index(project_like, widgets, target_parent, target_index):
    roots = _root_widgets(project_like)
    widgets = _sort_by_tree_order(project_like, _top_level_widgets(widgets, exclude_roots=roots))
    if not widgets:
        return widgets, None, "Cannot move selection in tree: no widgets are selected."
    if _has_locked_widgets(widgets):
        return widgets, None, "Cannot move selection in tree: locked widgets cannot be moved."
    if target_parent is None or not getattr(target_parent, "is_container", False):
        return widgets, None, "Cannot move selection in tree: choose a valid target container."

    excluded_ids = set()
    for widget in widgets:
        excluded_ids.update(_subtree_ids(widget))
    if id(target_parent) in excluded_ids:
        return widgets, None, "Cannot move selection in tree: target container is inside the current selection."

    children = list(getattr(target_parent, "children", []) or [])
    if target_index is None:
        target_index = len(children)
    try:
        target_index = int(target_index)
    except (TypeError, ValueError):
        return widgets, None, "Cannot move selection in tree: target position is invalid."
    if target_index < 0 or target_index > len(children):
        return widgets, None, "Cannot move selection in tree: target position is invalid."

    selected_ids = {id(widget) for widget in widgets}
    adjusted_index = target_index - sum(1 for child in children[:target_index] if id(child) in selected_ids)
    adjusted_index = max(0, min(adjusted_index, len([child for child in children if id(child) not in selected_ids])))

    if all(widget.parent is target_parent for widget in widgets):
        remaining = [child for child in children if id(child) not in selected_ids]
        new_children = remaining[:adjusted_index] + widgets + remaining[adjusted_index:]
        if new_children == children:
            return widgets, None, "Cannot move selection in tree: widgets are already in that position."
    return widgets, adjusted_index, ""


def can_move_widgets_to_parent_index(project_like, widgets, target_parent, target_index):
    _, adjusted_index, message = _prepare_move_to_parent_index(project_like, widgets, target_parent, target_index)
    return adjusted_index is not None and not message


def move_widgets_to_parent_index(project_like, widgets, target_parent, target_index):
    widgets, adjusted_index, message = _prepare_move_to_parent_index(
        project_like, widgets, target_parent, target_index
    )
    if adjusted_index is None:
        return _failure(message)

    _recompute_layout(project_like)

    positions = [
        (widget, widget.parent, getattr(widget, "display_x", widget.x), getattr(widget, "display_y", widget.y))
        for widget in widgets
    ]
    target_uses_layout = _parent_uses_layout(target_parent)
    target_abs_x = getattr(target_parent, "display_x", 0)
    target_abs_y = getattr(target_parent, "display_y", 0)

    for widget, _, _, _ in positions:
        if widget.parent is not None:
            _remove_child(widget.parent, widget)

    insert_index = adjusted_index
    for widget, source_parent, abs_x, abs_y in positions:
        if source_parent is not target_parent:
            if target_uses_layout:
                widget.x = 0
                widget.y = 0
            else:
                widget.x = abs_x - target_abs_x
                widget.y = abs_y - target_abs_y
        _insert_child(target_parent, insert_index, widget)
        insert_index += 1

    _recompute_layout(project_like)
    return StructureOperationResult(
        changed=True,
        source="tree move",
        message=f"Moved {len(widgets)} widget(s) in the widget tree.",
        widgets=widgets,
        primary=widgets[-1],
    )


def lift_to_parent(project_like, widgets):
    roots = _root_widgets(project_like)
    widgets = _sort_by_tree_order(project_like, _top_level_widgets(widgets, exclude_roots=roots))
    if not widgets:
        return _failure("Cannot lift selection: no widgets are selected.")
    if _has_locked_widgets(widgets):
        return _failure("Cannot lift selection: locked widgets cannot be moved.")
    if any(widget.parent is None or widget.parent.parent is None for widget in widgets):
        return _failure("Cannot lift selection: selected widgets already belong to the top container.")

    _recompute_layout(project_like)

    parent_order = []
    grouped = {}
    for widget in widgets:
        parent = widget.parent
        key = id(parent)
        if key not in grouped:
            grouped[key] = (parent, [])
            parent_order.append(key)
        grouped[key][1].append(widget)

    lifted = []
    for key in parent_order:
        parent, siblings = grouped[key]
        grandparent = parent.parent
        target_uses_layout = _parent_uses_layout(grandparent)
        target_abs_x = getattr(grandparent, "display_x", 0)
        target_abs_y = getattr(grandparent, "display_y", 0)
        insert_index = grandparent.children.index(parent) + 1
        positions = [(widget, widget.display_x, widget.display_y) for widget in siblings]
        for widget, abs_x, abs_y in positions:
            _remove_child(parent, widget)
            if target_uses_layout:
                widget.x = 0
                widget.y = 0
            else:
                widget.x = abs_x - target_abs_x
                widget.y = abs_y - target_abs_y
            _insert_child(grandparent, insert_index, widget)
            insert_index += 1
            lifted.append(widget)

    _recompute_layout(project_like)
    return StructureOperationResult(
        changed=True,
        source="lift to parent",
        message=f"Lifted {len(lifted)} widget(s) to the parent container.",
        widgets=lifted,
        primary=lifted[-1] if lifted else None,
    )


def move_selection_by_step(project_like, widgets, step):
    roots = _root_widgets(project_like)
    widgets = _sort_by_tree_order(project_like, _top_level_widgets(widgets, exclude_roots=roots))
    if not widgets:
        return _failure("Cannot reorder selection: no widgets are selected.")
    if _has_locked_widgets(widgets):
        return _failure("Cannot reorder selection: locked widgets cannot be reordered.")
    if step not in (-1, 1):
        return _failure("Cannot reorder selection: unsupported move step.")

    grouped = {}
    for widget in widgets:
        if widget.parent is None:
            continue
        grouped.setdefault(id(widget.parent), (widget.parent, set()))[1].add(widget)

    if not grouped:
        return _failure("Cannot reorder selection: selected widgets do not have a movable parent.")

    moved = False
    for parent, selected_set in grouped.values():
        children = parent.children
        if step < 0:
            for index in range(1, len(children)):
                if children[index] in selected_set and children[index - 1] not in selected_set:
                    children[index - 1], children[index] = children[index], children[index - 1]
                    moved = True
        else:
            for index in range(len(children) - 2, -1, -1):
                if children[index] in selected_set and children[index + 1] not in selected_set:
                    children[index], children[index + 1] = children[index + 1], children[index]
                    moved = True

    if not moved:
        direction = "up" if step < 0 else "down"
        boundary = "top" if step < 0 else "bottom"
        return _failure(f"Cannot move selection {direction}: selected widgets are already at the {boundary}.")

    _recompute_layout(project_like)
    direction = "up" if step < 0 else "down"
    return StructureOperationResult(
        changed=True,
        source=f"move {direction}",
        message=f"Moved {len(widgets)} widget(s) {direction}.",
        widgets=_sort_by_tree_order(project_like, widgets),
        primary=widgets[-1],
    )
