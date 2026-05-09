#!/usr/bin/env python3
"""
SQL Optimization Skill

Analiza queries SQL, detecta anti-patterns, y sugiere optimizaciones.
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SQLIssue:
    """Problema detectado en un query SQL."""

    name: str
    severity: str  # low, medium, high, critical
    line: int
    description: str
    suggestion: str
    original: str
    improved: str | None = None


@dataclass
class SQLAnalysis:
    """Resultado del análisis de un query."""

    query: str
    score: int  # 0-100
    issues: list = field(default_factory=list)
    recommendations: list = field(default_factory=list)
    estimated_complexity: str = "unknown"  # simple, moderate, complex


# Anti-patterns de SQL
SQL_ANTIPATTERNS = {
    "select_star": {
        "pattern": r"SELECT\s+\*",
        "name": "SELECT *",
        "severity": "medium",
        "description": "SELECT * trae todas las columnas, incluso las que no necesitas",
        "suggestion": "Especifica solo las columnas que necesitas: SELECT col1, col2, col3",
    },
    "no_where": {
        "pattern": r"^SELECT\s+.+\s+FROM\s+\w+\s*(?:;|$)",
        "name": "Missing WHERE clause",
        "severity": "high",
        "description": "Query sin WHERE clause puede traer millones de registros",
        "suggestion": "Agrega una cláusula WHERE para filtrar resultados",
    },
    "like_leading_wildcard": {
        "pattern": r"LIKE\s+['\"]%",
        "name": "LIKE with leading wildcard",
        "severity": "high",
        "description": "LIKE '%value' no puede usar índices, causa full table scan",
        "suggestion": "Usar LIKE 'value%' o considerar full-text search",
    },
    "or_in_where": {
        "pattern": r"WHERE\s+.+\s+OR\s+",
        "name": "OR in WHERE clause",
        "severity": "medium",
        "description": "OR puede prevenir uso de índices",
        "suggestion": "Considerar usar UNION o IN() para mejor performance",
    },
    "not_in": {
        "pattern": r"NOT\s+IN\s*\(",
        "name": "NOT IN with subquery",
        "severity": "medium",
        "description": "NOT IN con subquery puede tener problemas con NULLs y performance",
        "suggestion": "Usar NOT EXISTS o LEFT JOIN WHERE IS NULL",
    },
    "function_on_column": {
        "pattern": r"WHERE\s+(?:UPPER|LOWER|TRIM|YEAR|MONTH|DATE)\s*\(",
        "name": "Function on indexed column",
        "severity": "high",
        "description": "Aplicar funciones a columnas previene uso de índices",
        "suggestion": "Indexar la expresión o reformular el query",
    },
    "implicit_conversion": {
        "pattern": r"=\s*['\"][0-9]+['\"]",
        "name": "Potential implicit type conversion",
        "severity": "low",
        "description": "Comparar números como strings puede causar conversión implícita",
        "suggestion": "Usar el tipo de dato correcto sin comillas para números",
    },
    "distinct_overuse": {
        "pattern": r"SELECT\s+DISTINCT\s+",
        "name": "DISTINCT might hide a problem",
        "severity": "low",
        "description": "DISTINCT a menudo oculta un problema de JOINs duplicados",
        "suggestion": "Verificar si los JOINs son correctos antes de usar DISTINCT",
    },
    "no_limit": {
        "pattern": r"SELECT\s+.+\s+FROM\s+(?!.*LIMIT)",
        "name": "No LIMIT clause",
        "severity": "low",
        "description": "Queries sin LIMIT pueden retornar demasiados registros",
        "suggestion": "Agregar LIMIT para paginar resultados",
    },
    "cartesian_join": {
        "pattern": r"FROM\s+\w+\s*,\s*\w+\s+WHERE",
        "name": "Potential Cartesian join",
        "severity": "critical",
        "description": "JOIN implícito con comas puede causar producto cartesiano",
        "suggestion": "Usar sintaxis explícita: JOIN ... ON",
    },
    "order_by_number": {
        "pattern": r"ORDER\s+BY\s+\d+",
        "name": "ORDER BY column number",
        "severity": "low",
        "description": "ORDER BY número de columna es frágil y difícil de mantener",
        "suggestion": "Usar nombre de columna explícito",
    },
    "null_comparison": {
        "pattern": r"(?:=|!=|<>)\s*NULL",
        "name": "NULL comparison with =",
        "severity": "critical",
        "description": "Comparar con NULL usando = siempre da FALSE",
        "suggestion": "Usar IS NULL o IS NOT NULL",
    },
}

# Índices recomendados por patrón
INDEX_RECOMMENDATIONS = {
    "equality": "CREATE INDEX idx_{table}_{column} ON {table}({column});",
    "range": "CREATE INDEX idx_{table}_{column} ON {table}({column});",
    "composite": "CREATE INDEX idx_{table}_{cols} ON {table}({columns});",
    "covering": "CREATE INDEX idx_{table}_covering ON {table}({columns}) INCLUDE ({include});",
    "partial": "CREATE INDEX idx_{table}_{column}_partial ON {table}({column}) WHERE {condition};",
}


def analyze_query(query: str) -> SQLAnalysis:
    """Analiza un query SQL y detecta problemas."""
    # Normalizar query
    query_upper = query.upper().strip()
    query_normalized = re.sub(r"\s+", " ", query_upper)

    issues = []
    score = 100

    # Detectar anti-patterns
    for _key, pattern_info in SQL_ANTIPATTERNS.items():
        if re.search(pattern_info["pattern"], query_normalized, re.IGNORECASE):
            severity = pattern_info["severity"]
            penalty = {"critical": 25, "high": 15, "medium": 10, "low": 5}[severity]
            score -= penalty

            issues.append(
                SQLIssue(
                    name=pattern_info["name"],
                    severity=severity,
                    line=1,
                    description=pattern_info["description"],
                    suggestion=pattern_info["suggestion"],
                    original=query[:100] + "..." if len(query) > 100 else query,
                )
            )

    # Estimar complejidad
    join_count = len(re.findall(r"\bJOIN\b", query_upper))
    subquery_count = len(re.findall(r"\(\s*SELECT", query_upper))

    if join_count > 5 or subquery_count > 2:
        complexity = "complex"
    elif join_count > 2 or subquery_count > 0:
        complexity = "moderate"
    else:
        complexity = "simple"

    # Recomendaciones generales
    recommendations = []

    if "SELECT *" in query_upper:
        recommendations.append("Especificar columnas mejora performance y claridad")

    if join_count > 3:
        recommendations.append("Considerar denormalizar o usar CTEs para queries complejos")

    if "DISTINCT" in query_upper and join_count > 0:
        recommendations.append("Verificar que los JOINs no generan duplicados innecesarios")

    if "ORDER BY" in query_upper and "LIMIT" not in query_upper:
        recommendations.append("Agregar LIMIT cuando se usa ORDER BY para mejor performance")

    # Asegurar score mínimo
    score = max(0, score)

    return SQLAnalysis(
        query=query,
        score=score,
        issues=issues,
        recommendations=recommendations,
        estimated_complexity=complexity,
    )


def suggest_indexes(query: str, table_name: str | None = None) -> list:
    """Sugiere índices basados en el query."""
    suggestions = []
    query_upper = query.upper()

    # Extraer tablas del FROM
    from_match = re.search(r"FROM\s+(\w+)", query_upper)
    table = table_name or (from_match.group(1).lower() if from_match else "table_name")

    # Buscar columnas en WHERE
    where_match = re.search(r"WHERE\s+(.+?)(?:ORDER|GROUP|LIMIT|$)", query_upper, re.DOTALL)
    if where_match:
        where_clause = where_match.group(1)

        # Columnas con =
        eq_cols = re.findall(r"(\w+)\s*=\s*(?:\?|\'[^\']+\'|\d+)", where_clause)
        for col in eq_cols:
            if col.upper() not in ["AND", "OR", "NOT"]:
                suggestions.append(
                    {
                        "type": "equality",
                        "column": col.lower(),
                        "sql": INDEX_RECOMMENDATIONS["equality"].format(
                            table=table, column=col.lower()
                        ),
                        "reason": f"Columna {col} usada en comparación de igualdad",
                    }
                )

        # Columnas con rango
        range_cols = re.findall(r"(\w+)\s*(?:>|<|>=|<=|BETWEEN)", where_clause)
        for col in range_cols:
            if col.upper() not in ["AND", "OR", "NOT"]:
                suggestions.append(
                    {
                        "type": "range",
                        "column": col.lower(),
                        "sql": INDEX_RECOMMENDATIONS["range"].format(
                            table=table, column=col.lower()
                        ),
                        "reason": f"Columna {col} usada en comparación de rango",
                    }
                )

    # Buscar columnas en ORDER BY
    order_match = re.search(r"ORDER\s+BY\s+(\w+)", query_upper)
    if order_match:
        col = order_match.group(1).lower()
        suggestions.append(
            {
                "type": "ordering",
                "column": col,
                "sql": f"CREATE INDEX idx_{table}_{col} ON {table}({col});",
                "reason": f"Columna {col} usada en ORDER BY",
            }
        )

    # Buscar columnas en JOIN
    join_matches = re.findall(r"JOIN\s+(\w+)\s+\w*\s*ON\s+\w+\.(\w+)\s*=", query_upper)
    for join_table, join_col in join_matches:
        suggestions.append(
            {
                "type": "join",
                "table": join_table.lower(),
                "column": join_col.lower(),
                "sql": f"CREATE INDEX idx_{join_table.lower()}_{join_col.lower()} ON {join_table.lower()}({join_col.lower()});",
                "reason": f"Columna {join_col} usada en JOIN condition",
            }
        )

    return suggestions


def rewrite_query(query: str) -> str | None:
    """Intenta reescribir el query con mejoras."""
    improved = query

    # Reemplazar SELECT * con placeholder
    if re.search(r"SELECT\s+\*", improved, re.IGNORECASE):
        improved = re.sub(
            r"SELECT\s+\*", "SELECT /* TODO: specify columns */ *", improved, flags=re.IGNORECASE
        )

    # Agregar LIMIT si no existe
    if not re.search(r"\bLIMIT\b", improved, re.IGNORECASE):
        improved = improved.rstrip(";") + "\nLIMIT 1000;"

    # Reemplazar NOT IN con NOT EXISTS
    not_in_match = re.search(
        r"(\w+)\s+NOT\s+IN\s*\(\s*SELECT\s+(\w+)\s+FROM\s+(\w+)", improved, re.IGNORECASE
    )
    if not_in_match:
        col, subquery_col, subquery_table = not_in_match.groups()
        improved += f"""

