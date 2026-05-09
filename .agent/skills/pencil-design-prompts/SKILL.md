---
name: pencil-design-prompts
description: "Colección de prompts efectivos para diseño UI/UX con Pencil.dev. Incluye prompts para apps web, móviles, landing pages, iteración de diseños, componentes, y workflow de 5 pasos (get_editor_state, get_guidelines, batch_get, batch_design, get_screenshot). Triggers: pencil.dev, UI design, UX prompts, wireframe, mockup, design prompts."
type: feature
---

# Pencil Design Prompts

> Coleccion de prompts efectivos para diseno UI/UX con Pencil.dev

## Referencias Detalladas

- [Design System Guidelines](references/design-system-guidelines.md) - Guias para apps y dashboards
- [Landing Page Guidelines](references/landing-page-guidelines.md) - Guias para landing pages de alta conversion

## Prompts para Crear Disenos

### Apps Web
```
"Design a web app for [DOMINIO]. Use a [ESTILO] style."
```
Ejemplos:
- "Design a web app for managing rocket launches. Use a technical style."
- "Design a web app for task management. Use a minimal clean style."
- "Design a web app for inventory tracking. Use a corporate professional style."

### Apps Moviles
```
"Design a mobile app for [FUNCION]. Use a [ESTILO] style."
```
Ejemplos:
- "Design a mobile app for tracking music royalties. Use a Scandinavian minimalistic style."
- "Design a mobile app for fitness tracking. Use a bold energetic style."

### Landing Pages
```
"Design a landing page for [PRODUCTO/SERVICIO]. Focus on [OBJETIVO]."
```
Ejemplos:
- "Design a landing page for a SaaS product. Focus on conversion."
- "Design a landing page for a cafe in Tokyo. Focus on atmosphere."

## Prompts para Iterar Disenos

### Explorar Direcciones
```
"Explore a totally different design direction."
"Explore a different layout, but keep the current design direction."
```

### Extender Paginas
```
"Use the selected design as the base design. Design a new page: [NOMBRE]."
```

### Cambiar Tema
```
"Convert this design to dark mode."
"Convert this design to light mode."
"Apply a warmer color palette."
```

### Refinar Tipografia
```
"Use bolder headlines with Swiss design principles."
"Change to a more elegant/classy font selection."
"Improve text hierarchy with better sizing."
```

### Mejorar Layout
```
"Add side navigation to this design."
"Make this design simpler and cleaner."
"Improve spacing and alignment."
```

## Prompts para Componentes

### Dashboard
```
"Create a dashboard with:
- Sidebar navigation (240px width)
- Stats cards row (3 cards)
- Main content area with data table
- Header with user menu"
```

### Formularios
```
"Create a form with:
- Input fields with labels
- Validation states
- Submit button
- Consistent spacing"
```

### Cards
```
"Create a card component with:
- Image area
- Title and description
- Action buttons
- Hover state"
```

## Flujo de Trabajo Recomendado

1. **Iniciar** - Obtener estado del editor
   ```
   get_editor_state(include_schema: true)
   ```

2. **Obtener Guias** - Segun el tipo de proyecto
   ```
   get_guidelines(topic: "design-system")  # Para apps
   get_guidelines(topic: "landing-page")   # Para webs
   get_guidelines(topic: "tailwind")       # Para codigo
   ```

3. **Leer Componentes** - Del design system
   ```
   batch_get(patterns: [{reusable: true}], readDepth: 2)
   ```

4. **Disenar** - Crear elementos
   ```
   batch_design(operations: "...")
   ```

5. **Verificar** - Screenshot del resultado
   ```
   get_screenshot(nodeId: "...")
   ```

## Operaciones batch_design

### Insert (I) - Insertar nuevo nodo
```javascript
sidebar=I("parentId", {type: "frame", layout: "vertical", width: 240})
```

### Copy (C) - Copiar nodo existente
```javascript
newCard=C("cardId", "parentId", {positionDirection: "right"})
```

### Update (U) - Actualizar propiedades
```javascript
U("nodeId", {content: "New text", fill: "#FF0000"})
```

### Replace (R) - Reemplazar nodo
```javascript
newNode=R("oldNodeId", {type: "text", content: "Replaced"})
```

### Delete (D) - Eliminar nodo
```javascript
D("nodeId")
```

### Generate Image (G) - Imagen AI o stock
```javascript
G("frameId", "stock", "modern office workspace")
G("frameId", "ai", "minimalist logo flat design")
```

## Tips

1. **Maximo 25 operaciones** por llamada batch_design
2. **Usar bindings** para referenciar nodos creados
3. **Verificar con screenshots** despues de cambios grandes
4. **No reusar nombres de binding** entre operaciones
5. **Dividir por secciones** para disenos grandes

---
*Skill creada: 2026-02-02*
*Fuente: https://www.pencil.dev/prompts*
