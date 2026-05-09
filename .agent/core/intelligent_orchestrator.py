# mypy: ignore-errors
#!/usr/bin/env python3
"""
Intelligent Orchestrator - Análisis de tareas y selección de estrategia.

Capa 1 del pipeline de orquestación (pre-ejecución):
1. Recibe una tarea y analiza su complejidad (TRIVIAL → RESEARCH)
2. Selecciona la estrategia óptima (DIRECT, REACT, DEBATE, COMPOSED, etc.)
3. Recomienda agentes según el análisis

Jerarquía de orquestación (3 módulos):
    IntelligentOrchestrator.analyze()  → análisis y estrategia (este módulo)
    Orchestrator.execute()             → ejecución con fallback 3-tier (orchestrator.py)
    MetaOrchestrator.evaluate()        → calidad post-ejecución (meta_orchestrator.py)

Version: 1.0.0
"""

import asyncio
import contextlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

# Setup logging
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger("intelligent-orchestrator")


class TaskComplexity(Enum):
    """Task complexity levels."""

    TRIVIAL = "trivial"  # Single action, no thinking needed
    SIMPLE = "simple"  # Few steps, minimal reasoning
    MODERATE = "moderate"  # Multiple steps, some reasoning
    COMPLEX = "complex"  # Many steps, significant reasoning
    EXPERT = "expert"  # Requires deep expertise
    RESEARCH = "research"  # Requires exploration and learning


class ExecutionStrategy(Enum):
    """Execution strategies."""

    DIRECT = "direct"  # Execute immediately
    THINK_FIRST = "think_first"  # Chain-of-thought then execute
    DEBATE = "debate"  # Multi-agent debate then execute
    REACT = "react"  # ReAct loop
    COMPOSED = "composed"  # Compose skills dynamically
    COLLABORATIVE = "collaborative"  # Multiple agents working together
    ADAPTIVE = "adaptive"  # Adapt strategy during execution


@dataclass
class TaskAnalysis:
    """Analysis of a task."""

    task: str
    complexity: TaskComplexity
    domains: list[str]
    required_capabilities: list[str]
    estimated_steps: int
    risk_level: float  # 0-1
    confidence: float  # 0-1
    recommended_strategy: ExecutionStrategy
    recommended_agents: list[str]
    recommended_modules: list[str]
    warnings: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "complexity": self.complexity.value,
            "domains": self.domains,
            "required_capabilities": self.required_capabilities,
            "estimated_steps": self.estimated_steps,
            "risk_level": self.risk_level,
            "confidence": self.confidence,
            "recommended_strategy": self.recommended_strategy.value,
            "recommended_agents": self.recommended_agents,
            "recommended_modules": self.recommended_modules,
            "warnings": self.warnings,
            "suggestions": self.suggestions,
        }


@dataclass
class ExecutionStep:
    """A single execution step."""

    step_number: int
    action: str
    agent: str | None
    module: str | None
    input_data: dict
    output_data: dict | None = None
    status: str = "pending"
    duration_ms: float = 0
    error: str | None = None
    reflection: str | None = None


@dataclass
class ExecutionResult:
    """Result of intelligent execution."""

    task: str
    success: bool
    output: Any
    analysis: TaskAnalysis
    steps: list[ExecutionStep]
    total_duration_ms: float
    tokens_used: int
    quality_score: float
    explanation: str
    learnings: list[str]
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "success": self.success,
            "output": self.output,
            "analysis": self.analysis.to_dict(),
            "steps": [
                {
                    "step_number": s.step_number,
                    "action": s.action,
                    "agent": s.agent,
                    "module": s.module,
                    "status": s.status,
                    "duration_ms": s.duration_ms,
                    "error": s.error,
                    "reflection": s.reflection,
                }
                for s in self.steps
            ],
            "total_duration_ms": self.total_duration_ms,
            "tokens_used": self.tokens_used,
            "quality_score": self.quality_score,
            "explanation": self.explanation,
            "learnings": self.learnings,
            "metadata": self.metadata,
        }

    def export_report(self) -> str:
        """Export as markdown report."""
        lines = [
            "# Intelligent Execution Report",
            "",
            f"**Task:** {self.task}",
            f"**Status:** {'✅ Success' if self.success else '❌ Failed'}",
            f"**Quality Score:** {self.quality_score:.2f}/1.0",
            f"**Duration:** {self.total_duration_ms:.0f}ms",
            f"**Tokens Used:** {self.tokens_used}",
            "",
            "## Analysis",
            "",
            f"- **Complexity:** {self.analysis.complexity.value}",
            f"- **Strategy:** {self.analysis.recommended_strategy.value}",
            f"- **Domains:** {', '.join(self.analysis.domains)}",
            f"- **Agents Used:** {', '.join(self.analysis.recommended_agents)}",
            "",
            "## Execution Steps",
            "",
        ]

        for step in self.steps:
            status_icon = (
                "✅" if step.status == "completed" else "❌" if step.status == "failed" else "⏳"
            )
            lines.append(f"{step.step_number}. {status_icon} **{step.action}**")
            if step.agent:
                lines.append(f"   - Agent: {step.agent}")
            if step.module:
                lines.append(f"   - Module: {step.module}")
            if step.reflection:
                lines.append(f"   - Reflection: {step.reflection}")
            lines.append(f"   - Duration: {step.duration_ms:.0f}ms")
            lines.append("")

        lines.extend(["## Explanation", "", self.explanation, "", "## Learnings", ""])

        for learning in self.learnings:
            lines.append(f"- {learning}")

        return "\n".join(lines)


