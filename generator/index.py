import logging
from string import Template
from typing import Optional

import environment as env
from slides import Slides


class Index:
    def __init__(self, work_dir, filename='index.template.html'):
        self.work_dir = work_dir
        self.content = ''

        template_path = env.get_template(work_dir, filename)

        if not template_path:
            raise ValueError(f'Cannot find template `{filename}` in `{work_dir}`')

        self.template = Template(template_path)

    def __generate_items(self, zotero, tags_filter: Optional[set] = None):
        text = ''
        dictionary = []
        for item in zotero.get_items_filtered(item_tags_any=tags_filter, with_attachments=False):
            logging.info(f'Processing `{item.title}`')
            text += Index.format_element(title=item.title,
                                         year=item.year,
                                         identifier=item.identifier,
                                         tags=item.tags)
            if item.kind == 'presentation':
                slides = Slides(item, self.work_dir)
                slides.generate()
                break
            dictionary.append(item.to_dict())
        return text, dictionary

    def fill(self, zotero):
        items, dictionary = self.__generate_items(zotero)
        content = Index.format_list(name='all', content=items)
        self.content = self.template.safe_substitute(content=content, data=dictionary)

    def save(self):
        with open(f'{self.work_dir}/index.html', 'w') as f:
            return f.write(self.content)

    @staticmethod
    def format_list(name, content):
        return f'<div class="column column-60 work-list" id="{name}-list">' \
               f'<table><tbody> {content} </tbody> </table> </div>'

    @staticmethod
    def format_element(title, year, identifier, tags, icon='fas fa-globe'):
        tags_string = "".join([f'<a href="javascript:void(0)" class="tag">{tag}</a>' for tag in tags])
        return f'<tr id="id-{identifier}" class="list-element">' \
               f'<td>' \
               f'<div class="meta"><span>{year}</span></div>' \
               f'<span class="icon"><i class="{icon}"></i></span>' \
               f'<a href="{identifier}.html">{title}</a>' \
               f'</td>' \
               f'<td>' \
               f'{tags_string}' \
               f'</td>' \
               f'</tr>'
