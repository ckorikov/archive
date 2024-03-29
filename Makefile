python-exec=python3
template=tools/index.template 

all: help

help:
	@echo "not implemented"

generate-json:
	${python-exec} tools/build_archive.py

generate-html: publications.json
	${python-exec} tools/index_html_generator.py  -t ${template} -p publications.json

clean:
	rm -f publications.json index.html

generate: generate-json generate-html

format: black isort

black:
	${python-exec} -m black tools -l 120

isort:
	${python-exec} -m isort tools

install:
	${python-exec} -m pip install -r tools/requirements.txt
