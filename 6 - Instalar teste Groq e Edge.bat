@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist "%~dp0.venv\Scripts\python.exe" goto erro
"%~dp0.venv\Scripts\python.exe" -m pip install "edge-tts>=7,<8" "av>=14,<17" "requests>=2.32,<3" "sounddevice>=0.4,<1"
if errorlevel 1 goto erro
echo Pronto. Abra o Neymar, cadastre sua chave Groq e selecione groq e edge nas Configuracoes.
echo Edge nao exige chave. NVIDIA continua usando a chave ja cadastrada.
pause
exit /b 0
:erro
echo Nao foi possivel instalar. Confira o erro acima. Se nao tem .venv, execute primeiro o instalador 1.
pause
exit /b 1
