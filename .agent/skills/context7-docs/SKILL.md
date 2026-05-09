---
name: context7-docs
description: Obtiene documentación actualizada de librerías y frameworks via Context7 MCP
type: feature
---

# Context7 Documentation Skill

> Obtiene documentación actualizada de librerías y frameworks via Context7 MCP.

## Metadata

| Campo | Valor |
|-------|-------|
| **Nombre** | context7-docs |
| **Versión** | 1.0.0 |
| **Categoría** | documentation, ai, mcp |
| **Requiere** | Node.js >= 18, API Key (opcional) |

## Descripción

Context7 resuelve el problema de documentación desactualizada en LLMs.
Proporciona documentación específica de versión directamente desde la fuente.

## Capacidades

- Resolver IDs de librerías (ej: "nextjs" → "/vercel/next.js/v15.0.0")
- Obtener documentación actualizada con ejemplos de código
- Filtrar por tópico específico
- Limitar tokens de respuesta

## Herramientas MCP

### resolve-library-id
```json
{
  "name": "resolve-library-id",
  "parameters": {
    "query": "pregunta del usuario",
    "libraryName": "nombre de la librería"
  }
}
```

### query-docs
```json
{
  "name": "query-docs",
  "parameters": {
    "libraryId": "/vercel/next.js",
    "query": "cómo configurar middleware"
  }
}
```

## Uso

### En prompts
Agregar "use context7" al final del prompt:
```
Cómo configuro autenticación con Supabase? use context7
```

### Con librería específica
```
Implementar SSR con Next.js 15. use library /vercel/next.js
```

### Via script
```bash
python .agent/skills/context7-docs/scripts/context7.py "next.js middleware"
```

## Librerías Soportadas (ejemplos)

| Librería | Context7 ID |
|----------|-------------|
| Next.js | /vercel/next.js |
| React | /facebook/react |
| Supabase | /supabase/supabase |
| Prisma | /prisma/prisma |
| Tailwind | /tailwindlabs/tailwindcss |
| MongoDB | /mongodb/docs |
| FastAPI | /tiangolo/fastapi |
| Django | /django/django |

## Configuración

### API Key (recomendado)
Obtener en: https://context7.com/dashboard

### Variables de entorno
```bash
export CONTEXT7_API_KEY="tu-api-key"
```

## Integración con Agentes

Este skill es usado por:
- `docs-specialist` - Agente especializado en documentación
- `frontend-specialist` - Para docs de React, Next.js, etc.
- `backend-specialist` - Para docs de FastAPI, Django, etc.

## Referencias

- [GitHub](https://github.com/upstash/context7)
- [Documentación](https://context7.com)
- [MCP Smithery](https://smithery.ai/server/@upstash/context7-mcp)
