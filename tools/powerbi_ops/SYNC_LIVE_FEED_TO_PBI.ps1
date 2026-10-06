# ============================================================
# SYNC_LIVE_FEED_TO_PBI.ps1
# Fetches live Google Sheets streams (Heartbeat, ForensicLive, CERank)
# and directly updates in-memory Tabular models in active Power BI instances
# ============================================================

param(
    [int]$SpecificPort = 0
)

$ErrorActionPreference = 'Stop'
[System.Reflection.Assembly]::LoadFrom("C:\Program Files\Microsoft Power BI Desktop\bin\Microsoft.PowerBI.Tabular.dll") | Out-Null

$wc = New-Object System.Net.WebClient
$wc.Headers.Add("User-Agent", "AngelPowerBiSync/1.0")

# 1. Fetch Live Heartbeat
Write-Host "Fetching live HEARTBEAT from Google Sheets..." -ForegroundColor Cyan
$hbRaw = $wc.DownloadString('https://docs.google.com/spreadsheets/d/1Zu_9uJDQdDujsmtavdKnzupL-u2FtQ6C-LlkAswyzcs/gviz/tq?tqx=out:csv&sheet=HEARTBEAT')
$hbObj = ($hbRaw | ConvertFrom-Csv | Select-Object -First 1)

$hbTs = [string]$hbObj.'Last Ping (IST)'
$hbRunnerStatus = [string]$hbObj.'Angel Session Status'
$hbSymbolsScanned = 216; [int]::TryParse([string]$hbObj.'Auto-Discovered Symbols', [ref]$hbSymbolsScanned) | Out-Null
$hbEngineStatus = [string]$hbObj.'Engine Status'
$hbWriterAge = 0.0; [double]::TryParse([string]$hbObj.'Seconds Since Last Write', [ref]$hbWriterAge) | Out-Null
$hbFeedAlert = ([string]$hbObj.'Automated Feed Alert').Replace('"', "''")

Write-Host "Heartbeat: $hbTs | $hbRunnerStatus | $hbEngineStatus | Age: $hbWriterAge s" -ForegroundColor Green

# Build Heartbeat DATATABLE DAX
$hbDax = @"
DATATABLE(
    "timestamp", STRING,
    "writer_age_sec", DOUBLE,
    "runner_status", STRING,
    "engine_status", STRING,
    "symbols_scanned", INTEGER,
    "feed_alert", STRING,
    {
        {"$hbTs", $hbWriterAge, "$hbRunnerStatus", "$hbEngineStatus", $hbSymbolsScanned, "$hbFeedAlert"}
    }
)
"@

# 2. Fetch Live ForensicLive
Write-Host "Fetching live FORENSIC_LIVE from Google Sheets..." -ForegroundColor Cyan
$flRaw = $wc.DownloadString('https://docs.google.com/spreadsheets/d/1Zu_9uJDQdDujsmtavdKnzupL-u2FtQ6C-LlkAswyzcs/gviz/tq?tqx=out:csv&sheet=FORENSIC_LIVE')
$flItems = @($flRaw | ConvertFrom-Csv)
Write-Host "Loaded $($flItems.Count) ForensicLive rows." -ForegroundColor Green

