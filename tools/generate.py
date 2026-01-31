#!/usr/bin/env python3
"""Generate Hugo content from publications.json + archive.yaml."""

import logging
import shutil
from pathlib import Path

import click
import yaml

from models import (
    COURSE_TYPES,
    RESEARCH_TYPES,
    ArchiveConfig,
    Course,
    Publication,
    PublicationsData,
    get_archive_config_path,
    get_content_dir,
    get_static_data_dir,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)


def pub_to_item(pub: Publication, config: ArchiveConfig) -> dict:
    """Convert publication to item dict for frontmatter."""
    authors = [config.normalize(str(a)) for a in pub.authors if str(a)]
    tags = config.normalize_list(pub.tags)
    item = {
        "title": pub.title,
        "url": pub.url or "",
        "authors": authors,
        "tags": tags,
    }
    if pub.pdf:
        item["pdf"] = pub.pdf
    return item


def course_to_item(course: Course, config: ArchiveConfig) -> dict:
    """Convert course to item dict for frontmatter (main page)."""
    return {
        "title": config.normalize(course.name),
        "slug": course.slug,
        "school": course.school,
        "year": course.year,
        "lectures_count": len(course.lectures),
        "is_course": True,
    }


def lecture_to_item(lec: Publication) -> dict:
    """Convert lecture publication to item dict."""
    item = {"title": lec.title, "url": lec.url or ""}
    if lec.pdf:
        item["pdf"] = lec.pdf
    return item


def course_to_card(course: Course, config: ArchiveConfig) -> dict:
    """Convert course to card dict with lectures (teaching page)."""
    return {
        "title": config.normalize(course.name),
        "slug": course.slug,
        "year": course.year,
        "lectures_count": len(course.lectures),
        "lectures": [lecture_to_item(lec) for lec in course.lectures],
    }


def group_pubs_by_year(
    publications: list[Publication],
    config: ArchiveConfig,
) -> list[dict]:
    """Group publications by year, return list of year groups."""
    by_year: dict[int, list[Publication]] = {}
    for pub in publications:
        by_year.setdefault(pub.year, []).append(pub)

    groups = []
    for year in sorted(by_year.keys(), reverse=True):
        pubs = sorted(by_year[year], key=lambda p: p.date_sort_key, reverse=True)
        groups.append(
            {
                "year": year,
                "items": [pub_to_item(p, config) for p in pubs],
            }
        )
    return groups


def group_by_year(
    publications: list[Publication],
    courses: list[Course],
    config: ArchiveConfig,
) -> list[dict]:
    """Group publications and courses by year, return list of year groups."""
    by_year: dict[int, list[dict]] = {}

    # Add standalone publications
    for pub in publications:
        item = pub_to_item(pub, config)
        item["_sort_key"] = pub.date_sort_key
        by_year.setdefault(pub.year, []).append(item)

    # Add courses
    for course in courses:
        item = course_to_item(course, config)
        item["_sort_key"] = course.latest_date
        by_year.setdefault(course.year, []).append(item)

    groups = []
    for year in sorted(by_year.keys(), reverse=True):
        items = sorted(by_year[year], key=lambda x: x["_sort_key"], reverse=True)
        items = [{k: v for k, v in item.items() if k != "_sort_key"} for item in items]
        groups.append({"year": year, "items": items})

    return groups


def filter_publications(
    publications: list[Publication],
    config: ArchiveConfig,
    tag: str | None = None,
    has_course: bool | None = None,
) -> list[Publication]:
    """Filter publications by criteria."""
    result = publications

    if tag:
        normalized_tag = config.normalize(tag)
        result = [p for p in result if normalized_tag in config.normalize_list(p.tags)]

    if has_course is True:
        result = [p for p in result if p.course]
    elif has_course is False:
        result = [p for p in result if not p.course]

    return result


def compute_courses(
    publications: list[Publication],
    config: ArchiveConfig,
) -> list[Course]:
    """Compute courses from publications with allowed presentation_type and course field.

    Only publications with presentation_type in COURSE_TYPES become course lectures.
    Other publications with meetingName (e.g. conference presentations) are ignored.
    """
    # Only allowed types with meetingName become course lectures
    lectures = [p for p in publications if p.course and p.presentation_type in COURSE_TYPES]

    # Group by normalized (course, school)
    groups: dict[tuple[str, str], list[Publication]] = {}
    for lec in lectures:
        course_name = config.normalize(lec.course)
        school_name = config.normalize(lec.school) if lec.school else ""
        key = (course_name, school_name)
        groups.setdefault(key, []).append(lec)

    courses = []
    for (name, school), group_lectures in groups.items():
        course = Course.from_lectures(name, school, group_lectures)
        courses.append(course)

    # Sort by year descending, then name
    courses.sort(key=lambda c: (-c.year, c.name))
    return courses


