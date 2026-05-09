#!/usr/bin/env python3
"""
Load Testing Engineer - Ingeniero de pruebas de carga.

Genera scripts de prueba de carga para k6, Locust, y otras herramientas.
Analiza resultados y proporciona recomendaciones.

Uso:
    python load_testing_engineer.py generate <url> --tool k6
    python load_testing_engineer.py generate <url> --tool locust --vus 100
    python load_testing_engineer.py analyze <results.json>
"""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from urllib.parse import urlparse

# Configuracion de logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("antigravity.agents.load-testing-engineer")


class TestType(Enum):
    """Tipos de prueba de carga."""

    SMOKE = "smoke"
    LOAD = "load"
    STRESS = "stress"
    SPIKE = "spike"
    SOAK = "soak"
    BREAKPOINT = "breakpoint"


class Tool(Enum):
    """Herramientas de load testing."""

    K6 = "k6"
    LOCUST = "locust"
    ARTILLERY = "artillery"
    JMETER = "jmeter"


@dataclass
class TestConfig:
    """Configuracion de prueba."""

    target_url: str
    test_type: TestType = TestType.LOAD
    vus: int = 10
    duration_minutes: int = 5
    ramp_up_minutes: int = 1
    thresholds: dict = field(
        default_factory=lambda: {
            "p95_latency_ms": 500,
            "p99_latency_ms": 1000,
            "error_rate_percent": 1,
            "min_rps": 100,
        }
    )


@dataclass
class Endpoint:
    """Un endpoint a testear."""

    method: str
    path: str
    weight: int = 1
    headers: dict = field(default_factory=dict)
    body: dict | None = None


@dataclass
class LoadTestScript:
    """Script de prueba generado."""

    tool: Tool
    test_type: TestType
    target_url: str
    script: str
    filename: str
    instructions: str

    def to_dict(self) -> dict:
        return {
            "tool": self.tool.value,
            "test_type": self.test_type.value,
            "target_url": self.target_url,
            "script": self.script,
            "filename": self.filename,
            "instructions": self.instructions,
        }


