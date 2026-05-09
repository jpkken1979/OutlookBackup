# Regla: Estándares Python

Aplica a todos los archivos `.py` del repositorio.

## Requisitos

- **Type hints** obligatorios en todas las funciones
- **Docstrings** en formato Google
- **Pydantic** `BaseModel` con `Field()` para validación de datos
- **Dataclasses** para estructuras de datos simples
- **Logging** con formato `[%(asctime)s] [%(levelname)s]`
- Linter: **ruff** (reglas: E, W, F, I, B, C4, UP, ARG, SIM), línea máx 100
- Type checker: **mypy** (strict)

## Plantilla de función

```python
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)

@dataclass
class ExampleModel:
    """Descripción corta.

    Args:
        name: El valor del nombre.
        value: Valor numérico opcional.
    """
    name: str
    value: Optional[int] = None


def process_data(input_str: str) -> dict:
    """Procesa datos de entrada.

    Args:
        input_str: Datos a procesar.

    Returns:
        Diccionario con resultado procesado.
    """
    logger.info("Procesamiento iniciado")
    ...
```

## Tests

- Framework: pytest + pytest-asyncio (async mode: auto)
- Coverage mínimo: 80% (enforced)
- `make test` para suite completa, `make test-quick` para core
