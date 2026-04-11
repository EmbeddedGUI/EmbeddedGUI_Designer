"""Tests for shared test SDK builders."""

from ui_designer.tests.sdk_builders import build_test_sdk_root, mark_bundled_test_sdk_root


class TestSdkBuilders:
    def test_build_test_sdk_root_creates_minimal_sdk_layout(self, tmp_path):
        sdk_root = build_test_sdk_root(tmp_path / "sdk")

        assert (sdk_root / "src").is_dir()
        assert (sdk_root / "porting" / "designer").is_dir()
        assert (sdk_root / "Makefile").read_text(encoding="utf-8") == "all:\n"

    def test_mark_bundled_test_sdk_root_writes_bundle_metadata(self, tmp_path):
        sdk_root = tmp_path / "sdk"
        sdk_root.mkdir()

        mark_bundled_test_sdk_root(sdk_root, metadata_name="bundle.json", source_root="D:/custom/sdk")

        assert (sdk_root / "bundle.json").read_text(encoding="utf-8") == '{"source_root": "D:/custom/sdk"}\n'
