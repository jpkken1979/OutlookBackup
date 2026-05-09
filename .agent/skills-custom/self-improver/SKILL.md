---
name: self-improver
description: Auto-mejora continua de Claude Code - detecta gaps, genera nuevos skills y optimiza existentes basándose en patrones de fallo.
triggers:
  - "auto-mejorar"
  - "mejorarme"
  - "generar skill"
  - "detecta gaps"
  - "optimizar skills"
version: "1.0.0"
author: Antigravity Ecosystem
tags: [self-improvement, skill-generation, optimization, automation]
category: intelligence
---

# Self-Improver — Auto-MeJora Continua

## Propósito

Analiza los patrones de conversación, detecta gaps de capacidad, y genera nuevos skills o mejora los existentes automáticamente.

##触发 (Triggers)

- Sesión de trabajo que revela un gap (no existe skill para X)
- Petición del usuario: "mejorame", "auto-mejorar", "genera skill para..."
- Detección de errores repetitivos que podrían resolverse con automatización
- Fin de sesión con hallazgos significativos

## Proceso

### 1. Detectar Gap
```
- Analizar el último intercambio o sesión
- Identificar: ¿qué capacidad falta?
- Clasificar: skill nuevo vs. mejora de existente
```

### 2. Evaluar
```
- ¿Ya existe algo similar? (buscar en .agent/skills/)
- ¿Vale la pena crear? (frecuencia de uso vs. esfuerzo)
- ¿Qué tan complejo es? (skill simple vs. complejo)
```

### 3. Generar
```
- Skill simple → generar .md + script mínimo
- Skill complejo → crear esqueleto + documentar para desarrollo manual
- Mejora existente → proponer diff
```

### 4. Validar
```
- Verificar que el skill generado es invocable
- Probar con un caso de uso básico
- Documentar en memoria del proyecto
```

## Estructura de Output

```
self-improver/
├── analyze.py           # Análisis de gaps
├── generate.py         # Generación de skills
├── templates/         # Plantillas para skills
│   ├── skill_simple.md
│   └── skill_complex.md
└── registry.json       # Skills generados
```

## Métricas de Auto-Evaluación

| Métrica | Descripción |
|---------|-------------|
| `gaps_detected` | Gaps encontrados en la sesión |
| `skills_generated` | Skills nuevos creados |
| `skills_improved` | Skills mejorados |
| `coverage_delta` | Cambio en cobertura de capacidades |

## Ejemplo de Uso

```bash
# Analizar gaps de la sesión actual
python .agent/skills-custom/self-improver/scripts/analyze.py --session

# Generar skill basado en gap detectado
python .agent/skills-custom/self-improver/scripts/generate.py --gap "No tengo forma de hacer X"

# Auto-mejora completa (detectar + generar)
python .agent/skills-custom/self-improver/scripts/main.py --auto
```

## Integración

- Se ejecuta automáticamente al final de sesiones significativas
- Registra skills generados en `.agent/skills-custom/self-improver/registry.json`
- Ingiere al Brain como `pattern` con tag `self-improvement`
