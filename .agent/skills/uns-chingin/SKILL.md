---
name: uns-chingin
type: feature
description: "Generación de 賃金台帳 (registros de nómina) con cálculos fiscales japoneses. Triggers: nómina, chingin, 賃金台帳, salario, payroll, 給与計算, deducciones, 所得税, horas extra, 残業代."
source: uns
---
# UNS-CHINGIN SKILL (賃金台帳 Generator)

## Descripción

Skill especializada para generación de 賃金台帳 (registros de nómina) con todos los cálculos fiscales japoneses. Basada en el sistema Chingin-v8.0-PRO.

## Capacidades

1. **Cálculo de Salarios**: Base + horas extras + bonificaciones
2. **Deducciones Automáticas**: 健康保険, 厚生年金, 雇用保険, 所得税
3. **Multiplicadores de Horas**:
   - 残業 (Overtime): 1.25x
   - 深夜 (Nocturno 22:00-5:00): 1.25x
   - 休日 (Festivo): 1.35x
   - 残業60h超 (>60h overtime): 1.50x
4. **Generación de Excel**: Formato estándar japonés
5. **Filtrado de Archivos**: Por patrones 従業員賃金計, 請負

## Configuración UNS

```python
UNS_CONFIG = {
    "company_name": "ユニバーサル企画株式会社",
    "permit_number": "派23-303669",
    "address": "愛知県名古屋市港区名港二丁目6-30"
}
```

## Tasas de Deducción (2026)

| Concepto | Tasa | Nombre Japonés |
|----------|------|----------------|
| Seguro de Salud | 5.0% | 健康保険 |
| Pensión | 9.15% | 厚生年金 |
| Seguro de Empleo | 0.6% | 雇用保険 |

## Uso

```bash
# Generar nómina mensual
python chingin_generator.py --month 2026-01 --employees data.json

# Filtrar archivos Excel para subir
python chingin_generator.py filter --folder "/path/to/excels"

# Calcular nómina individual
python chingin_generator.py calculate --employee "NGUYEN VAN A" --hours 168 --overtime 20
```

## Integración con Repos

- **Chingin-v8.0-PRO1.28v**: Versión más reciente con backend/frontend
- **Chingin-v6.0-PRO**: Versión estable anterior
- **ChinginGenerator-v4-PRO**: Versión CLI legacy

## Archivos Generados

- `賃金台帳_YYYY年MM月.xlsx` - Registro mensual
- `給与明細_氏名_YYYY年MM月.pdf` - Recibo individual
- `源泉徴収票_氏名_YYYY年.xlsx` - Certificado fiscal anual

## Reglas de Negocio

1. **36協定**: Límite de 45h/mes overtime (80h excepcional)
2. **深夜割増**: Aplica entre 22:00-5:00
3. **休日割増**: Domingos y festivos nacionales
4. **端数処理**: Redondeo ROUND_HALF_UP
