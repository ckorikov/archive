"""Playwright test configuration."""

from pathlib import Path

import pytest

BASE_URL = "http://localhost:1313"
SNAPSHOTS_DIR = Path(__file__).parent / "snapshots"

PAGES = [
    ("/", "index"),
    ("/teaching/", "teaching"),
    ("/teaching/2026-mipt-effective-ai-2026/", "course"),
    ("/casimir/", "casimir"),
    ("/ai/", "ai"),
    ("/about/", "about"),
]


@pytest.fixture(scope="session")
def browser_type_launch_args() -> dict:
    return {"channel": "chrome"}