$flRowDaxList = [System.Collections.Generic.List[string]]::new()
foreach ($item in $flItems) {
    $fTs = [string]$item.'Timestamp (IST)'
    $fSym = [string]$item.'Symbol'
    if ([string]::IsNullOrWhiteSpace($fSym)) { continue }
    
    $fLtp = 0.0; [double]::TryParse(([string]$item.'Fut LTP').Replace(',', ''), [ref]$fLtp) | Out-Null
    $fChg = 0.0; [double]::TryParse(([string]$item.'Fut Chg %').Replace(',', '').Replace('%', ''), [ref]$fChg) | Out-Null
    $fObi = 0.0; [double]::TryParse(([string]$item.'Fut OBI').Replace(',', ''), [ref]$fObi) | Out-Null
    $fAtm = 0.0; [double]::TryParse(([string]$item.'ATM Strike').Replace(',', ''), [ref]$fAtm) | Out-Null
    $fCeContract = [string]$item.'ATM CE Contract'
    $fCeLtp = 0.0; [double]::TryParse(([string]$item.'CE LTP').Replace(',', ''), [ref]$fCeLtp) | Out-Null
    $fCeChg = 0.0; [double]::TryParse(([string]$item.'CE Chg %').Replace(',', '').Replace('%', ''), [ref]$fCeChg) | Out-Null
    $fCeOi = 0L; [long]::TryParse(([string]$item.'CE OI').Replace(',', ''), [ref]$fCeOi) | Out-Null
    $fCeObi = 0.0; [double]::TryParse(([string]$item.'CE OBI').Replace(',', ''), [ref]$fCeObi) | Out-Null
    $fPeContract = [string]$item.'ATM PE Contract'
    $fPeLtp = 0.0; [double]::TryParse(([string]$item.'PE LTP').Replace(',', ''), [ref]$fPeLtp) | Out-Null
    $fPeChg = 0.0; [double]::TryParse(([string]$item.'PE Chg %').Replace(',', '').Replace('%', ''), [ref]$fPeChg) | Out-Null
    $fPeOi = 0L; [long]::TryParse(([string]$item.'PE OI').Replace(',', ''), [ref]$fPeOi) | Out-Null
    $fPcr = 0.0; [double]::TryParse(([string]$item.'ATM PCR').Replace(',', ''), [ref]$fPcr) | Out-Null
    $fSignal = ([string]$item.'Forensic Action Signal').Replace('"', "''")
    $fCeValid = if ($fCeLtp -gt 0) { "TRUE" } else { "FALSE" }
    $fPeValid = if ($fPeLtp -gt 0) { "TRUE" } else { "FALSE" }
    
    $flRowDaxList.Add("        {`"$fSym`", `"$fTs`", $fLtp, $fChg, $fObi, $fAtm, `"$fCeContract`", $fCeLtp, $fCeChg, $fCeOi, $fCeObi, `"$fPeContract`", $fPeLtp, $fPeChg, $fPeOi, $fPcr, `"$fSignal`", $fCeValid, $fPeValid}")
}

$flDax = @"
DATATABLE(
    "symbol", STRING,
    "time_ist", STRING,
    "fut_ltp", DOUBLE,
    "fut_chg_pct", DOUBLE,
    "fut_obi", DOUBLE,
    "atm_strike", DOUBLE,
    "ce_contract", STRING,
    "ce_ltp", DOUBLE,
    "ce_chg_pct", DOUBLE,
    "ce_oi", INTEGER,
    "ce_obi", DOUBLE,
    "pe_contract", STRING,
    "pe_ltp", DOUBLE,
    "pe_chg_pct", DOUBLE,
    "pe_oi", INTEGER,
    "atm_pcr", DOUBLE,
    "forensic_signal", STRING,
    "ce_valid", BOOLEAN,
    "pe_valid", BOOLEAN,
    {
$($flRowDaxList -join ",`n")
    }
)
"@

# 3. Fetch Live CE_PE_RANK
Write-Host "Fetching live CE_PE_RANK from Google Sheets..." -ForegroundColor Cyan
$ceRaw = $wc.DownloadString('https://docs.google.com/spreadsheets/d/1Zu_9uJDQdDujsmtavdKnzupL-u2FtQ6C-LlkAswyzcs/gviz/tq?tqx=out:csv&sheet=CE_PE_RANK')
$ceItems = @($ceRaw | ConvertFrom-Csv)
Write-Host "Loaded $($ceItems.Count) CE_PE_RANK rows." -ForegroundColor Green

