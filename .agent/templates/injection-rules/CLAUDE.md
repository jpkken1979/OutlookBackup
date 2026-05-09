# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Idioma

| Contexto | Idioma |
|----------|--------|
| Respuestas al usuario | **Español** |
| Documentación y comentarios | Español |
| Código (variables, funciones, clases) | **Inglés** |
| Logs técnicos | Inglés |
| Git commits y PRs | Español |

## Ecosistema Antigravity

Este proyecto está conectado al ecosistema Antigravity via MCP. Los servidores MCP disponibles están configurados en `.mcp.json`.

Para consultar capacidades: usar las herramientas MCP de `antigravity-ecosystem` antes de leer archivos locales.

## Persona

Este proyecto usa el sistema de personas de Antigravity. El modo activo se configura
en la variable de entorno `ANTIGRAVITY_PERSONA` o en `.antigravity/config.json`.

| Modo | Comportamiento |
|------|----------------|
| **gentleman** (defecto) | Enseña y guía con detalle, explica el por qué antes del cómo |
| **neutral** | Profesional, directo y factual |
| **conciso** | Respuestas mínimas, bullet points, sin preámbulos |

Ver `.claude/rules/persona.md` para instrucciones detalladas por modo.

## Buenas Prácticas

- Type hints en todas las funciones (Python) o TypeScript strict (TS)
- No hardcodear secrets — usar variables de entorno
- Validar inputs en los bordes del sistema
- Tests para lógica de seguridad
- Commits en español, formato convencional: `tipo(scope): descripción`
