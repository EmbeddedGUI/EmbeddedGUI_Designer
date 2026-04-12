import json

from ui_designer.utils.resource_config_overlay import (
    APP_RESOURCE_CONFIG_DESIGNER_FILENAME,
    APP_RESOURCE_CONFIG_FILENAME,
    DESIGNER_RESOURCE_DIRNAME,
    ensure_resource_config_file,
    load_merged_resource_config,
    make_empty_resource_config_content,
    merge_resource_configs,
    user_resource_config_path,
)


class TestMergeResourceConfigs:
    def test_user_overlay_overrides_image_storage_fields(self):
        merged = merge_resource_configs(
            {
                "img": [
                    {
                        "file": "hero.png",
                        "format": "rgb565",
                        "alpha": "4",
                        "external": "0",
                        "swap": "0",
                    }
                ],
                "font": [],
            },
            {
                "img": [
                    {
                        "file": "hero.png",
                        "format": "rgb565",
                        "alpha": "4",
                        "external": "1",
                        "swap": "1",
                        "compress": "qoi",
                    }
                ],
                "font": [],
            },
        )

        assert merged["img"] == [
            {
                "file": "hero.png",
                "format": "rgb565",
                "alpha": "4",
                "external": "1",
                "swap": "1",
                "compress": "qoi",
            }
        ]

    def test_user_overlay_appends_font_text_files(self):
        merged = merge_resource_configs(
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
            },
            {
                "img": [],
                "font": [
                    {
                        "file": "demo.ttf",
                        "pixelsize": "16",
                        "fontbitsize": "4",
                        "text": "custom_chars.txt",
                        "external": "1",
                    }
                ],
            },
        )

        assert merged["font"] == [
            {
                "file": "demo.ttf",
                "pixelsize": "16",
                "fontbitsize": "4",
                "external": "1",
                "text": ".designer/_generated_text_demo_16_4.txt,custom_chars.txt",
            }
        ]

    def test_user_only_entries_are_preserved(self):
        merged = merge_resource_configs(
            {"img": [], "font": []},
            {
                "img": [{"file": "user.png", "format": "alpha", "alpha": "4"}],
                "font": [],
                "theme": "custom",
            },
        )

        assert merged["img"] == [{"file": "user.png", "format": "alpha", "alpha": "4"}]
        assert merged["theme"] == "custom"

    def test_font_text_merge_deduplicates_repeated_paths(self):
        merged = merge_resource_configs(
            {
                "img": [],
                "font": [
                    {
                        "file": "demo.ttf",
                        "pixelsize": "16",
                        "fontbitsize": "4",
                        "text": ".designer/_generated_text_demo_16_4.txt,shared.txt",
                    }
                ],
            },
            {
                "img": [],
                "font": [
                    {
                        "file": "demo.ttf",
                        "pixelsize": "16",
                        "fontbitsize": "4",
                        "text": "shared.txt,custom.txt",
                    }
                ],
            },
        )

        assert merged["font"] == [
            {
                "file": "demo.ttf",
                "pixelsize": "16",
                "fontbitsize": "4",
                "text": ".designer/_generated_text_demo_16_4.txt,shared.txt,custom.txt",
            }
        ]


class TestLoadMergedResourceConfig:
    def test_loads_split_files_from_disk(self, tmp_path):
        designer_dir = tmp_path / DESIGNER_RESOURCE_DIRNAME
        designer_dir.mkdir()
        (designer_dir / APP_RESOURCE_CONFIG_DESIGNER_FILENAME).write_text(
            json.dumps(
                {
                    "img": [{"file": "designer.png", "format": "rgb565", "alpha": "4"}],
                    "font": [],
                },
                ensure_ascii=False,
                indent=4,
            ),
            encoding="utf-8",
        )
        (tmp_path / APP_RESOURCE_CONFIG_FILENAME).write_text(
            '{\n'
            '  // user overlay\n'
            '  "img": [\n'
            '    {"file": "designer.png", "format": "rgb565", "alpha": "4", "external": "1"}\n'
            '  ],\n'
            '  "font": []\n'
            '}\n',
            encoding="utf-8",
        )

        merged = load_merged_resource_config(str(tmp_path))

        assert merged["img"] == [
            {
                "file": "designer.png",
                "format": "rgb565",
                "alpha": "4",
                "external": "1",
            }
        ]

    def test_ignores_legacy_root_designer_config_when_split_file_is_missing(self, tmp_path):
        (tmp_path / APP_RESOURCE_CONFIG_DESIGNER_FILENAME).write_text(
            json.dumps(
                {
                    "img": [{"file": "legacy.png", "format": "alpha", "alpha": "4"}],
                    "font": [],
                },
                ensure_ascii=False,
                indent=4,
            ),
            encoding="utf-8",
        )
        (tmp_path / APP_RESOURCE_CONFIG_FILENAME).write_text(
            json.dumps(
                {
                    "img": [
                        {
                            "file": "legacy.png",
                            "format": "alpha",
                            "alpha": "4",
                            "external": "1",
                        }
                    ],
                    "font": [],
                },
                ensure_ascii=False,
                indent=4,
            ),
            encoding="utf-8",
        )

        merged = load_merged_resource_config(str(tmp_path))

        assert merged["img"] == [
            {
                "file": "legacy.png",
                "format": "alpha",
                "alpha": "4",
                "external": "1",
            }
        ]
        assert "font" in merged

    def test_root_legacy_designer_entries_do_not_contribute_without_split_file(self, tmp_path):
        (tmp_path / APP_RESOURCE_CONFIG_DESIGNER_FILENAME).write_text(
            json.dumps(
                {
                    "img": [{"file": "legacy_only.png", "format": "alpha", "alpha": "4"}],
                    "font": [],
                },
                ensure_ascii=False,
                indent=4,
            ),
            encoding="utf-8",
        )
        (tmp_path / APP_RESOURCE_CONFIG_FILENAME).write_text(
            json.dumps(
                {
                    "img": [],
                    "font": [],
                },
                ensure_ascii=False,
                indent=4,
            ),
            encoding="utf-8",
        )

        merged = load_merged_resource_config(str(tmp_path))

        assert merged["img"] == []
        assert merged["font"] == []


class TestEnsureResourceConfigFile:
    def test_user_resource_config_path_points_at_overlay_file(self, tmp_path):
        assert user_resource_config_path(str(tmp_path)) == str(tmp_path / APP_RESOURCE_CONFIG_FILENAME)

    def test_creates_default_overlay_config_once(self, tmp_path):
        config_path = tmp_path / "resource" / "src" / APP_RESOURCE_CONFIG_FILENAME

        created = ensure_resource_config_file(str(config_path))
        created_again = ensure_resource_config_file(str(config_path))

        assert created is True
        assert created_again is False
        assert config_path.read_text(encoding="utf-8") == make_empty_resource_config_content()
