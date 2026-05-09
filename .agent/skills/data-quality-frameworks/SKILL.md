---
name: data-quality-frameworks
description: Implement data quality validation with Great Expectations, dbt tests, and data contracts. Production patterns for ensuring reliable data pipelines with automated validation, monitoring, and alerting.
type: feature
category: data-ml
version: 2.1.0
tags:
---
  - data-quality
  - great-expectations
  - dbt
  - data-contracts
  - data-governance
  - testing
requires:
  python_modules:
    - great_expectations
    - pydantic
    - pandas
  optional:
    - dbt-core
    - sqlalchemy
triggers:
  - "data quality|validation|expectations"
  - "dbt test|testing strategy"
  - "data contract|governance"
---

# Data Quality Frameworks

Production patterns for implementing data quality with Great Expectations, dbt tests, and data contracts to ensure reliable data pipelines with zero tolerance for bad data.

## Use this skill when

- Implementing data quality checks in pipelines
- Setting up Great Expectations validation
- Building comprehensive dbt test suites
- Establishing data contracts between teams
- Monitoring data quality metrics in production
- Automating data validation in CI/CD
- Defining SLA/SLO for data freshness and completeness
- Building data quality dashboards
- Implementing point-in-time validation

## Do not use this skill when

- The data sources are undefined or unavailable
- You cannot modify validation rules or schemas
- The task is unrelated to data quality or contracts
- Working with unstructured data (images, text blobs)

## Core Concepts

### 1. Data Quality Dimensions

```
Accuracy      → Data matches source of truth
Completeness  → All required fields are populated
Consistency   → Data aligns across systems
Timeliness    → Data is fresh and up-to-date
Uniqueness    → No unintended duplicates
Validity      → Data conforms to schema/format
```

### 2. Great Expectations Pattern

Great Expectations provides declarative validation with automatic documentation.

#### Basic Setup

```python
from great_expectations.dataset import PandasDataset
from great_expectations.core.expectation_suite import ExpectationSuite

# Create context (production: use store configuration)
import great_expectations as ge

context = ge.get_context()

# Load data as validatable dataset
validator = context.get_validator(
    batch_request={
        "datasource_name": "my_datasource",
        "data_connector_name": "default",
        "data_asset_name": "customer_table"
    }
)
```

#### Defining Expectations

```python
# Column expectations
validator.expect_column_values_to_not_be_null(column="customer_id")
validator.expect_column_values_to_be_in_set(
    column="status",
    value_set=["active", "inactive", "suspended"]
)
validator.expect_column_values_to_be_between(
    column="age",
    min_value=0,
    max_value=150
)

# Table-level expectations
validator.expect_table_row_count_to_be_between(
    min_value=1000,
    max_value=10000000
)
validator.expect_table_columns_to_match_ordered_list(
    column_list=["id", "name", "email", "created_at"]
)

# Save expectation suite
validator.save_expectation_suite()
```

#### Validation with Error Handling

```python
# Run validation
validation_result = validator.validate()

# Handle failures
if not validation_result.success:
    for result in validation_result.results:
        if not result.success:
            print(f"Failed: {result.expectation_config.expectation_type}")
            print(f"Reason: {result.result}")

    # Route to remediation
    notify_data_owner()
    trigger_remediation_pipeline()
else:
    print("All validations passed ✓")
```

### 3. dbt Test Patterns

dbt tests are SQL assertions that ensure data integrity.

#### Singular Tests (Custom SQL)

```sql
-- tests/singular/assert_customer_ids_unique.sql
SELECT customer_id, COUNT(*) as cnt
FROM {{ ref('customers') }}
GROUP BY customer_id
HAVING cnt > 1
```

#### Generic Tests (Reusable)

```yaml
# models/schema.yml
models:
  - name: customers
    columns:
      - name: customer_id
        tests:
          - unique
          - not_null
          - relationships:
              to: ref('accounts')
              field: customer_id

      - name: email
        tests:
          - unique
          - not_null
          - regex:
              pattern: "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"

      - name: created_at
        tests:
          - not_null
          - dbt_utils.expression_is_true:
              expression: "created_at <= current_date"
```

#### Custom Generic Test

```sql
-- tests/generic/is_valid_iso_date.sql
{% test is_valid_iso_date(model, column) %}

SELECT *
FROM {{ model }}
WHERE {{ column }} IS NOT NULL
  AND {{ column }} NOT SIMILAR TO '^\d{4}-\d{2}-\d{2}$'

{% endtest %}
```

