# code-reviewer

- **Tier:** quality
- **Description:** Revisa codigo buscando errores, code smells y mejoras

## Capacidades

- Ejecuta linters por lenguaje (ruff para Python, tsc para TypeScript, cargo check para Rust)
- Recopila issues y los clasifica por severidad
- Genera resumen priorizado con sugerencias de fix via LLM

## Uso

```bash
python scripts/main.py "revisar calidad del codigo"
```

## Herramientas requeridas (opcionales)

- `ruff` — linter Python
- `npx tsc` — type checker TypeScript
- `cargo` — compilador Rust

Si una herramienta no esta instalada, se omite ese chequeo sin error.

---

## OMC Spec-First Enhancement

### Philosophy

> "Verify against SPEC, not against style. Evidence FRESH from re-running, not assumed."

La revision de codigo debe comenzar preguntando **QUE deberia pasar** antes de revisar **como esta implementado**. Toda verificacion requiere evidencia directa, no suposicion.

### Spec-First Workflow

```
1. SPEC   -> Confirmar comprension del comportamiento esperado
2. REVIEW -> Inspeccionar codigo contra la spec
3. VERIFY -> Re-ejecutar comandos para verificar (no asumir)
4. REPORT -> Hallazgos basados en evidencia concreta
```

### Markers

| Marker | Significado |
|--------|-------------|
| `[SPEC]` | Especificacion que se esta verificando |
| `[VERIFIED]` | Test pasado con evidencia fresca |
| `[FAILED]` | Test fallo con evidencia adjunta |
| `[GAP]` | La implementacion no cumple la spec |

### Spec-First Review Checklist

- [ ] **Antes de revisar**: confirmar que se entiende el comportamiento esperado
- [ ] **Durante**: marcar cada finding con `[SPEC]` referenciando el requisito
- [ ] **Despues**: re-ejecutar linters/tests para confirmar hallazgos (no asumir)
- [ ] **Reporte**: separar `[VERIFIED]` / `[FAILED]` / `[GAP]` con evidencia

### Integracion con /team-plan

Este agente es llamado en la etapa **verify** del pipeline `/team-plan`:

```bash
python scripts/main.py "verificar spec: <descripcion de la spec>"
```

El output debe ser evidencia-based: salida de linter, mensajes de error, no interpretaciones.
