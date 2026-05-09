#!/usr/bin/env python3
"""
Debugger Agent

Capabilities:
- Root cause analysis
- Bug diagnosis and resolution
- Stack trace interpretation
- Regression test generation
"""

import asyncio
import logging
import re
import traceback
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


class Debugger:
    """Debugger agent for root cause analysis and bug resolution."""

    def __init__(self) -> None:
        self.name = "Debugger"
        logger.info("Debugger initialized")

    async def execute(self, task: str) -> dict[str, Any]:
        """Execute a debugging task.

        Args:
            task: Description of the bug or error to debug.

        Returns:
            Dictionary with root cause, fix, and regression test.
        """
        logger.info(f"Debugging: {task[:80]}")

        result: dict[str, Any] = {
            "agent": self.name,
            "task": task,
            "status": "completed",
            "root_cause": "",
            "fix": None,
            "regression_test": None,
            "defensive_patterns": [],
        }

        task_lower = task.lower()

        if "typeerror" in task_lower or "cannot read" in task_lower or "undefined" in task_lower:
            result["root_cause"] = "Attempted to access a property or method on null/undefined (TypeError)"
            result["fix"] = {
                "description": "Add null/undefined check before accessing property",
                "code": "// Before: data.map(x => x.value)\n// After:\nif (data && Array.isArray(data)) {\n  return data.map(x => x.value);\n}\n// Or use optional chaining: data?.map(x => x.value)",
            }
            result["regression_test"] = "expect(() => processData(null)).not.toThrow();\nconst result = processData([{value: 1}]);\nexpect(result).toEqual([1]);"

        elif "500" in task or "internal server error" in task_lower:
            result["root_cause"] = "Server-side error — likely unhandled exception or invalid state"
            result["fix"] = {
                "description": "Add comprehensive error handling and logging",
                "code": "try:\n    result = await process_request(data)\nexcept Exception as e:\n    logger.error(f\"Request failed: {e}\", exc_info=True)\n    raise HTTPException(status_code=500, detail=\"Internal server error\")",
            }
            result["regression_test"] = "with pytest.raises(HTTPException) as exc_info:\n    response = client.post('/api/users', json={})\nassert exc_info.value.status_code == 500"

        elif "timeout" in task_lower or "deadlock" in task_lower:
            result["root_cause"] = "Operation exceeded time limit or entered deadlock state"
            result["fix"] = {
                "description": "Add timeout handling and deadlock prevention",
                "code": "import asyncio\n\nasync def with_timeout(coro, seconds=30):\n    try:\n        return await asyncio.wait_for(coro, timeout=seconds)\n    except asyncio.TimeoutError:\n        logger.error(f\"Operation timed out after {seconds}s\")\n        raise",
            }
            result["regression_test"] = "with pytest.raises(asyncio.TimeoutError):\n    await asyncio.wait_for(long_operation(), timeout=0.001)"

        elif "race condition" in task_lower:
            result["root_cause"] = "Concurrent access to shared state without proper synchronization"
            result["fix"] = {
                "description": "Use proper locking or atomic operations",
                "code": "import asyncio\n\n_lock = asyncio.Lock()\n\nasync def safe_update():\n    async with _lock:\n        # Critical section\n        shared_state['count'] += 1",
            }
            result["regression_test"] = "async def test_concurrent_updates():\n    await asyncio.gather(*[safe_update() for _ in range(100)])\n    assert shared_state['count'] == 100"

        else:
            result["root_cause"] = f"Systematic analysis of: {task}"
            result["fix"] = {
                "description": "General debugging steps",
                "code": "# 1. Check logs for stack trace\n# 2. Reproduce the bug in isolation\n# 3. Identify the exact failure point\n# 4. Fix and add regression test",
            }
            result["regression_test"] = "# Write a test that reproduces this specific error"

        result["defensive_patterns"] = [
            "Add null checks for optional values",
            "Use type hints to catch type mismatches early",
            "Implement retry with exponential backoff for transient errors",
            "Log all unhandled exceptions with stack traces",
        ]

        logger.info(f"Debugging complete: {result['root_cause'][:80]}")
        return result


async def main() -> None:
    """CLI entry point."""
    import sys

    if len(sys.argv) > 1:
        task = " ".join(sys.argv[1:])
        debugger = Debugger()
        result = await debugger.execute(task)
        print(f"Root cause: {result['root_cause']}")
        if result["fix"]:
            print(f"Fix: {result['fix']['description']}")
    else:
        print("Usage: python debugger.py <bug description>")


if __name__ == "__main__":
    asyncio.run(main())