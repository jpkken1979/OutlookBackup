---
name: tob-static-analysis
type: feature
description: "Integración de herramientas de análisis estático recomendadas por Trail of Bits. Semgrep, CodeQL, Bandit, mypy, eslint-security y más."
---

# Trail of Bits: Static Analysis Tooling

Guía de herramientas de análisis estático para detección de vulnerabilidades y calidad de código.

## Herramientas por Lenguaje

### Python

| Herramienta | Propósito | Comando |
|-------------|-----------|---------|
| **Semgrep** | Vulnerabilidades + patterns | `semgrep --config auto .` |
| **Bandit** | Seguridad Python específico | `bandit -r src/ -ll` |
| **mypy** | Type checking estricto | `mypy --strict src/` |
| **ruff** | Linting rápido (reemplaza flake8) | `ruff check .` |
| **pylint** | Análisis profundo | `pylint src/` |
| **safety** | Vulnerabilidades en deps | `safety check` |

### JavaScript/TypeScript

| Herramienta | Propósito | Comando |
|-------------|-----------|---------|
| **Semgrep** | Vulnerabilidades + patterns | `semgrep --config auto .` |
| **ESLint Security** | Reglas de seguridad | `eslint --ext .ts,.tsx .` |
| **npm audit** | Vulnerabilidades en deps | `npm audit` |
| **tsc --strict** | Type checking | `tsc --noEmit --strict` |

### Multi-lenguaje

| Herramienta | Propósito | Comando |
|-------------|-----------|---------|
| **CodeQL** | Análisis semántico profundo | GitHub Actions |
| **Semgrep** | Pattern matching universal | `semgrep --config auto .` |
| **Snyk** | Vulnerabilidades en deps | `snyk test` |
| **Trivy** | Containers + IaC + code | `trivy fs .` |

## Semgrep — Herramienta Principal

### Configuración

```yaml
# .semgrep.yml
rules:
  - id: no-hardcoded-secrets
    patterns:
      - pattern: |
          $KEY = "..."
      - metavariable-regex:
          metavariable: $KEY
          regex: (password|secret|token|api_key)
    message: "Possible hardcoded secret"
    languages: [python, javascript, typescript]
    severity: ERROR

  - id: no-shell-true
    pattern: subprocess.run(..., shell=True, ...)
    message: "Never use shell=True in subprocess"
    languages: [python]
    severity: ERROR
    fix: |
      subprocess.run(shlex.split($CMD), shell=False, ...)
```

### Rulesets Recomendados

```bash
# Seguridad general
semgrep --config p/security-audit .

# OWASP Top 10
semgrep --config p/owasp-top-ten .

# Secrets detection
semgrep --config p/secrets .

# Python security
semgrep --config p/python .

# JavaScript/TypeScript
semgrep --config p/javascript .
semgrep --config p/typescript .

# Docker
semgrep --config p/dockerfile .
```

## CodeQL

### GitHub Actions Setup

```yaml
# .github/workflows/codeql.yml
name: CodeQL Analysis
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  analyze:
    runs-on: ubuntu-latest
    permissions:
      security-events: write
    strategy:
      matrix:
        language: [python, javascript]
    steps:
      - uses: actions/checkout@v4
      - uses: github/codeql-action/init@v3
        with:
          languages: ${{ matrix.language }}
      - uses: github/codeql-action/analyze@v3
```

## Bandit (Python-específico)

```bash
# Escaneo básico
bandit -r .agent/core/ -ll

# Con severidad mínima
bandit -r .agent/ -ll -ii --severity-level medium

# Generar reporte JSON
bandit -r src/ -f json -o bandit-report.json

# Excluir tests
bandit -r src/ --exclude tests/
```

## Pipeline de CI Recomendado

```yaml
static-analysis:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4

    # Semgrep (rápido, multi-lenguaje)
    - name: Semgrep
      run: semgrep --config auto --error .

    # Bandit (Python security)
    - name: Bandit
      run: bandit -r .agent/core/ -ll -ii --severity-level medium

    # Type checking
    - name: mypy
      run: mypy --strict .agent/core/

    # Dependency audit
    - name: Safety
      run: safety check --json
```

## Métricas de Calidad

| Métrica | Objetivo |
|---------|----------|
| Semgrep findings (ERROR) | 0 |
| Bandit findings (HIGH) | 0 |
| mypy errors | 0 |
| npm audit (critical) | 0 |
| Coverage | ≥ 80% |

## Recursos

- [Semgrep](https://semgrep.dev/)
- [Trail of Bits Testing Handbook](https://appsec.guide/)
- [Bandit](https://bandit.readthedocs.io/)
- [CodeQL](https://codeql.github.com/)
