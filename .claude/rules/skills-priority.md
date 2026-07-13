# Regla: Skills y Agentes Prioritarios por App

Aplica a todas las sesiones de Claude Code en este repositorio.

## Principio

Cada app del ecosistema tiene un **dominio específico** (UNS Dispatch, Kintai, Payroll, Web/SEO, etc.) y un subset de skills/agents que son los más útiles para ese dominio. En vez de revisar mentalmente los 879 skills + 113 agents disponibles, la IA debe priorizar los del dominio actual.

## Cómo descubrir los skills prioritarios

1. **Leer la sección "Skills y Agentes prioritarios para esta app" del `CLAUDE.md` de la app.**
   Esa sección lista 4-8 skills/agents curados para el dominio.

2. Si esa sección no existe (app sin clasificar), inferir el dominio del nombre + `package.json` + estructura del repo, y proponer skills relevantes al usuario.

3. Antes de improvisar código o invocar un skill genérico, **verificar si hay uno especializado** en la lista prioritaria. Ejemplo:
   - Trabajando en `Chingiv7.026.3.30` y necesitás calcular seguro social → usar `social-insurance-calc` (en la lista prioritaria) en lugar de escribir lógica desde cero.
   - Trabajando en `Paginaweb26.3.30` y querés un componente UI nuevo → usar `magic-21st` MCP + `ui-ux-pro-max` skill en lugar de escribir HTML manual.

## Cuándo invocar un skill custom

| Patrón usuario dice | Skill prioritario a invocar (si está en la lista) |
|---|---|
| "validar el kintai" / "verificar overtime" | `kintai-validator` |
| "calcular yukyu" / "vacaciones" | `yukyu-calculator` |
| "premium de seguro social" / "shaho" | `social-insurance-calc` |
| "generar contrato individual" / "kobetsu" | `kobetsu-contracts` |
| "validar licencia haken" | `haken-license-validator` |
| "exportar dataset" / "audit trail" | `arari-workflow` |
| "componente UI" / "dashboard" / "landing" | `magic-21st` MCP + `frontend-design` skill |
| "SEO" / "content strategy" | `seo-content-strategist` agent |
| "analizar logs" / "EDA" / "KPIs" | `data-analyst` agent |
| "experimento ML" / "modelo predictivo" | `ml-experimenter` agent |

## Anti-patrones

- **NO** ignorar la lista prioritaria del CLAUDE.md y reinventar la solución desde cero.
- **NO** invocar un skill irrelevante (ej. `seo-content-strategist` cuando estás en un proyecto de payroll).
- **NO** asumir que un skill no existe sin verificar primero la lista prioritaria del CLAUDE.md de la app actual.

## Inventario completo

La lista prioritaria es un **subset curado**. Si el caso lo requiere y no está cubierto por la lista, consultar:
- `RULES.md` (inventario completo de skills/agents)
- `.agent/skills/` (807 skills base)
- `.agent/skills-custom/` (72 skills custom)
- `.agent/agents/` (113 agentes)
- `/brain query "<tema>"` para búsqueda semántica en el Brain Network

## Fuente canónica

- Lista prioritaria por app: `CLAUDE.md` raíz de cada app, sección "Skills y Agentes prioritarios para esta app"
- Generador: `.agent/scripts/classify_apps.py` (cuando exista) — hoy se genera manual via subagente
- Distribución: `.agent/scripts/mcp_injector.py --full --dev-preset` y `.agent/scripts/sync_skills_to_claude.py`
