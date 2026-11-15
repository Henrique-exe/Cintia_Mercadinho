@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Ambiente virtual nao encontrado. Execute instalar_windows.bat primeiro.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" launcher.py
if errorlevel 1 pause
