@echo off
REM Start API and frontend dev servers (run from project root)

echo Starting Kannada Voice Banking dev servers...
echo.

start "API Server" cmd /k "cd /d %~dp0.. && uvicorn api.main:app --reload --port 8000"
timeout /t 2 /nobreak >nul
start "Frontend" cmd /k "cd /d %~dp0..\frontend && npm run dev"

echo.
echo API:      http://localhost:8000
echo Frontend: http://localhost:5173
echo.
echo Close the opened terminal windows to stop the servers.
