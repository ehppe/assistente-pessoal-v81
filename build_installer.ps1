$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

Write-Host 'Preparando o ambiente de construção...'
python -m venv .build-venv
& .\.build-venv\Scripts\python.exe -m pip install --upgrade pip
& .\.build-venv\Scripts\python.exe -m pip install -r requirements-installer.txt

Write-Host 'Baixando o reconhecimento de voz local...'
& .\.build-venv\Scripts\python.exe instalar_modelo.py

Write-Host 'Gerando o aplicativo independente...'
Remove-Item -Recurse -Force build\pyinstaller, dist\Neymar -ErrorAction SilentlyContinue
& .\.build-venv\Scripts\python.exe -m PyInstaller `
    --noconfirm `
    --clean `
    --distpath dist `
    --workpath build\pyinstaller `
    build\Neymar.spec

if ($LASTEXITCODE -ne 0) { throw 'O PyInstaller não conseguiu gerar o aplicativo.' }
Copy-Item -Recurse -Force modelos dist\Neymar\modelos

Write-Host 'Gerando Neymar-Setup-v81.exe...'
$inno = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (!$inno) { throw 'Instale o Inno Setup 6 para concluir a construção.' }
& $inno build\Neymar.iss
if ($LASTEXITCODE -ne 0) { throw 'O Inno Setup não conseguiu gerar o instalador.' }
Write-Host 'Pronto: dist\Neymar-Setup-v81.exe'
