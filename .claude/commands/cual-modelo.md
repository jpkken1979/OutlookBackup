# /cual-modelo — Recomendador de modelo por tarea

Detectá el modo según los argumentos y actuá:

## Modo 1 — Objetivo (un solo paso)
Si el argumento describe un **objetivo multi-tarea** (varios entregables, "y",
verbos compuestos, alcance amplio):
1. Generá el plan con el flujo existente (`/plan new <objetivo>`), que escribe
   `.claude/planning/active/task_plan.md`.
2. Anotá ese plan corriendo:
   `python .agent/skills-custom/cual-modelo/scripts/main.py --yes`
3. Mostrá al usuario el plan ya anotado con el modelo por tarea.

## Modo 2 — Anotar (sin args)
Si no hay argumentos: anotá el plan activo:
`python .agent/skills-custom/cual-modelo/scripts/main.py` (mostrá el diff; aplicá
con `--yes` tras confirmación del usuario).

## Modo 3 — Tarea suelta
Si el argumento es una **acción única y acotada**:
`python .agent/skills-custom/cual-modelo/scripts/main.py "<tarea>"`

## Modo 4 — Agent Teams
Si el usuario va a spawnear un team (o pide "modelo por teammate"):
`python .agent/skills-custom/cual-modelo/scripts/main.py --teams "rol 1" "rol 2" ...`
Emite una línea por teammate con su modelo, lista para pegar en el spawn prompt.
(Los teammates NO heredan el `/model` del lead — el modelo se fija al spawn.)

## Ambigüedad
Si no podés distinguir entre Modo 1 y Modo 3, **preguntá**:
"¿Armo el plan completo o solo te digo el modelo de esta tarea?"

## Notas
- El default es conservador: nunca baja la calidad del código.
- Override: `--model <haiku|sonnet|opus>` o env `ANTIGRAVITY_FORCE_MODEL`.
- **Provider alternativo activo** (minimax/zai/openrouter/... según proxy_state):
  el CLI NO degrada modelos por tarea — avisa que se use el mejor modelo del
  provider y omite `model`. Detección override: env `ANTIGRAVITY_ACTIVE_PROVIDER`.
