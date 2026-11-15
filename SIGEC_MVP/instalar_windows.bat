@echo off
chcp 65001 >nul
cd /d "%~dp0"
python --version >nul 2>&1
if errorlevel 1 (
  echo Python nao encontrado. Instale Python 3.12 ou 3.13 e marque Add Python to PATH.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" python -m venv .venv
if not exist ".venv\Scripts\python.exe" (
  echo Falha ao criar ambiente virtual.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo Falha ao instalar dependencias. Conecte-se a internet apenas para essa instalacao.
  pause
  exit /b 1
)
echo Instalacao finalizada. Execute iniciar_sigec.bat.
pause
