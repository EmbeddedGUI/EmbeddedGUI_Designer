"""Centralized widget type registry for EmbeddedGUI Designer.

Provides a single source of truth for widget type descriptors, replacing
scattered hardcoded lists across widget_tree.py, code_generator.py, and
property_panel.py.

Built-in widgets are loaded from ``ui_designer/custom_widgets/*.py`` on first
access. App-local custom widgets are discovered from ``egui_view_*.h`` headers
under the current app directory and registered at runtime.
"""

import os
import importlib.util
import logging

logger = logging.getLogger(__name__)

_APP_LOCAL_WIDGET_PLUGIN_DIRNAME = "custom_widgets"


_CATEGORY_ORDER = (
    "Basics",
    "Layout",
    "Input",
    "Navigation",
    "Display & Data",
    "Media",
    "Decoration",
    "Custom",
)

_SCENARIO_ORDER = (
    "Layout & Containers",
    "Input & Forms",
    "Navigation & Flow",
    "Data & Visualization",
    "Feedback & Status",
    "Media & Content",
    "Decoration",
)


_BROWSER_METADATA = {
    "button": {"category": "Basics", "keywords": ["tap", "action", "cta"], "icon_key": "button", "preview_kind": "widget", "browse_priority": 10},
    "label": {"category": "Basics", "keywords": ["text", "caption", "title"], "icon_key": "text", "preview_kind": "widget", "browse_priority": 10},
    "image": {"category": "Basics", "keywords": ["photo", "asset", "bitmap"], "icon_key": "image", "preview_kind": "widget", "browse_priority": 20},
    "card": {"category": "Basics", "keywords": ["container", "surface"], "icon_key": "card", "preview_kind": "widget", "browse_priority": 20},
    "divider": {"category": "Basics", "keywords": ["line", "separator"], "icon_key": "divider", "preview_kind": "widget", "browse_priority": 40},
    "line": {"category": "Basics", "keywords": ["stroke", "separator"], "icon_key": "divider", "preview_kind": "widget", "browse_priority": 50},
    "textblock": {"category": "Basics", "keywords": ["rich text", "paragraph"], "icon_key": "text", "preview_kind": "widget", "browse_priority": 30},
    "group": {"category": "Layout", "keywords": ["container", "nest"], "icon_key": "layout", "preview_kind": "layout", "browse_priority": 10},
    "linearlayout": {"category": "Layout", "keywords": ["stack", "column", "row"], "icon_key": "layout", "preview_kind": "layout", "browse_priority": 20},
    "gridlayout": {"category": "Layout", "keywords": ["grid", "matrix"], "icon_key": "grid", "preview_kind": "layout", "browse_priority": 30},
    "scroll": {"category": "Layout", "keywords": ["scroll", "viewport"], "icon_key": "layout", "preview_kind": "layout", "browse_priority": 40},
    "list": {"category": "Layout", "keywords": ["list", "repeater"], "icon_key": "list", "preview_kind": "layout", "browse_priority": 50},
    "table": {"category": "Display & Data", "keywords": ["table", "data", "rows"], "icon_key": "table", "preview_kind": "chart", "browse_priority": 40},
    "textinput": {"category": "Input", "keywords": ["text", "field", "entry"], "icon_key": "input", "preview_kind": "input", "browse_priority": 10},
    "combobox": {"category": "Input", "keywords": ["select", "dropdown"], "icon_key": "input", "preview_kind": "input", "browse_priority": 20},
    "checkbox": {"category": "Input", "keywords": ["boolean", "check"], "icon_key": "toggle", "preview_kind": "input", "browse_priority": 30},
    "radio_button": {"category": "Input", "keywords": ["choice", "single"], "icon_key": "toggle", "preview_kind": "input", "browse_priority": 40},
    "slider": {"category": "Input", "keywords": ["range", "scrub"], "icon_key": "input", "preview_kind": "input", "browse_priority": 50},
    "switch": {"category": "Input", "keywords": ["toggle", "on off"], "icon_key": "toggle", "preview_kind": "input", "browse_priority": 60},
    "number_picker": {"category": "Input", "keywords": ["numeric", "spinner"], "icon_key": "input", "preview_kind": "input", "browse_priority": 70},
    "roller": {"category": "Input", "keywords": ["wheel", "picker"], "icon_key": "input", "preview_kind": "input", "browse_priority": 80},
    "stepper": {"category": "Input", "keywords": ["steps", "wizard"], "icon_key": "input", "preview_kind": "input", "browse_priority": 90},
    "segmented_control": {"category": "Navigation", "keywords": ["segment", "switch"], "icon_key": "navigation", "preview_kind": "navigation", "browse_priority": 10},
    "tab_bar": {"category": "Navigation", "keywords": ["tabs", "tab"], "icon_key": "navigation", "preview_kind": "navigation", "browse_priority": 20},
    "menu": {"category": "Navigation", "keywords": ["menu", "options"], "icon_key": "navigation", "preview_kind": "navigation", "browse_priority": 30},
    "page_indicator": {"category": "Navigation", "keywords": ["pager", "dots"], "icon_key": "navigation", "preview_kind": "navigation", "browse_priority": 40},
    "viewpage": {"category": "Navigation", "keywords": ["page", "screen"], "icon_key": "page", "preview_kind": "navigation", "browse_priority": 50},
    "viewpage_cache": {"category": "Navigation", "keywords": ["page", "cache"], "icon_key": "page", "preview_kind": "navigation", "browse_priority": 60},
    "chart": {"category": "Display & Data", "keywords": ["trend", "graph"], "icon_key": "chart", "preview_kind": "chart", "browse_priority": 10},
    "chart_bar": {"category": "Display & Data", "keywords": ["bars", "data"], "icon_key": "chart", "preview_kind": "chart", "browse_priority": 20},
    "chart_line": {"category": "Display & Data", "keywords": ["line", "trend"], "icon_key": "chart", "preview_kind": "chart", "browse_priority": 30},
    "chart_pie": {"category": "Display & Data", "keywords": ["pie", "ratio"], "icon_key": "chart", "preview_kind": "chart", "browse_priority": 40},
    "chart_scatter": {"category": "Display & Data", "keywords": ["points", "scatter"], "icon_key": "chart", "preview_kind": "chart", "browse_priority": 50},
    "gauge": {"category": "Display & Data", "keywords": ["meter", "dial"], "icon_key": "chart", "preview_kind": "chart", "browse_priority": 60},
    "progress_bar": {"category": "Display & Data", "keywords": ["loading", "progress"], "icon_key": "progress", "preview_kind": "widget", "browse_priority": 70},
    "spinner": {"category": "Display & Data", "keywords": ["busy", "loading"], "icon_key": "progress", "preview_kind": "widget", "browse_priority": 80},
    "activity_ring": {"category": "Display & Data", "keywords": ["ring", "activity"], "icon_key": "progress", "preview_kind": "widget", "browse_priority": 90},
    "animated_image": {"category": "Media", "keywords": ["animation", "gif"], "icon_key": "image", "preview_kind": "media", "browse_priority": 20},
    "mp4": {"category": "Media", "keywords": ["video", "movie"], "icon_key": "media", "preview_kind": "media", "browse_priority": 10},
    "analog_clock": {"category": "Decoration", "keywords": ["clock", "time"], "icon_key": "time", "preview_kind": "widget", "browse_priority": 20},
    "digital_clock": {"category": "Decoration", "keywords": ["clock", "time"], "icon_key": "time", "preview_kind": "widget", "browse_priority": 30},
    "notification_badge": {"category": "Decoration", "keywords": ["badge", "status"], "icon_key": "status", "preview_kind": "widget", "browse_priority": 40},
    "led": {"category": "Decoration", "keywords": ["status", "indicator"], "icon_key": "status", "preview_kind": "widget", "browse_priority": 50},
}


