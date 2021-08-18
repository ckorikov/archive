from pyzotero import zotero

_LIBRARY_ID = 4809962
_LIBRARY_TYPE = 'user'


class Zotero:
    def __init__(self, api_key):
        self.__handle = zotero.Zotero(_LIBRARY_ID, _LIBRARY_TYPE, api_key)
        self.__items = None

    def __fetch(self):
        if not self.__items:
            self.__items = self.__handle.publications()
            self.__items = [item['data'] for item in self.__items]

    def get_items(self):
        self.__fetch()
        return self.__items

    def get_items_type(self, item_type):
        self.__fetch()
        return [item for item in self.__items if item['itemType'] == item_type]

    def get_presentations(self):
        return self.get_items_type(item_type='presentation')
