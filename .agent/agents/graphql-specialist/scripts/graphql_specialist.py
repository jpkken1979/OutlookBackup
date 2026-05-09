#!/usr/bin/env python3
"""
GraphQL Specialist Agent

Diseña schemas, genera resolvers, y optimiza APIs GraphQL.
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class GraphQLType:
    """Representa un tipo GraphQL."""

    name: str
    kind: str  # type, input, interface, union, enum, scalar
    fields: list = field(default_factory=list)
    implements: list = field(default_factory=list)
    description: str = ""


@dataclass
class GraphQLField:
    """Campo de un tipo GraphQL."""

    name: str
    type: str
    nullable: bool = True
    args: list = field(default_factory=list)
    description: str = ""


# Templates de schema
SCHEMA_TEMPLATES = {
    "basic": '''"""
{description}
"""
type Query {{
  {queries}
}}

type Mutation {{
  {mutations}
}}
''',
    "with_subscriptions": '''"""
{description}
"""
type Query {{
  {queries}
}}

type Mutation {{
  {mutations}
}}

type Subscription {{
  {subscriptions}
}}
''',
}

# Templates de resolvers
RESOLVER_TEMPLATES = {
    "typescript": """import {{ Resolvers }} from './generated/graphql';

export const {name}Resolvers: Resolvers = {{
  Query: {{
    {query_resolvers}
  }},
  Mutation: {{
    {mutation_resolvers}
  }},
  {type_name}: {{
    {field_resolvers}
  }},
}};
""",
    "python": """from ariadne import QueryType, MutationType, ObjectType

query = QueryType()
mutation = MutationType()
{type_lower} = ObjectType("{type_name}")

{query_resolvers}

{mutation_resolvers}

{field_resolvers}

