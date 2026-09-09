"""Sandboxed in-process connectors for project files, Git and SQLite.

These adapters keep the default broker useful while avoiding one process per
connector.  Every filesystem path is resolved below the active project root and
known secret/configuration files are never exposed through the MCP surface.
"""

from __future__ import annotations

import base64
import importlib.util
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from .models import ConnectorStatus

_MAX_FILE_BYTES = 1_048_576
_MAX_WRITE_BYTES = 2_097_152
_MAX_SEARCH_FILES = 2_000
_MAX_RESULTS = 200
_SAFE_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/@{}~^:+-]{0,199}$")
_DATABASE_SUFFIXES = {".db", ".sqlite", ".sqlite3"}
_SKIP_DIRECTORIES = {
    ".git",
    ".venv",
    ".venv-mcp",
    "__pycache__",
    "node_modules",
    "target",
}
_PROTECTED_NAMES = {
    ".env",
    "auth.json",
    "credentials.json",
    "codex-accounts.json",
    "secrets.json",
}

INTERNAL_OPERATIONS: dict[str, tuple[str, ...]] = {
    "filesystem": (
        "read_file",
        "list_directory",
        "search_files",
        "get_file_info",
        "write_file",
        "create_directory",
        "move_file",
        "delete_file",
        "remove_directory",
    ),
    "git": (
        "status",
        "diff",
        "log",
        "show",
        "branch_list",
        "add",
        "commit",
        "checkout",
        "branch_create",
        "reset",
        "clean",
        "branch_delete",
    ),
    "sqlite": (
        "list_databases",
        "list_tables",
        "schema",
        "query",
        "execute",
        "integrity_check",
    ),
    "nexus-memory": (
        "recall",
        "search",
        "stats",
        "suggest",
        "brain_query",
        "brain_stats",
        "store",
        "brain_ingest",
        "delete",
        "clear_user",
    ),
}


class InternalConnectorError(RuntimeError):
    """Safe failure returned by an internal connector."""

    def __init__(
        self,
        message: str,
        *,
        status: ConnectorStatus = ConnectorStatus.ERROR,
        retryable: bool = False,
    ):
        super().__init__(message)
        self.status = status
        self.retryable = retryable


def _required_string(arguments: Mapping[str, Any], name: str) -> str:
    value = arguments.get(name)
    if not isinstance(value, str) or not value.strip():
        raise InternalConnectorError(f"Argument '{name}' is required")
    return value.strip()


def _bounded_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return min(max(parsed, minimum), maximum)


def _is_protected(path: Path, root: Path) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return True
    lowered_parts = [part.lower() for part in relative.parts]
    name = relative.name.lower()
    if name in _PROTECTED_NAMES:
        return True
    if name.startswith(".env.") and name != ".env.example":
        return True
    if ".antigravity" in lowered_parts and "state" in lowered_parts:
        return True
    return False


def _workspace_path(
    root: Path,
    raw_path: str,
    *,
    allow_missing: bool = False,
    allow_protected: bool = False,
) -> Path:
    if "\x00" in raw_path:
        raise InternalConnectorError("Path contains invalid characters")
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve(strict=False)
    if not resolved.is_relative_to(root):
        raise InternalConnectorError("Path is outside the active project")
    if not allow_protected and _is_protected(resolved, root):
        raise InternalConnectorError("Protected configuration cannot be accessed through MCP")
    if not allow_missing and not resolved.exists():
        raise InternalConnectorError("Requested path does not exist")
    return resolved


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix() or "."


def _file_payload(path: Path, root: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "path": _relative(path, root),
        "type": "directory" if path.is_dir() else "file",
        "size": stat.st_size,
        "modified_at": stat.st_mtime,
    }


