@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title Assistente pessoal 81 - Instalacao
echo Instalando Assistente pessoal 81. Esta etapa precisa de internet.
set "NEYMAR_PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if exist "%NEYMAR_PY%" goto ambiente
where py >nul 2>nul
if errorlevel 1 goto instalar_python
py -3.12 -c "import sys" >nul 2>nul
if errorlevel 1 goto instalar_python
py -3.12 -m venv "%~dp0.venv"
goto componentes
:instalar_python
winget install --exact --id Python.Python.3.12 --scope user --location "%LOCALAPPDATA%\Programs\Python\Python312" --accept-package-agreements --accept-source-agreements
if errorlevel 1 goto erro
:ambiente
"%NEYMAR_PY%" -m venv "%~dp0.venv"
if errorlevel 1 goto erro
:componentes
if not exist "%~dp0.venv\Scripts\python.exe" goto erro
"%~dp0.venv\Scripts\python.exe" -m pip install -r "%~dp0requirements.txt"
if errorlevel 1 goto erro
"%~dp0.venv\Scripts\python.exe" -m pip install -r "%~dp0requirements-interface.txt"
if errorlevel 1 goto erro
"%~dp0.venv\Scripts\python.exe" "%~dp0instalar_modelo.py"
if errorlevel 1 goto erro
call "%~dp03 - Instalar IA local opcional.bat" silencioso
if errorlevel 1 goto erro
call "%~dp02 - Corrigir Inicializacao Automatica.bat" silencioso
if errorlevel 1 goto erro
"%~dp0.venv\Scripts\python.exe" "%~dp0configuracao_inicial.py"
if errorlevel 1 goto erro
echo.
echo Instalado. Abra Iniciar Assistente.bat. Configure sua chave NVIDIA nas Configuracoes ou use Ollama local.
echo Para voz neural local, execute tambem 4 - Instalar voz Piper opcional.bat.
pause
exit /b 0
:erro
echo.
echo A instalacao nao terminou. Tire uma foto do erro acima.
pause
exit /b 1
