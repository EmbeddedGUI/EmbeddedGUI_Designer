"""Tests for CompilerEngine and BuildConfig."""

import os
from unittest.mock import MagicMock, patch

import pytest

from ui_designer.engine.compiler import BuildConfig, CompilerEngine


MAKE_DRYRUN_OUTPUT = """\
echo Compiling  : "example/HelloDesigner_1/main_page.c"
gcc -DEGUI_APP=\\"HelloDesigner_1\\" -DEGUI_PORT=EGUI_PORT_TYPE_PC -O0 -Wall -std=c99 -Iexample/HelloDesigner_1 -Isrc -Iporting/designer -c example/HelloDesigner_1/main_page.c  -o output/obj/example/HelloDesigner_1/main_page.o
echo Compiling  : "example/HelloDesigner_1/.designer/uicode.c"
gcc -DEGUI_APP=\\"HelloDesigner_1\\" -DEGUI_PORT=EGUI_PORT_TYPE_PC -O0 -Wall -std=c99 -Iexample/HelloDesigner_1 -Isrc -Iporting/designer -c example/HelloDesigner_1/.designer/uicode.c  -o output/obj/example/HelloDesigner_1/.designer/uicode.o
echo Compiling  : "porting/designer/main.c"
gcc -DEGUI_APP=\\"HelloDesigner_1\\" -DEGUI_PORT=EGUI_PORT_TYPE_PC -O0 -Wall -std=c99 -Iexample/HelloDesigner_1 -Isrc -Iporting/designer -c porting/designer/main.c  -o output/obj/porting/designer/main.o
echo Linking    : "output/main.exe"
gcc -DEGUI_APP=\\"HelloDesigner_1\\" -O0 -Wall -std=c99 -o output/main.exe output/obj/example/HelloDesigner_1/main_page.o output/obj/example/HelloDesigner_1/.designer/uicode.o output/obj/porting/designer/main.o output/libegui.a -lpthread
echo Building   : "output/main.exe"
"""

MAKE_DRYRUN_OUTPUT_NO_EXE_SUFFIX = """\
echo Compiling  : "example/HelloDesigner_1/main_page.c"
gcc -DEGUI_APP=\\"HelloDesigner_1\\" -DEGUI_PORT=EGUI_PORT_TYPE_PC -O0 -Wall -std=c99 -Iexample/HelloDesigner_1 -Isrc -Iporting/designer -c example/HelloDesigner_1/main_page.c  -o output/obj/example/HelloDesigner_1/main_page.o
echo Linking    : "output/main"
gcc -DEGUI_APP=\\"HelloDesigner_1\\" -O0 -Wall -std=c99 -o output/main output/obj/example/HelloDesigner_1/main_page.o output/libegui.a -lpthread
"""


