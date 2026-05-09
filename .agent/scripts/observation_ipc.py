#!/usr/bin/env python3
"""Observation IPC helper — Bridge seguro para Electron.

Recibe comandos por argumentos de línea de comandos en lugar de
código Python inyectado. Diseñado para uso desde ipcMain.handle()
de Nexus Desktop.

Comandos disponibles:
- stats: Obtener estadísticas del pipeline de observaciones.
- search <query> [--limit N]: Buscar observaciones por texto.
- sessions [--limit N]: Obtener sesiones recientes.
- file-history <path> [--limit N]: Obtener historial de un archivo.
- projects: Resumen de proyectos observados por el pipeline local.
- queue: Cola derivada de sesiones fallidas o incompletas.
"""

import argparse
import json
import sys
from pathlib import Path


def _validate_root(root: str) -> Path:
    """Valida que root sea un directorio Antigravity legítimo.

    Args:
        root: Ruta candidata al proyecto.

    Returns:
        Path resuelto y validado.

    Raises:
        ValueError: Si la ruta no es un directorio Antigravity válido.
    """
    root_path = Path(root).resolve()
    if not root_path.is_dir():
        raise ValueError(f"Root path does not exist: {root_path}")
    if not (root_path / ".agent").is_dir():
        raise ValueError(f"Not an Antigravity project (missing .agent/): {root_path}")
    return root_path


def _validate_file_path(root: Path, file_path: str) -> str:
    """Valida que file_path esté dentro del proyecto (previene path traversal).

    Args:
        root: Ruta raíz validada del proyecto.
        file_path: Ruta del archivo a consultar.

    Returns:
        Ruta normalizada y validada.

    Raises:
        ValueError: Si file_path escapa del directorio del proyecto.
    """
    resolved = Path(file_path).resolve()
    if not str(resolved).startswith(str(root)):
        raise ValueError(f"Path traversal detected: {file_path} escapes {root}")
    return str(resolved)


def _setup_path(root: Path) -> None:
    """Agrega .agent/ al sys.path para importar módulos core."""
    agent_path = str(root / ".agent")
    if agent_path not in sys.path:
        sys.path.insert(0, agent_path)


def cmd_stats(root: str) -> dict:
    """Obtiene estadísticas del pipeline de observaciones.

    Args:
        root: Ruta raíz del proyecto Antigravity.

    Returns:
        Diccionario con éxito y estadísticas.
    """
    root_path = _validate_root(root)
    _setup_path(root_path)
    from core.observation_pipeline import get_observation_pipeline

    pipeline = get_observation_pipeline(str(root_path))
    stats = pipeline.get_stats()
    return {"success": True, "stats": stats}


def cmd_search(root: str, query: str, limit: int = 10) -> dict:
    """Busca observaciones por texto.

    Args:
        root: Ruta raíz del proyecto Antigravity.
        query: Texto a buscar.
        limit: Número máximo de resultados.

    Returns:
        Diccionario con éxito y resultados.
    """
    root_path = _validate_root(root)
    _setup_path(root_path)
    from core.hybrid_search import get_hybrid_search

    search = get_hybrid_search(str(root_path))
    results = search.search_sql(query, limit=limit)
    return {"success": True, "results": [r.to_dict() for r in results]}


def cmd_sessions(root: str, limit: int = 10) -> dict:
    """Obtiene sesiones recientes.

    Args:
        root: Ruta raíz del proyecto Antigravity.
        limit: Número máximo de sesiones.

    Returns:
        Diccionario con éxito y sesiones.
    """
    root_path = _validate_root(root)
    _setup_path(root_path)
    from core.observation_pipeline import get_observation_pipeline

    pipeline = get_observation_pipeline(str(root_path))
    summaries = pipeline._store.get_recent_session_summaries(limit)
    return {"success": True, "sessions": summaries}


