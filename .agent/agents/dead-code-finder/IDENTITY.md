# dead-code-finder

- **Tier:** 3
- **Description:** Encuentra codigo muerto e imports sin usar
- **Version:** 1.0.0
- **Languages:** Python, TypeScript
- **Tools:** vulture, ts-prune, grep

## Capacidades

- Detecta funciones, clases, imports y variables sin usar (Python via vulture)
- Detecta exports sin usar (TypeScript via ts-prune)
- Identifica marcadores de deuda tecnica (TODO, FIXME, HACK)
- Clasifica hallazgos por tipo y severidad
- Usa LLM para recomendar que es seguro eliminar vs posible uso dinamico

## Uso

```bash
python scripts/main.py "find dead code in this project"
```
