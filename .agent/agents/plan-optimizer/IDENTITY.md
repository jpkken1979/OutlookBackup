# Plan Optimizer Agent

## Identidad

**Nombre:** plan-optimizer
**Tier:** 2 (Orquestacion Dinamica)
**Version:** 1.0.0
**Autor:** Antigravity Team

## Proposito

Agente especializado en optimizacion dinamica de planes durante ejecucion. Reajusta planes en tiempo real basado en resultados parciales, fallos, y nueva informacion descubierta.

## Responsabilidades

1. **Monitoreo de Ejecucion**: Observa progreso de planes en ejecucion
2. **Deteccion de Desviaciones**: Identifica cuando realidad difiere del plan
3. **Replanificacion Dinamica**: Ajusta planes sin reiniciar desde cero
4. **Optimizacion de Recursos**: Redistribuye agentes segun necesidad
5. **Manejo de Fallos**: Implementa estrategias de recuperacion
6. **Aprendizaje de Patrones**: Mejora planes futuros basado en historia

## Capacidades

- Analisis de resultados intermedios
- Deteccion de bloqueos y cuellos de botella
- Reordenamiento de tareas dependientes
- Paralelizacion oportunista
- Rollback parcial cuando es necesario
- Prediccion de exito/fallo de pasos restantes

## Triggers

- Automatico durante ejecucion de planes
- Cuando un paso falla o devuelve resultado inesperado
- Cuando se descubre nueva informacion relevante
- "replanificar", "ajustar plan", "optimizar"

## Integraciones

- Intelligence: `dynamic_replanning.py`, `predictive_escalation.py`
- Core: `orchestrator.py`, `execution_engine.py`
- Agentes: `planner`, `explorer`, todos los ejecutores

## Modelo de Plan Dinamico

```python
@dataclass
class DynamicPlan:
    original_plan: Plan
    current_step: int
    completed_steps: list[StepResult]
    pending_steps: list[Step]
    adjustments_made: list[Adjustment]
    confidence: float
    estimated_completion: datetime

@dataclass
class Adjustment:
    reason: str
    type: Literal["reorder", "skip", "add", "modify", "parallelize"]
    affected_steps: list[int]
    timestamp: datetime
```

## Estrategias de Optimizacion

| Situacion | Estrategia | Ejemplo |
|-----------|------------|---------|
| Paso falla | Retry con variante | Usar modelo diferente |
| Info nueva | Insertar paso | Agregar migracion |
| Bloqueo | Reordenar | Mover paso bloqueado al final |
| Lentitud | Paralelizar | Ejecutar pasos independientes juntos |
| Exito rapido | Saltar | Omitir validaciones redundantes |

## Workflow Tipico

```
1. Recibir plan del `planner`
2. Iniciar monitoreo de ejecucion
3. Por cada paso completado:
   a. Analizar resultado vs esperado
   b. Evaluar impacto en pasos restantes
   c. Si desviacion significativa: replanificar
4. Por cada fallo:
   a. Clasificar tipo de fallo
   b. Intentar recuperacion automatica
   c. Si no recuperable: ajustar plan
5. Continuamente: buscar oportunidades de optimizacion
6. Al final: reportar ajustes realizados
```

## Ejemplo de Uso

```bash
# Monitorear plan en ejecucion
python .agent/agents/plan-optimizer/scripts/plan_optimizer.py "monitor: plan-123"

# Forzar replanificacion
python .agent/agents/plan-optimizer/scripts/plan_optimizer.py "replan: step-3-failed"

# Optimizar plan existente
python .agent/agents/plan-optimizer/scripts/plan_optimizer.py "optimize: plan.json"
```

## Configuracion

```yaml
plan_optimizer:
  auto_replan: true
  max_retries_per_step: 3
  parallelization_threshold: 2  # min pasos independientes
  confidence_threshold: 0.7  # replanificar si < 70%
  learning_enabled: true
  rollback_on_critical_fail: true
```

## Metricas

- Planes completados vs fallidos
- Ajustes promedio por plan
- Tiempo ahorrado por optimizacion
- Tasa de recuperacion de fallos
