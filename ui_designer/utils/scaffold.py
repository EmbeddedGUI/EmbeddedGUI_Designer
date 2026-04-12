"""Scaffold utilities for creating split user/designer project files.

These helpers generate and migrate ``build.mk`` / ``app_egui_config.h`` wrapper
files plus their Designer-managed companions under ``.designer/``. They are
Qt-free so both the GUI and CLI helpers can share the same behavior.
"""

from __future__ import annotations

import json
import os
import re
import shutil

from ..model.workspace import sdk_example_app_dir
from .resource_config_overlay import (
    APP_RESOURCE_CONFIG_DESIGNER_FILENAME,
    APP_RESOURCE_CONFIG_FILENAME,
    DESIGNER_RESOURCE_DIRNAME,
    designer_resource_config_path,
    designer_resource_dir,
    ensure_resource_config_file,
    is_designer_resource_path,
    make_empty_resource_config_content,
    user_resource_config_path,
)

DESIGNER_PROJECT_DIRNAME = ".designer"
EGUIPROJECT_DIRNAME = ".eguiproject"
LAYOUT_DIR_RELPATH = f"{EGUIPROJECT_DIRNAME}/layout"
RESOURCE_DIR_RELPATH = f"{EGUIPROJECT_DIRNAME}/resources"
MOCKUP_DIR_RELPATH = f"{EGUIPROJECT_DIRNAME}/mockup"
REFERENCE_FRAMES_DIR_RELPATH = f"{EGUIPROJECT_DIRNAME}/reference_frames"
RELEASE_CONFIG_RELPATH = f"{EGUIPROJECT_DIRNAME}/release.json"
REGRESSION_REPORT_RELPATH = f"{EGUIPROJECT_DIRNAME}/regression_report.html"
REGRESSION_RESULTS_RELPATH = f"{EGUIPROJECT_DIRNAME}/regression_results.json"
RESOURCE_IMAGES_DIR_RELPATH = f"{RESOURCE_DIR_RELPATH}/images"
RESOURCE_CATALOG_FILENAME = "resources.xml"
RESOURCE_CATALOG_RELPATH = f"{RESOURCE_DIR_RELPATH}/{RESOURCE_CATALOG_FILENAME}"
RESOURCE_SRC_DIR_RELPATH = "resource/src"
SUPPORTED_TEXT_FILENAME = "supported_text.txt"
SUPPORTED_TEXT_RELPATH = f"{RESOURCE_SRC_DIR_RELPATH}/{SUPPORTED_TEXT_FILENAME}"
RESOURCE_IMG_DIR_RELPATH = "resource/img"
RESOURCE_FONT_DIR_RELPATH = "resource/font"
BUILD_DESIGNER_FILENAME = "build_designer.mk"
APP_CONFIG_DESIGNER_FILENAME = "app_egui_config_designer.h"
UICODE_HEADER_FILENAME = "uicode.h"
UICODE_SOURCE_FILENAME = "uicode.c"
EGUI_STRINGS_HEADER_FILENAME = "egui_strings.h"
EGUI_STRINGS_SOURCE_FILENAME = "egui_strings.c"

BUILD_DESIGNER_RELPATH = f"{DESIGNER_PROJECT_DIRNAME}/{BUILD_DESIGNER_FILENAME}"
APP_CONFIG_DESIGNER_RELPATH = f"{DESIGNER_PROJECT_DIRNAME}/{APP_CONFIG_DESIGNER_FILENAME}"
BUILD_MK_RELPATH = "build.mk"
APP_CONFIG_RELPATH = "app_egui_config.h"
BUILD_DESIGNER_INCLUDE_TARGET = f"$(EGUI_APP_PATH)/{BUILD_DESIGNER_RELPATH}"
UICODE_HEADER_RELPATH = f"{DESIGNER_PROJECT_DIRNAME}/{UICODE_HEADER_FILENAME}"
UICODE_SOURCE_RELPATH = f"{DESIGNER_PROJECT_DIRNAME}/{UICODE_SOURCE_FILENAME}"
EGUI_STRINGS_HEADER_RELPATH = f"{DESIGNER_PROJECT_DIRNAME}/{EGUI_STRINGS_HEADER_FILENAME}"
EGUI_STRINGS_SOURCE_RELPATH = f"{DESIGNER_PROJECT_DIRNAME}/{EGUI_STRINGS_SOURCE_FILENAME}"
RESOURCE_CONFIG_RELPATH = f"{RESOURCE_SRC_DIR_RELPATH}/{APP_RESOURCE_CONFIG_FILENAME}"
DESIGNER_RESOURCE_CONFIG_RELPATH = (
    f"{RESOURCE_SRC_DIR_RELPATH}/{DESIGNER_RESOURCE_DIRNAME}/{APP_RESOURCE_CONFIG_DESIGNER_FILENAME}"
)
DESIGNER_CODEGEN_STALE_STRING_RELPATHS = (
    EGUI_STRINGS_HEADER_RELPATH,
    EGUI_STRINGS_SOURCE_RELPATH,
    EGUI_STRINGS_HEADER_FILENAME,
    EGUI_STRINGS_SOURCE_FILENAME,
)

LEGACY_BUILD_DESIGNER_RELPATH = BUILD_DESIGNER_FILENAME
LEGACY_APP_CONFIG_DESIGNER_RELPATH = APP_CONFIG_DESIGNER_FILENAME

BUILD_DESIGNER_INCLUDE_LINE = f"include {BUILD_DESIGNER_INCLUDE_TARGET}"
APP_CONFIG_DESIGNER_INCLUDE_LINE = f'#include "{APP_CONFIG_DESIGNER_RELPATH}"'

APP_CONFIG_WRAPPER_GUARD = "_APP_EGUI_CONFIG_H_"
APP_CONFIG_DESIGNER_GUARD = "_APP_EGUI_CONFIG_DESIGNER_H_"

