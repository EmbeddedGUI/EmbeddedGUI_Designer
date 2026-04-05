"""Focused UI tests for status center recent-actions visibility simplification."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtWidgets import QApplication

    _has_pyqt5 = True
except ImportError:
    _has_pyqt5 = False

_skip_no_qt = pytest.mark.skipif(not _has_pyqt5, reason="PyQt5 not available")


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
    app.processEvents()


def _menu_labels(menu):
    return [action.text() for action in menu.actions() if not action.isSeparator()]


@_skip_no_qt
def test_status_center_hides_recent_actions_summary_but_keeps_repeat_history_metadata(qapp):
    from ui_designer.ui.status_center_panel import StatusCenterPanel

    panel = StatusCenterPanel()
    panel._set_last_action(
        "open_assets_panel",
        [
            "open_assets_panel",
            "open_components_panel",
            "open_structure_panel",
            "open_project_panel",
        ],
    )

    assert panel._recent_actions_label.isHidden() is True
    assert panel._recent_actions_label.text() == "Recent actions (4): Assets, Components, Structure, +1 more."
    assert panel._recent_actions_label.toolTip() == "4 recent actions: Assets, Components, Structure, Project"
    assert panel._recent_actions_label.accessibleName() == (
        "Recent actions summary: 4 recent actions tracked. Assets, Components, Structure, Project."
    )
    assert panel._repeat_action_button.text() == "Repeat Assets"
    assert panel._repeat_action_button.isEnabled() is True
    assert _menu_labels(panel._repeat_action_menu) == [
        "Assets",
        "Components",
        "Structure",
        "Project",
        "Clear Recent Actions (4)",
    ]
    panel.deleteLater()
