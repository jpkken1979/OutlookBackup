@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

:: ═══════════════════════════════════════════════════════════════════════════
:: DEV LAUNCHER - Lanzador Inteligente de Apps
:: ═══════════════════════════════════════════════════════════════════════════
:: Autor: Antigravity Agents
:: Uso: start-app.bat [puerto] [opciones]
:: ═══════════════════════════════════════════════════════════════════════════

title Dev Launcher - Iniciando...

:: ─────────────────────────────────────────────────────────────────
:: COLORES (usando ANSI escape codes)
:: ─────────────────────────────────────────────────────────────────
set "GREEN=[92m"
set "RED=[91m"
set "YELLOW=[93m"
set "BLUE=[94m"
set "CYAN=[96m"
set "RESET=[0m"
set "BOLD=[1m"

:: ─────────────────────────────────────────────────────────────────
:: CONFIGURACIÓN POR DEFECTO
:: ─────────────────────────────────────────────────────────────────
set "FRONTEND_BASE_PORT=3000"
set "BACKEND_BASE_PORT=8000"
set "PORT_SUFFIX=000"
set "PROJECT_TYPE=unknown"
set "HAS_FRONTEND=0"
set "HAS_BACKEND=0"
set "CURRENT_DIR=%CD%"
set "APP_NAME=%~n0"

:: Obtener nombre de la carpeta actual
for %%I in (.) do set "APP_NAME=%%~nxI"

:: ─────────────────────────────────────────────────────────────────
:: BANNER
:: ─────────────────────────────────────────────────────────────────
cls
echo.
echo %CYAN%╔═══════════════════════════════════════════════════════════════╗%RESET%
echo %CYAN%║%RESET%  %BOLD%%BLUE%DEV LAUNCHER%RESET% - Lanzador Inteligente                       %CYAN%║%RESET%
echo %CYAN%╠═══════════════════════════════════════════════════════════════╣%RESET%
echo %CYAN%║%RESET%  App: %YELLOW%%APP_NAME%%RESET%
echo %CYAN%║%RESET%  Dir: %CURRENT_DIR%
echo %CYAN%╚═══════════════════════════════════════════════════════════════╝%RESET%
echo.

:: ─────────────────────────────────────────────────────────────────
:: PARSEAR ARGUMENTOS
:: ─────────────────────────────────────────────────────────────────
if "%~1"=="--help" goto :show_help
if "%~1"=="-h" goto :show_help
if "%~1"=="--kill-ports" goto :kill_ports
if "%~1"=="--check" goto :check_only
if "%~1"=="--install" goto :install_only
if "%~1"=="--docker" goto :docker_mode

:: Si se pasó un número, usarlo como puerto
set "ARG1=%~1"
if defined ARG1 (
    echo %ARG1%| findstr /r "^[0-9][0-9][0-9]$" >nul
    if !errorlevel!==0 (
        set "PORT_SUFFIX=%ARG1%"
        goto :skip_port_prompt
    )
)

:: ─────────────────────────────────────────────────────────────────
:: PASO 1: DETECTAR TIPO DE PROYECTO
:: ─────────────────────────────────────────────────────────────────
echo %BLUE%[1/6]%RESET% Detectando tipo de proyecto...

:: Detectar frontend
if exist "package.json" (
    set "HAS_FRONTEND=1"
    findstr /i "next" package.json >nul 2>&1 && set "PROJECT_TYPE=nextjs"
    findstr /i "react" package.json >nul 2>&1 && if "!PROJECT_TYPE!"=="unknown" set "PROJECT_TYPE=react"
    findstr /i "vue" package.json >nul 2>&1 && if "!PROJECT_TYPE!"=="unknown" set "PROJECT_TYPE=vue"
    findstr /i "angular" package.json >nul 2>&1 && if "!PROJECT_TYPE!"=="unknown" set "PROJECT_TYPE=angular"
    if "!PROJECT_TYPE!"=="unknown" set "PROJECT_TYPE=node"
)

