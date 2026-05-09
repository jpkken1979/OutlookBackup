---
name: figma-design
description: "```"
type: feature
---

---
name: figma-design
description: "Figma como herramienta de diseño — guía avanzada de design systems, componentes, variables, Auto Layout, prototipado, developer handoff y workflows de equipo. Usar cuando se diseñen interfaces, UIs, flujos de producto, design tokens o sistemas de componentes. NO confundir con la skill 'figma' que es solo el MCP server para design-to-code."
type: feature
allowed-tools: Read, Write, Edit, Glob, Grep
version: 2.0.0
updated: 2026-02-28
---

# Figma — Guía Completa de Diseño

> **Versión:** Figma 2025/2026 (incluye Variables, Dev Mode, Figma Make, Figma AI)
> **Nivel:** Intermedio → Avanzado

---

## 🗺️ Ecosistema Figma 2026

```
Figma
├── Figma Design     → Editor principal UI/UX
├── FigJam           → Whiteboard colaborativo
├── Figma Slides     → Presentaciones
├── Figma Sites      → Publicar diseños como webs (Beta)
├── Figma Draw       → Ilustración vectorial (Nuevo)
├── Figma Buzz       → Gestión de brand assets (Beta)
├── Figma Make       → AI que convierte wireframes en apps (Nuevo)
└── Dev Mode         → Handoff para desarrolladores
```

---

## 🏗️ Fundamentos de Arquitectura en Figma

### Jerarquía de archivos
```
Organization
└── Team
    └── Project
        └── File (.fig)
            ├── Page 1: Design (pantallas activas)
            ├── Page 2: Components (librería local)
            ├── Page 3: Archive (versiones anteriores)
            └── Page 4: Research (user flows, wireframes)
```

### Buenas prácticas de nomenclatura
```
Componentes:  Icon/Arrow/Right
              Button/Primary/Default
              Card/Product/Hover
              
Frames:       [Screen] Home – Logged In
              [Screen] Profile – Edit Mode
              
Variables:    color/brand/primary
              spacing/base/4
              typography/heading/size
              
Layers:       ❌  Rectangle 47, Group 23
              ✅  Hero Image, Nav Container
```

---

## ⚙️ Variables — Design Tokens en Figma

Variables (2024+) son el sistema de design tokens nativo de Figma. Reemplazan a los estilos para colores, espaciado, tipografía y radios.

### Tipos de variables
| Tipo | Para qué | Ejemplo |
|------|---------|---------|
| Color | Paletas, temas | `color/brand/primary = #7C3AED` |
| Number | Espaciado, tamaño, radio | `spacing/4 = 16` |
| String | Texto parametrizable | `copy/cta/default = "Get started"` |
| Boolean | Toggle de features | `feature/dark-mode = true` |

### Crear variables de color
```
Assets panel > Local variables > + New variable > Color
─ Collection name: "Color System"
  ├── brand/primary:   #7C3AED
  ├── brand/secondary: #06B6D4
  ├── neutral/900:     #0F172A
  ├── neutral/500:     #64748B
  ├── neutral/100:     #F1F5F9
  └── semantic/error:  #EF4444
```

### Multi-mode (Light/Dark con variables)
```
Collection: "Color System"
Modes: Light | Dark
─ bg/surface:       Light=#FFFFFF  Dark=#0F172A
─ bg/elevated:      Light=#F8FAFC  Dark=#1E293B
─ text/primary:     Light=#0F172A  Dark=#F8FAFC
─ text/secondary:   Light=#64748B  Dark=#94A3B8
─ border/default:   Light=#E2E8F0  Dark=#334155
```

**Aplicar modo:**
- En un frame → `Design panel > Variables > Mode selector`
- Para preview dark: seleccionar frame → cambiar modo → ver resultado instantáneo

### Token naming convention (W3C Design Tokens)
```
{category}/{subcategory}/{variant}/{state}

color/feedback/error/default
color/feedback/error/hover
spacing/component/button/padding-x
radius/component/card/default
```

---

## 📦 Components — Sistema de Componentes

### Anatomía de un componente
```
Main Component (⬥ diamante morado)
└── Instance (◇ diamante vacío, hereda todo)
```

### Component Properties (2023+)
Permiten exponer controles del componente directamente en el panel de diseño:

