#!/usr/bin/env python3
"""
Explainable Decisions - Generates human-readable decision explanations.

This module provides decision explainability that:
1. Traces decision paths through reasoning
2. Generates human-readable explanations
3. Highlights key factors in decisions
4. Provides confidence breakdowns
5. Creates audit trails for accountability

Usage:
    from .agent.core.intelligence import DecisionExplainer, explain_decision

    explainer = DecisionExplainer()

    # Explain a decision
    explanation = await explainer.explain(
        decision="Use PostgreSQL for the database",
        context={"requirements": ["ACID", "JSON support", "scalability"]},
        alternatives=["MySQL", "MongoDB", "SQLite"]
    )

    print(explanation.summary)
    for factor in explanation.key_factors:
        print(f"  - {factor.name}: {factor.weight:.0%}")
"""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger("antigravity.intelligence.explainable_decisions")


class FactorType(Enum):
    """Types of decision factors."""

    REQUIREMENT = "requirement"  # Must-have requirement
    PREFERENCE = "preference"  # Nice-to-have
    CONSTRAINT = "constraint"  # Limitation
    RISK = "risk"  # Risk consideration
    COST = "cost"  # Cost factor
    PERFORMANCE = "performance"  # Performance factor
    COMPATIBILITY = "compatibility"  # Compatibility with existing
    EXPERTISE = "expertise"  # Team/agent expertise
    PRECEDENT = "precedent"  # Past decisions


class DecisionConfidence(Enum):
    """Confidence levels for decisions."""

    VERY_HIGH = "very_high"  # 90%+
    HIGH = "high"  # 80-90%
    MEDIUM = "medium"  # 60-80%
    LOW = "low"  # 40-60%
    VERY_LOW = "very_low"  # <40%


@dataclass
class DecisionFactor:
    """A factor that influenced a decision."""

    name: str
    factor_type: FactorType
    weight: float  # 0.0 to 1.0
    value: Any
    impact: str  # How it affected decision
    evidence: str  # Supporting evidence
    satisfied: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.factor_type.value,
            "weight": self.weight,
            "value": str(self.value),
            "impact": self.impact,
            "evidence": self.evidence,
            "satisfied": self.satisfied,
        }


@dataclass
class Alternative:
    """An alternative that was considered."""

    name: str
    score: float
    pros: list[str]
    cons: list[str]
    rejection_reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "score": self.score,
            "pros": self.pros,
            "cons": self.cons,
            "rejection_reason": self.rejection_reason,
        }


@dataclass
class DecisionTrace:
    """A step in the decision process."""

    step: int
    action: str
    reasoning: str
    factors_considered: list[str]
    outcome: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "action": self.action,
            "reasoning": self.reasoning,
            "factors_considered": self.factors_considered,
            "outcome": self.outcome,
        }


@dataclass
class DecisionExplanation:
    """Complete explanation of a decision."""

    decision: str
    summary: str
    confidence: DecisionConfidence
    confidence_score: float
    key_factors: list[DecisionFactor]
    decision_trace: list[DecisionTrace]
    alternatives_considered: list[Alternative]
    risks: list[str]
    assumptions: list[str]
    caveats: list[str]
    human_readable: str
    audit_trail: dict[str, Any]
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "summary": self.summary,
            "confidence": self.confidence.value,
            "confidence_score": self.confidence_score,
            "key_factors": [f.to_dict() for f in self.key_factors],
            "decision_trace": [t.to_dict() for t in self.decision_trace],
            "alternatives_considered": [a.to_dict() for a in self.alternatives_considered],
            "risks": self.risks,
            "assumptions": self.assumptions,
            "caveats": self.caveats,
            "human_readable": self.human_readable,
            "created_at": self.created_at.isoformat(),
        }


