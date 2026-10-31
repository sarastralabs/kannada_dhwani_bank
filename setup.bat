@echo off
REM ============================================================================
REM  Kannada Voice Banking — ONE-CLICK SETUP (new PC / deployment)
REM
REM  Double-click this file OR run from CMD:
REM    setup.bat
REM    setup.bat --fresh     (delete .venv and reinstall everything)
REM    setup.bat --skip-models   (venv + pip + npm only, no HF downloads)
REM ============================================================================

cd /d "%~dp0"
echo.
echo  Kannada Voice Banking Assistant - Setup
echo  Project: %CD%
echo.

set "EXTRA="
if /i "%~1"=="--fresh" set "EXTRA=-Fresh"
if /i "%~1"=="--skip-models" set "EXTRA=-SkipModels"
if /i "%~2"=="--fresh" set "EXTRA=%EXTRA% -Fresh"
if /i "%~2"=="--skip-models" set "EXTRA=%EXTRA% -SkipModels"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup_new_pc.ps1" %EXTRA%
if errorlevel 1 (
  echo.
  echo  SETUP FAILED - read the messages above.
  pause
  exit /b 1
)

echo.
echo  Setup finished. See scripts\setup_new_pc.ps1 output for how to run.
pause
