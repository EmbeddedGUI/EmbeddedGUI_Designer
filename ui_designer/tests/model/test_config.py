"""Tests for DesignerConfig model."""

import json
import os
from pathlib import Path

import pytest
from unittest.mock import patch

from ui_designer.model.config import DesignerConfig, _get_config_dir, _get_config_path
from ui_designer.model.workspace import normalize_path


@pytest.fixture(autouse=True)
def reset_singleton(tmp_path, monkeypatch):
    """Reset the singleton instance before each test."""
    monkeypatch.setenv("EMBEDDEDGUI_DESIGNER_CONFIG_DIR", str(tmp_path / "config-home"))
    DesignerConfig._instance = None
    yield
    DesignerConfig._instance = None


@pytest.fixture
def config():
    """Create a fresh DesignerConfig (not singleton)."""
    return DesignerConfig()


def _resolve_without_workspace_discovery(*candidates, cached_sdk_root=None):
    def _is_sdk_root(path_text):
        candidate = Path(path_text)
        return (
            candidate.is_dir()
            and (candidate / "Makefile").is_file()
            and (candidate / "src").is_dir()
            and (candidate / "porting" / "designer").is_dir()
        )

    normalized_candidates = []
    for candidate in candidates:
        normalized = normalize_path(candidate)
        if normalized:
            normalized_candidates.append(normalized)
    for candidate in normalized_candidates:
        if _is_sdk_root(candidate):
            return candidate

    cached_candidate = normalize_path(cached_sdk_root)
    if cached_candidate and _is_sdk_root(cached_candidate):
        return cached_candidate
    return normalized_candidates[0] if normalized_candidates else ""


class TestDefaults:
    """Test default configuration values."""

    def test_default_values(self, config):
        assert config.sdk_root == ""
        assert config.egui_root == ""
        assert config.last_app == "HelloDesigner"
        assert config.recent_projects == []
        assert config.theme == "dark"
        assert config.auto_compile is True
        assert config.overlay_mode == "horizontal"
        assert config.overlay_flipped is True
        assert config.show_grid is True
        assert config.grid_size == 8
        assert config.font_size_px == 0
        assert config.show_all_examples is False
        assert config.window_geometry == ""
        assert config.window_state == ""
        assert config.widget_browser_active_category == "all"
        assert config.diagnostics_view == {}
        assert config.show_clean_all_startup_notice is True

    def test_egui_root_alias_updates_sdk_root(self, config):
        config.egui_root = "/alias/sdk"
        assert config.sdk_root == normalize_path("/alias/sdk")
        assert config.egui_root == normalize_path("/alias/sdk")

    def test_sdk_root_assignment_normalizes_path(self, config):
        config.sdk_root = "/alias/sdk"
        assert config.sdk_root == normalize_path("/alias/sdk")


