import logging
from string import Template

import environment as env


class Index:
    def __init__(self, topics: dict, work_dir, filename='index.template.html'):
        self.topics: dict = topics
        self.work_dir = work_dir
        self.content = ''

        template_path = env.get_template(work_dir, filename)

        if not template_path:
            raise ValueError(f'Cannot find template `{filename}` in `{work_dir}`')

        self.template = Template(template_path)

    def __generate_controllers(self):
        text = ''
        for topic, tags in self.topics.items():
            logging.info(f'Generate topic `{topic}`')
            text += f' <a id="{topic}" class="topic-controller" href="#">#{topic}</a>'
        return text

    def __generate_items(self, zotero, tags_filter: set):
        text = ''
        for item in zotero.get_items_filtered(item_tags_any=tags_filter, with_attachments=False):
            logging.info(f'Processing `{item.title}`')
            text += Index.format_element(title=item.title,
                                         year=item.year,
                                         identifier=item.identifier,
                                         tags=item.tags)
        return text

    def __generate_lists(self, zotero):
        text = ''
        hidden = False
        for topic, tags in self.topics.items():
            logging.info(f'Generate list for `{topic}`')
            data = self.__generate_items(zotero, tags)
            text += Index.format_list(name=topic, content=data, hidden=hidden)
            if not hidden:
                hidden = True
        return text

    def fill(self, zotero):
        controllers_text = self.__generate_controllers()
        items_text = self.__generate_lists(zotero)
        self.content = self.template.safe_substitute(controllers=controllers_text,
                                                     content=items_text
                                                     )

    def save(self):
        with open(f'{self.work_dir}/index.html', 'w') as f:
            return f.write(self.content)

    @staticmethod
    def format_list(name, content, hidden=True):
        flag_string = 'display: None' if hidden else ''
        return f'<div class="column column-60 work-list" id="{name}-list" style="{flag_string}">' \
               f'<table><tbody> {content} </tbody> </table> </div>'

    @staticmethod
    def format_element(title, year, identifier, tags, icon='fas fa-globe'):
        tags_string = "".join([f'<a href="#" class="tag">{tag}</a>' for tag in tags])
        return f'<tr id="{identifier}">' \
               f'<td>' \
               f'<div class="meta"><span>{year}</span></div>' \
               f'<span class="icon"><i class="{icon}"></i></span>' \
               f'<a href="#">{title}</a>' \
               f'</td>' \
               f'<td>' \
               f'{tags_string}' \
               f'</td>' \
               f'</tr>'
