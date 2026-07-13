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

Si el script no emite nada, significa que la heuristica decidio no consultar.
Si emite un bloque `[NotebookLM Auto-Recall]`, tratalo como contexto auxiliar y
contrasta con archivos locales cuando haya conflicto.