class TestSaveLoad:
    """Test save/load JSON round-trip."""

    def test_save_and_load_roundtrip(self, config, tmp_path):
        config.sdk_root = "/some/path"
        config.last_app = "MyApp"
        config.theme = "light"
        config.auto_compile = False
        config.show_grid = False
        config.grid_size = 12
        config.font_size_px = 14
        config.widget_browser_active_category = "layout"
        config.diagnostics_view = {"severity_filter": "warning"}
        config.show_clean_all_startup_notice = False

        config_path = tmp_path / "config.json"
        with patch("ui_designer.model.config._get_config_path", return_value=str(config_path)):
            with patch("ui_designer.model.config._get_config_dir", return_value=str(tmp_path)):
                config.save()

        loaded = DesignerConfig()
        with patch("ui_designer.model.config._get_config_path", return_value=str(config_path)):
            loaded.load()

        assert loaded.sdk_root == normalize_path("/some/path")
        assert loaded.egui_root == normalize_path("/some/path")
        assert loaded.last_app == "MyApp"
        assert loaded.theme == "light"
        assert loaded.auto_compile is False
        assert loaded.show_grid is False
        assert loaded.grid_size == 12
        assert loaded.font_size_px == 14
        assert loaded.widget_browser_active_category == "layout"
        assert loaded.diagnostics_view == {"severity_filter": "warning"}
        assert loaded.show_clean_all_startup_notice is False

    def test_load_nonexistent_file(self, config, tmp_path):
        config_path = tmp_path / "nonexistent.json"
        with patch("ui_designer.model.config._get_config_path", return_value=str(config_path)):
            config.load()
        # Should keep defaults
        assert config.last_app == "HelloDesigner"
        assert config.theme == "dark"

    def test_load_corrupted_file(self, config, tmp_path):
        config_path = tmp_path / "config.json"
        config_path.write_text("not valid json {{{")
        with patch("ui_designer.model.config._get_config_path", return_value=str(config_path)):
            config.load()  # should not raise
        assert config.last_app == "HelloDesigner"

    def test_load_ignores_legacy_widget_browser_filter_fields(self, config, tmp_path):
        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "widget_browser_active_scenario": "scenario:layout & containers",
                    "widget_browser_active_tags": ["layout"],
                    "widget_browser_sort_mode": "name",
                    "widget_browser_complexity_filter": "advanced",
                }
            ),
            encoding="utf-8",
        )

        with patch("ui_designer.model.config._get_config_path", return_value=str(config_path)):
            config.load()

        assert config.widget_browser_active_category == "all"
        assert not hasattr(config, "widget_browser_active_scenario")
        assert not hasattr(config, "widget_browser_active_tags")
        assert not hasattr(config, "widget_browser_sort_mode")
        assert not hasattr(config, "widget_browser_complexity_filter")

    def test_save_creates_directory(self, config, tmp_path):
        nested = tmp_path / "sub" / "dir"
        config_path = nested / "config.json"
        with patch("ui_designer.model.config._get_config_path", return_value=str(config_path)):
            with patch("ui_designer.model.config._get_config_dir", return_value=str(nested)):
                config.save()
        assert config_path.is_file()

    def test_save_omits_legacy_lightweight_drag_key(self, config, tmp_path):
        config_path = tmp_path / "config.json"
        with patch("ui_designer.model.config._get_config_path", return_value=str(config_path)):
            with patch("ui_designer.model.config._get_config_dir", return_value=str(tmp_path)):
                config.save()

        data = json.loads(config_path.read_text(encoding="utf-8"))
        assert "lightweight_drag" not in data

    def test_save_omits_legacy_sdk_and_recent_app_aliases(self, config, tmp_path):
        config_path = tmp_path / "config.json"
        with patch("ui_designer.model.config._get_config_path", return_value=str(config_path)):
            with patch("ui_designer.model.config._get_config_dir", return_value=str(tmp_path)):
                config.save()

        data = json.loads(config_path.read_text(encoding="utf-8"))
        assert "egui_root" not in data
        assert "recent_apps" not in data
        assert "widget_browser_active_scenario" not in data
        assert "widget_browser_active_tags" not in data
        assert "widget_browser_sort_mode" not in data
        assert "widget_browser_complexity_filter" not in data

    def test_load_ignores_legacy_lightweight_drag_key(self, config, tmp_path):
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({"lightweight_drag": False, "grid_size": 12}), encoding="utf-8")

        with patch("ui_designer.model.config._get_config_path", return_value=str(config_path)):
            config.load()

        assert config.grid_size == 12
        assert not hasattr(config, "lightweight_drag")


