STATIC_DATA_DIR := site/static/data
SITE_DIR := site
TOOLS_DIR := tools
CONTENT_DIR := $(SITE_DIR)/content
DEPLOYMENT_DIR := public
UV_RUN := uv run --project $(TOOLS_DIR)

PUBLICATIONS := $(STATIC_DATA_DIR)/publications.json
CONFIG := archive.yaml
CONTENT_STAMP := $(CONTENT_DIR)/.stamp

.PHONY: all build deploy serve debug clean fetch validate generate lint check format test help

all: build

help:
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@echo "  build     Build site to docs/ for GitHub Pages"
	@echo "  deploy    Clean and rebuild (production)"
	@echo "  serve     Start dev server with drafts"
	@echo "  clean     Remove generated files"
	@echo "  fetch     Fetch publications from Zotero"
	@echo "  validate  Validate data files"
	@echo "  generate  Generate Hugo content"
	@echo "  lint      Lint all source files (Python, YAML, HTML)"
	@echo "  format    Format all source files (Python, HTML, CSS)"

# Fetch from Zotero API
fetch:
	$(UV_RUN) $(if $(wildcard .env),--env-file .env) $(TOOLS_DIR)/fetch.py --output $(PUBLICATIONS)

# Validate data files
validate: $(PUBLICATIONS)
	$(UV_RUN) $(TOOLS_DIR)/validate.py \
		--publications $(PUBLICATIONS) \
		--config $(CONFIG)

# Generate content
generate: validate
	$(UV_RUN) $(TOOLS_DIR)/generate.py \
		--publications $(PUBLICATIONS) \
		--config $(CONFIG) \
		--output $(CONTENT_DIR)

# Incremental build via stamp file
$(CONTENT_STAMP): $(PUBLICATIONS) $(CONFIG)
	$(MAKE) generate
	touch $@

# Build to docs/ for GitHub Pages
build: $(CONTENT_STAMP)
	$(UV_RUN) hugo --source $(SITE_DIR) --minify --destination $(CURDIR)/$(DEPLOYMENT_DIR)

# Alias for build (production deploy)
deploy: clean build

# Dev server with drafts
serve: $(CONTENT_STAMP)
	$(UV_RUN) hugo server --source $(SITE_DIR) --destination $(CURDIR)/$(DEPLOYMENT_DIR) -D

# Clean generated files (keeps publications.json)
clean:
	rm -rf $(DEPLOYMENT_DIR) $(CONTENT_DIR)
	rm -f $(SITE_DIR)/static/llms.txt $(SITE_DIR)/static/ai.txt

# Lint all source files (Python + YAML + HTML)
lint:
	$(UV_RUN) ruff check $(TOOLS_DIR)
	$(UV_RUN) yamllint -c .yamllint.yaml .github/workflows/ archive.yaml
	$(UV_RUN) djlint $(SITE_DIR)/themes/

# Alias for lint
check: lint

# Run smoke and visual tests (server must be running: make serve)
test:
	$(UV_RUN) pytest $(TOOLS_DIR)/tests/ -v

# Format all source files (Python + HTML + CSS)
format:
	$(UV_RUN) ruff format $(TOOLS_DIR)
	$(UV_RUN) ruff check --fix $(TOOLS_DIR)
	$(UV_RUN) djlint $(SITE_DIR)/themes/ --reformat
	npx --yes prettier --write "$(SITE_DIR)/themes/**/*.css"
