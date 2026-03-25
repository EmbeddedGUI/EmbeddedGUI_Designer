#!/usr/bin/env python
"""Inspect local repository health for UI Designer development."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ui_designer.model.repo_health import collect_repo_health, format_repo_health_json, format_repo_health_text


def _parse_args():
    parser = argparse.ArgumentParser(description="Inspect local UI Designer repository health")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    payload = collect_repo_health()
    if args.json:
        print(format_repo_health_json(payload))
    else:
        print(format_repo_health_text(payload))
    return 0


if __name__ == "__main__":
    sys.exit(main())
