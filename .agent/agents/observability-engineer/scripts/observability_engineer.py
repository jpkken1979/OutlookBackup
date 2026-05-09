#!/usr/bin/env python3
"""
Observability Engineer Agent

Implementa los tres pilares: logs, métricas, y traces.
"""

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class SLODefinition:
    """Definición de un SLO."""

    name: str
    target: float  # 99.9 = 99.9%
    window: str  # "30d", "7d"
    sli_query: str
    error_budget_policy: str = "alert"


# Templates de instrumentación
INSTRUMENTATION_TEMPLATES = {
    "python_otel": '''"""
OpenTelemetry instrumentation for Python application.
"""
from opentelemetry import trace, metrics
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s [%(name)s] [trace_id=%(otelTraceID)s span_id=%(otelSpanID)s] %(message)s'
)

def setup_telemetry(service_name: str, otlp_endpoint: str = "localhost:4317"):
    """Initialize OpenTelemetry with OTLP exporter."""

    # Resource with service info
    resource = Resource.create({{
        SERVICE_NAME: service_name,
        "service.version": "1.0.0",
        "deployment.environment": "production",
    }})

    # Tracing
    trace_provider = TracerProvider(resource=resource)
    trace_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True))
    )
    trace.set_tracer_provider(trace_provider)

    # Metrics
    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=otlp_endpoint, insecure=True),
        export_interval_millis=60000,
    )
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)

    # Auto-instrumentation
    FastAPIInstrumentor.instrument()
    RequestsInstrumentor().instrument()
    SQLAlchemyInstrumentor().instrument()

    return trace.get_tracer(service_name), metrics.get_meter(service_name)


# Usage example
tracer, meter = setup_telemetry("{app_name}")

# Custom metrics
request_counter = meter.create_counter(
    "http_requests_total",
    description="Total HTTP requests",
    unit="1"
)

request_duration = meter.create_histogram(
    "http_request_duration_seconds",
    description="HTTP request duration",
    unit="s"
)

# Custom span example
@tracer.start_as_current_span("process_order")
def process_order(order_id: str):
    span = trace.get_current_span()
    span.set_attribute("order.id", order_id)

    # Business logic here
    pass
''',
    "node_otel": """/**
 * OpenTelemetry instrumentation for Node.js application.
 */
import {{ NodeSDK }} from '@opentelemetry/sdk-node';
import {{ getNodeAutoInstrumentations }} from '@opentelemetry/auto-instrumentations-node';
import {{ OTLPTraceExporter }} from '@opentelemetry/exporter-trace-otlp-grpc';
import {{ OTLPMetricExporter }} from '@opentelemetry/exporter-metrics-otlp-grpc';
import {{ PeriodicExportingMetricReader }} from '@opentelemetry/sdk-metrics';
import {{ Resource }} from '@opentelemetry/resources';
import {{ SemanticResourceAttributes }} from '@opentelemetry/semantic-conventions';
import {{ trace, metrics, SpanStatusCode }} from '@opentelemetry/api';

const OTLP_ENDPOINT = process.env.OTLP_ENDPOINT || 'http://localhost:4317';

const resource = new Resource({{
  [SemanticResourceAttributes.SERVICE_NAME]: '{app_name}',
  [SemanticResourceAttributes.SERVICE_VERSION]: '1.0.0',
  [SemanticResourceAttributes.DEPLOYMENT_ENVIRONMENT]: process.env.NODE_ENV || 'development',
}});

const sdk = new NodeSDK({{
  resource,
  traceExporter: new OTLPTraceExporter({{
    url: OTLP_ENDPOINT,
  }}),
  metricReader: new PeriodicExportingMetricReader({{
    exporter: new OTLPMetricExporter({{
      url: OTLP_ENDPOINT,
    }}),
    exportIntervalMillis: 60000,
  }}),
  instrumentations: [getNodeAutoInstrumentations()],
}});

sdk.start();

// Graceful shutdown
process.on('SIGTERM', () => {{
  sdk.shutdown()
    .then(() => console.log('Telemetry shut down'))
    .catch((error) => console.error('Error shutting down telemetry', error))
    .finally(() => process.exit(0));
}});

// Custom metrics
const meter = metrics.getMeter('{app_name}');
const tracer = trace.getTracer('{app_name}');

export const requestCounter = meter.createCounter('http_requests_total', {{
  description: 'Total HTTP requests',
}});

export const requestDuration = meter.createHistogram('http_request_duration_seconds', {{
  description: 'HTTP request duration in seconds',
}});

// Custom span example
export async function processOrder(orderId: string) {{
  return tracer.startActiveSpan('process_order', async (span) => {{
    try {{
      span.setAttribute('order.id', orderId);

      // Business logic here

      span.setStatus({{ code: SpanStatusCode.OK }});
    }} catch (error) {{
      span.setStatus({{ code: SpanStatusCode.ERROR, message: error.message }});
      throw error;
    }} finally {{
      span.end();
    }}
  }});
}}

export {{ tracer, meter }};
""",
}

# Templates de dashboards Grafana
DASHBOARD_TEMPLATES = {
    "service": {
        "title": "{service_name} Service Dashboard",
        "panels": [
            {
                "title": "Request Rate",
                "type": "timeseries",
                "targets": [
                    {
                        "expr": 'rate(http_requests_total{{service="{service_name}"}}[5m])',
                        "legendFormat": "{{method}} {{path}}",
                    }
                ],
            },
            {
                "title": "Error Rate",
                "type": "timeseries",
                "targets": [
                    {
                        "expr": 'rate(http_requests_total{{service="{service_name}", status=~"5.."}}[5m]) / rate(http_requests_total{{service="{service_name}"}}[5m]) * 100',
                        "legendFormat": "Error %",
                    }
                ],
            },
            {
                "title": "Latency P99",
                "type": "timeseries",
                "targets": [
                    {
                        "expr": 'histogram_quantile(0.99, rate(http_request_duration_seconds_bucket{{service="{service_name}"}}[5m]))',
                        "legendFormat": "P99",
                    }
                ],
            },
            {
                "title": "Active Connections",
                "type": "stat",
                "targets": [
                    {
                        "expr": 'sum(active_connections{{service="{service_name}"}})',
                        "legendFormat": "Connections",
                    }
                ],
            },
        ],
    },
    "slo": {
        "title": "{service_name} SLO Dashboard",
        "panels": [
            {
                "title": "Availability SLO",
                "type": "gauge",
                "targets": [
                    {
                        "expr": '(1 - (sum(rate(http_requests_total{{service="{service_name}", status=~"5.."}}[30d])) / sum(rate(http_requests_total{{service="{service_name}"}}[30d])))) * 100',
                        "legendFormat": "Availability %",
                    }
                ],
                "thresholds": [99.9, 99.5, 99.0],
            },
            {
                "title": "Error Budget Remaining",
                "type": "stat",
                "targets": [
                    {
                        "expr": '(0.001 - (sum(rate(http_requests_total{{service="{service_name}", status=~"5.."}}[30d])) / sum(rate(http_requests_total{{service="{service_name}"}}[30d])))) / 0.001 * 100',
                        "legendFormat": "Budget %",
                    }
                ],
            },
            {
                "title": "Latency P99 SLO (< 200ms)",
                "type": "gauge",
                "targets": [
                    {
                        "expr": 'histogram_quantile(0.99, rate(http_request_duration_seconds_bucket{{service="{service_name}"}}[30d])) * 1000',
                        "legendFormat": "P99 ms",
                    }
                ],
                "thresholds": [100, 150, 200],
            },
        ],
    },
}

