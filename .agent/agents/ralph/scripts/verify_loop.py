"""Ralph — Verify loop agent with evidence-based completion."""
import subprocess
import shlex
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime

@dataclass
class VerificationStep:
    """Single verification step in the loop."""
    iteration: int
    passed: bool
    output: str
    errors: list[str] = field(default_factory=list)
    fix_attempted: bool = False


@dataclass
class RalphReport:
    """Complete Ralph verification loop report."""
    status: str  # PASSED, MAX_ITERATIONS, CANNOT_FIX, STOPPED
    total_iterations: int
    max_iterations: int
    steps: list[VerificationStep]
    final_output: str
    timestamp: str

    def format_markdown(self) -> str:
        status_icon = "[VERIFIED]" if self.status == "PASSED" else "[FAILED]"
        lines = [
            "## Ralph Verification Report\n",
            f"**Status**: {status_icon} {self.status}\n",
            f"**Iterations**: {self.total_iterations}/{self.max_iterations}\n",
            f"**Timestamp**: {self.timestamp}\n",
            "\n### Loop History\n"
        ]
        for step in self.steps:
            icon = "[PASS]" if step.passed else "[FAIL]"
            lines.append(f"- Iter {step.iteration}: {icon}")
            if step.errors:
                for err in step.errors[:3]:  # Show max 3 errors
                    lines.append(f"  - {err[:100]}")
        return "\n".join(lines)


class RalphAgent:
    """Persistent verification agent that loops until complete."""

    def __init__(self, max_iterations: int = 5):
        self.max_iterations = max_iterations
        self.steps: list[VerificationStep] = []
        self.current_iteration = 0
        self._stopped = False

    def verify(self, command: str) -> dict[str, Any]:
        """Run verification command and return result."""
        try:
            result = subprocess.run(
                shlex.split(command),
                shell=False,
                capture_output=True,
                text=True,
                timeout=120
            )
            return {
                "passed": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {
                "passed": False,
                "stdout": "",
                "stderr": "Command timed out after 120 seconds",
                "returncode": -1
            }
        except Exception as e:
            return {
                "passed": False,
                "stdout": "",
                "stderr": str(e),
                "returncode": -1
            }

    def fix_if_needed(self, verification_result: dict[str, Any]) -> dict[str, Any] | None:
        """If verification failed, analyze and attempt to fix."""
        if verification_result["passed"]:
            return None

        errors = verification_result.get("stderr", "")

        # Parse errors to understand what needs fixing
        # This is a simplified version - real implementation would be more sophisticated
        fix_result = {
            "analyzed_errors": errors[:500],
            "fix_location": "unknown",  # Would be determined by error analysis
            "fix_applied": False
        }

        # For now, just report the issue - actual fix would require more context
        return fix_result

    def stop(self):
        """Stop the verification loop."""
        self._stopped = True

    def run_loop(self, verify_cmd: str) -> RalphReport:
        """Run verification loop until passed or max iterations or stopped."""
        self.steps = []
        self.current_iteration = 0
        self._stopped = False
        timestamp = datetime.now().isoformat()

        while self.current_iteration < self.max_iterations:
            if self._stopped:
                return RalphReport(
                    status="STOPPED",
                    total_iterations=self.current_iteration,
                    max_iterations=self.max_iterations,
                    steps=self.steps,
                    final_output="Verification loop stopped by user",
                    timestamp=timestamp
                )

            self.current_iteration += 1

            # Run verification
            result = self.verify(verify_cmd)
            errors = []
            if not result["passed"]:
                errors = result.get("stderr", "").split("\n")[:5]

            step = VerificationStep(
                iteration=self.current_iteration,
                passed=result["passed"],
                output=result.get("stdout", "")[:500],
                errors=errors
            )
            self.steps.append(step)

            if result["passed"]:
                return RalphReport(
                    status="PASSED",
                    total_iterations=self.current_iteration,
                    max_iterations=self.max_iterations,
                    steps=self.steps,
                    final_output=result.get("stdout", "")[:500],
                    timestamp=timestamp
                )

            # Try to fix (simplified - real implementation would do actual fixes)
            fix_result = self.fix_if_needed(result)
            if fix_result:
                step.fix_attempted = True

        return RalphReport(
            status="MAX_ITERATIONS",
            total_iterations=self.current_iteration,
            max_iterations=self.max_iterations,
            steps=self.steps,
            final_output=f"Reached max iterations ({self.max_iterations}) without passing",
            timestamp=timestamp
        )


def main() -> RalphReport:
    """CLI entry point for ralph agent."""
    import sys

    verify_cmd = sys.argv[1] if len(sys.argv) > 1 else "echo 'no command provided'"
    agent = RalphAgent()
    return agent.run_loop(verify_cmd)


if __name__ == "__main__":
    report = main()
    print(report.format_markdown())
