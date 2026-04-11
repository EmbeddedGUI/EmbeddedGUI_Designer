"""Shared test-only page construction helpers."""

from __future__ import annotations

from ui_designer.model.page import Page
from ui_designer.model.widget_model import WidgetModel
from ui_designer.utils.scaffold import require_page_root


def build_test_page(name="main_page", *, screen_width=240, screen_height=320):
    """Build a default Page model for tests."""
    return Page.create_default(name, screen_width=screen_width, screen_height=screen_height)


def build_test_page_with_root(page_name="main_page", *, screen_width=240, screen_height=320):
    """Build a default Page model and return it with its root widget."""
    page = build_test_page(page_name, screen_width=screen_width, screen_height=screen_height)
    root = require_page_root(page, page_name)
    return page, root


def build_test_page_with_root_widget(
    page_name="main_page",
    root_widget_type="group",
    *,
    root_name="root_group",
    x=0,
    y=0,
    width=240,
    height=320,
):
    """Build a Page model with a shared custom root widget and return both."""
    root = WidgetModel(root_widget_type, name=root_name, x=x, y=y, width=width, height=height)
    page = build_test_page_from_root(
        page_name,
        root=root,
        screen_width=width,
        screen_height=height,
    )
    return page, root


def build_test_page_from_root(name="main_page", root=None, *, screen_width=240, screen_height=320):
    """Build a Page model with a caller-supplied or default root widget."""
    if root is None:
        root = WidgetModel("group", name="root_group", x=0, y=0, width=screen_width, height=screen_height)
    return Page(file_path=f"layout/{name}.xml", root_widget=root)


def build_test_pages(*names, screen_width=240, screen_height=320):
    """Build multiple default Page models for tests."""
    return tuple(
        build_test_page(name, screen_width=screen_width, screen_height=screen_height)
        for name in names
    )


def add_test_widget(
    page,
    widget_type="label",
    *,
    name="title",
    x=12,
    y=16,
    width=100,
    height=24,
):
    """Attach a basic widget to a test page and return it."""
    widget = WidgetModel(widget_type, name=name, x=x, y=y, width=width, height=height)
    root = require_page_root(page)
    root.add_child(widget)
    return widget


def build_test_page_with_widget(
    page_name="main_page",
    widget_type="label",
    *,
    screen_width=240,
    screen_height=320,
    **widget_kwargs,
):
    """Build a default Page with one attached widget."""
    page, _root = build_test_page_with_root(
        page_name,
        screen_width=screen_width,
        screen_height=screen_height,
    )
    widget = add_test_widget(page, widget_type, **widget_kwargs)
    return page, widget


def build_test_page_with_title(page_name="main_page", *, screen_width=240, screen_height=320, **widget_kwargs):
    """Build a default Page with a title label attached."""
    return build_test_page_with_widget(
        page_name,
        "label",
        screen_width=screen_width,
        screen_height=screen_height,
        **widget_kwargs,
    )
