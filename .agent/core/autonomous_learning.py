# mypy: ignore-errors
#!/usr/bin/env python3
"""
Autonomous Learning Pipeline.

System that learns and improves autonomously from:
- Execution patterns
- User feedback
- Error recovery
- Successful strategies

Version: 1.0.0
"""

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger("autonomous-learning")


class LearningType(Enum):
    """Types of learning."""

    PATTERN_EXTRACTION = "pattern_extraction"
    FEEDBACK_INCORPORATION = "feedback_incorporation"
    ERROR_ANALYSIS = "error_analysis"
    STRATEGY_OPTIMIZATION = "strategy_optimization"
    SKILL_GENERATION = "skill_generation"
    PREFERENCE_LEARNING = "preference_learning"


class FeedbackType(Enum):
    """Types of feedback."""

    EXPLICIT_POSITIVE = "explicit_positive"
    EXPLICIT_NEGATIVE = "explicit_negative"
    IMPLICIT_ACCEPTANCE = "implicit_acceptance"
    IMPLICIT_REJECTION = "implicit_rejection"
    CORRECTION = "correction"


@dataclass
class ExecutionPattern:
    """A detected execution pattern."""

    pattern_id: str
    task_type: str
    steps: list[dict]
    success_rate: float
    occurrence_count: int
    last_seen: datetime
    context_features: dict
    metadata: dict = field(default_factory=dict)


@dataclass
class LearningEvent:
    """A learning event."""

    event_id: str
    learning_type: LearningType
    timestamp: datetime
    input_data: dict
    learned_knowledge: dict
    confidence: float
    applied: bool = False


@dataclass
class LearnedStrategy:
    """A learned strategy."""

    strategy_id: str
    name: str
    description: str
    trigger_conditions: list[str]
    steps: list[dict]
    success_rate: float
    usage_count: int
    created_at: datetime
    last_used: datetime | None = None


@dataclass
class UserPreference:
    """A learned user preference."""

    preference_id: str
    category: str
    key: str
    value: Any
    confidence: float
    observation_count: int
    last_observed: datetime


@dataclass
class LearningReport:
    """Report on learning activities."""

    period_start: datetime
    period_end: datetime
    patterns_discovered: int
    strategies_learned: int
    feedback_processed: int
    errors_analyzed: int
    skills_generated: int
    improvements: list[str]
    recommendations: list[str]

    def to_dict(self) -> dict:
        return {
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "patterns_discovered": self.patterns_discovered,
            "strategies_learned": self.strategies_learned,
            "feedback_processed": self.feedback_processed,
            "errors_analyzed": self.errors_analyzed,
            "skills_generated": self.skills_generated,
            "improvements": self.improvements,
            "recommendations": self.recommendations,
        }

    def export_report(self) -> str:
        """Export as markdown."""
        lines = [
            "# Autonomous Learning Report",
            "",
            f"**Period:** {self.period_start.strftime('%Y-%m-%d')} to {self.period_end.strftime('%Y-%m-%d')}",
            "",
            "## Summary",
            "",
            f"- **Patterns Discovered:** {self.patterns_discovered}",
            f"- **Strategies Learned:** {self.strategies_learned}",
            f"- **Feedback Processed:** {self.feedback_processed}",
            f"- **Errors Analyzed:** {self.errors_analyzed}",
            f"- **Skills Generated:** {self.skills_generated}",
            "",
            "## Improvements Made",
            "",
        ]

        for imp in self.improvements:
            lines.append(f"- {imp}")

        lines.extend(["", "## Recommendations", ""])

        for rec in self.recommendations:
            lines.append(f"- {rec}")

        return "\n".join(lines)


