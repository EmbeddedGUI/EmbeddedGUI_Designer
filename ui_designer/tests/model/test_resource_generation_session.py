import json
import subprocess
import sys
from pathlib import Path

import pytest

from ui_designer.model.resource_generation_session import (
    GenerationPaths,
    ResourceGenerationSession,
    infer_generation_paths,
)
from ui_designer.tests.sdk_builders import build_test_sdk_root


def _build_sdk_with_generator(root: Path) -> Path:
    sdk_root = build_test_sdk_root(root)
    tools_dir = sdk_root / "scripts" / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    (tools_dir / "build_in").mkdir(parents=True, exist_ok=True)
    (tools_dir / "app_resource_generate.py").write_text("print('ok')\n", encoding="utf-8")
    return sdk_root


def test_infer_generation_paths_prefers_standard_resource_layout(tmp_path):
    config_path = tmp_path / "DemoApp" / "resource" / "src" / "app_resource_config.json"
    paths = infer_generation_paths(str(config_path))

    assert paths.config_path == str(config_path.resolve())
    assert paths.source_dir == str(config_path.parent.resolve())
    assert paths.workspace_dir == str(config_path.parent.parent.resolve())
    assert paths.bin_output_dir == str(config_path.parent.parent.resolve())


def test_session_merged_config_uses_adjacent_designer_overlay(tmp_path):
    source_dir = tmp_path / "resource" / "src"
    designer_dir = source_dir / ".designer"
    designer_dir.mkdir(parents=True)
    (designer_dir / "app_resource_config_designer.json").write_text(
        json.dumps(
            {
                "img": [],
                "font": [
                    {
                        "file": "demo.ttf",
                        "pixelsize": "16",
                        "fontbitsize": "4",
                        "external": "0",
                        "text": ".designer/_generated_text_demo_16_4.txt",
                    }
                ],
                "mp4": [],
            },
            ensure_ascii=False,
            indent=4,
        ),
        encoding="utf-8",
    )

    session = ResourceGenerationSession()
    session.reset(
        GenerationPaths(source_dir=str(source_dir)),
        {
            "img": [],
            "font": [
                {
                    "file": "demo.ttf",
                    "pixelsize": "16",
                    "fontbitsize": "4",
                    "external": "1",
                    "text": "custom.txt",
                }
            ],
            "mp4": [],
        },
    )

    merged = session.merged_config()

    assert merged["font"] == [
        {
            "file": "demo.ttf",
            "pixelsize": "16",
            "fontbitsize": "4",
            "external": "1",
            "text": ".designer/_generated_text_demo_16_4.txt,custom.txt",
        }
    ]


def test_session_load_from_file_rejects_designer_managed_config(tmp_path):
    source_dir = tmp_path / "resource" / "src"
    designer_config = source_dir / ".designer" / "app_resource_config_designer.json"
    designer_config.parent.mkdir(parents=True)
    designer_config.write_text("{\"img\": [], \"font\": [], \"mp4\": []}\n", encoding="utf-8")
    expected_user_config = source_dir / "app_resource_config.json"

    session = ResourceGenerationSession()

    with pytest.raises(ValueError) as excinfo:
        session.load_from_file(str(designer_config))

    assert "Designer-managed" in str(excinfo.value)
    assert str(expected_user_config.resolve()) in str(excinfo.value)


def test_session_save_user_config_rejects_designer_managed_config_path(tmp_path):
    source_dir = tmp_path / "resource" / "src"
    designer_config = source_dir / ".designer" / "app_resource_config_designer.json"

    session = ResourceGenerationSession()
    session.reset(
        GenerationPaths(
            config_path=str(source_dir / "app_resource_config.json"),
            source_dir=str(source_dir),
        ),
        {
            "img": [],
            "font": [],
            "mp4": [],
        },
    )

    with pytest.raises(ValueError) as excinfo:
        session.save_user_config(str(designer_config))

    assert "Designer-managed" in str(excinfo.value)
    assert not designer_config.exists()


def test_validation_issues_reject_designer_managed_source_dir(tmp_path):
    sdk_root = _build_sdk_with_generator(tmp_path / "sdk")
    source_dir = tmp_path / "resource" / "src" / ".designer"
    workspace_dir = tmp_path / "workspace"
    bin_output_dir = tmp_path / "bin"
    source_dir.mkdir(parents=True)

    session = ResourceGenerationSession(str(sdk_root))
    session.reset(
        GenerationPaths(
            config_path=str(tmp_path / "resource" / "src" / "app_resource_config.json"),
            source_dir=str(source_dir),
            workspace_dir=str(workspace_dir),
            bin_output_dir=str(bin_output_dir),
        ),
        {
            "img": [],
            "font": [],
            "mp4": [],
        },
    )

    issues = session.validation_issues(for_generation=True)

    assert any(issue.code == "source_dir_reserved" for issue in issues)


