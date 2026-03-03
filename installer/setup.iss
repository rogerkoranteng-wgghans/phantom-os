; Phantom OS — Inno Setup Script
; Requires Inno Setup 6.x  https://jrsoftware.org/isinfo.php
; Run from repo root:  iscc installer\setup.iss

#define AppName      "Phantom OS"
#define AppVersion   "1.0.0"
#define AppPublisher "Phantom OS"
#define AppURL       "https://github.com/your-org/phantom-os"
#define AppExeName   "PhantomOS.exe"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
LicenseFile=..\LICENSE
OutputDir=.\Output
OutputBaseFilename=PhantomOS-Setup
SetupIconFile=.\phantom_icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64

; Minimum Windows 10 1903
MinVersion=10.0.18362

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
english.ApiKeyLabel=Gemini API Key:
english.ApiKeyDesc=Enter your Google Gemini API key. Get one free at https://aistudio.google.com/

[Code]
var
  ApiKeyPage: TInputQueryWizardPage;

procedure InitializeWizard();
begin
  ApiKeyPage := CreateInputQueryPage(
    wpSelectDir,
    'Gemini API Key',
    'Required for Phantom OS to work',
    'Enter your Gemini API Key. You can get one for free at aistudio.google.com');
  ApiKeyPage.Add('API Key:', False);
  // Try to pre-fill from existing config
  ApiKeyPage.Values[0] := '';
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ConfigDir, ConfigFile, ApiKey: String;
  Lines: TArrayOfString;
begin
  if CurStep = ssPostInstall then begin
    ApiKey := ApiKeyPage.Values[0];
    if ApiKey <> '' then begin
      ConfigDir := ExpandConstant('{userappdata}\PhantomOS');
      ForceDirectories(ConfigDir);
      ConfigFile := ConfigDir + '\config.env';
      SetArrayLength(Lines, 3);
      Lines[0] := 'GEMINI_API_KEY=' + ApiKey;
      Lines[1] := 'REDIS_URL=embedded';
      Lines[2] := 'GOOGLE_CLOUD_PROJECT=phantom-os';
      SaveStringsToFile(ConfigFile, Lines, False);
    end;
  end;
end;

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startupicon"; Description: "Start Phantom OS with Windows"; GroupDescription: "Startup:"; Flags: unchecked

[Files]
; Launcher executable (standalone single exe)
Source: "..\dist\PhantomOS.exe";   DestDir: "{app}"; Flags: ignoreversion

; Backend (folder with all DLLs and deps)
Source: "..\dist\PhantomBackend\*"; DestDir: "{app}\PhantomBackend"; Flags: ignoreversion recursesubdirs createallsubdirs

; Agent (folder with all DLLs and deps)
Source: "..\dist\PhantomAgent\*";   DestDir: "{app}\PhantomAgent";   Flags: ignoreversion recursesubdirs createallsubdirs

; Default config template
Source: "config.env.template";     DestDir: "{app}"; DestName: "config.env.template"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}";                         Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\{#AppExeName}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}";   Filename: "{uninstallexe}"
Name: "{commondesktop}\{#AppName}";                 Filename: "{app}\{#AppExeName}"; Tasks: desktopicon
Name: "{userstartup}\{#AppName}";                   Filename: "{app}\{#AppExeName}"; Tasks: startupicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\PhantomBackend"
Type: filesandordirs; Name: "{app}\PhantomAgent"