class TestBuildConfigExtract:
    def _make_result(self, stdout="", returncode=0):
        result = MagicMock()
        result.stdout = stdout
        result.stderr = ""
        result.returncode = returncode
        return result

    @patch("subprocess.run")
    @patch("os.path.getmtime", return_value=1000.0)
    def test_extract_parses_compile_commands(self, mock_mtime, mock_run):
        mock_run.return_value = self._make_result(MAKE_DRYRUN_OUTPUT)
        cfg = BuildConfig.extract("/project", "HelloDesigner_1", "example")

        assert cfg is not None
        assert "gcc" in cfg.compile_cmd_prefix
        assert "-O0" in cfg.compile_cmd_prefix
        assert "-Isrc" in cfg.compile_cmd_prefix

    @patch("subprocess.run")
    @patch("os.path.getmtime", return_value=1000.0)
    def test_extract_parses_src_to_obj_mapping(self, mock_mtime, mock_run):
        mock_run.return_value = self._make_result(MAKE_DRYRUN_OUTPUT)
        cfg = BuildConfig.extract("/project", "HelloDesigner_1", "example")

        assert "main_page.c" in cfg.src_to_obj
        assert "uicode.c" in cfg.src_to_obj
        assert "main.c" in cfg.src_to_obj
        src, obj = cfg.src_to_obj["uicode.c"]
        assert src == "example/HelloDesigner_1/.designer/uicode.c"
        assert obj == "output/obj/example/HelloDesigner_1/.designer/uicode.o"

    @patch("subprocess.run")
    @patch("os.path.getmtime", return_value=1000.0)
    def test_extract_parses_link_command(self, mock_mtime, mock_run):
        mock_run.return_value = self._make_result(MAKE_DRYRUN_OUTPUT)
        cfg = BuildConfig.extract("/project", "HelloDesigner_1", "example")

        assert "output/main.exe" in cfg.link_cmd
        assert "libegui.a" in cfg.link_cmd
        assert "-lpthread" in cfg.link_cmd

    @patch("subprocess.run")
    @patch("os.path.getmtime", return_value=1000.0)
    def test_extract_accepts_link_command_without_windows_exe_suffix(self, mock_mtime, mock_run):
        mock_run.return_value = self._make_result(MAKE_DRYRUN_OUTPUT_NO_EXE_SUFFIX)
        cfg = BuildConfig.extract("/project", "HelloDesigner_1", "example")

        assert cfg is not None
        assert "output/main" in cfg.link_cmd

    @patch("subprocess.run")
    @patch("os.path.getmtime", return_value=1000.0)
    def test_extract_retries_without_exe_suffix_when_preferred_target_missing(self, mock_mtime, mock_run):
        mock_run.side_effect = [
            MagicMock(returncode=2, stdout="", stderr="make: *** No rule to make target 'main.exe'.  Stop.\n"),
            self._make_result(MAKE_DRYRUN_OUTPUT_NO_EXE_SUFFIX),
        ]

        cfg = BuildConfig.extract("/project", "HelloDesigner_1", "example", target_name="main.exe")

        assert cfg is not None
        assert "output/main" in cfg.link_cmd
        assert mock_run.call_args_list[0][0][0][4] == "main.exe"
        assert mock_run.call_args_list[1][0][0][4] == "main"

    @patch("subprocess.run")
    @patch("os.path.getmtime", return_value=1000.0)
    def test_extract_generates_presplit_args(self, mock_mtime, mock_run):
        mock_run.return_value = self._make_result(MAKE_DRYRUN_OUTPUT)
        cfg = BuildConfig.extract("/project", "HelloDesigner_1", "example")

        assert isinstance(cfg.compile_cmd_args, list)
        assert cfg.compile_cmd_args[0] == "gcc"
        assert isinstance(cfg.link_cmd_args, list)
        assert cfg.link_cmd_args[0] == "gcc"

    @patch("subprocess.run")
    @patch("os.path.getmtime", return_value=1000.0)
    def test_extract_tracks_project_designer_makefiles(self, mock_mtime, mock_run):
        mock_run.return_value = self._make_result(MAKE_DRYRUN_OUTPUT)
        cfg = BuildConfig.extract("/project", "HelloDesigner_1", "example")

        assert os.path.join("example", "HelloDesigner_1", ".designer", "build_designer.mk") in cfg._makefile_mtimes
        assert os.path.join("example", "HelloDesigner_1", "build_designer.mk") not in cfg._makefile_mtimes

    @patch("subprocess.run")
    def test_extract_returns_none_on_make_failure(self, mock_run):
        mock_run.return_value = self._make_result("error", returncode=1)
        assert BuildConfig.extract("/project", "HelloDesigner_1", "example") is None

    @patch("subprocess.run")
    def test_extract_returns_none_on_empty_output(self, mock_run):
        mock_run.return_value = self._make_result("")
        assert BuildConfig.extract("/project", "HelloDesigner_1", "example") is None

    @patch("subprocess.run", side_effect=FileNotFoundError)
    def test_extract_returns_none_when_make_missing(self, mock_run):
        assert BuildConfig.extract("/project", "HelloDesigner_1", "example") is None


class TestBuildConfigIsValid:
    def test_valid_when_mtimes_match(self, tmp_path):
        cfg = BuildConfig()
        makefile = tmp_path / "Makefile"
        makefile.write_text("test")
        cfg._makefile_mtimes = {"Makefile": os.path.getmtime(str(makefile))}
        assert cfg.is_valid(str(tmp_path))

    def test_invalid_when_mtime_changes(self, tmp_path):
        cfg = BuildConfig()
        makefile = tmp_path / "Makefile"
        makefile.write_text("test")
        cfg._makefile_mtimes = {"Makefile": os.path.getmtime(str(makefile)) - 1}
        assert not cfg.is_valid(str(tmp_path))

    def test_invalid_when_file_missing(self, tmp_path):
        cfg = BuildConfig()
        cfg._makefile_mtimes = {"missing": 1.0}
        assert not cfg.is_valid(str(tmp_path))

    def test_invalid_when_no_mtimes(self, tmp_path):
        cfg = BuildConfig()
        assert not cfg.is_valid(str(tmp_path))


