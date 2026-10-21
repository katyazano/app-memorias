; Guion de instalación Inno Setup para Memorias de Gastos
#ifndef AppVersion
#define AppVersion "2.0.0"
#endif

[Setup]
AppId={{5D8B41A9-2E24-4B7C-A89E-75DF3650221E}
AppName=Memorias de Gastos
AppVersion={#AppVersion}
AppPublisher=Despacho de Arquitectura
DefaultDirName={localappdata}\Programs\MemoriasGastos
PrivilegesRequired=lowest
DefaultGroupName=Memorias de Gastos
OutputDir=dist
OutputBaseFilename=Instalador-Memorias-{#AppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
DisableProgramGroupPage=yes
DisableDirPage=no
UninstallDisplayIcon={app}\MemoriasGastos.exe
UninstallFilesDir={app}\uninst
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "dist\MemoriasGastos\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Memorias de Gastos\Memorias de Gastos"; Filename: "{app}\MemoriasGastos.exe"
Name: "{autoprograms}\Memorias de Gastos\Memorias de Gastos (Modo Depuración)"; Filename: "{app}\MemoriasGastos-Debug.exe"
Name: "{autoprograms}\Memorias de Gastos\Desinstalar Memorias de Gastos"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Memorias de Gastos"; Filename: "{app}\MemoriasGastos.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\MemoriasGastos.exe"; Description: "{cm:LaunchProgram,Memorias de Gastos}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; IMPORTANTE: Solo se limpian temporales generados en la carpeta del programa.
; Los datos de usuario (%LOCALAPPDATA%\MemoriasGastos: base de datos, comprobantes, respaldos)
; NUNCA se eliminan al desinstalar ni al actualizar.
Type: files; Name: "{app}\*.log"
Type: files; Name: "{app}\*.tmp"
