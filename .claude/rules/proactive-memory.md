# Regla: Sugerencias Proactivas de Memoria y Auto-Save

Aplica a todas las sesiones de Claude Code en este repositorio.
Funciona con `antigravity-memory` (MCP) cuando esta disponible, y siempre con `.claude/memory/` (archivos locales).

---

## Parte 1: Sugerencias proactivas (pre-creacion)

Antes de **crear** una funcion, componente, modulo o patron nuevo, llama `memory_suggest` con:
- `intent`: descripcion de lo que vas a crear
- `type`: "function", "component", "module", "pattern" o "any"
- `context`: framework o lenguaje si es relevante

### Si hay trabajo previo (`has_prior_work: true`)

1. Presenta las sugerencias al usuario antes de escribir codigo
2. Pregunta si quiere reutilizar, adaptar o crear desde cero
3. Solo procede a crear codigo nuevo si el usuario lo confirma

### Si no hay trabajo previo (`has_prior_work: false`)

Procede normalmente a crear el codigo.

### Cuando NO llamar memory_suggest

- Ediciones menores a codigo existente (fixes, refactors)
- Archivos de configuracion
- Tests (a menos que sea un framework de testing nuevo)
- Documentacion

---

## Parte 2: Auto-save triggers (post-accion)

Despues de completar acciones significativas, guardar automaticamente en `.claude/memory/`.
Ver `.claude/rules/auto-save-triggers.md` para la lista completa de triggers y formato.

### Triggers principales

| Trigger | Archivo destino | Cuando |
|---|---|---|
| `decision` | `decision_{topic}.md` | Decisiones de arquitectura o diseno |
| `bugfix` | `bugfix_{topic}.md` | Bugs no triviales resueltos con root cause |
| `discovery` | `discovery_{topic}.md` | Comportamiento no documentado o gotchas |
| `pattern` | `pattern_{topic}.md` | Nuevos patrones o convenciones establecidas |
| `config` | `config_{topic}.md` | Cambios de configuracion del ecosistema |
| `session` | `session_{date}.md` | Cierre de sesion significativa (3+ cambios) |

### Auto-guardar codigo nuevo

Despues de **crear** codigo nuevo exitosamente (funciones, componentes, modulos), guardar una referencia:

1. **En antigravity-memory** (si disponible):
```
memory_store({
  "content": "Cree [tipo] [nombre] en [archivo] -- [descripcion corta de que hace]",
  "metadata": {"type": "[function|component|module]", "project": "[nombre del proyecto]"}
})
```

2. **En `.claude/memory/`** (siempre):
Crear archivo con el formato definido en `auto-save-triggers.md` usando trigger `pattern` o `decision` segun corresponda.

### Cuando NO auto-guardar

- Ediciones menores (typos, formatting)
- Cambios ya documentados en CLAUDE.md
- Informacion derivable del codigo o git log
- Tareas rutinarias sin decisiones significativas

---

## Parte 3: Comando de sesion

Usar `/session-summary` al final de sesiones significativas para generar un resumen completo, guardarlo en memoria y actualizar `ESTADO_PROYECTO.md`.
