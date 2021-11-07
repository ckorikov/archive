import logging
from string import Template

import environment as env


class Index:
    def __init__(self, work_dir, filename='index.template.html'):
        self.work_dir = work_dir
        self.content = ''

        template_path = env.get_template(work_dir, filename)

        if not template_path:
            raise ValueError(f'Cannot find template `{filename}` in `{work_dir}`')

        self.template = Template(template_path)

    def fill(self, zotero):
        for item in zotero.get_items():
            logging.info(f'Processing `{item.title}`')
            self.content += Index.format_element(title=item.title, year=item.year, tag=item.tag)

        self.content = self.template.safe_substitute(content=self.content)

    def save(self):
        with open(f'{self.work_dir}/index.html', 'w') as f:
            return f.write(self.content)

    @staticmethod
    def format_element(title, year, tag, icon='fas fa-globe'):
        return f'<tr id="{tag}"><td>' \
               f'<div class="meta"><span>{year}</span></div>' \
               f'<span class="icon"><i class="{icon}"></i></span>' \
               f'<a href="#">{title}</a>' \
               f'</td></tr>'
