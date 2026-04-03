#!/usr/bin/env python
"""Run GUI-interaction pytest subset on a real Qt GUI platform.

This wrapper is intended for event-level UI tests (QTest mouse/key interaction)
that should not run under QT_QPA_PLATFORM=offscreen.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TEST_PATH = "ui_designer/tests/ui/test_main_window_file_flow.py"
DEFAULT_FILTER = (
    "status_panel_top_splitter_handle_drag_with_qtest or "
    "workspace_left_nav_buttons_switch_panels_via_click or "
    "workspace_inspector_tabs_switch_via_tabbar_click or "
    "bottom_toggle_button_click_hides_and_shows_bottom_panel"
)


def _parse_args() -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(
        description="Run GUI interaction tests with a non-offscreen Qt platform",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=[DEFAULT_TEST_PATH],
        help="Optional pytest paths/node ids (default: GUI interaction test module)",
    )
    parser.add_argument(
        "--pytest-filter",
        default=DEFAULT_FILTER,
        help="pytest -k expression for selecting GUI interaction tests",
    )
    parser.add_argument(
        "--qt-platform",
        default="xcb",
        help="QT_QPA_PLATFORM value (default: xcb)",
    )
    parser.add_argument(
        "--xvfb",
        choices=["auto", "on", "off"],
        default="auto",
        help="Use xvfb-run on Linux (default: auto)",
    )
    parser.add_argument(
        "--keep-basetemp",
        action="store_true",
        help="Keep generated pytest temp directory",
    )
    args, extra = parser.parse_known_args()
    if extra and extra[0] == "--":
        extra = extra[1:]
    return args, extra


def _should_use_xvfb(mode: str) -> bool:
    if mode == "on":
        return True
    if mode == "off":
        return False
    return sys.platform.startswith("linux")


def main() -> int:
    args, passthrough = _parse_args()

    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = str(args.qt_platform or "xcb").strip() or "xcb"

    command = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "ui_designer" / "run_pytest.py"),
    ]
    command.extend(args.paths)
    if args.keep_basetemp:
        command.append("--keep-basetemp")
    command.extend(["--", "-k", args.pytest_filter])
    command.extend(passthrough)

    if _should_use_xvfb(args.xvfb):
        command = ["xvfb-run", "-a", *command]

    result = subprocess.run(command, cwd=REPO_ROOT, env=env, check=False)
    return int(result.returncode)


if __name__ == "__main__":
    sys.exit(main())
