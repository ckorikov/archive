#!/usr/bin/env python3
"""Fetch publications from Zotero and save to publications.json."""

import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import click
from pyzotero import zotero

from models import Author, Publication, PublicationsData, get_data_dir

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

ZOTERO_API_KEY = os.environ.get("ZOTERO_API_KEY", "hTvqMYvC4Bjhm4xGHqyCTSWv")
ZOTERO_LIBRARY_ID = int(os.environ.get("ZOTERO_LIBRARY_ID", "4809962"))
ZOTERO_LIBRARY_TYPE = os.environ.get("ZOTERO_LIBRARY_TYPE", "user")


def parse_date(date_str: str | None) -> tuple[int, int | None, int | None]:
    """Parse Zotero date string into (year, month, day)."""
    if not date_str:
        return (0, None, None)

    formats = ["%Y/%m/%d", "%Y-%m-%d", "%Y/%m", "%Y-%m", "%Y"]
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            if fmt in ("%Y/%m/%d", "%Y-%m-%d"):
                return (dt.year, dt.month, dt.day)
            if fmt in ("%Y/%m", "%Y-%m"):
                return (dt.year, dt.month, None)
            return (dt.year, None, None)
        except ValueError:
            continue

    # Try to extract year from string
    match = re.search(r"\b(19|20)\d{2}\b", date_str)
    if match:
        return (int(match.group()), None, None)

    return (0, None, None)


def normalize_language(lang: str | None) -> str:
    """Normalize language string."""
    if not lang:
        return "english"
    if "ru" in lang.lower():
        return "russian"
    return "english"


def parse_item(data: dict) -> Publication | None:
    """Parse Zotero item data into Publication."""
    item_type = data.get("itemType", "")
    if item_type in ("attachment", "note"):
        return None

    # Handle websiteType override (for github, colab, etc.)
    if "websiteType" in data:
        item_type = data["websiteType"].lower()

    year, month, day = parse_date(data.get("date"))
    if year == 0:
        log.warning(f"Skipping item without year: {data.get('title', 'unknown')}")
        return None

    authors = [
        Author(firstName=c.get("firstName", ""), lastName=c.get("lastName", ""))
        for c in data.get("creators", [])
        if c.get("creatorType") in ("author", "presenter", None)
    ]

    tags = [tag["tag"] for tag in data.get("tags", [])]

    # Course-related fields (for presentations/lectures)
    course = data.get("meetingName") or None
    school = data.get("place") or None
    section = data.get("sessionTitle") or None

    # Clean empty strings
    if course == "":
        course = None
    if school == "":
        school = None
    if section == "":
        section = None

    return Publication(
        id=data["key"],
        type=item_type,
        year=year,
        month=month,
        day=day,
        title=data.get("title", "Untitled"),
        authors=authors,
        tags=tags,
        url=data.get("url") or None,
        language=normalize_language(data.get("language")),
        course=course,
        school=school,
        section=section,
    )


def fetch_item_details(zt: zotero.Zotero, key: str, retries: int = 3) -> dict:
    """Fetch full details for a single item with retry."""
    import time

    for attempt in range(retries):
        try:
            return zt.item(key)
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(1)
                continue
            raise e


def fetch_from_zotero(workers: int = 8) -> list[dict]:
    """Fetch all items from Zotero library with full details."""
    log.info(f"Fetching from Zotero library {ZOTERO_LIBRARY_ID}")
    zt = zotero.Zotero(ZOTERO_LIBRARY_ID, ZOTERO_LIBRARY_TYPE, ZOTERO_API_KEY)
    zt.add_parameters(sort="date")

    # First pass: get list of items
    items = zt.everything(zt.publications())
    log.info(f"Fetched {len(items)} items, getting details with {workers} workers...")

    # Second pass: get full details in parallel (includes tags)
    keys = [item["data"]["key"] for item in items]
    detailed_items = []

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(fetch_item_details, zt, key): key for key in keys}
        for i, future in enumerate(as_completed(futures)):
            detailed_items.append(future.result())
            if (i + 1) % 20 == 0:
                log.info(f"  {i + 1}/{len(keys)} items processed")

    log.info(f"Fetched details for {len(detailed_items)} items")
    return detailed_items


def parse_items(items: list[dict]) -> list[Publication]:
    """Parse Zotero items into Publications."""
    publications = []
    for item in items:
        data = item.get("data", item)
        pub = parse_item(data)
        if pub:
            publications.append(pub)
    log.info(f"Parsed {len(publications)} publications")
    return publications


@click.command()
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    default=None,
    help="Output JSON file path",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Fetch and parse but don't save",
)
def main(output: str | None, dry_run: bool) -> None:
    """Fetch publications from Zotero and save to JSON."""
    items = fetch_from_zotero()
    publications = parse_items(items)

    if dry_run:
        log.info("Dry run - not saving")
        for pub in publications[:5]:
            print(f"  {pub.year}: {pub.title[:50]}...")
        return

    output_path = Path(output) if output else get_data_dir() / "publications.json"
    data = PublicationsData(publications=publications)
    data.save(output_path)
    log.info(f"Saved to {output_path}")


if __name__ == "__main__":
    main()
