; Inno-Setup-Skript für den Graph-Plotter-Installer.
; Wird von build_exe.py aufgerufen; die Werte unten sind nur Vorgaben für einen manuellen Aufruf.

#ifndef AppVersion
  #define AppVersion "0.0"
#endif
#ifndef SourceDir
  #define SourceDir "dist\GraphPlotter"
#endif
#ifndef OutputDir
  #define OutputDir "dist"
#endif
#ifndef IconFile
  #define IconFile "build\graph_plotter.ico"
#endif
#ifndef LicenseFile
  #define LicenseFile "LICENSE"
#endif

[Setup]
AppId={{8E4C2B7A-5D1F-4A3E-9C6B-2F7D1E0A4B93}
AppName=Graph Plotter
AppVersion={#AppVersion}
AppVerName=Graph Plotter {#AppVersion}
DefaultDirName={autopf}\Graph Plotter
DefaultGroupName=Graph Plotter
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\GraphPlotter.exe
SetupIconFile={#IconFile}
LicenseFile={#LicenseFile}
OutputDir={#OutputDir}
OutputBaseFilename=GraphPlotter_v{#AppVersion}_Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; Ohne Administratorrechte installierbar (dann nur für den aktuellen Benutzer)
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
ChangesAssociations=yes
; Läuft das Programm, bietet Setup an, es zu schließen (Name wird in graph_plotter/app.py angelegt)
AppMutex=GraphPlotterLaeuft
CloseApplications=yes

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "assoc"; Description: "Projektdateien (.gplot) mit Graph Plotter öffnen"; GroupDescription: "Dateizuordnung:"

[InstallDelete]
; Bei einem Update die Bibliotheken der alten Version vollständig entfernen, damit keine veralteten
; Dateien liegen bleiben (Einstellungen und Projekte liegen woanders und sind nicht betroffen).
Type: filesandordirs; Name: "{app}\_internal"
Type: filesandordirs; Name: "{app}\Lizenzen"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Graph Plotter"; Filename: "{app}\GraphPlotter.exe"
Name: "{group}\Anleitung"; Filename: "{app}\LIESMICH.txt"
Name: "{group}\Lizenz"; Filename: "{app}\LIZENZ.txt"
Name: "{group}\Graph Plotter deinstallieren"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Graph Plotter"; Filename: "{app}\GraphPlotter.exe"; Tasks: desktopicon

[Registry]
Root: HKA; Subkey: "Software\Classes\.gplot"; ValueType: string; ValueName: ""; ValueData: "GraphPlotter.Projekt"; Flags: uninsdeletevalue; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\GraphPlotter.Projekt"; ValueType: string; ValueName: ""; ValueData: "Graph-Plotter-Projekt"; Flags: uninsdeletekey; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\GraphPlotter.Projekt\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\GraphPlotter.exe,0"; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\GraphPlotter.Projekt\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\GraphPlotter.exe"" ""%1"""; Tasks: assoc

[Run]
Filename: "{app}\GraphPlotter.exe"; Description: "{cm:LaunchProgram,Graph Plotter}"; Flags: nowait postinstall skipifsilent
; Automatisches Update aus dem Programm (Setup läuft mit /SILENT): Programm danach wieder starten
Filename: "{app}\GraphPlotter.exe"; Flags: nowait runasoriginaluser; Check: WizardSilent
