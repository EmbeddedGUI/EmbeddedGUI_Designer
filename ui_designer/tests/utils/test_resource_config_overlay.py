import json

from ui_designer.utils.resource_config_overlay import (
    APP_RESOURCE_CONFIG_DESIGNER_FILENAME,
    APP_RESOURCE_CONFIG_FILENAME,
    DESIGNER_RESOURCE_DIRNAME,
    load_merged_resource_config,
    merge_resource_configs,
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
