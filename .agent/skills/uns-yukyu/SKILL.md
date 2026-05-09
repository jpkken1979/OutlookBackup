---
name: uns-yukyu
type: feature
description: "Gestión de 有給休暇 (vacaciones pagadas) según ley japonesa. Triggers: yukyu, 有給休暇, vacaciones, paid leave, 年休, días libres, holiday tracker, 休暇管理."
source: uns
---
# UNS-YUKYU SKILL - 有給休暇管理システム

## Descripción

Sistema de gestión de vacaciones pagadas (有給休暇 / Yukyu Kyuka) para empresas japonesas. Calcula automáticamente los días de vacaciones según la antigüedad y trackea el uso.

## Ley Aplicable

Según la **労働基準法 第39条** (Ley de Normas Laborales, Artículo 39):

| Antigüedad | Días de Yukyu |
|------------|---------------|
| 6 meses | 10 días |
| 1.5 años | 11 días |
| 2.5 años | 12 días |
| 3.5 años | 14 días |
| 4.5 años | 16 días |
| 5.5 años | 18 días |
| 6.5+ años | 20 días (máximo) |

## Funcionalidades

### 1. Cálculo Automático de Días
- Calcula días correspondientes según fecha de ingreso
- Considera días proporcionales para part-time
- Aplica regla de 80% asistencia

### 2. Tracking de Uso
- Registro de solicitudes de vacaciones
- Aprobación por supervisores
- Balance en tiempo real

### 3. Obligación de 5 Días
Desde 2019, empleadores deben asegurar que empleados con 10+ días tomen al menos 5 días/año.

### 4. Caducidad
- Los días no usados expiran a los 2 años
- Tracking de días por expirar

## Uso

```bash
# Calcular días para empleado
python yukyu.py calculate --employee EMP001

# Ver balance actual
python yukyu.py balance --employee EMP001

# Registrar uso de vacaciones
python yukyu.py use --employee EMP001 --days 3 --start 2026-03-01

# Alertas de cumplimiento (5 días obligatorios)
python yukyu.py compliance --year 2026

# Exportar reporte
python yukyu.py report --year 2026 --output yukyu_report.xlsx
```

## Modelo de Datos

```python
@dataclass
class YukyuRecord:
    employee_id: str
    grant_date: date        # Fecha de otorgamiento
    days_granted: int       # Días otorgados
    days_used: int          # Días usados
    days_remaining: int     # Días restantes
    expiry_date: date       # Fecha de expiración (2 años)
```

## Integración

Se integra con:
- **uns-shain-daicho**: Datos de empleados
- **uns-kintai**: Asistencia para cálculo de 80%
- **haken-saas**: Sistema派遣

## Reglas Antigravity

- ✅ Logging de todas las operaciones
- ✅ Validación de fechas
- ✅ Cumplimiento con 労働基準法
- ✅ Exportación a Excel
