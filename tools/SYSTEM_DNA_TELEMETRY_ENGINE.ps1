# ================================================================================
# ANGEL F&O SYSTEM DNA TELEMETRY ENGINE & QUANTUM AUDITOR
# Probes every organ, artery, cell, and node in the entire ecosystem at micro-level.
# Generates: system_live_telemetry.json (for live animated ECG/MRI dashboard)
# Generates: SYSTEM_LIVE_DNA_AUDIT.csv (continuous micro-trace log)
# ================================================================================

param(
    [int]$LoopCount = 1,
    [int]$IntervalSeconds = 10,
    [switch]$Continuous
)

$ErrorActionPreference = 'Continue'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$JsonPath = Join-Path $ScriptDir "system_live_telemetry.json"
$CsvPath = Join-Path $ScriptDir "SYSTEM_LIVE_DNA_AUDIT.csv"

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host " ANGEL F&O QUANTUM DNA TELEMETRY ENGINE INITIALIZING" -ForegroundColor Cyan
Write-Host " Telemetry JSON: $JsonPath" -ForegroundColor Cyan
Write-Host " Telemetry CSV : $CsvPath" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan

function Run-SingleTelemetryCycle {
    $cycleStart = Get-Date
    $stampIST = $cycleStart.ToString("yyyy-MM-dd HH:mm:ss")
    $nowEpoch = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()

    $nodes = @{}
    $arteries = @()
    $auditLogs = [System.Collections.Generic.List[PSCustomObject]]::new()
    $wc = New-Object System.Net.WebClient
    $wc.Headers.Add("User-Agent", "AngelDnaTelemetry/2.0")

    # Helper function
    function Record-NodeTrace {
        param(
            [string]$NodeId,
            [string]$NodeName,
            [string]$Category,
            [string]$Status,          # HEALTHY, WARNING, CRITICAL
            [double]$HealthScore,      # 0 to 100
            [string]$LatencyMs,
            [hashtable]$MicroCells,
            [string]$Diagnostics
        )
        $nodes[$NodeId] = @{
            id = $NodeId
            name = $NodeName
            category = $Category
            status = $Status
            health_score = $HealthScore
            latency = $LatencyMs
            micro_cells = $MicroCells
            diagnostics = $Diagnostics
            last_checked = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
        }

        $auditLogs.Add([PSCustomObject]@{
            Timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
            NodeId = $NodeId
            NodeName = $NodeName
            Status = $Status
            HealthScore = $HealthScore
            Latency = $LatencyMs
            Diagnostics = $Diagnostics
            MicroMetrics = ($MicroCells.GetEnumerator() | ForEach-Object { "$($_.Key)=$($_.Value)" }) -join '; '
        })
    }

    # ----------------------------------------------------------------------------
    # 1. ORGAN 1: ANGEL ONE BROKER (The Heart)
    # ----------------------------------------------------------------------------
    $sheetId = "1Zu_9uJDQdDujsmtavdKnzupL-u2FtQ6C-LlkAswyzcs"
    $hbTimer = [System.Diagnostics.Stopwatch]::StartNew()
    $hbStatus = "CRITICAL"; $hbHealth = 0; $hbDiag = ""; $hbCells = @{}

    try {
        $hbRaw = $wc.DownloadString("https://docs.google.com/spreadsheets/d/$sheetId/gviz/tq?tqx=out:csv&sheet=HEARTBEAT&range=A1:F2")
        $hbTimer.Stop()
        $hbObj = ($hbRaw | ConvertFrom-Csv | Select-Object -First 1)
        
        $pTs = [string]$hbObj.'Last Ping (IST)'
        $pAuth = [string]$hbObj.'Angel Session Status'
        $pScanned = [string]$hbObj.'Auto-Discovered Symbols'
        $pEngine = [string]$hbObj.'Engine Status'
        $pAge = [string]$hbObj.'Seconds Since Last Write'
        $pAlert = [string]$hbObj.'Automated Feed Alert'

        $ageSec = 0.0; [double]::TryParse($pAge, [ref]$ageSec) | Out-Null
        $symCount = 0; [int]::TryParse($pScanned, [ref]$symCount) | Out-Null

        $hbCells = @{
            "HEARTBEAT!A2 [Last Ping]" = $pTs
            "HEARTBEAT!B2 [Session Auth]" = $pAuth
            "HEARTBEAT!C2 [Discovered Symbols]" = "$symCount / 216"
            "HEARTBEAT!D2 [Engine Cycle]" = $pEngine
            "HEARTBEAT!E2 [Writer Age]" = "${ageSec}s"
            "HEARTBEAT!F2 [Feed Alert]" = $pAlert
        }

        if ($pAuth -match "CONNECTED" -and $ageSec -le 120 -and $symCount -ge 216) {
            $hbStatus = "HEALTHY"
            $hbHealth = 100.0
            $hbDiag = "Broker WebSocket streaming optimally ($symCount symbols, age ${ageSec}s)."
        } elseif ($pAuth -match "CONNECTED" -and $ageSec -le 300) {
            $hbStatus = "WARNING"
            $hbHealth = 75.0
            $hbDiag = "Broker stream active but writer latency elevated (${ageSec}s)."
        } else {
            $hbStatus = "CRITICAL"
            $hbHealth = 25.0
            $hbDiag = "Broker stream degraded: Auth=$pAuth, Age=${ageSec}s."
        }
    } catch {
        $hbTimer.Stop()
        $hbDiag = "Failed to reach broker heartbeat stream: $($_.Exception.Message)"
    }
    Record-NodeTrace -NodeId "broker_heart" -NodeName "Angel One Broker Engine" -Category "Source" -Status $hbStatus -HealthScore $hbHealth -LatencyMs "$($hbTimer.ElapsedMilliseconds)ms" -MicroCells $hbCells -Diagnostics $hbDiag

    # ----------------------------------------------------------------------------
    # 2. ORGAN 2: GOOGLE SHEETS LIVE REPOSITORY (Circulatory System)
    # ----------------------------------------------------------------------------
    $gsTimer = [System.Diagnostics.Stopwatch]::StartNew()
    $gsStatus = "CRITICAL"; $gsHealth = 0; $gsDiag = ""; $gsCells = @{}
    try {
        $flRaw = $wc.DownloadString("https://docs.google.com/spreadsheets/d/$sheetId/gviz/tq?tqx=out:csv&sheet=FORENSIC_LIVE&range=A1:E3")
        $flItems = @($flRaw | ConvertFrom-Csv)
        $ceRaw = $wc.DownloadString("https://docs.google.com/spreadsheets/d/$sheetId/gviz/tq?tqx=out:csv&sheet=CE_PE_RANK&range=A1:D3")
        $ceItems = @($ceRaw | ConvertFrom-Csv)
        $gsTimer.Stop()

        $flFirst = $flItems[0]
        $ceFirst = $ceItems[0]

        $gsCells = @{
            "FORENSIC_LIVE!A2 [Time]" = [string]$flFirst.'Timestamp (IST)'
            "FORENSIC_LIVE!B2 [Symbol]" = [string]$flFirst.'Symbol'
            "FORENSIC_LIVE!D2 [Fut LTP]" = [string]$flFirst.'Fut LTP'
            "CE_PE_RANK!A2 [Rank Time]" = [string]$ceFirst.psobject.Properties[0].Value
            "CE_PE_RANK!C2 [Symbol]" = [string]$ceFirst.psobject.Properties[2].Value
            "CE_PE_RANK!D2 [LTP]" = [string]$ceFirst.psobject.Properties[3].Value
        }

        if ($flItems.Count -ge 1 -and $ceItems.Count -ge 1) {
            $gsStatus = "HEALTHY"
            $gsHealth = 100.0
            $gsDiag = "Google Sheets tabs (HEARTBEAT, FORENSIC_LIVE, CE_PE_RANK) fully responsive."
        } else {
            $gsStatus = "WARNING"
            $gsHealth = 60.0
            $gsDiag = "Google Sheets returned partial rows."
        }
    } catch {
        $gsTimer.Stop()
        $gsDiag = "Google Sheets stream fetch error: $($_.Exception.Message)"
    }
    Record-NodeTrace -NodeId "google_sheets_live" -NodeName "Google Sheets (OPTION_SHEET)" -Category "Streaming" -Status $gsStatus -HealthScore $gsHealth -LatencyMs "$($gsTimer.ElapsedMilliseconds)ms" -MicroCells $gsCells -Diagnostics $gsDiag

    # ----------------------------------------------------------------------------
    # 3. ORGAN 3: GOOGLE CLOUD BIGQUERY & SERVICE ACCOUNT (The Brain)
    # ----------------------------------------------------------------------------
    $gcpTimer = [System.Diagnostics.Stopwatch]::StartNew()
    $gcpStatus = "CRITICAL"; $gcpHealth = 0; $gcpDiag = ""; $gcpCells = @{}
    $keyPath = "C:\Users\ADMIN\Downloads\angel_sheets_key.json"

    if (Test-Path $keyPath) {
        try {
            $saKey = Get-Content $keyPath -Raw | ConvertFrom-Json
            $pkText = $saKey.private_key -replace '-----BEGIN PRIVATE KEY-----', '' -replace '-----END PRIVATE KEY-----', '' -replace '\s+', ''
            $pkBytes = [Convert]::FromBase64String($pkText)
            $cngKey = [System.Security.Cryptography.CngKey]::Import($pkBytes, [System.Security.Cryptography.CngKeyBlobFormat]::Pkcs8PrivateBlob)
            $rsa = New-Object System.Security.Cryptography.RSACng($cngKey)
            
            $header = @{ alg = "RS256"; typ = "JWT" } | ConvertTo-Json -Compress
            $claim = @{
                iss = $saKey.client_email
                scope = "https://www.googleapis.com/auth/spreadsheets https://www.googleapis.com/auth/bigquery"
                aud = $saKey.token_uri
                exp = $nowEpoch + 3600
                iat = $nowEpoch
            } | ConvertTo-Json -Compress

            function B64Url([byte[]]$b) { [Convert]::ToBase64String($b).TrimEnd('=').Replace('+', '-').Replace('/', '_') }
            $jwtPayload = "$(B64Url([System.Text.Encoding]::UTF8.GetBytes($header))).$(B64Url([System.Text.Encoding]::UTF8.GetBytes($claim)))"
            $sig = $rsa.SignData([System.Text.Encoding]::UTF8.GetBytes($jwtPayload), [System.Security.Cryptography.HashAlgorithmName]::SHA256, [System.Security.Cryptography.RSASignaturePadding]::Pkcs1)
            $jwt = "$jwtPayload.$(B64Url($sig))"

            $authResp = Invoke-RestMethod -Uri $saKey.token_uri -Method Post -Body @{ grant_type = "urn:ietf:params:oauth:grant-type:jwt-bearer"; assertion = $jwt } -ContentType "application/x-www-form-urlencoded"
            $gcpToken = $authResp.access_token

            # Query BigQuery tables
            $bqUrl = "https://bigquery.googleapis.com/bigquery/v2/projects/$($saKey.project_id)/datasets/fno_predictions/tables"
            $bqResp = Invoke-RestMethod -Uri $bqUrl -Method Get -Headers @{ Authorization = "Bearer $gcpToken" }
            $bqTables = @($bqResp.tables.tableReference.tableId)
            $gcpTimer.Stop()

            $gcpCells = @{
                "GCP Project" = [string]$saKey.project_id
                "Client Email" = [string]$saKey.client_email
                "OAuth2 Token" = "Active (Bearer)"
                "BigQuery Tables" = "$($bqTables.Count) tables ($($bqTables -join ', '))"
            }

            if ($bqTables.Count -ge 4) {
                $gcpStatus = "HEALTHY"
                $gcpHealth = 100.0
                $gcpDiag = "BigQuery dataset fno_predictions healthy with 4 active tables."
            } else {
                $gcpStatus = "WARNING"
                $gcpHealth = 70.0
                $gcpDiag = "BigQuery accessible but expected 4 tables, found $($bqTables.Count)."
            }
        } catch {
            $gcpTimer.Stop()
            $gcpDiag = "GCP BigQuery authentication error: $($_.Exception.Message)"
        }
    } else {
        $gcpTimer.Stop()
        $gcpDiag = "Service account key missing from Downloads folder."
    }
    Record-NodeTrace -NodeId "gcp_bigquery" -NodeName "Google Cloud BigQuery" -Category "Data Warehouse" -Status $gcpStatus -HealthScore $gcpHealth -LatencyMs "$($gcpTimer.ElapsedMilliseconds)ms" -MicroCells $gcpCells -Diagnostics $gcpDiag

    # ----------------------------------------------------------------------------
    # 4. ORGAN 4: GITHUB REPO (The Genetic Vault)
    # ----------------------------------------------------------------------------
    $ghTimer = [System.Diagnostics.Stopwatch]::StartNew()
    $ghStatus = "CRITICAL"; $ghHealth = 0; $ghDiag = ""; $ghCells = @{}
    try {
        $predRaw = $wc.DownloadString("https://raw.githubusercontent.com/psw2025-cmd/angel-fno-scanner/main/data/latest_predictions.json")
        $preds = $predRaw | ConvertFrom-Json
        $ghTimer.Stop()

        $pCount = $preds.Count
        $pSample = if ($pCount -gt 0) { $preds[0].symbol } else { "NONE" }
        $hasToken = [bool]($env:GITHUB_TOKEN -or $env:GH_TOKEN)

        $ghCells = @{
            "Repo" = "psw2025-cmd/angel-fno-scanner"
            "Predictions Count" = "$pCount symbols"
            "Sample Prediction" = $pSample
            "Write Capability" = if ($hasToken) { "Full (PAT configured)" } else { "Read-Only (PAT optional)" }
        }

        if ($pCount -ge 100) {
            $ghStatus = "HEALTHY"
            $ghHealth = if ($hasToken) { 100.0 } else { 92.0 }
            $ghDiag = "GitHub predictions branch verified ($pCount symbols)."
        } else {
            $ghStatus = "WARNING"
            $ghHealth = 65.0
            $ghDiag = "Predictions file has low symbol count ($pCount)."
        }
    } catch {
        $ghTimer.Stop()
        $ghDiag = "GitHub predictions fetch failed: $($_.Exception.Message)"
    }
    Record-NodeTrace -NodeId "github_repo" -NodeName "GitHub Predictions Engine" -Category "Model Repository" -Status $ghStatus -HealthScore $ghHealth -LatencyMs "$($ghTimer.ElapsedMilliseconds)ms" -MicroCells $ghCells -Diagnostics $ghDiag

    # ----------------------------------------------------------------------------
    # 5. ORGAN 5: POWER BI DESKTOP TABULAR ENGINE (The Action Muscle)
    # ----------------------------------------------------------------------------
    $pbiTimer = [System.Diagnostics.Stopwatch]::StartNew()
    $pbiStatus = "CRITICAL"; $pbiHealth = 0; $pbiDiag = ""; $pbiCells = @{}

    $msmdPids = @(Get-Process msmdsrv -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
    $pbiConns = @(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.OwningProcess -in $msmdPids -and $_.LocalAddress -eq '127.0.0.1' })

    if ($pbiConns.Count -gt 0) {
        $port = $pbiConns[0].LocalPort
        try {
            Add-Type -Path 'C:\Program Files\Microsoft Power BI Desktop\bin\Microsoft.PowerBI.AdomdClient.dll' -ErrorAction Stop
            $conn = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection("Data Source=localhost:$port")
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
            $pbiTimer.Stop()

            $mFresh = [string]$dt.Rows[0][1]
            $mTime = [string]$dt.Rows[0][3]
            $mTopCe = [string]$dt.Rows[0][4]
            $mTopCePct = [string]$dt.Rows[0][5]
            $mTopPe = [string]$dt.Rows[0][6]
            $mTopPePct = [string]$dt.Rows[0][7]

            $pbiCells = @{
                "Active SSAS Port" = "Port $port (PID: $($msmdPids -join ', '))"
                "Writer Freshness" = $mFresh
                "Latest Forensic Time" = $mTime
                "Top Real CE" = "$mTopCe (+$mTopCePct%)"
                "Top Real PE" = "$mTopPe (+$mTopPePct%)"
            }

            if ($mFresh -match "0 sec") {
                $pbiStatus = "HEALTHY"
                $pbiHealth = 100.0
                $pbiDiag = "Power BI in-memory VertiPaq engine 100% synchronized (0s writer age)."
            } elseif ($mFresh -match "sec") {
                $pbiStatus = "HEALTHY"
                $pbiHealth = 95.0
                $pbiDiag = "Power BI rendered live data ($mFresh)."
            } else {
                $pbiStatus = "WARNING"
                $pbiHealth = 70.0
                $pbiDiag = "Power BI active but measures pending fresh stream injection."
            }
        } catch {
            $pbiTimer.Stop()
            $pbiStatus = "WARNING"
            $pbiHealth = 50.0
            $pbiDiag = "SSAS running on port $port but DAX query failed: $($_.Exception.Message)"
        }
    } else {
        $pbiTimer.Stop()
        $pbiDiag = "Power BI Desktop is closed (msmdsrv.exe not found)."
    }
    Record-NodeTrace -NodeId "powerbi_engine" -NodeName "Power BI Desktop (SSAS Engine)" -Category "Visualization" -Status $pbiStatus -HealthScore $pbiHealth -LatencyMs "$($pbiTimer.ElapsedMilliseconds)ms" -MicroCells $pbiCells -Diagnostics $pbiDiag

    # ----------------------------------------------------------------------------
    # 6. ORGAN 6: AGY CLI AUTONOMOUS DAEMON (Nervous System)
    # ----------------------------------------------------------------------------
    $agyTimer = [System.Diagnostics.Stopwatch]::StartNew()
    $daemonProc = Get-WmiObject Win32_Process -Filter "CommandLine LIKE '%AUTO_MONITOR_AND_CALIBRATE.ps1%'" -ErrorAction SilentlyContinue
    $agyTimer.Stop()

    $agyCells = @{
        "Daemon Status" = if ($daemonProc) { "RUNNING (Loop active)" } else { "STOPPED" }
        "Daemon PID" = if ($daemonProc) { [string]$daemonProc.ProcessId } else { "N/A" }
        "Interval" = "120 seconds"
        "Injection Method" = "Direct TOM Live Sync"
    }

    if ($daemonProc) {
        $agyStatus = "HEALTHY"
        $agyHealth = 100.0
        $agyDiag = "Autonomous 120s calibration daemon running continuously (PID: $($daemonProc.ProcessId))."
    } else {
        $agyStatus = "WARNING"
        $agyHealth = 40.0
        $agyDiag = "Autonomous daemon not detected in background."
    }
    Record-NodeTrace -NodeId "agy_daemon" -NodeName "AGY CLI Autonomous Daemon" -Category "Automation" -Status $agyStatus -HealthScore $agyHealth -LatencyMs "$($agyTimer.ElapsedMilliseconds)ms" -MicroCells $agyCells -Diagnostics $agyDiag

    # ----------------------------------------------------------------------------
    # ARTERIES (Flow Connections Between Nodes)
    # ----------------------------------------------------------------------------
    $arteriesList = [System.Collections.Generic.List[hashtable]]::new()
    function Add-Artery {
        param([string]$From, [string]$To, [string]$Label, [string]$FlowState, [double]$RatePerMin)
        $arteriesList.Add(@{
            source = $From
            target = $To
            label = $Label
            state = $FlowState    # FLOWING, SLOW, BLOCKED
            rate = $RatePerMin
        })
    }

    $b2sFlow = if ($nodes["broker_heart"].status -eq "HEALTHY" -and $nodes["google_sheets_live"].status -eq "HEALTHY") { "FLOWING" } else { "SLOW" }
    Add-Artery -From "broker_heart" -To "google_sheets_live" -Label "Angel SmartAPI WebSocket -> Google Sheets" -FlowState $b2sFlow -RatePerMin 4.0

    $s2pFlow = if ($nodes["google_sheets_live"].status -eq "HEALTHY" -and $nodes["powerbi_engine"].status -eq "HEALTHY") { "FLOWING" } else { "BLOCKED" }
    Add-Artery -From "google_sheets_live" -To "powerbi_engine" -Label "Sheets -> Power BI VertiPaq (TOM Direct)" -FlowState $s2pFlow -RatePerMin 0.5

    $gh2pFlow = if ($nodes["github_repo"].status -eq "HEALTHY") { "FLOWING" } else { "SLOW" }
    Add-Artery -From "github_repo" -To "powerbi_engine" -Label "GitHub Predictions -> Power BI Horizon" -FlowState $gh2pFlow -RatePerMin 0.1

    $gcpFlow = if ($nodes["gcp_bigquery"].status -eq "HEALTHY") { "FLOWING" } else { "SLOW" }
    Add-Artery -From "gcp_bigquery" -To "powerbi_engine" -Label "BigQuery Warehousing -> Power BI DirectQuery" -FlowState $gcpFlow -RatePerMin 0.2

    $agyFlow = if ($nodes["agy_daemon"].status -eq "HEALTHY") { "FLOWING" } else { "BLOCKED" }
    Add-Artery -From "agy_daemon" -To "powerbi_engine" -Label "AGY Daemon Orchestration -> Power BI Model" -FlowState $agyFlow -RatePerMin 0.5

    # Overall System ECG Rate (Heartbeat BPM)
    $healthScores = @($nodes.Values | ForEach-Object { [double]$_["health_score"] })
    $systemHealthAvg = if ($healthScores.Count -gt 0) { ($healthScores | Measure-Object -Average).Average } else { 0.0 }
    $ecgBpm = [int](60 + ($systemHealthAvg * 0.2))   # Healthy ~ 80 BPM
    $systemState = if ($systemHealthAvg -ge 90) { "OPTIMAL (BLOOD FLOW NORMAL)" } elseif ($systemHealthAvg -ge 70) { "ATTENTION (MILD RESISTANCE)" } else { "ARRHYTHMIA (CRITICAL FAULT DETECTED)" }

    # Assemble JSON Telemetry Packet
    $telemetryData = @{
        system_name = "ANGEL ONE F&O QUANTUM DNA & CIRCULATION ENGINE"
        generated_at = $stampIST
        overall_health_score = [Math]::Round($systemHealthAvg, 1)
        system_state = $systemState
        ecg_bpm = $ecgBpm
        active_nodes_count = $nodes.Count
        healthy_nodes_count = @($nodes.Values | Where-Object { $_["status"] -eq "HEALTHY" }).Count
        nodes = $nodes
        arteries = $arteriesList
    }

    $jsonContent = $telemetryData | ConvertTo-Json -Depth 6
    $jsonContent | Set-Content -Path $JsonPath -Encoding UTF8
    $repoRoot = Split-Path -Parent $ScriptDir
    if (Test-Path $repoRoot) {
        $jsonContent | Set-Content -Path (Join-Path $repoRoot "system_live_telemetry.json") -Encoding UTF8 -ErrorAction SilentlyContinue
        $monDir = Join-Path $repoRoot "operator\monitor"
        if (Test-Path $monDir) {
            $jsonContent | Set-Content -Path (Join-Path $monDir "system_live_telemetry.json") -Encoding UTF8 -ErrorAction SilentlyContinue
        }
    }

    # Append to CSV Audit Log with Resilient Sharing Retry
    $csvWritten = $false
    for ($retries = 0; $retries -lt 5 -and -not $csvWritten; $retries++) {
        try {
            $csvExists = Test-Path $CsvPath
            if (-not $csvExists) {
                $auditLogs | Export-Csv -Path $CsvPath -NoTypeInformation -Encoding UTF8 -ErrorAction Stop
            } else {
                $auditLogs | Export-Csv -Path $CsvPath -NoTypeInformation -Encoding UTF8 -Append -ErrorAction Stop
            }
            $csvWritten = $true
        } catch {
            Start-Sleep -Milliseconds 250
        }
    }

    Write-Host "[$stampIST] Telemetry Cycle Finished | Health: $([Math]::Round($systemHealthAvg, 1))% | ECG: ${ecgBpm} BPM | State: $systemState" -ForegroundColor $(if ($systemHealthAvg -ge 90) { "Green" } else { "Yellow" })
}

if ($Continuous) {
    Write-Host "Running continuous telemetry loop (Interval: ${IntervalSeconds}s)..." -ForegroundColor Yellow
    while ($true) {
        Run-SingleTelemetryCycle
        Start-Sleep -Seconds $IntervalSeconds
    }
} else {
    for ($i = 0; $i -lt $LoopCount; $i++) {
        Run-SingleTelemetryCycle
        if ($i -lt ($LoopCount - 1)) { Start-Sleep -Seconds $IntervalSeconds }
    }
}
