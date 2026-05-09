---
description: Refactorización sistemática de código. Workflow universal compatible con cualquier LLM.
universal: true
---

# /refactor - Refactorización de Código

> Workflow universal compatible con: Claude, GPT-4, Gemini, Codex, Llama, Mistral

## Código a Refactorizar

$ARGUMENTS

---

## Proceso de Refactorización

### Fase 1: Análisis del Código Actual

```markdown
## Análisis de Estado Actual

### Métricas de Código
| Métrica | Valor Actual | Objetivo |
|---------|--------------|----------|
| Complejidad ciclomática | X | < 10 |
| Líneas por función | X | < 50 |
| Profundidad de anidamiento | X | < 4 |
| Duplicación de código | X% | < 5% |

### Code Smells Detectados
- [ ] **Long Method** - Funciones muy largas
- [ ] **Large Class** - Clases con muchas responsabilidades
- [ ] **Feature Envy** - Métodos que usan más datos de otra clase
- [ ] **Data Clumps** - Grupos de datos que siempre van juntos
- [ ] **Primitive Obsession** - Uso excesivo de primitivos
- [ ] **Switch Statements** - Switches que deberían ser polimorfismo
- [ ] **Parallel Inheritance** - Jerarquías paralelas
- [ ] **Lazy Class** - Clases que hacen muy poco
- [ ] **Speculative Generality** - Abstracción prematura
- [ ] **Temporary Field** - Campos usados ocasionalmente
- [ ] **Message Chains** - Cadenas de llamadas
- [ ] **Middle Man** - Delegación excesiva
- [ ] **Inappropriate Intimacy** - Clases muy acopladas
- [ ] **Comments** - Comentarios que compensan mal código

### Deuda Técnica Identificada
| Item | Severidad | Esfuerzo | Prioridad |
|------|-----------|----------|-----------|
| [descripción] | [Alta/Media/Baja] | [horas] | [1-5] |
```

---

### Fase 2: Plan de Refactorización

```markdown
## Plan de Refactorización

### Objetivo
[Descripción clara de qué se quiere lograr]

### Scope
- **Archivos afectados:** [lista]
- **Funcionalidad afectada:** [descripción]
- **Riesgo de regresión:** [Bajo/Medio/Alto]

### Estrategia

#### Orden de Refactorización
1. [Paso 1] - [justificación]
2. [Paso 2] - [justificación]
3. [Paso 3] - [justificación]

#### Tests de Caracterización
- [ ] Tests existentes pasan
- [ ] Agregar tests para comportamiento actual
- [ ] Definir tests de regresión

### Técnicas a Aplicar
| Técnica | Aplicación | Beneficio |
|---------|------------|-----------|
| Extract Method | [dónde] | [qué mejora] |
| Extract Class | [dónde] | [qué mejora] |
| Rename | [qué] | [claridad] |
```

---

### Fase 3: Ejecución Segura

```markdown
## Proceso de Refactorización Segura

### Pre-requisitos
- [ ] Tests pasan (verde)
- [ ] Código commiteado
- [ ] Branch de feature creado

### Ciclo de Refactorización

\`\`\`
┌─────────────────────────────────────────┐
│     1. VERIFICAR TESTS (Verde)          │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│     2. HACER UN PEQUEÑO CAMBIO          │
│        (Una sola técnica a la vez)      │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│     3. EJECUTAR TESTS                   │
└─────────────────┬───────────────────────┘
                  │
         ┌───────┴───────┐
         ▼               ▼
    ┌─────────┐     ┌─────────┐
    │  VERDE  │     │  ROJO   │
    │ Commit  │     │ Revert  │
    └────┬────┘     └────┬────┘
         │               │
         └───────┬───────┘
                 │
                 ▼
        ┌────────────────┐
        │ ¿Más cambios?  │
        └───────┬────────┘
                │
       ┌────────┴────────┐
       ▼                 ▼
   [Continuar]        [Fin]
\`\`\`

### Commits Atómicos
Cada commit debe ser:
- Un solo tipo de refactoring
- Tests pasando
- Mensaje descriptivo
\`\`\`
refactor: extract calculateTotal into separate function
refactor: rename userList to activeUsers
refactor: move validation logic to UserValidator class
\`\`\`
```

---

### Fase 4: Técnicas de Refactorización

#### Extract Method