class TestRecentProjects:
    """Test recent project MRU list management."""

    def test_add_recent_project(self, config, tmp_path):
        config_path = tmp_path / "config.json"
        with patch("ui_designer.model.config._get_config_path", return_value=str(config_path)):
            with patch("ui_designer.model.config._get_config_dir", return_value=str(tmp_path)):
                config.add_recent_project("/root1/example/App1/App1.egui", "/root1", "App1")
        assert config.recent_projects == [
            {
                "project_path": normalize_path("/root1/example/App1/App1.egui"),
                "sdk_root": normalize_path("/root1"),
                "display_name": "App1",
            }
        ]
        assert config.recent_projects[0]["display_name"] == "App1"

    def test_add_recent_project_moves_to_front(self, config, tmp_path):
        config_path = tmp_path / "config.json"
        with patch("ui_designer.model.config._get_config_path", return_value=str(config_path)):
            with patch("ui_designer.model.config._get_config_dir", return_value=str(tmp_path)):
                config.add_recent_project("/root/example/App1/App1.egui", "/root", "App1")
                config.add_recent_project("/root/example/App2/App2.egui", "/root", "App2")
                config.add_recent_project("/root/example/App1/App1.egui", "/root", "App1")
        assert config.recent_projects[0]["display_name"] == "App1"
        assert len(config.recent_projects) == 2

    def test_add_recent_project_max_10(self, config, tmp_path):
        config_path = tmp_path / "config.json"
        with patch("ui_designer.model.config._get_config_path", return_value=str(config_path)):
            with patch("ui_designer.model.config._get_config_dir", return_value=str(tmp_path)):
                for i in range(15):
                    config.add_recent_project(f"/root/example/App{i}/App{i}.egui", "/root", f"App{i}")
        assert len(config.recent_projects) == 10
        assert config.recent_projects[0]["display_name"] == "App14"

    def test_add_recent_project_deduplicates(self, config, tmp_path):
        config_path = tmp_path / "config.json"
        with patch("ui_designer.model.config._get_config_path", return_value=str(config_path)):
            with patch("ui_designer.model.config._get_config_dir", return_value=str(tmp_path)):
                config.add_recent_project("/root/example/App1/App1.egui", "/root", "App1")
                config.add_recent_project("/root/example/App1/App1.egui", "/root", "App1")
        assert len(config.recent_projects) == 1

    def test_remove_recent_project_updates_recent_project_list(self, config, tmp_path):
        config_path = tmp_path / "config.json"
        with patch("ui_designer.model.config._get_config_path", return_value=str(config_path)):
            with patch("ui_designer.model.config._get_config_dir", return_value=str(tmp_path)):
                config.add_recent_project("/root/App1/App1.egui", "/root", "App1")
                config.add_recent_project("/root/App2/App2.egui", "/root", "App2")

                removed = config.remove_recent_project("/root/App1/App1.egui")

        assert removed is True
        assert [item["display_name"] for item in config.recent_projects] == ["App2"]

    def test_remove_recent_project_clears_last_project_path_when_matching(self, config, tmp_path):
        config_path = tmp_path / "config.json"
        with patch("ui_designer.model.config._get_config_path", return_value=str(config_path)):
            with patch("ui_designer.model.config._get_config_dir", return_value=str(tmp_path)):
                config.add_recent_project("/root/App1/App1.egui", "/root", "App1")
                config.last_project_path = normalize_path("/root/App1/App1.egui")

                removed = config.remove_recent_project("/root/App1/App1.egui")

        assert removed is True
        assert config.last_project_path == ""

    def test_set_widget_browser_active_category_normalizes_value(self, config, tmp_path):
        config_path = tmp_path / "config.json"
        with patch("ui_designer.model.config._get_config_path", return_value=str(config_path)):
            with patch("ui_designer.model.config._get_config_dir", return_value=str(tmp_path)):
                config.set_widget_browser_active_category("LAYOUT")

        assert config.widget_browser_active_category == "layout"


class TestPathManagement:
    """Test path helper methods."""

    def test_get_app_dir(self, config):
        config.sdk_root = "/project"
        config.last_app = "MyApp"
        result = config.get_app_dir()
        assert result == os.path.join(normalize_path("/project"), "example", "MyApp")

    def test_get_app_dir_with_args(self, config):
        result = config.get_app_dir("TestApp", "/other/root")
        assert result == os.path.join(normalize_path("/other/root"), "example", "TestApp")

    def test_get_app_dir_empty_root(self, config):
        config.sdk_root = ""
        assert config.get_app_dir() == ""

    def test_get_app_dir_uses_cached_sdk_when_saved_root_is_invalid(self, config, tmp_path):
        cached_sdk = tmp_path / "cfg" / "sdk" / "EmbeddedGUI"
        (cached_sdk / "src").mkdir(parents=True)
        (cached_sdk / "porting" / "designer").mkdir(parents=True)
        (cached_sdk / "Makefile").write_text("all:\n")
        config.sdk_root = str(tmp_path / "missing_sdk")
        config.last_app = "MyApp"

        with patch("ui_designer.model.config.resolve_available_sdk_root", side_effect=_resolve_without_workspace_discovery):
            with patch("ui_designer.model.config._get_config_dir", return_value=str(tmp_path / "cfg")):
                result = config.get_app_dir()

        assert result == os.path.join(normalize_path(str(cached_sdk)), "example", "MyApp")

    def test_get_project_path(self, config):
        config.sdk_root = "/project"
        config.last_app = "MyApp"
        result = config.get_project_path()
        assert result == os.path.join(normalize_path("/project"), "example", "MyApp", "MyApp.egui")

    def test_get_project_path_empty(self, config):
        config.sdk_root = ""
        assert config.get_project_path() == ""

    def test_list_available_apps(self, config, tmp_path):
        config.sdk_root = str(tmp_path)
        example_dir = tmp_path / "example"
        example_dir.mkdir()

        # Create valid app (has build.mk)
        app1 = example_dir / "ValidApp"
        app1.mkdir()
        (app1 / "build.mk").write_text("")
        (app1 / "ValidApp.egui").write_text("")

        # Create invalid app (no build.mk)
        app2 = example_dir / "InvalidApp"
        app2.mkdir()

        with patch("ui_designer.model.config.resolve_available_sdk_root", side_effect=_resolve_without_workspace_discovery):
            apps = config.list_available_apps()
        assert "ValidApp" in apps
        assert "InvalidApp" not in apps

    def test_list_available_apps_empty_root(self, config):
        config.sdk_root = ""
        with patch("ui_designer.model.config.resolve_available_sdk_root", side_effect=_resolve_without_workspace_discovery):
            assert config.list_available_apps() == []

    def test_list_available_apps_uses_cached_sdk_when_saved_root_is_invalid(self, config, tmp_path):
        cached_sdk = tmp_path / "cfg" / "sdk" / "EmbeddedGUI"
        example_dir = cached_sdk / "example"
        app_dir = example_dir / "CachedApp"
        (app_dir).mkdir(parents=True)
        (cached_sdk / "src").mkdir(parents=True, exist_ok=True)
        (cached_sdk / "porting" / "designer").mkdir(parents=True, exist_ok=True)
        (cached_sdk / "Makefile").write_text("all:\n")
        (app_dir / "build.mk").write_text("")
        (app_dir / "CachedApp.egui").write_text("")
        config.sdk_root = str(tmp_path / "missing_sdk")

        with patch("ui_designer.model.config.resolve_available_sdk_root", side_effect=_resolve_without_workspace_discovery):
            with patch("ui_designer.model.config._get_config_dir", return_value=str(tmp_path / "cfg")):
                apps = config.list_available_apps()

        assert apps == ["CachedApp"]

    def test_list_available_apps_no_example_dir(self, config, tmp_path):
        config.sdk_root = str(tmp_path)
        with patch("ui_designer.model.config.resolve_available_sdk_root", side_effect=_resolve_without_workspace_discovery):
            assert config.list_available_apps() == []


