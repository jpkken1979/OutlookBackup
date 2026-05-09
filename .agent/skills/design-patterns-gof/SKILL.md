---
name: design-patterns-gof
description: "- Diseñando arquitectura de software"
type: feature
---

# Design Patterns (Gang of Four)

> 23 patrones de diseño esenciales para programación orientada a objetos.

## Cuándo Usar Esta Skill

- Diseñando arquitectura de software
- Resolviendo problemas comunes de diseño
- Refactorizando código existente
- Code review de patrones

---

## Patrones Creacionales (5)

### 1. Factory Method
**Propósito:** Crear objetos sin especificar la clase exacta.

```python
# Python
from abc import ABC, abstractmethod

class Creator(ABC):
    @abstractmethod
    def factory_method(self) -> "Product":
        pass
    
    def operation(self) -> str:
        product = self.factory_method()
        return f"Creator: {product.operation()}"

class ConcreteCreatorA(Creator):
    def factory_method(self) -> "Product":
        return ConcreteProductA()

class Product(ABC):
    @abstractmethod
    def operation(self) -> str:
        pass

class ConcreteProductA(Product):
    def operation(self) -> str:
        return "ProductA"
```

```typescript
// TypeScript
interface Product {
  operation(): string;
}

abstract class Creator {
  abstract factoryMethod(): Product;
  
  operation(): string {
    const product = this.factoryMethod();
    return `Creator: ${product.operation()}`;
  }
}

class ConcreteCreatorA extends Creator {
  factoryMethod(): Product {
    return new ConcreteProductA();
  }
}
```

**Cuándo usar:** Múltiples tipos de objetos similares, extensibilidad.
**Cuándo NO usar:** Un solo tipo, constructor simple.

---

### 2. Abstract Factory
**Propósito:** Crear familias de objetos relacionados.

```python
from abc import ABC, abstractmethod

class AbstractFactory(ABC):
    @abstractmethod
    def create_product_a(self) -> "AbstractProductA":
        pass
    
    @abstractmethod
    def create_product_b(self) -> "AbstractProductB":
        pass

class ConcreteFactory1(AbstractFactory):
    def create_product_a(self) -> "AbstractProductA":
        return ConcreteProductA1()
    
    def create_product_b(self) -> "AbstractProductB":
        return ConcreteProductB1()
```

**Cuándo usar:** Familias de productos, UI themes, cross-platform.
**Cuándo NO usar:** Productos no relacionados.

---

### 3. Builder
**Propósito:** Construir objetos complejos paso a paso.

```python
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class House:
    walls: int = 0
    doors: int = 0
    windows: int = 0
    roof: Optional[str] = None
    garage: bool = False

class HouseBuilder:
    def __init__(self):
        self._house = House()
    
    def set_walls(self, count: int) -> "HouseBuilder":
        self._house.walls = count
        return self
    
    def set_doors(self, count: int) -> "HouseBuilder":
        self._house.doors = count
        return self
    
    def set_roof(self, roof_type: str) -> "HouseBuilder":
        self._house.roof = roof_type
        return self
    
    def build(self) -> House:
        return self._house

# Uso fluent
house = (HouseBuilder()
    .set_walls(4)
    .set_doors(2)
    .set_roof("tile")
    .build())
```

**Cuándo usar:** Objetos con muchos parámetros, inmutabilidad.
**Cuándo NO usar:** Objetos simples (<4 parámetros).

---

### 4. Singleton
**Propósito:** Garantizar una única instancia global.

```python
class Singleton:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

# Thread-safe con lock
import threading

class ThreadSafeSingleton:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
```

**Cuándo usar:** Configuración global, connection pools.
**Cuándo NO usar:** Testing (difícil de mockear), estado mutable global.

---

### 5. Prototype
**Propósito:** Clonar objetos existentes.

```python
import copy
from abc import ABC, abstractmethod

class Prototype(ABC):
    @abstractmethod
    def clone(self) -> "Prototype":
        pass

class ConcretePrototype(Prototype):
    def __init__(self, value: int, nested: list):
        self.value = value
        self.nested = nested
    
    def clone(self) -> "Prototype":
        return copy.deepcopy(self)
```

**Cuándo usar:** Objetos costosos de crear, configuraciones base.
**Cuándo NO usar:** Objetos con referencias circulares complejas.

---

## Patrones Estructurales (7)

### 6. Adapter
**Propósito:** Convertir interfaz incompatible en compatible.