resolvers = [query, mutation, {type_lower}]
""",
}

# Directivas comunes
COMMON_DIRECTIVES = {
    "deprecated": 'directive @deprecated(reason: String = "No longer supported") on FIELD_DEFINITION | ENUM_VALUE',
    "auth": "directive @auth(requires: Role = ADMIN) on FIELD_DEFINITION | OBJECT",
    "cacheControl": "directive @cacheControl(maxAge: Int, scope: CacheControlScope) on FIELD_DEFINITION | OBJECT",
    "rateLimit": "directive @rateLimit(limit: Int!, duration: Int!) on FIELD_DEFINITION",
}


def parse_schema(schema_content: str) -> list:
    """Parsea un schema GraphQL básico."""
    types = []

    # Extraer types
    type_pattern = r"type\s+(\w+)(?:\s+implements\s+([\w\s&]+))?\s*\{([^}]+)\}"
    for match in re.finditer(type_pattern, schema_content):
        name = match.group(1)
        implements = match.group(2).split("&") if match.group(2) else []
        fields_str = match.group(3)

        fields = []
        field_pattern = r"(\w+)(?:\([^)]*\))?\s*:\s*([\w\[\]!]+)"
        for field_match in re.finditer(field_pattern, fields_str):
            fields.append(
                GraphQLField(
                    name=field_match.group(1),
                    type=field_match.group(2),
                    nullable="!" not in field_match.group(2),
                )
            )

        types.append(
            GraphQLType(
                name=name, kind="type", fields=fields, implements=[i.strip() for i in implements]
            )
        )

    # Extraer inputs
    input_pattern = r"input\s+(\w+)\s*\{([^}]+)\}"
    for match in re.finditer(input_pattern, schema_content):
        name = match.group(1)
        fields_str = match.group(2)

        fields = []
        field_pattern = r"(\w+)\s*:\s*([\w\[\]!]+)"
        for field_match in re.finditer(field_pattern, fields_str):
            fields.append(GraphQLField(name=field_match.group(1), type=field_match.group(2)))

        types.append(GraphQLType(name=name, kind="input", fields=fields))

    # Extraer enums
    enum_pattern = r"enum\s+(\w+)\s*\{([^}]+)\}"
    for match in re.finditer(enum_pattern, schema_content):
        name = match.group(1)
        values = [v.strip() for v in match.group(2).split("\n") if v.strip()]
        types.append(
            GraphQLType(
                name=name,
                kind="enum",
                fields=[GraphQLField(name=v, type="EnumValue") for v in values],
            )
        )

    return types


def generate_type_schema(name: str, fields: list, description: str = "") -> str:
    """Genera schema para un tipo."""
    lines = []

    if description:
        lines.append(f'"""{description}"""')

    lines.append(f"type {name} {{")

    for field in fields:
        field_type = field.get("type", "String")
        nullable = field.get("nullable", True)
        type_str = field_type if nullable else f"{field_type}!"

        if field.get("description"):
            lines.append(f'  """{field["description"]}"""')
        lines.append(f"  {field['name']}: {type_str}")

    lines.append("}")

    return "\n".join(lines)


def generate_crud_schema(entity_name: str) -> str:
    """Genera schema CRUD completo para una entidad."""
    entity_lower = entity_name.lower()

    schema = f'''"""
{entity_name} entity
"""
type {entity_name} {{
  id: ID!
  createdAt: DateTime!
  updatedAt: DateTime!
}}

input Create{entity_name}Input {{
  # Add fields here
}}

input Update{entity_name}Input {{
  # Add fields here
}}

type {entity_name}Connection {{
  edges: [{entity_name}Edge!]!
  pageInfo: PageInfo!
  totalCount: Int!
}}

type {entity_name}Edge {{
  node: {entity_name}!
  cursor: String!
}}

extend type Query {{
  """Get a single {entity_name} by ID"""
  {entity_lower}(id: ID!): {entity_name}

  """List all {entity_name}s with pagination"""
  {entity_lower}s(
    first: Int
    after: String
    last: Int
    before: String
    filter: {entity_name}Filter
    orderBy: {entity_name}OrderBy
  ): {entity_name}Connection!
}}

extend type Mutation {{
  """Create a new {entity_name}"""
  create{entity_name}(input: Create{entity_name}Input!): {entity_name}!

  """Update an existing {entity_name}"""
  update{entity_name}(id: ID!, input: Update{entity_name}Input!): {entity_name}!

  """Delete a {entity_name}"""
  delete{entity_name}(id: ID!): Boolean!
}}

input {entity_name}Filter {{
  id: IDFilter
  # Add more filters
}}

input {entity_name}OrderBy {{
  field: {entity_name}OrderField!
  direction: OrderDirection!
}}

enum {entity_name}OrderField {{
  CREATED_AT
  UPDATED_AT
}}
'''

    return schema


def generate_resolver_typescript(type_name: str) -> str:
    """Genera resolver en TypeScript."""
    type_lower = type_name.lower()

    return f"""import {{ Resolvers }} from '../generated/graphql';
import {{ {type_name}Service }} from '../services/{type_lower}.service';
import {{ Context }} from '../context';

export const {type_lower}Resolvers: Resolvers<Context> = {{
  Query: {{
    {type_lower}: async (_, {{ id }}, ctx) => {{
      return ctx.dataSources.{type_lower}Service.findById(id);
    }},

    {type_lower}s: async (_, args, ctx) => {{
      return ctx.dataSources.{type_lower}Service.findMany(args);
    }},
  }},

  Mutation: {{
    create{type_name}: async (_, {{ input }}, ctx) => {{
      ctx.requireAuth();
      return ctx.dataSources.{type_lower}Service.create(input);
    }},

    update{type_name}: async (_, {{ id, input }}, ctx) => {{
      ctx.requireAuth();
      return ctx.dataSources.{type_lower}Service.update(id, input);
    }},

    delete{type_name}: async (_, {{ id }}, ctx) => {{
      ctx.requireAuth();
      return ctx.dataSources.{type_lower}Service.delete(id);
    }},
  }},

  {type_name}: {{
    // Add field resolvers here
    // relatedItems: async (parent, _, ctx) => {{
    //   return ctx.dataSources.itemService.findByParentId(parent.id);
    // }},
  }},
}};
"""


def generate_resolver_python(type_name: str) -> str:
    """Genera resolver en Python (Ariadne)."""
    type_lower = type_name.lower()

    return f'''from ariadne import QueryType, MutationType, ObjectType
from .services import {type_lower}_service
from .auth import require_auth

query = QueryType()
mutation = MutationType()
{type_lower}_type = ObjectType("{type_name}")


@query.field("{type_lower}")
async def resolve_{type_lower}(_, info, id: str):
    return await {type_lower}_service.find_by_id(id)


@query.field("{type_lower}s")
async def resolve_{type_lower}s(_, info, **kwargs):
    return await {type_lower}_service.find_many(**kwargs)


@mutation.field("create{type_name}")
@require_auth
async def resolve_create_{type_lower}(_, info, input: dict):
    return await {type_lower}_service.create(input)


@mutation.field("update{type_name}")
@require_auth
async def resolve_update_{type_lower}(_, info, id: str, input: dict):
    return await {type_lower}_service.update(id, input)


@mutation.field("delete{type_name}")
@require_auth
async def resolve_delete_{type_lower}(_, info, id: str):
    return await {type_lower}_service.delete(id)


resolvers = [query, mutation, {type_lower}_type]
'''


def generate_dataloader(type_name: str) -> str:
    """Genera DataLoader para batching."""
    type_lower = type_name.lower()

    return f"""import DataLoader from 'dataloader';
