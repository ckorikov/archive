import logging
import os
from string import Template

import pdf2image

import layout as env


class Slides:
    def __init__(self, item, output_dir, root_dir, filename='slides.template.html'):
        logging.info(f'Create slides generator for `{item.title}`')
        self.__item = item
        self.output_dir = output_dir
        self.root_dir = root_dir
        self.content = ''

        template_path = env.get_template(f'{root_dir}/templates', filename)

        if not template_path:
            raise ValueError(f'Cannot find template `{filename}` in `{root_dir}/templates`')

        self.template = Template(template_path)

    def __pdf_to_images(self, pdf_file, output='data', dpi=100):
        logging.info(f'Converting pdf to images to {output}...')
        if not os.path.exists(output):
            os.mkdir(output)
        images = pdf2image.convert_from_bytes(pdf_file, dpi=dpi)
        for i, image in enumerate(images):
            image.save(f'{output}/page{i}.png', 'PNG')
        return len(images)

    def __generate_slides(self, path, n):
        slides = ''
        for i in range(n):
            slides += f'<section><img class="r-stretch" src="{path}/page{i}.png"></section>'

        authors = [f'<a href="#">{author}</a>' for author in self.__item.creators]
        authors = " ".join(authors)

        tags = [f'<a href="#">#{tag}</a>' for tag in self.__item.tags]
        tags = " ".join(tags)

        counter = f'{n} slide' if n == 1 else f'{n} slides'

        self.content = self.template.safe_substitute(title=self.__item.title,
                                                     date=self.__item.date,
                                                     author=authors,
                                                     tags=tags,
                                                     counter=counter,
                                                     slides=slides)

    def generate(self):
        if not os.path.exists(f'{self.output_dir}/data'):
            os.mkdir(f'{self.output_dir}/data')
        if 'pdf' not in self.__item.url:
            logging.warning(f'URL is not a path to pdf file for `{self.__item.title}`')
            return
        logging.info(f'Downloading file for `{self.__item.title}`')
        data = self.__item.file
        logging.info(f'Received file for `{self.__item.title}`')
        try:
            number_of_pages = self.__pdf_to_images(data, output=f'{self.output_dir}/data/{self.__item.identifier}')
        except Exception:
            logging.warning(f'Skip `{self.__item.title}`')
            return
        self.__generate_slides(f'{self.output_dir}/data/{self.__item.identifier}', number_of_pages)
        self.save(self.__item.identifier)

    def save(self, name):
        with open(f'{self.output_dir}/data/{name}/index.html', 'w') as f:
            return f.write(self.content)
