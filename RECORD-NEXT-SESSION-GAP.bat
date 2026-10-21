@echo off
REM Double-click this file. It does not buy or sell anything.
REM It does not turn on live orders. Paper mode stays on.
REM It copies a forecast the system already saved, and it leaves the result blank.
REM If that forecast is for a day that already passed, it says so.
REM It does not invent a stock name, a price, or a profit.
REM When the window stops, copy all of the text and paste it back.
cd /d C:\AngelFNO_Workstation\repos\angel-fno-scanner
set PAPER_MODE=1
set LIVE_ORDER_AUTHORITY=0
echo PAPER_MODE=%PAPER_MODE%
echo LIVE_ORDER_AUTHORITY=%LIVE_ORDER_AUTHORITY%
echo.
schtasks /Query /TN "AngelFNO-Gap-Forward-Record" >nul 2>&1
if "%ERRORLEVEL%"=="0" (
  echo The weekday 3:35 PM reminder is already on this PC.
) else (
  echo The weekday reminder is not on this PC yet.
  echo Windows may ask you to allow a change. Allow it if you want the reminder.
  schtasks /Create /TN "AngelFNO-Gap-Forward-Record" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 15:35 /RL LIMITED /F /TR "cmd.exe /c set PAPER_MODE=1&& set LIVE_ORDER_AUTHORITY=0&& cd /d C:\AngelFNO_Workstation\repos\angel-fno-scanner&& C:\AngelFNO_Workstation\repos\angel-fno-scanner\.venv\Scripts\python.exe tools\gapup_verifier.py record >> C:\AngelFNO_Workstation\angel-agent-supervisor\logs\gapup_record_task.log 2>&1"
  echo Reminder install exit code: %ERRORLEVEL%
)
echo.
echo Checking the saved forecast now:
C:\AngelFNO_Workstation\repos\angel-fno-scanner\.venv\Scripts\python.exe tools\gapup_verifier.py record
echo Record exit code: %ERRORLEVEL%
echo.
echo Paste this whole window back.
pause