def _fs_read_file(root: Path, arguments: Mapping[str, Any]) -> dict[str, Any]:
    path = _workspace_path(root, _required_string(arguments, "path"))
    if not path.is_file():
        raise InternalConnectorError("Requested path is not a file")
    max_bytes = _bounded_int(
        arguments.get("max_bytes"),
        default=_MAX_FILE_BYTES,
        minimum=1,
        maximum=_MAX_FILE_BYTES,
    )
    if path.stat().st_size > max_bytes:
        raise InternalConnectorError(f"File exceeds the {max_bytes} byte read limit")
    return {
        "path": _relative(path, root),
        "content": path.read_text(encoding="utf-8", errors="replace"),
    }


def _fs_list_directory(root: Path, arguments: Mapping[str, Any]) -> dict[str, Any]:
    raw_path = str(arguments.get("path") or ".")
    path = _workspace_path(root, raw_path)
    if not path.is_dir():
        raise InternalConnectorError("Requested path is not a directory")
    limit = _bounded_int(arguments.get("limit"), default=200, minimum=1, maximum=500)
    entries = []
    for child in sorted(path.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())):
        if child.name in _SKIP_DIRECTORIES or _is_protected(child.resolve(), root):
            continue
        entries.append(_file_payload(child, root))
        if len(entries) >= limit:
            break
    return {"path": _relative(path, root), "entries": entries}


def _is_searchable_file(candidate: Path, root: Path) -> bool:
    """Descarta entradas que no deben escanearse: no-archivos, ruido o protegidas."""
    if not candidate.is_file():
        return False
    relative_parts = candidate.relative_to(root).parts
    if any(part in _SKIP_DIRECTORIES for part in relative_parts):
        return False
    resolved = candidate.resolve()
    return not (_is_protected(resolved, root) or candidate.stat().st_size > _MAX_FILE_BYTES)


def _search_file_matches(
    candidate: Path,
    root: Path,
    needle: str,
    case_sensitive: bool,
    limit: int,
) -> list[dict[str, Any]]:
    """Busca coincidencias de linea dentro de un archivo, acotadas a `limit`."""
    try:
        lines = candidate.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    matches: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines, start=1):
        haystack = line if case_sensitive else line.casefold()
        if needle in haystack:
            matches.append(
                {"path": _relative(candidate, root), "line": line_number, "preview": line[:500]}
            )
            if len(matches) >= limit:
                break
    return matches


def _fs_search_files(root: Path, arguments: Mapping[str, Any]) -> dict[str, Any]:
    query = _required_string(arguments, "query")
    base = _workspace_path(root, str(arguments.get("path") or "."))
    if not base.is_dir():
        raise InternalConnectorError("Search path is not a directory")
    limit = _bounded_int(arguments.get("limit"), default=50, minimum=1, maximum=_MAX_RESULTS)
    case_sensitive = bool(arguments.get("case_sensitive", False))
    needle = query if case_sensitive else query.casefold()
    results: list[dict[str, Any]] = []
    scanned = 0
    for candidate in base.rglob("*"):
        if scanned >= _MAX_SEARCH_FILES or len(results) >= limit:
            break
        if not _is_searchable_file(candidate, root):
            continue
        scanned += 1
        results.extend(
            _search_file_matches(candidate, root, needle, case_sensitive, limit - len(results))
        )
    return {"query": query, "scanned_files": scanned, "results": results}


def _fs_get_file_info(root: Path, arguments: Mapping[str, Any]) -> dict[str, Any]:
    path = _workspace_path(root, _required_string(arguments, "path"))
    return _file_payload(path, root)


def _fs_write_file(root: Path, arguments: Mapping[str, Any]) -> dict[str, Any]:
    path = _workspace_path(root, _required_string(arguments, "path"), allow_missing=True)
    content = arguments.get("content")
    if not isinstance(content, str):
        raise InternalConnectorError("Argument 'content' must be text")
    encoded = content.encode("utf-8")
    if len(encoded) > _MAX_WRITE_BYTES:
        raise InternalConnectorError("Content exceeds the 2 MiB write limit")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="wb",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        temporary = Path(handle.name)
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return _file_payload(path, root)


