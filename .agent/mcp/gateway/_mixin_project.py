"""Mixin: handlers de contexto de proyecto externo.

Permite al ChatPanel leer el árbol de archivos y contenido de cualquier
directorio de la PC del usuario, con validación estricta de paths para
prevenir path traversal.

Endpoints:
  GET  /v1/project/tree   — árbol de directorios (depth configurable)
  GET  /v1/project/read   — leer contenido de un archivo
  POST /v1/project/write  — escribir un archivo
  GET  /v1/project/search — buscar texto en archivos del proyecto
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from aiohttp import web

log = logging.getLogger("antigravity-gateway")

# Extensiones de texto que vale la pena leer
_TEXT_EXTENSIONS = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".rs",
    ".go",
    ".java",
    ".c",
    ".cpp",
    ".h",
    ".cs",
    ".rb",
    ".php",
    ".swift",
    ".kt",
    ".md",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".env",
    ".sh",
    ".bat",
    ".ps1",
    ".sql",
    ".graphql",
    ".proto",
    ".html",
    ".css",
    ".scss",
    ".vue",
    ".svelte",
}

# Directorios a ignorar siempre
_IGNORE_DIRS = {
    "node_modules",
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    ".next",
    ".nuxt",
    "out",
    "target",
    ".cargo",
    "vendor",
    ".gradle",
    ".idea",
    ".vscode",
    "coverage",
    ".nyc_output",
    ".cache",
}

# Tamaño máximo para leer un archivo (2 MB)
_MAX_FILE_SIZE = 2 * 1024 * 1024


def _validate_project_path(raw_path: str) -> Path | None:
    """Valida y normaliza un path. Rechaza paths relativos con .. y paths vacíos."""
    if not raw_path or not raw_path.strip():
        return None
    try:
        p = Path(raw_path.strip()).resolve()
        # Asegurar que sea un directorio o archivo real
        return p
    except (ValueError, OSError):
        return None


def _is_within_root(target: Path, root: Path) -> bool:
    """Verifica que target esté dentro de root (previene path traversal)."""
    try:
        target.relative_to(root)
        return True
    except ValueError:
        return False


# Archivos sensibles que NUNCA se exponen ni se escriben, sin importar el root.
# Defensa en profundidad contra exfiltración de credenciales / tampering de config.
_SENSITIVE_FILE_NAMES = {
    "session.key",
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    ".netrc",
    ".git-credentials",
    ".npmrc",
    ".pypirc",
    "credentials",
    "credentials.json",
}

# Directorios de credenciales que NUNCA se atraviesan (en cualquier nivel del path).
_SENSITIVE_DIR_PARTS = {
    ".ssh",
    ".aws",
    ".gnupg",
    ".codex",
}


def _get_allowed_roots() -> list[Path]:
    """Roots permitidos para acceso a archivos del proyecto.

    Configurable vía la env var ``ANTIGRAVITY_PROJECT_ROOTS`` (separada por
    ``os.pathsep``). Si no está seteada devuelve lista vacía: en ese caso no se
    aplica confinamiento por allowlist, pero el denylist de archivos/directorios
    sensibles SIEMPRE se evalúa.

    Returns:
        Lista de roots permitidos ya resueltos a path absoluto.
    """
    raw = os.environ.get("ANTIGRAVITY_PROJECT_ROOTS", "").strip()
    roots: list[Path] = []
    for part in raw.split(os.pathsep):
        candidate = part.strip()
        if not candidate:
            continue
        try:
            roots.append(Path(candidate).expanduser().resolve())
        except (ValueError, OSError):
            continue
    return roots


def _check_path_allowed(target: Path) -> str | None:
    """Valida un path contra el denylist de sensibles y el allowlist de roots.

    Esta validación es server-side y no depende del ``root`` provisto por el
    cliente (que solo puede acotar más, nunca ampliar).

    Args:
        target: Path ya resuelto a absoluto a validar.

    Returns:
        ``None`` si el acceso está permitido, o un string con el motivo del
        rechazo si está denegado.
    """
    name_lower = target.name.lower()
    # `.env.example` es plantilla pública (versionada), no es sensible.
    if name_lower != ".env.example" and (
        name_lower in _SENSITIVE_FILE_NAMES or name_lower.startswith(".env")
    ):
        return "Acceso denegado: archivo sensible"
    parts_lower = {p.lower() for p in target.parts}
    if parts_lower & _SENSITIVE_DIR_PARTS:
        return "Acceso denegado: directorio sensible"
    allowed_roots = _get_allowed_roots()
    if allowed_roots and not any(_is_within_root(target, root) for root in allowed_roots):
        return "Acceso denegado: fuera de los roots permitidos (ANTIGRAVITY_PROJECT_ROOTS)"
    return None


class _ProjectMixin:
    """Handlers de contexto de proyecto externo."""

    async def handle_project_tree(self, request: web.Request) -> web.Response:
        """GET /v1/project/tree?path=<dir>&depth=<n> — Árbol del proyecto."""
        from .._gateway_main import _make_response

        raw_path = request.query.get("path", "").strip()
        if not raw_path:
            return web.json_response(
                _make_response(error="Parámetro 'path' requerido", status=400), status=400
            )

        root = _validate_project_path(raw_path)
        if root is None or not root.exists():
            return web.json_response(
                _make_response(error=f"Directorio no encontrado: {raw_path}", status=404),
                status=404,
            )
        if not root.is_dir():
            return web.json_response(
                _make_response(error="El path debe ser un directorio", status=400), status=400
            )

        # Confinamiento server-side: denylist de sensibles + allowlist de roots.
        denied = _check_path_allowed(root)
        if denied:
            return web.json_response(_make_response(error=denied, status=403), status=403)

        depth = min(max(1, int(request.query.get("depth", "3"))), 6)

        loop = asyncio.get_running_loop()
        tree = await loop.run_in_executor(
            self._thread_pool,
            lambda: _build_tree(root, root, depth, 0),
        )

        # Estadísticas básicas
        all_files = _flatten_files(tree)
        stats = {
            "total_files": len(all_files),
            "total_dirs": _count_dirs(tree),
            "extensions": _count_extensions(all_files),
        }

        return web.json_response(
            _make_response(
                data={
                    "root": str(root),
                    "depth": depth,
                    "tree": tree,
                    "stats": stats,
                }
            )
        )

    async def handle_project_read(self, request: web.Request) -> web.Response:
        """GET /v1/project/read?path=<file>&root=<dir> — Leer un archivo."""
        from .._gateway_main import _make_response, _sanitize_error

        raw_path = request.query.get("path", "").strip()
        raw_root = request.query.get("root", "").strip()

        if not raw_path:
            return web.json_response(
                _make_response(error="Parámetro 'path' requerido", status=400), status=400
            )

        file_path = _validate_project_path(raw_path)
        if file_path is None:
            return web.json_response(_make_response(error="Path inválido", status=400), status=400)

        # Confinamiento server-side: denylist de sensibles + allowlist de roots.
        denied = _check_path_allowed(file_path)
        if denied:
            return web.json_response(_make_response(error=denied, status=403), status=403)

        # Si se especificó root, verificar que el archivo está dentro
        if raw_root:
            root = _validate_project_path(raw_root)
            if root and not _is_within_root(file_path, root):
                return web.json_response(
                    _make_response(
                        error="Acceso denegado: el archivo está fuera del proyecto activo",
                        status=403,
                    ),
                    status=403,
                )

        if not file_path.exists() or not file_path.is_file():
            return web.json_response(
                _make_response(error=f"Archivo no encontrado: {raw_path}", status=404),
                status=404,
            )

        size = file_path.stat().st_size
        if size > _MAX_FILE_SIZE:
            return web.json_response(
                _make_response(
                    error=f"Archivo demasiado grande ({size // 1024}KB, máx 2MB)", status=413
                ),
                status=413,
            )

        loop = asyncio.get_running_loop()
        try:
            content = await loop.run_in_executor(
                self._thread_pool,
                lambda: file_path.read_text(encoding="utf-8", errors="replace"),
            )
        except Exception as exc:
            return web.json_response(
                _make_response(error=_sanitize_error(exc), status=500), status=500
            )

        return web.json_response(
            _make_response(
                data={
                    "path": str(file_path),
                    "name": file_path.name,
                    "extension": file_path.suffix,
                    "size_bytes": size,
                    "content": content,
                    "lines": content.count("\n") + 1,
                }
            )
        )

    async def handle_project_write(self, request: web.Request) -> web.Response:
        """POST /v1/project/write — Escribir un archivo del proyecto."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            body = await request.json()
        except Exception:
            return web.json_response(
                _make_response(error="JSON body requerido", status=400), status=400
            )

        raw_path = str(body.get("path", "")).strip()
        raw_root = str(body.get("root", "")).strip()
        content = body.get("content")

        if not raw_path:
            return web.json_response(
                _make_response(error="Campo 'path' requerido", status=400), status=400
            )
        if content is None or not isinstance(content, str):
            return web.json_response(
                _make_response(error="Campo 'content' requerido (string)", status=400), status=400
            )

        file_path = _validate_project_path(raw_path)
        if file_path is None:
            return web.json_response(_make_response(error="Path inválido", status=400), status=400)

        # Confinamiento server-side: denylist de sensibles + allowlist de roots.
        denied = _check_path_allowed(file_path)
        if denied:
            return web.json_response(_make_response(error=denied, status=403), status=403)

        # Verificar que el archivo está dentro del root del proyecto
        if raw_root:
            root = _validate_project_path(raw_root)
            if root and not _is_within_root(file_path, root):
                return web.json_response(
                    _make_response(
                        error="Acceso denegado: el archivo está fuera del proyecto activo",
                        status=403,
                    ),
                    status=403,
                )

        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(
                self._thread_pool,
                lambda: _write_file_safe(file_path, content),
            )
        except Exception as exc:
            return web.json_response(
                _make_response(error=_sanitize_error(exc), status=500), status=500
            )

        return web.json_response(
            _make_response(
                data={
                    "path": str(file_path),
                    "size_bytes": len(content.encode("utf-8")),
                    "message": f"Archivo escrito: {file_path.name}",
                }
            )
        )

    async def handle_project_search(self, request: web.Request) -> web.Response:
        """GET /v1/project/search?path=<dir>&q=<query>&ext=<.ts,.tsx> — Búsqueda en archivos."""
        from .._gateway_main import _make_response

        raw_path = request.query.get("path", "").strip()
        query = request.query.get("q", "").strip()
        ext_filter = request.query.get("ext", "").strip()
        limit = min(50, max(1, int(request.query.get("limit", "20"))))

        if not raw_path:
            return web.json_response(
                _make_response(error="Parámetro 'path' requerido", status=400), status=400
            )
        if not query:
            return web.json_response(
                _make_response(error="Parámetro 'q' requerido", status=400), status=400
            )

        root = _validate_project_path(raw_path)
        if root is None or not root.is_dir():
            return web.json_response(
                _make_response(error=f"Directorio no encontrado: {raw_path}", status=404),
                status=404,
            )

        # Confinamiento server-side: denylist de sensibles + allowlist de roots.
        denied = _check_path_allowed(root)
        if denied:
            return web.json_response(_make_response(error=denied, status=403), status=403)

        extensions = {e.strip() for e in ext_filter.split(",") if e.strip()} or _TEXT_EXTENSIONS

        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(
            self._thread_pool,
            lambda: _search_in_files(root, query, extensions, limit),
        )

        return web.json_response(
            _make_response(
                data={
                    "query": query,
                    "root": str(root),
                    "total": len(results),
                    "results": results,
                }
            )
        )


