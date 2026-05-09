# mypy: ignore-errors
#!/usr/bin/env python3
"""
Active Reflection System (MARS-inspired)

Implements continuous reflection during task execution, not just post-hoc.

Based on: MARS (Metacognitive Agent Reflective Self-improvement)
- Principle-based reflection: Abstract normative rules to avoid errors
- Procedural reflection: Derive step-by-step strategies for success

Key Benefits:
- Catches errors during execution, not after
- Enables adaptive strategy adjustment
- Generates transparent reasoning traces
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger("antigravity.active_reflection")


class ReflectionLevel(Enum):
    """Levels of reflection intensity."""

    NONE = "none"  # No reflection (fast mode)
    LIGHT = "light"  # Quick sanity checks
    STANDARD = "standard"  # Normal reflection
    DEEP = "deep"  # Thorough analysis (slower)


class ConcernSeverity(Enum):
    """Severity levels for identified concerns."""

    INFO = "info"  # Informational
    WARNING = "warning"  # Potential issue
    ERROR = "error"  # Likely problem
    CRITICAL = "critical"  # Must address immediately


@dataclass
class ReflectionCheckpoint:
    """Checkpoint during active reflection."""

    step_number: int
    timestamp: str
    agent: str
    task: str

    # What was done
    action_taken: str
    partial_output: str

    # Reflection results
    principle_check: dict = field(default_factory=dict)
    procedural_check: dict = field(default_factory=dict)
    concerns: list[dict] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)

    # Scores
    confidence: float = 0.8
    on_track: bool = True
    should_continue: bool = True
    should_adjust: bool = False

    # Inner monologue
    inner_monologue: str = ""

    def to_dict(self) -> dict:
        return {
            "step_number": self.step_number,
            "timestamp": self.timestamp,
            "agent": self.agent,
            "task": self.task,
            "action_taken": self.action_taken,
            "partial_output_length": len(self.partial_output),
            "principle_check": self.principle_check,
            "procedural_check": self.procedural_check,
            "concerns": self.concerns,
            "suggestions": self.suggestions,
            "confidence": self.confidence,
            "on_track": self.on_track,
            "should_continue": self.should_continue,
            "should_adjust": self.should_adjust,
            "inner_monologue": self.inner_monologue,
        }


@dataclass
class StrategyAdjustment:
    """Recommended strategy adjustment."""

    reason: str
    original_approach: str
    recommended_approach: str
    confidence: float
    supporting_evidence: list[str] = field(default_factory=list)


@dataclass
class ReflectionSession:
    """Complete reflection session for a task."""

    task_id: str
    task_description: str
    agent: str
    started_at: str
    ended_at: str | None = None

    checkpoints: list[ReflectionCheckpoint] = field(default_factory=list)
    adjustments_made: list[StrategyAdjustment] = field(default_factory=list)
    final_confidence: float = 0.0
    success: bool = False

    def get_summary(self) -> dict:
        return {
            "task_id": self.task_id,
            "agent": self.agent,
            "checkpoints": len(self.checkpoints),
            "adjustments": len(self.adjustments_made),
            "final_confidence": self.final_confidence,
            "success": self.success,
            "concerns_raised": sum(len(c.concerns) for c in self.checkpoints),
        }


class ActiveReflection:
    """
    MARS-inspired active reflection during task execution.

    Features:
    - Principle-based reflection: Check against normative rules
    - Procedural reflection: Verify step-by-step strategy
    - Inner monologue: Generate transparent reasoning traces
    - Adaptive adjustment: Recommend strategy changes when needed

    Usage:
        reflection = ActiveReflection(level=ReflectionLevel.STANDARD)

        # Start session
        session = reflection.start_session("task_123", "Implement auth", "coder")

        # Reflect at each step
        for step in execution_steps:
            checkpoint = await reflection.reflect_on_step(
                session=session,
                action="Wrote validation logic",
                partial_output=current_code
            )

            if checkpoint.should_adjust:
                # Handle strategy adjustment
                adjustment = await reflection.suggest_adjustment(session)

        # End session
        reflection.end_session(session, success=True)
    """

    # Core principles that guide reflection
    PRINCIPLES = {
        "completeness": {
            "description": "Output should address all aspects of the task",
            "check_patterns": ["TODO", "FIXME", "incomplete", "missing"],
            "weight": 0.25,
        },
        "correctness": {
            "description": "Output should be factually and technically correct",
            "check_patterns": ["maybe", "possibly", "not sure", "I think"],
            "weight": 0.25,
        },
        "safety": {
            "description": "Output should not introduce security vulnerabilities",
            "check_patterns": ["eval(", "exec(", "shell=True", "password=", "secret="],
            "weight": 0.2,
        },
        "clarity": {
            "description": "Output should be clear and well-structured",
            "check_patterns": [],  # Structural analysis instead
            "weight": 0.15,
        },
        "efficiency": {
            "description": "Approach should be reasonably efficient",
            "check_patterns": ["O(n^2)", "O(n^3)", "nested loop", "slow"],
            "weight": 0.15,
        },
    }

    # Task type to expected procedure mapping
    PROCEDURES = {
        "implementation": [
            "understand_requirements",
            "check_existing_code",
            "design_solution",
            "implement",
            "validate",
        ],
        "debugging": [
            "reproduce_issue",
            "identify_root_cause",
            "propose_fix",
            "implement_fix",
            "verify_fix",
        ],
        "refactoring": [
            "understand_current_code",
            "identify_improvements",
            "plan_changes",
            "make_changes",
            "verify_behavior",
        ],
        "security_audit": [
            "scan_codebase",
            "identify_vulnerabilities",
            "assess_severity",
            "recommend_fixes",
            "document_findings",
        ],
    }

    def __init__(
        self, level: ReflectionLevel = ReflectionLevel.STANDARD, reflection_interval: int = 3
    ):
        self.level = level
        self.reflection_interval = reflection_interval
        self._sessions: dict[str, ReflectionSession] = {}
        self._step_counter: dict[str, int] = {}

    def start_session(self, task_id: str, task_description: str, agent: str) -> ReflectionSession:
        """Start a new reflection session for a task."""
        session = ReflectionSession(
            task_id=task_id,
            task_description=task_description,
            agent=agent,
            started_at=datetime.now().isoformat(),
        )
        self._sessions[task_id] = session
        self._step_counter[task_id] = 0

        logger.info(f"Started reflection session for task {task_id}")
        return session

    def end_session(
        self, session: ReflectionSession, success: bool, final_output: str = ""
    ) -> ReflectionSession:
        """End a reflection session."""
        session.ended_at = datetime.now().isoformat()
        session.success = success

        # Calculate final confidence based on checkpoints
        if session.checkpoints:
            avg_confidence = sum(c.confidence for c in session.checkpoints) / len(
                session.checkpoints
            )
            concern_penalty = sum(0.05 * len(c.concerns) for c in session.checkpoints)
            adjustment_penalty = 0.03 * len(session.adjustments_made)

            session.final_confidence = max(
                0.0, avg_confidence - concern_penalty - adjustment_penalty
            )
        else:
            session.final_confidence = 0.5  # Unknown

        logger.info(
            f"Ended reflection session for task {session.task_id} (success={success}, confidence={session.final_confidence:.2f})"
        )
        return session

    async def reflect_on_step(
        self,
        session: ReflectionSession,
        action: str,
        partial_output: str,
        context: dict | None = None,
    ) -> ReflectionCheckpoint:
        """
        Perform reflection at a step.

        Args:
            session: Current reflection session
            action: Description of action taken
            partial_output: Current output/state
            context: Additional context

        Returns:
            ReflectionCheckpoint with analysis and recommendations
        """
        self._step_counter[session.task_id] += 1
        step_num = self._step_counter[session.task_id]

        # Skip reflection if level is NONE or interval not reached
        if self.level == ReflectionLevel.NONE:
            return self._create_skip_checkpoint(session, step_num, action, partial_output)

        if step_num % self.reflection_interval != 0 and self.level != ReflectionLevel.DEEP:
            return self._create_skip_checkpoint(session, step_num, action, partial_output)

        # Perform reflection
        checkpoint = ReflectionCheckpoint(
            step_number=step_num,
            timestamp=datetime.now().isoformat(),
            agent=session.agent,
            task=session.task_description,
            action_taken=action,
            partial_output=partial_output,
        )

        # Principle-based reflection
        checkpoint.principle_check = await self._check_principles(partial_output, context)

        # Procedural reflection
        checkpoint.procedural_check = await self._check_procedure(
            session, step_num, action, context
        )

        # Identify concerns
        checkpoint.concerns = await self._identify_concerns(
            checkpoint.principle_check, checkpoint.procedural_check, partial_output
        )

        # Generate suggestions
        checkpoint.suggestions = await self._generate_suggestions(checkpoint)

        # Calculate confidence and track status
        checkpoint.confidence = self._calculate_confidence(checkpoint)
        checkpoint.on_track = checkpoint.confidence >= 0.6
        checkpoint.should_continue = checkpoint.confidence >= 0.4
        checkpoint.should_adjust = len(checkpoint.concerns) > 2 or checkpoint.confidence < 0.5

        # Generate inner monologue
        checkpoint.inner_monologue = await self._generate_inner_monologue(checkpoint)

        # Add to session
        session.checkpoints.append(checkpoint)

        if checkpoint.concerns:
            logger.warning(f"Step {step_num} raised {len(checkpoint.concerns)} concerns")

        return checkpoint

    async def suggest_adjustment(self, session: ReflectionSession) -> StrategyAdjustment | None:
        """
        Suggest strategy adjustment based on reflection history.

        Returns:
            StrategyAdjustment if adjustment needed, None otherwise
        """
        if not session.checkpoints:
            return None

        recent_checkpoints = session.checkpoints[-3:]  # Last 3 checkpoints
        all_concerns = []
        for cp in recent_checkpoints:
            all_concerns.extend(cp.concerns)

        if not all_concerns:
            return None

        # Analyze concern patterns
        concern_types = [c.get("type", "unknown") for c in all_concerns]
        most_common = max(set(concern_types), key=concern_types.count)

        # Generate adjustment recommendation
        adjustment = StrategyAdjustment(
            reason=f"Repeated concerns of type '{most_common}' detected",
            original_approach=session.checkpoints[0].action_taken
            if session.checkpoints
            else "unknown",
            recommended_approach=self._recommend_approach(most_common, all_concerns),
            confidence=0.7,
            supporting_evidence=[c.get("description", "") for c in all_concerns[:3]],
        )

        session.adjustments_made.append(adjustment)
        return adjustment

    def _create_skip_checkpoint(
        self, session: ReflectionSession, step_num: int, action: str, partial_output: str
    ) -> ReflectionCheckpoint:
        """Create a minimal checkpoint when reflection is skipped."""
        return ReflectionCheckpoint(
            step_number=step_num,
            timestamp=datetime.now().isoformat(),
            agent=session.agent,
            task=session.task_description,
            action_taken=action,
            partial_output=partial_output,
            confidence=0.8,  # Default confidence
            on_track=True,
            should_continue=True,
            inner_monologue="[Reflection skipped for this step]",
        )

    async def _check_principles(self, output: str, context: dict | None) -> dict:
        """Check output against core principles."""
        results = {}

        for principle_name, principle_def in self.PRINCIPLES.items():
            check_result = {"passed": True, "score": 1.0, "issues": []}

            # Check for problematic patterns
            output_lower = output.lower()
            for pattern in principle_def["check_patterns"]:
                if pattern.lower() in output_lower:
                    check_result["passed"] = False
                    check_result["score"] -= 0.2
                    check_result["issues"].append(f"Found '{pattern}'")

            check_result["score"] = max(0.0, check_result["score"])
            results[principle_name] = check_result

        return results

    async def _check_procedure(
        self, session: ReflectionSession, step_num: int, action: str, context: dict | None
    ) -> dict:
        """Check if procedure is being followed correctly."""
        task_type = self._infer_task_type(session.task_description)
        expected_procedure = self.PROCEDURES.get(task_type, [])

        if not expected_procedure:
            return {"status": "unknown", "message": "Task type not recognized"}

        # Estimate current phase based on step number
        total_phases = len(expected_procedure)
        expected_phase_index = min(
            int((step_num / 10) * total_phases),  # Assume ~10 steps total
            total_phases - 1,
        )
        expected_phase = expected_procedure[expected_phase_index]

        # Simple heuristic check
        action_lower = action.lower()
        phase_matches = expected_phase.replace("_", " ") in action_lower

        return {
            "task_type": task_type,
            "expected_phase": expected_phase,
            "phase_index": expected_phase_index,
            "total_phases": total_phases,
            "phase_matches": phase_matches,
            "status": "on_track" if phase_matches else "uncertain",
        }

    async def _identify_concerns(
        self, principle_check: dict, procedural_check: dict, output: str
    ) -> list[dict]:
        """Identify concerns from checks."""
        concerns = []

        # Principle concerns
        for principle, result in principle_check.items():
            if not result.get("passed", True):
                for issue in result.get("issues", []):
                    concerns.append(
                        {
                            "type": "principle_violation",
                            "principle": principle,
                            "severity": ConcernSeverity.WARNING.value,
                            "description": f"{principle}: {issue}",
                        }
                    )

        # Procedural concerns
        if procedural_check.get("status") == "uncertain":
            concerns.append(
                {
                    "type": "procedural",
                    "severity": ConcernSeverity.INFO.value,
                    "description": f"Current action may not align with expected phase: {procedural_check.get('expected_phase')}",
                }
            )

        # Output length concern
        if len(output) < 50:
            concerns.append(
                {
                    "type": "completeness",
                    "severity": ConcernSeverity.WARNING.value,
                    "description": "Output seems very short - may be incomplete",
                }
            )

        return concerns

    async def _generate_suggestions(self, checkpoint: ReflectionCheckpoint) -> list[str]:
        """Generate actionable suggestions based on concerns."""
        suggestions = []

        for concern in checkpoint.concerns:
            concern_type = concern.get("type", "")

            if concern_type == "principle_violation":
                principle = concern.get("principle", "")
                if principle == "safety":
                    suggestions.append("Review code for security vulnerabilities before proceeding")
                elif principle == "completeness":
                    suggestions.append("Ensure all requirements are addressed")
                elif principle == "correctness":
                    suggestions.append("Verify technical accuracy of the solution")

            elif concern_type == "procedural":
                suggestions.append("Consider revisiting the expected workflow for this task type")

            elif concern_type == "completeness":
                suggestions.append("Expand output to fully address the task")

        return list(set(suggestions))  # Deduplicate

    def _calculate_confidence(self, checkpoint: ReflectionCheckpoint) -> float:
        """Calculate confidence score for checkpoint."""
        base_confidence = 0.8

        # Adjust based on principle checks
        for principle, result in checkpoint.principle_check.items():
            weight = self.PRINCIPLES[principle]["weight"]
            score = result.get("score", 1.0)
            base_confidence += (score - 0.8) * weight

        # Penalty for concerns
        base_confidence -= 0.05 * len(checkpoint.concerns)

        # Bonus for procedural alignment
        if checkpoint.procedural_check.get("phase_matches", False):
            base_confidence += 0.05

        return max(0.0, min(1.0, base_confidence))

    async def _generate_inner_monologue(self, checkpoint: ReflectionCheckpoint) -> str:
        """Generate inner monologue for transparency."""
        parts = []

        # State assessment
        if checkpoint.on_track:
            parts.append(f"Step {checkpoint.step_number}: Progress looks good.")
        else:
            parts.append(f"Step {checkpoint.step_number}: Some concerns identified.")

        # Principle summary
        failed_principles = [
            p for p, r in checkpoint.principle_check.items() if not r.get("passed", True)
        ]
        if failed_principles:
            parts.append(f"Principles needing attention: {', '.join(failed_principles)}.")

        # Concerns
        if checkpoint.concerns:
            severity_counts = {}
            for c in checkpoint.concerns:
                sev = c.get("severity", "info")
                severity_counts[sev] = severity_counts.get(sev, 0) + 1
            parts.append(f"Concerns: {severity_counts}.")

        # Confidence
        parts.append(f"Confidence: {checkpoint.confidence:.0%}.")

        # Recommendation
        if checkpoint.should_adjust:
            parts.append("RECOMMEND: Strategy adjustment may be needed.")
        elif not checkpoint.should_continue:
            parts.append("ALERT: Consider stopping and reassessing.")

        return " ".join(parts)

    def _infer_task_type(self, task_description: str) -> str:
        """Infer task type from description."""
        task_lower = task_description.lower()

        if any(w in task_lower for w in ["fix", "bug", "error", "issue", "debug"]):
            return "debugging"
        elif any(w in task_lower for w in ["refactor", "clean", "improve", "optimize"]):
            return "refactoring"
        elif any(w in task_lower for w in ["security", "audit", "vulnerability", "scan"]):
            return "security_audit"
        else:
            return "implementation"

    def _recommend_approach(self, concern_type: str, concerns: list[dict]) -> str:
        """Recommend alternative approach based on concerns."""
        recommendations = {
            "principle_violation": "Slow down and review against principles before proceeding",
            "procedural": "Return to the expected workflow phase",
            "completeness": "Add more detail and ensure all aspects are covered",
            "safety": "Perform security review before continuing",
        }
        return recommendations.get(
            concern_type, "Review current approach and consider alternatives"
        )

    def get_session(self, task_id: str) -> ReflectionSession | None:
        """Get a reflection session by task ID."""
        return self._sessions.get(task_id)

    def get_all_sessions(self) -> list[ReflectionSession]:
        """Get all reflection sessions."""
        return list(self._sessions.values())


# Singleton instance
_active_reflection_instance: ActiveReflection | None = None


def get_active_reflection(level: ReflectionLevel = ReflectionLevel.STANDARD) -> ActiveReflection:
    """Get or create the active reflection instance."""
    global _active_reflection_instance
    if _active_reflection_instance is None:
        _active_reflection_instance = ActiveReflection(level=level)
    return _active_reflection_instance


# =============================================================================
# Demo
# =============================================================================


async def demo():
    """Demonstrate active reflection."""
    reflection = ActiveReflection(
        level=ReflectionLevel.STANDARD,
        reflection_interval=1,  # Reflect every step for demo
    )

    # Start session
    session = reflection.start_session(
        task_id="demo_001",
        task_description="Implement JWT authentication for the API",
        agent="coder",
    )

    # Simulate execution steps
    steps = [
        ("Analyzed requirements", "Need JWT auth with refresh tokens"),
        ("Checked existing code", "Found auth.py with basic validation"),
        ("Designed solution", "Will use PyJWT with RS256, TODO: add refresh logic"),
        (
            "Implementing JWT generation",
            "def generate_token(user): secret = 'hardcoded_secret_key'",
        ),
        ("Added refresh token logic", "Implemented full JWT flow with proper key management"),
    ]

    print("=== Active Reflection Demo ===\n")

    for action, output in steps:
        checkpoint = await reflection.reflect_on_step(
            session=session, action=action, partial_output=output
        )

        print(f"Step {checkpoint.step_number}: {action}")
        print(f"  Inner monologue: {checkpoint.inner_monologue}")
        if checkpoint.concerns:
            print(f"  Concerns: {len(checkpoint.concerns)}")
            for c in checkpoint.concerns:
                print(f"    - [{c['severity']}] {c['description']}")
        if checkpoint.should_adjust:
            adjustment = await reflection.suggest_adjustment(session)
            if adjustment:
                print(f"  ADJUSTMENT: {adjustment.recommended_approach}")
        print()

    # End session
    reflection.end_session(session, success=True)

    print("=== Session Summary ===")
    summary = session.get_summary()
    for k, v in summary.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    asyncio.run(demo())
