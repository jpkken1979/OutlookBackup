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
from datetime import datetime

# Re-exportaciones de modelos y enums desde el sub-paquete (Plan 018 — paso 1).
# Los consumidores externos siguen importando desde este modulo sin cambios.
from .intelligent_orchestrator_parts.models import (
    ExecutionResult,
    ExecutionStep,
    ExecutionStrategy,
    TaskAnalysis,
    TaskComplexity,
)
from .intelligent_orchestrator_parts.complexity_analyzer import detect_complexity
from .intelligent_orchestrator_parts.agent_recommender import (
    detect_capabilities,
    detect_domains,
    select_agents,
)
from .intelligent_orchestrator_parts.strategy_selector import (
    estimate_steps,
    select_modules,
    select_strategy,
)
from .intelligent_orchestrator_parts.task_warnings import generate_warnings
from .intelligent_orchestrator_parts.execution_engine import ExecutionStrategiesMixin
from .intelligent_orchestrator_parts.module_dispatch import ModuleBackedMixin

# Setup logging
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger("intelligent-orchestrator")


class IntelligentOrchestrator(ExecutionStrategiesMixin, ModuleBackedMixin):
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
                ConfidenceAssessor,
                MultiAgentDebate,
                QualityScorer,
                SelfReflection,
                create_knowledge_graph,
            )

            self._modules["reflection"] = SelfReflection()
            self._modules["cot"] = ChainOfThought()
            self._modules["debate"] = MultiAgentDebate()
            self._modules["metacognition"] = ConfidenceAssessor()
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
        """Detect task complexity.

        Delega a la funcion pura detect_complexity() del sub-paquete (Plan 018).
        La firma del metodo se preserva para que los callers internos sigan
        funcionando sin cambios.
        """
        return detect_complexity(task)

    def _detect_domains(self, task: str) -> list[str]:
        """Detect relevant domains."""
        return detect_domains(task)

    def _detect_capabilities(self, task: str, domains: list[str]) -> list[str]:
        """Detect required capabilities."""
        return detect_capabilities(task, domains)

    def _estimate_steps(self, task: str, complexity: TaskComplexity) -> int:
        """Estimate number of execution steps."""
        return estimate_steps(complexity)

    def _select_strategy(
        self, complexity: TaskComplexity, risk_level: float, domains: list[str]
    ) -> ExecutionStrategy:
        """Select optimal execution strategy."""
        return select_strategy(complexity, risk_level, domains)

    def _select_agents(self, domains: list[str], capabilities: list[str]) -> list[str]:
        """Select optimal agents based on domains and capabilities."""
        return select_agents(domains, capabilities)

    def _select_modules(self, complexity: TaskComplexity, strategy: ExecutionStrategy) -> list[str]:
        """Select intelligence modules to use."""
        return select_modules(complexity, strategy)

    def _generate_warnings(
        self, task: str, risk_level: float, complexity: TaskComplexity
    ) -> list[str]:
        """Generate warnings for the task."""
        return generate_warnings(task, risk_level, complexity)

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
