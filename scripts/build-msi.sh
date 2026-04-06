#!/usr/bin/env bash
# Build xplaneMCP.msi (WiX) on Windows via Git Bash / WSL with dotnet on PATH.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STAGING="$ROOT/artifacts/msi-staging"
CONFIG="${1:-Release}"
echo "Publishing self-contained win-x64 -> $STAGING ..."
dotnet publish "$ROOT/src/XPlaneMcp.Server/XPlaneMcp.Server.csproj" -c "$CONFIG" -r win-x64 --self-contained true -o "$STAGING"
cp -f "$ROOT/installer/CopyCodexMcpSnippet.ps1" "$STAGING/"
cp -f "$ROOT/installer/CopyCodexMcpSnippet.cmd" "$STAGING/"
cp -f "$ROOT/installer/CodexSetup.txt" "$STAGING/"
echo "Building WiX MSI..."
dotnet build "$ROOT/installer/xplaneMcp.wixproj" -c "$CONFIG"
echo "MSI: $ROOT/artifacts/installer/xplaneMCP.msi"