class TestCompilerFastPath:
    def _make_engine(self, tmp_path):
        engine = CompilerEngine.__new__(CompilerEngine)
        engine.project_root = str(tmp_path)
        engine.app_dir = str(tmp_path / "example" / "TestApp")
        engine.app_name = "TestApp"
        engine.app_root_arg = "example"
        engine._app_root_error = ""
        engine._compile_count = 0
        engine._last_changed_files = []
        engine._build_config = None
        engine._screen_width = 240
        engine._screen_height = 320
        engine._last_runtime_error = ""
        engine._preview_build_probe_ran = False
        engine._preview_build_error = ""
        engine._preview_make_target = ""
        engine.bridge = MagicMock()
        return engine

    def _make_config(self, tmp_path):
        cfg = BuildConfig()
        cfg.compile_cmd_prefix = "gcc -O0 -Wall -Isrc"
        cfg.link_cmd = "gcc -o output/main.exe output/obj/.designer/uicode.o output/libegui.a"
        cfg.compile_cmd_args = ["gcc", "-O0", "-Wall", "-Isrc"]
        cfg.link_cmd_args = ["gcc", "-o", "output/main.exe", "output/obj/.designer/uicode.o", "output/libegui.a"]
        cfg.src_to_obj = {
            "uicode.c": ("example/TestApp/.designer/uicode.c", "output/obj/.designer/uicode.o"),
        }
        makefile = tmp_path / "Makefile"
        makefile.write_text("test")
        cfg._makefile_mtimes = {"Makefile": os.path.getmtime(str(makefile))}
        return cfg

    @patch("subprocess.run")
    @patch("subprocess.Popen")
    def test_fast_path_used_when_config_valid(self, mock_popen, mock_run, tmp_path):
        engine = self._make_engine(tmp_path)
        engine._build_config = self._make_config(tmp_path)
        engine._last_changed_files = ["uicode.c"]
        (tmp_path / "output").mkdir()
        (tmp_path / "output" / "libegui.a").write_bytes(b"lib")

        fake_proc = MagicMock()
        fake_proc.communicate.return_value = (b"", b"")
        fake_proc.returncode = 0
        mock_popen.return_value = fake_proc
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        success, _ = engine.compile()
        assert success
        assert mock_popen.call_count == 1
        assert mock_popen.call_args[1]["shell"] is False
        assert mock_run.call_args[1]["shell"] is False

    def test_write_project_files_creates_parent_dirs_for_nested_designer_outputs(self, tmp_path):
        engine = self._make_engine(tmp_path)

        written = engine.write_project_files(
            {
                ".designer/build_designer.mk": "# designer build\n",
                ".designer/app_egui_config_designer.h": "#define TEST_FLAG 1\n",
            }
        )

        assert ".designer/build_designer.mk" in written
        assert ".designer/app_egui_config_designer.h" in written
        assert (tmp_path / "example" / "TestApp" / ".designer" / "build_designer.mk").read_text(encoding="utf-8") == (
            "# designer build\n"
        )
        assert (tmp_path / "example" / "TestApp" / ".designer" / "app_egui_config_designer.h").read_text(encoding="utf-8") == (
            "#define TEST_FLAG 1\n"
        )

    def test_write_project_files_removes_legacy_root_counterparts_even_when_no_nested_file_changes(self, tmp_path):
        engine = self._make_engine(tmp_path)
        app_dir = tmp_path / "example" / "TestApp"
        (app_dir / ".designer").mkdir(parents=True)
        (app_dir / ".designer" / "uicode.c").write_text("int ui(void) { return 0; }\n", encoding="utf-8")
        (app_dir / "uicode.c").write_text("legacy root copy\n", encoding="utf-8")

        written = engine.write_project_files({}, generated_relpaths=[".designer/uicode.c"])

        assert written == []
        assert not (app_dir / "uicode.c").exists()
        assert (app_dir / ".designer" / "uicode.c").is_file()

    @patch("subprocess.run")
    def test_falls_back_to_make_without_config(self, mock_run, tmp_path):
        engine = self._make_engine(tmp_path)
        engine._last_changed_files = ["uicode.c"]
        mock_run.return_value = MagicMock(returncode=0, stdout="ok\n", stderr="")

        success, _ = engine.compile()
        assert success
        assert mock_run.call_args_list[0][0][0][0] == "make"

    @patch("subprocess.run")
    def test_falls_back_to_make_when_no_libegui(self, mock_run, tmp_path):
        engine = self._make_engine(tmp_path)
        engine._build_config = self._make_config(tmp_path)
        engine._last_changed_files = ["uicode.c"]
        mock_run.return_value = MagicMock(returncode=0, stdout="ok\n", stderr="")

        success, _ = engine.compile()
        assert success
        assert mock_run.call_args_list[0][0][0][0] == "make"

    @patch("subprocess.run")
    def test_falls_back_when_unknown_file(self, mock_run, tmp_path):
        engine = self._make_engine(tmp_path)
        engine._build_config = self._make_config(tmp_path)
        engine._last_changed_files = ["other.c"]
        (tmp_path / "output").mkdir()
        (tmp_path / "output" / "libegui.a").write_bytes(b"lib")
        mock_run.return_value = MagicMock(returncode=0, stdout="ok\n", stderr="")

        success, _ = engine.compile()
        assert success
        assert mock_run.call_args_list[0][0][0][0] == "make"

    @patch("subprocess.run")
    @patch("subprocess.Popen")
    def test_fast_compile_failure_falls_back_to_make(self, mock_popen, mock_run, tmp_path):
        engine = self._make_engine(tmp_path)
        engine._build_config = self._make_config(tmp_path)
        engine._last_changed_files = ["uicode.c"]
        (tmp_path / "output").mkdir()
        (tmp_path / "output" / "libegui.a").write_bytes(b"lib")

        fake_proc = MagicMock()
        fake_proc.communicate.return_value = (b"error\n", b"")
        fake_proc.returncode = 1
        fake_proc.kill = MagicMock()
        mock_popen.return_value = fake_proc
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="ok\n", stderr=""),
            MagicMock(returncode=0, stdout=MAKE_DRYRUN_OUTPUT, stderr=""),
        ]

        with patch("os.path.getmtime", return_value=1000.0):
            success, _ = engine.compile()
        assert success

    @patch("subprocess.run")
    def test_make_compile_extracts_config(self, mock_run, tmp_path):
        engine = self._make_engine(tmp_path)
        make_result = MagicMock(returncode=0, stdout="ok\n", stderr="")
        dryrun_result = MagicMock(returncode=0, stdout=MAKE_DRYRUN_OUTPUT, stderr="")
        mock_run.side_effect = [make_result, dryrun_result]

        with patch("os.path.getmtime", return_value=1000.0):
            success, _ = engine._make_compile()

        assert success
        assert engine._build_config is not None
        assert "uicode.c" in engine._build_config.src_to_obj

    @patch("subprocess.run")
    def test_force_rebuild_uses_always_make_build(self, mock_run, tmp_path):
        engine = self._make_engine(tmp_path)
        engine._build_config = self._make_config(tmp_path)
        make_result = MagicMock(returncode=0, stdout="build ok\n", stderr="")
        dryrun_result = MagicMock(returncode=0, stdout=MAKE_DRYRUN_OUTPUT, stderr="")
        mock_run.side_effect = [make_result, dryrun_result]

        with patch("os.path.getmtime", return_value=1000.0):
            success, output = engine.compile(force_rebuild=True)

        assert success
        assert mock_run.call_args_list[0][0][0][:4] == ["make", "-B", "-j", engine.get_preview_make_target_name()]
        assert "build ok" in output
        assert engine._build_config is not None

    @patch("subprocess.run")
    def test_make_compile_falls_back_to_bare_main_target(self, mock_run, tmp_path):
        engine = self._make_engine(tmp_path)
        engine._preview_make_target = "main.exe"
        mock_run.side_effect = [
            MagicMock(returncode=2, stdout="", stderr="make: *** No rule to make target 'main.exe'.  Stop.\n"),
            MagicMock(returncode=0, stdout="build ok\n", stderr=""),
            MagicMock(returncode=0, stdout=MAKE_DRYRUN_OUTPUT_NO_EXE_SUFFIX, stderr=""),
        ]

        with patch("os.path.getmtime", return_value=1000.0):
            success, output = engine.compile(force_rebuild=True)

        assert success
        assert "build ok" in output
        assert engine.get_preview_make_target_name() == "main"
        assert mock_run.call_args_list[0][0][0][:4] == ["make", "-B", "-j", "main.exe"]
        assert mock_run.call_args_list[1][0][0][:4] == ["make", "-B", "-j", "main"]

    @patch("subprocess.run")
    def test_force_rebuild_returns_build_failure_output(self, mock_run, tmp_path):
        engine = self._make_engine(tmp_path)
        engine._build_config = self._make_config(tmp_path)
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="build failed\n")

        success, output = engine.compile(force_rebuild=True)

        assert not success
        assert "build failed" in output
        assert mock_run.call_count == 1

    def test_write_uicode_sets_changed(self, tmp_path):
        engine = self._make_engine(tmp_path)
        os.makedirs(engine.app_dir, exist_ok=True)
        engine.write_uicode("int main() {}")
        assert engine._last_changed_files == ["uicode.c"]
        assert os.path.isfile(os.path.join(engine.app_dir, ".designer", "uicode.c"))

    def test_write_uicode_removes_legacy_root_copy(self, tmp_path):
        engine = self._make_engine(tmp_path)
        os.makedirs(engine.app_dir, exist_ok=True)
        legacy_uicode = os.path.join(engine.app_dir, "uicode.c")
        with open(legacy_uicode, "w", encoding="utf-8") as f:
            f.write("legacy root copy\n")

        engine.write_uicode("int main() {}")

        assert not os.path.exists(legacy_uicode)
        assert os.path.isfile(os.path.join(engine.app_dir, ".designer", "uicode.c"))

    def test_write_uicode_removes_legacy_root_copies_for_existing_designer_outputs(self, tmp_path):
        engine = self._make_engine(tmp_path)
        designer_dir = tmp_path / "example" / "TestApp" / ".designer"
        designer_dir.mkdir(parents=True)
        (designer_dir / "uicode.h").write_text("// designer header\n", encoding="utf-8")
        (designer_dir / "egui_strings.h").write_text("// designer strings header\n", encoding="utf-8")
        (designer_dir / "egui_strings.c").write_text("// designer strings source\n", encoding="utf-8")
        (designer_dir / "main_page.h").write_text("// designer page header\n", encoding="utf-8")
        (designer_dir / "main_page_layout.c").write_text("// designer page layout\n", encoding="utf-8")

        legacy_root_files = (
            "uicode.h",
            "egui_strings.h",
            "egui_strings.c",
            "main_page.h",
            "main_page_layout.c",
        )
        for relpath in legacy_root_files:
            (tmp_path / "example" / "TestApp" / relpath).write_text("// legacy root copy\n", encoding="utf-8")

        engine.write_uicode("int main() {}")

        for relpath in legacy_root_files:
            assert not os.path.exists(os.path.join(engine.app_dir, relpath))


