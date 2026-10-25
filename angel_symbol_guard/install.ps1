#requires -version 5.1
$ErrorActionPreference = 'Stop'
$repo = (Get-Location).Path
if (!(Test-Path 'agent_manifest.json') -or !(Test-Path 'config\fno_canonical_universe_219.json')) { throw 'Run this installer from the angel-fno-scanner repository root.' }
if (!(Get-Command python -ErrorAction SilentlyContinue)) { throw 'Python not found on PATH.' }
$source = Join-Path $PSScriptRoot 'symbol_guard.py'
if (!(Test-Path $source)) { throw 'symbol_guard.py must be next to install.ps1.' }
New-Item -ItemType Directory -Force config,tools,'.github\workflows' | Out-Null
$regPath = 'config\corporate_action_registry.json'
if (!(Test-Path $regPath)) {
@'
{
  "schema_version": 1,
  "events": [
    {
      "old_symbol": "ICICIPRULI",
      "new_symbol": "ICICILIFE",
      "effective_date": "2026-10-23",
      "exchange": "NSE",
      "segments": ["EQ", "FO"],
      "equity_isin": "INE726G01019",
      "source_ref": "NSE/CML/76967",
      "source_url": "https://nsearchives.nseindia.com/content/circulars/CML76967.pdf",
      "derivatives_source_ref": "NSE/FAOP/77013",
      "derivatives_source_url": "https://nsearchives.nseindia.com/content/circulars/FAOP77013.pdf",
      "status": "exchange_verified"
    }
  ]
}
'@ | Set-Content -LiteralPath $regPath -Encoding UTF8
Write-Host 'CREATED registry' -ForegroundColor Green
} else { Write-Host 'PRESERVED existing registry (not overwritten)' -ForegroundColor Yellow }
$dest = 'tools\symbol_identity_guard.py'
if (!(Test-Path $dest)) { Copy-Item -LiteralPath $source -Destination $dest; Write-Host 'CREATED guard' -ForegroundColor Green }
else { Write-Host 'PRESERVED existing guard (not overwritten)' -ForegroundColor Yellow }
$workflow='.github\workflows\symbol-identity-audit.yml'
if (!(Test-Path $workflow)) {
@'
name: Symbol Identity Audit
on:
  push:
    paths:
      - 'agent_manifest.json'
      - 'config/fno_canonical_universe_219.json'
      - 'config/corporate_action_registry.json'
      - 'tools/symbol_identity_guard.py'
      - '.github/workflows/symbol-identity-audit.yml'
  pull_request:
  schedule:
    - cron: '15 2 * * 1-5'
  workflow_dispatch:
permissions:
  contents: read
jobs:
  offline-identity:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: python tools/symbol_identity_guard.py
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: symbol-identity-audit
          path: proof-output/symbol-identity/identity_audit.json
'@ | Set-Content -LiteralPath $workflow -Encoding UTF8
Write-Host 'CREATED GitHub audit workflow' -ForegroundColor Green
} else { Write-Host 'PRESERVED existing workflow (not overwritten)' -ForegroundColor Yellow }
python tools\symbol_identity_guard.py
$code=$LASTEXITCODE
Write-Host "OFFLINE AUDIT EXIT: $code; production remains NOT CERTIFIED without live evidence"
exit $code
