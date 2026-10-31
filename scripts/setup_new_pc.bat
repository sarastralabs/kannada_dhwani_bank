@echo off
REM One-click wrapper for full first-time setup on a new Windows PC.
REM Double-click this file, or run from CMD:
REM   scripts\setup_new_pc.bat

cd /d "%~dp0.."
echo.
echo Running full setup (PowerShell)...
echo Project: %CD%
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_new_pc.ps1"
if errorlevel 1 (
  echo.
  echo Setup failed. Read the error above.
  pause
  exit /b 1
)

echo.
pause
