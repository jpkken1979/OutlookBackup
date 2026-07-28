"""
Intelligent Router — Auto-routing de tareas al mecanismo óptimo.

Analiza cualquier tarea en lenguaje natural y decide automáticamente
la ruta de ejecución óptima:

  - DIRECT: Un solo agente ejecuta la tarea (simple, rápida)
  - AUCTION: Se subasta entre agentes capaces (requiere selección)
  - SWARM: Enjambre multi-agente colabora (tarea compleja, multi-fase)
  - WORKFLOW: Ejecuta un grafo de workflow predefinido (proceso conocido)
  - PLAN: MetaPlanner descompone y orquesta (estrategia con planificación)

El router usa análisis de complejidad basado en:
  - Conteo de verbos de acción (indicador de multi-fase)
  - Presencia de keywords de colaboración
  - Longitud y estructura de la tarea
  - Historial de ejecuciones similares
  - Capabilities requeridas inferidas del texto

Usage:
    router = IntelligentRouter(bus=bus)

    # Analizar y ejecutar automáticamente
    result = await router.route_and_execute(
        "Refactoriza el módulo de autenticación, asegurando seguridad y tests"
    )
    print(result["route"])     # "swarm"
    print(result["reason"])    # "Tarea compleja multi-fase con 3+ dominios"
    print(result["result"])    # Resultado de ejecución

    # Solo analizar sin ejecutar
    analysis = router.analyze("Busca dónde se define la clase UserModel")
    print(analysis["route"])   # "direct"
    print(analysis["agent"])   # "explorer"
"""
# mypy: ignore-errors

import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("antigravity.intelligent_router")


# ============================================================
# Constantes
# ============================================================
ROUTER_CHANNEL = "router.decisions"

# Pesos para el score de complejidad
COMPLEXITY_WEIGHTS = {
    "action_verbs": 0.25,  # Múltiples acciones = más complejo
    "domain_count": 0.30,  # Múltiples dominios = más complejo
    "word_count": 0.15,  # Tareas largas tienden a ser más complejas
    "collaboration_kw": 0.20,  # Keywords de colaboración
    "specificity": 0.10,  # Qué tan específica es la tarea
}


# ============================================================
# Enums
# ============================================================
class RouteType(str, Enum):
    """Tipo de ruta de ejecución."""

    DIRECT = "direct"  # Un agente directo
    AUCTION = "auction"  # Subasta entre agentes
    SWARM = "swarm"  # Enjambre multi-agente
    WORKFLOW = "workflow"  # Grafo de workflow
    PLAN = "plan"  # MetaPlanner


class ComplexityLevel(str, Enum):
    """Nivel de complejidad de una tarea."""

    TRIVIAL = "trivial"  # 0.0 - 0.2
    SIMPLE = "simple"  # 0.2 - 0.4
    MODERATE = "moderate"  # 0.4 - 0.6
    COMPLEX = "complex"  # 0.6 - 0.8
    EPIC = "epic"  # 0.8 - 1.0


# ============================================================
# Modelos
# ============================================================
@dataclass
class RouteDecision:
    """Decisión de routing para una tarea."""

    decision_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task: str = ""
    route: RouteType = RouteType.DIRECT
    complexity: ComplexityLevel = ComplexityLevel.SIMPLE
    complexity_score: float = 0.0
    recommended_agent: str | None = None
    recommended_agents: list[str] = field(default_factory=list)
    required_capabilities: list[str] = field(default_factory=list)
    reason: str = ""
    confidence: float = 0.0
    analysis: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "task": self.task[:200],
            "route": self.route.value,
            "complexity": self.complexity.value,
            "complexity_score": round(self.complexity_score, 3),
            "recommended_agent": self.recommended_agent,
            "recommended_agents": self.recommended_agents,
            "required_capabilities": self.required_capabilities,
            "reason": self.reason,
            "confidence": round(self.confidence, 3),
            "analysis": self.analysis,
            "timestamp": self.timestamp,
        }


