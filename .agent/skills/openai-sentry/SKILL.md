---
name: openai-sentry
description: "Observabilidad read-only de Sentry. Lista issues, obtiene detalles de eventos y stack traces usando sentry_api.py. Requiere SENTRY_AUTH_TOKEN."
type: feature
---

# Sentry Observability

Integración read-only con Sentry para diagnóstico y observabilidad de errores.

## Requisitos

- `SENTRY_AUTH_TOKEN` — Token de autenticación de Sentry (variable de entorno)
- `SENTRY_ORG` — Slug de la organización
- `SENTRY_PROJECT` — Slug del proyecto (opcional, para filtrar)

## Comandos Disponibles

### List Issues
Lista los issues más recientes o filtrados:

```bash
python scripts/sentry_api.py list-issues \
  --org my-org \
  --project my-project \
  --status unresolved \
  --limit 10
```

### Issue Detail
Obtiene detalles completos de un issue específico:

```bash
python scripts/sentry_api.py issue-detail \
  --org my-org \
  --issue-id 12345
```

Retorna:
- Titulo y mensaje de error
- Frecuencia y usuarios afectados
- Primera y última ocurrencia
- Tags asociados
- Stack trace del último evento

### Event Detail
Obtiene un evento específico con su contexto completo:

```bash
python scripts/sentry_api.py event-detail \
  --org my-org \
  --issue-id 12345 \
  --event-id abc123
```

Retorna:
- Stack trace completo
- Breadcrumbs (acciones del usuario antes del error)
- Device/browser context
- Request data (headers, body)
- Custom tags y extra data

## Script sentry_api.py

```python
#!/usr/bin/env python3
"""Sentry API client for observability queries."""

import os
import requests
import json
import sys

SENTRY_BASE = "https://sentry.io/api/0"
AUTH_TOKEN = os.environ.get("SENTRY_AUTH_TOKEN")

def list_issues(org: str, project: str | None = None,
                status: str = "unresolved", limit: int = 10) -> list[dict]:
    """Lista issues de Sentry."""
    url = f"{SENTRY_BASE}/organizations/{org}/issues/"
    params = {"query": f"is:{status}", "limit": limit}
    if project:
        params["project"] = project
    headers = {"Authorization": f"Bearer {AUTH_TOKEN}"}
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    return response.json()

def issue_detail(org: str, issue_id: str) -> dict:
    """Obtiene detalle de un issue."""
    url = f"{SENTRY_BASE}/organizations/{org}/issues/{issue_id}/"
    headers = {"Authorization": f"Bearer {AUTH_TOKEN}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()

def event_detail(org: str, issue_id: str, event_id: str) -> dict:
    """Obtiene detalle de un evento específico."""
    url = f"{SENTRY_BASE}/organizations/{org}/issues/{issue_id}/events/{event_id}/"
    headers = {"Authorization": f"Bearer {AUTH_TOKEN}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()
```

## Casos de Uso

1. **Triaje de errores** — Listar issues no resueltos por frecuencia.
2. **Root cause analysis** — Examinar stack traces y breadcrumbs.
3. **Impact assessment** — Ver usuarios afectados y frecuencia.
4. **Regression detection** — Detectar issues que reaparecen.

## Seguridad

- Token de Sentry **NUNCA** hardcodeado — siempre via `SENTRY_AUTH_TOKEN`
- Solo operaciones de lectura — no modificar, resolver ni eliminar issues
- Rate limiting: respetar los headers `X-Sentry-Rate-Limit-*`

## Recursos

- [Sentry API Docs](https://docs.sentry.io/api/)
- [Authentication](https://docs.sentry.io/api/auth/)
