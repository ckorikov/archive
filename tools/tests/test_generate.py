"""Unit tests for generate.py helpers."""

from generate import (
    curate_tags,
    pub_to_item,
    quote_block,
    strip_shortcodes,
)
from models import ArchiveConfig, Group, Publication, SiteConfig


def make_config(
    groups: list[Group] | None = None,
    aliases: dict[str, list[str]] | None = None,
) -> ArchiveConfig:
    return ArchiveConfig(
        site=SiteConfig(author="Owner"),
        groups=groups or [],
        aliases=aliases or {},
    )


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


class TestCurateTags:
    def test_keeps_only_taxonomy_tags(self) -> None:
        config = make_config([Group(name="Research", tags=["casimir", "ai"])])
        tags = ["Casimir force", "Drude model", "casimir", "ai"]
        assert curate_tags(tags, config) == ["casimir", "ai"]

    def test_dedup_case_insensitive(self) -> None:
        config = make_config([Group(name="Research", tags=["casimir"])])
        assert curate_tags(["casimir", "Casimir", "CASIMIR"], config) == ["casimir"]

    def test_canonical_spelling_from_taxonomy(self) -> None:
        config = make_config([Group(name="Research", tags=["Casimir"])])
        assert curate_tags(["casimir"], config) == ["Casimir"]

    def test_empty_when_no_match(self) -> None:
        config = make_config([Group(name="Research", tags=["ai"])])
        assert curate_tags(["physics", "optics"], config) == []


class TestPubToItem:
    def test_tags_curated(self) -> None:
        config = make_config(groups=[Group(name="Research", tags=["casimir"])])
        pub = Publication(
            id="X",
            type="journalArticle",
            year=2024,
            title="T",
            tags=["Casimir force", "casimir", "noise"],
        )
        assert pub_to_item(pub, config)["tags"] == ["casimir"]
