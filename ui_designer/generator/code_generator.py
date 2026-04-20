"""C code generator for EmbeddedGUI Designer — MFC-style multi-file output.

Architecture (per page):
    .designer/{page_name}.h        — generated page struct + hook declarations
    .designer/{page_name}_layout.c — generated lifecycle wrappers + layout code
    {page_name}.c                  — user implementation (created once)
    {page_name}_ext.h              — user struct extension / hook override macros

Framework files (fully generated, always overwritten):
    .designer/uicode.h
    .designer/uicode.c
    .designer/app_egui_config_designer.h
    .designer/build_designer.mk

This keeps always-generated Designer outputs under ``.designer/`` while
leaving business logic in root ``*.c`` / ``*_ext.h`` files.
"""

from dataclasses import dataclass
import re

# Current page split:
#   {page}.h        - fully generated page struct + hook declarations
#   {page}_layout.c - fully generated lifecycle wrappers + layout code
#   {page}.c        - user-owned hook implementations
#   {page}_ext.h    - user-owned struct extension / hook override macros

from ..model.widget_model import (
    WidgetModel, BackgroundModel,
    AnimationModel, ANIMATION_TYPES, INTERPOLATOR_TYPES,
    derive_image_c_expr, derive_font_c_expr,
)
from ..model.page_fields import page_field_declaration, page_field_default_assignment, valid_page_fields
from ..model.page_timers import valid_page_timers
from ..model.widget_registry import WidgetRegistry
from ..model.string_resource import parse_string_ref
from ..utils.scaffold import (
    APP_CONFIG_DESIGNER_RELPATH,
    BUILD_DESIGNER_RELPATH,
    UICODE_DISP_HEADER_RELPATH,
    UICODE_HEADER_RELPATH,
    UICODE_SOURCE_RELPATH,
    designer_page_header_relpath,
    designer_page_layout_relpath,
    materialize_generated_project_files,
    make_app_build_designer_mk_content,
    make_app_config_designer_h_content,
    page_ext_header_relpath,
    page_user_source_relpath,
    project_config_backup_dir,
)


def _get_type_info(widget_type):
    """Get type info from registry."""
    return WidgetRegistry.instance().get(widget_type)


def _collect_project_widget_registry_errors(project):
    registry = WidgetRegistry.instance()
    errors = []

    for page in getattr(project, "pages", []) or []:
        for widget in page.get_all_widgets():
            if registry.has(widget.widget_type):
                continue
            errors.append(
                f"{page.name}/{widget.name}: unknown widget type '{widget.widget_type}'"
            )

    return errors


def _page_custom_header_includes(page):
    includes = []
    seen = set()
    for widget in page.get_all_widgets():
        header_include = str(_get_type_info(widget.widget_type).get("header_include", "") or "").strip()
        if not header_include or header_include in seen:
            continue
        seen.add(header_include)
        includes.append(header_include.replace("\\", "/"))
    return sorted(includes)


# ── Helpers ────────────────────────────────────────────────────────

def _simple_init_func(widget_type):
    """Get the simple init function (without params) for a widget type."""
    info = _get_type_info(widget_type)
    func = info.get("init_func", "")
    return func.replace("_with_params", "")


def _bg_macro_name(bg_type):
    """Map bg_type to the EGUI background macro suffix."""
    mapping = {
        "solid": "SOLID",
        "round_rectangle": "ROUND_RECTANGLE",
        "round_rectangle_corners": "ROUND_RECTANGLE_CORNERS",
        "circle": "CIRCLE",
    }
    return mapping.get(bg_type, "SOLID")


def _gradient_dir_macro(direction):
    """Map gradient direction string to C macro."""
    mapping = {
        "vertical": "EGUI_BACKGROUND_GRADIENT_DIR_VERTICAL",
        "horizontal": "EGUI_BACKGROUND_GRADIENT_DIR_HORIZONTAL",
    }
    return mapping.get(direction, "EGUI_BACKGROUND_GRADIENT_DIR_VERTICAL")


def _gen_bg_param_init(param_name, bg, bg_type_override=None):
    """Generate a EGUI_BACKGROUND_COLOR_PARAM_INIT_xxx(...) line."""
    bt = bg_type_override or bg.bg_type

    # Gradient background uses a different macro
    if bt == "gradient":
        direction = _gradient_dir_macro(bg.direction)
        return (
            f"EGUI_BACKGROUND_GRADIENT_PARAM_INIT({param_name}, "
            f"{direction}, {bg.start_color}, {bg.end_color}, {bg.alpha});"
        )
    macro = _bg_macro_name(bt)

    if bg.stroke_width > 0:
        macro += "_STROKE"

    args = [param_name]

    if bt == "solid":
        args += [bg.color, bg.alpha]
    elif bt == "round_rectangle":
        args += [bg.color, bg.alpha, str(bg.radius)]
    elif bt == "round_rectangle_corners":
        args += [
            bg.color, bg.alpha,
            str(bg.radius_left_top), str(bg.radius_left_bottom),
            str(bg.radius_right_top), str(bg.radius_right_bottom),
        ]
    elif bt == "circle":
        args += [bg.color, bg.alpha, str(bg.radius)]

    if bg.stroke_width > 0:
        args += [str(bg.stroke_width), bg.stroke_color, bg.stroke_alpha]

    return f"EGUI_BACKGROUND_COLOR_PARAM_INIT_{macro}({', '.join(args)});"


def _upper_guard(name):
    """Convert page name to header guard: main_page -> _MAIN_PAGE_H_"""
    return f"_{name.upper()}_H_"


def _page_ext_guard(name):
    return f"_{name.upper()}_EXT_H_"


def _page_hook_macro_names(name):
    upper = name.upper()
    return {
        "fields": f"EGUI_{upper}_EXT_FIELDS",
        "init": f"EGUI_{upper}_HOOK_INIT",
        "on_open": f"EGUI_{upper}_HOOK_ON_OPEN",
        "on_close": f"EGUI_{upper}_HOOK_ON_CLOSE",
        "on_key": f"EGUI_{upper}_HOOK_ON_KEY",
    }


def _page_user_hook_names(name):
    prefix = f"egui_{name}"
    return {
        "init": f"{prefix}_user_init",
        "on_open": f"{prefix}_user_on_open",
        "on_close": f"{prefix}_user_on_close",
        "on_key": f"{prefix}_user_on_key_pressed",
    }


def _timer_helper_names(name):
    prefix = f"egui_{name}"
    return {
        "init": f"{prefix}_timers_init",
        "start_auto": f"{prefix}_timers_start_auto",
        "stop": f"{prefix}_timers_stop",
    }


def _format_callback_signature(signature, func_name):
    if not signature or not func_name:
        return ""
    try:
        return signature.format(func_name=func_name)
    except Exception:
        return signature.replace("{func_name}", func_name)


def _extract_parameter_names(signature_line):
    if "(" not in signature_line or ")" not in signature_line:
        return []
    params = signature_line.split("(", 1)[1].rsplit(")", 1)[0].strip()
    if not params or params == "void":
        return []

    names = []
    for raw_param in params.split(","):
        param = raw_param.strip()
        if not param or param == "void":
            continue
        match = re.search(r"([A-Za-z_]\w*)\s*(?:\[[^\]]*\])?$", param)
        if match:
            names.append(match.group(1))
    return names


def _function_definition_exists(content, func_name):
    if not content or not func_name:
        return False
    pattern = rf"^\s*(?:static\s+)?void\s+{re.escape(func_name)}\s*\("
    return re.search(pattern, content, re.MULTILINE) is not None


def collect_page_callback_stubs(page):
    """Collect callback skeleton metadata for a page."""
    callbacks = []
    seen = set()

    if page is None:
        return callbacks

    for widget in page.get_all_widgets():
        if widget.on_click:
            key = ("view", widget.on_click)
            if key not in seen:
                seen.add(key)
                callbacks.append(
                    {
                        "kind": "view",
                        "name": widget.on_click,
                        "signature": "void {func_name}(egui_view_t *self)",
                    }
                )

        type_info = _get_type_info(widget.widget_type)
        events_def = type_info.get("events", {})
        for event_name, func_name in sorted(widget.events.items()):
            if not func_name:
                continue
            event_info = events_def.get(event_name)
            if not event_info:
                continue
            key = ("view", func_name)
            if key in seen:
                continue
            seen.add(key)
            callbacks.append(
                {
                    "kind": "view",
                    "name": func_name,
                    "signature": event_info.get("signature", ""),
                }
            )

    for timer in valid_page_timers(page, getattr(page, "timers", [])):
        callback_name = timer.get("callback", "")
        if not callback_name:
            continue
        key = ("timer", callback_name)
        if key in seen:
            continue
        seen.add(key)
        callbacks.append(
            {
                "kind": "timer",
                "name": callback_name,
                "signature": "void {func_name}(egui_timer_t *timer)",
            }
        )

    return callbacks


def render_page_callback_stub(page, callback_name, signature, kind="view"):
    """Render a callback stub suitable for a page user source file."""
    signature_line = _format_callback_signature(signature, callback_name)
    if not signature_line:
        return ""

    lines = [signature_line, "{"]
    if kind == "timer":
        struct_type = f"egui_{page.name}_t"
        lines.append(f"    {struct_type} *local = ({struct_type} *)timer->user_data;")
        lines.append("    EGUI_UNUSED(local);")
        lines.append("    // TODO: Handle timer tick here")
    else:
        for param_name in _extract_parameter_names(signature_line):
            lines.append(f"    EGUI_UNUSED({param_name});")
        lines.append("    // TODO: Handle callback here")
    lines.append("}")
    return "\n".join(lines)


# ── Per-widget init code (data-driven) ───────────────────────────

def _emit_property_code(widget, prop_name, prop_def, cg, cast, indent):
    """Emit a single C line from a code_gen descriptor.

    Returns a string (one C statement) or None if nothing to emit.
    """
    kind = cg["kind"]

    # Kinds that carry no runtime setter (used only for params / struct init)
    if kind in ("param_only", "param"):
        return None

    func = cg["func"]
    value = widget.properties.get(prop_name, prop_def.get("default"))

    def _resolve_scalar_value():
        skip = cg.get("skip_default", True)
        if skip and value == prop_def.get("default"):
            return None
        skip_values = cg.get("skip_values", [])
        if value in skip_values:
            return None
        value_map = cg.get("value_map")
        if value_map and value in value_map:
            return value_map[value]
        if cg.get("bool_to_int"):
            return "1" if value else "0"
        return str(value)

    if kind == "setter":
        c_value = _resolve_scalar_value()
        if c_value is None:
            return None
        return f"{indent}{func}({cast}, {c_value});"

    elif kind == "field_setter":
        c_value = _resolve_scalar_value()
        if c_value is None:
            return None
        cast_type = cg.get("cast_type", "")
        field_name = cg.get("field", "")
        if not cast_type or not field_name:
            return None
        return f"{indent}(({cast_type} *)&local->{widget.name})->{field_name} = {c_value};"

    elif kind == "text_setter":
        text = str(value or "")
        if not text:
            return None
        str_key = parse_string_ref(text)
        if str_key is not None:
            enum_name = f"EGUI_STR_{str_key.upper()}"
            return f'{indent}{func}({cast}, egui_i18n_get({enum_name}));'
        return f'{indent}{func}({cast}, "{text}");'

    elif kind == "multi_setter":
        # Check skip conditions
        if cg.get("skip_default") and value == prop_def.get("default"):
            return None
        # Collect values from multiple properties referenced in args template
        args_tpl = cg["args"]
        # Normalize list form to comma-separated string (e.g. ["{year}", "{month}"])
        if isinstance(args_tpl, list):
            args_tpl = ", ".join(args_tpl)
        props = widget.properties
        # Replace {prop_name} placeholders with actual values
        import re as _re
        def _repl(m):
            key = m.group(1)
            return str(props.get(key, prop_def.get("default", "")))
        c_args = _re.sub(r'\{(\w+)\}', _repl, args_tpl)
        return f"{indent}{func}({cast}, {c_args});"

    elif kind == "derived_setter":
        derive_type = cg["derive"]
        cast_prefix = cg.get("cast", "")
        if derive_type == "font":
            expr = derive_font_c_expr(widget)
        elif derive_type == "image":
            expr = derive_image_c_expr(widget)
        else:
            return None
        if not expr or expr == "NULL":
            return None
        return f"{indent}{func}({cast}, {cast_prefix}{expr});"

    elif kind == "image_setter":
        expr = derive_image_c_expr(widget)
        if not expr or expr == "NULL":
            return None
        cast_prefix = cg.get("cast", "")
        return f"{indent}{func}({cast}, {cast_prefix}{expr});"

    return None


def _gen_widget_init_lines(widget, indent="    ", *, core_expr="core"):
    """Generate explicit API calls to init a single widget.

    Uses ``local->{name}`` as the widget reference (inside on_open).
    Returns a list of lines (without leading newlines).

    Property-specific code is driven by the ``code_gen`` descriptors
    in WIDGET_TYPES, so new widget types need no changes here.
    """
    lines = []
    wt = widget.widget_type
    ref = f"local->{widget.name}"
    cast = f"(egui_view_t *)&{ref}"

    # Widget name comment for readability
    lines.append(f"{indent}// {widget.name} ({wt})")

    # Init
    init_func = _simple_init_func(wt)
    if init_func:
        lines.append(f"{indent}{init_func}({cast}, {core_expr});")

    # Position & Size
    lines.append(f"{indent}egui_view_set_position({cast}, {widget.x}, {widget.y});")
    lines.append(f"{indent}egui_view_set_size({cast}, {widget.width}, {widget.height});")

    # Margin
    has_individual = (widget.margin_left or widget.margin_right or
                      widget.margin_top or widget.margin_bottom)
    if has_individual:
        lines.append(
            f"{indent}egui_view_set_margin({cast}, "
            f"{widget.margin_left}, {widget.margin_right}, "
            f"{widget.margin_top}, {widget.margin_bottom});"
        )
    elif widget.margin != 0:
        lines.append(f"{indent}egui_view_set_margin_all({cast}, {widget.margin});")

    # ── Data-driven property setters ──
    type_info = _get_type_info(wt)
    props_def = type_info.get("properties", {})
    emitted_groups = set()

    for prop_name, prop_def in props_def.items():
        cg = prop_def.get("code_gen")
        if cg is None:
            continue

        # Skip if this property belongs to a group already emitted
        group = cg.get("group")
        if group:
            if group in emitted_groups:
                continue
            emitted_groups.add(group)

        line = _emit_property_code(widget, prop_name, prop_def, cg, cast, indent)
        if line:
            lines.append(line)

    # on_click listener
    if widget.on_click:
        lines.append(f"{indent}egui_view_set_on_click_listener({cast}, {widget.on_click});")

    # Event listeners (data-driven from registry)
    type_info = _get_type_info(wt)
    events_def = type_info.get("events", {})
    for event_name, func_name in widget.events.items():
        if not func_name:
            continue
        event_info = events_def.get(event_name)
        if not event_info:
            continue
        setter = event_info["setter"]
        lines.append(f"{indent}{setter}({cast}, {func_name});")

    return lines


# ── Background generation (file-scope declarations) ──────────────

def _gen_bg_declarations(all_widgets, page_name):
    """Generate background declaration lines at file scope.

    Returns (decl_lines, init_lines).
      decl_lines: file-scope static declarations
      init_lines: code to run inside on_open (init_with_params + set_background)
    """
    decl_lines = []
    init_lines = []

    bg_widgets = [w for w in all_widgets if w.background and w.background.bg_type != "none"]
    if not bg_widgets:
        return decl_lines, init_lines

    decl_lines.append("// Background declarations")

    for w in bg_widgets:
        bg = w.background
        bg_name = f"bg_{page_name}_{w.name}"
        is_gradient = (bg.bg_type == "gradient")

        # Static object — different type for gradient
        if is_gradient:
            decl_lines.append(f"static egui_background_gradient_t {bg_name};")
        else:
            decl_lines.append(f"static egui_background_color_t {bg_name};")

        # Normal param
        normal_param = f"{bg_name}_param_normal"
        decl_lines.append(_gen_bg_param_init(normal_param, bg))

        # Pressed param
        pressed_ref = "NULL"
        if bg.has_pressed:
            pressed_bg = BackgroundModel()
            pressed_bg.bg_type = bg.bg_type
            pressed_bg.color = bg.pressed_color
            pressed_bg.alpha = bg.pressed_alpha
            pressed_bg.radius = bg.radius
            pressed_bg.radius_left_top = bg.radius_left_top
            pressed_bg.radius_left_bottom = bg.radius_left_bottom
            pressed_bg.radius_right_top = bg.radius_right_top
            pressed_bg.radius_right_bottom = bg.radius_right_bottom
            pressed_bg.stroke_width = bg.stroke_width
            pressed_bg.stroke_color = bg.stroke_color
            pressed_bg.stroke_alpha = bg.stroke_alpha
            pressed_param = f"{bg_name}_param_pressed"
            decl_lines.append(_gen_bg_param_init(pressed_param, pressed_bg))
            pressed_ref = f"&{pressed_param}"

        # Disabled param
        disabled_ref = "NULL"
        if bg.has_disabled:
            disabled_bg = BackgroundModel()
            disabled_bg.bg_type = "solid"
            disabled_bg.color = bg.disabled_color
            disabled_bg.alpha = bg.disabled_alpha
            disabled_bg.stroke_width = 0
            disabled_param = f"{bg_name}_param_disabled"
            decl_lines.append(_gen_bg_param_init(disabled_param, disabled_bg, "solid"))
            disabled_ref = f"&{disabled_param}"

        # Combined params
        decl_lines.append(
            f"EGUI_BACKGROUND_PARAM_INIT({bg_name}_params, "
            f"&{normal_param}, {pressed_ref}, {disabled_ref});"
        )
        decl_lines.append("")

        # Init code for on_open
        if is_gradient:
            init_lines.append(
                f"    egui_background_gradient_init_with_params("
                f"(egui_background_t *)&{bg_name}, &{bg_name}_params);"
            )
        else:
            init_lines.append(
                f"    egui_background_color_init_with_params("
                f"(egui_background_t *)&{bg_name}, &{bg_name}_params);"
            )
        init_lines.append(
            f"    egui_view_set_background("
            f"(egui_view_t *)&local->{w.name}, (egui_background_t *)&{bg_name});"
        )

        # Card widgets have their own bg_color/border drawn in on_draw(),
        # which covers the view background. Sync them from the Background.
        if w.widget_type == "card":
            init_lines.append(
                f"    egui_view_card_set_bg_color("
                f"(egui_view_t *)&local->{w.name}, {bg.color}, {bg.alpha});"
            )
            if bg.stroke_width > 0:
                init_lines.append(
                    f"    egui_view_card_set_border("
                    f"(egui_view_t *)&local->{w.name}, {bg.stroke_width}, {bg.stroke_color});"
                )
            else:
                init_lines.append(
                    f"    egui_view_card_set_border("
                    f"(egui_view_t *)&local->{w.name}, 0, {bg.color});"
                )

    return decl_lines, init_lines


