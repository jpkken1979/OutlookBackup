#!/usr/bin/env python3
"""
Cliente async para la Obsidian Local REST API.

Requiere el plugin 'obsidian-local-rest-api' activo en Obsidian.
Token se lee de la variable de entorno OBSIDIAN_API_KEY o del archivo
~/.antigravity/obsidian_token.

Endpoints soportados:
  GET    /vault/{path}      — leer nota
  PUT    /vault/{path}      — crear/actualizar nota
  POST   /vault/{path}      — append a nota
  DELETE /vault/{path}      — eliminar nota
  GET    /vault/            — listar vault root
  POST   /search/simple/    — búsqueda por query string
  POST   /commands/         — ejecutar comando de Obsidian

Uso básico:
    from core.obsidian_client import ObsidianClient

    async with ObsidianClient() as client:
        if await client.health_check():
            note = await client.get_note("00-Inbox/mi-nota.md")
            await client.create_note("06-Decisiones/adr-001.md", content)
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from types import TracebackType

import aiohttp

logger = logging.getLogger("antigravity.obsidian_client")

# =============================================================================
# CONSTANTES
# =============================================================================
DEFAULT_PORT = 27124
DEFAULT_HOST = "127.0.0.1"
REQUEST_TIMEOUT = 10.0  # segundos
TOKEN_FILE = Path.home() / ".antigravity" / "obsidian_token"
ENV_TOKEN_KEY = "OBSIDIAN_API_KEY"

# Carpetas canónicas del vault Antigravity
VAULT_FOLDERS = {
    "inbox": "00-Inbox",
    "projects": "01-Proyectos",
    "areas": "02-Areas",
    "resources": "03-Recursos",
    "archive": "04-Archivo",
    "sessions": "05-Sesiones",
    "decisions": "06-Decisiones",
    "templates": "07-Templates",
}


# =============================================================================
# MODELOS DE DATOS
# =============================================================================


@dataclass
class NoteStat:
    """Metadatos de una nota de Obsidian.

    Args:
        ctime: Timestamp de creación (unix ms).
        mtime: Timestamp de modificación (unix ms).
        size: Tamaño en bytes.
    """

    ctime: int = 0
    mtime: int = 0
    size: int = 0


@dataclass
class ObsidianNote:
    """Representa una nota de Obsidian con su contenido y metadatos.

    Args:
        path: Ruta relativa dentro del vault (ej: "00-Inbox/nota.md").
        content: Contenido markdown de la nota.
        stat: Metadatos de archivo (ctime, mtime, size).
        tags: Lista de tags extraídos del frontmatter.
        frontmatter: Diccionario con los campos del frontmatter YAML.
    """

    path: str
    content: str
    stat: NoteStat = field(default_factory=NoteStat)
    tags: list[str] = field(default_factory=list)
    frontmatter: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# HELPERS
# =============================================================================


def _load_token() -> str | None:
    """Lee el API token desde env var o archivo de configuración.

    Returns:
        Token como string, o None si no se encuentra.
    """
    # 1. Variable de entorno (prioridad máxima)
    token = os.environ.get(ENV_TOKEN_KEY)
    if token:
        logger.debug("Token cargado desde variable de entorno %s", ENV_TOKEN_KEY)
        return token.strip()

    # 2. Archivo ~/.antigravity/obsidian_token
    if TOKEN_FILE.exists():
        token = TOKEN_FILE.read_text(encoding="utf-8").strip()
        if token:
            logger.debug("Token cargado desde archivo %s", TOKEN_FILE)
            return token

    logger.warning(
        "No se encontró token de Obsidian. Definí %s o creá el archivo %s",
        ENV_TOKEN_KEY,
        TOKEN_FILE,
    )
    return None


def _build_headers(token: str | None) -> dict[str, str]:
    """Construye los headers HTTP para las requests.

    Args:
        token: API token de Obsidian Local REST API.

    Returns:
        Diccionario de headers.
    """
    headers: dict[str, str] = {"Content-Type": "text/markdown", "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _build_adr_content(
    title: str,
    context: str,
    decision: str,
    consequences: list[str],
    date: str,
) -> str:
    """Genera el contenido markdown de un ADR.

    Args:
        title: Título de la decisión.
        context: Contexto que motivó la decisión.
        decision: La decisión tomada.
        consequences: Lista de consecuencias (positivas y negativas).
        date: Fecha en formato YYYY-MM-DD.

    Returns:
        Contenido markdown del ADR con frontmatter.
    """
    consequences_md = "\n".join(f"- {c}" for c in consequences)
    return f"""---
