"""Shared test-only helpers for fake codegen save/prepare flows."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from ui_designer.utils.scaffold import save_project_model


def _normalize_fake_files(files_or_filename, content=None):
    """Normalize either a single fake file pair or a relpath-to-content mapping."""
    if isinstance(files_or_filename, dict):
        return dict(files_or_filename)
    if content is None:
        raise ValueError("content is required when passing a single fake filename")
    return {str(files_or_filename): content}


def build_materialized_codegen_result(files=None, *, all_generated_files=None):
    """Return a SimpleNamespace shaped like materialized codegen outputs."""
    return SimpleNamespace(
        files=dict(files or {}),
        all_generated_files=dict(all_generated_files or {}),
    )


def build_fake_save_project_and_materialize_codegen(
    files_or_filename,
    content=None,
    *,
    capture=None,
):
    """Return a fake save+materialize callable that still writes scaffold sidecars."""
    fake_files = _normalize_fake_files(files_or_filename, content=content)

    def _materialize(project, output_dir, **kwargs):
        save_project_model(
            project,
            output_dir,
            with_designer_scaffold=True,
            overwrite_scaffold=kwargs.get("overwrite", False),
            remove_legacy_designer_files=kwargs.get("remove_legacy_designer_files", False),
        )
        if capture is not None:
            capture.update(
                {
                    "project": project,
                    "output_dir": output_dir,
                    "kwargs": dict(kwargs),
                }
            )
        output_path = Path(output_dir)
        for relpath, text in fake_files.items():
            target = output_path / relpath
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        return build_materialized_codegen_result(fake_files)

    return _materialize


def build_fake_prepare_project_codegen_outputs(
    files=None,
    *,
    all_generated_files=None,
    capture=None,
):
    """Return a fake prepare callable that records args and runs the prepare hook."""
    prepared = build_materialized_codegen_result(
        files,
        all_generated_files=all_generated_files,
    )

    def _prepare(project_obj, output_dir, backup=True, before_prepare=None, cleanup_legacy=False):
        if callable(before_prepare):
            before_prepare(output_dir)
        if capture is not None:
            capture.update(
                {
                    "project": project_obj,
                    "output_dir": output_dir,
                    "backup": backup,
                    "before_prepare": before_prepare,
                    "cleanup_legacy": cleanup_legacy,
                }
            )
        return prepared

    return _prepare