# ── Shadow generation (file-scope declarations) ──────────────────

def _gen_shadow_declarations(all_widgets, page_name):
    """Generate shadow declaration lines at file scope.

    Returns (decl_lines, init_lines).
      decl_lines: file-scope static shadow param declarations
      init_lines: code to run inside on_open (egui_view_set_shadow calls)
    """
    decl_lines = []
    init_lines = []

    shadow_widgets = [w for w in all_widgets if w.shadow is not None]
    if not shadow_widgets:
        return decl_lines, init_lines

    decl_lines.append("// Shadow declarations")

    for w in shadow_widgets:
        s = w.shadow
        shadow_name = f"shadow_{page_name}_{w.name}"

        if s.corner_radius > 0:
            decl_lines.append(
                f"EGUI_SHADOW_PARAM_INIT_ROUND({shadow_name}, "
                f"{s.width}, {s.ofs_x}, {s.ofs_y}, "
                f"{s.color}, {s.opa}, {s.corner_radius});"
            )
        else:
            decl_lines.append(
                f"EGUI_SHADOW_PARAM_INIT({shadow_name}, "
                f"{s.width}, {s.ofs_x}, {s.ofs_y}, "
                f"{s.color}, {s.opa});"
            )

        init_lines.append(
            f"    egui_view_set_shadow("
            f"(egui_view_t *)&local->{w.name}, &{shadow_name});"
        )

    decl_lines.append("")
    return decl_lines, init_lines


# ── Animation generation (file-scope declarations) ────────────────

def _gen_anim_declarations(all_widgets, page_name):
    """Generate animation declaration and init lines.

    Returns (decl_lines, init_lines).
    """
    decl_lines = []
    init_lines = []

    anim_widgets = [w for w in all_widgets if w.animations]
    if not anim_widgets:
        return decl_lines, init_lines

    decl_lines.append("// Animation declarations")
    for w in anim_widgets:
        for i, anim in enumerate(w.animations):
            ainfo = ANIMATION_TYPES.get(anim.anim_type)
            if not ainfo:
                continue
            suffix = f"_{i}" if len(w.animations) > 1 else ""
            anim_name = f"anim_{w.name}_{anim.anim_type}{suffix}"
            member = f"local->{anim_name}"
            anim_cast = f"EGUI_ANIM_OF(&{member})"
            view_cast = f"(egui_view_t *)&local->{w.name}"

            # Params macro
            param_vals = ", ".join(
                str(anim.params.get(p, "0")) for p in ainfo["params"]
            )
            decl_lines.append(
                f"{ainfo['params_macro']}({anim_name}_params, {param_vals});"
            )

            # Interpolator instance
            interp_key = anim.interpolator
            interp_base = INTERPOLATOR_TYPES.get(interp_key, "egui_interpolator_linear")
            decl_lines.append(
                f"static {interp_base}_t {anim_name}_interpolator;"
            )
            decl_lines.append("")

            # Init lines (inside layout_init)
            init_lines.append(
                f"    {ainfo['init_func']}({anim_cast});"
            )
            init_lines.append(
                f"    {ainfo['params_set_func']}(&{member}, &{anim_name}_params);"
            )
            init_lines.append(
                f"    egui_animation_duration_set({anim_cast}, {anim.duration});"
            )
            # Interpolator init + set
            init_lines.append(
                f"    {interp_base}_init((egui_interpolator_t *)&{anim_name}_interpolator);"
            )
            init_lines.append(
                f"    egui_animation_interpolator_set({anim_cast}, "
                f"(egui_interpolator_t *)&{anim_name}_interpolator);"
            )
            # Repeat settings
            if anim.repeat_count != 0:
                init_lines.append(
                    f"    egui_animation_repeat_count_set({anim_cast}, {anim.repeat_count});"
                )
            if anim.repeat_mode == "reverse":
                init_lines.append(
                    f"    egui_animation_repeat_mode_set({anim_cast}, "
                    f"EGUI_ANIMATION_REPEAT_MODE_REVERSE);"
                )
            # Target view
            init_lines.append(
                f"    egui_animation_target_view_set({anim_cast}, {view_cast});"
            )
            # Auto start
            if anim.auto_start:
                init_lines.append(
                    f"    egui_animation_start({anim_cast});"
                )
            init_lines.append("")

    return decl_lines, init_lines


# ── Page Header (.h) ─────────────────────────────────────────────

def generate_page_header(page, project):
    """Generate the ``.designer/{page_name}.h`` file content.

    This file is fully regenerated on every save.
    """
    name = page.name
    guard = _upper_guard(name)
    struct_name = f"egui_{name}"
    struct_type = f"egui_{name}_t"
    ext_header = page_ext_header_relpath(name)
    hook_macros = _page_hook_macro_names(name)
    hook_funcs = _page_user_hook_names(name)
    helper_names = _timer_helper_names(name)

    lines = []
    lines.append(f"#ifndef {guard}")
    lines.append(f"#define {guard}")
    lines.append("")
    lines.append("// ===== Auto-generated by EmbeddedGUI Designer =====")
    lines.append("// This file is regenerated when the layout changes.")
    lines.append(
        f"// Extend the page via the user-owned {page_ext_header_relpath(name)} and {page_user_source_relpath(name)} files."
    )
    lines.append("")
    lines.append('#include "egui.h"')
    for header_include in _page_custom_header_includes(page):
        lines.append(f'#include "{header_include}"')
    lines.append("")
    lines.append(f"typedef struct {struct_name} {struct_type};")
    lines.append(f'#include "{ext_header}"')
    lines.append("")
    lines.append(f"#ifndef {hook_macros['fields']}")
    lines.append(f"#define {hook_macros['fields']}")
    lines.append("#endif")
    lines.append("")
    lines.append(f"#ifndef {hook_macros['init']}")
    lines.append(f"#define {hook_macros['init']}(_page) {hook_funcs['init']}(_page)")
    lines.append("#endif")
    lines.append(f"#ifndef {hook_macros['on_open']}")
    lines.append(f"#define {hook_macros['on_open']}(_page) {hook_funcs['on_open']}(_page)")
    lines.append("#endif")
    lines.append(f"#ifndef {hook_macros['on_close']}")
    lines.append(f"#define {hook_macros['on_close']}(_page) {hook_funcs['on_close']}(_page)")
    lines.append("#endif")
    lines.append(f"#ifndef {hook_macros['on_key']}")
    lines.append(
        f"#define {hook_macros['on_key']}(_page, _keycode) {hook_funcs['on_key']}(_page, _keycode)"
    )
    lines.append("#endif")
    lines.append("")
    lines.append("/* Set up for C function definitions, even when using C++ */")
    lines.append("#ifdef __cplusplus")
    lines.append('extern "C" {')
    lines.append("#endif")
    lines.append("")
    lines.append(f"void {hook_funcs['init']}({struct_type} *page);")
    lines.append(f"void {hook_funcs['on_open']}({struct_type} *page);")
    lines.append(f"void {hook_funcs['on_close']}({struct_type} *page);")
    lines.append(f"void {hook_funcs['on_key']}({struct_type} *page, uint16_t keycode);")
    lines.append("")

    lines.append(f"struct {struct_name}")
    lines.append("{")
    lines.append("    egui_page_base_t base;")
    lines.append("")

    # Widget members (all widgets in this page) — generated
    all_widgets = page.get_all_widgets()
    if all_widgets:
        lines.append("    // UI widgets (auto-generated, do not edit)")
        for w in all_widgets:
            type_info = _get_type_info(w.widget_type)
            c_type = type_info.get("c_type", "egui_view_t")
            lines.append(f"    {c_type} {w.name};")
        lines.append("")

    # Animation struct members
    anim_widgets = [w for w in all_widgets if w.animations]
    if anim_widgets:
        lines.append("    // Animations (auto-generated, do not edit)")
        for w in anim_widgets:
            for i, anim in enumerate(w.animations):
                ainfo = ANIMATION_TYPES.get(anim.anim_type, {})
                c_type = ainfo.get("c_type", "egui_animation_t")
                suffix = f"_{i}" if len(w.animations) > 1 else ""
                lines.append(
                    f"    {c_type} anim_{w.name}_{anim.anim_type}{suffix};"
                )
        lines.append("")

    generated_timers = valid_page_timers(page, getattr(page, "timers", []))
    if generated_timers:
        lines.append("    // Timers (auto-generated from Designer metadata)")
        for timer in generated_timers:
            lines.append(f"    egui_timer_t {timer['name']};")
        lines.append("")

    generated_page_fields = [field for field in valid_page_fields(page, page.user_fields) if page_field_declaration(field)]
    if generated_page_fields:
        lines.append("    // Page fields (auto-generated from Designer metadata)")
        for field in generated_page_fields:
            lines.append(f"    {page_field_declaration(field)}")
        lines.append("")

    lines.append(f"    {hook_macros['fields']}")
    lines.append("};")
    lines.append("")

    # Function declarations
    lines.append(
        f"// Layout init (auto-generated in {designer_page_layout_relpath(name)})"
    )
    lines.append(f"void {struct_name}_layout_init(egui_page_base_t *self);")
    lines.append("")
    lines.append(
        f"// Page init (auto-generated in {designer_page_layout_relpath(name)})"
    )
    lines.append(f"void {struct_name}_init(egui_page_base_t *self, egui_core_t *core);")
    lines.append("")
    if generated_timers:
        lines.append(
            f"// Timer helpers (auto-generated in {designer_page_layout_relpath(name)})"
        )
        lines.append(f"void {helper_names['init']}(egui_page_base_t *self);")
        lines.append(f"void {helper_names['start_auto']}(egui_page_base_t *self);")
        lines.append(f"void {helper_names['stop']}(egui_page_base_t *self);")
        lines.append("")
    lines.append("/* Ends C function definitions when using C++ */")
    lines.append("#ifdef __cplusplus")
    lines.append("}")
    lines.append("#endif")
    lines.append("")
    lines.append(f"#endif /* {guard} */")
    lines.append("")

    return "\n".join(lines)


