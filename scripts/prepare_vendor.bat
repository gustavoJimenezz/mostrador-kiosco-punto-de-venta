@echo off
:: ============================================================
:: prepare_vendor.bat
:: Ticket 12 — Preparación del Bundle de Binarios (Portable MariaDB)
::
:: Descarga MariaDB ZIP para Windows x64, extrae los binarios
:: mínimos en vendor\mariadb y configura el datadir inicial.
::
:: Requisitos:
::   - Ejecutar como Administrador en Windows 11
::   - PowerShell 5+ disponible (incluido en Windows 11)
::   - Conexión a internet para la descarga inicial
::
:: Uso:
::   scripts\prepare_vendor.bat
:: ============================================================

setlocal EnableDelayedExpansion

:: --- Configuración -----------------------------------------------------------
set MARIADB_VERSION=11.4.5
set MARIADB_ARCH=winx64
set MARIADB_ZIP=mariadb-%MARIADB_VERSION%-win%MARIADB_ARCH%.zip
set DOWNLOAD_URL=https://downloads.mariadb.org/rest-api/mariadb/%MARIADB_VERSION%/%MARIADB_ZIP%
set VENDOR_DIR=%~dp0..\vendor
set MARIADB_DIR=%VENDOR_DIR%\mariadb
set DATA_DIR=%VENDOR_DIR%\mariadb\data
set LOGS_DIR=%VENDOR_DIR%\mariadb\logs
set TEMP_ZIP=%TEMP%\%MARIADB_ZIP%

echo.
echo ============================================================
echo  Preparacion de MariaDB Portable v%MARIADB_VERSION%
echo ============================================================
echo.

:: --- Verificar directorio vendor ---------------------------------------------
if not exist "%VENDOR_DIR%" mkdir "%VENDOR_DIR%"

:: --- Descarga ----------------------------------------------------------------
echo [1/5] Descargando MariaDB %MARIADB_VERSION% ZIP para Windows x64...
echo       URL: %DOWNLOAD_URL%
echo       Destino temporal: %TEMP_ZIP%
echo.

if exist "%TEMP_ZIP%" (
    echo       Archivo ya existe en temp, saltando descarga.
) else (
    powershell -NoProfile -Command ^
        "Invoke-WebRequest -Uri '%DOWNLOAD_URL%' -OutFile '%TEMP_ZIP%' -UseBasicParsing"
    if !errorlevel! neq 0 (
        echo [ERROR] Fallo la descarga. Verificar URL y conexion a internet.
        echo         Descarga manual: https://mariadb.org/download/
        exit /b 1
    )
)

:: --- Extracción --------------------------------------------------------------
echo [2/5] Extrayendo ZIP en vendor\...
if exist "%MARIADB_DIR%\.extracted" (
    echo       Extraccion previa detectada, saltando.
) else (
    powershell -NoProfile -Command ^
        "Expand-Archive -Path '%TEMP_ZIP%' -DestinationPath '%VENDOR_DIR%' -Force"
    if !errorlevel! neq 0 (
        echo [ERROR] Fallo la extraccion del ZIP.
        exit /b 1
    )

    :: Renombrar carpeta extraída (ej: mariadb-11.4.5-winx64 -> mariadb)
    if exist "%VENDOR_DIR%\mariadb-%MARIADB_VERSION%-win%MARIADB_ARCH%" (
        ren "%VENDOR_DIR%\mariadb-%MARIADB_VERSION%-win%MARIADB_ARCH%" mariadb
    )

    echo. > "%MARIADB_DIR%\.extracted"
)

:: --- Limpieza de archivos innecesarios ---------------------------------------
echo [3/5] Eliminando archivos innecesarios (reduccion de ~500MB a ~100MB)...

:: Carpetas completas a eliminar
set DIRS_TO_REMOVE=mysql-test sql-bench

for %%D in (%DIRS_TO_REMOVE%) do (
    if exist "%MARIADB_DIR%\%%D" (
        echo       Eliminando carpeta: %%D
        rd /s /q "%MARIADB_DIR%\%%D"
    )
)

:: Archivos de debug (simbolos PDB)
echo       Eliminando simbolos de debug (*.pdb)...
del /s /q "%MARIADB_DIR%\*.pdb" 2>nul

:: Archivos de idioma en share (conservar solo errmsg.sys del ingles)
if exist "%MARIADB_DIR%\share" (
    echo       Limpiando share\: conservando solo english\errmsg.sys...
    for /d %%L in ("%MARIADB_DIR%\share\*") do (
        if /i not "%%~nxL"=="english" (
            rd /s /q "%%L" 2>nul
        )
    )
)

:: Binarios de replicacion no necesarios para uso mono-terminal
set BINS_TO_REMOVE=mysqlbinlog.exe mysqlslap.exe mysqltest.exe ^
    mariadb-binlog.exe mariadb-slap.exe mariadb-test.exe ^
    mariadb-dump.exe mysqldump.exe replace.exe

for %%B in (%BINS_TO_REMOVE%) do (
    if exist "%MARIADB_DIR%\bin\%%B" (
        echo       Eliminando bin\%%B
        del /q "%MARIADB_DIR%\bin\%%B"
    )
)

:: Archivos .pdb dentro de lib/
del /s /q "%MARIADB_DIR%\lib\*.pdb" 2>nul

:: Documentacion HTML
if exist "%MARIADB_DIR%\docs" rd /s /q "%MARIADB_DIR%\docs"

echo       Limpieza completada.

:: --- Copiar my.ini -----------------------------------------------------------
echo [4/5] Instalando my.ini configurado para kiosco...
set MY_INI_SRC=%~dp0..\vendor\mariadb\my.ini
if exist "%MY_INI_SRC%" (
    :: El archivo ya esta en destino si el directorio es el mismo
    echo       my.ini ya presente en vendor\mariadb\my.ini
) else (
    echo [WARN] No se encontro vendor\mariadb\my.ini — copiar manualmente.
)

:: Crear directorio de datos y logs
if not exist "%DATA_DIR%" mkdir "%DATA_DIR%"
if not exist "%LOGS_DIR%" mkdir "%LOGS_DIR%"

:: --- Inicializar datadir -----------------------------------------------------
echo [5/5] Inicializando datadir con mysql_install_db.exe...
if exist "%DATA_DIR%\mysql" (
    echo       Datadir ya inicializado, saltando.
) else (
    "%MARIADB_DIR%\bin\mysql_install_db.exe" --datadir="%DATA_DIR%" --password=""
    if !errorlevel! neq 0 (
        echo [ERROR] Fallo la inicializacion del datadir.
        exit /b 1
    )
    echo       Datadir inicializado correctamente.
)

:: --- Verificación de tamaño --------------------------------------------------
echo.
echo Verificando tamano de vendor\mariadb...
powershell -NoProfile -Command ^
    "$size = (Get-ChildItem '%MARIADB_DIR%' -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB; Write-Host ('  Tamano actual: {0:N0} MB' -f $size); if ($size -gt 120) { Write-Host '  [WARN] Supera el limite de 120MB definido en el DoD.' } else { Write-Host '  [OK] Dentro del limite de 120MB.' }"

:: --- Resumen -----------------------------------------------------------------
echo.
echo ============================================================
echo  Preparacion completada.
echo.
echo  Para iniciar MariaDB:
echo    vendor\mariadb\bin\mysqld.exe --defaults-file=vendor\mariadb\my.ini
echo.
echo  Para conectar (otra terminal):
echo    vendor\mariadb\bin\mysql.exe -u root -p --port=3306
echo ============================================================
echo.

endlocal
exit /b 0
