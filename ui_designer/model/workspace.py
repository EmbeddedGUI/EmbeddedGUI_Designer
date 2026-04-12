"""Workspace path helpers for EmbeddedGUI Designer."""

from __future__ import annotations

import os
import sys
from typing import Iterable


_COMMON_SDK_CONTAINER_NAMES = ("sdk", "SDK")
SDK_ROOT_ENV_VAR = "EMBEDDEDGUI_SDK_ROOT"
DEFAULT_DESIGNER_SDK_CONTAINER = "sdk"
DEFAULT_DESIGNER_SDK_DIRNAME = "EmbeddedGUI"
DEFAULT_DESIGNER_EXAMPLES_DIRNAME = "examples"
SDK_RESOURCE_GENERATOR_RELPATH = os.path.join("scripts", "tools", "app_resource_generate.py")
SDK_OUTPUT_DIRNAME = "output"


def normalize_path(path: str | None) -> str:
    """Return an absolute normalized path, or an empty string."""
    if not path:
        return ""
    return os.path.normpath(os.path.abspath(path))


def is_valid_sdk_root(path: str | None) -> bool:
    """Return True when *path* looks like a valid EmbeddedGUI SDK root."""
    root = normalize_path(path)
    if not root:
        return False
    return (
        os.path.isfile(os.path.join(root, "Makefile"))
        and os.path.isdir(os.path.join(root, "src"))
        and os.path.isdir(os.path.join(root, "porting", "designer"))
    )


def _dedupe_paths(paths: Iterable[str]) -> list[str]:
    seen = set()
    result = []
    for path in paths:
        norm = normalize_path(path)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        result.append(norm)
    return result


def _walk_ancestors(path: str) -> list[str]:
    current = normalize_path(path)
    if not current:
        return []
    if os.path.isfile(current):
        current = os.path.dirname(current)

    result = []
    while current:
        result.append(current)
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return result


def _looks_like_sdk_dir_name(name: str) -> bool:
    name = (name or "").strip().lower()
    if not name:
        return False
    return name in {"sdk", "embeddedgui"} or "embeddedgui" in name


def _list_matching_child_dirs(base: str) -> list[str]:
    base = normalize_path(base)
    if not base or not os.path.isdir(base):
        return []

    result = []
    try:
        for entry in sorted(os.listdir(base)):
            child = os.path.join(base, entry)
            if os.path.isdir(child) and _looks_like_sdk_dir_name(entry):
                result.append(child)
    except OSError:
        return []
    return result


def _search_common_sdk_locations(anchor: str) -> list[str]:
    result = []
    for base in _walk_ancestors(anchor):
        result.append(base)
        result.extend(_list_matching_child_dirs(base))
        for container_name in _COMMON_SDK_CONTAINER_NAMES:
            container_dir = os.path.join(base, container_name)
            result.append(container_dir)
            result.extend(_list_matching_child_dirs(container_dir))
    return result


def _search_nearby_sdk_locations(anchor: str) -> list[str]:
    """Search only the provided anchor and its immediate SDK-like children."""
    base = normalize_path(anchor)
    if not base:
        return []
    if os.path.isfile(base):
        base = os.path.dirname(base)

    result = [base]
    result.extend(_list_matching_child_dirs(base))
    for container_name in _COMMON_SDK_CONTAINER_NAMES:
        container_dir = os.path.join(base, container_name)
        result.append(container_dir)
        result.extend(_list_matching_child_dirs(container_dir))
    return result


def resolve_sdk_root_candidate(path: str | None) -> str:
    """Resolve *path* to a valid SDK root when possible.

    Accepts exact SDK roots as well as nearby parent/container directories such
    as ``sdk/`` or a project directory living under ``sdk_root/example/app``.
    """
    candidate = normalize_path(path)
    if not candidate:
        return ""

    if is_valid_sdk_root(candidate):
        return candidate

    inferred = infer_sdk_root_from_project_dir(candidate)
    if inferred:
        return inferred

    for nearby in _dedupe_paths(_search_nearby_sdk_locations(candidate)):
        if is_valid_sdk_root(nearby):
            return nearby
    return ""