-- Alternativa con NOT EXISTS (mejor performance):
-- WHERE NOT EXISTS (
--     SELECT 1 FROM {subquery_table}
--     WHERE {subquery_table}.{subquery_col} = outer_table.{col}
-- )"""

    return improved if improved != query else None


def analyze_file(file_path: Path) -> list:
    """Analiza un archivo SQL con múltiples queries."""
    content = file_path.read_text(encoding="utf-8")

    # Separar queries por ;
    queries = [q.strip() for q in content.split(";") if q.strip()]

    results = []
    for i, query in enumerate(queries, 1):
        if query.upper().startswith(("SELECT", "INSERT", "UPDATE", "DELETE")):
            analysis = analyze_query(query)
            results.append({"query_number": i, "analysis": analysis})

    return results


def print_analysis(analysis: SQLAnalysis):
    """Imprime el análisis de forma legible."""
    score_icon = "🟢" if analysis.score >= 80 else "🟡" if analysis.score >= 60 else "🔴"

    print(f"\n{'=' * 60}")
    print(" SQL ANALYSIS")
    print(f"{'=' * 60}")
    print(f"\n{score_icon} Score: {analysis.score}/100")
    print(f"📊 Complejidad: {analysis.estimated_complexity}")

    if analysis.issues:
        print(f"\n⚠️  Problemas detectados ({len(analysis.issues)}):")
        for issue in analysis.issues:
            severity_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}[
                issue.severity
            ]
            print(f"\n   {severity_icon} [{issue.severity.upper()}] {issue.name}")
            print(f"      {issue.description}")
            print(f"      💡 {issue.suggestion}")

    if analysis.recommendations:
        print("\n📝 Recomendaciones:")
        for rec in analysis.recommendations:
            print(f"   • {rec}")


def print_antipatterns():
    """Lista todos los anti-patterns detectados."""
    print(f"\n{'=' * 60}")
    print(" SQL ANTI-PATTERNS DETECTADOS")
    print(f"{'=' * 60}\n")

    for _key, info in SQL_ANTIPATTERNS.items():
        severity_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}[
            info["severity"]
        ]
        print(f"{severity_icon} {info['name']} [{info['severity']}]")
        print(f"   {info['description']}")
        print(f"   💡 {info['suggestion']}\n")


def main():
    parser = argparse.ArgumentParser(
        description="SQL Optimization Skill - Analiza y optimiza queries SQL"
    )

    subparsers = parser.add_subparsers(dest="command", help="Comando")

    # analyze
    analyze_parser = subparsers.add_parser("analyze", help="Analiza un query SQL")
    analyze_parser.add_argument("query", nargs="?", help="Query SQL o archivo .sql")

    # check-antipatterns
    check_parser = subparsers.add_parser("check-antipatterns", help="Verifica anti-patterns")
    check_parser.add_argument("file", help="Archivo SQL a verificar")

    # suggest-indexes
    idx_parser = subparsers.add_parser("suggest-indexes", help="Sugiere índices")
    idx_parser.add_argument("query", help="Query SQL o archivo")
    idx_parser.add_argument("--table", "-t", help="Nombre de tabla principal")

    # rewrite
    rewrite_parser = subparsers.add_parser("rewrite", help="Reescribe query optimizado")
    rewrite_parser.add_argument("query", help="Query SQL")

    # list-antipatterns
    subparsers.add_parser("list-antipatterns", help="Lista anti-patterns")

    # Común
    parser.add_argument("--json", action="store_true", help="Output JSON")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    if args.command == "analyze":
        query = args.query

        # Leer desde stdin si no hay argumento
        if not query:
            print("Ingresa el query SQL (termina con Ctrl+D):")
            query = sys.stdin.read()

        # Si es un archivo, leerlo
        if query and Path(query).exists():
            query = Path(query).read_text(encoding="utf-8")

        analysis = analyze_query(query)

        if args.json:
            print(
                json.dumps(
                    {
                        "score": analysis.score,
                        "complexity": analysis.estimated_complexity,
                        "issues": [
                            {
                                "name": i.name,
                                "severity": i.severity,
                                "description": i.description,
                                "suggestion": i.suggestion,
                            }
                            for i in analysis.issues
                        ],
                        "recommendations": analysis.recommendations,
                    },
                    indent=2,
                )
            )
        else:
            print_analysis(analysis)

    elif args.command == "check-antipatterns":
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"Error: Archivo '{args.file}' no encontrado")
            return 1

        results = analyze_file(file_path)

        if args.json:
            print(
                json.dumps(
                    [
                        {
                            "query_number": r["query_number"],
                            "score": r["analysis"].score,
                            "issues_count": len(r["analysis"].issues),
                        }
                        for r in results
                    ],
                    indent=2,
                )
            )
        else:
            print(f"\n🔍 Análisis de {file_path}")
            print(f"   Queries analizados: {len(results)}")

            total_issues = sum(len(r["analysis"].issues) for r in results)
            print(f"   Total de problemas: {total_issues}")

            for r in results:
                if r["analysis"].issues:
                    print(f"\n--- Query #{r['query_number']} ---")
                    print_analysis(r["analysis"])

    elif args.command == "suggest-indexes":
        query = args.query

        if Path(query).exists():
            query = Path(query).read_text(encoding="utf-8")

        suggestions = suggest_indexes(query, args.table)

        if args.json:
            print(json.dumps(suggestions, indent=2))
        else:
            print(f"\n{'=' * 60}")
            print(" ÍNDICES SUGERIDOS")
            print(f"{'=' * 60}\n")

            if suggestions:
                for s in suggestions:
                    print(f"📊 Tipo: {s['type']}")
                    print(f"   Razón: {s['reason']}")
                    print(f"   SQL: {s['sql']}\n")
            else:
                print("No se encontraron sugerencias de índices")

    elif args.command == "rewrite":
        query = args.query

        if Path(query).exists():
            query = Path(query).read_text(encoding="utf-8")

        improved = rewrite_query(query)

        if improved:
            if args.json:
                print(json.dumps({"original": query, "improved": improved}, indent=2))
            else:
                print("\n--- Query Original ---")
                print(query)
                print("\n--- Query Mejorado ---")
                print(improved)
        else:
            print("No se encontraron mejoras automáticas")

    elif args.command == "list-antipatterns":
        if args.json:
            print(
                json.dumps(
                    {
                        key: {
                            "name": info["name"],
                            "severity": info["severity"],
                            "description": info["description"],
                            "suggestion": info["suggestion"],
                        }
                        for key, info in SQL_ANTIPATTERNS.items()
                    },
                    indent=2,
                )
            )
        else:
            print_antipatterns()

    return 0


if __name__ == "__main__":
    sys.exit(main())
