# repo-analyzer

- **Tier:** 9
- **Description:** Analiza estructura, metricas y salud del repositorio
- **Version:** 1.0.0
- **Languages:** Any
- **Tools:** file system analysis, framework detection

## Capacidades

- Cuenta archivos por extension y lineas de codigo
- Detecta frameworks y dependencias (package.json, pyproject.toml, Cargo.toml)
- Verifica presencia de CI/CD, documentacion, tests y linting
- Calcula un score de salud del repositorio (0-100)
- Genera reporte ejecutivo con LLM

## Uso

```bash
python scripts/main.py "analyze this repository"
```
