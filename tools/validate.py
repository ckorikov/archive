#!/usr/bin/env python3
"""Validate publications.json against Pydantic schema."""

import logging
import sys
from pathlib import Path

import click
from pydantic import ValidationError

from models import (
    RESEARCH_TYPES,
    ArchiveConfig,
    Publication,
    PublicationsData,
    get_archive_config_path,
    get_static_data_dir,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

# URL-bearing fields scanned for editorial issues.
URL_FIELDS = ("url", "pdf")
FORBIDDEN_URL_HOST = "dropbox.com"
MAX_TITLE_LEN = 60
MAX_AUTHORS = 3


def describe(pub: Publication) -> str:
    """Human-readable label for warnings: id, title, first authors."""
    title = pub.title
    if len(title) > MAX_TITLE_LEN:
        title = title[: MAX_TITLE_LEN - 1] + "…"
    label = f"{pub.id} '{title}'"
    if pub.authors:
        names = ", ".join(str(a) for a in pub.authors[:MAX_AUTHORS])
        if len(pub.authors) > MAX_AUTHORS:
            names += " et al."
        label += f" ({names})"
    return label


def check_url_present(pub: Publication) -> list[str]:
    """WARN if url is missing, empty, or a placeholder '#'."""
    url = (pub.url or "").strip()
    if not url or url == "#":
        return [f"{describe(pub)}: missing or placeholder url ({pub.url!r})"]
    return []


def check_no_dropbox(pub: Publication) -> list[str]:
    """WARN if any URL points at Dropbox — PDFs should live locally."""
    sources = [(field, getattr(pub, field) or "") for field in URL_FIELDS]
    sources += [(a.kind, a.url) for a in pub.artifacts]
    return [
        f"{describe(pub)}: {name} points at {FORBIDDEN_URL_HOST} ({value})"
        for name, value in sources
        if FORBIDDEN_URL_HOST in value
    ]


def check_authors(pub: Publication) -> list[str]:
    """WARN if the author list is empty (software folds programmers in here)."""
    if not pub.authors:
        return [f"{describe(pub)}: empty author list"]
    return []


def check_group_overlap(pub: Publication, config: ArchiveConfig) -> list[str]:
    """WARN if a publication matches more than one group.

    Grouping is 'first match wins' by group order, so a multi-group match
    means classification silently depends on the order of groups.
    """
    pub_tags = set(config.normalize_list(pub.tags))
    matched = [g.name for g in config.groups if pub_tags & {config.normalize(t) for t in g.tags}]
    if len(matched) > 1:
        return [f"{describe(pub)}: matches multiple groups {matched}"]
    return []


def check_editorial(data: PublicationsData, config: ArchiveConfig) -> tuple[list[str], list[str]]:
    """Apply editorial rules. Return (errors, warnings)."""
    errors: list[str] = []
    warnings: list[str] = []
    for pub in data.publications:
        warnings += check_url_present(pub)
        warnings += check_no_dropbox(pub)
        warnings += check_authors(pub)
        warnings += check_group_overlap(pub, config)
    return errors, warnings


def validate_publications(path: Path) -> PublicationsData | None:
    """Validate publications.json file."""
    if not path.exists():
        log.error(f"File not found: {path}")
        return None

    try:
        data = PublicationsData.load(path)
        log.info(f"Validated {len(data.publications)} publications")
        return data
    except ValidationError as e:
        log.error(f"Validation failed:\n{e}")
        return None


def validate_config(path: Path) -> ArchiveConfig | None:
    """Validate archive.yaml file."""
    if not path.exists():
        log.error(f"File not found: {path}")
        return None

    try:
        config = ArchiveConfig.load(path)
        log.info(f"Validated config: {len(config.groups)} groups, {len(config.sections)} sections")
        return config
    except ValidationError as e:
        log.error(f"Config validation failed:\n{e}")
        return None


def print_stats(data: PublicationsData) -> None:
    """Print publication statistics."""
    pubs = data.publications
    years = [p.year for p in pubs]
    research_pubs = [p for p in pubs if p.pub_type in RESEARCH_TYPES]
    paper_num = len(research_pubs)
    # Count courses by unique (course, school) pairs
    courses = {(p.course, p.school or "") for p in pubs if p.course}

    print("\n--- Statistics ---")
    print(f"papers: {paper_num}")
    print(f"courses: {len(courses)}")
    print(f"year_start: {min(years)}")
    print(f"year_end: {max(years)}")


@click.command()
@click.option("-p", "--publications", type=click.Path(), help="Path to publications.json")
@click.option("-c", "--config", type=click.Path(), help="Path to archive.yaml")
def main(publications: str | None, config: str | None) -> None:
    """Validate data files and show statistics."""
    pub_path = Path(publications) if publications else get_static_data_dir() / "publications.json"
    config_path = Path(config) if config else get_archive_config_path()

    data = validate_publications(pub_path)
    cfg = validate_config(config_path)

    if data is None or cfg is None:
        log.error("Validation failed, see errors above")
        sys.exit(1)

    errors, warnings = check_editorial(data, cfg)
    for w in warnings:
        log.warning(w)
    for e in errors:
        log.error(e)
    if errors:
        log.error(f"Editorial validation failed: {len(errors)} error(s)")
        sys.exit(1)

    print_stats(data)
    log.info("All validations passed")


if __name__ == "__main__":
    main()
