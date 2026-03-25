#!/usr/bin/env python
"""Inspect local repository health for UI Designer development."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ui_designer.model.repo_health import collect_repo_health, critical_repo_health_issues, format_repo_health_json, format_repo_health_text


EXIT_OK = 0
EXIT_HEALTH_ERROR = 2


def _parse_args():
    parser = argparse.ArgumentParser(description="Inspect local UI Designer repository health")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    parser.add_argument("--strict", action="store_true", help="Return a non-zero exit code on critical repository health issues")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    payload = collect_repo_health()
    if args.json:
        print(format_repo_health_json(payload))
    else:
        print(format_repo_health_text(payload))
    if args.strict and critical_repo_health_issues(payload):
        return EXIT_HEALTH_ERROR
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
