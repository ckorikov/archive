import logging

import environment as env
from index import Index
from zotero import Zotero


def main():
    logging.info('Started static content generator')

    work_dir = env.get_work_dir()
    logging.info(f'Set work directory `{work_dir}`')

    zotero = Zotero(api_key='hTvqMYvC4Bjhm4xGHqyCTSWv', debug=True)
    logging.info('Connected to Zotero')

    logging.info('Started index page generation')

    index = Index(work_dir)
    index.fill(zotero)
    index.save()


if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s',
                        encoding='utf-8',
                        level=logging.INFO)
    try:
        main()
    except Exception as e:
        logging.error(f'Error occurred {e}')
        raise
    finally:
        logging.info('Finished')
