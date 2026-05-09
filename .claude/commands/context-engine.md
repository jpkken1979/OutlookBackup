Controlar el Pluggable Context Engine activo del ecosistema Antigravity.

## Cuando usarlo

- Antes de una sesion larga: elegir el engine optimo (brain_aware, composite).
- Diagnostico: ver que se esta inyectando al contexto del agente.
- Metricas: comparar chars/tokens del engine actual vs legacy.

## Uso

```
/context-engine                        # lista y estado actual
/context-engine list                   # solo la lista
/context-engine current                # solo el activo + fuentes
/context-engine switch <name>          # cambiar engine (persiste en config.json)
/context-engine preview "<task>"       # simula con una tarea (sin side effects)
/context-engine stats                  # comparacion chars/tokens
```

Engines disponibles: `default`, `brain_aware`, `delta_aware`, `summarizing`,
`domain_uns`, `composite`.

## Flujo

1. Parsear el subcomando.
2. Llamar la tool MCP correspondiente del server `antigravity-context-engine`:
   - sin args o `list` → `context_engine_list`
   - `current` → `context_engine_current`
   - `switch <name>` → `context_engine_switch`
   - `preview "<task>"` → `context_engine_preview`
   - `stats` → `context_engine_stats`
3. Presentar el resultado de forma tabular y concisa en espanol.

## Formato de presentacion

### Lista

```
## Context Engines disponibles

| Nombre        | Requiere       | Version | Descripcion                          |
|---------------|----------------|---------|--------------------------------------|
| default       | -              | 1.0.0   | Baseline historico                   |
| brain_aware   | brain          | 1.0.0   | Default + top-3 del Brain            |
| delta_aware   | delta_reader   | 1.0.0   | Marca archivos grandes               |
| summarizing   | -              | 1.0.0   | Comprime open_files + history        |
| domain_uns    | -              | 1.0.0   | Reglas UNS al detectar keywords      |
| composite     | brain          | 1.0.0   | Chain (delta → brain → sum → uns)    |

**Activo:** composite (via .antigravity/config.json)
```

### Current

```
## Engine activo

- **Resuelto:** composite
- **Env var:** (vacio)
- **Config file:** composite
- **Disponibles:** default, brain_aware, delta_aware, summarizing, domain_uns, composite
```

### Switch

```
## Engine cambiado

- `composite` → `brain_aware`
- Persistido en: `.antigravity/config.json`
```

### Preview

```
## Preview (engine=composite)

**Task:** refactor login to use new session API

### Contexto que se inyectaria

(seccion renderizada del prompt)
```

### Stats

```
## Stats (engine=composite)

| Metrica             | Valor  |
|---------------------|--------|
| Section chars       | 980    |
| Section tokens ~    | 245    |
| Saved vs legacy     | 340 chars / 85 tokens |
```

## Reglas

- Responder en espanol.
- Si falla el MCP, sugerir correr `/reload-plugins`.
- Al switch: confirmar el nuevo engine y recordar que afecta a la proxima invocacion, no a la actual.
- En preview, truncar la seccion a 600 chars en el output si es muy larga.
