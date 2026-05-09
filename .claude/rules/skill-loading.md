# Regla: Jerarquia de Carga de Skills

Cuando necesites una capacidad o patron, seguir este orden estricto:

## Tier 1: Standards Inyectados (preferido)
Verificar si las reglas del proyecto en `.claude/rules/` ya cubren el caso.
Estas reglas se auto-inyectan en cada sesion y tienen la mayor prioridad.

Ejemplos: convenciones de commits, seguridad, idioma, arquitectura, best practices.

## Tier 2: Registry del Ecosistema (fallback)
Buscar en el ecosistema Antigravity:
1. Skills locales: `.agent/skills/` (1006 disponibles)
2. Skills custom: `.agent/skills-custom/`
3. Skills remotos: `antigravity-remote` via MCP

Usar el skill tal cual si existe. No reinventar.

```bash
# Buscar via MCP (preferido)
# antigravity-ecosystem → list_skills, search_skills

# Buscar localmente (fallback)
ls .agent/skills/ | grep -i "keyword"
```

## Tier 3: skills.sh (fallback externo)
Si no existe localmente ni en el ecosistema:
```bash
npx skills find "descripcion de lo que necesitas"
npx skills add <owner/repo> --skill <name> --agent claude-code --yes
```

Criterios de seleccion:
- Mayor numero de instalaciones (popularidad = confianza)
- Fuente verificada (vercel-labs, anthropics, repos oficiales)
- Compatibilidad con claude-code

## Tier 4: Crear nuevo (ultimo recurso)
Solo si los 3 tiers anteriores no cubren el caso.
Antes de crear:
1. Documentar que se verificaron los 3 tiers anteriores
2. Guardar en memoria que se creo algo nuevo (para futuras sesiones)
3. Seguir la estructura estandar de skills del ecosistema

## Regla practica

> Nunca crear desde cero sin verificar los 3 tiers. Si un skill existe, usarlo o adaptarlo.
