@echo off
REM =============================================================================
REM  backup_daily.bat — Backup diario automático de la base de datos del POS
REM  Ejecutado por una tarea programada de Windows creada durante la instalación.
REM
REM  Estrategia:
REM    - Copia los archivos de datos de MariaDB Portable al directorio de backups.
REM    - Retiene los últimos 7 backups; elimina los más antiguos.
REM    - Registra resultado en un log rotativo (máx 500 KB).
REM
REM  Variables de entorno esperadas (definidas en la tarea programada):
REM    KIOSCO_INSTALL_DIR  — directorio raíz de instalación (ej: C:\KioscoPOS)
REM =============================================================================

setlocal EnableDelayedExpansion

REM ---------------------------------------------------------------------------
REM  Configuración
REM ---------------------------------------------------------------------------
set "INSTALL_DIR=%KIOSCO_INSTALL_DIR%"
if "%INSTALL_DIR%"=="" set "INSTALL_DIR=C:\KioscoPOS"

set "MARIADB_DATA=%INSTALL_DIR%\vendor\mariadb\data"
set "BACKUP_DIR=%INSTALL_DIR%\backups"
set "LOG_FILE=%INSTALL_DIR%\backups\backup.log"
set "MAX_BACKUPS=7"

REM Timestamp para el nombre del archivo: YYYY-MM-DD_HH-MM
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set "DT=%%I"
set "TIMESTAMP=%DT:~0,4%-%DT:~4,2%-%DT:~6,2%_%DT:~8,2%-%DT:~10,2%"
set "BACKUP_PATH=%BACKUP_DIR%\db_%TIMESTAMP%"

REM ---------------------------------------------------------------------------
REM  Verificaciones previas
REM ---------------------------------------------------------------------------
if not exist "%MARIADB_DATA%" (
    call :log "ERROR" "Directorio de datos MariaDB no encontrado: %MARIADB_DATA%"
    exit /b 1
)

if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

REM ---------------------------------------------------------------------------
REM  Detener MariaDB para garantizar consistencia del backup
REM ---------------------------------------------------------------------------
call :log "INFO" "Iniciando backup — deteniendo servicio MariaDB..."
sc query KioscoPOS_MariaDB >nul 2>&1
if %errorlevel% equ 0 (
    sc stop KioscoPOS_MariaDB >nul 2>&1
    timeout /t 5 /nobreak >nul
    set "SERVICE_STOPPED=true"
) else (
    REM MariaDB se ejecuta como proceso, no como servicio
    taskkill /f /im mysqld.exe >nul 2>&1
    timeout /t 3 /nobreak >nul
    set "SERVICE_STOPPED=false"
)

REM ---------------------------------------------------------------------------
REM  Copiar directorio de datos
REM ---------------------------------------------------------------------------
call :log "INFO" "Copiando datos a: %BACKUP_PATH%"
xcopy /e /i /q /h "%MARIADB_DATA%" "%BACKUP_PATH%" >nul 2>&1

if %errorlevel% equ 0 (
    call :log "INFO" "Backup completado exitosamente: %BACKUP_PATH%"
) else (
    call :log "ERROR" "Fallo al copiar datos. Código de error: %errorlevel%"
)

REM ---------------------------------------------------------------------------
REM  Reiniciar MariaDB
REM ---------------------------------------------------------------------------
if "%SERVICE_STOPPED%"=="true" (
    sc start KioscoPOS_MariaDB >nul 2>&1
    call :log "INFO" "Servicio MariaDB reiniciado."
) else (
    start "" /min "%INSTALL_DIR%\vendor\mariadb\bin\mysqld.exe" --defaults-file="%INSTALL_DIR%\vendor\mariadb\my.ini"
    call :log "INFO" "Proceso MariaDB reiniciado."
)

REM ---------------------------------------------------------------------------
REM  Rotación: eliminar backups más antiguos que MAX_BACKUPS
REM ---------------------------------------------------------------------------
call :log "INFO" "Rotando backups (máx: %MAX_BACKUPS%)..."
set "COUNT=0"
for /f "delims=" %%D in ('dir /b /ad /o-d "%BACKUP_DIR%\db_*" 2^>nul') do (
    set /a COUNT+=1
    if !COUNT! gtr %MAX_BACKUPS% (
        call :log "INFO" "Eliminando backup antiguo: %%D"
        rd /s /q "%BACKUP_DIR%\%%D" >nul 2>&1
    )
)

call :log "INFO" "Backup diario finalizado. Total backups: !COUNT!"
endlocal
exit /b 0

REM ---------------------------------------------------------------------------
REM  Subrutina de logging con rotación básica (500 KB máx)
REM ---------------------------------------------------------------------------
:log
set "_LEVEL=%~1"
set "_MSG=%~2"
for /f "tokens=2 delims==" %%T in ('wmic os get localdatetime /value') do set "_NOW=%%T"
set "_TIMESTAMP=%_NOW:~0,4%-%_NOW:~4,2%-%_NOW:~6,2% %_NOW:~8,2%:%_NOW:~10,2%:%_NOW:~12,2%"
echo [%_TIMESTAMP%] [%_LEVEL%] %_MSG% >> "%LOG_FILE%"

REM Rotar log si supera 500 KB
for %%F in ("%LOG_FILE%") do (
    if %%~zF gtr 512000 (
        move /y "%LOG_FILE%" "%LOG_FILE%.old" >nul 2>&1
    )
)
exit /b 0
