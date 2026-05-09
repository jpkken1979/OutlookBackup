# Regla: Arquitectura de 4 Capas

Todo el código debe respetar la separación de capas:

```
┌──────────────────────────────────────────┐
│ Capa 1: DIRECTIVA                        │
│ → SKILL.md, IDENTITY.md, rules.md        │
│ → Define QUÉ hacer y las restricciones  │
├──────────────────────────────────────────┤
│ Capa 2: CONTEXTO                         │
│ → .context/, memory/, data/              │
│ → Información persistente y estado      │
├──────────────────────────────────────────┤
│ Capa 3: EJECUCIÓN                        │
│ → scripts/, src/, tools/                │
│ → Código que realiza acciones           │
├──────────────────────────────────────────┤
│ Capa 4: OBSERVABILIDAD                   │
│ → logs/, artifacts/, dashboard/         │
│ → Evidencia y monitoreo                 │
└──────────────────────────────────────────┘
```

## Convenciones de Agentes

```
.agent/agents/<agent-name>/
├── IDENTITY.md         # Identidad, capacidades, tier
├── memory/
│   └── shared_memory.json
├── scripts/            # Implementación del agente
└── logs/               # Historial de ejecución
```

## Convenciones de Skills

```
<ide-dir>/skills/<skill-name>/
├── SKILL.md            # Documentación (requerida)
├── scripts/
│   └── main.py         # Entry point
├── logs/               # Auto-generados
└── utils/              # Utilidades compartidas
```

## Sistema de Tiers de Agentes (12 tiers)

Orchestration → Core Dev → Quality → Security → DevOps →
Specialized → UNS Enterprise → Intelligence → System →
Data & ML → Desktop → Content

Ver `CLAUDE.md` y `.antigravity/rules.md` para detalles completos.
