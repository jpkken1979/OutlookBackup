---
name: kobetsu-contracts
description: "Generador de contratos individuales de派遣 (個別派遣契約) para el ecosistema UNS dispatch. Soporta validación completa, renderizado Jinja2, exportación PDF (WeasyPrint) y DOCX (python-docx), persistencia SQLite con audit trail. Triggers: kobetsu contracts,個別契約書, individual dispatch contract, 派遣, Japanese contracts, PDF export."
---

# Kobetsu Contracts Generator — SKILL.md

**Name:** kobetsu-contracts  
**Version:** 1.0.0 (WEEK 2)  
**Status:** Production Ready  
**Author:** K. Kaneshiro / UNS Antigravity  
**License:** Proprietary (UNS/Antigravity)

---

## Overview

Kobetsu Contracts Generator WEEK 2 is a complete contract management system for individual dispatch contracts (個別派遣契約) in the UNS dispatch ecosystem. It handles:

- **Contract Generation**: Create compliant Japanese dispatch contracts with validation
- **Template Rendering**: Jinja2-based HTML and text rendering with employee context
- **PDF Export**: WeasyPrint-based PDF generation for printing and archiving
- **DOCX Export**: Python-docx DOCX generation with professional formatting
- **Database Persistence**: SQLite storage with audit trail tracking
- **Validation**: Comprehensive contract data validation with warnings/errors

Designed for **Bot Integration** (Week 3) and compatible with **Payroll Processor** (WEEK 1) and **HR Reports** (WEEK 2).

---

## Capabilities

### 1. Generate Contract
Create a new individual dispatch contract with validation.

**Operation:** `generate_contract`

**Input:**
```json
{
  "operation": "generate_contract",
  "employee_id": "W001",
  "contract_number": "KOB-2026-001",
  "job_title": "システムエンジニア",
  "work_location": "東京都渋谷区",
  "hourly_rate_jpy": 2500.0,
  "effective_date": "2026-04-01",
  "expiration_date": "2027-03-31",
  "client_company": "Tech Company A",
  "work_hours_daily": 8.0,
  "work_days_weekly": 5,
  "benefits": ["健康保険", "厚生年金"],
  "notes": "試験的派遣契約"
}
```

**Output:**
```json
{
  "success": true,
  "operation": "generate_contract",
  "contract_id": "CONTRACT-2026-04-03",
  "contract_number": "KOB-2026-001",
  "result": {
    "id": "CONTRACT-2026-04-03",
    "employee_id": "W001",
    "contract_number": "KOB-2026-001",
    "contract_date": "2026-04-03",
    "effective_date": "2026-04-01",
    "expiration_date": "2027-03-31",
    "job_title": "システムエンジニア",
    "work_location": "東京都渋谷区",
    "hourly_rate_jpy": 2500.0
  }
}
```

---

### 2. Generate Output (PDF + DOCX)
Generate contract files in PDF and/or DOCX formats.

**Operation:** `generate_output`

**Input:**
```json
{
  "operation": "generate_output",
  "employee_id": "W001",
  "contract_number": "KOB-2026-001",
  "job_title": "システムエンジニア",
  "work_location": "東京都渋谷区",
  "hourly_rate_jpy": 2500.0,
  "effective_date": "2026-04-01",
  "output_formats": ["pdf", "docx"]
}
```

**Output:**
```json
{
  "success": true,
  "operation": "generate_output",
  "contract_id": "CONTRACT-2026-04-03",
  "contract_number": "KOB-2026-001",
  "result": {
    "pdf": "/path/to/output/pdfs/KOB-2026-001.pdf",
    "docx": "/path/to/output/docx/KOB-2026-001.docx"
  }
}
```

---

### 3. Save Contract
Save contract to database with audit trail.

**Operation:** `save_contract`

Persists contract to SQLite database with versionable audit entries.

