Ejecutar validación de calidad y linting según el tipo de proyecto.

## Python (.agent/, tests/)

```bash
ruff check .agent/ --fix
ruff format --check .agent/
python -m mypy .agent/core
```

## TypeScript — Nexus (nexus-app/)

```bash
cd nexus-app && npm run lint
cd nexus-app && npx tsc -b tsconfig.app.json --noEmit
```

## TypeScript — Bot (src/)

```bash
npx tsc --noEmit
```

## Regla

No reportar como "listo" hasta que todos los checks pasen. Si hay errores, corregirlos inmediatamente.
