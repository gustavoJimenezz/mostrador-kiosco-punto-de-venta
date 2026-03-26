; =============================================================================
;  installer.iss — Script de Inno Setup para Kiosco POS
;
;  Genera: Instalar_Kiosco_POS.exe
;
;  Contenido del instalador:
;    - POS.exe (onefile) o carpeta POS.dist/ (standalone)
;    - vendor/mariadb/         (MariaDB Portable, preparado en Ticket 5.2)
;    - config/database.ini     (configuración inicial de la DB)
;    - installer/scripts/backup_daily.bat
;
;  Acciones post-instalación:
;    - Acceso directo en escritorio y menú inicio
;    - Regla de firewall para MariaDB (puerto 3306, solo si multi-caja)
;    - Tarea programada "Kiosco POS - Backup Diario" via schtasks.exe
;    - Permisos de escritura sobre la carpeta de datos
;
;  Requisitos:
;    - Inno Setup 6.3+  (https://jrsoftware.org/isinfo.php)
;    - build.bat ejecutado previamente (genera dist\POS.dist\ o dist\POS.exe)
;    - vendor\mariadb\ preparado (Ticket 5.2)
;
;  Uso:
;    1. Ejecutar build.bat para generar la compilación Nuitka en dist/
;    2. Preparar vendor/mariadb/ con el bundle de MariaDB Portable
;    3. Compilar este .iss desde la raíz del proyecto:
;         iscc installer\installer.iss
;    4. El instalador queda en: dist\Instalar_Kiosco_POS.exe
; =============================================================================

#define MyAppName        "Kiosco POS"
#define MyAppVersion     "1.0.0"
#define MyAppPublisher   "Mostrador Kiosco"
#define MyAppURL         ""
#define MyAppExeName     "POS.exe"
#define MyAppId          "{{A7F3C2E1-84B0-4D9A-B5F2-1E6C3A8D0F72}"
#define MyOutputDir      "..\dist"
#define MySourceDir      ".."
#define MultiCajaEnabled 0   ; Cambiar a 1 para habilitar regla de firewall multi-caja

; =============================================================================
[Setup]
; =============================================================================

AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; Directorio de instalación por defecto
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes

; Requiere privilegios de administrador para instalar
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=

; Salida
OutputDir={#MyOutputDir}
OutputBaseFilename=Instalar_Kiosco_POS
SetupIconFile={#MySourceDir}\installer\assets\icon.ico

; Compresión LZMA2 máxima para reducir tamaño del instalador
Compression=lzma2/ultra64
SolidCompression=yes
LZMANumBlockThreads=4

; Interfaz visual
WizardStyle=modern
WizardSizePercent=120
WizardImageFile={#MySourceDir}\installer\assets\banner.bmp

; Registro de desinstalación
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName} {#MyAppVersion}

; Reinicio del sistema: solo si es absolutamente necesario
RestartIfNeededByRun=no

; Arquitectura objetivo: solo 64-bit
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; Versión mínima de Windows: Windows 10 (10.0)
MinVersion=10.0

; =============================================================================
[Languages]
; =============================================================================

Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

; =============================================================================
[Messages]
; =============================================================================

; Mensajes personalizados en español
spanish.WelcomeLabel1=Bienvenido al instalador de [name]
spanish.WelcomeLabel2=Este asistente instalar� [name/ver] en su equipo.%n%nSe recomienda cerrar todas las aplicaciones antes de continuar.
spanish.FinishedHeadingLabel=Instalaci�n completada
spanish.FinishedLabelNoIcons=[name] fue instalado correctamente en su equipo.

; =============================================================================
[CustomMessages]
; =============================================================================

spanish.InstallMultiCaja=Instalar regla de firewall para operaci�n multi-caja (puerto 3306)
spanish.BackupTaskCreated=Tarea de backup diario creada correctamente.
spanish.BackupTaskFailed=Advertencia: no se pudo crear la tarea de backup. Crearla manualmente si es necesario.

; =============================================================================
[Tasks]
; =============================================================================

; Acceso directo en escritorio (seleccionado por defecto)
Name: "desktopicon"; Description: "Crear acceso directo en el {cm:DesktopFolder}"; \
    GroupDescription: "Accesos directos:"; Flags: checkedonce

; =============================================================================
[Files]
; =============================================================================

; --- Ejecutable principal ---
; Modo standalone (carpeta POS.dist/): incluir toda la carpeta
Source: "{#MySourceDir}\dist\POS.dist\*"; \
    DestDir: "{app}"; \
    Flags: ignoreversion recursesubdirs createallsubdirs; \
    Check: IsStandaloneMode

; Modo onefile (POS.exe único)
Source: "{#MySourceDir}\dist\POS.exe"; \
    DestDir: "{app}"; \
    Flags: ignoreversion; \
    Check: IsOnefileMode

; --- MariaDB Portable (preparado en Ticket 5.2) ---
Source: "{#MySourceDir}\vendor\mariadb\*"; \
    DestDir: "{app}\vendor\mariadb"; \
    Flags: ignoreversion recursesubdirs createallsubdirs

; --- Configuración inicial de la base de datos ---
Source: "{#MySourceDir}\config\database.ini"; \
    DestDir: "{app}\config"; \
    Flags: ignoreversion onlyifdoesntexist

; --- Script de backup diario ---
Source: "{#MySourceDir}\installer\scripts\backup_daily.bat"; \
    DestDir: "{app}\scripts"; \
    Flags: ignoreversion

; =============================================================================
[Dirs]
; =============================================================================

; Carpeta de datos: permisos de escritura para Usuarios (no solo Administradores)
Name: "{app}\data";         Permissions: users-modify
Name: "{app}\backups";      Permissions: users-modify
Name: "{app}\config";       Permissions: users-modify
Name: "{app}\logs";         Permissions: users-modify

; =============================================================================
[Icons]
; =============================================================================

; Menú Inicio
Name: "{group}\{#MyAppName}"; \
    Filename: "{app}\{#MyAppExeName}"; \
    WorkingDir: "{app}"; \
    IconFilename: "{app}\{#MyAppExeName}"

Name: "{group}\Desinstalar {#MyAppName}"; \
    Filename: "{uninstallexe}"

; Escritorio (condicional según tarea elegida por el usuario)
Name: "{autodesktop}\{#MyAppName}"; \
    Filename: "{app}\{#MyAppExeName}"; \
    WorkingDir: "{app}"; \
    IconFilename: "{app}\{#MyAppExeName}"; \
    Tasks: desktopicon

; =============================================================================
[Registry]
; =============================================================================

; Registrar la ruta de instalación para que otros scripts la encuentren
Root: HKLM; \
    Subkey: "SOFTWARE\{#MyAppPublisher}\{#MyAppName}"; \
    ValueType: string; ValueName: "InstallDir"; \
    ValueData: "{app}"; \
    Flags: uninsdeletekey

Root: HKLM; \
    Subkey: "SOFTWARE\{#MyAppPublisher}\{#MyAppName}"; \
    ValueType: string; ValueName: "Version"; \
    ValueData: "{#MyAppVersion}"; \
    Flags: uninsdeletekey

; =============================================================================
[Run]
; =============================================================================

; ---- Regla de firewall para multi-caja (puerto 3306) ----
; Solo se ejecuta si MultiCajaEnabled = 1 (definido al compilar con /DMultiCajaEnabled=1)
#if MultiCajaEnabled == 1
Filename: "netsh"; \
    Parameters: "advfirewall firewall add rule name=""Kiosco POS MariaDB"" dir=in action=allow protocol=TCP localport=3306"; \
    Flags: runhidden waituntilterminated; \
    StatusMsg: "Configurando regla de firewall para MariaDB..."; \
    RunOnceId: "FirewallRule3306"
#endif

; ---- Tarea programada: Backup Diario ----
; Crea la tarea "Kiosco POS - Backup Diario" que se ejecuta a las 02:00 AM.
; Pasa KIOSCO_INSTALL_DIR como variable de entorno al script.
Filename: "schtasks.exe"; \
    Parameters: "/create /tn ""Kiosco POS - Backup Diario"" /tr ""{app}\scripts\backup_daily.bat"" /sc daily /st 02:00 /ru SYSTEM /rl highest /f /v1 /z /env KIOSCO_INSTALL_DIR={app}"; \
    Flags: runhidden waituntilterminated; \
    StatusMsg: "Creando tarea de backup diario..."; \
    RunOnceId: "BackupDailyTask"

; ---- Abrir la aplicación al finalizar (opcional, no seleccionado por defecto) ----
Filename: "{app}\{#MyAppExeName}"; \
    Description: "Iniciar {#MyAppName} ahora"; \
    Flags: nowait postinstall skipifsilent; \
    WorkingDir: "{app}"

; =============================================================================
[UninstallRun]
; =============================================================================

; Eliminar tarea programada de backup al desinstalar
Filename: "schtasks.exe"; \
    Parameters: "/delete /tn ""Kiosco POS - Backup Diario"" /f"; \
    Flags: runhidden waituntilterminated; \
    RunOnceId: "RemoveBackupTask"

; Eliminar regla de firewall al desinstalar (si fue creada)
#if MultiCajaEnabled == 1
Filename: "netsh"; \
    Parameters: "advfirewall firewall delete rule name=""Kiosco POS MariaDB"""; \
    Flags: runhidden waituntilterminated; \
    RunOnceId: "RemoveFirewallRule"
#endif

; =============================================================================
[UninstallDelete]
; =============================================================================

; Eliminar carpeta de logs generados en tiempo de ejecución (no son datos del usuario)
Type: filesandordirs; Name: "{app}\logs"

; NO eliminar {app}\data ni {app}\backups automáticamente para proteger datos del cliente.
; El desinstalador deja esas carpetas y las elimina solo si están vacías.
Type: dirifempty; Name: "{app}\data"
Type: dirifempty; Name: "{app}\backups"
Type: dirifempty; Name: "{app}"

; =============================================================================
[Code]
; =============================================================================

{
  Funciones Pascal Script de Inno Setup para:
    - Detectar automáticamente si se compiló en modo standalone o onefile.
    - Mostrar advertencia al desinstalar si existen datos en {app}\data.
}

{ ---------------------------------------------------------------------------
  IsStandaloneMode / IsOnefileMode
  Verifica qué artefacto de compilación existe en dist\ para incluir
  los archivos correctos según el modo de compilación Nuitka utilizado.
  --------------------------------------------------------------------------- }
function IsStandaloneMode: Boolean;
begin
  Result := DirExists(ExpandConstant('{src}\..\dist\POS.dist'));
end;

function IsOnefileMode: Boolean;
begin
  Result := FileExists(ExpandConstant('{src}\..\dist\POS.exe'))
            and not IsStandaloneMode;
end;

{ ---------------------------------------------------------------------------
  InitializeSetup
  Validación previa al inicio del wizard.
  --------------------------------------------------------------------------- }
function InitializeSetup: Boolean;
var
  HasStandalone: Boolean;
  HasOnefile: Boolean;
begin
  HasStandalone := IsStandaloneMode;
  HasOnefile    := IsOnefileMode;

  if not HasStandalone and not HasOnefile then
  begin
    MsgBox(
      'No se encontró el artefacto de compilación.' + #13#10 +
      'Ejecute build.bat antes de compilar el instalador.' + #13#10 + #13#10 +
      'Esperado:  dist\POS.dist\  o  dist\POS.exe',
      mbError,
      MB_OK
    );
    Result := False;
    Exit;
  end;

  if not DirExists(ExpandConstant('{src}\..\vendor\mariadb')) then
  begin
    MsgBox(
      'No se encontró la carpeta vendor\mariadb.' + #13#10 +
      'Complete el Ticket 5.2 (Bundle de Binarios) antes de compilar el instalador.',
      mbError,
      MB_OK
    );
    Result := False;
    Exit;
  end;

  Result := True;
end;

{ ---------------------------------------------------------------------------
  InitializeUninstall
  Advertencia si existen datos en {app}\data antes de desinstalar.
  --------------------------------------------------------------------------- }
function InitializeUninstall: Boolean;
var
  DataDir: String;
  Confirm: Integer;
begin
  DataDir := ExpandConstant('{app}\data');

  if DirExists(DataDir) then
  begin
    Confirm := MsgBox(
      'La carpeta de datos (' + DataDir + ') contiene información del sistema.' + #13#10 +
      'La desinstalación NO eliminará esos datos.' + #13#10 + #13#10 +
      '¿Desea continuar con la desinstalación?',
      mbConfirmation,
      MB_YESNO or MB_DEFBUTTON2
    );

    if Confirm = IDNO then
    begin
      Result := False;
      Exit;
    end;
  end;

  Result := True;
end;

