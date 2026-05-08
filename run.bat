@echo off
REM Quick launcher para desarrollo (sin compilar a .exe)
chcp 65001 >nul 2>&1
cd /d "%~dp0"

if not exist ".venv" (
    echo Creando entorno virtual por primera vez...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    python -m pip install --upgrade pip --quiet
    pip install -r requirements.txt --quiet
) else (
    call .venv\Scripts\activate.bat
)

python src\main.py
pause
