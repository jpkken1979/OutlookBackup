# SDD Fase 4: Design

Diseña la arquitectura, interfaces y flujo de datos de la solución.
Traduce la especificación en un blueprint implementable.

## Prerequisito

La Fase 3 (Spec) debe estar completa y aprobada.

## Acciones

1. **Diseñar arquitectura de componentes**
   - Diagrama ASCII de componentes y sus relaciones
   - Ubicación de cada componente en la arquitectura de 4 capas (Directiva, Contexto, Ejecución, Observabilidad)
   - Interfaces públicas de cada componente

2. **Definir tipos e interfaces**
   - Types/interfaces completos en el lenguaje correspondiente
   - Pydantic models para Python, TypeScript interfaces para TS
   - Enums y constantes

3. **Diseñar flujo de datos**
   - Diagrama de secuencia ASCII para el flujo principal
   - Puntos de validación y transformación
   - Manejo de estado

4. **Diseñar manejo de errores**
   - Jerarquía de excepciones si aplica
   - Estrategia de retry/fallback
   - Logging y observabilidad

5. **Planificar la estructura de archivos**
   - Archivos nuevos a crear con su propósito
   - Archivos existentes a modificar
   - Tests correspondientes

## Output esperado

```markdown
## Diseño Arquitectónico — [nombre del cambio]

### Diagrama de componentes
```
┌─────────────────┐     ┌─────────────────┐
│  ComponenteA    │────→│  ComponenteB    │
│  (capa: X)      │     │  (capa: Y)      │
└────────┬────────┘     └─────────────────┘
         │
         ▼
┌─────────────────┐
│  ComponenteC    │
│  (capa: Z)      │
└─────────────────┘
```

### Tipos e interfaces

```python
# Python
from typing import Protocol

class NombreProtocol(Protocol):
    def metodo(self, arg: str) -> Result: ...
```

```typescript
// TypeScript (si aplica)
interface NombreInterface {
  metodo(arg: string): Promise<Result>;
}
```

### Flujo de datos
```
Usuario → [Validación] → [Procesamiento] → [Persistencia] → [Respuesta]
                │                                    │
                └── Error → [Logger] ──────────────→ │
```

### Estructura de archivos
| Archivo | Acción | Propósito |
|---------|--------|-----------|
| `ruta/nuevo.py` | Crear | descripción |
| `ruta/existente.py` | Modificar | qué cambiar |
| `tests/test_nuevo.py` | Crear | tests para nuevo.py |

### Decisiones de diseño
| Decisión | Alternativa descartada | Razón |
|----------|----------------------|-------|
| ... | ... | ... |

### Siguiente paso
La Fase 5 (Tasks) descompondrá este diseño en tareas ejecutables ordenadas.
```

---

Diseña la arquitectura para: $ARGUMENTS
