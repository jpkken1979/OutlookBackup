# Workflow Rules para IAs - Antigravity Ecosystem

> Referencia de metodología de trabajo. NO se inyecta automáticamente.
> Las IAs deben consultar este archivo cuando trabajen en tareas complejas (3+ pasos).
> Para reglas del ecosistema (agentes, skills): ver `RULES.md`
> Para estándares de código: ver `.antigravity/rules.md`

---

## 1. Planificación Obligatoria

Entrar en **plan mode** para cualquier tarea no-trivial:

1. Escribir lista numerada de pasos ANTES de codificar
2. Incluir pasos de verificación (tests, checks, review), no solo "build"
3. Si algo se desvía, PARAR, actualizar el plan, indicar en qué paso falló

```
tasks/todo.md  → Plan con checkboxes [ ] y links a archivos
tasks/lessons.md → Lecciones aprendidas
```

---

## 2. Estrategia de Subagentes

- Un subagente por responsabilidad: planificación, investigación, código, testing, documentación
- Cada handoff define: input, output esperado, límites (qué NO hacer), constraints de tiempo/contexto
- Evitar overlap: no permitir que múltiples agentes modifiquen el mismo archivo sin reconciliación

**Consulta primero:** `.agent/agents/` tiene agentes especializados para cada responsabilidad.

---

## 3. Loop de Auto-Mejora

Después de cada corrección, agregar a `tasks/lessons.md`:

```
## [Fecha] - [Título del error]
- **Error**: Qué pasó
- **Root cause**: Por qué pasó
- **Regla nueva**: Qué hacer diferente
- **Ejemplo malo**: ❌ Código que causó el error
- **Ejemplo bueno**: ✅ Código correcto
```

Antes de tareas similares, revisar lecciones relevantes y declarar cuáles se aplicarán.

---

## 4. Verificación Antes de "Done"

NUNCA marcar una tarea como completada sin al menos UNA verificación concreta:

- **Código**: Correr tests, linters, type-checkers. Si no existen, proponer test mínimo
- **Comparar antes vs después**: Declarar qué cambió y qué se garantiza sin cambios
- **Para este ecosistema**: `pytest tests/ -v` y `ruff check .`

---

## 5. Elegancia Balanceada

- Para cambios no-triviales: intentar una segunda solución más simple
- Si un fix se siente hacky, preferir reescribir con insights del debugging
- NO over-engineer fixes pequeños; proponer refactors grandes como tareas separadas

---

## 6. Bug Fixing Autónomo

```
1. REPRODUCIR → con el input más simple posible
2. ROOT CAUSE → usar logs/traces/lectura dirigida (NO ediciones random)
3. FIX MÍNIMO → cambio más pequeño que resuelva el problema
4. TEST        → que falle antes y pase después del fix
5. RIESGO      → describir riesgo residual
```

No depender del usuario para guiar cada paso. Generar hipótesis, experimentos y conclusiones por cuenta propia.

---

## 7. Gestión de Tareas

1. **Planificar** → `tasks/todo.md` con checkboxes
2. **Verificar plan** → Para tareas grandes, esperar OK del usuario
3. **Trackear progreso** → Marcar items al completar
4. **Explicar cambios** → Resumen ejecutivo de máx 5 bullets
5. **Documentar resultados** → Actualizar `tasks/todo.md` con outcomes
6. **Capturar lecciones** → Actualizar `tasks/lessons.md`

---

## 8. Principios Core

| Principio | Regla |
|-----------|-------|
| **Simplicidad** | Solución más simple que cumpla requisitos. No agregar dependencias sin justificación |
| **No pereza** | No "TODO" sin nota de riesgo y plan de resolución |
| **Impacto mínimo** | Tocar solo lo necesario. Si cambias más, justificar |
| **Seguridad** | Nunca inventar o exponer datos sensibles |
| **Sin duplicación** | Buscar funciones/patrones existentes en el repo ANTES de crear nuevos |

---

## 9. Reglas de Prompts Estructurados

Para tareas que involucren LLMs o prompt engineering:

- Usar secciones explícitas: `<context>`, `<task>`, `<rules>`, `<output format>`
- Dar ejemplos pequeños de input/output cuando el formato importa
- Pedir razonamiento paso a paso para tareas complejas
- Para problemas grandes: dividir en subtareas encadenadas (prompt chaining)

---

## 10. Indice Rapido (ver seccion 15 para tabla completa)

---

## 11. SDD — Spec-Driven Development (tareas complejas)