_BUILD_DESIGNER_LINES = (
    f"EGUI_CODE_SRC\t\t+= $(EGUI_APP_PATH)/{DESIGNER_PROJECT_DIRNAME}",
    "EGUI_CODE_SRC\t\t+= $(EGUI_APP_PATH)",
    "EGUI_CODE_SRC\t\t+= $(EGUI_APP_PATH)/resource",
    "EGUI_CODE_SRC\t\t+= $(EGUI_APP_PATH)/resource/img",
    "EGUI_CODE_SRC\t\t+= $(EGUI_APP_PATH)/resource/font",
    "",
    f"EGUI_CODE_INCLUDE\t+= $(EGUI_APP_PATH)/{DESIGNER_PROJECT_DIRNAME}",
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


def _split_make_include_target(content: str, include_name: str) -> str:
    match = re.search(
        rf"^\s*include\s+(?P<path>\S*{re.escape(include_name)})\s*$",
        content,
        re.MULTILINE,
    )
    return match.group("path") if match else ""


def project_designer_dir(project_dir: str) -> str:
    return os.path.join(project_dir, DESIGNER_PROJECT_DIRNAME)


def project_config_dir(project_dir: str) -> str:
    return os.path.join(project_dir, EGUIPROJECT_DIRNAME)


def project_config_path(project_dir: str, *parts: str) -> str:
    return os.path.join(project_config_dir(project_dir), *parts)


def project_generated_resource_dir(project_dir: str) -> str:
    return os.path.join(project_dir, "resource")


def project_resource_src_dir(project_dir: str) -> str:
    return os.path.join(project_generated_resource_dir(project_dir), "src")


def project_user_resource_config_path(project_dir: str) -> str:
    return user_resource_config_path(project_resource_src_dir(project_dir))


def project_designer_resource_dir(project_dir: str) -> str:
    return designer_resource_dir(project_resource_src_dir(project_dir))


def project_designer_resource_config_path(project_dir: str) -> str:
    return designer_resource_config_path(project_resource_src_dir(project_dir))


def project_supported_text_path(project_dir: str) -> str:
    return os.path.join(project_resource_src_dir(project_dir), SUPPORTED_TEXT_FILENAME)


def project_config_resource_dir(project_dir: str) -> str:
    return project_config_path(project_dir, "resources")


def resource_catalog_path(resource_dir: str) -> str:
    return os.path.join(resource_dir, RESOURCE_CATALOG_FILENAME) if resource_dir else ""


def project_resource_catalog_path(project_dir: str) -> str:
    return resource_catalog_path(project_config_resource_dir(project_dir))


def project_config_images_dir(project_dir: str) -> str:
    return project_config_path(project_dir, "resources", "images")


def resource_images_dir(resource_dir: str) -> str:
    return os.path.join(resource_dir, "images") if resource_dir else ""


def resource_source_path(resource_dir: str, resource_type: str, filename: str) -> str:
    if not resource_dir or not filename:
        return ""
    if str(resource_type or "").strip().lower() in {"image", "image_file"}:
        return os.path.join(resource_images_dir(resource_dir), filename)
    return os.path.join(resource_dir, filename)


def project_config_layout_dir(project_dir: str) -> str:
    return project_config_path(project_dir, "layout")


def project_config_mockup_dir(project_dir: str) -> str:
    return project_config_path(project_dir, "mockup")


def project_config_reference_frames_dir(project_dir: str) -> str:
    return project_config_path(project_dir, "reference_frames")


def project_config_regression_report_path(project_dir: str) -> str:
    return project_config_path(project_dir, "regression_report.html")


def project_config_regression_results_path(project_dir: str) -> str:
    return project_config_path(project_dir, "regression_results.json")


def _sdk_example_path(sdk_root: str | None, app_name: str | None, resolver) -> str:
    app_dir = sdk_example_app_dir(sdk_root, app_name)
    if not app_dir:
        return ""
    return resolver(app_dir)


def sdk_example_config_dir(sdk_root: str | None, app_name: str | None) -> str:
    return _sdk_example_path(sdk_root, app_name, project_config_dir)


def sdk_example_layout_dir(sdk_root: str | None, app_name: str | None) -> str:
    return _sdk_example_path(sdk_root, app_name, project_config_layout_dir)


def sdk_example_config_resource_dir(sdk_root: str | None, app_name: str | None) -> str:
    return _sdk_example_path(sdk_root, app_name, project_config_resource_dir)


def sdk_example_resource_images_dir(sdk_root: str | None, app_name: str | None) -> str:
    return _sdk_example_path(sdk_root, app_name, project_config_images_dir)


def sdk_example_generated_resource_dir(sdk_root: str | None, app_name: str | None) -> str:
    return _sdk_example_path(sdk_root, app_name, project_generated_resource_dir)


def sdk_example_resource_src_dir(sdk_root: str | None, app_name: str | None) -> str:
    return _sdk_example_path(sdk_root, app_name, project_resource_src_dir)


def sdk_example_supported_text_path(sdk_root: str | None, app_name: str | None) -> str:
    return _sdk_example_path(sdk_root, app_name, project_supported_text_path)


def sdk_example_resource_catalog_path(sdk_root: str | None, app_name: str | None) -> str:
    return _sdk_example_path(sdk_root, app_name, project_resource_catalog_path)


def sdk_example_user_resource_config_path(sdk_root: str | None, app_name: str | None) -> str:
    return _sdk_example_path(sdk_root, app_name, project_user_resource_config_path)


def sdk_example_designer_resource_config_path(sdk_root: str | None, app_name: str | None) -> str:
    return _sdk_example_path(sdk_root, app_name, project_designer_resource_config_path)


def sdk_example_app_config_path(sdk_root: str | None, app_name: str | None) -> str:
    return _sdk_example_path(sdk_root, app_name, project_app_config_path)


def sdk_example_reference_frames_dir(sdk_root: str | None, app_name: str | None) -> str:
    return _sdk_example_path(sdk_root, app_name, project_config_reference_frames_dir)


def sdk_example_regression_report_path(sdk_root: str | None, app_name: str | None) -> str:
    return _sdk_example_path(sdk_root, app_name, project_config_regression_report_path)


def sdk_example_regression_results_path(sdk_root: str | None, app_name: str | None) -> str:
    return _sdk_example_path(sdk_root, app_name, project_config_regression_results_path)


def project_file_relpath(app_name: str) -> str:
    return f"{app_name}.egui"


def project_build_mk_path(project_dir: str) -> str:
    return os.path.join(project_dir, BUILD_MK_RELPATH)


def project_app_config_path(project_dir: str) -> str:
    return os.path.join(project_dir, APP_CONFIG_RELPATH)


def project_file_path(project_dir: str, app_name: str) -> str:
    return os.path.join(project_dir, project_file_relpath(app_name))


def _layout_xml_filename(page_name: str) -> str:
    return f"{page_name}.xml"


def project_layout_xml_path(project_dir: str, page_name: str) -> str:
    return project_config_path(project_dir, "layout", _layout_xml_filename(page_name))


def sdk_example_layout_xml_path(sdk_root: str | None, app_name: str | None, page_name: str) -> str:
    app_dir = sdk_example_app_dir(sdk_root, app_name)
    if not app_dir:
        return ""
    return project_layout_xml_path(app_dir, page_name)


def project_layout_xml_relpath(page_name: str) -> str:
    return f"{LAYOUT_DIR_RELPATH}/{_layout_xml_filename(page_name)}"


def _normalize_project_copy_dir(path: str) -> str:
    return os.path.normpath(os.path.abspath(path)) if path else ""


def _copy_file_if_missing(src_path: str, dst_path: str) -> None:
    if not os.path.isfile(src_path) or os.path.exists(dst_path):
        return
    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
    shutil.copy2(src_path, dst_path)


def _copy_project_resource_tree(src_dir: str, dst_dir: str) -> None:
    for walk_root, dir_names, file_names in os.walk(src_dir):
        dir_names[:] = [name for name in dir_names if not is_designer_resource_path(name)]
        rel_root = os.path.relpath(walk_root, src_dir)
        walk_dst = dst_dir if rel_root in ("", ".") else os.path.join(dst_dir, rel_root)
        os.makedirs(walk_dst, exist_ok=True)
        for file_name in file_names:
            if is_designer_resource_path(file_name):
                continue
            shutil.copy2(
                os.path.join(walk_root, file_name),
                os.path.join(walk_dst, file_name),
            )


def copy_project_sidecar_files(src_dir: str, dst_dir: str) -> None:
    """Copy user-owned Save As sidecars while skipping Designer-reserved resources."""
    src_dir = _normalize_project_copy_dir(src_dir)
    dst_dir = _normalize_project_copy_dir(dst_dir)
    if not src_dir or not os.path.isdir(src_dir) or not dst_dir or src_dir == dst_dir:
        return

    for src_path, dst_path in (
        (project_build_mk_path(src_dir), project_build_mk_path(dst_dir)),
        (project_app_config_path(src_dir), project_app_config_path(dst_dir)),
        (
            os.path.join(src_dir, RESOURCE_CONFIG_RELPATH),
            os.path.join(dst_dir, RESOURCE_CONFIG_RELPATH),
        ),
    ):
        _copy_file_if_missing(src_path, dst_path)

    src_resource_dir = project_config_resource_dir(src_dir)
    dst_resource_dir = project_config_resource_dir(dst_dir)
    if os.path.isdir(src_resource_dir):
        _copy_project_resource_tree(src_resource_dir, dst_resource_dir)

    src_mockup_dir = project_config_mockup_dir(src_dir)
    dst_mockup_dir = project_config_mockup_dir(dst_dir)
    if os.path.isdir(src_mockup_dir):
        shutil.copytree(src_mockup_dir, dst_mockup_dir, dirs_exist_ok=True)


def default_scaffold_circle_radius(screen_width, screen_height) -> int:
    return min(int(screen_width), int(screen_height)) // 2


def bind_project_storage(project, project_dir="", *, sdk_root=None):
    """Normalize and attach the persisted project directory and optional SDK root."""
    project.project_dir = os.path.normpath(str(project_dir)) if project_dir else ""
    if sdk_root is not None:
        project.sdk_root = os.path.normpath(str(sdk_root)) if sdk_root else ""
    return project


def designer_scaffold_kwargs(
    screen_width,
    screen_height,
    *,
    overwrite=False,
    color_depth=16,
    circle_radius=None,
    extra_config_macros=None,
    refresh_designer_resource_config=None,
    remove_legacy_designer_files=False,
):
    """Return normalized scaffold keyword arguments for shared Designer helpers."""
    if circle_radius is None:
        circle_radius = default_scaffold_circle_radius(screen_width, screen_height)

    kwargs = {
        "overwrite": overwrite,
        "color_depth": color_depth,
        "circle_radius": circle_radius,
    }
    if extra_config_macros is not None:
        kwargs["extra_config_macros"] = list(extra_config_macros)
    if refresh_designer_resource_config is not None:
        kwargs["refresh_designer_resource_config"] = refresh_designer_resource_config
    if remove_legacy_designer_files:
        kwargs["remove_legacy_designer_files"] = True
    return kwargs


def designer_conversion_scaffold_kwargs(
    screen_width,
    screen_height,
    *,
    color_depth=16,
):
    """Return scaffold defaults shared by conversion/import entry points."""
    return designer_scaffold_kwargs(
        screen_width,
        screen_height,
        overwrite=True,
        color_depth=color_depth,
        extra_config_macros=[("EGUI_CONFIG_FUNCTION_SUPPORT_SHADOW", "1")],
        refresh_designer_resource_config=False,
    )


def designer_codegen_relpath(filename: str) -> str:
    normalized = str(filename or "").replace("\\", "/").lstrip("/")
    return f"{DESIGNER_PROJECT_DIRNAME}/{normalized}"


def designer_page_header_relpath(page_name: str) -> str:
    return designer_codegen_relpath(f"{page_name}.h")


def designer_page_layout_relpath(page_name: str) -> str:
    return designer_codegen_relpath(f"{page_name}_layout.c")


def designer_codegen_legacy_root_relpath(relpath: str) -> str:
    normalized = str(relpath or "").replace("\\", "/").lstrip("/")
    prefix = f"{DESIGNER_PROJECT_DIRNAME}/"
    if normalized.startswith(prefix):
        return normalized[len(prefix):]
    return normalized


def legacy_designer_codegen_cleanup_relpaths(generated_files, *, remove_stale_strings=False):
    """Return legacy root paths that should be removed after writing designer outputs."""
    generated_relpaths = {
        str(filename or "").replace("\\", "/")
        for filename in getattr(generated_files, "keys", lambda: generated_files)()
    }
    cleanup_relpaths = {
        designer_codegen_legacy_root_relpath(relpath)
        for relpath in generated_relpaths
        if relpath.startswith(f"{DESIGNER_PROJECT_DIRNAME}/")
    }

    if remove_stale_strings and EGUI_STRINGS_HEADER_RELPATH not in generated_relpaths:
        cleanup_relpaths.update(DESIGNER_CODEGEN_STALE_STRING_RELPATHS)

    cleanup_relpaths.difference_update(generated_relpaths)
    return tuple(sorted(relpath for relpath in cleanup_relpaths if relpath))


def _resolve_project_output_path(project_dir, relpath):
    project_root = os.path.realpath(os.path.normpath(str(project_dir or "")))
    normalized_relpath = str(relpath or "").replace("\\", "/").lstrip("/")
    if not project_root or not normalized_relpath:
        return None, normalized_relpath

    candidate = os.path.realpath(
        os.path.join(project_root, normalized_relpath.replace("/", os.sep))
    )
    try:
        common = os.path.commonpath([project_root, candidate])
    except ValueError:
        return None, normalized_relpath
    if common != project_root:
        return None, normalized_relpath
    return candidate, normalized_relpath


def write_generated_project_files(project_dir, generated_files, *, newline=None):
    """Write generated project files under ``project_dir`` and return their relpaths."""
    written = []
    for relpath, content in (generated_files or {}).items():
        path, normalized_relpath = _resolve_project_output_path(project_dir, relpath)
        if path is None:
            raise ValueError(f"Generated file path escapes project directory: {relpath}")
        parent_dir = os.path.dirname(path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline=newline) as f:
            f.write(content)
        written.append(normalized_relpath)
    return tuple(written)


def cleanup_legacy_designer_codegen_files(
    project_dir,
    generated_files,
    *,
    backup_existing=False,
    remove_stale_strings=False,
):
    """Remove legacy designer codegen copies under ``project_dir``."""
    if not project_dir:
        return ()
    cleanup_relpaths = legacy_designer_codegen_cleanup_relpaths(
        generated_files,
        remove_stale_strings=remove_stale_strings,
    )
    if not cleanup_relpaths:
        return ()

    backup_file = None
    backup_root = ""
    if backup_existing:
        from ..generator.user_code_preserver import backup_file as _backup_file

        backup_file = _backup_file
        backup_root = os.path.join(
            os.path.realpath(os.path.normpath(str(project_dir or ""))),
            EGUIPROJECT_DIRNAME,
            "backup",
        )

    removed = []
    for relpath in cleanup_relpaths:
        path, _normalized_relpath = _resolve_project_output_path(project_dir, relpath)
        if path is None or not os.path.isfile(path):
            continue
        try:
            if backup_file is not None:
                backup_file(path, backup_root)
            os.remove(path)
            removed.append(relpath)
        except OSError:
            pass
    return tuple(removed)


def materialize_generated_project_files(
    project_dir,
    generated_files,
    all_generated_files,
    *,
    newline=None,
    backup_existing=False,
    remove_stale_strings=False,
):
    """Write generated project files and remove legacy designer codegen copies."""
    written = write_generated_project_files(
        project_dir,
        generated_files,
        newline=newline,
    )
    removed = cleanup_legacy_designer_codegen_files(
        project_dir,
        all_generated_files,
        backup_existing=backup_existing,
        remove_stale_strings=remove_stale_strings,
    )
    return written, removed


def build_designer_path(project_dir: str) -> str:
    return os.path.join(project_dir, BUILD_DESIGNER_RELPATH.replace("/", os.sep))


def app_config_designer_path(project_dir: str) -> str:
    return os.path.join(project_dir, APP_CONFIG_DESIGNER_RELPATH.replace("/", os.sep))


def legacy_build_designer_path(project_dir: str) -> str:
    return os.path.join(project_dir, LEGACY_BUILD_DESIGNER_RELPATH)


def legacy_app_config_designer_path(project_dir: str) -> str:
    return os.path.join(project_dir, LEGACY_APP_CONFIG_DESIGNER_RELPATH)


def build_mk_designer_include_target(content: str) -> str:
    target = _split_make_include_target(content, BUILD_DESIGNER_FILENAME)
    return target if target.replace("\\", "/") == BUILD_DESIGNER_INCLUDE_TARGET else ""


def app_config_designer_include_target(content: str) -> str:
    target = _split_local_include_target(content, APP_CONFIG_DESIGNER_FILENAME)
    return target.replace("\\", "/") if target.replace("\\", "/") == APP_CONFIG_DESIGNER_RELPATH else ""


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
    include_target = app_config_designer_include_target(wrapper_content)
    if include_target:
        designer_path = os.path.normpath(os.path.join(os.path.dirname(config_path), include_target))
        _consume(designer_path)

    return (
        width if width is not None else default_width,
        height if height is not None else default_height,
    )


def build_mk_includes_designer(content: str) -> bool:
    """Return True when ``build.mk`` already includes ``build_designer.mk``."""
    return bool(build_mk_designer_include_target(content))


def app_config_includes_designer(content: str) -> bool:
    """Return True when ``app_egui_config.h`` already includes the designer header."""
    return bool(app_config_designer_include_target(content))


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
        if _split_make_include_target(raw_line, BUILD_DESIGNER_FILENAME):
            continue
        if normalized in designer_keys:
            continue
        if re.match(r"^#\s*(Build configuration|Designer-managed build inputs|User build overrides)\b", stripped):
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
        }:
            continue
        if _split_local_include_target(raw_line, APP_CONFIG_DESIGNER_FILENAME):
            continue
        if stripped == "#endif" and conditional_depth <= 0:
            continue
        if stripped == "/* Define user overrides above the Designer include. */":
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