def test_stage_workspace_copies_source_tree_and_writes_current_user_config(tmp_path):
    source_dir = tmp_path / "source"
    workspace_dir = tmp_path / "workspace"
    (source_dir / ".designer").mkdir(parents=True)
    (source_dir / "images").mkdir(parents=True)
    (source_dir / "hero.png").write_bytes(b"PNG")
    (source_dir / "notes.txt").write_text("hello\n", encoding="utf-8")
    (source_dir / ".designer" / "app_resource_config_designer.json").write_text("{\"img\": [], \"font\": [], \"mp4\": []}\n", encoding="utf-8")

    session = ResourceGenerationSession()
    session.reset(
        GenerationPaths(
            config_path=str(source_dir / "app_resource_config.json"),
            source_dir=str(source_dir),
            workspace_dir=str(workspace_dir),
            bin_output_dir=str(workspace_dir / "bin"),
        ),
        {
            "img": [{"file": "hero.png", "format": "rgb565", "alpha": "4", "external": "0"}],
            "font": [],
            "mp4": [],
        },
    )

    staged_config_path = session.stage_workspace()

    assert Path(staged_config_path).is_file()
    assert (workspace_dir / "src" / "hero.png").is_file()
    assert (workspace_dir / "src" / "notes.txt").is_file()
    assert (workspace_dir / "src" / ".designer" / "app_resource_config_designer.json").is_file()
    assert json.loads((workspace_dir / "src" / "app_resource_config.json").read_text(encoding="utf-8")) == session.user_data


def test_stage_workspace_skips_legacy_designer_artifacts_outside_designer_dir(tmp_path):
    source_dir = tmp_path / "source"
    workspace_dir = tmp_path / "workspace"
    designer_dir = source_dir / ".designer"
    designer_dir.mkdir(parents=True)
    (source_dir / "hero.png").write_bytes(b"PNG")
    (source_dir / "app_resource_config_designer.json").write_text("{\"img\": [], \"font\": [], \"mp4\": []}\n", encoding="utf-8")
    (source_dir / ".app_resource_config_merged.json").write_text("{\"img\": [], \"font\": [], \"mp4\": []}\n", encoding="utf-8")
    (source_dir / "_generated_text_demo_16_4.txt").write_text("legacy\n", encoding="utf-8")
    (designer_dir / "app_resource_config_designer.json").write_text("{\"img\": [], \"font\": [], \"mp4\": []}\n", encoding="utf-8")
    (designer_dir / "_generated_text_demo_16_4.txt").write_text("designer\n", encoding="utf-8")

    session = ResourceGenerationSession()
    session.reset(
        GenerationPaths(
            config_path=str(source_dir / "app_resource_config.json"),
            source_dir=str(source_dir),
            workspace_dir=str(workspace_dir),
            bin_output_dir=str(workspace_dir / "bin"),
        ),
        {
            "img": [{"file": "hero.png", "format": "rgb565", "alpha": "4", "external": "0"}],
            "font": [],
            "mp4": [],
        },
    )

    session.stage_workspace()

    assert (workspace_dir / "src" / "hero.png").is_file()
    assert not (workspace_dir / "src" / "app_resource_config_designer.json").exists()
    assert not (workspace_dir / "src" / ".app_resource_config_merged.json").exists()
    assert not (workspace_dir / "src" / "_generated_text_demo_16_4.txt").exists()
    assert (workspace_dir / "src" / ".designer" / "app_resource_config_designer.json").is_file()
    assert (workspace_dir / "src" / ".designer" / "_generated_text_demo_16_4.txt").read_text(encoding="utf-8") == "designer\n"


