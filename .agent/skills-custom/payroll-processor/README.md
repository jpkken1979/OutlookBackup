# Payroll Processor WEEK 1 — README

Payroll calculation and reporting system for UNS dispatch and salary management.

## Quick Start (5 minutos)

### 1. Instalación de dependencias
```bash
pip install -e ".[dev]"  # Desde raíz del repo
```

### 2. Inicializar base de datos
```python
from pathlib import Path
from payroll_processor.scripts.database import PayrollDatabase

db_path = Path("payroll.db")
db = PayrollDatabase(db_path)
db.init_database()
# Se crea: employee_master, payroll_records, payroll_history
```

### 3. Calcular nómina
```python
from payroll_processor.scripts.main import execute

result = execute({
    "operation": "calculate",
    "employee_id": "W001",
    "regular_hours": 160.0,
    "overtime_hours": 10.0,
    "bonus": 50000.0,
    "year": 2026,
    "month": 2,
})

print(result)
# {
#   "success": true,
#   "operation": "calculate",
#   "payslip_id": "PAYSLIP-20260201-W001",
#   "result": { "gross_pay": ..., "net_pay": ... }
# }
```

### 4. Generar payslip (HTML)
```python
result = execute({
    "operation": "generate_payslip",
    "employee_id": "W001",
    "regular_hours": 160.0,
    "output_format": "html",
    "output_path": "/tmp/payslip_W001.html",
    "year": 2026,
    "month": 2,
})

print(f"Guardado en: {result['result']}")
```

---

## Estructura del Proyecto

```
payroll-processor/
├── scripts/
│   ├── __init__.py
│   ├── main.py              # Entry point (operaciones principales)
│   ├── database.py          # SQLite operations
│   ├── payroll_calculator.py # Lógica de cálculo (impuestos, horas)
│   └── payroll_generators.py # JSON, HTML, Excel output
├── templates/
│   ├── payslip.html         # Template Jinja2 para payslip
│   └── report.html          # Template para reportes
├── tests/
│   ├── __init__.py
│   ├── conftest.py          # Pytest fixtures (sample_employee, temp_db, etc.)
│   ├── test_payroll_calculator.py
│   ├── test_payroll_generators.py
│   ├── test_payroll_execute.py
│   └── fixtures/
│       └── employee_fixtures.py  # Factory functions
├── logs/
│   └── (auto-generated) payroll_YYYYMMDD.log
├── sql_schema.sql           # DDL: CREATE TABLE, indices, triggers
├── payroll.db               # SQLite database (auto-created)
├── SKILL.md                 # Documentación de capabilities
├── skill.yaml               # Metadata para discovery
└── README.md                # Este archivo
```

---

## API Reference

### `execute(params: Dict[str, Any]) -> Dict[str, Any]`

Punto de entrada principal para operaciones de nómina.

**Parámetros:**
- `operation` (str, required): `calculate`, `generate_payslip`, `export_report`
- `employee_id` (str, required): ID del empleado
- `regular_hours` (float, required): Horas regulares (0–200)
- `overtime_hours` (float, optional): Horas extra (0–45, 36協定)
- `bonus` (float, optional): Bonificación (¥)
- `year` (int, optional): Año fiscal (default: 2026)
- `month` (int, optional): Mes (default: 1)
- `output_format` (str, optional): `json`, `html`, `excel` (default: `json`)
- `output_path` (str, optional): Ruta de salida para HTML/Excel

---

## Casos de Uso

### Caso 1: Cálculo básico
```python
result = execute({
    "operation": "calculate",
    "employee_id": "W001",
    "regular_hours": 160.0,
    "year": 2026,
    "month": 2,
})

payslip = result["result"]
print(f"Bruto: ¥{payslip['gross_pay']:,.0f}")
print(f"Descuentos: ¥{payslip['total_deductions']:,.0f}")
print(f"Neto: ¥{payslip['net_pay']:,.0f}")
```

### Caso 2: Con overtime y bonificación
```python
result = execute({
    "operation": "calculate",
    "employee_id": "W002",
    "regular_hours": 160.0,
    "overtime_hours": 20.0,
    "bonus": 100000.0,
    "year": 2026,
    "month": 6,
})
```

### Caso 3: Generar Excel
```python
result = execute({
    "operation": "generate_payslip",
    "employee_id": "W001",
    "regular_hours": 160.0,
    "output_format": "excel",
    "output_path": "/tmp/payslip_W001.xlsx",
    "year": 2026,
    "month": 2,
})
```

---

## Testing

```bash
# Suite completa
pytest tests/ -v

# Con coverage
pytest tests/ -v --cov=payroll_processor --cov-report=html

# Solo calculator
pytest tests/test_payroll_calculator.py -v

# Solo generators
pytest tests/test_payroll_generators.py -v

# Solo integration
pytest tests/test_payroll_execute.py -v
```

---

## Logging

Los logs se guardan en `scripts/logs/payroll_YYYYMMDD.log`:

```
[2026-04-03 10:15:22,123] [INFO] database: Initialized database
[2026-04-03 10:15:23,456] [INFO] payroll_calculator: Initialized calculator for W001
[2026-04-03 10:15:24,789] [INFO] database: Saved payslip: PAYSLIP-20260201-W001
```

---

## Linting & Type Checking

```bash
ruff check scripts/
ruff format scripts/
mypy scripts/payroll_calculator.py
```

---

## Dependencias

- Python 3.11+
- pydantic >= 2.0.0
- jinja2 >= 3.0.0
- openpyxl >= 3.0.0
- sqlite3 (stdlib)

---

## Roadmap

**WEEK 2:** Batch processing, HR Reports, Bot Telegram  
**WEEK 3:** Approval workflow, Contract generation  
**WEEK 4:** Tax forms, Payment scheduling  
**WEEK 5:** Multi-currency, Enterprise features

---

## License & Support

**License:** Proprietary (UNS/Antigravity)  
**Author:** K. Kaneshiro  
**Email:** k.kaneshiro@uns-kikaku.com  
**Status:** Production Ready (v1.0.0)

