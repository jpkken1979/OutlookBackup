---
name: hr-reports
description: "Generate professional HR reports (roster, hours, dispatch, absence) from employee attendance and payroll data. Exports to Excel (.xlsx), HTML, or CSV with automatic formatting and summaries. Triggers: hr reports, attendance, roster, payroll, dispatch, absence, employee reports, Excel export."
---

# HR Reports Generator Skill

**Skill Name:** hr-reports  
**Version:** 1.0.0  
**Tier:** 6 (Specialized)  
**Status:** Production  
**Category:** HR / Reporting

## Overview

Generate professional HR reports (roster, hours, dispatch, absence) from employee attendance and payroll data. Exports to Excel (.xlsx), HTML, or CSV with automatic formatting and summaries.

## Capabilities

### Report Types

| Type | Purpose | Output |
|------|---------|--------|
| **roster** | Attendance summary by employee | Present/absent/late/early leave counts + total hours |
| **hours** | Payroll detail (hours × rate) | Daily entries with earnings calculation |
| **dispatch** | Dispatch assignment summary | Client assignments with allocation hours and costs |
| **absence** | Absence/leave tracking | Detailed absence records with reasons |

### Features

- **Automatic Data Enrichment**: Merges attendance, employee info, and payroll rates
- **Professional Formatting**: Excel sheets with styled headers, borders, auto-widths
- **Summary Statistics**: Aggregated metrics per report type
- **Multi-Sheet Export**: Combine multiple reports in single workbook
- **Database Persistence**: Saves report metadata for auditing
- **Date Range Filtering**: Flexible period selection
- **Employee Filtering**: Generate for specific employee or all staff

## Parameters

```yaml
start_date:
  type: date
  description: Report period start (YYYY-MM-DD)
  required: true
  example: "2024-03-01"

end_date:
  type: date
  description: Report period end (YYYY-MM-DD)
  required: true
  example: "2024-03-31"

report_type:
  type: string
  description: "Type of report"
  required: true
  enum: [roster, hours, dispatch, absence]
  example: "roster"

employee_id:
  type: string
  description: "Optional employee filter (omit for all staff)"
  required: false
  example: "EMP001"

output_path:
  type: string
  description: "Path where to save report (Excel file)"
  required: false
  example: "/reports/roster_2024_03.xlsx"

file_format:
  type: string
  description: "Export format"
  required: false
  enum: [xlsx, html, csv]
  default: "xlsx"

include_summary:
  type: boolean
  description: "Include summary statistics section"
  required: false
  default: true

generated_by:
  type: string
  description: "User/system identifier for audit trail"
  required: false
  default: "system"
```

## Usage Examples

### Generate Roster Report

```python
from scripts.main import HRReportProcessor, ReportParams

processor = HRReportProcessor("/path/to/database.db")

params = ReportParams(
    start_date="2024-03-01",
    end_date="2024-03-31",
    report_type="roster",
    output_path="/reports/roster_march.xlsx",
    include_summary=True,
    generated_by="hr_admin"
)

result = processor.execute(params)
processor.export_excel(result, params.output_path)
```

### Generate Hours/Payroll Report

```python
params = ReportParams(
    start_date="2024-03-01",
    end_date="2024-03-31",
    report_type="hours",
    output_path="/reports/payroll_march.xlsx"
)

result = processor.generate_hours(params)
processor.export_excel(result, params.output_path)
```

### Generate Dispatch Assignments

```python
params = ReportParams(
    start_date="2024-03-01",
    end_date="2024-03-31",
    report_type="dispatch",
    employee_id="EMP001",  # Single employee
    file_format="xlsx"
)

result = processor.generate_dispatch(params)
```

### Generate Absence Report

```python
params = ReportParams(
    start_date="2024-03-01",
    end_date="2024-03-31",
    report_type="absence"
)

result = processor.generate_absence(params)
# Access DataFrame directly
print(result["data"])
print(result["summary"])
```

## Output Formats

### Excel (.xlsx)

- **Advantages**: Professional formatting, multiple sheets, formulas support
- **Sheets**: Data (with summary if requested), styles (headers, borders, auto-width)
- **Size**: Typical 50-500KB depending on record count
- **Compatibility**: All Excel versions, Google Sheets, LibreOffice

### HTML

