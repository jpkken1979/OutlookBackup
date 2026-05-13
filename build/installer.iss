; UNS Outlook Backup v3.0 - Inno Setup Installer Script

#define MyAppName "UNS \u30e1\u30fc\u30eb\u30d0\u30c3\u30af\u30a2\u30c3\u30d7"
#define MyAppNameASCII "UNS Outlook Backup"
#define MyAppVersion "3.1.1"
#define MyAppPublisher "\u30e6\u30cb\u30d0\u30fc\u30b5\u30eb\u4f01\u753b\u682a\u5f0f\u4f1a\u793e"
#define MyAppURL "https://www.uns-kikaku.com"
#define MyAppExeName "UNS-Outlook-Backup.exe"

[Setup]
AppId={{C1D7F2E4-5E6F-6F7B-BD9F-3F4F5A6B7C8D}}
AppName={#MyAppNameASCII}
AppVersion={#MyAppVersion}
AppVerName={#MyAppNameASCII} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={autopf}\UNS-Kikaku\Outlook-Backup
DefaultGroupName=UNS-Kikaku
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=UNS-Outlook-Backup-Setup-{#MyAppVersion}
SetupIconFile=..\assets\icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
VersionInfoVersion={#MyAppVersion}

[Languages]
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
Source: "..\dist\UNS-Outlook-Backup.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\docs\INSTRUCCIONES.md"; DestDir: "{app}"; Flags: ignoreversion isreadme
; WebView2 evergreen bootstrapper (~1.7MB) \u2014 Fase 2 plan v3.2 (decision 2026-05-13).
; Se copia a {tmp} y se borra al terminar. Solo se ejecuta si Code.WebView2NeedsInstall = True.
; El archivo NO esta en git (ver .gitignore *.exe). Descargar antes del build:
;   curl -L -o redist/MicrosoftEdgeWebview2Setup.exe https://go.microsoft.com/fwlink/p/?LinkId=2124703
Source: "..\redist\MicrosoftEdgeWebview2Setup.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall; Check: WebView2NeedsInstall

[Icons]
Name: "{autoprograms}\{#MyAppNameASCII}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autoprograms}\Uninstall {#MyAppNameASCII}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppNameASCII}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Instalar WebView2 Runtime ANTES de ofrecer launch del programa.
; StatusMsg en japones (la app es localizada para UNS-Kikaku).
Filename: "{tmp}\MicrosoftEdgeWebview2Setup.exe"; Parameters: "/silent /install"; StatusMsg: "WebView2 \u30e9\u30f3\u30bf\u30a4\u30e0\u3092\u30a4\u30f3\u30b9\u30c8\u30fc\u30eb\u4e2d..."; Check: WebView2NeedsInstall
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppNameASCII, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "schtasks"; Parameters: "/Delete /TN ""UNS-Outlook-Backup-Auto"" /F"; Flags: runhidden; RunOnceId: "DelTask"

[Code]
{ Fase 2 plan v3.2: deteccion del runtime WebView2 antes de bundlear bootstrapper.
  GUID canonico publicado por Microsoft (ver src/runtime_check.py). }
function WebView2NeedsInstall: Boolean;
var
  Version: String;
begin
  Result := True;
  { Check 1: HKLM 32-bit (machine-wide install via 32-bit installer) }
  if RegQueryStringValue(HKEY_LOCAL_MACHINE,
    'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}',
    'pv', Version) and (Version <> '') and (Version <> '0.0.0.0') then
  begin
    Result := False;
    Exit;
  end;
  { Check 2: HKLM 64-bit (machine-wide install via 64-bit installer) }
  if RegQueryStringValue(HKEY_LOCAL_MACHINE,
    'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}',
    'pv', Version) and (Version <> '') and (Version <> '0.0.0.0') then
  begin
    Result := False;
    Exit;
  end;
  { Check 3: HKCU (per-user install, comun en empresas con politica restrictiva) }
  if RegQueryStringValue(HKEY_CURRENT_USER,
    'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}',
    'pv', Version) and (Version <> '') and (Version <> '0.0.0.0') then
  begin
    Result := False;
    Exit;
  end;
end;
