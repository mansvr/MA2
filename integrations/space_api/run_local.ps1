# Local API (needs NVIDIA GPU + full Python deps — same as HF image).
# From repo root: .\integrations\space_api\run_local.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$env:PYTHONPATH = $Root
Set-Location $PSScriptRoot

if (-not $env:MESHANYTHING_SERVER_API_KEY) {
    Write-Host "MESHANYTHING_SERVER_API_KEY not set — API auth disabled (OK for local dev)."
}

python -m uvicorn app:app --host 127.0.0.1 --port 7860