def resolve_preferred_sdk_root(*candidates: str | None) -> str:
    """Return the first valid SDK root resolved from *candidates*.

    If none of the candidates resolve to a valid SDK root, the first non-empty
    normalized candidate is returned so the UI can still surface an invalid
    configured path to the user.
    """
    normalized_candidates = _dedupe_paths(candidates)
    for candidate in normalized_candidates:
        resolved = resolve_sdk_root_candidate(candidate)
        if resolved:
            return resolved
    return normalized_candidates[0] if normalized_candidates else ""


def resolve_available_sdk_root(*candidates: str | None, cached_sdk_root: str | None = None) -> str:
    """Resolve the best currently-usable SDK root.

    Preference order:
    1. The first valid SDK resolved from *candidates*
    2. A valid *cached_sdk_root*
    3. The first non-empty normalized candidate for UI display purposes
    """
    sdk_root = resolve_preferred_sdk_root(*candidates)
    cached_sdk_root = normalize_path(cached_sdk_root)
    if not is_valid_sdk_root(cached_sdk_root):
        cached_sdk_root = ""
    if cached_sdk_root and not is_valid_sdk_root(sdk_root):
        return cached_sdk_root
    return sdk_root


def resolve_configured_sdk_root(
    *candidates: str | None,
    cached_sdk_root: str | None = None,
    preserve_invalid: bool = False,
) -> str:
    """Resolve an SDK root from configured paths without broad ancestor search first.

    Preference order:
    1. Exact valid candidates or direct ``example/``-based inference
    2. A valid cached SDK root
    3. The first invalid configured candidate when ``preserve_invalid`` is true
    4. Broad ``resolve_available_sdk_root()`` fallback
    """
    normalized_candidates = _dedupe_paths(candidates)

    for candidate in normalized_candidates:
        if is_valid_sdk_root(candidate):
            return candidate
        inferred = infer_sdk_root_from_project_dir(candidate)
        if inferred:
            return inferred

    cached_sdk_root = normalize_path(cached_sdk_root)
    if is_valid_sdk_root(cached_sdk_root):
        return cached_sdk_root

    if preserve_invalid:
        return normalized_candidates[0] if normalized_candidates else ""

    return resolve_available_sdk_root(*normalized_candidates, cached_sdk_root=cached_sdk_root)


def serialize_sdk_root(project_dir: str, sdk_root: str) -> str:
    """Serialize *sdk_root* for storage in a project file."""
    project_dir = normalize_path(project_dir)
    sdk_root = normalize_path(sdk_root)
    if not project_dir or not sdk_root:
        return ""
    try:
        return os.path.relpath(sdk_root, project_dir).replace("\\", "/")
    except ValueError:
        return sdk_root.replace("\\", "/")


def resolve_project_sdk_root(project_dir: str, stored_path: str) -> str:
    """Resolve a stored SDK path relative to *project_dir*."""
    project_dir = normalize_path(project_dir)
    stored_path = (stored_path or "").strip()
    if not project_dir or not stored_path:
        return ""
    if os.path.isabs(stored_path):
        return normalize_path(stored_path)
    return normalize_path(os.path.join(project_dir, stored_path))


def infer_sdk_root_from_project_dir(project_dir: str) -> str:
    """Infer SDK root when the project lives under ``sdk_root/example/app``."""
    project_dir = normalize_path(project_dir)
    if not project_dir:
        return ""
    example_dir = os.path.dirname(project_dir)
    if os.path.basename(example_dir) != "example":
        return ""
    candidate = os.path.dirname(example_dir)
    if is_valid_sdk_root(candidate):
        return candidate
    return ""


def compute_make_app_root_arg(sdk_root: str, app_dir: str, app_name: str) -> str:
    """Compute ``EGUI_APP_ROOT_PATH`` for make."""
    sdk_root = normalize_path(sdk_root)
    app_dir = normalize_path(app_dir)
    if not sdk_root or not app_dir or not app_name:
        raise ValueError("sdk_root, app_dir, and app_name are required")

    example_app_dir = normalize_path(os.path.join(sdk_root, "example", app_name))
    if app_dir == example_app_dir:
        return "example"

    try:
        relative_parent = os.path.relpath(os.path.dirname(app_dir), sdk_root)
    except ValueError as exc:
        raise ValueError("External app must be on the same drive as the SDK root") from exc

    relative_parent = relative_parent.replace("\\", "/")
    return relative_parent or "."


