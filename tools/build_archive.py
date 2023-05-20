#!/usr/bin/env python3
import logging
import pickle
import re
from dataclasses import dataclass
from datetime import datetime
from multiprocessing import Manager, Pool, cpu_count
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import click
import pandas as pd
from pyzotero import zotero
from tqdm import tqdm
from transliterate import translit

logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")


@dataclass
class Config:
    api_key: str = "hTvqMYvC4Bjhm4xGHqyCTSWv"
    library_id: int = 4809962
    library_type: str = "user"
    jobs: int = cpu_count()
    cache: bool = False
    output_json: str = "publications.json"


@click.command()
@click.option("-j", "--jobs", type=int, default=cpu_count(), help="Number of jobs.")
@click.option("-c", "--cache", type=bool, is_flag=True, default=False, help="Use cache.")
def process_cli(**kwargs):
    cfg = Config(**kwargs)
    main(cfg)


class Item:
    def __init__(self, item: Dict) -> None:
        self.key = item["key"]
        self.type = item["itemType"]
        self.title = item.get("title", None)
        self.authors = [Item.name(author["firstName"], author["lastName"]) for author in item.get("creators", [])]
        self.language = Item.normalize_language(item.get("language", None))
        self.url = item.get("url", None)
        self.year, self.month, self.day = Item.date(item["date"])
        self.place = item.get("place", None)
        self.tags = {tag["tag"] for tag in item.get("tags", {})}

        self.review_type(item)

    @property
    def identifier(self):
        return Item.normalize(f"{self.year}-{self.title}-{self.type}")

    def to_dict(self):
        return {
            "id": self.identifier,
            "type": self.type,
            "year": self.year,
            "month": self.month,
            "day": self.day,
            "title": self.title,
            "authors": list(self.authors),
            "tags": list(self.tags),
            "url": self.url,
            "language": self.language,
        }
    
    def review_type(self, item: Dict):
        if "websiteType" in item:
            self.type = item["websiteType"].lower()

    def __repr__(self) -> str:
        return f"[{self.type}] {self.title} ({self.date})"

    @staticmethod
    def name(first: str, second: str) -> str:
        name = []
        if first:
            name.append(first)
        if second:
            name.append(second)
        return " ".join(name)
    
    @staticmethod
    def normalize_language(lang: Optional[str]) -> str:
        if lang is None:
            return None
        if 'ru' in lang.lower():
            return 'russian'
        else:
            return 'english'

    def normalize(text: str) -> str:
        text = text.lower()
        text = translit(text, "ru", reversed=True)
        text = text.replace("'", "")
        text = text.replace("c++", "cpp")
        text_list = []
        for e in text:
            text_list.append(e if e.isalnum() else "-")
        text = "".join(text_list)
        text = re.sub(r"(-)\1+", r"-", text)
        text = text.lstrip("-")
        text = text.rstrip("-")
        return text

    def date(date_str: str) -> Tuple[int, Optional[int], Optional[int]]:
        try:
            date = datetime.strptime(date_str, "%Y/%m/%d").date()
            return date.year, date.month, date.day
        except ValueError:
            pass

        try:
            date = datetime.strptime(date_str, "%Y/%m").date()
            return date.year, date.month, None
        except ValueError:
            pass

        try:
            date = datetime.strptime(date_str, "%Y").date()
            return date.year, None, None
        except ValueError:
            pass


class Cache:
    def __init__(self, filename: str = ".cache") -> None:
        self._filename = Path(filename)

    def exists(self):
        return self._filename.exists()

    def load(self) -> Optional[List[Dict]]:
        if not self.exists():
            return None

        with open(self._filename, "rb") as f:
            return pickle.load(f)

    def save(self, items: List[Dict]) -> List[Dict]:
        with open(self._filename, "wb") as f:
            pickle.dump(items, f)
        return items


def get_zotero_items(cfg: Config) -> List[Dict]:
    logging.info(f"Download data from zotero library `{cfg.library_id}`")
    zt = zotero.Zotero(cfg.library_id, cfg.library_type, cfg.api_key)
    zt.add_parameters(sort="date")
    return zt.everything(zt.publications())


def get_element_data(args):
    item, parameters = args
    key = item["data"]["key"]
    zt = parameters["zotero"]
    return zt.item(key)


def get_item_details(items: List[Dict], cfg: Config):
    zt = zotero.Zotero(cfg.library_id, cfg.library_type, cfg.api_key)
    with Manager() as manager:
        with Pool(cfg.jobs) as pool:
            parameters = manager.dict()
            parameters["zotero"] = zt
            data = [(item, parameters) for item in items]
            items = list(tqdm(pool.imap_unordered(get_element_data, data), total=len(data)))
    return items


def get_items(cfg: Config):
    items: List[Dict] = get_zotero_items(cfg)    
    items = get_item_details(items, cfg)
    return items


def parse_items(items: List[Dict], cfg: Config) -> List[Item]:
    result = []
    for item in items:
        data = item["data"]
        if data["itemType"] != "attachment":
            result.append(Item(data))
    return result


def items_to_dataframe(items: List[Item], cfg: Config) -> pd.DataFrame:
    list_of_dics = [i.to_dict() for i in items]
    df = pd.DataFrame(list_of_dics)
    df = df.astype({"year": "Int64", "month": "Int64", "day": "Int64"})
    return df


def export_json(filename: Path, items: List[Item], cfg: Config):
    df = items_to_dataframe(items, cfg)
    df.to_json(filename, force_ascii=False, orient="records", lines=False)


def export_csv(filename: Path, items: List[Item], cfg: Config):
    df = items_to_dataframe(items, cfg)
    df.to_csv(filename)


def main(cfg: Config):
    if cfg.cache:
        cache = Cache()
        items = cache.load() if cache.exists() else cache.save(get_items(cfg))
    else:
        items = get_items(cfg)

    items = parse_items(items, cfg)
    export_json(cfg.output_json, items, cfg)


if __name__ == "__main__":
    process_cli()
