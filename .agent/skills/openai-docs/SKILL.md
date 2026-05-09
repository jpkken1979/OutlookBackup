---
name: openai-docs
description: "Referencia de la documentación de desarrollador de OpenAI. Usa cuando necesites consultar APIs, SDKs o productos de OpenAI incluyendo Responses API, Agents SDK, Codex y Realtime."
type: feature
---

# OpenAI Developer Docs Reference

Referencia rápida de la documentación de OpenAI para desarrollo con sus APIs y SDKs.

## MCP Server Integration

Si disponible, usar las herramientas MCP para consultar docs:

```
mcp__openaiDeveloperDocs__search("query")   # Buscar en docs
mcp__openaiDeveloperDocs__fetch("url")       # Obtener página específica
mcp__openaiDeveloperDocs__list()             # Listar secciones
```

## Product Snapshots

### Apps SDK
SDK para construir aplicaciones con modelos OpenAI:
- Chat completions
- Function calling
- Structured outputs
- Vision y multimodal

### Responses API
API unificada para interacciones con modelos:
- Streaming responses
- Tool use
- Multi-turn conversations
- JSON mode / structured outputs

### Chat Completions API
Endpoint clásico para conversaciones:
- `POST /v1/chat/completions`
- Messages array con roles (system, user, assistant)
- Temperature, top_p, max_tokens

### Codex (Code Generation)
Modelos especializados en código:
- Code completion
- Code explanation
- Bug fixing
- Code review

### gpt-oss (Open Source)
Modelos open-source de OpenAI:
- Weights descargables
- Fine-tuning local
- Inference optimizada

### Realtime API
API para comunicación en tiempo real:
- WebSocket connections
- Audio streaming bidireccional
- Baja latencia
- Voice-to-voice

### Agents SDK
Framework para agentes autónomos:
- Tool definitions
- Multi-step reasoning
- Handoffs entre agentes
- Guardrails y safety

## Endpoints Principales

| Endpoint | Uso |
|----------|-----|
| `/v1/chat/completions` | Conversaciones con modelos |
| `/v1/embeddings` | Vectores de texto |
| `/v1/audio/speech` | Text-to-speech |
| `/v1/audio/transcriptions` | Speech-to-text |
| `/v1/images/generations` | Generación de imágenes |
| `/v1/moderations` | Moderación de contenido |

## Modelos Actuales

| Modelo | Tipo |
|--------|------|
| `gpt-4o` | Multimodal flagship |
| `gpt-4o-mini` | Eficiente y económico |
| `o1` | Reasoning avanzado |
| `o3-mini` | Reasoning económico |
| `gpt-4o-mini-tts` | Text-to-speech |
| `dall-e-3` | Generación de imágenes |

## Recursos

- [OpenAI Platform Docs](https://platform.openai.com/docs)
- [API Reference](https://platform.openai.com/docs/api-reference)
- [Cookbook](https://cookbook.openai.com)
