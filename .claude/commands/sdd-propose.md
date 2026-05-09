# SDD Fase 2: Propose

Propone 2-3 soluciones alternativas con trade-offs claros.
Se basa en el reporte de exploración de Fase 1.

## Prerequisito

La Fase 1 (Explore) debe haberse completado. Si no existe reporte de exploración, ejecutar `/sdd-explore` primero.

## Acciones

1. **Sintetizar hallazgos de exploración**
   - Revisar archivos relevantes, dependencias y riesgos de Fase 1
   - Identificar las restricciones duras (no negociables) vs flexibles

2. **Generar 2-3 propuestas**
   - Cada propuesta debe ser viable y distinta en enfoque
   - Incluir al menos una opción conservadora (menor riesgo) y una ambiciosa (mayor beneficio)

3. **Analizar trade-offs por propuesta**
   - Complejidad de implementación (horas estimadas)
   - Riesgo de breaking changes
   - Mantenibilidad a largo plazo
   - Impacto en performance
   - Compatibilidad con la arquitectura existente (4 capas, MCP-first)

4. **Recomendar una propuesta**
   - Justificar la recomendación con criterios objetivos
   - Indicar qué propuesta NO elegir si hay restricciones de tiempo

## Output esperado

```markdown
## Propuestas — [nombre del cambio]

### Propuesta A: [nombre descriptivo]
**Enfoque**: descripción en 1-2 oraciones
**Cambios**: lista de archivos/módulos afectados
**Pros**:
- ...
**Contras**:
- ...
**Esfuerzo estimado**: X horas
**Riesgo**: bajo/medio/alto

### Propuesta B: [nombre descriptivo]
**Enfoque**: ...
**Cambios**: ...
**Pros**: ...
**Contras**: ...
**Esfuerzo estimado**: X horas
**Riesgo**: bajo/medio/alto

### Propuesta C (opcional): [nombre descriptivo]
...

### Recomendación
Propuesta [X] porque [justificación].
Si hay restricciones de tiempo, elegir Propuesta [Y] como alternativa rápida.

### Siguiente paso
Con la propuesta aprobada, la Fase 3 (Spec) detallará la especificación técnica completa.
```

---

Propón soluciones para: $ARGUMENTS
