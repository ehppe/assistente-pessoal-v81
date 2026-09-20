@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist "%~dp0.venv\Scripts\pythonw.exe" goto instalar
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0assistente_local.py"
exit /b 0
:instalar
echo Execute primeiro 1 - Instalar Assistente.bat nesta pasta.
pause
