# security-scanner

- **Tier:** 4
- **Description:** Escanea codigo en busca de vulnerabilidades y patrones peligrosos

## Capacidades

- Busca patrones peligrosos: secrets hardcodeados, shell=True, eval(), innerHTML, SQL injection
- Detecta archivos .env que no deberian estar commiteados
- Verifica que .gitignore proteja archivos sensibles
- Clasifica hallazgos por severidad (critical/high/medium/low)
- Genera resumen con clasificacion real vs falso positivo via LLM

## Uso

```bash
python scripts/main.py "escanear seguridad del proyecto"
```

## Sin dependencias externas

Este agente usa solo grep/búsqueda de texto — no requiere herramientas externas.