def _dedupe_strings(values):
    seen = set()
    result = []
    for value in values or []:
        text = str(value or "").strip()
        key = text.lower()
        if not text or key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def _infer_category(type_name, descriptor):
    type_name = str(type_name or "").strip().lower()
    if descriptor.get("is_container"):
        return "Layout"
    if any(token in type_name for token in ("chart", "gauge", "progress", "scale", "meter")):
        return "Display & Data"
    if any(token in type_name for token in ("tab", "menu", "page", "nav", "breadcrumb", "indicator")):
        return "Navigation"
    if any(token in type_name for token in ("input", "checkbox", "radio", "switch", "slider", "picker", "stepper", "combo", "keyboard", "lock")):
        return "Input"
    if any(token in type_name for token in ("video", "mp4", "media", "audio", "wave")):
        return "Media"
    if any(token in type_name for token in ("image", "clock", "badge", "led", "decor", "avatar")):
        return "Decoration"
    return "Basics"


def _infer_scenario(type_name, descriptor, category):
    category = str(category or "")
    if descriptor.get("is_container") or category == "Layout":
        return "Layout & Containers"
    if category == "Input":
        return "Input & Forms"
    if category == "Navigation":
        return "Navigation & Flow"
    if category == "Display & Data":
        if any(token in str(type_name or "") for token in ("progress", "spinner", "ring", "badge", "led", "stopwatch", "clock")):
            return "Feedback & Status"
        return "Data & Visualization"
    if category == "Media":
        return "Media & Content"
    if category == "Decoration":
        return "Decoration"
    return "Feedback & Status"