# ── Page Layout Source (*_layout.c) — 100% generated ─────────────

def generate_page_layout_source(page, project):
    """Generate the ``.designer/{page_name}_layout.c`` file content.

    This file is 100% auto-generated and overwritten on every save.
    It contains NO user code regions. All widget initialization,
    hierarchy building, page lifecycle wrappers, and layout logic lives here.
    """
    name = page.name
    prefix = f"egui_{name}"
    struct_type = f"egui_{name}_t"
    hook_macros = _page_hook_macro_names(name)
    helper_names = _timer_helper_names(name)
    all_widgets = page.get_all_widgets()
    generated_timers = valid_page_timers(page, getattr(page, "timers", []))
    has_timers = bool(generated_timers)
    has_auto_start_timers = any(timer.get("auto_start") for timer in generated_timers)

    lines = []
    lines.append("// ===== Auto-generated by EmbeddedGUI Designer =====")
    lines.append("// DO NOT EDIT – this file is fully regenerated on every save.")
    lines.append(
        f"// User logic belongs in {page_user_source_relpath(name)} and {page_ext_header_relpath(name)} (never overwritten)."
    )
    lines.append("")
    lines.append('#include "egui.h"')
    lines.append("#include <stdlib.h>")
    lines.append("")
    lines.append('#include "uicode.h"')
    lines.append(f'#include "{name}.h"')

    # Include i18n header if any widget uses @string/ references
    _has_string_refs = False
    for w in all_widgets:
        text = w.properties.get("text", "")
        if parse_string_ref(text) is not None:
            _has_string_refs = True
            break
    if _has_string_refs:
        lines.append('#include "egui_strings.h"')

    lines.append("")

    # Forward declarations for onClick callbacks (defined in user .c file)
    callback_funcs = set()
    for w in all_widgets:
        if w.on_click:
            callback_funcs.add(w.on_click)
    if callback_funcs:
        lines.append("// Forward declarations for onClick callbacks")
        for func_name in sorted(callback_funcs):
            lines.append(f"extern void {func_name}(egui_view_t *self);")
        lines.append("")

    # Forward declarations for event callbacks (defined in user .c file)
    event_decls = []  # (signature_line, sort_key)
    for w in all_widgets:
        type_info = _get_type_info(w.widget_type)
        events_def = type_info.get("events", {})
        for event_name, func_name in w.events.items():
            if not func_name:
                continue
            event_info = events_def.get(event_name)
            if not event_info:
                continue
            sig = event_info["signature"].format(func_name=func_name)
            decl = f"extern {sig};"
            event_decls.append((decl, func_name))
    if event_decls:
        lines.append("// Forward declarations for event callbacks")
        seen = set()
        for decl, key in sorted(event_decls, key=lambda x: x[1]):
            if decl not in seen:
                seen.add(decl)
                lines.append(decl)
        lines.append("")

    # Background file-scope declarations
    bg_decl_lines, bg_init_lines = _gen_bg_declarations(all_widgets, name)
    if bg_decl_lines:
        lines.extend(bg_decl_lines)
        lines.append("")

    # Shadow file-scope declarations
    shadow_decl_lines, shadow_init_lines = _gen_shadow_declarations(all_widgets, name)
    if shadow_decl_lines:
        lines.extend(shadow_decl_lines)
        lines.append("")

    # Animation file-scope declarations (params + interpolators)
    anim_decl_lines, anim_init_lines = _gen_anim_declarations(all_widgets, name)
    if anim_decl_lines:
        lines.extend(anim_decl_lines)
        lines.append("")

    auto_start_timers = [timer for timer in generated_timers if timer.get("auto_start")]
    if generated_timers:
        callback_names = sorted({timer["callback"] for timer in generated_timers if timer.get("callback")})
        if callback_names:
            lines.append("// Forward declarations for timer callbacks")
            for callback_name in callback_names:
                lines.append(f"extern void {callback_name}(egui_timer_t *timer);")
            lines.append("")

        lines.append(f"void {helper_names['init']}(egui_page_base_t *self)")
        lines.append("{")
        lines.append(f"    {struct_type} *local = ({struct_type} *)self;")
        for timer in generated_timers:
            lines.append(
                f"    egui_timer_init_timer(&local->{timer['name']}, (void *)local, {timer['callback']});"
            )
        lines.append("}")
        lines.append("")

        lines.append(f"void {helper_names['start_auto']}(egui_page_base_t *self)")
        lines.append("{")
        lines.append(f"    {struct_type} *local = ({struct_type} *)self;")
        if auto_start_timers:
            for timer in auto_start_timers:
                lines.append(
                    f"    egui_page_base_start_timer(self, &local->{timer['name']}, {timer['delay_ms']}, {timer['period_ms']});"
                )
        else:
            lines.append("    EGUI_UNUSED(local);")
        lines.append("}")
        lines.append("")

        lines.append(f"void {helper_names['stop']}(egui_page_base_t *self)")
        lines.append("{")
        lines.append(f"    {struct_type} *local = ({struct_type} *)self;")
        for timer in generated_timers:
            lines.append(f"    egui_page_base_stop_timer(self, &local->{timer['name']});")
        lines.append("}")
        lines.append("")

    # ── layout_init function ──
    lines.append(f"void {prefix}_layout_init(egui_page_base_t *self)")
    lines.append("{")
    lines.append(f"    {struct_type} *local = ({struct_type} *)self;")
    lines.append("    egui_core_t *core = egui_page_base_get_core(self);")
    lines.append("    EGUI_UNUSED(core);")
    lines.append("")

    field_init_lines = []
    for field in valid_page_fields(page, page.user_fields):
        assignment = page_field_default_assignment(field)
        if assignment:
            field_init_lines.append(f"    {assignment}")
    if field_init_lines:
        lines.append("    // Initialize page fields")
        lines.extend(field_init_lines)
        lines.append("")

    if all_widgets:
        # Init each widget
        lines.append("    // Init views")
        for w in all_widgets:
            lines.extend(_gen_widget_init_lines(w, core_expr="core"))
            lines.append("")

        # Set backgrounds
        if bg_init_lines:
            lines.append("    // Set backgrounds")
            lines.extend(bg_init_lines)
            lines.append("")

        # Set shadows
        if shadow_init_lines:
            lines.append("    // Set shadows")
            lines.extend(shadow_init_lines)
            lines.append("")

        # Build hierarchy (add children)
        hierarchy_lines = []
        for w in all_widgets:
            if not w.children:
                continue
            type_info = _get_type_info(w.widget_type)
            add_func = type_info.get("add_child_func")
            if add_func:
                for child in w.children:
                    hierarchy_lines.append(
                        f"    {add_func}("
                        f"(egui_view_t *)&local->{w.name}, "
                        f"(egui_view_t *)&local->{child.name});"
                    )
        if hierarchy_lines:
            lines.append("    // Build hierarchy")
            lines.extend(hierarchy_lines)
            lines.append("")

        # Layout (for containers with layout_func)
        layout_lines = []
        for w in all_widgets:
            if not w.children:
                continue
            type_info = _get_type_info(w.widget_type)
            layout_func = type_info.get("layout_func")
            if layout_func:
                # Skip auto-layout if any child has explicit (non-zero) position
                has_explicit_pos = any(
                    c.x != 0 or c.y != 0 for c in w.children
                )
                if has_explicit_pos:
                    continue
                args_tpl = type_info.get("layout_func_args")
                if args_tpl:
                    # Expand {prop} placeholders from widget properties
                    import re as _re
                    def _repl_layout(m, _w=w):
                        key = m.group(1)
                        if key == "orientation_value":
                            ori = _w.properties.get("orientation", "vertical")
                            return "1" if ori == "horizontal" else "0"
                        return str(_w.properties.get(key, ""))
                    extra = _re.sub(r'\{(\w+)\}', _repl_layout, args_tpl)
                    layout_lines.append(
                        f"    {layout_func}((egui_view_t *)&local->{w.name}, {extra});"
                    )
                else:
                    layout_lines.append(
                        f"    {layout_func}((egui_view_t *)&local->{w.name});"
                    )
        if layout_lines:
            lines.append("    // Re-layout children")
            lines.extend(layout_lines)
            lines.append("")

        # Init animations
        if anim_init_lines:
            lines.append("    // Init animations")
            lines.extend(anim_init_lines)
            lines.append("")

        # Add root widget(s) to page
        if page.root_widget:
            root_name = page.root_widget.name
            lines.append("    // Add to page root")
            lines.append(
                f"    egui_page_base_add_view(self, (egui_view_t *)&local->{root_name});"
            )
            lines.append("")

            # If root widget has a background, apply it to self->root_view
            root_bg = page.root_widget.background
            if root_bg and root_bg.bg_type != "none":
                bg_name = f"bg_{name}_{root_name}"
                lines.append("    // Set page background")
                lines.append(
                    f"    egui_view_set_background("
                    f"(egui_view_t *)&self->root_view, "
                    f"(egui_background_t *)&{bg_name});"
                )
                lines.append("")

    lines.append("}")
    lines.append("")

    lines.append(f"static void {prefix}_on_open(egui_page_base_t *self)")
    lines.append("{")
    lines.append(f"    {struct_type} *local = ({struct_type} *)self;")
    lines.append("    EGUI_UNUSED(local);")
    lines.append("    egui_page_base_on_open(self);")
    lines.append(f"    {prefix}_layout_init(self);")
    if has_auto_start_timers:
        lines.append(f"    {helper_names['start_auto']}(self);")
    lines.append(f"    {hook_macros['on_open']}(local);")
    lines.append("}")
    lines.append("")

    lines.append(f"static void {prefix}_on_close(egui_page_base_t *self)")
    lines.append("{")
    lines.append(f"    {struct_type} *local = ({struct_type} *)self;")
    lines.append("    EGUI_UNUSED(local);")
    if has_timers:
        lines.append(f"    {helper_names['stop']}(self);")
    lines.append("    egui_page_base_on_close(self);")
    lines.append(f"    {hook_macros['on_close']}(local);")
    lines.append("}")
    lines.append("")

    lines.append(f"static void {prefix}_on_key_pressed(egui_page_base_t *self, uint16_t keycode)")
    lines.append("{")
    lines.append(f"    {struct_type} *local = ({struct_type} *)self;")
    lines.append("    EGUI_UNUSED(local);")
    lines.append("    EGUI_UNUSED(keycode);")
    lines.append(f"    {hook_macros['on_key']}(local, keycode);")
    lines.append("}")
    lines.append("")

    lines.append(f"static const egui_page_base_api_t EGUI_VIEW_API_TABLE_NAME({struct_type}) = {{")
    lines.append(f"    .on_open = {prefix}_on_open,")
    lines.append(f"    .on_close = {prefix}_on_close,")
    lines.append(f"    .on_key_pressed = {prefix}_on_key_pressed,")
    lines.append("};")
    lines.append("")

    lines.append(f"void {prefix}_init(egui_page_base_t *self, egui_core_t *core)")
    lines.append("{")
    lines.append(f"    {struct_type} *local = ({struct_type} *)self;")
    lines.append("    EGUI_UNUSED(local);")
    lines.append("    egui_page_base_init(self, core);")
    lines.append(f"    self->api = &EGUI_VIEW_API_TABLE_NAME({struct_type});")
    if has_timers:
        lines.append(f"    {helper_names['init']}(self);")
    lines.append(f'    egui_page_base_set_name(self, "{name}");')
    lines.append(f"    {hook_macros['init']}(local);")
    lines.append("}")
    lines.append("")

    return "\n".join(lines)


