---
name: uns-rirekisho
type: feature
description: "Generación de 履歴書 (CV japonés) y 職務経歴書 en formato JIS. Triggers: rirekisho, 履歴書, curriculum, CV japonés, 職務経歴書, shokumu keirekisho, JIS format."
source: uns
---
# UNS-RIREKISHO SKILL - 履歴書生成システム

## Descripción

Sistema de generación de履歴書 (Rirekisho - Currículum Japonés) y職務経歴書 (Shokumu Keirekisho - Historial Profesional) en formato estándar japonés JIS.

## Formatos Soportados

### 1. 履歴書 (Rirekisho) - CV Estándar
Formato tradicional japonés con:
- Foto 3x4 cm (esquina superior derecha)
- 氏名 con furigana
- 生年月日 en formato japonés (令和/平成)
- 学歴・職歴 cronológico
- 免許・資格 (licencias y certificaciones)
- 志望動機 (motivación)
- 本人希望記入欄 (preferencias del candidato)

### 2. 職務経歴書 (Shokumu Keirekisho) - Historial Profesional
Documento complementario con:
- Resumen de carrera
- Detalle de cada empresa
- Logros específicos
- Habilidades técnicas

## Especificaciones JIS

Según **JIS Z 8303** (Formato de documentos):
- Tamaño: A4 o B5 (A4 más común actualmente)
- Orientación: Vertical
- Márgenes: 20mm superior/inferior, 25mm izquierda/derecha
- Fuente: 明朝体 o ゴシック体, 10.5-11pt

## Funcionalidades

### 1. Generación de Rirekisho
```python
# Estructura de datos esperada
rirekisho_data = {
    "personal": {
        "name_kanji": "山田 太郎",
        "name_furigana": "やまだ たろう",
        "name_romaji": "YAMADA Taro",
        "birth_date": "1990-05-15",
        "gender": "男",
        "nationality": "日本",
        "address": "東京都渋谷区...",
        "phone": "090-XXXX-XXXX",
        "email": "yamada@example.com",
        "photo_path": "photo.jpg"  # Opcional
    },
    "education": [
        {
            "date": "2009-04",
            "event": "東京大学 工学部 入学"
        },
        {
            "date": "2013-03",
            "event": "東京大学 工学部 卒業"
        }
    ],
    "work_history": [
        {
            "date": "2013-04",
            "event": "株式会社ABC 入社"
        },
        {
            "date": "2020-03",
            "event": "株式会社ABC 退職"
        },
        {
            "date": "2020-04",
            "event": "株式会社XYZ 入社"
        },
        {
            "date": "現在",
            "event": "在職中"
        }
    ],
    "licenses": [
        "普通自動車第一種運転免許",
        "TOEIC 850点",
        "日本語能力試験 N1"
    ],
    "motivation": "貴社の事業拡大に...",
    "preferences": "勤務地：東京都内希望"
}
```

### 2. Conversión de Fechas
- Gregoriano → 和暦 (令和/平成/昭和)
- Cálculo automático de edad

### 3. Validación de Datos
- Formato de teléfono japonés
- Código postal válido
- Fechas cronológicamente correctas

### 4. Exportación
- HTML (para impresión desde navegador)
- JSON (para integración)
- PDF (via WeasyPrint/browser)

## Uso

```bash
# Generar履歴書 desde JSON
python rirekisho.py generate --input employee.json --output rirekisho.html

# Generar職務経歴書
python rirekisho.py shokumu --input employee.json --output shokumu.html

# Generar ambos documentos
python rirekisho.py full --input employee.json --output-dir ./output/

# Validar datos antes de generar
python rirekisho.py validate --input employee.json

# Convertir fecha a 和暦
python rirekisho.py wareki --date 1990-05-15
# Output: 平成2年5月15日
```

## Modelo de Datos

```python
from dataclasses import dataclass
from datetime import date
from typing import List, Optional

@dataclass
class RirekishoEntry:
    date: str           # Fecha en formato "YYYY-MM" o "現在"
    event: str          # Descripción del evento

@dataclass
class PersonalInfo:
    name_kanji: str
    name_furigana: str
    name_romaji: Optional[str]
    birth_date: date
    gender: str
    nationality: str
    address: str
    phone: str
    email: Optional[str]
    photo_path: Optional[str]

@dataclass
class Rirekisho:
    personal: PersonalInfo
    education: List[RirekishoEntry]
    work_history: List[RirekishoEntry]
    licenses: List[str]
    motivation: str
    preferences: Optional[str]
```

## Integración

Se integra con:
- **uns-shain-daicho**: Datos de empleados
- **haken-saas**: Sistema de派遣
- **haken-documents**: Otros documentos oficiales

## Reglas para Extranjeros

Para trabajadores extranjeros (外国人労働者):
- Incluir 在留資格 (status de residencia)
- Incluir 在留カード番号
- Nombre en katakana + romaji
- Nacionalidad obligatoria

## Ejemplo de Output

El履歴書 generado incluye:
1. **Encabezado**
   - Título "履歴書"
   - Fecha de creación

2. **Sección Personal**
   - Foto (esquina derecha)
   - Nombre con furigana
   - Fecha nacimiento (和暦)
   - Dirección completa
   - Contacto

3. **学歴・職歴**
   - Tabla cronológica
   - Línea separadora entre educación y trabajo
   - "以上" al final

4. **免許・資格**
   - Lista de certificaciones

5. **志望動機・本人希望欄**
   - Texto libre

## Reglas Antigravity

- ✅ Formato JIS Z 8303 estricto
- ✅ Conversión automática a 和暦
- ✅ Validación de datos personales
- ✅ Soporte multiidioma (japonés/español)
- ✅ Logging de todas las operaciones
