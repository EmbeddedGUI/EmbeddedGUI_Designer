"""Lifecycle smoke tests for MainWindow shutdown behavior."""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path



def test_main_window_close_smoke_with_active_timers():
    repo_root = Path(__file__).resolve().parents[3]
    script = textwrap.dedent(
        f"""
        import os
        import shutil
        import sys
        import time
        from pathlib import Path

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

        repo_root = Path({repr(str(repo_root))})
        sys.path.insert(0, str(repo_root / "scripts"))

        from PyQt5.QtWidgets import QApplication

        from ui_designer.ui.main_window import MainWindow
        from ui_designer.utils.scaffold import load_saved_project_model
        from ui_designer.utils.runtime_temp import create_repo_temp_workspace
        from ui_designer.tests.ui.window_test_helpers import disable_main_window_compile, open_loaded_test_project


        class DisabledCompiler:
            def can_build(self):
                return False

            def is_preview_running(self):
                return False

            def stop_exe(self):
                return None

            def cleanup(self):
                return None

            def get_build_error(self):
                return "preview disabled for smoke"

            def set_screen_size(self, width, height):
                return None

            def is_exe_ready(self):
                return False


        app = QApplication.instance() or QApplication([])
        sample_project_dir = repo_root / "samples" / "release_smoke" / "ReleaseSmokeApp"
        sample_sdk_root = repo_root / "sdk" / "EmbeddedGUI"
        config_root = create_repo_temp_workspace(repo_root, "ui_designer_close_smoke_")
        os.environ["EMBEDDEDGUI_DESIGNER_CONFIG_DIR"] = str(config_root)
        try:
            for _ in range(12):
                project = load_saved_project_model(str(sample_project_dir))
                window = MainWindow(str(sample_sdk_root))
                disable_main_window_compile(window, DisabledCompiler)
                open_loaded_test_project(window, project, sample_project_dir, sample_sdk_root)
                window.widget_tree.filter_edit.setText("main")
                window._compile_timer.start(10)
                window._regen_timer.start(10)
                window._project_watch_timer.start(10)
                window.close()
                window.deleteLater()
                app.sendPostedEvents()
                app.processEvents()
                time.sleep(0.03)
                app.sendPostedEvents()
                app.processEvents()
        finally:
            shutil.rmtree(config_root, ignore_errors=True)
        """
    )

    env = os.environ.copy()
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    result = subprocess.run(
        [sys.executable, "-c", script],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        timeout=120,
    )

    assert result.returncode == 0, f"stdout:\n{result.stdout}\n\nstderr:\n{result.stderr}"
