---
name: canva
description: "Canva design platform — guía completa para crear diseños profesionales con Canva. Cubre Brand Kit, Magic Studio AI, templates, formatos de contenido, tipografía, color, diseño editorial y workflows de equipo. Usar cuando se necesite crear gráficas, presentaciones, social media, documentos o contenido visual sin código."
type: feature
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
version: 2.0.0
updated: 2026-02-28
---

# Canva — Guía de Diseño Completa

> **Nivel:** Desde básico hasta Power User
> **Enfoque:** Diseño práctico, Brand Kit, AI generativo y flujos de equipo

---

## 🧩 ¿Cuándo usar esta skill?

| Tarea | Usar Canva |
|-------|-----------|
| Social media posts (Instagram, LinkedIn, X) | ✅ |
| Presentaciones de negocio / pitch decks | ✅ |
| Logos, íconos, avatares | ✅ (Canva Pro) |
| Posters, flyers, banners | ✅ |
| Documentos / reports visuales | ✅ (Canva Docs) |
| Videos cortos y animaciones | ✅ |
| Mockups de UI/app (alta fidelidad) | ❌ → Usar Figma |
| Design systems con tokens | ❌ → Usar Figma |
| Prototipado interactivo | ❌ → Usar Figma |

---

## 🏗️ Arquitectura de Canva

```
Canva
├── Canva Design         → Editor de diseño principal
├── Canva Docs           → Documentos visuales colaborativos
├── Canva Presentations  → Slides con modo presentador
├── Canva Websites       → Publicación web simple
├── Canva Video          → Edición de video
├── Canva Print          → Pedidos de impresión
└── Magic Studio         → Suite de IA generativa
    ├── Magic Design     → Genera diseños desde prompt
    ├── Magic Write      → Genera texto con IA
    ├── Magic Media      → Imagen/video desde texto (Dream Lab)
    ├── Magic Expand     → Extiende imágenes (outpainting)
    ├── Magic Eraser     → Elimina objetos de fotos
    ├── Magic Grab       → Elimina fondos + reposiciona
    ├── Magic Morph      → Transforma formas con IA
    ├── Magic Switch     → Cambia formato/idioma del diseño
    ├── Magic Animate    → Animaciones automáticas
    └── Bulk Create      → Genera N variantes desde spreadsheet
```

---

## 🎨 Brand Kit (Identidad de Marca)

El Brand Kit centraliza la identidad visual y es **la primera cosa a configurar** en cualquier proyecto de marca.

### Configuración en Canva Pro/Teams

```
Brand Hub > + New brand kit
├── Brand Name
├── Logo (SVG preferido, también PNG con transparencia)
├── Colors → Añadir paleta HEX/RGB/OKLCH
│   ├── Primary: #principal
│   ├── Secondary: #secundario
│   └── Accent: #acento
├── Fonts
│   ├── Heading font + tamaño (ej. "Playfair Display, 48px")
│   ├── Sub-heading font (ej. "DM Sans, 24px")
│   └── Body font (ej. "Inter, 16px")
├── Graphics / Icons → SVGs de la marca
└── Photos → Galería de imágenes de marca
```

### Cómo aplicar Brand Kit en un diseño
1. En el editor → **Brand** tab en el panel izquierdo
2. Los colores/fuentes de marca aparecen como primera opción en cada selector
3. Los logos y gráficos se insertan drag-and-drop

### Reglas para Brand Kit efectivo
- Logo: siempre SVG o PNG de alta resolución con fondo transparente
- Definir mínimo 4 colores (primario, secundario, acento, neutro)
- Incluir versión clara Y oscura del logo
- Añadir **1 fuente máximo por role** (heading, body) para consistencia
- Usar **Brand Voice** (Canva AI) para que Magic Write escriba en el tono de la marca

---

## 📐 Sistema de Templates y Formatos

### Formatos sociales 2026 (píxeles)
| Plataforma | Formato | Dimensiones |
|-----------|---------|-------------|
| Instagram Post | Cuadrado | 1080×1080 |
| Instagram Post | Vertical | 1080×1350 |
| Instagram Story/Reels | Vertical | 1080×1920 |
| LinkedIn | Post cuadrado | 1200×1200 |
| LinkedIn | Banner | 1584×396 |
| X (Twitter) | Post | 1200×675 |
| YouTube | Thumbnail | 1280×720 |
| YouTube | Banner | 2560×1440 |
| TikTok | Video | 1080×1920 |
| Facebook | Post | 1200×630 |
| Pinterest | Pin | 1000×1500 |

