#!/usr/bin/env python3
"""
Refactoring Playbook - Herramientas de Refactoring
Ejemplos y utilidades para técnicas de refactoring.
"""

import logging
import re
import ast
from dataclasses import dataclass
from enum import Enum

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# =============================================================================
# CODE SMELLS DETECTOR
# =============================================================================


class CodeSmell(Enum):
    LONG_METHOD = "Long Method"
    LARGE_CLASS = "Large Class"
    LONG_PARAMETER_LIST = "Long Parameter List"
    DUPLICATE_CODE = "Duplicate Code"
    DEAD_CODE = "Dead Code"
    FEATURE_ENVY = "Feature Envy"
    DATA_CLUMPS = "Data Clumps"
    PRIMITIVE_OBSESSION = "Primitive Obsession"
    SWITCH_STATEMENTS = "Switch Statements"
    COMMENTS = "Comments (as deodorant)"


@dataclass
class SmellDetection:
    """Detección de code smell."""

    smell: CodeSmell
    location: str
    line: int
    description: str
    suggested_refactoring: str


class CodeSmellDetector:
    """Detector de code smells en Python."""

    # Configuración de umbrales
    MAX_METHOD_LINES = 20
    MAX_CLASS_LINES = 200
    MAX_PARAMS = 4
    MAX_NESTING = 3

    def detect(self, code: str) -> list[SmellDetection]:
        """Detecta code smells en el código."""
        detections: list[SmellDetection] = []

        try:
            tree = ast.parse(code)
            lines = code.split("\n")

            self._detect_long_methods(tree, lines, detections)
            self._detect_large_classes(tree, lines, detections)
            self._detect_long_param_lists(tree, detections)
            self._detect_deep_nesting(tree, detections)
            self._detect_switch_statements(tree, detections)
            self._detect_comment_smell(lines, detections)

        except SyntaxError as e:
            logger.error(f"Syntax error: {e}")

        return detections

    def _detect_long_methods(
        self, tree: ast.AST, lines: list[str], detections: list[SmellDetection]
    ) -> None:
        """Detecta métodos largos."""
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                start = node.lineno
                end = node.end_lineno or start
                length = end - start + 1

                if length > self.MAX_METHOD_LINES:
                    detections.append(
                        SmellDetection(
                            smell=CodeSmell.LONG_METHOD,
                            location=node.name,
                            line=start,
                            description=f"Method has {length} lines (max: {self.MAX_METHOD_LINES})",
                            suggested_refactoring="Extract Method: Split into smaller, focused methods",
                        )
                    )

    def _detect_large_classes(
        self, tree: ast.AST, lines: list[str], detections: list[SmellDetection]
    ) -> None:
        """Detecta clases grandes."""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                start = node.lineno
                end = node.end_lineno or start
                length = end - start + 1

                if length > self.MAX_CLASS_LINES:
                    detections.append(
                        SmellDetection(
                            smell=CodeSmell.LARGE_CLASS,
                            location=node.name,
                            line=start,
                            description=f"Class has {length} lines (max: {self.MAX_CLASS_LINES})",
                            suggested_refactoring="Extract Class: Split by responsibility",
                        )
                    )

    def _detect_long_param_lists(self, tree: ast.AST, detections: list[SmellDetection]) -> None:
        """Detecta listas de parámetros largas."""
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                params = [p for p in node.args.args if p.arg not in ("self", "cls")]
                if len(params) > self.MAX_PARAMS:
                    detections.append(
                        SmellDetection(
                            smell=CodeSmell.LONG_PARAMETER_LIST,
                            location=node.name,
                            line=node.lineno,
                            description=f"Method has {len(params)} parameters (max: {self.MAX_PARAMS})",
                            suggested_refactoring="Introduce Parameter Object or use Builder pattern",
                        )
                    )

    def _detect_deep_nesting(self, tree: ast.AST, detections: list[SmellDetection]) -> None:
        """Detecta anidamiento profundo."""

        def get_max_depth(node: ast.AST, current_depth: int = 0) -> int:
            max_depth = current_depth
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
                    child_depth = get_max_depth(child, current_depth + 1)
                    max_depth = max(max_depth, child_depth)
                else:
                    child_depth = get_max_depth(child, current_depth)
                    max_depth = max(max_depth, child_depth)
            return max_depth

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                depth = get_max_depth(node)
                if depth > self.MAX_NESTING:
                    detections.append(
                        SmellDetection(
                            smell=CodeSmell.LONG_METHOD,
                            location=node.name,
                            line=node.lineno,
                            description=f"Nesting depth is {depth} (max: {self.MAX_NESTING})",
                            suggested_refactoring="Replace Nested Conditional with Guard Clauses",
                        )
                    )

    def _detect_switch_statements(self, tree: ast.AST, detections: list[SmellDetection]) -> None:
        """Detecta switch statements (if-elif chains)."""
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                elif_count = 0
                current = node
                while hasattr(current, "orelse") and current.orelse:
                    if len(current.orelse) == 1 and isinstance(current.orelse[0], ast.If):
                        elif_count += 1
                        current = current.orelse[0]
                    else:
                        break

                if elif_count >= 3:
                    detections.append(
                        SmellDetection(
                            smell=CodeSmell.SWITCH_STATEMENTS,
                            location="if-elif chain",
                            line=node.lineno,
                            description=f"Long if-elif chain with {elif_count + 1} branches",
                            suggested_refactoring="Replace Conditional with Polymorphism or Strategy pattern",
                        )
                    )

    def _detect_comment_smell(self, lines: list[str], detections: list[SmellDetection]) -> None:
        """Detecta comentarios que indican código confuso."""
        smell_patterns = [
            r"#\s*TODO:?\s*fix",
            r"#\s*HACK",
            r"#\s*FIXME",
            r"#\s*XXX",
            r"#\s*WARNING",
            r"#\s*This is\s+(confusing|tricky|complex)",
        ]

        for i, line in enumerate(lines, 1):
            for pattern in smell_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    detections.append(
                        SmellDetection(
                            smell=CodeSmell.COMMENTS,
                            location="Comment",
                            line=i,
                            description="Comment suggests code needs refactoring",
                            suggested_refactoring="Refactor the code so the comment becomes unnecessary",
                        )
                    )
                    break