| Property Type | Para qué | Ejemplo |
|--------------|---------|---------|
| **Variant** | Estados del componente | `State: Default | Hover | Active | Disabled` |
| **Boolean** | Mostrar/ocultar capas | `Show Icon: true/false` |
| **Instance swap** | Cambiar un sub-componente | `Icon: [cualquier ícono]` |
| **Text** | Editar texto directamente | `Label: "Submit"` |

### Estructura recomendada de componentes (Atomic Design)

```
/Components
  /Atoms
    Button/           → Button/Primary/Default, Hover, Active, Disabled
    Input/            → Input/Text/Default, Focus, Error, Disabled
    Icon/             → Icon/**/ (todos los íconos como variantes)
    Badge/            → Badge/Status/Online, Offline, Away
    
  /Molecules
    Card/             → Card/Product, Card/User, Card/Metric
    NavItem/          → NavItem/Desktop/Active, NavItem/Mobile
    FormField/        → FormField/Default, Error, Success
    
  /Organisms
    Navbar/           → Navbar/Desktop, Navbar/Mobile
    Sidebar/          → Sidebar/Expanded, Collapsed
    Modal/            → Modal/Confirm, Modal/Form
    
  /Templates
    DashboardLayout/
    AuthLayout/
    LandingLayout/
```

### Variantes — Cómo estructurarlas
```
Component Set (grupo de variantes):
  Properties:
    Type: Primary | Secondary | Ghost | Destructive
    Size: Small | Medium | Large
    State: Default | Hover | Active | Disabled | Loading
    
Naming en frames internos (Figma auto-detecta):
  "Type=Primary, Size=Medium, State=Default"
  "Type=Primary, Size=Medium, State=Hover"
```

**Truco:** Con 3 propiedades de 4 valores cada una = 64 variantes automáticas. Siempre partir de la variante más simple y duplicar.

---

## 📏 Auto Layout — El Motor de Layouts

Auto Layout es el feature más importante de Figma para crear UIs que escalen.

### Conceptos clave
```
Frame con Auto Layout = flex container en CSS

Direction:
  Horizontal → flex-direction: row
  Vertical   → flex-direction: column

Spacing:
  Gap         → gap
  Padding     → padding (individual por lado)

Sizing:
  Fixed       → width: 200px
  Hug         → width: fit-content
  Fill        → width: 100% (flex-grow: 1)

Alignment:
  Start | Center | End | Space between
  (= justify-content en el eje principal)
```

### Patrones comunes
```tsx
// BOTÓN con Auto Layout:
Frame (Auto Layout, Horizontal, 16px gap)
├── padding: 12 16
├── min-width: 120
├── Hug width
└── Children:
    ├── Icon (16×16, Fixed)
    └── Label ("Submit", Fill, center)

// CARD con Auto Layout:
Frame (Auto Layout, Vertical, 0 gap)
├── width: 320, height: Hug
└── Children:
    ├── Image (320×200, Fixed)
    └── Content (Vertical, 16 padding, 12 gap)
        ├── Title (text, Fill)
        ├── Description (text, Fill)
        └── Button (component instance)

// NAV BAR con Auto Layout:
Frame (Auto Layout, Horizontal, Space between)
├── padding: 0 24
├── height: 64, width: Fill
└── Children:
    ├── Logo (100×32)
    └── NavLinks (Auto Layout, Horizontal, 32 gap)
```

### Absolute Position dentro de Auto Layout
- Seleccionar capa dentro de frame AL → `Design > Layout > Absolute position`
- La capa queda flotante (como `position: absolute` en CSS) y no afecta el layout

### Responsive con Constraints + Auto Layout
```
Frame "Screen" (1440px)
└── Container (Auto Layout, min-width: 320, max-width: 1200, centered)
    └── Grid (Auto Layout, Wrap, gap: 24)
        └── Card (Fill width, min-width: 280)
```

---

## 🔄 Prototyping Avanzado

### Tipos de interacciones
| Trigger | Para qué |
|---------|---------|
| On click | Navegación, popups |
| On hover | Tooltips, hover states |
| On drag | Carruseles, sliders |
| After delay | Animaciones automáticas, loaders |
| Key/gamepad | Demos con teclado |
| Mouse down/up | Botones con presión |

### Animaciones disponibles
| Tipo | Comportamiento |
|------|---------------|
| Instant | Sin animación |
| Dissolve | Fade in/out |
| Move in/out | Slide desde dirección |
| Slide in/out | Slide con overlap |
| Push | La pantalla "empuja" a la siguiente |
| Smart animate | **Anima automáticamente** elementos con el mismo nombre entre frames |

