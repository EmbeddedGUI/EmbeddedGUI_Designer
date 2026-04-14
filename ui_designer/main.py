"""EmbeddedGUI Visual UI Designer entry point."""

from __future__ import annotations

import argparse
import contextlib
import io
import os
import sys


_PREVIOUS_QT_MESSAGE_HANDLER = None
_QT_MESSAGE_FILTER_INSTALLED = False


def _suppress_noisy_qt_platform_logs():
    """Mute verbose Qt platform debug categories unless the user already chose rules."""
    rules = str(os.environ.get("QT_LOGGING_RULES", "") or "").strip()
    quiet_rules = [
        "qt.qpa.windows.debug=false",
        "qt.qpa.events.debug=false",
    ]
    if not rules:
        os.environ["QT_LOGGING_RULES"] = ";".join(quiet_rules)
        return

    normalized = rules.lower()
    missing = []
    for rule in quiet_rules:
        category = rule.split("=", 1)[0].strip().lower()
        if category not in normalized:
            missing.append(rule)
    if missing:
        os.environ["QT_LOGGING_RULES"] = ";".join([rules, *missing])


def _should_suppress_qt_message(message: str) -> bool:
    text = str(message or "")
    return "External WM_DESTROY received for" in text


def _install_qt_message_filter():
    global _PREVIOUS_QT_MESSAGE_HANDLER, _QT_MESSAGE_FILTER_INSTALLED
    if _QT_MESSAGE_FILTER_INSTALLED:
        return

    try:
        from PyQt5.QtCore import qInstallMessageHandler
    except ImportError:
        return

    def _handler(msg_type, context, message):
        if _should_suppress_qt_message(message):
            return
        if callable(_PREVIOUS_QT_MESSAGE_HANDLER):
            _PREVIOUS_QT_MESSAGE_HANDLER(msg_type, context, message)

    _PREVIOUS_QT_MESSAGE_HANDLER = qInstallMessageHandler(_handler)
    _QT_MESSAGE_FILTER_INSTALLED = True


def _suppress_qfluentwidgets_tip():
    """Import qfluentwidgets while suppressing the promotion tip."""
    with contextlib.redirect_stdout(io.StringIO()):
        import qfluentwidgets
    return qfluentwidgets


_suppress_noisy_qt_platform_logs()
_suppress_qfluentwidgets_tip()

# Ensure the repository root is on sys.path so package imports work.
_script_dir = os.path.dirname(os.path.abspath(__file__))
_scripts_dir = os.path.normpath(os.path.join(_script_dir, ".."))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)


def _parse_args():
    parser = argparse.ArgumentParser(description="EmbeddedGUI Visual UI Designer")
    parser.add_argument(
        "--project",
        "-p",
        help="Open an existing project (.egui file or directory containing one)",
        default=None,
    )
    parser.add_argument(
        "--app",
        help="Target APP name (default: from config or HelloDesigner)",
        default=None,
    )
    parser.add_argument(
        "--sdk-root",
        "--root",
        dest="sdk_root",
        help="EmbeddedGUI SDK root directory",
        default=None,
    )
    return parser.parse_args()


def main():
    args = _parse_args()

    try:
        from PyQt5.QtWidgets import QApplication
    except ImportError:
        print("Error: PyQt5 is required. Install it with:")
        print("  pip install PyQt5")
        sys.exit(1)

    from ui_designer.model.config import get_config
    from ui_designer.model.widget_registry import WidgetRegistry
    from ui_designer.model.workspace import find_sdk_root, normalize_path
    from ui_designer.ui.main_window import MainWindow
    from ui_designer.ui.theme import apply_theme, configure_platform_font_environment

    _install_qt_message_filter()

    config = get_config()
    cli_project = normalize_path(args.project)
    sdk_root = find_sdk_root(
        cli_sdk_root=args.sdk_root,
        configured_sdk_root=config.sdk_root,
        project_path=cli_project,
    )
    app_name = args.app or config.last_app or "HelloDesigner"

    if sdk_root:
        config.sdk_root = sdk_root
        config.save()

    WidgetRegistry.instance()

    configure_platform_font_environment()
    app = QApplication(sys.argv)
    app.setApplicationName("EmbeddedGUI Designer")
    app.setProperty("designer_font_size_pt", int(getattr(config, "font_size_px", 0) or 0))
    apply_theme(app, config.theme, density=getattr(config, "ui_density", "standard"))

    window = MainWindow(sdk_root, app_name=app_name)

    project_to_open = ""
    preferred_sdk_root = sdk_root
    if cli_project:
        project_to_open = cli_project
    elif config.last_project_path:
        last_project_path = normalize_path(config.last_project_path)
        if os.path.exists(last_project_path):
            project_to_open = last_project_path
            preferred_sdk_root = preferred_sdk_root or config.sdk_root
        else:
            removed = False
            remove_recent_project = getattr(config, "remove_recent_project", None)
            if callable(remove_recent_project):
                try:
                    removed = bool(remove_recent_project(last_project_path))
                except Exception:
                    removed = False
            if getattr(config, "last_project_path", ""):
                config.last_project_path = ""
                if not removed:
                    config.save()

    if project_to_open:
        try:
            window._open_project_path(project_to_open, preferred_sdk_root=preferred_sdk_root, silent=not bool(cli_project))
        except Exception as exc:
            print(f"Warning: Failed to load project: {exc}")

    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