title: "{title}"
date: {date}
status: accepted
tags:
  - adr
  - decision
---

# {title}

## Contexto

{context}

## Decisión

{decision}

## Consecuencias

{consequences_md}
"""


def _build_session_content(
    summary: str,
    files_changed: list[str],
    decisions: list[str],
    date: str,
    timestamp: str,
) -> str:
    """Genera el contenido markdown de una nota de sesión.

    Args:
        summary: Resumen de la sesión.
        files_changed: Lista de archivos modificados.
        decisions: Lista de decisiones tomadas.
        date: Fecha en formato YYYY-MM-DD.
        timestamp: Timestamp ISO para el frontmatter.

    Returns:
        Contenido markdown de la sesión.
    """
    files_md = "\n".join(f"- `{f}`" for f in files_changed) if files_changed else "- (ninguno)"
    decisions_md = "\n".join(f"- {d}" for d in decisions) if decisions else "- (ninguna)"
    return f"""---
title: "Sesión {date}"
date: {timestamp}
tags:
  - session
  - antigravity
---

# Sesión de trabajo — {date}

## Resumen

{summary}

## Archivos modificados

{files_md}

## Decisiones tomadas

{decisions_md}
"""


# =============================================================================
# CLIENTE PRINCIPAL
# =============================================================================


class ObsidianClient:
    """Cliente async para Obsidian Local REST API.

    Gestiona la conexión HTTP al plugin obsidian-local-rest-api y expone
    operaciones de lectura, escritura, búsqueda y creación de notas.

    Args:
        host: Host del servidor (default: 127.0.0.1).
        port: Puerto del servidor (default: 27124).
        token: API token. Si es None, se lee desde env/archivo.

    Example:
        async with ObsidianClient() as client:
            nota = await client.get_note("00-Inbox/ideas.md")
            print(nota.content)
    """

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        token: str | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._token = token or _load_token()
        self._base_url = f"http://{host}:{port}"
        self._session: aiohttp.ClientSession | None = None
        logger.info("ObsidianClient inicializado en %s", self._base_url)

    # ------------------------------------------------------------------
    # Context manager async
    # ------------------------------------------------------------------

    async def __aenter__(self) -> ObsidianClient:
        """Abre la sesión HTTP al entrar al context manager."""
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        self._session = aiohttp.ClientSession(
            headers=_build_headers(self._token),
            timeout=timeout,
        )
        logger.debug("Sesión HTTP abierta")
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Cierra la sesión HTTP al salir del context manager."""
        if self._session and not self._session.closed:
            await self._session.close()
            logger.debug("Sesión HTTP cerrada")

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------

    def _ensure_session(self) -> aiohttp.ClientSession:
        """Verifica que la sesión esté abierta.

        Returns:
            La sesión aiohttp activa.

        Raises:
            RuntimeError: Si se usa el cliente fuera del context manager.
        """
        if self._session is None or self._session.closed:
            raise RuntimeError(
                "ObsidianClient debe usarse como context manager: "
                "async with ObsidianClient() as client: ..."
            )
        return self._session

    def _url(self, path: str) -> str:
        """Construye la URL completa para un endpoint.

        Args:
            path: Ruta del endpoint (ej: "/vault/nota.md").

        Returns:
            URL completa.
        """
        return f"{self._base_url}{path}"

    # ------------------------------------------------------------------
    # Operaciones de vault
    # ------------------------------------------------------------------

    async def get_note(self, path: str) -> ObsidianNote:
        """Lee una nota del vault por su ruta relativa.

        Args:
            path: Ruta relativa dentro del vault (ej: "00-Inbox/nota.md").

        Returns:
            ObsidianNote con contenido y metadatos.

        Raises:
            aiohttp.ClientResponseError: Si la nota no existe (404) u otro error HTTP.
        """
        session = self._ensure_session()
        url = self._url(f"/vault/{path}")
        logger.info("Leyendo nota: %s", path)

        async with session.get(url, headers={"Accept": "application/vnd.olrapi.note+json"}) as resp:
            resp.raise_for_status()
            data: dict[str, Any] = await resp.json()

        stat_raw = data.get("stat", {})
        stat = NoteStat(
            ctime=stat_raw.get("ctime", 0),
            mtime=stat_raw.get("mtime", 0),
            size=stat_raw.get("size", 0),
        )

        return ObsidianNote(
            path=path,
            content=data.get("content", ""),
            stat=stat,
            tags=data.get("tags", []),
            frontmatter=data.get("frontmatter", {}),
        )

    async def create_note(
        self,
        path: str,
        content: str,
        overwrite: bool = False,
    ) -> bool:
        """Crea o actualiza una nota en el vault.

        Args:
            path: Ruta relativa de la nota (ej: "00-Inbox/nueva.md").
            content: Contenido markdown de la nota.
            overwrite: Si es True, sobreescribe la nota si existe.

        Returns:
            True si la operación fue exitosa.
        """
        session = self._ensure_session()
        url = self._url(f"/vault/{path}")
        headers: dict[str, str] = {"Content-Type": "text/markdown"}

        if not overwrite:
            headers["If-None-Match"] = "*"  # falla si ya existe

        logger.info("Creando nota: %s (overwrite=%s)", path, overwrite)

        async with session.put(url, data=content.encode("utf-8"), headers=headers) as resp:
            if resp.status in (200, 204):
                logger.info("Nota creada/actualizada: %s", path)
                return True
            if resp.status == 412 and not overwrite:
                logger.warning("Nota ya existe y overwrite=False: %s", path)
                return False
            resp.raise_for_status()
            return False

    async def append_to_note(self, path: str, content: str) -> bool:
        """Agrega contenido al final de una nota existente.

        Args:
            path: Ruta relativa de la nota.
            content: Texto a agregar (se agrega con separador \\n\\n).

        Returns:
            True si la operación fue exitosa.
        """
        session = self._ensure_session()
        url = self._url(f"/vault/{path}")
        logger.info("Appending a nota: %s", path)

        async with session.post(
            url, data=content.encode("utf-8"), headers={"Content-Type": "text/markdown"}
        ) as resp:
            if resp.status in (200, 204):
                logger.info("Contenido agregado a: %s", path)
                return True
            resp.raise_for_status()
            return False

    async def delete_note(self, path: str) -> bool:
        """Elimina una nota del vault.

        Args:
            path: Ruta relativa de la nota a eliminar.

        Returns:
            True si la nota fue eliminada, False si no existía.
        """
        session = self._ensure_session()
        url = self._url(f"/vault/{path}")
        logger.info("Eliminando nota: %s", path)

        async with session.delete(url) as resp:
            if resp.status in (200, 204):
                logger.info("Nota eliminada: %s", path)
                return True
            if resp.status == 404:
                logger.warning("Nota no encontrada para eliminar: %s", path)
                return False
            resp.raise_for_status()
            return False

    async def list_notes(self, folder: str = "") -> list[str]:
        """Lista las notas en una carpeta del vault.

        Args:
            folder: Carpeta relativa a listar. String vacío lista la raíz.

        Returns:
            Lista de rutas relativas de notas/archivos encontrados.
        """
        session = self._ensure_session()
        path = f"/vault/{folder}/" if folder else "/vault/"
        url = self._url(path)
        logger.info("Listando vault: %s", path)

        async with session.get(url) as resp:
            resp.raise_for_status()
            data: dict[str, Any] = await resp.json()

        files: list[str] = data.get("files", [])
        logger.debug("Encontrados %d archivos en %s", len(files), path)
        return files

    # ------------------------------------------------------------------
    # Búsqueda
    # ------------------------------------------------------------------

    async def search(self, query: str, limit: int = 10) -> list[ObsidianNote]:
        """Busca notas en el vault por contenido o título.

        Args:
            query: String de búsqueda.
            limit: Número máximo de resultados (default: 10).

        Returns:
            Lista de ObsidianNote con los resultados.
        """
        session = self._ensure_session()
        url = self._url("/search/simple/")
        params = {"query": query}
        logger.info("Buscando en vault: '%s' (limit=%d)", query, limit)

        async with session.post(url, params=params) as resp:
            resp.raise_for_status()
            results: list[dict[str, Any]] = await resp.json()

        notes: list[ObsidianNote] = []
        for item in results[:limit]:
            note_path = item.get("filename", "")
            if note_path:
                notes.append(
                    ObsidianNote(
                        path=note_path,
                        content=item.get("content", ""),
                        tags=item.get("tags", []),
                        frontmatter=item.get("frontmatter", {}),
                    )
                )

        logger.info("Búsqueda devolvió %d resultados para '%s'", len(notes), query)
        return notes

    # ------------------------------------------------------------------
    # Operaciones de alto nivel
    # ------------------------------------------------------------------

    async def create_adr(
        self,
        title: str,
        context: str,
        decision: str,
        consequences: list[str],
    ) -> str:
        """Crea un ADR (Architecture Decision Record) completo en el vault.

        El ADR se guarda en la carpeta 06-Decisiones con formato
        adr-YYYYMMDD-{slug}.md.

        Args:
            title: Título descriptivo de la decisión.
            context: Contexto técnico que motivó la decisión.
            decision: La decisión tomada y el razonamiento.
            consequences: Lista de consecuencias esperadas.

        Returns:
            Ruta relativa de la nota creada en el vault.
        """
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        date_compact = now.strftime("%Y%m%d")

        # Slug: minúsculas, espacios → guiones, solo alfanumérico
        slug = title.lower()
        slug = "".join(c if c.isalnum() or c == " " else "" for c in slug)
        slug = "-".join(slug.split())[:50]

        path = f"{VAULT_FOLDERS['decisions']}/adr-{date_compact}-{slug}.md"
        content = _build_adr_content(title, context, decision, consequences, date_str)

        logger.info("Creando ADR: %s", path)
        await self.create_note(path, content, overwrite=False)
        return path

    async def create_session_note(
        self,
        summary: str,
        files_changed: list[str],
        decisions: list[str],
    ) -> str:
        """Crea una nota de sesión de trabajo en el vault.

        La nota se guarda en 05-Sesiones con formato
        session-YYYY-MM-DD-HH-MM.md.

        Args:
            summary: Resumen ejecutivo de lo que se hizo en la sesión.
            files_changed: Lista de archivos creados o modificados.
            decisions: Lista de decisiones técnicas tomadas.

        Returns:
            Ruta relativa de la nota creada en el vault.
        """
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        timestamp = now.isoformat(timespec="seconds")
        file_ts = now.strftime("%Y-%m-%d-%H-%M")

        path = f"{VAULT_FOLDERS['sessions']}/session-{file_ts}.md"
        content = _build_session_content(summary, files_changed, decisions, date_str, timestamp)

        logger.info("Creando nota de sesión: %s", path)
        await self.create_note(path, content, overwrite=False)
        return path

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    async def health_check(self) -> bool:
        """Verifica que el plugin Obsidian Local REST API está activo.

        Returns:
            True si el plugin responde correctamente, False en caso contrario.
        """
        session = self._ensure_session()
        url = self._url("/")
        logger.debug("Verificando health de Obsidian API en %s", url)

        try:
            async with session.get(url) as resp:
                is_ok = resp.status == 200
                if is_ok:
                    logger.info("Obsidian API activa en %s", self._base_url)
                else:
                    logger.warning("Obsidian API respondió con status %d", resp.status)
                return is_ok
        except aiohttp.ClientConnectorError:
            logger.error(
                "No se pudo conectar a Obsidian API en %s. "
                "¿Está Obsidian abierto con el plugin activo?",
                self._base_url,
            )
            return False
        except Exception as exc:  # noqa: BLE001
            logger.error("Error inesperado en health_check: %s", exc)
            return False
