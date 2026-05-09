---
name: uns-shain-daicho
type: feature
description: "Gestión de 社員台帳 (registro de empleados) para empresas 派遣. Triggers: shain daicho, 社員台帳, registro empleados, employee registry, 社員管理, datos empleados."
source: uns
---
# UNS-SHAIN-DAICHO SKILL (社員台帳 Manager)

## Descripción

Skill para gestión completa del 社員台帳 (registro de empleados) para empresas de派遣. Basada en UNS-Shain-Daicho-Manager.

## Capacidades

1. **Registro de Empleados**: Alta, baja, modificación de派遣社員
2. **Datos de Visa**: Tracking de 在留カード y vencimientos
3. **Alertas Automáticas**: Visas próximas a vencer
4. **Búsqueda Avanzada**: Por nombre, visa, fábrica
5. **Exportación**: Excel, JSON, PDF
6. **Integración Excel**: Lee archivos .xlsm estándar UNS

## Datos Gestionados

### 従業員マスタ (Datos de Empleado)
- 氏名 / 氏名カナ (Nombre)
- 生年月日 (Fecha de nacimiento)
- 国籍 (Nacionalidad)
- 住所 (Dirección)
- 電話番号 (Teléfono)
- メール (Email)

### 在留資格情報 (Datos de Visa)
- 在留カード番号 (Número de tarjeta)
- 在留資格 (Tipo de visa)
- 在留期限 (Fecha de vencimiento)
- 派遣先 (Fábrica asignada)

### 銀行情報 (Datos Bancarios)
- 銀行名 (Banco)
- 支店名 (Sucursal)
- 口座種別 (Tipo de cuenta)
- 口座番号 (Número)

## Uso

```bash
# Ver resumen de empleados
python shain_daicho.py summary --file 社員台帳.xlsm

# Ver empleados activos
python shain_daicho.py active --file 社員台帳.xlsm

# Alertas de visas próximas a vencer
python shain_daicho.py visa-alerts --days 90

# Buscar empleado
python shain_daicho.py search "NGUYEN" --file 社員台帳.xlsm

# Exportar a JSON
python shain_daicho.py export json --file 社員台帳.xlsm
```

## Tipos de Visa Soportados

| Código | Nombre | Duración |
|--------|--------|----------|
| 技能実習1号 | Trainee Level 1 | 1 año |
| 技能実習2号 | Trainee Level 2 | 2 años |
| 技能実習3号 | Trainee Level 3 | 2 años |
| 特定技能1号 | SSW Type 1 | 5 años |
| 特定技能2号 | SSW Type 2 | Indefinido |

## Niveles de Alerta de Visa

- 🔴 **URGENTE**: ≤30 días para vencer
- 🟠 **ADVERTENCIA**: 31-60 días
- 🟡 **ATENCIÓN**: 61-90 días
- 🟢 **OK**: >90 días

## Integración con Repos

- **UNS-Shain-Daicho-Manager**: Versión principal con Streamlit
- **UNS-DBUNIX**: Base de datos PostgreSQL
- **Saca-visitas-V1.0-11.25**: Sistema de visas complementario

## Estructura de Archivo Excel

El archivo `社員台帳.xlsm` esperado debe contener:
- Hoja "マスタ" con datos de empleados
- Hoja "在留" con datos de visas
- Hoja "派遣先" con fábricas

## Reglas Antigravity

- ✅ Español en documentación
- ✅ Logging obligatorio
- ✅ Artifacts en `/artifacts/shain/`
- ✅ Validación de datos