```python
class Target:
    def request(self) -> str:
        return "Target: default"

class Adaptee:
    def specific_request(self) -> str:
        return "Adaptee: specific"

class Adapter(Target):
    def __init__(self, adaptee: Adaptee):
        self._adaptee = adaptee
    
    def request(self) -> str:
        return f"Adapter: {self._adaptee.specific_request()}"
```

**Cuándo usar:** Integrar librerías legacy, APIs externas.

---

### 7. Bridge
**Propósito:** Separar abstracción de implementación.

```python
from abc import ABC, abstractmethod

class Implementation(ABC):
    @abstractmethod
    def operation_impl(self) -> str:
        pass

class Abstraction:
    def __init__(self, implementation: Implementation):
        self._impl = implementation
    
    def operation(self) -> str:
        return f"Abstraction: {self._impl.operation_impl()}"
```

**Cuándo usar:** Múltiples dimensiones de variación (forma + color).

---

### 8. Composite
**Propósito:** Tratar objetos individuales y composiciones uniformemente.

```python
from abc import ABC, abstractmethod
from typing import List

class Component(ABC):
    @abstractmethod
    def operation(self) -> str:
        pass

class Leaf(Component):
    def operation(self) -> str:
        return "Leaf"

class Composite(Component):
    def __init__(self):
        self._children: List[Component] = []
    
    def add(self, component: Component) -> None:
        self._children.append(component)
    
    def operation(self) -> str:
        results = [child.operation() for child in self._children]
        return f"Branch({'+'.join(results)})"
```

**Cuándo usar:** Estructuras de árbol (filesystem, UI).

---

### 9. Decorator
**Propósito:** Añadir comportamiento dinámicamente.

```python
from abc import ABC, abstractmethod

class Component(ABC):
    @abstractmethod
    def operation(self) -> str:
        pass

class ConcreteComponent(Component):
    def operation(self) -> str:
        return "ConcreteComponent"

class Decorator(Component):
    def __init__(self, component: Component):
        self._component = component
    
    def operation(self) -> str:
        return self._component.operation()

class ConcreteDecoratorA(Decorator):
    def operation(self) -> str:
        return f"DecoratorA({self._component.operation()})"
```

**Cuándo usar:** Añadir funcionalidad sin herencia, middleware.

---

### 10. Facade
**Propósito:** Interfaz simplificada a subsistema complejo.

```python
class SubsystemA:
    def operation_a(self) -> str:
        return "SubsystemA"

class SubsystemB:
    def operation_b(self) -> str:
        return "SubsystemB"

class Facade:
    def __init__(self):
        self._subsystem_a = SubsystemA()
        self._subsystem_b = SubsystemB()
    
    def operation(self) -> str:
        result = self._subsystem_a.operation_a()
        result += self._subsystem_b.operation_b()
        return f"Facade: {result}"
```

**Cuándo usar:** Simplificar APIs complejas, librerías.

---

### 11. Flyweight
**Propósito:** Compartir estado común entre objetos.

```python
class Flyweight:
    def __init__(self, shared_state: str):
        self._shared_state = shared_state
    
    def operation(self, unique_state: str) -> str:
        return f"Flyweight({self._shared_state}, {unique_state})"

class FlyweightFactory:
    _flyweights: dict = {}
    
    @classmethod
    def get_flyweight(cls, shared_state: str) -> Flyweight:
        if shared_state not in cls._flyweights:
            cls._flyweights[shared_state] = Flyweight(shared_state)
        return cls._flyweights[shared_state]
```

**Cuándo usar:** Miles de objetos similares (caracteres, partículas).

---

### 12. Proxy
**Propósito:** Controlar acceso a objeto.

```python
from abc import ABC, abstractmethod

class Subject(ABC):
    @abstractmethod
    def request(self) -> str:
        pass

class RealSubject(Subject):
    def request(self) -> str:
        return "RealSubject"

class Proxy(Subject):
    def __init__(self, real_subject: RealSubject):
        self._real_subject = real_subject
    
    def request(self) -> str:
        if self._check_access():
            return self._real_subject.request()
        return "Access denied"
    
    def _check_access(self) -> bool:
        return True  # Auth logic
```

**Cuándo usar:** Lazy loading, caching, logging, auth.

---

## Patrones de Comportamiento (11)

### 13. Chain of Responsibility
**Propósito:** Pasar solicitud por cadena de handlers.

```python
from abc import ABC, abstractmethod
from typing import Optional

class Handler(ABC):
    _next: Optional["Handler"] = None
    
    def set_next(self, handler: "Handler") -> "Handler":
        self._next = handler
        return handler
    
    @abstractmethod
    def handle(self, request: str) -> Optional[str]:
        pass

class ConcreteHandlerA(Handler):
    def handle(self, request: str) -> Optional[str]:
        if request == "A":
            return f"HandlerA: {request}"
        elif self._next:
            return self._next.handle(request)
        return None
```

**Cuándo usar:** Middleware, validaciones en cadena.

---

### 14. Command
**Propósito:** Encapsular acción como objeto.

```python
from abc import ABC, abstractmethod

class Command(ABC):
    @abstractmethod
    def execute(self) -> None:
        pass

class ConcreteCommand(Command):
    def __init__(self, receiver: "Receiver", payload: str):
        self._receiver = receiver
        self._payload = payload
    
    def execute(self) -> None:
        self._receiver.action(self._payload)

class Receiver:
    def action(self, payload: str) -> None:
        print(f"Receiver: {payload}")

class Invoker:
    def __init__(self):
        self._commands: list = []
    
    def add_command(self, command: Command) -> None:
        self._commands.append(command)
    
    def execute_commands(self) -> None:
        for command in self._commands:
            command.execute()
```

**Cuándo usar:** Undo/redo, job queues, transacciones.

---

### 15. Iterator
**Propósito:** Recorrer colección sin exponer estructura.

```python
from typing import Iterator, List

class WordsCollection:
    def __init__(self):
        self._words: List[str] = []
    
    def add(self, word: str) -> None:
        self._words.append(word)
    
    def __iter__(self) -> Iterator[str]:
        return iter(self._words)
    
    def reverse_iterator(self) -> Iterator[str]:
        return reversed(self._words)
```

**Cuándo usar:** Colecciones personalizadas, lazy evaluation.

---

### 16. Mediator
**Propósito:** Centralizar comunicación entre objetos.

```python
from abc import ABC, abstractmethod

class Mediator(ABC):
    @abstractmethod
    def notify(self, sender: object, event: str) -> None:
        pass

class ConcreteMediator(Mediator):
    def __init__(self, c1: "Component1", c2: "Component2"):
        self._component1 = c1
        self._component2 = c2
        c1.mediator = self
        c2.mediator = self
    
    def notify(self, sender: object, event: str) -> None:
        if event == "A":
            self._component2.do_c()
        elif event == "D":
            self._component1.do_b()

class BaseComponent:
    def __init__(self, mediator: Mediator = None):
        self._mediator = mediator
    
    @property
    def mediator(self) -> Mediator:
        return self._mediator
    
    @mediator.setter
    def mediator(self, mediator: Mediator) -> None:
        self._mediator = mediator
```

**Cuándo usar:** Reducir dependencias entre componentes UI.

---

### 17. Memento
**Propósito:** Guardar y restaurar estado.

```python
from dataclasses import dataclass
from typing import List

@dataclass
class Memento:
    state: str

class Originator:
    def __init__(self, state: str):
        self._state = state
    
    def save(self) -> Memento:
        return Memento(self._state)
    
    def restore(self, memento: Memento) -> None:
        self._state = memento.state

class Caretaker:
    def __init__(self, originator: Originator):
        self._mementos: List[Memento] = []
        self._originator = originator
    
    def backup(self) -> None:
        self._mementos.append(self._originator.save())
    
    def undo(self) -> None:
        if self._mementos:
            memento = self._mementos.pop()
            self._originator.restore(memento)
```

**Cuándo usar:** Undo/redo, snapshots, transacciones.

---

### 18. Observer
**Propósito:** Notificar cambios a múltiples objetos.

```python
from abc import ABC, abstractmethod
from typing import List

class Observer(ABC):
    @abstractmethod
    def update(self, subject: "Subject") -> None:
        pass

class Subject:
    def __init__(self):
        self._observers: List[Observer] = []
        self._state: int = 0
    
    def attach(self, observer: Observer) -> None:
        self._observers.append(observer)
    
    def detach(self, observer: Observer) -> None:
        self._observers.remove(observer)
    
    def notify(self) -> None:
        for observer in self._observers:
            observer.update(self)
    
    def set_state(self, state: int) -> None:
        self._state = state
        self.notify()
```

**Cuándo usar:** Eventos, pub/sub, MVC, reactive programming.

---

### 19. State
**Propósito:** Cambiar comportamiento según estado.

