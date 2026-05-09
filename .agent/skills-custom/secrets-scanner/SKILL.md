---
name: secrets-scanner
description: Escanea repositorios para detectar credenciales, tokens y secretos antes de commit o CI.
---

# secrets-scanner

**Skill**: `secrets-scanner`
**Type**: Security / Pre-commit / CI/CD
**Entry Point**: `scripts/main.py`
**Dependencies**: Stdlib only (no external packages)

---

## Proposito

Escanea archivos del codebase para detectar secrets hardcodeados, API keys, tokens,
passwords y otros credenciales antes de que se commiteen. Es una herramienta de
prevencion que se integra con el workflow de pre-commit y pipelines de CI/CD.

---

## Uso

```bash
# Scan entire repo
py .agent/skills-custom/secrets-scanner/scripts/main.py --scope .

# Scan specific directory
py .agent/skills-custom/secrets-scanner/scripts/main.py --scope .agent

# JSON output for CI/CD
py .agent/skills-custom/secrets-scanner/scripts/main.py --scope . --format json

# Scan with fixes displayed
py .agent/skills-custom/secrets-scanner/scripts/main.py --scope . --fix

# Exclude patterns
py .agent/skills-custom/secrets-scanner/scripts/main.py --scope . \
    --exclude node_modules \
    --exclude vendor \
    --exclude .git

# Git diff mode (unstaged changes only)
py .agent/skills-custom/secrets-scanner/scripts/main.py --git-diff

# Pre-commit hook mode (fail on critical)
py .agent/skills-custom/secrets-scanner/scripts/main.py --git-diff --fail-on-secrets

# Interactive suppression of false positives
py .agent/skills-custom/secrets-scanner/scripts/main.py --scope . --interactive

# List all detected secret types
py .agent/skills-custom/secrets-scanner/scripts/main.py --list-types

# Help
py .agent/skills-custom/secrets-scanner/scripts/main.py --help
```

---

## Secrets Detectados

| Tipo | Patrones | Severidad |
|------|----------|-----------|
| AWS Access Key | `AKIA...` | CRITICAL |
| AWS Secret Key | `aws_secret_access_key`, `aws_secret_key` | CRITICAL |
| GitHub Personal Access Token | `ghp_...`, `github_pat_...` | CRITICAL |
| OpenAI API Key | `sk-...`, `sk-proj-...` | CRITICAL |
| Anthropic API Key | `sk-ant-...` | CRITICAL |
| Slack Token | `xox[baprs]-...` | CRITICAL |
| Telegram Bot Token | `\d{8,10}:[\w-]{35}` | CRITICAL |
| RSA/EC/DSA Private Key | `-----BEGIN (RSA\|EC\|DSA\|OPENSSH) PRIVATE KEY-----` | CRITICAL |
| JWT Bearer Token | `Bearer eyJ...` | HIGH |
| Generic API Key | `api_key=`, `apikey=`, `api-token=` | HIGH |
| Database URL with credentials | `postgresql://...`, `mysql://...` with user:pass | HIGH |
| Password in URL | `password:` in URLs | HIGH |
| Environment secrets | `SECRET=`, `TOKEN=`, `PASSWORD=`, `PRIVATE=` | MEDIUM |
| Minimax API Key | `MINIMAX_...`, `MINIMAX_API_KEY=` | CRITICAL |
| ZAI API Key | `ZAI_...`, `ZAI_API_KEY=` | CRITICAL |
| High-entropy strings | Shannon entropy > 4.5 (random-looking keys) | HIGH |

---

## Severidades

| Nivel | Significado | Comportamiento por defecto |
|-------|-------------|---------------------------|
| **CRITICAL** | Credencial real de servicio conocido (AWS, GitHub, OpenAI) | Sale en rojo, exit code 1 |
| **HIGH** | Patron generico con alto riesgo (JWT, API keys, DB URLs) | Sale en amarillo, exit code 1 si `--fail-on-secrets` |
| **MEDIUM** | Posible secreto con bajo riesgo (env vars con prefijo comun) | Sale en azul, warning |

---

## Flags

