@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist "%~dp0.venv\Scripts\python.exe" goto erro
"%~dp0.venv\Scripts\python.exe" -m pip install "faster-whisper>=1.1,<2"
if errorlevel 1 goto erro
"%~dp0.venv\Scripts\python.exe" "%~dp0instalar_whisper.py"
if errorlevel 1 goto erro
echo Pronto. Abra o Neymar, selecione whisper em Reconhecimento e salve.
echo O modelo funciona localmente apos este download. Nao precisa de chave de API.
pause
exit /b 0
:erro
echo Instalacao incompleta. Se ainda nao tem .venv, execute primeiro 1 - Instalar Assistente.bat.
echo Confira o erro acima e tente novamente.
pause
exit /b 1
