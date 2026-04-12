"""Shared test-only helpers for fake subprocess results."""

from __future__ import annotations

from ui_designer.tests.namespace_fixtures import build_namespace_stub


def build_completed_process_result(*, returncode=0, stdout="", stderr=""):
    """Return a namespace stub shaped like subprocess.CompletedProcess."""
    return build_namespace_stub(
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )
