---
name: observability-monitoring-monitor-setup
description: Set up comprehensive observability with metrics (Prometheus), logs (ELK/Loki), traces (Jaeger), and Grafana dashboards. Full visibility into system health, MTTR reduction, and proactive alerting.
category: monitoring
version: 2.1.0
tags:
type: feature
---
  - prometheus
  - grafana
  - tracing
  - logging
  - alerting
  - observability
  - metrics
requires:
  tools:
    - docker
  python_modules:
    - prometheus_client
  optional:
    - jaeger
    - elasticsearch
    - datadog
triggers:
  - "monitoring|observability|alerting"
  - "metrics|logs|traces"
  - "prometheus|grafana|dashboard"
type: feature
---

# Monitoring and Observability Setup

Set up comprehensive observability infrastructure with metrics, logs, and traces. Build dashboards that surface actionable insights, establish alerting that reduces MTTR, and enable proactive issue detection.

## Three Pillars of Observability

```
┌─────────────────────────────────────────┐
│  Observability (understand unknown)      │
├─────────────────────────────────────────┤
│  Metrics                                 │
│  └─ Time-series data (Prometheus)       │
│     Performance, throughput, latency    │
│                                          │
│  Logs                                    │
│  └─ Structured events (ELK/Loki)       │
│     Debugging, audit trails, context    │
│                                          │
│  Traces                                  │
│  └─ Request journeys (Jaeger/Tempo)    │
│     Distributed request flows           │
└─────────────────────────────────────────┘
```

## Use this skill when

- Setting up comprehensive monitoring and observability stack
- Implementing metrics collection and dashboards
- Building distributed tracing infrastructure
- Configuring structured logging and log aggregation
- Creating alerts and runbooks
- Establishing on-call procedures
- Monitoring Kubernetes clusters and microservices

## Do not use this skill when

- Only basic health checks are needed (use simple HTTP endpoints)
- The task is unrelated to monitoring
- Observability tooling choices are already fixed

## Architecture: Complete Observability Stack

```
Applications (instrumented)
  ↓ (metrics: push/pull)
  ↓ (logs: stdout)
  ↓ (traces: OTLP)

┌─────────────────────────────────────┐
│  Collection Layer                     │
├─────────────────────────────────────┤
│  Prometheus scraper (pull)            │
│  Fluentd/Filebeat (log shipping)      │
│  OpenTelemetry collector (OTLP)      │
└─────────────────────────────────────┘
  ↓        ↓         ↓
Prometheus  ELK     Jaeger
(metrics)  (logs)  (traces)
  ↓        ↓         ↓
  └─────→ Grafana ←─┘
         (unified UI)
```

## Metrics Implementation (Prometheus)

### Instrumentation Example

```python
from prometheus_client import Counter, Histogram, Gauge, start_http_server
import time

# Define metrics
request_count = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

request_duration = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint'],
    buckets=[0.1, 0.5, 1, 2, 5, 10]
)

db_connection_pool = Gauge(
    'db_active_connections',
    'Active database connections',
    ['pool_name']
)

# Usage in Flask/FastAPI
@app.route('/api/users/<int:user_id>')
def get_user(user_id):
    start = time.time()
    try:
        user = fetch_user(user_id)
        request_count.labels(method='GET', endpoint='/api/users/{id}', status=200).inc()
        return user
    except Exception as e:
        request_count.labels(method='GET', endpoint='/api/users/{id}', status=500).inc()
        raise
    finally:
        duration = time.time() - start
        request_duration.labels(method='GET', endpoint='/api/users/{id}').observe(duration)

# Start metrics server
start_http_server(8000)  # Expose /metrics on :8000
```

### Prometheus Configuration

```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    cluster: 'production'
    region: 'us-west-2'

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['localhost:9093']

scrape_configs:
  - job_name: 'api-service'
    static_configs:
      - targets: ['localhost:8000']
    relabel_configs:
      - source_labels: [__address__]
        target_label: instance

  - job_name: 'postgres'
    static_configs:
      - targets: ['localhost:9187']  # postgres_exporter

  - job_name: 'redis'
    static_configs:
      - targets: ['localhost:9121']  # redis_exporter

  - job_name: 'kubernetes'
    kubernetes_sd_configs:
      - role: pod
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
        action: keep
        regex: true
```

### Alert Rules

```yaml
# alert_rules.yml
groups:
  - name: application_alerts
    interval: 30s
    rules:
      - alert: HighErrorRate
        expr: |
          sum(rate(http_requests_total{status=~"5.."}[5m]))
          / sum(rate(http_requests_total[5m])) > 0.05
        for: 5m
        annotations:
          summary: "High error rate on {{ $labels.job }}"
          runbook: "https://wiki.company.com/alerts/high-error-rate"

      - alert: SlowResponse
        expr: |
          histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m])) > 1
        for: 10m
        annotations:
          summary: "Slow response times detected"
```

