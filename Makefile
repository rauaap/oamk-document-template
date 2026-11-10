.DEFAULT_GOAL := all

MARKDOWN ?= report.md
TEMPLATE ?= templates/report.odt
OUTPUT ?= build/report.odt
# Optional override; otherwise chapter-start comes from Markdown front matter.
START ?=
SYSTEM_PYTHON ?= /usr/bin/python3

.PHONY: all setup test clean
all: $(OUTPUT) $(OUTPUT:.odt=.pdf)

# UNO is supplied by LibreOffice, not PyPI. Use the Python it is installed for.
.venv/.report-ready: pyproject.toml uv.lock
	uv venv --allow-existing --system-site-packages --python $(SYSTEM_PYTHON) .venv
	uv sync --locked --python $(SYSTEM_PYTHON)
	uv run --no-sync python -c 'import uno'
	touch $@

setup: .venv/.report-ready

test: setup
	uv run --no-sync python -m unittest discover -s tests -v

# Grouped outputs: one build creates both ODT and PDF.
$(OUTPUT) $(OUTPUT:.odt=.pdf) &: $(MARKDOWN) $(TEMPLATE) scripts/build_report.py scripts/front_matter.py Makefile .venv/.report-ready
	uv run --no-sync python scripts/build_report.py --template "$(TEMPLATE)" --markdown "$(MARKDOWN)" --output "$(OUTPUT)" $(if $(START),--start "$(START)")

clean:
	rm -rf build
