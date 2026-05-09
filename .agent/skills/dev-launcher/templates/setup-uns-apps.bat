@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

:: ═══════════════════════════════════════════════════════════════════════════
:: SETUP UNS APPS - Configura todas las apps de ユニバーサル企画
:: ═══════════════════════════════════════════════════════════════════════════

title Setup UNS Apps

set "GREEN=[92m"
set "RED=[91m"
set "YELLOW=[93m"
set "CYAN=[96m"
set "RESET=[0m"

set "SKILL_DIR=%~dp0.."
set "LAUNCHER=%SKILL_DIR%\templates\start-app.bat"

cls
echo.
echo %CYAN%╔═══════════════════════════════════════════════════════════════╗%RESET%
echo %CYAN%║%RESET%  %CYAN%SETUP UNS APPS%RESET%                                              %CYAN%║%RESET%
echo %CYAN%║%RESET%  Configurar todas las apps de ユニバーサル企画              %CYAN%║%RESET%
echo %CYAN%╚═══════════════════════════════════════════════════════════════╝%RESET%
echo.

:: Lista de apps UNS con sus puertos
:: Formato: nombre_carpeta:puerto_suffix
set APPS[0]=Chingin-v8.0-PRO:001
set APPS[1]=UNS-Shain-Daicho-Manager:002
set APPS[2]=UNS-KintaiPRO:003
set APPS[3]=rirekisho-nextjs:004
set APPS[4]=YuKyuDATA-app1.0v:005

echo %CYAN%Apps a configurar:%RESET%
echo.
echo   App                          Puerto
echo   ─────────────────────────────────────
echo   Chingin-v8.0-PRO             3001 / 8001
echo   UNS-Shain-Daicho-Manager     3002 / 8002
echo   UNS-KintaiPRO                3003 / 8003
echo   rirekisho-nextjs             3004 / 8004
echo   YuKyuDATA-app1.0v            3005 / 8005
echo.

set /p "CONFIRM=¿Continuar? (S/N): "
if /i not "!CONFIRM!"=="S" exit /b 0

echo.

:: Procesar cada app
for /L %%i in (0,1,4) do (
    for /f "tokens=1,2 delims=:" %%a in ("!APPS[%%i]!") do (
        set "APP_NAME=%%a"
        set "PORT_SUFFIX=%%b"
        set "APP_PATH=%USERPROFILE%\!APP_NAME!"

        if exist "!APP_PATH!" (
            echo %CYAN%[%%a]%RESET% Instalando launcher...

            :: Copiar launcher
            copy /y "%LAUNCHER%" "!APP_PATH!\start-app.bat" >nul 2>&1

            if errorlevel 1 (
                echo   %RED%✗ Error al copiar%RESET%
            ) else (
                echo   %GREEN%✓ Launcher instalado%RESET%

                :: Crear archivo de puerto predeterminado
                echo !PORT_SUFFIX!> "!APP_PATH!\.default-port"
                echo   %GREEN%✓ Puerto predeterminado: !PORT_SUFFIX!%RESET%
            )
        ) else (
            echo %YELLOW%[%%a]%RESET% No encontrado, saltando...
        )
        echo.
    )
)

echo.
echo %GREEN%╔═══════════════════════════════════════════════════════════════╗%RESET%
echo %GREEN%║  ✓ Configuración completada                                   ║%RESET%
echo %GREEN%╚═══════════════════════════════════════════════════════════════╝%RESET%
echo.
echo %CYAN%Para iniciar una app:%RESET%
echo   cd "%%USERPROFILE%%\Chingin-v8.0-PRO"
echo   start-app.bat
echo.
echo %CYAN%O con puerto específico:%RESET%
echo   start-app.bat 001
echo.

pause
