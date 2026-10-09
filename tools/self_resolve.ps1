<#
.SYNOPSIS
    Self-Resolve Hygiene and Maintenance Automation Script
    Implements 5 core hygiene checks in accordance with AGENTS.md and DeepSeek routing rules.

.DESCRIPTION
    Check 1: Scan verify_*.py for emojis (🟢, 🔴, etc.) and replace with ASCII [PASS]/[FAIL]/[WARN]/[*] to prevent cp1252 errors.
    Check 2: Ensure **/desktop.ini is present in .gitignore.
    Check 3: Count audit/verify_harness_*.json. If > 20, move files older than 7 days to audit/archive/YYYY-MM/ gzipped.
    Check 4: Check git status for untracked orphans. Warn user if > 10.
    Check 5: Check git worktree list. Warn user to close IDE before pruning if > 1.
    Writes report only to C:\Temp\ (no writes to live production systems).
#>

[CmdletBinding()]
param (
    [string]$RepoRoot = "",
    [int]$ArchiveDays = 7,
    [string]$TempDir = "C:\Temp",
    [string]$OutputFile = "C:\Temp\SELF_RESOLVE_REPORT.txt"
)

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = Split-Path -Parent $PSScriptRoot
}

$ErrorActionPreference = "Stop"
$utf8NoBom = [System.Text.UTF8Encoding]::new($false)

# Ensure output directory exists
if (-not (Test-Path $TempDir)) {
    New-Item -ItemType Directory -Path $TempDir -Force | Out-Null
}

$reportLines = [System.Collections.Generic.List[string]]::new()

function Log-Report {
    param([string]$Message)
    $timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    $line = "[$timestamp] $Message"
    Write-Host $line
    $reportLines.Add($line)
}

Log-Report "=================================================================="
Log-Report "SELF-RESOLVE HYGIENE & MAINTENANCE AUTOMATION"
Log-Report "Repo Root: $RepoRoot"
Log-Report "Report File: $OutputFile"
Log-Report "Archive Days Threshold: $ArchiveDays days"
Log-Report "=================================================================="

# ==============================================================================
# CHECK 1: grep emoji in verify_*.py - if found replace with [PASS]/[FAIL]
# ==============================================================================
Log-Report "`n[CHECK 1] Scanning verify_*.py files for emojis..."

$verifyFiles = Get-ChildItem -Path $RepoRoot -Recurse -Filter "verify_*.py" | Where-Object {
    $_.FullName -notmatch "(\.venv|site-packages|\.git)"
}

$emojiReplacements = @(
    @{ Pattern = [char]::ConvertFromUtf32(0x1F7E2); Replacement = "[PASS]" }, # 🟢
    @{ Pattern = [char]::ConvertFromUtf32(0x1F534); Replacement = "[FAIL]" }, # 🔴
    @{ Pattern = [char]::ConvertFromUtf32(0x2705);  Replacement = "[PASS]" }, # ✅
    @{ Pattern = [char]::ConvertFromUtf32(0x274C);  Replacement = "[FAIL]" }, # ❌
    @{ Pattern = [char]::ConvertFromUtf32(0x26A0);  Replacement = "[WARN]" }, # ⚠️
    @{ Pattern = [char]::ConvertFromUtf32(0x2728);  Replacement = "[*]" }     # ✨
)

$check1ModifiedCount = 0

foreach ($file in $verifyFiles) {
    $filePath = $file.FullName
    $content = [System.IO.File]::ReadAllText($filePath, [System.Text.Encoding]::UTF8)
    $modified = $false
    $fileReplacements = 0

    foreach ($rep in $emojiReplacements) {
        if ($content.Contains($rep.Pattern)) {
            $occurrences = ([regex]::Matches($content, [regex]::Escape($rep.Pattern))).Count
            $content = $content.Replace($rep.Pattern, $rep.Replacement)
            $modified = $true
            $fileReplacements += $occurrences
        }
    }

    # Also clean any trailing variation selectors (\uFE0F) attached to warnings
    $variationSelector = [char]::ConvertFromUtf32(0xFE0F)
    if ($content.Contains($variationSelector)) {
        $content = $content.Replace($variationSelector, "")
        $modified = $true
    }

    # Clean double PASS PASS or FAIL FAIL if previously prepended
    if ($content.Contains("[PASS] PASS")) {
        $content = $content.Replace("[PASS] PASS", "[PASS]")
        $modified = $true
        $fileReplacements++
    }
    if ($content.Contains("[FAIL] FAIL")) {
        $content = $content.Replace("[FAIL] FAIL", "[FAIL]")
        $modified = $true
        $fileReplacements++
    }

    if ($modified) {
        [System.IO.File]::WriteAllText($filePath, $content, $utf8NoBom)
        $relPath = $filePath.Substring($RepoRoot.Length).TrimStart("\/")
        Log-Report "  -> Cleaned $relPath : replaced $fileReplacements emoji / redundant token instance(s)"
        $check1ModifiedCount++
    }
}

