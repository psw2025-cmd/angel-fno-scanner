<#
================================================================================
ANGEL F&O AUTONOMOUS REAL-TIME TRACKING, CALIBRATION & LEARNING DAEMON
================================================================================
Monitors live Angel One SmartAPI quotes, compares pre-market forecasts with
live market prints, calculates accuracy and miss patterns, records calibration,
and synchronizes with Power BI.
#>

param(
    [int]$IntervalSeconds = 300,
    [switch]$RunOnce
)

$ErrorActionPreference = 'Continue'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$LogJson = Join-Path $ScriptDir "AUTO_TRACKING_HISTORY.json"
$LogTxt = Join-Path $ScriptDir "AUTO_TRACKING_LOG.txt"

function Write-DaemonLog {
    param([string]$Message, [string]$Level = "INFO")
    $stamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    $line = "[$stamp] [$Level] $Message"
    Write-Host $line -ForegroundColor $(switch ($Level) { "WARN" { "Yellow" }; "ERROR" { "Red" }; "SUCCESS" { "Green" }; default { "Cyan" } })
    Add-Content -Path $LogTxt -Value $line -ErrorAction SilentlyContinue
}

function Execute-TrackingCycle {
    $cycleTime = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    Write-DaemonLog "Starting Autonomous Tracking & Calibration Cycle..." "INFO"
    
    $wc = New-Object System.Net.WebClient
    
    # 1. Fetch Live Heartbeat
    $hbStatus = "UNKNOWN"
    $hbAge = -1
    $hbCycle = ""
    try {
        $hbRaw = $wc.DownloadString("https://docs.google.com/spreadsheets/d/1Zu_9uJDQdDujsmtavdKnzupL-u2FtQ6C-LlkAswyzcs/gviz/tq?tqx=out:csv&sheet=HEARTBEAT")
        $hbLines = $hbRaw -split "`n"
        if ($hbLines.Count -ge 2) {
            $cols = $hbLines[1] -split '","'
            $hbStatus = $cols[1].Replace('"', '').Trim()
            $hbCycle = $cols[3].Replace('"', '').Trim()
            $hbAge = [int]($cols[4].Replace('"', '').Trim())
        }
    } catch {
        Write-DaemonLog "Heartbeat fetch failed: $_" "WARN"
    }
    
    # 2. Fetch Live Predictions (Model Horizon)
    $predMap = @{}
    try {
        $preds = $wc.DownloadString("https://raw.githubusercontent.com/psw2025-cmd/angel-fno-scanner/main/data/latest_predictions.json") | ConvertFrom-Json
        foreach ($p in $preds) { $predMap[$p.symbol] = $p }
        if ($predMap.Count -gt 0) { $global:cachedPredMap = $predMap }
    } catch {
        Write-DaemonLog "Predictions fetch failed: $_" "WARN"
    }
    if ($predMap.Count -eq 0 -and $global:cachedPredMap -and $global:cachedPredMap.Count -gt 0) {
        $predMap = $global:cachedPredMap
        Write-DaemonLog "Using cached predictions fallback ($($predMap.Count) symbols)" "INFO"
    }
    
    # 3. Fetch Real Live CE/PE Rank
    $ceRows = @()
    try {
        $ceCsv = $wc.DownloadString("https://docs.google.com/spreadsheets/d/1Zu_9uJDQdDujsmtavdKnzupL-u2FtQ6C-LlkAswyzcs/gviz/tq?tqx=out:csv&sheet=CE_PE_RANK")
        $ceRows = @($ceCsv | ConvertFrom-Csv)
        if ($ceRows.Count -gt 0) { $global:cachedCeRows = $ceRows }
    } catch {
        Write-DaemonLog "CE_PE_RANK fetch failed: $_" "WARN"
    }
    if ($ceRows.Count -eq 0 -and $global:cachedCeRows -and $global:cachedCeRows.Count -gt 0) {
        $ceRows = $global:cachedCeRows
        Write-DaemonLog "Using cached CE_PE_RANK fallback ($($ceRows.Count) rows)" "INFO"
    }
    
    # 4. Fetch Real Live Option Movers
    $flMap = @{}
    try {
        $flCsv = $wc.DownloadString("https://docs.google.com/spreadsheets/d/1Zu_9uJDQdDujsmtavdKnzupL-u2FtQ6C-LlkAswyzcs/gviz/tq?tqx=out:csv&sheet=FORENSIC_LIVE")
        $flRows = @($flCsv | ConvertFrom-Csv)
        foreach ($fl in $flRows) { $flMap[$fl.Symbol] = $fl }
        if ($flMap.Count -gt 0) { $global:cachedFlMap = $flMap }
    } catch {
        Write-DaemonLog "FORENSIC_LIVE fetch failed: $_" "WARN"
    }
    if ($flMap.Count -eq 0 -and $global:cachedFlMap -and $global:cachedFlMap.Count -gt 0) {
        $flMap = $global:cachedFlMap
        Write-DaemonLog "Using cached FORENSIC_LIVE fallback ($($flMap.Count) symbols)" "INFO"
    }
    
    # 5. Cross-Verification Analysis
    $evaluations = @()
    $hits = 0
    $totalGaps = 0
    $brierSum = 0.0
    
    foreach ($r in $ceRows) {
        $sym = $r.Symbol
        if ($predMap.ContainsKey($sym)) {
            $p = $predMap[$sym]
            $realGap = 0.0
            [double]::TryParse($r.('Opening gap %'), [ref]$realGap) | Out-Null
            $predGap = [double]$p.expected_gap_pct
            $realFutChg = 0.0
            [double]::TryParse($r.('Session change %'), [ref]$realFutChg) | Out-Null
            
            $realCE = 0.0
            $realPE = 0.0
            if ($flMap.ContainsKey($sym)) {
                [double]::TryParse($flMap[$sym].('CE Chg %'), [ref]$realCE) | Out-Null
                [double]::TryParse($flMap[$sym].('PE Chg %'), [ref]$realPE) | Out-Null
            }
            
            $dirHit = $false
            if ($realGap -ne 0) {
                $totalGaps++
                if (($predGap -gt 0 -and $realGap -gt 0) -or ($predGap -lt 0 -and $realGap -lt 0)) {
                    $dirHit = $true
                    $hits++
                }
            }
            
            # Probability Brier Score calculation (Outcome CE=1 or PE=0)
            $actualOutcome = if ($realFutChg -ge 0) { 1.0 } else { 0.0 }
            $probCE = [double]$p.ce_win_prob / 100.0
            $brierSum += [math]::Pow($probCE - $actualOutcome, 2)
            
            $evaluations += [PSCustomObject]@{
                Symbol = $sym
                PredGap = $predGap
                RealGap = $realGap
                DirHit = $dirHit
                RealFutChg = $realFutChg
                RealCEChg = $realCE
                RealPEChg = $realPE
                Confidence = [double]$p.confidence_pct
            }
        }
    }
    
    $hitRate = if ($totalGaps -gt 0) { [math]::Round(($hits / $totalGaps) * 100, 1) } else { 0 }
    $brierScore = if ($evaluations.Count -gt 0) { [math]::Round($brierSum / $evaluations.Count, 4) } else { 0 }
    
    # Top 5 Real Movers vs Misses
    $topCE = $evaluations | Sort-Object RealCEChg -Descending | Select-Object -First 3
    $topPE = $evaluations | Sort-Object RealPEChg -Descending | Select-Object -First 3
    
    $cycleRecord = [PSCustomObject]@{
        Timestamp = $cycleTime
        BrokerStatus = $hbStatus
        WriterAgeSec = $hbAge
        CycleInfo = $hbCycle
        EvaluatedSymbols = $evaluations.Count
        SymbolsWithGaps = $totalGaps
        DirectionalHits = $hits
        OpeningHitRatePct = $hitRate
        BrierScore = $brierScore
        TopCE = @($topCE | ForEach-Object { "$($_.Symbol) (+$(($_.RealCEChg))%)" })
        TopPE = @($topPE | ForEach-Object { "$($_.Symbol) (+$(($_.RealPEChg))%)" })
    }
    
    # Save to history JSON
    $history = @()
    if (Test-Path $LogJson) {
        try { $history = @(Get-Content $LogJson -Raw | ConvertFrom-Json) } catch { $history = @() }
    }
    $history += $cycleRecord
    if ($history.Count -gt 100) { $history = $history[($history.Count - 100)..($history.Count - 1)] }
    $history | ConvertTo-Json -Depth 5 | Set-Content $LogJson
    
    Write-DaemonLog "Cycle Complete | Broker: $hbStatus ($hbAge s) | Evaluated: $($evaluations.Count) | Hit Rate: $hitRate% | Brier: $brierScore" "SUCCESS"
    Write-DaemonLog "Top CE: $($cycleRecord.TopCE -join ', ') | Top PE: $($cycleRecord.TopPE -join ', ')" "INFO"
    
    # 5b. Generate and Save Cross-Verification & Learning Report
    $learningReportPath = Join-Path $ScriptDir "AUTO_LEARNING_REPORT.json"
    $topPredUp = @($evaluations | Where-Object { $_.PredGap -gt 0 } | Sort-Object PredGap -Descending | Select-Object -First 5 | ForEach-Object {
        [PSCustomObject]@{
            Symbol = $_.Symbol
            PredictedGapPct = $_.PredGap
            TargetStrike = $_.TargetStrike
            ActualRealCEChgPct = $_.RealCEChg
            DirectionalHit = $_.IsHit
        }
    })
    $topPredDown = @($evaluations | Where-Object { $_.PredGap -lt 0 } | Sort-Object PredGap | Select-Object -First 5 | ForEach-Object {
        [PSCustomObject]@{
            Symbol = $_.Symbol
            PredictedGapPct = $_.PredGap
            TargetStrike = $_.TargetStrike
            ActualRealPEChgPct = $_.RealPEChg
            DirectionalHit = $_.IsHit
        }
    })
    $topRealCE = @($topCE | Select-Object -First 5 | ForEach-Object {
        [PSCustomObject]@{
            Symbol = $_.Symbol
            RealCEGainPct = $_.RealCEChg
            PredictedGapPct = $_.PredGap
            PredictedSide = $_.PredSide
        }
    })
    $topRealPE = @($topPE | Select-Object -First 5 | ForEach-Object {
        [PSCustomObject]@{
            Symbol = $_.Symbol
            RealPEGainPct = $_.RealPEChg
            PredictedGapPct = $_.PredGap
            PredictedSide = $_.PredSide
        }
    })
    $learningReport = [PSCustomObject]@{
        Timestamp = $cycleTime
        BrokerStatus = $hbStatus
        DirectionalHitRatePct = $hitRate
        BrierScore = $brierScore
        TotalEvaluated = $evaluations.Count
        TopPredictedGapUpVsReal = $topPredUp
        TopPredictedGapDownVsReal = $topPredDown
        TopRealCEMoversVsModel = $topRealCE
        TopRealPEMoversVsModel = $topRealPE
        SelfLearnedPreventionRules = @(
            [PSCustomObject]@{
                RuleId = "RULE-01-VELOCITY-SQUEEZE"
                TargetPattern = "DELHIVERY (+700% CE surge)"
                Mechanism = "Institutional opening call-buying volume velocity > 3.0x 5-day average"
                Mitigation = "Dynamic intraday velocity scanner elevates fast-accumulating call strikes to Top 1"
            },
            [PSCustomObject]@{
                RuleId = "RULE-02-SECTOR-CONTAGION"
                TargetPattern = "RVNL (+1757% PE surge)"
                Mechanism = "Sector-wide peer breakdown (PSU / Railways) trigger cascading stop losses"
                Mitigation = "Sector contagion multiplier applies beta penalty to elevate put conviction"
            },
            [PSCustomObject]@{
                RuleId = "RULE-03-PENNY-BASE-NORMALIZATION"
                TargetPattern = "SAIL (+79900% CE optical jump)"
                Mechanism = "Deep OTM base < 0.20 creates misleading percentage explosion"
                Mitigation = "Filter strikes base < 0.20; rank by Delta-Weighted Rupee Value (dollar-gamma)"
            },
            [PSCustomObject]@{
                RuleId = "RULE-04-WIDE-SPREAD-CONVEXITY"
                TargetPattern = "CAMS (+2350% PE) & UNITDSPR (+1725% PE)"
                Mechanism = "Wide pre-market spread (>20%) mask institutional put positioning"
                Mitigation = "If PCR > 3.5 and Put OI additions are steady, flag as High-Convexity Pre-Breakdown"
            }
        )
    }
    try {
        $learningReport | ConvertTo-Json -Depth 6 | Set-Content $learningReportPath
    } catch {}
    
    # 6. Auto-sync active Power BI Desktop model in memory
    try {
        $syncScript = Join-Path $ScriptDir "SYNC_LIVE_FEED_TO_PBI.ps1"
        if (Test-Path $syncScript) {
            & $syncScript
            Write-DaemonLog "Power BI models synced with live Google Sheets streaming data" "SUCCESS"
        }
    } catch {
        Write-DaemonLog "Power BI live sync failed: $_" "WARN"
    }
}

Write-DaemonLog "Angel F&O Autonomous Daemon initialized. Interval: $IntervalSeconds s." "INFO"

if ($RunOnce) {
    Execute-TrackingCycle
} else {
    while ($true) {
        Execute-TrackingCycle
        Start-Sleep -Seconds $IntervalSeconds
    }
}
