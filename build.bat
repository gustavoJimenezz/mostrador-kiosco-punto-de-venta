@echo off
REM =============================================================================
REM  build.bat — Compilación del sistema POS con Nuitka
REM  Entorno requerido: Windows 11 + Python 3.12 + Poetry
REM
REM  Uso:
REM    build.bat              → compila con el modo definido en build_config.py
REM    build.bat --onefile    → fuerza modo ejecutable único
REM    build.bat --standalone → fuerza modo carpeta (arranque rápido en HDD)
REM    build.bat --help       → muestra esta ayuda
REM =============================================================================

setlocal EnableDelayedExpansion

REM --- Ayuda ------------------------------------------------------------------
if "%1"=="--help" (
    echo Uso: build.bat [--onefile ^| --standalone]
    echo.
    echo  --onefile     Genera POS.exe unico. Simple, pero lento en HDD.
    echo  --standalone  Genera carpeta POS.dist/. Arranque rapido en HDD/CPUs viejas.
    echo  Sin argumento usa el modo definido en build_config.py ^(BUILD_MODE^).
    echo.
    echo  Editar build_config.py para cambiar version, nombre, icono, etc.
    exit /b 0
)

REM --- Leer configuracion desde build_config.py ------------------------------
echo [1/5] Leyendo configuracion desde build_config.py...
for /f "usebackq delims=" %%i in (
    `poetry run python -c "import build_config as c; print(c.APP_NAME)"`
) do set APP_NAME=%%i

for /f "usebackq delims=" %%i in (
    `poetry run python -c "import build_config as c; print(c.APP_VERSION)"`
) do set APP_VERSION=%%i

for /f "usebackq delims=" %%i in (
    `poetry run python -c "import build_config as c; print(c.COMPANY_NAME)"`
) do set COMPANY_NAME=%%i

for /f "usebackq delims=" %%i in (
    `poetry run python -c "import build_config as c; print(c.PRODUCT_DESCRIPTION)"`
) do set PRODUCT_DESCRIPTION=%%i

for /f "usebackq delims=" %%i in (
    `poetry run python -c "import build_config as c; print(c.ENTRY_POINT)"`
) do set ENTRY_POINT=%%i

for /f "usebackq delims=" %%i in (
    `poetry run python -c "import build_config as c; print(c.OUTPUT_DIR)"`
) do set OUTPUT_DIR=%%i

for /f "usebackq delims=" %%i in (
    `poetry run python -c "import build_config as c; print(c.ICON_PATH)"`
) do set ICON_PATH=%%i

for /f "usebackq delims=" %%i in (
    `poetry run python -c "import build_config as c; print(c.BUILD_MODE)"`
) do set BUILD_MODE=%%i

for /f "usebackq delims=" %%i in (
    `poetry run python -c "import build_config as c; print(str(c.ENABLE_PYSIDE6_PLUGIN).lower())"`
) do set ENABLE_PYSIDE6=%%i

for /f "usebackq delims=" %%i in (
    `poetry run python -c "import build_config as c; print(str(c.WINDOWS_UAC_ADMIN).lower())"`
) do set UAC_ADMIN=%%i

for /f "usebackq delims=" %%i in (
    `poetry run python -c "import build_config as c; print(str(c.SHOW_MEMORY).lower())"`
) do set SHOW_MEM=%%i

for /f "usebackq delims=" %%i in (
    `poetry run python -c "import build_config as c; print(c.OPTIMIZATION_LEVEL)"`
) do set OPT_LEVEL=%%i

for /f "usebackq delims=" %%i in (
    `poetry run python -c "import build_config as c; print(str(c.DISABLE_CONSOLE).lower())"`
) do set NO_CONSOLE=%%i

REM --- Argumento de línea de comando sobreescribe BUILD_MODE -----------------
if "%1"=="--onefile"    set BUILD_MODE=onefile
if "%1"=="--standalone" set BUILD_MODE=standalone

REM --- Calcular nombre real de carpeta que genera Nuitka ---------------------
REM Nuitka nombra la carpeta segun el script de entrada (main.py -> main.dist),
REM no segun --output-filename. Esto se usa para el paso de copia post-build.
for %%F in (%ENTRY_POINT%) do set DIST_FOLDER=%%~nF.dist
set DIST_PATH=%OUTPUT_DIR%\%DIST_FOLDER%

echo     APP_NAME    : %APP_NAME%
echo     VERSION     : %APP_VERSION%
echo     ENTRY_POINT : %ENTRY_POINT%
echo     OUTPUT_DIR  : %OUTPUT_DIR%
echo     BUILD_MODE  : %BUILD_MODE%
echo.

REM --- Verificar que Nuitka este disponible -----------------------------------
echo [2/5] Verificando Nuitka...
poetry run python -m nuitka --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Nuitka no encontrado. Ejecuta: poetry add nuitka --group dev
    exit /b 1
)
echo     OK
echo.

REM --- Crear directorio de salida (y limpiar build anterior) ----------------
echo [3/5] Preparando directorio de salida: %OUTPUT_DIR%\...
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"
if "%BUILD_MODE%"=="standalone" (
    if exist "%DIST_PATH%" (
        echo     Limpiando build anterior: %DIST_PATH%\...
        rd /s /q "%DIST_PATH%"
    )
)
echo     OK
echo.

REM --- Construir flags de Nuitka --------------------------------------------
echo [4/5] Construyendo comando Nuitka...