# ── Page User Source / Ext Header (user-owned, created once) ─────

def _render_ext_fields_definition(macro_name, body_text=""):
    body_lines = [line.rstrip() for line in str(body_text or "").splitlines()]
    while body_lines and not body_lines[0].strip():
        body_lines.pop(0)
    while body_lines and not body_lines[-1].strip():
        body_lines.pop()
    body_lines = [line for line in body_lines if line.strip()]

    lines = [f"#ifndef {macro_name}"]
    if not body_lines:
        lines.append(f"#define {macro_name}")
    elif len(body_lines) == 1:
        lines.append(f"#define {macro_name} {body_lines[0].lstrip()}")
    else:
        lines.append(f"#define {macro_name} \\")
        for line in body_lines[:-1]:
            lines.append(f"{line} \\")
        lines.append(body_lines[-1])
    lines.append("#endif")
    return lines


def generate_page_ext_header(page, project, *, include_text="", declaration_text="", fields_text=""):
    name = page.name
    guard = _page_ext_guard(name)
    hook_macros = _page_hook_macro_names(name)
    hook_funcs = _page_user_hook_names(name)

    lines = []
    lines.append(f"#ifndef {guard}")
    lines.append(f"#define {guard}")
    lines.append("")
    lines.append(f"// User extension header for {name}")
    lines.append("// Add private includes, declarations, struct fields, or hook overrides here.")
    lines.append("")

    include_lines = str(include_text or "").rstrip("\n")
    if include_lines:
        lines.extend(include_lines.splitlines())
        lines.append("")

    lines.append("#ifdef __cplusplus")
    lines.append('extern "C" {')
    lines.append("#endif")
    lines.append("")

    declaration_lines = str(declaration_text or "").rstrip("\n")
    if declaration_lines:
        lines.extend(declaration_lines.splitlines())
        lines.append("")

    lines.append("#ifdef __cplusplus")
    lines.append("}")
    lines.append("#endif")
    lines.append("")
    lines.extend(_render_ext_fields_definition(hook_macros["fields"], fields_text))
    lines.append("")
    lines.append("/* Optional hook overrides:")
    lines.append(f"#define {hook_macros['init']}(_page) {hook_funcs['init']}(_page)")
    lines.append(f"#define {hook_macros['on_open']}(_page) {hook_funcs['on_open']}(_page)")
    lines.append(f"#define {hook_macros['on_close']}(_page) {hook_funcs['on_close']}(_page)")
    lines.append(
        f"#define {hook_macros['on_key']}(_page, _keycode) {hook_funcs['on_key']}(_page, _keycode)"
    )
    lines.append("*/")
    lines.append("")
    lines.append(f"#endif /* {guard} */")
    lines.append("")
    return "\n".join(lines)


def _render_page_user_hook_function(signature_line, struct_type, body_text="", todo_comment="", unused_names=()):
    lines = [signature_line, "{"]
    lines.append(f"    {struct_type} *local = page;")
    lines.append("    EGUI_UNUSED(local);")
    for unused_name in unused_names:
        lines.append(f"    EGUI_UNUSED({unused_name});")

    body_lines = [line.rstrip() for line in str(body_text or "").splitlines()]
    while body_lines and not body_lines[0].strip():
        body_lines.pop(0)
    while body_lines and not body_lines[-1].strip():
        body_lines.pop()

    if body_lines:
        lines.extend(body_lines)
    else:
        lines.append(f"    {todo_comment}")
    lines.append("}")
    return "\n".join(lines)


def _render_page_user_source_content(page, project, *, preamble="", hook_bodies=None):
    name = page.name
    struct_type = f"egui_{name}_t"
    hook_funcs = _page_user_hook_names(name)
    generated_callbacks = collect_page_callback_stubs(page)
    hook_bodies = hook_bodies or {}

    lines = []
    lines.append(f"// {name}.c – User implementation for {name}")
    lines.append("// This file is YOUR code. The designer only creates or migrates it once.")
    lines.append(
        f"// Generated page lifecycle wrappers live in {designer_page_layout_relpath(name)}."
    )
    lines.append("")
    lines.append('#include "egui.h"')
    lines.append("#include <stdlib.h>")
    lines.append("")
    lines.append('#include "uicode.h"')
    lines.append(f'#include "{name}.h"')
    lines.append("")

    preamble_text = str(preamble or "").rstrip("\n")
    if preamble_text:
        lines.extend(preamble_text.splitlines())
        lines.append("")

    callback_preamble = preamble_text
    for callback in generated_callbacks:
        callback_name = callback.get("name", "")
        if _function_definition_exists(callback_preamble, callback_name):
            continue
        stub = render_page_callback_stub(
            page,
            callback_name,
            callback.get("signature", ""),
            kind=callback.get("kind", "view"),
        )
        if stub:
            lines.append(stub)
            lines.append("")

    lines.append(
        _render_page_user_hook_function(
            f"void {hook_funcs['init']}({struct_type} *page)",
            struct_type,
            hook_bodies.get("init", ""),
            "// TODO: Add custom init logic here.",
        )
    )
    lines.append("")
    lines.append(
        _render_page_user_hook_function(
            f"void {hook_funcs['on_open']}({struct_type} *page)",
            struct_type,
            hook_bodies.get("on_open", ""),
            "// TODO: Add page-open logic here.",
        )
    )
    lines.append("")
    lines.append(
        _render_page_user_hook_function(
            f"void {hook_funcs['on_close']}({struct_type} *page)",
            struct_type,
            hook_bodies.get("on_close", ""),
            "// TODO: Add cleanup logic here.",
        )
    )
    lines.append("")
    lines.append(
        _render_page_user_hook_function(
            f"void {hook_funcs['on_key']}({struct_type} *page, uint16_t keycode)",
            struct_type,
            hook_bodies.get("on_key_pressed", ""),
            "// TODO: Handle page key events here.",
            unused_names=("keycode",),
        )
    )
    lines.append("")
    return "\n".join(lines)