import {{ {type_name} }} from '../generated/graphql';
import {{ {type_name}Repository }} from '../repositories/{type_lower}.repository';

export function create{type_name}Loader(repository: {type_name}Repository) {{
  return new DataLoader<string, {type_name} | null>(
    async (ids) => {{
      const items = await repository.findByIds(ids as string[]);

      // Map results to maintain order
      const itemMap = new Map(items.map(item => [item.id, item]));
      return ids.map(id => itemMap.get(id) ?? null);
    }},
    {{
      // Enable caching within a single request
      cache: true,
      // Batch window in ms
      batchScheduleFn: (callback) => setTimeout(callback, 10),
    }}
  );
}}
"""


def analyze_schema(schema_content: str) -> dict:
    """Analiza un schema GraphQL y detecta problemas."""
    issues = []
    recommendations = []

    types = parse_schema(schema_content)

    # Contar tipos
    type_counts = {"type": 0, "input": 0, "enum": 0, "interface": 0}
    for t in types:
        type_counts[t.kind] = type_counts.get(t.kind, 0) + 1

    # Detectar problemas
    for t in types:
        # Tipos muy grandes
        if len(t.fields) > 20:
            issues.append(
                {
                    "severity": "medium",
                    "type": t.name,
                    "message": f"Type {t.name} tiene {len(t.fields)} campos (considera dividir)",
                }
            )

        # Campos sin descripción
        fields_without_desc = [f for f in t.fields if not f.description]
        if len(fields_without_desc) > 5:
            issues.append(
                {
                    "severity": "low",
                    "type": t.name,
                    "message": f"Type {t.name} tiene campos sin documentar",
                }
            )

    # Recomendaciones
    if not any(t.name == "PageInfo" for t in types):
        recommendations.append("Agregar PageInfo type para paginación Relay-style")

    if not any("DateTime" in str(t.fields) for t in types):
        recommendations.append("Considerar agregar scalar DateTime")

    if not re.search(r"directive\s+@auth", schema_content):
        recommendations.append("Considerar agregar directiva @auth para autorización")

    return {
        "types_count": type_counts,
        "total_types": len(types),
        "total_fields": sum(len(t.fields) for t in types),
        "issues": issues,
        "recommendations": recommendations,
    }


def generate_common_types() -> str:
    """Genera tipos comunes reutilizables."""
    return '''"""
