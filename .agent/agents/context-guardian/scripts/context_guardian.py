#!/usr/bin/env python3
"""
Context Guardian Agent - Gestion proactiva del context window

Predice overflow, comprime inteligentemente, y asegura informacion critica.
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class ContextPriority(Enum):
    """Prioridad de segmentos de contexto."""

    CRITICAL = "critical"  # Nunca comprimir
    IMPORTANT = "important"  # Comprimir con cuidado
    NORMAL = "normal"  # Compresion standard
    ARCHIVABLE = "archivable"  # Puede archivarse


@dataclass
class ContextSegment:
    """Segmento de contexto."""

    id: str
    content: str
    tokens: int
    priority: ContextPriority
    created_at: datetime
    last_referenced: datetime
    category: str  # "system", "user", "assistant", "code", "context"
    compression_ratio: float = 1.0  # 1.0 = sin comprimir


@dataclass
class ContextState:
    """Estado actual del contexto."""

    total_tokens: int
    max_tokens: int
    usage_percent: float
    segments: list[ContextSegment]
    critical_count: int
    archivable_count: int

    @property
    def is_warning(self) -> bool:
        return self.usage_percent >= 70

    @property
    def is_critical(self) -> bool:
        return self.usage_percent >= 90


@dataclass
class CompressionResult:
    """Resultado de compresion."""

    original_tokens: int
    compressed_tokens: int
    segments_compressed: int
    segments_archived: int
    savings_percent: float


@dataclass
class ArchivedContext:
    """Contexto archivado."""

    id: str
    summary: str
    original_tokens: int
    archived_at: datetime
    keywords: list[str]
    recoverable: bool = True


class ContextGuardian:
    """Guardian del context window."""

    # Limites por defecto para diferentes modelos
    MODEL_LIMITS = {
        "claude-opus-4-5": 200000,
        "claude-sonnet-4": 200000,
        "claude-haiku-3-5": 200000,
        "gpt-4-turbo": 128000,
        "gpt-4o": 128000,
        "gpt-3.5-turbo": 16000,
    }

    def __init__(
        self,
        model: str = "claude-sonnet-4",
        warning_threshold: float = 0.7,
        critical_threshold: float = 0.9,
    ):
        self.model = model
        self.max_tokens = self.MODEL_LIMITS.get(model, 200000)
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold

        self.segments: list[ContextSegment] = []
        self.archived: list[ArchivedContext] = []
        self.segment_counter = 0

    def estimate_tokens(self, text: str) -> int:
        """Estima tokens en texto."""
        # Aproximacion: ~4 caracteres por token
        return len(text) // 4 + 1

    def add_segment(
        self, content: str, category: str = "context", priority: ContextPriority | None = None
    ) -> ContextSegment:
        """Agrega segmento de contexto."""
        self.segment_counter += 1

        # Auto-detectar prioridad si no se especifica
        if priority is None:
            priority = self._detect_priority(content, category)

        segment = ContextSegment(
            id=f"seg_{self.segment_counter}",
            content=content,
            tokens=self.estimate_tokens(content),
            priority=priority,
            created_at=datetime.now(),
            last_referenced=datetime.now(),
            category=category,
        )

        self.segments.append(segment)
        return segment

    def _detect_priority(self, content: str, category: str) -> ContextPriority:
        """Detecta prioridad automaticamente."""
        content_lower = content.lower()

        # System prompts siempre criticos
        if category == "system":
            return ContextPriority.CRITICAL

        # Detectar contenido critico
        critical_patterns = [
            r"importante:",
            r"critico:",
            r"no olvidar:",
            r"requisito:",
            r"must:",
            r"required:",
            r"decision:",
            r"arquitectura:",
        ]
        for pattern in critical_patterns:
            if re.search(pattern, content_lower):
                return ContextPriority.CRITICAL

        # Codigo reciente es importante
        if category == "code" and len(content) > 100:
            return ContextPriority.IMPORTANT

        # Contenido viejo es archivable
        # (esto se evaluaria con last_referenced en produccion)

        return ContextPriority.NORMAL

    def get_state(self) -> ContextState:
        """Obtiene estado actual del contexto."""
        total = sum(s.tokens for s in self.segments)

        return ContextState(
            total_tokens=total,
            max_tokens=self.max_tokens,
            usage_percent=(total / self.max_tokens) * 100,
            segments=self.segments,
            critical_count=sum(1 for s in self.segments if s.priority == ContextPriority.CRITICAL),
            archivable_count=sum(
                1 for s in self.segments if s.priority == ContextPriority.ARCHIVABLE
            ),
        )

    def predict_overflow(self, additional_tokens: int) -> dict:
        """Predice si habra overflow con tokens adicionales."""
        state = self.get_state()
        projected = state.total_tokens + additional_tokens
        projected_percent = (projected / self.max_tokens) * 100

        return {
            "current_tokens": state.total_tokens,
            "additional_tokens": additional_tokens,
            "projected_tokens": projected,
            "projected_percent": projected_percent,
            "will_overflow": projected > self.max_tokens,
            "will_warn": projected_percent >= (self.warning_threshold * 100),
            "tokens_until_overflow": max(0, self.max_tokens - projected),
            "recommendation": self._get_recommendation(projected_percent),
        }

    def _get_recommendation(self, usage_percent: float) -> str:
        """Genera recomendacion basada en uso."""
        if usage_percent >= 95:
            return "URGENTE: Comprimir inmediatamente o archivar contexto"
        if usage_percent >= 90:
            return "CRITICO: Iniciar compresion agresiva"
        if usage_percent >= 80:
            return "ADVERTENCIA: Considerar comprimir segmentos no criticos"
        if usage_percent >= 70:
            return "ATENCION: Monitorear uso de contexto"
        return "OK: Contexto dentro de limites seguros"

    def compress(
        self, target_percent: float | None = None, aggressive: bool = False
    ) -> CompressionResult:
        """Comprime contexto para reducir uso."""
        state = self.get_state()
        original_tokens = state.total_tokens

        if target_percent is None:
            target_percent = 60.0  # Default: reducir a 60%

        target_tokens = int(self.max_tokens * (target_percent / 100))
        tokens_to_remove = max(0, state.total_tokens - target_tokens)

        if tokens_to_remove == 0:
            return CompressionResult(
                original_tokens=original_tokens,
                compressed_tokens=original_tokens,
                segments_compressed=0,
                segments_archived=0,
                savings_percent=0,
            )

        segments_compressed = 0
        segments_archived = 0

        # Ordenar segmentos por prioridad (menor primero) y antiguedad
        sortable = [
            (s, s.priority.value, s.last_referenced)
            for s in self.segments
            if s.priority != ContextPriority.CRITICAL
        ]
        sortable.sort(key=lambda x: (x[1], x[2]))

        tokens_removed = 0
        segments_to_archive = []

        for segment, _, _ in sortable:
            if tokens_removed >= tokens_to_remove:
                break

            if segment.priority == ContextPriority.ARCHIVABLE or aggressive:
                # Archivar
                segments_to_archive.append(segment)
                tokens_removed += segment.tokens
                segments_archived += 1
            else:
                # Comprimir (simular - en produccion usaria LLM)
                compressed = self._compress_segment(segment)
                tokens_saved = segment.tokens - compressed.tokens
                tokens_removed += tokens_saved
                segment.content = compressed.content
                segment.tokens = compressed.tokens
                segment.compression_ratio = compressed.compression_ratio
                segments_compressed += 1

        # Mover a archivo
        for segment in segments_to_archive:
            self._archive_segment(segment)
            self.segments.remove(segment)

        new_state = self.get_state()
        savings = ((original_tokens - new_state.total_tokens) / original_tokens) * 100

        return CompressionResult(
            original_tokens=original_tokens,
            compressed_tokens=new_state.total_tokens,
            segments_compressed=segments_compressed,
            segments_archived=segments_archived,
            savings_percent=savings,
        )

    def _compress_segment(self, segment: ContextSegment) -> ContextSegment:
        """Comprime un segmento (simulado)."""
        # En produccion: usar LLM para resumir
        # Por ahora: truncar a 50%
        original_len = len(segment.content)
        compressed_content = segment.content[: original_len // 2] + "..."

        return ContextSegment(
            id=segment.id,
            content=compressed_content,
            tokens=self.estimate_tokens(compressed_content),
            priority=segment.priority,
            created_at=segment.created_at,
            last_referenced=segment.last_referenced,
            category=segment.category,
            compression_ratio=0.5,
        )

    def _archive_segment(self, segment: ContextSegment) -> None:
        """Archiva un segmento."""
        # Extraer keywords (simplificado)
        words = segment.content.lower().split()
        keywords = list({w for w in words if len(w) > 5})[:10]

        archived = ArchivedContext(
            id=segment.id,
            summary=segment.content[:200] + "..."
            if len(segment.content) > 200
            else segment.content,
            original_tokens=segment.tokens,
            archived_at=datetime.now(),
            keywords=keywords,
        )
        self.archived.append(archived)

    def recover(self, query: str) -> ArchivedContext | None:
        """Recupera contexto archivado que coincida con query."""
        query_words = set(query.lower().split())

        best_match = None
        best_score = 0

        for archived in self.archived:
            if not archived.recoverable:
                continue

            # Score basado en keywords coincidentes
            matches = len(query_words & set(archived.keywords))
            if matches > best_score:
                best_score = matches
                best_match = archived

        return best_match

    def execute(self, task: str) -> dict:
        """Ejecuta comando del guardian."""
        task_lower = task.lower()

        if task_lower == "status":
            state = self.get_state()
            return {
                "operation": "status",
                "total_tokens": state.total_tokens,
                "max_tokens": state.max_tokens,
                "usage_percent": state.usage_percent,
                "is_warning": state.is_warning,
                "is_critical": state.is_critical,
                "segments_count": len(state.segments),
                "critical_count": state.critical_count,
                "archivable_count": state.archivable_count,
                "archived_count": len(self.archived),
                "recommendation": self._get_recommendation(state.usage_percent),
            }

        elif task_lower.startswith("predict:"):
            additional = task[8:].strip()
            try:
                tokens = int(additional)
            except ValueError:
                tokens = self.estimate_tokens(additional)

            return {"operation": "predict", **self.predict_overflow(tokens)}

        elif task_lower.startswith("compress"):
            # Parse target percent
            match = re.search(r"(\d+)%", task)
            target = float(match.group(1)) if match else None
            aggressive = "aggressive" in task_lower

            result = self.compress(target_percent=target, aggressive=aggressive)
            return {
                "operation": "compress",
                "original_tokens": result.original_tokens,
                "compressed_tokens": result.compressed_tokens,
                "segments_compressed": result.segments_compressed,
                "segments_archived": result.segments_archived,
                "savings_percent": result.savings_percent,
            }

        elif task_lower.startswith("recover:"):
            query = task[8:].strip()
            recovered = self.recover(query)
            if recovered:
                return {
                    "operation": "recover",
                    "found": True,
                    "id": recovered.id,
                    "summary": recovered.summary,
                    "original_tokens": recovered.original_tokens,
                    "archived_at": recovered.archived_at.isoformat(),
                }
            return {"operation": "recover", "found": False, "query": query}

        else:
            return {
                "operation": "unknown",
                "error": f"Unknown command: {task}",
                "available": [
                    "status",
                    "predict:<tokens>",
                    "compress [--target N%]",
                    "recover:<query>",
                ],
            }


def main():
    parser = argparse.ArgumentParser(description="Context Guardian - Gestion de context window")
    parser.add_argument(
        "command", nargs="?", default="status", help="Comando (status, predict, compress, recover)"
    )
    parser.add_argument("--model", default="claude-sonnet-4", help="Modelo LLM")
    parser.add_argument("--json", action="store_true", help="Output JSON")

    args = parser.parse_args()

    guardian = ContextGuardian(model=args.model)

    # Simular contexto para demo
    guardian.add_segment("System prompt with instructions...", "system", ContextPriority.CRITICAL)
    guardian.add_segment("User asked about authentication...", "user")
    guardian.add_segment(
        "Here is the auth implementation code...", "code", ContextPriority.IMPORTANT
    )
    guardian.add_segment(
        "Some older context that is not very relevant anymore...",
        "context",
        ContextPriority.ARCHIVABLE,
    )

    result = guardian.execute(args.command)

    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        op = result.get("operation", "unknown")

        if op == "status":
            usage = result["usage_percent"]
            status_icon = "✓" if usage < 70 else ("⚠" if usage < 90 else "✗")
            print(f"[{status_icon}] Context Guardian Status")
            print("=" * 40)
            print(
                f"Uso: {result['total_tokens']:,} / {result['max_tokens']:,} tokens ({usage:.1f}%)"
            )
            print(f"Segmentos: {result['segments_count']} ({result['critical_count']} criticos)")
            print(f"Archivados: {result['archived_count']}")
            print(f"\n{result['recommendation']}")

        elif op == "predict":
            status = "OK" if not result["will_overflow"] else "OVERFLOW"
            print(f"Prediccion: {status}")
            print(f"Actual: {result['current_tokens']:,} tokens")
            print(f"Adicional: {result['additional_tokens']:,} tokens")
            print(
                f"Proyectado: {result['projected_tokens']:,} tokens ({result['projected_percent']:.1f}%)"
            )
            print(f"\n{result['recommendation']}")

        elif op == "compress":
            print("Compresion completada")
            print(f"Antes: {result['original_tokens']:,} tokens")
            print(f"Despues: {result['compressed_tokens']:,} tokens")
            print(f"Ahorro: {result['savings_percent']:.1f}%")
            print(
                f"Comprimidos: {result['segments_compressed']}, Archivados: {result['segments_archived']}"
            )

        elif op == "recover":
            if result["found"]:
                print(f"Contexto recuperado: {result['id']}")
                print(f"Resumen: {result['summary'][:100]}...")
            else:
                print(f"No se encontro contexto para: {result['query']}")

        else:
            print(f"Error: {result.get('error', 'Unknown')}")

    sys.exit(0)


if __name__ == "__main__":
    main()
