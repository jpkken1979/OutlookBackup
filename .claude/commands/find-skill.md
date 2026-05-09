---
description: Buscar e instalar skills de skills.sh
argument-hint: "[query]"
allowed-tools: Bash
---

Buscar skills en skills.sh que coincidan con la query del usuario: $ARGUMENTS

1. Ejecutar `npx skills find "$ARGUMENTS"` para buscar
2. Mostrar los top 5 resultados con nombre, instalaciones y URL
3. Preguntar al usuario cuál quiere instalar
4. Si elige uno, instalarlo con: `npx skills add <owner/repo> --skill <skill-name> --agent claude-code --yes`
5. Verificar que se instaló con `npx skills list`
