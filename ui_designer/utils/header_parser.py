"""C header parser for extracting EmbeddedGUI widget API information.

Parses egui_view_*.h headers to extract struct types, init functions,
setter functions, params macros, and listener callbacks. Generates
widget registration templates for custom_widgets/*.py.
"""

import os
import re
from pathlib import Path


# ── Regex patterns ────────────────────────────────────────────────

# typedef struct egui_view_xxx egui_view_xxx_t;
RE_TYPEDEF = re.compile(
    r'typedef\s+struct\s+(egui_view_\w+)\s+\1_t\s*;'
)

# void egui_view_xxx_init(egui_view_t *self, egui_core_t *core);
RE_INIT = re.compile(
    r'void\s+(egui_view_\w+_init)\s*\('
    r'\s*egui_view_t\s*\*\s*self\s*'
    r'(?:,\s*egui_core_t\s*\*\s*core\s*)?\)\s*;'
)

# void egui_view_xxx_init_with_params(egui_view_t *self, const xxx_params_t *params);
RE_INIT_PARAMS = re.compile(
    r'void\s+(egui_view_\w+_init_with_params)\s*\('
    r'\s*egui_view_t\s*\*\s*self\s*,'
    r'\s*const\s+(egui_view_\w+_params_t)\s*\*\s*params\s*\)\s*;'
)

# #define EGUI_VIEW_XXX_PARAMS_INIT(args...)
RE_PARAMS_MACRO = re.compile(
    r'#define\s+(EGUI_VIEW_\w+_PARAMS_INIT(?:_\w+)?)\s*\(([^)]+)\)'
)

# void egui_view_xxx_set_yyy(egui_view_t *self, ...);
RE_SETTER = re.compile(
    r'void\s+(egui_view_\w+_set_\w+)\s*\(\s*egui_view_t\s*\*\s*self\s*'
    r'(?:,\s*(.+?))?\s*\)\s*;'
)

# typedef void (*egui_view_on_xxx_listener_t)(egui_view_t *self, ...);
RE_LISTENER_TYPEDEF = re.compile(
    r'typedef\s+void\s+\(\s*\*\s*(egui_view_on_\w+_listener_t)\s*\)\s*\('
    r'\s*egui_view_t\s*\*\s*self\s*(?:,\s*(.+?))?\s*\)\s*;'
)

# void egui_view_xxx_set_on_yyy_listener(egui_view_t *self, listener_type listener);
RE_SET_LISTENER = re.compile(
    r'void\s+(egui_view_\w+_set_on_\w+_listener)\s*\('
    r'\s*egui_view_t\s*\*\s*self\s*,\s*'
    r'(egui_view_\w+_listener_t)\s+listener\s*\)\s*;'
)

# typedef struct egui_view_xxx_params egui_view_xxx_params_t;
RE_PARAMS_TYPEDEF = re.compile(
    r'typedef\s+struct\s+(egui_view_\w+_params)\s+\1_t\s*;'
)


# ── C type to code_gen kind mapping ──────────────────────────────

def _infer_code_gen(func_name, params_str):
    """Infer code_gen descriptor from a setter function signature.

    Args:
        func_name: e.g. "egui_view_slider_set_value"
        params_str: parameter string after self, e.g. "uint8_t value"

    Returns:
        dict with code_gen descriptor, or None if not mappable.
    """
    if not params_str:
        return {"kind": "setter", "func": func_name}

    params_str = params_str.strip()
    parts = [p.strip() for p in params_str.split(",")]

    if len(parts) == 1:
        ptype, pname = _split_type_name(parts[0])
        if ptype == "const char *":
            return {"kind": "text_setter", "func": func_name}
        if ptype in ("const egui_font_t *", "egui_font_t *"):
            return {"kind": "derived_setter", "func": func_name,
                    "derive": "font", "cast": "(egui_font_t *)"}
        if ptype in ("const egui_image_t *", "egui_image_t *"):
            return {"kind": "derived_setter", "func": func_name,
                    "derive": "image", "cast": ""}
        if ptype in ("uint8_t", "int", "int16_t", "uint16_t", "int32_t", "uint32_t"):
            return {"kind": "setter", "func": func_name}
        return {"kind": "setter", "func": func_name}

    # Multi-parameter setter
    arg_names = []
    for p in parts:
        _, pname = _split_type_name(p)
        arg_names.append("{" + pname + "}")
    return {
        "kind": "multi_setter",
        "func": func_name,
        "args": ", ".join(arg_names),
    }


