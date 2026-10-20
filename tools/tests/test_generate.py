"""Unit tests for generate.py helpers."""

from pathlib import Path

import yaml

from generate import (
    compute_courses,
    curate_tags,
    filter_publications,
    generate_about,
    pub_to_item,
    quote_block,
    strip_shortcodes,
)
from models import ArchiveConfig, Author, Group, Organization, Publication, SiteConfig


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

    def test_license_emitted(self) -> None:
        config = make_config()
        pub = Publication(
            id="SW",
            type="computerProgram",
            year=2026,
            title="Sim8",
            authors=[Author(firstName="C", lastName="Korikov")],
            license="MIT",
        )
        item = pub_to_item(pub, config)
        assert item["authors"] == ["C Korikov"]
        assert item["license"] == "MIT"

    def test_no_license_omitted(self) -> None:
        config = make_config()
        pub = Publication(id="P", type="journalArticle", year=2024, title="T")
        assert "license" not in pub_to_item(pub, config)


class TestGenerateAbout:
    def test_overwrites_stale_page(self, tmp_path: Path) -> None:
        about_path = tmp_path / "about" / "_index.md"
        about_path.parent.mkdir(parents=True)
        about_path.write_text("---\ntitle: About\n---\n\nStale bio")
        config = ArchiveConfig(site=SiteConfig(author="Owner", bio="Fresh bio"))

        generate_about(tmp_path, config)

        text = about_path.read_text()
        assert "Fresh bio" in text
        assert "Stale bio" not in text

    def test_writes_person_structured_data(self, tmp_path: Path) -> None:
        site = SiteConfig(
            author="Owner",
            works_for=[Organization(name="Huawei", url="https://www.huawei.com")],
            affiliations=[Organization(name="MIPT")],
            knows_about=["Casimir effect"],
        )

        generate_about(tmp_path, ArchiveConfig(site=site))

        front = yaml.safe_load((tmp_path / "about" / "_index.md").read_text().split("---")[1])
        assert front["works_for"] == [{"name": "Huawei", "url": "https://www.huawei.com"}]
        assert front["affiliations"] == [{"name": "MIPT"}]
        assert front["knows_about"] == ["Casimir effect"]

    def test_omits_empty_person_fields(self, tmp_path: Path) -> None:
        generate_about(tmp_path, ArchiveConfig(site=SiteConfig(author="Owner")))

        front = yaml.safe_load((tmp_path / "about" / "_index.md").read_text().split("---")[1])
        assert not {"works_for", "affiliations", "knows_about"} & front.keys()


class TestLectureVsSeries:
    """A proceedings series must not turn a paper into a course lecture."""

    def make(self, pub_type: str, presentation_type: str | None = None) -> Publication:
        return Publication.model_validate(
            {
                "id": "X",
                "type": pub_type,
                "year": 2026,
                "title": "T",
                "series": "ICS '26",
                "presentationType": presentation_type,
            }
        )

    def test_paper_with_series_is_standalone(self) -> None:
        paper = self.make("conferencePaper")
        assert not paper.is_lecture
        assert filter_publications([paper], make_config(), has_course=False) == [paper]
        assert compute_courses([paper], make_config()) == []

    def test_conference_talk_with_series_is_standalone(self) -> None:
        talk = self.make("presentation", "Conference")
        assert not talk.is_lecture
        assert compute_courses([talk], make_config()) == []

    def test_lecture_is_course(self) -> None:
        lecture = self.make("presentation", "Lecture")
        assert lecture.is_lecture
        assert filter_publications([lecture], make_config(), has_course=False) == []
        assert filter_publications([lecture], make_config(), has_course=True) == [lecture]
        [course] = compute_courses([lecture], make_config())
        assert [lec.id for lec in course.lectures] == [lecture.id]
