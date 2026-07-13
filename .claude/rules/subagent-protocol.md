# Regla: Protocolo de Sub-Agentes

Cuando delegues a un sub-agente (Agent tool):

## Contexto que debe recibir
1. Descripcion clara de la tarea (3-5 palabras en description)
2. Prompt detallado con TODO el contexto necesario
3. Rutas absolutas de archivos relevantes
4. Restricciones (no modificar, solo investigar, etc.)

## Lo que debe devolver
1. Resumen ejecutivo (1-3 lineas)
2. Hallazgos detallados con archivos y lineas
3. Recomendaciones concretas
4. Si modifica archivos: lista de cambios hechos

## Reglas
- Cada sub-agente empieza con contexto fresco — no asumir trabajo previo
- Preferir varios agentes pequenos y enfocados a uno grande
- Lanzar en paralelo cuando las tareas son independientes
- No permitir que multiples agentes modifiquen el mismo archivo sin reconciliacion
- Incluir siempre la ruta absoluta del repositorio actual obtenida desde el workspace activo

## Test de inflacion de contexto
Antes de delegar, evaluar:
- Si la tarea requiere < 3 archivos y < 50 lineas de cambio: hacerla directamente
- Si la tarea requiere investigacion amplia o cambios en multiples archivos: delegar
- Si multiples tareas son independientes: lanzar agentes en paralelo

## Anti-patrones
- Delegar tareas triviales (un solo archivo, cambio obvio)
- Enviar todo el contexto de la sesion al sub-agente (solo lo relevante)
- Asumir que el sub-agente conoce decisiones previas de la sesion
- Pedir al sub-agente que haga mas de una responsabilidad
