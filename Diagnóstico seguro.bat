@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (".venv\Scripts\python.exe" diagnostico_sistema.py) else (py -3.12 diagnostico_sistema.py)
pause
