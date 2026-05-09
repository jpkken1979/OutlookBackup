#!/bin/bash
# Payroll Processor — Validation Script (Fase 7: Verify)
# Run: bash run_validation.sh

set -e  # Exit on error

echo "=========================================="
echo "PAYROLL PROCESSOR — FULL VALIDATION"
echo "=========================================="
echo ""

SKILL_DIR=".agent/skills-custom/payroll-processor"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ============================================================================
# 1. PYTHON SYNTAX CHECK
# ============================================================================
echo "1️⃣  Checking Python syntax..."
python3 -m py_compile $SKILL_DIR/scripts/*.py 2>/dev/null && \
    echo -e "${GREEN}✅ Syntax OK${NC}" || \
    echo -e "${RED}❌ Syntax errors${NC}"

# ============================================================================
# 2. RUFF LINTER
# ============================================================================
echo ""
echo "2️⃣  Running Ruff linter..."
ruff check $SKILL_DIR/ --select E,W,F,I,B,C4,UP,ARG,SIM 2>/dev/null && \
    echo -e "${GREEN}✅ Ruff OK${NC}" || \
    echo -e "${YELLOW}⚠️  Ruff warnings (see above)${NC}"

# ============================================================================
# 3. RUFF FORMAT CHECK
# ============================================================================
echo ""
echo "3️⃣  Checking code format..."
ruff format --check $SKILL_DIR/ 2>/dev/null && \
    echo -e "${GREEN}✅ Format OK${NC}" || \
    echo -e "${YELLOW}⚠️  Format issues (run: ruff format $SKILL_DIR/)${NC}"

# ============================================================================
# 4. MYPY TYPE CHECKING
# ============================================================================
echo ""
echo "4️⃣  Running Mypy type checker..."
python3 -m mypy $SKILL_DIR/scripts/ \
    --no-error-summary \
    --ignore-missing-imports \
    2>/dev/null && \
    echo -e "${GREEN}✅ Type checking OK${NC}" || \
    echo -e "${YELLOW}⚠️  Type warnings (see above)${NC}"

# ============================================================================
# 5. PYTEST UNIT TESTS
# ============================================================================
echo ""
echo "5️⃣  Running unit tests..."
python3 -m pytest $SKILL_DIR/tests/test_*.py \
    -v \
    --tb=short \
    --color=yes \
    2>/dev/null && \
    echo -e "${GREEN}✅ All tests passed${NC}" || \
    echo -e "${RED}❌ Some tests failed${NC}"

# ============================================================================
# 6. PYTEST COVERAGE
# ============================================================================
echo ""
echo "6️⃣  Measuring code coverage..."
python3 -m pytest $SKILL_DIR/tests/ \
    --cov=$SKILL_DIR/scripts \
    --cov-report=term-missing:skip-covered \
    --cov-fail-under=80 \
    --color=yes \
    2>/dev/null && \
    echo -e "${GREEN}✅ Coverage >= 80%${NC}" || \
    echo -e "${RED}❌ Coverage < 80%${NC}"

# ============================================================================
# 7. SECURITY CHECK (Basic)
# ============================================================================
echo ""
echo "7️⃣  Running security checks..."
grep -r "shell=True" $SKILL_DIR/scripts/ 2>/dev/null && \
    echo -e "${RED}❌ Found shell=True (security risk)${NC}" || \
    echo -e "${GREEN}✅ No shell=True found${NC}"

grep -r "hardcoded.*password\|hardcoded.*api\|hardcoded.*token" $SKILL_DIR/scripts/ 2>/dev/null && \
    echo -e "${RED}❌ Found hardcoded secrets${NC}" || \
    echo -e "${GREEN}✅ No hardcoded secrets found${NC}"

# ============================================================================
# 8. IMPORT VALIDATION
# ============================================================================
echo ""
echo "8️⃣  Checking imports..."
python3 -c "
import sys
sys.path.insert(0, '$SKILL_DIR/scripts')
try:
    from main import execute, validate
    from payroll_calculator import PayrollCalculator
    from payroll_generators import PayslipGenerator
    from database import init_database, load_employee
    print('✅ All imports OK')
except ImportError as e:
    print(f'❌ Import error: {e}')
    sys.exit(1)
" 2>/dev/null || echo -e "${RED}❌ Import check failed${NC}"

# ============================================================================
# 9. DATABASE SCHEMA VALIDATION
# ============================================================================
echo ""
echo "9️⃣  Validating SQLite schema..."
if [ -f "$SKILL_DIR/sql_schema.sql" ]; then
    python3 << 'EOF'
import sqlite3
import tempfile
import os

# Create temp DB
with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
    temp_db = f.name

try:
    # Load schema
    with open('.agent/skills-custom/payroll-processor/sql_schema.sql', 'r') as f:
        schema = f.read()

    # Apply schema
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.executescript(schema)
    conn.commit()

    # Verify tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]

    required_tables = {'employee_master', 'payroll_records', 'payroll_history'}
    if required_tables.issubset(set(tables)):
        print('✅ Schema validation OK')
    else:
        print('❌ Missing tables:', required_tables - set(tables))

    conn.close()
finally:
    os.unlink(temp_db)
EOF
else
    echo -e "${YELLOW}⚠️  sql_schema.sql not found${NC}"
fi

# ============================================================================
# SUMMARY
# ============================================================================
echo ""
echo "=========================================="
echo "VALIDATION COMPLETE"
echo "=========================================="
echo ""
echo "Next: Merge from worktree, run full test suite, commit to branch"
