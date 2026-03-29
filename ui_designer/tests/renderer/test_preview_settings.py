"""Tests for preview engine settings resolution."""

from ui_designer.settings.preview_settings import PreviewSettings


def test_preview_settings_prefers_config_when_v2_flag_disabled():
    settings = PreviewSettings.from_config("v2")
    assert settings.resolve_initial_engine(env_v2_enabled=False) == "v2"


def test_preview_settings_env_flag_forces_v2():
    settings = PreviewSettings.from_config("v1")
    assert settings.resolve_initial_engine(env_v2_enabled=True) == "v2"


def test_preview_settings_normalizes_empty_to_v1_default():
    settings = PreviewSettings.from_config("")
    assert settings.preferred_engine == "v1"
    assert settings.resolve_initial_engine(env_v2_enabled=False) == "v1"
