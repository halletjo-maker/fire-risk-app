@echo off
chcp 65001 >nul
REM Installation en un double-clic (Windows) : backend Python + frontend Node.js
cd /d "%~dp0"
echo.
echo  === Installation - Analyse Boursiere ===
echo.

where node >nul 2>nul
if errorlevel 1 (
  echo  [ERREUR] Node.js est introuvable.
  echo  Installe la version LTS depuis https://nodejs.org puis relance install.bat
  pause
  exit /b 1
)

set "PY="
py -3.13 --version >nul 2>nul && set "PY=py -3.13"
if not defined PY py -3.12 --version >nul 2>nul && set "PY=py -3.12"
if not defined PY py -3.11 --version >nul 2>nul && set "PY=py -3.11"
if not defined PY (
  echo  [ERREUR] Python 3.11, 3.12 ou 3.13 est introuvable.
  echo  Installe Python 3.13 depuis https://www.python.org/downloads/windows/
  echo  en cochant "Add python.exe to PATH", puis relance install.bat
  pause
  exit /b 1
)
echo  Python utilise :
%PY% --version
node --version

if not exist .env (
  copy .env.example .env >nul
  echo  Fichier .env cree.
)

echo.
echo  [1/2] Installation du backend (2 a 5 minutes)...
cd backend
if not exist .venv %PY% -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip >nul
.venv\Scripts\python -m pip install -r requirements.txt
if errorlevel 1 (
  echo  [ERREUR] Installation Python impossible. Copie le message ci-dessus a Claude.
  pause
  exit /b 1
)

echo.
echo  [2/2] Installation du frontend (1 a 3 minutes)...
cd ..\frontend
call npm install --no-fund --no-audit
if errorlevel 1 (
  echo  [ERREUR] Installation Node.js impossible. Copie le message ci-dessus a Claude.
  pause
  exit /b 1
)
cd ..
echo.
echo  === Installation terminee ! Double-clique maintenant sur start.bat ===
echo.
pause
