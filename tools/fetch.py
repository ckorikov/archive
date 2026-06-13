#!/usr/bin/env python3
"""Fetch publications from Zotero and save to publications.json."""

import logging
import os
import re
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import click
from pyzotero import zotero

from models import Artifact, Author, Publication, PublicationsData, get_static_data_dir

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
        api_key = os.environ.get("ZOTERO_API_KEY")
        library_id = os.environ.get("ZOTERO_LIBRARY_ID")
        if not api_key or not library_id:
            raise SystemExit("Missing ZOTERO_API_KEY or ZOTERO_LIBRARY_ID.\nSet credentials in .env (see README).")
        return cls(
            api_key=api_key,
            library_id=int(library_id),
            library_type=os.environ.get("ZOTERO_LIBRARY_TYPE", "user"),
        )


SKIP_TYPES = {"attachment", "note"}
# Creator roles folded into authors — all answer "who made it".
AUTHOR_TYPES = {"author", "presenter", "director", "programmer", "contributor", None}
PRIMARY_TYPES = {"journalArticle", "conferencePaper", "report"}
SOFTWARE_TYPE = "computerProgram"
# Zotero itemType -> artifact kind for a preprint merged into its published version.
PREPRINT_KINDS = {"preprint": "arxiv"}
# Zotero itemType -> artifact kind for the two halves of one event.
EVENT_KINDS = {"presentation": "slides", "videoRecording": "video"}

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


def extract_related_keys(data: dict[str, Any]) -> list[str]:
    """Extract related item keys from Zotero relations field.

    Zotero stores relations as URLs: http://zotero.org/users/123/items/KEY
    """
    relations = data.get("relations", {})
    dc_relation = relations.get("dc:relation", [])
    if isinstance(dc_relation, str):
        dc_relation = [dc_relation]
    matches = (re.search(r"/items/([A-Z0-9]+)$", url) for url in dc_relation)
    return [m.group(1) for m in matches if m]


def _merge_related(
    publications: list[Publication],
    relations: dict[str, list[str]],
    fold: Callable[[Publication, Publication], str | None],
    label: str,
) -> list[Publication]:
    """Walk Related Item pairs; `fold` collapses a pair and returns the id to drop.

    `fold(pub, related)` applies its policy (which is primary, what to copy) and
    returns the secondary's id, or None if the pair doesn't apply. Already-dropped
    records are skipped, so bidirectional relations collapse once.
    """
    by_key = {p.id: p for p in publications}
    to_remove: set[str] = set()
    for pub in publications:
        if pub.id in to_remove:
            continue
        for related_key in relations.get(pub.id, []):
            related = by_key.get(related_key)
            if related is None or related.id in to_remove:
                continue
            dropped = fold(pub, related)
            if dropped:
                to_remove.add(dropped)
    if to_remove:
        log.info(f"Merged {len(to_remove)} {label}")
    return [p for p in publications if p.id not in to_remove]


def merge_preprints(
    publications: list[Publication],
    relations: dict[str, list[str]],
) -> list[Publication]:
    """Add a preprint's arXiv link to its published version, then drop the preprint."""

    def fold(pub: Publication, related: Publication) -> str | None:
        if pub.type in PREPRINT_KINDS and related.type in PRIMARY_TYPES:
            preprint, primary = pub, related
        elif related.type in PREPRINT_KINDS and pub.type in PRIMARY_TYPES:
            preprint, primary = related, pub
        else:
            return None
        kind = PREPRINT_KINDS[preprint.type]
        if preprint.url and not any(a.kind == kind for a in primary.artifacts):
            primary.artifacts.append(Artifact(kind=kind, url=preprint.url))
        return preprint.id

    return _merge_related(publications, relations, fold, "preprint(s) into published versions")


def merge_event_artifacts(
    publications: list[Publication],
    relations: dict[str, list[str]],
) -> list[Publication]:
    """Collapse a linked presentation+video into one card; drop the video.

    The presentation becomes the card and keeps both links as `artifacts`
    (slides, video) — unlike a preprint, the secondary link is not lost.
    """

    def fold(pub: Publication, related: Publication) -> str | None:
        types = {pub.type, related.type}
        if types != set(EVENT_KINDS):
            return None
        slides, video = (pub, related) if pub.type == "presentation" else (related, pub)
        slides.artifacts = [Artifact(kind=EVENT_KINDS[p.type], url=p.url) for p in (slides, video) if p.url]
        return video.id

    return _merge_related(publications, relations, fold, "event video(s) into presentation cards")


