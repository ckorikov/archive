"""Unit tests for models.py helpers."""

import unicodedata

import pytest

from models import Author, Publication, PublicationsData, slugify


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Computer Science", "computer-science"),
        ("Высшая школа", "vysshaya-shkola"),
        ("Юридический", "yuridicheskiy"),
        ("Хэширование щи январь", "kheshirovanie-shchi-yanvar"),
        ("2014_Кориков_TeX", "2014-korikov-tex"),
        ("объём", "obem"),
        ("  --уже-готово--  ", "uzhe-gotovo"),
    ],
)
def test_slugify(text: str, expected: str) -> None:
    assert slugify(text) == expected


def test_slugify_nfd_input() -> None:
    """macOS filenames arrive in NFD: 'й'/'ё' decomposed into base + mark."""
    assert slugify(unicodedata.normalize("NFD", "Йод ёж")) == "yod-ezh"


def test_license_survives_save_load(tmp_path) -> None:
    pub = Publication(
        id="S",
        type="computerProgram",
        year=2026,
        title="Sim8",
        authors=[Author(firstName="C", lastName="Korikov")],
        license="MIT",
    )
    path = tmp_path / "pubs.json"
    PublicationsData(publications=[pub]).save(path)

    loaded = PublicationsData.load(path)
    assert loaded.publications[0].license == "MIT"
