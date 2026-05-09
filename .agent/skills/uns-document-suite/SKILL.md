---
name: uns-document-suite
type: feature
description: >
---
  Suite completa de generacion de 6 documentos legales PDF para派遣 de UNS-Kikaku (JP-v26.3.10).
  Cubre los 6 tipos: 個別契約書 (contrato individual), 派遣先通知書 (notificacion), 派遣先管理台帳
  (registro cliente), 派遣元管理台帳 (registro agencia), 労働契約書兼就業条件明示書 (contrato laboral),
  就業条件明示書 (condiciones de empleo). Usa este skill SIEMPRE que necesites: (1) Generar o modificar
  cualquier documento PDF de派遣, (2) Entender el formato exacto de cada documento, (3) Agregar campos
  o secciones a un PDF existente, (4) Debuggear layout de PDFKit, (5) Entender la API de documentos,
  (6) Crear nuevos tipos de documentos派遣. Triggers: generar PDF, documento派遣, 個別契約書, 通知書,
  管理台帳, 契約書, 就業条件明示書, kobetsu PDF, tsuchisho, daicho, keiyakusho, shugyojoken,
  document generation, PDF layout, PDFKit, haken document, dispatch document, 派遣書類.
user-invocable: false
---

# UNS Document Suite — 6 Documentos Legales PDF

Suite completa de generacion de documentos para el sistema JP-v26.3.10 (Hono + React + PDFKit).

## Resumen de Documentos

| # | Documento | Archivo | Funcion | Paginas |
|---|-----------|---------|---------|---------|
| 1 | 個別契約書 | `server/pdf/kobetsu-pdf.ts` | `generateKobetsuPDF()` | 1 por contrato |
| 2 | 派遣先通知書 | `server/pdf/tsuchisho-pdf.ts` | `generateTsuchishoPDF()` | Multi (20 emp/pag) |
| 3 | 派遣先管理台帳 | `server/pdf/hakensakikanridaicho-pdf.ts` | `generateHakensakiKanriDaichoPDF()` | 1 por empleado |
| 4 | 派遣元管理台帳 | `server/pdf/hakenmotokanridaicho-pdf.ts` | `generateHakenmotoKanriDaichoPDF()` | 1 por empleado |
| 5 | 労働契約書兼就業条件明示書 | `server/pdf/keiyakusho-pdf.ts` | `generateKeiyakushoPDF()` | Multi-pagina |
| 6 | 就業条件明示書 | `server/pdf/shugyojoken-pdf.ts` | `generateShugyoJokenMeijishoPDF()` | Multi-pagina |

## API Endpoints

```
POST /api/documents/generate/:contractId     → Genera docs 1-4 + 6 (bundle por contrato)
POST /api/documents/generate-batch           → Genera docs 1-4 para multiples contratos
POST /api/documents/keiyakusho/:employeeNumber   → Genera doc 5 por empleado
POST /api/documents/shugyojoken/:employeeNumber  → Genera doc 6 por empleado
GET  /api/documents/download/:filename       → Descarga PDF generado
GET  /api/documents/list/:contractId         → Lista PDFs de un contrato
```

## Constantes Compartidas (helpers.ts)

```typescript
// A4: 595.28 x 841.89 pt
const LM = 20;      // Margen izquierdo (30 en kobetsu)
const W  = 555;      // Ancho util (535 en kobetsu)
const RH = 12;       // Altura fila estandar
const SH = 10;       // Altura header seccion
const TALL_H = 16;   // Fila expandida

// Helpers principales
C(x, y, w, h, text, fs, opts)  // Celda generica con borde
L(x, y, w, h, text, fs)        // Celda etiqueta (fondo #e8e8e8)
V(x, y, w, h, text, fs)        // Celda valor (sin fondo)
personRow(y, label, dept, role, name, phone)  // 9 celdas persona
legalRow(y, title, text)        // Fila legal altura dinamica
sectionHeader(y, text)          // Header seccion fondo #d0d0e8
drawRow(y, cells[])             // Multi-celda para台帳
labelRow(y, label, value, lw)   // 2 celdas label+valor
```

### Funciones Utilitarias

```typescript
parseDate(str)              // ISO o japones → Date
calculateAge(birthDate)     // Edad en anos
ageGroup(birthDate)         // "18未満" | "18以上45歳未満" | "46以上60歳未満" | "60歳以上"
isIndefiniteEmployment(h,e) // >1095 dias = 無期雇用
yen(amount)                 // Formato ¥1,234
```

