"""Unified Knowledge Bridge — integra mem0, Obsidian y ProjectMemory.

Provee una interfaz unica para buscar, almacenar y sincronizar conocimiento
across las tres fuentes del ecosistema Antigravity. Diseñado para que Nexus
y el gateway puedan acceder a TODO el conocimiento del proyecto de forma
transparente.

Fuentes integradas:
- mem0 (ChromaDB): memoria semantica, embeddings, busqueda vectorial
- Obsidian: vault markdown, decisiones, sesiones, knowledge base
- ProjectMemory: hotspots, decisiones, errores, test trends, CI, sesiones
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class KnowledgeSource(str, Enum):
    """Fuente de origen del conocimiento."""

    MEM0 = "mem0"
    OBSIDIAN = "obsidian"
    PROJECT = "project_memory"


class KnowledgeCategory(str, Enum):
    """Categoría semántica del conocimiento."""

    DECISION = "decision"
    ERROR = "error"
    PATTERN = "pattern"
    SESSION = "session"
    HOTSPOT = "hotspot"
    NOTE = "note"
    CI = "ci"
    TEST = "test"
    GENERAL = "general"


@dataclass
class KnowledgeEntry:
    """Entrada unificada de conocimiento de cualquier fuente."""

    id: str
    content: str
    source: KnowledgeSource
    category: KnowledgeCategory
    relevance_score: float = 0.0
    timestamp: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serializa a dict para JSON."""
        return {
            "id": self.id,
            "content": self.content,
            "source": self.source.value,
            "category": self.category.value,
            "relevance_score": self.relevance_score,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class ProjectKnowledge:
    """Contexto completo de conocimiento de un proyecto."""

    project_path: str
    decisions: list[KnowledgeEntry] = field(default_factory=list)
    errors: list[KnowledgeEntry] = field(default_factory=list)
    patterns: list[KnowledgeEntry] = field(default_factory=list)
    sessions: list[KnowledgeEntry] = field(default_factory=list)
    hotspots: list[KnowledgeEntry] = field(default_factory=list)
    ci_health: dict[str, Any] = field(default_factory=dict)
    test_trends: list[dict[str, Any]] = field(default_factory=list)
    obsidian_notes: list[KnowledgeEntry] = field(default_factory=list)
    mem0_memories: list[KnowledgeEntry] = field(default_factory=list)

    @property
    def total_entries(self) -> int:
        """Total de entradas de conocimiento."""
        return (
            len(self.decisions)
            + len(self.errors)
            + len(self.patterns)
            + len(self.sessions)
            + len(self.hotspots)
            + len(self.obsidian_notes)
            + len(self.mem0_memories)
        )

    def to_dict(self) -> dict[str, Any]:
        """Serializa a dict."""
        return {
            "project_path": self.project_path,
            "total_entries": self.total_entries,
            "decisions": [e.to_dict() for e in self.decisions],
            "errors": [e.to_dict() for e in self.errors],
            "patterns": [e.to_dict() for e in self.patterns],
            "sessions": [e.to_dict() for e in self.sessions],
            "hotspots": [e.to_dict() for e in self.hotspots],
            "ci_health": self.ci_health,
            "test_trends": self.test_trends,
            "obsidian_notes": [e.to_dict() for e in self.obsidian_notes],
            "mem0_memories": [e.to_dict() for e in self.mem0_memories],
        }


@dataclass
class SyncResult:
    """Resultado de sincronización."""

    synced_to_obsidian: int = 0
    synced_from_obsidian: int = 0
    synced_to_mem0: int = 0
    errors: list[str] = field(default_factory=list)
    duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serializa a dict."""
        return {
            "synced_to_obsidian": self.synced_to_obsidian,
            "synced_from_obsidian": self.synced_from_obsidian,
            "synced_to_mem0": self.synced_to_mem0,
            "errors": self.errors,
            "duration_ms": self.duration_ms,
        }


# ---------------------------------------------------------------------------
# Adapters — cada fuente tiene su propio adapter
# ---------------------------------------------------------------------------


class Mem0Adapter:
    """Adapter para consultar mem0 via gateway HTTP."""

    def __init__(
        self, gateway_url: str = "http://127.0.0.1:4747", api_key: str | None = None
    ) -> None:
        self.gateway_url = gateway_url.rstrip("/")
        self._available: bool | None = None
        # api_key explícita > variable de entorno > session key del disco
        self._api_key: str | None = (
            api_key or os.getenv("ANTIGRAVITY_API_KEY") or self._load_session_key()
        )

    @staticmethod
    def _load_session_key() -> str | None:
        """Intenta leer la session key cifrada del disco (sin crash si falla)."""
        try:
            from mcp.session_key import read_session_key  # type: ignore[import]

            return read_session_key()
        except Exception:
            pass
        try:
            # Fallback: importar desde path relativo cuando se ejecuta fuera del gateway
            import sys

            agent_mcp = Path(__file__).resolve().parents[1] / "mcp"
            if str(agent_mcp.parent) not in sys.path:
                sys.path.insert(0, str(agent_mcp.parent))
            from mcp.session_key import read_session_key as _rsk  # type: ignore[import]

            return _rsk()
        except Exception:
            return None

    def _auth_headers(self) -> dict[str, str]:
        """Devuelve headers de autenticación para el gateway."""
        if self._api_key:
            return {"X-API-Key": self._api_key}
        return {}

    async def is_available(self) -> bool:
        """Verifica si mem0 está accesible via gateway."""
        try:
            import aiohttp

            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                async with session.get(f"{self.gateway_url}/v1/health") as resp:
                    self._available = resp.status == 200
                    return self._available
        except Exception:
            self._available = False
            return False

    async def search(self, query: str, limit: int = 10) -> list[KnowledgeEntry]:
        """Búsqueda semántica en mem0."""
        if self._available is False:
            return []
        try:
            import aiohttp

            params = {"query": query, "limit": str(limit)}
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.get(
                    f"{self.gateway_url}/v1/mem0/recall",
                    params=params,
                    headers=self._auth_headers(),
                ) as resp:
                    if resp.status != 200:
                        logger.debug("mem0 recall status %s (sin auth?)", resp.status)
                        return []
                    data = await resp.json()

            results: list[KnowledgeEntry] = []
            # El gateway envuelve la respuesta en {"ok": ..., "data": {...}}
            # Las memorias pueden estar en data.data.memories o directamente en data.memories
            payload = data.get("data", data) if isinstance(data.get("data"), dict) else data
            memories = (
                payload.get("memories") or payload.get("entries") or payload.get("results") or []
            )
            if not isinstance(memories, list):
                memories = []
            for i, mem in enumerate(memories[:limit]):
                content = mem.get("memory", mem.get("content", mem.get("text", "")))
                meta = mem.get("metadata", {})
                entry = KnowledgeEntry(
                    id=mem.get("id", f"mem0_{i}"),
                    content=str(content),
                    source=KnowledgeSource.MEM0,
                    category=_classify_category(str(content), meta),
                    relevance_score=mem.get("score", 1.0 - i * 0.05),
                    timestamp=meta.get("created_at", meta.get("timestamp", "")),
                    metadata=meta,
                )
                results.append(entry)
            return results
        except Exception as exc:
            logger.warning("mem0 search failed: %s", exc)
            return []

    async def store(self, content: str, metadata: dict[str, Any] | None = None) -> bool:
        """Almacena en mem0 via gateway."""
        try:
            import aiohttp

            payload: dict[str, Any] = {"memory": content}
            if metadata:
                payload["metadata"] = metadata
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.post(
                    f"{self.gateway_url}/v1/mem0/store",
                    json=payload,
                    headers=self._auth_headers(),
                ) as resp:
                    return resp.status in (200, 201)
        except Exception as exc:
            logger.warning("mem0 store failed: %s", exc)
            return False


class GitVaultAdapter:
    """Adapter para leer un vault de Obsidian directo del disco (sin REST API).

    Funciona aunque Obsidian no esté abierto. Lee los archivos .md
    directamente del directorio del vault (local o clonado via git).
    """

    def __init__(self, vault_path: str | None = None) -> None:
        self._vault_path: Path | None = None
        if vault_path:
            self._vault_path = Path(vault_path)
        else:
            # Intentar detectar vault desde env o paths conocidos
            env_path = os.getenv("OBSIDIAN_VAULT_PATH")
            if env_path:
                self._vault_path = Path(env_path)

    def is_available(self) -> bool:
        """El vault es accesible si el directorio existe y tiene .md files."""
        if self._vault_path is None:
            return False
        return self._vault_path.is_dir() and any(self._vault_path.glob("*.md"))

    def _read_note(self, path: Path) -> KnowledgeEntry | None:
        """Lee una nota y la convierte a KnowledgeEntry."""
        try:
            content = path.read_text(encoding="utf-8")
            rel_path = str(path.relative_to(self._vault_path)) if self._vault_path else path.name

            # Extraer frontmatter básico
            frontmatter: dict[str, Any] = {}
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    for line in parts[1].strip().split("\n"):
                        if ":" in line:
                            key, _, val = line.partition(":")
                            frontmatter[key.strip()] = val.strip().strip('"').strip("'")
                    content = parts[2].strip()

            return KnowledgeEntry(
                id=f"vault_{hashlib.md5(rel_path.encode(), usedforsecurity=False).hexdigest()[:12]}",
                content=content[:2000],
                source=KnowledgeSource.OBSIDIAN,
                category=_classify_obsidian_note(rel_path),
                relevance_score=0.8,
                timestamp=frontmatter.get("date", ""),
                metadata={
                    "path": rel_path,
                    "frontmatter": frontmatter,
                    "tags": [
                        t.strip().lstrip("#")
                        for t in frontmatter.get("tags", "").split(",")
                        if t.strip()
                    ]
                    if isinstance(frontmatter.get("tags"), str)
                    else [],
                },
            )
        except Exception as exc:
            logger.debug("Failed to read vault note %s: %s", path, exc)
            return None

    def search(self, query: str, limit: int = 10) -> list[KnowledgeEntry]:
        """Búsqueda por texto en archivos del vault."""
        if not self.is_available():
            return []
        query_lower = query.lower()
        results: list[KnowledgeEntry] = []

        assert self._vault_path is not None  # guarded by is_available
        for md_file in sorted(self._vault_path.rglob("*.md")):
            # Skip hidden dirs and .obsidian
            if any(part.startswith(".") for part in md_file.relative_to(self._vault_path).parts):
                continue
            try:
                content = md_file.read_text(encoding="utf-8")
                if query_lower in content.lower():
                    entry = self._read_note(md_file)
                    if entry:
                        # Boost relevance if query is in title
                        if query_lower in md_file.stem.lower():
                            entry.relevance_score = 0.95
                        results.append(entry)
                        if len(results) >= limit:
                            break
            except Exception:
                continue
        return results

    def list_folder(self, folder: str, limit: int = 20) -> list[KnowledgeEntry]:
        """Lista notas de una carpeta específica."""
        if not self.is_available():
            return []
        assert self._vault_path is not None  # guarded by is_available
        folder_path = self._vault_path / folder
        if not folder_path.is_dir():
            return []
        results: list[KnowledgeEntry] = []
        for md_file in sorted(folder_path.glob("*.md"), reverse=True):
            entry = self._read_note(md_file)
            if entry:
                results.append(entry)
                if len(results) >= limit:
                    break
        return results

    def list_projects(self, limit: int = 20) -> list[KnowledgeEntry]:
        """Lista notas de proyectos."""
        return self.list_folder("proyectos", limit)

    def list_daily_notes(self, limit: int = 10) -> list[KnowledgeEntry]:
        """Lista daily notes recientes."""
        return self.list_folder("daily-notes", limit)

    def list_research(self, limit: int = 10) -> list[KnowledgeEntry]:
        """Lista research notes."""
        return self.list_folder("research", limit)


class ObsidianAdapter:
    """Adapter para interactuar con Obsidian vault.

    Intenta primero la REST API de Obsidian. Si no está disponible,
    usa GitVaultAdapter como fallback para leer el vault del filesystem.
    """

    def __init__(self, vault_path: str | None = None) -> None:
        self._client: Any = None
        self._vault_path = vault_path
        self._available: bool | None = None
        self._git_vault = GitVaultAdapter(vault_path)
        self._use_git_fallback: bool = False

    async def _get_client(self) -> Any:
        """Lazy-load ObsidianClient."""
        if self._client is not None:
            return self._client
        try:
            from .obsidian_client import ObsidianClient

            self._client = ObsidianClient()
            return self._client
        except ImportError:
            logger.warning("ObsidianClient not available")
            return None

    async def is_available(self) -> bool:
        """Verifica si Obsidian está accesible (REST o filesystem)."""
        # Try REST API first
        try:
            client = await self._get_client()
            if client is not None:
                async with client:
                    result = await client.health_check()
                    if result:
                        self._available = True
                        self._use_git_fallback = False
                        return True
        except Exception:
            pass

        # Fallback to direct filesystem access
        if self._git_vault is not None and self._git_vault.is_available():
            self._available = True
            self._use_git_fallback = True
            logger.info("Obsidian REST unavailable, using vault filesystem fallback")
            return True

        self._available = False
        return False

    async def search(self, query: str, limit: int = 10) -> list[KnowledgeEntry]:
        """Busca notas en Obsidian."""
        # Git vault fallback (sync, run in executor)
        if self._use_git_fallback and self._git_vault:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._git_vault.search, query, limit)

        if self._available is False:
            return []
        try:
            client = await self._get_client()
            if client is None:
                return []
            async with client:
                notes = await client.search(query, limit=limit)
                results: list[KnowledgeEntry] = []
                for i, note in enumerate(notes[:limit]):
                    entry = KnowledgeEntry(
                        id=f"obsidian_{hashlib.md5(note.path.encode(), usedforsecurity=False).hexdigest()[:12]}",
                        content=note.content[:2000] if note.content else "",
                        source=KnowledgeSource.OBSIDIAN,
                        category=_classify_obsidian_note(note.path),
                        relevance_score=1.0 - i * 0.05,
                        timestamp=note.stat.mtime if note.stat else "",
                        metadata={
                            "path": note.path,
                            "tags": note.tags or [],
                            "frontmatter": note.frontmatter or {},
                        },
                    )
                    results.append(entry)
                return results
        except Exception as exc:
            logger.warning("Obsidian search failed: %s", exc)
            return []

    async def list_decisions(self, limit: int = 20) -> list[KnowledgeEntry]:
        """Lista decisiones (ADRs) del vault."""
        # Git vault fallback
        if self._use_git_fallback and self._git_vault:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, self._git_vault.list_folder, "06-Decisiones", limit
            )

        try:
            client = await self._get_client()
            if client is None:
                return []
            async with client:
                notes = await client.list_notes("06-Decisiones")
                results: list[KnowledgeEntry] = []
                for i, note_path in enumerate(notes[:limit]):
                    note = await client.get_note(note_path)
                    if note and note.content:
                        results.append(
                            KnowledgeEntry(
                                id=f"obsidian_adr_{i}",
                                content=note.content[:2000],
                                source=KnowledgeSource.OBSIDIAN,
                                category=KnowledgeCategory.DECISION,
                                relevance_score=0.9,
                                timestamp=note.stat.mtime if note.stat else "",
                                metadata={"path": note.path},
                            )
                        )
                return results
        except Exception as exc:
            logger.debug("Obsidian decisions list failed: %s", exc)
            return []

    async def list_sessions(self, limit: int = 10) -> list[KnowledgeEntry]:
        """Lista sesiones recientes del vault."""
        # Git vault fallback
        if self._use_git_fallback and self._git_vault:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, self._git_vault.list_folder, "05-Sesiones", limit
            )

        try:
            client = await self._get_client()
            if client is None:
                return []
            async with client:
                notes = await client.list_notes("05-Sesiones")
                results: list[KnowledgeEntry] = []
                for i, note_path in enumerate(notes[:limit]):
                    note = await client.get_note(note_path)
                    if note and note.content:
                        results.append(
                            KnowledgeEntry(
                                id=f"obsidian_session_{i}",
                                content=note.content[:2000],
                                source=KnowledgeSource.OBSIDIAN,
                                category=KnowledgeCategory.SESSION,
                                relevance_score=0.8,
                                timestamp=note.stat.mtime if note.stat else "",
                                metadata={"path": note.path},
                            )
                        )
                return results
        except Exception as exc:
            logger.debug("Obsidian sessions list failed: %s", exc)
            return []

    async def write_decision(
        self, title: str, context: str, decision: str, consequences: str
    ) -> str | None:
        """Escribe un ADR en Obsidian."""
        try:
            client = await self._get_client()
            if client is None:
                return None
            async with client:
                return await client.create_adr(title, context, decision, consequences)
        except Exception as exc:
            logger.warning("Obsidian write_decision failed: %s", exc)
            return None

    async def write_session(
        self,
        summary: str,
        files_changed: list[str] | None = None,
        decisions: list[str] | None = None,
    ) -> str | None:
        """Escribe una nota de sesión en Obsidian."""
        try:
            client = await self._get_client()
            if client is None:
                return None
            async with client:
                return await client.create_session_note(
                    summary, files_changed or [], decisions or []
                )
        except Exception as exc:
            logger.warning("Obsidian write_session failed: %s", exc)
            return None


class ProjectMemoryAdapter:
    """Adapter para ProjectMemory local."""

    def __init__(self, project_root: str | None = None) -> None:
        self._pm: Any = None
        self._project_root = project_root

    def _get_pm(self) -> Any:
        """Lazy-load ProjectMemory."""
        if self._pm is not None:
            return self._pm
        try:
            from .project_memory import get_project_memory

            self._pm = get_project_memory(self._project_root)
            return self._pm
        except ImportError:
            logger.warning("ProjectMemory not available")
            return None

    def is_available(self) -> bool:
        """ProjectMemory siempre está disponible si el módulo existe."""
        return self._get_pm() is not None

    def get_decisions(self, limit: int = 20) -> list[KnowledgeEntry]:
        """Obtiene decisiones del proyecto."""
        pm = self._get_pm()
        if pm is None:
            return []
        try:
            decisions = pm.get_decisions(limit=limit)
            return [
                KnowledgeEntry(
                    id=d.get("id", f"pm_decision_{i}"),
                    content=_format_decision(d),
                    source=KnowledgeSource.PROJECT,
                    category=KnowledgeCategory.DECISION,
                    relevance_score=0.9,
                    timestamp=d.get("date", ""),
                    metadata=d,
                )
                for i, d in enumerate(decisions)
            ]
        except Exception as exc:
            logger.warning("ProjectMemory decisions failed: %s", exc)
            return []

    def get_errors(self, query: str | None = None) -> list[KnowledgeEntry]:
        """Obtiene errores conocidos del proyecto."""
        pm = self._get_pm()
        if pm is None:
            return []
        try:
            errors = pm.get_known_errors(query=query)
            return [
                KnowledgeEntry(
                    id=f"pm_error_{i}",
                    content=_format_error(e),
                    source=KnowledgeSource.PROJECT,
                    category=KnowledgeCategory.ERROR,
                    relevance_score=0.85,
                    timestamp=e.get("last_seen", ""),
                    metadata=e,
                )
                for i, e in enumerate(errors)
            ]
        except Exception as exc:
            logger.warning("ProjectMemory errors failed: %s", exc)
            return []

    def get_hotspots(self, top_k: int = 10) -> list[KnowledgeEntry]:
        """Obtiene archivos hotspot (más modificados)."""
        pm = self._get_pm()
        if pm is None:
            return []
        try:
            hotspots = pm.get_hotspots(top_k=top_k)
            return [
                KnowledgeEntry(
                    id=f"pm_hotspot_{i}",
                    content=f"{h.get('path', '?')}: {h.get('modifications', 0)} cambios",
                    source=KnowledgeSource.PROJECT,
                    category=KnowledgeCategory.HOTSPOT,
                    relevance_score=0.7,
                    timestamp=h.get("last_modified", ""),
                    metadata=h,
                )
                for i, h in enumerate(hotspots)
            ]
        except Exception as exc:
            logger.warning("ProjectMemory hotspots failed: %s", exc)
            return []

    def get_sessions(self, limit: int = 5) -> list[KnowledgeEntry]:
        """Obtiene sesiones recientes."""
        pm = self._get_pm()
        if pm is None:
            return []
        try:
            sessions = pm.get_recent_sessions(last_n=limit)
            return [
                KnowledgeEntry(
                    id=s.get("session_id", f"pm_session_{i}"),
                    content=_format_session(s),
                    source=KnowledgeSource.PROJECT,
                    category=KnowledgeCategory.SESSION,
                    relevance_score=0.75,
                    timestamp=s.get("date", ""),
                    metadata=s,
                )
                for i, s in enumerate(sessions)
            ]
        except Exception as exc:
            logger.warning("ProjectMemory sessions failed: %s", exc)
            return []

    def get_ci_health(self) -> dict[str, Any]:
        """Obtiene salud de CI."""
        pm = self._get_pm()
        if pm is None:
            return {}
        try:
            return pm.get_ci_health()
        except Exception:
            return {}

    def get_test_trends(self, last_n: int = 10) -> list[dict[str, Any]]:
        """Obtiene tendencias de tests."""
        pm = self._get_pm()
        if pm is None:
            return []
        try:
            return pm.get_test_trends(last_n=last_n)
        except Exception:
            return []

    def get_project_health(self) -> dict[str, Any]:
        """Obtiene salud general del proyecto."""
        pm = self._get_pm()
        if pm is None:
            return {}
        try:
            return pm.get_project_health()
        except Exception:
            return {}

    def search_decisions(self, query: str) -> list[KnowledgeEntry]:
        """Busca decisiones por texto."""
        pm = self._get_pm()
        if pm is None:
            return []
        try:
            results = pm.search_decisions(query)
            return [
                KnowledgeEntry(
                    id=d.get("id", f"pm_dec_search_{i}"),
                    content=_format_decision(d),
                    source=KnowledgeSource.PROJECT,
                    category=KnowledgeCategory.DECISION,
                    relevance_score=0.85,
                    timestamp=d.get("date", ""),
                    metadata=d,
                )
                for i, d in enumerate(results)
            ]
        except Exception:
            return []


# ---------------------------------------------------------------------------
# Unified Knowledge Bridge — la interfaz principal
# ---------------------------------------------------------------------------


class UnifiedKnowledgeBridge:
    """Puente unificado de conocimiento del ecosistema Antigravity.

    Integra mem0 (semántico), Obsidian (vault) y ProjectMemory (local)
    en una sola interfaz para búsqueda, almacenamiento y sincronización.

    Usage:
        bridge = UnifiedKnowledgeBridge(project_root="/path/to/project")
        results = await bridge.search("cómo configuré CORS")
        context = await bridge.get_project_context()
        brief = await bridge.generate_knowledge_brief()
    """

    def __init__(
        self,
        project_root: str | None = None,
        gateway_url: str | None = None,
        obsidian_vault_path: str | None = None,
    ) -> None:
        _gw = gateway_url or str(os.getenv("ANTIGRAVITY_GATEWAY_URL", "http://127.0.0.1:4747"))
        self.mem0 = Mem0Adapter(gateway_url=_gw)
        self.obsidian = ObsidianAdapter(vault_path=obsidian_vault_path)
        self.project = ProjectMemoryAdapter(project_root=project_root)
        self._project_root = project_root

    async def check_sources(self) -> dict[str, bool]:
        """Verifica disponibilidad de cada fuente."""
        mem0_ok, obsidian_ok = await asyncio.gather(
            self.mem0.is_available(),
            self.obsidian.is_available(),
        )
        project_ok = self.project.is_available()
        return {
            "mem0": mem0_ok,
            "obsidian": obsidian_ok,
            "project_memory": project_ok,
        }

    async def search(
        self,
        query: str,
        sources: list[KnowledgeSource] | None = None,
        limit: int = 20,
    ) -> list[KnowledgeEntry]:
        """Búsqueda unificada across todas las fuentes.

        Consulta en paralelo mem0, Obsidian y ProjectMemory, luego
        fusiona, deduplica y rankea los resultados por relevancia.

        Args:
            query: Texto de búsqueda en lenguaje natural.
            sources: Fuentes a consultar (None = todas).
            limit: Máximo de resultados.

        Returns:
            Lista de KnowledgeEntry ordenada por relevance_score.
        """
        active_sources = sources or list(KnowledgeSource)
        tasks: list[asyncio.Task[list[KnowledgeEntry]]] = []

        if KnowledgeSource.MEM0 in active_sources:
            tasks.append(asyncio.create_task(self.mem0.search(query, limit=limit)))

        if KnowledgeSource.OBSIDIAN in active_sources:
            tasks.append(asyncio.create_task(self.obsidian.search(query, limit=limit)))

        # ProjectMemory es sync, lo corremos en executor
        pm_results: list[KnowledgeEntry] = []
        if KnowledgeSource.PROJECT in active_sources:
            loop = asyncio.get_event_loop()
            pm_decisions = await loop.run_in_executor(None, self.project.search_decisions, query)
            pm_errors = await loop.run_in_executor(None, self.project.get_errors, query)
            pm_results = pm_decisions + pm_errors

        # Esperar resultados async
        async_results: list[KnowledgeEntry] = []
        if tasks:
            gathered = await asyncio.gather(*tasks, return_exceptions=True)
            for result in gathered:
                if isinstance(result, list):
                    async_results.extend(result)
                elif isinstance(result, Exception):
                    logger.warning("Knowledge source failed: %s", result)

        all_results = async_results + pm_results
        all_results = _deduplicate(all_results)
        all_results.sort(key=lambda e: e.relevance_score, reverse=True)
        return all_results[:limit]

    async def get_project_context(self) -> ProjectKnowledge:
        """Obtiene TODO el contexto conocido sobre el proyecto actual.

        Recopila decisiones, errores, patrones, sesiones, hotspots,
        salud de CI, tendencias de tests, notas de Obsidian y memorias
        de mem0 — todo en un solo objeto.

        Returns:
            ProjectKnowledge con toda la información disponible.
        """
        pk = ProjectKnowledge(project_path=self._project_root or ".")

        # Recopilar de ProjectMemory (sync)
        loop = asyncio.get_event_loop()
        pk.decisions = await loop.run_in_executor(None, self.project.get_decisions, 30)
        pk.errors = await loop.run_in_executor(None, self.project.get_errors, None)
        pk.hotspots = await loop.run_in_executor(None, self.project.get_hotspots, 15)
        pk.sessions = await loop.run_in_executor(None, self.project.get_sessions, 10)
        pk.ci_health = await loop.run_in_executor(None, self.project.get_ci_health)
        pk.test_trends = await loop.run_in_executor(None, self.project.get_test_trends, 10)

        # Recopilar de Obsidian y mem0 (async, paralelo)
        project_name = Path(self._project_root).name if self._project_root else "proyecto"

        obsidian_task = asyncio.create_task(self.obsidian.list_decisions(limit=15))
        mem0_task = asyncio.create_task(self.mem0.search(f"proyecto {project_name}", limit=15))

        obsidian_results, mem0_results = await asyncio.gather(
            obsidian_task, mem0_task, return_exceptions=True
        )
        if isinstance(obsidian_results, list):
            pk.obsidian_notes = obsidian_results
        if isinstance(mem0_results, list):
            pk.mem0_memories = mem0_results

        return pk

    async def store(
        self,
        content: str,
        category: KnowledgeCategory,
        metadata: dict[str, Any] | None = None,
        targets: list[KnowledgeSource] | None = None,
    ) -> dict[str, bool]:
        """Almacena conocimiento en una o más fuentes.

        Args:
            content: Texto del conocimiento.
            category: Categoría semántica.
            metadata: Metadatos adicionales.
            targets: Fuentes destino (None = auto-route).

        Returns:
            Dict con resultado por fuente: {"mem0": True, "obsidian": False, ...}.
        """
        meta = metadata or {}
        meta["category"] = category.value
        meta["stored_at"] = datetime.now().isoformat()

        if targets is None:
            targets = _auto_route_targets(category)

        results: dict[str, bool] = {}

        if KnowledgeSource.MEM0 in targets:
            results["mem0"] = await self.mem0.store(content, meta)

        if KnowledgeSource.OBSIDIAN in targets:
            results["obsidian"] = await self._store_obsidian(content, category, meta)

        if KnowledgeSource.PROJECT in targets:
            results["project_memory"] = self._store_project(content, category, meta)

        return results

    async def _store_obsidian(
        self, content: str, category: KnowledgeCategory, meta: dict[str, Any]
    ) -> bool:
        """Almacena en Obsidian según la categoría (solo decisions y sessions).

        Returns:
            True si se escribió un archivo, False si la categoría no aplica o falló.
        """
        if category == KnowledgeCategory.DECISION:
            path = await self.obsidian.write_decision(
                title=meta.get("title", "Decisión sin título"),
                context=meta.get("context", ""),
                decision=content,
                consequences=meta.get("consequences", ""),
            )
            return path is not None
        if category == KnowledgeCategory.SESSION:
            path = await self.obsidian.write_session(
                summary=content,
                files_changed=meta.get("files_changed", []),
                decisions=meta.get("decisions", []),
            )
            return path is not None
        return False

    def _store_project(
        self, content: str, category: KnowledgeCategory, meta: dict[str, Any]
    ) -> bool:
        """Almacena en ProjectMemory según la categoría (decisions y errors).

        Returns:
            True si se registró, False si no aplica o hubo excepción.
        """
        pm = self.project._get_pm()
        if pm and category == KnowledgeCategory.DECISION:
            try:
                pm.record_decision(
                    description=content,
                    chosen=meta.get("chosen", content[:100]),
                    reasoning=meta.get("reasoning", ""),
                    tags=meta.get("tags", []),
                )
                return True
            except Exception:
                return False
        if pm and category == KnowledgeCategory.ERROR:
            try:
                pm.record_error(
                    pattern=content,
                    resolution=meta.get("resolution", ""),
                    prevention=meta.get("prevention", ""),
                    files_affected=meta.get("files_affected", []),
                )
                return True
            except Exception:
                return False
        return False

    async def generate_knowledge_brief(self, max_chars: int = 8000) -> str:
        """Genera un KNOWLEDGE_BRIEF.md con todo el contexto del proyecto.

        Este archivo se inyecta en proyectos externos para que cualquier
        IA tenga acceso completo al conocimiento del proyecto.

        Args:
            max_chars: Límite de caracteres del brief.

        Returns:
            Contenido markdown del knowledge brief.
        """
        pk = await self.get_project_context()
        now = datetime.now().isoformat(timespec="seconds")
        project_name = Path(self._project_root).name if self._project_root else "Proyecto"

        sections: list[str] = [
            f"# Knowledge Brief — {project_name}",
            "\n> Auto-generado por Antigravity Unified Knowledge Bridge.",
            f"> Fecha: {now}",
            "> Fuentes: mem0 + Obsidian + ProjectMemory",
            f"> Total entradas: {pk.total_entries}",
        ]

        for builder in (
            self._brief_decisions,
            self._brief_errors,
            self._brief_hotspots,
            self._brief_sessions,
            self._brief_ci_health,
            self._brief_test_trends,
            self._brief_obsidian_notes,
            self._brief_mem0_memories,
        ):
            sections.extend(builder(pk))

        brief = "\n".join(sections)
        if len(brief) > max_chars:
            brief = brief[:max_chars] + "\n\n> [Truncado por límite de tokens]"

        return brief

    @staticmethod
    def _brief_decisions(pk: ProjectKnowledge) -> list[str]:
        """Construye la sección de decisiones de arquitectura del brief.

        Args:
            pk: Conocimiento agregado del proyecto.

        Returns:
            Líneas markdown de la sección (vacío si no hay decisiones).
        """
        if not pk.decisions:
            return []
        lines = ["\n## Decisiones de Arquitectura\n"]
        lines.extend(f"- **{d.timestamp}**: {d.content[:200]}" for d in pk.decisions[:10])
        return lines

    @staticmethod
    def _brief_errors(pk: ProjectKnowledge) -> list[str]:
        """Construye la sección de errores conocidos del brief.

        Args:
            pk: Conocimiento agregado del proyecto.

        Returns:
            Líneas markdown de la sección (vacío si no hay errores).
        """
        if not pk.errors:
            return []
        lines = ["\n## Errores Conocidos y Resoluciones\n"]
        lines.extend(f"- {e.content[:200]}" for e in pk.errors[:10])
        return lines

    @staticmethod
    def _brief_hotspots(pk: ProjectKnowledge) -> list[str]:
        """Construye la sección de archivos hotspot del brief.

        Args:
            pk: Conocimiento agregado del proyecto.

        Returns:
            Líneas markdown de la sección (vacío si no hay hotspots).
        """
        if not pk.hotspots:
            return []
        lines = ["\n## Archivos Hotspot (más modificados)\n"]
        lines.extend(f"- {h.content}" for h in pk.hotspots[:8])
        return lines

    @staticmethod
    def _brief_sessions(pk: ProjectKnowledge) -> list[str]:
        """Construye la sección de sesiones recientes del brief.

        Args:
            pk: Conocimiento agregado del proyecto.

        Returns:
            Líneas markdown de la sección (vacío si no hay sesiones).
        """
        if not pk.sessions:
            return []
        lines = ["\n## Sesiones Recientes\n"]
        lines.extend(f"- **{s.timestamp}**: {s.content[:200]}" for s in pk.sessions[:5])
        return lines

    @staticmethod
    def _brief_ci_health(pk: ProjectKnowledge) -> list[str]:
        """Construye la sección de salud de CI del brief.

        Args:
            pk: Conocimiento agregado del proyecto.

        Returns:
            Líneas markdown de la sección (vacío si no hay datos de CI).
        """
        if not pk.ci_health:
            return []
        status = pk.ci_health.get("status", "unknown")
        rate = pk.ci_health.get("success_rate", 0)
        return ["\n## Salud de CI\n", f"- Estado: **{status}** (éxito: {rate:.0%})"]

    @staticmethod
    def _brief_test_trends(pk: ProjectKnowledge) -> list[str]:
        """Construye la sección de tests del brief.

        Args:
            pk: Conocimiento agregado del proyecto.

        Returns:
            Líneas markdown de la sección (vacío si no hay tendencias de tests).
        """
        if not pk.test_trends:
            return []
        latest = pk.test_trends[-1]
        if not latest:
            return []
        return [
            "\n## Tests\n",
            (
                f"- Último run: {latest.get('passed', 0)} passed, "
                f"{latest.get('failed', 0)} failed, "
                f"{latest.get('skipped', 0)} skipped"
            ),
        ]

    @staticmethod
    def _brief_obsidian_notes(pk: ProjectKnowledge) -> list[str]:
        """Construye la sección de notas de Obsidian del brief.

        Args:
            pk: Conocimiento agregado del proyecto.

        Returns:
            Líneas markdown de la sección (vacío si no hay notas).
        """
        if not pk.obsidian_notes:
            return []
        lines = ["\n## Notas de Obsidian\n"]
        for n in pk.obsidian_notes[:5]:
            path = n.metadata.get("path", "")
            lines.append(f"- [{path}] {n.content[:150]}")
        return lines

    @staticmethod
    def _brief_mem0_memories(pk: ProjectKnowledge) -> list[str]:
        """Construye la sección de memorias semánticas (mem0) del brief.

        Args:
            pk: Conocimiento agregado del proyecto.

        Returns:
            Líneas markdown de la sección (vacío si no hay memorias).
        """
        if not pk.mem0_memories:
            return []
        lines = ["\n## Memorias Semánticas (mem0)\n"]
        lines.extend(f"- {m.content[:200]}" for m in pk.mem0_memories[:5])
        return lines

    async def sync_to_obsidian(self) -> SyncResult:
        """Sincroniza conocimiento del proyecto → Obsidian.

        Toma decisiones y sesiones de ProjectMemory que no están en
        Obsidian y las escribe como notas.
        """
        from .knowledge_sync import sync_project_to_obsidian

        return await sync_project_to_obsidian(self.project, self.obsidian)

    async def sync_from_obsidian(self) -> SyncResult:
        """Sincroniza conocimiento de Obsidian → mem0.

        Toma notas de Obsidian y las indexa en mem0 para búsqueda semántica.
        """
        from .knowledge_sync import sync_obsidian_to_mem0

        return await sync_obsidian_to_mem0(self.obsidian, self.mem0)

    async def full_sync(self) -> SyncResult:
        """Sincronización bidireccional completa."""
        import time

        start = time.monotonic()

        result_to, result_from = await asyncio.gather(
            self.sync_to_obsidian(),
            self.sync_from_obsidian(),
            return_exceptions=True,
        )

        merged = SyncResult()
        if isinstance(result_to, SyncResult):
            merged.synced_to_obsidian = result_to.synced_to_obsidian
            merged.errors.extend(result_to.errors)
        elif isinstance(result_to, Exception):
            merged.errors.append(f"sync_to_obsidian: {result_to}")

        if isinstance(result_from, SyncResult):
            merged.synced_from_obsidian = result_from.synced_from_obsidian
            merged.synced_to_mem0 = result_from.synced_to_mem0
            merged.errors.extend(result_from.errors)
        elif isinstance(result_from, Exception):
            merged.errors.append(f"sync_from_obsidian: {result_from}")

        merged.duration_ms = (time.monotonic() - start) * 1000
        return merged


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _classify_category(content: str, metadata: dict[str, Any]) -> KnowledgeCategory:
    """Clasifica categoría basándose en contenido y metadata."""
    cat = metadata.get("category", "").lower()
    if cat in ("decision", "decisión"):
        return KnowledgeCategory.DECISION
    if cat in ("error", "bug", "bugfix"):
        return KnowledgeCategory.ERROR
    if cat in ("pattern", "patrón"):
        return KnowledgeCategory.PATTERN
    if cat in ("session", "sesión"):
        return KnowledgeCategory.SESSION

    content_lower = content.lower()
    if any(w in content_lower for w in ("decidí", "decisión", "decided", "elegimos")):
        return KnowledgeCategory.DECISION
    if any(w in content_lower for w in ("error", "bug", "fix", "crash", "falla")):
        return KnowledgeCategory.ERROR
    if any(w in content_lower for w in ("patrón", "pattern", "convención")):
        return KnowledgeCategory.PATTERN
    return KnowledgeCategory.GENERAL


def _classify_obsidian_note(path: str) -> KnowledgeCategory:
    """Clasifica categoría de nota Obsidian por su ubicación."""
    path_lower = path.lower()
    if "decisiones" in path_lower or "adr" in path_lower:
        return KnowledgeCategory.DECISION
    if "sesiones" in path_lower:
        return KnowledgeCategory.SESSION
    if "error" in path_lower or "bug" in path_lower:
        return KnowledgeCategory.ERROR
    return KnowledgeCategory.NOTE


def _format_decision(d: dict[str, Any]) -> str:
    """Formatea una decisión de ProjectMemory como texto legible."""
    parts = [d.get("description", "")]
    if d.get("chosen"):
        parts.append(f"Elegido: {d['chosen']}")
    if d.get("reasoning"):
        parts.append(f"Razón: {d['reasoning']}")
    if d.get("outcome"):
        parts.append(f"Resultado: {d['outcome']}")
    return " | ".join(p for p in parts if p)


def _format_error(e: dict[str, Any]) -> str:
    """Formatea un error de ProjectMemory como texto legible."""
    parts = [e.get("pattern", "")]
    if e.get("resolution"):
        parts.append(f"Resolución: {e['resolution']}")
    if e.get("prevention"):
        parts.append(f"Prevención: {e['prevention']}")
    occ = e.get("occurrences", 0)
    if occ > 1:
        parts.append(f"({occ} ocurrencias)")
    return " | ".join(p for p in parts if p)


def _format_session(s: dict[str, Any]) -> str:
    """Formatea una sesión de ProjectMemory como texto legible."""
    desc = s.get("task_description", "Sesión sin descripción")
    files = len(s.get("files_modified", []))
    commits = len(s.get("commits", []))
    return f"{desc} ({files} archivos, {commits} commits)"


def _deduplicate(entries: list[KnowledgeEntry]) -> list[KnowledgeEntry]:
    """Deduplica entradas por contenido similar."""
    seen_hashes: set[str] = set()
    unique: list[KnowledgeEntry] = []
    for entry in entries:
        content_hash = hashlib.md5(
            entry.content[:200].lower().encode(), usedforsecurity=False
        ).hexdigest()
        if content_hash not in seen_hashes:
            seen_hashes.add(content_hash)
            unique.append(entry)
    return unique


def _auto_route_targets(category: KnowledgeCategory) -> list[KnowledgeSource]:
    """Determina las fuentes destino automáticamente según categoría."""
    if category in (KnowledgeCategory.DECISION, KnowledgeCategory.SESSION):
        return [KnowledgeSource.MEM0, KnowledgeSource.OBSIDIAN, KnowledgeSource.PROJECT]
    if category in (KnowledgeCategory.ERROR, KnowledgeCategory.PATTERN):
        return [KnowledgeSource.MEM0, KnowledgeSource.PROJECT]
    return [KnowledgeSource.MEM0]


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_bridge: UnifiedKnowledgeBridge | None = None


def get_knowledge_bridge(
    project_root: str | None = None,
    gateway_url: str | None = None,
) -> UnifiedKnowledgeBridge:
    """Obtiene instancia singleton del bridge.

    Si se pasan project_root o gateway_url distintos a los del singleton
    existente, se crea una nueva instancia para respetar el contexto pedido.
    """
    global _bridge
    if _bridge is None:
        _bridge = UnifiedKnowledgeBridge(project_root=project_root, gateway_url=gateway_url)
        return _bridge

    # Si el caller pide un project_root específico y el singleton fue creado
    # sin él (o con uno distinto), devolver una instancia fresca sin reemplazar
    # el singleton global (para no romper otros callers que confían en él).
    if project_root is not None and _bridge._project_root != project_root:
        return UnifiedKnowledgeBridge(project_root=project_root, gateway_url=gateway_url)

    return _bridge