if exist "frontend\package.json" (
    set "HAS_FRONTEND=1"
    set "FRONTEND_DIR=frontend"
)

if exist "client\package.json" (
    set "HAS_FRONTEND=1"
    set "FRONTEND_DIR=client"
)

:: Detectar backend
if exist "requirements.txt" (
    set "HAS_BACKEND=1"
    set "BACKEND_TYPE=python"
)

if exist "pyproject.toml" (
    set "HAS_BACKEND=1"
    set "BACKEND_TYPE=python-poetry"
)

if exist "backend\requirements.txt" (
    set "HAS_BACKEND=1"
    set "BACKEND_DIR=backend"
    set "BACKEND_TYPE=python"
)

if exist "server\package.json" (
    set "HAS_BACKEND=1"
    set "BACKEND_DIR=server"
    set "BACKEND_TYPE=node"
)

if exist "api\package.json" (
    set "HAS_BACKEND=1"
    set "BACKEND_DIR=api"
    set "BACKEND_TYPE=node"
)

if exist "backend\package.json" (
    set "HAS_BACKEND=1"
    set "BACKEND_DIR=backend"
    set "BACKEND_TYPE=node"
)

:: Detectar Docker
if exist "docker-compose.yml" set "HAS_DOCKER=1"
if exist "docker-compose.yaml" set "HAS_DOCKER=1"
if exist "Dockerfile" set "HAS_DOCKERFILE=1"

:: Mostrar resultados
echo       %GREEN%✓%RESET% Tipo: %YELLOW%%PROJECT_TYPE%%RESET%
if "%HAS_FRONTEND%"=="1" echo       %GREEN%✓%RESET% Frontend detectado
if "%HAS_BACKEND%"=="1" echo       %GREEN%✓%RESET% Backend detectado (%BACKEND_TYPE%)
if "%HAS_DOCKER%"=="1" echo       %GREEN%✓%RESET% Docker Compose disponible
echo.

:: ─────────────────────────────────────────────────────────────────
:: PASO 2: PREGUNTAR PUERTO
:: ─────────────────────────────────────────────────────────────────
echo %BLUE%[2/6]%RESET% Configuración de puertos
echo.
echo       Puertos actuales en uso:
call :check_common_ports

echo.
echo       %CYAN%Ingresa los 3 dígitos finales del puerto:%RESET%
echo       Ejemplo: 001 = Frontend:3001, Backend:8001
echo                002 = Frontend:3002, Backend:8002
echo.
set /p "PORT_SUFFIX=       Puerto [001-999]: "

:: Validar entrada
if not defined PORT_SUFFIX set "PORT_SUFFIX=000"
echo %PORT_SUFFIX%| findstr /r "^[0-9][0-9][0-9]$" >nul
if errorlevel 1 (
    echo       %RED%✗%RESET% Puerto inválido, usando 000
    set "PORT_SUFFIX=000"
)

:skip_port_prompt
:: Calcular puertos finales
set /a "FRONTEND_PORT=3%PORT_SUFFIX%"
set /a "BACKEND_PORT=8%PORT_SUFFIX%"

echo.
echo       %GREEN%✓%RESET% Frontend: %YELLOW%http://localhost:%FRONTEND_PORT%%RESET%
echo       %GREEN%✓%RESET% Backend:  %YELLOW%http://localhost:%BACKEND_PORT%%RESET%
echo.

:: ─────────────────────────────────────────────────────────────────
:: PASO 3: VERIFICAR SI PUERTOS ESTÁN LIBRES
:: ─────────────────────────────────────────────────────────────────
echo %BLUE%[3/6]%RESET% Verificando puertos...

netstat -ano | findstr ":%FRONTEND_PORT% " | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo       %YELLOW%⚠%RESET% Puerto %FRONTEND_PORT% está en uso
    set /p "KILL_PORT=       ¿Liberar puerto? (S/N): "
    if /i "!KILL_PORT!"=="S" (
        for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%FRONTEND_PORT% " ^| findstr "LISTENING"') do (
            taskkill /PID %%a /F >nul 2>&1
            echo       %GREEN%✓%RESET% Proceso %%a terminado
        )
    )
)

