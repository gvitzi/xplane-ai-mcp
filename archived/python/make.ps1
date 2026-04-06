# Same targets as Makefile — use from archived/python when `make` is not installed.
# Example:  cd archived/python; .\make.ps1 mcp -- --skip-flight

$ErrorActionPreference = 'Stop'

$python = if ($env:PYTHON) { $env:PYTHON } else { 'python' }
$pip = if ($env:PIP) { $env:PIP } else { 'pip' }

$here = $PSScriptRoot
$src = Join-Path $here 'src'

function Set-ArchivedPythonPath {
    $sep = [IO.Path]::PathSeparator
    if ($env:PYTHONPATH) {
        $env:PYTHONPATH = "$src$sep$env:PYTHONPATH"
    } else {
        $env:PYTHONPATH = $src
    }
}

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

Push-Location $here
try {
    switch ($target) {
        'help' {
            Write-Host 'Targets (run from archived/python):'
            Write-Host '  .\make.ps1 install              pip install -e .[dev]'
            Write-Host '  .\make.ps1 test                 python -m pytest (flags after --)'
            Write-Host '  .\make.ps1 mcp                  python -m xplane_mcp.poc (flags after --)'
        }
        'install' {
            & $pip install -e '.[dev]'
        }
        'test' {
            Set-ArchivedPythonPath
            & $python -m pytest @pass
        }
        'mcp' {
            Set-ArchivedPythonPath
            & $python -m xplane_mcp.poc @pass
        }
        default {
            Write-Error "Unknown target '$target'. Use: install, test, mcp, or help."
        }
    }
} finally {
    Pop-Location
}
