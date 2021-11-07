import sys


def get_work_dir():
    return sys.argv[1] if len(sys.argv) > 1 else '.'


def get_template(path, filename='index.template.html'):
    with open(f'{path}/{filename}', 'r') as f:
        return f.read()