class TestCompilerRuntime:
    def _make_engine(self, tmp_path):
        engine = CompilerEngine.__new__(CompilerEngine)
        engine.project_root = str(tmp_path)
        engine.app_dir = str(tmp_path / "app")
        engine.app_name = "TestApp"
        engine.app_root_arg = "example"
        engine._app_root_error = ""
        engine._compile_count = 0
        engine._screen_width = 240
        engine._screen_height = 320
        engine._last_runtime_error = ""
        engine._preview_build_probe_ran = False
        engine._preview_build_error = ""
        engine._preview_make_target = ""
        engine.bridge = MagicMock()
        return engine

    def test_validate_preview_reports_bridge_error(self, tmp_path):
        engine = self._make_engine(tmp_path)
        engine.bridge.is_running = False
        ready, err = engine.validate_preview()
        assert not ready
        assert "not running" in err

    @patch("ui_designer.engine.compiler._run_make_dry_run_target")
    def test_preview_build_probe_reports_missing_main_target(self, mock_dry_run, tmp_path):
        engine = self._make_engine(tmp_path)
        engine._preview_make_target = "main.exe"
        mock_dry_run.side_effect = [
            MagicMock(returncode=2, stdout="", stderr="make: *** No rule to make target 'main.exe'.  Stop.\n"),
            MagicMock(returncode=2, stdout="", stderr="make: *** No rule to make target 'main'.  Stop.\n"),
        ]

        assert engine.ensure_preview_build_available() is False
        assert "preview build target unavailable" in engine.get_preview_build_error().lower()
        assert engine.ensure_preview_build_available() is False
        assert mock_dry_run.call_count == 2

    @patch("ui_designer.engine.compiler._run_make_dry_run_target")
    def test_preview_build_probe_falls_back_to_bare_main_target(self, mock_dry_run, tmp_path):
        engine = self._make_engine(tmp_path)
        engine._preview_make_target = "main.exe"
        mock_dry_run.side_effect = [
            MagicMock(returncode=2, stdout="", stderr="make: *** No rule to make target 'main.exe'.  Stop.\n"),
            MagicMock(returncode=0, stdout="dry run ok\n", stderr=""),
        ]

        assert engine.ensure_preview_build_available() is True
        assert engine.get_preview_build_error() == ""
        assert engine.get_preview_make_target_name() == "main"
        assert mock_dry_run.call_count == 2

    @patch("ui_designer.engine.compiler._run_make_dry_run_target")
    def test_reset_preview_build_probe_allows_retry(self, mock_dry_run, tmp_path):
        engine = self._make_engine(tmp_path)
        engine._preview_make_target = "main.exe"
        mock_dry_run.side_effect = [
            MagicMock(returncode=2, stdout="", stderr="make: *** No rule to make target 'main.exe'.  Stop.\n"),
            MagicMock(returncode=2, stdout="", stderr="make: *** No rule to make target 'main'.  Stop.\n"),
            MagicMock(returncode=0, stdout="dry run ok\n", stderr=""),
        ]

        assert engine.ensure_preview_build_available() is False

        engine.reset_preview_build_probe()
        engine._preview_make_target = "main.exe"

        assert engine.ensure_preview_build_available() is True
        assert engine.get_preview_build_error() == ""
        assert mock_dry_run.call_count == 3

    def test_executable_paths_use_shared_output_helpers(self, tmp_path):
        engine = self._make_engine(tmp_path)
        main_name = "main.exe" if os.name == "nt" else "main"
        run_name = "designer_run_1.exe" if os.name == "nt" else "designer_run_1"

        assert engine.exe_path == os.path.join(str(tmp_path), "output", main_name)
        assert engine._run_exe_path(1) == os.path.join(str(tmp_path), "output", run_name)

    def test_uicode_path_falls_back_to_shared_example_app_dir(self, tmp_path):
        engine = self._make_engine(tmp_path)
        engine.app_dir = ""

        assert engine.uicode_path == os.path.join(
            str(tmp_path),
            "example",
            "TestApp",
            ".designer",
            "uicode.c",
        )

    def test_validate_preview_accepts_correct_frame(self, tmp_path):
        engine = self._make_engine(tmp_path)
        engine.bridge.is_running = True
        engine.bridge.render.return_value = bytes(240 * 320 * 3)
        ready, err = engine.validate_preview()
        assert ready
        assert err == ""

    def test_get_last_runtime_error_prefers_app_root_error(self, tmp_path):
        engine = self._make_engine(tmp_path)
        engine._app_root_error = "External app must be on the same drive as the SDK root"
        assert "same drive" in engine.get_last_runtime_error()
        assert engine.can_build() is False
        assert "same drive" in engine.get_build_error()

    def test_init_records_cross_drive_error(self, tmp_path):
        with patch("ui_designer.engine.compiler.compute_make_app_root_arg", side_effect=ValueError("cross drive")):
            with patch.object(CompilerEngine, "_cleanup_stale_processes"):
                engine = CompilerEngine(str(tmp_path), str(tmp_path / "app"), "TestApp")
        assert engine.get_last_runtime_error() == "cross drive"
        assert engine.get_build_error() == "cross drive"
        assert not engine.is_exe_ready()

    def test_init_records_external_alias_creation_error(self, tmp_path):
        with patch("ui_designer.engine.compiler.compute_make_app_root_arg", return_value="../external"):
            with patch.object(CompilerEngine, "_ensure_external_app_root_alias", side_effect=RuntimeError("alias unsupported")):
                with patch.object(CompilerEngine, "_cleanup_stale_processes"):
                    engine = CompilerEngine(str(tmp_path), str(tmp_path / "app"), "TestApp")
        assert engine.get_last_runtime_error() == "alias unsupported"
        assert engine.get_build_error() == "alias unsupported"
        assert engine.can_build() is False

    def test_init_rewrites_external_parent_with_alias(self, tmp_path):
        external_app = tmp_path.parent / "external" / "TestApp"
        with patch("ui_designer.engine.compiler.compute_make_app_root_arg", return_value="../external"):
            with patch.object(CompilerEngine, "_ensure_external_app_root_alias", return_value="build/ui_designer_external/abc123") as mock_alias:
                with patch.object(CompilerEngine, "_cleanup_stale_processes"):
                    engine = CompilerEngine(str(tmp_path), str(external_app), "TestApp")
        assert engine.app_root_arg == "build/ui_designer_external/abc123"
        mock_alias.assert_called_once_with()
