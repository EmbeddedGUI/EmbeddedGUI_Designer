"""Shared fixtures for ui_designer tests."""

import gc
import os
import sys
import pytest

from .project_builders import build_test_project
from .qt_test_utils import close_widget_safely, drain_qt_events, ensure_qapp

# Ensure the repository root is on sys.path so `ui_designer` and root scripts import correctly
_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_UI_DESIGNER_DIR = os.path.dirname(_TESTS_DIR)
_SCRIPTS_DIR = os.path.dirname(_UI_DESIGNER_DIR)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

TEST_DATA_DIR = os.path.join(_TESTS_DIR, "test_data")


def _cleanup_qt_state():
    try:
        from PyQt5.QtGui import QPixmapCache
        from PyQt5.QtWidgets import QApplication
    except ImportError:
        return

    app = QApplication.instance()
    if app is None:
        return

    try:
        app.setQuitOnLastWindowClosed(False)
    except Exception:
        pass

    drain_qt_events(app)
    for widget in list(QApplication.topLevelWidgets()):
        close_widget_safely(widget)
    drain_qt_events(app)
    try:
        QPixmapCache.clear()
    except Exception:
        pass
    gc.collect()
    drain_qt_events(app)


@pytest.fixture
def test_data_dir():
    """Path to the test_data/ directory with static fixtures."""
    return TEST_DATA_DIR


@pytest.fixture(autouse=True)
def reset_widget_counter():
    """Reset WidgetModel._counter before each test to avoid state leaks."""
    from ui_designer.model.widget_model import WidgetModel
    WidgetModel.reset_counter()
    yield
    WidgetModel.reset_counter()


@pytest.fixture(autouse=True)
def cleanup_qt_widgets():
    """Keep the shared QApplication free of leaked top-level widgets across tests."""
    _cleanup_qt_state()
    yield
    _cleanup_qt_state()


@pytest.fixture
def qapp():
    """Return the shared QApplication for Qt UI tests."""
    app = ensure_qapp()
    yield app
    drain_qt_events(app)


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    """Bind DesignerConfig to a per-test temporary config path."""
    from ui_designer.model.config import DesignerConfig

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_path = config_dir / "config.json"
    monkeypatch.setattr("ui_designer.model.config._get_config_dir", lambda: str(config_dir))
    monkeypatch.setattr("ui_designer.model.config._get_config_path", lambda: str(config_path))
    DesignerConfig._instance = None
    config = DesignerConfig.instance()
    yield config
    DesignerConfig._instance = None


@pytest.fixture
def simple_label():
    """Create a basic label widget."""
    from ui_designer.model.widget_model import WidgetModel
    return WidgetModel("label", name="test_label", x=10, y=20, width=100, height=30)


@pytest.fixture
def simple_button():
    """Create a basic button widget."""
    from ui_designer.model.widget_model import WidgetModel
    return WidgetModel("button", name="test_button", x=0, y=0, width=80, height=40)


@pytest.fixture
def simple_image():
    """Create a basic image widget with an image file set."""
    from ui_designer.model.widget_model import WidgetModel
    w = WidgetModel("image", name="test_image", x=0, y=0, width=64, height=64)
    w.properties["image_file"] = "star.png"
    w.properties["image_format"] = "rgb565"
    w.properties["image_alpha"] = "4"
    return w


@pytest.fixture
def container_group():
    """Create a group container with two children."""
    from ui_designer.model.widget_model import WidgetModel
    group = WidgetModel("group", name="root_group", x=0, y=0, width=240, height=320)
    label = WidgetModel("label", name="child_label", x=10, y=10, width=100, height=30)
    button = WidgetModel("button", name="child_button", x=10, y=50, width=100, height=40)
    group.add_child(label)
    group.add_child(button)
    return group


@pytest.fixture
def linearlayout_vertical():
    """Create a vertical LinearLayout with 3 children."""
    from ui_designer.model.widget_model import WidgetModel
    layout = WidgetModel("linearlayout", name="ll_v", x=0, y=0, width=200, height=300)
    layout.properties["orientation"] = "vertical"
    layout.properties["align_type"] = "EGUI_ALIGN_CENTER"
    for i in range(3):
        child = WidgetModel("label", name=f"item_{i}", x=0, y=0, width=100, height=40)
        layout.add_child(child)
    return layout


@pytest.fixture
def linearlayout_horizontal():
    """Create a horizontal LinearLayout with 3 children."""
    from ui_designer.model.widget_model import WidgetModel
    layout = WidgetModel("linearlayout", name="ll_h", x=0, y=0, width=300, height=100)
    layout.properties["orientation"] = "horizontal"
    layout.properties["align_type"] = "EGUI_ALIGN_CENTER"
    for i in range(3):
        child = WidgetModel("label", name=f"item_{i}", x=0, y=0, width=80, height=30)
        layout.add_child(child)
    return layout


@pytest.fixture
def simple_page():
    """Create a Page with a root group containing one label."""
    from ui_designer.model.widget_model import WidgetModel
    from ui_designer.model.page import Page
    root = WidgetModel("group", name="root_group", x=0, y=0, width=240, height=320)
    label = WidgetModel("label", name="my_label", x=10, y=10, width=100, height=30)
    label.properties["text"] = "Hello"
    root.add_child(label)
    page = Page(file_path="layout/main_page.xml", root_widget=root)
    return page


@pytest.fixture
def simple_project(simple_page):
    """Create a Project with one page."""
    proj = build_test_project("TestApp")
    proj.pages = [simple_page]
    proj.startup_page = simple_page.name
    return proj


@pytest.fixture
def multi_page_project():
    """Create a Project with two pages for multi-page testing."""
    from ui_designer.model.widget_model import WidgetModel
    proj = build_test_project("MultiPageApp", pages=["main_page", "settings"])

    page1 = proj.get_page_by_name("main_page")
    page2 = proj.get_page_by_name("settings")
    assert page1 is not None
    assert page2 is not None

    root1 = page1.root_widget
    root2 = page2.root_widget
    assert root1 is not None
    assert root2 is not None

    label1 = WidgetModel("label", name="title", x=10, y=10, width=220, height=30)
    label1.properties["text"] = "Page One"
    root1.add_child(label1)

    btn = WidgetModel("button", name="back_btn", x=10, y=10, width=100, height=40)
    btn.properties["text"] = "Back"
    btn.on_click = "on_back_click"
    root2.add_child(btn)
    return proj


@pytest.fixture
def string_catalog():
    """Create a StringResourceCatalog with default + Chinese locale."""
    from ui_designer.model.string_resource import StringResourceCatalog
    cat = StringResourceCatalog()
    cat.set("app_name", "My App", "")
    cat.set("greeting", "Hello", "")
    cat.set("app_name", "My App ZH", "zh")
    cat.set("greeting", "Ni Hao", "zh")
    return cat


@pytest.fixture
def tmp_project_dir(tmp_path):
    """Create a temporary directory structure simulating a project dir."""
    return tmp_path

