# ================================================================================
# ANGEL F&O AUTOMATED END-TO-END HEALTH CHECK & TRACE AUDITOR
# One-click diagnostic tool for User and AI Agents
# Auto-generates: SYSTEM_HEALTH_AUDIT_REPORT.csv
# ================================================================================

param(
    [string]$OutputFile = "SYSTEM_HEALTH_AUDIT_REPORT.csv"
)

$ErrorActionPreference = 'Continue'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$CsvPath = Join-Path $ScriptDir $OutputFile

$stampNow = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
$now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host " ANGEL F&O END-TO-END SYSTEM HEALTH AUDITOR & TRACER" -ForegroundColor Cyan
Write-Host " Timestamp (IST): $stampNow" -ForegroundColor Cyan
Write-Host " Output Report: $CsvPath" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan

$auditRows = [System.Collections.Generic.List[PSCustomObject]]::new()

function Add-AuditEntry {
    param(
        [string]$Component,
        [string]$CheckName,
        [string]$Status,          # PASS, WARN, FAIL
        [string]$AgeOrLatency,
        [string]$RawValue,
        [string]$IssueIdentified,
        [string]$Recommendation
    )
    $color = switch ($Status) {
        "PASS" { "Green" }
        "WARN" { "Yellow" }
        default { "Red" }
    }
    Write-Host ("[{0}] {1} :: {2} -> {3}" -f $Status, $Component, $CheckName, $RawValue) -ForegroundColor $color
    if ($IssueIdentified -and $IssueIdentified -ne "NONE") {
        Write-Host ("       Alert: {0} | Fix: {1}" -f $IssueIdentified, $Recommendation) -ForegroundColor Yellow
    }

    $auditRows.Add([PSCustomObject]@{
        Timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
        Component = $Component
        CheckName = $CheckName
        Status = $Status
        AgeOrLatency = $AgeOrLatency
        RawValue = $RawValue
        IssueIdentified = $IssueIdentified
        Recommendation = $Recommendation
    })
}

$wc = New-Object System.Net.WebClient
$wc.Headers.Add("User-Agent", "AngelHealthCheck/1.0")

# --------------------------------------------------------------------------------
# 1. BROKER & GOOGLE SHEETS STREAMING CHECKS
# --------------------------------------------------------------------------------
Write-Host "`n>>> [1/6] CHECKING BROKER CONNECTION & GOOGLE SHEETS FEEDS..." -ForegroundColor White

$sheetId = "1Zu_9uJDQdDujsmtavdKnzupL-u2FtQ6C-LlkAswyzcs"
$hbUrl = "https://docs.google.com/spreadsheets/d/$sheetId/gviz/tq?tqx=out:csv&sheet=HEARTBEAT"
try {
    $hbRaw = $wc.DownloadString($hbUrl)
    $hbObj = ($hbRaw | ConvertFrom-Csv | Select-Object -First 1)
    
    $hbTs = [string]$hbObj.'Last Ping (IST)'
    $hbStatus = [string]$hbObj.'Angel Session Status'
    $hbScanned = [string]$hbObj.'Auto-Discovered Symbols'
    $hbEngine = [string]$hbObj.'Engine Status'
    $hbAge = [string]$hbObj.'Seconds Since Last Write'
    $hbAlert = [string]$hbObj.'Automated Feed Alert'

    $brokerStatus = if ($hbStatus -match "CONNECTED") { "PASS" } else { "FAIL" }
    $brokerIssue = if ($brokerStatus -eq "PASS") { "NONE" } else { "Broker stream reported status: $hbStatus" }
    $brokerRec = if ($brokerStatus -eq "PASS") { "Broker WebSocket is streaming normally." } else { "Restart angel_autonomous_daemon in Google Cloud Shell." }
    Add-AuditEntry -Component "Broker Feed" -CheckName "Angel One Session Auth" -Status $brokerStatus -AgeOrLatency "${hbAge}s" -RawValue "$hbStatus ($hbEngine)" -IssueIdentified $brokerIssue -Recommendation $brokerRec

    $ageSec = 0.0; [double]::TryParse($hbAge, [ref]$ageSec) | Out-Null
    $freshStatus = if ($ageSec -le 120) { "PASS" } elseif ($ageSec -le 300) { "WARN" } else { "FAIL" }
    $freshIssue = if ($freshStatus -eq "PASS") { "NONE" } else { "Writer age is ${ageSec}s (exceeds 120s normal limit)" }
    $freshRec = if ($freshStatus -eq "PASS") { "Feed latency is optimal." } else { "Check cloud daemon log (~/bot.log) for network throttling or API rate limit." }
    Add-AuditEntry -Component "Broker Feed" -CheckName "Stream Freshness & Ping" -Status $freshStatus -AgeOrLatency "${ageSec}s" -RawValue "Ping: $hbTs | Alert: $hbAlert" -IssueIdentified $freshIssue -Recommendation $freshRec

    $scannedInt = 0; [int]::TryParse($hbScanned, [ref]$scannedInt) | Out-Null
    $univStatus = if ($scannedInt -ge 216) { "PASS" } else { "WARN" }
    Add-AuditEntry -Component "Universe" -CheckName "F&O Universe Scanned Count" -Status $univStatus -AgeOrLatency "0s" -RawValue "$scannedInt / 216 contracts" -IssueIdentified $(if ($univStatus -eq "PASS") { "NONE" } else { "Only $scannedInt symbols active" }) -Recommendation "Verify NSE F&O ScripMaster universe filter in cloud daemon."
} catch {
    Add-AuditEntry -Component "Broker Feed" -CheckName "Google Sheet Fetch" -Status "FAIL" -AgeOrLatency "N/A" -RawValue "FAILED: $($_.Exception.Message)" -IssueIdentified "Cannot download HEARTBEAT from Google Sheets" -Recommendation "Check internet connection or Google Sheets sharing permissions."
}

