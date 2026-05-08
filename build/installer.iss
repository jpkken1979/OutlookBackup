; UNS Outlook Backup v3.0 - Inno Setup Installer Script

#define MyAppName "UNS \u30e1\u30fc\u30eb\u30d0\u30c3\u30af\u30a2\u30c3\u30d7"
#define MyAppNameASCII "UNS Outlook Backup"
#define MyAppVersion "3.1.0"
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
Name: "webview2"; Description: "WebView2 Runtime (\u5fc5\u8981\u306a\u5834\u5408\u30a4\u30f3\u30b9\u30c8\u30fc\u30eb)"; GroupDescription: "Components:"; Flags: unchecked

[Files]
Source: "..\dist\UNS-Outlook-Backup.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\docs\INSTRUCCIONES.md"; DestDir: "{app}"; Flags: ignoreversion isreadme

[Icons]
Name: "{autoprograms}\{#MyAppNameASCII}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autoprograms}\Uninstall {#MyAppNameASCII}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppNameASCII}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppNameASCII, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "schtasks"; Parameters: "/Delete /TN ""UNS-Outlook-Backup-Auto"" /F"; Flags: runhidden; RunOnceId: "DelTask"
