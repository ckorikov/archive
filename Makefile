STATIC_DATA_DIR := site/static/data
SITE_DIR := site
TOOLS_DIR := tools
CONTENT_DIR := $(SITE_DIR)/content
DEPLOYMENT_DIR := docs

PUBLICATIONS := $(STATIC_DATA_DIR)/publications.json
CONFIG := archive.yaml
CONTENT_STAMP := $(CONTENT_DIR)/.stamp

.PHONY: all build deploy serve debug clean fetch validate generate check format help

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
	@echo "  check     Check Python code with ruff"
	@echo "  format    Format Python code with ruff"

# Fetch from Zotero API
fetch:
	uv run --project $(TOOLS_DIR) $(TOOLS_DIR)/fetch.py --output $(PUBLICATIONS)

# Validate data files
validate: $(PUBLICATIONS)
	uv run --project $(TOOLS_DIR) $(TOOLS_DIR)/validate.py \
		--publications $(PUBLICATIONS) \
		--config $(CONFIG)

# Generate content
generate: validate
	uv run --project $(TOOLS_DIR) $(TOOLS_DIR)/generate.py \
		--publications $(PUBLICATIONS) \
		--config $(CONFIG) \
		--output $(CONTENT_DIR) \
		--clean

# Incremental build via stamp file
$(CONTENT_STAMP): $(PUBLICATIONS) $(CONFIG)
	$(MAKE) generate
	touch $@

# Build to docs/ for GitHub Pages
build: $(CONTENT_STAMP)
	hugo --source $(SITE_DIR) --minify --destination $(CURDIR)/$(DEPLOYMENT_DIR)

# Alias for build (production deploy)
deploy: clean build

# Dev server with drafts
serve: $(CONTENT_STAMP)
	hugo server --source $(SITE_DIR) --destination $(CURDIR)/$(DEPLOYMENT_DIR) -D

# Clean generated files (keeps publications.json)
clean:
	rm -rf $(DEPLOYMENT_DIR) $(CONTENT_DIR) $(SITE_DIR)/public

# Check and fix Python code
check:
	uv run --project $(TOOLS_DIR) ruff check --fix $(TOOLS_DIR)

# Format Python code
format:
	uv run --project $(TOOLS_DIR) ruff format $(TOOLS_DIR)