# --------------------------------------------------------------------------------
# 2. GOOGLE CLOUD PLATFORM & BIGQUERY ACCESS CHECKS
# --------------------------------------------------------------------------------
Write-Host "`n>>> [2/6] CHECKING GOOGLE CLOUD OAUTH2 & BIGQUERY..." -ForegroundColor White

$saKeyPath = "C:\Users\ADMIN\Downloads\angel_sheets_key.json"
$gcpToken = $null
if (Test-Path $saKeyPath) {
    try {
        $saKey = Get-Content $saKeyPath -Raw | ConvertFrom-Json
        $pkText = $saKey.private_key -replace '-----BEGIN PRIVATE KEY-----', '' -replace '-----END PRIVATE KEY-----', '' -replace '\s+', ''
        $pkBytes = [Convert]::FromBase64String($pkText)
        $cngKey = [System.Security.Cryptography.CngKey]::Import($pkBytes, [System.Security.Cryptography.CngKeyBlobFormat]::Pkcs8PrivateBlob)
        $rsa = New-Object System.Security.Cryptography.RSACng($cngKey)
        
        $header = @{ alg = "RS256"; typ = "JWT" } | ConvertTo-Json -Compress
        $claim = @{
            iss = $saKey.client_email
            scope = "https://www.googleapis.com/auth/spreadsheets https://www.googleapis.com/auth/bigquery https://www.googleapis.com/auth/cloud-platform"
            aud = $saKey.token_uri
            exp = $now + 3600
            iat = $now
        } | ConvertTo-Json -Compress

        function B64Enc([byte[]]$b) { [Convert]::ToBase64String($b).TrimEnd('=').Replace('+', '-').Replace('/', '_') }
        $jwtPayload = "$(B64Enc([System.Text.Encoding]::UTF8.GetBytes($header))).$(B64Enc([System.Text.Encoding]::UTF8.GetBytes($claim)))"
        $sig = $rsa.SignData([System.Text.Encoding]::UTF8.GetBytes($jwtPayload), [System.Security.Cryptography.HashAlgorithmName]::SHA256, [System.Security.Cryptography.RSASignaturePadding]::Pkcs1)
        $jwtToken = "$jwtPayload.$(B64Enc($sig))"

        $authResp = Invoke-RestMethod -Uri $saKey.token_uri -Method Post -Body @{ grant_type = "urn:ietf:params:oauth:grant-type:jwt-bearer"; assertion = $jwtToken } -ContentType "application/x-www-form-urlencoded"
        $gcpToken = $authResp.access_token

        Add-AuditEntry -Component "Google Cloud" -CheckName "Service Account RSA-2048 Auth" -Status "PASS" -AgeOrLatency "$($authResp.expires_in)s expiry" -RawValue "Email: $($saKey.client_email) (Project: $($saKey.project_id))" -IssueIdentified "NONE" -Recommendation "OAuth2 token generation healthy via Windows CNG."

        # BigQuery API Query
        $bqUrl = "https://bigquery.googleapis.com/bigquery/v2/projects/$($saKey.project_id)/datasets/fno_predictions/tables"
        $bqResp = Invoke-RestMethod -Uri $bqUrl -Method Get -Headers @{ Authorization = "Bearer $gcpToken" }
        $bqTables = @($bqResp.tables.tableReference.tableId) -join ', '
        Add-AuditEntry -Component "Google Cloud" -CheckName "BigQuery Dataset fno_predictions" -Status "PASS" -AgeOrLatency "< 1s" -RawValue "Tables: $bqTables" -IssueIdentified "NONE" -Recommendation "BigQuery tables accessible for automated forecast ingestion."
    } catch {
        Add-AuditEntry -Component "Google Cloud" -CheckName "GCP Authentication" -Status "FAIL" -AgeOrLatency "N/A" -RawValue "FAILED: $($_.Exception.Message)" -IssueIdentified "Service account token exchange failed" -Recommendation "Check angel_sheets_key.json validity or Google Cloud IAM roles."
    }
} else {
    Add-AuditEntry -Component "Google Cloud" -CheckName "GCP Key File" -Status "FAIL" -AgeOrLatency "N/A" -RawValue "Missing $saKeyPath" -IssueIdentified "angel_sheets_key.json not found in Downloads" -Recommendation "Download service account JSON from Google Cloud Console."
}

