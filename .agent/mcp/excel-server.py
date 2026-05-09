#!/usr/bin/env python3
"""Antigravity Excel MCP Server.

JSON-RPC 2.0 stdio server que expone el ExcelEngine a clientes MCP
(Claude Code, Cursor, Windsurf). Sigue el patrón de brain-server.py
y memory-server.py.

Métodos expuestos:
    excel_open, excel_close, excel_list_sessions,
    excel_parse_smart, excel_read_range,
    excel_write_range, excel_apply_formula, excel_set_format,
    excel_create_table, excel_save_as, excel_health.

Métodos Plan B (delegan a XlwingsBackend cuando está disponible):
    excel_run_macro, excel_create_chart, excel_create_pivot,
    excel_update_dashboard, excel_screenshot, excel_power_query,
    excel_dax_measure, excel_slicer, excel_conditional_format,
    excel_calculation_mode.

v1.0.0 — 2026-04-27
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

logging.basicConfig(
    level=os.getenv("ANTIGRAVITY_LOG_LEVEL", "INFO"),
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("excel-server")

# ---------------------------------------------------------------------------
# Path setup — igual que en brain-server.py
# ---------------------------------------------------------------------------
_AGENT_DIR = Path(__file__).resolve().parent.parent
if str(_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(_AGENT_DIR))

_AGENT_CORE = _AGENT_DIR / "core"
if str(_AGENT_CORE) not in sys.path:
    sys.path.insert(0, str(_AGENT_CORE))

from core.brain import Brain  # noqa: E402  # type: ignore[import-not-found]
from core.excel_engine import ExcelEngine  # noqa: E402  # type: ignore[import-not-found]
from core.excel_engine.types import CellFormat  # noqa: E402  # type: ignore[import-not-found]

# ---------------------------------------------------------------------------
# Lazy engine init — se inicializa en el primer request
# ---------------------------------------------------------------------------
_engine: ExcelEngine | None = None
_INIT_ERROR: str | None = None


def _ensure_engine() -> ExcelEngine:
    """Retorna (o inicializa) el singleton ExcelEngine.

    Returns:
        La instancia de ExcelEngine lista para usar.

    Raises:
        RuntimeError: Si la inicialización previa falló.
    """
    global _engine, _INIT_ERROR
    if _engine is not None:
        return _engine
    if _INIT_ERROR is not None:
        raise RuntimeError(_INIT_ERROR)
    try:
        brain_dir = os.getenv("ANTIGRAVITY_BRAIN_DIR")
        if brain_dir is None:
            antigravity_root = os.getenv("ANTIGRAVITY_ROOT", "")
            if antigravity_root:
                brain_dir = str(Path(antigravity_root) / ".agent" / "brain")
            else:
                brain_dir = str(Path.home() / ".antigravity" / "brain")
        brain = Brain(Path(brain_dir), app_id="antigravity-excel")
        _engine = ExcelEngine(brain=brain)
        logger.info("Excel engine inicializado; brain en %s", brain_dir)
        return _engine
    except Exception as exc:
        _INIT_ERROR = f"engine init failed: {exc}"
        logger.exception("Engine init falló")
        raise


# ---------------------------------------------------------------------------
# Handlers — funciones puras que reciben params dict y devuelven dict
# ---------------------------------------------------------------------------


def handle_excel_open(params: dict[str, Any]) -> dict[str, Any]:
    """Abre un archivo Excel y crea una sesión.

    Args:
        params: Debe contener 'path' y opcionalmente 'mode' (read|write).

    Returns:
        dict con status='ok' y data.session_id, o status='error'.
    """
    path = params.get("path", "")
    mode = params.get("mode", "read")
    if not path:
        return {
            "status": "error",
            "error": {
                "category": "user",
                "code": "MISSING_PATH",
                "message": "path es requerido",
                "suggested_next_actions": [],
                "retryable": False,
                "backend_message": None,
                "retry_after_ms": None,
                "brain_hint_used": None,
            },
        }
    return _ensure_engine().open(path, mode=mode).to_dict()


def handle_excel_close(params: dict[str, Any]) -> dict[str, Any]:
    """Cierra una sesión y opcionalmente guarda.

    Args:
        params: Debe contener 'session_id'. Opcional: 'save' (bool, default True).

    Returns:
        dict con status='ok' o status='error'.
    """
    sid = params.get("session_id", "")
    save = bool(params.get("save", True))
    return _ensure_engine().close(sid, save=save).to_dict()


def handle_excel_list_sessions(params: dict[str, Any]) -> dict[str, Any]:  # noqa: ARG001
    """Lista todas las sesiones activas.

    Args:
        params: No se usan parámetros.

    Returns:
        dict con status='ok' y data.sessions.
    """
    return _ensure_engine().list_sessions().to_dict()


def handle_excel_parse_smart(params: dict[str, Any]) -> dict[str, Any]:
    """Parse inteligente de un archivo Excel usando el SuperAgent.

    Args:
        params: Debe contener 'path'. Opcional: 'hints' (dict).

    Returns:
        dict con status='ok' y data con el contenido parseado.
    """
    path = params.get("path", "")
    hints = params.get("hints")
    return _ensure_engine().parse_smart(path, hints=hints).to_dict()


def handle_excel_read_range(params: dict[str, Any]) -> dict[str, Any]:
    """Lee un rango de celdas de una sesión abierta.

    Args:
        params: session_id, sheet, range (alias range_addr).

    Returns:
        dict con status='ok' y data.values.
    """
    sid = params["session_id"]
    sheet = params["sheet"]
    range_addr = params.get("range", params.get("range_addr"))
    return _ensure_engine().read_range(sid, sheet=sheet, range_addr=range_addr).to_dict()


def handle_excel_write_range(params: dict[str, Any]) -> dict[str, Any]:
    """Escribe valores en un rango de celdas.

    Args:
        params: session_id, sheet, range, values (list[list]).
            Opcional: fmt (dict CellFormat).

    Returns:
        dict con status='ok' o status='error'.
    """
    sid = params["session_id"]
    sheet = params["sheet"]
    range_addr = params.get("range", params.get("range_addr"))
    values = params["values"]
    fmt_dict = params.get("fmt")
    fmt = CellFormat(**fmt_dict) if fmt_dict else None
    return (
        _ensure_engine()
        .write_range(sid, sheet=sheet, range_addr=range_addr, values=values, fmt=fmt)
        .to_dict()
    )


def handle_excel_apply_formula(params: dict[str, Any]) -> dict[str, Any]:
    """Aplica una fórmula a un rango de celdas.

    Args:
        params: session_id, sheet, range, formula (str).

    Returns:
        dict con status='ok' o status='error'.
    """
    sid = params["session_id"]
    sheet = params["sheet"]
    range_addr = params.get("range", params.get("range_addr"))
    formula = params["formula"]
    return (
        _ensure_engine()
        .apply_formula(sid, sheet=sheet, range_addr=range_addr, formula=formula)
        .to_dict()
    )


def handle_excel_set_format(params: dict[str, Any]) -> dict[str, Any]:
    """Aplica formato a un rango de celdas.

    Args:
        params: session_id, sheet, range, fmt (dict CellFormat).

    Returns:
        dict con status='ok' o status='error'.
    """
    sid = params["session_id"]
    sheet = params["sheet"]
    range_addr = params.get("range", params.get("range_addr"))
    fmt = CellFormat(**params.get("fmt", {}))
    return _ensure_engine().set_format(sid, sheet=sheet, range_addr=range_addr, fmt=fmt).to_dict()


def handle_excel_create_table(params: dict[str, Any]) -> dict[str, Any]:
    """Crea una tabla con estilo en el rango indicado.

    Args:
        params: session_id, sheet, range, name. Opcional: style.

    Returns:
        dict con status='ok' o status='error'.
    """
    sid = params["session_id"]
    return (
        _ensure_engine()
        .create_table(
            sid,
            sheet=params["sheet"],
            range_addr=params.get("range", params.get("range_addr")),
            name=params["name"],
            style=params.get("style"),
        )
        .to_dict()
    )


def handle_excel_save_as(params: dict[str, Any]) -> dict[str, Any]:
    """Guarda la sesión en una ruta distinta con un formato dado.

    Args:
        params: session_id, path (destino), format (str).

    Returns:
        dict con status='ok' o status='error'.
    """
    sid = params["session_id"]
    return _ensure_engine().save_as(sid, path=params["path"], format=params["format"]).to_dict()


def handle_excel_health(params: dict[str, Any]) -> dict[str, Any]:  # noqa: ARG001
    """Health check; reporta backends disponibles.

    Args:
        params: No se usan parámetros.

    Returns:
        dict con status='ok' y data.backends_available.
    """
    available = ["openpyxl", "super-agent"]
    return {
        "status": "ok",
        "data": {
            "backends_available": available,
            "xlwings_ready": False,
            "note": (
                "Plan A: xlwings no incluido; ops que lo requieren devuelven BACKEND_NOT_SHIPPED"
            ),
        },
    }


# ---------------------------------------------------------------------------
# Plan B handlers — delegan al engine con los params correctos
# ---------------------------------------------------------------------------


def handle_excel_run_macro(params: dict[str, Any]) -> dict[str, Any]:
    """Ejecuta una macro VBA (requiere xlwings).

    Args:
        params: session_id, macro_name, args.

    Returns:
        dict con status='ok' o status='error'.
    """
    sid = params.get("session_id", "")
    macro_name = params.get("macro_name", "")
    args: list[Any] = params.get("args", [])
    return _ensure_engine().run_macro(sid, macro_name, args).to_dict()


def handle_excel_create_chart(params: dict[str, Any]) -> dict[str, Any]:
    """Crea un gráfico en la hoja.

    Args:
        params: session_id, sheet, range_addr, chart_type, title, legend.

    Returns:
        dict con status='ok' o status='error'.
    """
    sid = params.get("session_id", "")
    sheet = params.get("sheet", "")
    range_addr = params.get("range_addr", params.get("source_range", ""))
    chart_type = params.get("chart_type", "column")
    title = params.get("title")
    legend = params.get("legend", True)
    return (
        _ensure_engine()
        .create_chart(sid, sheet=sheet, range_addr=range_addr, chart_type=chart_type, title=title, legend=legend)
        .to_dict()
    )


def handle_excel_create_pivot(params: dict[str, Any]) -> dict[str, Any]:
    """Crea una tabla dinámica.

    Args:
        params: session_id, source_sheet, source_range, target_sheet, target_cell,
            row_fields, col_fields, value_fields.

    Returns:
        dict con status='ok' o status='error'.
    """
    sid = params.get("session_id", "")
    sheet = params.get("source_sheet", "")
    data_range = params.get("source_range", "")
    dest_cell = params.get("target_cell", "")
    rows = params.get("row_fields")
    columns = params.get("col_fields")
    values = params.get("value_fields")
    return (
        _ensure_engine()
        .create_pivot(sid, sheet=sheet, data_range=data_range, dest_cell=dest_cell,
                       rows=rows, columns=columns, values=values)
        .to_dict()
    )


def handle_excel_update_dashboard(params: dict[str, Any]) -> dict[str, Any]:
    """Actualiza un dashboard.

    Args:
        params: session_id, kpis (dict con sheet y data_sheets).

    Returns:
        dict con status='ok' o status='error'.
    """
    sid = params.get("session_id", "")
    kpis = params.get("kpis", {})
    dashboard_sheet = kpis.get("sheet", "Dashboard")
    data_sheets = kpis.get("data_sheets", [])
    refresh_all = kpis.get("refresh_all", True)
    return (
        _ensure_engine()
        .update_dashboard(sid, dashboard_sheet=dashboard_sheet,
                           data_sheets=data_sheets, refresh_all=refresh_all)
        .to_dict()
    )


def handle_excel_screenshot(params: dict[str, Any]) -> dict[str, Any]:
    """Captura una hoja o región como imagen PNG.

    Args:
        params: session_id, sheet, path, region (opcional).

    Returns:
        dict con status='ok' o status='error'.
    """
    sid = params.get("session_id", "")
    sheet = params.get("sheet", "")
    path = params.get("path", "")
    region = params.get("region")
    return _ensure_engine().screenshot(sid, sheet=sheet, path=path, region=region).to_dict()


def handle_excel_power_query(params: dict[str, Any]) -> dict[str, Any]:
    """Ejecuta una Power Query.

    Args:
        params: session_id, action (query_name), m_code (connection_string),
            output_cell (opcional, default 'A1'), sql (opcional).

    Returns:
        dict con status='ok' o status='error'.
    """
    sid = params.get("session_id", "")
    query_name = params.get("action", "")
    connection_string = params.get("m_code", "")
    output_cell = params.get("output_cell", "A1")
    sql = params.get("sql")
    return (
        _ensure_engine()
        .power_query(sid, query_name=query_name, connection_string=connection_string,
                      output_cell=output_cell, sql=sql)
        .to_dict()
    )


def handle_excel_dax_measure(params: dict[str, Any]) -> dict[str, Any]:
    """Crea o actualiza una medida DAX.

    Args:
        params: session_id, table (table_name), name (measure_name), expression.

    Returns:
        dict con status='ok' o status='error'.
    """
    sid = params.get("session_id", "")
    table_name = params.get("table", "")
    measure_name = params.get("name", "")
    expression = params.get("expression", "")
    return (
        _ensure_engine()
        .dax_measure(sid, table_name=table_name, measure_name=measure_name, expression=expression)
        .to_dict()
    )


def handle_excel_slicer(params: dict[str, Any]) -> dict[str, Any]:
    """Agrega un slicer a la hoja.

    Args:
        params: session_id, action, slicer_name (pivot_table_name),
            items (selections, no-op en engine), dest_cell.

    Returns:
        dict con status='ok' o status='error'.
    """
    sid = params.get("session_id", "")
    pivot_table_name = params.get("slicer_name", "")
    # items (selections) no es parametro del engine; se ignora
    source_field = params.get("items", "")
    dest_cell = params.get("dest_cell", "")
    style = params.get("style")
    return (
        _ensure_engine()
        .slicer(sid, pivot_table_name=pivot_table_name, source_field=source_field,
                 dest_cell=dest_cell, style=style)
        .to_dict()
    )


def handle_excel_conditional_format(params: dict[str, Any]) -> dict[str, Any]:
    """Aplica formato condicional a un rango.

    Args:
        params: session_id, sheet, range_addr, rule (dict con type, threshold, style).

    Returns:
        dict con status='ok' o status='error'.
    """
    sid = params.get("session_id", "")
    sheet = params.get("sheet", "")
    range_addr = params.get("range_addr", "")
    rule = params.get("rule", {})
    rule_type = rule.get("type", "cell_value")
    formula_or_threshold = rule.get("threshold", rule.get("formula"))
    format_style = rule.get("style")
    return (
        _ensure_engine()
        .conditional_format(sid, sheet=sheet, range_addr=range_addr,
                             rule_type=rule_type, formula_or_threshold=formula_or_threshold,
                             format_style=format_style)
        .to_dict()
    )


def handle_excel_calculation_mode(params: dict[str, Any]) -> dict[str, Any]:
    """Cambia el modo de cálculo de Excel.

    Args:
        params: session_id, mode ('automatic'|'manual'|'semiautomatic').

    Returns:
        dict con status='ok' o status='error'.
    """
    sid = params.get("session_id", "")
    mode = params.get("mode", "automatic")
    return _ensure_engine().calculation_mode(sid, mode=mode).to_dict()


# ---------------------------------------------------------------------------
# Dispatcher — tabla de despacho JSON-RPC 2.0
# ---------------------------------------------------------------------------

METHODS: dict[str, Any] = {
    "excel_open": handle_excel_open,
    "excel_close": handle_excel_close,
    "excel_list_sessions": handle_excel_list_sessions,
    "excel_parse_smart": handle_excel_parse_smart,
    "excel_read_range": handle_excel_read_range,
    "excel_write_range": handle_excel_write_range,
    "excel_apply_formula": handle_excel_apply_formula,
    "excel_set_format": handle_excel_set_format,
    "excel_create_table": handle_excel_create_table,
    "excel_save_as": handle_excel_save_as,
    "excel_health": handle_excel_health,
    "excel_run_macro": handle_excel_run_macro,
    "excel_create_chart": handle_excel_create_chart,
    "excel_create_pivot": handle_excel_create_pivot,
    "excel_update_dashboard": handle_excel_update_dashboard,
    "excel_screenshot": handle_excel_screenshot,
    "excel_power_query": handle_excel_power_query,
    "excel_dax_measure": handle_excel_dax_measure,
    "excel_slicer": handle_excel_slicer,
    "excel_conditional_format": handle_excel_conditional_format,
    "excel_calculation_mode": handle_excel_calculation_mode,
}


def handle_request(request: dict[str, Any]) -> dict[str, Any]:
    """Despacha un request JSON-RPC 2.0 al handler correspondiente.

    Args:
        request: dict con jsonrpc, id, method, params.

    Returns:
        dict JSON-RPC 2.0 con result o error.
    """
    method = request.get("method", "")
    params = request.get("params", {}) or {}
    rid = request.get("id")
    # P1: Notifications JSON-RPC 2.0 no deben responder
    if rid is None or method.startswith("notifications/"):
        return None
    handler = METHODS.get(method)
    if handler is None:
        return {
            "jsonrpc": "2.0",
            "id": rid,
            "error": {
                "code": -32601,
                "message": f"method not found: {method}",
            },
        }
    try:
        result = handler(params)
        return {"jsonrpc": "2.0", "id": rid, "result": result}
    except Exception as exc:  # noqa: BLE001
        logger.exception("handler %s lanzó excepción", method)
        return {
            "jsonrpc": "2.0",
            "id": rid,
            "error": {
                "code": -32000,
                "message": str(exc),
            },
        }


# ---------------------------------------------------------------------------
# Entry point stdio
# ---------------------------------------------------------------------------


def main() -> None:
    """Lee líneas JSON de stdin y escribe respuestas JSON-RPC en stdout."""
    try:
        _ensure_engine()
    except Exception:
        logger.warning("Engine no listo al arrancar; se reintenta en el primer request")

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            response = handle_request(request)
            if response is not None:
                print(json.dumps(response, ensure_ascii=False), flush=True)
        except json.JSONDecodeError as exc:
            print(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {
                            "code": -32700,
                            "message": f"Parse error: {exc}",
                        },
                    }
                ),
                flush=True,
            )


if __name__ == "__main__":
    main()