def _split_type_name(param):
    """Split 'uint8_t value' into ('uint8_t', 'value')."""
    param = param.strip()
    # Handle pointer types like "const char *text"
    if "*" in param:
        idx = param.rfind("*")
        return (param[:idx + 1].strip(), param[idx + 1:].strip())
    parts = param.rsplit(None, 1)
    if len(parts) == 2:
        return (parts[0], parts[1])
    return (param, "")


def _infer_property_type(c_type):
    """Map C type to property type string."""
    c_type = c_type.strip()
    if c_type == "const char *":
        return "string"
    if c_type in ("uint8_t", "int", "int16_t", "uint16_t", "int32_t", "uint32_t"):
        return "int"
    if c_type in ("egui_color_t",):
        return "color"
    if c_type in ("egui_alpha_t",):
        return "alpha"
    return "string"


# ── Header parsing ───────────────────────────────────────────────

class WidgetHeaderInfo:
    """Parsed information from a single widget header file."""

    def __init__(self):
        self.header_path = ""
        self.c_type = ""           # e.g. "egui_view_slider_t"
        self.struct_name = ""      # e.g. "egui_view_slider"
        self.init_func = ""        # e.g. "egui_view_slider_init"
        self.init_with_params = "" # e.g. "egui_view_slider_init_with_params"
        self.params_type = ""      # e.g. "egui_view_slider_params_t"
        self.params_macros = []    # e.g. ["EGUI_VIEW_SLIDER_PARAMS_INIT"]
        self.setters = []          # list of (func_name, params_str)
        self.listener_typedefs = {}  # listener_type -> params_str
        self.set_listeners = []    # list of (func_name, listener_type)

    @property
    def widget_name(self):
        """Extract widget name from struct: 'egui_view_slider' -> 'slider'."""
        if self.struct_name.startswith("egui_view_"):
            return self.struct_name[len("egui_view_"):]
        return self.struct_name


_APP_WIDGET_SCAN_IGNORE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".eguiproject",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".idea",
    ".vscode",
    "resource",
    "output",
    "dist",
}


def _should_ignore_widget_scan_dir(name):
    name = str(name or "").strip()
    if not name:
        return False
    if name in _APP_WIDGET_SCAN_IGNORE_DIRS:
        return True
    return name.startswith("build")


def discover_widget_headers(app_dir):
    """Recursively discover app-local ``egui_view_*.h`` headers."""
    app_dir = Path(app_dir)
    if not app_dir.is_dir():
        return []

    results = []
    for current_dir, dirnames, filenames in os.walk(str(app_dir)):
        dirnames[:] = sorted(d for d in dirnames if not _should_ignore_widget_scan_dir(d))
        for filename in sorted(filenames):
            if not filename.startswith("egui_view_") or not filename.endswith(".h"):
                continue
            results.append(str(Path(current_dir) / filename))
    return results