class LoadTestingEngineer:
    """Generador de scripts de prueba de carga."""

    def __init__(self):
        self.templates = self._load_templates()

    def _load_templates(self) -> dict:
        """Cargar templates de scripts."""
        return {
            "k6_smoke": """import http from 'k6/http';
import {{ check, sleep }} from 'k6';

export const options = {{
  vus: 1,
  duration: '1m',
  thresholds: {{
    http_req_duration: ['p(95)<{p95_latency}'],
    http_req_failed: ['rate<0.01'],
  }},
}};

export default function () {{
  const res = http.get('{url}');
  check(res, {{
    'status is 200': (r) => r.status === 200,
    'response time < {p95_latency}ms': (r) => r.timings.duration < {p95_latency},
  }});
  sleep(1);
}}
""",
            "k6_load": """import http from 'k6/http';
import {{ check, sleep }} from 'k6';
import {{ Rate, Trend }} from 'k6/metrics';

const errorRate = new Rate('errors');
const latency = new Trend('latency');

export const options = {{
  stages: [
    {{ duration: '{ramp_up}m', target: {vus} }},
    {{ duration: '{duration}m', target: {vus} }},
    {{ duration: '{ramp_up}m', target: 0 }},
  ],
  thresholds: {{
    http_req_duration: ['p(95)<{p95_latency}', 'p(99)<{p99_latency}'],
    http_req_failed: ['rate<{error_rate}'],
    errors: ['rate<{error_rate}'],
  }},
}};

export default function () {{
  const res = http.get('{url}');

  check(res, {{
    'status is 200': (r) => r.status === 200,
    'response time OK': (r) => r.timings.duration < {p95_latency},
  }}) || errorRate.add(1);

  latency.add(res.timings.duration);
  sleep(Math.random() * 2 + 1);
}}
""",
            "k6_stress": """import http from 'k6/http';
import {{ check, sleep }} from 'k6';

export const options = {{
  stages: [
    {{ duration: '2m', target: {vus} }},
    {{ duration: '5m', target: {vus} }},
    {{ duration: '2m', target: {vus_2x} }},
    {{ duration: '5m', target: {vus_2x} }},
    {{ duration: '2m', target: {vus_3x} }},
    {{ duration: '5m', target: {vus_3x} }},
    {{ duration: '10m', target: 0 }},
  ],
  thresholds: {{
    http_req_duration: ['p(99)<{p99_latency}'],
    http_req_failed: ['rate<{error_rate}'],
  }},
}};

export default function () {{
  const res = http.get('{url}');
  check(res, {{
    'status is 2xx or 3xx': (r) => r.status >= 200 && r.status < 400,
  }});
  sleep(1);
}}
""",
            "k6_spike": """import http from 'k6/http';
import {{ check, sleep }} from 'k6';

export const options = {{
  stages: [
    {{ duration: '10s', target: {vus} }},
    {{ duration: '1m', target: {vus} }},
    {{ duration: '10s', target: {vus_10x} }},
    {{ duration: '3m', target: {vus_10x} }},
    {{ duration: '10s', target: {vus} }},
    {{ duration: '3m', target: {vus} }},
    {{ duration: '10s', target: 0 }},
  ],
}};

export default function () {{
  const res = http.get('{url}');
  check(res, {{
    'status is 200': (r) => r.status === 200,
  }});
  sleep(1);
}}
""",
            "locust_load": '''from locust import HttpUser, task, between, events
import time

class ApiUser(HttpUser):
    wait_time = between(1, 3)

    @task(10)
    def get_main(self):
        with self.client.get("{path}", catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"Got status {{response.status_code}}")

    def on_start(self):
        """Ejecutar al inicio de cada usuario."""
        pass


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Generar reporte al finalizar."""
    stats = environment.stats
    print("\\n=== Resultados Finales ===")
    print(f"Total requests: {{stats.total.num_requests}}")
    print(f"Failures: {{stats.total.num_failures}}")
    print(f"Avg response time: {{stats.total.avg_response_time:.2f}}ms")
    print(f"p95: {{stats.total.get_response_time_percentile(0.95):.2f}}ms")
    print(f"p99: {{stats.total.get_response_time_percentile(0.99):.2f}}ms")
''',
        }

    def generate_script(
        self, config: TestConfig, tool: Tool = Tool.K6, endpoints: list[Endpoint] = None
    ) -> LoadTestScript:
        """Generar script de prueba."""
        logger.info(f"Generando script {tool.value} para {config.test_type.value} test")

        parsed_url = urlparse(config.target_url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        path = parsed_url.path or "/"

        if tool == Tool.K6:
            return self._generate_k6_script(config, base_url, path)
        elif tool == Tool.LOCUST:
            return self._generate_locust_script(config, base_url, path)
        else:
            raise ValueError(f"Herramienta no soportada: {tool}")

    def _generate_k6_script(self, config: TestConfig, base_url: str, path: str) -> LoadTestScript:
        """Generar script k6."""
        template_key = f"k6_{config.test_type.value}"
        template = self.templates.get(template_key, self.templates["k6_load"])

        script = template.format(
            url=f"{base_url}{path}",
            vus=config.vus,
            vus_2x=config.vus * 2,
            vus_3x=config.vus * 3,
            vus_10x=config.vus * 10,
            duration=config.duration_minutes,
            ramp_up=config.ramp_up_minutes,
            p95_latency=config.thresholds["p95_latency_ms"],
            p99_latency=config.thresholds["p99_latency_ms"],
            error_rate=config.thresholds["error_rate_percent"] / 100,
        )

        instructions = f"""# Instrucciones para ejecutar

## Requisitos
- Instalar k6: https://k6.io/docs/getting-started/installation/

## Ejecutar
```bash
# Ejecutar test
k6 run {config.test_type.value}_test.js

# Con output a JSON
k6 run --out json=results.json {config.test_type.value}_test.js

# Con mas VUs
k6 run --vus {config.vus * 2} {config.test_type.value}_test.js
```

## Interpretar resultados
- http_req_duration: Tiempo de respuesta
- http_req_failed: Tasa de errores
- iterations: Requests completados

## Thresholds configurados
- p95 latencia: <{config.thresholds["p95_latency_ms"]}ms
- p99 latencia: <{config.thresholds["p99_latency_ms"]}ms
- Error rate: <{config.thresholds["error_rate_percent"]}%
"""

        return LoadTestScript(
            tool=Tool.K6,
            test_type=config.test_type,
            target_url=config.target_url,
            script=script,
            filename=f"{config.test_type.value}_test.js",
            instructions=instructions,
        )

    def _generate_locust_script(
        self, config: TestConfig, base_url: str, path: str
    ) -> LoadTestScript:
        """Generar script Locust."""
        template = self.templates["locust_load"]

        script = template.format(path=path)

        instructions = f"""# Instrucciones para ejecutar

## Requisitos
```bash
pip install locust
```

## Ejecutar
```bash
# Modo web UI
locust -f locustfile.py --host={base_url}

# Modo headless
locust -f locustfile.py --host={base_url} \\
    --users {config.vus} \\
    --spawn-rate 10 \\
    --run-time {config.duration_minutes}m \\
    --headless

# Con reporte HTML
locust -f locustfile.py --host={base_url} \\
    --users {config.vus} \\
    --headless \\
    --html=report.html
```

## Interpretar resultados
- Abrir http://localhost:8089 para web UI
- Ver metricas en tiempo real
- Descargar CSV con resultados
"""

        return LoadTestScript(
            tool=Tool.LOCUST,
            test_type=config.test_type,
            target_url=config.target_url,
            script=script,
            filename="locustfile.py",
            instructions=instructions,
        )

    def analyze_results(self, results_file: Path) -> dict:
        """Analizar resultados de prueba."""
        logger.info(f"Analizando resultados de {results_file}")

        try:
            data = json.loads(results_file.read_text())
        except Exception as e:
            return {"error": f"No se pudo leer archivo: {e}"}

        analysis = {"summary": {}, "bottlenecks": [], "recommendations": []}

        # Analisis basico (adaptable segun formato)
        if "metrics" in data:
            metrics = data["metrics"]

            # Extraer metricas clave
            if "http_req_duration" in metrics:
                duration = metrics["http_req_duration"]
                analysis["summary"]["avg_latency_ms"] = duration.get("avg", 0)
                analysis["summary"]["p95_latency_ms"] = duration.get("p(95)", 0)
                analysis["summary"]["p99_latency_ms"] = duration.get("p(99)", 0)

            if "http_reqs" in metrics:
                reqs = metrics["http_reqs"]
                analysis["summary"]["total_requests"] = reqs.get("count", 0)
                analysis["summary"]["rps"] = reqs.get("rate", 0)

            if "http_req_failed" in metrics:
                failed = metrics["http_req_failed"]
                analysis["summary"]["error_rate"] = failed.get("rate", 0)

        # Detectar cuellos de botella
        if analysis["summary"].get("p99_latency_ms", 0) > 1000:
            analysis["bottlenecks"].append(
                {
                    "type": "high_latency",
                    "description": "p99 latencia > 1s indica posible cuello de botella",
                    "severity": "high",
                }
            )

        if analysis["summary"].get("error_rate", 0) > 0.01:
            analysis["bottlenecks"].append(
                {
                    "type": "high_errors",
                    "description": "Error rate > 1% indica problemas de estabilidad",
                    "severity": "critical",
                }
            )

        # Generar recomendaciones
        if analysis["bottlenecks"]:
            analysis["recommendations"].extend(
                [
                    "Revisar logs del servidor durante el test",
                    "Verificar uso de CPU y memoria",
                    "Analizar queries lentas en la base de datos",
                    "Considerar agregar cache",
                    "Verificar connection pool settings",
                ]
            )

        return analysis


def main():
    """Entry point principal."""
    parser = argparse.ArgumentParser(
        description="Load Testing Engineer - Generador de pruebas de carga"
    )
    subparsers = parser.add_subparsers(dest="command", help="Comandos disponibles")

    # Comando: generate
    gen_parser = subparsers.add_parser("generate", help="Generar script de prueba")
    gen_parser.add_argument("url", help="URL objetivo")
    gen_parser.add_argument("--tool", "-t", choices=["k6", "locust"], default="k6")
    gen_parser.add_argument(
        "--type", "-T", choices=["smoke", "load", "stress", "spike"], default="load"
    )
    gen_parser.add_argument("--vus", type=int, default=10, help="Usuarios virtuales")
    gen_parser.add_argument("--duration", type=int, default=5, help="Duracion en minutos")
    gen_parser.add_argument("--output", "-o", help="Archivo de salida")
    gen_parser.add_argument("--json", action="store_true", help="Output en JSON")

    # Comando: analyze
    analyze_parser = subparsers.add_parser("analyze", help="Analizar resultados")
    analyze_parser.add_argument("results", help="Archivo de resultados JSON")
    analyze_parser.add_argument("--json", action="store_true", help="Output en JSON")

    args = parser.parse_args()

    engineer = LoadTestingEngineer()

    if args.command == "generate":
        config = TestConfig(
            test_type=TestType[args.type.upper()],
            target_url=args.url,
            vus=args.vus,
            duration_minutes=args.duration,
        )

        result = engineer.generate_script(config, Tool[args.tool.upper()])

        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(f"# {result.filename}")
            print(result.script)
            print("\n" + "=" * 50)
            print(result.instructions)

        if args.output:
            Path(args.output).write_text(result.script)
            logger.info(f"Script guardado en {args.output}")

    elif args.command == "analyze":
        analysis = engineer.analyze_results(Path(args.results))

        if args.json:
            print(json.dumps(analysis, indent=2))
        else:
            print("# Analisis de Resultados\n")
            print("## Resumen")
            for key, value in analysis.get("summary", {}).items():
                print(f"- {key}: {value}")

            print("\n## Cuellos de Botella")
            for b in analysis.get("bottlenecks", []):
                print(f"- [{b['severity'].upper()}] {b['description']}")

            print("\n## Recomendaciones")
            for r in analysis.get("recommendations", []):
                print(f"- {r}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
