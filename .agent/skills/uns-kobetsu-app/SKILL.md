---
name: uns-kobetsu-app
type: feature
description: >
---
  Guía completa de la aplicación Electron Kobetsu App para generar個別契約書,通知書 y DAICHO.
  Usa este skill SIEMPRE que necesites: (1) Modificar o extender la app Kobetsu, (2) Debuggear
  errores de Electron/SQLite/PDFKit, (3) Agregar nuevos empleados o empresas, (4) Cambiar el
  formato de PDFs generados, (5) Entender la arquitectura del proyecto, (6) Agregar nuevas
  funcionalidades al frontend o backend. Triggers: kobetsu app, electron app, kobetsu修正,
  app修正, desktop app UNS, modificar kobetsu, debug electron, SQLite kobetsu, agregar empleado,
  cambiar PDF formato, nueva funcionalidad kobetsu.
---

# UNS Kobetsu App — Guía Completa

Aplicación de escritorio Electron + SQLite + PDFKit que genera contratos individuales de派遣
para ユニバーサル企画株式会社 (UNS-Kikaku).

## Arquitectura

```
kobetsu-app/
├── package.json                   ← Electron 28 + better-sqlite3 + pdfkit
├── fonts/NotoSansJP-Regular.ttf   ← Fuente japonesa (9.6MB, REQUERIDA)
├── data/kobetsu.db                ← SQLite (auto-generada al iniciar)
├── output/                        ← PDFs generados
├── src/
│   ├── main/
│   │   ├── main.js                ← Backend: DB + IPC + PDF generators (937 líneas)
│   │   └── seed-data.js           ← 76 empresas + 392 empleados (301KB)
│   └── renderer/
│       └── index.html             ← Frontend single-file (601 líneas)
```

## Stack y Dependencias

| Componente | Versión | Configuración Crítica |
|---|---|---|
| Electron | 28.x | `nodeIntegration: true`, `contextIsolation: false` |
| better-sqlite3 | 11.x | Requiere `npx @electron/rebuild` después de install |
| PDFKit | 0.13.x | Registra fuente JP como `doc.registerFont('JP', fontPath)` |

## Comandos Esenciales

```bash
cd kobetsu-app
npm install                 # Instalar dependencias
npx @electron/rebuild       # OBLIGATORIO: recompilar better-sqlite3 para Electron
npm start                   # Ejecutar (equivale a npx electron .)

# Resetear base de datos
del data\kobetsu.db         # Windows
rm data/kobetsu.db          # Linux/Mac
npm start                   # Se re-crea automáticamente desde seed-data.js
```

## Base de Datos SQLite

### Tablas Principales

**employees** (392 registros) — Campos clave:
- `employee_number` (UNIQUE), `full_name`, `katakana_name`, `sex`, `nationality`
- `dispatch_company`, `department`, `line`, `job_description`
- `hourly_rate`, `billing_rate`, `profit_margin`
- `birth_date`, `hire_date`, `actual_hire_date`
- `visa_expiry`, `visa_type`, `postal_code`, `address`
- `health_insurance`, `nursing_insurance`, `pension`, `standard_compensation`

**client_companies** (76 registros) — Cada registro es una combinación única empresa+línea:
- Datos empresa: `company_name/address/phone`
- Datos fábrica: `factory_name/address/phone`
- Personal: `commander_dept/name/phone`, `supervisor_dept/name/phone`
- Quejas: `complaint_client_*`, `complaint_uns_*`, `complaint_uns_handler_*`
- Tarifas: `hourly_rate`, `billing_rate`, `profit_margin`
- Horarios: `work_hours`, `break_time`, `overtime_hours`, `calendar`
- Pagos: `cutoff_day`, `payment_day`, `bank_account`, `time_unit`

### Consultas Cascading (IPC Handlers)

```javascript
// 1. Obtener empresas únicas
ipcMain.handle('get-companies', () =>
  db.prepare('SELECT DISTINCT company_name FROM client_companies ORDER BY company_name').all()
);

// 2. Fábricas de una empresa
ipcMain.handle('get-factories', (_, company) =>
  db.prepare('SELECT DISTINCT factory_name FROM client_companies WHERE company_name=?').all(company)
);

// 3. Departamentos de una fábrica
ipcMain.handle('get-departments', (_, company, factory) =>
  db.prepare('SELECT DISTINCT department FROM client_companies WHERE company_name=? AND factory_name=?').all(company, factory)
);

// 4. Líneas de un departamento
ipcMain.handle('get-lines', (_, company, factory, dept) =>
  db.prepare('SELECT DISTINCT line FROM client_companies WHERE company_name=? AND factory_name=? AND department=?').all(company, factory, dept)
);

// 5. Detalles completos de una línea
ipcMain.handle('get-company-details', (_, line) =>
  db.prepare('SELECT * FROM client_companies WHERE line=?').get(line)
);

// 6. Empleados de una empresa
ipcMain.handle('get-employees', (_, company) =>
  db.prepare('SELECT * FROM employees WHERE dispatch_company=? ORDER BY employee_number').all(company)
);
```

