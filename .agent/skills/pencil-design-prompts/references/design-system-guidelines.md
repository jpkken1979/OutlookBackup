# Pencil Design System Guidelines

> Guias completas para componer pantallas y dashboards usando componentes de design system en archivos `.pen`

---

## 1. Patrones de Componentes Comunes

| Patron | Uso |
|--------|-----|
| `Button/*` | Variantes de botones |
| `Input/*` o `Input Group/*` | Inputs de formulario |
| `Card` | Contenedores de tarjetas |
| `Sidebar` | Navegacion lateral |
| `Table` o `Data Table` | Elementos de tabla |
| `Alert/*` | Alertas de feedback |
| `Modal/*` o `Dialog` | Dialogos modales |

---

## 2. Trabajando con Slots

Los slots son frames placeholder dentro de componentes donde insertas componentes hijos.

### Identificar Slots
```json
{
  "id": "slotId",
  "name": "Content Slot",
  "slot": ["recommendedComponentId1", "recommendedComponentId2"]
}
```

### Usar Slots
```javascript
sidebar=I(page, {type: "ref", ref: "sidebarId", height: "fill_container"})
item1=I(sidebar+"/contentSlotId", {type: "ref", ref: "sidebarItemId"})
item2=I(sidebar+"/contentSlotId", {type: "ref", ref: "sidebarItemId"})
```

Para ocultar un slot: `enabled: false`

---

## 3. Iconos

### Familias Disponibles

| Font Family | Estilo | Ejemplos |
|-------------|--------|----------|
| `lucide` | Outline, rounded | `home`, `settings`, `user`, `search` |
| `feather` | Outline, rounded | `home`, `settings`, `user`, `search` |
| `Material Symbols Outlined` | Outline | `home`, `settings`, `person`, `search` |
| `Material Symbols Rounded` | Rounded | `home`, `settings`, `person`, `search` |

### Uso de Iconos
```javascript
icon=I(container, {type: "icon_font", iconFontFamily: "lucide", iconFontName: "settings", width: 24, height: 24, fill: "$--foreground"})
```

### Iconos Comunes

| Accion | Lucide/Feather | Material Symbols |
|--------|----------------|------------------|
| Home | `home` | `home` |
| Settings | `settings` | `settings` |
| User | `user` | `person` |
| Search | `search` | `search` |
| Add | `plus` | `add` |
| Close | `x` | `close` |
| Edit | `edit`, `pencil` | `edit` |
| Delete | `trash`, `trash-2` | `delete` |
| Dashboard | `layout-dashboard` | `dashboard` |

---

## 4. Composicion de Sidebar

### Estructura
```
Sidebar Component
├── Header (logo, brand)
├── Content Slot ← Insertar items aqui
└── Footer (user profile, settings)
```

### Ejemplo
```javascript
sidebar=I(page, {type: "ref", ref: "sidebarId", height: "fill_container"})
sectionTitle=I(sidebar+"/contentSlotId", {type: "ref", ref: "sidebarSectionTitleId", descendants: {"labelTextId": {content: "Main Menu"}}})
itemDashboard=I(sidebar+"/contentSlotId", {type: "ref", ref: "sidebarItemActiveId", descendants: {"iconId": {iconFontName: "dashboard"}, "labelId": {content: "Dashboard"}}})
itemUsers=I(sidebar+"/contentSlotId", {type: "ref", ref: "sidebarItemDefaultId", descendants: {"iconId": {iconFontName: "users"}, "labelId": {content: "Users"}}})
```

---

## 5. Composicion de Cards

### Estructura
```
Card Component
├── Header Slot ← Titulo, descripcion
├── Content Slot ← Contenido principal
└── Actions Slot ← Botones
```

### Ejemplo
```javascript
card=I(container, {type: "ref", ref: "cardId", width: 480})
newNode=R(card+"/headerSlotId", {type: "frame", layout: "vertical", gap: 4, padding: 24, width: "fill_container", children: [
  {type: "text", content: "Card Title", fill: "$--foreground", fontSize: 18, fontWeight: "600"},
  {type: "text", content: "Description", fill: "$--muted-foreground", fontSize: 14}
]})
U(card+"/contentSlotId", {layout: "vertical", gap: 16, padding: 24})
input=I(card+"/contentSlotId", {type: "ref", ref: "inputGroupId", width: "fill_container"})
U(card+"/actionsSlotId", {gap: 12, justifyContent: "end", padding: 24})
saveBtn=I(card+"/actionsSlotId", {type: "ref", ref: "buttonPrimaryId", descendants: {"labelId": {content: "Save"}}})
```

---

## 6. Composicion de Tablas

### Estructura
```
Table (frame)
├── Table Header — Search/filter + action buttons
├── Table Wrapper
│   ├── Header Row
│   │   └── Cell → Content
│   ├── Data Row 1
│   │   └── Cell → Content
│   └── ...
└── Table Footer — Pagination
```

### Anchos de Columna Sugeridos

| Tipo de Columna | Ancho Tipico |
|-----------------|--------------|
| Nombre (primario) | 200-250px |
| Email, URL | `fill_container` |
| Status, badge | 100-120px |
| Fecha | 120-150px |
| Acciones | 80-100px |
| Numeros | 80-100px |

### Ejemplo
```javascript
row1=I(table, {type: "ref", ref: "dataTableRowId", width: "fill_container"})
nameCell=I(row1, {type: "ref", ref: "dataTableCellId", width: "fill_container"})
nameText=I(nameCell, {type: "text", content: "John Doe"})
statusCell=I(row1, {type: "ref", ref: "dataTableCellId", width: 120})
statusBadge=I(statusCell, {type: "ref", ref: "labelSuccessId", descendants: {"textId": {content: "Active"}}})
```

