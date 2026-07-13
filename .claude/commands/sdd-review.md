# SDD Fase 8: Review

Code review automatizado de todos los cambios implementados.
Busca bugs, problemas de seguridad, patrones incorrectos y oportunidades de mejora.

## Prerequisito

La Fase 7 (Verify) debe estar completa con lint, types y tests pasando.

## Acciones

1. **Identificar todos los cambios**
   - `git diff` para ver todos los cambios no commiteados
   - `git diff --stat` para resumen de archivos modificados
   - Leer cada archivo modificado completo para contexto

2. **Review de correctitud**
   - Lógica de negocio correcta según la especificación (Fase 3)
   - Manejo de edge cases
   - Race conditions en código async
   - Null/undefined handling
   - Off-by-one errors
   - Resource leaks (file handles, connections)

3. **Review de seguridad**
   - No secrets hardcodeados
   - No `shell=True` en subprocess
   - Input validation en bordes del sistema
   - Path traversal prevention
   - SQL injection (si aplica)
   - XSS prevention (si aplica)
   - CORS configurado correctamente

4. **Review de patrones y convenciones**
   - Adherencia a la arquitectura de 4 capas
   - MCP-first (no bypass directo de archivos si hay MCP disponible)
   - Type hints completos (Python)
   - Docstrings Google-style en funciones públicas
   - No `any` en TypeScript
   - Framer Motion variants fuera de componentes (Nexus)
   - Naming conventions (inglés para código, español para docs)

5. **Review de mantenibilidad**
   - Funciones con responsabilidad única
   - Código duplicado
   - Complejidad ciclomática razonable
   - Tests suficientes para los cambios
   - Imports organizados

6. **Review de performance**
   - N+1 queries
   - Operaciones bloqueantes en código async
   - Caching donde corresponde
   - Lazy loading de módulos pesados

## Output esperado

```markdown
## Code Review — [nombre del cambio]

### Resumen
- Archivos revisados: N
- Issues encontrados: N (N críticos, N mejoras)

### Issues críticos (bloquean merge)
1. **[SEGURIDAD]** archivo:línea — descripción
2. **[BUG]** archivo:línea — descripción

### Mejoras sugeridas (no bloquean)
1. **[PATTERN]** archivo:línea — descripción
2. **[PERF]** archivo:línea — descripción
3. **[STYLE]** archivo:línea — descripción

### Lo que está bien
- Punto positivo 1
- Punto positivo 2

### Veredicto
- [ ] APROBADO — listo para commit
- [ ] CAMBIOS REQUERIDOS — corregir issues críticos
- [ ] MEJORAS OPCIONALES — aprobar con sugerencias

### Siguiente paso
Si aprobado, la Fase 9 (Archive) documentará las decisiones y creará el commit.
```

---

Revisa los cambios de: $ARGUMENTS
