---
name: GITHUB_TOKEN read-only por defecto bloquea creacion de releases
description: GitHub Actions con permisos minimos rompe softprops/action-gh-release sin avisar claro
type: project
auto_saved: true
trigger: discovery
date: 2026-05-08
---

## Gotcha
Desde 2023, GitHub cambio el default del `GITHUB_TOKEN` en Actions a permisos read-only
sobre `contents`. Esto rompe cualquier action que necesite escribir releases, tags, o
modificar el repo desde el workflow.

El error tipico de `softprops/action-gh-release@v2`:
```
Resource not accessible by integration
https://docs.github.com/rest/releases/releases#create-a-release
```

El mensaje NO menciona permisos — confuso para diagnosticar.

## Donde se vio
Run `25530099198` en `jpkken1979/OutlookBackup` — el build compilo .exe + installer OK,
los upload-artifact funcionaron, pero `Create release on tag` fallo con el error de arriba.

## Solucion
Agregar `permissions: contents: write` al job (preferible) o al workflow:

```yaml
jobs:
  build-windows:
    runs-on: windows-latest
    permissions:
      contents: write  # necesario para crear release
    steps:
      ...
      - name: Create release on tag
        if: startsWith(github.ref, 'refs/tags/v')
        uses: softprops/action-gh-release@v2
        with:
          files: dist/*.exe
```

## Implicaciones
- Aplicar a nivel de job es mas seguro que a nivel de workflow (principio de menor privilegio).
- Otros permisos comunes que pueden faltar: `pull-requests: write` (para comentar PRs),
  `issues: write` (para crear issues), `packages: write` (para publicar paquetes).
- Si el repo usa branch protection, el token de Actions tambien necesita estar permitido
  en las reglas de proteccion para crear releases.

## Como prevenir
- Cuando un workflow usa una accion que escribe al repo (releases, tags, comments),
  agregar `permissions:` explicito desde el inicio.
- Lista comun de actions que necesitan permisos extra:
  - `softprops/action-gh-release` -> `contents: write`
  - `peter-evans/create-pull-request` -> `contents: write` + `pull-requests: write`
  - `actions/create-release` (deprecated) -> `contents: write`
