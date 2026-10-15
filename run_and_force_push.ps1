# Local Phase 2 retry wrapper. Never deletes active Git locks or rewrites remote history.
[CmdletBinding()]
param([ValidateRange(1,10)][int]$MaxAttempts = 10)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
Set-Location $PSScriptRoot
$env:PAPER_MODE = '1'
$env:LIVE_ORDER_AUTHORITY = '0'
$receipt = 'data/paper_ledger/receipt.json'
function Git([string[]]$Arguments) {
    $out = & git @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) { throw "git $($Arguments -join ' ') failed: $out" }
    return ($out | Out-String).Trim()
}
function Verify-Remote([string]$Expected) {
    $remote = (Git @('ls-remote','origin','refs/heads/test-framework')).Split()[0]
    return $remote -eq $Expected
}
if ((Git @('branch','--show-current')) -ne 'test-framework') { throw 'Checkout test-framework first.' }
if (Test-Path '.git/index.lock') { throw 'Git index.lock exists: inspect the running Git process; active locks are never force-deleted.' }
if ((Git @('status','--porcelain','--untracked-files=no')) -ne '') { throw 'Tracked working tree is dirty; preserve local changes before retrying.' }
$success = $false
for ($i=1; $i -le $MaxAttempts; $i++) {
    Write-Host "Phase 2 attempt $i/$MaxAttempts"
    try {
        $env:PAPER_MODE='1'; $env:LIVE_ORDER_AUTHORITY='0'
        & python run_phase2_local.py --push
        if ($LASTEXITCODE -ne 0) { throw 'Local paper runner returned nonzero exit.' }
        if (-not (Test-Path $receipt)) { throw 'Receipt missing.' }
        $r = Get-Content $receipt -Raw | ConvertFrom-Json
        if ($r.paper_mode -ne 1 -or $r.live_order_authority -ne 0 -or $r.status -ne 'LOCAL_ARTIFACT_ONLY_NOT_INSERTED') { throw 'Unsafe or invalid receipt.' }
        if ($r.prediction_hash -notmatch '^[a-f0-9]{64}$' -or $r.source_hash -notmatch '^[a-f0-9]{64}$') { throw 'Invalid receipt hashes.' }
        $head = Git @('rev-parse','HEAD')
        if (-not (Verify-Remote $head)) { throw 'Remote branch SHA does not match local HEAD.' }
        $tracked = Git @('ls-tree','-r','--name-only','HEAD','--',$receipt)
        if ($tracked -ne $receipt) { throw 'Receipt not included in pushed commit.' }
        Write-Host "VERIFIED_REMOTE_RECEIPT_COMMIT=$head"
        Write-Host "PREDICTION_SHA256=$($r.prediction_hash)"
        $success = $true
        break
    } catch {
        Write-Warning $_.Exception.Message
        if ($i -eq $MaxAttempts) { break }
        if (Test-Path '.git/index.lock') { throw 'Git lock detected; cannot safely assume it is stale.' }
        try {
            Git @('fetch','origin','test-framework') | Out-Null
            $local = Git @('rev-parse','HEAD')
            $remote = Git @('rev-parse','origin/test-framework')
            if ($local -ne $remote) {
                $base = Git @('merge-base','HEAD','origin/test-framework')
                if ($base -ne $remote) { throw 'Remote branch diverged; preserve both histories and resolve explicitly.' }
            }
        } catch { throw "Cannot safely retry divergent or unavailable Git state: $_" }
        Start-Sleep -Seconds ([Math]::Min(60, 3 * $i))
    }
}
if (-not $success) { throw "Phase 2 remote verification failed after $MaxAttempts attempts. No forced push or lock deletion performed." }
