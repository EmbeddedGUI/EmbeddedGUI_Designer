"""Tests for built-in font charset preset helpers."""

from ui_designer.services.font_charset_presets import (
    build_charset,
    charset_custom_chars_after_presets,
    charset_count_for_preset,
    infer_charset_presets_from_text,
    charset_presets,
    custom_chars_from_text,
    preview_charset_chars,
    serialize_charset_chars,
    suggest_charset_filename,
    summarize_charset_diff,
)


def test_builtin_preset_counts_match_expected_values():
    expected = {
        "ascii_printable": 95,
        "gb2312_fullwidth_symbols": 682,
        "gb2312_level1_hanzi": 3755,
        "gb2312_level2_hanzi": 3008,
        "gb2312_all": 7540,
        "gbk_all": 21886,
    }

    assert {preset.preset_id for preset in charset_presets()} == set(expected)
    for preset_id, count in expected.items():
        assert charset_count_for_preset(preset_id) == count


def test_build_charset_preserves_preset_order_and_reports_contributions():
    result = build_charset(("ascii_printable", "gb2312_fullwidth_symbols"), custom_text="A中")

    assert result.total_chars == 95 + 682 + 1
    assert [item.source_id for item in result.contributions] == [
        "ascii_printable",
        "gb2312_fullwidth_symbols",
        "custom",
    ]
    assert result.contributions[0].added_chars == 95
    assert result.contributions[1].added_chars == 682
    assert result.contributions[2].total_chars == 2
    assert result.contributions[2].added_chars == 1
    assert result.chars[0] == " "
    assert "中" in result.chars


def test_custom_chars_expand_entities_and_ignore_only_line_breaks():
    chars = custom_chars_from_text("A&#x4E2D;\n \r\nA")

    assert chars == ("A", "中", " ")


def test_serialize_charset_chars_uses_entities_for_space_and_non_ascii():
    text = serialize_charset_chars((" ", "A", "中"))

    assert text == "&#x0020;\nA\n&#x4E2D;\n"


def test_preview_charset_chars_uses_stable_serialized_tokens():
    preview = preview_charset_chars((" ", "A", "中"), limit=3)

    assert preview == "&#x0020; A &#x4E2D;"


def test_suggest_charset_filename_covers_single_combo_and_custom_cases():
    assert suggest_charset_filename(("ascii_printable",), "") == "charset_ascii_printable.txt"
    assert suggest_charset_filename(("ascii_printable",), "中") == "charset_ascii_printable_custom.txt"
    assert suggest_charset_filename(("ascii_printable", "gb2312_level1_hanzi"), "") == "charset_combo.txt"
    assert suggest_charset_filename(("ascii_printable", "gb2312_level1_hanzi"), "中") == "charset_combo_custom.txt"
    assert suggest_charset_filename((), "中") == "charset_custom.txt"


def test_infer_charset_presets_from_text_matches_exact_builtin_content():
    assert infer_charset_presets_from_text(serialize_charset_chars((" ", "A", "B"))) == ()
    assert infer_charset_presets_from_text(serialize_charset_chars(build_charset(("ascii_printable",)).chars)) == (
        "ascii_printable",
    )


def test_charset_custom_chars_after_presets_returns_only_uncovered_chars():
    text = serialize_charset_chars(build_charset(("ascii_printable",), custom_text="中").chars)

    assert charset_custom_chars_after_presets(text, ("ascii_printable",)) == ("中",)
    assert charset_custom_chars_after_presets(text, ())[-1] == "中"


def test_summarize_charset_diff_tracks_added_and_removed_chars():
    diff = summarize_charset_diff("&#x0020;\nA\n中\n", (" ", "B", "中"))

    assert diff.existing_count == 3
    assert diff.new_count == 3
    assert diff.added_count == 1
    assert diff.removed_count == 1
    assert diff.added_chars == ("B",)
    assert diff.removed_chars == ("A",)
