@echo off
chcp 65001 >nul
REM Lance l'application complete (interface + serveur) sur le port 8000.
cd /d "%~dp0"
if not exist backend\.venv\Scripts\python.exe (
  echo  L'application n'est pas encore installee : double-clique d'abord sur install.bat
  pause
  exit /b 1
)
if not exist .env copy .env.example .env >nul
start "Analyse Boursiere - NE PAS FERMER" cmd /k "cd backend && .venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
echo.
echo  L'application demarre (10 secondes)...
echo    Sur ce PC  : http://localhost:8000
echo    Telephone  : http://ADRESSE-IP-DU-PC:8000  (meme Wi-Fi)
echo.
echo  Adresse(s) IP de ce PC :
ipconfig | findstr /c:"IPv4"
echo.
echo  Pour arreter : ferme la fenetre "Analyse Boursiere - NE PAS FERMER".
timeout /t 10 >nul
start http://localhost:8000
