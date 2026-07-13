# Code Review Automatizado (GGA-inspired)

Revisa los cambios actuales buscando problemas de calidad, seguridad y patrones.

## Proceso

1. **Obtener cambios**: ejecutar `git diff` para ver qué cambió
2. **Analizar por categoría**:
   - **Seguridad**: secrets hardcodeados, shell=True, eval/exec, path traversal, XSS, SQL injection
   - **Bugs**: null checks faltantes, race conditions, resource leaks, off-by-one
   - **Arquitectura**: violaciones de capas, imports cruzados, acoplamiento excesivo
   - **Tests**: cobertura de cambios, assertions faltantes, mocks incorrectos
   - **Estilo**: naming inconsistente, código muerto, TODOs sin contexto
   - **Performance**: N+1 queries, sync en async, memory leaks potenciales

3. **Reportar**: Por cada hallazgo:
   - Archivo:línea
   - Categoría y severidad (CRITICAL/HIGH/MEDIUM/LOW)
   - Descripción del problema
   - Sugerencia de fix

4. **Veredicto**: PASSED o FAILED con razón

## Output format

```
╔═══════════════════════════════════════╗
║  CODE REVIEW — [PASSED|FAILED]       ║
╚═══════════════════════════════════════╝

[Hallazgos organizados por severidad]

Resumen: X critical, Y high, Z medium, W low
```

---

Revisa los cambios en: $ARGUMENTS
Si no se especifica, revisa `git diff HEAD`.
