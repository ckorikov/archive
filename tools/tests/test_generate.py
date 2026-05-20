"""Unit tests for generate.py helpers."""

from generate import quote_block, strip_shortcodes


class TestStripShortcodes:
    def test_no_shortcodes(self) -> None:
        assert strip_shortcodes("plain text") == "plain text"

    def test_single_logo(self) -> None:
        text = '{{< logo "huawei" "Huawei" >}}'
        assert strip_shortcodes(text) == "Huawei"

    def test_multiple_logos_inline(self) -> None:
        text = '{{< logo "huawei" "Huawei" >}}, {{< logo "mipt" "MIPT" >}}.'
        assert strip_shortcodes(text) == "Huawei, MIPT."

    def test_logo_with_prefix(self) -> None:
        text = '{{< logo "intel" "ex-Intel" >}}'
        assert strip_shortcodes(text) == "ex-Intel"

    def test_multiline_bio(self) -> None:
        text = 'Researcher and educator.\n\n{{< logo "huawei" "Huawei" >}}, {{< logo "mipt" "MIPT" >}}.'
        expected = "Researcher and educator.\n\nHuawei, MIPT."
        assert strip_shortcodes(text) == expected

    def test_unterminated_shortcode_preserved(self) -> None:
        text = "before {{< broken"
        assert strip_shortcodes(text) == "before {{< broken"

    def test_empty_string(self) -> None:
        assert strip_shortcodes("") == ""


class TestQuoteBlock:
    def test_single_line(self) -> None:
        assert quote_block("hello") == "> hello"

    def test_multiline(self) -> None:
        assert quote_block("a\nb") == "> a\n> b"

    def test_empty_lines_kept(self) -> None:
        assert quote_block("a\n\nb") == "> a\n>\n> b"

    def test_empty_string(self) -> None:
        assert quote_block("") == ""
