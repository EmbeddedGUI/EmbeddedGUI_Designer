"""Shared Qt test helpers."""

from __future__ import annotations


def ensure_qapp():
    """Return the shared QApplication instance, creating it when available."""
    try:
        from PyQt5.QtWidgets import QApplication
    except ImportError:
        return None

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def drain_qt_events(app=None):
    """Flush posted events for the shared QApplication when present."""
    app = app or ensure_qapp()
    if app is None:
        return
    try:
        app.sendPostedEvents()
    except Exception:
        pass
    try:
        app.processEvents()
    except Exception:
        pass


def close_widget_safely(widget, *, stop_rendering=True):
    """Best-effort close helper for headless Qt widget tests."""
    if widget is None:
        return

    if stop_rendering:
        stop = getattr(widget, "stop_rendering", None)
        if callable(stop):
            try:
                stop()
            except Exception:
                pass

    try:
        undo_manager = getattr(widget, "_undo_manager", None)
        if undo_manager is not None:
            undo_manager.mark_all_saved()
    except Exception:
        pass
    try:
        clear_project_dirty = getattr(widget, "_clear_project_dirty", None)
        if callable(clear_project_dirty):
            clear_project_dirty()
    except Exception:
        pass
    try:
        widget.hide()
    except Exception:
        pass
    try:
        widget.close()
    except Exception:
        pass
    try:
        widget.deleteLater()
    except Exception:
        pass

    drain_qt_events()
