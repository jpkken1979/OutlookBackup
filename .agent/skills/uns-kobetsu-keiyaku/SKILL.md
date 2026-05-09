---
name: uns-kobetsu-keiyaku
type: feature
description: >
---
  Documentación legal completa para contratos individuales de派遣 (個別契約書) según la
  労働者派遣法 japonesa. Contiene todos los campos obligatorios, textos legales, estructura
  de datos, y validaciones para contratos de trabajadores extranjeros. Usar SIEMPRE que
  necesites: (1) Verificar que un contrato cumple requisitos legales, (2) Entender los campos
  obligatorios del個別契約書, (3) Crear o revisar contratos de派遣, (4) Consultar la
  estructura legal japonesa de contratos de dispatch, (5) Validar datos antes de generar PDF.
  Triggers: contrato派遣, 個別契約書, dispatch contract, worker assignment, 派遣先契約,
  requisitos legales派遣, 派遣法, labor dispatch law, validar contrato, campos obligatorios,
  contrato legal japonés.
---

# UNS 個別契約書 — Referencia Legal Completa

Documentación legal para contratos individuales de派遣 según la labor de dispatch act japonesa.

## Marco Legal

La **労働者派遣法** (Ley de Dispatch de Trabajadores) regula la relación tripartita:
- **派遣元** (UNS-Kikaku): Empresa que emplea al trabajador
- **派遣先**: Empresa donde el trabajador presta servicios
- **派遣労働者**: El trabajador派遣

El **Artículo 26** establece los elementos obligatorios del contrato individual.

## 11 Elementos Obligatorios (Art. 26)

### 1. 派遣労働者の業務内容 — Descripción del trabajo
```
Campo DB: job_description
Ejemplo: "自動車部品の組立・検査" (Ensamblaje e inspección de partes automotrices)
Validación: No vacío, máx 100 caracteres
```

### 2. 就業場所 — Lugar de trabajo
```
Campos DB: factory_name, factory_address, factory_phone
Incluir: Nombre de fábrica + departamento + dirección completa
```

### 3. 指揮命令者 — Supervisor responsable
```
Campos DB: commander_dept, commander_name, commander_phone
El supervisor que da órdenes directas al trabajador en la fábrica
```

### 4. 派遣期間 — Período de dispatch
```
Campos: start_date, end_date
Límite legal: Máximo 3 años en el mismo puesto
Excepciones: 無期雇用 puede exceder 3 años
```

### 5. 就業日・就業時間 — Días y horario
```
Campos DB: calendar, work_hours, break_time
Ejemplo: "月曜日～金曜日 / 8:30～17:30 / 休憩60分"
Incluir: Días laborables, horario, descanso, horas extra
```

### 6. 安全衛生 — Seguridad e higiene
```
Texto legal fijo:
"派遣先及び派遣元事業主は、労働者派遣法第44条から第47条の2までの規定により
課された各法令を順守し、自己に課された法令上の責任を負う。"
```

### 7. 苦情処理 — Procedimiento de quejas
```
Responsables por ambas partes:
├── 派遣先: complaint_client_dept/name/phone
├── 派遣元: complaint_uns_dept/name/phone
└── 派遣元(処理): complaint_uns_handler_dept/name/phone

Procedimiento: (1) Recibir queja → (2) Notificar a責任者 → (3) Resolver rápidamente
```

### 8. 派遣料金 — Tarifa de dispatch
```
Estructura:
├── 基本時給: hourly_rate (ej: ¥1,872)
├── 残業 (125%): Math.round(rate × 1.25) (ej: ¥2,340)
├── 休日 (135%): Math.round(rate × 1.35) (ej: ¥2,527)
├── 60h超 (150%): Math.round(rate × 1.50) (ej: ¥2,808)
└── 計算単位: time_unit (15分単位 por defecto)
```

### 9. 契約解除措置 — Medidas de rescisión
```
Obligaciones de la派遣先:
（１）Notificar con anticipación razonable
（２）Buscar nuevo empleo para el trabajador (関連会社での就業を斡旋)
（３）Compensar: 30日前に予告 o pagar 30日分の賃金相当額
```

### 10. 紹介予定派遣 — Dispatch con intención de contratación
```
UNS default: 無 (no aplica)
Si aplica: especificar condiciones de contratación directa
```

### 11. 待遇決定方式 — Método de determinación de condiciones
```
UNS default: 協定対象派遣労働者（労使協定方式）
Alternativa: 派遣先均等・均衡方式
```

## Estructura del Documento PDF

```
┌──────────────────────────────────────────┐
│           人材派遣個別契約書                │ ← Título
├──────────────────────────────────────────┤
│ [甲]（派遣先）と[乙]（UNS）間の契約...     │ ← Intro
├──────────────────────────────────────────┤
│ 【派遣先】                                │
│  派遣先事業所: 名称/所在地/TEL             │
│  就業場所: 名称/所在地                     │
│  組織単位 / 抵触日                         │
│  指揮命令者: 部署/役職/氏名/TEL            │
│  製造業務専門派遣先責任者: 同上             │
│  苦情処理担当者: 同上                      │
├──────────────────────────────────────────┤
│ 【派遣元】                                │
│  製造業務専門派遣元責任者: 部署/役職/氏名/TEL│
│  苦情処理担当者: 同上                      │
├──────────────────────────────────────────┤
│ ☑ 協定対象派遣労働者に指定  □ 指定なし     │
│ ☑ 付与される福利なし  □ 付与される福利あり  │
├──────────────────────────────────────────┤
│ 【派遣内容】                              │
│  業務内容 / 責任の程度 / 派遣期間+人数     │
│  就業日 / 就業時間+休憩 / 時間外労働       │
├──────────────────────────────────────────┤
│ 【派遣料金】基本/残業/休日/60h超           │
│  労働時間の計算は 15分単位で計算する        │
├──────────────────────────────────────────┤
│ 【支払い】締日/支払日/支払方法/振込先       │
├──────────────────────────────────────────┤
│  安全・衛生 / 便宜供与 / 苦情処理方法      │
│  契約解除措置 / 紹介予定派遣 / 待遇決定方式 │
├──────────────────────────────────────────┤
│  甲: [empresa]          乙: UNS-Kikaku    │ ← Firma
│  契約日: YYYY-MM-DD                       │
└──────────────────────────────────────────┘
```

## Validaciones Antes de Generar

```
Checklist de Validación:
☐ company_name no vacío
☐ factory_address no vacío
☐ commander_name no vacío
☐ start_date < end_date
☐ end_date - start_date ≤ 3 años (para有期雇用)
☐ hourly_rate > 0
☐ Al menos 1 empleado seleccionado
☐ Empleados tienen visa vigente (visa_expiry > start_date)
☐ contract_date calculada correctamente (-2 días hábiles)
☐ Textos legales completos (6 secciones)
```

## Tipos de Trabajadores

| Tipo | Condición | Límite de Período |
|---|---|---|
| 有期雇用派遣 | Antigüedad ≤ 3 años (1095 días) | Máx 3 años en mismo puesto |
| 無期雇用派遣 | Antigüedad > 3 años | Sin límite |
| 60歳以上 | Edad ≥ 60 años | Sin límite |

## Responsabilidades por Parte

### 甲 (派遣先 — Empresa cliente)
- Designar指揮命令者
- Cumplir安全衛生
- Gestionar quejas de su lado
- Notificar 30 días antes de rescisión

### 乙 (派遣元 — UNS-Kikaku)
- Emplear al trabajador
- Pagar salario y seguros sociales
- Designar派遣元責任者
- Gestionar quejas de su lado
- Buscar nuevo empleo en caso de rescisión
