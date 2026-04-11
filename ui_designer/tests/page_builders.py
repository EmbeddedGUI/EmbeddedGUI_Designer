"""Shared test-only page construction helpers."""

from __future__ import annotations

from ui_designer.model.page import Page
from ui_designer.model.widget_model import WidgetModel
from ui_designer.utils.scaffold import (
    add_page_widget,
    build_page_model_with_root_widget,
    build_page_model_with_widget,
    build_page_model_with_widgets,
    require_page_root,
)


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
    return build_page_model_with_root_widget(
        page_name,
        root_widget_type,
        root_name=root_name,
        x=x,
        y=y,
        width=width,
        height=height,
    )


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
    return add_page_widget(
        page,
        widget_type,
        name=name,
        x=x,
        y=y,
        width=width,
        height=height,
    )


def build_test_page_with_widget(
    page_name="main_page",
    widget_type="label",
    *,
    screen_width=240,
    screen_height=320,
    root_widget_type="group",
    root_name="root_group",
    root_x=0,
    root_y=0,
    **widget_kwargs,
):
    """Build a default Page with one attached widget."""
    return build_page_model_with_widget(
        page_name,
        widget_type,
        screen_width=screen_width,
        screen_height=screen_height,
        root_widget_type=root_widget_type,
        root_name=root_name,
        root_x=root_x,
        root_y=root_y,
        **widget_kwargs,
    )


def build_test_page_with_widgets(
    page_name="main_page",
    *,
    screen_width=240,
    screen_height=320,
    root_widget_type="group",
    root_name="root_group",
    root_x=0,
    root_y=0,
    widgets=None,
):
    """Build a default Page with multiple attached widgets."""
    return build_page_model_with_widgets(
        page_name,
        screen_width=screen_width,
        screen_height=screen_height,
        root_widget_type=root_widget_type,
        root_name=root_name,
        root_x=root_x,
        root_y=root_y,
        widgets=widgets,
    )


def build_test_page_with_title(page_name="main_page", *, screen_width=240, screen_height=320, **widget_kwargs):
    """Build a default Page with a title label attached."""
    return build_test_page_with_widget(
        page_name,
        "label",
        screen_width=screen_width,
        screen_height=screen_height,
        **widget_kwargs,
    )
