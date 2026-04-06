# GNU Make — run from archived/python (same targets as Taskfile.yml).
.PHONY: help install test mcp

PYTHON ?= python
PIP ?= pip
PYTEST_ARGS ?=
MCP_ARGS ?=

help:
	@echo Targets (run from archived/python):
	@echo "  make install              pip install -e .[dev]"
	@echo "  make test                 pytest (optional PYTEST_ARGS=...)"
	@echo "  make mcp                  python -m xplane_mcp.poc (optional MCP_ARGS=...)"

install:
	$(PIP) install -e ".[dev]"

test:
	cd "$(CURDIR)" && PYTHONPATH="$(CURDIR)/src" $(PYTHON) -m pytest $(PYTEST_ARGS)

mcp:
	cd "$(CURDIR)" && PYTHONPATH="$(CURDIR)/src" $(PYTHON) -m xplane_mcp.poc $(MCP_ARGS)
