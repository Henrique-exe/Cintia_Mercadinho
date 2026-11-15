#if VER < EncodeVer(6,7,4) || VER >= EncodeVer(6,7,5)
#error Use Inno Setup 6.7.4.
#endif

; Compilar apenas com Inno Setup 6.7.4, pelo build.ps1.
#include "..\build\payload-defines.iss"

[Setup]
AppId={{7A8549B2-E8E1-49F0-9B85-C36BA51B569C}
AppName=SIGEC
AppVersion={#AppVersion}
AppPublisher=Projeto Mercadinho da Cíntia
DefaultDirName={localappdata}\Programs\SIGEC
DisableDirPage=yes
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64os
ArchitecturesInstallIn64BitMode=x64os
MinVersion=10.0
OutputDir=..\release
OutputBaseFilename=Instalar SIGEC
SetupIconFile=sigec.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\versions\{#PayloadId}\SIGEC.exe
SetupMutex=Local\SIGEC.Maintenance.7A8549B2
CloseApplications=no
RestartApplications=no
InfoBeforeFile=LEIA-ME.txt

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Files]
#include "..\build\payload-files.iss"
Source: "LEIA-ME.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{userdesktop}\SIGEC"; Filename: "{app}\versions\{#PayloadId}\SIGEC.exe"; WorkingDir: "{app}"; IconFilename: "{app}\versions\{#PayloadId}\SIGEC.exe"; IconIndex: 0
Name: "{userprograms}\SIGEC\SIGEC"; Filename: "{app}\versions\{#PayloadId}\SIGEC.exe"; WorkingDir: "{app}"; IconFilename: "{app}\versions\{#PayloadId}\SIGEC.exe"; IconIndex: 0
Name: "{userprograms}\SIGEC\Fazer backup do SIGEC"; Filename: "{app}\versions\{#PayloadId}\SIGEC.exe"; Parameters: "--backup"; WorkingDir: "{app}"
Name: "{userprograms}\SIGEC\Encerrar SIGEC"; Filename: "{app}\versions\{#PayloadId}\SIGEC.exe"; Parameters: "--stop"; WorkingDir: "{app}"

[Registry]
Root: HKCU; Subkey: "Software\SIGEC"; ValueType: string; ValueName: "InstalledExe"; ValueData: "{app}\versions\{#PayloadId}\SIGEC.exe"; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\SIGEC"; ValueType: string; ValueName: "Version"; ValueData: "{#AppVersion}"; Flags: uninsdeletevalue
; Não há entradas para data, backups, logs nem UninstallDelete de diretórios.

[Code]
var
  MaintenanceStream, StartupStream: TFileStream;

function NeedsFile(RelativeName, ExpectedHash: String): Boolean;
var Filename: String;
begin
  Filename := ExpandConstant('{app}\versions\{#PayloadId}\') + RelativeName;
  Result := True;
  if FileExists(Filename) then
    try
      Result := CompareText(GetSHA256OfFile(Filename), ExpectedHash) <> 0;
    except
      Result := True;
    end;
end;

function ExclusiveStream(Name: String): TFileStream;
var Filename: String;
begin
  Filename := ExpandConstant('{localappdata}\SIGEC\runtime\') + Name;
  if not ForceDirectories(ExtractFileDir(Filename)) then
    RaiseException('Não foi possível criar a pasta de manutenção do SIGEC.');
  if not FileExists(Filename) then
    if not SaveStringToFile(Filename, '', False) then
      RaiseException('Não foi possível criar o arquivo de manutenção do SIGEC.');
  Result := TFileStream.Create(Filename, $0012);
end;

function ServerBusy: Boolean;
var Probe: TFileStream;
begin
  Result := True;
  try
    Probe := ExclusiveStream('server.lock');
    Probe.Free;
    Result := False;
  except
    Log('SIGEC em uso ou lock inacessível.');
  end;
end;

function StopAndProtect: String;
var Exe: String; ExitCode: Integer; Probe: TFileStream;
begin
  Result := '';
  try
    if MaintenanceStream = nil then
      MaintenanceStream := ExclusiveStream('maintenance.lock');
    if ServerBusy then begin
      if not RegQueryStringValue(HKCU, 'Software\SIGEC', 'InstalledExe', Exe) then
        RaiseException('Não foi possível localizar o SIGEC instalado para encerrá-lo.');
      if not FileExists(Exe) then
        RaiseException('O inicializador instalado está ausente. Encerre o SIGEC com segurança ou reinicie o PC e tente reparar.');
      if not Exec(Exe, '--stop --no-dialog', ExtractFileDir(Exe), SW_HIDE, ewWaitUntilTerminated, ExitCode) then
        RaiseException('Não foi possível solicitar o encerramento do SIGEC.');
      if ExitCode <> 0 then
        RaiseException('O SIGEC não concluiu o encerramento. Aguarde e tente novamente. Consulte %LOCALAPPDATA%\SIGEC\logs\sigec.log.');
    end;
    // Bloqueia novas partidas inclusive em outra sessão do MESMO usuário.
    if StartupStream = nil then StartupStream := ExclusiveStream('startup.lock');
    Probe := ExclusiveStream('server.lock');
    Probe.Free;
  except
    Result := GetExceptionMessage;
    if StartupStream <> nil then begin StartupStream.Free; StartupStream := nil; end;
    if MaintenanceStream <> nil then begin MaintenanceStream.Free; MaintenanceStream := nil; end;
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var OldExe: String; OldVersion: Int64;
begin
  Result := '';
  if RegQueryStringValue(HKCU, 'Software\SIGEC', 'InstalledExe', OldExe) then
    if GetPackedVersion(OldExe, OldVersion) then
      if ComparePackedVersion(OldVersion, PackVersionComponents({#AppMajor}, {#AppMinor}, {#AppPatch}, 0)) > 0 then begin
        Result := 'Há uma versão mais nova instalada. Use o instalador dessa versão para reparar.';
        exit;
      end;
  if ServerBusy then begin
    if WizardSilent then begin
      Result := 'Encerre o SIGEC antes de uma instalação silenciosa.';
      exit;
    end;
    if MsgBox('Conclua a venda e outras operações em todas as abas do SIGEC. Ao continuar, o sistema vai parar de aceitar operações e aguardar as requisições em andamento. Continuar?', mbConfirmation, MB_YESNO) <> IDYES then begin
      Result := 'Instalação cancelada para manter o SIGEC em execução.';
      exit;
    end;
  end;
  Result := StopAndProtect;
end;

function InitializeUninstall: Boolean;
var Error: String;
begin
  Result := False;
  if CheckForMutexes('Local\SIGEC.Maintenance.7A8549B2') then begin
    MsgBox('Há outra manutenção do SIGEC em andamento.', mbError, MB_OK);
    exit;
  end;
  CreateMutex('Local\SIGEC.Maintenance.7A8549B2');
  if ServerBusy then begin
    if UninstallSilent then exit;
    if MsgBox('Conclua as operações no SIGEC. A desinstalação encerrará o servidor após aguardar as requisições em andamento. Os dados e backups serão preservados. Continuar?', mbConfirmation, MB_YESNO) <> IDYES then exit;
  end;
  Error := StopAndProtect;
  Result := Error = '';
  if not Result then MsgBox(Error, mbError, MB_OK);
end;

procedure ReleaseProtection;
begin
  if StartupStream <> nil then begin StartupStream.Free; StartupStream := nil; end;
  if MaintenanceStream <> nil then begin MaintenanceStream.Free; MaintenanceStream := nil; end;
end;

procedure DeinitializeSetup;
begin
  ReleaseProtection;
end;

procedure DeinitializeUninstall;
begin
  ReleaseProtection;
end;
