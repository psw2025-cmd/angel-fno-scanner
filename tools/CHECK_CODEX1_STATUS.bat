@echo off
setlocal enabledelayedexpansion
title AngelFNO - CODEX-1 Zero-Trust Pre-Flight Tripwire Checker

set "PY=C:\AngelFNO_Workstation\repos\angel-fno-scanner\.venv\Scripts\python.exe"
set "GATE_SCRIPT=C:\AngelFNO_Workstation\tools\verify_codex1_gates.py"

if not exist "!PY!" (
    color 4F
    echo [CRITICAL ERROR] Python runtime not found at: !PY!
    echo EXIT CODE 1
    pause
    exit /b 1
)

if not exist "!GATE_SCRIPT!" (
    color 4F
    echo [CRITICAL ERROR] Gate script not found at: !GATE_SCRIPT!
    echo EXIT CODE 1
    pause
    exit /b 1
)

"!PY!" "!GATE_SCRIPT!" %*
set "EXIT_CODE=%errorlevel%"

if !EXIT_CODE! EQU 0 (
    color 0A
    echo.
    echo ===============================================================================
    echo    VERIFICATION SUCCESS: SYSTEM 100%% GREEN - ALL 4 GATES PASSED
    echo ===============================================================================
    echo.
    pause
    exit /b 0
) else (
    color 4F
    echo.
    echo ===============================================================================
    echo    CRITICAL TRIPWIRE TRIPPED: GATE VERIFICATION FAILED [RED - EXIT CODE !EXIT_CODE!]
    echo ===============================================================================
    echo.
    pause
    exit /b 1
)
