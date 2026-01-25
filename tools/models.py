"""Pydantic models and utilities for archive-tools."""

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


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


TYPE_ICONS: dict[str, str] = {
    "journalArticle": "fa-file-alt",
    "presentation": "fa-chalkboard-teacher",
    "thesis": "fa-user-graduate",
    "conferencePaper": "fa-file-alt",
    "book": "fa-book",
    "bookSection": "fa-book-open",
    "blogPost": "fa-globe",
    "videoRecording": "fa-video",
    "webpage": "fa-link",
    "report": "fa-file-contract",
    "preprint": "fa-file-alt",
}

RESEARCH_TYPES: set[str] = {"journalArticle", "conferencePaper", "thesis", "preprint", "report"}


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

    id: str
    type: str
    year: int
    month: int | None = None
    day: int | None = None
    title: str
    authors: list[Author] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    url: str | None = None
    language: str = "english"
    course: str | None = None
    school: str | None = None
    section: str | None = None

    @property
    def icon(self) -> str:
        """Get icon class for this publication type."""
        return TYPE_ICONS.get(self.type, "fa-file")

    @property
    def date_sort_key(self) -> tuple[int, int, int]:
        """Sort key for chronological ordering."""
        return (self.year, self.month or 0, self.day or 0)


class Course(BaseModel):
    """Computed course from publications."""

    slug: str
    name: str
    school: str
    school_short: str
    year: int
    lectures: list[Publication] = Field(default_factory=list)
    sections: dict[str, list[Publication]] = Field(default_factory=dict)

    @classmethod
    def from_lectures(
        cls,
        name: str,
        school: str,
        lectures: list[Publication],
        school_mapping: dict[str, str],
    ) -> Course:
        """Create course from list of lectures."""
        sorted_lectures = sorted(lectures, key=lambda p: p.date_sort_key)
        year = min(lec.year for lec in sorted_lectures)
        school_short = school_mapping.get(school, school)
        slug = f"{year}-{slugify(school_short)}-{slugify(name)}"

        sections: dict[str, list[Publication]] = {}
        for lec in sorted_lectures:
            section_name = lec.section or ""
            sections.setdefault(section_name, []).append(lec)

        return cls(
            slug=slug,
            name=name,
            school=school,
            school_short=school_short,
            year=year,
            lectures=sorted_lectures,
            sections=sections,
        )


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


class SiteConfig(BaseModel):
    """Site configuration."""

    author: str


class ArchiveConfig(BaseModel):
    """Full archive.yaml configuration."""

    site: SiteConfig
    schools: dict[str, str] = Field(default_factory=dict)
    sections: list[Section] = Field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> ArchiveConfig:
        """Load configuration from YAML file."""
        import yaml

        with path.open() as f:
            data = yaml.safe_load(f)
        return cls.model_validate(data)


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
    """Convert text to URL-safe slug."""
    import re

    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return re.sub(r"-+", "-", text).strip("-")


def get_project_root() -> Path:
    """Get project root directory."""
    return Path(__file__).parent.parent


def get_data_dir() -> Path:
    """Get data directory path."""
    return get_project_root() / "data"


def get_content_dir() -> Path:
    """Get content directory path."""
    return get_project_root() / "site" / "content"


def get_archive_config_path() -> Path:
    """Get archive.yaml path."""
    return get_project_root() / "archive.yaml"
