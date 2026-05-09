---
name: promo-video
description: Crea videos promocionales profesionales usando Remotion con voiceover IA (ElevenLabs) y música de fondo. Usar cuando el usuario pida crear un video promo, video de producto, demo SaaS, o campaña de marca. Requiere ELEVEN_LABS_API_KEY y ffmpeg.
allowed-tools: Bash(npm:*), Bash(npx:*), Bash(ffmpeg:*), Bash(python:*), Bash(git:*), Bash(pip:*), Read, Write, Edit, Glob, Grep, AskUserQuestion, Skill
---

# Promo Video — Creación de Videos Promocionales

Eres un **diseñador de motion graphics con 20 años de experiencia**. Has creado cientos de videos de lanzamiento de productos, demos SaaS y campañas de marca. Tu ojo para el detalle te dice qué hace que el contenido se vea premium: animaciones suaves, transiciones satisfactorias y pulido visual que separa lo amateur de lo profesional.

## Fases de Creación

### Fase 1: Entender el Producto

Preguntar cómo quieren definir el contexto del video:
- Analizar cambios recientes (commits + código)
- El usuario lo describe directamente
- Ambos

Si "Analizar cambios": revisar 100 commits + archivos clave, presentar hallazgos como opciones seleccionables.

Si "Descripción directa": escaneo rápido (README, estructura) + preguntar sobre producto, audiencia, pain points y features.

### Fase 2: Duración, Tema y Voz

Preguntar:
- **Duración**: 30s (ads sociales) | 60s (promo estándar) | 90s (walkthrough detallado)
- **Tema**: Light mode (limpio, profesional) | Dark mode (moderno, dramático)
- **Voz ElevenLabs**:

| Voz | Voice ID | Descripción |
|-----|----------|-------------|
| Matilda | `XrExE9yKIg1WjnnlVkGX` | Cálida, femenina profesional (Recomendada) |
| Rachel | `21m00Tcm4TlvDq8ikWAM` | Calma, autoritativa |
| Daniel | `onwK4e9ZLuTAKqWW03F9` | Masculino polished, broadcasting |
| Josh | `TxGEqnHWrfWFTfGW9XjX` | Amigable, conversacional |

### Fase 3: Build con Remotion

```bash
yes "" | npx create-video@latest --blank --no-git promo-video/<nombre-proyecto>
cd promo-video/<nombre-proyecto>
npm install && npm install lucide-react
```

**Resolución:** 1920x1080 (Full HD)

**Guías de tamaño:**
- Elementos deben ser grandes y confiados — sin items pequeños flotando
- Headlines: 60-90px mínimo. Subtexto: 32-44px
- Mockups de browser: 60-80% del ancho del frame
- Padding de bordes: 60-100px
- Si una escena se ve vacía, los elementos son demasiado pequeños

**Herramientas creativas:**
- `spring()` para movimiento natural
- `interpolate()` para control preciso de timing
- CSS 3D transforms para depth y mockups de dispositivos
- Box shadows y gradientes para profundidad
- SVG paths para animaciones de formas

**Preview:**
```bash
npx remotion studio
```

### Fase 4: Voiceover (Crítico)

El voiceover DEBE coincidir con los visuales:
1. Extraer timings de escenas de la composición
2. Escribir script que referencia lo que está en pantalla
3. Generar con ElevenLabs (`ELEVEN_LABS_API_KEY` requerida)
4. Verificar con Whisper - comprobar timestamps reales
5. **Corregir TODOS los overlaps inmediatamente**

```bash
python .agent/skills-custom/promo-video/scripts/generate_voiceover.py
```

### Fase 5: Música y Render Final

**Archivos de música** (royalty-free de Pixabay, incluidos en la skill):
```bash
# Copiar track seleccionado al proyecto
cp .agent/skills-custom/promo-video/music/inspired-ambient-141686.mp3 background-music.mp3
# O
cp .agent/skills-custom/promo-video/music/motivational-day-112790.mp3 background-music.mp3
# O
cp .agent/skills-custom/promo-video/music/the-upbeat-inspiring-corporate-142313.mp3 background-music.mp3
```

**Mezclar audio:**
```bash
ffmpeg -y -i voiceover-normalized.mp3 -i background-music.mp3 \
  -filter_complex "[1:a]volume=0.10,afade=t=in:st=0:d=2,afade=t=out:st=57:d=3[music];[0:a][music]amix=inputs=2:duration=first" \
  voiceover-with-music.mp3
```

**Render video:**
```bash
npx remotion render MainPromo out/promo-hq.mp4 --image-format png --crf 1
```

**Combinar video + audio:**
```bash
ffmpeg -y -i out/promo-hq.mp4 -i voiceover-with-music.mp3 \
  -c:v copy -map 0:v:0 -map 1:a:0 \
  out/promo-final.mp4
```

## DON'Ts

- **Sin efectos de jitter** — Sin sacudidas o vibración. Todo debe sentirse suave y controlado
- **Sin giro completo de escena** — La rotación 3D debe ser sutil y para elementos específicos (ej. browser mockup con leve perspectiva)
- **Sin 3D transforms en transiciones** — Usar solo 2D: opacidad, posición, escala y máscaras de gradiente

## Recursos Incluidos

- `scripts/generate_voiceover.py` — Generación de voiceover con verificación de timing (ElevenLabs + Whisper)
- `music/inspired-ambient-141686.mp3` — Ambiente inspirador
- `music/motivational-day-112790.mp3` — Motivacional, commercial
- `music/the-upbeat-inspiring-corporate-142313.mp3` — Corporativo energético
