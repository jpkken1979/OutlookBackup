@echo off
REM ============================================================
REM UNS Outlook Backup v2.0 - Build Script para Windows
REM ============================================================
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1

echo ============================================================
echo  UNS Outlook Backup v2.0 - Build Script
echo  ユニバーサル企画株式会社
echo ============================================================
echo.

cd /d "%~dp0"

REM ===== 1. Verificar Python =====
echo [1/5] Verificando Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python no encontrado en PATH
    echo Instala Python 3.10+ desde: https://python.org
    pause
    exit /b 1
)
python --version
echo.

REM ===== 2. Crear venv si no existe =====
echo [2/5] Configurando entorno virtual...
if not exist ".venv" (
    python -m venv .venv
)
call .venv\Scripts\activate.bat

REM ===== 3. Instalar dependencias =====
echo [3/5] Instalando dependencias...
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo ERROR instalando dependencias
    pause
    exit /b 1
)
echo OK
echo.

REM ===== 4. Generar icono si no existe =====
if not exist "assets\icon.ico" (
    echo [4/5] Generando icono...
    python build\generate_icon.py
) else (
    echo [4/5] Icono encontrado en assets\icon.ico
)
echo.

REM ===== 5. Compilar con PyInstaller =====
echo [5/5] Compilando .exe con PyInstaller...
echo Esto puede tardar 1-2 minutos...
echo.

if exist "dist\UNS-Outlook-Backup.exe" del /q "dist\UNS-Outlook-Backup.exe"

pyinstaller build\pyinstaller.spec --clean --noconfirm
if errorlevel 1 (
    echo ERROR durante la compilacion
    pause
    exit /b 1
)

if not exist "dist\UNS-Outlook-Backup.exe" (
    echo ERROR: dist\UNS-Outlook-Backup.exe no fue generado
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  COMPILACION EXITOSA
echo ============================================================
for %%I in ("dist\UNS-Outlook-Backup.exe") do echo Tamaño: %%~zI bytes
echo.

REM ===== Inno Setup =====
echo [BONUS] Buscando Inno Setup...
set "INNO_PATH="
for %%P in (
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    "C:\Program Files\Inno Setup 6\ISCC.exe"
) do (
    if exist %%P set "INNO_PATH=%%~P"
)

if "%INNO_PATH%"=="" (
    echo Inno Setup no encontrado.
    echo Para generar instalador: descarga de https://jrsoftware.org/isdl.php
    echo El .exe portable está en dist\
) else (
    echo Inno Setup: %INNO_PATH%
    "%INNO_PATH%" build\installer.iss
    if errorlevel 1 (
        echo ERROR generando instalador
    ) else (
        echo INSTALADOR GENERADO:
        dir /b dist\UNS-Outlook-Backup-Setup-*.exe
    )
)

echo.
pause
