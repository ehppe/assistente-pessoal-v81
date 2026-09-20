@echo off
chcp 65001 >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0inicializacao.ps1"
if errorlevel 1 goto erro
if /i "%~1"=="silencioso" exit /b 0
pause
exit /b 0
:erro
if /i "%~1"=="silencioso" exit /b 1
pause
exit /b 1
