# /finalize — cierre verificable y seguro

Contrato requerido: `FINALIZE_CONTRACT_V5`.

Usa `$source-command-finalize` como **fuente canónica** y ejecuta su flujo completo con
estos argumentos del usuario:

`$ARGUMENTS`

Si la skill todavía no está cargada, búscala en este orden:

1. `.agent/skills-custom/source-command-finalize/SKILL.md` del workspace.
2. `~/.codex/skills/source-command-finalize/SKILL.md` o el catálogo equivalente del IDE.
3. Broker MCP `antigravity` (connector de skills), si el gateway está disponible.

Antes de usar una copia global o MCP, valida frontmatter, el marcador
`FINALIZE_CONTRACT_V5` y estas referencias obligatorias:

- `references/workflow.md`
- `references/gate-matrix.md`
- `references/report-template.md`

Si existe fuente canónica en el workspace, compara el SHA-256 de esos cuatro archivos
contra la copia candidata. Cualquier diferencia la invalida. Sin workspace, exige el
marcador V5 en los cuatro archivos y reporta que la procedencia criptográfica no pudo
compararse. Si falla una comprobación, trata la skill como no disponible.

No sustituyas la skill por el antiguo agente `finalizer` ni por sus scripts heredados.
Si no puede cargarse, detén las mutaciones y entrega un preflight read-only indicando
`UNVERIFIED: canonical finalize skill unavailable`.

Modo predeterminado: `APPLY`. Usa `DRY-RUN` o `RESUME` solo cuando el usuario lo pida o
cuando el contexto indique inequívocamente que está retomando un cierre interrumpido.
