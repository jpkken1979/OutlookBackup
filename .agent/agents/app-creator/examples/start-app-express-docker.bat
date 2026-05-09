@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

REM ============================================================================
REM App Creator - Express Docker Launcher
REM Descripción: Script para iniciar aplicación Express en Docker
REM Características: build automático, puerto dinámico, volúmenes para desarrollo
REM ============================================================================

title Express Application - Docker Launcher
color 0C

REM Colors y Variables
set "GREEN=[SUCCESS]"
set "RED=[ERROR]"
set "YELLOW=[INFO]"
set "BLUE=[CONFIG]"

REM Configuración
set "APP_NAME=Express App"
set "DEFAULT_PORT=3000"
set "CONTAINER_NAME=express-app-dev"
set "IMAGE_NAME=express-app:dev"

cls
echo.
echo ╔════════════════════════════════════════════════════════════════════╗
echo ║           %APP_NAME% - Docker Launcher                     ║
echo ║                  Powered by App Creator Agent                      ║
echo ╚════════════════════════════════════════════════════════════════════╝
echo.

REM Verificar Docker
docker --version >nul 2>&1
if errorlevel 1 (
    echo %RED% Docker no instalado. Por favor instala Docker Desktop
    pause
    exit /b 1
)
echo %GREEN% Docker detectado

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

REM Crear Dockerfile si no existe
echo.
echo %BLUE% === Verificando Dockerfile ===

if not exist "Dockerfile" (
    echo %YELLOW% Creando Dockerfile...
    (
        echo FROM node:18-alpine
        echo.
        echo WORKDIR /app
        echo.
        echo REM Copiar archivos de configuración
        echo COPY package*.json ./
        echo.
        echo REM Instalar dependencias
        echo RUN npm ci --only=production
        echo.
        echo REM Copiar aplicación
        echo COPY . .
        echo.
        echo REM Health check
        echo HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
        echo     CMD node -e "require('http').get('http://localhost:3000/', (r) => {if (r.statusCode !== 200) throw new Error(r.statusCode)})"
        echo.
        echo EXPOSE 3000
        echo CMD ["npm", "start"]
    ) > Dockerfile
    echo %GREEN% Dockerfile creado
) else (
    echo %GREEN% Dockerfile detectado
)

REM Crear .env si no existe
echo.
echo %BLUE% === Configurando Variables de Entorno ===

if not exist ".env" (
    echo %YELLOW% Creando archivo .env...
    (
        echo PORT=%PORT%
        echo NODE_ENV=production
        echo DEBUG=false
        echo APP_NAME=%APP_NAME%
        echo APP_ENVIRONMENT=docker
        echo API_BASE_URL=http://localhost:%PORT%
    ) > .env
    echo %GREEN% Archivo .env creado
)

REM Información final
echo.
echo %BLUE% === Información de Docker ===
echo %YELLOW% Imagen: %IMAGE_NAME%
echo %YELLOW% Contenedor: %CONTAINER_NAME%
echo %YELLOW% Puerto Host: %PORT%
echo %YELLOW% Puerto Container: 3000
echo %YELLOW% URL: http://localhost:%PORT%
echo.

REM Detener contenedor anterior si existe
echo %YELLOW% Limpiando contenedores anteriores...
docker stop %CONTAINER_NAME% >nul 2>&1
docker rm %CONTAINER_NAME% >nul 2>&1

REM Build image
echo.
echo %YELLOW% Construyendo imagen Docker...
docker build -t %IMAGE_NAME% .

if errorlevel 1 (
    echo %RED% Error al construir imagen
    pause
    exit /b 1
)
echo %GREEN% Imagen construida correctamente

REM Run container
echo.
echo %YELLOW% Iniciando contenedor...
docker run -d ^
  --name %CONTAINER_NAME% ^
  -p %PORT%:3000 ^
  -v %cd%:/app ^
  -v /app/node_modules ^
  --env-file .env ^
  %IMAGE_NAME%

if errorlevel 1 (
    echo %RED% Error al iniciar contenedor
    pause
    exit /b 1
)

echo %GREEN% Contenedor iniciado correctamente
echo.
echo %BLUE% === Siguientes pasos ===
echo %YELLOW% Ver logs: docker logs -f %CONTAINER_NAME%
echo %YELLOW% Detener: docker stop %CONTAINER_NAME%
echo %YELLOW% Acceder: http://localhost:%PORT%
echo.

pause
