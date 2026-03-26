#!/usr/bin/env python
"""Run UI Designer tests with a stable temporary workspace."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TEST_ROOT = REPO_ROOT / "ui_designer" / "tests"
DEFAULT_PYTEST_CONFIG = REPO_ROOT / "ui_designer" / "pyproject.toml"
DEFAULT_BASETEMP_ROOT = REPO_ROOT / "temp" / "pytest"


def default_basetemp_root() -> Path:
    return DEFAULT_BASETEMP_ROOT


def build_basetemp_path(base_root: str | Path | None = None) -> Path:
    root = Path(base_root or default_basetemp_root()).resolve()
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
        default=str(default_basetemp_root()),
        help="Parent directory used for pytest --basetemp",
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
    return run_pytest(
        test_paths=args.paths,
        basetemp_root=args.basetemp_root,
        extra_args=list(extra_args),
        keep_basetemp=args.keep_basetemp,
    )


if __name__ == "__main__":
    sys.exit(main())
