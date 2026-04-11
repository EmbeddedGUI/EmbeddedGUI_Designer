"""Shared test-only SDK construction helpers."""

from __future__ import annotations

from pathlib import Path


def build_test_sdk_root(root, *, makefile_text="all:\n"):
    """Create the minimal directory layout required for a valid SDK root."""
    sdk_root = Path(root)
    (sdk_root / "src").mkdir(parents=True, exist_ok=True)
    (sdk_root / "porting" / "designer").mkdir(parents=True, exist_ok=True)
    (sdk_root / "Makefile").write_text(makefile_text, encoding="utf-8")
    return sdk_root


def mark_bundled_test_sdk_root(
    root,
    *,
    metadata_name=".designer_sdk_bundle.json",
    source_root="D:/sdk/EmbeddedGUI",
):
    """Write bundle metadata so a test SDK root is treated as bundled."""
    sdk_root = Path(root)
    (sdk_root / metadata_name).write_text(
        f'{{"source_root": "{source_root}"}}\n',
        encoding="utf-8",
    )
    return sdk_root