### Smart Animate — el poder real
```
Frame A:                Frame B:
└── Button (Position: x=100, y=200)  └── Button (Position: x=400, y=100)

Si Button tiene el mismo nombre en A y B:
Smart animate lo mueve suavemente de (100,200) a (400,100)
+ Anima: position, size, rotation, opacity, fill, border-radius
```

**Truco para microinteracciones:**
1. Crear frame "Estado Normal"
2. Duplicar → "Estado Hover"
3. Modificar lo que cambia (escala, sombra, color)
4. Conectar: On hover → Hover frame → Smart animate (200ms, Ease Out)

### Scroll y Fixed elements
- Frame con `Clip content: ON` + `Overflow: Scrollable (Vertical/Horizontal)`
- Elementos con `Fixed position when scrolling` = header/footer sticky
- Para prototipos tipo app: usar `Prototype > Scroll behavior`

---

## 🎨 Design Tokens & Developer Handoff

### Dev Mode
Dev Mode convierte Figma en documentación de código para desarrolladores.

**Activar:** Toggle `Dev Mode` en toolbar (o `Shift + D`)

**Qué ven los devs:**
- Propiedades CSS de cualquier elemento
- Espaciado exacto entre elementos
- Variables → CSS custom properties
- Assets exportables
- Código React/CSS/Swift/Kotlin (integración con plugins)

### Plugin: Figma Tokens (Style Dictionary)
Para exportar variables a código:
```json
// Output: tokens.json (Style Dictionary format)
{
  "color": {
    "brand": {
      "primary": { "$value": "#7C3AED", "$type": "color" }
    }
  },
  "spacing": {
    "4":  { "$value": "16px", "$type": "dimension" },
    "8":  { "$value": "32px", "$type": "dimension" }
  }
}
```

### Convenciones de handoff
```
Preparar antes de handoff:
✅ Todos los colores usan Variables (no valores inline)
✅ Textos usan Text Styles
✅ Íconos/imágenes marcados como exportables
✅ Frames de pantallas nombrados descriptivamente
✅ Anotaciones con Figma Annotations tool
✅ Documentar estados: Default, Hover, Active, Error, Empty, Loading
✅ Especificar breakpoints: Mobile(375), Tablet(768), Desktop(1440)
```

---

## 🤖 Figma AI (2025/2026)

### Figma Make
Convierte wireframes o diseños en código front-end funcional:
1. Diseñar wireframe/mockup en Figma
2. `Make AI` en toolbar → seleccionar parte del diseño
3. Genera: HTML/CSS, React, o prototipo interactivo
4. Editar con prompts de lenguaje natural: "Añade un botón de cierre en la esquina superior derecha"

### Otras herramientas AI en Figma
| Feature | Qué hace |
|---------|---------|
| `Generate via AI` | Genera UI desde descripción de texto |
| `Rename layers` (AI) | Renombra todas las capas descriptivamente |
| `Fill with AI image` | Rellena un frame con imagen generada |
| `Generate copy` | Genera placeholder text realista (no Lorem Ipsum) |
| AI Search | Busca en toda la org por concepto ("cards con sombra azul") |

---

## 📊 Figma para Design Systems

### Estructura de una librería de DS

```
Design System File
├── 📄 Page: Foundations
│   ├── Color palette + Variables
│   ├── Typography scale
│   ├── Spacing grid
│   ├── Shadow styles
│   └── Motion tokens
│
├── 📄 Page: Components
│   ├── Atoms (Button, Input, Icon, Badge...)
│   ├── Molecules (Card, NavItem, FormField...)
│   └── Organisms (Navbar, Sidebar, Modal...)
│
├── 📄 Page: Patterns
│   ├── Form layouts
│   ├── Data tables
│   └── Navigation patterns
│
└── 📄 Page: Documentation
    ├── Usage guidelines
    ├── Dos and Don'ts
    └── Changelog
```

### Publicar librería
```
Assets panel (Cmd/Ctrl+Alt+O) >
  Local components > ... > Publish >
  Describir cambios > Publish
```

### Versioning con Branches
```
File menu > Create branch > "feat/new-button-design"
─ Trabajar en la branch sin afectar main
─ Comparar diferencias: View > Compare changes
─ Merge cuando esté aprobado: Branch > Merge into main
```

---

## ⌨️ Atajos Esenciales

