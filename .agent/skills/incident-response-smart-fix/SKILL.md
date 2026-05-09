---
type: feature
name: incident-response-smart-fix
description: "Master intelligent incident response and root cause analysis using AI-assisted debugging, observability, and multi-agent orchestration. Covers 4-phase incident resolution (analysis → investigation → fix → verification), automated root cause detection with git bisect, distributed tracing and structured logging, error telemetry analysis, regression prevention, performance validation, and architectural fixes. Includes patterns for production debugging (safe techniques, minimal risk), automated testing gates, communication protocols, and MTTR reduction. Implements coordination between specialist agents (domain experts, test engineers, DevOps teams) with context sharing. Use when debugging production issues, reducing MTTR, implementing post-mortem improvements, preventing recurring incidents, coordinating multi-team incident response, or automating incident detection/remediation."
---

# Intelligent Incident Response & Root Cause Analysis

Master systematic incident resolution with AI assistance, observability, and multi-agent coordination.

---

## Incident Resolution Phases

```
Phase 1: ANALYSIS
├─ Gather error traces, logs, alerts
├─ Identify symptom vs root cause
├─ Determine blast radius (which users affected)
└─ Establish timeline and reproduction steps

Phase 2: ROOT CAUSE INVESTIGATION
├─ Deep code review (suspects)
├─ Automated git bisect (find introducing commit)
├─ Dependency version checks
├─ Database/cache state inspection
└─ Performance profiling

Phase 3: FIX IMPLEMENTATION
├─ Design minimal fix (avoid scope creep)
├─ Implement with comprehensive tests
├─ Security/performance review
├─ Prepare rollback plan
└─ Stage for production

Phase 4: VERIFICATION
├─ Run regression suites
├─ Benchmark performance
├─ Monitor error rates
├─ Validate no new issues
└─ Post-mortem & prevention
```

---

## Pattern 1: Error Trace Analysis & Reproduction

### Parsing Error Data

```python
from dataclasses import dataclass
from typing import List, Dict
from datetime import datetime

@dataclass
class ErrorTrace:
    """Structured error information."""
    error_id: str
    error_type: str              # Exception class
    message: str
    timestamp: datetime
    user_id: str | None
    request_id: str              # For tracing
    stack_trace: List[str]       # Code location
    context: Dict               # Local variables, request data
    affected_users: int
    error_rate: float            # Errors per minute

class ErrorAnalyzer:
    """Analyze error patterns for RCA."""

    def __init__(self, error_logs: List[ErrorTrace]):
        self.errors = error_logs

    def find_pattern(self) -> Dict:
        """Identify error spike pattern."""
        # Group by time window
        windows = self._group_by_time_window(self.errors, window_minutes=5)

        # Find anomaly (sudden spike)
        baseline = sum(len(w) for w in windows[:3]) / 3  # First 15 min
        spike = max(len(w) for w in windows[3:])         # After 15 min

        if spike > baseline * 3:  # 3x spike
            spike_time = [w for w in windows if len(w) == spike][0][0].timestamp
            return {
                "anomaly": "spike",
                "baseline_errors_per_min": baseline,
                "spike_errors_per_min": spike,
                "spike_started": spike_time,
            }

        return {}

    def analyze_stack_trace(self) -> str:
        """Find most common failure point."""
        # Extract function call
        failing_functions = []

        for error in self.errors:
            # Parse stack trace
            # frame = "  File \"app.py\", line 123, in process_payment"
            if error.stack_trace:
                last_frame = error.stack_trace[-1]  # Innermost frame
                failing_functions.append(last_frame)

        # Most common
        from collections import Counter
        top = Counter(failing_functions).most_common(1)
        return top[0][0] if top else "Unknown"

    def reproduce_error(self) -> Dict:
        """Gather data to reproduce the error."""
        first_error = self.errors[0]

        return {
            "request_id": first_error.request_id,
            "user_id": first_error.user_id,
            "error_type": first_error.error_type,
            "error_message": first_error.message,
            "context": first_error.context,  # Request params, state
            "stack_trace": first_error.stack_trace,
        }

    def _group_by_time_window(self, errors: List[ErrorTrace], window_minutes: int):
        from collections import defaultdict
        windows = defaultdict(list)
        for error in errors:
            bucket = error.timestamp.replace(second=0, microsecond=0)
            bucket = bucket.replace(minute=bucket.minute // window_minutes * window_minutes)
            windows[bucket].append(error)
        return list(windows.values())
```

