"""Pydantic models and utilities for archive-tools."""

import re
import unicodedata
from datetime import date
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

# BGN/PCGN-style romanization: matches how names appear in publications
# ("Юрий" -> "yuriy", not "jurij").
CYRILLIC_TO_LATIN: dict[str, str] = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "kh",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "shch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}


class PublicationType(StrEnum):
    """Supported publication types from Zotero."""

    JOURNAL_ARTICLE = "journalArticle"
    PRESENTATION = "presentation"
    THESIS = "thesis"
    CONFERENCE_PAPER = "conferencePaper"
    BOOK = "book"
    BOOK_SECTION = "bookSection"
    BLOG_POST = "blogPost"
    VIDEO_RECORDING = "videoRecording"
    WEBPAGE = "webpage"
    REPORT = "report"
    PREPRINT = "preprint"


TYPE_ICONS: dict[PublicationType, str] = {
    PublicationType.JOURNAL_ARTICLE: "fa-file-alt",
    PublicationType.PRESENTATION: "fa-chalkboard-teacher",
    PublicationType.THESIS: "fa-user-graduate",
    PublicationType.CONFERENCE_PAPER: "fa-file-alt",
    PublicationType.BOOK: "fa-book",
    PublicationType.BOOK_SECTION: "fa-book-open",
    PublicationType.BLOG_POST: "fa-globe",
    PublicationType.VIDEO_RECORDING: "fa-video",
    PublicationType.WEBPAGE: "fa-link",
    PublicationType.REPORT: "fa-file-contract",
    PublicationType.PREPRINT: "fa-file-alt",
}

RESEARCH_TYPES: set[PublicationType] = {
    PublicationType.JOURNAL_ARTICLE,
    PublicationType.CONFERENCE_PAPER,
    PublicationType.THESIS,
    PublicationType.PREPRINT,
    PublicationType.REPORT,
}

COURSE_TYPES: set[str] = {"Lecture", "GitHub"}


class Author(BaseModel):
    """Publication author."""

    first_name: str = Field(default="", alias="firstName")
    last_name: str = Field(default="", alias="lastName")

    def __str__(self) -> str:
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.last_name or self.first_name


class Artifact(BaseModel):
    """An external link merged from a related item: arxiv, slides, video."""

    kind: str  # "arxiv" | "slides" | "video"
    url: str