def _fs_create_directory(root: Path, arguments: Mapping[str, Any]) -> dict[str, Any]:
    path = _workspace_path(root, _required_string(arguments, "path"), allow_missing=True)
    path.mkdir(parents=bool(arguments.get("parents", True)), exist_ok=True)
    return _file_payload(path, root)


def _fs_move_file(root: Path, arguments: Mapping[str, Any]) -> dict[str, Any]:
    source = _workspace_path(root, _required_string(arguments, "source"))
    target = _workspace_path(root, _required_string(arguments, "target"), allow_missing=True)
    if target.exists() and not bool(arguments.get("overwrite", False)):
        raise InternalConnectorError("Target already exists")
    target.parent.mkdir(parents=True, exist_ok=True)
    os.replace(source, target)
    return {"source": _relative(source, root), "target": _relative(target, root)}


def _fs_delete_file(root: Path, arguments: Mapping[str, Any]) -> dict[str, Any]:
    path = _workspace_path(root, _required_string(arguments, "path"))
    if not path.is_file():
        raise InternalConnectorError("Only files can be deleted by this operation")
    path.unlink()
    return {"path": _relative(path, root), "deleted": True}


def _fs_remove_directory(root: Path, arguments: Mapping[str, Any]) -> dict[str, Any]:
    path = _workspace_path(root, _required_string(arguments, "path"))
    if path == root:
        raise InternalConnectorError("The project root cannot be removed")
    try:
        path.rmdir()
    except OSError as exc:
        raise InternalConnectorError("Directory must be empty before removal") from exc
    return {"path": _relative(path, root), "removed": True}


_FILESYSTEM_HANDLERS: dict[str, Callable[[Path, Mapping[str, Any]], dict[str, Any]]] = {
    "read_file": _fs_read_file,
    "list_directory": _fs_list_directory,
    "search_files": _fs_search_files,
    "get_file_info": _fs_get_file_info,
    "write_file": _fs_write_file,
    "create_directory": _fs_create_directory,
    "move_file": _fs_move_file,
    "delete_file": _fs_delete_file,
    "remove_directory": _fs_remove_directory,
}


