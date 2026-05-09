"""
Intelligence Hub - Coordinador Central de Inteligencia

Conecta TODOS los sistemas de inteligencia en un unico punto de entrada:
- Memory Replay (decisiones, patrones, errores de proyectos anteriores)
- Self-Improvement (metricas de ejecucion, propuestas de mejora)
- Skill Marketplace (ranking, recomendaciones)
- Learning Loop (patrones de exito/error por interaccion)
- Autonomous Learning (pipeline de aprendizaje batch)
- Metrics Collector (metricas de agentes)
- Feedback (retroalimentacion del usuario)
- Quality Scorer (evaluacion de outputs)

Flujo:
  PRE-EJECUCION:  query_intelligence(task) -> IntelligenceContext
  SELECCION:      rank_agents(task, candidates) -> list[RankedAgent]
  SELECCION:      rank_skills(task, candidates) -> list[RankedSkill]
  POST-EJECUCION: record_outcome(task, result) -> None

v1.0.0 - 2026-02-13
"""
# mypy: ignore-errors

from __future__ import annotations

import asyncio
import hashlib
import json
import logging

logger = logging.getLogger(__name__)

from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class AgentPerformance:
    """Rendimiento historico de un agente para un tipo de tarea."""

    agent_name: str
    task_type: str
    executions: int = 0
    successes: int = 0
    avg_quality: float = 0.0
    avg_duration_ms: float = 0.0
    last_used: str = ""
    error_types: dict[str, int] = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        return self.successes / self.executions if self.executions > 0 else 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["success_rate"] = self.success_rate
        return d


@dataclass
class SkillEffectiveness:
    """Efectividad historica de un skill para un tipo de tarea."""

    skill_name: str
    task_type: str
    uses: int = 0
    successes: int = 0
    avg_quality: float = 0.0
    user_ratings: list[float] = field(default_factory=list)
    last_used: str = ""

    @property
    def success_rate(self) -> float:
        return self.successes / self.uses if self.uses > 0 else 0.0

    @property
    def avg_rating(self) -> float:
        return sum(self.user_ratings) / len(self.user_ratings) if self.user_ratings else 0.0

    @property
    def composite_score(self) -> float:
        """Score compuesto: 40% success_rate + 30% quality + 30% rating."""
        rating_norm = self.avg_rating / 5.0 if self.avg_rating > 0 else 0.5
        return (self.success_rate * 0.4) + (self.avg_quality * 0.3) + (rating_norm * 0.3)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["success_rate"] = self.success_rate
        d["avg_rating"] = self.avg_rating
        d["composite_score"] = self.composite_score
        return d


@dataclass
class RankedAgent:
    """Agente rankeado con justificacion."""

    agent_name: str
    score: float
    reasons: list[str] = field(default_factory=list)
    historical_success_rate: float = 0.0
    task_affinity: float = 0.0
    recency_bonus: float = 0.0


@dataclass
class RankedSkill:
    """Skill rankeado con justificacion."""

    skill_name: str
    score: float
    reasons: list[str] = field(default_factory=list)
    historical_effectiveness: float = 0.0
    task_affinity: float = 0.0


@dataclass
class IntelligenceContext:
    """Contexto completo de inteligencia pre-ejecucion."""

    task: str
    task_type: str
    relevant_decisions: list[dict] = field(default_factory=list)
    relevant_patterns: list[dict] = field(default_factory=list)
    relevant_errors: list[dict] = field(default_factory=list)
    learned_avoidances: list[dict] = field(default_factory=list)
    suggested_agents: list[RankedAgent] = field(default_factory=list)
    suggested_skills: list[RankedSkill] = field(default_factory=list)
    user_preferences: dict[str, Any] = field(default_factory=dict)
    risk_level: float = 0.0
    confidence: float = 0.0

    def to_dict(self) -> dict:
        result = {
            "task": self.task,
            "task_type": self.task_type,
            "relevant_decisions": self.relevant_decisions,
            "relevant_patterns": self.relevant_patterns,
            "relevant_errors": self.relevant_errors,
            "learned_avoidances": self.learned_avoidances,
            "suggested_agents": [asdict(a) for a in self.suggested_agents],
            "suggested_skills": [asdict(s) for s in self.suggested_skills],
            "user_preferences": self.user_preferences,
            "risk_level": self.risk_level,
            "confidence": self.confidence,
        }
        return result


# ---------------------------------------------------------------------------
# Task Classification
# ---------------------------------------------------------------------------

