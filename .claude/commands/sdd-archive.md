# SDD Fase 9: Archive

Documenta las decisiones tomadas, actualiza el estado del proyecto y crea el commit final.
Cierra el ciclo SDD dejando evidencia para futuras sesiones.

## Prerequisito

La Fase 8 (Review) debe estar completa con veredicto APROBADO.

## Acciones

1. **Documentar decisiones en memoria**
   - Si `antigravity-memory` está disponible, guardar un resumen del cambio via `memory_store`
   - Incluir: qué se cambió, por qué, alternativas descartadas, lecciones aprendidas

2. **Actualizar ESTADO_PROYECTO.md**
   - Agregar entrada de sesión con fecha, cambio realizado y archivos afectados
   - Formato consistente con entradas anteriores del archivo

3. **Crear resumen de decisiones**
   - Decisiones de arquitectura tomadas y su justificación
   - Trade-offs aceptados conscientemente
   - Deuda técnica introducida (si la hay) con plan de resolución

4. **Crear commit**
   - Formato convencional en español: `tipo(scope): descripción`
   - Cuerpo del commit con resumen de cambios
   - Co-Authored-By header
   - Incluir solo archivos relevantes (no `.env`, `*.db`, `*.log`)

5. **Verificar estado final**
   - `git status` limpio (todo commiteado)
   - No quedan archivos temporales o de debug

## Output esperado

```markdown
## Archivo SDD — [nombre del cambio]

### Decisiones documentadas
1. **[Decisión]**: [justificación]
   - Alternativa descartada: [cuál] — [por qué]
2. ...

### Trade-offs aceptados
- [Trade-off]: [beneficio obtenido] vs [costo aceptado]

### Deuda técnica
- [ ] [Descripción] — prioridad: baja/media/alta — plan: [cuándo resolver]
- (ninguna si no aplica)

### Lecciones aprendidas
- [Lección que aplica a futuras implementaciones]

### Commit
`tipo(scope): descripción del commit`

### Archivos afectados
- Creados: N
- Modificados: N
- Eliminados: N

### Estado del proyecto actualizado
ESTADO_PROYECTO.md actualizado con entrada de sesión.

---
Ciclo SDD completado.
```

## Memoria

Si `antigravity-memory` está disponible, guardar:

```
memory_store({
  "content": "SDD completado: [cambio]. Decisiones: [resumen]. Archivos: [lista]. Trade-offs: [resumen].",
  "metadata": {"type": "sdd-archive", "project": "[repo actual]"}
})
```

---

Archiva los resultados de: $ARGUMENTS
