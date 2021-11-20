import os
import sys


def get_output_dir():
    return os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.getcwd()


def get_root_dir():
    return os.path.abspath(os.path.dirname(__file__))


def get_template(path, filename='index.template.html'):
    with open(f'{path}/{filename}', 'r') as f:
        return f.read()
