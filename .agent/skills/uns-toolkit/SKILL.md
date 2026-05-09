---
name: uns-toolkit
type: feature
description: "Toolkit general para operaciones UNS (派遣). Triggers: UNS toolkit, herramientas UNS, 派遣ツール, operaciones dispatch, utilidades UNS."
source: uns
---
# UNS-TOOLKIT - Herramientas Profesionales para 派遣

## Descripción

Kit de herramientas profesional para empresas de派遣社員 en Japón. Incluye CLI unificado, validadores, generadores de documentos y utilidades de conversión.

## Componentes

### 1. CLI Unificado (`uns`)
Comando único para todas las operaciones:
```bash
uns payroll calculate --month 2026-01
uns visa check --days 90
uns employee list --active
uns invoice generate --client "加藤木材"
uns report monthly --format excel
```

### 2. Validadores de Datos Japoneses
- マイナンバー (My Number) - 12 dígitos con checksum
- 在留カード番号 (Residence Card) - Formato específico
- 銀行口座 (Bank Account) - Validación por banco
- 電話番号 (Phone) - Formatos japoneses
- 郵便番号 (Postal Code) - 7 dígitos

### 3. Generador de Reportes Excel
- 賃金台帳 con formato oficial
- 勤怠表 con cálculos automáticos
- 請求書 profesional
- 源泉徴収票 anual

### 4. Conversor de Formatos
- Excel ↔ JSON
- CSV ↔ Excel
- JSON → PDF (reportes)
- Excel → CSV (exportación)

### 5. Calculadora Fiscal Completa
- 所得税 (Income Tax) con brackets 2026
- 住民税 (Resident Tax)
- 社会保険料 (Social Insurance)
- 年末調整 (Year-end Adjustment)

### 6. Sistema de Backup
- Versionado automático
- Compresión inteligente
- Restauración selectiva
- Sincronización con cloud

## Instalación

```bash
# Agregar al PATH
export PATH="$PATH:/path/to/.agent/skills/uns-toolkit/scripts"

# O usar directamente
python uns.py --help
```

## Mejores Prácticas Implementadas

- ✅ Type hints en todo el código
- ✅ Validación de entrada con Pydantic
- ✅ Logging estructurado
- ✅ Manejo de errores robusto
- ✅ Tests unitarios incluidos
- ✅ Documentación bilingüe (ES/JP)