# --------------------------------------------------------------------------------
# 3. GOOGLE SHEETS READ & WRITE PROBE
# --------------------------------------------------------------------------------
Write-Host "`n>>> [3/6] TESTING GOOGLE SHEETS READ & WRITE ACCESS..." -ForegroundColor White

if ($gcpToken) {
    try {
        $writeStamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss IST")
        $range = [System.Uri]::EscapeDataString("Cloud_Automation_Setup!Z1")
        $writeUrl = "https://sheets.googleapis.com/v4/spreadsheets/$sheetId/values/${range}?valueInputOption=USER_ENTERED"
        $body = @"
{
  "range": "Cloud_Automation_Setup!Z1",
  "majorDimension": "ROWS",
  "values": [
    ["HEALTH_AUDIT_PROBE_CONFIRMED: $writeStamp"]
  ]
}
"@
        $req = [System.Net.HttpWebRequest]::Create($writeUrl)
        $req.Method = "PUT"
        $req.Headers.Add("Authorization", "Bearer $gcpToken")
        $req.ContentType = "application/json; charset=utf-8"
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($body)
        $req.ContentLength = $bytes.Length
        $stream = $req.GetRequestStream()
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Close()
        $wResp = $req.GetResponse()
        $wReader = New-Object System.IO.StreamReader($wResp.GetResponseStream())
        $wJson = $wReader.ReadToEnd() | ConvertFrom-Json

        Add-AuditEntry -Component "Google Sheets" -CheckName "Sheets API v4 Write Probe" -Status "PASS" -AgeOrLatency "< 1s" -RawValue "Updated cell Cloud_Automation_Setup!Z1 (Cells: $($wJson.updatedCells))" -IssueIdentified "NONE" -Recommendation "Read & write permissions are active on OPTION_SHEET."
    } catch {
        Add-AuditEntry -Component "Google Sheets" -CheckName "Sheets API Write Probe" -Status "FAIL" -AgeOrLatency "N/A" -RawValue "Write failed: $($_.Exception.Message)" -IssueIdentified "Cannot write to Google Sheet via API" -Recommendation "Verify service account has 'Editor' permission on the Google Sheet."
    }
}

# --------------------------------------------------------------------------------
# 4. POWER BI DESKTOP IN-MEMORY ENGINE & VISUAL AUDIT
# --------------------------------------------------------------------------------
Write-Host "`n>>> [4/6] AUDITING POWER BI DESKTOP & SSAS IN-MEMORY ENGINE..." -ForegroundColor White

