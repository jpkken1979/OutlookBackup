---
type: feature
name: htmx
description: Skill para implementar interactividad con HTMX, accediendo a features modernas del navegador directamente desde HTML
---

# HTMX

## Metadata
- **Name**: HTMX
- **Category**: Frontend
- **Version**: 1.0.0
- **Author**: Antigravity Team

## Description
Skill para implementar interactividad con HTMX - accede a features modernas del navegador directamente desde HTML.

## Capabilities
- AJAX requests desde atributos HTML
- CSS Transitions
- WebSockets y SSE
- History API
- Extensions
- Integración con backend frameworks

## Key Features
- **No JavaScript**: Interactividad sin escribir JS
- **Progressive enhancement**: Funciona sin JS habilitado
- **Small footprint**: ~14KB minified
- **Hypermedia-driven**: REST como fue diseñado

## Core Attributes
- `hx-get`, `hx-post`, `hx-put`, `hx-delete`: HTTP requests
- `hx-trigger`: Evento que dispara el request
- `hx-target`: Elemento a actualizar
- `hx-swap`: Cómo insertar el contenido
- `hx-indicator`: Loading indicator
- `hx-boost`: Mejora links y forms

## Usage
```bash
# Generar componente HTMX
python scripts/htmx.py component --name search --trigger keyup

# Generar endpoint backend
python scripts/htmx.py endpoint --framework fastapi --name search

# Generar ejemplo de patrón
python scripts/htmx.py pattern --name infinite-scroll

# Listar todos los atributos
python scripts/htmx.py attributes
```

## Inputs
- `component_name`: Nombre del componente
- `trigger`: Evento trigger (click, keyup, etc.)
- `target`: Selector del target
- `swap`: Método de swap (innerHTML, outerHTML, etc.)

## Outputs
- HTML con atributos HTMX
- Backend endpoint code
- CSS para transiciones

## Dependencies
- htmx.org (CDN o npm)

## Related Skills
- `fastapi-pro`
- `django-pro`
- `flask-patterns`
