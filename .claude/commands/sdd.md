# SDD — Spec-Driven Development Orchestrator

Coordina el flujo de desarrollo basado en especificaciones en 9 fases secuenciales.
Cada fase produce un output concreto que alimenta la siguiente.

## Fases

| # | Fase | Comando | Propósito |
|---|------|---------|-----------|
| 1 | **Explore** | `/sdd-explore` | Investigar el codebase y entender el contexto |
| 2 | **Propose** | `/sdd-propose` | Proponer 2-3 soluciones con trade-offs |
| 3 | **Spec** | `/sdd-spec` | Escribir especificación técnica detallada |
| 4 | **Design** | `/sdd-design` | Diseñar arquitectura e interfaces |
| 5 | **Tasks** | `/sdd-tasks` | Descomponer en tareas ejecutables |
| 6 | **Apply** | `/sdd-apply` | Implementar los cambios |
| 7 | **Verify** | `/sdd-verify` | Verificar con tests, lint y typecheck |
| 8 | **Review** | `/sdd-review` | Code review automatizado |
| 9 | **Archive** | `/sdd-archive` | Documentar decisiones y aprendizajes |

## Instrucciones

Cuando el usuario describe una feature o cambio, ejecutar las fases secuencialmente:

1. Ejecutar cada fase en orden, produciendo el output esperado.
2. **Pausar después de cada fase** y presentar un resumen al usuario.
3. Esperar aprobación explícita (`ok`, `siguiente`, `next`, `continuar`) antes de avanzar.
4. Si el usuario pide cambios, iterar en la fase actual antes de avanzar.
5. El usuario puede saltar fases con `skip` o ir a una fase específica con `ir a fase N`.

## Regla de delegación

| Situación | Acción |
|-----------|--------|
| Leer 1-3 archivos | Inline en la fase actual |
| Leer 4+ archivos | Delegar a sub-agente |
| Escribir múltiples archivos | Delegar a sub-agente |
| Tests / build / lint | Delegar a sub-agente |
| Operación simple y rápida | Inline |

## Contexto del ecosistema

- Backend Python: `.agent/` (core, mcp, agents, skills)
- Desktop app: `nexus-app/` (Tauri 2 + React 19)
- Bot Telegram: `src/` (TypeScript, grammy)
- MCP server: `mcp-server/` (Python)
- Gateway: `start_gateway.py` → `:4747`

Respetar siempre las convenciones de `CLAUDE.md`: idioma, formato de commits, arquitectura de 4 capas, MCP-first.

## Formato de tracking

Al iniciar, crear un bloque de estado que se actualiza en cada fase:

```
## SDD Progress
- [x] Fase 1: Explore — completada
- [ ] Fase 2: Propose — en curso
- [ ] Fase 3: Spec
- [ ] Fase 4: Design
- [ ] Fase 5: Tasks
- [ ] Fase 6: Apply
- [ ] Fase 7: Verify
- [ ] Fase 8: Review
- [ ] Fase 9: Archive
```

---

Describe la feature o cambio que necesitas: $ARGUMENTS