def generate_page_user_source(page, project):
    """Generate the {page_name}.c user implementation skeleton."""
    return _render_page_user_source_content(page, project)


# ── helpers ───────────────────────────────────────────────────────

def _project_uses_resources(project):
    """Return True if any widget references a generated resource (image or font)."""
    for page in project.pages:
        for w in page.get_all_widgets():
            # New structured resource properties
            if w.properties.get("image_file", ""):
                return True
            if w.properties.get("font_file", ""):
                return True
            # Legacy: check for C expression strings
            for val in w.properties.values():
                if isinstance(val, str) and val.startswith("&egui_res_"):
                    return True
    return False


# ── uicode.h ─────────────────────────────────────────────────────

def generate_uicode_header(project):
    """Generate uicode.h with page enum and exported functions."""
    lines = []
    lines.append("#ifndef _UICODE_H_")
    lines.append("#define _UICODE_H_")
    lines.append("")
    lines.append('#include "egui.h"')
    lines.append("")
    if _project_uses_resources(project):
        lines.append('#include "app_egui_resource_generate.h"')
        lines.append("")
    lines.append("/* Set up for C function definitions, even when using C++ */")
    lines.append("#ifdef __cplusplus")
    lines.append('extern "C" {')
    lines.append("#endif")
    lines.append("")

    # Page index enum
    lines.append("// Page indices")
    lines.append("enum {")
    for i, page in enumerate(project.pages):
        enum_name = f"PAGE_{page.name.upper()}"
        lines.append(f"    {enum_name} = {i},")
    lines.append(f"    PAGE_COUNT = {len(project.pages)},")
    lines.append("};")
    lines.append("")

    # Exported functions
    lines.append("void uicode_switch_page(int page_index);")
    lines.append("int uicode_start_next_page(void);")
    lines.append("int uicode_start_prev_page(void);")
    lines.append("void uicode_disp0_init(egui_core_t *core);")
    lines.append("void uicode_create_ui(void);")
    lines.append("")
    lines.append("/* Ends C function definitions when using C++ */")
    lines.append("#ifdef __cplusplus")
    lines.append("}")
    lines.append("#endif")
    lines.append("")
    lines.append("#endif /* _UICODE_H_ */")
    lines.append("")

    return "\n".join(lines)


def generate_uicode_disp0_header(project):
    """Generate a compatibility header for the new SDK display entrypoint."""
    _ = project
    lines = []
    lines.append("#ifndef _UICODE_DISP0_H_")
    lines.append("#define _UICODE_DISP0_H_")
    lines.append("")
    lines.append('#include "uicode.h"')
    lines.append("")
    lines.append("#endif /* _UICODE_DISP0_H_ */")
    lines.append("")
    return "\n".join(lines)


# ── uicode.c (EasyPage mode) ─────────────────────────────────────

def _gen_uicode_easy_page(project):
    """Generate uicode.c for EasyPage mode (union + switch page management)."""
    pages = project.pages
    has_i18n = project.string_catalog.has_strings
    lines = []
    lines.append("// ===== Auto-generated by EmbeddedGUI Designer =====")
    lines.append("")
    lines.append('#include "egui.h"')
    lines.append("#include <stdlib.h>")
    lines.append('#include "uicode.h"')
    if has_i18n:
        lines.append('#include "egui_strings.h"')
    lines.append("")

    # Include each page header
    for page in pages:
        lines.append(f'#include "{page.name}.h"')
    lines.append("")

    # Toast
    lines.append("static egui_toast_std_t toast;")
    lines.append("static egui_page_base_t *current_page = NULL;")
    lines.append("static egui_core_t *s_uicode_core = NULL;")
    lines.append("")

    # Page union
    lines.append("union page_array {")
    for page in pages:
        lines.append(f"    egui_{page.name}_t {page.name};")
    lines.append("};")
    lines.append("")
    lines.append("static union page_array g_page_array;")
    lines.append("static int current_index = 0;")
    lines.append("static char toast_str[50];")
    lines.append("")

    # Determine startup page index
    startup_index = 0
    for i, page in enumerate(pages):
        if page.name == project.startup_page:
            startup_index = i
            break

    # uicode_switch_page
    lines.append("void uicode_switch_page(int page_index)")
    lines.append("{")
    lines.append("    egui_core_t *core = egui_toast_get_core((egui_toast_t *)&toast);")
    lines.append("    if (core == NULL)")
    lines.append("    {")
    lines.append("        return;")
    lines.append("    }")
    lines.append("")
    lines.append("    current_index = page_index;")
    lines.append("")
    lines.append('    egui_api_sprintf(toast_str, "Start page %d", page_index);')
    lines.append("    egui_toast_show_info((egui_toast_t *)&toast, toast_str);")
    lines.append("")
    lines.append("    if (current_page)")
    lines.append("    {")
    lines.append("        egui_page_base_close(current_page);")
    lines.append("    }")
    lines.append("")
    lines.append("    switch (page_index)")
    lines.append("    {")
    for i, page in enumerate(pages):
        lines.append(f"    case {i}:")
        lines.append(
            f"        egui_{page.name}_init("
            f"(egui_page_base_t *)&g_page_array.{page.name}, core);"
        )
        lines.append(
            f"        current_page = "
            f"(egui_page_base_t *)&g_page_array.{page.name};"
        )
        lines.append("        break;")
    lines.append("    default:")
    lines.append("        break;")
    lines.append("    }")
    lines.append("")
    lines.append("    egui_page_base_open(current_page);")
    lines.append("}")
    lines.append("")

    # uicode_start_next_page
    lines.append("int uicode_start_next_page(void)")
    lines.append("{")
    lines.append("    int page_index = current_index + 1;")
    lines.append("    if (page_index >= PAGE_COUNT)")
    lines.append("    {")
    lines.append('        egui_toast_show_info((egui_toast_t *)&toast, "No more next page");')
    lines.append("        return -1;")
    lines.append("    }")
    lines.append("")
    lines.append("    uicode_switch_page(page_index);")
    lines.append("    return 0;")
    lines.append("}")
    lines.append("")

    # uicode_start_prev_page
    lines.append("int uicode_start_prev_page(void)")
    lines.append("{")
    lines.append("    int page_index = current_index - 1;")
    lines.append("    if (page_index < 0)")
    lines.append("    {")
    lines.append('        egui_toast_show_info((egui_toast_t *)&toast, "No more previous page");')
    lines.append("        return -1;")
    lines.append("    }")
    lines.append("")
    lines.append("    uicode_switch_page(page_index);")
    lines.append("    return 0;")
    lines.append("}")
    lines.append("")

    # Key event handler
    lines.append("void egui_port_hanlde_key_event(int key, int event)")
    lines.append("{")
    lines.append("    if (event == 0)")
    lines.append("    {")
    lines.append("        return;")
    lines.append("    }")
    lines.append("")
    lines.append("    if (current_page)")
    lines.append("    {")
    lines.append("        egui_page_base_key_pressed(current_page, key);")
    lines.append("    }")
    lines.append("}")
    lines.append("")

    # uicode_init_ui
    lines.append("static void uicode_init_ui(egui_core_t *core)")
    lines.append("{")
    lines.append("    if (core == NULL)")
    lines.append("    {")
    lines.append("        return;")
    lines.append("    }")
    lines.append("")
    lines.append("    s_uicode_core = core;")
    if has_i18n:
        lines.append("    // Initialize i18n string tables")
        lines.append("    egui_strings_init();")
        lines.append("")
    lines.append("    // Init toast")
    lines.append("    egui_toast_std_init((egui_toast_t *)&toast, core);")
    lines.append("    egui_toast_set_as_default((egui_toast_t *)&toast);")
    lines.append("")
    lines.append("    // Start with startup page")
    lines.append("    current_page = NULL;")
    lines.append(f"    current_index = {startup_index};")
    lines.append(f"    uicode_switch_page({startup_index});")
    lines.append("}")
    lines.append("")

    lines.append("void uicode_disp0_init(egui_core_t *core)")
    lines.append("{")
    lines.append("    uicode_init_ui(core);")
    lines.append("}")
    lines.append("")

    # uicode_create_ui
    lines.append("void uicode_create_ui(void)")
    lines.append("{")
    lines.append("    if (s_uicode_core != NULL)")
    lines.append("    {")
    lines.append("        uicode_init_ui(s_uicode_core);")
    lines.append("    }")
    lines.append("}")
    lines.append("")

    # Recording test actions — auto-cycle through all pages
    if len(pages) > 1:
        lines.append("#if EGUI_CONFIG_RECORDING_TEST")
        lines.append(
            "// Recording actions: visit every page for visual verification"
        )
        lines.append(
            "bool egui_port_get_recording_action"
            "(int action_index, egui_sim_action_t *p_action)"
        )
        lines.append("{")
        # Guard: this callback is called every frame; only switch page on
        # the first call for each action_index to avoid repeated side effects.
        lines.append("    static int last_action = -1;")
        lines.append("    int first_call = (action_index != last_action);")
        lines.append("    last_action = action_index;")
        lines.append("")
        lines.append("    switch (action_index)")
        lines.append("    {")
        case_idx = 0
        lines.append(f"    case {case_idx}:")
        lines.append("        // Capture startup page")
        lines.append("        if (first_call)")
        lines.append("            recording_request_snapshot();")
        lines.append("        EGUI_SIM_SET_WAIT(p_action, 200);")
        lines.append("        return true;")
        for i, page in enumerate(pages):
            if i == startup_index:
                continue  # startup page is already shown
            case_idx += 1
            lines.append(f"    case {case_idx}:")
            lines.append(
                f"        // Switch to {page.name} (PAGE_{page.name.upper()})"
            )
            lines.append("        if (first_call)")
            lines.append("        {")
            lines.append(f"            uicode_switch_page({i});")
            lines.append("            recording_request_snapshot();")
            lines.append("        }")
            lines.append("        EGUI_SIM_SET_WAIT(p_action, 200);")
            lines.append("        return true;")
        # Return to startup page at the end
        case_idx += 1
        lines.append(f"    case {case_idx}:")
        lines.append("        // Return to startup page")
        lines.append("        if (first_call)")
        lines.append("        {")
        lines.append(
            f"            uicode_switch_page({startup_index});"
        )
        lines.append("            recording_request_snapshot();")
        lines.append("        }")
        lines.append("        EGUI_SIM_SET_WAIT(p_action, 200);")
        lines.append("        return true;")
        lines.append("    default:")
        lines.append("        return false;")
        lines.append("    }")
        lines.append("}")
        lines.append("#endif")
        lines.append("")

    return "\n".join(lines)


