[Setup]
AppId={{AC6FD3D0-6CCA-4770-A6BB-93459F2C437C}
AppName=Tesla Vpn
AppVersion=1.0.5
DefaultDirName={localappdata}\Programs\TeslaVpn
DefaultGroupName=Tesla Vpn
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
OutputDir=..\artifacts\windows
OutputBaseFilename=TeslaVpn-1.0.5-Windows-x64-Setup
SetupIconFile=build\icon.ico
UninstallDisplayIcon={app}\TeslaVpn.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Files]
Source: "..\artifacts\windows\TeslaVpn\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Tesla Vpn"; Filename: "{app}\TeslaVpn.exe"
Name: "{autodesktop}\Tesla Vpn"; Filename: "{app}\TeslaVpn.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Run]
Filename: "{app}\TeslaVpn.exe"; Description: "Launch Tesla Vpn"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{app}\TeslaVpn.exe"; Parameters: "--restore-proxy"; Flags: runhidden waituntilterminated skipifdoesntexist
