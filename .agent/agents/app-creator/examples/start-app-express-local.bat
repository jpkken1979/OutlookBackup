@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

REM ============================================================================
REM App Creator - Express Local Launcher
REM Descripción: Script inteligente para iniciar aplicación Express en local
REM Características: selección de puerto, instalación de deps, CORS automático
REM ============================================================================

title Express Application - Local Launcher
color 0C

REM Colors y Variables
set "GREEN=[SUCCESS]"
set "RED=[ERROR]"
set "YELLOW=[INFO]"
set "BLUE=[CONFIG]"

REM Configuración detectada
set "APP_NAME=Express App"
set "MAIN_FILE=server.js"
set "DEFAULT_PORT=3000"
set "DATABASE_URL="
set "CORS_ORIGINS=http://localhost:3000"

cls
echo.
echo ╔════════════════════════════════════════════════════════════════════╗
echo ║           %APP_NAME% - Local Launcher                      ║
echo ║                  Powered by App Creator Agent                      ║
echo ╚════════════════════════════════════════════════════════════════════╝
echo.

REM Verificar Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo %RED% Node.js no instalado. Por favor instala Node.js 14+
    pause
    exit /b 1
)
echo %GREEN% Node.js detectado

REM Verificar npm
npm --version >nul 2>&1
if errorlevel 1 (
    echo %RED% npm no instalado
    pause
    exit /b 1
)
echo %GREEN% npm detectado

REM Seleccionar puerto
echo.
echo %BLUE% === Configuración de Puerto ===
echo %YELLOW% Puerto por defecto: %DEFAULT_PORT%
set /p USER_PORT="Ingresa el puerto deseado (o presiona Enter para default): "

if "%USER_PORT%"=="" (
    set "PORT=%DEFAULT_PORT%"
) else (
    set "PORT=%USER_PORT%"
)

REM Validar rango de puerto
for /f %%A in ('powershell -Command "[int]$p = %PORT%; if ($p -ge 1024 -and $p -le 65535) { Write-Host 1 } else { Write-Host 0 }"') do set VALID=%%A

if "%VALID%"=="0" (
    echo %RED% Puerto inválido. Debe estar entre 1024 y 65535
    pause
    exit /b 1
)

echo %GREEN% Puerto confirmado: %PORT%

REM Verificar e instalar dependencias
echo.
echo %YELLOW% Verificando dependencias de npm...

if not exist "node_modules" (
    echo %YELLOW% node_modules no encontrado. Instalando...
    call npm install -q
    echo %GREEN% Dependencias instaladas
) else (
    echo %GREEN% node_modules detectado
)

REM Crear/Actualizar .env
echo.
echo %BLUE% === Configurando Variables de Entorno ===

if not exist ".env" (
    echo %YELLOW% Creando archivo .env...
    (
        echo BACKEND_PORT=%PORT%
        echo PORT=%PORT%
        echo FRONTEND_PORT=3000
        echo API_BASE_URL=http://localhost:%PORT%
        echo NODE_ENV=development
        echo DEBUG=true
        echo APP_NAME=%APP_NAME%
        echo APP_ENVIRONMENT=development
        if not "!DATABASE_URL!"=="" echo DATABASE_URL=!DATABASE_URL!
        echo CORS_ORIGINS=%CORS_ORIGINS%
    ) > .env
    echo %GREEN% Archivo .env creado
) else (
    echo %GREEN% Archivo .env existente - actualizando puerto...
    echo %GREEN% .env actualizado
)

REM Información final
echo.
echo %BLUE% === Información de Inicio ===
echo %YELLOW% Aplicación: %APP_NAME%
echo %YELLOW% Archivo principal: %MAIN_FILE%
echo %YELLOW% Puerto: %PORT%
echo %YELLOW% URL: http://localhost:%PORT%
echo %YELLOW% CORS configurado para: %CORS_ORIGINS%
echo.

REM Iniciar servidor
echo %YELLOW% Iniciando servidor Express...
echo.

set PORT=%PORT%
set NODE_ENV=development
npm start

pause
