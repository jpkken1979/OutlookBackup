---
name: payroll-processor
description: "Sistema completo de cálculo y procesamiento de nómina para gestión dispatch y salary de UNS. Calcula gross pay con deducciones japonesas (社保/雇用保険/所得税), persiste en SQLite, exporta JSON/HTML/Excel, valida36協定 y minimum wage. Triggers: payroll, nómina,給与, Japanese payroll, salary calculation, payslip, tax deductions."
---

# Payroll Processor — SKILL.md

**Name:** payroll-processor  
**Version:** 1.0.0 (WEEK 1)  
**Status:** Production Ready  
**Author:** K. Kaneshiro / UNS Antigravity  
**License:** Proprietary (UNS/Antigravity)

---

## Overview

Payroll Processor WEEK 1 is a complete, modular payroll calculation and reporting system for UNS dispatch and salary management. It handles:

- **Payroll Calculation**: Gross pay (regular + overtime + bonus) with Japanese tax deductions
- **Database Persistence**: SQLite with employee master and payslip records
- **Multi-format Output**: JSON, HTML (Jinja2), Excel (openpyxl)
- **Validation**: Input validation, 36協定 (overtime limit), minimum wage enforcement
- **Logging**: Structured logging to files and console

Designed for **Bot Integration** (Week 2) and compatible with **HR Reports** and **Contracts** skills (Week 2-3).

---

## Capabilities

### 1. Calculate Payroll
Orchestrate full payroll calculation for an employee in a specific month.

**Operation:** `calculate`

**Input:**
```json
{
  "operation": "calculate",
  "employee_id": "W001",
  "regular_hours": 160.0,
  "overtime_hours": 10.0,
  "bonus": 50000.0,
  "year": 2026,
  "month": 2
}
```

**Output:**
```json
{
  "success": true,
  "operation": "calculate",
  "payslip_id": "PAYSLIP-20260201-W001",
  "result": {
    "id": "PAYSLIP-20260201-W001",
    "employee_id": "W001",
    "year": 2026,
    "month": 2,
    "regular_hours": 160.0,
    "overtime_hours": 10.0,
    "regular_pay": 200000.0,
    "overtime_pay": 15625.0,
    "bonus": 50000.0,
    "gross_pay": 265625.0,
    "income_tax": 26562.5,
    "social_insurance": 26169.5625,
    "employment_insurance": 1062.5,
    "total_deductions": 53794.5625,
    "net_pay": 211830.4375
  }
}
```

---

### 2. Generate Payslip (JSON/HTML/Excel)
Generate payslip output in multiple formats.

**Operation:** `generate_payslip`

Supports: `json`, `html`, `excel`

---

### 3. Export Report
Placeholder for payroll reports (implemented in WEEK 2).

---

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `operation` | string | Yes | — | `calculate`, `generate_payslip`, `export_report` |
| `employee_id` | string | Yes | — | Employee ID (e.g., 'W001') |
| `regular_hours` | float | Yes | — | Regular work hours (0–200/month) |
| `overtime_hours` | float | No | 0.0 | Overtime hours (0–45/month, 36協定) |
| `bonus` | float | No | 0.0 | Bonus amount (¥) |
| `year` | int | No | 2026 | Fiscal year (2000–2099) |
| `month` | int | No | 1 | Fiscal month (1–12) |
| `output_format` | string | No | json | `json`, `html`, `excel` (for `generate_payslip`) |
| `output_path` | string | No | — | File path for HTML/Excel output |

---

## Examples

### Calculate Payroll
```json
{
  "operation": "calculate",
  "employee_id": "W001",
  "regular_hours": 160.0,
  "overtime_hours": 10.0,
  "bonus": 50000.0,
  "year": 2026,
  "month": 2
}
```

### Generate HTML Payslip
```json
{
  "operation": "generate_payslip",
  "employee_id": "W001",
  "regular_hours": 160.0,
  "output_format": "html",
  "output_path": "/tmp/payslip_W001.html",
  "year": 2026,
  "month": 2
}
```

### Generate Excel Payslip
```json
{
  "operation": "generate_payslip",
  "employee_id": "W001",
  "regular_hours": 160.0,
  "output_format": "excel",
  "output_path": "/tmp/payslip_W001.xlsx",
  "year": 2026,
  "month": 2
}
```

---

## Validations

- **Employee ID**: Must exist in database
- **Regular Hours**: 0–200 per month
- **Overtime Hours**: 0–45 per month (36協定 limit)
- **Bonus**: ≥0
- **Year**: 2000–2099
- **Month**: 1–12

---

## Security

### Input Validation
- Employee ID must exist in database
- All numeric inputs validated for range and type
- Path traversal prevention in file output

### Data Privacy
- Payslips contain sensitive data — store securely
- Never log full payslip data; only transaction IDs
- Encrypt output when transmitted

### Compliance
- Japanese payroll regulations (36協定, tax rates)
- All deductions per employee tax rates in database
- Audit trail in `payroll_history` table

---

## Limitations (WEEK 1)

1. **No Batch Processing**: Single employee at a time
2. **No Report Generation**: HR Reports come in WEEK 2
3. **Fixed Tax Rates**: Per employee record (no dynamic)
4. **SQLite Only**: No PostgreSQL/MySQL
5. **JPY Only**: No multi-currency

---

## Database

**Tables:**
- `employee_master`: Employee data
- `payroll_records`: Payslip records
- `payroll_history`: Audit trail

**Indices:** `employee_status`, `employee_department`, `payroll_employee_date`, `payroll_date`

---

## Performance

- Single Payslip: <100ms
- 50 Employees (1 month): <5 seconds
- Database Size: ~500KB (12 months × 50 employees)

---

## Dependencies

- Python 3.11+
- Pydantic 2.0+
- Jinja2 3.0+
- openpyxl 3.0+
- sqlite3 (stdlib)

---

## Compatibility

**Compatible Agents:**
- `accounting-specialist`
- `finance-officer`
- `hr-specialist`

**Compatible Skills (WEEK 2):**
- `hr-reports`
- `contracts`
- `telegram-bot`

**Gateway:** Antigravity MCP Gateway v3.1+ (port 4747)

---

## Testing

```bash
pytest tests/ -v --cov=payroll_processor
```

Coverage: >80%

---

## Version

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-04-03 | Initial release (WEEK 1) |

---

## Support

Contact: k.kaneshiro@uns-kikaku.com  
Logs: `scripts/logs/payroll_*.log`
