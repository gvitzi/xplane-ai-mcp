# Copies a Codex CLI ~/.codex/config.toml snippet for this install (stdio MCP).
$ErrorActionPreference = 'Stop'
$exePath = Join-Path $PSScriptRoot 'XPlaneMcp.Server.exe'
if (-not (Test-Path -LiteralPath $exePath)) {
    exit 1
}
$full = [System.IO.Path]::GetFullPath($exePath)
# TOML single-quoted literal: escape ' as ''
$lit = $full -replace "'", "''"
$snippet = @"
[mcp_servers.xplaneMCP]
command = '$lit'
args = []
enabled = true

# Optional (X-Plane Web API):
# env = { XPLANE_HOST = "127.0.0.1", XPLANE_PORT = "49000" }
"@
Set-Clipboard -Value $snippet