---

## Pattern 2: Automated Root Cause Detection with Git Bisect

### Finding the Introducing Commit

```bash
#!/bin/bash
# Automated git bisect to find introducing commit

# 1. Start bisect
git bisect start

# 2. Mark current as bad
git bisect bad HEAD

# 3. Mark last known good
git bisect good v2.5.0

# 4. Git will checkout midway commits
# For each commit, run tests:

while true; do
    # Run the failing test
    if pytest tests/test_payment.py::test_process_payment; then
        git bisect good
    else
        git bisect bad
    fi
done

# Output: "Commit abc123 is the first bad commit"
```

```python
import subprocess
from typing import Optional

class AutoBisect:
    """Automated git bisect to find regression."""

    def __init__(self, repo_path: str, test_command: str):
        self.repo_path = repo_path
        self.test_command = test_command
        self.result = None

    def bisect_find_bad_commit(self, good_commit: str, bad_commit: str) -> Optional[str]:
        """Auto-bisect between commits."""

        subprocess.run(
            f"cd {self.repo_path} && git bisect start && git bisect bad {bad_commit} && git bisect good {good_commit}",
            shell=True,
        )

        while True:
            # Run test on current commit
            result = subprocess.run(
                self.test_command,
                shell=True,
                cwd=self.repo_path,
                capture_output=True,
            )

            if result.returncode == 0:
                # Test passed
                subprocess.run("git bisect good", shell=True, cwd=self.repo_path)
            else:
                # Test failed
                subprocess.run("git bisect bad", shell=True, cwd=self.repo_path)

            # Check if bisect is complete
            output = subprocess.check_output(
                "git bisect log",
                shell=True,
                cwd=self.repo_path,
                text=True
            )

            if "is the first bad commit" in output:
                # Extract commit hash
                lines = output.split('\n')
                for line in lines:
                    if "is the first bad commit" in line:
                        commit_hash = line.split()[0]
                        self.result = commit_hash
                        return commit_hash

    def get_commit_info(self, commit_hash: str) -> Dict:
        """Get info about the bad commit."""
        result = subprocess.run(
            f"git show {commit_hash} --stat",
            shell=True,
            cwd=self.repo_path,
            capture_output=True,
            text=True,
        )
        return {"output": result.stdout}
```

---

## Pattern 3: Distributed Tracing for Multi-Service Issues

### Request-ID Based Tracing

```python
import logging
from contextvars import ContextVar
from typing import Optional

# Global context variable
request_context: ContextVar[Optional[str]] = ContextVar('request_id', default=None)

class DistributedTraceLogger:
    """Log with request_id for tracing across services."""

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)

    def log(self, level: int, message: str, **extra):
        """Log with request_id context."""
        request_id = request_context.get()
        if request_id:
            message = f"[{request_id}] {message}"
        self.logger.log(level, message, **extra)

    def info(self, message: str, **extra):
        self.log(logging.INFO, message, **extra)

    def error(self, message: str, **extra):
        self.log(logging.ERROR, message, **extra)

# Usage in Flask/FastAPI
from fastapi import FastAPI, Request
import uuid

app = FastAPI()

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request_context.set(request_id)

    # Pass to downstream services
    headers = request.headers.copy()
    headers["X-Request-ID"] = request_id

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response

@app.get("/api/payment")
async def process_payment(request: Request):
    logger = DistributedTraceLogger(__name__)
    logger.info("Processing payment")  # Logs with request_id prefix
    # ...
```

---

## Pattern 4: Production-Safe Debugging Techniques

### Remote Debugging with Debugpy

