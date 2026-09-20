@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist "%~dp0.venv\Scripts\python.exe" goto erro
"%~dp0.venv\Scripts\python.exe" -m pip install --upgrade "piper-tts>=1.3,<2" espeakng-loader
if errorlevel 1 goto erro
if not exist "%~dp0modelos\piper" mkdir "%~dp0modelos\piper"
pushd "%~dp0modelos\piper"
for %%V in (pt_BR-faber-medium pt_BR-cadu-medium pt_BR-jeff-medium pt_BR-edresson-low) do (
    echo Instalando voz %%V...
    "%~dp0.venv\Scripts\python.exe" -m piper.download_voices %%V
    if errorlevel 1 goto erro_pasta
)
popd
echo Abra Configuracoes, selecione piper e escolha uma das quatro vozes. Salve e teste.
pause
exit /b 0
:erro_pasta
popd
:erro
echo Nao foi possivel instalar a voz Piper. A voz do Windows continua disponivel.
pause
exit /b 1
