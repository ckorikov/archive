import logging
import pickle
from os.path import exists
from typing import Optional

import requests
from pyzotero import zotero

_LIBRARY_ID = 4809962
_LIBRARY_TYPE = 'user'


def transliterate(text):
    """
    https://gist.github.com/ledovsky/6398962
    """
    slovar = {'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
              'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'i', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n',
              'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'h',
              'ц': 'c', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch', 'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e',
              'ю': 'u', 'я': 'ya', 'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Е': 'E', 'Ё': 'YO',
              'Ж': 'ZH', 'З': 'Z', 'И': 'I', 'Й': 'I', 'К': 'K', 'Л': 'L', 'М': 'M', 'Н': 'N',
              'О': 'O', 'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T', 'У': 'U', 'Ф': 'F', 'Х': 'H',
              'Ц': 'C', 'Ч': 'CH', 'Ш': 'SH', 'Щ': 'SCH', 'Ъ': '', 'Ы': 'y', 'Ь': '', 'Э': 'E',
              'Ю': 'U', 'Я': 'YA', ',': '', '?': '', ' ': '_', '~': '', '!': '', '@': '', '#': '',
              '$': '', '%': '', '^': '', '&': '', '*': '', '(': '', ')': '', '-': '', '=': '', '+': '',
              ':': '', ';': '', '<': '', '>': '', '\'': '', '"': '', '\\': '', '/': '', '№': '',
              '[': '', ']': '', '{': '', '}': '', 'ґ': '', 'ї': '', 'є': '', 'Ґ': 'g', 'Ї': 'i',
              'Є': 'e', '—': ''}
    for key in slovar:
        text = text.replace(key, slovar[key])
    return text


def process(text):
    text = text.lower()
    text = transliterate(text)
    text = text.replace('_', '-')
    return text


class Item:
    def __init__(self, data):
        self.data = data
        self.__file = None

    def __fetch(self):
        if not self.__file:
            url = self.data['url']
            self.__file = requests.get(url)

    @property
    def title(self):
        if 'title' in self.data:
            return self.data['title']

    @property
    def language(self):
        if 'language' in self.data:
            return self.data['language']

    @property
    def date(self):
        if 'date' in self.data:
            return self.data['date']

    @property
    def year(self):
        date = self.date
        if date and '/' in date:
            return date.split('/')[0]
        return date

    @property
    def creators(self):
        return [" ".join((author['firstName'], author['lastName'])) for author in self.data['creators']]

    @property
    def tags(self):
        return {tag_item['tag'] for tag_item in self.data['tags']}

    @property
    def identifier(self):
        date = self.year
        title = self.title
        title = process(title)
        return f'{date}-{title}'

    @property
    def file(self):
        self.__fetch()
        if self.__file:
            return self.__file.content

    def __repr__(self):
        return str(self.data)


class Zotero:
    def __init__(self, api_key, debug=False):
        self.__debug_mode = debug
        self.__handle = zotero.Zotero(_LIBRARY_ID, _LIBRARY_TYPE, api_key)
        self.__items = None

    def __get_debug_data(self, debug_file='debug.data'):
        if self.__debug_mode and exists(debug_file):
            with open(debug_file, 'rb') as f:
                self.__items = pickle.load(f)
        else:
            self.__fetch()
            with open(debug_file, 'wb') as f:
                pickle.dump(self.__items, f)

    def __try_fetch(self):
        if self.__debug_mode:
            self.__get_debug_data()
        else:
            self.__fetch()

    def __fetch(self):
        if not self.__items:
            self.__handle.add_parameters(sort='date')
            self.__items = self.__handle.publications()
            self.__items = [self.__handle.item(item['data']['key']) for item in self.__items]
            self.__items = [Item(item['data']) for item in self.__items]

    def get_items(self):
        self.__try_fetch()
        return self.__items

    def get_items_filtered(self,
                           item_types_any: Optional[set] = None,
                           item_tags_any: Optional[set] = None,
                           with_attachments=True):
        if item_types_any is None:
            item_types_any = {}

        if item_tags_any is None:
            item_tags_any = {}

        logging.info(
            f'Get Zotero items filtered by type={item_types_any}, '
            f'tags={item_tags_any} with attachments={with_attachments}')

        self.__try_fetch()

        def predicate(cond_type: str, cond_tags: set):
            if not with_attachments and cond_type == 'attachment':
                return False
            if item_tags_any and cond_tags.isdisjoint(item_tags_any):
                return False
            if item_types_any and cond_type not in item_types_any:
                return False
            return True

        return [item for item in self.__items if predicate(item.data['itemType'], item.tags)]

    def get_presentations(self, tags=None):
        return self.get_items_filtered(item_types_any={'presentation'}, item_tags_any=tags, with_attachments=False)
