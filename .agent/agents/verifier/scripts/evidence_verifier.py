"""Verifier — Evidence-based completion validation."""
import subprocess
import shlex
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime

@dataclass
class VerificationCriteria:
    """Single acceptance criterion."""
    description: str
    verified: bool
    evidence: str  # Fresh evidence, not assumed
    verification_command: str | None = None


@dataclass
class VerificationReport:
    """Complete verification report with fresh evidence."""
    overall_pass: bool
    timestamp: str
    criteria: list[VerificationCriteria]
    gaps: list[str]
    evidence_summary: str

    def format_markdown(self) -> str:
        lines = [
            "## Verification Report\n",
            f"**Overall**: {'[VERIFIED]' if self.overall_pass else '[FAILED]'}\n",
            f"**Timestamp**: {self.timestamp}\n",
            f"**Evidence Summary**: {self.evidence_summary}\n"
        ]
        if self.gaps:
            lines.append("\n### Gaps")
            for gap in self.gaps:
                lines.append(f"- {gap}")
        lines.append("\n### Criteria Results")
        for c in self.criteria:
            status = "[VERIFIED]" if c.verified else "[FAILED]"
            lines.append(f"- {status} {c.description}")
            if c.evidence:
                # Truncate long evidence
                evidence_preview = c.evidence[:300] + "..." if len(c.evidence) > 300 else c.evidence
                lines.append(f"  Evidence: {evidence_preview}")
        return "\n".join(lines)


class VerifierAgent:
    """Evidence-based verification with fresh validation."""

    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries

    def verify(self, acceptance_criteria: list[str], verification_commands: list[dict[str, str]]) -> VerificationReport:
        """Verify work against acceptance criteria with FRESH evidence."""
        results = []
        timestamp = datetime.now().isoformat()

        # Run fresh verification commands
        for cmd_config in verification_commands:
            cmd = cmd_config.get("command", "")
            description = cmd_config.get("description", "")
            result = self._run_fresh_verification(cmd)
            results.append({
                "description": description,
                "passed": result["passed"],
                "output": result["output"],
                "returncode": result["returncode"]
            })

        # Evaluate against criteria
        criteria_results = []
        gaps = []

        for i, criterion in enumerate(acceptance_criteria):
            if i < len(results):
                verified = results[i].get("passed", False)
                output = results[i].get("output", "")
                evidence = output[:500] if output else "No output captured"
            else:
                verified = False
                evidence = "No verification command provided for this criterion"

            criteria_results.append(VerificationCriteria(
                description=criterion,
                verified=verified,
                evidence=evidence
            ))

            if not verified:
                gaps.append(f"Criterion not met: {criterion}")

        overall_pass = len(gaps) == 0
        passed_count = len([r for r in results if r.get("passed")])
        evidence_summary = f"{passed_count}/{len(results)} checks passed"

        return VerificationReport(
            overall_pass=overall_pass,
            timestamp=timestamp,
            criteria=criteria_results,
            gaps=gaps,
            evidence_summary=evidence_summary
        )

    def _run_fresh_verification(self, command: str) -> dict[str, Any]:
        """Run verification with FRESH evidence (not cached)."""
        try:
            result = subprocess.run(
                shlex.split(command),
                shell=False,
                capture_output=True,
                text=True,
                timeout=60
            )
            return {
                "passed": result.returncode == 0,
                "output": result.stdout + result.stderr,
                "returncode": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {
                "passed": False,
                "output": "Verification command timed out after 60 seconds",
                "returncode": -1
            }
        except Exception as e:
            return {
                "passed": False,
                "output": f"Verification error: {str(e)}",
                "returncode": -1
            }

    def verify_single(self, criterion: str, command: str) -> VerificationCriteria:
        """Verify a single criterion with fresh evidence."""
        result = self._run_fresh_verification(command)
        return VerificationCriteria(
            description=criterion,
            verified=result["passed"],
            evidence=result["output"][:500] if result["output"] else "No output",
            verification_command=command
        )


def main() -> VerificationReport:
    """CLI entry point for verifier agent."""
    agent = VerifierAgent()
    return agent.verify(acceptance_criteria=[], verification_commands=[])


if __name__ == "__main__":
    report = main()
    print(report.format_markdown())