# ── Helpers síncronos (corren en thread pool) ──────────────────────────────


def _build_tree(
    path: Path,
    root: Path,
    max_depth: int,
    current_depth: int,
) -> dict:
    """Construye recursivamente el árbol de archivos."""
    node: dict = {
        "name": path.name or str(path),
        "path": str(path),
        "type": "directory" if path.is_dir() else "file",
    }

    if path.is_dir() and current_depth < max_depth:
        children = []
        try:
            entries = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
            for entry in entries:
                if entry.name.startswith(".") and entry.name not in {".env", ".env.example"}:
                    continue
                if entry.is_dir() and entry.name in _IGNORE_DIRS:
                    continue
                children.append(_build_tree(entry, root, max_depth, current_depth + 1))
        except PermissionError:
            pass
        node["children"] = children
    elif path.is_file():
        node["extension"] = path.suffix
        node["size_bytes"] = _safe_stat(path)

    return node


def _safe_stat(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _flatten_files(node: dict) -> list[dict]:
    if node["type"] == "file":
        return [node]
    result = []
    for child in node.get("children", []):
        result.extend(_flatten_files(child))
    return result


def _count_dirs(node: dict) -> int:
    if node["type"] == "file":
        return 0
    count = 1
    for child in node.get("children", []):
        count += _count_dirs(child)
    return count


def _count_extensions(files: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for f in files:
        ext = f.get("extension", "")
        if ext:
            counts[ext] = counts.get(ext, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: x[1], reverse=True)[:15])


def _write_file_safe(path: Path, content: str) -> None:
    """Escribe contenido en un archivo creando directorios intermedios si es necesario."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _match_lines_in_file(file_path: Path, query_lower: str, max_matches: int = 5) -> list[dict]:
    """Devuelve hasta `max_matches` líneas de un archivo que contienen la query.

    Args:
        file_path: Ruta del archivo a leer.
        query_lower: Query ya en minúsculas.
        max_matches: Máximo de coincidencias a devolver por archivo.

    Returns:
        Lista de dicts {"line", "text"} (puede estar vacía).
    """
    content = file_path.read_text(encoding="utf-8", errors="replace")
    matches: list[dict] = []
    for i, line in enumerate(content.splitlines()):
        if query_lower in line.lower():
            matches.append({"line": i + 1, "text": line.strip()[:200]})
            if len(matches) >= max_matches:
                break
    return matches


def _search_in_files(
    root: Path,
    query: str,
    extensions: set[str],
    limit: int,
) -> list[dict]:
    """Búsqueda de texto en archivos del proyecto (case-insensitive)."""
    results = []
    query_lower = query.lower()

    for dirpath, dirnames, filenames in os.walk(root):
        # Ignorar directorios excluidos
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in _IGNORE_DIRS]

        for filename in filenames:
            if len(results) >= limit:
                return results
            file_path = Path(dirpath) / filename
            if file_path.suffix not in extensions:
                continue
            if _safe_stat(file_path) > _MAX_FILE_SIZE:
                continue

            try:
                matches = _match_lines_in_file(file_path, query_lower)
            except (OSError, UnicodeDecodeError):
                continue
            if matches:
                results.append(
                    {
                        "file": str(file_path),
                        "relative": str(file_path.relative_to(root)),
                        "matches": matches,
                    }
                )

    return results