---

## 7. Patrones de Layout de Pantalla

### Pattern A: Sidebar + Content (Dashboard)
```
┌──────────┬────────────────────────────────┐
│          │                                │
│ Sidebar  │     Main Content Area          │
│  280px   │      fill_container            │
│          │                                │
└──────────┴────────────────────────────────┘
```

```javascript
screen=I(document, {type: "frame", name: "Dashboard", layout: "horizontal", width: 1440, height: "fit_content(900)", fill: "$--background", placeholder: true})
sidebar=I(screen, {type: "ref", ref: "sidebarId", height: "fill_container"})
main=I(screen, {type: "frame", layout: "vertical", width: "fill_container", height: "fill_container(900)", padding: 32, gap: 24})
```

### Pattern B: Header + Content
```
┌────────────────────────────────────────────┐
│              Header Bar (64px)             │
├────────────────────────────────────────────┤
│                                            │
│            Content Area                    │
│                                            │
└────────────────────────────────────────────┘
```

```javascript
screen=I(document, {type: "frame", layout: "vertical", width: 1200, height: "fit_content(800)", fill: "$--background", placeholder: true})
header=I(screen, {type: "frame", layout: "horizontal", width: "fill_container", height: 64, padding: [0, 24], alignItems: "center", justifyContent: "space_between"})
content=I(screen, {type: "frame", layout: "vertical", width: "fill_container", height: "fit_content(736)", padding: 32, gap: 24})
```

### Pattern C: Two-Column Layout
```
┌─────────────────────┬─────────────┐
│                     │             │
│    Main (2/3)       │  Side (1/3) │
│   fill_container    │   360px     │
│                     │             │
└─────────────────────┴─────────────┘
```

```javascript
columns=I(content, {type: "frame", layout: "horizontal", width: "fill_container", height: "fill_container(900)", gap: 24})
mainCol=I(columns, {type: "frame", layout: "vertical", width: "fill_container", gap: 24})
sideCol=I(columns, {type: "frame", layout: "vertical", width: 360, gap: 24})
```

---

## 8. Referencia de Espaciado

| Contexto | Gap | Padding |
|----------|-----|---------|
| Secciones de pantalla | 24-32 | — |
| Grid de cards | 16-24 | — |
| Campos de formulario | 16 | — |
| Grupos de botones | 12 | — |
| Dentro de cards | — | 24 |
| Dentro de botones | — | [10, 16] |
| Dentro de inputs | — | [8, 16] |
| Area de contenido | — | 32 |
| Items de sidebar | 0 | [12, 16] |

---

## 9. Jerarquia de Botones

| Prioridad | Variante | Uso Comun |
|-----------|----------|-----------|
| 1 | Primary/Default | Accion principal (Save, Submit) |
| 2 | Secondary | Acciones alternativas |
| 3 | Outline | Terciario, Cancel, Back |
| 4 | Ghost | Acciones inline, navegacion |
| 5 | Destructive | Delete, Remove |

### Alineacion de Acciones
- **Cards/Modals:** Alinear a la derecha (`justifyContent: "end"`)
- **Forms:** Submit a la derecha
- **Toolbars:** Primario a la izquierda, secundario a la derecha
- **Destructive + Cancel:** Cancel izquierda, Destructive derecha

---

## 10. Design Tokens

### Colores
| Token | Uso |
|-------|-----|
| `$--background` | Fondo de pagina |
| `$--foreground` | Texto primario |
| `$--muted-foreground` | Texto secundario |
| `$--card` | Fondo de cards |
| `$--border` | Bordes, divisores |
| `$--primary` | Acciones primarias |
| `$--destructive` | Acciones de peligro |

### Colores Semanticos
| Estado | Background | Foreground |
|--------|------------|------------|
| Success | `$--color-success` | `$--color-success-foreground` |
| Warning | `$--color-warning` | `$--color-warning-foreground` |
| Error | `$--color-error` | `$--color-error-foreground` |
| Info | `$--color-info` | `$--color-info-foreground` |

### Tipografia
| Token | Uso |
|-------|-----|
| `$--font-primary` | Headings, labels, navegacion |
| `$--font-secondary` | Body text, descripciones |

### Border Radius
| Token | Uso |
|-------|-----|
| `$--radius-none` | Tablas, contenedores sharp |
| `$--radius-m` | Cards, modals |
| `$--radius-pill` | Buttons, inputs, badges |

---

## 11. Principios de Diseno

### Jerarquia Visual
- Un punto focal claro por seccion
- Usar tamano, peso y color para establecer importancia
- Acciones primarias visualmente dominantes

### Alineacion y Grid
- Alinear elementos a un grid implicito
- Consistencia en alineacion de bordes
- Evitar elementos huerfanos o flotantes

### Consistencia de Espaciado
- Siempre usar valores de gap/padding existentes
- No mezclar valores de espaciado arbitrarios
- Mantener ritmo vertical consistente

### Uso de Color
- Siempre usar tokens `$--variable`, nunca hardcodear hex/rgb
- Asegurar suficiente contraste para legibilidad
- Usar colores semanticos para su proposito

### Densidad de Contenido
- No sobrellenar - dejar espacio para respirar
- Cards deben contener una idea primaria
- Tablas con cantidad razonable de columnas (4-7)

---

*Fuente: Pencil.dev Design System Guidelines*
*Actualizado: 2026-02-02*
