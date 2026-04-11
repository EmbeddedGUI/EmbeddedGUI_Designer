"""Shared test-only page construction helpers."""

from __future__ import annotations

from ui_designer.model.page import Page
from ui_designer.model.widget_model import WidgetModel


def build_test_page(name="main_page", *, screen_width=240, screen_height=320):
    """Build a default Page model for tests."""
    return Page.create_default(name, screen_width=screen_width, screen_height=screen_height)


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
    page.root_widget.add_child(widget)
    return widget


def build_test_page_with_title(name="main_page", *, screen_width=240, screen_height=320):
    """Build a default Page with a title label attached."""
    page = build_test_page(name, screen_width=screen_width, screen_height=screen_height)
    title = add_test_widget(page)
    return page, title
