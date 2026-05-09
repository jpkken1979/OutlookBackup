---
type: feature
name: japanese-document-ocr
description: Skill especializado en OCR de documentos japoneses con soporte para Kanji, Hiragana, Katakana y detección de layout
---

# Japanese Document OCR Skill

## Metadata
- **Name**: japanese-document-ocr
- **Version**: 1.0.0
- **Category**: ocr, document-processing
- **Tags**: ocr, japanese, kanji, zairyucard, passport, license, document-extraction

## Description
Skill especializado en OCR de documentos japoneses con soporte para:
- Kanji, Hiragana, Katakana y Romaji
- Texto vertical y horizontal
- Detección de layout (etiqueta → valor)
- Preprocesamiento de imagen (rotación, contraste, recorte)
- Documentos: 在留カード (Zairyū Card), pasaporte, licencia de conducir

## Motores OCR Soportados
1. **EasyOCR** (recomendado) - Mejor precisión para japonés
2. **PaddleOCR** - Alta precisión, requiere PaddlePaddle
3. **Tesseract** - Fallback, requiere jpn.traineddata
4. **manga-ocr** - Especializado en texto japonés de manga

## Inputs
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| image_path | string | Yes* | Ruta a imagen o PDF |
| image_bytes | bytes | Yes* | Bytes de la imagen |
| engine | string | No | easyocr/paddleocr/tesseract (default: easyocr) |
| preprocess | boolean | No | Aplicar preprocesamiento (default: true) |
| detect_layout | boolean | No | Detectar pares etiqueta-valor (default: true) |
| languages | list | No | Idiomas (default: ['ja', 'en']) |

*Uno de image_path o image_bytes es requerido

## Outputs
| Field | Type | Description |
|-------|------|-------------|
| success | boolean | Si la extracción fue exitosa |
| text_blocks | list | Lista de bloques de texto con bbox y confianza |
| layout_pairs | list | Pares etiqueta→valor detectados |
| raw_text | string | Texto completo concatenado |
| warnings | list | Advertencias de calidad |

## Campos Comunes en Documentos Japoneses

### 在留カード (Zairyū Card / Residence Card)
| Campo Japonés | Campo Español | Ubicación |
|---------------|---------------|-----------|
| 氏名 | Nombre | Frente, arriba |
| 生年月日 | Fecha de nacimiento | Frente |
| 性別 | Género | Frente |
| 国籍・地域 | Nacionalidad/Región | Frente |
| 住居地 | Dirección | Frente/Reverso |
| 在留資格 | Estado de residencia | Frente |
| 在留期間 | Período de estancia | Frente |
| 就労制限の有無 | Permiso de trabajo | Frente |
| 在留カード番号 | Número de tarjeta | Frente, arriba |
| 有効期限 | Fecha de expiración | Frente |

### Pasaporte Japonés
| Campo | Descripción |
|-------|-------------|
| 氏名 | Nombre completo |
| 旅券番号 | Número de pasaporte |
| 生年月日 | Fecha de nacimiento |
| 有効期限 | Fecha de expiración |

### Licencia de Conducir
| Campo | Descripción |
|-------|-------------|
| 氏名 | Nombre |
| 免許証番号 | Número de licencia |
| 生年月日 | Fecha de nacimiento |
| 住所 | Dirección |
| 有効期限 | Fecha de expiración |

## Ejemplo de Uso

```python
from japanese_document_ocr import JapaneseDocumentOCR

ocr = JapaneseDocumentOCR(engine="easyocr")

# Extraer de imagen
result = ocr.extract("zairyucard.jpg")

print(result['layout_pairs'])
# [
#   {"label": "氏名", "value": "田中 太郎", "confidence": 0.95},
#   {"label": "生年月日", "value": "1990年01月15日", "confidence": 0.92},
#   ...
# ]

# Extraer con preprocesamiento
result = ocr.extract(
    "dark_scan.jpg",
    preprocess=True,
    detect_layout=True
)
```

## Preprocesamiento Incluido
1. **Deskew**: Enderezar imagen rotada
2. **Contrast Enhancement**: Mejorar contraste bajo
3. **Denoise**: Reducir ruido
4. **Binarization**: Convertir a blanco/negro para mejor OCR
5. **Border Crop**: Recortar bordes innecesarios

## Dependencias
- easyocr (recomendado)
- opencv-python
- numpy
- Pillow
- pdf2image (para PDFs)

## Instalación de Dependencias

```bash
pip install easyocr opencv-python numpy Pillow pdf2image

# Para Tesseract (fallback):
# Ubuntu: sudo apt-get install tesseract-ocr tesseract-ocr-jpn
# macOS: brew install tesseract tesseract-lang

# Para PaddleOCR:
# pip install paddlepaddle paddleocr
```

## Notas Importantes
- El OCR puede confundir caracteres similares (体/休, 大/太)
- Siempre verificar campos críticos con baja confianza
- Las fechas se normalizan a YYYY-MM-DD
- El texto se conserva tal como aparece (no se "corrige")
