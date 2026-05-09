---
# Skill Metadata (YAML frontmatter)
name: skill-name-here
description: "Descripción concisa de lo que hace este skill"
category: backend|frontend|testing|security|devops|database|ai|architecture|specialized
version: "1.0.0"
author: Antigravity Team
source: internal|imported

# Optional metadata
dependencies: []
related_skills: []
keywords: [keyword1, keyword2, keyword3]
tier: 1-6  # 1=Core, 6=Specialized
---

# Skill Name

Descripción detallada del skill y su propósito.

## Cuándo Usar

- Situación 1 donde este skill es útil
- Situación 2 donde este skill es útil
- Situación 3 donde este skill es útil

## Cuándo NO Usar

- Situación donde otro skill es más apropiado
- Limitaciones conocidas

## Capacidades

### Principales
- Capacidad 1
- Capacidad 2
- Capacidad 3

### Avanzadas
- Capacidad avanzada 1
- Capacidad avanzada 2

## Estructura del Directorio

```
skill-name/
├── SKILL.md           # Este archivo
├── scripts/           # Código ejecutable
│   ├── main.py        # Punto de entrada
│   └── helpers.py     # Funciones auxiliares
├── templates/         # Plantillas reutilizables
├── examples/          # Ejemplos de uso
│   ├── input.json     # Ejemplo de entrada
│   └── output.json    # Ejemplo de salida
└── references/        # Documentación adicional
```

## Uso

### Ejemplo Básico

```python
# Ejemplo de cómo usar este skill
from skill_name import main_function

result = main_function(input_data)
print(result)
```

### Ejemplo Avanzado

```python
# Ejemplo más complejo con configuración
from skill_name import AdvancedProcessor

processor = AdvancedProcessor(
    option1=True,
    option2="value"
)
result = processor.process(input_data)
```

## Inputs

| Parámetro | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| param1 | string | Sí | Descripción del parámetro |
| param2 | int | No | Valor por defecto: 10 |
| param3 | list | No | Lista de elementos |

## Outputs

| Campo | Tipo | Descripción |
|-------|------|-------------|
| result | object | Resultado principal |
| status | string | Estado de la operación |
| errors | list | Lista de errores si los hay |

## Integración con Agentes

Este skill puede ser usado por los siguientes agentes:
- `agent-name-1` - Para tarea X
- `agent-name-2` - Para tarea Y

## Consideraciones de Seguridad

- Punto de seguridad 1
- Punto de seguridad 2
- Validaciones requeridas

## Changelog

### v1.0.0
- Versión inicial

---

*Skill parte del ecosistema Antigravity Agents*
