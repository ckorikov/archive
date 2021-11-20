import logging

import environment as env
from index import Index
from zotero import Zotero


def prepare_directories():
    output_dir = env.get_output_dir()
    logging.info(f'Output directory `{output_dir}`')
    root_dir = env.get_root_dir()
    logging.info(f'Root directory `{root_dir}`')

    assert output_dir != root_dir, 'Run generator in the source directory is prohibited'

    return output_dir, root_dir


def main():
    logging.info('Started static content generator')
    output_dir, root_dir = prepare_directories()

    zotero = Zotero(api_key='hTvqMYvC4Bjhm4xGHqyCTSWv', debug=True)

    logging.info('Started index page generation')
    index = Index(output_dir)
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