Common scalar types
"""
scalar DateTime
scalar JSON
scalar Upload

"""
Pagination types (Relay-style)
"""
type PageInfo {
  hasNextPage: Boolean!
  hasPreviousPage: Boolean!
  startCursor: String
  endCursor: String
}

"""
Common filter inputs
"""
input IDFilter {
  eq: ID
  in: [ID!]
  notIn: [ID!]
}

input StringFilter {
  eq: String
  contains: String
  startsWith: String
  endsWith: String
  in: [String!]
}

input IntFilter {
  eq: Int
  gt: Int
  gte: Int
  lt: Int
  lte: Int
  in: [Int!]
}

input DateTimeFilter {
  eq: DateTime
  gt: DateTime
  gte: DateTime
  lt: DateTime
  lte: DateTime
}

"""
Sorting
"""
enum OrderDirection {
  ASC
  DESC
}

"""
Error handling
"""
interface Error {
  message: String!
  code: String!
}

type ValidationError implements Error {
  message: String!
  code: String!
  field: String!
}

type NotFoundError implements Error {
  message: String!
  code: String!
  resourceType: String!
  resourceId: ID!
}

union MutationResult = Success | ValidationError | NotFoundError

type Success {
  success: Boolean!
}
'''


def main():
    parser = argparse.ArgumentParser(
        description="GraphQL Specialist - Diseña y optimiza APIs GraphQL"
    )

    subparsers = parser.add_subparsers(dest="command", help="Comando")

    # analyze
    analyze_parser = subparsers.add_parser("analyze", help="Analiza schema")
    analyze_parser.add_argument("schema", help="Archivo .graphql")

    # generate
    gen_parser = subparsers.add_parser("generate", help="Genera schema")
    gen_parser.add_argument("--entity", "-e", required=True, help="Nombre de entidad")
    gen_parser.add_argument("--crud", action="store_true", help="Generar CRUD completo")

    # resolver
    res_parser = subparsers.add_parser("resolver", help="Genera resolver")
    res_parser.add_argument("type_name", help="Nombre del tipo")
    res_parser.add_argument(
        "--language", "-l", choices=["typescript", "python"], default="typescript"
    )

    # dataloader
    dl_parser = subparsers.add_parser("dataloader", help="Genera DataLoader")
    dl_parser.add_argument("type_name", help="Nombre del tipo")

    # common
    subparsers.add_parser("common", help="Genera tipos comunes")

    # validate
    val_parser = subparsers.add_parser("validate", help="Valida schema")
    val_parser.add_argument("schema", help="Archivo .graphql")

    # Común
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--output", "-o", help="Archivo de salida")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    output = None

    if args.command == "analyze":
        schema_path = Path(args.schema)
        if not schema_path.exists():
            print(f"Error: {args.schema} no existe")
            return 1

        schema_content = schema_path.read_text()
        analysis = analyze_schema(schema_content)

        if args.json:
            output = json.dumps(analysis, indent=2)
        else:
            print(f"\n{'=' * 60}")
            print(" ANÁLISIS DE SCHEMA GRAPHQL")
            print(f"{'=' * 60}")
            print("\n📊 Estadísticas:")
            for kind, count in analysis["types_count"].items():
                if count > 0:
                    print(f"   {kind}: {count}")
            print(f"   Total campos: {analysis['total_fields']}")

            if analysis["issues"]:
                print(f"\n⚠️  Problemas ({len(analysis['issues'])}):")
                for issue in analysis["issues"]:
                    icon = {"low": "🟢", "medium": "🟡", "high": "🟠"}[issue["severity"]]
                    print(f"   {icon} [{issue['type']}] {issue['message']}")

            if analysis["recommendations"]:
                print("\n💡 Recomendaciones:")
                for rec in analysis["recommendations"]:
                    print(f"   • {rec}")

    elif args.command == "generate":
        if args.crud:
            output = generate_crud_schema(args.entity)
        else:
            output = generate_type_schema(args.entity, [])

    elif args.command == "resolver":
        if args.language == "typescript":
            output = generate_resolver_typescript(args.type_name)
        else:
            output = generate_resolver_python(args.type_name)

    elif args.command == "dataloader":
        output = generate_dataloader(args.type_name)

    elif args.command == "common":
        output = generate_common_types()

    elif args.command == "validate":
        schema_path = Path(args.schema)
        if not schema_path.exists():
            print(f"Error: {args.schema} no existe")
            return 1

        schema_content = schema_path.read_text()
        types = parse_schema(schema_content)

        print("✓ Schema válido")
        print(f"  Tipos encontrados: {len(types)}")
        for t in types[:10]:
            print(f"    - {t.name} ({t.kind})")
        if len(types) > 10:
            print(f"    ... y {len(types) - 10} más")

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