### Formatos document/print
| Tipo | Dimensiones |
|------|------------|
| A4 | 210×297mm |
| US Letter | 215.9×279.4mm |
| Presentación | 1920×1080px (16:9) |
| Tarjeta personal | 91×55mm |
| Doble carta | 431.8×279.4mm |

### Custom sizes
`Crear diseño > Tamaño personalizado > [W x H px/mm/cm/in]`

---

## ✏️ Flujo de diseño profesional en Canva

### 1. Planificación (antes de abrir el editor)
- Definir el **objetivo** del diseño (vender, informar, entretener)
- Identificar **audiencia** → qué les resuena
- Elegir **jerarquía visual**: qué es lo primero que debe ver el ojo
- Recopilar assets: fotos, logos, iconos

### 2. Estructura base
1. Elegir template o empezar desde cero
2. Establecer **grid/líneas guía**: `View > Rulers & Guides` ó `Arrange > Add guides`
3. Definir zonas: headline, visual principal, CTA, espacio de respiración

### 3. Tipografía con intención
```
JERARQUÍA TÍPICA:
┌─────────────────────────────────┐
│ HEADLINE      → 60–80px, bold   │
│ Subheadline   → 24–36px, medium │
│ Body text     → 14–18px, regular│
│ Caption/Label → 10–12px, light  │
└─────────────────────────────────┘
```

**Reglas de tipografía Canva:**
- Máximo **2 fuentes** por diseño (display + body)
- Contraste de tamaño: el headline debe ser al menos **3x** el body
- Line height (interlineado): 1.4–1.6 para body, 1.1–1.2 para headlines
- Kerning (espacio entre letras) en uppercase: add +50–100 para legibilidad
- **NUNCA** usar más de 3 pesos de la misma fuente

**Pares de fuentes que funcionan:**
| Display | Body |
|---------|------|
| Playfair Display | DM Sans |
| Cormorant Garamond | Mulish |
| Space Grotesk | Inter |
| Clash Display | Plus Jakarta Sans |
| Neue Montreal | IBM Plex Sans |

### 4. Color y composición
**Regla 60-30-10:**
- 60% → Color dominante (fondo)
- 30% → Color secundario (áreas de soporte)
- 10% → Color acento (CTAs, highlights)

**Generadores de paletas integrados:**
- `Styles > Colors > + Add color` → importar desde URL/imagen (Magic Palette)
- Cambiar paleta total: `Styles > Color palettes` → clic en una → cambia todos los elementos de golpe

### 5. Imágenes y media
- **Canva Photos** (gratuitas y de pago): buscar en panel Media
- **Upload yours**: drag-and-drop o `Upload > Upload files`
- **Background Remover** (Pro): seleccionar imagen → `Edit image > BG Remover`
- **Ajustes de imagen**: brillo, contraste, saturación, blur, viñeta, duotono

**Trucos de imagen:**
- Para foto de fondo: colocar en la capa inferior + `Position > Background`
- Para foto dentro de un frame/shape: drag sobre la forma → encaja automáticamente
- Recortar: doble clic en imagen → crop handle

### 6. Elementos gráficos
- **Shapes** básicas: cuadrados, círculos, polígonos → personalizar borde/fill
- **Lines & arrows**: para diagramas y separadores
- **Grids**: para layouts estructurados (`Elements > Grids`)
- **Frames**: marcos elegantes para fotos
- **Charts**: gráficos estadísticos (`Elements > Charts` → importar datos)
- **Tables**: tablas editables (`Elements > Table`)
- **Icons**: millones via `Elements > Icons` (búsqueda en inglés da más resultados)

---

## 🤖 Magic Studio AI — Guía Completa

### Magic Design (prompt → diseño)
```
Inicio > Magic Design > [describir el diseño]
Ejemplo: "Slide profesional para presentar métricas de ventas Q1, 
          estilo corporativo azul, gráfico de barras central"
```
Genera 6 variantes → elegir la más cercana → editar

### Magic Write (IA de texto)
- Seleccionar cuadro de texto → doble clic → `Magic Write`
- Útil para: headlines, copy de marketing, bio, descripciones

