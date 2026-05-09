# Consolidation Map — Data Engineering Skills Group

## Primary Skill

This is the **Data Engineering — Complete Stack** specialist skill.

**Name:** `data-engineer`
**Focus:** Complete modern data stack (Spark, dbt, Airflow, cloud platforms)
**Best for:** Enterprise data architecture, full pipeline design, cloud data warehousing

---

## Related Skills in This Group

### 1. `data-engineering` — Data Engineering Patterns & Tools

**Relationship:** **Complementary — Specific patterns and tools**

- **Overlap:** Both cover data pipelines, ETL/ELT, dbt, streaming, partitioning, orchestration
- **Difference:**
  - `data-engineer`: **Complete expert** (Spark, Airflow, cloud platforms, real-time, data quality, governance)
  - `data-engineering`: **Pattern guide** with markdown docs (etl-vs-elt.md, dbt-patterns.md, data-quality.md, streaming.md, partitioning.md, orchestration.md, cost-optimization.md, data-modeling.md)
- **When to use each:**
  - Use `data-engineer` for **AI/agent-driven** design and recommendations
  - Use `data-engineering` for **reference documentation** and pattern lookup
- **Combined workflow:**
  1. Consult `data-engineering` for pattern reference (quick lookup)
  2. Use `data-engineer` for **implementation guidance** and architecture decisions
  3. Example: "Is my partition strategy correct?" → `data-engineering` (reference) vs. "Design optimal partitioning for 10TB dataset" → `data-engineer` (agent)

---

### 2. `data-engineering-data-driven-feature` — Feature Engineering & Development

**Relationship:** **Specialized — ML-specific data engineering**

- **Overlap:** Both touch data pipelines
- **Difference:**
  - `data-engineer`: **Infrastructure-focused** (warehouses, lakes, orchestration, governance)
  - `data-engineering-data-driven-feature`: **ML-focused** (feature engineering, feature stores, ML pipeline integration)
- **When to use each:**
  - Use `data-engineer` for **data warehouse/lake architecture**
  - Use `data-engineering-data-driven-feature` for **feature engineering and ML pipelines**
- **Combined workflow:**
  1. Use `data-engineer` to build the **data pipeline** (ingestion, transformation, warehouse)
  2. Use `data-engineering-data-driven-feature` to build the **feature store** and ML-specific transforms

---

### 3. `data-engineering-data-pipeline` — Data Pipeline Implementation

**Relationship:** **Specialized — Execution-focused**

- **Overlap:** Both cover pipeline implementation
- **Difference:**
  - `data-engineer`: **Design and architecture** at enterprise scale
  - `data-engineering-data-pipeline`: **Hands-on implementation** of specific pipeline patterns
- **When to use each:**
  - Use `data-engineer` for **architecture decisions**
  - Use `data-engineering-data-pipeline` for **step-by-step pipeline coding**
- **Combined workflow:**
  1. Use `data-engineer` to design pipeline (Spark vs dbt, Airflow vs Dagster)
  2. Use `data-engineering-data-pipeline` to implement the chosen pattern

---

## Decision Matrix

| Scenario | Primary Skill | Secondary Skills |
|----------|---------------|------------------|
| **Design modern data stack** | `data-engineer` | `data-engineering` (reference) |
| **Quick pattern lookup** | `data-engineering` | — |
| **Build data warehouse** | `data-engineer` | `data-engineering` (dbt patterns) |
| **Implement specific pipeline** | `data-engineering-data-pipeline` | `data-engineer` (architecture) |
| **Feature engineering for ML** | `data-engineering-data-driven-feature` | `data-engineer` (infrastructure) |
| **Optimize costs** | `data-engineer` | `data-engineering` (cost-optimization.md) |
| **Design real-time streaming** | `data-engineer` | `data-engineering` (streaming.md) |
| **Orchestrate complex DAGs** | `data-engineer` | `data-engineering` (orchestration.md) |

---

## Why They're Separate (Not Merged)

1. **Different audiences:** Agents vs. developers vs. ML engineers
2. **Different formats:** Expert guidance vs. markdown reference vs. code patterns
3. **Different depth:** Enterprise architecture vs. pattern reference vs. implementation
4. **Reusability:** Can be invoked independently in different contexts
5. **Maintenance:** Easier to update patterns in one place (data-engineering) while data-engineer stays architecture-focused

---

## Recommended Usage Pattern

```python
# In orchestration or skill composition:

# Step 1: Architecture decision
await run_skill("data-engineer", {
    "task": "Design modern data stack for real-time analytics",
    "volume": "10TB+ daily",
    "requirements": ["streaming", "ml-features", "governance"]
})
# → Recommends Kafka + dbt + Snowflake + feature store

# Step 2: Reference implementation patterns
pattern = await run_skill("data-engineering", {
    "task": "Show dbt patterns for dimensional modeling"
})
# → Returns dbt-patterns.md content

# Step 3: Build specific pipeline
await run_skill("data-engineering-data-pipeline", {
    "pattern": "spark-to-snowflake",
    "source": "kafka-topic",
    "transformations": [...]
})
# → Hands-on implementation

# Result: Complete data pipeline with strong architecture foundation
```

---

## Related Skills Outside This Group

- **`business-intelligence`** — Analytics and BI tools (Tableau, Looker)
- **`database-architect`** — Database design and optimization
- **`devops-advanced`** — Infrastructure and cloud platforms
- **`architecture-patterns`** — General system design patterns
- **`ml-engineer`** — ML-specific data pipelines and feature stores

---

## Cross-References

- **Data source:** `.agent/skills/data-engineer/SKILL.md`
- **Related group:** `data-engineering`, `data-engineering-data-driven-feature`, `data-engineering-data-pipeline`
- **Organization doc:** `.context/SKILLS_ORGANIZATION.md` (master index)
