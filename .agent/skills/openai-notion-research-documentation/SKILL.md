---
name: openai-notion-research-documentation
description: "Investigación y documentación con Notion. Crea briefs, resúmenes, comparativas y reportes de investigación completos con citas."
type: feature
---

# Notion Research & Documentation

Crea documentos de investigación estructurados y almacenados en Notion.

## Setup

```bash
mcp add notion --url https://mcp.notion.com/mcp
```

## Tipos de Documento

### Research Brief
Resumen ejecutivo de investigación rápida:

```markdown
# Research Brief: [Tema]

## Pregunta de Investigación
[Qué queremos saber]

## Hallazgos Clave
1. [Hallazgo principal]
2. [Hallazgo secundario]

## Fuentes
- [Fuente 1] — [Credibilidad: alta/media]
- [Fuente 2]

## Recomendación
[Acción sugerida basada en hallazgos]
```

### Summary Report
Resumen de tema con profundidad media:

```markdown
# Summary: [Tema]

## Contexto
[Antecedentes y por qué importa]

## Análisis
### [Subtema 1]
[Análisis detallado]

### [Subtema 2]
[Análisis detallado]

## Conclusiones
[Puntos principales]

## Referencias
1. [Referencia con link]
```

### Comparison Report
Análisis comparativo de opciones:

```markdown
# Comparativa: [Opción A] vs [Opción B]

## Criterios de Evaluación
| Criterio | Peso | Opción A | Opción B |
|----------|------|----------|----------|
| Rendimiento | 30% | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| Costo | 25% | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| Facilidad | 20% | ⭐⭐⭐⭐ | ⭐⭐ |
| Soporte | 15% | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| Ecosistema | 10% | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |

## Análisis Detallado
### Opción A
[Fortalezas, debilidades, casos de uso ideales]

### Opción B
[Fortalezas, debilidades, casos de uso ideales]

## Recomendación
[Cuál elegir y por qué, según contexto]
```

### Comprehensive Report
Investigación completa con citas y metodología:

```markdown
# [Título del Reporte]

## Resumen Ejecutivo
[2-3 párrafos con hallazgos principales]

## Metodología
[Cómo se realizó la investigación]

## 1. Introducción
[Contexto, objetivos, alcance]

## 2. Estado del Arte
[Qué existe actualmente, antecedentes]

## 3. Análisis
### 3.1 [Área de Análisis 1]
[Análisis con datos y evidencia]

### 3.2 [Área de Análisis 2]
[Análisis con datos y evidencia]

## 4. Hallazgos
[Lista priorizada de hallazgos]

## 5. Recomendaciones
[Acciones concretas basadas en hallazgos]

## 6. Conclusiones
[Síntesis final]

## Referencias
[1] Autor, "Título", Fuente, Año. URL
[2] ...

## Apéndices
[Datos adicionales, metodología detallada]
```

## Workflow de Investigación

1. **Definir pregunta** — Qué necesitamos investigar y por qué.
2. **Recopilar fuentes** — Buscar información de múltiples fuentes.
3. **Analizar** — Extraer hallazgos relevantes.
4. **Estructurar** — Elegir tipo de documento y llenar plantilla.
5. **Citar** — Incluir referencias con links.
6. **Publicar** — Crear en Notion con tags y categorización.

## Recursos

- [Notion API](https://developers.notion.com/)
- [Notion MCP](https://github.com/makenotion/notion-mcp-server)
