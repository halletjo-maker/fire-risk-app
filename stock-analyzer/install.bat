@echo off
chcp 65001 >nul
REM Installation en un double-clic (Windows) : seul Python est necessaire.
REM L'interface est deja fabriquee dans backend\web (pas besoin de Node.js).
cd /d "%~dp0"
echo.
echo  === Installation - Analyse Boursiere ===
echo.

if not exist backend\requirements.txt goto :no_files

REM Python 3.12 ou 3.13 obligatoire (une bibliotheque d'indicateurs ne supporte pas encore 3.14)
set "PY="
py -3.13 --version >nul 2>nul && set "PY=py -3.13"
if not defined PY py -3.12 --version >nul 2>nul && set "PY=py -3.12"
if not defined PY python -c "import sys; sys.exit(0 if sys.version_info[:2] in ((3,12),(3,13)) else 1)" >nul 2>nul && set "PY=python"
if not defined PY goto :no_python

REM Chemin complet de l'interpreteur (plus fiable que py / python)
set "BASEPY="
for /f "usebackq delims=" %%i in (`%PY% -c "import sys; print(sys.executable)"`) do set "BASEPY=%%i"
if not defined BASEPY goto :no_python
echo  Python utilise : "%BASEPY%"
"%BASEPY%" --version

if not exist .env copy .env.example .env >nul

cd backend
set "RUNPY="
set "PIPUSER="

REM 1er essai : environnement isole backend\.venv
echo.
echo  [1/2] Creation de l'environnement Python...
if not exist .venv\Scripts\python.exe (
  if exist .venv rmdir /s /q .venv
  "%BASEPY%" -m venv .venv >nul 2>nul
)
if exist .venv\Scripts\python.exe (
  .venv\Scripts\python.exe -c "print()" >nul 2>nul && set "RUNPY=%CD%\.venv\Scripts\python.exe"
)

REM 2e essai : venv bloque par le PC, on installe dans le Python de l'utilisateur
if not defined RUNPY (
  echo  Environnement isole impossible sur ce PC : installation dans ton Python.
  if exist .venv rmdir /s /q .venv
  set "RUNPY=%BASEPY%"
  set "PIPUSER=--user"
)

echo.
echo  [2/2] Installation des bibliotheques - 2 a 5 minutes...
"%RUNPY%" -m pip install %PIPUSER% --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto :pip_failed

REM Memorise l'interpreteur pour start.bat
> python_path.txt echo %RUNPY%
cd ..
echo.
echo  === Installation terminee ! Double-clique maintenant sur start.bat ===
echo.
pause
exit /b 0

:no_files
echo  [ERREUR] Fichiers introuvables. Extrais d'abord le ZIP :
echo  clic droit sur le fichier ZIP, puis "Extraire tout...", puis relance install.bat
echo  depuis le dossier extrait.
pause
exit /b 1

:no_python
echo  [ERREUR] Python 3.12 ou 3.13 est introuvable.
echo  Versions detectees :
py --list 2>nul
python --version 2>nul
echo.
echo  Installe Python 3.13 depuis https://www.python.org/downloads/windows/
echo  en cochant "Add python.exe to PATH", puis relance install.bat
pause
exit /b 1

:pip_failed
echo.
echo  [ERREUR] Installation des bibliotheques impossible.
echo  Envoie une capture de cette fenetre a Claude.
pause
exit /b 1
