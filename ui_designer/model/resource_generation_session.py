"""Standalone resource-generation session helpers for the Designer UI."""

from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from shutil import which

from .workspace import (
    is_valid_sdk_root,
    normalize_path,
    sdk_resource_generator_path,
)
from ..utils.resource_config_overlay import (
    APP_RESOURCE_CONFIG_FILENAME,
    designer_resource_config_path,
    is_designer_resource_path,
    load_resource_config,
    make_empty_resource_config,
    merge_resource_configs,
    merged_resource_config_path,
    parse_resource_config_content,
)


KNOWN_RESOURCE_SECTIONS = ("img", "font", "mp4")

_IMG_FORMAT_CHOICES = ("rgb565", "rgb32", "gray8", "alpha", "all")
_IMG_ALPHA_CHOICES = ("0", "1", "2", "4", "8", "all")
_IMG_EXTERNAL_CHOICES = ("0", "1", "all")
_IMG_COMPRESS_CHOICES = ("none", "qoi", "rle")
_IMG_SWAP_CHOICES = ("0", "1")
_FONT_BITS_CHOICES = ("1", "2", "4", "8", "all")
_MP4_COMPRESS_CHOICES = ("none", "qoi", "rle")


@dataclass(frozen=True)
class ResourceFieldSpec:
    name: str
    label: str
    editor: str = "line"
    choices: tuple[str, ...] = ()
    placeholder: str = ""
    required: bool = False
    file_filter: str = "All files (*)"
    browse_mode: str = "file"


@dataclass(frozen=True)
class ResourceSectionSpec:
    name: str
    label: str
    fields: tuple[ResourceFieldSpec, ...]


RESOURCE_SECTION_SPECS: dict[str, ResourceSectionSpec] = {
    "img": ResourceSectionSpec(
        name="img",
        label="Images",
        fields=(
            ResourceFieldSpec("file", "File", required=True, file_filter="Image files (*.png *.bmp *.jpg *.jpeg *.gif *.webp);;All files (*)"),
            ResourceFieldSpec("name", "Name"),
            ResourceFieldSpec("format", "Format", editor="combo", choices=_IMG_FORMAT_CHOICES),
            ResourceFieldSpec("alpha", "Alpha", editor="combo", choices=_IMG_ALPHA_CHOICES),
            ResourceFieldSpec("external", "External", editor="combo", choices=_IMG_EXTERNAL_CHOICES),
            ResourceFieldSpec("dim", "Dim", placeholder="e.g. 120,120"),
            ResourceFieldSpec("rot", "Rotate", placeholder="e.g. 90"),
            ResourceFieldSpec("swap", "Swap", editor="combo", choices=_IMG_SWAP_CHOICES),
            ResourceFieldSpec("compress", "Compress", editor="combo", choices=_IMG_COMPRESS_CHOICES),
            ResourceFieldSpec("bg", "Bg"),
        ),
    ),
    "font": ResourceSectionSpec(
        name="font",
        label="Fonts",
        fields=(
            ResourceFieldSpec("file", "File", required=True, file_filter="Font files (*.ttf *.otf);;All files (*)"),
            ResourceFieldSpec("name", "Name"),
            ResourceFieldSpec("pixelsize", "Pixel Size", placeholder="4-48 or all"),
            ResourceFieldSpec("fontbitsize", "Bit Size", editor="combo", choices=_FONT_BITS_CHOICES),
            ResourceFieldSpec("external", "External", editor="combo", choices=_IMG_EXTERNAL_CHOICES),
            ResourceFieldSpec("text", "Text", required=True, file_filter="Text files (*.txt);;All files (*)"),
            ResourceFieldSpec("weight", "Weight", placeholder="e.g. 500"),
        ),
    ),
    "mp4": ResourceSectionSpec(
        name="mp4",
        label="MP4",
        fields=(
            ResourceFieldSpec("file", "File", required=True, file_filter="Video files (*.mp4 *.avi *.mov *.mkv);;All files (*)"),
            ResourceFieldSpec("name", "Name"),
            ResourceFieldSpec("fps", "FPS", placeholder="e.g. 10"),
            ResourceFieldSpec("width", "Width", placeholder="e.g. 240"),
            ResourceFieldSpec("height", "Height", placeholder="e.g. 240"),
            ResourceFieldSpec("format", "Format", editor="combo", choices=_IMG_FORMAT_CHOICES),
            ResourceFieldSpec("alpha", "Alpha", editor="combo", choices=_IMG_ALPHA_CHOICES),
            ResourceFieldSpec("external", "External", editor="combo", choices=_IMG_EXTERNAL_CHOICES),
            ResourceFieldSpec("compress", "Compress", editor="combo", choices=_MP4_COMPRESS_CHOICES),
        ),
    ),
}


