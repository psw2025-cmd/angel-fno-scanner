@echo off
setlocal enabledelayedexpansion
title Angel F&O Admin Diagnostics Tool

echo ===============================================================================
echo          ANGEL F&O - SYSTEM & CLOUD ADMINISTRATION DIAGNOSTICS TOOL            
echo ===============================================================================
echo.
echo Running admin_tools.py...
echo.

set PYTHON_EXE=C:\AngelFNO_Workstation\repos\angel-fno-scanner\.venv\Scripts\python.exe
if not exist "%PYTHON_EXE%" (
    set PYTHON_EXE=C:\Users\ADMIN\AppData\Local\Programs\Python\Python312\python.exe
)

"%PYTHON_EXE%" "C:\AngelFNO_Workstation\repos\angel-fno-scanner\admin_tools.py"
set EXIT_CODE=%ERRORLEVEL%

echo.
if %EXIT_CODE% EQU 0 (
    color 2F
    echo [PASS] Configured administrative acceptance checks passed; not trading certification.
) else (
    color 4F
    echo [FAIL] ATTENTION NEEDED - ONE OR MORE CHECKS RETURNED FAILURE OR WARNING
)

echo.
echo Detailed Outputs Generated:
echo   - Text Report : C:\temp\admin_tools_output.txt
echo   - JSON Report : C:\temp\admin_tools_report.json
echo   - Archive Dir : C:\temp\admin_tools\
echo.
echo Press any key to exit...
pause >nul
exit /b %EXIT_CODE%
