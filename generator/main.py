import zotero as zot


def main():
    zotero = zot.Zotero(api_key='')

    for item in zotero.get_items():
        print(item.title, item.date)
        print(item.tag)


if __name__ == '__main__':
    main()
