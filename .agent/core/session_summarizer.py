#!/usr/bin/env python3
"""
Session Summarizer - Resumen AI de sesiones de trabajo.

Usa el sistema LLM multi-provider existente para generar resumenes
inteligentes de sesiones de trabajo, basados en las observaciones
capturadas por el ObservationPipeline.

El resumen se almacena en ProjectMemory y en el ObservationStore
para ser inyectado como contexto en futuras sesiones.

Usage:
    from .session_summarizer import get_session_summarizer

    summarizer = get_session_summarizer()

    # Generar resumen de la sesion actual
    summary = await summarizer.summarize_session("session_20260222_143000")

    # Obtener resumenes recientes para context injection
    context = summarizer.get_recent_summaries_context(max_sessions=5)

v1.0.0 - 2026-02-22
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("antigravity.session_summarizer")


# System prompt para el summarizer
SUMMARIZER_SYSTEM_PROMPT = """\
Eres un asistente que resume sesiones de desarrollo de software.
Tu trabajo es crear resumenes concisos y utiles de lo que se hizo
durante una sesion de programacion.

Reglas:
- Resume en espanol
- Maximo 200 palabras
- Estructura: Objetivo, Acciones clave, Archivos modificados, Resultado
- No repitas informacion redundante
- Enfocate en DECISIONES y CAMBIOS, no en lecturas
- Si hubo errores, menciona como se resolvieron
- Usa formato Markdown con headers ##
"""

SUMMARIZER_USER_TEMPLATE = """\
Resume esta sesion de desarrollo:

**Sesion:** {session_id}
**Duracion:** {start_time} a {end_time}
**Total acciones:** {total_observations}
**Tasa de exito:** {success_rate:.0%}

**Archivos modificados ({n_modified}):**
{files_modified}

**Archivos leidos ({n_read}):**
{files_read}

**Herramientas usadas:**
{tools_used}

**Errores encontrados ({n_errors}):**
{errors}

