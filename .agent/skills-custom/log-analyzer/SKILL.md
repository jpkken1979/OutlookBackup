---
name: log-analyzer
description: "Analiza archivos de log para encontrar patrones de errores, anomalías y generar reportes actionables. Diseñado para el ecosistema Antigravity: gateway logs, Nexus logs, agent logs, test output. Triggers: log analyzer, error detection, log patterns, crash analysis, log report, gateway logs, nexus logs, agent logs, test output."
---

# Log Analyzer Skill

Analiza archivos de log para encontrar patrones de errores, anomalías y generar reportes actionables.

**Agent Tier:** 2 (Quality, Security y superiores)
**Auth Required:** No (acceso a filesystem local)
**Timeout:** 30 segundos por archivo
**Cost:** Free (solo stdlib — cero dependencias externas)
**Stdlib:** `re`, `dataclasses`, `collections`, `datetime`, `pathlib`, `json`, `argparse`, `logging`

## Descripcion

Log Analyzer escanea archivos o directorios de log y detecta patrones de error usando regex predefinidos organizados por severidad. Agrupa errores similares para deduplicar, detecta bursts temporales (muchos errores en poco tiempo), calcula un health score y genera recomendaciones actionables.

Casos de uso:
- Diagnosticar crashes o errores en el gateway `:4747`
- Analizar salida de tests (`pytest` output como `.log`)
- Auditar logs de Nexus para encontrar bottlenecks o auth failures
- Revisar output de agentes en `.agent/logs/`

## Compatibilidad

Designed para:
- Gateway logs (`start_gateway.py` output)
- Nexus logs (`nexus-app/src-tauri/`)
- Agent logs (`.agent/logs/`, `.agent/agents/*/logs/`)
- Test output (archivos `.log` de pytest / Vitest)
- Cualquier archivo de texto con formato de log

## Input Schema

```json
{
  "path": "string (required) — archivo .log o directorio a escanear",
  "min_severity": "string (optional) — ALL | LOW | MEDIUM | HIGH | CRITICAL (default: ALL)",
  "format": "string (optional) — text | markdown | json (default: text)",
  "output_file": "string (optional) — guardar reporte en archivo en vez de stdout",
  "burst_window_seconds": "int (optional, default 300) — ventana para deteccion de bursts",
  "burst_threshold": "int (optional, default 5) — min errores en ventana para burst",
  "verbose": "boolean (optional) — salida debug"
}
```

## Output Schema

```json
{
  "scan_date": "ISO 8601",
  "total_lines": "int",
  "files_scanned": "int",
  "total_errors": "int",
  "health_score": "int 0-100",
  "groups": [
    {
      "code": "E001",
      "severity": "CRITICAL",
      "description": "Python exception or stack trace",
      "group_key": "python_exception",
      "count": 7,
      "first_seen": "2026-04-22 14:23:11",
      "last_seen": "2026-04-22 14:45:02",
      "sample_line": "...",
      "files": ["gateway.log", "agent.log"]
    }
  ],
  "bursts": [
    {
      "start": "2026-04-22T14:30:00",
      "end": "2026-04-22T14:35:00",
      "window_seconds": 300,
      "error_count": 15,
      "severity": "CRITICAL"
    }
  ]
}
```

## CLI

```bash
# Analisis rapido
py .agent/skills-custom/log-analyzer/scripts/main.py --path gateway.log

# Solo errores criticos en JSON
py .agent/skills-custom/log-analyzer/scripts/main.py --path .agent/logs/ --level critical --format json

# Salvar reporte en markdown
py .agent/skills-custom/log-analyzer/scripts/main.py --path /tmp/nexus.log --format markdown --output report.md

# Ver patrones disponibles
py .agent/skills-custom/log-analyzer/scripts/main.py --list-patterns

# Verbose para debugging
py .agent/skills-custom/log-analyzer/scripts/main.py --path gateway.log --verbose
```

## Patrones de deteccion

### CRITICAL

| Code | Descripcion | Group Key |
|------|-------------|-----------|
| E001 | Python exception / stack trace | `python_exception` |
| E002 | Generic ERROR level log | `error_generic` |
| E003 | Connection refused | `connection_refused` |
| E004 | Authentication failure | `auth_failure` |
| E005 | HTTP 500 Internal Server Error | `http_500` |
| E006 | Out of memory | `oom_error` |
| E007 | Permission denied | `permission_denied` |

### HIGH

| Code | Descripcion | Group Key |
|------|-------------|-----------|
| W001 | Warning-level log | `warning_generic` |
| W002 | Timeout error | `timeout_error` |
| W003 | Connection reset | `connection_reset` |
| W004 | Deprecated API usage | `deprecated_api` |
| W005 | HTTP 502/503/504 | `http_5xx_gateway` |
| W006 | Panic / fatal error | `panic_fatal` |

### MEDIUM

| Code | Descripcion | Group Key |
|------|-------------|-----------|
| M001 | Rate limiting | `rate_limit` |
| M002 | Retry attempt | `retry_attempt` |
| M003 | SSL / certificate error | `ssl_error` |
| M004 | Database lock | `db_locked` |

### LOW

| Code | Descripcion | Group Key |
|------|-------------|-----------|
| L001 | Slow query / slow request | `slow_operation` |
| L002 | Deprecated feature notice | `deprecated_notice` |
| L003 | Disk full warning | `disk_full` |

## Features

1. **Multi-file analysis** — pasa un directorio y escanea recursivamente todos los `.log`
2. **Pattern matching** — regex precompilados para 20+ tipos de errores
3. **Severity grouping** — errores agrupados por severidad (CRITICAL > HIGH > MEDIUM > LOW)
4. **Deduplication** — errores similares agrupados via `group_key`; muestra count, first/last seen
5. **Timestamp analysis** — extrae timestamps de lineas y detecta bursts temporales
6. **Health score** — 0-100 basado en densidad y severidad de errores
7. **Report generation** — texto plano, markdown, o JSON
8. **Recommendations** — consejos actionables generados automaticamente

## Health Score

| Score | Label | Significado |
|-------|-------|-------------|
| 80-100 | HEALTHY | Sin errores criticos o alta densidad de errores |
| 50-79 | NEEDS ATTENTION | Algunos errores que requieren investigacion |
| 0-49 | CRITICAL | Alta densidad de errores criticos |

## Uso programatico

```python
import sys
sys.path.insert(0, ".agent")
from skills_custom.log_analyzer.scripts import run_analysis
from pathlib import Path

result = run_analysis(Path("gateway.log"), min_severity="HIGH")
print(f"Health: {result.health_score}/100")
for g in result.groups:
    print(f"  [{g.severity}] {g.count}x {g.description}")
```

## Errores manejados

- Archivo inexistente → exit code 1
- Directorio sin archivos `.log` → report vacio con 0 lineas
- Archivos binarios → se leen como texto con `errors='replace'`
- Timestamps no parseables → se omiten en burst detection (no rompen el scan)
- Archivos vacios → skip silencioso

## Seguridad

- Sin `shell=True`, sin `eval`, sin `pickle`
- Acceso solo a archivos especificados por el usuario
- SQL no usado (zero database dependencies)
- Files > 50MB: se procesan linea a linea sin cargar full en RAM

## Tests

```bash
python -m pytest .agent/skills-custom/log-analyzer/tests/ -v
```

## Version

1.0.0

## Author

OpenAntigravity — K. Kaneshiro / UNS
**Created:** 2026-04-22

## License

Misma licencia que OpenAntigravity.
