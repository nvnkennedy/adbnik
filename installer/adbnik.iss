; Inno Setup 6 — compile after PyInstaller has built dist\Adbnik\
;   ISCC.exe installer\adbnik.iss
; Or: powershell -File scripts\build_installer.ps1
;
; Download Inno Setup: https://jrsoftware.org/isdl.php
;
; Authenticode (production / enterprise): sign the generated Adbnik_Setup_*.exe after compile,
; or configure Inno's Sign Tools — see docs/WINDOWS_CODE_SIGNING.md in the published repo.

#define MyAppName "Adbnik"
#define MyAppVersion "0.2.0"
#define MyAppPublisher "Adbnik contributors"
#define MyAppExeName "Adbnik.exe"
; Fixed AppId so upgrades replace the same install (generate a new GUID if you fork the app)
#define MyAppId "{{C4D8E1F2-9A3B-4C5D-8E6F-1A2B3C4D5E6F}"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL=https://github.com/
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=..\dist_installer
OutputBaseFilename=Adbnik_Setup_{#MyAppVersion}
SetupIconFile=..\assets\adbnik.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; Prefer x64compatible over deprecated x64 (Inno Setup 6.3+)
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=no
PrivilegesRequired=admin
LicenseFile=..\LICENSE

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\Adbnik\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; PyInstaller onedir: nothing extra under {app} usually; user config stays in %USERPROFILE%\.adbnik.json
