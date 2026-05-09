---
name: sql-optimization
description: "Optimiza queries SQL, analiza planes de ejecución y recomienda índices. Soporta PostgreSQL, MySQL y SQLite. Detecta anti-patterns (SELECT *, missing WHERE, LIKE '%val%', implicit type conversion, N+1 queries). Triggers: SQL optimization, query performance, EXPLAIN plan, index recommendation, SQL anti-patterns, database tuning."
type: feature
---

# sql-optimization

## Metadata
- **Name**: SQL Optimization
- **Category**: Database
- **Version**: 1.0.0
- **Author**: Antigravity Team

## Description
Skill para optimizar queries SQL, analizar planes de ejecución, y recomendar índices. Soporta PostgreSQL, MySQL, y SQLite.

## Capabilities
- Análisis de queries SQL
- Detección de anti-patterns
- Recomendación de índices
- Reescritura de queries
- Análisis de EXPLAIN plans
- Detección de N+1 queries
- Optimización de JOINs
- Partitioning recommendations

## Inputs
- `query`: Query SQL a analizar
- `schema`: Schema de la base de datos (opcional)
- `database`: Tipo de base de datos (postgresql, mysql, sqlite)
- `explain_output`: Output de EXPLAIN ANALYZE (opcional)

## Outputs
- Score de calidad del query (0-100)
- Lista de problemas detectados
- Sugerencias de optimización
- Query reescrito (opcional)
- Índices recomendados

## Usage
```bash
python scripts/sql_optimization.py analyze "SELECT * FROM users WHERE email = 'test@test.com'"
python scripts/sql_optimization.py check-antipatterns query.sql
python scripts/sql_optimization.py suggest-indexes schema.sql queries/
python scripts/sql_optimization.py --list-antipatterns
```

## Anti-patterns Detectados
- SELECT *
- Missing WHERE clause
- LIKE '%value%' (no puede usar índice)
- OR en WHERE (considerar UNION)
- Implicit type conversion
- Functions on indexed columns
- Correlated subqueries
- Missing LIMIT
- Cartesian joins
- NOT IN with NULLs

## Dependencies
- sqlparse
- sqlglot (optional)

## Related Skills
- `sql-optimization-patterns`
- `database-design`
- `postgres-best-practices`
