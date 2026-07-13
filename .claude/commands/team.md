# /team — Task List Teams (Agent Teams)

## Uso
- `/team create <nombre> <lead>` — Crear equipo nuevo
- `/team status <nombre>` — Ver estado del equipo
- `/team add <nombre> <agente>` — Agregar teammate al equipo
- `/team task add <nombre> <desc>` — Agregar tarea al backlog
- `/team task claim <nombre> <task_id> <agente>` — Reclamar tarea
- `/team task complete <nombre> <task_id>` — Completar tarea
- `/team lock <nombre> acquire <file> <agent> <task_id>` — Adquirir lock
- `/team lock <nombre> release <file>` — Liberar lock
- `/team list` — Listar todos los equipos
- `/team delete <nombre>` — Eliminar equipo

## Descripcion

Sistema de lead + teammates con task list compartida:
- **Task list**: pending / in_progress / completed / blocked
- **File locking**: previene race conditions
- **Self-claim**: al completar, auto-busca la siguiente tarea
- **El lead solo orquesta**, no ejecuta

Inspirado en la arquitectura de equipos de Claude Code.

## Concepto

```
Lead (orquesta) ──> Teammate A (ejecuta tarea 1)
                ──> Teammate B (ejecuta tarea 2, bloqueada por A)
                ──> Teammate C (espera, auto-claim al terminar B)

Estado compartido:
  ~/.antigravity/teams/{team_name}/state.json
  ~/.antigravity/teams/{team_name}/log.jsonl
```

## Comandos detallados

### Crear equipo
```
/team create auth-team architect
```
Crea un equipo `auth-team` con `architect` como lead.

### Agregar teammates
```
/team add auth-team coder
/team add auth-team reviewer
```

### Agregar tareas
```
/team task add auth-team "Implementar endpoint /login con JWT"
/team task add auth-team "Escribir tests de autenticacion" --priority 2
/team task add auth-team "Auditar seguridad" --blocked-by <task_id>
```

### Workflow tipico
```
/team task add auth-team "Diseñar schema de usuarios"
/team task add auth-team "Implementar API /users" --blocked-by <schema_task_id>
/team task add auth-team "Implementar API /auth" --blocked-by <users_task_id>

/team task claim auth-team <schema_id> coder
# coder ejecuta...
/team task complete auth-team <schema_id>  # auto-claim para /users
/team task claim auth-team <users_id> coder
# coder ejecuta...
/team task complete auth-team <users_id>  # auto-claim para /auth
```

### File locking
```
/team lock auth-team acquire src/auth/login.ts coder <task_id>
# coder puede editar login.ts sin race condition
/team lock auth-team release src/auth/login.ts  # al terminar
```

### Ver estado
```
/team status auth-team
```
Muestra: miembros, progreso (X/Y completadas), tareas por estado, locks activos.

## Ejemplos concretos

### Equipo para feature multi-archivo
```
/team create api-team architect
/team add api-team backend-dev
/team add api-team frontend-dev

# El lead (architect) descompone la tarea
/team task add api-team "Crear schema de database" --priority 2
/team task add api-team "Implementar endpoints REST" --priority 1
/team task add api-team "Integrar frontend con API" --priority 1

/team task claim api-team <schema_task> backend-dev
/team task claim api-team <endpoints_task> backend-dev
/team task claim api-team <frontend_task> frontend-dev

# Locks para prevenir conflicts
/team lock api-team acquire src/db/schema.ts backend-dev <schema_task>
/team lock api-team acquire src/api/routes.ts backend-dev <endpoints_task>
/team lock api-team acquire src/frontend/api.ts frontend-dev <frontend_task>
```

## Storage

- Estado: `~/.antigravity/teams/{team_name}/state.json`
- Log de eventos: `~/.antigravity/teams/{team_name}/log.jsonl`
- Persiste entre sesiones (sobrevive cierres del IDE)

## Integracion con orchestrator

El lead usa el `TaskListManager` para orquestar, pero la ejecucion real
de los teammates va por el orchestrator existente (via gateway HTTP
o script `invoke-agent.py`).