set NUITKA_FLAGS=--standalone
set NUITKA_FLAGS=%NUITKA_FLAGS% --output-dir=%OUTPUT_DIR%
set NUITKA_FLAGS=%NUITKA_FLAGS% --output-filename=%APP_NAME%.exe

REM Modo de compilacion
if "%BUILD_MODE%"=="onefile" (
    set NUITKA_FLAGS=%NUITKA_FLAGS% --onefile
)

REM Plugin PySide6
if "%ENABLE_PYSIDE6%"=="true" (
    set NUITKA_FLAGS=%NUITKA_FLAGS% --enable-plugin=pyside6
)

REM Privilegios UAC
if "%UAC_ADMIN%"=="true" (
    set NUITKA_FLAGS=%NUITKA_FLAGS% --windows-uac-admin
)

REM Estadisticas de memoria
if "%SHOW_MEM%"=="true" (
    set NUITKA_FLAGS=%NUITKA_FLAGS% --show-memory
)

REM Nivel de optimizacion
set NUITKA_FLAGS=%NUITKA_FLAGS% --python-flag=no_asserts
if "%OPT_LEVEL%"=="2" (
    set NUITKA_FLAGS=%NUITKA_FLAGS% --lto=yes
) else (
    set NUITKA_FLAGS=%NUITKA_FLAGS% --lto=no
)

REM Deshabilitar consola (app GUI pura)
if "%NO_CONSOLE%"=="true" (
    set NUITKA_FLAGS=%NUITKA_FLAGS% --windows-console-mode=disable
)

REM SQLAlchemy usa decoradores que registran estrategias ORM al definir clases.
REM Nuitka elimina ese codigo como "muerto". Incluir el paquete completo evita esto.
set NUITKA_FLAGS=%NUITKA_FLAGS% --include-package=sqlalchemy.orm
set NUITKA_FLAGS=%NUITKA_FLAGS% --include-package=sqlalchemy.dialects.mysql

REM Metadatos del ejecutable
set NUITKA_FLAGS=%NUITKA_FLAGS% --product-name="%APP_NAME%"
set NUITKA_FLAGS=%NUITKA_FLAGS% --product-version=%APP_VERSION%
set NUITKA_FLAGS=%NUITKA_FLAGS% --company-name="%COMPANY_NAME%"
set NUITKA_FLAGS=%NUITKA_FLAGS% --file-description="%PRODUCT_DESCRIPTION%"

REM Icono del ejecutable (solo si el archivo existe)
if exist "%ICON_PATH%" (
    set NUITKA_FLAGS=%NUITKA_FLAGS% --windows-icon-from-ico="%ICON_PATH%"
) else (
    echo     ADVERTENCIA: Icono no encontrado en %ICON_PATH%, se compilara sin icono.
)

echo     Flags: %NUITKA_FLAGS%
echo.

REM --- Ejecutar Nuitka -------------------------------------------------------
echo [5/5] Compilando con Nuitka...
echo       Esto puede tardar varios minutos. No cerrar esta ventana.
echo.

set START_TIME=%TIME%
poetry run python -m nuitka %NUITKA_FLAGS% %ENTRY_POINT%

if %errorlevel% neq 0 (
    echo.
    echo ERROR: La compilacion fallo. Revisar la salida anterior.
    exit /b 1
)

REM --- Copiar recursos al output (solo en modo standalone) ------------------
if "%BUILD_MODE%"=="standalone" (
    echo.
    echo [Post-build] Copiando recursos a %DIST_PATH%\...

    REM vendor\mariadb (motor de base de datos portable)
    if not exist "vendor\mariadb\bin\mysqld.exe" (
        echo ADVERTENCIA: vendor\mariadb no encontrado o incompleto.
        echo              Ejecutar scripts\prepare_vendor.bat antes de compilar.
    ) else (
        powershell -NoProfile -Command ^
            "Copy-Item -Path 'vendor\mariadb' -Destination '%DIST_PATH%\vendor\mariadb' -Recurse -Force"
        if !errorlevel! neq 0 (
            echo ERROR: Fallo la copia de vendor\mariadb.
            exit /b 1
        )
        echo     OK — vendor\mariadb copiado.
    )

    REM config\database.ini (parametros de conexion a MariaDB)
    if not exist "config\database.ini" (
        echo ADVERTENCIA: config\database.ini no encontrado. La app no podra conectar a la DB.
    ) else (
        if not exist "%DIST_PATH%\config" mkdir "%DIST_PATH%\config"
        copy /Y "config\database.ini" "%DIST_PATH%\config\database.ini" >nul
        if !errorlevel! neq 0 (
            echo ERROR: Fallo la copia de config\database.ini.
            exit /b 1
        )
        echo     OK — config\database.ini copiado.
    )

    REM .env (variables de entorno: DATABASE_URL y otros)
    if exist ".env" (
        copy /Y ".env" "%DIST_PATH%\.env" >nul
        echo     OK — .env copiado.
    )
)

set END_TIME=%TIME%

echo.
echo =============================================================================
echo  Compilacion exitosa
echo  Modo   : %BUILD_MODE%
echo  Inicio : %START_TIME%
echo  Fin    : %END_TIME%
if "%BUILD_MODE%"=="onefile" (
    echo  Salida : %OUTPUT_DIR%\%APP_NAME%.exe
) else (
    echo  Salida : %DIST_PATH%\
    echo  Nota   : distribuir toda la carpeta %DIST_FOLDER%\, no solo el .exe
)
echo =============================================================================
echo.

endlocal
exit /b 0
