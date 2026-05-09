---
name: design-md-collection
description: "Envuelve la colección awesome-design-md de VoltAgent: 55+ sistemas de diseño listos para usar como DESIGN.md en cualquier proyecto. Diseños inspirados en Figma, Linear, Vercel, Stripe, Cursor, etc. Formato de 9 secciones: Color Palette, Typography, Spacing, Component Library, Layout, Motion, Visual Assets, Design Principles, Accessibility. Triggers: design system, design.md, UI system, Figma, Linear, Vercel, Stripe."
type: feature
---

# design-md-collection

Skill que envuelve la colecci\u00f3n **awesome-design-md** de [VoltAgent](https://github.com/VoltAgent/awesome-design-md): 55+ sistemas de dise\u00f1o listos para usar como `DESIGN.md` en cualquier proyecto.

## \u00bfQu\u00e9 es?

La colecci\u00f3n provee archivos `DESIGN.md` inspirados en sitios reales (Figma, Linear, Vercel, Cursor, Stripe, etc.). Cada `DESIGN.md` describe en formato markdown plano c\u00f3mo deber\u00eda verse y sentirse un proyecto: paleta de colores, tipograf\u00eda, espa\u00f1iado, componentes UI, patr\u00f3nes de interacci\u00f3n, etc.

## Colecci\u00f3n

- **Ra\u00edz**: `.agent/tmp/awesome-design/design-md/`
- **55+ dise\u00f1os**: Airbnb, Airtable, Apple, BMW, Cal, Claude, Clay, ClickHouse, Coinbase, Cohere, Composable AI, Cursor, ElevenLabs, Expo, Ferrari, Figma, Framer, Hashicorp, IBM, Intercom, Kraken, Lamborghini, Linear.app, Lovable, MiniMax, Mintlify, Miro, Mistral AI, MongoDB, Notion, NVIDIA, Ollama, OpenCode AI, Pinterest, Posthog, Raycast, Renault, Replicate, Resend, Revolut, Runway ML, Sanity, Semrush, Sentry, SpaceX, Spotify, Stripe, Supabase, Superhuman, Tesla, Together AI, Uber, Vercel, VoltAgent, Warp, Webflow, Wise, xAI, Zapier.

## Formato DESIGN.md (9 secciones)

Cada Dise\u00f1o sigue la estructura de 9 secciones de VoltAgent:

| # | Secci\u00f3n | Descripci\u00f3n |
|---|---|---|
| 1 | Color Palette | Paleta completa con hex, rgb, usage |
| 2 | Typography | Sistema tipogr\u00e1fico con font-stack, sizes, weights, line-heights |
| 3 | Spacing | Sistema de espa\u00f1iado (4px base grid) |
| 4 | Component Library | Gu\u00eda de componentes UI (buttons, inputs, cards, modals, etc.) |
| 5 | Layout & Structure | Grid system, breakpoints, estructura de p\u00e1gina |
| 6 | Motion & Animation | Est\u00e1ndares de animaci\u00f3n, timing, easing |
| 7 | Visual Assets | Iconos, ilustraciones, im\u00e1genes, logotipos |
| 8 | Design Principles | Principios de dise\u00f1o, filosof\u00eda, decisiones clave |
| 9 | Accessibility | Contraste, focus states, aria, keyboard navigation |

## Archivos del skill

```
design-md-collection/
\u251c\u2500\u2500 SKILL.md                  # Este archivo
\u251c\u2500\u2500 INDEX.md                  # \u00cdndice generado (auto-generado por generate_index.py)
\u2514\u2500\u2500 scripts/
    \u251c\u2500\u2500 __init__.py           # Marker vac\u00edo
    \u251c\u2500\u2500 generate_index.py    # Genera INDEX.md desde los README.md de cada dise\u00f1o
    \u251c\u2500\u2500 apply_design.py       # Copia un dise\u00f1o seleccionado a un proyecto target
```

## Comandos

### Generar \u00cdndice

```bash
python .agent/skills/design-md-collection/scripts/generate_index.py
```

Recorre todos los subdirectorios en `.agent/tmp/awesome-design/design-md/` y genera `INDEX.md` con el nombre, descripci\u00f3n y categor\u00eda de cada dise\u00f1o.

### Aplicar un dise\u00f1o a un proyecto

```bash
python .agent/skills/design-md-collection/scripts/apply_design.py <design-name> <target-dir>
```

Ejemplo:

```bash
python .agent/skills/design-md-collection/scripts/apply_design.py figma ./mi-proyecto
```

Copia `.agent/tmp/awesome-design/design-md/figma/DESIGN.md` a `<target-dir>/DESIGN.md`. Si el archivo ya existe, pregunta si sobreescribir.

## Categor\u00edas de la colecci\u00f3n

| Categor\u00eda | Dise\u00f1os |
|---|---|
| AI & LLM Platforms | claude, cohere, elevenlabs, minimax, mistral.ai, ollama, opencode.ai, replicate, runwayml, together.ai, voltagent, x.ai |
| Developer Tools & IDEs | cursor, expo, lovable, raycast, superhuman, vercel, warp |
| Backend, Database & DevOps | clickhouse, ibm, mongodb, supabase |
| Design & Creative | figma, framer, miro, sanity, webflow |
| Finance & Crypto | coinbase, kraken, revolut, wise |
| Social & Media | pinterest, spotify |
| Automotive & Hardware | apple, bmw, ferrari, lamborghini, nvidia, renault, tesla |
| Productivity & SaaS | airbnb, airtable, cal, clay, hashicorp, intercom, linear.app, mintlify, notion, posthog, semrush, sentry, spacex, stripe, uber, zapier |
| Other | composio, raycast, replicate, together.ai, voltagent, zapier |

## Notas

- Los `README.md` de cada dise\u00f1o redireccionan a `https://getdesign.md/<name>/design-md` para obtener el contenido completo.
- El skill no descarga contenido — usa los README.md disponibles localmente.
- Para dise\u00f1os que redireccionan, usar la URL p\u00fablica para ingestar el contenido real.
