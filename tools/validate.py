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
    PublicationsData,
    get_archive_config_path,
    get_static_data_dir,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)


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

    errors = 0

    data = validate_publications(pub_path)
    if data is None:
        errors += 1

    cfg = validate_config(config_path)
    if cfg is None:
        errors += 1

    if errors:
        sys.exit(1)

    print_stats(data)
    log.info("All validations passed")


if __name__ == "__main__":
    main()