class FactorAnalyzer:
    """Analyzes and extracts decision factors."""

    def extract_factors(
        self,
        decision: str,
        context: dict[str, Any],
    ) -> list[DecisionFactor]:
        """
        Extract factors from decision context.

        Args:
            decision: The decision made
            context: Context of the decision

        Returns:
            List of decision factors
        """
        factors = []

        # Extract requirements
        requirements = context.get("requirements", [])
        for req in requirements:
            factors.append(
                DecisionFactor(
                    name=f"Requirement: {req}",
                    factor_type=FactorType.REQUIREMENT,
                    weight=0.9,
                    value=req,
                    impact="Must be satisfied",
                    evidence=f"Listed in requirements: {req}",
                    satisfied=self._check_requirement(decision, req),
                )
            )

        # Extract constraints
        constraints = context.get("constraints", [])
        for constraint in constraints:
            factors.append(
                DecisionFactor(
                    name=f"Constraint: {constraint}",
                    factor_type=FactorType.CONSTRAINT,
                    weight=0.8,
                    value=constraint,
                    impact="Limits available options",
                    evidence=f"Constraint: {constraint}",
                )
            )

        # Extract preferences
        preferences = context.get("preferences", [])
        for pref in preferences:
            factors.append(
                DecisionFactor(
                    name=f"Preference: {pref}",
                    factor_type=FactorType.PREFERENCE,
                    weight=0.5,
                    value=pref,
                    impact="Preferred but not required",
                    evidence=f"Preference: {pref}",
                )
            )

        # Analyze implicit factors from decision text
        implicit_factors = self._extract_implicit_factors(decision, context)
        factors.extend(implicit_factors)

        return factors

    def _check_requirement(self, decision: str, requirement: str) -> bool:
        """Check if a requirement is satisfied by the decision."""
        # Simple keyword matching
        decision_lower = decision.lower()
        req_words = requirement.lower().split()
        return any(word in decision_lower for word in req_words)

    def _extract_implicit_factors(
        self,
        decision: str,
        context: dict[str, Any],
    ) -> list[DecisionFactor]:
        """Extract implicit factors from decision analysis."""
        factors = []
        decision_lower = decision.lower()

        # Performance factor
        perf_keywords = ["fast", "performance", "speed", "efficient", "optimize"]
        if any(kw in decision_lower for kw in perf_keywords):
            factors.append(
                DecisionFactor(
                    name="Performance consideration",
                    factor_type=FactorType.PERFORMANCE,
                    weight=0.7,
                    value="High performance required",
                    impact="Prioritizes speed and efficiency",
                    evidence=f"Keywords in decision: {decision[:100]}",
                )
            )

        # Cost factor
        cost_keywords = ["cost", "budget", "expensive", "cheap", "free", "pricing"]
        if any(kw in decision_lower for kw in cost_keywords):
            factors.append(
                DecisionFactor(
                    name="Cost consideration",
                    factor_type=FactorType.COST,
                    weight=0.6,
                    value="Cost-conscious",
                    impact="Budget constraints influence choice",
                    evidence="Cost mentioned in decision",
                )
            )

        # Risk factor
        risk_keywords = ["risk", "safe", "secure", "stable", "proven", "mature"]
        if any(kw in decision_lower for kw in risk_keywords):
            factors.append(
                DecisionFactor(
                    name="Risk mitigation",
                    factor_type=FactorType.RISK,
                    weight=0.7,
                    value="Risk-averse approach",
                    impact="Favors proven, stable solutions",
                    evidence="Safety/risk mentioned in decision",
                )
            )

        return factors


