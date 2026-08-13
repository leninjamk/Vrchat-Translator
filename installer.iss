#define MyAppName "VRChat Speech Translator"
#define MyAppVersion "5.0"
#define MyAppPublisher "LeNinjaMK"
#define ProjectDir "C:\Users\AnonymousBR\Desktop\Projetos Python\Tradutor 2.0 - Copia - Copia"

[Setup]
AppId={{9F2C4E1A-7B3D-4E9A-9C2B-1A2B3C4D5E6F}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir={#ProjectDir}\dist_installer
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
; Backend Python (código-fonte) — o .venv é criado durante a instalação
; (Install.bat -> install_project.py), nunca empacotado aqui: evita um
; instalador de vários GB e deixa o pip resolver os pacotes certos pra
; máquina de quem instala.
Source: "{#ProjectDir}\service\*"; DestDir: "{app}\service"; Excludes: "__pycache__,*.pyc"; Flags: recursesubdirs ignoreversion
Source: "{#ProjectDir}\core\*"; DestDir: "{app}\core"; Excludes: "__pycache__,*.pyc"; Flags: recursesubdirs ignoreversion
Source: "{#ProjectDir}\native\*"; DestDir: "{app}\native"; Excludes: "__pycache__,*.pyc"; Flags: recursesubdirs ignoreversion
Source: "{#ProjectDir}\bin\*"; DestDir: "{app}\bin"; Flags: ignoreversion
Source: "{#ProjectDir}\run_service.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#ProjectDir}\config.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#ProjectDir}\requirements.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#ProjectDir}\install_project.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#ProjectDir}\Install.bat"; DestDir: "{app}"; Flags: ignoreversion
; App Tauri compilado (frontend/src-tauri/target/release/frontend.exe) — o
; nome do arquivo vira {#MyAppName}.exe pra ficar amigável nos atalhos.
; spawn_sidecar() em lib.rs procura run_service.py do LADO do .exe primeiro
; (esse layout) antes de cair pro caminho relativo de dev.
Source: "{#ProjectDir}\frontend\src-tauri\target\release\frontend.exe"; DestDir: "{app}"; DestName: "{#MyAppName}.exe"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppName}.exe"; WorkingDir: "{app}"
Name: "{userdesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppName}.exe"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{group}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"

[Run]
; Tentei rodar isso escondido (Exec com SW_HIDE) numa página própria do
; wizard, mas em teste real travou: em algum ponto da cadeia cmd -> bat ->
; bat -> python -> subprocessos a última linha do log se perdeu e o
; instalador ficou esperando pra sempre por um sinal de conclusão que nunca
; chegou (ver histórico do projeto). Voltando pro jeito comprovado — a janela
; do Install.bat fica visível, mas NUNCA trava.
Filename: "{app}\Install.bat"; WorkingDir: "{app}"; StatusMsg: "Instalando dependências (baixa Python se preciso e as bibliotecas necessárias — pode levar alguns minutos)..."; Flags: waituntilterminated
Filename: "{app}\{#MyAppName}.exe"; Description: "Abrir o {#MyAppName} agora"; Flags: postinstall nowait skipifsilent

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