TASK_TYPE_KEYWORDS: dict[str, list[str]] = {
    "frontend": ["ui", "frontend", "react", "css", "tailwind", "component", "page", "layout"],
    "backend": ["api", "backend", "server", "endpoint", "rest", "graphql", "database", "query"],
    "testing": ["test", "testing", "spec", "coverage", "e2e", "unit", "integration"],
    "security": ["security", "auth", "vulnerability", "owasp", "penetration", "audit"],
    "devops": ["deploy", "docker", "ci", "cd", "pipeline", "kubernetes", "infra"],
    "refactoring": ["refactor", "clean", "restructure", "simplify", "optimize", "modularize"],
    "debugging": ["bug", "fix", "error", "debug", "crash", "issue", "broken"],
    "documentation": ["docs", "readme", "documentation", "comment", "explain"],
    "data": ["excel", "csv", "data", "migration", "import", "export", "etl", "database"],
    "mobile": ["mobile", "ios", "android", "react native", "flutter"],
    "design": ["design", "figma", "wireframe", "prototype", "ux", "accessibility"],
    "architecture": ["architecture", "system design", "scalable", "microservice", "pattern"],
    "ml": ["ml", "machine learning", "model", "training", "prediction", "ai"],
    "uns_enterprise": ["payroll", "haken", "uns", "dispatch", "contract", "japanese"],
}


def classify_task(task: str) -> str:
    """Clasifica una tarea por tipo usando keywords."""
    task_lower = task.lower()
    scores: dict[str, int] = {}
    for task_type, keywords in TASK_TYPE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in task_lower)
        if score > 0:
            scores[task_type] = score
    if not scores:
        return "general"
    return max(scores, key=scores.get)


# ---------------------------------------------------------------------------
# Intelligence Hub
# ---------------------------------------------------------------------------