def cmd_file_history(root: str, file_path: str, limit: int = 20) -> dict:
    """Obtiene historial de observaciones para un archivo.

    Args:
        root: Ruta raíz del proyecto Antigravity.
        file_path: Ruta del archivo a consultar.
        limit: Número máximo de entradas.

    Returns:
        Diccionario con éxito e historial.
    """
    root_path = _validate_root(root)
    safe_path = _validate_file_path(root_path, file_path)
    _setup_path(root_path)
    from core.observation_pipeline import get_observation_pipeline

    pipeline = get_observation_pipeline(str(root_path))
    obs = pipeline._store.get_observations_by_file(safe_path, limit)
    entries = [
        {
            "timestamp": o.timestamp,
            "tool": o.tool_name,
            "action": o.observation_type,
            "summary": o.tool_input_summary,
            "success": o.success,
            "error": o.error_message,
        }
        for o in obs
    ]
    return {"success": True, "history": entries}


def cmd_projects(root: str) -> dict:
    """Construye una vista simple de proyectos a partir del pipeline local."""
    root_path = _validate_root(root)
    _setup_path(root_path)
    from core.observation_pipeline import get_observation_pipeline

    pipeline = get_observation_pipeline(str(root_path))
    stats = pipeline.get_stats()
    sessions = pipeline._store.get_recent_session_summaries(5)
    latest = sessions[0] if sessions else {}

    project = {
        "name": root_path.name,
        "path": str(root_path),
        "total_observations": stats.get("total_observations", 0),
        "total_sessions": stats.get("total_sessions", 0),
        "last_session_id": latest.get("session_id"),
        "last_activity": latest.get("end_time") or latest.get("start_time"),
        "success_rate": latest.get("success_rate"),
    }
    return {"success": True, "projects": [project]}


def cmd_queue(root: str, limit: int = 20) -> dict:
    """Deriva una cola de sesiones fallidas o incompletas."""
    root_path = _validate_root(root)
    _setup_path(root_path)
    from core.observation_pipeline import get_observation_pipeline

    pipeline = get_observation_pipeline(str(root_path))
    sessions = pipeline._store.get_recent_session_summaries(limit)
    items = []
    for session in sessions:
        success_rate = float(session.get("success_rate", 1.0) or 0.0)
        errors = session.get("errors") or []
        if success_rate >= 1.0 and not errors:
            continue
        items.append(
            {
                "id": session.get("session_id"),
                "session_id": session.get("session_id"),
                "status": "failed" if success_rate < 1.0 else "review",
                "success_rate": success_rate,
                "error_count": len(errors),
                "errors": errors,
                "updated_at": session.get("end_time") or session.get("start_time"),
            }
        )
    return {"success": True, "items": items}


def main() -> None:
    """Entry point — parsea argumentos y ejecuta el comando solicitado."""
    parser = argparse.ArgumentParser(description="Observation IPC helper")
    parser.add_argument("--root", required=True, help="Antigravity project root path")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("stats")

    search_p = sub.add_parser("search")
    search_p.add_argument("query", help="Search text")
    search_p.add_argument("--limit", type=int, default=10)

    sessions_p = sub.add_parser("sessions")
    sessions_p.add_argument("--limit", type=int, default=10)

    fh_p = sub.add_parser("file-history")
    fh_p.add_argument("path", help="File path to look up")
    fh_p.add_argument("--limit", type=int, default=20)

    sub.add_parser("projects")

    queue_p = sub.add_parser("queue")
    queue_p.add_argument("--limit", type=int, default=20)

    args = parser.parse_args()

    try:
        if args.command == "stats":
            result = cmd_stats(args.root)
        elif args.command == "search":
            result = cmd_search(args.root, args.query, args.limit)
        elif args.command == "sessions":
            result = cmd_sessions(args.root, args.limit)
        elif args.command == "file-history":
            result = cmd_file_history(args.root, args.path, args.limit)
        elif args.command == "projects":
            result = cmd_projects(args.root)
        elif args.command == "queue":
            result = cmd_queue(args.root, args.limit)
        else:
            result = {"success": False, "error": f"Unknown command: {args.command}"}
    except Exception as e:
        result = {"success": False, "error": str(e)}

    print(json.dumps(result))


if __name__ == "__main__":
    main()
