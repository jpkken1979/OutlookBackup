---
name: observability-monitoring-slo-implement
description: Implement SLO/SLI frameworks with error budgets. Design reliability targets, measure service performance, and balance reliability with feature velocity using data-driven error budget allocation.
category: monitoring
version: 2.1.0
tags:
type: feature
---
  - SLO
  - SLI
  - error-budget
  - reliability
  - observability
  - alerts
requires:
  python_modules:
    - prometheus_client
    - datadog
  optional:
    - splunk
    - prometheus
triggers:
  - "SLO|SLI|error budget"
  - "reliability target|uptime"
  - "service level objective"
type: feature
---

# SLO Implementation Guide

Design comprehensive SLO/SLI frameworks that establish reliability targets, measure service performance, and balance reliability with feature velocity using error budgets.

## Core Concepts

### SLI / SLO / SLA Hierarchy

```
SLI (Service Level Indicator)
  ↓ (Measured value, e.g., 99.95% availability)

SLO (Service Level Objective)
  ↓ (Internal target, e.g., 99.9% availability)

SLA (Service Level Agreement)
  ↓ (Contract commitment with penalties)
```

### Common SLI Types

**Availability/Uptime**
- % of successful requests (HTTP 2xx/3xx)
- Endpoint reachability
- Database connection success

**Latency**
- Response time (p50, p95, p99)
- Query execution time
- Time-to-first-byte

**Correctness**
- Error rate (5xx, validation failures)
- Data consistency checks
- Replay/retry rate

**Freshness (for data systems)**
- Data staleness (max age)
- Pipeline lag
- Cache hit ratio

## Use this skill when

- Defining SLIs/SLOs and error budgets for services
- Building SLO dashboards, alerts, and reporting
- Aligning reliability targets with business priorities
- Setting error budget burn alerts
- Implementing canary deployments with SLO gates
- Standardizing reliability practices across teams
- Making go/no-go deployment decisions

## Do not use this skill when

- You only need basic monitoring without reliability targets
- There is no access to service telemetry or metrics
- The task is unrelated to service reliability
- Stakeholder alignment on reliability is undefined

## SLO Definition Template

```yaml
service: payment-processor
owner: payments-team
tier: critical  # critical, standard, best-effort

slos:
  - name: request_success_rate
    description: "Successful payment transactions"
    sli:
      metric: request_success_rate
      filters:
        method: "POST"
        path: "/v1/transactions"
    objectives:
      - target: 99.95%
        window: 30d
      - target: 99.9%
        window: 7d
    error_budget:
      monthly_allowed_errors: 0.05%  # 14.4 minutes downtime/month
    alert_threshold: 95%  # Alert if 1/3 of budget burned

  - name: request_latency_p99
    description: "Transaction latency (99th percentile)"
    sli:
      metric: request_latency_ms
      percentile: 99
      filters:
        path: "/v1/transactions"
    objectives:
      - target: 500ms
        window: 30d
    alert_threshold: 450ms

  - name: database_replication_lag
    description: "Replication lag to read replicas"
    sli:
      metric: postgres_replication_lag_seconds
      filters:
        slot: "standby_*"
    objectives:
      - target: < 5s
        window: 30d
    alert_threshold: 3s
```

## Error Budget Calculation

```python
from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass
class ErrorBudget:
    """Error budget tracking and allocation."""
    sli_target: float  # e.g., 0.9999 for 99.99%
    window_days: int

    @property
    def allowed_error_rate(self) -> float:
        """Fraction of time service can be down."""
        return 1 - self.sli_target

    @property
    def downtime_minutes(self) -> float:
        """Total downtime allowed in window."""
        return self.allowed_error_rate * self.window_days * 24 * 60

    def calculate_burn_rate(
        self,
        actual_error_rate: float,
        sli_target: float
    ) -> float:
        """How fast is budget being consumed?"""
        allowed_rate = 1 - sli_target
        if allowed_rate == 0:
            return float('inf') if actual_error_rate > 0 else 0
        return actual_error_rate / allowed_rate

    def remaining_budget(
        self,
        errors_so_far: int,
        total_requests: int,
        days_elapsed: int
    ) -> float:
        """Remaining error budget as percentage."""
        budget_used = errors_so_far / total_requests
        budget_available = self.allowed_error_rate
        return max(0, (budget_available - budget_used) / budget_available * 100)

# Example
budget = ErrorBudget(sli_target=0.9995, window_days=30)
print(f"SLO Target: 99.95%")
print(f"Allowed error rate: {budget.allowed_error_rate:.4%}")
print(f"Max downtime: {budget.downtime_minutes:.1f} minutes/month")

# Track burn
burn_rate = budget.calculate_burn_rate(
    actual_error_rate=0.001,  # 0.1% errors
    sli_target=0.9995
)
print(f"Burn rate: {burn_rate:.1f}x")  # How many "SLO lifetimes" used per day
```