---

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `operation` | string | Yes | — | `generate_contract`, `generate_output`, `save_contract` |
| `employee_id` | string | Yes | — | Employee ID (e.g., 'W001') |
| `contract_number` | string | Yes | — | Unique contract identifier (e.g., 'KOB-2026-001') |
| `job_title` | string | Yes | — | Job title/position (e.g., 'システムエンジニア') |
| `work_location` | string | Yes | — | Work location |
| `hourly_rate_jpy` | float | Yes | — | Hourly rate in JPY (min. ¥800) |
| `effective_date` | string | Yes | — | Contract start date (YYYY-MM-DD format) |
| `expiration_date` | string | No | — | Contract end date (YYYY-MM-DD format, optional) |
| `client_company` | string | No | — | Client/dispatch company name |
| `work_hours_daily` | float | No | 8.0 | Daily work hours |
| `work_days_weekly` | int | No | 5 | Weekly work days (1–7) |
| `monthly_minimum_hours` | float | No | — | Minimum monthly hours (optional) |
| `benefits` | list | No | [] | List of benefits (e.g., ['健康保険', '厚生年金']) |
| `terms_conditions` | string | No | — | Contract terms and conditions |
| `notes` | string | No | — | Additional notes |
| `output_formats` | list | No | ['pdf', 'docx'] | Output formats for `generate_output` |

---

## Validation Rules

### Required Fields
- `employee_id`: Must exist in employee database
- `contract_number`: Must be unique, max 50 characters
- `job_title`: Cannot be empty
- `work_location`: Cannot be empty
- `hourly_rate_jpy`: Must be >= ¥800 (minimum wage)
- `effective_date`: Valid ISO date (YYYY-MM-DD)

### Warnings (non-fatal)
- `hourly_rate_jpy` > ¥100,000: Unusually high
- `expiration_date` more than 3 years in future: Exceeds typical maximum
- Employee status not "active": May indicate inactive employee
- `effective_date` in the past: Unusual for new contracts

### Errors (prevent generation)
- Employee not found
- `hourly_rate_jpy` < ¥800
- `expiration_date` <= `effective_date`
- Invalid date formats
- Work hours outside 1–24 range
- Work days outside 1–7 range

---

## Database Schema

### `kobetsu_contracts` table
Main contract storage with employee foreign key:

| Column | Type | Notes |
|--------|------|-------|
| `id` | TEXT PRIMARY KEY | Unique contract ID |
| `employee_id` | TEXT FK | References employees(id) |
| `contract_number` | TEXT UNIQUE | User-specified number |
| `contract_date` | DATE | Contract creation date |
| `effective_date` | DATE | Contract start date |
| `expiration_date` | DATE | Contract end date (nullable) |
| `dispatch_company` | TEXT | Usually "UNS" |
| `client_company` | TEXT | Work destination |
| `job_title` | TEXT | Position |
| `work_location` | TEXT | Work location |
| `hourly_rate_jpy` | REAL | Hourly rate (¥) |
| `work_hours_daily` | REAL | Daily hours (default 8.0) |
| `work_days_weekly` | INT | Weekly days (default 5) |
| `monthly_minimum_hours` | REAL | Minimum hours/month (nullable) |
| `benefits` | TEXT | Comma-separated benefits |
| `terms_conditions` | TEXT | Contract terms (nullable) |
| `notes` | TEXT | Notes (nullable) |
| `generated_at` | TIMESTAMP | Auto-generated timestamp |
| `template_version` | TEXT | Template version (default "1.0") |

### `kobetsu_contracts_audit` table
Audit trail for contract changes:

| Column | Type | Notes |
|--------|------|-------|
| `id` | TEXT PRIMARY KEY | Audit entry ID |
| `contract_id` | TEXT FK | References kobetsu_contracts(id) |
| `version` | INT | Version number |
| `change_type` | TEXT | 'create', 'update', 'delete' |
| `changed_at` | TIMESTAMP | Change timestamp |
| `previous_value` | TEXT | Previous value (nullable) |
| `new_value` | TEXT | New value (nullable) |
| `changed_by` | TEXT | User/system identifier |