@dataclass
class RouteExecution:
    """Resultado de ejecutar una tarea via el router."""

    decision: RouteDecision
    execution_result: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"  # pending, executing, completed, failed
    started_at: float = field(default_factory=time.time)
    completed_at: float | None = None
    duration_seconds: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision.to_dict(),
            "execution_result": self.execution_result,
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
        }


# ============================================================
# Capability Extractor — infiere capabilities del texto
# ============================================================
class CapabilityExtractor:
    """Extrae capabilities requeridas del texto de una tarea."""

    # Mapping: keyword → capability
    KEYWORD_CAPABILITIES: dict[str, list[str]] = {
        # Code analysis
        "analiza": ["code-analysis"],
        "explora": ["code-analysis", "search"],
        "busca": ["search"],
        "encuentra": ["search"],
        "dependencias": ["dependencies"],
        "imports": ["dependencies"],
        # Architecture
        "arquitectura": ["architecture", "design"],
        "diseña": ["design"],
        "estructura": ["architecture"],
        "patrón": ["patterns"],
        "refactoriza": ["code-analysis", "architecture"],
        # Security
        "seguridad": ["security"],
        "vulnerabilidad": ["security", "audit"],
        "audita": ["audit"],
        "penetración": ["security"],
        # Testing
        "test": ["testing"],
        "prueba": ["testing"],
        "coverage": ["testing", "quality"],
        "regresión": ["testing"],
        # Frontend
        "ui": ["frontend", "ui"],
        "componente": ["frontend"],
        "react": ["frontend", "react"],
        "css": ["frontend", "css"],
        "estilo": ["frontend", "css"],
        # Backend
        "api": ["backend", "api"],
        "endpoint": ["backend", "api"],
        "servidor": ["backend"],
        "rest": ["backend", "api"],
        # Database
        "base de datos": ["database"],
        "sql": ["database", "sql"],
        "schema": ["database", "schema"],
        "migración": ["database"],
        # DevOps
        "deploy": ["devops", "infrastructure"],
        "ci": ["devops", "ci-cd"],
        "docker": ["devops"],
        "pipeline": ["devops", "ci-cd"],
        # Performance
        "performance": ["performance"],
        "optimiza": ["performance", "optimization"],
        "lento": ["performance", "profiling"],
        # Documentation
        "documenta": ["documentation"],
        "readme": ["documentation"],
        # ML
        "modelo": ["machine-learning"],
        "entrena": ["machine-learning"],
        "datos": ["data-science"],
    }

    @classmethod
    def extract(cls, task: str) -> list[str]:
        """Extrae capabilities de una tarea en lenguaje natural."""
        task_lower = task.lower()
        capabilities: set[str] = set()

        for keyword, caps in cls.KEYWORD_CAPABILITIES.items():
            if keyword in task_lower:
                capabilities.update(caps)

        return sorted(capabilities)


