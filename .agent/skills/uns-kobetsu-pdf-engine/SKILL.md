---
name: uns-kobetsu-pdf-engine
type: feature
description: >
---
  Motor de generación de PDFs con PDFKit para documentos legales japoneses de派遣.
  Contiene todas las constantes de layout, helpers de celdas, anchos de columna, y patrones
  para crear grids densos en A4 vertical. Usa este skill SIEMPRE que necesites: (1) Modificar
  el formato del個別契約書 PDF, (2) Crear nuevas plantillas de documentos派遣, (3) Ajustar
  anchos de columna o alturas de fila, (4) Agregar nuevas secciones al PDF, (5) Debuggear
  problemas de layout en PDFKit, (6) Replicar el estilo de grid denso japonés.
  Triggers: PDF layout, PDFKit grid, kobetsu PDF, formato PDF, columnas PDF, 個別契約書PDF,
  layout A4, dense grid PDF, tabla PDF japonés, PDFKit helper, celda bordes PDF.
---

# UNS Kobetsu PDF Engine

Motor de layout para generar documentos legales japoneses en una sola página A4 usando PDFKit.

## Constantes Globales

```javascript
// A4 portrait: 595.28 x 841.89 pt
const LM = 20;    // Margen izquierdo
const W = 555;     // Ancho útil total (595.28 - 20*2 ≈ 555)
const RH = 12;     // Altura de fila estándar
const SH = 10;     // Altura de header de sección
const tallH = 16;  // Altura de fila expandida (para texto largo)
```

## Helpers de Dibujo

Estas 3 funciones son la base de todo el sistema de grid:

```javascript
// C() — Celda genérica con borde
// Dibuja un rectángulo con borde, fondo opcional, y texto posicionado
function C(x, y, w, h, text, fs, opts) {
  opts = opts || {};
  doc.lineWidth(0.4);
  doc.rect(x, y, w, h).stroke();
  if (opts.bg) {
    doc.save().fillColor(opts.bg)
      .rect(x + 0.2, y + 0.2, w - 0.4, h - 0.4).fill().restore();
  }
  doc.fontSize(fs || 6).fillColor('#000');
  const p = 2; // padding
  const ty = y + (h - (fs || 6)) / 2; // centrado vertical
  if (opts.align === 'center') {
    doc.text(text || '', x, ty, { width: w, align: 'center', lineBreak: false });
  } else {
    doc.text(text || '', x + p, ty, { width: w - p * 2, lineBreak: opts.wrap || false });
  }
}

// L() — Celda etiqueta (fondo gris #e8e8e8)
function L(x, y, w, h, text, fs) {
  C(x, y, w, h, text, fs || 5.5, { bg: '#e8e8e8' });
}

// V() — Celda valor (sin fondo)
function V(x, y, w, h, text, fs) {
  C(x, y, w, h, text, fs || 6, {});
}
```

## Anchos de Columna por Sección

### Filas de Ubicación (派遣先事業所 / 就業場所)

```
| MainLabel(58) | SubLabel(20) | Value(135) | SubLabel(22) | Value(215) | TEL(18) | Value(87) |
  Total: 58 + 20 + 135 + 22 + 215 + 18 + 87 = 555 ✓
```

```javascript
const Lmain = 58;   // 派遣先事業所 / 就業場所
const Lsub = 20;    // 名称 / 所在地
const Laddr = 22;   // 所在地 (segunda)
const Ltel = 18;    // TEL
const V1 = 135;     // Valor nombre
const V2 = 215;     // Valor dirección
const V3 = 87;      // Valor teléfono
```

### Filas de Persona (指揮命令者 / 責任者 / 苦情処理)

```
| Label(105) | 部署(14) | Val(84) | 役職(14) | Val(56) | 氏名(14) | Val(100) | TEL(14) | Val(154) |
  Total: 105 + 14 + 84 + 14 + 56 + 14 + 100 + 14 + 154 = 555 ✓
```

```javascript
const PL = 105;          // Label principal
const PsL = 14;          // Sub-label (部署/役職/氏名/TEL)
const PvW = [84, 56, 100, 154]; // Anchos de valor

function personRow(yy, mainLbl, dept, role, name, phone) {
  let xx = LM;
  L(xx, yy, PL, RH, mainLbl, 4.5); xx += PL;
  L(xx, yy, PsL, RH, '部署', 4.5); xx += PsL;
  V(xx, yy, PvW[0], RH, dept, 5.5); xx += PvW[0];
  L(xx, yy, PsL, RH, '役職', 4.5); xx += PsL;
  V(xx, yy, PvW[1], RH, role, 5.5); xx += PvW[1];
  L(xx, yy, PsL, RH, '氏名', 4.5); xx += PsL;
  V(xx, yy, PvW[2], RH, name, 5.5); xx += PvW[2];
  L(xx, yy, PsL, RH, 'TEL', 4.5); xx += PsL;
  V(xx, yy, PvW[3], RH, phone, 5.5);
}
```