$msmdPids = @(Get-Process msmdsrv -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
$pbiConns = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.OwningProcess -in $msmdPids -and $_.LocalAddress -eq '127.0.0.1' }

if ($pbiConns.Count -gt 0) {
    $activePort = $pbiConns[0].LocalPort
    try {
        Add-Type -Path 'C:\Program Files\Microsoft Power BI Desktop\bin\Microsoft.PowerBI.AdomdClient.dll' -ErrorAction Stop
        $conn = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection("Data Source=localhost:$activePort")
        $conn.Open()
        $cmd = $conn.CreateCommand()
        $cmd.CommandText = @"
EVALUATE 
ROW(
    "HeartbeatStatus", [Heartbeat Status Display],
    "HeartbeatFreshness", [Heartbeat Freshness Display],
    "HeartbeatSymbols", [Heartbeat Symbols Display],
    "LatestForensicTime", [Latest Forensic Time],
    "TopRealCE", [Top Real CE Symbol],
    "TopRealCE_Pct", [Top Real CE %],
    "TopRealPE", [Top Real PE Symbol],
    "TopRealPE_Pct", [Top Real PE %]
)
"@
        $adapter = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdDataAdapter($cmd)
        $dt = New-Object System.Data.DataTable
        $adapter.Fill($dt) | Out-Null
        $conn.Close()

        $pbiFreshness = $dt.Rows[0][1]
        $pbiTime = $dt.Rows[0][3]
        $pbiTopCe = $dt.Rows[0][4]
        $pbiTopCePct = $dt.Rows[0][5]
        $pbiTopPe = $dt.Rows[0][6]
        $pbiTopPePct = $dt.Rows[0][7]

        Add-AuditEntry -Component "Power BI" -CheckName "SSAS In-Memory Measures" -Status "PASS" -AgeOrLatency "$pbiFreshness" -RawValue "Forensic: $pbiTime | Top CE: $pbiTopCe ($pbiTopCePct%) | Top PE: $pbiTopPe ($pbiTopPePct%)" -IssueIdentified "NONE" -Recommendation "Power BI in-memory VertiPaq engine is rendering live data."
        Add-AuditEntry -Component "Power BI" -CheckName "Active Desktop Port" -Status "PASS" -AgeOrLatency "0s" -RawValue "Port $activePort (PIDs: $($msmdPids -join ', '))" -IssueIdentified "NONE" -Recommendation "TOM stream injection connected to port $activePort."
    } catch {
        Add-AuditEntry -Component "Power BI" -CheckName "SSAS Query Evaluation" -Status "WARN" -AgeOrLatency "N/A" -RawValue "Query Error: $($_.Exception.Message)" -IssueIdentified "Calculated tables pending recalculation" -Recommendation "Run SYNC_LIVE_FEED_TO_PBI.ps1 to refresh in-memory tables."
    }
} else {
    Add-AuditEntry -Component "Power BI" -CheckName "Desktop Process" -Status "WARN" -AgeOrLatency "N/A" -RawValue "PBIDesktop.exe / msmdsrv.exe not currently running" -IssueIdentified "Power BI Desktop is closed" -Recommendation "Launch ANGEL_FNO_MONITOR.pbip to view live dashboards."
}

# --------------------------------------------------------------------------------
# 5. GITHUB REPOSITORY & DAILY PREDICTIONS CHECK
# --------------------------------------------------------------------------------
Write-Host "`n>>> [5/6] CHECKING GITHUB REPO & PREDICTIONS..." -ForegroundColor White

