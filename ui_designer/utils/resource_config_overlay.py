"""Helpers for split designer/user resource config ownership.

Designer-managed widget/resource discovery writes to
``resource/src/.designer/app_resource_config_designer.json``. User-authored
overlay entries live in ``resource/src/app_resource_config.json``. Resource
generation consumes the merged effective view of both files.
"""

from __future__ import annotations

import json
import os
from collections import OrderedDict


APP_RESOURCE_CONFIG_FILENAME = "app_resource_config.json"
APP_RESOURCE_CONFIG_DESIGNER_FILENAME = "app_resource_config_designer.json"
APP_RESOURCE_CONFIG_MERGED_FILENAME = ".app_resource_config_merged.json"
DESIGNER_RESOURCE_DIRNAME = ".designer"

_RESOURCE_LIST_KEYS = ("img", "font", "mp4")


def make_empty_resource_config() -> dict:
    """Return the default resource config structure."""
    return {
        "img": [],
        "font": [],
        "mp4": [],
    }


def make_empty_resource_config_content() -> str:
    """Return the default user-overlay resource config JSON content."""
    return json.dumps(make_empty_resource_config(), indent=4, ensure_ascii=False) + "\n"


def ensure_resource_config_file(path: str) -> bool:
    """Create the default user-overlay resource config file when missing."""
    if os.path.exists(path):
        return False
    parent_dir = os.path.dirname(path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(make_empty_resource_config_content())
    return True


def load_resource_config(path: str) -> dict | None:
    """Load a JSON/JSON5-like resource config file."""
    if not path or not os.path.isfile(path):
        return None

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    return parse_resource_config_content(content)


def parse_resource_config_content(content: str) -> dict | None:
    """Parse JSON/JSON5-like resource config text."""
    try:
        import json5

        data = json5.loads(content)
    except Exception:
        cleaned = content
        cleaned = _strip_json_comments(cleaned)
        cleaned = _strip_trailing_commas(cleaned)
        data = json.loads(cleaned)

    return data if isinstance(data, dict) else None


def designer_resource_dir(src_dir: str) -> str:
    return os.path.join(src_dir, DESIGNER_RESOURCE_DIRNAME)


def designer_resource_relpath(name: str) -> str:
    return f"{DESIGNER_RESOURCE_DIRNAME}/{name}".replace("\\", "/")


def user_resource_config_path(src_dir: str) -> str:
    return os.path.join(src_dir, APP_RESOURCE_CONFIG_FILENAME)


def designer_resource_config_path(src_dir: str) -> str:
    return os.path.join(designer_resource_dir(src_dir), APP_RESOURCE_CONFIG_DESIGNER_FILENAME)


def merged_resource_config_path(src_dir: str) -> str:
    return os.path.join(designer_resource_dir(src_dir), APP_RESOURCE_CONFIG_MERGED_FILENAME)


def designer_generated_text_relpath(name: str) -> str:
    return designer_resource_relpath(name)


def is_designer_resource_path(path: str) -> bool:
    normalized = str(path or "").replace("\\", "/").strip()
    if not normalized:
        return False
    basename = os.path.basename(normalized)
    if normalized == DESIGNER_RESOURCE_DIRNAME:
        return True
    if normalized.startswith(f"{DESIGNER_RESOURCE_DIRNAME}/"):
        return True
    if basename in {APP_RESOURCE_CONFIG_DESIGNER_FILENAME, APP_RESOURCE_CONFIG_MERGED_FILENAME}:
        return True
    return basename.startswith("_generated_text_")


def merge_resource_configs(designer_config: dict | None, user_config: dict | None) -> dict:
    """Merge designer-generated and user-authored resource configs."""
    merged = make_empty_resource_config()
    designer_config = designer_config or {}
    user_config = user_config or {}

    for key in _RESOURCE_LIST_KEYS:
        merged[key] = _merge_resource_section(
            key,
            designer_config.get(key, []),
            user_config.get(key, []),
        )

    passthrough_keys = set(designer_config.keys()) | set(user_config.keys())
    passthrough_keys.difference_update(_RESOURCE_LIST_KEYS)
    for key in sorted(passthrough_keys):
        if key in user_config:
            merged[key] = user_config[key]
        else:
            merged[key] = designer_config[key]

    return merged


def load_merged_resource_config(src_dir: str) -> dict | None:
    """Load and merge split config files from ``resource/src``."""
    user_path = user_resource_config_path(src_dir)
    designer_config = load_resource_config(designer_resource_config_path(src_dir))
    user_config = load_resource_config(user_path)
    if designer_config is None and user_config is None:
        return None
    return merge_resource_configs(designer_config, user_config)


def _strip_json_comments(content: str) -> str:
    result_chars = []
    in_string = False
    escaped = False
    i = 0
    length = len(content)

    while i < length:
        ch = content[i]
        nxt = content[i + 1] if i + 1 < length else ""

        if in_string:
            result_chars.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            i += 1
            continue

        if ch == '"':
            in_string = True
            result_chars.append(ch)
            i += 1
            continue

        if ch == "/" and nxt == "/":
            i += 2
            while i < length and content[i] not in "\r\n":
                i += 1
            continue

        if ch == "/" and nxt == "*":
            i += 2
            while i + 1 < length and not (content[i] == "*" and content[i + 1] == "/"):
                i += 1
            i += 2
            continue

        result_chars.append(ch)
        i += 1

    return "".join(result_chars)


def _strip_trailing_commas(content: str) -> str:
    result_chars = []
    in_string = False
    escaped = False
    i = 0
    length = len(content)

    while i < length:
        ch = content[i]

        if in_string:
            result_chars.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            i += 1
            continue

        if ch == '"':
            in_string = True
            result_chars.append(ch)
            i += 1
            continue

        if ch == ",":
            j = i + 1
            while j < length and content[j] in " \t\r\n":
                j += 1
            if j < length and content[j] in "]}":
                i += 1
                continue

        result_chars.append(ch)
        i += 1

    return "".join(result_chars)


def _merge_resource_section(section: str, designer_entries, user_entries):
    ordered = OrderedDict()

    for entry in designer_entries or []:
        if not isinstance(entry, dict):
            continue
        ordered[_resource_identity(section, entry)] = dict(entry)

    for entry in user_entries or []:
        if not isinstance(entry, dict):
            continue
        identity = _resource_identity(section, entry)
        existing = ordered.get(identity)
        if existing is None:
            ordered[identity] = dict(entry)
            continue
        ordered[identity] = _merge_resource_entry(section, existing, entry)

    return list(ordered.values())


def _merge_resource_entry(section: str, designer_entry: dict, user_entry: dict) -> dict:
    merged = dict(designer_entry)
    for key, value in user_entry.items():
        if section == "font" and key == "text":
            merged["text"] = _merge_font_text_value(designer_entry.get("text"), value)
            continue
        merged[key] = value
    return merged


def _merge_font_text_value(designer_value, user_value) -> str:
    values = []
    for raw in (designer_value, user_value):
        for item in str(raw or "").split(","):
            normalized = item.strip()
            if normalized and normalized not in values:
                values.append(normalized)
    return ",".join(values)


def _resource_identity(section: str, entry: dict) -> tuple:
    if section == "img":
        return (
            "img",
            _norm(entry.get("name")),
            _norm(entry.get("file")),
            _norm(entry.get("format", "rgb565")),
            _norm(entry.get("alpha", "4")),
            _norm(entry.get("dim")),
            _norm(entry.get("rot")),
        )
    if section == "font":
        return (
            "font",
            _norm(entry.get("name")),
            _norm(entry.get("file")),
            _norm(entry.get("pixelsize", "16")),
            _norm(entry.get("fontbitsize", "4")),
            _norm(entry.get("weight")),
        )
    if section == "mp4":
        return (
            "mp4",
            _norm(entry.get("name")),
            _norm(entry.get("file")),
            _norm(entry.get("fps", "10")),
            _norm(entry.get("width", "0")),
            _norm(entry.get("height", "0")),
            _norm(entry.get("format", "rgb565")),
            _norm(entry.get("alpha", "0")),
        )
    return (section, _norm(json.dumps(entry, sort_keys=True, ensure_ascii=False)))


def _norm(value) -> str:
    return str(value or "").strip()
