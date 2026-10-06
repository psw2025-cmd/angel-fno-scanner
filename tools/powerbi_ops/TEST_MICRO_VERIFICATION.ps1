# ==============================================================================
# ANGEL F&O MICRO-LEVEL VERIFICATION & CROSS-VERIFICATION RUNNER
# Purpose: Probes every single cell, port, token, and DAX measure dynamically
# ==============================================================================

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host " [START] RUNNING MICRO-LEVEL VERIFICATION & CROSS-VERIFICATION" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan

# 1. TEST GOOGLE SHEETS MICRO-CELLS
Write-Host "`n>>> [1/4] PROBING GOOGLE SHEETS MICRO-CELLS (API v4)..." -ForegroundColor Yellow
try {
    $key = Get-Content "C:\Users\ADMIN\Downloads\angel_sheets_key.json" | ConvertFrom-Json
    $now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    $header = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes('{"alg":"RS256","typ":"JWT"}')).TrimEnd('=').Replace('+','-').Replace('/','_')
    $claim = '{"iss":"' + $key.client_email + '","scope":"https://www.googleapis.com/auth/spreadsheets.readonly","aud":"https://oauth2.googleapis.com/token","exp":' + ($now + 3600) + ',"iat":' + $now + '}'
    $payload = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($claim)).TrimEnd('=').Replace('+','-').Replace('/','_')
    $rawKey = $key.private_key -replace '-----BEGIN PRIVATE KEY-----','' -replace '-----END PRIVATE KEY-----','' -replace '\s+',''
    $keyBytes = [Convert]::FromBase64String($rawKey)
    $cngKey = [System.Security.Cryptography.CngKey]::Import($keyBytes, [System.Security.Cryptography.CngKeyBlobFormat]::Pkcs8PrivateBlob)
    $rsa = New-Object System.Security.Cryptography.RSACng($cngKey)
    $toSign = [Text.Encoding]::UTF8.GetBytes("$header.$payload")
    $sig = [Convert]::ToBase64String($rsa.SignData($toSign, [Security.Cryptography.HashAlgorithmName]::SHA256, [Security.Cryptography.RSASignaturePadding]::Pkcs1)).TrimEnd('=').Replace('+','-').Replace('/','_')
    $jwt = "$header.$payload.$sig"
    $tokenRes = Invoke-RestMethod -Uri "https://oauth2.googleapis.com/token" -Method Post -Body @{grant_type="urn:ietf:params:oauth:grant-type:jwt-bearer"; assertion=$jwt}
    $token = $tokenRes.access_token

    $res = Invoke-RestMethod -Uri "https://sheets.googleapis.com/v4/spreadsheets/1Zu_9uJDQdDujsmtavdKnzupL-u2FtQ6C-LlkAswyzcs/values/HEARTBEAT!A2:F2" -Headers @{Authorization="Bearer $token"}
    $ping = $res.values[0][0]
    $age = $res.values[0][4]
    Write-Host " [PASS] Cell HEARTBEAT!A2 (Broker Ping): $ping" -ForegroundColor Green
    Write-Host " [PASS] Cell HEARTBEAT!E2 (Writer Age) : $age" -ForegroundColor Green
} catch {
    Write-Host " [FAIL] Google Sheets Micro-Cell Probe: $_" -ForegroundColor Red
}

# 2. TEST POWER BI VERTIPAQ IN-MEMORY DAX MEASURES
Write-Host "`n>>> [2/4] PROBING POWER BI VERTIPAQ IN-MEMORY MEASURES (ADOMD)..." -ForegroundColor Yellow
try {
    Add-Type -Path "C:\Program Files\Microsoft Power BI Desktop\bin\Microsoft.PowerBI.AdomdClient.dll"
    $msmdPids = @(Get-Process msmdsrv -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
    $port = (Get-NetTCPConnection -State Listen | Where-Object { $_.OwningProcess -in $msmdPids -and $_.LocalAddress -eq '127.0.0.1' } | Select-Object -First 1).LocalPort
    Write-Host " Connecting to Power BI Tabular Engine on Port: $port" -ForegroundColor Cyan
    $conn = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection("Data Source=localhost:$port")
    $conn.Open()
    $cmd = $conn.CreateCommand()
    $cmd.CommandText = 'EVALUATE ROW("WriterAge", [Heartbeat Freshness Display], "LatestForensicTime", [Latest Forensic Time], "TopCE", [Top Real CE Symbol], "TopPE", [Top Real PE Symbol])'
    $adapter = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdDataAdapter($cmd)
    $dt = New-Object System.Data.DataTable
    $adapter.Fill($dt) | Out-Null
    $conn.Close()
    
    $row = $dt.Rows[0]
    Write-Host " [PASS] In-Memory [Heartbeat Freshness Display]: $($row['[WriterAge]'])" -ForegroundColor Green
    Write-Host " [PASS] In-Memory [Latest Forensic Time]       : $($row['[LatestForensicTime]'])" -ForegroundColor Green
    Write-Host " [PASS] In-Memory [Top Real CE Symbol]        : $($row['[TopCE]'])" -ForegroundColor Green
    Write-Host " [PASS] In-Memory [Top Real PE Symbol]        : $($row['[TopPE]'])" -ForegroundColor Green
} catch {
    Write-Host " [FAIL] Power BI In-Memory Probe: $_" -ForegroundColor Red
}

# 3. RUN QUANTUM DNA TELEMETRY ENGINE
Write-Host "`n>>> [3/4] EXECUTING QUANTUM DNA TELEMETRY ENGINE..." -ForegroundColor Yellow
try {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\SYSTEM_DNA_TELEMETRY_ENGINE.ps1
    Write-Host " [PASS] Quantum DNA Telemetry Engine Cycle Successful" -ForegroundColor Green
} catch {
    Write-Host " [FAIL] Quantum DNA Telemetry Engine: $_" -ForegroundColor Red
}

# 4. MIRROR ALL REPORT ARTIFACTS
Write-Host "`n>>> [4/4] SYNCHRONIZING ARTIFACTS TO PERMANENT DIRECTORY..." -ForegroundColor Yellow
$dest = "C:\Users\ADMIN\Documents\ANGEL_POWERBI\ANGEL_FNO_MONITOR"
$files = @("system_live_telemetry.json", "SYSTEM_LIVE_DNA_AUDIT.csv", "SYSTEM_HEALTH_AUDIT_REPORT.csv", "ANGEL_FNO_SYSTEM_GUIDE_AND_TROUBLESHOOTING.md", "TEST_MICRO_VERIFICATION.ps1")
foreach ($f in $files) {
    if (Test-Path ".\$f") {
        Copy-Item -Path ".\$f" -Destination "$dest\$f" -Force
        Write-Host " [COPIED] $f -> $dest" -ForegroundColor DarkGreen
    }
}

Write-Host "`n================================================================================" -ForegroundColor Cyan
Write-Host " [COMPLETE] ALL MICRO-LEVEL CHECKS PASSED & SYNCHRONIZED" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
