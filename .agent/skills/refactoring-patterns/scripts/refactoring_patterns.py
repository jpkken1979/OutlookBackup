#!/usr/bin/env python3
"""
Refactoring Patterns Skill

Detecta code smells y sugiere refactorizaciones siguiendo patrones de Martin Fowler.
"""

import argparse
import ast
import json
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CodeSmell:
    """Representa un code smell detectado."""

    name: str
    severity: str  # low, medium, high, critical
    location: str
    line: int
    description: str
    suggestion: str
    pattern: str  # Patrón de refactorización recomendado


@dataclass
class RefactoringPattern:
    """Patrón de refactorización."""

    name: str
    category: str
    description: str
    when_to_use: str
    steps: list
    example_before: str
    example_after: str


# Catálogo de patrones de Martin Fowler
REFACTORING_PATTERNS = {
    "extract-method": RefactoringPattern(
        name="Extract Method",
        category="Composing Methods",
        description="Extrae un fragmento de código en un método separado",
        when_to_use="Cuando tienes un fragmento de código que puede agruparse",
        steps=[
            "1. Crear nuevo método con nombre descriptivo",
            "2. Copiar código extraído al nuevo método",
            "3. Identificar variables locales usadas",
            "4. Pasar variables como parámetros si necesario",
            "5. Reemplazar código original con llamada al método",
        ],
        example_before="""def print_invoice(invoice):
    print("*" * 40)
    print("INVOICE")
    print("*" * 40)

    total = 0
    for item in invoice.items:
        total += item.price * item.quantity

    print(f"Total: {total}")""",
        example_after="""def print_invoice(invoice):
    print_header()
    total = calculate_total(invoice.items)
    print(f"Total: {total}")

def print_header():
    print("*" * 40)
    print("INVOICE")
    print("*" * 40)

def calculate_total(items):
    return sum(item.price * item.quantity for item in items)""",
    ),
    "extract-variable": RefactoringPattern(
        name="Extract Variable",
        category="Composing Methods",
        description="Extrae una expresión compleja en una variable con nombre significativo",
        when_to_use="Cuando una expresión es difícil de entender",
        steps=[
            "1. Declarar variable inmutable con nombre descriptivo",
            "2. Asignar la expresión a la variable",
            "3. Reemplazar expresión original con la variable",
        ],
        example_before="""if order.quantity * order.price - order.discount > 1000:
    apply_premium_shipping(order)""",
        example_after="""order_total = order.quantity * order.price - order.discount
if order_total > 1000:
    apply_premium_shipping(order)""",
    ),
    "inline-method": RefactoringPattern(
        name="Inline Method",
        category="Composing Methods",
        description="Reemplaza una llamada a método con el cuerpo del método",
        when_to_use="Cuando el cuerpo del método es tan claro como su nombre",
        steps=[
            "1. Verificar que el método no es polimórfico",
            "2. Encontrar todas las llamadas al método",
            "3. Reemplazar cada llamada con el cuerpo",
            "4. Eliminar el método",
        ],
        example_before="""def get_rating():
    return 2 if more_than_five_late_deliveries() else 1

def more_than_five_late_deliveries():
    return self.late_deliveries > 5""",
        example_after="""def get_rating():
    return 2 if self.late_deliveries > 5 else 1""",
    ),
    "rename-variable": RefactoringPattern(
        name="Rename Variable",
        category="Simplifying Names",
        description="Cambia el nombre de una variable para mejor claridad",
        when_to_use="Cuando el nombre no comunica la intención",
        steps=[
            "1. Verificar que no hay conflictos de nombre",
            "2. Renombrar todas las referencias",
            "3. Ejecutar tests",
        ],
        example_before="""def calc(x, y, z):
    return x * y - z""",
        example_after="""def calculate_total(price, quantity, discount):
    return price * quantity - discount""",
    ),
    "replace-temp-with-query": RefactoringPattern(
        name="Replace Temp with Query",
        category="Composing Methods",
        description="Reemplaza variable temporal con llamada a método",
        when_to_use="Cuando una variable temporal se usa para almacenar un cálculo",
        steps=[
            "1. Extraer la expresión a un método",
            "2. Reemplazar referencias a la variable con llamadas al método",
            "3. Eliminar la declaración de la variable",
        ],
        example_before="""base_price = quantity * item_price
if base_price > 1000:
    return base_price * 0.95""",
        example_after="""if base_price() > 1000:
    return base_price() * 0.95

def base_price():
    return quantity * item_price""",
    ),
    "introduce-parameter-object": RefactoringPattern(
        name="Introduce Parameter Object",
        category="Simplifying Method Calls",
        description="Agrupa parámetros relacionados en un objeto",
        when_to_use="Cuando varios métodos usan el mismo grupo de parámetros",
        steps=[
            "1. Crear clase para agrupar parámetros",
            "2. Modificar método para aceptar el objeto",
            "3. Actualizar todas las llamadas",
        ],
        example_before="""def amount_invoiced(start_date, end_date):
    pass

def amount_received(start_date, end_date):
    pass""",
        example_after="""@dataclass
class DateRange:
    start: date
    end: date

def amount_invoiced(date_range: DateRange):
    pass

def amount_received(date_range: DateRange):
    pass""",
    ),
    "replace-conditional-with-polymorphism": RefactoringPattern(
        name="Replace Conditional with Polymorphism",
        category="Simplifying Conditional Logic",
        description="Reemplaza condicionales con polimorfismo de clases",
        when_to_use="Cuando tienes switch/if que varía según tipo",
        steps=[
            "1. Crear clase base o protocolo",
            "2. Crear subclase para cada caso",
            "3. Mover lógica de cada caso a su subclase",
            "4. Eliminar el condicional",
        ],
        example_before="""def calculate_area(shape):
    if shape.type == "circle":
        return 3.14 * shape.radius ** 2
    elif shape.type == "rectangle":
        return shape.width * shape.height""",
        example_after="""class Shape:
    def area(self): pass

class Circle(Shape):
    def area(self):
        return 3.14 * self.radius ** 2

class Rectangle(Shape):
    def area(self):
        return self.width * self.height""",
    ),
    "decompose-conditional": RefactoringPattern(
        name="Decompose Conditional",
        category="Simplifying Conditional Logic",
        description="Extrae condición y branches a métodos separados",
        when_to_use="Cuando tienes un condicional complejo",
        steps=[
            "1. Extraer condición a método con nombre descriptivo",
            "2. Extraer branch 'then' a método",
            "3. Extraer branch 'else' a método",
        ],
        example_before="""if date < SUMMER_START or date > SUMMER_END:
    charge = quantity * winter_rate + winter_service_charge
else:
    charge = quantity * summer_rate""",
        example_after="""if is_summer(date):
    charge = summer_charge(quantity)
else:
    charge = winter_charge(quantity)""",
    ),
}