def parse_header(header_path):
    """Parse a single C header file and extract widget API info.

    Args:
        header_path: Path to the .h file.

    Returns:
        WidgetHeaderInfo or None if no widget typedef found.
    """
    path = Path(header_path)
    text = path.read_text(encoding="utf-8", errors="replace")

    info = WidgetHeaderInfo()
    info.header_path = str(path)

    # Find main struct typedef (prefer non-params typedef)
    matches = RE_TYPEDEF.findall(text)
    if not matches:
        return None
    # Filter out _params typedefs, prefer the main widget struct
    main_matches = [m for m in matches if not m.endswith("_params")]
    if main_matches:
        info.struct_name = main_matches[0]
    else:
        info.struct_name = matches[0]
    info.c_type = f"{info.struct_name}_t"

    # Init functions
    for m in RE_INIT.finditer(text):
        if "_init_with_params" not in m.group(1):
            info.init_func = m.group(1)

    for m in RE_INIT_PARAMS.finditer(text):
        info.init_with_params = m.group(1)
        info.params_type = m.group(2)

    # Params macros
    for m in RE_PARAMS_MACRO.finditer(text):
        info.params_macros.append(m.group(1))

    # Setter functions (exclude set_on_*_listener)
    for m in RE_SETTER.finditer(text):
        func_name = m.group(1)
        if "set_on_" in func_name and "_listener" in func_name:
            continue
        params_str = m.group(2) or ""
        info.setters.append((func_name, params_str))

    # Listener typedefs
    for m in RE_LISTENER_TYPEDEF.finditer(text):
        info.listener_typedefs[m.group(1)] = m.group(2) or ""

    # Set listener functions
    for m in RE_SET_LISTENER.finditer(text):
        info.set_listeners.append((m.group(1), m.group(2)))

    return info


def parse_widget_dir(widget_dir):
    """Parse all egui_view_*.h files in a directory.

    Returns:
        list of WidgetHeaderInfo objects.
    """
    results = []
    d = Path(widget_dir)
    for h in sorted(d.glob("egui_view_*.h")):
        info = parse_header(h)
        if info:
            results.append(info)
    return results


def _build_properties(info):
    props = {}
    for func_name, params_str in info.setters:
        prefix = f"egui_view_{info.widget_name}_set_"
        if not func_name.startswith(prefix):
            continue
        prop_name = func_name[len(prefix):]
        cg = _infer_code_gen(func_name, params_str)
        if cg is None:
            continue

        if params_str:
            parts = [p.strip() for p in params_str.split(",")]
            ptype, _ = _split_type_name(parts[0])
            prop_type = _infer_property_type(ptype)
        else:
            prop_type = "int"

        props[prop_name] = {
            "type": prop_type,
            "default": _default_for_type(prop_type),
            "code_gen": cg,
        }
    return props


def _build_events(info):
    events = {}
    for set_func, listener_type in info.set_listeners:
        prefix = f"egui_view_{info.widget_name}_set_on_"
        if not set_func.startswith(prefix):
            continue
        suffix = set_func[len(prefix):]
        if suffix.endswith("_listener"):
            suffix = suffix[:-len("_listener")]
        event_name = "on" + _snake_to_camel(suffix)

        listener_params = info.listener_typedefs.get(listener_type, "")
        if listener_params:
            sig = f"void {{func_name}}(egui_view_t *self, {listener_params})"
        else:
            sig = "void {func_name}(egui_view_t *self)"

        events[event_name] = {
            "setter": set_func,
            "signature": sig,
        }
    return events


def build_runtime_widget_registration(info, app_root):
    """Build an app-local widget registration payload from parsed header info."""
    if info is None:
        raise ValueError("missing widget header info")

    app_root_path = Path(app_root).resolve()
    header_path = Path(info.header_path).resolve()
    widget_name = info.widget_name
    c_type = info.c_type
    init_func = info.init_with_params or info.init_func
    if not widget_name or not c_type or not init_func:
        raise ValueError(f"{header_path.name} does not expose a usable widget init API")

    try:
        header_include = header_path.relative_to(app_root_path).as_posix()
    except ValueError:
        header_include = header_path.name

    descriptor = {
        "c_type": c_type,
        "init_func": init_func,
        "params_macro": info.params_macros[0] if info.params_macros else "",
        "params_type": info.params_type,
        "is_container": False,
        "add_child_func": None,
        "layout_func": None,
        "properties": _build_properties(info),
        "header_include": header_include,
        "source_header_path": str(header_path),
        "addable": True,
        "browser": {
            "keywords": [widget_name.replace("_", " "), "custom", header_path.stem],
            "browse_priority": 900,
        },
    }
    events = _build_events(info)
    if events:
        descriptor["events"] = events

    xml_tag = _snake_to_pascal(widget_name)
    return {
        "type_name": widget_name,
        "xml_tag": xml_tag,
        "display_name": xml_tag,
        "descriptor": descriptor,
    }


