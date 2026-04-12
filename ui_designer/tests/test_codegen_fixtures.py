"""Tests for shared fake codegen fixtures."""

from ui_designer.tests.codegen_fixtures import (
    build_fake_prepare_project_codegen_outputs,
    build_fake_save_project_and_materialize_codegen,
    build_generated_always_codegen_files,
    build_materialized_codegen_result,
)
from ui_designer.utils.scaffold import build_empty_project_model


class TestCodegenFixtures:
    def test_build_materialized_codegen_result_matches_codegen_shape(self):
        result = build_materialized_codegen_result(
            {"main_page.c": "// generated\n"},
            all_generated_files={".designer/uicode.c": ("// generated\n", "generated_always")},
        )

        assert result.files == {"main_page.c": "// generated\n"}
        assert result.all_generated_files == {
            ".designer/uicode.c": ("// generated\n", "generated_always")
        }

    def test_build_generated_always_codegen_files_maps_content_to_generated_always(self):
        assert build_generated_always_codegen_files(
            {".designer/uicode.c": "// generated\n"}
        ) == {
            ".designer/uicode.c": ("// generated\n", "generated_always")
        }

    def test_build_fake_save_project_and_materialize_codegen_writes_scaffold_and_files(self, tmp_path):
        project_dir = tmp_path / "FakeMaterializeDemo"
        project = build_empty_project_model(
            "FakeMaterializeDemo",
            320,
            240,
            sdk_root="D:/sdk",
            project_dir=str(project_dir),
            pages=["home"],
        )
        seen = {}
        fake_materialize = build_fake_save_project_and_materialize_codegen(
            {"generated.c": "// generated\n"},
            capture=seen,
        )

        result = fake_materialize(
            project,
            str(project_dir),
            overwrite=True,
            remove_legacy_designer_files=True,
        )

        assert (project_dir / "FakeMaterializeDemo.egui").is_file()
        assert (project_dir / "build.mk").is_file()
        assert (project_dir / ".designer" / "build_designer.mk").is_file()
        assert (project_dir / "generated.c").read_text(encoding="utf-8") == "// generated\n"
        assert result.files == {"generated.c": "// generated\n"}
        assert result.all_generated_files == {}
        assert seen["project"] is project
        assert seen["output_dir"] == str(project_dir)
        assert seen["kwargs"] == {
            "overwrite": True,
            "remove_legacy_designer_files": True,
        }

    def test_build_fake_prepare_project_codegen_outputs_runs_prepare_hook_and_captures_args(self):
        hook_calls = []
        seen = {}
        fake_prepare = build_fake_prepare_project_codegen_outputs(
            {".designer/uicode.c": "// rebuild\n"},
            capture=seen,
        )

        result = fake_prepare(
            "project",
            "D:/workspace/Demo",
            backup=False,
            before_prepare=lambda output_dir: hook_calls.append(output_dir),
            cleanup_legacy=True,
        )

        assert hook_calls == ["D:/workspace/Demo"]
        assert result.files == {".designer/uicode.c": "// rebuild\n"}
        assert result.all_generated_files == {
            ".designer/uicode.c": ("// rebuild\n", "generated_always")
        }
        assert seen["project"] == "project"
        assert seen["output_dir"] == "D:/workspace/Demo"
        assert seen["backup"] is False
        assert callable(seen["before_prepare"]) is True
        assert seen["cleanup_legacy"] is True
