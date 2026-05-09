---
name: nanobanana-ppt-skills
description: "Genera PPTs de alta calidad con IA: análisis de documentos, imágenes Gemini (2K/4K), estilos profesionales y transiciones de video con Kling AI (v2.0)"
source: "https://github.com/op7418/NanoBanana-PPT-Skills"
version: "2.0.0"
risk: safe
requires:
type: feature
---
  - GEMINI_API_KEY (obligatorio)
  - KLING_ACCESS_KEY (opcional, solo para video)
  - KLING_SECRET_KEY (opcional, solo para video)
  - FFmpeg (opcional, solo para exportar video completo)
tags: [ppt, presentaciones, gemini, kling-ai, video, imagen, ia-generativa]
type: feature
---

# NanoBanana PPT Skills

> Genera presentaciones profesionales con IA  imágenes 2K/4K + transiciones de video con un solo comando.

## Cuándo usar esta skill?

- El usuario quiere generar una presentación PPT desde un documento o texto
- Necesita diapositivas visuales de alta calidad para demo, pitch o pitch deck
- Quiere añadir transiciones animadas entre slides (Kling AI)
- Necesita exportar la presentación como video MP4

---

## Dependencias y API Keys

| Variable | Obligatoria | Propósito |
|---|---|---|
| `GEMINI_API_KEY` |  Sí | Genera imágenes de slides via Gemini 3 Pro (Nano Banana Pro) |
| `KLING_ACCESS_KEY` |  Opcional | Transiciones de video con Kling AI |
| `KLING_SECRET_KEY` |  Opcional | Transiciones de video con Kling AI |

**Obtener claves:**
- Gemini: https://aistudio.google.com/apikey (gratuita con límites)
- Kling AI: https://klingai.com/ (requiere cuenta)

---

## Instalación rápida

```bash
# 1. Clonar el repo
git clone https://github.com/op7418/NanoBanana-PPT-Skills.git
cd NanoBanana-PPT-Skills

# 2. Entorno virtual
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Dependencias base
pip install google-genai pillow python-dotenv

# 4. FFmpeg (opcional, para exportar video)
# macOS:   brew install ffmpeg
# Ubuntu:  sudo apt-get install ffmpeg
# Windows: descargar de ffmpeg.org, añadir al PATH

# 5. Configurar API keys
cp .env.example .env
# Editar .env con tus claves
```

`.env` mínimo:
```
GEMINI_API_KEY=tu_api_key_aqui
KLING_ACCESS_KEY=tu_kling_access_key   # opcional
KLING_SECRET_KEY=tu_kling_secret_key   # opcional
```

---

## Flujo de trabajo principal

### FASE 1  Planificar el contenido (slides_plan.json)

Claude analiza el documento y genera el plan automáticamente. Pasos:
1. El usuario comparte el documento/texto
2. Claude pregunta: estilos, número de páginas, resolución
3. Claude genera `slides_plan.json`

**Estructura del plan:**
```json
{
  "title": "Mi Presentación",
  "total_slides": 5,
  "slides": [
    { "slide_number": 1, "page_type": "cover",   "content": "Título: ...\nSubtítulo: ..." },
    { "slide_number": 2, "page_type": "content",  "content": "Puntos:\n- Punto 1\n- Punto 2" },
    { "slide_number": 3, "page_type": "data",     "content": "Antes: 65%\nDespués: 92%\nMejora: +27%" }
  ]
}
```

**Tipos de página:**
| Tipo | Descripción |
|---|---|
| `cover` | Portada principal con título y subtítulo |
| `content` | Slide de contenido con puntos o texto |
| `data` | Slide de datos/métricas con comparativas |

---

### FASE 2  Generar imágenes PPT

```bash
python3 generate_ppt.py \
  --plan slides_plan.json \
  --style styles/gradient-glass.md \
  --resolution 2K
```

**Output:** `outputs/TIMESTAMP/`
- `images/slide_01.png ... slide_N.png`  imágenes generadas
- `index.html`  reproductor HTML5 interactivo
- `prompts.json`  prompts usados (reproducibilidad)

---

### FASE 3  Generar video con transiciones (opcional)

Requiere Kling AI + FFmpeg.

