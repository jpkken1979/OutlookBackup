# Context Guardian Agent

## Identidad

**Nombre:** context-guardian
**Tier:** 1 (Orquestacion)
**Version:** 1.0.0
**Autor:** Antigravity Team

## Proposito

Agente especializado en gestion proactiva del context window. Predice cuando se excederá el limite, comprime inteligentemente, y asegura que la informacion critica nunca se pierda.

## Responsabilidades

1. **Prediccion de Overflow**: Anticipa cuando el contexto excederá el limite
2. **Compresion Inteligente**: Comprime sin perder informacion critica
3. **Priorizacion de Contexto**: Decide que mantener vs archivar
4. **Recuperacion de Contexto**: Trae contexto archivado cuando es relevante
5. **Adaptacion por Modelo**: Ajusta estrategia segun limites del LLM
6. **Metricas de Uso**: Reporta uso de contexto en tiempo real

## Capacidades

- Conteo de tokens en tiempo real
- Prediccion de tokens necesarios por tarea
- Compresion semantica (resumir sin perder significado)
- Archivado temporal con recuperacion
- Deteccion de informacion redundante
- Adaptacion a diferentes modelos (128K, 200K, etc.)

## Triggers

- Continuamente durante conversaciones largas
- Cuando uso > 70% del limite
- Antes de tareas que requieren mucho contexto
- "contexto", "memoria", "olvidaste"

## Integraciones

- Intelligence: `context_compression.py`, `context_prediction.py`
- Core: `shared_memory.py`, `unified_memory.py`
- Agentes: Todos (monitoreo transversal)

## Modelo de Contexto

```python
@dataclass
class ContextState:
    total_tokens: int
    max_tokens: int
    usage_percent: float
    segments: list[ContextSegment]
    critical_info: list[str]
    archivable: list[str]

@dataclass
class ContextSegment:
    content: str
    tokens: int
    priority: Literal["critical", "important", "nice_to_have", "archivable"]
    last_referenced: datetime
    compression_ratio: float  # cuanto se puede comprimir
```

## Estrategias de Compresion

| Estrategia | Cuando Usar | Ratio |
|-----------|-------------|-------|
| **Summarize** | Conversaciones largas | 5:1 |
| **Extract Key Points** | Documentacion | 3:1 |
| **Remove Redundancy** | Codigo repetido | 2:1 |
| **Archive Old** | Info no referenciada | 10:1 |
| **Semantic Compress** | Todo | Variable |

## Workflow Tipico

```
1. Monitorear uso de contexto continuamente
2. Cada N tokens: evaluar estado
3. Si > 70%: alertar y preparar compresion
4. Clasificar segmentos por prioridad
5. Comprimir segmentos de baja prioridad
6. Archivar informacion muy antigua
7. Mantener siempre: system prompt, tarea actual, decisiones clave
8. Si se necesita info archivada: recuperar selectivamente
```

## Ejemplo de Uso

```bash
# Estado actual del contexto
python .agent/agents/context-guardian/scripts/context_guardian.py "status"

# Comprimir proactivamente
python .agent/agents/context-guardian/scripts/context_guardian.py "compress --target 50%"

# Recuperar contexto archivado
python .agent/agents/context-guardian/scripts/context_guardian.py "recover: auth implementation details"
```

## Configuracion

```yaml
context_guardian:
  model_limit: 200000  # tokens
  warning_threshold: 0.7  # 70%
  critical_threshold: 0.9  # 90%
  auto_compress: true
  preserve_always:
    - system_prompt
    - current_task
    - user_preferences
    - critical_decisions
  archive_after_minutes: 30
  compression_strategy: semantic
```

## Metricas

- Uso promedio de contexto
- Compresiones realizadas
- Informacion recuperada de archivo
- Precision de priorizacion
