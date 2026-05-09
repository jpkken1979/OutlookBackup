---
name: sql-optimization-patterns
description: Master SQL query optimization, indexing strategies, and EXPLAIN analysis. Eliminate slow queries, optimize schemas, reduce latency. Use when debugging slow queries, designing schemas, or optimizing application performance.
type: feature
category: performance
version: 2.1.0
tags:
---
  - sql
  - performance
  - indexing
  - query-optimization
  - explain-analysis
  - database
requires:
  tools:
    - postgresql
    - mysql
    - sqlite3
  optional:
    - pgbench
    - explain_analyze
triggers:
  - "slow query|query optimization|performance"
  - "index|indexing strategy|query plan"
  - "EXPLAIN|database latency"

# SQL Optimization Patterns

Master systematic SQL query optimization through proper indexing, query analysis, and schema design. Transform slow queries into lightning-fast operations.

## Use this skill when

- Debugging slow-running queries (>1s response time)
- Designing performant database schemas and migrations
- Optimizing application response times
- Reducing database load and cloud costs
- Improving scalability for growing datasets
- Analyzing EXPLAIN/EXPLAIN ANALYZE query plans
- Implementing efficient and selective indexes
- Resolving N+1 query problems
- Tuning database configuration for workload
- Profiling query performance in production

## Do not use this skill when

- The task is unrelated to SQL optimization
- Database is managed by vendor (no access to optimization)
- Query performance is not a bottleneck

## Core Performance Metrics

```
Response Time (ms)     → User-facing latency
Throughput (ops/sec)   → Queries per second
CPU Usage (%)          → Server load
Memory (MB)            → Working set size
I/O Operations (IOPS)  → Disk I/O rate
```

## EXPLAIN Analysis Framework

### PostgreSQL EXPLAIN (Analyzing Query Plans)

```sql
-- Basic EXPLAIN (shows plan without executing)
EXPLAIN SELECT * FROM users WHERE age > 30;

-- EXPLAIN ANALYZE (shows actual vs estimated costs)
EXPLAIN ANALYZE SELECT * FROM users WHERE age > 30;

-- Full output with planning time
EXPLAIN (ANALYZE, BUFFERS, TIMING, VERBOSE)
SELECT * FROM orders WHERE user_id = 123 AND status = 'pending';
```

**Key metrics to understand:**

```
Seq Scan    → Full table scan (slow for large tables)
Index Scan  → Uses index (fast for selective queries)
Hash Join   → Hash table join (good for large tables)
Nested Loop → Loop join (good for small outer table)
Bitmap Scan → Multi-index access (PostgreSQL optimization)

Cost model: (startup_cost, total_cost)
Rows: Estimated vs Actual (discrepancies indicate stale statistics)
```

### MySQL EXPLAIN Output

```sql
-- Basic EXPLAIN
EXPLAIN SELECT * FROM users WHERE id = 123;

-- JSON format (more detailed)
EXPLAIN FORMAT=JSON SELECT * FROM orders
WHERE user_id = 123 AND created_at > '2024-01-01';

-- Key columns:
-- type: ALL (bad) → index (good) → const (best)
-- key: NULL (no index) → index_name (good)
-- rows: Estimated rows examined
-- Extra: "Using where" (filter after read), "Using index" (index-only scan)
```

## Indexing Strategy Patterns

### 1. Single Column Index (Most Common)

```sql
-- Usage: Filter on one column frequently
CREATE INDEX idx_users_email ON users(email);

-- When to use: WHERE email = 'x@y.com'
-- When NOT to use: Low selectivity (< 5% of rows)

-- Example: Who has the email 'john@example.com'?
EXPLAIN ANALYZE SELECT * FROM users WHERE email = 'john@example.com';
-- Should show: Index Scan on idx_users_email
```

### 2. Composite Index (Multi-column)

```sql
-- Order matters: most selective first
CREATE INDEX idx_orders_user_status ON orders(user_id, status);

-- Good for: WHERE user_id = ? AND status = ?
SELECT * FROM orders WHERE user_id = 123 AND status = 'pending';

-- Leftmost prefix rule: Can also use for: WHERE user_id = ?
-- But NOT for: WHERE status = ? (skips first column)

-- Avoid over-indexing: Each index slows down writes (INSERT, UPDATE, DELETE)
```

### 3. Partial Index (Filtered Index)

```sql
-- Index only relevant rows
CREATE INDEX idx_active_users ON users(id) WHERE is_active = true;

-- Saves space and makes index faster
-- Use when: Filtering on status/flag frequently

-- Example: Find active user by email
SELECT * FROM users WHERE email = 'x@y.com' AND is_active = true;
```

### 4. Covering Index (Index-Only Scan)

```sql
-- Include all columns needed in query (avoid table lookup)
CREATE INDEX idx_orders_user_amount ON orders(user_id, amount, created_at);

-- Query that can be satisfied by index alone
SELECT user_id, amount, created_at FROM orders WHERE user_id = 123;

-- PostgreSQL: "Index Only Scan"
-- MySQL: "Using index" in Extra column
-- Result: 10-100x faster (no table access)
```

## Query Optimization Patterns

### 1. N+1 Query Problem (Most Common Performance Bug)

**Bad (N+1 queries):**
```sql
-- 1 query to get users
SELECT * FROM users LIMIT 10;

-- Then N queries (one per user!)
SELECT * FROM orders WHERE user_id = 1;
SELECT * FROM orders WHERE user_id = 2;
-- ... 10 queries total
```

