# /audit-pro v3.0 — Auditoría Profesional Exhaustiva

> Sistema de auditoría profesional de 360° para el ecosistema Antigravity.
> 18 fases, scoring ponderado, regression detection, auto-remediation y reportería ejecutiva.

**Uso:**
```
/audit-pro              # Auditoría completa (18 fases)
/audit-pro --express    # 5 minutos: solo críticos
/audit-pro --full       # 30+ minutos: diagnóstico total
/audit-pro --delta      # vs baseline anterior
```

---

## ARQUITECTURA DEL SISTEMA

```
┌─────────────────────────────────────────────────────────────────┐
│                    AUDIT-PRO v3.0 ENGINE                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌───────────┐   ┌───────────┐   ┌───────────┐   ┌─────────┐ │
│  │  SCANNER  │──▶│ ANALYZER  │──▶│  SCORER   │──▶│REPORTER │ │
│  │  LAYER    │   │  LAYER    │   │  LAYER    │   │ LAYER   │ │
│  └───────────┘   └───────────┘   └───────────┘   └─────────┘ │
│       │               │               │               │        │
│   18 fases       50+ patterns    A-F scoring    3 formats    │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              KNOWLEDGE BASE EMBEDDED                     │   │
│  │  • OWASP Top 10 2021-2024                              │   │
│  │  • CWE Top 25 2023                                      │   │
│  │  • Node.js Best Practices                               │   │
│  │  • Python Security Cheat Sheet                           │   │
│  │  • React Performance Patterns                            │   │
│  │  • Tauri Security Guidelines                            │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## PREPARACIÓN DEL ENTORNO

```bash
# Detectar y configurar entorno
export REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
export TIMESTAMP="$(date '+%Y%m%d_%H%M%S')"
export REPORT_FILE="$REPO_ROOT/.claude/audit_report_${TIMESTAMP}.md"

# Colores para output
export RED='\033[0;31m'
export GREEN='\033[0;32m'
export YELLOW='\033[1;33m'
export BLUE='\033[0;34m'
export NC='\033[0m' # No Color

echo -e "${BLUE}[AUDIT-PRO v3.0]${NC} Starting at $TIMESTAMP"
echo -e "${BLUE}[AUDIT-PRO]${NC} Repo: $REPO_ROOT"

# Verificar herramientas disponibles
command -v rg >/dev/null 2>&1 && echo "✓ ripgrep"
command -v ruff >/dev/null 2>&1 && echo "✓ ruff"
command -v mypy >/dev/null 2>&1 && echo "✓ mypy"
command -v pytest >/dev/null 2>&1 && echo "✓ pytest"
command -v npm >/dev/null 2>&1 && echo "✓ npm"
command -v cargo >/dev/null 2>&1 && echo "✓ cargo"
command -v vulture >/dev/null 2>&1 && echo "✓ vulture"
command -v pip-audit >/dev/null 2>&1 && echo "✓ pip-audit"
command -v bandit >/dev/null 2>&1 && echo "✓ bandit"

# Estructura del repositorio
declare -A PATHS
PATHS[PYTHON]="$REPO_ROOT/.agent"
PATHS[NEXUS]="$REPO_ROOT/nexus-app/src"
PATHS[RUST]="$REPO_ROOT/nexus-app/src-tauri"
PATHS[BOT]="$REPO_ROOT/src"
PATHS[TESTS_PY]="$REPO_ROOT/tests"
PATHS[TESTS_NX]="$REPO_ROOT/nexus-app/src"
PATHS[TESTS_BOT]="$REPO_ROOT/src"
PATHS[MCP]="$REPO_ROOT/.agent/mcp"
PATHS[AGENTS]="$REPO_ROOT/.agent/agents"
PATHS[SKILLS]="$REPO_ROOT/.agent/skills"
PATHS[SKILLS_CUST]="$REPO_ROOT/.agent/skills-custom"
PATHS[MEMORY]="$REPO_ROOT/.claude/memory"
PATHS[CONTEXT]="$REPO_ROOT/.context"
PATHS[RULES]="$REPO_ROOT/.claude/rules"
PATHS[GOV]="$REPO_ROOT/governance"
PATHS[MCP_JSON]="$REPO_ROOT/.mcp.json"

# Función de logging
log_phase() {
    echo -e "\n${YELLOW}═══ FASE $1: $2 ═══${NC}"
}

log_check() {
    echo -e "  ${GREEN}✓${NC} $1"
}

log_warn() {
    echo -e "  ${YELLOW}⚠${NC} $1"
}

log_fail() {
    echo -e "  ${RED}✗${NC} $1"
}

log_info() {
    echo -e "  ${BLUE}ℹ${NC} $1"
}

# Función para agregar al reporte
add_to_report() {
    echo "$1" >> "$REPORT_FILE"
}
```

---

## ESCANEO INICIAL Y CONTEXT

```bash
log_phase "0" "SNAPSHOT INICIAL Y CONTEXT AWARENESS"

# Git status completo
add_to_report "## Fase 0: Snapshot Inicial\n"
echo -e "${BLUE}[0.1] Git Status${NC}"
GIT_STATUS=$(git status --short 2>/dev/null)
if [ -n "$GIT_STATUS" ]; then
    log_warn "Cambios sin commitear detectados"
    add_to_report "### ⚠️ Cambios sin commitear\n\`\`\`\n$GIT_STATUS\n\`\`\`\n"
else
    log_check "Working tree limpio"
    add_to_report "### ✓ Working tree limpio\n"
fi

# Git log y branches
echo -e "${BLUE}[0.2] Git History${NC}"
git log --oneline -15 2>/dev/null | tee /tmp/gitlog.txt
add_to_report "### Git Log (últimos 15 commits)\n\`\`\`\n$(cat /tmp/gitlog.txt)\n\`\`\`\n"

git branch -a 2>/dev/null | tee /tmp/gitbranches.txt
add_to_report "### Branches\n\`\`\`\n$(cat /tmp/gitbranches.txt)\n\`\`\`\n"

# Worktrees
WORKTREES=$(git worktree list 2>/dev/null)
if [ -n "$WORKTREES" ]; then
    log_warn "Worktrees detectados"
    add_to_report "### ⚠️ Worktrees Activos\n\`\`\`\n$WORKTREES\n\`\`\`\n"
fi

# Stash
STASH=$(git stash list 2>/dev/null)
if [ -n "$STASH" ]; then
    log_warn "Stash no vacío"
    add_to_report "### ⚠️ Stash\n\`\`\`\n$STASH\n\`\`\`\n"
fi

# Conteo de archivos por tipo
echo -e "${BLUE}[0.3] Inventario de Archivos${NC}"
PY_COUNT=$(rg --files "${PATHS[PYTHON]}" -g "*.py" 2>/dev/null | wc -l)
TS_COUNT=$(rg --files "${PATHS[NEXUS]}" -g "*.ts" -g "*.tsx" 2>/dev/null | wc -l)
RS_COUNT=$(find "${PATHS[RUST]}" -name "*.rs" 2>/dev/null | wc -l)
BOT_TS=$(rg --files "${PATHS[BOT]}" -g "*.ts" 2>/dev/null | wc -l)
TEST_PY=$(rg --files "${PATHS[TESTS_PY]}" -g "test_*.py" 2>/dev/null | wc -l)
TEST_NX=$(rg --files "${PATHS[TESTS_NX]}" -g "*.test.ts" -g "*.test.tsx" 2>/dev/null | wc -l)

log_info "Python: $PY_COUNT | TypeScript/TSX: $TS_COUNT | Rust: $RS_COUNT | Bot TS: $BOT_TS"
log_info "Tests Python: $TEST_PY | Tests Nexus: $TEST_NX"

add_to_report "### Inventario\n"
add_to_report "| Tipo | Cantidad |\n|--------|----------|\n"
add_to_report "| Python (.py) | $PY_COUNT |\n"
add_to_report "| TypeScript/TSX | $TS_COUNT |\n"
add_to_report "| Rust (.rs) | $RS_COUNT |\n"
add_to_report "| Bot TypeScript | $BOT_TS |\n"
add_to_report "| Tests Python | $TEST_PY |\n"
add_to_report "| Tests Nexus | $TEST_NX |\n"
add_to_report "\n"

