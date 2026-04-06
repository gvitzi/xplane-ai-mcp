# Publish the MCP server to ./artifacts/xplane-mcp (repo root relative).
# Usage: pwsh -File scripts/publish-server.ps1 [-Configuration Release] [-Output path]

param(
    [string] $Configuration = "Release",
    [string] $Output = ""
)

$ErrorActionPreference = 'Stop'
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
$project = Join-Path $repoRoot 'src/XPlaneMcp.Server/XPlaneMcp.Server.csproj'
if (-not (Test-Path $project)) {
    Write-Error "Project not found: $project"
}

if (-not $Output) {
    $Output = Join-Path $repoRoot 'artifacts/xplane-mcp'
}

New-Item -ItemType Directory -Force -Path $Output | Out-Null

Write-Host "Publishing $project -> $Output ($Configuration)..."
dotnet publish $project -c $Configuration -o $Output --no-self-contained

$exe = Join-Path $Output 'XPlaneMcp.Server.exe'
if (Test-Path $exe) {
    Write-Host ""
    Write-Host "Published executable: $exe"
    Write-Host 'Cursor mcp.json example: set "command" to this path, "args": [], "cwd" to repo root (or omit).'
} else {
    $dll = Join-Path $Output 'XPlaneMcp.Server.dll'
    if (Test-Path $dll) {
        Write-Host ""
        Write-Host "Published: $dll"
        Write-Host 'Run with: dotnet "<path>/XPlaneMcp.Server.dll"'
    }
}
