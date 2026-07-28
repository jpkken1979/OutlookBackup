"""Sandboxed in-process connectors for project files, Git and SQLite.

These adapters keep the default broker useful while avoiding one process per
connector.  Every filesystem path is resolved below the active project root and
known secret/configuration files are never exposed through the MCP surface.
"""

from __future__ import annotations

import base64
import json
import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
import time
from collections.abc import Mapping, Sequence
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


def _filesystem_call(root: Path, operation: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
    if operation == "read_file":
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

    if operation == "list_directory":
        raw_path = str(arguments.get("path") or ".")
        path = _workspace_path(root, raw_path)
        if not path.is_dir():
            raise InternalConnectorError("Requested path is not a directory")
        limit = _bounded_int(
            arguments.get("limit"),
            default=200,
            minimum=1,
            maximum=500,
        )
        entries = []
        for child in sorted(path.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())):
            if child.name in _SKIP_DIRECTORIES or _is_protected(child.resolve(), root):
                continue
            entries.append(_file_payload(child, root))
            if len(entries) >= limit:
                break
        return {"path": _relative(path, root), "entries": entries}

    if operation == "search_files":
        query = _required_string(arguments, "query")
        base = _workspace_path(root, str(arguments.get("path") or "."))
        if not base.is_dir():
            raise InternalConnectorError("Search path is not a directory")
        limit = _bounded_int(
            arguments.get("limit"),
            default=50,
            minimum=1,
            maximum=_MAX_RESULTS,
        )
        case_sensitive = bool(arguments.get("case_sensitive", False))
        needle = query if case_sensitive else query.casefold()
        results: list[dict[str, Any]] = []
        scanned = 0
        for candidate in base.rglob("*"):
            if scanned >= _MAX_SEARCH_FILES or len(results) >= limit:
                break
            if not candidate.is_file():
                continue
            relative_parts = candidate.relative_to(root).parts
            if any(part in _SKIP_DIRECTORIES for part in relative_parts):
                continue
            resolved = candidate.resolve()
            if _is_protected(resolved, root) or candidate.stat().st_size > _MAX_FILE_BYTES:
                continue
            scanned += 1
            try:
                lines = candidate.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for line_number, line in enumerate(lines, start=1):
                haystack = line if case_sensitive else line.casefold()
                if needle in haystack:
                    results.append(
                        {
                            "path": _relative(candidate, root),
                            "line": line_number,
                            "preview": line[:500],
                        }
                    )
                    if len(results) >= limit:
                        break
        return {"query": query, "scanned_files": scanned, "results": results}

    if operation == "get_file_info":
        path = _workspace_path(root, _required_string(arguments, "path"))
        return _file_payload(path, root)

    if operation == "write_file":
        path = _workspace_path(
            root,
            _required_string(arguments, "path"),
            allow_missing=True,
        )
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

    if operation == "create_directory":
        path = _workspace_path(
            root,
            _required_string(arguments, "path"),
            allow_missing=True,
        )
        path.mkdir(parents=bool(arguments.get("parents", True)), exist_ok=True)
        return _file_payload(path, root)

    if operation == "move_file":
        source = _workspace_path(root, _required_string(arguments, "source"))
        target = _workspace_path(
            root,
            _required_string(arguments, "target"),
            allow_missing=True,
        )
        if target.exists() and not bool(arguments.get("overwrite", False)):
            raise InternalConnectorError("Target already exists")
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(source, target)
        return {"source": _relative(source, root), "target": _relative(target, root)}

    if operation == "delete_file":
        path = _workspace_path(root, _required_string(arguments, "path"))
        if not path.is_file():
            raise InternalConnectorError("Only files can be deleted by this operation")
        path.unlink()
        return {"path": _relative(path, root), "deleted": True}

    if operation == "remove_directory":
        path = _workspace_path(root, _required_string(arguments, "path"))
        if path == root:
            raise InternalConnectorError("The project root cannot be removed")
        try:
            path.rmdir()
        except OSError as exc:
            raise InternalConnectorError("Directory must be empty before removal") from exc
        return {"path": _relative(path, root), "removed": True}

    raise InternalConnectorError(f"Unsupported filesystem operation '{operation}'")


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
        raise InternalConnectorError(
            f"Git operation failed with exit code {completed.returncode}"
        )
    return {
        "exit_code": completed.returncode,
        "stdout": output,
        "stderr": error,
    }