class IntelligentOrchestrator:
    """
    The master orchestrator that unifies all intelligence capabilities.

    This orchestrator:
    1. Analyzes tasks using metacognition and chain-of-thought
    2. Predicts risks and potential escalations
    3. Selects optimal agents and strategies
    4. Composes skills dynamically when needed
    5. Executes with full reflection and quality scoring
    6. Learns from every execution
    7. Adapts to user emotions and context
    """

    def __init__(self, config: dict | None = None):
        self.config = config or self._default_config()
        self.execution_history: list[ExecutionResult] = []
        self._modules_loaded = False
        self._modules = {}
        self._intelligence_hub = None

        # Statistics
        self.stats = {
            "total_executions": 0,
            "successful_executions": 0,
            "total_tokens": 0,
            "avg_quality_score": 0.0,
            "domains_handled": set(),
            "strategies_used": {},
        }

    def _get_intelligence_hub(self):
        """Lazy-load Intelligence Hub para enriquecer decisiones con datos reales."""
        if self._intelligence_hub is None:
            try:
                from .intelligence_hub import get_intelligence_hub

                self._intelligence_hub = get_intelligence_hub()
            except ImportError:
                logger.debug("Intelligence Hub no disponible")
        return self._intelligence_hub

    def _default_config(self) -> dict:
        """Default configuration."""
        return {
            "enable_reflection": True,
            "enable_chain_of_thought": True,
            "enable_debate": True,
            "enable_emotion_detection": True,
            "enable_predictive_escalation": True,
            "enable_quality_scoring": True,
            "enable_learning": True,
            "max_steps": 50,
            "max_debate_rounds": 3,
            "min_quality_threshold": 0.7,
            "risk_threshold": 0.8,
            "auto_escalate": True,
            "parallel_execution": True,
            "memory_persistence": True,
        }

    async def _load_modules(self):
        """Lazy load intelligence modules."""
        if self._modules_loaded:
            return

        try:
            # Foundation modules
            from .intelligence import (
                ChainOfThought,
                Metacognition,
                MultiAgentDebate,
                QualityScorer,
                SelfReflection,
                create_knowledge_graph,
            )

            self._modules["reflection"] = SelfReflection()
            self._modules["cot"] = ChainOfThought()
            self._modules["debate"] = MultiAgentDebate()
            self._modules["metacognition"] = Metacognition()
            self._modules["knowledge"] = create_knowledge_graph()
            self._modules["quality"] = QualityScorer()

            # Nivel 1 modules
            from .intelligence import (
                ContextCompressor,
                PredictiveEscalation,
                ProactiveSuggester,
                SkillGenerator,
                ToolLearner,
            )

            self._modules["tool_learner"] = ToolLearner()
            self._modules["skill_generator"] = SkillGenerator()
            self._modules["escalation"] = PredictiveEscalation()
            self._modules["compressor"] = ContextCompressor()
            self._modules["suggester"] = ProactiveSuggester()

            # Nivel 2 modules
            from .intelligence import (
                ABTester,
                AdversarialTester,
                AgentMessenger,
                DecisionExplainer,
                EmotionDetector,
            )

            self._modules["adversarial"] = AdversarialTester()
            self._modules["explainer"] = DecisionExplainer()
            self._modules["messenger"] = AgentMessenger()
            self._modules["ab_tester"] = ABTester()
            self._modules["emotion"] = EmotionDetector()

            # Nivel 3 modules
            from .intelligence import (
                CollaborativeMemory,
                DomainSpecializer,
                ErrorRecovery,
                SkillComposer,
                TimeAwareMemory,
            )

            self._modules["composer"] = SkillComposer()
            self._modules["specializer"] = DomainSpecializer()
            self._modules["collab_memory"] = CollaborativeMemory()
            self._modules["time_memory"] = TimeAwareMemory()
            self._modules["recovery"] = ErrorRecovery()

            self._modules_loaded = True
            logger.info(f"Loaded {len(self._modules)} intelligence modules")

        except ImportError as e:
            logger.warning(f"Could not load some modules: {e}")
            self._modules_loaded = True

    async def analyze_task(self, task: str, context: dict | None = None) -> TaskAnalysis:
        """
        Deeply analyze a task to determine optimal execution strategy.

        Uses:
        - Chain-of-thought for reasoning
        - Metacognition for confidence assessment
        - Domain detection for agent selection
        - Risk prediction for escalation planning
        """
        await self._load_modules()

        context = context or {}

        # Detect complexity
        complexity = self._detect_complexity(task)

        # Detect domains
        domains = self._detect_domains(task)

        # Detect required capabilities
        capabilities = self._detect_capabilities(task, domains)

        # Estimate steps
        estimated_steps = self._estimate_steps(task, complexity)

        # Predict risk
        risk_level = await self._predict_risk(task, context)

        # Assess confidence
        confidence = await self._assess_confidence(task, domains)

        # Select strategy
        strategy = self._select_strategy(complexity, risk_level, domains)

        # Select agents
        agents = self._select_agents(domains, capabilities)

        # Select modules
        modules = self._select_modules(complexity, strategy)

        # Generate warnings
        warnings = self._generate_warnings(task, risk_level, complexity)

        # Generate suggestions
        suggestions = await self._generate_suggestions(task, context)

        # Enriquecer con Intelligence Hub (datos reales de ejecuciones previas)
        hub = self._get_intelligence_hub()
        if hub:
            try:
                intel_ctx = hub.query_intelligence(task)
                # Ajustar riesgo si el hub tiene datos de CI/errores
                if intel_ctx.risk_level > risk_level:
                    risk_level = intel_ctx.risk_level
                    warnings.append(
                        f"Intelligence Hub: riesgo elevado ({risk_level:.2f}) por historial"
                    )
                # Ajustar confianza si hay patrones previos
                if intel_ctx.confidence > confidence:
                    confidence = intel_ctx.confidence
                # Agregar avoidances como warnings
                for avoidance in intel_ctx.learned_avoidances:
                    reason = avoidance.get("reason") or avoidance.get("correction", "")
                    if reason:
                        warnings.append(f"Aprendizaje previo: {reason}")
                # Agregar errores conocidos como sugerencias
                for error in intel_ctx.relevant_errors[:2]:
                    desc = error.get("description", "")
                    resolution = error.get("resolution", "")
                    if desc and resolution:
                        suggestions.append(f"Error conocido '{desc}': {resolution}")
                # Re-rankear agentes con datos historicos
                if agents:
                    candidates = [
                        {"name": a, "tier": 3, "skills": [], "description": a} for a in agents
                    ]
                    ranked = hub.rank_agents(task, candidates, top_k=len(agents))
                    agents = [r.agent_name for r in ranked]
                    # Re-evaluar estrategia con nuevo risk_level
                    strategy = self._select_strategy(complexity, risk_level, domains)
            except Exception as e:
                logger.debug("Error consultando Intelligence Hub: %s", e)

        return TaskAnalysis(
            task=task,
            complexity=complexity,
            domains=domains,
            required_capabilities=capabilities,
            estimated_steps=estimated_steps,
            risk_level=risk_level,
            confidence=confidence,
            recommended_strategy=strategy,
            recommended_agents=agents,
            recommended_modules=modules,
            warnings=warnings,
            suggestions=suggestions,
        )

    def _detect_complexity(self, task: str) -> TaskComplexity:
        """Detect task complexity."""
        task_lower = task.lower()

        # Research indicators
        research_keywords = ["research", "investigate", "explore", "analyze", "study", "compare"]
        if any(kw in task_lower for kw in research_keywords):
            return TaskComplexity.RESEARCH

        # Expert indicators
        expert_keywords = [
            "architect",
            "design system",
            "security audit",
            "performance optimization",
            "migrate",
        ]
        if any(kw in task_lower for kw in expert_keywords):
            return TaskComplexity.EXPERT

        # Complex indicators
        complex_keywords = ["implement", "create", "build", "develop", "refactor", "integrate"]
        if any(kw in task_lower for kw in complex_keywords):
            return TaskComplexity.COMPLEX

        # Moderate indicators
        moderate_keywords = ["update", "modify", "add", "change", "fix bug", "improve"]
        if any(kw in task_lower for kw in moderate_keywords):
            return TaskComplexity.MODERATE

        # Simple indicators
        simple_keywords = ["rename", "move", "delete", "copy", "format", "lint"]
        if any(kw in task_lower for kw in simple_keywords):
            return TaskComplexity.SIMPLE

        # Length-based heuristic
        if len(task.split()) < 5:
            return TaskComplexity.TRIVIAL
        elif len(task.split()) < 15:
            return TaskComplexity.SIMPLE
        elif len(task.split()) < 30:
            return TaskComplexity.MODERATE
        else:
            return TaskComplexity.COMPLEX

    def _detect_domains(self, task: str) -> list[str]:
        """Detect relevant domains."""
        task_lower = task.lower()
        domains = []

        domain_keywords = {
            "frontend": [
                "react",
                "vue",
                "angular",
                "css",
                "html",
                "ui",
                "component",
                "tailwind",
                "nextjs",
            ],
            "backend": [
                "api",
                "server",
                "endpoint",
                "rest",
                "graphql",
                "database",
                "fastapi",
                "express",
            ],
            "database": [
                "sql",
                "postgresql",
                "mysql",
                "mongodb",
                "prisma",
                "schema",
                "migration",
                "query",
            ],
            "security": [
                "auth",
                "security",
                "vulnerability",
                "owasp",
                "encryption",
                "token",
                "jwt",
                "oauth",
            ],
            "devops": [
                "docker",
                "kubernetes",
                "ci/cd",
                "deploy",
                "pipeline",
                "terraform",
                "aws",
                "cloud",
            ],
            "testing": [
                "test",
                "spec",
                "coverage",
                "unit",
                "integration",
                "e2e",
                "playwright",
                "jest",
            ],
            "mobile": ["react native", "flutter", "ios", "android", "mobile"],
            "ml": ["machine learning", "ml", "model", "training", "inference", "ai", "neural"],
            "documentation": ["docs", "readme", "documentation", "comment", "docstring"],
        }

        for domain, keywords in domain_keywords.items():
            if any(kw in task_lower for kw in keywords):
                domains.append(domain)

        return domains if domains else ["general"]

    def _detect_capabilities(self, task: str, domains: list[str]) -> list[str]:
        """Detect required capabilities."""
        capabilities = []
        task_lower = task.lower()

        capability_keywords = {
            "code_generation": ["create", "implement", "write", "generate", "build"],
            "code_analysis": ["analyze", "review", "audit", "inspect", "check"],
            "refactoring": ["refactor", "improve", "optimize", "clean"],
            "debugging": ["debug", "fix", "resolve", "troubleshoot"],
            "testing": ["test", "verify", "validate"],
            "documentation": ["document", "explain", "describe"],
            "planning": ["plan", "design", "architect"],
            "research": ["research", "investigate", "explore"],
        }

        for capability, keywords in capability_keywords.items():
            if any(kw in task_lower for kw in keywords):
                capabilities.append(capability)

        # Add domain-specific capabilities
        for domain in domains:
            capabilities.append(f"{domain}_expertise")

        return capabilities if capabilities else ["general_execution"]

    def _estimate_steps(self, task: str, complexity: TaskComplexity) -> int:
        """Estimate number of execution steps."""
        base_steps = {
            TaskComplexity.TRIVIAL: 1,
            TaskComplexity.SIMPLE: 3,
            TaskComplexity.MODERATE: 7,
            TaskComplexity.COMPLEX: 15,
            TaskComplexity.EXPERT: 25,
            TaskComplexity.RESEARCH: 20,
        }
        return base_steps.get(complexity, 5)

    async def _predict_risk(self, task: str, context: dict) -> float:
        """Predict risk level using predictive escalation module."""
        if "escalation" in self._modules and self._modules["escalation"]:
            try:
                prediction = await self._modules["escalation"].predict(task, context)
                return prediction.risk_score if hasattr(prediction, "risk_score") else 0.5
            except Exception:
                logger.exception(
                    "Error in escalation module for task %s",
                    task.get("id") if isinstance(task, dict) else str(task),
                )

        # Fallback heuristic
        risk_keywords = [
            "delete",
            "remove",
            "production",
            "deploy",
            "security",
            "password",
            "credential",
        ]
        task_lower = task.lower()
        risk_count = sum(1 for kw in risk_keywords if kw in task_lower)
        return min(0.3 + (risk_count * 0.15), 1.0)

    async def _assess_confidence(self, task: str, domains: list[str]) -> float:
        """Assess confidence using metacognition module."""
        if "metacognition" in self._modules and self._modules["metacognition"]:
            try:
                assessment = await self._modules["metacognition"].assess(task)
                return assessment.confidence if hasattr(assessment, "confidence") else 0.7
            except Exception:
                logger.exception(
                    "Error in metacognition assessment for task %s",
                    task[:50] if isinstance(task, str) else str(task),
                )

        # Fallback: higher confidence for familiar domains
        familiar_domains = ["frontend", "backend", "database", "testing"]
        familiarity = sum(1 for d in domains if d in familiar_domains)
        return min(0.5 + (familiarity * 0.15), 0.95)

    def _select_strategy(
        self, complexity: TaskComplexity, risk_level: float, domains: list[str]
    ) -> ExecutionStrategy:
        """Select optimal execution strategy."""

        # High risk -> debate for consensus
        if risk_level > 0.8:
            return ExecutionStrategy.DEBATE

        # Research -> adaptive strategy
        if complexity == TaskComplexity.RESEARCH:
            return ExecutionStrategy.ADAPTIVE

        # Expert level -> composed skills
        if complexity == TaskComplexity.EXPERT:
            return ExecutionStrategy.COMPOSED

        # Complex with multiple domains -> collaborative
        if complexity == TaskComplexity.COMPLEX and len(domains) > 2:
            return ExecutionStrategy.COLLABORATIVE

        # Moderate -> think first
        if complexity in [TaskComplexity.MODERATE, TaskComplexity.COMPLEX]:
            return ExecutionStrategy.THINK_FIRST

        # Simple tasks -> direct execution
        return ExecutionStrategy.DIRECT

    def _select_agents(self, domains: list[str], capabilities: list[str]) -> list[str]:
        """Select optimal agents based on domains and capabilities."""
        agents = []

        domain_agents = {
            "frontend": ["frontend-specialist", "react-specialist", "ui-ux-designer"],
            "backend": ["backend-specialist", "api-designer"],
            "database": ["database-architect"],
            "security": ["security-auditor"],
            "devops": ["devops-engineer"],
            "testing": ["test-engineer", "qa-specialist"],
            "mobile": ["mobile-developer"],
            "ml": ["ml-engineer"],
            "documentation": ["documentation-writer"],
            "general": ["explorer", "planner"],
        }

        for domain in domains:
            if domain in domain_agents:
                agents.extend(domain_agents[domain][:2])  # Top 2 per domain

        # Add capability-based agents
        capability_agents = {
            "code_analysis": "code-reviewer",
            "refactoring": "refactor",
            "debugging": "debugger",
            "planning": "architect",
        }

        for cap in capabilities:
            if cap in capability_agents and capability_agents[cap] not in agents:
                agents.append(capability_agents[cap])

        # Ensure we have at least explorer
        if not agents:
            agents = ["explorer", "planner"]

        return list(set(agents))[:5]  # Max 5 agents

    def _select_modules(self, complexity: TaskComplexity, strategy: ExecutionStrategy) -> list[str]:
        """Select intelligence modules to use."""
        # Always use these
        modules = ["reflection", "quality"]

        # Strategy-based selection
        if strategy == ExecutionStrategy.THINK_FIRST:
            modules.append("cot")
        elif strategy == ExecutionStrategy.DEBATE:
            modules.extend(["cot", "debate"])
        elif strategy == ExecutionStrategy.REACT:
            modules.append("react")
        elif strategy == ExecutionStrategy.COMPOSED:
            modules.extend(["cot", "composer"])
        elif strategy == ExecutionStrategy.COLLABORATIVE:
            modules.extend(["messenger", "collab_memory"])
        elif strategy == ExecutionStrategy.ADAPTIVE:
            modules.extend(["cot", "metacognition", "recovery"])

        # Complexity-based additions
        if complexity in [TaskComplexity.COMPLEX, TaskComplexity.EXPERT]:
            modules.extend(["escalation", "explainer"])

        return list(set(modules))

    def _generate_warnings(
        self, task: str, risk_level: float, complexity: TaskComplexity
    ) -> list[str]:
        """Generate warnings for the task."""
        warnings = []

        if risk_level > 0.7:
            warnings.append("⚠️ High-risk task - extra verification recommended")

        if complexity == TaskComplexity.EXPERT:
            warnings.append("⚠️ Expert-level task - may require human review")

        task_lower = task.lower()
        if "production" in task_lower:
            warnings.append("⚠️ Production environment detected - proceed with caution")

        if "delete" in task_lower or "remove" in task_lower:
            warnings.append("⚠️ Destructive operation - ensure backups exist")

        return warnings

    async def _generate_suggestions(self, task: str, context: dict) -> list[str]:
        """Generate proactive suggestions."""
        if "suggester" in self._modules and self._modules["suggester"]:
            try:
                suggestions = await self._modules["suggester"].suggest(task, context)
                return [s.text if hasattr(s, "text") else str(s) for s in suggestions[:3]]
            except Exception:
                logger.exception("Error in suggester suggest")
        return []

    async def execute(
        self, task: str, context: dict | None = None, config_override: dict | None = None
    ) -> ExecutionResult:
        """
        Execute a task with full intelligence capabilities.

        This is the main entry point for intelligent execution.
        """
        start_time = datetime.now()
        context = context or {}
        config = {**self.config, **(config_override or {})}

        steps: list[ExecutionStep] = []
        tokens_used = 0

        try:
            # Step 1: Analyze task
            step = ExecutionStep(
                step_number=1,
                action="Analyzing task",
                agent=None,
                module="metacognition",
                input_data={"task": task},
            )
            analysis = await self.analyze_task(task, context)
            step.output_data = analysis.to_dict()
            step.status = "completed"
            step.duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            steps.append(step)

            logger.info(
                f"Task analysis: complexity={analysis.complexity.value}, strategy={analysis.recommended_strategy.value}"
            )

            # Step 2: Detect emotion if enabled
            if config.get("enable_emotion_detection"):
                user_text = context.get("user_message", task)
                emotion_result = await self._detect_emotion(user_text)
                if emotion_result:
                    context["detected_emotion"] = emotion_result
                    logger.info(f"Detected emotion: {emotion_result.get('emotion', 'neutral')}")

            # Step 3: Check for escalation
            if config.get("enable_predictive_escalation") and analysis.risk_level > config.get(
                "risk_threshold", 0.8
            ):
                if config.get("auto_escalate"):
                    logger.warning(
                        f"High risk detected ({analysis.risk_level:.2f}), flagging for review"
                    )
                    analysis.warnings.append(
                        "🚨 Task auto-flagged for human review due to high risk"
                    )

            # Step 4: Execute based on strategy
            step_start = datetime.now()
            output, strategy_steps = await self._execute_strategy(
                task=task, analysis=analysis, context=context, config=config
            )
            steps.extend(strategy_steps)

            # Step 5: Quality scoring
            quality_score = 0.0
            if config.get("enable_quality_scoring"):
                quality_score = await self._score_quality(output, task)

            # Step 6: Reflection
            reflection = None
            if config.get("enable_reflection"):
                reflection = await self._reflect(output, task, analysis)

            # Step 7: Extract learnings
            learnings = await self._extract_learnings(task, output, analysis, steps)

            # Step 8: Generate explanation
            explanation = await self._generate_explanation(task, analysis, steps, output)

            # Calculate totals
            total_duration = (datetime.now() - start_time).total_seconds() * 1000

            result = ExecutionResult(
                task=task,
                success=True,
                output=output,
                analysis=analysis,
                steps=steps,
                total_duration_ms=total_duration,
                tokens_used=tokens_used,
                quality_score=quality_score,
                explanation=explanation,
                learnings=learnings,
                metadata={
                    "strategy": analysis.recommended_strategy.value,
                    "agents_used": analysis.recommended_agents,
                    "modules_used": analysis.recommended_modules,
                    "reflection": reflection,
                },
            )

            # Update stats
            self._update_stats(result)

            # Store in history
            if config.get("memory_persistence"):
                self.execution_history.append(result)

            # Learn from execution
            if config.get("enable_learning"):
                await self._learn_from_execution(result)

            return result

        except Exception as e:
            logger.error(f"Execution failed: {e}")
            total_duration = (datetime.now() - start_time).total_seconds() * 1000

            # Attempt recovery
            recovery_result = await self._attempt_recovery(task, str(e), context)

            return ExecutionResult(
                task=task,
                success=False,
                output=None,
                analysis=analysis
                if "analysis" in locals()
                else TaskAnalysis(
                    task=task,
                    complexity=TaskComplexity.COMPLEX,
                    domains=["general"],
                    required_capabilities=[],
                    estimated_steps=0,
                    risk_level=1.0,
                    confidence=0.0,
                    recommended_strategy=ExecutionStrategy.DIRECT,
                    recommended_agents=[],
                    recommended_modules=[],
                ),
                steps=steps,
                total_duration_ms=total_duration,
                tokens_used=tokens_used,
                quality_score=0.0,
                explanation=f"Execution failed: {str(e)}",
                learnings=[f"Error encountered: {str(e)}"],
                metadata={"error": str(e), "recovery_attempted": recovery_result is not None},
            )

    async def _execute_strategy(
        self, task: str, analysis: TaskAnalysis, context: dict, config: dict
    ) -> tuple[Any, list[ExecutionStep]]:
        """Execute task based on selected strategy."""
        strategy = analysis.recommended_strategy
        steps = []

        if strategy == ExecutionStrategy.DIRECT:
            output, step = await self._execute_direct(task, analysis, context)
            steps.append(step)

        elif strategy == ExecutionStrategy.THINK_FIRST:
            thinking, think_step = await self._execute_think(task, analysis, context)
            steps.append(think_step)
            output, exec_step = await self._execute_with_thinking(task, thinking, analysis, context)
            steps.append(exec_step)

        elif strategy == ExecutionStrategy.DEBATE:
            debate_result, debate_step = await self._execute_debate(task, analysis, context)
            steps.append(debate_step)
            output, exec_step = await self._execute_with_consensus(
                task, debate_result, analysis, context
            )
            steps.append(exec_step)

        elif strategy == ExecutionStrategy.REACT:
            output, react_steps = await self._execute_react(task, analysis, context)
            steps.extend(react_steps)

        elif strategy == ExecutionStrategy.COMPOSED:
            pipeline, compose_step = await self._compose_pipeline(task, analysis, context)
            steps.append(compose_step)
            output, exec_steps = await self._execute_pipeline(pipeline, analysis, context)
            steps.extend(exec_steps)

        elif strategy == ExecutionStrategy.COLLABORATIVE:
            output, collab_steps = await self._execute_collaborative(task, analysis, context)
            steps.extend(collab_steps)

        elif strategy == ExecutionStrategy.ADAPTIVE:
            output, adaptive_steps = await self._execute_adaptive(task, analysis, context)
            steps.extend(adaptive_steps)

        else:
            output, step = await self._execute_direct(task, analysis, context)
            steps.append(step)

        return output, steps

    async def _execute_direct(
        self, task: str, analysis: TaskAnalysis, context: dict
    ) -> tuple[Any, ExecutionStep]:
        """Direct execution without extra reasoning."""
        step = ExecutionStep(
            step_number=len(self.execution_history) + 2,
            action="Direct execution",
            agent=analysis.recommended_agents[0] if analysis.recommended_agents else None,
            module=None,
            input_data={"task": task},
        )

        # Simulate execution (in real implementation, would call actual agent)
        output = {
            "status": "completed",
            "task": task,
            "approach": "direct",
            "result": f"Task '{task[:50]}...' executed directly",
        }

        step.output_data = output
        step.status = "completed"

        return output, step

    async def _execute_think(
        self, task: str, analysis: TaskAnalysis, context: dict
    ) -> tuple[dict, ExecutionStep]:
        """Execute chain-of-thought reasoning."""
        step = ExecutionStep(
            step_number=len(self.execution_history) + 2,
            action="Chain-of-thought reasoning",
            agent=None,
            module="cot",
            input_data={"task": task},
        )

        if "cot" in self._modules and self._modules["cot"]:
            try:
                result = await self._modules["cot"].think(task)
                thinking = (
                    result.to_dict() if hasattr(result, "to_dict") else {"thoughts": str(result)}
                )
            except Exception as e:
                thinking = {"thoughts": f"Thinking about: {task}", "error": str(e)}
        else:
            thinking = {"thoughts": f"Analyzing task: {task}"}

        step.output_data = thinking
        step.status = "completed"

        return thinking, step

    async def _execute_with_thinking(
        self, task: str, thinking: dict, analysis: TaskAnalysis, context: dict
    ) -> tuple[Any, ExecutionStep]:
        """Execute with chain-of-thought results."""
        step = ExecutionStep(
            step_number=len(self.execution_history) + 3,
            action="Execution with reasoning",
            agent=analysis.recommended_agents[0] if analysis.recommended_agents else None,
            module=None,
            input_data={"task": task, "thinking": thinking},
        )

        output = {
            "status": "completed",
            "task": task,
            "approach": "think_first",
            "reasoning": thinking,
            "result": "Task executed with reasoning",
        }

        step.output_data = output
        step.status = "completed"

        return output, step

    async def _execute_debate(
        self, task: str, analysis: TaskAnalysis, context: dict
    ) -> tuple[dict, ExecutionStep]:
        """Execute multi-agent debate."""
        step = ExecutionStep(
            step_number=len(self.execution_history) + 2,
            action="Multi-agent debate",
            agent=None,
            module="debate",
            input_data={"task": task},
        )

        if "debate" in self._modules and self._modules["debate"]:
            try:
                result = await self._modules["debate"].debate(task)
                debate_result = (
                    result.to_dict() if hasattr(result, "to_dict") else {"consensus": str(result)}
                )
            except Exception as e:
                debate_result = {"consensus": "Proceed with caution", "error": str(e)}
        else:
            debate_result = {"consensus": "Agreed approach for: " + task[:50]}

        step.output_data = debate_result
        step.status = "completed"

        return debate_result, step

    async def _execute_with_consensus(
        self, task: str, debate_result: dict, analysis: TaskAnalysis, context: dict
    ) -> tuple[Any, ExecutionStep]:
        """Execute with debate consensus."""
        step = ExecutionStep(
            step_number=len(self.execution_history) + 3,
            action="Execution with consensus",
            agent=analysis.recommended_agents[0] if analysis.recommended_agents else None,
            module=None,
            input_data={"task": task, "consensus": debate_result},
        )

        output = {
            "status": "completed",
            "task": task,
            "approach": "debate",
            "consensus": debate_result,
            "result": "Task executed with multi-agent consensus",
        }

        step.output_data = output
        step.status = "completed"

        return output, step

    async def _execute_react(
        self, task: str, analysis: TaskAnalysis, context: dict
    ) -> tuple[Any, list[ExecutionStep]]:
        """Execute using ReAct pattern."""
        steps = []
        iterations = min(analysis.estimated_steps, self.config.get("max_steps", 10))

        for i in range(iterations):
            step = ExecutionStep(
                step_number=len(self.execution_history) + 2 + i,
                action=f"ReAct iteration {i + 1}",
                agent=None,
                module="react",
                input_data={"task": task, "iteration": i},
            )

            # Simulated ReAct iteration
            step.output_data = {
                "thought": f"Thinking about step {i + 1}",
                "action": f"Executing step {i + 1}",
                "observation": f"Observed result of step {i + 1}",
            }
            step.status = "completed"
            steps.append(step)

        output = {
            "status": "completed",
            "task": task,
            "approach": "react",
            "iterations": iterations,
            "result": "Task completed via ReAct pattern",
        }

        return output, steps

    async def _compose_pipeline(
        self, task: str, analysis: TaskAnalysis, context: dict
    ) -> tuple[dict, ExecutionStep]:
        """Compose skills into a pipeline."""
        step = ExecutionStep(
            step_number=len(self.execution_history) + 2,
            action="Composing skill pipeline",
            agent=None,
            module="composer",
            input_data={"task": task, "domains": analysis.domains},
        )

        if "composer" in self._modules and self._modules["composer"]:
            try:
                result = await self._modules["composer"].compose(task)
                pipeline = result.to_dict() if hasattr(result, "to_dict") else {"skills": []}
            except Exception:
                logger.exception(
                    "Error in composer compose for task %s",
                    task.get("id") if isinstance(task, dict) else str(task),
                )
                pipeline = {"skills": analysis.required_capabilities}
        else:
            pipeline = {"skills": analysis.required_capabilities}

        step.output_data = pipeline
        step.status = "completed"

        return pipeline, step

    async def _execute_pipeline(
        self, pipeline: dict, analysis: TaskAnalysis, context: dict
    ) -> tuple[Any, list[ExecutionStep]]:
        """Execute composed pipeline."""
        steps = []
        skills = pipeline.get("skills", [])

        for i, skill in enumerate(skills):
            step = ExecutionStep(
                step_number=len(self.execution_history) + 3 + i,
                action=f"Executing skill: {skill}",
                agent=None,
                module="composer",
                input_data={"skill": skill},
            )
            step.output_data = {"skill": skill, "status": "executed"}
            step.status = "completed"
            steps.append(step)

        output = {
            "status": "completed",
            "approach": "composed",
            "skills_executed": skills,
            "result": "Pipeline executed successfully",
        }

        return output, steps

    async def _execute_collaborative(
        self, task: str, analysis: TaskAnalysis, context: dict
    ) -> tuple[Any, list[ExecutionStep]]:
        """Execute with multiple agents collaborating."""
        steps = []
        agents = analysis.recommended_agents[:3]

        for i, agent in enumerate(agents):
            step = ExecutionStep(
                step_number=len(self.execution_history) + 2 + i,
                action=f"Agent {agent} contribution",
                agent=agent,
                module="messenger",
                input_data={"task": task, "agent": agent},
            )
            step.output_data = {"agent": agent, "contribution": f"Work from {agent}"}
            step.status = "completed"
            steps.append(step)

        # Synthesis step
        synthesis_step = ExecutionStep(
            step_number=len(self.execution_history) + 2 + len(agents),
            action="Synthesizing contributions",
            agent=None,
            module="collab_memory",
            input_data={"agents": agents},
        )
        synthesis_step.output_data = {"synthesis": "Combined work from all agents"}
        synthesis_step.status = "completed"
        steps.append(synthesis_step)

        output = {
            "status": "completed",
            "approach": "collaborative",
            "agents": agents,
            "result": "Collaborative execution completed",
        }

        return output, steps

    async def _execute_adaptive(
        self, task: str, analysis: TaskAnalysis, context: dict
    ) -> tuple[Any, list[ExecutionStep]]:
        """Execute with adaptive strategy changes."""
        steps = []
        current_strategy = ExecutionStrategy.THINK_FIRST

        # Start with thinking
        thinking, think_step = await self._execute_think(task, analysis, context)
        steps.append(think_step)

        # Adapt based on thinking
        if "uncertain" in str(thinking).lower():
            current_strategy = ExecutionStrategy.DEBATE
            debate_result, debate_step = await self._execute_debate(task, analysis, context)
            steps.append(debate_step)

        # Final execution
        exec_step = ExecutionStep(
            step_number=len(self.execution_history) + 2 + len(steps),
            action="Adaptive execution",
            agent=analysis.recommended_agents[0] if analysis.recommended_agents else None,
            module=None,
            input_data={"task": task, "adapted_strategy": current_strategy.value},
        )
        exec_step.output_data = {"result": "Adaptive execution completed"}
        exec_step.status = "completed"
        steps.append(exec_step)

        output = {
            "status": "completed",
            "approach": "adaptive",
            "strategies_used": [current_strategy.value],
            "result": "Adaptive execution completed",
        }

        return output, steps

    async def _detect_emotion(self, text: str) -> dict | None:
        """Detect emotion in text."""
        if "emotion" in self._modules and self._modules["emotion"]:
            try:
                result = await self._modules["emotion"].detect(text)
                return result.to_dict() if hasattr(result, "to_dict") else {"emotion": "neutral"}
            except Exception:
                logger.exception("Error in emotion detection for text (len=%d)", len(text))
        return None

    async def _score_quality(self, output: Any, task: str) -> float:
        """Score output quality."""
        if "quality" in self._modules and self._modules["quality"]:
            try:
                result = await self._modules["quality"].score(str(output), task)
                return result.score if hasattr(result, "score") else 0.7
            except Exception:
                logger.exception("Error in quality scoring")
        return 0.7

    async def _reflect(self, output: Any, task: str, analysis: TaskAnalysis) -> dict | None:
        """Reflect on output."""
        if "reflection" in self._modules and self._modules["reflection"]:
            try:
                result = await self._modules["reflection"].reflect(str(output), task)
                return result.to_dict() if hasattr(result, "to_dict") else None
            except Exception:
                logger.exception("Error in reflection reflect")
        return None

    async def _extract_learnings(
        self, task: str, output: Any, analysis: TaskAnalysis, steps: list[ExecutionStep]
    ) -> list[str]:
        """Extract learnings from execution."""
        learnings = []

        # Strategy effectiveness
        learnings.append(
            f"Strategy '{analysis.recommended_strategy.value}' used for {analysis.complexity.value} task"
        )

        # Domain insights
        if analysis.domains:
            learnings.append(f"Domains involved: {', '.join(analysis.domains)}")

        # Step analysis
        successful_steps = sum(1 for s in steps if s.status == "completed")
        learnings.append(f"{successful_steps}/{len(steps)} steps completed successfully")

        # Risk handling
        if analysis.risk_level > 0.5:
            learnings.append(f"High-risk task (risk={analysis.risk_level:.2f}) handled")

        return learnings

    async def _generate_explanation(
        self, task: str, analysis: TaskAnalysis, steps: list[ExecutionStep], output: Any
    ) -> str:
        """Generate human-readable explanation."""
        if "explainer" in self._modules and self._modules["explainer"]:
            try:
                result = await self._modules["explainer"].explain(
                    {
                        "task": task,
                        "strategy": analysis.recommended_strategy.value,
                        "steps": len(steps),
                    }
                )
                return str(result)
            except Exception:
                logger.exception("Error in explainer explain")

        return (
            f"Task analyzed as {analysis.complexity.value} complexity with "
            f"{len(analysis.domains)} domain(s). Used {analysis.recommended_strategy.value} "
            f"strategy with {len(steps)} execution steps."
        )

    async def _attempt_recovery(self, task: str, error: str, context: dict) -> dict | None:
        """Attempt to recover from error."""
        if "recovery" in self._modules and self._modules["recovery"]:
            try:
                result = await self._modules["recovery"].recover(error, context)
                return result.to_dict() if hasattr(result, "to_dict") else None
            except Exception:
                logger.exception("Error in recovery module")
        return None

    async def _learn_from_execution(self, result: ExecutionResult):
        """Learn from execution for future improvements."""
        if "time_memory" in self._modules and self._modules["time_memory"]:
            with contextlib.suppress(Exception):
                await self._modules["time_memory"].remember(
                    {
                        "task_pattern": result.task[:100],
                        "strategy": result.analysis.recommended_strategy.value,
                        "success": result.success,
                        "quality": result.quality_score,
                    }
                )

        # Alimentar Intelligence Hub con resultado real
        hub = self._get_intelligence_hub()
        if hub:
            try:
                for agent_name in result.analysis.recommended_agents:
                    error_type = None
                    if not result.success and result.metadata.get("error"):
                        error_type = result.metadata["error"][:100]
                    hub.record_outcome(
                        task=result.task,
                        agent_name=agent_name,
                        success=result.success,
                        quality_score=result.quality_score,
                        duration_ms=int(result.total_duration_ms),
                        error_type=error_type,
                    )
            except Exception as e:
                logger.debug("Error alimentando Intelligence Hub: %s", e)

    def _update_stats(self, result: ExecutionResult):
        """Update orchestrator statistics."""
        self.stats["total_executions"] += 1
        if result.success:
            self.stats["successful_executions"] += 1
        self.stats["total_tokens"] += result.tokens_used

        # Update average quality
        total = self.stats["total_executions"]
        prev_avg = self.stats["avg_quality_score"]
        self.stats["avg_quality_score"] = (prev_avg * (total - 1) + result.quality_score) / total

        # Track domains
        for domain in result.analysis.domains:
            self.stats["domains_handled"].add(domain)

        # Track strategies
        strategy = result.analysis.recommended_strategy.value
        self.stats["strategies_used"][strategy] = self.stats["strategies_used"].get(strategy, 0) + 1

    def get_stats(self) -> dict:
        """Get orchestrator statistics."""
        return {
            **self.stats,
            "domains_handled": list(self.stats["domains_handled"]),
            "success_rate": (
                self.stats["successful_executions"] / self.stats["total_executions"]
                if self.stats["total_executions"] > 0
                else 0
            ),
        }

    def export_report(self) -> str:
        """Export orchestrator report."""
        stats = self.get_stats()
        lines = [
            "# Intelligent Orchestrator Report",
            "",
            "## Statistics",
            "",
            f"- **Total Executions:** {stats['total_executions']}",
            f"- **Success Rate:** {stats['success_rate']:.1%}",
            f"- **Average Quality:** {stats['avg_quality_score']:.2f}",
            f"- **Total Tokens:** {stats['total_tokens']}",
            "",
            "## Domains Handled",
            "",
        ]

        for domain in stats["domains_handled"]:
            lines.append(f"- {domain}")

        lines.extend(["", "## Strategies Used", ""])

        for strategy, count in stats["strategies_used"].items():
            lines.append(f"- {strategy}: {count}")

        return "\n".join(lines)


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

