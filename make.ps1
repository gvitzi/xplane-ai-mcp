# Repo root — .NET MCP server + integration pytest.
#
# Examples:
#   .\make.ps1 test -- -v
#   .\make.ps1 test-integration -- --xplane-root="C:\X-Plane 12"

$ErrorActionPreference = 'Stop'

$python = if ($env:PYTHON) { $env:PYTHON } else { 'python' }
$pip = if ($env:PIP) { $env:PIP } else { 'pip' }
$repo = $PSScriptRoot
$sln = Join-Path $repo 'src/XPlaneMcp.sln'
$proj = Join-Path $repo 'src/XPlaneMcp.Server/XPlaneMcp.Server.csproj'

$target = $args[0]
$pass = @()
if ($args.Count -gt 1) {
    $pass = @($args[1..($args.Count - 1)])
}
if ($pass.Count -ge 1 -and $pass[0] -eq '--') {
    $pass = if ($pass.Count -gt 1) { @($pass[1..($pass.Count - 1)]) } else { @() }
}

if (-not $target) {
    $target = 'help'
}

function Invoke-Publish {
    $script = Join-Path $repo 'scripts/publish-server.ps1'
    if (Get-Command pwsh -ErrorAction SilentlyContinue) {
        & pwsh -NoProfile -ExecutionPolicy Bypass -File $script @pass
    } else {
        & powershell -NoProfile -ExecutionPolicy Bypass -File $script @pass
    }
}

switch ($target) {
    'help' {
        Write-Host 'Targets (repo root):'
        Write-Host '  .\make.ps1 install              dotnet restore/build + pip install -e .[dev]'
        Write-Host '  .\make.ps1 install-dotnet       dotnet only'
        Write-Host '  .\make.ps1 install-py-dev       pip install -e .[dev] only'
        Write-Host '  .\make.ps1 test                 dotnet test + pytest'
        Write-Host '  .\make.ps1 test-integration     pytest -m integration (flags after --)'
        Write-Host '  .\make.ps1 run / mcp            dotnet run MCP server'
        Write-Host '  .\make.ps1 publish              scripts/publish-server.ps1'
        Write-Host '  .\make.ps1 msi                  WiX MSI -> artifacts/installer/xplane_mcp_installer.msi'
    }
    'install' {
        dotnet restore $sln
        dotnet build $sln -c Debug
        & $pip install -e '.[dev]'
    }
    'install-dotnet' {
        dotnet restore $sln
        dotnet build $sln -c Debug
    }
    'install-py-dev' {
        & $pip install -e '.[dev]'
    }
    'test' {
        dotnet test $sln -c Release
        Push-Location $repo
        try {
            & $python -m pytest @pass
        } finally {
            Pop-Location
        }
    }
    'test-integration' {
        Push-Location $repo
        try {
            & $python -m pytest -m integration @pass
        } finally {
            Pop-Location
        }
    }
    'run' {
        dotnet run --project $proj -c Release @pass
    }
    'mcp' {
        dotnet run --project $proj -c Release @pass
    }
    'publish' {
        Invoke-Publish
    }
    'msi' {
        $script = Join-Path $repo 'scripts/build-msi.ps1'
        & powershell -NoProfile -ExecutionPolicy Bypass -File $script @pass
    }
    default {
        Write-Error "Unknown target '$target'. Use: install, test, run, mcp, publish, msi, or help."
    }
}
