---
name: openai-transcribe
description: "Transcripción de audio con gpt-4o-mini-transcribe. Usa cuando necesites transcribir audio con diarización de hablantes, speaker hints y timestamps."
type: feature
---

# OpenAI Audio Transcription

Transcribe audio a texto con soporte de diarización usando modelos OpenAI.

## Modelos

| Modelo | Capacidad |
|--------|-----------|
| `gpt-4o-mini-transcribe` | Transcripción estándar de alta precisión |
| `gpt-4o-transcribe-diarize` | Transcripción + identificación de hablantes |

## Workflow

1. **Preparar audio** — Formato compatible (mp3, wav, m4a, webm, mp4).
2. **Configurar opciones** — Idioma, diarización, speaker hints.
3. **Transcribir** — Ejecutar via API o script CLI.
4. **Post-procesar** — Formatear output, extraer segmentos.

## Diarización de Hablantes

Identifica automáticamente quién habla en cada segmento:

```json
{
  "segments": [
    {
      "speaker": "Speaker 1",
      "start": 0.0,
      "end": 3.5,
      "text": "Good morning, let's start the meeting."
    },
    {
      "speaker": "Speaker 2",
      "start": 3.8,
      "end": 7.2,
      "text": "Sure, I have updates on the project."
    }
  ]
}
```

## Known Speaker Hints

Pre-identificar hablantes por nombre para mejor output:

```python
response = client.audio.transcriptions.create(
    model="gpt-4o-transcribe-diarize",
    file=audio_file,
    speaker_labels=True,
    speaker_hints=["Alice", "Bob", "Charlie"]
)
```

## Script CLI

```bash
python scripts/transcribe_diarize.py \
  --input recording.mp3 \
  --model gpt-4o-transcribe-diarize \
  --speakers "Alice,Bob" \
  --output transcript.json \
  --format diarized_json
```

## Formatos de Salida

| Formato | Descripción |
|---------|-------------|
| `text` | Texto plano sin timestamps |
| `json` | JSON con timestamps por segmento |
| `diarized_json` | JSON con speaker labels + timestamps |
| `srt` | Subtítulos SubRip |
| `vtt` | Web Video Text Tracks |

## Idiomas Soportados

Soporte multi-idioma automático. Para mejor precisión, especificar `language`:

```python
response = client.audio.transcriptions.create(
    model="gpt-4o-mini-transcribe",
    file=audio_file,
    language="es"  # ISO 639-1
)
```

## Recursos

- [OpenAI Transcription API](https://platform.openai.com/docs/guides/speech-to-text)
- [Supported Formats](https://platform.openai.com/docs/guides/speech-to-text/supported-formats)