**Observaciones clave:**
{key_observations}
"""


class SessionSummarizer:
    """Genera resumenes AI de sesiones de trabajo.

    Usa el LLMClient existente para generar resumenes comprimidos
    que son utiles como contexto en futuras sesiones.
    """

    def __init__(self, project_root: str | None = None):
        self._root = Path(project_root).resolve() if project_root else Path(".").resolve()
        self._llm_client: Any = None
        self._observation_pipeline: Any = None

    # -----------------------------------------------------------------------
    # Lazy loading
    # -----------------------------------------------------------------------

    def _get_llm_client(self) -> Any:
        """Obtiene el LLMClient (lazy loading)."""
        if self._llm_client is None:
            try:
                from .llm import LLMClient, LLMConfig

                self._llm_client = LLMClient(
                    LLMConfig(
                        max_tokens=1024,
                        temperature=0.3,
                    )
                )
            except ImportError:
                logger.warning("LLMClient no disponible para summarization")
            except Exception as e:
                logger.warning("Error inicializando LLMClient: %s", e)
        return self._llm_client

    def _get_pipeline(self) -> Any:
        """Obtiene el ObservationPipeline (lazy loading)."""
        if self._observation_pipeline is None:
            try:
                from .observation_pipeline import get_observation_pipeline

                self._observation_pipeline = get_observation_pipeline(str(self._root))
            except ImportError:
                logger.warning("ObservationPipeline no disponible")
        return self._observation_pipeline

    # -----------------------------------------------------------------------
    # Core: Summarize
    # -----------------------------------------------------------------------

    async def summarize_session(self, session_id: str) -> str:
        """Genera resumen AI de una sesion.

        Args:
            session_id: ID de la sesion a resumir

        Returns:
            Resumen en formato Markdown
        """
        pipeline = self._get_pipeline()
        if not pipeline:
            return self._generate_fallback_summary(session_id)

        # Obtener datos de la sesion
        observations = pipeline.get_session_observations(session_id)
        if not observations:
            return f"## Sesion {session_id}\nSin observaciones registradas."

        summary_data = pipeline.generate_session_summary(session_id)

        # Intentar resumen con AI
        llm = self._get_llm_client()
        if llm:
            try:
                return await self._generate_ai_summary(summary_data, observations)
            except Exception as e:
                logger.warning("Error generando resumen AI: %s. Usando fallback.", e)

        # Fallback: resumen estructurado sin AI
        return self._generate_structured_summary(summary_data, observations)

    async def _generate_ai_summary(self, summary_data: Any, observations: list) -> str:
        """Genera resumen usando LLM."""
        llm = self._get_llm_client()
        if not llm:
            raise RuntimeError("LLM client not available")

        # Preparar observaciones clave (solo high/critical)
        key_obs = [
            obs.to_context_string() for obs in observations if obs.priority in ("critical", "high")
        ][:20]

        # Formatear prompt
        prompt = SUMMARIZER_USER_TEMPLATE.format(
            session_id=summary_data.session_id,
            start_time=summary_data.start_time[:19],
            end_time=summary_data.end_time[:19],
            total_observations=summary_data.total_observations,
            success_rate=summary_data.success_rate,
            n_modified=len(summary_data.files_modified),
            files_modified="\n".join(f"- {f}" for f in summary_data.files_modified[:15])
            or "Ninguno",
            n_read=len(summary_data.files_read),
            files_read="\n".join(f"- {f}" for f in summary_data.files_read[:10]) or "Ninguno",
            tools_used="\n".join(f"- {t}: {c}x" for t, c in summary_data.tools_used.items()),
            n_errors=len(summary_data.errors),
            errors="\n".join(f"- {e}" for e in summary_data.errors[:5]) or "Ninguno",
            key_observations="\n".join(f"- {o}" for o in key_obs) or "Ninguno",
        )

        response = await llm.generate(
            prompt=prompt,
            system=SUMMARIZER_SYSTEM_PROMPT,
        )

        return response.content

    def _generate_structured_summary(self, summary_data: Any, observations: list) -> str:
        """Genera resumen estructurado sin AI (fallback)."""
        lines = [
            f"## Sesion: {summary_data.session_id}",
            "",
            f"**Periodo:** {summary_data.start_time[:19]} - {summary_data.end_time[:19]}",
            f"**Acciones:** {summary_data.total_observations} | "
            f"**Exito:** {summary_data.success_rate:.0%}",
            "",
        ]

        if summary_data.files_modified:
            lines.append("### Archivos Modificados")
            for f in summary_data.files_modified[:10]:
                lines.append(f"- `{f}`")
            lines.append("")

        if summary_data.tools_used:
            lines.append("### Herramientas")
            for tool, count in sorted(
                summary_data.tools_used.items(), key=lambda x: x[1], reverse=True
            ):
                lines.append(f"- {tool}: {count}x")
            lines.append("")

        if summary_data.errors:
            lines.append("### Errores")
            for err in summary_data.errors[:5]:
                lines.append(f"- {err}")
            lines.append("")

        return "\n".join(lines)

    def _generate_fallback_summary(self, session_id: str) -> str:
        """Resumen minimo cuando no hay pipeline disponible."""
        return f"## Sesion {session_id}\nResumen no disponible (pipeline no inicializado)."

    # -----------------------------------------------------------------------
    # Context for Injection
    # -----------------------------------------------------------------------

    def get_recent_summaries_context(self, max_sessions: int = 5, max_tokens: int = 2000) -> str:
        """Obtiene resumenes recientes formateados para context injection.

        Args:
            max_sessions: Maximo de sesiones a incluir
            max_tokens: Maximo aproximado de tokens

        Returns:
            String formateado con resumenes recientes
        """
        pipeline = self._get_pipeline()
        if not pipeline:
            return ""

        summaries = pipeline._store.get_recent_session_summaries(max_sessions)
        if not summaries:
            return ""

        lines = ["## Sesiones Recientes", ""]
        current_chars = sum(len(l) for l in lines)
        max_chars = max_tokens * 4

        for s in summaries:
            ai_summary = s.get("ai_summary")
            if ai_summary:
                block = ai_summary
            else:
                block = (
                    f"### {s['session_id']}\n"
                    f"- Acciones: {s['total_observations']}\n"
                    f"- Archivos: {', '.join(s.get('files_modified', [])[:5])}\n"
                    f"- Exito: {s.get('success_rate', 1.0):.0%}"
                )

            if current_chars + len(block) > max_chars:
                break

            lines.append(block)
            lines.append("")
            current_chars += len(block)

        return "\n".join(lines)

    # -----------------------------------------------------------------------
    # Batch Summarize
    # -----------------------------------------------------------------------

    async def summarize_pending_sessions(self) -> list[str]:
        """Resume todas las sesiones que no tienen resumen AI.

        Returns:
            Lista de session_ids resumidos
        """
        pipeline = self._get_pipeline()
        if not pipeline:
            return []

        summaries = pipeline._store.get_recent_session_summaries(20)
        summarized: list[str] = []

        for s in summaries:
            if s.get("ai_summary"):
                continue  # Ya tiene resumen

            try:
                ai_summary = await self.summarize_session(s["session_id"])
                # Actualizar en store
                from .observation_pipeline import SessionObservationSummary

                summary_obj = SessionObservationSummary(
                    session_id=s["session_id"],
                    start_time=s.get("start_time", ""),
                    end_time=s.get("end_time", ""),
                    total_observations=s.get("total_observations", 0),
                    files_modified=s.get("files_modified", []),
                    files_read=s.get("files_read", []),
                    tools_used=s.get("tools_used", {}),
                    errors=s.get("errors", []),
                    success_rate=s.get("success_rate", 1.0),
                )
                pipeline._store.store_session_summary(summary_obj, ai_summary)
                summarized.append(s["session_id"])
                logger.info("Sesion %s resumida con AI", s["session_id"])
            except Exception as e:
                logger.warning("Error resumiendo sesion %s: %s", s["session_id"], e)

        return summarized


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_summarizer: SessionSummarizer | None = None


def get_session_summarizer(project_root: str | None = None) -> SessionSummarizer:
    """Obtiene instancia singleton del SessionSummarizer."""
    global _summarizer
    if _summarizer is None:
        _summarizer = SessionSummarizer(project_root)
    return _summarizer
