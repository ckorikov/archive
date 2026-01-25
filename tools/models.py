"""Pydantic models and utilities for archive-tools."""

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class PublicationType(str, Enum):
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
        result: set[str] = set()
        for lec in self.lectures:
            result.update(lec.tags)
        return result

    @property
    def latest_date(self) -> tuple[int, int, int]:
        """Get date of the latest lecture for sorting."""
        if not self.lectures:
            return (0, 0, 0)
        return max(lec.date_sort_key for lec in self.lectures)


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
    linkedin: str | None = None
    twitter: str | None = None


class SiteConfig(BaseModel):
    """Site configuration."""

    author: str
    bio: str | None = None
    contacts: Contacts | None = None


class ArchiveConfig(BaseModel):
    """Full archive.yaml configuration."""

    site: SiteConfig
    groups: list[Group] = Field(default_factory=list)
    sections: list[Section] = Field(default_factory=list)
    aliases: dict[str, list[str]] = Field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> ArchiveConfig:
        """Load configuration from YAML file."""
        import yaml

        with path.open() as f:
            data = yaml.safe_load(f)
        return cls.model_validate(data)

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
    """Convert text to ASCII URL-safe slug with transliteration."""
    import contextlib
    import re

    from transliterate import translit
    from transliterate.exceptions import LanguageDetectionError

    text = text.lower().strip()

    with contextlib.suppress(LanguageDetectionError):
        text = translit(text, reversed=True)

    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return re.sub(r"-+", "-", text).strip("-")


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
