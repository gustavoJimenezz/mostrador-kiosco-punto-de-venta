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

REM --- Crear directorio de salida --------------------------------------------
echo [3/5] Preparando directorio de salida: %OUTPUT_DIR%\...
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"
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
)

REM Deshabilitar consola (app GUI pura)
if "%NO_CONSOLE%"=="true" (
    set NUITKA_FLAGS=%NUITKA_FLAGS% --windows-console-mode=disable
)

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
    echo  Salida : %OUTPUT_DIR%\%APP_NAME%.dist\
    echo  Nota   : distribuir toda la carpeta %APP_NAME%.dist\, no solo el .exe
)
echo =============================================================================
echo.

endlocal
exit /b 0
