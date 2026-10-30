@echo off
chcp 65001 >nul
REM Lance le backend (port 8000) et le frontend (port 3000) dans deux fenetres.
cd /d "%~dp0"
if not exist backend\.venv (
  echo  L'application n'est pas encore installee : double-clique d'abord sur install.bat
  pause
  exit /b 1
)
if not exist .env copy .env.example .env >nul
start "Backend - Analyse Boursiere" cmd /k "cd backend && .venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
start "Frontend - Analyse Boursiere" cmd /k "cd frontend && npm run dev"
echo.
echo  Patiente 10 secondes puis ouvre :
echo    Sur ce PC  : http://localhost:3000
echo    Telephone  : http://ADRESSE-IP-DU-PC:3000  (meme Wi-Fi)
echo.
echo  Adresse(s) IP de ce PC :
ipconfig | findstr /c:"IPv4"
echo.
echo  Pour arreter : ferme les deux fenetres noires "Backend" et "Frontend".
timeout /t 10 >nul
start http://localhost:3000
pause