class PythonCodeAnalyzer(ast.NodeVisitor):
    """Analizador de código Python para detectar code smells."""

    def __init__(self, source: str, filename: str = "<unknown>"):
        self.source = source
        self.filename = filename
        self.smells: list[CodeSmell] = []
        self.lines = source.split("\n")

    def analyze(self) -> list[CodeSmell]:
        """Ejecuta el análisis completo."""
        try:
            tree = ast.parse(self.source)
            self.visit(tree)
        except SyntaxError as e:
            self.smells.append(
                CodeSmell(
                    name="Syntax Error",
                    severity="critical",
                    location=self.filename,
                    line=e.lineno or 0,
                    description=f"Error de sintaxis: {e.msg}",
                    suggestion="Corregir el error de sintaxis",
                    pattern="N/A",
                )
            )
        return self.smells

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Analiza definiciones de funciones."""
        # Long Method (>20 líneas)
        func_lines = node.end_lineno - node.lineno + 1 if node.end_lineno else 0
        if func_lines > 20:
            self.smells.append(
                CodeSmell(
                    name="Long Method",
                    severity="medium" if func_lines < 50 else "high",
                    location=self.filename,
                    line=node.lineno,
                    description=f"Método '{node.name}' tiene {func_lines} líneas (máx recomendado: 20)",
                    suggestion="Extraer partes del método en funciones más pequeñas",
                    pattern="extract-method",
                )
            )

        # Long Parameter List (>4 parámetros)
        param_count = len(node.args.args)
        if param_count > 4:
            self.smells.append(
                CodeSmell(
                    name="Long Parameter List",
                    severity="medium",
                    location=self.filename,
                    line=node.lineno,
                    description=f"Método '{node.name}' tiene {param_count} parámetros (máx recomendado: 4)",
                    suggestion="Agrupar parámetros relacionados en un objeto",
                    pattern="introduce-parameter-object",
                )
            )

        # Single letter parameter names
        for arg in node.args.args:
            if len(arg.arg) == 1 and arg.arg not in ["_", "x", "y", "z", "i", "j", "k"]:
                self.smells.append(
                    CodeSmell(
                        name="Unclear Parameter Name",
                        severity="low",
                        location=self.filename,
                        line=node.lineno,
                        description=f"Parámetro '{arg.arg}' no es descriptivo",
                        suggestion="Usar nombre descriptivo para el parámetro",
                        pattern="rename-variable",
                    )
                )

        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        """Analiza definiciones de clases."""
        # Large Class (>300 líneas)
        class_lines = node.end_lineno - node.lineno + 1 if node.end_lineno else 0
        if class_lines > 300:
            self.smells.append(
                CodeSmell(
                    name="Large Class",
                    severity="high",
                    location=self.filename,
                    line=node.lineno,
                    description=f"Clase '{node.name}' tiene {class_lines} líneas (máx recomendado: 300)",
                    suggestion="Dividir la clase en clases más pequeñas con responsabilidades claras",
                    pattern="extract-class",
                )
            )

        # Count methods
        methods = [n for n in node.body if isinstance(n, ast.FunctionDef)]
        if len(methods) > 20:
            self.smells.append(
                CodeSmell(
                    name="Too Many Methods",
                    severity="medium",
                    location=self.filename,
                    line=node.lineno,
                    description=f"Clase '{node.name}' tiene {len(methods)} métodos",
                    suggestion="Considerar dividir la clase",
                    pattern="extract-class",
                )
            )

        self.generic_visit(node)

    def visit_If(self, node: ast.If):
        """Analiza condicionales."""
        # Nested conditionals (>3 niveles)
        depth = self._get_nesting_depth(node)
        if depth > 3:
            self.smells.append(
                CodeSmell(
                    name="Deep Nesting",
                    severity="medium",
                    location=self.filename,
                    line=node.lineno,
                    description=f"Condicional con {depth} niveles de anidación",
                    suggestion="Extraer condiciones a métodos o usar early returns",
                    pattern="decompose-conditional",
                )
            )

        # Complex condition
        if isinstance(node.test, ast.BoolOp) and len(node.test.values) > 3:
            self.smells.append(
                CodeSmell(
                    name="Complex Conditional",
                    severity="medium",
                    location=self.filename,
                    line=node.lineno,
                    description="Condición con múltiples operadores booleanos",
                    suggestion="Extraer la condición a un método con nombre descriptivo",
                    pattern="decompose-conditional",
                )
            )

        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare):
        """Detecta magic numbers."""
        for comparator in node.comparators:
            if isinstance(comparator, ast.Constant):
                if isinstance(comparator.value, (int, float)):
                    if comparator.value not in [0, 1, -1, 2, 100]:
                        self.smells.append(
                            CodeSmell(
                                name="Magic Number",
                                severity="low",
                                location=self.filename,
                                line=node.lineno,
                                description=f"Número mágico: {comparator.value}",
                                suggestion="Reemplazar con constante con nombre significativo",
                                pattern="extract-variable",
                            )
                        )

        self.generic_visit(node)

    def _get_nesting_depth(self, node: ast.AST, depth: int = 1) -> int:
        """Calcula profundidad de anidación."""
        max_depth = depth
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.With)):
                child_depth = self._get_nesting_depth(child, depth + 1)
                max_depth = max(max_depth, child_depth)
        return max_depth


def analyze_file(file_path: Path) -> list[CodeSmell]:
    """Analiza un archivo Python."""
    try:
        source = file_path.read_text(encoding="utf-8")
        analyzer = PythonCodeAnalyzer(source, str(file_path))
        return analyzer.analyze()
    except Exception as e:
        return [
            CodeSmell(
                name="Analysis Error",
                severity="critical",
                location=str(file_path),
                line=0,
                description=f"No se pudo analizar: {e}",
                suggestion="Verificar que el archivo es Python válido",
                pattern="N/A",
            )
        ]


def analyze_directory(dir_path: Path) -> dict:
    """Analiza todos los archivos Python en un directorio."""
    results = {
        "total_files": 0,
        "total_smells": 0,
        "by_severity": {"critical": 0, "high": 0, "medium": 0, "low": 0},
        "by_type": {},
        "files": {},
    }

    for py_file in dir_path.rglob("*.py"):
        # Ignorar archivos de test, __pycache__, etc.
        if "__pycache__" in str(py_file) or "test_" in py_file.name:
            continue

        results["total_files"] += 1
        smells = analyze_file(py_file)

        if smells:
            relative_path = str(py_file.relative_to(dir_path))
            results["files"][relative_path] = [
                {
                    "name": s.name,
                    "severity": s.severity,
                    "line": s.line,
                    "description": s.description,
                    "pattern": s.pattern,
                }
                for s in smells
            ]

            for smell in smells:
                results["total_smells"] += 1
                results["by_severity"][smell.severity] += 1
                results["by_type"][smell.name] = results["by_type"].get(smell.name, 0) + 1

    return results


def print_smells(smells: list[CodeSmell]):
    """Imprime code smells de forma legible."""
    severity_colors = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}

    for smell in smells:
        icon = severity_colors.get(smell.severity, "⚪")
        print(f"\n{icon} [{smell.severity.upper()}] {smell.name}")
        print(f"   Ubicación: {smell.location}:{smell.line}")
        print(f"   Descripción: {smell.description}")
        print(f"   Sugerencia: {smell.suggestion}")
        print(f"   Patrón: {smell.pattern}")


def print_pattern(pattern_name: str):
    """Imprime detalles de un patrón de refactorización."""
    pattern = REFACTORING_PATTERNS.get(pattern_name)
    if not pattern:
        print(f"Patrón '{pattern_name}' no encontrado")
        print(f"Patrones disponibles: {', '.join(REFACTORING_PATTERNS.keys())}")
        return

    print(f"\n{'=' * 60}")
    print(f" {pattern.name}")
    print(f"{'=' * 60}")
    print(f"\nCategoría: {pattern.category}")
    print(f"\nDescripción: {pattern.description}")
    print(f"\nCuándo usar: {pattern.when_to_use}")
    print("\nPasos:")
    for step in pattern.steps:
        print(f"  {step}")
    print("\n--- Antes ---")
    print(pattern.example_before)
    print("\n--- Después ---")
    print(pattern.example_after)


def main():
    parser = argparse.ArgumentParser(
        description="Refactoring Patterns Skill - Detecta code smells y sugiere refactorizaciones"
    )

    subparsers = parser.add_subparsers(dest="command", help="Comando")

    # analyze
    analyze_parser = subparsers.add_parser("analyze", help="Analiza código")
    analyze_parser.add_argument("path", help="Archivo o directorio a analizar")

    # detect-smells (alias de analyze)
    detect_parser = subparsers.add_parser("detect-smells", help="Detecta code smells")
    detect_parser.add_argument("path", help="Archivo o directorio")

    # suggest
    suggest_parser = subparsers.add_parser("suggest", help="Sugiere refactorización")
    suggest_parser.add_argument("path", help="Archivo a analizar")
    suggest_parser.add_argument("--pattern", "-p", help="Patrón específico a mostrar")

    # list-patterns
    subparsers.add_parser("list-patterns", help="Lista patrones disponibles")

    # pattern
    pattern_parser = subparsers.add_parser("pattern", help="Muestra detalles de un patrón")
    pattern_parser.add_argument("name", help="Nombre del patrón")

    # Común
    parser.add_argument("--json", action="store_true", help="Output JSON")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    if args.command in ["analyze", "detect-smells"]:
        path = Path(args.path)

        if path.is_file():
            smells = analyze_file(path)
            if args.json:
                print(
                    json.dumps(
                        [
                            {
                                "name": s.name,
                                "severity": s.severity,
                                "location": s.location,
                                "line": s.line,
                                "description": s.description,
                                "suggestion": s.suggestion,
                                "pattern": s.pattern,
                            }
                            for s in smells
                        ],
                        indent=2,
                    )
                )
            else:
                if smells:
                    print(f"\n🔍 Análisis de {path}")
                    print(f"   Encontrados: {len(smells)} code smells")
                    print_smells(smells)
                else:
                    print(f"✅ No se encontraron code smells en {path}")
        elif path.is_dir():
            results = analyze_directory(path)
            if args.json:
                print(json.dumps(results, indent=2))
            else:
                print(f"\n{'=' * 60}")
                print(f" ANÁLISIS DE DIRECTORIO: {path}")
                print(f"{'=' * 60}")
                print(f"\nArchivos analizados: {results['total_files']}")
                print(f"Code smells totales: {results['total_smells']}")
                print("\nPor severidad:")
                for sev, count in results["by_severity"].items():
                    if count > 0:
                        print(f"  {sev}: {count}")
                print("\nPor tipo:")
                for smell_type, count in sorted(results["by_type"].items(), key=lambda x: -x[1]):
                    print(f"  {smell_type}: {count}")
        else:
            print(f"Error: {path} no existe")
            return 1

    elif args.command == "suggest":
        path = Path(args.path)
        if args.pattern:
            print_pattern(args.pattern)
        else:
            smells = analyze_file(path)
            suggested_patterns = {s.pattern for s in smells if s.pattern != "N/A"}
            print(f"\n🔧 Patrones sugeridos para {path}:")
            for pattern_name in suggested_patterns:
                print_pattern(pattern_name)

    elif args.command == "list-patterns":
        if args.json:
            print(
                json.dumps(
                    {
                        name: {"category": p.category, "description": p.description}
                        for name, p in REFACTORING_PATTERNS.items()
                    },
                    indent=2,
                )
            )
        else:
            print(f"\n{'=' * 60}")
            print(" PATRONES DE REFACTORIZACIÓN DISPONIBLES")
            print(f"{'=' * 60}\n")
            for name, pattern in REFACTORING_PATTERNS.items():
                print(f"📘 {name}")
                print(f"   Categoría: {pattern.category}")
                print(f"   {pattern.description}\n")

    elif args.command == "pattern":
        if args.json:
            pattern = REFACTORING_PATTERNS.get(args.name)
            if pattern:
                print(
                    json.dumps(
                        {
                            "name": pattern.name,
                            "category": pattern.category,
                            "description": pattern.description,
                            "when_to_use": pattern.when_to_use,
                            "steps": pattern.steps,
                            "example_before": pattern.example_before,
                            "example_after": pattern.example_after,
                        },
                        indent=2,
                    )
                )
        else:
            print_pattern(args.name)

    return 0


if __name__ == "__main__":
    sys.exit(main())
