---
name: openclaw-integration
description: "Integración bidireccional con el ecosistema OpenClaw. Permite importar skills de ClawHub al Antigravity, exportar skills al formato OpenClaw, conectar con Gateway OpenClaw y sincronizar agentes entre ambos ecosistemas. Triggers: openclaw, clawhub, import skills, export skills, ecosystem integration."
type: feature
---

# OpenClaw Integration Skill

## Metadata

| Campo | Valor |
|-------|-------|
| **Nombre** | openclaw-integration |
| **Versión** | 1.0.0 |
| **Categoría** | AI/Agents |
| **Autor** | Antigravity Team |
| **Licencia** | MIT |
| **Dependencias** | httpx, pydantic |

---

## Descripción

Skill para integración bidireccional con el ecosistema **OpenClaw** (anteriormente ClawdBot/Moltbot).

OpenClaw es un asistente de IA personal de código abierto con 100K+ estrellas en GitHub que destaca por:
- Local-first execution
- Multi-channel messaging (WhatsApp, Telegram, Discord, etc.)
- 1,715+ skills disponibles
- ClawHub marketplace

Esta skill permite:
1. **Importar skills de ClawHub** al ecosistema Antigravity
2. **Exportar skills de Antigravity** al formato OpenClaw
3. **Conectar con Gateway OpenClaw** para comunicación entre ecosistemas
4. **Sincronizar agentes** entre ambos sistemas

---

## Inputs

| Parámetro | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| `action` | string | Sí | Acción a realizar: `import`, `export`, `sync`, `connect` |
| `skill_name` | string | No | Nombre del skill a importar/exportar |
| `openclaw_url` | string | No | URL del Gateway OpenClaw |
| `api_key` | string | No | API key para autenticación |

---

## Outputs

```json
{
  "success": true,
  "action": "import",
  "result": {
    "skill_name": "playwright-pro",
    "version": "1.2.0",
    "installed_path": ".agent/skills/playwright-pro/"
  }
}
```

---

## Uso

### Importar skill de ClawHub

```bash
python .agent/skills/openclaw-integration/scripts/openclaw_integration.py \
  --action import \
  --skill-name playwright-pro
```

### Exportar skill a formato OpenClaw

```bash
python .agent/skills/openclaw-integration/scripts/openclaw_integration.py \
  --action export \
  --skill-name browser-automation \
  --output-dir ./exported/
```

### Conectar con Gateway OpenClaw

```bash
python .agent/skills/openclaw-integration/scripts/openclaw_integration.py \
  --action connect \
  --openclaw-url ws://192.168.1.100:18789
```

### Sincronizar agentes

```bash
python .agent/skills/openclaw-integration/scripts/openclaw_integration.py \
  --action sync
```

---

## Arquitectura

```
┌─────────────────────────────────────────────────────────┐
│                 ANTIGRAVITY ECOSYSTEM                   │
│                                                         │
│  ┌─────────────┐     ┌──────────────────────┐          │
│  │   Agents    │────▶│  OpenClaw Integration │          │
│  │   (52+)     │     │        Skill          │          │
│  └─────────────┘     └──────────┬───────────┘          │
│                                 │                       │
│  ┌─────────────┐                │                       │
│  │   Skills    │◀───────────────┤                       │
│  │   (677+)    │                │                       │
│  └─────────────┘                │                       │
│                                 │                       │
└─────────────────────────────────┼───────────────────────┘
                                  │
                                  │ WebSocket / HTTP
                                  │
┌─────────────────────────────────▼───────────────────────┐
│                  OPENCLAW ECOSYSTEM                     │
│                                                         │
│  ┌─────────────┐     ┌──────────────────────┐          │
│  │  Gateway    │────▶│      ClawHub         │          │
│  │  Server     │     │   (1,715+ skills)    │          │
│  └─────────────┘     └──────────────────────┘          │
│                                                         │
│  ┌─────────────┐     ┌──────────────────────┐          │
│  │  Channels   │     │      Agents          │          │
│  │ (Multi)     │     │                      │          │
│  └─────────────┘     └──────────────────────┘          │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## Mapeo de Skills

| OpenClaw Category | Antigravity Category | Count |
|-------------------|---------------------|-------|
| Coding Agents & IDEs | AI/Agents | 55 |
| Web & Frontend | Frontend & UI | 46 |
| Git & GitHub | DevOps | 34 |
| Browser & Automation | Automation | 69 |
| AI & LLMs | AI/Agents | 159 |
| DevOps & Cloud | DevOps | 144 |

---

## Configuración

Crear archivo `.env` con:

```env
# OpenClaw Integration
OPENCLAW_GATEWAY_URL=ws://127.0.0.1:18789
OPENCLAW_API_KEY=your-api-key
CLAWHUB_REGISTRY_URL=https://clawhub.io/api/v1
```

---

## Referencias

- [OpenClaw GitHub](https://github.com/clawdbot/clawdbot)
- [ClawHub Registry](https://github.com/VoltAgent/awesome-clawdbot-skills)
- [OpenClaw Documentation](https://clawd.bot/)
- [Claude Code Skills for Clawdbot](https://github.com/justbecauselabs/clawd-skills)

---

## Changelog

### 1.0.0 (2026-02-03)
- Initial release
- Import/export skills
- Gateway connection
- Agent synchronization
