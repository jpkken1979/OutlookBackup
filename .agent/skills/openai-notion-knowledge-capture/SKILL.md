---
name: openai-notion-knowledge-capture
description: "Captura conocimiento de conversaciones y lo estructura en páginas Notion (wiki entries, how-tos, FAQs, decisiones). Requiere Notion MCP."
type: feature
---

# Notion Knowledge Capture

Convierte conversaciones e información en páginas estructuradas de Notion.

## Setup

```bash
# Agregar Notion MCP server
mcp add notion --url https://mcp.notion.com/mcp
```

## Tipos de Documentos

### Wiki Entry
Entrada de conocimiento enciclopédica:
- Definición clara
- Contexto y antecedentes
- Ejemplos prácticos
- Referencias cruzadas

### How-To Guide
Guía paso a paso:
- Prerequisitos
- Pasos numerados
- Troubleshooting
- Resultado esperado

### FAQ
Preguntas frecuentes:
- Pregunta clara
- Respuesta concisa
- Contexto adicional
- Links a recursos

### Decision Record
Registro de decisión arquitectónica:
- Contexto del problema
- Opciones consideradas
- Decisión tomada
- Consecuencias y trade-offs

## Workflow

1. **Identificar conocimiento** — Detectar información valiosa en la conversación.
2. **Clasificar tipo** — Wiki, how-to, FAQ o decisión.
3. **Estructurar contenido** — Aplicar la plantilla correspondiente.
4. **Crear en Notion** — Usar la API/MCP para crear la página.
5. **Vincular** — Agregar links cruzados a páginas relacionadas.

## Plantilla de Wiki Entry

```markdown
# [Título del Tema]

## Definición
[Descripción clara y concisa]

## Contexto
[Por qué es relevante, antecedentes]

## Detalles Técnicos
[Especificaciones, implementación]

## Ejemplos
[Casos de uso prácticos]

## Referencias
- [Link 1]
- [Link 2]

## Metadata
- Creado: [fecha]
- Última actualización: [fecha]
- Tags: [tag1, tag2]
```

## API de Notion MCP

```javascript
// Crear página
mcp__notion__create_page({
  parent: { database_id: "abc123" },
  properties: {
    "Name": { title: [{ text: { content: "Mi Documento" } }] },
    "Type": { select: { name: "Wiki" } },
    "Tags": { multi_select: [{ name: "python" }, { name: "api" }] }
  },
  children: [
    {
      type: "heading_1",
      heading_1: { rich_text: [{ text: { content: "Definición" } }] }
    },
    {
      type: "paragraph",
      paragraph: { rich_text: [{ text: { content: "..." } }] }
    }
  ]
})
```

## Best Practices

- Títulos descriptivos y buscables
- Tags consistentes para categorización
- Links cruzados entre documentos relacionados
- Actualizar contenido existente antes de crear duplicados
- Incluir fecha de última revisión

## Recursos

- [Notion API](https://developers.notion.com/)
- [Notion MCP](https://github.com/makenotion/notion-mcp-server)