class AlternativeAnalyzer:
    """Analyzes alternatives that were considered."""

    def analyze_alternatives(
        self,
        decision: str,
        alternatives: list[str],
        context: dict[str, Any],
    ) -> list[Alternative]:
        """
        Analyze why alternatives were rejected.

        Args:
            decision: The chosen decision
            alternatives: List of alternatives
            context: Decision context

        Returns:
            List of analyzed alternatives
        """
        analyzed = []

        for alt in alternatives:
            if alt.lower() in decision.lower():
                # This was the chosen option
                continue

            # Analyze pros and cons
            pros, cons = self._analyze_pros_cons(alt, context)

            # Score the alternative
            score = self._score_alternative(alt, pros, cons, context)

            # Generate rejection reason
            rejection = self._generate_rejection_reason(alt, cons, context)

            analyzed.append(
                Alternative(
                    name=alt,
                    score=score,
                    pros=pros,
                    cons=cons,
                    rejection_reason=rejection,
                )
            )

        return analyzed

    def _analyze_pros_cons(
        self,
        alternative: str,
        context: dict[str, Any],
    ) -> tuple:
        """Analyze pros and cons of an alternative."""
        # This would ideally use knowledge about the alternatives
        # For now, we generate based on context
        pros = []
        cons = []

        context.get("requirements", [])

        # Simple heuristic analysis
        alt_lower = alternative.lower()

        # Common technology characteristics
        tech_characteristics = {
            "postgresql": {
                "pros": ["ACID compliance", "JSON support", "Mature ecosystem"],
                "cons": ["More complex setup", "Higher resource usage"],
            },
            "mysql": {
                "pros": ["Wide adoption", "Good performance", "Easy to use"],
                "cons": ["Limited JSON support", "Less advanced features"],
            },
            "mongodb": {
                "pros": ["Flexible schema", "Easy scaling", "Document model"],
                "cons": ["No ACID by default", "Eventual consistency"],
            },
            "sqlite": {
                "pros": ["Zero config", "Lightweight", "File-based"],
                "cons": ["Limited concurrency", "Not for production scale"],
            },
            "react": {
                "pros": ["Large ecosystem", "Virtual DOM", "Component model"],
                "cons": ["Learning curve", "Frequent updates"],
            },
            "vue": {
                "pros": ["Easy learning curve", "Good docs", "Flexible"],
                "cons": ["Smaller ecosystem", "Less jobs"],
            },
        }

        if alt_lower in tech_characteristics:
            chars = tech_characteristics[alt_lower]
            pros = chars["pros"][:3]
            cons = chars["cons"][:2]
        else:
            pros = ["Potential option"]
            cons = ["Unknown characteristics"]

        return pros, cons

    def _score_alternative(
        self,
        alternative: str,
        pros: list[str],
        cons: list[str],
        context: dict[str, Any],
    ) -> float:
        """Score an alternative 0-1."""
        # Base score from pros vs cons
        base_score = len(pros) / (len(pros) + len(cons) + 0.1)

        # Adjust based on requirements match
        requirements = context.get("requirements", [])
        req_match = sum(1 for r in requirements if r.lower() in " ".join(pros).lower())
        req_bonus = req_match * 0.1

        return min(1.0, base_score + req_bonus)

    def _generate_rejection_reason(
        self,
        alternative: str,
        cons: list[str],
        context: dict[str, Any],
    ) -> str:
        """Generate reason for rejecting alternative."""
        requirements = context.get("requirements", [])

        # Check if requirements are unmet
        unmet = []
        for req in requirements:
            req_lower = req.lower()
            if any(con_word in req_lower for con in cons for con_word in con.lower().split()):
                unmet.append(req)

        if unmet:
            return f"Does not fully satisfy: {', '.join(unmet[:2])}"
        elif cons:
            return f"Limitations: {cons[0]}"
        else:
            return "Other option better matched requirements"


class ExplanationGenerator:
    """Generates human-readable explanations."""

    def generate(
        self,
        decision: str,
        factors: list[DecisionFactor],
        alternatives: list[Alternative],
        context: dict[str, Any],
    ) -> str:
        """
        Generate human-readable explanation.

        Args:
            decision: The decision made
            factors: Factors considered
            alternatives: Alternatives analyzed
            context: Decision context

        Returns:
            Human-readable explanation string
        """
        lines = []

        # Opening
        lines.append(f"**Decision:** {decision}")
        lines.append("")

        # Why this was chosen
        lines.append("**Why this choice:**")

        # Key factors
        key_factors = sorted(factors, key=lambda f: f.weight, reverse=True)[:3]
        for factor in key_factors:
            icon = "✓" if factor.satisfied else "○"
            lines.append(f"- {icon} {factor.name} (weight: {factor.weight:.0%})")

        lines.append("")

        # Alternatives considered
        if alternatives:
            lines.append("**Alternatives considered:**")
            for alt in alternatives[:3]:
                lines.append(f"- {alt.name} (score: {alt.score:.0%})")
                lines.append(f"  Rejected: {alt.rejection_reason}")

        lines.append("")

        # Confidence statement
        satisfied_count = sum(1 for f in factors if f.satisfied)
        total_factors = len(factors)
        confidence = satisfied_count / total_factors if total_factors > 0 else 0.5

        if confidence > 0.8:
            lines.append("**Confidence:** High - All major requirements satisfied")
        elif confidence > 0.6:
            lines.append("**Confidence:** Medium - Most requirements satisfied")
        else:
            lines.append("**Confidence:** Low - Some requirements may not be fully met")

        return "\n".join(lines)


