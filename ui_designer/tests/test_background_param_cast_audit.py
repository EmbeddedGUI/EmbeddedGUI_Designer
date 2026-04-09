"""Audit against dangerous background params pointer casts in C sources."""

from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCAN_ROOTS = (
    REPO_ROOT / "examples",
    REPO_ROOT / "sdk" / "EmbeddedGUI" / "example",
    REPO_ROOT / "sdk" / "EmbeddedGUI" / "src",
)
FORBIDDEN_CAST_RE = re.compile(r"\(\s*(?:const\s+)?egui_background_params_t\s*\*\s*\)")


def _iter_scan_files() -> list[Path]:
    files: set[Path] = set()
    for root in SCAN_ROOTS:
        if not root.exists():
            continue
        files.update(path.resolve() for path in root.rglob("*.c") if path.is_file())
        files.update(path.resolve() for path in root.rglob("*.h") if path.is_file())
    return sorted(files)


def test_repo_has_no_background_params_pointer_casts():
    issues: list[str] = []

    for path in _iter_scan_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for line_no, line in enumerate(text.splitlines(), start=1):
            if FORBIDDEN_CAST_RE.search(line):
                rel = path.relative_to(REPO_ROOT).as_posix()
                issues.append(f"{rel}:{line_no}: {line.strip()}")

    assert not issues, (
        "Forbidden casts to egui_background_params_t* found.\n"
        "Wrap raw background params with EGUI_BACKGROUND_PARAM_INIT(...) instead.\n"
        + "\n".join(issues)
    )
