# Regla: Estándares Python

Aplica a todos los archivos `.py` del repositorio.

## Requisitos

- **Type hints** obligatorios en todas las funciones (parámetros + return)
- **Docstrings** en formato Google en funciones públicas
- **Pydantic** `BaseModel` con `Field()` para validación de datos
- **Logging** con `logger = logging.getLogger(__name__)`
- Linter: **ruff** (reglas: E, W, F, I, B, C4, UP, ARG, SIM)
- Type checker: **mypy**
- `shell=False` siempre en subprocess — usar `shlex.split()`
- Serialización segura: solo JSON o Pydantic para datos externos

## Plantilla de función

```python
import logging
from typing import Optional

logger = logging.getLogger(__name__)


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

- Framework: pytest + pytest-asyncio (`asyncio_mode = "auto"`)
- Coverage mínimo: 80%
- `make test` para suite completa
