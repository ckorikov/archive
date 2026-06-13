"""Unit tests for fetch.py: extract_related_keys and merge_preprints."""

from fetch import extract_related_keys, merge_preprints, parse_item
from models import Publication


class TestParseItemCreators:
    def test_software_folds_creators_into_authors_with_license(self) -> None:
        data = {
            "key": "SW1",
            "itemType": "computerProgram",
            "date": "2026",
            "title": "Sim8",
            "rights": "MIT",
            "creators": [
                {"creatorType": "programmer", "firstName": "C", "lastName": "Korikov"},
                {"creatorType": "contributor", "firstName": "A", "lastName": "Lovelace"},
            ],
        }
        pub = parse_item(data)
        assert [str(a) for a in pub.authors] == ["C Korikov", "A Lovelace"]
        assert pub.license == "MIT"

    def test_video_director_is_author(self) -> None:
        data = {
            "key": "V1",
            "itemType": "videoRecording",
            "date": "2024",
            "title": "Talk",
            "creators": [{"creatorType": "director", "firstName": "C", "lastName": "K"}],
        }
        pub = parse_item(data)
        assert [str(a) for a in pub.authors] == ["C K"]

    def test_non_software_has_no_license(self) -> None:
        data = {
            "key": "J1",
            "itemType": "journalArticle",
            "date": "2025",
            "title": "Paper",
            "rights": "CC-BY",
            "creators": [{"creatorType": "author", "firstName": "C", "lastName": "K"}],
        }
        pub = parse_item(data)
        assert type(pub) is Publication
        assert pub.license is None


def make_pub(key: str, pub_type: str, url: str | None = None) -> Publication:
    return Publication(id=key, type=pub_type, year=2024, title=f"Title {key}", url=url)


class TestExtractRelatedKeys:
    def test_empty_relations(self) -> None:
        assert extract_related_keys({}) == []

    def test_single_relation(self) -> None:
        data = {"relations": {"dc:relation": "http://zotero.org/users/123/items/ABCD1234"}}
        assert extract_related_keys(data) == ["ABCD1234"]

    def test_multiple_relations(self) -> None:
        data = {
            "relations": {
                "dc:relation": [
                    "http://zotero.org/users/123/items/KEY00001",
                    "http://zotero.org/users/123/items/KEY00002",
                ]
            }
        }
        assert extract_related_keys(data) == ["KEY00001", "KEY00002"]

    def test_no_dc_relation(self) -> None:
        data = {"relations": {"owl:sameAs": "http://zotero.org/users/123/items/ABCD1234"}}
        assert extract_related_keys(data) == []

    def test_invalid_url_ignored(self) -> None:
        data = {"relations": {"dc:relation": "not-a-valid-url"}}
        assert extract_related_keys(data) == []


class TestMergePreprints:
    def test_no_relations(self) -> None:
        pubs = [
            make_pub("J1", "journalArticle"),
            make_pub("P1", "preprint", "https://arxiv.org/abs/2301.00001"),
        ]
        result = merge_preprints(pubs, {})
        assert len(result) == 2  # nothing merged

    def test_preprint_merged_into_journal(self) -> None:
        journal = make_pub("J1", "journalArticle")
        preprint = make_pub("P1", "preprint", "https://arxiv.org/abs/2301.00001")
        relations = {"P1": ["J1"]}

        result = merge_preprints([journal, preprint], relations)

        assert len(result) == 1
        assert result[0].id == "J1"
        assert result[0].arxiv_url == "https://arxiv.org/abs/2301.00001"

    def test_relation_from_journal_side(self) -> None:
        """Works even if only the journal has the relation (not the preprint)."""
        journal = make_pub("J1", "journalArticle")
        preprint = make_pub("P1", "preprint", "https://arxiv.org/abs/2301.00001")
        relations = {"J1": ["P1"]}

        result = merge_preprints([journal, preprint], relations)

        assert len(result) == 1
        assert result[0].arxiv_url == "https://arxiv.org/abs/2301.00001"

    def test_bidirectional_not_double_processed(self) -> None:
        """Zotero creates bidirectional relations; preprint must appear once."""
        journal = make_pub("J1", "journalArticle")
        preprint = make_pub("P1", "preprint", "https://arxiv.org/abs/2301.00001")
        relations = {"P1": ["J1"], "J1": ["P1"]}

        result = merge_preprints([journal, preprint], relations)

        assert len(result) == 1
        assert result[0].arxiv_url == "https://arxiv.org/abs/2301.00001"

    def test_preprint_without_url_skips_arxiv_url(self) -> None:
        journal = make_pub("J1", "journalArticle")
        preprint = make_pub("P1", "preprint", url=None)
        relations = {"P1": ["J1"]}

        result = merge_preprints([journal, preprint], relations)

        assert len(result) == 1
        assert result[0].arxiv_url is None

    def test_two_unrelated_preprints_kept(self) -> None:
        pubs = [
            make_pub("P1", "preprint", "https://arxiv.org/abs/1"),
            make_pub("P2", "preprint", "https://arxiv.org/abs/2"),
        ]
        result = merge_preprints(pubs, {"P1": ["P2"]})
        assert len(result) == 2  # preprint+preprint — no merge

    def test_conference_paper_merged(self) -> None:
        conf = make_pub("C1", "conferencePaper")
        preprint = make_pub("P1", "preprint", "https://arxiv.org/abs/2301.00001")
        relations = {"P1": ["C1"]}

        result = merge_preprints([conf, preprint], relations)

        assert len(result) == 1
        assert result[0].id == "C1"
        assert result[0].arxiv_url == "https://arxiv.org/abs/2301.00001"

    def test_existing_arxiv_url_not_overwritten(self) -> None:
        journal = make_pub("J1", "journalArticle")
        journal.arxiv_url = "https://arxiv.org/abs/existing"
        preprint = make_pub("P1", "preprint", "https://arxiv.org/abs/new")
        relations = {"P1": ["J1"]}

        result = merge_preprints([journal, preprint], relations)

        assert result[0].arxiv_url == "https://arxiv.org/abs/existing"
