#!/usr/bin/env python3
"""Skill Search Index - Busqueda semantica de skills via ChromaDB.

Indexa SKILL.md en ChromaDB para busqueda semantica con fallback por keywords.
Usage: ``index = get_skill_search(); index.reindex(); index.search("query")``
v1.0.0 - 2026-02-27
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger("antigravity.skill_search")


@dataclass
class SkillInfo:
    """Informacion extraida de un SKILL.md."""

    name: str
    path: Path
    description: str
    triggers: list[str] = field(default_factory=list)
    content: str = ""
    content_hash: str = ""

    def to_document(self) -> str:
        """Genera texto indexable combinando nombre, descripcion, triggers y contenido."""
        parts = [f"Skill: {self.name}"]
        if self.description:
            parts.append(self.description)
        if self.triggers:
            parts.append(f"Triggers: {', '.join(self.triggers)}")
        body = self.content.strip()
        if body:
            parts.append(body[:500])
        return "\n".join(parts)


@dataclass
class SkillSearchResult:
    """Resultado de busqueda de skills."""

    name: str
    path: str
    description: str
    score: float
    triggers: list[str] = field(default_factory=list)


class SkillSearchIndex:
    """Indice de busqueda semantica de skills con ChromaDB y fallback por keywords."""

    COLLECTION_NAME = "antigravity_skills"

    def __init__(self, project_root: str | None = None) -> None:
        self._root = Path(project_root).resolve() if project_root else Path(".").resolve()
        self._collection: Any = None
        self._client: Any = None
        self._chroma_available: bool | None = None
        self._skills_cache: dict[str, SkillInfo] = {}

    def _ensure_collection(self) -> bool:
        """Inicializa la coleccion ChromaDB de forma lazy."""
        if self._chroma_available is False:
            return False
        if self._collection is not None:
            return True
        try:
            import chromadb

            self._client = chromadb.HttpClient(host="localhost", port=8000)
            self._client.heartbeat()
            self._collection = self._client.get_or_create_collection(
                name=self.COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
            self._chroma_available = True
            logger.info("ChromaDB conectado (coleccion: %s)", self.COLLECTION_NAME)
            return True
        except Exception as e:
            self._chroma_available = False
            logger.debug("ChromaDB no disponible, fallback keywords: %s", e)
            return False

    def _discover_skill_files(self) -> list[Path]:
        """Descubre todos los SKILL.md en skills/ y plugins/*/skills/."""
        paths: list[Path] = []
        for base in [self._root / ".agent" / "skills", self._root / ".agent" / "plugins"]:
            if not base.is_dir():
                continue
            if base.name == "skills":
                for d in sorted(base.iterdir()):
                    if d.is_dir() and (d / "SKILL.md").exists():
                        paths.append(d / "SKILL.md")
            else:  # plugins
                for plugin in sorted(base.iterdir()):
                    ps = plugin / "skills"
                    if plugin.is_dir() and ps.is_dir():
                        for d in sorted(ps.iterdir()):
                            if d.is_dir() and (d / "SKILL.md").exists():
                                paths.append(d / "SKILL.md")
        return paths

    @staticmethod
    def _parse_skill_md(skill_md: Path) -> SkillInfo | None:
        """Extrae metadata y contenido de un SKILL.md."""
        try:
            raw = skill_md.read_text(encoding="utf-8")
        except Exception:
            return None
        name = skill_md.parent.name
        content_hash = hashlib.sha256(raw.encode()).hexdigest()  # SHA256 para hash de cache (no es seguridad pero MD5 esta obsoleto)
        description, triggers, body = "", [], raw
        fm_match = re.match(r"^---\n(.*?)\n---\s*", raw, re.DOTALL)
        if fm_match:
            fm_text = fm_match.group(1)
            body = raw[fm_match.end() :]
            try:
                meta = yaml.safe_load(fm_text)
                if isinstance(meta, dict):
                    name = meta.get("name", name)
                    desc = meta.get("description", "")
                    description = desc if isinstance(desc, str) else ""
            except yaml.YAMLError:
                m = re.search(r'^description:\s*"?(.+?)"?\s*$', fm_text, re.MULTILINE)
                if m:
                    description = m.group(1)
        trig_match = re.search(r"(?:Triggers|Use when)[:\s]+(.+)", description, re.IGNORECASE)
        if trig_match:
            triggers = [
                t.strip().strip("\"'").strip().lower()
                for t in trig_match.group(1).rstrip(".").split(",")
                if t.strip()
            ]
        return SkillInfo(
            name=name,
            path=skill_md.parent,
            description=description,
            triggers=triggers,
            content=body.strip(),
            content_hash=content_hash,
        )

    def reindex(self, force: bool = False) -> int:
        """Indexa o actualiza skills en ChromaDB. Solo reindexar nuevos/modificados."""
        skill_files = self._discover_skill_files()
        logger.info("Descubiertos %d SKILL.md para indexar", len(skill_files))
        use_chroma = self._ensure_collection()
        indexed, existing_hashes = 0, {}
        if use_chroma and not force and self._collection is not None:
            try:
                existing = self._collection.get(include=["metadatas"])
                for i, mid in enumerate(existing["ids"]):
                    mt = existing["metadatas"][i] if existing["metadatas"] else {}
                    existing_hashes[mid] = mt.get("content_hash", "")
            except Exception:
                pass
        for skill_md in skill_files:
            info = self._parse_skill_md(skill_md)
            if info is None:
                continue
            self._skills_cache[info.name] = info
            if not force and existing_hashes.get(info.name) == info.content_hash:
                continue
            if use_chroma and self._collection is not None:
                meta: dict[str, str | int | float | bool] = {
                    "name": info.name,
                    "path": str(info.path),
                    "description": info.description[:500],
                    "content_hash": info.content_hash,
                }
                if info.triggers:
                    meta["triggers"] = ", ".join(info.triggers)
                try:
                    self._collection.upsert(
                        ids=[info.name],
                        documents=[info.to_document()],
                        metadatas=[meta],
                    )
                    indexed += 1
                except Exception as e:
                    logger.debug("Error indexando skill %s: %s", info.name, e)
        logger.info("Skills indexados/actualizados: %d de %d", indexed, len(skill_files))
        return indexed

    def search(self, query: str, limit: int = 10) -> list[SkillSearchResult]:
        """Busca skills semanticamente. Usa ChromaDB o fallback por keywords."""
        if self._ensure_collection() and self._collection is not None:
            return self._search_chroma(query, limit)
        return self._search_keyword(query, limit)

    def _search_chroma(self, query: str, limit: int) -> list[SkillSearchResult]:
        """Busqueda semantica via ChromaDB."""
        try:
            results = self._collection.query(  # type: ignore[union-attr]  # chromadb collection: nullable, checked at runtime
                query_texts=[query],
                n_results=min(limit, 20),
            )
        except Exception as e:
            logger.debug("Error en busqueda ChromaDB: %s", e)
            return self._search_keyword(query, limit)
        if not results or not results.get("ids"):
            return []
        output: list[SkillSearchResult] = []
        ids = results["ids"][0]
        distances = results.get("distances", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        for i, skill_id in enumerate(ids):
            dist = distances[i] if i < len(distances) else 0.5
            score = round(max(0.0, 1.0 - dist), 4)
            mt = metadatas[i] if i < len(metadatas) else {}
            trig_str = mt.get("triggers", "")
            trigs = [t.strip() for t in trig_str.split(",") if t.strip()] if trig_str else []
            output.append(
                SkillSearchResult(
                    name=skill_id,
                    path=mt.get("path", ""),
                    description=mt.get("description", ""),
                    score=score,
                    triggers=trigs,
                )
            )
        return output

    def _search_keyword(self, query: str, limit: int) -> list[SkillSearchResult]:
        """Fallback: busqueda por coincidencia de keywords."""
        if not self._skills_cache:
            for skill_md in self._discover_skill_files():
                info = self._parse_skill_md(skill_md)
                if info:
                    self._skills_cache[info.name] = info
        query_lower = query.casefold()
        query_words = set(query_lower.split())
        scored: list[tuple[float, SkillInfo]] = []
        for info in self._skills_cache.values():
            searchable = f"{info.name} {info.description} {' '.join(info.triggers)}".casefold()
            if query_lower in searchable:
                scored.append((0.9, info))
            else:
                overlap = len(query_words & set(searchable.split()))
                if overlap > 0:
                    scored.append((min(0.8, overlap / max(len(query_words), 1)), info))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            SkillSearchResult(
                name=info.name,
                path=str(info.path),
                description=info.description,
                score=round(s, 4),
                triggers=info.triggers,
            )
            for s, info in scored[:limit]
        ]


_instance: SkillSearchIndex | None = None


def get_skill_search(project_root: str | None = None) -> SkillSearchIndex:
    """Obtiene la instancia singleton de SkillSearchIndex."""
    global _instance  # noqa: PLW0603
    if _instance is None:
        _instance = SkillSearchIndex(project_root)
    return _instance