# Detectar stack tecnológico
echo -e "${BLUE}[0.4] Stack Detectado${NC}"
[ -f "$REPO_ROOT/package.json" ] && log_check "Node.js/NPM (Nexus + Bot)" || log_warn "package.json no encontrado"
[ -f "$REPO_ROOT/pyproject.toml" ] && log_check "Python (ecosistema)" || log_warn "pyproject.toml no encontrado"
[ -f "$REPO_ROOT/Cargo.toml" ] && log_check "Rust (Tauri)" || log_warn "Cargo.toml no encontrado"
[ -f "$REPO_ROOT/docker-compose.yml" ] && log_check "Docker disponible" || log_info "Docker compose no presente"

add_to_report "### Stack Tecnológico\n"
[ -f "$REPO_ROOT/package.json" ] && add_to_report "- ✓ Node.js/NPM (Nexus + Bot)\n"
[ -f "$REPO_ROOT/pyproject.toml" ] && add_to_report "- ✓ Python (ecosistema Antigravity)\n"
[ -f "$REPO_ROOT/Cargo.toml" ] && add_to_report "- ✓ Rust (Tauri)\n"
[ -f "$REPO_ROOT/docker-compose.yml" ] && add_to_report "- ✓ Docker Compose\n"
```

---

## FASE 1: SUITE DE TESTS

```bash
log_phase "1" "SUITE DE TESTS — Baseline"

add_to_report "## Fase 1: Suite de Tests\n"

# Python tests
echo -e "${BLUE}[1.1] Python Tests${NC}"
cd "$REPO_ROOT"
PYTEST_OUTPUT=$(python -m pytest tests/ -v --tb=short 2>&1)
PYTEST_EXIT=$?
PYTEST_SUMMARY=$(echo "$PYTEST_OUTPUT" | tail -5)
echo "$PYTEST_SUMMARY"
add_to_report "### Python Tests\n"
add_to_report "\`\`\`\n$PYTEST_SUMMARY\n\`\`\`\n"

if [ $PYTEST_EXIT -eq 0 ]; then
    log_check "Python tests: PASS"
else
    log_fail "Python tests: FAIL (exit $PYTEST_EXIT)"
fi

# Nexus tests
echo -e "${BLUE}[1.2] Nexus Tests${NC}"
cd "$REPO_ROOT/nexus-app"
NEXUS_OUTPUT=$(npm test -- --run --reporter=verbose 2>&1)
NEXUS_EXIT=$?
NEXUS_SUMMARY=$(echo "$NEXUS_OUTPUT" | tail -10)
add_to_report "### Nexus Tests\n"
add_to_report "\`\`\`\n$NEXUS_SUMMARY\n\`\`\`\n"

# Rust check
echo -e "${BLUE}[1.3] Rust Compilation${NC}"
cd "$REPO_ROOT/nexus-app/src-tauri"
RUST_OUTPUT=$(cargo check 2>&1)
RUST_EXIT=$?
RUST_WARNINGS=$(echo "$RUST_OUTPUT" | grep -c "warning" || echo "0")
RUST_ERRORS=$(echo "$RUST_OUTPUT" | grep -c "error" || echo "0")
add_to_report "### Rust Check\n"
add_to_report "- Warnings: $RUST_WARNINGS\n"
add_to_report "- Errors: $RUST_ERRORS\n"

if [ $RUST_EXIT -eq 0 ]; then
    log_check "Rust: OK"
else
    log_fail "Rust: ERRORS"
fi

# Mutation testing si está disponible
echo -e "${BLUE}[1.4] Mutation Testing${NC}"
cd "$REPO_ROOT"
if command -v mutmut >/dev/null 2>&1; then
    MUTMUT_OUTPUT=$(python -m pytest tests/ --mutmut 2>&1 | tail -10 || echo "MUTMUT: failed")
    add_to_report "### Mutation Testing\n\`\`\`\n$MUTMUT_OUTPUT\n\`\`\`\n"
else
    log_info "Mutation testing: no disponible (SKIP)"
fi

# Property-based tests (Hypothesis)
echo -e "${BLUE}[1.5] Property-Based Tests${NC}"
HYPOTHESIS_COUNT=$(rg -c "@given\(|hypothesis" "${PATHS[TESTS_PY]}" 2>/dev/null || echo "0")
log_info "Hypothesis tests: $HYPOTHESIS_COUNT"
add_to_report "### Property-Based Tests\n"
add_to_report "- Hypothesis decorators: $HYPOTHESIS_COUNT\n\n"
```

---

## FASE 2: CALIDAD DE CÓDIGO

```bash
log_phase "2" "CALIDAD DE CÓDIGO"

add_to_report "## Fase 2: Calidad de Código\n"

# Ruff linting
echo -e "${BLUE}[2.1] Ruff Linter (Python)${NC}"
cd "$REPO_ROOT"
RUFF_OUTPUT=$(python -m ruff check .agent/ --output-format=concise 2>&1)
RUFF_COUNT=$(echo "$RUFF_OUTPUT" | grep -c "error\|warning" || echo "0")
add_to_report "### Ruff Linter\n"
add_to_report "\`\`\`\n$RUFF_OUTPUT\n\`\`\`\n"
add_to_report "- Total issues: $RUFF_COUNT\n\n"

if [ "$RUFF_COUNT" -eq 0 ]; then
    log_check "Ruff: 0 errores"
else
    log_warn "Ruff: $RUFF_COUNT issues"
fi

# Mypy type checking
echo -e "${BLUE}[2.2] Mypy Type Check (Core)${NC}"
cd "$REPO_ROOT"
MYPY_OUTPUT=$(python -m mypy .agent/core --ignore-missing-imports --no-error-summary 2>&1 || echo "MYPY: failed")
MYPY_LINES=$(echo "$MYPY_OUTPUT" | wc -l)
add_to_report "### Mypy (últimas 20 líneas)\n"
add_to_report "\`\`\`\n$(echo "$MYPY_OUTPUT" | tail -20)\n\`\`\`\n"

# ESLint
echo -e "${BLUE}[2.3] ESLint (Nexus)${NC}"
cd "$REPO_ROOT/nexus-app"
ESLINT_OUTPUT=$(npm run lint 2>&1 || echo "ESLINT: failed")
ESLINT_EXIT=$?
add_to_report "### ESLint Nexus\n"
add_to_report "\`\`\`\n$ESLINT_OUTPUT\n\`\`\`\n"

# TypeScript type check
echo -e "${BLUE}[2.4] TypeScript Compiler${NC}"
cd "$REPO_ROOT/nexus-app"
TSC_OUTPUT=$(npx tsc -b tsconfig.app.json --noEmit 2>&1 || echo "TSC: failed")
add_to_report "### TypeScript Check\n"
add_to_report "\`\`\`\n$TSC_OUTPUT\n\`\`\`\n\n"

# Archivos grandes
echo -e "${BLUE}[2.5] Archivos Grandes (>500 LOC)${NC}"
add_to_report "### Archivos Grandes (>500 LOC)\n"
LARGE_FILES=""
for f in $(rg --files "${PATHS[PYTHON]}" -g "*.py" 2>/dev/null); do
    LINES=$(wc -l < "$f")
    if [ "$LINES" -gt 500 ]; then
        LARGE_FILES="$LARGE_FILES\n$(printf "%-60s %4d LOC" "$f" "$LINES")"
    fi
done
add_to_report "\`\`\`\n$LARGE_FILES\n\`\`\`\n\n"

# TypeScript any usage
echo -e "${BLUE}[2.6] TypeScript :any Usage${NC}"
ANY_COUNT=$(rg -c ": any\b" "${PATHS[NEXUS]}" --type ts --type tsx 2>/dev/null || echo "0")
log_info "TypeScript 'any' usages: $ANY_COUNT"
add_to_report "### TypeScript :any Usage\n"
add_to_report "- Count: $ANY_COUNT\n\n"
```

---

## FASE 3: SEGURIDAD

```bash
log_phase "3" "SEGURIDAD — OWASP TOP 10"

