---
name: test-runner
description: Ejecuta tests del proyecto y analiza resultados con LLM
tier: 3
version: 1.1
date: 2026-04-21
status: active
---

# test-runner Agent

- **Tier:** 3 (Quality)
- **Description:** Ejecuta tests del proyecto y analiza resultados

## Capacidades

- Detecta framework de testing: pytest (Python), vitest/jest (TypeScript/JS), cargo test (Rust)
- Ejecuta los tests con output compacto
- Parsea resultados: passed, failed, errors, skipped
- Captura detalles de fallos para analisis
- Genera resumen con causas probables y sugerencias via LLM

## Uso

```bash
python scripts/main.py "ejecutar tests del proyecto"
```

## Herramientas requeridas (opcionales)

- `pytest` — test runner Python
- `npx vitest` / `npx jest` — test runner TypeScript/JS
- `cargo` — test runner Rust

Si una herramienta no esta instalada, se omite ese chequeo sin error.
