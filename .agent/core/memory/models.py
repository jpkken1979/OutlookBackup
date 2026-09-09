"""Memory models and deduplication logic for OpenAntigravity memory system.

Defines MemoryEntry, MemoryDeduplicator and related types for managing
the 3-layer memory system (Markdown + Brain + mem0) with automatic
deduplication, causal ordering and temporal decay.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional
import hashlib
import json
import logging

logger = logging.getLogger(__name__)


class MemoryType(str, Enum):
    """Classificación de entradas de memoria."""

    DECISION = "decision"
    BUGFIX = "bugfix"
    DISCOVERY = "discovery"
    PATTERN = "pattern"
    CONFIG = "config"
    SESSION = "session"
    PROJECT = "project"
    AUDIT = "audit"
    FEEDBACK = "feedback"
    OTHER = "other"


class MemoryLayer(str, Enum):
    """Capas del sistema de memoria."""

    MARKDOWN = "markdown"  # .claude/memory/*.md (versionado en git)
    BRAIN = "brain"  # .agent/brain/ (conocimiento con cross-refs)
    MEM0 = "mem0"  # Gateway :4747 (cache auxiliar)


@dataclass
class MemoryEntry:
    """Una entrada individual en el sistema de memoria.

    Atributos:
        id: Hash único de contenido (para deduplicación).
        path: Ruta del archivo fuente.
        name: Nombre humano de la entrada.
        description: Descripción breve.
        content_hash: SHA256 del contenido (para detectar cambios).
        memory_type: Clasificación de la entrada.
        created_at: Timestamp de creación (ISO 8601).
        updated_at: Timestamp de última actualización.
        layer: Capas donde existe (puede estar en varias).
        confidence: Puntuación de confianza [0.0, 1.0].
        decay_factor: Factor de decaimiento temporal (para mem0).
        tags: Etiquetas adicionales.
        related_entries: IDs de entradas relacionadas.
        is_canonical: True si es la entrada de verdad (vs duplicado).
    """

    id: str
    path: Path
    name: str
    description: str
    content_hash: str
    memory_type: MemoryType
    created_at: str
    updated_at: str
    layer: list[MemoryLayer] = field(default_factory=lambda: [MemoryLayer.MARKDOWN])
    confidence: float = 1.0
    decay_factor: float = 1.0
    tags: list[str] = field(default_factory=list)
    related_entries: list[str] = field(default_factory=list)
    is_canonical: bool = True

    def to_dict(self) -> dict:
        """Serializar a diccionario."""
        return {
            "id": self.id,
            "path": str(self.path),
            "name": self.name,
            "description": self.description,
            "content_hash": self.content_hash,
            "memory_type": self.memory_type.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "layer": [l.value for l in self.layer],
            "confidence": self.confidence,
            "decay_factor": self.decay_factor,
            "tags": self.tags,
            "related_entries": self.related_entries,
            "is_canonical": self.is_canonical,
        }

    @classmethod
    def from_dict(cls, data: dict) -> MemoryEntry:
        """Deserializar de diccionario."""
        return cls(
            id=data["id"],
            path=Path(data["path"]),
            name=data["name"],
            description=data["description"],
            content_hash=data["content_hash"],
            memory_type=MemoryType(data["memory_type"]),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            layer=[MemoryLayer(l) for l in data.get("layer", ["markdown"])],
            confidence=data.get("confidence", 1.0),
            decay_factor=data.get("decay_factor", 1.0),
            tags=data.get("tags", []),
            related_entries=data.get("related_entries", []),
            is_canonical=data.get("is_canonical", True),
        )


@dataclass
class DeduplicationResult:
    """Resultado de un análisis de deduplicación.

    Atributos:
        total_entries: Total de entradas procesadas.
        duplicates_found: Número de clusters de duplicados.
        canonical_entries: Número de entradas canónicas (mantener).
        redundant_entries: IDs de entradas a eliminar.
        merge_operations: Lista de (source_id, target_id, reason) a aplicar.
        dedup_date: Timestamp del análisis.
    """

    total_entries: int
    duplicates_found: int
    canonical_entries: int
    redundant_entries: list[str] = field(default_factory=list)
    merge_operations: list[tuple[str, str, str]] = field(default_factory=list)
    dedup_date: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class MemoryDeduplicator:
    """Deduplicador de entradas de memoria con similarity matching.

    Agrupa entradas por similitud de contenido/metadatos y markea
    redundancias para eliminación o fusión, preservando la canónica.
    """

    def __init__(self, similarity_threshold: float = 0.85):
        """Inicializar deduplicador.

        Args:
            similarity_threshold: [0.0, 1.0] mínima similitud para clusters.
        """
        self.threshold = max(0.0, min(1.0, similarity_threshold))
        self.logger = logging.getLogger(__name__)

    @staticmethod
    def compute_hash(text: str) -> str:
        """Computar SHA256 del contenido."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @staticmethod
    def jaccard_similarity(set_a: set, set_b: set) -> float:
        """Jaccard similarity entre dos conjuntos.

        Args:
            set_a: Primer conjunto de tokens.
            set_b: Segundo conjunto de tokens.

        Returns:
            Similitud en [0.0, 1.0].
        """
        if not set_a and not set_b:
            return 1.0
        if not set_a or not set_b:
            return 0.0
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return intersection / union if union > 0 else 0.0

    @staticmethod
    def tokenize(text: str) -> set[str]:
        """Tokenizar texto en palabras únicas (lowercase).

        Args:
            text: Texto a tokenizar.

        Returns:
            Conjunto de tokens únicos.
        """
        words = text.lower().split()
        return {w.strip(".,;:!?\"'()[]{}") for w in words if w.strip()}

    def cluster_entries(self, entries: list[MemoryEntry]) -> dict[str, list[MemoryEntry]]:
        """Agrupar entradas en clusters de duplicados.

        Usa Jaccard similarity sobre nombres + descripciones. Cada cluster
        contiene entradas muy similares; el primero es la canónica.

        Args:
            entries: Lista de entradas.

        Returns:
            Diccionario {cluster_id: list[MemoryEntry]}.
        """
        clusters: dict[str, list[MemoryEntry]] = {}
        assigned = set()

        for i, entry_a in enumerate(entries):
            if entry_a.id in assigned:
                continue

            cluster_id = entry_a.id
            cluster = [entry_a]
            assigned.add(entry_a.id)
            tokens_a = self.tokenize(f"{entry_a.name} {entry_a.description}")

            for entry_b in entries[i + 1 :]:
                if entry_b.id in assigned:
                    continue
                tokens_b = self.tokenize(f"{entry_b.name} {entry_b.description}")
                sim = self.jaccard_similarity(tokens_a, tokens_b)

                if sim >= self.threshold:
                    cluster.append(entry_b)
                    assigned.add(entry_b.id)

            clusters[cluster_id] = cluster

        return clusters

    def deduplicate(self, entries: list[MemoryEntry]) -> DeduplicationResult:
        """Analizar duplicados y recomendar acciones.

        Args:
            entries: Lista de entradas a analizar.

        Returns:
            DeduplicationResult con acciones recomendadas.
        """
        clusters = self.cluster_entries(entries)

        redundant_ids: list[str] = []
        merge_ops: list[tuple[str, str, str]] = []
        canonical_count = 0

        for cluster_id, cluster in clusters.items():
            if len(cluster) <= 1:
                canonical_count += 1
                continue

            # Ordenar por updated_at (más reciente primero) para elegir canónica
            cluster.sort(key=lambda e: e.updated_at, reverse=True)
            canonical = cluster[0]
            canonical_count += 1

            for redundant in cluster[1:]:
                redundant_ids.append(redundant.id)
                merge_ops.append(
                    (
                        redundant.id,
                        canonical.id,
                        f"Similarity {self.threshold:.2f}: merge to canonical",
                    )
                )
                self.logger.info(
                    f"Marked {redundant.id} as redundant (duplicate of {canonical.id})"
                )

        return DeduplicationResult(
            total_entries=len(entries),
            duplicates_found=len([c for c in clusters.values() if len(c) > 1]),
            canonical_entries=canonical_count,
            redundant_entries=redundant_ids,
            merge_operations=merge_ops,
            dedup_date=datetime.utcnow().isoformat(),
        )

    def save_dedup_report(self, result: DeduplicationResult, output_path: Path) -> None:
        """Guardar reporte de deduplicación en JSON.

        Args:
            result: Resultado del análisis.
            output_path: Archivo de salida.
        """
        report = {
            "total_entries": result.total_entries,
            "duplicates_found": result.duplicates_found,
            "canonical_entries": result.canonical_entries,
            "redundant_count": len(result.redundant_entries),
            "redundant_entries": result.redundant_entries,
            "merge_operations": [
                {"source": src, "target": tgt, "reason": reason}
                for src, tgt, reason in result.merge_operations
            ],
            "dedup_date": result.dedup_date,
        }
        output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        self.logger.info(f"Dedup report written to {output_path}")
