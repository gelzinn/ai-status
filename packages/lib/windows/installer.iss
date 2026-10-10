#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{B54847A0-253A-43C3-BCA9-46E1AC4E5266}
AppName=AI Status
AppVersion={#AppVersion}
AppPublisher=gelzinn
AppPublisherURL=https://github.com/gelzinn/ai-status
DefaultDirName={localappdata}\Programs\AI Status
DefaultGroupName=AI Status
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
OutputDir=..\..\..\dist
OutputBaseFilename=ai-status-{#AppVersion}-windows-x64-setup
Compression=lzma2/ultra64
LZMAUseSeparateProcess=yes
LZMANumBlockThreads=1
SolidCompression=yes
CloseApplications=yes
RestartApplications=no
UninstallDisplayIcon={app}\ai-status.exe
LicenseFile=..\..\..\LICENSE
WizardStyle=modern
SetupIconFile=..\..\..\build\windows-app.ico

[Tasks]
Name: "autostart"; Description: "Start AI Status when I sign in to Windows"; Flags: unchecked

[Files]
Source: "..\..\..\dist\ai-status\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\AI Status"; Filename: "{app}\ai-status.exe"; Parameters: "tray"

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "AI Status"; ValueData: """{app}\ai-status.exe"" tray"; Tasks: autostart; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: none; ValueName: "AI Status"; Flags: uninsdeletevalue

[Run]
Filename: "{app}\ai-status.exe"; Parameters: "tray"; Description: "Launch AI Status"; Flags: nowait postinstall skipifsilent
