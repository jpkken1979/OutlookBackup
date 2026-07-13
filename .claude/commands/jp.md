# /jp — Ejecutor Impecable del Ecosistema Antigravity

> Cuando invocás `/jp` (sin args), el sistema hace un análisis inteligente del estado actual
> y te presenta las mejores acciones a ejecutar. Cuando ponés `/jp <tarea>`, ejecuta directamente.

## Modo sin argumentos: Análisis Inteligente

Cuando ponés `/jp` solo, el sistema automáticamente:

### 1. Escaneo del estado actual

```
git status          → cambios pendientes sin commitear
git diff --stat      → archivos modificados
make test-quick      → tests que pueden estar fallando
ESTADO_PROYECTO.md   → ultimo trabajo realizado
```

### 2. Presentación inteligente

Basado en el análisis, el sistema presenta opciones:

```
## Contexto detectado

Trabajo pendiente:
- 3 archivos modificados en .agent/core/
- Tests: 1401 passing, 1 failing (pre-existing)
- Ultimo commit: hace 2 horas

## Opciones disponibles

[1] Commit + push cambios pendientes (Recomendado)
    Archivos: orchestrator.py, brain.py, memory.py

[2] Continuar trabajo anterior (ESTADO_PROYECTO.md)
    "Integracion nuevo MCP server"

[3] Ejecutar auditoria rapida
    Seguridad + calidad del codigo

[4] Help - ver todos los comandos

Elegí [1-4] o describí la tarea:
```

### 3. Ejecución según selección

| Opción | Acción |
|---|---|
| 1 | Commit con mensaje inteligente basado en archivos cambiados |
| 2 | Leer ESTADO_PROYECTO.md y continuar el trabajo |
| 3 | Ejecutar auditoría rápida con sub-agents |
| custom | Interpretar como tarea y ejecutar con /jp <tarea> |

### 4. Si no hay trabajo pendiente

```
## Estado limpio

No hay cambios pendientes. El repo está sincronizado.

Sugerencias:
- [N]uevo trabajo: describí la tarea a implementar
- [A]uditar: revisión completa del repo
- [B]uild: compilar y verificar Nexus
- [R]ecall: buscar contexto en el Brain

> _
```

## Modo con argumentos: /jp <tarea>

Igual que antes — clasificar y ejecutar:

```
/jp implementar un logger estructurado
/jp debuggear el error de auth en el gateway
/jp auditar la seguridad del bot
/jp refactorizar el modulo de memoria
```

## Flujo inteligente completo

```
/jp (sin args)
    ↓
┌─ Hay cambios pendientes?
│   ├─ Si → mostrar opciones de commit/continuar
│   └─ No → mostrar sugerencias de trabajo
↓
Si usuario selecciona → ejecutar acción
Si usuario describe tarea → /jp <tarea>
```

## Reglas inquebrantables

| Regla | Por qué |
|---|---|
| `evidence_before_assertions` | No decir "funciona" sin tests |
| `never_leave_uncommitted` | El trabajo se sincroniza entre PCs |
| `persistence_brain` | Conocimiento nuevo va al Brain |
| `scope_control` | Si es muy grande: milestone 1, validar, continuar |
| `fallback_tiers` | Si un agente falla, intentar siguiente tier |

## Alias inteligentes

```
/jp           → Análisis inteligente + acciones sugeridas
/jp s         → Skip análisis, mostrar estado rápido
/jp n         → Nuevo trabajo (modo implementar)
/jp a         → Auditoria rapida
/jp c         → Commit pendiente
/jp b         → Build Nexus
```

## Implementation notes

- El análisis usa sub-agents en paralelo para velocidad
- Solo carga módulos según la acción seleccionada
- Nunca deja trabajo sin commitear
- Siempre hace Brain ingest del trabajo realizado

---

**version**: 3.0.0
**autor**: K. Kaneshiro
**fecha**: 2026-05-09
**tags**: `execution, orchestration, ecosystem, brain, persistence, smart`