netstat -ano | findstr ":%BACKEND_PORT% " | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo       %YELLOW%⚠%RESET% Puerto %BACKEND_PORT% está en uso
    set /p "KILL_PORT=       ¿Liberar puerto? (S/N): "
    if /i "!KILL_PORT!"=="S" (
        for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%BACKEND_PORT% " ^| findstr "LISTENING"') do (
            taskkill /PID %%a /F >nul 2>&1
            echo       %GREEN%✓%RESET% Proceso %%a terminado
        )
    )
)

echo       %GREEN%✓%RESET% Puertos verificados
echo.

:: ─────────────────────────────────────────────────────────────────
:: PASO 4: ACTUALIZAR .ENV
:: ─────────────────────────────────────────────────────────────────
echo %BLUE%[4/6]%RESET% Sincronizando archivos .env...

:: Crear/Actualizar .env principal
call :update_env_file ".env"

:: Para Next.js, también actualizar .env.local
if "%PROJECT_TYPE%"=="nextjs" (
    call :update_env_file ".env.local"
)

:: Si hay carpeta frontend separada
if defined FRONTEND_DIR (
    call :update_env_file "%FRONTEND_DIR%\.env"
    call :update_env_file "%FRONTEND_DIR%\.env.local"
)

:: Si hay carpeta backend separada
if defined BACKEND_DIR (
    call :update_env_file "%BACKEND_DIR%\.env"
)

echo       %GREEN%✓%RESET% Archivos .env sincronizados
echo.

:: ─────────────────────────────────────────────────────────────────
:: PASO 5: VERIFICAR/INSTALAR DEPENDENCIAS
:: ─────────────────────────────────────────────────────────────────
echo %BLUE%[5/6]%RESET% Verificando dependencias...

:: Frontend (Node.js)
if "%HAS_FRONTEND%"=="1" (
    set "CHECK_DIR=%CD%"
    if defined FRONTEND_DIR set "CHECK_DIR=%CD%\%FRONTEND_DIR%"

    if not exist "!CHECK_DIR!\node_modules" (
        echo       %YELLOW%⚠%RESET% node_modules no encontrado
        echo       %CYAN%→%RESET% Instalando dependencias...

        if defined FRONTEND_DIR (
            pushd "!FRONTEND_DIR!"
            call npm install
            popd
        ) else (
            call npm install
        )

        if errorlevel 1 (
            echo       %RED%✗%RESET% Error instalando dependencias
            goto :error_handler
        )
        echo       %GREEN%✓%RESET% Dependencias instaladas
    ) else (
        echo       %GREEN%✓%RESET% node_modules existe
    )
)

:: Backend (Python)
if "%BACKEND_TYPE%"=="python" (
    set "CHECK_DIR=%CD%"
    if defined BACKEND_DIR set "CHECK_DIR=%CD%\%BACKEND_DIR%"

    if not exist "!CHECK_DIR!\venv" (
        echo       %YELLOW%⚠%RESET% venv no encontrado
        echo       %CYAN%→%RESET% Creando entorno virtual...

        if defined BACKEND_DIR (
            pushd "!BACKEND_DIR!"
            python -m venv venv
            call venv\Scripts\activate.bat
            pip install -r requirements.txt
            popd
        ) else (
            python -m venv venv
            call venv\Scripts\activate.bat
            pip install -r requirements.txt
        )

        if errorlevel 1 (
            echo       %RED%✗%RESET% Error instalando dependencias Python
            goto :error_handler
        )
        echo       %GREEN%✓%RESET% Dependencias Python instaladas
    ) else (
        echo       %GREEN%✓%RESET% venv existe
    )
)

echo.