| Flag | Descripcion |
|------|-------------|
| `--scope <path>` | Directorio o archivo a escanear (default: `.`) |
| `--exclude <pattern>` | Patrones a excluir (puede repetirse) |
| `--format <text\|json>` | Formato de salida (default: `text`) |
| `--fix` | Muestra sugerencias de correccion |
| `--git-diff` | Escanea solo cambios sin commgear (unstaged + staged) |
| `--fail-on-secrets` | Sale con codigo 1 si encuentra secrets (para CI) |
| `--interactive` | Modo interactivo para suprimir false positives |
| `--list-types` | Lista todos los tipos de secrets detectados |
| `--entropy-threshold <float>` | Threshold de entropia (default: 4.5) |
| `--no-entropy` | Desactiva deteccion por entropia |
| `--help` | Muestra esta ayuda |

---

## Integracion Pre-commit

```bash
# Instalar hook
py .agent/skills-custom/secrets-scanner/scripts/main.py --git-hooks

# O manualmente en .git/hooks/pre-commit
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
python "$REPO_ROOT/.agent/skills-custom/secrets-scanner/scripts/main.py" \
    --git-diff \
    --fail-on-secrets
if [ $? -ne 0 ]; then
    echo "SECRETS FOUND — commit aborted"
    exit 1
fi
```

---

## Integracion CI/CD (GitHub Actions)

```yaml
- name: Scan for secrets
  run: |
    python .agent/skills-custom/secrets-scanner/scripts/main.py \
        --scope . \
        --format json \
        --fail-on-secrets \
        --exclude node_modules \
        --exclude vendor \
        --exclude .git
```

---

## Salida Text

```
SECRETS SCAN REPORT — .
======================
Scan date: 2026-04-22
Files scanned: 1,247
Secrets found: 3

CRITICAL (1)
  [S001] .env:15 — AWS_SECRET KEY='AKIAIOSFODNN7EXAMPLE'
     -> Remove from code. Use environment variable.

HIGH (2)
  [S003] nexus-app/src/api.ts:89 — Bearer token hardcoded
     -> Use secure token storage

RECOMMENDATIONS:
  1. Run secrets-scanner in CI/CD pipeline
  2. Enable pre-commit hook: secrets-scanner --git-hooks
  3. Rotate exposed credentials immediately

SECRETS FOUND — DO NOT COMMIT
```

---

## Salida JSON

```json
{
  "scan_date": "2026-04-22T10:30:00Z",
  "scope": ".",
  "files_scanned": 1247,
  "secrets_found": 3,
  "findings": [
    {
      "id": "S001",
      "severity": "CRITICAL",
      "type": "aws_access_key",
      "file": ".env",
      "line": 15,
      "matched": "AKIAIOSF***",
      "context": "AWS_SECRET_KEY='AKIAIOSFODNN7EXAMPLE'",
      "remediation": "Remove from code. Use environment variable."
    }
  ],
  "summary": {
    "critical": 1,
    "high": 2,
    "medium": 0
  }
}
```

---

## Exit Codes

| Code | Significado |
|------|-------------|
| 0 | Sin secrets detectados |
| 1 | Secrets detectados (CRITICAL o `--fail-on-secrets` activo) |
| 2 | Error (path no existe, etc.) |

---

## Archivos del Skill

```
.agent/skills-custom/secrets-scanner/
├── SKILL.md              # Esta documentacion
└── scripts/
    ├── __init__.py
    ├── main.py           # CLI entry point
    ├── patterns.py       # Definicion de patrones de deteccion
    ├── entropy.py        # Deteccion de entropia (high-entropy strings)
    └── scanner.py        # Logica de escaneo de archivos
```

---

## Notas

- **Stdlib only**: no requiere dependencias externas. Usa `re` y `math` de la stdlib.
- **Type hints**: todo el codigo tiene type hints completos.
- **No false positives comunes**: excluye automaticamente comentarios con ejemplos,
  strings que contienen "example", "test", "placeholder".
- **Entropy detection**: detecta strings que parecen aleatorios (keys generadas)
  usando la formula de Shannon entropy.
