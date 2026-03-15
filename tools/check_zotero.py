#!/usr/bin/env python3
"""Check if Zotero My Publications have changed. Outputs SHA256 hash of versions."""

import hashlib
import json
import os
import sys

from pyzotero import zotero


def get_publications_hash(library_id: int, library_type: str, api_key: str) -> str:
    """Fetch publication versions from Zotero and return their SHA256 hash."""
    zt = zotero.Zotero(library_id, library_type, api_key)
    versions: dict[str, int] = zt.publications(format="versions")
    canonical = json.dumps(versions, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def main() -> None:
    api_key = os.environ.get("ZOTERO_API_KEY")
    library_id = os.environ.get("ZOTERO_LIBRARY_ID")
    if not api_key or not library_id:
        print("Missing ZOTERO_API_KEY or ZOTERO_LIBRARY_ID", file=sys.stderr)
        sys.exit(1)

    library_type = os.environ.get("ZOTERO_LIBRARY_TYPE", "user")
    h = get_publications_hash(int(library_id), library_type, api_key)
    print(h)


if __name__ == "__main__":
    main()
