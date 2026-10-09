@echo off
REM Windows batch runner for Makefile targets
if "%1"=="" goto help
if "%1"=="100-year-check" goto check100
if "%1"=="test" goto runtest
if "%1"=="reconciliation" goto recon
if "%1"=="recovery-test" goto recovery

:check100
echo Running 100-Year Autonomy Architecture Verification Suite...
python tools/memory_guard.py
if errorlevel 1 exit /b 1
python tools/verify_sheets_bq_reconciliation.py
if errorlevel 1 exit /b 1
pytest tests/
if errorlevel 1 exit /b 1
python tools/pre_post_matrix.py
if errorlevel 1 exit /b 1
python tools/crash_safe_test.py
if errorlevel 1 exit /b 1
python tools/test_recovery.py
if errorlevel 1 exit /b 1
python tools/self_learner.py --check
if errorlevel 1 exit /b 1
echo [OK] 100-YEAR CHECK COMPLETED SUCCESSFULLY.
exit /b 0

:runtest
pytest tests/
exit /b %errorlevel%

:recon
python tools/verify_sheets_bq_reconciliation.py
exit /b %errorlevel%

:recovery
python tools/test_recovery.py
exit /b %errorlevel%

:help
echo Usage: make.bat [100-year-check ^| test ^| reconciliation ^| recovery-test]
exit /b 1
