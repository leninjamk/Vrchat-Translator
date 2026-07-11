#define MyAppName "VRChat Speech Translator"
#define MyAppVersion "5.0"
#define MyAppPublisher "LeNinjaMK"
#define ProjectDir "C:\Users\AnonymousBR\Desktop\Projetos Python\Tradutor 2.0 - Copia"

[Setup]
AppId={{9F2C4E1A-7B3D-4E9A-9C2B-1A2B3C4D5E6F}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=C:\Users\ANONYM~1\AppData\Local\Temp\claude\c--Users-AnonymousBR-Desktop-Projetos-Python-Tradutor-2-0---Copia\50394191-f7fb-4e5d-811e-bd47c80868f6\scratchpad\dist_installer
OutputBaseFilename=VRChatSpeechTranslator_Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupLogging=yes

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na Área de Trabalho"; GroupDescription: "Atalhos adicionais:"

[Files]
Source: "{#ProjectDir}\*"; DestDir: "{app}"; Excludes: ".venv,__pycache__,.git,.claude,settings.json,main.py,core\audio.py,*.pyc,*.pyo,*.exe,installer.iss"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\Run.bat"; WorkingDir: "{app}"
Name: "{userdesktop}\{#MyAppName}"; Filename: "{app}\Run.bat"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{group}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\Install.bat"; WorkingDir: "{app}"; StatusMsg: "Instalando dependências (baixa Python se preciso e as bibliotecas necessárias — pode levar alguns minutos)..."; Flags: waituntilterminated
Filename: "{app}\Run.bat"; Description: "Abrir o {#MyAppName} agora"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\.venv"
Type: files; Name: "{app}\settings.json"

[Code]
procedure DeleteAllPycache(const Dir: string);
var
  FindRec: TFindRec;
  FullPath: string;
begin
  if FindFirst(Dir + '\*', FindRec) then
  begin
    try
      repeat
        if (FindRec.Name <> '.') and (FindRec.Name <> '..') then
        begin
          FullPath := Dir + '\' + FindRec.Name;
          if FileOrDirExists(FullPath) and DirExists(FullPath) then
          begin
            if FindRec.Name = '__pycache__' then
              DelTree(FullPath, True, True, True)
            else
              DeleteAllPycache(FullPath);
          end;
        end;
      until not FindNext(FindRec);
    finally
      FindClose(FindRec);
    end;
  end;
end;

procedure RemoveEmptyDirs(const Dir: string);
var
  FindRec: TFindRec;
  FullPath: string;
begin
  if FindFirst(Dir + '\*', FindRec) then
  begin
    try
      repeat
        if (FindRec.Name <> '.') and (FindRec.Name <> '..') then
        begin
          FullPath := Dir + '\' + FindRec.Name;
          if DirExists(FullPath) then
            RemoveEmptyDirs(FullPath);
        end;
      until not FindNext(FindRec);
    finally
      FindClose(FindRec);
    end;
  end;
  RemoveDir(Dir);
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    DeleteAllPycache(ExpandConstant('{app}'));
    RemoveEmptyDirs(ExpandConstant('{app}'));
  end;
end;