# ============================================================
# Complexity Analyzer — analiza complejidad de la tarea
# ============================================================
class ComplexityAnalyzer:
    """Analiza la complejidad de una tarea."""

    # Verbos de acción en español e inglés
    ACTION_VERBS = {
        "analiza",
        "explora",
        "busca",
        "refactoriza",
        "implementa",
        "crea",
        "diseña",
        "audita",
        "testea",
        "prueba",
        "despliega",
        "migra",
        "optimiza",
        "documenta",
        "revisa",
        "corrige",
        "integra",
        "configura",
        "valida",
        "evalúa",
        "investiga",
        "arregla",
        "mejora",
        "agrega",
        "elimina",
        "actualiza",
        "analyze",
        "explore",
        "search",
        "refactor",
        "implement",
        "create",
        "design",
        "audit",
        "test",
        "deploy",
        "migrate",
        "optimize",
        "document",
        "review",
        "fix",
        "integrate",
    }

    # Keywords que indican colaboración/complejidad
    COLLABORATION_KEYWORDS = {
        "asegurando",
        "verificando",
        "incluyendo",
        "además",
        "también",
        "después",
        "luego",
        "finalmente",
        "y luego",
        "para que",
        "de modo que",
        "junto con",
        "coordinando",
        "colaborando",
        "completo",
        "integral",
        "exhaustivo",
        "profundo",
    }

    # Dominios técnicos
    DOMAIN_KEYWORDS: dict[str, str] = {
        "seguridad": "security",
        "security": "security",
        "test": "testing",
        "prueba": "testing",
        "arquitectura": "architecture",
        "diseño": "architecture",
        "frontend": "frontend",
        "ui": "frontend",
        "backend": "backend",
        "api": "backend",
        "base de datos": "database",
        "database": "database",
        "performance": "performance",
        "rendimiento": "performance",
        "deploy": "devops",
        "ci": "devops",
        "docker": "devops",
        "documenta": "docs",
    }

    @classmethod
    def analyze(cls, task: str) -> dict[str, Any]:
        """Analiza la complejidad de una tarea."""
        task_lower = task.lower()
        words = task_lower.split()

        # Contar verbos de acción
        action_count = sum(1 for w in words if w.rstrip(".,;:") in cls.ACTION_VERBS)

        # Contar dominios únicos
        domains_found: set[str] = set()
        for kw, domain in cls.DOMAIN_KEYWORDS.items():
            if kw in task_lower:
                domains_found.add(domain)

        # Keywords de colaboración
        collab_count = sum(1 for kw in cls.COLLABORATION_KEYWORDS if kw in task_lower)

        # Word count normalizado (0-1, cap en 50 palabras)
        word_count_score = min(len(words) / 50.0, 1.0)

        # Specificity: tareas con nombres propios/técnicos son más específicas
        specific_patterns = len(re.findall(r'[A-Z][a-z]+[A-Z]|`[^`]+`|"[^"]+"', task))
        specificity_score = min(specific_patterns / 3.0, 1.0)

        # Score de complejidad ponderado
        action_score = min(action_count / 4.0, 1.0)
        domain_score = min(len(domains_found) / 3.0, 1.0)
        collab_score = min(collab_count / 3.0, 1.0)

        complexity_score = (
            COMPLEXITY_WEIGHTS["action_verbs"] * action_score
            + COMPLEXITY_WEIGHTS["domain_count"] * domain_score
            + COMPLEXITY_WEIGHTS["word_count"] * word_count_score
            + COMPLEXITY_WEIGHTS["collaboration_kw"] * collab_score
            + COMPLEXITY_WEIGHTS["specificity"] * specificity_score
        )

        # Determinar nivel
        if complexity_score < 0.2:
            level = ComplexityLevel.TRIVIAL
        elif complexity_score < 0.4:
            level = ComplexityLevel.SIMPLE
        elif complexity_score < 0.6:
            level = ComplexityLevel.MODERATE
        elif complexity_score < 0.8:
            level = ComplexityLevel.COMPLEX
        else:
            level = ComplexityLevel.EPIC

        return {
            "complexity_score": complexity_score,
            "complexity_level": level,
            "action_verbs_found": action_count,
            "domains_found": sorted(domains_found),
            "domain_count": len(domains_found),
            "collaboration_keywords": collab_count,
            "word_count": len(words),
            "specificity_score": specificity_score,
        }


