"""Smoke tests: pages load and key elements are present."""

import pytest
from conftest import BASE_URL, PAGES
from playwright.sync_api import Page, expect


@pytest.mark.parametrize("path,name", PAGES)
def test_page_loads(page: Page, path: str, name: str) -> None:
    response = page.goto(BASE_URL + path)
    assert response is not None and response.status == 200, f"{path} returned {response}"


@pytest.mark.parametrize("path,name", PAGES)
def test_no_404_text(page: Page, path: str, name: str) -> None:
    page.goto(BASE_URL + path)
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