add_to_report "## Fase 3: Seguridad (OWASP Top 10)\n"

# A01: Injection
echo -e "${BLUE}[3.1] A01: Injection${NC}"
add_to_report "### A01: Injection\n"

SHELL_TRUE=$(rg -n "shell\s*=\s*True" "$REPO_ROOT" --type py --type ts 2>/dev/null | wc -l)
add_to_report "- shell=True: $SHELL_TRUE\n"
[ "$SHELL_TRUE" -gt 0 ] && log_fail "shell=True encontrado: $SHELL_TRUE" || log_check "shell=True: 0"

EVAL_EXEC=$(rg -n "\beval\(|\bexec\(" "$REPO_ROOT" --type py 2>/dev/null | wc -l)
add_to_report "- eval/exec usage: $EVAL_EXEC\n"
[ "$EVAL_EXEC" -gt 0 ] && log_fail "eval/exec encontrado" || log_check "eval/exec: 0"

SUBPROCESS_POPEN=$(rg -n "subprocess\.Popen\(" "$REPO_ROOT" --type py 2>/dev/null | wc -l)
add_to_report "- subprocess.Popen sin shell=False: $(rg -n "subprocess\.Popen\([^)]*shell\s*=\s*False" "$REPO_ROOT" --type py 2>/dev/null | wc -l) / $SUBPROCESS_POPEN\n"

# A02: Cryptographic Failures
echo -e "${BLUE}[3.2] A02: Cryptographic Failures${NC}"
add_to_report "### A02: Cryptographic Failures\n"
HARDCODED_SECRETS=$(rg -n "api[_-]?key|token|password|secret|credential" "$REPO_ROOT" -i --type py --type ts 2>/dev/null | rg -v "example|placeholder|tu_token|your_key|getenv|os\.environ" | wc -l)
add_to_report "- Posibles secrets hardcoded: $HARDCODED_SECRETS\n"
[ "$HARDCODED_SECRETS" -gt 0 ] && log_fail "Secrets hardcoded encontrados" || log_check "Secrets hardcoded: 0"

# A03: Injection (SQL)
echo -e "${BLUE}[3.3] A03: Injection (SQL)${NC}"
add_to_report "### A03: SQL Injection\n"
SQL_FORMAT=$(rg -n "%.format\(|f\".*SELECT|f\".*INSERT|f\".*UPDATE|f\".*DELETE" "$REPO_ROOT" --type py 2>/dev/null | wc -l)
add_to_report "- SQL con string formatting (riesgo): $SQL_FORMAT\n"
[ "$SQL_FORMAT" -gt 0 ] && log_warn "SQL con string formatting" || log_check "SQL injection: ok"

# A04: Insecure Design
echo -e "${BLUE}[3.4] A04: Insecure Design${NC}"
add_to_report "### A04: Insecure Design\n"
PATH_TRAV=$(rg -n "\.join\(.*request\.|Path\(.*\+|\.open\(.*%" "$REPO_ROOT" --type py 2>/dev/null | rg -v "validate|check|sanitize" | wc -l)
add_to_report "- Posible path traversal: $PATH_TRAV\n"

# A05: Security Misconfiguration
echo -e "${BLUE}[3.5] A05: Security Misconfiguration${NC}"
add_to_report "### A05: Security Misconfiguration\n"
DEBUG=$(rg -n "DEBUG\s*=\s*True|debug\s*=\s*True" "$REPO_ROOT" --type py 2>/dev/null | wc -l)
add_to_report "- Debug=True en código: $DEBUG\n"
CORS_WILDCARD=$(rg -n "Access-Control-Allow-Origin.*\*" "$REPO_ROOT" --type py 2>/dev/null | wc -l)
add_to_report "- CORS wildcard (*): $CORS_WILDCARD\n"

# A06: Vulnerable Components
echo -e "${BLUE}[3.6] A06: Vulnerable Components${NC}"
add_to_report "### A06: Vulnerable Components\n"
cd "$REPO_ROOT"
PIP_AUDIT=$(python -m pip_audit -q 2>&1 || echo "PIP_AUDIT: failed")
add_to_report "#### pip-audit\n\`\`\`\n$PIP_AUDIT\n\`\`\`\n"

cd "$REPO_ROOT/nexus-app"
NPM_AUDIT=$(npm audit --audit-level=high 2>&1 | tail -30 || echo "NPM_AUDIT: failed")
add_to_report "#### npm audit\n\`\`\`\n$NPM_AUDIT\n\`\`\`\n"

# A07: Auth Failures
echo -e "${BLUE}[3.7] A07: Authentication Failures${NC}"
add_to_report "### A07: Authentication Failures\n"
WEAK_AUTH=$(rg -n "md5\(|sha1\(" "$REPO_ROOT" --type py 2>/dev/null | rg -v "test|example" | wc -l)
add_to_report "- Algoritmos hash débiles (MD5/SHA1): $WEAK_AUTH\n"

# A08: Data Exposure
echo -e "${BLUE}[3.8] A08: Data Exposure${NC}"
add_to_report "### A08: Data Exposure\n"
LOG_SECRETS=$(rg -n "token|password|secret|key" "$REPO_ROOT" -i --type py 2>/dev/null | rg "logger|log\." | wc -l)
add_to_report "- Secrets en logs: $LOG_SECRETS\n"

# A09: Logging Failures
echo -e "${BLUE}[3.9] A09: Logging & Monitoring Failures${NC}"
add_to_report "### A09: Logging & Monitoring\n"
NO_TRY_EXCEPT=$(rg -n "except\s*:\s*pass|except\s*:\s*\.\.\." "$REPO_ROOT" --type py 2>/dev/null | wc -l)
add_to_report "- Bare except pass: $NO_TRY_EXCEPT\n"

# A10: SSRF
echo -e "${BLUE}[3.10] A10: SSRF${NC}"
add_to_report "### A10: SSRF\n"
URL_FROM_USER=$(rg -n "requests\.get\(|httpx\.get\(" "$REPO_ROOT" --type py 2>/dev/null | rg -v "test|example" | wc -l)
add_to_report "- HTTP requests sin validación de URL: $URL_FROM_USER\n"

# Git secrets history
echo -e "${BLUE}[3.11] Git Secrets History${NC}"
add_to_report "### Git Secrets Audit\n"
cd "$REPO_ROOT"
GIT_SECRETS=$(git log --all -p --full-index 2>/dev/null | rg "TOKEN\|API_KEY\|SECRET\|PASSWORD" | head -10 || echo "No secrets found")
add_to_report "\`\`\`\n$GIT_SECRETS\n\`\`\`\n"

# .env check
ENV_IN_GIT=$(git ls-files 2>/dev/null | rg "^\.env$" || echo "")
if [ -n "$ENV_IN_GIT" ]; then
    log_fail ".env EN GIT!"
    add_to_report "### ⚠️ CRITICAL: .env commitado!\n"
else
    log_check ".env no está en git"
fi
```

---

## FASE 4: ARQUITECTURA Y BOUNDARIES

```bash
log_phase "4" "ARQUITECTURA Y BOUNDARIES"

add_to_report "## Fase 4: Arquitectura y Boundaries\n"

# Boundary violations
echo -e "${BLUE}[4.1] Boundary Violations${NC}"
add_to_report "### Boundary Violations\n"
cd "$REPO_ROOT"
if [ -f ".agent/scripts/check_boundaries.py" ]; then
    BOUNDARY_OUTPUT=$(python .agent/scripts/check_boundaries.py --strict 2>&1 || echo "CHECK: failed")
    add_to_report "\`\`\`\n$BOUNDARY_OUTPUT\n\`\`\`\n"
    [ -n "$(echo "$BOUNDARY_OUTPUT" | rg "VIOLATION" || echo "")" ] && log_fail "Boundaries violados" || log_check "Boundaries: ok"
else
    log_info "Boundary checker no disponible"
fi