## Logging Implementation (ELK / Loki)

### Structured Logging Pattern

```python
import json
import logging
from datetime import datetime

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add context from extra fields
        if hasattr(record, 'user_id'):
            log_data['user_id'] = record.user_id
        if hasattr(record, 'request_id'):
            log_data['request_id'] = record.request_id

        # Add exception details
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        return json.dumps(log_data)

# Setup
logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logger.addHandler(handler)

# Usage with context
logger.info("User login", extra={'user_id': 123, 'request_id': 'req-456'})
```

### Loki Configuration (log aggregation)

```yaml
# loki-config.yml
auth_enabled: false

ingester:
  chunk_idle_period: 3m
  chunk_retain_period: 1m
  max_chunk_age: 1h

limits_config:
  enforce_metric_name: false
  reject_old_samples: true
  reject_old_samples_max_age: 168h

schema_config:
  configs:
    - from: 2024-01-01
      store: boltdb-shipper
      object_store: filesystem
      schema: v11
      index:
        prefix: index_
        period: 24h

server:
  http_listen_port: 3100
```

## Distributed Tracing (Jaeger)

### Instrumentation with OpenTelemetry

```python
from opentelemetry import trace, metrics
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

# Setup Jaeger exporter
jaeger_exporter = JaegerExporter(
    agent_host_name="localhost",
    agent_port=6831,
)

trace.set_tracer_provider(TracerProvider())
trace.get_tracer_provider().add_span_processor(
    BatchSpanProcessor(jaeger_exporter)
)

# Auto-instrumentation
FlaskInstrumentor().instrument_app(app)
SQLAlchemyInstrumentor().instrument()

# Manual spans
tracer = trace.get_tracer(__name__)

@app.route('/checkout')
def checkout():
    with tracer.start_as_current_span("checkout") as span:
        span.set_attribute("user.id", user_id)

        with tracer.start_as_current_span("validate_cart") as validate_span:
            validate_cart()

        with tracer.start_as_current_span("process_payment") as payment_span:
            payment_span.set_attribute("amount", total)
            process_payment()

        return response
```

## Grafana Dashboards

### Key Dashboard Sections

```json
{
  "title": "Service Overview",
  "panels": [
    {
      "title": "Request Rate",
      "targets": [{
        "expr": "sum(rate(http_requests_total[5m])) by (method)"
      }]
    },
    {
      "title": "Error Rate",
      "targets": [{
        "expr": "sum(rate(http_requests_total{status=~\"5..\"}[5m])) by (service)"
      }]
    },
    {
      "title": "p99 Latency",
      "targets": [{
        "expr": "histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))"
      }]
    },
    {
      "title": "Database Connections",
      "targets": [{
        "expr": "db_active_connections"
      }]
    }
  ]
}
```

## Setup Checklist

- [ ] **Install Prometheus** — Metrics collection and storage
- [ ] **Install Grafana** — Unified dashboarding and visualization
- [ ] **Configure log shipping** — ELK Stack or Loki
- [ ] **Deploy Jaeger** — Distributed tracing
- [ ] **Instrument applications** — Add prometheus_client, OpenTelemetry SDKs
- [ ] **Create dashboards** — Key metrics for different personas
- [ ] **Define alerts** — Critical, warning, and info level rules
- [ ] **Document runbooks** — Response procedures for each alert
- [ ] **Setup on-call rotation** — Alert routing and escalation
- [ ] **Test end-to-end** — Verify data flow from app → collection → visualization

## Anti-Patterns

❌ Monitoring only availability (need latency + errors + utilization)
❌ High-cardinality labels (infinite metric explosion)
❌ Alerting on too many things (alert fatigue)
❌ No runbooks (ops doesn't know how to respond)
❌ Log everything (storage cost explosion)

## Best Practices

✅ Monitor outcomes (user experience), not just internal metrics
✅ Use structured logging for better searchability
✅ Sample traces in production (100% tracing = too much data)
✅ Keep cardinality under control (limit label values)
✅ Alert on SLOs, not raw metrics
✅ Automate runbook execution where possible

## Resources

- **Detailed patterns**: See `resources/implementation-playbook.md`
- **Prometheus docs**: https://prometheus.io/docs/
- **Grafana docs**: https://grafana.com/docs/
- **Jaeger tracing**: https://www.jaegertracing.io/
- **OpenTelemetry**: https://opentelemetry.io/
