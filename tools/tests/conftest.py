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


@pytest.fixture
def snapshot(request: pytest.FixtureRequest, pytestconfig: pytest.Config):
    """Simple PNG snapshot fixture. Use --snapshot-update to refresh."""
    update = pytestconfig.getoption("--snapshot-update", default=False)

    class Snapshot:
        def assert_match(self, data: bytes, name: str) -> None:
            path = SNAPSHOTS_DIR / name
            if update or not path.exists():
                SNAPSHOTS_DIR.mkdir(exist_ok=True)
                path.write_bytes(data)
                return
            existing = path.read_bytes()
            assert data == existing, f"Screenshot mismatch: {name}"

    return Snapshot()
