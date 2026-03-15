"""Visual tests: pages render without errors and produce non-empty screenshots."""

import pytest
from conftest import BASE_URL, PAGES, SNAPSHOTS_DIR
from playwright.sync_api import Page

VIEWPORT_DESKTOP = {"width": 1280, "height": 800}
VIEWPORT_MOBILE = {"width": 390, "height": 844}


def take_screenshot(page: Page, path: str, name: str, suffix: str) -> None:
    page.goto(BASE_URL + path)
    page.wait_for_load_state("networkidle")
    data = page.screenshot(full_page=True)
    assert len(data) > 1000, f"Screenshot too small for {path}"
    SNAPSHOTS_DIR.mkdir(exist_ok=True)
    (SNAPSHOTS_DIR / f"{name}-{suffix}.png").write_bytes(data)


@pytest.mark.parametrize("path,name", PAGES)
def test_screenshot_desktop(page: Page, path: str, name: str) -> None:
    page.set_viewport_size(VIEWPORT_DESKTOP)
    take_screenshot(page, path, name, "desktop")


@pytest.mark.parametrize("path,name", PAGES)
def test_screenshot_mobile(page: Page, path: str, name: str) -> None:
    page.set_viewport_size(VIEWPORT_MOBILE)
    take_screenshot(page, path, name, "mobile")
