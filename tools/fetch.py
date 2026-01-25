#!/usr/bin/env python3
"""Fetch publications from Zotero and save to publications.json."""

import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import click
from pyzotero import zotero

from models import Author, Publication, PublicationsData, get_data_dir

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ZoteroFetcherConfig:
    """Zotero API configuration."""

    api_key: str
    library_id: int
    library_type: str = "user"
    workers: int = 8
    retries: int = 3

    @classmethod
    def from_env(cls) -> ZoteroFetcherConfig:
        return cls(
            api_key=os.environ.get("ZOTERO_API_KEY", "hTvqMYvC4Bjhm4xGHqyCTSWv"),
            library_id=int(os.environ.get("ZOTERO_LIBRARY_ID", "4809962")),
            library_type=os.environ.get("ZOTERO_LIBRARY_TYPE", "user"),
        )


SKIP_TYPES = {"attachment", "note"}
AUTHOR_TYPES = {"author", "presenter", None}

DATE_FORMATS = [
    ("%Y/%m/%d", lambda dt: (dt.year, dt.month, dt.day)),
    ("%Y-%m-%d", lambda dt: (dt.year, dt.month, dt.day)),
    ("%Y/%m", lambda dt: (dt.year, dt.month, None)),
    ("%Y-%m", lambda dt: (dt.year, dt.month, None)),
    ("%Y", lambda dt: (dt.year, None, None)),
]


def parse_date(date_str: str | None) -> tuple[int, int | None, int | None]:
    """Parse Zotero date string into (year, month, day)."""
    if not date_str:
        return (0, None, None)

    for fmt, extractor in DATE_FORMATS:
        try:
            return extractor(datetime.strptime(date_str, fmt))
        except ValueError:
            continue

    match = re.search(r"\b(19|20)\d{2}\b", date_str)
    if match:
        return (int(match.group()), None, None)

    return (0, None, None)


def normalize_language(lang: str | None) -> str:
    """Normalize language to 'russian' or 'english'."""
    if lang and "ru" in lang.lower():
        return "russian"
    return "english"


def empty_to_none(value: str | None) -> str | None:
    """Convert empty string to None."""
    return value if value else None


def parse_item(data: dict[str, Any]) -> Publication | None:
    """Parse Zotero item data into Publication."""
    item_type = data.get("itemType", "")

    if "websiteType" in data:
        item_type = data["websiteType"].lower()

    year, month, day = parse_date(data.get("date"))
    if year == 0:
        return None

    authors = [
        Author(firstName=c.get("firstName", ""), lastName=c.get("lastName", ""))
        for c in data.get("creators", [])
        if c.get("creatorType") in AUTHOR_TYPES
    ]

    return Publication(
        id=data["key"],
        type=item_type,
        year=year,
        month=month,
        day=day,
        title=data.get("title", "Untitled"),
        authors=authors,
        tags=[tag["tag"] for tag in data.get("tags", [])],
        url=empty_to_none(data.get("url")),
        language=normalize_language(data.get("language")),
        course=empty_to_none(data.get("series")),
        school=empty_to_none(data.get("place")),
        section=empty_to_none(data.get("sessionTitle")),
        presentationType=empty_to_none(data.get("presentationType")),
    )


def fetch_item_details(zt: zotero.Zotero, key: str, retries: int = 3) -> dict[str, Any]:
    """Fetch full item details with exponential backoff retry."""
    for attempt in range(retries):
        try:
            return zt.item(key)
        except Exception as e:
            if attempt < retries - 1:
                delay = 2**attempt  # 1s, 2s, 4s
                log.debug(f"Retry {attempt + 1}/{retries} for {key} in {delay}s: {e}")
                time.sleep(delay)
            else:
                raise


def fetch_from_zotero(config: ZoteroFetcherConfig) -> list[dict[str, Any]]:
    """Fetch all items from Zotero with full details (parallel)."""
    log.info(f"Fetching from Zotero library {config.library_id}")
    zt = zotero.Zotero(config.library_id, config.library_type, config.api_key)
    zt.add_parameters(sort="date")

    items = zt.everything(zt.publications())
    log.info(f"Fetched {len(items)} items, getting details...")

    keys = [item["data"]["key"] for item in items]
    detailed = []

    with ThreadPoolExecutor(max_workers=config.workers) as executor:
        futures = {executor.submit(fetch_item_details, zt, key, config.retries): key for key in keys}
        for future in as_completed(futures):
            detailed.append(future.result())

    log.info(f"Fetched {len(detailed)} item details")
    return detailed


def parse_items(items: list[dict[str, Any]]) -> list[Publication]:
    """Parse Zotero items into Publications, filtering invalid ones."""
    publications = []
    skipped_attachments = 0
    skipped_no_date = 0

    for item in items:
        data = item.get("data", item)
        item_type = data.get("itemType", "")
        title = data.get("title", "unknown")

        if item_type in SKIP_TYPES:
            log.warning(f"Skipped {item_type}: {title}")
            skipped_attachments += 1
            continue

        pub = parse_item(data)
        if pub:
            publications.append(pub)
        else:
            log.warning(f"Skipped (no date): {title}")
            skipped_no_date += 1

    log.info(f"Parsed {len(publications)}/{len(items)} items")
    if skipped_attachments or skipped_no_date:
        log.warning(f"Total skipped: {skipped_attachments} attachments, {skipped_no_date} no date")
    return publications


@click.command()
@click.option("-o", "--output", type=click.Path(), help="Output JSON file path")
@click.option("--dry-run", is_flag=True, help="Fetch and parse but don't save")
def main(output: str | None, dry_run: bool) -> None:
    """Fetch publications from Zotero and save to JSON."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    config = ZoteroFetcherConfig.from_env()
    items = fetch_from_zotero(config)
    publications = parse_items(items)

    if dry_run:
        log.info("Dry run - not saving")
        for pub in publications[:5]:
            print(f"  {pub.year}: {pub.title[:50]}...")
        return

    output_path = Path(output) if output else get_data_dir() / "publications.json"
    PublicationsData(publications=publications).save(output_path)
    log.info(f"Saved to {output_path}")


if __name__ == "__main__":
    main()