:: ─────────────────────────────────────────────────────────────────
:: PASO 6: INICIAR APLICACIONES
:: ─────────────────────────────────────────────────────────────────
echo %BLUE%[6/6]%RESET% Iniciando aplicaciones...
echo.

:: Actualizar título de la ventana
title Dev Launcher - %APP_NAME% [F:%FRONTEND_PORT% B:%BACKEND_PORT%]

:: Iniciar Backend primero (en nueva ventana)
if "%HAS_BACKEND%"=="1" (
    echo       %CYAN%→%RESET% Iniciando backend en puerto %BACKEND_PORT%...

    if "%BACKEND_TYPE%"=="python" (
        if defined BACKEND_DIR (
            start "Backend - %APP_NAME%" cmd /k "cd /d %CD%\%BACKEND_DIR% && call venv\Scripts\activate.bat && set PORT=%BACKEND_PORT% && python -m uvicorn main:app --reload --port %BACKEND_PORT% || python app.py || python main.py || python manage.py runserver 0.0.0.0:%BACKEND_PORT% || echo ERROR: No se pudo iniciar el backend && pause"
        ) else (
            start "Backend - %APP_NAME%" cmd /k "cd /d %CD% && call venv\Scripts\activate.bat && set PORT=%BACKEND_PORT% && python -m uvicorn main:app --reload --port %BACKEND_PORT% || python app.py || python main.py || echo ERROR: No se pudo iniciar el backend && pause"
        )
    )

    if "%BACKEND_TYPE%"=="node" (
        if defined BACKEND_DIR (
            start "Backend - %APP_NAME%" cmd /k "cd /d %CD%\%BACKEND_DIR% && set PORT=%BACKEND_PORT% && npm run dev || npm start || echo ERROR: No se pudo iniciar el backend && pause"
        )
    )

    :: Esperar un momento para que el backend inicie
    echo       %YELLOW%⏳%RESET% Esperando que el backend inicie...
    timeout /t 3 /nobreak >nul
)

:: Iniciar Frontend
if "%HAS_FRONTEND%"=="1" (
    echo       %CYAN%→%RESET% Iniciando frontend en puerto %FRONTEND_PORT%...

    if defined FRONTEND_DIR (
        start "Frontend - %APP_NAME%" cmd /k "cd /d %CD%\%FRONTEND_DIR% && set PORT=%FRONTEND_PORT% && npm run dev -- -p %FRONTEND_PORT% || npm run dev || npm start || echo ERROR: No se pudo iniciar el frontend && pause"
    ) else (
        if "%PROJECT_TYPE%"=="nextjs" (
            start "Frontend - %APP_NAME%" cmd /k "cd /d %CD% && set PORT=%FRONTEND_PORT% && npm run dev -- -p %FRONTEND_PORT% || echo ERROR: No se pudo iniciar Next.js && pause"
        ) else (
            start "Frontend - %APP_NAME%" cmd /k "cd /d %CD% && set PORT=%FRONTEND_PORT% && npm run dev || npm start || echo ERROR: No se pudo iniciar el frontend && pause"
        )
    )
)

:: ─────────────────────────────────────────────────────────────────
:: RESUMEN FINAL
:: ─────────────────────────────────────────────────────────────────
echo.
echo %GREEN%╔═══════════════════════════════════════════════════════════════╗%RESET%
echo %GREEN%║%RESET%  %BOLD%✓ APLICACIÓN INICIADA CORRECTAMENTE%RESET%                         %GREEN%║%RESET%
echo %GREEN%╠═══════════════════════════════════════════════════════════════╣%RESET%
echo %GREEN%║%RESET%                                                               %GREEN%║%RESET%
if "%HAS_FRONTEND%"=="1" (
echo %GREEN%║%RESET%  %CYAN%Frontend:%RESET%  http://localhost:%FRONTEND_PORT%                        %GREEN%║%RESET%
)
if "%HAS_BACKEND%"=="1" (
echo %GREEN%║%RESET%  %CYAN%Backend:%RESET%   http://localhost:%BACKEND_PORT%                        %GREEN%║%RESET%
echo %GREEN%║%RESET%  %CYAN%API Docs:%RESET%  http://localhost:%BACKEND_PORT%/docs                   %GREEN%║%RESET%
)
echo %GREEN%║%RESET%                                                               %GREEN%║%RESET%
echo %GREEN%║%RESET%  %YELLOW%Presiona Ctrl+C en las ventanas para detener%RESET%                 %GREEN%║%RESET%
echo %GREEN%╚═══════════════════════════════════════════════════════════════╝%RESET%
echo.

