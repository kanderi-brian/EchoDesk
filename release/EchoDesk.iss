#define MyAppName "EchoDesk"
#ifndef MyAppVersion
  #define MyAppVersion "3.2.0"
#endif
#define MyAppPublisher "EchoDesk AI"
#define MyAppExeName "EchoDesk.exe"

[Setup]
AppId={{C53D3A45-B7BA-4C5A-9328-D90E93C0723A}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\EchoDesk
DefaultGroupName=EchoDesk
OutputDir=..\dist
OutputBaseFilename=EchoDesk-Setup-{#MyAppVersion}
SetupIconFile=..\assets\echodesk.ico
UninstallDisplayIcon={app}\EchoDesk.exe
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible

[Files]
Source: "..\dist\EchoDesk\EchoDesk.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autodesktop}\EchoDesk"; Filename: "{app}\EchoDesk.exe"; Tasks: desktopicon
Name: "{autoprograms}\EchoDesk\EchoDesk"; Filename: "{app}\EchoDesk.exe"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked
Name: "startup"; Description: "Launch EchoDesk when I sign in"; GroupDescription: "Startup:"; Flags: checkedonce

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "EchoDesk"; ValueData: "\"{app}\EchoDesk.exe\""; Tasks: startup; Flags: uninsdeletevalue

[Run]
Filename: "{app}\EchoDesk.exe"; Description: "Launch EchoDesk"; Flags: nowait postinstall skipifsilent
