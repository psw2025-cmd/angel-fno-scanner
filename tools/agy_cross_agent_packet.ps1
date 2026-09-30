param(
    [Parameter(Mandatory=$true)][string]$Claim,
    [string]$Observation = "Local runtime observation captured by AGY CLI.",
    [string]$PrimaryEvidence = "Local Windows process/port/runtime evidence.",
    [string]$BeforeState = "Not supplied",
    [string]$ActionTaken = "Evidence capture only",
    [string]$AfterState = "Not supplied",
    [string]$PeerCheckRequest = "Independently verify against GitHub, Google Sheet, BigQuery and available artifacts.",
    [string]$KnownLimitations = "",
    [ValidateSet("OBSERVED","OPEN_AUTO_FIXABLE","IMPLEMENTED_NOT_DEPLOYED","VERIFIED_LOCAL","VERIFIED_REMOTE","DISPUTED","WAITING_FOR_PEER","WAITING_FOR_USER","RESOLVED_TWO_PARTY")]
    [string]$Status = "WAITING_FOR_PEER",
    [string]$RepoPath = ".",
    [int]$IssueNumber = 3,
    [switch]$PostToGitHub
)

$ErrorActionPreference = "Stop"
$repoFullName = "psw2025-cmd/angel-fno-scanner"
$tz = [System.TimeZoneInfo]::FindSystemTimeZoneById("India Standard Time")
$nowIst = [System.TimeZoneInfo]::ConvertTimeFromUtc([DateTime]::UtcNow, $tz)
$stamp = $nowIst.ToString("yyyyMMdd_HHmmss")
$claimId = "AGY-" + $stamp + "-" + ([Guid]::NewGuid().ToString("N").Substring(0,8))

function Try-Text([scriptblock]$Block) {
    try { return (& $Block | Out-String).Trim() } catch { return "" }
}

$resolvedRepo = (Resolve-Path $RepoPath).Path
$headSha = Try-Text { git -C $resolvedRepo rev-parse HEAD 2>$null }
$branch = Try-Text { git -C $resolvedRepo rev-parse --abbrev-ref HEAD 2>$null }

$targetNames = @("PBIDesktop.exe","msmdsrv.exe","powershell.exe","pwsh.exe","python.exe","python3.exe")
$procRaw = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object { $targetNames -contains $_.Name }

$processes = @()
$pids = @()
foreach ($p in $procRaw) {
    $pids += [int]$p.ProcessId
    $processes += [ordered]@{
        pid = [int]$p.ProcessId
        name = [string]$p.Name
        creation_date = [string]$p.CreationDate
    }
}

$listeners = @()
try {
    $tcp = Get-NetTCPConnection -State Listen -ErrorAction Stop
    foreach ($c in $tcp) {
        if ($pids -contains [int]$c.OwningProcess) {
            $listeners += [ordered]@{
                local_address = [string]$c.LocalAddress
                local_port = [int]$c.LocalPort
                owning_process = [int]$c.OwningProcess
            }
        }
    }
} catch {}

$packet = [ordered]@{
    schema_version = "1.0"
    claim_id = $claimId
    claiming_agent = "AGY_CLI"
    claim_time_ist = $nowIst.ToString("yyyy-MM-ddTHH:mm:ss.fffzzz")
    host_or_runtime = $env:COMPUTERNAME
    repo = $repoFullName
    branch = $branch
    base_sha = $null
    head_sha = $(if ($headSha) { $headSha } else { $null })
    artifact_sha256 = $null
    claim = $Claim
    observation = $Observation
    exact_commands = @(
        "Get-CimInstance Win32_Process (filtered names; command lines intentionally omitted)",
        "Get-NetTCPConnection -State Listen (filtered to captured process IDs)",
        "git rev-parse HEAD",
        "git rev-parse --abbrev-ref HEAD"
    )
    primary_evidence = $PrimaryEvidence
    source_timestamps = [ordered]@{
        packet_time_ist = $nowIst.ToString("yyyy-MM-dd HH:mm:ss")
    }
    pid_process_ports = @(
        [ordered]@{ processes = $processes; listeners = $listeners }
    )
    before_state = $BeforeState
    action_taken = $ActionTaken
    after_state = $AfterState
    safety_state = "PAPER_ANALYZER_ONLY; LIVE_ORDER_AUTHORITY_NOT_GRANTED"
    secrets_redacted = $true
    peer_check_request = $PeerCheckRequest
    known_limitations = $KnownLimitations
    status = $Status
}

$outDir = Join-Path $resolvedRepo "cross_agent_packets"
New-Item -ItemType Directory -Path $outDir -Force | Out-Null
$jsonPath = Join-Path $outDir ($claimId + ".json")
$packet | ConvertTo-Json -Depth 10 | Set-Content -Path $jsonPath -Encoding UTF8
$sha256 = (Get-FileHash -Algorithm SHA256 -Path $jsonPath).Hash.ToLowerInvariant()
$packet.artifact_sha256 = $sha256
$packet | ConvertTo-Json -Depth 10 | Set-Content -Path $jsonPath -Encoding UTF8

# Re-hash after inserting artifact_sha256 is intentionally not used as self-referential content cannot hash to itself.
# The artifact_sha256 field identifies the first canonical payload serialization before hash annotation.
$mdPath = Join-Path $outDir ($claimId + ".md")
$jsonForComment = Get-Content $jsonPath -Raw
@"
## CROSS_AGENT_PACKET $claimId

Status: **$Status**

```json
$jsonForComment
```

Peer requested: ChatGPT independent verification against GitHub/Sheets/BigQuery/available artifacts.
"@ | Set-Content -Path $mdPath -Encoding UTF8

Write-Host "[PASS] Cross-agent packet created"
Write-Host "JSON: $jsonPath"
Write-Host "Markdown: $mdPath"
Write-Host "Claim ID: $claimId"
Write-Host "Head SHA: $headSha"

if ($PostToGitHub) {
    if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
        throw "GitHub CLI 'gh' is not installed or not on PATH. Packet remains saved locally."
    }
    gh issue comment $IssueNumber --repo $repoFullName --body-file $mdPath
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to post packet to GitHub Issue #$IssueNumber."
    }
    Write-Host "[PASS] Packet posted to canonical coordination Issue #$IssueNumber"
}