### Dream Lab (imagen desde texto - imágenes artísticas)
```
Apps > Dream Lab
Prompt ejemplo: "Flat illustration de ciudad nocturna con luces de neón, 
                  estilo vectorial, colores purple y cyan"
Estilo: Real, Anime, Illustration, Photography, etc.
```

### Magic Media (imagen + video desde texto)
- `Elements > Generate image` → prompt visual
- Para video: apps de video → `Generate video`

### Magic Expand (outpainting)
1. Subir imagen → seleccionar
2. `Edit image > Magic Expand`
3. Elegir dirección de expansión o "Expand all"
4. La IA completa el espacio adicionalmente

### Bulk Create (N diseños desde tabla)
```
Apps > Bulk Create
1. Conectar Google Sheet O subir CSV
2. Mapear columnas → {{{nombre_columna}}} en elementos del diseño
3. Generate → crea N páginas/archivos automáticamente
```
Útil para: tarjetas de empleados, certificados, posts personalizados, etiquetas de producto

### Magic Animate
- Seleccionar elemento → `Animate` en toolbar superior
- **Rise, Pan, Pop**: para elementos individuales
- **Drift, Breathe, Flicker**: para objetos sutiles
- **Scroll animations** (en Canva Websites): efecto parallax y reveal al scroll

---

## 🖼️ Layouts y Composición Avanzada

### Sistema de capas (Layers)
```
Panel derecho > Position > Layers
O: clic derecho en canvas > "Layer" panel
```
- `Bring to front / Send to back` para apilar
- **Agrupar** (`Cmd/Ctrl+G`): para mover conjuntos de elementos
- **Lock**: clic derecho > Lock position → evita mover accidentalmente el fondo

### Grids y Alignment
- `View > Show rulers` + drag desde ruler para crear **guides** manuales
- `Arrange > Align & Distribute` para alinear múltiples selecciones:
  - Left/Center/Right/Top/Middle/Bottom
  - Distribute horizontally/vertically (espaciado igual)
- Canva tiene **smart guides** automáticos al arrastrar (líneas rosas/bles)

### Crear plantillas reutiizables
1. Diseñar el template
2. `File > Save as template` → asigna a Brand Kit o carpeta
3. Compartir con equipo: `Share > Share template link`

---

## 👥 Workflows de Equipo

### Comentarios y revisión
- `Share > Share link with edit/comment/view`
- Colocar comentario: clic en el símbolo de burbuja → clic en zona del canvas
- **Menciones**: `@nombre` en comentario → notifica al colaborador
- **Resolve**: marcar como resuelto cuando se implementa el cambio

### Presentaciones con Presenter Mode
1. `Present > Presenter view`
2. Panel de control con notas y siguiente slide
3. **Q&A mode**: permite que la audiencia envíe preguntas en tiempo real
4. **Timer**: modo presentador incluye cronómetro

### Canva Docs
Documentos híbridos código-diseño para equipos:
- Insertar diseños de Canva dentro del doc
- Tablas, imágenes, embeds de video
- Toggle sections, checklists
- Compartir como web page

### Exportación profesional
| Formato | Cuándo |
|---------|--------|
| PNG alta resolución (300dpi) | Print, logos |
| PDF Print (CMYK) | Impresión profesional |
| PDF Web | Digital, presentaciones |
| SVG | Logos vectoriales (Pro) |
| MP4 | Videos, animaciones |
| GIF | Animaciones web |
| PPTX | Exportar a PowerPoint |

**Exportar alta calidad:**
`Share > Download > PDF Print > Crop marks & bleed ✓ > Color profile: CMYK`

---

## 🎯 Checklist de Diseño Profesional en Canva

Antes de publicar/exportar verificar:

**Visual:**
- [ ] Jerarquía clara (headline domina, body secundario)
- [ ] Máximo 2 fuentes, colores coherentes con Brand Kit
- [ ] Contraste WCAG AA (4.5:1 texto sobre fondo)
- [ ] Sin elementos cortados en los bordes (respetar área segura)
- [ ] Imágenes en alta resolución (no pixeladas)

**Contenido:**
- [ ] Mensaje principal legible en 3 segundos
- [ ] CTA visible y claro si aplica
- [ ] Texto libre de errores ortográficos (revisar con `T > Spell check`)
- [ ] Logos en versión correcta para el fondo (claro/oscuro)

