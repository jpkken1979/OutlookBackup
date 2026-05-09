---
name: nano-banana-pro
description: Generación de imágenes con IA usando FLUX (HuggingFace, gratis) o Google Gemini. Usar cuando el usuario pida "generar imagen", "crear imagen", "nano banana", o solicite assets visuales. Para uso inmediato sin costo usar flux-schnell con HF_TOKEN.
---

# Nano Banana Pro — Generación de Imágenes con IA

Genera imágenes usando FLUX.1-schnell (HuggingFace, **gratis**) o modelos Gemini de Google.

## Modelos Disponibles

### HuggingFace — Gratis (recomendado para empezar)

| Modelo | ID real | Descripción |
|--------|---------|-------------|
| **flux-schnell** | `black-forest-labs/FLUX.1-schnell` | FLUX rápido, Apache 2.0, **recomendado** |
| **sdxl** | `stabilityai/stable-diffusion-xl-base-1.0` | Stable Diffusion XL |

Requiere `HF_TOKEN` gratuito: https://huggingface.co/settings/tokens

### Gemini — Requiere billing (~$0.04/imagen)

| Modelo | ID real | Descripción |
|--------|---------|-------------|
| **nanobanana** | `gemini-2.5-flash-image` | El modelo "Nano Banana" original |
| **nanobanana-pro** | `gemini-3-pro-image-preview` | Máxima calidad |
| **flash** | `gemini-3.1-flash-image-preview` | Más rápido |
| **exp** | `gemini-2.0-flash-exp-image-generation` | Experimental |

Requiere `GEMINI_API_KEY` + billing en Google Cloud.

## Setup Rápido (HuggingFace, gratis)

```bash
# 1. Obtener token gratis en https://huggingface.co/settings/tokens
# 2. Configurar en el entorno
export HF_TOKEN=hf_xxxxxxxxxxxxxxxx

# 3. Generar imagen
uv run .agent/skills-custom/nano-banana-pro/scripts/image.py \
  --prompt "Descripción de la imagen" \
  --output "./assets/imagen.png" \
  --model flux-schnell
```

## Uso Completo

```bash
uv run .agent/skills-custom/nano-banana-pro/scripts/image.py \
  --prompt "Un patrón geométrico minimalista en azul marino" \
  --output "./hero.png" \
  --model flux-schnell \
  --aspect landscape
```

**Opciones:**
- `--prompt` (requerido): Descripción detallada de la imagen
- `--output` (requerido): Ruta de salida (PNG/JPG)
- `--aspect`: `square` (1024x1024) | `landscape` (1280x720) | `portrait` (720x1280)
- `--model`: Ver tabla de modelos arriba (default: `flux-schnell`)
- `--width` / `--height`: Tamaño personalizado en píxeles

## Integrar en Frontend

```html
<img src="./assets/hero.png" alt="Hero" class="hero-image" />
```

```jsx
import heroImage from './assets/hero.png';
<img src={heroImage} alt="Hero" className="hero-image" />
```

## Prompts Efectivos

Incluir en el prompt:
1. **Sujeto**: Qué muestra la imagen
2. **Estilo**: Minimalista, abstracto, fotorrealista, ilustrado
3. **Colores**: Paleta específica
4. **Tono**: Profesional, dinámico, elegante
5. **Contexto**: Hero, ícono, textura, ilustración

**Ejemplo:**
> Un patrón geométrico minimalista con círculos translúcidos en coral, teal y dorado sobre fondo azul marino profundo, para sección hero de landing page fintech moderna

## Ubicación de Salida Recomendada

- `./assets/` para proyectos HTML simples
- `./src/assets/` o `./public/` para React/Vue
- Nombres descriptivos: `hero-abstract-gradient.png`, `icon-user.png`
