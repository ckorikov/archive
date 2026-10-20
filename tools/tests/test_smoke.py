"""Smoke tests: pages load and key elements are present."""

import pytest
from conftest import BASE_URL, PAGES
from playwright.sync_api import Page, expect


@pytest.mark.parametrize("path,name", PAGES)
def test_page_loads(page: Page, path: str, name: str) -> None:
    response = page.goto(BASE_URL + path)
    assert response is not None and response.status == 200, f"{path} returned {response}"
    expect(page.locator("body")).not_to_contain_text("404")


def test_index_has_nav(page: Page) -> None:
    page.goto(BASE_URL + "/")
    expect(page.locator(".nav")).to_be_visible()


def test_index_has_groups(page: Page) -> None:
    page.goto(BASE_URL + "/")
    expect(page.locator(".group_type").first).to_be_visible()


def test_teaching_has_courses(page: Page) -> None:
    page.goto(BASE_URL + "/teaching/")
    expect(page.locator(".course").first).to_be_visible()


def test_course_has_syllabus(page: Page) -> None:
    page.goto(BASE_URL + "/teaching/2026-mipt-effective-ai-2026/")
    expect(page.locator(".syllabus")).to_be_visible()


def test_course_has_description(page: Page) -> None:
    page.goto(BASE_URL + "/teaching/2026-mipt-effective-ai-2026/")
    expect(page.locator(".course-header__description")).to_be_visible()


def test_casimir_has_publications(page: Page) -> None:
    page.goto(BASE_URL + "/casimir/")
    expect(page.locator(".item").first).to_be_visible()


@pytest.mark.parametrize("path,name", PAGES)
def test_page_has_own_og_card(page: Page, path: str, name: str) -> None:
    page.goto(BASE_URL + path)
    meta = page.locator('meta[property="og:image"]')
    image_url = meta.get_attribute("content")
    assert image_url and image_url.endswith(".jpg"), image_url
    assert page.locator('meta[property="og:image:width"]').get_attribute("content") == "1200"
    assert page.locator('meta[property="og:image:height"]').get_attribute("content") == "630"
    response = page.request.get(image_url)
    assert response.status == 200, f"{image_url} returned {response.status}"
    assert response.headers["content-type"] == "image/jpeg"
