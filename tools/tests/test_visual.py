"""Visual regression tests: screenshot comparison."""

import pytest
from conftest import BASE_URL, PAGES
from playwright.sync_api import Page

VIEWPORT = {"width": 1280, "height": 800}
VIEWPORT_MOBILE = {"width": 390, "height": 844}


@pytest.mark.parametrize("path,name", PAGES)
def test_screenshot_desktop(page: Page, path: str, name: str, snapshot) -> None:
    page.set_viewport_size(VIEWPORT)
    page.goto(BASE_URL + path)
    page.wait_for_load_state("networkidle")
    snapshot.assert_match(page.screenshot(full_page=True), f"{name}-desktop.png")


@pytest.mark.parametrize("path,name", PAGES)
def test_screenshot_mobile(page: Page, path: str, name: str, snapshot) -> None:
    page.set_viewport_size(VIEWPORT_MOBILE)
    page.goto(BASE_URL + path)
    page.wait_for_load_state("networkidle")
    snapshot.assert_match(page.screenshot(full_page=True), f"{name}-mobile.png")