## Alert Strategy: Multi-Window Burn Alerts

```python
class BurnRateAlert:
    """Detect SLO breaches early with multi-window burn alerts."""

    ALERT_RULES = [
        # Fast burn (will exceed budget in 1 hour if continues)
        {"window": "5m", "burn_rate": 36, "severity": "critical"},
        # Medium burn (will exceed budget in 1 day)
        {"window": "30m", "burn_rate": 6, "severity": "warning"},
        # Slow burn (will exceed budget in 1 week)
        {"window": "2h", "burn_rate": 1, "severity": "info"},
    ]

    def check_alert(self, actual_burn_rate: float) -> dict | None:
        """Return alert if burn rate exceeds threshold."""
        for rule in self.ALERT_RULES:
            if actual_burn_rate >= rule["burn_rate"]:
                return {
                    "severity": rule["severity"],
                    "message": f"High error rate detected",
                    "burn_rate": actual_burn_rate,
                    "window": rule["window"],
                    "action": "Page on-call" if rule["severity"] == "critical" else "Create ticket"
                }
        return None
```

## Prometheus SLO Implementation

```yaml
# prometheus/slo_rules.yml
groups:
  - name: slo_rules
    interval: 30s
    rules:
      # Record SLI
      - record: sli:request_success_rate:ratio
        expr: |
          sum(rate(http_requests_total{status=~"2.."}[5m]))
          / sum(rate(http_requests_total[5m]))

      # Calculate error budget remaining
      - record: slo:error_budget_remaining:percent
        expr: |
          100 * (1 - (1 - sli:request_success_rate:ratio) / (1 - 0.9995))

      # Burn rate alert
      - alert: HighErrorRate
        expr: |
          (1 - sli:request_success_rate:ratio) > 0.0005
        for: 5m
        annotations:
          summary: "Error rate breaching SLO for {{ $labels.job }}"
```

## Deployment Gate with SLO Validation

```python
class DeploymentGate:
    """Block deployments if SLO is at risk."""

    def can_deploy(self, current_burn_rate: float, slo_target: float) -> bool:
        """
        Allow deployment only if error budget is healthy.

        Rule: Don't deploy if > 50% of monthly budget already consumed
        """
        allowed_error_rate = 1 - slo_target
        days_in_month = 30
        days_elapsed = self._days_since_month_start()

        budget_daily = allowed_error_rate / days_in_month
        budget_consumed = current_burn_rate * days_elapsed

        if budget_consumed > allowed_error_rate * 0.5:
            return False  # Block deployment
        return True

    def deployment_risk_report(self, metrics: dict) -> str:
        """Generate risk report for deployment decision."""
        return f"""
        Current error rate: {metrics['error_rate']:.3%}
        Error budget remaining: {metrics['budget_remaining']:.1f}%
        Burn rate: {metrics['burn_rate']:.1f}x

        ✓ SAFE TO DEPLOY if error budget > 25%
        ⚠ CAUTION if error budget 10-25%
        ✗ BLOCK DEPLOYMENT if error budget < 10%
        """
```

## Implementation Checklist

- [ ] **Identify**: List all critical services and their SLI candidates
- [ ] **Measure**: Set up metrics/logging to calculate SLIs
- [ ] **Define**: Agree on SLO targets with stakeholders
- [ ] **Calculate**: Compute error budgets and burndown windows
- [ ] **Alert**: Configure multi-window burn rate alerts
- [ ] **Visualize**: Build dashboards showing budget remaining
- [ ] **Automate**: Integrate SLOs into deployment gates
- [ ] **Review**: Quarterly SLO review and adjustment process

## Anti-Patterns to Avoid

- ❌ SLOs set without stakeholder alignment (too high → unrealistic, too low → overspend)
- ❌ Alerting on SLO breach after it happens (use burn rate alerts instead)
- ❌ Static SLOs that don't adapt (review quarterly)
- ❌ SLOs without error budget (no guidance on feature velocity vs reliability)
- ❌ Ignoring toil/labor in SLO calculations (toil = undifferentiated manual work)

## Best Practices

✅ **Set SLOs based on business impact**, not technical metrics
✅ **Use error budgets to enable fast iteration** (don't waste budget on toil)
✅ **Alert on burn rate**, not on absolute SLO breach
✅ **Review SLOs quarterly** — adjust based on real data
✅ **Include all services** — even "internal" systems need SLOs
✅ **Track toil** — use error budget capacity to pay down technical debt

## Resources

- **Detailed patterns & playbook**: See `resources/implementation-playbook.md`
- **Google SRE Book**: https://sre.google/books/ (Chapter 4: Service Level Objectives)
- **Burn rate alerts**: https://cloud.google.com/blog/products/management-tools/slos-error-budgets-and-burn-rate-alerts