```python
# In production code (with feature flag)
import debugpy
import os

if os.getenv("ENABLE_DEBUG") == "true":
    debugpy.listen(("0.0.0.0", 5678))
    print("⏸ Waiting for debugger to attach...")
    debugpy.wait_for_client()

# To debug:
# 1. Export ENABLE_DEBUG=true
# 2. Start app
# 3. In IDE (VS Code), attach debugger: 127.0.0.1:5678
```

### Time-Travel Debugging (Record & Replay)

```python
# Lightweight: Record execution
class ExecutionRecorder:
    def __init__(self):
        self.events = []

    def record_call(self, function_name: str, args: tuple, result: any):
        self.events.append({
            "function": function_name,
            "args": args,
            "result": result,
            "timestamp": time.time(),
        })

    def replay(self):
        """Replay execution to debug."""
        for event in self.events:
            print(f"Call: {event['function']}{event['args']} -> {event['result']}")
```

---

## Pattern 5: Post-Incident Prevention

### Automated Detection Rules

```python
class IncidentPrevention:
    """Generate alerting and prevention measures."""

    @staticmethod
    def suggest_monitoring(error_pattern: Dict) -> List[str]:
        """Generate alerts from incident."""
        alerts = []

        # Alert on error rate spike
        alerts.append(
            'alert: error_rate_spike\n'
            '  if rate(errors_total[5m]) > 100 * baseline\n'
            '  for 2m\n'
            '  annotations:\n'
            '    summary: "Error rate spike detected"\n'
        )

        # Alert on latency increase
        alerts.append(
            'alert: latency_increase\n'
            '  if histogram_quantile(0.95, response_time_ms) > 1000\n'
            '  for 5m\n'
        )

        return alerts

    @staticmethod
    def suggest_code_improvements(root_cause: str) -> List[str]:
        """Suggest architectural improvements."""

        improvements = [
            "Add type hints to prevent silent type errors",
            "Implement circuit breaker for external API calls",
            "Add input validation with Pydantic schemas",
            "Increase test coverage for payment module",
            "Add database query timeout (currently unbounded)",
        ]

        return improvements

    @staticmethod
    def generate_postmortem_template() -> str:
        return """
## Incident Postmortem

### Timeline
- **T+0m**: Error spike detected
- **T+5m**: Root cause identified
- **T+15m**: Fix deployed
- **T+25m**: Monitoring confirms recovery

### Root Cause
[Detailed explanation of underlying cause]

### Contributing Factors
1. Insufficient error handling
2. No circuit breaker for third-party API
3. Missing test coverage

### Immediate Actions
- [ ] Deploy hotfix
- [ ] Monitor metrics
- [ ] Notify affected users

### Follow-up Actions
- [ ] Add circuit breaker pattern
- [ ] Increase test coverage to 90%
- [ ] Implement request timeouts
- [ ] Add better error messages

### Prevention
- Automated alerts on error rate spikes
- Load testing before major releases
- Staged rollouts (5% → 25% → 100%)
"""
```

---

## Best Practices Checklist

| Practice | Why | How |
|----------|-----|-----|
| **Minimize blast radius** | Reduce impact | Use feature flags, staged rollouts |
| **Safe rollback** | Quick recovery | Database migrations are backward-compatible |
| **Correlate errors** | Find root cause | Use request_id + distributed tracing |
| **Automate root cause** | Speed investigation | Git bisect, error pattern matching |
| **Test fix thoroughly** | Prevent regression | Unit + integration + staged rollout |
| **Monitor after deploy** | Catch issues early | Alert on error rate, latency, resource usage |
| **Document learnings** | Prevent recurrence | Postmortem + architectural improvements |

---

## Implementation Checklist

- [ ] Set up centralized logging (ELK, DataDog)
- [ ] Implement distributed tracing (request_id)
- [ ] Create error dashboards (error rate, affected users)
- [ ] Automate git bisect for regression detection
- [ ] Set up alerting rules (error spike, latency)
- [ ] Write incident response runbook
- [ ] Train team on incident coordination
- [ ] Implement feature flags for safe rollbacks
- [ ] Create postmortem template
- [ ] Establish MTTR targets and track progress
