# UNS-DATA-LOADER SKILL

## Descripción

Cargador de datos reales desde archivos Excel de ユニバーサル企画株式会社.
Lee los archivos de la carpeta `APP UNS-CLAUDEJP Archivos` para integrarlos con el ecosistema de agentes.

## Archivos Soportados

### Archivos Principales
| Archivo | Tipo | Contenido |
|---------|------|-----------|
| `【新】社員台帳(UNS)T　2022.04.05～.xlsm` | Excel Macro | Registro de empleados |
| `有給休暇管理.xlsm` | Excel Macro | Gestión de有給休暇 |
| `口座管理表.xlsx` | Excel | Cuentas bancarias |
| `家賃控除(社員№入力）.xlsm` | Excel Macro | Descuentos de vivienda |
| `寮家賃(UNS).xlsx` | Excel | Precios de dormitorios |

### Carpetas de Datos
| Carpeta | Contenido |
|---------|-----------|
| `factories/` | JSON de cada cliente派遣先 |
| `Kyuryo/` | Nóminas mensuales (xlsm) |
| `勤怠表ALL2025/` | Hojas de asistencia por mes |

## Uso

```python
from uns_data_loader import UNSDataLoader

loader = UNSDataLoader()

# Cargar empleados
employees = loader.load_employees()

# Cargar fábricas
factories = loader.load_factories()

# Cargar nómina de un mes
payroll = loader.load_payroll("2025.1")

# Cargar asistencia
attendance = loader.load_attendance("2025.1", "高雄工業")
```

## Dependencias

- `openpyxl` - Lectura de Excel (.xlsx)
- `xlrd` - Lectura de Excel antiguo (.xls)
- `pandas` - Manipulación de datos (opcional)

## Estructura de Datos de Salida

### Empleado
```python
{
    "employee_id": "001",
    "name_kanji": "グエン バン アイン",
    "name_kana": "ぐえん ばん あいん",
    "birth_date": "1990-05-15",
    "nationality": "ベトナム",
    "visa_type": "技能実習2号",
    "visa_expiry": "2026-03-31",
    "factory": "高雄工業株式会社",
    "plant": "本社工場",
    "start_date": "2023-04-01",
    "hourly_rate": 1650,
    "bank_account": {...}
}
```

### Fábrica
```python
{
    "factory_id": "高雄工業株式会社_本社工場",
    "client_company": {...},
    "plant": {...},
    "lines": [...],
    "schedule": {...},
    "payment": {...}
}
```

## Reglas Antigravity

- ✅ Nunca modificar archivos Excel originales
- ✅ Logging de todas las operaciones de lectura
- ✅ Cache de datos para evitar lecturas repetidas
- ✅ Validación de datos al cargar