def find_sdk_root(
    *,
    cli_sdk_root: str | None = None,
    configured_sdk_root: str | None = None,
    project_path: str | None = None,
    env: dict[str, str] | None = None,
    extra_candidates: Iterable[str] | None = None,
) -> str:
    """Find the best SDK root candidate."""
    env = env or os.environ
    candidates = []

    if cli_sdk_root:
        candidates.append(cli_sdk_root)

    if project_path:
        project_norm = normalize_path(project_path)
        project_dir = project_norm if os.path.isdir(project_norm) else os.path.dirname(project_norm)
        candidates.extend(_search_common_sdk_locations(project_dir))
        inferred = infer_sdk_root_from_project_dir(project_dir)
        if inferred:
            candidates.append(inferred)

    if configured_sdk_root:
        candidates.append(configured_sdk_root)

    env_sdk_root = env.get(SDK_ROOT_ENV_VAR, "")
    if env_sdk_root:
        candidates.append(env_sdk_root)

    if extra_candidates:
        candidates.extend(extra_candidates)

    runtime_anchor = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else __file__)
    candidates.extend(_search_common_sdk_locations(runtime_anchor))
    candidates.extend(_search_common_sdk_locations(os.getcwd()))

    for candidate in _dedupe_paths(candidates):
        resolved = resolve_sdk_root_candidate(candidate)
        if resolved:
            return resolved
    return ""


def describe_sdk_root(path: str | None) -> str:
    """Return a short status string for a candidate SDK root."""
    root = normalize_path(path)
    if not root:
        return "missing"
    if is_valid_sdk_root(root):
        return "ready"
    return "invalid"


def sdk_resource_generator_path(sdk_root: str | None) -> str:
    """Return the absolute path to ``app_resource_generate.py`` for an SDK root."""
    root = normalize_path(sdk_root)
    if not root:
        return ""
    return normalize_path(os.path.join(root, SDK_RESOURCE_GENERATOR_RELPATH))


def sdk_output_dir(sdk_root: str | None) -> str:
    """Return the absolute SDK ``output`` directory path."""
    root = normalize_path(sdk_root)
    if not root:
        return ""
    return normalize_path(os.path.join(root, SDK_OUTPUT_DIRNAME))


def sdk_output_path(sdk_root: str | None, *parts: str) -> str:
    """Return a path under the SDK ``output`` directory."""
    output_dir = sdk_output_dir(sdk_root)
    if not output_dir:
        return ""
    return normalize_path(os.path.join(output_dir, *parts))


def designer_runtime_root(repo_root: str | None = None) -> str:
    """Return the Designer runtime root directory.

    Source runs use the repository root by default. Frozen builds use the
    directory containing the executable so local projects/examples live beside
    the packaged app.
    """
    if getattr(sys, "frozen", False):
        return normalize_path(os.path.dirname(sys.executable))

    resolved_repo_root = normalize_path(repo_root)
    if resolved_repo_root:
        return resolved_repo_root

    return normalize_path(os.path.join(os.path.dirname(__file__), "..", ".."))


def designer_examples_root(
    repo_root: str | None = None,
    dirname: str = DEFAULT_DESIGNER_EXAMPLES_DIRNAME,
) -> str:
    """Return the root directory for bundled Designer examples."""
    runtime_root = designer_runtime_root(repo_root)
    if not runtime_root:
        return ""
    return normalize_path(os.path.join(runtime_root, dirname))


def list_designer_example_entries(repo_root: str | None = None) -> list[dict[str, object]]:
    """List bundled Designer example projects under ``examples/``."""
    examples_root = designer_examples_root(repo_root)
    if not examples_root or not os.path.isdir(examples_root):
        return []

    entries: list[dict[str, object]] = []
    for entry_name in sorted(os.listdir(examples_root)):
        app_dir = normalize_path(os.path.join(examples_root, entry_name))
        if not os.path.isdir(app_dir):
            continue

        project_files = sorted(
            filename
            for filename in os.listdir(app_dir)
            if filename.lower().endswith(".egui") and os.path.isfile(os.path.join(app_dir, filename))
        )
        if len(project_files) != 1:
            continue

        project_name = os.path.splitext(project_files[0])[0]
        entries.append(
            {
                "app_name": project_name,
                "app_dir": app_dir,
                "project_path": normalize_path(os.path.join(app_dir, project_files[0])),
                "has_project": True,
                "is_unmanaged": False,
                "source": "designer",
            }
        )

    return sorted(entries, key=lambda item: str(item.get("app_name", "")).lower())