## Generación de PDFs

La app genera 3 tipos de documentos. Cada uno tiene su propia función en `main.js`:

| Documento | Función | Formato | Líneas |
|---|---|---|---|
| 個別契約書 | `generateKobetsuPDF()` | 1 página A4 vertical, grid denso | 393-677 |
| 派遣先通知書 | `generateTsuchishoPDF()` | Tabla 9 columnas, multi-página | 680-781 |
| 派遣元管理台帳 | `generateDaichoPDF()` | 1 PDF por empleado, checkboxes | 787-937 |

Para detalles del layout del個別契約書, consultar el skill `uns-kobetsu-pdf-engine`.

### Flujo de Generación de PDF

```javascript
// En el IPC handler 'generate-pdf':
const doc = new PDFDocument({ size: 'A4', margin: 30 });
doc.registerFont('JP', fontPath);
doc.font('JP');

// Dispatch según tipo
if (type === 'kobetsu') generateKobetsuPDF(doc, data);
else if (type === 'tsuchisho') generateTsuchishoPDF(doc, data);
else if (type === 'daicho') generateDaichoPDF(doc, data);

doc.end();
```

### Data Object pasado a generatePDF

```javascript
const data = {
  company_name: 'string',          // Nombre de la empresa派遣先
  factory_name: 'string',          // Nombre de la fábrica
  department: 'string',            // Departamento
  line: 'string',                  // Línea (ID único)
  hourly_rate: Number,             // Tarifa por hora
  start_date: 'YYYY-MM-DD',       // Inicio del contrato
  end_date: 'YYYY-MM-DD',         // Fin del contrato
  contract_date: 'YYYY-MM-DD',    // Fecha del contrato (start - 2 días hábiles)
  notification_date: 'YYYY-MM-DD',// Fecha de notificación (start - 3 días hábiles)
  employee_count: Number,          // Cantidad de empleados seleccionados
  employees: Array,                // Array de objetos employee
  companyDetails: Object,          // Objeto completo de client_companies
  copies: Number                   // Número de copias
};
```

## Reglas de Negocio

### Tarifas
- 基本: `hourly_rate`
- 残業 (125%): `Math.round(rate × 1.25)`
- 休日 (135%): `Math.round(rate × 1.35)`
- 60時間超 (150%): `Math.round(rate × 1.50)`
- Unidad: configurable por empresa (`time_unit`, default 15 min)

### Fechas
- `contract_date` = `start_date` - 2 días hábiles (excluye sáb/dom)
- `notification_date` = `start_date` - 3 días hábiles

### Tipo de Empleo
- **無期雇用** (indefinido): antigüedad > 1095 días (3 años)
- **有期雇用** (temporal): antigüedad ≤ 1095 días

## Problemas Comunes y Soluciones

| Problema | Solución |
|---|---|
| `NODE_MODULE_VERSION mismatch` | `npx @electron/rebuild` |
| `electron no se reconoce` | Usar `npx electron .` |
| DB desactualizada | Borrar `data/kobetsu.db` y reiniciar |
| Caracteres rotos en PDF | Verificar `fonts/NotoSansJP-Regular.ttf` |
| Empleados no aparecen | El join es por campo `line`, no por company_name |

## Cómo Extender la App

### Agregar nueva empresa
Añadir objeto a `COMPANY_DATA` en `seed-data.js` con claves compactas:
```javascript
{ cn:'新会社名', ca:'住所', cp:'電話', fn:'工場名', fa:'工場住所', fp:'工場電話',
  dp:'部署', ln:'ライン名', hr:1200, br:1620, pm:420, ... }
```
Luego borrar `kobetsu.db` y reiniciar.

### Agregar nuevo empleado
Añadir objeto a `EMPLOYEE_DATA` en `seed-data.js`:
```javascript
{ en:'E001', fn:'名前', kn:'カタカナ', sx:'M', nt:'ベトナム',
  bd:'1990-01-01', hr:1200, dc:'派遣先名', dp:'部署', ln:'ライン', ... }
```

### Modificar formato de PDF
Editar la función correspondiente en `main.js`. Ver skill `uns-kobetsu-pdf-engine` para constantes de layout y helpers.

### Agregar nueva página al frontend
En `index.html`, agregar al sidebar y crear la función `renderNuevaPage()` siguiendo el patrón existente de `renderContractPage()`.
