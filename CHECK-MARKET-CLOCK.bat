@echo off
REM Double-click this file. It only checks five market-clock cases and prints PASS or FAIL.
cd /d C:\AngelFNO_Workstation\repos\angel-fno-scanner
python tools\check_market_clock_cases.py
set RC=%ERRORLEVEL%
echo.
if "%RC%"=="0" (
  echo RESULT PASS
) else (
  echo RESULT FAIL
)
if /I "%~1"=="nopause" exit /b %RC%
echo.
echo You can close this window.
pause
exit /b %RC%
