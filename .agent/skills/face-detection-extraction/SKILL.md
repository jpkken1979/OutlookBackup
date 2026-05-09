---
name: face-detection-extraction
description: Skill especializado en detectar y recortar la foto o rostro impresa en documentos de identidad
type: feature
---

# Face Detection & Extraction Skill

## Metadata
- **Name**: face-detection-extraction
- **Version**: 1.0.0
- **Category**: image-processing, document-extraction
- **Tags**: face-detection, id-card, photo-extraction, opencv, document

## Description
Skill especializado en detectar y RECORTAR la foto/rostro impresa en documentos de identidad.

**IMPORTANTE**: Este skill NO realiza reconocimiento facial (identificación de personas).
Solo detecta la REGIÓN de la foto y la recorta para almacenarla.

## Casos de Uso
- Extraer la foto de una tarjeta de residencia (Zairyū Card)
- Extraer la foto de un pasaporte
- Extraer la foto de una licencia de conducir
- Extraer la foto de cualquier documento de identidad

## Métodos de Detección
1. **Haar Cascade** (OpenCV) - Rápido, funciona bien en fotos frontales
2. **DNN Face Detector** (OpenCV) - Más preciso, basado en deep learning
3. **Template Matching** - Para documentos con posición conocida de foto

## Desafíos en Documentos de Identidad
- La foto puede estar en diferentes posiciones según el tipo de documento
- Hologramas pueden interferir con la detección
- Fotos en blanco y negro o de baja calidad
- Diferentes tamaños de foto según el documento

## Inputs
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| image_path | string | Yes* | Ruta a la imagen del documento |
| image_bytes | bytes | Yes* | Bytes de la imagen |
| document_type | string | No | Tipo de documento para optimizar búsqueda |
| method | string | No | haar/dnn/template (default: haar) |
| min_confidence | float | No | Confianza mínima para aceptar (default: 0.5) |

*Uno de image_path o image_bytes es requerido

## Outputs
| Field | Type | Description |
|-------|------|-------------|
| success | boolean | Si se detectó al menos una foto |
| faces | list | Lista de fotos detectadas con bbox y bytes |
| warnings | list | Advertencias de detección |

## Estructura de `faces`
```json
{
  "bbox": "x,y,width,height",
  "confidence": 0.95,
  "image_bytes": "<bytes de la imagen recortada>",
  "image_mime": "image/png"
}
```

## Posiciones Típicas de Fotos

### Zairyū Card (在留カード)
- Posición: Lado izquierdo, parte superior
- Tamaño aproximado: 24mm x 30mm
- Orientación: Frontal

### Pasaporte Japonés
- Posición: Lado izquierdo
- Tamaño: 35mm x 45mm
- Orientación: Frontal

### Licencia de Conducir Japonesa
- Posición: Lado izquierdo
- Tamaño: Similar al pasaporte

## Ejemplo de Uso

```python
from face_detection_extraction import FaceDetector

detector = FaceDetector(method="haar")

# Detectar y recortar fotos
result = detector.detect_and_extract("zairyucard.jpg")

if result['success']:
    for i, face in enumerate(result['faces']):
        # Guardar foto recortada
        with open(f"face_{i}.png", "wb") as f:
            f.write(face['image_bytes'])

        print(f"Foto {i}: bbox={face['bbox']}, confidence={face['confidence']}")
```

## Dependencias
- opencv-python
- numpy
- Pillow (opcional, para conversión de formatos)

## Notas de Seguridad
- NO almacenar datos biométricos
- NO intentar identificar a la persona
- Solo se recorta la región de la foto
- La imagen se almacena como BLOB sin metadata de identidad
