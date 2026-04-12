"""Shared ``SimpleNamespace``-backed test doubles."""

from __future__ import annotations

from types import SimpleNamespace


def build_namespace_stub(**attrs):
    return SimpleNamespace(**attrs)


def build_project_stub(*, pages=None, **attrs):
    return build_namespace_stub(pages=list(pages or []), **attrs)


def build_widget_stub(*, properties=None, **extra_properties):
    resolved_properties = dict(properties or {})
    resolved_properties.update(extra_properties)
    return build_namespace_stub(properties=resolved_properties)


def build_overwrite_diff(*, existing_count=0, new_count=0, added_count=0, removed_count=0, **attrs):
    return build_namespace_stub(
        existing_count=existing_count,
        new_count=new_count,
        added_count=added_count,
        removed_count=removed_count,
        **attrs,
    )