### Fila de Tarifas (派遣料金)

```
| 基本(50) | ¥val(68) | 残業(60) | ¥val(68) | 休日(60) | ¥val(68) | 60h超(68) | ¥val(113) |
  Total: 50 + 68 + 60 + 68 + 60 + 68 + 68 + 113 = 555 ✓
```

```javascript
const rlw = [50, 60, 60, 68];    // Rate label widths
const rvw = [68, 68, 68, 113];   // Rate value widths
```

### Filas de Contenido (派遣内容)

```
| Label(65) | Value(490) |  ← fila completa
| Label(65) | Value(200) | Label2(30) | Value2(260) |  ← fila dividida
  Total: 65 + 490 = 555 ✓  /  65 + 200 + 30 + 260 = 555 ✓
```

### Filas de Pago (支払い)

```
| 締日(35) | Val(80) | 支払日(40) | Val(100) | 支払方法(50) | Val(250) |
  Total: 35 + 80 + 40 + 100 + 50 + 250 = 555 ✓
```

### Secciones Legales (altura dinámica)

```javascript
function legalRow(yy, title, text) {
  const lLW = 85;  // Label width
  const lVW = W - lLW;  // Value width = 470
  const lFS = 4.5; // Font size legal

  const th = doc.heightOfString(text, { width: lVW - 4, fontSize: lFS });
  const h = Math.max(th + 4, 10);
  L(LM, yy, lLW, h, title, 5);
  doc.lineWidth(0.4).rect(LM + lLW, yy, lVW, h).stroke();
  doc.fontSize(lFS).fillColor('#000').text(text, LM + lLW + 2, yy + 2, { width: lVW - 4 });
  return yy + h;
}
```

## Tipografía por Sección

| Sección | Font Size | Notas |
|---|---|---|
| Título | 12pt | Centrado |
| Texto intro | 5.5pt | Párrafo libre |
| Headers de sección | 7pt | Fondo `#d0d0e8`, centrado |
| Labels (etiquetas) | 5-5.5pt | Fondo gris `#e8e8e8` |
| Valores | 6pt | Sin fondo |
| Person row labels | 4.5pt | Para texto largo (製造業務専門派遣先責任者) |
| Checkboxes | 6pt | ☑ y □ Unicode |
| Tarifas valores | 7pt | Más grande para legibilidad |
| Texto legal | 4.5pt | Altura dinámica |
| Firma | 6pt | Dos columnas |

## Mapa de Posiciones Y (Estimado)

```
y=18   → Título
y=34   → Texto introductorio
y=45   → 【派遣先】 header
y=55   → 派遣先事業所 (3 filas × 12pt = 36pt)
y=91   → 指揮命令者 (3 filas × 12pt = 36pt)
y=130  → 【派遣元】 header
y=140  → 責任者 (2 filas × 12pt = 24pt)
y=167  → Checkboxes (2 filas × 11pt = 22pt)
y=192  → 【派遣内容】 header
y=202  → Contenido (6 filas, ~80pt total)
y=285  → 【派遣料金】 header + rates
y=315  → 【支払い】 header + payment
y=352  → Secciones legales (~130pt dinámico)
y=490  → Firma
```

## Patrones de PDFKit

### Texto en celda (no rebasa)
```javascript
doc.text(text, x + 2, ty, { width: w - 4, lineBreak: false });
```

### Texto multilínea en celda alta
```javascript
doc.lineWidth(0.4).rect(x, y, w, tallH).stroke();
doc.fontSize(5).text(text, x + 2, y + 2, { width: w - 4 }); // lineBreak: true (default)
```

### Header de sección con fondo
```javascript
C(LM, y, W, SH, '【派遣先】', 7, { bg: '#d0d0e8', align: 'center' });
```

### Checkbox con Unicode
```javascript
C(LM, y, halfW, cbH, '  ☑ 協定対象派遣労働者に指定', 6, {});
C(LM + halfW, y, W - halfW, cbH, '  □ 指定なし', 6, {});
```

## Regla de Oro

**Siempre verificar que los anchos sumen W (555)**. Si se cambia un ancho de columna, ajustar la última columna de la fila para absorber la diferencia. Usar comentarios `// Check: a+b+c = 555 ✓` para documentar.

## Cómo Agregar Nueva Sección

1. Definir anchos de columna que sumen 555
2. Agregar header con `C(LM, y, W, SH, '【新セクション】', 7, { bg: '#d0d0e8', align: 'center' })`
3. Incrementar `y += SH`
4. Agregar filas con `L()` para labels y `V()` para valores
5. Incrementar `y += RH` por cada fila
6. Agregar gap `y += 3` entre secciones
7. Verificar que todo cabe en la página (y < 820 al final)