**Técnico:**
- [ ] Formato correcto para el canal destino
- [ ] Resolución correcta (72dpi web, 300dpi print)
- [ ] Fuentes disponibles (Pro o subidas como custom font)

---

## 🔌 Integraciones Clave

| App | Para qué |
|-----|---------|
| Google Drive | Importar/exportar directo |
| Slack | Compartir diseños sin salir de Slack |
| Hubspot | Crear assets de marketing |
| Mailchimp | Templates de email |
| Hootsuite/Buffer | Programar posts desde Canva |
| Shopify | Assets de producto |
| Dropbox | Subir/bajar archivos |
| Giphy | Insertar GIFs animados |
| QR Code | Generar QR dentro del diseño |
| Pexels/Pixabay | Fotos gratuitas adicionales |

---

## 💡 Tips Pro y Atajos

### Atajos de teclado esenciales
| Atajo | Acción |
|-------|--------|
| `Ctrl/Cmd + C/V` | Copiar/pegar |
| `Ctrl/Cmd + D` | Duplicar |
| `Ctrl/Cmd + G` | Agrupar |
| `Ctrl/Cmd + Shift + G` | Desagrupar |
| `Ctrl/Cmd + A` | Seleccionar todo |
| `Ctrl/Cmd + Z` | Deshacer |
| `Ctrl/Cmd + Shift + [/]` | Traer al frente / mandar atrás |
| `Alt + drag` | Duplicar elemento arrastrando |
| `Ctrl/Cmd + Enter` | Editar texto |
| `R` | Insertar rectángulo |
| `C` | Insertar círculo |
| `L` | Insertar línea |
| `T` | Insertar texto |
| `Espacio + drag` | Pan (moverse por el canvas) |
| `Ctrl/Cmd + scroll` | Zoom in/out |
| `Shift + drag` | Mantener proporciones al resize |
| `Ctrl/Cmd + K` | Buscar en Canva (comando universal) |

### Trucos poco conocidos
1. **Color dropper**: clic en picker de color → ícono cuentagotas → clic en cualquier parte de la pantalla
2. **Reemplazar fuente global**: Seleccionar todo un texto → cambiar fuente → aplica a todo
3. **Copiar estilos**: Clic derecho en elemento → "Copy style" → pegar en otro
4. **Transparencia con clic**: Seleccionar → escribir un número `0`-`9` para cambiar opacity (0=10%, 9=90%, 0+0=0%)
5. **Resize desde centro**: `Alt + drag` en handle redimensiona desde el centro
6. **Template sugeridos por IA**: `Home > Magic Design` → sube tu logo y Canva genera templates on-brand
7. **Smart mockups**: Elementos > Mockups → coloca tu diseño en iPhone, laptop, cartel

---

## 🔄 Canva vs Figma — Cuándo Usar Cada Uno

| Escenario | Canva | Figma |
|-----------|-------|-------|
| Post de Instagram en 5 min | ✅ | ❌ Overkill |
| Presentación de ventas | ✅ | Posible |
| UI de app móvil | ❌ | ✅ |
| Design system escalable | ❌ | ✅ |
| Prototipado interactivo complejo | ❌ | ✅ |
| Certificados en bulk (500 piezas) | ✅ (Bulk Create) | ❌ |
| Logo + branding inicial | ✅ (básico) | ✅ (avanzado) |
| Mockup de producto | ✅ (Smart Mockups) | ✅ |
| Video/animación social | ✅ | ❌ |
| Infografía | ✅ | Posible |
| Developer handoff CSS | ❌ | ✅ (Dev Mode) |

---

## Anti-patrones Comunes

1. **Demasiadas fuentes**: Nunca más de 2. Canva lo hace fácil de hacer mal.
2. **Fondo blanco puro + texto negro puro**: Demasiado contraste. Usar `#1a1a1a` sobre `#f5f5f5`.
3. **Stretching de logos**: Siempre usar `Shift + drag` para mantener proporciones.
4. **Baja resolución para print**: Siempre exportar PDF Print para impresiones físicas.
5. **Texto sobre foto sin tratamiento**: Añadir overlay semitransparente o blur detrás del texto.
6. **Ignorar área segura**: Los elementos importantes deben estar a ≥5mm del borde.
7. **Templates sin personalizar**: Los templates de Canva los usa todo el mundo. Personalizar siempre: colores, fuentes, imágenes.
