---
description: Auditoría de seguridad universal basada en el comando legacy security-audit.
universal: true
aliases:
  - security-audit
  - audit-security
---

# /security-audit - Auditoría de seguridad

## Objetivo

Auditar un área o el sistema completo con foco en:
- authn/authz
- injection
- exposición de secretos
- validación de entradas
- configuración insegura

## Entrada

`$ARGUMENTS`

Áreas recomendadas:
- `auth`
- `api`
- `frontend`
- `config`
- `all`

## Flujo

### 1. Delimitar superficie

Identificar archivos y rutas relevantes para el área pedida.

### 2. Ejecutar revisión orientada a riesgo

Buscar al menos:
- control de acceso roto
- SQL/command/path injection
- XSS/CSRF cuando aplique
- secretos o tokens expuestos
- CORS, cookies o headers inseguros

### 3. Reportar por severidad

Clasificar:
- CRÍTICO
- ALTO
- MEDIO
- BAJO

## Salida esperada

```markdown
## Hallazgos

### CRÍTICO
- ...

### ALTO
- ...

## Remediación
- paso concreto
- archivo o área afectada
```
