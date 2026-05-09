---
name: openai-sora
description: "Genera video con Sora (sora-2, sora-2-pro). Usa cuando el usuario quiere crear, remixar o generar videos por lotes con prompt augmentation estructurado."
type: feature
---

# Sora Video Generation

Genera videos a partir de prompts de texto usando los modelos Sora de OpenAI.

## Modelos Disponibles

| Modelo | Uso |
|--------|-----|
| `sora-2` | Video estándar (4s, 8s, 12s) |
| `sora-2-pro` | Alta calidad, detalles finos |

## Workflow

1. **Definir objetivo** — Qué tipo de video se necesita (escena, concepto, demo).
2. **Augmentar el prompt** — Usar la plantilla de structured prompt augmentation.
3. **Seleccionar parámetros** — Duración (4/8/12s), modelo, aspect ratio.
4. **Generar** — Ejecutar via API o script CLI.
5. **Revisar y iterar** — Evaluar resultado, ajustar prompt si necesario.

## Prompt Augmentation Template

```
Subject: [descripción del sujeto principal]
Setting: [ambiente, locación, contexto]
Action: [qué ocurre en la escena]
Camera: [ángulo, movimiento, tipo de toma]
Lighting: [iluminación natural/artificial, hora del día]
Style: [cinematográfico, animación, documental, etc.]
Mood: [tono emocional de la escena]
```

## Modos de Operación

### Create (Nuevo)
Genera video desde cero a partir de un text prompt.

### Remix
Modifica un video existente con nuevos parámetros o estilo.

### Batch
Genera múltiples videos con variaciones del mismo prompt.

## Script CLI

```bash
python scripts/sora.py --prompt "A cat walking on a beach at sunset" \
  --model sora-2 \
  --duration 8 \
  --aspect-ratio 16:9
```

## Guardrails

- **NO** generar contenido con menores en contextos inapropiados
- **NO** representar personas reales sin autorización
- **NO** recrear personajes con copyright
- Respetar las políticas de uso de OpenAI
- Verificar que el prompt no viola las restricciones de contenido

## Parámetros

| Parámetro | Valores | Default |
|-----------|---------|---------|
| `duration` | 4, 8, 12 segundos | 8 |
| `model` | sora-2, sora-2-pro | sora-2 |
| `aspect_ratio` | 16:9, 9:16, 1:1 | 16:9 |
| `resolution` | 480p, 720p, 1080p | 720p |

## Recursos

- [OpenAI Sora API Docs](https://platform.openai.com/docs/guides/video-generation)
- [Sora Prompt Guide](https://platform.openai.com/docs/guides/video-generation/prompting)
