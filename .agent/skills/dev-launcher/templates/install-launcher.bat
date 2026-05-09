@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

:: ═══════════════════════════════════════════════════════════════════════════
:: INSTALL LAUNCHER - Instala start-app.bat en tus proyectos
:: ═══════════════════════════════════════════════════════════════════════════
:: Uso: install-launcher.bat NombreApp
::      install-launcher.bat NombreApp --symlink
:: ═══════════════════════════════════════════════════════════════════════════

title Instalador de Dev Launcher

set "GREEN=[92m"
set "RED=[91m"
set "YELLOW=[93m"
set "CYAN=[96m"
set "RESET=[0m"

:: Obtener el directorio de esta skill
set "SKILL_DIR=%~dp0.."
set "LAUNCHER_SOURCE=%SKILL_DIR%\templates\start-app.bat"

cls
echo.
echo %CYAN%╔═══════════════════════════════════════════════════════════════╗%RESET%
echo %CYAN%║%RESET%  %CYAN%DEV LAUNCHER - Instalador%RESET%                                  %CYAN%║%RESET%
echo %CYAN%╚═══════════════════════════════════════════════════════════════╝%RESET%
echo.

:: Verificar argumentos
if "%~1"=="" (
    goto :interactive_mode
)

:: Modo con argumentos
set "APP_NAME=%~1"
set "USE_SYMLINK=0"
if /i "%~2"=="--symlink" set "USE_SYMLINK=1"

set "APP_PATH=%USERPROFILE%\%APP_NAME%"
goto :install_to_app

:interactive_mode
echo %CYAN%Tus proyectos en %USERPROFILE%:%RESET%
echo.

:: Listar carpetas que parecen proyectos
set "COUNT=0"
for /d %%D in ("%USERPROFILE%\*") do (
    if exist "%%D\package.json" (
        set /a COUNT+=1
        echo   !COUNT!. %%~nxD %GREEN%[Node.js]%RESET%
    ) else if exist "%%D\requirements.txt" (
        set /a COUNT+=1
        echo   !COUNT!. %%~nxD %YELLOW%[Python]%RESET%
    ) else if exist "%%D\docker-compose.yml" (
        set /a COUNT+=1
        echo   !COUNT!. %%~nxD %CYAN%[Docker]%RESET%
    )
)

echo.
echo %CYAN%Escribe el nombre de la carpeta donde instalar:%RESET%
set /p "APP_NAME=Nombre de app: "

if not defined APP_NAME (
    echo %RED%Nombre requerido%RESET%
    pause
    exit /b 1
)

set "APP_PATH=%USERPROFILE%\%APP_NAME%"

:install_to_app
:: Verificar que existe la app
if not exist "%APP_PATH%" (
    echo %RED%✗ No existe: %APP_PATH%%RESET%
    echo.
    pause
    exit /b 1
)

:: Verificar que existe el source
if not exist "%LAUNCHER_SOURCE%" (
    echo %RED%✗ No se encontró el launcher source%RESET%
    echo   %LAUNCHER_SOURCE%
    pause
    exit /b 1
)

:: Copiar launcher
echo.
echo %CYAN%Instalando en: %APP_PATH%%RESET%
copy /y "%LAUNCHER_SOURCE%" "%APP_PATH%\start-app.bat" >nul

if errorlevel 1 (
    echo %RED%✗ Error al copiar%RESET%
    pause
    exit /b 1
)

echo %GREEN%✓ Launcher instalado correctamente%RESET%
echo.
echo %CYAN%Para usar:%RESET%
echo   cd "%APP_PATH%"
echo   start-app.bat
echo.

:: Preguntar si instalar en otra app
set /p "OTRA=¿Instalar en otra app? (S/N): "
if /i "!OTRA!"=="S" goto :interactive_mode

echo.
echo %GREEN%¡Instalación completada!%RESET%
pause
