@echo off
chcp 65001 >nul
REM Installation en un double-clic (Windows) : seul Python est necessaire.
REM L'interface est deja fabriquee dans backend\web (pas besoin de Node.js).
cd /d "%~dp0"
echo.
echo  === Installation - Analyse Boursiere ===
echo.

if not exist backend\requirements.txt (
  echo  [ERREUR] Fichiers introuvables. Extrais d'abord le ZIP :
  echo  clic droit sur le fichier ZIP, puis "Extraire tout...", puis relance install.bat
  echo  depuis le dossier extrait.
  pause
  exit /b 1
)

REM Python 3.12 ou 3.13 obligatoire (une bibliotheque d'indicateurs ne supporte pas encore 3.14)
set "PY="
py -3.13 --version >nul 2>nul && set "PY=py -3.13"
if not defined PY py -3.12 --version >nul 2>nul && set "PY=py -3.12"
if not defined PY python -c "import sys; sys.exit(0 if sys.version_info[:2] in ((3,12),(3,13)) else 1)" >nul 2>nul && set "PY=python"
if not defined PY (
  echo  [ERREUR] Python 3.12 ou 3.13 est introuvable.
  echo  Versions detectees :
  py --list 2>nul
  python --version 2>nul
  echo.
  echo  Installe Python 3.13 depuis https://www.python.org/downloads/windows/
  echo  en cochant "Add python.exe to PATH", puis relance install.bat
  pause
  exit /b 1
)
echo  Python utilise :
%PY% --version

if not exist .env (
  copy .env.example .env >nul
  echo  Fichier .env cree.
)

echo.
echo  Installation des bibliotheques (2 a 5 minutes)...
cd backend
if not exist .venv\Scripts\python.exe %PY% -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip >nul
.venv\Scripts\python -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo  [ERREUR] Installation impossible. Envoie une capture de cette fenetre a Claude.
  pause
  exit /b 1
)
cd ..
echo.
echo  === Installation terminee ! Double-clique maintenant sur start.bat ===
echo.
pause
