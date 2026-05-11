"""
UNS Backup v2.0 - Windows Task Scheduler Integration
======================================================
Crea/elimina/consulta tareas programadas usando schtasks.exe (built-in Windows).
"""

import datetime
import os
import subprocess
import sys

TASK_NAME = "UNS-Outlook-Backup-Auto"


def get_app_executable() -> str:
    """Detecta la ruta del .exe (en build PyInstaller) o python script (dev)."""
    if getattr(sys, "frozen", False):
        return sys.executable
    return f'"{sys.executable}" "{os.path.abspath(sys.argv[0])}"'


def _run_schtasks(args: list, capture: bool = True) -> subprocess.CompletedProcess:
    """Ejecuta schtasks.exe y devuelve el resultado."""
    cmd = ["schtasks"] + args
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NO_WINDOW

    try:
        return subprocess.run(
            cmd,
            capture_output=capture,
            text=True,
            encoding="cp932" if os.name == "nt" else "utf-8",
            errors="ignore",
            creationflags=creationflags,
            timeout=30,
        )
    except FileNotFoundError:
        raise RuntimeError("schtasks.exe no encontrado (¿no estás en Windows?)")
    except subprocess.TimeoutExpired:
        raise RuntimeError("schtasks.exe timeout")


def task_exists() -> bool:
    """Verifica si la tarea programada existe."""
    try:
        result = _run_schtasks(["/Query", "/TN", TASK_NAME])
        return result.returncode == 0
    except Exception:
        return False


def get_task_info() -> dict | None:
    """Devuelve info de la tarea programada actual."""
    try:
        result = _run_schtasks(["/Query", "/TN", TASK_NAME, "/FO", "CSV", "/V"])
        if result.returncode != 0:
            return None

        lines = result.stdout.strip().split("\n")
        if len(lines) < 2:
            return None

        # CSV headers + values
        import csv
        from io import StringIO

        reader = csv.DictReader(StringIO(result.stdout))
        rows = list(reader)
        if not rows:
            return None

        row = rows[0]
        return {
            "name": row.get("TaskName", ""),
            "next_run": row.get("Next Run Time", ""),
            "last_run": row.get("Last Run Time", ""),
            "last_result": row.get("Last Result", ""),
            "status": row.get("Status", ""),
            "schedule": row.get("Schedule", ""),
        }
    except Exception as e:
        print(f"Error get_task_info: {e}")
        return None


def create_task(
    frequency: str, time_hhmm: str, day_of_week: str = "MON", custom_days: int = 7
) -> bool:
    """
    Crea una tarea programada.
    :param frequency: 'daily' | 'weekly' | 'biweekly' | 'monthly' | 'custom'
    :param time_hhmm: '02:00' (24h)
    :param day_of_week: 'MON','TUE',etc para weekly/biweekly
    :param custom_days: cada N días si frequency='custom'
    """
    # Construir comando
    exe = get_app_executable()
    tr = f"{exe} --auto"

    args = [
        "/Create",
        "/TN",
        TASK_NAME,
        "/TR",
        tr,
        "/ST",
        time_hhmm,
        "/F",  # forzar overwrite si existe
    ]

    if frequency == "daily":
        args.extend(["/SC", "DAILY"])
    elif frequency == "weekly":
        args.extend(["/SC", "WEEKLY", "/D", day_of_week])
    elif frequency == "biweekly":
        # schtasks no tiene "biweekly" directo, usamos WEEKLY con /MO 2
        args.extend(["/SC", "WEEKLY", "/D", day_of_week, "/MO", "2"])
    elif frequency == "monthly":
        # Día 1 del mes
        args.extend(["/SC", "MONTHLY", "/D", "1"])
    elif frequency == "custom":
        days = max(1, int(custom_days))
        args.extend(["/SC", "DAILY", "/MO", str(days)])
    else:
        raise ValueError(f"Frecuencia desconocida: {frequency}")

    try:
        result = _run_schtasks(args)
        if result.returncode == 0:
            return True
        print(f"schtasks error: {result.stdout} {result.stderr}")
        return False
    except Exception as e:
        print(f"Error creando tarea: {e}")
        return False


def delete_task() -> bool:
    """Elimina la tarea programada."""
    try:
        result = _run_schtasks(["/Delete", "/TN", TASK_NAME, "/F"])
        return result.returncode == 0
    except Exception as e:
        print(f"Error borrando tarea: {e}")
        return False


def run_task_now() -> bool:
    """Ejecuta la tarea inmediatamente (para testear)."""
    try:
        result = _run_schtasks(["/Run", "/TN", TASK_NAME])
        return result.returncode == 0
    except Exception as e:
        print(f"Error ejecutando tarea: {e}")
        return False


def calculate_next_run(
    frequency: str, time_hhmm: str, day_of_week: str = "MON", custom_days: int = 7
) -> str:
    """Calcula la próxima ejecución estimada (para mostrar al usuario)."""
    try:
        now = datetime.datetime.now()
        hh, mm = map(int, time_hhmm.split(":"))

        next_run = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if next_run <= now:
            next_run += datetime.timedelta(days=1)

        days_map = {"MON": 0, "TUE": 1, "WED": 2, "THU": 3, "FRI": 4, "SAT": 5, "SUN": 6}

        if frequency == "weekly":
            target_dow = days_map.get(day_of_week, 0)
            days_until = (target_dow - next_run.weekday()) % 7
            if days_until == 0 and next_run <= now:
                days_until = 7
            next_run += datetime.timedelta(days=days_until)
        elif frequency == "biweekly":
            target_dow = days_map.get(day_of_week, 0)
            days_until = (target_dow - next_run.weekday()) % 7
            next_run += datetime.timedelta(days=days_until)
        elif frequency == "monthly":
            next_run = next_run.replace(day=1)
            if next_run <= now:
                if next_run.month == 12:
                    next_run = next_run.replace(year=next_run.year + 1, month=1)
                else:
                    next_run = next_run.replace(month=next_run.month + 1)
        elif frequency == "custom":
            # Asume próxima ejecución en N días desde hoy
            next_run += datetime.timedelta(days=max(0, custom_days - 1))

        return next_run.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return "(計算できません)"