@dataclass
class GenerationPaths:
    config_path: str = ""
    source_dir: str = ""
    workspace_dir: str = ""
    bin_output_dir: str = ""

    def normalized(self) -> "GenerationPaths":
        return GenerationPaths(
            config_path=normalize_path(self.config_path),
            source_dir=normalize_path(self.source_dir),
            workspace_dir=normalize_path(self.workspace_dir),
            bin_output_dir=normalize_path(self.bin_output_dir),
        )


@dataclass
class ResourceGenerationValidationIssue:
    severity: str
    code: str
    message: str
    section: str = ""
    entry_index: int = -1
    field: str = ""


@dataclass
class ResourceGenerationResult:
    success: bool
    command: list[str] = field(default_factory=list)
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""
    staged_config_path: str = ""
    issues: list[ResourceGenerationValidationIssue] = field(default_factory=list)


def infer_generation_paths(config_path: str, *, source_dir: str = "", workspace_dir: str = "", bin_output_dir: str = "") -> GenerationPaths:
    config_path = normalize_path(config_path)
    source_dir = normalize_path(source_dir)
    workspace_dir = normalize_path(workspace_dir)
    bin_output_dir = normalize_path(bin_output_dir)

    if not source_dir and config_path:
        source_dir = normalize_path(os.path.dirname(config_path))

    if not workspace_dir and source_dir:
        if os.path.basename(source_dir).lower() == "src":
            workspace_dir = normalize_path(os.path.dirname(source_dir))
        else:
            workspace_dir = normalize_path(os.path.join(source_dir, ".resource_workspace"))

    if not bin_output_dir and workspace_dir:
        bin_output_dir = workspace_dir

    return GenerationPaths(
        config_path=config_path,
        source_dir=source_dir,
        workspace_dir=workspace_dir,
        bin_output_dir=bin_output_dir,
    )


def _require_user_config_path(config_path: str) -> str:
    normalized = normalize_path(config_path)
    if not normalized:
        return ""
    if not is_designer_resource_path(normalized):
        return normalized

    hint = ""
    parent_dir = os.path.basename(os.path.dirname(normalized))
    if parent_dir == ".designer":
        source_dir = os.path.dirname(os.path.dirname(normalized))
        user_config = normalize_path(os.path.join(source_dir, APP_RESOURCE_CONFIG_FILENAME))
        if user_config:
            hint = f" Use the user overlay instead: {user_config}"

    raise ValueError(f"'{normalized}' is Designer-managed and cannot be edited directly.{hint}")


def default_entry_for_section(section: str) -> dict:
    if section == "img":
        return {
            "file": "",
            "format": "rgb565",
            "alpha": "4",
            "external": "0",
            "swap": "0",
            "compress": "none",
        }
    if section == "font":
        return {
            "file": "",
            "pixelsize": "16",
            "fontbitsize": "4",
            "external": "0",
            "text": "",
        }
    if section == "mp4":
        return {
            "file": "",
            "fps": 10,
            "width": 0,
            "height": 0,
            "format": "rgb565",
            "alpha": "0",
            "external": "0",
            "compress": "none",
        }
    return {}


def section_entry_label(section: str, entry: dict, index: int) -> str:
    entry = entry if isinstance(entry, dict) else {}
    name = str(entry.get("name", "") or "").strip()
    file_name = str(entry.get("file", "") or "").strip()
    primary = name or file_name or f"{section}_{index + 1}"
    return primary


class ResourceGenerationSession:
    """Manage standalone resource-generation editing state."""

    def __init__(self, sdk_root: str = ""):
        self.sdk_root = normalize_path(sdk_root)
        self.paths = GenerationPaths()
        self.user_data = _ordered_user_config(make_empty_resource_config())

    def reset(self, paths: GenerationPaths | None = None, user_data: dict | None = None):
        self.paths = (paths or GenerationPaths()).normalized()
        self.user_data = _ordered_user_config(user_data)

    def set_sdk_root(self, sdk_root: str):
        self.sdk_root = normalize_path(sdk_root)

    def set_paths(self, paths: GenerationPaths):
        self.paths = (paths or GenerationPaths()).normalized()

    def update_path(self, field_name: str, value: str):
        if not hasattr(self.paths, field_name):
            return
        setattr(self.paths, field_name, normalize_path(value))

    def load_from_file(
        self,
        config_path: str,
        *,
        source_dir: str = "",
        workspace_dir: str = "",
        bin_output_dir: str = "",
    ):
        resolved_paths = infer_generation_paths(
            config_path,
            source_dir=source_dir,
            workspace_dir=workspace_dir,
            bin_output_dir=bin_output_dir,
        )
        resolved_paths.config_path = _require_user_config_path(resolved_paths.config_path)
        data = load_resource_config(resolved_paths.config_path) if resolved_paths.config_path else None
        if data is None:
            raise FileNotFoundError(f"Resource config not found: {config_path}")
        self.reset(resolved_paths, data)

    def apply_raw_json_text(self, content: str):
        data = parse_resource_config_content(content or "")
        if data is None:
            raise ValueError("Resource config must be a JSON object.")
        self.user_data = _ordered_user_config(data)

    def to_user_json_text(self) -> str:
        return json.dumps(_ordered_user_config(self.user_data), indent=4, ensure_ascii=False) + "\n"

    def effective_overlay_path(self) -> str:
        if not self.paths.source_dir:
            return ""
        return designer_resource_config_path(self.paths.source_dir)

    def load_overlay_data(self) -> dict | None:
        overlay_path = self.effective_overlay_path()
        if not overlay_path:
            return None
        return load_resource_config(overlay_path)

    def merged_config(self) -> dict:
        return merge_resource_configs(self.load_overlay_data(), _ordered_user_config(self.user_data))

    def merged_json_text(self) -> str:
        return json.dumps(self.merged_config(), indent=4, ensure_ascii=False) + "\n"

    def save_user_config(self, path: str = "") -> str:
        target_path = _require_user_config_path(path or self.paths.config_path)
        if not target_path:
            raise ValueError("Config path is empty.")
        parent_dir = os.path.dirname(target_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        with open(target_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(self.to_user_json_text())
        self.paths.config_path = target_path
        if not self.paths.source_dir:
            inferred = infer_generation_paths(target_path)
            self.paths.source_dir = inferred.source_dir
            if not self.paths.workspace_dir:
                self.paths.workspace_dir = inferred.workspace_dir
            if not self.paths.bin_output_dir:
                self.paths.bin_output_dir = inferred.bin_output_dir
        return target_path

    def section_entries(self, section: str) -> list[dict]:
        entries = self.user_data.get(section)
        if isinstance(entries, list):
            return entries
        fixed_entries: list[dict] = []
        self.user_data[section] = fixed_entries
        return fixed_entries

    def add_entry(self, section: str, entry: dict | None = None) -> int:
        entries = self.section_entries(section)
        entries.append(copy.deepcopy(entry or default_entry_for_section(section)))
        return len(entries) - 1

    def remove_entry(self, section: str, index: int):
        entries = self.section_entries(section)
        if 0 <= index < len(entries):
            entries.pop(index)

    def update_entry_value(self, section: str, index: int, field_name: str, value):
        entries = self.section_entries(section)
        if not (0 <= index < len(entries)):
            return
        entry = entries[index]
        if not isinstance(entry, dict):
            entry = {}
            entries[index] = entry
        normalized = _normalize_entry_value(field_name, value)
        if normalized in (None, ""):
            entry.pop(field_name, None)
            return
        entry[field_name] = normalized

    def validation_issues(self, *, for_generation: bool = False) -> list[ResourceGenerationValidationIssue]:
        issues: list[ResourceGenerationValidationIssue] = []
        data = self.merged_config() if for_generation else _ordered_user_config(self.user_data)
        generator_script = sdk_resource_generator_path(self.sdk_root) if self.sdk_root else ""

        if for_generation:
            if not is_valid_sdk_root(self.sdk_root):
                issues.append(ResourceGenerationValidationIssue("error", "sdk_root", "A valid EmbeddedGUI SDK root is required for generation."))
            elif not os.path.isfile(generator_script):
                issues.append(
                    ResourceGenerationValidationIssue(
                        "error",
                        "generator_script_missing",
                        f"Missing SDK resource generator: {generator_script}",
                    )
                )
            if not self.paths.source_dir:
                issues.append(ResourceGenerationValidationIssue("error", "source_dir", "Source directory is required for generation."))
            elif not os.path.isdir(self.paths.source_dir):
                issues.append(ResourceGenerationValidationIssue("error", "source_dir_missing", f"Source directory does not exist: {self.paths.source_dir}"))
            elif is_designer_resource_path(self.paths.source_dir):
                issues.append(
                    ResourceGenerationValidationIssue(
                        "error",
                        "source_dir_reserved",
                        f"Source directory cannot be a Designer-managed path: {self.paths.source_dir}",
                    )
                )
            if not self.paths.workspace_dir:
                issues.append(ResourceGenerationValidationIssue("error", "workspace_dir", "Workspace directory is required for generation."))
            if not self.paths.bin_output_dir:
                issues.append(ResourceGenerationValidationIssue("error", "bin_output_dir", "Bin output directory is required for generation."))

        if self.paths.source_dir and self.paths.workspace_dir and self.paths.source_dir == self.paths.workspace_dir:
            issues.append(
                ResourceGenerationValidationIssue(
                    "error",
                    "workspace_overlap",
                    "Workspace directory cannot be the same as the source directory.",
                )
            )

        build_in_dir = _build_in_dir_for_generator(generator_script)
        for section in KNOWN_RESOURCE_SECTIONS:
            entries = data.get(section, [])
            if not isinstance(entries, list):
                issues.append(ResourceGenerationValidationIssue("error", "section_type", f"Section '{section}' must be a list.", section=section))
                continue
            for index, entry in enumerate(entries):
                issues.extend(
                    _validate_entry(
                        section,
                        index,
                        entry,
                        source_dir=self.paths.source_dir,
                        build_in_dir=build_in_dir,
                        for_generation=for_generation,
                    )
                )

        has_mp4 = bool(data.get("mp4"))
        if for_generation and has_mp4 and which("ffmpeg") is None:
            issues.append(
                ResourceGenerationValidationIssue(
                    "error",
                    "ffmpeg_missing",
                    "MP4 generation requires ffmpeg to be available in PATH.",
                    section="mp4",
                )
            )

        return issues

    def stage_workspace(self) -> str:
        workspace_dir = self.paths.workspace_dir
        source_dir = self.paths.source_dir
        if not workspace_dir:
            raise ValueError("Workspace directory is empty.")

        target_src_dir = os.path.join(workspace_dir, "src")
        source_dir = normalize_path(source_dir)
        target_src_dir = normalize_path(target_src_dir)
        workspace_dir = normalize_path(workspace_dir)

        if source_dir and source_dir != target_src_dir:
            if os.path.isdir(target_src_dir):
                shutil.rmtree(target_src_dir)
            os.makedirs(target_src_dir, exist_ok=True)
            _copy_source_tree(source_dir, target_src_dir, skip_roots=[workspace_dir])
        else:
            os.makedirs(target_src_dir, exist_ok=True)

        staged_config_path = os.path.join(target_src_dir, APP_RESOURCE_CONFIG_FILENAME)
        with open(staged_config_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(self.to_user_json_text())
        return staged_config_path

    def stage_generation_config(self) -> str:
        workspace_dir = self.paths.workspace_dir
        if not workspace_dir:
            raise ValueError("Workspace directory is empty.")

        target_src_dir = normalize_path(os.path.join(workspace_dir, "src"))
        os.makedirs(target_src_dir, exist_ok=True)
        staged_config_path = merged_resource_config_path(target_src_dir)
        os.makedirs(os.path.dirname(staged_config_path), exist_ok=True)
        staged_config = _expand_font_text_entries_for_generation(self.merged_config())
        with open(staged_config_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(staged_config, f, indent=4, ensure_ascii=False)
            f.write("\n")
        return staged_config_path

    def run_generation(self, *, timeout_seconds: int = 300) -> ResourceGenerationResult:
        issues = self.validation_issues(for_generation=True)
        blocking = [issue for issue in issues if issue.severity == "error"]
        if blocking:
            return ResourceGenerationResult(
                success=False,
                returncode=-1,
                issues=issues,
            )

        self.stage_workspace()
        staged_config_path = self.stage_generation_config()
        generator_script = _resolved_existing_path(sdk_resource_generator_path(self.sdk_root))
        command = [
            sys.executable,
            generator_script,
            "-r",
            self.paths.workspace_dir,
            "-o",
            self.paths.bin_output_dir,
            "-f",
            "true",
            "--config",
            staged_config_path,
        ]
        try:
            try:
                completed = self._run_generator_subprocess(command, timeout_seconds=timeout_seconds)
            except subprocess.TimeoutExpired as exc:
                return ResourceGenerationResult(
                    success=False,
                    command=command,
                    returncode=-1,
                    stdout=str(exc.stdout or ""),
                    stderr=str(exc.stderr or ""),
                    staged_config_path=staged_config_path,
                    issues=issues + [
                        ResourceGenerationValidationIssue(
                            "error",
                            "generation_timeout",
                            f"Resource generation timed out after {timeout_seconds} seconds.",
                        )
                    ],
                )
            except Exception as exc:
                return ResourceGenerationResult(
                    success=False,
                    command=command,
                    returncode=-1,
                    stdout="",
                    stderr=str(exc),
                    staged_config_path=staged_config_path,
                    issues=issues + [
                        ResourceGenerationValidationIssue(
                            "error",
                            "generation_failed",
                            f"Failed to run resource generator: {exc}",
                        )
                    ],
                )

            return ResourceGenerationResult(
                success=completed.returncode == 0,
                command=command,
                returncode=completed.returncode,
                stdout=completed.stdout or "",
                stderr=completed.stderr or "",
                staged_config_path=staged_config_path,
                issues=issues,
            )
        finally:
            try:
                os.remove(staged_config_path)
            except OSError:
                pass

    def _run_generator_subprocess(self, command: list[str], *, timeout_seconds: int):
        preferred_cwd = _resolved_existing_path(self.sdk_root) or None
        try:
            return subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                cwd=preferred_cwd,
            )
        except OSError as exc:
            if not preferred_cwd:
                raise
            return subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                cwd=None,
            )


def _ordered_user_config(data: dict | None) -> dict:
    source = data if isinstance(data, dict) else {}
    ordered: dict = {}
    empty = make_empty_resource_config()
    for key in KNOWN_RESOURCE_SECTIONS:
        if key in source:
            ordered[key] = copy.deepcopy(source.get(key))
        else:
            ordered[key] = copy.deepcopy(empty.get(key, []))
    for key, value in source.items():
        if key in ordered:
            continue
        ordered[key] = copy.deepcopy(value)
    return ordered


def _split_text_items(value) -> list[str]:
    values = []
    for item in str(value or "").split(","):
        normalized = item.strip()
        if normalized and normalized not in values:
            values.append(normalized)
    return values


def _expand_font_text_entries_for_generation(data: dict | None) -> dict:
    expanded = copy.deepcopy(data if isinstance(data, dict) else {})
    font_entries = []
    for entry in expanded.get("font", []) or []:
        if not isinstance(entry, dict):
            font_entries.append(copy.deepcopy(entry))
            continue
        text_items = _split_text_items(entry.get("text"))
        if len(text_items) <= 1:
            font_entries.append(copy.deepcopy(entry))
            continue
        for text_item in text_items:
            cloned_entry = dict(entry)
            cloned_entry["text"] = text_item
            font_entries.append(cloned_entry)
    if "font" in expanded:
        expanded["font"] = font_entries
    return expanded


def _normalize_entry_value(field_name: str, value):
    if isinstance(value, str):
        value = value.strip()
    if value in (None, ""):
        return ""
    if field_name in {"fps", "width", "height", "weight"}:
        try:
            return int(str(value).strip())
        except Exception:
            return str(value).strip()
    if field_name == "rot":
        raw = str(value).strip()
        try:
            return int(raw) if "." not in raw else float(raw)
        except Exception:
            return raw
    return value


def _validate_entry(section: str, index: int, entry, *, source_dir: str, build_in_dir: str, for_generation: bool) -> list[ResourceGenerationValidationIssue]:
    issues: list[ResourceGenerationValidationIssue] = []
    if not isinstance(entry, dict):
        return [
            ResourceGenerationValidationIssue(
                "error",
                "entry_type",
                f"Entry {index + 1} in '{section}' must be an object.",
                section=section,
                entry_index=index,
            )
        ]

    def add_issue(code: str, message: str, field: str = "", severity: str = "error"):
        issues.append(
            ResourceGenerationValidationIssue(
                severity,
                code,
                message,
                section=section,
                entry_index=index,
                field=field,
            )
        )

    if section == "img":
        _require_non_empty(entry, "file", add_issue)
        _validate_choice(entry, "format", _IMG_FORMAT_CHOICES, add_issue)
        _validate_choice(entry, "alpha", _IMG_ALPHA_CHOICES, add_issue)
        _validate_choice(entry, "external", _IMG_EXTERNAL_CHOICES, add_issue)
        _validate_choice(entry, "swap", _IMG_SWAP_CHOICES, add_issue)
        _validate_choice(entry, "compress", _IMG_COMPRESS_CHOICES, add_issue)
        _validate_dim(entry, "dim", add_issue)
        _validate_float_like(entry, "rot", add_issue)
        if for_generation:
            _validate_relative_source_file(entry, "file", source_dir, add_issue)

    elif section == "font":
        _require_non_empty(entry, "file", add_issue)
        _require_non_empty(entry, "text", add_issue)
        _validate_numeric_or_all(entry, "pixelsize", add_issue)
        _validate_choice(entry, "fontbitsize", _FONT_BITS_CHOICES, add_issue)
        _validate_choice(entry, "external", _IMG_EXTERNAL_CHOICES, add_issue)
        _validate_int_like(entry, "weight", add_issue)
        if for_generation:
            _validate_font_file(entry, "file", source_dir, build_in_dir, add_issue)
            _validate_multi_relative_source_file(entry, "text", source_dir, add_issue)

    elif section == "mp4":
        _require_non_empty(entry, "file", add_issue)
        _validate_int_like(entry, "fps", add_issue)
        _validate_int_like(entry, "width", add_issue)
        _validate_int_like(entry, "height", add_issue)
        _validate_choice(entry, "format", _IMG_FORMAT_CHOICES, add_issue)
        _validate_choice(entry, "alpha", _IMG_ALPHA_CHOICES, add_issue)
        _validate_choice(entry, "external", _IMG_EXTERNAL_CHOICES, add_issue)
        _validate_choice(entry, "compress", _MP4_COMPRESS_CHOICES, add_issue)
        if for_generation:
            _validate_relative_source_file(entry, "file", source_dir, add_issue)

    return issues


def _require_non_empty(entry: dict, field_name: str, add_issue):
    value = str(entry.get(field_name, "") or "").strip()
    if not value:
        add_issue("required", f"Field '{field_name}' is required.", field=field_name)


def _validate_choice(entry: dict, field_name: str, choices: tuple[str, ...], add_issue):
    if field_name not in entry:
        return
    value = str(entry.get(field_name, "") or "").strip()
    if not value:
        return
    if value not in choices:
        add_issue(
            "invalid_choice",
            f"Field '{field_name}' must be one of: {', '.join(choices)}.",
            field=field_name,
        )


def _validate_int_like(entry: dict, field_name: str, add_issue):
    if field_name not in entry:
        return
    raw = str(entry.get(field_name, "") or "").strip()
    if not raw:
        return
    try:
        int(raw)
    except Exception:
        add_issue("invalid_number", f"Field '{field_name}' must be an integer.", field=field_name)


def _validate_float_like(entry: dict, field_name: str, add_issue):
    if field_name not in entry:
        return
    raw = str(entry.get(field_name, "") or "").strip()
    if not raw:
        return
    try:
        float(raw)
    except Exception:
        add_issue("invalid_number", f"Field '{field_name}' must be numeric.", field=field_name)


def _validate_numeric_or_all(entry: dict, field_name: str, add_issue):
    if field_name not in entry:
        return
    raw = str(entry.get(field_name, "") or "").strip()
    if not raw or raw == "all":
        return
    try:
        int(raw)
    except Exception:
        add_issue("invalid_number", f"Field '{field_name}' must be an integer or 'all'.", field=field_name)


def _validate_dim(entry: dict, field_name: str, add_issue):
    if field_name not in entry:
        return
    raw = str(entry.get(field_name, "") or "").strip()
    if not raw:
        return
    parts = [part.strip() for part in raw.split(",")]
    if len(parts) != 2:
        add_issue("invalid_dim", f"Field '{field_name}' must look like 'width,height'.", field=field_name)
        return
    for part in parts:
        try:
            int(part)
        except Exception:
            add_issue("invalid_dim", f"Field '{field_name}' must contain integers.", field=field_name)
            return


def _validate_relative_source_file(entry: dict, field_name: str, source_dir: str, add_issue):
    raw = str(entry.get(field_name, "") or "").strip()
    if not raw:
        return
    if os.path.isabs(raw):
        add_issue(
            "absolute_path_unsupported",
            f"Field '{field_name}' must be relative to the source directory for this resource type.",
            field=field_name,
        )
        return
    if not source_dir:
        return
    target = normalize_path(os.path.join(source_dir, raw))
    if not os.path.exists(target):
        add_issue("missing_file", f"Missing source file: {raw}", field=field_name)


def _validate_multi_relative_source_file(entry: dict, field_name: str, source_dir: str, add_issue):
    raw = str(entry.get(field_name, "") or "").strip()
    if not raw:
        return
    for item in raw.split(","):
        path_item = item.strip()
        if not path_item:
            continue
        if os.path.isabs(path_item):
            add_issue(
                "absolute_path_unsupported",
                f"Field '{field_name}' must contain source-dir-relative paths.",
                field=field_name,
            )
            return
        if source_dir:
            target = normalize_path(os.path.join(source_dir, path_item))
            if not os.path.exists(target):
                add_issue("missing_file", f"Missing text file: {path_item}", field=field_name)


def _validate_font_file(entry: dict, field_name: str, source_dir: str, build_in_dir: str, add_issue):
    raw = str(entry.get(field_name, "") or "").strip()
    if not raw:
        return
    if os.path.isabs(raw):
        if not os.path.isfile(raw):
            add_issue("missing_file", f"Missing font file: {raw}", field=field_name)
        return
    normalized = raw.replace("\\", "/")
    if normalized.startswith("build_in/"):
        if not build_in_dir:
            add_issue("build_in_unavailable", "Cannot resolve build_in fonts without a valid SDK generator path.", field=field_name)
            return
        candidate = normalize_path(os.path.join(build_in_dir, normalized[len("build_in/"):]))
        if not os.path.isfile(candidate):
            add_issue("missing_file", f"Missing build_in font: {raw}", field=field_name)
        return
    if source_dir:
        candidate = normalize_path(os.path.join(source_dir, raw))
        if not os.path.isfile(candidate):
            add_issue("missing_file", f"Missing font file: {raw}", field=field_name)


def _build_in_dir_for_generator(generator_script: str) -> str:
    generator_script = normalize_path(generator_script)
    if not generator_script:
        return ""
    return normalize_path(os.path.join(os.path.dirname(generator_script), "build_in"))


def _resolved_existing_path(path: str) -> str:
    normalized = normalize_path(path)
    if not normalized:
        return ""
    if not os.path.exists(normalized):
        return normalized
    return normalize_path(os.path.realpath(normalized))


def _should_stage_designer_resource_path(source_dir: str, path: str) -> bool:
    normalized = normalize_path(path)
    if not normalized:
        return False
    rel_path = os.path.relpath(normalized, source_dir).replace("\\", "/")
    path_parts = [part for part in rel_path.split("/") if part and part != "."]
    if not path_parts:
        return True
    if path_parts[0] == ".designer":
        return True
    return not is_designer_resource_path(rel_path)


def _copy_source_tree(source_dir: str, target_dir: str, *, skip_roots: list[str] | None = None):
    source_dir = normalize_path(source_dir)
    target_dir = normalize_path(target_dir)
    skip_roots = [normalize_path(path) for path in (skip_roots or []) if normalize_path(path)]

    for root, dirs, files in os.walk(source_dir):
        normalized_root = normalize_path(root)
        dirs[:] = [
            name
            for name in dirs
            if not any(_is_same_or_child(os.path.join(normalized_root, name), skip_root) for skip_root in skip_roots)
            and _should_stage_designer_resource_path(source_dir, os.path.join(normalized_root, name))
        ]
        relative_root = os.path.relpath(normalized_root, source_dir)
        destination_root = target_dir if relative_root == "." else os.path.join(target_dir, relative_root)
        os.makedirs(destination_root, exist_ok=True)
        for file_name in files:
            src_path = os.path.join(normalized_root, file_name)
            if not _should_stage_designer_resource_path(source_dir, src_path):
                continue
            dst_path = os.path.join(destination_root, file_name)
            os.makedirs(os.path.dirname(dst_path), exist_ok=True)
            shutil.copy2(src_path, dst_path)


def _is_same_or_child(path: str, root: str) -> bool:
    path = normalize_path(path)
    root = normalize_path(root)
    if not path or not root:
        return False
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:
        return False
