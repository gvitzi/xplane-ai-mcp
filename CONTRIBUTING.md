# Contributing

Thanks for helping improve **xplane-ai-mcp**.

## Quick start

- **.NET MCP server:** solution at [`src/XPlaneMcp.sln`](src/XPlaneMcp.sln). Build and test:

  ```bash
  dotnet build src/XPlaneMcp.sln -c Release
  dotnet test src/XPlaneMcp.sln -c Release
  ```

- **Python tests** (repo root): install dev deps, then run pytest (integration tests are excluded by default):

  ```bash
  pip install -e ".[dev]"
  pytest
  ```

- **Integration tests** (require X-Plane running with the Web API enabled):

  ```bash
  pytest -m integration --xplane-root="PATH/TO/X-Plane 12"
  ```

  Build the server first so `tests/mcp_stdio.py` can find `xplaneMCP.exe`, or pass `--mcp-server=PATH`.

- **Windows helpers:** [`make.ps1`](make.ps1) / [`make.cmd`](make.cmd) wrap common `dotnet` and `pytest` flows.

## Pull requests

- Prefer small, focused changes with a clear description.
- Use [Conventional Commits](https://www.conventionalcommits.org/) style messages (e.g. `feat(mcp):`, `fix:`, `docs:`).
- For larger features, open an issue first to agree on scope.

## Code style

- Match existing patterns in touched files (C# nullable, MCP tool naming in `PascalCase` → MCP `snake_case`).
- Do not commit secrets, local paths, or credentials.
