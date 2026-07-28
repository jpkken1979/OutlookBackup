# Regla: NotebookLM Auto-Recall Light

NotebookLM es una fuente auxiliar de memoria documental por proyecto. No reemplaza
al repo local, Brain Network ni mem0; se usa cuando la pregunta necesita contexto
historico o referencias documentales ya subidas.

## Cuando usarlo automaticamente

Si existe `.agent/notebooklm/projects.json` con un notebook asociado al proyecto,
consulta NotebookLM sin esperar que el usuario lo mencione cuando el prompt pida:

- memoria, contexto, historial, decisiones, referencias o "que se hizo antes";
- arquitectura, reglas, docs, workflows, auditoria, pendientes o produccion;
- recomendaciones basadas en el libro de memoria del proyecto;
- preguntas tipo "que falta", "segun la memoria", "por que decidimos X".

## Cuando no usarlo

- Cambios pequenos de codigo donde los archivos locales bastan.
- Comandos slash explicitos como `/cuota`, `/notebooklm-*` o `/finalize`.
- Preguntas que requieren estado vivo del repo, DB, tests o servidor actual:
  verifica localmente primero.

## Como ejecutarlo

Ruta preferida en clientes que ejecutan hooks: el `UserPromptSubmit` corre
`.agent/scripts/notebooklm_auto_recall.py` o el hook de memoria que lo llama.

Ruta manual para agentes sin hooks:

```bash
python .agent/scripts/notebooklm_auto_recall.py --prompt "<pregunta>" --cwd "<repo>"
```

Si el script no emite nada, significa que la heuristica decidio no consultar
**o que el circuit breaker esta abierto** (3 fallos/timeouts consecutivos →
silencio por 6 horas; estado en `~/.antigravity/notebooklm/auto_recall_breaker.json`,
borrarlo para resetear a mano). Si emite un bloque `[NotebookLM Auto-Recall]`,
tratalo como contexto auxiliar y contrasta con archivos locales cuando haya
conflicto.

## Politica: cuando NO usar NotebookLM (research 2026-07-17)

NotebookLM es la capa documental **auxiliar** (cold path). Las capas 1-3
(markdown git + Brain + mem0) son la memoria de runtime (hot path, sub-segundo).

- **Nunca como fuente de verdad**: eso es git (markdown + Brain). La
  integracion va por cookies/scraping (no hay API consumer; la oficial es solo
  Enterprise) y puede romperse sin aviso — ej. device-binding de Google
  (jacob-bd/notebooklm-mcp-cli issue #248, 2026-07).
- **Nunca en flujos bloqueantes**: una query tarda 5-30s. Para recall por
  prompt usar Brain/mem0; NotebookLM solo on-demand (`/notebooklm-ask`) o via
  el auto-recall selectivo con breaker.
- **Version del CLI pineada** en `notebooklm_bridge.py`
  (`NOTEBOOKLM_MCP_CLI_VERSION`); subirla es decision consciente
  (override: env `ANTIGRAVITY_NLM_CLI_VERSION`).
- **Preguntas globales del ecosistema**: preferir `cross_notebook_query`
  (MCP `notebooklm-mcp`) sobre iterar notebook por notebook.
