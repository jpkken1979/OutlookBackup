---
description: Comparar skills locales vs skills.sh — encontrar gaps y upgrades
argument-hint: "[categoria|all]"
context: fork
agent: general-purpose
allowed-tools: Bash, Read, Grep, Glob
---

Comparar los skills locales del ecosistema contra skills.sh para encontrar:
1. Skills donde el local es mejor (LOCAL WINS)
2. Skills que existen en skills.sh pero no localmente (MISSING)
3. Skills que podrían upgradearse (UPGRADE CANDIDATES)

Si $ARGUMENTS es "all", está vacío, o no fue proporcionado, ejecutar:
```
python .agent/scripts/compare_skills.py --all
```

Si $ARGUMENTS es un nombre de categoría específico (e.g. "security", "ai", "testing"), ejecutar:
```
python .agent/scripts/compare_skills.py --category $ARGUMENTS
```

Categorías disponibles: security, testing, api, database, devops, ci-cd, frontend, backend, react, typescript, python, ui-ux, design, accessibility, docker, kubernetes, terraform, ai, llm, rag, agents, git, performance, monitoring.

Después de mostrar el reporte, preguntar al usuario si quiere:
- Instalar algún skill faltante con `npx skills add <ref>`
- Ver detalles de algún upgrade candidate
- Comparar otra categoría