### Datos UNS (constantes en helpers.ts)

```
会社名: ユニバーサル企画株式会社
住所: 〒461-0025 愛知県名古屋市東区徳川2-18-18
代表者: 代表取締役 中山 雅和
許可番号: 派 23-303669
TEL: 052-938-8840
派遣元責任者: 営業部 取締役 部長 中山 欣英
```

---

## Doc 1: 個別契約書 (kobetsu-pdf.ts)

Contrato individual de派遣. Grid denso de 1 pagina A4.

### Layout

- **Pagina:** A4 vertical, margen izq 30pt, top 11pt
- **Grid:** 27 columnas (A-AA), 64 filas, ancho total 535pt
- **Escala:** Factor 0.8946 para encajar en A4
- **Font:** Auto-shrink (min 3pt) para encajar en celda
- **Titulo:** 13pt centrado "人材派遣個別契約書"

### Secciones (de arriba a abajo)

| Fila | Seccion | Contenido |
|------|---------|-----------|
| 1 | Titulo | "人材派遣個別契約書" (13pt) |
| 2-3 | Intro | Texto "甲(派遣先)...乙(派遣元)..." |
| 4-9 | 【派遣先】 | Empresa, fabrica, direccion, TEL, 指揮命令者, 苦情処理担当, 派遣先責任者 |
| 10-11 | 【派遣元】 | 派遣元責任者, 苦情処理担当 |
| 12-20 | 【派遣内容】 | 業務内容, 責任程度, 契約期間, 就業日, 就業時間, 休憩, 時間外, 人数 |
| 21-25 | 【派遣料金】 | 基本/残業(125%)/深夜(125%)/休日(135%)/60h超(150%) |
| 26-29 | 【支払い】 | 締日, 支払日, 振込先 |
| 30-57 | Clausulas legales | 安全衛生, 便宜供与, 苦情処理, 契約解除, 紛争防止, 無期雇用, 待遇決定 |
| 58-64 | Firma | Fecha, 甲(印), 乙(印) |

### Tarifas (calculadas automaticamente)

```
基本:     ¥hourlyRate
残業125%: ¥Math.round(rate * 1.25)
深夜125%: ¥Math.round(rate * 1.25)
休日135%: ¥Math.round(rate * 1.35)
60h超150%: ¥Math.round(rate * 1.50)
```

### Prioridad de Tarifa (CRITICO)

```
1. contract_employees.hourlyRate  ← tasa individual por contrato (billingRate)
2. employee.billingRate           ← 単価 de Excel import
3. factory.hourlyRate             ← fallback de fabrica
```

---

## Doc 2: 派遣先通知書 (tsuchisho-pdf.ts)

Notificacion a la empresa cliente con tabla de empleados despachados.

### Layout

- **Pagina:** A4, margen 30pt, ancho 535pt
- **Paginacion:** 20 empleados por pagina, auto-continua
- **Fila:** 16pt por empleado

### Estructura

```
Header: "派遣先通知書" (14pt)
  → Destinatario (empresa cliente) 御中
  → Remitente (UNS datos completos)
  → Fecha de referencia

Tabla 9 columnas:
| No | 氏名(カタカナ) | 性別 | 年齢区分 | 雇用保険 | 健康保険 | 厚生年金 | 雇用期間 | 待遇決定方式 |
|    | katakanaName   | M/F  | ageGroup | 加入     | 加入     | 加入     | 無期/有期 | 協定対象...  |

Filas vacias auto-rellenadas hasta 20/pagina
Footer: "以上"
```

### Campos derivados

| Campo | Logica |
|-------|--------|
| 性別 | `gender === 'M' ? '男' : '女'` |
| 年齢区分 | `ageGroup(birthDate)` → 4 categorias |
| 雇用期間 | `isIndefinite ? '無期雇用' : '有期雇用(3月)'` |
| 保険 | Hardcoded "加入" (todos inscritos) |
| 待遇決定 | "協定対象派遣労働者(労使協定式方式)" |

---

## Doc 3: 派遣先管理台帳 (hakensakikanridaicho-pdf.ts)

Registro de gestion del lado cliente. 1 pagina por empleado.

### Layout

- **Pagina:** A4, margen 30pt, ancho 535pt
- **Filas:** 18pt altura, label 115pt ancho
- **Titulo:** "派遣先管理台帳" (14pt centrado)

### Secciones

