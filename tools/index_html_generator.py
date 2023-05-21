#!/usr/bin/env python3
import logging
from dataclasses import dataclass
from io import TextIOWrapper
from string import Template
from typing import List, Set
from bs4 import BeautifulSoup

import click
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")


@dataclass
class Config:
    template_file: TextIOWrapper
    publications_file: TextIOWrapper
    output_file: str


@click.command()
@click.option("-t", "--template-file", type=click.File(), default="index.template", help="Template file.")
@click.option("-p", "--publications-file", type=click.File(), required=True, help="Publications JSON file.")
@click.option("-o", "--output-file", type=click.Path(), default="index.html", help="Output HTML file.")
def process_cli(**kwargs):
    cfg = Config(**kwargs)
    main(cfg)


def gen_icon(item_type: str) -> str:
    type_to_icon_dict = {
        "blogPost": "fas fa-globe",
        "habr": "fas fa-heading",
        "webpage": "fas fa-globe",
        "github": "fab fa-github",
        "miro": "fas fa-object-group",
        "colab": "fab fa-google",
        "telegraph": "fa-brands fa-telegram",
        "presentation": "fas fa-chalkboard-teacher",
        "conferencePaper": "fas fa-file-alt",
        "journalArticle": "fas fa-file-alt",
        "magazineArticle": "fas fa-book-open",
        "thesis": "fas fa-user-graduate",
        "videoRecording": "fas fa-video",
        "book": "fas fa-book",
        "group": "fas fa-layer-group",
    }
    icon_str = type_to_icon_dict.get(item_type, "fas fa-file-alt")
    return f'<span class="icon"><i class="{icon_str}"></i></span>'


def gen_year(year: int):
    return f'<div class="meta"><span>{year}</span></div>'


def gen_title(title: str, url: str):
    return f'<a href="{url}" target="_blank">{title}</a></td>'


def gen_main_block(year: int, item_type: str, title: str, url: str):
    year_str = gen_year(year)
    icon_str = gen_icon(item_type)
    title_str = gen_title(title, url)
    return f"<td>{year_str} {icon_str} {title_str}</td>"


def gen_tags_block(tags: List[str]):
    tag_list = []
    for tag in tags:
        tag_list.append(f'<a href="javascript:void(0);" class="tag">{tag}</a>')
    tag_list_str = " ".join(tag_list)
    return f"<td>{tag_list_str}</td>"


def gen_qr_code(item_id: str):
    return f'<td><a href="javascript:void(0);" class="qr"><i class="fa fa-qrcode"></i></a></td>'


def gen_item(item_id: str, year: int, item_type: str, title: str, url: str, tags: List[str]):
    main_str = gen_main_block(year, item_type, title, url)
    tags_str = gen_tags_block(tags)
    qrcode_str = gen_qr_code(item_id)
    return f'<tr id="{item_id}" class="publication">{main_str} {tags_str} {qrcode_str}</tr>'


def gen_group_title(year: int, title: str):
    year_str = gen_year(year)
    icon_str = gen_icon("group")
    return f'<tr><td colspan="3">{year_str} {icon_str} {title}</td></tr>'


def split_dataframe(publications_dataframe):
    no_group_df = publications_dataframe[publications_dataframe["group"].isnull()]
    grouped_df = publications_dataframe[publications_dataframe["group"].notnull()]
    groups = grouped_df.groupby(["year", "group"])

    for group_name, group_df in groups:
        if len(group_df) > 1:
            min_year = group_df["year"].min()
            placeholder_row = pd.Series({"group": group_name, "title": group_name[1], "year": min_year})
            no_group_df = pd.concat([no_group_df, placeholder_row.to_frame().T])
        else:
            no_group_df = pd.concat([no_group_df, group_df])

    no_group_df = no_group_df.sort_values(by=["year", "month", "day", "title"], ascending=False)

    return no_group_df, groups


