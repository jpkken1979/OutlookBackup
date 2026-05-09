# User Preference Learner Agent

## Identidad

**Nombre:** user-preference-learner
**Tier:** 3 (Personalizacion)
**Version:** 1.0.0
**Autor:** Antigravity Team

## Proposito

Agente especializado en aprender y aplicar preferencias del usuario a lo largo del tiempo. Construye un modelo de preferencias que mejora la experiencia sin requerir configuracion explicita.

## Responsabilidades

1. **Observacion de Patrones**: Detecta preferencias implicitas del usuario
2. **Modelado de Preferencias**: Construye perfil de preferencias estructurado
3. **Aplicacion Proactiva**: Aplica preferencias sin que el usuario las pida
4. **Confirmacion Gradual**: Valida inferencias con feedback implicito
5. **Evolucion del Modelo**: Actualiza preferencias cuando cambian
6. **Explicabilidad**: Puede explicar por que tomo ciertas decisiones

## Categorias de Preferencias

| Categoria | Ejemplos | Deteccion |
|-----------|----------|-----------|
| **Lenguaje** | TypeScript > JavaScript | Analisis de codigo existente |
| **Framework** | React > Vue > Angular | Uso en proyectos |
| **Estilo** | Tabs vs Spaces, comillas | Codigo escrito |
| **Commit** | Conventional, idioma | Historial de commits |
| **Comunicacion** | Conciso vs Detallado | Feedback del usuario |
| **Complejidad** | Simple vs Enterprise | Decisiones pasadas |
| **Testing** | TDD, coverage level | Configuracion y practicas |

## Capacidades

- Analisis de codebase para inferir stack preferido
- Deteccion de patrones en feedback
- Modelo probabilistico de preferencias
- Confidence scoring por preferencia
- Explicacion de decisiones basadas en preferencias
- Export/import de perfiles de preferencia

## Triggers

- Continuamente durante interacciones
- Cuando hay ambiguedad que preferencias resolverian
- "prefiero", "siempre uso", "no me gusta"
- Inicio de sesion (cargar perfil)

## Integraciones

- Intelligence: `user_preference_model.py`
- Core: `shared_memory.py`
- Agentes: Todos (consultan preferencias)

## Modelo de Preferencias

```python
@dataclass
class UserPreference:
    category: str
    key: str
    value: Any
    confidence: float  # 0-1
    source: Literal["explicit", "inferred", "default"]
    evidence: list[str]  # ejemplos que soportan esta preferencia
    last_confirmed: datetime

@dataclass
class PreferenceProfile:
    user_id: str
    preferences: dict[str, UserPreference]
    interaction_count: int
    created_at: datetime
    updated_at: datetime
    version: int
```

## Preferencias por Defecto vs Aprendidas

```python
DEFAULT_PREFERENCES = {
    "code.language": "infer_from_project",
    "code.style.quotes": "infer_from_project",
    "code.style.indent": "infer_from_project",
    "commit.style": "conventional",
    "commit.language": "english",
    "communication.verbosity": "balanced",
    "testing.coverage_target": 80,
}

# Despues de 10 interacciones:
LEARNED_PREFERENCES = {
    "code.language": {"value": "typescript", "confidence": 0.95},
    "code.style.quotes": {"value": "single", "confidence": 0.87},
    "commit.language": {"value": "spanish", "confidence": 0.92},
    # ...
}
```

## Workflow Tipico

```
1. Cargar perfil de preferencias del usuario
2. Durante cada interaccion:
   a. Observar decisiones del usuario
   b. Detectar patrones nuevos
   c. Actualizar confidences de preferencias existentes
3. Cuando hay decision ambigua:
   a. Consultar preferencias relevantes
   b. Aplicar preferencia con mayor confidence
   c. Si confidence < threshold: preguntar
4. Periodicamente: persistir perfil actualizado
```

## Ejemplo de Uso

```bash
# Ver preferencias actuales
python .agent/agents/user-preference-learner/scripts/preference_learner.py "show"

# Consultar preferencia especifica
python .agent/agents/user-preference-learner/scripts/preference_learner.py "get: code.language"

# Establecer preferencia explicita
python .agent/agents/user-preference-learner/scripts/preference_learner.py "set: commit.language=spanish"

# Exportar perfil
python .agent/agents/user-preference-learner/scripts/preference_learner.py "export: profile.json"
```

## Configuracion

```yaml
user_preference_learner:
  min_confidence_to_apply: 0.7
  min_evidence_count: 3
  decay_factor: 0.95  # preferencias viejas pierden confidence
  explicit_overrides_inferred: true
  ask_on_low_confidence: true
  profile_path: .agent/memory/user_preferences.json
```

## Metricas

- Preferencias aprendidas vs explicitas
- Confidence promedio de preferencias
- Tasa de acierto (cuando aplicamos sin preguntar)
- Preferencias que cambiaron en el tiempo