```
1. 基本情報
   - カタカナ氏名, 性別, 年齢区分(60才以上/未満)
   - 社会保険: 雇用保険/健康保険/厚生年金 (有/無)

2. 派遣先情報
   - 会社名, 住所, 部署+ライン, TEL, 施設名
   - 業務内容 + 雇用期間(同じ行split)

3. 責任程度
   - ☑付与される権限なし / □付与される権限あり

4. 派遣期間
   - 開始日 ～ 終了日

5. 協定・限定チェック (3行)
   - ☑協定対象派遣労働者
   - 60才以上チェック + 協定対象限定
   - ☑協定対象派遣労働者に限定

6. 派遣先責任者
   - 部署 + 氏名 + TEL

7. 派遣元情報
   - UNS名 + 許可番号, 住所, 責任者

8. 就業日・状況
   - "派遣先年間カレンダーによる" + タイムシート参照

9. 教育訓練
   - 自動: "安全衛生教育" (初回 OR 入社から2年毎)

10. 苦情申出状況 (3対行)
    - 日付欄 + 内容欄 (申出/紛議)

Footer: "【教育訓練記録：毎２年更新】"
```

---

## Doc 4: 派遣元管理台帳 (hakenmotokanridaicho-pdf.ts)

Registro de gestion del lado agencia (UNS). 1 pagina por empleado.

### Layout

- **Pagina:** A4, margen 30pt, ancho 535pt
- **Filas:** 18pt, label 155pt ancho
- **Titulo:** "派遣元管理台帳" (13pt) + "労働者派遣法第37条" subtitulo

### Secciones

```
1. 派遣元事業主
   - UNS名, 許可番号, 住所

2. 派遣労働者
   - カタカナ氏名, 性別+年齢(60才以上/未満)
   - 国籍, 雇用形態(無期/有期3ヶ月)
   - 社会保険(3項チェック)

3. 派遣先
   - 会社名, 工場+住所, 部署+ライン, TEL

4. 派遣業務
   - 業務内容(全高), 責任程度(4択チェック)
   - 派遣期間, 就業日, 就業時間, 休憩, 時間外

5. 派遣料金・賃金 (CRITICO: 2レート区別)
   - 派遣料金(1時間): billingRate (単価 = 工場→UNS)
   - 派遣労働者の賃金(1時間): hourlyRate (時給 = UNS→社員)
   - 待遇決定方式: ☑協定対象派遣労働者(労使協定方式)

6. 責任者・苦情処理
   - 派遣元: 責任者 + 苦情担当
   - 派遣先: 責任者 + 苦情担当

7. その他
   - 抵触日(事業所単位), 契約日

8. 教育訓練 (3行: 訓練1/2/3)
9. キャリアコンサルティング (2行: 相談1/2)
10. 苦情申出 (表: No/申出日/苦情内容/処理状況, 3行)
```

### Distincion billingRate vs hourlyRate

```
派遣料金 = billingRate (単価) → lo que paga la fabrica a UNS
賃金     = hourlyRate (時給) → lo que paga UNS al trabajador
差額     = margen de UNS
```

---

## Doc 5: 労働契約書兼就業条件明示書 (keiyakusho-pdf.ts)

Contrato laboral + condiciones. Multi-pagina, por empleado.

### Layout

- **Pagina:** A4, margen 30pt, ancho 535pt
- **Filas:** 18pt, label 140pt (labelRow helper)
- **Auto-paginacion:** despues de fila 650+

### Secciones (12 bloques)

```
1. 労働者情報
   - カタカナ, 氏名, 生年月日+年齢, 性別, 国籍, 住所

2. 契約期間
   - 雇用期間(開始～終了), 雇用形態(無期/有期3ヶ月), 入社日

3. 就業場所
   - 会社名, 工場名, 部署+ライン, 住所, TEL
   - 業務内容, 責任程度, 抵触日

4. 派遣元責任者
   - UNS苦情処理担当, TEL

5. 就業時間
   - 日勤/夜勤(split) OR 一般, 休憩時間
   - シフトパターン, 就業日, 休日

6. 時間外労働
   - 上限, 特別条件, 深夜(22:00-5:00 +25%), 休日(月2回 +35%)

7. 賃金
   - 基本時給, 残業(+25%), 60h超(+50%), 休日(+35%), 深夜(+25%)
   - 締日, 支払日, 支払方法, 控除

8. 退職
   - 自己都合(30日前), 解雇(30日+手当)

9. 契約更新
   - 無期→N/A / 有期→☑更新可能(基準あり)

10. 社会保険・安全衛生
    - 加入状況, 安全規定, 守秘義務

11. 派遣料金
    - 単価表示, 協定対象派遣労働者方式

12. 在留資格 (外国人のみ)
    - ビザ種類, 期限

Footer: 署名欄 甲(雇用主UNS) + 乙(労働者)
```

