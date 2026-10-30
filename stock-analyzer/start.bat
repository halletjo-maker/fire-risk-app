@echo off
chcp 65001 >nul
REM Lance l'application complete (interface + serveur) sur le port 8000.
cd /d "%~dp0"
if not exist backend\requirements.txt goto :no_files

REM Recherche d'un Python ou les bibliotheques sont installees
set "RUNPY="
set "CHECK=import uvicorn, fastapi, pandas_ta"
if exist backend\.venv\Scripts\python.exe backend\.venv\Scripts\python.exe -c "%CHECK%" >nul 2>nul && set "RUNPY=%~dp0backend\.venv\Scripts\python.exe"
if not defined RUNPY py -3.13 -c "%CHECK%" >nul 2>nul && set "RUNPY=py -3.13"
if not defined RUNPY py -3.12 -c "%CHECK%" >nul 2>nul && set "RUNPY=py -3.12"
if not defined RUNPY python -c "%CHECK%" >nul 2>nul && set "RUNPY=python"
if not defined RUNPY goto :not_installed

if not exist .env copy .env.example .env >nul
echo  Python utilise : %RUNPY%
start "Analyse Boursiere - NE PAS FERMER" /d "%~dp0backend" cmd /k %RUNPY% -m uvicorn app.main:app --host 0.0.0.0 --port 8000
echo.
echo  L'application demarre - 10 secondes...
echo    Sur ce PC  : http://localhost:8000
echo    Telephone  : http://ADRESSE-IP-DU-PC:8000 - meme Wi-Fi
echo.
echo  Adresse IP de ce PC :
ipconfig | findstr /c:"IPv4"
echo.
echo  Pour arreter : ferme la fenetre "Analyse Boursiere - NE PAS FERMER".
timeout /t 10 >nul
start "" http://localhost:8000
exit /b 0

:no_files
echo  [ERREUR] Fichiers introuvables. Lance start.bat depuis le dossier stock-analyzer extrait.
pause
exit /b 1

:not_installed
echo  [ERREUR] Les bibliotheques Python sont introuvables.
echo  Double-clique d'abord sur install.bat et attends "Installation terminee".
pause
exit /b 1
