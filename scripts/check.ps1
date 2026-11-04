$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
$script:failed = $false

function Invoke-Step {
    param([string]$Name, [string]$Dir, [scriptblock]$Cmd)
    Write-Host "==> $Name" -ForegroundColor Cyan
    Push-Location $Dir
    $global:LASTEXITCODE = 0
    & $Cmd
    if ($LASTEXITCODE -ne 0) {
        Write-Host "FAIL $Name (exit $LASTEXITCODE)" -ForegroundColor Red
        $script:failed = $true
    } else {
        Write-Host "OK   $Name" -ForegroundColor Green
    }
    Pop-Location
}

Invoke-Step 'db reachable' $root { docker compose exec -T db pg_isready -h localhost }
$backend = Join-Path $root 'backend'
Invoke-Step 'ruff check' $backend { uv run ruff check . }
Invoke-Step 'ruff format' $backend { uv run ruff format --check . }
Invoke-Step 'pytest' $backend { uv run pytest -q }

$frontend = Join-Path $root 'frontend'
if (Test-Path (Join-Path $frontend 'package.json')) {
    Invoke-Step 'tsc' $frontend { npm run typecheck }
    Invoke-Step 'eslint' $frontend { npm run lint }
    Invoke-Step 'vite build' $frontend { npm run build }
} else {
    Write-Host 'SKIP frontend (not created yet)' -ForegroundColor Yellow
}

if ($script:failed) {
    Write-Host 'CHECKS FAILED' -ForegroundColor Red
    exit 1
}
Write-Host 'ALL CHECKS PASSED' -ForegroundColor Green
exit 0
