---
type: feature
name: haken-saas
description: "Sistema SaaS enterprise-grade para la gestión integral de empresas de envío de personal (人材派遣) en Japón. Maneja la relación tripartita派遣元/派遣先/派遣社員, cálculo automático de nóminas con deducciones japonesas (社保/雇用保険/所得税), facturación a clientes, generación de documentos legales, y cumplimiento 36協定 y抵触日. Triggers: haken saas,派遣, payroll, nómina japonesa, 36協定, teishoku, dispatch management."
---

# HAKEN-SAAS SKILL - Sistema de Gestión para 人材派遣

## Descripción

Sistema SaaS enterprise-grade para la gestión integral de empresas de envío de personal (人材派遣) en Japón. Diseñado para manejar la compleja relación tripartita entre:

- **派遣元 (Haken Moto)**: Agencia de envío
- **派遣先 (Haken Saki)**: Empresa cliente
- **派遣社員 (Haken Shain)**: Trabajador enviado

## Estructura del Proyecto

```
haken-saas/
├── haken.py                    # CLI unificado principal
├── SKILL.md                    # Esta documentación
│
├── core/                       # Núcleo del sistema
│   ├── __init__.py
│   ├── models.py              # Modelos de datos (Tenant, Client, Worker, etc.)
│   └── haken_system.py        # Sistema principal y lógica de negocio
│
├── documents/                  # Generación de documentos legales
│   ├── __init__.py
│   └── document_generator.py  # Generador de 派遣元管理台帳, 労働条件通知書, etc.
│
├── integrations/               # Integraciones externas
│   ├── __init__.py
│   ├── zengin_format.py       # Formato Zengin para transferencias bancarias
│   └── egov_api.py            # API e-Gov para trámites gubernamentales
│
└── mobile/                     # API móvil
    ├── __init__.py
    └── attendance_api.py      # API REST para fichaje GPS/QR/Slack
```

## Arquitectura del Sistema

```
╔═══════════════════════════════════════════════════════════════════════════╗
║                         HAKEN SAAS PLATFORM                                ║
╠═══════════════════════════════════════════════════════════════════════════╣
║  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐        ║
║  │   派遣元管理      │  │   派遣先管理      │  │   派遣社員管理    │        ║
║  │   (Agency)       │  │   (Client)       │  │   (Worker)       │        ║
║  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘        ║
║           │                     │                     │                   ║
║           └─────────────────────┼─────────────────────┘                   ║
║                                 ▼                                         ║
║                   ┌─────────────────────────┐                             ║
║                   │    PLACEMENT ENGINE      │                             ║
║                   │    (契約・配置管理)      │                             ║
║                   └────────────┬────────────┘                             ║
║                                │                                          ║
║      ┌─────────────────────────┼─────────────────────────┐                ║
║      ▼                         ▼                         ▼                ║
║  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐            ║
║  │  勤怠管理     │      │  給与計算     │      │  請求管理     │            ║
║  │  Attendance  │      │  Payroll     │      │  Billing     │            ║
║  └──────┬───────┘      └──────┬───────┘      └──────┬───────┘            ║
║         │                     │                     │                     ║
║         └─────────────────────┼─────────────────────┘                     ║
║                               ▼                                           ║
║                 ┌─────────────────────────┐                               ║
║                 │   COMPLIANCE ENGINE      │                               ║
║                 │   (法令遵守・書類生成)   │                               ║
║                 └─────────────────────────┘                               ║
╠═══════════════════════════════════════════════════════════════════════════╣
║  INTEGRATIONS:                                                            ║
║  • e-Gov API (電子政府)  • Zengin Format (全銀)  • Mobile API (GPS/QR)    ║
╚═══════════════════════════════════════════════════════════════════════════╝
```

## Instalación y Uso

### CLI Principal

```bash
# Ver todos los comandos disponibles
python haken.py --help

# Ver estado del sistema
python haken.py status
```

### Comandos por Módulo

#### Inicialización
```bash
python haken.py init --company "ユニバーサル企画株式会社" --permit "派23-303669"
```

#### Gestión de Trabajadores
```bash
python haken.py worker add --data worker.json
python haken.py worker list
python haken.py worker search --skill "溶接" --available
```

#### Gestión de Clientes
```bash
python haken.py client add --data client.json
python haken.py client list --all
```

#### Colocaciones (Placements)
```bash
python haken.py placement create --worker W0001 --client C0001 --start 2026-02-01
python haken.py placement check-teishoku --days 90
```

#### Nómina
```bash
python haken.py payroll calculate --month 2026-01
```

#### Facturación
```bash
python haken.py billing generate --client C0001 --month 2026-01
```

#### Cumplimiento Legal
```bash
python haken.py compliance audit
python haken.py compliance 36kyotei --month 2026-01
```

#### Documentos
```bash
python haken.py documents list
```

#### Formato Zengin
```bash
python haken.py zengin demo
python haken.py zengin validate --file archivo.txt
```

#### e-Gov
```bash
python haken.py egov list
python haken.py egov test
```

#### API de Asistencia
```bash
python haken.py attendance serve --port 8081
python haken.py attendance test
```

## Módulos Detallados

### 1. Core (core/)

#### models.py
Modelos de datos completos con dataclasses:
- `Tenant`: Agencia de envío (派遣元)
- `Client`: Empresa cliente (派遣先)
- `ClientDepartment`: Departamentos del cliente
- `Worker`: Trabajador enviado (派遣社員)
- `JobOrder`: Orden de trabajo
- `Placement`: Colocación/Contrato (relación tripartita)
- `AttendanceRecord`: Registro de asistencia
- `PayrollRecord`: Registro de nómina
- `BillingRecord`: Registro de facturación

