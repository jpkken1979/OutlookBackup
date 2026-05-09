#!/usr/bin/env python3
"""
Excel Specialist Agent — cliente HTTP del gateway :4747.

Delega operaciones Excel al antigravity-excel MCP via gateway.
No tiene lógica de parseo ni de negocio — solo delega.

Version: 1.0.0
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# Paths
AGENT_DIR = Path(__file__).parent.parent.parent
MEMORY_DIR = AGENT_DIR / "memory"
SHARED_MEMORY_PATH = MEMORY_DIR / "shared_memory.json"


def get_gateway_url() -> str:
    """Obtiene la URL del gateway desde env var."""
    return os.environ.get("ANTIGRAVITY_GATEWAY", "http://127.0.0.1:4747")


def get_api_key() -> str:
    """Obtiene la API key desde env var."""
    key = os.environ.get("ANTIGRAVITY_API_KEY", "")
    if not key:
        logger.warning("ANTIGRAVITY_API_KEY no está configurada")
    return key


def load_shared_memory() -> dict[str, Any]:
    """Carga la memoria compartida del agente."""
    if not SHARED_MEMORY_PATH.exists():
        return {
            "version": "1.0",
            "last_run": None,
            "total_tasks": 0,
            "total_sessions": 0,
            "stats": {
                "parse": 0,
                "write": 0,
                "live": 0,
                "chart": 0,
                "pivot": 0,
                "macro": 0,
                "power": 0,
            },
            "last_errors": [],
        }
    with open(SHARED_MEMORY_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_shared_memory(memory: dict[str, Any]) -> None:
    """Guarda la memoria compartida del agente."""
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    memory["last_run"] = datetime.utcnow().isoformat()
    with open(SHARED_MEMORY_PATH, "w", encoding="utf-8") as f:
        json.dump(memory, f, indent=2, ensure_ascii=False)


def update_stats(
    memory: dict[str, Any], mode: str, success: bool, error: str | None = None,
) -> None:
    """Actualiza las estadísticas del agente."""
    memory["total_tasks"] += 1
    if mode in memory["stats"]:
        memory["stats"][mode] += 1
    if not success and error:
        memory["last_errors"].append(
            {"mode": mode, "error": error, "ts": datetime.utcnow().isoformat()}
        )
        # Keep only last 10 errors
        memory["last_errors"] = memory["last_errors"][-10:]


def gateway_request(
    method: str, endpoint: str, data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Hace un request HTTP al gateway.

    Args:
        method: HTTP method (GET, POST)
        endpoint: Endpoint path (ej. /v1/excel/parse)
        data: Body JSON para POST

    Returns:
        Respuesta JSON del gateway
    """
    url = f"{get_gateway_url()}{endpoint}"
    api_key = get_api_key()

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key

    body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data else None

    logger.info(f"Request {method} {url}")
    if body:
        logger.debug(f"Body: {body.decode('utf-8')[:500]}")

    try:
        req = urllib.request.Request(
            url,
            data=body,
            headers=headers,
            method=method,
        )
        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))
            logger.info(f"Response OK: {str(result)[:200]}")
            return result
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else ""
        logger.error(f"HTTP {e.code}: {error_body[:500]}")
        return {"success": False, "error": f"HTTP {e.code}", "detail": error_body[:500]}
    except urllib.error.URLError as e:
        logger.error(f"URL error: {e.reason}")
        return {"success": False, "error": f"URL error: {e.reason}"}
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {"success": False, "error": str(e)}


def cmd_parse(
    file_path: str, sheet: str | None = None, detect_tables: bool = True,
) -> dict[str, Any]:
    """Parsea un archivo Excel."""
    data = {
        "file_path": file_path,
        "detect_tables": detect_tables,
    }
    if sheet:
        data["sheet_names"] = [sheet]
    return gateway_request("POST", "/v1/excel/parse", data)


def cmd_open(file_path: str, mode: str = "write") -> dict[str, Any]:
    """Abre un archivo Excel."""
    data = {
        "file_path": file_path,
        "mode": mode,
    }
    return gateway_request("POST", "/v1/excel/sessions", data)


def cmd_write(sid: str, sheet: str, cell_range: str, values: list[list[Any]]) -> dict[str, Any]:
    """Escribe valores a un rango."""
    data = {
        "sheet": sheet,
        "range": cell_range,
        "values": values,
    }
    return gateway_request("POST", f"/v1/excel/sessions/{sid}/range", data)


def cmd_close(sid: str, save: bool = False) -> dict[str, Any]:
    """Cierra un archivo Excel."""
    data = {
        "save": save,
    }
    return gateway_request("DELETE", f"/v1/excel/sessions/{sid}", data)


def cmd_macro(sid: str, macro_name: str, args: list[Any] | None = None) -> dict[str, Any]:
    """Ejecuta una macro VBA."""
    data = {
        "macro_name": macro_name,
    }
    if args:
        data["args"] = args
    return gateway_request("POST", f"/v1/excel/sessions/{sid}/macro", data)