def compute_stats(publications: list[Publication], courses: list[Course]) -> dict:
    """Compute statistics for margin display."""
    years = [p.year for p in publications]
    research_pubs = [p for p in publications if p.pub_type in RESEARCH_TYPES]
    paper_num = len(research_pubs)

    return {
        "papers": paper_num,
        "courses": len(courses),
        "year_start": min(years) if years else 0,
        "year_end": max(years) if years else 0,
    }


def write_frontmatter(path: Path, data: dict, content: str = "") -> None:
    """Write markdown file with YAML frontmatter."""
    path.parent.mkdir(parents=True, exist_ok=True)

    frontmatter = yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False)

    with path.open("w") as f:
        f.write("---\n")
        f.write(frontmatter)
        f.write("---\n")
        if content:
            f.write("\n")
            f.write(content)

    log.debug(f"Wrote {path}")


def match_pubs_by_tags(
    pubs: list[Publication],
    group_tags: set[str],
    seen_ids: set[str],
    config: ArchiveConfig,
) -> list[Publication]:
    """Match publications by tags, updating seen_ids."""
    matched = []
    for pub in pubs:
        if pub.id in seen_ids:
            continue
        pub_tags = set(config.normalize_list(pub.tags))
        if pub_tags & group_tags:
            matched.append(pub)
            seen_ids.add(pub.id)
    return matched


def match_courses_by_tags(
    courses: list[Course],
    group_tags: set[str],
    seen_slugs: set[str],
    config: ArchiveConfig,
) -> list[Course]:
    """Match courses by tags (any lecture tag), updating seen_slugs."""
    matched = []
    for course in courses:
        if course.slug in seen_slugs:
            continue
        course_tags = {config.normalize(t) for t in course.tags}
        if course_tags & group_tags:
            matched.append(course)
            seen_slugs.add(course.slug)
    return matched


def group_items(
    standalone_pubs: list[Publication],
    courses: list[Course],
    config: ArchiveConfig,
) -> list[dict]:
    """Group standalone publications and courses by tags."""
    seen_pub_ids: set[str] = set()
    seen_course_slugs: set[str] = set()
    groups_data = []

    for group in config.groups:
        group_tags = {config.normalize(t) for t in group.tags}
        matched_pubs = match_pubs_by_tags(standalone_pubs, group_tags, seen_pub_ids, config)
        matched_courses = match_courses_by_tags(courses, group_tags, seen_course_slugs, config)

        if matched_pubs or matched_courses:
            groups_data.append({
                "name": group.name,
                "items": group_by_year(matched_pubs, matched_courses, config),
            })

    # Other: items not matching any group
    other_pubs = [p for p in standalone_pubs if p.id not in seen_pub_ids]
    other_courses = [c for c in courses if c.slug not in seen_course_slugs]
    if other_pubs or other_courses:
        groups_data.append({
            "name": "Other",
            "items": group_by_year(other_pubs, other_courses, config),
        })

    return groups_data


def generate_index(
    content_dir: Path,
    publications: list[Publication],
    courses: list[Course],
    config: ArchiveConfig,
    stats: dict,
) -> None:
    """Generate main index page with groups, stats, and nav."""
    standalone = filter_publications(publications, config, has_course=False)
    groups_data = group_items(standalone, courses, config)
    nav_items = [{"path": s.path, "label": s.label} for s in config.sections]

    data = {
        "title": "Publications",
        "layout": "index",
        "stats": stats,
        "nav": nav_items,
        "groups": groups_data,
    }
    write_frontmatter(content_dir / "_index.md", data)

    counts = ", ".join(f"{g['name']}: {sum(len(y['items']) for y in g['items'])}" for g in groups_data)
    log.info(f"Generated _index.md ({counts})")


def generate_section(
    content_dir: Path,
    section_path: str,
    label: str,
    publications: list[Publication],
    config: ArchiveConfig,
) -> None:
    """Generate a section index page with grouped publications."""
    clean_path = section_path.strip("/")
    if not clean_path:
        return

    data = {
        "title": label,
        "type": "publications",
        "publications_count": len(publications),
        "items": group_pubs_by_year(publications, config),
    }

    section_dir = content_dir / clean_path
    write_frontmatter(section_dir / "_index.md", data)
    log.info(f"Generated {clean_path}/_index.md ({len(publications)} publications)")


def group_courses_by_school(courses: list[Course]) -> dict[str, list[Course]]:
    """Group courses by school, sorted by latest date."""
    by_school: dict[str, list[Course]] = {}
    for course in courses:
        by_school.setdefault(course.school, []).append(course)
    return by_school


