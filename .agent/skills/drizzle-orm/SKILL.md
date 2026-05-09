---
name: drizzle-orm
description: Skill para trabajar con Drizzle ORM, el ORM TypeScript headless con máximo type-safety y mínimo overhead
type: feature
---

# Drizzle ORM

## Metadata
- **Name**: Drizzle ORM
- **Category**: Database
- **Version**: 1.0.0
- **Author**: Antigravity Team

## Description
Skill para trabajar con Drizzle ORM, el ORM TypeScript headless con máximo type-safety y mínimo overhead.

## Capabilities
- Generación de schemas
- Migrations management
- Query building type-safe
- Relations y joins
- Integración con múltiples drivers
- Drizzle Studio
- Introspección de DB existente

## Key Features
- **SQL-like**: Sintaxis familiar para desarrolladores SQL
- **Zero dependencies**: Core sin dependencias externas
- **Multiple dialects**: PostgreSQL, MySQL, SQLite
- **Serverless ready**: Conexiones eficientes

## Usage
```bash
# Generar schema desde modelo
python scripts/drizzle_orm.py schema --model User --fields "id:serial,name:text,email:text"

# Generar migration
python scripts/drizzle_orm.py migration --name create_users

# Generar queries comunes
python scripts/drizzle_orm.py queries --table users

# Setup completo
python scripts/drizzle_orm.py setup --database postgres --project .
```

## Inputs
- `model_name`: Nombre del modelo
- `fields`: Definición de campos
- `database`: postgres | mysql | sqlite
- `migration_name`: Nombre de la migración

## Outputs
- Schema files (TypeScript)
- Migration files
- Query examples
- drizzle.config.ts

## Dependencies
- drizzle-orm
- drizzle-kit
- postgres / mysql2 / better-sqlite3

## Related Skills
- `database-design`
- `postgres-best-practices`
- `prisma-expert`