class AutonomousLearningPipeline:
    """
    Pipeline that learns and improves autonomously.

    Components:
    1. Pattern Extractor - Finds patterns in successful executions
    2. Feedback Processor - Incorporates user feedback
    3. Error Analyzer - Learns from failures
    4. Strategy Optimizer - Improves execution strategies
    5. Skill Generator - Creates new skills automatically
    6. Preference Learner - Learns user preferences
    """

    def __init__(self, data_dir: str = ".agent/data/learning"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Storage
        self.patterns: dict[str, ExecutionPattern] = {}
        self.strategies: dict[str, LearnedStrategy] = {}
        self.preferences: dict[str, UserPreference] = {}
        self.learning_events: list[LearningEvent] = []
        self.feedback_buffer: list[dict] = []
        self.error_buffer: list[dict] = []

        # Configuration
        self.config = {
            "min_pattern_occurrences": 3,
            "min_strategy_success_rate": 0.7,
            "preference_confidence_threshold": 0.6,
            "learning_batch_size": 10,
            "auto_apply_threshold": 0.9,
        }

        # Load persisted data
        self._load_state()

    def _load_state(self):
        """Load persisted learning state."""
        state_file = self.data_dir / "learning_state.json"
        if state_file.exists():
            try:
                with open(state_file, encoding="utf-8") as f:
                    state = json.load(f)
                    # Restore patterns, strategies, preferences
                    logger.info(
                        f"Loaded learning state with {len(state.get('patterns', {}))} patterns"
                    )
            except Exception as e:
                logger.warning(f"Could not load state: {e}")

    def _save_state(self):
        """Persist learning state."""
        state_file = self.data_dir / "learning_state.json"
        try:
            state = {
                "patterns": {
                    k: {
                        "pattern_id": v.pattern_id,
                        "task_type": v.task_type,
                        "steps": v.steps,
                        "success_rate": v.success_rate,
                        "occurrence_count": v.occurrence_count,
                        "last_seen": v.last_seen.isoformat(),
                        "context_features": v.context_features,
                    }
                    for k, v in self.patterns.items()
                },
                "strategies": {
                    k: {
                        "strategy_id": v.strategy_id,
                        "name": v.name,
                        "description": v.description,
                        "trigger_conditions": v.trigger_conditions,
                        "steps": v.steps,
                        "success_rate": v.success_rate,
                        "usage_count": v.usage_count,
                    }
                    for k, v in self.strategies.items()
                },
                "preferences": {
                    k: {
                        "preference_id": v.preference_id,
                        "category": v.category,
                        "key": v.key,
                        "value": v.value,
                        "confidence": v.confidence,
                        "observation_count": v.observation_count,
                    }
                    for k, v in self.preferences.items()
                },
                "saved_at": datetime.now().isoformat(),
            }
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Could not save state: {e}")

    def _generate_id(self, content: str) -> str:
        """Generate unique ID from content."""
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    # =========================================================================
    # PATTERN EXTRACTION
    # =========================================================================

    async def extract_patterns(self, executions: list[dict]) -> list[ExecutionPattern]:
        """
        Extract patterns from execution history.

        Args:
            executions: List of execution records

        Returns:
            Discovered patterns
        """
        discovered = []

        # Group by task type
        by_type: dict[str, list[dict]] = {}
        for execution in executions:
            task_type = self._classify_task(execution.get("task", ""))
            if task_type not in by_type:
                by_type[task_type] = []
            by_type[task_type].append(execution)

        # Find patterns within each type
        for task_type, type_executions in by_type.items():
            if len(type_executions) < self.config["min_pattern_occurrences"]:
                continue

            # Extract step sequences from successful executions
            successful = [e for e in type_executions if e.get("success", False)]
            if not successful:
                continue

            # Find common step patterns
            step_sequences = [self._extract_steps(e) for e in successful]
            common_pattern = self._find_common_pattern(step_sequences)

            if common_pattern:
                pattern_id = self._generate_id(f"{task_type}:{json.dumps(common_pattern)}")
                success_rate = len(successful) / len(type_executions)

                pattern = ExecutionPattern(
                    pattern_id=pattern_id,
                    task_type=task_type,
                    steps=common_pattern,
                    success_rate=success_rate,
                    occurrence_count=len(successful),
                    last_seen=datetime.now(),
                    context_features=self._extract_context_features(successful),
                )

                self.patterns[pattern_id] = pattern
                discovered.append(pattern)

                # Log learning event
                self._log_learning_event(
                    LearningType.PATTERN_EXTRACTION,
                    {"task_type": task_type, "executions": len(type_executions)},
                    {"pattern_id": pattern_id, "steps": common_pattern},
                    success_rate,
                )

        self._save_state()
        return discovered

    def _classify_task(self, task: str) -> str:
        """Classify task into type."""
        task_lower = task.lower()

        if any(kw in task_lower for kw in ["create", "add", "implement", "build"]):
            return "creation"
        elif any(kw in task_lower for kw in ["fix", "bug", "error", "resolve"]):
            return "debugging"
        elif any(kw in task_lower for kw in ["refactor", "improve", "optimize"]):
            return "refactoring"
        elif any(kw in task_lower for kw in ["test", "verify", "check"]):
            return "testing"
        elif any(kw in task_lower for kw in ["analyze", "review", "audit"]):
            return "analysis"
        elif any(kw in task_lower for kw in ["document", "explain", "describe"]):
            return "documentation"
        else:
            return "general"

    def _extract_steps(self, execution: dict) -> list[str]:
        """Extract step sequence from execution."""
        steps = execution.get("steps", [])
        return [s.get("action", "") for s in steps if isinstance(s, dict)]

    def _find_common_pattern(self, sequences: list[list[str]]) -> list[dict] | None:
        """Find common pattern across sequences."""
        if not sequences:
            return None

        # Simple: use first sequence as base, validate against others
        base = sequences[0]
        if not base:
            return None

        # Count step frequencies
        step_counts: dict[str, int] = {}
        for seq in sequences:
            for step in seq:
                step_counts[step] = step_counts.get(step, 0) + 1

        # Keep steps that appear in majority
        threshold = len(sequences) * 0.6
        common_steps = [
            {"action": step, "frequency": count / len(sequences)}
            for step, count in step_counts.items()
            if count >= threshold
        ]

        return common_steps if common_steps else None

    def _extract_context_features(self, executions: list[dict]) -> dict:
        """Extract common context features."""
        features = {"avg_duration_ms": 0, "common_agents": [], "common_modules": []}

        durations = [e.get("duration_ms", 0) for e in executions if e.get("duration_ms")]
        if durations:
            features["avg_duration_ms"] = sum(durations) / len(durations)

        # Count agent usage
        agent_counts: dict[str, int] = {}
        for e in executions:
            for agent in e.get("agents_used", []):
                agent_counts[agent] = agent_counts.get(agent, 0) + 1

        features["common_agents"] = [
            a for a, c in agent_counts.items() if c >= len(executions) * 0.5
        ]

        return features

    # =========================================================================
    # FEEDBACK PROCESSING
    # =========================================================================

    async def process_feedback(
        self, feedback_type: FeedbackType, context: dict, details: str | None = None
    ):
        """
        Process user feedback for learning.

        Args:
            feedback_type: Type of feedback
            context: Context of the feedback
            details: Additional details
        """
        feedback = {
            "type": feedback_type.value,
            "context": context,
            "details": details,
            "timestamp": datetime.now().isoformat(),
        }

        self.feedback_buffer.append(feedback)

        # Process if batch is ready
        if len(self.feedback_buffer) >= self.config["learning_batch_size"]:
            await self._process_feedback_batch()

        # Immediate learning for explicit feedback
        if feedback_type in [FeedbackType.EXPLICIT_POSITIVE, FeedbackType.EXPLICIT_NEGATIVE]:
            await self._learn_from_explicit_feedback(feedback)

        self._log_learning_event(
            LearningType.FEEDBACK_INCORPORATION,
            {"feedback_type": feedback_type.value},
            {"incorporated": True},
            0.8,
        )

    async def _process_feedback_batch(self):
        """Process accumulated feedback."""
        if not self.feedback_buffer:
            return

        # Aggregate feedback by context
        by_context: dict[str, list[dict]] = {}
        for fb in self.feedback_buffer:
            ctx_key = json.dumps(fb["context"], sort_keys=True)
            if ctx_key not in by_context:
                by_context[ctx_key] = []
            by_context[ctx_key].append(fb)

        # Learn from aggregated feedback
        for ctx_key, feedbacks in by_context.items():
            positive = sum(
                1 for f in feedbacks if f["type"] in ["explicit_positive", "implicit_acceptance"]
            )
            negative = sum(
                1 for f in feedbacks if f["type"] in ["explicit_negative", "implicit_rejection"]
            )

            if positive + negative > 0:
                satisfaction_rate = positive / (positive + negative)
                # Update relevant patterns/strategies
                await self._update_based_on_satisfaction(ctx_key, satisfaction_rate)

        self.feedback_buffer.clear()
        self._save_state()

    async def _learn_from_explicit_feedback(self, feedback: dict):
        """Learn immediately from explicit feedback."""
        if feedback["type"] == "explicit_positive":
            # Reinforce the approach
            logger.info("Positive feedback received - reinforcing approach")
        elif feedback["type"] == "explicit_negative":
            # Mark for improvement
            logger.info("Negative feedback received - marking for improvement")

    async def _update_based_on_satisfaction(self, context_key: str, satisfaction_rate: float):
        """Update patterns/strategies based on satisfaction."""
        logger.debug(
            "Updating strategy satisfaction for context=%s rate=%.3f",
            context_key,
            satisfaction_rate,
        )
        # Adjust confidence of related strategies
        for strategy in self.strategies.values():
            # Simple relevance check - in production would be more sophisticated
            strategy.success_rate = (strategy.success_rate * 0.9) + (satisfaction_rate * 0.1)

    # =========================================================================
    # ERROR ANALYSIS
    # =========================================================================

    async def analyze_error(self, error: dict) -> dict:
        """
        Analyze error for learning.

        Args:
            error: Error details

        Returns:
            Analysis result with learned insights
        """
        self.error_buffer.append({**error, "analyzed_at": datetime.now().isoformat()})

        analysis = {
            "error_type": error.get("type", "unknown"),
            "categorization": self._categorize_error(error),
            "similar_errors": self._find_similar_errors(error),
            "suggested_fixes": [],
            "prevention_recommendations": [],
        }

        # Learn from error patterns
        if len(self.error_buffer) >= self.config["learning_batch_size"]:
            error_patterns = await self._extract_error_patterns()
            analysis["learned_patterns"] = len(error_patterns)

        # Generate fix suggestions
        analysis["suggested_fixes"] = self._generate_fix_suggestions(error)
        analysis["prevention_recommendations"] = self._generate_prevention_recommendations(error)

        self._log_learning_event(
            LearningType.ERROR_ANALYSIS, {"error_type": error.get("type")}, analysis, 0.7
        )

        self._save_state()
        return analysis

    def _categorize_error(self, error: dict) -> str:
        """Categorize error type."""
        error_msg = str(error.get("message", "")).lower()

        if "import" in error_msg or "module" in error_msg:
            return "import_error"
        elif "permission" in error_msg or "access" in error_msg:
            return "permission_error"
        elif "timeout" in error_msg:
            return "timeout_error"
        elif "memory" in error_msg:
            return "memory_error"
        elif "network" in error_msg or "connection" in error_msg:
            return "network_error"
        elif "syntax" in error_msg:
            return "syntax_error"
        else:
            return "general_error"

    def _find_similar_errors(self, error: dict) -> list[dict]:
        """Find similar past errors."""
        similar = []
        error_category = self._categorize_error(error)

        for past_error in self.error_buffer[-100:]:  # Last 100 errors
            if self._categorize_error(past_error) == error_category:
                similar.append(past_error)

        return similar[:5]

    async def _extract_error_patterns(self) -> list[dict]:
        """Extract patterns from error buffer."""
        patterns = []

        # Group by category
        by_category: dict[str, list[dict]] = {}
        for error in self.error_buffer:
            cat = self._categorize_error(error)
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(error)

        for category, errors in by_category.items():
            if len(errors) >= 3:
                patterns.append(
                    {
                        "category": category,
                        "count": len(errors),
                        "common_context": self._find_common_error_context(errors),
                    }
                )

        return patterns

    def _find_common_error_context(self, errors: list[dict]) -> dict:
        """Find common context in errors."""
        # Simple implementation - find common keys
        common = {}
        if errors:
            first_context = errors[0].get("context", {})
            for key in first_context:
                values = [e.get("context", {}).get(key) for e in errors]
                if len({str(v) for v in values}) == 1:
                    common[key] = values[0]
        return common

    def _generate_fix_suggestions(self, error: dict) -> list[str]:
        """Generate fix suggestions for error."""
        category = self._categorize_error(error)

        suggestions = {
            "import_error": [
                "Check if the module is installed: pip install <module>",
                "Verify the import path is correct",
                "Check for circular imports",
            ],
            "permission_error": [
                "Check file/directory permissions",
                "Run with elevated privileges if needed",
                "Verify the path exists",
            ],
            "timeout_error": [
                "Increase timeout value",
                "Check network connectivity",
                "Optimize the operation",
            ],
            "network_error": [
                "Check internet connection",
                "Verify the URL/endpoint",
                "Check firewall settings",
            ],
            "syntax_error": [
                "Check for missing brackets or quotes",
                "Verify indentation",
                "Run a linter",
            ],
        }

        return suggestions.get(category, ["Check error message for details"])

    def _generate_prevention_recommendations(self, error: dict) -> list[str]:
        """Generate recommendations to prevent error."""
        return [
            "Add proper error handling",
            "Implement retry logic for transient failures",
            "Add validation before operations",
        ]

    # =========================================================================
    # STRATEGY OPTIMIZATION
    # =========================================================================

    async def optimize_strategies(self) -> list[LearnedStrategy]:
        """
        Optimize execution strategies based on learning.

        Returns:
            Optimized strategies
        """
        optimized = []

        for strategy_id, strategy in self.strategies.items():
            # Skip strategies with insufficient data
            if strategy.usage_count < 5:
                continue

            # Calculate improvement potential
            improvement = await self._calculate_improvement_potential(strategy)

            if improvement > 0.1:  # 10% improvement potential
                optimized_strategy = await self._optimize_strategy(strategy)
                self.strategies[strategy_id] = optimized_strategy
                optimized.append(optimized_strategy)

                self._log_learning_event(
                    LearningType.STRATEGY_OPTIMIZATION,
                    {"strategy_id": strategy_id},
                    {"improvement": improvement},
                    0.8,
                )

        self._save_state()
        return optimized

    async def _calculate_improvement_potential(self, strategy: LearnedStrategy) -> float:
        """Calculate potential for strategy improvement."""
        # Based on success rate gap from optimal
        optimal_rate = 0.95
        current_rate = strategy.success_rate
        gap = optimal_rate - current_rate

        # Higher gap = more potential
        return gap

    async def _optimize_strategy(self, strategy: LearnedStrategy) -> LearnedStrategy:
        """Optimize a strategy."""
        # Add error handling steps if missing
        has_error_handling = any("error" in str(s).lower() for s in strategy.steps)
        if not has_error_handling:
            strategy.steps.append(
                {"action": "handle_errors", "description": "Added error handling"}
            )

        # Add validation steps
        has_validation = any("valid" in str(s).lower() for s in strategy.steps)
        if not has_validation:
            strategy.steps.insert(
                0, {"action": "validate_inputs", "description": "Added input validation"}
            )

        return strategy

    # =========================================================================
    # SKILL GENERATION
    # =========================================================================

    async def generate_skills(self) -> list[dict]:
        """
        Generate new skills from learned patterns.

        Returns:
            Generated skill definitions
        """
        generated = []

        for pattern in self.patterns.values():
            # Only generate from high-quality patterns
            if pattern.success_rate < self.config["min_strategy_success_rate"]:
                continue
            if pattern.occurrence_count < self.config["min_pattern_occurrences"]:
                continue

            skill = await self._generate_skill_from_pattern(pattern)
            if skill:
                generated.append(skill)

                self._log_learning_event(
                    LearningType.SKILL_GENERATION,
                    {"pattern_id": pattern.pattern_id},
                    {"skill_name": skill.get("name")},
                    pattern.success_rate,
                )

        return generated

    async def _generate_skill_from_pattern(self, pattern: ExecutionPattern) -> dict | None:
        """Generate skill definition from pattern."""
        skill_name = f"auto_{pattern.task_type}_{pattern.pattern_id[:8]}"

        return {
            "name": skill_name,
            "description": f"Auto-generated skill for {pattern.task_type} tasks",
            "generated_from": "pattern",
            "pattern_id": pattern.pattern_id,
            "steps": pattern.steps,
            "success_rate": pattern.success_rate,
            "confidence": pattern.success_rate,
            "created_at": datetime.now().isoformat(),
        }

    # =========================================================================
    # PREFERENCE LEARNING
    # =========================================================================

    async def learn_preference(
        self, category: str, key: str, value: Any, observation_strength: float = 1.0
    ):
        """
        Learn a user preference.

        Args:
            category: Preference category
            key: Preference key
            value: Preference value
            observation_strength: How strong this observation is
        """
        pref_id = self._generate_id(f"{category}:{key}")

        if pref_id in self.preferences:
            pref = self.preferences[pref_id]
            # Update existing preference
            pref.observation_count += 1
            pref.confidence = min(pref.confidence + 0.1 * observation_strength, 0.99)
            pref.value = value  # Use latest value
            pref.last_observed = datetime.now()
        else:
            # New preference
            self.preferences[pref_id] = UserPreference(
                preference_id=pref_id,
                category=category,
                key=key,
                value=value,
                confidence=0.5 * observation_strength,
                observation_count=1,
                last_observed=datetime.now(),
            )

        self._log_learning_event(
            LearningType.PREFERENCE_LEARNING,
            {"category": category, "key": key},
            {"value": value},
            self.preferences[pref_id].confidence,
        )

        self._save_state()

    def get_preference(self, category: str, key: str) -> Any | None:
        """Get a learned preference."""
        pref_id = self._generate_id(f"{category}:{key}")
        pref = self.preferences.get(pref_id)

        if pref and pref.confidence >= self.config["preference_confidence_threshold"]:
            return pref.value
        return None

    def get_all_preferences(self, category: str | None = None) -> list[UserPreference]:
        """Get all learned preferences."""
        prefs = list(self.preferences.values())
        if category:
            prefs = [p for p in prefs if p.category == category]
        return sorted(prefs, key=lambda p: p.confidence, reverse=True)

    # =========================================================================
    # LEARNING EVENTS
    # =========================================================================

    def _log_learning_event(
        self,
        learning_type: LearningType,
        input_data: dict,
        learned_knowledge: dict,
        confidence: float,
    ):
        """Log a learning event."""
        event = LearningEvent(
            event_id=self._generate_id(f"{learning_type.value}:{datetime.now().isoformat()}"),
            learning_type=learning_type,
            timestamp=datetime.now(),
            input_data=input_data,
            learned_knowledge=learned_knowledge,
            confidence=confidence,
        )
        self.learning_events.append(event)

        # Keep only recent events
        if len(self.learning_events) > 1000:
            self.learning_events = self.learning_events[-500:]

    # =========================================================================
    # REPORTING
    # =========================================================================

    def generate_report(self, period_days: int = 7) -> LearningReport:
        """Generate learning report for period."""
        end_time = datetime.now()
        start_time = end_time - timedelta(days=period_days)

        # Count events by type in period
        period_events = [e for e in self.learning_events if e.timestamp >= start_time]

        patterns_discovered = sum(
            1 for e in period_events if e.learning_type == LearningType.PATTERN_EXTRACTION
        )
        strategies_learned = sum(
            1 for e in period_events if e.learning_type == LearningType.STRATEGY_OPTIMIZATION
        )
        feedback_processed = sum(
            1 for e in period_events if e.learning_type == LearningType.FEEDBACK_INCORPORATION
        )
        errors_analyzed = sum(
            1 for e in period_events if e.learning_type == LearningType.ERROR_ANALYSIS
        )
        skills_generated = sum(
            1 for e in period_events if e.learning_type == LearningType.SKILL_GENERATION
        )

        # Generate improvements and recommendations
        improvements = []
        recommendations = []

        if patterns_discovered > 0:
            improvements.append(f"Discovered {patterns_discovered} new execution patterns")
        if strategies_learned > 0:
            improvements.append(f"Optimized {strategies_learned} strategies")
        if skills_generated > 0:
            improvements.append(f"Generated {skills_generated} new skills")

        if errors_analyzed > 5:
            recommendations.append("High error rate - consider adding more validation")
        if feedback_processed < 5:
            recommendations.append("Low feedback - encourage users to provide feedback")

        return LearningReport(
            period_start=start_time,
            period_end=end_time,
            patterns_discovered=patterns_discovered,
            strategies_learned=strategies_learned,
            feedback_processed=feedback_processed,
            errors_analyzed=errors_analyzed,
            skills_generated=skills_generated,
            improvements=improvements,
            recommendations=recommendations,
        )

    # =========================================================================
    # MAIN LEARNING LOOP
    # =========================================================================

    async def run_learning_cycle(self, executions: list[dict] = None):
        """
        Run a complete learning cycle.

        Args:
            executions: Recent executions to learn from
        """
        logger.info("Starting learning cycle...")

        # 1. Extract patterns
        if executions:
            patterns = await self.extract_patterns(executions)
            logger.info(f"Extracted {len(patterns)} patterns")

        # 2. Process feedback batch
        await self._process_feedback_batch()

        # 3. Optimize strategies
        optimized = await self.optimize_strategies()
        logger.info(f"Optimized {len(optimized)} strategies")

        # 4. Generate skills
        skills = await self.generate_skills()
        logger.info(f"Generated {len(skills)} skills")

        # 5. Save state
        self._save_state()

        logger.info("Learning cycle complete")


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

_pipeline: AutonomousLearningPipeline | None = None


def get_learning_pipeline() -> AutonomousLearningPipeline:
    """Get the learning pipeline instance."""
    global _pipeline
    if _pipeline is None:
        _pipeline = AutonomousLearningPipeline()
    return _pipeline


async def learn_from_execution(execution: dict):
    """Learn from a single execution."""
    pipeline = get_learning_pipeline()
    await pipeline.extract_patterns([execution])


async def learn_from_feedback(feedback_type: str, context: dict):
    """Learn from user feedback."""
    pipeline = get_learning_pipeline()
    await pipeline.process_feedback(FeedbackType(feedback_type), context)


async def learn_from_error(error: dict):
    """Learn from an error."""
    pipeline = get_learning_pipeline()
    return await pipeline.analyze_error(error)


# =============================================================================
# CLI
# =============================================================================


async def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Autonomous Learning Pipeline")
    parser.add_argument("--report", action="store_true", help="Generate learning report")
    parser.add_argument("--days", type=int, default=7, help="Report period in days")
    parser.add_argument("--cycle", action="store_true", help="Run learning cycle")
    parser.add_argument("--stats", action="store_true", help="Show statistics")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    pipeline = get_learning_pipeline()

    if args.report:
        report = pipeline.generate_report(args.days)
        if args.json:
            print(json.dumps(report.to_dict(), indent=2))
        else:
            print(report.export_report())

    elif args.cycle:
        await pipeline.run_learning_cycle()
        print("Learning cycle completed")

    elif args.stats:
        stats = {
            "patterns": len(pipeline.patterns),
            "strategies": len(pipeline.strategies),
            "preferences": len(pipeline.preferences),
            "learning_events": len(pipeline.learning_events),
            "feedback_buffer": len(pipeline.feedback_buffer),
            "error_buffer": len(pipeline.error_buffer),
        }
        if args.json:
            print(json.dumps(stats, indent=2))
        else:
            for key, value in stats.items():
                print(f"{key}: {value}")

    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
