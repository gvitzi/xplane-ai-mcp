# Build xplaneMCP.msi (WiX): self-contained win-x64 publish + MSI to artifacts/installer/.
# Requires .NET SDK 9+ (restores WixToolset.Sdk via NuGet).
#
# Usage: powershell -File scripts/build-msi.ps1 [-Configuration Release]

param(
    [string] $Configuration = "Release"
)

$ErrorActionPreference = 'Stop'
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
$staging = Join-Path $repoRoot 'artifacts/msi-staging'
$serverProj = Join-Path $repoRoot 'src/XPlaneMcp.Server/XPlaneMcp.Server.csproj'
$wixProj = Join-Path $repoRoot 'installer/xplaneMcp.wixproj'
$msiOut = Join-Path $repoRoot 'artifacts/installer/xplaneMCP.msi'

New-Item -ItemType Directory -Force -Path $staging | Out-Null

$appIco = Join-Path $repoRoot 'resources/xplane_mcp_icon.ico'
if (-not (Test-Path $appIco)) {
    Write-Error "Missing application icon: $appIco"
}

Write-Host "Preparing installer UI bitmaps from resources/background.png..."
python (Join-Path $repoRoot 'scripts/prepare_installer_assets.py')

Write-Host "Publishing self-contained win-x64 -> $staging ..."
dotnet publish $serverProj -c $Configuration -r win-x64 --self-contained true -o $staging /p:ApplicationIcon=$appIco

$installerDir = Join-Path $repoRoot 'installer'
Copy-Item (Join-Path $installerDir 'CopyCodexMcpSnippet.ps1') $staging -Force
Copy-Item (Join-Path $installerDir 'CopyCodexMcpSnippet.cmd') $staging -Force
Copy-Item (Join-Path $installerDir 'CodexSetup.txt') $staging -Force

if (-not (Test-Path (Join-Path $staging 'XPlaneMcp.Server.exe'))) {
    Write-Error "Publish did not produce XPlaneMcp.Server.exe under $staging"
}

Write-Host "Building WiX MSI..."
dotnet build $wixProj -c $Configuration

if (-not (Test-Path $msiOut)) {
    Write-Error "MSI not found at expected path: $msiOut"
}

Write-Host ""
Write-Host "MSI: $msiOut"
Write-Host "Install: double-click or msiexec /i `"$msiOut`""
Write-Host "Silent:    msiexec /i `"$msiOut`" /qn"
Write-Host "Default install dir: C:\Program Files\xplaneMCP\XPlaneMcp.Server.exe"
