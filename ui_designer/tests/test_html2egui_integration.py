"""Integration tests for scripts/html2egui_helper.py subcommands.

These tests call the actual script via subprocess to verify end-to-end behavior.
"""

import json
import os
import subprocess
import sys
import pytest

from ui_designer.model.workspace import require_designer_sdk_root

# Path to the helper script
SCRIPT_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "html2egui_helper.py")
)
# EmbeddedGUI Designer repo root
REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
SDK_ROOT = require_designer_sdk_root(repo_root=REPO_ROOT, cli_flag="EMBEDDEDGUI_SDK_ROOT")


def _run_helper(*cmd_args, check=True):
    """Run scripts/html2egui_helper.py with given arguments."""
    result = subprocess.run(
        [sys.executable, SCRIPT_PATH] + list(cmd_args),
        # Avoid inheriting a potentially invalid stdin handle on Windows CI,
        # which can raise WinError 6 during subprocess setup.
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=30,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"Command failed (rc={result.returncode}):\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    return result


@pytest.mark.integration
class TestScaffold:
    """Test scaffold subcommand."""

    def test_scaffold_creates_project_structure(self, tmp_path):
        app_name = "TestScaffoldApp"
        app_dir = tmp_path / "example" / app_name

        result = _run_helper(
            "scaffold", "--app", app_name,
            "--width", "320", "--height", "240", "--force",
        )

        real_app_dir = os.path.join(SDK_ROOT, "example", app_name)
        try:
            assert os.path.isdir(real_app_dir)
            egui_file = os.path.join(real_app_dir, f"{app_name}.egui")
            assert os.path.isfile(egui_file)
            assert os.path.isfile(os.path.join(real_app_dir, "app_egui_config.h"))
            assert os.path.isfile(os.path.join(real_app_dir, ".designer", "app_egui_config_designer.h"))
            assert os.path.isfile(os.path.join(real_app_dir, "build.mk"))
            assert os.path.isfile(os.path.join(real_app_dir, ".designer", "build_designer.mk"))
            assert os.path.isdir(os.path.join(real_app_dir, ".eguiproject", "layout"))
            assert os.path.isfile(
                os.path.join(real_app_dir, ".eguiproject", "layout", "main_page.xml")
            )
            egui_content = open(egui_file, "r", encoding="utf-8").read()
            assert 'sdk_root="' in egui_content
            assert 'egui_root="' not in egui_content
        finally:
            # Cleanup
            import shutil
            if os.path.isdir(real_app_dir):
                shutil.rmtree(real_app_dir, ignore_errors=True)

    def test_scaffold_multi_page(self):
        app_name = "TestMultiPageApp"
        result = _run_helper(
            "scaffold", "--app", app_name,
            "--width", "320", "--height", "240",
            "--pages", "home,settings,detail", "--force",
        )

        real_app_dir = os.path.join(SDK_ROOT, "example", app_name)
        try:
            layout_dir = os.path.join(real_app_dir, ".eguiproject", "layout")
            assert os.path.isfile(os.path.join(layout_dir, "home.xml"))
            assert os.path.isfile(os.path.join(layout_dir, "settings.xml"))
            assert os.path.isfile(os.path.join(layout_dir, "detail.xml"))
        finally:
            import shutil
            if os.path.isdir(real_app_dir):
                shutil.rmtree(real_app_dir, ignore_errors=True)


@pytest.mark.integration
class TestGenerateCode:
    """Test generate-code subcommand."""

    def test_generate_code_from_scaffold(self):
        app_name = "TestGenCodeApp"

        # Step 1: Scaffold
        _run_helper(
            "scaffold", "--app", app_name,
            "--width", "240", "--height", "320", "--force",
        )

        real_app_dir = os.path.join(SDK_ROOT, "example", app_name)
        try:
            # Step 2: Generate code
            result = _run_helper("generate-code", "--app", app_name)

            # Verify generated files
            assert os.path.isfile(os.path.join(real_app_dir, ".designer", "main_page.h"))
            assert os.path.isfile(os.path.join(real_app_dir, ".designer", "main_page_layout.c"))
            assert os.path.isfile(os.path.join(real_app_dir, "main_page.c"))
            assert os.path.isfile(os.path.join(real_app_dir, ".designer", "uicode.h"))
            assert os.path.isfile(os.path.join(real_app_dir, ".designer", "uicode.c"))

            # Verify resource config was generated
            rc_path = os.path.join(real_app_dir, "resource", "src", ".designer", "app_resource_config_designer.json")
            assert os.path.isfile(rc_path)
            with open(rc_path, "r") as f:
                data = json.load(f)
            assert "img" in data
            assert "font" in data
        finally:
            import shutil
            if os.path.isdir(real_app_dir):
                shutil.rmtree(real_app_dir, ignore_errors=True)

    def test_scaffold_force_migrates_wrappers_without_overwriting_user_content(self):
        app_name = "TestScaffoldPreserveWrappersApp"
        _run_helper(
            "scaffold", "--app", app_name,
            "--width", "320", "--height", "240", "--force",
        )

        real_app_dir = os.path.join(SDK_ROOT, "example", app_name)
        try:
            build_mk = os.path.join(real_app_dir, "build.mk")
            config_h = os.path.join(real_app_dir, "app_egui_config.h")
            overlay_path = os.path.join(real_app_dir, "resource", "src", "app_resource_config.json")
            designer_build = os.path.join(real_app_dir, ".designer", "build_designer.mk")
            designer_config = os.path.join(real_app_dir, ".designer", "app_egui_config_designer.h")

            with open(build_mk, "w", encoding="utf-8") as f:
                f.write("# custom build\nEGUI_CODE_SRC += legacy.c\n")
            with open(config_h, "w", encoding="utf-8") as f:
                f.write("#define CUSTOM_CFG 1\n")
            with open(overlay_path, "w", encoding="utf-8") as f:
                json.dump({"img": [{"name": "user_logo"}], "font": []}, f)
            with open(designer_build, "w", encoding="utf-8") as f:
                f.write("# stale designer build\n")
            with open(designer_config, "w", encoding="utf-8") as f:
                f.write("#define STALE_DESIGNER_CFG 1\n")

            result = _run_helper(
                "scaffold", "--app", app_name,
                "--width", "320", "--height", "240", "--force",
            )

            with open(build_mk, "r", encoding="utf-8") as f:
                build_content = f.read()
            with open(config_h, "r", encoding="utf-8") as f:
                config_content = f.read()
            with open(overlay_path, "r", encoding="utf-8") as f:
                overlay_data = json.load(f)
            with open(designer_build, "r", encoding="utf-8") as f:
                designer_build_content = f.read()
            with open(designer_config, "r", encoding="utf-8") as f:
                designer_config_content = f.read()

            assert "Updated: build.mk" in result.stdout
            assert "Updated: app_egui_config.h" in result.stdout
            assert "# custom build" in build_content
            assert "EGUI_CODE_SRC += legacy.c" in build_content
            assert ".designer/build_designer.mk" in build_content
            assert "#define CUSTOM_CFG 1" in config_content
            assert '#include ".designer/app_egui_config_designer.h"' in config_content
            assert overlay_data == {"img": [{"name": "user_logo"}], "font": []}
            assert "# stale designer build" not in designer_build_content
            assert "Designer-managed build inputs" in designer_build_content
            assert "STALE_DESIGNER_CFG" not in designer_config_content
            assert "#define EGUI_CONFIG_SCEEN_WIDTH  320" in designer_config_content
        finally:
            import shutil
            if os.path.isdir(real_app_dir):
                shutil.rmtree(real_app_dir, ignore_errors=True)

    def test_generate_code_removes_legacy_root_designer_outputs(self):
        app_name = "TestGenCodeLegacyCleanupApp"

        _run_helper(
            "scaffold", "--app", app_name,
            "--width", "240", "--height", "320", "--force",
        )

        real_app_dir = os.path.join(SDK_ROOT, "example", app_name)
        legacy_files = (
            "main_page.h",
            "main_page_layout.c",
            "uicode.h",
            "uicode.c",
            "egui_strings.h",
            "egui_strings.c",
            "build_designer.mk",
            "app_egui_config_designer.h",
        )
        try:
            for relpath in legacy_files:
                with open(os.path.join(real_app_dir, relpath), "w", encoding="utf-8") as f:
                    f.write(f"// stale legacy file: {relpath}\n")

            _run_helper("generate-code", "--app", app_name)

            for relpath in legacy_files:
                assert not os.path.exists(os.path.join(real_app_dir, relpath))

            assert os.path.isfile(os.path.join(real_app_dir, ".designer", "main_page.h"))
            assert os.path.isfile(os.path.join(real_app_dir, ".designer", "main_page_layout.c"))
            assert os.path.isfile(os.path.join(real_app_dir, ".designer", "uicode.h"))
            assert os.path.isfile(os.path.join(real_app_dir, ".designer", "uicode.c"))
            assert os.path.isfile(os.path.join(real_app_dir, ".designer", "build_designer.mk"))
            assert os.path.isfile(os.path.join(real_app_dir, ".designer", "app_egui_config_designer.h"))
        finally:
            import shutil
            if os.path.isdir(real_app_dir):
                shutil.rmtree(real_app_dir, ignore_errors=True)

    def test_generate_code_skips_designer_reserved_resource_sync(self):
        app_name = "TestGenCodeReservedSyncApp"

        _run_helper(
            "scaffold", "--app", app_name,
            "--width", "240", "--height", "320", "--force",
        )

        real_app_dir = os.path.join(SDK_ROOT, "example", app_name)
        try:
            images_dir = os.path.join(real_app_dir, ".eguiproject", "resources", "images")
            os.makedirs(images_dir, exist_ok=True)
            with open(os.path.join(images_dir, "hero.png"), "wb") as f:
                f.write(b"PNG")
            with open(os.path.join(images_dir, "_generated_text_preview.png"), "wb") as f:
                f.write(b"BAD")

            _run_helper("generate-code", "--app", app_name)

            src_dir = os.path.join(real_app_dir, "resource", "src")
            assert os.path.isfile(os.path.join(src_dir, "hero.png"))
            assert not os.path.exists(os.path.join(src_dir, "_generated_text_preview.png"))
        finally:
            import shutil
            if os.path.isdir(real_app_dir):
                shutil.rmtree(real_app_dir, ignore_errors=True)

    def test_generate_code_syncs_root_resource_files_to_src(self):
        app_name = "TestGenCodeRootResourceSyncApp"

        _run_helper(
            "scaffold", "--app", app_name,
            "--width", "240", "--height", "320", "--force",
        )

        real_app_dir = os.path.join(SDK_ROOT, "example", app_name)
        try:
            resources_dir = os.path.join(real_app_dir, ".eguiproject", "resources")
            os.makedirs(resources_dir, exist_ok=True)
            with open(os.path.join(resources_dir, "kept.txt"), "w", encoding="utf-8") as f:
                f.write("hello\n")
            with open(os.path.join(resources_dir, "_generated_text_demo_16_4.txt"), "w", encoding="utf-8") as f:
                f.write("reserved\n")

            _run_helper("generate-code", "--app", app_name)

            src_dir = os.path.join(real_app_dir, "resource", "src")
            assert os.path.isfile(os.path.join(src_dir, "kept.txt"))
            assert not os.path.exists(os.path.join(src_dir, "_generated_text_demo_16_4.txt"))
        finally:
            import shutil
            if os.path.isdir(real_app_dir):
                shutil.rmtree(real_app_dir, ignore_errors=True)


@pytest.mark.integration
class TestExtractText:
    """Test extract-text subcommand."""

    def test_extract_text_from_html(self, tmp_path):
        html_file = tmp_path / "test.html"
        html_file.write_text(
            '<div class="w-[320px] h-[240px]">'
            '<span>Hello World</span>'
            '<span>Test 123</span>'
            '</div>',
            encoding="utf-8",
        )

        result = _run_helper("extract-text", "--input", str(html_file))
        # Output should contain the extracted characters
        assert "H" in result.stdout
        assert "W" in result.stdout


@pytest.mark.integration
class TestExtractLayout:
    """Test extract-layout subcommand."""

    def test_extract_layout_from_html(self, tmp_path):
        html_file = tmp_path / "test.html"
        html_file.write_text(
            '<div class="w-[320px] h-[240px] bg-slate-900">'
            '  <div class="flex flex-col p-4">'
            '    <span class="text-white text-lg">Title</span>'
            '    <span class="text-slate-400 text-sm">Subtitle</span>'
            '  </div>'
            '</div>',
            encoding="utf-8",
        )

        result = _run_helper("extract-layout", "--input", str(html_file))
        # Output should be valid JSON
        data = json.loads(result.stdout)
        assert "screen" in data
        assert data["screen"]["width"] == 320
        assert data["screen"]["height"] == 240
