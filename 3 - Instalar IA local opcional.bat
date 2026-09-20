@echo off
chcp 65001 >nul
setlocal
where ollama >nul 2>nul
if not errorlevel 1 goto modelo
winget install --exact --id Ollama.Ollama --accept-package-agreements --accept-source-agreements
if errorlevel 1 goto erro
:modelo
set "NEYMAR_OLLAMA=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
if exist "%NEYMAR_OLLAMA%" goto baixar
set "NEYMAR_OLLAMA=ollama"
:baixar
start "" /min "%NEYMAR_OLLAMA%" serve
timeout /t 5 /nobreak >nul
"%NEYMAR_OLLAMA%" pull qwen2.5:3b
if errorlevel 1 goto erro
echo Inteligencia local pronta. Abra o Neymar.
if /i "%~1"=="silencioso" exit /b 0
pause
exit /b 0
:erro
echo Nao foi possivel instalar o Ollama ou baixar o modelo. Confira o erro acima.
if /i "%~1"=="silencioso" exit /b 1
pause
exit /b 1
