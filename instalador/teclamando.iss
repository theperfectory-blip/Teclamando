; Instalador de Teclamando (Inno Setup 6). Lo arma instalador\construir.bat.
; Se instala para el usuario actual (sin pedir administrador) en %LOCALAPPDATA%\Programs\Teclamando.
; Lo tuyo (ajustes, palabras aprendidas) queda en %APPDATA%\Teclamando y no se borra al desinstalar.

#ifndef Version
  #define Version "1.0.4"
#endif
#define Navegacion "HKLM\SOFTWARE\Microsoft\Input\Settings\ControllerProcessor\ControllerToVKMapping"

[Setup]
AppId={{6E2B9C14-3F7A-4D58-9B1E-7A0C5D2F8E31}
AppName=Teclamando
AppVersion={#Version}
AppVerName=Teclamando {#Version}
AppPublisher=Teclamando
AppPublisherURL=https://github.com/theperfectory-blip/Teclamando
DefaultDirName={autopf}\Teclamando
DefaultGroupName=Teclamando
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
LicenseFile=..\LICENSE
SetupIconFile=..\icono.ico
UninstallDisplayIcon={app}\Teclamando.exe
UninstallDisplayName=Teclamando
OutputDir=salida
OutputBaseFilename=Teclamando-{#Version}-instalador
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "inicio"; Description: "Arrancar con Windows, en espera: se enciende con Back + Start (Share + Options en PlayStation)"
Name: "escritorio"; Description: "Acceso directo en el escritorio"; Flags: unchecked
Name: "sinnavegacion"; Description: "Que Windows NO mueva también el menú Inicio y la barra de tareas con el mando (evita que un botón haga dos cosas; pide permiso de administrador y reiniciar). Se deshace al desinstalar."; Flags: unchecked

[Files]
Source: "build\teclamando.dist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "LEEME.txt"; DestDir: "{app}"; Flags: ignoreversion isreadme
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\extras\desactivar_navegacion_windows.reg"; DestDir: "{app}\extras"; Flags: ignoreversion
Source: "..\extras\restaurar_navegacion_windows.reg"; DestDir: "{app}\extras"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Teclamando\Teclamando"; Filename: "{app}\Teclamando.exe"
Name: "{autoprograms}\Teclamando\Configurar otro mando (PlayStation, genérico)"; Filename: "{app}\Teclamando.exe"; Parameters: "--configurar"
Name: "{autoprograms}\Teclamando\Detener Teclamando"; Filename: "{sys}\taskkill.exe"; Parameters: "/im Teclamando.exe /f"; IconFilename: "{app}\Teclamando.exe"; Flags: runminimized
Name: "{autoprograms}\Teclamando\Léeme"; Filename: "{app}\LEEME.txt"
Name: "{userstartup}\Teclamando"; Filename: "{app}\Teclamando.exe"; Parameters: "espera"; Tasks: inicio
Name: "{autodesktop}\Teclamando"; Filename: "{app}\Teclamando.exe"; Tasks: escritorio

[Run]
Filename: "{sys}\reg.exe"; Parameters: "add ""{#Navegacion}"" /v Enabled /t REG_DWORD /d 0 /f"; Verb: "runas"; Flags: shellexec runhidden waituntilterminated; Tasks: sinnavegacion; StatusMsg: "Apagando la navegación de Windows con el mando..."
Filename: "{app}\Teclamando.exe"; Description: "Encender Teclamando ahora"; Flags: postinstall nowait skipifsilent

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/im Teclamando.exe /f"; Flags: runhidden; RunOnceId: "detener"
Filename: "{sys}\reg.exe"; Parameters: "delete ""{#Navegacion}"" /f"; Verb: "runas"; Flags: shellexec runhidden waituntilterminated; Tasks: sinnavegacion; RunOnceId: "navegacion"

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Codigo: Integer;
begin
  { al actualizar: cerrar la copia que esté corriendo }
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/im Teclamando.exe /f', '', SW_HIDE, ewWaitUntilTerminated, Codigo);
  Result := '';
end;

function NeedRestart(): Boolean;
begin
  { el cambio de la navegación de Windows recién vale después de reiniciar }
  Result := WizardIsTaskSelected('sinnavegacion');
end;
