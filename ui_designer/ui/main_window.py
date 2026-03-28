"""Main window for EmbeddedGUI Designer 鈥?Android Studio-like IDE layout.

All panels (Project Explorer, Widget Tree, Properties) are QDockWidgets
that can be freely dragged, docked, and rearranged.  Page switching uses
a qfluentwidgets.TabBar strip above the central editor area.

Layout (default):
    鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?
    鈹?Project  鈹? [page tabs bar]       鈹? Widget Tree  鈹?
    鈹?Explorer 鈹? Design/Split/Code     鈹傗攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?
    鈹?         鈹?                       鈹? Properties   鈹?
    鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹粹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹粹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?
"""

import copy
import json
import os
import re
import shutil
import subprocess

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QTabWidget, QToolButton, QPushButton, QFrame,
    QAction, QActionGroup, QFileDialog, QStatusBar,
    QMessageBox, QScrollArea, QDockWidget, QMenu,
    QApplication, QDialog, QStackedWidget, QToolBar, QInputDialog, QProgressDialog, QLabel,
    QLineEdit, QPlainTextEdit, QTextEdit,
)
from PyQt5.QtCore import Qt, QTimer, QSize, QByteArray, QSignalBlocker
from PyQt5.QtGui import QIcon

from qfluentwidgets import PrimaryPushButton, PushButton, TabBar, TabCloseButtonDisplayMode

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
from .release_dialogs import ReleaseBuildDialog, ReleaseHistoryDialog, ReleaseProfilesDialog
from .repo_health_dialog import RepositoryHealthDialog
from .widget_browser import WidgetBrowserPanel
from .status_center_panel import StatusCenterPanel
from ..model.widget_model import WidgetModel
from ..model.project import Project
from ..model.page import Page
from ..model.build_metadata import format_sdk_binding_label
from ..model.config import get_config
from ..model.release import ReleaseRequest
from ..model.sdk_bootstrap import (
    AUTO_DOWNLOAD_STRATEGY_TEXT,
    default_sdk_install_dir,
    describe_auto_download_plan,
    describe_sdk_source,
    ensure_sdk_downloaded,
)
from ..model.workspace import (
    infer_sdk_root_from_project_dir,
    is_valid_sdk_root,
    normalize_path,
    resolve_available_sdk_root,
    resolve_sdk_root_candidate,
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
    generate_all_files,
    generate_all_files_preserved,
    generate_page_user_source,
    generate_uicode,
    render_page_callback_stub,
)
from ..generator.user_code_preserver import compute_source_hash, embed_source_hash, read_existing_file
from ..generator.resource_config_generator import ResourceConfigGenerator
from ..engine.compiler import CompilerEngine
from ..engine.release_engine import collect_release_diagnostics, latest_release_entry, load_release_history, release_history_path, release_project
from ..engine.layout_engine import compute_layout, compute_page_layout
from ..utils.scaffold import make_app_build_mk_content, make_app_config_h_content, make_empty_resource_config_content
from .theme import apply_theme
from .widgets.page_navigator import PageNavigator, PAGE_TEMPLATES


WORKSPACE_LAYOUT_VERSION = 2


_DETACHED_WORKERS = set()
_DESIGNER_REPO_ROOT = normalize_path(os.path.join(os.path.dirname(__file__), "..", ".."))


def _release_detached_worker(worker):
    _DETACHED_WORKERS.discard(worker)
    try:
        worker.deleteLater()
    except Exception:
        pass


def _release_sdk_summary(sdk) -> str:
    if not isinstance(sdk, dict):
        return "unknown"
    source_kind = str(sdk.get("source_kind") or "").strip()
    revision = str(sdk.get("revision") or sdk.get("commit_short") or sdk.get("commit") or "").strip()
    if sdk.get("dirty") and revision:
        revision += " (dirty)"
    if source_kind and revision:
        return f"{source_kind} {revision}"
    if source_kind:
        return source_kind
    if revision:
        return revision
    return "unknown"


def _latest_release_summary(entry):
    if not isinstance(entry, dict) or not entry:
        return "No release history available"
    build_id = str(entry.get("build_id") or entry.get("created_at_utc") or "unknown-build").strip()
    profile_id = str(entry.get("profile_id") or "unknown-profile").strip()
    status = str(entry.get("status") or "").strip()
    if not status:
        if "success" in entry:
            status = "success" if bool(entry.get("success")) else "failed"
        else:
            status = "unknown"
    return f"Latest release: {build_id} | {profile_id} | {status} | sdk {_release_sdk_summary(entry.get('sdk'))}"


def _release_action_tooltip(action_label, latest_entry, *, path="", unavailable_label="") -> str:
    lines = [action_label, "", _latest_release_summary(latest_entry)]
    if path:
        lines.extend(["", path])
    elif unavailable_label:
        lines.extend(["", unavailable_label])
    return "\n".join(lines)


