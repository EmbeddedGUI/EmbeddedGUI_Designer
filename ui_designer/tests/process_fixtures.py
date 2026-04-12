"""Shared test-only helpers for fake subprocess results."""

from __future__ import annotations

from types import SimpleNamespace


def build_completed_process_result(*, returncode=0, stdout="", stderr=""):
    """Return a SimpleNamespace shaped like subprocess.CompletedProcess."""
    return SimpleNamespace(
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )
