---
name: refactoring-playbook
description: "- Mejorando código legacy"
type: feature
---

# Refactoring Playbook

> Técnicas sistemáticas para mejorar código sin cambiar comportamiento.

## Cuándo Usar Esta Skill

- Mejorando código legacy
- Reduciendo deuda técnica
- Preparando código para nueva funcionalidad
- Code review y mejoras

---

## Principios de Refactoring

### Cuándo Refactorizar

✅ **Sí refactorizar:**
- Antes de añadir nueva funcionalidad
- Cuando el código es difícil de entender
- Cuando hay duplicación
- Cuando los tests pasan y hay cobertura

❌ **No refactorizar:**
- Sin tests que cubran el código
- Bajo presión de deadline
- Código que no necesita cambios
- Todo a la vez (hacer incremental)

### Regla de Tres

> La primera vez, solo hazlo. La segunda vez, duplica con reluctancia. La tercera vez, refactoriza.

---

## Técnicas de Refactoring (20+)

### 1. Extract Method/Function

**Antes:**
```python
def print_invoice(invoice):
    print("*" * 40)
    print(f"Invoice #{invoice.number}")
    print("*" * 40)
    
    total = 0
    for item in invoice.items:
        print(f"{item.name}: ${item.price}")
        total += item.price
    
    print("-" * 40)
    print(f"Total: ${total}")
```

**Después:**
```python
def print_invoice(invoice):
    print_header(invoice)
    total = print_items(invoice.items)
    print_total(total)

def print_header(invoice):
    print("*" * 40)
    print(f"Invoice #{invoice.number}")
    print("*" * 40)

def print_items(items):
    total = 0
    for item in items:
        print(f"{item.name}: ${item.price}")
        total += item.price
    return total

def print_total(total):
    print("-" * 40)
    print(f"Total: ${total}")
```

---

### 2. Inline Method

**Antes:**
```python
def get_rating(driver):
    return more_than_five_late_deliveries(driver)

def more_than_five_late_deliveries(driver):
    return driver.late_deliveries > 5
```

**Después:**
```python
def get_rating(driver):
    return driver.late_deliveries > 5
```

---

### 3. Extract Variable

**Antes:**
```python
def calculate_price(order):
    return (order.quantity * order.item_price -
            max(0, order.quantity - 500) * order.item_price * 0.05 +
            min(order.quantity * order.item_price * 0.1, 100))
```

**Después:**
```python
def calculate_price(order):
    base_price = order.quantity * order.item_price
    quantity_discount = max(0, order.quantity - 500) * order.item_price * 0.05
    shipping = min(base_price * 0.1, 100)
    return base_price - quantity_discount + shipping
```

---

### 4. Replace Temp with Query

**Antes:**
```python
def calculate_total(order):
    base_price = order.quantity * order.item_price
    if base_price > 1000:
        return base_price * 0.95
    return base_price
```

**Después:**
```python
def calculate_total(order):
    if base_price(order) > 1000:
        return base_price(order) * 0.95
    return base_price(order)

def base_price(order):
    return order.quantity * order.item_price
```

---

### 5. Replace Conditional with Polymorphism

**Antes:**
```python
def calculate_shipping(order):
    if order.shipping_type == "standard":
        return order.weight * 1.5
    elif order.shipping_type == "express":
        return order.weight * 3.0
    elif order.shipping_type == "overnight":
        return order.weight * 5.0 + 10
```

**Después:**
```python
from abc import ABC, abstractmethod

class ShippingStrategy(ABC):
    @abstractmethod
    def calculate(self, weight: float) -> float:
        pass

class StandardShipping(ShippingStrategy):
    def calculate(self, weight: float) -> float:
        return weight * 1.5

class ExpressShipping(ShippingStrategy):
    def calculate(self, weight: float) -> float:
        return weight * 3.0

class OvernightShipping(ShippingStrategy):
    def calculate(self, weight: float) -> float:
        return weight * 5.0 + 10

def calculate_shipping(order):
    return order.shipping_strategy.calculate(order.weight)
```

---

### 6. Replace Magic Number with Constant

**Antes:**
```python
def calculate_potential_energy(mass, height):
    return mass * 9.81 * height

def is_valid_password(password):
    return len(password) >= 8
```

**Después:**
```python
GRAVITATIONAL_CONSTANT = 9.81
MIN_PASSWORD_LENGTH = 8

def calculate_potential_energy(mass, height):
    return mass * GRAVITATIONAL_CONSTANT * height

def is_valid_password(password):
    return len(password) >= MIN_PASSWORD_LENGTH
```

---

### 7. Introduce Parameter Object

**Antes:**
```python
def create_report(start_date, end_date, department, format, include_charts):
    # ...
    pass

create_report("2024-01-01", "2024-12-31", "Sales", "PDF", True)
```

**Después:**
```python
@dataclass
class ReportConfig:
    start_date: str
    end_date: str
    department: str
    format: str = "PDF"
    include_charts: bool = False

def create_report(config: ReportConfig):
    # ...
    pass

create_report(ReportConfig(
    start_date="2024-01-01",
    end_date="2024-12-31",
    department="Sales"
))
```

---

### 8. Replace Loop with Pipeline

**Antes:**
```python
def get_expensive_products(products):
    result = []
    for product in products:
        if product.price > 100:
            if product.in_stock:
                result.append(product.name.upper())
    return result
```

