@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
 echo Execute primeiro 1 - Instalar Assistente.bat.
 pause
 exit /b 1
)
".venv\Scripts\python.exe" -m pip install -r requirements-interface.txt
if errorlevel 1 (
 echo Falha na instalacao. A interface classica continua disponivel.
 pause
 exit /b 1
)
echo Interface instalada. Feche o Neymar pela bandeja e abra novamente.
pause
