"""Unit tests for editorial rules in validate.py."""

from models import ArchiveConfig, Author, Group, Publication, PublicationsData, SiteConfig
from validate import (
    check_authors,
    check_editorial,
    check_group_overlap,
    check_no_dropbox,
    check_url_present,
)


def make_pub(
    key: str = "K1",
    url: str | None = "https://example.com",
    arxiv_url: str | None = None,
    pdf: str | None = None,
    authors: list[Author] | None = None,
    tags: list[str] | None = None,
) -> Publication:
    return Publication(
        id=key,
        type="journalArticle",
        year=2024,
        title=f"Title {key}",
        url=url,
        arxiv_url=arxiv_url,
        pdf=pdf,
        authors=authors if authors is not None else [Author(firstName="A", lastName="B")],
        tags=tags or [],
    )


def make_config(groups: list[Group] | None = None) -> ArchiveConfig:
    return ArchiveConfig(site=SiteConfig(author="X"), groups=groups or [])


class TestCheckUrlPresent:
    def test_valid_url_ok(self) -> None:
        assert check_url_present(make_pub(url="https://example.com")) == []

    def test_placeholder_fails(self) -> None:
        assert check_url_present(make_pub(url="#"))

    def test_empty_fails(self) -> None:
        assert check_url_present(make_pub(url=""))

    def test_whitespace_fails(self) -> None:
        assert check_url_present(make_pub(url="   "))

    def test_missing_fails(self) -> None:
        assert check_url_present(make_pub(url=None))


class TestCheckNoDropbox:
    def test_clean_ok(self) -> None:
        assert check_no_dropbox(make_pub(url="https://example.com")) == []

    def test_dropbox_in_url_fails(self) -> None:
        assert check_no_dropbox(make_pub(url="https://www.dropbox.com/s/abc/x.pdf"))

    def test_dropbox_in_pdf_fails(self) -> None:
        assert check_no_dropbox(make_pub(pdf="https://dropbox.com/x.pdf"))

    def test_dropbox_in_arxiv_fails(self) -> None:
        assert check_no_dropbox(make_pub(arxiv_url="https://dropbox.com/x"))


class TestCheckAuthors:
    def test_with_authors_ok(self) -> None:
        assert check_authors(make_pub()) == []

    def test_empty_warns(self) -> None:
        assert check_authors(make_pub(authors=[]))


class TestCheckGroupOverlap:
    def test_single_group_ok(self) -> None:
        config = make_config([Group(name="AI", tags=["ml"]), Group(name="HW", tags=["fpga"])])
        assert check_group_overlap(make_pub(tags=["ml"]), config) == []

    def test_no_group_ok(self) -> None:
        config = make_config([Group(name="AI", tags=["ml"])])
        assert check_group_overlap(make_pub(tags=["other"]), config) == []

    def test_multiple_groups_warns(self) -> None:
        config = make_config([Group(name="AI", tags=["ml"]), Group(name="HW", tags=["fpga"])])
        assert check_group_overlap(make_pub(tags=["ml", "fpga"]), config)


class TestCheckEditorial:
    def test_clean_data_passes(self) -> None:
        data = PublicationsData(publications=[make_pub()])
        errors, warnings = check_editorial(data, make_config())
        assert errors == []
        assert warnings == []

    def test_collects_warnings(self) -> None:
        config = make_config([Group(name="AI", tags=["ml"]), Group(name="HW", tags=["fpga"])])
        data = PublicationsData(
            publications=[
                make_pub(key="bad", url="#", authors=[], tags=["ml", "fpga"]),
            ]
        )
        errors, warnings = check_editorial(data, config)
        assert errors == []
        assert len(warnings) == 3  # placeholder url + empty authors + multi-group