# ── uicode.c (Activity mode) ─────────────────────────────────────

def _gen_uicode_activity(project):
    """Generate uicode.c for Activity mode.

    Each page struct is wrapped inside an activity adapter.
    The activity lifecycle delegates to page_base lifecycle.
    """
    pages = project.pages
    has_i18n = project.string_catalog.has_strings
    lines = []
    lines.append("// ===== Auto-generated by EmbeddedGUI Designer =====")
    lines.append("// Activity mode — pages wrapped in activity adapters")
    lines.append("")
    lines.append('#include "egui.h"')
    lines.append("#include <stdlib.h>")
    lines.append('#include "uicode.h"')
    if has_i18n:
        lines.append('#include "egui_strings.h"')
    lines.append("")

    for page in pages:
        lines.append(f'#include "{page.name}.h"')
    lines.append("")

    # Define activity adapter for each page
    lines.append("// ── Activity adapters wrapping page_base pages ──")
    lines.append("")
    for page in pages:
        adapter = f"{page.name}_activity"
        page_type = f"egui_{page.name}_t"
        lines.append(f"typedef struct {{")
        lines.append(f"    egui_activity_t base;")
        lines.append(f"    {page_type} page_data;")
        lines.append(f"}} {adapter}_t;")
        lines.append("")

        # on_create
        lines.append(f"static void {adapter}_on_create(egui_activity_t *self)")
        lines.append("{")
        lines.append(f"    egui_activity_on_create(self);")
        lines.append(f"    {adapter}_t *w = ({adapter}_t *)self;")
        lines.append(f"    egui_{page.name}_init((egui_page_base_t *)&w->page_data, egui_activity_get_core(self));")
        lines.append(f"    egui_page_base_open((egui_page_base_t *)&w->page_data);")
        lines.append("}")
        lines.append("")

        # on_destroy
        lines.append(f"static void {adapter}_on_destroy(egui_activity_t *self)")
        lines.append("{")
        lines.append(f"    {adapter}_t *w = ({adapter}_t *)self;")
        lines.append(f"    egui_page_base_close((egui_page_base_t *)&w->page_data);")
        lines.append(f"    egui_activity_on_destroy(self);")
        lines.append("}")
        lines.append("")

        # vtable
        lines.append(f"static const egui_activity_api_t {adapter}_api = {{")
        lines.append(f"    .on_create = {adapter}_on_create,")
        lines.append(f"    .on_destroy = {adapter}_on_destroy,")
        lines.append(f"    .on_start = egui_activity_on_start,")
        lines.append(f"    .on_stop = egui_activity_on_stop,")
        lines.append(f"    .on_resume = egui_activity_on_resume,")
        lines.append(f"    .on_pause = egui_activity_on_pause,")
        lines.append("};")
        lines.append("")

        # init
        lines.append(f"static void {adapter}_init(egui_activity_t *self, egui_core_t *core)")
        lines.append("{")
        lines.append(f"    egui_activity_init(self, core);")
        lines.append(f"    self->api = &{adapter}_api;")
        lines.append("}")
        lines.append("")

    # Union
    lines.append("// ── Page/Activity union ──")
    lines.append("union page_array {")
    for page in pages:
        lines.append(f"    {page.name}_activity_t {page.name};")
    lines.append("};")
    lines.append("")
    lines.append("static union page_array g_page_array;")
    lines.append("static int current_index = 0;")
    lines.append("static egui_toast_std_t toast;")
    lines.append("static egui_core_t *s_uicode_core = NULL;")
    lines.append("static char toast_str[50];")
    lines.append("")

    startup_index = 0
    for i, page in enumerate(pages):
        if page.name == project.startup_page:
            startup_index = i
            break

    # uicode_switch_page
    lines.append("void uicode_switch_page(int page_index)")
    lines.append("{")
    lines.append("    egui_activity_t *current_activity = NULL;")
    lines.append("    if (s_uicode_core == NULL)")
    lines.append("    {")
    lines.append("        return;")
    lines.append("    }")
    lines.append("")
    lines.append("    current_activity = egui_core_activity_get_current(s_uicode_core);")
    lines.append("    current_index = page_index;")
    lines.append('    egui_api_sprintf(toast_str, "Start page %d", page_index);')
    lines.append("    if (current_activity != NULL)")
    lines.append("    {")
    lines.append("        egui_activity_show_toast_info(current_activity, toast_str);")
    lines.append("        egui_activity_finish(current_activity);")
    lines.append("    }")
    lines.append("    else")
    lines.append("    {")
    lines.append("        egui_toast_show_info((egui_toast_t *)&toast, toast_str);")
    lines.append("    }")
    lines.append("")
    lines.append("    switch (page_index)")
    lines.append("    {")
    for i, page in enumerate(pages):
        adapter = f"{page.name}_activity"
        lines.append(f"    case {i}:")
        lines.append(
            f"        {adapter}_init("
            f"(egui_activity_t *)&g_page_array.{page.name}, s_uicode_core);"
        )
        lines.append(
            f"        egui_activity_start("
            f"(egui_activity_t *)&g_page_array.{page.name}, NULL);"
        )
        lines.append("        break;")
    lines.append("    default:")
    lines.append("        break;")
    lines.append("    }")
    lines.append("}")
    lines.append("")

    # next / prev
    lines.append("int uicode_start_next_page(void)")
    lines.append("{")
    lines.append("    int page_index = current_index + 1;")
    lines.append("    if (page_index >= PAGE_COUNT)")
    lines.append("    {")
    lines.append("        egui_activity_t *current_activity = egui_core_activity_get_current(s_uicode_core);")
    lines.append("        if (current_activity != NULL)")
    lines.append("        {")
    lines.append('            egui_activity_show_toast_info(current_activity, "No more next page");')
    lines.append("        }")
    lines.append("        else")
    lines.append("        {")
    lines.append('            egui_toast_show_info((egui_toast_t *)&toast, "No more next page");')
    lines.append("        }")
    lines.append("        return -1;")
    lines.append("    }")
    lines.append("    uicode_switch_page(page_index);")
    lines.append("    return 0;")
    lines.append("}")
    lines.append("")
    lines.append("int uicode_start_prev_page(void)")
    lines.append("{")
    lines.append("    int page_index = current_index - 1;")
    lines.append("    if (page_index < 0)")
    lines.append("    {")
    lines.append("        egui_activity_t *current_activity = egui_core_activity_get_current(s_uicode_core);")
    lines.append("        if (current_activity != NULL)")
    lines.append("        {")
    lines.append('            egui_activity_show_toast_info(current_activity, "No more previous page");')
    lines.append("        }")
    lines.append("        else")
    lines.append("        {")
    lines.append('            egui_toast_show_info((egui_toast_t *)&toast, "No more previous page");')
    lines.append("        }")
    lines.append("        return -1;")
    lines.append("    }")
    lines.append("    uicode_switch_page(page_index);")
    lines.append("    return 0;")
    lines.append("}")
    lines.append("")

    # uicode_init_ui / create_ui
    lines.append("static void uicode_init_ui(egui_core_t *core)")
    lines.append("{")
    lines.append("    if (core == NULL)")
    lines.append("    {")
    lines.append("        return;")
    lines.append("    }")
    lines.append("")
    lines.append("    s_uicode_core = core;")
    if has_i18n:
        lines.append("    // Initialize i18n string tables")
        lines.append("    egui_strings_init();")
        lines.append("")
    lines.append("    egui_toast_std_init((egui_toast_t *)&toast, core);")
    lines.append("    egui_toast_set_as_default((egui_toast_t *)&toast);")
    lines.append("")
    lines.append(f"    current_index = {startup_index};")
    lines.append(f"    uicode_switch_page({startup_index});")
    lines.append("}")
    lines.append("")
    lines.append("void uicode_disp0_init(egui_core_t *core)")
    lines.append("{")
    lines.append("    uicode_init_ui(core);")
    lines.append("}")
    lines.append("")
    lines.append("void uicode_create_ui(void)")
    lines.append("{")
    lines.append("    if (s_uicode_core != NULL)")
    lines.append("    {")
    lines.append("        uicode_init_ui(s_uicode_core);")
    lines.append("    }")
    lines.append("}")
    lines.append("")

    return "\n".join(lines)


