# /search — Búsqueda universal en el ecosistema

Abre el modal de búsqueda universal (Cmd+K / Ctrl+K) en Nexus y permite buscar
en memorias, Brain Network, código y agentes del ecosistema Antigravity.

## Uso

```
/search [query]
```

Si se proporciona `query`, se pre-carga en el campo de búsqueda al abrir el modal.
Si se omite, se abre el modal vacío esperando input del usuario.

## Qué busca

| Fuente | Descripción |
|---|---|
| **Memorias** | Archivos `.md` en `.claude/memory/` |
| **Brain Network** | Nodos concepts/sessions/patterns del Brain |
| **Código** | Archivos fuente del proyecto (ripgrep) |
| **Agentes** | Agentes y skills disponibles |

## Integración

- Alias del shortcut global `Cmd+K` / `Ctrl+K` en Nexus
- Abre el `UniversalSearchModal` en Nexus
- Resultado: al presionar Enter se copia el preview al portapapeles

## Fuente

- Modal: `nexus-app/src/components/UniversalSearchModal.tsx`
- Hook: `nexus-app/src/hooks/useUniversalSearch.ts`
- Engine: `.agent/core/universal_search.py`
- Gateway: `POST /v1/search/universal` via `.agent/mcp/gateway_main.py`
- Rust command: `commands::knowledge::universal_search` en `nexus-app/src-tauri/src/commands/knowledge.rs`