```python
# ANTES
def process_order(order):
    # Calcular subtotal
    subtotal = 0
    for item in order.items:
        subtotal += item.price * item.quantity

    # Aplicar descuento
    if order.customer.is_premium:
        discount = subtotal * 0.1
    else:
        discount = 0

    # Calcular impuestos
    tax = (subtotal - discount) * 0.21

    return subtotal - discount + tax

# DESPUÉS
def process_order(order):
    subtotal = calculate_subtotal(order.items)
    discount = calculate_discount(subtotal, order.customer)
    tax = calculate_tax(subtotal - discount)
    return subtotal - discount + tax

def calculate_subtotal(items):
    return sum(item.price * item.quantity for item in items)

def calculate_discount(subtotal, customer):
    return subtotal * 0.1 if customer.is_premium else 0

def calculate_tax(amount):
    return amount * 0.21
```

#### Extract Class

```python
# ANTES
class Order:
    def __init__(self):
        self.customer_name = ""
        self.customer_email = ""
        self.customer_address = ""
        self.customer_phone = ""
        self.items = []
        self.total = 0

# DESPUÉS
class Customer:
    def __init__(self, name, email, address, phone):
        self.name = name
        self.email = email
        self.address = address
        self.phone = phone

class Order:
    def __init__(self, customer: Customer):
        self.customer = customer
        self.items = []
        self.total = 0
```

#### Replace Conditional with Polymorphism

```python
# ANTES
def calculate_shipping(order):
    if order.shipping_type == "standard":
        return 5.99
    elif order.shipping_type == "express":
        return 15.99
    elif order.shipping_type == "overnight":
        return 29.99

# DESPUÉS
from abc import ABC, abstractmethod

class ShippingStrategy(ABC):
    @abstractmethod
    def calculate(self, order) -> float:
        pass

class StandardShipping(ShippingStrategy):
    def calculate(self, order) -> float:
        return 5.99

class ExpressShipping(ShippingStrategy):
    def calculate(self, order) -> float:
        return 15.99

class OvernightShipping(ShippingStrategy):
    def calculate(self, order) -> float:
        return 29.99

# Uso
shipping = ShippingFactory.create(order.shipping_type)
cost = shipping.calculate(order)
```

---

### Fase 5: Verificación

```markdown
## Verificación Post-Refactorización

### Checklist de Calidad
- [ ] Todos los tests pasan
- [ ] No hay regresiones en funcionalidad
- [ ] Métricas de código mejoraron
- [ ] Código es más legible
- [ ] Nombres son descriptivos
- [ ] No hay duplicación nueva

### Métricas Comparativas
| Métrica | Antes | Después | Δ |
|---------|-------|---------|---|
| Complejidad | X | Y | -Z% |
| Líneas | X | Y | -Z% |
| Duplicación | X% | Y% | -Z% |
| Cobertura | X% | Y% | +Z% |

### Documentación de Cambios
| Cambio | Justificación |
|--------|---------------|
| [cambio 1] | [por qué] |
| [cambio 2] | [por qué] |
```

---

## Catálogo de Técnicas

### Simplificación
| Técnica | Cuándo Usar |
|---------|-------------|
| **Rename** | Nombres confusos |
| **Extract Variable** | Expresiones complejas |
| **Inline Variable** | Variable innecesaria |
| **Replace Magic Number** | Números sin contexto |

### Reorganización
| Técnica | Cuándo Usar |
|---------|-------------|
| **Extract Method** | Método muy largo |
| **Inline Method** | Método trivial |
| **Extract Class** | Clase con muchas responsabilidades |
| **Move Method** | Método en clase incorrecta |

### Simplificación de Condicionales
| Técnica | Cuándo Usar |
|---------|-------------|
| **Decompose Conditional** | Condicional complejo |
| **Consolidate Conditional** | Múltiples condiciones, misma acción |
| **Replace Nested with Guard** | Anidamiento profundo |
| **Replace Conditional with Polymorphism** | Switch/if-else por tipo |

---

## Principios

1. **Pequeños pasos** - Un cambio a la vez
2. **Tests primero** - Nunca refactorizar sin tests
3. **Commits frecuentes** - Poder revertir fácilmente
4. **No mezclar** - Refactoring separado de features
5. **Boy Scout Rule** - Dejar el código mejor de como lo encontraste

---

*Workflow de Refactorización v1.0 - Compatible con cualquier LLM*
