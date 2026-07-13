# SDD Fase 3: Spec

Escribe la especificación técnica detallada de la solución aprobada.
Este documento es el contrato que guía la implementación en fases posteriores.

## Prerequisito

Las Fases 1 (Explore) y 2 (Propose) deben estar completas, con una propuesta aprobada por el usuario.

## Acciones

1. **Definir el alcance exacto**
   - Qué se incluye y qué queda fuera (scope boundary)
   - Criterios de aceptación medibles

2. **Especificar interfaces y contratos**
   - Firmas de funciones/métodos con type hints completos
   - Schemas de datos (Pydantic models, TypeScript types)
   - Endpoints API si aplica (método, path, request/response)
   - Eventos y callbacks

3. **Documentar comportamiento esperado**
   - Flujo principal (happy path)
   - Casos edge y manejo de errores
   - Valores por defecto y límites

4. **Definir criterios de verificación**
   - Tests unitarios necesarios
   - Tests de integración necesarios
   - Validaciones de lint/typecheck esperadas
   - Métricas de performance si aplica

5. **Identificar dependencias de implementación**
   - Librerías nuevas necesarias
   - Cambios en configuración
   - Migraciones de datos si aplica

## Output esperado

```markdown
## Especificación Técnica — [nombre del cambio]

### Alcance
**Incluido**: ...
**Excluido**: ...

### Criterios de aceptación
1. [ ] Criterio medible 1
2. [ ] Criterio medible 2
...

### Interfaces

#### [Nombre de la interfaz/función]
```python
# o typescript, según corresponda
def nombre_funcion(param1: str, param2: int = 0) -> ResultType:
    """Descripción."""
    ...
```

#### Schemas de datos
```python
class NombreModel(BaseModel):
    campo1: str = Field(..., description="...")
    campo2: int = Field(default=0, ge=0)
```

### Comportamiento

#### Flujo principal
1. Paso 1
2. Paso 2
...

#### Manejo de errores
| Error | Causa | Respuesta |
|-------|-------|-----------|
| ... | ... | ... |

### Verificación
- Tests unitarios: lista de test cases
- Tests integración: escenarios end-to-end
- Lint: sin errores ruff/eslint
- Types: sin errores mypy/tsc

### Dependencias
- Nuevas librerías: ...
- Config changes: ...
- Migraciones: ...

### Notas de implementación
Consideraciones adicionales para la fase de diseño y apply.
```

---

Especifica técnicamente: $ARGUMENTS