# =============================================================================
# REFACTORING CATALOG
# =============================================================================


@dataclass
class RefactoringTechnique:
    """Descripción de una técnica de refactoring."""

    name: str
    category: str
    when_to_use: str
    steps: list[str]
    example_before: str
    example_after: str


class RefactoringCatalog:
    """Catálogo de técnicas de refactoring."""

    TECHNIQUES = [
        RefactoringTechnique(
            name="Extract Method",
            category="Composing Methods",
            when_to_use="When you have a code fragment that can be grouped together",
            steps=[
                "1. Create a new method with a name that explains what it does",
                "2. Copy the extracted code to the new method",
                "3. Replace the original code with a call to the new method",
                "4. Look for variables: pass as parameters or extract further",
            ],
            example_before="""def print_invoice(invoice):
    print("Invoice Details")
    print("-" * 40)
    # Print header
    print(f"Invoice #: {invoice.number}")
    print(f"Date: {invoice.date}")
    print(f"Customer: {invoice.customer}")
    # Print items
    for item in invoice.items:
        print(f"  {item.name}: ${item.price}")
    # Print total
    print("-" * 40)
    print(f"Total: ${invoice.total}")""",
            example_after="""def print_invoice(invoice):
    print_header(invoice)
    print_items(invoice.items)
    print_total(invoice.total)

def print_header(invoice):
    print("Invoice Details")
    print("-" * 40)
    print(f"Invoice #: {invoice.number}")
    print(f"Date: {invoice.date}")
    print(f"Customer: {invoice.customer}")

def print_items(items):
    for item in items:
        print(f"  {item.name}: ${item.price}")

def print_total(total):
    print("-" * 40)
    print(f"Total: ${total}")""",
        ),
        RefactoringTechnique(
            name="Replace Conditional with Polymorphism",
            category="Simplifying Conditional Expressions",
            when_to_use="When you have a conditional that chooses different behavior based on type",
            steps=[
                "1. Create subclasses for each leg of the conditional",
                "2. Create a polymorphic method in the superclass",
                "3. Override the method in each subclass with appropriate behavior",
                "4. Replace the conditional with a call to the polymorphic method",
            ],
            example_before="""def calculate_shipping(order):
    if order.shipping_type == "standard":
        return order.weight * 1.5
    elif order.shipping_type == "express":
        return order.weight * 3.0 + 5.0
    elif order.shipping_type == "overnight":
        return order.weight * 5.0 + 15.0
    else:
        raise ValueError("Unknown shipping type")""",
            example_after="""from abc import ABC, abstractmethod

class ShippingStrategy(ABC):
    @abstractmethod
    def calculate(self, weight: float) -> float:
        pass

class StandardShipping(ShippingStrategy):
    def calculate(self, weight: float) -> float:
        return weight * 1.5

class ExpressShipping(ShippingStrategy):
    def calculate(self, weight: float) -> float:
        return weight * 3.0 + 5.0

class OvernightShipping(ShippingStrategy):
    def calculate(self, weight: float) -> float:
        return weight * 5.0 + 15.0

def calculate_shipping(order):
    return order.shipping_strategy.calculate(order.weight)""",
        ),
        RefactoringTechnique(
            name="Introduce Parameter Object",
            category="Making Method Calls Simpler",
            when_to_use="When you have a group of parameters that naturally go together",
            steps=[
                "1. Create a new class to hold the parameter group",
                "2. Add the new object as a parameter",
                "3. For each parameter in the group, add it to the object",
                "4. Remove the old parameters one by one",
            ],
            example_before="""def create_appointment(
    start_date,
    start_time,
    end_date,
    end_time,
    title,
    location
):
    # ...

def is_available(
    start_date,
    start_time,
    end_date,
    end_time
):
    # ...""",
            example_after="""@dataclass
class DateTimeRange:
    start_date: date
    start_time: time
    end_date: date
    end_time: time

def create_appointment(
    time_range: DateTimeRange,
    title: str,
    location: str
):
    # ...

def is_available(time_range: DateTimeRange) -> bool:
    # ...""",
        ),
        RefactoringTechnique(
            name="Replace Temp with Query",
            category="Composing Methods",
            when_to_use="When you have a temporary variable that holds the result of an expression",
            steps=[
                "1. Extract the right-hand side of the assignment into a method",
                "2. Replace all references to the temp with calls to the new method",
                "3. Remove the temp declaration and assignment",
            ],
            example_before="""def get_price(quantity):
    base_price = quantity * item_price
    if base_price > 1000:
        return base_price * 0.95
    else:
        return base_price * 0.98""",
            example_after="""def get_price(quantity):
    if base_price(quantity) > 1000:
        return base_price(quantity) * 0.95
    else:
        return base_price(quantity) * 0.98

def base_price(quantity):
    return quantity * item_price""",
        ),
    ]

    @classmethod
    def get_all(cls) -> list[RefactoringTechnique]:
        """Obtiene todas las técnicas."""
        return cls.TECHNIQUES

    @classmethod
    def get_by_category(cls, category: str) -> list[RefactoringTechnique]:
        """Obtiene técnicas por categoría."""
        return [t for t in cls.TECHNIQUES if t.category == category]

    @classmethod
    def suggest_for_smell(cls, smell: CodeSmell) -> list[RefactoringTechnique]:
        """Sugiere refactorings para un code smell."""
        smell_to_technique = {
            CodeSmell.LONG_METHOD: ["Extract Method"],
            CodeSmell.LONG_PARAMETER_LIST: ["Introduce Parameter Object"],
            CodeSmell.SWITCH_STATEMENTS: ["Replace Conditional with Polymorphism"],
        }
        technique_names = smell_to_technique.get(smell, [])
        return [t for t in cls.TECHNIQUES if t.name in technique_names]


