#!/usr/bin/env python3
"""Fetch publications from Zotero and save to publications.json."""

import logging
import os
import re
import threading
import time
from collections import defaultdict
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
PREPRINT_TYPES = {"preprint"}
PRIMARY_TYPES = {"journalArticle", "conferencePaper", "report"}
SOFTWARE_TYPE = "computerProgram"
# Zotero itemType -> artifact kind, ordered by display priority (slides first).
EVENT_KINDS = {"presentation": "slides", "videoRecording": "video"}
KIND_ORDER = {kind: i for i, kind in enumerate(EVENT_KINDS.values())}

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


def merge_preprints(
    publications: list[Publication],
    relations: dict[str, list[str]],
) -> list[Publication]:
    """Merge preprint+journal pairs: copy arXiv URL to primary, drop preprint.

    Uses Zotero Related Items to detect pairs. Handles both directions
    (preprint→journal and journal→preprint).
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

            if pub.type in PREPRINT_TYPES and related.type in PRIMARY_TYPES:
                preprint, primary = pub, related
            elif related.type in PREPRINT_TYPES and pub.type in PRIMARY_TYPES:
                preprint, primary = related, pub
            else:
                continue

            if primary.arxiv_url is None:
                primary.arxiv_url = preprint.url
            to_remove.add(preprint.id)

    merged = [p for p in publications if p.id not in to_remove]
    if to_remove:
        log.info(f"Merged {len(to_remove)} preprint(s) into primary publications")
    return merged


def _undirected_graph(relations: dict[str, list[str]]) -> dict[str, set[str]]:
    """Build a symmetric adjacency map from Zotero's directed relations."""
    adj: dict[str, set[str]] = defaultdict(set)
    for key, related in relations.items():
        for other in related:
            adj[key].add(other)
            adj[other].add(key)
    return adj


def _event_component(
    start: str,
    adj: dict[str, set[str]],
    by_key: dict[str, Publication],
) -> list[Publication]:
    """Connected component reachable through event-type items only.

    Traversal stops at non-event nodes (they are neither collected nor
    expanded), so unrelated clusters cannot bridge through, say, a paper.
    """
    seen: set[str] = set()
    stack = [start]
    component: list[Publication] = []
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        pub = by_key.get(cur)
        if pub is None or pub.type not in EVENT_KINDS:
            continue
        component.append(pub)
        stack.extend(adj.get(cur, ()))
    return component


def merge_event_artifacts(
    publications: list[Publication],
    relations: dict[str, list[str]],
) -> list[Publication]:
    """Collapse linked slides+video of one event into a single card.

    Like merge_preprints, pairs come from Zotero Related Items (symmetric and
    transitive). Unlike preprints, the secondary record's link is kept: the
    primary (the presentation) gains an `artifacts` list with each member's
    kind and URL, and the others are dropped. Roles come from itemType, since
    the relation itself carries no type.
    """
    adj = _undirected_graph(relations)
    by_key = {p.id: p for p in publications}
    to_remove: set[str] = set()
    visited: set[str] = set()

    for pub in publications:
        if pub.id in visited or pub.type not in EVENT_KINDS:
            continue
        component = _event_component(pub.id, adj, by_key)
        visited |= {p.id for p in component}
        # Both types required — leaves slides-only lecture runs untouched.
        if {p.type for p in component} != set(EVENT_KINDS):
            continue
        # slides sort first, so ordered[0] is the presentation (surviving card).
        ordered = sorted(
            component,
            key=lambda p: (KIND_ORDER[EVENT_KINDS[p.type]], *p.date_sort_key, p.title),
        )
        primary = ordered[0]
        primary.artifacts = [Artifact(kind=EVENT_KINDS[p.type], url=p.url) for p in ordered if p.url]
        to_remove |= {p.id for p in ordered[1:]}

    if to_remove:
        log.info(f"Merged {len(to_remove)} event artifact(s) into presentation cards")
    return [p for p in publications if p.id not in to_remove]


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

    Preprints related to journal articles via Zotero Related Items are merged:
    the arXiv URL is copied to the primary publication and the preprint is dropped.
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