# Templates de alertas Prometheus
ALERT_TEMPLATES = {
    "high_error_rate": """groups:
  - name: {service_name}_alerts
    rules:
      - alert: HighErrorRate
        expr: |
          (
            sum(rate(http_requests_total{{service="{service_name}", status=~"5.."}}[5m]))
            /
            sum(rate(http_requests_total{{service="{service_name}"}}[5m]))
          ) > 0.01
        for: 5m
        labels:
          severity: critical
          service: {service_name}
        annotations:
          summary: "High error rate on {{{{ $labels.service }}}}"
          description: "Error rate is {{{{ $value | humanizePercentage }}}} (threshold: 1%)"
          runbook_url: "https://runbooks.example.com/high-error-rate"
""",
    "high_latency": """      - alert: HighLatency
        expr: |
          histogram_quantile(0.99,
            rate(http_request_duration_seconds_bucket{{service="{service_name}"}}[5m])
          ) > 0.5
        for: 5m
        labels:
          severity: warning
          service: {service_name}
        annotations:
          summary: "High P99 latency on {{{{ $labels.service }}}}"
          description: "P99 latency is {{{{ $value | humanizeDuration }}}}"
""",
    "error_budget_burn": """      - alert: ErrorBudgetBurn
        expr: |
          (
            sum(rate(http_requests_total{{service="{service_name}", status=~"5.."}}[1h]))
            /
            sum(rate(http_requests_total{{service="{service_name}"}}[1h]))
          ) > (1 - {slo_target}) * 14.4
        for: 5m
        labels:
          severity: critical
          service: {service_name}
        annotations:
          summary: "Error budget burning too fast on {{{{ $labels.service }}}}"
          description: "At current rate, will exhaust monthly error budget in < 2 days"
""",
    "pod_restart": """      - alert: PodRestartLoop
        expr: |
          increase(kube_pod_container_status_restarts_total{{
            namespace="{namespace}",
            pod=~"{service_name}.*"
          }}[1h]) > 3
        for: 5m
        labels:
          severity: warning
          service: {service_name}
        annotations:
          summary: "Pod restart loop detected"
          description: "Pod {{{{ $labels.pod }}}} has restarted {{{{ $value }}}} times in the last hour"
""",
}

# Template de runbook
RUNBOOK_TEMPLATE = """# Runbook: {alert_name}

## Overview
**Alert**: {alert_name}
**Severity**: {severity}
**Service**: {service_name}
**Last Updated**: {date}

## Description
{description}

## Impact
- User-facing: {user_facing}
- Revenue impact: {revenue_impact}

## Detection
This alert fires when:
```
{alert_condition}
```

## Investigation Steps

### 1. Verify the alert
```bash
# Check current metric value
curl -s "http://prometheus:9090/api/v1/query?query={verification_query}" | jq .

# Check recent logs
kubectl logs -l app={service_name} --tail=100 | grep -i error
```

### 2. Check service health
```bash
# Check pod status
kubectl get pods -l app={service_name}

# Check recent events
kubectl get events --field-selector involvedObject.name={service_name}

# Check resource usage
kubectl top pods -l app={service_name}
```

### 3. Check dependencies
```bash
# Database connectivity
kubectl exec -it deploy/{service_name} -- nc -zv postgres 5432

# Redis connectivity
kubectl exec -it deploy/{service_name} -- nc -zv redis 6379
```

## Remediation Steps

### Quick fixes
1. **Scale up**: `kubectl scale deploy/{service_name} --replicas=5`
2. **Restart pods**: `kubectl rollout restart deploy/{service_name}`
3. **Check config**: `kubectl get configmap {service_name}-config -o yaml`

### If quick fixes don't work
1. Check recent deployments: `kubectl rollout history deploy/{service_name}`
2. Rollback if needed: `kubectl rollout undo deploy/{service_name}`
3. Escalate to on-call engineer

## Escalation
- **L1**: On-call engineer via PagerDuty
- **L2**: {service_name} team lead
- **L3**: Platform team

## References
- [Service Documentation](https://docs.example.com/{service_name})
- [Architecture Diagram](https://diagrams.example.com/{service_name})
- [Previous Incidents](https://incidents.example.com?service={service_name})
"""