def _git_call(root: Path, operation: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
    if operation == "status":
        return _run_git(root, ["status", "--short", "--branch"])
    if operation == "diff":
        args = ["diff", "--no-ext-diff"]
        if bool(arguments.get("staged", False)):
            args.append("--cached")
        raw_path = arguments.get("path")
        if isinstance(raw_path, str) and raw_path.strip():
            args.extend(["--", _relative(_workspace_path(root, raw_path), root)])
        return _run_git(root, args)
    if operation == "log":
        limit = _bounded_int(arguments.get("limit"), default=20, minimum=1, maximum=100)
        return _run_git(
            root,
            [
                "log",
                f"-{limit}",
                "--date=iso-strict",
                "--pretty=format:%h%x09%ad%x09%s",
            ],
        )
    if operation == "show":
        ref = _safe_ref(arguments.get("ref") or "HEAD")
        return _run_git(root, ["show", "--stat", "--oneline", "--decorate", ref])
    if operation == "branch_list":
        return _run_git(root, ["branch", "--list", "--verbose", "--no-abbrev"])
    if operation == "add":
        return _run_git(root, ["add", "--", *_git_paths(root, arguments.get("paths"))])
    if operation == "commit":
        message = _required_string(arguments, "message")
        if len(message) > 500:
            raise InternalConnectorError("Commit message exceeds 500 characters")
        return _run_git(root, ["commit", "-m", message])
    if operation == "checkout":
        return _run_git(root, ["checkout", _safe_ref(arguments.get("ref"))])
    if operation == "branch_create":
        return _run_git(root, ["branch", _safe_ref(arguments.get("name"), "name")])
    if operation == "reset":
        mode = str(arguments.get("mode") or "mixed").lower()
        if mode not in {"soft", "mixed", "hard"}:
            raise InternalConnectorError("Reset mode must be soft, mixed or hard")
        ref = _safe_ref(arguments.get("ref") or "HEAD")
        return _run_git(root, ["reset", f"--{mode}", ref])
    if operation == "clean":
        if bool(arguments.get("force", False)):
            return _run_git(root, ["clean", "-fd"])
        return _run_git(root, ["clean", "-nd"])
    if operation == "branch_delete":
        flag = "-D" if bool(arguments.get("force", False)) else "-d"
        return _run_git(root, ["branch", flag, _safe_ref(arguments.get("name"), "name")])
    raise InternalConnectorError(f"Unsupported Git operation '{operation}'")


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


def _sqlite_call(root: Path, operation: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
    if operation == "list_databases":
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

    path = _database_path(root, arguments)
    if operation in {"list_tables", "schema", "query", "integrity_check"}:
        try:
            connection = sqlite3.connect(_database_uri(path), uri=True, timeout=5)
        except sqlite3.Error as exc:
            raise InternalConnectorError("SQLite database could not be opened") from exc
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        connection.execute("PRAGMA foreign_keys=ON")
        _configure_query_deadline(connection)
        try:
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
        except sqlite3.Error as exc:
            raise InternalConnectorError("SQLite query failed") from exc
        finally:
            connection.close()

    if operation == "execute":
        sql = _single_statement(_required_string(arguments, "sql"))
        if sql_operation_class(sql) == "read":
            raise InternalConnectorError("Use the query operation for read-only SQL")
        try:
            connection = sqlite3.connect(path, timeout=5)
            connection.execute("PRAGMA foreign_keys=ON")
            _configure_query_deadline(connection)
            with connection:
                cursor = connection.execute(
                    sql,
                    _query_parameters(arguments.get("parameters")),
                )
            return {
                "row_count": max(cursor.rowcount, 0),
                "last_row_id": cursor.lastrowid,
            }
        except sqlite3.Error as exc:
            raise InternalConnectorError("SQLite write failed") from exc
        finally:
            if "connection" in locals():
                connection.close()

    raise InternalConnectorError(f"Unsupported SQLite operation '{operation}'")


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
    raise InternalConnectorError(f"Unknown internal connector '{connector_id}'")