**Después:**
```python
def get_expensive_products(products):
    return [
        product.name.upper()
        for product in products
        if product.price > 100 and product.in_stock
    ]

# O con funciones
def get_expensive_products(products):
    return (
        products
        .filter(lambda p: p.price > 100)
        .filter(lambda p: p.in_stock)
        .map(lambda p: p.name.upper())
        .to_list()
    )
```

---

### 9. Extract Class

**Antes:**
```python
class Person:
    def __init__(self, name, area_code, number, street, city, zip_code):
        self.name = name
        self.area_code = area_code
        self.number = number
        self.street = street
        self.city = city
        self.zip_code = zip_code
    
    def get_phone_number(self):
        return f"({self.area_code}) {self.number}"
    
    def get_full_address(self):
        return f"{self.street}, {self.city} {self.zip_code}"
```

**Después:**
```python
@dataclass
class PhoneNumber:
    area_code: str
    number: str
    
    def __str__(self):
        return f"({self.area_code}) {self.number}"

@dataclass
class Address:
    street: str
    city: str
    zip_code: str
    
    def __str__(self):
        return f"{self.street}, {self.city} {self.zip_code}"

@dataclass
class Person:
    name: str
    phone: PhoneNumber
    address: Address
```

---

### 10. Replace Nested Conditionals with Guard Clauses

**Antes:**
```python
def calculate_pay(employee):
    if employee.is_active:
        if employee.is_full_time:
            if employee.years > 5:
                return employee.base_salary * 1.2
            else:
                return employee.base_salary
        else:
            return employee.hourly_rate * employee.hours
    else:
        return 0
```

**Después:**
```python
def calculate_pay(employee):
    if not employee.is_active:
        return 0
    
    if not employee.is_full_time:
        return employee.hourly_rate * employee.hours
    
    if employee.years > 5:
        return employee.base_salary * 1.2
    
    return employee.base_salary
```

---

### 11. Rename for Clarity

**Antes:**
```python
def calc(a, b, t):
    return a + b if t == 1 else a * b

x = calc(5, 3, 1)
```

**Después:**
```python
def calculate_price(base_price, tax, operation_type):
    ADD_OPERATION = 1
    if operation_type == ADD_OPERATION:
        return base_price + tax
    return base_price * tax

total_price = calculate_price(base_price=5, tax=3, operation_type=1)
```

---

### 12. Decompose Conditional

**Antes:**
```python
if date.before(SUMMER_START) or date.after(SUMMER_END):
    charge = quantity * winter_rate + winter_service_charge
else:
    charge = quantity * summer_rate
```

**Después:**
```python
def is_summer(date):
    return not date.before(SUMMER_START) and not date.after(SUMMER_END)

def summer_charge(quantity):
    return quantity * summer_rate

def winter_charge(quantity):
    return quantity * winter_rate + winter_service_charge

if is_summer(date):
    charge = summer_charge(quantity)
else:
    charge = winter_charge(quantity)
```

---

## Patrones de Refactoring a Gran Escala

### Strangler Fig Pattern

Para migrar sistemas legacy gradualmente:

```
1. Identificar módulo a migrar
2. Crear nueva implementación
3. Redirigir tráfico gradualmente (feature flags)
4. Monitorear
5. Eliminar código viejo
```

```python
# Feature flag para migración gradual
def get_user(user_id):
    if feature_flags.is_enabled("new_user_service"):
        return new_user_service.get(user_id)
    return legacy_user_service.get(user_id)
```

### Branch by Abstraction

Para refactorizar código muy acoplado:

```
1. Crear abstracción (interface)
2. Implementar abstracción con código existente
3. Crear nueva implementación
4. Migrar clientes gradualmente
5. Eliminar implementación vieja
```

```python
# Paso 1-2: Crear abstracción e implementar con código existente
class NotificationService(ABC):
    @abstractmethod
    def send(self, message: str) -> None:
        pass

class LegacyNotificationService(NotificationService):
    def send(self, message: str) -> None:
        # Código legacy aquí
        pass

# Paso 3: Nueva implementación
class ModernNotificationService(NotificationService):
    def send(self, message: str) -> None:
        # Nueva implementación
        pass

# Paso 4: Migrar clientes
def notify_user(service: NotificationService, msg: str):
    service.send(msg)
```

---

## Checklist de Refactoring

### Antes de Empezar
- [ ] ¿Hay tests que cubren el código?
- [ ] ¿Los tests pasan actualmente?
- [ ] ¿Entiendo qué hace el código?
- [ ] ¿Es un buen momento? (no deadline)

### Durante
- [ ] Cambios pequeños e incrementales
- [ ] Tests pasan después de cada cambio
- [ ] Commit frecuente
- [ ] No añadir funcionalidad nueva

### Después
- [ ] ¿El código es más legible?
- [ ] ¿Es más fácil de modificar?
- [ ] ¿Se eliminó duplicación?
- [ ] ¿Los tests siguen pasando?

---

## Code Smells y Su Refactoring

| Code Smell | Refactoring |
|------------|-------------|
| Long Method | Extract Method |
| Large Class | Extract Class |
| Long Parameter List | Parameter Object |
| Duplicate Code | Extract Method/Class |
| Feature Envy | Move Method |
| Data Clumps | Extract Class |
| Primitive Obsession | Replace with Object |
| Switch Statements | Replace with Polymorphism |
| Parallel Inheritance | Move Field/Method |
| Comments (excesivos) | Extract Method, Rename |

---

*Skill: refactoring-playbook v1.0*