#### haken_system.py
Sistema principal con lógica de negocio:
- Cálculo automático de 抵触日 (3 años)
- Verificación de 36協定 (45h/mes, 360h/año)
- Motor de nóminas con deducciones japonesas
- Motor de facturación con cálculo de 粗利

### 2. Documents (documents/)

#### document_generator.py
Generación de documentos obligatorios:

| Documento | 日本語名 | Función |
|-----------|---------|---------|
| Agency Ledger | 派遣元管理台帳 | `generate_haken_moto_kanri_taicho()` |
| Client Ledger | 派遣先管理台帳 | `generate_haken_saki_kanri_taicho()` |
| Dispatch Contract | 労働者派遣契約書 | `generate_haken_keiyakusho()` |
| Work Conditions | 労働条件通知書 | `generate_roudou_jouken_tsuuchisho()` |
| Employment Terms | 就業条件明示書 | `generate_shuugyou_jouken_meijisho()` |
| Wage Ledger | 賃金台帳 | `generate_chingin_daicho()` |

### 3. Integrations (integrations/)

#### zengin_format.py
Generador de archivos Zengin para transferencias bancarias:
- Formato de longitud fija (120 bytes/registro)
- Encoding Shift-JIS
- Validación de archivos
- Conversión de Katakana full-width a half-width

#### egov_api.py
Cliente para API e-Gov:
- Autenticación OAuth2
- Envío de trámites (雇用保険, 健康保険)
- Consulta de estado
- Modo sandbox para pruebas

### 4. Mobile (mobile/)

#### attendance_api.py
API REST para fichaje móvil:
- **GPS con Geofencing**: Verifica ubicación dentro del radio de trabajo
- **Código QR**: Fichaje rápido con escaneo
- **Slack Bot**: Comandos /clock-in, /clock-out, /status
- **LINE Bot**: Integración con webhook

Endpoints:
```
GET  /health              - Health check
GET  /api/summary         - Resumen diario
POST /api/clock/gps       - Fichaje GPS
POST /api/clock/qr        - Fichaje QR
POST /api/slack/command   - Webhook Slack
POST /api/line/webhook    - Webhook LINE
```

## Cálculos Financieros

### Nómina del Trabajador
```
給与総額 = (基本時給 × 通常時間)
         + (時給 × 1.25 × 残業時間)
         + (時給 × 1.25 × 深夜時間)
         + (時給 × 1.35 × 休日時間)

控除額 = 健康保険 (5.0%)
       + 厚生年金 (9.15%)
       + 雇用保険 (0.6%)
       + 所得税 (tabla progresiva)
       + 住民税 (importación)

手取り = 給与総額 - 控除額
```

### Facturación al Cliente
```
請求額 = Σ(H_base × Rate_base)
       + Σ(H_overtime × Rate_overtime)
       + Σ(H_night × Rate_night)
       + 経費

粗利 = 請求額 - 給与総額 - 社会保険料(会社負担分)
```

## Tasas de Horas Extra (割増率)

| Tipo | Tasa | Condición |
|------|------|-----------|
| 残業 (Overtime) | 1.25x | Más de 8h/día o 40h/semana |
| 深夜 (Night) | 1.25x | 22:00 - 05:00 |
| 休日 (Holiday) | 1.35x | Días festivos/domingos |
| 残業60h超 | 1.50x | Más de 60h overtime/mes |
| 深夜残業 | 1.50x | Overtime + Night combined |
| 休日深夜 | 1.60x | Holiday + Night combined |

## Reglas de 抵触日 (Teishoku-bi)

- **Límite Individual**: 3 años máximo por trabajador en mismo puesto
- **Límite Organizacional**: 3 años para el departamento receptor
- **Alertas**: 90, 60, 30 días antes del vencimiento
- **Extensión**: Requiere consulta con sindicato o representantes

## Reglas de 36協定 (Saburoku Kyoutei)

Límites de horas extra mensuales:
- **Límite general**: 45 horas/mes
- **Límite especial**: 80 horas/mes (con acuerdo especial)
- **Límite anual**: 360 horas/año

## Datos de Ejemplo

El sistema incluye datos de ejemplo en `templates/sample_data.json`:

```json
{
  "employees": [
    {
      "id": "EMP001",
      "name": "NGUYEN VAN ANH",
      "name_kana": "グエン バン アイン",
      "hourly_rate": 1200,
      "visa_type": "技能実習2号"
    }
  ],
  "company": {
    "name": "ユニバーサル企画株式会社",
    "permit": "派23-303669"
  }
}
```

## Reglas Antigravity

- ✅ Arquitectura multi-tenant con RLS
- ✅ Cifrado de datos sensibles (My Number, bancarios)
- ✅ Logging completo de auditoría
- ✅ Cumplimiento 100% con Ley de Envío de Trabajadores
- ✅ Documentación bilingüe (ES/JP)
- ✅ Type hints en todo el código
- ✅ Validación con dataclasses
- ✅ CLI unificado

## Tecnologías

- **Python 3.11+**: Lenguaje principal
- **dataclasses**: Modelado de datos
- **Decimal**: Precisión financiera
- **JSON**: Formato de datos
- **HTTP Server**: API REST nativa

---

*HAKEN SaaS v1.0.0 - Sistema de Gestión de 人材派遣*
*Creado con Claude Code para Antigravity Agents*
