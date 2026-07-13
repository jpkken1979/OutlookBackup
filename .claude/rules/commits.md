# Regla: Formato de Commits

## Estructura

```
<type>(<scope>): <descripción en español>

[cuerpo opcional]

Co-Authored-By: Claude <noreply@anthropic.com>
```

## Tipos permitidos

| Tipo | Cuándo usarlo |
|------|---------------|
| `feat` | Nueva funcionalidad |
| `fix` | Corrección de bug |
| `docs` | Solo documentación |
| `style` | Formato, sin cambio lógico |
| `refactor` | Refactorización sin cambio de comportamiento |
| `test` | Añadir o corregir tests |
| `chore` | Mantenimiento, deps, configuración |

## Ejemplos

```
feat(agents): agregar agente especializado en análisis de costos
fix(nexus): corregir race condition en splash screen lifecycle
chore(metrics): actualizar métricas de rendimiento de agentes
docs(skills): documentar estructura de skills modulares
```

## Reglas adicionales

- Descripción siempre en **español**
- Scope en inglés (nombre del módulo/directorio)
- Primera línea máximo 72 caracteres
- Usar imperative mood en el tipo pero descripción en indicativo