def _read_text_file(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def _write_text(path, content):
    parent_dir = os.path.dirname(path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


def _write_text_if_changed(path, content):
    existing = _read_text_file(path)
    if existing == content:
        return "unchanged"
    _write_text(path, content)
    return "created" if existing is None else "updated"


def _write_text_if_missing(path, content):
    if os.path.exists(path):
        return "unchanged"
    _write_text(path, content)
    return "created"


def _remove_file_if_exists(path):
    try:
        if path and os.path.exists(path):
            os.remove(path)
            return True
    except OSError:
        return False
    return False


def generate_designer_resource_config(project, src_dir):
    """Ensure the user overlay exists and regenerate the Designer resource config."""
    user_config_path = user_resource_config_path(src_dir)
    user_config_created = ensure_resource_config_file(user_config_path)

    from ..generator.resource_config_generator import ResourceConfigGenerator

    config_path = ResourceConfigGenerator().generate_and_save(project, src_dir)
    return user_config_created, config_path


def sync_project_resources_and_generate_designer_resource_config(
    project,
    project_dir,
    src_dir=None,
    *,
    before_generate=None,
):
    """Sync project resources into ``resource/src`` and regenerate resource configs."""
    project_dir = os.path.normpath(project_dir)
    src_dir = os.path.normpath(src_dir or project_resource_src_dir(project_dir))
    project.sync_resources_to_src(project_dir)
    if callable(before_generate):
        before_generate(project_dir)
    return generate_designer_resource_config(project, src_dir)


def sync_project_scaffold_sidecars(
    project_dir,
    app_name,
    screen_width=240,
    screen_height=320,
    *,
    color_depth=16,
    circle_radius=None,
    extra_config_macros=None,
    refresh_user_wrappers=False,
    refresh_designer_resource_config=False,
    remove_legacy_designer_files=False,
):
    """Create or migrate split scaffold sidecar files for a project directory.

    Returns a mapping of normalized project-relative paths to actions:
    ``created``, ``updated``, ``unchanged``, or ``removed``.
    """
    project_dir = os.path.normpath(project_dir)
    designer_dir = project_designer_dir(project_dir)
    resource_src_dir = project_resource_src_dir(project_dir)

    os.makedirs(project_dir, exist_ok=True)
    os.makedirs(designer_dir, exist_ok=True)
    os.makedirs(resource_src_dir, exist_ok=True)

    actions = {}

    build_mk_path = project_build_mk_path(project_dir)
    build_mk_existing = _read_text_file(build_mk_path)
    if build_mk_existing is None:
        actions[BUILD_MK_RELPATH] = _write_text_if_changed(
            build_mk_path,
            make_app_build_mk_content(app_name),
        )
    elif refresh_user_wrappers or build_mk_designer_include_target(build_mk_existing) != BUILD_DESIGNER_INCLUDE_TARGET:
        actions[BUILD_MK_RELPATH] = _write_text_if_changed(
            build_mk_path,
            migrate_app_build_mk_content(build_mk_existing, app_name),
        )
    else:
        actions[BUILD_MK_RELPATH] = "unchanged"

    config_h_path = project_app_config_path(project_dir)
    config_h_existing = _read_text_file(config_h_path)
    if config_h_existing is None:
        actions[APP_CONFIG_RELPATH] = _write_text_if_changed(
            config_h_path,
            make_app_config_h_content(app_name),
        )
    elif refresh_user_wrappers or app_config_designer_include_target(config_h_existing) != APP_CONFIG_DESIGNER_RELPATH:
        actions[APP_CONFIG_RELPATH] = _write_text_if_changed(
            config_h_path,
            migrate_app_config_h_content(
                config_h_existing,
                app_name,
                screen_width,
                screen_height,
                color_depth=color_depth,
                circle_radius=circle_radius,
            ),
        )
    else:
        actions[APP_CONFIG_RELPATH] = "unchanged"

    actions[BUILD_DESIGNER_RELPATH] = _write_text_if_changed(
        build_designer_path(project_dir),
        make_app_build_designer_mk_content(app_name),
    )
    actions[APP_CONFIG_DESIGNER_RELPATH] = _write_text_if_changed(
        app_config_designer_path(project_dir),
        make_app_config_designer_h_content(
            app_name,
            screen_width,
            screen_height,
            color_depth=color_depth,
            circle_radius=circle_radius,
            extra_macros=extra_config_macros,
        ),
    )

    actions[RESOURCE_CONFIG_RELPATH] = _write_text_if_missing(
        user_resource_config_path(resource_src_dir),
        make_empty_resource_config_content(),
    )
    designer_resource_cfg = designer_resource_config_path(resource_src_dir)
    if refresh_designer_resource_config:
        actions[DESIGNER_RESOURCE_CONFIG_RELPATH] = _write_text_if_changed(
            designer_resource_cfg,
            make_empty_resource_config_content(),
        )
    else:
        actions[DESIGNER_RESOURCE_CONFIG_RELPATH] = _write_text_if_missing(
            designer_resource_cfg,
            make_empty_resource_config_content(),
        )

    if remove_legacy_designer_files:
        for relpath, legacy_path in (
            (LEGACY_BUILD_DESIGNER_RELPATH, legacy_build_designer_path(project_dir)),
            (LEGACY_APP_CONFIG_DESIGNER_RELPATH, legacy_app_config_designer_path(project_dir)),
        ):
            if _remove_file_if_exists(legacy_path):
                actions[relpath] = "removed"

    return actions


def normalize_scaffold_pages(pages=None):
    """Return normalized scaffold page names with a stable default."""
    normalized = [str(page_name).strip() for page_name in (pages or []) if str(page_name).strip()]
    return normalized or ["main_page"]


def build_empty_project_model(
    app_name,
    screen_width=240,
    screen_height=320,
    *,
    sdk_root="",
    project_dir="",
    pages=None,
):
    """Build a minimal Designer project model with default empty pages."""
    from ..model.project import Project

    project = Project(screen_width=screen_width, screen_height=screen_height, app_name=app_name)
    bind_project_storage(project, project_dir, sdk_root=sdk_root)

    normalized_pages = normalize_scaffold_pages(pages)
    project.startup_page = normalized_pages[0]
    for page_name in normalized_pages:
        project.create_new_page(page_name)
    return project


def require_page_root(page, page_name=""):
    """Return a page root widget, raising when the page or root widget is missing."""
    target_page_name = str(page_name or getattr(page, "name", "") or "").strip()
    if page is None:
        if target_page_name:
            raise RuntimeError(f"Scaffold page '{target_page_name}' was not created")
        raise RuntimeError("Scaffold page was not created")
    root = page.root_widget
    if root is None:
        raise RuntimeError(f"Scaffold page '{page.name}' did not create a root widget")
    return root


def build_basic_widget_model(
    widget_type="label",
    *,
    name="title",
    x=12,
    y=16,
    width=100,
    height=24,
):
    """Build a basic widget model with shared scaffold defaults."""
    from ..model.widget_model import WidgetModel

    return WidgetModel(widget_type, name=name, x=x, y=y, width=width, height=height)


def add_page_widget(
    page,
    widget_type="label",
    *,
    name="title",
    x=12,
    y=16,
    width=100,
    height=24,
):
    """Attach a basic widget to a page scaffold and return it."""
    widget = build_basic_widget_model(
        widget_type,
        name=name,
        x=x,
        y=y,
        width=width,
        height=height,
    )
    root = require_page_root(page)
    root.add_child(widget)
    return widget


def add_widget_children(parent, widgets=None):
    """Attach a list of widgets to a parent container in order."""
    for widget in widgets or []:
        parent.add_child(widget)
    return parent


def build_page_model_with_widget(
    page_name="main_page",
    widget_type="label",
    *,
    screen_width=240,
    screen_height=320,
    root_widget_type="group",
    root_name="root_group",
    root_x=0,
    root_y=0,
    **widget_kwargs,
):
    """Build a default page model with one attached widget."""
    widget = build_basic_widget_model(widget_type, **widget_kwargs)
    page, root = build_page_model_with_widgets(
        page_name,
        screen_width=screen_width,
        screen_height=screen_height,
        root_widget_type=root_widget_type,
        root_name=root_name,
        root_x=root_x,
        root_y=root_y,
        widgets=[widget],
    )
    return page, widget


def build_page_model_only_with_widget(
    page_name="main_page",
    widget_type="label",
    *,
    screen_width=240,
    screen_height=320,
    root_widget_type="group",
    root_name="root_group",
    root_x=0,
    root_y=0,
    **widget_kwargs,
):
    """Build a default page model with one attached widget and return only the widget."""
    _page, widget = build_page_model_with_widget(
        page_name,
        widget_type,
        screen_width=screen_width,
        screen_height=screen_height,
        root_widget_type=root_widget_type,
        root_name=root_name,
        root_x=root_x,
        root_y=root_y,
        **widget_kwargs,
    )
    return widget


def require_project_page_root(project, page_name=""):
    """Return a project page and root widget, raising when either is missing."""
    target_page_name = str(page_name or "").strip()
    page = project.get_page_by_name(target_page_name) if target_page_name else project.get_startup_page()
    if page is None:
        if target_page_name:
            raise RuntimeError(f"Scaffold project did not create page '{target_page_name}'")
        raise RuntimeError("Scaffold project did not create a startup page")
    root = require_page_root(page, target_page_name)
    return page, root


def build_empty_project_model_with_root(
    app_name,
    screen_width=240,
    screen_height=320,
    *,
    sdk_root="",
    project_dir="",
    page_name="main_page",
):
    """Build a minimal Designer project model and return it with its page root widget."""
    project = build_empty_project_model(
        app_name,
        screen_width,
        screen_height,
        sdk_root=sdk_root,
        project_dir=project_dir,
        pages=[page_name],
    )
    page, root = require_project_page_root(project, page_name)
    return project, page, root


def build_project_model_from_pages(
    pages=None,
    app_name="TestApp",
    screen_width=240,
    screen_height=320,
    *,
    sdk_root="",
    project_dir="",
    page_mode="easy_page",
    startup=None,
    startup_page=None,
):
    """Build a project model from preconstructed page models."""
    from ..model.project import Project

    project = Project(screen_width=screen_width, screen_height=screen_height, app_name=app_name)
    bind_project_storage(project, project_dir, sdk_root=sdk_root)
    project.page_mode = page_mode
    for page in pages or []:
        project.add_page(page)
    if startup_page is not None:
        project.startup_page = startup_page
    elif startup is not None:
        project.startup_page = startup
    elif project.pages:
        project.startup_page = project.pages[0].name
    return project


def build_project_model_from_root(
    root,
    *,
    page_name="main_page",
    app_name="TestApp",
    screen_width=None,
    screen_height=None,
    sdk_root="",
    project_dir="",
    page_mode="easy_page",
    startup=None,
    startup_page=None,
):
    """Build a single-page project model around a caller-supplied root widget."""
    resolved_screen_width = screen_width
    if resolved_screen_width is None:
        resolved_screen_width = getattr(root, "width", None)
    if resolved_screen_width is None:
        resolved_screen_width = 240

    resolved_screen_height = screen_height
    if resolved_screen_height is None:
        resolved_screen_height = getattr(root, "height", None)
    if resolved_screen_height is None:
        resolved_screen_height = 320

    page = build_page_model_from_root(
        page_name,
        root=root,
        screen_width=resolved_screen_width,
        screen_height=resolved_screen_height,
    )
    project = build_project_model_from_pages(
        [page],
        app_name=app_name,
        screen_width=resolved_screen_width,
        screen_height=resolved_screen_height,
        sdk_root=sdk_root,
        project_dir=project_dir,
        page_mode=page_mode,
        startup=startup,
        startup_page=startup_page,
    )
    return project, page


def build_project_model_from_root_with_widgets(
    root,
    *,
    widgets=None,
    page_name="main_page",
    app_name="TestApp",
    screen_width=None,
    screen_height=None,
    sdk_root="",
    project_dir="",
    page_mode="easy_page",
    startup=None,
    startup_page=None,
):
    """Build a single-page project model around a supplied root widget and attach children."""
    add_widget_children(root, widgets)
    return build_project_model_from_root(
        root,
        page_name=page_name,
        app_name=app_name,
        screen_width=screen_width,
        screen_height=screen_height,
        sdk_root=sdk_root,
        project_dir=project_dir,
        page_mode=page_mode,
        startup=startup,
        startup_page=startup_page,
    )


def build_project_model_only_from_root_with_widgets(
    root,
    *,
    widgets=None,
    page_name="main_page",
    app_name="TestApp",
    screen_width=None,
    screen_height=None,
    sdk_root="",
    project_dir="",
    page_mode="easy_page",
    startup=None,
    startup_page=None,
):
    """Build a root-backed single-page project model and return only the populated project."""
    project, _page = build_project_model_from_root_with_widgets(
        root,
        widgets=widgets,
        page_name=page_name,
        app_name=app_name,
        screen_width=screen_width,
        screen_height=screen_height,
        sdk_root=sdk_root,
        project_dir=project_dir,
        page_mode=page_mode,
        startup=startup,
        startup_page=startup_page,
    )
    return project


def build_page_model_with_root_widget(
    page_name="main_page",
    root_widget_type="group",
    *,
    root_name="root_group",
    x=0,
    y=0,
    width=240,
    height=320,
):
    """Build a page model with a caller-configurable scaffold root widget."""
    from ..model.page import Page

    root = build_basic_widget_model(
        root_widget_type,
        name=root_name,
        x=x,
        y=y,
        width=width,
        height=height,
    )
    page = Page(file_path=f"layout/{page_name}.xml", root_widget=root)
    return page, root


def build_page_model_from_root(
    page_name="main_page",
    root=None,
    *,
    screen_width=240,
    screen_height=320,
):
    """Build a page model around a caller-supplied root widget or a default group root."""
    from ..model.page import Page

    resolved_root = root
    if resolved_root is None:
        resolved_root = build_basic_widget_model(
            "group",
            name="root_group",
            x=0,
            y=0,
            width=screen_width,
            height=screen_height,
        )
    return Page(file_path=f"layout/{page_name}.xml", root_widget=resolved_root)


def build_page_model_from_root_with_widgets(
    page_name="main_page",
    root=None,
    *,
    screen_width=240,
    screen_height=320,
    widgets=None,
):
    """Build a page model around a supplied root widget and attach children."""
    page = build_page_model_from_root(
        page_name,
        root=root,
        screen_width=screen_width,
        screen_height=screen_height,
    )
    resolved_root = require_page_root(page, page_name)
    add_widget_children(resolved_root, widgets)
    return page, resolved_root


def build_page_model_with_widgets(
    page_name="main_page",
    *,
    screen_width=240,
    screen_height=320,
    root_widget_type="group",
    root_name="root_group",
    root_x=0,
    root_y=0,
    widgets=None,
):
    """Build a page model with a configurable root widget and attached children."""
    page, root = build_page_model_with_root_widget(
        page_name,
        root_widget_type,
        root_name=root_name,
        x=root_x,
        y=root_y,
        width=screen_width,
        height=screen_height,
    )
    add_widget_children(root, widgets)
    return page, root


def build_page_model_root_with_widgets(
    page_name="main_page",
    *,
    screen_width=240,
    screen_height=320,
    root_widget_type="group",
    root_name="root_group",
    root_x=0,
    root_y=0,
    widgets=None,
):
    """Build a page model with attached children and return only the populated root widget."""
    _page, root = build_page_model_with_widgets(
        page_name,
        screen_width=screen_width,
        screen_height=screen_height,
        root_widget_type=root_widget_type,
        root_name=root_name,
        root_x=root_x,
        root_y=root_y,
        widgets=widgets,
    )
    return root


def build_project_model_with_page_widgets(
    app_name,
    screen_width=240,
    screen_height=320,
    *,
    sdk_root="",
    project_dir="",
    page_widgets=None,
    page_customizers=None,
    pages=None,
    project_customizer=None,
):
    """Build a project model, attach widgets to named pages, and apply optional customizers."""
    resolved_pages = pages
    if resolved_pages is None:
        resolved_pages = []
        for page_name in page_widgets or {}:
            if page_name not in resolved_pages:
                resolved_pages.append(page_name)
        for page_name in page_customizers or {}:
            if page_name not in resolved_pages:
                resolved_pages.append(page_name)
        if not resolved_pages:
            resolved_pages = None
    else:
        resolved_pages = list(resolved_pages)
        for page_name in page_widgets or {}:
            if page_name not in resolved_pages:
                resolved_pages.append(page_name)
        for page_name in page_customizers or {}:
            if page_name not in resolved_pages:
                resolved_pages.append(page_name)

    project = build_empty_project_model(
        app_name,
        screen_width,
        screen_height,
        sdk_root=sdk_root,
        project_dir=project_dir,
        pages=resolved_pages,
    )
    roots = {}
    pages_by_name = {}
    for page in project.pages:
        resolved_page, root = require_project_page_root(project, page.name)
        pages_by_name[page.name] = resolved_page
        roots[page.name] = root

    for page_name, widgets in (page_widgets or {}).items():
        root = roots[page_name]
        add_widget_children(root, widgets)

    for page_name, page_customizer in (page_customizers or {}).items():
        page_customizer(pages_by_name[page_name], roots[page_name])

    if project_customizer is not None:
        project_customizer(project)

    return project, roots


def build_project_model_only_with_page_widgets(
    app_name,
    screen_width=240,
    screen_height=320,
    *,
    sdk_root="",
    project_dir="",
    page_widgets=None,
    page_customizers=None,
    pages=None,
    project_customizer=None,
):
    """Build a multi-page project model and return only the populated project."""
    project, _roots = build_project_model_with_page_widgets(
        app_name,
        screen_width,
        screen_height,
        sdk_root=sdk_root,
        project_dir=project_dir,
        page_widgets=page_widgets,
        page_customizers=page_customizers,
        pages=pages,
        project_customizer=project_customizer,
    )
    return project


def build_project_model_with_widgets(
    app_name,
    screen_width=240,
    screen_height=320,
    *,
    sdk_root="",
    project_dir="",
    page_name="main_page",
    widgets=None,
    page_customizer=None,
    project_customizer=None,
):
    """Build a single-page project model, attach widgets, and apply optional customizers."""
    project, roots = build_project_model_with_page_widgets(
        app_name,
        screen_width,
        screen_height,
        sdk_root=sdk_root,
        project_dir=project_dir,
        page_widgets={page_name: widgets or []},
        page_customizers={page_name: page_customizer} if page_customizer is not None else None,
        pages=[page_name],
        project_customizer=project_customizer,
    )
    page, root = require_project_page_root(project, page_name)
    return project, page, root


def build_project_model_and_page_with_widgets(
    app_name,
    screen_width=240,
    screen_height=320,
    *,
    sdk_root="",
    project_dir="",
    page_name="main_page",
    widgets=None,
    page_customizer=None,
    project_customizer=None,
):
    """Build a single-page project model and return the project with its populated page."""
    project, page, _root = build_project_model_with_widgets(
        app_name,
        screen_width,
        screen_height,
        sdk_root=sdk_root,
        project_dir=project_dir,
        page_name=page_name,
        widgets=widgets,
        page_customizer=page_customizer,
        project_customizer=project_customizer,
    )
    return project, page


def build_project_model_and_root_with_widgets(
    app_name,
    screen_width=240,
    screen_height=320,
    *,
    sdk_root="",
    project_dir="",
    page_name="main_page",
    widgets=None,
    page_customizer=None,
    project_customizer=None,
):
    """Build a single-page project model and return the project with its populated root widget."""
    project, _page, root = build_project_model_with_widgets(
        app_name,
        screen_width,
        screen_height,
        sdk_root=sdk_root,
        project_dir=project_dir,
        page_name=page_name,
        widgets=widgets,
        page_customizer=page_customizer,
        project_customizer=project_customizer,
    )
    return project, root


def build_project_model_only_with_widgets(
    app_name,
    screen_width=240,
    screen_height=320,
    *,
    sdk_root="",
    project_dir="",
    page_name="main_page",
    widgets=None,
    page_customizer=None,
    project_customizer=None,
):
    """Build a single-page project model and return only the populated project."""
    project, _page, _root = build_project_model_with_widgets(
        app_name,
        screen_width,
        screen_height,
        sdk_root=sdk_root,
        project_dir=project_dir,
        page_name=page_name,
        widgets=widgets,
        page_customizer=page_customizer,
        project_customizer=project_customizer,
    )
    return project


def build_project_model_with_widget(
    app_name,
    widget_type="label",
    *,
    page_name="main_page",
    screen_width=240,
    screen_height=320,
    sdk_root="",
    project_dir="",
    page_customizer=None,
    project_customizer=None,
    **widget_kwargs,
):
    """Build a single-page project model, attach one widget, and apply optional customizers."""
    widget = build_basic_widget_model(widget_type, **widget_kwargs)
    project, page, root = build_project_model_with_widgets(
        app_name,
        screen_width,
        screen_height,
        sdk_root=sdk_root,
        project_dir=project_dir,
        page_name=page_name,
        widgets=[widget],
        page_customizer=page_customizer,
        project_customizer=project_customizer,
    )
    return project, page, widget


def build_project_model_and_page_with_widget(
    app_name,
    widget_type="label",
    *,
    page_name="main_page",
    screen_width=240,
    screen_height=320,
    sdk_root="",
    project_dir="",
    page_customizer=None,
    project_customizer=None,
    **widget_kwargs,
):
    """Build a single-page project model with one widget and return the project with its page."""
    project, page, _widget = build_project_model_with_widget(
        app_name,
        widget_type,
        page_name=page_name,
        screen_width=screen_width,
        screen_height=screen_height,
        sdk_root=sdk_root,
        project_dir=project_dir,
        page_customizer=page_customizer,
        project_customizer=project_customizer,
        **widget_kwargs,
    )
    return project, page


def build_project_model_only_with_widget(
    app_name,
    widget_type="label",
    *,
    page_name="main_page",
    screen_width=240,
    screen_height=320,
    sdk_root="",
    project_dir="",
    page_customizer=None,
    project_customizer=None,
    **widget_kwargs,
):
    """Build a single-page project model with one widget and return only the project."""
    project, _page, _widget = build_project_model_with_widget(
        app_name,
        widget_type,
        page_name=page_name,
        screen_width=screen_width,
        screen_height=screen_height,
        sdk_root=sdk_root,
        project_dir=project_dir,
        page_customizer=page_customizer,
        project_customizer=project_customizer,
        **widget_kwargs,
    )
    return project


def build_empty_project_xml(app_name, screen_width=240, screen_height=320, *, stored_sdk_root="", pages=None):
    """Build an empty ``.egui`` project XML using the shared project model."""
    project = build_empty_project_model(
        app_name,
        screen_width,
        screen_height,
        pages=pages,
    )
    return project.to_xml_string(stored_sdk_root=stored_sdk_root)


def build_empty_page_xml(page_name, screen_width=240, screen_height=320):
    """Build an empty page layout XML using the shared default page model."""
    from ..model.page import Page

    page = Page.create_default(
        page_name,
        screen_width=screen_width,
        screen_height=screen_height,
    )
    return page.to_xml_string()


def build_empty_resources_xml():
    """Build an empty resources.xml using the shared resource catalog serializer."""
    from ..model.resource_catalog import ResourceCatalog

    return ResourceCatalog().to_xml_string()


def sync_project_scaffold_core_files(
    project_dir,
    app_name,
    screen_width=240,
    screen_height=320,
    *,
    stored_sdk_root="",
    pages=None,
):
    """Create or refresh the core scaffold files for a Designer project."""
    project_dir = os.path.normpath(project_dir)
    normalized_pages = normalize_scaffold_pages(pages)

    for rel_dir in (
        EGUIPROJECT_DIRNAME,
        LAYOUT_DIR_RELPATH,
        RESOURCE_DIR_RELPATH,
        RESOURCE_IMAGES_DIR_RELPATH,
        RESOURCE_IMG_DIR_RELPATH,
        RESOURCE_FONT_DIR_RELPATH,
    ):
        os.makedirs(os.path.join(project_dir, rel_dir.replace("/", os.sep)), exist_ok=True)

    actions = {}
    project_relpath = project_file_relpath(app_name)
    actions[project_relpath] = _write_text_if_changed(
        os.path.join(project_dir, project_relpath),
        build_empty_project_xml(
            app_name,
            screen_width,
            screen_height,
            stored_sdk_root=stored_sdk_root,
            pages=normalized_pages,
        ),
    )
    actions[RESOURCE_CATALOG_RELPATH] = _write_text_if_changed(
        project_resource_catalog_path(project_dir),
        build_empty_resources_xml(),
    )
    for page_name in normalized_pages:
        relpath = project_layout_xml_relpath(page_name)
        actions[relpath] = _write_text_if_missing(
            os.path.join(project_dir, relpath.replace("/", os.sep)),
            build_empty_page_xml(page_name, screen_width, screen_height),
        )
    return actions


def apply_designer_project_scaffold(
    project_dir,
    app_name,
    screen_width=240,
    screen_height=320,
    *,
    overwrite=False,
    color_depth=16,
    circle_radius=None,
    extra_config_macros=None,
    refresh_designer_resource_config=None,
    remove_legacy_designer_files=False,
):
    """Apply the shared split scaffold policy used by Designer entry points."""
    if refresh_designer_resource_config is None:
        refresh_designer_resource_config = overwrite

    return sync_project_scaffold_sidecars(
        project_dir,
        app_name,
        screen_width,
        screen_height,
        color_depth=color_depth,
        circle_radius=circle_radius,
        extra_config_macros=extra_config_macros,
        refresh_user_wrappers=overwrite,
        refresh_designer_resource_config=refresh_designer_resource_config,
        remove_legacy_designer_files=remove_legacy_designer_files,
    )


def _prepare_project_save(
    project,
    project_dir,
    *,
    sdk_root=None,
    before_save=None,
):
    """Normalize a save target, bind project storage, and run an optional save hook."""
    project_dir = os.path.normpath(project_dir)
    os.makedirs(project_dir, exist_ok=True)
    bind_project_storage(project, project_dir, sdk_root=sdk_root)
    if callable(before_save):
        before_save(project_dir)
    return project_dir


def save_project_with_designer_scaffold(
    project,
    project_dir,
    *,
    sdk_root=None,
    before_save=None,
    overwrite=False,
    color_depth=16,
    circle_radius=None,
    extra_config_macros=None,
    refresh_designer_resource_config=None,
    remove_legacy_designer_files=False,
):
    """Apply the shared Designer sidecar scaffold and save a project model."""
    project_dir = _prepare_project_save(
        project,
        project_dir,
        sdk_root=sdk_root,
        before_save=before_save,
    )
    actions = apply_designer_project_scaffold(
        project_dir,
        project.app_name,
        project.screen_width,
        project.screen_height,
        overwrite=overwrite,
        color_depth=color_depth,
        circle_radius=circle_radius,
        extra_config_macros=extra_config_macros,
        refresh_designer_resource_config=refresh_designer_resource_config,
        remove_legacy_designer_files=remove_legacy_designer_files,
    )
    project.save(project_dir)
    return actions


def materialize_project_codegen_outputs(
    project,
    project_dir,
    *,
    backup=True,
    extra_files=None,
    newline=None,
    backup_existing=False,
    before_materialize=None,
):
    """Materialize project codegen outputs with an optional pre-write hook."""
    if callable(before_materialize):
        before_materialize(project_dir)

    from ..generator.code_generator import materialize_project_codegen

    return materialize_project_codegen(
        project,
        project_dir,
        backup=backup,
        extra_files=extra_files,
        newline=newline,
        backup_existing=backup_existing,
    )


def prepare_project_codegen_outputs(
    project,
    project_dir,
    *,
    backup=True,
    before_prepare=None,
    cleanup_legacy=False,
    backup_existing=False,
):
    """Prepare project codegen outputs with optional pre-prepare and cleanup hooks."""
    if callable(before_prepare):
        before_prepare(project_dir)

    from ..generator.code_generator import prepare_generated_project_files

    prepared = prepare_generated_project_files(
        project,
        project_dir,
        backup=backup,
    )
    if cleanup_legacy:
        cleanup_legacy_designer_codegen_files(
            project_dir,
            prepared.all_generated_files,
            backup_existing=backup_existing,
            remove_stale_strings=not project.string_catalog.has_strings,
        )
    return prepared


def save_project_and_materialize_codegen(
    project,
    project_dir,
    *,
    sdk_root=None,
    before_save=None,
    overwrite=False,
    color_depth=16,
    circle_radius=None,
    extra_config_macros=None,
    refresh_designer_resource_config=None,
    remove_legacy_designer_files=False,
    backup=True,
    extra_files=None,
    newline=None,
    backup_existing=False,
    before_materialize=None,
):
    """Save a project with the shared scaffold policy, then materialize codegen outputs."""
    save_project_with_designer_scaffold(
        project,
        project_dir,
        sdk_root=sdk_root,
        before_save=before_save,
        overwrite=overwrite,
        color_depth=color_depth,
        circle_radius=circle_radius,
        extra_config_macros=extra_config_macros,
        refresh_designer_resource_config=refresh_designer_resource_config,
        remove_legacy_designer_files=remove_legacy_designer_files,
    )
    return materialize_project_codegen_outputs(
        project,
        project_dir,
        backup=backup,
        extra_files=extra_files,
        newline=newline,
        backup_existing=backup_existing,
        before_materialize=before_materialize,
    )


def save_project_model(
    project,
    project_dir,
    *,
    sdk_root=None,
    before_save=None,
    with_designer_scaffold=False,
    overwrite_scaffold=False,
    color_depth=16,
    circle_radius=None,
    extra_config_macros=None,
    refresh_designer_resource_config=None,
    remove_legacy_designer_files=False,
):
    """Save a project model with optional Designer scaffold sidecars."""
    if with_designer_scaffold:
        return save_project_with_designer_scaffold(
            project,
            project_dir,
            sdk_root=sdk_root,
            before_save=before_save,
            overwrite=overwrite_scaffold,
            color_depth=color_depth,
            circle_radius=circle_radius,
            extra_config_macros=extra_config_macros,
            refresh_designer_resource_config=refresh_designer_resource_config,
            remove_legacy_designer_files=remove_legacy_designer_files,
        )
    project_dir = _prepare_project_save(
        project,
        project_dir,
        sdk_root=sdk_root,
        before_save=before_save,
    )
    project.save(project_dir)
    return {}


def save_empty_project_with_designer_scaffold(
    app_name,
    project_dir,
    screen_width=240,
    screen_height=320,
    *,
    sdk_root="",
    pages=None,
    project_customizer=None,
    overwrite_scaffold=False,
    color_depth=16,
    circle_radius=None,
    extra_config_macros=None,
    refresh_designer_resource_config=None,
    remove_legacy_designer_files=False,
):
    """Build and save an empty project model with the shared Designer scaffold policy."""
    project = build_empty_project_model(
        app_name,
        screen_width,
        screen_height,
        sdk_root=sdk_root,
        project_dir=project_dir,
        pages=pages,
    )
    if callable(project_customizer):
        project_customizer(project)
    save_project_model(
        project,
        project_dir,
        with_designer_scaffold=True,
        overwrite_scaffold=overwrite_scaffold,
        color_depth=color_depth,
        circle_radius=circle_radius,
        extra_config_macros=extra_config_macros,
        refresh_designer_resource_config=refresh_designer_resource_config,
        remove_legacy_designer_files=remove_legacy_designer_files,
    )
    return project


def scaffold_designer_project(
    project_dir,
    app_name,
    screen_width=240,
    screen_height=320,
    *,
    stored_sdk_root="",
    pages=None,
    overwrite=False,
    color_depth=16,
    circle_radius=None,
    extra_config_macros=None,
    refresh_designer_resource_config=None,
    remove_legacy_designer_files=False,
):
    """Apply the complete shared Designer project scaffold to a directory."""
    actions = apply_designer_project_scaffold(
        project_dir,
        app_name,
        screen_width,
        screen_height,
        overwrite=overwrite,
        color_depth=color_depth,
        circle_radius=circle_radius,
        extra_config_macros=extra_config_macros,
        refresh_designer_resource_config=refresh_designer_resource_config,
        remove_legacy_designer_files=remove_legacy_designer_files,
    )
    actions.update(
        sync_project_scaffold_core_files(
            project_dir,
            app_name,
            screen_width,
            screen_height,
            stored_sdk_root=stored_sdk_root,
            pages=pages,
        )
    )
    return actions


def scaffold_designer_project_with_sdk_root(
    project_dir,
    app_name,
    sdk_root,
    screen_width=240,
    screen_height=320,
    *,
    pages=None,
    overwrite=False,
    color_depth=16,
    circle_radius=None,
    extra_config_macros=None,
    refresh_designer_resource_config=None,
    remove_legacy_designer_files=False,
):
    """Apply the complete shared Designer scaffold using a relative stored SDK root."""
    from ..model.workspace import serialize_sdk_root

    return scaffold_designer_project(
        project_dir,
        app_name,
        screen_width,
        screen_height,
        stored_sdk_root=serialize_sdk_root(project_dir, sdk_root),
        pages=pages,
        overwrite=overwrite,
        color_depth=color_depth,
        circle_radius=circle_radius,
        extra_config_macros=extra_config_macros,
        refresh_designer_resource_config=refresh_designer_resource_config,
        remove_legacy_designer_files=remove_legacy_designer_files,
    )


def scaffold_conversion_project_with_sdk_root(
    project_dir,
    app_name,
    sdk_root,
    screen_width=240,
    screen_height=320,
    *,
    pages=None,
    color_depth=16,
):
    """Apply the shared conversion/import scaffold defaults using a relative SDK root."""
    return scaffold_designer_project_with_sdk_root(
        project_dir,
        app_name,
        sdk_root,
        screen_width,
        screen_height,
        pages=pages,
        **designer_conversion_scaffold_kwargs(
            screen_width,
            screen_height,
            color_depth=color_depth,
        ),
    )


def ensure_designer_project_scaffold_with_sdk_root(
    project_dir,
    app_name,
    sdk_root,
    screen_width=240,
    screen_height=320,
    **kwargs,
):
    """Create a Designer scaffold only when the target directory is missing."""
    project_dir = os.path.normpath(project_dir)
    if os.path.exists(project_dir):
        return False, {}

    actions = scaffold_designer_project_with_sdk_root(
        project_dir,
        app_name,
        sdk_root,
        screen_width,
        screen_height,
        **kwargs,
    )
    return True, actions


def ensure_conversion_project_scaffold_with_sdk_root(
    project_dir,
    app_name,
    sdk_root,
    screen_width=240,
    screen_height=320,
    *,
    color_depth=16,
):
    """Create a conversion/import scaffold only when the target directory is missing."""
    return ensure_designer_project_scaffold_with_sdk_root(
        project_dir,
        app_name,
        sdk_root,
        screen_width,
        screen_height,
        **designer_conversion_scaffold_kwargs(
            screen_width,
            screen_height,
            color_depth=color_depth,
        ),
    )
