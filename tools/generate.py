#!/usr/bin/env python3
"""Generate Hugo content from publications.json + archive.yaml."""

import logging
import re
import tomllib
from datetime import date
from pathlib import Path
from typing import Any

import click
import yaml

from models import (
    RESEARCH_TYPES,
    ArchiveConfig,
    Contacts,
    Course,
    Publication,
    PublicationsData,
    Section,
    get_archive_config_path,
    get_content_dir,
    get_static_data_dir,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

DEFAULT_DATE = date(1990, 3, 25)
# (year, date sort key, frontmatter item) — input to year_groups()
type YearEntry = tuple[int, tuple[int, int, int], dict]
SHORTCODE = re.compile(r"\{\{<(.*?)>\}\}", re.DOTALL)


def strip_shortcodes(text: str) -> str:
    """Replace Hugo shortcodes like {{< logo "k" "Label" >}} with their label.

    Treats the last quoted argument as the human-readable label. Used to
    sanitize bio text destined for plain-text outputs (llms.txt, ai.txt).
    """
    return SHORTCODE.sub(lambda m: shortcode_label(m.group(1)), text)


def shortcode_label(args: str) -> str:
    """Return the last quoted argument of a shortcode, or '' if none."""
    parts = args.split('"')
    return parts[-2] if len(parts) >= 3 else ""


def quote_block(text: str) -> str:
    """Prefix every line with '> ' for a markdown blockquote."""
    return "\n".join(f"> {line}" if line else ">" for line in text.splitlines())


def latest_pub_date(publications: list[Publication]) -> date:
    """Return date of the most recent publication."""
    if not publications:
        return DEFAULT_DATE
    return max(p.pub_date for p in publications)


def taxonomy_tags(config: ArchiveConfig) -> dict[str, str]:
    """Map casefolded group tag -> canonical spelling. The curated taxonomy."""
    return {config.normalize(t).casefold(): config.normalize(t) for g in config.groups for t in g.tags}


def curate_tags(tags: list[str], config: ArchiveConfig) -> list[str]:
    """Keep only tags in the curated taxonomy, deduped case-insensitively.

    Drops raw Zotero keyword noise (e.g. 'Casimir force', 'Drude model'),
    keeping curated group tags and collapsing case variants (casimir / Casimir).
    """
    taxonomy = taxonomy_tags(config)
    seen: set[str] = set()
    result: list[str] = []
    for t in config.normalize_list(tags):
        key = t.casefold()
        canonical = taxonomy.get(key)
        if canonical and key not in seen:
            seen.add(key)
            result.append(canonical)
    return result


def pub_to_item(pub: Publication, config: ArchiveConfig) -> dict:
    """Convert publication to item dict for frontmatter."""
    authors = [config.normalize(str(a)) for a in pub.authors if str(a)]
    tags = curate_tags(pub.tags, config)
    item = {
        "title": pub.title,
        "url": pub.url or "",
        "authors": authors,
        "tags": tags,
    }
    if pub.license:
        item["license"] = pub.license
    if pub.pdf:
        item["pdf"] = pub.pdf
    if pub.artifacts:
        item["artifacts"] = [{"kind": a.kind, "url": a.url} for a in pub.artifacts]
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
    card: dict = {
        "title": config.normalize(course.name),
        "slug": course.slug,
        "year": course.year,
        "lectures_count": len(course.lectures),
        "lectures": [lecture_to_item(lec) for lec in course.lectures],
    }
    return with_description(card, course, config)


def with_description(data: dict, course: Course, config: ArchiveConfig) -> dict:
    """Return data with the course description appended, if configured."""
    description = config.course_description(course.slug)
    return {**data, "description": description} if description else data


def group_pubs_by_year(
    publications: list[Publication],
    config: ArchiveConfig,
) -> list[dict]:
    """Group publications by year, return list of year groups."""
    return year_groups([pub_entry(p, config) for p in publications])


def group_by_year(
    publications: list[Publication],
    courses: list[Course],
    config: ArchiveConfig,
) -> list[dict]:
    """Group publications and courses by year, return list of year groups."""
    pub_entries = [pub_entry(p, config) for p in publications]
    course_entries = [course_entry(c, config) for c in courses]
    return year_groups(pub_entries + course_entries)


def pub_entry(pub: Publication, config: ArchiveConfig) -> YearEntry:
    """Return (year, sort key, item) for a publication."""
    return (pub.year, pub.date_sort_key, pub_to_item(pub, config))


def course_entry(course: Course, config: ArchiveConfig) -> YearEntry:
    """Return (year, sort key, item) for a course."""
    return (course.year, course.latest_date, course_to_item(course, config))


def year_groups(entries: list[YearEntry]) -> list[dict]:
    """Bucket items by year (newest first), each sorted by date descending.

    Sorting is stable, so items with equal dates keep their input order.
    """
    by_year: dict[int, list[YearEntry]] = {}
    for entry in entries:
        by_year.setdefault(entry[0], []).append(entry)
    groups = []
    for year in sorted(by_year, reverse=True):
        newest = sorted(by_year[year], key=lambda e: e[1], reverse=True)
        groups.append({"year": year, "items": [item for *_, item in newest]})
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

    if has_course is not None:
        result = [p for p in result if p.is_lecture == has_course]

    return result


def compute_courses(
    publications: list[Publication],
    config: ArchiveConfig,
) -> list[Course]:
    """Group lectures (Publication.is_lecture) into courses by (course, school)."""
    groups: dict[tuple[str, str], list[Publication]] = {}
    for lec in (p for p in publications if p.is_lecture):
        groups.setdefault(course_key(lec, config), []).append(lec)

    courses = [Course.from_lectures(*key, lecs) for key, lecs in groups.items()]
    return sorted(courses, key=lambda c: (-c.year, c.name))


def course_key(lecture: Publication, config: ArchiveConfig) -> tuple[str, str]:
    """Return the normalized (course, school) pair a lecture belongs to."""
    school = config.normalize(lecture.school) if lecture.school else ""
    return (config.normalize(lecture.course), school)


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


def group_items(
    standalone_pubs: list[Publication],
    courses: list[Course],
    config: ArchiveConfig,
) -> list[dict]:
    """Group standalone publications and courses by tags, plus 'Other'."""
    tag_sets = [{config.normalize(t) for t in g.tags} for g in config.groups]
    pub_buckets = bucket_by_tags(
        [(p.id, set(config.normalize_list(p.tags)), p) for p in standalone_pubs],
        tag_sets,
    )
    course_buckets = bucket_by_tags(
        [(c.slug, {config.normalize(t) for t in c.tags}, c) for c in courses],
        tag_sets,
    )
    names = [g.name for g in config.groups] + ["Other"]
    rows = zip(names, pub_buckets, course_buckets, strict=True)
    return [
        {"name": name, "items": group_by_year(pubs, group_courses, config)}
        for name, pubs, group_courses in rows
        if pubs or group_courses
    ]


def bucket_by_tags[T](
    entries: list[tuple[str, set[str], T]],
    tag_sets: list[set[str]],
) -> list[list[T]]:
    """Assign each (key, tags, item) to the first tag set its tags intersect.

    Returns one bucket per tag set plus a trailing bucket of unmatched items.
    A key is claimed once: later entries with an already claimed key are dropped.
    """
    claimed: set[str] = set()
    buckets: list[list[T]] = []
    for group_tags in tag_sets:
        bucket: list[T] = []
        for key, tags, item in entries:
            if key in claimed or not tags & group_tags:
                continue
            claimed.add(key)
            bucket.append(item)
        buckets.append(bucket)
    buckets.append([item for key, _, item in entries if key not in claimed])
    return buckets


def generate_index(
    content_dir: Path,
    publications: list[Publication],
    courses: list[Course],
    config: ArchiveConfig,
) -> None:
    """Generate main index page with groups, stats, and nav."""
    standalone = filter_publications(publications, config, has_course=False)
    groups_data = group_items(standalone, courses, config)
    nav_items = [{"path": s.path, "label": s.label} for s in config.sections]

    data = {
        "title": "Publications",
        "layout": "index",
        "date": latest_pub_date(publications),
        "stats": compute_stats(publications, courses),
        "nav": nav_items,
        "groups": groups_data,
    }
    write_frontmatter(content_dir / "_index.md", data)

    counts = ", ".join(f"{g['name']}: {sum(len(y['items']) for y in g['items'])}" for g in groups_data)
    log.info(f"Generated _index.md ({counts})")


def generate_section(
    content_dir: Path,
    section: Section,
    publications: list[Publication],
    config: ArchiveConfig,
) -> None:
    """Generate a section index page with grouped publications."""
    clean_path = section.path.strip("/")
    if not clean_path:
        return

    data = {
        "title": section.label,
        "type": "publications",
        "date": latest_pub_date(publications),
        "publications_count": len(publications),
        "items": group_pubs_by_year(publications, config),
    }

    write_frontmatter(content_dir / clean_path / "_index.md", data)
    log.info(f"Generated {clean_path}/_index.md ({len(publications)} publications)")


def generate_course_page(
    teaching_dir: Path,
    course: Course,
    config: ArchiveConfig,
) -> None:
    """Generate individual course page."""
    course_data: dict = {
        "title": config.normalize(course.name),
        "type": "course",
        "layout": "course/single",
        "date": latest_pub_date(course.lectures),
        "slug": course.slug,
        "school": course.school,
        "year": course.year,
        "lectures_count": len(course.lectures),
        "lectures": [sectioned_lecture_item(lec, config) for lec in course.lectures],
    }
    page_data = with_description(course_data, course, config)
    write_frontmatter(teaching_dir / f"{course.slug}.md", page_data)


def sectioned_lecture_item(lec: Publication, config: ArchiveConfig) -> dict:
    """Convert lecture to item dict tagged with its normalized course section."""
    section = config.normalize(lec.section) if lec.section else ""
    return {**lecture_to_item(lec), "section": section}


def generate_teaching(
    content_dir: Path,
    courses: list[Course],
    config: ArchiveConfig,
) -> None:
    """Generate teaching section with course pages."""
    teaching_dir = content_dir / "teaching"
    all_lectures = [lec for c in courses for lec in c.lectures]
    data = {
        "title": "Teaching",
        "layout": "teaching/list",
        "date": latest_pub_date(all_lectures),
        "courses_count": len(courses),
        "schools": group_by_school(courses, config),
    }
    write_frontmatter(teaching_dir / "_index.md", data)
    log.info(f"Generated teaching/_index.md ({len(courses)} courses)")

    # Individual course pages
    for course in courses:
        generate_course_page(teaching_dir, course, config)

    log.info(f"Generated {len(courses)} course pages")


def group_by_school(courses: list[Course], config: ArchiveConfig) -> list[dict]:
    """Group course cards by school; schools and courses newest first."""
    by_school: dict[str, list[Course]] = {}
    for course in courses:
        by_school.setdefault(course.school, []).append(course)

    def cards(group: list[Course]) -> list[dict]:
        newest = sorted(group, key=lambda c: c.latest_date, reverse=True)
        return [course_to_card(c, config) for c in newest]

    schools = sorted(
        by_school.items(),
        key=lambda kv: max(c.latest_date for c in kv[1]),
        reverse=True,
    )
    return [{"name": school, "courses": cards(group)} for school, group in schools]


# SiteConfig fields passed to the about page for the Person JSON-LD
PERSON_FIELDS = {"works_for", "affiliations", "knows_about"}


def generate_about(content_dir: Path, config: ArchiveConfig) -> None:
    """Generate about page with contacts."""
    about_path = content_dir / "about" / "_index.md"

    contacts = {}
    if config.site.contacts:
        contacts = config.site.contacts.model_dump(exclude_none=True)

    data: dict[str, Any] = {
        "title": "About",
        "type": "about",
        "contacts": contacts,
    }
    if config.site.job_title:
        data["job_title"] = config.site.job_title
    person = config.site.model_dump(include=PERSON_FIELDS, exclude_none=True)
    data.update({key: value for key, value in person.items() if value})
    bio = config.site.bio or ""
    write_frontmatter(about_path, data, content=bio)
    log.info("Generated about/_index.md")


def format_contacts(contacts: Contacts | None) -> list[str]:
    """Format contacts as markdown links."""
    if not contacts:
        return []
    lines: list[str] = []
    urls = {
        "github": "https://github.com/{}",
        "scholar": "https://scholar.google.com/citations?user={}",
        "linkedin": "https://linkedin.com/in/{}",
        "twitter": "https://x.com/{}",
    }
    for field, template in urls.items():
        value = getattr(contacts, field, None)
        if value:
            lines.append(f"- [{field.title()}]({template.format(value)})")
    if contacts.email:
        lines.append(f"- Email: {contacts.email}")
    return lines


def build_llms_txt(
    publications: list[Publication],
    courses: list[Course],
    config: ArchiveConfig,
    base_url: str,
) -> str:
    """Build llms.txt content for LLM crawlers."""
    contact_lines = format_contacts(config.site.contacts)
    lines = [
        *llms_header(config, compute_stats(publications, courses)),
        *md_section("Pages", llms_pages(config, base_url)),
        *md_section("Data", llms_data(base_url)),
        *md_section("Research papers", llms_research(publications)),
        *md_section("Courses", llms_courses(courses, base_url)),
        *(md_section("Contacts", contact_lines) if contact_lines else []),
        "",
    ]
    return "\n".join(lines)


def md_section(heading: str, lines: list[str]) -> list[str]:
    """Return a '## heading' markdown section, preceded by a blank line."""
    return ["", f"## {heading}", "", *lines]


def llms_header(config: ArchiveConfig, stats: dict) -> list[str]:
    """Return the llms.txt title and bio/stats blockquote."""
    bio = strip_shortcodes(config.site.bio or "")
    return [
        f"# {config.site.author} — Archive",
        "",
        quote_block(bio),
        f"> {stats['papers']} papers, {stats['courses']} courses, {stats['year_start']}–{stats['year_end']}.",
    ]


def llms_pages(config: ArchiveConfig, base_url: str) -> list[str]:
    """Return links to site sections and the about page."""
    sections = [f"- [{s.label}]({base_url + s.path})" for s in config.sections]
    return [*sections, f"- [About]({base_url}/about/)"]


def llms_data(base_url: str) -> list[str]:
    """Return links to machine-readable site data."""
    return [
        f"- [publications.json]({base_url}/data/publications.json): "
        "Machine-readable catalog of all publications (JSON)",
        f"- [RSS feed]({base_url}/index.xml)",
        f"- [Sitemap]({base_url}/sitemap.xml)",
    ]


def llms_research(publications: list[Publication]) -> list[str]:
    """Return research papers (no lectures), newest first."""
    research = sorted(
        [p for p in publications if not p.is_lecture and p.pub_type in RESEARCH_TYPES],
        key=lambda p: p.date_sort_key,
        reverse=True,
    )
    lines = []
    for pub in research:
        authors = ", ".join(str(a) for a in pub.authors if str(a))
        lines.append(f"- [{pub.title}]({pub.url or '#'}): {authors} ({pub.year})")
    return lines


def llms_courses(courses: list[Course], base_url: str) -> list[str]:
    """Return course page links with school, year and lecture count."""
    lines = []
    for course in courses:
        url = f"{base_url}/teaching/{course.slug}/"
        details = f"{course.school}, {course.year}, {len(course.lectures)} lectures"
        lines.append(f"- [{course.name}]({url}): {details}")
    return lines


def read_base_url(site_dir: Path) -> str:
    """Read baseURL from hugo.toml, stripping trailing slash."""
    with (site_dir / "hugo.toml").open("rb") as f:
        data = tomllib.load(f)
    return data["baseURL"].rstrip("/")


def generate_all(
    publications: list[Publication],
    config: ArchiveConfig,
    content_dir: Path,
) -> None:
    """Generate all content files."""
    content_dir.mkdir(parents=True, exist_ok=True)
    courses = compute_courses(publications, config)

    generate_index(content_dir, publications, courses, config)
    generate_sections(content_dir, publications, courses, config)
    generate_about(content_dir, config)  # not in nav
    write_llms_txt(content_dir.parent, publications, courses, config)


def generate_sections(
    content_dir: Path,
    publications: list[Publication],
    courses: list[Course],
    config: ArchiveConfig,
) -> None:
    """Generate every non-root section; the course section becomes Teaching."""
    for section in config.sections:
        if section.path == "/":
            continue
        if section.filter and section.filter.has_course:
            generate_teaching(content_dir, courses, config)
            continue
        section_pubs = section_publications(section, publications, config)
        generate_section(content_dir, section, section_pubs, config)


def section_publications(
    section: Section,
    publications: list[Publication],
    config: ArchiveConfig,
) -> list[Publication]:
    """Apply the section's filter (if any) to publications."""
    if not section.filter:
        return publications
    return filter_publications(
        publications,
        config,
        tag=section.filter.tag,
        has_course=section.filter.has_course,
    )


def write_llms_txt(
    site_dir: Path,
    publications: list[Publication],
    courses: list[Course],
    config: ArchiveConfig,
) -> None:
    """Write llms.txt and its ai.txt copy into the site's static dir."""
    base_url = read_base_url(site_dir)
    llms_content = build_llms_txt(publications, courses, config, base_url)
    for name in ("llms.txt", "ai.txt"):
        (site_dir / "static" / name).write_text(llms_content)
    log.info("Generated llms.txt, ai.txt")


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
def main(
    publications: str | None,
    config: str | None,
    output: str | None,
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
    generate_all(data.publications, cfg, content_dir)

    log.info(f"Content generated in {content_dir}")


if __name__ == "__main__":
    main()
