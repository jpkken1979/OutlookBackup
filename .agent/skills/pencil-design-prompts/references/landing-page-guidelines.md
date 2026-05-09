# Landing Page Design Guidelines (High Conversion + High Craft)

> Guia completa para disenar landing pages que conviertan usando Pencil.dev

---

## Filosofia Central

**Las personas no compran productos. Compran una mejor version de si mismas.**

Cada elemento de la pagina debe responder la pregunta del visitante: "A donde me llevaras? En quien me convertire?" Muestra la transformacion, no solo la herramienta.

---

## Estructura SaaS / Startup Landing Page

1. **Header** — Logo, navegacion, login, CTA principal
2. **Hero Section** — Badge, headline, subheadline, CTAs, visual del producto, logos de confianza
3. **Problem/Solution** — Como funciona con step cards
4. **Core Features** — 3 features principales con screenshots
5. **Secondary Features Grid** — Grid de cards con iconos
6. **Social Proof** — Stats, testimonios, metricas
7. **Pricing** — Tiers con feature lists y CTAs
8. **FAQ** — Preguntas frecuentes
9. **Final CTA** — Headline, subheadline, CTA, linea de confianza
10. **Footer** — Logo, navegacion, copyright

---

## Proceso Obligatorio

### 1. Brief & Requirements Check (OBLIGATORIO)

Antes de disenar, verificar:
- **Producto**: Que es, que problema resuelve, categoria
- **Audiencia**: Para quien es, que roles importan
- **Objetivo**: Conversion principal (signup, demo, waitlist)
- **Propuesta de valor**: Que lo diferencia, top 3-5 beneficios
- **Tono**: Personalidad (friendly, professional, luxury)
- **Restricciones**: Secciones obligatorias/prohibidas
- **Assets**: Colores, UI, screenshots existentes

### 2. Conceptos a Comunicar

Identificar:
- **Conceptos de dominio**: En que espacio estamos
- **Conceptos cualitativos**: Como debe sentirse

Mapear cada concepto a decisiones de diseno.

### 3. Transformation Mapping (OBLIGATORIO)

Definir el arco emocional:

| Estado | Pregunta |
|--------|----------|
| **Before** | Que dolor/frustracion siente el visitante ahora? |
| **After** | Como se ve la vida despues de usar el producto? |
| **Bridge** | Como el producto los lleva de Before a After? |
| **Feeling** | Que emocion dominante debe evocar la pagina? |

---

## Guias de Contenido

### Jerarquia de Headlines (mas fuerte a mas debil)

| Tipo | Ejemplo | Impacto |
|------|---------|---------|
| **Transformacion** | "Finalmente siente control de tu inbox" | Alto |
| **Outcome** | "Publica mas contenido, crece tu audiencia" | Alto |
| **Beneficio** | "Escribe 10x mas rapido" | Medio |
| **Feature** | "Asistente de escritura con IA" | Bajo |

Lidera con transformacion u outcome.

### Principios de Copy

- Oraciones cortas y directas
- Escribir con confianza
- Hablar a tu audiencia
- Beneficios + features juntos
- Evitar fluff y jerga
- Cada seccion necesita headline + linea de soporte

---

## Guias Visuales

### Direccion Estetica (OBLIGATORIO)

Elegir direccion clara:
- Brutalmente minimal
- Maximalist chaos
- Retro-futuristic
- Organic/natural
- Luxury/refined
- Playful/toy-like
- Editorial/magazine
- Brutalist/raw
- Art deco/geometric

### Jerarquia de Imagenes (priorizar en orden)

| Tipo | Descripcion | Impacto |
|------|-------------|---------|
| **Transformacion** | Personas en el estado "after" | Mas alto |
| **Uso contextual** | Personas usando el producto | Alto |
| **Producto en ambiente** | Producto en setting que implica uso | Medio |
| **Producto aislado** | Producto solo | Bajo |

### Prompts para Imagenes

**Debil**: "Una laptop en un escritorio"
**Mejor**: "Una persona escribiendo en una laptop"
**Optimo**: "Una persona reclinada de su laptop, ojos cerrados, sonrisa leve, momento de satisfaccion"

---

## Hero Section

El hero comprime todo el producto en una pantalla.

### Elementos
- **Headline**: Promesa principal u outcome
- **Subheadline**: Que hace el producto realmente
- **CTA**: Una accion primaria + opcional secundaria
- **Visual**: Screenshot o imagen (50%+ visible above fold)

### Reglas
- Una idea clara, sin feature lists
- Layout preferido: vertical (headline, subheadline, CTAs)
- Debe funcionar sin visuales
- NO usar imagenes AI como background con texto encima

### Ejemplo batch_design
```javascript
hero=I("pageId", {type: "frame", name: "Hero", layout: "vertical", width: "fill_container", height:"fit_content(400)", padding: [80, 120], gap: 32})
heroHeadline=I(hero, {type: "text", content: "Transform Your Workflow", fontSize: 64, fontWeight: "bold", textColor: "#FFFFFF"})
heroSubline=I(hero, {type: "text", content: "The all-in-one platform that helps teams ship faster", fontSize: 24, textColor: "#A0A0A0"})
ctaButton=I(hero, {type: "frame", layout: "horizontal", padding: [16, 32], cornerRadius: 8, fill: "#6366F1"})
ctaText=I(ctaButton, {type: "text", content: "Get Started Free", fontSize: 18, fontWeight: "semibold", textColor: "#FFFFFF"})
```

---

## Footer Section

### Estructura Core
- Logo/nombre de empresa
- Grupos de links (Product, Company, Resources, Legal)
- Info legal/meta

### Visual Expression
Incluir un momento visual bold:
- Elemento grafico abstracto
- Tratamiento de background expresivo
- Composicion de layout inesperada

---

## Product Screenshots

Crear placeholders para screenshots:
- Aspect ratio: 1:1 o 16:9
- Fill o border sutil
- Texto "Screenshot placeholder" centrado
- **NO dibujar UI dentro de placeholders**

---

## Evitar "AI Slop" (OBLIGATORIO)

NO caer en esteticas genericas de IA:

| Evitar | Hacer |
|--------|-------|
| Typefaces genericas | Fonts distintivas y con caracter |
| Backgrounds planos | Atmosfera con gradients, patterns, texturas |
| Layouts predecibles | Composiciones inesperadas |
| Card patterns repetitivos | Variacion en estructura |
| Animaciones dispersas | Motion deliberado y bien ejecutado |

---

## Ritmo Visual

- No apilar muchas secciones de solo texto
- Alternar entre secciones text-heavy y visuales
- Las secciones visuales deben clarificar, no decorar
- Mantener momentum y prevenir scroll fatigue

---

## Checklist Final

- [ ] Hero claro y premium
- [ ] Identidad cohesiva
- [ ] Color disciplinado
- [ ] Spacing consistente
- [ ] Tipografia limpia
- [ ] Info compleja estructurada
- [ ] Elementos de trust intencionales
- [ ] Motion sutil
- [ ] Fotos generadas correctamente
- [ ] Pagina se siente moderna y product-first

---

*Fuente: Pencil.dev Landing Page Guidelines*
*Actualizado: 2026-02-02*