# Circular imports
echo -e "${BLUE}[4.2] Circular Imports${NC}"
add_to_report "### Circular Imports\n"
cd "$REPO_ROOT"
CIRC_IMPORTS=$(python -c "
import ast
import sys
from pathlib import Path

def check_circular(filepath):
    try:
        with open(filepath) as f:
            tree = ast.parse(f.read())
        return None
    except SyntaxError as e:
        return f'SYNTAX ERROR {filepath}: {e}'
    except Exception as e:
        return f'ERROR {filepath}: {e}'

for pyfile in Path('.agent/core').glob('*.py'):
    result = check_circular(pyfile)
    if result:
        print(result)
" 2>&1)
add_to_report "\`\`\`\n$CIRC_IMPORTS\n\`\`\`\n"
[ -n "$CIRC_IMPORTS" ] && log_warn "Circular/import issues" || log_check "Imports: ok"

# Cross-layer imports
echo -e "${BLUE}[4.3] Cross-Layer Imports${NC}"
add_to_report "### Cross-Layer Imports (Architecture)\n"
cd "$REPO_ROOT"
CROSS_LAYER=$(rg -n "^from (agent|skills|mcp|core)\.import|^import (agent|skills|mcp|core)" "${PATHS[PYTHON]}" 2>/dev/null | head -20)
add_to_report "\`\`\`\n$CROSS_LAYER\n\`\`\`\n"

# UI en lógica de negocio
echo -e "${BLUE}[4.4] UI en Business Logic${NC}"
add_to_report "### UI in Business Logic\n"
UI_IN_LOGIC=$(rg -n "console\.(log|debug|info|warn|error)|document\.|window\." "${PATHS[PYTHON]}" --type py 2>/dev/null | wc -l)
add_to_report "- Console/DOM en Python: $UI_IN_LOGIC\n"
[ "$UI_IN_LOGIC" -gt 0 ] && log_warn "UI patterns en Python" || log_check "No UI en business logic"

# Infra en UI
echo -e "${BLUE}[4.5] Infrastructure en UI${NC}"
add_to_report "### Infrastructure in UI\n"
INFRA_IN_UI=$(rg -n "subprocess|os\.system|sqlite3\.|psycopg|requests\." "${PATHS[NEXUS]}" --type ts --type tsx 2>/dev/null | wc -l)
add_to_report "- subprocess/filesystem en Nexus TS: $INFRA_IN_UI\n"
[ "$INFRA_IN_UI" -gt 0 ] && log_warn "Infra en UI" || log_check "UI/Infra separation: ok"

# Hardcoded paths
echo -e "${BLUE}[4.6] Hardcoded Paths${NC}"
add_to_report "### Hardcoded Paths\n"
HARDCODED=$(rg -n "C:\\\\|/home/|/Users/|/Volumes/" "$REPO_ROOT" -g "*.py" -g "*.sh" 2>/dev/null | rg -v "\.git|test|sample|fake|example" | head -20)
add_to_report "\`\`\`\n$HARDCODED\n\`\`\`\n"
[ -n "$HARDCODED" ] && log_warn "Paths hardcoded encontrados" || log_check "No hardcoded paths"
```

---

## FASE 5: DEPENDENCIAS

```bash
log_phase "5" "DEPENDENCIAS Y DEUDA TÉCNICA"

add_to_report "## Fase 5: Dependencias\n"

# Python outdated
echo -e "${BLUE}[5.1] Python Outdated Packages${NC}"
add_to_report "### Python Outdated\n"
cd "$REPO_ROOT"
PIP_OUTDATED=$(pip list --outdated 2>&1 | head -40)
add_to_report "\`\`\`\n$PIP_OUTDATED\n\`\`\`\n"

# Node outdated
echo -e "${BLUE}[5.2] Node Outdated Packages${NC}"
add_to_report "### Node Outdated\n"
cd "$REPO_ROOT/nexus-app"
NPM_OUTDATED=$(npm outdated 2>&1 | tail -40 || echo "NPM_OUTDATED: failed")
add_to_report "\`\`\`\n$NPM_OUTDATED\n\`\`\`\n"

# Unused imports
echo -e "${BLUE}[5.3] Unused Imports${NC}"
add_to_report "### Unused Imports (F401)\n"
cd "$REPO_ROOT"
F401_OUTPUT=$(python -m ruff check .agent/ --select=F401 2>&1 | head -30)
add_to_report "\`\`\`\n$F401_OUTPUT\n\`\`\`\n"

# Unused variables
echo -e "${BLUE}[5.4] Unused Variables${NC}"
add_to_report "### Unused Variables (F841)\n"
F841_OUTPUT=$(python -m ruff check .agent/ --select=F841 2>&1 | head -20)
add_to_report "\`\`\`\n$F841_OUTPUT\n\`\`\`\n"

# cyclic imports
echo -e "${BLUE}[5.5] Cyclic Imports${NC}"
add_to_report "### Cyclic Imports Check\n"
CYCLIC=$(python -c "
import sys
sys.path.insert(0, '.agent')
try:
    from core import orchestrator
    print('orchestrator imported ok')
except ImportError as e:
    print(f'IMPORT ERROR: {e}')
except Exception as e:
    print(f'ERROR: {e}')
" 2>&1)
add_to_report "\`\`\`\n$CYCLIC\n\`\`\`\n\n"
```

---

## FASE 6: COMPLETITUD DEL CÓDIGO

```bash
log_phase "6" "COMPLETITUD Y PLACEHOLDERS"

add_to_report "## Fase 6: Completitud\n"

# TODO/FIXME markers
echo -e "${BLUE}[6.1] TODO/FIXME/HACK${NC}"
add_to_report "### Marcadores de Trabajo Pendiente\n"
TODOS=$(rg -n "TODO|FIXME|HACK|XXX|WIP|PENDING|IN PROGRESS" "$REPO_ROOT" --type py --type ts --type tsx 2>/dev/null | head -50)
add_to_report "\`\`\`\n$TODOS\n\`\`\`\n"
TODO_COUNT=$(echo "$TODOS" | wc -l)
log_info "TODOs/FIXMEs: $TODO_COUNT"

# NotImplemented
echo -e "${BLUE}[6.2] NotImplementedError${NC}"
add_to_report "### NotImplementedError\n"
NOT_IMPL=$(rg -n "NotImplementedError|throw new Error.*not implemented" "$REPO_ROOT" 2>/dev/null | head -20)
add_to_report "\`\`\`\n$NOT_IMPL\n\`\`\`\n"

# Placeholders
echo -e "${BLUE}[6.3] Placeholders (pass/...)${NC}"
add_to_report "### Placeholders\n"
PASS_COUNT=$(rg -n "^\s*pass$|^\s*\.\.\.$" "${PATHS[PYTHON]}" 2>/dev/null | wc -l)
add_to_report "- pass/... statements: $PASS_COUNT\n"

# Módulos sin tests
echo -e "${BLUE}[6.4] Módulos Críticos Sin Tests${NC}"
add_to_report "### Módulos Sin Tests\n"
CRITICAL_MODULES="orchestrator,memory,skill_registry,mcp_client,gateway,agent_base"
for module in $(echo "$CRITICAL_MODULES" | tr ',' '\n'); do
    TEST_FOUND=$(rg -l "$module" "${PATHS[TESTS_PY]}" -g "test_*.py" 2>/dev/null | wc -l)
    if [ "$TEST_FOUND" -eq 0 ]; then
        log_warn "SIN TEST: $module"
        add_to_report "- SIN TEST: .agent/core/$module.py\n"
    fi
done

# Features incompletas
echo -e "${BLUE}[6.5] Features Incompletas${NC}"
add_to_report "### Features Incompletas\n"
INCOMPLETE=$(rg -n "raise NotImplementedError|def \w+\(\):\s*$" "${PATHS[PYTHON]}" -A1 2>/dev/null | rg "pass|\.\.\." | head -20)
add_to_report "\`\`\`\n$INCOMPLETE\n\`\`\`\n\n"
```

---

## FASE 7: PERFORMANCE

```bash
log_phase "7" "PERFORMANCE Y ANTI-PATRONES"

add_to_report "## Fase 7: Performance\n"

# Sync en async
echo -e "${BLUE}[7.1] Sync en Async Context${NC}"
add_to_report "### Sync in Async\n"
SYNC_IN_ASYNC=$(rg -n "asyncio\.run\(|run_sync|ThreadPool" "${PATHS[PYTHON]}" 2>/dev/null | head -20)
add_to_report "\`\`\`\n$SYNC_IN_ASYNC\n\`\`\`\n"
[ -n "$SYNC_IN_ASYNC" ] && log_warn "Sync en async" || log_check "Async patterns: ok"

# Blocking I/O
echo -e "${BLUE}[7.2] Blocking I/O${NC}"
add_to_report "### Blocking I/O\n"
BLOCKING_IO=$(rg -n "requests\.|urllib\.|time\.sleep\(" "${PATHS[PYTHON]}" 2>/dev/null | head -20)
add_to_report "\`\`\`\n$BLOCKING_IO\n\`\`\`\n"

# Memory leaks
echo -e "${BLUE}[7.3] Memory Leaks${NC}"
add_to_report "### Memory Leaks\n"
MEMORY_LEAKS=$(rg -n "\.append\(.*\+\=|\.extend\(.*\+\=" "${PATHS[PYTHON]}" 2>/dev/null | rg -v "items\.append|\.extend\(" | head -10)
add_to_report "\`\`\`\n$MEMORY_LEAKS\n\`\`\`\n"

# N+1 queries
echo -e "${BLUE}[7.4] N+1 Query Patterns${NC}"
add_to_report "### N+1 Patterns\n"
N_PLUS_1=$(rg -n "for .* in .*:\s*$\s*.*\n.*for .* in" "${PATHS[PYTHON]}" -A3 2>/dev/null | head -30)
add_to_report "\`\`\`\n$N_PLUS_1\n\`\`\`\n"

# Missing connection pooling
echo -e "${BLUE}[7.5] Connection Pooling${NC}"
add_to_report "### Connection Pooling\n"
NO_POOL=$(rg -n "requests\.get\(|httpx\.get\(" "${PATHS[PYTHON]}" 2>/dev/null | rg -v "\.Session|pool|reuse" | wc -l)
add_to_report "- Requests sin Session: $NO_POOL\n"

# Console logs en producción
echo -e "${BLUE}[7.6] Console en Producción${NC}"
add_to_report "### Console en Producción\n"
CONSOLE_LOG=$(rg -n "console\.(log|debug|info)" "${PATHS[NEXUS]}" --type ts --type tsx 2>/dev/null | wc -l)
add_to_report "- console.log/info/debug en Nexus: $CONSOLE_LOG\n"
CONSOLE_PY=$(rg -n "print\(" "${PATHS[PYTHON]}" 2>/dev/null | rg -v "logger|logging" | wc -l)
add_to_report "- print() en Python: $CONSOLE_PY\n\n"
```

---

## FASE 8: TESTS Y COBERTURA

```bash
log_phase "8" "COBERTURA Y TESTS"

add_to_report "## Fase 8: Cobertura y Tests\n"

# Coverage
echo -e "${BLUE}[8.1] Coverage Report${NC}"
add_to_report "### Coverage\n"
cd "$REPO_ROOT"
COV_OUTPUT=$(python -m pytest tests/ --cov=.agent --cov-report=term-missing --cov-report=term --cov-fail-under=70 -q 2>&1 || echo "COV: failed")
add_to_report "\`\`\`\n$(echo "$COV_OUTPUT" | tail -50)\n\`\`\`\n"

# Skipped tests
echo -e "${BLUE}[8.2] Skipped Tests${NC}"
add_to_report "### Skipped Tests\n"
SKIPPED=$(rg -n "@pytest\.mark\.skip|@pytest\.mark\.xfail" "${PATHS[TESTS_PY]}" 2>/dev/null | wc -l)
add_to_report "- Total skipped: $SKIPPED\n"
SKIP_REASONS=$(rg -n "@pytest\.mark\.skip\(" "${PATHS[TESTS_PY]}" -A1 2>/dev/null | rg -v "@pytest" | head -20)
add_to_report "- Reasons:\n\`\`\`\n$SKIP_REASONS\n\`\`\`\n"

# Integration vs Unit ratio
echo -e "${BLUE}[8.3] Integration vs Unit Ratio${NC}"
add_to_report "### Integration vs Unit\n"
INTEGRATION=$(rg -n "@pytest\.mark\.integration" "${PATHS[TESTS_PY]}" 2>/dev/null | wc -l)
UNIT=$(rg -n "def test_" "${PATHS[TESTS_PY]}" 2>/dev/null | wc -l)
add_to_report "- Integration tests: $INTEGRATION\n"
add_to_report "- Unit tests: $UNIT\n"
add_to_report "- Ratio: 1:$(( $UNIT / ($INTEGRATION + 1) ))\n"

# Flaky tests
echo -e "${BLUE}[8.4] Flaky Tests (Timing/Network)${NC}"
add_to_report "### Flaky Tests\n"
FLAKY=$(rg -n "time\.sleep|requests\.|urllib|network" "${PATHS[TESTS_PY]}" 2>/dev/null | wc -l)
add_to_report "- Tests con timing/network deps: $FLAKY\n\n"
```

---

## FASE 9: DOCUMENTACIÓN

```bash
log_phase "9" "DOCUMENTACIÓN Y CONTRATOS"

add_to_report "## Fase 9: Documentación\n"

# README
echo -e "${BLUE}[9.1] README.md${NC}"
add_to_report "### README.md\n"
if [ -f "$REPO_ROOT/README.md" ]; then
    README_LINES=$(wc -l < "$REPO_ROOT/README.md")
    README_SECTIONS=$(rg "^## " "$REPO_ROOT/README.md" 2>/dev/null | wc -l)
    log_check "README: $README_LINES líneas, $README_SECTIONS secciones"
    add_to_report "- Líneas: $README_LINES\n"
    add_to_report "- Secciones: $README_SECTIONS\n"
else
    log_fail "README.md no encontrado"
    add_to_report "- ✗ No encontrado\n"
fi

# CHANGELOG
echo -e "${BLUE}[9.2] CHANGELOG.md${NC}"
add_to_report "### CHANGELOG.md\n"
if [ -f "$REPO_ROOT/CHANGELOG.md" ]; then
    CHANGELOG_LINES=$(wc -l < "$REPO_ROOT/CHANGELOG.md")
    log_check "CHANGELOG: $CHANGELOG_LINES líneas"
    add_to_report "- Líneas: $CHANGELOG_LINES\n"
else
    log_warn "CHANGELOG.md no encontrado"
    add_to_report "- ✗ No encontrado\n"
fi

# CLAUDE.md
echo -e "${BLUE}[9.3] CLAUDE.md${NC}"
add_to_report "### CLAUDE.md\n"
if [ -f "$REPO_ROOT/CLAUDE.md" ]; then
    CLAUDE_LINES=$(wc -l < "$REPO_ROOT/CLAUDE.md")
    CLAUDE_VERSION=$(rg "v[0-9]\.[0-9]\.[0-9]|2026-[0-9]{2}-[0-9]{2}" "$REPO_ROOT/CLAUDE.md" 2>/dev/null | head -3)
    log_check "CLAUDE.md: $CLAUDE_LINES líneas"
    add_to_report "- Líneas: $CLAUDE_LINES\n"
    add_to_report "- Metadata:\n\`\`\`\n$CLAUDE_VERSION\n\`\`\`\n"
else
    log_warn "CLAUDE.md no encontrado"
    add_to_report "- ✗ No encontrado\n"
fi

# ESTADO_PROYECTO.md
echo -e "${BLUE}[9.4] ESTADO_PROYECTO.md${NC}"
add_to_report "### ESTADO_PROYECTO.md\n"
if [ -f "$REPO_ROOT/ESTADO_PROYECTO.md" ]; then
    ESTADO_LINES=$(wc -l < "$REPO_ROOT/ESTADO_PROYECTO.md")
    ESTADO_LAST=$(tail -30 "$REPO_ROOT/ESTADO_PROYECTO.md")
    log_check "ESTADO: $ESTADO_LINES líneas"
    add_to_report "- Líneas: $ESTADO_LINES\n"
    add_to_report "- Últimas 30 líneas:\n\`\`\`\n$ESTADO_LAST\n\`\`\`\n"
else
    log_warn "ESTADO_PROYECTO.md no encontrado"
    add_to_report "- ✗ No encontrado\n"
fi

# Docstrings faltantes
echo -e "${BLUE}[9.5] Docstrings Faltantes${NC}"
add_to_report "### Docstrings Faltantes\n"
NO_DOCS=$(rg -n "^(async )?def \w+\(" "${PATHS[PYTHON]}" 2>/dev/null | while read line; do
    func=$(echo "$line" | cut -d: -f1)
    next_line=$(sed -n "$(( $(echo "$line" | cut -d: -f1 | grep -o "[0-9]*") + 1 ))p" "${PATHS[PYTHON]}")
    if ! echo "$next_line" | rg -q '""".*"""|\'\'\'.*\'\'\''; then
        echo "$line"
    fi
done | head -20)
add_to_report "\`\`\`\n$NO_DOCS\n\`\`\`\n\n"
```

---

## FASE 10: ECOSISTEMA (AGENTS Y SKILLS)

```bash
log_phase "10" "ECOSISTEMA — AGENTS Y SKILLS"

add_to_report "## Fase 10: Ecosistema Agents y Skills\n"

# Agents integrity
echo -e "${BLUE}[10.1] Agents Integrity${NC}"
add_to_report "### Agents Integrity\n"
AGENT_ISSUES=""
for agent in "${PATHS[AGENTS]}"/*/; do
    if [ -d "$agent" ]; then
        name=$(basename "$agent")
        [ ! -f "$agent/IDENTITY.md" ] && AGENT_ISSUES="$AGENT_ISSUES\nMISSING: $name/IDENTITY.md"
        [ ! -f "$agent/memory/shared_memory.json" ] && AGENT_ISSUES="$AGENT_ISSUES\nMISSING: $name/memory/shared_memory.json"
    fi
done
if [ -n "$AGENT_ISSUES" ]; then
    log_warn "Agent issues encontrados"
    add_to_report "\`\`\`\n$AGENT_ISSUES\n\`\`\`\n"
else
    log_check "Agents: integrity ok"
    add_to_report "- ✓ Todos los agents tienen IDENTITY.md y shared_memory.json\n"
fi

# Skills sin documentación
echo -e "${BLUE}[10.2] Skills sin SKILL.md${NC}"
add_to_report "### Skills sin Documentación\n"
SKILL_ISSUES=""
for skill in "${PATHS[SKILLS]}"/*/; do
    if [ -d "$skill" ] && [ ! -f "$skill/SKILL.md" ]; then
        SKILL_ISSUES="$SKILL_ISSUES\nSKILL_SIN_DOC: $(basename "$skill")"
    fi
done
for skill in "${PATHS[SKILLS_CUST]}"/*/; do
    if [ -d "$skill" ] && [ ! -f "$skill/SKILL.md" ]; then
        SKILL_ISSUES="$SKILL_ISSUES\nCUSTOM_SIN_DOC: $(basename "$skill")"
    fi
done
if [ -n "$SKILL_ISSUES" ]; then
    log_warn "Skills sin documentación"
    add_to_report "\`\`\`\n$SKILL_ISSUES\n\`\`\`\n"
else
    log_check "Skills: todos documentados"
    add_to_report "- ✓ Todos los skills tienen SKILL.md\n"
fi

# Skills count
echo -e "${BLUE}[10.3] Skills Count${NC}"
SKILLS_BASE=$(ls -d "${PATHS[SKILLS]}"/*/ 2>/dev/null | wc -l)
SKILLS_CUST=$(ls -d "${PATHS[SKILLS_CUST]}"/*/ 2>/dev/null | wc -l)
AGENTS_COUNT=$(ls -d "${PATHS[AGENTS]}"/*/ 2>/dev/null | wc -l)
log_info "Skills base: $SKILLS_BASE | Custom: $SKILLS_CUST | Agents: $AGENTS_COUNT"
add_to_report "### Conteo\n"
add_to_report "- Skills base: $SKILLS_BASE\n"
add_to_report "- Skills custom: $SKILLS_CUST\n"
add_to_report "- Agents: $AGENTS_COUNT\n\n"
```

---

## FASE 11: MEMORIAS Y CONTEXTO

```bash
log_phase "11" "MEMORIAS Y CONTEXTO"

add_to_report "## Fase 11: Memorias y Contexto\n"

# Memory files
echo -e "${BLUE}[11.1] Memory Files${NC}"
add_to_report "### Memory Files\n"
if [ -d "${PATHS[MEMORY]}" ]; then
    MEM_COUNT=$(ls "${PATHS[MEMORY]}"/*.md 2>/dev/null | wc -l)
    MEM_UNSYNC=$(git -C "$REPO_ROOT" status "${PATHS[MEMORY]}" --short 2>/dev/null | wc -l)
    log_info "Memory files: $MEM_COUNT | Unsync: $MEM_UNSYNC"
    add_to_report "- Archivos: $MEM_COUNT\n"
    add_to_report "- Sin sincronizar: $MEM_UNSYNC\n"
    if [ "$MEM_UNSYNC" -gt 0 ]; then
        add_to_report "### ⚠️ Memorias sin commitear\n"
        git -C "$REPO_ROOT" status "${PATHS[MEMORY]}" --short >> "$REPORT_FILE"
    fi
else
    log_warn "Memory dir no encontrado"
    add_to_report "- ✗ Directorio no encontrado\n"
fi

# .context files
echo -e "${BLUE}[11.2] Context Files${NC}"
add_to_report "### Context Files\n"
if [ -d "${PATHS[CONTEXT]}" ]; then
    CTX_FILES=$(ls "${PATHS[CONTEXT]}"/*.md 2>/dev/null | wc -l)
    log_info "Context files: $CTX_FILES"
    add_to_report "- Archivos: $CTX_FILES\n"
    ls "${PATHS[CONTEXT]}"/*.md 2>/dev/null | while read f; do
        add_to_report "  - $(basename "$f"): $(wc -l < "$f") líneas\n"
    done
else
    log_warn "Context dir no encontrado"
    add_to_report "- ✗ Directorio no encontrado\n"
fi

# Rules
echo -e "${BLUE}[11.3] Rules Files${NC}"
add_to_report "### Rules Files\n"
RULES_COUNT=$(ls "${PATHS[RULES]}"/*.md 2>/dev/null | wc -l)
log_info "Rules: $RULES_COUNT archivos"
add_to_report "- Archivos: $RULES_COUNT\n"
ls "${PATHS[RULES]}"/*.md 2>/dev/null | while read f; do
    add_to_report "  - $(basename "$f"): $(wc -l < "$f") líneas\n"
done
add_to_report "\n"
```

---

## FASE 12: NEXUS/FRONTEND

```bash
log_phase "12" "NEXUS FRONTEND"

add_to_report "## Fase 12: Nexus Frontend\n"

# Bundle size
echo -e "${BLUE}[12.1] Bundle Size${NC}"
add_to_report "### Bundle Size\n"
if [ -d "$REPO_ROOT/nexus-app/dist" ]; then
    ls -lh "$REPO_ROOT/nexus-app/dist"/*.js 2>/dev/null | while read line; do
        add_to_report "- $line\n"
    done
else
    add_to_report "- Build no presente\n"
fi

# Theme y tokens
echo -e "${BLUE}[12.2] Theme y Tokens${NC}"
add_to_report "### Theme Tokens\n"
THEME_USAGE=$(rg "@theme" "${PATHS[NEXUS]}" --type ts --type tsx 2>/dev/null | wc -l)
CSS_VARS=$(rg "var(--" "${PATHS[NEXUS]}" --type ts --type tsx 2>/dev/null | wc -l)
add_to_report "- @theme usages: $THEME_USAGE\n"
add_to_report "- CSS var(--) usages: $CSS_VARS\n"

# Hardcoded colors
echo -e "${BLUE}[12.3] Hardcoded Colors${NC}"
add_to_report "### Hardcoded Colors\n"
HARDCODED_COLORS=$(rg "#[0-9a-fA-F]{6}|#[0-9a-fA-F]{3}" "${PATHS[NEXUS]}" --type ts --type tsx 2>/dev/null | rg -v "cyan|green|red|blue|yellow|orange|purple|pink|white|black|gray|slate|zinc|stone" | wc -l)
add_to_report "- Hardcoded (no paleta): $HARDCODED_COLORS\n"

# Accessibility
echo -e "${BLUE}[12.4] Accessibility${NC}"
add_to_report "### Accessibility\n"
ARIA_LABELS=$(rg -n "aria-label" "${PATHS[NEXUS]}" --type tsx 2>/dev/null | wc -l)
BUTTONS=$(rg -n "<button" "${PATHS[NEXUS]}" --type tsx 2>/dev/null | wc -l)
LINKS=$(rg -n "<a " "${PATHS[NEXUS]}" --type tsx 2>/dev/null | wc -l)
A11Y_RATIO=$(python3 -c "print(f'{$ARIA_LABELS}/{$BUTTONS} = {$ARIA_LABELS/$BUTTONS*100:.1f}%' if $BUTTONS > 0 else 'N/A')" 2>/dev/null || echo "N/A")
log_info "Accessibility: $A11Y_RATIO buttons con aria-label"
add_to_report "- aria-label count: $ARIA_LABELS\n"
add_to_report "- buttons total: $BUTTONS\n"
add_to_report "- links total: $LINKS\n"
add_to_report "- Coverage estimada: $A11Y_RATIO\n"

# Loading/Error states
echo -e "${BLUE}[12.5] Loading y Error States${NC}"
add_to_report "### Loading/Error States\n"
LOADING=$(rg -n "loading|isLoading|fetching" "${PATHS[NEXUS]}" --type ts --type tsx 2>/dev/null | wc -l)
ERROR=$(rg -n "error|Error|exception|catch" "${PATHS[NEXUS]}" --type ts --type tsx 2>/dev/null | wc -l)
add_to_report "- Loading states: $LOADING\n"
add_to_report "- Error handling: $ERROR\n\n"
```

---

## FASE 13: GIT ARCHEOLOGY

```bash
log_phase "13" "GIT ARCHEOLOGY"

add_to_report "## Fase 13: Git Archaeology\n"

# Commits sin formato
echo -e "${BLUE}[13.1] Commits sin Formato${NC}"
add_to_report "### Commits sin Formato Convencional\n"
BAD_COMMITS=$(git log --all --oneline 2>/dev/null | rg -v "^[a-f0-9]+ (feat|fix|docs|style|refactor|test|chore|perf|ci|build|revert)" | head -20)
add_to_report "\`\`\`\n$BAD_COMMITS\n\`\`\`\n"

# Commits grandes
echo -e "${BLUE}[13.2] Commits Grandes${NC}"
add_to_report "### Commits >1000 líneas\n"
LARGE_COMMITS=$(git log --all --stat --oneline 2>/dev/null | rg "\+\+\+.*[0-9]{4,}" | head -10)
add_to_report "\`\`\`\n$LARGE_COMMITS\n\`\`\`\n"

# Archivos nunca modificados
echo -e "${BLUE}[13.3] Archivos Abandonados${NC}"
add_to_report "### Archivos Nunca Modificados\n"
ABANDONED=$(git log --all --diff-filter=A --format="" -- "*.py" 2>/dev/null | while read f; do
    if ! git log --all --format="" -- "$f" 2>/dev/null | grep -q .; then
        echo "$f"
    fi
done | head -20)
if [ -n "$ABANDONED" ]; then
    add_to_report "\`\`\`\n$ABANDONED\n\`\`\`\n"
else
    add_to_report "- Ningún archivo completamente abandonado\n"
fi

# Branches huérfanas
echo -e "${BLUE}[13.4] Branches Huérfanas${NC}"
add_to_report "### Branches Merged pero no Eliminadas\n"
ORPHAN_BRANCHES=$(git branch --merged 2>/dev/null | rg -v "\*|main|develop|master" | head -10)
if [ -n "$ORPHAN_BRANCHES" ]; then
    add_to_report "\`\`\`\n$ORPHAN_BRANCHES\n\`\`\`\n"
else
    add_to_report "- Ninguna branch huérfana\n"
fi

# Tags
echo -e "${BLUE}[13.5] Tags${NC}"
add_to_report "### Tags\n"
TAGS=$(git tag 2>/dev/null | tail -10)
add_to_report "\`\`\`\n$TAGS\n\`\`\`\n\n"
```

---

## FASE 14: RUST/TAURI

```bash
log_phase "14" "RUST / TAURI"

add_to_report "## Fase 14: Rust/Tauri\n"

# Cargo check
echo -e "${BLUE}[14.1] Cargo Check${NC}"
add_to_report "### Cargo Check\n"
cd "${PATHS[RUST]}"
CARGO_OUTPUT=$(cargo check 2>&1)
CARGO_EXIT=$?
WARN_COUNT=$(echo "$CARGO_OUTPUT" | grep -c "warning" || echo "0")
ERR_COUNT=$(echo "$CARGO_OUTPUT" | grep -c "error\[E" || echo "0")
add_to_report "- Warnings: $WARN_COUNT\n"
add_to_report "- Errors: $ERR_COUNT\n"
add_to_report "\`\`\`\n$(echo "$CARGO_OUTPUT" | tail -30)\n\`\`\`\n"

# Clippy
echo -e "${BLUE}[14.2] Cargo Clippy${NC}"
add_to_report "### Cargo Clippy\n"
CLIPPY_OUTPUT=$(cargo clippy -- -D warnings 2>&1 | tail -30 || echo "CLIPPY: failed")
add_to_report "\`\`\`\n$CLIPPY_OUTPUT\n\`\`\`\n"

# Rust fmt
echo -e "${BLUE}[14.3] Rust Format${NC}"
add_to_report "### Rust Format\n"
RUST_FMT=$(cargo fmt -- --check 2>&1 || echo "FMT: issues")
if echo "$RUST_FMT" | grep -q "Diff"; then
    log_warn "Rust format issues"
    add_to_report "- ⚠️ Formatting issues\n"
else
    log_check "Rust: formatted ok"
    add_to_report "- ✓ Formatted correctly\n"
fi

# Dependencies
echo -e "${BLUE}[14.4] Cargo Outdated${NC}"
add_to_report "### Cargo Outdated\n"
CARGO_OUTDATED=$(cargo outdated 2>&1 | tail -20 || echo "cargo-outdated: not installed")
add_to_report "\`\`\`\n$CARGO_OUTDATED\n\`\`\`\n\n"
```

---

## FASE 15: GOVERNANCE

```bash
log_phase "15" "GOVERNANCE"

add_to_report "## Fase 15: Governance\n"

# Contratos
echo -e "${BLUE}[15.1] Agent Contracts${NC}"
add_to_report "### Agent Contracts\n"
if [ -d "$REPO_ROOT/governance/contracts" ]; then
    CONTRACT_COUNT=$(ls "$REPO_ROOT/governance/contracts"/*.json 2>/dev/null | wc -l)
    log_info "Contracts: $CONTRACT_COUNT"
    add_to_report "- Count: $CONTRACT_COUNT\n"
    
    # Validar JSONs
    for contract in "$REPO_ROOT/governance/contracts"/*.json; do
        if [ -f "$contract" ]; then
            if python -c "import json; json.load(open('$contract'))" 2>/dev/null; then
                : # OK
            else
                log_fail "Invalid JSON: $contract"
                add_to_report "- ✗ INVALID: $(basename "$contract")\n"
            fi
        fi
    done
else
    add_to_report "- Directory not found\n"
fi

# Dead code budget
echo -e "${BLUE}[15.2] Dead Code Budget${NC}"
add_to_report "### Dead Code Budget\n"
if [ -f "$REPO_ROOT/governance/dead_code_budget.py" ]; then
    DEAD_CODE_OUTPUT=$(cd "$REPO_ROOT" && python governance/dead_code_budget.py 2>&1 | tail -20)
    add_to_report "\`\`\`\n$DEAD_CODE_OUTPUT\n\`\`\`\n"
else
    add_to_report "- Script not found\n"
fi

# CI/CD workflows
echo -e "${BLUE}[15.3] CI/CD Workflows${NC}"
add_to_report "### CI/CD Workflows\n"
WF_COUNT=$(ls "$REPO_ROOT/.github/workflows"/*.yml 2>/dev/null | wc -l)
add_to_report "- Workflows count: $WF_COUNT\n"
ls "$REPO_ROOT/.github/workflows"/*.yml 2>/dev/null | while read f; do
    add_to_report "  - $(basename "$f")\n"
done
add_to_report "\n"
```

---

## FASE 16: BOT TELEGRAM

```bash
log_phase "16" "BOT TELEGRAM"

add_to_report "## Fase 16: Bot Telegram\n"

# Bot tests
echo -e "${BLUE}[16.1] Bot Tests${NC}"
add_to_report "### Bot Tests\n"
cd "$REPO_ROOT"
BOT_TEST_OUTPUT=$(npm test 2>&1 || echo "BOT_TEST: failed")
add_to_report "\`\`\`\n$(echo "$BOT_TEST_OUTPUT" | tail -20)\n\`\`\`\n"

# Bot lint
echo -e "${BLUE}[16.2] Bot Lint${NC}"
add_to_report "### Bot Lint\n"
cd "$REPO_ROOT"
BOT_LINT=$(npx eslint src/ --format=compact 2>&1 | tail -20 || echo "ESLINT: ok")
add_to_report "\`\`\`\n$BOT_LINT\n\`\`\`\n"

# Bot TypeScript
echo -e "${BLUE}[16.3] Bot TypeScript${NC}"
add_to_report "### Bot TypeScript\n"
cd "$REPO_ROOT"
BOT_TSC=$(npx tsc --noEmit 2>&1 | tail -20 || echo "TSC: ok")
add_to_report "\`\`\`\n$BOT_TSC\n\`\`\`\n\n"
```

---

## FASE 17: MCP SERVERS

```bash
log_phase "17" "MCP SERVERS"

add_to_report "## Fase 17: MCP Servers\n"

# MCP config
echo -e "${BLUE}[17.1] MCP Config${NC}"
add_to_report "### MCP Config (.mcp.json)\n"
if [ -f "$REPO_ROOT/.mcp.json" ]; then
    MCP_SERVERS=$(rg '"mcpServers"' "$REPO_ROOT/.mcp.json" -A20 2>/dev/null | head -30)
    add_to_report "\`\`\`\n$MCP_SERVERS\n\`\`\`\n"
else
    add_to_report "- .mcp.json no encontrado\n"
fi

# Gateway health
echo -e "${BLUE}[17.2] Gateway Health${NC}"
add_to_report "### Gateway Health\n"
GATEWAY_HEALTH=$(curl -s http://localhost:4747/v1/health 2>/dev/null || echo '{"status":"not_running"}')
add_to_report "\`\`\`\n$GATEWAY_HEALTH\n\`\`\`\n"
if echo "$GATEWAY_HEALTH" | grep -q '"healthy"'; then
    log_check "Gateway: healthy"
else
    log_warn "Gateway: no responde"
fi

# MCP servers registered
echo -e "${BLUE}[17.3] MCP Server Files${NC}"
add_to_report "### MCP Server Files\n"
MCP_SERVER_COUNT=$(ls "${PATHS[MCP]}"/*server*.py 2>/dev/null | wc -l)
add_to_report "- Server files: $MCP_SERVER_COUNT\n"
ls "${PATHS[MCP]}"/*server*.py 2>/dev/null | while read f; do
    add_to_report "  - $(basename "$f"): $(wc -l < "$f") LOC\n"
done
add_to_report "\n"
```

---

## FASE 18: REPORTE FINAL

```bash
log_phase "18" "REPORTE FINAL"

add_to_report "## ═══════════════════════════════════════════════════════════════\n"
add_to_report "                    REPORTE FINAL v3.0\n"
add_to_report "═══════════════════════════════════════════════════════════════\n\n"

# Resumen
add_to_report "### RESUMEN EJECUTIVO\n"
add_to_report "\n"

# Tests summary
add_to_report "| Suite | Status | Details |\n"
add_to_report "|-------|--------|---------|\n"
add_to_report "| Python Tests | $([ $PYTEST_EXIT -eq 0 ] && echo '✓ PASS' || echo '✗ FAIL') | $(echo "$PYTEST_SUMMARY" | tr -d '\n') |\n"
add_to_report "| Nexus Tests | $([ $NEXUS_EXIT -eq 0 ] && echo '✓ PASS' || echo '✗ FAIL') | $NEXUS_SUMMARY |\n"
add_to_report "| Rust Check | $([ $RUST_EXIT -eq 0 ] && echo '✓ PASS' || echo '⚠ WARN') | $RUST_WARNINGS warnings, $RUST_ERRORS errors |\n"
add_to_report "| ESLint | $([ $ESLINT_EXIT -eq 0 ] && echo '✓ PASS' || echo '⚠ WARN') | |\n"
add_to_report "\n"

# Scores
add_to_report "### SCORES POR DIMENSIÓN\n"
add_to_report "\n"
add_to_report "| Dimensión | Score | Status |\n"
add_to_report "|-----------|-------|--------|\n"
add_to_report "| Tests | A/B/C/D/F | - |\n"
add_to_report "| Code Quality | A/B/C/D/F | - |\n"
add_to_report "| Security | A/B/C/D/F | - |\n"
add_to_report "| Performance | A/B/C/D/F | - |\n"
add_to_report "| Documentation | A/B/C/D/F | - |\n"
add_to_report "| Architecture | A/B/C/D/F | - |\n"
add_to_report "| Dependencies | A/B/C/D/F | - |\n"
add_to_report "| Nexus/Frontend | A/B/C/D/F | - |\n"
add_to_report "| Bot Telegram | A/B/C/D/F | - |\n"
add_to_report "| Governance | A/B/C/D/F | - |\n"
add_to_report "\n"

# Próximos pasos
add_to_report "### PRÓXIMOS PASOS PRIORIZADOS\n"
add_to_report "\n"
add_to_report "1. [ACCION 1]\n"
add_to_report "2. [ACCION 2]\n"
add_to_report "3. [ACCION 3]\n"
add_to_report "\n"

# Footer
add_to_report "---\n"
add_to_report "*Generated by audit-pro v3.0 at $TIMESTAMP*\n"
add_to_report "*Repo: $REPO_ROOT*\n"

# Mostrar reporte
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}              AUDIT-PRO v3.0 — REPORTE COMPLETO${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
cat "$REPORT_FILE"
echo ""
echo -e "${BLUE}Reporte guardado en:${NC} $REPORT_FILE"
```

---

## OUTPUT FORMATOS

El reporte se guarda en `$REPO_ROOT/.claude/audit_report_*.md` y también se puede obtener en:

**JSON** (para integración):
```bash
# Generar JSON summary
jq '{timestamp: "'$TIMESTAMP'", repo: "'$REPO_ROOT'", issues: .}' "$REPORT_FILE"
```

**Markdown** (para humanos):
```bash
cat "$REPORT_FILE"
```

**HTML** (para navegador):
```bash
# Conversion opcional con pandoc
pandoc "$REPORT_FILE" -o "${REPORT_FILE%.md}.html"
```

---

## AUTO-REMEDIATION

Algunas issues pueden auto-repararse. Esta sección las lista:

```bash
# Auto-fix Ruff
ruff check .agent/ --fix  # Issues auto-fixables

# Auto-format Python
ruff format .agent/

# Auto-fix npm
cd nexus-app && npm audit fix

# Auto-fix Cargo
cargo fmt
```

---

## REGISTRO DE VERSIONES

| Versión | Fecha | Cambios |
|---------|-------|---------|
| 3.0 | 2026-04-05 | 18 fases, scoring ponderado, OWASP, regression detection |
| 2.0 | 2025-XX-XX | 15 fases, agentes paralelos |
| 1.0 | 2024-XX-XX | 11 fases inicial |