- **Advantages**: Responsive design, browser-viewable, print-friendly
- **Features**: Japanese formatting (日本語対応), summary cards, responsive tables
- **Styling**: Included CSS with print optimizations
- **Size**: Typical 20-200KB

### CSV

- **Advantages**: Lightweight, universal compatibility
- **Format**: RFC 4180 compliant
- **Encoding**: UTF-8

## Data Requirements

### Required Tables

The skill expects these SQLite tables:

```sql
-- Employees
CREATE TABLE employees (
    employee_id TEXT PRIMARY KEY,
    name TEXT,
    department TEXT,
    hourly_rate DECIMAL(8, 2)
    -- ... other fields
);

-- Attendance Records
CREATE TABLE attendance_records (
    id INTEGER PRIMARY KEY,
    employee_id TEXT,
    date DATE,
    hours_worked DECIMAL(5, 2),
    status TEXT,  -- present, absent, late, early_leave
    reason TEXT
);

-- Dispatch Assignments
CREATE TABLE dispatch_assignments (
    id INTEGER PRIMARY KEY,
    employee_id TEXT,
    dispatch_date DATE,
    client_name TEXT,
    hours_allocated DECIMAL(5, 2),
    hourly_rate DECIMAL(8, 2)
);

-- HR Reports (auto-created)
CREATE TABLE hr_reports (
    id INTEGER PRIMARY KEY,
    report_type TEXT,
    report_name TEXT,
    start_date DATE,
    end_date DATE,
    generated_by TEXT,
    file_path TEXT,
    created_at TIMESTAMP
);
```

## Report Output Examples

### Roster Report Summary
```
Total Employees: 45
Present Days (Total): 880
Absent Days (Total): 35
Late Arrivals: 22
Early Leaves: 18
Average Hours/Day: 7.9
```

### Hours Report Summary
```
Record Count: 892
Total Hours Worked: 7,056.5
Total Earnings: ¥10,584,750
Average Hourly Rate: ¥1,500
Unique Employees: 45
```

### Dispatch Report Summary
```
Total Assignments: 156
Total Hours Allocated: 1,248
Total Assignment Cost: ¥1,872,000
Unique Employees: 42
Unique Clients: 12
```

## Error Handling

The skill validates:
- **Date range**: end_date >= start_date
- **Report type**: Must be one of [roster, hours, dispatch, absence]
- **Output path**: Directory must exist if specified
- **Employee ID**: Filtered employee must exist in database
- **File format**: Must be one of [xlsx, html, csv]

Validation errors are raised with descriptive messages.

## Performance

- **Small reports** (< 100 rows): < 500ms
- **Medium reports** (100-1000 rows): < 2s
- **Large reports** (1000-10000 rows): < 10s
- **Memory usage**: Linear with row count (~1MB per 5000 rows)

## Integration Points

### Dependencies
- **pandas**: Data manipulation
- **openpyxl**: Excel export (optional, installed with skill)
- **jinja2**: HTML templates (future enhancement)

### Related Skills
- `payroll-processor`: Complements hours reports with payroll calculations
- `attendance-tracker`: Feeds attendance data to this skill
- `dispatch-manager`: Provides dispatch assignment data

## Database Schema

The skill automatically extends the base schema with:

```sql
-- New tables created by sql_schema_extensions.sql
attendance_records  -- Detailed daily attendance
hr_reports          -- Report metadata for auditing
```

See `sql_schema_extensions.sql` for complete schema definition.

## Testing

Full test coverage (80%+) with:
- **Unit tests**: Report generators, Excel builder, validators
- **Integration tests**: Database operations, full execution flow
- **Fixtures**: Sample data (3 employees, 5 attendance records, 4 dispatch assignments)

Run tests:
```bash
pytest tests/ -v --cov=scripts
```

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| `No data available` | Empty date range or no matching records | Verify database has records in period, check employee_id filter |
| `File not found` | Invalid output path | Ensure output directory exists |
| `openpyxl not found` | Excel export not installed | `pip install openpyxl` |
| `Invalid report_type` | Typo in report type | Use one of: roster, hours, dispatch, absence |
| `Database locked` | Another process is using it | Close other connections, retry |

## Changelog

### v1.0.0 (2024-03-01)
- Initial release
- 4 report types (roster, hours, dispatch, absence)
- Excel, HTML, CSV export
- Database persistence
- Full test coverage

## Author

Antigravity Team  
UNS / Japan

## License

Proprietary - Part of Antigravity Ecosystem
