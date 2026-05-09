---
name: openai-speech
description: "Text-to-speech con gpt-4o-mini-tts. Usa cuando el usuario necesita generar audio narrado, voiceover, IVR o contenido de accesibilidad con control fino de voz."
type: feature
---

# OpenAI Text-to-Speech

Genera audio hablado de alta calidad usando el modelo gpt-4o-mini-tts de OpenAI.

## Modelo

- **gpt-4o-mini-tts-2025-12-15** — TTS con instruction augmentation para control fino de voz.

## Voces Disponibles

| Voz | Características |
|-----|----------------|
| `cedar` | Clara, profesional, versátil |
| `marin` | Cálida, expresiva, conversacional |
| `alloy` | Neutral, balanceada |
| `echo` | Suave, contemplativa |
| `fable` | Expresiva, narrativa |
| `onyx` | Profunda, autoritaria |
| `nova` | Energética, juvenil |
| `shimmer` | Ligera, amigable |

## Workflow

1. **Preparar texto** — Limpiar y formatear el texto de entrada.
2. **Seleccionar voz** — Elegir la voz apropiada para el caso de uso.
3. **Configurar instrucciones** — Usar instruction augmentation para tono/estilo.
4. **Generar audio** — Ejecutar via API o script CLI.
5. **Revisar calidad** — Escuchar y ajustar si necesario.

## Instruction Augmentation Template

```
Voice Affect: [cheerful, serious, empathetic, authoritative]
Tone: [warm, clinical, casual, formal]
Pacing: [slow, moderate, fast, varied]
Emotion: [neutral, excited, calm, urgent]
Pronunciation: [notas especiales para nombres, acrónimos, etc.]
```

## Casos de Uso

- **Narración** — Audiobooks, podcasts, documentales
- **Voiceover** — Videos corporativos, tutoriales
- **IVR** — Sistemas de respuesta de voz interactiva
- **Accesibilidad** — Lectura de contenido para usuarios con discapacidad visual
- **E-learning** — Cursos y material educativo

## Script CLI

```bash
python scripts/text_to_speech.py \
  --text "Bienvenido al sistema Antigravity" \
  --voice cedar \
  --instructions "Voice Affect: professional; Tone: warm; Pacing: moderate" \
  --output output/welcome.mp3
```

## API Example

```python
from openai import OpenAI

client = OpenAI()

response = client.audio.speech.create(
    model="gpt-4o-mini-tts",
    voice="cedar",
    input="Hello, welcome to our platform.",
    instructions="Speak in a warm, professional tone with moderate pacing."
)

response.stream_to_file("output.mp3")
```

## Formatos de Salida

- MP3 (default)
- WAV
- FLAC
- AAC
- OGG/Opus

## Recursos

- [OpenAI TTS API](https://platform.openai.com/docs/guides/text-to-speech)
- [Voice Guide](https://platform.openai.com/docs/guides/text-to-speech/voice-options)
