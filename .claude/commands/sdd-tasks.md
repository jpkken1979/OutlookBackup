# SDD Fase 5: Tasks

Descompone el diseño aprobado en tareas ejecutables, ordenadas por dependencia.
Cada tarea es una unidad de trabajo autocontenida que puede implementarse y verificarse independientemente.

## Prerequisito

La Fase 4 (Design) debe estar completa y aprobada.

## Acciones

1. **Descomponer en tareas atómicas**
   - Cada tarea modifica 1-3 archivos máximo
   - Cada tarea tiene un criterio de verificación claro
   - Tareas ordenadas por dependencia (las dependencias van primero)

2. **Clasificar cada tarea**
   - Tipo: create / modify / test / config / docs
   - Prioridad: P0 (bloqueante) / P1 (necesaria) / P2 (nice-to-have)
   - Complejidad: baja / media / alta

3. **Definir orden de ejecución**
   - Identificar tareas que pueden ejecutarse en paralelo
   - Identificar dependencias estrictas entre tareas
   - Agrupar tareas relacionadas

4. **Estimar esfuerzo**
   - Tiempo estimado por tarea
   - Tiempo total del flujo completo

## Output esperado

```markdown
## Plan de Tareas — [nombre del cambio]

### Resumen
- Total de tareas: N
- Tiempo estimado total: X minutos
- Tareas P0 (bloqueantes): N
- Tareas parallelizables: N

### Tareas

#### T1: [nombre descriptivo] — P0
- **Tipo**: create
- **Archivos**: `ruta/archivo.py`
- **Descripción**: qué hacer exactamente
- **Dependencias**: ninguna
- **Verificación**: cómo verificar que está completa
- **Tiempo estimado**: X min

#### T2: [nombre descriptivo] — P0
- **Tipo**: modify
- **Archivos**: `ruta/existente.py`
- **Descripción**: qué cambiar
- **Dependencias**: T1
- **Verificación**: ...
- **Tiempo estimado**: X min

#### T3: [nombre descriptivo] — P1
- **Tipo**: test
- **Archivos**: `tests/test_nuevo.py`
- **Descripción**: tests para T1 y T2
- **Dependencias**: T1, T2
- **Verificación**: `pytest tests/test_nuevo.py -v` pasa
- **Tiempo estimado**: X min

...

### Grafo de dependencias
```
T1 ──→ T2 ──→ T4
  ╲         ╱
   └→ T3 ─┘
T5 (independiente)
```

### Orden de ejecución sugerido
1. T1 (base)
2. T2, T5 (paralelo)
3. T3 (depende de T1, T2)
4. T4 (depende de T2, T3)

### Siguiente paso
La Fase 6 (Apply) implementará estas tareas en el orden definido.
```

---

Descompón en tareas: $ARGUMENTS