$ceRowDaxList = [System.Collections.Generic.List[string]]::new()
foreach ($item in $ceItems) {
    # Extract properties using matching or index
    $pNames = @($item.psobject.Properties | Select-Object -ExpandProperty Name)
    if ($pNames.Count -lt 25) { continue }
    
    $rTs = [string]$item.($pNames[0])
    $rSym = [string]$item.($pNames[2])
    if ([string]::IsNullOrWhiteSpace($rSym)) { continue }
    
    $rStat = ([string]$item.($pNames[24])).Replace('"', "''")
    $rFutChg = 0.0; [double]::TryParse(([string]$item.($pNames[4])).Replace(',', '').Replace('%', ''), [ref]$rFutChg) | Out-Null
    $rOpenGap = 0.0; [double]::TryParse(([string]$item.($pNames[6])).Replace(',', '').Replace('%', ''), [ref]$rOpenGap) | Out-Null
    $rFutObi = 0.0; [double]::TryParse(([string]$item.($pNames[8])).Replace(',', ''), [ref]$rFutObi) | Out-Null
    $rCeChg = 0.0; [double]::TryParse(([string]$item.($pNames[11])).Replace(',', '').Replace('%', ''), [ref]$rCeChg) | Out-Null
    $rPeChg = 0.0; [double]::TryParse(([string]$item.($pNames[18])).Replace(',', '').Replace('%', ''), [ref]$rPeChg) | Out-Null
    $rCeOi = 0L; [long]::TryParse(([string]$item.($pNames[12])).Replace(',', ''), [ref]$rCeOi) | Out-Null
    $rPeOi = 0L; [long]::TryParse(([string]$item.($pNames[19])).Replace(',', ''), [ref]$rPeOi) | Out-Null
    $rCeOiChg = 0.0; [double]::TryParse(([string]$item.($pNames[13])).Replace(',', ''), [ref]$rCeOiChg) | Out-Null
    $rPeOiChg = 0.0; [double]::TryParse(([string]$item.($pNames[20])).Replace(',', ''), [ref]$rPeOiChg) | Out-Null
    $rCeObi = 0.0; [double]::TryParse(([string]$item.($pNames[15])).Replace(',', ''), [ref]$rCeObi) | Out-Null
    $rPcr = 0.0; [double]::TryParse(([string]$item.($pNames[21])).Replace(',', ''), [ref]$rPcr) | Out-Null
    $rCeStreak = 0L; [long]::TryParse(([string]$item.($pNames[22])).Replace(',', ''), [ref]$rCeStreak) | Out-Null
    $rPeStreak = 0L; [long]::TryParse(([string]$item.($pNames[23])).Replace(',', ''), [ref]$rPeStreak) | Out-Null
    $rWhy = if ($pNames.Count -gt 27) { ([string]$item.($pNames[27])).Replace('"', "''") } else { "" }
    
    $ceRowDaxList.Add("        {`"$rTs`", `"$rSym`", `"$rStat`", $rFutChg, $rOpenGap, $rFutObi, $rCeChg, $rPeChg, $rCeOi, $rPeOi, $rCeOiChg, $rPeOiChg, $rCeObi, $rPcr, $rCeStreak, $rPeStreak, `"$rWhy`"}")
}

$ceDax = @"
DATATABLE(
    "rank_time_ist", STRING,
    "symbol", STRING,
    "rank_status", STRING,
    "fut_chg_pct", DOUBLE,
    "opening_gap_pct", DOUBLE,
    "fut_obi", DOUBLE,
    "ce_chg_pct", DOUBLE,
    "pe_chg_pct", DOUBLE,
    "ce_oi", INTEGER,
    "pe_oi", INTEGER,
    "ce_oi_change", DOUBLE,
    "pe_oi_change", DOUBLE,
    "ce_obi", DOUBLE,
    "atm_pcr", DOUBLE,
    "ce_streak", INTEGER,
    "pe_streak", INTEGER,
    "explanation", STRING,
    {
$($ceRowDaxList -join ",`n")
    }
)
"@

# 4. Find all active Power BI ports
$msmdPids = @(Get-Process msmdsrv -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
$conns = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.OwningProcess -in $msmdPids -and $_.LocalAddress -eq '127.0.0.1' }

$ports = if ($SpecificPort -gt 0) { @($SpecificPort) } else { @($conns | Select-Object -ExpandProperty LocalPort -Unique) }
Write-Host "Target Power BI Ports: $($ports -join ', ')" -ForegroundColor Cyan

# Column definitions for TOM
$hbColsDef = @(
    @("timestamp", [Microsoft.AnalysisServices.Tabular.DataType]::String),
    @("writer_age_sec", [Microsoft.AnalysisServices.Tabular.DataType]::Double),
    @("runner_status", [Microsoft.AnalysisServices.Tabular.DataType]::String),
    @("engine_status", [Microsoft.AnalysisServices.Tabular.DataType]::String),
    @("symbols_scanned", [Microsoft.AnalysisServices.Tabular.DataType]::Int64),
    @("feed_alert", [Microsoft.AnalysisServices.Tabular.DataType]::String)
)

$flColsDef = @(
    @("symbol", [Microsoft.AnalysisServices.Tabular.DataType]::String),
    @("time_ist", [Microsoft.AnalysisServices.Tabular.DataType]::String),
    @("fut_ltp", [Microsoft.AnalysisServices.Tabular.DataType]::Double),
    @("fut_chg_pct", [Microsoft.AnalysisServices.Tabular.DataType]::Double),
    @("fut_obi", [Microsoft.AnalysisServices.Tabular.DataType]::Double),
    @("atm_strike", [Microsoft.AnalysisServices.Tabular.DataType]::Double),
    @("ce_contract", [Microsoft.AnalysisServices.Tabular.DataType]::String),
    @("ce_ltp", [Microsoft.AnalysisServices.Tabular.DataType]::Double),
    @("ce_chg_pct", [Microsoft.AnalysisServices.Tabular.DataType]::Double),
    @("ce_oi", [Microsoft.AnalysisServices.Tabular.DataType]::Int64),
    @("ce_obi", [Microsoft.AnalysisServices.Tabular.DataType]::Double),
    @("pe_contract", [Microsoft.AnalysisServices.Tabular.DataType]::String),
    @("pe_ltp", [Microsoft.AnalysisServices.Tabular.DataType]::Double),
    @("pe_chg_pct", [Microsoft.AnalysisServices.Tabular.DataType]::Double),
    @("pe_oi", [Microsoft.AnalysisServices.Tabular.DataType]::Int64),
    @("atm_pcr", [Microsoft.AnalysisServices.Tabular.DataType]::Double),
    @("forensic_signal", [Microsoft.AnalysisServices.Tabular.DataType]::String),
    @("ce_valid", [Microsoft.AnalysisServices.Tabular.DataType]::Boolean),
    @("pe_valid", [Microsoft.AnalysisServices.Tabular.DataType]::Boolean)
)

