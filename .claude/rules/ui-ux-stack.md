# Stack UI/UX del ecosistema — guia maestra

Auto-inyectado en cada sesion. Define que herramientas usar cuando el usuario pida UI/UX, paginas web "geniales", componentes modernos, dashboards, landing pages, etc.

## Capas del stack

| Capa | Tool | Cuando usar | Como invocar |
|---|---|---|---|
| 1. Intelligence | `ui-ux-pro-max` skill v2.5.0 | Elegir estilos, paletas, tipografias, guidelines de accesibilidad/UX | `python3 .agent/skills/ui-ux-pro-max/scripts/search.py "<query>" --domain <product\|style\|color\|typography\|landing\|chart\|ux>` |
| 2. Componentes IA | `magic-21st` MCP | Generar componentes UI nuevos a partir de descripcion en lenguaje natural | MCP tool, requiere `MAGIC_21ST_API_KEY` |
| 3. Componentes library | `shadcn-ui-components` skill + shadcn/ui MCP | Componentes base ya probados (shadcn/ui, radix) | Skill + MCP query |
| 4. Estilo | `tailwind-v4-shadcn` skill | Convenciones Tailwind v4 + shadcn integrados | Skill |
| 5. Animacion | `framer-motion@12.38` (instalado en nexus-app) | Animaciones declarativas en React | `import { motion } from "motion/react"` o `framer-motion` |
| 6. Orquestador | `uiuxexpert` skill custom | Flujo end-to-end: search shadcn + web + implementacion con Tailwind + Framer | Skill |
| 7. Sistema 10 modulos | `ui-ux` skill | Sistema definitivo UI/UX (cuando es trabajo grande de design system) | Skill |

## Cuando usar cada uno

### Pagina o componente nuevo
1. Consulta `ui-ux-pro-max` para elegir paleta/tipografia/estilo segun el producto (SaaS, e-commerce, etc.)
2. Si necesitas un componente especifico (ej. dashboard sidebar con stats): `magic-21st` lo genera con IA
3. Si el componente existe en shadcn/ui: usar `shadcn-ui-components` skill antes de generar uno nuevo
4. Aplicar Tailwind v4 segun `tailwind-v4-shadcn` skill
5. Animaciones con `framer-motion` (extraer variants a archivos `*Variants.ts` fuera del componente, ver `.claude/rules/typescript.md`)

### Refactor de UI existente
1. `uiuxexpert` skill para auditar y proponer
2. `ui-ux-pro-max` con `--domain ux` para guidelines de accesibilidad/touch/contrast
3. Implementar con `react-doctor` para verificar a11y, memory leaks, paleta consistente

### Design system desde cero
1. `ui-ux` skill (sistema 10 modulos)
2. `ui-ux-pro-max` para data-driven decisions
3. `magic-21st` para componentes base de la libreria

## Reglas de oro

- **NO inventar paletas**: siempre consultar `ui-ux-pro-max --domain color` con el tipo de producto. 161 paletas curadas.
- **NO improvisar typography**: 57 pairings curadas. Usar siempre Google Fonts via `--domain typography`.
- **A11y first**: contrast minimo 4.5:1, touch targets 44x44px, focus rings visibles. `ui-ux-pro-max --domain ux` siempre devuelve a11y como priority 1.
- **Framer Motion variants fuera del componente**: archivo `*Variants.ts` separado. Ver `.claude/rules/typescript.md`.
- **`prefers-reduced-motion`**: respetarlo siempre que uses Framer.
- **Tailwind v4 con `@theme`** en `index.css` (sin `tailwind.config.js`). Ver `.claude/rules/typescript.md`.

## Comando 21st.dev Magic — generacion de componentes con IA

```
# Una vez configurada la API key en .env o env var MAGIC_21ST_API_KEY:
# En Claude Code se invoca via el MCP magic-21st (tools como /ui, /21 segun version)
```

API key: obtener en `https://21st.dev/magic/console` (login required).
Setear en `.env` del proyecto: `MAGIC_21ST_API_KEY=tu_key_aqui` o en variables de usuario Windows.

## Stack para apps nuevas (auto-injected via mcp_injector)

El `mcp_injector.py` con `--dev-preset` ahora incluye `magic-21st` automaticamente.
Cualquier app nueva que reciba el ecosistema MCP tendra:
- `magic-21st` (UI con IA, requiere API key)
- `context7` (docs de librerias)
- `chrome-devtools` (debugging)
- `git`, `filesystem` (operaciones)
- Todos los `antigravity-*` MCPs core
- El skill `ui-ux-pro-max` se copia con el bundle de skills

## Troubleshooting

| Sintoma | Fix |
|---|---|
| `magic-21st` falla con "API key" | Verificar `MAGIC_21ST_API_KEY` en env. Obtener en `https://21st.dev/magic/console` |
| `magic-21st` falla con "npx no se reconoce" | Bugfix ya aplicado en `.mcp.json` (rutas absolutas + PATH). Si reaparece ver `bugfix_mcp_path_2026_05_15.md` |
| `ui-ux-pro-max` search.py error de imports | Necesita Python 3.8+. Probar `py .agent/skills/ui-ux-pro-max/scripts/search.py "test" --domain color` |
| Componentes generados no respetan paleta del proyecto | Pasar contexto explicito a `magic-21st`: "Use these colors from tailwind config: #..." |
| Animaciones con jitter | Verificar `will-change` + `transform3d` + `prefers-reduced-motion`. `ui-ux-pro-max --domain ux` tiene guideline |

## Recursos

- 21st.dev Magic MCP: <https://github.com/21st-dev/magic-mcp>
- 21st.dev Components gallery: <https://21st.dev/community/components>
- 21st.dev Magic Console (API key): <https://21st.dev/magic/console>
- ui-ux-pro-max repo: <https://github.com/nextlevelbuilder/ui-ux-pro-max-skill>
- ui-ux-pro-max homepage: <https://uupm.cc>
- Framer Motion: <https://www.framer.com/motion/>
- shadcn/ui: <https://ui.shadcn.com>

## Historial de cambios

| Fecha | Cambio |
|---|---|
| 2026-05-17 | Stack UI/UX creado. Skill ui-ux-pro-max actualizado a v2.5.0 (github). magic-21st MCP agregado al `.mcp.json` y al `mcp_injector` (dev preset). |