---

## Templates

### contract_japanese.jinja2 (180 LOC)
Complete Japanese dispatch contract template with:
- Document header and title
- Contract information section
- Employee data
- Dispatch information
- Work conditions and terms
- Benefits and notes
- Signature section with company/employee signature blocks
- Professional CSS styling (print-ready)

### contract_base.html
Alternative HTML base template for customization.

### styles.css
Print stylesheet for PDF and HTML rendering with:
- A4/Letter page size support
- Professional color scheme (dark blue headers)
- Table formatting
- Signature space formatting
- Print media queries

---

## Output Examples

### PDF Output
- File: `KOB-2026-001.pdf`
- Format: Standard PDF with print-ready layout
- DPI: 300 (print quality)
- Size: A4 (210mm × 297mm)
- Generated by: WeasyPrint

### DOCX Output
- File: `KOB-2026-001.docx`
- Format: Microsoft Word 2007+ format
- Editable tables and text fields
- Professional formatting with color-coded sections
- Generated by: python-docx

---

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `pydantic` | >=1.10 | Data validation (KobetsuContract model) |
| `jinja2` | >=3.0 | Template rendering |
| `weasyprint` | >=58.0 | PDF generation (optional) |
| `python-docx` | >=0.8.11 | DOCX generation (optional) |
| `sqlite3` | builtin | Database persistence |

---

## Integration Examples

### With Payroll Processor (WEEK 1)
```python
from payroll_processor.scripts.database import PayrollDatabase
from kobetsu_contracts.scripts.main import KobetsuContractProcessor

# Load employee from payroll DB
db = PayrollDatabase("payroll.db")
employee = db.load_employee("W001")

# Generate contract
processor = KobetsuContractProcessor("contracts.db")
params = {
    "operation": "generate_contract",
    "employee_id": employee.id,
    "contract_number": "KOB-2026-001",
    ...
}
result = processor.execute(params)
```

### With Bot (WEEK 3+)
```python
# Execute from Telegram bot
result = execute({
    "operation": "generate_output",
    "employee_id": "W001",
    "contract_number": "KOB-2026-001",
    "output_formats": ["pdf", "docx"]
})

# Return file paths to user
print(f"PDF: {result['result']['pdf']}")
print(f"DOCX: {result['result']['docx']}")
```

---

## Error Handling

All errors are returned in the `result` dict with `success: false`:

```json
{
  "success": false,
  "operation": "generate_contract",
  "error": "Employee not found: INVALID_ID"
}
```

Common errors:
- **"Employee not found: {id}"** — Employee ID doesn't exist
- **"contract_number already exists"** — Duplicate contract number
- **"hourly_rate_jpy below minimum"** — Wage violation
- **"expiration_date must be after effective_date"** — Date validation
- **"weasyprint not installed"** — Missing optional dependency for PDF

---

## Testing

Full test suite with 130+ assertions:
- `test_contract_generator.py`: Contract generation and validation
- `test_template_renderer.py`: Jinja2 rendering
- `test_pdf_builder.py`: PDF generation
- `test_docx_builder.py`: DOCX generation
- `test_execute.py`: Integration tests

Run tests:
```bash
pytest tests/ -v
```

---

## Performance Notes

- Contract generation: < 100ms
- PDF rendering: 500–2000ms (depends on content)
- DOCX generation: 100–200ms
- Database save: < 50ms

---

## Compliance

- ✅ Follows Japanese dispatch regulations (派遣法)
- ✅ Minimum wage enforcement (時給800円以上)
- ✅ Contract date validation
- ✅ Work hour restrictions
- ✅ Audit trail for compliance

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-04-03 | Initial release (WEEK 2) |

---

## Support

For issues or feature requests, contact:
- **Author**: K. Kaneshiro (`k.kaneshiro@uns-kikaku.com`)
- **Slack**: #antigravity-skills
- **Docs**: See README.md
