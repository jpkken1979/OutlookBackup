#!/usr/bin/env python3
"""excel-toolkit CLI — fallback directo al ExcelEngine.

Invoca el engine directamente via import Python (no HTTP), para debugging
o cuando el gateway no esta corriendo.

Usage:
    python scripts/main.py parse --path <file>
    python scripts/main.py write --session <id> --sheet <name> --range <addr> --values <json>
    python scripts/main.py chart --session <id> --sheet <name> --range <addr> --type <type>
    python scripts/main.py macro --session <id> --name <macro>
    python scripts/main.py power --session <id> --action <name>
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup — mismo patron que excel-server.py
# ---------------------------------------------------------------------------
_AGENT_DIR = Path(__file__).resolve().parent.parent.parent.parent / ".agent"
if str(_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(_AGENT_DIR))

sys.path.insert(0, str(_AGENT_DIR / "core"))
sys.path.insert(0, str(_AGENT_DIR / "core" / "excel_engine"))

from core.brain import Brain  # noqa: E402
from core.excel_engine import ExcelEngine  # noqa: E402
from core.excel_engine.types import CellFormat  # noqa: E402


def _engine() -> ExcelEngine:
    """Crea una instancia del ExcelEngine con Brain real."""
    brain_dir = os.getenv("ANTIGRAVITY_BRAIN_DIR")
    if brain_dir is None:
        antigravity_root = os.getenv("ANTIGRAVITY_ROOT", "")
        if antigravity_root:
            brain_dir = str(Path(antigravity_root) / ".agent" / "brain")
        else:
            brain_dir = str(Path.home() / ".antigravity" / "brain")
    brain = Brain(Path(brain_dir), app_id="excel-toolkit-cli")
    return ExcelEngine(brain=brain)


def cmd_parse(path: str, hints_json: str | None) -> None:
    """Parse inteligente de archivo Excel."""
    engine = _engine()
    hints = json.loads(hints_json) if hints_json else None
    result = engine.parse_smart(path, hints=hints)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


def cmd_open(path: str, mode: str) -> None:
    """Abre archivo Excel y devuelve session_id."""
    engine = _engine()
    result = engine.open(path, mode=mode)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


def cmd_close(session_id: str, save: bool) -> None:
    """Cierra sesion."""
    engine = _engine()
    result = engine.close(session_id, save=save)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


def cmd_list() -> None:
    """Lista sesiones activas."""
    engine = _engine()
    result = engine.list_sessions()
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


def cmd_read(session_id: str, sheet: str, range_addr: str) -> None:
    """Lee rango de celdas."""
    engine = _engine()
    result = engine.read_range(session_id, sheet=sheet, range_addr=range_addr)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


def cmd_write(
    session_id: str, sheet: str, range_addr: str, values_json: str, fmt_json: str | None,
) -> None:
    """Escribe valores en rango."""
    engine = _engine()
    values = json.loads(values_json)
    fmt = CellFormat(**json.loads(fmt_json)) if fmt_json else None
    result = engine.write_range(
        session_id, sheet=sheet, range_addr=range_addr, values=values, fmt=fmt
    )
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


def cmd_formula(session_id: str, sheet: str, range_addr: str, formula: str) -> None:
    """Aplica formula a rango."""
    engine = _engine()
    result = engine.apply_formula(session_id, sheet=sheet, range_addr=range_addr, formula=formula)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


def cmd_format(session_id: str, sheet: str, range_addr: str, fmt_json: str) -> None:
    """Aplica formato a rango."""
    engine = _engine()
    fmt = CellFormat(**json.loads(fmt_json))
    result = engine.set_format(session_id, sheet=sheet, range_addr=range_addr, fmt=fmt)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


def cmd_table(session_id: str, sheet: str, range_addr: str, name: str, style: str | None) -> None:
    """Crea tabla Excel."""
    engine = _engine()
    result = engine.create_table(
        session_id, sheet=sheet, range_addr=range_addr, name=name, style=style
    )
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


def cmd_save(session_id: str, path: str, fmt: str) -> None:
    """Guarda workbook como."""
    engine = _engine()
    result = engine.save_as(session_id, path=path, format=fmt)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


def cmd_chart(session_id: str, sheet: str, range_addr: str, chart_type: str,
              title: str | None, legend: bool) -> None:
    """Crea grafico."""
    engine = _engine()
    result = engine.create_chart(session_id, sheet=sheet, range_addr=range_addr,
                                 chart_type=chart_type, title=title, legend=legend)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


def cmd_pivot(session_id: str, sheet: str, data_range: str, dest_cell: str,
             rows: str | None, columns: str | None, values: str | None) -> None:
    """Crea tabla pivote."""
    engine = _engine()
    result = engine.create_pivot(
        session_id, sheet=sheet, data_range=data_range, dest_cell=dest_cell,
        rows=json.loads(rows) if rows else None,
        columns=json.loads(columns) if columns else None,
        values=json.loads(values) if values else None,
    )
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


def cmd_macro(session_id: str, name: str, args_json: str | None) -> None:
    """Ejecuta macro VBA."""
    engine = _engine()
    args = json.loads(args_json) if args_json else []
    result = engine.run_macro(session_id, macro_name=name, args=args)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


def cmd_dashboard(session_id: str, dashboard_sheet: str, data_sheets_json: str,
                  refresh_all: bool) -> None:
    """Actualiza dashboard."""
    engine = _engine()
    data_sheets = json.loads(data_sheets_json) if data_sheets_json else []
    result = engine.update_dashboard(session_id, dashboard_sheet=dashboard_sheet,
                                     data_sheets=data_sheets, refresh_all=refresh_all)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


def cmd_screenshot(session_id: str, sheet: str, path: str, region: str | None) -> None:
    """Captura hoja como PNG."""
    engine = _engine()
    result = engine.screenshot(session_id, sheet=sheet, path=path, region=region)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


def cmd_power(session_id: str, query_name: str, connection_string: str,
              output_cell: str, sql: str | None) -> None:
    """Ejecuta Power Query."""
    engine = _engine()
    result = engine.power_query(session_id, query_name=query_name,
                                connection_string=connection_string,
                                output_cell=output_cell, sql=sql)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


def cmd_dax(session_id: str, table: str, name: str, expression: str) -> None:
    """Crea medida DAX."""
    engine = _engine()
    result = engine.dax_measure(session_id, table_name=table,
                                measure_name=name, expression=expression)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


def cmd_slicer(session_id: str, pivot_table: str, source_field: str,
               dest_cell: str, style: str | None) -> None:
    """Crea slicer."""
    engine = _engine()
    result = engine.slicer(session_id, pivot_table_name=pivot_table,
                           source_field=source_field, dest_cell=dest_cell, style=style)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


def cmd_cond_fmt(session_id: str, sheet: str, range_addr: str,
                 rule_type: str, threshold: str, style: str | None) -> None:
    """Aplica formato condicional."""
    engine = _engine()
    result = engine.conditional_format(session_id, sheet=sheet, range_addr=range_addr,
                                      rule_type=rule_type,
                                      formula_or_threshold=threshold,
                                      format_style=style)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


def cmd_calc_mode(session_id: str, mode: str) -> None:
    """Cambia modo de calculo."""
    engine = _engine()
    result = engine.calculation_mode(session_id, mode=mode)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


def cmd_health() -> None:
    """Health check del engine."""
    engine = _engine()
    # El engine no tiene health propio, pero podemos listar sesiones como proxy
    result = engine.list_sessions()
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="excel-toolkit CLI — fallback directo al ExcelEngine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # parse
    p_parse = sub.add_parser("parse", help="Parse inteligente de archivo Excel")
    p_parse.add_argument("--path", required=True, help="Ruta al archivo Excel")
    p_parse.add_argument("--hints", help="JSON hints dict")

    # open
    p_open = sub.add_parser("open", help="Abre archivo Excel")
    p_open.add_argument("--path", required=True, help="Ruta al archivo")
    p_open.add_argument("--mode", default="write", choices=["read", "write", "live"],
                        help="Modo de apertura")

    # close
    p_close = sub.add_parser("close", help="Cierra sesion")
    p_close.add_argument("--session", required=True, help="Session ID")
    p_close.add_argument("--save", default="true", help="Guardar cambios (true/false)")

    # list
    sub.add_parser("list", help="Lista sesiones activas")

    # read
    p_read = sub.add_parser("read", help="Lee rango de celdas")
    p_read.add_argument("--session", required=True)
    p_read.add_argument("--sheet", required=True)
    p_read.add_argument("--range", required=True)

    # write
    p_write = sub.add_parser("write", help="Escribe valores en rango")
    p_write.add_argument("--session", required=True)
    p_write.add_argument("--sheet", required=True)
    p_write.add_argument("--range", required=True)
    p_write.add_argument("--values", required=True, help="JSON 2D array")
    p_write.add_argument("--fmt", help="JSON CellFormat")

    # formula
    p_formula = sub.add_parser("formula", help="Aplica formula a rango")
    p_formula.add_argument("--session", required=True)
    p_formula.add_argument("--sheet", required=True)
    p_formula.add_argument("--range", required=True)
    p_formula.add_argument("--formula", required=True)

    # format
    p_fmt = sub.add_parser("format", help="Aplica formato a rango")
    p_fmt.add_argument("--session", required=True)
    p_fmt.add_argument("--sheet", required=True)
    p_fmt.add_argument("--range", required=True)
    p_fmt.add_argument("--fmt", required=True, help="JSON CellFormat")

    # table
    p_table = sub.add_parser("table", help="Crea tabla Excel")
    p_table.add_argument("--session", required=True)
    p_table.add_argument("--sheet", required=True)
    p_table.add_argument("--range", required=True)
    p_table.add_argument("--name", required=True)
    p_table.add_argument("--style", help="Nombre del estilo")

    # save
    p_save = sub.add_parser("save", help="Guarda workbook como")
    p_save.add_argument("--session", required=True)
    p_save.add_argument("--path", required=True)
    p_save.add_argument("--format", required=True, choices=["xlsx", "pdf", "csv", "xlsm"])

    # chart
    p_chart = sub.add_parser("chart", help="Crea grafico")
    p_chart.add_argument("--session", required=True)
    p_chart.add_argument("--sheet", required=True)
    p_chart.add_argument("--range", required=True)
    p_chart.add_argument("--type", required=True,
                         choices=["column", "bar", "line", "pie", "scatter", "area"])
    p_chart.add_argument("--title")
    p_chart.add_argument("--legend", type=bool, default=True)

    # pivot
    p_pivot = sub.add_parser("pivot", help="Crea tabla pivote")
    p_pivot.add_argument("--session", required=True)
    p_pivot.add_argument("--sheet", required=True)
    p_pivot.add_argument("--data-range", required=True)
    p_pivot.add_argument("--dest-cell", required=True)
    p_pivot.add_argument("--rows")
    p_pivot.add_argument("--columns")
    p_pivot.add_argument("--values")

    # macro
    p_macro = sub.add_parser("macro", help="Ejecuta macro VBA")
    p_macro.add_argument("--session", required=True)
    p_macro.add_argument("--name", required=True)
    p_macro.add_argument("--args", help="JSON array de argumentos")

    # dashboard
    p_dash = sub.add_parser("dashboard", help="Actualiza dashboard")
    p_dash.add_argument("--session", required=True)
    p_dash.add_argument("--dashboard-sheet", required=True)
    p_dash.add_argument("--data-sheets", help="JSON array de nombres de hojas")
    p_dash.add_argument("--refresh-all", type=bool, default=True)

    # screenshot
    p_ss = sub.add_parser("screenshot", help="Captura hoja como PNG")
    p_ss.add_argument("--session", required=True)
    p_ss.add_argument("--sheet", required=True)
    p_ss.add_argument("--path", required=True)
    p_ss.add_argument("--region")

    # power
    p_power = sub.add_parser("power", help="Ejecuta Power Query")
    p_power.add_argument("--session", required=True)
    p_power.add_argument("--query-name", required=True)
    p_power.add_argument("--connection-string", default="")
    p_power.add_argument("--output-cell", default="A1")
    p_power.add_argument("--sql")

    # dax
    p_dax = sub.add_parser("dax", help="Crea medida DAX")
    p_dax.add_argument("--session", required=True)
    p_dax.add_argument("--table", required=True)
    p_dax.add_argument("--name", required=True)
    p_dax.add_argument("--expression", required=True)

    # slicer
    p_slicer = sub.add_parser("slicer", help="Crea slicer")
    p_slicer.add_argument("--session", required=True)
    p_slicer.add_argument("--pivot-table", required=True)
    p_slicer.add_argument("--source-field", required=True)
    p_slicer.add_argument("--dest-cell", required=True)
    p_slicer.add_argument("--style")

    # cond_fmt
    p_cf = sub.add_parser("cond-fmt", help="Aplica formato condicional")
    p_cf.add_argument("--session", required=True)
    p_cf.add_argument("--sheet", required=True)
    p_cf.add_argument("--range", required=True)
    p_cf.add_argument("--rule-type", required=True,
                      choices=["cell_value", "formula", "color_scale", "data_bar", "icon_set"])
    p_cf.add_argument("--threshold", required=True)
    p_cf.add_argument("--style")

    # calc_mode
    p_calc = sub.add_parser("calc-mode", help="Cambia modo de calculo")
    p_calc.add_argument("--session", required=True)
    p_calc.add_argument("--mode", required=True, choices=["automatic", "manual", "semiautomatic"])

    # health
    sub.add_parser("health", help="Health check del engine")

    args = parser.parse_args()

    try:
        if args.cmd == "parse":
            cmd_parse(args.path, args.hints)
        elif args.cmd == "open":
            cmd_open(args.path, args.mode)
        elif args.cmd == "close":
            cmd_close(args.session, args.save.lower() == "true")
        elif args.cmd == "list":
            cmd_list()
        elif args.cmd == "read":
            cmd_read(args.session, args.sheet, args.range)
        elif args.cmd == "write":
            cmd_write(args.session, args.sheet, args.range, args.values, args.fmt)
        elif args.cmd == "formula":
            cmd_formula(args.session, args.sheet, args.range, args.formula)
        elif args.cmd == "format":
            cmd_format(args.session, args.sheet, args.range, args.fmt)
        elif args.cmd == "table":
            cmd_table(args.session, args.sheet, args.range, args.name, args.style)
        elif args.cmd == "save":
            cmd_save(args.session, args.path, args.format)
        elif args.cmd == "chart":
            cmd_chart(args.session, args.sheet, args.range, args.type, args.title, args.legend)
        elif args.cmd == "pivot":
            cmd_pivot(args.session, args.sheet, args.data_range, args.dest_cell,
                      args.rows, args.columns, args.values)
        elif args.cmd == "macro":
            cmd_macro(args.session, args.name, args.args)
        elif args.cmd == "dashboard":
            cmd_dashboard(args.session, args.dashboard_sheet, args.data_sheets, args.refresh_all)
        elif args.cmd == "screenshot":
            cmd_screenshot(args.session, args.sheet, args.path, args.region)
        elif args.cmd == "power":
            cmd_power(args.session, args.query_name, args.connection_string,
                      args.output_cell, args.sql)
        elif args.cmd == "dax":
            cmd_dax(args.session, args.table, args.name, args.expression)
        elif args.cmd == "slicer":
            cmd_slicer(
            args.session, args.pivot_table, args.source_field, args.dest_cell, args.style,
        )
        elif args.cmd == "cond-fmt":
            cmd_cond_fmt(
                args.session, args.sheet, args.range, args.rule_type,
                args.threshold, args.style,
            )
        elif args.cmd == "calc-mode":
            cmd_calc_mode(args.session, args.mode)
        elif args.cmd == "health":
            cmd_health()
    except Exception as exc:
        print(json.dumps({
            "status": "error",
            "error": {"category": "fatal", "code": "CLI_ERROR", "message": str(exc)}
        }, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
