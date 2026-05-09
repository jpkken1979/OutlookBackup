---
name: data-engineering
description: Data engineering patterns and tools. ETL/ELT pipelines, dbt transformations, data quality, streaming, partitioning, orchestration.
type: feature
category: data
tags: [data-engineering, etl, dbt, pipelines, streaming, data-quality, orchestration]
version: 1.0.0
---

# Data Engineering

> Build scalable, reliable data pipelines.
> **Data quality first, quantity second.**

---

## 📑 Content Map

| File | Description | When to Read |
|------|-------------|--------------|
| `etl-vs-elt.md` | ETL vs ELT comparison, when to use | Pipeline architecture |
| `dbt-patterns.md` | dbt models, testing, documentation | SQL transformations |
| `data-quality.md` | Validation rules, quality checks, monitoring | Ensuring reliability |
| `streaming.md` | Event streaming, Kafka, pub/sub | Real-time data |
| `partitioning.md` | Partition strategies, bucketing | Query optimization |
| `orchestration.md` | DAG scheduling, error handling, monitoring | Workflow management |
| `cost-optimization.md` | Compression, tiering, caching | Reducing cloud spend |
| `data-modeling.md` | Dimensional models, slowly changing dimensions | Analytics schemas |

---

## 🔗 Related Skills

| Need | Skill |
|------|-------|
| Database design | `@[skills/database-design]` |
| Cloud infrastructure | `@[skills/devops-advanced]` |
| Analytics | `@[skills/business-intelligence]` |
| Architecture patterns | `@[skills/architecture-patterns]` |

---

## ✅ Data Pipeline Checklist

Before deploying to production:

- [ ] **Data source schema understood?**
- [ ] **Transformation logic tested?** (with sample data)
- [ ] **Data quality rules defined?**
- [ ] **Monitoring/alerting configured?**
- [ ] **Error handling implemented?** (retry, dead-letter)
- [ ] **Partitioning strategy chosen?**
- [ ] **Retention policy defined?**
- [ ] **Incremental/delta handling?** (avoid full reprocessing)
- [ ] **Cost estimated?** (storage, compute)
- [ ] **Disaster recovery plan?**
- [ ] **Data lineage documented?**

---

## ETL vs ELT Decision Tree

```
┌─ Is data clean/well-understood?
│  └─ YES → ELT (transform in warehouse)
│  └─ NO  → ETL (transform in pipeline)
│
├─ Need real-time transformations?
│  └─ YES → ELT + streaming
│  └─ NO  → ELT (batch) or ETL
│
└─ Data volume > 1TB?
   └─ YES → ELT (scale horizontally)
   └─ NO  → ETL is simpler
```

---

## dbt Project Structure

```
my_dbt_project/
├── dbt_project.yml          # Project config
├── models/
│   ├── staging/             # Raw data, minimal transformation
│   │   ├── stg_customers.sql
│   │   └── stg_orders.sql
│   ├── intermediate/        # Cross-domain logic
│   │   └── int_customer_orders.sql
│   └── marts/               # Final business logic
│       ├── dim_customers.sql
│       └── fct_orders.sql
├── tests/                   # dbt test definitions
├── macros/                  # Reusable SQL functions
├── seeds/                   # Static reference data
└── analyses/                # Ad-hoc analysis queries
```

---

## Data Quality Framework

### Validation Rules

```python
# Examples of quality checks
rules = {
    "completeness": "0% NULL values in critical columns",
    "uniqueness": "No duplicate customer IDs",
    "validity": "Email format matches regex",
    "consistency": "order_date <= shipping_date",
    "accuracy": "Total invoice amount = sum(line_items)",
    "timeliness": "Data loaded within 1 hour of source"
}
```

### Monitoring Strategy

| Metric | Alert Threshold | Action |
|--------|-----------------|--------|
| Null count | > 5% | Page on-call, rollback |
| Freshness | > 2 hours | Investigate source |
| Row count change | ±50% | Manual review |
| Data drift | Anomaly detected | Alert but don't fail |

---

## Streaming Architecture

### Pub/Sub Pattern
```
Source → Publisher → Message Queue → Subscriber → Sink
         (Kafka/Kinesis)         (Consumer)
```

### Event Schema
```json
{
  "event_id": "uuid",
  "event_type": "order.created",
  "timestamp": "2024-03-06T15:00:00Z",
  "source": "ecommerce-api",
  "data": {...},
  "version": "1.0"
}
```

---

## Partitioning Strategies

### Time-based Partitioning
**Best for:** Time-series data, logs, events
```sql
PARTITION BY date(created_at)
-- Storage: /data/year=2024/month=03/day=06/
```

### Hash Partitioning
**Best for:** Even distribution, no obvious partition key
```sql
PARTITION BY HASH(customer_id) INTO 8 BUCKETS
```

### Range Partitioning
**Best for:** Numeric ranges, IDs
```sql
PARTITION BY RANGE(price) (
  PARTITION p0 VALUES LESS THAN (100),
  PARTITION p1 VALUES LESS THAN (500),
  PARTITION p2 VALUES LESS THAN (MAXVALUE)
)
```

---

## Orchestration Tools

| Tool | Best For | Language |
|------|----------|----------|
| **Airflow** | Complex DAGs, dynamic workflows | Python |
| **dbt Cloud** | Scheduled dbt runs, monitoring | YAML |
| **Dagster** | Asset-oriented pipelines | Python |
| **Prefect** | Modern workflow engine | Python |
| **Step Functions** | AWS-native, serverless | JSON |

---

## ❌ Anti-Patterns

**DON'T:**
- Skip data quality testing
- Reprocess all data every run
- Store raw data without schema validation
- Miss partition keys (causes query scans)
- Ignore data lineage
- Make transformations non-idempotent
- Use hardcoded credentials
- Assume data won't change

**DO:**
- Partition by query pattern
- Use incremental models in dbt
- Version your dbt project
- Test data, not just code
- Monitor pipeline health
- Document transformations
- Use materialized views for aggregates
- Track data SLAs

---

## Cost Optimization

### Storage Tier Strategy
```
Hot (0-30 days)     → Standard tier, immediate access
Warm (30-90 days)   → Infrequent access tier
Cold (90+ days)     → Archive tier, retrieval fee OK
Frozen (1+ year)    → Cold storage or delete
```

### Compression Techniques
```
CSV/JSON            → Snappy (fast) or gzip (small)
Parquet             → Column-specific compression
Columnar databases  → LZ4 or zstd
Time-series data    → Delta encoding
```

---

## Script

| Script | Purpose | Command |
|--------|---------|---------|
| `scripts/dbt_analyzer.py` | Analyze dbt project for issues | `python scripts/dbt_analyzer.py --project <path>` |
| `scripts/data_quality_monitor.py` | Monitor data quality metrics | `python scripts/data_quality_monitor.py --config config.yaml` |
| `scripts/etl_cost_estimator.py` | Estimate pipeline costs | `python scripts/etl_cost_estimator.py --rows 1000000` |

## Related Skills

This skill is part of the **Data Engineering** group. See `.context/SKILLS_ORGANIZATION.md` for the complete group map.

| Skill | Relationship | When to Use |
|-------|---|---|
| `data-engineer` | Expert designer | Architecture decisions and design guidance (uses this skill for reference) |
| `data-engineering-data-pipeline` | Specialized implementation | Hands-on pipeline implementation |
| `data-engineering-data-driven-feature` | Specialized ML focus | Feature engineering and ML pipelines |

**Read more:** `.agent/skills/data-engineer/CONSOLIDATION_MAP.md` for decision matrix and combined workflows.
