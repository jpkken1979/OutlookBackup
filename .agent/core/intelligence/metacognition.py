#!/usr/bin/env python3
"""
Metacognition Module - Knowing what you know and don't know.

This module enables agents to:
- Assess their own confidence accurately
- Identify knowledge gaps proactively
- Know when to ask for help
- Calibrate uncertainty appropriately
- Predict when they might fail

Usage:
    from .agent.core.intelligence import Metacognition

    meta = Metacognition()
    assessment = await meta.assess(
        task="Implement OAuth2 with PKCE",
        agent_expertise=["backend", "security"],
        context={"language": "python"}
    )

    if assessment.should_escalate:
        print("Need human input!")
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger("antigravity.intelligence.metacognition")


class KnowledgeLevel(Enum):
    """Levels of knowledge/expertise."""

    EXPERT = "expert"  # Deep, reliable knowledge
    COMPETENT = "competent"  # Solid working knowledge
    FAMILIAR = "familiar"  # Basic understanding
    AWARE = "aware"  # Know it exists
    UNKNOWN = "unknown"  # No knowledge


class UncertaintySource(Enum):
    """Sources of uncertainty."""

    KNOWLEDGE_GAP = "knowledge_gap"  # Don't know enough
    AMBIGUOUS_TASK = "ambiguous_task"  # Task is unclear
    NOVEL_DOMAIN = "novel_domain"  # New/unfamiliar area
    CONFLICTING_INFO = "conflicting_info"  # Contradictory information
    INCOMPLETE_CONTEXT = "incomplete_context"  # Missing information
    COMPLEXITY = "complexity"  # Too complex to be sure
    EXTERNAL_DEPENDENCY = "external_dependency"  # Depends on unknown external factors


class EscalationReason(Enum):
    """Reasons for escalating to human."""

    HIGH_RISK = "high_risk"
    LOW_CONFIDENCE = "low_confidence"
    ETHICAL_CONCERN = "ethical_concern"
    BUSINESS_DECISION = "business_decision"
    NOVEL_SITUATION = "novel_situation"
    CONFLICTING_REQUIREMENTS = "conflicting_requirements"
    RESOURCE_LIMIT = "resource_limit"


@dataclass
class KnowledgeAssessment:
    """Assessment of knowledge in a specific area."""

    area: str
    level: KnowledgeLevel
    confidence_in_assessment: float  # How sure about this assessment
    evidence: list[str]
    gaps: list[str]


@dataclass
class ConfidenceAssessment:
    """Complete metacognitive assessment."""

    task: str
    overall_confidence: float  # 0.0 to 1.0
    calibrated_confidence: float  # Adjusted for known biases
    knowledge_assessments: list[KnowledgeAssessment]
    uncertainty_sources: list[UncertaintySource]
    uncertainty_details: dict[str, str]
    should_escalate: bool
    escalation_reasons: list[EscalationReason]
    questions_to_clarify: list[str]
    knowledge_gaps: list[str]
    assumptions_made: list[str]
    risk_level: str  # low, medium, high, critical
    recommended_approach: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        d = asdict(self)
        d["knowledge_assessments"] = [
            {**asdict(ka), "level": ka.level.value} for ka in self.knowledge_assessments
        ]
        d["uncertainty_sources"] = [us.value for us in self.uncertainty_sources]
        d["escalation_reasons"] = [er.value for er in self.escalation_reasons]
        return d

    def summary(self) -> str:
        """Generate human-readable summary."""
        lines = [
            "## Metacognitive Assessment",
            "",
            f"**Task:** {self.task}",
            f"**Confidence:** {self.overall_confidence:.0%} (calibrated: {self.calibrated_confidence:.0%})",
            f"**Risk Level:** {self.risk_level.upper()}",
            f"**Escalate:** {'YES' if self.should_escalate else 'No'}",
        ]

        if self.escalation_reasons:
            lines.append(
                f"**Escalation Reasons:** {', '.join(r.value for r in self.escalation_reasons)}"
            )

        if self.knowledge_gaps:
            lines.extend(["", "### Knowledge Gaps"])
            for gap in self.knowledge_gaps:
                lines.append(f"- {gap}")

        if self.questions_to_clarify:
            lines.extend(["", "### Questions to Clarify"])
            for q in self.questions_to_clarify:
                lines.append(f"- {q}")

        if self.assumptions_made:
            lines.extend(["", "### Assumptions Made"])
            for a in self.assumptions_made:
                lines.append(f"- {a}")

        lines.extend(["", "### Recommended Approach", self.recommended_approach])

        return "\n".join(lines)


class Metacognition:
    """
    Metacognition engine - self-aware reasoning about knowledge and abilities.

    Enables agents to accurately assess what they know, identify gaps,
    and make informed decisions about when to proceed vs escalate.
    """

    # Known domains and expertise levels
    DOMAIN_EXPERTISE = {
        "python": KnowledgeLevel.EXPERT,
        "javascript": KnowledgeLevel.EXPERT,
        "typescript": KnowledgeLevel.EXPERT,
        "react": KnowledgeLevel.EXPERT,
        "rust": KnowledgeLevel.COMPETENT,
        "security": KnowledgeLevel.COMPETENT,
        "database": KnowledgeLevel.COMPETENT,
        "devops": KnowledgeLevel.COMPETENT,
        "ml": KnowledgeLevel.FAMILIAR,
        "blockchain": KnowledgeLevel.AWARE,
        "quantum": KnowledgeLevel.UNKNOWN,
    }

    # Confidence calibration based on known biases
    OVERCONFIDENCE_DOMAINS = {"security", "performance", "scalability"}
    UNDERCONFIDENCE_DOMAINS = {"documentation", "testing", "simple_tasks"}

    # Risk indicators
    HIGH_RISK_KEYWORDS = {
        "production",
        "deploy",
        "delete",
        "drop",
        "security",
        "auth",
        "payment",
        "pii",
        "sensitive",
        "credential",
        "secret",
        "key",
        "database migration",
        "schema change",
        "irreversible",
    }

    ESCALATION_THRESHOLD = 0.5
    HIGH_RISK_ESCALATION_THRESHOLD = 0.7

    def __init__(
        self,
        memory_dir: Path | None = None,
        domain_expertise: dict[str, KnowledgeLevel] | None = None,
    ):
        self.memory_dir = memory_dir or Path(".agent/memory/metacognition")
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.domain_expertise = domain_expertise or self.DOMAIN_EXPERTISE.copy()
        self.assessment_history: list[ConfidenceAssessment] = []
        logger.info("Metacognition engine initialized")

    async def assess(
        self,
        task: str,
        agent_expertise: list[str] | None = None,
        context: dict[str, Any] | None = None,
        prior_attempts: int = 0,
    ) -> ConfidenceAssessment:
        """
        Perform metacognitive assessment of ability to complete task.

        Args:
            task: The task to assess
            agent_expertise: Agent's areas of expertise
            context: Additional context
            prior_attempts: Number of previous attempts (for adjustment)

        Returns:
            ConfidenceAssessment with detailed self-analysis
        """
        context = context or {}
        agent_expertise = agent_expertise or []

        logger.info(f"Metacognitive assessment for: {task[:50]}...")

        # Extract domains from task
        domains = self._extract_domains(task)

        # Assess knowledge in each domain
        knowledge_assessments = []
        for domain in domains:
            assessment = self._assess_domain_knowledge(domain, agent_expertise)
            knowledge_assessments.append(assessment)

        # Identify uncertainty sources
        uncertainty_sources, uncertainty_details = self._identify_uncertainties(
            task, context, knowledge_assessments
        )

        # Calculate raw confidence
        raw_confidence = self._calculate_raw_confidence(knowledge_assessments)

        # Calibrate confidence
        calibrated = self._calibrate_confidence(raw_confidence, domains, prior_attempts)

        # Assess risk
        risk_level = self._assess_risk(task, context)

        # Determine if escalation needed
        should_escalate, escalation_reasons = self._should_escalate(
            calibrated, risk_level, uncertainty_sources
        )

        # Generate clarifying questions
        questions = self._generate_questions(task, knowledge_assessments, uncertainty_sources)

        # Identify knowledge gaps
        gaps = self._identify_knowledge_gaps(knowledge_assessments)

        # Identify assumptions
        assumptions = self._identify_assumptions(task, context)

        # Recommend approach
        approach = self._recommend_approach(calibrated, risk_level, should_escalate, gaps)

        result = ConfidenceAssessment(
            task=task,
            overall_confidence=raw_confidence,
            calibrated_confidence=calibrated,
            knowledge_assessments=knowledge_assessments,
            uncertainty_sources=uncertainty_sources,
            uncertainty_details=uncertainty_details,
            should_escalate=should_escalate,
            escalation_reasons=escalation_reasons,
            questions_to_clarify=questions,
            knowledge_gaps=gaps,
            assumptions_made=assumptions,
            risk_level=risk_level,
            recommended_approach=approach,
        )

        self.assessment_history.append(result)
        await self._save_assessment(result)

        logger.info(f"Assessment complete: confidence={calibrated:.0%}, escalate={should_escalate}")
        return result

    def _extract_domains(self, task: str) -> set[str]:
        """Extract relevant domains from task description."""
        domains = set()
        task_lower = task.lower()

        # Match against known domains
        domain_keywords = {
            "python": ["python", "pip", "django", "flask", "fastapi"],
            "javascript": ["javascript", "js", "node", "npm", "yarn"],
            "typescript": ["typescript", "ts", "type"],
            "react": ["react", "jsx", "tsx", "hook", "component"],
            "rust": ["rust", "cargo", "crate"],
            "security": ["security", "auth", "password", "token", "encrypt", "vulnerability"],
            "database": ["database", "sql", "postgres", "mysql", "mongodb", "query"],
            "devops": ["deploy", "docker", "kubernetes", "ci/cd", "pipeline"],
            "ml": ["machine learning", "ml", "model", "training", "neural"],
            "api": ["api", "rest", "graphql", "endpoint"],
        }

        for domain, keywords in domain_keywords.items():
            if any(kw in task_lower for kw in keywords):
                domains.add(domain)

        # If no domains identified, mark as novel
        if not domains:
            domains.add("general")

        return domains

    def _assess_domain_knowledge(
        self,
        domain: str,
        agent_expertise: list[str],
    ) -> KnowledgeAssessment:
        """Assess knowledge in a specific domain."""
        # Get base level from known expertise
        base_level = self.domain_expertise.get(domain, KnowledgeLevel.FAMILIAR)

        # Adjust if agent has explicit expertise
        if domain in agent_expertise:
            # Upgrade one level
            level_order = [
                KnowledgeLevel.UNKNOWN,
                KnowledgeLevel.AWARE,
                KnowledgeLevel.FAMILIAR,
                KnowledgeLevel.COMPETENT,
                KnowledgeLevel.EXPERT,
            ]
            current_idx = level_order.index(base_level)
            base_level = level_order[min(current_idx + 1, len(level_order) - 1)]

        # Generate gaps based on level
        gaps = []
        if base_level in [KnowledgeLevel.UNKNOWN, KnowledgeLevel.AWARE]:
            gaps.append(f"Limited understanding of {domain} fundamentals")
        elif base_level == KnowledgeLevel.FAMILIAR:
            gaps.append(f"May miss advanced {domain} patterns")

        return KnowledgeAssessment(
            area=domain,
            level=base_level,
            confidence_in_assessment=0.8,
            evidence=[f"Base knowledge level for {domain}"],
            gaps=gaps,
        )

    def _identify_uncertainties(
        self,
        task: str,
        context: dict[str, Any],
        knowledge: list[KnowledgeAssessment],
    ) -> tuple[list[UncertaintySource], dict[str, str]]:
        """Identify sources of uncertainty."""
        sources = []
        details = {}

        # Check for knowledge gaps
        weak_areas = [
            k for k in knowledge if k.level in [KnowledgeLevel.UNKNOWN, KnowledgeLevel.AWARE]
        ]
        if weak_areas:
            sources.append(UncertaintySource.KNOWLEDGE_GAP)
            details["knowledge_gap"] = f"Weak in: {', '.join(k.area for k in weak_areas)}"

        # Check for ambiguity
        if "?" in task or len(task) < 20:
            sources.append(UncertaintySource.AMBIGUOUS_TASK)
            details["ambiguous_task"] = "Task description may be incomplete"

        # Check for novel domains
        if any(k.level == KnowledgeLevel.UNKNOWN for k in knowledge):
            sources.append(UncertaintySource.NOVEL_DOMAIN)
            details["novel_domain"] = "Task involves unfamiliar domains"

        # Check for missing context
        essential_context = ["requirements", "constraints", "environment"]
        missing = [c for c in essential_context if c not in context]
        if missing:
            sources.append(UncertaintySource.INCOMPLETE_CONTEXT)
            details["incomplete_context"] = f"Missing: {', '.join(missing)}"

        # Check for complexity
        complex_indicators = ["integrate", "migrate", "refactor", "architect", "scale"]
        if any(ind in task.lower() for ind in complex_indicators):
            sources.append(UncertaintySource.COMPLEXITY)
            details["complexity"] = "Task involves complex operations"

        return sources, details

    def _calculate_raw_confidence(self, knowledge: list[KnowledgeAssessment]) -> float:
        """Calculate raw confidence from knowledge assessments."""
        if not knowledge:
            return 0.5

        level_scores = {
            KnowledgeLevel.EXPERT: 0.95,
            KnowledgeLevel.COMPETENT: 0.80,
            KnowledgeLevel.FAMILIAR: 0.60,
            KnowledgeLevel.AWARE: 0.35,
            KnowledgeLevel.UNKNOWN: 0.15,
        }

        scores = [level_scores[k.level] for k in knowledge]
        # Use minimum score weighted with average (pessimistic but not extreme)
        min_score = min(scores)
        avg_score = sum(scores) / len(scores)

        return 0.4 * min_score + 0.6 * avg_score

    def _calibrate_confidence(
        self,
        raw: float,
        domains: set[str],
        prior_attempts: int,
    ) -> float:
        """Calibrate confidence to account for known biases."""
        calibrated = raw

        # Adjust for overconfidence in certain domains
        if domains & self.OVERCONFIDENCE_DOMAINS:
            calibrated *= 0.85  # Reduce by 15%

        # Adjust for underconfidence
        if domains & self.UNDERCONFIDENCE_DOMAINS:
            calibrated = min(1.0, calibrated * 1.1)  # Increase by 10%

        # Adjust for prior attempts (failure = lower confidence)
        if prior_attempts > 0:
            calibrated *= 0.8**prior_attempts

        return max(0.1, min(0.95, calibrated))

    def _assess_risk(self, task: str, context: dict[str, Any]) -> str:
        """Assess risk level of the task."""
        task_lower = task.lower()

        # Count risk indicators
        risk_count = sum(1 for kw in self.HIGH_RISK_KEYWORDS if kw in task_lower)

        # Check context for risk factors
        if context.get("production"):
            risk_count += 2
        if context.get("irreversible"):
            risk_count += 2
        if context.get("affects_users"):
            risk_count += 1

        if risk_count >= 4:
            return "critical"
        elif risk_count >= 2:
            return "high"
        elif risk_count >= 1:
            return "medium"
        return "low"

    def _should_escalate(
        self,
        confidence: float,
        risk: str,
        uncertainties: list[UncertaintySource],
    ) -> tuple[bool, list[EscalationReason]]:
        """Determine if should escalate to human."""
        reasons = []

        # High risk tasks need higher confidence
        if (
            risk == "critical"
            and confidence < 0.9
            or risk == "high"
            and confidence < self.HIGH_RISK_ESCALATION_THRESHOLD
        ):
            reasons.append(EscalationReason.HIGH_RISK)

        # Low confidence
        if confidence < self.ESCALATION_THRESHOLD:
            reasons.append(EscalationReason.LOW_CONFIDENCE)

        # Novel situations
        if UncertaintySource.NOVEL_DOMAIN in uncertainties:
            reasons.append(EscalationReason.NOVEL_SITUATION)

        # Conflicting information
        if UncertaintySource.CONFLICTING_INFO in uncertainties:
            reasons.append(EscalationReason.CONFLICTING_REQUIREMENTS)

        return len(reasons) > 0, reasons

    def _generate_questions(
        self,
        task: str,
        knowledge: list[KnowledgeAssessment],
        uncertainties: list[UncertaintySource],
    ) -> list[str]:
        """Generate clarifying questions."""
        questions = []

        # Questions based on uncertainties
        if UncertaintySource.AMBIGUOUS_TASK in uncertainties:
            questions.append("Can you provide more specific requirements?")

        if UncertaintySource.INCOMPLETE_CONTEXT in uncertainties:
            questions.append("What are the constraints (time, resources, compatibility)?")

        # Questions based on knowledge gaps
        weak_areas = [
            k for k in knowledge if k.level in [KnowledgeLevel.UNKNOWN, KnowledgeLevel.AWARE]
        ]
        for area in weak_areas[:2]:
            questions.append(f"Can you provide guidance on {area.area} requirements?")

        # Standard clarifying questions
        questions.append("What does success look like for this task?")

        return questions[:5]

    def _identify_knowledge_gaps(
        self,
        knowledge: list[KnowledgeAssessment],
    ) -> list[str]:
        """Identify knowledge gaps."""
        gaps = []

        for k in knowledge:
            gaps.extend(k.gaps)

            if k.level == KnowledgeLevel.UNKNOWN:
                gaps.append(f"No knowledge of {k.area}")
            elif k.level == KnowledgeLevel.AWARE:
                gaps.append(f"Only basic awareness of {k.area}")

        return list(set(gaps))[:5]

    def _identify_assumptions(
        self,
        task: str,
        context: dict[str, Any],
    ) -> list[str]:
        """Identify assumptions being made."""
        assumptions = []

        # Common assumptions
        if "existing" not in task.lower():
            assumptions.append("Assuming greenfield implementation (no legacy constraints)")

        if not context.get("environment"):
            assumptions.append("Assuming standard development environment")

        if not context.get("scale"):
            assumptions.append("Assuming moderate scale requirements")

        if not context.get("timeline"):
            assumptions.append("No specific timeline constraints")

        return assumptions[:5]

    def _recommend_approach(
        self,
        confidence: float,
        risk: str,
        escalate: bool,
        gaps: list[str],
    ) -> str:
        """Recommend approach based on assessment."""
        if escalate:
            return (
                "ESCALATE: Request human guidance before proceeding. "
                + f"Key concerns: {', '.join(gaps[:2]) if gaps else 'low confidence'}"
            )

        if confidence >= 0.8 and risk in ["low", "medium"]:
            return "PROCEED: Confidence is sufficient. Execute with standard safeguards."

        if confidence >= 0.6:
            return (
                "PROCEED WITH CAUTION: Execute incrementally, verify each step. "
                + "Consider seeking review for critical sections."
            )

        return (
            "GATHER MORE INFORMATION: Research the gaps before proceeding. "
            + f"Focus on: {', '.join(gaps[:2]) if gaps else 'task requirements'}"
        )

    async def _save_assessment(self, result: ConfidenceAssessment) -> None:
        """Save assessment to disk."""
        try:
            filename = f"metacog_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            filepath = self.memory_dir / filename
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Failed to save assessment: {e}")

    def update_domain_expertise(self, domain: str, level: KnowledgeLevel) -> None:
        """Update domain expertise based on learning."""
        self.domain_expertise[domain] = level
        logger.info(f"Updated expertise: {domain} -> {level.value}")


# Quick assessment function
async def assess_confidence(
    task: str,
    context: dict[str, Any] | None = None,
) -> ConfidenceAssessment:
    """Quick metacognitive assessment."""
    meta = Metacognition()
    return await meta.assess(task, context=context)
