---
name: tech-debt-tracker
description: Identifica y prioriza deuda técnica en superficies Python, TypeScript y Rust.
---

# Tech Debt Tracker Skill

Identifica y hace seguimiento de deuda técnica en el codebase. Analiza Python, TypeScript y Rust para encontrar issues de calidad.

## Superficies soportadas

| Superficie | Path | Lenguajes |
|---|---|---|
| Runtime Python | `.agent/` | Python |
| Desktop Nexus | `nexus-app/src/` | TypeScript, Rust |
| Bot Telegram | `src/` | TypeScript |

## Tipos de deuda detectados

| Tipo | Rule ID | Prioridad | Detecta |
|---|---|---|---|
| `types` | PY001, PY002 | CRITICAL | Funciones Python sin type hints, missing return types |
| `todos` | TD001, TD002 | HIGH | TODOs sin issue, FIXME, XXX, HACK sin contexto |
| `complexity` | CX001, CX002 | MEDIUM | Funciones >50 líneas, archivos >500 líneas |
| `naming` | NM001 | LOW | Nombres inconsistentes (snake vs camel) |
| `duplicates` | DP001 | MEDIUM | Bloques >5 líneas idénticos |
| `unused` | UN001, UN002 | HIGH | Imports sin usar, variables sin usar |

## Uso

```bash
# Scan completo (todas las superficies)
py .agent/skills-custom/tech-debt-tracker/scripts/main.py --scope full

# Scan por superficie
py .agent/skills-custom/tech-debt-tracker/scripts/main.py --scope .agent
py .agent/skills-custom/tech-debt-tracker/scripts/main.py --scope nexus-app/src
py .agent/skills-custom/tech-debt-tracker/scripts/main.py --scope src

# Solo un tipo de deuda
py .agent/skills-custom/tech-debt-tracker/scripts/main.py --debt types
py .agent/skills-custom/tech-debt-tracker/scripts/main.py --debt todos
py .agent/skills-custom/tech-debt-tracker/scripts/main.py --debt complexity
py .agent/skills-custom/tech-debt-tracker/scripts/main.py --debt naming
py .agent/skills-custom/tech-debt-tracker/scripts/main.py --debt duplicates
py .agent/skills-custom/tech-debt-tracker/scripts/main.py --debt unused

# Output
py .agent/skills-custom/tech-debt-tracker/scripts/main.py --scope .agent --format json
py .agent/skills-custom/tech-debt-tracker/scripts/main.py --scope .agent --format markdown
```

## Scoring

```
Score = 100 - (critical*10 + high*5 + medium*2)
> 80  = healthy
60-80 = attention needed
< 60  = critical state
```

## Integración con el ecosistema

- **Skill ID**: `tech-debt-tracker` en `.agent/skills-custom/tech-debt-tracker/`
- **Entry point**: `scripts/main.py` (CLI argparse)
- **Dependencies**: solo stdlib Python
- **Compatible con**: Nexus Desktop, Claude Code, CLI directo

## Arquitectura de detection

```
detectors.py
├── PythonTypeDetector     → PY001, PY002
├── TodoDetector          → TD001, TD002
├── ComplexityDetector    → CX001, CX002
├── NamingDetector        → NM001
├── DuplicateDetector     → DP001
└── UnusedDetector        → UN001, UN002

rules.py
├── PYTHON_PATTERNS       → regex para Python AST (type hints)
├── TYPESCRIPT_PATTERNS   → regex para TypeScript
├── RUST_PATTERNS         → regex para Rust
└── DEBT_RULES            → metadata de cada rule (severity, description)
```

## Ejemplo de output

```
TECH DEBT REPORT — .agent/
Generated: 2026-04-22

CRITICAL (arreglar ASAP)
  [PY001] .agent/core/orchestrator.py:234 — function process_request has no type hints
  [PY002] .agent/mcp/gateway.py:89 — missing return type annotation

HIGH (resolver en sprint)
  [TD001] .agent/core/brain.py:45 — TODO: implement cache invalidation (no issue)
  [TD002] .agent/mcp/skills-server.py:12 — FIXME: temporary hack for Windows

MEDIUM (trackear)
  [CX001] .agent/core/context_engines/builtin/delta_aware.py:234 — function is 234 lines (max 50)
  [CX002] .agent/skills-custom/autonomous-executor/scripts/main.py:512 — file is 512 lines

SUMMARY
  Total files scanned: 342
  Critical: 12
  High: 28
  Medium: 45
  Score: 67/100 (needs attention)
```
