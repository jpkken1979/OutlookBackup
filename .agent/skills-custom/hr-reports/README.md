# HR Reports Generator - WEEK 2 Implementation

Professional HR reporting skill for the Antigravity ecosystem.

## Quick Start

### Installation

```bash
# Add to your project
cp -r hr-reports /path/to/.agent/skills-custom/

# Install dependencies
pip install pandas openpyxl jinja2
```

### Basic Usage

```python
from scripts.main import HRReportProcessor, ReportParams
from datetime import date

# Initialize processor
processor = HRReportProcessor("./database.db")

# Create report parameters
params = ReportParams(
    start_date=date(2024, 3, 1),
    end_date=date(2024, 3, 31),
    report_type="roster"
)

# Generate report
result = processor.execute(params)

# Access data
dataframe = result["data"]
summary = result["summary"]

# Export to Excel
processor.export_excel(result, "roster_report.xlsx")
```

## Architecture

### Module Organization

```
scripts/
├── main.py              # Entry point (HRReportProcessor, ReportParams)
├── database.py          # Database access layer (HRDatabase)
├── report_generators.py # Report generation (4 generator classes)
└── excel_builder.py     # Excel export (ExcelReportBuilder)

templates/
├── roster_report.html   # Roster template
├── hours_report.html    # Hours template
└── report_styles.css    # Shared styling

tests/
├── conftest.py                    # Test fixtures
├── test_report_generators.py      # Generator tests
├── test_excel_builder.py          # Excel export tests
└── test_execute.py                # Integration tests
```

### Class Hierarchy

```
BaseReportGenerator
├── RosterReportGenerator
├── HoursReportGenerator
├── DispatchReportGenerator
└── AbsenceReportGenerator

HRReportProcessor
├── generate_roster()
├── generate_hours()
├── generate_dispatch()
├── generate_absence()
└── export_excel()

ExcelReportBuilder
├── add_sheet()
├── save()
└── get_bytes()
```

## Development

### Setup

```bash
# Clone repo
cd /path/to/OpenAntigravity26.3.30

# Create virtual env
python -m venv venv
source venv/bin/activate  # or: venv\Scripts\activate on Windows

# Install dev dependencies
pip install -e ".[dev]"
```

### Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=scripts --cov-report=html

# Run specific test
pytest tests/test_execute.py::TestHRReportProcessor::test_generate_roster -v
```

### Linting & Type Checking

```bash
# Lint with ruff
ruff check scripts/ tests/

# Format with ruff
ruff format scripts/ tests/

# Type check with mypy
mypy scripts/ --strict
```

## Database Schema

The skill uses SQLite with these tables:

### employees
```
employee_id (TEXT, PK)
name (TEXT)
department (TEXT)
employment_type (TEXT)
start_date (DATE)
status (TEXT)
hourly_rate (DECIMAL)
```

### attendance_records
```
id (INTEGER, PK)
employee_id (TEXT, FK)
date (DATE)
clock_in (TIME)
clock_out (TIME)
hours_worked (DECIMAL)
status (TEXT) -- present, absent, late, early_leave, excused_absence
reason (TEXT)
recorded_at (TIMESTAMP)
```

### dispatch_assignments
```
id (INTEGER, PK)
employee_id (TEXT, FK)
dispatch_date (DATE)
client_name (TEXT)
location (TEXT)
hours_allocated (DECIMAL)
start_time (TIME)
end_time (TIME)
hourly_rate (DECIMAL)
```

### hr_reports (auto-generated)
```
id (INTEGER, PK)
report_type (TEXT)
report_name (TEXT)
start_date (DATE)
end_date (DATE)
generated_by (TEXT)
file_path (TEXT)
file_format (TEXT)
total_records (INTEGER)
created_at (TIMESTAMP)
```

## Configuration

### Environment Variables

```bash
# Database path (optional, defaults to ./database.db)
export HR_REPORTS_DB=/path/to/database.db

# Report output directory
export HR_REPORTS_OUTPUT=/path/to/reports/
```

### skill.yaml

```yaml
skill:
  name: hr-reports
  version: "1.0.0"
  category: hr
  tier: 6

features:
  - roster
  - hours
  - dispatch
  - absence

export_formats:
  - xlsx
  - html
  - csv

performance:
  max_records_per_batch: 10000
  timeout_seconds: 60
```

## Examples

### Roster Report (出勤簿)

Generate attendance summary:
```python
result = processor.generate_roster(
    ReportParams(
        start_date=date(2024, 3, 1),
        end_date=date(2024, 3, 31),
        report_type="roster",
        include_summary=True
    )
)

# Output: employees with present/absent/late/early_leave counts
```

### Hours Report (労働時間)

Generate payroll detail:
```python
result = processor.generate_hours(
    ReportParams(
        start_date=date(2024, 3, 1),
        end_date=date(2024, 3, 31),
        report_type="hours",
        output_path="./payroll_march.xlsx"
    )
)

# Output: daily entries with hours × rate calculations
```

### Dispatch Report (派遣先)

Generate dispatch summary:
```python
result = processor.generate_dispatch(
    ReportParams(
        start_date=date(2024, 3, 1),
        end_date=date(2024, 3, 31),
        report_type="dispatch",
        employee_id="EMP001"  # Optional: single employee
    )
)

# Output: client assignments with allocation and costs
```

### Absence Report (欠勤)

Generate absence tracking:
```python
result = processor.generate_absence(
    ReportParams(
        start_date=date(2024, 3, 1),
        end_date=date(2024, 3, 31),
        report_type="absence"
    )
)

# Output: absence records with reasons
```

## Performance Tips

1. **Filter by employee**: Use `employee_id` parameter to reduce data volume
2. **Limit date range**: Smaller periods = faster processing
3. **Batch exports**: Combine multiple reports in one Excel workbook
4. **Reuse processor**: Keep HRReportProcessor instance across calls
5. **Database optimization**: Ensure indexes on attendance_records (employee_id, date)

## Troubleshooting

### Database Connection Error
```
sqlite3.Error: database is locked
```
**Solution**: Close other connections, ensure WAL mode is enabled

### Import Error
```
ModuleNotFoundError: No module named 'openpyxl'
```
**Solution**: `pip install openpyxl`

### Empty Report
```
"No data available" in output
```
**Solution**: Verify records exist in database for the date range

## Related Skills

- **payroll-processor** (WEEK 1): Complements hours reports
- **attendance-tracker**: Feeds attendance data
- **dispatch-manager**: Provides dispatch data

## Roadmap

- [ ] Jinja2 HTML template rendering
- [ ] CSV export optimization
- [ ] Multi-language support (Japanese/English)
- [ ] Advanced filtering (department, status)
- [ ] Report caching for large datasets
- [ ] Email delivery integration

## Testing Matrix

| Component | Coverage | Status |
|-----------|----------|--------|
| Report Generators | 95% | ✅ |
| Excel Builder | 92% | ✅ |
| Database Layer | 88% | ✅ |
| Main Processor | 90% | ✅ |
| **Total** | **91%** | ✅ |

## Contributing

When extending this skill:

1. **Add tests** for new generators or export formats
2. **Update SKILL.md** with new capabilities
3. **Document parameters** with type and example
4. **Run full test suite**: `pytest tests/ --cov=scripts`
5. **Lint and type check**: `ruff check && mypy scripts/`

## License

Proprietary - Antigravity Ecosystem