### Endpoint y Parametros

```
POST /api/documents/keiyakusho/:employeeNumber
Body: { startDate?, endDate? }
→ Auto-calcula 3 meses si no se proveen fechas
→ Busca empleado por numero, su fabrica, empresa
→ Usa billingRate || factory.hourlyRate como tarifa
```

---

## Doc 6: 就業条件明示書 (shugyojoken-pdf.ts)

Notificacion de condiciones de empleo. Multi-pagina, por empleado.

### Layout

- **Pagina:** A4, margen 30pt, ancho 535pt
- **Filas:** 18pt, usa labelRow + drawRow helpers
- **Auto-paginacion:** despues de fila 620+, 700+

### Secciones (10 bloques)

```
1. 派遣先情報
   - 会社名, 就業場所(工場/部署/ライン), 所在地, 指揮命令者

2. 業務内容
   - 業務内容, 責任程度

3. 派遣期間・就業条件
   - 開始～終了, 就業日, 就業時間, 休憩, 時間外上限

4. 賃金
   - 時給, 残業(+25%), 60h超(+50%), 休日(+35%)
   - 締日, 支払日, 支払方法

5. 雇用情報
   - 雇用形態(無期/有期3ヶ月), 待遇決定方式(協定対象派遣労働者)

6. 社会保険
   - 雇用保険/健康保険/厚生年金: 加入

7. 苦情申出先
   - UNS側 + 派遣先側 担当者

8. 期間制限
   - 事業所単位の抵触日, 個人単位(3年上限)

9. 派遣契約解除措置
   - 30日前通知 OR 30日分賃金相当

10. 休暇
    - 年次有給(6ヶ月後), その他(慶弔/産前産後/育児介護)

Footer: 確認署名欄(労働者)
```

### Endpoint y Parametros

```
POST /api/documents/shugyojoken/:employeeNumber
Body: { startDate?, endDate? }
→ Misma logica que keiyakusho
→ Auto-calcula 3 meses si no hay fechas
```

---

## Flujo de Generacion por Contrato

Cuando se llama `POST /api/documents/generate/:contractId`:

```
1. Fetch contrato + relaciones (empresa, fabrica, empleados)
2. Build data comun (horarios, supervisores, tarifas)
3. Map empleados con prioridad: contract_employees.hourlyRate > employee.billingRate > factory.hourlyRate
4. Generar en secuencia:
   a. 個別契約書 (pag 1) + 通知書 (pag 2) → 1 PDF combinado
   b. 派遣先管理台帳 → 1 pagina por empleado
   c. 派遣元管理台帳 → 1 pagina por empleado
   d. 就業条件明示書 → 1 pagina por empleado
5. Guardar en output/ con nombre: "{empresa}_{departamento}_{tipo}.pdf"
```

## Flujo Batch

```
POST /api/documents/generate-batch
Body: { contractIds: [1, 2, 3] }
→ Genera 個別契約書+通知書 combinado (todos los contratos)
→ Genera 派遣先管理台帳 combinado (todos los empleados)
→ Genera 派遣元管理台帳 combinado (todos los empleados)
```

## Tipo de Empleo (compartido entre todos los docs)

```typescript
const hireDate = employee.hireDate || employee.actualHireDate;
const daysSinceHire = (startDate - hireDate) / (1000*60*60*24);
const isIndefinite = daysSinceHire > 1095; // >3 anos
// 無期雇用派遣労働者 vs 有期雇用派遣労働者(3ヶ月)
```

## Grupo de Edad (通知書 y台帳)

```typescript
age < 18  → "18未満"
age < 45  → "18以上45歳未満"
age < 60  → "46以上60歳未満"
age >= 60 → "60歳以上"
```

## Troubleshooting

| Problema | Solucion |
|----------|----------|
| Caracteres rotos | Verificar `server/pdf/fonts/NotoSansJP-Regular.ttf` |
| Texto cortado | Reducir fontSize o aumentar ancho celda |
| 2 paginas en kobetsu | Reducir row heights o font sizes |
| Tarifa incorrecta | Verificar cadena: contract_employees > employee.billingRate > factory |
| PDF vacio | Verificar que el contrato tiene empleados asignados |
| Fecha mal formateada | parseDate() acepta ISO y japones |
