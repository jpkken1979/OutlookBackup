#!/usr/bin/env python3
"""
Drizzle ORM Skill

Genera schemas, migrations, y queries para Drizzle ORM.
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path


# Type mappings
TYPE_MAP = {
    "serial": "serial",
    "int": "integer",
    "integer": "integer",
    "bigint": "bigint",
    "text": "text",
    "string": "varchar(255)",
    "varchar": "varchar",
    "boolean": "boolean",
    "bool": "boolean",
    "timestamp": "timestamp",
    "date": "date",
    "json": "json",
    "jsonb": "jsonb",
    "uuid": "uuid",
    "real": "real",
    "float": "real",
    "double": "doublePrecision",
}

# Schema template
SCHEMA_TEMPLATE = """import {{ pgTable, {column_types} }} from 'drizzle-orm/pg-core';
import {{ createInsertSchema, createSelectSchema }} from 'drizzle-zod';
import {{ z }} from 'zod';

export const {table_name} = pgTable('{table_name}', {{
{columns}
}});

// Zod schemas for validation
export const insert{model_name}Schema = createInsertSchema({table_name});
export const select{model_name}Schema = createSelectSchema({table_name});

// TypeScript types
export type {model_name} = typeof {table_name}.$inferSelect;
export type New{model_name} = typeof {table_name}.$inferInsert;
"""

# Drizzle config template
DRIZZLE_CONFIG = """import type {{ Config }} from 'drizzle-kit';

export default {{
  schema: './src/db/schema/*',
  out: './drizzle',
  driver: '{driver}',
  dbCredentials: {{
    {credentials}
  }},
}} satisfies Config;
"""

# Query templates
QUERY_TEMPLATES = {
    "findAll": """// Find all {table}
export async function findAll{model}s() {{
  return db.select().from({table});
}}
""",
    "findById": """// Find {table} by ID
export async function find{model}ById(id: {id_type}) {{
  return db.select().from({table}).where(eq({table}.id, id));
}}
""",
    "findByField": """// Find {table} by field
export async function find{model}By{field_cap}({field}: {field_type}) {{
  return db.select().from({table}).where(eq({table}.{field}, {field}));
}}
""",
    "create": """// Create {table}
export async function create{model}(data: New{model}) {{
  return db.insert({table}).values(data).returning();
}}
""",
    "update": """// Update {table}
export async function update{model}(id: {id_type}, data: Partial<New{model}>) {{
  return db.update({table})
    .set({{ ...data, updatedAt: new Date() }})
    .where(eq({table}.id, id))
    .returning();
}}
""",
    "delete": """// Delete {table}
export async function delete{model}(id: {id_type}) {{
  return db.delete({table}).where(eq({table}.id, id)).returning();
}}
""",
    "paginate": """// Paginate {table}
export async function paginate{model}s(page: number = 1, limit: number = 10) {{
  const offset = (page - 1) * limit;

  const [items, countResult] = await Promise.all([
    db.select().from({table}).limit(limit).offset(offset),
    db.select({{ count: count() }}).from({table}),
  ]);

  return {{
    items,
    total: countResult[0].count,
    page,
    limit,
    totalPages: Math.ceil(countResult[0].count / limit),
  }};
}}
""",
}

# Migration template
MIGRATION_TEMPLATE = """-- Migration: {name}
-- Created at: {timestamp}

-- Up Migration
{up_sql}

-- Down Migration (rollback)
-- {down_sql}
"""

# Relations template
RELATIONS_TEMPLATE = """import {{ relations }} from 'drizzle-orm';
import {{ {tables} }} from './schema';

export const {table}Relations = relations({table}, ({{ one, many }}) => ({{
  // One-to-one relation
  // profile: one(profiles, {{
  //   fields: [{table}.profileId],
  //   references: [profiles.id],
  // }}),

  // One-to-many relation
  // posts: many(posts),
}}));
"""


def parse_fields(fields_str: str) -> list:
    """Parsea string de campos a lista."""
    fields = []
    for field in fields_str.split(","):
        parts = field.strip().split(":")
        if len(parts) >= 2:
            name = parts[0].strip()
            field_type = parts[1].strip()
            nullable = len(parts) > 2 and "nullable" in parts[2]
            default = None
            if len(parts) > 2:
                for part in parts[2:]:
                    if part.startswith("default="):
                        default = part.split("=")[1]

            fields.append(
                {
                    "name": name,
                    "type": TYPE_MAP.get(field_type, field_type),
                    "nullable": nullable,
                    "default": default,
                }
            )
    return fields


def generate_column(field: dict) -> str:
    """Genera definición de columna Drizzle."""
    name = field["name"]
    col_type = field["type"]

    # Handle special types
    if col_type == "serial":
        col = f"  {name}: serial('{name}').primaryKey()"
    elif col_type == "uuid":
        col = f"  {name}: uuid('{name}').defaultRandom().primaryKey()"
    elif "varchar" in col_type:
        match = re.search(r"\((\d+)\)", col_type)
        length = match.group(1) if match else "255"
        col = f"  {name}: varchar('{name}', {{ length: {length} }})"
    else:
        col = f"  {name}: {col_type}('{name}')"

    # Add modifiers
    if field.get("nullable"):
        pass  # Nullable by default in Drizzle
    else:
        col += ".notNull()"

    if field.get("default"):
        default_val = field["default"]
        if default_val == "now":
            col += ".defaultNow()"
        elif default_val == "uuid":
            col += ".defaultRandom()"
        else:
            col += f".default({default_val})"

    return col


def generate_schema(model_name: str, fields: list) -> str:
    """Genera schema Drizzle."""
    table_name = model_name.lower() + "s"

    # Generate columns
    columns = []
    column_types = set()

    for field in fields:
        col = generate_column(field)
        columns.append(col)

        # Track types used
        col_type = field["type"]
        if col_type == "serial":
            column_types.add("serial")
        elif "varchar" in col_type:
            column_types.add("varchar")
        elif col_type in TYPE_MAP.values():
            column_types.add(col_type)

    # Add common columns
    columns.append("  createdAt: timestamp('created_at').defaultNow().notNull()")
    columns.append("  updatedAt: timestamp('updated_at').defaultNow().notNull()")
    column_types.add("timestamp")

    return SCHEMA_TEMPLATE.format(
        table_name=table_name,
        model_name=model_name,
        columns=",\n".join(columns),
        column_types=", ".join(sorted(column_types)),
    )


def generate_queries(table_name: str, model_name: str, id_type: str = "string") -> str:
    """Genera queries comunes."""
    queries = []

    for _name, template in QUERY_TEMPLATES.items():
        query = template.format(
            table=table_name,
            model=model_name,
            id_type=id_type,
            field="name",
            field_cap="Name",
            field_type="string",
        )
        queries.append(query)

    imports = f"""import {{ db }} from './db';
