# Regla: Sincronizacion de Memorias en Git

Aplica a todas las sesiones de Claude Code en este repositorio.

> Para la jerarquia completa de las tres capas de memoria (markdown, Brain
> Network, mem0) ver `.claude/rules/memory-engine.md`. Esta regla se enfoca
> solo en la politica de sincronizacion entre PCs via git.

## Principio

Las memorias del proyecto (capas 1 y 2) viven DENTRO del repositorio para
sincronizarse entre PCs via git:

- `.claude/memory/` — memorias markdown
- `.agent/brain/` — Brain Network (concepts/, sessions/, patterns/, etc.)

La ubicacion externa `~/.claude/projects/.../memory/` es volatil y NO sincroniza
entre maquinas. Solo sirve como buffer que el hook `Stop` copia al repo.

## Obligatorio al guardar

Cuando guardes una memoria significativa, escribir en el repositorio directamente:

- Capa 1 (markdown): `.claude/memory/<tipo>_<topic>.md`
- Capa 2 (brain): `brain.ingest(...)` desde `.agent/core/brain.py`

No hace falta escribir primero en `~/.claude/projects/.../memory/`; el hook
de sync corre al cerrar sesion y cubre ese caso.

Si hay conflicto entre la copia del sistema y la del repositorio, la del
repositorio es la **fuente de verdad**.

## Al iniciar sesion

Si `.claude/memory/MEMORY.md` existe en el repositorio, leerlo para recuperar
contexto de sesiones anteriores (incluso de otras PCs). El Brain Network
tambien se puede consultar via `/brain query` o `/recall`.

## Al cerrar sesion (CRITICO — OBLIGATORIO)

**Regla de hierro: toda memoria generada durante la sesion DEBE estar en git
antes de cerrar.** Si no se sube, se pierde cuando cambies de PC.

1. **Capa 1** (`.claude/memory/`): el hook `memory-sync.sh` corre automatico en
   Stop y copia de `~/.claude/projects/`. Verificar que los archivos quedaron
   en el working tree antes de salir.
2. **Capa 2** (`.agent/brain/`): el hook Stop corre
   `rebuild_brain_index.py` automaticamente — pero eso solo reconstruye `index.md`.
   **NO alcanza**. Hay que hacer `git add` y `git commit` de TODOS los cambios
   del brain generados durante la sesion.
3. **Commit + push automatico**: al cerrar cualquier sesion (incluyendo `/finalize`,
   `/git-pushing`, `/session-summary` y el hook Stop), SIEMPRE ejecutar:

   ```bash
   # Ver que cambio en el brain
   git status .agent/brain/ .claude/memory/
   # Si hay cambios sin commitear, hacer:
   git add .agent/brain/ .claude/memory/
   git commit -m "chore(memory): sincronizar memorias de sesion"
   git push
   ```

4. **Nunca irse sin hacer push de las memorias**. Si el push falla (offline,
   conflicto), avisar al usuario y no cerrar la sesion hasta resolverlo.
5. **Si hay cambios no relacionados con memorias** (código, configs), hacer
   commits separados — no mezclar memorias con cambios funcionales.

**El brain es la memoria del usuario.** Si se pierde, se pierde conocimiento
acumulado. No existe raz\u00f3n v\u00e1lida para no subirlo.

## Política de gitignore — NO ignorar nada de .claude/

**NUNCA** agregar archivos de `.claude/` al `.gitignore`. Todo debe subirse al repositorio para sincronizar entre PCs:

| Ubicacion | Proposito | Sincroniza por git |
|---|---|---|
| `.claude/memory/MEMORY.md` | Indice de memorias | **Si** |
| `.claude/memory/*.md` | Memorias individuales | **Si** |
| `.claude/settings.json` | Settings compartidos del proyecto | **Si** |
| `.claude/settings.local.json` | Settings locales (modelo, effort) | **Si** |
| `.claude/commands/*.md` | Slash commands | **Si** |
| `.claude/hooks/scripts/*.sh` | Hook scripts | **Si** |
| `.claude/rules/*.md` | Reglas auto-inyectadas | **Si** |
| `.claude/skills/` | Skills instalados (skills.sh) | **Si** |
| `.agent/brain/concepts/` | Nodos concepts del Brain | **Si** |
| `.agent/brain/sessions/` | Nodos sessions del Brain | **Si** |
| `.agent/brain/patterns/` | Nodos patterns del Brain | **Si** |
| `.agent/brain/index.md` | Indice reconstruido del Brain | **Si** |
| `.agent/brain/log.md` | Log append-only de operaciones | **Si** |
| `~/.claude/projects/.../memory/` | Auto-memory externo de Claude Code | No (cache) |
| `~/.antigravity/memory/` | Cache mem0 (capa 3) | No (cache) |

**Excepcion**: `.claude/worktrees/` se ignora porque son temporales de sesion.
