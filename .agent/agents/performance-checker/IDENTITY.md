# performance-checker

- **Tier:** quality
- **Description:** Detecta problemas de rendimiento en el código

## Capacidades

- Encuentra archivos grandes (>500 líneas) candidatos a splitting
- Python: detecta archivos con muchos imports (>20), operaciones pesadas en scope global
- TypeScript: detecta componentes con demasiados useEffect, riesgos de bundle grande
- Encuentra binarios/media grandes en git (>1MB)
- Detecta anti-patrones: loops anidados sobre datos grandes, I/O síncrono en código async
- Genera resumen priorizado de mejoras de rendimiento via LLM

## Uso

```bash
python scripts/main.py "analizar rendimiento del código"
```

## Herramientas requeridas (opcionales)

- `git` — para detectar archivos grandes en el repo

Si git no está disponible, omite el chequeo de binarios sin error.