def parse_item(data: dict[str, Any]) -> Publication | None:
    """Parse Zotero item data into Publication."""
    item_type = data.get("itemType", "")

    if "websiteType" in data:
        item_type = data["websiteType"].lower()

    year, month, day = parse_date(data.get("date"))
    if year == 0:
        return None

    def creators_of(*types: str | None) -> list[Author]:
        wanted = set(types)
        return [
            Author(firstName=c.get("firstName", ""), lastName=c.get("lastName", ""))
            for c in data.get("creators", [])
            if c.get("creatorType") in wanted
        ]

    license_ = empty_to_none(data.get("rights")) if item_type == SOFTWARE_TYPE else None

    return Publication(
        id=data["key"],
        type=item_type,
        year=year,
        month=month,
        day=day,
        title=data.get("title", "Untitled"),
        authors=creators_of(*AUTHOR_TYPES),
        tags=[tag["tag"] for tag in data.get("tags", [])],
        url=empty_to_none(data.get("url")),
        license=license_,
        language=normalize_language(data.get("language")),
        course=empty_to_none(data.get("series")),
        school=empty_to_none(data.get("place")),
        section=empty_to_none(data.get("sessionTitle")),
        presentationType=empty_to_none(data.get("presentationType")),
    )


def fetch_item_details(zt_factory: Callable[[], zotero.Zotero], key: str, retries: int = 3) -> dict[str, Any]:
    """Fetch full item details with exponential backoff retry.

    Uses a per-thread Zotero client because pyzotero stores per-request state
    (self.request, self.url_params) on the instance and is not thread-safe;
    sharing one client across threads corrupts format detection and yields
    raw bytes instead of parsed JSON.

    On HTTP 429 pyzotero records a backoff but does not raise, returning raw
    bytes instead — detect this and retry; the per-thread client's backoff
    timer will throttle the next call.
    """
    zt = zt_factory()
    for attempt in range(retries):
        try:
            result = zt.item(key)
            if isinstance(result, dict):
                return result
            log.debug(f"Rate-limited on {key} (attempt {attempt + 1}/{retries}): {result[:80]!r}")
        except Exception as e:
            if attempt == retries - 1:
                raise
            log.debug(f"Retry {attempt + 1}/{retries} for {key}: {e}")
        if attempt < retries - 1:
            time.sleep(2**attempt)  # 1s, 2s, 4s
    raise RuntimeError(f"Failed to fetch {key} after {retries} retries (rate-limited)")


def fetch_from_zotero(config: ZoteroFetcherConfig) -> list[dict[str, Any]]:
    """Fetch all items from Zotero with full details (parallel)."""
    log.info(f"Fetching from Zotero library {config.library_id}")

    local = threading.local()

    def zt_factory() -> zotero.Zotero:
        client = getattr(local, "client", None)
        if client is None:
            client = zotero.Zotero(config.library_id, config.library_type, config.api_key)
            local.client = client
        return client

    zt = zt_factory()
    zt.add_parameters(sort="date")

    items = zt.everything(zt.publications())
    log.info(f"Fetched {len(items)} items, getting details...")

    keys = [item["data"]["key"] for item in items]
    detailed = []

    with ThreadPoolExecutor(max_workers=config.workers) as executor:
        futures = {executor.submit(fetch_item_details, zt_factory, key, config.retries): key for key in keys}
        for future in as_completed(futures):
            detailed.append(future.result())

    log.info(f"Fetched {len(detailed)} item details")
    return detailed


def parse_items(items: list[dict[str, Any]]) -> list[Publication]:
    """Parse Zotero items into Publications, filtering invalid ones.

    Related items are merged into a primary record's `artifacts` list: a
    preprint contributes its arXiv link, a video its recording link.
    """
    publications = []
    relations: dict[str, list[str]] = {}
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
            related = extract_related_keys(data)
            if related:
                relations[pub.id] = related
        else:
            log.warning(f"Skipped (no date): {title}")
            skipped_no_date += 1

    log.info(f"Parsed {len(publications)}/{len(items)} items")
    if skipped_attachments or skipped_no_date:
        log.warning(f"Total skipped: {skipped_attachments} attachments, {skipped_no_date} no date")

    merged = merge_preprints(publications, relations)
    return merge_event_artifacts(merged, relations)


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

    output_path = Path(output) if output else get_static_data_dir() / "publications.json"
    PublicationsData(publications=publications).save(output_path)
    log.info(f"Saved to {output_path}")


if __name__ == "__main__":
    main()