class DecisionExplainer:
    """
    Generates explanations for decisions.

    This class:
    1. Analyzes decision factors
    2. Evaluates alternatives
    3. Traces decision process
    4. Generates human-readable explanations
    """

    def __init__(self, memory_dir: Path | None = None):
        # 3-tier resolution: explicit param > env var > user home (NO repo path)
        if memory_dir:
            self.memory_dir = Path(memory_dir)
        elif os.environ.get("ANTIGRAVITY_DECISIONS_PATH"):
            self.memory_dir = Path(os.environ["ANTIGRAVITY_DECISIONS_PATH"])
        else:
            self.memory_dir = Path.home() / ".antigravity" / "memory" / "decisions"
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        self.factor_analyzer = FactorAnalyzer()
        self.alternative_analyzer = AlternativeAnalyzer()
        self.explanation_generator = ExplanationGenerator()

        # History for audit
        self.decision_history: list[DecisionExplanation] = []

    async def explain(
        self,
        decision: str,
        context: dict[str, Any] | None = None,
        alternatives: list[str] | None = None,
        reasoning_trace: list[str] | None = None,
    ) -> DecisionExplanation:
        """
        Explain a decision.

        Args:
            decision: The decision to explain
            context: Context of the decision
            alternatives: Alternatives that were considered
            reasoning_trace: Steps in reasoning (if available)

        Returns:
            DecisionExplanation
        """
        context = context or {}
        alternatives = alternatives or []
        reasoning_trace = reasoning_trace or []

        # Extract factors
        factors = self.factor_analyzer.extract_factors(decision, context)

        # Analyze alternatives
        analyzed_alternatives = self.alternative_analyzer.analyze_alternatives(
            decision, alternatives, context
        )

        # Build decision trace
        trace = self._build_decision_trace(decision, factors, reasoning_trace)

        # Calculate confidence
        confidence_score = self._calculate_confidence(factors)
        confidence = self._score_to_confidence(confidence_score)

        # Generate human-readable explanation
        human_readable = self.explanation_generator.generate(
            decision, factors, analyzed_alternatives, context
        )

        # Identify risks and assumptions
        risks = self._identify_risks(factors, context)
        assumptions = self._identify_assumptions(factors, context)
        caveats = self._identify_caveats(factors, analyzed_alternatives)

        # Build audit trail
        audit_trail = self._build_audit_trail(decision, factors, analyzed_alternatives, context)

        # Generate summary
        summary = self._generate_summary(decision, confidence, factors)

        explanation = DecisionExplanation(
            decision=decision,
            summary=summary,
            confidence=confidence,
            confidence_score=confidence_score,
            key_factors=factors,
            decision_trace=trace,
            alternatives_considered=analyzed_alternatives,
            risks=risks,
            assumptions=assumptions,
            caveats=caveats,
            human_readable=human_readable,
            audit_trail=audit_trail,
        )

        self.decision_history.append(explanation)
        self._save_explanation(explanation)

        return explanation

    def _build_decision_trace(
        self,
        decision: str,
        factors: list[DecisionFactor],
        reasoning: list[str],
    ) -> list[DecisionTrace]:
        """Build decision trace."""
        trace = []

        # Step 1: Understand requirements
        trace.append(
            DecisionTrace(
                step=1,
                action="Analyze requirements",
                reasoning="Identified key requirements and constraints",
                factors_considered=[
                    f.name for f in factors if f.factor_type == FactorType.REQUIREMENT
                ],
                outcome="Requirements understood",
            )
        )

        # Step 2: Evaluate options
        trace.append(
            DecisionTrace(
                step=2,
                action="Evaluate options",
                reasoning="Assessed each option against requirements",
                factors_considered=[f.name for f in factors],
                outcome="Options scored",
            )
        )

        # Step 3: Make decision
        trace.append(
            DecisionTrace(
                step=3,
                action="Select best option",
                reasoning="Chose option that best satisfies requirements",
                factors_considered=[f.name for f in factors if f.weight > 0.7],
                outcome=decision,
            )
        )

        # Add any provided reasoning steps
        for i, step in enumerate(reasoning, start=4):
            trace.append(
                DecisionTrace(
                    step=i,
                    action=f"Additional reasoning {i - 3}",
                    reasoning=step,
                    factors_considered=[],
                    outcome="Continued analysis",
                )
            )

        return trace

    def _calculate_confidence(self, factors: list[DecisionFactor]) -> float:
        """Calculate confidence score."""
        if not factors:
            return 0.5

        # Weighted average of factor satisfaction
        total_weight = sum(f.weight for f in factors)
        satisfied_weight = sum(f.weight for f in factors if f.satisfied)

        return satisfied_weight / total_weight if total_weight > 0 else 0.5

    def _score_to_confidence(self, score: float) -> DecisionConfidence:
        """Convert score to confidence level."""
        if score >= 0.9:
            return DecisionConfidence.VERY_HIGH
        elif score >= 0.8:
            return DecisionConfidence.HIGH
        elif score >= 0.6:
            return DecisionConfidence.MEDIUM
        elif score >= 0.4:
            return DecisionConfidence.LOW
        else:
            return DecisionConfidence.VERY_LOW

    def _identify_risks(
        self,
        factors: list[DecisionFactor],
        context: dict[str, Any],
    ) -> list[str]:
        """Identify risks in the decision."""
        risks = []

        # Unsatisfied requirements are risks
        unsatisfied = [f for f in factors if not f.satisfied]
        for f in unsatisfied[:3]:
            risks.append(f"Unsatisfied factor: {f.name}")

        # Low-weight factors that weren't considered
        low_weight = [f for f in factors if f.weight < 0.3]
        if low_weight:
            risks.append("Some minor factors may have been underweighted")

        # Context-based risks
        if context.get("time_pressure"):
            risks.append("Decision made under time pressure")

        if context.get("incomplete_information"):
            risks.append("Decision made with incomplete information")

        return risks

    def _identify_assumptions(
        self,
        factors: list[DecisionFactor],
        context: dict[str, Any],
    ) -> list[str]:
        """Identify assumptions in the decision."""
        assumptions = []

        # Common assumptions
        if any(f.factor_type == FactorType.PERFORMANCE for f in factors):
            assumptions.append("Assumed performance requirements are accurate")

        if any(f.factor_type == FactorType.COST for f in factors):
            assumptions.append("Assumed budget constraints are fixed")

        if context.get("requirements"):
            assumptions.append("Assumed stated requirements are complete")

        return assumptions

    def _identify_caveats(
        self,
        factors: list[DecisionFactor],
        alternatives: list[Alternative],
    ) -> list[str]:
        """Identify caveats about the decision."""
        caveats = []

        # Close alternatives
        close_alternatives = [a for a in alternatives if a.score > 0.7]
        if close_alternatives:
            caveats.append(f"Alternative '{close_alternatives[0].name}' was a close second")

        # Low confidence factors
        low_conf = [f for f in factors if f.weight < 0.5]
        if len(low_conf) > len(factors) / 2:
            caveats.append("Many factors had low certainty")

        return caveats

    def _build_audit_trail(
        self,
        decision: str,
        factors: list[DecisionFactor],
        alternatives: list[Alternative],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Build audit trail for the decision."""
        return {
            "timestamp": datetime.now().isoformat(),
            "decision": decision,
            "factors_count": len(factors),
            "alternatives_count": len(alternatives),
            "context_keys": list(context.keys()),
            "satisfied_factors": sum(1 for f in factors if f.satisfied),
            "checksum": hash(decision + str(factors)),
        }

    def _generate_summary(
        self,
        decision: str,
        confidence: DecisionConfidence,
        factors: list[DecisionFactor],
    ) -> str:
        """Generate decision summary."""
        key_factors = sorted(factors, key=lambda f: f.weight, reverse=True)[:2]
        factor_names = [f.name.split(": ")[-1] for f in key_factors]

        return (
            f"Decided: {decision}. "
            f"Key factors: {', '.join(factor_names)}. "
            f"Confidence: {confidence.value}."
        )

    def _save_explanation(self, explanation: DecisionExplanation) -> None:
        """Save explanation to disk."""
        filename = f"decision_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = self.memory_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(explanation.to_dict(), f, indent=2, default=str)

    def get_decision_history(self, limit: int = 10) -> list[DecisionExplanation]:
        """Get recent decision history."""
        return self.decision_history[-limit:]

    def export_report(self) -> str:
        """Export decision report as markdown."""
        lines = [
            "# Decision Explanation Report",
            "",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            f"**Total decisions explained:** {len(self.decision_history)}",
            "",
        ]

        for explanation in self.decision_history[-5:]:
            lines.extend(
                [
                    f"## {explanation.decision}",
                    "",
                    explanation.human_readable,
                    "",
                    "---",
                    "",
                ]
            )

        return "\n".join(lines)


# Convenience function
async def explain_decision(
    decision: str,
    context: dict[str, Any] | None = None,
    alternatives: list[str] | None = None,
) -> DecisionExplanation:
    """Quick function to explain a decision."""
    explainer = DecisionExplainer()
    return await explainer.explain(decision, context, alternatives)
