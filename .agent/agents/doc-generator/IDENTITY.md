# doc-generator

- **Tier:** 3
- **Description:** Genera documentacion para funciones y clases sin docstrings
- **Version:** 1.0.0
- **Languages:** Python, TypeScript
- **Tools:** AST (Python), regex (TypeScript)

## Capacidades

- Escanea archivos Python usando AST para encontrar funciones/clases sin docstrings
- Escanea archivos TypeScript para encontrar exports sin JSDoc
- Reporta cobertura de documentacion (X de Y funciones documentadas)
- Genera sugerencias de docstrings para los items mas importantes con LLM
- Lista items sin documentar con archivo y linea

## Uso

```bash
python scripts/main.py "find undocumented code"
```
