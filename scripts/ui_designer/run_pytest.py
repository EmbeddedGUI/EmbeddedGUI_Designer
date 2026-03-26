#!/usr/bin/env python
"""Run UI Designer tests with a stable temporary workspace."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TEST_ROOT = REPO_ROOT / "ui_designer" / "tests"
DEFAULT_PYTEST_CONFIG = REPO_ROOT / "ui_designer" / "pyproject.toml"
DEFAULT_BASETEMP_ROOT = REPO_ROOT / "temp" / "pytest"
CONFIG_DIR_ENV_VAR = "EMBEDDEDGUI_DESIGNER_CONFIG_DIR"


def _default_user_config_dir() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    elif sys.platform == "darwin":
        base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME", os.path.join(os.path.expanduser("~"), ".config"))
    return Path(base) / "EmbeddedGUI-Designer"


def _default_config_dir() -> Path:
    override = os.environ.get(CONFIG_DIR_ENV_VAR, "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return _default_user_config_dir().expanduser().resolve()


def default_basetemp_root() -> Path:
    return DEFAULT_BASETEMP_ROOT


def candidate_basetemp_roots() -> list[Path]:
    candidates = [
        default_basetemp_root(),
        _default_config_dir() / "pytest",
        Path(tempfile.gettempdir()).resolve() / "EmbeddedGUI-Designer" / "pytest",
    ]
    deduped = []
    seen = set()
    for candidate in candidates:
        resolved = Path(candidate).expanduser().resolve()
        key = str(resolved)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(resolved)
    return deduped


def probe_writable_root(path: str | Path) -> tuple[bool, str]:
    resolved = Path(path).expanduser().resolve()
    try:
        resolved.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return False, f"{type(exc).__name__}: {exc}"

    probe_path = resolved / f".write-probe-{os.getpid()}-{time.time_ns()}"
    try:
        probe_path.write_text("probe", encoding="utf-8")
    except OSError as exc:
        return False, f"{type(exc).__name__}: {exc}"
    finally:
        probe_path.unlink(missing_ok=True)
    return True, ""


def resolve_basetemp_root(basetemp_root: str | Path | None = None) -> Path:
    if basetemp_root is not None:
        resolved = Path(basetemp_root).expanduser().resolve()
        ok, issue = probe_writable_root(resolved)
        if not ok:
            raise ValueError(f"Basetemp root is not writable: {resolved} ({issue})")
        return resolved

    failures = []
    for candidate in candidate_basetemp_roots():
        ok, issue = probe_writable_root(candidate)
        if ok:
            return candidate
        failures.append(f"{candidate} ({issue})")

    raise RuntimeError("No writable pytest basetemp root found: " + "; ".join(failures))


def build_basetemp_path(base_root: str | Path | None = None) -> Path:
    root = resolve_basetemp_root(base_root)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    return root / f"run-{stamp}-{os.getpid()}"


def build_pytest_command(
    test_paths: list[str] | None = None,
    *,
    basetemp: str | Path | None = None,
    extra_args: list[str] | None = None,
) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-c",
        str(DEFAULT_PYTEST_CONFIG),
    ]
    command.extend(test_paths or [str(DEFAULT_TEST_ROOT)])
    if basetemp:
        command.extend(["--basetemp", str(Path(basetemp).resolve())])
    command.extend(extra_args or [])
    return command


def _parse_args():
    parser = argparse.ArgumentParser(description="Run UI Designer pytest suite with a safe temp root")
    parser.add_argument(
        "paths",
        nargs="*",
        help="Optional test paths or node ids (default: ui_designer/tests)",
    )
    parser.add_argument(
        "--basetemp-root",
        default=None,
        help=(
            "Parent directory used for pytest --basetemp "
            f"(default: auto-detect writable root, preferring {default_basetemp_root()})"
        ),
    )
    parser.add_argument(
        "--keep-basetemp",
        action="store_true",
        help="Keep the generated pytest base temp directory after the run",
    )
    args, extra_args = parser.parse_known_args()
    if extra_args and extra_args[0] == "--":
        extra_args = extra_args[1:]
    return args, extra_args


def run_pytest(
    *,
    test_paths: list[str] | None = None,
    basetemp_root: str | Path | None = None,
    extra_args: list[str] | None = None,
    keep_basetemp: bool = False,
) -> int:
    basetemp = build_basetemp_path(basetemp_root)
    basetemp.parent.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["TMP"] = str(basetemp)
    env["TEMP"] = str(basetemp)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.setdefault("QT_QPA_PLATFORM", "offscreen")

    command = build_pytest_command(test_paths, basetemp=basetemp, extra_args=extra_args)
    try:
        result = subprocess.run(
            command,
            cwd=REPO_ROOT,
            env=env,
            check=False,
        )
        return int(result.returncode)
    finally:
        if not keep_basetemp:
            shutil.rmtree(basetemp, ignore_errors=True)


def main() -> int:
    args, extra_args = _parse_args()
    try:
        return run_pytest(
            test_paths=args.paths,
            basetemp_root=args.basetemp_root,
            extra_args=list(extra_args),
            keep_basetemp=args.keep_basetemp,
        )
    except (RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
