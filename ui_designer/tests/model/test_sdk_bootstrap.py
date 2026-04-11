"""Tests for ui_designer.model.sdk_bootstrap."""

from pathlib import Path

from ui_designer.tests.sdk_builders import build_test_sdk_root, mark_bundled_test_sdk_root

from ui_designer.model.sdk_bootstrap import (
    BUNDLED_SDK_METADATA_NAME,
    default_cached_sdk_install_dir,
    default_sdk_install_dir,
    describe_sdk_source,
    describe_sdk_source_hint,
    is_bundled_sdk_root,
    is_runtime_local_sdk_root,
)
from ui_designer.model.workspace import normalize_path


def _create_sdk_root(root: Path):
    return build_test_sdk_root(root)


def _mark_bundled_sdk(root: Path):
    return mark_bundled_test_sdk_root(root, metadata_name=BUNDLED_SDK_METADATA_NAME)


class TestSdkBootstrap:
    def test_default_sdk_install_dir_uses_config_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr("ui_designer.model.sdk_bootstrap._get_config_dir", lambda: str(tmp_path / "config"))
        monkeypatch.delattr("ui_designer.model.sdk_bootstrap.sys.frozen", raising=False)

        assert default_sdk_install_dir() == normalize_path(str(tmp_path / "config" / "sdk" / "EmbeddedGUI"))

    def test_default_sdk_install_dir_prefers_bundled_sdk_root_when_frozen(self, tmp_path, monkeypatch):
        runtime_dir = tmp_path / "EmbeddedGUI-Designer"
        bundled_sdk_root = runtime_dir / "sdk" / "EmbeddedGUI-main"
        runtime_dir.mkdir(parents=True)
        build_test_sdk_root(bundled_sdk_root)
        mark_bundled_test_sdk_root(bundled_sdk_root, metadata_name=BUNDLED_SDK_METADATA_NAME)

        monkeypatch.setattr("ui_designer.model.sdk_bootstrap.sys.frozen", True, raising=False)
        monkeypatch.setattr("ui_designer.model.sdk_bootstrap.sys.executable", str(runtime_dir / "EmbeddedGUI-Designer.exe"))

        assert default_sdk_install_dir() == normalize_path(str(bundled_sdk_root))
        assert is_bundled_sdk_root(str(bundled_sdk_root)) is True

    def test_default_sdk_install_dir_uses_runtime_sdk_target_when_frozen_and_writable(self, tmp_path, monkeypatch):
        runtime_dir = tmp_path / "EmbeddedGUI-Designer"
        runtime_dir.mkdir(parents=True)

        monkeypatch.setattr("ui_designer.model.sdk_bootstrap.sys.frozen", True, raising=False)
        monkeypatch.setattr("ui_designer.model.sdk_bootstrap.sys.executable", str(runtime_dir / "EmbeddedGUI-Designer.exe"))
        monkeypatch.setattr("ui_designer.model.sdk_bootstrap.os.access", lambda path, mode: normalize_path(path) == normalize_path(str(runtime_dir)))

        assert default_sdk_install_dir() == normalize_path(str(runtime_dir / "sdk" / "EmbeddedGUI"))
        assert is_runtime_local_sdk_root(str(runtime_dir / "sdk" / "EmbeddedGUI")) is False

    def test_is_bundled_sdk_root_false_when_not_frozen(self, tmp_path, monkeypatch):
        sdk_root = tmp_path / "sdk"
        build_test_sdk_root(sdk_root)
        monkeypatch.delattr("ui_designer.model.sdk_bootstrap.sys.frozen", raising=False)

        assert is_bundled_sdk_root(str(sdk_root)) is False

    def test_runtime_local_sdk_without_bundle_metadata_is_not_reported_as_bundled(self, tmp_path, monkeypatch):
        runtime_dir = tmp_path / "EmbeddedGUI-Designer"
        sdk_root = runtime_dir / "sdk" / "EmbeddedGUI"
        build_test_sdk_root(sdk_root)

        monkeypatch.setattr("ui_designer.model.sdk_bootstrap.sys.frozen", True, raising=False)
        monkeypatch.setattr("ui_designer.model.sdk_bootstrap.sys.executable", str(runtime_dir / "EmbeddedGUI-Designer.exe"))

        assert is_runtime_local_sdk_root(str(sdk_root)) is True
        assert is_bundled_sdk_root(str(sdk_root)) is False

    def test_describe_sdk_source_hint_includes_bundled_revision(self, tmp_path, monkeypatch):
        runtime_dir = tmp_path / "EmbeddedGUI-Designer"
        sdk_root = runtime_dir / "sdk" / "EmbeddedGUI"
        build_test_sdk_root(sdk_root)
        (sdk_root / BUNDLED_SDK_METADATA_NAME).write_text(
            '{"source_root": "D:/sdk/EmbeddedGUI", "git_describe": "sdk-main-416d576"}\n',
            encoding="utf-8",
        )

        monkeypatch.setattr("ui_designer.model.sdk_bootstrap.sys.frozen", True, raising=False)
        monkeypatch.setattr("ui_designer.model.sdk_bootstrap.sys.executable", str(runtime_dir / "EmbeddedGUI-Designer.exe"))

        text = describe_sdk_source_hint(str(sdk_root))

        assert f"Packaged with Designer from: {normalize_path('D:/sdk/EmbeddedGUI')}" in text
        assert "Bundled SDK revision: sdk-main-416d576" in text

    def test_default_cached_sdk_install_dir_uses_config_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr("ui_designer.model.sdk_bootstrap._get_config_dir", lambda: str(tmp_path / "config"))

        assert default_cached_sdk_install_dir() == normalize_path(str(tmp_path / "config" / "sdk" / "EmbeddedGUI"))

    def test_describe_sdk_source_distinguishes_cached_and_custom_sdk(self, tmp_path, monkeypatch):
        monkeypatch.setattr("ui_designer.model.sdk_bootstrap._get_config_dir", lambda: str(tmp_path / "config"))

        cached_sdk_root = tmp_path / "config" / "sdk" / "EmbeddedGUI"
        custom_sdk_root = tmp_path / "workspace" / "EmbeddedGUI"
        _create_sdk_root(cached_sdk_root)
        _create_sdk_root(custom_sdk_root)

        assert describe_sdk_source(str(cached_sdk_root)) == "default SDK cache"
        assert describe_sdk_source(str(custom_sdk_root)) == "selected SDK root"