:: Mantener esta ventana abierta
echo Presiona cualquier tecla para cerrar este launcher...
pause >nul
goto :eof

:: ═══════════════════════════════════════════════════════════════════════════
:: FUNCIONES
:: ═══════════════════════════════════════════════════════════════════════════

:update_env_file
:: Actualiza o crea archivo .env con los puertos correctos
set "ENV_FILE=%~1"

:: Crear archivo si no existe
if not exist "%ENV_FILE%" (
    echo # Auto-generado por Dev Launcher > "%ENV_FILE%"
    echo # Fecha: %date% %time% >> "%ENV_FILE%"
    echo. >> "%ENV_FILE%"
)

:: Crear archivo temporal con las actualizaciones
set "TEMP_ENV=%TEMP%\env_temp_%RANDOM%.txt"

:: Variables a establecer
echo PORT=%FRONTEND_PORT%> "%TEMP_ENV%"
echo NEXT_PUBLIC_PORT=%FRONTEND_PORT%>> "%TEMP_ENV%"
echo NEXT_PUBLIC_API_URL=http://localhost:%BACKEND_PORT%>> "%TEMP_ENV%"
echo NEXT_PUBLIC_BACKEND_URL=http://localhost:%BACKEND_PORT%>> "%TEMP_ENV%"
echo VITE_API_URL=http://localhost:%BACKEND_PORT%>> "%TEMP_ENV%"
echo REACT_APP_API_URL=http://localhost:%BACKEND_PORT%>> "%TEMP_ENV%"
echo API_URL=http://localhost:%BACKEND_PORT%>> "%TEMP_ENV%"
echo BACKEND_URL=http://localhost:%BACKEND_PORT%>> "%TEMP_ENV%"
echo BACKEND_PORT=%BACKEND_PORT%>> "%TEMP_ENV%"
echo FRONTEND_URL=http://localhost:%FRONTEND_PORT%>> "%TEMP_ENV%"
echo CORS_ORIGINS=http://localhost:%FRONTEND_PORT%,http://127.0.0.1:%FRONTEND_PORT%>> "%TEMP_ENV%"
echo ALLOWED_HOSTS=localhost,%FRONTEND_PORT%,127.0.0.1>> "%TEMP_ENV%"

:: Leer archivo existente y actualizar/agregar variables
if exist "%ENV_FILE%" (
    for /f "usebackq tokens=1,* delims==" %%a in ("%ENV_FILE%") do (
        set "VAR_NAME=%%a"
        set "VAR_EXISTS=0"
        :: Verificar si la variable ya está en nuestras actualizaciones
        findstr /i /b "!VAR_NAME!=" "%TEMP_ENV%" >nul 2>&1
        if errorlevel 1 (
            :: Variable no está en nuestras actualizaciones, mantenerla
            if not "!VAR_NAME!"=="" if not "!VAR_NAME:~0,1!"=="#" (
                echo %%a=%%b>> "%TEMP_ENV%"
            )
        )
    )
)

:: Reemplazar archivo original
move /y "%TEMP_ENV%" "%ENV_FILE%" >nul 2>&1

echo       %GREEN%✓%RESET% Actualizado: %ENV_FILE%
goto :eof

