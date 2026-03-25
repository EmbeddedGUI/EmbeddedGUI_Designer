"""Repository health helpers shared by CLI and GUI workflows."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SDK_SUBMODULE_PATH = Path("sdk") / "EmbeddedGUI"
RELEASE_SMOKE_PROJECT = Path("samples") / "release_smoke" / "ReleaseSmokeApp"
KNOWN_STALE_DIR_NAMES = (
    ".pytest-tmp-codex",
    "tmpxtayw0f6",
    "verify_pytest_release",
)


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
    for name in KNOWN_STALE_DIR_NAMES:
        path = resolved_repo_root / name
        if not path.exists():
            continue
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
        entries.append(
            {
                "path": str(path),
                "accessible": accessible,
                "issue": issue,
            }
        )
    return entries


def collect_repo_health(repo_root: str | Path = REPO_ROOT) -> dict[str, object]:
    resolved_repo_root = Path(repo_root).resolve()
    submodule_status_line = _run_git_text(resolved_repo_root, "submodule", "status", "--", str(SDK_SUBMODULE_PATH))
    sdk_root = resolved_repo_root / SDK_SUBMODULE_PATH
    stale_dirs = inspect_problem_dirs(resolved_repo_root)
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
    if not (resolved_repo_root / RELEASE_SMOKE_PROJECT).is_dir():
        suggestions.append("Restore samples/release_smoke/ReleaseSmokeApp before running release smoke checks")

    return {
        "repo_root": str(resolved_repo_root),
        "sdk_submodule": {
            "path": str(sdk_root),
            "present": sdk_root.exists(),
            "initialized": sdk_is_initialized(submodule_status_line),
            "status": submodule_status_line,
        },
        "release_smoke_project": {
            "path": str(resolved_repo_root / RELEASE_SMOKE_PROJECT),
            "present": (resolved_repo_root / RELEASE_SMOKE_PROJECT).is_dir(),
        },
        "stale_temp_dirs": stale_dirs,
        "git_status_show_untracked": show_untracked or "default",
        "suggestions": suggestions,
    }


def summarize_repo_health(payload: dict[str, object]) -> str:
    sdk = payload.get("sdk_submodule") if isinstance(payload.get("sdk_submodule"), dict) else {}
    smoke = payload.get("release_smoke_project") if isinstance(payload.get("release_smoke_project"), dict) else {}
    stale_dirs = payload.get("stale_temp_dirs") if isinstance(payload.get("stale_temp_dirs"), list) else []

    issues = []
    if not sdk.get("initialized", False):
        issues.append("SDK submodule is not initialized")
    if not smoke.get("present", False):
        issues.append("release smoke sample is missing")
    if stale_dirs:
        issues.append(f"{len(stale_dirs)} stale temp dir(s) detected")
    if not issues:
        return "Repository health looks good."
    return "; ".join(issues)


def critical_repo_health_issues(payload: dict[str, object]) -> list[str]:
    sdk = payload.get("sdk_submodule") if isinstance(payload.get("sdk_submodule"), dict) else {}
    smoke = payload.get("release_smoke_project") if isinstance(payload.get("release_smoke_project"), dict) else {}

    issues = []
    if not sdk.get("initialized", False):
        issues.append("SDK submodule is not initialized")
    if not smoke.get("present", False):
        issues.append("release smoke sample is missing")
    return issues


def repo_health_view_payload(payload: dict[str, object], *, critical_only: bool = False) -> dict[str, object]:
    if not critical_only:
        return payload

    sdk = payload.get("sdk_submodule") if isinstance(payload.get("sdk_submodule"), dict) else {}
    smoke = payload.get("release_smoke_project") if isinstance(payload.get("release_smoke_project"), dict) else {}
    critical_issues = critical_repo_health_issues(payload)

    suggestions = []
    if not sdk.get("initialized", False):
        suggestions.append("Run: git submodule update --init --recursive")
    if not smoke.get("present", False):
        suggestions.append("Restore samples/release_smoke/ReleaseSmokeApp before running release smoke checks")

    return {
        "repo_root": str(payload.get("repo_root") or ""),
        "sdk_submodule": {
            "path": str(sdk.get("path") or ""),
            "present": bool(sdk.get("present", False)),
            "initialized": bool(sdk.get("initialized", False)),
            "status": str(sdk.get("status") or ""),
        },
        "release_smoke_project": {
            "path": str(smoke.get("path") or ""),
            "present": bool(smoke.get("present", False)),
        },
        "stale_temp_dirs": [],
        "git_status_show_untracked": str(payload.get("git_status_show_untracked") or "default"),
        "suggestions": suggestions,
        "critical_issues": critical_issues,
    }


def repo_health_counts(payload: dict[str, object]) -> dict[str, int]:
    stale_dirs = payload.get("stale_temp_dirs") if isinstance(payload.get("stale_temp_dirs"), list) else []
    suggestions = payload.get("suggestions") if isinstance(payload.get("suggestions"), list) else []
    critical_issues = payload.get("critical_issues") if isinstance(payload.get("critical_issues"), list) else critical_repo_health_issues(payload)
    return {
        "critical": len(critical_issues),
        "suggestions": len(suggestions),
        "stale_dirs": len(stale_dirs),
    }


def format_repo_health_text(payload: dict[str, object], *, critical_only: bool = False) -> str:
    counts = repo_health_counts(payload)
    lines = [
        f"[summary] {summarize_repo_health(payload)}",
        f"[counts] critical={counts['critical']} suggestions={counts['suggestions']} stale={counts['stale_dirs']}",
        f"[view] critical_only={str(bool(critical_only)).lower()}",
        "",
        f"[repo] {payload.get('repo_root', '')}",
    ]
    sdk = payload.get("sdk_submodule") if isinstance(payload.get("sdk_submodule"), dict) else {}
    smoke = payload.get("release_smoke_project") if isinstance(payload.get("release_smoke_project"), dict) else {}
    lines.append(f"sdk_submodule.initialized: {str(bool(sdk.get('initialized', False))).lower()}")
    sdk_status = str(sdk.get("status") or "")
    if sdk_status:
        lines.append(f"sdk_submodule.status: {sdk_status}")
    lines.append(f"release_smoke.present: {str(bool(smoke.get('present', False))).lower()}")
    lines.append(f"git_status_show_untracked: {payload.get('git_status_show_untracked', 'default')}")
    stale_dirs = payload.get("stale_temp_dirs") if isinstance(payload.get("stale_temp_dirs"), list) else []
    lines.append(f"stale_temp_dirs: {len(stale_dirs)}")
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


def format_repo_health_json(payload: dict[str, object], *, critical_only: bool = False) -> str:
    report = dict(payload)
    report["_summary"] = summarize_repo_health(payload)
    report["_counts"] = repo_health_counts(payload)
    report["_view"] = {
        "critical_only": bool(critical_only),
    }
    return json.dumps(report, indent=2, ensure_ascii=False)