def generate_uicode_source(project):
    """Generate uicode.c based on project page_mode."""
    if project.page_mode == "activity":
        return _gen_uicode_activity(project)
    return _gen_uicode_easy_page(project)


# ── app_egui_config.h ─────────────────────────────────────────────

def generate_app_config_designer(project):
    """Generate app_egui_config_designer.h with screen dimensions."""
    w = project.screen_width
    h = project.screen_height

    # Determine max circle radius needed from circular progress bars
    max_radius = 20  # default
    for page in project.pages:
        for widget in page.get_all_widgets():
            if widget.widget_type == "circular_progress_bar":
                r = min(widget.width, widget.height) // 2
                if r > max_radius:
                    max_radius = r

    # (not baked into config — keeps config portable)
    return make_app_config_designer_h_content(
        project.app_name,
        w,
        h,
        circle_radius=max_radius,
    )


# ── Public API ────────────────────────────────────────────────────

# File categories for the generation system:
#   GENERATED_ALWAYS  – fully generated, overwritten every time
#   GENERATED_PRESERVED – legacy category kept for compatibility
#   USER_OWNED – created once as skeleton, then owned by the user

GENERATED_ALWAYS = "generated_always"
GENERATED_PRESERVED = "generated_preserved"
USER_OWNED = "user_owned"

# Active generation flow now uses GENERATED_ALWAYS and USER_OWNED.
# GENERATED_PRESERVED remains as a compatibility constant for older callers/tests.


@dataclass(frozen=True)
class PreparedGeneratedProjectFiles:
    """Prepared project codegen outputs for save/export/preview flows."""

    files: dict[str, str]
    all_generated_files: dict[str, tuple[str, str]]


def generate_all_files(project):
    """Generate all C files for the project.

    Returns:
        dict[str, tuple[str, str]]: filename -> (content, category)
            category is one of GENERATED_ALWAYS or USER_OWNED
    """
    files = {}

    for page in project.pages:
        files[designer_page_header_relpath(page.name)] = (
            generate_page_header(page, project), GENERATED_ALWAYS
        )
        files[designer_page_layout_relpath(page.name)] = (
            generate_page_layout_source(page, project), GENERATED_ALWAYS
        )
        files[page_user_source_relpath(page.name)] = (
            generate_page_user_source(page, project), USER_OWNED
        )
        files[page_ext_header_relpath(page.name)] = (
            generate_page_ext_header(page, project), USER_OWNED
        )

    files[UICODE_HEADER_RELPATH] = (generate_uicode_header(project), GENERATED_ALWAYS)
    files[UICODE_DISP_HEADER_RELPATH] = (generate_uicode_disp0_header(project), GENERATED_ALWAYS)
    files[UICODE_SOURCE_RELPATH] = (generate_uicode_source(project), GENERATED_ALWAYS)
    files[BUILD_DESIGNER_RELPATH] = (
        make_app_build_designer_mk_content(project.app_name),
        GENERATED_ALWAYS,
    )
    files[APP_CONFIG_DESIGNER_RELPATH] = (
        generate_app_config_designer(project),
        GENERATED_ALWAYS,
    )

    # i18n string resources
    if project.string_catalog.has_strings:
        from .string_resource_generator import generate_string_files
        string_files = generate_string_files(project.string_catalog)
        files.update(string_files)

    return files


def _generate_all_files_preserved_from_manifest(project, output_dir, all_files, *, backup=True):
    """Filter a full generated manifest to the files that should be written now."""
    import os
    from .user_code_preserver import (
        read_existing_file,
        backup_file,
        cleanup_old_backups,
        embed_source_hash,
        should_skip_generation,
        compute_source_hash,
    )

    result = {}
    pages_by_name = {page.name: page for page in project.pages}

    backup_root = project_config_backup_dir(output_dir)

    for filename, (content, category) in all_files.items():
        filepath = os.path.join(output_dir, filename)
        source_hash = compute_source_hash(content)

        if category == USER_OWNED:
            existing = read_existing_file(filepath)
            if existing is not None:
                page_name = _page_name_from_user_owned_filename(filename)
                page = pages_by_name.get(page_name)
                if page is not None and _is_legacy_designer_user_source(existing):
                    raise ValueError(
                        _unsupported_legacy_page_source_message(filename, page_name)
                    )
                continue

            if filename.endswith("_ext.h"):
                page_name = filename[:-len("_ext.h")]
                legacy_header = read_existing_file(os.path.join(output_dir, f"{page_name}.h"))
                if _legacy_page_header_has_user_code(legacy_header):
                    raise ValueError(
                        _unsupported_legacy_page_header_message(page_name)
                    )
            result[filename] = embed_source_hash(content, source_hash)
            continue

        if should_skip_generation(filepath, source_hash):
            continue
        content_with_hash = embed_source_hash(content, source_hash)
        if backup and os.path.isfile(filepath):
            backup_file(filepath, backup_root)
        result[filename] = content_with_hash

    # Cleanup old backups (keep last 20)
    if backup:
        cleanup_old_backups(backup_root, keep=20)

    return result


def prepare_generated_project_files(project, output_dir, backup=True):
    """Return preserved write outputs together with the full generated manifest."""
    registry_errors = _collect_project_widget_registry_errors(project)
    if registry_errors:
        summary = "\n".join(f"- {line}" for line in registry_errors[:10])
        if len(registry_errors) > 10:
            summary += f"\n- ... and {len(registry_errors) - 10} more issue(s)"
        raise ValueError(f"Code generation blocked by unresolved widget types:\n{summary}")

    all_files = generate_all_files(project)
    files = _generate_all_files_preserved_from_manifest(
        project,
        output_dir,
        all_files,
        backup=backup,
    )
    return PreparedGeneratedProjectFiles(
        files=files,
        all_generated_files=all_files,
    )


def materialize_project_codegen(
    project,
    output_dir,
    *,
    backup=True,
    extra_files=None,
    newline=None,
    backup_existing=False,
):
    """Prepare and materialize project codegen outputs for save/export flows."""
    prepared = prepare_generated_project_files(project, output_dir, backup=backup)
    files = dict(prepared.files)
    files.update(extra_files or {})
    materialize_generated_project_files(
        output_dir,
        files,
        prepared.all_generated_files,
        newline=newline,
        backup_existing=backup_existing,
        remove_stale_strings=not project.string_catalog.has_strings,
    )
    return PreparedGeneratedProjectFiles(
        files=files,
        all_generated_files=prepared.all_generated_files,
    )


def generate_all_files_preserved(project, output_dir, backup=True):
    """Generate all C files with proper ownership semantics.

    Generated files are always rewritten when the generated hash changes.
    User-owned files are only created when missing. Unsupported legacy page
    source/header layouts are rejected with an actionable error.
    """
    return prepare_generated_project_files(project, output_dir, backup=backup).files


def _page_name_from_user_owned_filename(filename):
    if filename.endswith("_ext.h"):
        return filename[:-len("_ext.h")]
    if filename.endswith(".c"):
        return filename[:-2]
    return ""


def _unsupported_legacy_page_source_message(filename, page_name):
    page_label = page_name or filename
    return (
        f"Unsupported legacy page source detected: {filename} still uses the old Designer-generated layout for "
        f"'{page_label}'. Automatic migration is no longer supported. Back up the file, then run Clean All && "
        "Reconstruct or rewrite the page source against the split hooks manually."
    )


def _unsupported_legacy_page_header_message(page_name):
    filename = f"{page_name}.h" if page_name else "*.h"
    return (
        f"Unsupported legacy page header detected: {filename} still contains legacy USER CODE blocks. Automatic "
        "migration into *_ext.h is no longer supported. Back up the file and move any needed code into the new "
        "extension header manually, or run Clean All && Reconstruct."
    )


def _looks_like_designer_user_source(content):
    return (
        "Layout/widget init is in" in content
        and "_on_open(egui_page_base_t *self)" in content
    )


def _is_legacy_designer_user_source(content):
    return (
        _looks_like_designer_user_source(content)
        or (
            "Layout/widget init is in" in content
            and "USER CODE BEGIN" in content
        )
    )


def _legacy_page_header_has_user_code(existing_content):
    from .user_code_preserver import extract_user_code

    blocks = extract_user_code(existing_content or "")
    return any(str(blocks.get(tag, "") or "").strip() for tag in ("includes", "declarations", "user_fields"))


# ── Legacy single-file generator (backward compatibility) ────────

def generate_uicode(project):
    """Generate uicode.c content.

    For multi-page projects (MFC mode), returns the uicode.c only.
    Full project generation should use generate_all_files() instead.
    """
    if project.pages:
        return generate_uicode_source(project)

    # Fallback for empty projects
    return (
        '#include "egui.h"\n'
        '#include "uicode.h"\n'
        "\n"
        "static void uicode_init_ui(egui_core_t *core) { EGUI_UNUSED(core); }\n"
        "void uicode_disp0_init(egui_core_t *core) { uicode_init_ui(core); }\n"
        "void uicode_create_ui(void) {}\n"
    )
