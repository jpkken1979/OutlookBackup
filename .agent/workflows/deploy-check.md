---
description: Checklist universal pre-deploy basado en el comando legacy deploy-check.
universal: true
aliases:
  - deploy-check
  - predeploy
---

# /deploy-check - Verificación previa a deploy

## Objetivo

Confirmar si el proyecto está listo para desplegar sin romper build, tests o seguridad básica.

## Entrada

`$ARGUMENTS`

Entornos sugeridos:
- `production`
- `staging`
- `local`

## Flujo

### 1. Validar build

Ejecutar los comandos de build y typecheck relevantes del repo.

### 2. Validar calidad

Ejecutar:
- lint
- tests clave
- checks de config

### 3. Validar seguridad mínima

Revisar:
- secrets
- variables de entorno necesarias
- configuración remota
- credenciales por defecto

## Salida esperada

```markdown
## Deploy Readiness

- Build: OK|FAIL
- Lint: OK|FAIL
- Tests: OK|FAIL
- Config: OK|FAIL
- Security baseline: OK|FAIL

## Bloqueantes
- ...
```
