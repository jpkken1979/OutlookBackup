# /ui — Orquestador del Stack UI/UX completo

> Crea, refactor o audita interfaces web "geniales" usando todo el stack:
> `ui-ux-pro-max` (intelligence) + `magic-21st` MCP (componentes IA) +
> `shadcn-ui-components` + Tailwind v4 + Framer Motion + react-doctor.

Ver `docs/rules-reference/ui-ux-stack.md` para la guia completa del stack.

## Modos

| Comando | Que hace |
|---|---|
| `/ui` | Modo interactivo: pregunta que queres construir y arma el plan |
| `/ui build <descripcion>` | Construye un componente o pagina desde cero |
| `/ui refactor <archivo>` | Audita y refactoriza UI existente con todo el stack |
| `/ui review` | Audita la UI de toda la rama con `react-doctor` + a11y + paleta |
| `/ui search <query>` | Busqueda data-driven en `ui-ux-pro-max` (estilos, paletas, etc.) |
| `/ui generate <prompt>` | Genera componente via `magic-21st` MCP |
| `/ui setup` | Verifica que el stack este completo (API key, dependencias, MCPs) |

## Modo sin argumentos: Analisis interactivo

Cuando pones `/ui` solo:

### 1. Escaneo del contexto

```
- Directorios UI detectados (nexus-app/src/, src/components/, etc.)
- Stack tecnico (React/Vue/Svelte detectado en package.json)
- magic-21st MCP: ¿API key configurada en MAGIC_21ST_API_KEY?
- Framer Motion: ¿instalado en package.json?
- Tailwind: ¿v4 con @theme o v3 con tailwind.config.js?
- ui-ux-pro-max: validar `python3 .agent/skills/ui-ux-pro-max/scripts/search.py "test" --domain ux`
```

### 2. Presentacion inteligente

```
## Contexto detectado

Stack: React 19 + Tailwind v4 + Framer Motion 12.38 + shadcn/ui
magic-21st: ⚠️ Falta MAGIC_21ST_API_KEY (obtener en https://21st.dev/magic/console)
ui-ux-pro-max v2.5.0: ✅ operativo (67 styles, 161 palettes, 25 charts)

## Opciones

[1] Build nuevo componente/pagina (Recomendado)
    -> /ui build "<descripcion>"
[2] Refactor UI existente
    -> /ui refactor <archivo>
[3] Audit completo de la rama
    -> /ui review
[4] Search data-driven (paletas, tipografia, estilos)
    -> /ui search "<query>"
[5] Setup del stack (verificar API keys, dependencias)
    -> /ui setup

Elegi [1-5] o describi directamente que queres construir.
```

## Modo: build

**Sintaxis**: `/ui build <descripcion en lenguaje natural>`

Ejemplos:
- `/ui build landing page para SaaS de gestion de personal`
- `/ui build dashboard con sidebar + 4 stat cards + grafico de lineas`
- `/ui build modal de confirmacion con animacion blur+scale`

### Flujo

1. **Decidir estilo/paleta/tipografia** (data-driven):
   ```bash
   py .agent/skills/ui-ux-pro-max/scripts/search.py "<tipo de producto>" --domain product
   py .agent/skills/ui-ux-pro-max/scripts/search.py "<estilo deseado>" --domain style
   py .agent/skills/ui-ux-pro-max/scripts/search.py "<tipo producto>" --domain color
   py .agent/skills/ui-ux-pro-max/scripts/search.py "<tipo producto>" --domain typography
   ```
   Mostrar al usuario las opciones top-3 y elegir o confirmar.

2. **A11y/UX guidelines aplicables**:
   ```bash
   py .agent/skills/ui-ux-pro-max/scripts/search.py "<contexto>" --domain ux
   ```
   Capturar las priority 1-2 (CRITICAL) como restricciones obligatorias.

3. **Generar componente con magic-21st** (si esta configurado):
   - Usar el MCP `magic-21st` pasandole prompt enriquecido: descripcion + paleta elegida + a11y constraints + stack target (React/Tailwind v4)
   - Si magic-21st no esta configurado: usar shadcn/ui MCP + componer manualmente segun el data-driven plan

4. **Aplicar Tailwind v4 + Framer Motion**:
   - Variants de Framer en archivo `*Variants.ts` separado (regla del proyecto)
   - Respetar `prefers-reduced-motion`
   - Touch targets minimo 44x44px (ui-ux-pro-max critical rule)

5. **Validar con react-doctor**:
   ```bash
   # Ejecutar el skill react-doctor sobre el archivo generado
   ```
   Fix automatico de issues mecanicos (a11y labels, memory leaks, paleta inconsistente).

