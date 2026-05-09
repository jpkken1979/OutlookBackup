---
name: jp
description: |
  Orquestador autónomo inteligente. Cuando el usuario dice "/jp", "/ejecutar",
  "/jp hacer X", "/continuar", ejecuta un plan usando todos los subagentes y skills
  disponibles de forma orquestada y eficiente. Usa las mejores prácticas:
  divide en pasos并行 ejecuta subagentes en paralelo, retry en caso de error,
  y reporta progreso en vivo.
  SPECIALMENTE para tareas complejas que requieren múltiples agentes y skills.
triggers:
  - "/jp"
  - "/ejecutar"
  - "/jp hacer"
  - "/continuar"
  - "/autonomous"
  - "ejecuta esto"
  - "continúa con"
---

# JP — Orquestador Autónomo Inteligente

## Propósito

Recibe un **objetivo libre** del usuario → genera un **plan estructurado** →
espera **aprobación** → ejecuta de forma **autónoma** usando subagentes y skills
de forma paralela, con retry automático, abort threshold, y reporte de progreso.

**No es un ejecutor lineal.** Es un orquestador que:
1. Divide la tarea en pasos independientes
2. Ejecuta en paralelo lo que puede并行
3. Retry en caso de error (hasta 3 intentos)
4. Reporta progreso en vivo
5. Permite abortar si el threshold de errores supera el 30%

## Uso

```bash
# Ejecutar una tarea
python .agent/skills-custom/jp/scripts/main.py --task "Refactorizar el módulo de auth"

# Continuar tarea pendiente
python .agent/skills-custom/jp/scripts/main.py --continue

# Contexto específico
python .agent/skills-custom/jp/scripts/main.py --task "Agregar tests al módulo de users" --context ./mi-app
```

## Argumentos

| Arg | Descripción | Default |
|-----|-------------|---------|
| `--task` | Objetivo libre de la tarea | (requerido si no es --continue) |
| `--context` | Path del proyecto/contexto | `.` |
| `--continue` | Continuar tarea pendiente | false |
| `--parallel` | Máx subagentes en paralelo | 5 |
| `--retry` | Intentos max retry por paso | 3 |
| `--abort-threshold` | Threshold abort (%) | 30 |
| `--verbose` | Output detallado | false |

## Flujo de Ejecución

### STEP 1: Recibir y Analizar Objetivo

Recibir el objetivo libre del usuario. Analizar:
- Qué necesita hacer (verbo + objeto)
- Qué archivos/rutas están involucrados
- Qué skills/agentes podrían ser necesarios
- Dependencias entre pasos

```python
# Análisis del objetivo
task_breakdown = {
    "action": "refactorizar" | "implementar" | "auditar" | "testear" | "documentar" | "migrar",
    "target": "módulo/componente específico",
    "scope": ["archivo1", "archivo2"],
    "required_skills": ["skill1", "skill2"],
    "required_agents": ["agent1", "agent2"],
    "steps": [
        {"id": 1, "action": "...", "parallel_group": "A"},
        {"id": 2, "action": "...", "parallel_group": "A"},
        {"id": 3, "action": "...", "depends_on": [2]},
    ]
}
```

### STEP 2: Generar Plan

Generar un plan estructurado basado en el análisis:

```markdown
## Plan: [OBJETIVO]

### Pasos

| # | Acción | Skills/Agentes | Depende de | Parallel Group |
|---|--------|----------------|-----------|----------------|
| 1 | Analizar código actual | Explore agent | - | A |
| 2 | Detectar issues | Code-reviewer agent | 1 | A |
| 3 | Implementar fix | Code-simplifier agent | 2 | B |
| 4 | Agregar tests | Test-engineer agent | 3 | B |
| 5 | Actualizar docs | Document-specialist agent | 4 | C |

### Estimación
- Total pasos: 5
- Ejecución paralela: 2 grupos (A, B)
- Tiempo estimado: ~15-20 min
```

**Preguntar al usuario: "¿Procedo con el plan?"**

### STEP 3: Ejecutar Plan (con Approval Gate)

Una vez aprobado, ejecutar en fases:

#### FASE A: Ejecución paralela (Steps sin dependencias)

Ejecutar todos los steps del parallel_group "A" en paralelo.

```python
# Ejemplo de ejecución并行
from concurrent.futures import ThreadPoolExecutor, as_completed

parallel_steps = [s for s in steps if s.parallel_group == "A"]
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {executor.submit(execute_step, s): s for s in parallel_steps}
    results = {}
    for future in as_completed(futures):
        step = futures[future]
        try:
            result = future.result()
            results[step.id] = {"status": "success", "result": result}
        except Exception as e:
            results[step.id] = {"status": "error", "error": str(e)}
            if should_retry(step, e):
                retry_step(step)
            else:
                error_count += 1
```

