"""Global configuration management for EmbeddedGUI Designer."""

from __future__ import annotations

import json
import os
import sys

from .workspace import infer_sdk_root_from_project_dir, is_valid_sdk_root, normalize_path, resolve_available_sdk_root


CONFIG_DIR_ENV_VAR = "EMBEDDEDGUI_DESIGNER_CONFIG_DIR"


def _default_user_config_dir():
    """Return the user-scoped config directory for the current platform."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    elif sys.platform == "darwin":
        base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME", os.path.join(os.path.expanduser("~"), ".config"))
    return os.path.join(base, "EmbeddedGUI-Designer")


def _get_legacy_config_dir():
    """Return the historical repo-local config directory."""
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return normalize_path(os.path.join(base, ".config"))


def _config_path_for_dir(config_dir):
    """Build the config.json path for a config directory."""
    return normalize_path(os.path.join(config_dir, "config.json"))


def _get_config_dir():
    """Get the primary configuration directory path."""
    override = normalize_path(os.environ.get(CONFIG_DIR_ENV_VAR, ""))
    if override:
        return override
    return normalize_path(_default_user_config_dir())


def _get_config_path():
    """Get the full path to the primary config file."""
    return _config_path_for_dir(_get_config_dir())


def _get_legacy_config_path():
    """Get the full path to the legacy repo-local config file."""
    return _config_path_for_dir(_get_legacy_config_dir())


def _get_load_config_paths():
    """Return config load candidates, preferring the new user-scoped path."""
    paths = []
    for path in (_get_config_path(), _get_legacy_config_path()):
        normalized = normalize_path(path)
        if normalized and normalized not in paths:
            paths.append(normalized)
    return paths


class DesignerConfig:
    """Manages global designer configuration."""

    _instance = None

    def __init__(self):
        self.sdk_root = ""
        self.egui_root = ""
        self.last_app = "HelloDesigner"
        self.last_project_path = ""
        self.recent_projects = []
        self.recent_apps = []
        self.theme = "dark"
        self.auto_compile = True
        self.overlay_mode = "horizontal"
        self.overlay_flipped = True
        self.preview_engine = "v1"
        self.show_grid = True
        self.grid_size = 8
        self.font_size_px = 0
        self.show_all_examples = False
        self.window_geometry = ""
        self.window_state = ""
        self.workspace_layout_version = 0
        self.workspace_left_panel = "project"
        self.workspace_state = {}
        self.widget_browser_recent = []
        self.widget_browser_favorites = []
        self.widget_browser_active_scenario = "all"
        self.widget_browser_active_tags = []
        self.widget_browser_sort_mode = "relevance"
        self.widget_browser_complexity_filter = "all"
        self.workspace_status_panel_state = {}
        self.sdk_setup_prompted = False
        self.release_history_view = {}
        self.repo_health_view = {}
        self.diagnostics_view = {}

    @property
    def egui_root(self):
        """Legacy alias for ``sdk_root``."""
        return self.sdk_root

    @egui_root.setter
    def egui_root(self, value):
        self.sdk_root = normalize_path(value)

    @classmethod
    def instance(cls):
        """Get the singleton config instance."""
        if cls._instance is None:
            cls._instance = cls()
            cls._instance.load()
        return cls._instance

    def _normalize_recent_projects(self, recent_projects, recent_apps, fallback_sdk_root):
        normalized = []

        for item in recent_projects or []:
            if not isinstance(item, dict):
                continue
            project_path = normalize_path(item.get("project_path", ""))
            sdk_root = normalize_path(item.get("sdk_root", item.get("egui_root", "")))
            display_name = item.get("display_name", "")
            if not project_path:
                continue
            if not display_name:
                display_name = os.path.splitext(os.path.basename(project_path))[0]
            normalized.append(
                {
                    "project_path": project_path,
                    "sdk_root": sdk_root,
                    "display_name": display_name,
                }
            )

        for app_name, egui_root in recent_apps or []:
            sdk_root = normalize_path(egui_root or fallback_sdk_root)
            if not sdk_root or not app_name:
                continue
            project_path = normalize_path(os.path.join(sdk_root, "example", app_name, f"{app_name}.egui"))
            normalized.append(
                {
                    "project_path": project_path,
                    "sdk_root": sdk_root,
                    "display_name": app_name,
                }
            )

        deduped = []
        seen = set()
        for item in normalized:
            key = item["project_path"]
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped[:10]

    def _legacy_recent_apps_from_projects(self):
        result = []
        for item in self.recent_projects[:10]:
            app_name = item.get("display_name") or os.path.splitext(os.path.basename(item.get("project_path", "")))[0]
            sdk_root = item.get("sdk_root", "")
            if app_name and sdk_root:
                result.append((app_name, sdk_root))
        return result

    def _default_cached_sdk_root(self):
        return normalize_path(os.path.join(_get_config_dir(), "sdk", "EmbeddedGUI"))

    def _legacy_cached_sdk_root(self):
        return normalize_path(os.path.join(_get_legacy_config_dir(), "sdk", "EmbeddedGUI"))

    def _resolve_sdk_root(self, sdk_root=""):
        candidates = []
        for candidate in (sdk_root, self.sdk_root, self.egui_root):
            normalized = normalize_path(candidate)
            if normalized and normalized not in candidates:
                candidates.append(normalized)

        for candidate in candidates:
            if is_valid_sdk_root(candidate):
                return candidate
            inferred = infer_sdk_root_from_project_dir(candidate)
            if inferred:
                return inferred

        primary_cached = self._default_cached_sdk_root()
        if is_valid_sdk_root(primary_cached):
            return primary_cached

        legacy_cached = self._legacy_cached_sdk_root()
        if is_valid_sdk_root(legacy_cached):
            return legacy_cached

        return resolve_available_sdk_root(*candidates, cached_sdk_root=primary_cached)

    def load(self):
        """Load configuration from file."""
        config_path = ""
        for candidate in _get_load_config_paths():
            if os.path.isfile(candidate):
                config_path = candidate
                break
        if not config_path:
            return

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.sdk_root = normalize_path(data.get("sdk_root", data.get("egui_root", "")))
            self.egui_root = self.sdk_root
            self.last_app = data.get("last_app", "HelloDesigner")
            self.last_project_path = normalize_path(data.get("last_project_path", ""))
            self.recent_projects = self._normalize_recent_projects(
                data.get("recent_projects", []),
                data.get("recent_apps", []),
                self.sdk_root,
            )
            self.recent_apps = self._legacy_recent_apps_from_projects()
            self.theme = data.get("theme", "dark")
            self.auto_compile = data.get("auto_compile", True)
            self.overlay_mode = data.get("overlay_mode", "horizontal")
            self.overlay_flipped = data.get("overlay_flipped", True)
            self.preview_engine = str(data.get("preview_engine", "v1") or "v1")
            self.show_grid = data.get("show_grid", True)
            self.grid_size = int(data.get("grid_size", 8))
            self.font_size_px = data.get("font_size_px", 0)
            self.show_all_examples = data.get("show_all_examples", False)
            self.window_geometry = data.get("window_geometry", "")
            self.window_state = data.get("window_state", "")
            self.workspace_layout_version = int(data.get("workspace_layout_version", 0) or 0)
            workspace_left_panel = str(data.get("workspace_left_panel", "project") or "project")
            if workspace_left_panel == "components":
                workspace_left_panel = "widgets"
            self.workspace_left_panel = workspace_left_panel
            workspace_state = data.get("workspace_state", {})
            self.workspace_state = workspace_state if isinstance(workspace_state, dict) else {}
            recent = data.get("widget_browser_recent", [])
            favorites = data.get("widget_browser_favorites", [])
            self.widget_browser_recent = [str(item).strip() for item in recent if str(item).strip()][:24]
            self.widget_browser_favorites = [str(item).strip() for item in favorites if str(item).strip()][:64]
            active_scenario = str(data.get("widget_browser_active_scenario", "all") or "all").strip().lower()
            self.widget_browser_active_scenario = active_scenario or "all"
            active_tags = data.get("widget_browser_active_tags", [])
            self.widget_browser_active_tags = [str(item).strip() for item in active_tags if str(item).strip()][:24]
            sort_mode = str(data.get("widget_browser_sort_mode", "relevance") or "relevance").strip().lower()
            self.widget_browser_sort_mode = sort_mode if sort_mode in {"relevance", "name", "complexity"} else "relevance"
            complexity_filter = str(data.get("widget_browser_complexity_filter", "all") or "all").strip().lower()
            self.widget_browser_complexity_filter = (
                complexity_filter if complexity_filter in {"all", "basic", "intermediate", "advanced"} else "all"
            )
            status_state = data.get("workspace_status_panel_state", {})
            self.workspace_status_panel_state = status_state if isinstance(status_state, dict) else {}
            self.sdk_setup_prompted = data.get("sdk_setup_prompted", False)
            self.release_history_view = data.get("release_history_view", {}) if isinstance(data.get("release_history_view", {}), dict) else {}
            self.repo_health_view = data.get("repo_health_view", {}) if isinstance(data.get("repo_health_view", {}), dict) else {}
            self.diagnostics_view = data.get("diagnostics_view", {}) if isinstance(data.get("diagnostics_view", {}), dict) else {}
        except Exception as e:
            print(f"Warning: Failed to load config: {e}")

    def save(self):
        """Save configuration to file."""
        config_dir = _get_config_dir()
        config_path = _get_config_path()

        try:
            os.makedirs(config_dir, exist_ok=True)
            data = {
                "sdk_root": self.sdk_root,
                "egui_root": self.sdk_root,
                "last_app": self.last_app,
                "last_project_path": self.last_project_path,
                "recent_projects": self.recent_projects,
                "recent_apps": self._legacy_recent_apps_from_projects(),
                "theme": self.theme,
                "auto_compile": self.auto_compile,
                "overlay_mode": self.overlay_mode,
                "overlay_flipped": self.overlay_flipped,
                "preview_engine": self.preview_engine,
                "show_grid": self.show_grid,
                "grid_size": self.grid_size,
                "font_size_px": self.font_size_px,
                "show_all_examples": self.show_all_examples,
                "window_geometry": self.window_geometry,
                "window_state": self.window_state,
                "workspace_layout_version": self.workspace_layout_version,
                "workspace_left_panel": self.workspace_left_panel,
                "workspace_state": self.workspace_state,
                "widget_browser_recent": self.widget_browser_recent,
                "widget_browser_favorites": self.widget_browser_favorites,
                "widget_browser_active_scenario": self.widget_browser_active_scenario,
                "widget_browser_active_tags": self.widget_browser_active_tags,
                "widget_browser_sort_mode": self.widget_browser_sort_mode,
                "widget_browser_complexity_filter": self.widget_browser_complexity_filter,
                "workspace_status_panel_state": self.workspace_status_panel_state,
                "sdk_setup_prompted": self.sdk_setup_prompted,
                "release_history_view": self.release_history_view,
                "repo_health_view": self.repo_health_view,
                "diagnostics_view": self.diagnostics_view,
            }
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Warning: Failed to save config: {e}")

    def add_recent_project(self, project_path, sdk_root="", display_name=""):
        """Add a project to the MRU list."""
        project_path = normalize_path(project_path)
        sdk_root = normalize_path(sdk_root)
        if not project_path:
            return
        if not display_name:
            display_name = os.path.splitext(os.path.basename(project_path))[0]

        self.recent_projects = [item for item in self.recent_projects if item.get("project_path") != project_path]
        self.recent_projects.insert(
            0,
            {
                "project_path": project_path,
                "sdk_root": sdk_root,
                "display_name": display_name,
            },
        )
        self.recent_projects = self.recent_projects[:10]
        self.recent_apps = self._legacy_recent_apps_from_projects()
        self.save()

    def remove_recent_project(self, project_path):
        """Remove a project from the MRU list."""
        project_path = normalize_path(project_path)
        if not project_path:
            return False

        original_len = len(self.recent_projects)
        self.recent_projects = [item for item in self.recent_projects if item.get("project_path") != project_path]
        removed = len(self.recent_projects) != original_len
        if removed:
            if self.last_project_path == project_path:
                self.last_project_path = ""
            self.recent_apps = self._legacy_recent_apps_from_projects()
            self.save()
        return removed

    def add_recent_app(self, app_name, egui_root):
        """Legacy MRU helper kept for compatibility."""
        if not app_name:
            return
        sdk_root = normalize_path(egui_root)
        project_path = ""
        if sdk_root:
            project_path = os.path.join(sdk_root, "example", app_name, f"{app_name}.egui")
        self.add_recent_project(project_path, sdk_root, app_name)

    def record_widget_browser_recent(self, widget_type):
        """Add a widget type to the browser MRU list."""
        widget_type = str(widget_type or "").strip()
        if not widget_type:
            return
        self.widget_browser_recent = [item for item in self.widget_browser_recent if item != widget_type]
        self.widget_browser_recent.insert(0, widget_type)
        self.widget_browser_recent = self.widget_browser_recent[:24]
        self.save()

    def toggle_widget_browser_favorite(self, widget_type):
        """Toggle a widget type in the browser favorites list."""
        widget_type = str(widget_type or "").strip()
        if not widget_type:
            return False
        favorites = [item for item in self.widget_browser_favorites if item]
        if widget_type in favorites:
            favorites = [item for item in favorites if item != widget_type]
            enabled = False
        else:
            favorites.insert(0, widget_type)
            enabled = True
        self.widget_browser_favorites = favorites[:64]
        self.save()
        return enabled

    def set_widget_browser_filters(self, scenario=None, tags=None):
        """Persist widget browser scenario and active tag filters."""
        if scenario is not None:
            normalized = str(scenario or "all").strip().lower()
            self.widget_browser_active_scenario = normalized or "all"
        if tags is not None:
            unique_tags = []
            seen = set()
            for item in tags:
                text = str(item or "").strip()
                key = text.lower()
                if not text or key in seen:
                    continue
                seen.add(key)
                unique_tags.append(text)
            self.widget_browser_active_tags = unique_tags[:24]
        self.save()

    def set_widget_browser_organizers(self, sort_mode=None, complexity=None):
        """Persist widget browser sort mode and complexity filter."""
        if sort_mode is not None:
            normalized_sort = str(sort_mode or "relevance").strip().lower()
            self.widget_browser_sort_mode = (
                normalized_sort if normalized_sort in {"relevance", "name", "complexity"} else "relevance"
            )
        if complexity is not None:
            normalized_complexity = str(complexity or "all").strip().lower()
            self.widget_browser_complexity_filter = (
                normalized_complexity if normalized_complexity in {"all", "basic", "intermediate", "advanced"} else "all"
            )
        self.save()

    def get_app_dir(self, app_name=None, sdk_root=None):
        """Get the default SDK example directory for an app."""
        app_name = app_name or self.last_app
        sdk_root = self._resolve_sdk_root(sdk_root)
        if not sdk_root or not app_name:
            return ""
        return os.path.join(sdk_root, "example", app_name)

    def get_project_path(self, app_name=None, sdk_root=None):
        """Get the default SDK example project path for an app."""
        app_dir = self.get_app_dir(app_name, sdk_root)
        if not app_dir:
            return ""
        app_name = app_name or self.last_app
        return os.path.join(app_dir, f"{app_name}.egui")

    def list_available_app_entries(self, sdk_root=None, include_legacy=False):
        """List all available app entries in the SDK ``example/`` directory."""
        sdk_root = self._resolve_sdk_root(sdk_root)
        if not sdk_root:
            return []

        example_dir = os.path.join(sdk_root, "example")
        if not os.path.isdir(example_dir):
            return []

        entries = []
        for name in os.listdir(example_dir):
            app_path = os.path.join(example_dir, name)
            if not os.path.isdir(app_path):
                continue
            if not os.path.isfile(os.path.join(app_path, "build.mk")):
                continue

            project_path = os.path.join(app_path, f"{name}.egui")
            has_project = os.path.isfile(project_path)
            if not has_project and not include_legacy:
                continue

            entries.append(
                {
                    "app_name": name,
                    "app_dir": app_path,
                    "project_path": project_path if has_project else "",
                    "has_project": has_project,
                    "is_legacy": not has_project,
                }
            )
        return sorted(entries, key=lambda item: item["app_name"].lower())

    def list_available_apps(self, sdk_root=None, include_legacy=False):
        """Return app names for SDK examples."""
        entries = self.list_available_app_entries(sdk_root=sdk_root, include_legacy=include_legacy)
        return [entry["app_name"] for entry in entries]


def get_config():
    """Get the global config instance."""
    return DesignerConfig.instance()
