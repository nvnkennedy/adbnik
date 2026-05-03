; Inno Setup — compile after PyInstaller: ..\\..\\dist\\Adbnik\\
; Example: ISCC.exe /DMyAppVersion=6.1.3 packaging\\windows\\adbnik.iss

#ifndef MyAppVersion
  #define MyAppVersion "6.1.3"
#endif

#define MyAppName "Adbnik"
#define MyAppExeName "Adbnik.exe"
#define MyAppPublisher "Adbnik contributors"
#define BuildDir "..\..\dist\Adbnik"

[Setup]
AppId={{A8F6E2D4-1C7B-4E9F-A3D2-8B6C4E1F9A7D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\{#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\..\installers
OutputBaseFilename=Adbnik-{#MyAppVersion}-Setup-unsigned
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
InfoBeforeFile=INSTALLER_NOTICE.txt
SetupIconFile=..\..\branding\favicon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#BuildDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
