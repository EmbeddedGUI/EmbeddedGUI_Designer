"""Scaffold utilities for creating split user/designer project files.

These helpers generate and migrate ``build.mk`` / ``app_egui_config.h`` wrapper
files plus their Designer-managed companions (``build_designer.mk`` and
``app_egui_config_designer.h``). They are Qt-free so both the GUI and CLI
helpers can share the same behavior.
"""

from __future__ import annotations

import json
import os
import re


BUILD_DESIGNER_INCLUDE_LINE = "include $(EGUI_APP_PATH)/build_designer.mk"
APP_CONFIG_DESIGNER_INCLUDE_LINE = '#include "app_egui_config_designer.h"'

APP_CONFIG_WRAPPER_GUARD = "_APP_EGUI_CONFIG_H_"
APP_CONFIG_DESIGNER_GUARD = "_APP_EGUI_CONFIG_DESIGNER_H_"

_BUILD_DESIGNER_LINES = (
    "EGUI_CODE_SRC\t\t+= $(EGUI_APP_PATH)",
    "EGUI_CODE_SRC\t\t+= $(EGUI_APP_PATH)/resource",
    "EGUI_CODE_SRC\t\t+= $(EGUI_APP_PATH)/resource/img",
    "EGUI_CODE_SRC\t\t+= $(EGUI_APP_PATH)/resource/font",
    "",
    "EGUI_CODE_INCLUDE\t+= $(EGUI_APP_PATH)",
    "EGUI_CODE_INCLUDE\t+= $(EGUI_APP_PATH)/resource",
    "EGUI_CODE_INCLUDE\t+= $(EGUI_APP_PATH)/resource/img",
    "EGUI_CODE_INCLUDE\t+= $(EGUI_APP_PATH)/resource/font",
)

_CPP_WRAPPER_LINES = {
    "/* Set up for C function definitions, even when using C++ */",
    "/* Ends C function definitions when using C++ */",
    "#ifdef __cplusplus",
    'extern "C" {',
    "}",
}


def _normalize_make_line(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip())


def _normalize_macro_value(value: str) -> str:
    return re.sub(r"\s+", "", str(value or ""))


def _compact_preserved_lines(lines):
    compacted = []
    pending_blank = False
    for raw_line in lines:
        line = raw_line.rstrip()
        if not line:
            pending_blank = bool(compacted)
            continue
        if pending_blank:
            compacted.append("")
            pending_blank = False
        compacted.append(line)
    while compacted and not compacted[-1]:
        compacted.pop()
    return compacted


def _designer_build_line_keys():
    return {_normalize_make_line(line) for line in _BUILD_DESIGNER_LINES if line.strip()}