def cmd_chart(
    sid: str,
    sheet: str,
    data_range: str,
    chart_type: str,
    dest_cell: str = "I1",
) -> dict[str, Any]:
    """Crea un chart."""
    data = {
        "sheet": sheet,
        "data_range": data_range,
        "chart_type": chart_type,
        "dest_cell": dest_cell,
    }
    return gateway_request("POST", f"/v1/excel/sessions/{sid}/chart", data)


def cmd_pivot(
    sid: str,
    source_sheet: str,
    source_range: str,
    dest_cell: str,
) -> dict[str, Any]:
    """Crea una tabla dinámica."""
    data = {
        "source_sheet": source_sheet,
        "source_range": source_range,
        "dest_cell": dest_cell,
    }
    return gateway_request("POST", f"/v1/excel/sessions/{sid}/pivot", data)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Excel Specialist Agent — cliente gateway :4747",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # parse
    p_parse = sub.add_parser("parse", help="Parsear archivo Excel")
    p_parse.add_argument("file_path", help="Ruta al archivo Excel")
    p_parse.add_argument("--sheet", help="Hoja específica a procesar")
    p_parse.add_argument("--no-detect", action="store_true", help="Desactivar detección de tablas")

    # open
    p_open = sub.add_parser("open", help="Abrir archivo Excel")
    p_open.add_argument("file_path", help="Ruta al archivo Excel")
    p_open.add_argument(
        "--mode", choices=["write", "live"], default="write", help="Modo: write o live",
    )

    # write
    p_write = sub.add_parser("write", help="Escribir a rango")
    p_write.add_argument("sid", help="Session ID")
    p_write.add_argument("sheet", help="Nombre de hoja")
    p_write.add_argument("range", help="Rango (ej. A1:C3)")
    p_write.add_argument("values_json", help="Valores en JSON (array de arrays)")

    # close
    p_close = sub.add_parser("close", help="Cerrar archivo")
    p_close.add_argument("sid", help="Session ID")
    p_close.add_argument("--save", action="store_true", help="Guardar antes de cerrar")

    # macro
    p_macro = sub.add_parser("macro", help="Ejecutar macro VBA")
    p_macro.add_argument("sid", help="Session ID")
    p_macro.add_argument("macro_name", help="Nombre de la macro")
    p_macro.add_argument("--args", help="Argumentos en JSON (array)")

    # chart
    p_chart = sub.add_parser("chart", help="Crear chart")
    p_chart.add_argument("sid", help="Session ID")
    p_chart.add_argument("sheet", help="Hoja con datos")
    p_chart.add_argument("range", help="Rango de datos (ej. A1:D10)")
    p_chart.add_argument("type", help="Tipo de chart (bar, line, pie, column)")
    p_chart.add_argument("--dest", default="I1", help="Celda destino (default: I1)")

    # pivot
    p_pivot = sub.add_parser("pivot", help="Crear tabla dinámica")
    p_pivot.add_argument("sid", help="Session ID")
    p_pivot.add_argument("source_sheet", help="Hoja origen")
    p_pivot.add_argument("source_range", help="Rango origen (ej. A1:D100)")
    p_pivot.add_argument("dest_cell", help="Celda destino (ej. F1)")

    args = parser.parse_args()

    memory = load_shared_memory()
    result: dict[str, Any] = {"success": False}
    mode = "unknown"

    try:
        if args.command == "parse":
            mode = "parse"
            result = cmd_parse(args.file_path, args.sheet, not args.no_detect)

        elif args.command == "open":
            mode = "live" if args.mode == "live" else "write"
            result = cmd_open(args.file_path, args.mode)

        elif args.command == "write":
            mode = "write"
            values = json.loads(args.values_json)
            result = cmd_write(args.sid, args.sheet, args.range, values)

        elif args.command == "close":
            result = cmd_close(args.sid, args.save)

        elif args.command == "macro":
            mode = "macro"
            macro_args = json.loads(args.args) if args.args else None
            result = cmd_macro(args.sid, args.macro_name, macro_args)

        elif args.command == "chart":
            mode = "chart"
            result = cmd_chart(args.sid, args.sheet, args.range, args.type, args.dest)

        elif args.command == "pivot":
            mode = "pivot"
            result = cmd_pivot(args.sid, args.source_sheet, args.source_range, args.dest_cell)

    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        result = {"success": False, "error": f"JSON inválido: {e}"}
    except Exception as e:
        logger.error(f"Error ejecutando comando: {e}")
        result = {"success": False, "error": str(e)}

    # Update stats
    update_stats(memory, mode, result.get("success", False), result.get("error"))
    save_shared_memory(memory)

    # Output
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))

    if not result.get("success", False):
        sys.exit(1)


if __name__ == "__main__":
    main()