import {{ {table_name} }} from './schema';
import {{ eq, count }} from 'drizzle-orm';
import type {{ New{model_name} }} from './schema';

"""

    return imports + "\n".join(queries)


def generate_migration(name: str, up_sql: str = "", down_sql: str = "") -> str:
    """Genera archivo de migración."""
    datetime.now().strftime("%Y%m%d%H%M%S")

    return MIGRATION_TEMPLATE.format(
        name=name,
        timestamp=datetime.now().isoformat(),
        up_sql=up_sql or "-- Add your SQL here",
        down_sql=down_sql or "-- Add rollback SQL here",
    )


def generate_config(database: str) -> str:
    """Genera drizzle.config.ts."""
    if database == "postgres":
        return DRIZZLE_CONFIG.format(
            driver="pg", credentials="connectionString: process.env.DATABASE_URL!"
        )
    elif database == "mysql":
        return DRIZZLE_CONFIG.format(
            driver="mysql2", credentials="""uri: process.env.DATABASE_URL!"""
        )
    elif database == "sqlite":
        return DRIZZLE_CONFIG.format(driver="better-sqlite", credentials="url: './sqlite.db'")
    return ""


def generate_db_client(database: str) -> str:
    """Genera cliente de base de datos."""
    if database == "postgres":
        return """import { drizzle } from 'drizzle-orm/postgres-js';
import postgres from 'postgres';
import * as schema from './schema';

const connectionString = process.env.DATABASE_URL!;
const client = postgres(connectionString);
export const db = drizzle(client, { schema });
"""
    elif database == "mysql":
        return """import { drizzle } from 'drizzle-orm/mysql2';
import mysql from 'mysql2/promise';
import * as schema from './schema';

const connection = await mysql.createConnection(process.env.DATABASE_URL!);
export const db = drizzle(connection, { schema, mode: 'default' });
"""
    elif database == "sqlite":
        return """import { drizzle } from 'drizzle-orm/better-sqlite3';
import Database from 'better-sqlite3';
import * as schema from './schema';

const sqlite = new Database('./sqlite.db');
export const db = drizzle(sqlite, { schema });
"""
    return ""


def main():
    parser = argparse.ArgumentParser(description="Drizzle ORM Skill - Genera schemas y queries")

    subparsers = parser.add_subparsers(dest="command", help="Comando")

    # schema
    schema_parser = subparsers.add_parser("schema", help="Genera schema")
    schema_parser.add_argument("--model", "-m", required=True, help="Nombre del modelo")
    schema_parser.add_argument("--fields", "-f", required=True, help="Campos (name:type,...)")

    # queries
    queries_parser = subparsers.add_parser("queries", help="Genera queries")
    queries_parser.add_argument("--table", "-t", required=True, help="Nombre de la tabla")
    queries_parser.add_argument("--model", "-m", help="Nombre del modelo")

    # migration
    mig_parser = subparsers.add_parser("migration", help="Genera migration")
    mig_parser.add_argument("--name", "-n", required=True, help="Nombre de la migración")

    # setup
    setup_parser = subparsers.add_parser("setup", help="Genera setup completo")
    setup_parser.add_argument(
        "--database", "-d", choices=["postgres", "mysql", "sqlite"], default="postgres"
    )

    # config
    config_parser = subparsers.add_parser("config", help="Genera drizzle.config.ts")
    config_parser.add_argument(
        "--database", "-d", choices=["postgres", "mysql", "sqlite"], default="postgres"
    )

    # Común
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--output", "-o", help="Archivo de salida")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    output = None

    if args.command == "schema":
        fields = parse_fields(args.fields)
        output = generate_schema(args.model, fields)

    elif args.command == "queries":
        model_name = args.model or args.table.title().rstrip("s")
        output = generate_queries(args.table, model_name)

    elif args.command == "migration":
        output = generate_migration(args.name)

    elif args.command == "config":
        output = generate_config(args.database)

    elif args.command == "setup":
        files = {
            "drizzle.config.ts": generate_config(args.database),
            "src/db/index.ts": generate_db_client(args.database),
        }
        if args.json:
            output = json.dumps(files, indent=2)
        else:
            for filename, content in files.items():
                print(f"\n{'=' * 60}")
                print(f" {filename}")
                print(f"{'=' * 60}\n")
                print(content)

    # Output
    if output:
        if hasattr(args, "output") and args.output:
            Path(args.output).write_text(output)
            print(f"✓ Escrito en {args.output}")
        else:
            print(output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
