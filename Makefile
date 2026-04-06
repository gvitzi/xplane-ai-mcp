# Requires GNU Make (e.g. chocolatey make, Git Bash, or WSL on Windows).
# On Windows without make:  .\make.ps1   or   make.cmd test -- -v
.PHONY: help install install-dotnet install-py-dev test test-integration run mcp publish publish-sh

PYTHON ?= python
PIP ?= pip
PYTEST_ARGS ?=
DOTNET_SLN ?= $(CURDIR)/src/XPlaneMcp.sln
SERVER_PROJ ?= $(CURDIR)/src/XPlaneMcp.Server/XPlaneMcp.Server.csproj

help:
	@echo Targets (repo root — .NET MCP + integration pytest):
	@echo "  make install              dotnet restore/build + pip install -e .[dev]"
	@echo "  make install-dotnet       dotnet restore + build only"
	@echo "  make install-py-dev       pip install -e .[dev] only"
	@echo "  make test                 dotnet test + pytest (default excludes integration)"
	@echo "  make test-integration     pytest -m integration (pass PYTEST_ARGS or extra args)"
	@echo "  make run / make mcp       dotnet run MCP stdio server"
	@echo "  make publish              pwsh scripts/publish-server.ps1"
	@echo "  make publish-sh           bash scripts/publish-server.sh"

install:
	dotnet restore "$(DOTNET_SLN)"
	dotnet build "$(DOTNET_SLN)" -c Debug
	$(PIP) install -e ".[dev]"

install-dotnet:
	dotnet restore "$(DOTNET_SLN)"
	dotnet build "$(DOTNET_SLN)" -c Debug

install-py-dev:
	$(PIP) install -e ".[dev]"

test:
	dotnet test "$(DOTNET_SLN)" -c Release
	cd "$(CURDIR)" && $(PYTHON) -m pytest $(PYTEST_ARGS)

test-integration:
	cd "$(CURDIR)" && $(PYTHON) -m pytest -m integration $(PYTEST_ARGS)

run:
	dotnet run --project "$(SERVER_PROJ)" -c Release

mcp: run

publish:
	powershell -NoProfile -ExecutionPolicy Bypass -File "$(CURDIR)/scripts/publish-server.ps1"

publish-sh:
	bash "$(CURDIR)/scripts/publish-server.sh"