```python
from abc import ABC, abstractmethod

class State(ABC):
    @abstractmethod
    def handle(self, context: "Context") -> None:
        pass

class ConcreteStateA(State):
    def handle(self, context: "Context") -> None:
        print("State A → B")
        context.state = ConcreteStateB()

class ConcreteStateB(State):
    def handle(self, context: "Context") -> None:
        print("State B → A")
        context.state = ConcreteStateA()

class Context:
    def __init__(self, state: State):
        self._state = state
    
    @property
    def state(self) -> State:
        return self._state
    
    @state.setter
    def state(self, state: State) -> None:
        self._state = state
    
    def request(self) -> None:
        self._state.handle(self)
```

**Cuándo usar:** State machines, workflows, game states.

---

### 20. Strategy
**Propósito:** Intercambiar algoritmos en runtime.

```python
from abc import ABC, abstractmethod
from typing import List

class Strategy(ABC):
    @abstractmethod
    def execute(self, data: List[int]) -> List[int]:
        pass

class BubbleSort(Strategy):
    def execute(self, data: List[int]) -> List[int]:
        return sorted(data)  # Simplified

class QuickSort(Strategy):
    def execute(self, data: List[int]) -> List[int]:
        return sorted(data)  # Simplified

class Context:
    def __init__(self, strategy: Strategy):
        self._strategy = strategy
    
    def set_strategy(self, strategy: Strategy) -> None:
        self._strategy = strategy
    
    def execute_strategy(self, data: List[int]) -> List[int]:
        return self._strategy.execute(data)
```

**Cuándo usar:** Múltiples algoritmos, payment methods, validaciones.

---

### 21. Template Method
**Propósito:** Definir esqueleto de algoritmo.

```python
from abc import ABC, abstractmethod

class AbstractClass(ABC):
    def template_method(self) -> None:
        self.base_operation1()
        self.required_operation1()
        self.base_operation2()
        self.hook()
    
    def base_operation1(self) -> None:
        print("Base operation 1")
    
    def base_operation2(self) -> None:
        print("Base operation 2")
    
    @abstractmethod
    def required_operation1(self) -> None:
        pass
    
    def hook(self) -> None:
        pass  # Optional override
```

**Cuándo usar:** Frameworks, hooks, lifecycle methods.

---

### 22. Visitor
**Propósito:** Separar algoritmo de estructura.

```python
from abc import ABC, abstractmethod

class Visitor(ABC):
    @abstractmethod
    def visit_element_a(self, element: "ElementA") -> None:
        pass
    
    @abstractmethod
    def visit_element_b(self, element: "ElementB") -> None:
        pass

class Element(ABC):
    @abstractmethod
    def accept(self, visitor: Visitor) -> None:
        pass

class ElementA(Element):
    def accept(self, visitor: Visitor) -> None:
        visitor.visit_element_a(self)

class ElementB(Element):
    def accept(self, visitor: Visitor) -> None:
        visitor.visit_element_b(self)
```

**Cuándo usar:** AST traversal, report generation, serialization.

---

### 23. Interpreter
**Propósito:** Evaluar gramática o expresiones.

```python
from abc import ABC, abstractmethod
from typing import Dict

class Expression(ABC):
    @abstractmethod
    def interpret(self, context: Dict[str, int]) -> int:
        pass

class Number(Expression):
    def __init__(self, value: int):
        self._value = value
    
    def interpret(self, context: Dict[str, int]) -> int:
        return self._value

class Variable(Expression):
    def __init__(self, name: str):
        self._name = name
    
    def interpret(self, context: Dict[str, int]) -> int:
        return context.get(self._name, 0)

class Add(Expression):
    def __init__(self, left: Expression, right: Expression):
        self._left = left
        self._right = right
    
    def interpret(self, context: Dict[str, int]) -> int:
        return self._left.interpret(context) + self._right.interpret(context)
```

**Cuándo usar:** DSLs, calculadoras, parsers simples.

---

## Matriz de Decisión

| Patrón | Problema | Alternativa Moderna |
|--------|----------|---------------------|
| Singleton | Estado global | Dependency Injection |
| Factory | Creación flexible | Constructor + DI |
| Observer | Eventos | RxJS, Event Emitter |
| Strategy | Algoritmos | Lambdas, Higher-order functions |
| Decorator | Extensión | Mixins, Composition |
| Command | Acciones | Async/await, Promises |
| State | FSM | XState, Redux |

---

## Referencias

- **Libro:** "Design Patterns" - Gang of Four (1994)
- **Refactoring Guru:** https://refactoring.guru/design-patterns
- **Python Patterns:** https://python-patterns.guide/

---

*Skill: design-patterns-gof v1.0*
