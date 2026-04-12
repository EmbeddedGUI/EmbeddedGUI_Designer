"""Tests for shared fake subprocess fixtures."""

from ui_designer.tests.process_fixtures import build_completed_process_result


def test_build_completed_process_result_matches_subprocess_shape():
    result = build_completed_process_result(
        returncode=1,
        stdout="out",
        stderr="err",
    )

    assert result.returncode == 1
    assert result.stdout == "out"
    assert result.stderr == "err"


def test_build_completed_process_result_defaults_to_success_shape():
    result = build_completed_process_result()

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""