def default_designer_sdk_root(
    repo_root: str | None,
    container_dirname: str = DEFAULT_DESIGNER_SDK_CONTAINER,
    dirname: str = DEFAULT_DESIGNER_SDK_DIRNAME,
) -> str:
    """Return the default SDK submodule root for the standalone Designer repo."""
    repo_root = normalize_path(repo_root)
    if not repo_root:
        return ""
    return normalize_path(os.path.join(repo_root, container_dirname, dirname))


def fallback_designer_sdk_root(repo_root: str | None, dirname: str = DEFAULT_DESIGNER_SDK_DIRNAME) -> str:
    """Return the fallback sibling SDK root for the standalone Designer repo."""
    repo_root = normalize_path(repo_root)
    if not repo_root:
        return ""
    return normalize_path(os.path.join(os.path.dirname(repo_root), dirname))


def describe_designer_sdk_root_help(repo_root: str | None, cli_flag: str = "--sdk-root") -> str:
    """Return a user-facing hint for resolving the external SDK root."""
    submodule_sdk_root = default_designer_sdk_root(repo_root)
    sibling_sdk_root = fallback_designer_sdk_root(repo_root)
    return (
        f"Provide {cli_flag} <path>, or set {SDK_ROOT_ENV_VAR}, "
        f"or initialize the SDK submodule at {submodule_sdk_root}, "
        f"or place the SDK at {sibling_sdk_root}"
    )


def resolve_designer_sdk_root(
    *,
    repo_root: str | None,
    cli_sdk_root: str | None = None,
    env: dict[str, str] | None = None,
) -> str:
    """Resolve the external EmbeddedGUI SDK for the standalone Designer repo.

    Resolution order is strict:
    1. ``cli_sdk_root`` when provided
    2. ``EMBEDDEDGUI_SDK_ROOT`` when set
    3. Repo submodule ``sdk/EmbeddedGUI`` under ``repo_root``
    4. Sibling ``../EmbeddedGUI`` beside ``repo_root``

    Explicit CLI and environment values are validated strictly. If either is
    provided but invalid, ``ValueError`` is raised instead of silently falling
    back to another source.
    """
    env = env or os.environ

    cli_sdk_root = normalize_path(cli_sdk_root)
    if cli_sdk_root:
        resolved = resolve_sdk_root_candidate(cli_sdk_root)
        if resolved:
            return resolved
        raise ValueError(f"invalid EmbeddedGUI SDK root: {cli_sdk_root}")

    env_sdk_root = normalize_path(env.get(SDK_ROOT_ENV_VAR, ""))
    if env_sdk_root:
        resolved = resolve_sdk_root_candidate(env_sdk_root)
        if resolved:
            return resolved
        raise ValueError(f"invalid EmbeddedGUI SDK root from {SDK_ROOT_ENV_VAR}: {env_sdk_root}")

    submodule_sdk_root = default_designer_sdk_root(repo_root)
    if submodule_sdk_root:
        resolved = resolve_sdk_root_candidate(submodule_sdk_root)
        if resolved:
            return resolved

    sibling_sdk_root = fallback_designer_sdk_root(repo_root)
    if sibling_sdk_root:
        resolved = resolve_sdk_root_candidate(sibling_sdk_root)
        if resolved:
            return resolved

    return ""


def require_designer_sdk_root(
    *,
    repo_root: str | None,
    cli_sdk_root: str | None = None,
    env: dict[str, str] | None = None,
    cli_flag: str = "--sdk-root",
) -> str:
    """Return the external SDK root or raise a clear ``RuntimeError``."""
    try:
        sdk_root = resolve_designer_sdk_root(
            repo_root=repo_root,
            cli_sdk_root=cli_sdk_root,
            env=env,
        )
    except ValueError as exc:
        raise RuntimeError(
            f"{exc}\n{describe_designer_sdk_root_help(repo_root, cli_flag=cli_flag)}"
        ) from exc

    if sdk_root:
        return sdk_root

    raise RuntimeError(
        "EmbeddedGUI SDK root not found.\n"
        f"{describe_designer_sdk_root_help(repo_root, cli_flag=cli_flag)}"
    )



