---
name: hakensaki-geo-identifier
description: "Identifica y verifica empresas 派遣先 cruzando direcciones de empleados (社員台帳) con ubicaciones de fábricas. Resuelve ambigüedades cuando múltiples empresas comparten el mismo nombre."
source: uns
---

# HAKENSAKI GEO-IDENTIFIER SKILL

## Propósito

Técnica de geolocalización cruzada empleado-fábrica para identificar empresas `派遣先`
cuando el nombre es ambiguo o incompleto.

## Cuándo usarlo

- Hay varias empresas con el mismo nombre.
- El registro interno solo contiene nombre corto o abreviado.
- Faltan dirección, teléfono o razón social completa.
- Se necesita validar una fábrica o sede concreta antes de completar documentos.

## Principio

Los trabajadores despachados tienden a vivir cerca de la planta donde trabajan. Sus
direcciones residenciales en `社員台帳` permiten inferir la zona geográfica correcta de
la empresa.

## Algoritmo

1. Extraer de `社員台帳` todos los empleados asignados al `派遣先`.
2. Recolectar sus direcciones residenciales.
3. Agrupar por prefectura y ciudad predominantes.
4. Buscar en web empresas con ese nombre dentro de esa zona.
5. Verificar coincidencia por industria, ubicación y estructura operativa.
6. Devolver empresa verificada con nivel de confianza.

## Datos de entrada útiles

- `派遣先`
- `配属先`
- `配属ライン`
- `仕事内容`
- `住所`

## Fuentes recomendadas

- Mapion
- NAVITIME
- Baseconnect
- iタウンページ
- マイナビ
- 法人番号 / houjin.info

## Señales de confianza

- Alta: 10+ trabajadores concentrados en la misma zona y datos web consistentes.
- Media: 3-9 trabajadores con patrón geográfico razonable.
- Baja: 1-2 trabajadores o múltiples candidatos igualmente plausibles.

## Reglas

- No asumir la primera empresa encontrada.
- Normalizar katakana half-width/full-width antes de comparar.
- Buscar variantes en romaji y katakana si aplica.
- Separar empresa matriz y subsidiaria.
- Reportar siempre el nivel de confianza y la evidencia.

## Integración

- Combina bien con `uns-shain-daicho` para leer `DBGenzaiX`.
- Útil para completar `企業データ一覧`, contratos y documentos de dispatch.

## Caso real

`プレテック` fue desambiguado como `プレテック株式会社` en `岡山県井原市`,
usando un cluster de 7 trabajadores viviendo en la misma zona.
