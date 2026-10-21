@echo off
setlocal
cd /d "C:\AngelFNO_Workstation\repos\angel-fno-scanner"
call .venv\Scripts\activate.bat
echo ===============================================================
echo     ANGEL FNO SYSTEM VERIFICATION - 4-POINT TRIPWIRE GATES
echo ===============================================================
python tools\verify_codex1_gates.py
if %ERRORLEVEL% NEQ 0 (
    color 4F
    echo [CRITICAL ERROR] One or more gates failed!
    pause
    exit /b 1
)
color 2F
echo [SUCCESS] All 4 gates PASSED 100%% GREEN!
echo.
echo Running negative control test suite...
python -m unittest tests\test_verify_codex1_gates.py
pause
exit /b 0