6. **Mostrar al usuario**:
   - Path del archivo creado
   - Score react-doctor antes/despues
   - Sugerencias de mejoras opcionales

## Modo: refactor

**Sintaxis**: `/ui refactor <archivo>`

Flujo:
1. Leer el archivo objetivo
2. `react-doctor` para detectar issues
3. `ui-ux-pro-max --domain ux` para guidelines aplicables
4. Aplicar fixes automaticos + sugerir mejoras estructurales
5. Diff antes/despues con explicacion de cada cambio

## Modo: review

**Sintaxis**: `/ui review`

Audita TODA la UI de la rama actual:
1. `git diff main` para identificar archivos UI cambiados
2. Por cada archivo: `react-doctor` + a11y check + paleta consistency
3. Reporte agrupado por severidad (critical/high/medium/low)
4. Sugerir batch fix con `/jpread` si hay muchos issues mecanicos

## Modo: search

**Sintaxis**: `/ui search <query>`

Wrapper rapido de `ui-ux-pro-max`:
```bash
py .agent/skills/ui-ux-pro-max/scripts/search.py "<query>" --domain <auto-detect>
```

Si el query menciona "color" o "palette" -> `--domain color`
Si menciona "font" o "typography" -> `--domain typography`
Si menciona "landing", "saas", "ecommerce" -> `--domain product`
Si menciona "chart" o "graph" -> `--domain chart`
Si menciona "a11y", "accessibility", "touch" -> `--domain ux`
Default: `--domain style`

## Modo: generate

**Sintaxis**: `/ui generate <prompt>`

Llamada directa al MCP `magic-21st`:
- Requiere `MAGIC_21ST_API_KEY` configurada
- Pasa el prompt textual al MCP
- Devuelve el componente generado en el archivo destino que elija el usuario

Si falta la API key, mostrar:
```
⚠️ magic-21st no esta configurado.
Obtener API key: https://21st.dev/magic/console
Setear: MAGIC_21ST_API_KEY=... en .env del proyecto
Recargar: /reload-plugins
```

## Modo: setup

**Sintaxis**: `/ui setup`

Verifica el stack:

| Check | OK? |
|---|---|
| `ui-ux-pro-max` skill instalado y v2.5.0+ | `ls .agent/skills/ui-ux-pro-max/data/styles.csv` |
| `magic-21st` MCP en `.mcp.json` | `grep '"magic-21st"' .mcp.json` |
| `MAGIC_21ST_API_KEY` en env o .env | `echo $MAGIC_21ST_API_KEY` |
| Framer Motion en package.json | `grep '"framer-motion"' package.json` |
| Tailwind v4 con @theme | `grep '@theme' nexus-app/src/index.css` |
| Skills relacionados | `ls .agent/skills/ | grep -iE "ui-ux\|shadcn\|tailwind"` |

Reportar todos los checks con OK/MISSING y dar el comando exacto para arreglarlos.

## Reglas de oro (heredadas del stack)

- A11y first: contrast 4.5:1, touch 44x44px, focus rings visibles
- Framer variants fuera del componente (`*Variants.ts`)
- `prefers-reduced-motion` siempre
- Tailwind v4 con `@theme` en `index.css` (sin `tailwind.config.js`)
- No inventar paletas: 161 curadas en `ui-ux-pro-max`
- No improvisar tipografia: 57 pairings curadas con Google Fonts imports

## Integracion con otros comandos

| Despues de `/ui` | Comando sugerido |
|---|---|
| Componente creado y se ve bien | `/finalize` para commit+push |
| Detectaste issues complejos | `/jpread` (react-doctor full) |
| Necesitas componer multiples componentes | `/sdd` (spec-driven 9 fases) |
| Refactor masivo | `/ralph` (loop hasta completar) |

## Ejemplos completos

```
/ui build landing page para SaaS de gestion de personal japones (派遣)
    -> ui-ux-pro-max sugiere: product=saas, style=minimalism+bento,
       color=palette#42 (azul corp con acentos rojos),
       fonts=Inter + JetBrains Mono
    -> magic-21st genera el hero + features + pricing
    -> react-doctor: a11y 95/100, sin memory leaks
    -> Archivo: src/pages/Landing.tsx + LandingVariants.ts
```

```
/ui search "dark mode dashboard"
    -> --domain style
    -> 5 estilos top: glassmorphism-dark, brutalism-dark, minimalism-dark, ...
    -> 5 paletas: zinc-950, slate-950, neutral-950, ...
```

## Fuente

- Regla maestra: `docs/rules-reference/ui-ux-stack.md`
- Skill data: `.agent/skills/ui-ux-pro-max/`
- MCP: `magic-21st` en `.mcp.json`
