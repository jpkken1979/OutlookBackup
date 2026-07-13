# SDD Fase 7: Verify

Ejecuta tests, linting y typechecking para validar que la implementación es correcta.
Identifica y reporta errores para corrección antes de avanzar.

## Prerequisito

La Fase 6 (Apply) debe estar completa.

## Acciones

1. **Detectar stack afectado**
   - Si se modificaron archivos `.py` → ejecutar suite Python
   - Si se modificaron archivos en `nexus-app/` → ejecutar suite Nexus
   - Si se modificaron archivos en `src/` → ejecutar suite Bot
   - Si se modificaron archivos en `src-tauri/` → ejecutar cargo check

2. **Ejecutar linting**
   - Python: `ruff check .agent/` y `ruff format --check .agent/`
   - Nexus: `cd nexus-app && npm run lint`
   - Aplicar auto-fix cuando sea posible (`ruff check --fix`)

3. **Ejecutar type checking**
   - Python: `python -m mypy .agent/core` (módulos modificados)
   - Nexus: `cd nexus-app && npm run ts:app`
   - Rust: `cd nexus-app/src-tauri && cargo check`

4. **Ejecutar tests**
   - Python: `python -m pytest tests/ -x --tb=short` (o tests específicos del área modificada)
   - Nexus: `cd nexus-app && npm test`
   - Bot: `npm test` (desde raíz)
   - Priorizar tests del área afectada antes de la suite completa

5. **Verificar cobertura**
   - Python: `python -m pytest tests/ --cov --cov-report=term-missing`
   - Verificar que se mantiene el mínimo de 80%

6. **Corregir errores encontrados**
   - Errores de lint → auto-fix o corregir manualmente
   - Errores de types → corregir type hints
   - Tests fallidos → analizar causa raíz y corregir
   - Reportar cada corrección

## Output esperado

```markdown
## Reporte de Verificación — [nombre del cambio]

### Linting
- **Python (ruff)**: PASS / N errores encontrados (N corregidos)
- **Nexus (eslint)**: PASS / N errores encontrados (N corregidos)

### Type checking
- **Python (mypy)**: PASS / N errores
- **TypeScript (tsc)**: PASS / N errores
- **Rust (cargo)**: PASS / N errores

### Tests
- **Suite ejecutada**: nombre de la suite
- **Resultado**: N passed, N failed, N skipped
- **Tests fallidos**: lista con causa
- **Cobertura**: X% (mínimo 80%)

### Correcciones aplicadas
1. Corrección 1 — archivo, descripción
2. ...

### Estado final
- [ ] Lint limpio
- [ ] Types limpios
- [ ] Tests pasando
- [ ] Cobertura >= 80%

### Siguiente paso
La Fase 8 (Review) realizará code review automatizado del cambio completo.
```

---

Verifica la implementación de: $ARGUMENTS