def test_stage_generation_config_expands_multi_text_font_entries_from_merged_config(tmp_path):
    source_dir = tmp_path / "source"
    workspace_dir = tmp_path / "workspace"
    designer_dir = source_dir / ".designer"
    designer_dir.mkdir(parents=True)
    (designer_dir / "app_resource_config_designer.json").write_text(
        json.dumps(
            {
                "img": [],
                "font": [
                    {
                        "file": "demo.ttf",
                        "name": "demo",
                        "pixelsize": "16",
                        "fontbitsize": "4",
                        "external": "0",
                        "text": ".designer/generated.txt",
                    }
                ],
                "mp4": [],
            },
            ensure_ascii=False,
            indent=4,
        )
        + "\n",
        encoding="utf-8",
    )

    session = ResourceGenerationSession()
    session.reset(
        GenerationPaths(
            config_path=str(source_dir / "app_resource_config.json"),
            source_dir=str(source_dir),
            workspace_dir=str(workspace_dir),
            bin_output_dir=str(workspace_dir / "bin"),
        ),
        {
            "img": [],
            "font": [
                {
                    "file": "demo.ttf",
                    "name": "demo",
                    "pixelsize": "16",
                    "fontbitsize": "4",
                    "external": "0",
                    "text": "ui_text.txt,charset.txt",
                }
            ],
            "mp4": [],
        },
    )

    session.stage_workspace()
    staged_config_path = session.stage_generation_config()
    staged_config = json.loads(Path(staged_config_path).read_text(encoding="utf-8"))

    assert Path(staged_config_path).is_file()
    assert staged_config["font"] == [
        {
            "file": "demo.ttf",
            "name": "demo",
            "pixelsize": "16",
            "fontbitsize": "4",
            "external": "0",
            "text": ".designer/generated.txt",
        },
        {
            "file": "demo.ttf",
            "name": "demo",
            "pixelsize": "16",
            "fontbitsize": "4",
            "external": "0",
            "text": "ui_text.txt",
        },
        {
            "file": "demo.ttf",
            "name": "demo",
            "pixelsize": "16",
            "fontbitsize": "4",
            "external": "0",
            "text": "charset.txt",
        },
    ]


def test_run_generation_uses_sdk_script_and_workspace_paths(tmp_path, monkeypatch):
    sdk_root = _build_sdk_with_generator(tmp_path / "sdk")
    source_dir = tmp_path / "source"
    workspace_dir = tmp_path / "workspace"
    bin_output_dir = tmp_path / "bin"
    source_dir.mkdir()

    captured = {}

    def _fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 0, stdout="generated\n", stderr="")

    monkeypatch.setattr("ui_designer.model.resource_generation_session.subprocess.run", _fake_run)

    session = ResourceGenerationSession(str(sdk_root))
    session.reset(
        GenerationPaths(
            config_path=str(source_dir / "app_resource_config.json"),
            source_dir=str(source_dir),
            workspace_dir=str(workspace_dir),
            bin_output_dir=str(bin_output_dir),
        ),
        {
            "img": [],
            "font": [],
            "mp4": [],
        },
    )

    result = session.run_generation()

    staged_generation_config = workspace_dir / "src" / ".designer" / ".app_resource_config_merged.json"
    assert result.success is True
    assert captured["command"][0] == sys.executable
    assert captured["command"][1] == str((sdk_root / "scripts" / "tools" / "app_resource_generate.py").resolve())
    assert captured["command"][2:] == [
        "-r",
        str(workspace_dir.resolve()),
        "-o",
        str(bin_output_dir.resolve()),
        "-f",
        "true",
        "--config",
        str(staged_generation_config.resolve()),
    ]
    assert captured["kwargs"]["cwd"] == str(sdk_root.resolve())
    assert (workspace_dir / "src" / "app_resource_config.json").is_file()
    assert staged_generation_config.is_file()


def test_run_generation_retries_without_cwd_when_process_launch_cwd_is_unsupported(tmp_path, monkeypatch):
    sdk_root = _build_sdk_with_generator(tmp_path / "sdk")
    source_dir = tmp_path / "source"
    workspace_dir = tmp_path / "workspace"
    bin_output_dir = tmp_path / "bin"
    source_dir.mkdir()

    calls = []

    def _flaky_run(command, **kwargs):
        calls.append(kwargs.get("cwd"))
        if len(calls) == 1:
            raise OSError(50, "cwd unsupported")
        return subprocess.CompletedProcess(command, 0, stdout="generated\n", stderr="")

    monkeypatch.setattr("ui_designer.model.resource_generation_session.subprocess.run", _flaky_run)

    session = ResourceGenerationSession(str(sdk_root))
    session.reset(
        GenerationPaths(
            config_path=str(source_dir / "app_resource_config.json"),
            source_dir=str(source_dir),
            workspace_dir=str(workspace_dir),
            bin_output_dir=str(bin_output_dir),
        ),
        {
            "img": [],
            "font": [],
            "mp4": [],
        },
    )

    result = session.run_generation()

    assert result.success is True
    assert calls == [str(sdk_root.resolve()), None]
