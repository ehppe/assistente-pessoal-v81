#define MyAppName "Neymar — Assistente Pessoal"
#define MyAppVersion "81"
#define MyAppPublisher "Assistente Pessoal"
#define MyAppExeName "Neymar.exe"

[Setup]
AppId={{22B04F91-9E47-4F71-9E22-A0B250980081}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\NeymarAssistente
DefaultGroupName=Neymar Assistente
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=Neymar-Setup-v81
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
SetupLogging=yes
CloseApplications=yes
RestartApplications=no
UninstallDisplayName={#MyAppName}

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; GroupDescription: "Atalhos:"; Flags: checkedonce
Name: "startup"; Description: "Iniciar o Neymar junto com o Windows"; GroupDescription: "Inicialização:"; Flags: checkedonce

[Files]
Source: "..\dist\Neymar\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Neymar Assistente"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\Neymar Assistente"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{userstartup}\Neymar Assistente"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: startup

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir o Neymar e concluir a configuração"; Flags: nowait postinstall skipifsilent

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
    Log('Atualizando somente arquivos do programa; configurações, chaves e dados existentes serão preservados.');
end;
