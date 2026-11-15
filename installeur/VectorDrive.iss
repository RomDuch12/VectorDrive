; Installateur Windows de VectorDrive (Inno Setup 6).
; Compilé par outils/publier.py :  ISCC /DVersion=x.y.z installeur\VectorDrive.iss
; Entrée : dist\VectorDrive (sortie PyInstaller) ; sortie : dist\installeur.
;
; Installation par utilisateur par défaut (pas de droits administrateur,
; mises à jour silencieuses sans UAC) ; « pour tous les utilisateurs »
; possible depuis l'assistant. Association du seul format .vdz : les .vnd
; restent à TypeEdit.

#ifndef Version
  #define Version "0.0.0"
#endif

#ifndef Publisher
#define Publisher "VectorDrive"
#endif
#ifndef Edition
#define Edition ""
#endif
#ifndef AppSrc
#define AppSrc "..\dist\VectorDrive"
#endif
[Setup]
AppId={{6B0F3C1E-5A0D-4C8B-9E57-2D1B7F4A9C31}
AppName=VectorDrive
AppVersion={#Version}
AppVerName=VectorDrive {#Version}
AppPublisher={#Publisher}
VersionInfoVersion={#Version}
VersionInfoProductName=VectorDrive
DefaultDirName={autopf}\VectorDrive
DefaultGroupName=VectorDrive
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist\installeur
OutputBaseFilename=VectorDrive{#Edition}-{#Version}-setup
SetupIconFile=..\vectordrive\ressources\vectordrive.ico
UninstallDisplayIcon={app}\VectorDrive.exe
UninstallDisplayName=VectorDrive
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=force
RestartApplications=no
ChangesAssociations=yes

[Languages]
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
fr.AssocVdz=Ouvrir les dessins .vdz avec VectorDrive
en.AssocVdz=Open .vdz drawings with VectorDrive
fr.DocVdz=Dessin VectorDrive
en.DocVdz=VectorDrive drawing

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "assoc"; Description: "{cm:AssocVdz}"

[InstallDelete]
; une mise à jour remplace entièrement le dossier _internal (bibliothèques)
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "{#AppSrc}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\VectorDrive"; Filename: "{app}\VectorDrive.exe"
Name: "{autodesktop}\VectorDrive"; Filename: "{app}\VectorDrive.exe"; Tasks: desktopicon

[Registry]
Root: HKA; Subkey: "Software\Classes\.vdz"; ValueType: string; ValueName: ""; ValueData: "VectorDrive.Document"; Flags: uninsdeletevalue; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\VectorDrive.Document"; ValueType: string; ValueName: ""; ValueData: "{cm:DocVdz}"; Flags: uninsdeletekey; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\VectorDrive.Document\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\VectorDrive.exe,0"; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\VectorDrive.Document\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\VectorDrive.exe"" ""%1"""; Tasks: assoc

[Run]
Filename: "{app}\VectorDrive.exe"; Description: "{cm:LaunchProgram,VectorDrive}"; Flags: nowait postinstall skipifsilent
; mise à jour silencieuse lancée depuis VectorDrive : relance automatique
; (/NORELAUNCH : installation silencieuse sans relance, pour les essais)
Filename: "{app}\VectorDrive.exe"; Flags: nowait; Check: ShouldRelaunch

[Code]
function CmdLineParamExists(const Value: string): Boolean;
var
  I: Integer;
begin
  Result := False;
  for I := 1 to ParamCount do
    if CompareText(ParamStr(I), Value) = 0 then
    begin
      Result := True;
      Exit;
    end;
end;

function ShouldRelaunch: Boolean;
begin
  Result := WizardSilent and not CmdLineParamExists('/NORELAUNCH');
end;