# ============================================================
# Agent Selector — selecciona el mejor agente para la tarea
# ============================================================
class AgentSelector:
    """Selecciona el mejor agente basado en capabilities requeridas."""

    # Mapping: capability → agente principal
    CAPABILITY_AGENTS: dict[str, str] = {
        "code-analysis": "explorer",
        "search": "explorer",
        "dependencies": "explorer",
        "architecture": "architect",
        "design": "architect",
        "patterns": "architect",
        "security": "security-auditor",
        "audit": "security-auditor",
        "testing": "test-engineer",
        "quality": "test-engineer",
        "debugging": "debugger",
        "troubleshooting": "debugger",
        "frontend": "frontend-specialist",
        "ui": "frontend-specialist",
        "react": "frontend-specialist",
        "backend": "backend-specialist",
        "api": "backend-specialist",
        "database": "database-architect",
        "sql": "database-architect",
        "devops": "devops-engineer",
        "infrastructure": "devops-engineer",
        "ci-cd": "devops-engineer",
        "performance": "performance-optimizer",
        "optimization": "performance-optimizer",
        "documentation": "documentation-writer",
        "machine-learning": "ml-engineer",
        "data-science": "ml-engineer",
        "planning": "planner",
    }

    @classmethod
    def select_best(cls, capabilities: list[str]) -> str | None:
        """Selecciona el mejor agente para las capabilities dadas."""
        if not capabilities:
            return "explorer"  # Default

        # Contar votos por agente
        votes: dict[str, int] = {}
        for cap in capabilities:
            agent = cls.CAPABILITY_AGENTS.get(cap)
            if agent:
                votes[agent] = votes.get(agent, 0) + 1

        if not votes:
            return "explorer"  # Fallback

        return max(votes, key=lambda a: votes[a])

    @classmethod
    def select_team(cls, capabilities: list[str]) -> list[str]:
        """Selecciona un equipo de agentes para las capabilities."""
        agents: set[str] = set()
        for cap in capabilities:
            agent = cls.CAPABILITY_AGENTS.get(cap)
            if agent:
                agents.add(agent)
        return sorted(agents) if agents else ["explorer"]


