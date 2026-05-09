#!/usr/bin/env python3
"""
UNS MCP SERVER - Antigravity Extension
=======================================
Expone las herramientas de UNS-Kikaku al Model Context Protocol.
"""

from mcp.server.fastmcp import FastMCP
import sys
from pathlib import Path

# Agregar rutas de skills al path
sys.path.append(str(Path(__file__).parent.parent / ".agent/skills/uns-enterprise/uns-data-loader/scripts"))

mcp = FastMCP("UNS-Commander")

@mcp.tool()
def get_active_employees_count() -> str:
    """Retorna el conteo actual de empleados activos en el Excel maestro."""
    from data_loader import EmployeeLoader
    try:
        loader = EmployeeLoader()
        haken = loader.process_haken(loader.load_sheet("派遣社員", header_row=1))
        ukeoi = loader.process_ukeoi(loader.load_sheet("請負社員", header_row=2))
        active_haken = len([e for e in haken if e['is_active']])
        active_ukeoi = len([e for e in ukeoi if e['is_active']])
        return f"Total Activos: {active_haken + active_ukeoi} (Haken: {active_haken}, Ukeoi: {active_ukeoi})"
    except Exception as e:
        return f"Error leyendo datos: {e}"

@mcp.tool()
def get_japanese_labor_rule(topic: str) -> str:
    """Consulta las reglas de la ley laboral japonesa (Haken-ho, 36 Kyotei)."""
    kb_path = Path(__file__).parent.parent / "docs/knowledge/KNOWLEDGE_LEGAL_JP.md"
    if not kb_path.exists():
        return "Conocimiento legal no inicializado."

    with open(kb_path, encoding="utf-8") as f:
        content = f.read()

    # Búsqueda simple por palabra clave
    lines = content.split("\n")
    relevant = [l for l in lines if topic.lower() in l.lower()]
    return "\n".join(relevant) if relevant else "Tema no encontrado en la base de datos legal."

if __name__ == "__main__":
    mcp.run()
