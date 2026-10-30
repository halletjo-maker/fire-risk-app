@echo off
chcp 65001 >nul
REM Mot de passe oublie : en choisir un nouveau (l'application peut rester lancee).
cd /d "%~dp0backend"
set "RUNPY="
if exist .venv\Scripts\python.exe .venv\Scripts\python.exe -c "import fastapi" >nul 2>nul && set "RUNPY=.venv\Scripts\python.exe"
if not defined RUNPY py -3.13 -c "import fastapi" >nul 2>nul && set "RUNPY=py -3.13"
if not defined RUNPY py -3.12 -c "import fastapi" >nul 2>nul && set "RUNPY=py -3.12"
if not defined RUNPY python -c "import fastapi" >nul 2>nul && set "RUNPY=python"
if not defined RUNPY goto :not_installed
echo.
echo  === Nouveau mot de passe ===
echo.
%RUNPY% -m app.reset_password
echo.
pause
exit /b 0

:not_installed
echo  [ERREUR] Application non installee : lance d'abord install.bat
pause
exit /b 1