# ============================================================
# Intelligent Router
# ============================================================
class IntelligentRouter:
    """
    Router inteligente que analiza tareas y decide automáticamente
    la ruta de ejecución óptima.
    """

    def __init__(self, bus: Any = None) -> None:
        self._bus = bus
        self._decision_history: list[RouteDecision] = []
        self._execution_history: list[RouteExecution] = []

        # Métricas
        self._metrics = {
            "decisions_total": 0,
            "executions_total": 0,
            "routes": {rt.value: 0 for rt in RouteType},
            "avg_complexity": 0.0,
            "avg_confidence": 0.0,
        }

    # --------------------------------------------------------
    # Analyze — solo análisis sin ejecución
    # --------------------------------------------------------
    def analyze(self, task: str) -> RouteDecision:
        """
        Analiza una tarea y retorna la decisión de routing.
        No ejecuta nada — solo decide.
        """
        self._metrics["decisions_total"] += 1

        # Extraer capabilities
        capabilities = CapabilityExtractor.extract(task)

        # Analizar complejidad
        complexity = ComplexityAnalyzer.analyze(task)
        score = complexity["complexity_score"]
        level = complexity["complexity_level"]

        # Decidir ruta
        route, reason, confidence = self._decide_route(task, capabilities, complexity)

        # Seleccionar agente(s) recomendado(s)
        best_agent = AgentSelector.select_best(capabilities)
        team = AgentSelector.select_team(capabilities)

        decision = RouteDecision(
            task=task,
            route=route,
            complexity=level,
            complexity_score=score,
            recommended_agent=best_agent,
            recommended_agents=team,
            required_capabilities=capabilities,
            reason=reason,
            confidence=confidence,
            analysis=complexity,
        )

        # Actualizar métricas
        self._metrics["routes"][route.value] += 1
        n = self._metrics["decisions_total"]
        self._metrics["avg_complexity"] = (self._metrics["avg_complexity"] * (n - 1) + score) / n
        self._metrics["avg_confidence"] = (
            self._metrics["avg_confidence"] * (n - 1) + confidence
        ) / n

        # Guardar historial
        self._decision_history.append(decision)
        if len(self._decision_history) > 500:
            self._decision_history = self._decision_history[-400:]

        logger.info(
            "Router decision: route=%s complexity=%s(%.2f) agent=%s caps=%s — '%.60s...'",
            route.value,
            level.value,
            score,
            best_agent,
            capabilities,
            task,
        )

        return decision

    def _decide_route(
        self,
        task: str,
        capabilities: list[str],
        complexity: dict[str, Any],
    ) -> tuple[RouteType, str, float]:
        """Decide la ruta óptima basada en el análisis."""
        score = complexity["complexity_score"]
        domains = complexity["domain_count"]
        actions = complexity["action_verbs_found"]
        collab = complexity["collaboration_keywords"]

        # Regla 1: Tareas triviales/simples → DIRECT
        if score < 0.3 and domains <= 1:
            return (
                RouteType.DIRECT,
                f"Tarea simple (score={score:.2f}) con 1 dominio — ejecución directa",
                0.90,
            )

        # Regla 2: Tarea moderada con múltiples dominios → AUCTION
        if 0.3 <= score < 0.55 and domains >= 2:
            return (
                RouteType.AUCTION,
                f"Tarea moderada con {domains} dominios — subasta entre agentes capaces",
                0.80,
            )

        # Regla 3: Tarea moderada con un dominio → DIRECT con confianza media
        if 0.3 <= score < 0.55 and domains <= 1:
            return (
                RouteType.DIRECT,
                f"Tarea moderada (score={score:.2f}) con dominio específico — agente directo",
                0.75,
            )

        # Regla 4: Tarea compleja con keywords de colaboración → SWARM
        if score >= 0.55 and (collab >= 2 or domains >= 3):
            return (
                RouteType.SWARM,
                f"Tarea compleja (score={score:.2f}) con {domains} dominios "
                f"y {collab} indicadores de colaboración — enjambre multi-agente",
                0.85,
            )

        # Regla 5: Tarea compleja con múltiples acciones → PLAN
        if score >= 0.55 and actions >= 3:
            return (
                RouteType.PLAN,
                f"Tarea compleja con {actions} acciones — MetaPlanner descompone",
                0.80,
            )

        # Regla 6: Tarea compleja genérica → AUCTION
        if score >= 0.55:
            return (
                RouteType.AUCTION,
                f"Tarea compleja (score={score:.2f}) — subasta para selección óptima",
                0.70,
            )

        # Default: DIRECT
        return (
            RouteType.DIRECT,
            "Ruta por defecto — ejecución directa",
            0.60,
        )

    # --------------------------------------------------------
    # Route and Execute — análisis + ejecución
    # --------------------------------------------------------
    async def route_and_execute(
        self,
        task: str,
        context: dict[str, Any] | None = None,
        from_agent: str = "api",
        force_route: str | None = None,
    ) -> dict[str, Any]:
        """
        Analiza la tarea, decide la ruta, y ejecuta.

        Args:
            task: Tarea en lenguaje natural.
            context: Contexto adicional.
            from_agent: Quién origina la solicitud.
            force_route: Forzar una ruta específica (override).

        Returns:
            dict con decisión + resultado de ejecución.
        """
        # Fase 1: Analizar
        decision = self.analyze(task)

        # Override si se fuerza ruta
        if force_route:
            decision.route = RouteType(force_route)
            decision.reason = f"Ruta forzada: {force_route}"

        execution = RouteExecution(decision=decision, status="executing")
        self._metrics["executions_total"] += 1

        # Fase 2: Ejecutar según ruta
        try:
            result = await self._execute_route(decision, context, from_agent)
            execution.execution_result = result
            execution.status = "completed"
        except Exception as e:
            execution.execution_result = {"error": str(e)}
            execution.status = "failed"
            logger.error("Router execution failed: %s", e)

        execution.completed_at = time.time()
        execution.duration_seconds = execution.completed_at - execution.started_at

        self._execution_history.append(execution)
        if len(self._execution_history) > 200:
            self._execution_history = self._execution_history[-150:]

        # Publicar decisión en bus
        if self._bus:
            try:
                await self._bus.publish(
                    ROUTER_CHANNEL,
                    {
                        "event": "route_executed",
                        "route": decision.route.value,
                        "task": task[:100],
                        "agent": decision.recommended_agent,
                        "status": execution.status,
                        "duration": execution.duration_seconds,
                    },
                    from_agent="intelligent-router",
                )
            except Exception:
                pass

        return execution.to_dict()

    async def _execute_route(
        self,
        decision: RouteDecision,
        context: dict[str, Any] | None,
        from_agent: str,
    ) -> dict[str, Any]:
        """Ejecuta la tarea según la ruta decidida."""

        if decision.route == RouteType.DIRECT:
            return await self._execute_direct(decision, context, from_agent)
        elif decision.route == RouteType.AUCTION:
            return await self._execute_auction(decision, context, from_agent)
        elif decision.route == RouteType.SWARM:
            return await self._execute_swarm(decision, context, from_agent)
        elif decision.route == RouteType.PLAN:
            return await self._execute_plan(decision, context, from_agent)
        elif decision.route == RouteType.WORKFLOW:
            return await self._execute_workflow(decision, context, from_agent)
        else:
            return await self._execute_direct(decision, context, from_agent)

    async def _execute_direct(
        self,
        decision: RouteDecision,
        context: dict | None,
        from_agent: str,
    ) -> dict[str, Any]:
        """Ejecuta via agente directo en el daemon."""
        from .agent_daemon import get_daemon

        daemon = await get_daemon()
        task_id = await daemon.submit_task(
            agent_name=decision.recommended_agent or "explorer",
            task=decision.task,
            from_agent=from_agent,
            context=context,
            priority_name="NORMAL",
        )
        return {"method": "direct", "agent": decision.recommended_agent, "task_id": task_id}

    async def _execute_auction(
        self,
        decision: RouteDecision,
        context: dict | None,
        from_agent: str,
    ) -> dict[str, Any]:
        """Ejecuta via subasta."""
        from .agent_daemon import get_daemon

        daemon = await get_daemon()
        result = await daemon.auction_task(
            task=decision.task,
            required_capabilities=decision.required_capabilities,
            from_agent=from_agent,
        )
        return {"method": "auction", **result}

    async def _execute_swarm(
        self,
        decision: RouteDecision,
        context: dict | None,
        from_agent: str,
    ) -> dict[str, Any]:
        """Ejecuta via enjambre."""
        from .agent_daemon import get_daemon

        daemon = await get_daemon()
        result = await daemon.execute_swarm(
            task=decision.task,
            agents=decision.recommended_agents,
            context=context,
        )
        return {"method": "swarm", **result}

    async def _execute_plan(
        self,
        decision: RouteDecision,
        context: dict | None,
        from_agent: str,
    ) -> dict[str, Any]:
        """Ejecuta via MetaPlanner."""
        from .agent_daemon import get_daemon

        daemon = await get_daemon()
        result = await daemon.plan_and_execute(decision.task, context)
        return {"method": "plan", **result}

    async def _execute_workflow(
        self,
        decision: RouteDecision,
        context: dict | None,
        from_agent: str,
    ) -> dict[str, Any]:
        """Ejecuta via workflow predefinido."""
        from .agent_daemon import get_daemon

        daemon = await get_daemon()
        result = await daemon.execute_workflow(
            graph_name="default", initial_state={"task": decision.task}
        )
        return {"method": "workflow", **result}

    # --------------------------------------------------------
    # Stats & History
    # --------------------------------------------------------
    def get_stats(self) -> dict[str, Any]:
        """Retorna estadísticas del router."""
        return {
            "metrics": {**self._metrics},
            "decision_history_size": len(self._decision_history),
            "execution_history_size": len(self._execution_history),
        }

    def get_decision_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Retorna historial de decisiones."""
        return [d.to_dict() for d in self._decision_history[-limit:]]

    def get_execution_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Retorna historial de ejecuciones."""
        return [e.to_dict() for e in self._execution_history[-limit:]]


# ============================================================
# Singleton
# ============================================================
_instance: IntelligentRouter | None = None


async def get_intelligent_router(bus: Any = None) -> IntelligentRouter:
    """Obtiene o crea el router inteligente global."""
    global _instance
    if _instance is None:
        _instance = IntelligentRouter(bus=bus)
    return _instance
