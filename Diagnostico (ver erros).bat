@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Feche o Neymar pela bandeja antes de abrir o diagnostico.
if not exist "%~dp0.venv\Scripts\python.exe" goto instalar
"%~dp0.venv\Scripts\python.exe" -X faulthandler "%~dp0assistente_local.py"
pause
exit /b 0
:instalar
echo Execute 1 - Instalar Assistente.bat primeiro.
pause
