# SDD Fase 6: Apply

Implementa los cambios según la especificación, diseño y plan de tareas aprobados.
Sigue estrictamente el orden de tareas definido en Fase 5.

## Prerequisito

Las Fases 3 (Spec), 4 (Design) y 5 (Tasks) deben estar completas y aprobadas.

## Acciones

1. **Ejecutar tareas en orden**
   - Seguir el orden de ejecución definido en Fase 5
   - Completar una tarea antes de iniciar la siguiente (salvo tareas paralelas)
   - Reportar progreso después de cada tarea

2. **Por cada tarea**
   - Leer los archivos a modificar (si existen)
   - Implementar los cambios usando Edit (preferido) o Write (archivos nuevos)
   - Verificar que el cambio compila/no rompe imports
   - Respetar convenciones del ecosistema:
     - Python: type hints, docstrings Google, ruff-compatible
     - TypeScript: strict mode, no `any`, componentes funcionales
     - Rust: cargo check limpio

3. **Regla de delegación**
   - Tarea con 1-2 archivos → implementar inline
   - Tarea con 3+ archivos → considerar sub-agente
   - Si una tarea falla, pausar y reportar antes de continuar

4. **Validación incremental**
   - Después de cada tarea, verificar que no se rompe nada existente
   - Si hay tests existentes relacionados, ejecutarlos
   - No dejar imports rotos o variables sin usar

## Output esperado

Después de cada tarea completada:

```markdown
### Tarea TN: [nombre] — Completada

**Archivos modificados**:
- `ruta/archivo.py` — descripción del cambio
- ...

**Cambios clave**:
- Descripción concisa de lo implementado

**Estado**: completada / con advertencias / bloqueada
```

Al finalizar todas las tareas:

```markdown
## Resumen de Implementación — [nombre del cambio]

### Tareas completadas: N/N

### Archivos creados
- `ruta/nuevo.py`

### Archivos modificados
- `ruta/existente.py`

### Pendientes (si hay)
- ...

### Siguiente paso
La Fase 7 (Verify) ejecutará tests, lint y typecheck para validar la implementación.
```

## Reglas de seguridad

- NO hardcodear tokens, passwords o API keys
- NO usar `shell=True` en subprocess
- Validar inputs en los bordes del sistema
- Sanitizar mensajes de error (no exponer paths internos)

---

Implementa los cambios para: $ARGUMENTS