$ceColsDef = @(
    @("rank_time_ist", [Microsoft.AnalysisServices.Tabular.DataType]::String),
    @("symbol", [Microsoft.AnalysisServices.Tabular.DataType]::String),
    @("rank_status", [Microsoft.AnalysisServices.Tabular.DataType]::String),
    @("fut_chg_pct", [Microsoft.AnalysisServices.Tabular.DataType]::Double),
    @("opening_gap_pct", [Microsoft.AnalysisServices.Tabular.DataType]::Double),
    @("fut_obi", [Microsoft.AnalysisServices.Tabular.DataType]::Double),
    @("ce_chg_pct", [Microsoft.AnalysisServices.Tabular.DataType]::Double),
    @("pe_chg_pct", [Microsoft.AnalysisServices.Tabular.DataType]::Double),
    @("ce_oi", [Microsoft.AnalysisServices.Tabular.DataType]::Int64),
    @("pe_oi", [Microsoft.AnalysisServices.Tabular.DataType]::Int64),
    @("ce_oi_change", [Microsoft.AnalysisServices.Tabular.DataType]::Double),
    @("pe_oi_change", [Microsoft.AnalysisServices.Tabular.DataType]::Double),
    @("ce_obi", [Microsoft.AnalysisServices.Tabular.DataType]::Double),
    @("atm_pcr", [Microsoft.AnalysisServices.Tabular.DataType]::Double),
    @("ce_streak", [Microsoft.AnalysisServices.Tabular.DataType]::Int64),
    @("pe_streak", [Microsoft.AnalysisServices.Tabular.DataType]::Int64),
    @("explanation", [Microsoft.AnalysisServices.Tabular.DataType]::String)
)

function Update-ModelTable {
    param($Model, [string]$TableName, [string]$DaxExpr, [array]$Cols)
    
    if ($Model.Tables.Contains($TableName)) {
        $Model.Tables.Remove($TableName)
    }
    $t = New-Object Microsoft.AnalysisServices.Tabular.Table
    $t.Name = $TableName
    $part = New-Object Microsoft.AnalysisServices.Tabular.Partition
    $part.Name = "${TableName}_Partition"
    $part.Source = New-Object Microsoft.AnalysisServices.Tabular.CalculatedPartitionSource
    $part.Source.Expression = $DaxExpr
    $t.Partitions.Add($part)
    
    foreach ($c in $Cols) {
        $col = New-Object Microsoft.AnalysisServices.Tabular.CalculatedTableColumn
        $col.Name = $c[0]
        $col.DataType = $c[1]
        $col.SourceColumn = "[" + $c[0] + "]"
        $t.Columns.Add($col)
    }
    $Model.Tables.Add($t)
}

foreach ($port in $ports) {
    try {
        Write-Host "Connecting to localhost:$port..." -ForegroundColor Yellow
        $server = New-Object Microsoft.AnalysisServices.Tabular.Server
        $server.Connect("localhost:$port")
        $db = $server.Databases[0]
        $model = $db.Model
        Write-Host "Connected to model: $($model.Name) on port $port" -ForegroundColor Green

        Update-ModelTable -Model $model -TableName "Heartbeat" -DaxExpr $hbDax -Cols $hbColsDef
        Update-ModelTable -Model $model -TableName "ForensicLive" -DaxExpr $flDax -Cols $flColsDef
        Update-ModelTable -Model $model -TableName "CERank" -DaxExpr $ceDax -Cols $ceColsDef

        Write-Host "Committing live streaming update to port $port..." -ForegroundColor Yellow
        $model.SaveChanges()
        $model.RequestRefresh([Microsoft.AnalysisServices.Tabular.RefreshType]::Calculate)
        $model.SaveChanges()
        Write-Host "SUCCESS: Power BI on port $port fully refreshed with LIVE streaming data!" -ForegroundColor Green
        $server.Disconnect()
    } catch {
        Write-Host "ERROR refreshing port ${port}: $($_.Exception.ToString())" -ForegroundColor Red
    }
}

Write-Host "Live stream synchronization complete." -ForegroundColor Green
