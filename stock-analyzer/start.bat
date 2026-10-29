@echo off
REM Lance le backend (port 8000) et le frontend (port 3000) dans deux fenêtres.
cd /d "%~dp0"
if not exist .env (
  copy .env.example .env >nul
  echo .env cree depuis .env.example - pense a le completer
)
start "Backend - Analyse Boursiere" cmd /k "cd backend && .venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8000"
start "Frontend - Analyse Boursiere" cmd /k "cd frontend && npm run dev"
echo.
echo   PC     : http://localhost:3000
echo   Mobile : http://ADRESSE-IP-DU-PC:3000  (voir "ipconfig", ligne IPv4)
echo.
