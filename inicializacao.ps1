$ErrorActionPreference = 'Stop'
$javaPython = Join-Path $PSScriptRoot '.venv\Scripts\pythonw.exe'
if (!(Test-Path $javaPython)) { throw 'Execute 1 - Instalar Assistente.bat primeiro.' }
$startup = [Environment]::GetFolderPath('Startup')
$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut((Join-Path $startup 'Neymar Assistente.lnk'))
$link.TargetPath = $javaPython
$link.Arguments = '"' + (Join-Path $PSScriptRoot 'assistente_local.py') + '"'
$link.WorkingDirectory = $PSScriptRoot
$link.Description = 'Assistente pessoal 81'
$link.Save()
$legacy = Join-Path $startup 'Java Assistente.lnk'
if (Test-Path $legacy) { Remove-Item -LiteralPath $legacy }
$previous = Join-Path $startup 'Javis Assistente.lnk'
if (Test-Path $previous) { Remove-Item -LiteralPath $previous }
Write-Host 'Inicializacao automatica configurada para esta pasta.'
