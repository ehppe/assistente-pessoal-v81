@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" (start "" ".venv\Scripts\pythonw.exe" configuracao_inicial.py) else (py -3.12 configuracao_inicial.py)
