---
name: decision-plan-hardening-v3.2
description: Plan multi-fase aprobado para llevar UNS Outlook Backup de v3.1.1 a v3.2.0 con hardening Win 10/11 + features de competidores
type: project
auto_saved: true
trigger: decision
date: 2026-05-13
---

# Decision: Plan multi-fase v3.1 → v3.2 aprobado

## Contexto

K. Kaneshiro pidio "entender la app, buscar apps similares en GitHub/web, implementar todo lo util,
testear que funcione 100% en Win 10/11". Pedido demasiado amplio para una sesion sola.

Decidimos: **plan completo escrito primero**, despues ejecutar por fases en sesiones separadas.

## Que se aprobo

Plan vive en `docs/PLAN_HARDENING_WIN10_11.md`. Tiene 6 fases ejecutables, cada una cerrable
en su propia sesion con commit + tests + handoff.

| Fase | Scope | Estado |
|---|---|---|
| 0 | Planificacion | ✅ aprobado 2026-05-13 |
| 1 | Test infrastructure (matrix Win 10/11 + tests version-specific) | pendiente |
| 2 | WebView2 detection + bundle bootstrapper en installer | pendiente |
| 3 | Long path support con prefijo `\\?\` | pendiente |
| 4 | Outlook version compat (M365 vs perpetual 2019/2021) | pendiente |
| 5 | Audit formal de competidores → top 3 features | pendiente |
| 6 | Implementar features + VSS hot-copy OST + release v3.2.0 | pendiente |

## Decisiones tomadas

1. **Targets de soporte**: Win 11 22H2+ y Win 10 22H2 con Outlook M365 / 2019 / 2021. NO Outlook 2016.
2. **WebView2 bundling en installer**: SI. Bootstrapper de ~1.7MB en Inno Setup (no offline standalone).
   Impacto real ~2MB, no 100MB como se pensaba inicialmente.
3. **VSS hot-copy de OST**: SI implementar en Fase 6. Fallback a comportamiento actual si no admin.
   Si no entra en sesion, baja a v3.2.1.

## Decisiones pendientes (no decididas hoy)

1. Soporte Outlook 2016: el plan asume NO, pero usuario no lo confirmo formalmente.
2. Code signing certificate (~$300/year): tracking aparte cuando usuario decida.

## Gaps criticos detectados (verificados con grep 2026-05-13)

| Gap | Evidencia | Fase que lo resuelve |
|---|---|---|
| Sin deteccion de WebView2 | `grep "WebView2" src/` vacio | Fase 2 |
| Sin manejo de long paths | `grep "\\\\\\\\?\\\\\\\\" src/` vacio | Fase 3 |
| Outlook versions hardcoded | `account_inventory.py` solo `16.0/15.0/14.0` | Fase 4 |
| Sin distinguir Outlook M365 vs perpetual | `Dispatch("Outlook.Application")` sin checkear flavor | Fase 4 |

## Workflow para proximas sesiones

1. Leer `docs/PLAN_HARDENING_WIN10_11.md` + esta memoria.
2. Identificar fase a trabajar (en orden, salvo que el usuario diga otra cosa).
3. Crear branch `feat/fase-N-<scope>`.
4. Ejecutar deliverables.
5. Tests verdes localmente + en CI.
6. Commit + push.
7. Marcar fase como ✅ en el plan.
8. Cerrar con `/finalize`.

## Referencias

- Plan completo: `docs/PLAN_HARDENING_WIN10_11.md`
- CLAUDE.md actualizado en esta sesion (testing + sub-packages + quality CI)
- Estado del producto: v3.1.1 (verificable en `build/installer.iss:5` y `pyproject.toml:10`)