:check_common_ports
:: Muestra puertos comunes en uso
for %%p in (3000 3001 3002 3003 8000 8001 8002 8003 5000 5173 4200) do (
    netstat -ano | findstr ":%%p " | findstr "LISTENING" >nul 2>&1
    if not errorlevel 1 (
        echo       %YELLOW%•%RESET% Puerto %%p: EN USO
    )
)
goto :eof

:kill_ports
:: Mata procesos en puertos comunes de desarrollo
echo.
echo %YELLOW%Liberando puertos de desarrollo...%RESET%
for %%p in (3000 3001 3002 3003 8000 8001 8002 8003 5000 5173 4200) do (
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%%p " ^| findstr "LISTENING" 2^>nul') do (
        taskkill /PID %%a /F >nul 2>&1
        echo   %GREEN%✓%RESET% Puerto %%p liberado (PID: %%a)
    )
)
echo.
echo %GREEN%Puertos liberados.%RESET%
pause
goto :eof

:check_only
:: Solo verificar proyecto sin iniciar
echo.
echo %CYAN%=== Verificación de Proyecto ===%RESET%
echo.
echo Directorio: %CD%
echo Tipo: %PROJECT_TYPE%
echo Frontend: %HAS_FRONTEND%
echo Backend: %HAS_BACKEND% (%BACKEND_TYPE%)
echo Docker: %HAS_DOCKER%
echo.
pause
goto :eof

:install_only
:: Solo instalar dependencias
echo.
echo %CYAN%=== Instalando Dependencias ===%RESET%
echo.
if exist "package.json" (
    echo Instalando dependencias Node.js...
    call npm install
)
if exist "requirements.txt" (
    echo Instalando dependencias Python...
    pip install -r requirements.txt
)
echo.
echo %GREEN%Dependencias instaladas.%RESET%
pause
goto :eof

:docker_mode
:: Modo Docker
echo.
echo %CYAN%=== Modo Docker ===%RESET%
echo.
if exist "docker-compose.yml" (
    docker-compose up --build
) else if exist "docker-compose.yaml" (
    docker-compose up --build
) else (
    echo %RED%No se encontró docker-compose.yml%RESET%
)
pause
goto :eof

:show_help
echo.
echo %CYAN%DEV LAUNCHER - Ayuda%RESET%
echo.
echo Uso: start-app.bat [puerto] [opciones]
echo.
echo Opciones:
echo   [001-999]       Usar puerto específico (ej: 001 = 3001/8001)
echo   --help, -h      Mostrar esta ayuda
echo   --check         Solo verificar proyecto
echo   --install       Solo instalar dependencias
echo   --kill-ports    Liberar puertos en uso
echo   --docker        Iniciar con Docker
echo.
echo Ejemplos:
echo   start-app.bat              Inicio interactivo
echo   start-app.bat 001          Puerto 3001/8001
echo   start-app.bat --kill-ports Liberar puertos
echo.
pause
goto :eof

:error_handler
echo.
echo %RED%╔═══════════════════════════════════════════════════════════════╗%RESET%
echo %RED%║  ERROR: Algo salió mal                                        ║%RESET%
echo %RED%╠═══════════════════════════════════════════════════════════════╣%RESET%
echo %RED%║                                                               ║%RESET%
echo %RED%║  Posibles causas:                                             ║%RESET%
echo %RED%║  • Puerto ya está en uso                                      ║%RESET%
echo %RED%║  • Faltan dependencias                                        ║%RESET%
echo %RED%║  • Error en package.json o requirements.txt                   ║%RESET%
echo %RED%║  • Node.js o Python no instalado                              ║%RESET%
echo %RED%║                                                               ║%RESET%
echo %RED%║  Intenta:                                                     ║%RESET%
echo %RED%║  1. start-app.bat --kill-ports                                ║%RESET%
echo %RED%║  2. start-app.bat --install                                   ║%RESET%
echo %RED%║                                                               ║%RESET%
echo %RED%╚═══════════════════════════════════════════════════════════════╝%RESET%
echo.
echo Presiona cualquier tecla para cerrar...
pause >nul
exit /b 1
