---
name: uns-enterprise
type: feature
description: "Gestión empresarial integral para empresas 派遣 japonesas. Cubre contratos haken, nómina, cumplimiento laboral japonés, gestión de workers y automatización administrativa UNS."
source: uns
version: "1.0.0"
risk: safe
tags: [haken, dispatch, japan, empresa, rrhh, contratos, nomina, uns]
---

# UNS Enterprise — Gestión Empresarial para Empresas 派遣

> Sistema integral de gestión para empresas de dispatch/temp staffing japonesas.
> UNS = automatización para 派遣会社 (haken kaisha).

---

## ¿Cuándo usar esta skill?

- Automatizar documentación de contratos haken (派遣契約)
- Gestionar trabajadores dispatch: registro, asignación, rotación
- Calcular nómina con horas extra (残業代) y deducciones japonesas
- Generar documentos legales requeridos por ley laboral japonesa
- Cumplimiento: 労働者派遣法 (Ley de Dispatch de Trabajadores)

---

## Skills relacionadas

| Skill | Propósito |
|---|---|
| `haken-contracts` | Generación de contratos de dispatch específicos |
| `haken-documents` | Documentos administrativos del sistema haken |
| `haken-saas` | SaaS para gestión de empresa dispatch |
| `uns-hr-specialist` | Agente especialista en RRHH del ecosistema UNS |
| `haken-system-architect` | Arquitectura del sistema UNS completo |

---

## Tipos de contrato haken (派遣契約)

| Tipo | Descripción | Duración típica |
|---|---|---|
| 特定派遣 | Dispatch a empresa específica | 3-6 meses |
| 一般派遣 | Dispatch general con rotación | Variable |
| 紹介予定派遣 | Dispatch con vista a contratación | 6 meses max |

**Campos críticos obligatorios:**
- `dispatch_start_date` / `dispatch_end_date`
- `client_company` (派遣先) + `dispatching_company` (派遣元 = UNS)
- `hourly_rate` + multiplicadores de horas extra
- `work_location` + `work_hours` + supervisor en cliente

---

## Nómina — multiplicadores legales japoneses (労基法)

| Tipo de hora | Multiplicador |
|---|---|
| Horas regulares | ×1.0 |
| Horas extra semana (1-45h/mes) | ×1.25 |
| Horas extra noche (desde 22:00) | ×1.35 |
| Trabajo en días de descanso | ×1.35 |

**Deducciones obligatorias del empleado:**

| Concepto | Tasa aprox. |
|---|---|
| 健康保険 (Seguro médico) | ~5% |
| 厚生年金 (Pensión) | ~9.15% |
| 雇用保険 (Seguro desempleo) | ~0.6% |
| 所得税 (IRPF) | Escala progresiva |
| 住民税 (Impuesto municipal) | ~10% |

---

## Documentos legales obligatorios

| Documento | Cuándo |
|---|---|
| 労働条件通知書 | Al inicio de la relación laboral |
| 就業条件明示書 | Por cada contrato de dispatch |
| キャリアアップ措置 | Plan de desarrollo profesional anual |
| 同一労働同一賃金 | Verificación periódica de igualdad salarial |

---

## Límites de duración dispatch (por ley)

- Manufactura y oficina: **máx 3 años** por puesto/persona
- **26 ocupaciones exentas** (IT, traducción, diseño, contabilidad, etc.)
- Alerta automática recomendada a los 2.5 años

---

## Scripts del sistema

```bash
# Registrar trabajador
python scripts/worker_register.py --data worker.json

# Generar contrato de dispatch
python scripts/contract_generator.py --worker UNS-0001 --client "ABC株式会社" --start 2026-04-01

# Calcular nómina mensual
python scripts/payroll_calc.py --month 2026-03 --workers all

# Verificar cumplimiento (límites de duración)
python scripts/compliance_check.py --check duration_limits

# Reporte mensual
python scripts/report_monthly.py --month 2026-03 --format excel
```

---

## Variables de entorno requeridas

```bash
# .env — NUNCA commitear con valores reales
UNS_BANK_ACCOUNT=xxx          # Datos bancarios empresa
UNS_DISPATCH_LICENSE=xxx      # Número de licencia 派遣業許可
UNS_COMPANY_NAME=xxx          # Nombre legal de la empresa
UNS_COMPANY_ADDRESS=xxx       # Dirección registrada
```

---

## KPIs del sistema

| KPI | Descripción |
|---|---|
| `workers_active` | Trabajadores actualmente en dispatch |
| `workers_available` | Trabajadores disponibles para asignar |
| `fill_rate` | % de solicitudes cubiertas |
| `avg_dispatch_duration` | Duración promedio (días) |
| `renewal_rate` | % de contratos renovados |

---

## Checklist operación mensual

```
[ ] Contratos que vencen en los próximos 30 días
[ ] Nómina calculada y distribuida (último día hábil)
[ ] Informe mensual enviado a clientes activos
[ ] Alerta de límites de duración dispatch
[ ] Auditoría de igualdad salarial (同一労働同一賃金)
[ ] Backup de datos de trabajadores y contratos
```

---

*Sistema UNS Enterprise — Ecosistema Antigravity — Licencia interna*