Para tareas complejas (3+ archivos, nueva feature, refactor grande), usar el workflow SDD de 9 fases:

### Fases

| Fase | Nombre | Qué hacer |
|------|--------|-----------|
| 1 | **Explore** | Investigar el codebase, entender estado actual, identificar dependencias |
| 2 | **Propose** | Escribir propuesta con alcance, archivos afectados, riesgos |
| 3 | **Spec** | Definir especificación técnica: interfaces, contratos, tipos |
| 4 | **Plan** | Dividir en tareas atómicas con orden de ejecución y dependencias |
| 5 | **Implement** | Ejecutar el plan, un paso a la vez, verificando cada paso |
| 6 | **Test** | Escribir y ejecutar tests que validen la implementación |
| 7 | **Review** | Code review automatizado (lint, types, security) |
| 8 | **Document** | Actualizar docs si la feature lo requiere |
| 9 | **Finalize** | Commit, push, actualizar memoria y estado del proyecto |

### Cuándo usar SDD completo vs parcial

- **SDD completo (9 fases)**: Nueva feature, refactor arquitectónico, integración nueva
- **SDD parcial (fases 1,5,6,7)**: Bug fix, mejora menor, cambio de configuración
- **Sin SDD**: Cambios triviales (typos, docs, config simple)

### Slash commands SDD disponibles

- `/sdd` — Orquestador completo
- `/sdd-explore` — Solo fase 1 (exploración)
- `/sdd-propose` — Solo fase 2 (propuesta)

---

## 12. Jerarquía de Carga de Skills

Antes de implementar cualquier capacidad, seguir este orden:

1. **Tier 1 — Rules inyectadas**: `.claude/rules/` (auto-inyectadas, máxima prioridad)
2. **Tier 2 — Ecosistema Antigravity**: `.agent/skills/`, `.agent/skills-custom/`, `antigravity-remote` via MCP
3. **Tier 3 — skills.sh**: `npx skills find "descripción"` (registry externo)
4. **Tier 4 — Crear nuevo**: Solo si los 3 anteriores no cubren el caso

Ver `.claude/rules/skill-loading.md` para detalles.

---

## 13. Protocolo de Sub-Agentes

Reglas para delegar trabajo a sub-agentes:

### Test de inflación de contexto (antes de delegar)
- Tarea < 3 archivos y < 50 líneas: hacerla directamente
- Investigación amplia o cambios multi-archivo: delegar
- Tareas independientes: lanzar agentes en paralelo

### Cada sub-agente recibe
- Descripción clara (3-5 palabras)
- Prompt con TODO el contexto necesario (rutas absolutas)
- Restricciones explícitas (qué NO hacer)

### Cada sub-agente devuelve
- Resumen ejecutivo (1-3 líneas)
- Hallazgos con archivos y líneas
- Recomendaciones concretas
- Lista de cambios si modificó archivos

Ver `.claude/rules/subagent-protocol.md` para detalles.

---

## 14. Auto-Save Triggers para Memoria

Guardar automáticamente en `.claude/memory/` después de:

| Trigger | Qué guardar | Archivo |
|---------|-------------|---------|
| Decisión de arquitectura | Qué, por qué, alternativas descartadas | `decision_{topic}.md` |
| Bug resuelto con root cause | Síntoma, causa, fix, prevención | `bugfix_{topic}.md` |
| Descubrimiento del codebase | Qué, dónde, implicaciones | `discovery_{topic}.md` |
| Patrón nuevo establecido | Patrón, cuándo usarlo, ejemplo | `pattern_{topic}.md` |
| Config crítica modificada | Valor anterior vs nuevo, razón | `config_{topic}.md` |
| Cierre de sesión (3+ cambios) | Resumen, archivos, decisiones, pendientes | `session_{date}.md` |

Ver `.claude/rules/auto-save-triggers.md` para formato y detalles.

---

## 15. Cuándo Consultar Este Archivo (actualizado)

| Situación | Secciones |
|-----------|-----------|
| Tarea con 3+ pasos | 1, 7, 11 (SDD) |
| Bug fixing | 6 |
| Refactoring | 5, 11 |
| Después de un error | 3 |
| Antes de marcar "done" | 4 |
| Trabajo con subagentes | 2, 13 |
| Necesito una capacidad | 12 (skill loading) |
| Tarea compleja nueva | 11 (SDD completo) |
| Fin de sesión | 14 (auto-save) |

---

*Referencia de workflow para el ecosistema Antigravity v3.0.0*
*Consultar bajo demanda — no inyectar automáticamente para ahorrar tokens.*