**Good (Join instead):**
```sql
-- 1 query: users + orders together
SELECT u.*, o.* FROM users u
LEFT JOIN orders o ON u.id = o.user_id
LIMIT 10;
```

### 2. Subquery Optimization

**Inefficient (evaluates subquery per row):**
```sql
SELECT * FROM orders o
WHERE o.user_id IN (
  SELECT user_id FROM users WHERE created_at > NOW() - INTERVAL 30 DAY
);
```

**Optimized (use JOIN or CTE):**
```sql
-- Option 1: JOIN
SELECT DISTINCT o.* FROM orders o
INNER JOIN users u ON o.user_id = u.id
WHERE u.created_at > NOW() - INTERVAL 30 DAY;

-- Option 2: CTE (more readable)
WITH recent_users AS (
  SELECT user_id FROM users WHERE created_at > NOW() - INTERVAL 30 DAY
)
SELECT * FROM orders WHERE user_id IN (SELECT user_id FROM recent_users);
```

### 3. Aggregation Optimization

**Slow (full table aggregation):**
```sql
SELECT COUNT(*) FROM orders;  -- Counts all billion rows
```

**Fast (approximate count from stats):**
```sql
-- PostgreSQL: Use relation stats (almost instant)
SELECT (EXTRACT(EPOCH FROM NOW()) - EXTRACT(EPOCH FROM pg_stat_get_live_tuples('orders'::regclass)))::bigint as estimated_rows;

-- Or: Keep running count in separate table
SELECT count FROM order_counts WHERE metric = 'total_orders';
```

### 4. LIMIT Optimization (Pagination)

**Problem: OFFSET is expensive**
```sql
-- Bad for large offsets (scans all 999,999 rows first!)
SELECT * FROM orders ORDER BY created_at DESC LIMIT 10 OFFSET 999990;
```

**Solution: Cursor-based pagination**
```sql
-- Instead of offset, remember last ID
SELECT * FROM orders
WHERE created_at < (SELECT created_at FROM orders WHERE id = ?)
ORDER BY created_at DESC LIMIT 10;
```

## Database Configuration Tuning

### PostgreSQL (postgresql.conf)

```ini
# Memory allocation
shared_buffers = 25% of RAM           # Working memory for cache
effective_cache_size = 75% of RAM     # Total available memory
work_mem = RAM / max_parallel_processes

# Parallelization (PG 9.6+)
max_parallel_workers_per_gather = 4
max_parallel_maintenance_workers = 4

# Query planner
random_page_cost = 1.1  # Lower for SSDs (default 4 for HDDs)
```

### MySQL (my.cnf)

```ini
# InnoDB buffer pool (most important)
innodb_buffer_pool_size = 75% of RAM

# Query cache (legacy, often disabled in MySQL 8.0+)
query_cache_type = OFF  # Modern: Use Redis/Memcached instead

# Connection limits
max_connections = 200
```

## Profiling Tools & Commands

| Tool | Purpose | Command |
|------|---------|---------|
| **EXPLAIN** | See query plan | `EXPLAIN SELECT ...` |
| **pgbench** | Load testing PostgreSQL | `pgbench -c 10 -j 2 -T 30 db` |
| **mysqlslap** | Load testing MySQL | `mysqlslap --concurrency=10 --iterations=100` |
| **pt-query-digest** | Analyze slow log | `pt-query-digest /var/log/mysql/slow.log` |
| **SHOW PROCESSLIST** | Live queries | `SHOW FULL PROCESSLIST` |
| **pg_stat_statements** | Per-query stats (PG) | `SELECT * FROM pg_stat_statements ORDER BY total_time DESC` |

## Performance Checklist

- [ ] **ANALYZE**: Run `EXPLAIN ANALYZE` on slow queries
- [ ] **INDEXES**: Create indexes on WHERE/JOIN/ORDER BY columns
- [ ] **STATISTICS**: Update table statistics (`ANALYZE table_name`)
- [ ] **N+1**: Verify no N+1 patterns in application code
- [ ] **JOINS**: Prefer JOIN over IN (SELECT ...)
- [ ] **LIMITS**: Use cursor pagination instead of OFFSET
- [ ] **CACHE**: Consider caching aggregations/reports
- [ ] **PARTITIONING**: Partition huge tables (>100M rows) by date or hash
- [ ] **DENORMALIZATION**: Strategic denormalization for reporting tables

## Anti-Patterns

❌ Optimizing without EXPLAIN (guessing)
❌ Creating indexes on low-selectivity columns
❌ Assuming indexes help all queries (cost analysis needed)
❌ Ignoring table statistics (run ANALYZE regularly)
❌ Caching hot tables instead of optimizing queries

## Best Practices

✅ **Measure before optimizing** — Use real production data
✅ **Profile bottlenecks** — EXPLAIN ANALYZE is your friend
✅ **Index strategically** — Every index slows writes
✅ **Monitor constantly** — Set up alerts for slow queries
✅ **Test on production-like data** — Dev data hides issues
✅ **Document why** — Explain why index was created (future you will thank you)

## Resources

- **Detailed patterns**: See `resources/implementation-playbook.md`
- **PostgreSQL docs**: https://www.postgresql.org/docs/current/sql-explain.html
- **MySQL docs**: https://dev.mysql.com/doc/refman/8.0/en/explain.html
- **Use The Index Luke**: https://use-the-index-luke.com/ (free book)