# ── Template generation ──────────────────────────────────────────

def generate_registration_template(info):
    """Generate a widget registration Python file from parsed header info.

    Args:
        info: WidgetHeaderInfo object.

    Returns:
        str: Python source code for a custom_widgets/*.py file.
    """
    wname = info.widget_name
    c_type = info.c_type
    init_func = info.init_with_params or info.init_func
    params_macro = info.params_macros[0] if info.params_macros else ""
    params_type = info.params_type

    props = _build_properties(info)
    events = _build_events(info)

    # Format XML tag
    xml_tag = _snake_to_pascal(wname)

    # Generate Python source
    lines = []
    lines.append(f'"""Auto-generated {xml_tag} widget plugin for EmbeddedGUI Designer."""')
    lines.append("from ui_designer.model.widget_registry import WidgetRegistry")
    lines.append("")
    lines.append("WidgetRegistry.instance().register(")
    lines.append(f'    type_name="{wname}",')
    lines.append("    descriptor={")
    lines.append(f'        "c_type": "{c_type}",')
    lines.append(f'        "init_func": "{init_func}",')
    lines.append(f'        "params_macro": "{params_macro}",')
    lines.append(f'        "params_type": "{params_type}",')
    lines.append(f'        "is_container": False,')
    lines.append(f'        "add_child_func": None,')
    lines.append(f'        "layout_func": None,')
    lines.append(f'        "properties": {{')
    for pname, pdef in props.items():
        lines.append(f'            "{pname}": {{')
        lines.append(f'                "type": "{pdef["type"]}", "default": {_repr_default(pdef["default"])},')
        cg = pdef["code_gen"]
        cg_str = _format_code_gen(cg)
        lines.append(f'                "code_gen": {cg_str},')
        lines.append(f'            }},')
    lines.append(f'        }},')
    if events:
        lines.append(f'        "events": {{')
        for ename, edef in events.items():
            lines.append(f'            "{ename}": {{')
            lines.append(f'                "setter": "{edef["setter"]}",')
            lines.append(f'                "signature": "{edef["signature"]}",')
            lines.append(f'            }},')
        lines.append(f'        }},')
    lines.append("    },")
    lines.append(f'    xml_tag="{xml_tag}",')
    lines.append(f'    display_name="{xml_tag}",')
    lines.append(")")
    lines.append("")

    return "\n".join(lines)


def _default_for_type(prop_type):
    """Return a sensible default value for a property type."""
    if prop_type == "string":
        return ""
    if prop_type == "int":
        return 0
    if prop_type == "color":
        return "EGUI_COLOR_WHITE"
    if prop_type == "alpha":
        return "EGUI_ALPHA_100"
    return ""


def _repr_default(val):
    """Format a default value for Python source output."""
    if isinstance(val, str):
        return f'"{val}"'
    return repr(val)


def _format_code_gen(cg):
    """Format a code_gen dict as a Python dict literal string."""
    parts = []
    for k, v in cg.items():
        parts.append(f'"{k}": "{v}"')
    return "{" + ", ".join(parts) + "}"


def _snake_to_camel(s):
    """Convert snake_case to CamelCase: 'value_changed' -> 'ValueChanged'."""
    return "".join(w.capitalize() for w in s.split("_"))


def _snake_to_pascal(s):
    """Convert snake_case to PascalCase: 'progress_bar' -> 'ProgressBar'."""
    return "".join(w.capitalize() for w in s.split("_"))

