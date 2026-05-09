# IAPOI — Investiga, Analiza, Piensa, Planea, Orquesta, Implementa

Metodología de 6 fases para resolver cualquier tarea compleja de forma autónoma e inteligente.
Cada fase produce un output concreto que alimenta la siguiente, usando sub-agentes y skills del ecosistema.

## Fases

| # | Fase | Acción | Output |
|---|------|--------|--------|
| 1 | **Investiga** | Buscar en web, codebase, memoria y Obsidian | Reporte de hallazgos con fuentes |
| 2 | **Analiza** | Evaluar hallazgos, identificar patrones y gaps | Diagnóstico con pros/contras |
| 3 | **Piensa** | Diseñar la solución, considerar trade-offs | Diseño técnico con decisiones |
| 4 | **Planea** | Descomponer en tareas concretas y ordenadas | TodoList con dependencias |
| 5 | **Orquesta** | Ejecutar tareas en paralelo con sub-agentes | Implementación con progreso |
| 6 | **Implementa** | Integrar, verificar, testear y commitear | Código verificado + commit |

## Instrucciones

Cuando el usuario describe una tarea, objetivo o problema:

### Fase 1: INVESTIGA
1. Usar la herramienta Agent (subagent_type: Explore) para investigar el codebase
2. Buscar en la web con WebSearch si la tarea involucra tecnologías externas
3. Consultar la memoria del proyecto via Knowledge Bridge (`/v1/knowledge/search`)
4. Verificar si ya existen skills, agentes o soluciones en el ecosistema
5. **Output**: Reporte de 5-10 hallazgos relevantes con archivos y fuentes

### Fase 2: ANALIZA
1. Evaluar cada hallazgo: ¿es suficiente? ¿hay gaps?
2. Identificar dependencias, riesgos y restricciones
3. Comparar con soluciones existentes del ecosistema
4. Clasificar la complejidad: trivial / medio / complejo / investigación
5. **Output**: Diagnóstico honesto con "lo que funciona", "lo que no", "lo que falta"

### Fase 3: PIENSA
1. Diseñar la solución basándose en el análisis
2. Considerar trade-offs explícitamente (rendimiento vs simplicidad, etc.)
3. Identificar los archivos que se van a tocar
4. Decidir qué sub-agentes o skills del ecosistema usar
5. Validar contra las reglas del proyecto (CLAUDE.md, RULES.md)
6. **Output**: Diseño técnico con decisiones justificadas

### Fase 4: PLANEA
1. Crear un TodoList detallado con TodoWrite
2. Ordenar tareas por dependencias (no paralelizar lo que depende de otro)
3. Estimar qué tareas pueden ejecutarse en paralelo
4. Identificar qué tareas requieren sub-agentes vs inline
5. Definir criterios de éxito para cada tarea
6. **Output**: TodoList creado, pausar y pedir aprobación al usuario

### Fase 5: ORQUESTA
1. Lanzar sub-agentes en paralelo para tareas independientes (Agent tool)
2. Para tareas simples (< 3 archivos), ejecutar directamente
3. Marcar cada tarea como completada en el TodoList al terminar
4. Si un sub-agente falla, diagnosticar antes de reintentar
5. Mantener al usuario informado del progreso
6. **Output**: Todas las tareas ejecutadas con progreso visible

### Fase 6: IMPLEMENTA
1. Verificar que todos los cambios están integrados correctamente
2. Correr linters (`ruff check`, `npm run lint`)
3. Correr tests relevantes (`pytest`, `npm test`)
4. Si hay errores, arreglarlos iterativamente
5. Commitear con mensaje convencional en español
6. Push al branch correspondiente
7. **Output**: Código verificado, testeado y commiteado

## Reglas de ejecución

- **Pausar después de Fase 4 (Planea)** para pedir aprobación del plan
- Las fases 1-3 pueden ejecutarse sin pausa si la tarea es clara
- Las fases 5-6 se ejecutan solo después de aprobación
- Siempre explicar el POR QUÉ antes del CÓMO (modo gentleman)
- Respuestas en español, código en inglés
- Usar sub-agentes para investigación amplia (> 4 archivos)
- Hacer inline para tareas puntuales (< 3 archivos)

## Uso de herramientas por fase

| Fase | Herramientas principales |
|------|-------------------------|
| Investiga | Agent(Explore), WebSearch, Grep, Glob, Knowledge Bridge |
| Analiza | Read, Grep, Agent(Explore) |
| Piensa | Read (archivos clave), CLAUDE.md, RULES.md |
| Planea | TodoWrite |
| Orquesta | Agent(general-purpose), Agent(worktree), Bash |
| Implementa | Edit, Write, Bash (tests/lint), Git |

## Atajos

- Si el usuario dice "rápido" o "fast": comprimir fases 1-3 en una sola y ejecutar
- Si el usuario dice "solo investiga": ejecutar solo fase 1 y reportar
- Si el usuario dice "implementa directo": asumir fases 1-4 y ir a 5-6
- El usuario puede saltar fases con "skip" o ir a una con "fase N"

## Ejemplo de invocación

```
/iapoi Necesito agregar soporte para WebSocket en el gateway
```

Resultado: investiga el estado actual → analiza qué tiene y qué falta → piensa el diseño → planea las tareas → orquesta sub-agentes → implementa y commitea.