def delete_page_generated_files(project_dir, page_name):
    """Delete the three generated C files for a removed page.

    Removes {page_name}.h, {page_name}_layout.c, {page_name}.c from
    project_dir so they are no longer picked up by EGUI_CODE_SRC.
    Silently ignores missing files and permission errors.

    Only deletes files that resolve to paths strictly inside project_dir
    (path traversal via page_name like '../other_project/file' is blocked).
    """
    if not page_name or not project_dir:
        return
    project_real = os.path.realpath(project_dir)
    for suffix in (f"{page_name}.h", f"{page_name}_layout.c", f"{page_name}.c"):
        fpath = os.path.realpath(os.path.join(project_dir, suffix))
        # Safety check: only files directly inside project_real
        if not fpath.startswith(project_real + os.sep):
            continue
        try:
            if os.path.isfile(fpath):
                os.remove(fpath)
        except OSError:
            pass


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
        self._compile_timer.timeout.connect(self._do_compile_and_run)

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
        self._undo_manager = UndoManager()
        self._undoing = False  # True during undo/redo to suppress snapshot recording
        self._active_batch_source = ""
        self._project_watch_snapshot = {}
        self._external_reload_pending = False
        self._last_runtime_error_text = ""

        self._project_watch_timer = QTimer(self)
        self._project_watch_timer.setInterval(1000)
        self._project_watch_timer.timeout.connect(self._poll_project_files)

        self._init_ui()
        self._init_menus()
        self._init_toolbar()
        self._restore_diagnostics_view_state()
        self._apply_saved_window_state()
        # Start with welcome page (don't auto-create project)
        self._show_welcome_page()

    # 鈹€鈹€ UI Construction 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    def _init_ui(self):
        self.setWindowTitle("EmbeddedGUI Designer")
        self.setMinimumSize(1100, 700)
        self.resize(1400, 800)

        self._central_stack = QStackedWidget()

        self._welcome_page = WelcomePage()
        self._welcome_page.open_recent.connect(self._open_recent_project)
        self._welcome_page.new_project.connect(self._new_project)
        self._welcome_page.open_project.connect(self._open_project)
        self._welcome_page.open_app.connect(self._open_app_dialog)
        self._welcome_page.set_sdk_root.connect(self._set_sdk_root)
        self._welcome_page.download_sdk.connect(self._download_sdk)
        self._central_stack.addWidget(self._welcome_page)

        editor_container = QWidget()
        self._editor_container = editor_container
        editor_container.setObjectName("workspace_shell")
        editor_layout = QVBoxLayout(editor_container)
        editor_layout.setContentsMargins(12, 12, 12, 12)
        editor_layout.setSpacing(12)

        self._toolbar_host = QFrame()
        self._toolbar_host.setObjectName("workspace_command_bar")
        self._toolbar_host_layout = QHBoxLayout(self._toolbar_host)
        self._toolbar_host_layout.setContentsMargins(10, 8, 10, 8)
        self._toolbar_host_layout.setSpacing(10)
        editor_layout.addWidget(self._toolbar_host)

        self.project_dock = ProjectExplorerDock(self)
        self.project_dock.setObjectName("project_explorer_dock")
        self.project_dock.setMinimumWidth(220)
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
        right_scroll.setMinimumWidth(300)
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
        self.status_center_panel = StatusCenterPanel()
        self.status_center_panel.setObjectName("workspace_status_center_panel")

        self._project_workspace = ProjectWorkspacePanel(self.project_dock, self.page_navigator)
        self._project_workspace.setObjectName("project_workspace_panel")
        saved_workspace_state = self._config.workspace_state if isinstance(self._config.workspace_state, dict) else {}
        self._project_workspace.set_view(saved_workspace_state.get("project_workspace_view", ProjectWorkspacePanel.VIEW_LIST))

        self._left_panel_stack = QStackedWidget()
        self._left_panel_pages = {
            "project": self._project_workspace,
            "structure": self.widget_tree,
            "widgets": self.widget_browser,
            "assets": self.res_panel,
            "status": self.status_center_panel,
        }
        for panel in self._left_panel_pages.values():
            self._left_panel_stack.addWidget(panel)

        self._workspace_nav_buttons = {}
        self._workspace_nav_frame = QFrame()
        self._workspace_nav_frame.setObjectName("workspace_nav_rail")
        nav_layout = QVBoxLayout(self._workspace_nav_frame)
        nav_layout.setContentsMargins(8, 10, 8, 10)
        nav_layout.setSpacing(8)
        for key, label, icon_key in (
            ("project", "Project", "project"),
            ("structure", "Structure", "structure"),
            ("widgets", "Components", "widgets"),
            ("assets", "Assets", "assets"),
            ("status", "Status", "diagnostics"),
        ):
            button = self._create_workspace_nav_button(label, icon_key, key)
            self._workspace_nav_buttons[key] = button
            nav_layout.addWidget(button)
        nav_layout.addStretch()

        self._left_shell = QWidget()
        self._left_shell.setObjectName("workspace_left_shell")
        left_shell_layout = QHBoxLayout(self._left_shell)
        left_shell_layout.setContentsMargins(0, 0, 0, 0)
        left_shell_layout.setSpacing(12)
        left_shell_layout.addWidget(self._workspace_nav_frame, 0)
        left_shell_layout.addWidget(self._left_panel_stack, 1)

        center_shell = QWidget()
        self._center_shell = center_shell
        center_shell.setObjectName("workspace_center_shell")
        center_layout = QVBoxLayout(center_shell)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(12)

        self.page_tab_bar = self._create_page_tab_bar()
        center_layout.addWidget(self.page_tab_bar)

        self.preview_panel = PreviewPanel(screen_width=240, screen_height=320)
        self.preview_panel.set_show_grid(self._config.show_grid)
        self.preview_panel.set_grid_size(self._config.grid_size)
        self.preview_panel.overlay.zoom_changed.connect(lambda _factor: self._update_preview_appearance_action_metadata())
        self.editor_tabs = EditorTabs(self.preview_panel, show_mode_switch=False)
        center_layout.addWidget(self.editor_tabs, 1)

        self._page_tools_tabs = QTabWidget()
        self._page_tools_tabs.addTab(self.page_fields_panel, make_icon("page"), "Fields")
        self._page_tools_tabs.addTab(self.page_timers_panel, make_icon("time"), "Timers")
        self._page_tools_tabs.currentChanged.connect(lambda _index: self._update_workspace_tab_metadata())

        self._inspector_tabs = QTabWidget()
        self._inspector_tabs.setObjectName("workspace_inspector_tabs")
        self._inspector_tabs.addTab(self.props_dock, make_icon("properties"), "Properties")
        self._inspector_tabs.addTab(self.animations_panel, make_icon("animation"), "Animations")
        self._inspector_tabs.addTab(self._page_tools_tabs, make_icon("page"), "Page")
        self._inspector_tabs.currentChanged.connect(lambda _index: self._update_workspace_tab_metadata())

        self._top_splitter = QSplitter(Qt.Horizontal)
        self._top_splitter.setChildrenCollapsible(False)
        self._top_splitter.addWidget(self._left_shell)
        self._top_splitter.addWidget(center_shell)
        self._top_splitter.addWidget(self._inspector_tabs)
        self._top_splitter.setSizes([350, 920, 360])

        self._bottom_header = QFrame()
        self._bottom_header.setObjectName("workspace_bottom_header")
        bottom_header_layout = QHBoxLayout(self._bottom_header)
        bottom_header_layout.setContentsMargins(10, 8, 10, 8)
        bottom_header_layout.setSpacing(8)
        self._bottom_title = QLabel("Tools")
        self._bottom_title.setObjectName("workspace_section_title")
        bottom_header_layout.addWidget(self._bottom_title)
        self._bottom_toggle_button = PushButton("Hide")
        self._bottom_toggle_button.clicked.connect(lambda: self._set_bottom_panel_visible(not self._bottom_panel_visible))
        bottom_header_layout.addStretch()
        bottom_header_layout.addWidget(self._bottom_toggle_button)

        self._bottom_tabs = QTabWidget()
        self._bottom_tabs.addTab(self.diagnostics_panel, make_icon("diagnostics"), "Diagnostics")
        self._bottom_tabs.addTab(self.history_panel, make_icon("history"), "History")
        self._bottom_tabs.addTab(self.debug_panel, make_icon("debug"), "Debug Output")
        self._bottom_tabs.currentChanged.connect(self._on_bottom_tab_changed)

        bottom_shell = QWidget()
        self._bottom_shell = bottom_shell
        bottom_shell.setObjectName("workspace_bottom_shell")
        bottom_layout = QVBoxLayout(bottom_shell)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(8)
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
        self._current_left_panel = "project"

        # Status bar
        self._sdk_status_label = QLabel("SDK: missing")
        self.statusBar().addPermanentWidget(self._sdk_status_label)
        self._update_sdk_status_label()
        self.statusBar().showMessage("Ready")

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
        self.property_panel.validation_message.connect(self._on_property_validation_message)
        self.property_panel.user_code_requested.connect(self._on_user_code_requested)

        self.widget_browser.insert_requested.connect(self._insert_widget_from_browser)
        self.widget_browser.reveal_requested.connect(self._reveal_widget_type_in_structure)
        self.status_center_panel.action_requested.connect(self._on_status_center_action_requested)
        self._project_workspace.view_changed.connect(self._on_project_workspace_view_changed)

        # Preview panel
        self.preview_panel.selection_changed.connect(self._on_preview_selection_changed)
        self.preview_panel.widget_selected.connect(self._on_preview_widget_selected)
        self.preview_panel.context_menu_requested.connect(self._show_preview_context_menu)
        self.preview_panel.widget_moved.connect(self._on_widget_moved)
        self.preview_panel.widget_resized.connect(self._on_widget_resized)
        self.preview_panel.widget_reordered.connect(self._on_widget_reordered)
        self.preview_panel.resource_dropped.connect(self._on_resource_dropped)
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
        self.status_center_panel.restore_view_state(getattr(self._config, "workspace_status_panel_state", {}))

    def _apply_stylesheet(self):
        pass  # Rely entirely on the global Fusion / Fluent theme

    def _prepare_workspace_dock(self, dock_widget):
        if dock_widget is None or not isinstance(dock_widget, QDockWidget):
            return
        dock_widget.setFeatures(QDockWidget.NoDockWidgetFeatures)
        dock_widget.setTitleBarWidget(QWidget(dock_widget))

    def _create_workspace_nav_button(self, label, icon_key, panel_key):
        button = QToolButton(self)
        button.setProperty("workspaceNav", True)
        button.setCheckable(True)
        button.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        button.setIcon(make_icon(icon_key, size=22))
        button.setIconSize(QSize(22, 22))
        button.setText(label)
        button.clicked.connect(lambda checked=False, key=panel_key: self._select_left_panel(key))
        return button

    def _workspace_panel_label(self, panel_key):
        return {
            "project": "Project",
            "structure": "Structure",
            "widgets": "Components",
            "assets": "Assets",
            "status": "Status",
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

    def _status_workspace_nav_context(self):
        diagnostics_counts = self.diagnostics_panel.severity_counts() if hasattr(self, "diagnostics_panel") else {"error": 0, "warning": 0}
        error_count = int(diagnostics_counts.get("error", 0) or 0)
        warning_count = int(diagnostics_counts.get("warning", 0) or 0)
        dirty_count = len(self._undo_manager.dirty_pages()) if hasattr(self, "_undo_manager") else 0
        dirty_text = "no dirty pages" if dirty_count == 0 else ("1 dirty page" if dirty_count == 1 else f"{dirty_count} dirty pages")
        return f"Diagnostics: {error_count} errors and {warning_count} warnings. Dirty state: {dirty_text}."

    def _update_workspace_nav_button_metadata(self, current_panel):
        if not hasattr(self, "_workspace_nav_buttons"):
            return
        for key, button in self._workspace_nav_buttons.items():
            label = self._workspace_panel_label(key)
            if key == "project":
                context = self._project_workspace_nav_context()
            elif key == "structure":
                context = self._structure_workspace_nav_context()
            elif key == "widgets":
                context = self._components_workspace_nav_context()
            elif key == "assets":
                context = self._assets_workspace_nav_context()
            elif key == "status":
                context = self._status_workspace_nav_context()
            else:
                context = ""
            if key == current_panel:
                tooltip = f"Currently showing {label} panel."
                accessible_name = f"Workspace panel button: {label}. Current panel."
            else:
                tooltip = f"Open {label} panel."
                accessible_name = f"Workspace panel button: {label}."
            if context:
                tooltip = f"{tooltip} {context}"
                accessible_name = f"{accessible_name} {context}"
            button.setToolTip(tooltip)
            button.setStatusTip(tooltip)
            button.setAccessibleName(accessible_name)
        current_label = self._workspace_panel_label(current_panel)
        current_context = self._workspace_menu_action_context(current_panel)
        if hasattr(self, "_workspace_nav_frame"):
            nav_summary = f"Workspace navigation rail. Current panel: {current_label}."
            self._workspace_nav_frame.setToolTip(nav_summary)
            self._workspace_nav_frame.setStatusTip(nav_summary)
            self._workspace_nav_frame.setAccessibleName(nav_summary)
        if hasattr(self, "_left_panel_stack"):
            stack_summary = f"Workspace panels: {current_label} visible."
            if current_context:
                stack_summary = f"{stack_summary} {current_context}"
            self._left_panel_stack.setToolTip(stack_summary)
            self._left_panel_stack.setStatusTip(stack_summary)
            self._left_panel_stack.setAccessibleName(stack_summary)
        if hasattr(self, "_left_shell"):
            shell_summary = f"Workspace left shell: {current_label} panel visible."
            if current_context:
                shell_summary = f"{shell_summary} {current_context}"
            self._left_shell.setToolTip(shell_summary)
            self._left_shell.setStatusTip(shell_summary)
            self._left_shell.setAccessibleName(shell_summary)
        self._update_workspace_layout_metadata()

    def _workspace_menu_action_context(self, panel_key):
        if panel_key == "project":
            return self._project_workspace_nav_context()
        if panel_key == "structure":
            return self._structure_workspace_nav_context()
        if panel_key == "widgets":
            return self._components_workspace_nav_context()
        if panel_key == "assets":
            return self._assets_workspace_nav_context()
        if panel_key == "status":
            return self._status_workspace_nav_context()
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
        has_mockup, mockup_visible, _opacity, _mockup_context = self._preview_mockup_action_context()
        mockup_state = "none loaded" if not has_mockup else ("visible" if mockup_visible else "hidden")
        if hasattr(self, "_view_menu"):
            self._apply_action_hint(
                self._view_menu.menuAction(),
                (
                    "Change workspace layout, themes, preview modes, and mockup options. "
                    f"Theme: {theme_label}. Font size: {font_label}. Layout: {layout_label}. "
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

    def _update_build_menu_metadata(self):
        if not hasattr(self, "_build_menu"):
            return
        compile_state = "available" if getattr(getattr(self, "_compile_action", None), "isEnabled", lambda: False)() else "unavailable"
        auto_compile_state = "on" if getattr(getattr(self, "auto_compile_action", None), "isChecked", lambda: False)() else "off"
        preview_running = bool(self.compiler is not None and self.compiler.is_preview_running()) if hasattr(self, "compiler") else False
        preview_state = "running" if preview_running else "stopped"
        release_state = "available" if getattr(getattr(self, "_release_history_action", None), "isEnabled", lambda: False)() else "unavailable"
        project_state = "open" if getattr(self, "project", None) is not None else "none"
        self._apply_action_hint(
            self._build_menu.menuAction(),
            (
                "Compile previews, generate resources, and manage release builds. "
                f"Project: {project_state}. Compile: {compile_state}. Auto compile: {auto_compile_state}. "
                f"Preview: {preview_state}. Release history: {release_state}."
            ),
        )

    def _update_file_menu_metadata(self):
        if not hasattr(self, "_file_menu"):
            return
        project_state = "open" if getattr(self, "project", None) is not None else "none"
        dirty_state = "present" if hasattr(self, "_undo_manager") and self._undo_manager.is_any_dirty() else "none"
        reload_state = "available" if getattr(getattr(self, "_reload_project_action", None), "isEnabled", lambda: False)() else "unavailable"
        recent = getattr(getattr(self, "_config", None), "recent_projects", []) or []
        recent_count = min(len(recent), 10)
        recent_label = "none" if recent_count == 0 else f"{recent_count} project" if recent_count == 1 else f"{recent_count} projects"
        self._apply_action_hint(
            self._file_menu.menuAction(),
            (
                "Create, open, save, export, and close projects. "
                f"Project: {project_state}. Unsaved changes: {dirty_state}. Reload: {reload_state}. Recent projects: {recent_label}."
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
        quick_move_menu = getattr(self, "_quick_move_into_menu", None)
        quick_move_state = (
            "available"
            if quick_move_menu is not None and quick_move_menu.menuAction().isEnabled()
            else "unavailable"
        )
        self._apply_action_hint(
            self._structure_menu.menuAction(),
            (
                "Group, move, and reorder widgets in the page hierarchy. "
                f"{self._selection_accessibility_text()} "
                f"Group/Ungroup: {group_state}. Move Into: {move_into_state}. "
                f"Reorder/Lift: {reorder_lift_state}. Quick Move: {quick_move_state}."
            ),
        )

    def _update_generate_resources_action_metadata(self):
        if not hasattr(self, "_generate_resources_action"):
            return
        project_state = "open" if getattr(self, "project", None) is not None and bool(self._project_dir) else "none"
        sdk_state = "valid" if self._has_valid_sdk_root() else "invalid"
        resources_dir = self._get_eguiproject_resource_dir()
        resources_state = "available" if resources_dir and os.path.isdir(resources_dir) else "missing"
        hint = (
            "Run resource generation (app_resource_generate.py) to produce\n"
            "C source files from .eguiproject/resources/ assets and widget config. "
            f"Project: {project_state}. SDK: {sdk_state}. Source resources: {resources_state}."
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
        page = self._left_panel_pages[panel_key]
        self._left_panel_stack.setCurrentWidget(page)
        for key, button in getattr(self, "_workspace_nav_buttons", {}).items():
            button.setChecked(key == panel_key)
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
            tooltip = "Open or create a project to insert a widget."
            accessible_name = "Insert widget unavailable."
        else:
            target = self._insert_target_summary(parent)
            tooltip = f"Open Components and insert a widget into {target}."
            accessible_name = f"Insert widget target: {target}."
        self._insert_widget_button.setToolTip(tooltip)
        self._insert_widget_button.setStatusTip(tooltip)
        self._insert_widget_button.setAccessibleName(accessible_name)

    def _action_hint(self, base_text, enabled, blocked_reason=""):
        if enabled or not blocked_reason:
            return base_text
        reason = blocked_reason.rstrip(".")
        return f"{base_text} Unavailable: {reason}."

    def _apply_action_hint(self, action, hint):
        if action is None:
            return
        action.setToolTip(hint)
        action.setStatusTip(hint)

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
        if not self.compiler.can_build():
            build_error_getter = getattr(self.compiler, "get_build_error", None)
            build_error = build_error_getter() if callable(build_error_getter) else ""
            if build_error:
                return build_error
        return "compile preview is unavailable"

    def _update_toolbar_action_metadata(self):
        command_bar_summary = "Workspace command bar with insert, edit, preview, mode, and status controls."
        if hasattr(self, "_toolbar_host"):
            self._toolbar_host.setToolTip(command_bar_summary)
            self._toolbar_host.setStatusTip(command_bar_summary)
            self._toolbar_host.setAccessibleName(command_bar_summary)
        toolbar_summary = "Main toolbar: insert, save, edit, and preview commands."
        if hasattr(self, "_toolbar"):
            self._toolbar.setToolTip(toolbar_summary)
            self._toolbar.setStatusTip(toolbar_summary)
            self._toolbar.setAccessibleName(toolbar_summary)
        if hasattr(self, "_save_action"):
            has_project = getattr(self, "project", None) is not None
            self._save_action.setEnabled(has_project)
            if has_project:
                dirty_count = len(self._undo_manager.dirty_pages()) if hasattr(self, "_undo_manager") else 0
                dirty_label = "none" if dirty_count == 0 else f"{dirty_count} page" if dirty_count == 1 else f"{dirty_count} pages"
                save_hint = f"Save the current project (Ctrl+S). Unsaved pages: {dirty_label}."
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
            compile_hint = self._action_hint(
                "Compile the current project and run the preview (F5).",
                self._compile_action.isEnabled(),
                self._compile_action_blocked_reason(),
            )
            self._apply_action_hint(self._compile_action, compile_hint)
        if hasattr(self, "_stop_action"):
            stop_hint = self._action_hint(
                "Stop the running preview executable.",
                self._stop_action.isEnabled(),
                "preview is not running",
            )
            self._apply_action_hint(self._stop_action, stop_hint)

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

    def _show_inspector_tab(self, section, inner_section=None):
        section_map = {
            "properties": 0,
            "animations": 1,
            "page": 2,
        }
        index = section_map.get(section, 0)
        if hasattr(self, "_inspector_tabs"):
            self._inspector_tabs.setCurrentIndex(index)
        if section == "page" and inner_section in ("fields", "timers") and hasattr(self, "_page_tools_tabs"):
            self._page_tools_tabs.setCurrentIndex(0 if inner_section == "fields" else 1)
        self._update_view_panel_navigation_action_metadata()

    def _show_bottom_panel(self, section="Diagnostics"):
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
        self._bottom_panel_visible = bool(visible)
        self._bottom_tabs.setVisible(self._bottom_panel_visible)
        if self._bottom_panel_visible:
            self._workspace_splitter.setSizes([760, 220])
            self._bottom_toggle_button.setText("Hide")
        else:
            self._workspace_splitter.setSizes([1000, 0])
            self._bottom_toggle_button.setText("Show")
        self._update_bottom_toggle_button_metadata()
        self._update_workspace_tab_metadata()

    def _on_bottom_tab_changed(self, index):
        titles = {0: "Diagnostics", 1: "History", 2: "Debug Output"}
        if hasattr(self, "_bottom_title"):
            self._bottom_title.setText(titles.get(index, "Tools"))
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
        self._bottom_toggle_button.setToolTip(tooltip)
        self._bottom_toggle_button.setStatusTip(tooltip)
        self._bottom_toggle_button.setAccessibleName(accessible_name)

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
            self._inspector_tabs.setToolTip(tooltip)
            self._inspector_tabs.setStatusTip(tooltip)
            self._inspector_tabs.setAccessibleName(
                f"Inspector tabs: {current} selected. {self._inspector_tabs.count()} tabs. Current page: {current_page}. {selection_text}"
            )
        if hasattr(self, "_page_tools_tabs"):
            current = self._current_tab_text(self._page_tools_tabs, "Fields")
            current_page = str(getattr(getattr(self, "_current_page", None), "name", "") or "none")
            tooltip = f"Page tools tabs. Current section: {current}. Current page: {current_page}."
            self._page_tools_tabs.setToolTip(tooltip)
            self._page_tools_tabs.setStatusTip(tooltip)
            self._page_tools_tabs.setAccessibleName(
                f"Page tools tabs: {current} selected. {self._page_tools_tabs.count()} tabs. Current page: {current_page}."
            )
        if hasattr(self, "_bottom_tabs"):
            current = self._current_tab_text(self._bottom_tabs, "Diagnostics")
            current_page = self._current_page_accessibility_text()
            visibility = "visible" if self._bottom_panel_visible else "hidden"
            tooltip = f"Bottom tools tabs. Current section: {current}. Current page: {current_page}. Panel {visibility}."
            self._bottom_tabs.setToolTip(tooltip)
            self._bottom_tabs.setStatusTip(tooltip)
            self._bottom_tabs.setAccessibleName(
                f"Bottom tools tabs: {current} selected. {self._bottom_tabs.count()} tabs. Current page: {current_page}. Panel {visibility}."
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
            self._editor_container.setToolTip(editor_summary)
            self._editor_container.setStatusTip(editor_summary)
            self._editor_container.setAccessibleName(editor_summary)
        if hasattr(self, "_center_shell"):
            center_summary = f"Workspace center shell. Current page: {current_page}. Mode: {current_mode}."
            self._center_shell.setToolTip(center_summary)
            self._center_shell.setStatusTip(center_summary)
            self._center_shell.setAccessibleName(center_summary)
        if hasattr(self, "_top_splitter"):
            top_splitter_summary = (
                f"Workspace columns. Left panel: {current_panel}. Editor mode: {current_mode}. "
                f"Inspector section: {inspector_section}. Current page: {current_page}."
            )
            self._top_splitter.setToolTip(top_splitter_summary)
            self._top_splitter.setStatusTip(top_splitter_summary)
            self._top_splitter.setAccessibleName(top_splitter_summary)
        if hasattr(self, "_workspace_splitter"):
            workspace_splitter_summary = (
                f"Workspace rows. Editor area visible. Bottom tools {visibility}. "
                f"Current section: {bottom_section}. Current page: {current_page}."
            )
            self._workspace_splitter.setToolTip(workspace_splitter_summary)
            self._workspace_splitter.setStatusTip(workspace_splitter_summary)
            self._workspace_splitter.setAccessibleName(workspace_splitter_summary)
        if hasattr(self, "_bottom_header"):
            bottom_header_summary = f"Bottom tools header. Current section: {bottom_section}. Panel {visibility}."
            self._bottom_header.setToolTip(bottom_header_summary)
            self._bottom_header.setStatusTip(bottom_header_summary)
            self._bottom_header.setAccessibleName(bottom_header_summary)
        if hasattr(self, "_bottom_shell"):
            bottom_shell_summary = (
                f"Workspace bottom shell. Current section: {bottom_section}. Panel {visibility}. "
                f"Current page: {current_page}."
            )
            self._bottom_shell.setToolTip(bottom_shell_summary)
            self._bottom_shell.setStatusTip(bottom_shell_summary)
            self._bottom_shell.setAccessibleName(bottom_shell_summary)

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
        dirty_label = (
            "No dirty pages"
            if dirty_count == 0
            else (f"{dirty_count} dirty page" if dirty_count == 1 else f"{dirty_count} dirty pages")
        )
        summary = f"Page tabs: {page_label}. Current page: {current_page}. Startup page: {startup_page}. {dirty_label}."
        self.page_tab_bar.setToolTip(summary)
        self.page_tab_bar.setStatusTip(summary)
        self.page_tab_bar.setAccessibleName(summary)

    def _update_main_view_metadata(self):
        if not hasattr(self, "_central_stack"):
            return
        current_index = self._central_stack.currentIndex()
        view_label = "Welcome page" if current_index == 0 else "Editor workspace"
        summary = f"Main view stack: {view_label} visible."
        self._central_stack.setToolTip(summary)
        self._central_stack.setStatusTip(summary)
        self._central_stack.setAccessibleName(summary)
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
            button.setToolTip(tooltip)
            button.setStatusTip(tooltip)
            button.setAccessibleName(accessible_name)

    def _set_chip(self, chip, text, tone=None, accessible_name=None, tool_tip=None):
        if chip is None:
            return
        chip.setText(text)
        chip.setAccessibleName(accessible_name or text)
        if tool_tip is not None:
            chip.setToolTip(tool_tip)
            chip.setStatusTip(tool_tip)
        if tone is not None:
            chip.setProperty("chipTone", tone)
        chip.style().unpolish(chip)
        chip.style().polish(chip)
        chip.update()

    def _update_workspace_chips(self):
        diagnostics_counts = self.diagnostics_panel.severity_counts() if hasattr(self, "diagnostics_panel") else {"error": 0, "warning": 0, "info": 0}
        preview_text = "Preview idle"
        preview_tone = "accent"
        if self.preview_panel.is_python_preview_active():
            preview_text = "Python preview"
            preview_tone = "warning"
        elif self.compiler is not None and self.compiler.is_preview_running():
            preview_text = "Live preview"
            preview_tone = "success"

        if hasattr(self, "_sdk_chip"):
            sdk_text = "SDK ready" if self._has_valid_sdk_root() else "SDK missing"
            self._set_chip(
                self._sdk_chip,
                sdk_text,
                "accent" if self._has_valid_sdk_root() else "warning",
                accessible_name=f"Workspace status: {sdk_text}.",
                tool_tip="Open Status Center to review SDK readiness.",
            )
        dirty_pages = set(self._undo_manager.dirty_pages()) if hasattr(self, "_undo_manager") else set()
        if hasattr(self, "_dirty_chip"):
            dirty_count = len(dirty_pages)
            dirty_text = f"Dirty {dirty_count}" if dirty_pages else "Clean"
            dirty_summary = f"{dirty_count} dirty page" if dirty_count == 1 else f"{dirty_count} dirty pages"
            if not dirty_pages:
                dirty_summary = "no dirty pages"
            self._set_chip(
                self._dirty_chip,
                dirty_text,
                "warning" if dirty_pages else "success",
                accessible_name=f"Workspace status: {dirty_summary}.",
                tool_tip="Open History to review unsaved changes.",
            )
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
                dirty_pages=len(dirty_pages),
            )
        if hasattr(self, "_selection_chip"):
            count = len(self._selection_state.widgets) if hasattr(self, "_selection_state") else 0
            selection_text = f"{count} selected" if count else "No selection"
            selection_summary = f"{count} selected" if count else "no selection"
            self._set_chip(
                self._selection_chip,
                selection_text,
                accessible_name=f"Workspace status: {selection_summary}.",
                tool_tip="Open Structure to review the current selection.",
            )
        if hasattr(self, "_preview_chip"):
            self._set_chip(
                self._preview_chip,
                preview_text,
                preview_tone,
                accessible_name=f"Workspace status: {preview_text}.",
                tool_tip="Open Debug Output to inspect preview runtime details.",
            )
        if hasattr(self, "_diagnostics_chip"):
            error_count = int(diagnostics_counts.get("error", 0) or 0)
            warning_count = int(diagnostics_counts.get("warning", 0) or 0)
            if error_count:
                tone = "danger"
            elif warning_count:
                tone = "warning"
            else:
                tone = "success"
            label = f"Diagnostics {error_count}E/{warning_count}W"
            self._set_chip(
                self._diagnostics_chip,
                label,
                tone,
                accessible_name=f"Workspace diagnostics: {error_count} errors and {warning_count} warnings.",
                tool_tip="Open Diagnostics to review issues and warnings.",
            )

        self._update_status_center(
            dirty_pages=len(dirty_pages),
            selection_count=len(self._selection_state.widgets) if hasattr(self, "_selection_state") else 0,
            preview_text=preview_text,
            diagnostics_counts=diagnostics_counts,
        )
        self._update_workspace_tab_metadata()
        self._update_workspace_nav_button_metadata(getattr(self, "_current_left_panel", "project"))
        self._update_view_panel_navigation_action_metadata()

    def _apply_workspace_iconography(self):
        if hasattr(self, "_workspace_nav_buttons"):
            icon_map = {
                "project": "project",
                "structure": "structure",
                "widgets": "widgets",
                "assets": "assets",
                "status": "diagnostics",
            }
            for key, button in self._workspace_nav_buttons.items():
                button.setIcon(make_icon(icon_map.get(key, "widgets"), size=22))
        if hasattr(self, "_insert_widget_button"):
            self._insert_widget_button.setIcon(make_icon("widgets"))
        if hasattr(self, "_mode_buttons"):
            for mode, icon_key in ((MODE_DESIGN, "widgets"), (MODE_SPLIT, "layout"), (MODE_CODE, "page")):
                self._mode_buttons[mode].setIcon(make_icon(icon_key))

    def _on_status_center_action_requested(self, action_key):
        action = str(action_key or "").strip().lower()
        if action == "open_project_panel":
            self._select_left_panel("project")
            return
        if action == "open_structure_panel":
            self._select_left_panel("structure")
            return
        if action == "open_components_panel":
            self._select_left_panel("widgets")
            return
        if action == "open_assets_panel":
            self._select_left_panel("assets")
            return
        if action == "open_properties_inspector":
            self._show_inspector_tab("properties")
            return
        if action == "open_animations_inspector":
            self._show_inspector_tab("animations")
            return
        if action == "open_page_fields":
            self._show_inspector_tab("page", "fields")
            return
        if action == "open_page_timers":
            self._show_inspector_tab("page", "timers")
            return
        if action == "open_diagnostics":
            self._show_bottom_panel("Diagnostics")
            return
        if action == "open_error_diagnostics":
            self._show_bottom_panel("Diagnostics")
            if hasattr(self, "diagnostics_panel"):
                self.diagnostics_panel.set_severity_filter("error")
            return
        if action == "open_warning_diagnostics":
            self._show_bottom_panel("Diagnostics")
            if hasattr(self, "diagnostics_panel"):
                self.diagnostics_panel.set_severity_filter("warning")
            return
        if action == "open_info_diagnostics":
            self._show_bottom_panel("Diagnostics")
            if hasattr(self, "diagnostics_panel"):
                self.diagnostics_panel.set_severity_filter("info")
            return
        if action == "open_history":
            self._show_bottom_panel("History")
            return
        if action == "open_debug":
            self._show_bottom_panel("Debug Output")
            return
        if action == "open_first_error":
            self._show_bottom_panel("Diagnostics")
            if hasattr(self, "diagnostics_panel"):
                self.diagnostics_panel.open_first_error()
            return
        if action == "open_first_warning":
            self._show_bottom_panel("Diagnostics")
            if hasattr(self, "diagnostics_panel"):
                self.diagnostics_panel.open_first_warning()

    def _update_status_center(self, *, dirty_pages=0, selection_count=0, preview_text="Preview idle", diagnostics_counts=None):
        if not hasattr(self, "status_center_panel"):
            return
        counts = diagnostics_counts or {"error": 0, "warning": 0, "info": 0}
        runtime_error = str(self._last_runtime_error_text or "").strip()
        if not runtime_error and self.compiler is not None:
            try:
                runtime_error = str(self.compiler.get_last_runtime_error() or "").strip()
            except Exception:
                runtime_error = ""
        self.status_center_panel.set_status(
            sdk_ready=self._has_valid_sdk_root(),
            can_compile=bool(getattr(self, "_compile_action", None) and self._compile_action.isEnabled()),
            dirty_pages=int(dirty_pages or 0),
            selection_count=int(selection_count or 0),
            preview_label=preview_text,
            diagnostics_errors=int(counts.get("error", 0) or 0),
            diagnostics_warnings=int(counts.get("warning", 0) or 0),
            diagnostics_infos=int(counts.get("info", 0) or 0),
            runtime_error=runtime_error,
        )

    def _apply_saved_window_state(self):
        geometry = (self._config.window_geometry or "").strip()
        if geometry:
            try:
                self.restoreGeometry(QByteArray.fromBase64(geometry.encode("ascii")))
            except Exception:
                pass

        if int(getattr(self._config, "workspace_layout_version", 0) or 0) != WORKSPACE_LAYOUT_VERSION:
            return

        state = (self._config.window_state or "").strip()
        if state:
            try:
                self.restoreState(QByteArray.fromBase64(state.encode("ascii")))
            except Exception:
                pass

        workspace_state = getattr(self._config, "workspace_state", {}) if isinstance(getattr(self._config, "workspace_state", {}), dict) else {}
        for splitter, key in (
            (getattr(self, "_top_splitter", None), "top_splitter"),
            (getattr(self, "_workspace_splitter", None), "workspace_splitter"),
        ):
            state = str(workspace_state.get(key, "") or "").strip()
            if splitter is None or not state:
                continue
            try:
                splitter.restoreState(QByteArray.fromBase64(state.encode("ascii")))
            except Exception:
                pass

        self._select_left_panel(getattr(self._config, "workspace_left_panel", "project"))

    def _save_window_state_to_config(self):
        try:
            self._config.window_geometry = bytes(self.saveGeometry().toBase64()).decode("ascii")
            self._config.window_state = bytes(self.saveState().toBase64()).decode("ascii")
            self._config.workspace_layout_version = WORKSPACE_LAYOUT_VERSION
            self._config.workspace_left_panel = getattr(self, "_current_left_panel", "project")
            self._config.workspace_state = {
                "top_splitter": bytes(self._top_splitter.saveState().toBase64()).decode("ascii") if hasattr(self, "_top_splitter") else "",
                "workspace_splitter": bytes(self._workspace_splitter.saveState().toBase64()).decode("ascii") if hasattr(self, "_workspace_splitter") else "",
            }
            self._config.workspace_status_panel_state = (
                self.status_center_panel.view_state() if hasattr(self, "status_center_panel") else {}
            )
        except Exception:
            self._config.window_geometry = ""
            self._config.window_state = ""
            self._config.workspace_state = {}
            self._config.workspace_status_panel_state = {}

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
            worker.finished.connect(lambda *args, _worker=worker: _release_detached_worker(_worker))
        except Exception:
            _release_detached_worker(worker)

    def _cleanup_worker_ref(self, worker, attr_name):
        if worker is None:
            return
        if getattr(self, attr_name, None) is worker:
            setattr(self, attr_name, None)
        if worker in _DETACHED_WORKERS:
            _release_detached_worker(worker)
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

    def _apply_sdk_root(self, path, status_message=""):
        path = normalize_path(path)
        if not path:
            return

        self.project_root = path
        self._config.sdk_root = path
        self._config.egui_root = path
        self._config.sdk_setup_prompted = True
        self._config.save()

        if self.project is not None:
            self.project.sdk_root = path
            self._bump_async_generation()
            self._shutdown_async_activity()
            self._recreate_compiler()
            self._update_compile_availability()
            if self.compiler is None or not self.compiler.can_build():
                reason = "SDK unavailable, compile preview disabled"
                if self.compiler is not None and self.compiler.get_build_error():
                    reason = self.compiler.get_build_error()
                self._switch_to_python_preview(reason)
            elif self.auto_compile:
                self._trigger_compile()

        self._welcome_page.refresh()
        self._update_sdk_status_label()
        if status_message:
            self.statusBar().showMessage(status_message)

    def _has_valid_sdk_root(self):
        return is_valid_sdk_root(self.project_root)

    def _recreate_compiler(self):
        if self.compiler is not None:
            self.compiler.cleanup()
            self.compiler = None

        if not self._has_valid_sdk_root() or not self._project_dir or not self.app_name:
            return

        self.compiler = CompilerEngine(self.project_root, self._project_dir, self.app_name)
        if self.project is not None:
            self.compiler.set_screen_size(self.project.screen_width, self.project.screen_height)

    def _update_compile_availability(self):
        can_compile = (
            self.project is not None
            and self.compiler is not None
            and self._has_valid_sdk_root()
            and self.compiler.can_build()
        )
        can_release = self.project is not None and bool(self._project_dir) and self._has_valid_sdk_root()
        latest_entry = latest_release_entry(self._project_dir, output_dir=self._release_output_root()) if self.project is not None and self._project_dir else {}
        has_release_history = bool(latest_entry)
        release_root = normalize_path(latest_entry.get("release_root", "")) if isinstance(latest_entry, dict) else ""
        dist_dir = normalize_path(latest_entry.get("dist_dir", "")) if isinstance(latest_entry, dict) else ""
        manifest_path = normalize_path(latest_entry.get("manifest_path", "")) if isinstance(latest_entry, dict) else ""
        zip_path = normalize_path(latest_entry.get("zip_path", "")) if isinstance(latest_entry, dict) else ""
        log_path = normalize_path(latest_entry.get("log_path", "")) if isinstance(latest_entry, dict) else ""
        version_path = self._latest_release_version_path(latest_entry)
        history_file_path = normalize_path(release_history_path(self._project_dir, output_dir=self._release_output_root())) if self._project_dir else ""
        can_browse_release_history = self.project is not None and bool(self._project_dir)
        self._compile_action.setEnabled(can_compile)
        self.auto_compile_action.setEnabled(can_compile)
        self._apply_action_hint(
            self.auto_compile_action,
            self._action_hint(
                "Automatically compile and rerun the preview after changes.",
                self.auto_compile_action.isEnabled(),
                self._compile_action_blocked_reason(),
            ),
        )
        self._stop_action.setEnabled(self.compiler is not None and self.compiler.is_preview_running())
        self._reload_project_action.setEnabled(self.project is not None and bool(self._project_dir))
        self._apply_action_hint(
            self._reload_project_action,
            self._action_hint(
                "Reload the current project from disk (Ctrl+Shift+R).",
                self._reload_project_action.isEnabled(),
                "open a project first",
            ),
        )
        if hasattr(self, "_release_build_action"):
            self._release_build_action.setEnabled(can_release)
            self._release_profiles_action.setEnabled(self.project is not None)
            self._release_history_action.setEnabled(can_browse_release_history)
            self._apply_action_hint(
                self._release_build_action,
                self._action_hint(
                    "Build a release package for the current project.",
                    self._release_build_action.isEnabled(),
                    "open a project first"
                    if self.project is None
                    else "save the project to disk first"
                    if not self._project_dir
                    else "set a valid SDK root first",
                ),
            )
            self._apply_action_hint(
                self._release_profiles_action,
                self._action_hint(
                    "Edit release profiles for the current project.",
                    self._release_profiles_action.isEnabled(),
                    "open a project first",
                ),
            )
            self._apply_action_hint(
                self._release_history_action,
                self._action_hint(
                    "Browse recorded release builds for the current project.",
                    self._release_history_action.isEnabled(),
                    "open a project first" if self.project is None else "save the project to disk first",
                ),
            )
            self._apply_action_hint(
                self._repo_health_action,
                "Inspect the Designer repository health summary.",
            )
            self._open_last_release_dir_action.setEnabled(bool(release_root and os.path.isdir(release_root)))
            self._open_last_release_dist_action.setEnabled(bool(dist_dir and os.path.isdir(dist_dir)))
            self._open_last_release_manifest_action.setEnabled(bool(manifest_path and os.path.isfile(manifest_path)))
            self._open_last_release_version_action.setEnabled(bool(version_path))
            self._open_last_release_package_action.setEnabled(bool(zip_path and os.path.isfile(zip_path)))
            self._open_last_release_log_action.setEnabled(bool(log_path and os.path.isfile(log_path)))
            self._open_release_history_file_action.setEnabled(bool(history_file_path and os.path.isfile(history_file_path)))
            self._open_last_release_dir_action.setToolTip(
                _release_action_tooltip("Open last release folder", latest_entry, path=release_root, unavailable_label="Release folder unavailable")
            )
            self._open_last_release_dir_action.setStatusTip(self._open_last_release_dir_action.toolTip())
            self._open_last_release_dist_action.setToolTip(
                _release_action_tooltip("Open last release dist", latest_entry, path=dist_dir, unavailable_label="Release dist unavailable")
            )
            self._open_last_release_dist_action.setStatusTip(self._open_last_release_dist_action.toolTip())
            self._open_last_release_manifest_action.setToolTip(
                _release_action_tooltip(
                    "Open last release manifest",
                    latest_entry,
                    path=manifest_path,
                    unavailable_label="Release manifest unavailable",
                )
            )
            self._open_last_release_manifest_action.setStatusTip(self._open_last_release_manifest_action.toolTip())
            self._open_last_release_version_action.setToolTip(
                _release_action_tooltip(
                    "Open last release version",
                    latest_entry,
                    path=version_path,
                    unavailable_label="Release version unavailable",
                )
            )
            self._open_last_release_version_action.setStatusTip(self._open_last_release_version_action.toolTip())
            self._open_last_release_package_action.setToolTip(
                _release_action_tooltip(
                    "Open last release package",
                    latest_entry,
                    path=zip_path,
                    unavailable_label="Release package unavailable",
                )
            )
            self._open_last_release_package_action.setStatusTip(self._open_last_release_package_action.toolTip())
            self._open_last_release_log_action.setToolTip(
                _release_action_tooltip("Open last release log", latest_entry, path=log_path, unavailable_label="Release log unavailable")
            )
            self._open_last_release_log_action.setStatusTip(self._open_last_release_log_action.toolTip())
            self._open_release_history_file_action.setToolTip(
                _release_action_tooltip(
                    "Open release history file",
                    latest_entry,
                    path=history_file_path,
                    unavailable_label="Release history file unavailable",
                )
            )
            self._open_release_history_file_action.setStatusTip(self._open_release_history_file_action.toolTip())
        self._update_build_menu_metadata()
        self._update_file_menu_metadata()
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

    def _persist_current_project_to_config(self):
        self._config.last_app = self.app_name or self._config.last_app
        self._config.last_project_path = normalize_path(os.path.join(self._project_dir, f"{self.app_name}.egui")) if self._project_dir else ""
        if self._has_valid_sdk_root():
            self._config.sdk_root = self.project_root
            self._config.egui_root = self.project_root
        if self._config.last_project_path:
            self._config.add_recent_project(self._config.last_project_path, self.project_root, self.app_name)
        else:
            self._config.save()
        self._update_recent_menu()

    def _read_app_dimensions(self, app_dir):
        screen_w, screen_h = 240, 320
        config_h = os.path.join(app_dir, "app_egui_config.h")
        if not os.path.isfile(config_h):
            return screen_w, screen_h

        try:
            with open(config_h, "r", encoding="utf-8") as f:
                content = f.read()
            import re
            match = re.search(r"EGUI_CONFIG_SCEEN_WIDTH\s+(\d+)", content)
            if match:
                screen_w = int(match.group(1))
            match = re.search(r"EGUI_CONFIG_SCEEN_HEIGHT\s+(\d+)", content)
            if match:
                screen_h = int(match.group(1))
        except Exception:
            pass
        return screen_w, screen_h

    def _create_standard_project_model(self, app_name, sdk_root, project_dir):
        WidgetModel.reset_counter()
        screen_w, screen_h = self._read_app_dimensions(project_dir)
        project = Project(screen_width=screen_w, screen_height=screen_h, app_name=app_name)
        project.sdk_root = sdk_root
        project.project_dir = project_dir
        project.create_new_page("main_page")
        return project

    def _scaffold_project_directory(self, project_dir, app_name, screen_width, screen_height):
        os.makedirs(project_dir, exist_ok=True)
        resource_src_dir = os.path.join(project_dir, "resource", "src")
        os.makedirs(resource_src_dir, exist_ok=True)

        build_mk = os.path.join(project_dir, "build.mk")
        if not os.path.exists(build_mk):
            with open(build_mk, "w", encoding="utf-8") as f:
                f.write(make_app_build_mk_content(app_name))

        config_h = os.path.join(project_dir, "app_egui_config.h")
        if not os.path.exists(config_h):
            with open(config_h, "w", encoding="utf-8") as f:
                f.write(make_app_config_h_content(app_name, screen_width, screen_height))

        resource_cfg = os.path.join(resource_src_dir, "app_resource_config.json")
        if not os.path.exists(resource_cfg):
            with open(resource_cfg, "w", encoding="utf-8") as f:
                f.write(make_empty_resource_config_content())

    def _copy_project_sidecar_files(self, src_dir, dst_dir):
        if not src_dir or not os.path.isdir(src_dir) or normalize_path(src_dir) == normalize_path(dst_dir):
            return

        for rel_path in ("build.mk", "app_egui_config.h"):
            src_path = os.path.join(src_dir, rel_path)
            dst_path = os.path.join(dst_dir, rel_path)
            if os.path.isfile(src_path) and not os.path.exists(dst_path):
                shutil.copy2(src_path, dst_path)

        for rel_dir in (
            os.path.join(".eguiproject", "resources"),
            os.path.join(".eguiproject", "mockup"),
        ):
            src_path = os.path.join(src_dir, rel_dir)
            dst_path = os.path.join(dst_dir, rel_dir)
            if os.path.isdir(src_path):
                shutil.copytree(src_path, dst_path, dirs_exist_ok=True)

    def _build_project_watch_snapshot(self):
        snapshot = {}
        if not self._project_dir or not self.app_name:
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

        project_file = os.path.join(self._project_dir, f"{self.app_name}.egui")
        eguiproject_dir = os.path.join(self._project_dir, ".eguiproject")
        watch_roots = [
            project_file,
            os.path.join(eguiproject_dir, "layout"),
            os.path.join(eguiproject_dir, "resources"),
            os.path.join(eguiproject_dir, "mockup"),
            os.path.join(eguiproject_dir, "custom_widgets"),
        ]
        for root in watch_roots:
            _add_path(root)
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

    def _refresh_project_watch_snapshot(self):
        if self.project is None or not self._project_dir:
            self._project_watch_timer.stop()
            self._project_watch_snapshot = {}
            self._external_reload_pending = False
            return

        self._project_watch_snapshot = self._build_project_watch_snapshot()
        self._external_reload_pending = False
        if not self._project_watch_timer.isActive():
            self._project_watch_timer.start()

    def _poll_project_files(self):
        if self.project is None or not self._project_dir:
            return

        if self._external_reload_pending:
            if self._undo_manager.is_any_dirty():
                return
            if self._compile_worker is not None and self._compile_worker.isRunning():
                return
            if self._precompile_worker is not None and self._precompile_worker.isRunning():
                return
            self._reload_project_from_disk(auto=True)
            return

        new_snapshot = self._build_project_watch_snapshot()
        if not self._project_watch_snapshot:
            self._project_watch_snapshot = new_snapshot
            return
        if new_snapshot == self._project_watch_snapshot:
            return

        changed_paths = self._diff_project_watch_snapshot(self._project_watch_snapshot, new_snapshot)
        self._project_watch_snapshot = new_snapshot
        summary = self._summarize_changed_paths(changed_paths)

        if self._undo_manager.is_any_dirty():
            self._external_reload_pending = True
            self.debug_panel.log_info(f"External project change detected while dirty: {summary or 'project files updated'}")
            self.statusBar().showMessage("External project changes detected. Save or reload from disk to sync.", 5000)
            return

        if self._compile_worker is not None and self._compile_worker.isRunning():
            self._external_reload_pending = True
            return

        if self._precompile_worker is not None and self._precompile_worker.isRunning():
            self._external_reload_pending = True
            self.statusBar().showMessage("External project changes detected. Reload will resume after background compile.", 4000)
            return

        self._reload_project_from_disk(auto=True, changed_paths=changed_paths)

    def _reload_project_from_disk(self, checked=False, auto=False, changed_paths=None):
        del checked
        if self.project is None or not self._project_dir:
            return False

        if self._undo_manager.is_any_dirty():
            reply = QMessageBox.question(
                self,
                "Reload Project",
                "Reload project files from disk and discard unsaved changes?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return False

        current_page_name = self._current_page.name if self._current_page else ""

        try:
            project = Project.load(self._project_dir)
        except Exception as exc:
            self._external_reload_pending = True
            self.debug_panel.log_error(f"Project reload failed: {exc}")
            self._show_bottom_panel("Debug Output")
            if auto:
                self.statusBar().showMessage(f"Project reload failed: {exc}", 6000)
            else:
                QMessageBox.critical(self, "Reload Project Failed", f"Failed to reload project:\n{exc}")
            return False

        self._open_loaded_project(project, self._project_dir, preferred_sdk_root=self.project_root, silent=True)
        if current_page_name and self.project and self.project.get_page_by_name(current_page_name):
            if self._current_page is None or self._current_page.name != current_page_name:
                self._switch_page(current_page_name)

        summary = self._summarize_changed_paths(changed_paths or [])
        if auto:
            self.debug_panel.log_info(f"Project reloaded from disk: {summary or 'external changes applied'}")
            self.statusBar().showMessage(f"Reloaded external changes: {summary or 'project updated'}", 5000)
        else:
            self.statusBar().showMessage("Project reloaded from disk", 4000)
        return True

    def _clear_editor_state(self):
        self._stop_background_timers()
        self.preview_panel.stop_rendering()
        self._last_runtime_error_text = ""
        self._project_watch_snapshot = {}
        self._external_reload_pending = False
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
        self._update_edit_actions()
        self._update_widget_browser_target(preferred_parent=None)
        self._update_workspace_chips()
        self._update_workspace_tab_metadata()

    def _open_loaded_project(self, project, project_dir, preferred_sdk_root="", silent=False):
        project_dir = normalize_path(project_dir)
        self._bump_async_generation()
        self._shutdown_async_activity()
        self._last_runtime_error_text = ""
        resolved_sdk_root = self._resolve_ui_sdk_root(
            preferred_sdk_root or project.sdk_root,
            infer_sdk_root_from_project_dir(project_dir),
            self.project_root,
            self._config.sdk_root,
            self._config.egui_root,
        )
        project.sdk_root = resolved_sdk_root or normalize_path(preferred_sdk_root or project.sdk_root)
        project.project_dir = project_dir

        self.project = project
        self._project_dir = project_dir
        self.project_root = project.sdk_root
        self.app_name = project.app_name
        self._undo_manager = UndoManager()
        self._recreate_compiler()
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

        if self.compiler is None or not self.compiler.can_build():
            reason = "SDK unavailable, compile preview disabled"
            if self.compiler is not None and self.compiler.get_build_error():
                reason = self.compiler.get_build_error()
            self._switch_to_python_preview(reason)
            self.statusBar().showMessage(f"Opened project in editing-only mode: {reason}")
        else:
            self._trigger_compile()
            sdk_source = self._describe_sdk_source(project.sdk_root)
            if sdk_source:
                self.statusBar().showMessage(f"Opened: {project_dir} | SDK: {sdk_source}")
            else:
                self.statusBar().showMessage(f"Opened: {project_dir}")

        if not project.sdk_root and not silent:
            QMessageBox.information(
                self,
                "SDK Root Missing",
                "The project opened successfully, but no valid EmbeddedGUI SDK root was found. Preview will use Python fallback until you set the SDK root.",
            )

    # 鈹€鈹€ View switching 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    def _show_welcome_page(self):
        """Show the welcome page (hide editor)."""
        self._central_stack.setCurrentIndex(0)
        self._welcome_page.refresh()
        self.setWindowTitle("EmbeddedGUI Designer")
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
        page_tab_bar.setTabMaximumWidth(180)
        page_tab_bar.setTabShadowEnabled(False)
        page_tab_bar.setFixedHeight(40)
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

        new_action = QAction("New Project", self)
        new_action.setShortcut("Ctrl+N")
        self._apply_action_hint(new_action, "Create a new EmbeddedGUI Designer project.")
        new_action.triggered.connect(self._new_project)
        file_menu.addAction(new_action)

        open_app_action = QAction("Open SDK Example...", self)
        open_app_action.setShortcut("Ctrl+Shift+O")
        self._apply_action_hint(open_app_action, "Open an SDK example project or legacy example.")
        open_app_action.triggered.connect(self._open_app_dialog)
        file_menu.addAction(open_app_action)

        open_action = QAction("Open Project File...", self)
        open_action.setShortcut("Ctrl+O")
        self._apply_action_hint(open_action, "Open an existing .egui project file.")
        open_action.triggered.connect(self._open_project)
        file_menu.addAction(open_action)

        download_sdk_action = QAction("Download SDK Copy...", self)
        self._apply_action_hint(download_sdk_action, describe_auto_download_plan())
        download_sdk_action.triggered.connect(self._download_sdk)
        file_menu.addAction(download_sdk_action)

        set_sdk_root_action = QAction("Set SDK Root...", self)
        self._apply_action_hint(set_sdk_root_action, "Choose the EmbeddedGUI SDK root used for compile preview.")
        set_sdk_root_action.triggered.connect(self._set_sdk_root)
        file_menu.addAction(set_sdk_root_action)

        # Recent Projects submenu
        self._recent_menu = file_menu.addMenu("Recent Projects")
        self._apply_action_hint(self._recent_menu.menuAction(), "Open a recently used project.")
        self._update_recent_menu()

        file_menu.addSeparator()

        self._save_action = QAction("Save Project", self)
        self._save_action.setShortcut("Ctrl+S")
        self._save_action.triggered.connect(self._save_project)
        file_menu.addAction(self._save_action)

        save_as_action = QAction("Save As...", self)
        save_as_action.setShortcut("Ctrl+Shift+S")
        self._apply_action_hint(save_as_action, "Save the current project to a new file (Ctrl+Shift+S).")
        save_as_action.triggered.connect(self._save_project_as)
        file_menu.addAction(save_as_action)

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

        close_project_action = QAction("Close Project", self)
        close_project_action.setShortcut("Ctrl+W")
        self._apply_action_hint(close_project_action, "Close the current project (Ctrl+W).")
        close_project_action.triggered.connect(self._close_project)
        file_menu.addAction(close_project_action)

        file_menu.addSeparator()

        export_action = QAction("Export C Code...", self)
        export_action.setShortcut("Ctrl+E")
        self._apply_action_hint(export_action, "Export generated C code for the current project (Ctrl+E).")
        export_action.triggered.connect(self._export_code)
        file_menu.addAction(export_action)

        file_menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.setShortcut("Ctrl+Q")
        self._apply_action_hint(quit_action, "Quit EmbeddedGUI Designer (Ctrl+Q).")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

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
        self._apply_action_hint(self._align_left_action, "Align the current selection to the left edge of the primary widget.")
        self._align_left_action.triggered.connect(lambda: self._align_selection("left"))
        arrange_menu.addAction(self._align_left_action)

        self._align_right_action = QAction("Align Right", self)
        self._apply_action_hint(self._align_right_action, "Align the current selection to the right edge of the primary widget.")
        self._align_right_action.triggered.connect(lambda: self._align_selection("right"))
        arrange_menu.addAction(self._align_right_action)

        self._align_top_action = QAction("Align Top", self)
        self._apply_action_hint(self._align_top_action, "Align the current selection to the top edge of the primary widget.")
        self._align_top_action.triggered.connect(lambda: self._align_selection("top"))
        arrange_menu.addAction(self._align_top_action)

        self._align_bottom_action = QAction("Align Bottom", self)
        self._apply_action_hint(
            self._align_bottom_action,
            "Align the current selection to the bottom edge of the primary widget.",
        )
        self._align_bottom_action.triggered.connect(lambda: self._align_selection("bottom"))
        arrange_menu.addAction(self._align_bottom_action)

        self._align_hcenter_action = QAction("Align Horizontal Center", self)
        self._apply_action_hint(
            self._align_hcenter_action,
            "Align the current selection to the horizontal center of the primary widget.",
        )
        self._align_hcenter_action.triggered.connect(lambda: self._align_selection("hcenter"))
        arrange_menu.addAction(self._align_hcenter_action)

        self._align_vcenter_action = QAction("Align Vertical Center", self)
        self._apply_action_hint(
            self._align_vcenter_action,
            "Align the current selection to the vertical center of the primary widget.",
        )
        self._align_vcenter_action.triggered.connect(lambda: self._align_selection("vcenter"))
        arrange_menu.addAction(self._align_vcenter_action)

        arrange_menu.addSeparator()

        self._distribute_h_action = QAction("Distribute Horizontally", self)
        self._apply_action_hint(
            self._distribute_h_action,
            "Distribute the current selection evenly across the horizontal axis.",
        )
        self._distribute_h_action.triggered.connect(lambda: self._distribute_selection("horizontal"))
        arrange_menu.addAction(self._distribute_h_action)

        self._distribute_v_action = QAction("Distribute Vertically", self)
        self._apply_action_hint(
            self._distribute_v_action,
            "Distribute the current selection evenly across the vertical axis.",
        )
        self._distribute_v_action.triggered.connect(lambda: self._distribute_selection("vertical"))
        arrange_menu.addAction(self._distribute_v_action)

        arrange_menu.addSeparator()

        self._bring_front_action = QAction("Bring to Front", self)
        self._apply_action_hint(
            self._bring_front_action,
            "Bring the current selection to the front of its parent stack.",
        )
        self._bring_front_action.triggered.connect(self._move_selection_to_front)
        arrange_menu.addAction(self._bring_front_action)

        self._send_back_action = QAction("Send to Back", self)
        self._apply_action_hint(
            self._send_back_action,
            "Send the current selection to the back of its parent stack.",
        )
        self._send_back_action.triggered.connect(self._move_selection_to_back)
        arrange_menu.addAction(self._send_back_action)

        arrange_menu.addSeparator()

        self._toggle_lock_action = QAction("Toggle Lock", self)
        self._apply_action_hint(
            self._toggle_lock_action,
            "Toggle the designer lock state for the current selection.",
        )
        self._toggle_lock_action.triggered.connect(self._toggle_selection_locked)
        arrange_menu.addAction(self._toggle_lock_action)

        self._toggle_hide_action = QAction("Toggle Hide", self)
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
        self._group_selection_action.setShortcut("Ctrl+G")
        self._group_selection_action.triggered.connect(self._group_selection)
        structure_menu.addAction(self._group_selection_action)

        self._ungroup_selection_action = QAction("Ungroup", self)
        self._ungroup_selection_action.setShortcut("Ctrl+Shift+G")
        self._ungroup_selection_action.triggered.connect(self._ungroup_selection)
        structure_menu.addAction(self._ungroup_selection_action)

        self._move_into_container_action = QAction("Move Into...", self)
        self._move_into_container_action.setShortcut("Ctrl+Shift+I")
        self._move_into_container_action.triggered.connect(self._move_selection_into_container)
        structure_menu.addAction(self._move_into_container_action)

        self._move_into_last_target_action = QAction("Move Into Last Target", self)
        self._move_into_last_target_action.setShortcut("Ctrl+Alt+I")
        self._move_into_last_target_action.triggered.connect(self._move_selection_into_last_target)
        structure_menu.addAction(self._move_into_last_target_action)

        self._clear_move_target_history_action = QAction("Clear Move Target History", self)
        self._clear_move_target_history_action.triggered.connect(self._clear_move_target_history)
        structure_menu.addAction(self._clear_move_target_history_action)

        self._quick_move_into_menu = structure_menu.addMenu("Quick Move Into")
        self._quick_move_into_menu.setToolTipsVisible(True)
        self._quick_move_into_menu.aboutToShow.connect(self._refresh_quick_move_into_menu)

        self._lift_to_parent_action = QAction("Lift To Parent", self)
        self._lift_to_parent_action.setShortcut("Ctrl+Shift+L")
        self._lift_to_parent_action.triggered.connect(self._lift_selection_to_parent)
        structure_menu.addAction(self._lift_to_parent_action)

        structure_menu.addSeparator()

        self._move_up_action = QAction("Move Up", self)
        self._move_up_action.setShortcut("Alt+Up")
        self._move_up_action.triggered.connect(self._move_selection_up)
        structure_menu.addAction(self._move_up_action)

        self._move_down_action = QAction("Move Down", self)
        self._move_down_action.setShortcut("Alt+Down")
        self._move_down_action.triggered.connect(self._move_selection_down)
        structure_menu.addAction(self._move_down_action)

        self._move_top_action = QAction("Move To Top", self)
        self._move_top_action.setShortcut("Alt+Shift+Up")
        self._move_top_action.triggered.connect(self._move_selection_to_top)
        structure_menu.addAction(self._move_top_action)

        self._move_bottom_action = QAction("Move To Bottom", self)
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
            action.setToolTip(hint)
            action.setStatusTip(hint)
        self._quick_move_into_menu.menuAction().setToolTip(self._quick_move_into_menu_hint())
        self._quick_move_into_menu.menuAction().setStatusTip(self._quick_move_into_menu_hint())

        # 鈹€鈹€ Build menu 鈹€鈹€
        build_menu = menubar.addMenu("Build")
        self._build_menu = build_menu
        self._apply_action_hint(
            build_menu.menuAction(),
            "Compile previews, generate resources, and manage release builds.",
        )

        self._compile_action = QAction("Compile && Run", self)
        self._compile_action.setShortcut("F5")
        self._compile_action.triggered.connect(self._do_compile_and_run)
        build_menu.addAction(self._compile_action)

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

        self._release_build_action = QAction("Release Build...", self)
        self._apply_action_hint(self._release_build_action, "Build a release package for the current project.")
        self._release_build_action.triggered.connect(self._release_build)
        build_menu.addAction(self._release_build_action)

        self._release_profiles_action = QAction("Release Profiles...", self)
        self._apply_action_hint(self._release_profiles_action, "Edit release profiles for the current project.")
        self._release_profiles_action.triggered.connect(self._edit_release_profiles)
        build_menu.addAction(self._release_profiles_action)

        self._open_last_release_dir_action = QAction("Open Last Release Folder", self)
        self._open_last_release_dir_action.triggered.connect(self._open_last_release_folder)
        build_menu.addAction(self._open_last_release_dir_action)

        self._open_last_release_dist_action = QAction("Open Last Release Dist", self)
        self._open_last_release_dist_action.triggered.connect(self._open_last_release_dist)
        build_menu.addAction(self._open_last_release_dist_action)

        self._open_last_release_manifest_action = QAction("Open Last Release Manifest", self)
        self._open_last_release_manifest_action.triggered.connect(self._open_last_release_manifest)
        build_menu.addAction(self._open_last_release_manifest_action)

        self._open_last_release_version_action = QAction("Open Last Release Version", self)
        self._open_last_release_version_action.triggered.connect(self._open_last_release_version)
        build_menu.addAction(self._open_last_release_version_action)

        self._open_last_release_package_action = QAction("Open Last Release Package", self)
        self._open_last_release_package_action.triggered.connect(self._open_last_release_package)
        build_menu.addAction(self._open_last_release_package_action)

        self._open_last_release_log_action = QAction("Open Last Release Log", self)
        self._open_last_release_log_action.triggered.connect(self._open_last_release_log)
        build_menu.addAction(self._open_last_release_log_action)

        self._open_release_history_file_action = QAction("Open Release History File", self)
        self._open_release_history_file_action.triggered.connect(self._open_release_history_file)
        build_menu.addAction(self._open_release_history_file_action)

        self._release_history_action = QAction("Release History...", self)
        self._apply_action_hint(self._release_history_action, "Browse recorded release builds for the current project.")
        self._release_history_action.triggered.connect(self._show_release_history)
        build_menu.addAction(self._release_history_action)

        self._repo_health_action = QAction("Repository Health...", self)
        self._apply_action_hint(self._repo_health_action, "Inspect the Designer repository health summary.")
        self._repo_health_action.triggered.connect(self._show_repository_health)
        build_menu.addAction(self._repo_health_action)

        build_menu.addSeparator()

        self._generate_resources_action = QAction("Generate Resources", self)
        self._generate_resources_action.setToolTip(
            "Run resource generation (app_resource_generate.py) to produce\n"
            "C source files from .eguiproject/resources/ assets and widget config."
        )
        self._generate_resources_action.setStatusTip(self._generate_resources_action.toolTip())
        self._generate_resources_action.triggered.connect(self._generate_resources)
        build_menu.addAction(self._generate_resources_action)
        self._update_generate_resources_action_metadata()
        self._update_build_menu_metadata()

        # 鈹€鈹€ View menu 鈹€鈹€
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
            ("Status", "status"),
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
        tb.setIconSize(QSize(18, 18))
        tb.setToolButtonStyle(Qt.ToolButtonIconOnly)
        tb.setStyleSheet(
            "QToolBar { spacing: 6px; background: transparent; border: none; }"
            "QToolButton { padding: 6px 10px; border-radius: 10px; }"
        )
        self._toolbar_host_layout.addWidget(tb, 1)

        for action, icon_key in (
            (self._save_action, "save"),
            (self._undo_action, "undo"),
            (self._redo_action, "redo"),
            (self._copy_action, "properties"),
            (self._paste_action, "properties"),
            (self._compile_action, "compile"),
            (self._stop_action, "stop"),
        ):
            action.setIcon(make_icon(icon_key))

        self._insert_widget_button = PrimaryPushButton("Insert Widget")
        self._insert_widget_button.setIcon(make_icon("widgets"))
        self._insert_widget_button.clicked.connect(lambda: self._show_widget_browser_for_parent(self._default_insert_parent()))
        tb.addWidget(self._insert_widget_button)
        self._update_insert_widget_button_metadata()

        tb.addSeparator()
        tb.addAction(self._save_action)

        tb.addSeparator()

        tb.addAction(self._undo_action)
        tb.addAction(self._redo_action)
        tb.addAction(self._copy_action)
        tb.addAction(self._paste_action)

        tb.addSeparator()

        tb.addAction(self._compile_action)
        tb.addAction(self._stop_action)

        mode_host = QWidget()
        mode_layout = QHBoxLayout(mode_host)
        mode_layout.setContentsMargins(0, 0, 0, 0)
        mode_layout.setSpacing(6)
        self._mode_buttons = {}
        for label, mode, icon_key in (
            ("Design", MODE_DESIGN, "widgets"),
            ("Split", MODE_SPLIT, "layout"),
            ("Code", MODE_CODE, "page"),
        ):
            button = QPushButton(label)
            button.setCheckable(True)
            button.setIcon(make_icon(icon_key))
            button.clicked.connect(lambda checked=False, m=mode: self.editor_tabs.set_mode(m))
            self._mode_buttons[mode] = button
            mode_layout.addWidget(button)
        self._toolbar_host_layout.addWidget(mode_host, 0)
        self._update_editor_mode_button_metadata(self.editor_tabs.mode)

        chips_host = QWidget()
        chips_layout = QHBoxLayout(chips_host)
        chips_layout.setContentsMargins(0, 0, 0, 0)
        chips_layout.setSpacing(8)
        self._sdk_chip = QToolButton()
        self._sdk_chip.setAutoRaise(True)
        self._sdk_chip.clicked.connect(lambda checked=False: self._select_left_panel("status"))
        self._sdk_chip.setObjectName("workspace_status_chip")
        self._sdk_chip.setProperty("chipTone", "accent")
        self._dirty_chip = QToolButton()
        self._dirty_chip.setAutoRaise(True)
        self._dirty_chip.clicked.connect(lambda checked=False: self._show_bottom_panel("History"))
        self._dirty_chip.setObjectName("workspace_status_chip")
        self._dirty_chip.setProperty("chipTone", "success")
        self._selection_chip = QToolButton()
        self._selection_chip.setAutoRaise(True)
        self._selection_chip.clicked.connect(lambda checked=False: self._select_left_panel("structure"))
        self._selection_chip.setObjectName("workspace_status_chip")
        self._preview_chip = QToolButton()
        self._preview_chip.setAutoRaise(True)
        self._preview_chip.clicked.connect(lambda checked=False: self._show_bottom_panel("Debug Output"))
        self._preview_chip.setObjectName("workspace_status_chip")
        self._diagnostics_chip = QToolButton()
        self._diagnostics_chip.setAutoRaise(True)
        self._diagnostics_chip.clicked.connect(lambda checked=False: self._show_bottom_panel("Diagnostics"))
        self._diagnostics_chip.setObjectName("workspace_status_chip")
        self._diagnostics_chip.setProperty("chipTone", "warning")
        for chip in (self._sdk_chip, self._dirty_chip, self._selection_chip, self._preview_chip, self._diagnostics_chip):
            chips_layout.addWidget(chip)
        self._toolbar_host_layout.addWidget(chips_host, 0)

        self._toolbar = tb
        self._update_compile_availability()
        self._update_edit_actions()
        self._update_toolbar_action_metadata()
        self._apply_workspace_iconography()
        self._update_workspace_chips()

    # 鈹€鈹€ Theme 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    def _set_theme(self, theme):
        """Set the application theme and save to config."""
        apply_theme(QApplication.instance(), theme)
        self._config.theme = theme
        self._config.save()
        self._apply_workspace_iconography()
        self._update_view_and_theme_action_metadata()
        if hasattr(self, "widget_browser"):
            self.widget_browser.refresh()

    def _set_font_sizes(self):
        """Set a single font size for the entire UI."""
        current_size = self._config.font_size_px
        if not current_size or current_size <= 0:
            current_size = 9

        size, ok = QInputDialog.getInt(
            self, "Font Size", "Font size (pt):",
            value=current_size, min=6, max=48
        )
        if not ok:
            return

        # Apply via stylesheet (DPI-independent, overrides all widgets)
        app = QApplication.instance()
        base_ss = self._get_base_stylesheet(app)
        app.setStyleSheet(base_ss + f"\n* {{ font-size: {size}pt; }}")

        # Debug panel uses its own font
        self.debug_panel.set_output_font_size_pt(size)

        # Persist to config
        self._config.font_size_px = size
        self._config.save()
        self._update_view_and_theme_action_metadata()
        self.statusBar().showMessage(f"Font size set to {size}pt (saved)")

    def _get_base_stylesheet(self, app):
        """Get the base stylesheet without any font-size override."""
        ss = app.styleSheet()
        # Remove any previous font-size override line we added
        import re
        ss = re.sub(r'\n\*\s*\{\s*font-size:\s*\d+pt;\s*\}', '', ss)
        return ss

    # 鈹€鈹€ Project operations 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    def _update_recent_menu(self):
        """Update the Recent Projects submenu."""
        self._recent_menu.clear()
        recent = self._config.recent_projects
        if not recent:
            hint = "Open a recently used project. No recent projects are available."
            self._recent_menu.menuAction().setToolTip(hint)
            self._recent_menu.menuAction().setStatusTip(hint)
            action = QAction("(No recent projects)", self)
            action.setEnabled(False)
            action.setToolTip("No recent projects are available.")
            action.setStatusTip(action.toolTip())
            self._recent_menu.addAction(action)
            self._update_file_menu_metadata()
            return

        recent_count = min(len(recent), 10)
        noun = "project" if recent_count == 1 else "projects"
        hint = f"Open a recently used project. {recent_count} recent {noun} available."
        self._recent_menu.menuAction().setToolTip(hint)
        self._recent_menu.menuAction().setStatusTip(hint)

        for item in recent[:10]:
            project_path = item.get("project_path", "")
            sdk_root = self._resolve_ui_sdk_root(
                item.get("sdk_root", ""),
            )
            display_name = item.get("display_name") or os.path.splitext(os.path.basename(project_path))[0]
            project_exists = bool(project_path) and os.path.exists(project_path)
            action_label = display_name if project_exists else f"[Missing] {display_name}"
            action = QAction(action_label, self)
            tooltip = project_path
            if not project_exists:
                tooltip = f"{project_path}\nProject path is missing. Selecting it will offer to remove the stale entry."
            action.setToolTip(tooltip)
            action.setStatusTip(tooltip)
            action.triggered.connect(
                lambda checked, p=project_path, r=sdk_root: self._open_recent_project(p, r)
            )
            self._recent_menu.addAction(action)
        self._update_file_menu_metadata()

    def _release_output_root(self):
        if not self._project_dir:
            return ""
        return os.path.join(self._project_dir, "output", "ui_designer_release")

    def _latest_release_version_path(self, entry):
        if not isinstance(entry, dict):
            return ""
        dist_dir = normalize_path(entry.get("dist_dir", ""))
        release_root = normalize_path(entry.get("release_root", ""))
        for base_dir in (dist_dir, release_root):
            if not base_dir:
                continue
            candidate = normalize_path(os.path.join(base_dir, "VERSION.txt"))
            if candidate and os.path.isfile(candidate):
                return candidate
        return ""

    def _update_sdk_status_label(self):
        if not hasattr(self, "_sdk_status_label"):
            return
        sdk_root = self.project_root or self._active_sdk_root()
        binding_label = format_sdk_binding_label(sdk_root, _DESIGNER_REPO_ROOT)
        tooltip = sdk_root or "No SDK root configured"
        self._sdk_status_label.setText(binding_label)
        self._sdk_status_label.setToolTip(tooltip)
        self._sdk_status_label.setStatusTip(tooltip)
        self._sdk_status_label.setAccessibleName(f"SDK binding: {binding_label}.")
        self._update_workspace_chips()

    def _edit_release_profiles(self):
        if self.project is None:
            return
        dialog = ReleaseProfilesDialog(self.project.release_config, self)
        if dialog.exec_() != QDialog.Accepted:
            return
        self.project.release_config = dialog.release_config
        if self._project_dir:
            self.project.release_config.save(self._project_dir)
            self._refresh_project_watch_snapshot()
        self.statusBar().showMessage("Release profiles updated", 4000)
        self._update_compile_availability()

    def _open_path_in_shell(self, path):
        path = normalize_path(path)
        if not path or not os.path.exists(path):
            raise FileNotFoundError(path or "")
        if sys.platform == "win32":
            os.startfile(path)
            return
        opener = "open" if sys.platform == "darwin" else "xdg-open"
        subprocess.Popen([opener, path])

    def _open_last_release_folder(self):
        if not self._project_dir:
            return
        entry = latest_release_entry(self._project_dir, output_dir=self._release_output_root())
        release_root = normalize_path(entry.get("release_root", "")) if isinstance(entry, dict) else ""
        if not release_root:
            self.statusBar().showMessage("No release history available", 4000)
            return
        try:
            self._open_path_in_shell(release_root)
        except Exception as exc:
            QMessageBox.warning(self, "Open Release Folder Failed", str(exc))

    def _open_last_release_dist(self):
        if not self._project_dir:
            return
        entry = latest_release_entry(self._project_dir, output_dir=self._release_output_root())
        dist_dir = normalize_path(entry.get("dist_dir", "")) if isinstance(entry, dict) else ""
        if not dist_dir:
            self.statusBar().showMessage("No release dist directory available", 4000)
            return
        try:
            self._open_path_in_shell(dist_dir)
        except Exception as exc:
            QMessageBox.warning(self, "Open Release Dist Failed", str(exc))

    def _open_last_release_manifest(self):
        if not self._project_dir:
            return
        entry = latest_release_entry(self._project_dir, output_dir=self._release_output_root())
        manifest_path = normalize_path(entry.get("manifest_path", "")) if isinstance(entry, dict) else ""
        if not manifest_path:
            self.statusBar().showMessage("No release manifest available", 4000)
            return
        try:
            self._open_path_in_shell(manifest_path)
        except Exception as exc:
            QMessageBox.warning(self, "Open Release Manifest Failed", str(exc))

    def _open_last_release_version(self):
        if not self._project_dir:
            return
        entry = latest_release_entry(self._project_dir, output_dir=self._release_output_root())
        version_path = self._latest_release_version_path(entry)
        if not version_path:
            self.statusBar().showMessage("No release version file available", 4000)
            return
        try:
            self._open_path_in_shell(version_path)
        except Exception as exc:
            QMessageBox.warning(self, "Open Release Version Failed", str(exc))

    def _open_last_release_package(self):
        if not self._project_dir:
            return
        entry = latest_release_entry(self._project_dir, output_dir=self._release_output_root())
        zip_path = normalize_path(entry.get("zip_path", "")) if isinstance(entry, dict) else ""
        if not zip_path:
            self.statusBar().showMessage("No release package available", 4000)
            return
        try:
            self._open_path_in_shell(zip_path)
        except Exception as exc:
            QMessageBox.warning(self, "Open Release Package Failed", str(exc))

    def _open_last_release_log(self):
        if not self._project_dir:
            return
        entry = latest_release_entry(self._project_dir, output_dir=self._release_output_root())
        log_path = normalize_path(entry.get("log_path", "")) if isinstance(entry, dict) else ""
        if not log_path:
            self.statusBar().showMessage("No release log available", 4000)
            return
        try:
            self._open_path_in_shell(log_path)
        except Exception as exc:
            QMessageBox.warning(self, "Open Release Log Failed", str(exc))

    def _open_release_history_file(self):
        if not self._project_dir:
            return
        history_path = normalize_path(release_history_path(self._project_dir, output_dir=self._release_output_root()))
        if not history_path or not os.path.isfile(history_path):
            self.statusBar().showMessage("No release history file available", 4000)
            return
        try:
            self._open_path_in_shell(history_path)
        except Exception as exc:
            QMessageBox.warning(self, "Open Release History File Failed", str(exc))

    def _show_release_history(self):
        if not self._project_dir:
            return
        history_entries = load_release_history(self._project_dir, output_dir=self._release_output_root())
        dialog = ReleaseHistoryDialog(
            history_entries,
            open_path_callback=self._open_path_in_shell,
            history_path=release_history_path(self._project_dir, output_dir=self._release_output_root()),
            refresh_history_callback=lambda: load_release_history(self._project_dir, output_dir=self._release_output_root()),
            project_key=self._project_dir,
            parent=self,
        )
        dialog.exec_()

    def _show_repository_health(self):
        dialog = RepositoryHealthDialog(_DESIGNER_REPO_ROOT, open_path_callback=self._open_path_in_shell, parent=self)
        dialog.exec_()

    def _release_build(self):
        if self.project is None or not self._project_dir:
            return
        if not self._has_valid_sdk_root():
            QMessageBox.warning(self, "SDK Root Missing", "A valid EmbeddedGUI SDK root is required to build a release.")
            return

        self._flush_pending_xml()
        diagnostics = collect_release_diagnostics(self.project)
        warning_count = len(diagnostics["warnings"])
        dialog = ReleaseBuildDialog(
            self.project.release_config,
            format_sdk_binding_label(self.project_root, _DESIGNER_REPO_ROOT),
            self._release_output_root(),
            warning_count,
            self,
        )
        if dialog.exec_() != QDialog.Accepted:
            return

        self._save_project()
        if not self._project_dir:
            return

        profile = self.project.release_config.get_profile(dialog.selected_profile_id)
        result = release_project(
            ReleaseRequest(
                project=self.project,
                project_dir=self._project_dir,
                sdk_root=self.project_root,
                profile=profile,
                designer_root=_DESIGNER_REPO_ROOT,
                output_dir=self._release_output_root(),
                warnings_as_errors=dialog.warnings_as_errors,
                package_release=dialog.package_release,
            )
        )
        self._update_compile_availability()
        designer_revision = str(getattr(result, "designer_revision", "") or "").strip()
        sdk = getattr(result, "sdk", {})
        sdk_source_kind = ""
        sdk_revision = ""
        if isinstance(sdk, dict):
            sdk_source_kind = str(sdk.get("source_kind") or "").strip()
            sdk_revision = str(sdk.get("revision") or sdk.get("commit_short") or sdk.get("commit") or "").strip()
        if result.success:
            self.statusBar().showMessage(result.message, 5000)
            summary_lines = [result.message]
            if result.build_id:
                summary_lines.extend(["", "Build ID:", result.build_id])
            if result.profile_id:
                summary_lines.extend(["", "Profile:", result.profile_id])
            summary_lines.extend(["", "Manifest:", result.manifest_path])
            if result.history_path:
                summary_lines.extend(["", "History:", result.history_path])
            if result.zip_path:
                summary_lines.extend(["", "Package:", result.zip_path])
            if designer_revision:
                summary_lines.extend(["", "Designer Revision:", designer_revision])
            if sdk_source_kind:
                summary_lines.extend(["", "SDK Source:", sdk_source_kind])
            if sdk_revision:
                summary_lines.extend(["", "SDK Revision:", sdk_revision])
            QMessageBox.information(
                self,
                "Release Build Succeeded",
                "\n".join(summary_lines),
            )
            return

        self.debug_panel.log_error(result.message)
        self.debug_panel.log_error(f"Release log: {result.log_path}")
        self._show_bottom_panel("Debug Output")
        self.statusBar().showMessage(result.message, 5000)
        summary_lines = [result.message]
        if result.build_id:
            summary_lines.extend(["", "Build ID:", result.build_id])
        if result.profile_id:
            summary_lines.extend(["", "Profile:", result.profile_id])
        if result.manifest_path:
            summary_lines.extend(["", "Manifest:", result.manifest_path])
        if result.history_path:
            summary_lines.extend(["", "History:", result.history_path])
        if result.log_path:
            summary_lines.extend(["", "Log:", result.log_path])
        if designer_revision:
            summary_lines.extend(["", "Designer Revision:", designer_revision])
        if sdk_source_kind:
            summary_lines.extend(["", "SDK Source:", sdk_source_kind])
        if sdk_revision:
            summary_lines.extend(["", "SDK Revision:", sdk_revision])
        QMessageBox.warning(self, "Release Build Failed", "\n".join(summary_lines))

    def _open_app_dialog(self):
        """Show dialog to select and open an SDK example."""
        dialog = AppSelectorDialog(self, self._active_sdk_root(), on_download_sdk=self._download_sdk)
        if dialog.exec_() != QDialog.Accepted:
            return

        entry = dialog.selected_entry
        sdk_root = normalize_path(dialog.egui_root)
        if not entry:
            return

        self.project_root = sdk_root
        self._config.sdk_root = sdk_root
        self._config.egui_root = sdk_root
        self._config.save()

        if entry.get("has_project"):
            try:
                self._open_project_path(entry.get("project_path", ""), preferred_sdk_root=sdk_root)
            except Exception as exc:
                QMessageBox.critical(self, "Error", f"Failed to open SDK example:\n{exc}")
            return

        try:
            self._import_legacy_example(entry, sdk_root)
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to import legacy example:\n{exc}")

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

    def _download_sdk(self):
        target_dir = default_sdk_install_dir()
        progress = QProgressDialog(f"Preparing SDK download...\nTarget: {target_dir}", "Cancel", 0, 100, self)
        progress.setWindowTitle("Download EmbeddedGUI SDK")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setValue(0)

        def on_progress(message, percent):
            if progress.wasCanceled():
                raise RuntimeError("SDK download canceled by user")
            progress.setLabelText(message)
            if percent is not None:
                progress.setValue(max(0, min(100, percent)))
            QApplication.processEvents()

        try:
            sdk_root = ensure_sdk_downloaded(target_dir, progress_callback=on_progress)
        except Exception as exc:
            progress.close()
            QMessageBox.warning(
                self,
                "Download SDK Failed",
                "Failed to prepare an EmbeddedGUI SDK automatically.\n\n"
                f"Target location:\n{target_dir}\n\n"
                f"Automatic setup order: {AUTO_DOWNLOAD_STRATEGY_TEXT}\n\n"
                f"{exc}\n\n"
                "You can try again later, install git for clone fallback, or select an existing SDK root manually.",
            )
            return ""

        progress.setValue(100)
        progress.close()
        self._apply_sdk_root(sdk_root, status_message=self._format_sdk_status_message("SDK downloaded to", sdk_root))
        return sdk_root

    def maybe_prompt_initial_sdk_setup(self):
        if self._has_valid_sdk_root() or self._config.sdk_setup_prompted:
            return

        self._config.sdk_setup_prompted = True
        self._config.save()

        dialog = QMessageBox(self)
        dialog.setWindowTitle("Prepare EmbeddedGUI SDK")
        dialog.setIcon(QMessageBox.Information)
        dialog.setText("No EmbeddedGUI SDK was detected.")
        target_dir = default_sdk_install_dir()
        dialog.setInformativeText(
            "Designer can download a local SDK copy automatically.\n"
            f"Target location:\n{target_dir}\n\n"
            f"Automatic setup order: {AUTO_DOWNLOAD_STRATEGY_TEXT}\n"
            "You can also point Designer to an existing SDK root."
        )
        download_btn = dialog.addButton("Download SDK Automatically", QMessageBox.AcceptRole)
        select_btn = dialog.addButton("Select SDK Root...", QMessageBox.ActionRole)
        dialog.addButton("Skip for Now", QMessageBox.RejectRole)
        dialog.exec_()

        clicked = dialog.clickedButton()
        if clicked == download_btn:
            self._download_sdk()
        elif clicked == select_btn:
            self._set_sdk_root()

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

    def _import_legacy_example(self, entry, sdk_root):
        app_name = entry.get("app_name", "")
        app_dir = normalize_path(entry.get("app_dir", ""))
        project_path = normalize_path(os.path.join(app_dir, f"{app_name}.egui"))
        eguiproject_dir = os.path.join(app_dir, ".eguiproject")

        if os.path.exists(eguiproject_dir) and not os.path.isfile(project_path):
            QMessageBox.warning(
                self,
                "Legacy Example Conflict",
                "This example already contains a .eguiproject directory but has no .egui file. Please resolve the directory conflict manually before importing it into Designer.",
            )
            return

        project = self._create_standard_project_model(app_name, sdk_root, app_dir)
        self._scaffold_project_directory(app_dir, app_name, project.screen_width, project.screen_height)
        project.save(app_dir)
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
        if dirty_pages:
            title += " *"
        self.setWindowTitle(title)
        self._update_history_panel()
        self._update_diagnostics_panel()
        self._update_workspace_chips()
        self._update_file_menu_metadata()

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

        # Reuse config-side recovery so legacy repo-local caches still work.
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
            self._config.egui_root,
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

        sdk_root = self._resolve_ui_sdk_root(sdk_root)
        if is_valid_sdk_root(sdk_root):
            return os.path.join(sdk_root, "example")

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

        sdk_root = self._active_sdk_root()
        if sdk_root:
            return os.path.join(sdk_root, "example")

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
            mockup_path = os.path.join(self._project_dir, ".eguiproject", self._current_page.mockup_image_path)
            mockup_dir = normalize_path(os.path.dirname(mockup_path))
            if os.path.isdir(mockup_dir):
                return mockup_dir

        if self._project_dir:
            mockup_dir = os.path.join(self._project_dir, ".eguiproject", "mockup")
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

        os.makedirs(project_dir, exist_ok=True)
        project = Project(screen_width=dialog.screen_width, screen_height=dialog.screen_height, app_name=dialog.app_name)
        project.sdk_root = sdk_root
        project.project_dir = project_dir
        project.create_new_page("main_page")
        self._scaffold_project_directory(project_dir, dialog.app_name, dialog.screen_width, dialog.screen_height)
        project.save(project_dir)
        self._open_loaded_project(project, project_dir, preferred_sdk_root=sdk_root)
        self.statusBar().showMessage(f"Created project: {dialog.app_name}")

    def _open_project_path(self, path, preferred_sdk_root="", silent=False):
        path = normalize_path(path)
        if not path:
            raise FileNotFoundError("Project path is empty")
        if not os.path.exists(path):
            raise FileNotFoundError(path)

        project = Project.load(path)
        project_dir = path if os.path.isdir(path) else os.path.dirname(path)
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

    def _save_project_files(self, project_dir):
        self.project.project_dir = project_dir
        self.project.sdk_root = self.project_root
        self._scaffold_project_directory(project_dir, self.project.app_name, self.project.screen_width, self.project.screen_height)
        self.project.save(project_dir)

        files = generate_all_files_preserved(self.project, project_dir, backup=True)
        for filename, content in files.items():
            filepath = os.path.join(project_dir, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
        return files

    def _save_project(self):
        if self.project is None:
            self.statusBar().showMessage("No project to save")
            return

        self._flush_pending_xml()

        if not self._project_dir:
            self._save_project_as()
            return

        os.makedirs(self._project_dir, exist_ok=True)
        files = self._save_project_files(self._project_dir)
        self._bump_async_generation()
        self._shutdown_async_activity()
        self._recreate_compiler()
        self._undo_manager.mark_all_saved()
        self._persist_current_project_to_config()
        self._refresh_project_watch_snapshot()
        self._update_window_title()
        self._update_compile_availability()
        self.statusBar().showMessage(f"Saved: {self._project_dir} ({len(files)} code file(s) updated)")

    def _save_project_as(self):
        if self.project is None:
            self.statusBar().showMessage("No project to save")
            return

        path = QFileDialog.getExistingDirectory(self, "Save Project To Directory", self._default_save_project_as_dir())
        if not path:
            return

        path = normalize_path(path)
        if self._has_directory_conflict(path, allow_current=True):
            self._show_directory_conflict(path, "The selected directory already exists")
            return

        old_project_dir = self._project_dir
        os.makedirs(path, exist_ok=True)
        self._copy_project_sidecar_files(old_project_dir, path)
        files = self._save_project_files(path)
        self._project_dir = path
        self.project.project_dir = path
        self._bump_async_generation()
        self._shutdown_async_activity()
        self._recreate_compiler()
        self._undo_manager.mark_all_saved()
        self._persist_current_project_to_config()
        self._refresh_project_watch_snapshot()
        self._update_window_title()
        self._update_compile_availability()
        self.statusBar().showMessage(f"Saved: {path} ({len(files)} code file(s) updated)")

    def _close_project(self):
        """Close current project and return to welcome page."""
        if self.project is None:
            self._show_welcome_page()
            return

        if self._undo_manager.is_any_dirty():
            reply = QMessageBox.question(
                self, "Close Project",
                "There are unsaved changes. Do you want to save before closing?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save
            )

            if reply == QMessageBox.Cancel:
                return
            if reply == QMessageBox.Save:
                self._save_project()

        self._bump_async_generation()
        self._shutdown_async_activity()
        if self.compiler is not None:
            self.compiler.stop_exe()
            self.compiler.cleanup()
            self.compiler = None

        self._project_watch_snapshot = {}
        self._external_reload_pending = False
        self.project = None
        self._project_dir = None
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
        files = generate_all_files_preserved(
            self.project, path, backup=True,
        )
        for filename, content in files.items():
            filepath = os.path.join(path, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
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
        eguiproject_dir = os.path.join(self._project_dir, ".eguiproject")
        mockup_dir = os.path.join(eguiproject_dir, "mockup")
        os.makedirs(mockup_dir, exist_ok=True)
        filename = os.path.basename(path)
        dest = os.path.join(mockup_dir, filename)
        # Handle name collision
        if os.path.abspath(path) != os.path.abspath(dest):
            base, ext = os.path.splitext(filename)
            counter = 1
            while os.path.isfile(dest):
                dest = os.path.join(mockup_dir, f"{base}_{counter}{ext}")
                filename = f"{base}_{counter}{ext}"
                counter += 1
            shutil.copy2(path, dest)

        # Store relative path (relative to .eguiproject/)
        rel_path = f"mockup/{filename}"
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
                eguiproject_dir = os.path.join(self._project_dir, ".eguiproject")
                full_path = os.path.join(eguiproject_dir, self._current_page.mockup_image_path)
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
            eguiproject_dir = os.path.join(self._project_dir, ".eguiproject")
            full_path = os.path.join(eguiproject_dir, path)
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

        # Load project-level custom widget plugins
        if self._project_dir:
            from ..model.widget_registry import WidgetRegistry
            custom_dir = os.path.join(self._project_dir, ".eguiproject", "custom_widgets")
            WidgetRegistry.instance().load_custom_widgets(custom_dir)

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
        if self.compiler is None or not self.compiler.can_build():
            reason = "SDK unavailable, compile preview disabled"
            if self.compiler is not None and self.compiler.get_build_error():
                reason = self.compiler.get_build_error()
            self._switch_to_python_preview(reason)
            return
        if self._precompile_worker is not None and self._precompile_worker.isRunning():
            return
        if not self.compiler.is_exe_ready():
            self.statusBar().showMessage("Background compiling...")
            self.debug_panel.log_action("Starting background precompile...")
            self.debug_panel.log_cmd(
                f"make -j main.exe APP={self.app_name} PORT=designer EGUI_APP_ROOT_PATH={self.compiler.app_root_arg} COMPILE_DEBUG= COMPILE_OPT_LEVEL=-O0"
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
        if success:
            self.statusBar().showMessage("Ready (precompiled)", 3000)
            self.debug_panel.log_success("Background precompile completed")
        else:
            self.statusBar().showMessage("Precompile failed", 5000)
            self.debug_panel.log_error("Background precompile failed")
            self.debug_panel.log_compile_output(False, message)
            self._show_bottom_panel("Debug Output")

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
        if self._project_dir:
            return os.path.join(self._project_dir, "resource")
        return ""

    def _get_eguiproject_resource_dir(self):
        """Compute the .eguiproject/resources/ path for the current project.

        This is the authoritative directory for all source resource files.
        Used by the resource panel for browsing and importing.
        """
        if self._project_dir:
            return os.path.join(self._project_dir, ".eguiproject", "resources")
        return ""

    def _get_eguiproject_images_dir(self):
        """Compute the .eguiproject/resources/images/ path.

        Authoritative directory for source image files.
        Used for Page XML image path resolution.
        """
        res_dir = self._get_eguiproject_resource_dir()
        return os.path.join(res_dir, "images") if res_dir else ""

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
        self._finalize_resource_reference_change(touched_pages, source=f"{res_type} resource rename")

    def _on_resource_deleted(self, res_type, filename):
        """Clear widget references after a resource file was deleted."""
        touched_pages = self._rewrite_resource_references(res_type, filename, "")
        self._finalize_resource_reference_change(touched_pages, source=f"{res_type} resource delete")

    def _on_string_key_deleted(self, key, replacement_text):
        """Rewrite widget text references after a string key was deleted."""
        touched_pages, _ = rewrite_project_string_references(
            self.project,
            key,
            replacement_text=replacement_text,
        )
        self._finalize_resource_reference_change(touched_pages, source="string key delete")

    def _on_string_key_renamed(self, old_key, new_key):
        """Rewrite widget text references after a string key was renamed."""
        touched_pages, _ = rewrite_project_string_references(
            self.project,
            old_key,
            new_key=new_key,
        )
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
        # Auto-trigger resource generation with debounce
        self._refresh_project_watch_snapshot()
        self._regen_timer.start()
        current_message = self.statusBar().currentMessage()
        if not current_message.startswith("Updated resources in "):
            self.statusBar().showMessage("Resources changed, will regenerate...")

    def _on_resource_feedback_message(self, message):
        if message:
            self.statusBar().showMessage(message, 5000)

    def _on_resource_usage_activated(self, page_name, widget_name):
        if not self.project or not page_name or not widget_name:
            return
        if self._current_page is None or self._current_page.name != page_name:
            self._switch_page(page_name)
        target_page = self.project.get_page_by_name(page_name)
        target_widget = self._find_widget_in_page(target_page, widget_name)
        if target_widget is not None:
            self._set_selection([target_widget], primary=target_widget, sync_tree=True, sync_preview=True)
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
        if not assign_resource_to_widget(widget, res_type, filename):
            return
        self.property_panel.set_selection(self._selection_state.widgets, self._selection_state.primary)
        self._update_resource_usage_panel()
        self._on_model_changed(source=f"{res_type} resource drop")

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
        src_dir = os.path.join(res_dir, "src") if res_dir else ""
        if not res_dir or not eguiproject_res_dir or not os.path.isdir(eguiproject_res_dir):
            if not silent:
                QMessageBox.warning(
                    self,
                    "Error",
                    "No .eguiproject/resources directory found.\nPlease import resources first.",
                )
            return False

        self.project.sync_resources_to_src(self._project_dir)

        try:
            ResourceConfigGenerator().generate_and_save(self.project, src_dir)
        except Exception as exc:
            self.debug_panel.log_error(f"Resource config generation failed: {exc}")
            if not silent:
                QMessageBox.warning(self, "Error", f"Failed to generate resource config:\n{exc}")
            return False

        import subprocess
        import sys

        gen_script = os.path.join(self.project_root, "scripts", "tools", "app_resource_generate.py")
        if not os.path.isfile(gen_script):
            if not silent:
                QMessageBox.warning(self, "Error", f"Cannot find resource generator:\n{gen_script}")
            self.debug_panel.log_error(f"Resource generation skipped: missing generator {gen_script}")
            return False

        output_dir = os.path.join(self.project_root, "output")
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
        """Run the resource generation pipeline.

        Steps:
        1. Sync .eguiproject/resources/ -> resource/src/
        2. Generate app_resource_config.json from layout XML (ResourceConfigGenerator)
        3. Run app_resource_generate.py to produce C source files

        Args:
            silent: If True, suppress warning dialogs (used for auto-trigger).
        """
        self.statusBar().showMessage("Generating resources...")
        if self._run_resource_generation(silent=silent):
            self.statusBar().showMessage("Resource generation completed.")
        else:
            self.statusBar().showMessage("Resource generation FAILED.")

    def _ensure_resources_generated(self):
        """Generate app_resource_config.json from widget properties and run
        app_resource_generate.py if .eguiproject/resources/ exists.

        Called before each compile to ensure resource C files are up-to-date.
        Skips entirely when resources haven't changed since last generation.
        Runs silently 鈥?errors are logged to debug panel only.
        """
        if not self._resources_need_regen:
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
        self._trigger_compile()
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
        return os.path.join(self._project_dir, f"{page.name}.c")

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

        begin_marker = "// USER CODE BEGIN callbacks"
        end_marker = "// USER CODE END callbacks"
        begin_index = content.find(begin_marker)
        end_index = content.find(end_marker)
        if begin_index < 0 or end_index < begin_index:
            return content, False

        body_start = content.find("\n", begin_index)
        if body_start < 0 or body_start >= end_index:
            return content, False

        callback_body = content[body_start + 1:end_index]
        if callback_body.strip():
            new_body = callback_body.rstrip() + "\n\n" + stub + "\n"
        else:
            new_body = stub + "\n"
        updated = content[:body_start + 1] + new_body + content[end_index:]
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
        self._trigger_compile()

    def _on_page_duplicated(self, source_name, page_name):
        """User requested duplicating an existing page."""
        if not self.project:
            return
        self.project.duplicate_page(source_name, page_name)
        self.project_dock.set_project(self.project)
        self._refresh_page_navigator()
        self._ensure_page_tab(page_name)
        self._switch_page(page_name)
        self._trigger_compile()

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
                delete_page_generated_files(self._project_dir, page_name)
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
            self._trigger_compile()
            self._update_window_title()
            self._update_edit_actions()

    def _on_page_renamed(self, old_name, new_name):
        """User renamed a page."""
        if not self.project:
            return
        page = self.project.get_page_by_name(old_name)
        if page:
            was_current = self._current_page is not None and self._current_page.name == old_name
            page.file_path = f"layout/{new_name}.xml"
            # Update startup_page reference if needed
            if self.project.startup_page == old_name:
                self.project.startup_page = new_name
            self._undo_manager.rename_stack(old_name, new_name)
            self.project_dock.set_project(self.project)
            self._refresh_page_navigator()
            self._rename_page_tab(old_name, new_name)
            if was_current:
                self._switch_page(new_name)
            elif self._current_page:
                self.project_dock.set_current_page(self._current_page.name)
                self.page_navigator.set_current_page(self._current_page.name)
                self._trigger_compile()
                self._update_edit_actions()

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

    def _on_startup_changed(self, page_name):
        """User changed the startup page."""
        if self.project:
            self.project.startup_page = page_name
            self.project_dock.set_project(self.project)
            self.page_navigator.set_startup_page(page_name)
            self._update_page_tab_bar_metadata()
            self._update_workspace_chips()
            self._trigger_compile()

    def _on_page_mode_changed(self, mode):
        """User switched between easy_page and activity mode."""
        if self.project:
            self.project.page_mode = mode
            self._trigger_compile()

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
            self._move_into_last_target_action,
            self._clear_move_target_history_action,
        ):
            structure_menu.addAction(action)
        quick_move_menu = structure_menu.addMenu("Quick Move Into")
        quick_move_menu.setToolTipsVisible(True)
        self._populate_quick_move_into_menu(quick_move_menu)
        if hasattr(self, "_quick_move_into_menu"):
            source_quick_move_action = self._quick_move_into_menu.menuAction()
            preview_quick_move_action = quick_move_menu.menuAction()
            preview_quick_move_action.setEnabled(source_quick_move_action.isEnabled())
            preview_quick_move_action.setToolTip(source_quick_move_action.toolTip())
            preview_quick_move_action.setStatusTip(source_quick_move_action.statusTip())
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
                self._move_into_last_target_action,
                self._clear_move_target_history_action,
                quick_move_menu.menuAction(),
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

    def _set_selection(self, widgets=None, primary=None, sync_tree=True, sync_preview=True):
        self._selection_state.set_widgets(widgets or [], primary=primary)
        self._selected_widget = self._selection_state.primary
        self.property_panel.set_selection(self._selection_state.widgets, self._selection_state.primary)
        self.animations_panel.set_selection(self._selection_state.widgets, self._selection_state.primary)
        if sync_tree:
            self.widget_tree.set_selected_widgets(self._selection_state.widgets, self._selection_state.primary)
        if sync_preview:
            self.preview_panel.set_selection(self._selection_state.widgets, self._selection_state.primary)
        self._update_edit_actions()
        self._update_diagnostics_panel()
        self._show_selection_feedback()
        self._update_widget_browser_target()
        if hasattr(self, "widget_browser") and self._selection_state.primary is not None:
            self.widget_browser.select_widget_type(self._selection_state.primary.widget_type)
        self._update_workspace_chips()

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
        repeat_target = self._repeat_move_target_summary(widgets)
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
                if repeat_target:
                    return f"Selection note: Ctrl+Alt+I repeats move into {repeat_target}."
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
            if repeat_target:
                return f"Selection note: Ctrl+Alt+I repeats move into {repeat_target}."
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

    def _remembered_move_target_label(self):
        if not hasattr(self, "widget_tree") or self.widget_tree is None:
            return ""
        return self.widget_tree.remembered_move_target_label()

    def _recent_move_target_labels(self):
        if not hasattr(self, "widget_tree") or self.widget_tree is None:
            return []
        return self.widget_tree.recent_move_target_labels()

    def _set_remembered_move_target_label(self, label):
        if hasattr(self, "widget_tree") and self.widget_tree is not None:
            self.widget_tree.set_remembered_move_target_label(label)

    def _remember_move_target_label(self, label):
        if hasattr(self, "widget_tree") and self.widget_tree is not None:
            self.widget_tree.remember_move_target_label(label)

    def _remember_move_target(self, target_widget=None, label=""):
        if hasattr(self, "widget_tree") and self.widget_tree is not None:
            self.widget_tree.remember_move_target(target_widget, label)

    def _move_into_choices(self, widgets=None):
        return available_move_targets(self._structure_project_context(), widgets or self._top_level_selected_widgets())

    def _quick_move_into_choices(self, widgets=None):
        choices = self._move_into_choices(widgets)
        recent_labels = self._recent_move_target_labels()
        if not recent_labels:
            return choices

        choice_by_label = {choice.label: choice for choice in choices}
        prioritized = [choice_by_label[label] for label in recent_labels if label in choice_by_label]
        if not prioritized:
            return choices
        prioritized_labels = {choice.label for choice in prioritized}
        return prioritized + [choice for choice in choices if choice.label not in prioritized_labels]

    def _recent_move_into_choices(self, widgets=None):
        choices = self._move_into_choices(widgets)
        if not choices:
            return []
        choice_by_label = {choice.label: choice for choice in choices}
        return [choice_by_label[label] for label in self._recent_move_target_labels() if label in choice_by_label]

    def _remaining_move_into_choices(self, widgets=None):
        choices = self._move_into_choices(widgets)
        recent_labels = {choice.label for choice in self._recent_move_into_choices(widgets)}
        return [choice for choice in choices if choice.label not in recent_labels]

    def _move_into_target_default_index(self, choices):
        remembered_label = self._remembered_move_target_label()
        if not remembered_label:
            return 0
        for index, choice in enumerate(choices):
            if choice.label == remembered_label:
                return index
        return 0

    def _resolve_move_target_label(self, widgets, target_widget):
        for choice in self._move_into_choices(widgets):
            if choice.widget is target_widget:
                return choice.label
        return ""

    def _remembered_move_target_choice(self, widgets=None):
        remembered_label = self._remembered_move_target_label()
        if not remembered_label:
            return None
        for choice in self._move_into_choices(widgets):
            if choice.label == remembered_label:
                return choice
        return None

    def _move_into_last_target_reason(self, widgets=None):
        if not self._remembered_move_target_label():
            return "move something into a container first."
        if self._remembered_move_target_choice(widgets) is None:
            return "the last target is not available for the current selection."
        return ""

    def _move_into_last_target_hint(self, widgets=None):
        shortcut = ""
        if hasattr(self, "_move_into_last_target_action"):
            shortcut = self._move_into_last_target_action.shortcut().toString()
        choice = self._remembered_move_target_choice(widgets)
        label = choice.label if choice is not None else self._remembered_move_target_label()
        suffix = f" ({shortcut})" if shortcut else ""
        if label:
            return f"Move the current selection into {label} again{suffix}"
        return f"Move the current selection into the last remembered container target{suffix}"

    def _clear_move_target_history_hint(self):
        count = len(self._recent_move_target_labels())
        if count:
            noun = "target" if count == 1 else "targets"
            return f"Forget {count} recent move-into {noun} for the current page"
        return "Forget recent move-into targets for the current page"

    def _quick_move_into_menu_hint(self):
        available_count = len(self._quick_move_into_choices())
        available_label = "none" if available_count == 0 else f"{available_count} available"
        remembered_target = self._repeat_move_target_summary() or "none"
        recent_count = len(self._recent_move_target_labels())
        recent_label = (
            "none"
            if recent_count == 0
            else f"{recent_count} target" if recent_count == 1 else f"{recent_count} targets"
        )
        return (
            "Move directly into an available container target, or manage move-target history. "
            f"Targets: {available_label}. Remembered target: {remembered_target}. Recent history: {recent_label}."
        )

    def _repeat_move_target_summary(self, widgets=None):
        choice = self._remembered_move_target_choice(widgets)
        if choice is None:
            return ""
        return getattr(choice.widget, "name", "") or choice.label

    def _refresh_quick_move_into_menu(self):
        if not hasattr(self, "_quick_move_into_menu"):
            return

        self._populate_quick_move_into_menu(self._quick_move_into_menu)

    def _add_quick_move_into_action(self, menu, choice):
        action = QAction(choice.label, self)
        action.setToolTip(f"Move the current selection into {choice.label}.")
        action.setStatusTip(f"Move the current selection into {choice.label}.")
        action.triggered.connect(
            lambda checked=False, target=choice.widget, target_label=choice.label: self._move_selection_into_target(
                target,
                target_label=target_label,
            )
        )
        menu.addAction(action)

    def _add_quick_move_into_section(self, menu, title):
        section_action = QAction(title, menu)
        section_action.setEnabled(False)
        menu.addAction(section_action)

    def _add_quick_move_into_note(self, menu, text, tooltip=""):
        note_action = QAction(text, menu)
        note_action.setEnabled(False)
        if tooltip:
            note_action.setToolTip(tooltip)
            note_action.setStatusTip(tooltip)
        menu.addAction(note_action)

    def _add_quick_move_history_actions(self, menu):
        widgets = self._top_level_selected_widgets()

        move_into_last_target_action = QAction("Move Into Last Target", self)
        move_into_last_target_choice = self._remembered_move_target_choice(widgets)
        move_into_last_target_action.setEnabled(move_into_last_target_choice is not None)
        move_into_last_target_action.setToolTip(
            self._structure_action_hint(
                self._move_into_last_target_hint(widgets),
                move_into_last_target_choice is not None,
                self._move_into_last_target_reason(widgets),
            )
        )
        move_into_last_target_action.setStatusTip(move_into_last_target_action.toolTip())
        move_into_last_target_action.triggered.connect(self._move_selection_into_last_target)
        menu.addAction(move_into_last_target_action)

        clear_move_target_history_action = QAction("Clear Move Target History", self)
        has_recent_move_targets = bool(self._recent_move_target_labels())
        clear_move_target_history_action.setEnabled(has_recent_move_targets)
        clear_move_target_history_action.setToolTip(
            self._structure_action_hint(
                self._clear_move_target_history_hint(),
                has_recent_move_targets,
                "no recent move targets are saved.",
            )
        )
        clear_move_target_history_action.setStatusTip(clear_move_target_history_action.toolTip())
        clear_move_target_history_action.triggered.connect(self._clear_move_target_history)
        menu.addAction(clear_move_target_history_action)

    def _populate_quick_move_into_menu(self, menu):
        menu.clear()
        recent_choices = self._recent_move_into_choices()
        remaining_choices = self._remaining_move_into_choices()

        if recent_choices:
            self._add_quick_move_into_section(menu, "Recent Targets")
            for choice in recent_choices:
                self._add_quick_move_into_action(menu, choice)
            if remaining_choices:
                menu.addSeparator()
                self._add_quick_move_into_section(menu, "Other Targets")
        elif remaining_choices:
            self._add_quick_move_into_section(menu, "Recent Targets")
            self._add_quick_move_into_note(
                menu,
                "(No recent targets yet)",
                "Move something into a container first to build recent targets for this page.",
            )
            menu.addSeparator()
            self._add_quick_move_into_section(menu, "Other Targets")
        for choice in remaining_choices:
            self._add_quick_move_into_action(menu, choice)
        if not recent_choices and not remaining_choices:
            self._add_quick_move_into_note(menu, "(No eligible target containers)")
        if menu.actions():
            menu.addSeparator()
        self._add_quick_move_into_section(menu, "History")
        self._add_quick_move_history_actions(menu)

    def _move_selection_into_target(self, target, target_label=""):
        if target is None:
            return
        widgets = self._top_level_selected_widgets()
        if not target_label:
            target_label = self._resolve_move_target_label(widgets, target)
        if self._apply_structure_result(move_into_container(self._structure_project_context(), widgets, target)) and target_label:
            self._remember_move_target(target, target_label)

    def _move_selection_into_last_target(self):
        widgets = self._top_level_selected_widgets()
        target_choice = self._remembered_move_target_choice(widgets)
        if target_choice is None:
            reason = self._move_into_last_target_reason(widgets).rstrip(".")
            if reason:
                self._show_selection_action_blocked("move into last target", reason)
            return
        self._move_selection_into_target(target_choice.widget, target_label=target_choice.label)

    def _clear_move_target_history(self):
        if not self._recent_move_target_labels():
            self._show_selection_action_blocked("clear move target history", "no recent move targets are saved")
            return
        cleared_count = len(self._recent_move_target_labels())
        self.widget_tree.clear_remembered_move_target_labels()
        self._update_edit_actions()
        self.statusBar().showMessage(self._cleared_move_target_history_message(cleared_count), 4000)

    def _choose_structure_target_choice(self, widgets):
        choices = self._quick_move_into_choices(widgets)
        if not choices:
            self._show_selection_action_blocked("move into container", "no eligible target containers are available")
            return None

        labels = [choice.label for choice in choices]
        selected_label, ok = QInputDialog.getItem(
            self,
            "Move Into Container",
            "Target container (recent targets first):",
            labels,
            self._move_into_target_default_index(choices),
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

    def _cleared_move_target_history_text(self, count):
        noun = "target" if count == 1 else "targets"
        return f"cleared {count} recent move {noun}"

    def _cleared_move_target_history_message(self, count):
        noun = "target" if count == 1 else "targets"
        return f"Cleared {count} recent move {noun}."

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
        deleted_count, skipped_locked, removed_targets = self._delete_selection()
        if deleted_count:
            message = f"Cut {deleted_count} widget(s)"
            if removed_targets:
                message += f"; {self._cleared_move_target_history_text(removed_targets)}"
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
            return 0, locked_count, 0

        removed_targets = self.widget_tree.forget_move_targets_for_widgets(widgets)

        for widget in widgets:
            if widget.parent is not None:
                widget.parent.remove_child(widget)

        self.widget_tree.rebuild_tree()
        self._clear_selection(sync_tree=True, sync_preview=True)
        self._record_page_state_change(source="widget delete")
        message = f"Deleted {len(widgets)} widget(s)"
        if removed_targets:
            message += f"; {self._cleared_move_target_history_text(removed_targets)}"
        if locked_count:
            message += f"; skipped {self._locked_widget_summary(locked_count)}"
        self.statusBar().showMessage(message, 3000)
        return len(widgets), locked_count, removed_targets

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
        if self._apply_structure_result(move_into_container(self._structure_project_context(), widgets, target_choice.widget)):
            self._remember_move_target(target_choice.widget, target_choice.label)

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
        repeat_move_target_choice = self._remembered_move_target_choice(selected_widgets)
        self._move_into_last_target_action.setEnabled(repeat_move_target_choice is not None)
        has_recent_move_targets = bool(self._recent_move_target_labels())
        self._clear_move_target_history_action.setEnabled(has_recent_move_targets)
        self._lift_to_parent_action.setEnabled(structure_state.can_lift)
        self._move_up_action.setEnabled(structure_state.can_move_up)
        self._move_down_action.setEnabled(structure_state.can_move_down)
        self._move_top_action.setEnabled(structure_state.can_move_top)
        self._move_bottom_action.setEnabled(structure_state.can_move_bottom)
        for action, (base_text, reason_attr) in self._structure_action_hints.items():
            hint = self._structure_action_hint(base_text, action.isEnabled(), self._structure_action_reason(structure_state, reason_attr))
            action.setToolTip(hint)
            action.setStatusTip(hint)
        repeat_hint = self._structure_action_hint(
            self._move_into_last_target_hint(selected_widgets),
            repeat_move_target_choice is not None,
            self._move_into_last_target_reason(selected_widgets),
        )
        self._move_into_last_target_action.setToolTip(repeat_hint)
        self._move_into_last_target_action.setStatusTip(repeat_hint)
        clear_history_hint = self._structure_action_hint(
            self._clear_move_target_history_hint(),
            has_recent_move_targets,
            "no recent move targets are saved.",
        )
        self._clear_move_target_history_action.setToolTip(clear_history_hint)
        self._clear_move_target_history_action.setStatusTip(clear_history_hint)
        has_quick_move_history = repeat_move_target_choice is not None or has_recent_move_targets
        quick_menu_enabled = structure_state.can_move_into or has_quick_move_history
        quick_hint = self._structure_action_hint(
            self._quick_move_into_menu_hint(),
            quick_menu_enabled,
            self._structure_action_reason(structure_state, "move_into_reason"),
        )
        self._quick_move_into_menu.menuAction().setEnabled(quick_menu_enabled)
        self._quick_move_into_menu.menuAction().setToolTip(quick_hint)
        self._quick_move_into_menu.menuAction().setStatusTip(quick_hint)
        self._refresh_quick_move_into_menu()
        self._update_toolbar_action_metadata()
        self._update_arrange_menu_metadata()
        self._update_structure_menu_metadata()
        self._update_edit_menu_metadata()

    def _on_tree_selection_changed(self, widgets, primary):
        self._set_selection(widgets, primary=primary, sync_tree=False, sync_preview=True)

    def _on_preview_selection_changed(self, widgets, primary):
        self._set_selection(widgets, primary=primary, sync_tree=True, sync_preview=False)

    def _on_widget_selected(self, widget):
        """Widget selected from tree panel."""
        self._set_selection([widget] if widget is not None else [], primary=widget, sync_tree=False, sync_preview=True)

    def _on_preview_widget_selected(self, widget):
        """Widget selected from preview panel overlay."""
        self._set_selection([widget] if widget is not None else [], primary=widget, sync_tree=True, sync_preview=False)

    def _on_widget_moved(self, widget, new_x, new_y):
        """Widget dragged on preview overlay."""
        self._active_batch_source = "canvas move"
        if widget == self._selection_state.primary:
            self.property_panel.set_selection(self._selection_state.widgets, self._selection_state.primary)
        self._on_model_changed(source="canvas move")

    def _on_widget_resized(self, widget, new_width, new_height):
        """Widget resized on preview overlay."""
        self._active_batch_source = "canvas resize"
        if widget == self._selection_state.primary:
            self.property_panel.set_selection(self._selection_state.widgets, self._selection_state.primary)
        self._on_model_changed(source="canvas resize")

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

    def _record_page_state_change(self, update_preview=True, trigger_compile=True, source=""):
        """Record the current page snapshot and refresh dependent UI state."""
        if self._current_page and not self._undoing:
            xml = self._current_page.to_xml_string()
            stack = self._undo_manager.get_stack(self._current_page.name)
            stack.push(xml, label=source or "property edit")
        if update_preview:
            self._update_preview_overlay()
        self._sync_xml_to_editors()
        self._update_resource_usage_panel()
        if trigger_compile:
            self._trigger_compile()
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
            self._trigger_compile()
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
            stack = self._undo_manager.get_stack(self._current_page.name)
            stack.begin_batch()

    def _on_drag_finished(self):
        """Preview drag/resize ended 鈥?commit undo batch."""
        if self._current_page:
            xml = self._current_page.to_xml_string()
            stack = self._undo_manager.get_stack(self._current_page.name)
            stack.end_batch(xml, label=self._active_batch_source or "canvas drag")
            self._active_batch_source = ""
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
            self._trigger_compile()
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
        self._update_build_menu_metadata()

    def _trigger_compile(self):
        """Trigger a debounced compile."""
        if self._is_closing:
            return
        if not self.auto_compile:
            return
        if self.compiler is None:
            self._refresh_python_preview("SDK unavailable, compile preview disabled")
            return
        self._compile_timer.start()

    def _flush_pending_xml(self):
        """Flush any pending XML edits from the editor into the model."""
        if self.editor_tabs._parse_timer.isActive():
            self.editor_tabs._parse_timer.stop()
            self.editor_tabs._emit_xml_changed()

    def _do_compile_and_run(self):
        """Execute compile and run cycle (async, multi-file)."""
        if not self.project:
            return
        if self._is_closing:
            return
        if self.compiler is None or not self.compiler.can_build():
            reason = "SDK unavailable, compile preview disabled"
            if self.compiler is not None and self.compiler.get_build_error():
                reason = self.compiler.get_build_error()
            self._last_runtime_error_text = reason
            self._switch_to_python_preview(reason)
            self.statusBar().showMessage("Compile preview unavailable")
            self._update_workspace_chips()
            return
        if self._compile_worker is not None and self._compile_worker.isRunning():
            # Mark that we need to recompile after current one finishes
            self._pending_compile = True
            return
        # Wait for precompile to finish to avoid conflicts
        if self._precompile_worker is not None and self._precompile_worker.isRunning():
            self.statusBar().showMessage("Waiting for background compile...")
            self.debug_panel.log_info("Waiting for background compile to finish...")
            self._pending_compile = True
            return

        self._pending_compile = False

        # Always use the latest editor content
        self._flush_pending_xml()
        self._update_diagnostics_panel()
        if not self._ensure_codegen_preflight("Compile preview", show_dialog=False, switch_to_python_preview=True):
            return

        self.statusBar().showMessage("Compiling...")
        self.preview_panel.status_label.setText("Compiling...")

        self.debug_panel.log_action("Starting compile and run...")
        self.debug_panel.log_info(f"Generating code for {len(self.project.pages)} page(s)")

        # Generate resource config + resource C files if needed
        self._ensure_resources_generated()

        # Temporarily set startup_page to current page for preview
        original_startup = self.project.startup_page
        if self._current_page:
            self.project.startup_page = self._current_page.name

        files = generate_all_files(self.project)

        # Restore original startup_page
        self.project.startup_page = original_startup

        self.debug_panel.log_info(f"Generated {len(files)} file(s): {', '.join(files.keys())}")
        self.debug_panel.log_cmd(
            f"make -j main.exe APP={self.app_name} PORT=designer EGUI_APP_ROOT_PATH={self.compiler.app_root_arg} COMPILE_DEBUG= COMPILE_OPT_LEVEL=-O0"
        )

        generation = self._async_generation
        worker = self.compiler.compile_and_run_async(
            code=None,
            callback=lambda success, message, old_process: self._on_compile_finished(worker, generation, success, message, old_process),
            files_dict=files,
        )
        self._compile_worker = worker
        # Connect log signal for detailed timing info
        worker.log.connect(lambda message, msg_type: self._on_compile_log(worker, generation, message, msg_type))

    def _on_compile_log(self, worker, generation, message, msg_type):
        """Handle log messages from compile worker."""
        if self._is_closing or generation != self._async_generation or worker is not self._compile_worker:
            return
        self.debug_panel.log(message, msg_type)

    def _on_compile_finished(self, worker, generation, success, message, old_process):
        """Callback when background compilation completes."""
        del old_process
        self._cleanup_worker_ref(worker, "_compile_worker")
        if self._is_closing or generation != self._async_generation:
            return
        # Update debug panel with compile output
        self.debug_panel.log_compile_output(success, message)

        # Check if we need to recompile due to pending changes
        if self._pending_compile:
            self._pending_compile = False
            self._trigger_compile()

        if success:
            self._last_runtime_error_text = ""
            self.statusBar().showMessage(message)
            self.preview_panel.status_label.setText(f"OK - {message}")
            # Start headless frame rendering
            self.preview_panel.start_rendering(self.compiler)
            self.debug_panel.log_action("Headless preview started")
        else:
            self._last_runtime_error_text = (message.splitlines()[0] if message else "Compile failed")
            self.statusBar().showMessage("Compile FAILED - see Debug Output")
            if self.compiler is not None:
                self.compiler.stop_exe()
            self._switch_to_python_preview(message.splitlines()[0] if message else "Compile failed")
            # Show debug dock on compile failure
            self._show_bottom_panel("Debug Output")
        self._update_compile_availability()

    def _on_preview_runtime_failed(self, reason):
        if self._is_closing:
            return
        self._last_runtime_error_text = reason or "Headless preview stopped responding"
        if self.compiler is not None:
            self.compiler.stop_exe()
        self.debug_panel.log_error(reason or "Headless preview stopped responding")
        self._show_bottom_panel("Debug Output")
        self._switch_to_python_preview(reason or "Headless preview stopped responding")
        self._update_compile_availability()

    def _try_embed_exe(self):
        """Legacy - headless rendering replaces window embedding."""
        pass

    def _stop_exe(self):
        self._stop_background_timers()
        self.preview_panel.stop_rendering()
        self._last_runtime_error_text = ""
        if self.compiler is not None:
            self.compiler.stop_exe()
        self.preview_panel.status_label.setText("Preview stopped")
        self._update_compile_availability()

    def closeEvent(self, event):
        self._is_closing = True
        if self.project and self._undo_manager.is_any_dirty():
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "There are unsaved changes. Do you want to save before closing?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save
            )
            if reply == QMessageBox.Cancel:
                self._is_closing = False
                event.ignore()
                return
            elif reply == QMessageBox.Save:
                self._save_project()

        # Save config
        self._config.auto_compile = self.auto_compile
        self._config.overlay_mode = self.preview_panel._mode
        self._config.overlay_flipped = self.preview_panel._flipped
        self._save_window_state_to_config()
        self._save_diagnostics_view_state()
        if self._has_valid_sdk_root():
            self._config.sdk_root = self.project_root
            self._config.egui_root = self.project_root
        self._config.save()

        self._bump_async_generation()
        self._shutdown_async_activity(wait_ms=500)
        self.widget_tree.shutdown()
        if self.compiler is not None:
            self.compiler.cleanup()
            self.compiler = None
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








