"""Helpers for tracking resource references across designer projects."""

from __future__ import annotations

from dataclasses import dataclass

from .resource_binding import RESOURCE_PROPERTY_TYPES
from .string_resource import DEFAULT_LOCALE, make_string_ref, parse_string_ref
from .widget_registry import WidgetRegistry


_RESOURCE_TYPE_BY_PROPERTY = {value: key for key, value in RESOURCE_PROPERTY_TYPES.items()}


@dataclass(frozen=True)
class ResourceUsageEntry:
    """A single widget property that references a project resource."""

    resource_type: str
    resource_name: str
    page_name: str
    widget_name: str
    property_name: str
    widget_type: str = ""


def iter_widget_resource_usages(widget, page_name=""):
    """Yield resource usage entries for a widget."""
    if widget is None:
        return []

    descriptor = WidgetRegistry.instance().get(widget.widget_type)
    properties = descriptor.get("properties", {})
    entries = []

    for prop_name, prop_info in properties.items():
        resource_type = _RESOURCE_TYPE_BY_PROPERTY.get(prop_info.get("type", ""), "")
        if not resource_type:
            continue

        resource_name = widget.properties.get(prop_name, "")
        if not resource_name:
            continue

        entries.append(
            ResourceUsageEntry(
                resource_type=resource_type,
                resource_name=resource_name,
                page_name=page_name,
                widget_name=widget.name,
                property_name=prop_name,
                widget_type=widget.widget_type,
            )
        )

    text_value = widget.properties.get("text", "")
    string_key = parse_string_ref(text_value)
    if string_key:
        entries.append(
            ResourceUsageEntry(
                resource_type="string",
                resource_name=string_key,
                page_name=page_name,
                widget_name=widget.name,
                property_name="text",
                widget_type=widget.widget_type,
            )
        )

    return entries


def collect_page_resource_usages(page):
    """Collect all resource usages for a page."""
    if page is None:
        return []

    entries = []
    for widget in page.get_all_widgets():
        entries.extend(iter_widget_resource_usages(widget, page_name=page.name))
    return entries


def collect_project_resource_usages(project):
    """Collect all resource usages, grouped by ``(resource_type, resource_name)``."""
    index = {}
    if project is None:
        return index

    for page in getattr(project, "pages", []):
        for entry in collect_page_resource_usages(page):
            key = (entry.resource_type, entry.resource_name)
            index.setdefault(key, []).append(entry)

    return index


def find_resource_usages(project, resource_type, resource_name):
    """Return all usages for a specific resource."""
    if not project or not resource_type or not resource_name:
        return []
    return list(collect_project_resource_usages(project).get((resource_type, resource_name), []))


def collect_unused_resource_names(resource_names, usage_index, resource_type):
    """Return resource names that have no recorded usages."""
    names = list(resource_names or [])
    if not resource_type:
        return []
    return [name for name in names if not usage_index.get((resource_type, name))]


def filter_resource_names(resource_names, usage_index, resource_type, *, search_text="", status="all", missing_names=None):
    """Filter resource names by search text and status."""
    names = list(resource_names or [])
    search_text = str(search_text or "").strip().casefold()
    status = str(status or "all").strip().lower()
    missing_name_set = set(missing_names or ())
    unused_name_set = set(collect_unused_resource_names(names, usage_index, resource_type))

    filtered = []
    for name in names:
        if search_text and search_text not in str(name or "").casefold():
            continue
        if status == "missing" and name not in missing_name_set:
            continue
        if status == "unused" and name not in unused_name_set:
            continue
        filtered.append(name)
    return filtered


def collect_unused_string_keys(string_catalog, usage_index):
    """Return string resource keys that have no recorded usages."""
    if string_catalog is None:
        return []
    return [
        key
        for key in getattr(string_catalog, "all_keys", [])
        if not usage_index.get(("string", key))
    ]


def filter_string_keys(string_catalog, usage_index, *, locale=DEFAULT_LOCALE, search_text="", status="all"):
    """Filter string keys by search text and usage status."""
    if string_catalog is None:
        return []

    keys = list(getattr(string_catalog, "all_keys", []))
    search_text = str(search_text or "").strip().casefold()
    status = str(status or "all").strip().lower()
    unused_key_set = set(collect_unused_string_keys(string_catalog, usage_index))

    filtered = []
    for key in keys:
        value = string_catalog.get(key, locale)
        if search_text:
            haystack = f"{key}\n{value}".casefold()
            if search_text not in haystack:
                continue
        if status == "unused" and key not in unused_key_set:
            continue
        filtered.append(key)
    return filtered


def rewrite_project_resource_references(project, resource_type, old_name, new_name):
    """Rewrite matching widget resource references across project pages."""
    if project is None or not resource_type or not old_name:
        return [], 0

    touched_pages = []
    rewrite_count = 0

    for page in getattr(project, "pages", []):
        page_rewrites = 0
        for widget in page.get_all_widgets():
            for entry in iter_widget_resource_usages(widget, page_name=page.name):
                if entry.resource_type != resource_type or entry.resource_name != old_name:
                    continue
                widget.properties[entry.property_name] = new_name
                page_rewrites += 1

        if page_rewrites:
            touched_pages.append(page)
            rewrite_count += page_rewrites

    return touched_pages, rewrite_count


def rewrite_project_string_references(project, old_key, new_key="", replacement_text=None):
    """Rewrite matching ``@string/`` references across project pages."""
    if project is None or not old_key:
        return [], 0

    old_ref = make_string_ref(old_key)
    if new_key:
        new_value = make_string_ref(new_key)
    elif replacement_text is not None:
        new_value = replacement_text
    else:
        new_value = ""

    touched_pages = []
    rewrite_count = 0

    for page in getattr(project, "pages", []):
        page_rewrites = 0
        for widget in page.get_all_widgets():
            if widget.properties.get("text", "") != old_ref:
                continue
            widget.properties["text"] = new_value
            page_rewrites += 1

        if page_rewrites:
            touched_pages.append(page)
            rewrite_count += page_rewrites

    return touched_pages, rewrite_count
