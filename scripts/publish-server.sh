#!/usr/bin/env bash
# Publish the MCP server to ./artifacts/xplane-mcp (repo root relative).
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROJECT="$REPO_ROOT/src/XPlaneMcp.Server/XPlaneMcp.Server.csproj"
CONFIG="${1:-Release}"
OUT="${2:-$REPO_ROOT/artifacts/xplane-mcp}"
mkdir -p "$OUT"
echo "Publishing $PROJECT -> $OUT ($CONFIG)..."
dotnet publish "$PROJECT" -c "$CONFIG" -o "$OUT" --no-self-contained
echo "Done. Output: $OUT"
