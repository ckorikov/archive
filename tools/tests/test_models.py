"""Unit tests for models.py helpers."""

import unicodedata

import pytest

from models import slugify


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
