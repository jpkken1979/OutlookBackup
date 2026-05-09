---
type: feature
name: haken-documents
description: "Generador de documentos oficiales en formato A4 vertical para empresas de envío de personal (人材派遣) en Japón. Genera contratos individuales (個別契約書), certificados de empleo, nóminas, documentos de notificación laboral, registros de asistencia, y más. Todos los formatos conformes a las regulaciones del Ministerio de Salud y Trabajo de Japón. Triggers: haken documents, 派遣, 在職証明書, 労働条件通知書, kobetsu, dispatch documents, Japanese HR."
---

# HAKEN-DOCUMENTS SKILL - Generador de Documentos Oficiales para 人材派遣

## Descripción

Skill especializada en la generación de documentos oficiales en formato A4 vertical para empresas de envío de personal (人材派遣) en Japón. Genera todos los documentos obligatorios que la agencia debe entregar a los trabajadores (派遣社員).

## Documentos Disponibles

### 📋 Documentos Contractuales (契約関連)

| Documento | 日本語名 | Descripción |
|-----------|---------|-------------|
| Individual Contract | 個別契約書 | Contrato individual por cada派遣 |
| Employment Contract | 雇用契約書 | Contrato de empleo派遣元↔派遣社員 |
| Basic Contract | 労働者派遣基本契約書 | Contrato marco派遣元↔派遣先 |
| Dispatch Contract | 労働者派遣契約書 | Contrato de派遣 específico |

### 📄 Documentos de Notificación (通知書関連)

| Documento | 日本語名 | Descripción |
|-----------|---------|-------------|
| Working Conditions | 労働条件通知書 | Notificación de condiciones laborales |
| Employment Conditions | 就業条件明示書 | Condiciones de empleo en派遣先 |
| Hiring Notice | 雇入通知書 | Notificación de contratación |

### 📑 Certificados (証明書関連)

| Documento | 日本語名 | Descripción |
|-----------|---------|-------------|
| Employment Certificate | 在職証明書 | Certificado de empleo actual |
| Retirement Certificate | 退職証明書 | Certificado de retiro |
| Income Certificate | 収入証明書 | Certificado de ingresos |
| Employment History | 就労証明書 | Certificado de historial laboral |

### 💰 Documentos Financieros (給与関連)

| Documento | 日本語名 | Descripción |
|-----------|---------|-------------|
| Pay Slip | 給与明細書 | Recibo de nómina mensual |
| Withholding Tax | 源泉徴収票 | Certificado de retención fiscal |
| Wage Ledger | 賃金台帳 | Registro de salarios |

### 📊 Registros Obligatorios (台帳関連)

| Documento | 日本語名 | Descripción |
|-----------|---------|-------------|
| Agency Ledger | 派遣元管理台帳 | Registro de gestión (agencia) |
| Client Ledger | 派遣先管理台帳 | Registro de gestión (cliente) |

### 🛂 Documentos para Visa (ビザ関連)

| Documento | 日本語名 | Descripción |
|-----------|---------|-------------|
| Employment Verification | 雇用証明書 | Para renovación de visa |
| Tax Payment Certificate | 納税証明書 | Comprobante de pago de impuestos |

## Estructura del Proyecto

```
haken-documents/
├── SKILL.md                    # Esta documentación
├── generate.py                 # CLI principal
│
├── templates/                  # Templates A4 en formato JSON/HTML
│   ├── contracts/             # 契約書類
│   │   ├── kobetsu_keiyakusho.py      # 個別契約書
│   │   ├── koyou_keiyakusho.py        # 雇用契約書
│   │   └── haken_keiyakusho.py        # 労働者派遣契約書
│   │
│   ├── notices/               # 通知書類
│   │   ├── roudou_jouken.py           # 労働条件通知書
│   │   ├── shuugyou_jouken.py         # 就業条件明示書
│   │   └── yatoire_tsuuchi.py         # 雇入通知書
│   │
│   ├── certificates/          # 証明書類
│   │   ├── zaishoku_shoumeisho.py     # 在職証明書
│   │   ├── taishoku_shoumeisho.py     # 退職証明書
│   │   ├── shuunyuu_shoumeisho.py     # 収入証明書
│   │   └── shuuro_shoumeisho.py       # 就労証明書
│   │
│   ├── payroll/               # 給与関連
│   │   ├── kyuuyo_meisai.py           # 給与明細書
│   │   ├── gensen_choushuuhyou.py     # 源泉徴収票
│   │   └── chingin_daicho.py          # 賃金台帳
│   │
│   └── ledgers/               # 台帳関連
│       ├── hakenmoto_kanri.py         # 派遣元管理台帳
│       └── hakensaki_kanri.py         # 派遣先管理台帳
│
├── core/
│   ├── pdf_generator.py       # Generador PDF (A4)
│   ├── html_generator.py      # Generador HTML
│   └── validators.py          # Validadores de datos
│
└── output/                    # Documentos generados
```

## Uso

### CLI Principal

```bash
# Ver documentos disponibles
python generate.py list

# Generar documento específico
python generate.py create --type zaishoku --data employee.json --output ./output

# Generar todos los documentos de un empleado
python generate.py batch --employee W0001 --output ./output

# Generar en formato específico
python generate.py create --type taishoku --format pdf --data data.json
```

### Ejemplos de Datos de Entrada

```json
{
  "employee": {
    "name_kanji": "グエン バン アイン",
    "name_kana": "グエン バン アイン",
    "name_romaji": "NGUYEN VAN ANH",
    "birth_date": "1990-05-15",
    "nationality": "ベトナム",
    "address": "愛知県豊田市若林町1-2-3",
    "phone": "090-1234-5678"
  },
  "company": {
    "name": "ユニバーサル企画株式会社",
    "permit_number": "派23-303669",
    "address": "愛知県豊田市土橋町7-7-7",
    "representative": "浅田 健二"
  },
  "employment": {
    "start_date": "2024-04-01",
    "end_date": "2027-03-31",
    "hourly_rate": 1200,
    "position": "製造作業員"
  }
}
```

## Formato A4 Vertical

Todos los documentos siguen el estándar A4 japonés:
- **Tamaño**: 210mm × 297mm
- **Márgenes**: 20mm (superior/inferior), 25mm (izquierda/derecha)
- **Fuente principal**: Yu Gothic / MS Gothic
- **Tamaño de fuente**: 10.5pt (cuerpo), 14pt (títulos)
- **Orientación**: Vertical (縦書き para algunos documentos formales)

## Reglas de Cumplimiento

- ✅ Formato conforme a 厚生労働省 (Ministerio de Trabajo)
- ✅ Incluye todos los campos obligatorios por ley
- ✅ Sello de empresa (社印) placeholder
- ✅ Número de documento único
- ✅ Fecha de emisión automática
- ✅ Período de retención indicado

## Integración con Haken SaaS

Esta skill se integra con el sistema Haken SaaS principal:

```python
from haken_documents import DocumentGenerator

# Inicializar generador
generator = DocumentGenerator(company_info)

# Generar certificado de empleo
doc = generator.create_zaishoku_shoumeisho(employee_data)

# Exportar a PDF
doc.export_pdf("zaishoku_nguyen.pdf")
```

---

*Haken Documents Skill v1.0.0*
*Creado para Antigravity Agents*