class TestSingleton:
    """Test singleton pattern."""

    def test_instance_returns_same_object(self, tmp_path):
        config_path = tmp_path / "config.json"
        with patch("ui_designer.model.config._get_config_path", return_value=str(config_path)):
            inst1 = DesignerConfig.instance()
            inst2 = DesignerConfig.instance()
        assert inst1 is inst2


class TestConfigMigration:
    def test_get_config_dir_uses_env_override(self, tmp_path, monkeypatch):
        override_dir = tmp_path / "custom-config"
        monkeypatch.setenv("EMBEDDEDGUI_DESIGNER_CONFIG_DIR", str(override_dir))

        assert _get_config_dir() == normalize_path(str(override_dir))
        assert _get_config_path() == normalize_path(str(override_dir / "config.json"))

    def test_load_uses_primary_user_config_path_only(self, config, tmp_path):
        primary_path = tmp_path / "user" / "config.json"
        primary_path.parent.mkdir(parents=True)
        primary_path.write_text(json.dumps({"last_app": "PrimaryApp"}), encoding="utf-8")
        observed_paths = []
        real_isfile = os.path.isfile

        with patch("ui_designer.model.config._get_config_path", return_value=str(primary_path)):
            with patch(
                "ui_designer.model.config.os.path.isfile",
                side_effect=lambda path: observed_paths.append(normalize_path(path)) or real_isfile(path),
            ):
                config.load()

        assert config.last_app == "PrimaryApp"
        assert observed_paths == [normalize_path(str(primary_path))]

    def test_load_ignores_legacy_recent_apps_payload(self, config, tmp_path):
        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps({"recent_apps": [["LegacyApp", "/legacy/sdk"]]}),
            encoding="utf-8",
        )

        with patch("ui_designer.model.config._get_config_path", return_value=str(config_path)):
            config.load()

        assert config.recent_projects == []

    def test_load_ignores_legacy_egui_root_config_key(self, config, tmp_path):
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({"egui_root": "/legacy/sdk"}), encoding="utf-8")

        with patch("ui_designer.model.config._get_config_path", return_value=str(config_path)):
            config.load()

        assert config.sdk_root == ""
        assert config.egui_root == ""

    def test_load_ignores_legacy_recent_project_egui_root_key(self, config, tmp_path):
        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "recent_projects": [
                        {
                            "project_path": "/legacy/example/App/App.egui",
                            "egui_root": "/legacy/sdk",
                            "display_name": "App",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        with patch("ui_designer.model.config._get_config_path", return_value=str(config_path)):
            config.load()

        assert config.recent_projects == [
            {
                "project_path": normalize_path("/legacy/example/App/App.egui"),
                "sdk_root": "",
                "display_name": "App",
            }
        ]
