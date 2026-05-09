#!/usr/bin/env python3
"""
Design Patterns GoF - Ejemplos Ejecutables
Implementaciones prácticas de los 23 patrones de diseño.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
from collections.abc import Callable, Iterator

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# =============================================================================
# CREATIONAL PATTERNS
# =============================================================================


# --- Singleton ---
class Singleton:
    """Garantiza una única instancia de una clase."""

    _instance: Optional["Singleton"] = None

    def __new__(cls) -> "Singleton":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self.data: dict = {}
        logger.info("Singleton inicializado")


# --- Factory Method ---
class Document(ABC):
    """Producto abstracto."""

    @abstractmethod
    def render(self) -> str:
        pass


class PDFDocument(Document):
    def render(self) -> str:
        return "Rendering PDF document"


class HTMLDocument(Document):
    def render(self) -> str:
        return "Rendering HTML document"


class DocumentFactory:
    """Factory Method para crear documentos."""

    @staticmethod
    def create(doc_type: str) -> Document:
        factories = {
            "pdf": PDFDocument,
            "html": HTMLDocument,
        }
        if doc_type not in factories:
            raise ValueError(f"Unknown document type: {doc_type}")
        return factories[doc_type]()


# --- Builder ---
@dataclass
class Email:
    """Producto complejo construido paso a paso."""

    sender: str = ""
    recipient: str = ""
    subject: str = ""
    body: str = ""
    attachments: list = field(default_factory=list)


class EmailBuilder:
    """Builder para construir emails complejos."""

    def __init__(self) -> None:
        self._email = Email()

    def from_address(self, sender: str) -> "EmailBuilder":
        self._email.sender = sender
        return self

    def to_address(self, recipient: str) -> "EmailBuilder":
        self._email.recipient = recipient
        return self

    def with_subject(self, subject: str) -> "EmailBuilder":
        self._email.subject = subject
        return self

    def with_body(self, body: str) -> "EmailBuilder":
        self._email.body = body
        return self

    def attach(self, filename: str) -> "EmailBuilder":
        self._email.attachments.append(filename)
        return self

    def build(self) -> Email:
        return self._email


# =============================================================================
# STRUCTURAL PATTERNS
# =============================================================================


# --- Adapter ---
class LegacyPrinter:
    """Sistema legacy con interfaz incompatible."""

    def print_document(self, text: str) -> None:
        print(f"[LEGACY] {text}")


class ModernPrinter(ABC):
    """Interfaz moderna esperada."""

    @abstractmethod
    def print(self, content: str) -> None:
        pass


class PrinterAdapter(ModernPrinter):
    """Adapta LegacyPrinter a ModernPrinter."""

    def __init__(self, legacy: LegacyPrinter) -> None:
        self._legacy = legacy

    def print(self, content: str) -> None:
        self._legacy.print_document(content)


# --- Decorator ---
class Coffee(ABC):
    """Componente base."""

    @abstractmethod
    def cost(self) -> float:
        pass

    @abstractmethod
    def description(self) -> str:
        pass


class SimpleCoffee(Coffee):
    def cost(self) -> float:
        return 2.0

    def description(self) -> str:
        return "Simple coffee"


class CoffeeDecorator(Coffee):
    """Decorador base."""

    def __init__(self, coffee: Coffee) -> None:
        self._coffee = coffee


class MilkDecorator(CoffeeDecorator):
    def cost(self) -> float:
        return self._coffee.cost() + 0.5

    def description(self) -> str:
        return f"{self._coffee.description()}, milk"


class SugarDecorator(CoffeeDecorator):
    def cost(self) -> float:
        return self._coffee.cost() + 0.2

    def description(self) -> str:
        return f"{self._coffee.description()}, sugar"


# =============================================================================
# BEHAVIORAL PATTERNS
# =============================================================================


# --- Observer ---
class Subject:
    """Sujeto que notifica a observadores."""

    def __init__(self) -> None:
        self._observers: list[Callable] = []
        self._state: str | None = None

    def attach(self, observer: Callable) -> None:
        self._observers.append(observer)

    def detach(self, observer: Callable) -> None:
        self._observers.remove(observer)

    def notify(self) -> None:
        for observer in self._observers:
            observer(self._state)

    def set_state(self, state: str) -> None:
        self._state = state
        logger.info(f"Estado cambiado a: {state}")
        self.notify()


# --- Strategy ---
class PaymentStrategy(ABC):
    """Estrategia de pago."""

    @abstractmethod
    def pay(self, amount: float) -> str:
        pass


class CreditCardPayment(PaymentStrategy):
    def pay(self, amount: float) -> str:
        return f"Paid ${amount:.2f} with credit card"


class PayPalPayment(PaymentStrategy):
    def pay(self, amount: float) -> str:
        return f"Paid ${amount:.2f} with PayPal"


class ShoppingCart:
    """Contexto que usa estrategias."""

    def __init__(self, strategy: PaymentStrategy) -> None:
        self._strategy = strategy

    def checkout(self, amount: float) -> str:
        return self._strategy.pay(amount)


# --- Iterator ---
class BookCollection:
    """Colección iterable de libros."""

    def __init__(self) -> None:
        self._books: list[str] = []

    def add(self, book: str) -> None:
        self._books.append(book)

    def __iter__(self) -> Iterator[str]:
        return iter(self._books)


# =============================================================================
# DEMO
# =============================================================================


def main() -> None:
    """Demostración de patrones de diseño."""
    print("\n" + "=" * 60)
    print("DESIGN PATTERNS GoF - Ejemplos Ejecutables")
    print("=" * 60)

    # Singleton
    print("\n--- SINGLETON ---")
    s1 = Singleton()
    s2 = Singleton()
    print(f"s1 is s2: {s1 is s2}")

    # Factory Method
    print("\n--- FACTORY METHOD ---")
    pdf = DocumentFactory.create("pdf")
    html = DocumentFactory.create("html")
    print(pdf.render())
    print(html.render())

    # Builder
    print("\n--- BUILDER ---")
    email = (
        EmailBuilder()
        .from_address("sender@example.com")
        .to_address("recipient@example.com")
        .with_subject("Test Email")
        .with_body("Hello, World!")
        .attach("document.pdf")
        .build()
    )
    print(f"Email: {email}")

    # Adapter
    print("\n--- ADAPTER ---")
    legacy = LegacyPrinter()
    modern = PrinterAdapter(legacy)
    modern.print("Hello through adapter!")

    # Decorator
    print("\n--- DECORATOR ---")
    coffee = SimpleCoffee()
    coffee = MilkDecorator(coffee)
    coffee = SugarDecorator(coffee)
    print(f"{coffee.description()} = ${coffee.cost():.2f}")

    # Observer
    print("\n--- OBSERVER ---")
    subject = Subject()
    subject.attach(lambda state: print(f"Observer 1 received: {state}"))
    subject.attach(lambda state: print(f"Observer 2 received: {state}"))
    subject.set_state("NEW_STATE")

    # Strategy
    print("\n--- STRATEGY ---")
    cart_cc = ShoppingCart(CreditCardPayment())
    cart_pp = ShoppingCart(PayPalPayment())
    print(cart_cc.checkout(100.00))
    print(cart_pp.checkout(50.00))

    # Iterator
    print("\n--- ITERATOR ---")
    books = BookCollection()
    books.add("Design Patterns")
    books.add("Clean Code")
    books.add("Refactoring")
    for book in books:
        print(f"  - {book}")

    print("\n" + "=" * 60)
    print("Todos los patrones ejecutados exitosamente")
    print("=" * 60)


if __name__ == "__main__":
    main()
