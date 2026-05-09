---
name: database-migration-validator
description: "Validate database migration scripts for safety and correctness before execution"
version: 1.1.0
tags: [database, migration, validation, safety]
author: Example Organization
---

# Database Migration Validator

Validate database migration scripts for safety, correctness, and compliance before execution.

[Extended thinking: Database migrations are high-risk operations that can cause data loss, downtime, or performance issues if not properly validated. This skill combines automated checks with expert review criteria to catch issues before production deployment.]

## Use this skill when

- Creating new database migration scripts
- Reviewing migrations before deployment
- Auditing migration safety in CI/CD pipelines
- Training team on migration best practices

## Do not use this skill when

- Writing initial database schema (use database-design-patterns)
- Debugging failed migrations (use database-troubleshooting)
- Rolling back migrations (use database-rollback-procedures)

## Instructions

### Phase 1: Static Analysis

Run automated validation script:

```bash
python scripts/validate_migration.py path/to/migration.sql
```

This checks for:
- Destructive operations without safeguards
- Missing rollback procedures
- Performance anti-patterns
- Syntax errors and typos

### Phase 2: Manual Review

Review migration against checklist:

1. **Safety Checks**
   - [ ] No DROP TABLE without IF EXISTS
   - [ ] No DROP COLUMN without backup strategy
   - [ ] No TRUNCATE on production tables
   - [ ] All data transformations are reversible

2. **Performance Checks**
   - [ ] Large table alterations use batching
   - [ ] Indexes added CONCURRENTLY (PostgreSQL)
   - [ ] No blocking operations during business hours
   - [ ] Estimated execution time documented

3. **Correctness Checks**
   - [ ] Foreign key constraints validated
   - [ ] Data types appropriate for domain
   - [ ] Default values sensible
   - [ ] Migration is idempotent

4. **Rollback Readiness**
   - [ ] Reverse migration provided
   - [ ] Rollback tested in staging
   - [ ] Rollback time estimated
   - [ ] Data recovery plan documented

### Phase 3: Execution Planning

Document execution strategy:

```yaml
migration: add_user_preferences_table
estimated_duration: 2 minutes
locks_required: none
blocking_operations: none
rollback_duration: 1 minute
deployment_window: any
requires_downtime: false
```

### Phase 4: Approval

Required approvals:
- Tech lead: Architecture review
- DBA: Performance and safety review
- DevOps: Deployment strategy review

## Safety

**CRITICAL**: Never execute destructive migrations without:
1. Complete database backup
2. Tested rollback procedure
3. Approval from tech lead and DBA
4. Scheduled maintenance window (for risky operations)

## Examples

### Example 1: Safe Column Addition

**Migration**:
```sql
-- Add email_verified column with safe defaults
ALTER TABLE users
  ADD COLUMN IF NOT EXISTS email_verified BOOLEAN DEFAULT false NOT NULL;

-- Backfill based on existing data
UPDATE users
  SET email_verified = true
  WHERE email_confirmed_at IS NOT NULL;
```

**Validation Result**: ✅ PASS
- Uses IF NOT EXISTS
- Safe default value
- Backfill logic clear
- No performance issues (small table)

### Example 2: Risky Column Removal (Requires Safeguards)

**Migration** (BEFORE validation):
```sql
-- Remove deprecated legacy_id column
ALTER TABLE orders DROP COLUMN legacy_id;
```

**Validation Result**: ❌ FAIL
- No IF EXISTS check
- No backup strategy documented
- Irreversible data loss

**Migration** (AFTER fixes):
```sql
-- Step 1: Backup data to archive table
CREATE TABLE IF NOT EXISTS orders_legacy_id_archive AS
  SELECT order_id, legacy_id, archived_at
  FROM orders
  WHERE legacy_id IS NOT NULL;

-- Step 2: Verify backup
DO $$
BEGIN
  IF (SELECT COUNT(*) FROM orders WHERE legacy_id IS NOT NULL) !=
     (SELECT COUNT(*) FROM orders_legacy_id_archive)
  THEN
    RAISE EXCEPTION 'Backup verification failed';
  END IF;
END $$;

-- Step 3: Remove column
ALTER TABLE orders DROP COLUMN IF EXISTS legacy_id;
```

**Validation Result**: ✅ PASS
- Data backed up to archive
- Verification step included
- IF EXISTS added
- Rollback possible from archive

### Example 3: Performance-Optimized Index Creation

**Migration**:
```sql
-- Create index on large table without blocking writes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_orders_user_id_created_at
  ON orders (user_id, created_at DESC);

-- Verify index creation
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE indexname = 'idx_orders_user_id_created_at'
  ) THEN
    RAISE EXCEPTION 'Index creation failed';
  END IF;
END $$;
```

**Validation Result**: ✅ PASS
- Uses CONCURRENTLY (no table lock)
- IF NOT EXISTS prevents errors
- Verification step included
- Safe for production deployment

## Validation Script Usage

### Basic Validation

```bash
# Validate single migration
python scripts/validate_migration.py migrations/001_add_users_table.sql

# Output:
# ✅ Syntax check: PASS
# ✅ Safety check: PASS
# ✅ Performance check: PASS
# ⚠️  Warning: Missing rollback migration
#
# Overall: PASS (1 warning)
```

### CI/CD Integration

```yaml
# .github/workflows/validate-migrations.yml
name: Validate Migrations

on:
  pull_request:
    paths:
      - 'migrations/**'

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Validate migrations
        run: |
          python scripts/validate_migration.py migrations/*.sql
          if [ $? -ne 0 ]; then
            echo "❌ Migration validation failed"
            exit 1
          fi
```

### Batch Validation

```bash
# Validate all pending migrations
python scripts/validate_migration.py --batch migrations/pending/*.sql

# Generate validation report
python scripts/validate_migration.py --report migrations/*.sql > validation_report.md
```

## Troubleshooting

**Problem**: Script reports "Destructive operation detected"
- **Cause**: Migration contains DROP, TRUNCATE, or DELETE without safeguards
- **Solution**: Add IF EXISTS, backup strategy, or data verification
- **Prevention**: Always use validation script before committing

**Problem**: "Performance warning: Full table lock"
- **Cause**: Operation blocks reads/writes on large table
- **Solution**: Use CONCURRENTLY, batch operations, or schedule maintenance window
- **Prevention**: Test migrations on production-sized data in staging

**Problem**: "Rollback migration missing"
- **Cause**: No reverse migration provided
- **Solution**: Create rollback script with same filename + `.rollback.sql`
- **Prevention**: Write rollback before forward migration

## Validation Checklist

Before approving migration:

- [ ] Automated validation script passes
- [ ] Manual review checklist complete
- [ ] Rollback migration exists and tested
- [ ] Execution plan documented
- [ ] Performance impact estimated
- [ ] Approvals obtained
- [ ] Backup strategy confirmed
- [ ] Monitoring plan in place

## Success Metrics

- **Validation coverage**: >95% of migrations validated before deployment
- **Incident reduction**: Zero migration-related outages
- **Review time**: <30 minutes per migration
- **False positives**: <5% of warnings

## Dependencies

### Required Tools
- `scripts/validate_migration.py`: Automated validation script
- Database client (psql, mysql, etc.)

### Optional Tools
- `scripts/generate_rollback.py`: Auto-generate rollback migrations
- `scripts/estimate_migration_time.py`: Performance estimation

## Related Skills

- `database-design-patterns`: Creating optimal schemas
- `database-rollback-procedures`: Reverting failed migrations
- `database-performance-tuning`: Optimizing slow migrations