```bash
# Paso 1: Generar prompts de transición (en Claude Code):
# "Analiza imágenes en outputs/TIMESTAMP/images,
#  genera transition_prompts.json para cada transición"

# Paso 2: Generar los videos
python3 generate_ppt_video.py \
  --slides-dir outputs/TIMESTAMP/images \
  --output-dir outputs/TIMESTAMP_video \
  --prompts-file outputs/TIMESTAMP/transition_prompts.json \
  --mode professional \
  --duration 5
```

**Output:** `outputs/TIMESTAMP_video/`
- `videos/`  clips de transición
- `video_index.html`  reproductor interactivo
- `full_ppt_video.mp4`  video MP4 completo

---

## Estilos disponibles

### `gradient-glass.md`  Glassmorphism / Apple Keynote
- Degradados neón: violeta / azul eléctrico / coral
- Objetos 3D de vidrio + iluminación cinematográfica
- **Ideal para:** tech, pitch empresarial, demos

### `vector-illustration.md`  Ilustración vectorial
- Diseño plano retro con contornos negros
- Colores vintage cálidos y geométricos
- **Ideal para:** educación, creatividad, branding cálido

### Añadir estilo propio
Crear un archivo `.md` en `styles/` describiendo el estilo visualmente (como un prompt de imagen), luego usarlo con `--style styles/mi-estilo.md`.

---

## Resolución y tiempos

| Resolución | Dimensiones | Peso/página | Tiempo/página | Uso recomendado |
|---|---|---|---|---|
| `2K` | 27521536 | ~2.5 MB | ~30 seg | Online, demos  |
| `4K` | 55043072 | ~8 MB | ~60 seg | Impresión, pantallas grandes |

**Páginas recomendadas:**
- 3-5 páginas  Elevator pitch / intro rápida
- 5-10 páginas  Demo estándar / presentación de producto
- 10-15 páginas  Pitch deck completo / formación
- 20-25 páginas  Seminario / capacitación profunda

---

## Atajos del reproductor interactivo

| Tecla | Acción |
|---|---|
| `` / `` | Siguiente slide (reproduce transición  muestra imagen 2s) |
| `` / `` | Slide anterior |
| `Home` | Portada (preview en loop) |
| `End` | Última slide |
| `Espacio` | Pausa/continua video |
| `ESC` | Pantalla completa |
| `H` | Mostrar/ocultar controles |

**Exportar a PDF:** Abrir `index.html`  `Ctrl+P`  "Guardar como PDF"

---

## Checklist antes de generar

```
[ ] GEMINI_API_KEY configurada en .env
[ ] Número de slides decidido (recomendado: 5-10)
[ ] Estilo elegido según audiencia
[ ] slides_plan.json preparado con page_type correcto
[ ] Resolución seleccionada según destino final
[ ] (Opcional) Kling AI configurada para transiciones
[ ] (Opcional) FFmpeg instalado para exportar MP4
```

---

## Solución de problemas

| Problema | Solución |
|---|---|
| `GEMINI_API_KEY not found` | Verificar que `.env` existe en el directorio del script |
| Imágenes lentas / timeout | Usar 2K; limitar a 5 slides por batch |
| FFmpeg error | `ffmpeg -version` para verificar; reinstalar si falla |
| Kling AI lento | Normal: 30-60 seg/transición |
| Error API Kling | Verificar KLING_ACCESS_KEY y KLING_SECRET_KEY |

---

## Prompt de inicio rápido

Compartir con Claude al iniciar:

```
Quiero generar un PPT con NanoBanana PPT Skills.

Documento/Tema:
[PEGAR CONTENIDO AQUÍ]

Preferencias:
- Slides: [5 / 8 / 10]
- Estilo: [gradient-glass / vector-illustration]
- Resolución: [2K / 4K]
- Video con transiciones: [sí / no]

Por favor: (1) analiza el contenido, (2) planifica slides_plan.json,
(3) ejecuta generate_ppt.py para crear las imágenes.
```

---

## Seguridad

- **NUNCA** commitear `.env` con API keys reales
- `.env` está en `.gitignore`  no modificar esa regla
- Verificar antes de push: `grep -r "AIzaSy" --exclude-dir=.git .` (debe dar vacío)

---

*Fuente: https://github.com/op7418/NanoBanana-PPT-Skills  MIT License  v2.0.0*
