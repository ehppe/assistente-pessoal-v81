@echo off
chcp 65001 >nul
title Neymar - Teste de temperatura
if not exist "%~dp0.venv\Scripts\python.exe" (
  echo O assistente ainda nao foi instalado.
  echo Execute primeiro: 1 - Instalar Assistente.bat
  pause
  exit /b 1
)
"%~dp0.venv\Scripts\python.exe" "%~dp0diagnostico_temperatura.py"
echo.
pause