class Publication(BaseModel):
    """Single publication from Zotero."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    type: str
    year: int
    month: int | None = None
    day: int | None = None
    title: str
    authors: list[Author] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    url: str | None = None
    pdf: str | None = None  # Local PDF path (for archive)
    language: str = "english"
    course: str | None = Field(default=None, alias="series")
    school: str | None = None
    section: str | None = None
    presentation_type: str | None = Field(default=None, alias="presentationType")
    license: str | None = None  # Software only
    # External links merged from related Zotero items: arxiv, slides, video.
    artifacts: list[Artifact] = Field(default_factory=list)

    @property
    def pub_type(self) -> PublicationType | None:
        """Get publication type as enum."""
        try:
            return PublicationType(self.type)
        except ValueError:
            return None

    @property
    def icon(self) -> str:
        """Get icon class for this publication type."""
        if self.pub_type:
            return TYPE_ICONS.get(self.pub_type, "fa-file")
        return "fa-file"

    @property
    def date_sort_key(self) -> tuple[int, int, int]:
        """Sort key for chronological ordering."""
        return (self.year, self.month or 0, self.day or 0)

    @property
    def pub_date(self) -> date:
        """Publication date, defaulting missing month/day to 1."""
        return date(self.year, self.month or 1, self.day or 1)


class Course(BaseModel):
    """Computed course from publications."""

    slug: str
    name: str
    school: str
    year: int
    lectures: list[Publication] = Field(default_factory=list)
    sections: dict[str, list[Publication]] = Field(default_factory=dict)

    @classmethod
    def from_lectures(
        cls,
        name: str,
        school: str,
        lectures: list[Publication],
    ) -> Course:
        """Create course from list of lectures."""
        if not lectures:
            raise ValueError("from_lectures() requires at least one lecture")
        # Sort by date, then by title for stable ordering
        sorted_lectures = sorted(lectures, key=lambda p: (*p.date_sort_key, p.title))
        year = min(lec.year for lec in sorted_lectures)
        slug_parts = [str(year)]
        if school:
            slug_parts.append(slugify(school))
        slug_parts.append(slugify(name))
        slug = "-".join(slug_parts)

        sections: dict[str, list[Publication]] = {}
        for lec in sorted_lectures:
            section_name = lec.section or ""
            sections.setdefault(section_name, []).append(lec)

        return cls(
            slug=slug,
            name=name,
            school=school,
            year=year,
            lectures=sorted_lectures,
            sections=sections,
        )

    @property
    def tags(self) -> set[str]:
        """Aggregate all tags from lectures."""
        return {t for lec in self.lectures for t in lec.tags}

    @property
    def latest_date(self) -> tuple[int, int, int]:
        """Get date of the latest lecture for sorting."""
        if not self.lectures:
            return (0, 0, 0)
        return max(lec.date_sort_key for lec in self.lectures)


class CourseConfig(BaseModel):
    """Course metadata from archive.yaml."""

    slug: str
    description: str = ""


class Group(BaseModel):
    """Group for main page grouping by tags."""

    name: str
    tags: list[str] = Field(default_factory=list)


class SectionFilter(BaseModel):
    """Filter configuration for a section."""

    tag: str | None = None
    has_course: bool | None = None


class Section(BaseModel):
    """Site section configuration."""

    path: str
    label: str
    filter: SectionFilter | None = None
    group_by: list[str] = Field(default_factory=lambda: ["year"])


class Contacts(BaseModel):
    """Contact information."""

    email: str | None = None
    github: str | None = None
    scholar: str | None = None
    orcid: str | None = None
    linkedin: str | None = None
    twitter: str | None = None


class SiteConfig(BaseModel):
    """Site configuration."""

    author: str
    job_title: str | None = None
    bio: str | None = None
    contacts: Contacts | None = None


class ArchiveConfig(BaseModel):
    """Full archive.yaml configuration."""

    site: SiteConfig
    groups: list[Group] = Field(default_factory=list)
    courses: list[CourseConfig] = Field(default_factory=list)
    sections: list[Section] = Field(default_factory=list)
    aliases: dict[str, list[str]] = Field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> ArchiveConfig:
        """Load configuration from YAML file."""
        import yaml

        with path.open() as f:
            data = yaml.safe_load(f)
        return cls.model_validate(data)

    def course_description(self, slug: str) -> str:
        """Return description for a course slug, or empty string."""
        for c in self.courses:
            if c.slug == slug:
                return c.description
        return ""

    def normalize(self, value: str) -> str:
        """Normalize value using aliases. Return canonical form."""
        for canonical, variants in self.aliases.items():
            if value == canonical or value in variants:
                return canonical
        return value

    def normalize_list(self, values: list[str]) -> list[str]:
        """Normalize list of values, preserving order and removing duplicates."""
        seen: set[str] = set()
        result: list[str] = []
        for v in values:
            normalized = self.normalize(v)
            if normalized not in seen:
                seen.add(normalized)
                result.append(normalized)
        return result


class PublicationsData(BaseModel):
    """Container for publications.json."""

    publications: list[Publication]

    @classmethod
    def load(cls, path: Path) -> PublicationsData:
        """Load publications from JSON file."""
        import json

        with path.open() as f:
            data = json.load(f)
        return cls.model_validate(data)

    def save(self, path: Path) -> None:
        """Save publications to JSON file."""
        import json

        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w") as f:
            json.dump(self.model_dump(by_alias=True), f, indent=2, ensure_ascii=False)


def slugify(text: str) -> str:
    """Convert text to ASCII URL-safe slug with Cyrillic transliteration."""
    # macOS stores filenames in NFD; without NFC 'й' is 'и' + combining mark
    text = unicodedata.normalize("NFC", text).lower()
    chars = [
        CYRILLIC_TO_LATIN[ch] if ch in CYRILLIC_TO_LATIN else (ch if ch.isascii() and ch.isalnum() else "-")
        for ch in text
    ]
    return re.sub(r"-+", "-", "".join(chars)).strip("-")


def get_project_root() -> Path:
    """Get project root directory."""
    return Path(__file__).parent.parent


def get_static_data_dir() -> Path:
    """Get static data directory path (for publications.json)."""
    return get_project_root() / "site" / "static" / "data"


def get_content_dir() -> Path:
    """Get content directory path."""
    return get_project_root() / "site" / "content"


def get_archive_config_path() -> Path:
    """Get archive.yaml path."""
    return get_project_root() / "archive.yaml"