def generate_instrumentation(app_name: str, language: str) -> str:
    """Genera código de instrumentación."""
    template_key = f"{language}_otel"
    template = INSTRUMENTATION_TEMPLATES.get(template_key, "# Language not supported")
    return template.format(app_name=app_name)


def generate_dashboard(service_name: str, dashboard_type: str) -> dict:
    """Genera dashboard de Grafana."""
    template = DASHBOARD_TEMPLATES.get(dashboard_type, DASHBOARD_TEMPLATES["service"])

    dashboard = {
        "title": template["title"].format(service_name=service_name),
        "uid": f"{service_name}-{dashboard_type}",
        "timezone": "browser",
        "refresh": "30s",
        "time": {"from": "now-6h", "to": "now"},
        "panels": [],
    }

    for i, panel in enumerate(template["panels"]):
        panel_config = {
            "id": i + 1,
            "title": panel["title"],
            "type": panel["type"],
            "gridPos": {"x": (i % 2) * 12, "y": (i // 2) * 8, "w": 12, "h": 8},
            "targets": [
                {
                    "expr": t["expr"].format(service_name=service_name),
                    "legendFormat": t["legendFormat"],
                }
                for t in panel["targets"]
            ],
        }
        dashboard["panels"].append(panel_config)

    return dashboard


def generate_alerts(
    service_name: str, slo_target: float = 0.999, namespace: str = "default"
) -> str:
    """Genera reglas de alertas Prometheus."""
    alerts = []

    for _name, template in ALERT_TEMPLATES.items():
        alert = template.format(
            service_name=service_name, slo_target=slo_target, namespace=namespace
        )
        alerts.append(alert)

    return "\n".join(alerts)


def generate_runbook(
    alert_name: str,
    service_name: str,
    severity: str = "critical",
    description: str = "",
    alert_condition: str = "",
) -> str:
    """Genera un runbook para una alerta."""
    return RUNBOOK_TEMPLATE.format(
        alert_name=alert_name,
        service_name=service_name,
        severity=severity,
        description=description or f"Alert triggered for {service_name}",
        date=datetime.now().strftime("%Y-%m-%d"),
        user_facing="Yes" if severity == "critical" else "Potentially",
        revenue_impact="High" if severity == "critical" else "Medium",
        alert_condition=alert_condition or "See Prometheus alert definition",
        verification_query=f'http_requests_total{{service="{service_name}"}}',
    )


def analyze_logs(log_content: str) -> dict:
    """Analiza logs y extrae patrones."""
    import re

    lines = log_content.strip().split("\n")
    total_lines = len(lines)

    # Contar por nivel
    levels = {"ERROR": 0, "WARN": 0, "INFO": 0, "DEBUG": 0}
    for line in lines:
        for level in levels:
            if level in line.upper():
                levels[level] += 1
                break

    # Extraer errores únicos
    error_patterns = {}
    error_regex = r"(?:error|exception|failed)[\s:]+(.{0,100})"
    for line in lines:
        match = re.search(error_regex, line, re.IGNORECASE)
        if match:
            error = match.group(1)[:50]
            error_patterns[error] = error_patterns.get(error, 0) + 1

    # Top errores
    top_errors = sorted(error_patterns.items(), key=lambda x: -x[1])[:10]

    return {
        "total_lines": total_lines,
        "by_level": levels,
        "error_rate": levels["ERROR"] / total_lines * 100 if total_lines > 0 else 0,
        "top_errors": top_errors,
        "recommendations": get_log_recommendations(levels, total_lines),
    }


def get_log_recommendations(levels: dict, total: int) -> list:
    """Genera recomendaciones basadas en análisis de logs."""
    recs = []

    error_rate = levels["ERROR"] / total * 100 if total > 0 else 0
    if error_rate > 5:
        recs.append(f"Error rate alto ({error_rate:.1f}%) - investigar causa raíz")

    if levels["DEBUG"] > total * 0.5:
        recs.append("Muchos logs DEBUG - considerar reducir en producción")

    if levels["INFO"] < total * 0.1:
        recs.append("Pocos logs INFO - agregar más contexto de operaciones")

    return recs


def main():
    parser = argparse.ArgumentParser(
        description="Observability Engineer - Implementa logs, métricas, y traces"
    )

    subparsers = parser.add_subparsers(dest="command", help="Comando")

    # instrument
    inst_parser = subparsers.add_parser("instrument", help="Genera instrumentación")
    inst_parser.add_argument("--app", "-a", required=True, help="Nombre de la app")
    inst_parser.add_argument("--language", "-l", choices=["python", "node"], default="python")

    # dashboard
    dash_parser = subparsers.add_parser("dashboard", help="Genera dashboard Grafana")
    dash_parser.add_argument("--name", "-n", required=True, help="Nombre del servicio")
    dash_parser.add_argument("--type", "-t", choices=["service", "slo"], default="service")

    # alerts
    alert_parser = subparsers.add_parser("alerts", help="Genera alertas Prometheus")
    alert_parser.add_argument("--service", "-s", required=True, help="Nombre del servicio")
    alert_parser.add_argument("--slo", type=float, default=99.9, help="SLO target (ej: 99.9)")
    alert_parser.add_argument("--namespace", "-n", default="default", help="Kubernetes namespace")

    # runbook
    rb_parser = subparsers.add_parser("runbook", help="Genera runbook")
    rb_parser.add_argument("--alert", "-a", required=True, help="Nombre de la alerta")
    rb_parser.add_argument("--service", "-s", required=True, help="Nombre del servicio")
    rb_parser.add_argument(
        "--severity", choices=["critical", "warning", "info"], default="critical"
    )

    # analyze-logs
    log_parser = subparsers.add_parser("analyze-logs", help="Analiza logs")
    log_parser.add_argument("--file", "-f", required=True, help="Archivo de logs")

    # Común
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--output", "-o", help="Archivo de salida")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    output = None

    if args.command == "instrument":
        output = generate_instrumentation(args.app, args.language)

    elif args.command == "dashboard":
        dashboard = generate_dashboard(args.name, args.type)
        output = json.dumps(dashboard, indent=2)

    elif args.command == "alerts":
        output = generate_alerts(args.service, args.slo / 100, args.namespace)

    elif args.command == "runbook":
        output = generate_runbook(args.alert, args.service, args.severity)

    elif args.command == "analyze-logs":
        log_path = Path(args.file)
        if not log_path.exists():
            print(f"Error: {args.file} no existe")
            return 1

        content = log_path.read_text()
        analysis = analyze_logs(content)

        if args.json:
            output = json.dumps(analysis, indent=2)
        else:
            print(f"\n{'=' * 60}")
            print(" ANÁLISIS DE LOGS")
            print(f"{'=' * 60}")
            print("\n📊 Estadísticas:")
            print(f"   Total líneas: {analysis['total_lines']:,}")
            print(f"   Error rate: {analysis['error_rate']:.2f}%")
            print("\n   Por nivel:")
            for level, count in analysis["by_level"].items():
                pct = count / analysis["total_lines"] * 100 if analysis["total_lines"] > 0 else 0
                print(f"     {level}: {count:,} ({pct:.1f}%)")

            if analysis["top_errors"]:
                print("\n🔴 Top errores:")
                for error, count in analysis["top_errors"][:5]:
                    print(f"   [{count}x] {error}")

            if analysis["recommendations"]:
                print("\n💡 Recomendaciones:")
                for rec in analysis["recommendations"]:
                    print(f"   • {rec}")

    # Output
    if output:
        if hasattr(args, "output") and args.output:
            Path(args.output).write_text(output)
            print(f"✓ Escrito en {args.output}")
        else:
            print(output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
