# Payroll Processor — Estructura de Archivos (WEEK 1)

## Directorios a crear

```
.agent/skills-custom/payroll-processor/
├── SKILL.md                          # Documentación (capabilities, parameters, examples)
├── skill.yaml                        # Metadata (name, version, author, parameters, sandbox)
├── STRUCTURE.md                      # Este archivo
│
├── scripts/
│   ├── __init__.py
│   ├── main.py                       # Entry point (execute, validate)
│   ├── payroll_calculator.py         # Core business logic (taxes, calculations)
│   ├── payroll_generators.py         # Output generation (JSON, HTML, Excel)
│   └── database.py                   # SQLite operations
│
├── templates/
│   ├── payslip.html                  # Jinja2 template para recibo (給与明細)
│   └── report.html                   # Jinja2 template para reportes
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                   # Pytest fixtures compartidas
│   ├── test_payroll_execute.py       # Integration tests (execute function)
│   ├── test_payroll_calculator.py    # Unit tests (calculations)
│   ├── test_payroll_generators.py    # Unit tests (output generation)
│   ├── test_payroll_database.py      # Unit tests (DB operations)
│   ├── fixtures/
│   │   ├── employee_fixtures.py      # Mock employee data
│   │   └── payroll_fixtures.py       # Mock payroll data
│   └── __pycache__/                  # Auto-generated (pytest cache)
│
├── logs/
│   └── payroll_processor.log         # Runtime logs (auto-generated)
│
└── README.md                         # Guía de uso (desarrollo, testing, deployment)
```

## Archivos existentes a importar

- **`.agent/skills-custom/_uns_employee_schema.py`**
  - Reutilizar: `Employee`, `Payslip`, `DeductionBreakdown`, `ContractType`, `EmployeeStatus`
  - NO duplicar código

## Archivos a modificar

- **`.env`** → Agregar variables de configuración (tax rates, DB path, etc.)
- **`.agent/core/payroll_models.py`** (nuevo si no existe) → Modelos compartidos
- **`.mcp.json`** (opcional) → Registrar skill como MCP server

## Archivos NO tocar

- `pyproject.toml` — Deps ya están definidas ✅
- `.claudemd` — Referencia ✅
- `IMPLEMENTATION_PLAN_90DAYS.md` — Plan existente ✅
- `.agent/skills-custom/_uns_employee_schema.py` — Reutilizar, no modificar

---

## Tamaño estimado de código

| Archivo | Tipo | Líneas | Complejidad |
|---------|------|--------|------------|
| `scripts/main.py` | Orchestration | 80-100 | Media |
| `scripts/payroll_calculator.py` | Core Logic | 150-200 | Alta |
| `scripts/payroll_generators.py` | Output | 120-150 | Media |
| `scripts/database.py` | Persistence | 100-120 | Media |
| `templates/payslip.html` | Template | 80-100 | Baja |
| `templates/report.html` | Template | 60-80 | Baja |
| `tests/test_*.py` | Tests | 400-500 | Media |
| **TOTAL** | — | **~1100-1250** | — |

---

## Orden de creación (WEEK 1)

### Day 1-2: Foundation
1. ✅ Create directory structure
2. ✅ Create `scripts/__init__.py`
3. ✅ Create `tests/__init__.py`
4. ✅ Create SQL schema (database.py)
5. ✅ Create `conftest.py` con fixtures

### Day 3-4: Core Logic
6. ✅ Implement `payroll_calculator.py`
7. ✅ Implement tests para calculator
8. ✅ Create Pydantic models

### Day 5: Output
9. ✅ Implement `payroll_generators.py`
10. ✅ Create Jinja2 templates
11. ✅ Implement tests para generators

### Day 6: Integration
12. ✅ Implement `main.py` (execute + validate)
13. ✅ Implement integration tests
14. ✅ Implement database.py

### Day 7: Polish
15. ✅ Create SKILL.md
16. ✅ Create skill.yaml
17. ✅ Final testing + lint + coverage
18. ✅ Git commit

---

## Dependencies
- ✅ Already in pyproject.toml:
  - pandas>=2.0.0
  - openpyxl>=3.1.0
  - jinja2>=3.1.0
  - pydantic>=2.0.0
  - pytest>=7.4.0 (dev)

---

## Next Steps
→ Fase 5: Descomponer en tareas ejecutables (día a día)
→ Fase 6: Implementar código (escribir los archivos)
