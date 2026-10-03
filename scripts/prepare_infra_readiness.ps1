#Requires -Version 5.1
<#
.SYNOPSIS
Prepare provenance infrastructure and produce evidence without running market code.
.DESCRIPTION
Requires Python 3.11+ and the repository's Google dependencies. Uses existing Google
credentials. Default mode adds missing nullable schema fields and initializes an
empty WRITE_PROVENANCE tab. -VerifyOnly performs no cloud mutations.
No package installation, workflow dispatch, production rows, or broker calls.
#>
[CmdletBinding()]
param(
    [string]$RepoRoot,
    [string]$OutputRoot = 'C:\AngelFNO_Workstation\reports',
    [string]$PythonExe,
    [switch]$VerifyOnly,
    [switch]$Offline
)
$ErrorActionPreference = 'Stop'
try {
    if (-not $RepoRoot) { $RepoRoot = Split-Path -Parent $PSScriptRoot }
    $RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
    $helper = Join-Path $PSScriptRoot 'infra_readiness.py'
    if (-not $PythonExe) {
        $venvPython = Join-Path $RepoRoot '.venv\Scripts\python.exe'
        if (Test-Path -LiteralPath $venvPython) { $PythonExe = $venvPython }
        else { $PythonExe = (Get-Command python.exe -ErrorAction Stop).Source }
    }
    $arguments = @($helper, '--repo', $RepoRoot, '--output-root', $OutputRoot)
    if ($VerifyOnly) { $arguments += '--verify-only' }
    if ($Offline) { $arguments += '--offline' }
    & $PythonExe @arguments
    $result = $LASTEXITCODE
    if ($null -eq $result) { throw 'Python did not return an exit code.' }
    exit $result
} catch {
    Write-Error ('Readiness launcher failed: ' + $_.Exception.Message)
    exit 2
}