def _infer_tags(type_name, descriptor, browser):
    type_name = str(type_name or "").strip().lower()
    category = str(browser.get("category", ""))
    scenario = str(browser.get("scenario", ""))
    tags = [category, scenario]
    if descriptor.get("is_container"):
        tags.extend(["container", "layout"])
    if any(token in type_name for token in ("button", "menu", "tab", "segmented", "navigation")):
        tags.append("interaction")
    if any(token in type_name for token in ("text", "label", "input", "keyboard", "combo", "picker")):
        tags.append("text")
    if any(token in type_name for token in ("chart", "gauge", "table", "progress", "spinner", "ring", "scale")):
        tags.append("data")
    if any(token in type_name for token in ("image", "mp4", "media")):
        tags.append("media")
    if any(token in type_name for token in ("clock", "badge", "led", "notification", "status")):
        tags.append("status")
    return _dedupe_strings(tags)


def _infer_complexity(type_name, descriptor):
    type_name = str(type_name or "").strip().lower()
    if descriptor.get("is_container"):
        return "advanced"
    if any(token in type_name for token in ("chart", "table", "mp4", "keyboard", "viewpage", "grid", "gauge", "calendar")):
        return "intermediate"
    return "basic"


class WidgetRegistry:
    """Central registry for widget type descriptors.

    Usage::

        reg = WidgetRegistry.instance()
        reg.get("label")           # -> descriptor dict
        reg.addable_types()        # -> [("Label", "label"), ...]
        reg.container_types()      # -> {"group", "linearlayout", ...}
        reg.tag_to_type("Label")   # -> "label"
        reg.type_to_tag("label")   # -> "Label"
    """

    _instance = None

    def __init__(self):
        self._types = {}        # type_name -> descriptor dict
        self._tag_map = {}      # XML tag -> type_name
        self._rev_tag_map = {}  # type_name -> XML tag
        self._addable = []      # [(display_name, type_name), ...]
        self._display_names = {}  # type_name -> display name
        self._origins = {}      # type_name -> origin
        self._active_origin = None
        self._app_local_issues = []
        self._app_local_project_dir = ""

    @classmethod
    def instance(cls):
        """Return the singleton registry, creating it on first call."""
        if cls._instance is None:
            cls._instance = cls()
            cls._instance._load_builtins()
        return cls._instance

    @classmethod
    def reset(cls):
        """Reset the singleton (for testing)."""
        cls._instance = None

    def _load_builtins(self):
        """Load all widget types from the custom_widgets/ plugin directory."""
        # custom_widgets/ is a sibling package of model/
        pkg_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        widgets_dir = os.path.join(pkg_dir, "custom_widgets")
        self.load_custom_widgets(widgets_dir, origin="builtin")

    def register(self, type_name, descriptor, xml_tag=None, display_name=None, origin=None):
        """Register a widget type.

        Args:
            type_name:    Internal type key (e.g., "label", "my_gauge").
            descriptor:   Dict with c_type, init_func, properties, etc.
            xml_tag:      XML tag for serialization (default: TitleCase of type_name).
            display_name: Human-readable name for UI menus (default: same as xml_tag).
        """
        type_name = str(type_name or "").strip()
        if not type_name:
            raise ValueError("type_name is required")

        origin = str(origin or self._active_origin or "runtime")

        existing_tag = self._rev_tag_map.get(type_name)
        if existing_tag and self._tag_map.get(existing_tag) == type_name:
            del self._tag_map[existing_tag]

        descriptor = dict(descriptor or {})
        descriptor.setdefault("origin", origin)
        self._types[type_name] = descriptor
        self._origins[type_name] = origin

        # Derive XML tag if not provided
        if xml_tag is None:
            xml_tag = type_name.replace("_", " ").title().replace(" ", "")
        self._tag_map[xml_tag] = type_name
        self._rev_tag_map[type_name] = xml_tag

        # Display name for menus
        if display_name is None:
            display_name = xml_tag
        self._display_names[type_name] = display_name

        # Add to addable list (avoid duplicates on re-register)
        addable = descriptor.get("addable", True)
        # Remove existing entry if re-registering
        self._addable = [(dn, tn) for dn, tn in self._addable if tn != type_name]
        if addable:
            self._addable.append((display_name, type_name))

    def origin(self, type_name):
        """Return the registration origin for a widget type."""
        return self._origins.get(type_name, "")

    def _remove_type(self, type_name):
        xml_tag = self._rev_tag_map.pop(type_name, "")
        if xml_tag and self._tag_map.get(xml_tag) == type_name:
            del self._tag_map[xml_tag]
        self._types.pop(type_name, None)
        self._display_names.pop(type_name, None)
        self._origins.pop(type_name, None)
        self._addable = [(dn, tn) for dn, tn in self._addable if tn != type_name]

    def clear_origin(self, origin):
        """Remove all widget types registered from the given origin."""
        origin = str(origin or "").strip()
        if not origin:
            return
        for type_name in [tn for tn, current_origin in self._origins.items() if current_origin == origin]:
            self._remove_type(type_name)

    def clear_app_local_widgets(self):
        """Remove all app-local widget registrations and scan issues."""
        self.clear_origin("app_local")
        self._app_local_issues = []
        self._app_local_project_dir = ""

    def app_local_issues(self):
        """Return diagnostics captured during the last app-local widget scan."""
        return list(self._app_local_issues)

    def app_local_project_dir(self):
        """Return the project directory used for the last app-local widget scan."""
        return self._app_local_project_dir

    def app_local_plugin_dir(self, project_dir=None):
        """Return the app-local Python widget descriptor directory."""
        base_dir = project_dir or self._app_local_project_dir
        if not base_dir:
            return ""
        return os.path.join(base_dir, _APP_LOCAL_WIDGET_PLUGIN_DIRNAME)

    def load_app_local_widgets(self, project_dir):
        """Scan the app directory for ``egui_view_*.h`` and register them."""
        from ..utils.header_parser import (
            build_runtime_widget_registration,
            discover_widget_headers,
            parse_header,
        )

        self.clear_origin("app_local")
        self._app_local_issues = []
        self._app_local_project_dir = os.path.normpath(os.path.abspath(project_dir)) if project_dir else ""

        if not self._app_local_project_dir or not os.path.isdir(self._app_local_project_dir):
            return []

        plugin_dir = self.app_local_plugin_dir(self._app_local_project_dir)

        for header_path in discover_widget_headers(self._app_local_project_dir):
            try:
                info = parse_header(header_path)
            except Exception as exc:
                self._app_local_issues.append(
                    {
                        "severity": "warning",
                        "code": "app_local_widget_parse_failed",
                        "message": (
                            f"Failed to parse app-local widget header '{os.path.basename(header_path)}': {exc}. "
                            f"You can add a manual widget descriptor under '{plugin_dir}'."
                        ),
                        "widget_name": os.path.basename(header_path),
                    }
                )
                continue

            if info is None:
                self._app_local_issues.append(
                    {
                        "severity": "warning",
                        "code": "app_local_widget_unrecognized",
                        "message": (
                            f"Skipped '{os.path.basename(header_path)}' because it does not expose a recognized EmbeddedGUI widget API. "
                            f"You can add a manual widget descriptor under '{plugin_dir}'."
                        ),
                        "widget_name": os.path.basename(header_path),
                    }
                )
                continue

            try:
                registration = build_runtime_widget_registration(info, self._app_local_project_dir)
            except ValueError as exc:
                self._app_local_issues.append(
                    {
                        "severity": "warning",
                        "code": "app_local_widget_invalid",
                        "message": f"{exc}. You can add a manual widget descriptor under '{plugin_dir}'.",
                        "widget_name": info.widget_name or os.path.basename(header_path),
                    }
                )
                continue

            type_name = registration["type_name"]
            xml_tag = registration["xml_tag"]
            display_name = registration["display_name"]
            descriptor = registration["descriptor"]

            existing_type_origin = self.origin(type_name)
            if self.has(type_name) and existing_type_origin == "app_local":
                self._app_local_issues.append(
                    {
                        "severity": "warning",
                        "code": "app_local_widget_duplicate_type",
                        "message": f"Skipped duplicate app-local widget '{type_name}' because another header in this project already registered that type.",
                        "widget_name": type_name,
                    }
                )
                continue
            if self.has(type_name) and existing_type_origin != "app_local":
                self._app_local_issues.append(
                    {
                        "severity": "warning",
                        "code": "app_local_widget_type_conflict",
                        "message": f"Skipped app-local widget '{type_name}' because that type name is already registered by {existing_type_origin or 'another source'}.",
                        "widget_name": type_name,
                    }
                )
                continue

            existing_tag_type = self._tag_map.get(xml_tag)
            if existing_tag_type and existing_tag_type != type_name:
                self._app_local_issues.append(
                    {
                        "severity": "warning",
                        "code": "app_local_widget_tag_conflict",
                        "message": f"Skipped app-local widget '{type_name}' because XML tag '{xml_tag}' is already used by '{existing_tag_type}'.",
                        "widget_name": type_name,
                    }
                )
                continue

            self.register(
                type_name,
                descriptor,
                xml_tag=xml_tag,
                display_name=display_name,
                origin="app_local",
            )

        self.load_custom_widgets(plugin_dir, origin="app_local")
        return self.app_local_issues()

    def get(self, type_name):
        """Get descriptor for a widget type. Returns empty dict if unknown."""
        return self._types.get(type_name, {})

    def has(self, type_name):
        """Check if a widget type is registered."""
        return type_name in self._types

    def tag_to_type(self, tag):
        """Convert XML tag to internal type name."""
        return self._tag_map.get(tag, tag.lower())

    def type_to_tag(self, type_name):
        """Convert internal type name to XML tag."""
        return self._rev_tag_map.get(type_name, type_name)

    def addable_types(self):
        """Return list of (display_name, type_name) for the Add Widget menu."""
        return list(self._addable)

    def display_name(self, type_name):
        """Return the preferred UI display name for a widget type."""
        if type_name in self._display_names:
            return self._display_names[type_name]
        return str(type_name or "").replace("_", " ").title()

    def container_types(self):
        """Return set of type names that are containers."""
        return {tn for tn, desc in self._types.items() if desc.get("is_container")}

    def all_types(self):
        """Return dict of all registered type descriptors."""
        return dict(self._types)

    def browser_item(self, type_name):
        """Return normalized browser metadata for a widget type."""
        descriptor = self.get(type_name)
        if not descriptor:
            return {}

        browser = dict(_BROWSER_METADATA.get(type_name, {}))
        browser.update(descriptor.get("browser", {}))
        browser.setdefault("category", _infer_category(type_name, descriptor))
        browser.setdefault("scenario", _infer_scenario(type_name, descriptor, browser.get("category", "")))
        browser.setdefault("icon_key", browser.get("icon_key") or type_name)
        browser.setdefault("preview_kind", browser.get("preview_kind") or ("layout" if descriptor.get("is_container") else "widget"))
        browser.setdefault("browse_priority", int(browser.get("browse_priority", 999) or 999))
        browser.setdefault("complexity", _infer_complexity(type_name, descriptor))
        browser["keywords"] = _dedupe_strings(
            list(browser.get("keywords", []))
            + [self.display_name(type_name), type_name.replace("_", " "), browser["category"], browser["scenario"]]
        )
        browser["tags"] = _dedupe_strings(list(browser.get("tags", [])) + _infer_tags(type_name, descriptor, browser))
        browser["type_name"] = type_name
        browser["display_name"] = self.display_name(type_name)
        browser["is_container"] = bool(descriptor.get("is_container"))
        browser["addable"] = bool(descriptor.get("addable", True))
        return browser

    def browser_items(self, addable_only=True):
        """Return sorted widget browser items."""
        items = []
        for type_name, descriptor in self._types.items():
            if addable_only and not descriptor.get("addable", True):
                continue
            items.append(self.browser_item(type_name))
        return sorted(
            items,
            key=lambda item: (
                _SCENARIO_ORDER.index(item.get("scenario", "")) if item.get("scenario", "") in _SCENARIO_ORDER else len(_SCENARIO_ORDER),
                _CATEGORY_ORDER.index(item.get("category", "Custom")) if item.get("category", "Custom") in _CATEGORY_ORDER else len(_CATEGORY_ORDER),
                int(item.get("browse_priority", 999)),
                item.get("display_name", "").lower(),
            ),
        )

    def browser_categories(self):
        """Return the fixed widget browser categories."""
        return list(_CATEGORY_ORDER)

    def browser_scenarios(self):
        """Return scenarios used for task-oriented widget browsing."""
        scenarios = []
        seen = set()
        for item in self.browser_items(addable_only=True):
            scenario = str(item.get("scenario", "")).strip()
            if not scenario:
                continue
            key = scenario.lower()
            if key in seen:
                continue
            seen.add(key)
            scenarios.append(scenario)

        ordered = [scenario for scenario in _SCENARIO_ORDER if scenario.lower() in seen]
        extras = [scenario for scenario in scenarios if scenario not in ordered]
        return ordered + extras

    def load_custom_widgets(self, *dirs, origin=None):
        """Scan directories for custom widget .py plugin files and execute them.

        Each .py file is expected to call ``WidgetRegistry.instance().register(...)``
        to register one or more custom widget types.

        Files starting with ``_`` are skipped.

        Args:
            *dirs: Directory paths to scan for .py files.
        """
        previous_origin = self._active_origin
        self._active_origin = origin or previous_origin or "runtime"
        try:
            for d in dirs:
                if not d or not os.path.isdir(d):
                    continue
                for fname in sorted(os.listdir(d)):
                    if not fname.endswith(".py") or fname.startswith("_"):
                        continue
                    path = os.path.join(d, fname)
                    try:
                        mod_name = f"custom_widget_{fname[:-3]}"
                        spec = importlib.util.spec_from_file_location(mod_name, path)
                        if spec and spec.loader:
                            mod = importlib.util.module_from_spec(spec)
                            spec.loader.exec_module(mod)
                            logger.info("Loaded custom widget plugin: %s", path)
                    except Exception:
                        logger.exception("Failed to load custom widget plugin: %s", path)
        finally:
            self._active_origin = previous_origin