# =============================================================================
# DEMO
# =============================================================================

SAMPLE_CODE = """
class OrderProcessor:
    def process_order(self, order_id, customer_name, customer_email, customer_phone,
                      item_name, item_price, item_quantity, shipping_address,
                      billing_address, payment_method, discount_code):
        # SMELL: este código necesita refactoring
        # This is confusing but it works
        if payment_method == "credit_card":
            # Process credit card
            print("Processing credit card...")
            if discount_code:
                if discount_code == "SAVE10":
                    price = item_price * 0.9
                elif discount_code == "SAVE20":
                    price = item_price * 0.8
                elif discount_code == "SAVE30":
                    price = item_price * 0.7
                else:
                    price = item_price
            else:
                price = item_price
        elif payment_method == "paypal":
            # Process paypal
            print("Processing paypal...")
            if discount_code:
                if discount_code == "SAVE10":
                    price = item_price * 0.9
                elif discount_code == "SAVE20":
                    price = item_price * 0.8
                elif discount_code == "SAVE30":
                    price = item_price * 0.7
                else:
                    price = item_price
            else:
                price = item_price
        elif payment_method == "bank_transfer":
            # Process bank transfer
            print("Processing bank transfer...")
            price = item_price
        else:
            raise ValueError("Unknown payment method")

        total = price * item_quantity
        print(f"Order total: {total}")
        return total
"""


def main() -> None:
    """Demostración de herramientas de refactoring."""
    print("\n" + "=" * 60)
    print("REFACTORING PLAYBOOK - Demo")
    print("=" * 60)

    # Detectar code smells
    print("\n--- CODE SMELL DETECTION ---")
    detector = CodeSmellDetector()
    detections = detector.detect(SAMPLE_CODE)

    for d in detections:
        print(f"\n[{d.smell.value}] at {d.location}:{d.line}")
        print(f"  {d.description}")
        print(f"  Suggestion: {d.suggested_refactoring}")

    # Mostrar técnicas sugeridas
    print("\n--- SUGGESTED REFACTORINGS ---")
    seen_techniques = set()
    for d in detections:
        techniques = RefactoringCatalog.suggest_for_smell(d.smell)
        for t in techniques:
            if t.name not in seen_techniques:
                seen_techniques.add(t.name)
                print(f"\n{t.name} ({t.category})")
                print(f"  When to use: {t.when_to_use}")
                print("  Steps:")
                for step in t.steps:
                    print(f"    {step}")

    # Mostrar catálogo completo
    print("\n--- REFACTORING CATALOG ---")
    for technique in RefactoringCatalog.get_all():
        print(f"\n{technique.name}")
        print(f"  Category: {technique.category}")
        print(f"  When to use: {technique.when_to_use}")

    print("\n" + "=" * 60)
    print("Refactoring analysis complete")
    print("=" * 60)


if __name__ == "__main__":
    main()