class IntelligenceHub:
    """Coordinador central que conecta todos los sistemas de inteligencia.

    Proporciona:
    - Pre-ejecucion: contexto completo basado en memoria e historia
    - Seleccion: ranking de agentes y skills basado en datos reales
    - Post-ejecucion: distribuye resultados a todos los sistemas de aprendizaje
    """

    def __init__(self, project_root: str | None = None):
        self._root = Path(project_root) if project_root else Path(".")
        # PRIMARIO: ~/.antigravity/projects/<hash>/intelligence/
        resolved = str(self._root.resolve())
        project_hash = hashlib.sha256(resolved.encode()).hexdigest()[:16]
        self._data_dir = Path.home() / ".antigravity" / "projects" / project_hash / "intelligence"
        self._data_dir.mkdir(parents=True, exist_ok=True)

        # SECUNDARIO: <proyecto>/.antigravity/intelligence/ (visible para otras IAs)
        self._project_data_dir = self._root.resolve() / ".antigravity" / "intelligence"
        self._project_data_dir.mkdir(parents=True, exist_ok=True)

        # Performance tracking (loaded lazily)
        self._agent_perf: dict[str, AgentPerformance] = {}
        self._skill_eff: dict[str, SkillEffectiveness] = {}
        self._loaded = False

        # Load existing performance data eagerly (fast: JSON from disk)
        self._load_performance_data()
        self._loaded = True

        # Subsystems (loaded lazily to avoid import errors)
        self._memory_replay = None
        self._learning_loop = None
        self._self_improver = None
        self._metrics_collector = None
        self._feedback_collector = None
        self._context7_enhancer = None

    # -----------------------------------------------------------------------
    # Lazy loading
    # -----------------------------------------------------------------------

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._load_performance_data()
        self._loaded = True

    def _load_from_dir(self, directory: Path, filename: str, cls: type, target: dict) -> None:
        """Carga datos desde un directorio y los fusiona en target."""
        filepath = directory / filename
        if not filepath.exists():
            return
        try:
            data = json.loads(filepath.read_text(encoding="utf-8"))
            for key, val in data.items():
                if key not in target:
                    target[key] = cls(**val)
        except Exception as e:
            logger.warning("Error cargando %s de %s: %s", filename, directory, e)

    def _load_performance_data(self) -> None:
        """Carga datos historicos de performance, fusionando home y proyecto."""
        # Primario: home
        self._load_from_dir(
            self._data_dir, "agent_performance.json", AgentPerformance, self._agent_perf
        )
        self._load_from_dir(
            self._data_dir, "skill_effectiveness.json", SkillEffectiveness, self._skill_eff
        )
        # Secundario: proyecto (agrega lo que no exista en home)
        self._load_from_dir(
            self._project_data_dir, "agent_performance.json", AgentPerformance, self._agent_perf
        )
        self._load_from_dir(
            self._project_data_dir, "skill_effectiveness.json", SkillEffectiveness, self._skill_eff
        )

    def _save_to_dir(self, directory: Path, filename: str, content: str) -> None:
        """Guarda contenido en un directorio."""
        try:
            (directory / filename).write_text(content, encoding="utf-8")
        except OSError as e:
            logger.debug("No se pudo guardar %s en %s: %s", filename, directory, e)

    def _save_performance_data(self) -> None:
        """Persiste datos de performance en AMBAS ubicaciones (home + proyecto)."""
        agent_data = {k: v.to_dict() for k, v in self._agent_perf.items()}
        skill_data = {k: v.to_dict() for k, v in self._skill_eff.items()}

        # Remove computed properties before saving
        for v in agent_data.values():
            v.pop("success_rate", None)
        for v in skill_data.values():
            v.pop("success_rate", None)
            v.pop("avg_rating", None)
            v.pop("composite_score", None)

        agent_json = json.dumps(agent_data, indent=2, default=str)
        skill_json = json.dumps(skill_data, indent=2, default=str)

        # Guardar en home (primario)
        self._save_to_dir(self._data_dir, "agent_performance.json", agent_json)
        self._save_to_dir(self._data_dir, "skill_effectiveness.json", skill_json)
        # Guardar en proyecto (secundario, para otras IAs)
        self._save_to_dir(self._project_data_dir, "agent_performance.json", agent_json)
        self._save_to_dir(self._project_data_dir, "skill_effectiveness.json", skill_json)

    def _get_memory_replay(self) -> Any:
        if self._memory_replay is None:
            try:
                from .memory_replay import get_memory_replay

                self._memory_replay = get_memory_replay()
            except ImportError:
                logger.debug("MemoryReplay no disponible")
        return self._memory_replay

    def _get_learning_loop(self) -> Any:
        if self._learning_loop is None:
            try:
                from .learning_loop import get_learning_loop

                self._learning_loop = get_learning_loop(str(self._root))
            except ImportError:
                logger.debug("LearningLoop no disponible")
        return self._learning_loop

    def _get_self_improver(self) -> Any:
        if self._self_improver is None:
            try:
                from .self_improvement import get_self_improver

                self._self_improver = get_self_improver()
            except ImportError:
                logger.debug("SelfImprover no disponible")
        return self._self_improver

    def _get_metrics_collector(self) -> Any:
        if self._metrics_collector is None:
            try:
                from .metrics_collector import get_metrics_collector

                self._metrics_collector = get_metrics_collector()
            except ImportError:
                logger.debug("MetricsCollector no disponible")
        return self._metrics_collector

    def _get_project_memory(self) -> Any:
        if not hasattr(self, "_project_memory"):
            self._project_memory = None
        if self._project_memory is None:
            try:
                from .project_memory import get_project_memory

                self._project_memory = get_project_memory(str(self._root))
            except ImportError:
                logger.debug("ProjectMemory no disponible")
        return self._project_memory

    def _get_context7_enhancer(self) -> Any:
        """Lazy-load del enhancer Context7 para enriquecimiento documental."""
        if self._context7_enhancer is None:
            try:
                from .intelligence.context7_enhanced import get_context7_enhancer

                cache_path = self._root / ".agent" / "memory" / "context7_cache"
                self._context7_enhancer = get_context7_enhancer(cache_path)
            except Exception as e:
                logger.debug("Context7Enhancer no disponible: %s", e)
                self._context7_enhancer = False
        return self._context7_enhancer if self._context7_enhancer is not False else None

    def _enrich_with_context7(self, task: str, ctx: IntelligenceContext) -> None:
        """Enriquece contexto con librerías detectadas y docs cacheadas de Context7."""
        enhancer = self._get_context7_enhancer()
        if enhancer is None:
            return
        try:
            detected = enhancer.detect_libraries(task)
            if not detected:
                return

            ctx.relevant_patterns.append(
                {
                    "name": "context7_libraries_detected",
                    "description": f"Librerías detectadas: {', '.join(detected[:5])}",
                    "context": "context7_enhanced",
                    "benefits": ["Documentación oficial y snippets actualizados"],
                }
            )

            cached = enhancer.search_cache(task, limit=3)
            for doc in cached:
                ctx.relevant_patterns.append(
                    {
                        "name": f"context7_cache:{doc.library_id}",
                        "description": doc.query[:160],
                        "context": "context7_cache",
                        "benefits": [f"{len(doc.code_examples)} ejemplos de código"],
                    }
                )

            # Auto-fetch no bloqueante para futuras consultas.
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(enhancer.auto_fetch(task, max_results=2, max_tokens=2000))
            except RuntimeError:
                asyncio.run(enhancer.auto_fetch(task, max_results=2, max_tokens=2000))
        except Exception as e:
            logger.debug("Error enriqueciendo contexto con Context7: %s", e)

    # -----------------------------------------------------------------------
    # PRE-EJECUCION: Obtener contexto de inteligencia
    # -----------------------------------------------------------------------

    def query_intelligence(
        self, task: str, tech_stack: list[str] | None = None
    ) -> IntelligenceContext:
        """Consulta TODOS los sistemas de inteligencia antes de ejecutar una tarea.

        Args:
            task: Descripcion de la tarea
            tech_stack: Stack tecnologico relevante

        Returns:
            IntelligenceContext con todo el conocimiento previo relevante
        """
        self._ensure_loaded()
        task_type = classify_task(task)
        ctx = IntelligenceContext(task=task, task_type=task_type)

        # 1. Consultar Memory Replay (proyectos anteriores)
        memory_replay = self._get_memory_replay()
        if memory_replay:
            try:
                recalls = memory_replay.recall(task, tech_stack=tech_stack or [], top_k=3)
                for recall in recalls:
                    ctx.relevant_decisions.extend(
                        [
                            {
                                "description": d.description,
                                "chosen": d.chosen_option,
                                "reasoning": d.reasoning,
                                "outcome": d.outcome,
                            }
                            for d in getattr(recall, "relevant_decisions", [])
                        ]
                    )
                    ctx.relevant_patterns.extend(
                        [
                            {
                                "name": p.name,
                                "description": p.description,
                                "context": p.context,
                                "benefits": p.benefits,
                            }
                            for p in getattr(recall, "relevant_patterns", [])
                        ]
                    )
                    ctx.relevant_errors.extend(
                        [
                            {
                                "description": e.description,
                                "root_cause": e.root_cause,
                                "resolution": e.resolution,
                                "prevention": e.prevention,
                            }
                            for e in getattr(recall, "relevant_errors", [])
                        ]
                    )
            except Exception as e:
                logger.debug("Error consultando MemoryReplay: %s", e)

        # 2. Consultar Learning Loop (avoidances y correcciones)
        learning_loop = self._get_learning_loop()
        if learning_loop:
            try:
                should_avoid, reason = learning_loop.should_avoid(task)
                if should_avoid:
                    ctx.learned_avoidances.append(
                        {
                            "action": task,
                            "reason": reason,
                        }
                    )
                hint = learning_loop.get_correction_hint(task)
                if hint:
                    ctx.learned_avoidances.append(
                        {
                            "action": task,
                            "correction": hint,
                        }
                    )
            except Exception as e:
                logger.debug("Error consultando LearningLoop: %s", e)

        # 3. Consultar Project Memory (errores conocidos, decisiones, CI health)
        project_memory = self._get_project_memory()
        if project_memory:
            try:
                pm_context = project_memory.get_context_for_task(task)
                # Errores conocidos del proyecto
                for err in pm_context.get("known_errors", []):
                    ctx.relevant_errors.append(
                        {
                            "description": err.get("pattern", ""),
                            "root_cause": "",
                            "resolution": err.get("resolution", ""),
                            "prevention": err.get("prevention", ""),
                            "source": "project_memory",
                        }
                    )
                # Decisiones previas del proyecto
                for dec in pm_context.get("relevant_decisions", []):
                    ctx.relevant_decisions.append(
                        {
                            "description": dec.get("description", ""),
                            "chosen": dec.get("chosen", ""),
                            "reasoning": dec.get("reasoning", ""),
                            "outcome": dec.get("outcome", ""),
                            "source": "project_memory",
                        }
                    )
                # CI health afecta risk level
                ci_status = pm_context.get("ci_health", {}).get("status", "")
                if ci_status == "unhealthy":
                    ctx.risk_level = max(ctx.risk_level, 0.7)
                elif ci_status == "degraded":
                    ctx.risk_level = max(ctx.risk_level, 0.4)
            except Exception as e:
                logger.debug("Error consultando ProjectMemory: %s", e)

        # 4. Calcular risk level basado en errores previos
        if ctx.relevant_errors:
            ctx.risk_level = max(ctx.risk_level, min(1.0, len(ctx.relevant_errors) * 0.2))

        # 5. Calcular confidence basado en patrones exitosos
        if ctx.relevant_patterns:
            ctx.confidence = min(1.0, len(ctx.relevant_patterns) * 0.25)

        # 6. Enriquecer con contexto documental de Context7 (si aplica)
        self._enrich_with_context7(task, ctx)

        logger.info(
            "IntelligenceContext para '%s': tipo=%s, decisiones=%d, patrones=%d, "
            "errores=%d, avoidances=%d, risk=%.2f, confidence=%.2f",
            task[:50],
            task_type,
            len(ctx.relevant_decisions),
            len(ctx.relevant_patterns),
            len(ctx.relevant_errors),
            len(ctx.learned_avoidances),
            ctx.risk_level,
            ctx.confidence,
        )
        return ctx

    # -----------------------------------------------------------------------
    # SELECCION: Ranking inteligente de agentes
    # -----------------------------------------------------------------------

    def rank_agents(
        self,
        task: str,
        candidates: list[dict[str, Any]],
        top_k: int = 5,
    ) -> list[RankedAgent]:
        """Rankea agentes candidatos usando datos historicos de performance.

        Args:
            task: Descripcion de la tarea
            candidates: Lista de dicts con al menos 'name' y opcionalmente
                       'tier', 'skills', 'description'
            top_k: Cuantos devolver

        Returns:
            Lista de RankedAgent ordenados por score descendente
        """
        self._ensure_loaded()
        task_type = classify_task(task)
        task_lower = task.lower()
        now = datetime.now()
        ranked: list[RankedAgent] = []

        for candidate in candidates:
            name = candidate.get("name", "unknown")
            tier = candidate.get("tier", 5)
            skills = candidate.get("skills", [])
            description = candidate.get("description", "")

            reasons: list[str] = []
            score = 0.0

            # --- Factor 1: Historical performance (0-0.35) ---
            perf_key = f"{name}:{task_type}"
            perf = self._agent_perf.get(perf_key)
            historical_sr = 0.5  # default neutral
            if perf and perf.executions >= 3:
                historical_sr = perf.success_rate
                quality_factor = perf.avg_quality
                perf_score = (historical_sr * 0.6 + quality_factor * 0.4) * 0.35
                score += perf_score
                reasons.append(
                    f"Historial: {perf.executions} ejecuciones, "
                    f"{historical_sr:.0%} exito, {quality_factor:.1f} calidad"
                )
            else:
                # Sin historial: bonus por ser nuevo (exploration bonus)
                score += 0.15
                reasons.append("Sin historial previo (exploration bonus)")

            # --- Factor 2: Skill match (0-0.30) ---
            skill_match = 0.0
            task_keywords = set(task_lower.split())
            if skills:
                matching = sum(1 for s in skills if s.lower() in task_lower)
                skill_match = min(1.0, matching / max(len(skills), 1))
            # Also check description
            if description:
                desc_words = set(description.lower().split())
                overlap = len(task_keywords & desc_words)
                skill_match = max(skill_match, min(1.0, overlap / max(len(task_keywords), 1)))

            score += skill_match * 0.30
            if skill_match > 0.3:
                reasons.append(f"Afinidad con tarea: {skill_match:.0%}")

            # --- Factor 3: Tier priority (0-0.15) ---
            tier_score = max(0, (7 - tier)) / 6.0  # tier 1=1.0, tier 6=0.17
            score += tier_score * 0.15
            if tier <= 2:
                reasons.append(f"Tier {tier} (alta prioridad)")

            # --- Factor 4: Recency bonus (0-0.10) ---
            recency_bonus = 0.0
            if perf and perf.last_used:
                try:
                    last = datetime.fromisoformat(perf.last_used)
                    days_ago = (now - last).days
                    if days_ago < 7:
                        recency_bonus = 0.10
                        reasons.append("Usado recientemente (< 7 dias)")
                    elif days_ago < 30:
                        recency_bonus = 0.05
                except (ValueError, TypeError):
                    pass
            score += recency_bonus

            # --- Factor 5: Error penalty (0 to -0.15) ---
            if perf and perf.error_types:
                total_errors = sum(perf.error_types.values())
                error_rate = total_errors / max(perf.executions, 1)
                error_penalty = min(0.15, error_rate * 0.15 + total_errors * 0.01)
                score -= error_penalty
                if error_penalty > 0.03:
                    reasons.append(
                        f"Penalizacion por {total_errors} errores previos ({error_rate:.0%} tasa)"
                    )

            ranked.append(
                RankedAgent(
                    agent_name=name,
                    score=round(max(0.0, min(1.0, score)), 3),
                    reasons=reasons,
                    historical_success_rate=historical_sr,
                    task_affinity=skill_match,
                    recency_bonus=recency_bonus,
                )
            )

        ranked.sort(key=lambda r: r.score, reverse=True)
        return ranked[:top_k]

    # -----------------------------------------------------------------------
    # SELECCION: Ranking inteligente de skills
    # -----------------------------------------------------------------------

    def rank_skills(
        self,
        task: str,
        candidates: list[str],
        top_k: int = 5,
    ) -> list[RankedSkill]:
        """Rankea skills candidatos usando datos historicos de efectividad.

        Args:
            task: Descripcion de la tarea
            candidates: Lista de nombres de skills
            top_k: Cuantos devolver

        Returns:
            Lista de RankedSkill ordenados por score descendente
        """
        self._ensure_loaded()
        task_type = classify_task(task)
        task_lower = task.lower()
        ranked: list[RankedSkill] = []

        for skill_name in candidates:
            reasons: list[str] = []
            score = 0.0

            # --- Factor 1: Historical effectiveness (0-0.40) ---
            eff_key = f"{skill_name}:{task_type}"
            eff = self._skill_eff.get(eff_key)
            historical_eff = 0.5
            if eff and eff.uses >= 2:
                historical_eff = eff.composite_score
                score += historical_eff * 0.40
                reasons.append(
                    f"Efectividad historica: {eff.uses} usos, "
                    f"{eff.success_rate:.0%} exito, calidad {eff.avg_quality:.1f}"
                )
            else:
                score += 0.20  # Exploration bonus
                reasons.append("Sin historial (exploration bonus)")

            # --- Factor 2: Name/keyword affinity (0-0.35) ---
            name_parts = set(skill_name.replace("-", " ").replace("_", " ").lower().split())
            task_words = set(task_lower.split())
            overlap = len(name_parts & task_words)
            affinity = min(1.0, overlap / max(len(name_parts), 1))
            score += affinity * 0.35
            if affinity > 0.3:
                reasons.append(f"Afinidad de nombre: {affinity:.0%}")

            # --- Factor 3: Task type match (0-0.25) ---
            type_keywords = TASK_TYPE_KEYWORDS.get(task_type, [])
            type_overlap = sum(1 for kw in type_keywords if kw in skill_name.lower())
            type_match = min(1.0, type_overlap / max(len(type_keywords), 1))
            score += type_match * 0.25
            if type_match > 0:
                reasons.append(f"Match con tipo '{task_type}': {type_match:.0%}")

            ranked.append(
                RankedSkill(
                    skill_name=skill_name,
                    score=round(max(0.0, min(1.0, score)), 3),
                    reasons=reasons,
                    historical_effectiveness=historical_eff,
                    task_affinity=affinity,
                )
            )

        ranked.sort(key=lambda r: r.score, reverse=True)
        return ranked[:top_k]

    # -----------------------------------------------------------------------
    # POST-EJECUCION: Registrar resultado en todos los sistemas
    # -----------------------------------------------------------------------

    def record_outcome(
        self,
        task: str,
        agent_name: str,
        success: bool,
        quality_score: float = 0.0,
        duration_ms: int = 0,
        skills_used: list[str] | None = None,
        error_type: str | None = None,
        user_rating: float | None = None,
        corrections: str | None = None,
    ) -> None:
        """Registra el resultado de una ejecucion en TODOS los sistemas.

        Este metodo es el punto central que alimenta el aprendizaje:
        - Actualiza performance de agentes
        - Actualiza efectividad de skills
        - Alimenta el Learning Loop
        - Alimenta el Self-Improver
        - Alimenta el Metrics Collector
        """
        self._ensure_loaded()
        task_type = classify_task(task)
        now_str = datetime.now().isoformat()

        # 1. Actualizar agent performance
        perf_key = f"{agent_name}:{task_type}"
        perf = self._agent_perf.get(perf_key)
        if perf is None:
            perf = AgentPerformance(agent_name=agent_name, task_type=task_type)
            self._agent_perf[perf_key] = perf

        perf.executions += 1
        if success:
            perf.successes += 1
        perf.avg_quality = (
            perf.avg_quality * (perf.executions - 1) + quality_score
        ) / perf.executions
        perf.avg_duration_ms = (
            perf.avg_duration_ms * (perf.executions - 1) + duration_ms
        ) / perf.executions
        perf.last_used = now_str
        if error_type:
            perf.error_types[error_type] = perf.error_types.get(error_type, 0) + 1

        # 2. Actualizar skill effectiveness
        for skill in skills_used or []:
            eff_key = f"{skill}:{task_type}"
            eff = self._skill_eff.get(eff_key)
            if eff is None:
                eff = SkillEffectiveness(skill_name=skill, task_type=task_type)
                self._skill_eff[eff_key] = eff

            eff.uses += 1
            if success:
                eff.successes += 1
            eff.avg_quality = (eff.avg_quality * (eff.uses - 1) + quality_score) / eff.uses
            eff.last_used = now_str
            if user_rating is not None:
                eff.user_ratings.append(user_rating)
                # Keep only last 50 ratings
                if len(eff.user_ratings) > 50:
                    eff.user_ratings = eff.user_ratings[-50:]

        # 3. Alimentar Learning Loop
        learning_loop = self._get_learning_loop()
        if learning_loop:
            try:
                from .learning_loop import OutcomeType

                event_id = learning_loop.record_action(
                    task, {"agent": agent_name, "task_type": task_type}
                )
                if corrections:
                    outcome = OutcomeType.CORRECTED
                elif success:
                    outcome = OutcomeType.SUCCESS
                else:
                    outcome = OutcomeType.FAILED
                learning_loop.record_outcome(event_id, outcome, correction=corrections or None)
            except Exception as e:
                logger.debug("Error alimentando LearningLoop: %s", e)

        # 4. Alimentar Self-Improver
        self_improver = self._get_self_improver()
        if self_improver:
            try:
                self_improver.record_execution(
                    agent_name=agent_name,
                    task_type=task_type,
                    success=success,
                    duration_ms=duration_ms,
                    quality_score=quality_score,
                    retries=0,
                    errors=[error_type] if error_type else [],
                )
            except Exception as e:
                logger.debug("Error alimentando SelfImprover: %s", e)

        # 5. Alimentar Metrics Collector
        metrics = self._get_metrics_collector()
        if metrics:
            try:
                metrics.track_agent_invocation(agent_name, success, duration_ms)
                if error_type:
                    metrics.track_error(error_type, f"Agent {agent_name}: {task[:100]}")
            except Exception as e:
                logger.debug("Error alimentando MetricsCollector: %s", e)

        # 6. Alimentar Project Memory (errores recurrentes)
        project_memory = self._get_project_memory()
        if project_memory and error_type:
            try:
                project_memory.record_error(
                    pattern=f"{agent_name}:{error_type}",
                    resolution=corrections or "",
                    files_affected=[],
                )
            except Exception as e:
                logger.debug("Error alimentando ProjectMemory: %s", e)

        # 7. Persistir
        self._save_performance_data()

        logger.info(
            "Outcome registrado: agent=%s, task_type=%s, success=%s, "
            "quality=%.2f, duration=%dms, skills=%s",
            agent_name,
            task_type,
            success,
            quality_score,
            duration_ms,
            skills_used,
        )

    # -----------------------------------------------------------------------
    # REPORTES: Dashboards de inteligencia
    # -----------------------------------------------------------------------

    def get_agent_leaderboard(
        self, task_type: str | None = None, min_executions: int = 3
    ) -> list[dict]:
        """Devuelve ranking de agentes por performance.

        Args:
            task_type: Filtrar por tipo de tarea (None = todos)
            min_executions: Minimo de ejecuciones para aparecer

        Returns:
            Lista ordenada de agentes con metricas
        """
        self._ensure_loaded()
        agents: list[dict] = []

        for key, perf in self._agent_perf.items():
            if perf.executions < min_executions:
                continue
            if task_type and perf.task_type != task_type:
                continue
            agents.append(perf.to_dict())

        agents.sort(key=lambda a: a.get("success_rate", 0), reverse=True)
        return agents

    def get_skill_leaderboard(self, task_type: str | None = None, min_uses: int = 2) -> list[dict]:
        """Devuelve ranking de skills por efectividad.

        Args:
            task_type: Filtrar por tipo de tarea (None = todos)
            min_uses: Minimo de usos para aparecer

        Returns:
            Lista ordenada de skills con metricas
        """
        self._ensure_loaded()
        skills: list[dict] = []

        for key, eff in self._skill_eff.items():
            if eff.uses < min_uses:
                continue
            if task_type and eff.task_type != task_type:
                continue
            skills.append(eff.to_dict())

        skills.sort(key=lambda s: s.get("composite_score", 0), reverse=True)
        return skills

    def get_intelligence_report(self) -> dict:
        """Reporte completo del estado de inteligencia del ecosistema."""
        self._ensure_loaded()

        total_agent_executions = sum(p.executions for p in self._agent_perf.values())
        total_skill_uses = sum(s.uses for s in self._skill_eff.values())

        avg_success = 0.0
        if self._agent_perf:
            rates = [p.success_rate for p in self._agent_perf.values() if p.executions >= 3]
            avg_success = sum(rates) / len(rates) if rates else 0.0

        # Top performers
        top_agents = sorted(
            [p for p in self._agent_perf.values() if p.executions >= 3],
            key=lambda p: p.success_rate,
            reverse=True,
        )[:5]

        top_skills = sorted(
            [s for s in self._skill_eff.values() if s.uses >= 2],
            key=lambda s: s.composite_score,
            reverse=True,
        )[:5]

        # Struggling agents
        struggling = sorted(
            [p for p in self._agent_perf.values() if p.executions >= 3 and p.success_rate < 0.7],
            key=lambda p: p.success_rate,
        )[:5]

        # Task type distribution
        task_types: dict[str, int] = {}
        for perf in self._agent_perf.values():
            task_types[perf.task_type] = task_types.get(perf.task_type, 0) + perf.executions

        report = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_agent_executions": total_agent_executions,
                "total_skill_uses": total_skill_uses,
                "unique_agents_tracked": len({p.agent_name for p in self._agent_perf.values()}),
                "unique_skills_tracked": len({s.skill_name for s in self._skill_eff.values()}),
                "avg_success_rate": round(avg_success, 3),
            },
            "top_agents": [p.to_dict() for p in top_agents],
            "top_skills": [s.to_dict() for s in top_skills],
            "struggling_agents": [p.to_dict() for p in struggling],
            "task_distribution": task_types,
        }

        # Add learning loop insights
        learning_loop = self._get_learning_loop()
        if learning_loop:
            try:
                insights = learning_loop.get_insights()
                report["learning_insights"] = insights
            except Exception:
                logger.exception("Error getting learning insights")

        # Add self-improvement proposals
        self_improver = self._get_self_improver()
        if self_improver:
            try:
                proposals = self_improver.list_proposals(status="PROPOSED")
                report["pending_improvements"] = (
                    len(proposals) if isinstance(proposals, list) else 0
                )
            except Exception:
                logger.exception("Error listing improvement proposals")

        return report

    def get_recommendation(self, task: str) -> dict:
        """Recomendacion completa para una tarea: mejor agente + mejores skills.

        Metodo de conveniencia que combina query_intelligence + rank_agents + rank_skills.
        """
        ctx = self.query_intelligence(task)

        return {
            "task": task,
            "task_type": ctx.task_type,
            "risk_level": ctx.risk_level,
            "confidence": ctx.confidence,
            "warnings": [a["reason"] for a in ctx.learned_avoidances],
            "past_patterns": [p["name"] for p in ctx.relevant_patterns[:3]],
            "past_errors_to_avoid": [e["description"] for e in ctx.relevant_errors[:3]],
        }


# ---------------------------------------------------------------------------
# Singleton por proyecto (soporta multiples proyectos simultaneos via MCP)
# ---------------------------------------------------------------------------

_hub_instances: dict[str, IntelligenceHub] = {}


def get_intelligence_hub(project_root: str | None = None) -> IntelligenceHub:
    """Obtiene la instancia del Intelligence Hub para un proyecto especifico.

    Cada proyecto tiene su propia instancia, identificada por hash del path.
    Esto permite que el MCP server atienda multiples proyectos sin mezclar datos.
    """
    import hashlib as _hl

    root = Path(project_root) if project_root else Path(".")
    key = _hl.sha256(str(root.resolve()).encode()).hexdigest()[:16]
    if key not in _hub_instances:
        _hub_instances[key] = IntelligenceHub(project_root)
    return _hub_instances[key]