def _designer_config_equivalent_values(screen_width, screen_height, color_depth, circle_radius):
    return {
        "EGUI_CONFIG_SCEEN_WIDTH": {
            _normalize_macro_value(screen_width),
        },
        "EGUI_CONFIG_SCEEN_HEIGHT": {
            _normalize_macro_value(screen_height),
        },
        "EGUI_CONFIG_PFB_WIDTH": {
            _normalize_macro_value(screen_width // 8),
            _normalize_macro_value(f"({screen_width} / 8)"),
            _normalize_macro_value(f"({screen_width}/8)"),
            _normalize_macro_value("(EGUI_CONFIG_SCEEN_WIDTH / 8)"),
            _normalize_macro_value("(EGUI_CONFIG_SCEEN_WIDTH/8)"),
        },
        "EGUI_CONFIG_PFB_HEIGHT": {
            _normalize_macro_value(screen_height // 8),
            _normalize_macro_value(f"({screen_height} / 8)"),
            _normalize_macro_value(f"({screen_height}/8)"),
            _normalize_macro_value("(EGUI_CONFIG_SCEEN_HEIGHT / 8)"),
            _normalize_macro_value("(EGUI_CONFIG_SCEEN_HEIGHT/8)"),
        },
        "EGUI_CONFIG_COLOR_DEPTH": {
            _normalize_macro_value(color_depth),
        },
        "EGUI_CONFIG_FUNCTION_SUPPORT_MASK": {
            _normalize_macro_value("1"),
        },
        "EGUI_CONFIG_CIRCLE_SUPPORT_RADIUS_BASIC_RANGE": {
            _normalize_macro_value(circle_radius),
        },
    }


def _split_local_include_target(content: str, include_name: str) -> str:
    match = re.search(
        rf'^\s*#\s*include\s+"(?P<path>[^"]*{re.escape(include_name)})"\s*$',
        content,
        re.MULTILINE,
    )
    return match.group("path") if match else ""


def parse_define_int(content: str, macro_name: str, default=None):
    """Parse a decimal integer from a ``#define`` line."""
    match = re.search(
        rf"^\s*#\s*define\s+{re.escape(macro_name)}\s+(.+)$",
        content,
        re.MULTILINE,
    )
    if not match:
        return default
    value = match.group(1).split("//", 1)[0].strip()
    number_match = re.search(r"\d+", value)
    if not number_match:
        return default
    return int(number_match.group(0))


def read_app_config_dimensions(config_path: str, default_width=240, default_height=320):
    """Read screen dimensions from a wrapper config and its designer include."""
    width = None
    height = None

    def _consume(path):
        nonlocal width, height
        if not path or not os.path.isfile(path):
            return ""
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except OSError:
            return ""
        if width is None:
            width = parse_define_int(content, "EGUI_CONFIG_SCEEN_WIDTH", None)
        if height is None:
            height = parse_define_int(content, "EGUI_CONFIG_SCEEN_HEIGHT", None)
        return content

    wrapper_content = _consume(config_path)
    include_target = _split_local_include_target(wrapper_content, "app_egui_config_designer.h")
    if include_target:
        designer_path = os.path.normpath(os.path.join(os.path.dirname(config_path), include_target))
        _consume(designer_path)

    return (
        width if width is not None else default_width,
        height if height is not None else default_height,
    )


def build_mk_includes_designer(content: str) -> bool:
    """Return True when ``build.mk`` already includes ``build_designer.mk``."""
    return _normalize_make_line(BUILD_DESIGNER_INCLUDE_LINE) in {
        _normalize_make_line(line) for line in content.splitlines()
    }


def app_config_includes_designer(content: str) -> bool:
    """Return True when ``app_egui_config.h`` already includes the designer header."""
    return bool(_split_local_include_target(content, "app_egui_config_designer.h"))


def make_app_build_designer_mk_content(app_name):
    """Return Designer-managed ``build_designer.mk`` content."""
    lines = [
        f"# Designer-managed build inputs for {app_name}",
        "",
        *_BUILD_DESIGNER_LINES,
        "",
    ]
    return "\n".join(lines)


def make_app_build_mk_content(app_name, preserved_lines=None):
    """Return the user-owned ``build.mk`` wrapper content."""
    lines = [
        f"# User build overrides for {app_name}",
        "",
        BUILD_DESIGNER_INCLUDE_LINE,
    ]
    preserved = _compact_preserved_lines(preserved_lines or [])
    if preserved:
        lines.extend(["", *preserved])
    lines.append("")
    return "\n".join(lines)


def migrate_app_build_mk_content(existing_content, app_name):
    """Convert a legacy ``build.mk`` into the split wrapper format."""
    preserved = []
    designer_keys = _designer_build_line_keys()

    for raw_line in existing_content.splitlines():
        stripped = raw_line.strip()
        normalized = _normalize_make_line(raw_line)
        if not stripped:
            preserved.append("")
            continue
        if normalized == _normalize_make_line(BUILD_DESIGNER_INCLUDE_LINE):
            continue
        if normalized in designer_keys:
            continue
        if re.match(r"^#\s*(Build configuration|Designer-managed build inputs)\b", stripped):
            continue
        preserved.append(raw_line.rstrip())

    return make_app_build_mk_content(app_name, preserved)


def make_app_config_designer_h_content(
    app_name,
    screen_width=240,
    screen_height=320,
    *,
    color_depth=16,
    circle_radius=None,
    extra_macros=None,
):
    """Return Designer-managed ``app_egui_config_designer.h`` content."""
    if circle_radius is None:
        circle_radius = 20

    lines = [
        f"#ifndef {APP_CONFIG_DESIGNER_GUARD}",
        f"#define {APP_CONFIG_DESIGNER_GUARD}",
        "",
        f"/* Designer-managed defaults for {app_name} */",
        "",
        "#ifndef EGUI_CONFIG_SCEEN_WIDTH",
        f"#define EGUI_CONFIG_SCEEN_WIDTH  {screen_width}",
        "#endif",
        "",
        "#ifndef EGUI_CONFIG_SCEEN_HEIGHT",
        f"#define EGUI_CONFIG_SCEEN_HEIGHT {screen_height}",
        "#endif",
        "",
        "#ifndef EGUI_CONFIG_PFB_WIDTH",
        "#define EGUI_CONFIG_PFB_WIDTH  (EGUI_CONFIG_SCEEN_WIDTH / 8)",
        "#endif",
        "",
        "#ifndef EGUI_CONFIG_PFB_HEIGHT",
        "#define EGUI_CONFIG_PFB_HEIGHT (EGUI_CONFIG_SCEEN_HEIGHT / 8)",
        "#endif",
        "",
        "#ifndef EGUI_CONFIG_COLOR_DEPTH",
        f"#define EGUI_CONFIG_COLOR_DEPTH {color_depth}",
        "#endif",
        "",
        "#ifndef EGUI_CONFIG_FUNCTION_SUPPORT_MASK",
        "#define EGUI_CONFIG_FUNCTION_SUPPORT_MASK 1",
        "#endif",
        "",
        "#ifndef EGUI_CONFIG_CIRCLE_SUPPORT_RADIUS_BASIC_RANGE",
        f"#define EGUI_CONFIG_CIRCLE_SUPPORT_RADIUS_BASIC_RANGE {circle_radius}",
        "#endif",
    ]

    for macro_name, macro_value in extra_macros or []:
        lines.extend(
            [
                "",
                f"#ifndef {macro_name}",
                f"#define {macro_name} {macro_value}",
                "#endif",
            ]
        )

    lines.extend(
        [
            "",
            f"#endif /* {APP_CONFIG_DESIGNER_GUARD} */",
            "",
        ]
    )
    return "\n".join(lines)


def make_app_config_h_content(app_name, preserved_lines=None):
    """Return the user-owned ``app_egui_config.h`` wrapper content."""
    lines = [
        f"#ifndef {APP_CONFIG_WRAPPER_GUARD}",
        f"#define {APP_CONFIG_WRAPPER_GUARD}",
        "",
    ]
    preserved = _compact_preserved_lines(preserved_lines or [])
    if preserved:
        lines.extend([*preserved, ""])
    lines.extend(
        [
            "/* Define user overrides above the Designer include. */",
            APP_CONFIG_DESIGNER_INCLUDE_LINE,
            "",
            f"#endif /* {APP_CONFIG_WRAPPER_GUARD} */",
            "",
        ]
    )
    return "\n".join(lines)


def migrate_app_config_h_content(
    existing_content,
    app_name,
    screen_width=240,
    screen_height=320,
    *,
    color_depth=16,
    circle_radius=None,
):
    """Convert a legacy ``app_egui_config.h`` into the split wrapper format."""
    if circle_radius is None:
        circle_radius = 20

    equivalent_values = _designer_config_equivalent_values(
        screen_width,
        screen_height,
        color_depth,
        circle_radius,
    )
    preserved = []
    conditional_depth = 0

    for raw_line in existing_content.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            preserved.append("")
            continue
        if stripped in _CPP_WRAPPER_LINES:
            continue
        if re.match(r"^\s*#\s*(if|ifdef|ifndef)\b", raw_line):
            if stripped not in {
                f"#ifndef {APP_CONFIG_WRAPPER_GUARD}",
                f"#ifndef {APP_CONFIG_DESIGNER_GUARD}",
            }:
                conditional_depth += 1
        if stripped in {
            f"#ifndef {APP_CONFIG_WRAPPER_GUARD}",
            f"#define {APP_CONFIG_WRAPPER_GUARD}",
            f"#ifndef {APP_CONFIG_DESIGNER_GUARD}",
            f"#define {APP_CONFIG_DESIGNER_GUARD}",
            f"#endif /* {APP_CONFIG_WRAPPER_GUARD} */",
            f"#endif /* {APP_CONFIG_DESIGNER_GUARD} */",
            APP_CONFIG_DESIGNER_INCLUDE_LINE,
        }:
            continue
        if stripped == "#endif" and conditional_depth <= 0:
            continue
        if re.match(r"^/\*\s*(Configuration|Designer-managed defaults)\s+for\b", stripped):
            continue
        define_match = re.match(r"^\s*#\s*define\s+([A-Za-z0-9_]+)\s+(.+?)\s*$", raw_line)
        if define_match:
            macro_name = define_match.group(1)
            macro_value = define_match.group(2).split("//", 1)[0].strip()
            if macro_name in equivalent_values and _normalize_macro_value(macro_value) in equivalent_values[macro_name]:
                continue
        if stripped == "#endif" and conditional_depth > 0:
            conditional_depth -= 1
        preserved.append(raw_line.rstrip())

    return make_app_config_h_content(app_name, preserved)


def make_empty_resource_config_content():
    """Return the default user-overlay resource config content."""
    return json.dumps({"img": [], "font": []}, indent=4, ensure_ascii=False) + "\n"