def generate_course_page(
    teaching_dir: Path,
    course: Course,
    config: ArchiveConfig,
) -> None:
    """Generate individual course page."""
    lectures_data = []
    for lec in course.lectures:
        item = lecture_to_item(lec)
        item["section"] = config.normalize(lec.section) if lec.section else ""
        lectures_data.append(item)

    course_data = {
        "title": config.normalize(course.name),
        "type": "course",
        "layout": "course/single",
        "slug": course.slug,
        "school": course.school,
        "year": course.year,
        "lectures_count": len(course.lectures),
        "lectures": lectures_data,
    }
    write_frontmatter(teaching_dir / f"{course.slug}.md", course_data)


def generate_teaching(
    content_dir: Path,
    courses: list[Course],
    config: ArchiveConfig,
) -> None:
    """Generate teaching section with course pages."""
    teaching_dir = content_dir / "teaching"
    by_school = group_courses_by_school(courses)

    # Sort schools by their latest course date (most recent first)
    schools_sorted = sorted(
        by_school.keys(),
        key=lambda s: max(c.latest_date for c in by_school[s]),
        reverse=True,
    )

    schools_data = []
    for school in schools_sorted:
        school_courses = sorted(by_school[school], key=lambda c: c.latest_date, reverse=True)
        schools_data.append({
            "name": school,
            "courses": [course_to_card(c, config) for c in school_courses],
        })

    # Teaching index
    data = {
        "title": "Teaching",
        "layout": "teaching/list",
        "courses_count": len(courses),
        "schools": schools_data,
    }
    write_frontmatter(teaching_dir / "_index.md", data)
    log.info(f"Generated teaching/_index.md ({len(courses)} courses)")

    # Individual course pages
    for course in courses:
        generate_course_page(teaching_dir, course, config)

    log.info(f"Generated {len(courses)} course pages")


def generate_about(content_dir: Path, config: ArchiveConfig) -> None:
    """Generate about page with contacts."""
    about_path = content_dir / "about" / "_index.md"

    # Skip if file exists (user-edited content)
    if about_path.exists():
        log.info("Skipped about/_index.md (exists)")
        return

    contacts = {}
    if config.site.contacts:
        contacts = config.site.contacts.model_dump(exclude_none=True)

    data = {
        "title": "About",
        "type": "about",
        "contacts": contacts,
    }
    bio = config.site.bio or ""
    write_frontmatter(about_path, data, content=bio)
    log.info("Generated about/_index.md")


def generate_all(
    publications: list[Publication],
    config: ArchiveConfig,
    content_dir: Path,
    clean: bool = False,
) -> None:
    """Generate all content files."""
    if clean and content_dir.exists():
        shutil.rmtree(content_dir)
        log.info(f"Cleaned {content_dir}")

    content_dir.mkdir(parents=True, exist_ok=True)

    # Compute courses and stats
    courses = compute_courses(publications, config)
    stats = compute_stats(publications, courses)

    # Generate main index (includes stats and nav)
    generate_index(content_dir, publications, courses, config, stats)

    # Generate sections from config
    for section in config.sections:
        if section.path == "/":
            continue

        # Apply filters
        section_pubs = publications
        if section.filter:
            section_pubs = filter_publications(
                publications,
                config,
                tag=section.filter.tag,
                has_course=section.filter.has_course,
            )

        # Special sections
        if section.filter and section.filter.has_course:
            generate_teaching(content_dir, courses, config)
        else:
            generate_section(content_dir, section.path, section.label, section_pubs, config)

    # Generate about page (not in nav)
    generate_about(content_dir, config)


@click.command()
@click.option(
    "-p",
    "--publications",
    type=click.Path(exists=True),
    default=None,
    help="Path to publications.json",
)
@click.option(
    "-c",
    "--config",
    type=click.Path(exists=True),
    default=None,
    help="Path to archive.yaml",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    default=None,
    help="Output content directory",
)
@click.option(
    "--clean",
    is_flag=True,
    help="Remove existing content before generating",
)
def main(
    publications: str | None,
    config: str | None,
    output: str | None,
    clean: bool,
) -> None:
    """Generate Hugo content from publications and config."""
    pub_path = Path(publications) if publications else get_static_data_dir() / "publications.json"
    config_path = Path(config) if config else get_archive_config_path()
    content_dir = Path(output) if output else get_content_dir()

    # Load data
    data = PublicationsData.load(pub_path)
    cfg = ArchiveConfig.load(config_path)

    log.info(f"Loaded {len(data.publications)} publications")
    log.info(f"Loaded config with {len(cfg.sections)} sections")

    # Generate
    generate_all(data.publications, cfg, content_dir, clean=clean)

    log.info(f"Content generated in {content_dir}")


if __name__ == "__main__":
    main()