def _filesystem_call(root: Path, operation: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
    handler = _FILESYSTEM_HANDLERS.get(operation)
    if handler is None:
        raise InternalConnectorError(f"Unsupported filesystem operation '{operation}'")
    return handler(root, arguments)


def _git_executable() -> str:
    discovered = shutil.which("git")
    if discovered:
        return discovered
    candidates = (
        Path("C:/Program Files/Git/cmd/git.exe"),
        Path("C:/Program Files/Git/bin/git.exe"),
    )
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    raise InternalConnectorError("Git executable is not available", status=ConnectorStatus.OFFLINE)


def _safe_ref(value: Any, name: str = "ref") -> str:
    if not isinstance(value, str) or not _SAFE_REF.fullmatch(value.strip()):
        raise InternalConnectorError(f"Argument '{name}' is not a safe Git reference")
    return value.strip()


def _git_paths(root: Path, value: Any) -> list[str]:
    if not isinstance(value, list) or not value:
        raise InternalConnectorError("Argument 'paths' must be a non-empty list")
    paths: list[str] = []
    for raw in value[:200]:
        if not isinstance(raw, str):
            raise InternalConnectorError("Every Git path must be text")
        paths.append(_relative(_workspace_path(root, raw, allow_missing=True), root))
    return paths


def _run_git(root: Path, args: Sequence[str]) -> dict[str, Any]:
    environment = os.environ.copy()
    environment["GIT_TERMINAL_PROMPT"] = "0"
    try:
        completed = subprocess.run(
            [_git_executable(), *args],
            cwd=root,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise InternalConnectorError(
            "Git operation failed to start",
            status=ConnectorStatus.OFFLINE,
            retryable=True,
        ) from exc
    output = completed.stdout[-200_000:]
    error = completed.stderr[-20_000:]
    if completed.returncode != 0:
        raise InternalConnectorError(f"Git operation failed with exit code {completed.returncode}")
    return {
        "exit_code": completed.returncode,
        "stdout": output,
        "stderr": error,
    }


def _git_status(root: Path, arguments: Mapping[str, Any]) -> dict[str, Any]:
    del arguments
    return _run_git(root, ["status", "--short", "--branch"])


def _git_diff(root: Path, arguments: Mapping[str, Any]) -> dict[str, Any]:
    args = ["diff", "--no-ext-diff"]
    if bool(arguments.get("staged", False)):
        args.append("--cached")
    raw_path = arguments.get("path")
    if isinstance(raw_path, str) and raw_path.strip():
        args.extend(["--", _relative(_workspace_path(root, raw_path), root)])
    return _run_git(root, args)


def _git_log(root: Path, arguments: Mapping[str, Any]) -> dict[str, Any]:
    limit = _bounded_int(arguments.get("limit"), default=20, minimum=1, maximum=100)
    return _run_git(
        root,
        ["log", f"-{limit}", "--date=iso-strict", "--pretty=format:%h%x09%ad%x09%s"],
    )


def _git_show(root: Path, arguments: Mapping[str, Any]) -> dict[str, Any]:
    ref = _safe_ref(arguments.get("ref") or "HEAD")
    return _run_git(root, ["show", "--stat", "--oneline", "--decorate", ref])


def _git_branch_list(root: Path, arguments: Mapping[str, Any]) -> dict[str, Any]:
    del arguments
    return _run_git(root, ["branch", "--list", "--verbose", "--no-abbrev"])


def _git_add(root: Path, arguments: Mapping[str, Any]) -> dict[str, Any]:
    return _run_git(root, ["add", "--", *_git_paths(root, arguments.get("paths"))])


def _git_commit(root: Path, arguments: Mapping[str, Any]) -> dict[str, Any]:
    message = _required_string(arguments, "message")
    if len(message) > 500:
        raise InternalConnectorError("Commit message exceeds 500 characters")
    return _run_git(root, ["commit", "-m", message])


def _git_checkout(root: Path, arguments: Mapping[str, Any]) -> dict[str, Any]:
    return _run_git(root, ["checkout", _safe_ref(arguments.get("ref"))])


def _git_branch_create(root: Path, arguments: Mapping[str, Any]) -> dict[str, Any]:
    return _run_git(root, ["branch", _safe_ref(arguments.get("name"), "name")])


def _git_reset(root: Path, arguments: Mapping[str, Any]) -> dict[str, Any]:
    mode = str(arguments.get("mode") or "mixed").lower()
    if mode not in {"soft", "mixed", "hard"}:
        raise InternalConnectorError("Reset mode must be soft, mixed or hard")
    ref = _safe_ref(arguments.get("ref") or "HEAD")
    return _run_git(root, ["reset", f"--{mode}", ref])


def _git_clean(root: Path, arguments: Mapping[str, Any]) -> dict[str, Any]:
    if bool(arguments.get("force", False)):
        return _run_git(root, ["clean", "-fd"])
    return _run_git(root, ["clean", "-nd"])


def _git_branch_delete(root: Path, arguments: Mapping[str, Any]) -> dict[str, Any]:
    flag = "-D" if bool(arguments.get("force", False)) else "-d"
    return _run_git(root, ["branch", flag, _safe_ref(arguments.get("name"), "name")])


_GIT_HANDLERS: dict[str, Callable[[Path, Mapping[str, Any]], dict[str, Any]]] = {
    "status": _git_status,
    "diff": _git_diff,
    "log": _git_log,
    "show": _git_show,
    "branch_list": _git_branch_list,
    "add": _git_add,
    "commit": _git_commit,
    "checkout": _git_checkout,
    "branch_create": _git_branch_create,
    "reset": _git_reset,
    "clean": _git_clean,
    "branch_delete": _git_branch_delete,
}


def _git_call(root: Path, operation: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
    handler = _GIT_HANDLERS.get(operation)
    if handler is None:
        raise InternalConnectorError(f"Unsupported Git operation '{operation}'")
    return handler(root, arguments)


def _database_path(root: Path, arguments: Mapping[str, Any]) -> Path:
    path = _workspace_path(root, _required_string(arguments, "database"))
    if not path.is_file() or path.suffix.lower() not in _DATABASE_SUFFIXES:
        raise InternalConnectorError("Database must be an existing SQLite file in the project")
    return path


def _database_uri(path: Path) -> str:
    return f"{path.resolve().as_uri()}?mode=ro"


def _sqlite_value(value: Any) -> Any:
    if isinstance(value, bytes):
        return {
            "type": "blob",
            "size": len(value),
            "base64": base64.b64encode(value[:4096]).decode("ascii"),
            "truncated": len(value) > 4096,
        }
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _query_parameters(value: Any) -> Sequence[Any] | Mapping[str, Any]:
    if value is None:
        return ()
    if isinstance(value, Mapping):
        return {
            str(key): _sqlite_value(item)
            for key, item in value.items()
            if isinstance(item, (str, int, float, bool)) or item is None
        }
    if isinstance(value, list):
        if not all(isinstance(item, (str, int, float, bool)) or item is None for item in value):
            raise InternalConnectorError("SQLite parameters must be scalar JSON values")
        return tuple(value)
    raise InternalConnectorError("SQLite parameters must be a list or object")


def sql_operation_class(sql: str) -> str:
    """Classify one SQLite statement as read, write or destructive."""

    cleaned = re.sub(r"/\*.*?\*/|--[^\n]*", " ", sql, flags=re.DOTALL).strip()
    match = re.match(r"([A-Za-z]+)", cleaned)
    verb = match.group(1).lower() if match else ""
    if verb in {"select", "with", "explain"}:
        return "read"
    if verb in {"insert", "update", "replace", "create"}:
        return "write"
    if verb in {"delete", "drop", "alter", "vacuum", "attach", "detach", "reindex"}:
        return "destructive"
    return "destructive"


def _single_statement(sql: str) -> str:
    normalized = sql.strip()
    if not normalized:
        raise InternalConnectorError("Argument 'sql' is required")
    without_trailing = normalized[:-1].rstrip() if normalized.endswith(";") else normalized
    if ";" in without_trailing:
        raise InternalConnectorError("Only one SQLite statement is allowed per call")
    return normalized


def _configure_query_deadline(connection: sqlite3.Connection, seconds: float = 5.0) -> None:
    deadline = time.monotonic() + seconds
    connection.set_progress_handler(lambda: int(time.monotonic() > deadline), 5_000)


def _rows_payload(cursor: sqlite3.Cursor, limit: int) -> dict[str, Any]:
    columns = [description[0] for description in cursor.description or ()]
    rows = cursor.fetchmany(limit + 1)
    truncated = len(rows) > limit
    safe_rows = [
        {column: _sqlite_value(row[index]) for index, column in enumerate(columns)}
        for row in rows[:limit]
    ]
    return {
        "columns": columns,
        "rows": safe_rows,
        "row_count": len(safe_rows),
        "truncated": truncated,
    }


def _sqlite_list_databases(root: Path, arguments: Mapping[str, Any]) -> dict[str, Any]:
    del arguments
    databases = []
    for candidate in root.rglob("*"):
        if (
            candidate.is_file()
            and candidate.suffix.lower() in _DATABASE_SUFFIXES
            and not any(part in _SKIP_DIRECTORIES for part in candidate.relative_to(root).parts)
            and not _is_protected(candidate.resolve(), root)
        ):
            databases.append(_file_payload(candidate, root))
            if len(databases) >= 200:
                break
    return {"databases": databases}


def _sqlite_read_operation(
    connection: sqlite3.Connection, operation: str, arguments: Mapping[str, Any]
) -> dict[str, Any]:
    """Ejecuta una operacion de solo lectura sobre una conexion ya abierta."""
    if operation == "list_tables":
        cursor = connection.execute(
            """
            SELECT name, type
            FROM sqlite_master
            WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%'
            ORDER BY type, name
            """
        )
        return _rows_payload(cursor, 500)
    if operation == "schema":
        cursor = connection.execute(
            """
            SELECT name, type, sql
            FROM sqlite_master
            WHERE type IN ('table', 'view', 'index', 'trigger')
              AND name NOT LIKE 'sqlite_%'
            ORDER BY type, name
            """
        )
        return _rows_payload(cursor, 500)
    if operation == "integrity_check":
        row = connection.execute("PRAGMA quick_check").fetchone()
        return {"result": row[0] if row else "unknown"}

    sql = _single_statement(_required_string(arguments, "sql"))
    if sql_operation_class(sql) != "read":
        raise InternalConnectorError("Use the approved execute operation for writes")
    cursor = connection.execute(sql, _query_parameters(arguments.get("parameters")))
    limit = _bounded_int(arguments.get("limit"), default=100, minimum=1, maximum=500)
    return _rows_payload(cursor, limit)


def _sqlite_read(root: Path, operation: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
    path = _database_path(root, arguments)
    try:
        connection = sqlite3.connect(_database_uri(path), uri=True, timeout=5)
    except sqlite3.Error as exc:
        raise InternalConnectorError("SQLite database could not be opened") from exc
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    connection.execute("PRAGMA foreign_keys=ON")
    _configure_query_deadline(connection)
    try:
        return _sqlite_read_operation(connection, operation, arguments)
    except sqlite3.Error as exc:
        raise InternalConnectorError("SQLite query failed") from exc
    finally:
        connection.close()


def _sqlite_execute(root: Path, arguments: Mapping[str, Any]) -> dict[str, Any]:
    path = _database_path(root, arguments)
    sql = _single_statement(_required_string(arguments, "sql"))
    if sql_operation_class(sql) == "read":
        raise InternalConnectorError("Use the query operation for read-only SQL")
    connection = None
    try:
        connection = sqlite3.connect(path, timeout=5)
        connection.execute("PRAGMA foreign_keys=ON")
        _configure_query_deadline(connection)
        with connection:
            cursor = connection.execute(sql, _query_parameters(arguments.get("parameters")))
        return {
            "row_count": max(cursor.rowcount, 0),
            "last_row_id": cursor.lastrowid,
        }
    except sqlite3.Error as exc:
        raise InternalConnectorError("SQLite write failed") from exc
    finally:
        if connection is not None:
            connection.close()


_SQLITE_READ_OPERATIONS = {"list_tables", "schema", "query", "integrity_check"}


def _sqlite_call(root: Path, operation: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
    if operation == "list_databases":
        return _sqlite_list_databases(root, arguments)
    if operation in _SQLITE_READ_OPERATIONS:
        return _sqlite_read(root, operation, arguments)
    if operation == "execute":
        return _sqlite_execute(root, arguments)
    raise InternalConnectorError(f"Unsupported SQLite operation '{operation}'")


_memory_module: Any = None
_memory_module_root: Path | None = None


def _load_memory_module(root: Path) -> Any:
    """Load the canonical semantic memory module for the active workspace."""

    global _memory_module, _memory_module_root
    memory_path = root / ".agent" / "mcp" / "memory-server.py"
    if not memory_path.is_file():
        raise InternalConnectorError(
            "Nexus memory backend is not available in the active workspace",
            status=ConnectorStatus.OFFLINE,
            retryable=False,
        )
    if _memory_module is not None and _memory_module_root == root:
        return _memory_module

    agent_dir = root / ".agent"
    if str(agent_dir) not in sys.path:
        sys.path.insert(0, str(agent_dir))
    module_name = f"openantigravity_memory_{abs(hash(root))}"
    spec = importlib.util.spec_from_file_location(module_name, memory_path)
    if spec is None or spec.loader is None:
        raise InternalConnectorError("Nexus memory backend could not be loaded")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise InternalConnectorError(
            f"Nexus memory backend failed to load: {type(exc).__name__}",
            status=ConnectorStatus.OFFLINE,
            retryable=True,
        ) from exc
    _memory_module = module
    _memory_module_root = root
    return module


def _memory_call(root: Path, operation: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
    """Expose the canonical memory and Brain Network APIs through the broker."""

    if operation in {"recall", "search", "stats", "suggest", "store", "delete", "clear_user"}:
        module = _load_memory_module(root)
        handlers = {
            "recall": "handle_memory_recall",
            "search": "handle_memory_search",
            "stats": "handle_memory_stats",
            "suggest": "handle_memory_suggest",
            "store": "handle_memory_store",
            "delete": "handle_memory_delete",
            "clear_user": "handle_memory_clear_user",
        }
        handler = getattr(module, handlers[operation], None)
        if not callable(handler):
            raise InternalConnectorError(f"Unsupported Nexus memory operation '{operation}'")
        result = handler(dict(arguments))
        if not isinstance(result, dict):
            raise InternalConnectorError("Nexus memory returned an invalid response")
        return result

    if operation in {"brain_query", "brain_stats", "brain_ingest"}:
        agent_dir = root / ".agent"
        if str(agent_dir) not in sys.path:
            sys.path.insert(0, str(agent_dir))
        try:
            from core.brain_network import BrainNetwork
        except Exception as exc:
            raise InternalConnectorError(
                "Nexus Brain Network is not available",
                status=ConnectorStatus.OFFLINE,
                retryable=False,
            ) from exc

        network = BrainNetwork(root)
        if operation == "brain_query":
            question = arguments.get("question")
            if not isinstance(question, str) or not question.strip():
                raise InternalConnectorError("Argument 'question' is required")
            limit = _bounded_int(arguments.get("limit"), default=10, minimum=1, maximum=50)
            app_filter = arguments.get("app_filter")
            if app_filter is not None and not isinstance(app_filter, str):
                raise InternalConnectorError("Argument 'app_filter' must be text")
            results = network.query_network(question.strip(), limit=limit, app_filter=app_filter)
            return {
                "success": True,
                "total": len(results),
                "results": [item.to_dict() for item in results],
            }
        if operation == "brain_stats":
            return {"success": True, **network.network_stats()}

        title = arguments.get("title")
        if not isinstance(title, str) or not title.strip():
            raise InternalConnectorError("Argument 'title' is required")
        tags = arguments.get("tags", [])
        if not isinstance(tags, list) or not all(isinstance(item, str) for item in tags):
            raise InternalConnectorError("Argument 'tags' must be a list of text values")
        node = network.mother.ingest(
            title=title.strip(),
            context=str(arguments.get("context") or ""),
            decisions=str(arguments.get("decisions") or ""),
            area=str(arguments.get("area") or "general"),
            tags=tags[:50],
            node_type=str(arguments.get("node_type") or "session"),
            importance=str(arguments.get("importance") or "normal"),
        )
        return {
            "success": True,
            "slug": node.slug,
            "title": node.title,
            "type": node.type,
            "tags": node.tags,
            "related": node.related,
        }

    raise InternalConnectorError(f"Unsupported Nexus memory operation '{operation}'")


def call_internal(
    project_root: Path,
    connector_id: str,
    operation: str,
    arguments: Mapping[str, Any],
) -> dict[str, Any]:
    """Run one sandboxed internal connector operation."""

    root = project_root.resolve()
    if connector_id == "filesystem":
        return _filesystem_call(root, operation, arguments)
    if connector_id == "git":
        return _git_call(root, operation, arguments)
    if connector_id == "sqlite":
        return _sqlite_call(root, operation, arguments)
    if connector_id == "nexus-memory":
        return _memory_call(root, operation, arguments)
    raise InternalConnectorError(f"Unknown internal connector '{connector_id}'")
