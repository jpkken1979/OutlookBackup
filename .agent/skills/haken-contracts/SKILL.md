---
type: feature
name: haken-contracts
version: 1.0.0
description: Generador de documentos legales para empresas de 人材派遣 (派遣元). Incluye 個別契約書, 労働者派遣契約書, y otros documentos requeridos por la 労働者派遣法.
category: uns-enterprise
tags: [haken, contracts, legal, japanese, pdf, 派遣, 契約書]
author: Antigravity Agents
---

# Haken Contracts - 派遣契約書ジェネレーター

Generador de documentos legales para empresas de 人材派遣 (派遣元) como ユニバーサル企画株式会社.

## Documentos Soportados

### 1. 個別契約書 (Contrato Individual)
Contrato entre la 派遣元 (agencia) y la 派遣先 (empresa cliente) para cada trabajador派遣.

**Contenido requerido por ley:**
- 派遣労働者の氏名
- 業務内容
- 就業場所
- 指揮命令者
- 派遣期間
- 就業時間・休憩時間
- 派遣料金

### 2. 労働者派遣契約書 (Contrato de Trabajador派遣)
Contrato de empleo entre la 派遣元 y el 派遣労働者.

**Contenido requerido por ley:**
- 賃金
- 就業条件
- 社会保険加入状況
- 派遣先の情報
- 苦情処理担当者

### 3. 就業条件明示書 (Notificación de Condiciones Laborales)
Documento que debe entregarse al trabajador antes de cada 派遣.

### 4. 派遣先通知書 (Notificación a la Empresa Cliente)
Información del trabajador que debe comunicarse a la 派遣先.

## Uso

### Generar 個別契約書
```bash
python .agent/skills/haken-contracts/scripts/generate_kobetsu.py \
  --worker-name "グエン・ヴァン・ミン" \
  --client "株式会社ABC" \
  --start-date "2026-02-01" \
  --end-date "2026-04-30" \
  --hourly-rate 1500 \
  --output "contracts/kobetsu_nguyen_202602.pdf"
```

### Generar 労働者派遣契約書
```bash
python .agent/skills/haken-contracts/scripts/generate_roudousha.py \
  --worker-name "グエン・ヴァン・ミン" \
  --wage 1200 \
  --client "株式会社ABC" \
  --output "contracts/roudousha_nguyen.pdf"
```

### Generar desde JSON
```bash
python .agent/skills/haken-contracts/scripts/generate_contracts.py \
  --input placement_data.json \
  --type all \
  --output-dir contracts/
```

## Formato A4 Vertical (縦向き)

Todos los documentos se generan en formato **A4 縦向き (vertical/portrait)**:
- Tamaño: 210mm × 297mm
- Márgenes: 25mm (superior/inferior), 20mm (izquierda/derecha)
- Fuente: Gothic para títulos, Mincho para cuerpo

### Configuración CSS para A4 Vertical
```css
@page {
    size: A4 portrait;  /* 210mm x 297mm vertical */
    margin: 25mm 20mm;
}

body {
    font-family: "Yu Mincho", "MS Mincho", serif;
    font-size: 10.5pt;
    line-height: 1.8;
}
```

## Estructura de Datos

### Ejemplo de JSON para 個別契約書
```json
{
  "contract_number": "KC-2026-0001",
  "date": "2026-02-01",
  "agency": {
    "name": "ユニバーサル企画株式会社",
    "permit_number": "派13-XXXXXX",
    "address": "東京都...",
    "representative": "代表取締役 山田太郎",
    "phone": "03-XXXX-XXXX"
  },
  "client": {
    "name": "株式会社ABC",
    "address": "東京都...",
    "department": "製造部",
    "supervisor": "鈴木一郎",
    "supervisor_position": "部長"
  },
  "worker": {
    "name": "グエン・ヴァン・ミン",
    "name_kana": "グエン・ヴァン・ミン"
  },
  "placement": {
    "start_date": "2026-02-01",
    "end_date": "2026-04-30",
    "work_location": "埼玉県...",
    "work_description": "製造ライン作業",
    "work_hours": {
      "start": "08:00",
      "end": "17:00",
      "break": 60
    },
    "billing_rate": 1500,
    "overtime_rate": 1875,
    "holiday_rate": 2025
  }
}
```

## Requisitos Legales

Esta skill genera documentos que cumplen con:

1. **労働者派遣法** (Ley de派遣 de Trabajadores)
2. **労働基準法** (Ley de Normas Laborales)
3. **厚生労働省** guidelines para documentos de 派遣

### Elementos Obligatorios

| Documento | Elementos Requeridos |
|-----------|---------------------|
| 個別契約書 | 業務内容, 就業場所, 期間, 料金, 指揮命令者 |
| 労働者契約書 | 賃金, 就業時間, 社会保険, 有給休暇 |
| 就業条件明示書 | 派遣先情報, 業務内容, 安全衛生 |
| 派遣先通知書 | 社会保険加入状況, 派遣元責任者 |

## Dependencias

```bash
pip install weasyprint jinja2 pydantic
```

Para soporte de fuentes japonesas en Linux:
```bash
sudo apt-get install fonts-noto-cjk fonts-noto-cjk-extra
```

## Archivos

```
haken-contracts/
├── SKILL.md
├── scripts/
│   ├── generate_kobetsu.py      # 個別契約書
│   ├── generate_roudousha.py    # 労働者派遣契約書
│   ├── generate_contracts.py    # CLI principal
│   └── models.py                # Modelos Pydantic
├── templates/
│   ├── kobetsu_keiyaku.html     # Template 個別契約書
│   ├── roudousha_keiyaku.html   # Template 労働者契約書
│   ├── shugyou_joken.html       # Template 就業条件明示書
│   └── base.css                 # Estilos A4
├── examples/
│   └── sample_placement.json
└── assets/
    └── company_stamp.png        # 印鑑 placeholder
```

## Notas para ユニバーサル企画株式会社

Como 派遣元, los documentos generados incluyen:
- 派遣元責任者の情報
- 許可番号 prominentemente visible
- Cláusulas de 抵触日 awareness
- Información de 苦情処理 (manejo de quejas)