class TBodyContainer:
    def __init__(self, list_of_seen_items) -> None:
        self.list_of_seen_items = list_of_seen_items
        self.tbody_str_list = []
        self.elements = []
        self.curr_group = None

    def add(self, row):
        item_str = gen_item_if_not_seen(row, self.list_of_seen_items)
        if item_str:
            self.elements.append(item_str)

    def start_group(self, group):
        self.stop_group()
        self.curr_group = group
        title_str = gen_group_title(group["year"], group["title"])
        self.elements.append(title_str)

    def stop_group(self):
        if self.elements:
            if self.curr_group is not None:
                groups_str = '<tbody class="group">' + "\n".join(self.elements) + "</tbody>"
            else:
                groups_str = "<tbody>" + "\n".join(self.elements) + "</tbody>"
            self.tbody_str_list.append(groups_str)
            self.elements = []
        self.curr_group = None

    def __repr__(self) -> str:
        self.stop_group()
        return "\n".join(self.tbody_str_list)


def gen_list_of_items_grouped(publications_dataframe, list_of_seen_items: Set[str]) -> str:
    df, groups = split_dataframe(publications_dataframe)

    table_body = TBodyContainer(list_of_seen_items)
    for _, row in df.iterrows():
        if row["group"] in groups.groups:
            group_df = groups.get_group(row["group"])
            group_df = group_df.sort_values(by=["year", "month", "day", "title"], ascending=False)
            table_body.start_group(row)
            for _, group_row in group_df.iterrows():
                table_body.add(group_row)
            table_body.stop_group()
        else:
            table_body.add(row)

    return str(table_body)


def gen_item_if_not_seen(row, list_of_seen_items) -> str:
    if row["id"] not in list_of_seen_items:
        item_str = gen_item(
            item_id=row["id"],
            year=row["year"],
            item_type=row["type"],
            title=row["title"],
            url=row["url"],
            tags=row["tags"],
        )
        list_of_seen_items.add(row["id"])
        return item_str


def gen_list_of_items(publications_dataframe, list_of_seen_items: Set[str]) -> str:
    publications_dataframe = publications_dataframe.sort_values(by=["year", "month", "day", "title"], ascending=False)
    list_of_items = []
    for _, row in publications_dataframe.iterrows():
        item_str = gen_item_if_not_seen(row, list_of_seen_items)
        if item_str:
            list_of_items.append(item_str)
    return "<tbody>" + "\n".join(list_of_items) + "</tbody>"


def gen_table(name: str, tags: List[str], publications_dataframe, list_of_seen_items: Set[str]):
    if tags:
        mask = publications_dataframe["tags"].apply(lambda x: any(tag in x for tag in tags))
        subset_publications_dataframe = publications_dataframe[mask]
        list_of_item_str = gen_list_of_items_grouped(subset_publications_dataframe, list_of_seen_items)
    else:
        list_of_item_str = gen_list_of_items_grouped(publications_dataframe, list_of_seen_items)
    return f'<table> <thead><tr><th colspan="3">{name}</th></tr></thead>{list_of_item_str}</table>'


def gen_tables(publications_dataframe):
    list_of_tables = []
    list_of_seen_items = set()
    list_of_tables.append(gen_table("research", ["phd", "master", "casimir", "conference", "intel"], publications_dataframe, list_of_seen_items))
    list_of_tables.append(gen_table("teaching", ["polytech", "jiangsu"], publications_dataframe, list_of_seen_items))
    list_of_tables.append(gen_table("popsience", ["popscience"], publications_dataframe, list_of_seen_items))
    list_of_tables.append(gen_table("fun", ["fun", "wolfram", "hackathon", "winenot", "bar", "huawei"], publications_dataframe, list_of_seen_items))
    if len(list_of_seen_items) < len(publications_dataframe.index):
        list_of_tables.append(gen_table("other", [], publications_dataframe, list_of_seen_items))
    return "\n".join(list_of_tables)


def main(cfg: Config):
    publications_dataframe = pd.read_json(cfg.publications_file)
    table_str = gen_tables(publications_dataframe)

    template = Template(cfg.template_file.read())
    html_str = template.substitute({"content": table_str})

    soup = BeautifulSoup(html_str, 'html.parser')
    html_str = soup.prettify()
    
    with open(cfg.output_file, "w") as f:
        f.write(html_str)


if __name__ == "__main__":
    process_cli()
