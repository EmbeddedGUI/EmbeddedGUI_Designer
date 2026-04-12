"""Repository health helpers shared by CLI and GUI workflows."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from ..utils.runtime_temp import repo_temp_dir


REPO_ROOT = Path(__file__).resolve().parents[2]
SDK_SUBMODULE_PATH = Path("sdk") / "EmbeddedGUI"
LEGACY_STALE_DIR_NAMES = (
    ".pytest-tmp-codex",
    "tmpxtayw0f6",
)
TEMP_SCAN_MAX_DEPTH = 3


def _nearest_existing_dir(path: Path) -> Path | None:
    current = path.resolve()
    while not current.exists():
        parent = current.parent
        if parent == current:
            return None
        current = parent
    if current.is_dir():
        return current
    if current.parent == current:
        return None
    return current.parent


def _probe_write_access(directory: Path) -> tuple[bool, str]:
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        return False, "permission_denied"
    except OSError as exc:
        return False, type(exc).__name__

    temp_path = None
    try:
        fd, temp_name = tempfile.mkstemp(prefix=".repo-health-", dir=str(directory))
        os.close(fd)
        temp_path = Path(temp_name)
        return True, ""
    except PermissionError:
        return False, "permission_denied"
    except OSError as exc:
        return False, type(exc).__name__
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink()
            except OSError:
                pass


def _inspect_runtime_path(path: Path) -> dict[str, object]:
    resolved = path.resolve()
    exists = resolved.exists()
    if exists and not resolved.is_dir():
        return {
            "path": str(resolved),
            "exists": True,
            "writable": False,
            "issue": "not_directory",
        }

    probe_target = resolved if exists else _nearest_existing_dir(resolved.parent)
    if probe_target is None:
        return {
            "path": str(resolved),
            "exists": exists,
            "writable": False,
            "issue": "missing_parent",
        }

    writable, issue = _probe_write_access(probe_target)
    return {
        "path": str(resolved),
        "exists": exists,
        "writable": writable,
        "issue": issue,
    }


def _resolve_config_dir() -> Path:
    try:
        from .config import _get_config_dir

        return Path(_get_config_dir()).resolve()
    except Exception:
        override = os.environ.get("EMBEDDEDGUI_DESIGNER_CONFIG_DIR", "").strip()
        if override:
            return Path(override).expanduser().resolve()
        return (REPO_ROOT / ".config").resolve()


def _resolve_pytest_temp_root(repo_root: Path) -> Path:
    try:
        from scripts.ui_designer.run_pytest import resolve_basetemp_root

        return Path(resolve_basetemp_root()).resolve()
    except Exception:
        try:
            from scripts.ui_designer.run_pytest import default_basetemp_root

            return Path(default_basetemp_root()).resolve()
        except Exception:
            return repo_temp_dir(repo_root, "pytest")


def collect_runtime_paths(repo_root: str | Path = REPO_ROOT) -> dict[str, dict[str, object]]:
    resolved_repo_root = Path(repo_root).resolve()
    config_dir = _resolve_config_dir()
    pytest_temp_root = _resolve_pytest_temp_root(resolved_repo_root)
    return {
        "config_dir": _inspect_runtime_path(config_dir),
        "pytest_temp_root": _inspect_runtime_path(pytest_temp_root),
    }


def runtime_path_issues(payload: dict[str, object]) -> list[str]:
    runtime_paths = payload.get("runtime_paths") if isinstance(payload.get("runtime_paths"), dict) else {}
    config_dir = runtime_paths.get("config_dir") if isinstance(runtime_paths.get("config_dir"), dict) else {}
    pytest_temp_root = runtime_paths.get("pytest_temp_root") if isinstance(runtime_paths.get("pytest_temp_root"), dict) else {}

    issues = []
    if config_dir and not bool(config_dir.get("writable", False)):
        issues.append("config dir is not writable")
    if pytest_temp_root and not bool(pytest_temp_root.get("writable", False)):
        issues.append("pytest temp root is not writable")
    return issues


def _run_git_text(repo_root: str | Path, *args: str) -> str:
    resolved_repo_root = Path(repo_root).resolve()
    git_exe = shutil.which("git")
    if not git_exe or not resolved_repo_root.is_dir():
        return ""

    result = subprocess.run(
        [git_exe, "-c", f"safe.directory={resolved_repo_root}", "-C", str(resolved_repo_root), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def sdk_is_initialized(submodule_status_line: str) -> bool:
    line = (submodule_status_line or "").strip()
    return bool(line) and not line.startswith("-")


def inspect_problem_dirs(repo_root: str | Path = REPO_ROOT) -> list[dict[str, object]]:
    resolved_repo_root = Path(repo_root).resolve()
    entries: list[dict[str, object]] = []
    for name in LEGACY_STALE_DIR_NAMES:
        path = resolved_repo_root / name
        entry = _inspect_directory(path)
        if entry is not None:
            entries.append(entry)
    entries.extend(_inspect_temp_work_dirs(repo_temp_dir(resolved_repo_root)))
    return entries


def _inspect_directory(path: Path, *, include_accessible: bool = True) -> dict[str, object] | None:
    if not path.exists() or not path.is_dir():
        return None

    issue = ""
    accessible = True
    try:
        next(path.iterdir(), None)
    except PermissionError:
        accessible = False
        issue = "permission_denied"
    except OSError as exc:
        accessible = False
        issue = type(exc).__name__

    if not include_accessible and accessible:
        return None

    return {
        "path": str(path),
        "accessible": accessible,
        "issue": issue,
    }


def _inspect_temp_work_dirs(temp_root: Path) -> list[dict[str, object]]:
    if not temp_root.exists() or not temp_root.is_dir():
        return []

    results: list[dict[str, object]] = []
    seen_paths: set[str] = set()
    stack: list[tuple[Path, int]] = [(temp_root, 0)]

    while stack:
        current, depth = stack.pop()
        entry = _inspect_directory(current, include_accessible=False)
        if entry is not None:
            path_text = str(current)
            if path_text not in seen_paths:
                results.append(entry)
                seen_paths.add(path_text)
            continue

        if depth >= TEMP_SCAN_MAX_DEPTH:
            continue

        try:
            children = [child for child in current.iterdir() if child.is_dir()]
        except (PermissionError, OSError):
            continue

        for child in children:
            stack.append((child, depth + 1))

    results.sort(key=lambda item: item["path"])
    return results


def collect_repo_health(repo_root: str | Path = REPO_ROOT) -> dict[str, object]:
    resolved_repo_root = Path(repo_root).resolve()
    submodule_status_line = _run_git_text(resolved_repo_root, "submodule", "status", "--", str(SDK_SUBMODULE_PATH))
    sdk_root = resolved_repo_root / SDK_SUBMODULE_PATH
    stale_dirs = inspect_problem_dirs(resolved_repo_root)
    runtime_paths = collect_runtime_paths(resolved_repo_root)
    show_untracked = _run_git_text(resolved_repo_root, "config", "--get", "status.showUntrackedFiles")

    suggestions: list[str] = []
    if not sdk_is_initialized(submodule_status_line):
        suggestions.append("Run: git submodule update --init --recursive")
    if stale_dirs:
        suggestions.append("If git status is noisy, use: git status -uno")
        suggestions.append("To hide untracked noise locally, use: git config status.showUntrackedFiles no")
        inaccessible_paths = [entry["path"] for entry in stale_dirs if not entry["accessible"]]
        if inaccessible_paths:
            suggestions.append("Remove stale ACL-broken temp dirs from an elevated shell if they keep reappearing")
    config_dir = runtime_paths.get("config_dir") if isinstance(runtime_paths.get("config_dir"), dict) else {}
    pytest_temp_root = runtime_paths.get("pytest_temp_root") if isinstance(runtime_paths.get("pytest_temp_root"), dict) else {}
    if config_dir and not bool(config_dir.get("writable", False)):
        suggestions.append("Set EMBEDDEDGUI_DESIGNER_CONFIG_DIR to a writable folder, or fix permissions on the default config directory")
    if pytest_temp_root and not bool(pytest_temp_root.get("writable", False)):
        suggestions.append("Pass --basetemp-root <writable-folder> to scripts/ui_designer/run_pytest.py, or fix permissions on the default pytest temp root")

    return {
        "repo_root": str(resolved_repo_root),
        "sdk_submodule": {
            "path": str(sdk_root),
            "present": sdk_root.exists(),
            "initialized": sdk_is_initialized(submodule_status_line),
            "status": submodule_status_line,
        },
        "runtime_paths": runtime_paths,
        "stale_temp_dirs": stale_dirs,
        "git_status_show_untracked": show_untracked or "default",
        "suggestions": suggestions,
    }


def summarize_repo_health(payload: dict[str, object]) -> str:
    sdk = payload.get("sdk_submodule") if isinstance(payload.get("sdk_submodule"), dict) else {}
    stale_dirs = payload.get("stale_temp_dirs") if isinstance(payload.get("stale_temp_dirs"), list) else []

    issues = []
    if not sdk.get("initialized", False):
        issues.append("SDK submodule is not initialized")
    issues.extend(runtime_path_issues(payload))
    if stale_dirs:
        issues.append(f"{len(stale_dirs)} stale temp dir(s) detected")
    if not issues:
        return "Repository health looks good."
    return "; ".join(issues)


def critical_repo_health_issues(payload: dict[str, object]) -> list[str]:
    sdk = payload.get("sdk_submodule") if isinstance(payload.get("sdk_submodule"), dict) else {}

    issues = []
    if not sdk.get("initialized", False):
        issues.append("SDK submodule is not initialized")
    return issues


def blocked_repo_health_stale_dirs(payload: dict[str, object]) -> list[dict[str, object]]:
    stale_dirs = payload.get("stale_temp_dirs") if isinstance(payload.get("stale_temp_dirs"), list) else []
    blocked_dirs: list[dict[str, object]] = []
    for entry in stale_dirs:
        if not isinstance(entry, dict):
            continue
        if bool(entry.get("accessible", False)):
            continue
        blocked_dirs.append(dict(entry))
    return blocked_dirs


def repo_health_view_suggestions(
    payload: dict[str, object],
    *,
    include_critical: bool,
    stale_dirs: list[dict[str, object]],
) -> list[str]:
    sdk = payload.get("sdk_submodule") if isinstance(payload.get("sdk_submodule"), dict) else {}

    suggestions: list[str] = []
    if include_critical and not sdk.get("initialized", False):
        suggestions.append("Run: git submodule update --init --recursive")
    if stale_dirs:
        suggestions.append("If git status is noisy, use: git status -uno")
        suggestions.append("To hide untracked noise locally, use: git config status.showUntrackedFiles no")
        if any(not bool(entry.get("accessible", False)) for entry in stale_dirs):
            suggestions.append("Remove stale ACL-broken temp dirs from an elevated shell if they keep reappearing")
    return suggestions


def repo_health_view_payload(
    payload: dict[str, object],
    *,
    critical_only: bool = False,
    blocked_only: bool = False,
) -> dict[str, object]:
    if not critical_only and not blocked_only:
        return payload

    sdk = payload.get("sdk_submodule") if isinstance(payload.get("sdk_submodule"), dict) else {}
    critical_issues = critical_repo_health_issues(payload)
    blocked_stale_dirs = blocked_repo_health_stale_dirs(payload)

    if not critical_only:
        view_payload = dict(payload)
        view_payload["stale_temp_dirs"] = blocked_stale_dirs
        view_payload["suggestions"] = repo_health_view_suggestions(
            payload,
            include_critical=True,
            stale_dirs=blocked_stale_dirs,
        )
        return view_payload

    return {
        "repo_root": str(payload.get("repo_root") or ""),
        "sdk_submodule": {
            "path": str(sdk.get("path") or ""),
            "present": bool(sdk.get("present", False)),
            "initialized": bool(sdk.get("initialized", False)),
            "status": str(sdk.get("status") or ""),
        },
        "runtime_paths": payload.get("runtime_paths") if isinstance(payload.get("runtime_paths"), dict) else {},
        "stale_temp_dirs": blocked_stale_dirs if blocked_only else [],
        "git_status_show_untracked": str(payload.get("git_status_show_untracked") or "default"),
        "suggestions": repo_health_view_suggestions(
            payload,
            include_critical=True,
            stale_dirs=blocked_stale_dirs if blocked_only else [],
        ),
        "critical_issues": critical_issues,
    }


def repo_health_counts(payload: dict[str, object]) -> dict[str, int]:
    stale_dirs = payload.get("stale_temp_dirs") if isinstance(payload.get("stale_temp_dirs"), list) else []
    suggestions = payload.get("suggestions") if isinstance(payload.get("suggestions"), list) else []
    critical_issues = payload.get("critical_issues") if isinstance(payload.get("critical_issues"), list) else critical_repo_health_issues(payload)
    blocked_stale_dirs = sum(1 for entry in stale_dirs if not bool(entry.get("accessible", False)))
    return {
        "critical": len(critical_issues),
        "suggestions": len(suggestions),
        "stale_dirs": len(stale_dirs),
        "blocked_stale_dirs": blocked_stale_dirs,
    }


def format_repo_health_summary(
    payload: dict[str, object],
    *,
    critical_only: bool = False,
    blocked_only: bool = False,
) -> str:
    counts = repo_health_counts(payload)
    return (
        f"{summarize_repo_health(payload)} | "
        f"critical={counts['critical']} "
        f"suggestions={counts['suggestions']} "
        f"stale={counts['stale_dirs']} "
        f"blocked={counts['blocked_stale_dirs']} "
        f"critical_only={str(bool(critical_only)).lower()} "
        f"blocked_only={str(bool(blocked_only)).lower()}"
    )


def format_repo_health_text(
    payload: dict[str, object],
    *,
    critical_only: bool = False,
    blocked_only: bool = False,
) -> str:
    counts = repo_health_counts(payload)
    lines = [
        f"[summary] {summarize_repo_health(payload)}",
        (
            "[counts] "
            f"critical={counts['critical']} "
            f"suggestions={counts['suggestions']} "
            f"stale={counts['stale_dirs']} "
            f"blocked={counts['blocked_stale_dirs']}"
        ),
        (
            "[view] "
            f"critical_only={str(bool(critical_only)).lower()} "
            f"blocked_only={str(bool(blocked_only)).lower()}"
        ),
        "",
        f"[repo] {payload.get('repo_root', '')}",
    ]
    sdk = payload.get("sdk_submodule") if isinstance(payload.get("sdk_submodule"), dict) else {}
    lines.append(f"sdk_submodule.initialized: {str(bool(sdk.get('initialized', False))).lower()}")
    sdk_status = str(sdk.get("status") or "")
    if sdk_status:
        lines.append(f"sdk_submodule.status: {sdk_status}")
    lines.append(f"git_status_show_untracked: {payload.get('git_status_show_untracked', 'default')}")
    runtime_paths = payload.get("runtime_paths") if isinstance(payload.get("runtime_paths"), dict) else {}
    for key in ("config_dir", "pytest_temp_root"):
        entry = runtime_paths.get(key) if isinstance(runtime_paths.get(key), dict) else None
        if not entry:
            continue
        line = (
            f"runtime_paths.{key}: "
            f"path={entry.get('path', '')} "
            f"exists={str(bool(entry.get('exists', False))).lower()} "
            f"writable={str(bool(entry.get('writable', False))).lower()}"
        )
        issue = str(entry.get("issue") or "")
        if issue:
            line += f" issue={issue}"
        lines.append(line)
    stale_dirs = payload.get("stale_temp_dirs") if isinstance(payload.get("stale_temp_dirs"), list) else []
    lines.append(f"stale_temp_dirs: {len(stale_dirs)} (blocked {counts['blocked_stale_dirs']})")
    for entry in stale_dirs:
        line = f"  - {entry['path']}"
        if not entry["accessible"]:
            line += f" [{entry['issue']}]"
        lines.append(line)
    for suggestion in payload.get("suggestions", []):
        lines.append(f"suggestion: {suggestion}")
    critical_issues = payload.get("critical_issues") if isinstance(payload.get("critical_issues"), list) else critical_repo_health_issues(payload)
    if critical_issues:
        lines.append(f"critical_issues: {len(critical_issues)}")
        for issue in critical_issues:
            lines.append(f"critical: {issue}")
    return "\n".join(lines)


def format_repo_health_json(
    payload: dict[str, object],
    *,
    critical_only: bool = False,
    blocked_only: bool = False,
) -> str:
    report = dict(payload)
    report["_summary"] = summarize_repo_health(payload)
    report["_counts"] = repo_health_counts(payload)
    report["_view"] = {
        "critical_only": bool(critical_only),
        "blocked_only": bool(blocked_only),
    }
    return json.dumps(report, indent=2, ensure_ascii=False)
