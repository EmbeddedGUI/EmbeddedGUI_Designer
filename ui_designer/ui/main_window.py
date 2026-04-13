"""Main window for EmbeddedGUI Designer.

The editor workspace uses a central QSplitter layout (not floating QDockWidgets):
left rail + stacked panels, center page TabBar and editor (preview/code), right
inspector tabs, optional bottom tools. Menus and preferences restore splitter
geometry and the active left/inspector/bottom panels.

Layout (conceptual):

  +------------------------------------------------------------------+--------+
  | command bar (toolbar)                                            |        |
  +---------------------------+--------------------------------------+--------+
  | left tabs + stack         | page tabs + editor                   | inspec |
  | (project / tree /         | (Design | Split | Code)              | tabs   |
  |  widgets / ...)           |                                      |        |
  +---------------------------+--------------------------------------+--------+
  | bottom tools (diagnostics / history / debug), toggleable         |
  +------------------------------------------------------------------+
"""

import copy
import json
import os
import re
import shutil
import time

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QTabWidget, QToolButton, QPushButton, QFrame,
    QAction, QActionGroup, QFileDialog, QStatusBar,
    QMessageBox, QScrollArea, QDockWidget, QMenu,
    QApplication, QDialog, QStackedWidget, QToolBar, QInputDialog, QLabel,
    QLineEdit, QPlainTextEdit, QTextEdit, QSizePolicy,
)
from PyQt5.QtCore import Qt, QTimer, QByteArray, QSignalBlocker, QEvent
from PyQt5.QtGui import QGuiApplication

from qfluentwidgets import TabBar, TabCloseButtonDisplayMode

from .widget_tree import WidgetTreePanel
from .property_panel import PropertyPanel
from .preview_panel import PreviewPanel, MODE_VERTICAL, MODE_HORIZONTAL, MODE_HIDDEN
from .editor_tabs import EditorTabs, MODE_DESIGN, MODE_SPLIT, MODE_CODE
from .project_dock import ProjectExplorerDock
from .resource_panel import ResourcePanel
from .history_panel import HistoryPanel
from .diagnostics_panel import DiagnosticsPanel
from .animations_panel import AnimationsPanel
from .page_fields_panel import PageFieldsPanel
from .page_timers_panel import PageTimersPanel
from .app_selector import AppSelectorDialog
from .new_project_dialog import NewProjectDialog
from .welcome_page import WelcomePage
from .debug_panel import DebugPanel
from .iconography import make_icon
from .project_workspace import ProjectWorkspacePanel
from .widget_browser import WidgetBrowserPanel
from ..model.widget_model import WidgetModel
from ..model.project import Project
from ..model.project_cleaner import (
    DESIGNER_RECONSTRUCT_DELETE_SUMMARY,
    DESIGNER_SOURCE_PRESERVE_SUMMARY,
    clean_project_for_reconstruct,
)
from ..model.page import Page
from ..model.build_metadata import collect_sdk_fingerprint, format_sdk_binding_label
from ..model.config import get_config
from ..model.sdk_bootstrap import default_sdk_install_dir, describe_sdk_source
from ..model.workspace import (
    SDK_RESOURCE_GENERATOR_RELPATH,
    designer_runtime_root,
    infer_sdk_root_from_project_dir,
    is_valid_sdk_root,
    normalize_path,
    resolve_available_sdk_root,
    resolve_sdk_root_candidate,
    sdk_output_dir,
    sdk_output_path,
    sdk_resource_generator_path,
)
from ..model.resource_binding import assign_resource_to_widget
from ..model.resource_usage import (
    collect_project_resource_usages,
    rewrite_project_resource_references,
    rewrite_project_string_references,
)
from ..model.widget_registry import WidgetRegistry
from ..model.structure_ops import (
    available_move_targets,
    describe_structure_actions,
    group_selection,
    lift_to_parent,
    move_into_container,
    move_selection_by_step,
    move_selection_to_edge,
    ungroup_selection,
)
from ..model.selection_state import SelectionState
from ..model.diagnostics import (
    analyze_app_local_widget_issues,
    analyze_page,
    analyze_project_callback_conflicts,
    analyze_selection,
    diagnostic_entry_payload,
    diagnostic_target_payload,
    sort_diagnostic_entries,
)
from ..model.undo_manager import UndoManager
from ..generator.code_generator import (
    collect_page_callback_stubs,
    generate_page_user_source,
    generate_uicode,
    render_page_callback_stub,
)
from ..generator.user_code_preserver import (
    compute_source_hash,
    embed_source_hash,
    read_existing_file,
)
from ..engine.compiler import CompilerEngine
from ..engine.layout_engine import compute_layout, compute_page_layout
from ..utils.resource_config_overlay import (
    APP_RESOURCE_CONFIG_DESIGNER_FILENAME,
    APP_RESOURCE_CONFIG_FILENAME,
    DESIGNER_RESOURCE_DIRNAME,
)
from ..utils.scaffold import (
    APP_CONFIG_DESIGNER_RELPATH,
    BUILD_DESIGNER_RELPATH,
    DESIGNER_RESOURCE_CONFIG_RELPATH,
    RESOURCE_DIR_RELPATH,
    RESOURCE_SRC_DIR_RELPATH,
    bind_project_storage,
    copy_project_sidecar_files,
    designer_page_header_relpath,
    designer_page_layout_relpath,
    legacy_app_config_designer_path,
    legacy_build_designer_path,
    load_saved_project_model,
    materialize_project_codegen_outputs,
    prepare_project_codegen_outputs,
    project_config_images_dir,
    project_config_layout_dir,
    project_config_layout_xml_relpath,
    project_config_mockup_dir,
    project_config_mockup_path,
    project_config_mockup_relpath,
    project_config_path,
    project_config_resource_dir,
    project_app_config_path,
    project_build_mk_path,
    project_designer_dir,
    project_generated_resource_dir,
    project_designer_resource_dir,
    project_file_path,
    page_ext_header_relpath,
    page_user_source_relpath,
    project_page_user_source_path,
    project_orphaned_user_page_relpath,
    project_resource_src_dir,
    project_user_resource_config_path,
    save_empty_project_with_designer_scaffold,
    save_empty_sdk_example_project_with_designer_scaffold,
    save_project_and_materialize_codegen,
    save_project_model,
    sdk_example_paths,
    sync_project_resources_and_generate_designer_resource_config,
)
from .theme import apply_theme, theme_tokens


_DEFAULT_UI_TOKENS = theme_tokens("dark")
_SPACE_XXS = int(_DEFAULT_UI_TOKENS.get("space_xxs", 2))
_SPACE_XS = int(_DEFAULT_UI_TOKENS.get("space_xs", 4))
_SPACE_SM = int(_DEFAULT_UI_TOKENS.get("space_sm", 8))
_SPACE_MD = int(_DEFAULT_UI_TOKENS.get("space_md", 12))
_SPACE_LG = int(_DEFAULT_UI_TOKENS.get("space_lg", 16))
_RESOURCE_GENERATOR_SCRIPT_NAME = os.path.basename(SDK_RESOURCE_GENERATOR_RELPATH)
_GENERATE_RESOURCES_HINT_PREFIX = (
    f"Run resource generation ({_RESOURCE_GENERATOR_SCRIPT_NAME}) to produce\n"
    f"C source files from {RESOURCE_DIR_RELPATH}/ assets and widget config. "
)
from .widgets.page_navigator import PageNavigator, PAGE_TEMPLATES
from ..settings.ui_prefs import UIPreferences
from ..core.state_store import StateStore
from ..renderer.manager import RendererManager
from ..renderer.v1_python_renderer import V1PythonRenderer


WORKSPACE_LAYOUT_VERSION = 5

# UI-D-002: usable on 1280-wide laptops; clamp to primary screen on startup / restore.
MAIN_WINDOW_MIN_WIDTH = 960
MAIN_WINDOW_MIN_HEIGHT = 620
MAIN_WINDOW_DEFAULT_WIDTH = 1400
MAIN_WINDOW_DEFAULT_HEIGHT = 800
INSPECTOR_SCROLL_MIN_WIDTH = 264

# UIX-004: workspace shell proportions (top-level frame balance)
LEFT_PANEL_STACK_MIN_WIDTH = 256
LEFT_PANEL_DEFAULT_WIDTH = 376
CENTER_PANEL_DEFAULT_WIDTH = 860
INSPECTOR_PANEL_DEFAULT_WIDTH = 264
WORKSPACE_TOP_VISIBLE_HEIGHT = 860
WORKSPACE_BOTTOM_VISIBLE_HEIGHT = 200
WORKSPACE_TOP_HIDDEN_HEIGHT = 1000
WORKSPACE_BOTTOM_HIDDEN_HEIGHT = 0
WORKSPACE_CONTROL_HEIGHT = 22
WORKSPACE_TOOLBAR_HEIGHT = 24
PAGE_TAB_BAR_HEIGHT = 40
PAGE_TAB_BAR_MAX_WIDTH = 188

NEW_SHELL_ENABLED = os.environ.get("EGUI_NEW_SHELL_ENABLED", "0").strip().lower() in {"1", "true", "yes", "on"}


_DETACHED_WORKERS = set()
_DESIGNER_REPO_ROOT = normalize_path(os.path.join(os.path.dirname(__file__), "..", ".."))


def _discard_detached_worker(worker):
    _DETACHED_WORKERS.discard(worker)
    try:
        worker.deleteLater()
    except Exception:
        pass


def _project_child_realpath(project_dir, *parts):
    if not project_dir:
        return None
    project_real = os.path.realpath(project_dir)
    path = os.path.realpath(os.path.join(project_dir, *parts))
    if not path.startswith(project_real + os.sep):
        return None
    return path


def _archive_page_user_file(project_dir, page_name, src_path):
    """Move a user-owned page file into .eguiproject/orphaned_user_code/{page_name}/."""
    if not project_dir or not page_name or not src_path:
        return None
    project_real = os.path.realpath(project_dir)
    src = os.path.realpath(src_path)
    if not src.startswith(project_real + os.sep):
        return None
    if not os.path.isfile(src):
        return None

    orphan_root = _project_child_realpath(
        project_dir,
        project_orphaned_user_page_relpath(page_name),
    )
    if orphan_root is None:
        return None

    try:
        os.makedirs(orphan_root, exist_ok=True)
        base_name = os.path.basename(src)
        stem, ext = os.path.splitext(base_name)
        dest = os.path.join(orphan_root, base_name)
        index = 1
        while os.path.exists(dest):
            dest = os.path.join(orphan_root, f"{stem}_{index}{ext}")
            index += 1
        shutil.move(src, dest)
        return dest
    except OSError:
        return None


def delete_page_generated_files(project_dir, page_name):
    """Delete generated page files and archive user-owned ones.

    Removes designer-managed page files from ``.designer/`` and legacy root paths.
    Moves {page_name}.c and {page_name}_ext.h into
    .eguiproject/orphaned_user_code/{page_name}/ so user code is preserved.
    Silently ignores missing files and permission errors.

    Only deletes files that resolve to paths strictly inside project_dir
    (path traversal via page_name like '../other_project/file' is blocked).
    """
    if not page_name or not project_dir:
        return

    for suffix in (
        designer_page_header_relpath(page_name),
        designer_page_layout_relpath(page_name),
        f"{page_name}.h",
        f"{page_name}_layout.c",
    ):
        fpath = _project_child_realpath(project_dir, suffix)
        if fpath is None:
            continue
        try:
            if os.path.isfile(fpath):
                os.remove(fpath)
        except OSError:
            pass

    for suffix in (page_user_source_relpath(page_name), page_ext_header_relpath(page_name)):
        src = _project_child_realpath(project_dir, suffix)
        if src is None:
            continue
        _archive_page_user_file(project_dir, page_name, src)


def _callback_definition_exists(content, callback_name):
    if not content or not callback_name:
        return False
    pattern = rf"^\s*(?:static\s+)?void\s+{re.escape(callback_name)}\s*\("
    return re.search(pattern, content, re.MULTILINE) is not None


def _resolve_page_callback_target(page, callback_name, signature):
    for callback in collect_page_callback_stubs(page):
        if callback.get("name") == callback_name:
            return callback
    kind = "timer" if "egui_timer_t" in (signature or "") else "view"
    return {
        "kind": kind,
        "name": callback_name,
        "signature": signature,
    }


class MainWindow(QMainWindow):
    """Main designer window with project explorer, editor, tree, and properties."""

    def __init__(self, project_root, app_name="HelloDesigner"):
        super().__init__()
        self._config = get_config()
        self.project_root = normalize_path(project_root)
        self.app_name = app_name
        self.project = None
        self.compiler = None
        self.auto_compile = self._config.auto_compile
        self._project_dir = None      # directory containing .egui project file
        self._selected_widget = None
        self._selection_state = SelectionState()
        self._state_store = StateStore()
        self._renderer_manager = RendererManager()
        self._current_page = None      # currently-displayed Page object
        self._pending_insert_parent = None
        self._clipboard_payload = None
        self._paste_serial = 0
        self._async_generation = 0
        self._is_closing = False

        # Debounce timer for compile
        self._compile_timer = QTimer(self)
        self._compile_timer.setSingleShot(True)
        self._compile_timer.setInterval(500)
        self._compile_timer.timeout.connect(self._run_auto_compile_cycle)

        # Timer to find and embed exe window after compile (legacy, kept for compat)
        self._embed_timer = QTimer(self)
        self._embed_timer.setSingleShot(True)
        self._embed_timer.setInterval(0)  # Immediate - no delay
        self._embed_timer.timeout.connect(self._try_embed_exe)

        # Debounce timer for resource generation
        self._regen_timer = QTimer(self)
        self._regen_timer.setSingleShot(True)
        self._regen_timer.setInterval(800)  # Wait 800ms after last change
        self._regen_timer.timeout.connect(lambda: self._generate_resources(silent=True))

        self._compile_worker = None
        self._precompile_worker = None
        self._syncing_tabs = False
        self._resources_need_regen = False
        self._pending_compile = False  # Track if compile needed after current one
        self._pending_rebuild = False  # Track if a clean rebuild is queued
        self._undo_manager = UndoManager()
        self._undoing = False  # True during undo/redo to suppress snapshot recording
        self._active_batch_source = ""
        self._canvas_drag_batch_active = False
        self._canvas_drag_dirty = False
        self._last_drag_geometry_refresh_ts = 0.0
        self._project_watch_snapshot = {}
        self._external_reload_pending = False
        self._external_reload_changed_paths = []
        self._pending_page_renames = {}
        self._project_dirty = False
        self._project_dirty_sources = []
        self._last_runtime_error_text = ""
        self._auto_compile_retry_block_reason = ""
        self._rebuild_retry_block_reason = ""
        self._queued_compile_reasons = []
        self._selection_window_trace_token = 0
        self._selection_window_trace_deadline = 0.0
        self._selection_window_trace_source = ""
        self._selection_window_trace_summary = ""
        self._selection_window_trace_events = 0

        self._project_watch_timer = QTimer(self)
        self._project_watch_timer.setInterval(1000)
        self._project_watch_timer.timeout.connect(self._poll_project_files)

        self._init_ui()
        self.property_panel.set_debug_logger(self.debug_panel.log_info)
        self._install_debug_window_trace()
        self._init_renderer_manager()
        self._init_menus()
        self._init_toolbar()
        self._restore_diagnostics_view_state()
        self._apply_saved_window_state()
        # Start with welcome page (don't auto-create project)
        self._show_welcome_page()

    # 鈹€鈹€ UI Construction 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    def _update_debug_rebuild_action(self, show=None):
        if not hasattr(self, "debug_panel") or not hasattr(self, "_rebuild_action"):
            return
        visible = self.debug_panel.is_rebuild_action_visible() if show is None else bool(show)
        if not visible:
            self.debug_panel.set_rebuild_action_state(visible=False, enabled=False)
            return
        enabled = bool(self._rebuild_action.isEnabled())
        reason = self._rebuild_action_blocked_reason() if not enabled else ""
        if reason and not self._should_offer_debug_rebuild_action(reason):
            self.debug_panel.set_rebuild_action_state(visible=False, enabled=False)
            return
        tooltip = self._rebuild_action.toolTip() or (
            "Clean and rebuild the whole EGUI project, then rerun the preview (Ctrl+F5)."
        )
        accessible_name = (
            "Debug output recovery action: rebuild EGUI project"
            if enabled
            else f"Debug output recovery action unavailable: {reason}"
        )
        self.debug_panel.set_rebuild_action_state(
            visible=True,
            enabled=enabled,
            tooltip=tooltip,
            accessible_name=accessible_name,
        )

    def _init_ui(self):
        self.setWindowTitle("EmbeddedGUI Designer")
        self.setMinimumSize(MAIN_WINDOW_MIN_WIDTH, MAIN_WINDOW_MIN_HEIGHT)
        self.resize(MAIN_WINDOW_DEFAULT_WIDTH, MAIN_WINDOW_DEFAULT_HEIGHT)

        self._central_stack = QStackedWidget()
        self._central_stack.currentChanged.connect(
            lambda _index: QTimer.singleShot(0, self._apply_pending_workspace_splitter_defaults)
        )

        self._welcome_page = WelcomePage()
        self._welcome_page.open_recent.connect(self._open_recent_project)
        self._welcome_page.new_project.connect(self._new_project)
        self._welcome_page.open_project.connect(self._open_project)
        self._welcome_page.open_app.connect(self._open_app_dialog)
        self._welcome_page.set_sdk_root.connect(self._set_sdk_root)
        self._central_stack.addWidget(self._welcome_page)

        editor_container = QWidget()
        self._editor_container = editor_container
        editor_container.setObjectName("workspace_shell")
        editor_layout = QVBoxLayout(editor_container)
        editor_layout.setContentsMargins(6, 6, 6, 6)
        editor_layout.setSpacing(2)

        self._toolbar_host = QFrame()
        self._toolbar_host.setObjectName("workspace_command_bar")
        self._toolbar_host_layout = QVBoxLayout(self._toolbar_host)
        self._toolbar_host_layout.setContentsMargins(1, 1, 1, 1)
        self._toolbar_host_layout.setSpacing(0)

        self._toolbar_header = QFrame(self)
        self._toolbar_header.setObjectName("workspace_command_header")
        self._toolbar_header.hide()
        self._toolbar_eyebrow_label = QLabel("Workspace", self._toolbar_header)
        self._toolbar_eyebrow_label.setObjectName("workspace_command_eyebrow")
        self._toolbar_eyebrow_label.hide()
        self._toolbar_title_label = QLabel("Command Surface", self._toolbar_header)
        self._toolbar_title_label.setObjectName("workspace_command_title")
        self._toolbar_title_label.hide()
        self._toolbar_meta_label = QLabel("", self._toolbar_header)
        self._toolbar_meta_label.setObjectName("workspace_command_meta")
        self._toolbar_meta_label.hide()

        self._workspace_context_card = QFrame(self)
        self._workspace_context_card.setObjectName("workspace_context_card")
        self._workspace_context_card.hide()
        self._workspace_context_eyebrow = QLabel("Context", self._workspace_context_card)
        self._workspace_context_eyebrow.setObjectName("workspace_command_context_eyebrow")
        self._workspace_context_eyebrow.hide()
        self._workspace_context_label = QLabel("No project open", self._workspace_context_card)
        self._workspace_context_label.setObjectName("workspace_command_context_value")
        self._workspace_context_label.hide()

        self._toolbar_command_row = QWidget()
        self._toolbar_command_row.setObjectName("workspace_command_body")
        self._toolbar_command_row_layout = QHBoxLayout(self._toolbar_command_row)
        self._toolbar_command_row_layout.setContentsMargins(0, 0, 0, 0)
        self._toolbar_command_row_layout.setSpacing(2)
        self._toolbar_host_layout.addWidget(self._toolbar_command_row)
        editor_layout.addWidget(self._toolbar_host)

        self.project_dock = ProjectExplorerDock(self)
        self.project_dock.setObjectName("project_explorer_dock")
        self.project_dock.setMinimumWidth(LEFT_PANEL_STACK_MIN_WIDTH)
        self._prepare_workspace_dock(self.project_dock)

        self.page_navigator = PageNavigator()
        self.page_navigator.setObjectName("page_navigator_dock")
        self.page_nav_dock = self.page_navigator

        self.widget_tree = WidgetTreePanel()
        self.widget_tree.setObjectName("widget_tree_dock")
        self.tree_dock = self.widget_tree

        self.res_panel = ResourcePanel()
        self.res_panel.setObjectName("resources_dock")
        self.res_dock = self.res_panel

        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setMinimumWidth(INSPECTOR_SCROLL_MIN_WIDTH)
        right_scroll.setObjectName("properties_dock")
        self.property_panel = PropertyPanel()
        right_scroll.setWidget(self.property_panel)
        self.props_dock = right_scroll

        self.animations_panel = AnimationsPanel()
        self.animations_panel.setObjectName("animations_dock")
        self.animations_dock = self.animations_panel

        self.page_fields_panel = PageFieldsPanel()
        self.page_fields_panel.setObjectName("page_fields_dock")
        self.page_fields_dock = self.page_fields_panel

        self.page_timers_panel = PageTimersPanel()
        self.page_timers_panel.setObjectName("page_timers_dock")
        self.page_timers_dock = self.page_timers_panel

        self.debug_panel = DebugPanel()
        self.debug_panel.setObjectName("debug_output_dock")
        self.debug_dock = self.debug_panel

        self.history_panel = HistoryPanel()
        self.history_panel.setObjectName("history_dock")
        self.history_dock = self.history_panel

        self.diagnostics_panel = DiagnosticsPanel()
        self.diagnostics_panel.setObjectName("diagnostics_dock")
        self.diagnostics_dock = self.diagnostics_panel

        self.widget_browser = WidgetBrowserPanel()
        self.widget_browser.setObjectName("widgets_browser_panel")

        self._project_workspace = ProjectWorkspacePanel(self.project_dock, self.page_navigator)
        self._project_workspace.setObjectName("project_workspace_panel")
        saved_workspace_state = self._config.workspace_state if isinstance(self._config.workspace_state, dict) else {}
        self._project_workspace.set_view(saved_workspace_state.get("project_workspace_view", ProjectWorkspacePanel.VIEW_LIST))
        self._project_workspace._view_chip.show()

        self._left_panel_stack = QTabWidget()
        self._left_panel_stack.setObjectName("workspace_left_tabs")
        self._left_panel_stack.setMinimumWidth(LEFT_PANEL_STACK_MIN_WIDTH)
        self._left_panel_stack.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self._left_panel_stack.setDocumentMode(True)
        self._left_panel_stack.setUsesScrollButtons(False)
        self._left_panel_pages = {
            "project": self._project_workspace,
            "structure": self.widget_tree,
            "widgets": self.widget_browser,
            "assets": self.res_panel,
        }
        self._left_panel_tab_keys = []
        self._left_panel_tab_index_by_key = {}
        for key, label, short_label in (
            ("project", "Project", "Pages"),
            ("structure", "Structure", "Tree"),
            ("widgets", "Components", "Add"),
            ("assets", "Assets", "Assets"),
        ):
            panel = self._left_panel_pages[key]
            panel.setMinimumWidth(LEFT_PANEL_STACK_MIN_WIDTH)
            index = self._left_panel_stack.addTab(panel, str(short_label or label or ""))
            self._left_panel_tab_keys.append(key)
            self._left_panel_tab_index_by_key[key] = index
        self._workspace_nav_frame = self._left_panel_stack.tabBar()
        self._workspace_nav_frame.setObjectName("workspace_left_tabs_bar")
        self._workspace_nav_frame.setExpanding(False)
        self._workspace_nav_frame.setDrawBase(False)
        self._left_panel_stack.currentChanged.connect(self._on_left_panel_tab_changed)

        self._left_shell = QWidget()
        self._left_shell.setObjectName("workspace_left_shell")
        self._left_shell.setMinimumWidth(LEFT_PANEL_STACK_MIN_WIDTH)
        self._left_shell.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        left_shell_layout = QVBoxLayout(self._left_shell)
        left_shell_layout.setContentsMargins(0, 0, 0, 0)
        left_shell_layout.setSpacing(2)
        left_shell_layout.addWidget(self._left_panel_stack, 1)

        center_shell = QWidget()
        self._center_shell = center_shell
        center_shell.setObjectName("workspace_center_shell")
        center_shell.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        center_layout = QVBoxLayout(center_shell)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(2)

        self.page_tab_bar = self._create_page_tab_bar()
        center_layout.addWidget(self.page_tab_bar)

        self.preview_panel = PreviewPanel(screen_width=240, screen_height=320)
        self.preview_panel.set_show_grid(self._config.show_grid)
        self.preview_panel.set_grid_size(self._config.grid_size)
        self.preview_panel.overlay.zoom_changed.connect(lambda _factor: self._update_preview_appearance_action_metadata())
        self.editor_tabs = EditorTabs(self.preview_panel, show_mode_switch=False)
        center_layout.addWidget(self.editor_tabs, 1)

        self._page_inspector_body = QWidget()
        self._page_inspector_body.setObjectName("page_inspector_body")
        page_body_layout = QVBoxLayout(self._page_inspector_body)
        page_body_layout.setContentsMargins(0, 0, 0, 0)
        page_body_layout.setSpacing(2)
        page_body_layout.addWidget(self.page_fields_panel)
        page_body_layout.addWidget(self.page_timers_panel)

        self._page_tools_scroll = QScrollArea()
        self._page_tools_scroll.setObjectName("page_inspector_scroll")
        self._page_tools_scroll.setWidgetResizable(True)
        self._page_tools_scroll.setFrameShape(QFrame.NoFrame)
        self._page_tools_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._page_tools_scroll.setWidget(self._page_inspector_body)
        self._page_tools_section_focus = "fields"

        self._inspector_tabs = QTabWidget()
        self._inspector_tabs.setObjectName("workspace_inspector_tabs")
        self._inspector_tabs.setMinimumWidth(INSPECTOR_SCROLL_MIN_WIDTH)
        self._inspector_tabs.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
        self._inspector_tabs.setDocumentMode(True)
        self._inspector_tabs.tabBar().setDrawBase(False)
        self._inspector_tabs.addTab(self.props_dock, "Properties")
        self._inspector_tabs.addTab(self.animations_panel, "Animations")
        self._inspector_tabs.addTab(self._page_tools_scroll, "Page")
        self._inspector_tabs.currentChanged.connect(lambda _index: self._update_workspace_tab_metadata())

        self._top_splitter = QSplitter(Qt.Horizontal)
        self._top_splitter.setChildrenCollapsible(False)
        self._top_splitter.addWidget(self._left_shell)
        self._top_splitter.addWidget(center_shell)
        self._top_splitter.addWidget(self._inspector_tabs)
        self._top_splitter.setStretchFactor(0, 0)
        self._top_splitter.setStretchFactor(1, 1)
        self._top_splitter.setStretchFactor(2, 0)
        self._top_splitter.setSizes([
            LEFT_PANEL_DEFAULT_WIDTH,
            CENTER_PANEL_DEFAULT_WIDTH,
            INSPECTOR_PANEL_DEFAULT_WIDTH,
        ])

        self._bottom_header = QFrame()
        self._bottom_header.setObjectName("workspace_bottom_header")
        bottom_header_layout = QHBoxLayout(self._bottom_header)
        bottom_header_layout.setContentsMargins(1, 1, 1, 1)
        bottom_header_layout.setSpacing(2)
        self._bottom_title = QLabel("Tools")
        self._bottom_title.setObjectName("workspace_section_title")
        bottom_header_layout.addWidget(self._bottom_title)
        self._bottom_toggle_button = QPushButton("Hide")
        self._bottom_toggle_button.setObjectName("workspace_bottom_toggle_button")
        self._bottom_toggle_button.setFixedSize(48, WORKSPACE_CONTROL_HEIGHT)
        self._bottom_toggle_button.clicked.connect(lambda: self._set_bottom_panel_visible(not self._bottom_panel_visible))
        bottom_header_layout.addStretch()
        bottom_header_layout.addWidget(self._bottom_toggle_button)

        self._bottom_tabs = QTabWidget()
        self._bottom_tabs.setObjectName("workspace_bottom_tabs")
        self._bottom_tabs.setDocumentMode(True)
        self._bottom_tabs.tabBar().setDrawBase(False)
        self._bottom_tabs.addTab(self.diagnostics_panel, "Diagnostics")
        self._bottom_tabs.addTab(self.history_panel, "History")
        self._bottom_tabs.addTab(self.debug_panel, "Debug Output")
        self._bottom_tabs.currentChanged.connect(self._on_bottom_tab_changed)

        bottom_shell = QWidget()
        self._bottom_shell = bottom_shell
        bottom_shell.setObjectName("workspace_bottom_shell")
        bottom_layout = QVBoxLayout(bottom_shell)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(2)
        bottom_layout.addWidget(self._bottom_header)
        bottom_layout.addWidget(self._bottom_tabs, 1)

        self._workspace_splitter = QSplitter(Qt.Vertical)
        self._workspace_splitter.setChildrenCollapsible(False)
        self._workspace_splitter.addWidget(self._top_splitter)
        self._workspace_splitter.addWidget(bottom_shell)
        self._workspace_splitter.setSizes([900, 0])
        editor_layout.addWidget(self._workspace_splitter, 1)

        self._central_stack.addWidget(editor_container)
        self.setCentralWidget(self._central_stack)
        self._update_main_view_metadata()

        self._bottom_panel_visible = False
        self._bottom_panel_last_visible_sizes = [
            WORKSPACE_TOP_VISIBLE_HEIGHT,
            WORKSPACE_BOTTOM_VISIBLE_HEIGHT,
        ]
        self._current_left_panel = "project"
        self._focus_canvas_enabled = False
        self._focus_canvas_saved_top_sizes = []
        self._focus_canvas_saved_bottom_visible = False
        self._pending_default_top_splitter_sizes = False

        # Status bar
        self._workspace_status_label = QLabel("Page: none | Selection: none | Warnings: 0 | Ready")
        self._workspace_status_label.setObjectName("workspace_status_bar_label")
        self.statusBar().addPermanentWidget(self._workspace_status_label, 1)
        self._sdk_status_label = QLabel("SDK: missing")
        self.statusBar().addPermanentWidget(self._sdk_status_label)
        self._update_sdk_status_label()
        self._update_status_bar_summary()
        self.statusBar().showMessage("Ready")
        self._pending_clean_all_startup_notice = True

        # 鈹€鈹€ Connect signals 鈹€鈹€

        # Widget tree
        self.widget_tree.selection_changed.connect(self._on_tree_selection_changed)
        self.widget_tree.widget_selected.connect(self._on_widget_selected)
        self.widget_tree.tree_changed.connect(self._on_tree_changed)
        self.widget_tree.feedback_message.connect(self._on_widget_tree_feedback_message)
        self.widget_tree.browse_widgets_requested.connect(self._show_widget_browser_for_parent)

        # Property panel
        self.property_panel.property_changed.connect(self._on_property_changed)
        self.property_panel.resource_imported.connect(self._on_resource_imported)
        self.property_panel.generate_charset_requested.connect(self._on_property_panel_generate_charset_requested)
        self.property_panel.validation_message.connect(self._on_property_validation_message)
        self.property_panel.user_code_requested.connect(self._on_user_code_requested)

        self.widget_browser.insert_requested.connect(self._insert_widget_from_browser)
        self.widget_browser.reveal_requested.connect(self._reveal_widget_type_in_structure)
        self._project_workspace.view_changed.connect(self._on_project_workspace_view_changed)

        # Preview panel
        self.preview_panel.selection_changed.connect(self._on_preview_selection_changed)
        self.preview_panel.widget_selected.connect(self._on_preview_widget_selected)
        self.preview_panel.context_menu_requested.connect(self._show_preview_context_menu)
        self.preview_panel.widget_moved.connect(self._on_widget_moved)
        self.preview_panel.widget_resized.connect(self._on_widget_resized)
        self.preview_panel.widget_reordered.connect(self._on_widget_reordered)
        self.preview_panel.resource_dropped.connect(self._on_resource_dropped)
        self.preview_panel.widget_type_dropped.connect(self._on_widget_type_dropped)
        self.preview_panel.drag_started.connect(self._on_drag_started)
        self.preview_panel.drag_finished.connect(self._on_drag_finished)
        self.preview_panel.runtime_failed.connect(self._on_preview_runtime_failed)

        # Editor tabs (Code 鈫?Design sync)
        self.editor_tabs.xml_changed.connect(self._on_xml_changed)
        self.editor_tabs.save_requested.connect(self._save_project)
        self.editor_tabs.mode_changed.connect(self._sync_editor_mode_controls)

        # Project explorer
        self.project_dock.page_selected.connect(self._on_page_selected)
        self.project_dock.page_added.connect(self._on_page_added)
        self.project_dock.page_duplicated.connect(self._on_page_duplicated)
        self.project_dock.page_removed.connect(self._on_page_removed)
        self.project_dock.page_renamed.connect(self._on_page_renamed)
        self.project_dock.startup_changed.connect(self._on_startup_changed)
        self.project_dock.page_mode_changed.connect(self._on_page_mode_changed)

        self.page_navigator.page_selected.connect(self._on_page_selected)
        self.page_navigator.page_copy_requested.connect(self._duplicate_page_from_navigator)
        self.page_navigator.page_delete_requested.connect(self._on_page_removed)
        self.page_navigator.page_add_requested.connect(self._on_page_add_from_template)

        # Resource panel
        self.res_panel.resource_selected.connect(self._on_resource_selected)
        self.res_panel.resource_renamed.connect(self._on_resource_renamed)
        self.res_panel.resource_deleted.connect(self._on_resource_deleted)
        self.res_panel.string_key_renamed.connect(self._on_string_key_renamed)
        self.res_panel.string_key_deleted.connect(self._on_string_key_deleted)
        self.diagnostics_panel.diagnostic_activated.connect(self._on_diagnostic_requested)
        self.diagnostics_panel.copy_requested.connect(self._copy_diagnostics_summary)
        self.diagnostics_panel.copy_json_requested.connect(self._copy_diagnostics_json)
        self.diagnostics_panel.export_requested.connect(self._export_diagnostics_summary)
        self.diagnostics_panel.export_json_requested.connect(self._export_diagnostics_json)
        self.animations_panel.animations_changed.connect(self._on_widget_animations_changed)
        self.page_fields_panel.fields_changed.connect(self._on_page_fields_changed)
        self.page_fields_panel.validation_message.connect(self._on_property_validation_message)
        self.page_fields_panel.user_code_section_requested.connect(self._on_page_user_code_section_requested)
        self.page_timers_panel.timers_changed.connect(self._on_page_timers_changed)
        self.page_timers_panel.validation_message.connect(self._on_property_validation_message)
        self.page_timers_panel.user_code_requested.connect(self._on_user_code_requested)
        self.res_panel.resource_imported.connect(self._on_resource_imported)
        self.res_panel.feedback_message.connect(self._on_resource_feedback_message)
        self.res_panel.usage_activated.connect(self._on_resource_usage_activated)

        self._select_left_panel(self._config.workspace_left_panel or "project")
        self._sync_editor_mode_controls(self.editor_tabs.mode)
        self._on_bottom_tab_changed(self._bottom_tabs.currentIndex())
        self._set_bottom_panel_visible(False)
        self._update_workspace_tab_metadata()

    def _apply_stylesheet(self):
        pass  # Rely entirely on the global Fusion / Fluent theme

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self._apply_pending_workspace_splitter_defaults)
        if self._pending_clean_all_startup_notice:
            self._pending_clean_all_startup_notice = False
            QTimer.singleShot(0, self._maybe_show_clean_all_startup_notice)

    def _maybe_show_clean_all_startup_notice(self):
        if not getattr(self._config, "show_clean_all_startup_notice", True):
            return
        if self._clean_all_recovery_unavailable_reason():
            return
        self._config.show_clean_all_startup_notice = False
        self._config.save()
        message = (
            "Recovery tip: Build > Clean All && Reconstruct deletes generated project files "
            "and rebuilds from preserved Designer source state."
        )
        self.statusBar().showMessage(message, 12000)
        self.debug_panel.log_info(message)

    def _init_renderer_manager(self):
        """Register preview renderer and sync initial state."""
        self._renderer_manager.register(V1PythonRenderer(lambda: self._current_page))
        self._renderer_manager.switch("v1", fallback="v1")

    def _prepare_workspace_dock(self, dock_widget):
        if dock_widget is None or not isinstance(dock_widget, QDockWidget):
            return
        dock_widget.setFeatures(QDockWidget.NoDockWidgetFeatures)
        dock_widget.setTitleBarWidget(QWidget(dock_widget))

    def _set_toolbar_button_height(self, toolbar, action):
        widget = toolbar.widgetForAction(action)
        if widget is not None:
            widget.setFixedHeight(WORKSPACE_CONTROL_HEIGHT)
        return widget

    def _workspace_panel_label(self, panel_key):
        return {
            "project": "Project",
            "structure": "Structure",
            "widgets": "Components",
            "assets": "Assets",
        }.get(panel_key, str(panel_key or "Project").title())

    def _project_workspace_nav_context(self):
        view_label = "List view"
        if hasattr(self, "_project_workspace"):
            try:
                view_name = self._project_workspace.current_view()
            except Exception:
                view_name = ProjectWorkspacePanel.VIEW_LIST
            if view_name == ProjectWorkspacePanel.VIEW_THUMBNAILS:
                view_label = "Thumbnails"
        current_page = str(getattr(getattr(self, "_current_page", None), "name", "") or "none")
        startup_page = "none"
        project = getattr(self, "project", None)
        if project is not None:
            startup_value = str(getattr(project, "startup_page", "") or "").strip()
            if any(getattr(page, "name", None) == startup_value for page in getattr(project, "pages", []) or []):
                startup_page = startup_value
        return f"View: {view_label}. Active page: {current_page}. Startup page: {startup_page}."

    def _structure_workspace_nav_context(self):
        current_page = str(getattr(getattr(self, "_current_page", None), "name", "") or "none")
        widgets = [widget for widget in getattr(self._selection_state, "widgets", []) if widget is not None]
        if not widgets:
            selection_text = "Selection: none."
        elif len(widgets) == 1:
            primary = self._selection_state.primary or widgets[0]
            widget_name = str(getattr(primary, "name", "") or getattr(primary, "widget_type", "") or "widget")
            widget_type = str(getattr(primary, "widget_type", "") or "widget")
            selection_text = f"Selection: {widget_name} ({widget_type})."
        else:
            selection_text = f"Selection: {len(widgets)} widgets."
        return f"Current page: {current_page}. {selection_text}"

    def _components_workspace_nav_context(self):
        current_page = str(getattr(getattr(self, "_current_page", None), "name", "") or "none")
        if self._current_page is None:
            return "Current page: none. Insert target: unavailable."
        target = self._insert_target_summary(self._pending_insert_parent or self._default_insert_parent())
        return f"Current page: {current_page}. Insert target: {target}."

    def _assets_workspace_nav_context(self):
        current_page = str(getattr(getattr(self, "_current_page", None), "name", "") or "none")
        return f"Current page: {current_page}."

    def _update_workspace_nav_button_metadata(self, current_panel):
        if not hasattr(self, "_left_panel_tab_index_by_key"):
            return
        for key, index in self._left_panel_tab_index_by_key.items():
            label = self._workspace_panel_label(key)
            if key == "project":
                context = self._project_workspace_nav_context()
            elif key == "structure":
                context = self._structure_workspace_nav_context()
            elif key == "widgets":
                context = self._components_workspace_nav_context()
            elif key == "assets":
                context = self._assets_workspace_nav_context()
            else:
                context = ""
            if key == current_panel:
                tooltip = f"Currently showing {label} panel."
                accessible_name = f"Workspace panel tab: {label}. Current panel."
            else:
                tooltip = f"Open {label} panel."
                accessible_name = f"Workspace panel tab: {label}."
            if context:
                tooltip = f"{tooltip} {context}"
                accessible_name = f"{accessible_name} {context}"
            if self._left_panel_stack.tabToolTip(index) != tooltip:
                self._left_panel_stack.setTabToolTip(index, tooltip)
            if self._left_panel_stack.tabWhatsThis(index) != accessible_name:
                self._left_panel_stack.setTabWhatsThis(index, accessible_name)
        current_label = self._workspace_panel_label(current_panel)
        current_context = self._workspace_menu_action_context(current_panel)
        if hasattr(self, "_workspace_nav_frame"):
            nav_summary = f"Workspace panel tabs. Current panel: {current_label}."
            self._set_metadata_summary(self._workspace_nav_frame, nav_summary)
        if hasattr(self, "_left_panel_stack"):
            stack_summary = f"Workspace panels: {current_label} visible."
            if current_context:
                stack_summary = f"{stack_summary} {current_context}"
            self._set_metadata_summary(self._left_panel_stack, stack_summary)
        if hasattr(self, "_left_shell"):
            shell_summary = f"Workspace left shell: {current_label} panel visible."
            if current_context:
                shell_summary = f"{shell_summary} {current_context}"
            self._set_metadata_summary(self._left_shell, shell_summary)
        self._update_workspace_layout_metadata()

    def _on_left_panel_tab_changed(self, index):
        if index < 0 or index >= len(getattr(self, "_left_panel_tab_keys", [])):
            return
        panel_key = self._left_panel_tab_keys[index]
        if panel_key != getattr(self, "_current_left_panel", None):
            self._select_left_panel(panel_key)

    def _workspace_menu_action_context(self, panel_key):
        if panel_key == "project":
            return self._project_workspace_nav_context()
        if panel_key == "structure":
            return self._structure_workspace_nav_context()
        if panel_key == "widgets":
            return self._components_workspace_nav_context()
        if panel_key == "assets":
            return self._assets_workspace_nav_context()
        return ""

    def _inspector_menu_action_context(self):
        current_page = self._current_page_accessibility_text() if hasattr(self, "_current_page_accessibility_text") else "none"
        selection_text = self._selection_accessibility_text() if hasattr(self, "_selection_accessibility_text") else "Selection: none."
        return f"Current page: {current_page}. {selection_text}"

    def _tools_menu_action_context(self):
        current_page = self._current_page_accessibility_text() if hasattr(self, "_current_page_accessibility_text") else "none"
        visibility = "visible" if getattr(self, "_bottom_panel_visible", False) else "hidden"
        return f"Current page: {current_page}. Panel {visibility}."

    def _update_view_panel_navigation_action_metadata(self):
        if hasattr(self, "_workspace_menu"):
            current_panel = getattr(self, "_current_left_panel", "project")
            self._apply_action_hint(
                self._workspace_menu.menuAction(),
                f"Choose a workspace panel to show. Current panel: {self._workspace_panel_label(current_panel)}.",
            )
            for key, action in getattr(self, "_workspace_view_actions", {}).items():
                label = self._workspace_panel_label(key)
                context = self._workspace_menu_action_context(key)
                base = (
                    f"Currently showing the {label} workspace panel."
                    if key == current_panel
                    else f"Show the {label} workspace panel."
                )
                self._apply_action_hint(action, f"{base} {context}".strip())
        if hasattr(self, "_inspector_menu"):
            current_section = self._current_tab_text(self._inspector_tabs, "Properties") if hasattr(self, "_inspector_tabs") else "Properties"
            self._apply_action_hint(
                self._inspector_menu.menuAction(),
                f"Choose an inspector section to show. Current section: {current_section}.",
            )
            context = self._inspector_menu_action_context()
            for label, action in getattr(self, "_inspector_view_actions", {}).items():
                base = (
                    f"Currently showing the {label} inspector section."
                    if label == current_section
                    else f"Show the {label} inspector section."
                )
                self._apply_action_hint(action, f"{base} {context}".strip())
        if hasattr(self, "_tools_menu"):
            current_section = self._current_tab_text(self._bottom_tabs, "Diagnostics") if hasattr(self, "_bottom_tabs") else "Diagnostics"
            visibility = "visible" if getattr(self, "_bottom_panel_visible", False) else "hidden"
            self._apply_action_hint(
                self._tools_menu.menuAction(),
                f"Choose a bottom tools panel to show. Current section: {current_section}. Panel {visibility}.",
            )
            context = self._tools_menu_action_context()
            for label, action in getattr(self, "_tools_view_actions", {}).items():
                is_current = label == current_section and getattr(self, "_bottom_panel_visible", False)
                base = (
                    f"Currently showing the {label} tools panel."
                    if is_current
                    else f"Show the {label} tools panel."
                )
                self._apply_action_hint(action, f"{base} {context}".strip())

    def _overlay_mode_action_hint(self, mode, is_current=False):
        base_hints = {
            MODE_VERTICAL: "Show preview and overlay stacked vertically (Ctrl+1).",
            MODE_HORIZONTAL: "Show preview and overlay side by side (Ctrl+2).",
            MODE_HIDDEN: "Show only the overlay workspace (Ctrl+3).",
        }
        current_hints = {
            MODE_VERTICAL: "Currently showing preview and overlay stacked vertically (Ctrl+1).",
            MODE_HORIZONTAL: "Currently showing preview and overlay side by side (Ctrl+2).",
            MODE_HIDDEN: "Currently showing only the overlay workspace (Ctrl+3).",
        }
        hints = current_hints if is_current else base_hints
        return hints.get(mode, "")

    def _preview_appearance_action_context(self):
        mode = getattr(self.preview_panel, "overlay_mode", MODE_HORIZONTAL)
        mode_label = {
            MODE_VERTICAL: "Vertical",
            MODE_HORIZONTAL: "Horizontal",
            MODE_HIDDEN: "Overlay Only",
        }.get(mode, str(mode or "Preview"))
        zoom_label = getattr(getattr(self, "preview_panel", None), "_zoom_label", None)
        zoom_text = str(zoom_label.text() if zoom_label is not None else "100% (4px)")
        if mode == MODE_HIDDEN:
            return f"Current layout: {mode_label}. Zoom: {zoom_text}."
        order_text = "overlay first" if getattr(self.preview_panel, "_flipped", False) else "preview first"
        return f"Current layout: {mode_label}, {order_text}. Zoom: {zoom_text}."

    def _update_preview_appearance_action_metadata(self):
        if not hasattr(self, "preview_panel"):
            return
        current_mode = getattr(self.preview_panel, "overlay_mode", MODE_HORIZONTAL)
        context = self._preview_appearance_action_context()
        for mode, action in getattr(self, "_overlay_mode_actions", {}).items():
            hint = self._overlay_mode_action_hint(mode, is_current=(mode == current_mode))
            self._apply_action_hint(action, f"{hint} {context}".strip())
        if hasattr(self, "_swap_overlay_action"):
            if current_mode == MODE_HIDDEN:
                swap_hint = f"Swap preview and overlay unavailable in Overlay Only layout (Ctrl+4). {context}"
            else:
                swap_hint = f"Swap the preview and overlay positions (Ctrl+4). {context}"
            self._apply_action_hint(self._swap_overlay_action, swap_hint.strip())
        if hasattr(self, "_zoom_in_action"):
            zoom_text = str(self.preview_panel._zoom_label.text() or "100% (4px)")
            zoom_in_hint = f"Zoom in on the preview overlay (Ctrl+=). Current zoom: {zoom_text}."
            if self.preview_panel.overlay._zoom >= (self.preview_panel.overlay._zoom_max - 1e-9):
                zoom_in_hint += " Unavailable: already at maximum zoom."
            self._apply_action_hint(self._zoom_in_action, zoom_in_hint)
        if hasattr(self, "_zoom_out_action"):
            zoom_text = str(self.preview_panel._zoom_label.text() or "100% (4px)")
            zoom_out_hint = f"Zoom out on the preview overlay (Ctrl+-). Current zoom: {zoom_text}."
            if self.preview_panel.overlay._zoom <= (self.preview_panel.overlay._zoom_min + 1e-9):
                zoom_out_hint += " Unavailable: already at minimum zoom."
            self._apply_action_hint(self._zoom_out_action, zoom_out_hint)
        if hasattr(self, "_zoom_reset_action"):
            zoom_text = str(self.preview_panel._zoom_label.text() or "100% (4px)")
            zoom_reset_hint = f"Reset the preview overlay zoom to 100% (Ctrl+0). Current zoom: {zoom_text}."
            if abs(self.preview_panel.overlay._zoom - 1.0) <= 1e-9:
                zoom_reset_hint += " Unavailable: already at 100% zoom."
            self._apply_action_hint(self._zoom_reset_action, zoom_reset_hint)
        self._update_view_and_theme_action_metadata()

    def _current_grid_snap_label(self):
        size = int(getattr(self.preview_panel, "grid_size", lambda: 0)() or 0)
        return "off" if size <= 0 else f"{size}px"

    def _current_theme_label(self):
        theme = str(getattr(self._config, "theme", "dark") or "dark")
        return {"dark": "Dark", "light": "Light"}.get(theme, theme.title())

    def _preview_layout_menu_label(self):
        mode = getattr(self.preview_panel, "overlay_mode", MODE_HORIZONTAL)
        mode_label = {
            MODE_VERTICAL: "Vertical",
            MODE_HORIZONTAL: "Horizontal",
            MODE_HIDDEN: "Overlay Only",
        }.get(mode, str(mode or "Preview"))
        if mode == MODE_HIDDEN:
            return mode_label
        order = "overlay first" if getattr(self.preview_panel, "_flipped", False) else "preview first"
        return f"{mode_label}, {order}"

    def _preview_mockup_action_context(self):
        overlay = getattr(self.preview_panel, "overlay", None)
        has_mockup = bool(getattr(overlay, "_bg_image", None) is not None)
        visible = bool(getattr(overlay, "_bg_image_visible", True))
        opacity = int(round(float(getattr(overlay, "_bg_image_opacity", 0.3) or 0.0) * 100))
        if not has_mockup:
            state = "none loaded"
        else:
            state = "visible" if visible else "hidden"
        return has_mockup, visible, opacity, f"Current mockup: {state}. Opacity: {opacity}%."

    def _update_view_and_theme_action_metadata(self):
        if not hasattr(self, "preview_panel"):
            return
        theme_label = self._current_theme_label()
        layout_label = self._preview_layout_menu_label()
        grid_state = "visible" if self.preview_panel.show_grid() else "hidden"
        snap_label = self._current_grid_snap_label()
        font_size = int(getattr(self._config, "font_size_px", 0) or 0)
        font_label = "app default" if font_size <= 0 else f"{font_size}pt"
        density = str(getattr(self._config, "ui_density", "standard") or "standard").strip().lower()
        density_label = "Roomy+" if density in {"roomy_plus", "roomy+"} else ("Roomy" if density == "roomy" else "Standard")
        has_mockup, mockup_visible, _opacity, _mockup_context = self._preview_mockup_action_context()
        mockup_state = "none loaded" if not has_mockup else ("visible" if mockup_visible else "hidden")
        if hasattr(self, "_view_menu"):
            self._apply_action_hint(
                self._view_menu.menuAction(),
                (
                    "Change workspace layout, themes, preview modes, and mockup options. "
                    f"Theme: {theme_label}. Density: {density_label}. Font size: {font_label}. Layout: {layout_label}. "
                    f"Grid: {grid_state}. Snap: {snap_label}. Mockup: {mockup_state}."
                ),
            )
        if hasattr(self, "_theme_menu"):
            self._apply_action_hint(self._theme_menu.menuAction(), f"Choose the Designer theme. Current theme: {theme_label}.")
        current_theme = str(getattr(self._config, "theme", "dark") or "dark")
        if hasattr(self, "theme_dark_action"):
            dark_hint = "Currently using the dark Designer theme." if current_theme == "dark" else "Switch the Designer theme to dark."
            self._apply_action_hint(self.theme_dark_action, dark_hint)
        if hasattr(self, "theme_light_action"):
            light_hint = "Currently using the light Designer theme." if current_theme == "light" else "Switch the Designer theme to light."
            self._apply_action_hint(self.theme_light_action, light_hint)
        if hasattr(self, "_font_size_action"):
            self._apply_action_hint(self._font_size_action, f"Adjust the Designer font size. Current size: {font_label}.")
        if hasattr(self, "_focus_canvas_action"):
            if self._focus_canvas_enabled:
                focus_hint = (
                    "Currently focusing the canvas: left workspace rail, inspector, and bottom tools are hidden. "
                    "Toggle to restore the full workspace."
                )
            else:
                focus_hint = (
                    "Focus the canvas by hiding the left workspace rail, inspector, and bottom tools. "
                    "Toggle again to restore."
                )
            self._apply_action_hint(self._focus_canvas_action, focus_hint)

    def _update_build_menu_metadata(self, latest_entry=None, history_entries=None, history_file_path=""):
        if not hasattr(self, "_build_menu"):
            return
        compile_state = "available" if getattr(getattr(self, "_compile_action", None), "isEnabled", lambda: False)() else "unavailable"
        rebuild_state = "available" if getattr(getattr(self, "_rebuild_action", None), "isEnabled", lambda: False)() else "unavailable"
        clean_all_enabled = getattr(getattr(self, "_clean_all_action", None), "isEnabled", lambda: False)()
        reconstruct_state = "available" if clean_all_enabled else "unavailable"
        if clean_all_enabled and self._effective_rebuild_unavailable_reason():
            reconstruct_state = "available (preview rerun skipped)"
        auto_compile_state = "on" if getattr(getattr(self, "auto_compile_action", None), "isChecked", lambda: False)() else "off"
        preview_state = self._build_preview_state_text()
        project_state = "open" if getattr(self, "project", None) is not None else "none"
        sdk_state = "valid" if self._has_valid_sdk_root() else "invalid"
        resources_dir = self._get_eguiproject_resource_dir()
        resources_state = "available" if resources_dir and os.path.isdir(resources_dir) else "missing"
        self._apply_action_hint(
            self._build_menu.menuAction(),
            (
                "Compile previews, generate resources, or reconstruct a project from Designer sources. "
                f"Project: {project_state}. SDK: {sdk_state}. Compile: {compile_state}. Rebuild: {rebuild_state}. Reconstruct: {reconstruct_state}. "
                f"Auto compile: {auto_compile_state}. "
                f"Preview: {preview_state}. Source resources: {resources_state}. Resource directory: {resources_dir or 'none'}."
            ),
        )

    def _update_file_menu_metadata(self):
        if not hasattr(self, "_file_menu"):
            return
        project_state = "open" if getattr(self, "project", None) is not None else "none"
        dirty_state = self._unsaved_changes_summary_text()
        reload_enabled = getattr(getattr(self, "_reload_project_action", None), "isEnabled", lambda: False)()
        if self._external_reload_pending:
            pending_summary = self._summarize_changed_paths(getattr(self, "_external_reload_changed_paths", []) or [])
            reload_state = (
                f"pending external changes ({pending_summary})"
                if pending_summary
                else "pending external changes"
            )
        else:
            reload_state = "available" if reload_enabled else "unavailable"
        sdk_state = "valid" if self._has_valid_sdk_root() else "invalid"
        recent = getattr(getattr(self, "_config", None), "recent_projects", []) or []
        recent_count = min(len(recent), 10)
        recent_label = "none" if recent_count == 0 else f"{recent_count} project" if recent_count == 1 else f"{recent_count} projects"
        self._apply_action_hint(
            self._file_menu.menuAction(),
            (
                "Create, open, save, export, and close projects. "
                f"Project: {project_state}. SDK: {sdk_state}. Unsaved changes: {dirty_state}. Reload: {reload_state}. Recent projects: {recent_label}."
            ),
        )

    def _update_edit_menu_metadata(self):
        if not hasattr(self, "_edit_menu"):
            return
        page_label = self._current_page_accessibility_text()
        selection_text = self._selection_accessibility_text()
        undo_state = "available" if getattr(getattr(self, "_undo_action", None), "isEnabled", lambda: False)() else "unavailable"
        redo_state = "available" if getattr(getattr(self, "_redo_action", None), "isEnabled", lambda: False)() else "unavailable"
        self._apply_action_hint(
            self._edit_menu.menuAction(),
            (
                "Undo changes and work with the current selection. "
                f"Page: {page_label}. Undo: {undo_state}. Redo: {redo_state}. {selection_text}"
            ),
        )

    def _update_arrange_menu_metadata(self):
        if not hasattr(self, "_arrange_menu"):
            return
        selected_widgets = self._top_level_selected_widgets()
        selectable_widgets = [widget for widget in selected_widgets if not getattr(widget, "designer_locked", False)]
        align_state = "available" if getattr(getattr(self, "_align_left_action", None), "isEnabled", lambda: False)() else "unavailable"
        distribute_state = "available" if getattr(getattr(self, "_distribute_h_action", None), "isEnabled", lambda: False)() else "unavailable"
        reorder_state = "available" if selectable_widgets else "unavailable"
        lock_hide_state = "available" if selected_widgets else "unavailable"
        self._apply_action_hint(
            self._arrange_menu.menuAction(),
            (
                "Align, distribute, reorder, lock, and hide selected widgets. "
                f"{self._selection_accessibility_text()} "
                f"Align: {align_state}. Distribute: {distribute_state}. "
                f"Reorder: {reorder_state}. Lock/Hide: {lock_hide_state}."
            ),
        )

    def _update_structure_menu_metadata(self):
        if not hasattr(self, "_structure_menu"):
            return
        group_state = "available" if (
            getattr(getattr(self, "_group_selection_action", None), "isEnabled", lambda: False)()
            or getattr(getattr(self, "_ungroup_selection_action", None), "isEnabled", lambda: False)()
        ) else "unavailable"
        move_into_state = "available" if getattr(getattr(self, "_move_into_container_action", None), "isEnabled", lambda: False)() else "unavailable"
        reorder_lift_state = "available" if any(
            getattr(action, "isEnabled", lambda: False)()
            for action in (
                getattr(self, "_lift_to_parent_action", None),
                getattr(self, "_move_up_action", None),
                getattr(self, "_move_down_action", None),
                getattr(self, "_move_top_action", None),
                getattr(self, "_move_bottom_action", None),
            )
            if action is not None
        ) else "unavailable"
        self._apply_action_hint(
            self._structure_menu.menuAction(),
            (
                "Group, move, and reorder widgets in the page hierarchy. "
                f"{self._selection_accessibility_text()} "
                f"Group/Ungroup: {group_state}. Move Into: {move_into_state}. "
                f"Reorder/Lift: {reorder_lift_state}."
            ),
        )

    def _update_file_project_action_metadata(self):
        has_project = getattr(self, "project", None) is not None
        action_specs = (
            ("_save_as_action", "Save the current project to a new file (Ctrl+Shift+S)."),
            ("_close_project_action", "Close the current project (Ctrl+W)."),
            ("_export_action", "Export generated C code for the current project (Ctrl+E)."),
        )
        for attr_name, base_text in action_specs:
            action = getattr(self, attr_name, None)
            if action is None:
                continue
            action.setEnabled(has_project)
            if has_project:
                if attr_name == "_save_as_action":
                    hint = f"{base_text} Default parent: {self._default_save_project_as_dir()}."
                elif attr_name == "_close_project_action":
                    hint = f"{base_text} {self._unsaved_changes_hint_text()}"
                elif attr_name == "_export_action":
                    hint = f"{base_text} Default export directory: {self._default_export_code_dir()}."
                else:
                    hint = base_text
            else:
                hint = self._action_hint(base_text, False, "open a project first")
            self._apply_action_hint(action, hint)
        self._update_reload_project_action_metadata()
        self._update_quit_action_metadata()

    def _update_reload_project_action_metadata(self):
        action = getattr(self, "_reload_project_action", None)
        if action is None:
            return
        enabled = self.project is not None and bool(self._project_dir)
        action.setEnabled(enabled)
        if not enabled:
            self._apply_action_hint(
                action,
                self._action_hint("Reload the current project from disk (Ctrl+Shift+R).", False, "open a project first"),
            )
            return
        parts = [
            "Reload the current project from disk (Ctrl+Shift+R).",
            f"Current project directory: {normalize_path(self._project_dir)}.",
        ]
        if self._has_unsaved_changes():
            parts.append(f"Current unsaved changes: {self._unsaved_changes_summary_text()}.")
        if self._external_reload_pending:
            pending_summary = self._summarize_changed_paths(getattr(self, "_external_reload_changed_paths", []) or [])
            if pending_summary:
                parts.append(f"Pending external changes: {pending_summary}.")
            else:
                parts.append("Pending external changes detected.")
        self._apply_action_hint(action, " ".join(parts))

    def _update_quit_action_metadata(self):
        action = getattr(self, "_quit_action", None)
        if action is None:
            return
        project_state = "open" if getattr(self, "project", None) is not None else "none"
        self._apply_action_hint(
            action,
            f"Quit EmbeddedGUI Designer (Ctrl+Q). Project: {project_state}. {self._unsaved_changes_hint_text()}",
        )

    def _dirty_page_count(self):
        return len(self._undo_manager.dirty_pages()) if hasattr(self, "_undo_manager") else 0

    def _dirty_page_label(self):
        dirty_count = self._dirty_page_count()
        return "none" if dirty_count == 0 else f"{dirty_count} page" if dirty_count == 1 else f"{dirty_count} pages"

    def _has_unsaved_page_changes(self):
        return hasattr(self, "_undo_manager") and self._undo_manager.is_any_dirty()

    def _has_unsaved_changes(self):
        return self._has_unsaved_page_changes() or bool(getattr(self, "_project_dirty", False))

    def _project_dirty_reason_text(self, max_items=2):
        reasons = list(getattr(self, "_project_dirty_sources", []) or [])
        if not reasons:
            return ""
        labels = reasons[:max_items]
        remaining = len(reasons) - len(labels)
        summary = ", ".join(labels)
        if remaining > 0:
            summary += f" (+{remaining})"
        return summary

    def _project_dirty_suffix(self):
        reason_text = self._project_dirty_reason_text()
        return f" ({reason_text})" if reason_text else ""

    def _unsaved_changes_summary_text(self):
        dirty_label = self._dirty_page_label()
        if not getattr(self, "_project_dirty", False):
            return dirty_label
        project_label = f"project changes{self._project_dirty_suffix()}"
        if dirty_label == "none":
            return project_label
        return f"{dirty_label} + {project_label}"

    def _unsaved_changes_hint_text(self):
        summary = self._unsaved_changes_summary_text()
        if not getattr(self, "_project_dirty", False):
            return f"Unsaved pages: {summary}."
        return f"Unsaved changes: {summary}."

    def _unsaved_changes_prompt_text(self, action="close"):
        summary = self._unsaved_changes_summary_text()
        if action == "reload":
            return f"Reload project files from disk and discard unsaved changes: {summary}?"
        return f"There are unsaved changes: {summary}. Do you want to save before closing?"

    def _external_change_status_prefix(self, summary=""):
        summary = str(summary or "").strip()
        if not summary:
            return "External project changes detected"
        return f"External project changes detected: {summary}"

    def _external_reload_blocked_text(self, summary=""):
        return (
            f"{self._external_change_status_prefix(summary)}. Local unsaved changes remain: "
            f"{self._unsaved_changes_summary_text()}. Save or reload from disk to sync."
        )

    def _external_reload_compile_wait_text(self, summary=""):
        return f"{self._external_change_status_prefix(summary)}. Reload will resume after background compile."

    def _mark_project_dirty(self, source=""):
        if self.project is None:
            return
        self._project_dirty = True
        source = str(source or "").strip()
        if source and source not in self._project_dirty_sources:
            self._project_dirty_sources.append(source)
        self._update_window_title()

    def _clear_project_dirty(self):
        self._project_dirty = False
        self._project_dirty_sources = []

    def _update_file_open_action_metadata(self, binding_label=""):
        open_app_action = getattr(self, "_open_app_action", None)
        if open_app_action is not None:
            label = str(binding_label or format_sdk_binding_label(self.project_root or self._active_sdk_root(), _DESIGNER_REPO_ROOT))
            default_sdk_root = self._active_sdk_root() or "none"
            self._apply_action_hint(
                open_app_action,
                "Open a bundled example, SDK example project, or initialize a Designer project "
                f"for an unmanaged SDK example. Current binding: {label}. Default SDK root: {default_sdk_root}.",
            )
        open_project_action = getattr(self, "_open_project_action", None)
        if open_project_action is not None:
            recent = getattr(getattr(self, "_config", None), "recent_projects", []) or []
            recent_count = min(len(recent), 10)
            recent_label = (
                "none"
                if recent_count == 0
                else f"{recent_count} project" if recent_count == 1 else f"{recent_count} projects"
            )
            default_dir = self._default_open_project_dir()
            self._apply_action_hint(
                open_project_action,
                f"Open an existing .egui project file. Recent projects: {recent_label}. Default directory: {default_dir}.",
            )

    def _update_new_project_action_metadata(self, binding_label=""):
        action = getattr(self, "_new_project_action", None)
        if action is None:
            return
        label = str(binding_label or format_sdk_binding_label(self.project_root or self._active_sdk_root(), _DESIGNER_REPO_ROOT))
        default_parent = self._default_new_project_parent_dir(self.project_root or self._active_sdk_root()) or normalize_path(os.getcwd())
        self._apply_action_hint(
            action,
            f"Create a new EmbeddedGUI Designer project. Current binding: {label}. Default parent: {default_parent}.",
        )

    def _update_sdk_root_action_metadata(self, binding_label=""):
        action = getattr(self, "_set_sdk_root_action", None)
        if action is None:
            return
        label = str(binding_label or "SDK: missing")
        default_root = self._active_sdk_root() or "none"
        self._apply_action_hint(
            action,
            f"Choose the EmbeddedGUI SDK root used for compile preview. Current binding: {label}. Default selection: {default_root}.",
        )

    def _update_generate_resources_action_metadata(self):
        if not hasattr(self, "_generate_resources_action"):
            return
        project_state = "open" if getattr(self, "project", None) is not None and bool(self._project_dir) else "none"
        sdk_state = "valid" if self._has_valid_sdk_root() else "invalid"
        resources_dir = self._get_eguiproject_resource_dir()
        resources_state = "available" if resources_dir and os.path.isdir(resources_dir) else "missing"
        resource_dir_label = resources_dir or "none"
        hint = (
            f"{_GENERATE_RESOURCES_HINT_PREFIX}"
            f"Project: {project_state}. SDK: {sdk_state}. Source resources: {resources_state}. Resource directory: {resource_dir_label}."
        )
        self._apply_action_hint(self._generate_resources_action, hint)

    def _update_preview_grid_and_mockup_action_metadata(self):
        if not hasattr(self, "preview_panel"):
            return
        grid_visible = bool(self.preview_panel.show_grid())
        current_snap = self._current_grid_snap_label()
        grid_visibility = "visible" if grid_visible else "hidden"
        if hasattr(self, "_show_grid_action"):
            grid_hint = (
                f"Currently showing the preview grid overlay. Current snap: {current_snap}."
                if grid_visible
                else f"Show the preview grid overlay. Current snap: {current_snap}."
            )
            self._apply_action_hint(self._show_grid_action, grid_hint)
        if hasattr(self, "_grid_menu"):
            self._apply_action_hint(
                self._grid_menu.menuAction(),
                f"Choose the grid snap size. Current snap: {current_snap}. Grid {grid_visibility}.",
            )
        for size, action in getattr(self, "_grid_size_actions", {}).items():
            if size <= 0:
                hint = (
                    f"Grid snapping is currently disabled. Grid {grid_visibility}."
                    if current_snap == "off"
                    else f"Disable grid snapping. Current snap: {current_snap}. Grid {grid_visibility}."
                )
            else:
                hint = (
                    f"Currently snapping the overlay grid to {size}px. Grid {grid_visibility}."
                    if current_snap == f"{size}px"
                    else f"Snap the overlay grid to {size}px. Current snap: {current_snap}. Grid {grid_visibility}."
                )
            self._apply_action_hint(action, hint)

        has_mockup, mockup_visible, opacity, mockup_context = self._preview_mockup_action_context()
        if hasattr(self, "_bg_menu"):
            self._apply_action_hint(self._bg_menu.menuAction(), f"Manage the preview background mockup image. {mockup_context}")
        if hasattr(self, "_opacity_menu"):
            self._apply_action_hint(self._opacity_menu.menuAction(), f"Choose the mockup image opacity. {mockup_context}")
        if hasattr(self, "_load_bg_action"):
            self._apply_action_hint(self._load_bg_action, f"Load a mockup image behind the preview. {mockup_context}")
        if hasattr(self, "_toggle_bg_action"):
            if has_mockup:
                toggle_hint = (
                    f"Currently showing the background mockup image (Ctrl+M). {mockup_context}"
                    if mockup_visible
                    else f"Show the background mockup image (Ctrl+M). {mockup_context}"
                )
            else:
                toggle_hint = f"Toggle the background mockup image (Ctrl+M). {mockup_context}"
            self._apply_action_hint(self._toggle_bg_action, toggle_hint)
        if hasattr(self, "_clear_bg_action"):
            clear_hint = f"Remove the current background mockup image. {mockup_context}"
            if not has_mockup:
                clear_hint = f"Remove the current background mockup image. Unavailable: no mockup image loaded. {mockup_context}"
            self._apply_action_hint(self._clear_bg_action, clear_hint)
        for pct, action in getattr(self, "_opacity_actions", {}).items():
            hint = (
                f"Currently showing mockup opacity at {pct}%. {mockup_context}"
                if pct == opacity
                else f"Set the mockup image opacity to {pct}%. {mockup_context}"
            )
            self._apply_action_hint(action, hint)
        self._update_view_and_theme_action_metadata()

    def _select_left_panel(self, panel_key):
        if panel_key == "components":
            panel_key = "widgets"
        if panel_key not in getattr(self, "_left_panel_pages", {}):
            panel_key = "project"
        self._current_left_panel = panel_key
        self._config.workspace_left_panel = panel_key
        if hasattr(self, "_state_store"):
            self._state_store.set_left_tab(panel_key)
        page = self._left_panel_pages[panel_key]
        self._left_panel_stack.setCurrentWidget(page)
        index = getattr(self, "_left_panel_tab_index_by_key", {}).get(panel_key, -1)
        if index >= 0 and self._left_panel_stack.currentIndex() != index:
            blocker = QSignalBlocker(self._left_panel_stack)
            self._left_panel_stack.setCurrentIndex(index)
            del blocker
        self._update_workspace_nav_button_metadata(panel_key)
        self._update_view_panel_navigation_action_metadata()
        if panel_key == "widgets":
            self.widget_browser.focus_search()

    def _default_insert_parent(self):
        primary = self._primary_selected_widget()
        if primary is not None and getattr(primary, "is_container", False):
            return primary
        if primary is not None and getattr(primary, "parent", None) is not None and getattr(primary.parent, "is_container", False):
            return primary.parent
        if self._current_page is not None and getattr(self._current_page, "root_widget", None) is not None:
            return self._current_page.root_widget
        return None

    def _insert_target_summary(self, widget):
        if widget is None:
            return "Current page root"
        names = []
        current = widget
        while current is not None:
            names.append(current.name or current.widget_type)
            current = current.parent
        names.reverse()
        return " / ".join(names) if names else "Current page root"

    def _update_insert_widget_button_metadata(self, parent=None):
        if not hasattr(self, "_insert_widget_button"):
            return
        if self._current_page is None:
            tooltip = "Open or create a project to insert a component."
            accessible_name = "Insert component unavailable."
        else:
            target = self._insert_target_summary(parent)
            tooltip = f"Open the Components panel and insert a component into {target}."
            accessible_name = f"Insert component target: {target}."
        self._set_metadata_summary(self._insert_widget_button, tooltip, accessible_name)

    def _action_hint(self, base_text, enabled, blocked_reason=""):
        if enabled or not blocked_reason:
            return base_text
        reason = blocked_reason.rstrip(".")
        return f"{base_text} Unavailable: {reason}."

    def _apply_action_hint(self, action, hint):
        if action is None:
            return
        resolved_hint = str(hint or "")
        if str(action.property("_action_hint_snapshot") or "") == resolved_hint:
            return
        action.setToolTip(resolved_hint)
        action.setStatusTip(resolved_hint)
        action.setProperty("_action_hint_snapshot", resolved_hint)

    def _page_tab_state_summary(self, page_name):
        page_label = str(page_name or "").strip() or "unknown page"
        parts = [f"Page: {page_label}."]
        current_page = str(getattr(getattr(self, "_current_page", None), "name", "") or "").strip()
        startup_page = str(getattr(getattr(self, "project", None), "startup_page", "") or "").strip()
        dirty_pages = set(self._undo_manager.dirty_pages()) if hasattr(self, "_undo_manager") else set()
        if page_label == current_page:
            parts.append("Current page.")
        if page_label == startup_page:
            parts.append("Startup page.")
        parts.append("Unsaved changes." if page_label in dirty_pages else "No unsaved changes.")
        return " ".join(parts)

    def _page_tab_context_action_hint(self, action_key, page_name):
        state_summary = self._page_tab_state_summary(page_name)
        if action_key == "close_tab":
            return f"Close page tab. {state_summary}"
        if action_key == "close_others":
            return f"Close all other open page tabs and keep {page_name}. {state_summary}"
        if action_key == "close_all":
            return f"Close all open page tabs from {page_name}. {state_summary}"
        return state_summary

    def _paste_action_blocked_reason(self):
        if self._current_page is None:
            return "open a page first"
        if self._clipboard_payload is None:
            return "copy or cut widgets first"
        return "select a container or page root that can receive pasted widgets"

    def _arrange_action_blocked_reason(self, selected_widgets, selectable_widgets, minimum_count):
        if len(selectable_widgets) < minimum_count:
            if len(selected_widgets) >= minimum_count:
                return f"locked widgets leave fewer than {minimum_count} editable widgets"
            return f"select at least {minimum_count} widgets"
        layout_parent = self._shared_layout_managed_parent(selectable_widgets)
        if layout_parent is not None:
            return (
                f"selected widgets are layout-managed by the same {layout_parent.widget_type} parent; "
                "reorder them instead"
            )
        if self._shared_selection_parent(selectable_widgets) is None:
            return "selected widgets do not share the same free-position parent"
        return f"select at least {minimum_count} widgets"

    def _align_action_blocked_reason(self, selected_widgets, selectable_widgets):
        return self._arrange_action_blocked_reason(selected_widgets, selectable_widgets, 2)

    def _distribute_action_blocked_reason(self, selected_widgets, selectable_widgets):
        return self._arrange_action_blocked_reason(selected_widgets, selectable_widgets, 3)

    def _editable_selection_action_hint(self, base_text, selected_widgets, editable_widgets, partial_locked_note=""):
        if not selected_widgets:
            return self._action_hint(base_text, False, "select at least 1 widget")
        if not editable_widgets:
            return self._action_hint(base_text, False, "all selected widgets are locked")
        if len(editable_widgets) != len(selected_widgets) and partial_locked_note:
            return f"{base_text} {partial_locked_note}"
        return base_text

    def _compile_action_blocked_reason(self):
        if self.project is None:
            return "open a project first"
        if not self._has_valid_sdk_root():
            return "set a valid SDK root first"
        if self.compiler is None:
            return "save the project to a valid SDK workspace first"
        preview_unavailable_reason = self._effective_preview_unavailable_reason()
        if preview_unavailable_reason:
            return preview_unavailable_reason
        return "compile preview is unavailable"

    def _rebuild_action_blocked_reason(self):
        if self.project is None:
            return "open a project first"
        if not self._has_valid_sdk_root():
            return "set a valid SDK root first"
        if self.compiler is None:
            return "save the project to a valid SDK workspace first"
        rebuild_unavailable_reason = self._effective_rebuild_unavailable_reason()
        if rebuild_unavailable_reason:
            return rebuild_unavailable_reason
        return "clean rebuild is unavailable"

    def _clean_all_action_blocked_reason(self):
        if self.project is None:
            return "open a project first"
        if not self._project_dir:
            return "save the project first"
        clean_all_recovery_reason = self._clean_all_recovery_unavailable_reason()
        if clean_all_recovery_reason:
            return clean_all_recovery_reason
        return "clean-all recovery is unavailable"

    def _clean_all_recovery_unavailable_reason(self):
        reason = str(self._effective_preview_unavailable_reason() or "").strip()
        if not reason:
            return ""
        normalized_reason = reason.rstrip(".!? ")
        lowered = reason.lower()
        missing_target = self._missing_make_target_name(reason).lower()
        if missing_target in {"main.exe", "main"} or "preview build target unavailable" in lowered:
            return f"missing preview build targets cannot be recovered by reconstruction: {normalized_reason}"
        if "preview build target probe timed out" in lowered:
            return f"preview target probe failures cannot be recovered by reconstruction: {normalized_reason}"
        if lowered.startswith("preview build unavailable"):
            return f"preview build availability failures cannot be recovered by reconstruction: {normalized_reason}"
        if "make not found" in lowered:
            return f"missing build tools cannot be recovered by reconstruction: {normalized_reason}"
        return ""

    def _clean_all_action_runtime_note(self):
        if not hasattr(self, "_clean_all_action") or not self._clean_all_action.isEnabled():
            return ""
        rebuild_unavailable_reason = self._effective_rebuild_unavailable_reason()
        if rebuild_unavailable_reason:
            suffix = "" if str(rebuild_unavailable_reason).rstrip().endswith((".", "!", "?")) else "."
            return f" Preview rerun will be skipped: {rebuild_unavailable_reason}{suffix}"
        return ""

    def _clean_all_action_will_skip_preview_rerun(self):
        return bool(
            hasattr(self, "_clean_all_action")
            and self._clean_all_action.isEnabled()
            and not self._clean_all_recovery_unavailable_reason()
            and self._effective_rebuild_unavailable_reason()
        )

    def _clean_all_action_base_text(self):
        if self._clean_all_recovery_unavailable_reason() or self._clean_all_action_will_skip_preview_rerun():
            return (
                "Destructive recovery: delete project-side generated/code files outside the preserved "
                "Designer source set and reconstruct the project (Ctrl+Shift+F5)."
            )
        return (
            "Destructive recovery: delete project-side generated/code files outside the preserved "
            "Designer source set, reconstruct the project, and rerun the preview (Ctrl+Shift+F5)."
        )

    def _build_preview_state_text(self):
        if self.project is not None and self._effective_preview_unavailable_reason():
            return "editing only"
        preview_running = bool(self.compiler is not None and self.compiler.is_preview_running()) if hasattr(self, "compiler") else False
        if preview_running:
            return "running"
        if hasattr(self, "preview_panel") and self.preview_panel.is_python_preview_active():
            return "python preview"
        return "stopped"

    def _compile_action_context_summary(self):
        project_state = "open" if self.project is not None else "none"
        sdk_state = "valid" if self._has_valid_sdk_root() else "invalid"
        preview_state = self._build_preview_state_text()
        return f"Project: {project_state}. SDK: {sdk_state}. Preview: {preview_state}."

    def _clean_all_action_context_summary(self):
        project_state = "open" if self.project is not None else "none"
        saved_state = "saved" if self._project_dir else "unsaved"
        sdk_state = "valid" if self._has_valid_sdk_root() else "invalid"
        preview_state = self._build_preview_state_text()
        return f"Project: {project_state}. Saved project: {saved_state}. SDK: {sdk_state}. Preview: {preview_state}."

    def _auto_compile_action_context_summary(self):
        return self._compile_action_context_summary()

    def _stop_action_context_summary(self):
        project_state = "open" if self.project is not None else "none"
        preview_running = bool(self.compiler is not None and self.compiler.is_preview_running()) if hasattr(self, "compiler") else False
        preview_state = "running" if preview_running else "stopped"
        return f"Project: {project_state}. Preview: {preview_state}."

    def _update_toolbar_action_metadata(self):
        command_bar_summary = "Workspace command bar with insert, save, build, mode, context, and runtime indicators."
        if hasattr(self, "_toolbar_host"):
            self._set_metadata_summary(self._toolbar_host, command_bar_summary)
        toolbar_summary = "Main toolbar: insert, save, edit, and preview commands."
        if hasattr(self, "_toolbar"):
            self._set_metadata_summary(self._toolbar, toolbar_summary)
        self._update_workspace_command_surface_metadata()
        if hasattr(self, "_save_action"):
            has_project = getattr(self, "project", None) is not None
            self._save_action.setEnabled(has_project)
            if has_project:
                target_dir = normalize_path(self._project_dir) or "unsaved project directory"
                save_hint = f"Save the current project (Ctrl+S). {self._unsaved_changes_hint_text()} Target: {target_dir}."
            else:
                save_hint = self._action_hint("Save the current project (Ctrl+S).", False, "open a project first")
            self._apply_action_hint(self._save_action, save_hint)
        if hasattr(self, "_undo_action"):
            undo_hint = self._action_hint(
                "Undo the last change on the current page (Ctrl+Z).",
                self._undo_action.isEnabled(),
                "open a page first" if self._current_page is None else "no earlier changes are available on this page",
            )
            self._apply_action_hint(self._undo_action, undo_hint)
        if hasattr(self, "_redo_action"):
            redo_hint = self._action_hint(
                "Redo the next change on the current page (Ctrl+Shift+Z).",
                self._redo_action.isEnabled(),
                "open a page first" if self._current_page is None else "no later changes are available on this page",
            )
            self._apply_action_hint(self._redo_action, redo_hint)
        if hasattr(self, "_copy_action"):
            copy_hint = self._action_hint(
                "Copy the current selection (Ctrl+C).",
                self._copy_action.isEnabled(),
                "select at least 1 widget",
            )
            self._apply_action_hint(self._copy_action, copy_hint)
        if hasattr(self, "_paste_action"):
            paste_hint = self._action_hint(
                "Paste clipboard widgets into the current page (Ctrl+V).",
                self._paste_action.isEnabled(),
                self._paste_action_blocked_reason(),
            )
            self._apply_action_hint(self._paste_action, paste_hint)
        if hasattr(self, "_compile_action"):
            base_text = "Compile the current project and run the preview (F5)."
            compile_context = self._compile_action_context_summary()
            if self._compile_action.isEnabled():
                compile_hint = f"{base_text} {compile_context}"
            else:
                compile_hint = f"{base_text} {compile_context} Unavailable: {self._compile_action_blocked_reason()}."
            self._apply_action_hint(self._compile_action, compile_hint)
        if hasattr(self, "_rebuild_action"):
            base_text = "Clean and rebuild the whole EGUI project, then rerun the preview (Ctrl+F5)."
            rebuild_context = self._compile_action_context_summary()
            if self._rebuild_action.isEnabled():
                rebuild_hint = f"{base_text} {rebuild_context}"
            else:
                rebuild_hint = f"{base_text} {rebuild_context} Unavailable: {self._rebuild_action_blocked_reason()}."
            self._apply_action_hint(self._rebuild_action, rebuild_hint)
            self._update_debug_rebuild_action()
        if hasattr(self, "_clean_all_action"):
            base_text = self._clean_all_action_base_text()
            clean_context = self._clean_all_action_context_summary()
            if self._clean_all_action.isEnabled():
                clean_hint = f"{base_text} {clean_context}{self._clean_all_action_runtime_note()}"
            else:
                clean_hint = f"{base_text} {clean_context} Unavailable: {self._clean_all_action_blocked_reason()}."
            self._apply_action_hint(self._clean_all_action, clean_hint)
        if hasattr(self, "_stop_action"):
            base_text = "Stop the running preview executable."
            stop_context = self._stop_action_context_summary()
            stop_hint = (
                f"{base_text} {stop_context}"
                if self._stop_action.isEnabled()
                else f"{base_text} {stop_context} Unavailable: preview is not running."
            )
            self._apply_action_hint(self._stop_action, stop_hint)
        self._update_quit_action_metadata()

    def _update_widget_browser_target(self, preferred_parent=None):
        parent = preferred_parent or self._default_insert_parent()
        self._pending_insert_parent = parent
        if hasattr(self, "widget_browser"):
            self.widget_browser.set_insert_target_label(self._insert_target_summary(parent))
        self._update_insert_widget_button_metadata(parent)

    def _show_widget_browser_for_parent(self, preferred_parent=None):
        self._update_widget_browser_target(preferred_parent=preferred_parent)
        self._select_left_panel("widgets")

    def _insert_widget_from_browser(self, widget_type):
        if not widget_type or self._current_page is None:
            return
        parent = self._pending_insert_parent or self._default_insert_parent()
        inserted = self.widget_tree.insert_widget(widget_type, parent=parent)
        if inserted is None:
            return
        self._focus_properties_for_selection()
        self.widget_browser.refresh()
        self._pending_insert_parent = None
        self._update_widget_browser_target()
        self.statusBar().showMessage(f"Inserted {WidgetRegistry.instance().display_name(widget_type)}.", 3000)

    def _reveal_widget_type_in_structure(self, widget_type):
        self._select_left_panel("structure")
        if self._current_page is None or not widget_type:
            return

        widgets = [widget for widget in self._current_page.get_all_widgets() if getattr(widget, "widget_type", "") == widget_type]
        if not widgets:
            self.statusBar().showMessage(
                f"No {WidgetRegistry.instance().display_name(widget_type)} widgets exist on this page.",
                3000,
            )
            return

        primary = next((widget for widget in widgets if widget is not getattr(self._current_page, "root_widget", None)), widgets[0])
        self._set_selection([primary], primary=primary, sync_tree=True, sync_preview=True)
        self._focus_properties_for_selection()
        self.statusBar().showMessage(
            f"Revealed {WidgetRegistry.instance().display_name(widget_type)} in structure.",
            3000,
        )

    def _on_project_workspace_view_changed(self, view_name):
        if not isinstance(self._config.workspace_state, dict):
            self._config.workspace_state = {}
        self._config.workspace_state["project_workspace_view"] = view_name or ProjectWorkspacePanel.VIEW_LIST
        self._update_workspace_nav_button_metadata(getattr(self, "_current_left_panel", "project"))
        self._update_view_panel_navigation_action_metadata()

    def _focus_page_inspector_section(self, inner_section="fields"):
        """Scroll the Page inspector so Fields or Timers is visible (single-column, no nested tabs)."""
        focus_key = "timers" if inner_section == "timers" else "fields"
        self._page_tools_section_focus = focus_key
        scroll = getattr(self, "_page_tools_scroll", None)
        if scroll is None:
            return
        target = self.page_timers_panel if focus_key == "timers" else self.page_fields_panel
        QTimer.singleShot(0, lambda s=scroll, w=target: s.ensureWidgetVisible(w, 24, 24))

    def _show_inspector_tab(self, section, inner_section=None):
        if self._focus_canvas_enabled:
            self._set_focus_canvas_enabled(False)
        section_map = {
            "properties": 0,
            "animations": 1,
            "page": 2,
        }
        index = section_map.get(section, 0)
        if hasattr(self, "_inspector_tabs"):
            self._inspector_tabs.setCurrentIndex(index)
        if section == "page" and inner_section in ("fields", "timers"):
            self._focus_page_inspector_section(inner_section)
        self._update_view_panel_navigation_action_metadata()
        self._update_workspace_tab_metadata()

    def _show_bottom_panel(self, section="Diagnostics"):
        if self._focus_canvas_enabled:
            self._set_focus_canvas_enabled(False)
        if not hasattr(self, "_bottom_tabs"):
            return
        section_map = {
            "Diagnostics": 0,
            "History": 1,
            "Debug Output": 2,
        }
        self._bottom_tabs.setCurrentIndex(section_map.get(section, 0))
        self._set_bottom_panel_visible(True)
        self._update_view_panel_navigation_action_metadata()

    def _set_bottom_panel_visible(self, visible):
        if not hasattr(self, "_workspace_splitter"):
            return

        should_show = bool(visible)
        was_visible = bool(getattr(self, "_bottom_panel_visible", False))

        # Preserve user-adjusted splitter ratio when hiding/showing bottom tools.
        try:
            current_sizes = [int(v) for v in self._workspace_splitter.sizes()]
        except Exception:
            current_sizes = []
        if len(current_sizes) >= 2 and sum(current_sizes) > 0 and current_sizes[1] > 0:
            live_visible_sizes = current_sizes[:2]
        else:
            live_visible_sizes = []

        if was_visible and not should_show and live_visible_sizes:
            self._bottom_panel_last_visible_sizes = live_visible_sizes

        self._bottom_panel_visible = should_show
        self._bottom_tabs.setVisible(self._bottom_panel_visible)

        if self._bottom_panel_visible:
            if was_visible:
                # Keep current splitter geometry while already visible.
                if live_visible_sizes:
                    self._bottom_panel_last_visible_sizes = live_visible_sizes
            else:
                restored_sizes = getattr(self, "_bottom_panel_last_visible_sizes", [])
                if not isinstance(restored_sizes, list) or len(restored_sizes) < 2 or sum(restored_sizes[:2]) <= 0:
                    restored_sizes = [WORKSPACE_TOP_VISIBLE_HEIGHT, WORKSPACE_BOTTOM_VISIBLE_HEIGHT]
                self._workspace_splitter.setSizes(restored_sizes[:2])
            self._bottom_toggle_button.setText("Hide")
        else:
            if was_visible:
                self._workspace_splitter.setSizes([
                    WORKSPACE_TOP_HIDDEN_HEIGHT,
                    WORKSPACE_BOTTOM_HIDDEN_HEIGHT,
                ])
            self._bottom_toggle_button.setText("Show")

        self._update_bottom_toggle_button_metadata()
        self._update_workspace_tab_metadata()

    def _on_bottom_tab_changed(self, index):
        titles = {0: "Diagnostics", 1: "History", 2: "Debug Output"}
        current_label = titles.get(index, "Tools")
        if hasattr(self, "_bottom_title"):
            self._bottom_title.setText(current_label)
        if hasattr(self, "_state_store"):
            self._state_store.set_bottom_tab(current_label)
        self._update_workspace_tab_metadata()

    def _update_bottom_toggle_button_metadata(self):
        if not hasattr(self, "_bottom_toggle_button"):
            return
        if self._bottom_panel_visible:
            tooltip = "Hide the bottom tools panel."
            accessible_name = "Bottom tools toggle: shown. Activate to hide."
        else:
            tooltip = "Show the bottom tools panel."
            accessible_name = "Bottom tools toggle: hidden. Activate to show."
        self._set_metadata_summary(self._bottom_toggle_button, tooltip, accessible_name)

    def _current_tab_text(self, tab_widget, fallback):
        if tab_widget is None or tab_widget.count() <= 0:
            return fallback
        index = tab_widget.currentIndex()
        if index < 0:
            index = 0
        return tab_widget.tabText(index) or fallback

    def _current_page_accessibility_text(self):
        return str(getattr(getattr(self, "_current_page", None), "name", "") or "none")

    def _selection_accessibility_text(self):
        widgets = [widget for widget in getattr(self._selection_state, "widgets", []) if widget is not None]
        if not widgets:
            return "Selection: none."
        if len(widgets) == 1:
            primary = self._selection_state.primary or widgets[0]
            widget_name = str(getattr(primary, "name", "") or getattr(primary, "widget_type", "") or "widget")
            widget_type = str(getattr(primary, "widget_type", "") or "widget")
            return f"Selection: {widget_name} ({widget_type})."
        return f"Selection: {len(widgets)} widgets."

    def _update_workspace_tab_metadata(self):
        if hasattr(self, "_inspector_tabs"):
            current = self._current_tab_text(self._inspector_tabs, "Properties")
            current_page = self._current_page_accessibility_text()
            selection_text = self._selection_accessibility_text()
            tooltip = f"Inspector tabs. Current section: {current}. Current page: {current_page}. {selection_text}"
            self._set_metadata_summary(
                self._inspector_tabs,
                tooltip,
                f"Inspector tabs: {current} selected. {self._inspector_tabs.count()} tabs. Current page: {current_page}. {selection_text}",
            )
        if hasattr(self, "_page_tools_scroll"):
            current_page = str(getattr(getattr(self, "_current_page", None), "name", "") or "none")
            focus = getattr(self, "_page_tools_section_focus", "fields")
            focus_label = "Timers" if focus == "timers" else "Fields"
            tooltip = (
                f"Page inspector (Fields and Timers). Scroll focus: {focus_label}. "
                f"Current page: {current_page}."
            )
            self._set_metadata_summary(
                self._page_tools_scroll,
                tooltip,
                f"Page inspector: Fields and Timers sections. Scroll focus: {focus_label}. "
                f"Current page: {current_page}.",
            )
        if hasattr(self, "_bottom_tabs"):
            current = self._current_tab_text(self._bottom_tabs, "Diagnostics")
            current_page = self._current_page_accessibility_text()
            visibility = "visible" if self._bottom_panel_visible else "hidden"
            tooltip = f"Bottom tools tabs. Current section: {current}. Current page: {current_page}. Panel {visibility}."
            self._set_metadata_summary(
                self._bottom_tabs,
                tooltip,
                f"Bottom tools tabs: {current} selected. {self._bottom_tabs.count()} tabs. Current page: {current_page}. Panel {visibility}.",
            )
        self._update_workspace_layout_metadata()

    def _update_workspace_layout_metadata(self):
        current_page = self._current_page_accessibility_text() if hasattr(self, "_current_page_accessibility_text") else "none"
        current_panel = self._workspace_panel_label(getattr(self, "_current_left_panel", "project"))
        current_mode = self._editor_mode_label(getattr(getattr(self, "editor_tabs", None), "mode", MODE_DESIGN))
        inspector_section = self._current_tab_text(getattr(self, "_inspector_tabs", None), "Properties")
        bottom_section = self._current_tab_text(getattr(self, "_bottom_tabs", None), "Diagnostics")
        visibility = "visible" if getattr(self, "_bottom_panel_visible", False) else "hidden"
        if hasattr(self, "_editor_container"):
            editor_summary = (
                f"Editor workspace. Left panel: {current_panel}. Current page: {current_page}. "
                f"Mode: {current_mode}. Bottom tools {visibility}."
            )
            self._set_metadata_summary(self._editor_container, editor_summary)
        if hasattr(self, "_center_shell"):
            center_summary = f"Workspace center shell. Current page: {current_page}. Mode: {current_mode}."
            self._set_metadata_summary(self._center_shell, center_summary)
        if hasattr(self, "_top_splitter"):
            top_splitter_summary = (
                f"Workspace columns. Left panel: {current_panel}. Editor mode: {current_mode}. "
                f"Inspector section: {inspector_section}. Current page: {current_page}."
            )
            self._set_metadata_summary(self._top_splitter, top_splitter_summary)
        if hasattr(self, "_workspace_splitter"):
            workspace_splitter_summary = (
                f"Workspace rows. Editor area visible. Bottom tools {visibility}. "
                f"Current section: {bottom_section}. Current page: {current_page}."
            )
            self._set_metadata_summary(self._workspace_splitter, workspace_splitter_summary)
        if hasattr(self, "_bottom_header"):
            bottom_header_summary = f"Bottom tools header. Current section: {bottom_section}. Panel {visibility}."
            self._set_metadata_summary(self._bottom_header, bottom_header_summary)
        if hasattr(self, "_bottom_shell"):
            bottom_shell_summary = (
                f"Workspace bottom shell. Current section: {bottom_section}. Panel {visibility}. "
                f"Current page: {current_page}."
            )
            self._set_metadata_summary(self._bottom_shell, bottom_shell_summary)
        self._update_workspace_command_surface_metadata()

    def _update_page_tab_bar_metadata(self):
        if not hasattr(self, "page_tab_bar"):
            return
        count = self.page_tab_bar.count()
        page_label = f"{count} open page" if count == 1 else f"{count} open pages"
        current_page = "none"
        current_index = self.page_tab_bar.currentIndex()
        if count > 0 and current_index >= 0:
            current_page = self._page_tab_name(current_index)
        elif self._current_page is not None and getattr(self._current_page, "name", ""):
            current_page = self._current_page.name
        project = getattr(self, "project", None)
        project_pages = getattr(project, "pages", []) or []
        startup_value = str(getattr(project, "startup_page", "") or "").strip()
        startup_page = startup_value if any(getattr(page, "name", None) == startup_value for page in project_pages) else "none"
        dirty_pages = set(self._undo_manager.dirty_pages()) if hasattr(self, "_undo_manager") else set()
        dirty_count = len(dirty_pages)
        project_dirty_suffix = self._project_dirty_suffix()
        if dirty_count == 0 and not self._project_dirty:
            dirty_label = "No dirty pages"
        elif dirty_count == 0:
            dirty_label = f"Project changes pending{project_dirty_suffix}"
        elif self._project_dirty:
            page_dirty_label = f"{dirty_count} dirty page" if dirty_count == 1 else f"{dirty_count} dirty pages"
            dirty_label = f"{page_dirty_label} + project changes{project_dirty_suffix}"
        else:
            dirty_label = f"{dirty_count} dirty page" if dirty_count == 1 else f"{dirty_count} dirty pages"
        summary = f"Page tabs: {page_label}. Current page: {current_page}. Startup page: {startup_page}. {dirty_label}."
        if getattr(self, "_page_tab_bar_metadata_snapshot", None) == summary:
            return
        self.page_tab_bar.setToolTip(summary)
        self.page_tab_bar.setStatusTip(summary)
        self.page_tab_bar.setAccessibleName(summary)
        self._page_tab_bar_metadata_snapshot = summary

    def _update_main_view_metadata(self):
        if not hasattr(self, "_central_stack"):
            return
        current_index = self._central_stack.currentIndex()
        view_label = "Welcome page" if current_index == 0 else "Editor workspace"
        summary = f"Main view stack: {view_label} visible."
        self._set_metadata_summary(self._central_stack, summary)
        self._update_workspace_layout_metadata()

    def _sync_editor_mode_controls(self, mode):
        if hasattr(self, "_mode_buttons"):
            for key, button in self._mode_buttons.items():
                button.setChecked(key == mode)
            self._update_editor_mode_button_metadata(mode)
        self._update_workspace_layout_metadata()

    def _editor_mode_label(self, mode):
        return {
            MODE_DESIGN: "Design",
            MODE_SPLIT: "Split",
            MODE_CODE: "Code",
        }.get(mode, str(mode or "Unknown"))

    def _update_editor_mode_button_metadata(self, current_mode):
        if not hasattr(self, "_mode_buttons"):
            return
        current_mode = current_mode or MODE_DESIGN
        for key, button in self._mode_buttons.items():
            label = self._editor_mode_label(key)
            if key == current_mode:
                tooltip = f"Currently showing {label} mode."
                accessible_name = f"Editor mode button: {label}. Current mode."
            else:
                tooltip = f"Switch the workspace editor to {label} mode."
                accessible_name = f"Editor mode button: {label}."
            self._set_metadata_summary(button, tooltip, accessible_name)

    def _set_metadata_summary(self, widget, tooltip, accessible_name=None):
        if widget is None:
            return False
        resolved_tooltip = str(tooltip or "")
        resolved_accessible_name = str(accessible_name or resolved_tooltip)
        snapshot = (resolved_tooltip, resolved_accessible_name)
        if getattr(widget, "_metadata_summary_snapshot", None) == snapshot:
            return False
        widget.setToolTip(resolved_tooltip)
        widget.setStatusTip(resolved_tooltip)
        widget.setAccessibleName(resolved_accessible_name)
        widget._metadata_summary_snapshot = snapshot
        return True

    def _update_workspace_context_label(self, *, page_count=0):
        if getattr(self, "project", None) is None:
            text = "No project open"
            tooltip = "Open or create a project to start editing."
        else:
            project_label = os.path.basename(normalize_path(self._project_dir) or "") or getattr(self, "app_name", "Project")
            current_page = str(getattr(getattr(self, "_current_page", None), "name", "") or "No page")
            text = f"{project_label} / {current_page}"
            page_label = f"{page_count} page" if page_count == 1 else f"{page_count} pages"
            tooltip = f"Current workspace context: {project_label}. Current page: {current_page}. Project contains {page_label}."
        self._workspace_context_summary = {"text": text, "tooltip": tooltip}
        if hasattr(self, "_workspace_context_label"):
            self._workspace_context_label.setText(text)
            self._set_metadata_summary(self._workspace_context_label, tooltip, text)
        if hasattr(self, "_workspace_context_card"):
            self._set_metadata_summary(
                self._workspace_context_card,
                tooltip,
                f"Workspace context card: {text}.",
            )
        if hasattr(self, "_workspace_context_eyebrow"):
            self._set_metadata_summary(
                self._workspace_context_eyebrow,
                "Current workspace context card.",
                "Current workspace context card.",
            )
        self._update_status_bar_summary()

    def _status_bar_hint_text(self, *, has_project, error_count, warning_count, selection_count):
        if not has_project:
            return "Open a project"
        if error_count > 0:
            return "Open Diagnostics"
        if warning_count > 0:
            return "Review warnings"
        if selection_count > 0:
            return "Edit selection"
        return "Ready"

    def _preview_unavailable_reason(self):
        if getattr(self, "project", None) is None:
            return ""
        compiler = getattr(self, "compiler", None)
        if compiler is None:
            return "SDK unavailable, compile preview disabled"
        if not compiler.can_build():
            build_error_getter = getattr(compiler, "get_build_error", None)
            build_error = build_error_getter() if callable(build_error_getter) else ""
            return build_error or "SDK unavailable, compile preview disabled"
        preview_error_getter = getattr(compiler, "get_preview_build_error", None)
        preview_error = preview_error_getter() if callable(preview_error_getter) else ""
        return str(preview_error or "").strip()

    def _preview_retry_blocked_reason(self):
        reason = str(getattr(self, "_auto_compile_retry_block_reason", "") or "").strip()
        if self._preview_retry_block_reason_is_environmental(reason):
            return reason
        return ""

    def _rebuild_retry_block_reason_is_environmental(self, reason=""):
        normalized = str(reason or "").strip()
        if not normalized:
            return False
        return self._missing_make_target_name(normalized).lower() == "clean"

    def _rebuild_retry_blocked_reason(self):
        reason = str(getattr(self, "_rebuild_retry_block_reason", "") or "").strip()
        if self._rebuild_retry_block_reason_is_environmental(reason):
            return reason
        return ""

    def _effective_preview_unavailable_reason(self):
        reason = self._preview_unavailable_reason()
        if reason:
            return reason
        return self._preview_retry_blocked_reason()

    def _effective_rebuild_unavailable_reason(self):
        reason = self._effective_preview_unavailable_reason()
        if reason:
            return reason
        return self._rebuild_retry_blocked_reason()

    def _preview_mode_text(self):
        if getattr(self, "project", None) is None:
            return "No Preview"
        if self._effective_preview_unavailable_reason():
            return "Editing Only"
        if hasattr(self, "preview_panel") and self.preview_panel.is_python_preview_active():
            return "Python Preview"
        is_preview_running = getattr(self.compiler, "is_preview_running", None)
        if callable(is_preview_running) and is_preview_running():
            return "Live Preview"
        is_exe_ready = getattr(self.compiler, "is_exe_ready", None)
        if callable(is_exe_ready) and is_exe_ready():
            return "Preview Ready"
        return "Preview Idle"

    def _update_status_bar_summary(self):
        if not hasattr(self, "_workspace_status_label"):
            return
        diagnostics_counts = (
            self.diagnostics_panel.severity_counts()
            if hasattr(self, "diagnostics_panel")
            else {"error": 0, "warning": 0, "info": 0}
        )
        error_count = int(diagnostics_counts.get("error", 0) or 0)
        warning_count = int(diagnostics_counts.get("warning", 0) or 0)
        has_project = getattr(self, "project", None) is not None
        current_page = str(getattr(getattr(self, "_current_page", None), "name", "") or "none")
        selection_count = len(self._selection_state.widgets) if hasattr(self, "_selection_state") else 0
        if selection_count <= 0:
            selection_text = "none"
        elif selection_count == 1:
            primary = getattr(self._selection_state, "primary", None)
            selection_text = str(
                getattr(primary, "name", "") or getattr(primary, "widget_type", "") or "1 widget"
            )
        else:
            selection_text = f"{selection_count} widgets"
        hint = self._status_bar_hint_text(
            has_project=has_project,
            error_count=error_count,
            warning_count=warning_count,
            selection_count=selection_count,
        )
        preview_text = self._preview_mode_text()
        summary = (
            f"Page: {current_page} | Preview: {preview_text} | Selection: {selection_text} "
            f"| Warnings: {warning_count} | {hint}"
        )
        self._workspace_status_label.setText(summary)
        self._set_metadata_summary(
            self._workspace_status_label,
            summary,
            f"Workspace status bar summary: {summary}.",
        )

    def _update_workspace_command_surface_metadata(self):
        current_panel = self._workspace_panel_label(getattr(self, "_current_left_panel", "project"))
        current_mode = self._editor_mode_label(getattr(getattr(self, "editor_tabs", None), "mode", MODE_DESIGN))
        current_page = self._current_page_accessibility_text()
        if getattr(self, "project", None) is None:
            summary = "Open a project to enable insert, save, preview, and mode controls."
        else:
            summary = (
                f"{current_mode} mode. {current_panel} panel. Current page: {current_page}. "
                "Use commands to insert, save, build, and check runtime."
            )
        if hasattr(self, "_toolbar_command_row"):
            self._set_metadata_summary(
                self._toolbar_command_row,
                summary,
                "Workspace command row.",
            )
        if hasattr(self, "_toolbar_header"):
            self._set_metadata_summary(
                self._toolbar_header,
                "Workspace command header. Engineering summary, current context, and command posture.",
                "Workspace command header. Engineering summary, current context, and command posture.",
            )
        if hasattr(self, "_toolbar_eyebrow_label"):
            self._set_metadata_summary(
                self._toolbar_eyebrow_label,
                "Engineering workspace command surface.",
                "Engineering workspace command surface.",
            )
        if hasattr(self, "_toolbar_title_label"):
            self._set_metadata_summary(
                self._toolbar_title_label,
                "Design command center for insert, save, preview, and mode controls.",
                "Design command center for insert, save, preview, and mode controls.",
            )
        if hasattr(self, "_toolbar_meta_label"):
            self._toolbar_meta_label.setText(summary)
            self._set_metadata_summary(self._toolbar_meta_label, summary, summary)

    def _update_workspace_chips(self):
        diagnostics_counts = self.diagnostics_panel.severity_counts() if hasattr(self, "diagnostics_panel") else {"error": 0, "warning": 0, "info": 0}
        dirty_pages = set(self._undo_manager.dirty_pages()) if hasattr(self, "_undo_manager") else set()
        dirty_count = len(dirty_pages)
        selection_count = len(self._selection_state.widgets) if hasattr(self, "_selection_state") else 0

        page_count = len(getattr(self.project, "pages", [])) if getattr(self, "project", None) is not None else 0
        active_page_name = str(getattr(getattr(self, "_current_page", None), "name", "") or "")
        startup_page_name = ""
        if getattr(self, "project", None) is not None:
            startup_value = str(getattr(self.project, "startup_page", "") or "").strip()
            if any(getattr(page, "name", None) == startup_value for page in getattr(self.project, "pages", []) or []):
                startup_page_name = startup_value
        if hasattr(self, "_project_workspace"):
            self._project_workspace.set_workspace_snapshot(
                page_count=page_count,
                active_page=active_page_name,
                startup_page=startup_page_name,
                dirty_pages=dirty_count,
                project_dirty=self._project_dirty,
                project_dirty_reason=self._project_dirty_reason_text(),
            )
        self._update_workspace_context_label(page_count=page_count)
        self._update_status_bar_summary()
        self._update_workspace_tab_metadata()
        self._update_workspace_nav_button_metadata(getattr(self, "_current_left_panel", "project"))
        self._update_view_panel_navigation_action_metadata()

    def _apply_saved_window_state(self):
        geometry = (self._config.window_geometry or "").strip()
        if geometry:
            try:
                self.restoreGeometry(QByteArray.fromBase64(geometry.encode("ascii")))
            except Exception:
                pass

        layout_state_matches = int(getattr(self._config, "workspace_layout_version", 0) or 0) == WORKSPACE_LAYOUT_VERSION

        workspace_state = getattr(self._config, "workspace_state", {}) if isinstance(getattr(self._config, "workspace_state", {}), dict) else {}
        ui_prefs = UIPreferences.from_workspace_state(workspace_state)
        saved_active_left_panel = str(workspace_state.get("active_left_panel", "") or "").strip()
        self._pending_default_top_splitter_sizes = (not layout_state_matches) or not str(ui_prefs.top_splitter or "").strip()

        if layout_state_matches:
            state = (self._config.window_state or "").strip()
            if state:
                try:
                    self.restoreState(QByteArray.fromBase64(state.encode("ascii")))
                except Exception:
                    pass

            for splitter, state in (
                (getattr(self, "_top_splitter", None), ui_prefs.top_splitter),
                (getattr(self, "_workspace_splitter", None), ui_prefs.workspace_splitter),
            ):
                state = str(state or "").strip()
                if splitter is None or not state:
                    continue
                try:
                    splitter.restoreState(QByteArray.fromBase64(state.encode("ascii")))
                except Exception:
                    pass

        self._select_left_panel(saved_active_left_panel or getattr(self._config, "workspace_left_panel", "project"))
        if hasattr(self, "_inspector_tabs") and self._inspector_tabs.count() > 0:
            inspector_index = {
                "properties": 0,
                "animations": 1,
                "page": 2,
            }.get(str(getattr(ui_prefs, "inspector_section", "properties") or "properties").strip().lower())
            if inspector_index is None:
                inspector_index = max(0, min(ui_prefs.inspector_tab_index, self._inspector_tabs.count() - 1))
            self._inspector_tabs.setCurrentIndex(inspector_index)
        if hasattr(self, "_page_tools_scroll"):
            idx = max(0, min(int(getattr(ui_prefs, "page_tools_tab_index", 0) or 0), 1))
            self._page_tools_section_focus = "timers" if idx else "fields"
            if hasattr(self, "_inspector_tabs") and self._inspector_tabs.currentIndex() == 2:
                self._focus_page_inspector_section(self._page_tools_section_focus)
        if hasattr(self, "_bottom_tabs") and self._bottom_tabs.count() > 0:
            bottom_index = {
                "diagnostics": 0,
                "history": 1,
                "debug_output": 2,
            }.get(str(getattr(ui_prefs, "bottom_panel_kind", "diagnostics") or "diagnostics").strip().lower())
            if bottom_index is None:
                bottom_index = max(0, min(ui_prefs.bottom_tab_index, self._bottom_tabs.count() - 1))
            self._bottom_tabs.setCurrentIndex(bottom_index)
        self._set_bottom_panel_visible(bool(ui_prefs.bottom_panel_visible))
        if bool(getattr(ui_prefs, "focus_canvas_enabled", False)):
            self._set_focus_canvas_enabled(True)

        if hasattr(self, "property_panel"):
            self.property_panel.set_inspector_group_expanded_state(
                getattr(ui_prefs, "inspector_group_expanded", {}) or {},
            )
            self.property_panel.set_property_grid_name_column_width(
                getattr(ui_prefs, "property_grid_name_column_width", 176),
            )

        self._clamp_window_to_available_screen()

    def _apply_pending_workspace_splitter_defaults(self):
        if not getattr(self, "_pending_default_top_splitter_sizes", False):
            return
        if not hasattr(self, "_central_stack") or self._central_stack.currentWidget() is not getattr(self, "_editor_container", None):
            return
        if not hasattr(self, "_top_splitter"):
            self._pending_default_top_splitter_sizes = False
            return
        self._top_splitter.setSizes([
            LEFT_PANEL_DEFAULT_WIDTH,
            CENTER_PANEL_DEFAULT_WIDTH,
            INSPECTOR_PANEL_DEFAULT_WIDTH,
        ])
        self._pending_default_top_splitter_sizes = False

    def _clamp_window_to_available_screen(self):
        """Shrink and/or reposition so the frame fits the primary screen work area."""
        try:
            screen = QGuiApplication.primaryScreen()
            if screen is None:
                return
            avail = screen.availableGeometry()
            margin = 12
            max_w = max(self.minimumWidth(), avail.width() - 2 * margin)
            max_h = max(self.minimumHeight(), avail.height() - 2 * margin)
            tw = min(self.width(), max_w)
            th = min(self.height(), max_h)
            if tw != self.width() or th != self.height():
                self.resize(tw, th)
            fg = self.frameGeometry()
            if fg.right() > avail.right():
                self.move(avail.right() - fg.width() - margin, fg.top())
            if fg.bottom() > avail.bottom():
                self.move(self.x(), avail.bottom() - fg.height() - margin)
            fg = self.frameGeometry()
            if fg.left() < avail.left():
                self.move(avail.left() + margin, fg.top())
            if fg.top() < avail.top():
                self.move(self.x(), avail.top() + margin)
        except Exception:
            pass

    def _save_window_state_to_config(self):
        try:
            self._config.window_geometry = bytes(self.saveGeometry().toBase64()).decode("ascii")
            self._config.window_state = bytes(self.saveState().toBase64()).decode("ascii")
            self._config.workspace_layout_version = WORKSPACE_LAYOUT_VERSION
            self._config.workspace_left_panel = getattr(self, "_current_left_panel", "project")
            ui_prefs = UIPreferences(
                top_splitter=bytes(self._top_splitter.saveState().toBase64()).decode("ascii") if hasattr(self, "_top_splitter") else "",
                workspace_splitter=bytes(self._workspace_splitter.saveState().toBase64()).decode("ascii") if hasattr(self, "_workspace_splitter") else "",
                inspector_tab_index=self._inspector_tabs.currentIndex() if hasattr(self, "_inspector_tabs") else 0,
                inspector_section=(
                    {0: "properties", 1: "animations", 2: "page"}.get(self._inspector_tabs.currentIndex(), "properties")
                    if hasattr(self, "_inspector_tabs")
                    else "properties"
                ),
                page_tools_tab_index=(
                    (1 if getattr(self, "_page_tools_section_focus", "fields") == "timers" else 0)
                    if hasattr(self, "_page_tools_scroll")
                    else 0
                ),
                bottom_tab_index=self._bottom_tabs.currentIndex() if hasattr(self, "_bottom_tabs") else 0,
                bottom_panel_kind=(
                    {0: "diagnostics", 1: "history", 2: "debug_output"}.get(self._bottom_tabs.currentIndex(), "diagnostics")
                    if hasattr(self, "_bottom_tabs")
                    else "diagnostics"
                ),
                bottom_panel_visible=bool(getattr(self, "_bottom_panel_visible", False)),
                focus_canvas_enabled=bool(getattr(self, "_focus_canvas_enabled", False)),
                active_left_panel=getattr(self, "_current_left_panel", "project"),
                panel_layout={},
                inspector_group_expanded=(
                    self.property_panel.inspector_group_expanded_snapshot()
                    if hasattr(self, "property_panel")
                    else {}
                ),
                property_grid_name_column_width=(
                    self.property_panel.property_grid_name_column_width()
                    if hasattr(self, "property_panel")
                    else 176
                ),
            )
            self._config.workspace_state = ui_prefs.to_workspace_state()
        except Exception:
            self._config.window_geometry = ""
            self._config.window_state = ""
            self._config.workspace_state = {}

    def _restore_diagnostics_view_state(self):
        if not hasattr(self, "diagnostics_panel"):
            return
        view_state = self._config.diagnostics_view if isinstance(self._config.diagnostics_view, dict) else {}
        self.diagnostics_panel.restore_view_state(view_state)

    def _save_diagnostics_view_state(self):
        if not hasattr(self, "diagnostics_panel"):
            self._config.diagnostics_view = {}
            return
        self._config.diagnostics_view = self.diagnostics_panel.view_state()

    def _bump_async_generation(self):
        self._async_generation += 1
        self._pending_compile = False
        self._pending_rebuild = False
        self._queued_compile_reasons = []

    def _stop_background_timers(self):
        for timer in (
            self._compile_timer,
            self._embed_timer,
            self._regen_timer,
            self._project_watch_timer,
        ):
            timer.stop()

    @staticmethod
    def _disconnect_worker_signals(worker):
        if worker is None:
            return
        for signal_name in ("finished", "log"):
            signal = getattr(worker, signal_name, None)
            if signal is None:
                continue
            try:
                signal.disconnect()
            except Exception:
                pass

    def _detach_worker(self, worker):
        if worker is None:
            return
        self._disconnect_worker_signals(worker)
        _DETACHED_WORKERS.add(worker)
        try:
            worker.finished.connect(lambda *args, _worker=worker: _discard_detached_worker(_worker))
        except Exception:
            _discard_detached_worker(worker)

    def _cleanup_worker_ref(self, worker, attr_name):
        if worker is None:
            return
        if getattr(self, attr_name, None) is worker:
            setattr(self, attr_name, None)
        if worker in _DETACHED_WORKERS:
            _discard_detached_worker(worker)
            return
        try:
            worker.deleteLater()
        except Exception:
            pass

    def _shutdown_worker(self, worker, attr_name, wait_ms=200):
        if worker is None:
            return
        self._disconnect_worker_signals(worker)
        try:
            worker.requestInterruption()
        except Exception:
            pass
        still_running = False
        try:
            still_running = worker.isRunning()
        except Exception:
            still_running = False
        if still_running:
            try:
                still_running = not worker.wait(wait_ms)
            except Exception:
                still_running = True
        if still_running:
            self._detach_worker(worker)
            if getattr(self, attr_name, None) is worker:
                setattr(self, attr_name, None)
            return
        self._cleanup_worker_ref(worker, attr_name)

    def _shutdown_async_activity(self, wait_ms=200):
        self._stop_background_timers()
        self.preview_panel.stop_rendering()
        self._shutdown_worker(self._compile_worker, "_compile_worker", wait_ms=wait_ms)
        self._shutdown_worker(self._precompile_worker, "_precompile_worker", wait_ms=wait_ms)

    def _describe_sdk_source(self, path=""):
        sdk_root = normalize_path(path or self.project_root)
        if not sdk_root or not is_valid_sdk_root(sdk_root):
            return ""
        return describe_sdk_source(sdk_root)

    def _format_sdk_status_message(self, prefix, path=""):
        sdk_root = normalize_path(path or self.project_root)
        sdk_source = self._describe_sdk_source(sdk_root)
        if sdk_root and sdk_source:
            return f"{prefix}: {sdk_root} [{sdk_source}]"
        if sdk_root:
            return f"{prefix}: {sdk_root}"
        return prefix

    @staticmethod
    def _sdk_revision_text(fingerprint) -> str:
        if fingerprint is None:
            return ""
        for attr in ("revision", "commit_short", "commit"):
            text = str(getattr(fingerprint, attr, "") or "").strip()
            if text:
                return text
        return ""

    def _reset_project_scaffold_for_sdk(self, sdk_fingerprint) -> bool:
        if self.project is None or not self._project_dir:
            return False

        try:
            self.project.sdk_fingerprint = copy.deepcopy(sdk_fingerprint)
            self._save_project_files(self._project_dir, reset_scaffold=True)
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Project Reset Failed",
                f"Failed to reset the project scaffold for the current SDK:\n{exc}",
            )
            return False

        self._refresh_project_watch_snapshot()
        self._update_compile_availability()
        return True

    def _maybe_prompt_sdk_version_reset(self, project, resolved_sdk_root, *, silent=False) -> bool:
        if silent or project is None or not resolved_sdk_root:
            return False

        recorded_revision = self._sdk_revision_text(getattr(project, "sdk_fingerprint", None))
        if not recorded_revision:
            return False

        current_fingerprint = collect_sdk_fingerprint(
            resolved_sdk_root,
            designer_repo_root=_DESIGNER_REPO_ROOT,
        )
        current_revision = self._sdk_revision_text(current_fingerprint)
        if not current_revision or current_revision == recorded_revision:
            return False

        reply = QMessageBox.question(
            self,
            "SDK Version Mismatch",
            "The project was created or last reset against a different SDK revision.\n\n"
            f"Recorded SDK revision:\n{recorded_revision}\n\n"
            f"Current SDK revision:\n{current_revision}\n\n"
            f"Reset the project scaffold now? This regenerates {BUILD_DESIGNER_RELPATH}, "
            f"{APP_CONFIG_DESIGNER_RELPATH}, {DESIGNER_RESOURCE_CONFIG_RELPATH}, "
            "and updates the .egui SDK version metadata while preserving user wrapper/overlay files.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return False

        return self._reset_project_scaffold_for_sdk(current_fingerprint)

    def _apply_sdk_root(self, path, status_message=""):
        path = normalize_path(path)
        if not path:
            return

        self.project_root = path
        self._config.sdk_root = path
        self._config.save()

        if self.project is not None:
            bind_project_storage(self.project, self.project.project_dir, sdk_root=path)
            self._bump_async_generation()
            self._shutdown_async_activity()
            self._clear_rebuild_retry_block()
            self._recreate_compiler()
            preview_unavailable_reason = self._sync_preview_after_compiler_recreation(
                clear_when_available=True,
                preload_preview_error=True,
                probe_preview_availability=True,
            )
            preview_unavailable_reason = preview_unavailable_reason or self._effective_preview_unavailable_reason()
            if preview_unavailable_reason:
                self.statusBar().showMessage(
                    self._status_message_with_editing_only_mode(status_message, preview_unavailable_reason)
                )
            else:
                if self.auto_compile:
                    self._trigger_compile(reason="sdk root change")
            self._update_compile_availability()

        self._welcome_page.refresh()
        self._update_sdk_status_label()
        if status_message and not (self.project is not None and self._effective_preview_unavailable_reason()):
            self.statusBar().showMessage(status_message)

    def _has_valid_sdk_root(self):
        return is_valid_sdk_root(self.project_root)

    def _cleanup_compiler(self, *, stop_exe=False):
        """Release compiler resources without assuming optional hooks exist."""
        compiler = self.compiler
        if compiler is None:
            return
        if stop_exe:
            stop = getattr(compiler, "stop_exe", None)
            if callable(stop):
                stop()
        cleanup = getattr(compiler, "cleanup", None)
        if callable(cleanup):
            cleanup()
        self.compiler = None

    def _recreate_compiler(self):
        self._cleanup_compiler()

        if not self._has_valid_sdk_root() or not self._project_dir or not self.app_name:
            return

        self.compiler = CompilerEngine(self.project_root, self._project_dir, self.app_name)
        if self.project is not None:
            self.compiler.set_screen_size(self.project.screen_width, self.project.screen_height)

    def _update_compile_availability(self):
        preview_error = self._effective_preview_unavailable_reason()
        rebuild_error = self._effective_rebuild_unavailable_reason()
        can_build = (
            self.project is not None
            and self.compiler is not None
            and self._has_valid_sdk_root()
            and self.compiler.can_build()
        )
        can_compile = can_build and not preview_error
        can_rebuild = can_build and not rebuild_error
        resources_dir = self._get_eguiproject_resource_dir()
        resources_state = "available" if resources_dir and os.path.isdir(resources_dir) else "missing"
        self._compile_action.setEnabled(can_compile)
        self._rebuild_action.setEnabled(can_rebuild)
        if hasattr(self, "_clean_all_action"):
            self._clean_all_action.setEnabled(
                self.project is not None
                and bool(self._project_dir)
                and not self._clean_all_recovery_unavailable_reason()
            )
        self.auto_compile_action.setEnabled(can_compile)
        auto_compile_base = "Automatically compile and rerun the preview after changes."
        auto_compile_context = self._auto_compile_action_context_summary()
        self._apply_action_hint(
            self.auto_compile_action,
            (
                f"{auto_compile_base} {auto_compile_context}"
                if self.auto_compile_action.isEnabled()
                else f"{auto_compile_base} {auto_compile_context} Unavailable: {self._compile_action_blocked_reason()}."
            ),
        )
        self._stop_action.setEnabled(self.compiler is not None and self.compiler.is_preview_running())
        self._update_reload_project_action_metadata()
        self._update_build_menu_metadata()
        self._update_file_menu_metadata()
        self._update_file_project_action_metadata()
        self._update_generate_resources_action_metadata()
        self._update_edit_actions()
        self._update_workspace_chips()

    def _switch_to_python_preview(self, reason=""):
        if self._current_page is None:
            self.preview_panel.show_python_preview(None, reason)
            return
        self.preview_panel.show_python_preview(self._current_page, reason)

    def _refresh_python_preview(self, reason=""):
        if self.project is None or self._current_page is None:
            return
        if reason or self.preview_panel.is_python_preview_active() or self.compiler is None:
            self._switch_to_python_preview(reason)
            self.statusBar().showMessage("Using Python fallback preview.", 3000)

    def _persist_current_project_to_config(self):
        self._config.last_app = self.app_name or self._config.last_app
        project_path = self._get_project_file_path()
        self._config.last_project_path = normalize_path(project_path) if project_path else ""
        if self._has_valid_sdk_root():
            self._config.sdk_root = self.project_root
        if self._config.last_project_path:
            self._config.add_recent_project(self._config.last_project_path, self.project_root, self.app_name)
        else:
            self._config.save()
        self._update_recent_menu()

    def _load_project_app_local_widgets(self, project_dir):
        project_dir = normalize_path(project_dir)
        registry = WidgetRegistry.instance()
        if project_dir and registry.app_local_project_dir() == project_dir:
            issues = registry.app_local_issues()
        else:
            issues = registry.load_app_local_widgets(project_dir)
        if not hasattr(self, "debug_panel"):
            return issues
        for issue in issues:
            message = str(issue.get("message", "") or "").strip()
            if not message:
                continue
            if str(issue.get("severity", "warning") or "warning").lower() == "error":
                self.debug_panel.log_error(message)
            else:
                self.debug_panel.log_info(message)
        return issues

    def _build_project_watch_snapshot(self):
        snapshot = {}
        project_file = self._get_project_file_path()
        if not project_file:
            return snapshot

        def _add_path(path):
            path = normalize_path(path)
            if not path or not os.path.exists(path):
                return

            try:
                stat = os.stat(path)
            except OSError:
                return

            snapshot[path] = (
                1 if os.path.isdir(path) else 0,
                stat.st_mtime_ns,
                stat.st_size,
            )

            if not os.path.isdir(path):
                return

            try:
                entries = sorted(os.listdir(path))
            except OSError:
                return

            for name in entries:
                _add_path(os.path.join(path, name))

        watch_roots = [
            project_file,
            self._get_build_mk_path(),
            self._get_app_config_path(),
            self._get_designer_dir(),
            legacy_build_designer_path(self._project_dir),
            legacy_app_config_designer_path(self._project_dir),
            self._get_user_resource_config_path(),
            self._get_designer_resource_dir(),
            self._get_eguiproject_layout_dir(),
            self._get_eguiproject_resource_dir(),
            self._get_eguiproject_mockup_dir(),
            WidgetRegistry.instance().app_local_plugin_dir(self._project_dir),
        ]
        for root in watch_roots:
            _add_path(root)
        from ..utils.header_parser import discover_widget_headers

        for header_path in discover_widget_headers(self._project_dir):
            _add_path(header_path)
        return snapshot

    @staticmethod
    def _diff_project_watch_snapshot(old_snapshot, new_snapshot):
        changed = []
        all_paths = set(old_snapshot.keys()) | set(new_snapshot.keys())
        for path in sorted(all_paths):
            if old_snapshot.get(path) != new_snapshot.get(path):
                changed.append(path)
        return changed

    @staticmethod
    def _summarize_changed_paths(paths):
        if not paths:
            return ""

        labels = [os.path.basename(path) or path for path in paths[:3]]
        summary = ", ".join(labels)
        remaining = len(paths) - len(labels)
        if remaining > 0:
            summary += f" (+{remaining})"
        return summary

    @staticmethod
    def _changed_paths_touch_resource_config(paths):
        watched_names = {
            APP_RESOURCE_CONFIG_FILENAME,
            APP_RESOURCE_CONFIG_DESIGNER_FILENAME,
            DESIGNER_RESOURCE_DIRNAME,
        }
        return any(os.path.basename(path) in watched_names for path in paths or [])

    def _set_external_reload_pending(self, changed_paths=None):
        self._external_reload_pending = True
        self._external_reload_changed_paths = list(changed_paths or [])
        self._update_reload_project_action_metadata()
        self._update_file_menu_metadata()

    def _clear_external_reload_pending(self):
        self._external_reload_pending = False
        self._external_reload_changed_paths = []
        self._update_reload_project_action_metadata()
        self._update_file_menu_metadata()

    def _pending_external_reload_changed_paths(self):
        if self.project is None or not self._project_dir:
            return []
        if not self._project_watch_snapshot:
            return list(getattr(self, "_external_reload_changed_paths", []) or [])
        latest_snapshot = self._build_project_watch_snapshot()
        changed_paths = self._diff_project_watch_snapshot(self._project_watch_snapshot, latest_snapshot)
        self._external_reload_changed_paths = list(changed_paths or [])
        return changed_paths

    def _refresh_project_watch_snapshot(self):
        if self.project is None or not self._project_dir:
            self._project_watch_timer.stop()
            self._project_watch_snapshot = {}
            self._clear_external_reload_pending()
            return

        self._project_watch_snapshot = self._build_project_watch_snapshot()
        self._clear_external_reload_pending()
        if not self._project_watch_timer.isActive():
            self._project_watch_timer.start()

    def _sync_project_watch_snapshot_after_internal_write(self):
        if self.project is None or not self._project_dir or self._external_reload_pending:
            return
        self._project_watch_snapshot = self._build_project_watch_snapshot()
        if not self._project_watch_timer.isActive():
            self._project_watch_timer.start()

    def _poll_project_files(self):
        if self.project is None or not self._project_dir:
            return

        if self._external_reload_pending:
            if self._has_unsaved_changes():
                return
            if self._compile_worker is not None and self._compile_worker.isRunning():
                return
            if self._precompile_worker is not None and self._precompile_worker.isRunning():
                return
            changed_paths = self._pending_external_reload_changed_paths()
            if not changed_paths:
                self._clear_external_reload_pending()
                self.statusBar().showMessage("External project changes resolved. Reload no longer needed.", 4000)
                return
            self._reload_project_from_disk(
                auto=True,
                changed_paths=changed_paths,
            )
            return

        new_snapshot = self._build_project_watch_snapshot()
        if not self._project_watch_snapshot:
            self._project_watch_snapshot = new_snapshot
            return
        if new_snapshot == self._project_watch_snapshot:
            return

        changed_paths = self._diff_project_watch_snapshot(self._project_watch_snapshot, new_snapshot)
        summary = self._summarize_changed_paths(changed_paths)

        if self._has_unsaved_changes():
            self._set_external_reload_pending(changed_paths)
            self.debug_panel.log_info(f"External project change detected while dirty: {summary or 'project files updated'}")
            self.statusBar().showMessage(self._external_reload_blocked_text(summary), 5000)
            return

        if self._compile_worker is not None and self._compile_worker.isRunning():
            self._set_external_reload_pending(changed_paths)
            self.statusBar().showMessage(self._external_reload_compile_wait_text(summary), 4000)
            return

        if self._precompile_worker is not None and self._precompile_worker.isRunning():
            self._set_external_reload_pending(changed_paths)
            self.statusBar().showMessage(self._external_reload_compile_wait_text(summary), 4000)
            return

        self._reload_project_from_disk(auto=True, changed_paths=changed_paths)

    def _resume_pending_external_reload_if_ready(self, generation):
        if not self._external_reload_pending or self._has_unsaved_changes():
            return False
        self._poll_project_files()
        return self._is_closing or generation != self._async_generation or self._external_reload_pending

    def _reload_project_from_disk(self, checked=False, auto=False, changed_paths=None):
        del checked
        if self.project is None or not self._project_dir:
            return False

        if self._has_unsaved_changes():
            reply = QMessageBox.question(
                self,
                "Reload Project",
                self._unsaved_changes_prompt_text("reload"),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return False

        current_page_name = self._current_page.name if self._current_page else ""

        try:
            project = load_saved_project_model(self._project_dir)
        except Exception as exc:
            self._set_external_reload_pending(changed_paths or getattr(self, "_external_reload_changed_paths", []))
            self.debug_panel.log_error(f"Project reload failed: {exc}")
            self._show_bottom_panel("Debug Output")
            if auto:
                self.statusBar().showMessage(f"Project reload failed: {exc}", 6000)
            else:
                QMessageBox.critical(self, "Reload Project Failed", f"Failed to reload project:\n{exc}")
            return False

        resource_config_changed = self._changed_paths_touch_resource_config(changed_paths or [])
        if resource_config_changed:
            self._resources_need_regen = True

        self._open_loaded_project(project, self._project_dir, preferred_sdk_root=self.project_root, silent=True)
        if current_page_name and self.project and self.project.get_page_by_name(current_page_name):
            if self._current_page is None or self._current_page.name != current_page_name:
                self._switch_page(current_page_name)

        summary = self._summarize_changed_paths(changed_paths or [])
        preview_unavailable_reason = self._effective_preview_unavailable_reason()
        if auto:
            self.debug_panel.log_info(f"Project reloaded from disk: {summary or 'external changes applied'}")
            self.statusBar().showMessage(
                self._status_message_with_editing_only_mode(
                    f"Reloaded external changes: {summary or 'project updated'}",
                    preview_unavailable_reason,
                ),
                5000,
            )
        else:
            self.statusBar().showMessage(
                self._status_message_with_editing_only_mode(
                    "Project reloaded from disk",
                    preview_unavailable_reason,
                ),
                4000,
            )
        return True

    def _clear_editor_state(self):
        self._stop_background_timers()
        self.preview_panel.stop_rendering()
        self._last_runtime_error_text = ""
        self._clear_rebuild_retry_block()
        self._project_watch_snapshot = {}
        self._clear_external_reload_pending()
        self._pending_page_renames = {}
        self._clear_project_dirty()
        self._active_batch_source = ""
        self._selected_widget = None
        self._selection_state.clear()
        self._pending_insert_parent = None
        self._current_page = None
        self._clear_page_tabs()
        self.widget_tree.set_project(None)
        self.property_panel.set_selection([])
        self.preview_panel.set_widgets([])
        self.preview_panel.set_selection([])
        self.preview_panel.clear_background_image()
        self.project_dock.set_project(None)
        self.page_navigator.set_pages({})
        self.page_navigator.set_current_page("")
        self.history_panel.clear()
        self.diagnostics_panel.clear()
        self.animations_panel.clear()
        self.page_fields_panel.clear()
        self.page_timers_panel.clear()
        self._update_debug_rebuild_action(show=False)
        self._update_edit_actions()
        self._update_widget_browser_target(preferred_parent=None)
        self._update_workspace_chips()
        self._update_workspace_tab_metadata()

    def _is_auto_compile_retry_blocked(self):
        return bool(self._auto_compile_retry_block_reason)

    def _block_auto_compile_retry(self, reason=""):
        self._auto_compile_retry_block_reason = str(reason or "").strip()
        self._compile_timer.stop()
        self._pending_compile = False
        self._queued_compile_reasons = []

    def _block_rebuild_retry(self, reason=""):
        self._rebuild_retry_block_reason = str(reason or "").strip()

    def _clear_auto_compile_retry_block(self):
        self._auto_compile_retry_block_reason = ""

    def _clear_rebuild_retry_block(self):
        self._rebuild_retry_block_reason = ""

    def _preview_retry_block_reason_is_environmental(self, reason=""):
        normalized = str(reason or "").strip()
        if not normalized:
            return False
        lowered = normalized.lower()
        missing_target = self._missing_make_target_name(normalized).lower()
        return (
            missing_target in {"main.exe", "main", "clean"}
            or "preview build unavailable" in lowered
            or "preview build target unavailable" in lowered
            or "preview build target probe timed out" in lowered
            or "sdk unavailable, compile preview disabled" in lowered
            or "make not found" in lowered
        )

    def _sync_auto_compile_retry_block_for_preview_state(self, *, clear_when_available=False, preload_preview_error=False):
        reason = self._preview_unavailable_reason()
        if reason:
            if preload_preview_error or self._is_auto_compile_retry_blocked():
                self._block_auto_compile_retry(reason)
        else:
            should_clear = clear_when_available or self._preview_retry_block_reason_is_environmental(
                self._auto_compile_retry_block_reason
            )
            if should_clear:
                self._clear_auto_compile_retry_block()
        return reason

    def _sync_preview_after_compiler_recreation(
        self,
        *,
        clear_when_available=False,
        preload_preview_error=False,
        probe_environmental_recovery=False,
        probe_preview_availability=False,
    ):
        previous_reason = str(self._auto_compile_retry_block_reason or "").strip()
        if self.compiler is not None and self.compiler.can_build():
            ensure_available = getattr(self.compiler, "ensure_preview_build_available", None)
            should_probe = probe_preview_availability or (
                probe_environmental_recovery
                and previous_reason
                and self._preview_retry_block_reason_is_environmental(previous_reason)
            )
            if should_probe and callable(ensure_available):
                ensure_available(force=True)
        reason = self._sync_auto_compile_retry_block_for_preview_state(
            clear_when_available=clear_when_available,
            preload_preview_error=preload_preview_error,
        )
        if reason:
            self._switch_to_python_preview(reason)
        return reason

    @staticmethod
    def _status_message_with_editing_only_mode(status_message, preview_unavailable_reason=""):
        reason = str(preview_unavailable_reason or "").strip()
        if not reason:
            return status_message
        if status_message:
            return f"{status_message} | Editing-only mode: {reason}"
        return f"Editing-only mode: {reason}"

    def _should_offer_debug_rebuild_action(self, reason=""):
        return not (
            self._preview_retry_block_reason_is_environmental(reason)
            or self._rebuild_retry_block_reason_is_environmental(reason)
        )

    def _open_loaded_project(self, project, project_dir, preferred_sdk_root="", silent=False):
        project_dir = normalize_path(project_dir)
        self._bump_async_generation()
        self._shutdown_async_activity()
        self._last_runtime_error_text = ""
        self._clear_rebuild_retry_block()
        self._load_project_app_local_widgets(project_dir)
        resolved_sdk_root = self._resolve_ui_sdk_root(
            preferred_sdk_root or project.sdk_root,
            infer_sdk_root_from_project_dir(project_dir),
            self.project_root,
            self._config.sdk_root,
        )
        bind_project_storage(
            project,
            project_dir,
            sdk_root=resolved_sdk_root or normalize_path(preferred_sdk_root or project.sdk_root),
        )

        self.project = project
        self._project_dir = project_dir
        self.project_root = project.sdk_root
        self.app_name = project.app_name
        self._undo_manager = UndoManager()
        self._pending_page_renames = {}
        self._clear_project_dirty()
        self._recreate_compiler()
        self._sync_auto_compile_retry_block_for_preview_state()
        self._show_editor()
        self._clear_editor_state()
        self._update_sdk_status_label()
        self._apply_project()
        self._update_window_title()
        self._persist_current_project_to_config()
        self._refresh_project_watch_snapshot()

        startup = project.get_startup_page()
        if startup:
            self._switch_page(startup.name)
        elif project.pages:
            self._switch_page(project.pages[0].name)

        project_reset = self._maybe_prompt_sdk_version_reset(
            project,
            project.sdk_root,
            silent=silent,
        )

        sdk_source = self._describe_sdk_source(project.sdk_root)
        suffix = " | Project scaffold reset" if project_reset else ""
        if sdk_source:
            opened_status_message = f"Opened: {project_dir} | SDK: {sdk_source}{suffix}"
        else:
            opened_status_message = f"Opened: {project_dir}{suffix}"
        preview_unavailable_reason = self._effective_preview_unavailable_reason()
        if preview_unavailable_reason:
            self._switch_to_python_preview(preview_unavailable_reason)
            self.statusBar().showMessage(
                self._status_message_with_editing_only_mode(opened_status_message, preview_unavailable_reason)
            )
        else:
            self._trigger_compile(reason="project open")
            self.statusBar().showMessage(opened_status_message)

        if not project.sdk_root and not silent:
            QMessageBox.information(
                self,
                "SDK Root Missing",
                "The project opened successfully, but no valid EmbeddedGUI SDK root was found. Preview will use Python fallback until you set the SDK root.",
            )

    # 鈹€鈹€ View switching 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    def _show_welcome_page(self):
        """Show the welcome page (hide editor)."""
        if self.project is None:
            WidgetRegistry.instance().clear_app_local_widgets()
        self._central_stack.setCurrentIndex(0)
        self._welcome_page.refresh()
        self.setWindowTitle("EmbeddedGUI Designer")
        self._update_debug_rebuild_action(show=False)
        self._update_main_view_metadata()
        self._update_sdk_status_label()

    def _show_editor(self):
        """Show the editor (hide welcome page)."""
        self._central_stack.setCurrentIndex(1)
        self._update_widget_browser_target()
        self._update_main_view_metadata()

    def _create_page_tab_bar(self):
        page_tab_bar = TabBar()
        page_tab_bar.setMovable(True)
        page_tab_bar.setTabsClosable(True)
        page_tab_bar.setScrollable(True)
        page_tab_bar.setAddButtonVisible(False)
        page_tab_bar.setCloseButtonDisplayMode(TabCloseButtonDisplayMode.ON_HOVER)
        page_tab_bar.setTabMaximumWidth(PAGE_TAB_BAR_MAX_WIDTH)
        page_tab_bar.setTabShadowEnabled(False)
        page_tab_bar.setFixedHeight(PAGE_TAB_BAR_HEIGHT)
        page_tab_bar.tabCloseRequested.connect(self._on_page_tab_closed)
        page_tab_bar.currentChanged.connect(self._on_page_tab_changed)
        page_tab_bar.setContextMenuPolicy(Qt.CustomContextMenu)
        page_tab_bar.customContextMenuRequested.connect(self._show_tab_context_menu)
        page_tab_bar.currentChanged.connect(lambda _index: self._update_page_tab_bar_metadata())
        self._update_page_tab_bar_metadata()
        return page_tab_bar

    def _replace_page_tab_bar(self):
        old_tab_bar = self.page_tab_bar
        parent = old_tab_bar.parentWidget()
        layout = parent.layout() if parent is not None else None
        index = layout.indexOf(old_tab_bar) if layout is not None else -1

        self.page_tab_bar = self._create_page_tab_bar()
        if layout is not None:
            if index < 0:
                layout.addWidget(self.page_tab_bar)
            else:
                layout.insertWidget(index, self.page_tab_bar)

        old_tab_bar.setParent(None)
        old_tab_bar.deleteLater()

    def _clear_page_tabs(self):
        try:
            self.page_tab_bar.clear()
        except RuntimeError:
            self._replace_page_tab_bar()
        self._update_page_tab_bar_metadata()

    def _init_menus(self):
        menubar = self.menuBar()

        # 鈹€鈹€ File menu 鈹€鈹€
        file_menu = menubar.addMenu("File")
        self._file_menu = file_menu
        self._apply_action_hint(file_menu.menuAction(), "Create, open, save, export, and close projects.")

        self._new_project_action = QAction("New Project", self)
        self._new_project_action.setShortcut("Ctrl+N")
        self._apply_action_hint(self._new_project_action, "Create a new EmbeddedGUI Designer project.")
        self._new_project_action.triggered.connect(self._new_project)
        file_menu.addAction(self._new_project_action)

        self._open_app_action = QAction("Open Example...", self)
        self._open_app_action.setShortcut("Ctrl+Shift+O")
        self._apply_action_hint(
            self._open_app_action,
            "Open a bundled example, SDK example project, or initialize a Designer project for an unmanaged SDK example.",
        )
        self._open_app_action.triggered.connect(self._open_app_dialog)
        file_menu.addAction(self._open_app_action)

        self._open_project_action = QAction("Open Project...", self)
        self._open_project_action.setShortcut("Ctrl+O")
        self._apply_action_hint(self._open_project_action, "Open an existing .egui project file.")
        self._open_project_action.triggered.connect(self._open_project)
        file_menu.addAction(self._open_project_action)

        self._set_sdk_root_action = QAction("Set SDK...", self)
        self._apply_action_hint(self._set_sdk_root_action, "Choose the EmbeddedGUI SDK root used for compile preview.")
        self._set_sdk_root_action.triggered.connect(self._set_sdk_root)
        file_menu.addAction(self._set_sdk_root_action)

        # Recent Projects submenu
        self._recent_menu = file_menu.addMenu("Recent")
        self._apply_action_hint(self._recent_menu.menuAction(), "Open a recently used project.")
        self._update_recent_menu()

        file_menu.addSeparator()

        self._save_action = QAction("Save Project", self)
        self._save_action.setShortcut("Ctrl+S")
        self._save_action.triggered.connect(self._save_project)
        file_menu.addAction(self._save_action)

        self._save_as_action = QAction("Save As...", self)
        self._save_as_action.setShortcut("Ctrl+Shift+S")
        self._apply_action_hint(self._save_as_action, "Save the current project to a new file (Ctrl+Shift+S).")
        self._save_as_action.triggered.connect(self._save_project_as)
        file_menu.addAction(self._save_as_action)

        self._reload_project_action = QAction("Reload Project From Disk", self)
        self._reload_project_action.setShortcut("Ctrl+Shift+R")
        self._reload_project_action.triggered.connect(self._reload_project_from_disk)
        self._reload_project_action.setEnabled(False)
        self._apply_action_hint(
            self._reload_project_action,
            self._action_hint("Reload the current project from disk (Ctrl+Shift+R).", False, "open a project first"),
        )
        file_menu.addAction(self._reload_project_action)

        file_menu.addSeparator()

        self._close_project_action = QAction("Close Project", self)
        self._close_project_action.setShortcut("Ctrl+W")
        self._apply_action_hint(self._close_project_action, "Close the current project (Ctrl+W).")
        self._close_project_action.triggered.connect(self._close_project)
        file_menu.addAction(self._close_project_action)

        file_menu.addSeparator()

        self._export_action = QAction("Export C Code...", self)
        self._export_action.setShortcut("Ctrl+E")
        self._apply_action_hint(self._export_action, "Export generated C code for the current project (Ctrl+E).")
        self._export_action.triggered.connect(self._export_code)
        file_menu.addAction(self._export_action)

        file_menu.addSeparator()

        self._quit_action = QAction("Quit", self)
        self._quit_action.setShortcut("Ctrl+Q")
        self._apply_action_hint(self._quit_action, "Quit EmbeddedGUI Designer (Ctrl+Q).")
        self._quit_action.triggered.connect(self.close)
        file_menu.addAction(self._quit_action)

        # 鈹€鈹€ Edit menu 鈹€鈹€
        edit_menu = menubar.addMenu("Edit")
        self._edit_menu = edit_menu
        self._apply_action_hint(edit_menu.menuAction(), "Undo changes and work with the current selection.")

        self._undo_action = QAction("Undo", self)
        self._undo_action.setShortcut("Ctrl+Z")
        self._undo_action.setEnabled(False)
        self._undo_action.triggered.connect(self._undo)
        edit_menu.addAction(self._undo_action)

        self._redo_action = QAction("Redo", self)
        self._redo_action.setShortcut("Ctrl+Shift+Z")
        self._redo_action.setEnabled(False)
        self._redo_action.triggered.connect(self._redo)
        edit_menu.addAction(self._redo_action)

        self._select_all_action = QAction("Select All", self)
        self._select_all_action.setShortcut("Ctrl+A")
        self._select_all_action.triggered.connect(self._select_all)
        edit_menu.addAction(self._select_all_action)

        edit_menu.addSeparator()

        self._copy_action = QAction("Copy", self)
        self._copy_action.setShortcut("Ctrl+C")
        self._copy_action.triggered.connect(self._copy_selection)
        edit_menu.addAction(self._copy_action)

        self._cut_action = QAction("Cut", self)
        self._cut_action.setShortcut("Ctrl+X")
        self._cut_action.triggered.connect(self._cut_selection)
        edit_menu.addAction(self._cut_action)

        self._paste_action = QAction("Paste", self)
        self._paste_action.setShortcut("Ctrl+V")
        self._paste_action.triggered.connect(self._paste_selection)
        edit_menu.addAction(self._paste_action)

        self._duplicate_action = QAction("Duplicate", self)
        self._duplicate_action.setShortcut("Ctrl+D")
        self._duplicate_action.triggered.connect(self._duplicate_selection)
        edit_menu.addAction(self._duplicate_action)

        self._delete_action = QAction("Delete", self)
        self._delete_action.setShortcut("Del")
        self._delete_action.triggered.connect(self._delete_selection)
        edit_menu.addAction(self._delete_action)

        arrange_menu = menubar.addMenu("Arrange")
        self._arrange_menu = arrange_menu
        self._apply_action_hint(
            arrange_menu.menuAction(),
            "Align, distribute, reorder, lock, and hide selected widgets.",
        )

        self._align_left_action = QAction("Align Left", self)
        self._align_left_action.setIcon(make_icon("layout.align.left"))
        self._apply_action_hint(self._align_left_action, "Align the current selection to the left edge of the primary widget.")
        self._align_left_action.triggered.connect(lambda: self._align_selection("left"))
        arrange_menu.addAction(self._align_left_action)

        self._align_right_action = QAction("Align Right", self)
        self._align_right_action.setIcon(make_icon("layout.align.right"))
        self._apply_action_hint(self._align_right_action, "Align the current selection to the right edge of the primary widget.")
        self._align_right_action.triggered.connect(lambda: self._align_selection("right"))
        arrange_menu.addAction(self._align_right_action)

        self._align_top_action = QAction("Align Top", self)
        self._align_top_action.setIcon(make_icon("layout.align.top"))
        self._apply_action_hint(self._align_top_action, "Align the current selection to the top edge of the primary widget.")
        self._align_top_action.triggered.connect(lambda: self._align_selection("top"))
        arrange_menu.addAction(self._align_top_action)

        self._align_bottom_action = QAction("Align Bottom", self)
        self._align_bottom_action.setIcon(make_icon("layout.align.bottom"))
        self._apply_action_hint(
            self._align_bottom_action,
            "Align the current selection to the bottom edge of the primary widget.",
        )
        self._align_bottom_action.triggered.connect(lambda: self._align_selection("bottom"))
        arrange_menu.addAction(self._align_bottom_action)

        self._align_hcenter_action = QAction("Align Horizontal Center", self)
        self._align_hcenter_action.setIcon(make_icon("layout.align.center"))
        self._apply_action_hint(
            self._align_hcenter_action,
            "Align the current selection to the horizontal center of the primary widget.",
        )
        self._align_hcenter_action.triggered.connect(lambda: self._align_selection("hcenter"))
        arrange_menu.addAction(self._align_hcenter_action)

        self._align_vcenter_action = QAction("Align Vertical Center", self)
        self._align_vcenter_action.setIcon(make_icon("layout.align.middle"))
        self._apply_action_hint(
            self._align_vcenter_action,
            "Align the current selection to the vertical center of the primary widget.",
        )
        self._align_vcenter_action.triggered.connect(lambda: self._align_selection("vcenter"))
        arrange_menu.addAction(self._align_vcenter_action)

        arrange_menu.addSeparator()

        self._distribute_h_action = QAction("Distribute Horizontally", self)
        self._distribute_h_action.setIcon(make_icon("layout.distribute.h"))
        self._apply_action_hint(
            self._distribute_h_action,
            "Distribute the current selection evenly across the horizontal axis.",
        )
        self._distribute_h_action.triggered.connect(lambda: self._distribute_selection("horizontal"))
        arrange_menu.addAction(self._distribute_h_action)

        self._distribute_v_action = QAction("Distribute Vertically", self)
        self._distribute_v_action.setIcon(make_icon("layout.distribute.v"))
        self._apply_action_hint(
            self._distribute_v_action,
            "Distribute the current selection evenly across the vertical axis.",
        )
        self._distribute_v_action.triggered.connect(lambda: self._distribute_selection("vertical"))
        arrange_menu.addAction(self._distribute_v_action)

        arrange_menu.addSeparator()

        self._bring_front_action = QAction("Bring to Front", self)
        self._bring_front_action.setIcon(make_icon("canvas.layer.top"))
        self._apply_action_hint(
            self._bring_front_action,
            "Bring the current selection to the front of its parent stack.",
        )
        self._bring_front_action.triggered.connect(self._move_selection_to_front)
        arrange_menu.addAction(self._bring_front_action)

        self._send_back_action = QAction("Send to Back", self)
        self._send_back_action.setIcon(make_icon("canvas.layer.bottom"))
        self._apply_action_hint(
            self._send_back_action,
            "Send the current selection to the back of its parent stack.",
        )
        self._send_back_action.triggered.connect(self._move_selection_to_back)
        arrange_menu.addAction(self._send_back_action)

        arrange_menu.addSeparator()

        self._toggle_lock_action = QAction("Toggle Lock", self)
        self._toggle_lock_action.setIcon(make_icon("edit.lock"))
        self._apply_action_hint(
            self._toggle_lock_action,
            "Toggle the designer lock state for the current selection.",
        )
        self._toggle_lock_action.triggered.connect(self._toggle_selection_locked)
        arrange_menu.addAction(self._toggle_lock_action)

        self._toggle_hide_action = QAction("Toggle Hide", self)
        self._toggle_hide_action.setIcon(make_icon("edit.hidden"))
        self._apply_action_hint(
            self._toggle_hide_action,
            "Toggle the designer visibility state for the current selection.",
        )
        self._toggle_hide_action.triggered.connect(self._toggle_selection_hidden)
        arrange_menu.addAction(self._toggle_hide_action)

        structure_menu = menubar.addMenu("Structure")
        self._apply_action_hint(
            structure_menu.menuAction(),
            "Group, move, and reorder widgets in the page hierarchy.",
        )
        self._structure_menu = structure_menu

        self._group_selection_action = QAction("Group Selection", self)
        self._group_selection_action.setIcon(make_icon("nav.page_group"))
        self._group_selection_action.setShortcut("Ctrl+G")
        self._group_selection_action.triggered.connect(self._group_selection)
        structure_menu.addAction(self._group_selection_action)

        self._ungroup_selection_action = QAction("Ungroup", self)
        self._ungroup_selection_action.setIcon(make_icon("nav.component_library"))
        self._ungroup_selection_action.setShortcut("Ctrl+Shift+G")
        self._ungroup_selection_action.triggered.connect(self._ungroup_selection)
        structure_menu.addAction(self._ungroup_selection_action)

        self._move_into_container_action = QAction("Move Into...", self)
        self._move_into_container_action.setShortcut("Ctrl+Shift+I")
        self._move_into_container_action.triggered.connect(self._move_selection_into_container)
        structure_menu.addAction(self._move_into_container_action)

        self._lift_to_parent_action = QAction("Lift To Parent", self)
        self._lift_to_parent_action.setShortcut("Ctrl+Shift+L")
        self._lift_to_parent_action.triggered.connect(self._lift_selection_to_parent)
        structure_menu.addAction(self._lift_to_parent_action)

        structure_menu.addSeparator()

        self._move_up_action = QAction("Move Up", self)
        self._move_up_action.setIcon(make_icon("canvas.layer.up"))
        self._move_up_action.setShortcut("Alt+Up")
        self._move_up_action.triggered.connect(self._move_selection_up)
        structure_menu.addAction(self._move_up_action)

        self._move_down_action = QAction("Move Down", self)
        self._move_down_action.setIcon(make_icon("canvas.layer.down"))
        self._move_down_action.setShortcut("Alt+Down")
        self._move_down_action.triggered.connect(self._move_selection_down)
        structure_menu.addAction(self._move_down_action)

        self._move_top_action = QAction("Move To Top", self)
        self._move_top_action.setIcon(make_icon("canvas.layer.top"))
        self._move_top_action.setShortcut("Alt+Shift+Up")
        self._move_top_action.triggered.connect(self._move_selection_to_top)
        structure_menu.addAction(self._move_top_action)

        self._move_bottom_action = QAction("Move To Bottom", self)
        self._move_bottom_action.setIcon(make_icon("canvas.layer.bottom"))
        self._move_bottom_action.setShortcut("Alt+Shift+Down")
        self._move_bottom_action.triggered.connect(self._move_selection_to_bottom)
        structure_menu.addAction(self._move_bottom_action)
        self._structure_action_hints = {
            self._group_selection_action: ("Group the current selection (Ctrl+G)", "group_reason"),
            self._ungroup_selection_action: ("Ungroup the selected group widgets (Ctrl+Shift+G)", "ungroup_reason"),
            self._move_into_container_action: ("Move the current selection into another container (Ctrl+Shift+I)", "move_into_reason"),
            self._lift_to_parent_action: ("Lift the current selection to the parent container (Ctrl+Shift+L)", "lift_reason"),
            self._move_up_action: ("Move the current selection up among its siblings (Alt+Up)", "move_up_reason"),
            self._move_down_action: ("Move the current selection down among its siblings (Alt+Down)", "move_down_reason"),
            self._move_top_action: ("Move the current selection to the top of its sibling list (Alt+Shift+Up)", "move_top_reason"),
            self._move_bottom_action: ("Move the current selection to the bottom of its sibling list (Alt+Shift+Down)", "move_bottom_reason"),
        }
        for action, (hint, _reason_attr) in self._structure_action_hints.items():
            self._apply_action_hint(action, hint)

        # 鈹€鈹€ Build menu 鈹€鈹€
        build_menu = menubar.addMenu("Build")
        self._build_menu = build_menu
        self._apply_action_hint(
            build_menu.menuAction(),
            "Build previews, generate resources, or reconstruct the project from Designer sources.",
        )

        self._compile_action = QAction("Build EXE && Run", self)
        self._compile_action.setShortcut("F5")
        self._compile_action.triggered.connect(self._do_compile_and_run)
        build_menu.addAction(self._compile_action)

        self._rebuild_action = QAction("Rebuild EGUI Project", self)
        self._rebuild_action.setShortcut("Ctrl+F5")
        self._rebuild_action.triggered.connect(self._do_rebuild_egui_project)
        build_menu.addAction(self._rebuild_action)
        self.debug_panel.rebuild_requested.connect(self._do_rebuild_egui_project)
        self._update_debug_rebuild_action(show=False)

        self._clean_all_action = QAction("Clean All && Reconstruct", self)
        self._clean_all_action.setShortcut("Ctrl+Shift+F5")
        self._clean_all_action.triggered.connect(self._do_clean_all_and_reconstruct)
        build_menu.addAction(self._clean_all_action)

        self.auto_compile_action = QAction("Auto Compile", self)
        self.auto_compile_action.setCheckable(True)
        self.auto_compile_action.setChecked(self.auto_compile)
        self._apply_action_hint(self.auto_compile_action, "Automatically compile and rerun the preview after changes.")
        self.auto_compile_action.toggled.connect(self._toggle_auto_compile)
        build_menu.addAction(self.auto_compile_action)

        self._stop_action = QAction("Stop Exe", self)
        self._stop_action.triggered.connect(self._stop_exe)
        build_menu.addAction(self._stop_action)

        build_menu.addSeparator()

        self._generate_resources_action = QAction("Generate Resources", self)
        self._apply_action_hint(
            self._generate_resources_action,
            _GENERATE_RESOURCES_HINT_PREFIX.rstrip(),
        )
        self._generate_resources_action.triggered.connect(self._generate_resources)
        build_menu.addAction(self._generate_resources_action)
        self._update_generate_resources_action_metadata()
        self._update_build_menu_metadata()

        # View menu surface map (UI-S0-003):
        # - Theme / Font: global chrome.
        # - Workspace: left rail panels (project, structure, components, assets).
        # - Inspector: right tabs (properties, animations, page).
        # - Tools + overlay/grid/mockup: bottom panel + preview presentation.
        # There is no separate "Window" menu on this app; use the OS window frame.
        view_menu = menubar.addMenu("View")
        self._view_menu = view_menu
        self._apply_action_hint(
            view_menu.menuAction(),
            "Change workspace layout, themes, preview modes, and mockup options.",
        )

        # Theme Submenu
        theme_menu = view_menu.addMenu("Theme")
        self._theme_menu = theme_menu
        self._apply_action_hint(theme_menu.menuAction(), "Choose the Designer theme.")
        theme_group = QActionGroup(self)
        theme_group.setExclusive(True)

        self.theme_dark_action = QAction("Dark", self)
        self.theme_dark_action.setCheckable(True)
        self.theme_dark_action.setChecked(self._config.theme == 'dark')
        self._apply_action_hint(self.theme_dark_action, "Switch the Designer theme to dark.")
        self.theme_dark_action.triggered.connect(lambda: self._set_theme('dark'))
        theme_group.addAction(self.theme_dark_action)
        theme_menu.addAction(self.theme_dark_action)

        self.theme_light_action = QAction("Light", self)
        self.theme_light_action.setCheckable(True)
        self.theme_light_action.setChecked(self._config.theme == 'light')
        self._apply_action_hint(self.theme_light_action, "Switch the Designer theme to light.")
        self.theme_light_action.triggered.connect(lambda: self._set_theme('light'))
        theme_group.addAction(self.theme_light_action)
        theme_menu.addAction(self.theme_light_action)

        density_menu = view_menu.addMenu("UI Density")
        self._density_menu = density_menu
        self._apply_action_hint(density_menu.menuAction(), "Choose standard or roomy UI density.")
        density_group = QActionGroup(self)
        density_group.setExclusive(True)

        self._density_standard_action = QAction("Standard", self)
        self._density_standard_action.setCheckable(True)
        self._density_standard_action.setChecked(str(getattr(self._config, "ui_density", "standard") or "standard") == "standard")
        self._apply_action_hint(self._density_standard_action, "Use the default compact-balanced UI density.")
        self._density_standard_action.triggered.connect(lambda: self._set_ui_density("standard"))
        density_group.addAction(self._density_standard_action)
        density_menu.addAction(self._density_standard_action)

        self._density_roomy_action = QAction("Roomy", self)
        self._density_roomy_action.setCheckable(True)
        self._density_roomy_action.setChecked(str(getattr(self._config, "ui_density", "standard") or "standard") == "roomy")
        self._apply_action_hint(self._density_roomy_action, "Use larger text and roomier controls for readability.")
        self._density_roomy_action.triggered.connect(lambda: self._set_ui_density("roomy"))
        density_group.addAction(self._density_roomy_action)
        density_menu.addAction(self._density_roomy_action)

        self._density_roomy_plus_action = QAction("Roomy+", self)
        self._density_roomy_plus_action.setCheckable(True)
        self._density_roomy_plus_action.setChecked(
            str(getattr(self._config, "ui_density", "standard") or "standard") in {"roomy_plus", "roomy+"}
        )
        self._apply_action_hint(
            self._density_roomy_plus_action,
            "Use the most readable profile with larger text and extra spacing.",
        )
        self._density_roomy_plus_action.triggered.connect(lambda: self._set_ui_density("roomy_plus"))
        density_group.addAction(self._density_roomy_plus_action)
        density_menu.addAction(self._density_roomy_plus_action)

        view_menu.addSeparator()

        self._font_size_action = QAction("Font Size...", self)
        self._apply_action_hint(self._font_size_action, "Adjust the Designer font size.")
        self._font_size_action.triggered.connect(self._set_font_sizes)
        view_menu.addAction(self._font_size_action)

        view_menu.addSeparator()

        workspace_menu = view_menu.addMenu("Workspace")
        self._workspace_menu = workspace_menu
        self._workspace_view_actions = {}
        self._apply_action_hint(workspace_menu.menuAction(), "Choose a workspace panel to show.")
        for label, key in (
            ("Project", "project"),
            ("Structure", "structure"),
            ("Components", "widgets"),
            ("Assets", "assets"),
        ):
            action = QAction(label, self)
            self._apply_action_hint(action, f"Show the {label} workspace panel.")
            action.triggered.connect(lambda checked=False, panel_key=key: self._select_left_panel(panel_key))
            workspace_menu.addAction(action)
            self._workspace_view_actions[key] = action

        inspector_menu = view_menu.addMenu("Inspector")
        self._inspector_menu = inspector_menu
        self._inspector_view_actions = {}
        self._apply_action_hint(inspector_menu.menuAction(), "Choose an inspector section to show.")
        for label, key in (
            ("Properties", "properties"),
            ("Animations", "animations"),
            ("Page", "page"),
        ):
            action = QAction(label, self)
            self._apply_action_hint(action, f"Show the {label} inspector section.")
            action.triggered.connect(lambda checked=False, section=key: self._show_inspector_tab(section))
            inspector_menu.addAction(action)
            self._inspector_view_actions[label] = action

        tools_menu = view_menu.addMenu("Tools")
        self._tools_menu = tools_menu
        self._tools_view_actions = {}
        self._apply_action_hint(tools_menu.menuAction(), "Choose a bottom tools panel to show.")
        for label in ("Diagnostics", "History", "Debug Output"):
            action = QAction(label, self)
            self._apply_action_hint(action, f"Show the {label} tools panel.")
            action.triggered.connect(lambda checked=False, section=label: self._show_bottom_panel(section))
            tools_menu.addAction(action)
            self._tools_view_actions[label] = action

        self._focus_canvas_action = QAction("Focus Canvas", self)
        self._focus_canvas_action.setCheckable(True)
        self._apply_action_hint(
            self._focus_canvas_action,
            "Focus the canvas by hiding the left workspace rail, inspector, and bottom tools.",
        )
        self._focus_canvas_action.triggered.connect(self._set_focus_canvas_enabled)
        view_menu.addAction(self._focus_canvas_action)
        view_menu.addSeparator()

        self._overlay_group = QActionGroup(self)
        self._overlay_group.setExclusive(True)
        self._overlay_mode_actions = {}  # mode -> QAction

        # Restore saved layout mode from config
        saved_mode = self._config.overlay_mode
        saved_flipped = self._config.overlay_flipped
        self.preview_panel.set_overlay_mode(saved_mode)
        self.preview_panel._flipped = saved_flipped
        self.preview_panel._apply_mode()

        mode_items = [
            ("Vertical", MODE_VERTICAL, "Ctrl+1"),
            ("Horizontal", MODE_HORIZONTAL, "Ctrl+2"),
            ("Overlay Only", MODE_HIDDEN, "Ctrl+3"),
        ]
        for label, mode, shortcut in mode_items:
            action = QAction(label, self)
            action.setCheckable(True)
            action.setShortcut(shortcut)
            overlay_hint = {
                MODE_VERTICAL: "Show preview and overlay stacked vertically (Ctrl+1).",
                MODE_HORIZONTAL: "Show preview and overlay side by side (Ctrl+2).",
                MODE_HIDDEN: "Show only the overlay workspace (Ctrl+3).",
            }[mode]
            self._apply_action_hint(action, overlay_hint)
            if mode == saved_mode:
                action.setChecked(True)
            action.triggered.connect(
                lambda checked, m=mode: self._set_overlay_mode(m)
            )
            self._overlay_group.addAction(action)
            self._overlay_mode_actions[mode] = action
            view_menu.addAction(action)

        self._swap_overlay_action = QAction("Swap Preview/Overlay", self)
        self._swap_overlay_action.setShortcut("Ctrl+4")
        self._apply_action_hint(self._swap_overlay_action, "Swap the preview and overlay positions (Ctrl+4).")
        self._swap_overlay_action.triggered.connect(self._flip_overlay_layout)
        view_menu.addAction(self._swap_overlay_action)

        view_menu.addSeparator()

        self._zoom_in_action = QAction("Zoom In", self)
        self._zoom_in_action.setShortcut("Ctrl+=")
        self._apply_action_hint(self._zoom_in_action, "Zoom in on the preview overlay (Ctrl+=).")
        self._zoom_in_action.triggered.connect(lambda: self.preview_panel.overlay.zoom_in())
        view_menu.addAction(self._zoom_in_action)

        self._zoom_out_action = QAction("Zoom Out", self)
        self._zoom_out_action.setShortcut("Ctrl+-")
        self._apply_action_hint(self._zoom_out_action, "Zoom out on the preview overlay (Ctrl+-).")
        self._zoom_out_action.triggered.connect(lambda: self.preview_panel.overlay.zoom_out())
        view_menu.addAction(self._zoom_out_action)

        self._zoom_reset_action = QAction("Zoom Reset (100%)", self)
        self._zoom_reset_action.setShortcut("Ctrl+0")
        self._apply_action_hint(self._zoom_reset_action, "Reset the preview overlay zoom to 100% (Ctrl+0).")
        self._zoom_reset_action.triggered.connect(lambda: self.preview_panel.overlay.zoom_reset())
        view_menu.addAction(self._zoom_reset_action)
        self._update_preview_appearance_action_metadata()

        view_menu.addSeparator()

        self._show_grid_action = QAction("Show Grid", self)
        self._show_grid_action.setCheckable(True)
        self._show_grid_action.setChecked(self.preview_panel.show_grid())
        self._apply_action_hint(self._show_grid_action, "Toggle the preview grid overlay.")
        self._show_grid_action.toggled.connect(self._set_show_grid)
        view_menu.addAction(self._show_grid_action)

        self._grid_menu = view_menu.addMenu("Grid Size")
        self._apply_action_hint(self._grid_menu.menuAction(), "Choose the grid snap size.")
        self._grid_size_group = QActionGroup(self)
        self._grid_size_group.setExclusive(True)
        self._grid_size_actions = {}
        for size in (0, 4, 8, 12, 16, 24):
            action = QAction("No Snap" if size == 0 else f"{size}px", self)
            action.setCheckable(True)
            self._apply_action_hint(
                action,
                "Disable grid snapping." if size == 0 else f"Snap the overlay grid to {size}px.",
            )
            if size == self.preview_panel.grid_size():
                action.setChecked(True)
            action.triggered.connect(lambda checked, s=size: self._set_grid_size(s))
            self._grid_size_group.addAction(action)
            self._grid_size_actions[size] = action
            self._grid_menu.addAction(action)

        view_menu.addSeparator()

        # 鈹€鈹€ Background Mockup submenu 鈹€鈹€
        self._bg_menu = view_menu.addMenu("Background Mockup")
        self._apply_action_hint(self._bg_menu.menuAction(), "Manage the preview background mockup image.")

        self._load_bg_action = QAction("Load Mockup Image...", self)
        self._apply_action_hint(self._load_bg_action, "Load a mockup image behind the preview.")
        self._load_bg_action.triggered.connect(self._load_background_image)
        self._bg_menu.addAction(self._load_bg_action)

        self._toggle_bg_action = QAction("Show Mockup", self)
        self._toggle_bg_action.setCheckable(True)
        self._toggle_bg_action.setChecked(True)
        self._toggle_bg_action.setShortcut("Ctrl+M")
        self._apply_action_hint(self._toggle_bg_action, "Toggle the background mockup image (Ctrl+M).")
        self._toggle_bg_action.toggled.connect(self._toggle_background_image)
        self._bg_menu.addAction(self._toggle_bg_action)

        self._clear_bg_action = QAction("Clear Mockup Image", self)
        self._apply_action_hint(self._clear_bg_action, "Remove the current background mockup image.")
        self._clear_bg_action.triggered.connect(self._clear_background_image)
        self._bg_menu.addAction(self._clear_bg_action)

        self._bg_menu.addSeparator()

        # Opacity sub-menu with preset values
        self._opacity_menu = self._bg_menu.addMenu("Opacity")
        self._apply_action_hint(self._opacity_menu.menuAction(), "Choose the mockup image opacity.")
        self._opacity_group = QActionGroup(self)
        self._opacity_group.setExclusive(True)
        self._opacity_actions = {}
        for pct in [10, 20, 30, 50, 70, 100]:
            act = QAction(f"{pct}%", self)
            act.setCheckable(True)
            self._apply_action_hint(act, f"Set the mockup image opacity to {pct}%.")
            if pct == 30:
                act.setChecked(True)
            act.triggered.connect(
                lambda checked, p=pct: self._set_background_opacity(p / 100.0)
            )
            self._opacity_group.addAction(act)
            self._opacity_actions[pct] = act
            self._opacity_menu.addAction(act)
        self._update_preview_grid_and_mockup_action_metadata()
        self._update_view_and_theme_action_metadata()

    # 鈹€鈹€ Toolbar 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    def _init_toolbar(self):
        tb = QToolBar("Main Toolbar", self)
        tb.setObjectName("main_toolbar")
        tb.setMovable(False)
        tb.setToolButtonStyle(Qt.ToolButtonTextOnly)
        tb.setFixedHeight(WORKSPACE_TOOLBAR_HEIGHT)
        self._toolbar_command_row_layout.addWidget(tb, 1)

        toolbar_rail_sep = QFrame()
        toolbar_rail_sep.setObjectName("toolbar_host_separator")
        toolbar_rail_sep.setFrameShape(QFrame.VLine)
        toolbar_rail_sep.setFrameShadow(QFrame.Plain)
        toolbar_rail_sep.setFixedHeight(20)
        self._toolbar_command_row_layout.addWidget(toolbar_rail_sep, 0)

        self._insert_widget_button = QPushButton("Add")
        self._insert_widget_button.setObjectName("workspace_insert_button")
        self._insert_widget_button.setFixedSize(52, WORKSPACE_CONTROL_HEIGHT)
        self._insert_widget_button.clicked.connect(lambda: self._show_widget_browser_for_parent(self._default_insert_parent()))
        tb.addWidget(self._insert_widget_button)
        self._update_insert_widget_button_metadata()

        tb.addSeparator()
        tb.addAction(self._save_action)
        self._set_toolbar_button_height(tb, self._save_action)

        tb.addSeparator()

        tb.addAction(self._undo_action)
        self._set_toolbar_button_height(tb, self._undo_action)
        tb.addAction(self._redo_action)
        self._set_toolbar_button_height(tb, self._redo_action)
        more_menu = QMenu(self)
        more_menu.addAction(self._copy_action)
        more_menu.addAction(self._paste_action)
        self._toolbar_more_button = QToolButton()
        self._toolbar_more_button.setObjectName("workspace_toolbar_more")
        self._toolbar_more_button.setToolTip("More: copy, paste")
        self._toolbar_more_button.setAccessibleName("More toolbar actions")
        self._toolbar_more_button.setPopupMode(QToolButton.InstantPopup)
        self._toolbar_more_button.setMenu(more_menu)
        self._toolbar_more_button.setText("More")
        self._toolbar_more_button.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self._toolbar_more_button.setFixedHeight(WORKSPACE_CONTROL_HEIGHT)
        tb.addWidget(self._toolbar_more_button)

        tb.addSeparator()

        tb.addAction(self._compile_action)
        self._set_toolbar_button_height(tb, self._compile_action)
        tb.addAction(self._stop_action)
        self._set_toolbar_button_height(tb, self._stop_action)

        mode_host = QWidget()
        mode_host.setObjectName("workspace_mode_switch")
        mode_layout = QHBoxLayout(mode_host)
        mode_layout.setContentsMargins(0, 0, 0, 0)
        mode_layout.setSpacing(1)
        self._mode_buttons = {}
        for label, mode in (
            ("Design", MODE_DESIGN),
            ("Split", MODE_SPLIT),
            ("Code", MODE_CODE),
        ):
            button = QPushButton(label)
            button.setObjectName("workspace_mode_button")
            button.setCheckable(True)
            button.setFixedSize(52, WORKSPACE_CONTROL_HEIGHT)
            button.clicked.connect(lambda checked=False, m=mode: self.editor_tabs.set_mode(m))
            self._mode_buttons[mode] = button
            mode_layout.addWidget(button)
        self._toolbar_command_row_layout.addWidget(mode_host, 0)
        self._update_editor_mode_button_metadata(self.editor_tabs.mode)

        self._toolbar = tb
        self._update_compile_availability()
        self._update_edit_actions()
        self._update_toolbar_action_metadata()
        self._update_workspace_chips()

    def _set_focus_canvas_enabled(self, enabled):
        enabled = bool(enabled)
        if enabled == self._focus_canvas_enabled:
            if hasattr(self, "_focus_canvas_action"):
                with QSignalBlocker(self._focus_canvas_action):
                    self._focus_canvas_action.setChecked(enabled)
            return

        if enabled:
            if hasattr(self, "_top_splitter"):
                self._focus_canvas_saved_top_sizes = list(self._top_splitter.sizes())
            self._focus_canvas_saved_bottom_visible = bool(getattr(self, "_bottom_panel_visible", False))
            if hasattr(self, "_left_shell"):
                self._left_shell.hide()
            if hasattr(self, "_inspector_tabs"):
                self._inspector_tabs.hide()
            if getattr(self, "_bottom_panel_visible", False):
                self._set_bottom_panel_visible(False)
        else:
            if hasattr(self, "_left_shell"):
                self._left_shell.show()
            if hasattr(self, "_inspector_tabs"):
                self._inspector_tabs.show()
            if self._focus_canvas_saved_top_sizes and hasattr(self, "_top_splitter"):
                try:
                    self._top_splitter.setSizes(self._focus_canvas_saved_top_sizes)
                except Exception:
                    pass
            if self._focus_canvas_saved_bottom_visible:
                self._set_bottom_panel_visible(True)

        self._focus_canvas_enabled = enabled
        if hasattr(self, "_focus_canvas_action"):
            with QSignalBlocker(self._focus_canvas_action):
                self._focus_canvas_action.setChecked(enabled)
        self._update_view_and_theme_action_metadata()
        self._update_workspace_layout_metadata()
        self._update_view_panel_navigation_action_metadata()

    # 鈹€鈹€ Theme 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    def _set_theme(self, theme):
        """Set the application theme and save to config."""
        app = QApplication.instance()
        if app is not None:
            app.setProperty("designer_font_size_pt", int(getattr(self._config, "font_size_px", 0) or 0))
        apply_theme(
            app,
            theme,
            density=str(getattr(self._config, "ui_density", "standard") or "standard"),
        )
        self._refresh_theme_dependent_widgets()
        self._config.theme = theme
        self._config.save()
        self._update_view_and_theme_action_metadata()
        if hasattr(self, "widget_browser"):
            self.widget_browser.refresh()

    def _set_ui_density(self, density):
        """Set UI density profile and save to config."""
        normalized = str(density or "standard").strip().lower()
        if normalized in {"roomy+", "plus", "spacious"}:
            normalized = "roomy_plus"
        elif normalized not in {"standard", "roomy", "roomy_plus"}:
            normalized = "standard"
        app = QApplication.instance()
        if app is not None:
            app.setProperty("designer_font_size_pt", int(getattr(self._config, "font_size_px", 0) or 0))
        apply_theme(app, self._config.theme, density=normalized)
        self._refresh_theme_dependent_widgets()
        self._config.ui_density = normalized
        self._config.save()
        self._update_view_and_theme_action_metadata()
        if hasattr(self, "widget_browser"):
            self.widget_browser.refresh()
        if normalized == "roomy_plus":
            label = "Roomy+"
        elif normalized == "roomy":
            label = "Roomy"
        else:
            label = "Standard"
        self.statusBar().showMessage(f"UI density set to {label} (saved)", 3000)

    def _set_font_sizes(self):
        """Set the theme-driven application font size."""
        current_size = self._config.font_size_px
        if not current_size or current_size <= 0:
            current_size = 9

        size, ok = QInputDialog.getInt(
            self, "Font Size", "Font size (pt):",
            value=current_size, min=6, max=48
        )
        if not ok:
            return

        app = QApplication.instance()
        if app is not None:
            app.setProperty("designer_font_size_pt", int(size))
            apply_theme(
                app,
                self._config.theme,
                density=str(getattr(self._config, "ui_density", "standard") or "standard"),
            )
        self._refresh_theme_dependent_widgets()

        # Debug panel uses its own font
        self.debug_panel.set_output_font_size_pt(size)
        if hasattr(self, "editor_tabs"):
            self.editor_tabs.set_editor_font_size_pt(size)

        # Persist to config
        self._config.font_size_px = size
        self._config.save()
        self._update_view_and_theme_action_metadata()
        self.statusBar().showMessage(f"Font size set to {size}pt (saved)")

    # 鈹€鈹€ Project operations 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    def _refresh_theme_dependent_widgets(self):
        """Refresh inline theme-sensitive widgets after theme or font changes."""
        try:
            from .widgets.font_selector import EguiFontSelector
        except Exception:
            EguiFontSelector = None
        if EguiFontSelector is not None:
            for selector in self.findChildren(EguiFontSelector):
                try:
                    selector.refresh_theme_metrics()
                except Exception:
                    continue
        for attr_name in ("project_dock", "widget_tree"):
            panel = getattr(self, attr_name, None)
            refresh = getattr(panel, "refresh_tree_typography", None)
            if callable(refresh):
                try:
                    refresh()
                except Exception:
                    continue

    def _update_recent_menu(self):
        """Update the Recent Projects submenu."""
        recent = self._config.recent_projects
        snapshot = []
        for item in recent[:10]:
            project_path = item.get("project_path", "")
            sdk_root = self._resolve_ui_sdk_root(item.get("sdk_root", ""))
            display_name = item.get("display_name") or os.path.splitext(os.path.basename(project_path))[0]
            project_exists = bool(project_path) and os.path.exists(project_path)
            action_label = display_name if project_exists else f"[Missing] {display_name}"
            sdk_label = sdk_root or "not recorded"
            tooltip = f"Project: {project_path}\nSDK root: {sdk_label}."
            if not project_exists:
                tooltip = (
                    f"Project: {project_path}\n"
                    f"SDK root: {sdk_label}.\n"
                    "Project path is missing. Selecting it will offer to remove the stale entry."
                )
            snapshot.append((action_label, tooltip, project_path, sdk_root, bool(project_exists)))
        snapshot = tuple(snapshot)
        if getattr(self._recent_menu, "_recent_menu_snapshot", None) == snapshot:
            self._update_file_open_action_metadata()
            self._update_file_menu_metadata()
            return
        self._recent_menu.clear()
        self._recent_menu._recent_menu_snapshot = snapshot
        if not recent:
            hint = "Open a recently used project. No recent projects are available."
            self._apply_action_hint(self._recent_menu.menuAction(), hint)
            action = QAction("(No recent projects)", self)
            action.setEnabled(False)
            self._apply_action_hint(action, "No recent projects are available.")
            self._recent_menu.addAction(action)
            self._update_file_open_action_metadata()
            self._update_file_menu_metadata()
            return

        recent_count = min(len(recent), 10)
        noun = "project" if recent_count == 1 else "projects"
        hint = f"Open a recently used project. {recent_count} recent {noun} available."
        self._apply_action_hint(self._recent_menu.menuAction(), hint)

        for action_label, tooltip, project_path, sdk_root, _project_exists in snapshot:
            action = QAction(action_label, self)
            self._apply_action_hint(action, tooltip)
            action.triggered.connect(
                lambda checked, p=project_path, r=sdk_root: self._open_recent_project(p, r)
            )
            self._recent_menu.addAction(action)
        self._update_file_open_action_metadata()
        self._update_file_menu_metadata()

    def _update_sdk_status_label(self):
        if not hasattr(self, "_sdk_status_label"):
            return
        sdk_root = self.project_root or self._active_sdk_root()
        binding_label = format_sdk_binding_label(sdk_root, _DESIGNER_REPO_ROOT)
        tooltip = sdk_root or "No SDK root configured"
        accessible_name = f"SDK binding: {binding_label}."
        snapshot = (binding_label, str(tooltip or ""), accessible_name)
        if getattr(self._sdk_status_label, "_sdk_status_label_snapshot", None) != snapshot:
            self._sdk_status_label.setText(binding_label)
            self._set_metadata_summary(self._sdk_status_label, tooltip, accessible_name)
            self._sdk_status_label._sdk_status_label_snapshot = snapshot
        self._update_new_project_action_metadata(binding_label)
        self._update_file_open_action_metadata(binding_label)
        self._update_sdk_root_action_metadata(binding_label)
        self._update_workspace_chips()

    def _open_app_dialog(self):
        """Show dialog to select and open a bundled or SDK example."""
        dialog = AppSelectorDialog(self, sdk_root=self._active_sdk_root())
        if dialog.exec_() != QDialog.Accepted:
            return

        entry = dialog.selected_entry
        sdk_root = normalize_path(dialog.sdk_root)
        if not entry:
            return

        entry_source = str(entry.get("source") or "sdk")
        if entry_source == "sdk":
            self.project_root = sdk_root
            self._config.sdk_root = sdk_root
            self._config.save()

        if entry.get("has_project"):
            try:
                preferred_sdk_root = sdk_root if entry_source == "sdk" else ""
                self._open_project_path(entry.get("project_path", ""), preferred_sdk_root=preferred_sdk_root)
            except Exception as exc:
                QMessageBox.critical(self, "Error", f"Failed to open example:\n{exc}")
            return

        try:
            self._initialize_unmanaged_sdk_example(entry, sdk_root)
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to initialize Designer project for SDK example:\n{exc}")

    def _set_sdk_root(self):
        path = QFileDialog.getExistingDirectory(self, "Select EmbeddedGUI SDK Root", self._active_sdk_root() or "")
        if not path:
            return

        path = resolve_sdk_root_candidate(path)
        if not path:
            QMessageBox.warning(
                self,
                "Invalid SDK Root",
                "The selected directory does not contain a valid EmbeddedGUI SDK root.",
            )
            return

        self._apply_sdk_root(path, status_message=self._format_sdk_status_message("SDK root set to", path))

    def _open_recent_project(self, project_path, sdk_root=""):
        if not project_path:
            return
        try:
            self._open_project_path(project_path, preferred_sdk_root=sdk_root)
        except FileNotFoundError:
            reply = QMessageBox.question(
                self,
                "Recent Project Missing",
                f"The recent project path no longer exists:\n{project_path}\n\nRemove it from the recent project list?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if reply == QMessageBox.Yes:
                if self._config.remove_recent_project(project_path):
                    self._update_recent_menu()
                    self._welcome_page.refresh()
                self.statusBar().showMessage("Removed missing project from recent projects")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to open project:\n{exc}")

    def _initialize_unmanaged_sdk_example(self, entry, sdk_root):
        app_name = entry.get("app_name", "")
        app_dir = normalize_path(entry.get("app_dir", ""))
        example_paths = sdk_example_paths(sdk_root, app_name)
        project_path = example_paths["project_path"]
        eguiproject_dir = example_paths["config_dir"]

        if os.path.exists(eguiproject_dir) and not os.path.isfile(project_path):
            QMessageBox.warning(
                self,
                "Designer Project Conflict",
                "This SDK example already contains a .eguiproject directory but has no .egui file. "
                "Please resolve the directory conflict manually before initializing Designer here.",
            )
            return

        reply = QMessageBox.question(
            self,
            "Initialize Designer Project",
            "This will create a fresh Designer project scaffold in the selected SDK example directory.\n\n"
            "Existing app pages, resources, and business code remain on disk, but they are not migrated into "
            "Designer-managed pages or resource models.\n\n"
            f"App: {app_name}\n"
            f"Path:\n{app_dir}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        _project, project_path = save_empty_sdk_example_project_with_designer_scaffold(
            sdk_root=sdk_root,
            app_name=app_name,
            remove_legacy_designer_files=True,
        )
        self._open_project_path(project_path, preferred_sdk_root=sdk_root)

    def _update_window_title(self):
        """Update window title with current app name and dirty indicator."""
        dirty_pages = set(self._undo_manager.dirty_pages())
        self.project_dock.set_dirty_pages(dirty_pages)
        self.page_navigator.set_dirty_pages(dirty_pages)
        for i in range(self.page_tab_bar.count()):
            page_name = self._page_tab_name(i)
            self.page_tab_bar.setTabText(i, self._page_tab_label(page_name, dirty_pages))
        self._update_page_tab_bar_metadata()

        title = f"EmbeddedGUI Designer - {self.app_name}"
        if self._project_dir:
            title += f" [{self._project_dir}]"
        if dirty_pages or self._project_dirty:
            title += " *"
        self.setWindowTitle(title)
        self._update_history_panel()
        self._update_diagnostics_panel()
        self._update_workspace_chips()
        self._update_new_project_action_metadata()
        self._update_file_open_action_metadata()
        self._update_file_project_action_metadata()
        self._update_file_menu_metadata()
        self._update_toolbar_action_metadata()

    def _update_history_panel(self):
        if self._current_page is None:
            self.history_panel.clear()
            return

        stack = self._undo_manager.get_stack(self._current_page.name)
        dirty_source = stack.current_label() if stack.is_dirty() else ""
        self.history_panel.set_history(
            self._current_page.name,
            stack.history_entries(),
            dirty=stack.is_dirty(),
            dirty_source=dirty_source,
            can_undo=stack.can_undo(),
            can_redo=stack.can_redo(),
        )

    def _update_diagnostics_panel(self):
        if not hasattr(self, "diagnostics_panel"):
            return
        if self._current_page is None:
            self.diagnostics_panel.clear()
            self._update_workspace_chips()
            return

        resource_dir = self._get_eguiproject_resource_dir()
        catalog = self.project.resource_catalog if self.project is not None else None
        string_catalog = self.project.string_catalog if self.project is not None else None
        entries = analyze_page(
            self._current_page,
            resource_catalog=catalog,
            string_catalog=string_catalog,
            source_resource_dir=resource_dir,
        )
        entries.extend(analyze_app_local_widget_issues())
        entries.extend(analyze_project_callback_conflicts(self.project))
        entries.extend(analyze_selection(self._selection_state.widgets))
        self.diagnostics_panel.set_entries(sort_diagnostic_entries(entries))
        self._update_workspace_chips()

    def _copy_diagnostics_summary(self):
        if not hasattr(self, "diagnostics_panel") or not self.diagnostics_panel.has_entries():
            self.statusBar().showMessage("No diagnostics to copy.", 3000)
            return

        QApplication.clipboard().setText(self.diagnostics_panel.summary_text())
        self.statusBar().showMessage("Copied diagnostics summary.", 3000)

    def _copy_diagnostics_json(self):
        if not hasattr(self, "diagnostics_panel") or not self.diagnostics_panel.has_entries():
            self.statusBar().showMessage("No diagnostics JSON to copy.", 3000)
            return

        QApplication.clipboard().setText(self._diagnostics_json_text())
        self.statusBar().showMessage("Copied diagnostics JSON.", 3000)

    def _default_diagnostics_summary_export_path(self):
        default_dir = self._default_export_code_dir()
        if default_dir:
            return os.path.join(default_dir, "diagnostics-summary.txt")
        return "diagnostics-summary.txt"

    def _default_diagnostics_json_export_path(self):
        default_dir = self._default_export_code_dir()
        if default_dir:
            return os.path.join(default_dir, "diagnostics.json")
        return "diagnostics.json"

    def _diagnostics_json_text(self):
        entries = self.diagnostics_panel.entries() if hasattr(self, "diagnostics_panel") else []
        view_state = self.diagnostics_panel.view_state() if hasattr(self, "diagnostics_panel") else {}
        selected_entry = self.diagnostics_panel.current_selected_entry() if hasattr(self, "diagnostics_panel") else None
        selected_target = diagnostic_target_payload(selected_entry) if selected_entry is not None else {
            "target_kind": "",
            "target_page_name": "",
            "target_widget_name": "",
        }
        errors = sum(1 for entry in entries if entry.severity == "error")
        warnings = sum(1 for entry in entries if entry.severity == "warning")
        infos = sum(1 for entry in entries if entry.severity == "info")
        payload = {
            "project": {
                "app_name": self.project.app_name if self.project is not None else "",
                "project_dir": self._project_dir or "",
                "current_page": self._current_page.name if self._current_page is not None else "",
            },
            "summary": {
                "errors": errors,
                "warnings": warnings,
                "info": infos,
                "total": len(entries),
            },
            "view": {
                "severity_filter": str(view_state.get("severity_filter") or ""),
                "visible_total": len(entries),
                "selected_code": str(getattr(selected_entry, "code", "") or ""),
                "selected_target_kind": str(selected_target.get("target_kind") or ""),
                "selected_target_page_name": str(selected_target.get("target_page_name") or ""),
                "selected_target_widget_name": str(selected_target.get("target_widget_name") or ""),
            },
            "entries": [
                diagnostic_entry_payload(entry)
                for entry in entries
            ],
        }
        return json.dumps(payload, indent=2, ensure_ascii=False)

    def _export_diagnostics_summary(self):
        if not hasattr(self, "diagnostics_panel") or not self.diagnostics_panel.has_entries():
            self.statusBar().showMessage("No diagnostics to export.", 3000)
            return

        selected_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Diagnostics Summary",
            self._default_diagnostics_summary_export_path(),
            "Text Files (*.txt);;All Files (*)",
        )
        if not selected_path:
            return

        try:
            if "Text" in str(selected_filter):
                selected_path = selected_path if os.path.splitext(selected_path)[1] else selected_path + ".txt"
            resolved_path = os.path.abspath(os.path.normpath(selected_path))
            parent_dir = os.path.dirname(resolved_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
            with open(resolved_path, "w", encoding="utf-8") as f:
                f.write(self.diagnostics_panel.summary_text().rstrip() + "\n")
        except OSError as exc:
            QMessageBox.warning(self, "Export Diagnostics Summary Failed", str(exc))
            return

        self.statusBar().showMessage(f"Exported diagnostics summary to {resolved_path}", 3000)

    def _export_diagnostics_json(self):
        if not hasattr(self, "diagnostics_panel") or not self.diagnostics_panel.has_entries():
            self.statusBar().showMessage("No diagnostics JSON to export.", 3000)
            return

        selected_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Diagnostics JSON",
            self._default_diagnostics_json_export_path(),
            "JSON Files (*.json);;All Files (*)",
        )
        if not selected_path:
            return

        try:
            if "JSON" in str(selected_filter):
                selected_path = selected_path if os.path.splitext(selected_path)[1] else selected_path + ".json"
            resolved_path = os.path.abspath(os.path.normpath(selected_path))
            parent_dir = os.path.dirname(resolved_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
            with open(resolved_path, "w", encoding="utf-8") as f:
                f.write(self._diagnostics_json_text().rstrip() + "\n")
        except OSError as exc:
            QMessageBox.warning(self, "Export Diagnostics JSON Failed", str(exc))
            return

        self.statusBar().showMessage(f"Exported diagnostics JSON to {resolved_path}", 3000)

    def _update_resource_usage_panel(self):
        if not hasattr(self, "res_panel"):
            return
        if self.project is None:
            self.res_panel.set_resource_usage_index({})
            self.res_panel.set_usage_page_context("")
            return
        self.res_panel.set_resource_usage_index(collect_project_resource_usages(self.project))
        current_page_name = self._current_page.name if self._current_page is not None else ""
        self.res_panel.set_usage_page_context(current_page_name)

    def _collect_codegen_blockers(self):
        if self.project is None:
            return []

        resource_dir = self._get_eguiproject_resource_dir()
        catalog = self.project.resource_catalog if self.project is not None else None
        string_catalog = self.project.string_catalog if self.project is not None else None
        entries = []
        for page in self.project.pages:
            entries.extend(
                entry
                for entry in analyze_page(
                    page,
                    resource_catalog=catalog,
                    string_catalog=string_catalog,
                    source_resource_dir=resource_dir,
                )
                if entry.severity == "error"
            )
        entries.extend(
            entry
            for entry in analyze_project_callback_conflicts(self.project)
            if entry.severity == "error"
        )
        return sort_diagnostic_entries(entries)

    def _format_codegen_blocker_summary(self, entries, limit=5):
        entries = list(entries or [])
        lines = []
        for entry in entries[:limit]:
            scope = entry.page_name or "project"
            if entry.widget_name:
                scope = f"{scope}/{entry.widget_name}"
            lines.append(f"- {scope}: {entry.message}")
        remaining = max(0, len(entries) - limit)
        if remaining:
            lines.append(f"- ... and {remaining} more issue(s)")
        return "\n".join(lines)

    def _ensure_codegen_preflight(self, action_name, show_dialog=False, switch_to_python_preview=False):
        blockers = self._collect_codegen_blockers()
        if not blockers:
            return True

        summary = self._format_codegen_blocker_summary(blockers)
        self.debug_panel.log_error(f"{action_name} blocked by diagnostics ({len(blockers)} error(s))")
        if summary:
            self.debug_panel.log_error(summary)
        self._show_bottom_panel("Diagnostics")

        if switch_to_python_preview:
            self._switch_to_python_preview("Compile blocked by diagnostics")

        self.statusBar().showMessage(f"{action_name} blocked: {len(blockers)} error(s) in diagnostics.", 5000)

        if show_dialog:
            QMessageBox.warning(
                self,
                f"{action_name} Blocked",
                f"{action_name} blocked by diagnostics ({len(blockers)} error(s)).\n\n{summary}",
            )
        return False

    def _find_widget_in_page(self, page, widget_name):
        if page is None or not widget_name:
            return None
        for widget in page.get_all_widgets():
            if widget.name == widget_name:
                return widget
        return None

    def _resolved_cached_sdk_root(self):
        cached_sdk_root = normalize_path(default_sdk_install_dir())
        if is_valid_sdk_root(cached_sdk_root):
            return cached_sdk_root

        # Reuse config-side resolution so configured and cached SDK roots still work.
        config_cached_sdk_root = self._config._resolve_sdk_root("")
        if is_valid_sdk_root(config_cached_sdk_root):
            return config_cached_sdk_root
        return ""

    def _resolve_ui_sdk_root(self, *candidates):
        normalized_candidates = []
        for candidate in candidates:
            normalized = normalize_path(candidate)
            if normalized and normalized not in normalized_candidates:
                normalized_candidates.append(normalized)

        for candidate in normalized_candidates:
            if is_valid_sdk_root(candidate):
                return candidate
            inferred = infer_sdk_root_from_project_dir(candidate)
            if inferred:
                return inferred

        cached_sdk_root = self._resolved_cached_sdk_root()
        if cached_sdk_root:
            return cached_sdk_root

        return resolve_available_sdk_root(
            *normalized_candidates,
            cached_sdk_root=default_sdk_install_dir(),
        )

    def _active_sdk_root(self):
        return self._resolve_ui_sdk_root(
            self.project_root,
            self._config.sdk_root,
        )

    def _nearest_existing_directory(self, path=""):
        candidate = normalize_path(path)
        if not candidate:
            return ""
        while candidate and not os.path.exists(candidate):
            parent = os.path.dirname(candidate)
            if not parent or parent == candidate:
                return ""
            candidate = parent
        if os.path.isfile(candidate):
            candidate = os.path.dirname(candidate)
        return candidate if os.path.isdir(candidate) else ""

    def _default_new_project_parent_dir(self, sdk_root=""):
        if self._project_dir:
            existing_dir = self._nearest_existing_directory(os.path.dirname(self._project_dir))
            if existing_dir:
                return existing_dir

        last_project_path = normalize_path(self._config.last_project_path)
        if last_project_path:
            existing_dir = self._nearest_existing_directory(os.path.dirname(last_project_path))
            if existing_dir:
                return existing_dir

        runtime_root = designer_runtime_root(_DESIGNER_REPO_ROOT)
        if runtime_root:
            return runtime_root

        return normalize_path(os.getcwd())

    def _default_open_project_dir(self):
        if self._project_dir:
            existing_dir = self._nearest_existing_directory(self._project_dir)
            if existing_dir:
                return existing_dir

        last_project_path = normalize_path(self._config.last_project_path)
        if last_project_path:
            existing_dir = self._nearest_existing_directory(last_project_path)
            if existing_dir:
                return existing_dir

        runtime_root = designer_runtime_root(_DESIGNER_REPO_ROOT)
        if runtime_root:
            return runtime_root

        return normalize_path(os.getcwd())

    def _default_save_project_as_dir(self):
        if self._project_dir:
            existing_dir = self._nearest_existing_directory(os.path.dirname(self._project_dir))
            if existing_dir:
                return existing_dir
        return self._default_new_project_parent_dir()

    def _has_directory_conflict(self, path, *, allow_current=False):
        path = normalize_path(path)
        if not path:
            return False
        if allow_current and path == normalize_path(self._project_dir):
            return False
        return os.path.exists(path)

    def _show_directory_conflict(self, path, message):
        QMessageBox.warning(
            self,
            "Directory Conflict",
            f"{message}:\n{normalize_path(path)}",
        )

    def _default_export_code_dir(self):
        if self._project_dir:
            existing_dir = self._nearest_existing_directory(self._project_dir)
            if existing_dir:
                return existing_dir
        return self._default_open_project_dir()

    def _default_mockup_open_dir(self):
        if self._current_page and self._current_page.mockup_image_path and self._project_dir:
            mockup_path = project_config_path(self._project_dir, self._current_page.mockup_image_path)
            mockup_dir = normalize_path(os.path.dirname(mockup_path))
            if os.path.isdir(mockup_dir):
                return mockup_dir

        if self._project_dir:
            mockup_dir = self._get_eguiproject_mockup_dir()
            if os.path.isdir(mockup_dir):
                return normalize_path(mockup_dir)
            existing_dir = self._nearest_existing_directory(self._project_dir)
            if existing_dir:
                return existing_dir

        return self._default_open_project_dir()

    def _new_project(self):
        """Create a new project in a dedicated app directory."""
        default_sdk_root = self._active_sdk_root()
        default_parent_dir = self._default_new_project_parent_dir(default_sdk_root)
        dialog = NewProjectDialog(self, sdk_root=default_sdk_root, default_parent_dir=default_parent_dir)
        if dialog.exec_() != QDialog.Accepted:
            return

        sdk_root = normalize_path(dialog.sdk_root)
        project_dir = normalize_path(os.path.join(dialog.parent_dir, dialog.app_name))
        if self._has_directory_conflict(project_dir):
            self._show_directory_conflict(project_dir, "The target directory already exists")
            return

        project = save_empty_project_with_designer_scaffold(
            dialog.app_name,
            project_dir,
            dialog.screen_width,
            dialog.screen_height,
            sdk_root=sdk_root,
            remove_legacy_designer_files=True,
        )
        self._clear_auto_compile_retry_block()
        self._open_loaded_project(project, project_dir, preferred_sdk_root=sdk_root)
        self.statusBar().showMessage(
            self._status_message_with_editing_only_mode(
                f"Created project: {dialog.app_name}",
                self._effective_preview_unavailable_reason(),
            )
        )

    def _open_project_path(self, path, preferred_sdk_root="", silent=False):
        path = normalize_path(path)
        if not path:
            raise FileNotFoundError("Project path is empty")
        if not os.path.exists(path):
            raise FileNotFoundError(path)

        project = load_saved_project_model(path)
        project_dir = path if os.path.isdir(path) else os.path.dirname(path)
        self._clear_auto_compile_retry_block()
        self._open_loaded_project(project, project_dir, preferred_sdk_root=preferred_sdk_root, silent=silent)

    def _open_project(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Project", self._default_open_project_dir(),
            "EmbeddedGUI Projects (*.egui);;All Files (*.*)"
        )
        if not path:
            return
        try:
            self._open_project_path(path)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open project:\n{e}")

    def _persist_designer_state_only(self, project_dir):
        save_project_model(
            self.project,
            project_dir,
            sdk_root=self.project_root,
            before_save=self._load_project_app_local_widgets,
        )

    def _save_project_files(self, project_dir, *, reset_scaffold=False):
        materialized = save_project_and_materialize_codegen(
            self.project,
            project_dir,
            sdk_root=self.project_root,
            before_save=self._load_project_app_local_widgets,
            overwrite=reset_scaffold,
            remove_legacy_designer_files=True,
            backup=True,
            backup_existing=True,
            before_materialize=self._apply_pending_page_rename_outputs,
        )
        files = materialized.files
        self._clear_project_dirty()
        return files

    def _save_project(self):
        if self.project is None:
            self.statusBar().showMessage("No project to save")
            return False

        self._flush_pending_xml()

        if not self._project_dir:
            return self._save_project_as()

        try:
            files = self._save_project_files(self._project_dir)
        except Exception as exc:
            self._update_diagnostics_panel()
            self.debug_panel.log_error(f"Save failed: {exc}")
            self._show_bottom_panel("Diagnostics")
            QMessageBox.warning(self, "Save Failed", f"Failed to save generated code:\n{exc}")
            self.statusBar().showMessage(f"Save failed: {exc}", 5000)
            return False
        self._bump_async_generation()
        self._shutdown_async_activity()
        self._clear_rebuild_retry_block()
        self._recreate_compiler()
        preview_unavailable_reason = self._sync_preview_after_compiler_recreation(
            clear_when_available=True,
            preload_preview_error=True,
            probe_environmental_recovery=True,
        )
        preview_unavailable_reason = preview_unavailable_reason or self._effective_preview_unavailable_reason()
        self._undo_manager.mark_all_saved()
        self._persist_current_project_to_config()
        self._refresh_project_watch_snapshot()
        self._update_window_title()
        self._update_compile_availability()
        self.statusBar().showMessage(
            self._status_message_with_editing_only_mode(
                f"Saved: {self._project_dir} ({len(files)} code file(s) updated)",
                preview_unavailable_reason,
            )
        )
        return True

    def _save_project_as(self):
        if self.project is None:
            self.statusBar().showMessage("No project to save")
            return False

        path = QFileDialog.getExistingDirectory(self, "Save Project To Directory", self._default_save_project_as_dir())
        if not path:
            return False

        path = normalize_path(path)
        if self._has_directory_conflict(path, allow_current=True):
            self._show_directory_conflict(path, "The selected directory already exists")
            return False

        old_project_dir = self._project_dir
        copy_project_sidecar_files(old_project_dir, path)
        try:
            files = self._save_project_files(path)
        except Exception as exc:
            self._update_diagnostics_panel()
            self.debug_panel.log_error(f"Save As failed: {exc}")
            self._show_bottom_panel("Diagnostics")
            QMessageBox.warning(self, "Save As Failed", f"Failed to save generated code:\n{exc}")
            self.statusBar().showMessage(f"Save As failed: {exc}", 5000)
            return False
        self._project_dir = path
        self._bump_async_generation()
        self._shutdown_async_activity()
        self._clear_rebuild_retry_block()
        self._recreate_compiler()
        preview_unavailable_reason = self._sync_preview_after_compiler_recreation(
            clear_when_available=True,
            preload_preview_error=True,
            probe_environmental_recovery=True,
        )
        preview_unavailable_reason = preview_unavailable_reason or self._effective_preview_unavailable_reason()
        self._undo_manager.mark_all_saved()
        self._persist_current_project_to_config()
        self._refresh_project_watch_snapshot()
        self._update_window_title()
        self._update_compile_availability()
        self.statusBar().showMessage(
            self._status_message_with_editing_only_mode(
                f"Saved: {path} ({len(files)} code file(s) updated)",
                preview_unavailable_reason,
            )
        )
        return True

    def _close_project(self):
        """Close current project and return to welcome page."""
        if self.project is None:
            self._show_welcome_page()
            return

        if self._has_unsaved_changes():
            reply = QMessageBox.question(
                self, "Close Project",
                self._unsaved_changes_prompt_text("close"),
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save
            )

            if reply == QMessageBox.Cancel:
                return
            if reply == QMessageBox.Save:
                if not self._save_project():
                    return

        self._bump_async_generation()
        self._shutdown_async_activity()
        self._cleanup_compiler(stop_exe=True)

        self._project_watch_snapshot = {}
        self._clear_external_reload_pending()
        self.project = None
        self._project_dir = None
        WidgetRegistry.instance().clear_app_local_widgets()
        self._undo_manager = UndoManager()
        self._clear_editor_state()
        self._show_welcome_page()
        self._update_compile_availability()
        self.statusBar().showMessage("Project closed")

    def _export_code(self):
        """Export all generated C files to a directory, preserving user code."""
        if not self.project:
            return
        path = QFileDialog.getExistingDirectory(
            self, "Export C Code To Directory", self._default_export_code_dir()
        )
        if not path:
            return
        self._flush_pending_xml()
        self._update_diagnostics_panel()
        if not self._ensure_codegen_preflight("Export", show_dialog=True, switch_to_python_preview=False):
            return
        try:
            materialized = materialize_project_codegen_outputs(
                self.project,
                path,
                backup=True,
                backup_existing=True,
                before_materialize=self._apply_pending_page_rename_outputs,
            )
            files = materialized.files
        except Exception as exc:
            self._update_diagnostics_panel()
            self.debug_panel.log_error(f"Export failed: {exc}")
            self._show_bottom_panel("Diagnostics")
            QMessageBox.warning(self, "Export Failed", f"Failed to export generated code:\n{exc}")
            self.statusBar().showMessage(f"Export failed: {exc}", 5000)
            return
        self.statusBar().showMessage(
            f"Exported {len(files)} files to {path} (user code preserved)"
        )

    # 鈹€鈹€ Background Mockup Image 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    def _load_background_image(self):
        """Load a mockup image for the current page."""
        if not self._current_page:
            QMessageBox.warning(self, "Warning", "No page is currently open.")
            return
        if not self._project_dir:
            QMessageBox.warning(self, "Warning", "Please save the project first.")
            return

        from PyQt5.QtGui import QPixmap
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Mockup Image", self._default_mockup_open_dir(),
            "Images (*.png *.jpg *.jpeg *.bmp);;All Files (*.*)"
        )
        if not path:
            return
        pixmap = QPixmap(path)
        if pixmap.isNull():
            QMessageBox.warning(self, "Error", f"Failed to load image:\n{path}")
            return

        # Check if image size matches screen size
        sw = self.project.screen_width if self.project else 240
        sh = self.project.screen_height if self.project else 320
        if pixmap.width() != sw or pixmap.height() != sh:
            QMessageBox.information(
                self, "Image Size Mismatch",
                f"The mockup image size ({pixmap.width()}x{pixmap.height()}) "
                f"does not match the screen size ({sw}x{sh}).\n\n"
                f"The image will be scaled to {sw}x{sh} to fit the canvas."
            )
            pixmap = pixmap.scaled(sw, sh, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)

        # Copy image to .eguiproject/mockup/
        mockup_dir = self._get_eguiproject_mockup_dir()
        os.makedirs(mockup_dir, exist_ok=True)
        filename = os.path.basename(path)
        dest = project_config_mockup_path(self._project_dir, filename)
        # Handle name collision
        if os.path.abspath(path) != os.path.abspath(dest):
            base, ext = os.path.splitext(filename)
            counter = 1
            while os.path.isfile(dest):
                filename = f"{base}_{counter}{ext}"
                dest = project_config_mockup_path(self._project_dir, filename)
                counter += 1
            shutil.copy2(path, dest)

        # Store relative path (relative to .eguiproject/)
        rel_path = project_config_mockup_relpath(filename)
        self._current_page.mockup_image_path = rel_path
        self._current_page.mockup_image_visible = True
        self._set_background_toggle_state(True)

        # Apply to overlay
        self.preview_panel.set_background_image(pixmap)
        self.preview_panel.set_background_image_visible(True)
        self.preview_panel.set_background_image_opacity(self._current_page.mockup_image_opacity)
        self._refresh_project_watch_snapshot()
        self._record_page_state_change(update_preview=False, trigger_compile=False)
        self._update_preview_grid_and_mockup_action_metadata()
        self.statusBar().showMessage(f"Mockup image loaded: {filename}")

    def _toggle_background_image(self, visible):
        """Toggle mockup image visibility."""
        if self._current_page:
            if self._current_page.mockup_image_visible == visible:
                self.preview_panel.set_background_image_visible(visible)
                self._update_preview_grid_and_mockup_action_metadata()
                return
            self._current_page.mockup_image_visible = visible
        self.preview_panel.set_background_image_visible(visible)
        self._record_page_state_change(update_preview=False, trigger_compile=False, source="mockup visibility")
        self._update_preview_grid_and_mockup_action_metadata()

    def _clear_background_image(self):
        """Remove the mockup image from the current page."""
        if self._current_page and self._current_page.mockup_image_path:
            # Delete file from .eguiproject/mockup/
            if self._project_dir:
                full_path = project_config_path(self._project_dir, self._current_page.mockup_image_path)
                if os.path.isfile(full_path):
                    try:
                        os.remove(full_path)
                    except OSError:
                        pass
            self._current_page.mockup_image_path = ""
            self._current_page.mockup_image_visible = True
        self.preview_panel.clear_background_image()
        self._set_background_toggle_state(True)
        self._refresh_project_watch_snapshot()
        self._record_page_state_change(update_preview=False, trigger_compile=False)
        self._update_preview_grid_and_mockup_action_metadata()
        self.statusBar().showMessage("Mockup image cleared")

    def _set_background_opacity(self, opacity):
        """Set mockup image opacity."""
        if self._current_page:
            if self._current_page.mockup_image_opacity == opacity:
                self.preview_panel.set_background_image_opacity(opacity)
                self._update_preview_grid_and_mockup_action_metadata()
                return
            self._current_page.mockup_image_opacity = opacity
        self.preview_panel.set_background_image_opacity(opacity)
        self._record_page_state_change(update_preview=False, trigger_compile=False, source="mockup opacity")
        self._update_preview_grid_and_mockup_action_metadata()

    def _apply_page_mockup(self):
        """Load and apply the current page's mockup image."""
        if not self._current_page:
            self.preview_panel.clear_background_image()
            self._set_background_toggle_state(True)
            self._update_preview_grid_and_mockup_action_metadata()
            return

        path = self._current_page.mockup_image_path
        self._set_background_toggle_state(self._current_page.mockup_image_visible)
        self._sync_background_opacity_actions(self._current_page.mockup_image_opacity)
        if path and self._project_dir:
            full_path = project_config_path(self._project_dir, path)
            if os.path.isfile(full_path):
                from PyQt5.QtGui import QPixmap
                pixmap = QPixmap(full_path)
                if not pixmap.isNull():
                    # Scale to screen size if needed
                    sw = self.project.screen_width if self.project else 240
                    sh = self.project.screen_height if self.project else 320
                    if pixmap.width() != sw or pixmap.height() != sh:
                        pixmap = pixmap.scaled(sw, sh, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                    self.preview_panel.set_background_image(pixmap)
                    self.preview_panel.set_background_image_visible(
                        self._current_page.mockup_image_visible
                    )
                    self.preview_panel.set_background_image_opacity(
                        self._current_page.mockup_image_opacity
                    )
                    self._update_preview_grid_and_mockup_action_metadata()
                    return
        self.preview_panel.clear_background_image()
        self._update_preview_grid_and_mockup_action_metadata()

    def _set_background_toggle_state(self, visible):
        blocker = QSignalBlocker(self._toggle_bg_action)
        self._toggle_bg_action.setChecked(visible)
        del blocker

    def _sync_background_opacity_actions(self, opacity):
        target_pct = int(opacity * 100)
        for act in self._opacity_group.actions():
            act.setChecked(act.text() == f"{target_pct}%")

    def _apply_project(self):
        """Refresh all panels from the current project."""
        if not self.project:
            return

        self.project_dock.set_project(self.project)
        self.preview_panel.update_screen_size(self.project.screen_width, self.project.screen_height)
        if self.compiler is not None:
            self.compiler.set_screen_size(self.project.screen_width, self.project.screen_height)
        self._clear_page_tabs()
        self._refresh_page_navigator()

        # Refresh resource panel with catalog
        # Resource panel uses .eguiproject/resources/ as the source directory
        eguiproject_res_dir = self._get_eguiproject_resource_dir()
        res_dir = self._get_resource_dir()  # resource/ for property panel
        catalog = self.project.resource_catalog if self.project else None
        self.res_panel.set_resource_catalog(catalog)
        self.res_panel.set_resource_dir(eguiproject_res_dir)
        self.property_panel.set_resource_dir(res_dir)
        self.property_panel.set_source_resource_dir(eguiproject_res_dir)
        self.property_panel.set_resource_catalog(catalog)
        self._update_resource_usage_panel()

        # Refresh i18n string catalog
        string_catalog = self.project.string_catalog if self.project else None
        self.res_panel.set_string_catalog(string_catalog)
        # Feed string keys to property panel for @string/ completions
        if string_catalog:
            self.property_panel.set_string_keys(string_catalog.all_keys)
        else:
            self.property_panel.set_string_keys([])

        self._update_compile_availability()
        self._update_edit_actions()
        if self.compiler is not None:
            self._start_precompile()

    def _start_precompile(self):
        """Start background precompile if exe doesn't exist."""
        if not self.project:
            return
        if self._is_closing:
            return
        if self._is_auto_compile_retry_blocked():
            return
        if self.compiler is None or not self.compiler.can_build():
            reason = "SDK unavailable, compile preview disabled"
            if self.compiler is not None and self.compiler.get_build_error():
                reason = self.compiler.get_build_error()
            self._switch_to_python_preview(reason)
            return
        if not self._ensure_preview_build_available(auto=True):
            return
        if self._precompile_worker is not None and self._precompile_worker.isRunning():
            return
        if not self.compiler.is_exe_ready():
            self.statusBar().showMessage("Background compiling...")
            self.debug_panel.log_action("Starting background precompile...")
            self.debug_panel.log_info(f"Background precompile requested | {self._preview_runtime_snapshot()}")
            target_name_getter = getattr(self.compiler, "get_preview_make_target_name", None)
            target_name = target_name_getter() if callable(target_name_getter) else "main.exe"
            self.debug_panel.log_cmd(
                f"make -j {target_name} APP={self.app_name} PORT=designer "
                f"EGUI_APP_ROOT_PATH={self.compiler.app_root_arg} COMPILE_DEBUG= COMPILE_OPT_LEVEL=-O0"
            )
            generation = self._async_generation
            worker = self.compiler.precompile_async(
                callback=lambda success, message: self._on_precompile_done(worker, generation, success, message)
            )
            self._precompile_worker = worker

    def _on_precompile_done(self, worker, generation, success, message):
        """Callback when background precompile finishes."""
        self._cleanup_worker_ref(worker, "_precompile_worker")
        if self._is_closing or generation != self._async_generation:
            return
        self.debug_panel.log_info(
            f"Background precompile callback: success={success} message={message} | {self._preview_runtime_snapshot()}"
        )
        pending_rebuild = bool(self._pending_rebuild)
        pending_compile = bool(self._pending_compile) and not pending_rebuild
        self._pending_rebuild = False
        self._pending_compile = False
        if success:
            if self._resume_pending_external_reload_if_ready(generation):
                return
            self.statusBar().showMessage("Ready (precompiled)", 3000)
            self.debug_panel.log_success("Background precompile completed")
            if pending_rebuild:
                self._start_compile_cycle(force_rebuild=True, reason_fallback="pending clean rebuild")
            elif pending_compile:
                self._start_compile_cycle(force_rebuild=False, reason_fallback="pending auto compile")
        else:
            failure_summary = self._compile_failure_summary(message, "Precompile failed")
            self._block_auto_compile_retry(failure_summary)
            self.debug_panel.log_error("Background precompile failed")
            self.debug_panel.log_compile_output(False, message)
            status_message, guidance_message = self._compile_failure_feedback(
                message,
                force_rebuild=False,
                rebuild_unavailable_reason=self._rebuild_retry_blocked_reason(),
            )
            self.statusBar().showMessage(status_message, 5000)
            if guidance_message:
                self.debug_panel.log_info(guidance_message)
            self._switch_to_python_preview(failure_summary)
            self._update_debug_rebuild_action(show=self._should_offer_debug_rebuild_action(failure_summary))
            self._update_compile_availability()
            self._show_bottom_panel("Debug Output")
            if self._resume_pending_external_reload_if_ready(generation):
                return

    def _refresh_page_navigator(self):
        if not self.project:
            self.page_navigator.set_pages({})
            self.page_navigator.set_startup_page("")
            self.page_navigator.set_current_page("")
            return

        self.page_navigator.set_screen_size(self.project.screen_width, self.project.screen_height)
        self.page_navigator.set_pages({page.name: page for page in self.project.pages})
        self.page_navigator.set_startup_page(getattr(self.project, "startup_page", ""))

        current_name = ""
        if self._current_page and self.project.get_page_by_name(self._current_page.name):
            current_name = self._current_page.name
        self.page_navigator.set_current_page(current_name)

    def _make_unique_page_name(self, base_name):
        candidate = (base_name or "page").strip().replace(" ", "_").replace(".xml", "")
        if not candidate:
            candidate = "page"
        if not self.project:
            return candidate

        existing = {page.name for page in self.project.pages}
        if candidate not in existing:
            return candidate

        match = re.match(r"^(.*?)(?:_(\d+))?$", candidate)
        stem = candidate
        suffix = 2
        if match:
            stem = match.group(1) or candidate
            if match.group(2):
                suffix = int(match.group(2)) + 1

        while f"{stem}_{suffix}" in existing:
            suffix += 1
        return f"{stem}_{suffix}"

    # 鈹€鈹€ Resource panel integration 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    def _get_resource_dir(self):
        """Compute the resource directory path (resource/) for the current project.

        Used for the generation pipeline and for property_panel to scan
        generated fonts in resource/font/.
        """
        return self._resolve_project_path("get_resource_dir", project_generated_resource_dir)

    def _get_project_file_path(self):
        """Compute the project metadata file path ({app_name}.egui)."""
        return self._resolve_project_path(
            "get_project_file_path",
            lambda project_dir: project_file_path(project_dir, self.app_name),
        )

    def _resolve_project_path(self, project_getter_name, fallback_resolver):
        if self.project:
            getter = getattr(self.project, project_getter_name, None)
            if callable(getter):
                path = getter()
                if path:
                    return path
        if self._project_dir:
            return fallback_resolver(self._project_dir)
        return ""

    def _get_resource_src_dir(self):
        """Compute the generated resource source directory (resource/src/)."""
        return self._resolve_project_path("get_resource_src_dir", project_resource_src_dir)

    def _get_build_mk_path(self):
        """Compute the user-owned build.mk wrapper path."""
        return self._resolve_project_path("get_build_mk_path", project_build_mk_path)

    def _get_app_config_path(self):
        """Compute the user-owned app_egui_config.h wrapper path."""
        return self._resolve_project_path("get_app_config_path", project_app_config_path)

    def _get_designer_dir(self):
        """Compute the designer-managed .designer/ directory path."""
        return self._resolve_project_path("get_designer_dir", project_designer_dir)

    def _get_user_resource_config_path(self):
        """Compute the user-owned resource overlay config path."""
        return self._resolve_project_path("get_user_resource_config_path", project_user_resource_config_path)

    def _get_designer_resource_dir(self):
        """Compute the designer-managed resource metadata directory path."""
        return self._resolve_project_path("get_designer_resource_dir", project_designer_resource_dir)

    def _get_eguiproject_resource_dir(self):
        """Compute the .eguiproject/resources/ path for the current project.

        This is the authoritative directory for all source resource files.
        Used by the resource panel for browsing and importing.
        """
        return self._resolve_project_path("get_eguiproject_resource_dir", project_config_resource_dir)

    def _get_eguiproject_layout_dir(self):
        """Compute the .eguiproject/layout/ path for the current project."""
        return self._resolve_project_path("get_eguiproject_layout_dir", project_config_layout_dir)

    def _get_eguiproject_mockup_dir(self):
        """Compute the .eguiproject/mockup/ path for the current project."""
        return self._resolve_project_path("get_eguiproject_mockup_dir", project_config_mockup_dir)

    def _get_eguiproject_images_dir(self):
        """Compute the .eguiproject/resources/images/ path.

        Authoritative directory for source image files.
        Used for Page XML image path resolution.
        """
        return self._resolve_project_path("get_eguiproject_images_dir", project_config_images_dir)

    def _on_resource_selected(self, res_type, filename):
        """User selected/assigned a resource from the ResourcePanel."""
        target = self._primary_selected_widget()
        if target is None:
            return
        if not assign_resource_to_widget(target, res_type, filename):
            return
        self.property_panel.set_selection(self._selected_widgets(), self._primary_selected_widget())
        self._update_resource_usage_panel()
        self._on_model_changed(source=f"{res_type} resource assignment")

    def _on_resource_renamed(self, res_type, old_name, new_name):
        """Update widget references after a resource file was renamed."""
        touched_pages = self._rewrite_resource_references(res_type, old_name, new_name)
        self._mark_project_dirty("resources")
        self._finalize_resource_reference_change(touched_pages, source=f"{res_type} resource rename")

    def _on_resource_deleted(self, res_type, filename):
        """Clear widget references after a resource file was deleted."""
        touched_pages = self._rewrite_resource_references(res_type, filename, "")
        self._mark_project_dirty("resources")
        self._finalize_resource_reference_change(touched_pages, source=f"{res_type} resource delete")

    def _on_string_key_deleted(self, key, replacement_text):
        """Rewrite widget text references after a string key was deleted."""
        touched_pages, _ = rewrite_project_string_references(
            self.project,
            key,
            replacement_text=replacement_text,
        )
        self._mark_project_dirty("strings")
        self._finalize_resource_reference_change(touched_pages, source="string key delete")

    def _on_string_key_renamed(self, old_key, new_key):
        """Rewrite widget text references after a string key was renamed."""
        touched_pages, _ = rewrite_project_string_references(
            self.project,
            old_key,
            new_key=new_key,
        )
        self._mark_project_dirty("strings")
        self._finalize_resource_reference_change(touched_pages, source="string key rename")

    def _on_resource_imported(self):
        """Resource files were imported 鈥?sync catalog and auto-regenerate."""
        # Sync catalog from resource panel back to project
        if self.project:
            catalog = self.res_panel.get_resource_catalog()
            self.project.resource_catalog = catalog
            self.property_panel.set_resource_catalog(catalog)
            # Sync i18n string catalog
            self.project.string_catalog = self.res_panel.get_string_catalog()
            self.property_panel.set_string_keys(self.project.string_catalog.all_keys)
        self._update_resource_usage_panel()
        self._update_diagnostics_panel()
        self._resources_need_regen = True
        self._mark_project_dirty("resources")
        # Auto-trigger resource generation with debounce
        self._refresh_project_watch_snapshot()
        self._regen_timer.start()
        current_message = self.statusBar().currentMessage()
        if not current_message.startswith("Updated resources in "):
            self.statusBar().showMessage("Resources changed, will regenerate...")

    def _on_resource_feedback_message(self, message):
        if message:
            self.statusBar().showMessage(message, 5000)

    def _on_property_panel_generate_charset_requested(self, resource_type, source_name, initial_filename):
        self._select_left_panel("assets")
        self.res_panel.open_generate_charset_dialog_for_resource(
            resource_type,
            source_name,
            initial_filename=initial_filename,
        )

    def _on_resource_usage_activated(self, page_name, widget_name):
        if not self.project or not page_name or not widget_name:
            return
        if self._current_page is None or self._current_page.name != page_name:
            self._switch_page(page_name)
        target_page = self.project.get_page_by_name(page_name)
        target_widget = self._find_widget_in_page(target_page, widget_name)
        if target_widget is not None:
            self._set_selection([target_widget], primary=target_widget, sync_tree=True, sync_preview=True)
            self._focus_properties_for_selection()
            self.statusBar().showMessage(f"Focused resource usage: {page_name}/{widget_name}.", 4000)

    def _rewrite_resource_references(self, res_type, old_name, new_name):
        """Rewrite matching resource filename references across all project pages."""
        touched_pages, _ = rewrite_project_resource_references(self.project, res_type, old_name, new_name)
        return touched_pages

    def _finalize_resource_reference_change(self, touched_pages, source="resource reference update"):
        """Record dirty state and refresh current-page UI after resource ref changes."""
        if not touched_pages:
            return

        current_page_changed = False
        for page in touched_pages:
            stack = self._undo_manager.get_stack(page.name)
            stack.push(page.to_xml_string(), label=source or "resource reference update")
            self.page_navigator.refresh_thumbnail(page.name)
            if page is self._current_page:
                current_page_changed = True

        if current_page_changed:
            self.widget_tree.rebuild_tree()
            self.widget_tree.set_selected_widgets(self._selection_state.widgets, self._selection_state.primary)
            if self._selection_state.primary is not None:
                try:
                    self.property_panel.set_selection(self._selection_state.widgets, self._selection_state.primary)
                except RuntimeError:
                    pass
            self._update_preview_overlay()
            self._sync_xml_to_editors()

        self._update_resource_usage_panel()
        self._update_diagnostics_panel()
        self._update_undo_actions()
        self._update_window_title()
        if source:
            page_count = len(touched_pages)
            noun = "page" if page_count == 1 else "pages"
            self.statusBar().showMessage(f"Updated resources in {page_count} {noun}: {source}.", 4000)

    def _on_resource_dropped(self, widget, res_type, filename):
        """Resource was dropped onto a widget in the preview overlay."""
        self._set_selection([widget], primary=widget, sync_tree=True, sync_preview=False)
        self._focus_properties_for_selection()
        if not assign_resource_to_widget(widget, res_type, filename):
            return
        self.property_panel.set_selection(self._selection_state.widgets, self._selection_state.primary)
        self._update_resource_usage_panel()
        self._on_model_changed(source=f"{res_type} resource drop")

    def _current_screen_size(self):
        """Return the active logical screen size for preview-bound operations."""
        if self.project is not None:
            width = int(getattr(self.project, "screen_width", 0) or 0)
            height = int(getattr(self.project, "screen_height", 0) or 0)
            if width > 0 and height > 0:
                return width, height
        width = int(getattr(getattr(self, "preview_panel", None), "screen_width", 0) or 240)
        height = int(getattr(getattr(self, "preview_panel", None), "screen_height", 0) or 320)
        return max(width, 1), max(height, 1)

    def _on_widget_type_dropped(self, widget_type, x, y, target_widget):
        """Widget type dropped from library onto preview overlay."""
        widget_type = str(widget_type or "").strip()
        if not widget_type or self._current_page is None:
            return

        target_parent = None
        if target_widget is not None and getattr(target_widget, "is_container", False):
            target_parent = target_widget

        inserted = self.widget_tree.insert_widget(widget_type, parent=target_parent)
        if inserted is None:
            return

        if target_parent is None:
            screen_width, screen_height = self._current_screen_size()
            inserted.x = max(0, min(int(x or 0), max(screen_width - inserted.width, 0)))
            inserted.y = max(0, min(int(y or 0), max(screen_height - inserted.height, 0)))
            inserted.display_x = inserted.x
            inserted.display_y = inserted.y

        self.widget_tree.rebuild_tree()
        self._set_selection([inserted], primary=inserted, sync_tree=True, sync_preview=True)
        self._focus_properties_for_selection()
        self._record_page_state_change(source=f"widget drag insert: {widget_type}")

        if hasattr(self, "widget_browser"):
            self.widget_browser.record_insert(widget_type)

        self.statusBar().showMessage(
            f"Inserted {WidgetRegistry.instance().display_name(widget_type)} via drag",
            3000,
        )

    def _run_resource_generation(self, silent=False):
        if not self.project or not self._project_dir:
            return False
        if not self._has_valid_sdk_root():
            if not silent:
                QMessageBox.warning(
                    self,
                    "SDK Root Missing",
                    "A valid EmbeddedGUI SDK root is required to run resource generation.",
                )
            self.debug_panel.log_error("Resource generation skipped: SDK root is missing or invalid")
            return False

        res_dir = self._get_resource_dir()
        eguiproject_res_dir = self._get_eguiproject_resource_dir()
        src_dir = self._get_resource_src_dir() if res_dir else ""
        if not res_dir or not eguiproject_res_dir or not os.path.isdir(eguiproject_res_dir):
            if not silent:
                QMessageBox.warning(
                    self,
                    "Error",
                    f"No {RESOURCE_DIR_RELPATH} directory found.\nPlease import resources first.",
                )
            return False

        try:
            sync_project_resources_and_generate_designer_resource_config(
                self.project,
                self._project_dir,
                src_dir,
            )
            self._sync_project_watch_snapshot_after_internal_write()
        except Exception as exc:
            self.debug_panel.log_error(f"Resource config generation failed: {exc}")
            if not silent:
                QMessageBox.warning(self, "Error", f"Failed to generate resource config:\n{exc}")
            return False

        import subprocess
        import sys

        gen_script = sdk_resource_generator_path(self.project_root)
        if not os.path.isfile(gen_script):
            if not silent:
                QMessageBox.warning(self, "Error", f"Cannot find resource generator:\n{gen_script}")
            self.debug_panel.log_error(f"Resource generation skipped: missing generator {gen_script}")
            return False

        output_dir = sdk_output_dir(self.project_root)
        os.makedirs(output_dir, exist_ok=True)
        cmd = [
            sys.executable,
            gen_script,
            "-r",
            res_dir,
            "-o",
            output_dir,
            "-f",
            "true",
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=self.project_root,
            )
        except Exception as exc:
            self.debug_panel.log_error(f"Resource generation error: {exc}")
            if not silent:
                QMessageBox.warning(self, "Error", f"Failed to run resource generator:\n{exc}")
            return False

        if result.returncode != 0:
            err = result.stderr or result.stdout or "Unknown error"
            self.debug_panel.log_error(f"Resource generation failed (rc={result.returncode})")
            self.debug_panel.log_compile_output(False, err[:2000])
            if not silent:
                QMessageBox.warning(
                    self,
                    "Resource Generation Failed",
                    f"Return code {result.returncode}:\n{err[:2000]}",
                )
            return False

        self._resources_need_regen = False
        self.debug_panel.log_info("Resources generated successfully")
        return True

    def _generate_resources(self, silent=False):
        f"""Run the resource generation pipeline.

        Steps:
        1. Sync ``{RESOURCE_DIR_RELPATH}/`` -> ``{RESOURCE_SRC_DIR_RELPATH}/``
        2. Generate ``{DESIGNER_RESOURCE_CONFIG_RELPATH}`` from layout XML
        3. Run ``{_RESOURCE_GENERATOR_SCRIPT_NAME}`` to produce C source files

        Args:
            silent: If True, suppress warning dialogs (used for auto-trigger).
        """
        self.statusBar().showMessage("Generating resources...")
        if self._run_resource_generation(silent=silent):
            self.statusBar().showMessage("Resource generation completed.")
        else:
            self.statusBar().showMessage("Resource generation FAILED.")

    def _ensure_resources_generated(self):
        f"""Generate split resource config from widget properties and run
        ``{_RESOURCE_GENERATOR_SCRIPT_NAME}`` if ``{RESOURCE_DIR_RELPATH}/`` exists.

        Called before each compile to ensure resource C files are up-to-date.
        Skips entirely when resources haven't changed since last generation.
        Runs silently 鈥?errors are logged to debug panel only.
        """
        output_resource_bin = sdk_output_path(self.project_root, "app_egui_resource_merge.bin")
        resource_output_missing = bool(output_resource_bin) and not os.path.exists(output_resource_bin)
        if not self._resources_need_regen and not resource_output_missing:
            return
        self._run_resource_generation(silent=True)

    # 鈹€鈹€ Page management 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    def _switch_page(self, page_name):
        """Switch the editor to display a specific page."""
        if not self.project:
            return
        page = self.project.get_page_by_name(page_name)
        if page is None:
            return
        self._current_page = page
        if hasattr(self, "_state_store"):
            self._state_store.set_current_page(page_name)
        self.res_panel.set_usage_page_context(page_name)
        self._clear_selection(sync_tree=True, sync_preview=True)
        self.project_dock.set_current_page(page_name)
        self.page_navigator.set_current_page(page_name)

        # Initialize undo stack for this page if empty
        stack = self._undo_manager.get_stack(page_name)
        if not stack._history:
            stack.push(page.to_xml_string(), label="Loaded page")
            if not page.dirty:
                stack.mark_saved()

        # Ensure page tab exists and is selected
        self._syncing_tabs = True
        self._ensure_page_tab(page_name)
        self.page_tab_bar.setCurrentTab(page_name)
        self._syncing_tabs = False

        # Update widget tree with this page's widgets
        # Create a shim so WidgetTreePanel.set_project() works
        self._page_shim = _PageProjectShim(page)
        self.widget_tree.set_project(self._page_shim)
        self.page_fields_panel.set_page(page)
        self.page_timers_panel.set_page(page)

        # Update preview & XML
        self._update_preview_overlay()
        self._sync_xml_to_editors()

        # Load mockup image for this page
        self._apply_page_mockup()

        # Trigger compile to show current page in preview
        self._trigger_compile(reason="page switch")
        self._update_undo_actions()
        self._update_edit_actions()
        self._update_window_title()
        self._update_workspace_tab_metadata()

    def _on_page_selected(self, page_name):
        """User clicked a page in the Project Explorer."""
        self._switch_page(page_name)

    def _on_widget_animations_changed(self, animations):
        widget = self._primary_selected_widget()
        if widget is None:
            return
        widget.animations = list(animations or [])
        self._record_page_state_change(update_preview=False, trigger_compile=True, source="widget animations edit")

    def _on_page_fields_changed(self, fields):
        if self._current_page is None:
            return
        self._current_page.user_fields = list(fields or [])
        self._record_page_state_change(update_preview=False, trigger_compile=True, source="page fields edit")

    def _on_page_timers_changed(self, timers):
        if self._current_page is None:
            return
        self._current_page.timers = list(timers or [])
        self._record_page_state_change(update_preview=False, trigger_compile=True, source="page timers edit")

    def _page_user_source_path(self, page):
        if page is None or not self._project_dir:
            return ""
        return project_page_user_source_path(self._project_dir, page.name)

    def _generate_page_user_source_content(self, page):
        content = generate_page_user_source(page, self.project)
        return embed_source_hash(content, compute_source_hash(content))

    def _insert_callback_stub_into_user_source(self, content, page, callback_name, signature):
        if not content or not callback_name or _callback_definition_exists(content, callback_name):
            return content, False

        target = _resolve_page_callback_target(page, callback_name, signature)
        stub = render_page_callback_stub(
            page,
            target.get("name", ""),
            target.get("signature", ""),
            kind=target.get("kind", "view"),
        )
        if not stub:
            return content, False

        trimmed = content.rstrip()
        if trimmed:
            updated = trimmed + "\n\n" + stub + "\n"
        else:
            updated = stub + "\n"
        return updated, True

    def _ensure_page_user_source_ready(self, page, callback_name="", signature=""):
        filepath = self._page_user_source_path(page)
        if not filepath:
            return "", False, False

        existing_content = read_existing_file(filepath)
        if existing_content is None:
            content = self._generate_page_user_source_content(page)
        else:
            content = existing_content

        inserted = False
        if callback_name:
            content, inserted = self._insert_callback_stub_into_user_source(content, page, callback_name, signature)

        should_write = existing_content is None or content != existing_content
        if should_write:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

        has_callback = not callback_name or _callback_definition_exists(content, callback_name)
        return filepath, should_write or inserted, has_callback

    def _open_path_in_default_app(self, path):
        if not path or not os.path.exists(path):
            return False

        import subprocess
        import sys

        try:
            if os.name == "nt":
                os.startfile(os.path.normpath(path))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
            return True
        except Exception as exc:
            self.debug_panel.log_error(f"Failed to open user source: {exc}")
            return False

    def _open_page_user_source(self, callback_name="", signature="", section_name=""):
        if self.project is None or self._current_page is None:
            self.statusBar().showMessage("No active page available for user code.", 5000)
            return
        if not self._project_dir:
            self.statusBar().showMessage("Save the project first to create user source files.", 5000)
            return

        self._flush_pending_xml()

        filepath, updated, has_callback = self._ensure_page_user_source_ready(
            self._current_page,
            callback_name or "",
            signature or "",
        )
        if not filepath:
            self.statusBar().showMessage("Unable to resolve the page user source file.", 5000)
            return
        if updated:
            self._refresh_project_watch_snapshot()

        if not self._open_path_in_default_app(filepath):
            QMessageBox.warning(self, "Open User Code", f"Failed to open:\n{filepath}")
            return

        if callback_name and has_callback:
            self.statusBar().showMessage(
                f"Opened user code: {self._current_page.name}.c ({callback_name}).",
                5000,
            )
            return
        if callback_name:
            self.statusBar().showMessage(
                f"Opened user code: {self._current_page.name}.c. Add '{callback_name}' manually if needed.",
                5000,
            )
            return
        if section_name:
            self.statusBar().showMessage(
                f"Opened user code: {self._current_page.name}.c ({section_name}).",
                5000,
            )
            return
        self.statusBar().showMessage(f"Opened user code: {self._current_page.name}.c.", 5000)

    def _on_user_code_requested(self, callback_name, signature):
        self._open_page_user_source(callback_name=callback_name, signature=signature)

    def _on_page_user_code_section_requested(self, section_name):
        self._open_page_user_source(section_name=section_name or "")

    def _open_page_field_diagnostic(self, page_name, field_name):
        if not field_name or not hasattr(self, "page_fields_panel"):
            return False
        self._show_inspector_tab("page", inner_section="fields")
        if not self.page_fields_panel.select_field(field_name):
            return False
        self.statusBar().showMessage(f"Opened diagnostic field: {page_name}/{field_name}.", 4000)
        return True

    def _open_page_timer_diagnostic(self, page_name, timer_name):
        if not timer_name or not hasattr(self, "page_timers_panel"):
            return False
        self._show_inspector_tab("page", inner_section="timers")
        if not self.page_timers_panel.select_timer(timer_name):
            return False
        self.statusBar().showMessage(f"Opened diagnostic timer: {page_name}/{timer_name}.", 4000)
        return True

    def _on_diagnostic_requested(self, page_name, widget_name):
        if not self.project:
            return

        diagnostic_entry = self.diagnostics_panel.current_activated_entry() if hasattr(self, "diagnostics_panel") else None

        target_page_name = page_name or (self._current_page.name if self._current_page is not None else "")
        if not target_page_name:
            return

        page = self.project.get_page_by_name(target_page_name)
        if page is None:
            return

        if self._current_page is None or self._current_page.name != target_page_name:
            self._switch_page(target_page_name)
            page = self._current_page

        if not widget_name:
            return

        widget = self._find_widget_in_page(page, widget_name)
        if widget is None:
            diagnostic_code = str(getattr(diagnostic_entry, "code", "") or "")
            if diagnostic_code.startswith("page_field_") and self._open_page_field_diagnostic(target_page_name, widget_name):
                return
            if diagnostic_code.startswith("page_timer_") and self._open_page_timer_diagnostic(target_page_name, widget_name):
                return
            self.statusBar().showMessage(f"Diagnostic target not found: {target_page_name}/{widget_name}", 4000)
            return

        self._set_selection([widget], primary=widget, sync_tree=True, sync_preview=True)
        self._focus_properties_for_selection()
        if diagnostic_entry is not None and getattr(diagnostic_entry, "resource_type", "") and getattr(diagnostic_entry, "resource_name", ""):
            self._select_left_panel("assets")
            self.res_panel._select_resource_item(diagnostic_entry.resource_type, diagnostic_entry.resource_name)
            self.statusBar().showMessage(
                f"Opened diagnostic resource check: {diagnostic_entry.resource_type}/{diagnostic_entry.resource_name}.",
                4000,
            )
            return
        self.statusBar().showMessage(f"Opened diagnostic target: {target_page_name}/{widget_name}.", 4000)

    def _on_page_added(self, page_name):
        """User requested a new page."""
        if not self.project:
            return
        self.project.create_new_page(page_name)
        self.project_dock.set_project(self.project)
        self._refresh_page_navigator()
        self._ensure_page_tab(page_name)
        self._switch_page(page_name)
        self._mark_project_dirty("pages")
        self._trigger_compile(reason="page add")

    def _on_page_duplicated(self, source_name, page_name):
        """User requested duplicating an existing page."""
        if not self.project:
            return
        self.project.duplicate_page(source_name, page_name)
        self.project_dock.set_project(self.project)
        self._refresh_page_navigator()
        self._ensure_page_tab(page_name)
        self._switch_page(page_name)
        self._mark_project_dirty("pages")
        self._trigger_compile(reason="page duplicate")

    def _on_page_removed(self, page_name):
        """User deleted a page."""
        if not self.project:
            return
        page = self.project.get_page_by_name(page_name)
        if page:
            was_current = self._current_page is not None and self._current_page.name == page_name
            self.project.remove_page(page)
            self._undo_manager.remove_stack(page_name)
            self.project_dock.set_project(self.project)
            self._refresh_page_navigator()
            self._remove_page_tab(page_name)
            # Delete generated files for the removed page so they are not
            # picked up by EGUI_CODE_SRC on the next build.
            if self._project_dir:
                disk_page_names = [page_name]
                disk_page_names.extend(self._consume_pending_page_rename_sources(page_name))
                for disk_page_name in dict.fromkeys(disk_page_names):
                    delete_page_generated_files(self._project_dir, disk_page_name)
            if was_current and self.project.pages:
                self._switch_page(self.project.pages[0].name)
            elif not self.project.pages:
                self._current_page = None
                self._clear_selection(sync_tree=True, sync_preview=True)
                self.widget_tree.set_project(None)
                self.preview_panel.set_widgets([])
                self.preview_panel.set_selection([])
                self.page_navigator.set_current_page("")
            elif self._current_page:
                self.project_dock.set_current_page(self._current_page.name)
                self.page_navigator.set_current_page(self._current_page.name)
                self._update_preview_overlay()
            self._mark_project_dirty("pages")
            self._trigger_compile(reason="page remove")
            self._update_window_title()
            self._update_edit_actions()

    def _on_page_renamed(self, old_name, new_name):
        """User renamed a page."""
        if not self.project:
            return
        page = self.project.get_page_by_name(old_name)
        if page:
            was_current = self._current_page is not None and self._current_page.name == old_name
            page.file_path = project_config_layout_xml_relpath(new_name)
            self._record_pending_page_rename(old_name, new_name)
            # Update startup_page reference if needed
            if self.project.startup_page == old_name:
                self.project.startup_page = new_name
            self._undo_manager.rename_stack(old_name, new_name)
            self.project_dock.set_project(self.project)
            self._refresh_page_navigator()
            self._rename_page_tab(old_name, new_name)
            self._mark_project_dirty("page rename")
            if was_current:
                self._switch_page(new_name)
            elif self._current_page:
                self.project_dock.set_current_page(self._current_page.name)
                self.page_navigator.set_current_page(self._current_page.name)
                self._trigger_compile(reason="page rename")
                self._update_edit_actions()

    def _record_pending_page_rename(self, old_name, new_name):
        if not old_name or not new_name or old_name == new_name:
            return

        updated = {}
        remapped_existing = False
        for source_name, current_name in self._pending_page_renames.items():
            if current_name == old_name:
                current_name = new_name
                remapped_existing = True
            updated[source_name] = current_name

        if not remapped_existing:
            updated[old_name] = new_name

        self._pending_page_renames = {
            source_name: current_name
            for source_name, current_name in updated.items()
            if source_name and current_name and source_name != current_name
        }

    def _consume_pending_page_rename_sources(self, page_name):
        sources = [
            source_name
            for source_name, current_name in self._pending_page_renames.items()
            if current_name == page_name
        ]
        for source_name in sources:
            self._pending_page_renames.pop(source_name, None)
        return sources

    def _apply_pending_page_rename_outputs(self, output_dir):
        if not output_dir or not self._pending_page_renames:
            return

        for old_name, new_name in self._pending_page_renames.items():
            if not old_name or not new_name or old_name == new_name:
                continue

            for suffix in (
                designer_page_header_relpath(old_name),
                designer_page_layout_relpath(old_name),
                f"{old_name}.h",
                f"{old_name}_layout.c",
            ):
                src = _project_child_realpath(output_dir, suffix)
                if src is None:
                    continue
                try:
                    if os.path.isfile(src):
                        os.remove(src)
                except OSError:
                    pass

            for old_suffix, new_suffix in (
                (
                    page_user_source_relpath(old_name),
                    page_user_source_relpath(new_name),
                ),
                (
                    page_ext_header_relpath(old_name),
                    page_ext_header_relpath(new_name),
                ),
            ):
                src = _project_child_realpath(output_dir, old_suffix)
                dest = _project_child_realpath(output_dir, new_suffix)
                if src is None or dest is None or not os.path.isfile(src):
                    continue
                try:
                    if os.path.exists(dest):
                        _archive_page_user_file(output_dir, old_name, src)
                    else:
                        shutil.move(src, dest)
                except OSError:
                    _archive_page_user_file(output_dir, old_name, src)

    def _duplicate_page_from_navigator(self, page_name):
        if not self.project or not page_name:
            return
        self._on_page_duplicated(page_name, self._make_unique_page_name(f"{page_name}_copy"))

    def _on_page_add_from_template(self, template_key, anchor_page_name):
        del anchor_page_name
        if not self.project or template_key not in PAGE_TEMPLATES:
            return

        page_name = self._make_unique_page_name(f"{template_key}_page")
        template = PAGE_TEMPLATES[template_key]
        page = self.project.create_new_page(page_name)
        page.dirty = True

        existing_names = {widget.name for widget in page.get_all_widgets() if widget.name}
        root_widget = page.root_widget
        if root_widget is not None:
            for spec in template.get("widgets", []):
                widget = WidgetModel(
                    spec.get("type", "label"),
                    name=spec.get("name"),
                    x=spec.get("x", 0),
                    y=spec.get("y", 0),
                    width=spec.get("w", 100),
                    height=spec.get("h", 40),
                )
                widget.name = self._make_unique_widget_name(widget.name, existing_names=existing_names)
                if "text" in spec and "text" in widget.properties:
                    widget.properties["text"] = spec["text"]
                root_widget.add_child(widget)

        self.project_dock.set_project(self.project)
        self._refresh_page_navigator()
        self._ensure_page_tab(page_name)
        self._switch_page(page_name)
        self._mark_project_dirty("pages")

    def _on_startup_changed(self, page_name):
        """User changed the startup page."""
        if self.project and self.project.startup_page != page_name:
            self.project.startup_page = page_name
            self.project_dock.set_project(self.project)
            self.page_navigator.set_startup_page(page_name)
            self._update_page_tab_bar_metadata()
            self._update_workspace_chips()
            self._mark_project_dirty("startup page")
            self._trigger_compile(reason="startup page")

    def _on_page_mode_changed(self, mode):
        """User switched between easy_page and activity mode."""
        if self.project and self.project.page_mode != mode:
            self.project.page_mode = mode
            self._mark_project_dirty("page mode")
            self._trigger_compile(reason="page mode")

    # 鈹€鈹€ Page tabs (qfluentwidgets TabBar) 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    def _page_tab_name(self, index):
        item = self.page_tab_bar.tabItem(index)
        if item is not None and hasattr(item, "routeKey"):
            return item.routeKey()
        return self.page_tab_bar.tabText(index).rstrip("*")

    def _page_tab_label(self, page_name, dirty_pages=None):
        if dirty_pages is None:
            dirty_pages = set(self._undo_manager.dirty_pages())
        else:
            dirty_pages = set(dirty_pages)
        return f"{page_name}*" if page_name in dirty_pages else page_name

    def _ensure_page_tab(self, page_name):
        """Add a tab for page_name if not already present. Returns the index."""
        for i in range(self.page_tab_bar.count()):
            if self._page_tab_name(i) == page_name:
                return i
        # routeKey = page_name (unique per page)
        self.page_tab_bar.addTab(page_name, self._page_tab_label(page_name), None)
        self._update_page_tab_bar_metadata()
        return self.page_tab_bar.count() - 1

    def _remove_page_tab(self, page_name):
        for i in range(self.page_tab_bar.count()):
            if self._page_tab_name(i) == page_name:
                self.page_tab_bar.removeTab(i)
                self._update_page_tab_bar_metadata()
                return

    def _rename_page_tab(self, old_name, new_name):
        for i in range(self.page_tab_bar.count()):
            if self._page_tab_name(i) == old_name:
                item = self.page_tab_bar.tabItem(i)
                if item is not None and hasattr(item, "setRouteKey"):
                    item.setRouteKey(new_name)
                self.page_tab_bar.setTabText(i, self._page_tab_label(new_name))
                self._update_page_tab_bar_metadata()
                return

    def _on_page_tab_changed(self, index):
        if self._syncing_tabs:
            return
        if index < 0:
            self._update_page_tab_bar_metadata()
            return
        page_name = self._page_tab_name(index)
        if self._current_page and page_name == self._current_page.name:
            self._update_page_tab_bar_metadata()
            return
        self._switch_page(page_name)

    def _on_page_tab_closed(self, index):
        if index < 0:
            return
        page_name = self._page_tab_name(index)
        self.page_tab_bar.removeTab(index)
        self._update_page_tab_bar_metadata()
        # If current page tab closed, switch to another open tab or fallback
        if self._current_page and self._current_page.name == page_name:
            if self.page_tab_bar.count() > 0:
                new_index = min(index, self.page_tab_bar.count() - 1)
                self.page_tab_bar.setCurrentIndex(new_index)
                self._on_page_tab_changed(new_index)
            elif self.project and self.project.pages:
                self._switch_page(self.project.pages[0].name)

    def _build_page_tab_context_menu(self, index):
        menu = QMenu(self)
        menu.setToolTipsVisible(True)
        actions = {}

        if index >= 0:
            page_name = self._page_tab_name(index)
            close_tab = menu.addAction("Close")
            self._apply_action_hint(close_tab, self._page_tab_context_action_hint("close_tab", page_name))
            actions["close_tab"] = close_tab

            close_others = menu.addAction("Close Others")
            can_close_others = self.page_tab_bar.count() > 1
            close_others.setEnabled(can_close_others)
            self._apply_action_hint(
                close_others,
                self._action_hint(
                    self._page_tab_context_action_hint("close_others", page_name),
                    can_close_others,
                    "only 1 page tab is open",
                ),
            )
            actions["close_others"] = close_others

            close_all = menu.addAction("Close All")
            self._apply_action_hint(close_all, self._page_tab_context_action_hint("close_all", page_name))
            actions["close_all"] = close_all

        return menu, actions

    def _show_tab_context_menu(self, pos):
        index = -1
        for i in range(self.page_tab_bar.count()):
            r = self.page_tab_bar.tabRect(i)
            if r.contains(pos):
                index = i
                break

        menu, actions = self._build_page_tab_context_menu(index)
        close_tab = actions.get("close_tab")
        close_others = actions.get("close_others")
        close_all = actions.get("close_all")

        action = menu.exec_(self.page_tab_bar.mapToGlobal(pos))
        if action is None:
            return

        if action == close_tab and index >= 0:
            self._on_page_tab_closed(index)
        elif action == close_others and index >= 0:
            keep_name = self._page_tab_name(index)
            names_to_remove = []
            for i in range(self.page_tab_bar.count()):
                n = self._page_tab_name(i)
                if n != keep_name:
                    names_to_remove.append(n)
            for n in names_to_remove:
                self._remove_page_tab(n)
        elif action == close_all:
            self._clear_page_tabs()

    def _focused_text_input_widget(self):
        focus_widget = QApplication.focusWidget()
        if isinstance(focus_widget, (QLineEdit, QPlainTextEdit, QTextEdit)):
            return focus_widget
        return None

    def _select_all_page_widgets(self):
        if self._current_page is None:
            return []

        widgets = [
            widget
            for widget in self._current_page.get_all_widgets()
            if not getattr(widget, "designer_hidden", False)
        ]
        root_widget = self._current_page.root_widget
        if root_widget is not None and any(widget is not root_widget for widget in widgets):
            widgets = [widget for widget in widgets if widget is not root_widget]
        return widgets

    def _select_all(self):
        text_widget = self._focused_text_input_widget()
        if text_widget is not None:
            text_widget.selectAll()
            return

        widgets = self._select_all_page_widgets()
        if not widgets:
            return

        primary = self._selection_state.primary if self._selection_state.primary in widgets else widgets[-1]
        self._set_selection(widgets, primary=primary, sync_tree=True, sync_preview=True)
        self.statusBar().showMessage(f"Selected {len(widgets)} visible widget(s).", 3000)

    def _build_preview_context_menu(self, widget=None):
        menu = QMenu(self)
        menu.setToolTipsVisible(True)
        menu.addAction(self._select_all_action)
        if widget is not None and hasattr(self, "widget_tree") and self.widget_tree is not None:
            self.widget_tree._populate_select_menu(menu.addMenu("Select"), widget)
        menu.addSeparator()
        for action in (
            self._copy_action,
            self._cut_action,
            self._paste_action,
            self._duplicate_action,
            self._delete_action,
        ):
            menu.addAction(action)

        arrange_menu = menu.addMenu("Arrange")
        for action in (
            self._align_left_action,
            self._align_right_action,
            self._align_top_action,
            self._align_bottom_action,
            self._align_hcenter_action,
            self._align_vcenter_action,
            self._distribute_h_action,
            self._distribute_v_action,
            self._bring_front_action,
            self._send_back_action,
            self._toggle_lock_action,
            self._toggle_hide_action,
        ):
            arrange_menu.addAction(action)
        arrange_enabled = any(
            action.isEnabled()
            for action in (
                self._align_left_action,
                self._align_right_action,
                self._align_top_action,
                self._align_bottom_action,
                self._align_hcenter_action,
                self._align_vcenter_action,
                self._distribute_h_action,
                self._distribute_v_action,
                self._bring_front_action,
                self._send_back_action,
                self._toggle_lock_action,
                self._toggle_hide_action,
            )
        )
        arrange_menu.setEnabled(arrange_enabled)
        arrange_hint = "Arrange selected widgets by alignment, order, lock, and visibility."
        if not arrange_enabled:
            arrange_hint = "Arrange unavailable: select at least 1 widget."
        arrange_menu.menuAction().setToolTip(arrange_hint)
        arrange_menu.menuAction().setStatusTip(arrange_hint)

        structure_menu = menu.addMenu("Structure")
        structure_menu.setToolTipsVisible(True)
        for action in (
            self._group_selection_action,
            self._ungroup_selection_action,
            self._move_into_container_action,
        ):
            structure_menu.addAction(action)
        structure_menu.addSeparator()
        for action in (
            self._lift_to_parent_action,
            self._move_up_action,
            self._move_down_action,
            self._move_top_action,
            self._move_bottom_action,
        ):
            structure_menu.addAction(action)
        structure_enabled = any(
            action.isEnabled()
            for action in (
                self._group_selection_action,
                self._ungroup_selection_action,
                self._move_into_container_action,
                self._lift_to_parent_action,
                self._move_up_action,
                self._move_down_action,
                self._move_top_action,
                self._move_bottom_action,
            )
        )
        structure_menu.setEnabled(structure_enabled)
        structure_hint = "Group, move, and reorder widgets relative to the current selection."
        if not structure_enabled:
            structure_hint = self._structure_action_state().blocked_reason
            if structure_hint:
                structure_hint = f"Structure unavailable: {structure_hint}"
        structure_menu.menuAction().setToolTip(structure_hint)
        structure_menu.menuAction().setStatusTip(structure_hint)
        return menu

    def _show_preview_context_menu(self, widget, global_pos):
        menu = self._build_preview_context_menu(widget)
        if menu is None:
            return
        menu.exec_(global_pos)

    # 鈹€鈹€ Widget selection / editing 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    def _normalized_selection(self, widgets=None, primary=None):
        ordered = []
        seen = set()
        for widget in widgets or []:
            if widget is None:
                continue
            ident = id(widget)
            if ident in seen:
                continue
            ordered.append(widget)
            seen.add(ident)
        if not ordered:
            return [], None
        if primary is None or all(widget is not primary for widget in ordered):
            primary = ordered[-1]
        return ordered, primary

    def _selection_matches(self, widgets=None, primary=None):
        normalized_widgets, normalized_primary = self._normalized_selection(widgets, primary=primary)
        current_widgets = self._selection_state.widgets
        if normalized_primary is not self._selection_state.primary:
            return False
        if len(normalized_widgets) != len(current_widgets):
            return False
        return all(current is incoming for current, incoming in zip(current_widgets, normalized_widgets))

    @staticmethod
    def _widget_log_label(widget):
        if widget is None:
            return "none"
        name = str(getattr(widget, "name", "") or "").strip()
        widget_type = str(getattr(widget, "widget_type", "") or "widget").strip()
        if name:
            return f"{name} ({widget_type})"
        return widget_type

    def _selection_log_summary(self, widgets=None, primary=None):
        normalized_widgets, normalized_primary = self._normalized_selection(widgets, primary=primary)
        if not normalized_widgets:
            return "none"
        labels = [self._widget_log_label(widget) for widget in normalized_widgets[:3]]
        summary = ", ".join(labels)
        remaining = len(normalized_widgets) - len(labels)
        if remaining > 0:
            summary = f"{summary}, +{remaining} more"
        if len(normalized_widgets) > 1 and normalized_primary is not None:
            summary = f"{summary}; primary={self._widget_log_label(normalized_primary)}"
        return summary

    @staticmethod
    def _worker_runtime_state(worker):
        if worker is None:
            return "none"
        try:
            return "running" if worker.isRunning() else "idle"
        except Exception:
            return "unknown"

    def _preview_runtime_snapshot(self):
        preview_mode = "idle"
        if getattr(self.preview_panel, "is_python_preview_active", None) and self.preview_panel.is_python_preview_active():
            preview_mode = "python"
        elif bool(getattr(self.preview_panel, "is_embedded", False)):
            preview_mode = "headless"

        preview_running = "n/a"
        exe_ready = "n/a"
        if self.compiler is not None:
            try:
                preview_running = "running" if self.compiler.is_preview_running() else "stopped"
            except Exception:
                preview_running = "unknown"
            try:
                exe_ready = "ready" if self.compiler.is_exe_ready() else "missing"
            except Exception:
                exe_ready = "unknown"

        queued_reasons = self._format_compile_reasons(self._queued_compile_reasons) if self._queued_compile_reasons else "none"
        return (
            f"preview={preview_mode}/{preview_running}, exe={exe_ready}, "
            f"compile_worker={self._worker_runtime_state(self._compile_worker)}, "
            f"precompile_worker={self._worker_runtime_state(self._precompile_worker)}, "
            f"auto_compile={self.auto_compile}, pending_compile={self._pending_compile}, "
            f"pending_rebuild={self._pending_rebuild}, queued={queued_reasons}, "
            f"retry_block={self._auto_compile_retry_block_reason or 'none'}, "
            f"rebuild_block={self._rebuild_retry_block_reason or 'none'}"
        )

    @staticmethod
    def _format_timed_step(elapsed_ms, skipped=False):
        if skipped:
            return "skip"
        return f"{elapsed_ms:.1f}ms"

    def _log_selection_change(self, source, widgets=None, primary=None, elapsed_ms=0.0, changed=True):
        summary = self._selection_log_summary(widgets, primary=primary)
        state = self._preview_runtime_snapshot()
        if changed:
            self.debug_panel.log_info(
                f"Selection applied ({source}): {summary}. No compile queued. "
                f"elapsed={elapsed_ms:.1f}ms | {state}"
            )
        else:
            self.debug_panel.log_info(
                f"Selection unchanged ({source}): {summary}. elapsed={elapsed_ms:.1f}ms | {state}"
            )

    def _install_debug_window_trace(self):
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

    def _remove_debug_window_trace(self):
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)

    @staticmethod
    def _selection_window_event_name(event_type):
        if event_type == QEvent.Show:
            return "show"
        if event_type == QEvent.Hide:
            return "hide"
        if event_type == QEvent.WindowStateChange:
            return "state"
        return str(int(event_type))

    def _is_traceable_top_level_widget(self, widget):
        if not isinstance(widget, QWidget) or widget is self:
            return False
        try:
            return bool(widget.isWindow())
        except RuntimeError:
            return False

    @staticmethod
    def _top_level_widget_kind(widget):
        try:
            flags = int(widget.windowFlags())
        except Exception:
            return "window"
        kinds = []
        if flags & int(Qt.Popup):
            kinds.append("popup")
        if flags & int(Qt.Tool):
            kinds.append("tool")
        if flags & int(Qt.Dialog):
            kinds.append("dialog")
        if flags & int(Qt.Sheet):
            kinds.append("sheet")
        if flags & int(Qt.ToolTip):
            kinds.append("tooltip")
        return "/".join(kinds) or "window"

    def _describe_top_level_widget(self, widget):
        object_name = ""
        title = ""
        visible = False
        try:
            object_name = widget.objectName() or "-"
            title = str(widget.windowTitle() or "")
            visible = bool(widget.isVisible())
            geometry = widget.frameGeometry()
            geom_text = f"{geometry.x()},{geometry.y()} {geometry.width()}x{geometry.height()}"
        except RuntimeError:
            object_name = object_name or "-"
            geom_text = "deleted"
        return (
            f"{type(widget).__name__}#{object_name} "
            f"kind={self._top_level_widget_kind(widget)} "
            f"title={title!r} visible={int(visible)} geom={geom_text}"
        )

    def _begin_selection_window_trace(self, source, widgets=None, primary=None):
        self._selection_window_trace_token += 1
        token = self._selection_window_trace_token
        self._selection_window_trace_source = str(source or "unknown")
        self._selection_window_trace_summary = self._selection_log_summary(widgets, primary=primary)
        self._selection_window_trace_events = 0
        self._selection_window_trace_deadline = time.monotonic() + 1.0
        QTimer.singleShot(1000, lambda token=token: self._finish_selection_window_trace(token))

    def _finish_selection_window_trace(self, token):
        if token != self._selection_window_trace_token or self._is_closing:
            return
        self._selection_window_trace_deadline = 0.0
        self.debug_panel.log_info(
            f"Selection window trace ({self._selection_window_trace_source}): "
            f"{self._selection_window_trace_events} Qt top-level event(s) for "
            f"{self._selection_window_trace_summary}"
        )

    def eventFilter(self, watched, event):
        if (
            not self._is_closing
            and self._selection_window_trace_deadline > 0.0
            and time.monotonic() <= self._selection_window_trace_deadline
            and event.type() in (QEvent.Show, QEvent.Hide, QEvent.WindowStateChange)
            and self._is_traceable_top_level_widget(watched)
        ):
            self._selection_window_trace_events += 1
            self.debug_panel.log_info(
                f"Selection window event "
                f"({self._selection_window_trace_source}/{self._selection_window_event_name(event.type())}): "
                f"{self._describe_top_level_widget(watched)}"
            )
        return super().eventFilter(watched, event)

    def _set_selection(self, widgets=None, primary=None, sync_tree=True, sync_preview=True):
        normalized_widgets, normalized_primary = self._normalized_selection(widgets, primary=primary)
        if self._selection_matches(normalized_widgets, primary=normalized_primary):
            self._selected_widget = self._selection_state.primary
            if sync_tree:
                self.widget_tree.set_selected_widgets(self._selection_state.widgets, self._selection_state.primary)
            if sync_preview:
                self.preview_panel.set_selection(self._selection_state.widgets, self._selection_state.primary)
            return False

        total_started = time.perf_counter()
        self._selection_state.set_widgets(normalized_widgets, primary=normalized_primary)
        self._selected_widget = self._selection_state.primary
        if hasattr(self, "_state_store"):
            selected_id = getattr(self._selected_widget, "name", None) if self._selected_widget is not None else None
            self._state_store.set_selection(selected_id)
        step_started = time.perf_counter()
        self.property_panel.set_selection(self._selection_state.widgets, self._selection_state.primary)
        property_ms = (time.perf_counter() - step_started) * 1000.0
        step_started = time.perf_counter()
        self.animations_panel.set_selection(self._selection_state.widgets, self._selection_state.primary)
        animations_ms = (time.perf_counter() - step_started) * 1000.0
        tree_ms = 0.0
        if sync_tree:
            step_started = time.perf_counter()
            self.widget_tree.set_selected_widgets(self._selection_state.widgets, self._selection_state.primary)
            tree_ms = (time.perf_counter() - step_started) * 1000.0
        preview_ms = 0.0
        if sync_preview:
            step_started = time.perf_counter()
            self.preview_panel.set_selection(self._selection_state.widgets, self._selection_state.primary)
            preview_ms = (time.perf_counter() - step_started) * 1000.0
        step_started = time.perf_counter()
        self._update_edit_actions()
        edit_actions_ms = (time.perf_counter() - step_started) * 1000.0
        step_started = time.perf_counter()
        self._update_diagnostics_panel()
        diagnostics_ms = (time.perf_counter() - step_started) * 1000.0
        step_started = time.perf_counter()
        self._show_selection_feedback()
        feedback_ms = (time.perf_counter() - step_started) * 1000.0
        step_started = time.perf_counter()
        self._update_widget_browser_target()
        browser_target_ms = (time.perf_counter() - step_started) * 1000.0
        browser_focus_ms = 0.0
        if hasattr(self, "widget_browser") and self._selection_state.primary is not None:
            step_started = time.perf_counter()
            self.widget_browser.select_widget_type(self._selection_state.primary.widget_type)
            browser_focus_ms = (time.perf_counter() - step_started) * 1000.0
        step_started = time.perf_counter()
        self._update_workspace_chips()
        workspace_ms = (time.perf_counter() - step_started) * 1000.0
        total_ms = (time.perf_counter() - total_started) * 1000.0
        self.debug_panel.log_info(
            "Selection pipeline: "
            f"properties={self._format_timed_step(property_ms)}, "
            f"animations={self._format_timed_step(animations_ms)}, "
            f"tree={self._format_timed_step(tree_ms, skipped=not sync_tree)}, "
            f"preview={self._format_timed_step(preview_ms, skipped=not sync_preview)}, "
            f"edit_actions={self._format_timed_step(edit_actions_ms)}, "
            f"diagnostics={self._format_timed_step(diagnostics_ms)}, "
            f"feedback={self._format_timed_step(feedback_ms)}, "
            f"browser_target={self._format_timed_step(browser_target_ms)}, "
            f"browser_focus={self._format_timed_step(browser_focus_ms, skipped=self._selection_state.primary is None)}, "
            f"workspace={self._format_timed_step(workspace_ms)}, "
            f"total={total_ms:.1f}ms"
        )
        return True

    def _clear_selection(self, sync_tree=True, sync_preview=True):
        self._set_selection([], primary=None, sync_tree=sync_tree, sync_preview=sync_preview)

    def _selected_widgets(self):
        widgets = self._selection_state.widgets
        if widgets:
            return widgets
        if self._selected_widget is not None:
            return [self._selected_widget]
        return []

    def _primary_selected_widget(self):
        return self._selection_state.primary or self._selected_widget

    def _selection_feedback_message(self):
        widgets = [widget for widget in self._selection_state.widgets if widget is not None]
        if not widgets:
            return ""

        structure_reason = self._structure_action_state(widgets).blocked_reason
        if structure_reason:
            structure_reason = structure_reason.rstrip(".")
        if len(widgets) == 1:
            widget = widgets[0]
            parts = []
            if getattr(widget, "designer_locked", False):
                parts.append("locked")
            if getattr(widget, "designer_hidden", False):
                parts.append("hidden")
            if self._parent_uses_layout(widget.parent):
                parts.append(f"layout-managed by {widget.parent.widget_type}")
            if not parts:
                if structure_reason:
                    return f"Selection note: {structure_reason}."
                return ""
            return f"Selection note: {widget.name} is " + ", ".join(parts) + "."

        issues = []
        locked_count = sum(1 for widget in widgets if getattr(widget, "designer_locked", False))
        hidden_count = sum(1 for widget in widgets if getattr(widget, "designer_hidden", False))
        layout_count = sum(1 for widget in widgets if self._parent_uses_layout(widget.parent))
        if locked_count:
            noun = "widget" if locked_count == 1 else "widgets"
            issues.append(f"{locked_count} locked {noun}")
        if hidden_count:
            noun = "widget" if hidden_count == 1 else "widgets"
            issues.append(f"{hidden_count} hidden {noun}")
        if layout_count:
            noun = "widget" if layout_count == 1 else "widgets"
            issues.append(f"{layout_count} layout-managed {noun}")
        if not issues:
            if structure_reason:
                return f"Selection note: {structure_reason}."
            return ""
        return "Selection note: current selection includes " + ", ".join(issues) + "."

    def _show_selection_feedback(self):
        message = self._selection_feedback_message()
        if message:
            self.statusBar().showMessage(message, 5000)

    def _existing_widget_names(self, existing_names=None):
        if existing_names is not None:
            return existing_names
        if not self._current_page:
            return set()
        return {widget.name for widget in self._current_page.get_all_widgets() if widget.name}

    def _make_unique_widget_name(self, base_name, existing_names=None):
        candidate = (base_name or "widget").strip().replace(" ", "_")
        if not candidate:
            candidate = "widget"

        existing_names = self._existing_widget_names(existing_names)
        if candidate not in existing_names:
            existing_names.add(candidate)
            return candidate

        match = re.match(r"^(.*?)(?:_(\d+))?$", candidate)
        stem = candidate
        suffix = 2
        if match:
            stem = match.group(1) or candidate
            if match.group(2):
                suffix = int(match.group(2)) + 1

        while f"{stem}_{suffix}" in existing_names:
            suffix += 1

        resolved = f"{stem}_{suffix}"
        existing_names.add(resolved)
        return resolved

    def _rename_widget_subtree_uniquely(self, widget, existing_names):
        if widget is None:
            return
        widget.name = self._make_unique_widget_name(widget.name or widget.widget_type, existing_names=existing_names)
        for child in widget.children:
            self._rename_widget_subtree_uniquely(child, existing_names)

    def _top_level_selected_widgets(self, widgets=None, exclude_root=True):
        widgets = [widget for widget in (widgets or self._selected_widgets()) if widget is not None]
        if not widgets:
            return []

        selected_ids = {id(widget) for widget in widgets}
        result = []
        root_widget = self._current_page.root_widget if self._current_page else None

        for widget in widgets:
            if exclude_root and widget is root_widget:
                continue
            parent = widget.parent
            skip = False
            while parent is not None:
                if id(parent) in selected_ids:
                    skip = True
                    break
                parent = parent.parent
            if not skip:
                result.append(widget)
        return result

    def _parent_uses_layout(self, parent):
        if parent is None:
            return False
        return WidgetModel._get_type_info(parent.widget_type).get("layout_func") is not None

    def _structure_project_context(self):
        if self._current_page is None:
            return None
        return getattr(self, "_page_shim", _PageProjectShim(self._current_page))

    def _structure_action_state(self, widgets=None):
        selection = self._selected_widgets() if widgets is None else widgets
        return describe_structure_actions(self._structure_project_context(), selection)

    def _structure_action_hint(self, base_text, enabled, blocked_reason=""):
        return self._action_hint(base_text, enabled, blocked_reason)

    def _structure_action_reason(self, state, reason_attr=""):
        if reason_attr:
            reason = getattr(state, reason_attr, "")
            if reason:
                return reason
        return state.blocked_reason

    def _move_into_choices(self, widgets=None):
        return available_move_targets(self._structure_project_context(), widgets or self._top_level_selected_widgets())

    def _choose_structure_target_choice(self, widgets):
        choices = self._move_into_choices(widgets)
        if not choices:
            self._show_selection_action_blocked("move into container", "no eligible target containers are available")
            return None

        labels = [choice.label for choice in choices]
        selected_label, ok = QInputDialog.getItem(
            self,
            "Move Into Container",
            "Target container:",
            labels,
            0,
            False,
        )
        if not ok or not selected_label:
            return None

        for choice in choices:
            if choice.label == selected_label:
                return choice
        return None

    def _apply_structure_result(self, result):
        if not result.changed:
            if result.message:
                self.statusBar().showMessage(result.message, 4000)
            return False

        self.widget_tree.rebuild_tree()
        self._set_selection(result.widgets, primary=result.primary, sync_tree=True, sync_preview=True)
        self._record_page_state_change(source=result.source)
        if result.message:
            self.statusBar().showMessage(result.message, 5000)
        return True

    def _shared_selection_parent(self, widgets=None):
        widgets = [widget for widget in (widgets or []) if widget is not None]
        if not widgets:
            return None
        parent = widgets[0].parent
        if parent is None:
            return None
        for widget in widgets[1:]:
            if widget.parent is not parent:
                return None
        if self._parent_uses_layout(parent):
            return None
        return parent

    def _shared_layout_managed_parent(self, widgets=None):
        widgets = [widget for widget in (widgets or []) if widget is not None]
        if not widgets:
            return None
        parent = widgets[0].parent
        if parent is None or not self._parent_uses_layout(parent):
            return None
        for widget in widgets[1:]:
            if widget.parent is not parent:
                return None
        return parent

    def _default_paste_parent(self):
        if not self._current_page:
            return None

        primary = self._primary_selected_widget()
        if primary is not None:
            if primary.is_container:
                return primary
            if primary.parent is not None and primary.parent.is_container:
                return primary.parent

        root_widget = self._current_page.root_widget
        if root_widget is not None and root_widget.is_container:
            return root_widget
        return None

    def _selected_widget_payload(self):
        widgets = self._top_level_selected_widgets()
        if not widgets:
            return None
        return {
            "widgets": [copy.deepcopy(widget.to_dict()) for widget in widgets],
        }

    def _locked_widget_summary(self, count):
        noun = "widget" if count == 1 else "widgets"
        return f"{count} locked {noun}"

    def _show_selection_action_blocked(self, action, reason):
        self.statusBar().showMessage(f"Cannot {action}: {reason}.", 4000)

    def _deletable_selected_widgets(self):
        widgets = self._top_level_selected_widgets()
        deletable = [widget for widget in widgets if not getattr(widget, "designer_locked", False)]
        locked_count = len(widgets) - len(deletable)
        return deletable, locked_count

    def _paste_widget_payload(self, payload):
        if not self._current_page or not payload:
            return []

        parent = self._default_paste_parent()
        if parent is None:
            return []

        widgets_data = payload.get("widgets", [])
        if not widgets_data:
            return []

        self._paste_serial += 1
        offset = self.preview_panel.grid_size() or 12
        offset *= self._paste_serial
        existing_names = self._existing_widget_names()
        use_offset = not self._parent_uses_layout(parent)

        pasted_widgets = []
        for widget_data in widgets_data:
            widget = WidgetModel.from_dict(copy.deepcopy(widget_data))
            self._rename_widget_subtree_uniquely(widget, existing_names)
            if use_offset:
                widget.x += offset
                widget.y += offset
                widget.display_x = widget.x
                widget.display_y = widget.y
            parent.add_child(widget)
            pasted_widgets.append(widget)

        self.widget_tree.rebuild_tree()
        self._set_selection(pasted_widgets, primary=pasted_widgets[-1], sync_tree=True, sync_preview=True)
        self._record_page_state_change(source="clipboard paste")
        return pasted_widgets

    def _copy_selection(self):
        payload = self._selected_widget_payload()
        if not payload:
            return
        self._clipboard_payload = payload
        self._paste_serial = 0
        self._update_edit_actions()
        self.statusBar().showMessage(f"Copied {len(payload['widgets'])} widget(s)", 3000)

    def _cut_selection(self):
        deletable_widgets, locked_count = self._deletable_selected_widgets()
        if not deletable_widgets:
            if locked_count:
                self.statusBar().showMessage(f"Cannot cut selection: {self._locked_widget_summary(locked_count)}.", 4000)
            return
        payload = {
            "widgets": [copy.deepcopy(widget.to_dict()) for widget in deletable_widgets],
        }
        if not payload:
            return
        self._clipboard_payload = payload
        self._paste_serial = 0
        deleted_count, skipped_locked = self._delete_selection()
        if deleted_count:
            message = f"Cut {deleted_count} widget(s)"
            if skipped_locked:
                message += f"; skipped {self._locked_widget_summary(skipped_locked)}"
            self.statusBar().showMessage(message, 3000)

    def _paste_selection(self):
        pasted_widgets = self._paste_widget_payload(self._clipboard_payload)
        if pasted_widgets:
            self.statusBar().showMessage(f"Pasted {len(pasted_widgets)} widget(s)", 3000)

    def _duplicate_selection(self):
        payload = self._selected_widget_payload()
        if not payload:
            return
        duplicated_widgets = self._paste_widget_payload(payload)
        if duplicated_widgets:
            self.statusBar().showMessage(f"Duplicated {len(duplicated_widgets)} widget(s)", 3000)

    def _delete_selection(self):
        widgets, locked_count = self._deletable_selected_widgets()
        if not widgets:
            if locked_count:
                self.statusBar().showMessage(f"Cannot delete selection: {self._locked_widget_summary(locked_count)}.", 4000)
            return 0, locked_count

        for widget in widgets:
            if widget.parent is not None:
                widget.parent.remove_child(widget)

        self.widget_tree.rebuild_tree()
        self._clear_selection(sync_tree=True, sync_preview=True)
        self._record_page_state_change(source="widget delete")
        message = f"Deleted {len(widgets)} widget(s)"
        if locked_count:
            message += f"; skipped {self._locked_widget_summary(locked_count)}"
        self.statusBar().showMessage(message, 3000)
        return len(widgets), locked_count

    def _align_selection(self, mode):
        selected_widgets = self._top_level_selected_widgets()
        widgets = [widget for widget in selected_widgets if not getattr(widget, "designer_locked", False)]
        if len(widgets) < 2:
            if len(selected_widgets) >= 2:
                self._show_selection_action_blocked("align selection", "locked widgets leave fewer than 2 editable widgets")
            return
        layout_parent = self._shared_layout_managed_parent(widgets)
        if layout_parent is not None:
            self._show_selection_action_blocked(
                "align selection",
                f"selected widgets are layout-managed by the same {layout_parent.widget_type} parent; reorder them instead",
            )
            return
        if self._shared_selection_parent(widgets) is None:
            self._show_selection_action_blocked("align selection", "selected widgets do not share the same free-position parent")
            return

        primary = self._primary_selected_widget()
        if primary not in widgets:
            primary = widgets[-1]

        for widget in widgets:
            if widget is primary:
                continue
            if mode == "left":
                widget.x = primary.x
            elif mode == "right":
                widget.x = primary.x + primary.width - widget.width
            elif mode == "top":
                widget.y = primary.y
            elif mode == "bottom":
                widget.y = primary.y + primary.height - widget.height
            elif mode == "hcenter":
                widget.x = primary.x + (primary.width - widget.width) // 2
            elif mode == "vcenter":
                widget.y = primary.y + (primary.height - widget.height) // 2
            widget.display_x = widget.x
            widget.display_y = widget.y

        self._record_page_state_change(source=f"align {mode}")

    def _distribute_selection(self, axis):
        selected_widgets = self._top_level_selected_widgets()
        widgets = [widget for widget in selected_widgets if not getattr(widget, "designer_locked", False)]
        if len(widgets) < 3:
            if len(selected_widgets) >= 3:
                self._show_selection_action_blocked("distribute selection", "locked widgets leave fewer than 3 editable widgets")
            return
        layout_parent = self._shared_layout_managed_parent(widgets)
        if layout_parent is not None:
            self._show_selection_action_blocked(
                "distribute selection",
                f"selected widgets are layout-managed by the same {layout_parent.widget_type} parent; reorder them instead",
            )
            return
        if self._shared_selection_parent(widgets) is None:
            self._show_selection_action_blocked("distribute selection", "selected widgets do not share the same free-position parent")
            return

        key_name = "x" if axis == "horizontal" else "y"
        size_name = "width" if axis == "horizontal" else "height"
        widgets = sorted(widgets, key=lambda widget: getattr(widget, key_name))
        first = widgets[0]
        last = widgets[-1]
        inner_widgets = widgets[1:-1]
        if not inner_widgets:
            return

        start_edge = getattr(first, key_name) + getattr(first, size_name)
        end_edge = getattr(last, key_name)
        available = end_edge - start_edge
        used = sum(getattr(widget, size_name) for widget in inner_widgets)
        gap_count = len(widgets) - 1
        if gap_count <= 0:
            return
        gap = (available - used) // gap_count if available > used else 0

        cursor = start_edge + gap
        for widget in inner_widgets:
            setattr(widget, key_name, cursor)
            widget.display_x = widget.x
            widget.display_y = widget.y
            cursor += getattr(widget, size_name) + gap

        self._record_page_state_change(source=f"distribute {axis}")

    def _group_selection(self):
        self._apply_structure_result(group_selection(self._structure_project_context(), self._top_level_selected_widgets()))

    def _ungroup_selection(self):
        self._apply_structure_result(ungroup_selection(self._structure_project_context(), self._top_level_selected_widgets()))

    def _move_selection_into_container(self):
        widgets = self._top_level_selected_widgets()
        target_choice = self._choose_structure_target_choice(widgets)
        if target_choice is None:
            return
        self._apply_structure_result(move_into_container(self._structure_project_context(), widgets, target_choice.widget))

    def _lift_selection_to_parent(self):
        self._apply_structure_result(lift_to_parent(self._structure_project_context(), self._top_level_selected_widgets()))

    def _move_selection_up(self):
        self._apply_structure_result(move_selection_by_step(self._structure_project_context(), self._top_level_selected_widgets(), -1))

    def _move_selection_down(self):
        self._apply_structure_result(move_selection_by_step(self._structure_project_context(), self._top_level_selected_widgets(), 1))

    def _move_selection_to_top(self):
        self._apply_structure_result(move_selection_to_edge(self._structure_project_context(), self._top_level_selected_widgets(), "top"))

    def _move_selection_to_bottom(self):
        self._apply_structure_result(move_selection_to_edge(self._structure_project_context(), self._top_level_selected_widgets(), "bottom"))

    def _move_selection_to_front(self):
        selected_widgets = self._top_level_selected_widgets()
        widgets = [widget for widget in selected_widgets if not getattr(widget, "designer_locked", False)]
        if not widgets:
            if selected_widgets:
                self._show_selection_action_blocked("bring to front", "all selected widgets are locked")
            return
        grouped = {}
        for widget in widgets:
            if widget.parent is None:
                continue
            grouped.setdefault(id(widget.parent), (widget.parent, []) )[1].append(widget)

        for parent, children in grouped.values():
            ordered = [child for child in parent.children if child in children]
            remaining = [child for child in parent.children if child not in children]
            parent.children = remaining + ordered

        self.widget_tree.rebuild_tree()
        self._set_selection(widgets, primary=self._primary_selected_widget(), sync_tree=True, sync_preview=True)
        self._record_page_state_change(source="bring to front")

    def _move_selection_to_back(self):
        selected_widgets = self._top_level_selected_widgets()
        widgets = [widget for widget in selected_widgets if not getattr(widget, "designer_locked", False)]
        if not widgets:
            if selected_widgets:
                self._show_selection_action_blocked("send to back", "all selected widgets are locked")
            return
        grouped = {}
        for widget in widgets:
            if widget.parent is None:
                continue
            grouped.setdefault(id(widget.parent), (widget.parent, []) )[1].append(widget)

        for parent, children in grouped.values():
            ordered = [child for child in parent.children if child in children]
            remaining = [child for child in parent.children if child not in children]
            parent.children = ordered + remaining

        self.widget_tree.rebuild_tree()
        self._set_selection(widgets, primary=self._primary_selected_widget(), sync_tree=True, sync_preview=True)
        self._record_page_state_change(source="send to back")

    def _set_selection_flag(self, field_name):
        widgets = [widget for widget in self._selected_widgets() if self._current_page and widget is not self._current_page.root_widget]
        if not widgets:
            return
        new_value = not all(bool(getattr(widget, field_name, False)) for widget in widgets)
        for widget in widgets:
            setattr(widget, field_name, new_value)
        primary = self._primary_selected_widget()
        self.widget_tree.rebuild_tree()
        self._set_selection(widgets, primary=primary, sync_tree=True, sync_preview=True)
        label = "designer lock" if field_name == "designer_locked" else "designer visibility"
        self._record_page_state_change(trigger_compile=False, source=label)

    def _toggle_selection_locked(self):
        self._set_selection_flag("designer_locked")

    def _toggle_selection_hidden(self):
        self._set_selection_flag("designer_hidden")

    def _update_edit_actions(self):
        if not hasattr(self, "_copy_action"):
            return

        selected_widgets = self._top_level_selected_widgets()
        selectable_widgets = [widget for widget in selected_widgets if not getattr(widget, "designer_locked", False)]
        has_selection = bool(selected_widgets)
        has_deletable_selection = bool(selectable_widgets)
        has_project = self._current_page is not None
        can_select_all = bool(self._focused_text_input_widget()) or bool(self._select_all_page_widgets())
        can_paste = has_project and self._clipboard_payload is not None and self._default_paste_parent() is not None
        can_align = len(selectable_widgets) >= 2 and self._shared_selection_parent(selectable_widgets) is not None
        can_distribute = len(selectable_widgets) >= 3 and self._shared_selection_parent(selectable_widgets) is not None
        structure_state = self._structure_action_state()

        self._select_all_action.setEnabled(can_select_all)
        self._copy_action.setEnabled(has_selection)
        self._cut_action.setEnabled(has_deletable_selection)
        self._paste_action.setEnabled(can_paste)
        self._duplicate_action.setEnabled(has_selection)
        self._delete_action.setEnabled(has_deletable_selection)

        self._align_left_action.setEnabled(can_align)
        self._align_right_action.setEnabled(can_align)
        self._align_top_action.setEnabled(can_align)
        self._align_bottom_action.setEnabled(can_align)
        self._align_hcenter_action.setEnabled(can_align)
        self._align_vcenter_action.setEnabled(can_align)
        self._distribute_h_action.setEnabled(can_distribute)
        self._distribute_v_action.setEnabled(can_distribute)
        self._bring_front_action.setEnabled(has_selection)
        self._send_back_action.setEnabled(has_selection)
        self._toggle_lock_action.setEnabled(has_selection)
        self._toggle_hide_action.setEnabled(has_selection)
        align_blocked_reason = self._align_action_blocked_reason(selected_widgets, selectable_widgets)
        distribute_blocked_reason = self._distribute_action_blocked_reason(selected_widgets, selectable_widgets)
        for action, base_text in (
            (
                self._align_left_action,
                "Align the current selection to the left edge of the primary widget.",
            ),
            (
                self._align_right_action,
                "Align the current selection to the right edge of the primary widget.",
            ),
            (
                self._align_top_action,
                "Align the current selection to the top edge of the primary widget.",
            ),
            (
                self._align_bottom_action,
                "Align the current selection to the bottom edge of the primary widget.",
            ),
            (
                self._align_hcenter_action,
                "Align the current selection to the horizontal center of the primary widget.",
            ),
            (
                self._align_vcenter_action,
                "Align the current selection to the vertical center of the primary widget.",
            ),
        ):
            self._apply_action_hint(
                action,
                self._action_hint(base_text, action.isEnabled(), align_blocked_reason),
            )
        for action, base_text in (
            (
                self._distribute_h_action,
                "Distribute the current selection evenly across the horizontal axis.",
            ),
            (
                self._distribute_v_action,
                "Distribute the current selection evenly across the vertical axis.",
            ),
        ):
            self._apply_action_hint(
                action,
                self._action_hint(base_text, action.isEnabled(), distribute_blocked_reason),
            )
        self._apply_action_hint(
            self._bring_front_action,
            self._editable_selection_action_hint(
                "Bring the current selection to the front of its parent stack.",
                selected_widgets,
                selectable_widgets,
                "Locked widgets remain in place.",
            ),
        )
        self._apply_action_hint(
            self._send_back_action,
            self._editable_selection_action_hint(
                "Send the current selection to the back of its parent stack.",
                selected_widgets,
                selectable_widgets,
                "Locked widgets remain in place.",
            ),
        )
        self._apply_action_hint(
            self._toggle_lock_action,
            self._action_hint(
                "Toggle the designer lock state for the current selection.",
                self._toggle_lock_action.isEnabled(),
                "select at least 1 widget",
            ),
        )
        self._apply_action_hint(
            self._toggle_hide_action,
            self._action_hint(
                "Toggle the designer visibility state for the current selection.",
                self._toggle_hide_action.isEnabled(),
                "select at least 1 widget",
            ),
        )
        self._apply_action_hint(
            self._select_all_action,
            self._action_hint(
                "Select all visible widgets on the current page or all text in the focused editor (Ctrl+A).",
                self._select_all_action.isEnabled(),
                "focus a text field or open a page with selectable widgets"
                if self._current_page is None
                else "page has no selectable widgets",
            ),
        )
        self._apply_action_hint(
            self._cut_action,
            self._action_hint(
                "Cut the current selection (Ctrl+X).",
                self._cut_action.isEnabled(),
                "select at least 1 widget" if not has_selection else "locked widgets cannot be cut",
            ),
        )
        self._apply_action_hint(
            self._duplicate_action,
            self._action_hint(
                "Duplicate the current selection (Ctrl+D).",
                self._duplicate_action.isEnabled(),
                "select at least 1 widget",
            ),
        )
        self._apply_action_hint(
            self._delete_action,
            self._action_hint(
                "Delete the current selection (Del).",
                self._delete_action.isEnabled(),
                "select at least 1 widget" if not has_selection else "locked widgets cannot be deleted",
            ),
        )

        self._group_selection_action.setEnabled(structure_state.can_group)
        self._ungroup_selection_action.setEnabled(structure_state.can_ungroup)
        self._move_into_container_action.setEnabled(structure_state.can_move_into)
        self._lift_to_parent_action.setEnabled(structure_state.can_lift)
        self._move_up_action.setEnabled(structure_state.can_move_up)
        self._move_down_action.setEnabled(structure_state.can_move_down)
        self._move_top_action.setEnabled(structure_state.can_move_top)
        self._move_bottom_action.setEnabled(structure_state.can_move_bottom)
        for action, (base_text, reason_attr) in self._structure_action_hints.items():
            hint = self._structure_action_hint(base_text, action.isEnabled(), self._structure_action_reason(structure_state, reason_attr))
            self._apply_action_hint(action, hint)
        self._update_toolbar_action_metadata()
        self._update_arrange_menu_metadata()
        self._update_structure_menu_metadata()
        self._update_edit_menu_metadata()

    def _on_tree_selection_changed(self, widgets, primary):
        selection_started = time.perf_counter()
        self._begin_selection_window_trace("tree", widgets, primary=primary)
        self.debug_panel.log_info(
            f"Selection event (tree): {self._selection_log_summary(widgets, primary=primary)} | "
            f"{self._preview_runtime_snapshot()}"
        )
        if self._set_selection(widgets, primary=primary, sync_tree=False, sync_preview=True) is not False:
            elapsed_ms = (time.perf_counter() - selection_started) * 1000.0
            self._log_selection_change("tree", widgets, primary=primary, elapsed_ms=elapsed_ms, changed=True)
            self._focus_properties_for_selection()
        else:
            elapsed_ms = (time.perf_counter() - selection_started) * 1000.0
            self._log_selection_change("tree", widgets, primary=primary, elapsed_ms=elapsed_ms, changed=False)

    def _on_preview_selection_changed(self, widgets, primary):
        selection_started = time.perf_counter()
        self._begin_selection_window_trace("preview", widgets, primary=primary)
        self.debug_panel.log_info(
            f"Selection event (preview): {self._selection_log_summary(widgets, primary=primary)} | "
            f"{self._preview_runtime_snapshot()}"
        )
        if self._set_selection(widgets, primary=primary, sync_tree=True, sync_preview=False) is not False:
            elapsed_ms = (time.perf_counter() - selection_started) * 1000.0
            self._log_selection_change("preview", widgets, primary=primary, elapsed_ms=elapsed_ms, changed=True)
            self._focus_properties_for_selection()
        else:
            elapsed_ms = (time.perf_counter() - selection_started) * 1000.0
            self._log_selection_change("preview", widgets, primary=primary, elapsed_ms=elapsed_ms, changed=False)

    def _on_widget_selected(self, widget):
        """Widget selected from tree panel."""
        widgets = [widget] if widget is not None else []
        selection_started = time.perf_counter()
        self._begin_selection_window_trace("tree", widgets, primary=widget)
        self.debug_panel.log_info(
            f"Selection event (tree): {self._selection_log_summary(widgets, primary=widget)} | "
            f"{self._preview_runtime_snapshot()}"
        )
        if self._set_selection(widgets, primary=widget, sync_tree=False, sync_preview=True) is not False:
            elapsed_ms = (time.perf_counter() - selection_started) * 1000.0
            self._log_selection_change("tree", widgets, primary=widget, elapsed_ms=elapsed_ms, changed=True)
            self._focus_properties_for_selection()
        else:
            elapsed_ms = (time.perf_counter() - selection_started) * 1000.0
            self._log_selection_change("tree", widgets, primary=widget, elapsed_ms=elapsed_ms, changed=False)

    def _on_preview_widget_selected(self, widget):
        """Widget selected from preview panel overlay."""
        widgets = [widget] if widget is not None else []
        selection_started = time.perf_counter()
        self._begin_selection_window_trace("preview", widgets, primary=widget)
        self.debug_panel.log_info(
            f"Selection event (preview): {self._selection_log_summary(widgets, primary=widget)} | "
            f"{self._preview_runtime_snapshot()}"
        )
        if self._set_selection(widgets, primary=widget, sync_tree=True, sync_preview=False) is not False:
            elapsed_ms = (time.perf_counter() - selection_started) * 1000.0
            self._log_selection_change("preview", widgets, primary=widget, elapsed_ms=elapsed_ms, changed=True)
            self._focus_properties_for_selection()
        else:
            elapsed_ms = (time.perf_counter() - selection_started) * 1000.0
            self._log_selection_change("preview", widgets, primary=widget, elapsed_ms=elapsed_ms, changed=False)

    def _focus_properties_for_selection(self):
        if self._selection_state.primary is None:
            return
        if hasattr(self, "_inspector_tabs") and self._inspector_tabs.currentIndex() != 0:
            self._show_inspector_tab("properties")

    def _refresh_drag_geometry_if_due(self, widget):
        if widget != self._selection_state.primary:
            return
        now = time.monotonic()
        if (
            self._canvas_drag_batch_active
            and self._last_drag_geometry_refresh_ts > 0.0
            and (now - self._last_drag_geometry_refresh_ts) < (1.0 / 30.0)
        ):
            return
        self._last_drag_geometry_refresh_ts = now
        self.property_panel.refresh_live_geometry(
            self._selection_state.widgets,
            self._selection_state.primary,
        )

    def _on_widget_moved(self, widget, new_x, new_y):
        """Widget dragged on preview overlay."""
        self._active_batch_source = "canvas move"
        self._refresh_drag_geometry_if_due(widget)
        if self._canvas_drag_batch_active:
            self._canvas_drag_dirty = True
            return
        self._record_page_state_change(
            update_preview=False,
            trigger_compile=True,
            sync_xml=False,
            refresh_resources=False,
            source="canvas move",
        )

    def _on_widget_resized(self, widget, new_width, new_height):
        """Widget resized on preview overlay."""
        self._active_batch_source = "canvas resize"
        self._refresh_drag_geometry_if_due(widget)
        if self._canvas_drag_batch_active:
            self._canvas_drag_dirty = True
            return
        self._record_page_state_change(
            update_preview=False,
            trigger_compile=True,
            sync_xml=False,
            refresh_resources=False,
            source="canvas resize",
        )

    def _on_widget_reordered(self, widget, new_index):
        """Widget reordered within a layout container."""
        self.widget_tree.rebuild_tree()
        self.widget_tree.set_selected_widgets(self._selection_state.widgets, self._selection_state.primary)
        self._on_model_changed(source="layout reorder")

    def _on_tree_changed(self, source="widget tree change"):
        """Widget tree structure changed (add/delete/reorder)."""
        widgets = self.widget_tree.selected_widgets()
        primary = self.widget_tree._get_selected_widget()
        self._set_selection(widgets, primary=primary, sync_tree=False, sync_preview=True)
        self._on_model_changed(source=source or "widget tree change")

    def _on_widget_tree_feedback_message(self, message):
        if message:
            self.statusBar().showMessage(message, 5000)

    def _on_property_changed(self):
        """A property value was changed in the property panel."""
        primary = self._selection_state.primary
        patch = {}
        if primary is not None:
            patch = {
                "x": int(getattr(primary, "x", 0)),
                "y": int(getattr(primary, "y", 0)),
                "width": int(getattr(primary, "width", 0)),
                "height": int(getattr(primary, "height", 0)),
                "properties": dict(getattr(primary, "properties", {}) or {}),
            }
        self._state_store.set_node_patch(getattr(primary, "name", None) if primary is not None else None, patch)
        self.widget_tree.rebuild_tree()
        self.widget_tree.set_selected_widgets(self._selection_state.widgets, self._selection_state.primary)
        self.animations_panel.refresh()
        self._on_model_changed(source="property edit")

    def _on_property_validation_message(self, message):
        if message:
            self.statusBar().showMessage(message, 5000)

    def _on_model_changed(self, source=""):
        """Common handler: model changed 鈫?record snapshot + update preview + XML + recompile."""
        self._record_page_state_change(source=source)

    def _format_page_change_message(self, source):
        if not source or self._current_page is None:
            return ""
        return f"Changed {self._current_page.name}: {source}."

    def _record_page_state_change(
        self,
        update_preview=True,
        trigger_compile=True,
        sync_xml=True,
        refresh_resources=True,
        source="",
    ):
        """Record the current page snapshot and refresh dependent UI state."""
        if self._current_page and not self._undoing:
            xml = self._current_page.to_xml_string()
            stack = self._undo_manager.get_stack(self._current_page.name)
            stack.push(xml, label=source or "property edit")
        if update_preview:
            self._update_preview_overlay()
        if sync_xml:
            self._sync_xml_to_editors()
        if refresh_resources:
            self._update_resource_usage_panel()
        if trigger_compile:
            self._trigger_compile(reason=source or "model change")
        self._update_undo_actions()
        self._update_window_title()
        message = self._format_page_change_message(source)
        if message and not self._undoing:
            self.statusBar().showMessage(message, 3000)

    # 鈹€鈹€ Undo / Redo 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    def _undo(self):
        if not self._current_page:
            return
        stack = self._undo_manager.get_stack(self._current_page.name)
        xml = stack.undo()
        if xml is not None:
            self._apply_xml_snapshot(xml)

    def _redo(self):
        if not self._current_page:
            return
        stack = self._undo_manager.get_stack(self._current_page.name)
        xml = stack.redo()
        if xml is not None:
            self._apply_xml_snapshot(xml)

    def _apply_xml_snapshot(self, xml):
        """Restore page state from an XML snapshot without recording a new undo entry."""
        self._undoing = True
        try:
            images_dir = self._get_eguiproject_images_dir()
            src_dir = images_dir if images_dir else None
            new_page = Page.from_xml_string(xml, self._current_page.file_path, src_dir=src_dir)
            self._apply_page_state(self._current_page, new_page)
            # Refresh UI
            self._page_shim = _PageProjectShim(self._current_page)
            self.widget_tree.set_project(self._page_shim)
            self.page_fields_panel.set_page(self._current_page)
            self.page_timers_panel.set_page(self._current_page)
            self._clear_selection(sync_tree=True, sync_preview=True)
            self._update_preview_overlay()
            self._apply_page_mockup()
            self._sync_xml_to_editors()
            self._update_resource_usage_panel()
            self._trigger_compile(reason="undo/redo")
        finally:
            self._undoing = False
        self._update_undo_actions()
        self._update_window_title()

    def _update_undo_actions(self):
        """Enable/disable Undo and Redo menu actions based on stack state."""
        if self._current_page:
            stack = self._undo_manager.get_stack(self._current_page.name)
            self._undo_action.setEnabled(stack.can_undo())
            self._redo_action.setEnabled(stack.can_redo())
        else:
            self._undo_action.setEnabled(False)
            self._redo_action.setEnabled(False)
        self._update_toolbar_action_metadata()
        self._update_edit_menu_metadata()

    def _on_drag_started(self):
        """Preview drag/resize began 鈥?start undo batch."""
        if self._current_page:
            self._active_batch_source = ""
            self._canvas_drag_batch_active = True
            self._canvas_drag_dirty = False
            self._last_drag_geometry_refresh_ts = 0.0
            stack = self._undo_manager.get_stack(self._current_page.name)
            stack.begin_batch()

    def _on_drag_finished(self):
        """Preview drag/resize ended 鈥?commit undo batch."""
        if self._current_page:
            xml = self._current_page.to_xml_string()
            stack = self._undo_manager.get_stack(self._current_page.name)
            should_finalize_canvas_refresh = self._active_batch_source in {"canvas move", "canvas resize"}
            stack.end_batch(xml, label=self._active_batch_source or "canvas drag")
            if should_finalize_canvas_refresh and self._canvas_drag_dirty:
                self.property_panel.refresh_live_geometry(
                    self._selection_state.widgets,
                    self._selection_state.primary,
                )
                self._update_preview_overlay()
                self._sync_xml_to_editors()
                self._update_resource_usage_panel()
                self._trigger_compile(reason=self._active_batch_source or "canvas drag")
                message = self._format_page_change_message(self._active_batch_source)
                if message and not self._undoing:
                    self.statusBar().showMessage(message, 3000)
            self._active_batch_source = ""
            self._canvas_drag_batch_active = False
            self._canvas_drag_dirty = False
            self._last_drag_geometry_refresh_ts = 0.0
            self._update_undo_actions()
            self._update_window_title()

    # 鈹€鈹€ XML bidirectional sync 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    def _sync_xml_to_editors(self):
        """Push current page XML to the code editors (Design 鈫?Code)."""
        if not self._current_page:
            return
        try:
            xml_text = self._current_page.to_xml_string()
            self.editor_tabs.set_xml_text(xml_text)
        except Exception:
            pass

    def _on_xml_changed(self, xml_text):
        """User edited XML in the code editor (Code 鈫?Design)."""
        if not self._current_page:
            return
        try:
            images_dir = self._get_eguiproject_images_dir()
            src_dir = images_dir if images_dir else None
            new_page = Page.from_xml_string(xml_text, self._current_page.file_path, src_dir=src_dir)
            self._apply_page_state(self._current_page, new_page)

            if not self._undoing:
                stack = self._undo_manager.get_stack(self._current_page.name)
                stack.push(xml_text, label="xml edit")

            # Refresh tree and preview (without re-syncing XML back)
            self._page_shim = _PageProjectShim(self._current_page)
            self.widget_tree.set_project(self._page_shim)
            self._clear_selection(sync_tree=True, sync_preview=True)
            self._update_preview_overlay()
            self._apply_page_mockup()
            self._update_resource_usage_panel()
            self._trigger_compile(reason="xml edit")
            self._update_undo_actions()
            self._update_window_title()
            if not self._undoing:
                self.statusBar().showMessage(f"Changed {self._current_page.name}: xml edit.", 3000)
        except Exception:
            # XML parse error 鈥?ignore until user fixes it
            pass

    # 鈹€鈹€ Preview / Compile 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    def _apply_page_state(self, target_page, source_page):
        """Copy all serializable page state from source to target."""
        target_page.root_widget = source_page.root_widget
        target_page.user_fields = source_page.user_fields
        target_page.timers = source_page.timers
        target_page.mockup_image_path = source_page.mockup_image_path
        target_page.mockup_image_visible = source_page.mockup_image_visible
        target_page.mockup_image_opacity = source_page.mockup_image_opacity

    def _update_preview_overlay(self):
        """Update the preview overlay with current page widgets."""
        if self._current_page:
            compute_page_layout(self._current_page)
            widgets = self._current_page.get_all_widgets()
            self.preview_panel.set_widgets(widgets)
            self.preview_panel.set_selection(self._selection_state.widgets, self._selection_state.primary)
            self.page_navigator.refresh_thumbnail(self._current_page.name)

            if self.compiler is None or not self.compiler.can_build() or self.preview_panel.is_python_preview_active():
                reason = ""
                if self.compiler is None:
                    reason = "SDK unavailable, compile preview disabled"
                elif not self.compiler.can_build():
                    reason = self.compiler.get_build_error()
                self._refresh_python_preview(reason)

    def _set_overlay_mode(self, mode):
        self.preview_panel.set_overlay_mode(mode)
        # Persist layout config
        self._config.overlay_mode = mode
        self._config.save()
        # Sync menu checkmarks
        act = self._overlay_mode_actions.get(mode)
        if act:
            act.setChecked(True)
        self._update_preview_appearance_action_metadata()

    def _flip_overlay_layout(self):
        """Swap preview/overlay and persist the flipped state."""
        self.preview_panel.flip_layout()
        self._config.overlay_flipped = self.preview_panel._flipped
        self._config.save()
        self._update_preview_appearance_action_metadata()

    def _set_show_grid(self, show):
        self.preview_panel.set_show_grid(show)
        self._config.show_grid = bool(show)
        self._config.save()
        self._update_preview_grid_and_mockup_action_metadata()

    def _set_grid_size(self, size):
        self.preview_panel.set_grid_size(size)
        self._config.grid_size = int(size)
        self._config.save()
        action = self._grid_size_actions.get(int(size))
        if action is not None:
            action.setChecked(True)
        self._update_preview_grid_and_mockup_action_metadata()

    def _toggle_auto_compile(self, enabled):
        self.auto_compile = enabled
        if not enabled:
            self._compile_timer.stop()
            self._pending_compile = False
            self._queued_compile_reasons = []
        self._update_build_menu_metadata()

    def _normalize_compile_reason(self, reason=""):
        normalized = str(reason or "").strip()
        return normalized or "unspecified change"

    def _append_compile_reason(self, reason=""):
        normalized = self._normalize_compile_reason(reason)
        if normalized in self._queued_compile_reasons:
            return False, normalized
        self._queued_compile_reasons.append(normalized)
        return True, normalized

    def _consume_compile_reasons(self, fallback=""):
        reasons = list(self._queued_compile_reasons)
        self._queued_compile_reasons = []
        if reasons:
            return reasons
        return [self._normalize_compile_reason(fallback)]

    def _peek_compile_reasons(self, fallback=""):
        if self._queued_compile_reasons:
            return list(self._queued_compile_reasons)
        return [self._normalize_compile_reason(fallback)]

    def _format_compile_reasons(self, reasons):
        ordered = []
        seen = set()
        for reason in reasons or []:
            normalized = self._normalize_compile_reason(reason)
            if normalized in seen:
                continue
            ordered.append(normalized)
            seen.add(normalized)
        if not ordered:
            return self._normalize_compile_reason("")
        return "; ".join(ordered)

    def _clear_queued_compile_reasons(self):
        self._queued_compile_reasons = []

    def _trigger_compile(self, reason=""):
        """Trigger a debounced compile."""
        normalized_reason = self._normalize_compile_reason(reason)
        if self._is_closing:
            self.debug_panel.log_info(f"Auto compile trigger ignored during shutdown: {normalized_reason}")
            self._clear_queued_compile_reasons()
            return
        if not self.auto_compile:
            self.debug_panel.log_info(f"Auto compile trigger ignored: {normalized_reason} (auto compile disabled)")
            self._clear_queued_compile_reasons()
            return
        if self._is_auto_compile_retry_blocked():
            self.debug_panel.log_info(
                f"Auto compile trigger blocked: {normalized_reason} (retry blocked: {self._auto_compile_retry_block_reason})"
            )
            self._clear_queued_compile_reasons()
            return
        if self.compiler is None:
            self.debug_panel.log_info(
                f"Auto compile trigger blocked: {normalized_reason} (SDK unavailable, compile preview disabled)"
            )
            self._clear_queued_compile_reasons()
            self._refresh_python_preview("SDK unavailable, compile preview disabled")
            return
        preview_unavailable_reason = self._effective_preview_unavailable_reason()
        if preview_unavailable_reason:
            self.debug_panel.log_info(
                f"Auto compile trigger blocked: {normalized_reason} (preview unavailable: {preview_unavailable_reason})"
            )
            self._clear_queued_compile_reasons()
            self._switch_to_python_preview(preview_unavailable_reason)
            return
        should_append_reason = bool(str(reason or "").strip()) or not self._queued_compile_reasons
        if should_append_reason:
            added, merged_reason = self._append_compile_reason(reason)
            if added:
                if self._compile_timer.isActive():
                    self.debug_panel.log_info(f"Auto compile trigger merged: {merged_reason}")
                else:
                    self.debug_panel.log_info(f"Auto compile trigger queued: {merged_reason}")
        self._compile_timer.start()

    def _flush_pending_xml(self):
        """Flush any pending XML edits from the editor into the model."""
        if self.editor_tabs._parse_timer.isActive():
            self.editor_tabs._parse_timer.stop()
            self.editor_tabs._emit_xml_changed()

    def _do_compile_and_run(self):
        """Execute compile and run cycle (async, multi-file)."""
        self._clear_auto_compile_retry_block()
        reset_probe = getattr(self.compiler, "reset_preview_build_probe", None)
        if callable(reset_probe):
            reset_probe()
        self._start_compile_cycle(force_rebuild=False, reason_fallback="manual compile")

    def _run_auto_compile_cycle(self):
        if not self.auto_compile:
            return
        if self._is_auto_compile_retry_blocked():
            return
        preview_unavailable_reason = self._effective_preview_unavailable_reason()
        if preview_unavailable_reason:
            self._clear_queued_compile_reasons()
            self._switch_to_python_preview(preview_unavailable_reason)
            return
        self._start_compile_cycle(force_rebuild=False, reason_fallback="auto compile")

    def _do_rebuild_egui_project(self):
        """Run a clean rebuild for the current EGUI project and restart preview."""
        self._clear_auto_compile_retry_block()
        reset_probe = getattr(self.compiler, "reset_preview_build_probe", None)
        if callable(reset_probe):
            reset_probe()
        self._start_compile_cycle(force_rebuild=True, reason_fallback="manual clean rebuild")

    def _clean_all_confirmation_text(self):
        preserved_lines = "\n".join(f"  - {item}" for item in DESIGNER_SOURCE_PRESERVE_SUMMARY)
        deleted_lines = "\n".join(f"  - {item}" for item in DESIGNER_RECONSTRUCT_DELETE_SUMMARY)
        rerun_limitation = str(self._effective_rebuild_unavailable_reason() or "").strip()
        rerun_note = ""
        if rerun_limitation:
            rerun_note = (
                "\n\nCurrent preview rerun limitation:\n"
                f"  {rerun_limitation}\n"
                "Clean All will still reconstruct project files, but preview rerun will be skipped until this is resolved."
            )
        return (
            "This will permanently delete most project-side generated files and business/code outputs, "
            "then rebuild them from preserved Designer source state.\n\n"
            "Preserved:\n"
            f"{preserved_lines}\n\n"
            "Deleted and reconstructed:\n"
            f"{deleted_lines}\n\n"
            "Unsaved Designer changes will be saved first.\n"
            f"{rerun_note}\n"
            "Project directory:\n"
            f"{self._project_dir}"
        )

    def _do_clean_all_and_reconstruct(self):
        """Delete reconstructible outputs, rebuild from designer state, and rerun preview when available."""
        if self.project is None:
            return
        clean_all_recovery_reason = self._clean_all_recovery_unavailable_reason()
        if clean_all_recovery_reason:
            preview_unavailable_reason = str(self._effective_preview_unavailable_reason() or "").strip()
            _status_message, guidance_message = self._compile_failure_feedback(preview_unavailable_reason)
            self.debug_panel.log_info(f"Clean All skipped: {clean_all_recovery_reason}")
            if guidance_message:
                self.debug_panel.log_info(guidance_message)
            self.statusBar().showMessage(f"Clean All skipped: {clean_all_recovery_reason}", 5000)
            return
        if self._compile_worker is not None and self._compile_worker.isRunning():
            self.statusBar().showMessage("Wait for the current compile to finish before Clean All.", 5000)
            return
        if self._precompile_worker is not None and self._precompile_worker.isRunning():
            self.statusBar().showMessage("Wait for the current background compile to finish before Clean All.", 5000)
            return
        if not self._project_dir and not self._save_project():
            return

        reply = QMessageBox.warning(
            self,
            "Clean All and Reconstruct",
            self._clean_all_confirmation_text(),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self._flush_pending_xml()

        try:
            self._persist_designer_state_only(self._project_dir)
            self._bump_async_generation()
            self._shutdown_async_activity(wait_ms=500)
            self._cleanup_compiler(stop_exe=True)
            report = clean_project_for_reconstruct(self._project_dir)
            files = self._save_project_files(self._project_dir, reset_scaffold=True)
            if self._has_valid_sdk_root():
                self._ensure_resources_generated()
        except Exception as exc:
            self._update_diagnostics_panel()
            self.debug_panel.log_error(f"Clean all failed: {exc}")
            self._show_bottom_panel("Diagnostics")
            QMessageBox.warning(self, "Clean All Failed", f"Failed to reconstruct the project:\n{exc}")
            self.statusBar().showMessage(f"Clean all failed: {exc}", 5000)
            return

        self._recreate_compiler()
        preview_unavailable_reason = self._sync_preview_after_compiler_recreation(
            clear_when_available=True,
            preload_preview_error=True,
            probe_environmental_recovery=True,
        )
        preview_unavailable_reason = preview_unavailable_reason or self._effective_preview_unavailable_reason()
        rebuild_unavailable_reason = self._effective_rebuild_unavailable_reason()
        self._undo_manager.mark_all_saved()
        self._refresh_project_watch_snapshot()
        self._update_window_title()
        self._update_compile_availability()

        summary = (
            f"Cleaned {report.removed_files} file(s) and {report.removed_dirs} director"
            f"{'y' if report.removed_dirs == 1 else 'ies'}; reconstructed {len(files)} code file(s)."
        )
        self.debug_panel.log_action("Running destructive project cleanup and reconstruction...")
        self.debug_panel.log_info(summary)
        if preview_unavailable_reason:
            status_message = self._status_message_with_editing_only_mode(summary, preview_unavailable_reason)
        elif rebuild_unavailable_reason:
            status_message = f"{summary} | Preview rerun skipped: {rebuild_unavailable_reason}"
            self.debug_panel.log_info(f"Preview rerun skipped after reconstruction: {rebuild_unavailable_reason}")
        else:
            status_message = summary
        self.statusBar().showMessage(status_message, 5000)

        if self.compiler is not None and self.compiler.can_build() and not rebuild_unavailable_reason:
            self._clear_auto_compile_retry_block()
            self._start_compile_cycle(force_rebuild=True, reason_fallback="clean all reconstruct")

    @staticmethod
    def _compile_failure_summary(message, default):
        lines = [line.strip() for line in str(message or "").splitlines() if line.strip()]
        if not lines:
            return default
        if lines[0].lower() in {"compilation failed:", "rebuild failed:"} and len(lines) > 1:
            return lines[1]
        return lines[0]

    @staticmethod
    def _missing_make_target_name(message):
        match = re.search(r"No rule to make target ['`\"]?([^'`\"\r\n]+)", str(message or ""), flags=re.IGNORECASE)
        if not match:
            return ""
        return match.group(1).rstrip("'.:;!, ")

    @classmethod
    def _compile_failure_feedback(cls, message, *, force_rebuild=False, rebuild_unavailable_reason=""):
        lowered = str(message or "").lower()
        missing_target = cls._missing_make_target_name(message).lower()
        rebuild_missing_target = cls._missing_make_target_name(rebuild_unavailable_reason).lower()

        if missing_target in {"main.exe", "main"}:
            return (
                f"Preview build target '{missing_target}' is unavailable, switched to Python fallback.",
                f"Build system does not define the required '{missing_target}' preview target. Verify the SDK/designer "
                "Makefile setup. Build > Clean All && Reconstruct cannot recover missing build targets.",
            )
        if "preview build target unavailable" in lowered:
            return (
                "Preview build target is unavailable, switched to Python fallback.",
                "Build system does not define a compatible preview build target. Verify the SDK/designer Makefile "
                "setup. Build > Clean All && Reconstruct cannot recover missing build targets.",
            )
        if "preview build target probe timed out" in lowered:
            return (
                "Preview build target probe timed out, switched to Python fallback.",
                "Designer could not verify the preview build target before timeout. Check the SDK/designer "
                "Makefile setup and local toolchain responsiveness. Build > Clean All && Reconstruct cannot "
                "recover probe timeouts caused by the environment.",
            )
        if lowered.startswith("preview build unavailable"):
            return (
                "Preview build is unavailable, switched to Python fallback.",
                "Designer could not verify a usable preview build target. Check the SDK/designer Makefile setup "
                "and toolchain state. Build > Clean All && Reconstruct cannot recover missing preview build "
                "availability caused by the environment.",
            )
        if missing_target == "clean":
            return (
                "Clean rebuild target 'clean' is unavailable, switched to Python fallback.",
                "Build system does not define the 'clean' target. Verify the SDK/designer Makefile setup. "
                "Regular Compile remains available, Rebuild EGUI Project is disabled, and Clean All && "
                "Reconstruct will rebuild project files without rerunning the preview until the build "
                "environment changes.",
            )
        if "make not found" in lowered:
            return (
                "Build tool 'make' is unavailable, switched to Python fallback.",
                "The build tool 'make' was not found in PATH. Install or configure the required toolchain. "
                "Build > Clean All && Reconstruct cannot recover missing build tools.",
            )
        if force_rebuild:
            return (
                "EGUI clean rebuild failed, switched to Python fallback (see Debug Output)",
                "Clean rebuild did not recover the preview. If project-side generated files are corrupted, "
                "try Build > Clean All && Reconstruct.",
            )
        if rebuild_missing_target == "clean":
            return (
                "EXE build failed, switched to Python fallback. Rebuild-based recovery is unavailable until the build environment changes.",
                "Build failed. The build system does not define the 'clean' target required by Rebuild EGUI Project. "
                "Verify the SDK/designer Makefile setup before relying on rebuild-based recovery. Clean All && "
                "Reconstruct can still rebuild project files, but preview rerun will be skipped until the build "
                "environment changes.",
            )
        return (
            "EXE build failed, switched to Python fallback. Use Build > Rebuild EGUI Project first, "
            "or Clean All && Reconstruct if the project files are corrupted.",
            "Build failed. Use Build > Rebuild EGUI Project first. If that still fails, try "
            "Build > Clean All && Reconstruct to rebuild from Designer source state.",
        )

    def _ensure_preview_build_available(self, *, force_rebuild=False, auto=False):
        compiler = self.compiler
        if compiler is None:
            return True
        ensure_available = getattr(compiler, "ensure_preview_build_available", None)
        if not callable(ensure_available):
            return True
        if ensure_available(force=bool(force_rebuild)):
            return True

        reason_getter = getattr(compiler, "get_preview_build_error", None)
        reason = reason_getter() if callable(reason_getter) else ""
        reason = reason or "Preview build unavailable"
        self._last_runtime_error_text = reason
        self._block_auto_compile_retry(reason)
        status_message, guidance_message = self._compile_failure_feedback(reason, force_rebuild=force_rebuild)
        self.debug_panel.log_error(reason if auto else f"Preview build unavailable: {reason}")
        if guidance_message:
            self.debug_panel.log_info(guidance_message)
        self._switch_to_python_preview(reason)
        if status_message:
            self.statusBar().showMessage(status_message, 5000)
        self._update_compile_availability()
        return False

    def _start_compile_cycle(self, *, force_rebuild=False, reason_fallback=""):
        """Execute compile or clean rebuild asynchronously."""
        compile_reason_fallback = reason_fallback or ("manual clean rebuild" if force_rebuild else "manual compile")
        if not self.project:
            self._clear_queued_compile_reasons()
            return
        if self._is_closing:
            self._clear_queued_compile_reasons()
            return
        compile_reason_text = self._format_compile_reasons(self._peek_compile_reasons(compile_reason_fallback))
        self.debug_panel.log_info(f"Compile request received: {compile_reason_text} | {self._preview_runtime_snapshot()}")
        if self.compiler is None or not self.compiler.can_build():
            self._clear_queued_compile_reasons()
            reason = "SDK unavailable, compile preview disabled"
            if self.compiler is not None and self.compiler.get_build_error():
                reason = self.compiler.get_build_error()
            self._last_runtime_error_text = reason
            self._switch_to_python_preview(reason)
            self.statusBar().showMessage("Compile preview unavailable")
            self._update_workspace_chips()
            return
        if not self._ensure_preview_build_available(force_rebuild=force_rebuild):
            self._clear_queued_compile_reasons()
            return
        if self._compile_worker is not None and self._compile_worker.isRunning():
            if force_rebuild:
                self._pending_rebuild = True
                self._pending_compile = False
                self.statusBar().showMessage("Queued clean rebuild after current compile finishes...")
                self.debug_panel.log_info("Queued clean rebuild after current compile finishes...")
            elif not self._pending_rebuild:
                self._pending_compile = True
            return
        # Wait for precompile to finish to avoid conflicts
        if self._precompile_worker is not None and self._precompile_worker.isRunning():
            if force_rebuild:
                self._pending_rebuild = True
                self._pending_compile = False
                self.statusBar().showMessage("Waiting for background compile before clean rebuild...")
                self.debug_panel.log_info("Waiting for background compile to finish before clean rebuild...")
            else:
                self.statusBar().showMessage("Waiting for background compile...")
                self.debug_panel.log_info("Waiting for background compile to finish...")
                if not self._pending_rebuild:
                    self._pending_compile = True
            return

        self._pending_compile = False
        if force_rebuild:
            self._pending_rebuild = False

        # Always use the latest editor content
        self._flush_pending_xml()
        self._update_diagnostics_panel()
        if not self._ensure_codegen_preflight(
            "Rebuild preview" if force_rebuild else "Compile preview",
            show_dialog=False,
            switch_to_python_preview=True,
        ):
            self.debug_panel.log_info(f"Compile request blocked: {compile_reason_text}")
            self._clear_queued_compile_reasons()
            return

        compile_reason_text = self._format_compile_reasons(self._consume_compile_reasons(compile_reason_fallback))
        action_label = "Rebuilding..." if force_rebuild else "Compiling..."
        self.statusBar().showMessage(action_label)
        self.preview_panel.status_label.setText(action_label)

        if force_rebuild:
            self.debug_panel.log_info("Preview stop requested for clean rebuild before restart")
            self.preview_panel.stop_rendering()
            if self.compiler is not None:
                self.debug_panel.log_info("Compiler stop_exe requested for clean rebuild before restart")
                self.compiler.stop_exe()

        self.debug_panel.log_action("Starting clean rebuild and run..." if force_rebuild else "Starting compile and run...")
        self.debug_panel.log_info(f"Compile trigger: {compile_reason_text}")
        self.debug_panel.log_info(f"Generating code for {len(self.project.pages)} page(s)")

        # Generate resource config + resource C files if needed
        self._ensure_resources_generated()

        preview_output_dir = self.compiler.app_dir if self.compiler is not None else (self._project_dir or "")

        # Temporarily set startup_page to current page for preview
        original_startup = self.project.startup_page
        if self._current_page:
            self.project.startup_page = self._current_page.name
        try:
            try:
                prepared = prepare_project_codegen_outputs(
                    self.project,
                    preview_output_dir,
                    backup=False,
                    before_prepare=self._apply_pending_page_rename_outputs,
                    cleanup_legacy=True,
                )
                files = prepared.files
                all_generated_files = prepared.all_generated_files
            except Exception as exc:
                failure_summary = self._compile_failure_summary(
                    exc,
                    "Rebuild failed" if force_rebuild else "Compile failed",
                )
                self._block_auto_compile_retry(failure_summary)
                self._last_runtime_error_text = failure_summary
                self.debug_panel.log_error(f"Code generation failed: {exc}")
                self._show_bottom_panel("Debug Output")
                self._switch_to_python_preview(failure_summary)
                self.preview_panel.status_label.setText(failure_summary)
                self.statusBar().showMessage(failure_summary, 5000)
                self._update_debug_rebuild_action(show=self._should_offer_debug_rebuild_action(failure_summary))
                self._update_compile_availability()
                return
        finally:
            # Restore the persisted startup page even when preview generation fails.
            self.project.startup_page = original_startup

        self.debug_panel.log_info(f"Generated {len(files)} file(s): {', '.join(files.keys())}")
        make_prefix = "make -B -j" if force_rebuild else "make -j"
        target_name_getter = getattr(self.compiler, "get_preview_make_target_name", None)
        target_name = target_name_getter() if callable(target_name_getter) else "main.exe"
        self.debug_panel.log_cmd(
            f"{make_prefix} {target_name} APP={self.app_name} PORT=designer "
            f"EGUI_APP_ROOT_PATH={self.compiler.app_root_arg} COMPILE_DEBUG= COMPILE_OPT_LEVEL=-O0"
        )

        generation = self._async_generation
        worker = self.compiler.compile_and_run_async(
            code=None,
            callback=lambda success, message, old_process: self._on_compile_finished(
                worker, generation, force_rebuild, success, message, old_process
            ),
            files_dict=files,
            generated_relpaths=list(all_generated_files.keys()),
            force_rebuild=force_rebuild,
        )
        self._compile_worker = worker
        # Connect log signal for detailed timing info
        worker.log.connect(lambda message, msg_type: self._on_compile_log(worker, generation, message, msg_type))

    def _on_compile_log(self, worker, generation, message, msg_type):
        """Handle log messages from compile worker."""
        if self._is_closing or generation != self._async_generation or worker is not self._compile_worker:
            return
        self.debug_panel.log(message, msg_type)

    def _on_compile_finished(self, worker, generation, force_rebuild, success, message, old_process):
        """Callback when background compilation completes."""
        del old_process
        self._cleanup_worker_ref(worker, "_compile_worker")
        if self._is_closing or generation != self._async_generation:
            return
        # Update debug panel with compile output
        self.debug_panel.log_compile_output(success, message)

        # Check if we need to recompile due to pending changes
        pending_rebuild = bool(self._pending_rebuild)
        pending_compile = bool(self._pending_compile) and not pending_rebuild
        self._pending_rebuild = False
        self._pending_compile = False

        if success:
            self._last_runtime_error_text = ""
            if self._resume_pending_external_reload_if_ready(generation):
                return
            self.statusBar().showMessage(message)
            self.preview_panel.status_label.setText(f"OK - {message}")
            # Start headless frame rendering
            self.debug_panel.log_info("Preview start_rendering requested after successful compile")
            self.preview_panel.start_rendering(self.compiler)
            self.debug_panel.log_action(
                "Headless preview restarted after clean rebuild" if force_rebuild else "Headless preview started"
            )
            self.debug_panel.log_info(f"Preview runtime after compile success | {self._preview_runtime_snapshot()}")
            self._update_debug_rebuild_action(show=False)
            if pending_rebuild:
                self._start_compile_cycle(force_rebuild=True, reason_fallback="pending clean rebuild")
            elif pending_compile:
                self._trigger_compile(
                    reason="" if self._queued_compile_reasons else "pending compile after previous run"
                )
        else:
            failure_summary = self._compile_failure_summary(
                message,
                "Rebuild failed" if force_rebuild else "Compile failed",
            )
            if force_rebuild and self._rebuild_retry_block_reason_is_environmental(failure_summary):
                self._block_rebuild_retry(failure_summary)
            else:
                self._block_auto_compile_retry(failure_summary)
            self._last_runtime_error_text = failure_summary
            status_message, guidance_message = self._compile_failure_feedback(
                message,
                force_rebuild=force_rebuild,
                rebuild_unavailable_reason=self._rebuild_retry_blocked_reason(),
            )
            self.statusBar().showMessage(status_message)
            if guidance_message:
                self.debug_panel.log_info(guidance_message)
            if self.compiler is not None:
                self.debug_panel.log_info("Compiler stop_exe requested after compile failure")
                self.compiler.stop_exe()
            self._switch_to_python_preview(failure_summary)
            # Show debug dock on compile failure
            self._show_bottom_panel("Debug Output")
            self._update_debug_rebuild_action(show=self._should_offer_debug_rebuild_action(failure_summary))
        self._update_compile_availability()
        if not success and self._resume_pending_external_reload_if_ready(generation):
            return

    def _on_preview_runtime_failed(self, reason):
        if self._is_closing:
            return
        self._handle_preview_failure(reason or "Headless preview stopped responding")

    def _handle_preview_failure(self, reason: str) -> None:
        self._last_runtime_error_text = reason
        if self.compiler is not None:
            self.debug_panel.log_info("Compiler stop_exe requested after preview runtime failure")
            self.compiler.stop_exe()
        self.debug_panel.log_error(reason)
        self._show_bottom_panel("Debug Output")
        self._switch_to_python_preview(reason)
        self._renderer_manager.switch("v1", fallback="v1")
        self._update_compile_availability()
        self._resume_pending_external_reload_if_ready(self._async_generation)

    def _try_embed_exe(self):
        """Legacy - headless rendering replaces window embedding."""
        pass

    def _stop_exe(self):
        self._stop_background_timers()
        self.debug_panel.log_info("Manual preview stop requested")
        self.preview_panel.stop_rendering()
        self._last_runtime_error_text = ""
        if self.compiler is not None:
            self.debug_panel.log_info("Compiler stop_exe requested by manual preview stop")
            self.compiler.stop_exe()
        self.preview_panel.status_label.setText("Preview stopped")
        self._update_compile_availability()

    def closeEvent(self, event):
        self._is_closing = True
        if self.project and self._has_unsaved_changes():
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                self._unsaved_changes_prompt_text("close"),
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save
            )
            if reply == QMessageBox.Cancel:
                self._is_closing = False
                event.ignore()
                return
            elif reply == QMessageBox.Save:
                if not self._save_project():
                    self._is_closing = False
                    event.ignore()
                    return

        # Save config
        self._config.auto_compile = self.auto_compile
        self._config.overlay_mode = self.preview_panel._mode
        self._config.overlay_flipped = self.preview_panel._flipped
        self._save_window_state_to_config()
        self._save_diagnostics_view_state()
        if self._has_valid_sdk_root():
            self._config.sdk_root = self.project_root
        self._config.save()

        self._bump_async_generation()
        self._shutdown_async_activity(wait_ms=500)
        self.widget_tree.shutdown()
        self._remove_debug_window_trace()
        self._cleanup_compiler()
        event.accept()


class _PageProjectShim:
    """Shim that makes a Page look like a Project for WidgetTreePanel.

    WidgetTreePanel expects ``project.root_widgets`` to be a list.
    This adapter provides that interface for a single page.
    """

    def __init__(self, page):
        self._page = page

    @property
    def root_widgets(self):
        if self._page and self._page.root_widget:
            return [self._page.root_widget]
        return []
