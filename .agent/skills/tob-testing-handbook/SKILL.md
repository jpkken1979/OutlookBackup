---
name: tob-testing-handbook
type: feature
description: "Best practices de testing del Testing Handbook de Trail of Bits. Cubre unit tests, fuzzing, property testing, mutation testing y test design patterns."
---

# Trail of Bits: Testing Handbook

Mejores prácticas de testing basadas en el Testing Handbook de Trail of Bits.

## Principios Fundamentales

1. **Test the behavior, not the implementation** — Los tests no deben romperse por refactors internos.
2. **Arrange-Act-Assert** — Estructura clara en cada test.
3. **One assertion per concept** — Cada test verifica una cosa.
4. **Tests as documentation** — Los nombres de tests describen el comportamiento esperado.
5. **Deterministic** — Tests reproducibles, sin dependencias externas.

## Niveles de Testing

### Unit Tests
Prueban funciones/métodos individuales en aislamiento:

```python
def test_calculate_discount_standard_customer():
    """Descuento estándar aplicado correctamente."""
    customer = Customer(tier="standard")
    result = calculate_discount(price=100, customer=customer)
    assert result == 95.0  # 5% descuento

def test_calculate_discount_premium_customer():
    """Descuento premium aplicado correctamente."""
    customer = Customer(tier="premium")
    result = calculate_discount(price=100, customer=customer)
    assert result == 85.0  # 15% descuento

def test_calculate_discount_negative_price_raises():
    """Precio negativo lanza ValueError."""
    customer = Customer(tier="standard")
    with pytest.raises(ValueError, match="Price must be positive"):
        calculate_discount(price=-10, customer=customer)
```

### Property-Based Testing
Genera inputs automáticamente para descubrir edge cases:

```python
from hypothesis import given, strategies as st

@given(st.integers(min_value=0, max_value=10000))
def test_discount_never_exceeds_original_price(price):
    """El precio con descuento nunca supera el original."""
    customer = Customer(tier="premium")
    result = calculate_discount(price=price, customer=customer)
    assert 0 <= result <= price

@given(st.text(min_size=1, max_size=100))
def test_sanitize_preserves_length_bound(text):
    """Sanitización no excede longitud máxima."""
    result = sanitize_input(text, max_length=50)
    assert len(result) <= 50
```

### Fuzzing
Encuentra crashes y vulnerabilidades con inputs aleatorios:

```python
# atheris (Python fuzzer)
import atheris
import sys

def fuzz_target(data):
    try:
        fdp = atheris.FuzzedDataProvider(data)
        input_str = fdp.ConsumeUnicodeNoSurrogates(100)
        parse_config(input_str)  # Función bajo test
    except ValueError:
        pass  # Excepciones esperadas

atheris.Setup(sys.argv, fuzz_target)
atheris.Fuzz()
```

### Mutation Testing
Verifica que los tests detectan cambios en el código:

```bash
# Python — mutmut
pip install mutmut
mutmut run --paths-to-mutate=src/ --tests-dir=tests/
mutmut results
```

| Resultado | Significado |
|-----------|-------------|
| killed | Mutante detectado (test pasó) ✅ |
| survived | Mutante no detectado (falta test) ❌ |
| timeout | Mutante causó loop infinito |

### Integration Tests
Prueban interacción entre componentes:

```python
@pytest.mark.integration
async def test_api_creates_and_retrieves_user():
    """Flujo completo: crear usuario → obtener usuario."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Create
        resp = await client.post("/users", json={"name": "Alice"})
        assert resp.status_code == 201
        user_id = resp.json()["id"]

        # Retrieve
        resp = await client.get(f"/users/{user_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Alice"
```

## Test Design Patterns

### Fixture Factory
```python
@pytest.fixture
def make_user():
    """Factory para crear usuarios con defaults."""
    def _make(name="Test User", tier="standard", active=True):
        return User(name=name, tier=tier, active=active)
    return _make

def test_deactivate_user(make_user):
    user = make_user(active=True)
    user.deactivate()
    assert not user.active
```

### Parametrize
```python
@pytest.mark.parametrize("input_val,expected", [
    ("hello", "HELLO"),
    ("", ""),
    ("123", "123"),
    ("Hello World", "HELLO WORLD"),
])
def test_uppercase_transform(input_val, expected):
    assert uppercase(input_val) == expected
```

### Test Doubles
```python
from unittest.mock import AsyncMock, patch

async def test_send_notification_calls_email_service():
    mock_email = AsyncMock(return_value=True)
    with patch("app.services.send_email", mock_email):
        await notify_user(user_id="123", message="Hello")
    mock_email.assert_called_once()
```

## Anti-Patterns

- **NO** tests que dependen del orden de ejecución
- **NO** tests que requieren estado de red/DB real sin fixtures
- **NO** assertions vagas (`assert result is not None`)
- **NO** tests que verifican implementación interna (private methods)
- **NO** tests frágiles que fallan por cambios cosméticos

## Cobertura

```bash
# Generar reporte de cobertura
pytest --cov=src --cov-report=html --cov-report=term-missing

# Objetivo mínimo: 80%
pytest --cov=src --cov-fail-under=80
```

## Recursos

- [Trail of Bits Testing Handbook](https://appsec.guide/)
- [Hypothesis (Python)](https://hypothesis.readthedocs.io/)
- [mutmut (Mutation Testing)](https://mutmut.readthedocs.io/)
- [atheris (Fuzzing)](https://github.com/google/atheris)