_orchestrator: IntelligentOrchestrator | None = None


def get_orchestrator(config: dict | None = None) -> IntelligentOrchestrator:
    """Get or create the intelligent orchestrator."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = IntelligentOrchestrator(config)
    return _orchestrator


async def intelligent_execute(
    task: str, context: dict | None = None, config: dict | None = None
) -> ExecutionResult:
    """Execute task with full intelligence."""
    orchestrator = get_orchestrator(config)
    return await orchestrator.execute(task, context)


async def analyze_task(task: str, context: dict | None = None) -> TaskAnalysis:
    """Analyze task without executing."""
    orchestrator = get_orchestrator()
    return await orchestrator.analyze_task(task, context)


# =============================================================================
# CLI
# =============================================================================


async def main():
    """Main CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Intelligent Orchestrator")
    parser.add_argument("task", nargs="?", help="Task to execute")
    parser.add_argument("--analyze", action="store_true", help="Only analyze, don't execute")
    parser.add_argument("--stats", action="store_true", help="Show statistics")
    parser.add_argument("--report", action="store_true", help="Export report")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    orchestrator = get_orchestrator()

    if args.stats:
        stats = orchestrator.get_stats()
        if args.json:
            print(json.dumps(stats, indent=2))
        else:
            for key, value in stats.items():
                print(f"{key}: {value}")

    elif args.report:
        print(orchestrator.export_report())

    elif args.task:
        if args.analyze:
            analysis = await orchestrator.analyze_task(args.task)
            if args.json:
                print(json.dumps(analysis.to_dict(), indent=2))
            else:
                print(f"Complexity: {analysis.complexity.value}")
                print(f"Strategy: {analysis.recommended_strategy.value}")
                print(f"Domains: {', '.join(analysis.domains)}")
                print(f"Agents: {', '.join(analysis.recommended_agents)}")
                print(f"Risk: {analysis.risk_level:.2f}")
                print(f"Confidence: {analysis.confidence:.2f}")
        else:
            result = await orchestrator.execute(args.task)
            if args.json:
                print(json.dumps(result.to_dict(), indent=2, default=str))
            else:
                print(result.export_report())

    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