#### FASE B: Ejecución secuencial (Steps con dependencias)

Ejecutar pasos que dependen de resultados previos.

```python
for step in sequential_steps:
    prev_results = get_results(step.depends_on)
    result = execute_step(step, context=prev_results)
    if result.status == "error" and should_abort(result):
        abort_plan()
        break
```

### STEP 4: Reporte de Progreso

Reportar en vivo cada vez que un step complete:

```markdown
## Progreso: [OBJETIVO]

| # | Step | Status | Tiempo |
|---|------|--------|--------|
| 1 | Analizar código | ✅ done | 2m |
| 2 | Detectar issues | ✅ done | 3m |
| 3 | Implementar fix | 🔄 in-progress | 5m |
| 4 | Agregar tests | ⏳ pending | - |
| 5 | Actualizar docs | ⏳ pending | - |

**Errores**: 0/5
**Progreso**: 40%
```

### STEP 5: Finalización

Al completar todos los steps:

```markdown
## ✅ Ejecución Completada

**Objetivo**: [OBJETIVO]
**Duración total**: ~18 min
**Steps**: 5/5 completados
**Errores**: 0/5
**Resultado**: [resumen del trabajo realizado]

### Cambios realizados
- [archivo1]: refactorizado el módulo de auth
- [archivo2]: agregados 12 tests nuevos
- [archivo3]: actualizada documentación

### Siguientes pasos sugeridos
1. Run tests para verificar
2. Revisar cambios con git diff
3. Hacer commit
```

---

## Habilidades del Orquestador

### Detección automática de skills/agentes necesarios

| Tipo de tarea | Skills/Agentes recomendados |
|---------------|------------------------------|
| Refactorización | `code-simplifier`, `code-reviewer`, `Explore` |
| Nueva feature | `scaffold-generator`, `code-reviewer`, `test-engineer` |
| Auditoría | `auditoriajp`, `security-reviewer`, `code-reviewer` |
| Tests | `test-engineer`, `code-reviewer` |
| Documentación | `document-specialist`, `writer` |
| Bug fix | `debugger`, `code-reviewer`, `test-engineer` |
| Migración | `Explore`, `code-reviewer`, `test-engineer` |
| Build/Deploy | `sdd-apply`, `code-reviewer` |

### Retry automático

```python
def should_retry(step, error) -> bool:
    """Decide si hacer retry de un step."""
    if step.attempts >= max_retries:
        return False
    # Retry en errores transitorios
    transient_errors = ["timeout", "connection", "temporary"]
    return any(e in str(error).lower() for e in transient_errors)
```

### Abort threshold

```python
def should_abort(results) -> bool:
    """Determina si abortar la ejecución."""
    total = len(results)
    errors = sum(1 for r in results.values() if r.status == "error")
    threshold = (errors / total) * 100 if total > 0 else 0
    return threshold >= 30  # 30% de errores = abort
```

---

## Integración con el Ecosistema

El JP orchestrator usa:

| Componente | Cómo se usa |
|------------|-------------|
| `Explore` agent | Análisis inicial del codebase |
| `code-reviewer` | Code review de cambios |
| `security-reviewer` | Verificación de seguridad |
| `test-engineer` | Generación de tests |
| `auditoriajp` skill | Auditorías completas |
| `scaffold-generator` | Generación de scaffolding |
| `context7` | Best practices y documentación |
| `brain` (MCP) | Consulta de contexto previo |

---

## Edge Cases

| Caso | Manejo |
|------|--------|
| Objetivo ambiguo | Pedir clarificación antes de proceder |
| Dependencias circulares | Detectar y reportar error de diseño |
| Step falla pero hay retry | Retry automático hasta max_retries |
| Abort threshold superado | Detener ejecución, reportar estado |
| No hay skills para la tarea | Usar agents genéricos (Explore, code-reviewer) |
| Tarea toma > 1 hora | Reportar progreso cada 5 min, allow pause |

---

## Output

Entregar al usuario:
1. **Plan generado** (antes de ejecutar)
2. **Reporte de progreso** (en vivo)
3. **Resultado final** (summary + cambios)
4. **Sugerencias** (próximos pasos)

---

## Metadata de Ejecución

```yaml
jp_execution:
  task: string
  start_time: ISO8601
  end_time: ISO8601
  total_steps: number
  completed_steps: number
  failed_steps: number
  retries: number
  abort_triggered: boolean
  final_status: success | partial | aborted
```