if ($check1ModifiedCount -gt 0) {
    Log-Report "[CHECK 1 RESULT] [PASS] Replaced emojis in $check1ModifiedCount verify_*.py file(s) with ASCII status tokens."
} else {
    Log-Report "[CHECK 1 RESULT] [PASS] Clean. No emojis found in any verify_*.py files."
}

# ==============================================================================
# CHECK 2: check **/desktop.ini in .gitignore - if not add it
# ==============================================================================
Log-Report "`n[CHECK 2] Verifying **/desktop.ini presence in .gitignore..."

$gitignorePath = Join-Path $RepoRoot ".gitignore"
if (-not (Test-Path $gitignorePath)) {
    Log-Report "  -> .gitignore missing. Creating .gitignore..."
    [System.IO.File]::WriteAllText($gitignorePath, "**/desktop.ini`n", $utf8NoBom)
    Log-Report "[CHECK 2 RESULT] [PASS] Created .gitignore and added **/desktop.ini."
} else {
    $gitignoreLines = [System.IO.File]::ReadAllLines($gitignorePath, [System.Text.Encoding]::UTF8)
    $hasPattern = $false
    foreach ($line in $gitignoreLines) {
        if ($line.Trim() -eq "**/desktop.ini") {
            $hasPattern = $true
            break
        }
    }

    if ($hasPattern) {
        Log-Report "[CHECK 2 RESULT] [PASS] **/desktop.ini is already present in .gitignore."
    } else {
        [System.IO.File]::AppendAllText($gitignorePath, "`n**/desktop.ini`n", $utf8NoBom)
        Log-Report "[CHECK 2 RESULT] [ACTION] Appended **/desktop.ini to .gitignore."
    }
}

# ==============================================================================
# CHECK 3: count audit/verify_harness_*.json - if >20 - move older than 7 days
#          to audit/archive/YYYY-MM/ gzipped
# ==============================================================================
Log-Report "`n[CHECK 3] Checking audit/verify_harness_*.json count and retention..."

Add-Type -AssemblyName System.IO.Compression

$auditDir = Join-Path $RepoRoot "audit"
$archivedCount = 0