| Atajo | Acción |
|-------|--------|
| `F` o `A` | Nuevo frame/artboard |
| `R` | Rectángulo |
| `E` | Elipse |
| `T` | Texto |
| `P` | Pluma (vector paths) |
| `I` | Cuentagotas de color |
| `K` | Escalar manteniendo proporciones |
| `H` | Herramienta de mano (pan) |
| `V` | Herramienta de selección |
| `Cmd/Ctrl + G` | Agrupar |
| `Cmd/Ctrl + Alt + G` | Agrupar en Frame |
| `Cmd/Ctrl + Shift + G` | Desagrupar |
| `Cmd/Ctrl + D` | Duplicar |
| `Alt + drag` | Duplicar con drag |
| `Cmd/Ctrl + L` | Colapsar capas |
| `Cmd/Ctrl + \` | Ocultar/mostrar paneles |
| `Shift + D` | Alternar Dev Mode |
| `Cmd/Ctrl + Shift + H` | Alinear horizontal center |
| `Cmd/Ctrl + Shift + V` | Alinear vertical center |
| `Cmd/Ctrl + Shift + E` | Exportar selección |
| `Cmd/Ctrl + Alt + K` | Master component |
| `Cmd/Ctrl + Enter` | Entrar dentro de frame/grupo |
| `Esc` | Salir de frame/grupo |
| `Cmd/Ctrl + P` | Búsqueda de comandos (quick actions) |
| `Cmd/Ctrl + /` | Quick actions (igual que P) |
| `0-9` | Cambiar opacidad (1=10%, 0=100%) |
| `Shift + 0-9` | Zoom predefinido |

---

## 🔌 Plugins Recomendados

| Plugin | Para qué |
|--------|---------|
| **Figma Tokens** | Exportar variables/tokens a JSON (Style Dictionary) |
| **Iconify** | 200k+ íconos de todas las librerías |
| **Unsplash** | Insertar fotos de alta calidad |
| **Content Reel** | Datos reales (nombres, emails, avatares) en lugar de lorem ipsum |
| **Contrast** | Verificar ratio WCAG directamente en Figma |
| **A11y Annotation Kit** | Añadir anotaciones de accesibilidad |
| **Figma to Code** | Exportar React/Flutter/HTML |
| **FramerX** | Preview animaciones en Framer |
| **Noise & Texture** | Añadir texturas y granos |
| **Blobs** | Generador de formas orgánicas |
| **Chart** | Gráficos con datos reales |
| **Autoflow** | Diagramas de flujo automáticos |
| **Storyset** | Ilustraciones animables |
| **Pitch** | Exportar a presentaciones Pitch |

---

## ✅ Checklist Design System en Figma

### Foundations
- [ ] Variables de color con multi-mode (Light/Dark)
- [ ] Variables de spacing (4, 8, 12, 16, 24, 32, 48, 64, 96)
- [ ] Variables de typography (font-size, line-height, letter-spacing)
- [ ] Variables de border-radius (sm=4, md=8, lg=12, full=9999)
- [ ] Variables de shadows (sm, md, lg)
- [ ] Text Styles usando variables (no valores hardcodeados)

### Componentes
- [ ] Cada componente tiene variantes para todos sus estados
- [ ] Usar Component Properties (no capas duplicadas)
- [ ] Auto Layout en todos los componentes (no posicionamiento absoluto)
- [ ] Layers nombrados descriptivamente
- [ ] Assets exportables marcados (íconos, logos)
- [ ] Documentación embebida con Figma Annotations

### Handoff
- [ ] Dev Mode activado en archivo de producción
- [ ] Variables vinculadas a todos los valores de color/spacing
- [ ] Pantallas organizadas por sección/flow
- [ ] Redlines automáticas visibles en Dev Mode
- [ ] README en la primera página del archivo

---

## 🔄 Figma vs Canva — Diferencias Clave

| Aspecto | Figma | Canva |
|---------|-------|-------|
| Target | Diseñadores/devs | Todo el mundo |
| Curva aprendizaje | Alta | Baja |
| Design systems | ✅ Completo | ❌ Limitado |
| Prototipado | ✅ Avanzado | ❌ Básico |
| Colaboración | ✅ Multiplayer real | ✅ Bueno |
| Dev handoff | ✅ Dev Mode | ❌ No |
| Templates | Pocos, técnicos | Miles, marketing |
| Printing/marketing | ❌ Limitado | ✅ Excelente |
| Video/animación | ❌ Limitado | ✅ Fuerte |
| AI generativa | Figma Make (código) | Magic Studio (visual) |
| Precio | Desde $15/editor/mes | Desde gratis ($15 Pro) |