### 4. Data Contracts Pattern

Data contracts are agreements between producers and consumers.

```yaml
# data_contracts/customer_events.contract.yaml
contract:
  name: customer_events
  version: "2.1.0"
  producer: analytics_platform
  consumer: ["ml_team", "bi_team"]

  schema:
    event_id:
      type: string
      not_null: true
      unique: true
    customer_id:
      type: string
      not_null: true
    event_type:
      type: string
      enum: ["login", "purchase", "logout", "error"]
    event_timestamp:
      type: timestamp
      not_null: true
      constraint: "event_timestamp <= now()"
    properties:
      type: json
      schema:
        session_id: string
        duration_ms: integer

  sla:
    freshness: 15m        # Max lag from event to table
    completeness: 99.9%   # Min rows expected
    latency_p99: 5m       # 99th percentile latency

  owner: data_platform_team
  runbook: "https://wiki.company.com/customer_events_runbook"
```

### 5. Validation Pipeline Architecture

```python
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

class ValidationStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    WARNED = "warned"

@dataclass
class ValidationReport:
    dataset_name: str
    validation_status: ValidationStatus
    timestamp: datetime
    checks_run: int
    checks_passed: int
    checks_failed: int
    failure_details: list[dict]
    remediation_status: str | None = None

class DataQualityPipeline:
    """Production-ready quality validation pipeline."""

    def __init__(self, context):
        self.context = context
        self.metrics = {}

    def validate_dataset(self, dataset_name: str) -> ValidationReport:
        """Run full validation suite on dataset."""
        validator = self.context.get_validator(
            batch_request=self._build_batch_request(dataset_name)
        )

        result = validator.validate()

        failed = [r for r in result.results if not r.success]

        report = ValidationReport(
            dataset_name=dataset_name,
            validation_status=(
                ValidationStatus.FAILED if failed else ValidationStatus.PASSED
            ),
            timestamp=datetime.utcnow(),
            checks_run=len(result.results),
            checks_passed=len(result.results) - len(failed),
            checks_failed=len(failed),
            failure_details=[self._format_failure(f) for f in failed]
        )

        # Route to remediation if failures
        if failed:
            report.remediation_status = self._trigger_remediation(report)

        return report

    def _trigger_remediation(self, report: ValidationReport) -> str:
        """Trigger data remediation workflow."""
        # Options: quarantine, replay, skip, notify_owner
        if report.checks_failed > 5:
            return "quarantine"  # Stop pipeline
        elif report.checks_failed > 0:
            return "notify_owner"  # Alert team
        return "proceed"

    def publish_metrics(self, report: ValidationReport) -> None:
        """Publish to monitoring/observability."""
        self.metrics[report.dataset_name] = {
            "last_validation": report.timestamp.isoformat(),
            "pass_rate": report.checks_passed / report.checks_run,
            "failures": report.checks_failed,
            "remediation": report.remediation_status
        }
        # Send to Prometheus, CloudWatch, etc.
```

## Implementation Checklist

- [ ] **Assess**: Identify critical datasets and quality dimensions
- [ ] **Define**: Create expectations/tests and contract rules
- [ ] **Automate**: Wire validation into CI/CD and data pipeline
- [ ] **Monitor**: Set up dashboards and alerting
- [ ] **Iterate**: Refine expectations based on production failures

## Safety & Best Practices

- **Prevent cascade failures**: Use quarantine + notification instead of blocking
- **Test validation logic**: GE expectations should be version-controlled and tested
- **Secure sensitive data**: Mask PII in validation error messages
- **Document ownership**: Clearly assign data owner and remediation procedures
- **Start conservative**: Begin with critical tables; expand coverage incrementally

## Monitoring & Alerting

```yaml
# Prometheus alerts
groups:
  - name: data_quality
    rules:
      - alert: DataQualityCheckFailed
        expr: data_quality_checks_failed > 0
        for: 5m
        annotations:
          summary: "Data quality check failed for {{ $labels.dataset }}"

      - alert: DataQualityFreshnessBreached
        expr: |
          (time() - last_update_timestamp) > 900  # 15m SLA
        annotations:
          summary: "Data freshness SLA breached for {{ $labels.dataset }}"
```

## Resources

- **Detailed patterns & templates**: See `resources/implementation-playbook.md`
- **Great Expectations docs**: https://docs.greatexpectations.io/
- **dbt testing**: https://docs.getdbt.com/docs/building-a-dbt-project/tests
- **Data contracts specification**: https://datacontract.dev/