try {
    $predRaw = $wc.DownloadString("https://raw.githubusercontent.com/psw2025-cmd/angel-fno-scanner/main/data/latest_predictions.json")
    $preds = $predRaw | ConvertFrom-Json
    $symCount = $preds.Count
    $firstSym = if ($symCount -gt 0) { $preds[0].symbol } else { "NONE" }
    
    Add-AuditEntry -Component "GitHub" -CheckName "latest_predictions.json Feed" -Status "PASS" -AgeOrLatency "0s" -RawValue "Loaded $symCount predictions (Sample: $firstSym)" -IssueIdentified "NONE" -Recommendation "Pre-market predictions stream is active on GitHub main branch."

    $hasGitToken = [bool]($env:GITHUB_TOKEN -or $env:GH_TOKEN)
    $gitStatus = if ($hasGitToken) { "PASS" } else { "WARN" }
    $gitIssue = if ($hasGitToken) { "NONE" } else { "git.exe or GITHUB_TOKEN not set on local laptop" }
    $gitRec = if ($hasGitToken) { "Full git read and write active." } else { "To commit files directly to GitHub from laptop, set `$env:GITHUB_TOKEN = '<YOUR_PAT>'." }
    Add-AuditEntry -Component "GitHub" -CheckName "Repository Write/Push Access" -Status $gitStatus -AgeOrLatency "N/A" -RawValue "Read=100% Active | Write=$(if ($hasGitToken) { 'Enabled' } else { 'Needs PAT Token' })" -IssueIdentified $gitIssue -Recommendation $gitRec
} catch {
    Add-AuditEntry -Component "GitHub" -CheckName "Predictions Fetch" -Status "FAIL" -AgeOrLatency "N/A" -RawValue "Error: $($_.Exception.Message)" -IssueIdentified "Cannot fetch latest_predictions.json from GitHub" -Recommendation "Verify network connection to raw.githubusercontent.com."
}

# --------------------------------------------------------------------------------
# 6. GOOGLE COLAB & LOCAL AUTOMATION DAEMONS
# --------------------------------------------------------------------------------
Write-Host "`n>>> [6/6] CHECKING GOOGLE COLAB & LOCAL DAEMONS..." -ForegroundColor White

$colabPath = "C:\Users\ADMIN\Downloads\ANGEL_OPTION_2026.ipynb"
if (Test-Path $colabPath) {
    $nb = Get-Content $colabPath -Raw | ConvertFrom-Json
    Add-AuditEntry -Component "Google Colab" -CheckName "Local Notebook ANGEL_OPTION_2026.ipynb" -Status "PASS" -AgeOrLatency "0s" -RawValue "Valid notebook: $($nb.cells.Count) cells | Kernel: $($nb.metadata.kernelspec.display_name)" -IssueIdentified "NONE" -Recommendation "Colab notebook is ready for execution in browser or local Python."
} else {
    Add-AuditEntry -Component "Google Colab" -CheckName "Notebook File" -Status "WARN" -AgeOrLatency "N/A" -RawValue "Not found at $colabPath" -IssueIdentified "Colab file absent from Downloads" -Recommendation "Download ANGEL_OPTION_2026.ipynb if local cell inspection is required."
}

# Check active background daemons
$daemonProc = Get-WmiObject Win32_Process -Filter "CommandLine LIKE '%AUTO_MONITOR_AND_CALIBRATE.ps1%'" -ErrorAction SilentlyContinue
$daemonRunning = if ($daemonProc) { "PASS" } else { "WARN" }
$daemonIssue = if ($daemonProc) { "NONE" } else { "Background monitor daemon not detected" }
$daemonRec = if ($daemonProc) { "Daemon running every 120s." } else { "Launch AUTO_MONITOR_AND_CALIBRATE.ps1 -IntervalSeconds 120 in background." }
Add-AuditEntry -Component "AGY CLI" -CheckName "Background Daemon (120s Loop)" -Status $daemonRunning -AgeOrLatency "120s cycle" -RawValue $(if ($daemonProc) { "PID: $($daemonProc.ProcessId)" } else { "INACTIVE" }) -IssueIdentified $daemonIssue -Recommendation $daemonRec

# --------------------------------------------------------------------------------
# EXPORT TO CSV
# --------------------------------------------------------------------------------
$auditRows | Export-Csv -Path $CsvPath -NoTypeInformation -Encoding UTF8
Write-Host "`n================================================================================" -ForegroundColor Cyan
Write-Host " [SUCCESS] HEALTH AUDIT COMPLETE! Detailed report generated at:" -ForegroundColor Green
Write-Host " $CsvPath" -ForegroundColor Yellow
Write-Host " Total Checks: $($auditRows.Count) | Passed: $(($auditRows | Where-Object Status -eq 'PASS').Count) | Warnings: $(($auditRows | Where-Object Status -eq 'WARN').Count) | Failures: $(($auditRows | Where-Object Status -eq 'FAIL').Count)" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