if (Test-Path $auditDir) {
    $harnessFiles = Get-ChildItem -Path $auditDir -Filter "verify_harness_*.json" -File
    $harnessCount = $harnessFiles.Count
    Log-Report "  -> Found $harnessCount verify_harness_*.json files in $auditDir"

    if ($harnessCount -gt 20) {
        Log-Report "  -> File count ($harnessCount) exceeds threshold (20). Evaluating files older than $ArchiveDays days..."
        $cutoffDate = (Get-Date).AddDays(-$ArchiveDays)

        foreach ($file in $harnessFiles) {
            $isOlder = $false
            $yearMonth = $null

            # Attempt to parse date from filename: verify_harness_YYYYMMDD_HHMMSS.json
            if ($file.Name -match "^verify_harness_(\d{4})(\d{2})(\d{2})_") {
                $fYear = [int]$Matches[1]
                $fMonth = [int]$Matches[2]
                $fDay = [int]$Matches[3]
                try {
                    $fileDate = Get-Date -Year $fYear -Month $fMonth -Day $fDay -Hour 0 -Minute 0 -Second 0
                    if ($fileDate -lt $cutoffDate) {
                        $isOlder = $true
                        $yearMonth = "$($Matches[1])-$($Matches[2])"
                    }
                } catch {
                    # fallback to LastWriteTime
                }
            }

            if (-not $isOlder -and ($file.LastWriteTime -lt $cutoffDate)) {
                $isOlder = $true
                $yearMonth = $file.LastWriteTime.ToString("yyyy-MM")
            }

            if ($isOlder) {
                if (-not $yearMonth) {
                    $yearMonth = (Get-Date).ToString("yyyy-MM")
                }

                $archiveSubdir = Join-Path $auditDir "archive\$yearMonth"
                if (-not (Test-Path $archiveSubdir)) {
                    New-Item -ItemType Directory -Path $archiveSubdir -Force | Out-Null
                }

                $gzTargetPath = Join-Path $archiveSubdir "$($file.Name).gz"

                # Compress to .gz
                $inStream = [System.IO.File]::OpenRead($file.FullName)
                $outStream = [System.IO.File]::Create($gzTargetPath)
                $gzStream = [System.IO.Compression.GZipStream]::new($outStream, [System.IO.Compression.CompressionMode]::Compress)
                try {
                    $inStream.CopyTo($gzStream)
                } finally {
                    $gzStream.Dispose()
                    $outStream.Dispose()
                    $inStream.Dispose()
                }

                # Remove original uncompressed file
                Remove-Item -Path $file.FullName -Force
                $archivedCount++
            }
        }

        $remainingFiles = (Get-ChildItem -Path $auditDir -Filter "verify_harness_*.json" -File).Count
        Log-Report "[CHECK 3 RESULT] [PASS] Total: $harnessCount > 20 threshold. Archived $archivedCount files older than $ArchiveDays days to audit/archive/YYYY-MM/ (gzipped). Remaining uncompressed: $remainingFiles."
    } else {
        Log-Report "[CHECK 3 RESULT] [PASS] Count: $harnessCount <= 20 threshold. No archival required."
    }
} else {
    Log-Report "[CHECK 3 RESULT] [PASS] Directory $auditDir does not exist."
}

# ==============================================================================
# CHECK 4: git status orphans >10? warn user
# ==============================================================================
Log-Report "`n[CHECK 4] Checking untracked orphan files in git status..."

$gitStatusRaw = git -C $RepoRoot status --porcelain 2>&1
$orphanFiles = @($gitStatusRaw | Where-Object { $_ -match "^\?\?" })
$orphanCount = $orphanFiles.Count

if ($orphanCount -gt 10) {
    Log-Report "[CHECK 4 RESULT] [WARN] Untracked orphan files count: $orphanCount > 10 threshold!"
    Log-Report "  -> Warning: Too many untracked artifacts. Review untracked files with 'git status' and clean obsolete files."
    foreach ($orphan in ($orphanFiles | Select-Object -First 5)) {
        Log-Report "     $orphan"
    }
    if ($orphanCount -gt 5) {
        Log-Report "     ... ($($orphanCount - 5) more orphans)"
    }
} else {
    Log-Report "[CHECK 4 RESULT] [PASS] Untracked orphan files count: $orphanCount (within safe threshold <= 10)."
}

# ==============================================================================
# CHECK 5: git worktree list >1? warn close IDE before prune
# ==============================================================================
Log-Report "`n[CHECK 5] Checking active git worktrees..."

$worktreeList = git -C $RepoRoot worktree list 2>&1
$worktreeCount = ($worktreeList | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }).Count

if ($worktreeCount -gt 1) {
    Log-Report "[CHECK 5 RESULT] [WARN] Multiple git worktrees detected: $worktreeCount worktrees active (> 1 threshold)!"
    Log-Report "  -> Action Warning: Close IDE / editors before running 'git worktree prune' to prevent Windows file locking issues."
    foreach ($wt in $worktreeList) {
        Log-Report "     $wt"
    }
} else {
    Log-Report "[CHECK 5 RESULT] [PASS] Single active worktree detected ($worktreeCount)."
}

# ==============================================================================
# SUMMARY & PERSISTENCE TO C:\Temp
# ==============================================================================
Log-Report "`n=================================================================="
Log-Report "SELF-RESOLVE EXECUTION COMPLETE - NO WRITES TO PRODUCTION"
Log-Report "All outputs stored in $OutputFile"
Log-Report "=================================================================="

[System.IO.File]::WriteAllLines($OutputFile, $reportLines, $utf8NoBom)
Log-Report "Report successfully written to $OutputFile"
