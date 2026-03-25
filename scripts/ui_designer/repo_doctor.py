#!/usr/bin/env python
"""Inspect local repository health for UI Designer development."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SDK_SUBMODULE_PATH = Path("sdk") / "EmbeddedGUI"
RELEASE_SMOKE_PROJECT = Path("samples") / "release_smoke" / "ReleaseSmokeApp"
KNOWN_STALE_DIR_NAMES = (
    ".pytest-tmp-codex",
    "tmpxtayw0f6",
    "verify_pytest_release",
)


def _parse_args():
    parser = argparse.ArgumentParser(description="Inspect local UI Designer repository health")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    return parser.parse_args()


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


def _sdk_is_initialized(submodule_status_line: str) -> bool:
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
    if not _sdk_is_initialized(submodule_status_line):
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
            "initialized": _sdk_is_initialized(submodule_status_line),
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


def _print_human(payload: dict[str, object]) -> None:
    print(f"[repo] {payload['repo_root']}")
    sdk = payload["sdk_submodule"]
    smoke = payload["release_smoke_project"]
    print(f"sdk_submodule.initialized: {str(sdk['initialized']).lower()}")
    if sdk["status"]:
        print(f"sdk_submodule.status: {sdk['status']}")
    print(f"release_smoke.present: {str(smoke['present']).lower()}")
    print(f"git_status_show_untracked: {payload['git_status_show_untracked']}")
    stale_dirs = payload["stale_temp_dirs"]
    print(f"stale_temp_dirs: {len(stale_dirs)}")
    for entry in stale_dirs:
        line = f"  - {entry['path']}"
        if not entry["accessible"]:
            line += f" [{entry['issue']}]"
        print(line)
    for suggestion in payload["suggestions"]:
        print(f"suggestion: {suggestion}")


def main() -> int:
    args = _parse_args()
    payload = collect_repo_health()
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        _print_human(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
