; Wield's Windows installer (Inno Setup 6, free: https://jrsoftware.org/isinfo.php).
;
; Built by .github/workflows/build.yml from the PyInstaller folder:
;   iscc /DAppVersion=1.3.0 /DSourceDir=<repo>\dist\Wield installer\Wield.iss
;
; - Installs for the current user (no admin password), like VS Code's
;   user installer, into %LOCALAPPDATA%\Programs\Wield
; - Start-menu entry, a desktop icon (a tick box, on by default), and an
;   uninstaller in Windows' "Installed apps"
; - Running a newer setup over an older one updates it in place
; - Gestures, studios and settings live in %APPDATA%\Wield and are kept
;   on update and uninstall

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\dist\Wield"
#endif

#define AppName "Wield"
#define AppExe "Wield.exe"

[Setup]
; Never change AppId: it's how Windows recognises an update of the same app.
AppId={{644cecf1-3acc-4aef-a2d0-af8c985da78e}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Praveena Kiran
AppPublisherURL=https://praveena-kiran.github.io/Wield/
AppSupportURL=https://github.com/Praveena-Kiran/Wield/issues
AppUpdatesURL=https://github.com/Praveena-Kiran/Wield/releases
DefaultDirName={localappdata}\Programs\{#AppName}
DisableProgramGroupPage=yes
DisableDirPage=auto
PrivilegesRequired=lowest
OutputDir=..\installer-output
OutputBaseFilename=Wield-Setup
SetupIconFile=..\assets\icons\wield.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
WizardStyle=modern
Compression=lzma2
SolidCompression=yes
; Close a running Wield before replacing its files.
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Put a {#AppName} icon on the desktop"; GroupDescription: "Shortcuts:"

[InstallDelete]
; Old library files from a previous version (PyInstaller names change).
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
; Uninstalling also removes "Start Wield when I sign in" (backend/startup.py).
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: none; ValueName: "{#AppName}"; Flags: uninsdeletevalue dontcreatekey

[Run]
Filename: "{app}\{#AppExe}"; Description: "Open {#AppName} now"; Flags: nowait postinstall skipifsilent
