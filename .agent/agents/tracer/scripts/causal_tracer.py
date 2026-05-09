"""Tracer — Causal tracing with competing hypotheses."""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime

@dataclass
class Hypothesis:
    """A competing explanation for observed outcome."""
    name: str
    description: str
    evidence_for: list[str] = field(default_factory=list)
    evidence_against: list[str] = field(default_factory=list)
    confidence: float = 0.5

    def update_confidence(self) -> float:
        """Recalculate confidence based on evidence."""
        total_evidence = len(self.evidence_for) + len(self.evidence_against)
        if total_evidence == 0:
            self.confidence = 0.5
        else:
            self.confidence = len(self.evidence_for) / total_evidence
        return self.confidence


@dataclass
class TraceReport:
    """Complete causal trace report."""
    outcome: str
    timestamp: str
    hypotheses: list[Hypothesis]
    recommended_next_probe: str
    uncertainty_level: str  # high, medium, low

    def format_markdown(self) -> str:
        """Format report with OMC-style markers."""
        lines = [
            f"## Outcome\n{self.outcome}\n",
            f"## Timestamp\n{self.timestamp}\n",
            f"## Hypotheses (uncertainty: {self.uncertainty_level})\n"
        ]
        for h in self.hypotheses:
            lines.append(f"### [HYPOTHESIS] {h.name}")
            lines.append(f"{h.description}\n")
            if h.evidence_for:
                lines.append("[EVIDENCE_FOR]")
                for e in h.evidence_for:
                    lines.append(f"- {e}")
            if h.evidence_against:
                lines.append("[EVIDENCE_AGAINST]")
                for e in h.evidence_against:
                    lines.append(f"- {e}")
            lines.append(f"[UNCERTAINTY] {h.confidence:.2f}\n")
        lines.append(f"[NEXT_PROBE] {self.recommended_next_probe}")
        return "\n".join(lines)


class TracerAgent:
    """Evidence-driven causal tracing with competing hypotheses."""

    def __init__(self):
        self.hypotheses: list[Hypothesis] = []

    def trace(self, outcome: str, context: dict[str, Any]) -> TraceReport:
        """Analyze outcome and generate causal trace report."""
        # Generate initial hypotheses based on outcome
        self.hypotheses = self._generate_hypotheses(outcome, context)

        # Evaluate evidence for each hypothesis
        for hypothesis in self.hypotheses:
            self._collect_evidence(hypothesis, context)

        # Recommend next probe
        most_likely = max(self.hypotheses, key=lambda h: h.confidence)
        next_probe = self._recommend_probe(most_likely, context)

        uncertainty = self._calculate_uncertainty(self.hypotheses)

        return TraceReport(
            outcome=outcome,
            timestamp=datetime.now().isoformat(),
            hypotheses=self.hypotheses,
            recommended_next_probe=next_probe,
            uncertainty_level=uncertainty
        )

    def _generate_hypotheses(self, outcome: str, context: dict[str, Any]) -> list[Hypothesis]:
        """Generate competing hypotheses for outcome."""
        # Common hypothesis patterns based on outcome type
        hypotheses = []

        if "error" in outcome.lower() or "fail" in outcome.lower():
            hypotheses.append(Hypothesis(
                name="Configuration Error",
                description="The failure is caused by incorrect configuration settings",
                evidence_for=[],
                evidence_against=[]
            ))
            hypotheses.append(Hypothesis(
                name="Code Logic Error",
                description="The failure is caused by a bug in the implementation",
                evidence_for=[],
                evidence_against=[]
            ))
            hypotheses.append(Hypothesis(
                name="Dependency Issue",
                description="The failure is caused by a missing or incompatible dependency",
                evidence_for=[],
                evidence_against=[]
            ))
            hypotheses.append(Hypothesis(
                name="Environment Problem",
                description="The failure is caused by environmental factors (permissions, paths, etc.)",
                evidence_for=[],
                evidence_against=[]
            ))
        else:
            # Generic hypothesis
            hypotheses.append(Hypothesis(
                name="Expected Behavior",
                description="The outcome is the expected result based on current implementation",
                evidence_for=[],
                evidence_against=[]
            ))
            hypotheses.append(Hypothesis(
                name="Unexpected Side Effect",
                description="The outcome is caused by an unintended side effect of another change",
                evidence_for=[],
                evidence_against=[]
            ))

        return hypotheses

    def _collect_evidence(self, hypothesis: Hypothesis, context: dict[str, Any]) -> None:
        """Collect evidence for/against hypothesis based on context."""
        outcome = context.get("outcome", "")
        error_logs = context.get("error_logs", "")
        code_changes = context.get("recent_changes", [])

        # Evidence collection logic based on hypothesis type
        if hypothesis.name == "Configuration Error":
            if "config" in outcome.lower() or "env" in outcome.lower():
                hypothesis.evidence_for.append("Outcome mentions configuration or environment")
            if error_logs and ("permission" in error_logs.lower() or "path" in error_logs.lower()):
                hypothesis.evidence_for.append("Error logs suggest path/permission issues")

        elif hypothesis.name == "Code Logic Error":
            if error_logs and ("undefined" in error_logs.lower() or "null" in error_logs.lower()):
                hypothesis.evidence_for.append("Error suggests undefined/null reference")
            if code_changes and len(code_changes) > 0:
                hypothesis.evidence_against.append("Recent code changes may have caused this")

        hypothesis.update_confidence()

    def _recommend_probe(self, hypothesis: Hypothesis, context: dict[str, Any]) -> str:
        """Recommend next investigation step."""
        if hypothesis.name == "Configuration Error":
            return "Check configuration files and environment variables for mismatches"
        elif hypothesis.name == "Code Logic Error":
            return "Review recent code changes and run debugger to trace execution"
        elif hypothesis.name == "Dependency Issue":
            return "Check package.json / requirements.txt for version mismatches"
        elif hypothesis.name == "Environment Problem":
            return "Verify file permissions, path existence, and environment setup"
        else:
            return "Gather more context about the specific conditions that triggered this outcome"

    def _calculate_uncertainty(self, hypotheses: list[Hypothesis]) -> str:
        """Calculate overall uncertainty level."""
        if not hypotheses:
            return "high"
        avg_confidence = sum(h.confidence for h in hypotheses) / len(hypotheses)
        if avg_confidence < 0.3:
            return "high"
        elif avg_confidence < 0.7:
            return "medium"
        return "low"


def main() -> TraceReport:
    """CLI entry point for tracer agent."""
    import sys

    outcome = sys.argv[1] if len(sys.argv) > 1 else "unknown"
    agent = TracerAgent()
    return agent.trace(outcome, {})


if __name__ == "__main__":
    report = main()
    print(report.format_markdown())
